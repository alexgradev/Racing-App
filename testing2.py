import os
import yaml
from auth import login
from devices import get_devices, get_device_groups, filter_group_by_name
from geofences import get_geofences, filter_geofence_by_name
from reports import generate_report

os.system('cls')

# ─── Login ──────────────────────────────────────────────────
with open("secrets.yaml", "r") as f:
    credentials = yaml.safe_load(f)

token = login(credentials["email"], credentials["password"])
print("Logged in successfully.")

# ─── Find device group and get its device IDs ────────────────
groups, _ = get_device_groups(token)
group = filter_group_by_name(groups, "RALLY СТАРА ЗАГОРА")

if group is None:
    raise ValueError("Group 'RALLY СТАРА ЗАГОРА' not found.")

print(f"Group found: ID={group['id']} | Title={group['title']}")

devices = get_devices(token, group_id=group["id"])
device_ids = [d["id"] for d in devices]
print(f"Devices in group: {device_ids}")

# ─── Find geofence ───────────────────────────────────────────
geofences = get_geofences(token)
geofence = filter_geofence_by_name(geofences, "SL 10_60_RALLY_StZ 2026 day 1")

if geofence is None:
    raise ValueError("Geofence 'SL 10_60_RALLY_StZ 2026 day 1' not found.")

print(f"Geofence found: ID={geofence['id']} | Name={geofence['name']}")

# ─── Generate report ─────────────────────────────────────────
url = generate_report(
    token,
    title="RALLY СТАРА ЗАГОРА Report",
    report_type=53,
    format="xls",
    device_ids=device_ids,
    date_from="2026-05-01",
    date_to="2026-05-02",
    geofence_ids=[geofence["id"]],
)

if url:
    print(f"Report ready: {url}")
else:
    print("Report generation failed.")
