# Home Assistant setup

## Prerequisites

- Home Assistant `2026.8.0` or newer.
- A Samsung TV exposing HTTPS JSON-RPC IP Control on TCP port `1516`.
- IP Remote or IP Control enabled on the TV.
- A stable TV address supplied through DHCP reservation or local DNS.
- Optionally, a wired TV MAC address. Power-on runs over IP and the tested set has never needed the Wake-on-LAN fallback, so supply a MAC only when a TV is confirmed to require it.
- A current Home Assistant backup and an approved restart window.
- A trusted local network and a person at the TV for first pairing.

Read [DEPENDENCIES.md](DEPENDENCIES.md) for installation-type, optional Harmony, browser, and AI dependencies.

## Choose an installation path

### HACS custom repository

1. Create a Home Assistant backup.
2. Open HACS and add `https://github.com/anjulahettige/home-assistant-samsung-tv-ip-control` as a custom repository in the **Integration** category.
3. Install **Samsung TV IP Control**.
4. Restart Home Assistant during the approved maintenance window.

HACS installs the repository under `custom_components` and provides update delivery. The integration's runtime remains local and has no HACS frontend dependency.

### Manual copy

1. Download the current release on a trusted machine.
2. Review the release notes and repository security guidance.
3. Create a Home Assistant backup.
4. Copy only `custom_components/samsung_ip_control` into the active Home Assistant configuration directory.
5. Confirm the resulting path is `/config/custom_components/samsung_ip_control/manifest.json` from Home Assistant's perspective.
6. Keep backups outside `/config/custom_components`. Home Assistant can try to import extra directories under `custom_components` as integrations.
7. Run the configuration check supported by the Home Assistant installation type.
8. Restart Home Assistant during the approved maintenance window.

Home Assistant OS and Supervised users can use a supported file-access add-on. Container and Core users can copy into the host directory mapped or configured as `/config`. Avoid direct edits to `.storage`.

## Pair the TV

1. Turn on the TV.
2. Close Samsung Home and display an HDMI picture.
3. Open **Settings > Devices & services > Add integration**.
4. Select **Samsung TV IP Control**.
5. Enter a display name, the TV address, port `1516`, and the optional wired MAC.
6. Submit the form.
7. Accept the local IP Remote authorization prompt on the physical TV before the pairing timeout.

The config flow connects without a token, records the TV's SHA-256 certificate fingerprint, requests a Samsung access token, reads the TV serial for a stable unique ID, and validates the connection. Entity and device identifiers use a SHA-256 serial digest. Home Assistant stores the token, certificate fingerprint, and redacted identity metadata in the config entry.

The certificate trust is trust on first use. Complete first pairing on a trusted LAN while physically observing the expected TV prompt. A later certificate change blocks token transmission.

Home Assistant creates a media player entity and a remote entity. Entity IDs depend on the chosen device name. The examples use:

```text
media_player.samsung_tv
remote.samsung_tv_remote
```

Replace those IDs in every dashboard and automation example.

The remote entity publishes 54 commands in its `supported_commands` attribute. The media player exposes native play, pause, stop, and allowlisted app-launch actions. A `light` entity exposes backlight brightness. Review [COMMANDS.md](COMMANDS.md) before enabling model-dependent keys or applications, and [HOMEKIT_BRIGHTNESS.md](HOMEKIT_BRIGHTNESS.md) before exposing the TV through HomeKit Bridge.

## Enable optional local text input

Text input uses the TV's separate secure local WebSocket IME service. It does not change the Consumer IP command path and requires no SmartThings account.

1. Confirm the TV is on and supports synchronized IME input.
2. Open **Settings > Devices & services > Samsung TV IP Control**.
3. Select **Configure**.
4. Enable text input and use secure WebSocket port `8002` unless the TV requires another port.
5. Continue to **Pair local text input**.
6. Accept the separate local remote authorization prompt on the physical TV.
7. Confirm the remote entity's `text_input_enabled` attribute is `true`.

This pairing stores a separate token and certificate fingerprint in config-entry options. Use **Configure** again to disable text input or pair it again. Disabling removes the optional text token and fingerprint without changing the Consumer IP pairing.

Activate a non-sensitive Samsung system field, such as a suitable field in Settings, and test `samsung_ip_control.send_text` from **Developer Tools > Actions**. Use the examples in [COMMANDS.md](COMMANDS.md). Each call sets the complete field value, so test a short value, a longer value, the shorter value again to simulate Backspace, and an empty value to clear. Keep `submit` disabled during those checks and test it separately. Never put a secret in the Developer Tools action.

The first-party card sends the same complete-value operation automatically for every ordered keyboard edit and has no Send or Finish input control. It uses an authenticated no-store API endpoint instead of the action, bypasses service-call events and traces, stores no last synchronized value, returns no entered text, and clears its DOM field on blur or unload. Test application keyboards independently; the tested YouTube app ignored both this integration and SmartThings text. Enter a password through the card only when the Home Assistant page uses HTTPS and the browser, device keyboard, Home Assistant host, network, reverse proxy, and TV are trusted. The current plaintext remains transiently present in runtime memory while it is being entered and transmitted.

## Validate before optional layers

In **Developer Tools > Actions**, call `remote.send_command` with a harmless command:

```yaml
action: remote.send_command
target:
  entity_id: remote.samsung_tv_remote
data:
  command: up
```

Complete the direct Samsung sequence in [TESTING.md](TESTING.md) before installing the dashboard or Harmony automation.

For native playback, app launch, and optional text examples, use [COMMANDS.md](COMMANDS.md). Launching an application can change the active screen without changing the HDMI source reported by `getTVStates`.

## Add the Samsung dashboard

1. Open **Settings > Dashboards**.
2. Open the three-dot menu and select **Resources**.
3. Add `/samsung_ip_control_static/samsung-ip-remote-card.js` as a **JavaScript module** resource. This path is served by the integration and uses no external CDN.
4. Refresh Home Assistant after saving the resource.
5. Create a new dashboard and open its raw configuration editor.
6. Paste [the first-party remote example](../examples/dashboards/samsung-tv-remote.yaml).
7. Replace the example media-player and remote entity IDs.
8. Save and inspect desktop and mobile layouts.
9. Confirm all command groups render, TV Off retains its confirmation prompt, and the text field is disabled until optional text input is paired.
10. Run the dashboard acceptance checks in [TESTING.md](TESTING.md).

The first-party card requires no Mushroom, Card Mod, Button Card, or other HACS frontend package. Use [the native fallback](../examples/dashboards/samsung-tv-remote-native.yaml) when custom frontend resources are prohibited. It covers common actions with Home Assistant built-in cards and leaves text entry and less common commands in Developer Tools.

## Update connection details

Use the integration's **Reconfigure** action when the TV address, port, or Wake-on-LAN MAC changes. The flow validates the existing certificate pin, access token, and physical TV serial before saving the new connection details.

A certificate mismatch stops before token transmission. Verify the TV, address assignment, and network path. Remove and add the integration only after deciding to trust the replacement certificate.

## Reauthentication

When the TV rejects the stored token, Home Assistant starts reauthentication.

1. Turn on the TV.
2. Close Samsung Home and display an HDMI picture.
3. Open the reauthentication flow.
4. Submit the confirmation form.
5. Accept the new local IP Remote authorization prompt on the physical TV.

Reauthentication replaces the token after verifying the pinned certificate and the same TV serial. Config entries using an older identity format migrate only after the integration validates the physical TV, while their existing entity-registry identity remains attached.

## Update the integration

1. Review the release notes and security changes.
2. Create a backup.
3. Update through HACS or replace the full custom-component directory.
4. Run the Home Assistant configuration check.
5. Restart after approval.
6. Confirm both entities return.
7. Run tests for every affected command.
8. Retain the backup until physical acceptance passes.

## Remove the integration

1. Disable automations and dashboards that target the integration entities.
2. Open **Settings > Devices & services**.
3. Remove the Samsung TV IP Control config entry through its menu.
4. Restart after approval when removing the custom-component code.
5. Remove `custom_components/samsung_ip_control` through HACS or the supported file path.
6. Run the configuration check and confirm no automation references remain.

Do not edit registry or config-entry files under `.storage` for installation, reconfiguration, reauthentication, or removal.

## AI-assisted setup

Use the project skill at `.claude/skills/set-up-samsung-tv-ip-control/SKILL.md` or copy the prompt from [AI_ASSISTED_SETUP.md](AI_ASSISTED_SETUP.md). The AI guide identifies each MCP, browser, filesystem, and physical boundary and requires an evidence-based handoff.
