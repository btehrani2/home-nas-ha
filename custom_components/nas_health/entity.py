"""Base entity: device info for the hub and its child devices."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NasHealthCoordinator
from .devices import HUB, DeviceRef


def device_info(coordinator: NasHealthCoordinator, ref: DeviceRef, sw_version: str | None = None) -> DeviceInfo:
    entry = coordinator.config_entry
    hub_id = (DOMAIN, f"{entry.entry_id}:{HUB}")
    data = coordinator.data
    if ref.key == HUB:
        return DeviceInfo(identifiers={hub_id}, name=entry.title, manufacturer="nas-health",
                          model="NAS", sw_version=data.version if data else None,
                          configuration_url=coordinator.guide_url)
    return DeviceInfo(identifiers={(DOMAIN, f"{entry.entry_id}:{ref.key}")},
                      name=f"{entry.title} · {ref.name}", manufacturer="nas-health",
                      model=ref.name, sw_version=sw_version,
                      via_device_id=dr.async_get_device_id_by_identifier(
                          coordinator.hass, hub_id, config_entry_id=entry.entry_id),
                      configuration_url=coordinator.guide_url)


class NasHealthEntity(CoordinatorEntity[NasHealthCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NasHealthCoordinator, unique: str, ref: DeviceRef,
                 sw_version: str | None = None) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}:{unique}"
        self._attr_device_info = device_info(coordinator, ref, sw_version)


def add_new(coordinator, async_add_entities, known: set[str], make) -> None:
    """Add entities for keys that appeared since the last update (new checks, values, items).

    ``make`` returns {key: entity} for the current data.
    """
    def _check() -> None:
        fresh = {k: e for k, e in make().items() if k not in known}
        if fresh:
            known.update(fresh)
            async_add_entities(fresh.values())
    _check()
    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_check))
