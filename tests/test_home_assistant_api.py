"""Focused tests that run when the pinned Home Assistant package is installed."""

from __future__ import annotations

import asyncio
import base64
import json
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

try:
    from aiohttp import Fingerprint, WSMsgType
    from homeassistant.components.http import KEY_HASS, KEY_HASS_USER
    from homeassistant.components.media_player import (
        MediaPlayerEntityFeature,
        MediaType,
    )
    from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
    from homeassistant.exceptions import ConfigEntryAuthFailed
except ModuleNotFoundError as ex:
    raise unittest.SkipTest(
        "Home Assistant API tests require the pinned package"
    ) from ex

from custom_components.samsung_ip_control import async_setup, async_setup_entry
from custom_components.samsung_ip_control.config_flow import (
    SamsungIPControlConfigFlow,
    SamsungIPControlOptionsFlow,
    _serial_hash,
)
from custom_components.samsung_ip_control.const import (
    CONF_CERTIFICATE_FINGERPRINT,
    CONF_ENTITY_IDENTITY,
    CONF_SERIAL_HASH,
    CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT,
    CONF_TEXT_INPUT_ENABLED,
    CONF_TEXT_INPUT_PORT,
    CONF_TEXT_INPUT_TOKEN,
    CONF_TOKEN,
    DOMAIN,
)
from custom_components.samsung_ip_control.coordinator import (
    SamsungIPControlCoordinator,
)
from custom_components.samsung_ip_control.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.samsung_ip_control.media_player import (
    SamsungIPControlMediaPlayer,
)
from custom_components.samsung_ip_control.remote import SamsungIPControlRemote
from custom_components.samsung_ip_control.sensitive_text import (
    MAX_REQUEST_BYTES,
    SENSITIVE_TEXT_API_URL,
    SamsungSensitiveTextView,
)
from custom_components.samsung_ip_control.text_client import (
    MAX_TEXT_LENGTH,
    SamsungTextInputClient,
    SamsungTextInputProtocolError,
)


class FakeTextWebSocket:
    """Record text-input WebSocket messages."""

    def __init__(self, responses: list[types.SimpleNamespace] | None = None) -> None:
        self.sent: list[dict[str, object]] = []
        self.closed = False
        self.responses = responses or []
        self._closed_event = asyncio.Event()

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True
        self._closed_event.set()

    async def receive(self) -> types.SimpleNamespace:
        if self.responses:
            return self.responses.pop(0)
        await self._closed_event.wait()
        return types.SimpleNamespace(type=WSMsgType.CLOSED, data=None)


class FakeTextSession:
    """Record certificate-pinned WebSocket connections."""

    def __init__(self, websocket: FakeTextWebSocket) -> None:
        self.ws_connect = AsyncMock(return_value=websocket)


class FakeConfigEntries:
    """Provide the config-entry methods used by the migration helper."""

    def __init__(self, entries: list[types.SimpleNamespace]) -> None:
        self.entries = entries

    def async_entries(self, domain: str) -> list[types.SimpleNamespace]:
        if domain != DOMAIN:
            raise AssertionError("Unexpected integration domain")
        return self.entries


class FakeSensitiveTextRequest:
    """Provide only the authenticated request data used by the private view."""

    def __init__(
        self,
        hass: object,
        user: object,
        payload: object,
        *,
        content_length: int = 128,
    ) -> None:
        self.app = {KEY_HASS: hass}
        self.content_length = content_length
        self._user = user
        self.json = AsyncMock(return_value=payload)

    def __getitem__(self, key: object) -> object:
        if key != KEY_HASS_USER:
            raise KeyError(key)
        return self._user


class HomeAssistantApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_integration_registers_text_action_under_its_domain(self) -> None:
        http = types.SimpleNamespace(
            async_register_static_paths=AsyncMock(),
            register_view=Mock(),
        )
        with patch(
            "custom_components.samsung_ip_control.services.service.async_register_platform_entity_service"
        ) as register:
            result = await async_setup(types.SimpleNamespace(http=http), {})

        self.assertTrue(result)
        http.async_register_static_paths.assert_awaited_once()
        static_path = http.async_register_static_paths.await_args.args[0][0]
        self.assertEqual(
            static_path.url_path,
            "/samsung_ip_control_static/samsung-ip-remote-card.js",
        )
        self.assertFalse(static_path.cache_headers)
        register.assert_called_once()
        self.assertEqual(register.call_args.args[1:3], (DOMAIN, "send_text"))
        self.assertEqual(register.call_args.kwargs["entity_domain"], "remote")
        self.assertEqual(register.call_args.kwargs["func"], "async_send_text")
        http.register_view.assert_called_once()
        view = http.register_view.call_args.args[0]
        self.assertIsInstance(view, SamsungSensitiveTextView)
        self.assertEqual(view.url, SENSITIVE_TEXT_API_URL)
        self.assertTrue(view.requires_auth)

    async def test_sensitive_text_api_is_permission_checked_and_non_persistent(
        self,
    ) -> None:
        text_client = types.SimpleNamespace(async_send_text=AsyncMock())
        config_entry = types.SimpleNamespace(
            domain=DOMAIN,
            runtime_data=types.SimpleNamespace(text_client=text_client),
        )
        hass = types.SimpleNamespace(
            config_entries=types.SimpleNamespace(
                async_get_entry=Mock(return_value=config_entry)
            )
        )
        registry = types.SimpleNamespace(
            async_get=Mock(
                return_value=types.SimpleNamespace(
                    platform=DOMAIN,
                    config_entry_id="test-entry",
                )
            )
        )
        user = types.SimpleNamespace(
            permissions=types.SimpleNamespace(check_entity=Mock(return_value=True))
        )
        request = FakeSensitiveTextRequest(
            hass,
            user,
            {
                "entity_id": "remote.samsung_tv_remote",
                "password": "transient value",
            },
        )

        with patch(
            "custom_components.samsung_ip_control.sensitive_text.er.async_get",
            return_value=registry,
        ):
            response = await SamsungSensitiveTextView().post(request)

        text_client.async_send_text.assert_awaited_once_with(
            "transient value", submit=False
        )
        user.permissions.check_entity.assert_called_once()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(json.loads(response.body), {"success": True})
        self.assertNotIn(b"transient value", response.body)

    async def test_sensitive_text_api_rejects_oversized_body_before_parsing(
        self,
    ) -> None:
        request = FakeSensitiveTextRequest(
            types.SimpleNamespace(),
            types.SimpleNamespace(),
            {},
            content_length=MAX_REQUEST_BYTES + 1,
        )

        response = await SamsungSensitiveTextView().post(request)

        self.assertEqual(response.status, 413)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        request.json.assert_not_awaited()

    def test_options_flow_uses_current_config_entry_api(self) -> None:
        options_flow = SamsungIPControlConfigFlow.async_get_options_flow(
            types.SimpleNamespace()
        )
        self.assertIsNone(options_flow._pending_text_port)

    async def test_reauthentication_replaces_token_after_identity_check(self) -> None:
        entry = types.SimpleNamespace(
            entry_id="entry-one",
            unique_id="verified-serial",
            data={
                CONF_HOST: "192.0.2.1",
                CONF_PORT: 1516,
                CONF_MAC: "",
                CONF_TOKEN: "rejected-token",
                CONF_CERTIFICATE_FINGERPRINT: "A" * 64,
                CONF_ENTITY_IDENTITY: "stable-entity-identity",
                CONF_SERIAL_HASH: _serial_hash("verified-serial"),
            },
        )
        config_entries = FakeConfigEntries([entry])
        update_reload_and_abort = Mock(return_value={"type": "abort"})
        flow = types.SimpleNamespace(
            hass=types.SimpleNamespace(config_entries=config_entries),
            _get_reauth_entry=Mock(return_value=entry),
            async_set_unique_id=AsyncMock(),
            _verified_identity_updates=lambda current, serial: (
                SamsungIPControlConfigFlow._verified_identity_updates(
                    flow, current, serial
                )
            ),
            async_update_reload_and_abort=update_reload_and_abort,
        )
        client = types.SimpleNamespace(
            certificate_fingerprint="A" * 64,
            async_trust_current_certificate=AsyncMock(),
            async_pair=AsyncMock(return_value="replacement-token"),
            async_get_power=AsyncMock(return_value=True),
            async_get_device_information=AsyncMock(
                return_value={"serial": "verified-serial"}
            ),
        )

        with patch(
            "custom_components.samsung_ip_control.config_flow.SamsungIPControlClient",
            return_value=client,
        ):
            result = await SamsungIPControlConfigFlow.async_step_reauth_confirm(
                flow, {}
            )

        self.assertEqual(result, {"type": "abort"})
        client.async_trust_current_certificate.assert_not_awaited()
        flow.async_set_unique_id.assert_awaited_once_with("verified-serial")
        update_reload_and_abort.assert_called_once_with(
            entry,
            unique_id="verified-serial",
            data_updates={
                CONF_TOKEN: "replacement-token",
                CONF_CERTIFICATE_FINGERPRINT: "A" * 64,
                CONF_ENTITY_IDENTITY: "stable-entity-identity",
                CONF_SERIAL_HASH: _serial_hash("verified-serial"),
            },
        )

    async def test_legacy_reauthentication_establishes_missing_pin(self) -> None:
        entry = types.SimpleNamespace(
            entry_id="entry-one",
            unique_id="192.0.2.1",
            data={
                CONF_HOST: "192.0.2.1",
                CONF_PORT: 1516,
                CONF_MAC: "",
                CONF_TOKEN: "rejected-token",
            },
        )
        config_entries = FakeConfigEntries([entry])
        update_reload_and_abort = Mock(return_value={"type": "abort"})
        flow = types.SimpleNamespace(
            hass=types.SimpleNamespace(config_entries=config_entries),
            _get_reauth_entry=Mock(return_value=entry),
            async_set_unique_id=AsyncMock(),
            _verified_identity_updates=lambda current, serial: (
                SamsungIPControlConfigFlow._verified_identity_updates(
                    flow, current, serial
                )
            ),
            async_update_reload_and_abort=update_reload_and_abort,
        )
        client = types.SimpleNamespace(
            certificate_fingerprint=None,
            async_pair=AsyncMock(return_value="replacement-token"),
            async_get_power=AsyncMock(return_value=True),
            async_get_device_information=AsyncMock(
                return_value={"serial": "verified-serial"}
            ),
        )

        async def trust_current_certificate() -> str:
            client.certificate_fingerprint = "B" * 64
            return client.certificate_fingerprint

        client.async_trust_current_certificate = AsyncMock(
            side_effect=trust_current_certificate
        )

        with patch(
            "custom_components.samsung_ip_control.config_flow.SamsungIPControlClient",
            return_value=client,
        ):
            result = await SamsungIPControlConfigFlow.async_step_reauth_confirm(
                flow, {}
            )

        self.assertEqual(result, {"type": "abort"})
        client.async_trust_current_certificate.assert_awaited_once()
        update_reload_and_abort.assert_called_once_with(
            entry,
            unique_id="verified-serial",
            data_updates={
                CONF_TOKEN: "replacement-token",
                CONF_CERTIFICATE_FINGERPRINT: "B" * 64,
                CONF_ENTITY_IDENTITY: "192.0.2.1",
                CONF_SERIAL_HASH: _serial_hash("verified-serial"),
            },
        )

    async def test_disabling_text_input_removes_only_pairing_secrets(self) -> None:
        current_options = {
            CONF_TEXT_INPUT_ENABLED: True,
            CONF_TEXT_INPUT_PORT: 8002,
            CONF_TEXT_INPUT_TOKEN: "separate-text-token",
            CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT: "C" * 64,
            "unrelated_option": "retained",
        }
        create_entry = Mock(side_effect=lambda *, title, data: data)
        flow = types.SimpleNamespace(
            config_entry=types.SimpleNamespace(options=current_options),
            _pending_text_port=None,
            async_create_entry=create_entry,
        )

        result = await SamsungIPControlOptionsFlow.async_step_init(
            flow,
            {
                CONF_TEXT_INPUT_ENABLED: False,
                CONF_TEXT_INPUT_PORT: 8002,
            },
        )

        self.assertEqual(
            result,
            {
                CONF_TEXT_INPUT_ENABLED: False,
                CONF_TEXT_INPUT_PORT: 8002,
                "unrelated_option": "retained",
            },
        )
        self.assertNotIn(CONF_TEXT_INPUT_TOKEN, result)
        self.assertNotIn(CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT, result)

    async def test_text_input_pairing_uses_pinned_secure_websocket(self) -> None:
        response = {
            "event": "ms.channel.connect",
            "data": {"token": "separate-pairing-token"},
        }
        websocket = FakeTextWebSocket(
            [types.SimpleNamespace(type=WSMsgType.TEXT, data=json.dumps(response))]
        )
        session = FakeTextSession(websocket)
        client = SamsungTextInputClient(
            types.SimpleNamespace(),
            "192.0.2.1",
            port=8002,
            certificate_fingerprint="A" * 64,
        )

        with patch(
            "custom_components.samsung_ip_control.text_client.async_get_clientsession",
            return_value=session,
        ):
            token = await client.async_pair()

        self.assertEqual(token, "separate-pairing-token")
        self.assertTrue(websocket.closed)
        session.ws_connect.assert_awaited_once()
        url = session.ws_connect.await_args.args[0]
        options = session.ws_connect.await_args.kwargs
        self.assertEqual(url.scheme, "wss")
        self.assertEqual(url.host, "192.0.2.1")
        self.assertEqual(url.port, 8002)
        self.assertEqual(
            url.path,
            "/api/v2/channels/samsung.remote.control",
        )
        self.assertNotIn("token", url.query)
        self.assertIsInstance(options["ssl"], Fingerprint)
        self.assertEqual(options["max_msg_size"], 64 * 1024)

    async def test_optional_text_input_reuses_one_bounded_session(self) -> None:
        client = SamsungTextInputClient(
            types.SimpleNamespace(),
            "192.0.2.1",
            token="separate-text-token",
            certificate_fingerprint="A" * 64,
        )
        websocket = FakeTextWebSocket()
        client._async_open = AsyncMock(  # type: ignore[method-assign]
            return_value=(websocket, {"event": "ms.channel.connect"})
        )

        await client.async_send_text("Y", submit=False)
        await client.async_send_text("You", submit=False)
        await client.async_send_text("Y", submit=False)
        await client.async_send_text("", submit=True)

        self.assertEqual(
            websocket.sent,
            [
                {
                    "method": "ms.remote.control",
                    "params": {
                        "Cmd": base64.b64encode(b"Y").decode("ascii"),
                        "DataOfCmd": "base64",
                        "TypeOfRemote": "SendInputString",
                    },
                },
                {
                    "method": "ms.remote.control",
                    "params": {
                        "Cmd": base64.b64encode(b"You").decode("ascii"),
                        "DataOfCmd": "base64",
                        "TypeOfRemote": "SendInputString",
                    },
                },
                {
                    "method": "ms.remote.control",
                    "params": {
                        "Cmd": base64.b64encode(b"Y").decode("ascii"),
                        "DataOfCmd": "base64",
                        "TypeOfRemote": "SendInputString",
                    },
                },
                {
                    "method": "ms.remote.control",
                    "params": {
                        "Cmd": "",
                        "DataOfCmd": "base64",
                        "TypeOfRemote": "SendInputString",
                    },
                },
                {
                    "method": "ms.remote.control",
                    "params": {"TypeOfRemote": "SendInputEnd"},
                },
            ],
        )
        client._async_open.assert_awaited_once()  # type: ignore[attr-defined]
        self.assertFalse(websocket.closed)
        await client.async_close()
        self.assertTrue(websocket.closed)

        with self.assertRaises(ValueError):
            await client.async_send_text("contains\nnewline")
        with self.assertRaises(ValueError):
            await client.async_send_text("x" * (MAX_TEXT_LENGTH + 1))

    def test_text_input_rejects_unbounded_or_invalid_responses(self) -> None:
        with self.assertRaises(SamsungTextInputProtocolError):
            SamsungTextInputClient._parse_response("[]")
        with self.assertRaises(SamsungTextInputProtocolError):
            SamsungTextInputClient._parse_response("not-json")

    async def test_media_player_exposes_native_playback_and_app_launch(self) -> None:
        supported = object.__new__(SamsungIPControlMediaPlayer).supported_features
        for feature in (
            MediaPlayerEntityFeature.PLAY,
            MediaPlayerEntityFeature.PAUSE,
            MediaPlayerEntityFeature.STOP,
            MediaPlayerEntityFeature.PLAY_MEDIA,
        ):
            self.assertTrue(supported & feature)

        client = types.SimpleNamespace(
            async_send_navigation_key=AsyncMock(),
            async_launch_app=AsyncMock(),
        )
        coordinator, _ = self._coordinator()
        coordinator.async_apply_command_effect = Mock()
        coordinator.async_request_refresh = AsyncMock()
        player = types.SimpleNamespace(_client=client, coordinator=coordinator)
        await SamsungIPControlMediaPlayer.async_media_play(player)
        await SamsungIPControlMediaPlayer.async_media_pause(player)
        await SamsungIPControlMediaPlayer.async_media_stop(player)
        await SamsungIPControlMediaPlayer.async_play_media(
            player, MediaType.APP, "netflix"
        )
        self.assertEqual(
            client.async_send_navigation_key.await_args_list,
            [
                unittest.mock.call("play"),
                unittest.mock.call("pause"),
                unittest.mock.call("stop"),
            ],
        )
        client.async_launch_app.assert_awaited_once_with("netflix")
        coordinator.async_request_refresh.assert_not_awaited()

        with self.assertRaises(ValueError):
            await SamsungIPControlMediaPlayer.async_play_media(
                player, MediaType.VIDEO, "https://example.invalid/video"
            )

    async def test_remote_commands_publish_without_blocking_on_a_refresh(self) -> None:
        client = types.SimpleNamespace(
            async_power_on=AsyncMock(),
            async_run_remote_command=AsyncMock(),
        )
        coordinator, _ = self._coordinator()
        coordinator.async_apply_command_effect = Mock()
        coordinator.async_request_refresh = AsyncMock()
        remote = types.SimpleNamespace(_client=client, coordinator=coordinator)

        await SamsungIPControlRemote.async_turn_on(remote)
        await SamsungIPControlRemote.async_send_command(remote, ["volume_up"])

        client.async_power_on.assert_awaited_once()
        client.async_run_remote_command.assert_awaited_once_with("volume_up")
        self.assertEqual(
            coordinator.async_apply_command_effect.call_args_list,
            [unittest.mock.call("power_on"), unittest.mock.call("volume_up")],
        )
        coordinator.async_request_refresh.assert_not_awaited()

    @staticmethod
    def _coordinator(**data: object) -> tuple[types.SimpleNamespace, list[dict]]:
        """Build a coordinator stand-in that records everything it publishes."""
        published: list[dict] = []
        stub = types.SimpleNamespace(
            data={
                "power": True,
                "source": "HDMI 1",
                "surface": None,
                "muted": False,
                "volume_level": 0.50,
                **data,
            },
            _surface=None,
            _surface_source=None,
        )

        def publish(payload: dict) -> None:
            # The real coordinator makes each published snapshot the new
            # baseline, so consecutive commands have to compound.
            published.append(payload)
            stub.data = payload

        stub._async_publish = publish
        # Publishing must never go through async_set_updated_data, which resets
        # the refresh timer and would postpone the reconciling poll for as long
        # as someone keeps pressing buttons.
        stub.async_set_updated_data = Mock(
            side_effect=AssertionError("optimistic publish must not reset the poll")
        )
        return stub, published

    def test_publishing_notifies_listeners_without_rescheduling_the_poll(
        self,
    ) -> None:
        """A press every few seconds must not postpone the reconciling poll."""
        stub = types.SimpleNamespace(
            data={"power": False},
            async_update_listeners=Mock(),
            async_set_updated_data=Mock(),
        )
        SamsungIPControlCoordinator._async_publish(stub, {"power": True})

        self.assertEqual(stub.data, {"power": True})
        stub.async_update_listeners.assert_called_once()
        stub.async_set_updated_data.assert_not_called()

    def test_power_on_reports_the_home_surface_without_waiting_for_a_poll(
        self,
    ) -> None:
        """The set always wakes to Home and Samsung never reports it."""
        stub, published = self._coordinator(power=False)
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "power_on")
        self.assertEqual(published[-1]["power"], True)
        self.assertEqual(published[-1]["surface"], "Home")

    def test_input_selection_publishes_the_new_input_immediately(self) -> None:
        stub, published = self._coordinator()
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "hdmi_2")
        self.assertEqual(published[-1]["source"], "HDMI 2")
        self.assertIsNone(published[-1]["surface"])

    def test_application_launch_reports_its_surface_over_the_stale_input(self) -> None:
        stub, published = self._coordinator()
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "app_youtube")
        self.assertEqual(published[-1]["surface"], "YouTube")
        # Samsung keeps reporting the underlying input, so it must not change.
        self.assertEqual(published[-1]["source"], "HDMI 1")

    def test_application_aliases_resolve_to_one_surface_name(self) -> None:
        stub, published = self._coordinator()
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "app_prime_video")
        self.assertEqual(published[-1]["surface"], "Prime Video")

    def test_back_and_exit_fall_back_to_the_polled_input(self) -> None:
        for command in ("back", "exit"):
            stub, published = self._coordinator(surface="Home")
            stub._surface = "Home"
            SamsungIPControlCoordinator.async_apply_command_effect(stub, command)
            self.assertIsNone(published[-1]["surface"], command)

    def test_power_off_clears_the_tracked_surface(self) -> None:
        stub, published = self._coordinator(surface="Netflix")
        stub._surface = "Netflix"
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "power_off")
        self.assertEqual(published[-1]["power"], False)
        self.assertIsNone(published[-1]["surface"])

    def test_volume_and_mute_move_before_the_poll_confirms_them(self) -> None:
        stub, published = self._coordinator()
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "volume_up")
        self.assertAlmostEqual(published[-1]["volume_level"], 0.51)
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "volume_down")
        self.assertAlmostEqual(published[-1]["volume_level"], 0.50)
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "mute")
        self.assertTrue(published[-1]["muted"])

    def test_optimistic_volume_stays_inside_the_reported_range(self) -> None:
        stub, published = self._coordinator(volume_level=1.0)
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "volume_up")
        self.assertEqual(published[-1]["volume_level"], 1.0)

    def test_unknown_state_is_never_invented(self) -> None:
        """A missing reading stays missing rather than becoming a guess."""
        stub, published = self._coordinator(volume_level=None, muted=None)
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "volume_up")
        SamsungIPControlCoordinator.async_apply_command_effect(stub, "mute")
        self.assertIsNone(published[-1]["volume_level"])
        self.assertIsNone(published[-1]["muted"])

    async def test_a_polled_input_change_clears_a_stale_surface(self) -> None:
        """Picking up the remote moves the input without telling the integration."""
        stub = types.SimpleNamespace(
            client=types.SimpleNamespace(
                async_get_power=AsyncMock(return_value=True),
                async_get_states=AsyncMock(
                    return_value={"inputSource": "HDMI2", "volume": 20}
                ),
                async_get_device_information=AsyncMock(return_value={}),
            ),
            device_information={"model": "known"},
            _surface="Netflix",
            _surface_source="HDMI 1",
        )
        data = await SamsungIPControlCoordinator._async_update_data(stub)
        self.assertEqual(data["source"], "HDMI 2")
        self.assertIsNone(data["surface"])

    async def test_a_surface_survives_while_the_polled_input_holds(self) -> None:
        stub = types.SimpleNamespace(
            client=types.SimpleNamespace(
                async_get_power=AsyncMock(return_value=True),
                async_get_states=AsyncMock(
                    return_value={"inputSource": "HDMI1", "volume": 20}
                ),
                async_get_device_information=AsyncMock(return_value={}),
            ),
            device_information={"model": "known"},
            _surface="Netflix",
            _surface_source="HDMI 1",
        )
        data = await SamsungIPControlCoordinator._async_update_data(stub)
        self.assertEqual(data["surface"], "Netflix")

    async def test_home_after_wake_binds_to_the_first_polled_input(self) -> None:
        """The pre-wake state has no source, but the TV still wakes to Home."""
        stub = types.SimpleNamespace(
            client=types.SimpleNamespace(
                async_get_power=AsyncMock(return_value=True),
                async_get_states=AsyncMock(
                    return_value={"inputSource": "HDMI3", "volume": 20}
                ),
                async_get_device_information=AsyncMock(return_value={}),
            ),
            device_information={"model": "known"},
            _surface="Home",
            _surface_source=None,
        )
        data = await SamsungIPControlCoordinator._async_update_data(stub)
        self.assertEqual(data["surface"], "Home")
        self.assertEqual(stub._surface_source, "HDMI 3")

    async def test_setup_without_certificate_pin_starts_reauthentication(self) -> None:
        entry = types.SimpleNamespace(data={})
        with self.assertRaises(ConfigEntryAuthFailed):
            await async_setup_entry(types.SimpleNamespace(), entry)

    async def test_diagnostics_redact_private_connection_data(self) -> None:
        private_values = {
            "name": "Private TV Name",
            CONF_HOST: "192.0.2.1",
            CONF_MAC: "00:00:5E:00:53:01",
            CONF_TOKEN: "token-value",
            CONF_CERTIFICATE_FINGERPRINT: "A" * 64,
            CONF_ENTITY_IDENTITY: "private-entity-identity",
            CONF_SERIAL_HASH: "private-serial-hash",
        }
        coordinator = types.SimpleNamespace(
            data={"power": True, "speaker": "Private Bluetooth Speaker"},
            device_information={
                "model": "model",
                "firmware": "firmware",
                "serial": "private-serial",
            },
        )
        entry = types.SimpleNamespace(
            data=private_values,
            options={
                CONF_TEXT_INPUT_TOKEN: "separate-private-text-token",
                CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT: "B" * 64,
            },
            runtime_data=types.SimpleNamespace(coordinator=coordinator),
        )

        diagnostics = await async_get_config_entry_diagnostics(
            types.SimpleNamespace(), entry
        )
        serialized = json.dumps(diagnostics)
        for private_value in (
            *private_values.values(),
            "separate-private-text-token",
            "B" * 64,
            "private-serial",
            "Private Bluetooth Speaker",
        ):
            self.assertNotIn(private_value, serialized)
        self.assertIn("model", serialized)
        self.assertIn("firmware", serialized)

    async def test_verified_legacy_unique_id_migrates_to_serial(self) -> None:
        entry = types.SimpleNamespace(
            entry_id="entry-one",
            unique_id="192.0.2.1",
            data={CONF_HOST: "192.0.2.1", CONF_MAC: ""},
        )
        config_entries = FakeConfigEntries([entry])
        flow = types.SimpleNamespace(
            hass=types.SimpleNamespace(config_entries=config_entries)
        )

        identity_updates = SamsungIPControlConfigFlow._verified_identity_updates(
            flow, entry, "verified-serial"
        )
        self.assertEqual(
            identity_updates,
            {
                CONF_ENTITY_IDENTITY: "192.0.2.1",
                CONF_SERIAL_HASH: _serial_hash("verified-serial"),
            },
        )
        self.assertEqual(entry.unique_id, "192.0.2.1")

    async def test_unrelated_unique_id_is_rejected(self) -> None:
        entry = types.SimpleNamespace(
            entry_id="entry-one",
            unique_id="different-device",
            data={CONF_HOST: "192.0.2.1", CONF_MAC: ""},
        )
        config_entries = FakeConfigEntries([entry])
        flow = types.SimpleNamespace(
            hass=types.SimpleNamespace(config_entries=config_entries)
        )

        identity_updates = SamsungIPControlConfigFlow._verified_identity_updates(
            flow, entry, "verified-serial"
        )
        self.assertIsNone(identity_updates)

    async def test_serial_hash_mismatch_is_rejected(self) -> None:
        entry = types.SimpleNamespace(
            entry_id="entry-one",
            unique_id="verified-serial",
            data={
                CONF_HOST: "192.0.2.1",
                CONF_MAC: "",
                CONF_SERIAL_HASH: _serial_hash("different-serial"),
            },
        )
        config_entries = FakeConfigEntries([entry])
        flow = types.SimpleNamespace(
            hass=types.SimpleNamespace(config_entries=config_entries)
        )

        identity_updates = SamsungIPControlConfigFlow._verified_identity_updates(
            flow, entry, "verified-serial"
        )
        self.assertIsNone(identity_updates)

    async def test_serial_already_owned_by_another_entry_is_rejected(self) -> None:
        entry = types.SimpleNamespace(
            entry_id="entry-one",
            unique_id="192.0.2.1",
            data={CONF_HOST: "192.0.2.1", CONF_MAC: ""},
        )
        other_entry = types.SimpleNamespace(
            entry_id="entry-two",
            unique_id="verified-serial",
            data={CONF_HOST: "192.0.2.2", CONF_MAC: ""},
        )
        config_entries = FakeConfigEntries([entry, other_entry])
        flow = types.SimpleNamespace(
            hass=types.SimpleNamespace(config_entries=config_entries)
        )

        identity_updates = SamsungIPControlConfigFlow._verified_identity_updates(
            flow, entry, "verified-serial"
        )
        self.assertIsNone(identity_updates)


if __name__ == "__main__":
    unittest.main()
