"""Constants for the House Battery Control integration."""

DOMAIN = "house_battery_control"

# Config Keys
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_BATTERY_POWER_ENTITY = "battery_power_entity"
CONF_BATTERY_POWER_INVERT = "battery_power_invert"
CONF_SOLAR_ENTITY = "solar_entity"
CONF_GRID_ENTITY = "grid_entity"
CONF_GRID_POWER_INVERT = "grid_power_invert"
CONF_IMPORT_PRICE_ENTITY = "import_price_entity"
CONF_EXPORT_PRICE_ENTITY = "export_price_entity"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_LOAD_TODAY_ENTITY = "load_today_entity"
CONF_IMPORT_TODAY_ENTITY = "import_today_entity"
CONF_EXPORT_TODAY_ENTITY = "export_today_entity"

# Load Prediction Calibrations
CONF_LOAD_SENSITIVITY_HIGH_TEMP = "load_high_temp_sensitivity" # kW per deg above threshold
CONF_LOAD_SENSITIVITY_LOW_TEMP = "load_low_temp_sensitivity"   # kW per deg below threshold
CONF_LOAD_HIGH_TEMP_THRESHOLD = "load_high_temp_threshold"    # e.g. 25C
CONF_LOAD_LOW_TEMP_THRESHOLD = "load_low_temp_threshold"      # e.g. 15C

# Calibration
CONF_BATTERY_CAPACITY = "battery_capacity"
CONF_BATTERY_CHARGE_RATE_MAX = "battery_rate_max"
CONF_INVERTER_LIMIT_MAX = "inverter_limit"

# Control (Teslemetry/PW)
CONF_ALLOW_CHARGE_FROM_GRID_ENTITY = "allow_charge_entity"
CONF_ALLOW_EXPORT_ENTITY = "allow_export_entity"

# Default Values
DEFAULT_BATTERY_CAPACITY = 27.0
DEFAULT_BATTERY_RATE_MAX = 6.3
DEFAULT_INVERTER_LIMIT = 10.0
DEFAULT_CURRENCY = "c/kWh"
DEFAULT_SCAN_INTERVAL = 300
# 5 minutes

# States (match System Requirements)
STATE_IDLE = "IDLE"
STATE_CHARGE_GRID = "CHARGE_GRID"
STATE_CHARGE_SOLAR = "CHARGE_SOLAR"
STATE_DISCHARGE_HOME = "DISCHARGE_HOME"
STATE_DISCHARGE_GRID = "DISCHARGE_GRID"
STATE_PRESERVE = "PRESERVE"
STATE_MANUAL_DISCHARGE = "MANUAL_DISCHARGE"

# Attributes
ATTR_STATE_REASON = "reason"
ATTR_PLAN_HTML = "plan_html"
