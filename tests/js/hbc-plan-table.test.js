import { fixture, expect } from '@open-wc/testing';
import '../../custom_components/house_battery_control/frontend/hbc-plan-table.js';

describe('HBCPlanTable', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders a message if no plan data is available', async () => {
    const el = await fixture('<hbc-plan-table></hbc-plan-table>');
    expect(el.shadowRoot.textContent).to.include('No plan data available yet');
  });

  it('renders the plan table with 30min chunking by default', async () => {
    const el = await fixture('<hbc-plan-table></hbc-plan-table>');
    el.data = {
      plan: [
        { "Time": "10:00", "FSM State": "SELF_CONSUMPTION", "Import Rate": "10", "Export Rate": "5", "Net Grid": "1", "PV Forecast": "2", "Load Forecast": "3", "Air Temp Forecast": "20", "Interval Cost": "1", "Acq. Cost": "0", "Cumul. Cost": "1" },
        { "Time": "10:05", "FSM State": "CHARGE_GRID", "Inverter Limit": "50%", "Import Rate": "10", "Export Rate": "5", "Net Grid": "1", "PV Forecast": "2", "Load Forecast": "3", "Air Temp Forecast": "20", "Interval Cost": "1", "Acq. Cost": "0", "Cumul. Cost": "2" }
      ]
    };
    await el.updateComplete;

    const rows = el.shadowRoot.querySelectorAll('tbody tr');
    // The two elements don't hit the 25/55 boundary or end until the end of the array.
    // Actually, the chunking groups them. Length = 1 chunk.
    expect(rows.length).to.equal(1);
    
    // The chunk should inherit the CHARGE_GRID boundary state and limit
    expect(rows[0].classList.contains('state-charge')).to.be.true;
    
    // Check limit column (index 5)
    const cols = rows[0].querySelectorAll('td');
    expect(cols[5].textContent).to.include('50%');
  });

  it('toggles column visibility and persists to localStorage', async () => {
    const el = await fixture('<hbc-plan-table></hbc-plan-table>');
    el.data = {
      plan: [{ "Time": "10:00" }]
    };
    await el.updateComplete;

    // By default, 16 columns
    let headers = el.shadowRoot.querySelectorAll('th');
    expect(headers.length).to.equal(16);

    // Toggle "State" column
    el._toggleCol('State');
    await el.updateComplete;

    headers = el.shadowRoot.querySelectorAll('th');
    expect(headers.length).to.equal(15);
    
    const saved = JSON.parse(localStorage.getItem('hbc_hidden_cols'));
    expect(saved).to.deep.equal(['State']);
  });

  it('toggles resolution to 5min', async () => {
    const el = await fixture('<hbc-plan-table></hbc-plan-table>');
    el.data = {
      plan: [
        { "Time": "10:00" },
        { "Time": "10:05" }
      ]
    };
    await el.updateComplete;

    // Default 30min -> 1 row
    expect(el.shadowRoot.querySelectorAll('tbody tr').length).to.equal(1);

    // Switch to 5min
    el._switchResolution('5min');
    await el.updateComplete;

    // 5min -> 2 rows
    expect(el.shadowRoot.querySelectorAll('tbody tr').length).to.equal(2);
  });
});
