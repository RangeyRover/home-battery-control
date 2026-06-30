"""Logic for the Low Renewables Guard feature.

This guard overrides normal FSM logic to force charging to 100% when
renewables are extremely low (Amber Express < 30%) or Solcast forecast is poor.
"""

import logging
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class RenewablesGuard:
    """Evaluates low-renewables conditions and manages hysteresis state."""

    def __init__(self):
        """Initialize the guard."""
        self.is_active: bool = False
        self.renewables_avg: float | None = None
        self.trigger_reasons: list[str] = []

    def evaluate(
        self,
        rates: list[dict[str, Any]],
        solcast_tomorrow: float,
        trigger_mode: str,
        renewables_threshold: float,
        solcast_threshold: float,
        peak_solar: float,
    ) -> bool:
        """
        Evaluate if the low renewables guard should be active.

        Args:
            rates: Parsed Amber Express rates (must include 'renewables' field)
            solcast_tomorrow: Tomorrow's forecasted solar (kWh)
            trigger_mode: "OR" or "AND"
            renewables_threshold: e.g., 30.0 for 30%
            solcast_threshold: e.g., 50.0 for 50%
            peak_solar: e.g., 40.0 kWh (the reference value for 100% solcast)

        Returns:
            bool: True if guard is active, False otherwise.
        """
        self.trigger_reasons = []

        # 1. Calculate Amber Express 12-hour renewables average
        # We need the first 12 hours = 144 steps (5-minute intervals)
        valid_rates = [r for r in rates if r.get("renewables") is not None]
        if valid_rates:
            # Use up to 12 hours of data
            eval_rates = valid_rates[:144]
            self.renewables_avg = sum(r["renewables"] for r in eval_rates) / len(eval_rates)
        else:
            self.renewables_avg = None

        amber_triggered = False
        if self.renewables_avg is not None:
            # Apply +10% hysteresis if already active
            eff_threshold = (
                renewables_threshold + 10.0 if self.is_active else renewables_threshold
            )
            if self.renewables_avg <= eff_threshold:
                amber_triggered = True
                self.trigger_reasons.append(f"Amber Express ({self.renewables_avg:.1f}% <= {eff_threshold}%)")
        else:
            # If we don't have Amber Express data, it cannot trigger the Amber side
            amber_triggered = False

        # 2. Calculate Solcast condition
        solcast_target_kwh = peak_solar * (solcast_threshold / 100.0)
        solcast_triggered = False
        if solcast_tomorrow <= solcast_target_kwh:
            solcast_triggered = True
            self.trigger_reasons.append(f"Solcast Tomorrow ({solcast_tomorrow:.1f} <= {solcast_target_kwh:.1f} kWh)")

        # 3. Apply Trigger Mode logic
        if trigger_mode.upper() == "AND":
            # If we lack Amber Express data, we can't satisfy AND
            self.is_active = amber_triggered and solcast_triggered
        else:
            # OR mode
            self.is_active = amber_triggered or solcast_triggered

        if self.is_active:
            _LOGGER.info(
                f"Renewables Guard ACTIVE. Reasons: {', '.join(self.trigger_reasons)}"
            )

        return self.is_active

    def resolve_deadline_steps(self, rates: list[dict[str, Any]], deadlines: list[str], base_time: datetime) -> list[int]:
        """
        Convert time strings like '05:00' into solver step indices (0-287).

        Args:
            rates: Parsed rates containing 'start' timestamps for each step.
            deadlines: List of "HH:MM" string deadlines.
            base_time: The t=0 datetime to resolve relative indices.

        Returns:
            list[int]: Step indices corresponding to the deadlines.
        """
        steps = []
        # Fallback local timezone retrieval, assuming base_time has tzinfo
        # We need the time in local timezone to match "05:00" string

        for i, rate in enumerate(rates):
            rate_start = rate.get("start")
            if not rate_start:
                continue

            local_time = dt_util.as_local(rate_start)
            time_str = local_time.strftime("%H:%M")

            if time_str in deadlines:
                steps.append(i)

        return steps
