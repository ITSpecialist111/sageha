"""Shared fixtures for Sage Coffee tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOCK_AUTH0_SUB = "auth0|1234567890"
MOCK_REFRESH_TOKEN = "mock-refresh-token"
MOCK_ROTATED_TOKEN = "mock-rotated-refresh-token"


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
