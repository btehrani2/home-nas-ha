"""Config flow: the nas-health URL (as published through the web proxy)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NasHealthApi, NasHealthError
from .const import CONF_VERIFY_SSL, DEFAULT_NAME, DOMAIN


class NasHealthConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if not url.startswith(("https://", "http://")):
                errors[CONF_URL] = "invalid_url"
            else:
                await self.async_set_unique_id(url.lower())
                self._abort_if_unique_id_configured()
                session = async_get_clientsession(self.hass, verify_ssl=user_input[CONF_VERIFY_SSL])
                try:
                    await NasHealthApi(session, url).summary()
                except NasHealthError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME].strip() or DEFAULT_NAME,
                        data={CONF_URL: url, CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]})
        defaults = user_input or {}
        schema = vol.Schema({
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "https://")): str,
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)): bool,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
