# Contributing

Contributions are welcome, especially compatibility reports for additional Samsung models and firmware.

## Contribution license

By submitting code, documentation, or another copyrightable contribution for inclusion, you agree to license that contribution under the repository's [MIT License](LICENSE) and confirm that you have the right to do so. Do not submit material whose license conflicts with these terms.

## Before opening an issue

1. Read [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md), [docs/COMMANDS.md](docs/COMMANDS.md), and [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
2. Confirm that the TV exposes the local HTTPS service on port `1516`.
3. Reproduce the problem using the Home Assistant remote entity before adding Harmony.
4. Remove tokens, serial numbers, IP addresses, MAC addresses, hostnames, household names, and entered text from logs and screenshots.

## Feature requests

Use the feature-request issue form and describe the personal need, expected behavior, and affected integration area. Include a sanitized Samsung model identifier and firmware version when the request depends on TV capabilities. New protocol commands require an official contract or repeatable, sanitized hardware evidence.

## Development

1. Fork and clone the repository.
2. Create a focused branch.
3. Keep protocol commands inside the explicit allowlist.
4. Add or update tests.
5. Install the pinned development dependency:

```sh
python3 -m pip install --disable-pip-version-check --requirement requirements-dev.txt
```

6. Run:

```sh
python3 -m unittest discover -s tests -v
```

7. Run Ruff:

```sh
ruff check .
```

```sh
ruff format --check .
```

8. Update the relevant documentation and changelog.
9. Complete the applicable manual acceptance layers in [docs/TESTING.md](docs/TESTING.md).

The integration deliberately installs no separate Python runtime package. It uses Home Assistant's provided HTTP runtime for the optional WebSocket path. Discuss any new runtime dependency and its maintenance, license, update, and supply-chain impact before adding it to `manifest.json`.

## Compatibility reports

Include:

- Home Assistant version and installation type.
- Samsung model identifier and firmware version.
- Whether IP Remote is enabled and port 1516 is reachable.
- Which commands and apps produced JSON-RPC acceptance, visible physical success, unsupported behavior, or failure.
- The TV sales region and whether each tested app was installed, without including a Samsung or app account name.
- Whether optional text input paired separately, which application field was active, and whether characters and submit worked. Do not include the entered phrase.
- Whether Wake-on-LAN used a wired or wireless MAC.
- Harmony model and Hub firmware when relevant.

Exclude serial numbers, tokens, certificates, network addresses, entered text, and personally identifying device names.
