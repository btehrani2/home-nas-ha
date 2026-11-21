"""One problem sensor per check (on = yellow or red), plus "reboot needed"."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import devices
from .const import PROBLEM_COLORS
from .coordinator import NasHealthCoordinator
from .entity import NasHealthEntity, add_new


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: NasHealthCoordinator = entry.runtime_data

    def make() -> dict[str, BinarySensorEntity]:
        out: dict[str, BinarySensorEntity] = {}
        for cid, c in coordinator.data.checks.items():
            out[cid] = CheckProblem(coordinator, devices.for_check(cid, c.get("group", "")), cid)
        if "updates.reboot" in coordinator.data.checks:
            out["reboot"] = RebootNeeded(coordinator, devices.for_check("updates.reboot", "updates"))
        return out

    add_new(coordinator, async_add_entities, set(), make)


class CheckProblem(NasHealthEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, ref, check_id: str):
        super().__init__(coordinator, f"check:{check_id}", ref)
        self._check_id = check_id
        self._attr_name = coordinator.data.checks[check_id].get("name", check_id)

    def _check(self) -> dict | None:
        return self.coordinator.data.checks.get(self._check_id)

    @property
    def available(self) -> bool:
        return super().available and self._check() is not None

    @property
    def is_on(self) -> bool:
        return (self._check() or {}).get("color") in PROBLEM_COLORS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self._check() or {}
        return {"check_id": self._check_id, "color": c.get("color"), "trust": c.get("trust"),
                "summary": c.get("summary"), "action": c.get("action"),
                "verified_age": c.get("verified_age"), "group": c.get("group")}


class RebootNeeded(NasHealthEntity, BinarySensorEntity):
    _attr_name = "Reboot required"
    _attr_device_class = BinarySensorDeviceClass.UPDATE

    def __init__(self, coordinator, ref):
        super().__init__(coordinator, "reboot_needed", ref)

    @property
    def is_on(self) -> bool | None:
        c = self.coordinator.data.checks.get("updates.reboot") or {}
        v = (c.get("values") or {}).get("reboot_needed", {}).get("value")
        return v if isinstance(v, bool) else None
