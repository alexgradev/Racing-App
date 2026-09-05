"""Parsing helpers for the racing device naming convention.

Template (see other files/names_templates.txt):

    XXX-CCC-PILOT / COPILOT

    XXX   = racing id number (usually 3 or 4 digits)
    CCC   = class racer (variable length, no hyphens)
    PILOT / COPILOT = crew names, may contain white space

Examples:
    777-RR-ORGA6 / BEHKO
    103-St.-ИЛИЯ ТОШЕВ / ЖЕЛЬО ПОПОВ
    401-PROTO- ВИКТОР ВЕЛИКОВ / ВАСИЛ ВАСИЛЕВ
"""

import re

# id (digits) - class (no hyphen) - crew (anything non-empty)
DEVICE_NAME_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*([^-]+?)\s*-\s*(\S.*?)\s*$")


def parse_device_name(name):
    """Parse a device name into its parts.

    Returns a dict with keys ``racing_id``, ``racer_class``, ``pilot``,
    ``copilot`` and ``crew``, or ``None`` if the name does not follow the
    convention.
    """
    if not name:
        return None

    match = DEVICE_NAME_PATTERN.match(str(name))
    if not match:
        return None

    racing_id, racer_class, crew = match.groups()

    if "/" in crew:
        pilot, copilot = crew.split("/", 1)
    else:
        pilot, copilot = crew, ""

    return {
        "racing_id": racing_id,
        "racer_class": racer_class.strip(),
        "pilot": pilot.strip(),
        "copilot": copilot.strip(),
        "crew": crew.strip(),
    }


def is_racing_device(device):
    """True if the device name follows the racing naming convention."""
    return parse_device_name(device.get("name")) is not None


def filter_racing_devices(devices):
    """Return only the devices whose names follow the naming convention."""
    return [d for d in devices if is_racing_device(d)]


def get_racer_class(device):
    """Return the CCC (class racer) part of a device name, or None."""
    parsed = parse_device_name(device.get("name"))
    return parsed["racer_class"] if parsed else None


def unique_racer_classes(devices):
    """Return the sorted unique CCC values found across the given devices."""
    classes = {get_racer_class(d) for d in devices}
    classes.discard(None)
    return sorted(classes, key=lambda c: c.casefold())
