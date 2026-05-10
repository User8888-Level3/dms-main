"""Post-output Fair Housing compliance scrub.

Scans assembled markdown reports for forbidden language tied to
Fair Housing Act protected classes (federal) plus California FEHA
additions. Returns a ScrubResult with passed=True on clean output,
or passed=False with a list of violations on detection.

This is the SECOND layer of defense — the FIRST layer is the prompt
injection in Zubair's source SKILL.md files (see Task 7), which
instructs agents not to generate forbidden language. This scrub
catches anything that slips through.
"""

from dataclasses import dataclass, field
from typing import List
import re


# Forbidden phrase patterns. Each tuple: (regex, suggestion)
FORBIDDEN_PATTERNS = [
    # Familial status
    (r"\bfamily[- ]friendly\b", "Replace with: factual amenity distances + zoning info"),
    (r"\bgreat for (kids|children|families)\b", "Remove inference; cite factual school ratings only"),
    (r"\bperfect for (kids|children|families|young families)\b", "Remove inference; cite factual amenity distances"),
    (r"\bfamily[ -]?(neighborhood|area|community)\b", "Use 'single-family residential zoning' if zoning-relevant"),
    (r"\bretirement (community|area|neighborhood)\b", "Only allowed if 55+ HOA-defined community; cite the HOA fact"),
    (r"\bempty[ -]?nesters?\b", "Remove demographic framing"),

    # Steering language (coded)
    (r"\byou(?:'?ll| will) fit in\b", "Remove; cite factual amenities instead"),
    (r"\bright kind of (neighbors|people|community)\b", "Remove demographic framing entirely"),
    (r"\bsafe (area|neighborhood)\b", "Replace with crime stats + source link, no editorializing"),
    (r"\bbad (area|neighborhood)\b", "Same — stats + source only"),
    (r"\bgood (area|neighborhood)\b", "Replace with factual metrics (Walk Score, school ratings, amenities)"),

    # School narrative (vs factual)
    (r"\bschools are (great|good|excellent) (for|because)\b", "Cite raw rating only; no inference"),
    (r"\bschools (great|good|excellent) for (kids|children|families)\b", "Cite raw rating only; no inference"),

    # Demographic composition narratives
    (r"\b(predominantly|mostly|largely|primarily) (white|black|hispanic|asian|latino|jewish|christian|muslim|hindu|buddhist)\b",
     "Remove entirely. Demographics are not a property characteristic."),
    (r"\b(white|black|hispanic|asian|latino|jewish|christian|muslim) (neighborhood|community|area)\b",
     "Remove entirely. Demographics are not a property characteristic."),
    (r"\bgrowing (white|black|hispanic|asian|latino|jewish|christian|muslim|hindu|buddhist) population\b",
     "Remove entirely."),

    # Religion proximity
    (r"\bwalking distance to (?:the )?[\w.'\s]+?(church|synagogue|mosque|temple|cathedral|chapel)\b",
     "Remove. Religious institutions are not property characteristics."),
    (r"\bnear (a |the )?(church|synagogue|mosque|temple|cathedral)\b",
     "Remove. Religious institutions are not property characteristics."),

    # Disability framing
    (r"\bgreat for (the |a )?(elderly|disabled|handicapped)\b", "Remove demographic framing"),
    (r"\bnot suitable for (the |a )?(elderly|disabled|handicapped|families with children)\b",
     "Remove — risks discrimination claim"),
]


@dataclass
class Violation:
    line_number: int
    phrase: str
    suggestion: str


@dataclass
class ScrubResult:
    passed: bool
    violations: List[Violation] = field(default_factory=list)


def scrub_report(report_text: str) -> ScrubResult:
    violations: List[Violation] = []
    lines = report_text.splitlines()
    for line_num, line in enumerate(lines, start=1):
        for pattern, suggestion in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                violations.append(
                    Violation(
                        line_number=line_num,
                        phrase=match.group(0),
                        suggestion=suggestion,
                    )
                )
    return ScrubResult(passed=(len(violations) == 0), violations=violations)


def write_violations_report(result: ScrubResult, output_path) -> None:
    """Write a VIOLATIONS.md file describing each hit."""
    lines = ["# Fair Housing Scrub — Violations\n"]
    lines.append(f"**Status:** BLOCKED — {len(result.violations)} violation(s) found\n")
    lines.append("Review each below, edit the source report, and re-run.\n\n---\n")
    for i, v in enumerate(result.violations, start=1):
        lines.append(f"## Violation {i}\n")
        lines.append(f"- **Line:** {v.line_number}")
        lines.append(f"- **Phrase:** `{v.phrase}`")
        lines.append(f"- **Suggested rephrase:** {v.suggestion}\n")
    from pathlib import Path
    Path(output_path).write_text("\n".join(lines))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: fair_housing_scrub.py <report.md> [violations_out.md]", file=sys.stderr)
        sys.exit(2)
    from pathlib import Path
    report_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else report_path.parent / "VIOLATIONS.md"
    result = scrub_report(report_path.read_text())
    if result.passed:
        print("PASS")
        sys.exit(0)
    write_violations_report(result, out_path)
    print(f"FAIL — {len(result.violations)} violations. See {out_path}", file=sys.stderr)
    sys.exit(1)
