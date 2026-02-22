from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


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
    acquisition_cost: float = 0.0  # c/kWh accumulator


@dataclass
class FSMResult:
    state: str
    limit_kw: float
    reason: str
    target_soc: float | None = None
    projected_cost: float | None = None


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
