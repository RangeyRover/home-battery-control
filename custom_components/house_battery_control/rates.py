import logging
from datetime import datetime, timedelta
from typing import List, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class RateInterval(TypedDict):
    start: datetime
    end: datetime
    import_price: float  # c/kWh
    export_price: float  # c/kWh
    renewables: float | None  # renewables % (Amber Express)
    type: str  # ACTUAL or FORECAST


class RatesManager:
    """Manages fetching and processing tariff rates from Amber Electric."""

    def __init__(
        self,
        hass: HomeAssistant,
        import_entity_id: str,
        export_entity_id: str,
        use_amber_express: bool = False,
        pricing_mode: str = "amber_dynamic",
        config: dict | None = None,
    ):
        self._hass = hass
        self._import_entity_id = import_entity_id
        self._export_entity_id = export_entity_id
        self._use_amber_express = use_amber_express
        self._pricing_mode = pricing_mode
        self._config = config or {}
        self._rates: List[RateInterval] = []

    def update(self) -> None:
        """Fetch latest rates from both import and export sensors."""
        from .const import PRICING_MODE_FIXED_TOU
        if self._pricing_mode == PRICING_MODE_FIXED_TOU:
            from .fixed_tou import FixedTOUGenerator
            gen = FixedTOUGenerator(self._config)

            # Start forecast exactly on the current 5-minute boundary
            now = dt_util.now()
            minute_rounded = (now.minute // 5) * 5
            start_dt = now.replace(minute=minute_rounded, second=0, microsecond=0)

            raw_forecast = gen.generate_forecast(start_dt)

            merged = {}
            for r in raw_forecast:
                key = r["start_time"]
                merged[key] = {
                    "start": r["start_time"],
                    "end": r["end_time"],
                    "import_price": r["per_kwh"],
                    "export_price": 0.0,
                    "renewables": None,
                    "type": r["type"],
                }
            self._rates = sorted(merged.values(), key=lambda x: x["start"])
            _LOGGER.debug(f"Loaded {len(self._rates)} fixed TOU intervals")
            return

        if self._use_amber_express:
            import_rates = self._parse_amber_express_entity(self._import_entity_id, "import")
            export_rates = self._parse_amber_express_entity(self._export_entity_id, "export")
        else:
            import_rates = self._parse_entity(self._import_entity_id, "import")
            export_rates = self._parse_entity(self._export_entity_id, "export")

        # Merge by matching start times
        merged: dict[datetime, RateInterval] = {}
        for r in import_rates:
            key = r["start"]
            merged[key] = {
                "start": r["start"],
                "end": r["end"],
                "import_price": r["price"],
                "export_price": 0.0,
                "renewables": r.get("renewables"),
                "type": r["type"],
            }
        for r in export_rates:
            key = r["start"]
            if key in merged:
                merged[key]["export_price"] = r["price"]
            else:
                merged[key] = {
                    "start": r["start"],
                    "end": r["end"],
                    "import_price": 0.0,
                    "export_price": r["price"],
                    "renewables": r.get("renewables"),
                    "type": r["type"],
                }

        self._rates = sorted(merged.values(), key=lambda x: x["start"])
        _LOGGER.debug(f"Loaded {len(self._rates)} rate intervals")

    def _parse_entity(self, entity_id: str, label: str) -> list:
        """Parse rate intervals from an Amber sensor entity."""
        state = self._hass.states.get(entity_id)
        if not state:
            _LOGGER.warning(f"{label} price entity {entity_id} not found")
            return []

        raw_data = (
            state.attributes.get("forecast")
            or state.attributes.get("forecasts")
            or state.attributes.get("future_prices")
            or state.attributes.get("variable_intervals")
        )

        if not raw_data:
            _LOGGER.warning(f"No forecast data in {entity_id}")
            return []

        parsed = []
        for interval in raw_data:
            try:
                start_ts = dt_util.parse_datetime(
                    interval.get("start_time") or interval.get("periodStart", "")
                )
                end_ts = dt_util.parse_datetime(
                    interval.get("end_time") or interval.get("periodEnd", "")
                )

                if not start_ts or not end_ts:
                    continue

                # Ensure timezone-aware (spec 4: TZ safety)
                start_ts = dt_util.as_utc(start_ts)
                end_ts = dt_util.as_utc(end_ts)

                price = float(interval.get("per_kwh") or interval.get("perKwh", 0))

                # Phase 8: Force chunking all intervals into 5-minute ticks
                chunk_duration = timedelta(minutes=5)
                current_ts = start_ts

                while current_ts < end_ts:
                    next_ts = current_ts + chunk_duration
                    if next_ts > end_ts:
                        next_ts = end_ts

                    parsed.append(
                        {
                            "start": current_ts,
                            "end": next_ts,
                            "price": price,
                            "renewables": None,
                            "type": interval.get("type") or interval.get("periodType", "UNKNOWN"),
                        }
                    )
                    current_ts = next_ts

            except (ValueError, KeyError) as e:
                _LOGGER.error(f"Error parsing {label} rate interval: {e}")
                continue

        parsed.sort(key=lambda x: x["start"])
        return parsed

    def _parse_amber_express_entity(self, entity_id: str, label: str) -> list:
        """Parse rate intervals specifically from an Amber Express sensor's 'forecasts' array."""
        state = self._hass.states.get(entity_id)
        if not state:
            _LOGGER.warning(f"Amber Express {label} price entity {entity_id} not found")
            return []

        # Amber Express explicitly embeds its 24h timeline inside the 'forecasts' attribute array
        raw_data = state.attributes.get("forecasts", [])

        if not raw_data:
            _LOGGER.warning(f"No forecasts array in Amber Express entity {entity_id}")
            return []

        parsed = []
        for interval in raw_data:
            try:
                start_ts = dt_util.parse_datetime(interval.get("start_time", ""))
                end_ts = dt_util.parse_datetime(interval.get("end_time", ""))

                if not start_ts or not end_ts:
                    continue

                # Ensure timezone-aware (spec 4: TZ safety)
                start_ts = dt_util.as_utc(start_ts)
                end_ts = dt_util.as_utc(end_ts)

                renewables = float(interval.get("renewables", 100.0))
                advanced = interval.get("advanced_price_predicted", {})

                predicted_price = float(advanced.get("predicted", interval.get("per_kwh", 0.0)))
                high_price = float(advanced.get("high", predicted_price))

                if renewables >= 35.0:
                    price = predicted_price
                elif renewables <= 25.0:
                    price = high_price
                else:
                    # Linear interpolation between 35% and 25% (a 10% band)
                    ratio_predicted = (renewables - 25.0) / 10.0
                    ratio_high = 1.0 - ratio_predicted
                    price = (ratio_predicted * predicted_price) + (ratio_high * high_price)

                # Phase 8: Force chunking all intervals into 5-minute ticks
                chunk_duration = timedelta(minutes=5)
                current_ts = start_ts

                while current_ts < end_ts:
                    next_ts = current_ts + chunk_duration
                    if next_ts > end_ts:
                        next_ts = end_ts

                    parsed.append(
                        {
                            "start": current_ts,
                            "end": next_ts,
                            "price": price,
                            "renewables": renewables,
                            "type": "FORECAST", # Amber Express is purely forecast arrays
                        }
                    )
                    current_ts = next_ts

            except (ValueError, KeyError, TypeError) as e:
                _LOGGER.error(f"Error parsing Amber Express {label} rate interval: {e}")
                continue

        parsed.sort(key=lambda x: x["start"])
        return parsed

    def get_rates(self) -> List[RateInterval]:
        """Return the processed list of rates."""
        return self._rates

    def get_import_price_at(self, time: datetime) -> float:
        """Get the import price for a specific time."""
        for rate in self._rates:
            if rate["start"] <= time < rate["end"]:
                return rate["import_price"]
        return 0.0

    def get_export_price_at(self, time: datetime) -> float:
        """Get the export price for a specific time."""
        for rate in self._rates:
            if rate["start"] <= time < rate["end"]:
                return rate["export_price"]
        return 0.0
