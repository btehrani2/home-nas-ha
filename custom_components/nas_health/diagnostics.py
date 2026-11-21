"""Diagnostics download: the data last received from nas-health (it holds no secrets)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    d = c.data
    return {"url": entry.data.get("url"), "last_update_success": c.last_update_success,
            "summary": d.summary if d else None, "checks": d.checks if d else None,
            "updates": d.updates if d else None}
