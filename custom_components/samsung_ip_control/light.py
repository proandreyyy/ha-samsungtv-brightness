"""Light platform for Samsung TV IP Control.

HomeKit's Television service has no brightness characteristic, so a
dimmable, colorless light is the only way to get a real, draggable
brightness slider for the backlight into Apple Home.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SamsungIPControlConfigEntry, SamsungIPControlRuntimeData
from .const import BACKLIGHT_MAX, BACKLIGHT_MIN
from .entity import SamsungIPControlEntity

PARALLEL_UPDATES = 1

_DEFAULT_BACKLIGHT = (BACKLIGHT_MAX - BACKLIGHT_MIN) // 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SamsungIPControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the backlight light entity."""
    runtime = entry.runtime_data
    async_add_entities([SamsungIPControlBacklight(entry, runtime)])


class SamsungIPControlBacklight(SamsungIPControlEntity, LightEntity):
    """The TV backlight, exposed as a brightness-only light.

    "On" and "off" are a convenience, not a real TV state: off maps to
    backlight 0, and on restores the last non-zero level. The picture stays
    visible either way; only the backlight level changes.
    """

    _attr_name = "Backlight"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        entry: SamsungIPControlConfigEntry,
        runtime: SamsungIPControlRuntimeData,
    ) -> None:
        super().__init__(entry, runtime.coordinator, "backlight")
        self._client = runtime.client
        self._last_backlight = _DEFAULT_BACKLIGHT

    @property
    def is_on(self) -> bool | None:
        backlight = self.coordinator.data.get("backlight")
        if backlight is None:
            return None
        return backlight > BACKLIGHT_MIN

    @property
    def brightness(self) -> int | None:
        backlight = self.coordinator.data.get("backlight")
        if backlight is None:
            return None
        return round(backlight * 255 / BACKLIGHT_MAX)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            target = round(kwargs[ATTR_BRIGHTNESS] * BACKLIGHT_MAX / 255)
        else:
            target = self.coordinator.data.get("backlight") or self._last_backlight
        target = max(BACKLIGHT_MIN + 1, min(BACKLIGHT_MAX, target))
        await self._client.async_set_backlight(target)
        self._last_backlight = target
        self.coordinator.async_apply_local_state(backlight=target)

    async def async_turn_off(self, **kwargs: Any) -> None:
        backlight = self.coordinator.data.get("backlight")
        if backlight:
            self._last_backlight = backlight
        await self._client.async_set_backlight(BACKLIGHT_MIN)
        self.coordinator.async_apply_local_state(backlight=BACKLIGHT_MIN)
