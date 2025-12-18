"""Test the victron GX config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from victron_mqtt import CannotConnectError, OperationMode

from custom_components.victron_mqtt.const import (
    CONF_CONNECTION_TYPE,
    CONF_EXCLUDED_DEVICES,
    CONF_INSTALLATION_ID,
    CONF_OPERATION_MODE,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    CONF_SIMPLE_NAMING,
    CONF_UPDATE_FREQUENCY_SECONDS,
    CONF_VRM_PORTAL_ID,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_VRM,
    DEFAULT_PORT,
    DEFAULT_SIMPLE_NAMING,
    DEFAULT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry
from victron_mqtt import AuthenticationError

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "enable_custom_integrations")
MOCK_INSTALLATION_ID = "d41243d9b9c6"
MOCK_SERIAL = "HQ2234ABCDE"
MOCK_MODEL = "Cerbo GX"
MOCK_FRIENDLY_NAME = "Venus GX"
MOCK_HOST = "192.168.1.100"
MOCK_VRM_PORTAL_ID = "c0619ab123456"


@pytest.fixture
def mock_victron_hub():
    """Mock the Victron Hub."""
    with patch(
        "custom_components.victron_mqtt.config_flow.VictronVenusHub"
    ) as mock_hub:
        hub_instance = MagicMock()
        hub_instance.connect = AsyncMock()
        hub_instance.installation_id = MOCK_INSTALLATION_ID
        mock_hub.return_value = hub_instance
        yield mock_hub


@pytest.mark.usefixtures("mock_victron_hub")
async def test_user_flow_local_full_config(hass: HomeAssistant) -> None:
    """Test the full user flow with local connection and all configuration options."""
    # Step 1: Choose connection type
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: Select local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local"

    # Step 3: Configure local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SSL: False,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    # Step 4: Configure additional settings
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_OPERATION_MODE: OperationMode.FULL.value,
            CONF_SIMPLE_NAMING: True,
            CONF_ROOT_TOPIC_PREFIX: "N/test",
            CONF_UPDATE_FREQUENCY_SECONDS: 60,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Victron OS {MOCK_INSTALLATION_ID}"
    assert result["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_OPERATION_MODE: OperationMode.FULL.value,
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
        CONF_SIMPLE_NAMING: True,
        CONF_ROOT_TOPIC_PREFIX: "N/test",
        CONF_UPDATE_FREQUENCY_SECONDS: 60,
        CONF_EXCLUDED_DEVICES: [],
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
    }


@pytest.mark.usefixtures("mock_victron_hub")
async def test_user_flow_local_minimal_config(hass: HomeAssistant) -> None:
    """Test the user flow with local connection and minimal configuration."""
    # Step 1: Choose connection type
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 2: Select local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL},
    )
    assert result["step_id"] == "local"

    # Step 3: Configure local connection (minimal)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )
    assert result["step_id"] == "settings"

    # Step 4: Configure additional settings (defaults)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Victron OS {MOCK_INSTALLATION_ID}"
    assert result["data"] == {
        CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_SSL: False,
        CONF_SIMPLE_NAMING: False,
        CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        CONF_OPERATION_MODE: OperationMode.FULL.value,
        CONF_EXCLUDED_DEVICES: [],
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
    }


@pytest.mark.usefixtures("mock_victron_hub")
async def test_user_flow_vrm_config(hass: HomeAssistant) -> None:
    """Test the user flow with VRM connection."""
    # Step 1: Choose connection type
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 2: Select VRM connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_VRM},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vrm"

    # Step 3: Configure VRM connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_VRM_PORTAL_ID: MOCK_VRM_PORTAL_ID,
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "test-vrm-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    # Step 4: Configure additional settings
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_OPERATION_MODE: OperationMode.FULL.value,
            CONF_SIMPLE_NAMING: True,
            CONF_UPDATE_FREQUENCY_SECONDS: 30,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Victron OS {MOCK_INSTALLATION_ID}"
    assert CONF_CONNECTION_TYPE in result["data"]
    assert result["data"][CONF_CONNECTION_TYPE] == CONNECTION_TYPE_VRM
    assert result["data"][CONF_VRM_PORTAL_ID] == MOCK_VRM_PORTAL_ID
    assert result["data"][CONF_USERNAME] == "test@example.com"
    assert result["data"][CONF_PASSWORD] == "test-vrm-password"
    assert result["data"][CONF_SSL] is True
    assert result["data"][CONF_PORT] == 8883


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    # Step 1: Choose connection type
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Step 2: Select local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL},
    )

    # Step 3: Configure local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    # Step 4: Configure settings - should fail with cannot connect
    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test we handle unknown errors."""
    # Step 1: Choose connection type
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Step 2: Select local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL},
    )

    # Step 3: Configure local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    # Step 4: Configure settings - should fail with unknown error
    mock_victron_hub.return_value.connect.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover from error
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_victron_hub")
async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test configuration flow aborts when device is already configured."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
    )
    mock_config_entry.add_to_hass(hass)

    # Step 1: Choose connection type
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Step 2: Select local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL},
    )

    # Step 3: Configure local connection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    # Step 4: Configure settings
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_victron_hub")
async def test_ssdp_flow_success(hass: HomeAssistant) -> None:
    """Test SSDP discovery flow with successful connection."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_FRIENDLY_NAME
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_SERIAL: MOCK_SERIAL,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        CONF_MODEL: MOCK_MODEL,
        CONF_SIMPLE_NAMING: DEFAULT_SIMPLE_NAMING,
    }


async def test_ssdp_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test SSDP discovery flow when connection fails, aborts with cannot_connect."""
    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    # Should abort when connection fails
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_victron_hub")
async def test_ssdp_flow_already_configured(hass: HomeAssistant) -> None:
    """Test SSDP discovery flow aborts when device is already configured."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
    )
    mock_config_entry.add_to_hass(hass)

    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_victron_hub")
async def test_options_flow_local_success(hass: HomeAssistant) -> None:
    """Test options flow allows updating local configuration."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SERIAL: MOCK_SERIAL,
            CONF_MODEL: MOCK_MODEL,
            CONF_SSL: False,
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    # Step 1: Choose connection type
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Step 2: Select local connection
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL},
    )
    assert result["step_id"] == "local_options"

    # Step 3: Configure local connection
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 1883,
            CONF_USERNAME: "new-user",
            CONF_PASSWORD: "new-pass",
            CONF_SSL: True,
        },
    )
    assert result["step_id"] == "settings_options"

    # Step 4: Configure additional settings
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SIMPLE_NAMING: True,
                CONF_ROOT_TOPIC_PREFIX: "N/updated",
                CONF_UPDATE_FREQUENCY_SECONDS: 45,
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert mock_config_entry.data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_LOCAL
        assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
        assert mock_config_entry.data[CONF_PORT] == 1883
        assert mock_config_entry.data[CONF_USERNAME] == "new-user"
        assert mock_config_entry.data[CONF_PASSWORD] == "new-pass"
        assert mock_config_entry.data[CONF_SSL] is True
        assert mock_config_entry.data[CONF_SIMPLE_NAMING] is True
        assert mock_config_entry.data[CONF_ROOT_TOPIC_PREFIX] == "N/updated"
        assert mock_config_entry.data[CONF_UPDATE_FREQUENCY_SECONDS] == 45
        assert len(mock_reload.mock_calls) == 1


@pytest.mark.usefixtures("mock_victron_hub")
async def test_options_flow_vrm_success(hass: HomeAssistant) -> None:
    """Test options flow allows updating VRM configuration."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_VRM,
            CONF_VRM_PORTAL_ID: MOCK_VRM_PORTAL_ID,
            CONF_USERNAME: "old@example.com",
            CONF_PASSWORD: "old-password",
            CONF_HOST: "mqtt111.victronenergy.com",
            CONF_PORT: 8883,
            CONF_SSL: True,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    # Step 1: Choose connection type
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"

    # Step 2: Select VRM connection
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_VRM},
    )
    assert result["step_id"] == "vrm_options"

    # Step 3: Configure VRM connection
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VRM_PORTAL_ID: MOCK_VRM_PORTAL_ID,
            CONF_USERNAME: "new@example.com",
            CONF_PASSWORD: "new-password",
        },
    )
    assert result["step_id"] == "settings_options"

    # Step 4: Configure additional settings
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SIMPLE_NAMING: True,
                CONF_UPDATE_FREQUENCY_SECONDS: 60,
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert mock_config_entry.data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_VRM
        assert mock_config_entry.data[CONF_VRM_PORTAL_ID] == MOCK_VRM_PORTAL_ID
        assert mock_config_entry.data[CONF_USERNAME] == "new@example.com"
        assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
        assert mock_config_entry.data[CONF_SIMPLE_NAMING] is True
        assert len(mock_reload.mock_calls) == 1


async def test_options_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test options flow handles connection errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    # Step 1: Choose connection type
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Step 2: Select local connection
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL},
    )

    # Step 3: Configure local connection
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 1883,
            CONF_SSL: False,
        },
    )

    # Step 4: Configure settings - should fail with cannot connect
    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SIMPLE_NAMING: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_victron_hub")
async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test successful reauthentication flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: 42,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "new-username"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    assert mock_config_entry.data[CONF_UPDATE_FREQUENCY_SECONDS] == 42


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test reauthentication flow handles connection errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test recovery from error
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test reauthentication flow handles unknown errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    mock_victron_hub.return_value.connect.side_effect = Exception("Test error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test reauthentication flow handles authentication errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Invalid credentials"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "wrong-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Test recovery with correct credentials
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "correct-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
