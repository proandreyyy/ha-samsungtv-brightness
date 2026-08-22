"""Integration actions for Samsung TV IP Control."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN
from .text_client import MAX_TEXT_LENGTH

SERVICE_SEND_TEXT = "send_text"


def _validate_printable_text(value: object) -> str:
    """Validate bounded printable service-action text."""
    text = cv.string(value)
    if text and not text.isprintable():
        raise vol.Invalid("Text must not contain control characters")
    return text


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration-level entity actions."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_TEXT,
        entity_domain=REMOTE_DOMAIN,
        schema={
            vol.Required("text"): vol.All(
                cv.string,
                vol.Length(min=0, max=MAX_TEXT_LENGTH),
                _validate_printable_text,
            ),
            vol.Optional("submit", default=False): cv.boolean,
        },
        func="async_send_text",
    )
