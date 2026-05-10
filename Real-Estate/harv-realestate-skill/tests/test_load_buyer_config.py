"""Tests for load_buyer_config.py."""

import pytest
from load_buyer_config import load_buyer_config, BuyerConfigError


def test_load_full_config(fixtures_dir):
    config = load_buyer_config(fixtures_dir / "client_pinky.md")
    assert config["client_name"] == "Paramjit (Pinky) Sindhu"
    assert config["client_role"] == "buyer"
    assert config["max_price"] == 1500000
    assert config["lot_threshold_sqft"] == 6000
    assert "Solar PPA" in config["deal_breakers"]
    assert config["hubspot_contact_id"] == 483788088001


def test_load_minimal_config(fixtures_dir):
    config = load_buyer_config(fixtures_dir / "client_minimal.md")
    assert config["client_name"] == "Test User"
    assert config["client_role"] == "buyer"
    # Optional fields default to None or sensible defaults
    assert config.get("max_price") is None
    assert config.get("preferred_areas") == []
    assert config.get("must_haves") == []
    assert config.get("nice_to_haves") == []
    assert config.get("deal_breakers") == []


def test_missing_frontmatter_raises(fixtures_dir):
    with pytest.raises(BuyerConfigError, match="No frontmatter"):
        load_buyer_config(fixtures_dir / "client_no_frontmatter.md")


def test_malformed_yaml_raises(fixtures_dir):
    with pytest.raises(BuyerConfigError, match="YAML"):
        load_buyer_config(fixtures_dir / "client_malformed_yaml.md")


def test_missing_required_field_raises(fixtures_dir, tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("---\nclient_role: buyer\n---\n# missing client_name")
    with pytest.raises(BuyerConfigError, match="client_name"):
        load_buyer_config(bad)


def test_invalid_role_raises(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("---\nclient_name: X\nclient_role: investor\n---\n")
    with pytest.raises(BuyerConfigError, match="client_role"):
        load_buyer_config(bad)


def test_missing_file_raises(tmp_path):
    with pytest.raises(BuyerConfigError, match="not found"):
        load_buyer_config(tmp_path / "does_not_exist.md")


def test_no_trailing_newline_parses_ok(tmp_path):
    """A file whose final character is `---` (no trailing newline) should still parse."""
    path = tmp_path / "no_newline.md"
    path.write_bytes(b'---\nclient_name: "X"\nclient_role: buyer\n---')
    config = load_buyer_config(path)
    assert config["client_name"] == "X"
