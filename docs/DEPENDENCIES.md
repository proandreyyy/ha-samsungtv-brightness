# Dependencies and supported setup paths

The Samsung integration has no separately installed Python runtime packages. Home Assistant supplies the standard library, `aiohttp`, and `yarl` modules used by the integration, and `manifest.json` deliberately contains an empty `requirements` list.

## Core requirements

| Component | Requirement | Purpose |
| --- | --- | --- |
| Home Assistant | `2026.8.0` or newer | Hosts the custom integration, config flow, entities, diagnostics, and automations |
| Samsung TV | HTTPS JSON-RPC IP Control on TCP `1516` | Provides the local control API |
| Local network | Home Assistant can reach the TV address and port | Carries polling and commands |
| Stable TV identity | The TV must return a serial number during pairing | Supplies the stable Home Assistant config-entry unique ID |
| Trusted first pairing | User is present at the physical TV on a trusted LAN | Establishes the initial certificate pin and approves token creation |

The integration stores the Samsung Consumer IP access token and pinned certificate fingerprint in the Home Assistant config entry. Optional text input stores a separate local WebSocket token and certificate fingerprint in config-entry options. It does not use a `.env` file, `secrets.yaml`, SmartThings, or a cloud API.

## Optional components

| Component | Needed when | Notes |
| --- | --- | --- |
| Wired TV MAC address | Optional. Only when a TV is confirmed to need the Wake-on-LAN fallback; power-on works over IP without it | Stored in Home Assistant and redacted from diagnostics |
| Samsung local WebSocket IME on secure TCP `8002` | Text entry into a visible TV input field is wanted | Independently paired, independently certificate-pinned, and supported only when the TV advertises IME sync |
| HTTPS access to Home Assistant | Passwords or other secrets are entered through the first-party card | Encrypts the browser-to-Home-Assistant API request; HTTP remains acceptable only for non-sensitive text on the trusted LAN |
| HACS | Installing or updating through HACS | Add this GitHub repository as a custom Integration repository |
| Home Assistant Harmony integration | Harmony activity state controls TV power | Built into Home Assistant |
| Home Assistant Emulated Roku integration | Harmony buttons carry Samsung commands | Built into Home Assistant; exposes an unauthenticated LAN listener |
| Home Assistant HTTP integration | Serves the optional first-party remote card | Declared as a built-in manifest dependency; no external package or CDN |
| First-party Samsung remote card | Focused responsive daily remote, Number pad, and transient Samsung system text are wanted | JavaScript ships inside the custom integration, uses a private permission-checked no-store API endpoint for text, and must be registered once as a Lovelace module resource |
| Native Home Assistant dashboard fallback | Common direct TV controls are wanted without a custom resource | Uses built-in cards only; omits the transient text box and some extended keys |
| Home Assistant MCP Server | An AI should inspect or control exposed entities | Optional AI convenience; it is independent of this integration |
| Browser-capable AI or user-operated browser | Integration, dashboard, automation, trace, or pairing UI work is required | Use an existing authenticated session and keep credentials out of chat |
| `mcp-proxy` and `uv` | An MCP client supports only a local `stdio` process, such as the documented Claude Desktop local-proxy path | Follow the current Home Assistant MCP documentation, choose a reviewed release or commit, and store the token outside project files |

## Home Assistant installation types

### Home Assistant Operating System or Supervised

Use HACS or a supported file-access add-on to place the integration at `/config/custom_components/samsung_ip_control`. Create a backup before installation, run the available configuration check, and restart through the Home Assistant UI.

### Home Assistant Container

Copy the integration into the host directory mounted as `/config/custom_components/samsung_ip_control`. Confirm the complete directory is present, run Home Assistant's configuration check inside the container, and restart during an approved maintenance step.

### Home Assistant Core

Copy the integration into the active configuration directory under `custom_components/samsung_ip_control`. Run the configuration check with the same Home Assistant virtual environment, then restart the Core process through its normal service manager.

The repository does not assume a host path, container name, SSH account, operating system, or backup location.

## Development and CI dependencies

| Dependency | Where recorded | Purpose |
| --- | --- | --- |
| Python `3.14.2` | GitHub Actions workflow | Matches the minimum Python patch release required by Home Assistant `2026.8.2` |
| Python standard library `unittest` | Tests | Runs protocol and repository privacy checks without a Home Assistant install |
| Node.js syntax checker | GitHub-hosted runner and optional local validation | Parses the first-party remote card without adding an npm dependency |
| Ruff `0.16.4` | `requirements-dev.txt` | Lint and format validation |
| Home Assistant `2026.8.2` | `requirements-home-assistant.txt` | Imports every integration module against the physically tested API version |
| Hassfest action | Pinned GitHub Actions commit | Home Assistant metadata and structure validation |
| HACS action | Pinned GitHub Actions commit | HACS repository validation |
| CodeQL action | Pinned GitHub Actions commit | Static security analysis |

Install local development tooling with:

```sh
python3 -m pip install --disable-pip-version-check --requirement requirements-dev.txt
```

Run local checks with:

```sh
python3 -m unittest discover -s tests -v
```

```sh
ruff check .
```

```sh
ruff format --check .
```

Run the optional Home Assistant API import check in an isolated Python 3.14.2 environment with:

```sh
python3 -m pip install --disable-pip-version-check --requirement requirements-home-assistant.txt
```

```sh
python3 -c 'import custom_components.samsung_ip_control; import custom_components.samsung_ip_control.config_flow; import custom_components.samsung_ip_control.diagnostics; import custom_components.samsung_ip_control.frontend; import custom_components.samsung_ip_control.media_player; import custom_components.samsung_ip_control.remote; import custom_components.samsung_ip_control.services; import custom_components.samsung_ip_control.text_client'
```

## AI tooling boundary

The default Home Assistant Assist API exposed through MCP supports the tools and entities selected in Home Assistant. Home Assistant's developer documentation states that the built-in Assist API cannot perform administrative tasks. A custom LLM API may expose additional tools, and its per-API MCP endpoint requires administrator credentials. An AI must enumerate its actual tools and selected API before planning.

Connection requirements vary by client. Current Claude Code and Codex clients can use Home Assistant's Streamable HTTP endpoint with OAuth when the client machine can reach the Home Assistant URL, including an authorized local or VPN path. The documented Claude Desktop cloud connector requires a public Home Assistant URL. Claude Desktop can instead reach a local-only URL through `mcp-proxy` and a long-lived access token. Follow the current Home Assistant client-specific instructions because MCP transport and authorization support continues to evolve.

Use the Home Assistant UI for config-entry administration, HACS, dashboard import, automation editing, trace inspection, text-input pairing, reauthentication, and integration removal. Use filesystem or deployment access for the custom-component copy and server-side configuration check. A person must approve the Samsung TV's local Consumer IP and optional WebSocket remote authorization prompts, operate Harmony software or hardware when required, and confirm physical results.

Read [AI_ASSISTED_SETUP.md](AI_ASSISTED_SETUP.md) for the complete capability matrix and secure AI workflow.

## References

- [Home Assistant MCP Server](https://www.home-assistant.io/integrations/mcp_server/)
- [Home Assistant API for large language models](https://developers.home-assistant.io/docs/core/llm/)
- [Home Assistant integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [Home Assistant integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Claude Code skills](https://code.claude.com/docs/en/slash-commands)
