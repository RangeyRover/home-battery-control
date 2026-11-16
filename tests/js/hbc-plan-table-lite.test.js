import { fixture, expect } from '@open-wc/testing';
import '../../custom_components/house_battery_control/frontend/hbc-plan-table-lite.js';

describe('HBCPlanTableLite', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('applies semantic val-credit, val-cost, and val-neutral classes on Cost, Export, and Import columns', async () => {
    const columns = [
      "Time", "Local Time", "Import Rate", "Export Rate", "FSM State",
      "Inverter Limit", "Net Grid", "PV Forecast", "Load Forecast",
      "Air Temp Forecast", "Temp Delta", "Load Adj.", "SoC Forecast",
      "Interval Cost", "Cumul. Cost", "Acq. Cost", "Synthetic"
    ];
    const rows = [
      ["13:30", "13:30", "0.02", "-0.06", "CHARGE_GRID", "100%", "3.65", "4.27", "1.62", "19.0°C", "0.3°C", "0.00", "57.7%", "$0.0070", "$1052.0000", "0.0790", false],
      ["19:00", "19:00", "-0.04", "0.26", "DISCHARGE_GRID", "100%", "-9.42", "0.13", "0.71", "16.0°C", "-2.0°C", "0.00", "96.1%", "$-0.2070", "$1051.7930", "0.0490", false],
      ["18:00", "18:00", "0.00", "0.00", "SELF_CONSUMPTION", "0%", "0.00", "1.08", "1.10", "19.0°C", "0.3°C", "0.00", "100.0%", "$0.0000", "$1052.0000", "0.0490", false]
    ];

    const el = await fixture('<hbc-plan-table-lite></hbc-plan-table-lite>');
    el.hass = {
      fetchWithAuth: async () => ({
        ok: true,
        json: async () => ({ columns, rows })
      })
    };
    await el._fetchPlan();
    await el.updateComplete;

    const bodyRows = el.shadowRoot.querySelectorAll('tbody tr');
    expect(bodyRows.length).to.equal(3);

    // Row 0: positive Import (default), negative Export (val-cost), positive Cost (val-cost)
    const r0 = bodyRows[0].querySelectorAll('td');
    expect(r0[2].classList.contains('val-cost')).to.be.false;
    expect(r0[2].classList.contains('val-credit')).to.be.false;
    expect(r0[3].classList.contains('val-cost')).to.be.true;
    expect(r0[13].classList.contains('val-cost')).to.be.true;

    // Row 1: negative Import (val-credit), positive Export (val-credit), negative Cost (val-credit)
    const r1 = bodyRows[1].querySelectorAll('td');
    expect(r1[2].classList.contains('val-credit')).to.be.true;
    expect(r1[3].classList.contains('val-credit')).to.be.true;
    expect(r1[13].classList.contains('val-credit')).to.be.true;
    expect(r1[13].textContent).to.equal('-$0.20.7');

    // Row 2: zero values -> val-neutral
    const r2 = bodyRows[2].querySelectorAll('td');
    expect(r2[2].classList.contains('val-neutral')).to.be.true;
    expect(r2[3].classList.contains('val-neutral')).to.be.true;
    expect(r2[13].classList.contains('val-neutral')).to.be.true;

    // Header tooltips & legend
    const headers = el.shadowRoot.querySelectorAll('th');
    expect(headers[2].getAttribute('title')).to.be.a('string').and.not.be.empty;
    expect(headers[3].getAttribute('title')).to.be.a('string').and.not.be.empty;
    expect(headers[13].getAttribute('title')).to.be.a('string').and.not.be.empty;
    expect(el.shadowRoot.textContent.toLowerCase()).to.include('credit');
  });
});
