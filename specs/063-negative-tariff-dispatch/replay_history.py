"""Offline verification of the user-supplied price history, not measured dispatch."""
import argparse
from bisect import bisect_right
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import time
import types


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    package = types.ModuleType('_history_calculation')
    package.__path__ = [str(root / 'custom_components/house_battery_control')]
    sys.modules[package.__name__] = package
    module = importlib.import_module('_history_calculation.fsm.lin_fsm')
    data = list(csv.DictReader(args.csv.open(encoding='utf-8-sig')))
    entities = ['sensor.4_rosella_general_forecast', 'sensor.4_rosella_feed_in_price']
    series = []
    for entity in entities:
        values = sorted((datetime.fromisoformat(r['last_changed'].replace('Z', '+00:00')),
                         float(r['state'])) for r in data if r['entity_id'] == entity)
        assert values and all(math.isfinite(v) for _, v in values)
        series.append(values)
    starts = [[t for t, _ in values] for values in series]

    def prices(t):
        return [values[bisect_right(stamps, t)-1][1]
                for values, stamps in zip(series, starts)]

    beginning = max(values[0][0] for values in series)
    end = min(values[-1][0] for values in series)
    start = datetime.fromtimestamp(math.ceil(beginning.timestamp()/300)*300, timezone.utc)
    times = [start + timedelta(minutes=5*i)
             for i in range(int((end-start).total_seconds()//300)+1)]
    buy, sell = zip(*(prices(t) for t in times))
    local = timezone(timedelta(hours=10, minutes=30))  # Adelaide on 2026-10-11
    report = {
        'source': str(args.csv.resolve()),
        'sha256': hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        'source_rows': len(data),
        'price_rows': {key: len(values) for key, values in zip(entities, series)},
        'method': 'Backward-as-of prices at 5-minute boundaries; no future interpolation. '
                  'Retrospective price-path replay, not forecasts known at the time. '
                  'Import series is forecast; units retained. Physical inputs synthetic.',
        'sample_start_adelaide': times[0].astimezone(local).isoformat(),
        'sample_end_adelaide': times[-1].astimezone(local).isoformat(),
        'sample_count': len(times),
        'nonpositive_export_samples': sum(v <= 0 for v in sell),
        'negative_import_samples': sum(v < 0 for v in buy),
        'assumptions': {'capacity_kwh': 27, 'charge_kw': 6.3, 'discharge_kw': 10,
                        'one_way_efficiency': .95, 'load_kw': 1.5,
                        'acquisition_cost': -.25, 'export_margin': 0},
        'scenarios': [],
    }

    def verify(rows):
        forbidden = [i for i, r in enumerate(rows) if r['export_price'] <= 0 and
                     (r['state'] == 'DISCHARGE_GRID' or r['battery_export_kwh'] > 1e-6)]
        assert not forbidden, forbidden
        for r in rows:
            assert abs(r['grid_export_kwh']-r['solar_export_kwh']-r['battery_export_kwh']) < 1e-6
            assert abs(r['grid_import_kwh']+r['pv']/12+r['discharge_kwh']
                       -r['load']/12-r['charge_kwh']-r['grid_export_kwh']) < 1e-6
        return forbidden

    for solar in ('none', 'daylight_4.8kw_peak'):
        pv = []
        for t in times:
            lt = t.astimezone(local)
            h = lt.hour + lt.minute/60
            kw = 4.8*math.sin(math.pi*(h-6)/12) if solar != 'none' and 6 < h < 18 else 0
            pv.append(max(0, kw)/12)
        for soc in (.1, .5, 1):
            started = time.monotonic()
            _, cost, rows = module.LinearBatteryController().propose_state_of_charge(
                module.FakeBattery(27, soc, 6.3, 10), list(buy), list(sell),
                [.125]*len(times), pv, acquisition_cost=-.25)
            result = {'solar': solar, 'initial_soc': soc*100,
                      'seconds': round(time.monotonic()-started, 3), 'rows': len(rows),
                      'complete': len(rows) == len(times)}
            if rows:
                result.update(forbidden_battery_exports=len(verify(rows)),
                    nonpositive_solar_export_kwh=sum(r['solar_export_kwh'] for r in rows if r['export_price'] <= 0),
                    negative_price_grid_charge_kwh=sum(r['grid_charge_kwh'] for r in rows if r['import_price'] < 0),
                    positive_price_battery_export_kwh=sum(r['battery_export_kwh'] for r in rows if r['export_price'] > 0),
                    projected_meter_cost=cost)
            report['scenarios'].append(result)
            print(json.dumps(result), flush=True)

    # Cover EVERY observed price-change timestamp, including negative spikes
    # between the five-minute samples. These are independent first-step checks.
    events = sorted({t for values in series for t, _ in values if beginning <= t <= end})
    checked = negative = missing = 0
    for t in events:
        pb, ps = prices(t)
        _, _, rows = module.LinearBatteryController().propose_state_of_charge(
            module.FakeBattery(27, 1, 6.3, 10), [pb], [ps], [.125], [.4], acquisition_cost=-.25)
        if not rows:
            missing += 1
            continue
        verify(rows)
        checked += 1
        negative += ps <= 0
    report['price_change_checks'] = {'events': len(events), 'complete': checked,
                                    'nonpositive_export_events': negative,
                                    'empty_plans': missing, 'forbidden_battery_exports': 0}
    report['pass'] = all(r['complete'] for r in report['scenarios']) and missing == 0
    destination = Path(__file__).with_name('history-replay-results.json')
    destination.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report['price_change_checks']), flush=True)
    print(f"PASS={report['pass']} report={destination}", flush=True)
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
