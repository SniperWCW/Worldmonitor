"""Lage Monitor integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CARD_RESOURCE_URL, DOMAIN, FRONTEND_BASE_URL

_LOGGER = logging.getLogger(__name__)
FRONTEND_PATH = Path(__file__).resolve().parent / "frontend"

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up shared frontend resources."""
    await _async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lage Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Expose and auto-register the Lovelace card resource when possible."""
    if hass.data.get(f"{DOMAIN}_frontend_registered"):
        return

    if not FRONTEND_PATH.exists():
        _LOGGER.warning("Frontend path does not exist: %s", FRONTEND_PATH)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_BASE_URL, str(FRONTEND_PATH), cache_headers=False)]
    )
    _LOGGER.info(
        "Registered Lage Monitor frontend path %s -> %s",
        FRONTEND_BASE_URL,
        FRONTEND_PATH,
    )

    hass.data[f"{DOMAIN}_frontend_registered"] = True
    await _async_register_lovelace_resource(hass)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Create the Lovelace resource in storage mode if it is not already present."""
    lovelace = hass.data.get("lovelace")
    if lovelace is None or not hasattr(lovelace, "resources"):
        _LOGGER.debug("Lovelace storage resources are not available for auto-registration")
        return

    resources = lovelace.resources
    if resources is None or not hasattr(resources, "async_items"):
        _LOGGER.debug("Lovelace resources collection is not available")
        return

    existing = resources.async_items()
    for item in existing:
        if item.get("url") == CARD_RESOURCE_URL:
            return

    try:
        await resources.async_create_item({"res_type": "module", "url": CARD_RESOURCE_URL})
        _LOGGER.info("Registered Lovelace resource %s", CARD_RESOURCE_URL)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not auto-register Lovelace resource %s: %s",
            CARD_RESOURCE_URL,
            err,
        )
