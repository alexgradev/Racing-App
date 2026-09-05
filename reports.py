import requests

BASE_URL = "https://gps.easytracking.bg/api"


def get_reports(token):
    """Fetch saved reports and available report types. Returns (reports list, types list)."""
    response = requests.get(
        f"{BASE_URL}/get_reports",
        params={"lang": "bg", "user_api_hash": token},
    )
    response.raise_for_status()
    data = response.json()
    reports = data["items"]["reports"]["data"]
    types = data["items"]["types"]
    return reports, types


def generate_report(token, title, report_type, format, device_ids,
                    date_from, date_to, geofence_ids=None,
                    show_addresses=True, speed_limit=None,
                    from_time=None, to_time=None):
    """Generate a report and return its download URL, or None on failure."""
    body = {
        "title": title,
        "type": report_type,
        "format": format,
        "devices": device_ids if isinstance(device_ids, list) else [device_ids],
        "date_from": date_from,
        "date_to": date_to,
        "show_addresses": show_addresses,
    }
    if geofence_ids:
        body["geofences"] = geofence_ids
    if speed_limit is not None:
        body["speed_limit"] = speed_limit
    if from_time:
        body["from_time"] = from_time
    if to_time:
        body["to_time"] = to_time

    response = requests.post(
        f"{BASE_URL}/generate_report",
        params={"lang": "bg", "user_api_hash": token},
        json=body,
    )
    response.raise_for_status()
    result = response.json()

    if result["status"] == 3:
        return result["url"]
    return None
