"""Tests for render_lot_flag.py."""

from render_lot_flag import render_lot_flag


def test_below_threshold():
    flag = render_lot_flag(lot_size_sqft=4200, threshold=6000, client_name="Pinky")
    assert "BELOW" in flag
    assert "4,200" in flag
    assert "6,000" in flag
    assert "Pinky" in flag


def test_meets_threshold():
    flag = render_lot_flag(lot_size_sqft=7800, threshold=6000, client_name="Pinky")
    assert "✓" in flag or "meets" in flag.lower()
    assert "7,800" in flag


def test_no_threshold_returns_empty():
    flag = render_lot_flag(lot_size_sqft=4200, threshold=None, client_name="Pinky")
    assert flag == ""


def test_zero_threshold_returns_empty():
    flag = render_lot_flag(lot_size_sqft=4200, threshold=0, client_name="Pinky")
    assert flag == ""


def test_unparseable_lot_size():
    flag = render_lot_flag(lot_size_sqft=None, threshold=6000, client_name="Pinky")
    assert "unable to parse" in flag.lower() or "verify manually" in flag.lower()
