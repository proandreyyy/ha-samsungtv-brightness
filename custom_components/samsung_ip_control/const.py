"""Constants for Samsung TV IP Control."""

from __future__ import annotations

DOMAIN = "samsung_ip_control"

CONF_TOKEN = "token"
CONF_CERTIFICATE_FINGERPRINT = "certificate_fingerprint"
CONF_ENTITY_IDENTITY = "entity_identity"
CONF_SERIAL_HASH = "serial_hash"
CONF_TEXT_INPUT_ENABLED = "text_input_enabled"
CONF_TEXT_INPUT_PORT = "text_input_port"
CONF_TEXT_INPUT_TOKEN = "text_input_token"
CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT = "text_input_certificate_fingerprint"
DEFAULT_NAME = "Samsung TV"
DEFAULT_PORT = 1516
DEFAULT_SCAN_INTERVAL = 10

PLATFORMS = ["media_player", "remote"]

SOURCE_TO_API = {
    "HDMI 1": "HDMI1",
    "HDMI 2": "HDMI2",
    "HDMI 3": "HDMI3",
    "HDMI 4": "HDMI4",
}
API_TO_SOURCE = {value: key for key, value in SOURCE_TO_API.items()}

REMOTE_KEY_TO_API = {
    "up": "cursorUp",
    "down": "cursorDn",
    "left": "cursorLeft",
    "right": "cursorRight",
    "menu": "menu",
    "home": "firstScreen",
    "enter": "enter",
    "back": "return",
    "exit": "exit",
    "play": "play",
    "pause": "pause",
    "stop": "stop",
    "fast_forward": "fastforward",
    "rewind": "rewind",
    "power_toggle": "power",
    "digit_0": "number0",
    "digit_1": "number1",
    "digit_2": "number2",
    "digit_3": "number3",
    "digit_4": "number4",
    "digit_5": "number5",
    "digit_6": "number6",
    "digit_7": "number7",
    "digit_8": "number8",
    "digit_9": "number9",
    "caption": "caption",
    "dash": "dash",
    "red": "red",
    "green": "green",
    "yellow": "yellow",
    "blue": "blue",
    "ambient": "ambient",
    "multiview": "multiview",
}

APP_TO_API = {
    "browser": "webBrowser",
    "netflix": "netflix",
    "amazon": "amazon",
    "vudu": "VUDU",
    "vudu_alt": "vudu",
    "pandora": "pandora",
    "youtube": "youTube",
    "hulu": "hulu",
}

APP_ALIASES = {
    "web_browser": "browser",
    "amazon_prime": "amazon",
    "amazon_prime_video": "amazon",
    "prime_video": "amazon",
}

APP_COMMANDS = tuple(f"app_{app}" for app in APP_TO_API)

# Samsung keeps reporting the underlying HDMI input while Home or an application
# owns the screen, so the integration tracks the surface it last commanded and
# reports it alongside the polled input.
SURFACE_HOME = "Home"

APP_SURFACES = {
    "app_browser": "Browser",
    "app_netflix": "Netflix",
    "app_amazon": "Prime Video",
    "app_vudu": "Vudu",
    "app_vudu_alt": "Vudu",
    "app_pandora": "Pandora",
    "app_youtube": "YouTube",
    "app_hulu": "Hulu",
}

# Samsung's volume scale is 0-100 and its step buttons move exactly one unit.
VOLUME_STEP = 0.01

REMOTE_COMMANDS = (
    *REMOTE_KEY_TO_API,
    "volume_up",
    "volume_down",
    "mute",
    "channel_up",
    "channel_down",
    "hdmi_1",
    "hdmi_2",
    "hdmi_3",
    "hdmi_4",
    "power_on",
    "power_off",
    *APP_COMMANDS,
)
