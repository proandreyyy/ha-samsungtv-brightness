"""Authenticated, non-persistent transport for Samsung system text."""

from __future__ import annotations

from http import HTTPStatus
from typing import Final

import voluptuous as vol
from aiohttp import web
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .text_client import (
    MAX_TEXT_LENGTH,
    SamsungTextInputAuthError,
    SamsungTextInputCertificateError,
    SamsungTextInputError,
)

SENSITIVE_TEXT_API_PATH: Final = f"api/{DOMAIN}/sensitive_text"
SENSITIVE_TEXT_API_URL: Final = f"/{SENSITIVE_TEXT_API_PATH}"
MAX_REQUEST_BYTES: Final = 4096
NO_STORE_HEADERS: Final = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
}


def _validate_sensitive_text(value: object) -> str:
    """Validate bounded text without copying it into an error message."""
    if not isinstance(value, str):
        raise vol.Invalid("Value must be a string")
    if len(value) > MAX_TEXT_LENGTH:
        raise vol.Invalid(f"Value must contain at most {MAX_TEXT_LENGTH} characters")
    if value and not value.isprintable():
        raise vol.Invalid("Value must not contain control characters")
    return value


SENSITIVE_TEXT_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("password"): _validate_sensitive_text,
    },
    extra=vol.PREVENT_EXTRA,
)


class SamsungSensitiveTextView(HomeAssistantView):
    """Accept one transient complete-value snapshot from the first-party card."""

    url = SENSITIVE_TEXT_API_URL
    name = f"api:{DOMAIN}:sensitive_text"
    requires_auth = True

    def _response(
        self,
        result: dict[str, object],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> web.Response:
        """Return a response that browsers and intermediaries must not cache."""
        return self.json(result, status, headers=NO_STORE_HEADERS)

    async def post(self, request: web.Request) -> web.Response:
        """Send text without service events, traces, state, or response echoes."""
        content_length = request.content_length
        if content_length is None or content_length > MAX_REQUEST_BYTES:
            return self._response(
                {"success": False, "error": "Invalid request"},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        try:
            data = SENSITIVE_TEXT_SCHEMA(await request.json())
        except TypeError, ValueError, vol.Invalid:
            return self._response(
                {"success": False, "error": "Invalid request"},
                HTTPStatus.BAD_REQUEST,
            )

        hass: HomeAssistant = request.app[KEY_HASS]
        user = request[KEY_HASS_USER]
        entity_id = data["entity_id"]
        if user is None or not user.permissions.check_entity(entity_id, POLICY_CONTROL):
            return self._response(
                {"success": False, "error": "Forbidden"},
                HTTPStatus.FORBIDDEN,
            )

        entity_entry = er.async_get(hass).async_get(entity_id)
        if (
            entity_entry is None
            or entity_entry.platform != DOMAIN
            or entity_entry.config_entry_id is None
        ):
            return self._response(
                {"success": False, "error": "Entity not found"},
                HTTPStatus.NOT_FOUND,
            )

        config_entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
        if config_entry is None or config_entry.domain != DOMAIN:
            return self._response(
                {"success": False, "error": "Entity not found"},
                HTTPStatus.NOT_FOUND,
            )

        text_client = config_entry.runtime_data.text_client
        if text_client is None:
            return self._response(
                {"success": False, "error": "Text input is unavailable"},
                HTTPStatus.CONFLICT,
            )

        try:
            await text_client.async_send_text(data["password"], submit=False)
        except SamsungTextInputAuthError, SamsungTextInputCertificateError:
            return self._response(
                {"success": False, "error": "Text input is unavailable"},
                HTTPStatus.CONFLICT,
            )
        except SamsungTextInputError:
            return self._response(
                {"success": False, "error": "Text synchronization failed"},
                HTTPStatus.BAD_GATEWAY,
            )

        return self._response({"success": True})


@callback
def async_register_sensitive_text_view(hass: HomeAssistant) -> None:
    """Register the integration-level transient text endpoint once."""
    hass.http.register_view(SamsungSensitiveTextView())
