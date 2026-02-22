from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class FSMContext:
    soc: float  # Current Battery %
    solar_production: float  # Current kW
    load_power: float  # Current kW
    grid_voltage: float  # Volts (Optional)
    current_price: float  # c/kWh
    forecast_solar: List[dict]  # Next 24h
    forecast_load: List[dict]  # Next 24h
    forecast_price: List[dict]  # Next 24h
    config: dict  # System config constraints


@dataclass
class FSMResult:
    state: str
    limit_kw: float
    reason: str


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
