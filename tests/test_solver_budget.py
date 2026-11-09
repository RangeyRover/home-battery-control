"""Tests for US4 (non-destructive solver time budget & telemetry) and US5 (80% guard target SoC)."""

from unittest.mock import patch

import pytest
from custom_components.house_battery_control.fsm.base import (
    FSMContext,
    FSMResult,
    SolverInputs,
)
from custom_components.house_battery_control.fsm.lin_fsm import (
    FakeBattery,
    LinearBatteryController,
    LinearBatteryStateMachine,
)

EXPECTED_ROW_KEYS = {
    "target_soc",
    "state",
    "net_grid",
    "load",
    "pv",
    "import_price",
    "export_price",
    "acquisition_cost",
    "cumulative_cost",
    "grid_import_kwh",
    "grid_export_kwh",
    "charge_kwh",
    "discharge_kwh",
    "battery_export_kwh",
    "solar_export_kwh",
    "grid_charge_kwh",
}

EXPECTED_STATS_KEYS = {
    "solve_seconds",
    "budget_seconds",
    "passes",
    "integer_used",
    "reference_solve",
    "outcome",
    "detail",
    "horizon_steps",
}


def _make_battery(current_charge: float = 0.5) -> FakeBattery:
    return FakeBattery(
        capacity=27.0,
        current_charge=current_charge,
        charge_limit=6.3,
        discharge_limit=5.0,
        charging_efficiency=0.95,
        discharging_efficiency=0.95,
    )


def test_controller_defaults():
    """Controller initializes with 30.0s budget, 100.0% guard target SoC, and last_solve_stats=None."""
    ctrl = LinearBatteryController()
    assert ctrl.time_budget_s == 30.0
    assert ctrl.guard_target_soc == 100.0
    assert ctrl.last_solve_stats is None


@pytest.mark.parametrize(
    "scenario,kwargs",
    [
        (
            "positive_arbitrage",
            {
                "price_buy": [0.10] * 6 + [0.45] * 6,
                "price_sell": [0.05] * 6 + [0.35] * 6,
                "load_forecast": [0.08] * 12,
                "pv_forecast": [0.04] * 12,
            },
        ),
        (
            "negative_import_with_ref_solve",
            {
                "price_buy": [-0.15, -0.10] + [0.30] * 10,
                "price_sell": [-0.02, -0.02] + [0.20] * 10,
                "load_forecast": [0.08] * 12,
                "pv_forecast": [0.15] * 12,
            },
        ),
        (
            "inverted_negative_import_positive_export",
            {
                "price_buy": [-0.10] * 4 + [0.25] * 8,
                "price_sell": [0.05] * 4 + [0.15] * 8,
                "load_forecast": [0.06] * 12,
                "pv_forecast": [0.12] * 12,
            },
        ),
        (
            "guard_deadline_100pct",
            {
                "price_buy": [0.20] * 12,
                "price_sell": [0.05] * 12,
                "load_forecast": [0.04] * 12,
                "pv_forecast": [0.0] * 12,
                "guard_deadline_steps": [8],
            },
        ),
        (
            "no_import_blocked_steps",
            {
                "price_buy": [0.05] * 6 + [0.40] * 6,
                "price_sell": [0.02] * 6 + [0.30] * 6,
                "load_forecast": [0.08] * 12,
                "pv_forecast": [0.0] * 12,
                "no_import_steps": {0, 1},
            },
        ),
    ],
)
def test_solver_sequence_schema_and_stats_invariance(scenario, kwargs):
    """T019/T020: Verify sequence schema is unchanged and last_solve_stats is populated."""
    ctrl = LinearBatteryController()
    soc, cost, seq = ctrl.propose_state_of_charge(
        battery=_make_battery(0.5),
        acquisition_cost=0.08,
        reserve_soc=15.0,
        **kwargs,
    )
    assert isinstance(soc, float)
    assert isinstance(cost, float)
    assert len(seq) == 12
    for row in seq:
        assert EXPECTED_ROW_KEYS.issubset(set(row.keys()))

    stats = ctrl.last_solve_stats
    assert stats is not None
    assert set(stats.keys()) == EXPECTED_STATS_KEYS
    assert stats["outcome"] == "optimal"
    assert stats["budget_seconds"] == 30.0
    assert stats["passes"] >= 1
    assert stats["horizon_steps"] == 12
    assert stats["detail"] == ""
    assert stats["solve_seconds"] >= 0.0

    if scenario == "negative_import_with_ref_solve":
        assert stats["reference_solve"] is True
        assert stats["passes"] >= 2


def test_solver_timeout_non_destructive_fallback():
    """T020: Exhausting time_budget_s returns empty sequence and outcome == 'timeout'."""
    ctrl = LinearBatteryController()
    ctrl.time_budget_s = 5.0

    calls = [100.0, 106.0, 106.1]

    def fake_monotonic():
        return calls.pop(0) if calls else 106.2

    with patch(
        "custom_components.house_battery_control.fsm.lin_fsm.monotonic",
        side_effect=fake_monotonic,
    ):
        soc, cost, seq = ctrl.propose_state_of_charge(
            battery=_make_battery(0.425),
            price_buy=[0.20] * 6,
            price_sell=[0.05] * 6,
            load_forecast=[0.08] * 6,
            pv_forecast=[0.04] * 6,
        )

    assert soc == 0.425
    assert cost == 0.0
    assert seq == []
    assert ctrl.last_solve_stats is not None
    assert ctrl.last_solve_stats["outcome"] == "timeout"
    assert ctrl.last_solve_stats["budget_seconds"] == 5.0
    assert "exceeded" in ctrl.last_solve_stats["detail"].lower()


def test_solver_invalid_input_reports_no_plan():
    """T020: Invalid inputs report outcome == 'no_plan' with passes == 0 and non-empty detail."""
    ctrl = LinearBatteryController()
    soc, cost, seq = ctrl.propose_state_of_charge(
        battery=_make_battery(0.5),
        price_buy=[0.20] * 4,
        price_sell=[0.05] * 4,
        load_forecast=[-0.1] * 4,  # invalid negative load
        pv_forecast=[0.0] * 4,
    )
    assert soc == 0.5
    assert cost == 0.0
    assert seq == []
    assert ctrl.last_solve_stats is not None
    assert ctrl.last_solve_stats["outcome"] == "no_plan"
    assert ctrl.last_solve_stats["passes"] == 0
    assert ctrl.last_solve_stats["detail"] != ""


def test_guard_target_soc_80_percent_at_deadline():
    """T020/US5: guard_target_soc=80.0 targets 80% capacity at deadline instead of 100%."""
    price_buy = [0.25] * 24
    price_sell = [0.05] * 24
    load_f = [0.04] * 24
    pv_f = [0.0] * 24

    ctrl_80 = LinearBatteryController()
    ctrl_80.guard_target_soc = 80.0
    _, _, seq_80 = ctrl_80.propose_state_of_charge(
        battery=_make_battery(0.65),
        price_buy=price_buy,
        price_sell=price_sell,
        load_forecast=load_f,
        pv_forecast=pv_f,
        guard_deadline_steps=[20],
    )
    soc_at_deadline_80 = seq_80[19]["target_soc"]
    assert 79.5 <= soc_at_deadline_80 <= 81.0

    ctrl_100 = LinearBatteryController()
    ctrl_100.guard_target_soc = 100.0
    _, _, seq_100 = ctrl_100.propose_state_of_charge(
        battery=_make_battery(0.65),
        price_buy=price_buy,
        price_sell=price_sell,
        load_forecast=load_f,
        pv_forecast=pv_f,
        guard_deadline_steps=[20],
    )
    soc_at_deadline_100 = seq_100[19]["target_soc"]
    assert soc_at_deadline_100 >= 99.5


def test_fsm_adapter_populates_solver_stats_and_clamps_budget():
    """T020: LinearBatteryStateMachine clamps budget to [1.0, 60.0], passes guard_target_soc, and populates FSMResult.solver_stats."""
    fsm = LinearBatteryStateMachine()
    inputs = SolverInputs(
        price_buy=[0.25] * 12,
        price_sell=[0.05] * 12,
        load_kwh=[0.04] * 12,
        pv_kwh=[0.0] * 12,
        no_import_steps=set(),
        guard_deadline_steps=[8],
    )
    context = FSMContext(
        soc=70.0,
        solar_production=0.0,
        load_power=0.5,
        grid_voltage=240.0,
        current_price=25.0,
        forecast_solar=[],
        forecast_load=[],
        forecast_price=[],
        config={
            "capacity_kwh": 27.0,
            "battery_rate_max": 6.3,
            "inverter_limit": 10.0,
            "reserve_soc": 15.0,
            "round_trip_efficiency": 0.90,
            "export_margin": 0.02,
            "solver_time_budget": 120.0,  # should clamp to 60.0
            "guard_target_soc": 80.0,
        },
        acquisition_cost=0.08,
        solver_inputs=inputs,
    )
    result: FSMResult = fsm.calculate_next_state(context)
    assert result.solver_stats is not None
    assert result.solver_stats["budget_seconds"] == 60.0
    assert result.solver_stats["outcome"] == "optimal"
    soc_step_8 = result.future_plan[7]["target_soc"]
    assert 79.5 <= soc_step_8 <= 81.5
