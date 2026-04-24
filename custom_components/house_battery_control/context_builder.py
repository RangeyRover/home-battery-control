import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .const import CONF_NO_IMPORT_PERIODS
from .fsm.base import SolverInputs
from .fsm.lin_fsm import _is_in_no_import_period, _parse_no_import_periods

_LOGGER = logging.getLogger(__name__)


def align_forecasts(rates_timeline: list[Any], solar_forecast: list[Any], load_forecast: list[Any]) -> tuple:
    """Align solar and load forecasts to the rates timeline."""
    aligned_solar = []
    fallback_len = len(rates_timeline) if rates_timeline else 288

    if rates_timeline and solar_forecast:
        for rate in rates_timeline:
            rate_start = rate["start"]
            # Nearest neighbor O(N) alignment
            closest = min(
                solar_forecast, key=lambda x: abs((x["start"] - rate_start).total_seconds())
            )
            # If within 30 minutes, assume valid, otherwise 0
            if abs((closest["start"] - rate_start).total_seconds()) <= 1800:
                aligned_solar.append({"kw": closest["kw"]})
            else:
                aligned_solar.append({"kw": 0.0})
    else:
        # Provide a zeroed array of exact length to prevent FSM aborting via min(lengths)
        aligned_solar = [{"kw": 0.0} for _ in range(fallback_len)]

    # Let _build_solver_inputs handle any length discrepancies or synthetic fallbacks.

    return aligned_solar, load_forecast


def build_solver_inputs(
    config: dict[str, Any],
    rates_list: list[Any],
    forecast_load: list[Any],
    forecast_solar: list[Any],
    current_price: float,
    current_export_price: float,
) -> SolverInputs:
    """Build clean float arrays for the LP solver (Feature 024).

    Converts raw forecast dicts into typed float arrays of exactly 288
    elements, overrides row-0 with live prices, converts kW to kWh,
    and resolves no-import periods into step indices.
    """
    n = 288

    # --- Price arrays ---
    price_buy: list[float] = []
    price_sell: list[float] = []
    for i in range(n):
        if i < len(rates_list):
            entry = rates_list[i]
            price_buy.append(float(entry.get("import_price", 0.0)))
            price_sell.append(float(entry.get("export_price", 0.0)))
        elif price_buy:
            price_buy.append(price_buy[-1])
            price_sell.append(price_sell[-1])
        else:
            price_buy.append(0.0)
            price_sell.append(0.0)

    # Override row-0 with live price (FR-002)
    if current_price is not None:
        price_buy[0] = float(current_price)
    elif rates_list:
        price_buy[0] = float(rates_list[0].get("import_price", 0.0))

    if current_export_price is not None:
        price_sell[0] = float(current_export_price)
    elif rates_list:
        price_sell[0] = float(rates_list[0].get("export_price", 0.0))

    # --- Load / PV arrays (kW → kWh per 5-min step) ---
    step_hours = 5.0 / 60.0

    load_kwh: list[float] = []
    for i in range(n):
        if i < len(forecast_load):
            entry = forecast_load[i]
            kw = float(entry.get("kw", 0.0)) if isinstance(entry, dict) else 0.0
            load_kwh.append(kw * step_hours)
        elif load_kwh:
            load_kwh.append(load_kwh[-1])
        else:
            load_kwh.append(0.0)

    pv_kwh: list[float] = []
    for i in range(n):
        if i < len(forecast_solar):
            entry = forecast_solar[i]
            kw = float(entry.get("kw", 0.0)) if isinstance(entry, dict) else 0.0
            pv_kwh.append(kw * step_hours)
        elif pv_kwh:
            pv_kwh.append(pv_kwh[-1])
        else:
            pv_kwh.append(0.0)

    # --- No-import period resolution (FR-004) ---
    no_import_steps: set[int] | None = None
    no_import_cfg = config.get(CONF_NO_IMPORT_PERIODS, "")
    if no_import_cfg:
        periods = _parse_no_import_periods(no_import_cfg)
        if periods:
            blocked: set[int] = set()
            for t in range(n):
                if t < len(rates_list):
                    rate_start = rates_list[t].get("start")
                    if rate_start is not None:
                        local_time = dt_util.as_local(rate_start).time()
                        if _is_in_no_import_period(local_time, periods):
                            blocked.add(t)
                else:
                    # Beyond rates data — extrapolate time
                    if rates_list:
                        from datetime import timedelta
                        last_start = rates_list[-1].get("start")
                        if last_start is not None:
                            extrapolated = last_start + timedelta(minutes=5 * (t - len(rates_list) + 1))
                            local_time = dt_util.as_local(extrapolated).time()
                            if _is_in_no_import_period(local_time, periods):
                                blocked.add(t)
            no_import_steps = blocked if blocked else None

    return SolverInputs(
        price_buy=tuple(price_buy),
        price_sell=tuple(price_sell),
        load_kwh=tuple(load_kwh),
        pv_kwh=tuple(pv_kwh),
        no_import_steps=frozenset(no_import_steps) if no_import_steps else frozenset(),
    )
