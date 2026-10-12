"""
lin_fsm.py — LP FSM (SciPy HiGHS)
===================================
Implements all system requirements from specs/03-lp-fsm-system/system_requirements.md.
"""
try:
    from ..const import SOLVER_TOLERANCE_KWH
    from .base import BatteryStateMachine, FSMContext, FSMResult
except ImportError:
    from base import BatteryStateMachine, FSMContext, FSMResult
    from const import SOLVER_TOLERANCE_KWH

import logging
import math
import statistics
from datetime import time
from time import monotonic

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix, vstack

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  No-Import Period helpers (Feature 010)
# ---------------------------------------------------------------------------
def _parse_no_import_periods(config_str: str) -> list[tuple[time, time]]:
    """Parse comma-separated 'HH:MM-HH:MM' strings into (start, end) time tuples.

    Returns empty list for empty/None input. Invalid entries are logged and skipped.
    """
    if not config_str or not config_str.strip():
        return []
    periods = []
    for part in config_str.split(","):
        part = part.strip()
        if "-" not in part:
            _LOGGER.warning(f"Invalid no-import period (no dash): '{part}'")
            continue
        try:
            start_str, end_str = part.split("-", 1)
            sh, sm = map(int, start_str.strip().split(":"))
            eh, em = map(int, end_str.strip().split(":"))
            periods.append((time(sh, sm), time(eh, em)))
        except (ValueError, IndexError) as e:
            _LOGGER.warning(f"Invalid no-import period '{part}': {e}")
            continue
    return periods


def _is_in_no_import_period(t: time, periods: list[tuple[time, time]]) -> bool:
    """Check if a local time falls within any no-import period.

    Handles midnight-spanning windows (e.g. 22:00-06:00).
    """
    for start, end in periods:
        if start <= end:
            # Normal window: e.g. 15:00-21:00
            if start <= t < end:
                return True
        else:
            # Midnight wrap: e.g. 22:00-06:00
            if t >= start or t < end:
                return True
    return False


# ---------------------------------------------------------------------------
#  FakeBattery — §6 of system requirements
# ---------------------------------------------------------------------------
class FakeBattery:
    """Lightweight battery model constructed from FSMContext config."""

    def __init__(
        self,
        capacity: float,
        current_charge: float,
        charge_limit: float,
        discharge_limit: float,
        charging_efficiency: float = 0.95,
        discharging_efficiency: float = 0.95,
    ):
        self.capacity = capacity
        self.current_charge = current_charge          # fraction 0-1
        self.charging_power_limit = charge_limit      # kW
        self.discharging_power_limit = discharge_limit  # kW
        self.charging_efficiency = charging_efficiency
        self.discharging_efficiency = discharging_efficiency


# ---------------------------------------------------------------------------
#  LinearBatteryController — core LP solver (SciPy translation of GLOP source)
# ---------------------------------------------------------------------------
class LinearBatteryController:
    """Physical battery optimisation with signed tariffs and exact balances.

    Existing public interface; HiGHS integer direction constraints exclude
    simultaneous charge/discharge and import/export under negative tariffs.
    """

    def __init__(self):
        self.step = 288  # Default, overridden dynamically by calculate_next_state

    def propose_state_of_charge(
        self,
        battery: FakeBattery,
        price_buy: list[float],
        price_sell: list[float],
        load_forecast: list[float],
        pv_forecast: list[float],
        acquisition_cost: float = 0.0,
        cumulative_cost: float = 0.0,
        reserve_soc: float = 0.0,
        no_import_steps: set[int] | None = None,
        export_margin: float = 0.0,
        guard_deadline_steps: list[int] | None = None,
    ):
        # Keep the public controller contract; all energies below are kWh/5 min.
        n = len(price_buy)
        self.step = n
        fallback = (battery.current_charge, 0.0, [])
        tol = 1e-6
        started = monotonic()
        arrays = (price_buy, price_sell, load_forecast, pv_forecast)
        params = (battery.capacity, battery.current_charge,
                  battery.charging_power_limit, battery.discharging_power_limit,
                  battery.charging_efficiency, battery.discharging_efficiency,
                  acquisition_cost, cumulative_cost, reserve_soc, export_margin)
        if (not n or any(len(a) != n for a in arrays)
                or not all(np.isfinite(a).all() for a in arrays)
                or not all(math.isfinite(v) for v in params)
                or battery.capacity <= 0 or not 0 <= battery.current_charge <= 1
                or min(battery.charging_power_limit, battery.discharging_power_limit) < 0
                or not 0 < battery.charging_efficiency <= 1
                or not 0 < battery.discharging_efficiency <= 1
                or not 0 <= reserve_soc <= 100 or export_margin < 0
                or min(load_forecast) < 0 or min(pv_forecast) < 0):
            _LOGGER.warning("Invalid solver inputs; no forced action")
            return fallback

        capacity = battery.capacity
        current = capacity * battery.current_charge
        eta_in = battery.charging_efficiency
        eta_out = 1 / battery.discharging_efficiency
        charge_limit = battery.charging_power_limit / 12
        dis_limit = battery.discharging_power_limit / 12
        energy = np.asarray(load_forecast) - np.asarray(pv_forecast)
        # Preserve signed discharge variables, adding two direction indicators.
        # g=site import, c=charge, dh/dg=negative home/grid discharge,
        # s=solar export, b=stored energy, z=charge mode, w=import mode.
        g, c, dh, dg, s, b, z, w = 0, n, 2*n, 3*n, 4*n, 5*n, 6*n+1, 7*n+1
        size = 8*n+1
        obj = np.zeros(size)
        bounds = [(0.0, 0.0)] * size
        integrality = np.zeros(size)
        blocked = no_import_steps or set()
        for i in range(n):
            surplus = max(0.0, -energy[i])
            deficit = max(0.0, energy[i])
            obj[g+i] = price_buy[i]
            obj[dg+i] = price_sell[i] - export_margin
            obj[s+i] = -price_sell[i]
            bounds[g+i] = (0, 0 if i in blocked else deficit+charge_limit)
            bounds[c+i] = (0, charge_limit)
            bounds[dh+i] = (-min(deficit, dis_limit), 0)
            bounds[dg+i] = (-dis_limit, 0) if price_sell[i] > max(0, export_margin) else (0, 0)
            bounds[s+i] = (0, surplus)
            bounds[z+i] = bounds[w+i] = (0, 1)

        # Preserve existing terminal inventory policy, but no positive floor.
        terminal_value = max(0.0, acquisition_cost,
                             (statistics.median(price_buy)+acquisition_cost)/2)
        obj[b+n] = -terminal_value
        reserve = capacity * reserve_soc / 100
        for i in range(n+1):
            reachable = current + i*charge_limit*eta_in
            bounds[b+i] = (min(reserve, reachable), capacity)
        for deadline in guard_deadline_steps or []:
            if 0 < deadline <= n:
                lower, upper = bounds[b+deadline]
                reachable = min(capacity, current+deadline*charge_limit*eta_in)
                bounds[b+deadline] = (max(lower, reachable-SOLVER_TOLERANCE_KWH), upper)

        eq = lil_matrix((2*n+1, size))
        rhs = np.zeros(2*n+1)
        eq[0, b] = 1
        rhs[0] = current
        ub = lil_matrix((4*n, size))
        upper = np.zeros(4*n)
        for i in range(n):
            # Battery export appears on BOTH sides of the site balance and
            # cancels here; meter export is s-dg, never fictitious import slack.
            eq[1+i, g+i] = 1
            eq[1+i, c+i] = -1
            eq[1+i, dh+i] = -1
            eq[1+i, s+i] = -1
            rhs[1+i] = energy[i]
            eq[1+n+i, b+i] = 1
            eq[1+n+i, b+i+1] = -1
            eq[1+n+i, c+i] = eta_in
            eq[1+n+i, dh+i] = eq[1+n+i, dg+i] = eta_out
            # Battery direction and shared discharge limit.
            ub[4*i, c+i], ub[4*i, z+i] = 1, -charge_limit
            ub[4*i+1, dh+i] = ub[4*i+1, dg+i] = -1
            ub[4*i+1, z+i] = dis_limit
            upper[4*i+1] = dis_limit
            # Site cannot import and export in the same model interval.
            ub[4*i+2, g+i] = 1
            ub[4*i+2, w+i] = -(max(0, energy[i])+charge_limit)
            export_limit = max(0, -energy[i])+dis_limit
            ub[4*i+3, s+i], ub[4*i+3, dg+i] = 1, -1
            ub[4*i+3, w+i] = export_limit
            upper[4*i+3] = export_limit
        eq, ub = eq.tocsr(), ub.tocsr()

        def valid(x, local_bounds, matrix, limits, integer_modes):
            # Independent of solver status: never publish a broken trajectory.
            if x is None or len(x) != size or not np.isfinite(x).all():
                return False
            lo, hi = np.asarray(local_bounds).T
            return (np.all(x >= lo-tol) and np.all(x <= hi+tol)
                    and np.max(np.abs(eq @ x-rhs)) <= tol
                    and np.all(matrix @ x <= limits+tol)
                    and np.all(np.abs(x[integer_modes] - np.rint(x[integer_modes])) <= tol))

        def extract(x):
            inventory = current
            average_cost = acquisition_cost
            cash = cumulative_cost
            rows, violations = [], []
            for i in range(n):
                charge = max(0.0, x[c+i])
                home = max(0.0, -x[dh+i])
                export = max(0.0, -x[dg+i])
                imported = max(0.0, x[g+i])
                solar_export = max(0.0, x[s+i])
                grid_charge = max(0.0, charge-max(0.0, -energy[i]))
                # Inventory is stored kWh, not an SoC fraction. Solar has no
                # acquisition cash expenditure; losses affect stored energy.
                if charge > tol:
                    average_cost = (inventory*average_cost + grid_charge*price_buy[i]) / (inventory+charge*eta_in)
                inventory = max(0.0, x[b+i+1])
                if export > tol and price_sell[i]-export_margin < average_cost-tol:
                    violations.append(i)
                exported = solar_export+export
                cash += imported*price_buy[i]-exported*price_sell[i]
                state = ("DISCHARGE_GRID" if export > .005 else
                         "CHARGE_GRID" if grid_charge > .005 else "SELF_CONSUMPTION")
                rows.append({
                    "target_soc": inventory/capacity*100, "state": state,
                    "net_grid": (imported-exported)*12,
                    "load": load_forecast[i]*12, "pv": pv_forecast[i]*12,
                    "import_price": price_buy[i], "export_price": price_sell[i],
                    "acquisition_cost": average_cost, "cumulative_cost": cash,
                    "grid_import_kwh": imported, "grid_export_kwh": exported,
                    "charge_kwh": charge, "discharge_kwh": home+export,
                    "battery_export_kwh": export, "solar_export_kwh": solar_export,
                    "grid_charge_kwh": grid_charge,
                })
            return rows, violations

        solve_infeasible = False

        def solve(no_first_grid_charge=False):
            nonlocal solve_infeasible
            solve_infeasible = False
            local_bounds = list(bounds)
            integer_modes = integrality.copy()
            matrix, limits = ub, upper
            if no_first_grid_charge:
                constraint = lil_matrix((1, size))
                constraint[0, g] = 1
                matrix = vstack([ub, constraint.tocsr()], format="csr")
                limits = np.append(upper, max(0.0, energy[0]))
            # Preserve the acquisition gate through re-solving, never by
            # changing solved charge/discharge or patching future SoC values.
            # Add integer directions only when a relaxation actually uses
            # opposing flows. A physically valid optimum of the relaxation is
            # also an optimum of the full model; no heuristic flow clipping.
            for _ in range(3*n+1):
                remaining = 15.0-(monotonic()-started)
                if remaining <= 0:
                    return None
                result = linprog(obj, A_ub=matrix, b_ub=limits,
                                 A_eq=eq, b_eq=rhs, bounds=local_bounds,
                                 integrality=integer_modes, method="highs",
                                 options={"time_limit": remaining, "mip_rel_gap": 0.001})
                if not result.success or not valid(result.x, local_bounds, matrix, limits, integer_modes.astype(bool)):
                    solve_infeasible = not result.success and getattr(result, "status", None) == 2
                    _LOGGER.warning("Physical solver rejected: %s", getattr(result, "message", "invalid trajectory"))
                    return None
                x = result.x
                conflicting_battery = (x[c:c+n] > tol) & (-(x[dh:dh+n]+x[dg:dg+n]) > tol)
                conflicting_grid = (x[g:g+n] > tol) & ((x[s:s+n]-x[dg:dg+n]) > tol)
                if conflicting_battery.any() or conflicting_grid.any():
                    additions = np.zeros(size)
                    additions[z:z+n] = conflicting_battery
                    additions[w:w+n] = conflicting_grid
                    if not np.any(additions > integer_modes):
                        return None
                    integer_modes = np.maximum(integer_modes, additions)
                    continue
                rows, violations = extract(result.x)
                if not violations:
                    return result, rows
                for i in violations:
                    local_bounds[dg+i] = (0, 0)
            return None

        chosen = solve()
        if chosen is None:
            return fallback
        result, sequence = chosen
        # Negative-price charging must beat the same future with current grid
        # charging disabled, including later solar spill and terminal inventory.
        if price_buy[0] < 0 and sequence[0]["grid_charge_kwh"] > tol:
            reference = solve(no_first_grid_charge=True)
            if reference is None:
                # A reserve/deadline may mandate charging. Do not claim an
                # economic benefit when the comparison is infeasible.
                if not solve_infeasible or (not guard_deadline_steps and current >= reserve-tol):
                    return fallback
                sequence[0]["charge_reason"] = "Reserve/deadline constraint"
            else:
                ref_result, ref_rows = reference
                # A MIP can finish within its optimality gap. Only admit paid
                # charging if its feasible cost beats the reference LOWER
                # bound, not merely the cost of a possibly suboptimal reference.
                reference_bound = getattr(ref_result, "mip_dual_bound", None)
                if reference_bound is None:
                    reference_bound = float(obj @ ref_result.x)
                saving = float(reference_bound - obj @ result.x)
                if not math.isfinite(saving):
                    return fallback
                cash_saving = ref_rows[-1]["cumulative_cost"]-sequence[-1]["cumulative_cost"]
                if saving <= tol:
                    result, sequence = reference
                sequence[0]["charge_comparison_saving"] = max(0.0, saving)
                sequence[0]["charge_comparison_cash_saving"] = cash_saving if saving > tol else 0.0
        # Report real meter cash, not the optimisation objective/terminal credit.
        projected_cost = sequence[-1]["cumulative_cost"]-cumulative_cost
        return sequence[0]["target_soc"]/100, projected_cost, sequence



# ---------------------------------------------------------------------------
#  LinearBatteryStateMachine — adapter for FSMContext/FSMResult interface
# ---------------------------------------------------------------------------
class LinearBatteryStateMachine(BatteryStateMachine):
    """
    Wraps LinearBatteryController to satisfy the BatteryStateMachine ABC.
    This is the entry point for both hybrid_tester.py and coordinator.py.
    """

    def __init__(self):
        self.controller = LinearBatteryController()

    def calculate_next_state(self, context: FSMContext) -> FSMResult:
        # --- Fail-fast if solver_inputs not populated (FR-008) ---
        if context.solver_inputs is None:
            return FSMResult(
                state="ERROR",
                limit_kw=0.0,
                reason="solver_inputs not populated by coordinator",
            )

        # Force dynamic step horizon based on populated inputs
        number_step = len(context.solver_inputs.price_buy)
        self.controller.step = number_step

        # --- Read pre-built arrays from solver_inputs (Feature 024) ---
        si = context.solver_inputs
        price_buy = list(si.price_buy)
        price_sell = list(si.price_sell)
        load_f = list(si.load_kwh)
        pv_f = list(si.pv_kwh)
        no_import_steps = si.no_import_steps if si.no_import_steps else set()

        # --- Battery model — §6 ---
        capacity = max(13.5, context.config.get("battery_capacity",
                       context.config.get("capacity_kwh", 27.0)))
        limit_kw_charge = float(context.config.get("battery_rate_max", 6.3))
        limit_kw_discharge = float(context.config.get("inverter_limit", 10.0))
        current_soc = max(0.0, min(100.0, context.soc)) / 100.0

        rte = float(context.config.get("round_trip_efficiency", 0.90))
        one_way_eff = math.sqrt(rte)

        battery = FakeBattery(
            capacity=capacity,
            current_charge=current_soc,
            charge_limit=limit_kw_charge,
            discharge_limit=limit_kw_discharge,
            charging_efficiency=one_way_eff,
            discharging_efficiency=one_way_eff,
        )

        try:
            target_soc_frac, projected_cost, sequence = (
                self.controller.propose_state_of_charge(
                    battery=battery,
                    price_buy=price_buy,
                    price_sell=price_sell,
                    load_forecast=load_f,
                    pv_forecast=pv_f,
                    acquisition_cost=context.acquisition_cost,
                    cumulative_cost=context.cumulative_cost,
                    reserve_soc=float(context.config.get("reserve_soc", 0.0)),
                    no_import_steps=no_import_steps if no_import_steps else None,
                    export_margin=float(context.config.get("export_margin", 0.0)),
                    guard_deadline_steps=si.guard_deadline_steps,
                )
            )
        except Exception as e:
            _LOGGER.error("LP Solver failed: %s", e)
            return FSMResult(state="ERROR", limit_kw=0.0, reason=f"Solver Error: {e}")

        if target_soc_frac is None:
            return FSMResult(state="ERROR", limit_kw=0.0, reason="Solver returned None")

        target_soc_frac = float(target_soc_frac)

        # Defence at the existing calculation boundary. Row zero is the live
        # price supplied by the input builder. Never forward a contradictory
        # recommendation, even if a solver implementation returns one.
        if sequence and sequence[0]["state"] == "DISCHARGE_GRID":
            sell_now = price_sell[0]
            margin = float(context.config.get("export_margin", 0.0))
            if not math.isfinite(sell_now) or sell_now <= max(0.0, margin):
                return FSMResult(
                    state="SELF_CONSUMPTION", limit_kw=0.0,
                    reason="Battery export blocked by nonpositive effective tariff",
                    target_soc=current_soc * 100.0, future_plan=[],
                )

        # --- FR-001 (026): Single state source from sequence[0] ---
        if sequence:
            state_0 = sequence[0]["state"]
        else:
            state_0 = "SELF_CONSUMPTION"  # FR-003: safe default

        # --- Immediate action limit_kw — FR-002: calculation unchanged ---
        target_delta_kwh = (target_soc_frac - current_soc) * capacity
        power_kw = target_delta_kwh * 12.0  # kWh per 5-min → kW

        if state_0 == "CHARGE_GRID" and power_kw > 0.01:
            req = power_kw / battery.charging_efficiency
            limit_kw = round(min(limit_kw_charge, req), 2)
        elif state_0 == "DISCHARGE_GRID" and power_kw < -0.01:
            req = abs(power_kw) * battery.discharging_efficiency
            limit_kw = round(min(limit_kw_discharge, req), 2)
        else:
            limit_kw = 0.0

        reason_map = {
            "CHARGE_GRID": "LP Optimized Charge",
            "DISCHARGE_GRID": "LP Optimized Grid Export",
            "SELF_CONSUMPTION": "LP Optimized Self-Consumption",
        }

        return FSMResult(
            state=state_0,
            limit_kw=limit_kw,
            reason=reason_map.get(state_0, "LP Optimization: No action needed"),
            target_soc=target_soc_frac * 100.0,
            projected_cost=projected_cost,
            future_plan=sequence,
        )
