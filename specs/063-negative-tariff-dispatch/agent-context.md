# Feature 063 handoff

Implemented in place in lin_fsm.py under user-approved calculation-only scope. No split, import switch, HA integration work or Powerwall control changes. Canonical tasks.md is complete for that scope; validation.md records RED/GREEN and benchmarks. User explicitly requires SDD/TDD. Paid charging may increase later negative-price solar export only when the complete forecast comparison improves; direct nonpositive-price battery export is prohibited. Price units and forecast provenance remain the caller's contract. Future work must preserve these decisions.
