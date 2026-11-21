import pytest
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nas_health.const import DOMAIN

from .conftest import URL

ENTITY = "update.nas_frigate_frigate"
JOB = {"id": "20261122T080000-abc123", "key": "updates.containers/app:frigate", "state": "queued", "name": "Frigate"}


@pytest.fixture(autouse=True)
def fast_poll(monkeypatch):
    monkeypatch.setattr("custom_components.nas_health.update.JOB_POLL_SECONDS", 0)


async def setup(hass, token="tok-123"):
    entry = MockConfigEntry(domain=DOMAIN, title="NAS", data={"url": URL, "verify_ssl": True},
                            options={"install_token": token} if token else {}, unique_id=URL)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_no_install_without_token(hass: HomeAssistant, mock_api):
    await setup(hass, token=None)
    assert not hass.states.get(ENTITY).attributes["supported_features"] & UpdateEntityFeature.INSTALL


async def test_install_feature_only_for_installable(hass: HomeAssistant, mock_api):
    await setup(hass)
    assert hass.states.get(ENTITY).attributes["supported_features"] & UpdateEntityFeature.INSTALL
    fedora = hass.states.get("update.nas_fedora_fedora_other_updates")
    assert not fedora.attributes["supported_features"] & UpdateEntityFeature.INSTALL


async def test_install_success(hass: HomeAssistant, mock_api, aioclient_mock):
    await setup(hass)
    aioclient_mock.post(f"{URL}/api/v1/install", status=202, json={"job": JOB})
    aioclient_mock.get(f"{URL}/api/v1/jobs/{JOB['id']}", json={"job": JOB | {"state": "succeeded"}})
    await hass.services.async_call("update", "install", {"entity_id": ENTITY}, blocking=True)
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts and posts[0][2] == {"key": "updates.containers/app:frigate"}
    assert posts[0][3]["Authorization"] == "Bearer tok-123"


async def test_install_refused(hass: HomeAssistant, mock_api, aioclient_mock):
    await setup(hass)
    aioclient_mock.post(f"{URL}/api/v1/install", status=409,
                        json={"error": "not installing: Nightly backup is yellow (must be green first)"})
    with pytest.raises(HomeAssistantError, match="must be green"):
        await hass.services.async_call("update", "install", {"entity_id": ENTITY}, blocking=True)
    assert hass.states.get(ENTITY).attributes["in_progress"] is False


async def test_install_job_fails(hass: HomeAssistant, mock_api, aioclient_mock):
    await setup(hass)
    aioclient_mock.post(f"{URL}/api/v1/install", status=202, json={"job": JOB})
    aioclient_mock.get(f"{URL}/api/v1/jobs/{JOB['id']}",
                       json={"job": JOB | {"state": "failed", "message": "pull failed"}})
    with pytest.raises(HomeAssistantError, match="pull failed"):
        await hass.services.async_call("update", "install", {"entity_id": ENTITY}, blocking=True)


async def test_running_job_shows_in_progress(hass: HomeAssistant, mock_api, api_data):
    api_data["updates"]["items"][0]["job"] = JOB | {"state": "running"}
    mock_api()
    await setup(hass)
    assert hass.states.get(ENTITY).attributes["in_progress"] is True


async def test_options_flow_sets_token(hass: HomeAssistant, mock_api):
    entry = await setup(hass, token=None)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"install_token": " new-token "})
    await hass.async_block_till_done()
    assert entry.options == {"install_token": "new-token"}
    assert hass.states.get(ENTITY).attributes["supported_features"] & UpdateEntityFeature.INSTALL
