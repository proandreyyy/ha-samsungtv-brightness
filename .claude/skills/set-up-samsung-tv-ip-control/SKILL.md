---
name: set-up-samsung-tv-ip-control
description: Install, configure, audit, test, or troubleshoot the Samsung TV IP Control custom integration for Home Assistant, including optional dashboards, Logitech Harmony through Emulated Roku, Home Assistant MCP, and browser-assisted setup. Use for new installations, upgrades, AI-guided setup, capability-aware validation, privacy audits, and physical acceptance testing.
---

# Set Up Samsung TV IP Control

Follow the repository's safe setup and evidence workflow. Treat Home Assistant MCP, browser automation, filesystem access, and physical access as separate capabilities.

## Establish context

1. Locate the repository root containing `custom_components/samsung_ip_control/manifest.json`.
2. Read these files completely:
   - `README.md`
   - `SECURITY.md`
   - `docs/DEPENDENCIES.md`
   - `docs/HOME_ASSISTANT_SETUP.md`
   - `docs/COMMANDS.md`
   - `docs/AI_ASSISTED_SETUP.md`
   - `docs/TESTING.md`
3. Read `docs/HARMONY_SETUP.md` and `docs/BUTTON_MAP.md` when Harmony is in scope.

## Inventory capabilities

Identify and report which of these capabilities are available:

- Repository filesystem and local terminal.
- Authorized access to the Home Assistant configuration directory or deployment host.
- Authenticated Home Assistant browser.
- Home Assistant MCP, selected LLM API, authorization method, and enumerated live tool list.
- Harmony app, browser, Hub, or physical remote.
- A person at the Samsung TV.
- Whether optional local text input is wanted and whether the person can select a non-sensitive visible input field.

Apply the capability matrix in `docs/AI_ASSISTED_SETUP.md`. The default Home Assistant Assist API exposed through MCP has no administrative capability. Route config entries, HACS, dashboards, automation editing, traces, reauthentication, and optional text-input pairing through the authenticated browser. Treat `samsung_ip_control.send_text` as unavailable through MCP until the selected LLM API's enumerated tool list proves otherwise. Use deployment access for integration files and server-side configuration validation.

## Protect secrets and live state

- Keep passwords, cookies, Home Assistant tokens, Samsung tokens, certificate contents, serial numbers, network addresses, MAC addresses, diagnostics, entered TV text, and private screenshots out of chat, logs, commands, and repository files.
- Ask the user to enter private values directly into the authenticated Home Assistant UI.
- Never read or edit Home Assistant `.storage` for this workflow.
- Start with read-only checks.
- Obtain approval before installing files, using HACS, restarting Home Assistant, changing an automation, removing an integration, pairing optional text input, sending text, or running disruptive TV and Harmony tests.
- Record starting power, input, active screen or app, volume, mute, and Harmony activity before live control.
- Preserve a rollback path and current backup.

## Plan the setup

Collect or infer only non-secret choices:

- HACS or manual installation.
- Home Assistant OS, Supervised, Container, or Core.
- Wake-on-LAN enabled or disabled.
- Dashboard enabled or disabled.
- Harmony bridge enabled or disabled.
- Optional local text input enabled or disabled.
- Available AI tools and required human checkpoints.

Present a short plan that names each approval and physical handoff. Avoid requesting private values in chat.

## Install and configure

1. Run `python3 -m unittest discover -s tests -v` from the repository root.
2. Run Ruff when the development dependency is available.
3. Confirm a current Home Assistant backup exists.
4. Install through HACS or copy only `custom_components/samsung_ip_control` to the active Home Assistant config directory.
5. Run the supported Home Assistant configuration check.
6. Request restart approval and wait for Home Assistant to recover.
7. Use the browser to add **Samsung TV IP Control**.
8. Ask the user to enter the TV address and optional wired MAC directly in Home Assistant.
9. Ask the user to show an HDMI picture and accept the Samsung TV's local IP Remote authorization prompt.
10. Capture the resulting media player and remote entity IDs privately.
11. When optional text input is requested, use the integration's **Configure** flow to pair the separate secure WebSocket endpoint. Ask the user to accept the separate local remote prompt at the TV.
12. Activate an empty, non-sensitive Samsung system field. Send the complete values `h`, `ha`, `h`, and empty with `submit: false`. Ask the user to confirm exact typing, Backspace-equivalent replacement, and clearing without a blank glyph. Test the card's automatic typing, Backspace, paste-over, mid-string edit, clear, blur clearing, and HTTP warning using another harmless dummy value. Repeat with a mobile predictive keyboard and confirm each visible edit arrives while input is composing, without pressing Go or Done. Confirm the card uses its authenticated no-store API endpoint, returns no entered text, and creates no service-call event or trace. Then test `submit` separately through Developer Tools. Confirm the card has no Send or Finish input control. Test third-party application keyboards separately and record unsupported behavior; the tested YouTube app ignores both integration and SmartThings text. Number pad digits use Consumer IP independently. Never request, receive, enter, transmit, inspect, or verify a real password, access code, personal value, or untrusted text. The user may enter a secret personally only through the card over HTTPS on trusted runtime devices.
13. Complete direct tests before adding other optional layers.
14. When the first-party dashboard is requested, register the integration-served JavaScript module from `docs/HOME_ASSISTANT_SETUP.md`, import the dashboard, replace every example entity ID, and inspect desktop and mobile layouts. Use the native fallback when custom resources are prohibited.
15. Add Harmony only after direct Samsung tests pass. Replace all example entity IDs, source names, and exact activities.

Use the reconfigure flow for a changed TV address, port, or Wake-on-LAN MAC. Treat a certificate mismatch as a security event. Verify the physical TV and network before establishing a new trust decision.

## Test and restore

Follow `docs/TESTING.md` in order:

1. Automated repository tests.
2. Installation and config-entry health.
3. Harmless direct command.
4. Full direct Samsung acceptance with approval, including optional text input, playback, and installed allowlisted apps when those features are in scope.
5. Dashboard validation when installed.
6. Harmony event, trace, and physical-route validation when installed.
7. Diagnostics redaction and repository privacy checks when relevant.
8. Restoration of the recorded starting state.

For installation verification, follow the clean-install guidance in `docs/TESTING.md`. Keep any disposable Home Assistant instance isolated from production radios, databases, dashboards, and automations.

Synthetic events establish automation logic only. Physical TV behavior and Harmony button assignments require physical evidence.

## Report evidence

Finish with the evidence table from `docs/AI_ASSISTED_SETUP.md`. Mark each item Pass, Fail, Pending, or Skipped. Identify the evidence source and every remaining user, browser, MCP, deployment, or physical action.
