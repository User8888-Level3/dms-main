"""Render a lot-size flag for inclusion in a property report."""


def render_lot_flag(lot_size_sqft, threshold, client_name):
    if not threshold:
        return ""

    if lot_size_sqft is None:
        return f"Lot: unable to parse — verify manually (target {threshold:,}+ for {client_name})"

    if lot_size_sqft < threshold:
        return (
            f"Lot: {lot_size_sqft:,} sqft — BELOW {client_name}'s preference "
            f"(target {threshold:,}+)"
        )

    return f"Lot: {lot_size_sqft:,} sqft — ✓ meets preference (target {threshold:,}+)"
