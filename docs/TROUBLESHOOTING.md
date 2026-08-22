# Troubleshooting

## Integration is absent after installation

- Confirm `manifest.json` is under `/config/custom_components/samsung_ip_control`.
- Run a Home Assistant configuration check.
- Restart Home Assistant after installing or updating Python integration files.
- Inspect Home Assistant logs for `samsung_ip_control`.

## Home Assistant shows the icon but HACS does not

Home Assistant `2026.3` and newer serve this repository's local `brand/icon.png` from the authenticated brands API. Confirm the icon appears on **Settings > Devices & services** first. Some HACS frontend versions may still request the legacy public brands CDN and show a placeholder for an otherwise valid local icon; this does not affect installation or the Home Assistant integration page. Track the upstream [HACS local-brand issue](https://github.com/hacs/integration/issues/5171) instead of copying private branding files or changing the integration domain.

## First-party remote card is missing or shows a configuration error

- Confirm the integration is loaded before adding the resource.
- Open **Settings > Dashboards**, open the three-dot menu, and select **Resources**.
- Register `/samsung_ip_control_static/samsung-ip-remote-card.js` as a JavaScript module exactly once.
- Refresh the browser after adding or updating the resource. The integration disables cache headers for this module to prevent stale release code.
- Confirm the card configuration uses `type: custom:samsung-ip-remote-card` and valid remote and media-player entity IDs.
- Check the browser console for the card version banner or a module-load error. The banner contains a version only and never entered text or device data.
- Use `samsung-tv-remote-native.yaml` while custom resources are unavailable.

A `404` for the module means the installed integration version does not include the frontend file or has not loaded. Replace the complete integration directory, run a configuration check, and restart Home Assistant. Do not copy the JavaScript from an unreviewed website or CDN.

## Pairing cannot connect

- Turn on the TV.
- Enable IP Remote or IP Control.
- Confirm the TV address and port `1516`.
- Keep Home Assistant and the TV on mutually reachable networks.
- Close Samsung Home and show an HDMI picture.

## Pairing prompt is absent

- Retry while an HDMI picture is visible.
- Check whether the TV retains a denied-device entry that must be removed.
- Confirm that the configured model exposes this exact port 1516 protocol.

## Certificate mismatch

The integration stops before transmitting the token. Verify the physical TV, its address, and the local network. A legitimate TV certificate replacement requires removing and re-adding the integration to establish a new trust decision.

## TV address, port, or MAC changed

Open the integration menu under **Settings > Devices & services** and choose **Reconfigure**. Enter the new connection details. The flow saves them only after the existing certificate pin, token, and TV serial all validate.

Use reauthentication first when the TV rejects the token. Investigate a certificate mismatch before removing and re-adding the integration.

## TV did not return a serial number

The integration requires a stable hardware identity and leaves the config entry unsaved. Confirm the exact port `1516` protocol is supported, close Samsung Home, show an HDMI picture, and retry. Include the model and firmware in a sanitized compatibility report when the response still omits `serialNumber`.

## Power On fails while the TV is off

Power-on runs over IP first. On the tested set that wakes the TV from standby in roughly half a second, without Wake-on-LAN involved at all, so check the IP path before anything else:

- Reserve the TV address and confirm port `1516` still answers while the set is in standby.
- Confirm the certificate pin and access token are still valid, since an authentication failure is reported as-is rather than absorbed.

Wake-on-LAN is only a fallback for when the IP write fails, and it has never been observed to wake the tested set on its own. The MAC is optional. Configure it only when a TV is confirmed to need it, then:

- Configure the TV's wired MAC address.
- Confirm Wake-on-LAN is supported and enabled on the TV.
- Keep Home Assistant and the TV broadcast-reachable.
- Verify the MAC has not changed.

## Turning on reports "The TV rejected powerControl, code -32002"

A set in standby often rejects `powerOn` with `-32002`, or drops the connection, while still acting on the request.

The client now absorbs `-32002` and transport failures on `power_on`, sending Wake-on-LAN as a fallback when a MAC is configured. Any other error code still fails immediately, so a genuine rejection is not hidden.

If the error persists on the current release, the code is not `-32002`. Check the full message in the log before working through the Wake-on-LAN checks above.

## Buttons work but the card lags behind the TV

The TV acts on a button well inside the ten-second polling interval, so a card that only shows polled values looks stuck even though every command succeeded. Volume steps and input changes are the most visible cases.

The integration publishes each command's known result immediately, with no extra TV request. Forcing a refresh after each command is the wrong fix and actively slows the remote down: every TV request is serialized behind one lock and a poll is two round trips, so the next button press ends up waiting for both. If a stale value persists on the current release:

- Confirm the deployed `samsung-ip-remote-card.js` matches the release and refresh the browser.
- Check that the command actually succeeded, since a failed command publishes nothing.
- Remember that the next poll always wins. A value that snaps back after a second means the TV did not accept the command.

## The card shows an HDMI input while Home or an app is on screen

Samsung's `getTVStates` reports only the underlying HDMI input, and keeps reporting it while Samsung Home or an application owns the panel. No local reading distinguishes them, and the set always wakes to Home.

The integration tracks the surface it last commanded and publishes it as the `surface` attribute on the remote entity. The card shows `surface` when one is tracked and falls back to the polled input otherwise. The tracked surface clears when the TV powers off, when the polled input moves on its own, and on `back`, `exit`, HDMI selection, or power off.

Pressing keys on the physical remote to open an app is invisible to the integration, so the card keeps showing the polled input until something it can observe changes. That is a protocol limit, not a fault.

## HDMI wakes the TV but Samsung Home remains visible

- Confirm the HDMI source has an active picture.
- Retry the exact HDMI command.
- Capture the TV model, firmware, and timing in a sanitized compatibility report.

## Harmony produces no event

- Confirm the Roku carrier is included in the current Harmony activity.
- Confirm the Emulated Roku listener is reachable on its configured port.
- Listen for `roku_command` in Home Assistant Developer Tools.
- Confirm the event source name matches the automation exactly.
- Sync the Harmony remote after changing assignments.

## Event arrives but the TV does not respond

- Confirm the key exists in `tv_command_map`.
- Confirm the Samsung remote entity ID.
- Test the corresponding command directly with `remote.send_command`.
- Inspect the automation trace and integration logs.

## Rapid presses feel delayed

- Keep Harmony carrier delays at zero initially.
- Check whether the Home Assistant automation queue is accumulating.
- Increase Harmony Inter-Key Delay in small steps only when commands are missed or reordered.

## Playback key is accepted but nothing changes

`remoteKeyControl` reports command acceptance independently of the active application's behavior. Start known playable media, confirm the application's own remote supports the requested action, and test Play, Pause, Stop, Fast Forward, and Rewind separately. Record JSON-RPC acceptance and visible playback behavior as separate evidence.

## Application does not launch

- Confirm the app is installed, available in the TV's region, and launchable with the physical Samsung remote.
- Use an app ID from [COMMANDS.md](COMMANDS.md). Arbitrary app names are rejected locally.
- Test `app_youtube` or the native `play_media` action with media type `app` and media ID `youtube` when YouTube is installed.
- Treat retired or unavailable fixed apps as unsupported on that model and region.
- Include the sanitized model identifier, firmware, region, app ID, and TV error code in a compatibility report. Exclude tokens, serials, addresses, and diagnostics.

## Text input cannot be enabled

- Confirm the TV is on and secure TCP port `8002` is reachable from Home Assistant.
- Confirm the TV advertises IME synchronization through its local `/api/v2/` endpoint.
- Open **Settings > Devices & services**, locate Samsung TV IP Control, and choose **Configure**.
- Accept the separate local remote authorization prompt on the physical TV. The Consumer IP prompt and token do not authorize text input.
- Keep the TV and Home Assistant on a trusted local network. Do not expose port `8002` through NAT or an unauthenticated proxy.

## Text-input certificate changed

The integration blocks before sending the optional token. Verify the physical TV, its network address, and the local network. Open **Configure**, select **Pair text input again**, and establish a new pin only after confirming that the expected TV shows the new authorization prompt.

## Text action succeeds but no characters appear

- Activate a visible, non-sensitive Samsung system field and make sure the TV's on-screen keyboard or IME is ready.
- Test the complete values `h`, `ha`, `h`, and empty with `submit: false` from **Developer Tools > Actions**. The visible TV field should exactly match each snapshot, and empty must leave no blank glyph.
- Confirm `text_input_enabled` is `true` on the Samsung remote entity.
- Test a Samsung Settings field before testing third-party apps. On the tested TV, Samsung Settings accepted text while YouTube ignored both the integration and SmartThings text.
- Use the Number pad for digits when the active screen accepts Consumer IP number keys. This path is independent of WebSocket text and worked in the tested YouTube field.
- In the first-party card, typing begins synchronization immediately. Use a visible supported Samsung system field. Enter secrets only when the Home Assistant page uses HTTPS and every runtime device is trusted.
- On a mobile predictive keyboard, characters must synchronize while the browser reports composition in progress. Pressing Go or Done must not be required. If text appears only after Go, confirm the installed card does not discard `isComposing` input events and includes a `compositionend` fallback, then refresh the resource.
- If updates appear out of order, reload the card and verify that its version banner matches the installed integration. The card serializes every browser input event, and the backend reuses one WebSocket session for 30 idle seconds.
- Use **Configure** to pair text input again when the TV reports a rejected token.
- Record the application, sanitized TV model and firmware, visible result, and whether the TV showed an IME. Exclude the entered phrase, tokens, addresses, and diagnostics.

`submit: true` sends `SendInputEnd`. Its visible effect is application-specific and may mean Done, Next, search, or no action. Test complete-value synchronization first, clear the phrase with an empty snapshot, and test submit separately. Never use this action for passwords, access codes, personal data, or untrusted text because Home Assistant action data and traces can retain full and partial values.

## Card warns that Home Assistant uses HTTP

The card's private no-store API endpoint avoids service-call events and traces, but HTTP leaves the browser-to-Home-Assistant request unencrypted on the LAN. Continue using the field only for non-sensitive text. For secrets, access Home Assistant through a correctly configured HTTPS URL and confirm the card's HTTP warning disappears. Keep the browser, device keyboard, Home Assistant host, reverse proxy, and TV trusted, and disable request-body capture in any proxy or monitoring layer. The Developer Tools action remains unsuitable for secrets even over HTTPS because it creates service-call data.
