"""Shared pytest fixtures for harv-realestate tests."""

import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_buyer_config():
    return {
        "client_name": "Test Buyer",
        "client_role": "buyer",
        "target_close_date": "2027-02-15",
        "max_price": 1500000,
        "preferred_areas": ["Hayward", "Union City"],
        "must_haves": ["House (not condo/townhome)", "Big backyard"],
        "nice_to_haves": ["4+ bedrooms"],
        "deal_breakers": ["Solar PPA"],
        "lot_threshold_sqft": 6000,
        "hubspot_contact_id": 483788088001,
    }
