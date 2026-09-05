import requests

BASE_URL = "https://gps.easytracking.bg/api"


def get_devices(token, group_id=None, limit=1000):
    """Fetch all devices, optionally filtered by group_id. Returns a flat list of device dicts."""
    params = {
        "lang": "bg",
        "user_api_hash": token,
        "limit": limit,
    }
    if group_id is not None:
        params["group_id"] = group_id

    response = requests.get(f"{BASE_URL}/get_devices", params=params)
    response.raise_for_status()

    data = response.json()
    devices = []
    for group in data:
        devices.extend(group.get("items", []))
    return devices


def get_device_groups(token, limit=100, search=None):
    """Fetch all device groups. Returns (groups list, pagination dict)."""
    params = {
        "lang": "bg",
        "user_api_hash": token,
        "limit": limit,
    }
    if search:
        params["search_phrase"] = search

    response = requests.get(f"{BASE_URL}/devices_groups", params=params)
    response.raise_for_status()
    data = response.json()

    groups = [value for key, value in data.items() if key != "pagination"]
    pagination = data.get("pagination")
    return groups, pagination


def filter_group_by_name(groups, name):
    """Return the first group whose title matches name, or None."""
    for group in groups:
        if group["title"] == name:
            return group
    return None
