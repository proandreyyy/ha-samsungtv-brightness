# Commands, playback, applications, and text input

The Home Assistant `remote` entity exposes 52 strictly allowlisted commands. They cover every remote-key value in Samsung's published 2023 Consumer IP Control command sheet, the legacy `ambient` key from Samsung's 2018 sheet, channel buttons, discrete power and HDMI controls, volume and mute, and the sheet's fixed direct-access applications.

Samsung documents these options in its [2023 IP Command List](https://image-us.samsung.com/SamsungUS/samsungbusiness/resources/pdfs/ip-command-list/IP-Command-List_2023.pdf) and [2018 command list](https://image-us.samsung.com/SamsungUS/tv-ci-resources/2018-contact-and-other-resources/TV_IP_CommandList_v1_2_1Pager.pdf). Availability still depends on model, firmware, region, installed applications, current input, and current TV screen.

## Home Assistant interfaces

Use `remote.send_command` for any command in this document:

```yaml
action: remote.send_command
target:
  entity_id: remote.samsung_tv_remote
data:
  command: play
```

The media player also implements Home Assistant's native play, pause, stop, and app media actions. Launch an allowlisted application with:

```yaml
action: media_player.play_media
target:
  entity_id: media_player.samsung_tv
data:
  media_content_type: app
  media_content_id: netflix
```

The media player's `supported_apps` attribute lists the accepted application IDs. Unknown remote commands, application IDs, and media types are rejected before a TV request is sent.

## Navigation and system keys

| Home Assistant command | Samsung remote-key value | Intended control |
| --- | --- | --- |
| `up` | `cursorUp` | Navigate up |
| `down` | `cursorDn` | Navigate down |
| `left` | `cursorLeft` | Navigate left |
| `right` | `cursorRight` | Navigate right |
| `menu` | `menu` | Open the TV menu |
| `home` | `firstScreen` | Open Samsung Home |
| `enter` | `enter` | Select or confirm |
| `back` | `return` | Return to the previous screen |
| `exit` | `exit` | Exit the current screen |
| `power_toggle` | `power` | Toggle power state |
| `caption` | `caption` | Caption control where supported |
| `dash` | `dash` | Channel dash or separator |
| `ambient` | `ambient` | Legacy Ambient Mode key |
| `multiview` | `multiview` | Multi View key on supported TVs |

Prefer `power_on` and `power_off` in automations because they are deterministic. Reserve `power_toggle` for interactive remote layouts.

A set in standby often answers `power_on` with error `-32002` while still waking. The integration absorbs that code and sends Wake-on-LAN as a fallback when a MAC is configured, so an automation is not told a working command failed. The call returns without waiting for the panel; power and the `Home` surface are published locally and the next poll confirms. See [state reporting](ARCHITECTURE.md#state-reporting) for the values each command publishes ahead of the next poll, and for the `surface` attribute that reports Samsung Home and launched applications.

## Playback keys

| Home Assistant command | Samsung remote-key value |
| --- | --- |
| `play` | `play` |
| `pause` | `pause` |
| `stop` | `stop` |
| `fast_forward` | `fastforward` |
| `rewind` | `rewind` |

The native `media_player.media_play`, `media_player.media_pause`, and `media_player.media_stop` actions send the same allowlisted remote keys. The TV can accept a key even when the active application has no matching playback action, so physical behavior must be tested in each application.

## Number and color keys

The commands `digit_0` through `digit_9` map to Samsung's `number0` through `number9` remote-key values. They use Consumer IP Control rather than the optional WebSocket text path. On the tested TV, Number pad digits entered correctly in YouTube even though WebSocket text did not. The commands `red`, `green`, `yellow`, and `blue` map to the corresponding color keys and remain available through `remote.send_command`.

## Channel, volume, input, and power

| Commands | Control path |
| --- | --- |
| `channel_up`, `channel_down` | `channelUpDnControl` |
| `volume_up`, `volume_down` | `volumeUpDnControl` |
| `mute` | Reads the current mute state, then writes the opposite explicit state |
| `hdmi_1` through `hdmi_4` | `inputSourceControl` with a discrete HDMI value |
| `power_on`, `power_off` | `powerControl` with a discrete state |

Channel commands are relevant only while a TV tuner or compatible channel source is active. HDMI selection can fail when the model has no matching connected physical input.

## Direct application access

| Remote command | App media ID | Samsung application name |
| --- | --- | --- |
| `app_browser` | `browser` | `webBrowser` |
| `app_netflix` | `netflix` | `netflix` |
| `app_amazon` | `amazon` | `amazon` |
| `app_vudu` | `vudu` | `VUDU` |
| `app_vudu_alt` | `vudu_alt` | `vudu` |
| `app_pandora` | `pandora` | `pandora` |
| `app_youtube` | `youtube` | `youTube` |
| `app_hulu` | `hulu` | `hulu` |

App launch uses `directAccessControl` with Samsung's `applicationName` parameter. The two Vudu values are retained because Samsung publishes both case variants. `Prime Video`, `Amazon Prime`, and `Amazon Prime Video` are accepted aliases for the `amazon` media ID.

Samsung's 2023 sheet also names a newer First Screen App Control by application name for 2021-forward TVs, but the public sheet does not provide its JSON-RPC method or parameter contract. This integration does not send a guessed method or accept arbitrary application names. A future implementation needs an official contract or a sanitized, repeatable hardware trace before it can safely expand beyond the published direct-access list.

## Optional text input

Samsung's published Consumer IP command sheets contain no text-input method for port `1516`. Compatible Tizen TVs can advertise a separate local WebSocket IME service. This integration exposes that path only after it is independently enabled, certificate-pinned, and authorized through the integration's **Configure** flow. It remains local and uses no SmartThings or cloud API.

Activate a compatible, non-sensitive Samsung system field first, then run:

```yaml
action: samsung_ip_control.send_text
target:
  entity_id: remote.samsung_tv_remote
data:
  text: Samsung TV
  submit: false
```

Each action sets the complete field value with up to 200 printable characters. Send an empty `text` value to clear the active field. Consecutive calls reuse one paired WebSocket session for 30 idle seconds and consume `imeStart`, `imeUpdate`, and `imeEnd` without retaining the TV's text payload. `submit: true` sends Samsung's `SendInputEnd` message; application behavior varies, so test it separately. The action does not navigate to a field or guarantee that an application accepts IME input. On the tested TV, the sequence `h`, `ha`, `h`, and empty visibly performed typing, Backspace-equivalent replacement, and an exact clear in Samsung Settings. YouTube ignored both this action and SmartThings text, confirming that field as application-limited. Treat third-party application keyboards as unsupported until physically proven on the specific model and firmware.

Do not send passwords, access codes, personal data, or other secrets through `samsung_ip_control.send_text`. Home Assistant service-call events, automation YAML, blueprints, traces, backups, and debug material can retain action data.

The first-party card uses a separate authenticated `POST /api/samsung_ip_control/sensitive_text` endpoint for interactive entry. It bypasses Home Assistant services and traces, checks entity-control permission, bounds the request, returns no entered text, marks responses `Cache-Control: no-store`, retains no last-value cache, and clears the visible browser value on blur or unload. Sensitive entry through the card requires an HTTPS Home Assistant page and a trusted browser, device keyboard, Home Assistant host, network, reverse proxy, and TV. The plaintext necessarily exists transiently in those runtime components while being entered and transmitted.

Text entry uses Samsung's local `samsung.remote.control` WebSocket channel with repeated base64 `SendInputString` snapshots, TV IME lifecycle events, and optional `SendInputEnd`. Physical testing showed that the tested TV accepts ordered snapshots without `custom.remote.textReceived`; sending that compatibility broadcast caused later edits to stop following the browser field. The maintained [`samsungtvws` library](https://github.com/xchwarze/samsung-tv-ws-api/blob/master/samsungtvws/remote.py) notes that some TVs require the broadcast before their first text input, so this remains a model-specific compatibility boundary and must be reported if another TV needs that variant. Samsung's official [Keyboard/IME documentation](https://developer.samsung.com/smarttv/develop/guides/user-interaction/keyboardime.html) describes application-side IME behavior but does not define this remote WebSocket contract.

## Harmony and Emulated Roku boundary

The included Harmony automation deliberately keeps its original 13 Roku event keys and 15 Samsung outcomes. Playback and app commands are available through Home Assistant but are not routed from Roku by default.

An advanced user can add a Roku key only after confirming that Harmony emits a distinct `roku_command` event for that physical button. Add the event key and one command from this document to the automation's `tv_command_map`, retain the exact source-name and event-type conditions, and test the physical result. Some Harmony app buttons emit no Roku event, and source-device playback should normally remain assigned to the source device.

## Compatibility reporting

Record API acceptance separately from visible behavior. A successful JSON-RPC response proves that the TV accepted the command. It does not prove that the current application or screen acted on it. Report the model identifier, firmware, region, command, current screen or source, API result, and physical result after removing serial numbers and network identifiers.
