"""Options flow for UniFi MQTT Integration."""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
import logging

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SITE_ID,
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_VERSION,
    CONF_UPDATE_INTERVAL,
    VERSION_OPTIONS,
    DEFAULT_SITE_ID,
    DEFAULT_PORT,
    DEFAULT_VERIFY_SSL,
    DEFAULT_VERSION,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for UniFi MQTT Integration."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options flow."""
        if user_input is not None:
            # Update the config entry data with the new settings.
            # Note: This replaces the entire config entry data.
            self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
            return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Required(CONF_HOST, default=self.config_entry.data.get(CONF_HOST)): cv.string,
            vol.Required(CONF_USERNAME, default=self.config_entry.data.get(CONF_USERNAME)): cv.string,
            vol.Required(CONF_PASSWORD, default=self.config_entry.data.get(CONF_PASSWORD)): cv.string,
            vol.Optional(CONF_SITE_ID, default=self.config_entry.data.get(CONF_SITE_ID, DEFAULT_SITE_ID)): cv.string,
            vol.Optional(CONF_PORT, default=self.config_entry.data.get(CONF_PORT, DEFAULT_PORT)): cv.port,
            vol.Optional(CONF_VERIFY_SSL, default=self.config_entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)): cv.boolean,
            vol.Optional(CONF_VERSION, default=self.config_entry.data.get(CONF_VERSION, DEFAULT_VERSION)): vol.In(VERSION_OPTIONS),
            vol.Optional(CONF_UPDATE_INTERVAL, default=self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)): cv.positive_int,
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)

async def async_get_options_flow(config_entry):
    """Return options flow handler for UniFi MQTT Integration."""
    return OptionsFlowHandler(config_entry)
