import os
import yaml
from auth import login

os.system('cls')

# ─── Load credentials ───────────────────────────────────────
with open("secrets.yaml", "r") as f:
    credentials = yaml.safe_load(f)

# ─── Login ──────────────────────────────────────────────────
token = login(credentials["email"], credentials["password"])

