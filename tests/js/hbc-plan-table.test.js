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
    expect(rows.length).to.equal(1);
    expect(rows[0].classList.contains('state-charge')).to.be.true;

    const cols = rows[0].querySelectorAll('td');
    expect(cols[5].textContent).to.include('50%');
  });

  it('toggles column visibility and persists to localStorage', async () => {
    const el = await fixture('<hbc-plan-table></hbc-plan-table>');
    el.data = {
      plan: [{ "Time": "10:00" }]
    };
    await el.updateComplete;

    let headers = el.shadowRoot.querySelectorAll('th');
    expect(headers.length).to.equal(16);

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

    expect(el.shadowRoot.querySelectorAll('tbody tr').length).to.equal(1);

    el._switchResolution('5min');
    await el.updateComplete;

    expect(el.shadowRoot.querySelectorAll('tbody tr').length).to.equal(2);
  });

  it('applies semantic val-credit, val-cost, and val-neutral classes in 5min and 30min views', async () => {
    const el = await fixture('<hbc-plan-table></hbc-plan-table>');
    el.data = {
      plan: [
        {
          "Time": "13:25",
          "Local Time": "13:25",
          "FSM State": "CHARGE_GRID",
          "Import Rate": "0.02",
          "Export Rate": "-0.06",
          "Interval Cost": "$0.0070",
          "Cumul. Cost": "$10.0000",
          "Acq. Cost": "0.0800"
        },
        {
          "Time": "19:25",
          "Local Time": "19:25",
          "FSM State": "DISCHARGE_GRID",
          "Import Rate": "-0.05",
          "Export Rate": "0.26",
          "Interval Cost": "$-0.2070",
          "Cumul. Cost": "$9.7930",
          "Acq. Cost": "0.0500"
        },
        {
          "Time": "20:00",
          "Local Time": "20:00",
          "FSM State": "SELF_CONSUMPTION",
          "Import Rate": "0.00",
          "Export Rate": "0.00",
          "Interval Cost": "$0.0000",
          "Cumul. Cost": "$9.7930",
          "Acq. Cost": "0.0500"
        }
      ]
    };
    await el.updateComplete;

    // 30min chunking check (3 chunks because 13:25 and 19:25 end with :25, and 20:00 is last)
    let bodyRows = el.shadowRoot.querySelectorAll('tbody tr');
    expect(bodyRows.length).to.equal(3);
    expect(bodyRows[0].querySelectorAll('td')[3].classList.contains('val-cost')).to.be.true;
    expect(bodyRows[0].querySelectorAll('td')[13].classList.contains('val-cost')).to.be.true;
    expect(bodyRows[1].querySelectorAll('td')[2].classList.contains('val-credit')).to.be.true;
    expect(bodyRows[1].querySelectorAll('td')[3].classList.contains('val-credit')).to.be.true;
    expect(bodyRows[1].querySelectorAll('td')[13].classList.contains('val-credit')).to.be.true;
    expect(bodyRows[2].querySelectorAll('td')[13].classList.contains('val-neutral')).to.be.true;

    // Switch to 5min and verify row classes, header tooltips, and legend
    el._switchResolution('5min');
    await el.updateComplete;

    bodyRows = el.shadowRoot.querySelectorAll('tbody tr');
    // Row 0: positive Import (normal), negative Export (penalty -> val-cost), positive Cost (expense -> val-cost)
    const r0 = bodyRows[0].querySelectorAll('td');
    expect(r0[2].classList.contains('val-cost')).to.be.false;
    expect(r0[2].classList.contains('val-credit')).to.be.false;
    expect(r0[3].classList.contains('val-cost')).to.be.true;
    expect(r0[13].classList.contains('val-cost')).to.be.true;

    // Row 1: negative Import (val-credit), positive Export (val-credit), negative Cost (earning -> val-credit)
    const r1 = bodyRows[1].querySelectorAll('td');
    expect(r1[2].classList.contains('val-credit')).to.be.true;
    expect(r1[3].classList.contains('val-credit')).to.be.true;
    expect(r1[13].classList.contains('val-credit')).to.be.true;

    // Row 2: zero values -> val-neutral
    const r2 = bodyRows[2].querySelectorAll('td');
    expect(r2[2].classList.contains('val-neutral')).to.be.true;
    expect(r2[3].classList.contains('val-neutral')).to.be.true;
    expect(r2[13].classList.contains('val-neutral')).to.be.true;

    // Header tooltips on Import, Export, Cost
    const headers = el.shadowRoot.querySelectorAll('th');
    expect(headers[2].getAttribute('title')).to.be.a('string').and.not.be.empty;
    expect(headers[3].getAttribute('title')).to.be.a('string').and.not.be.empty;
    expect(headers[13].getAttribute('title')).to.be.a('string').and.not.be.empty;

    // Footer legend mentions credit and cost
    expect(el.shadowRoot.textContent.toLowerCase()).to.include('credit');
  });
});
