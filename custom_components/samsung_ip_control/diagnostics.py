"""Diagnostics for Samsung TV IP Control."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from . import SamsungIPControlConfigEntry
from .const import (
    CONF_CERTIFICATE_FINGERPRINT,
    CONF_ENTITY_IDENTITY,
    CONF_SERIAL_HASH,
    CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT,
    CONF_TEXT_INPUT_TOKEN,
    CONF_TOKEN,
)

TO_REDACT = {
    CONF_CERTIFICATE_FINGERPRINT,
    CONF_ENTITY_IDENTITY,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_SERIAL_HASH,
    CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT,
    CONF_TEXT_INPUT_TOKEN,
    CONF_TOKEN,
    "serial",
    "speaker",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SamsungIPControlConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with credentials and private metadata redacted."""
    runtime = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "state": async_redact_data(dict(runtime.coordinator.data), TO_REDACT),
        "device": async_redact_data(runtime.coordinator.device_information, TO_REDACT),
    }
