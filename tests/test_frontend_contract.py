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

    def test_external_event_fields_are_not_inserted_raw(self):
        self.assertNotIn("${item.title}", self.source)
        self.assertNotIn('href="${item.link', self.source)
        self.assertNotIn("${item.summary ||", self.source)

    def test_product_does_not_claim_ai_generation(self):
        self.assertNotIn("KI Lagebewertung", self.source)
        self.assertIn("Automatische Lageeinschätzung", self.source)


if __name__ == "__main__":
    unittest.main()
