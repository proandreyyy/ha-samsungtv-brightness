const SAMSUNG_IP_REMOTE_CARD_VERSION = "1.1.0";

const CONTROL_GROUPS = {
  quick: [
    { command: "power_on", label: "On", icon: "mdi:power", tone: "positive" },
    {
      command: "power_off",
      label: "Off",
      icon: "mdi:power-off",
      tone: "danger",
      confirm: "Turn off the Samsung TV?",
    },
    { command: "home", label: "Home", icon: "mdi:home" },
    { command: "back", label: "Back", icon: "mdi:arrow-u-left-top" },
  ],
  dpad: [
    { command: "menu", label: "Menu", icon: "mdi:menu" },
    { command: "up", label: "Up", icon: "mdi:chevron-up", iconOnly: true },
    { command: "exit", label: "Exit", icon: "mdi:location-exit" },
    { command: "left", label: "Left", icon: "mdi:chevron-left", iconOnly: true },
    { command: "enter", label: "OK", icon: "mdi:circle-outline", tone: "primary" },
    { command: "right", label: "Right", icon: "mdi:chevron-right", iconOnly: true },
    { command: "volume_down", label: "Volume down", icon: "mdi:volume-minus" },
    { command: "down", label: "Down", icon: "mdi:chevron-down", iconOnly: true },
    { command: "volume_up", label: "Volume up", icon: "mdi:volume-plus" },
  ],
  channel: [
    { command: "channel_down", label: "Channel down", icon: "mdi:minus" },
    { command: "mute", label: "Mute", icon: "mdi:volume-mute" },
    { command: "channel_up", label: "Channel up", icon: "mdi:plus" },
  ],
  playback: [
    { command: "rewind", label: "Rewind", icon: "mdi:rewind" },
    { command: "play", label: "Play", icon: "mdi:play", tone: "positive" },
    { command: "pause", label: "Pause", icon: "mdi:pause" },
    { command: "stop", label: "Stop", icon: "mdi:stop" },
    { command: "fast_forward", label: "Forward", icon: "mdi:fast-forward" },
  ],
  inputs: [
    { command: "hdmi_1", label: "HDMI 1", icon: "mdi:numeric-1-box" },
    { command: "hdmi_2", label: "HDMI 2", icon: "mdi:numeric-2-box" },
    { command: "hdmi_3", label: "HDMI 3", icon: "mdi:numeric-3-box" },
    { command: "hdmi_4", label: "HDMI 4", icon: "mdi:numeric-4-box" },
  ],
  apps: [
    { command: "app_youtube", label: "YouTube", icon: "mdi:youtube", tone: "youtube" },
    { command: "app_netflix", label: "Netflix", icon: "mdi:netflix", tone: "netflix" },
    { command: "app_amazon", label: "Prime Video", icon: "mdi:amazon", tone: "prime" },
    { command: "app_browser", label: "Browser", icon: "mdi:web" },
  ],
  digits: [
    { command: "digit_1", label: "1", icon: "mdi:numeric-1" },
    { command: "digit_2", label: "2", icon: "mdi:numeric-2" },
    { command: "digit_3", label: "3", icon: "mdi:numeric-3" },
    { command: "digit_4", label: "4", icon: "mdi:numeric-4" },
    { command: "digit_5", label: "5", icon: "mdi:numeric-5" },
    { command: "digit_6", label: "6", icon: "mdi:numeric-6" },
    { command: "digit_7", label: "7", icon: "mdi:numeric-7" },
    { command: "digit_8", label: "8", icon: "mdi:numeric-8" },
    { command: "digit_9", label: "9", icon: "mdi:numeric-9" },
    { command: "digit_0", label: "0", icon: "mdi:numeric-0" },
  ],
};

const buttonMarkup = (control, compact = false) => `
  <button
    type="button"
    class="control ${control.tone || ""} ${compact ? "compact" : ""} ${control.iconOnly ? "icon-only" : ""}"
    data-command="${control.command}"
    ${control.confirm ? `data-confirm="${control.confirm}"` : ""}
    aria-label="${control.label}"
    title="${control.label}"
  >
    <ha-icon icon="${control.icon}"></ha-icon>
    <span>${control.label}</span>
  </button>
`;

const controlFor = (command) =>
  Object.values(CONTROL_GROUPS)
    .flat()
    .find((control) => control.command === command);

class SamsungIPRemoteCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._rendered = false;
    this._statusTimer = null;
    this._textSendChain = Promise.resolve();
    this._compositionInputSeen = false;
    this._controlsEnabled = false;
    this.shadowRoot.addEventListener("click", (event) => this._handleClick(event));
  }

  static getStubConfig() {
    return {
      remote_entity: "remote.samsung_tv_remote",
      media_player_entity: "media_player.samsung_tv",
      name: "Samsung TV",
    };
  }

  setConfig(config) {
    if (!config.remote_entity || !config.media_player_entity) {
      throw new Error("remote_entity and media_player_entity are required");
    }
    this._config = { name: "Samsung TV", ...config };
    this._rendered = false;
    this._controlsEnabled = false;
    if (this.shadowRoot) {
      this.shadowRoot.replaceChildren();
    }
    this._renderIfReady();
  }

  set hass(hass) {
    this._hass = hass;
    this._renderIfReady();
    this._updateState();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._renderIfReady();
  }

  disconnectedCallback() {
    this._clearTransientText();
    if (this._statusTimer) {
      window.clearTimeout(this._statusTimer);
    }
  }

  getCardSize() {
    return 13;
  }

  getGridOptions() {
    return { columns: 12, rows: 14, min_columns: 6, min_rows: 8 };
  }

  _renderIfReady() {
    if (this._rendered || !this._config || !this._hass || !this.isConnected) {
      return;
    }
    this._render();
    this._rendered = true;
    this._updateState();
  }

  _render() {
    const template = document.createElement("template");
    template.innerHTML = `
      <style>
        :host {
          display: block;
          container-type: inline-size;
        }
        * {
          box-sizing: border-box;
        }
        ha-card {
          overflow: hidden;
        }
        .identity {
          min-width: 0;
        }
        .state-dot {
          width: 9px;
          height: 9px;
          border-radius: 50%;
          background: var(--disabled-text-color);
          box-shadow: 0 0 0 4px color-mix(in srgb, var(--disabled-text-color) 18%, transparent);
        }
        h1 {
          overflow: hidden;
          color: var(--primary-text-color);
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .panel-title {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 0 0 12px;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 760;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
        .panel-title ha-icon {
          --mdc-icon-size: 18px;
          color: var(--primary-color);
        }
        .control {
          min-width: 0;
          min-height: 74px;
          padding: 10px 7px;
          border: 1px solid color-mix(in srgb, var(--divider-color) 72%, transparent);
          border-radius: 15px;
          background: color-mix(in srgb, var(--secondary-background-color) 78%, transparent);
          color: var(--primary-text-color);
          font: inherit;
          cursor: pointer;
          transition: transform 120ms ease, border-color 120ms ease, background 120ms ease, box-shadow 120ms ease;
          -webkit-tap-highlight-color: transparent;
        }
        .control:hover {
          border-color: color-mix(in srgb, var(--primary-color) 58%, var(--divider-color));
          background: color-mix(in srgb, var(--primary-color) 10%, var(--secondary-background-color));
          box-shadow: 0 8px 22px rgba(0, 0, 0, 0.1);
          transform: translateY(-1px);
        }
        .control:active {
          transform: scale(0.97);
        }
        .control:focus-visible,
        input:focus-visible {
          outline: 2px solid var(--primary-color);
          outline-offset: 2px;
        }
        .control:disabled {
          cursor: wait;
          opacity: 0.55;
          transform: none;
        }
        .control ha-icon {
          display: block;
          margin: 0 auto 7px;
          --mdc-icon-size: 28px;
          color: var(--primary-color);
        }
        .control span {
          display: block;
          overflow: hidden;
          font-size: 12px;
          font-weight: 680;
          line-height: 1.15;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .control.compact {
          min-height: 62px;
        }
        .control.compact ha-icon {
          --mdc-icon-size: 24px;
          margin-bottom: 5px;
        }
        details {
          margin-top: 10px;
          border-top: 1px solid color-mix(in srgb, var(--divider-color) 68%, transparent);
        }
        summary {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 13px 2px 10px;
          color: var(--primary-text-color);
          font-size: 13px;
          font-weight: 740;
          cursor: pointer;
          list-style: none;
        }
        summary::-webkit-details-marker {
          display: none;
        }
        summary::after {
          content: "›";
          margin-left: auto;
          color: var(--secondary-text-color);
          font-size: 22px;
          transform: rotate(90deg);
          transition: transform 120ms ease;
        }
        details[open] summary::after {
          transform: rotate(-90deg);
        }
        .text-form {
          display: grid;
          grid-template-columns: minmax(0, 1fr);
          gap: 8px;
          align-items: center;
        }
        .text-form input[type="text"] {
          width: 100%;
          min-height: 44px;
          padding: 0 13px;
          border: 1px solid var(--divider-color);
          border-radius: 12px;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          font: inherit;
        }
        .text-form input[type="text"]:disabled {
          opacity: 0.62;
        }
        .privacy-note,
        .action-status {
          margin: 8px 2px 0;
          color: var(--secondary-text-color);
          font-size: 11px;
          line-height: 1.4;
        }
        .action-status {
          min-height: 16px;
          text-align: right;
        }
        @container (max-width: 560px) {
          .key-grid .control span {
            display: none;
          }
          .key-grid .control ha-icon {
            margin-bottom: 0;
          }
        }
        ha-card {
          background: var(--ha-card-background, var(--card-background-color));
          border: 1px solid color-mix(in srgb, var(--divider-color) 76%, transparent);
          border-radius: var(--ha-card-border-radius, 20px);
          box-shadow: 0 24px 60px rgba(0, 0, 0, 0.18);
        }
        .remote-shell {
          padding: 0;
        }
        .remote-header {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 20px 26px;
          border-bottom: 1px solid var(--divider-color);
        }
        .tv-icon {
          display: grid;
          width: 44px;
          height: 44px;
          flex: 0 0 44px;
          place-items: center;
          border: 1px solid var(--divider-color);
          border-radius: 12px;
          background: var(--secondary-background-color);
          color: var(--secondary-text-color);
        }
        .tv-icon ha-icon {
          --mdc-icon-size: 23px;
        }
        .identity h1 {
          margin: 0 0 4px;
          font-size: 17px;
          line-height: 1.2;
        }
        .device-summary {
          color: var(--secondary-text-color);
          font-size: 13px;
          font-variant-numeric: tabular-nums;
        }
        .power-control {
          display: inline-flex;
          min-height: 42px;
          margin-left: auto;
          padding: 0 19px;
          align-items: center;
          gap: 8px;
          border: 1px solid color-mix(in srgb, var(--error-color) 46%, var(--divider-color));
          border-radius: 999px;
          background: color-mix(in srgb, var(--error-color) 11%, transparent);
          color: var(--error-color);
          font: inherit;
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
        }
        .power-control.turn-on {
          border-color: color-mix(in srgb, var(--primary-color) 46%, var(--divider-color));
          background: color-mix(in srgb, var(--primary-color) 11%, transparent);
          color: var(--primary-color);
        }
        .power-control ha-icon {
          --mdc-icon-size: 18px;
        }
        .unavailable-banner {
          display: none;
          align-items: center;
          gap: 10px;
          padding: 11px 26px;
          border-bottom: 1px solid color-mix(in srgb, var(--warning-color, #f0aa3c) 30%, transparent);
          background: color-mix(in srgb, var(--warning-color, #f0aa3c) 10%, transparent);
          color: var(--warning-color, #f0aa3c);
          font-size: 13px;
        }
        .unavailable-banner.visible {
          display: flex;
        }
        .unavailable-banner .state-dot {
          width: 7px;
          height: 7px;
          background: currentColor;
          box-shadow: none;
        }
        .unavailable-banner .wake-button {
          min-height: 32px;
          margin-left: auto;
          padding: 0 13px;
          border: 1px solid currentColor;
          border-radius: 8px;
          background: transparent;
          color: inherit;
          font: inherit;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
        }
        .controls-area {
          display: grid;
          grid-template-areas: "left center right";
          grid-template-columns: minmax(230px, 300px) minmax(260px, 1fr) minmax(230px, 300px);
          gap: 26px;
          padding: 26px;
          transition: opacity 150ms ease;
        }
        .controls-area.inactive {
          opacity: 0.42;
        }
        /* Controls carry the disabled attribute while the TV is off, so pointer
           and keyboard activation are blocked together. Keep them legible at the
           dimmed area opacity instead of stacking the in-flight :disabled fade. */
        .controls-area.inactive .control:disabled {
          cursor: not-allowed;
          opacity: 1;
        }
        .left-stack { grid-area: left; }
        .center-stack { grid-area: center; }
        .right-stack { grid-area: right; }
        .remote-panel {
          padding: 19px;
          border: 1px solid var(--divider-color);
          border-radius: 16px;
          background: color-mix(in srgb, var(--secondary-background-color) 70%, transparent);
        }
        .stack-gap {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .utility-row,
        .channel-controls,
        .playback-controls,
        .input-grid,
        .app-grid,
        .nav-row,
        .key-grid {
          display: grid;
          gap: 9px;
        }
        .utility-row { grid-template-columns: 1fr 1.2fr 1fr; }
        .channel-controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .playback-controls { grid-template-columns: repeat(5, minmax(0, 1fr)); }
        .input-grid, .app-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .nav-row { grid-template-columns: repeat(4, minmax(0, 1fr)); width: min(100%, 272px); }
        .key-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
        .control {
          min-height: 44px;
          padding: 9px 7px;
          border-color: var(--divider-color);
          border-radius: 12px;
          background: var(--secondary-background-color);
          box-shadow: none;
        }
        .control:hover {
          border-color: color-mix(in srgb, var(--primary-color) 48%, var(--divider-color));
          background: color-mix(in srgb, var(--primary-color) 8%, var(--secondary-background-color));
          box-shadow: none;
        }
        .control ha-icon {
          --mdc-icon-size: 20px;
          margin-bottom: 5px;
          color: var(--secondary-text-color);
        }
        .control span {
          font-size: 11px;
          font-weight: 650;
        }
        .utility-row .control,
        .channel-controls .control {
          min-height: 44px;
        }
        .utility-row .control ha-icon,
        .channel-controls .control ha-icon,
        .playback-controls .control ha-icon {
          margin: 0 auto;
        }
        .utility-row .control span,
        .channel-controls .control span,
        .playback-controls .control span {
          display: none;
        }
        .playback-controls .control.positive {
          background: var(--secondary-background-color);
          border-color: var(--divider-color);
          color: var(--primary-text-color);
        }
        .playback-controls .control.positive ha-icon {
          color: var(--secondary-text-color);
        }
        .utility-row [data-command="mute"] span {
          display: block;
        }
        .utility-row [data-command="mute"] ha-icon {
          display: none;
        }
        .control.active {
          border-color: var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 12%, var(--secondary-background-color));
          color: var(--primary-color);
        }
        .control.active ha-icon {
          color: var(--primary-color);
        }
        .center-stack {
          display: flex;
          min-width: 0;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 19px;
        }
        .dpad-disc {
          position: relative;
          width: 244px;
          height: 244px;
          border: 1px solid var(--divider-color);
          border-radius: 50%;
          background: radial-gradient(circle at 50% 40%, var(--secondary-background-color), color-mix(in srgb, var(--card-background-color) 88%, #000));
          box-shadow: inset 0 2px 10px rgba(255, 255, 255, 0.03), 0 10px 30px rgba(0, 0, 0, 0.18);
        }
        .dpad-disc .control {
          position: absolute;
          min-height: 0;
          border: 0;
          background: transparent;
        }
        .dpad-disc .control span { display: none; }
        .dpad-disc .control ha-icon { --mdc-icon-size: 27px; margin: 0; }
        .dpad-disc [data-command="up"], .dpad-disc [data-command="down"] {
          left: 50%; width: 90px; height: 64px; transform: translateX(-50%);
        }
        .dpad-disc [data-command="up"] { top: 8px; border-radius: 44px 44px 14px 14px; }
        .dpad-disc [data-command="down"] { bottom: 8px; border-radius: 14px 14px 44px 44px; }
        .dpad-disc [data-command="left"], .dpad-disc [data-command="right"] {
          top: 50%; width: 64px; height: 90px; transform: translateY(-50%);
        }
        .dpad-disc [data-command="left"] { left: 8px; border-radius: 44px 14px 14px 44px; }
        .dpad-disc [data-command="right"] { right: 8px; border-radius: 14px 44px 44px 14px; }
        .dpad-disc [data-command="enter"] {
          top: 50%; left: 50%; width: 98px; height: 98px;
          transform: translate(-50%, -50%);
          border: 1px solid var(--divider-color);
          border-radius: 50%;
          background: var(--secondary-background-color);
        }
        .dpad-disc [data-command="enter"] ha-icon { display: none; }
        .dpad-disc [data-command="enter"] span { display: block; font-size: 15px; }
        .nav-row .control { min-height: 60px; }
        .input-grid .control { min-height: 80px; }
        .app-grid .control { min-height: 43px; }
        .app-grid .control ha-icon { display: none; }
        details {
          margin-top: 13px;
        }
        .text-footer {
          display: grid;
          grid-template-columns: auto minmax(180px, 1fr) minmax(240px, auto);
          gap: 14px;
          align-items: center;
          margin: 0 26px 26px;
          padding: 14px 18px;
          border: 1px solid var(--divider-color);
          border-radius: 16px;
          background: color-mix(in srgb, var(--secondary-background-color) 70%, transparent);
        }
        .text-label {
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 760;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
        .text-form input[type="text"] {
          background: var(--secondary-background-color);
        }
        .text-capability {
          margin: 0;
          max-width: 360px;
        }
        .action-status {
          grid-column: 1 / -1;
          margin: 0;
        }
        @container (max-width: 880px) {
          .controls-area {
            grid-template-areas: "center center" "left right";
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        @container (max-width: 620px) {
          .remote-header { padding: 14px 16px; }
          .tv-icon { width: 40px; height: 40px; flex-basis: 40px; }
          .power-control { width: 48px; min-height: 48px; padding: 0; justify-content: center; }
          .power-control span { display: none; }
          .controls-area {
            grid-template-areas: "center" "left" "right";
            grid-template-columns: 1fr;
            gap: 14px;
            padding: 16px;
          }
          .left-stack { display: grid; grid-template-columns: 1fr; }
          .remote-panel { padding: 14px; }
          .text-footer {
            grid-template-columns: 1fr;
            margin: 0 16px 16px;
          }
          .text-capability { max-width: none; }
          .dpad-disc { width: 230px; height: 230px; }
          .nav-row { width: 100%; }
          .nav-row .control { min-height: 62px; }
          .input-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
          .input-grid .control { min-height: 68px; }
          .input-grid .control span { font-size: 9px; }
          .app-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
          .app-grid .control span { font-size: 10px; }
        }
      </style>
      <ha-card>
        <div class="remote-shell">
          <header class="remote-header">
            <div class="tv-icon"><ha-icon icon="mdi:television"></ha-icon></div>
            <div class="identity">
              <h1></h1>
              <div class="device-summary">Unavailable</div>
            </div>
            <button type="button" class="power-control turn-on" data-command="power_on" aria-label="Turn on" title="Turn on">
              <ha-icon icon="mdi:power"></ha-icon><span>Turn on</span>
            </button>
          </header>
          <div class="unavailable-banner"><span class="state-dot"></span><span>The TV is unreachable. Send Wake-on-LAN and retry local control.</span><button type="button" class="wake-button" data-command="power_on">Wake</button></div>
          <div class="controls-area">
            <div class="left-stack stack-gap">
              <section class="remote-panel">
                <h2 class="panel-title">Volume</h2>
                <div class="utility-row">${["volume_down", "mute", "volume_up"].map((command) => buttonMarkup(controlFor(command), true)).join("")}</div>
                <h2 class="panel-title" style="margin-top:16px">Channel</h2>
                <div class="channel-controls">${["channel_down", "channel_up"].map((command) => buttonMarkup(controlFor(command), true)).join("")}</div>
              </section>
              <section class="remote-panel">
                <h2 class="panel-title">Playback</h2>
                <div class="playback-controls">${CONTROL_GROUPS.playback.map((item) => buttonMarkup(item, true)).join("")}</div>
              </section>
            </div>
            <div class="center-stack">
              <div class="dpad-disc">${["up", "down", "left", "right", "enter"].map((command) => buttonMarkup(controlFor(command))).join("")}</div>
              <div class="nav-row">${["back", "home", "menu", "exit"].map((command) => buttonMarkup(controlFor(command), true)).join("")}</div>
            </div>
            <div class="right-stack stack-gap">
              <section class="remote-panel">
                <h2 class="panel-title">Input source</h2>
              <div class="input-grid">${CONTROL_GROUPS.inputs.map((item) => buttonMarkup(item, true)).join("")}</div>
              </section>
              <section class="remote-panel">
              <h2 class="panel-title">Apps</h2>
              <div class="app-grid">${CONTROL_GROUPS.apps.map((item) => buttonMarkup(item, true)).join("")}</div>
              <details>
                <summary><ha-icon icon="mdi:dialpad"></ha-icon>Number pad</summary>
                <div class="key-grid">${CONTROL_GROUPS.digits.map((item) => buttonMarkup(item, true)).join("")}</div>
              </details>
              </section>
            </div>
          </div>
          <section class="text-footer">
            <span class="text-label">Text input</span>
            <div class="text-form"><input type="text" maxlength="200" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" data-1p-ignore data-lpignore="true" aria-label="Text to send to the active Samsung system field" placeholder="Pair system text from Configure first" /></div>
            <p class="privacy-note text-capability">Text input status unavailable.</p>
            <p class="action-status" aria-live="polite"></p>
          </section>
        </div>
      </ha-card>
    `;
    this.shadowRoot.appendChild(template.content.cloneNode(true));
    this.shadowRoot.querySelector("h1").textContent = this._config.name;
    const textInput = this.shadowRoot.querySelector(".text-form input[type='text']");
    textInput.addEventListener("compositionstart", () => {
      this._compositionInputSeen = false;
    });
    textInput.addEventListener("input", (event) => {
      if (event.isComposing) {
        this._compositionInputSeen = true;
      }
      this._queueText(event);
    });
    textInput.addEventListener("compositionend", (event) => {
      if (!this._compositionInputSeen) {
        this._queueText(event);
      }
      this._compositionInputSeen = false;
    });
    textInput.addEventListener("blur", () => this._clearTransientText());
  }

  _updateState() {
    if (!this._rendered || !this._hass) {
      return;
    }
    const media = this._hass.states[this._config.media_player_entity];
    const remote = this._hass.states[this._config.remote_entity];
    const state = media?.state || remote?.state || "unavailable";
    const source = media?.attributes?.source;
    const volume = media?.attributes?.volume_level;
    const muted = media?.attributes?.is_volume_muted;
    const textEnabled = remote?.attributes?.text_input_enabled === true;
    const securePage = window.location.protocol === "https:";
    const isOn = state === "on";
    const isUnavailable = state !== "on" && state !== "off";
    // The integration owns surface tracking so every dashboard and browser
    // agrees on what is actually on screen. Samsung keeps reporting the
    // underlying HDMI input while Home or an application owns the panel.
    const surface = remote?.attributes?.surface ?? null;
    const displayedSource = surface || source;
    const summary = isOn
      ? ["On", displayedSource, typeof volume === "number" ? `Volume ${Math.round(volume * 100)}%` : null, muted ? "Muted" : null]
          .filter(Boolean)
          .join(" · ")
      : state === "off"
        ? "Off · press power to turn on"
        : "Unavailable";

    this.shadowRoot.querySelector(".device-summary").textContent = summary;
    this.shadowRoot.querySelector(".controls-area").classList.toggle("inactive", !isOn);
    this._controlsEnabled = isOn;
    for (const button of this.shadowRoot.querySelectorAll(".controls-area .control")) {
      if (button.dataset.busy !== "true") {
        button.disabled = !isOn;
      }
    }
    this.shadowRoot.querySelector(".unavailable-banner").classList.toggle("visible", isUnavailable);

    const powerButton = this.shadowRoot.querySelector(".power-control");
    const powerCommand = isOn ? "power_off" : "power_on";
    const powerLabel = isOn ? "Turn off" : "Turn on";
    powerButton.dataset.command = powerCommand;
    powerButton.dataset.confirm = isOn ? "Turn off the Samsung TV?" : "";
    powerButton.setAttribute("aria-label", powerLabel);
    powerButton.setAttribute("title", powerLabel);
    powerButton.querySelector("span").textContent = powerLabel;
    powerButton.classList.toggle("turn-on", !isOn);

    this.shadowRoot.querySelector('[data-command="mute"]').classList.toggle("active", muted === true);
    for (const button of this.shadowRoot.querySelectorAll('.input-grid [data-command^="hdmi_"]')) {
      const expectedSource = button.dataset.command.replace("hdmi_", "HDMI ");
      button.classList.toggle("active", !surface && source === expectedSource);
    }

    const textInput = this.shadowRoot.querySelector(".text-form input[type='text']");
    textInput.disabled = !textEnabled || !isOn;
    textInput.placeholder = !textEnabled
      ? "Enable system text from Configure"
      : isOn
        ? "Type to send text…"
        : "Text input is unavailable while the TV is off";
    this.shadowRoot.querySelector(".text-capability").textContent = textEnabled
      ? !isOn
        ? "Text input is unavailable while the TV is off or unreachable."
        : securePage
          ? "Live typing into compatible Samsung text fields · up to 200 characters · clears on blur. Your browser, keyboard, Home Assistant host, network, any reverse proxy, and the TV all handle the text while it is sent."
          : "Insecure connection (HTTP) · text is sent unencrypted. Access Home Assistant over HTTPS for sensitive typing."
      : "System text is disabled. Open the integration's Configure flow and accept the separate TV prompt.";
  }

  async _handleClick(event) {
    const button = event.target.closest("button[data-command]");
    if (!button || !this._hass || button.disabled) {
      return;
    }
    const confirmation = button.dataset.confirm;
    if (confirmation && !window.confirm(confirmation)) {
      return;
    }
    const actionLabel = button.getAttribute("aria-label");
    const locksButton = ["power_on", "power_off"].includes(button.dataset.command);
    if (locksButton) {
      button.dataset.busy = "true";
      button.disabled = true;
    }
    this._setActionStatus(`Sending ${actionLabel}…`);
    try {
      await this._hass.callService("remote", "send_command", {
        entity_id: this._config.remote_entity,
        command: button.dataset.command,
      });
      this._setActionStatus(`${actionLabel} sent.`);
    } catch (_error) {
      this._setActionStatus("The TV command failed. Check Home Assistant logs.", true);
    } finally {
      if (locksButton) {
        delete button.dataset.busy;
        button.disabled = button.classList.contains("control") && !this._controlsEnabled;
      }
    }
  }

  _queueText(event) {
    if (!this._hass) {
      return;
    }
    const input = event.currentTarget;
    const text = input.value;
    const length = Array.from(text).length;
    if (length > 200 || /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/u.test(text)) {
      this._setActionStatus("Text must contain up to 200 printable characters.", true);
      return;
    }
    this._textSendChain = this._textSendChain
      .catch(() => undefined)
      .then(() => this._syncText(text));
  }

  async _syncText(text) {
    if (!this._hass || !this.isConnected) {
      return;
    }
    try {
      await this._hass.callApi("post", "samsung_ip_control/sensitive_text", {
        entity_id: this._config.remote_entity,
        password: text,
      });
      this._setActionStatus("Samsung text synchronized.");
    } catch (_error) {
      this._setActionStatus("Text sync failed. Confirm a supported Samsung field is active.", true);
    }
  }

  _clearTransientText() {
    const input = this.shadowRoot?.querySelector(".text-form input[type='text']");
    if (input) {
      input.value = "";
    }
  }

  _setActionStatus(message, isError = false) {
    const status = this.shadowRoot.querySelector(".action-status");
    if (!status) {
      return;
    }
    status.textContent = message;
    status.style.color = isError ? "var(--error-color)" : "var(--secondary-text-color)";
    if (this._statusTimer) {
      window.clearTimeout(this._statusTimer);
    }
    this._statusTimer = window.setTimeout(() => {
      status.textContent = "";
    }, 5000);
  }
}

if (!customElements.get("samsung-ip-remote-card")) {
  customElements.define("samsung-ip-remote-card", SamsungIPRemoteCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "samsung-ip-remote-card")) {
  window.customCards.push({
    type: "samsung-ip-remote-card",
    name: "Samsung TV IP Control Remote",
    description: "A responsive first-party remote for Samsung TV IP Control.",
    preview: true,
    documentationURL: "https://github.com/anjulahettige/home-assistant-samsung-tv-ip-control",
  });
}

console.info(`%c SAMSUNG-IP-REMOTE-CARD %c ${SAMSUNG_IP_REMOTE_CARD_VERSION} `, "color: white; background: #1473e6; font-weight: 700;", "color: #1473e6; background: transparent;");
