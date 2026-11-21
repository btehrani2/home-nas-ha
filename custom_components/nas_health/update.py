"""One update entity per item reported by the nas-health update checks.

Display only (no install yet). They appear under Settings → Updates.
"""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import devices
from .coordinator import NasHealthCoordinator
from .entity import NasHealthEntity, add_new

SKIP = {"updates.reboot/reboot"}        # shown as the "Reboot needed" binary sensor instead


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: NasHealthCoordinator = entry.runtime_data

    def make() -> dict[str, UpdateEntity]:
        out = {}
        for key, item in coordinator.data.updates.items():
            if key in SKIP:
                continue
            check = coordinator.data.checks.get(item.get("check", ""), {})
            ref = devices.for_update(item.get("check", ""), check.get("group", "updates"), item)
            out[key] = NasHealthUpdate(coordinator, ref, key)
        return out

    add_new(coordinator, async_add_entities, set(), make)


class NasHealthUpdate(NasHealthEntity, UpdateEntity):
    def __init__(self, coordinator, ref, key: str):
        item = coordinator.data.updates[key]
        app_version = item.get("installed") if key.startswith("updates.containers/app:") else None
        super().__init__(coordinator, f"update:{key}", ref, sw_version=app_version)
        self._key = key
        self._attr_name = item.get("name") or key
        self._attr_title = item.get("name")

    def _item(self) -> dict | None:
        return self.coordinator.data.updates.get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._item() is not None

    @property
    def installed_version(self) -> str | None:
        item = self._item() or {}
        return item.get("installed") or "current"

    @property
    def latest_version(self) -> str | None:
        item = self._item() or {}
        if not item.get("available"):
            return self.installed_version
        latest = item.get("latest") or "newer version"
        return latest if latest != self.installed_version else f"{latest} (new build)"

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        # nas-health already decided; versions here are display strings ("3 updates", "v3.4.2")
        return bool((self._item() or {}).get("available"))

    @property
    def release_summary(self) -> str | None:
        s = (self._item() or {}).get("summary")
        return s[:255] if s else None

    @property
    def release_url(self) -> str | None:
        return (self._item() or {}).get("url")
