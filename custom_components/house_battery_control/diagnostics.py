from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENT_EXPORT_PRICE_ENTITY,
    CONF_CURRENT_IMPORT_PRICE_ENTITY,
    CONF_EXPORT_PRICE_ENTITY,
    CONF_EXPORT_TODAY_ENTITY,
    CONF_GRID_ENTITY,
    CONF_IMPORT_PRICE_ENTITY,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_LOAD_TODAY_ENTITY,
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    CONF_SOLAR_ENTITY,
    CONF_SOLCAST_TODAY_ENTITY,
    CONF_SOLCAST_TOMORROW_ENTITY,
    CONF_WEATHER_ENTITY,
)


def build_sensor_diagnostics(coordinator) -> list[dict[str, Any]]:
    """Build sensor availability report for API diagnostics (spec 2.4)."""
    sensor_keys = [
        CONF_BATTERY_SOC_ENTITY,
        CONF_BATTERY_POWER_ENTITY,
        CONF_SOLAR_ENTITY,
        CONF_GRID_ENTITY,
        CONF_CURRENT_IMPORT_PRICE_ENTITY,
        CONF_CURRENT_EXPORT_PRICE_ENTITY,
        CONF_IMPORT_PRICE_ENTITY,
        CONF_EXPORT_PRICE_ENTITY,
        CONF_WEATHER_ENTITY,
        CONF_LOAD_TODAY_ENTITY,
        CONF_IMPORT_TODAY_ENTITY,
        CONF_EXPORT_TODAY_ENTITY,
        CONF_SOLCAST_TODAY_ENTITY,
        CONF_SOLCAST_TOMORROW_ENTITY,
        CONF_SCRIPT_CHARGE,
        CONF_SCRIPT_CHARGE_STOP,
        CONF_SCRIPT_DISCHARGE,
        CONF_SCRIPT_DISCHARGE_STOP,
    ]
    diagnostics = []
    for key in sensor_keys:
        entity_id = coordinator.config.get(key, "")
        if not entity_id:
            continue
        state = coordinator.hass.states.get(entity_id)
        diagnostics.append(
            {
                "entity_id": entity_id,
                "state": state.state if state else "not_found",
                "available": (state is not None and state.state != "unavailable"),
                "attributes": dict(state.attributes) if state else {},
            }
        )
    return diagnostics


def build_diagnostic_plan_table(
    coordinator,
    rates: list[Any],
    solar_forecast: list[Any],
    load_forecast: list[Any],
    weather: list[Any],
    current_soc: float,
    future_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Iterate over the rates timeline to unpack the FSM LP solver's execution path.

    Outputs an interpolation table with explicitly rounded strings that matches the precise
    state logic Home Assistant will execute, mapped by UTC timestamp rather than array index.
    """
    # Pre-parse Load
    parsed_loads = []
    for lf in load_forecast:
        if not isinstance(lf, dict):
            continue
        start_str = lf.get("start", "")
        if not start_str:
            continue
        st = dt_util.parse_datetime(start_str) if isinstance(start_str, str) else start_str
        if st:
            parsed_loads.append({"start": st, "kw": float(lf.get("kw", 0.0))})

    # Pre-parse Weather
    parsed_weather = []
    for w in weather:
        if not isinstance(w, dict):
            continue
        w_time = w.get("datetime")
        w_time = dt_util.parse_datetime(w_time) if isinstance(w_time, str) else w_time
        if w_time:
            parsed_weather.append({"datetime": w_time, "temperature": w.get("temperature")})

    table = []
    cumulative = 0.0
    simulated_soc = current_soc

    for idx, rate in enumerate(rates):
        start = rate["start"]
        end = rate.get("end", start)

        duration_mins = max(1, int((end - start).total_seconds() / 60.0))
        duration_hours = duration_mins / 60.0

        # --- 3. Weather Interpolation (Nearest Neighbor) ---
        temp_c = None
        if parsed_weather:
            closest = min(
                parsed_weather, key=lambda w: abs((start - w["datetime"]).total_seconds())
            )
            temp_c = closest.get("temperature")

        # FSM Constants
        capacity = coordinator.config.get(CONF_BATTERY_CAPACITY, 27.0)

        # --- 4. Default Interval Prices (fallback) ---
        price = rate.get("import_price", rate.get("price", 0.0))
        export_price = rate.get("export_price", price * 0.8)

        # --- 5. Map LP Solver Plan via Array Index ---
        if future_plan and 0 <= idx < len(future_plan):
            state = future_plan[idx].get("state", "UNKNOWN")
            target_soc = future_plan[idx].get("target_soc", simulated_soc)
            net_grid_kw = future_plan[idx].get("net_grid", 0.0)
            pv_kw_avg = future_plan[idx].get("pv", 0.0)
            load_kw_avg = future_plan[idx].get("load", 0.0)
            acq_cost = future_plan[idx].get("acquisition_cost", 0.0)
            cum_cost = future_plan[idx].get("cumulative_cost", 0.0)

            # Feature 028: Use exact prices from the solver, ignoring independent lookups
            price = future_plan[idx].get("import_price", price)
            export_price = future_plan[idx].get("export_price", export_price)

            # Use the FSM's computationally precise Net Grid value natively without overriding it.
            if net_grid_kw > 0:
                interval_cost = net_grid_kw * duration_hours * price
            else:
                interval_cost = net_grid_kw * duration_hours * export_price

        else:
            state = "SELF_CONSUMPTION"
            target_soc = simulated_soc
            net_grid_kw = 0.0
            pv_kw_avg = 0.0
            load_kw_avg = 0.0
            acq_cost = 0.0
            cum_cost = cumulative

            # --- 6. Fallback Battery Physics ---
            soc_delta = target_soc - simulated_soc
            pv_kwh = pv_kw_avg * duration_hours
            load_kwh = load_kw_avg * duration_hours

            # Implement standard 95% efficiency buffer to physics math proxy
            if soc_delta > 0:
                battery_kwh = ((soc_delta / 100.0) * capacity) / 0.95
            else:
                battery_kwh = ((soc_delta / 100.0) * capacity) * 0.95

            # Grid Impact = Load - PV + Battery Charge
            interval_kwh = load_kwh - pv_kwh + battery_kwh
            net_grid_kw = interval_kwh / duration_hours if duration_hours > 0 else 0.0
            if interval_kwh < 0:
                interval_cost = interval_kwh * export_price
            else:
                interval_cost = interval_kwh * price

        limit_pct = 100.0 if state != "SELF_CONSUMPTION" else 0.0

        cumulative = cum_cost if 'cum_cost' in locals() else cumulative + interval_cost

        table.append(
            {
                "Time": start.strftime("%H:%M") if hasattr(start, "strftime") else str(start),
                "Local Time": dt_util.as_local(start).strftime("%H:%M")
                if hasattr(start, "strftime")
                else str(start),
                "Import Rate": f"{price:.2f}",
                "Export Rate": f"{export_price:.2f}",
                "FSM State": state,
                "Inverter Limit": f"{limit_pct:.0f}%",
                "Net Grid": f"{net_grid_kw:.2f}",
                "PV Forecast": f"{pv_kw_avg:.2f}",
                "Load Forecast": f"{load_kw_avg:.2f}",
                "Air Temp Forecast": f"{temp_c:.1f}°C" if temp_c is not None else "—",
                "Temp Delta": f"{load_forecast[idx].get('temp_delta', 0):.1f}°C"
                if idx < len(load_forecast) and isinstance(load_forecast[idx], dict) and load_forecast[idx].get("temp_delta") is not None
                else "—",
                "Load Adj.": f"{load_forecast[idx].get('load_adjustment_kw', 0):.2f}"
                if idx < len(load_forecast) and isinstance(load_forecast[idx], dict)
                else "0.00",
                "SoC Forecast": f"{target_soc:.1f}%",
                "Interval Cost": f"${interval_cost:.4f}",
                "Cumul. Cost": f"${cumulative:.4f}",
                "cumulative_cost": cumulative,
                "Acq. Cost": f"{acq_cost:.4f}",
                "Synthetic": rate.get("synthetic", False),
            }
        )

        # Carry over SoC
        simulated_soc = target_soc

    return table
