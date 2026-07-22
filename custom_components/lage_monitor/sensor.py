"""Sensors for Lage Monitor."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ALERTS,
    ATTR_HEADLINES,
    ATTR_LAST_UPDATE,
    ATTR_MAP_MARKERS,
    ATTR_MILITARY_ITEMS,
    ATTR_SCORE_BREAKDOWN,
    ATTR_SOURCES,
    ATTR_TOP_KEYWORDS,
    DOMAIN,
)
from .coordinator import LageMonitorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = LageMonitorCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async_add_entities(
        [
            LageMonitorSensor(coordinator, entry, "germany_score", "Deutschland Lage-Score"),
            LageMonitorSensor(coordinator, entry, "global_score", "Welt Lage-Score"),
            LageMonitorSensor(coordinator, entry, "stability_index", "Stabilitätsindex"),
            LageMonitorSensor(coordinator, entry, "military_signal_score", "Militärisches Aktivitätssignal"),
            LageMonitorSensor(coordinator, entry, "active_alerts", "Aktive Warnungen"),
            LageMonitorSensor(coordinator, entry, "police_items", "Polizei- und Blaulichtmeldungen"),
            LageMonitorSensor(coordinator, entry, "high_priority_items", "Hochpriorisierte Ereignisse"),
        ]
    )


class LageMonitorSensor(CoordinatorEntity[LageMonitorCoordinator], SensorEntity):
    """Base sensor for Lage Monitor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LageMonitorCoordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        if "score" in key:
            self._attr_native_unit_of_measurement = "/100"
        if key in {"active_alerts", "police_items", "high_priority_items"}:
            self._attr_icon = "mdi:alert"
        else:
            self._attr_icon = "mdi:gauge"

    @property
    def native_value(self):
        """Return the state."""
        return getattr(self.coordinator.data, self._key)

    @property
    def extra_state_attributes(self):
        """Return rich context for the dashboard card."""
        if self._key != "germany_score":
            return None
        return {
            ATTR_ALERTS: self.coordinator.data.alerts,
            ATTR_HEADLINES: self.coordinator.data.headlines,
            ATTR_MAP_MARKERS: self.coordinator.data.map_markers,
            ATTR_MILITARY_ITEMS: self.coordinator.data.military_items,
            ATTR_SOURCES: self.coordinator.data.sources,
            ATTR_LAST_UPDATE: self.coordinator.data.last_update,
            ATTR_SCORE_BREAKDOWN: self.coordinator.data.score_breakdown,
            ATTR_TOP_KEYWORDS: self.coordinator.data.top_keywords,
        }
