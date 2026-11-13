"""Small, shared helpers for exam score calculations.

These functions intentionally contain no Odoo dependencies so every exam model
uses the same zero-maximum and percentage rules.
"""

def percentage(score, maximum):
    """Return ``score`` as a percentage, or zero for a non-positive maximum."""
    if not maximum or maximum <= 0:
        return 0.0
    return score / maximum * 100.0


def weighted_score(score_percentage, weight):
    """Convert a percentage into its contribution to a weighted final mark."""
    return score_percentage * weight / 100.0
