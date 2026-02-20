"""Default Battery State Machine — Rule-based deterministic FSM.

Decision logic considers:
- Current grid price (negative, cheap window, peak)
- Solar production and sunrise forecast
- Temperature-sensitive house load
- Battery SoC and reserve levels
- Next cheap charge opportunity vs upcoming peak
"""
import logging
from typing import List, Optional

from ..const import (
    STATE_CHARGE_GRID,
    STATE_CHARGE_SOLAR,
    STATE_DISCHARGE_HOME,
    STATE_IDLE,
    STATE_PRESERVE,
)
from .base import BatteryStateMachine, FSMContext, FSMResult

_LOGGER = logging.getLogger(__name__)

# --- Thresholds (could be made configurable later) ---
RESERVE_SOC = 15.0           # Don't discharge below this %
FULL_SOC = 95.0              # Consider battery "full" above this
CHEAP_PRICE_PERCENTILE = 25  # Bottom 25% of forecast = "cheap"
PEAK_PRICE_PERCENTILE = 75   # Top 25% of forecast = "peak"
PEAK_PRICE_ABSOLUTE = 35.0   # Absolute c/kWh above which = peak
SOLAR_MEANINGFUL_KW = 0.3    # Solar below this is negligible


class DefaultBatteryStateMachine(BatteryStateMachine):
    """Standard rule-based battery control logic."""

    def calculate_next_state(self, context: FSMContext) -> FSMResult:
        """Determine next state using prioritised decision cascade.

        Priority order:
        1. Negative price       → CHARGE_GRID (free energy)
        2. Cheap window + low SoC → CHARGE_GRID
        3. Excess solar         → CHARGE_SOLAR
        4. Peak price + SoC ok  → DISCHARGE_HOME
        5. High load + SoC ok   → DISCHARGE_HOME
        6. Peak coming + SoC ok → PRESERVE
        7. Default              → IDLE
        """

        price = context.current_price
        soc = context.soc
        solar = context.solar_production
        load = context.load_power

        # -------------------------------------------------------
        # 1. NEGATIVE PRICE → always take free energy
        # -------------------------------------------------------
        if price < 0:
            return FSMResult(
                state=STATE_CHARGE_GRID,
                limit_kw=self._max_charge_rate(context),
                reason=f"Negative price ({price:.1f} c/kWh) — charging from grid",
            )

        # -------------------------------------------------------
        # 2. CHEAP WINDOW + battery needs charge
        # -------------------------------------------------------
        cheap_threshold = self._find_cheap_threshold(context.forecast_price)
        is_cheap = price <= cheap_threshold if cheap_threshold is not None else False
        solar_coming = self._solar_coming_soon(context.forecast_solar)

        if is_cheap and soc < FULL_SOC:
            # If solar is coming soon and SoC is moderate, skip grid charge
            if solar_coming and soc > 50.0:
                return FSMResult(
                    state=STATE_IDLE,
                    limit_kw=0.0,
                    reason=f"Cheap price ({price:.1f}) but solar arriving soon, SoC {soc:.0f}% adequate",
                )
            return FSMResult(
                state=STATE_CHARGE_GRID,
                limit_kw=self._max_charge_rate(context),
                reason=f"Cheap window ({price:.1f} c/kWh, threshold {cheap_threshold:.1f}), SoC {soc:.0f}%",
            )

        # -------------------------------------------------------
        # 3. EXCESS SOLAR → charge from solar
        # -------------------------------------------------------
        solar_excess = solar - load
        if solar_excess > SOLAR_MEANINGFUL_KW and soc < FULL_SOC:
            return FSMResult(
                state=STATE_CHARGE_SOLAR,
                limit_kw=solar_excess,
                reason=f"Excess solar {solar_excess:.1f} kW, SoC {soc:.0f}%",
            )

        # -------------------------------------------------------
        # 4. PEAK PRICE → discharge to home
        # -------------------------------------------------------
        is_peak = self._is_peak_price(price, context.forecast_price)
        if is_peak and soc > RESERVE_SOC:
            return FSMResult(
                state=STATE_DISCHARGE_HOME,
                limit_kw=min(load, self._max_discharge_rate(context)),
                reason=f"Peak price ({price:.1f} c/kWh), discharging to serve {load:.1f} kW load",
            )

        # -------------------------------------------------------
        # 5. HIGH LOAD (no solar) → discharge to reduce import
        # -------------------------------------------------------
        if load > 2.0 and solar < SOLAR_MEANINGFUL_KW and soc > RESERVE_SOC and price > 15.0:
            return FSMResult(
                state=STATE_DISCHARGE_HOME,
                limit_kw=min(load, self._max_discharge_rate(context)),
                reason=f"High load ({load:.1f} kW), no solar, price {price:.1f} — discharging",
            )

        # -------------------------------------------------------
        # 6. PRESERVE → peak coming, hold charge
        # -------------------------------------------------------
        peak_coming = self._peak_coming_soon(context.forecast_price)
        if peak_coming and soc > 50.0 and not is_cheap:
            return FSMResult(
                state=STATE_PRESERVE,
                limit_kw=0.0,
                reason=f"Peak price approaching, preserving SoC {soc:.0f}%",
            )

        # -------------------------------------------------------
        # 7. IDLE
        # -------------------------------------------------------
        return FSMResult(
            state=STATE_IDLE,
            limit_kw=0.0,
            reason=f"Normal conditions — SoC {soc:.0f}%, price {price:.1f}, solar {solar:.1f} kW",
        )

    # === Helper Methods ===

    def _find_cheap_threshold(self, forecast_price: List[dict]) -> Optional[float]:
        """Find the price below which we consider it a 'cheap window'.
        Returns the price at the CHEAP_PRICE_PERCENTILE of the forecast."""
        if not forecast_price:
            return None
        prices = sorted([p["price"] for p in forecast_price])
        idx = max(0, int(len(prices) * CHEAP_PRICE_PERCENTILE / 100) - 1)
        return prices[idx]

    def _is_peak_price(self, current_price: float, forecast_price: List[dict]) -> bool:
        """Is the current price in peak territory?"""
        if current_price >= PEAK_PRICE_ABSOLUTE:
            return True
        if not forecast_price:
            return False
        prices = sorted([p["price"] for p in forecast_price])
        idx = min(len(prices) - 1, int(len(prices) * PEAK_PRICE_PERCENTILE / 100))
        return current_price >= prices[idx]

    def _solar_coming_soon(self, forecast_solar: List[dict]) -> bool:
        """Check if meaningful solar production starts within next 60 min."""
        # Look at first 12 slots (60 min of 5-min intervals)
        for slot in forecast_solar[:12]:
            if slot.get("kw", 0) >= SOLAR_MEANINGFUL_KW:
                return True
        return False

    def _peak_coming_soon(self, forecast_price: List[dict]) -> bool:
        """Check if peak pricing is expected within next 2 hours."""
        for slot in forecast_price[:24]:  # 24 * 5min = 2 hours
            if slot.get("price", 0) >= PEAK_PRICE_ABSOLUTE:
                return True
        return False

    def _max_charge_rate(self, context: FSMContext) -> float:
        """Maximum charge rate in kW. Uses 6.3 kW default."""
        return 6.3

    def _max_discharge_rate(self, context: FSMContext) -> float:
        """Maximum discharge rate in kW. Uses 5.0 kW default."""
        return 5.0
