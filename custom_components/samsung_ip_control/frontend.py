"""Frontend resources for Samsung TV IP Control."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

FRONTEND_URL = "/samsung_ip_control_static/samsung-ip-remote-card.js"
FRONTEND_FILE = Path(__file__).parent / "frontend" / "samsung-ip-remote-card.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the optional first-party remote card without caching stale releases."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(FRONTEND_FILE), cache_headers=False)]
    )
