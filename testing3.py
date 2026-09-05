import os
import yaml
from auth import login
from devices import get_devices, get_device_groups, filter_group_by_name
from geofences import get_geofences, filter_geofence_by_name, get_geofence_groups
from reports import generate_report

os.system('cls')

# ─── Login ──────────────────────────────────────────────────
with open("secrets.yaml", "r") as f:
    credentials = yaml.safe_load(f)

token = login(credentials["email"], credentials["password"])
print("Logged in successfully.")

# ── Usage of Geofence Group ────────────────────────────────────────────────────
groups, pagination = get_geofence_groups(token)

# print(f"Total geofence groups: {pagination['total']}")
# for group in groups:
#     print(f"ID: {group['id']} | Title: {group['title']}")


# # ── Sort alphabetically ──────────────────────────────────────
# groups, _ = get_geofence_groups(token, sort_by="title", sort="asc")

# ── Usage of All Geofences ────────────────────────────────────────────────────
geofences = get_geofences(token)

# for gf in geofences:
#     print(f"ID: {gf['id']} | Name: {gf['name']} | Type: {gf['type']} | Active: {gf['active']}")

# print(groups)

# print("==================================\n")
# print(geofences[250])

# Usage of get devices and get device group

devices = get_devices(token)

device_groups = get_device_groups(token)

print(devices[50])
print("\n=====================\n")
print(device_groups[0][2])

for group in device_groups[0]:
    print(f"ID: {group['id']} | Title: {group['title']}")
