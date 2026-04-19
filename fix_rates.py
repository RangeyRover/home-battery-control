import re

with open('custom_components/house_battery_control/rates_predictor.py', 'r') as f:
    code = f.read()

match = re.search(r'    def _run_analog_search\(self, target_kwh: float\) -> list\[AnalogDay\]:\n        \"\"\"Perform SQLite queries to find 5 closest historical days\. \(Blocking\)\"\"\"\n(.*?)        return analog_days', code, re.DOTALL)

if match:
    new_method = '''    def _run_analog_search(self, target_kwh: float) -> list[AnalogDay]:
        """Perform SQLite queries to find 5 closest historical days. (Blocking)"""
        
        debug_state = {
            "target_kwh": target_kwh,
            "status": "running",
            "daily_yields": {},
            "top_5_days": [],
            "error": None
        }
        
        try:
            end_date = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=365)
    
            daily_yields = {}
    
            # 1. Query past 365 days of Solcast predictions using Long Term Statistics
            try:
                lts_stats = statistics_during_period(
                    self._hass,
                    start_date,
                    end_date,
                    [self._solcast_entity_id],
                    "hour",
                    None,
                    {"state", "mean", "max", "sum"}
                )
            except Exception as e:
                _LOGGER.error(f"LTS Solcast query failed: {e}")
                lts_stats = {}
                
            lts_rows = lts_stats.get(self._solcast_entity_id, [])
            for row in lts_rows:
                # For hour statistics, take max forecast for that day
                row_start = dt_util.utc_from_timestamp(row["start"]) if isinstance(row["start"], (int, float)) else row["start"]
                forecast_date = (row_start + timedelta(days=1)).date()
                if forecast_date < end_date.date():
                    val = row.get("max") or row.get("mean") or row.get("state")
                    if val is not None:
                        daily_yields[forecast_date] = max(val, daily_yields.get(forecast_date, 0))
    
            # Fallback to history if LTS is empty (e.g. no state_class)
            if not daily_yields:
                solcast_states_dict = history.get_significant_states(
                    self._hass,
                    start_date,
                    end_date,
                    entity_ids=[self._solcast_entity_id],
                )
                solcast_states = solcast_states_dict.get(self._solcast_entity_id, [])
    
                # Process to daily yield.
                for state in solcast_states:
                    try:
                        val = float(state.state)
                        # Group by the date it was forecasting for (tomorrow relative to last_changed)
                        forecast_date = (state.last_changed + timedelta(days=1)).date()
                        if forecast_date < end_date.date():
                            daily_yields[forecast_date] = val
                    except (ValueError, TypeError):
                        continue
                        
            debug_state["daily_yields"] = {str(k): v for k, v in daily_yields.items()}
    
            if not daily_yields:
                _LOGGER.warning("No historical Solcast data found for analog search.")
                self._dump_debug(debug_state)
                return []
    
            # Find 5 most recent days that are within a 15% (or 2kWh) tolerance
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
                # Fallback to closest 5 regardless of recency if none within tolerance
                sorted_by_error = sorted(daily_yields.items(), key=lambda x: abs(x[1] - target_kwh))
                top_5_days = sorted_by_error[:5]
                
            debug_state["top_5_days"] = [(str(d), y) for d, y in top_5_days]
            debug_state["status"] = "success"
            self._dump_debug(debug_state)
    
            analog_days = []
            for d_date, d_yield in top_5_days:
                day_start = dt_util.now().replace(
                    year=d_date.year, month=d_date.month, day=d_date.day,
                    hour=0, minute=0, second=0, microsecond=0
                )
                day_end = day_start + timedelta(days=1)
    
                entity_ids = []
                if self._import_price_entity_id:
                    entity_ids.append(self._import_price_entity_id)
                if self._export_price_entity_id:
                    entity_ids.append(self._export_price_entity_id)
                if self._load_entity_id:
                    entity_ids.append(self._load_entity_id)
    
                if not entity_ids:
                    continue
    
                day_states_dict = history.get_significant_states(
                    self._hass,
                    day_start,
                    day_end,
                    entity_ids=entity_ids,
                )
    
                # Process Import Price
                import_curve = [0.0] * 288
                if self._import_price_entity_id:
                    states = day_states_dict.get(self._import_price_entity_id, [])
                    if states:
                        import_curve = self._normalize_to_288(states, day_start)
                    else:
                        import_curve = self._get_lts_curve(self._import_price_entity_id, day_start, day_end)
    
                # Process Export Price
                export_curve = [0.0] * 288
                if self._export_price_entity_id:
                    states = day_states_dict.get(self._export_price_entity_id, [])
                    if states:
                        export_curve = self._normalize_to_288(states, day_start)
                    else:
                        export_curve = self._get_lts_curve(self._export_price_entity_id, day_start, day_end)
    
                # Process Load Profile
                load_curve = [0.0] * 288
                if self._load_entity_id:
                    states = day_states_dict.get(self._load_entity_id, [])
                    if states:
                        load_curve = self._normalize_to_288(states, day_start)
                    else:
                        load_curve = self._get_lts_curve(self._load_entity_id, day_start, day_end)
    
                analog_days.append(
                    AnalogDay(
                        date=day_start,
                        pv_yield=d_yield,
                        pricing_curve=import_curve,
                        export_curve=export_curve,
                        load_curve=load_curve,
                    )
                )
    
            return analog_days
            
        except Exception as e:
            import traceback
            debug_state["status"] = "crashed"
            debug_state["error"] = str(e)
            debug_state["traceback"] = traceback.format_exc()
            self._dump_debug(debug_state)
            _LOGGER.error(f"Analog search crashed: {e}")
            return []
'''
    new_code = code[:match.start()] + new_method + code[match.end():]
    with open('custom_components/house_battery_control/rates_predictor.py', 'w') as f:
        f.write(new_code)
    print("Success!")
else:
    print("Match not found!")
