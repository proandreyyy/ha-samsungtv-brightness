# Testing and acceptance

Use the layers in order. Automated tests establish source behavior. Home Assistant UI checks establish installation and configuration. Physical tests establish TV and Harmony behavior.

## 1. Record the baseline

Before a state-changing test, record:

| Item | Starting value |
| --- | --- |
| TV power | On or Off |
| TV input | Current input |
| Volume | Current level |
| Mute | On or Off |
| Active screen, app, or text field | Current visible context |
| Harmony activity | Current activity or PowerOff |

Ask for approval before power, input, mute, volume, restart, or Harmony activity tests. Plan the exact restoration steps before sending the first command.

## 2. Automated repository tests

Run:

```sh
python3 -m unittest discover -s tests -v
```

The base suite uses Python's standard library and does not connect to Home Assistant or a TV. CI runs it on Python `3.14.2`, matching the minimum Python patch release required by the tested Home Assistant package. Home Assistant-specific tests skip when that package is absent and run in a separate CI job with the pinned package. Coverage includes:

- MAC and Samsung HDMI source normalization.
- Token-free pairing requests and authenticated token placement.
- TLS 1.2 minimum and SHA-256 certificate pinning.
- Rejection of authenticated requests when no certificate pin exists.
- Blocking token transmission after a certificate mismatch.
- JSON-RPC version validation and exact decimal-string response-ID correlation.
- Bounded response bodies and controlled remote error text.
- All 52 allowlisted remote commands, including the complete published key set and fixed direct-access apps.
- Exact `remoteKeyControl`, `channelUpDnControl`, and `directAccessControl` payloads.
- Native media-player play, pause, stop, and app-launch methods.
- Optional text payload encoding, printable 200-character boundary, certificate pinning, and credential redaction.
- Rejection of unknown commands.
- Deterministic sequential mute toggling.
- Wake-on-LAN fallback for HDMI selection.
- A standby `-32002` power rejection and a transport failure both absorbed on `power_on`, each falling back to Wake-on-LAN without blocking on a power read, and an unrelated error code still raising.
- `power_on` always attempting the IP write first, so a configured MAC is a fallback rather than a shortcut that leaves the set off.
- `power_off` propagating a rejection without polling or sending Wake-on-LAN.
- Commands publishing their result without awaiting a coordinator refresh, which would serialize an extra two-request poll ahead of the next button press.
- Publishing notifying listeners without going through `async_set_updated_data`, which would reset the refresh timer and let sustained button pressing postpone the reconciling poll indefinitely.
- Immediate publication of each command's known result for power, input, application surface, mute, and volume, including clamping to the reported range and never inventing a value that was not being reported.
- Surface tracking resolving application aliases, clearing on `back`, `exit`, and power off, surviving while the polled input holds, and clearing when the polled input moves on its own.
- Stable serial-based config-entry identity.
- Reauthentication replacing only a rejected token after certificate and serial identity validation.
- A verified legacy entry establishing its missing certificate pin only inside reauthentication.
- Verified migration of legacy host-based identity and rejection of an unrelated identity.
- Diagnostics redaction fields.
- Behavioral diagnostics redaction and missing-certificate reauthentication against the Home Assistant API.
- Duplicate serial ownership rejection during verified legacy migration.
- Manifest release fields and empty runtime dependency list.
- Private addresses, MACs, emails, home paths, config-entry IDs, common credential formats, and symlinks in tracked files.
- Commit-SHA pinning for external GitHub Actions.
- Dashboard commands remaining inside the integration allowlist and the Harmony example retaining its independent 15-command boundary.
- Permission-checked sensitive-text API dispatch without a Home Assistant service call, event, trace, or entity state.
- The endpoint bounding requests, applying `Cache-Control: no-store`, never echoing entered text, and the card retaining no plaintext last-value cache and clearing its DOM field on blur or unload.
- Disabling optional text input removing only its separate token and fingerprint while retaining unrelated options.
- The current release uses the MIT License, contains the required copyright notice, and has no conflicting license classification.

Install the recorded development dependency and run formatting checks:

```sh
python3 -m pip install --disable-pip-version-check --requirement requirements-dev.txt
```

```sh
ruff check .
```

```sh
ruff format --check .
```

GitHub Actions imports every integration module against the pinned, physically tested Home Assistant version and runs Hassfest, HACS validation, and CodeQL. Review the workflow results for every tagged release.

## 3. Repository privacy review

Run the automated suite, then inspect the exact material included in the release:

```sh
git status --short --branch
```

```sh
git diff --cached --check
```

```sh
git diff --cached
```

```sh
git log --all --oneline --decorate
```

Confirm:

- No token, password, cookie, private key, serial number, certificate content, private address, MAC address, email address, user home path, household hostname, Home Assistant config-entry ID, private screenshot, database, backup, log, or diagnostics file is staged or present in reachable Git history.
- Ignored caches, `.DS_Store`, local AI settings, `.mcp.json`, `.env` files, Home Assistant storage, databases, logs, keys, certificates, and backups remain outside Git.
- Repository ownership URLs and code-owner metadata resolve to `anjulahettige`.
- The MIT License and copyright notice are the intentional public terms and attribution.
- The repository has no symlink that points outside the project.

Repository tests scan the tracked working tree. Use a dedicated history-aware secret scanner again after commits, tags, or imported history exist.

## 4. Installation acceptance

1. Confirm the Home Assistant version meets [DEPENDENCIES.md](DEPENDENCIES.md).
2. Confirm the installed path ends with `/config/custom_components/samsung_ip_control/manifest.json`.
3. Confirm no backup or second copy exists under `/config/custom_components`.
4. Run the installation-specific Home Assistant configuration check.
5. Restart Home Assistant after approval.
6. Confirm **Samsung TV IP Control** appears under **Settings > Devices & services**.
7. Confirm the config entry loads without authentication, certificate, or transport errors.
8. Confirm one media player and one remote entity exist.
9. Confirm the remote entity lists exactly the 52 documented commands and the media player lists eight `supported_apps` values.
10. When optional text input was paired, confirm the remote's `text_input_enabled` attribute is `true` and the `samsung_ip_control.send_text` action appears.

### Clean-install confidence

An isolated Home Assistant instance at the minimum supported version or the exact tested patch release provides additional first-install confidence. It is optional when the exact release is already deployed, Home Assistant's configuration check passes, the installed runtime files match the release files, and the source has been reviewed from a fresh clone or archive. Record this optional coverage separately from the completed checks.

Test HACS custom-repository installation against the tagged release. Confirm the local icon, setup form, config entry, media player, remote entity, removal, and reinstall path. Keep production radios, databases, dashboards, and automations out of any temporary instance. Pair the physical TV only with approval and remove the temporary TV authorization afterward if the TV retains a separate client record.

## 5. Direct Samsung acceptance

Run these tests before dashboards or Harmony. Use **Developer Tools > Actions** in the browser. An MCP tool may be used only when its schema clearly supports the same action and target.

1. Record the starting power, source, volume, mute state, active screen or app, and Harmony activity.
2. Send `up` as the first harmless command.
3. Test Up, Down, Left, Right, Enter, Home, Menu, Back, and Exit.
4. Test Volume Up and Volume Down, then restore the starting volume.
5. Test Mute twice and confirm the starting mute state returns.
6. Test HDMI 1, HDMI 2, HDMI 3, and HDMI 4, then restore the starting input.
7. Test `play`, `pause`, `stop`, `fast_forward`, and `rewind` while known playable media is active. Record API acceptance and visible playback behavior separately.
8. Test digits 0 through 9, dash, caption, red, green, yellow, blue, Ambient, and Multi View only on a screen where the result can be recognized and safely reversed.
9. Test Channel Up and Channel Down only while a TV tuner or compatible channel source is active, then restore the starting channel when observable.
10. Launch one installed app with `remote.send_command`, then launch the same app with `media_player.play_media` and media type `app`.
11. Test every other installed allowlisted app. Mark absent, region-blocked, or retired apps as Unsupported instead of Fail.
12. When optional text input is enabled, activate an empty, non-sensitive Samsung system field and send `h`, `ha`, `h`, and an empty value with `submit: false`. Confirm each action sets the exact complete value and the final empty snapshot clears without leaving a blank glyph or control character.
13. In the first-party card, type a harmless phrase slowly and then quickly, use Backspace, paste over a selection, edit in the middle, and clear the field. Repeat on a mobile predictive keyboard while its input is still composing. Confirm every visible browser edit automatically reaches the TV in order before Go or Done is pressed, and the final visible value exactly matches the card. Confirm the card has no Send, Finish input, or synchronization-toggle control. Blur the field and unload the card, then confirm its DOM value clears and no plaintext last-value property exists.
14. Test each third-party application keyboard separately. Record the tested YouTube app as unsupported because it ignores both integration and SmartThings text. Test the same non-sensitive phrase with `submit: true` only in a compatible field and record whether it submits, closes the keyboard, or only ends the IME session.
15. Wait more than 30 seconds, send another value, and confirm a new authenticated session opens cleanly. Confirm a control character and a value longer than 200 characters are rejected before transmission. Use a harmless dummy value for privacy tests, never a real password, code, token, or personal value.
16. Test Power On, Power Off, and Power Toggle only with explicit approval. Restore the starting power state with a discrete command.
17. Restore the starting input, screen or application where practical, volume, mute state, power state, and Harmony activity.
18. Confirm no unexpected authentication, certificate, protocol, or transport errors appeared.

Record every command separately. A media-player state update supplies supporting evidence. The visible and audible TV result supplies physical evidence.

The official command sheets describe a broader cross-model surface than any single TV guarantees. `Accepted` means JSON-RPC success. `Physical pass` means the expected screen, playback, channel, or application behavior was observed. Use `Unsupported` when a documented option is unavailable on the tested model, firmware, region, input, or installed-app set.

## 6. Dashboard acceptance

1. Confirm `/samsung_ip_control_static/samsung-ip-remote-card.js` returns the exact module shipped in the installed integration and is registered once as a JavaScript-module resource.
2. Confirm the first-party dashboard targets the new remote and media-player entity IDs and loads without a missing-resource error.
3. Confirm the card contains the documented focused 39-command subset of the remote's 52-value `supported_commands` attribute. Confirm Hulu, both Vudu variants, Pandora, and the Extended controls section are absent from the card while the backend allowlist remains unchanged.
4. Confirm the status header reflects power, source, volume, and mute without exposing private device metadata.
5. Confirm TV Off retains a confirmation prompt.
6. Confirm the text field is disabled when optional text input is unpaired and enabled when `text_input_enabled` is true.
7. Confirm the automatic text field retains the current browser value only while focused and does not write it to browser local storage, session storage, entity state, console messages, or a last-synchronized plaintext property. Confirm there is no Send, Finish input, or synchronization-toggle control. Confirm the card calls the authenticated `POST /api/samsung_ip_control/sensitive_text` endpoint, never calls `samsung_ip_control.send_text`, and clears its DOM value on blur and unload.
8. Confirm an HTTP Home Assistant page displays the unencrypted-transport warning. On an HTTPS page, use only a dummy value to verify the warning clears and the request uses HTTPS. Confirm success and error responses contain `Cache-Control: no-store` and no entered text. Inspect Home Assistant events and traces to confirm the private card path creates no service-call event or trace.
9. Render at desktop width and a narrow mobile viewport. Confirm no clipped controls, horizontal overflow, unreadable labels, or inaccessible keyboard focus.
10. Test one harmless navigation button, one playback button with media active, one installed app, one HDMI button, and one Number pad digit on a compatible field.
11. Test the native fallback separately when it is distributed or documented for the release.

## 7. Harmony and Emulated Roku acceptance

1. Confirm the Emulated Roku listener is reachable only on the intended trusted network.
2. Listen for `roku_command` events in Home Assistant Developer Tools.
3. Start one managed activity from the physical Harmony remote.
4. Confirm Samsung Power On and Harmony's configured input.
5. Press every assigned physical control once and record its exact event key.
6. Confirm the automation trace maps the event to the intended allowlisted Samsung command.
7. Confirm source-device navigation remains assigned to the real source device.
8. Switch directly to another managed activity and confirm the TV remains on.
9. End the activity and confirm Samsung Power Off.
10. Confirm the automation queue returns to zero.
11. Restore the starting Harmony activity and TV state.

Synthetic Home Assistant events establish trigger, condition, mapping, and action behavior. They do not establish a physical Harmony button assignment.

## 8. Diagnostics privacy acceptance

Download integration diagnostics through Home Assistant and inspect the file locally before sharing it. Confirm these values appear as redacted or are absent:

- Samsung access token.
- TV serial number.
- TV address or hostname.
- Wired MAC address.
- User-chosen TV name.
- Pinned certificate fingerprint.
- Optional text-input token and certificate fingerprint.
- Derived entity identity and serial digest.
- Selected speaker name.

The remaining model, firmware, operational state, and non-identifying integration fields can support troubleshooting. Review them again for household-specific names before attaching the file to an issue.

## 9. AI execution rules

An AI must inventory its actual tools and use the matrix in [AI_ASSISTED_SETUP.md](AI_ASSISTED_SETUP.md). The default Home Assistant Assist API exposed through MCP cannot perform administrative tasks. Use an authenticated browser for integration setup, dashboards, automations, traces, text-input pairing, and reauthentication. Use deployment access for files and configuration checks. Ask the user to handle login, MFA, the Samsung TV's local Consumer IP and optional WebSocket authorization prompts, Harmony operation, selection of a safe on-screen text field, and physical confirmation.

AI reports must separate:

- Repository command output.
- Home Assistant configuration validation.
- Browser-observed UI state.
- MCP-observed entity state or action result.
- Automation event and trace evidence.
- Physical TV and Harmony confirmation.

Use Pass, Fail, Pending, or Skipped for every check. Never report a complete pass when a physical or browser-required step remains pending.

## 10. Failure and rollback

Stop the test at the first unexpected power, input, authentication, certificate, or routing result.

1. Record the failed command and evidence source without copying secrets.
2. Restore the recorded starting state through the last known-good direct path.
3. Disable only the new automation when the failure is in the Harmony layer.
4. Remove only the new dashboard when the failure is in the dashboard layer.
5. Restore the previous custom-component directory from the approved backup when the failure is in the integration update.
6. Run the Home Assistant configuration check before the approved restart.
7. Re-run the smallest failed layer before repeating the full acceptance sequence.
