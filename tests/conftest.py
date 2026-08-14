"""Shared fixtures for Sage Coffee tests."""

import asyncio
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sagecoffee.const import (
    CONF_BRAND,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    MACHINE_TYPE_SAGE,
)

MOCK_AUTH0_SUB = "auth0|1234567890"
MOCK_REFRESH_TOKEN = "mock-refresh-token"
MOCK_ROTATED_TOKEN = "mock-rotated-refresh-token"
MOCK_SERIAL = "SN12345678"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent actual integration setup when a config entry is created."""
    with patch(
        "custom_components.sagecoffee.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def mock_tokens() -> MagicMock:
    """A token set as returned by a successful authentication."""
    tokens = MagicMock()
    tokens.refresh_token = MOCK_ROTATED_TOKEN
    tokens.auth0_sub.return_value = MOCK_AUTH0_SUB
    return tokens


@pytest.fixture
def mock_auth_client(mock_tokens: MagicMock) -> Generator[MagicMock]:
    """Patch AuthClient where the config flow imports it."""
    with patch(
        "custom_components.sagecoffee.config_flow.AuthClient", autospec=True
    ) as mock_class:
        client = mock_class.return_value
        client.password_realm_login = AsyncMock(return_value=mock_tokens)
        client.refresh = AsyncMock(return_value=mock_tokens)
        yield client


@pytest.fixture
def mock_appliance() -> SimpleNamespace:
    """A discovered appliance as returned by the sagecoffee client."""
    return SimpleNamespace(serial_number=MOCK_SERIAL, name="Kitchen", model="BES995")


@pytest.fixture
def mock_client(mock_appliance: SimpleNamespace) -> Generator[MagicMock]:
    """Patch SageCoffeeClient where the integration imports it."""
    with patch(
        "custom_components.sagecoffee.SageCoffeeClient", autospec=True
    ) as mock_class:
        client = mock_class.return_value
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.list_appliances = AsyncMock(return_value=[mock_appliance])
        client.get_last_state = MagicMock(return_value=None)

        async def tail_state():
            # Keep the stream open until the listener task is cancelled.
            await asyncio.Event().wait()
            yield  # pragma: no cover

        client.tail_state = tail_state
        yield client


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A current-version config entry registered with Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=MOCK_AUTH0_SUB,
        data={
            CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
            CONF_BRAND: MACHINE_TYPE_SAGE,
        },
    )
    entry.add_to_hass(hass)
    return entry
