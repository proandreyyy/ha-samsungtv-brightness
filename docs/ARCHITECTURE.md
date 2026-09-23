# Architecture

## Integration path

```text
Home Assistant service call
  -> media_player or remote entity
  -> SamsungIPControlClient
  -> serialized executor job
  -> TLS certificate fingerprint validation
  -> authenticated HTTPS JSON-RPC request
  -> Samsung TV port 1516
```

The client serializes requests with an asynchronous lock. Each action-capable Home Assistant platform limits parallel service calls to one. Home Assistant's event loop stays free while synchronous `http.client` operations run through the executor.

Optional text input follows a separate local path:

```text
samsung_ip_control.send_text
  -> SamsungTextInputClient
  -> independently pinned TLS certificate and token
  -> secure Samsung WebSocket IME on TV port 8002
  -> active on-screen text field
```

The first-party card uses a non-persistent frontend path:

```text
authenticated Home Assistant frontend over HTTPS
  -> POST /api/samsung_ip_control/sensitive_text
  -> entity control-permission check
  -> SamsungTextInputClient
  -> independently pinned WSS connection to TV port 8002
  -> active on-screen text field
```

The text client uses Home Assistant's `aiohttp` runtime, a 40-second physical-pairing timeout, a 10-second command timeout, a 64 KiB message limit, a 20-message handshake bound, a 200-printable-character input limit, and a 30-second idle close. Consecutive updates reuse one serialized WebSocket session. A tracked receiver consumes `imeStart`, `imeUpdate`, and `imeEnd`; it records only lifecycle booleans and discards IME text payloads. It sends no Consumer IP token over the WebSocket path.

## Trust establishment

1. The config flow connects without sending a token.
2. It computes the SHA-256 fingerprint of the TV certificate.
3. It requests a persistent access token after the fingerprint is retained.
4. Every authenticated request connects, validates the peer certificate, and sends the JSON-RPC payload only after the fingerprint matches.
5. A changed certificate raises `SamsungIPControlCertificateError` before credentials leave Home Assistant.

The TV uses a self-signed certificate, so public certificate-authority validation is unavailable. Pinning makes the initial local pairing decision persistent.

Initial pairing is trust on first use. The user completes it on a trusted LAN while confirming the expected prompt on the physical TV. A later certificate mismatch blocks before token transmission.

Enabling text input creates a second trust decision. The options flow pins the secure WebSocket certificate before requesting its separate local remote token. Every later text connection supplies that token only while enforcing the pinned WebSocket fingerprint. Disabling text input removes both optional credential values from config-entry options and leaves the Consumer IP pairing unchanged.

## Device identity

After pairing, the integration reads the TV serial and uses it as the Home Assistant config-entry unique ID. Entity and device-registry identifiers use a SHA-256 digest of the serial, which stays stable across reinstallation without placing the plaintext serial in config-entry data. The digest and serial are redacted from diagnostics. Reconfiguration validates the pinned certificate, token, and serial digest before accepting a new address, port, or Wake-on-LAN MAC. A verified legacy identity migration changes the config-entry unique ID atomically with the flow's data update.

Some firmware has no `getDeviceInformation` at all — observed as JSON-RPC `-32601` on a Samsung QN90B, with every other Consumer IP Control method the integration uses still working. `_device_information_or_empty` catches that (and any other failure of this one call) and returns an empty record instead of failing pairing, reauthentication, or reconfiguration outright. Pairing, reauthentication, and reconfiguration all then fall back to the configured MAC, then the host, in that order, computing identity as `serial or mac or host.casefold()`. Serial is still always attempted and always preferred when the TV supports it; the fallback exists only for TVs that never can. `_verified_identity_updates` does not need to know which case it is — it treats the resolved identity the same way whether it came from a real serial or a fallback.

## Protocol limits

Every response must use JSON-RPC `2.0` and match the request ID. Response bodies are limited to 64 KiB. Exceptions omit device-provided message text so a compromised endpoint cannot inject arbitrary content into normal integration errors.

## Entities

### Media player

The media player exposes power, volume steps, explicit mute, HDMI source selection, play, pause, stop, allowlisted app launching, and polled TV state. App launch uses the native `play_media` action with media type `app`.

### Remote

The remote exposes a fixed 54-command allowlist: 52 derived from Samsung's published Consumer IP command sheets, covering all published remote-key values, the older Ambient key, channel buttons, fixed direct-access apps, and the established discrete controls, plus two undocumented `brightness_up`/`brightness_down` step commands (see [COMMANDS.md](COMMANDS.md#brightness-undocumented-by-samsung)). Unknown commands, arbitrary app names, and unsupported media types are rejected before any request reaches the TV.

When independently paired, the remote also accepts the integration-specific `samsung_ip_control.send_text` entity action. Text is outside the 54-command Consumer IP allowlist because Samsung publishes no text method for port `1516`. The action uses port `8002` and sets one complete field snapshot of up to 200 printable characters. An empty snapshot clears the active field. The action can optionally end the sequence. Keep secrets out of this action because Home Assistant service data and automation traces can retain full and partial values.

The first-party card calls `POST /api/samsung_ip_control/sensitive_text` through Home Assistant's authenticated frontend API. The handler rejects missing or oversized bodies before JSON parsing, checks entity-control permission, resolves only a `samsung_ip_control` entity and config entry, validates at most 200 printable characters, sends through the existing pinned text client, and returns only a success flag or generic error. It marks every response `Cache-Control: no-store`. It does not call `hass.services`, fire `EVENT_CALL_SERVICE`, create an automation or script trace, update entity state, echo the entered text, or log text. HTTPS is required between browser and Home Assistant for secrets; the current value still exists transiently in trusted runtime memory and on the TV.

The Harmony automation retains a narrower 15-command boundary. Expanding the Home Assistant entity does not implicitly expose new controls through Emulated Roku.

Diagnostics redact both tokens, both certificate fingerprints, the serial, TV address, MAC, user-chosen name, and derived identity fields.

### Backlight light

`light.<name>_backlight` exposes `backlightControl` as a brightness-only, colorless `Lightbulb`. It exists because HomeKit's `Television` service has no brightness characteristic at all, so a real, draggable slider in Apple Home has to be a separate accessory; see [HOMEKIT_BRIGHTNESS.md](HOMEKIT_BRIGHTNESS.md). Home Assistant's 0-255 brightness scale is linearly mapped to the TV's native 0-50 backlight range. Turning the light off writes backlight 0 and remembers the prior level; turning it back on without an explicit brightness restores that level. The coordinator polls `backlightControl` alongside the other state methods whenever the TV is powered on. Every write goes through the client's `async_queue_backlight`, not a direct `async_set_backlight`, for the coalescing reason below.

#### Coalesced writes

Each request opens its own TLS connection (see [Protocol limits](#protocol-limits)), so it has a real cost, and a fast slider drag in Apple Home can fire dozens of brightness writes in a couple of seconds. Working through every intermediate value strictly in arrival order made a full-range drag look stuck near its starting point for several seconds — the true final value was still queued behind many stale ones. `async_queue_backlight` keeps only the most recently requested target: a write already in flight finishes normally, and the writer then immediately sends whatever the latest target has become, dropping anything superseded in between. This is the same coalescing scheme the sibling `tvolve` iOS project already uses for its own slider. It is intentionally fire-and-forget from the entity's perspective — `async_turn_on`/`async_turn_off` publish the optimistic target immediately and return, and a write failure is logged rather than raised, since by the time a queued write finishes there is often already a newer target superseding it.

## First-party remote card

The integration declares Home Assistant's built-in `http` component as a manifest dependency and serves one static JavaScript module from `/samsung_ip_control_static/samsung-ip-remote-card.js`. The file is public like other Home Assistant frontend resources and contains only fixed UI code. It contains no configuration, token, address, device identity, or entered text.

Users register the module once through Home Assistant's dashboard Resources UI. The card accepts only a media-player entity ID, a remote entity ID, and an optional display name. Its buttons are compiled from a focused 39-command subset of the fixed 54-command backend allowlist and cannot submit arbitrary command names. Advanced users can call the omitted allowlisted commands through standard Home Assistant actions. The card calls those actions through the authenticated frontend session.

The text field is transient browser state. The card does not create a helper, write local or session storage, place text in an entity state, log the value, or retain a last-synchronized plaintext property. Every browser `input` event queues the complete current value through the private no-store API endpoint; Backspace, selection replacement, paste, and clearing need no separate protocol path. A serialized promise chain preserves every edit in order. The card clears its DOM value on blur and unload and has no Send, Finish input, or synchronization toggle. It displays an HTTP warning because sensitive values require HTTPS between the browser and Home Assistant.

## State reporting

The coordinator polls the TV every ten seconds. That interval alone is too slow for a remote, because the TV acts on a button in well under a second, so the integration also publishes what a command is known to have done as soon as the command succeeds. The next poll replaces every published value, so a rejected or ignored command self-corrects within one interval rather than sticking.

Commands deliberately do not request a refresh afterwards. Every TV request is serialized behind one lock, and a poll is two round trips, so forcing a refresh after each command made the next button press wait for both. Publishing the known result locally costs no I/O and needs no poll, and the scheduled interval reconciles.

Publishing also bypasses `async_set_updated_data`, which resets the refresh timer. Going through it meant a press every few seconds postponed the reconciling poll indefinitely, so optimistic values could drift with nothing ever correcting them. The coordinator sets its data and notifies listeners directly, leaving the schedule alone. Availability stays with the poll, because a command cannot vouch for a reading it never took.

Commands publish these values ahead of the poll:

| Command | Published immediately |
| --- | --- |
| `power_on` | Power on, surface `Home` |
| `power_off` | Power off, surface cleared |
| `hdmi_1` to `hdmi_4` | The selected input, surface cleared |
| `home` | Surface `Home` |
| `app_*` | The application's surface name, input unchanged |
| `back`, `exit` | Surface cleared |
| `mute` | The inverted mute state |
| `volume_up`, `volume_down` | One step of Samsung's 0-100 scale |

### Surface tracking

Samsung's `getTVStates` reports only the underlying HDMI input. It keeps reporting that input while Samsung Home or an application owns the screen, so the polled value alone cannot answer what is actually displayed. The set also always wakes to Home, which no reading reflects.

The integration therefore tracks the surface it last commanded and exposes it as the `surface` attribute on the remote entity, alongside the unchanged `source` attribute on the media player. The two answer different questions: `source` is Samsung's authoritative input, `surface` is what the integration knows is on screen.

A tracked surface is recorded together with the input that was current when it was set, and is cleared when:

- The TV reports power off.
- The polled input moves, which means something outside the integration changed it.
- `back`, `exit`, an HDMI selection, or power off is commanded.

When no surface is tracked, consumers fall back to the polled input. `surface` is a convenience for display, never a control input; HDMI selection and automations continue to use `source`.

## Power on

A set in standby commonly answers `powerControl` `powerOn` with error `-32002`, or drops the connection, while still acting on the request. Treating either as a failure reported an error for a command that had worked.

`power_on` therefore does two things and then returns:

1. Send `powerControl` `powerOn`.
2. On a transport error or `-32002`, send Wake-on-LAN when a MAC is configured.

Any other error code still fails immediately, so a genuine rejection is not hidden. The call does not wait for the panel to come up; `power_on` publishes power and the `Home` surface locally, and the next poll confirms.

The IP write is always attempted first. Wake-on-LAN does not wake the tested set on its own, so a configured MAC remains a fallback after `powerControl`.

On the tested set, `powerControl` `powerOn` wakes the TV from standby in roughly half a second and the fallback never has to fire. Wake-on-LAN has therefore never been observed to wake it, and the MAC is optional: leave it unset and power-on still works over IP. Configure it only if a TV is confirmed to need it.

Home Assistant's built-in `samsungtv` integration deprecated its own implicit Wake-on-LAN because a silent magic packet is difficult to reason about and directs users to an explicit `wake_on_lan.send_magic_packet` automation. This integration retains its optional fallback as a recovery path for models outside the current test set. Power-on always attempts the Samsung IP write first, and users can leave the MAC address unset when the fallback is unnecessary.

`power_off` sends the discrete state and propagates any rejection. A set that is already off is reachable and answers normally, so there is nothing to absorb.

## HDMI reliability

Exact HDMI selection performs:

1. Read hardware power state.
2. Power on or send Wake-on-LAN when required.
3. Wait four seconds after waking.
4. Send the exact HDMI input.
5. Wait one second.
6. Repeat the same exact input.

This sequence handles the tested TV opening Samsung Home during startup.

## Harmony path

```text
Physical Harmony button
  -> Harmony Hub
  -> Emulated Roku HTTP request
  -> Home Assistant roku_command event
  -> source, type, and key allowlist
  -> remote.send_command
  -> Samsung IP Control
```

Power uses Harmony `current_activity` transitions because the tested Roku power aliases were ambiguous. Input selection remains part of each Harmony activity.
