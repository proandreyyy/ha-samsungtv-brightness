"""State coordinator for Samsung TV IP Control."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    SamsungIPControlAuthError,
    SamsungIPControlClient,
    SamsungIPControlError,
    mute_from_api,
    source_from_api,
)
from .const import (
    APP_ALIASES,
    APP_SURFACES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SURFACE_HOME,
    VOLUME_STEP,
)

_LOGGER = logging.getLogger(__name__)


class SamsungIPControlCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll local state without performing I/O in entity properties."""

    def __init__(self, hass: HomeAssistant, client: SamsungIPControlClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            always_update=False,
        )
        self.client = client
        self.device_information: dict[str, str] = {}
        self._surface: str | None = None
        self._surface_source: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            powered_on = await self.client.async_get_power()
            states: dict[str, Any] = {}
            if powered_on:
                states = await self.client.async_get_states()
            if not self.device_information:
                self.device_information = (
                    await self.client.async_get_device_information()
                )
        except SamsungIPControlAuthError as ex:
            raise ConfigEntryAuthFailed(
                "The Samsung TV access token was rejected"
            ) from ex
        except SamsungIPControlError as ex:
            raise UpdateFailed(str(ex)) from ex

        volume = states.get("volume")
        try:
            volume_level = max(0.0, min(1.0, float(volume) / 100.0))
        except TypeError, ValueError:
            volume_level = None

        source = source_from_api(states.get("inputSource"))
        # A wake starts on Home before Samsung reports the underlying input.
        # Bind that surface to the first source reading, then clear it only if
        # the physical input genuinely changes later.
        if not powered_on:
            self._surface = None
            self._surface_source = None
        elif self._surface is not None and self._surface_source is None:
            self._surface_source = source
        elif self._surface is not None and source != self._surface_source:
            self._surface = None
            self._surface_source = None

        return {
            "power": powered_on,
            "volume_level": volume_level,
            "muted": mute_from_api(states.get("mute")),
            "source": source,
            "surface": self._surface,
            "picture_mode": states.get("pictureMode"),
            "sound_mode": states.get("soundMode"),
            "speaker": states.get("speakerSelect"),
        }

    @callback
    def _async_publish(self, data: dict[str, Any]) -> None:
        """Publish locally-known data without disturbing the poll schedule.

        `async_set_updated_data` resets the refresh timer, so a button press
        every few seconds would postpone the reconciling poll indefinitely and
        let optimistic values drift uncorrected. Availability is deliberately
        left to the poll: a command cannot vouch for a reading it never took.
        """
        self.data = data
        self.async_update_listeners()

    @callback
    def async_apply_local_state(self, **changes: Any) -> None:
        """Publish locally-known values before the next poll confirms them."""
        if self.data is None:
            return
        if "surface" in changes:
            self._surface = changes["surface"]
            self._surface_source = changes.get("source", self.data.get("source"))
        self._async_publish({**self.data, **changes})

    @callback
    def async_apply_command_effect(self, command: str) -> None:
        """Publish a command's known result without waiting for the next poll.

        The TV acts on a button in well under the polling interval, so holding
        the dashboard at the last polled values made working buttons look stuck.
        Every value here is replaced by the following poll.
        """
        if self.data is None:
            return

        changes: dict[str, Any] = {}
        surface = self._surface

        if command == "power_on":
            # The set always returns to Home when it wakes.
            changes["power"] = True
            surface = SURFACE_HOME
        elif command == "power_off":
            changes["power"] = False
            surface = None
        elif command == "home":
            surface = SURFACE_HOME
        elif command.startswith("app_"):
            app = command.removeprefix("app_")
            surface = APP_SURFACES.get(f"app_{APP_ALIASES.get(app, app)}")
        elif command.startswith("hdmi_") and command[-1:] in "1234":
            changes["source"] = f"HDMI {command[-1]}"
            surface = None
        elif command in ("back", "exit"):
            # Neither key has a knowable destination, so fall back to the input.
            surface = None
        elif command == "mute":
            muted = self.data.get("muted")
            if muted is not None:
                changes["muted"] = not muted
        elif command in ("volume_up", "volume_down"):
            level = self.data.get("volume_level")
            if level is not None:
                step = VOLUME_STEP if command == "volume_up" else -VOLUME_STEP
                changes["volume_level"] = max(0.0, min(1.0, level + step))

        if surface != self._surface:
            self._surface = surface
            self._surface_source = changes.get("source", self.data.get("source"))
        changes["surface"] = self._surface

        self._async_publish({**self.data, **changes})
