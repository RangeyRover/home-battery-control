"""Tests for __init__.py — integration setup structure (spec 2.2).

Verifies panel registration prerequisites and module structure
without needing a live HA event loop.
"""
from pathlib import Path


def test_init_module_importable():
    """__init__.py must be importable."""
    import custom_components.house_battery_control as hbc
    assert hasattr(hbc, "async_setup_entry")
    assert hasattr(hbc, "async_unload_entry")


def test_frontend_dir_defined():
    """FRONTEND_DIR constant must point to existing directory."""
    from custom_components.house_battery_control import FRONTEND_DIR
    assert isinstance(FRONTEND_DIR, Path)
    assert FRONTEND_DIR.exists(), f"{FRONTEND_DIR} does not exist"
    assert FRONTEND_DIR.name == "frontend"


def test_panel_js_exists():
    """hbc-panel.js must exist in frontend directory."""
    from custom_components.house_battery_control import FRONTEND_DIR
    panel_js = FRONTEND_DIR / "hbc-panel.js"
    assert panel_js.exists(), f"{panel_js} not found"
    content = panel_js.read_text(encoding="utf-8")
    assert "customElements.define" in content, "JS must register a custom element"
    assert "hbc-panel" in content, "Custom element must be named hbc-panel"


def test_static_path_config_importable():
    """StaticPathConfig must be importable (used in async_setup_entry)."""
    from homeassistant.components.http import StaticPathConfig
    assert StaticPathConfig is not None


def test_async_register_built_in_panel_importable():
    """async_register_built_in_panel must be directly importable (not via deprecated hass.components)."""
    from homeassistant.components.frontend import async_register_built_in_panel
    assert callable(async_register_built_in_panel)


def test_platforms_includes_sensor():
    """PLATFORMS must include sensor."""
    from custom_components.house_battery_control import PLATFORMS
    from homeassistant.const import Platform
    assert Platform.SENSOR in PLATFORMS


def test_web_views_importable():
    """All web view classes must be importable from __init__."""
    from custom_components.house_battery_control import (  # noqa: F401
        HBCApiPingView,
        HBCApiStatusView,
        HBCDashboardView,
        HBCPlanView,
    )
