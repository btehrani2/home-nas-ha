"""One update entity per item reported by the nas-health update checks.

They appear under Settings → Updates. With an install token (NAS Health → Configure)
items that nas-health marks as installable get an Install button; nas-health
checks its own policy and guards again before running anything.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import devices
from .api import NasHealthError, NasHealthInstallError
from .const import (CONF_INSTALL_TOKEN, JOB_MAX_SECONDS, JOB_POLL_SECONDS, QUEUE_MAX_SECONDS,
                    RECHECK_MAX_SECONDS, RECHECK_POLL_SECONDS)
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
        self._installing = False

    def _item(self) -> dict | None:
        return self.coordinator.data.updates.get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._item() is not None

    @property
    def supported_features(self) -> UpdateEntityFeature:
        token = self.coordinator.config_entry.options.get(CONF_INSTALL_TOKEN)
        if token and (self._item() or {}).get("installable"):
            return UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
        return UpdateEntityFeature(0)

    @property
    def in_progress(self) -> bool:
        job = (self._item() or {}).get("job") or {}
        return self._installing or job.get("state") in ("queued", "running")

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        token = self.coordinator.config_entry.options.get(CONF_INSTALL_TOKEN)
        if not token:
            raise HomeAssistantError("No install token configured (NAS Health → Configure)")
        api = self.coordinator.api
        self._installing = True
        self.async_write_ha_state()
        try:
            try:
                job = await api.install(self._key, token)
            except NasHealthInstallError as exc:
                raise HomeAssistantError(f"{self._attr_name}: {exc}") from exc
            # a job may wait in nas-health's queue ("Update all"); the run time counts from its start
            deadline = time.monotonic() + QUEUE_MAX_SECONDS + JOB_MAX_SECONDS
            running = False
            while job.get("state") in ("queued", "running"):
                if job.get("state") == "running" and not running:
                    running, deadline = True, time.monotonic() + JOB_MAX_SECONDS
                if time.monotonic() > deadline:
                    raise HomeAssistantError(f"{self._attr_name}: still running after {JOB_MAX_SECONDS // 60} min"
                                             if running else f"{self._attr_name}: still waiting in the queue")
                job = await self._poll(api, job)
            if job.get("state") != "succeeded":
                raise HomeAssistantError(f"{self._attr_name}: {job.get('message') or 'install failed'}")
            # nas-health re-runs the check after the job; wait for that result, so the
            # entity shows the new version instead of the state from before the install
            deadline = time.monotonic() + RECHECK_MAX_SECONDS
            while not job.get("rechecked", True) and time.monotonic() < deadline:
                job = await self._poll(api, job, RECHECK_POLL_SECONDS)
        finally:
            self._installing = False
            await self.coordinator.async_refresh()
            self.async_write_ha_state()

    async def _poll(self, api, job: dict, every: float = JOB_POLL_SECONDS) -> dict:
        await asyncio.sleep(every)
        try:
            return await api.job(job["id"])
        except NasHealthError:
            return job              # e.g. nginx restarting during its own update

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
