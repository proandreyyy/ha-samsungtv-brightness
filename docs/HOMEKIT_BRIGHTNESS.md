# Brightness in Apple Home

This integration was extended so its TV can act like a real Apple Home remote *and* expose backlight brightness, which needs two separate HomeKit accessories because of a hard limit in Apple's own spec.

## Why one accessory cannot do both

Home Assistant exposes a `media_player` with `device_class: tv` as HomeKit's `Television` service, which is what puts a TV under **Remotes** in the Home app and Control Center, with power, input selection, a D-pad, and a few playback buttons. `Television` has no brightness characteristic at all; the only slider HomeKit's Lightbulb service, which is a different accessory type entirely.

So getting both means:

- The existing `media_player`/`remote` pair for the actual remote.
- The new `light.<name>_backlight` entity (this fork) for a real, draggable brightness slider, added to Apple Home as its own tile.

## Two extra buttons on the remote

HomeKit's Television `RemoteKey` characteristic — the D-pad and the row of buttons under it — is a fixed set: arrows, `select`, `back`, `exit`, `information`, `play_pause`, `rewind`, `fast_forward`, `next_track`, `previous_track`. Volume is a separate characteristic (`TelevisionSpeaker`) that Home Assistant wires directly to `volume_up`/`volume_down`; the two are structurally independent, so remapping one never touches the other.

Home Assistant lets you remap any `RemoteKey` button to an arbitrary command sent to a linked `remote` entity through `remote_id` and `key_map`. Two of those buttons are rarely useful for live TV (`rewind`/`fast_forward`, or use `previous_track`/`next_track` instead) and are good candidates to sacrifice for brightness:

```yaml
homekit:
  entity_config:
    media_player.samsung_tv:
      remote:
        remote_id: remote.samsung_tv_remote
        key_map:
          rewind: brightness_down
          fast_forward: brightness_up
```

Pressing those two buttons in the Apple Home/Control Center remote now calls `remote.send_command` with `brightness_down`/`brightness_up` on `remote.samsung_tv_remote`, which this fork's `async_run_remote_command` recognizes and routes to `backlightControl` instead of a real remote key. The D-pad and volume rocker are untouched and keep working normally.

This gives discrete ±10 steps only — HomeKit's remote screen has no drag gesture, so a real slider still needs the separate light entity below.

## The brightness slider

Add `light.<name>_backlight` to Apple Home like any other accessory (or let the HomeKit Bridge add it automatically once the integration is installed). It shows up as a dimmable, colorless bulb:

- Dragging its slider maps Home's 0-255 brightness scale to the TV's native 0-50 backlight range.
- Turning it "off" sets backlight to 0; turning it back "on" restores the last non-zero level. The picture itself never turns off from this tile — only the backlight does.

## Caveats

- `backlightControl` is not in Samsung's published command sheets; see [COMMANDS.md](COMMANDS.md#brightness-undocumented-by-samsung) for what verifies it.
- Repurposing the volume rocker itself (instead of two `RemoteKey` buttons) was considered and rejected: Siri and the phone's physical volume buttons would keep saying "volume" while actually moving brightness, and you would lose real TV volume from this remote. The `RemoteKey` buttons above don't have that conflict.
- Reconfigure the `homekit:` entry (**Settings > Devices & services > HomeKit Bridge > Configure**, or edit `configuration.yaml` and restart) after adding the `remote:`/`key_map` block; it is not picked up live.
- A bare backlight write is accepted but the panel then fades to it over 10-15 seconds instead of snapping there; see [ARCHITECTURE.md](ARCHITECTURE.md#the-neighbor-value-nudge) for why every write is preceded by a throwaway neighboring value.
