"""Tests for the Sage Coffee config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sagecoffee.const import (
    CONF_BRAND,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    MACHINE_TYPE_BREVILLE,
    MACHINE_TYPE_SAGE,
)

from .conftest import MOCK_AUTH0_SUB, MOCK_REFRESH_TOKEN, MOCK_ROTATED_TOKEN

PASSWORD_INPUT = {
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "hunter2",
    CONF_BRAND: MACHINE_TYPE_SAGE,
}

TOKEN_INPUT = {
    CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
    CONF_BRAND: MACHINE_TYPE_BREVILLE,
}


async def test_user_step_shows_menu(hass: HomeAssistant) -> None:
    """The initial step offers a choice between password and token auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["password", "token"]


async def test_password_flow_creates_entry(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """A successful password login creates an entry with token, brand and unique ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PASSWORD_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_REFRESH_TOKEN: MOCK_ROTATED_TOKEN,
        CONF_BRAND: MACHINE_TYPE_SAGE,
    }
    assert result["result"].unique_id == MOCK_AUTH0_SUB
    mock_auth_client.password_realm_login.assert_awaited_once_with(
        "user@example.com", "hunter2"
    )


async def test_password_flow_invalid_auth_then_recover(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_tokens: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """A failed login shows an error and the flow can still succeed afterwards."""
    mock_auth_client.password_realm_login.side_effect = Exception("bad credentials")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PASSWORD_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_auth_client.password_realm_login.side_effect = None
    mock_auth_client.password_realm_login.return_value = mock_tokens

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PASSWORD_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_password_flow_duplicate_account_aborts(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Logging in with an already-configured account aborts the flow."""
    MockConfigEntry(domain=DOMAIN, unique_id=MOCK_AUTH0_SUB).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PASSWORD_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_password_flow_without_auth0_sub_creates_entry(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_tokens: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """When no auth0 subject is available the entry is created without a unique ID."""
    mock_tokens.auth0_sub.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PASSWORD_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id is None


async def test_token_flow_creates_entry_with_rotated_token(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """A valid token creates an entry storing the rotated token from the refresh."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TOKEN_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_REFRESH_TOKEN: MOCK_ROTATED_TOKEN,
        CONF_BRAND: MACHINE_TYPE_BREVILLE,
    }
    assert result["result"].unique_id == MOCK_AUTH0_SUB
    mock_auth_client.refresh.assert_awaited_once_with(MOCK_REFRESH_TOKEN)


async def test_token_flow_keeps_original_token_when_not_rotated(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_tokens: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """If the refresh response has no new refresh token, the entered one is kept."""
    mock_tokens.refresh_token = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TOKEN_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REFRESH_TOKEN] == MOCK_REFRESH_TOKEN


async def test_token_flow_invalid_token_shows_error(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """An invalid token shows an error on the token form."""
    mock_auth_client.refresh.side_effect = Exception("invalid token")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TOKEN_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_token_flow_duplicate_account_aborts(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """A token for an already-configured account aborts the flow."""
    MockConfigEntry(domain=DOMAIN, unique_id=MOCK_AUTH0_SUB).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TOKEN_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.fixture
def existing_entry(hass: HomeAssistant) -> MockConfigEntry:
    """An existing config entry to reauthenticate against."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_AUTH0_SUB,
        data={
            CONF_REFRESH_TOKEN: "expired-token",
            CONF_BRAND: MACHINE_TYPE_SAGE,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_reauth_password_updates_entry(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
    existing_entry: MockConfigEntry,
) -> None:
    """Reauthenticating with a password updates the stored token and brand."""
    result = await existing_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], PASSWORD_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert existing_entry.data == {
        CONF_REFRESH_TOKEN: MOCK_ROTATED_TOKEN,
        CONF_BRAND: MACHINE_TYPE_SAGE,
    }


async def test_reauth_token_updates_entry(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
    existing_entry: MockConfigEntry,
) -> None:
    """Reauthenticating with a token updates the stored token and brand."""
    result = await existing_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_token"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TOKEN_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert existing_entry.data == {
        CONF_REFRESH_TOKEN: MOCK_ROTATED_TOKEN,
        CONF_BRAND: MACHINE_TYPE_BREVILLE,
    }


async def test_reauth_token_failure_shows_error(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
    existing_entry: MockConfigEntry,
) -> None:
    """A failed reauth leaves the existing entry untouched and shows an error."""
    mock_auth_client.refresh.side_effect = Exception("invalid token")

    result = await existing_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_token"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TOKEN_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert existing_entry.data[CONF_REFRESH_TOKEN] == "expired-token"
