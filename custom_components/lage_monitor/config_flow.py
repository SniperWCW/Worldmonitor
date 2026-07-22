"""Config flow for Lage Monitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_ALERT_RADIUS_KM,
    CONF_CUSTOM_PRESS_FEEDS,
    CONF_FOCUS_MODE,
    CONF_INCLUDE_NEWS,
    CONF_INCLUDE_POLICE,
    CONF_INCLUDE_PRESS,
    CONF_LOCAL_KEYWORDS,
    CONF_NEWS_LIMIT,
    CONF_NINA_ARS,
    CONF_POLICE_COUNT_MODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_CUSTOM_PRESS_FEEDS,
    DEFAULT_FOCUS_MODE,
    DEFAULT_INCLUDE_NEWS,
    DEFAULT_INCLUDE_POLICE,
    DEFAULT_INCLUDE_PRESS,
    DEFAULT_LOCAL_KEYWORDS,
    DEFAULT_NEWS_LIMIT,
    DEFAULT_NINA_ARS,
    DEFAULT_POLICE_COUNT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the config/options schema."""
    return vol.Schema(
        {
            vol.Optional(CONF_NINA_ARS, default=defaults.get(CONF_NINA_ARS, DEFAULT_NINA_ARS)): str,
            vol.Optional(
                CONF_INCLUDE_POLICE,
                default=defaults.get(CONF_INCLUDE_POLICE, DEFAULT_INCLUDE_POLICE),
            ): bool,
            vol.Optional(
                CONF_INCLUDE_PRESS,
                default=defaults.get(CONF_INCLUDE_PRESS, DEFAULT_INCLUDE_PRESS),
            ): bool,
            vol.Optional(
                CONF_INCLUDE_NEWS,
                default=defaults.get(CONF_INCLUDE_NEWS, DEFAULT_INCLUDE_NEWS),
            ): bool,
            vol.Optional(
                CONF_NEWS_LIMIT,
                default=defaults.get(CONF_NEWS_LIMIT, DEFAULT_NEWS_LIMIT),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=50)),
            vol.Optional(
                CONF_POLICE_COUNT_MODE,
                default=defaults.get(CONF_POLICE_COUNT_MODE, DEFAULT_POLICE_COUNT_MODE),
            ): vol.In(
                {
                    "all": "Alle Blaulichtmeldungen",
                    "relevant": "Nur relevante Meldungen",
                }
            ),
            vol.Optional(
                CONF_FOCUS_MODE,
                default=defaults.get(CONF_FOCUS_MODE, DEFAULT_FOCUS_MODE),
            ): vol.In(
                {
                    "germany": "Deutschlandweit",
                    "local": "Standort / Landkreis / Orte",
                }
            ),
            vol.Optional(
                CONF_LOCAL_KEYWORDS,
                default=defaults.get(CONF_LOCAL_KEYWORDS, DEFAULT_LOCAL_KEYWORDS),
            ): str,
            vol.Optional(
                CONF_CUSTOM_PRESS_FEEDS,
                default=defaults.get(CONF_CUSTOM_PRESS_FEEDS, DEFAULT_CUSTOM_PRESS_FEEDS),
            ): str,
            vol.Optional(
                CONF_ALERT_RADIUS_KM,
                default=defaults.get(CONF_ALERT_RADIUS_KM, DEFAULT_ALERT_RADIUS_KM),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
        }
    )


class LageMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lage Monitor."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle initial setup."""
        if user_input is not None:
            await self.async_set_unique_id("lage_monitor_default")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Lage Monitor", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_build_schema({}))

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return the options flow."""
        return LageMonitorOptionsFlow(config_entry)


class LageMonitorOptionsFlow(config_entries.OptionsFlow):
    """Handle Lage Monitor options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_build_schema(defaults))
