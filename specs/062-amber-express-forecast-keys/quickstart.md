# Quickstart / Manual Verification: Amber Express Forecast Attributes

## Verification Commands

Run unit tests to verify Amber Express entity attribute parsing resilience:

```bash
pytest tests/test_rates.py -k "amber_express" -v
```

All Amber Express parsing tests should pass.
