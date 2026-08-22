# Security policy

## Reporting a vulnerability

Use GitHub private vulnerability reporting for a credential leak, authentication bypass, certificate-validation flaw, unsafe diagnostic, or a path that expands unauthenticated control. Keep sensitive reproduction material out of public issues and discussions. When private reporting is temporarily unavailable, open only a sanitized issue with no sensitive details.

Include the affected version, impact, minimum reproduction steps, and sanitized evidence. Remove tokens, serials, network identifiers, certificates, cookies, hostnames, household names, and screenshots containing private metadata.

## Security model

The integration's primary control path communicates directly from Home Assistant to the configured TV over local HTTPS port `1516`. Optional text input uses the TV's separate secure local WebSocket service, normally port `8002`, with an independent token and certificate pin.

Security controls include:

- A fixed remote-command allowlist.
- TLS `1.2` or newer.
- SHA-256 certificate pinning before any authenticated payload is sent.
- Stable serial-based Home Assistant config-entry identity.
- Six-second command timeouts and a 64 KiB response limit.
- JSON-RPC version and response-ID validation.
- Controlled exceptions that omit remote-provided message text.
- Transport errors that omit the private TV address and low-level network details.
- Serialized protocol requests.
- Diagnostics redaction.
- Independent certificate pinning and credentials for optional text input.
- A 200-printable-character text limit with control-character rejection.
- A first-party remote card with a fixed command surface, no persistent browser storage, and transient text-field clearing.
- No separately installed Python runtime dependencies.

The first certificate decision uses trust on first use. Pair on a trusted LAN, confirm the expected physical TV is displaying the authorization prompt, and investigate any later certificate mismatch before creating a new trust decision.

## Credential and private metadata handling

- Home Assistant stores the Samsung Consumer IP access token and certificate fingerprint in the config entry. Optional text input stores its separate local token and fingerprint in config-entry options.
- The repository requires no token, password, certificate, or `.env` file.
- Diagnostics redact both tokens, both certificate fingerprints, the TV serial, TV address or hostname, wired MAC, user-chosen name, entity identity, serial digest, and speaker name.
- Git ignores common Home Assistant databases, storage, logs, backups, keys, local AI settings, and MCP configuration.
- Repository privacy checks detect common credential formats, private IPv4 addresses, MAC addresses, emails, user home paths, config-entry IDs, and symlinks in tracked files.
- Issue reports must use sanitized logs and diagnostics.

Treat TV addresses, MACs, serials, certificate fingerprints, entity IDs that contain household names, Home Assistant tokens, browser sessions, and full diagnostics as private.

## Optional text-input boundary

Samsung's Consumer IP command sheets provide no text method for port `1516`. Text input therefore uses the TV's separate local WebSocket IME service only when explicitly enabled through **Configure**. The options flow pins that service's certificate before requesting its separate authorization token. A later certificate mismatch blocks before the token is sent.

The Developer Tools action sends text to whichever TV input field currently owns IME focus. It cannot determine whether that field is a search box, account field, or password field. Use that action only for non-sensitive, visible text. Never place passwords, access codes, tokens, personal data, or private searches in service calls, automations, scripts, blueprints, or AI prompts because Home Assistant service-call events, traces, YAML, backups, logs, and connected tools can retain action data.

The first-party card uses a dedicated authenticated HTTP API endpoint for interactive text. It checks the current user's entity-control permission and accepts only an entity owned by this integration. The handler bounds and validates the JSON body, creates no service call, event, automation, script, trace, state, or integration log record, never echoes the entered text, and applies `Cache-Control: no-store` to success and error responses. The frontend stores no last-synchronized plaintext and clears the DOM field when it loses focus or unloads.

This privacy boundary requires HTTPS between the browser and Home Assistant. The Samsung connection already uses certificate-pinned WSS. A Home Assistant page loaded over HTTP sends its authenticated API requests unencrypted across the LAN, so the card warns against secrets on HTTP. Even with HTTPS, the value necessarily exists transiently in the browser DOM and process, the device keyboard, the Home Assistant request and process memory, the Samsung WebSocket client, and the TV. Use a trusted device, browser profile, keyboard, Home Assistant host, and TV. Browser developer tools, endpoint monitoring, memory dumps, hostile extensions, keyboard learning, custom reverse-proxy request-body logging, and a compromised host remain outside the integration's protection.

Keep secure WebSocket port `8002` reachable only from trusted controllers. Do not expose it through NAT, a public tunnel, or an unauthenticated proxy. Disabling text input removes its optional token and fingerprint while preserving the Consumer IP pairing.

## Frontend resource boundary

The integration serves its first-party remote-card JavaScript at a static Home Assistant path. Like `/local` dashboard resources, the module URL is retrievable without Home Assistant authentication. The shipped file contains fixed source code only and must never contain a TV address, entity ID, token, certificate, household name, entered text, or another deployment value.

The card accepts entity IDs through private dashboard configuration and calls actions through the current authenticated Home Assistant frontend session. It exposes only the integration's fixed commands and has no arbitrary service, domain, URL, template, or script option. It does not use `localStorage`, `sessionStorage`, cookies, analytics, external code, or a CDN.

The transient text field remains in the page DOM while it has focus so complete-value replacement and Backspace remain possible. The card clears it locally on blur or unload and never logs it. The private no-store API path bypasses Home Assistant action data and traces. The autocomplete, autocorrect, autocapitalize, spellcheck, and common password-manager suppression attributes are advisory; browsers, extensions, and keyboards may ignore them. Shared profiles, device keyboards, developer tools, request inspection, process memory, reverse proxies, monitoring agents, and the TV remain possible runtime observation points.

## Emulated Roku boundary

Home Assistant documents Emulated Roku as an unauthenticated LAN API. Any client that can reach the listener can imitate a Roku key request. The included automation requires the configured source name and `keypress` type, then accepts only 13 tested keys that map to its independent 15-command Samsung boundary. The integration's additional playback, app, keypad, channel, color, and system commands are excluded from that automation. Source name is a routing filter and supplies no authentication.

Recommended deployment controls:

1. Keep Home Assistant, Harmony, and the TV on a trusted local network.
2. Block the Emulated Roku port from guest, IoT, and untrusted client networks unless those networks require access.
3. Exclude the port from NAT, UPnP, public tunnels, and unauthenticated reverse proxies.
4. Prefer a source-IP-restricted proxy that accepts the Harmony Hub and forwards to a listener unavailable to other clients.
5. Limit the automation to the exact source, event type, and allowlisted keys.
6. Keep unrelated emulation integrations on explicit exposure lists.
7. Give Home Assistant, the TV, and Harmony stable address assignments.

Network controls should enforce the Harmony source restriction. Home Assistant event data alone cannot authenticate a network client.

## Wake-on-LAN

Wake-on-LAN sends a broadcast magic packet containing the configured MAC address. Keep the Home Assistant host and TV within the intended broadcast boundary. Avoid routing UDP port `9` from untrusted networks.

## AI and MCP boundary

Home Assistant MCP is optional. The default Assist API supports exposed entity context and actions and has no administrative capability. Custom per-API endpoints may expose additional tools and require administrator credentials, so review the selected API and every live tool. Prefer OAuth where supported. Store any MCP credentials in a client secret facility or operating-system credential store. Keep literal tokens out of repositories, prompts, configuration examples, shell history, and screenshots.

Use an existing authenticated browser session for Home Assistant administration. Ask the user to complete login, MFA, and the Samsung TV's local Consumer IP and optional WebSocket authorization prompts. Never let an AI copy browser cookies or Home Assistant `.storage` into its working files or submit sensitive text to the TV.

Read [docs/AI_ASSISTED_SETUP.md](docs/AI_ASSISTED_SETUP.md) for the complete tool boundary.

## Dependency and workflow security

The integration manifest contains no separately installed Python requirements. Home Assistant supplies the `http`, `aiohttp`, and `yarl` runtime used for the first-party card and optional certificate-pinned WebSocket connection. The frontend module has no npm or CDN dependency. Development tooling is version-pinned. External GitHub Actions are pinned to full commit SHAs, Dependabot monitors action and development dependency updates, and CodeQL runs on the repository.

Review automated dependency updates before merging. Verify the upstream repository, release notes, and pinned commit whenever an action changes.

Optional AI bridge software runs outside this integration's dependency set. When `mcp-proxy` is required, select a reviewed release or commit and record it in the user's private environment documentation.

## Supported versions

Version `1.1.0` is the current supported release. Security fixes target the latest published version. Check the changelog and open fixes before reporting a vulnerability that may already be addressed.
