# Changelog

All notable changes to Samsung TV IP Control are documented here.

## [1.1.0] - 2026-08-22

### Integration

- Added local Samsung HTTPS JSON-RPC control on port `1516` with UI-based pairing, stable device identity, reconfiguration, and access-token reauthentication.
- Added media-player and remote entities with power, volume, mute, HDMI source, playback, and application controls.
- Added a fixed 52-command allowlist covering Samsung Consumer IP navigation, playback, number, color, channel, application, power, HDMI, volume, and mute controls.
- Added exact HDMI 1 through HDMI 4 selection with wake and retry behavior.
- Added immediate state publication after successful commands while retaining scheduled polling for reconciliation.
- Added application and Samsung Home surface tracking when the TV continues reporting the underlying HDMI source.
- Added optional Wake-on-LAN fallback for TVs that require it.

### Optional text input and dashboard

- Added independently paired local text input through the TV's secure WebSocket IME service, with a separate certificate pin and token.
- Added the bounded `samsung_ip_control.send_text` action for complete field snapshots and optional IME completion.
- Added an authenticated no-store endpoint for interactive card text that bypasses Home Assistant service events and traces.
- Added a responsive first-party remote card with 39 daily controls, four applications, playback, live state, Number pad, and ordered text synchronization.
- Added a native Home Assistant dashboard fallback.

### Harmony and documentation

- Added the optional Logitech Harmony and Emulated Roku bridge with an independent 15-command boundary.
- Added dashboard examples, Harmony automation examples, a button map, compatibility evidence, troubleshooting guidance, and AI-assisted setup documentation.
- Added bug, compatibility, and feature-request issue forms.

### Security and maintenance

- Added TLS 1.2 minimum enforcement and SHA-256 certificate pinning before token transmission.
- Added bounded protocol responses, exact JSON-RPC response correlation, controlled error messages, and privacy-redacted diagnostics.
- Added pinned development tooling, commit-pinned GitHub Actions, Dependabot, CodeQL, Hassfest, and HACS validation workflows.
- Adopted the MIT License.

### Known compatibility limits

- Consumer IP Control on port `1516` has confirmed hardware coverage for one Samsung model and firmware combination.
- Application, playback, channel, feature-key, and text-input behavior varies by model, firmware, region, installed application, and active TV screen.
- Toggle wake from standby and Wake-on-LAN-only wake remain unconfirmed on the tested TV. Automations should use the discrete power commands.
