"""Config flow for Samsung TV IP Control."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, override

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .client import (
    SamsungIPControlAuthError,
    SamsungIPControlCertificateError,
    SamsungIPControlClient,
    SamsungIPControlError,
    SamsungIPControlTransportError,
    normalize_mac,
)
from .const import (
    CONF_CERTIFICATE_FINGERPRINT,
    CONF_ENTITY_IDENTITY,
    CONF_SERIAL_HASH,
    CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT,
    CONF_TEXT_INPUT_ENABLED,
    CONF_TEXT_INPUT_PORT,
    CONF_TEXT_INPUT_TOKEN,
    CONF_TOKEN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from .text_client import (
    DEFAULT_TEXT_INPUT_PORT,
    SamsungTextInputCertificateError,
    SamsungTextInputClient,
    SamsungTextInputError,
    SamsungTextInputTransportError,
)

_LOGGER = logging.getLogger(__name__)


def _log_pairing_failure(step: str, ex: SamsungIPControlError) -> None:
    """Log the exception class, code, and message, never the TV's own text.

    "Pairing failed" alone does not distinguish a genuine on-TV decline from a
    later authenticated call rejecting the TV's response shape, so this is the
    only way to tell those apart. `SamsungIPControlProtocolError` messages are
    always a fixed string the client itself composed (e.g. naming the request
    method), never text copied from the TV's response, so logging `str(ex)`
    here does not violate that redaction boundary.
    """
    code = getattr(ex, "code", None)
    _LOGGER.warning(
        "Samsung TV IP Control %s failed: %s (code=%s): %s",
        step,
        type(ex).__name__,
        code,
        ex,
    )


def _serial_hash(serial: str) -> str:
    """Return a stable, non-plaintext identity derived from the TV serial."""
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


class SamsungIPControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Pair a Samsung TV over local IP Control."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SamsungIPControlOptionsFlow:
        """Create the optional-feature flow."""
        return SamsungIPControlOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect connection data and pair with the TV."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            mac_value = user_input.get(CONF_MAC, "").strip()
            if not host:
                errors[CONF_HOST] = "invalid_host"
            else:
                try:
                    mac = normalize_mac(mac_value) if mac_value else ""
                except ValueError:
                    errors[CONF_MAC] = "invalid_mac"
                    mac = ""
            if not errors:
                client = SamsungIPControlClient(
                    self.hass,
                    host,
                    port=user_input[CONF_PORT],
                    mac=mac or None,
                )
                try:
                    fingerprint = await client.async_trust_current_certificate()
                    token = await client.async_pair()
                    await client.async_get_power()
                    device_information = await client.async_get_device_information()
                except SamsungIPControlCertificateError:
                    errors["base"] = "certificate_mismatch"
                except SamsungIPControlTransportError:
                    errors["base"] = "cannot_connect"
                except SamsungIPControlError as ex:
                    _log_pairing_failure("initial pairing", ex)
                    errors["base"] = "pairing_failed"
                else:
                    serial = device_information["serial"]
                    if not serial:
                        errors["base"] = "missing_unique_id"
                    else:
                        serial_hash = _serial_hash(serial)
                        await self.async_set_unique_id(serial)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=user_input[CONF_NAME],
                            data={
                                CONF_NAME: user_input[CONF_NAME],
                                CONF_HOST: host,
                                CONF_PORT: user_input[CONF_PORT],
                                CONF_MAC: mac,
                                CONF_CERTIFICATE_FINGERPRINT: fingerprint,
                                CONF_ENTITY_IDENTITY: serial_hash,
                                CONF_SERIAL_HASH: serial_hash,
                                CONF_TOKEN: token,
                            },
                        )

        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
                ): cv.string,
                vol.Required(
                    CONF_HOST,
                    default=defaults.get(CONF_HOST, ""),
                ): cv.string,
                vol.Required(
                    CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(
                    CONF_MAC,
                    default=defaults.get(CONF_MAC, ""),
                ): cv.string,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "pairing_instructions": (
                    "Turn the TV on, close Samsung Home so an HDMI picture is "
                    "visible, then submit and accept the prompt on the TV."
                )
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start access-token renewal."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pair again and replace only the rejected token."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            client = SamsungIPControlClient(
                self.hass,
                entry.data[CONF_HOST],
                port=entry.data[CONF_PORT],
                mac=entry.data.get(CONF_MAC) or None,
                certificate_fingerprint=entry.data.get(CONF_CERTIFICATE_FINGERPRINT),
            )
            try:
                if not client.certificate_fingerprint:
                    await client.async_trust_current_certificate()
                token = await client.async_pair()
                await client.async_get_power()
                device_information = await client.async_get_device_information()
            except SamsungIPControlCertificateError:
                errors["base"] = "certificate_mismatch"
            except SamsungIPControlTransportError:
                errors["base"] = "cannot_connect"
            except SamsungIPControlError as ex:
                _log_pairing_failure("reauthentication", ex)
                errors["base"] = "pairing_failed"
            else:
                fingerprint = client.certificate_fingerprint
                serial = device_information["serial"]
                if fingerprint is None:
                    errors["base"] = "pairing_failed"
                elif not serial:
                    errors["base"] = "missing_unique_id"
                else:
                    await self.async_set_unique_id(serial)
                    identity_updates = self._verified_identity_updates(entry, serial)
                    if identity_updates is None:
                        errors["base"] = "device_mismatch"
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            unique_id=serial,
                            data_updates={
                                CONF_TOKEN: token,
                                CONF_CERTIFICATE_FINGERPRINT: fingerprint,
                                **identity_updates,
                            },
                        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "pairing_instructions": (
                    "Turn the TV on, close Samsung Home so an HDMI picture is "
                    "visible, then submit and accept the prompt on the TV."
                )
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update connection details after verifying the same physical TV."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            mac_value = user_input.get(CONF_MAC, "").strip()
            if not host:
                errors[CONF_HOST] = "invalid_host"
            else:
                try:
                    mac = normalize_mac(mac_value) if mac_value else ""
                except ValueError:
                    errors[CONF_MAC] = "invalid_mac"
                    mac = ""

            if not errors:
                client = SamsungIPControlClient(
                    self.hass,
                    host,
                    port=user_input[CONF_PORT],
                    token=entry.data[CONF_TOKEN],
                    mac=mac or None,
                    certificate_fingerprint=entry.data[CONF_CERTIFICATE_FINGERPRINT],
                )
                try:
                    await client.async_get_power()
                    device_information = await client.async_get_device_information()
                except SamsungIPControlCertificateError:
                    errors["base"] = "certificate_mismatch"
                except SamsungIPControlAuthError:
                    errors["base"] = "authentication_failed"
                except SamsungIPControlTransportError:
                    errors["base"] = "cannot_connect"
                except SamsungIPControlError as ex:
                    _log_pairing_failure("reconfiguration", ex)
                    errors["base"] = "pairing_failed"
                else:
                    serial = device_information["serial"]
                    if not serial:
                        errors["base"] = "missing_unique_id"
                    else:
                        await self.async_set_unique_id(serial)
                        identity_updates = self._verified_identity_updates(
                            entry, serial
                        )
                        if identity_updates is None:
                            errors["base"] = "device_mismatch"
                        else:
                            return self.async_update_reload_and_abort(
                                entry,
                                unique_id=serial,
                                data_updates={
                                    CONF_HOST: host,
                                    CONF_PORT: user_input[CONF_PORT],
                                    CONF_MAC: mac,
                                    **identity_updates,
                                },
                            )

        defaults = user_input or entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=defaults.get(CONF_HOST, ""),
                ): cv.string,
                vol.Required(
                    CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(
                    CONF_MAC,
                    default=defaults.get(CONF_MAC, ""),
                ): cv.string,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )

    def _verified_identity_updates(
        self, entry: config_entries.ConfigEntry, serial: str
    ) -> dict[str, str] | None:
        """Validate identity and return privacy-preserving migration data."""
        serial_hash = _serial_hash(serial)
        existing_serial_hash = entry.data.get(CONF_SERIAL_HASH)
        if existing_serial_hash and not hmac.compare_digest(
            existing_serial_hash, serial_hash
        ):
            return None

        legacy_unique_ids = {
            None,
            serial,
            entry.data[CONF_HOST].casefold(),
            entry.data.get(CONF_MAC) or None,
        }
        if entry.unique_id not in legacy_unique_ids:
            return None
        if any(
            candidate.entry_id != entry.entry_id and candidate.unique_id == serial
            for candidate in self.hass.config_entries.async_entries(DOMAIN)
        ):
            return None

        entity_identity = entry.data.get(CONF_ENTITY_IDENTITY)
        if not entity_identity:
            entity_identity = (
                entry.data.get(CONF_MAC) or entry.data[CONF_HOST].casefold()
            )
        return {
            CONF_ENTITY_IDENTITY: entity_identity,
            CONF_SERIAL_HASH: serial_hash,
        }


class SamsungIPControlOptionsFlow(OptionsFlowWithReload):
    """Configure independently paired optional local features."""

    _pending_text_port: int | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable, disable, or re-pair local WebSocket text input."""
        current = self.config_entry.options
        if self._pending_text_port is None:
            self._pending_text_port = current.get(
                CONF_TEXT_INPUT_PORT,
                DEFAULT_TEXT_INPUT_PORT,
            )
        has_pairing = bool(
            current.get(CONF_TEXT_INPUT_TOKEN)
            and current.get(CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT)
        )

        if user_input is not None:
            enabled = user_input[CONF_TEXT_INPUT_ENABLED]
            port = user_input[CONF_TEXT_INPUT_PORT]
            pair_again = user_input.get("pair_text_input_again", False)
            if not enabled:
                data = {
                    key: value
                    for key, value in current.items()
                    if key
                    not in {
                        CONF_TEXT_INPUT_TOKEN,
                        CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT,
                    }
                }
                data.update(
                    {
                        CONF_TEXT_INPUT_ENABLED: False,
                        CONF_TEXT_INPUT_PORT: port,
                    }
                )
                return self.async_create_entry(title="", data=data)

            if (
                has_pairing
                and not pair_again
                and port == current.get(CONF_TEXT_INPUT_PORT, DEFAULT_TEXT_INPUT_PORT)
            ):
                data = dict(current)
                data.update(
                    {
                        CONF_TEXT_INPUT_ENABLED: True,
                        CONF_TEXT_INPUT_PORT: port,
                    }
                )
                return self.async_create_entry(title="", data=data)

            self._pending_text_port = port
            return await self.async_step_text_pair()

        schema_fields: dict[vol.Marker, Any] = {
            vol.Required(
                CONF_TEXT_INPUT_ENABLED,
                default=current.get(CONF_TEXT_INPUT_ENABLED, False),
            ): cv.boolean,
            vol.Required(
                CONF_TEXT_INPUT_PORT,
                default=current.get(
                    CONF_TEXT_INPUT_PORT,
                    DEFAULT_TEXT_INPUT_PORT,
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        }
        if has_pairing:
            schema_fields[vol.Optional("pair_text_input_again", default=False)] = (
                cv.boolean
            )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_fields),
        )

    async def async_step_text_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trust the text-input certificate and request its separate token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SamsungTextInputClient(
                self.hass,
                self.config_entry.data[CONF_HOST],
                port=self._pending_text_port or DEFAULT_TEXT_INPUT_PORT,
            )
            try:
                fingerprint = await client.async_trust_current_certificate()
                token = await client.async_pair()
            except SamsungTextInputCertificateError:
                errors["base"] = "text_certificate_mismatch"
            except SamsungTextInputTransportError:
                errors["base"] = "text_cannot_connect"
            except SamsungTextInputError:
                errors["base"] = "text_pairing_failed"
            else:
                data = dict(self.config_entry.options)
                data.update(
                    {
                        CONF_TEXT_INPUT_ENABLED: True,
                        CONF_TEXT_INPUT_PORT: (
                            self._pending_text_port or DEFAULT_TEXT_INPUT_PORT
                        ),
                        CONF_TEXT_INPUT_TOKEN: token,
                        CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT: fingerprint,
                    }
                )
                return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="text_pair",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "pairing_instructions": (
                    "Turn the TV on, submit this step, and accept the separate "
                    "local remote authorization prompt on the TV."
                )
            },
        )
