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


def test_at_threshold_meets():
    """Boundary: lot == threshold should MEET, not be BELOW."""
    flag = render_lot_flag(lot_size_sqft=6000, threshold=6000, client_name="Pinky")
    assert "BELOW" not in flag
    assert "6,000" in flag


def test_zero_lot_size_treated_as_unparseable():
    """0 is not a real lot size — defensive against upstream parsers that return 0 for unknown."""
    flag = render_lot_flag(lot_size_sqft=0, threshold=6000, client_name="Pinky")
    assert "unable to parse" in flag.lower() or "verify manually" in flag.lower()
    assert "BELOW" not in flag


def test_float_lot_size_renders_as_integer():
    """Floats from CSV/pandas pipelines should render without trailing .0."""
    flag_below = render_lot_flag(lot_size_sqft=4200.0, threshold=6000, client_name="Pinky")
    assert "4,200 sqft" in flag_below
    assert "4,200.0" not in flag_below

    flag_meets = render_lot_flag(lot_size_sqft=7800.5, threshold=6000, client_name="Pinky")
    assert "7,800 sqft" in flag_meets
    assert "7,800.5" not in flag_meets
