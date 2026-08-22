# Logitech Harmony setup

## Design

Harmony uses a Home Assistant Emulated Roku as a network key carrier. Home Assistant translates the received `roku_command` events into a dedicated subset of the Samsung remote's fixed command allowlist.

The carrier handles button events. Home Assistant handles discrete Samsung power. Harmony handles each activity's input selection and source-device controls.

## 1. Add Emulated Roku to Home Assistant

Add the built-in **Emulated Roku** integration with:

- Name: `Home Assistant TV Controls`
- Port: `8061`, or another unused fixed port

Verify its device-info endpoint using your Home Assistant hostname and selected port:

```text
http://homeassistant.local:8061/query/device-info
```

Emulated Roku is an unauthenticated LAN listener. Keep the port off public, guest, and untrusted networks. Apply a source-IP-restricted proxy or equivalent network rule when the Home Assistant network contains untrusted clients. The automation source name and key allowlist limit routing and command scope; network policy supplies the sender restriction.

## 2. Add Roku to Harmony

1. In Harmony, scan for Wi-Fi devices.
2. Add the discovered Home Assistant device. The tested setup identifies it as `Roku 4`.
3. Rename it to `Samsung IP Remote` when a clearer device name is wanted.
4. Add this Roku device to every activity that needs Samsung IP commands.

## 3. Set carrier delays

The carrier is an always-ready LAN endpoint. Set its device delays to:

| Setting | Value |
| --- | --- |
| Power On Delay | `0s` |
| Inter-Key Delay | `0ms` |
| Inter-Device Delay | `0ms` |

Increase Inter-Key Delay only when physical testing shows missed, duplicated, or reordered rapid presses.

## 4. Configure activity devices

For every TV activity:

1. Include the real source device.
2. Include the Samsung TV.
3. Include the Roku 4 carrier.
4. Configure the required Samsung input inside the Harmony activity.
5. Keep navigation and playback on the real source device.
6. Assign Samsung controls through [BUTTON_MAP.md](BUTTON_MAP.md).

The integration exposes playback and app commands directly to Home Assistant. They remain outside the included Roku map. Keep playback on the real source device for SHIELD, Xbox, and similar activities. Follow the opt-in procedure in [COMMANDS.md](COMMANDS.md) only when a physical Harmony button produces a distinct Roku event and routing that command to the TV is intentional.

## 5. Add the Home Assistant automation

Copy [the automation example](../examples/automations/harmony_samsung_ip_control.yaml) into your automation configuration or recreate it in the UI.

Replace:

- `remote.harmony_hub` with your Harmony entity.
- `remote.samsung_tv_remote` with your Samsung IP remote entity.
- `SHIELD`, `Samsung`, and `XBOX` with your exact activity names.
- `Home Assistant TV Controls` when your Emulated Roku has another name.

Each managed activity needs one entry trigger with ID `activity_power_on` and one transition-to-PowerOff trigger with ID `activity_power_off`.

## 6. Sync and test

1. Sync the Elite after changing activities or button assignments.
2. Start each activity from the physical remote.
3. Confirm TV power, Harmony input selection, source navigation, TV volume, and mute.
4. Switch directly between active activities and confirm the TV remains on.
5. End each activity and confirm Harmony reaches PowerOff and the TV turns off.
6. Listen for `roku_command` in Home Assistant Developer Tools and verify every assigned key.

## Adding another activity

1. Add the real source, Samsung TV, and Roku carrier in Harmony.
2. Configure the input and source-device buttons in Harmony.
3. Duplicate one `activity_power_on` and one `activity_power_off` trigger with the exact new activity name.
4. Sync Harmony.
5. Run the full physical acceptance sequence.
6. Update the button-map dashboard or local documentation.

## Why Roku power keys are excluded

The tested Harmony implementation emitted the same `PowerOff` event for Roku `PowerOn` and `Sleep`, and starting an activity emitted no reliable Roku key. Exact Harmony activity transitions provide deterministic context for discrete Samsung power commands.
