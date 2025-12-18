"""Config flow for victron mqtt integration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

from victron_mqtt import (
    AuthenticationError,
    CannotConnectError,
    DeviceType,
    Hub as VictronVenusHub,
    OperationMode
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_ELEVATED_TRACING,
    CONF_EXCLUDED_DEVICES,
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_OPERATION_MODE,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    CONF_SIMPLE_NAMING,
    CONF_UPDATE_FREQUENCY_SECONDS,
    CONF_VRM_PORTAL_ID,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_VRM,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SIMPLE_NAMING,
    DEFAULT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
    VRM_BROKER_PORT,
    get_vrm_broker_url,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_CODES: Sequence[SelectOptionDict] = [
    {"value": device_type.code, "label": device_type.string}
    for device_type in DeviceType
    if device_type.string != "<Not used>"
]


def _get_connection_type_schema(defaults: MappingProxyType[str, Any] | None = None) -> vol.Schema:
    """Get the connection type selection schema."""
    if defaults is None:
        defaults = MappingProxyType({})
    
    connection_type = defaults.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL)
    
    return vol.Schema(
        {
            vol.Required(CONF_CONNECTION_TYPE, default=connection_type): SelectSelector(
                SelectSelectorConfig(
                    options=[CONNECTION_TYPE_LOCAL, CONNECTION_TYPE_VRM],
                    translation_key="connection_type",
                )
            ),
        }
    )


def _get_local_connection_schema(defaults: MappingProxyType[str, Any] | None = None) -> vol.Schema:
    """Get the local connection configuration schema."""
    if defaults is None:
        defaults = MappingProxyType({})
    
    default_host = defaults.get(CONF_HOST, DEFAULT_HOST)
    default_port = defaults.get(CONF_PORT, DEFAULT_PORT)
    default_ssl = defaults.get(CONF_SSL, False)
    
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=default_host): str,
            vol.Required(CONF_PORT, default=default_port): int,
            vol.Optional(
                CONF_USERNAME,
                description={"suggested_value": f"{defaults.get(CONF_USERNAME, '')}"},
            ): str,
            vol.Optional(
                CONF_PASSWORD,
                description={"suggested_value": f"{defaults.get(CONF_PASSWORD, '')}"},
            ): str,
            vol.Required(CONF_SSL, default=default_ssl): bool,
        }
    )


def _get_vrm_connection_schema(defaults: MappingProxyType[str, Any] | None = None) -> vol.Schema:
    """Get the VRM connection configuration schema."""
    if defaults is None:
        defaults = MappingProxyType({})
    
    return vol.Schema(
        {
            vol.Required(
                CONF_VRM_PORTAL_ID,
                description={"suggested_value": f"{defaults.get(CONF_VRM_PORTAL_ID, '')}"},
            ): str,
            vol.Required(
                CONF_USERNAME,
                description={"suggested_value": f"{defaults.get(CONF_USERNAME, '')}"},
            ): str,
            vol.Required(
                CONF_PASSWORD,
                description={"suggested_value": f"{defaults.get(CONF_PASSWORD, '')}"},
            ): str,
        }
    )


def _get_additional_settings_schema(defaults: MappingProxyType[str, Any] | None = None) -> vol.Schema:
    """Get the additional settings schema."""
    if defaults is None:
        defaults = MappingProxyType({})
    
    # Ensure operation_mode default is a string value (not an Enum instance)
    op_mode_default = defaults.get(CONF_OPERATION_MODE, OperationMode.FULL.value)
    op_default = (
        op_mode_default.value
        if isinstance(op_mode_default, OperationMode)
        else op_mode_default
    )
    
    return vol.Schema(
        {
            vol.Required(CONF_OPERATION_MODE, default=op_default): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        OperationMode.READ_ONLY.value,
                        OperationMode.FULL.value,
                        OperationMode.EXPERIMENTAL.value,
                    ],
                    translation_key="operation_mode",
                )
            ),
            vol.Optional(
                CONF_SIMPLE_NAMING,
                default=defaults.get(CONF_SIMPLE_NAMING, DEFAULT_SIMPLE_NAMING),
            ): bool,
            vol.Optional(
                CONF_ROOT_TOPIC_PREFIX,
                description={
                    "suggested_value": f"{defaults.get(CONF_ROOT_TOPIC_PREFIX, '')}"
                },
            ): str,
            vol.Optional(
                CONF_UPDATE_FREQUENCY_SECONDS,
                default=defaults.get(
                    CONF_UPDATE_FREQUENCY_SECONDS, DEFAULT_UPDATE_FREQUENCY_SECONDS
                ),
            ): int,
            vol.Optional(
                CONF_EXCLUDED_DEVICES, default=defaults.get(CONF_EXCLUDED_DEVICES, [])
            ): SelectSelector(
                SelectSelectorConfig(
                    options=DEVICE_CODES,
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_ELEVATED_TRACING,
                description={
                    "suggested_value": f"{defaults.get(CONF_ELEVATED_TRACING, '')}"
                },
            ): str,
        }
    )


async def validate_input(data: dict[str, Any]) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from zeroconf values as well as user input.

    Returns the installation id upon success.
    """
    _LOGGER.info("Validating input: %s", data)
    hub = VictronVenusHub(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        username=data.get(CONF_USERNAME) or None,
        password=data.get(CONF_PASSWORD) or None,
        use_ssl=data.get(CONF_SSL, False),
        installation_id=data.get(CONF_INSTALLATION_ID) or None,
        serial=data.get(CONF_SERIAL, "noserial"),
        topic_prefix=data.get(CONF_ROOT_TOPIC_PREFIX) or None,
        topic_log_info=data.get(CONF_ELEVATED_TRACING) or None,
    )

    await hub.connect()
    assert hub.installation_id is not None
    return hub.installation_id


def _process_vrm_portal_id(vrm_portal_id: str) -> tuple[bool, str, str, int]:
    """Process VRM Portal ID and generate broker URL.
    
    Args:
        vrm_portal_id: The VRM Portal ID
        
    Returns:
        Tuple of (success, error_message, host, port). If success is False, host and port are empty.
    """
    vrm_portal_id = vrm_portal_id.strip()
    if not vrm_portal_id:
        return False, "vrm_portal_id_required", "", 0
    
    # Validate portal ID format (alphanumeric)
    if not vrm_portal_id.replace("-", "").replace("_", "").isalnum():
        return False, "vrm_portal_id_invalid", "", 0
    
    # Generate the VRM broker host from portal ID using the calculation logic
    host = get_vrm_broker_url(vrm_portal_id)
    port = VRM_BROKER_PORT
    
    return True, "", host, port


class VictronMQTTConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for victronvenus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.hostname: str | None = None
        self.serial: str | None = None
        self.installation_id: str | None = None
        self.friendly_name: str | None = None
        self.model_name: str | None = None
        self.config_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - connection type selection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.info("Connection type selected: %s", user_input)
            self.config_data[CONF_CONNECTION_TYPE] = user_input[CONF_CONNECTION_TYPE]
            
            if user_input[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_LOCAL:
                return await self.async_step_local()
            else:
                return await self.async_step_vrm()

        return self.async_show_form(
            step_id="user",
            data_schema=_get_connection_type_schema(),
            errors=errors,
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle local connection configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.info("Local connection input received: %s", user_input)
            self.config_data.update(user_input)
            return await self.async_step_settings()

        defaults = MappingProxyType(self.config_data)
        return self.async_show_form(
            step_id="local",
            data_schema=_get_local_connection_schema(defaults),
            errors=errors,
        )

    async def async_step_vrm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle VRM connection configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.info("VRM connection input received: %s", user_input)
            
            # Process VRM Portal ID and generate host
            success, error_msg, host, port = _process_vrm_portal_id(
                user_input.get(CONF_VRM_PORTAL_ID, "")
            )
            if not success:
                errors["base"] = error_msg
                defaults = MappingProxyType({**self.config_data, **user_input})
                return self.async_show_form(
                    step_id="vrm",
                    data_schema=_get_vrm_connection_schema(defaults),
                    errors=errors,
                )
            
            # Store VRM-specific configuration
            self.config_data[CONF_VRM_PORTAL_ID] = user_input[CONF_VRM_PORTAL_ID]
            self.config_data[CONF_USERNAME] = user_input.get(CONF_USERNAME)
            self.config_data[CONF_PASSWORD] = user_input.get(CONF_PASSWORD)
            self.config_data[CONF_HOST] = host
            self.config_data[CONF_PORT] = port
            self.config_data[CONF_SSL] = True
            
            return await self.async_step_settings()

        defaults = MappingProxyType(self.config_data)
        return self.async_show_form(
            step_id="vrm",
            data_schema=_get_vrm_connection_schema(defaults),
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle additional settings configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.info("Settings input received: %s", user_input)
            self.config_data.update(user_input)
            
            # Prepare data for validation
            data = {
                **self.config_data,
                CONF_SERIAL: self.serial,
                CONF_MODEL: self.model_name,
            }
            data = {
                k: v for k, v in data.items() if v is not None
            }  # remove None values.

            try:
                installation_id = await validate_input(data)
                _LOGGER.info(
                    "Successfully connected to Victron device: %s", installation_id
                )
            except AuthenticationError:
                _LOGGER.exception("Authentication failed during setup")
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                _LOGGER.exception("Cannot connect to Victron device")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("General error connecting to Victron device")
                errors["base"] = "unknown"
            else:
                data[CONF_INSTALLATION_ID] = installation_id
                unique_id = installation_id
                await self.async_set_unique_id(unique_id)

                self._abort_if_unique_id_configured()

                title = self.friendly_name or f"Victron OS {unique_id}"
                return self.async_create_entry(title=title, data=data)

        if len(errors) > 0:
            _LOGGER.warning("Showing settings form with errors: %s", errors)
        
        defaults = MappingProxyType(self.config_data)
        return self.async_show_form(
            step_id="settings",
            data_schema=_get_additional_settings_schema(defaults),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            _LOGGER.info("Reauth user input received: %s", user_input)
            data = {
                **reauth_entry.data,
                CONF_USERNAME: user_input.get(CONF_USERNAME) or None,
                CONF_PASSWORD: user_input.get(CONF_PASSWORD) or None,
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}

            try:
                await validate_input(data)
                _LOGGER.info("Reauthentication successful")
            except AuthenticationError:
                _LOGGER.exception("Authentication failed during reauthentication")
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                _LOGGER.exception("Cannot connect during reauthentication")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("General error during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        reauth_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USERNAME, default=reauth_entry.data.get(CONF_USERNAME) or ""
                ): str,
                vol.Optional(
                    CONF_PASSWORD, default=reauth_entry.data.get(CONF_PASSWORD) or ""
                ): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema,
            errors=errors,
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> VictronMQTTOptionsFlow:
        """Get the options flow for this handler."""
        _LOGGER.info("Getting options flow handler")
        return VictronMQTTOptionsFlow()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle UPnP  discovery."""
        self.hostname = str(urlparse(discovery_info.ssdp_location).hostname)
        self.serial = discovery_info.upnp["serialNumber"]
        self.installation_id = discovery_info.upnp["X_VrmPortalId"]
        self.model_name = discovery_info.upnp["modelName"]
        self.friendly_name = discovery_info.upnp["friendlyName"]
        _LOGGER.debug(
            "SSDP: hostname=%s, serial=%s, installation_id=%s, model_name=%s, friendly_name=%s",
            self.hostname,
            self.serial,
            self.installation_id,
            self.model_name,
            self.friendly_name,
        )

        await self.async_set_unique_id(self.installation_id)
        self._abort_if_unique_id_configured()

        try:
            sensed_installation_id = await validate_input(
                {
                    CONF_HOST: self.hostname,
                    CONF_SERIAL: self.serial,
                    CONF_INSTALLATION_ID: self.installation_id,
                }
            )
            assert sensed_installation_id == self.installation_id
        except AuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=str(self.friendly_name),
            data={
                CONF_HOST: self.hostname,
                CONF_SERIAL: self.serial,
                CONF_INSTALLATION_ID: self.installation_id,
                CONF_MODEL: self.model_name,
                CONF_SIMPLE_NAMING: DEFAULT_SIMPLE_NAMING,
                CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
            },
        )


class VictronMQTTOptionsFlow(OptionsFlow):
    """Handle options flow for Victron MQTT."""

    def __init__(self) -> None:
        """Initialize."""
        self.config_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow - connection type selection."""
        _LOGGER.info(
            "Initializing options flow. current config: %s", self.config_entry.data
        )
        
        # Initialize config_data with current configuration
        self.config_data = dict(self.config_entry.data)
        
        if user_input is not None:
            _LOGGER.info("Connection type selected in options: %s", user_input)
            self.config_data[CONF_CONNECTION_TYPE] = user_input[CONF_CONNECTION_TYPE]
            
            if user_input[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_LOCAL:
                return await self.async_step_local_options()
            else:
                return await self.async_step_vrm_options()

        defaults = MappingProxyType(self.config_data)
        return self.async_show_form(
            step_id="init",
            data_schema=_get_connection_type_schema(defaults),
        )

    async def async_step_local_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle local connection configuration in options."""
        if user_input is not None:
            _LOGGER.info("Local connection options input received: %s", user_input)
            self.config_data.update(user_input)
            return await self.async_step_settings_options()

        defaults = MappingProxyType(self.config_data)
        return self.async_show_form(
            step_id="local_options",
            data_schema=_get_local_connection_schema(defaults),
        )

    async def async_step_vrm_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle VRM connection configuration in options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.info("VRM connection options input received: %s", user_input)
            
            # Process VRM Portal ID and generate host
            success, error_msg, host, port = _process_vrm_portal_id(
                user_input.get(CONF_VRM_PORTAL_ID, "")
            )
            if not success:
                errors["base"] = error_msg
                defaults = MappingProxyType({**self.config_data, **user_input})
                return self.async_show_form(
                    step_id="vrm_options",
                    data_schema=_get_vrm_connection_schema(defaults),
                    errors=errors,
                )
            
            # Store VRM-specific configuration
            self.config_data[CONF_VRM_PORTAL_ID] = user_input[CONF_VRM_PORTAL_ID]
            self.config_data[CONF_USERNAME] = user_input.get(CONF_USERNAME)
            self.config_data[CONF_PASSWORD] = user_input.get(CONF_PASSWORD)
            self.config_data[CONF_HOST] = host
            self.config_data[CONF_PORT] = port
            self.config_data[CONF_SSL] = True
            
            return await self.async_step_settings_options()

        defaults = MappingProxyType(self.config_data)
        return self.async_show_form(
            step_id="vrm_options",
            data_schema=_get_vrm_connection_schema(defaults),
            errors=errors,
        )

    async def async_step_settings_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle additional settings configuration in options."""
        if user_input is not None:
            _LOGGER.info("Settings options input received: %s", user_input)
            self.config_data.update(user_input)
            
            try:
                await validate_input(self.config_data)
            except AuthenticationError:
                return self.async_show_form(
                    step_id="settings_options",
                    data_schema=_get_additional_settings_schema(MappingProxyType(self.config_data)),
                    errors={"base": "invalid_auth"},
                )
            except CannotConnectError:
                return self.async_show_form(
                    step_id="settings_options",
                    data_schema=_get_additional_settings_schema(MappingProxyType(self.config_data)),
                    errors={"base": "cannot_connect"},
                )
            _LOGGER.info(
                "Options flow completed successfully. new config: %s", self.config_data
            )
            # Update the config entry with new data.
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_data
            )
            # Reload the entry to apply the new options
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})
        
        defaults = MappingProxyType(self.config_data)
        return self.async_show_form(
            step_id="settings_options",
            data_schema=_get_additional_settings_schema(defaults),
        )
