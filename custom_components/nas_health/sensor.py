"""Overall health, trust, update count and the checks' measured values."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import devices
from .const import COLORS
from .coordinator import NasHealthCoordinator
from .entity import NasHealthEntity, add_new

# values worth showing by default; everything else is created disabled (diagnostic)
PRIMARY_UNITS = {"°C", "%", "GB", "d"}
UNITS = {"°C": UnitOfTemperature.CELSIUS, "%": PERCENTAGE}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: NasHealthCoordinator = entry.runtime_data
    hub = devices.DeviceRef(devices.HUB, "")
    async_add_entities([OverallSensor(coordinator, hub), TrustSensor(coordinator, hub),
                        UpdatesSensor(coordinator, hub)])

    def make() -> dict[str, SensorEntity]:
        out = {}
        for cid, c in coordinator.data.checks.items():
            ref = devices.for_check(cid, c.get("group", ""))
            for name in (c.get("values") or {}):
                out[f"{cid}:{name}"] = ValueSensor(coordinator, ref, cid, name)
        return out

    add_new(coordinator, async_add_entities, set(), make)


class OverallSensor(NasHealthEntity, SensorEntity):
    _attr_name = "Health"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = COLORS
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, coordinator, ref):
        super().__init__(coordinator, "overall", ref)

    @property
    def native_value(self) -> str | None:
        return (self.coordinator.data.summary.get("overall") or {}).get("color")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator.data.summary
        o = s.get("overall") or {}
        return {"trust": o.get("trust"), "counts": o.get("counts"),
                "attention": [a.get("id") for a in s.get("attention", [])],
                "unverified": s.get("unverified", [])}


class TrustSensor(NasHealthEntity, SensorEntity):
    _attr_name = "Health trust"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:shield-check"

    def __init__(self, coordinator, ref):
        super().__init__(coordinator, "trust", ref)

    @property
    def native_value(self) -> float | None:
        t = (self.coordinator.data.summary.get("overall") or {}).get("trust")
        return round(t * 100, 1) if isinstance(t, (int, float)) else None


class UpdatesSensor(NasHealthEntity, SensorEntity):
    _attr_name = "Updates available"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:package-up"

    def __init__(self, coordinator, ref):
        super().__init__(coordinator, "updates_available", ref)

    @property
    def native_value(self) -> int:
        return sum(1 for i in self.coordinator.data.updates.values() if i.get("available"))


class ValueSensor(NasHealthEntity, SensorEntity):
    def __init__(self, coordinator, ref, check_id: str, name: str):
        super().__init__(coordinator, f"value:{check_id}:{name}", ref)
        self._check_id, self._name = check_id, name
        c = coordinator.data.checks[check_id]
        v = (c.get("values") or {}).get(name) or {}
        unit = v.get("unit")
        self._attr_name = f"{c.get('name', check_id)} {name.replace('_', ' ')}"
        numeric = isinstance(v.get("value"), (int, float)) and not isinstance(v.get("value"), bool)
        if unit:
            self._attr_native_unit_of_measurement = UNITS.get(unit, unit)
        if unit == "°C":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        if numeric:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        primary = numeric and unit in PRIMARY_UNITS
        self._attr_entity_registry_enabled_default = primary
        if not primary:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _value(self) -> dict | None:
        c = self.coordinator.data.checks.get(self._check_id)
        return (c.get("values") or {}).get(self._name) if c else None

    @property
    def available(self) -> bool:
        return super().available and self._value() is not None

    @property
    def native_value(self):
        v = (self._value() or {}).get("value")
        return str(v) if isinstance(v, bool) else v
