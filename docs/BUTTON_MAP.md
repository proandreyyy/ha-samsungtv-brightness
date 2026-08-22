# Harmony Roku 4 button map

The visible Harmony label can be customized while the underlying device command remains a Roku 4 command.

| Desired control | Assign this Roku 4 command | Home Assistant key | Samsung command |
| --- | --- | --- | --- |
| Up | Direction Up | `Up` | `up` |
| Down | Direction Down | `Down` | `down` |
| Left | Direction Left | `Left` | `left` |
| Right | Direction Right | `Right` | `right` |
| Volume Up | Fast Forward | `Fwd` | `volume_up` |
| Volume Down | Rewind | `Rev` | `volume_down` |
| Mute | Instant Replay | `InstantReplay` | `mute` |
| HDMI 1 | Back | `Back` | `hdmi_1` |
| HDMI 2 | Info | `Info` | `hdmi_2` |
| HDMI 3 | Search | `Search` | `hdmi_3` |
| HDMI 4 | Play | `Play` | `hdmi_4` |
| Home | Home | `Home` | `home` |
| Enter / OK | OK | `Select` | `enter` |

## Tested collisions

| Roku 4 command | Received result | Guidance |
| --- | --- | --- |
| Pause | `Play` | Leave unassigned when Play means HDMI 4 |
| Stop | `Play` | Leave unassigned when Play means HDMI 4 |
| PowerOn | `PowerOff` | Exclude from power automation |
| Sleep | `PowerOff` | Exclude from power automation |
| Exit | `Home` | Duplicate of Home |
| Options variants | `Info` | Collision with HDMI 2 |
| Page Up | `PowerOff` during testing | Exclude |
| Page Down | No event | Unusable in the tested setup |
| Netflix and other app keys | No event | Unusable as tested Roku carriers; launch supported apps directly through Home Assistant |

## Assignment guidance

For a Shield, Xbox, or another source activity, keep navigation and playback assigned to the real source device. Assign volume, mute, and any desired TV-only controls to Roku 4. For a TV-only activity, all supported navigation controls can use Roku 4.

The Samsung remote entity also exposes playback, app, keypad, channel, color, and additional system commands. They are intentionally absent from the default Roku mapping. Follow the evidence and opt-in procedure in [COMMANDS.md](COMMANDS.md) before adding any of them to a local automation.

Activity power uses Harmony activity-state changes and the discrete Samsung `power_on` and `power_off` commands.
