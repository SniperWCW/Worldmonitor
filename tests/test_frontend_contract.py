"""Small static contract checks for the dependency-free Lovelace card."""

from pathlib import Path
import unittest


CARD = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "lage_monitor"
    / "frontend"
    / "lage-monitor-card.js"
)


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CARD.read_text(encoding="utf-8")

    def test_mobile_focus_navigation_is_present(self):
        self.assertIn('class="scope-tabs"', self.source)
        self.assertIn('data-focus="${key}"', self.source)

    def test_leaflet_is_contained_in_card_stacking_context(self):
        self.assertIn("isolation: isolate;", self.source)
        self.assertIn("contain: paint;", self.source)

    def test_map_tiles_send_referrer_and_use_complete_attribution(self):
        self.assertIn('referrerPolicy: "origin"', self.source)
        self.assertIn("OpenStreetMap contributors", self.source)
        self.assertNotIn('L.tileLayer("https://tile.openstreetmap.org', self.source)

    def test_map_provider_is_configurable_and_errors_are_handled(self):
        self.assertIn('tile_url: DEFAULT_TILE_URL', self.source)
        self.assertIn('this._field("tile_url", "XYZ-Kachel-URL"', self.source)
        self.assertIn('this._mapLayer.on("tileerror"', self.source)
        self.assertIn('errorTileUrl: L.Util.emptyImageUrl', self.source)

    def test_external_event_fields_are_not_inserted_raw(self):
        self.assertNotIn("${item.title}", self.source)
        self.assertNotIn('href="${item.link', self.source)
        self.assertNotIn("${item.summary ||", self.source)

    def test_product_does_not_claim_ai_generation(self):
        self.assertNotIn("KI Lagebewertung", self.source)
        self.assertIn("Automatische Lageeinschätzung", self.source)

    def test_theme_cards_filter_events_and_map(self):
        self.assertIn('data-theme="${key}"', self.source)
        self.assertIn("itemMatchesTheme", self.source)
        self.assertIn("filterMapPoints(allMapPoints, focus, activeTheme)", self.source)

    def test_mobile_signal_strip_stays_compact(self):
        mobile = self.source.split("@media (max-width: 420px)", 1)[1]
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", mobile)


if __name__ == "__main__":
    unittest.main()
