from datetime import datetime, timedelta
from custom_components.house_battery_control.context_builder import align_forecasts
from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

class DummyRates:
    def get_rates(self):
        return []
    def get_import_price_at(self, *args, **kwargs):
        return 0.1
    def get_export_price_at(self, *args, **kwargs):
        return 0.05
    def get_tomorrows_outlook_data(self):
        return [], [0.2] * 288, [0.1] * 288, [1.5] * 288 # synthetic load = 1.5

class DummyWeather:
    def get_forecast(self):
        return []

class DummySolar:
    async def async_get_forecast(self):
        return []

class DummyStore:
    pass

class DummyExecutor:
    pass

class DummyPredictor:
    pass

class DummyFSM:
    pass

class DummyCoordinator(HBCDataUpdateCoordinator):
    def __init__(self):
        class DummyHass:
            pass
        self.hass = DummyHass()
        self.config = {}
        self.config_entry = None
        self.rates = DummyRates()
        self.weather = DummyWeather()
        self.solar = DummySolar()
        self.store = DummyStore()
        self.executor = DummyExecutor()
        self.load_predictor = DummyPredictor()
        self.fsm = DummyFSM()
        self.acquisition_cost = 0.1
        self.cumulative_cost = 0.0

    async def test(self):
        # Create extended rates timeline
        extended_rates_timeline = []
        now = datetime.now()
        for i in range(288):
            extended_rates_timeline.append({
                "start": now + timedelta(minutes=5*i),
                "synthetic_load_kw": 2.5 if i > 200 else 0.0
            })
        
        load_forecast = [{"kw": 1.0} for _ in range(100)]
        solar_forecast = [{"start": now + timedelta(minutes=5*i), "kw": 3.0} for i in range(100)]
        
        aligned_solar, load_forecast = align_forecasts(extended_rates_timeline, solar_forecast, load_forecast)
        print("Aligned Solar Length:", len(aligned_solar))
        print("Aligned Load Length:", len(load_forecast))
        
        si = self._build_solver_inputs(extended_rates_timeline, load_forecast, aligned_solar, 0.1, 0.05)
        print("Solver inputs Load Length:", len(si.load_kwh))
        print("Solver inputs Load [50]:", si.load_kwh[50] * 12) # Should be 1.0
        print("Solver inputs Load [250]:", si.load_kwh[250] * 12) # Should be 2.5 (from synthetic)

import asyncio
if __name__ == "__main__":
    asyncio.run(DummyCoordinator().test())
