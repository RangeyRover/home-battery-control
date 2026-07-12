import json

with open(r'API Data\hbc_status_2026-03-08T03-16-57-981Z.json') as f:
    d = json.load(f)

plan = d.get('plan', [])
bug_rows = []
for i, row in enumerate(plan):
    state = row.get('FSM State', '')
    soc = row.get('SoC Forecast', '0%')
    if 'CHARGE_GRID' in state and '100' in soc:
        bug_rows.append(f'  step {i}: {row["Time"]} Local={row["Local Time"]} state={state} SoC={soc} Net={row["Net Grid"]}')

print(f'Total plan rows: {len(plan)}')
print(f'CHARGE_GRID rows close to 100%: {len(bug_rows)}')
for r in bug_rows[:10]:
    print(r)
