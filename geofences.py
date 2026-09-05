import requests

BASE_URL = "https://gps.easytracking.bg/api"


def get_geofences(token):
    """Fetch all geofences. Returns a list of geofence dicts."""
    response = requests.get(
        f"{BASE_URL}/get_geofences",
        params={"lang": "bg", "user_api_hash": token},
    )
    response.raise_for_status()
    return response.json()["items"]["geofences"]


def filter_geofence_by_name(geofences, name):
    """Return the first geofence whose name matches, or None."""
    for gf in geofences:
        if gf["name"] == name:
            return gf
    return None

def get_geofence_groups(token, limit=50, search=None, sort_by=None, sort=None):
    """Returns all geofence groups."""

    params = {
        "lang": "bg",
        "user_api_hash": token,
        "limit": limit
    }

    if search:
        params["search_phrase"] = search
    if sort_by:
        params["sort_by"] = sort_by
        params["sort"] = sort or "asc"

    response = requests.get(
        f"{BASE_URL}/geofences_groups",
        params=params
    )

    response.raise_for_status()
    data = response.json()

    # Same unusual numbered-key structure as device groups
    groups = [value for key, value in data.items() if key != "pagination"]
    pagination = data.get("pagination")

    return groups, pagination
