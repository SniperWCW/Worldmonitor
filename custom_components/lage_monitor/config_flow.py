"""Config flow for Lage Monitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import selector

from .const import (
    CONF_ALERT_COOLDOWN_MIN,
    CONF_ALERT_ROUTE_DELAY,
    CONF_AUTOBAHN_ROUTES,
    CONF_WATER_ALWAYS,
    CONF_ALERT_NOTIFY_SERVICE,
    CONF_ALERT_RADIUS_KM,
    CONF_ALERT_SCORE_DROP,
    CONF_AUTOBAHN_ROADS,
    CONF_LAYER_RADIATION,
    CONF_LAYER_WATER,
    CONF_LIVE_STREAMS,
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
    CONF_WARN_AREA,
    CONF_WARN_DWD,
    CONF_WARN_LHP,
    CONF_WARN_MOWAS,
    CONF_WARN_POLICE,
    DEFAULT_ALERT_COOLDOWN_MIN,
    DEFAULT_ALERT_ROUTE_DELAY,
    DEFAULT_AUTOBAHN_ROUTES,
    DEFAULT_WATER_ALWAYS,
    DEFAULT_ALERT_NOTIFY_SERVICE,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_ALERT_SCORE_DROP,
    DEFAULT_AUTOBAHN_ROADS,
    DEFAULT_LAYER_RADIATION,
    DEFAULT_LAYER_WATER,
    DEFAULT_LIVE_STREAMS,
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
    DEFAULT_WARN_AREA,
    DEFAULT_WARN_DWD,
    DEFAULT_WARN_LHP,
    DEFAULT_WARN_MOWAS,
    DEFAULT_WARN_POLICE,
    DOMAIN,
)


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build a Home-Assistant-friendly schema without advanced selectors."""
    return vol.Schema(
        {
            vol.Optional(CONF_NINA_ARS, default=defaults.get(CONF_NINA_ARS, DEFAULT_NINA_ARS)): str,
            vol.Optional(
                CONF_WARN_AREA,
                default=defaults.get(CONF_WARN_AREA, DEFAULT_WARN_AREA),
            ): str,
            vol.Optional(
                CONF_INCLUDE_POLICE,
                default=defaults.get(CONF_INCLUDE_POLICE, DEFAULT_INCLUDE_POLICE),
            ): bool,
            vol.Optional(
                CONF_WARN_MOWAS,
                default=defaults.get(CONF_WARN_MOWAS, DEFAULT_WARN_MOWAS),
            ): bool,
            vol.Optional(
                CONF_WARN_DWD,
                default=defaults.get(CONF_WARN_DWD, DEFAULT_WARN_DWD),
            ): bool,
            vol.Optional(
                CONF_WARN_LHP,
                default=defaults.get(CONF_WARN_LHP, DEFAULT_WARN_LHP),
            ): bool,
            vol.Optional(
                CONF_WARN_POLICE,
                default=defaults.get(CONF_WARN_POLICE, DEFAULT_WARN_POLICE),
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
                    "all": "Alle Meldungen",
                    "relevant": "Nur relevante Meldungen",
                }
            ),
            vol.Optional(
                CONF_FOCUS_MODE,
                default=defaults.get(CONF_FOCUS_MODE, DEFAULT_FOCUS_MODE),
            ): vol.In(
                {
                    "germany": "Deutschlandweit",
                    "local": "Lokal",
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
                CONF_AUTOBAHN_ROADS,
                default=defaults.get(CONF_AUTOBAHN_ROADS, DEFAULT_AUTOBAHN_ROADS),
            ): str,
            vol.Optional(
                CONF_AUTOBAHN_ROUTES,
                default=defaults.get(CONF_AUTOBAHN_ROUTES, DEFAULT_AUTOBAHN_ROUTES),
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_LAYER_WATER,
                default=defaults.get(CONF_LAYER_WATER, DEFAULT_LAYER_WATER),
            ): bool,
            vol.Optional(
                CONF_WATER_ALWAYS,
                default=defaults.get(CONF_WATER_ALWAYS, DEFAULT_WATER_ALWAYS),
            ): bool,
            vol.Optional(
                CONF_LAYER_RADIATION,
                default=defaults.get(CONF_LAYER_RADIATION, DEFAULT_LAYER_RADIATION),
            ): bool,
            vol.Optional(
                CONF_LIVE_STREAMS,
                default=defaults.get(CONF_LIVE_STREAMS, DEFAULT_LIVE_STREAMS),
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_ALERT_NOTIFY_SERVICE,
                default=defaults.get(CONF_ALERT_NOTIFY_SERVICE, DEFAULT_ALERT_NOTIFY_SERVICE),
            ): str,
            vol.Optional(
                CONF_ALERT_SCORE_DROP,
                default=defaults.get(CONF_ALERT_SCORE_DROP, DEFAULT_ALERT_SCORE_DROP),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_ALERT_ROUTE_DELAY,
                default=defaults.get(CONF_ALERT_ROUTE_DELAY, DEFAULT_ALERT_ROUTE_DELAY),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=240)),
            vol.Optional(
                CONF_ALERT_COOLDOWN_MIN,
                default=defaults.get(CONF_ALERT_COOLDOWN_MIN, DEFAULT_ALERT_COOLDOWN_MIN),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
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
        """Return the options flow handler."""
        return LageMonitorOptionsFlow()


class LageMonitorOptionsFlow(config_entries.OptionsFlow):
    """Handle Lage Monitor options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_build_schema(defaults))
