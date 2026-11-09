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


def test_frontend_components_exist():
    """All required frontend web components must exist and register correctly."""
    from custom_components.house_battery_control import FRONTEND_DIR

    components = [
        "hbc-panel",
        "hbc-dashboard",
        "hbc-sensors",
        "hbc-plan-table",
    ]

    for component in components:
        js_file = FRONTEND_DIR / f"{component}.js"
        assert js_file.exists(), f"Frontend component {js_file.name} not found"
        content = js_file.read_text(encoding="utf-8")
        assert "customElements.define" in content, f"{component} must register a custom element"
        assert component in content, f"Custom element must be named {component}"


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
        HBCApiOutlookView,
        HBCApiPingView,
        HBCApiPlanView,
        HBCApiStatusView,
        HBCApiTelemetryView,
        HBCDashboardView,
    )

def test_init_registers_both_panels():
    """Verify __init__.py contains calls to register both hbc-panel and hbc-debug."""
    from custom_components.house_battery_control import __file__

    content = Path(__file__).read_text(encoding="utf-8")
    assert "frontend_url_path=\"hbc-panel\"" in content
    assert "frontend_url_path=\"hbc-debug\"" in content
    assert "hbc-panel-lite.js" in content


def test_panel_admin_only_constant_exists():
    """CONF_PANEL_ADMIN_ONLY must exist with default True."""
    from custom_components.house_battery_control.const import (
        CONF_PANEL_ADMIN_ONLY,
        DEFAULT_PANEL_ADMIN_ONLY,
    )

    assert isinstance(CONF_PANEL_ADMIN_ONLY, str)
    assert DEFAULT_PANEL_ADMIN_ONLY is True



def test_panel_cache_bust_v57_and_dashboard_solver_card():
    """T025/US4: Verify ?v=57 cache-bust on panel registrations and Solver card in hbc-dashboard.js."""
    from custom_components.house_battery_control import FRONTEND_DIR, __file__

    init_content = Path(__file__).read_text(encoding="utf-8")
    assert "/hbc/frontend/hbc-panel.js?v=57" in init_content
    assert "/hbc/frontend/hbc-panel-lite.js?v=57" in init_content

    dash_content = (FRONTEND_DIR / "hbc-dashboard.js").read_text(encoding="utf-8")
    assert "solver_stats" in dash_content
    assert "solve_seconds_max_24h" in dash_content
    assert "Solver" in dash_content
