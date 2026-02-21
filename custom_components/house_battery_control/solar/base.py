from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, TypedDict


class SolarForecastData(TypedDict):
    start: datetime
    kw: float  # Power in kW


class SolarForecastProvider(ABC):
    """Abstract Base Class for Solar Forecast Providers."""

    @abstractmethod
    async def async_get_forecast(self) -> List[SolarForecastData]:
        """Fetch the solar forecast.

        Returns:
            List[SolarForecastData]: A list of forecast intervals (5-minute granularity).
        """
        pass
