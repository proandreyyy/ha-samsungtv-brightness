"""Focused unit tests for the protocol client without a Home Assistant install."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).parents[1]
PACKAGE_PATH = ROOT / "custom_components" / "samsung_ip_control"

package = types.ModuleType("samsung_ip_control")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules["samsung_ip_control"] = package


def _load_module(name: str, filename: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, PACKAGE_PATH / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load_module("samsung_ip_control.const", "const.py")
const_module = sys.modules["samsung_ip_control.const"]
client_module = _load_module("samsung_ip_control.client", "client.py")

SamsungIPControlClient = client_module.SamsungIPControlClient
SamsungIPControlCertificateError = client_module.SamsungIPControlCertificateError
SamsungIPControlProtocolError = client_module.SamsungIPControlProtocolError
SamsungIPControlTransportError = client_module.SamsungIPControlTransportError
MAX_RESPONSE_BYTES = client_module.MAX_RESPONSE_BYTES
normalize_mac = client_module.normalize_mac
source_from_api = client_module.source_from_api
REMOTE_COMMANDS = const_module.REMOTE_COMMANDS
REMOTE_KEY_TO_API = const_module.REMOTE_KEY_TO_API
APP_COMMANDS = const_module.APP_COMMANDS
APP_TO_API = const_module.APP_TO_API
BACKLIGHT_MIN = const_module.BACKLIGHT_MIN
BACKLIGHT_MAX = const_module.BACKLIGHT_MAX
BACKLIGHT_STEP = const_module.BACKLIGHT_STEP


class FakeHomeAssistant:
    """Run executor jobs inline for unit tests."""

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class RecordingClient(SamsungIPControlClient):
    """Record high-level command dispatch without network I/O."""

    def __init__(self) -> None:
        super().__init__(FakeHomeAssistant(), "192.0.2.1", token="secret")
        self.calls: list[tuple[str, object]] = []

    async def async_send_navigation_key(self, command: str) -> None:
        self.calls.append(("remote_key", command))

    async def async_volume_up(self) -> None:
        self.calls.append(("volume", "up"))

    async def async_volume_down(self) -> None:
        self.calls.append(("volume", "down"))

    async def async_channel_up(self) -> None:
        self.calls.append(("channel", "up"))

    async def async_channel_down(self) -> None:
        self.calls.append(("channel", "down"))

    async def async_toggle_mute(self) -> None:
        self.calls.append(("mute", "toggle"))

    async def async_select_source(self, source: str, *, reliable: bool = True) -> None:
        self.calls.append(("source", source))

    async def async_power_on(self) -> None:
        self.calls.append(("power", "on"))

    async def async_power_off(self) -> None:
        self.calls.append(("power", "off"))

    async def async_launch_app(self, app: str) -> None:
        self.calls.append(("app", app))

    async def async_step_backlight(self, delta: int) -> int:
        self.calls.append(("backlight", delta))
        return 0


class MuteRecordingClient(SamsungIPControlClient):
    """Record explicit mute writes while simulating slow TV state reporting."""

    def __init__(self) -> None:
        super().__init__(FakeHomeAssistant(), "192.0.2.1", token="secret")
        self.requested_mute_states: list[bool] = []

    async def async_get_mute(self) -> bool:
        raise AssertionError("A cached mute state should avoid a stale getter")

    async def async_set_mute(self, muted: bool) -> None:
        self.requested_mute_states.append(muted)
        self._mute_state = muted


class WakeSourceClient(SamsungIPControlClient):
    """Simulate a TV whose HTTPS endpoint is unavailable while off."""

    def __init__(self) -> None:
        super().__init__(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            mac="00:00:5E:00:53:01",
        )
        self.calls: list[tuple[str, object]] = []

    async def async_get_power(self) -> bool:
        raise SamsungIPControlTransportError("TV is asleep")

    async def async_wake_on_lan(self) -> None:
        self.calls.append(("power", "wake_on_lan"))

    async def _async_request(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        return {}


class ClientHelperTests(unittest.TestCase):
    def test_mac_normalization(self) -> None:
        self.assertEqual(normalize_mac("00-00-5E-00-53-01"), "00:00:5E:00:53:01")
        with self.assertRaises(ValueError):
            normalize_mac("invalid")

    def test_source_normalization(self) -> None:
        self.assertEqual(source_from_api("HDMI4"), "HDMI 4")
        self.assertEqual(source_from_api("hdmi 2"), "HDMI 2")
        self.assertIsNone(source_from_api("digitalTv"))

    def test_request_contains_token_and_never_requires_it_for_pairing(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint="A" * 64,
        )
        payloads: list[dict[str, object]] = []

        def fake_post(payload: bytes, timeout: int) -> str:
            request = json.loads(payload)
            payloads.append(request)
            return json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": {}})

        client._sync_post = fake_post
        client._sync_request(1, "powerControl", None, True, 6)
        client._sync_request(2, "createAccessToken", None, False, 40)
        self.assertEqual(payloads[0]["id"], "1")
        self.assertEqual(payloads[1]["id"], "2")
        self.assertEqual(payloads[0]["params"], {"AccessToken": "secret"})
        self.assertNotIn("params", payloads[1])

    def test_authenticated_request_requires_certificate_pin(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(), "192.0.2.1", token="secret"
        )
        client._sync_post = Mock(side_effect=AssertionError("Network must stay unused"))

        with self.assertRaisesRegex(
            SamsungIPControlCertificateError, "trusted TV certificate"
        ):
            client._sync_request(1, "powerControl", None, True, 6)
        client._sync_post.assert_not_called()

    def test_response_must_match_json_rpc_version_and_request_id(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint="A" * 64,
        )
        client._sync_post = lambda payload, timeout: json.dumps(
            {"jsonrpc": "1.0", "id": "1", "result": {}}
        )
        with self.assertRaisesRegex(SamsungIPControlProtocolError, "JSON-RPC version"):
            client._sync_request(1, "powerControl", None, True, 6)

        client._sync_post = lambda payload, timeout: json.dumps(
            {"jsonrpc": "2.0", "id": "2", "result": {}}
        )
        with self.assertRaisesRegex(
            SamsungIPControlProtocolError, "mismatched JSON-RPC"
        ):
            client._sync_request(1, "powerControl", None, True, 6)

        client._sync_post = lambda payload, timeout: json.dumps(
            {"jsonrpc": "2.0", "id": 1, "result": {}}
        )
        with self.assertRaisesRegex(
            SamsungIPControlProtocolError, "mismatched JSON-RPC"
        ):
            client._sync_request(1, "powerControl", None, True, 6)

    def test_remote_error_message_is_not_copied_into_exception(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint="A" * 64,
        )
        client._sync_post = lambda payload, timeout: json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "1",
                "error": {"code": -1, "message": "attacker-controlled-log-text"},
            }
        )
        with self.assertRaises(SamsungIPControlProtocolError) as context:
            client._sync_request(1, "powerControl", None, True, 6)
        self.assertNotIn("attacker-controlled-log-text", str(context.exception))

    def test_http_response_size_is_bounded(self) -> None:
        certificate = b"samsung-tv-certificate"

        class FakeSocket:
            def getpeercert(self, *, binary_form: bool) -> bytes:
                return certificate

        class FakeResponse:
            status = 200

            def getheader(self, name: str) -> str | None:
                if name == "Content-Length":
                    return str(MAX_RESPONSE_BYTES + 1)
                return None

            def read(self, amount: int) -> bytes:
                raise AssertionError("Oversized response bodies must not be read")

        class FakeConnection:
            def __init__(self) -> None:
                self.sock = FakeSocket()

            def connect(self) -> None:
                return None

            def putrequest(self, *args, **kwargs) -> None:
                return None

            def putheader(self, *args, **kwargs) -> None:
                return None

            def endheaders(self) -> None:
                return None

            def send(self, payload: bytes) -> None:
                return None

            def getresponse(self) -> FakeResponse:
                return FakeResponse()

            def close(self) -> None:
                return None

        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint=SamsungIPControlClient._fingerprint(certificate),
        )
        with patch.object(
            client_module.http.client,
            "HTTPSConnection",
            return_value=FakeConnection(),
        ):
            with self.assertRaisesRegex(SamsungIPControlProtocolError, "size limit"):
                client._sync_post(b"{}", 6)

    def test_transport_error_omits_private_host(self) -> None:
        private_host = "private-household-tv.example"
        client = SamsungIPControlClient(
            FakeHomeAssistant(), private_host, token="secret"
        )

        class FailedConnection:
            def __init__(self, *args, **kwargs) -> None:
                return None

            def connect(self) -> None:
                raise OSError("private transport detail")

            def close(self) -> None:
                return None

        with patch.object(
            client_module.http.client,
            "HTTPSConnection",
            FailedConnection,
        ):
            with self.assertRaises(SamsungIPControlTransportError) as context:
                client._sync_post(b"{}", 6)
        self.assertNotIn(private_host, str(context.exception))
        self.assertNotIn("private transport detail", str(context.exception))

    def test_device_information_ignores_non_string_values(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(), "192.0.2.1", token="secret"
        )
        with patch.object(
            client,
            "_async_request",
            new=AsyncMock(
                return_value={
                    "modelID": " model ",
                    "FWVersion": None,
                    "serialNumber": 123,
                }
            ),
        ):
            result = self._run(client.async_get_device_information())
        self.assertEqual(result, {"model": "model", "firmware": "", "serial": ""})

    @staticmethod
    def _run(coroutine):
        return asyncio.run(coroutine)

    def test_certificate_fingerprint_is_normalized_and_enforced(self) -> None:
        certificate = b"samsung-tv-certificate"
        fingerprint = SamsungIPControlClient._fingerprint(certificate)
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint=":".join(
                fingerprint[index : index + 2]
                for index in range(0, len(fingerprint), 2)
            ),
        )
        client._validate_peer_certificate(certificate)
        with self.assertRaises(SamsungIPControlCertificateError):
            client._validate_peer_certificate(b"different-certificate")

    def test_tls_requires_version_1_2_or_newer(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(), "192.0.2.1", token="secret"
        )
        self.assertEqual(
            client._get_ssl_context().minimum_version,
            client_module.ssl.TLSVersion.TLSv1_2,
        )

    def test_certificate_mismatch_stops_request_before_token_is_sent(self) -> None:
        class FakeSocket:
            def getpeercert(self, *, binary_form: bool) -> bytes:
                if not binary_form:
                    raise AssertionError(
                        "The certificate must be requested in DER form"
                    )
                return b"unexpected-certificate"

        class FakeConnection:
            def __init__(self) -> None:
                self.sock = FakeSocket()
                self.sent = False

            def connect(self) -> None:
                return None

            def putrequest(self, *args, **kwargs) -> None:
                return None

            def putheader(self, *args, **kwargs) -> None:
                return None

            def endheaders(self) -> None:
                return None

            def send(self, payload: bytes) -> None:
                self.sent = True

            def close(self) -> None:
                return None

        expected = SamsungIPControlClient._fingerprint(b"expected-certificate")
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint=expected,
        )
        connection = FakeConnection()
        with patch.object(
            client_module.http.client,
            "HTTPSConnection",
            return_value=connection,
        ):
            with self.assertRaises(SamsungIPControlCertificateError):
                client._sync_request(1, "powerControl", None, True, 6)
        self.assertFalse(connection.sent)


class RemoteCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_allowlisted_remote_commands_dispatch(self) -> None:
        client = RecordingClient()
        for command in REMOTE_COMMANDS:
            await client.async_run_remote_command(command)
        self.assertEqual(len(client.calls), len(REMOTE_COMMANDS))
        for command in REMOTE_KEY_TO_API:
            self.assertIn(("remote_key", command), client.calls)
        for index in range(1, 5):
            self.assertIn(("source", f"HDMI {index}"), client.calls)
        self.assertIn(("channel", "up"), client.calls)
        self.assertIn(("channel", "down"), client.calls)
        for command in APP_COMMANDS:
            self.assertIn(("app", command.removeprefix("app_")), client.calls)
        self.assertIn(("backlight", BACKLIGHT_STEP), client.calls)
        self.assertIn(("backlight", -BACKLIGHT_STEP), client.calls)

    async def test_extended_remote_keys_use_documented_api_values(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(), "192.0.2.1", token="secret"
        )
        with patch.object(client, "_async_request", new=AsyncMock()) as request:
            await client.async_send_navigation_key("fast_forward")
            await client.async_send_navigation_key("digit_7")
            await client.async_send_navigation_key("multiview")
        self.assertEqual(
            request.await_args_list,
            [
                unittest.mock.call("remoteKeyControl", {"remoteKey": "fastforward"}),
                unittest.mock.call("remoteKeyControl", {"remoteKey": "number7"}),
                unittest.mock.call("remoteKeyControl", {"remoteKey": "multiview"}),
            ],
        )

    async def test_channel_buttons_use_channel_control(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(), "192.0.2.1", token="secret"
        )
        with patch.object(client, "_async_request", new=AsyncMock()) as request:
            await client.async_channel_up()
            await client.async_channel_down()
        self.assertEqual(
            request.await_args_list,
            [
                unittest.mock.call("channelUpDnControl", {"control": "channelUp"}),
                unittest.mock.call("channelUpDnControl", {"control": "channelDn"}),
            ],
        )

    async def test_direct_app_access_is_allowlisted(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(), "192.0.2.1", token="secret"
        )
        with (
            patch.object(client, "async_get_power", new=AsyncMock(return_value=True)),
            patch.object(client, "_async_request", new=AsyncMock()) as request,
        ):
            await client.async_launch_app("Netflix")
            await client.async_launch_app("Prime Video")
        self.assertEqual(
            request.await_args_list,
            [
                unittest.mock.call(
                    "directAccessControl",
                    {"applicationName": APP_TO_API["netflix"]},
                ),
                unittest.mock.call(
                    "directAccessControl",
                    {"applicationName": APP_TO_API["amazon"]},
                ),
            ],
        )
        with self.assertRaises(ValueError):
            await client.async_launch_app("arbitrary-unreviewed-app")

    async def test_app_launch_uses_wol_when_power_read_cannot_connect(self) -> None:
        client = WakeSourceClient()
        with patch.object(client_module.asyncio, "sleep", new=AsyncMock()):
            await client.async_launch_app("youtube")
        self.assertEqual(client.calls[0], ("power", "wake_on_lan"))
        self.assertEqual(
            client.calls[1],
            (
                "directAccessControl",
                {"applicationName": APP_TO_API["youtube"]},
            ),
        )

    @staticmethod
    def _power_client() -> SamsungIPControlClient:
        return SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            mac="00:00:5E:00:53:01",
            certificate_fingerprint="AA" * 32,
        )

    async def test_power_on_always_attempts_the_ip_write_first(self) -> None:
        """Wake-on-LAN alone does not wake the tested set, so it cannot replace
        the IP write when a MAC happens to be configured."""
        client = self._power_client()
        with (
            patch.object(client, "_async_request", new=AsyncMock()) as request,
            patch.object(client, "async_wake_on_lan", new=AsyncMock()) as wake,
            patch.object(client, "async_get_power", new=AsyncMock()) as read,
        ):
            await client.async_power_on()
        request.assert_awaited_once_with("powerControl", {"power": "powerOn"})
        wake.assert_not_awaited()
        read.assert_not_awaited()

    async def test_power_on_without_mac_accepts_not_applicable_without_polling(
        self,
    ) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint="AA" * 32,
        )
        rejection = SamsungIPControlProtocolError("rejected", code=-32002)
        with (
            patch.object(
                client, "_async_request", new=AsyncMock(side_effect=rejection)
            ),
            patch.object(client, "async_get_power", new=AsyncMock()) as read,
        ):
            await client.async_power_on()
        read.assert_not_awaited()

    async def test_power_on_propagates_an_unrelated_rejection(self) -> None:
        """Only the documented not-applicable code is treated as pending."""
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint="AA" * 32,
        )
        rejection = SamsungIPControlProtocolError("rejected", code=-32099)
        with (
            patch.object(
                client, "_async_request", new=AsyncMock(side_effect=rejection)
            ),
            patch.object(client, "async_wake_on_lan", new=AsyncMock()) as wake,
            self.assertRaises(SamsungIPControlProtocolError),
        ):
            await client.async_power_on()
        wake.assert_not_awaited()

    async def test_power_off_propagates_rejection_without_polling_or_wol(self) -> None:
        client = self._power_client()
        rejection = SamsungIPControlProtocolError("rejected", code=-32002)
        with (
            patch.object(
                client, "_async_request", new=AsyncMock(side_effect=rejection)
            ),
            patch.object(client, "async_wake_on_lan", new=AsyncMock()) as wake,
            patch.object(client, "async_get_power", new=AsyncMock()) as read,
            self.assertRaises(SamsungIPControlProtocolError),
        ):
            await client.async_power_off()
        wake.assert_not_awaited()
        read.assert_not_awaited()

    async def test_successful_power_write_skips_the_confirmation_read(self) -> None:
        client = SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint="AA" * 32,
        )
        with (
            patch.object(client, "_async_request", new=AsyncMock(return_value={})),
            patch.object(client, "async_get_power", new=AsyncMock()) as read,
        ):
            await client.async_power_on()
        read.assert_not_awaited()

    async def test_unknown_remote_command_is_rejected(self) -> None:
        client = RecordingClient()
        with self.assertRaises(ValueError):
            await client.async_run_remote_command("launch_app")

    async def test_two_fast_mute_presses_are_deterministic(self) -> None:
        client = MuteRecordingClient()
        client._mute_state = False
        await client.async_toggle_mute()
        await client.async_toggle_mute()
        self.assertEqual(client.requested_mute_states, [True, False])

    async def test_hdmi_selection_uses_wol_when_power_read_cannot_connect(self) -> None:
        client = WakeSourceClient()
        with patch.object(client_module.asyncio, "sleep", new=AsyncMock()):
            await client.async_select_source("HDMI 2")
        self.assertEqual(client.calls[0], ("power", "wake_on_lan"))
        self.assertEqual(
            client.calls[1:],
            [
                ("inputSourceControl", {"inputSource": "HDMI2"}),
                ("inputSourceControl", {"inputSource": "HDMI2"}),
            ],
        )


class BacklightTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _client() -> SamsungIPControlClient:
        return SamsungIPControlClient(
            FakeHomeAssistant(),
            "192.0.2.1",
            token="secret",
            certificate_fingerprint="AA" * 32,
        )

    async def test_get_backlight_reads_the_native_value(self) -> None:
        client = self._client()
        with patch.object(
            client,
            "_async_request",
            new=AsyncMock(return_value={"backlight": 30}),
        ):
            self.assertEqual(await client.async_get_backlight(), 30)

    async def test_get_backlight_rejects_an_out_of_range_reading(self) -> None:
        client = self._client()
        with patch.object(
            client,
            "_async_request",
            new=AsyncMock(return_value={"backlight": BACKLIGHT_MAX + 1}),
        ):
            with self.assertRaises(SamsungIPControlProtocolError):
                await client.async_get_backlight()

    async def test_set_backlight_rejects_out_of_range_values(self) -> None:
        client = self._client()
        with self.assertRaises(ValueError):
            await client.async_set_backlight(BACKLIGHT_MIN - 1)
        with self.assertRaises(ValueError):
            await client.async_set_backlight(BACKLIGHT_MAX + 1)

    async def test_set_backlight_writes_directly_with_no_power_check(self) -> None:
        """A preceding powerControl read visibly dulled the effect on a real
        Samsung QN90B, unlike the sibling project's direct write."""
        client = self._client()
        with (
            patch.object(client, "async_get_power", new=AsyncMock()) as get_power,
            patch.object(client, "_async_request", new=AsyncMock()) as request,
        ):
            await client.async_set_backlight(25)
        get_power.assert_not_awaited()
        request.assert_awaited_once_with("backlightControl", {"backlight": 25})

    async def test_step_backlight_clamps_at_the_maximum_and_skips_the_write(
        self,
    ) -> None:
        client = self._client()
        with (
            patch.object(
                client, "async_get_backlight", new=AsyncMock(return_value=BACKLIGHT_MAX)
            ),
            patch.object(client, "async_set_backlight", new=AsyncMock()) as setter,
        ):
            target = await client.async_step_backlight(BACKLIGHT_STEP)
        self.assertEqual(target, BACKLIGHT_MAX)
        setter.assert_not_awaited()

    async def test_step_backlight_clamps_at_the_minimum(self) -> None:
        client = self._client()
        with (
            patch.object(client, "async_get_backlight", new=AsyncMock(return_value=5)),
            patch.object(client, "async_set_backlight", new=AsyncMock()) as setter,
        ):
            target = await client.async_step_backlight(-BACKLIGHT_STEP)
        self.assertEqual(target, BACKLIGHT_MIN)
        setter.assert_awaited_once_with(BACKLIGHT_MIN)

    async def test_run_remote_command_returns_the_new_backlight(self) -> None:
        client = self._client()
        with patch.object(
            client, "async_step_backlight", new=AsyncMock(return_value=40)
        ) as step:
            result = await client.async_run_remote_command("brightness_up")
        step.assert_awaited_once_with(BACKLIGHT_STEP)
        self.assertEqual(result, 40)

    async def test_run_remote_command_returns_none_for_other_commands(self) -> None:
        client = RecordingClient()
        result = await client.async_run_remote_command("volume_up")
        self.assertIsNone(result)

    async def test_queue_backlight_rejects_out_of_range_values(self) -> None:
        client = self._client()
        with self.assertRaises(ValueError):
            client.async_queue_backlight(BACKLIGHT_MIN - 1)
        with self.assertRaises(ValueError):
            client.async_queue_backlight(BACKLIGHT_MAX + 1)

    async def test_queue_backlight_coalesces_rapid_writes(self) -> None:
        """A fast slider drag must not work through every intermediate value;
        only the target in flight and the final one should ever be written."""
        client = self._client()
        written: list[int] = []
        release = asyncio.Event()

        async def fake_set_backlight(value: int) -> None:
            written.append(value)
            if len(written) == 1:
                await release.wait()

        with patch.object(client, "async_set_backlight", new=fake_set_backlight):
            client.async_queue_backlight(10)
            await asyncio.sleep(0)  # let the writer claim 10 and block on it
            client.async_queue_backlight(20)
            client.async_queue_backlight(30)
            client.async_queue_backlight(40)
            release.set()
            await client._backlight_writer

        self.assertEqual(written, [10, 40])

    async def test_queue_backlight_logs_and_survives_a_write_failure(self) -> None:
        client = self._client()
        with patch.object(
            client,
            "async_set_backlight",
            new=AsyncMock(
                side_effect=SamsungIPControlProtocolError("rejected", code=-32601)
            ),
        ):
            with self.assertLogs(client_module.__name__, level="WARNING"):
                client.async_queue_backlight(10)
                await client._backlight_writer


if __name__ == "__main__":
    unittest.main()
