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
from pathlib import Path
from typing import List
import re
import sys


# Forbidden phrase patterns. Each tuple: (regex, suggestion, category)
FORBIDDEN_PATTERNS = [
    # Familial status
    (r"\bfamily[- ]friendly\b", "Replace with: factual amenity distances + zoning info", "familial"),
    (r"\bgreat for (kids|children|families)\b", "Remove inference; cite factual school ratings only", "familial"),
    (r"\bperfect for (kids|children|families|young families)\b", "Remove inference; cite factual amenity distances", "familial"),
    (r"\bfamily[ -]?(neighborhood|area|community)\b", "Use 'single-family residential zoning' if zoning-relevant", "familial"),
    (r"\bretirement (community|area|neighborhood)\b", "Only allowed if 55+ HOA-defined community; cite the HOA fact", "familial"),
    (r"\bempty[ -]?nesters?\b", "Remove demographic framing", "familial"),
    (r"\b(?:place|home) to raise (kids|children|family|families)\b",
     "Remove inference; cite zoning + amenity facts only", "familial"),
    (r"\b(growing|young|new|starter) famil(?:y|ies)\b",
     "Remove demographic framing", "familial"),

    # Steering language (coded)
    (r"\byou(?:'?ll| will) fit in\b", "Remove; cite factual amenities instead", "steering"),
    (r"\bright kind of (neighbors|people|community)\b", "Remove demographic framing entirely", "steering"),
    (r"\bsafe (area|neighborhood)\b", "Replace with crime stats + source link, no editorializing", "steering"),
    (r"\bbad (area|neighborhood)\b", "Same — stats + source only", "steering"),
    (r"\bgood (area|neighborhood)\b", "Replace with factual metrics (Walk Score, school ratings, amenities)", "steering"),
    (r"\byou(?:'?d| will| would) (?:love|enjoy|feel at home)\b",
     "Remove subjective framing; cite factual amenities", "steering"),
    (r"\byour kind of (neighbors|people|community|neighborhood|place)\b",
     "Remove demographic framing entirely", "steering"),

    # School narrative (vs factual)
    (r"\bschools are (great|good|excellent) (for|because)\b", "Cite raw rating only; no inference", "school"),
    (r"\bschools (great|good|excellent) for (kids|children|families)\b", "Cite raw rating only; no inference", "school"),

    # Demographic composition narratives
    (r"\b(predominantly|mostly|largely|primarily) (white|black|hispanic|asian|latino|jewish|christian|muslim|hindu|buddhist)\b",
     "Remove entirely. Demographics are not a property characteristic.", "demographic"),
    (r"\b(white|black|hispanic|asian|latino|jewish|christian|muslim) (neighborhood|community|area)\b",
     "Remove entirely. Demographics are not a property characteristic.", "demographic"),
    (r"\bgrowing (white|black|hispanic|asian|latino|jewish|christian|muslim|hindu|buddhist) population\b",
     "Remove entirely.", "demographic"),

    # Religion proximity
    (r"\bwalking distance to (?:the )?[\w.'\s]+?(church|synagogue|mosque|temple|cathedral|chapel)\b",
     "Remove. Religious institutions are not property characteristics.", "religion"),
    (r"\bnear (a |the )?(church|synagogue|mosque|temple|cathedral)\b",
     "Remove. Religious institutions are not property characteristics.", "religion"),
    (r"\b(?:steps from|short walk to|across from|blocks (?:away )?from|view of) (?:the |a )?[\w.'\s]{0,40}?(church|synagogue|mosque|temple|cathedral|chapel|religious institution)s?\b",
     "Remove. Religious institutions are not property characteristics.", "religion"),

    # Disability framing
    (r"\bgreat for (the |a )?(elderly|disabled|handicapped)\b", "Remove demographic framing", "disability"),
    (r"\bnot suitable for (the |a )?(elderly|disabled|handicapped|families with children)\b",
     "Remove — risks discrimination claim", "disability"),
]


@dataclass
class Violation:
    line_number: int
    phrase: str
    suggestion: str
    category: str


@dataclass
class ScrubResult:
    passed: bool
    violations: List[Violation] = field(default_factory=list)


def scrub_report(report_text: str) -> ScrubResult:
    violations: List[Violation] = []
    lines = report_text.splitlines()
    for line_num, line in enumerate(lines, start=1):
        for pattern, suggestion, category in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                violations.append(
                    Violation(
                        line_number=line_num,
                        phrase=match.group(0),
                        suggestion=suggestion,
                        category=category,
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
        lines.append(f"- **Category:** {v.category}")
        lines.append(f"- **Phrase:** `{v.phrase}`")
        lines.append(f"- **Suggested rephrase:** {v.suggestion}\n")
    Path(output_path).write_text("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fair_housing_scrub.py <report.md> [violations_out.md]", file=sys.stderr)
        sys.exit(2)
    report_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else report_path.parent / "VIOLATIONS.md"
    if not report_path.exists():
        print(f"Error: report not found: {report_path}", file=sys.stderr)
        sys.exit(2)
    result = scrub_report(report_path.read_text())
    if result.passed:
        print("PASS")
        sys.exit(0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_violations_report(result, out_path)
    print(f"FAIL — {len(result.violations)} violations. See {out_path}", file=sys.stderr)
    sys.exit(1)
