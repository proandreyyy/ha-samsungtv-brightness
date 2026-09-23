# Brightness in Apple Home

This integration was extended so its TV can act like a real Apple Home remote *and* expose backlight brightness, which needs two separate HomeKit accessories because of a hard limit in Apple's own spec.

## Why one accessory cannot do both

Home Assistant exposes a `media_player` with `device_class: tv` as HomeKit's `Television` service, which is what puts a TV under **Remotes** in the Home app and Control Center, with power, input selection, a D-pad, and a few playback buttons. `Television` has no brightness characteristic at all; the only slider HomeKit's Lightbulb service, which is a different accessory type entirely.

So getting both means:

- The existing `media_player`/`remote` pair for the actual remote.
- The new `light.<name>_backlight` entity (this fork) for a real, draggable brightness slider, added to Apple Home as its own tile.

## The `media_player` needs its own accessory

A `media_player` with `device_class: tv` must be exposed through a HomeKit Bridge config entry in **accessory** mode (Settings > Devices & services > Add integration > HomeKit Bridge > HomeKit mode: `accessory`), containing only that one entity. Home Assistant's own setup screen states this plainly: "Accessory mode is required for media players with the TV or RECEIVER device class to function properly." Putting it in a shared `bridge`-mode entry alongside other entities produces a Television accessory that partially works (power, input) but not the full remote screen. `light.<name>_backlight` and `remote.<name>_remote` have no such restriction and can live in an ordinary bridge-mode entry.

After adding it, the TV accessory can take a while to appear in Control Center's own Remote-picker sheet even though it already shows correctly inside the Home app itself under **Remotes**/**Speakers & TVs**; a single iPhone restart reliably clears that cache.

## Two extra buttons on the remote

HomeKit's Television `RemoteKey` characteristic — the D-pad and the row of buttons under it — is a fixed set: arrows, `select`, `back`, `exit`, `information`, `play_pause`, `rewind`, `fast_forward`, `next_track`, `previous_track`. Volume is a separate characteristic (`TelevisionSpeaker`) that Home Assistant wires directly to `volume_up`/`volume_down`; the two are structurally independent, so remapping one never touches the other.

**Which buttons Apple actually draws is not up to the accessory.** The public HomeKit Accessory Protocol only lets an accessory receive `RemoteKey` presses from a fixed enum; which of them get an on-screen icon, and where, is decided entirely by iOS. Confirmed on a real remote screen for a generic third-party TV accessory: only arrows, Select, Play/Pause, Back, and Info are ever shown in the idle view. `rewind` and `fast_forward` only get icons during an active "Now Playing" session — this integration's `media_player` never reports `playing` (only on/off), so those two are permanently unreachable here despite being valid `RemoteKey` values. Apple TV's own remote shows extra transport icons (skip 10s, captions), but that is a private integration between iOS and Apple TV hardware, not anything exposed through HomeKit to third-party accessories — there is no way to add custom icons or reproduce it. Use `arrow_left`/`arrow_right` instead of `rewind`/`fast_forward`; they are always visible, at the cost of losing horizontal D-pad navigation on this remote (up/down, Select, Play/Pause, and Back are left alone).

An earlier version of this document described remapping a `RemoteKey` button directly through `entity_config: media_player.X: remote: {remote_id, key_map}` under the `homekit:` YAML key. That option does not exist in current Home Assistant (confirmed against `2026.9.3`: `remote` is rejected as an invalid `entity_config` key, and failing to set up `homekit` this way also breaks any other integration that happens to declare it as a dependency, such as `xiaomi_miot`). Do not add that block.

What current Home Assistant actually does: any `RemoteKey` press without a built-in meaning (that is, anything but `play_pause`) fires the plain event `homekit_tv_remote_key_pressed`, with `key_name` and `entity_id` in the event data. Catch it with an ordinary automation instead of touching `configuration.yaml`:

```yaml
triggers:
  - trigger: event
    event_type: homekit_tv_remote_key_pressed
    event_data:
      key_name: arrow_left
      entity_id: media_player.samsung_tv
conditions: []
actions:
  - action: remote.send_command
    target:
      entity_id: remote.samsung_tv_remote
    data:
      command: brightness_down
mode: single
```

Add one such automation for `arrow_left` → `brightness_down` and a second for `arrow_right` → `brightness_up`. Build them in **Settings > Automations & scenes > Create automation**, or add the equivalent YAML directly to `automations.yaml` (safer than `configuration.yaml`: a mistake there fails just that one automation, not the whole `homekit` integration). `remote.send_command` with `brightness_down`/`brightness_up` is recognized by this fork's `async_run_remote_command` and routed to `backlightControl` instead of a real remote key. `up`, `down`, Select, Play/Pause, and Back are untouched and keep working normally, as does the separate volume rocker.

Each press snaps the backlight to the next multiple of 10 (0, 10, 20, ..., 50) in that direction rather than adding a raw ±10 to wherever it currently sits — see [COMMANDS.md](COMMANDS.md#brightness-undocumented-by-samsung). HomeKit's remote screen has no drag gesture, so a real continuously-variable slider still needs the separate light entity below.

## The brightness slider

Add `light.<name>_backlight` to Apple Home like any other accessory (or let the HomeKit Bridge add it automatically once the integration is installed). It shows up as a dimmable, colorless bulb:

- Dragging its slider maps Home's 0-255 brightness scale to the TV's native 0-50 backlight range.
- Turning it "off" sets backlight to 0; turning it back "on" restores the last non-zero level. The picture itself never turns off from this tile — only the backlight does.

## Caveats

- `backlightControl` is not in Samsung's published command sheets; see [COMMANDS.md](COMMANDS.md#brightness-undocumented-by-samsung) for what verifies it.
- Repurposing the volume rocker itself (instead of two `RemoteKey` buttons) was considered and rejected: Siri and the phone's physical volume buttons would keep saying "volume" while actually moving brightness, and you would lose real TV volume from this remote. The `RemoteKey` buttons above don't have that conflict.
- A new or edited automation is picked up without restarting Home Assistant; adding or removing an entity from a HomeKit Bridge config entry is not — reload that config entry (or restart) afterward.
- A bare backlight write is accepted but the panel then fades to it over 10-15 seconds instead of snapping there; see [ARCHITECTURE.md](ARCHITECTURE.md#the-neighbor-value-nudge) for why every write is preceded by a throwaway neighboring value.
