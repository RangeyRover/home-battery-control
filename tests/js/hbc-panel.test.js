import { fixture, expect } from '@open-wc/testing';
import '../../custom_components/house_battery_control/frontend/hbc-panel.js';

describe('HBCPanel', () => {
  it('renders Tomorrow\'s Outlook tab', async () => {
    const el = await fixture('<hbc-panel></hbc-panel>');
    el.hass = { fetchWithAuth: async () => ({ ok: true, json: async () => ({}) }) };
    el._loading = false;
    el._error = "";
    await el.updateComplete;
    
    // Check for the tab
    const tabs = el.shadowRoot.querySelectorAll('button');
    let found = false;
    tabs.forEach(t => {
      if (t.textContent.includes("Tomorrow's Outlook")) {
        found = true;
      }
    });
    expect(found).to.be.true;
  });

  it('renders the hbc-outlook component when tab is active', async () => {
    const el = await fixture('<hbc-panel></hbc-panel>');
    el.hass = { fetchWithAuth: async () => ({ ok: true, json: async () => ({}) }) };
    el._loading = false;
    el._error = "";
    await el.updateComplete;
    
    // Change active tab
    el._activeTab = 'outlook';
    await el.updateComplete;
    
    const outlook = el.shadowRoot.querySelector('hbc-outlook');
    expect(outlook).to.exist;
  });
});
