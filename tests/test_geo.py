"""Unit tests for lage_monitor.geo (no Home Assistant needed)."""

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

PKG_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "lage_monitor"
pkg = sys.modules.get("lm") or types.ModuleType("lm")
pkg.__path__ = [str(PKG_DIR)]
sys.modules["lm"] = pkg

from lm import geo  # noqa: E402

INSIDE = {
    "Berlin": (52.52, 13.405), "Hamburg": (53.551, 9.994), "München": (48.135, 11.582),
    "Aachen": (50.775, 6.084), "Flensburg": (54.783, 9.436), "Konstanz": (47.66, 9.175),
    "Görlitz": (51.152, 14.987), "Passau": (48.574, 13.431), "Freiburg": (47.999, 7.842),
    "Saarbrücken": (49.24, 6.997), "Trier": (49.756, 6.642), "Frankfurt (Oder)": (52.347, 14.551),
    "Garmisch": (47.492, 11.095), "Berchtesgaden": (47.631, 13.003), "Sylt": (54.91, 8.34),
    "Borkum": (53.59, 6.66), "Lindau": (47.546, 9.684), "Kehl": (48.57, 7.82),
    "Kleve": (51.79, 6.14), "Weil am Rhein": (47.59, 7.61), "Ahlbeck": (53.94, 14.19),
    "Kiefersfelden": (47.61, 12.18), "Cuxhaven": (53.862, 8.694), "Zittau": (50.9, 14.81),
}
OUTSIDE = {
    "Basel": (47.559, 7.588), "Salzburg": (47.809, 13.055), "Prag": (50.075, 14.438),
    "Stettin": (53.428, 14.553), "Straßburg": (48.573, 7.752), "Amsterdam": (52.368, 4.904),
    "Luxemburg": (49.611, 6.131), "Zürich": (47.377, 8.54), "Innsbruck": (47.269, 11.404),
    "Kopenhagen": (55.676, 12.568), "Breslau": (51.108, 17.039), "Venlo": (51.37, 6.169),
    "Maastricht": (50.851, 5.69), "Metz": (49.119, 6.176), "Kufstein": (47.583, 12.167),
    "Tønder": (54.934, 8.866), "Swinemünde": (53.91, 14.25), "Bregenz": (47.503, 9.747),
}


class OutlineTests(unittest.TestCase):
    def test_german_places_are_inside(self):
        wrong = [name for name, (lat, lon) in INSIDE.items() if not geo.in_germany(lat, lon)]
        self.assertEqual([], wrong)

    def test_foreign_places_near_the_border_are_outside(self):
        wrong = [name for name, (lat, lon) in OUTSIDE.items() if geo.in_germany(lat, lon)]
        self.assertEqual([], wrong)

    def test_old_bounding_box_would_have_been_wrong(self):
        min_lon, max_lat, max_lon, min_lat = 5.5, 55.2, 15.6, 47.0
        for name in ("Basel", "Salzburg", "Prag", "Stettin"):
            lat, lon = OUTSIDE[name]
            self.assertTrue(min_lon <= lon <= max_lon and min_lat <= lat <= max_lat, name)

    def test_region_of_point(self):
        self.assertEqual("de", geo.region_of_point(52.52, 13.405))
        self.assertEqual("near_abroad", geo.region_of_point(52.41, 16.93))  # Posen
        self.assertEqual("near_abroad", geo.region_of_point(49.12, 6.18))  # Metz
        self.assertEqual("world", geo.region_of_point(52.23, 21.01))  # Warschau, > ~3 deg
        self.assertEqual("world", geo.region_of_point(50.45, 30.52))  # Kiew
        self.assertEqual("world", geo.region_of_point(40.7, -74.0))  # New York


class GazetteerSanityTests(unittest.TestCase):
    def test_german_cities_have_a_state_and_lie_inside_germany(self):
        # Border towns may fall outside the coarse outline; allow a few km of slack
        # by checking against the neighbourhood, but states must always be set.
        for place in geo._PLACES:
            if place.kind == "city" and place.country == "DE":
                self.assertIsNotNone(place.state, place.name)
                self.assertIn(place.state, geo.STATES, place.name)
                self.assertEqual("de", geo.region_of_point(place.lat, place.lon), place.name)

    def test_foreign_cities_are_not_inside_germany(self):
        for place in geo._PLACES:
            if place.kind == "city" and place.country != "DE":
                self.assertFalse(geo.in_germany(place.lat, place.lon), place.name)

    def test_known_distances(self):
        berlin = geo._city_by_name("Berlin")
        hamburg = geo._city_by_name("Hamburg")
        munich = geo._city_by_name("München")
        self.assertAlmostEqual(255, geo.haversine_km(berlin.lat, berlin.lon, hamburg.lat, hamburg.lon), delta=15)
        self.assertAlmostEqual(504, geo.haversine_km(berlin.lat, berlin.lon, munich.lat, munich.lon), delta=20)

    def test_state_centroids_are_in_germany(self):
        for code, (name, lat, lon) in geo.STATES.items():
            self.assertTrue(geo.in_germany(lat, lon), name)

    def test_dienststellen_reference_known_states_and_cities(self):
        for code, (state, city) in geo.DIENSTSTELLEN.items():
            self.assertIn(state, geo.STATES, code)
            if city:
                place = geo._city_by_name(city)
                self.assertIsNotNone(place, f"{code}: {city}")
                self.assertEqual(state, place.state, f"{code}: {city}")


class PlaceMatchingTests(unittest.TestCase):
    def names(self, text):
        return [place.name for _pos, place in geo.find_places(text)]

    def test_interessen_is_not_essen(self):
        self.assertEqual([], self.names("Die Interessen der Anwohner und Adressen"))

    def test_essen_city_needs_a_preposition(self):
        self.assertEqual(["Essen"], self.names("Brand in Essen: zwei Verletzte"))
        self.assertEqual([], self.names("Beim Essen kam es zum Streit"))
        self.assertEqual([], self.names("Nach dem Essen gab es Ärger"))

    def test_halle_hall_vs_city(self):
        self.assertEqual([], self.names("Brand in der Halle eines Händlers"))
        self.assertEqual(["Halle"], self.names("Unfall in Halle gemeldet"))
        self.assertEqual(["Halle (Saale)"], self.names("Unfall in Halle (Saale)"))

    def test_umlaut_variants_match(self):
        for text in ("Düsseldorf", "Duesseldorf", "Dusseldorf"):
            self.assertEqual(["Düsseldorf"], self.names(f"Brand in {text}"), text)

    def test_city_adjective_kolner(self):
        self.assertEqual(["Köln"], self.names("Der Kölner Dom"))
        self.assertEqual(["Berlin"], self.names("Berliner Polizei"))

    def test_longest_name_wins(self):
        self.assertEqual(["Frankfurt (Oder)"], self.names("Unfall bei Frankfurt (Oder)"))
        self.assertEqual(["Sachsen-Anhalt"], self.names("Sturm über Sachsen-Anhalt"))
        self.assertEqual(["Sachsen"], self.names("Sturm über Sachsen"))

    def test_no_match_inside_longer_words(self):
        # "Bonner" -> Bonn + er is intended; a place inside a longer word is not
        self.assertEqual([], self.names("Kurseinbruch, Kielwasser und Hamburgers"))

    def test_order_of_appearance(self):
        self.assertEqual(["Bonn", "Köln"], self.names("Von Bonn nach Köln"))

    def test_count_by_country(self):
        counts = geo.count_by_country("Berlin, Hamburg und Warschau, dazu Kiew")
        self.assertEqual({"DE": 2, "PL": 1, "UA": 1}, counts)


class DienststelleTests(unittest.TestCase):
    def test_pol_prefixes(self):
        self.assertEqual(("HH", "Hamburg"), geo.parse_dienststelle("POL-HH: 261001-1. Unfall"))
        self.assertEqual(("NW", "Dortmund"), geo.parse_dienststelle("POL-DO: Einbruch"))
        self.assertEqual(("NW", None), geo.parse_dienststelle("POL-WES: Raub"))

    def test_rlp_and_thueringen_families(self):
        self.assertEqual(("RP", None), geo.parse_dienststelle("POL-PPMZ: Unfall"))
        self.assertEqual(("RP", None), geo.parse_dienststelle("POL-PDMY: Unfall"))
        self.assertEqual(("TH", None), geo.parse_dienststelle("LPI-EF: Vermisste Person"))

    def test_unknown_or_foreign_prefixes_are_not_guessed(self):
        self.assertIsNone(geo.parse_dienststelle("POL-XYZ: irgendwas"))
        self.assertIsNone(geo.parse_dienststelle("Normale Schlagzeile: ohne Kürzel"))
        self.assertIsNone(geo.parse_dienststelle("BPOL-NRW: Bundespolizei"))

    def test_dateline(self):
        self.assertEqual("Köln-Mülheim", geo.parse_dateline("Köln-Mülheim (ots) - Am Montag ..."))
        self.assertIsNone(geo.parse_dateline("Am Montag kam es zu einem Unfall"))


class LocateTests(unittest.TestCase):
    def test_dateline_has_highest_priority(self):
        match = geo.locate("POL-DO: Einbruch in Bochum", "Lünen (ots) - In der Nacht ...")
        self.assertEqual("Lünen" if geo._city_by_name("Lünen") else "Bochum", match.name)

    def test_dateline_city_used(self):
        match = geo.locate("POL-MS: Unfall auf der A1", "Münster (ots) - Am Montag ...")
        self.assertEqual(("Münster", "city", "dateline"), (match.name, match.precision, match.source))

    def test_title_city_before_dienststelle(self):
        match = geo.locate("POL-DO: Festnahme in Bochum", "")
        self.assertEqual(("Bochum", "title"), (match.name, match.source))

    def test_dienststelle_city_when_text_has_none(self):
        match = geo.locate("POL-HH: Zeugen gesucht", "Es kam zu einem Unfall.")
        self.assertEqual(("Hamburg", "dienststelle"), (match.name, match.source))

    def test_dienststelle_state_fallback_has_state_precision(self):
        match = geo.locate("POL-WES: Raub", "Unbekannte flüchteten.")
        self.assertEqual("state", match.precision)
        self.assertEqual("NW", match.state)
        self.assertEqual("Bundesland (ungefähr)", match.label)

    def test_state_and_country_fallbacks(self):
        self.assertEqual("state", geo.locate("Sturm über Bayern", "").precision)
        match = geo.locate("Drohnen über Polen gesichtet", "")
        self.assertEqual(("country", "PL"), (match.precision, match.country))

    def test_no_hit_returns_none(self):
        self.assertIsNone(geo.locate("Allgemeine Meldung ohne Ort", "Nichts Konkretes."))

    def test_interessen_does_not_create_a_marker(self):
        self.assertIsNone(geo.locate("Streit um Interessen der Länder", "Es ging um Adressen."))


class StateForPointTests(unittest.TestCase):
    def test_home_state_from_coordinates(self):
        self.assertEqual("BY", geo.state_for_point(48.14, 11.58))
        self.assertEqual("NW", geo.state_for_point(51.2, 7.0))
        self.assertIsNone(geo.state_for_point(47.56, 7.59))  # Basel is not in Germany


if __name__ == "__main__":
    unittest.main()
