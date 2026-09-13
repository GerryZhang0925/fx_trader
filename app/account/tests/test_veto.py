from __future__ import annotations

from datetime import datetime, timezone

from account.veto import (
    VetoConfig,
    VetoDedup,
    book_near_halt,
    evaluate,
    in_london_ny_overlap_at,
)


UTC = timezone.utc


def test_overlap_is_dst_not_fixed_utc():
    winter = datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
    winter_too_early = datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
    summer_after_london = datetime(2024, 7, 15, 15, 30, tzinfo=UTC)
    assert in_london_ny_overlap_at(winter)
    assert not in_london_ny_overlap_at(winter_too_early)
    assert not in_london_ny_overlap_at(summer_after_london)


def test_nfp_first_friday_0830_new_york():
    # 2026-10-02 is the first Friday. 08:30 America/New_York = 12:30 UTC (EDT).
    hit = evaluate(datetime(2026, 10, 2, 12, 30, tzinfo=UTC))
    miss = evaluate(datetime(2026, 10, 2, 15, 0, tzinfo=UTC))
    assert hit.notify and "nfp" in hit.codes
    assert "nfp" not in miss.codes


def test_fomc_third_wednesday_1400_new_york():
    # 2026-10-21 is the third Wednesday. 14:00 EDT = 18:00 UTC.
    hit = evaluate(datetime(2026, 10, 21, 18, 0, tzinfo=UTC))
    assert hit.notify and "fomc" in hit.codes


def test_spread_only_notifies_inside_overlap():
    cfg = VetoConfig(spread_pips=2.0)
    night = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    overlap = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    quiet = evaluate(night, spread_pips=2.4, cfg=cfg)
    loud = evaluate(overlap, spread_pips=2.4, cfg=cfg)
    ok = evaluate(overlap, spread_pips=1.5, cfg=cfg)
    assert quiet.reject and not quiet.notify
    assert loud.notify and "spread" in loud.codes
    assert not ok.reject


def test_book_halt_uses_r_not_percent_and_not_inverted():
    cfg = VetoConfig(max_daily_loss_r=2.0, max_consecutive_losses=3)
    assert not book_near_halt(daily_r=-0.1, consecutive_losses=0, cfg=cfg)
    assert not book_near_halt(daily_r=-1.99, cfg=cfg)
    assert book_near_halt(daily_r=-2.0, cfg=cfg)
    assert book_near_halt(consecutive_losses=3, cfg=cfg)
    assert book_near_halt(venue_halted=True, daily_r=0.5, cfg=cfg)


def test_dedup_sends_once_per_signature():
    dedup = VetoDedup()
    now = datetime(2026, 10, 2, 12, 30, tzinfo=UTC)
    first = evaluate(now)
    second = evaluate(now)
    assert dedup.should_send(first)
    assert not dedup.should_send(second)
