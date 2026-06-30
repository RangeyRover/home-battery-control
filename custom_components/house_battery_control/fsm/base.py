from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SolverInputs:
    """Pre-built solver input arrays prepared by the coordinator."""
    price_buy: list[float]                  # 288 import prices (c/kWh), t=0 = live
    price_sell: list[float]                 # 288 export prices (c/kWh), t=0 = live
    load_kwh: list[float]                   # 288 load values (kWh per 5-min step)
    pv_kwh: list[float]                     # 288 solar values (kWh per 5-min step)
    no_import_steps: set[int] | None = None # blocked step indices
    guard_deadline_steps: list[int] | None = None  # Step indices targeting 100% SoC


@dataclass
class FSMContext:
    soc: float  # Current Battery %
    solar_production: float  # Current kW
    load_power: float  # Current kW
    grid_voltage: float  # Volts (Optional)
    current_price: float  # c/kWh
    forecast_solar: list[Any]  # Next 24h
    forecast_load: list[Any]  # Next 24h
    forecast_price: list[Any]  # Next 24h
    config: dict[str, Any]  # System config constraints
    acquisition_cost: float = 0.0  # c/kWh, Default 0.0
    cumulative_cost: float = 0.0  # $, Default 0.0
    current_export_price: float = 0.0  # c/kWh, explicitly passed for t=0
    solver_inputs: SolverInputs | None = None  # Pre-built arrays for LP solver


@dataclass
class FSMResult:
    state: str
    limit_kw: float
    reason: str
    target_soc: float | None = None
    projected_cost: float | None = None
    future_plan: list[dict[str, Any]] | None = None


class BatteryStateMachine(ABC):
    """Abstract Base Class for Battery Control Logic."""

    @abstractmethod
    def calculate_next_state(self, context: FSMContext) -> FSMResult:
        """Determines the next state and control limits.

        Args:
            context (FSMContext): The current system state and forecasts.

        Returns:
            FSMResult: The calculated state, power limit, and reasoning.
        """
        pass
