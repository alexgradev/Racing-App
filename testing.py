import os
import yaml
import requests
from auth import login

os.system('cls')

BASE_URL = "https://gps.easytracking.bg/api"

# ─── Load credentials ───────────────────────────────────────
with open("secrets.yaml", "r") as f:
    credentials = yaml.safe_load(f)

# ─── Login ──────────────────────────────────────────────────
token = login(credentials["email"], credentials["password"])

def get_geofences(token):
    """Returns all geofences defined in the account."""

    response = requests.get(
        f"{BASE_URL}/get_geofences",
        params={
            "lang": "bg",
            "user_api_hash": token
        }
    )

    response.raise_for_status()
    return response.json()["items"]["geofences"]  # Drill into the nested structure


# Usage
geofences = get_geofences(token)

# for gf in geofences:
#     print(f"ID: {gf['id']} | Name: {gf['name']} | Type: {gf['type']} | Active: {gf['active']}")

def filter_geofence_by_name(data, name):
    """Returns a single geofence matching the given name."""

    for gf in data:
        if gf["name"] == name:
            return gf

    return None  # Not found


# Usage
geofence = filter_geofence_by_name(geofences, "SL 10_60_RALLY_StZ 2026 day 1")

print(f"ID: {geofence['id']} | Name: {geofence['name']} | Type: {geofence['type']} | Active: {geofence['active']}")

def get_device_groups(token, limit=50, search=None, sort_by=None, sort=None):
    """Fetches all device groups."""

    params = {
        "lang": "bg",
        "user_api_hash": token,
        "limit": limit
    }

    if search:
        params["search_phrase"] = search

    if sort_by:
        params["sorting[sort_by]"] = sort_by
        params["sorting[sort]"] = sort or "asc"

    response = requests.get(
        f"{BASE_URL}/devices_groups",
        params=params
    )

    response.raise_for_status()
    data = response.json()

    # Special handling — extract numbered keys, skip "pagination"
    groups = [
        value for key, value in data.items()
        if key != "pagination"
    ]

    pagination = data.get("pagination")

    return groups, pagination


# ── Usage ────────────────────────────────────────────────────
groups, pagination = get_device_groups(token)

# print(f"Total groups: {pagination['total']}")
# for group in groups:
#     print(f"ID: {group['id']} | Title: {group['title']}")

def filter_groups_by_name(data, name):
    """Returns a single group matching the given name."""

    for group in data:
        if group["title"] == name:
            return group

    return None  # Not found

print(filter_groups_by_name(groups, "RALLY СТАРА ЗАГОРА"))

def get_reports(token):
    """Fetches saved reports and available report types."""

    response = requests.get(
        f"{BASE_URL}/get_reports",
        params={
            "lang": "bg",
            "user_api_hash": token
        }
    )

    response.raise_for_status()
    data = response.json()

    reports = data["items"]["reports"]["data"]
    types   = data["items"]["types"]

    return reports, types


# ── Usage ────────────────────────────────────────────────────
reports, types = get_reports(token)
type_lookup = {t["title"]: t["id"] for t in types}


# Print available report types
# print("Available report types:")
# for t in types:
#     print(f"  ID {t['id']:>3} | {t['title']}")

# Print saved reports
# print("\nSaved reports:")
# for r in reports:
#     print(f"  ID {r['id']} | {r['title']} | Type: {r['type']} | Format: {r['format']}"

def generate_report(token, title, report_type, format, device_ids,
                    date_from, date_to, geofence_ids=None,
                    show_addresses=True, speed_limit=None,
                    from_time=None, to_time=None):
    """Generates a report immediately and returns the download URL."""

    body = {
        "title": title,
        "type": report_type,
        "format": format,           # "pdf", "xls", or "html"
        "devices": device_ids,
        "date_from": date_from,
        "date_to": date_to,
        "show_addresses": show_addresses,
    }

    # Only add optional fields if provided
    if geofence_ids:
        body["geofences"] = geofence_ids
    if speed_limit:
        body["speed_limit"] = speed_limit
    if from_time:
        body["from_time"] = from_time
    if to_time:
        body["to_time"] = to_time

    response = requests.post(
        f"{BASE_URL}/generate_report",
        params={
            "lang": "bg",
            "user_api_hash": token
        },
        json=body
    )

    response.raise_for_status()
    result = response.json()

    if result["status"] == 3:  # success for this endpoint
        print(f"Report ready: {result['url']}")
        return result["url"]
    else:
        print(f"Report generation failed. Status: {result['status']}")
        return None
    
# url = generate_report(
#     token,
#     title="test123",
#     report_type=type_lookup["Геозони"],   # → 5
#     format="pdf",
#     device_ids=device_ids,
#     date_from="2026-05-01",
#     date_to="2026-05-02",
#     speed_limit=90
# )

url = generate_report(
    token,
    title="Геозони Report",
    report_type=53,
    format="pdf",
    device_ids= 1376,          # still needed
    date_from="2026-05-01",          # still needed
    date_to="2026-05-02",            # still needed
    geofence_ids=[4317]         # the geofence you selected
)

print(url)