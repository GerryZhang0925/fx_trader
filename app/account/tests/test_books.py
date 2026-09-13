from __future__ import annotations

from account.books import (
    Sleeve,
    VenueSpec,
    round_lots,
    stacking_conflict,
)
from account.intent import desired_action
from account.books import DONCHIAN_H4, StackingPolicy, load_venues
from account.settings import load_config


def test_round_lots_never_rounds_up_past_min():
    spec = VenueSpec(lot_step=0.01, min_lot=0.01)
    assert round_lots(0.009, spec) == 0.0
    assert round_lots(0.019, spec) == 0.01
    assert round_lots(1.239, spec) == 1.23


def test_donchian_stacking_matches_engine():
    p = DONCHIAN_H4
    assert desired_action(p, 0, 1) == "enter"
    assert desired_action(p, 1, 1) == "ignore"
    assert desired_action(p, 1, -1) == "reverse"
    assert desired_action(p, 1, 0) == "hold"


def test_flatten_policy_does_not_reverse():
    p = StackingPolicy(opposite="flatten")
    assert desired_action(p, -1, 1) == "flatten"


def test_two_sleeves_same_symbol_is_book_conflict():
    a = Sleeve("h4", "paper", "donchian", ("GBPUSD",), 5.0)
    b = Sleeve("h1", "paper", "range", ("GBPUSD",), 1.0)
    assert stacking_conflict([a, b], "GBPUSD") == ["h4", "h1"]
    assert stacking_conflict([a, b], "USDJPY") == []


def test_book_uses_fxcm_demo_not_oanda():
    venues = load_venues(load_config())
    assert "oanda_practice" not in venues
    fx = venues["fxcm_demo"]
    assert fx.kind == "demo"
    assert fx.connector == "fxcm_demo"
    assert fx.currency == "USD"
    assert venues["paper_research"].kind == "paper"
