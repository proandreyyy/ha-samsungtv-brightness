# Compatibility and tested hardware

## Protocol requirement

The primary integration requires an HTTPS JSON-RPC service on TCP port `1516` and the methods used in `client.py`. A Samsung TV that only supports the WebSocket remote API cannot use this integration because pairing always begins through Consumer IP Control.

The TV must return a non-empty `serialNumber` from `getDeviceInformation`. The integration uses that value as the stable Home Assistant config-entry unique ID and redacts it from diagnostics.

The tested TV serializes JSON-RPC response identifiers as strings. The client therefore sends monotonically increasing decimal-string identifiers and requires an exact response match. This preserves response correlation without accepting loose numeric/string coercion.

The integration uses these methods:

- `createAccessToken`
- `powerControl`
- `getTVStates`
- `getDeviceInformation`
- `volumeUpDnControl`
- `channelUpDnControl`
- `muteControl`
- `inputSourceControl`
- `remoteKeyControl`
- `directAccessControl`

Optional text input has a second compatibility boundary. The TV must expose the secure `samsung.remote.control` WebSocket endpoint, normally on TCP port `8002`, advertise IME synchronization, complete its own authorization prompt, and accept these message types:

- `SendInputString`
- `SendInputEnd` when `submit` is requested
- `ms.remote.imeStart`, `ms.remote.imeUpdate`, and `ms.remote.imeEnd` lifecycle events

The integration independently pins this endpoint's TLS certificate, stores its separate token in config-entry options, reuses a session for consecutive complete-value snapshots, and closes it after 30 idle seconds. An empty snapshot clears the field. The tested TV required the snapshot flow without `custom.remote.textReceived`; the maintained `samsungtvws` library notes that some other TVs require that compatibility broadcast before first input. Text support therefore has both a TV-model lifecycle boundary and an application boundary.

## Samsung model-year boundary

Samsung's official [Consumer IP Control worksheet](https://image-us.samsung.com/SamsungUS/samsungbusiness/tv-ci-resources/Samsung-IP-Control.pdf) says the protocol is generally similar across model years and identifies a one-time port-address change in 2020. Samsung therefore describes two basic compatibility groups:

- 2019 and earlier.
- 2020 and later.

The worksheet does not map either group to this project's tested port `1516`. Port reachability, pairing, device-information output, and every command must be verified for each reported model. The current evidence covers one TV only and cannot establish support for either whole group.

## Physically tested matrix

| Component | Tested value | Result |
| --- | --- | --- |
| Home Assistant | `2026.8.2` | Pass |
| Installation | Home Assistant Container with host networking | Pass |
| Consumer IP command surface | 52 allowlisted commands | API and physical results recorded separately below |
| Samsung model identifier | `25_RSM_QD` | Pass |
| Samsung firmware | `T-RSMFDEUC-0090-1296.8` | Pass |
| Samsung endpoint | Local HTTPS JSON-RPC, port `1516` | Pass |
| Optional Samsung text endpoint | Secure local WebSocket, port `8002` | Pairing, Samsung Settings text synchronization, clearing, and mobile composition passed; idle reconnect and `submit` remain unconfirmed |
| Harmony remote | Logitech Harmony Elite | Pass |
| Harmony Hub firmware | `4.15.600` | Pass |
| Harmony carrier | Home Assistant Emulated Roku discovered as `Roku 4` | Pass |

The tested Home Assistant instance ran on Unraid. The integration has no Unraid dependency.

## Acceptance summary

All 52 allowlisted commands were invoked on the tested TV on 2026-08-22. Power, volume, mute, discrete HDMI selection, navigation, playback keys, digits, feature keys, channel keys, Browser, Netflix, Prime Video, and YouTube received successful API responses. The starting power, HDMI, volume, mute, and Harmony activity were restored after the run.

API acceptance and visible TV behavior are recorded separately because screen-dependent keys and applications can accept a command without performing a visible action. Play, Pause, Fast Forward, Rewind, Number pad input, Netflix launch, and YouTube launch received physical confirmation. YouTube accepted Stop while continuing playback. Vudu, Pandora, and Hulu were unavailable on the tested setup. Toggle wake from off remains unconfirmed, so automations should use discrete power commands.

Optional text input paired separately and synchronized complete values, replacement, mobile composition, and clearing in Samsung Settings. YouTube ignored both the integration and SmartThings text. Idle reconnect and `submit` behavior remain unconfirmed.

### Per-command acceptance for the tested TV

| Commands | Classification | Evidence |
| --- | --- | --- |
| `power_on`, `power_off` | Live state pass | The media player changed off and on and reconciled after wake. |
| `power_toggle` | Pending for wake | Toggle off was observed after a delay. Toggle wake from off was not independently observed. |
| `volume_up`, `volume_down`, `mute` | Live state pass | Volume moved 10% → 11% → 10%; mute moved false → true → false. |
| `hdmi_1` through `hdmi_4` | Live state pass | Each discrete source reconciled to the requested input. |
| `up`, `down`, `left`, `right`, `menu`, `home`, `enter`, `back`, `exit` | API pass | Every request succeeded; `home` also reported the Home surface. |
| `play`, `pause`, `fast_forward`, `rewind` | Physical pass in YouTube | The tested app visibly performed each action. |
| `stop` | API-only pass in YouTube | Accepted twice; the video continued. |
| `digit_0` through `digit_9` | API pass; Number pad physically passed | Every digit was accepted; Number pad entry has prior physical confirmation in YouTube. |
| `caption`, `dash`, `red`, `green`, `yellow`, `blue`, `ambient`, `multiview` | API pass | Every request succeeded; visible behavior depends on the active screen and model. |
| `channel_up`, `channel_down` | API pass | Both requests succeeded; no tuner channel was active for visible confirmation. |
| `app_browser`, `app_amazon` | Live state pass | Each request succeeded and reported Browser or Prime Video as the integration surface. |
| `app_netflix`, `app_youtube` | Physical pass | Each app has visible launch confirmation; both also passed the current API run. |
| `app_vudu`, `app_vudu_alt`, `app_pandora`, `app_hulu` | Unsupported on tested setup | The installed-app or regional route was unavailable, or the TV returned `-32002`. |

## Brightness (`backlightControl`)

`brightness_up` and `brightness_down` were added after the 2026-08-22 run recorded above and are **not** part of it. `backlightControl` is absent from Samsung's published Consumer IP command sheets; its only verification is a sibling project (`tvolve`) reading and writing it against a physical Samsung QN90B (`QE65QN90BATXSQ`) over the same port-`1516` channel. That is a different unit from the `25_RSM_QD` this repository's matrix above covers. Until it is exercised against a TV tracked in this repository's own compatibility log, treat it the way an unreported model would be treated: plausible by protocol similarity, not yet Pass.

## Reporting another model

Open a compatibility issue with the consumer model number, model year, sales region, firmware, Home Assistant version, installation type, reachable Consumer IP control port, and per-command results. Include whether power-on still works after the TV has been off for more than one minute and whether wired or wireless Wake-on-LAN was used. When optional text input was tested, include whether secure port `8002` was reachable, whether a separate authorization prompt appeared, which non-sensitive application field was active, and whether characters and `submit` behaved as expected.

Remove serial numbers, IP addresses, MAC addresses, tokens, certificate material, household names, entered text, and personally identifying entity or device names. A compatibility report should never include a full diagnostic archive unless the reporter has reviewed every field.
