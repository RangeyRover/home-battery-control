import { fixture, expect } from '@open-wc/testing';
import '../../custom_components/house_battery_control/frontend/hbc-dashboard.js';

describe('HBCDashboard', () => {
  it('renders correctly with empty data', async () => {
    const el = await fixture('<hbc-dashboard></hbc-dashboard>');
    expect(el).shadowDom.to.be.accessible();
    
    // Default flow values
    const flowValues = el.shadowRoot.querySelectorAll('.flow-value');
    expect(flowValues.length).to.equal(5);
    expect(flowValues[0].textContent).to.equal('0'); // Solar
    expect(flowValues[1].textContent).to.equal('0'); // Grid
    expect(flowValues[2].textContent).to.equal('0'); // Battery
    expect(flowValues[3].textContent).to.equal('0'); // House
    expect(flowValues[4].textContent).to.equal('0%'); // SoC
  });

  it('calculates summary stats correctly', async () => {
    const el = await fixture('<hbc-dashboard></hbc-dashboard>');
    el.data = {
      plan: [
        { "Import Rate": "10.0", "Export Rate": "5.0", "PV Forecast": "6.0", "Load Forecast": "2.0" },
        { "Import Rate": "20.0", "Export Rate": "5.0", "PV Forecast": "0.0", "Load Forecast": "4.0" }
      ]
    };
    await el.updateComplete;

    const stats = el._calculateSummaryStats();
    expect(stats.avgImport).to.equal('15.00'); // (10+20)/2
    expect(stats.avgExport).to.equal('5.00');  // (5+5)/2
    expect(stats.totalPV).to.equal('0.5');     // (6+0)/12
    expect(stats.totalLoad).to.equal('0.5');   // (2+4)/12
  });

  it('conditionally renders constraints bar', async () => {
    const el = await fixture('<hbc-dashboard></hbc-dashboard>');
    el.data = {
      no_import_periods: "10:00-11:00",
      observation_mode: true
    };
    await el.updateComplete;

    const bar = el.shadowRoot.querySelector('.constraints-bar');
    expect(bar).to.exist;
    expect(bar.querySelector('.no-import').textContent).to.include('10:00-11:00');
    expect(bar.querySelector('.observation')).to.exist;
  });
});
