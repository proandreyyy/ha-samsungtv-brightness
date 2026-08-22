"""Samsung TV IP Control integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import SamsungIPControlClient
from .const import (
    CONF_CERTIFICATE_FINGERPRINT,
    CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT,
    CONF_TEXT_INPUT_ENABLED,
    CONF_TEXT_INPUT_PORT,
    CONF_TEXT_INPUT_TOKEN,
    CONF_TOKEN,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import SamsungIPControlCoordinator
from .frontend import async_register_frontend
from .sensitive_text import async_register_sensitive_text_view
from .services import async_setup_services
from .text_client import DEFAULT_TEXT_INPUT_PORT, SamsungTextInputClient

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class SamsungIPControlRuntimeData:
    """Runtime objects shared by integration platforms."""

    client: SamsungIPControlClient
    coordinator: SamsungIPControlCoordinator
    text_client: SamsungTextInputClient | None


type SamsungIPControlConfigEntry = ConfigEntry[SamsungIPControlRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration-level actions."""
    await async_register_frontend(hass)
    async_setup_services(hass)
    async_register_sensitive_text_view(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SamsungIPControlConfigEntry
) -> bool:
    """Set up one paired TV."""
    if CONF_CERTIFICATE_FINGERPRINT not in entry.data:
        raise ConfigEntryAuthFailed(
            "The Samsung TV certificate has not been trusted; pair the TV again"
        )

    client = SamsungIPControlClient(
        hass,
        entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        token=entry.data[CONF_TOKEN],
        mac=entry.data.get(CONF_MAC),
        certificate_fingerprint=entry.data[CONF_CERTIFICATE_FINGERPRINT],
    )
    coordinator = SamsungIPControlCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    text_client = None
    if (
        entry.options.get(CONF_TEXT_INPUT_ENABLED)
        and entry.options.get(CONF_TEXT_INPUT_TOKEN)
        and entry.options.get(CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT)
    ):
        text_client = SamsungTextInputClient(
            hass,
            entry.data[CONF_HOST],
            port=entry.options.get(
                CONF_TEXT_INPUT_PORT,
                DEFAULT_TEXT_INPUT_PORT,
            ),
            token=entry.options[CONF_TEXT_INPUT_TOKEN],
            certificate_fingerprint=entry.options[
                CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT
            ],
        )

    entry.runtime_data = SamsungIPControlRuntimeData(
        client=client,
        coordinator=coordinator,
        text_client=text_client,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SamsungIPControlConfigEntry
) -> bool:
    """Unload one TV."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.runtime_data.text_client is not None:
        await entry.runtime_data.text_client.async_close()
    return unloaded
