"""Lage Monitor integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
import voluptuous as vol

from .const import CARD_RESOURCE_URL, DOMAIN, FRONTEND_BASE_URL

_LOGGER = logging.getLogger(__name__)
FRONTEND_PATH = Path(__file__).resolve().parent / "frontend"

PLATFORMS: list[Platform] = [Platform.SENSOR]
SERVICE_TEST_ALERT = "test_alert"
TEST_ALERT_SCHEMA = vol.Schema({vol.Optional("message", default=""): str})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up shared frontend resources."""
    await _async_register_frontend(hass)
    _async_register_services(hass)
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register ``lage_monitor.test_alert`` once."""
    if hass.services.has_service(DOMAIN, SERVICE_TEST_ALERT):
        return

    async def _handle_test_alert(call: ServiceCall) -> None:
        coordinators = [c for c in hass.data.get(DOMAIN, {}).values() if hasattr(c, "send_test_alert")]
        if not coordinators:
            raise ServiceValidationError("Lage Monitor ist nicht eingerichtet.")
        for coordinator in coordinators:
            coordinator.send_test_alert(call.data["message"])

    hass.services.async_register(DOMAIN, SERVICE_TEST_ALERT, _handle_test_alert, schema=TEST_ALERT_SCHEMA)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lage Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)
    _async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
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
    # Set the flag before the first await so concurrent callers
    # (async_setup and async_setup_entry) cannot both register.
    if hass.data.get(f"{DOMAIN}_frontend_registered"):
        return
    hass.data[f"{DOMAIN}_frontend_registered"] = True

    if not FRONTEND_PATH.exists():
        _LOGGER.warning("Frontend path does not exist: %s", FRONTEND_PATH)
        hass.data[f"{DOMAIN}_frontend_registered"] = False
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_BASE_URL, str(FRONTEND_PATH), cache_headers=False)]
    )
    _LOGGER.info(
        "Registered Lage Monitor frontend path %s -> %s",
        FRONTEND_BASE_URL,
        FRONTEND_PATH,
    )

    await _async_register_lovelace_resource(hass)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Create or update the Lovelace resource in storage mode, avoiding duplicates."""
    lovelace = hass.data.get("lovelace")
    if lovelace is None or not hasattr(lovelace, "resources"):
        _LOGGER.debug("Lovelace storage resources are not available for auto-registration")
        return

    resources = lovelace.resources
    if resources is None or not hasattr(resources, "async_items"):
        _LOGGER.debug("Lovelace resources collection is not available")
        return

    # YAML-mode resources are read-only; the user manages them manually.
    if not hasattr(resources, "async_create_item"):
        _LOGGER.debug("Lovelace resources are in YAML mode, skipping auto-registration")
        return

    # The collection may not be loaded yet; without loading, async_items()
    # is empty and a new duplicate would be created on every restart.
    if getattr(resources, "loaded", True) is False:
        await resources.async_load()
        resources.loaded = True

    resource_base_url = CARD_RESOURCE_URL.split("?", 1)[0]
    matches = [
        item
        for item in resources.async_items()
        if (item.get("url") or "").split("?", 1)[0] == resource_base_url
    ]

    if matches:
        # Keep the first entry, update it to the current version if needed.
        keep, extras = matches[0], matches[1:]
        if keep.get("url") != CARD_RESOURCE_URL and hasattr(resources, "async_update_item"):
            try:
                await resources.async_update_item(
                    keep["id"],
                    {"res_type": "module", "url": CARD_RESOURCE_URL},
                )
                _LOGGER.info("Updated Lovelace resource %s -> %s", keep.get("url"), CARD_RESOURCE_URL)
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not update Lovelace resource %s to %s: %s",
                    keep.get("url"),
                    CARD_RESOURCE_URL,
                    err,
                )
        # Remove duplicate entries left over from earlier versions.
        if hasattr(resources, "async_delete_item"):
            for item in extras:
                try:
                    await resources.async_delete_item(item["id"])
                    _LOGGER.info("Removed duplicate Lovelace resource %s", item.get("url"))
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "Could not remove duplicate Lovelace resource %s: %s",
                        item.get("url"),
                        err,
                    )
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


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
