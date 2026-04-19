import re

coord_path = "custom_components/house_battery_control/coordinator.py"
diag_path = "custom_components/house_battery_control/diagnostics.py"

with open(coord_path, "r", encoding="utf-8") as f:
    coord_content = f.read()

# 1. Extract _build_sensor_diagnostics
sensor_diag_match = re.search(r'(    def _build_sensor_diagnostics\(self, fsm_result, start_time: datetime, target_soc: float, max_charge_rate: float, load_p: float, start_soc: float, price_forecast: list, solar_forecast: list, load_forecast: list\):\n(?:        [^\n]*\n|    [^\n]*\n|\n)+?)(?=    def _build_diagnostic_plan_table)', coord_content)

sensor_diag_str = sensor_diag_match.group(1) if sensor_diag_match else ""

# 2. Extract _build_diagnostic_plan_table
plan_table_match = re.search(r'(    def _build_diagnostic_plan_table\(self, fsm_result, start_time: datetime\):\n(?:        [^\n]*\n|\n)+?)(?=    def _build_solver_inputs)', coord_content)

plan_table_str = plan_table_match.group(1) if plan_table_match else ""

if not sensor_diag_str or not plan_table_str:
    print("Could not find the methods!")
    exit(1)

# Modify methods to be standalone functions
# Remove `self, `
new_sensor_diag = sensor_diag_str.replace("def _build_sensor_diagnostics(self, fsm_result", "def build_sensor_diagnostics(fsm_result").replace("    def ", "def ").replace("        ", "    ").replace("            ", "        ").replace("                ", "            ").replace("                    ", "                ").replace("                        ", "                    ").replace("                            ", "                        ").replace("                                ", "                            ")

new_sensor_diag = new_sensor_diag.replace("self.synthetic_analog_days", "synthetic_analog_days").replace("self.config.get(", "config.get(")

# The new_sensor_diag will need `synthetic_analog_days` and `config` injected. Let's look at its arguments.
# Actually, the spec said `build_sensor_diagnostics(coordinator_state, config)`
# Wait! Instead of completely rewriting all `self.` accesses right now, let's just make it a pure python function
# or actually, we can just pass `self` as `coordinator` to the function for now to ensure NO REGRESSIONS (Strangler pattern principle: extract then refine).

new_sensor_diag = sensor_diag_str.replace("    def _build_sensor_diagnostics(self, fsm_result", "def build_sensor_diagnostics(self, fsm_result").replace("\n    ", "\n")
new_plan_table = plan_table_str.replace("    def _build_diagnostic_plan_table(self, fsm_result, start_time: datetime)", "def build_diagnostic_plan_table(self, fsm_result, start_time: datetime)").replace("\n    ", "\n")

new_diag_content = f"""from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)

{new_plan_table}

{new_sensor_diag}
"""

with open(diag_path, "w", encoding="utf-8") as f:
    f.write(new_diag_content)

# Now modify coordinator.py to call these
new_coord_content = coord_content.replace(sensor_diag_str, f"""    def _build_sensor_diagnostics(self, fsm_result, start_time: datetime, target_soc: float, max_charge_rate: float, load_p: float, start_soc: float, price_forecast: list, solar_forecast: list, load_forecast: list):
        from .diagnostics import build_sensor_diagnostics
        build_sensor_diagnostics(self, fsm_result, start_time, target_soc, max_charge_rate, load_p, start_soc, price_forecast, solar_forecast, load_forecast)

""")

new_coord_content = new_coord_content.replace(plan_table_str, f"""    def _build_diagnostic_plan_table(self, fsm_result, start_time: datetime):
        from .diagnostics import build_diagnostic_plan_table
        build_diagnostic_plan_table(self, fsm_result, start_time)

""")

with open(coord_path, "w", encoding="utf-8") as f:
    f.write(new_coord_content)

print("Diagnostics extracted successfully!")
