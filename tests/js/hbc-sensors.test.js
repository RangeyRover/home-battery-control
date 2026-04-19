import { fixture, expect, nextFrame } from '@open-wc/testing';
import '../../custom_components/house_battery_control/frontend/hbc-sensors.js';

describe('HBCSensors', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders nothing if data is empty', async () => {
    const el = await fixture('<hbc-sensors></hbc-sensors>');
    expect(el.shadowRoot.querySelector('.card')).to.be.null;
  });

  it('renders the sensor table', async () => {
    const el = await fixture('<hbc-sensors></hbc-sensors>');
    el.data = {
      sensors: [
        { entity_id: 'sensor.test1', state: '100', available: true },
        { entity_id: 'sensor.test2', state: 'unavailable', available: false }
      ]
    };
    await el.updateComplete;

    const rows = el.shadowRoot.querySelectorAll('tbody tr');
    expect(rows.length).to.equal(2);
    
    // Check first row
    const cols1 = rows[0].querySelectorAll('td');
    expect(cols1[0].textContent).to.include('sensor.test1');
    expect(cols1[2].querySelector('.badge').classList.contains('ok')).to.be.true;

    // Check second row
    const cols2 = rows[1].querySelectorAll('td');
    expect(cols2[0].textContent).to.include('sensor.test2');
    expect(cols2[2].querySelector('.badge').classList.contains('err')).to.be.true;
  });

  it('toggles visibility and saves to localStorage', async () => {
    const el = await fixture('<hbc-sensors></hbc-sensors>');
    el.data = {
      sensors: [{ entity_id: 'sensor.test', state: 'ok', available: true }]
    };
    await el.updateComplete;

    // Initially table is shown
    expect(el.shadowRoot.querySelector('table')).to.exist;
    expect(localStorage.getItem('hbc_sensors_hidden')).to.be.null;

    // Click to hide
    const header = el.shadowRoot.querySelector('h2');
    header.click();
    await el.updateComplete;

    expect(el.shadowRoot.querySelector('table')).to.be.null;
    expect(localStorage.getItem('hbc_sensors_hidden')).to.equal('true');

    // Click to show again
    header.click();
    await el.updateComplete;

    expect(el.shadowRoot.querySelector('table')).to.exist;
    expect(localStorage.getItem('hbc_sensors_hidden')).to.equal('false');
  });

  it('initializes hidden state from localStorage', async () => {
    localStorage.setItem('hbc_sensors_hidden', 'true');
    const el = await fixture('<hbc-sensors></hbc-sensors>');
    el.data = {
      sensors: [{ entity_id: 'sensor.test', state: 'ok', available: true }]
    };
    await el.updateComplete;

    expect(el.shadowRoot.querySelector('table')).to.be.null;
  });
});
