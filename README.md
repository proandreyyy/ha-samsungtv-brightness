# Samsung TV IP Control for Home Assistant

A local Home Assistant custom integration for Samsung TVs that expose Samsung's HTTPS JSON-RPC Consumer IP Control service on port `1516`. It provides direct TV control, exact HDMI selection, a focused remote card, and optional Logitech Harmony and Samsung text-input support.

I created this integration for my own living-room setup after needing reliable local control that matched the way I use Home Assistant and Harmony. That personal need grew into the integration shared here for owners of compatible Samsung TVs.

## When this integration is useful

Home Assistant's built-in [Samsung Smart TV integration](https://www.home-assistant.io/integrations/samsungtv/) supports a broad range of Samsung TVs and covers common power, volume, source, playback, remote, discovery, and diagnostic features. It remains the best starting point for most Samsung TV installations.

Samsung TV IP Control focuses on TVs with Consumer IP Control available on port `1516`. Choose it when the setup needs one or more of these capabilities:

- Discrete HDMI 1 through HDMI 4 selection.
- Consumer IP Control's explicit power, mute, state, application, and remote-key methods.
- SHA-256 pinning of the TV's self-signed certificate before its access token is transmitted.
- Optional local text entry through a separately paired and pinned connection.
- The included Home Assistant remote card.
- A bounded Harmony Elite and Emulated Roku control path.

The integration uses the independent `samsung_ip_control` domain and leaves Home Assistant's built-in `samsungtv` integration intact. Loading both integrations can create overlapping controls for the same TV, so select one primary control path after testing.

## Highlights

- UI-based setup with stable TV identity, reconfiguration, and token reauthentication.
- Local polling for power, volume, mute, HDMI source, picture mode, sound mode, and speaker state.
- Immediate state updates after successful commands, followed by regular polling for reconciliation.
- A `remote` entity with 54 fixed commands covering navigation, playback, digits, color and channel keys, direct applications, discrete power, exact HDMI selection, volume, mute, and two brightness step commands.
- A `light` entity exposing backlight brightness as a real, draggable slider in Apple Home, plus two remappable remote buttons for a physical ±10 shortcut. See [HOMEKIT_BRIGHTNESS.md](docs/HOMEKIT_BRIGHTNESS.md).
- Native media-player play, pause, stop, and allowlisted application launch.
- A responsive first-party remote card with 39 daily controls, four applications, live state, Number pad, and optional text entry.
- Privacy-redacted diagnostics and bounded protocol responses.
- Optional Wake-on-LAN fallback, Harmony bridge, native-card fallback, and AI-assisted setup guide.

## Compatibility

The primary control path requires Samsung's local HTTPS JSON-RPC Consumer IP Control service on TCP port `1516`. TVs limited to Samsung's WebSocket remote API are outside this integration's compatibility boundary.

The current release supports Home Assistant `2026.8.0` or newer and was validated with:

- Home Assistant `2026.8.2` in Home Assistant Container.
- Samsung model identifier `25_RSM_QD` with firmware `T-RSMFDEUC-0090-1296.8`.
- Local IP Remote enabled on port `1516`.
- Optional secure WebSocket text input on port `8002`.
- Logitech Harmony Elite and Hub through Home Assistant Emulated Roku.

Model, firmware, region, installed applications, and active TV screen can affect individual commands. Review the [tested hardware and per-command results](docs/COMPATIBILITY.md) before installation.

## Installation

### HACS custom repository

1. Create a current Home Assistant backup.
2. In HACS, open **Custom repositories**.
3. Add `https://github.com/anjulahettige/home-assistant-samsung-tv-ip-control` with category **Integration**.
4. Install **Samsung TV IP Control**.
5. Restart Home Assistant.
6. Add **Samsung TV IP Control** from **Settings > Devices & services**.

HACS installs the integration under `custom_components` and provides future update delivery. The integration's runtime control path remains local.

### Manual installation

1. Download the current [`v1.1.0` release](https://github.com/anjulahettige/home-assistant-samsung-tv-ip-control/releases/tag/v1.1.0).
2. Copy only `custom_components/samsung_ip_control` into the Home Assistant configuration directory under `custom_components`.
3. Run the configuration check supported by the Home Assistant installation type.
4. Restart Home Assistant.
5. Add **Samsung TV IP Control** from **Settings > Devices & services**.

Installation-type details, updates, and removal instructions are in [docs/HOME_ASSISTANT_SETUP.md](docs/HOME_ASSISTANT_SETUP.md).

## Pair the TV

1. Give the TV a stable DHCP reservation or local DNS address.
2. Enable the TV's IP Remote or IP Control setting.
3. Turn the TV on, close Samsung Home, and display an HDMI picture.
4. Add the integration and enter a display name, the TV address, and port `1516`.
5. Add the wired MAC address only when Wake-on-LAN fallback is wanted.
6. Accept the local IP Remote authorization prompt on the physical TV.

Complete first pairing on a trusted local network while observing the expected TV prompt. The integration records the TV certificate fingerprint before requesting its access token and stores the token in the Home Assistant config entry.

## Optional features

### First-party remote card

The included `custom:samsung-ip-remote-card` provides a focused daily remote with power, navigation, volume, channel, playback, HDMI, YouTube, Netflix, Prime Video, Browser, Number pad, and optional Samsung system text. It uses Home Assistant theme variables and has no third-party frontend dependency.

Follow the [dashboard setup instructions](examples/dashboards/README.md). A [native-card fallback](examples/dashboards/samsung-tv-remote-native.yaml) is included for installations that prohibit custom frontend resources.

### Local text input

Compatible TVs can pair a separate secure WebSocket IME connection, normally on port `8002`. Samsung system fields worked on the tested TV; third-party application support varies. The tested YouTube application ignored both this integration and SmartThings text.

The Developer Tools `samsung_ip_control.send_text` action can appear in Home Assistant events and traces, so use it only for non-sensitive text. The first-party card uses a separate authenticated no-store endpoint. Sensitive entry through the card requires HTTPS access to Home Assistant and trusted runtime devices. Read the [text-input security boundary](SECURITY.md#optional-text-input-boundary) before enabling it.

### Logitech Harmony

The optional Harmony bridge uses Home Assistant's Emulated Roku integration to carry a fixed set of TV commands. Harmony retains source-device control and normal activity input selection, while Home Assistant handles discrete Samsung IP power and the configured TV key map.

Start with [docs/HARMONY_SETUP.md](docs/HARMONY_SETUP.md) and [the example automation](examples/automations/harmony_samsung_ip_control.yaml).

### AI-assisted setup

The optional [AI-assisted setup guide](docs/AI_ASSISTED_SETUP.md) defines safe filesystem, browser, Home Assistant MCP, and physical-device boundaries. Compatible clients can also load the project skill from `.claude/skills/set-up-samsung-tv-ip-control`.

## Security

The integration enforces TLS 1.2 or newer, pins the TV certificate before authenticated requests, rejects unknown commands, bounds response and text sizes, and redacts private connection data from diagnostics. Pairing uses trust on first use, so the first authorization should happen on a trusted network with the expected TV physically visible.

Home Assistant's Emulated Roku listener is an unauthenticated local-network API. Keep it inside a trusted network boundary and apply network-level restrictions when Harmony is enabled. Read [SECURITY.md](SECURITY.md) for the complete security model and vulnerability-reporting instructions.

## Documentation

| Goal | Documentation |
| --- | --- |
| Install, pair, update, or remove | [Home Assistant setup](docs/HOME_ASSISTANT_SETUP.md) |
| Review commands, applications, and text input | [Command reference](docs/COMMANDS.md) |
| Check model and firmware evidence | [Compatibility](docs/COMPATIBILITY.md) |
| Configure Harmony | [Harmony setup](docs/HARMONY_SETUP.md) and [button map](docs/BUTTON_MAP.md) |
| Add a dashboard | [Dashboard examples](examples/dashboards/README.md) |
| Add brightness to Apple Home | [HomeKit brightness](docs/HOMEKIT_BRIGHTNESS.md) |
| Troubleshoot a problem | [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Understand the implementation | [Architecture](docs/ARCHITECTURE.md) |
| Develop or verify changes | [Testing and acceptance](docs/TESTING.md) and [contributing](CONTRIBUTING.md) |
| Review dependencies or AI tooling | [Dependencies](docs/DEPENDENCIES.md) and [AI-assisted setup](docs/AI_ASSISTED_SETUP.md) |

## Project status

Version [`1.1.0`](https://github.com/anjulahettige/home-assistant-samsung-tv-ip-control/releases/tag/v1.1.0) is the current release. All 52 allowlisted commands were exercised on the tested setup, with API acceptance and visible TV behavior recorded separately. Wider model and firmware reports are welcome through the repository's compatibility issue form.

This fork adds two more commands, `brightness_up` and `brightness_down`, plus a `light.<name>_backlight` entity, after that hardware run. They use `backlightControl`, a method Samsung does not publish; see [Brightness](docs/COMPATIBILITY.md#brightness-backlightcontrol) for what verifies it and why it is not yet part of the run above.

## License

Samsung TV IP Control is open-source software licensed under the [MIT License](LICENSE).
