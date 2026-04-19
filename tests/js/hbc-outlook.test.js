import { fixture, expect } from '@open-wc/testing';
import '../../custom_components/house_battery_control/frontend/hbc-outlook.js';

describe('HBCOutlook', () => {
  it('renders correctly with empty data', async () => {
    const el = await fixture('<hbc-outlook></hbc-outlook>');
    expect(el).shadowDom.to.be.accessible();
    
    // Should display a message or be empty, but not crash
    const text = el.shadowRoot.textContent;
    expect(text).to.include("Waiting for synthetic outlook data");
  });

  it('displays the 5 analog days in a details block', async () => {
    const el = await fixture('<hbc-outlook></hbc-outlook>');
    el.state = {
      synthetic_analog_days: ["2026-04-12", "2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16"],
      synthetic_pricing_curve: new Array(288).fill(0.1),
      synthetic_export_curve: new Array(288).fill(0.05),
      synthetic_load_curve: new Array(288).fill(1.5),
    };
    await el.updateComplete;
    
    const details = el.shadowRoot.querySelector('details.analog-days');
    expect(details).to.exist;
    
    const text = details.textContent;
    expect(text).to.include('2026-04-12');
    expect(text).to.include('2026-04-16');
  });

  it('renders SVG graphs for the curves', async () => {
    const el = await fixture('<hbc-outlook></hbc-outlook>');
    el.state = {
      synthetic_analog_days: ["2026-04-12"],
      synthetic_pricing_curve: new Array(288).fill(0.1),
      synthetic_export_curve: new Array(288).fill(0.05),
      synthetic_load_curve: new Array(288).fill(1.5),
    };
    await el.updateComplete;
    
    const details = el.shadowRoot.querySelector('details.outlook-graphs');
    expect(details).to.exist;
    
    const svg = details.querySelector('svg');
    expect(svg).to.exist;
    
    // Expect polyline elements for the 3 curves
    const polylines = svg.querySelectorAll('polyline');
    expect(polylines.length).to.equal(3);
  });
});
