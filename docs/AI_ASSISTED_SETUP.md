# AI-assisted setup and verification

This guide supports Claude Code, Codex, and other agents with filesystem, browser, or Home Assistant MCP tools. It also gives a chat-only AI enough structure to guide a person through the setup.

## Supported operating modes

| Mode | What the AI can complete | Required handoff |
| --- | --- | --- |
| Chat guidance | Produce a tailored setup plan and verify user-reported evidence | User performs every UI, file, and physical step |
| Filesystem or terminal | Audit the repository, run tests, copy files when authorized, and run a server-side configuration check | User or browser handles Home Assistant UI and TV approval |
| Browser | Configure integrations, HACS, dashboards, automations, actions, and traces through an authenticated UI | User handles login, MFA, TV approval, and physical Harmony work |
| Home Assistant MCP | Read available context and call the tools exposed by the configured LLM API | Browser or user handles administrative UI work |
| Browser plus filesystem plus optional MCP | Complete the largest safe portion of setup and collect strong evidence | User handles credentials and physical checkpoints |

MCP capabilities come from the LLM API selected in Home Assistant. The default Assist API supports exposed entities and actions and has no administrative capability. Custom per-API endpoints can expose other tools and require an administrator credential. An agent must identify the selected API, inspect its live tool list, and avoid promises based on MCP availability alone.

## Capability matrix

| Task | Default Home Assistant MCP | Authenticated browser | Filesystem or terminal | Person at device |
| --- | --- | --- | --- | --- |
| Read exposed entity state | Usually available when exposed | Available | Available only through a separately authorized API or logs | Optional |
| Call an exposed TV action | Tool-dependent | Available in Developer Tools | Tool-dependent | Approves disruptive test |
| Install custom-component files | Unavailable | HACS can install; raw files need a supported file tool | Available with authorized config-directory access | Approves deployment |
| Add or remove an integration | Unavailable through the built-in Assist API | Available | Avoid direct `.storage` editing | Approves removal |
| Accept local IP Remote pairing | Unavailable | Submit the config flow | Unavailable | Accepts authorization prompt on TV |
| Pair optional local text input | Unavailable | Open the integration's Configure flow | Unavailable | Accepts the separate authorization prompt on TV |
| Send text to an active TV field | Do not assume; only when the selected LLM API exposes this custom action | Available in Developer Tools > Actions | Available only through a separately authorized API | Selects a non-sensitive field and verifies visible characters |
| Import or edit a dashboard | Unavailable through the built-in Assist API | Available | Storage internals are out of scope | Reviews UI |
| Create or edit an automation | Unavailable through the built-in Assist API | Available | YAML is possible only when the instance uses managed YAML | Reviews behavior |
| Inspect an automation trace | Usually unavailable | Available | Possible only through an explicitly authorized API | Optional |
| Restart Home Assistant | Administrative and normally unavailable | Available | Installation-specific service command | Approves maintenance |
| Configure or sync Harmony | Unavailable | Harmony software may require a separate browser or app | Unavailable | Operates and verifies hardware |
| Confirm the physical TV result | State may provide partial evidence | UI state provides partial evidence | Logs provide partial evidence | Supplies final acceptance |

Treat browser visibility, MCP state, logs, and automation traces as separate evidence sources. Physical button assignment and TV behavior require a physical test.

## Security rules for AI work

1. Read `README.md`, `SECURITY.md`, `docs/DEPENDENCIES.md`, `docs/HOME_ASSISTANT_SETUP.md`, this guide, and `docs/TESTING.md` before changing a live system.
2. Inventory the available filesystem, browser, MCP, and deployment capabilities.
3. Use an existing authenticated browser session. Ask the user to complete login or MFA directly in the browser.
4. Keep Home Assistant tokens, Samsung tokens, passwords, cookies, certificate contents, serial numbers, IP addresses, MAC addresses, screenshots with private metadata, entered TV text, and diagnostics out of chat and repository files.
5. Never read, print, export, or rewrite Home Assistant `.storage` for this setup.
6. Obtain approval before copying files to the live config directory, installing through HACS, restarting Home Assistant, changing an automation, pairing optional text input, sending text, or running power, input, application, playback, mute, or volume tests.
7. Record the starting TV power, input, active screen or application, volume, mute state, and active Harmony activity before state-changing tests.
8. Use a harmless navigation command for the first live request.
9. Return the TV, volume, mute, input, screen or application where practical, and Harmony activity to their recorded starting state.
10. Report observed evidence and pending physical confirmation separately.

## Optional Home Assistant MCP setup

1. In Home Assistant, add the built-in **Model Context Protocol Server** integration.
2. Select the LLM API and expose only the entities and capabilities the AI needs.
3. Choose the current client-specific connection method:
   - Claude Code or Codex can use the Streamable HTTP endpoint with OAuth when the client machine can reach the authorized Home Assistant URL, including an approved local or VPN route.
   - The Claude Desktop cloud connector requires a protected public Home Assistant URL and brokers the connection through cloud infrastructure.
   - A client limited to a local `stdio` process can use `mcp-proxy`; the Home Assistant documentation gives Claude Desktop as the local-only example.
4. Prefer OAuth when the client supports it. When a proxy is required, select and record a reviewed release or commit instead of relying on an unreviewed floating checkout. Store any required long-lived access token in the AI client's secure secret facility or an operating-system credential store. A wrapper may retrieve the token at runtime and pass it only to the proxy process.
5. Keep literal tokens out of `.mcp.json`, Claude configuration committed to Git, shell history, screenshots, logs, and prompts.
6. Test authentication and MCP initialization separately. A successful REST response establishes token validity. A successful MCP initialization establishes transport and protocol compatibility.
7. Enumerate the connected MCP tools. Record which entities and actions are visible.

Review public exposure, TLS, authentication, client trust, and access policy before using a cloud connector. A direct local or VPN route keeps the endpoint within that network path. A local proxy keeps a local Home Assistant endpoint local to the machine running the AI client. Recheck the official client section before setup because MCP authorization and transport support continues to evolve.

## Browser workflow

1. Open Home Assistant in an existing signed-in browser session.
2. Ask the user to complete login or MFA when the session is signed out.
3. Confirm a current backup exists and record the Home Assistant version and installation type.
4. Install the integration through HACS or confirm the authorized filesystem deployment completed.
5. Run the configuration check through the supported UI or deployment path.
6. Ask for restart approval, restart Home Assistant, and wait for the UI to recover.
7. Open **Settings > Devices & services > Add integration** and select **Samsung TV IP Control**.
8. Enter the user's TV address, port, display name, and optional wired MAC without echoing those values into chat.
9. Ask the user to display an HDMI picture and accept the local IP Remote authorization prompt on the physical TV.
10. Capture the created media player and remote entity IDs from the UI. Keep them in the task context and out of public artifacts.
11. When text input is requested, open the integration's **Configure** flow, enable it, keep secure port `8002` unless the TV requires another port, and ask the user to accept the separate local remote prompt on the TV.
12. Activate an empty, non-sensitive Samsung system field, call `samsung_ip_control.send_text` with `h`, `ha`, `h`, and an empty value while `submit` remains false, and ask the user to confirm exact complete-value typing, Backspace-equivalent replacement, and clearing without a blank glyph. Test the card's automatic typing, Backspace, paste-over, mid-string edit, and clear behavior with another harmless dummy value. Repeat with a mobile predictive keyboard and confirm characters arrive while input is still composing, without pressing Go or Done. Confirm the card uses the authenticated no-store API endpoint, creates no service-call event or trace, echoes no entered text, clears on blur or unload, and warns when the Home Assistant page uses HTTP. Then test `submit` separately through Developer Tools. Confirm the card has no Send or Finish input control. Test third-party application keyboards separately; the tested YouTube app ignores both integration and SmartThings text. Use Number pad commands for digits when the screen accepts Consumer IP number keys. An AI must never request, receive, enter, transmit, inspect, or verify a real password, access code, personal value, or untrusted text. The user may enter a secret personally through the card only over HTTPS on trusted devices.
13. Run the direct integration tests before adding Harmony.
14. When the first-party dashboard is requested, register `/samsung_ip_control_static/samsung-ip-remote-card.js` as a JavaScript-module resource, import the example, replace every entity ID, and inspect desktop and mobile layouts. Use the native fallback when custom resources are prohibited.
15. Add the Harmony bridge only after direct Samsung tests pass. Replace all example activity names and entity IDs, then inspect the resulting automation in the UI.
16. Run the applicable acceptance tests and collect screenshots or traces only after checking them for private data and entered text.

Prefer semantic browser locators and fresh UI snapshots. Avoid coordinate-only actions when accessible labels are available. Stop when the visible page differs materially from the documented flow.

## Quick setup prompt

Use this prompt when you want the assistant to run the whole setup, including fetching the repository, and interview you for the details. Nothing needs to be edited before pasting it:

```text
Set up Samsung TV IP Control for Home Assistant for me. Complete every step your tools allow and guide me through the rest.

If this repository is not already available locally, download it from https://github.com/anjulahettige/home-assistant-samsung-tv-ip-control. Read README.md, SECURITY.md, docs/DEPENDENCIES.md, docs/HOME_ASSISTANT_SETUP.md, docs/AI_ASSISTED_SETUP.md, and docs/TESTING.md before changing anything.

Inventory your available tools first: repository filesystem, terminal, authenticated browser, Home Assistant MCP, and deployment access. Then ask me, in one round of questions, for anything you cannot discover yourself, such as my Home Assistant installation type, the installation method I prefer (HACS or manual), the TV display name and address, and whether I want Wake-on-LAN, optional local text input, the Harmony bridge, or a dashboard. Propose a plan with explicit checkpoints and wait for my approval before changing a live system.

Follow the security rules in docs/AI_ASSISTED_SETUP.md exactly. Never print or store credentials, tokens, IP addresses, MAC addresses, serial numbers, or entered TV text. Never edit Home Assistant .storage. Ask for approval before deploying files, restarting Home Assistant, pairing, changing automations, or sending TV commands. Record the TV and Harmony state before tests and restore it afterward. I will handle logins, the TV's on-screen authorization prompts, and physical confirmation when you ask.

Finish with the evidence table defined in docs/AI_ASSISTED_SETUP.md and list every skipped or pending check.
```

## Copy-and-paste setup prompt

This detailed variant suits users who prefer to pre-answer every setup choice instead of being interviewed. Replace the bracketed values locally. Keep addresses, MACs, tokens, and entity IDs inside the authenticated tools rather than the prompt whenever possible.

```text
Set up and verify Samsung TV IP Control for Home Assistant using this repository.

Read README.md, SECURITY.md, docs/DEPENDENCIES.md, docs/HOME_ASSISTANT_SETUP.md, docs/AI_ASSISTED_SETUP.md, and docs/TESTING.md before taking action. Use the project skill set-up-samsung-tv-ip-control when your client supports skills.

First inventory your available tools: repository filesystem, terminal, authenticated browser, Home Assistant MCP, deployment access, and any Harmony access. Enumerate the actual Home Assistant MCP tools. The default Assist API has no administrative capability, so route integration setup, HACS, dashboards, automations, reauthentication, and traces through the authenticated Home Assistant browser. Use filesystem or deployment access only for the custom-component copy and configuration check.

My choices:
- Installation method: [HACS or manual]
- Home Assistant installation type: [OS, Supervised, Container, or Core]
- TV display name: [enter locally]
- TV address: [enter directly in Home Assistant]
- IP Control port: [1516 unless my TV differs]
- Wake-on-LAN: [enabled with wired MAC or disabled]
- Optional local text input: [yes or no]
- Text-input WebSocket port: [8002 unless my TV differs]
- Harmony bridge: [yes or no]
- Dashboard: [complete first-party card, native fallback, or no]

Prepare a plan with explicit checkpoints. Start with read-only checks. Do not request or print credentials, cookies, tokens, certificate contents, serial numbers, IP addresses, MAC addresses, entered TV text, or unredacted diagnostics. Never edit Home Assistant .storage. Ask for approval before live file deployment, HACS installation, restart, automation changes, optional text-input pairing, text entry, and disruptive TV tests.

Use an existing authenticated browser session. Ask me to handle login, MFA, the Samsung TV's local Consumer IP and optional WebSocket authorization prompts, selection of an empty non-sensitive Samsung system field, Harmony app or remote steps, and physical confirmation. Do not assume the default Home Assistant MCP can configure the integration or invoke the custom text action. For the first-party dashboard, register only the integration-served JavaScript module documented in docs/HOME_ASSISTANT_SETUP.md; do not install an unrequested third-party card or use a CDN. When text input is enabled, test the complete snapshots `h`, `ha`, `h`, and empty with submit disabled. Then test the card's automatic typing, Backspace, paste-over, mid-string edits, clear, blur clearing, HTTP warning, private no-store API dispatch, response headers, absence of entered text in responses, and absence of service-call events or traces using harmless dummy text. Test submit separately through Developer Tools. Confirm the card has no Send or Finish input control. Never request, receive, enter, transmit, inspect, or verify a real password, access code, personal value, or untrusted text. Tell me that I may enter a secret personally only through the card while Home Assistant uses HTTPS and all runtime devices are trusted. Test third-party app keyboards separately and record unsupported behavior. Record the starting TV power, input, active screen or application, volume, mute state, and Harmony activity before tests. Run repository tests, direct integration tests, optional text input, playback and installed-app checks, optional dashboard checks, and optional Harmony tests in the order defined in docs/TESTING.md. Start live control with a harmless navigation command. Restore every recorded state after testing.

Finish with an evidence table containing check, method, observed result, and status. Label browser observations, MCP observations, configuration validation, automation traces, and physical confirmation separately. List every skipped or pending check and the exact person or tool needed to complete it.
```

## Validation-only prompt

```text
Audit an existing Samsung TV IP Control installation using docs/TESTING.md. Make no changes. Enumerate available MCP and browser capabilities, record the starting device state, run read-only checks first, and request approval before any command that changes TV or Harmony state. Separate UI, MCP, trace, log, and physical evidence. Restore the starting state and report every unverified item.
```

## Required AI handoff

Use this table in the final report:

| Check | Evidence source | Observed result | Status |
| --- | --- | --- | --- |
| Repository tests | Local command output | Exact pass or failure summary | Pass, Fail, or Skipped |
| Integration files | HACS, filesystem, or checksum | Installed version and path class | Pass, Fail, or Pending |
| Config entry | Browser | Loaded state and entity IDs | Pass, Fail, or Pending |
| Direct commands | Browser, MCP, and physical TV | Per-command result | Pass, Fail, or Pending |
| Optional text input | Browser action and physical TV | Pairing, visible characters, and cleanup | Pass, Fail, Pending, or Disabled |
| Dashboard | Browser | Render and target validation | Pass, Fail, or Pending |
| Harmony | Event, trace, and physical remote | Per-route result | Pass, Fail, or Pending |
| State restoration | Browser, MCP, and physical TV | Final state compared with baseline | Pass, Fail, or Pending |

Never convert partial evidence into a full pass.

## Current upstream documentation

- [Home Assistant MCP Server](https://www.home-assistant.io/integrations/mcp_server/)
- [Home Assistant LLM API and administrative boundary](https://developers.home-assistant.io/docs/core/llm/)
- [Claude Code project and personal skills](https://code.claude.com/docs/en/slash-commands)
