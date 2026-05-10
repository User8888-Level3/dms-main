"""Render a lot-size flag for inclusion in a property report."""


def render_lot_flag(lot_size_sqft, threshold, client_name):
    """Return a one-line markdown lot-size flag for a property report.

    Args:
        lot_size_sqft: Parsed lot size in sqft. Pass None for unparseable.
            Non-positive values (<= 0) are treated as unparseable too,
            since a 0-sqft lot is physically impossible — defensive against
            upstream parsers that return 0 for unknown.
        threshold: Buyer's preferred minimum lot size, or None / 0 / falsy
            for "no preference set" (returns empty string).
        client_name: Buyer's display name, embedded in BELOW message.

    Returns:
        Empty string if threshold is falsy. Otherwise a markdown line
        starting with "Lot:" — either MEETS, BELOW, or unparseable.
    """
    if not threshold:
        return ""

    if lot_size_sqft is None or lot_size_sqft <= 0:
        return f"Lot: unable to parse — verify manually (target {threshold:,}+ for {client_name})"

    if lot_size_sqft < threshold:
        return (
            f"Lot: {int(lot_size_sqft):,} sqft — BELOW {client_name}'s preference "
            f"(target {threshold:,}+)"
        )

    return f"Lot: {int(lot_size_sqft):,} sqft — ✓ meets preference (target {threshold:,}+)"
