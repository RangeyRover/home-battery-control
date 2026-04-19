import re

coord_path = "custom_components/house_battery_control/coordinator.py"
cb_path = "custom_components/house_battery_control/context_builder.py"

with open(coord_path, "r", encoding="utf-8") as f:
    coord_content = f.read()

# 1. Extract _build_solver_inputs (243 to 344)
solver_inputs_match = re.search(r'(    def _build_solver_inputs\(\n(?:        [^\n]*\n|    [^\n]*\n|\n)+?)(?=    async def _async_update_data)', coord_content)

solver_inputs_str = solver_inputs_match.group(1) if solver_inputs_match else ""

# modify it to remove self, change signature
new_solver_inputs = solver_inputs_str.replace("    def _build_solver_inputs(", "def build_solver_inputs(").replace("        self,\n", "").replace("\n    ", "\n")
new_solver_inputs = new_solver_inputs.replace("self.config.get", "config.get")

# 2. Extract align_forecasts from _async_update_data
align_forecasts_logic = """def align_forecasts(rates_timeline: list, solar_forecast: list, load_forecast: list) -> tuple:
    \"\"\"Align solar and load forecasts to the rates timeline.\"\"\"
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

    # Ensure load_forecast is populated to identical precision length
    if not load_forecast:
        load_forecast = [{"kw": 0.0} for _ in range(fallback_len)]
    elif len(load_forecast) < fallback_len:
        # Pad out truncated endpoints to prevent sequence breaks
        for _ in range(fallback_len - len(load_forecast)):
            load_forecast.append({"kw": 0.0})

    return aligned_solar, load_forecast
"""

new_cb_content = f"""from datetime import datetime
from homeassistant.util import dt as dt_util
from collections import namedtuple
import logging

_LOGGER = logging.getLogger(__name__)

from .fsm import SolverInputs
from .const import CONF_NO_IMPORT_PERIODS

{align_forecasts_logic}

{new_solver_inputs}
"""

with open(cb_path, "w", encoding="utf-8") as f:
    f.write(new_cb_content)

print("Context Builder logic extracted!")
