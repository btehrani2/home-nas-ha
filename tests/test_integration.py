from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.nas_health.const import DOMAIN, EVENT_STATE_CHANGED
from custom_components.nas_health.coordinator import guide_url

from .conftest import URL


async def setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="NAS", data={"url": URL, "verify_ssl": True}, unique_id=URL)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow(hass: HomeAssistant, mock_api):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL + "/", "name": "NAS", "verify_ssl": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"url": URL, "verify_ssl": True} and result["title"] == "NAS"


async def test_config_flow_cannot_connect(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/v1/summary", status=502)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL, "name": "NAS", "verify_ssl": True})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}


async def test_entities_and_devices(hass: HomeAssistant, mock_api):
    entry = await setup(hass)
    assert hass.states.get("sensor.nas_health").state == "green"
    assert hass.states.get("sensor.nas_health_trust").state == "90.0"
    assert hass.states.get("sensor.nas_updates_available").state == "2"
    assert hass.states.get("sensor.nas_temperatures_cpu").state == "48"
    assert hass.states.get("binary_sensor.nas_temperatures").state == "off"
    frigate = hass.states.get("update.nas_frigate_frigate")
    assert frigate.state == "on" and frigate.attributes["latest_version"] == "0.17.2"
    assert hass.states.get("update.nas_nginx_web_proxy_nginx").state == "off"
    assert hass.states.get("update.nas_fedora_fedora_other_updates").state == "on"
    assert hass.states.get("binary_sensor.nas_fedora_reboot_required").state == "off"
    assert hass.states.get("binary_sensor.nas_fedora_reboot_needed").state == "off"   # the check itself
    assert not [s for s in hass.states.async_entity_ids("update") if "reboot" in s]
    devs = {d.name: d for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)}
    assert {"NAS", "NAS · Fedora", "NAS · Network", "NAS · Frigate", "NAS · nginx (web proxy)"} <= set(devs)
    assert devs["NAS · Frigate"].sw_version == "0.17.0" and devs["NAS"].sw_version == "0.3.0"
    assert devs["NAS · Network"].via_device_id == devs["NAS"].id
    # low-level values are created disabled
    reg = er.async_get(hass)
    ent = reg.async_get("sensor.nas_container_updates_updates")
    assert ent is not None and ent.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_repairs_events_and_new_entities(hass: HomeAssistant, mock_api, api_data):
    entry = await setup(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    t = api_data["checks"]["checks"][0]
    t.update(color="yellow", summary="CPU 92 °C", action="Check the fan.")
    api_data["checks"]["checks"].append({"id": "storage.space", "name": "Free space", "group": "storage",
                                         "enabled": True, "color": "green", "trust": 1, "summary": "ok",
                                         "values": {"vol1_used": {"value": 12, "unit": "%"}}})
    mock_api()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.nas_temperatures").state == "on"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_system.temperatures")
    assert issue is not None and issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["action"] == "Check the fan."
    assert issue.learn_more_url == "https://nas.example.org/#status"
    assert [e.data["new_color"] for e in events] == ["yellow"]
    assert hass.states.get("sensor.nas_free_space_vol1_used").state == "12"          # added on the fly
    t.update(color="green", summary="ok", action=None)
    mock_api()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_system.temperatures") is None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unavailable_when_api_down(hass: HomeAssistant, mock_api, aioclient_mock):
    entry = await setup(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/v1/summary", status=502)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.nas_health").state == "unavailable"


def test_guide_url():
    assert guide_url("https://nas.example.org/health") == "https://nas.example.org/#status"
    assert guide_url("http://10.0.0.5:9095") == "http://10.0.0.5:9095/#status"
