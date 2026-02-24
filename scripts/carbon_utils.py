from __future__ import annotations

"""
Utility for estimating CO2 emissions in grams from CPU utilization over a time window.

This is a simple deterministic formula used by the demo data seeding script.
It is not meant to be a precise lifecycle analysis, just a reasonable way to
produce realistic-looking numbers that vary by region and load.
"""

from typing import Dict


# Approximate grid intensity in grams CO2 per kWh, by region.
GRID_INTENSITY_G_PER_KWH: Dict[str, float] = {
    "us-central1": 400.0,      # higher-carbon grid
    "europe-west1": 250.0,     # relatively cleaner grid
}

DEFAULT_INTENSITY_G_PER_KWH = 450.0


def _grid_intensity_for_region(region: str) -> float:
    """Return grid intensity (gCO2/kWh) for a region, with a sensible default."""
    return GRID_INTENSITY_G_PER_KWH.get(region, DEFAULT_INTENSITY_G_PER_KWH)


def estimate_co2_grams_formula(cpu_pct: float, region: str, window_minutes: float) -> float:
    """
    Roughly estimate grams of CO2 emitted over a time window.

    - cpu_pct: average CPU utilization percentage (0–100) for the window
    - region: cloud region name (e.g. \"us-central1\", \"europe-west1\")
    - window_minutes: duration of the window in minutes
    """
    if window_minutes <= 0 or cpu_pct <= 0:
        return 0.0

    # Very rough power model: assume a single virtual CPU with ~50W at 100% load.
    watts_at_full_load = 50.0
    utilization = max(0.0, min(cpu_pct, 100.0)) / 100.0

    # Watt-hours consumed over the window.
    watt_hours = watts_at_full_load * utilization * (window_minutes / 60.0)
    kilowatt_hours = watt_hours / 1000.0

    intensity = _grid_intensity_for_region(region)
    co2_grams = kilowatt_hours * intensity

    return co2_grams

