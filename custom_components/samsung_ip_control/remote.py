"""Remote platform for Samsung TV IP Control."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SamsungIPControlConfigEntry, SamsungIPControlRuntimeData
from .const import DOMAIN, REMOTE_COMMANDS
from .entity import SamsungIPControlEntity
from .text_client import (
    SamsungTextInputAuthError,
    SamsungTextInputCertificateError,
    SamsungTextInputError,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SamsungIPControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the focused local remote entity."""
    runtime = entry.runtime_data
    async_add_entities([SamsungIPControlRemote(entry, runtime)])


class SamsungIPControlRemote(SamsungIPControlEntity, RemoteEntity):
    """Remote exposing the allowlisted Consumer IP control surface."""

    _attr_name = "Remote"

    def __init__(
        self,
        entry: SamsungIPControlConfigEntry,
        runtime: SamsungIPControlRuntimeData,
    ) -> None:
        super().__init__(entry, runtime.coordinator, "remote")
        self._client = runtime.client
        self._text_client = runtime.text_client

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["power"])

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "supported_commands": list(REMOTE_COMMANDS),
            "text_input_enabled": self._text_client is not None,
            "surface": self.coordinator.data.get("surface"),
            "control_path": "Local Samsung IP Control HTTPS 1516",
        }

    async def async_turn_on(self, **kwargs: object) -> None:
        await self._client.async_power_on()
        self.coordinator.async_apply_command_effect("power_on")

    async def async_send_text(self, text: str, submit: bool = False) -> None:
        """Send non-sensitive text to the TV's active on-screen input."""
        if self._text_client is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="text_input_not_configured",
            )
        try:
            await self._text_client.async_send_text(text, submit=submit)
        except SamsungTextInputAuthError:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="text_input_authentication_failed",
            ) from None
        except SamsungTextInputCertificateError:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="text_input_certificate_mismatch",
            ) from None
        except SamsungTextInputError:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="text_input_failed",
            ) from None

    async def async_turn_off(self, **kwargs: object) -> None:
        await self._client.async_power_off()
        self.coordinator.async_apply_command_effect("power_off")

    async def async_send_command(
        self, command: Iterable[str], **kwargs: object
    ) -> None:
        repeats = int(kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS))
        delay = float(kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS))
        commands = list(command)
        invalid = [item for item in commands if item not in REMOTE_COMMANDS]
        if invalid:
            raise ValueError(f"Unsupported Samsung IP Control command: {invalid[0]}")

        for repeat_index in range(repeats):
            for command_index, item in enumerate(commands):
                result = await self._client.async_run_remote_command(item)
                if item in ("brightness_up", "brightness_down"):
                    self.coordinator.async_apply_local_state(backlight=result)
                else:
                    self.coordinator.async_apply_command_effect(item)
                if delay > 0 and (
                    command_index < len(commands) - 1 or repeat_index < repeats - 1
                ):
                    await asyncio.sleep(delay)
