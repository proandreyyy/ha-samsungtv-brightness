"""Media player platform for Samsung TV IP Control."""

from __future__ import annotations

from typing import Any, ClassVar

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SamsungIPControlConfigEntry, SamsungIPControlRuntimeData
from .const import APP_TO_API, SOURCE_TO_API
from .entity import SamsungIPControlEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SamsungIPControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the local media player entity."""
    runtime = entry.runtime_data
    async_add_entities([SamsungIPControlMediaPlayer(entry, runtime)])


class SamsungIPControlMediaPlayer(SamsungIPControlEntity, MediaPlayerEntity):
    """Local Samsung TV media player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )
    _attr_source_list: ClassVar[list[str]] = list(SOURCE_TO_API)

    def __init__(
        self,
        entry: SamsungIPControlConfigEntry,
        runtime: SamsungIPControlRuntimeData,
    ) -> None:
        super().__init__(entry, runtime.coordinator, "media_player")
        self._client = runtime.client

    @property
    def state(self) -> MediaPlayerState:
        return (
            MediaPlayerState.ON
            if self.coordinator.data["power"]
            else MediaPlayerState.OFF
        )

    @property
    def volume_level(self) -> float | None:
        return self.coordinator.data["volume_level"]

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.data["muted"]

    @property
    def source(self) -> str | None:
        return self.coordinator.data["source"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "picture_mode": self.coordinator.data["picture_mode"],
            "sound_mode": self.coordinator.data["sound_mode"],
            "speaker": self.coordinator.data["speaker"],
            "supported_apps": list(APP_TO_API),
            "control_path": "Local Samsung IP Control HTTPS 1516",
        }

    async def async_turn_on(self) -> None:
        await self._client.async_power_on()
        self.coordinator.async_apply_command_effect("power_on")

    async def async_turn_off(self) -> None:
        await self._client.async_power_off()
        self.coordinator.async_apply_command_effect("power_off")

    async def async_volume_up(self) -> None:
        await self._client.async_volume_up()
        self.coordinator.async_apply_command_effect("volume_up")

    async def async_volume_down(self) -> None:
        await self._client.async_volume_down()
        self.coordinator.async_apply_command_effect("volume_down")

    async def async_mute_volume(self, mute: bool) -> None:
        await self._client.async_set_mute(mute)
        self.coordinator.async_apply_local_state(muted=mute)

    async def async_select_source(self, source: str) -> None:
        await self._client.async_select_source(source)
        self.coordinator.async_apply_local_state(source=source, surface=None)

    async def async_media_play(self) -> None:
        await self._client.async_send_navigation_key("play")

    async def async_media_pause(self) -> None:
        await self._client.async_send_navigation_key("pause")

    async def async_media_stop(self) -> None:
        await self._client.async_send_navigation_key("stop")

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        if media_type not in (MediaType.APP, MediaType.APPS):
            raise ValueError(f"Unsupported media type: {media_type}")
        await self._client.async_launch_app(media_id)
        self.coordinator.async_apply_command_effect(f"app_{media_id}")
