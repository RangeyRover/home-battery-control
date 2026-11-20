"""Unit tests for upstream spike credibility pre-treatment state machine (Feature 066)."""

from datetime import datetime, timedelta, timezone

import pytest
from custom_components.house_battery_control.const import (
    CONF_MIRAGE_EXPORT_CAP,
    CONF_MIRAGE_IMPORT_CAP,
    CONF_SPIKE_RENEWABLES_THRESHOLD,
    SPIKE_REGIME_CREDIBLE_SCARCITY,
    SPIKE_REGIME_MIRAGE_CLAMPED,
    SPIKE_REGIME_NEAR_REALTIME,
)
from custom_components.house_battery_control.spike_credibility import (
    pretreat_rates_timeline,
)


def _slot(base: datetime, step: int, imp: float, exp: float, ren: float | None, spike: bool = False, **extra):
    d = {
        "start": base + timedelta(minutes=5 * step),
        "end": base + timedelta(minutes=5 * (step + 1)),
        "import_price": imp,
        "export_price": exp,
        "renewables": ren,
        "spike": spike,
        "type": "FORECAST",
    }
    d.update(extra)
    return d


def test_mirage_clamped_beyond_30m_when_renewables_high():
    """Rule 1: >30m ahead with renewables > 25% clamps import<=$0.60, export<=$0.35, and clears spike."""
    base = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
    # step 24 = +120 mins (>30m), Nov 11 smoking gun: $12.17 imp / $4.10 exp @ 68% renewables
    rates = [_slot(base, 0, 0.08, -0.02, 85.0), _slot(base, 24, 12.17, 4.10, 68.0, spike=True)]

    out = pretreat_rates_timeline(rates, now=base)

    mirage = out[1]
    assert mirage["spike_regime"] == SPIKE_REGIME_MIRAGE_CLAMPED
    assert mirage["import_price"] == pytest.approx(0.60)
    assert mirage["export_price"] == pytest.approx(0.35)
    assert mirage["spike"] is False
    assert mirage["raw_import_price"] == pytest.approx(12.17)
    assert mirage["raw_export_price"] == pytest.approx(4.10)
    assert mirage["raw_spike"] is True


def test_near_realtime_within_30m_uncapped_even_with_high_renewables():
    """Rule 2a: <=30m ahead (AEMO P5MIN window) passes 100% uncapped prices regardless of renewables."""
    base = datetime(2026, 11, 12, 4, 0, tzinfo=timezone.utc)
    # step 0 = 0m, step 6 = +30.0m boundary -> both <= 30m
    rates = [
        _slot(base, 0, 3.94, 3.50, 97.6, spike=True),
        _slot(base, 6, 2.50, 2.10, 90.0, spike=True),
    ]

    out = pretreat_rates_timeline(rates, now=base)

    assert out[0]["spike_regime"] == SPIKE_REGIME_NEAR_REALTIME
    assert out[0]["import_price"] == pytest.approx(3.94)
    assert out[0]["export_price"] == pytest.approx(3.50)
    assert out[0]["spike"] is True

    assert out[1]["spike_regime"] == SPIKE_REGIME_NEAR_REALTIME
    assert out[1]["import_price"] == pytest.approx(2.50)
    assert out[1]["export_price"] == pytest.approx(2.10)
    assert out[1]["spike"] is True


def test_credible_scarcity_low_renewables_short_and_long_horizon_weights():
    """Rule 2b: >30m ahead with renewables <= 25% applies 0.70x (<=6h) and 0.40x (>6h) weights up to saturation caps."""
    base = datetime(2026, 6, 21, 2, 0, tzinfo=timezone.utc)
    rates = [
        _slot(base, 0, 0.20, 0.05, 40.0),
        _slot(base, 36, 1.60, 1.35, 12.0, spike=True),   # +180m (<=6h): 0.70x excess
        _slot(base, 96, 1.60, 1.35, 10.0, spike=True),   # +480m (>6h):  0.40x excess
        _slot(base, 48, 24.36, 21.92, 2.6, spike=True),  # +240m extreme cap saturation
    ]

    out = pretreat_rates_timeline(rates, now=base)

    # +180m: imp = 0.60 + 0.70*(1.60-0.60) = 1.30; exp = 0.35 + 0.70*(1.35-0.35) = 1.05
    assert out[1]["spike_regime"] == SPIKE_REGIME_CREDIBLE_SCARCITY
    assert out[1]["import_price"] == pytest.approx(1.30)
    assert out[1]["export_price"] == pytest.approx(1.05)
    assert out[1]["spike"] is True

    # +480m: imp = 0.60 + 0.40*(1.60-0.60) = 1.00; exp = 0.35 + 0.40*(1.35-0.35) = 0.75
    assert out[2]["spike_regime"] == SPIKE_REGIME_CREDIBLE_SCARCITY
    assert out[2]["import_price"] == pytest.approx(1.00)
    assert out[2]["export_price"] == pytest.approx(0.75)
    assert out[2]["spike"] is True

    # Saturation caps: $1.50 import, $1.20 export
    assert out[3]["import_price"] == pytest.approx(1.50)
    assert out[3]["export_price"] == pytest.approx(1.20)


def test_negative_and_normal_tariffs_pass_through_unchanged():
    """Negative solar-sponge tariffs and normal TOU prices below caps are never altered."""
    base = datetime(2026, 11, 16, 3, 0, tzinfo=timezone.utc)
    rates = [
        _slot(base, 0, 0.02, -0.06, 95.0),
        _slot(base, 20, -0.05, -0.09, 110.0),
        _slot(base, 40, 0.58, 0.26, 45.0),
    ]

    out = pretreat_rates_timeline(rates, now=base)

    assert out[1]["import_price"] == pytest.approx(-0.05)
    assert out[1]["export_price"] == pytest.approx(-0.09)
    assert out[2]["import_price"] == pytest.approx(0.58)
    assert out[2]["export_price"] == pytest.approx(0.26)


def test_none_renewables_and_custom_caps():
    """Intervals with renewables=None pass through untouched; custom config caps override defaults."""
    base = datetime(2026, 11, 16, 3, 0, tzinfo=timezone.utc)
    rates = [
        _slot(base, 0, 0.20, 0.05, None),
        _slot(base, 20, 2.00, 1.50, None, spike=True),
        _slot(base, 24, 1.50, 1.20, 28.0, spike=True),
    ]
    cfg = {
        CONF_SPIKE_RENEWABLES_THRESHOLD: 30.0,
        CONF_MIRAGE_IMPORT_CAP: 0.50,
        CONF_MIRAGE_EXPORT_CAP: 0.30,
    }

    out = pretreat_rates_timeline(rates, now=base, config=cfg)

    # renewables=None -> untouched
    assert out[1]["spike_regime"] == SPIKE_REGIME_NEAR_REALTIME
    assert out[1]["import_price"] == pytest.approx(2.00)
    assert out[1]["export_price"] == pytest.approx(1.50)

    # 28.0 <= custom 30.0 -> CREDIBLE_SCARCITY with custom base caps 0.50 / 0.30
    assert out[2]["spike_regime"] == SPIKE_REGIME_CREDIBLE_SCARCITY
    assert out[2]["import_price"] == pytest.approx(0.50 + 0.70 * (1.50 - 0.50))
    assert out[2]["export_price"] == pytest.approx(0.30 + 0.70 * (1.20 - 0.30))
