import copy

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

URL = "https://nas.example.org/health"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _check(cid, name, group, color="green", values=None, summary="ok", action=None):
    return {"id": cid, "name": name, "group": group, "enabled": True, "color": color, "trust": 1.0,
            "summary": summary, "action": action, "values": values or {}, "verified_age": "1 min"}


SUMMARY = {"api_version": 1, "manager": {"version": "0.3.0"},
           "overall": {"color": "green", "trust": 0.9, "counts": {"red": 0, "yellow": 0, "green": 4, "cyan": 0}},
           "attention": [], "unverified": [], "updates_available": 2}
CHECKS = {"checks": [
    _check("system.temperatures", "Temperatures", "storage", values={"cpu": {"value": 48, "unit": "°C"}}),
    _check("network.internet", "Internet", "network", values={"ipv4_loss": {"value": 0, "unit": "%"}}),
    _check("updates.containers", "Container updates", "updates", values={"updates": {"value": 1}}),
    _check("updates.reboot", "Reboot needed", "updates", values={"reboot_needed": {"value": False}}),
]}
UPDATES = {"api_version": 1, "available": 2, "categories": [], "items": [
    {"key": "updates.containers/app:frigate", "check": "updates.containers", "id": "app:frigate",
     "name": "Frigate", "available": True, "installed": "0.17.0", "latest": "0.17.2", "summary": "new version",
     "url": "https://docker.example.org"},
    {"key": "updates.containers/app:nginx", "check": "updates.containers", "id": "app:nginx",
     "name": "nginx", "available": False, "installed": "1.31.9", "latest": "1.31.9"},
    {"key": "updates.fedora/other", "check": "updates.fedora", "id": "other", "name": "Fedora other updates",
     "available": True, "installed": "Fedora 45", "latest": "1 update", "count": 1},
    {"key": "updates.reboot/reboot", "check": "updates.reboot", "id": "reboot", "name": "Reboot needed",
     "available": False, "installed": "7.3.4"},
]}


@pytest.fixture
def api_data():
    return {"summary": copy.deepcopy(SUMMARY), "checks": copy.deepcopy(CHECKS), "updates": copy.deepcopy(UPDATES)}


@pytest.fixture
def mock_api(aioclient_mock, api_data):
    def register():
        aioclient_mock.clear_requests()
        aioclient_mock.get(f"{URL}/api/v1/summary", json=api_data["summary"])
        aioclient_mock.get(f"{URL}/api/v1/checks", json=api_data["checks"])
        aioclient_mock.get(f"{URL}/api/v1/updates", json=api_data["updates"])
    register()
    return register
