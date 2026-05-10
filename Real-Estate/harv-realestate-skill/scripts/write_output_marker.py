"""Generate MARKER.md audit trail in property subfolder."""

from datetime import datetime
from pathlib import Path
from typing import Iterable


def build_verification_stamp(mls_provided: bool, rpr_provided: bool) -> str:
    if mls_provided or rpr_provided:
        return "**Data Source: MLS/RPR (verified)**"
    return "**⚠️ PRELIMINARY — Web data only. NOT FOR CLIENT DELIVERY without MLS/RPR verification. DO NOT SEND TO CLIENT.**"


def _fmt_status(provided: bool, kind: str) -> str:
    return f"✅ {kind} provided" if provided else f"❌ {kind} not provided"


def _fmt_fh(passed: bool) -> str:
    return "Fair Housing scrub: PASSED" if passed else "Fair Housing scrub: BLOCKED"


def write_output_marker(
    out_path,
    address: str,
    client: str,
    mode: str,
    mls_provided: bool,
    rpr_provided: bool,
    fh_passed: bool,
    web_sources: Iterable[str],
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    stamp = build_verification_stamp(mls_provided, rpr_provided)
    web_list = ", ".join(web_sources) if web_sources else "(none)"

    content = f"""# Output Marker

**Generated:** {timestamp}
**Address:** {address}
**Client:** {client}
**Skill:** harv-realestate {mode}

## Data Sources

- {_fmt_status(mls_provided, "MLS PDF")}
- {_fmt_status(rpr_provided, "RPR PDF")}
- {_fmt_fh(fh_passed)}
- Web supplements: {web_list}

## Verification Status

{stamp}
"""
    Path(out_path).write_text(content)
