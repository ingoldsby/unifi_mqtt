"""Constants for the UniFi MQTT Test integration."""

DOMAIN = "unifi_mqtt_test"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SITE_ID = "site_id"
CONF_PORT = "port"
CONF_VERIFY_SSL = "verify_ssl"
CONF_VERSION = "version"

DEFAULT_SITE_ID = "default"
DEFAULT_PORT = 443
DEFAULT_VERIFY_SSL = True
DEFAULT_VERSION = "UDMP-unifiOS"

# Update interval is now 30 seconds instead of 5 minutes.
UPDATE_INTERVAL = 30  # seconds
