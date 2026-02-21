"""Tests for the Home Assistant startup event handling (Phase 15)."""
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from custom_components.house_battery_control import async_setup_entry

@pytest.mark.asyncio
async def test_coordinator_refreshes_on_ha_start():
    """Verify that the coordinator triggers a refresh when HA is fully started."""
    # 1. Setup mock hass
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.async_block_till_done = AsyncMock()
    hass.data = {}
    hass.http.register_view = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    
    # Store listeners manually to simulate event firing
    listeners = {}
    def mock_listen_once(event_type, callback):
        listeners[event_type] = callback
        return MagicMock() # Unsubscribe mock
    
    hass.bus.async_listen_once = mock_listen_once

    # 2. Setup mock config entry
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"
    mock_entry.data = {}
    mock_entry.options = {}
    mock_entry.add_update_listener = MagicMock()
    
    # 3. Patch HBCDataUpdateCoordinator and setup_entry dependencies
    with patch("custom_components.house_battery_control.HBCDataUpdateCoordinator") as mock_coord_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_request_refresh = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_coord_class.return_value = mock_coordinator
        
        # Ensure the mock hass has an awaitable for entry setups
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        
        with patch("homeassistant.components.http.StaticPathConfig"), \
             patch("homeassistant.components.frontend.async_register_built_in_panel"):
            
            await async_setup_entry(hass, mock_entry)
        
        # 4. Verify EVENT_HOMEASSISTANT_STARTED listener was registered
        assert EVENT_HOMEASSISTANT_STARTED in listeners
        
        # 5. Reset mock call history (it might have been called during init)
        mock_coordinator.async_request_refresh.reset_mock()
        
        # 6. Simulate firing the startup event by calling the listener
        await listeners[EVENT_HOMEASSISTANT_STARTED](MagicMock())
        
        # 7. Assert refresh was called
        mock_coordinator.async_request_refresh.assert_called_once()
