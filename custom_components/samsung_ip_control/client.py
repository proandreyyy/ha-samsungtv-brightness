"""Local Samsung TV JSON-RPC client for HTTPS port 1516."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import http.client
import json
import logging
import socket
import ssl
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from .const import (
    API_TO_SOURCE,
    APP_ALIASES,
    APP_TO_API,
    BACKLIGHT_MAX,
    BACKLIGHT_MIN,
    BACKLIGHT_STEP,
    DEFAULT_PORT,
    REMOTE_KEY_TO_API,
    SOURCE_TO_API,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"
COMMAND_TIMEOUT = 6
PAIR_TIMEOUT = 40
MAX_RESPONSE_BYTES = 64 * 1024
ERROR_UNAUTHORIZED = -32010
ERROR_STALE_TOKEN = -32700
# Samsung answers -32002 when a request cannot be applied in the TV's current
# state. A standby set returns it for powerOn while still acting on the request.
ERROR_NOT_APPLICABLE = -32002


class SamsungIPControlError(Exception):
    """Base error for Samsung IP Control."""


class SamsungIPControlAuthError(SamsungIPControlError):
    """The TV rejected the access token."""


class SamsungIPControlTransportError(SamsungIPControlError):
    """The TV could not be reached."""


class SamsungIPControlProtocolError(SamsungIPControlError):
    """The TV returned an invalid or unsuccessful response."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class SamsungIPControlCertificateError(SamsungIPControlError):
    """The TV's TLS certificate does not match the pinned certificate."""


def normalize_mac(value: str) -> str:
    """Return a normalized MAC address or raise ValueError."""
    compact = "".join(character for character in value if character.isalnum())
    if len(compact) != 12 or any(
        character not in "0123456789abcdefABCDEF" for character in compact
    ):
        raise ValueError("Invalid MAC address")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2)).upper()


def source_from_api(value: Any) -> str | None:
    """Convert Samsung's source value to a Home Assistant display value."""
    if not isinstance(value, str):
        return None
    compact = value.replace(" ", "").upper()
    return API_TO_SOURCE.get(compact)


def mute_from_api(value: Any) -> bool | None:
    """Convert Samsung's mute value to a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.casefold()
        if normalized in ("muteon", "on", "true", "1"):
            return True
        if normalized in ("muteoff", "off", "false", "0"):
            return False
    return None


class SamsungIPControlClient:
    """Async wrapper around Samsung's local HTTPS JSON-RPC endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        *,
        port: int = DEFAULT_PORT,
        token: str | None = None,
        mac: str | None = None,
        certificate_fingerprint: str | None = None,
    ) -> None:
        self._hass = hass
        self.host = host
        self.port = port
        self._token = token
        self.mac = normalize_mac(mac) if mac else None
        self._certificate_fingerprint = (
            self._normalize_certificate_fingerprint(certificate_fingerprint)
            if certificate_fingerprint
            else None
        )
        self._lock = asyncio.Lock()
        self._ssl_context: ssl.SSLContext | None = None
        self._request_id = 0
        self._mute_state: bool | None = None
        self._pending_backlight: int | None = None
        self._backlight_writer: asyncio.Task[None] | None = None

    @property
    def certificate_fingerprint(self) -> str | None:
        """Return the trusted SHA-256 TLS certificate fingerprint."""
        return self._certificate_fingerprint

    async def async_trust_current_certificate(self) -> str:
        """Trust the current TV certificate before any token is transmitted."""
        async with self._lock:
            fingerprint = await self._hass.async_add_executor_job(
                self._sync_get_certificate_fingerprint
            )
            self._certificate_fingerprint = fingerprint
            return fingerprint

    async def async_pair(self) -> str:
        """Ask the TV for a persistent access token."""
        result = await self._async_request(
            "createAccessToken", include_token=False, timeout=PAIR_TIMEOUT
        )
        token = result.get("AccessToken")
        if not isinstance(token, str) or not token:
            raise SamsungIPControlProtocolError(
                "The TV did not return an access token. Close Samsung Home, "
                "show an HDMI input, and retry."
            )
        self._token = token
        return token

    async def async_get_power(self) -> bool:
        """Return the TV's explicit hardware power state."""
        result = await self._async_request("powerControl")
        state = result.get("power")
        if state not in ("powerOn", "powerOff"):
            raise SamsungIPControlProtocolError(
                "The TV returned an unknown power state"
            )
        return state == "powerOn"

    async def async_power_on(self) -> None:
        """Request power-on without blocking while the panel wakes.

        The IP write has to be attempted first. Wake-on-LAN alone does not wake
        the tested set, so treating a configured MAC as a shortcut past
        powerControl left the TV off. Wake-on-LAN stays a fallback for the two
        ways a standby set refuses the write.
        """
        try:
            await self._async_request("powerControl", {"power": "powerOn"})
        except SamsungIPControlTransportError:
            if not self.mac:
                raise
            await self.async_wake_on_lan()
        except SamsungIPControlProtocolError as ex:
            if ex.code != ERROR_NOT_APPLICABLE:
                raise
            if self.mac:
                await self.async_wake_on_lan()

    async def async_power_off(self) -> None:
        """Turn the TV fully off."""
        await self._async_request("powerControl", {"power": "powerOff"})

    async def async_get_states(self) -> dict[str, Any]:
        """Return the local TV state snapshot."""
        states = await self._async_request("getTVStates")
        muted = mute_from_api(states.get("mute"))
        if muted is not None:
            self._mute_state = muted
        return states

    async def async_get_device_information(self) -> dict[str, str]:
        """Return non-secret device identification."""
        result = await self._async_request("getDeviceInformation")

        def string_value(key: str) -> str:
            value = result.get(key)
            return value.strip() if isinstance(value, str) else ""

        return {
            "model": string_value("modelID"),
            "firmware": string_value("FWVersion"),
            "serial": string_value("serialNumber"),
        }

    async def async_volume_up(self) -> None:
        """Increase the TV volume by one step."""
        await self._async_request("volumeUpDnControl", {"control": "volumeUp"})

    async def async_volume_down(self) -> None:
        """Decrease the TV volume by one step."""
        await self._async_request("volumeUpDnControl", {"control": "volumeDn"})

    async def async_channel_up(self) -> None:
        """Select the next TV channel."""
        await self._async_request("channelUpDnControl", {"control": "channelUp"})

    async def async_channel_down(self) -> None:
        """Select the previous TV channel."""
        await self._async_request("channelUpDnControl", {"control": "channelDn"})

    async def async_get_mute(self) -> bool:
        """Return the authoritative local mute state."""
        result = await self._async_request("muteControl")
        value = result.get("mute")
        if value not in ("muteOn", "muteOff"):
            raise SamsungIPControlProtocolError("The TV returned an unknown mute state")
        self._mute_state = value == "muteOn"
        return self._mute_state

    async def async_set_mute(self, muted: bool) -> None:
        """Set mute to an explicit state."""
        await self._async_request(
            "muteControl", {"mute": "muteOn" if muted else "muteOff"}
        )
        self._mute_state = muted

    async def async_toggle_mute(self) -> None:
        """Toggle mute using a fresh local state read."""
        current = (
            self._mute_state
            if self._mute_state is not None
            else await self.async_get_mute()
        )
        await self.async_set_mute(not current)

    async def async_get_backlight(self) -> int:
        """Return the TV's current backlight level, 0-50."""
        result = await self._async_request("backlightControl")
        value = result.get("backlight")
        if not isinstance(value, int) or not BACKLIGHT_MIN <= value <= BACKLIGHT_MAX:
            raise SamsungIPControlProtocolError(
                "The TV returned an unknown backlight value"
            )
        return value

    async def async_set_backlight(self, value: int) -> None:
        """Set an explicit backlight level, 0-50, then confirm it.

        Writes directly with no preceding power check; an unrelated
        `powerControl` read immediately before the write was tried and
        removed, since it added latency for no observed benefit. The write
        alone can sit accepted but visibly unapplied on the panel for a long
        time (in practice, until whatever the next unrelated request to the
        TV happens to be); a brief pause followed by a plain read of this
        same method is what a sibling project (`tvolve`) already does after
        every write, and empirically is what makes the physical picture
        react immediately instead of waiting on some later, unrelated
        request to nudge it. The read's own result is not used for
        anything; only its side effect on the TV matters here, so its
        failure is not treated as the write itself having failed.
        """
        if not isinstance(value, int) or not BACKLIGHT_MIN <= value <= BACKLIGHT_MAX:
            raise ValueError(
                f"Backlight must be between {BACKLIGHT_MIN} and {BACKLIGHT_MAX}"
            )
        await self._async_request("backlightControl", {"backlight": value})
        await asyncio.sleep(0.15)
        with suppress(SamsungIPControlError):
            await self.async_get_backlight()

    async def async_step_backlight(self, delta: int) -> int:
        """Adjust the backlight by delta, clamped to the native range.

        Reads before writing rather than trusting a locally cached value,
        because unlike mute there is no cheap way to keep backlight current
        between polls without a per-command round trip.
        """
        current = await self.async_get_backlight()
        target = max(BACKLIGHT_MIN, min(BACKLIGHT_MAX, current + delta))
        if target != current:
            await self.async_set_backlight(target)
        return target

    def async_queue_backlight(self, value: int) -> None:
        """Coalesce rapid backlight writes, keeping only the latest target.

        A fast slider drag (e.g. from a HomeKit accessory) can fire dozens of
        writes in a few seconds. Each write needs its own TLS handshake (no
        connection is kept open between requests), so working through every
        intermediate value strictly in the order it arrived left a full-range
        drag looking stuck near wherever it started for several seconds.
        Only the most recent target is kept; a write already in flight
        finishes normally, then immediately picks up whatever the latest
        target has since become, the same coalescing scheme the sibling
        `tvolve` project already uses for its own slider.
        """
        if not isinstance(value, int) or not BACKLIGHT_MIN <= value <= BACKLIGHT_MAX:
            raise ValueError(
                f"Backlight must be between {BACKLIGHT_MIN} and {BACKLIGHT_MAX}"
            )
        self._pending_backlight = value
        if self._backlight_writer is None or self._backlight_writer.done():
            self._backlight_writer = self._create_task(
                self._async_drain_backlight(), "Samsung TV backlight writer"
            )

    async def _async_drain_backlight(self) -> None:
        """Write the latest queued backlight target until none remains."""
        while self._pending_backlight is not None:
            target = self._pending_backlight
            self._pending_backlight = None
            try:
                await self.async_set_backlight(target)
            except SamsungIPControlError as ex:
                _LOGGER.warning(
                    "Samsung TV IP Control queued backlight write failed: "
                    "%s (code=%s): %s",
                    type(ex).__name__,
                    getattr(ex, "code", None),
                    ex,
                )
            except Exception:
                _LOGGER.exception(
                    "Samsung TV IP Control backlight write raised an "
                    "unexpected exception"
                )

    def _create_task(self, coroutine: Any, name: str) -> asyncio.Task[None]:
        """Create a Home Assistant tracked task, with a small test fallback."""
        create_task = getattr(self._hass, "async_create_task", None)
        if callable(create_task):
            return create_task(coroutine, name)
        return asyncio.create_task(coroutine, name=name)

    async def async_select_source(self, source: str, *, reliable: bool = True) -> None:
        """Select one exact HDMI source, optionally waking and retrying."""
        try:
            api_source = SOURCE_TO_API[source]
        except KeyError as ex:
            raise ValueError(f"Unsupported source: {source}") from ex

        await self._async_ensure_powered_on()

        await self._async_request("inputSourceControl", {"inputSource": api_source})
        if reliable:
            await asyncio.sleep(1)
            await self._async_request("inputSourceControl", {"inputSource": api_source})

    async def async_send_navigation_key(self, command: str) -> None:
        """Send one allowlisted Consumer IP remote key."""
        try:
            api_key = REMOTE_KEY_TO_API[command]
        except KeyError as ex:
            raise ValueError(f"Unsupported navigation command: {command}") from ex
        await self._async_request("remoteKeyControl", {"remoteKey": api_key})

    async def async_launch_app(self, app: str) -> None:
        """Launch one allowlisted Consumer IP direct-access application."""
        normalized = app.strip().lower().replace("-", "_").replace(" ", "_")
        normalized = APP_ALIASES.get(normalized, normalized)
        try:
            api_app = APP_TO_API[normalized]
        except KeyError as ex:
            raise ValueError(f"Unsupported application: {app}") from ex
        await self._async_ensure_powered_on()
        await self._async_request("directAccessControl", {"applicationName": api_app})

    async def _async_ensure_powered_on(self) -> None:
        """Ensure the TV is awake before an input or application command."""
        try:
            power_on = await self.async_get_power()
        except SamsungIPControlTransportError:
            if not self.mac:
                raise
            await self.async_wake_on_lan()
            await asyncio.sleep(4)
        else:
            if not power_on:
                await self.async_power_on()
                await asyncio.sleep(4)

    async def async_run_remote_command(self, command: str) -> int | None:
        """Run one allowlisted local remote command.

        Returns the new backlight level for `brightness_up`/`brightness_down`
        so a caller can publish it without a second read; every other command
        returns `None`, unchanged from before backlight support existed.
        """
        normalized = command.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in REMOTE_KEY_TO_API:
            await self.async_send_navigation_key(normalized)
            return None
        if normalized == "volume_up":
            await self.async_volume_up()
            return None
        if normalized == "volume_down":
            await self.async_volume_down()
            return None
        if normalized == "mute":
            await self.async_toggle_mute()
            return None
        if normalized == "channel_up":
            await self.async_channel_up()
            return None
        if normalized == "channel_down":
            await self.async_channel_down()
            return None
        if normalized.startswith("hdmi_") and normalized[-1:] in "1234":
            await self.async_select_source(f"HDMI {normalized[-1]}")
            return None
        if normalized == "power_on":
            await self.async_power_on()
            return None
        if normalized == "power_off":
            await self.async_power_off()
            return None
        if normalized == "brightness_up":
            return await self.async_step_backlight(BACKLIGHT_STEP)
        if normalized == "brightness_down":
            return await self.async_step_backlight(-BACKLIGHT_STEP)
        if normalized.startswith("app_"):
            await self.async_launch_app(normalized.removeprefix("app_"))
            return None
        raise ValueError(f"Unsupported remote command: {command}")

    async def async_wake_on_lan(self) -> None:
        """Send a local broadcast Wake-on-LAN packet."""
        if not self.mac:
            raise SamsungIPControlTransportError(
                "No MAC address is configured for Wake-on-LAN"
            )
        mac_bytes = bytes.fromhex(self.mac.replace(":", ""))
        packet = b"\xff" * 6 + mac_bytes * 16
        await self._hass.async_add_executor_job(self._sync_send_wol, packet)

    @staticmethod
    def _sync_send_wol(packet: bytes) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as wol_socket:
            wol_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            wol_socket.sendto(packet, ("255.255.255.255", 9))

    async def _async_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        include_token: bool = True,
        timeout: int = COMMAND_TIMEOUT,
    ) -> dict[str, Any]:
        async with self._lock:
            self._request_id += 1
            request_id = self._request_id
            return await self._hass.async_add_executor_job(
                self._sync_request,
                request_id,
                method,
                params,
                include_token,
                timeout,
            )

    def _sync_request(
        self,
        request_id: int,
        method: str,
        params: dict[str, Any] | None,
        include_token: bool,
        timeout: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "jsonrpc": JSONRPC_VERSION,
            # This TV API serializes response identifiers as JSON strings.
            # Sending a string keeps request/response correlation exact.
            "id": str(request_id),
            "method": method,
        }
        if include_token:
            if not self._token:
                raise SamsungIPControlAuthError("Pairing is required")
            if not self._certificate_fingerprint:
                raise SamsungIPControlCertificateError(
                    "A trusted TV certificate is required before using credentials"
                )
            body["params"] = {"AccessToken": self._token, **(params or {})}
        elif params:
            body["params"] = params

        payload = json.dumps(body).encode("utf-8")
        raw = self._sync_post(payload, timeout)
        try:
            response = json.loads(raw)
        except json.JSONDecodeError as ex:
            raise SamsungIPControlProtocolError(
                "The TV returned a non-JSON response"
            ) from ex
        if not isinstance(response, dict):
            raise SamsungIPControlProtocolError("The TV returned an invalid response")
        if response.get("jsonrpc") != JSONRPC_VERSION:
            raise SamsungIPControlProtocolError(
                "The TV returned an invalid JSON-RPC version"
            )
        if response.get("id") != str(request_id):
            raise SamsungIPControlProtocolError(
                "The TV returned a mismatched JSON-RPC response"
            )

        error = response.get("error")
        if error is None and "code" in response and "result" not in response:
            error = {
                "code": response.get("code"),
                "message": response.get("message"),
            }
        if error is not None:
            code = error.get("code") if isinstance(error, dict) else None
            if code == ERROR_UNAUTHORIZED or (
                code == ERROR_STALE_TOKEN and include_token
            ):
                raise SamsungIPControlAuthError(
                    f"The TV rejected pairing credentials, code {code}"
                )
            raise SamsungIPControlProtocolError(
                f"The TV rejected {method}, code {code}",
                code=code if isinstance(code, int) else None,
            )

        result = response.get("result")
        return result if isinstance(result, dict) else {}

    def _sync_post(self, payload: bytes, timeout: int) -> str:
        connection = http.client.HTTPSConnection(
            self.host, self.port, timeout=timeout, context=self._get_ssl_context()
        )
        try:
            connection.connect()
            self._validate_peer_certificate(self._peer_certificate(connection))
            connection.putrequest("POST", "/", skip_accept_encoding=True)
            connection.putheader("Accept", "application/json")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(len(payload)))
            connection.endheaders()
            connection.send(payload)
            response = connection.getresponse()
            if response.status < 200 or response.status >= 300:
                raise SamsungIPControlProtocolError(
                    f"The TV returned HTTP status {response.status}"
                )
            content_length = response.getheader("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as ex:
                    raise SamsungIPControlProtocolError(
                        "The TV returned an invalid Content-Length"
                    ) from ex
                if declared_length < 0 or declared_length > MAX_RESPONSE_BYTES:
                    raise SamsungIPControlProtocolError(
                        "The TV response exceeded the size limit"
                    )
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SamsungIPControlProtocolError(
                    "The TV response exceeded the size limit"
                )
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as ex:
                raise SamsungIPControlProtocolError(
                    "The TV returned a non-UTF-8 response"
                ) from ex
        except (TimeoutError, OSError, http.client.HTTPException) as ex:
            raise SamsungIPControlTransportError("Could not reach the TV") from ex
        finally:
            connection.close()

    def _sync_get_certificate_fingerprint(self) -> str:
        connection = http.client.HTTPSConnection(
            self.host,
            self.port,
            timeout=COMMAND_TIMEOUT,
            context=self._get_ssl_context(),
        )
        try:
            connection.connect()
            return self._fingerprint(self._peer_certificate(connection))
        except (TimeoutError, OSError, http.client.HTTPException) as ex:
            raise SamsungIPControlTransportError("Could not reach the TV") from ex
        finally:
            connection.close()

    def _get_ssl_context(self) -> ssl.SSLContext:
        if self._ssl_context is None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self._ssl_context = context
        return self._ssl_context

    @staticmethod
    def _peer_certificate(connection: http.client.HTTPSConnection) -> bytes:
        if connection.sock is None:
            raise SamsungIPControlProtocolError(
                "The TV did not establish a TLS connection"
            )
        certificate = connection.sock.getpeercert(binary_form=True)
        if not certificate:
            raise SamsungIPControlProtocolError(
                "The TV did not provide a TLS certificate"
            )
        return certificate

    @staticmethod
    def _fingerprint(certificate: bytes) -> str:
        return hashlib.sha256(certificate).hexdigest().upper()

    @staticmethod
    def _normalize_certificate_fingerprint(value: str) -> str:
        normalized = value.replace(":", "").strip().upper()
        if len(normalized) != 64 or any(
            character not in "0123456789ABCDEF" for character in normalized
        ):
            raise ValueError("Invalid SHA-256 certificate fingerprint")
        return normalized

    def _validate_peer_certificate(self, certificate: bytes) -> None:
        actual = self._fingerprint(certificate)
        expected = self._certificate_fingerprint
        if expected is not None and not hmac.compare_digest(actual, expected):
            raise SamsungIPControlCertificateError(
                "The TV TLS certificate changed; credentials were not transmitted"
            )
