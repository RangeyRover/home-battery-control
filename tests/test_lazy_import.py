"""Test to ensure third-party PIP dependencies are strictly lazy-loaded."""

import ast
import os

import pytest


def get_python_files(directory):
    """Recursively yield all .py files in a directory."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                yield os.path.join(root, file)

def test_no_top_level_pip_imports():
    """Assert pulp is never imported at the top-level scope of any integration file."""
    integration_dir = os.path.join(
        os.path.dirname(__file__),
        "../custom_components/house_battery_control"
    )

    assert os.path.exists(integration_dir), "Integration directory not found."

    for py_file in get_python_files(integration_dir):
        with open(py_file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=py_file)
            except SyntaxError:
                continue

            for node in tree.body:
                # Check import foo
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("pulp"), (
                            f"CRITICAL: Top-level import '{alias.name}' detected in {py_file}. "
                            f"PIP dependencies like PuLP MUST be lazy-loaded inside functions to avoid "
                            f"crashing Home Assistant before the package finishes installing."
                        )
                # Check from foo import bar
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("pulp"):
                        pytest.fail(
                            f"CRITICAL: Top-level 'from {node.module} import ...' detected in {py_file}. "
                            f"PIP dependencies like PuLP MUST be lazy-loaded inside functions to avoid "
                            f"crashing Home Assistant before the package finishes installing."
                        )

def test_lin_fsm_still_operates_with_lazy_loading(base_context):
    """Assert lazy-loading hasn't broken the FSM logic."""
    # This acts as a sanity check against the actual import running dynamically.
    from custom_components.house_battery_control.fsm.lin_fsm import (
        FakeBattery,
        LinearBatteryController,
    )

    controller = LinearBatteryController()
    battery = FakeBattery(capacity=27.0, current_charge=0.5, charge_limit=5.0, discharge_limit=5.0)

    # Passing valid 288-interval lists to match max bounds
    res = controller.propose_state_of_charge(
        site_id=0,
        timestamp="00:00",
        battery=battery,
        actual_previous_load=0,
        actual_previous_pv_production=0,
        price_buy=[10.0]*288,
        price_sell=[5.0]*288,
        load_forecast=[1.0]*288,
        pv_forecast=[0.0]*288,
        acquisition_cost=0.0
    )

    assert res is not None
    assert len(res) == 4

@pytest.fixture
def base_context():
    pass
