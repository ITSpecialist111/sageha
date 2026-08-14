"""Tests for the work light's brightness conversion and state logic (#33)."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS

from custom_components.sagecoffee.light import SageCoffeeWorkLight

from .conftest import MOCK_SERIAL


def make_light(state: dict[str, Any] | None) -> tuple[SageCoffeeWorkLight, MagicMock]:
    """Build a work light entity backed by a mocked coordinator."""
    coordinator = MagicMock()
    coordinator.get_state.return_value = state
    coordinator.client.set_work_light_brightness = AsyncMock()
    appliance = SimpleNamespace(serial_number=MOCK_SERIAL, name="Kitchen", model="X")
    return SageCoffeeWorkLight(coordinator, appliance), coordinator


def test_is_on_reflects_brightness() -> None:
    light, _ = make_light({"reported_state": "ready", "work_light_brightness": 50})
    assert light.is_on is True

    light, _ = make_light({"reported_state": "ready", "work_light_brightness": 0})
    assert light.is_on is False


def test_is_on_false_when_asleep_regardless_of_brightness() -> None:
    light, _ = make_light({"reported_state": "asleep", "work_light_brightness": 50})
    assert light.is_on is False


def test_is_on_unknown_without_state() -> None:
    light, _ = make_light(None)
    assert light.is_on is None
    assert light.brightness is None


def test_brightness_scales_api_value_to_ha_range() -> None:
    light, _ = make_light({"reported_state": "ready", "work_light_brightness": 100})
    assert light.brightness == 255

    light, _ = make_light({"reported_state": "ready", "work_light_brightness": 0})
    assert light.brightness is None


@pytest.mark.parametrize(
    ("ha_brightness", "expected_api_value"),
    [
        (255, 100),  # full brightness
        (128, 50),  # mid-scale rounds to nearest 10
        (1, 10),  # turning on always gives a visible brightness
    ],
)
async def test_turn_on_converts_and_clamps(
    ha_brightness: int, expected_api_value: int
) -> None:
    light, coordinator = make_light(
        {"reported_state": "ready", "work_light_brightness": 0}
    )

    await light.async_turn_on(**{ATTR_BRIGHTNESS: ha_brightness})

    coordinator.client.set_work_light_brightness.assert_awaited_once_with(
        expected_api_value, serial=MOCK_SERIAL
    )


async def test_turn_on_without_brightness_uses_full() -> None:
    light, coordinator = make_light(
        {"reported_state": "ready", "work_light_brightness": 0}
    )

    await light.async_turn_on()

    coordinator.client.set_work_light_brightness.assert_awaited_once_with(
        100, serial=MOCK_SERIAL
    )


async def test_turn_off_sends_zero() -> None:
    light, coordinator = make_light(
        {"reported_state": "ready", "work_light_brightness": 50}
    )

    await light.async_turn_off()

    coordinator.client.set_work_light_brightness.assert_awaited_once_with(
        0, serial=MOCK_SERIAL
    )
