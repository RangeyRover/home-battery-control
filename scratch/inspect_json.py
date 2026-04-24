import json
import sys

with open(r'JSON\hbc_snapshot_2026-04-24T05-39-53-102Z.json', encoding='utf-8') as f:
    d = json.load(f)

# Find the plan elements after 14:00 tomorrow (where synthetic should be active)
plan = d.get("plan", [])
print(f"Total plan rows: {len(plan)}")

for row in plan:
    if "04-25" in row["Time"] and row["Local Time"] >= "14:30":
        print(f"Plan @ {row['Local Time']}: Imp: {row['Import Rate']}, Exp: {row['Export Rate']}, Load: {row['Load Forecast']}, PV: {row['PV Forecast']}")

print("---")
# Also let's find what the synthetic arrays have at 15:00
# 15:00 is index 15 * 12 = 180
idx = 180
print(f"Synthetic @ 15:00 (idx {idx}):")
print(f"  Import: {d['synthetic_pricing_curve'][idx]}")
print(f"  Export: {d['synthetic_export_curve'][idx]}")
print(f"  Load:   {d['synthetic_load_curve'][idx]}")

# 15:30 is idx 186
idx = 186
print(f"Synthetic @ 15:30 (idx {idx}):")
print(f"  Import: {d['synthetic_pricing_curve'][idx]}")
print(f"  Export: {d['synthetic_export_curve'][idx]}")
print(f"  Load:   {d['synthetic_load_curve'][idx]}")

