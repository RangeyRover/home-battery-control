import re

file_path = r"C:\Users\markn\OneDrive - IXL Signalling\0-01 AI Programming\AI Coding\House Battery Control\custom_components\house_battery_control\rates_predictor.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update _get_lts_curve
old_lts_curve = """    def _get_lts_curve(self, entity_id: str, day_start: datetime, day_end: datetime) -> list[float]:
        try:
            stats = statistics_during_period(
                self._hass,
                day_start,
                day_end,
                [entity_id],
                "5minute",
                None,
                {"state", "mean", "sum", "max"}
            )
        except Exception as e:
            _LOGGER.error(f"LTS curve query failed for {entity_id}: {e}")
            stats = {}
            
        rows = stats.get(entity_id, [])
        curve = [0.0] * 288
        for row in rows:
            row_start = dt_util.utc_from_timestamp(row["start"]) if isinstance(row["start"], (int, float)) else row["start"]
            if row_start >= day_start and row_start < day_end:
                step = int((row_start - day_start).total_seconds() / 300)
                if 0 <= step < 288:
                    val = row.get("mean")
                    if val is None:
                        val = row.get("state")
                    if val is not None:
                        curve[step] = float(val)

        # Forward-fill any empty gaps in the curve
        current_val = 0.0
        for i in range(288):
            if curve[i] != 0.0:
                current_val = curve[i]
            else:
                curve[i] = current_val

        return curve"""

new_lts_curve = """    def _get_lts_curve(self, entity_id: str, day_start: datetime, day_end: datetime) -> list[float]:
        try:
            stats = statistics_during_period(
                self._hass,
                day_start,
                day_end,
                [entity_id],
                "hour",
                None,
                {"state", "mean", "sum", "max"}
            )
        except Exception as e:
            _LOGGER.error(f"LTS curve query failed for {entity_id}: {e}")
            stats = {}
            
        rows = stats.get(entity_id, [])
        curve = [0.0] * 288
        for row in rows:
            row_start = dt_util.utc_from_timestamp(row["start"]) if isinstance(row["start"], (int, float)) else row["start"]
            if row_start >= day_start and row_start < day_end:
                hour_idx = int((row_start - day_start).total_seconds() / 3600)
                if 0 <= hour_idx < 24:
                    val = row.get("mean")
                    if val is None:
                        val = row.get("state")
                    if val is None:
                        val = row.get("max")
                    
                    if val is not None:
                        for m in range(12):
                            idx = hour_idx * 12 + m
                            if idx < 288:
                                curve[idx] = float(val)

        # Forward-fill any empty gaps in the curve
        current_val = 0.0
        for i in range(288):
            if curve[i] != 0.0:
                current_val = curve[i]
            else:
                curve[i] = current_val

        return curve"""

content = content.replace(old_lts_curve, new_lts_curve)

# 2. Update tolerance and analog day selection
old_analog = """            # Find 5 most recent days that are within a 15% (or 2kWh) tolerance
            tolerance = max(2.0, target_kwh * 0.15)
            candidate_days = [
                (d_date, d_yield) for d_date, d_yield in daily_yields.items()
                if abs(d_yield - target_kwh) <= tolerance
            ]
            
            if candidate_days:
                # Sort the candidates by date descending (most recent first)
                candidate_days.sort(key=lambda x: x[0], reverse=True)
                top_5_days = candidate_days[:5]
            else:
                # Fallback: Just get the 5 days with the lowest absolute error
                sorted_by_error = sorted(daily_yields.items(), key=lambda x: abs(x[1] - target_kwh))
                top_5_days = sorted_by_error[:5]"""

new_analog = """            # Find 5 most recent days that are within a strict 5% tolerance
            tolerance = target_kwh * 0.05
            candidate_days = [
                (d_date, d_yield) for d_date, d_yield in daily_yields.items()
                if abs(d_yield - target_kwh) <= tolerance
            ]
            
            if candidate_days:
                # Sort the candidates by date descending (most recent first)
                candidate_days.sort(key=lambda x: x[0], reverse=True)
                top_5_days = candidate_days[:5]
            else:
                # Fallback: Just get the 5 days with the lowest absolute error
                sorted_by_error = sorted(daily_yields.items(), key=lambda x: abs(x[1] - target_kwh))
                top_5_days = sorted_by_error[:5]"""

content = content.replace(old_analog, new_analog)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced content successfully!")
