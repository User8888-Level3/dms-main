"""Tests for write_output_marker.py."""

from write_output_marker import write_output_marker, build_verification_stamp


def test_writes_verified_marker(tmp_path):
    out = tmp_path / "MARKER.md"
    write_output_marker(
        out_path=out,
        address="1234 Main St, Hayward",
        client="PinkyHayward-Union-City-May2026",
        mode="analyze",
        mls_provided=True,
        rpr_provided=True,
        fh_passed=True,
        web_sources=["HarvRealtor.com"],
    )
    text = out.read_text()
    assert "MLS/RPR (verified)" in text
    assert "1234 Main St" in text
    assert "Fair Housing scrub: PASSED" in text
    assert "HarvRealtor.com" in text


def test_writes_preliminary_marker_when_mls_missing(tmp_path):
    out = tmp_path / "MARKER.md"
    write_output_marker(
        out_path=out,
        address="1234 Main St",
        client="Test",
        mode="quick",
        mls_provided=False,
        rpr_provided=False,
        fh_passed=True,
        web_sources=["HarvRealtor.com", "Zillow"],
    )
    text = out.read_text()
    assert "PRELIMINARY" in text
    assert "DO NOT SEND TO CLIENT" in text


def test_marker_records_fh_status(tmp_path):
    out = tmp_path / "MARKER.md"
    write_output_marker(
        out_path=out,
        address="X",
        client="Y",
        mode="analyze",
        mls_provided=True,
        rpr_provided=True,
        fh_passed=False,
        web_sources=[],
    )
    text = out.read_text()
    assert "Fair Housing scrub: BLOCKED" in text


def test_build_verification_stamp_verified():
    stamp = build_verification_stamp(mls_provided=True, rpr_provided=True)
    assert "verified" in stamp.lower()
    assert "MLS/RPR" in stamp


def test_build_verification_stamp_preliminary():
    stamp = build_verification_stamp(mls_provided=False, rpr_provided=False)
    assert "PRELIMINARY" in stamp
    assert "DO NOT SEND TO CLIENT" in stamp


def test_build_verification_stamp_partial():
    # If only MLS or only RPR is present, treat as verified (any official source)
    stamp = build_verification_stamp(mls_provided=True, rpr_provided=False)
    assert "verified" in stamp.lower()
