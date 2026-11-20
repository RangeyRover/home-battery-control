"""Upstream spike credibility pre-treatment state machine (Feature 066).

Classifies every 5-minute forecast interval into one of three regimes BEFORE
both ``RenewablesGuard`` and ``LinearBatteryStateMachine`` see the timeline:

1. ``NEAR_REALTIME`` (``lead_mins <= 30.0`` OR ``renewables is None`` OR ``synthetic``):
   Inside AEMO's physical 5-minute dispatch / P5MIN horizon — pass 100% uncapped.
2. ``MIRAGE_CLAMPED`` (``lead_mins > 30.0`` AND ``renewables > spike_renewables_threshold``):
   High-renewables AEMO P30 mirage — clamp import/export to normal peak caps
   and clear ``spike = False`` while preserving ``raw_*`` diagnostics.
3. ``CREDIBLE_SCARCITY`` (``lead_mins > 30.0`` AND ``renewables <= spike_renewables_threshold``):
   Genuine low-renewables thermal/gas scarcity window — apply horizon-stepped
   expected-value weights (0.70x <= 6h, 0.40x > 6h) up to saturation caps and
   retain ``spike`` unchanged so ``RenewablesGuard`` can pre-charge to 100% SoC.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .const import (
    CONF_MIRAGE_EXPORT_CAP,
    CONF_MIRAGE_IMPORT_CAP,
    CONF_SPIKE_RENEWABLES_THRESHOLD,
    DEFAULT_MIRAGE_EXPORT_CAP,
    DEFAULT_MIRAGE_IMPORT_CAP,
    DEFAULT_SCARCITY_EXPORT_CAP,
    DEFAULT_SCARCITY_HORIZON_SHORT_MINS,
    DEFAULT_SCARCITY_IMPORT_CAP,
    DEFAULT_SCARCITY_LONG_WEIGHT,
    DEFAULT_SCARCITY_SHORT_WEIGHT,
    DEFAULT_SPIKE_NEAR_HORIZON_MINS,
    DEFAULT_SPIKE_RENEWABLES_THRESHOLD,
    SPIKE_REGIME_CREDIBLE_SCARCITY,
    SPIKE_REGIME_MIRAGE_CLAMPED,
    SPIKE_REGIME_NEAR_REALTIME,
)


def _resolve_reference_time(
    rates: list[dict[str, Any]],
    now: datetime | None,
) -> datetime | None:
    """Resolve the t=0 reference timestamp for lead-time calculation.

    In live Home Assistant operation ``now`` falls inside the active forecast
    window and is used directly. In offline replays or unit tests with fixed
    historical dates, ``now`` may be ``None`` or outside the timeline window,
    in which case we anchor cleanly on ``rates[0]["start"]``.
    """
    starts = [r["start"] for r in rates if isinstance(r.get("start"), datetime)]
    if not starts:
        return now

    first_start = rates[0]["start"] if isinstance(rates[0].get("start"), datetime) else min(starts)
    if now is None:
        return first_start

    ends = [
        r.get("end") if isinstance(r.get("end"), datetime) else r["start"]
        for r in rates
        if isinstance(r.get("start"), datetime)
    ]
    min_start = min(starts)
    max_end = max(ends)

    try:
        if (min_start - timedelta(hours=1)) <= now <= (max_end + timedelta(hours=1)):
            return now
    except TypeError:
        return first_start

    return first_start


def pretreat_rates_timeline(
    rates: list[dict[str, Any]],
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Pre-treat a 5-minute rate timeline using the 2-rule / 3-regime state machine."""
    if not rates:
        return []

    cfg = config or {}
    ren_threshold = float(
        cfg.get(CONF_SPIKE_RENEWABLES_THRESHOLD, DEFAULT_SPIKE_RENEWABLES_THRESHOLD)
    )
    mirage_imp_cap = float(
        cfg.get(CONF_MIRAGE_IMPORT_CAP, DEFAULT_MIRAGE_IMPORT_CAP)
    )
    mirage_exp_cap = float(
        cfg.get(CONF_MIRAGE_EXPORT_CAP, DEFAULT_MIRAGE_EXPORT_CAP)
    )

    ref_time = _resolve_reference_time(rates, now)
    treated: list[dict[str, Any]] = []

    for item in rates:
        row = dict(item)
        raw_imp = float(row.get("import_price", 0.0))
        raw_exp = float(row.get("export_price", 0.0))
        raw_spike = bool(row.get("spike", False))

        row["raw_import_price"] = raw_imp
        row["raw_export_price"] = raw_exp
        row["raw_spike"] = raw_spike

        start_ts = row.get("start")
        if isinstance(start_ts, datetime) and isinstance(ref_time, datetime):
            try:
                lead_mins = (start_ts - ref_time).total_seconds() / 60.0
            except TypeError:
                lead_mins = 0.0
        else:
            lead_mins = 0.0

        ren = row.get("renewables")
        is_synthetic = bool(row.get("synthetic", False))

        if (
            lead_mins <= DEFAULT_SPIKE_NEAR_HORIZON_MINS
            or ren is None
            or is_synthetic
        ):
            row["spike_regime"] = SPIKE_REGIME_NEAR_REALTIME
        elif float(ren) > ren_threshold:
            row["spike_regime"] = SPIKE_REGIME_MIRAGE_CLAMPED
            row["import_price"] = min(raw_imp, mirage_imp_cap)
            row["export_price"] = min(raw_exp, mirage_exp_cap)
            row["spike"] = False
        else:
            row["spike_regime"] = SPIKE_REGIME_CREDIBLE_SCARCITY
            weight = (
                DEFAULT_SCARCITY_SHORT_WEIGHT
                if lead_mins <= DEFAULT_SCARCITY_HORIZON_SHORT_MINS
                else DEFAULT_SCARCITY_LONG_WEIGHT
            )
            scarcity_imp_cap = max(DEFAULT_SCARCITY_IMPORT_CAP, mirage_imp_cap)
            scarcity_exp_cap = max(DEFAULT_SCARCITY_EXPORT_CAP, mirage_exp_cap)
            if raw_imp > mirage_imp_cap:
                row["import_price"] = min(
                    mirage_imp_cap + weight * (raw_imp - mirage_imp_cap),
                    scarcity_imp_cap,
                )
            if raw_exp > mirage_exp_cap:
                row["export_price"] = min(
                    mirage_exp_cap + weight * (raw_exp - mirage_exp_cap),
                    scarcity_exp_cap,
                )
            row["spike"] = raw_spike

        treated.append(row)

    return treated
