# NAS Health for Home Assistant

Shows a [nas-health](#what-is-nas-health) monitor in Home Assistant: the overall
health of a home NAS, one problem sensor per check, measured values, Repairs
issues for problems, and one **update entity** per updatable item (operating
system packages, container apps, Flatpak apps, firmware), which appear under
**Settings → Updates**.

## What is nas-health

A small manager that runs check plugins on a NAS (disks, mirrors, backups,
services, network, updates) and publishes the results through a read-only JSON
API (`/api/v1/summary`, `/api/v1/checks`, `/api/v1/updates`). Colours: red =
major impact, yellow = one capability affected, green = no problem found, cyan
= not verified recently.

## Install

1. Settings → **Marketplace** → custom repository → `https://github.com/btehrani2/home-nas-ha` (type: integration).
2. Install **NAS Health**, restart Home Assistant.
3. Settings → Devices & services → **Add integration** → NAS Health, and enter the
   API address as published by your web proxy, e.g. `https://nas.example.org/health`.

Manual install: copy `custom_components/nas_health` into `/config/custom_components/` and restart.

## What you get

| Entity | Meaning |
| --- | --- |
| `sensor.<nas>_health` | overall colour (green / yellow / red / cyan); attributes: trust, counts, checks needing attention |
| `sensor.<nas>_health_trust` | overall trust in % |
| `sensor.<nas>_updates_available` | number of items with an update |
| `binary_sensor.<check>` | one per check, **on** = yellow or red; attributes: summary, action, colour, trust |
| `sensor.<check>_<value>` | measured values; temperatures, percentages, sizes and ages enabled, the rest disabled (diagnostic) |
| `update.<item>` | one per item; **Install** button when an install token is set and nas-health allows the item |
| `binary_sensor.<nas>_fedora_reboot_required` | installed updates need a reboot |

Devices: the NAS (hub) with child devices for the operating system, network,
backups and each app. Problems also appear in **Settings → Repairs**, with what
to do.

## Installing updates (0.2.0, needs nas-health 0.4.0)

Installing is off on the NAS until `[install] enabled = true` is set in nas-health's
`config.toml`. Create a token on the NAS with `nas-health install-token` (printed
once; only its hash is stored), then enter it under Settings → Devices & services →
NAS Health → **Configure**. Update entities of allowed items then show **Install**.
Home Assistant only asks: nas-health checks its allow/deny list and that the backup
and storage checks are green, queues the update (one at a time, so "Update all" works), runs it as a systemd job (containers through
Arcane, Fedora with dnf, Flatpak), and Home Assistant shows progress until it ends.
Refusals and failures appear as an error with the reason. Leave the token empty for
display only.

Event `nas_health_state_changed` (`check_id`, `name`, `old_color`, `new_color`,
`summary`, `action`) fires when a check changes colour. The blueprint
`blueprints/automation/nas_health/alerts.yaml` turns it into phone notifications.

## Development

Tests use `pytest-homeassistant-custom-component`:

```bash
pip install pytest-homeassistant-custom-component
pytest
```

## License

MIT
