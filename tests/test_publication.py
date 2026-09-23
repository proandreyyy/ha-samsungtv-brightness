"""Release-shape, workflow, and privacy checks for the public repository."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import re
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "custom_components" / "samsung_ip_control" / "manifest.json"
BRAND_ICON = ROOT / "custom_components" / "samsung_ip_control" / "brand" / "icon.png"
PUBLICATION_TEST = Path(__file__).resolve()
IPV4_PATTERN = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
MAC_PATTERN = re.compile(
    r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])"
)
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
HOME_PATH_PATTERN = re.compile(r"(?:/Users/|/home/)[^/\s]+/")
CONFIG_ENTRY_ID_PATTERN = re.compile(r"\b01[0-9A-HJKMNP-TV-Z]{24}\b")
SECRET_PATTERNS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "JWT": re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
    ),
}
RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
DOCUMENTATION_MACS = {"00:00:5E:00:53:01"}
const_spec = importlib.util.spec_from_file_location(
    "publication_const",
    ROOT / "custom_components" / "samsung_ip_control" / "const.py",
)
if const_spec is None or const_spec.loader is None:
    raise RuntimeError("Could not load integration constants")
const_module = importlib.util.module_from_spec(const_spec)
const_spec.loader.exec_module(const_module)
REMOTE_COMMANDS = set(const_module.REMOTE_COMMANDS)

HARMONY_EXPECTED_COMMANDS = {
    "down",
    "enter",
    "hdmi_1",
    "hdmi_2",
    "hdmi_3",
    "hdmi_4",
    "home",
    "left",
    "mute",
    "power_off",
    "power_on",
    "right",
    "up",
    "volume_down",
    "volume_up",
}
DOCUMENTED_EXTENDED_COMMANDS = {
    "ambient",
    "app_amazon",
    "app_browser",
    "app_hulu",
    "app_netflix",
    "app_pandora",
    "app_vudu",
    "app_vudu_alt",
    "app_youtube",
    "back",
    "blue",
    "brightness_down",
    "brightness_up",
    "caption",
    "channel_down",
    "channel_up",
    "dash",
    "digit_0",
    "digit_1",
    "digit_2",
    "digit_3",
    "digit_4",
    "digit_5",
    "digit_6",
    "digit_7",
    "digit_8",
    "digit_9",
    "exit",
    "fast_forward",
    "green",
    "menu",
    "multiview",
    "pause",
    "play",
    "power_toggle",
    "red",
    "rewind",
    "stop",
    "yellow",
}
DASHBOARD_HIDDEN_COMMANDS = {
    "ambient",
    "app_hulu",
    "app_pandora",
    "app_vudu",
    "app_vudu_alt",
    "blue",
    "brightness_down",
    "brightness_up",
    "caption",
    "dash",
    "green",
    "multiview",
    "power_toggle",
    "red",
    "yellow",
}
EXPECTED_REMOTE_KEYS = {
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
EXPECTED_APPS = {
    "browser": "webBrowser",
    "netflix": "netflix",
    "amazon": "amazon",
    "vudu": "VUDU",
    "vudu_alt": "vudu",
    "pandora": "pandora",
    "youtube": "youTube",
    "hulu": "hulu",
}
IGNORED_PARTS = {".git", ".ruff_cache", ".venv", "__pycache__", "htmlcov"}


def repository_files() -> list[Path]:
    """Return publishable tracked and untracked files, excluding ignored files."""
    if (ROOT / ".git").is_dir():
        result = subprocess.run(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        paths = [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]
        return [path for path in paths if path.is_file()]
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not IGNORED_PARTS.intersection(path.relative_to(ROOT).parts)
    ]


def text_files() -> list[tuple[Path, str]]:
    """Read repository text files without attempting to decode binary artifacts."""
    files: list[tuple[Path, str]] = []
    for path in repository_files():
        if path.resolve() == PUBLICATION_TEST:
            continue
        content = path.read_bytes()
        if b"\0" in content:
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        files.append((path, text))
    return files


class PublicationTests(unittest.TestCase):
    def test_manifest_has_public_repository_fields(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        required = {
            "domain",
            "name",
            "codeowners",
            "config_flow",
            "documentation",
            "integration_type",
            "iot_class",
            "issue_tracker",
            "version",
        }
        self.assertFalse(required - manifest.keys())
        self.assertEqual(manifest["domain"], "samsung_ip_control")
        self.assertEqual(manifest["requirements"], [])
        self.assertEqual(manifest["dependencies"], ["http"])

    def test_hacs_brand_icon_is_valid_square_png(self) -> None:
        content = BRAND_ICON.read_bytes()
        self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(content[12:16], b"IHDR")
        width, height = struct.unpack(">II", content[16:24])
        self.assertEqual((width, height), (512, 512))

    def test_release_uses_mit_license(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Copyright (c) 2026 Anjula Hettige", license_text)
        self.assertIn("Permission is hereby granted, free of charge", license_text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', license_text)
        self.assertIn("open-source", readme)
        self.assertIn("MIT License", readme)

    def test_repository_contains_no_sensitive_metadata_or_credentials(self) -> None:
        findings: list[str] = []
        for path, text in text_files():
            relative_path = path.relative_to(ROOT)
            for match in IPV4_PATTERN.finditer(text):
                try:
                    address = ipaddress.ip_address(match.group())
                except ValueError:
                    continue
                if any(address in network for network in RFC1918_NETWORKS):
                    findings.append(f"{relative_path}: private IPv4 address")
            for match in MAC_PATTERN.finditer(text):
                normalized = match.group().replace("-", ":").upper()
                if normalized not in DOCUMENTATION_MACS:
                    findings.append(f"{relative_path}: MAC address")
            if EMAIL_PATTERN.search(text):
                findings.append(f"{relative_path}: email address")
            if HOME_PATH_PATTERN.search(text):
                findings.append(f"{relative_path}: user home path")
            if CONFIG_ENTRY_ID_PATTERN.search(text):
                findings.append(f"{relative_path}: Home Assistant config entry ID")
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{relative_path}: {label}")
        self.assertEqual(findings, [])

    def test_repository_contains_no_symlinks(self) -> None:
        symlinks = [
            str(path.relative_to(ROOT))
            for path in repository_files()
            if path.is_symlink()
        ]
        self.assertEqual(symlinks, [])

    def test_setup_form_uses_stable_device_identity(self) -> None:
        text = (
            ROOT / "custom_components" / "samsung_ip_control" / "config_flow.py"
        ).read_text(encoding="utf-8")
        self.assertIn('serial = device_information["serial"]', text)
        self.assertIn("self._abort_if_unique_id_configured()", text)
        self.assertIn("identity = serial or mac or host.casefold()", text)
        self.assertNotIn("identity = mac or host", text)

    def test_diagnostics_redact_private_device_metadata(self) -> None:
        text = (
            ROOT / "custom_components" / "samsung_ip_control" / "diagnostics.py"
        ).read_text(encoding="utf-8")
        for constant in (
            "CONF_CERTIFICATE_FINGERPRINT",
            "CONF_ENTITY_IDENTITY",
            "CONF_HOST",
            "CONF_MAC",
            "CONF_NAME",
            "CONF_SERIAL_HASH",
            "CONF_TEXT_INPUT_CERTIFICATE_FINGERPRINT",
            "CONF_TEXT_INPUT_TOKEN",
            "CONF_TOKEN",
            '"options"',
            '"serial"',
            '"speaker"',
        ):
            self.assertIn(constant, text)

    def test_action_platforms_limit_parallel_updates(self) -> None:
        for filename in ("media_player.py", "remote.py"):
            text = (
                ROOT / "custom_components" / "samsung_ip_control" / filename
            ).read_text(encoding="utf-8")
            self.assertIn("PARALLEL_UPDATES = 1", text)

    def test_external_github_actions_are_pinned_to_commit_shas(self) -> None:
        findings: list[str] = []
        for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
            for line_number, line in enumerate(
                workflow.read_text(encoding="utf-8").splitlines(), start=1
            ):
                match = re.search(r"\buses:\s*([^\s]+)", line)
                if not match or match.group(1).startswith("./"):
                    continue
                reference = match.group(1).rsplit("@", 1)[-1]
                if not re.fullmatch(r"[0-9a-f]{40}", reference):
                    findings.append(f"{workflow.name}:{line_number}")
        self.assertEqual(findings, [])

    def test_documented_shell_commands_use_one_line_per_code_block(self) -> None:
        findings: list[str] = []
        for path, text in text_files():
            if path.suffix != ".md":
                continue
            for block_number, match in enumerate(
                re.finditer(
                    r"```(?:sh|bash|shell|zsh|console)\s*\n(.*?)```",
                    text,
                    re.DOTALL | re.IGNORECASE,
                ),
                start=1,
            ):
                lines = [line for line in match.group(1).splitlines() if line.strip()]
                if len(lines) != 1:
                    findings.append(
                        f"{path.relative_to(ROOT)}: shell block {block_number}"
                    )
        self.assertEqual(findings, [])

    def test_text_input_service_is_optional_and_bounded(self) -> None:
        service = (
            ROOT / "custom_components" / "samsung_ip_control" / "services.yaml"
        ).read_text(encoding="utf-8")
        services_module = (
            ROOT / "custom_components" / "samsung_ip_control" / "services.py"
        ).read_text(encoding="utf-8")
        text_client = (
            ROOT / "custom_components" / "samsung_ip_control" / "text_client.py"
        ).read_text(encoding="utf-8")
        sensitive_text_module = (
            ROOT / "custom_components" / "samsung_ip_control" / "sensitive_text.py"
        ).read_text(encoding="utf-8")
        icons = json.loads(
            (
                ROOT / "custom_components" / "samsung_ip_control" / "icons.json"
            ).read_text(encoding="utf-8")
        )
        self.assertIn("send_text:", service)
        self.assertIn("Do not use this action for passwords", service)
        self.assertIn("async_register_platform_entity_service", services_module)
        self.assertIn("MAX_TEXT_LENGTH", services_module)
        self.assertIn("_validate_printable_text", services_module)
        self.assertIn("Fingerprint(bytes.fromhex(fingerprint))", text_client)
        self.assertNotIn("SmartThings", text_client)
        self.assertNotIn("custom.remote.textReceived", text_client)
        self.assertIn('vol.Required("password")', sensitive_text_module)
        self.assertIn("POLICY_CONTROL", sensitive_text_module)
        self.assertIn("requires_auth = True", sensitive_text_module)
        self.assertIn('"Cache-Control": "no-store"', sensitive_text_module)
        self.assertNotIn("EVENT_CALL_SERVICE", sensitive_text_module)
        self.assertNotIn("hass.services", sensitive_text_module)
        self.assertNotIn("_LOGGER", sensitive_text_module)
        self.assertEqual(
            icons["services"]["send_text"]["service"],
            "mdi:form-textbox",
        )

    def test_dashboard_uses_supported_remote_commands(self) -> None:
        dashboard = (
            ROOT / "examples" / "dashboards" / "samsung-tv-remote.yaml"
        ).read_text(encoding="utf-8")
        native_dashboard = (
            ROOT / "examples" / "dashboards" / "samsung-tv-remote-native.yaml"
        ).read_text(encoding="utf-8")
        remote_card = (
            ROOT
            / "custom_components"
            / "samsung_ip_control"
            / "frontend"
            / "samsung-ip-remote-card.js"
        ).read_text(encoding="utf-8")
        commands = set(re.findall(r'command: "([a-z0-9_]+)"', remote_card))
        native_commands = set(
            re.findall(
                r"^\s+command: ([a-z0-9_]+)$",
                native_dashboard,
                re.MULTILINE,
            )
        )
        self.assertEqual(commands, REMOTE_COMMANDS - DASHBOARD_HIDDEN_COMMANDS)
        self.assertEqual(len(commands), 39)
        self.assertTrue(HARMONY_EXPECTED_COMMANDS <= native_commands)
        self.assertTrue(native_commands <= REMOTE_COMMANDS)
        self.assertIn("custom:samsung-ip-remote-card", dashboard)
        self.assertIn(
            'callApi("post", "samsung_ip_control/sensitive_text"', remote_card
        )
        self.assertIn("password: text", remote_card)
        self.assertNotIn("callWS", remote_card)
        self.assertNotIn(
            'callService("samsung_ip_control", "send_text"',
            remote_card,
        )
        self.assertNotIn("localStorage", remote_card)
        self.assertNotIn("sessionStorage", remote_card)
        self.assertNotIn("eval(", remote_card)
        self.assertNotIn("send-button", remote_card)
        self.assertNotIn("finish-input", remote_card)
        self.assertNotIn("live-input", remote_card)
        self.assertNotIn("_lastSyncedText", remote_card)
        self.assertNotIn("!this._hass || event.isComposing", remote_card)
        self.assertIn('addEventListener("compositionend"', remote_card)
        self.assertIn('autocorrect="off"', remote_card)
        self.assertNotIn("Extended controls", remote_card)
        self.assertNotIn('label: "Hulu"', remote_card)
        self.assertNotIn('label: "Vudu"', remote_card)
        self.assertNotIn('label: "Pandora"', remote_card)

    def test_remote_exposes_documented_extended_keys_and_apps(self) -> None:
        self.assertEqual(
            REMOTE_COMMANDS,
            HARMONY_EXPECTED_COMMANDS | DOCUMENTED_EXTENDED_COMMANDS,
        )
        self.assertEqual(len(REMOTE_COMMANDS), 54)
        self.assertEqual(const_module.REMOTE_KEY_TO_API, EXPECTED_REMOTE_KEYS)
        self.assertEqual(const_module.APP_TO_API, EXPECTED_APPS)
        commands_doc = (ROOT / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
        dashboard = (
            ROOT / "examples" / "dashboards" / "samsung-tv-remote.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("`app_youtube`", commands_doc)
        self.assertIn("custom:samsung-ip-remote-card", dashboard)

    def test_harmony_example_routes_exact_remote_allowlist(self) -> None:
        automation = (
            ROOT / "examples" / "automations" / "harmony_samsung_ip_control.yaml"
        ).read_text(encoding="utf-8")
        map_block = automation.split("    tv_command_map:", 1)[1].split("  mode:", 1)[0]
        mapped = set(
            re.findall(r"^      [A-Za-z]+: ([a-z0-9_]+)$", map_block, re.MULTILINE)
        )
        action_commands = set(
            re.findall(r"^\s+command: ([a-z0-9_]+)$", automation, re.MULTILINE)
        )
        self.assertEqual(mapped | action_commands, HARMONY_EXPECTED_COMMANDS)
        self.assertFalse((mapped | action_commands) & DOCUMENTED_EXTENDED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
