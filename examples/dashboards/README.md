# Dashboard examples

For the focused first-party remote:

1. Install and load the Samsung TV IP Control integration.
2. Open **Settings > Dashboards**, open the three-dot menu, and select **Resources**.
3. Add `/samsung_ip_control_static/samsung-ip-remote-card.js` as a JavaScript module.
4. Refresh Home Assistant.
5. Create a dashboard and paste `samsung-tv-remote.yaml` into its raw configuration editor.

Replace:

- `media_player.samsung_tv`
- `remote.samsung_tv_remote`

The first-party remote card contains a focused 39-command daily-control surface, a TV Off confirmation, YouTube, Netflix, Prime Video, Browser, Number pad, and transient Samsung system text. Hulu, both Vudu variants, Pandora, color and infrequent system keys, and the Extended controls section remain absent from the card. Their allowlisted backend commands remain available through Home Assistant actions. The card uses Home Assistant theme variables, works at desktop and mobile widths, and adds no third-party frontend package. The action and app details are documented in [../../docs/COMMANDS.md](../../docs/COMMANDS.md). The Harmony button-map dashboard is read-only.

The card keeps typed text only in the current focused browser field and transient call variables. Each keyboard edit automatically sends the complete current value, including Backspace, selection replacement, paste, and an empty value for clearing. Updates remain serialized and the browser value stays visible for correction until it loses focus. The card has no Send or Finish input control, no last-value cache, and clears its DOM value on blur or unload. It uses a permission-checked no-store API endpoint that bypasses Home Assistant actions and traces and never echoes entered text. Sensitive text requires an HTTPS Home Assistant page and trusted browser, keyboard, Home Assistant host, network, reverse proxy, and TV. Use the Developer Tools text action only for non-sensitive values.

Use `samsung-tv-remote-native.yaml` when custom Lovelace resources are prohibited. That fallback uses built-in Home Assistant cards and provides the common navigation, volume, playback, applications, HDMI, and power controls. Use Developer Tools for the remaining commands and text input.
