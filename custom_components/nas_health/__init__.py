"""NAS Health: shows a nas-health monitor (checks, values, updates) in Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NasHealthApi
from .const import CONF_VERIFY_SSL, DOMAIN
from .coordinator import NasHealthCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.UPDATE]

type NasHealthConfigEntry = ConfigEntry[NasHealthCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NasHealthConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    coordinator = NasHealthCoordinator(hass, entry, NasHealthApi(session, entry.data[CONF_URL]))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # the hub must exist before child devices can point at it (via_device_id)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, f"{entry.entry_id}:hub")},
        name=entry.title, manufacturer="nas-health", model="NAS",
        sw_version=coordinator.data.version, configuration_url=coordinator.guide_url)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NasHealthConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        entry.runtime_data.remove_issues()
    return ok
