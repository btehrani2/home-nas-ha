"""Which Home Assistant device each check and update item belongs to.

Hub (the NAS hardware) with child devices: Fedora, Network, Backups and one per
app. Volumes and disks will get their own devices once nas-health reports per
device; until then storage checks sit on the hub.
"""

from __future__ import annotations

from dataclasses import dataclass

HUB = "hub"

APP_NAMES = {
    "immich": "Immich", "frigate": "Frigate", "syncthing": "Syncthing", "samba": "Samba",
    "headscale": "Headscale (VPN)", "nginx": "nginx (web proxy)", "music-assistant": "Music Assistant",
    "backrest": "Backrest", "arcane": "Arcane",
}
GROUP_DEVICES = {"network": ("network", "Network"), "backup": ("backups", "Backups")}
CHECK_DEVICES = {
    "updates.fedora": ("fedora", "Fedora"), "updates.reboot": ("fedora", "Fedora"),
    "updates.flatpak": ("fedora", "Fedora"),
    "services.immich": ("app:immich", APP_NAMES["immich"]),
    "services.frigate": ("app:frigate", APP_NAMES["frigate"]),
    "services.syncthing": ("app:syncthing", APP_NAMES["syncthing"]),
    "services.samba": ("app:samba", APP_NAMES["samba"]),
    "services.vpn": ("app:headscale", APP_NAMES["headscale"]),
    "services.sites": ("app:nginx", APP_NAMES["nginx"]),
}


@dataclass(frozen=True)
class DeviceRef:
    key: str          # stable part of the device identifier
    name: str         # suffix shown after the hub name ("" for the hub)


def for_check(check_id: str, group: str) -> DeviceRef:
    if check_id in CHECK_DEVICES:
        return DeviceRef(*CHECK_DEVICES[check_id])
    if group in GROUP_DEVICES:
        return DeviceRef(*GROUP_DEVICES[group])
    return DeviceRef(HUB, "")


def for_update(check_id: str, group: str, item: dict) -> DeviceRef:
    """Container items go to their app's device; everything else follows its check."""
    if check_id == "updates.containers" and str(item.get("id", "")).startswith("app:"):
        app = item["id"][4:]
        return DeviceRef(f"app:{app}", APP_NAMES.get(app, item.get("name") or app))
    return for_check(check_id, group)
