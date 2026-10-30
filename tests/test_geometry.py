"""Tests for the extracted GeoJSON geometry helpers."""

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lage_monitor"
if "lm" not in sys.modules:
    pkg = types.ModuleType("lm")
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules["lm"] = pkg

from lm import geometry  # noqa: E402


class GeometryTests(unittest.TestCase):
    SQUARE = [[[9.0, 48.0], [10.0, 48.0], [10.0, 49.0], [9.0, 49.0], [9.0, 48.0]]]

    def test_polygon_centroid_uses_lon_lat_order(self):
        ctx = geometry.geometry_context_from_geojson({"type": "Polygon", "coordinates": self.SQUARE})
        self.assertAlmostEqual(48.5, ctx["latitude"], places=4)
        self.assertAlmostEqual(9.5, ctx["longitude"], places=4)
        self.assertEqual(1, len(ctx["polygons"]))

    def test_hole_shifts_centroid_away(self):
        hole = [[9.0, 48.0], [9.5, 48.0], [9.5, 49.0], [9.0, 49.0], [9.0, 48.0]]
        ctx = geometry.geometry_context_from_geojson({"type": "Polygon", "coordinates": [self.SQUARE[0], hole]})
        self.assertGreater(ctx["longitude"], 9.5)

    def test_point_and_feature_collection(self):
        ctx = geometry.geometry_context_from_geojson(
            {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.18, 48.78]}}]}
        )
        self.assertEqual((48.78, 9.18), (ctx["latitude"], ctx["longitude"]))

    def test_invalid_coordinates_are_dropped(self):
        self.assertEqual({}, geometry.geometry_context_from_geojson({"type": "Point", "coordinates": [999, 999]}))
        self.assertEqual({}, geometry.geometry_context_from_geojson("nonsense"))

    def test_float_helpers(self):
        self.assertEqual(1.5, geometry.to_float_or_none(" 1.5 "))
        self.assertIsNone(geometry.to_float_or_none("x"))
        self.assertTrue(geometry.valid_lat_lon(48.0, 9.0))
        self.assertFalse(geometry.valid_lat_lon(91.0, 9.0))


if __name__ == "__main__":
    unittest.main()
