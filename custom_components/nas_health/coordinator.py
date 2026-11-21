"""Polls nas-health and keeps Repairs issues and state-change events in sync."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NasHealthApi, NasHealthError
from .const import DOMAIN, EVENT_STATE_CHANGED, PROBLEM_COLORS, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class NasHealthData:
    summary: dict[str, Any]
    checks: dict[str, dict[str, Any]]                     # check id -> check
    updates: dict[str, dict[str, Any]] = field(default_factory=dict)   # "check/item" -> item

    @property
    def version(self) -> str | None:
        return (self.summary.get("manager") or {}).get("version")


def guide_url(base_url: str) -> str:
    """The guide lives at the site root when the API is published under /health."""
    root = base_url.rstrip("/")
    return (root[: -len("/health")] if root.endswith("/health") else root) + "/#status"


class NasHealthCoordinator(DataUpdateCoordinator[NasHealthData]):
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: NasHealthApi) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api
        self.guide_url = guide_url(api.base_url)
        self._issues: set[str] = set()

    async def _async_update_data(self) -> NasHealthData:
        try:
            summary = await self.api.summary()
            checks = await self.api.checks()
            updates = await self.api.updates()
        except NasHealthError as exc:
            raise UpdateFailed(str(exc)) from exc
        data = NasHealthData(
            summary=summary,
            checks={c["id"]: c for c in checks if isinstance(c, dict) and c.get("id")},
            updates={i["key"]: i for i in updates.get("items", []) if isinstance(i, dict) and i.get("key")},
        )
        self._fire_changes(self.data, data)
        self._sync_issues(data)
        return data

    def _fire_changes(self, old: NasHealthData | None, new: NasHealthData) -> None:
        if old is None:
            return
        for cid, c in new.checks.items():
            prev = old.checks.get(cid)
            if prev is not None and prev.get("color") != c.get("color"):
                self.hass.bus.async_fire(EVENT_STATE_CHANGED, {
                    "check_id": cid, "name": c.get("name"), "old_color": prev.get("color"),
                    "new_color": c.get("color"), "summary": c.get("summary"), "action": c.get("action"),
                })

    def _issue_id(self, check_id: str) -> str:
        return f"{self.config_entry.entry_id}_{check_id}"

    def _sync_issues(self, data: NasHealthData) -> None:
        wanted: set[str] = set()
        for cid, c in data.checks.items():
            if not c.get("enabled", True) or c.get("color") not in PROBLEM_COLORS:
                continue
            issue_id = self._issue_id(cid)
            wanted.add(issue_id)
            ir.async_create_issue(
                self.hass, DOMAIN, issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR if c["color"] == "red" else ir.IssueSeverity.WARNING,
                translation_key="check_problem",
                translation_placeholders={
                    "name": str(c.get("name") or cid),
                    "summary": str(c.get("summary") or ""),
                    "action": str(c.get("action") or "See the guide."),
                },
                learn_more_url=self.guide_url,
            )
        for issue_id in self._issues - wanted:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        self._issues = wanted

    def remove_issues(self) -> None:
        for issue_id in self._issues:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        self._issues = set()
