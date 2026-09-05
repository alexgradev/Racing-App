"""Parsing helpers for the speed limit geofence naming convention.

Template (see other files/names_templates.txt):

    SL XX_AA_day B_ccccc
    SL_XX_AA_day B_ccccc   (both separators after "SL" are accepted)

    XX     = number of the speed limit zone
    AA     = speed limit in km/h (two digit number)
    day B  = day, where B is a single digit
    ccccc  = other helpful info, may contain white space

Examples:
    SL 03_60_day 1_varna 2024    -> speed limit 60
    SL_13_30_day 2_Dobrich 2025  -> speed limit 30
"""

import re

DEFAULT_SPEED_LIMIT = 60

GEOFENCE_NAME_PATTERN = re.compile(
    r"^\s*SL[\s_]*(\d+)\s*_\s*(\d+)\s*_\s*day\s*(\d)\s*_\s*(.*?)\s*$",
    re.IGNORECASE,
)


def parse_geofence_name(name):
    """Parse a geofence name into its parts.

    Returns a dict with keys ``zone``, ``speed_limit``, ``day`` and ``info``,
    or ``None`` if the name does not follow the convention.
    """
    if not name:
        return None

    match = GEOFENCE_NAME_PATTERN.match(str(name))
    if not match:
        return None

    zone, speed_limit, day, info = match.groups()
    return {
        "zone": zone,
        "speed_limit": int(speed_limit),
        "day": int(day),
        "info": info,
    }


def speed_limit_from_name(name, default=DEFAULT_SPEED_LIMIT):
    """Return the speed limit encoded in a geofence name, or ``default``."""
    parsed = parse_geofence_name(name)
    return parsed["speed_limit"] if parsed else default
