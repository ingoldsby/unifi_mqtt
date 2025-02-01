"""
Custom component that fetches UniFi device stats and publishes them via MQTT.

This integration queries a UniFi controller for device statistics and publishes
the data in three MQTT topics per device:
  • Discovery (for Home Assistant auto-discovery)
  • State (here we publish uptime)
  • Attributes (detailed stats)

The update runs every 5 minutes.
"""

import asyncio
import json
import logging
from datetime import timedelta

import pandas as pd
import voluptuous as vol
from pyunifi.controller import Controller

import homeassistant.helpers.config_validation as cv
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
    DEFAULT_SITE_ID,
    DEFAULT_PORT,
    DEFAULT_VERIFY_SSL,
    DEFAULT_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_SITE_ID, default=DEFAULT_SITE_ID): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
            vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): cv.string,
        })
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the UniFi MQTT integration."""
    conf = config.get(DOMAIN)
    if conf is None:
        _LOGGER.error("No configuration found for %s", DOMAIN)
        return False

    host = conf[CONF_HOST]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    site_id = conf[CONF_SITE_ID]
    port = conf[CONF_PORT]
    verify_ssl = conf[CONF_VERIFY_SSL]
    version = conf[CONF_VERSION]

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
        """Fetch data from the UniFi controller and publish MQTT messages."""
        try:
            unifi_devices = await hass.async_add_executor_job(controller.get_aps)
        except Exception as err:
            _LOGGER.error("Error fetching devices: %s", err)
            return

        active_devices = []

        for device in unifi_devices:
            # Only process adopted devices
            if not device.get("adopted"):
                continue

            target_mac = device.get("mac")
            try:
                devs = await hass.async_add_executor_job(controller.get_device_stat, target_mac)
            except Exception as err:
                _LOGGER.error("Error fetching stats for %s: %s", target_mac, err)
                continue

            name = devs.get("name", "Unknown")
            mac = devs.get("mac", "Unknown")
            device_type = devs.get("type", "Unknown")
            uptime_seconds = devs.get("uptime", 0)

            # Sanitize the device name for use in MQTT topics
            sanitized_name = name.replace(" ", "_").replace(".", "_").lower()

            # Format uptime
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            minutes = (uptime_seconds % 3600) // 60
            uptime = f"{days}d {hours}h {minutes}m"

            # Base attributes common to all device types
            attributes = {
                "type": device_type,
                "status": "On" if devs.get("state") == 1 else "Off",
                "mac_address": mac,
                "model": devs.get("model", "Unknown"),
                "cpu": devs.get("system-stats", {}).get("cpu", "N/A"),
                "ram": devs.get("system-stats", {}).get("mem", "N/A"),
                "activity": round(
                    (devs.get("uplink", {}).get("rx_bytes-r", 0) / 125000)
                    + (devs.get("uplink", {}).get("tx_bytes-r", 0) / 125000),
                    1,
                ),
                "bytes_rx": devs.get("rx_bytes", 0),
                "bytes_tx": devs.get("tx_bytes", 0),
                "update": "available" if devs.get("upgradable") else "none",
                "firmware_version": devs.get("version", "Unknown"),
                "ip_address": devs.get("ip", "Unknown"),
                "device_name": name,
            }

            # Process additional attributes based on device type
            if device_type == "usw":
                port_status = {}
                port_poe = {}
                port_power = {}

                if devs.get("state") == 1 and devs.get("port_table"):
                    port_table = pd.DataFrame(devs.get("port_table")).sort_values("port_idx")
                    for _, row in port_table.iterrows():
                        port_status[f"port{row['port_idx']}"] = "up" if row["up"] else "down"
                        if "poe_enable" in port_table.columns:
                            port_poe[f"port{row['port_idx']}"] = "power" if row["poe_enable"] else "none"
                        if "poe_power" in port_table.columns:
                            port_power[f"port{row['port_idx']}"] = (
                                0 if pd.isna(row["poe_power"]) else row["poe_power"]
                            )
                current_temperature = (
                    devs.get("general_temperature", "N/A") if devs.get("has_temperature") else "N/A"
                )
                attributes.update({
                    "ports_used": devs.get("num_sta", 0),
                    "ports_user": devs.get("user-num_sta", 0),
                    "ports_guest": devs.get("guest-num_sta", 0),
                    "active_ports": port_status,
                    "poe_ports": port_poe,
                    "poe_power": port_power,
                    "total_used_power": devs.get("total_used_power", 0),
                    "current_temperature": current_temperature,
                })

            elif device_type == "uap":
                vap_table = pd.DataFrame(devs.get("vap_table", []))
                radio_24ghz = {}
                radio_5ghz = {}
                radio_6ghz = {}
                if not vap_table.empty:
                    for index, row in vap_table[vap_table["radio"] == "ng"].iterrows():
                        radio_24ghz[f"ssid{index}"] = {
                            "ssid": row["essid"],
                            "channel": row["channel"],
                            "number_connected": row["num_sta"],
                            "satisfaction": 0 if row["satisfaction"] == -1 else row["satisfaction"],
                            "bytes_rx": row["rx_bytes"],
                            "bytes_tx": row["tx_bytes"],
                            "guest": row["is_guest"],
                        }
                    for index, row in vap_table[vap_table["radio"] == "na"].iterrows():
                        radio_5ghz[f"ssid{index}"] = {
                            "ssid": row["essid"],
                            "channel": row["channel"],
                            "number_connected": row["num_sta"],
                            "satisfaction": 0 if row["satisfaction"] == -1 else row["satisfaction"],
                            "bytes_rx": row["rx_bytes"],
                            "bytes_tx": row["tx_bytes"],
                            "guest": row["is_guest"],
                        }
                    for index, row in vap_table[vap_table["radio"] == "6e"].iterrows():
                        radio_6ghz[f"ssid{index}"] = {
                            "ssid": row["essid"],
                            "channel": row["channel"],
                            "number_connected": row["num_sta"],
                            "satisfaction": 0 if row["satisfaction"] == -1 else row["satisfaction"],
                            "bytes_rx": row["rx_bytes"],
                            "bytes_tx": row["tx_bytes"],
                            "guest": row["is_guest"],
                        }
                radio_clients = {}
                radio_scores = {}
                for index, radio in enumerate(devs.get("radio_table_stats", [])):
                    user_num_sta = radio.get("user-num_sta", 0)
                    satisfaction = radio.get("satisfaction", 0)
                    radio_clients[f"clients_wifi{index}"] = user_num_sta
                    radio_scores[f"score_wifi{index}"] = 0 if satisfaction == -1 else satisfaction
                attributes.update({
                    "clients": devs.get("user-wlan-num_sta", 0),
                    "guests": devs.get("guest-wlan-num_sta", 0),
                    "score": 0 if devs.get("satisfaction", 0) == -1 else devs.get("satisfaction", 0),
                    **radio_clients,
                    **radio_scores,
                    "ssids_24ghz": radio_24ghz,
                    "ssids_5ghz": radio_5ghz,
                    "ssids_6ghz": radio_6ghz,
                })

            elif device_type == "udm":
                port_status = {}
                port_poe = {}
                port_power = {}
                if devs.get("port_table"):
                    port_table = pd.DataFrame(devs.get("port_table")).sort_values("port_idx")
                    for _, row in port_table.iterrows():
                        port_status[row["port_idx"]] = "up" if row["up"] else "down"
                        port_poe[f"port{row['port_idx']}"] = "power" if row["poe_enable"] else "none"
                        port_power[f"port{row['port_idx']}"] = row["poe_power"]
                temperature_names = {}
                temperature_values = {}
                for index, temp in enumerate(devs.get("temperatures", [])):
                    temperature_names[f"temperature_{index}_name"] = temp.get("name", 0)
                    temperature_values[f"temperature_{index}_value"] = temp.get("value", 0)
                active_geo_info = devs.get("active_geo_info", {}).get("WAN", {}) if devs.get("active_geo_info") else {}
                attributes.update({
                    "isp_name": active_geo_info.get("isp_name", "Unknown"),
                    **temperature_names,
                    **temperature_values,
                    "hostname": devs.get("hostname", "Unknown"),
                    "total_max_power": devs.get("total_max_power", 0),
                    "speedtest_rundate": devs.get("speedtest-status", {}).get("rundate", 0),
                    "speedtest_latency": devs.get("speedtest-status", {}).get("latency", 0),
                    "speedtest_download": devs.get("speedtest-status", {}).get("xput_download", 0),
                    "speedtest_upload": devs.get("speedtest-status", {}).get("xput_upload", 0),
                    "total_used_power": devs.get("total_used_power", 0),
                    "lan_ip": devs.get("lan_ip", "Unknown"),
                    "number_of_connections": devs.get("num_sta", 0),
                    "ports_user": devs.get("user-num_sta", 0),
                    "ports_guest": devs.get("guest-num_sta", 0),
                    "active_ports": port_status,
                    "poe_ports": port_poe,
                    "poe_power": port_power,
                })

            # Build MQTT topics and payloads for discovery, state and attributes
            discovery_topic = f"homeassistant/sensor/{sanitized_name}/config"
            sensor_payload = {
                "name": name,
                "state_topic": f"unifi/devices/{sanitized_name}/state",
                "unique_id": mac.replace(":", ""),
                "json_attributes_topic": f"unifi/devices/{sanitized_name}/attributes",
                "device": {
                    "identifiers": [mac],
                    "name": name,
                    "manufacturer": "UniFi"
                }
            }
            await async_publish(hass, discovery_topic, json.dumps(sensor_payload), retain=True)

            state_topic = f"unifi/devices/{sanitized_name}/state"
            await async_publish(hass, state_topic, uptime, retain=True)

            attributes_topic = f"unifi/devices/{sanitized_name}/attributes"
            await async_publish(hass, attributes_topic, json.dumps(attributes), retain=True)

            active_devices.append(name)

        # Publish a summary of active devices
        summary_topic = "unifi/devices/summary"
        await async_publish(hass, summary_topic, json.dumps(active_devices), retain=True)

    # Schedule the update function to run periodically.
    async_track_time_interval(hass, update_unifi_data, timedelta(seconds=UPDATE_INTERVAL))
    # Run an initial update immediately.
    hass.async_create_task(update_unifi_data(None))

    return True
