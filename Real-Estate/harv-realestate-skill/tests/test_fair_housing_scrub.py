"""Tests for fair_housing_scrub.py."""

import pytest

from fair_housing_scrub import scrub_report, ScrubResult


def test_clean_report_passes(fixtures_dir):
    text = (fixtures_dir / "report_clean.md").read_text()
    result = scrub_report(text)
    assert result.passed is True
    assert result.violations == []


def test_familial_status_blocked(fixtures_dir):
    text = (fixtures_dir / "report_with_familial.md").read_text()
    result = scrub_report(text)
    assert result.passed is False
    assert any("family-friendly" in v.phrase.lower() for v in result.violations)
    assert any("kids" in v.phrase.lower() for v in result.violations)


def test_steering_phrases_blocked(fixtures_dir):
    text = (fixtures_dir / "report_with_steering.md").read_text()
    result = scrub_report(text)
    assert result.passed is False
    assert any("fit in" in v.phrase.lower() for v in result.violations)
    assert any("right kind of neighbors" in v.phrase.lower() for v in result.violations)


def test_demographic_narrative_blocked(fixtures_dir):
    text = (fixtures_dir / "report_with_demographics.md").read_text()
    result = scrub_report(text)
    assert result.passed is False
    assert len(result.violations) > 0


def test_religion_proximity_blocked(fixtures_dir):
    text = (fixtures_dir / "report_with_religion.md").read_text()
    result = scrub_report(text)
    assert result.passed is False
    assert any("church" in v.phrase.lower() or "synagogue" in v.phrase.lower() for v in result.violations)


def test_violation_includes_line_number():
    text = "Line 1 OK\nLine 2 has family-friendly content\nLine 3 OK\n"
    result = scrub_report(text)
    assert result.passed is False
    v = result.violations[0]
    assert v.line_number == 2
    assert "family-friendly" in v.phrase.lower()


def test_violation_includes_suggestion():
    text = "This is family-friendly area.\n"
    result = scrub_report(text)
    assert result.violations[0].suggestion  # any non-empty suggestion is fine for v1


def test_safe_when_used_factually():
    # "safe" alone is a steering proxy; we flag conservatively
    text = "This is a safe area.\n"
    result = scrub_report(text)
    assert result.passed is False  # flagged — Harv reviews case by case


def test_school_rating_factual_passes():
    text = "GreatSchools rating: 8/10 for elementary.\n"
    result = scrub_report(text)
    assert result.passed is True


def test_school_narrative_blocked():
    text = "The schools are great for families with kids.\n"
    result = scrub_report(text)
    assert result.passed is False


def test_religion_proximity_variants_blocked(fixtures_dir):
    text = (fixtures_dir / "report_with_religion_proximity.md").read_text()
    result = scrub_report(text)
    assert result.passed is False
    phrases = [v.phrase.lower() for v in result.violations]
    # Should catch each of: across from, blocks from, steps from, view of
    assert any("across from" in p for p in phrases)
    assert any("blocks from" in p for p in phrases)
    assert any("steps from" in p for p in phrases)
    assert any("view of" in p for p in phrases)


def test_familial_steering_variants_blocked(fixtures_dir):
    text = (fixtures_dir / "report_with_familial_steering.md").read_text()
    result = scrub_report(text)
    assert result.passed is False
    phrases = [v.phrase.lower() for v in result.violations]
    # Should catch: place to raise children, growing families, young families, starter family
    assert any("raise children" in p for p in phrases)
    assert any("growing families" in p or "growing family" in p for p in phrases)
    assert any("young families" in p or "starter family" in p for p in phrases)


def test_steering_love_variants_blocked(fixtures_dir):
    text = (fixtures_dir / "report_with_steering_variants.md").read_text()
    result = scrub_report(text)
    assert result.passed is False
    phrases = [v.phrase.lower() for v in result.violations]
    assert any("love" in p for p in phrases)
    assert any("your kind of" in p for p in phrases)


def test_violation_includes_category():
    text = "This is family-friendly area.\n"
    result = scrub_report(text)
    assert result.passed is False
    v = result.violations[0]
    assert v.category == "familial"
