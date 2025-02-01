from datetime import timedelta

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SITE_ID,
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_VERSION,
    UPDATE_INTERVAL,  # Now 30 seconds
)

    # Schedule the update function to run periodically.
    global UPDATE_LISTENER
    UPDATE_LISTENER = async_track_time_interval(
        hass, update_unifi_data, timedelta(seconds=UPDATE_INTERVAL)
    )
    # Run an initial update immediately.
    hass.async_create_task(update_unifi_data(None))
