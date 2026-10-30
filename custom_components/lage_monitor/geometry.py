"""GeoJSON geometry helpers (pure Python, no Home Assistant imports).

Extracted from the coordinator so the geometry logic can be tested and reused
on its own. Coordinates in GeoJSON are ``[lon, lat]`` (RFC 7946); the helpers
return ``[lat, lon]`` pairs.
"""

from __future__ import annotations

from typing import Any


def to_float_or_none(value) -> float | None:
    """Convert a numeric-ish value to float when possible."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def valid_lat_lon(lat: float | None, lon: float | None) -> bool:
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def geometry_context_from_geojson(geojson: object) -> dict[str, Any]:
    """Parse RFC 7946 geometry and retain areas for precise radius checks."""
    polygons: list[list[list[list[float]]]] = []
    points: list[list[float]] = []

    def position(raw: object) -> list[float] | None:
        if not isinstance(raw, (list, tuple)) or len(raw) < 2:
            return None
        lon = to_float_or_none(raw[0])
        lat = to_float_or_none(raw[1])
        if not valid_lat_lon(lat, lon):
            return None
        return [float(lat), float(lon)]

    def ring(raw: object) -> list[list[float]]:
        if not isinstance(raw, list):
            return []
        return [parsed for item in raw if (parsed := position(item)) is not None]

    def polygon(raw: object) -> list[list[list[float]]]:
        if not isinstance(raw, list):
            return []
        parsed_rings = [parsed for item in raw if len(parsed := ring(item)) >= 3]
        return parsed_rings

    def walk(node: object) -> None:
        if not isinstance(node, dict):
            return
        kind = str(node.get("type") or "").lower()
        if kind == "featurecollection":
            for feature in node.get("features") or []:
                walk(feature)
            return
        if kind == "feature":
            walk(node.get("geometry"))
            return
        if kind == "geometrycollection":
            for geometry in node.get("geometries") or []:
                walk(geometry)
            return

        coordinates = node.get("coordinates")
        if kind == "polygon":
            parsed = polygon(coordinates)
            if parsed:
                polygons.append(parsed)
            return
        if kind == "multipolygon" and isinstance(coordinates, list):
            for raw_polygon in coordinates:
                parsed = polygon(raw_polygon)
                if parsed:
                    polygons.append(parsed)
            return
        if kind == "point":
            parsed = position(coordinates)
            if parsed:
                points.append(parsed)
            return
        if kind in {"multipoint", "linestring"} and isinstance(coordinates, list):
            points.extend(parsed for item in coordinates if (parsed := position(item)) is not None)
            return
        if kind == "multilinestring" and isinstance(coordinates, list):
            for line in coordinates:
                if isinstance(line, list):
                    points.extend(parsed for item in line if (parsed := position(item)) is not None)
            return

        # Some upstream event feeds omit the geometry type. Keep a safe point fallback.
        points.extend(
            [
                [lat, lon]
                for lon, lat in flatten_coordinates(coordinates)
                if valid_lat_lon(lat, lon)
            ]
        )

    walk(geojson)
    latitude, longitude = area_weighted_centroid(polygons)
    if latitude is None or longitude is None:
        all_points = points or [
            point
            for polygon_item in polygons
            for ring_item in polygon_item
            for point in ring_item
        ]
        if all_points:
            latitude = sum(point[0] for point in all_points) / len(all_points)
            longitude = sum(point[1] for point in all_points) / len(all_points)

    context: dict[str, Any] = {}
    if latitude is not None and longitude is not None:
        context["latitude"] = round(latitude, 6)
        context["longitude"] = round(longitude, 6)
    if polygons:
        context["polygons"] = polygons
    elif points:
        context["points"] = points
    return context

def area_weighted_centroid(
    polygons: list[list[list[list[float]]]]
) -> tuple[float | None, float | None]:
    """Return polygon centroid while subtracting holes and weighting parts by area."""
    weighted_lat = 0.0
    weighted_lon = 0.0
    total_area = 0.0
    for polygon in polygons:
        for index, ring in enumerate(polygon):
            centroid_lat, centroid_lon, area = ring_centroid(ring)
            if centroid_lat is None or centroid_lon is None or area <= 0:
                continue
            weight = area if index == 0 else -area
            weighted_lat += centroid_lat * weight
            weighted_lon += centroid_lon * weight
            total_area += weight
    if total_area <= 1e-12:
        return None, None
    return weighted_lat / total_area, weighted_lon / total_area

def ring_centroid(
    ring: list[list[float]]
) -> tuple[float | None, float | None, float]:
    """Return planar centroid and absolute area for one lat/lon ring."""
    if len(ring) < 3:
        return None, None, 0.0
    cross_sum = 0.0
    centroid_lon_sum = 0.0
    centroid_lat_sum = 0.0
    for index, current in enumerate(ring):
        following = ring[(index + 1) % len(ring)]
        current_lat, current_lon = current
        next_lat, next_lon = following
        cross = current_lon * next_lat - next_lon * current_lat
        cross_sum += cross
        centroid_lon_sum += (current_lon + next_lon) * cross
        centroid_lat_sum += (current_lat + next_lat) * cross
    if abs(cross_sum) <= 1e-12:
        return None, None, 0.0
    return (
        centroid_lat_sum / (3 * cross_sum),
        centroid_lon_sum / (3 * cross_sum),
        abs(cross_sum) / 2,
    )

def flatten_coordinates(coords) -> list[tuple[float, float]]:
    """Flatten GeoJSON coordinate arrays to lon/lat tuples."""
    if (
        isinstance(coords, list)
        and len(coords) >= 2
        and isinstance(coords[0], (int, float))
        and isinstance(coords[1], (int, float))
    ):
        return [(float(coords[0]), float(coords[1]))]

    points: list[tuple[float, float]] = []
    if isinstance(coords, list):
        for child in coords:
            points.extend(flatten_coordinates(child))
    return points
