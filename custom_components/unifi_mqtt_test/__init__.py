# __init__.py

import asyncio
import json
import logging
from datetime import timedelta

import pandas as pd
import voluptuous as vol
from pyunifi.controller import Controller

from homeassistant.components.mqtt import async_publish
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SITE_ID,
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Global variable for the update listener
UPDATE_LISTENER = None

async def async_setup_entry(hass, entry):
    """Set up the UniFi MQTT Test integration from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    site_id = entry.data[CONF_SITE_ID]
    port = entry.data[CONF_PORT]
    verify_ssl = entry.data[CONF_VERIFY_SSL]
    version = entry.data[CONF_VERSION]

    def init_controller():
        return Controller(
            host, username, password, port, version, site_id=site_id, ssl_verify=verify_ssl
        )

    try:
        controller = await hass.async_add_executor_job(init_controller)
    except Exception as e:
        _LOGGER.error("Failed to initialize UniFi controller: %s", e)
        return False

    async def update_unifi_data(now):
        # Your update_unifi_data implementation goes here.
        pass

    global UPDATE_LISTENER
    UPDATE_LISTENER = async_track_time_interval(
        hass, update_unifi_data, timedelta(seconds=UPDATE_INTERVAL)
    )
    # Run an initial update immediately.
    hass.async_create_task(update_unifi_data(None))

    return True

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    global UPDATE_LISTENER
    if UPDATE_LISTENER is not None:
        UPDATE_LISTENER()
        UPDATE_LISTENER = None
    return True
