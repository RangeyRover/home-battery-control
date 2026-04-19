# Quickstart: Frontend Testing

This document describes how to execute the JavaScript testing suite for the Home Battery Control integration's frontend components.

## Prerequisites
- Node.js (v18+)
- npm

## Setup
Since this repository primarily uses Python, you must initialize the local Node modules first.
From the root of the repository, run:
```bash
npm install
```

## Running Tests
To run the full suite of JavaScript tests (which use `@web/test-runner` to test the LitElement web components headlessly), execute:
```bash
npm test
```

## Writing Tests
New frontend tests should be placed in `tests/js/`. They should use `.test.js` extensions and import the components from `custom_components/house_battery_control/frontend/`.

Example:
```javascript
import { fixture, expect } from '@open-wc/testing';
import '../../../custom_components/house_battery_control/frontend/hbc-dashboard.js';

describe('hbc-dashboard', () => {
  it('renders correctly', async () => {
    const el = await fixture('<hbc-dashboard></hbc-dashboard>');
    expect(el).to.be.accessible();
  });
});
```
