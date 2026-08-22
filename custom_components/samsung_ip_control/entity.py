"""Shared entity base for Samsung TV IP Control."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SamsungIPControlConfigEntry
from .const import CONF_ENTITY_IDENTITY, DOMAIN
from .coordinator import SamsungIPControlCoordinator


class SamsungIPControlEntity(CoordinatorEntity[SamsungIPControlCoordinator]):
    """Shared device metadata."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: SamsungIPControlConfigEntry,
        coordinator: SamsungIPControlCoordinator,
        entity_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        identity = (
            entry.data.get(CONF_ENTITY_IDENTITY)
            or entry.data.get(CONF_MAC)
            or entry.data[CONF_HOST]
        )
        self._attr_unique_id = f"{identity}_{entity_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the shared TV device."""
        details = self.coordinator.device_information
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._entry.data.get(CONF_ENTITY_IDENTITY)
                    or self._entry.data.get(CONF_MAC)
                    or self._entry.data[CONF_HOST],
                )
            },
            name=self._entry.data.get(CONF_NAME, self._entry.title),
            manufacturer="Samsung",
            model=details.get("model") or None,
            sw_version=details.get("firmware") or None,
            serial_number=details.get("serial") or None,
        )
