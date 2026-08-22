"""Optional local Samsung WebSocket client for on-screen text input."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import socket
import ssl
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError, Fingerprint, ServerFingerprintMismatch, WSMsgType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

if TYPE_CHECKING:
    from aiohttp import ClientWebSocketResponse
    from homeassistant.core import HomeAssistant

DEFAULT_TEXT_INPUT_PORT = 8002
TEXT_CONNECT_TIMEOUT = 40
TEXT_COMMAND_TIMEOUT = 10
TEXT_SESSION_IDLE_TIMEOUT = 30
MAX_TEXT_LENGTH = 200
MAX_RESPONSE_BYTES = 64 * 1024
MAX_STARTUP_MESSAGES = 20
CLIENT_NAME = "Home Assistant Samsung IP Control"

EVENT_CONNECT = "ms.channel.connect"
EVENT_UNAUTHORIZED = "ms.channel.unauthorized"
EVENT_ERROR = "ms.error"
EVENT_IME_START = "ms.remote.imeStart"
EVENT_IME_UPDATE = "ms.remote.imeUpdate"
EVENT_IME_END = "ms.remote.imeEnd"


class SamsungTextInputError(Exception):
    """Base error for optional Samsung text input."""


class SamsungTextInputTransportError(SamsungTextInputError):
    """The TV text-input endpoint could not be reached."""


class SamsungTextInputAuthError(SamsungTextInputError):
    """The TV rejected the WebSocket remote token."""


class SamsungTextInputCertificateError(SamsungTextInputError):
    """The TV WebSocket certificate does not match the trusted certificate."""


class SamsungTextInputProtocolError(SamsungTextInputError):
    """The TV returned an invalid WebSocket response."""


class SamsungTextInputClient:
    """Pair with and send text through Samsung's local WebSocket IME service."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        *,
        port: int = DEFAULT_TEXT_INPUT_PORT,
        token: str | None = None,
        certificate_fingerprint: str | None = None,
    ) -> None:
        self._hass = hass
        self.host = host
        self.port = port
        self._token = token
        self._certificate_fingerprint = (
            self._normalize_fingerprint(certificate_fingerprint)
            if certificate_fingerprint
            else None
        )
        self._websocket: ClientWebSocketResponse | None = None
        self._session_lock = asyncio.Lock()
        self._reader_task: asyncio.Task[None] | None = None
        self._idle_task: asyncio.Task[None] | None = None
        self._ime_active = False

    @property
    def certificate_fingerprint(self) -> str | None:
        """Return the trusted WebSocket certificate fingerprint."""
        return self._certificate_fingerprint

    async def async_trust_current_certificate(self) -> str:
        """Pin the TV's current WebSocket TLS certificate before pairing."""
        try:
            fingerprint = await self._hass.async_add_executor_job(
                self._sync_get_certificate_fingerprint
            )
        except OSError, ssl.SSLError:
            raise SamsungTextInputTransportError(
                "Could not reach the TV text-input endpoint"
            ) from None
        self._certificate_fingerprint = fingerprint
        return fingerprint

    async def async_pair(self) -> str:
        """Request a local WebSocket remote token from the physical TV."""
        websocket, response = await self._async_open(
            token=None,
            timeout=TEXT_CONNECT_TIMEOUT,
        )
        try:
            token = response.get("data", {}).get("token")
            if not isinstance(token, str) or not token or len(token) > 1024:
                raise SamsungTextInputProtocolError(
                    "The TV did not return a valid text-input token"
                )
            self._token = token
            return token
        finally:
            await websocket.close()

    async def async_send_text(self, text: str, *, submit: bool = False) -> None:
        """Set one complete text snapshot in the active TV input field."""
        if not self._token:
            raise SamsungTextInputAuthError("Text input is not paired")
        if not isinstance(text, str) or not 0 <= len(text) <= MAX_TEXT_LENGTH:
            raise ValueError(f"Text must contain 0 to {MAX_TEXT_LENGTH} characters")
        if text and not text.isprintable():
            raise ValueError("Text must not contain control characters")

        async with self._session_lock:
            websocket = await self._async_get_session()
            try:
                async with asyncio.timeout(TEXT_COMMAND_TIMEOUT):
                    await self._async_send_input_string(websocket, text)
                    if submit:
                        await websocket.send_json(
                            {
                                "method": "ms.remote.control",
                                "params": {"TypeOfRemote": "SendInputEnd"},
                            }
                        )
            except ClientError, TimeoutError:
                await self._async_close_session_locked()
                raise SamsungTextInputTransportError(
                    "The TV text-input connection closed during the command"
                ) from None
            self._schedule_idle_close_locked()

    @staticmethod
    async def _async_send_input_string(
        websocket: ClientWebSocketResponse, text: str
    ) -> None:
        """Send one complete field snapshot, including an empty value."""
        await websocket.send_json(
            {
                "method": "ms.remote.control",
                "params": {
                    "Cmd": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                    "DataOfCmd": "base64",
                    "TypeOfRemote": "SendInputString",
                },
            }
        )

    async def async_close(self) -> None:
        """Close the short-lived Samsung text-input session."""
        async with self._session_lock:
            await self._async_close_session_locked()

    async def _async_get_session(self) -> ClientWebSocketResponse:
        """Return one authenticated session shared by consecutive updates."""
        websocket = self._websocket
        if websocket is not None and not websocket.closed:
            return websocket

        websocket, _ = await self._async_open(
            token=self._token,
            timeout=TEXT_COMMAND_TIMEOUT,
        )
        self._websocket = websocket
        self._reader_task = self._create_task(
            self._async_receive_events(websocket),
            "Samsung TV text-input events",
        )
        return websocket

    async def _async_receive_events(self, websocket: ClientWebSocketResponse) -> None:
        """Consume bounded IME lifecycle events without retaining TV text."""
        try:
            while not websocket.closed:
                message = await websocket.receive()
                if message.type == WSMsgType.TEXT:
                    response = self._parse_response(message.data)
                    event = response.get("event")
                    if event == EVENT_IME_START:
                        self._ime_active = True
                    elif event == EVENT_IME_END:
                        self._ime_active = False
                    elif event == EVENT_IME_UPDATE:
                        # TV text can be sensitive. Never retain or expose the payload.
                        continue
                    elif event in (EVENT_UNAUTHORIZED, EVENT_ERROR):
                        break
                    continue
                if message.type in (
                    WSMsgType.CLOSE,
                    WSMsgType.CLOSED,
                    WSMsgType.ERROR,
                ):
                    break
        except ClientError, SamsungTextInputProtocolError:
            pass
        finally:
            if self._websocket is websocket:
                self._websocket = None
                self._ime_active = False
            with suppress(ClientError, TimeoutError):
                await websocket.close()

    def _schedule_idle_close_locked(self) -> None:
        """Close an inactive text session so the TV connection is not permanent."""
        if self._idle_task is not None:
            self._idle_task.cancel()
        self._idle_task = self._create_task(
            self._async_close_after_idle(),
            "Samsung TV text-input idle close",
        )

    async def _async_close_after_idle(self) -> None:
        """Close the shared text channel after its bounded idle window."""
        try:
            await asyncio.sleep(TEXT_SESSION_IDLE_TIMEOUT)
            await self.async_close()
        except asyncio.CancelledError:
            pass

    async def _async_close_session_locked(self) -> None:
        """Close and forget the active session while holding the session lock."""
        current_task = asyncio.current_task()
        idle_task = self._idle_task
        self._idle_task = None
        if idle_task is not None and idle_task is not current_task:
            idle_task.cancel()

        reader_task = self._reader_task
        self._reader_task = None
        websocket = self._websocket
        self._websocket = None
        self._ime_active = False
        if websocket is not None:
            with suppress(ClientError, TimeoutError):
                await websocket.close()
        if reader_task is not None and reader_task is not current_task:
            reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await reader_task

    def _create_task(self, coroutine: Any, name: str) -> asyncio.Task[None]:
        """Create a Home Assistant tracked task, with a small test fallback."""
        create_task = getattr(self._hass, "async_create_task", None)
        if callable(create_task):
            return create_task(coroutine, name)
        return asyncio.create_task(coroutine, name=name)

    async def _async_open(
        self, *, token: str | None, timeout: int
    ) -> tuple[ClientWebSocketResponse, dict[str, Any]]:
        """Open an authenticated, certificate-pinned WebSocket connection."""
        fingerprint = self._certificate_fingerprint
        if not fingerprint:
            raise SamsungTextInputCertificateError(
                "The TV text-input certificate has not been trusted"
            )

        query = {"name": base64.b64encode(CLIENT_NAME.encode("utf-8")).decode("ascii")}
        if token:
            query["token"] = token
        url = URL.build(
            scheme="wss",
            host=self.host,
            port=self.port,
            path="/api/v2/channels/samsung.remote.control",
            query=query,
        )
        session = async_get_clientsession(self._hass)
        websocket: ClientWebSocketResponse | None = None
        try:
            async with asyncio.timeout(timeout):
                websocket = await session.ws_connect(
                    url,
                    ssl=Fingerprint(bytes.fromhex(fingerprint)),
                    max_msg_size=MAX_RESPONSE_BYTES,
                )
                for _ in range(MAX_STARTUP_MESSAGES):
                    message = await websocket.receive()
                    if message.type == WSMsgType.TEXT:
                        response = self._parse_response(message.data)
                        event = response.get("event")
                        if event == EVENT_CONNECT:
                            return websocket, response
                        if event == EVENT_UNAUTHORIZED:
                            raise SamsungTextInputAuthError(
                                "The TV rejected the text-input token"
                            )
                        if event == EVENT_ERROR:
                            raise SamsungTextInputProtocolError(
                                "The TV rejected the text-input connection"
                            )
                        continue
                    if message.type in (
                        WSMsgType.CLOSE,
                        WSMsgType.CLOSED,
                        WSMsgType.ERROR,
                    ):
                        break
        except ServerFingerprintMismatch:
            if websocket is not None:
                with suppress(ClientError, TimeoutError):
                    await websocket.close()
            raise SamsungTextInputCertificateError(
                "The TV text-input certificate changed"
            ) from None
        except TimeoutError:
            if websocket is not None:
                with suppress(ClientError, TimeoutError):
                    await websocket.close()
            raise SamsungTextInputTransportError(
                "The TV text-input connection timed out"
            ) from None
        except ClientError:
            if websocket is not None:
                with suppress(ClientError, TimeoutError):
                    await websocket.close()
            raise SamsungTextInputTransportError(
                "Could not connect to the TV text-input endpoint"
            ) from None
        except SamsungTextInputError:
            if websocket is not None:
                with suppress(ClientError, TimeoutError):
                    await websocket.close()
            raise

        if websocket is not None:
            with suppress(ClientError, TimeoutError):
                await websocket.close()
        raise SamsungTextInputProtocolError(
            "The TV did not complete the text-input handshake"
        )

    @staticmethod
    def _parse_response(payload: str) -> dict[str, Any]:
        """Return one bounded WebSocket response object."""
        if len(payload.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise SamsungTextInputProtocolError(
                "The TV text-input response was too large"
            )
        try:
            response = json.loads(payload)
        except json.JSONDecodeError:
            raise SamsungTextInputProtocolError(
                "The TV returned invalid text-input JSON"
            ) from None
        if not isinstance(response, dict):
            raise SamsungTextInputProtocolError(
                "The TV returned an invalid text-input response"
            )
        return response

    def _sync_get_certificate_fingerprint(self) -> str:
        """Return the current WebSocket TLS certificate SHA-256 fingerprint."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with (
            socket.create_connection(
                (self.host, self.port), timeout=TEXT_COMMAND_TIMEOUT
            ) as raw_socket,
            context.wrap_socket(raw_socket, server_hostname=self.host) as tls_socket,
        ):
            certificate = tls_socket.getpeercert(binary_form=True)
        if not certificate:
            raise SamsungTextInputCertificateError(
                "The TV did not present a text-input certificate"
            )
        return hashlib.sha256(certificate).hexdigest()

    @staticmethod
    def _normalize_fingerprint(value: str) -> str:
        """Return a normalized SHA-256 fingerprint or raise ValueError."""
        normalized = value.replace(":", "").strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("Invalid certificate fingerprint")
        return normalized
