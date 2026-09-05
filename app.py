import time
import datetime
import pandas as pd
import requests
import streamlit as st

from auth import login
from devices import get_devices, get_device_groups
from geofences import get_geofences, get_geofence_groups
from reports import get_reports, generate_report
from report_processor import (
    process_speed_limit_report,
    process_speed_limit_penalty_report,
    to_xlsx,
    to_styled_xlsx,
)
from device_names import (
    filter_racing_devices,
    get_racer_class,
    parse_device_name,
    unique_racer_classes,
)
from geofence_names import parse_geofence_name, speed_limit_from_name, DEFAULT_SPEED_LIMIT

st.set_page_config(page_title="Gradev Racing App", layout="centered")

# Session state defaults 
if "page" not in st.session_state:
    st.session_state["page"] = "login"
if "token" not in st.session_state:
    st.session_state["token"] = None
if "report_data" not in st.session_state:
    st.session_state["report_data"] = None
if "sl_data" not in st.session_state:
    st.session_state["sl_data"] = None          # cached groups + geofences for speed limit flow
if "sl_selected_geofences" not in st.session_state:
    st.session_state["sl_selected_geofences"] = []
if "sl_speed_limits" not in st.session_state:
    st.session_state["sl_speed_limits"] = None  # final saved DataFrame
if "sl_device_data" not in st.session_state:
    st.session_state["sl_device_data"] = None   # cached device groups + devices
if "sl_selected_devices" not in st.session_state:
    st.session_state["sl_selected_devices"] = []
if "slp_device_data" not in st.session_state:
    st.session_state["slp_device_data"] = None   # cached devices for the penalty flow
if "slp_selected_devices" not in st.session_state:
    st.session_state["slp_selected_devices"] = []
if "slp_selected_geofences" not in st.session_state:
    st.session_state["slp_selected_geofences"] = []
if "slp_speed_limits" not in st.session_state:
    st.session_state["slp_speed_limits"] = None  # final saved DataFrame


def _show_full_multiselect_labels():
    """Stop multiselect chips from truncating long labels with an ellipsis.

    BaseWeb caps the tag text width, which hides the tail of geofence names
    (e.g. "SL_03_60_day 1..."). Let the tags grow and wrap instead.
    """
    st.markdown(
        """
        <style>
        div[data-baseweb="select"] span[data-baseweb="tag"] {
            max-width: none !important;
            height: auto !important;
        }
        div[data-baseweb="select"] span[data-baseweb="tag"] span {
            max-width: none !important;
            overflow: visible !important;
            text-overflow: clip !important;
            white-space: normal !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def go_to(page):
    st.session_state["page"] = page
    st.rerun()


# ════════════════════════════════════════════════════════════
# LOGIN PAGE
# ════════════════════════════════════════════════════════════
def show_login():
    st.title("Gradev Racing App")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True)

    if submit:
        if not email or not password:
            st.error("Please enter both email and password.")
        else:
            try:
                with st.spinner("Logging in..."):
                    token = login(email, password)
                st.session_state["token"] = token
                placeholder = st.empty()
                placeholder.success("Login successful!")
                time.sleep(3)
                placeholder.empty()
                go_to("menu")
            except requests.exceptions.HTTPError as e:
                try:
                    msg = e.response.json().get("message", "Invalid credentials.")
                except Exception:
                    msg = "Invalid credentials."
                st.error(f"Login failed: {msg}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")


# ════════════════════════════════════════════════════════════
# MENU PAGE
# ════════════════════════════════════════════════════════════
def show_menu():
    st.title("Generate Report")
    st.write("Select the type of report you want to generate:")
    st.divider()

    if st.button("Speed Limit Penalty Report", use_container_width=True, type="primary"):
        go_to("speed_limit_penalty_devices")

    if st.button("Speed Limit Report", use_container_width=True):
        go_to("speed_limit")

    if st.button("Waypoint Report", use_container_width=True):
        go_to("waypoint")

    if st.button("General Report", use_container_width=True):
        go_to("report")


# ════════════════════════════════════════════════════════════
# PLACEHOLDER PAGE (Waypoint)
# ════════════════════════════════════════════════════════════
def show_placeholder(name):
    if st.button("← Back"):
        go_to("menu")

    st.title(f"You want to create {name}")
    st.info("Under construction")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT REPORT — GEOFENCE SELECTION
# ════════════════════════════════════════════════════════════
def load_sl_data(token):
    if st.session_state["sl_data"] is not None:
        return st.session_state["sl_data"]

    with st.spinner("Loading geofences..."):
        groups, _ = get_geofence_groups(token)
        geofences = get_geofences(token)

    st.session_state["sl_data"] = {"groups": groups, "geofences": geofences}
    return st.session_state["sl_data"]


def show_speed_limit():
    if st.button("← Back"):
        go_to("menu")

    st.title("Speed Limit Report")

    _show_full_multiselect_labels()

    token = st.session_state["token"]
    data = load_sl_data(token)
    groups = data["groups"]
    all_geofences = data["geofences"]

    # ── Group + geofence selectors side by side ──────────────
    col1, col2 = st.columns(2)

    with col1:
        selected_group_titles = st.multiselect(
            "Geofence Groups",
            [g["title"] for g in groups],
            help="Leave empty to show every geofence. Selecting several groups "
                 "shows the geofences of all of them.",
        )

    # Geofences of all selected groups; no selection = no filter
    if selected_group_titles:
        selected_group_ids = {
            str(g["id"]) for g in groups if g["title"] in selected_group_titles
        }
        visible_geofences = [
            gf for gf in all_geofences if str(gf.get("group_id")) in selected_group_ids
        ]
    else:
        visible_geofences = all_geofences

    with col2:
        gf_options = [gf["name"] for gf in visible_geofences]
        selected_names = st.multiselect("Geofences", gf_options)

    # ── Button ───────────────────────────────────────────────
    st.divider()
    if st.button("Define Speed Limits", use_container_width=True, type="primary"):
        if not selected_names:
            st.error("Please select at least one geofence.")
        else:
            selected_gf = [gf for gf in visible_geofences if gf["name"] in selected_names]
            st.session_state["sl_selected_geofences"] = selected_gf
            go_to("speed_limit_table")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT REPORT — SPEED LIMIT TABLE
# ════════════════════════════════════════════════════════════
def show_speed_limit_table():
    if st.button("← Back"):
        go_to("speed_limit")

    st.title("Speed Limits")

    selected_gf = st.session_state["sl_selected_geofences"]

    if not selected_gf:
        st.warning("No geofences selected. Go back and select at least one.")
        return

    # Build editable DataFrame — name column read-only, speed_limit editable
    selected_gf_sorted = sorted(selected_gf, key=lambda gf: gf["name"])
    df = pd.DataFrame({
        "Geofence Name": [gf["name"] for gf in selected_gf_sorted],
        "Speed Limit":   [60] * len(selected_gf_sorted),   # default value
    })

    edited_df = st.data_editor(
        df,
        column_config={
            "Geofence Name": st.column_config.TextColumn(disabled=True),
            "Speed Limit": st.column_config.NumberColumn(
                min_value=0,
                max_value=999,
                step=1,
                format="%d km/h",
                required=True,
            ),
        },
        hide_index=True,
        use_container_width=True,
    )

    st.divider()
    if st.button("Save", use_container_width=True, type="primary"):
        # Merge speed limits back with full geofence data
        speed_limit_map = dict(zip(edited_df["Geofence Name"], edited_df["Speed Limit"]))

        rows = []
        for gf in selected_gf_sorted:
            row = dict(gf)
            row["speed_limit"] = int(speed_limit_map[gf["name"]])
            rows.append(row)

        result_df = pd.DataFrame(rows)
        st.session_state["sl_speed_limits"] = result_df
        go_to("speed_limit_devices")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT REPORT — DEVICE SELECTION
# ════════════════════════════════════════════════════════════
def load_sl_device_data(token):
    if st.session_state["sl_device_data"] is not None:
        return st.session_state["sl_device_data"]

    with st.spinner("Loading devices..."):
        groups, _ = get_device_groups(token)
        devices = get_devices(token)

    st.session_state["sl_device_data"] = {"groups": groups, "devices": devices}
    return st.session_state["sl_device_data"]


def show_speed_limit_devices():
    if st.button("← Back"):
        go_to("speed_limit_table")

    st.title("Select Devices")

    token = st.session_state["token"]
    data = load_sl_device_data(token)
    groups = data["groups"]
    all_devices = data["devices"]

    # ── Group + device selectors side by side ────────────────
    col1, col2 = st.columns(2)

    with col1:
        group_options = ["— All groups —"] + [g["title"] for g in groups]
        selected_group_title = st.selectbox("Device Group", group_options)

    selected_group_id = None
    if selected_group_title != "— All groups —":
        selected_group_id = next(
            g["id"] for g in groups if g["title"] == selected_group_title
        )

    if selected_group_id is not None:
        visible_devices = [
            d for d in all_devices
            if str(d.get("device_data", {}).get("pivot", {}).get("group_id")) == str(selected_group_id)
        ]
    else:
        visible_devices = all_devices

    with col2:
        device_options = [d["name"] for d in visible_devices]
        selected_names = st.multiselect("Devices", device_options)

    # ── Button ───────────────────────────────────────────────
    st.divider()
    if st.button("Save Devices", use_container_width=True, type="primary"):
        if not selected_names:
            st.error("Please select at least one device.")
        else:
            selected_devices = [d for d in visible_devices if d["name"] in selected_names]
            st.session_state["sl_selected_devices"] = selected_devices
            go_to("speed_limit_generate")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT REPORT — GENERATE
# ════════════════════════════════════════════════════════════
def show_speed_limit_generate():
    if st.button("← Back"):
        go_to("speed_limit_devices")

    st.title("Speed Limit Report")

    speed_limits_df = st.session_state["sl_speed_limits"]
    selected_devices = st.session_state["sl_selected_devices"]

    if speed_limits_df is None or not selected_devices:
        st.warning("Missing data. Please go back and complete the previous steps.")
        return

    # ── Date range ───────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("Date From", value=datetime.date.today())
    with col2:
        date_to = st.date_input("Date To", value=datetime.date.today(), min_value=date_from)

    # ── Title ────────────────────────────────────────────────
    title = st.text_input("Report Title", placeholder="Enter report title")

    # ── Geofence speed limits (read-only) ────────────────────
    st.subheader("Geofence Speed Limits")
    display_gf = speed_limits_df[["name", "speed_limit"]].copy()
    display_gf.columns = ["Geofence Name", "Speed Limit (km/h)"]
    st.dataframe(display_gf, use_container_width=True, hide_index=True)

    # ── Selected devices (read-only) ─────────────────────────
    st.subheader("Selected Devices")
    display_dev = pd.DataFrame({"Device Name": [d["name"] for d in selected_devices]})
    st.dataframe(display_dev, use_container_width=True, hide_index=True)

    # ── Generate ─────────────────────────────────────────────
    st.divider()
    if st.button("Generate Report", use_container_width=True, type="primary"):
        if not title.strip():
            st.error("Please enter a report title.")
        elif date_to < date_from:
            st.error("Date To must be equal to or later than Date From.")
        else:
            token = st.session_state["token"]
            geofence_ids = list(speed_limits_df["id"].astype(int))
            all_frames = []
            error_msg = None

            progress = st.progress(0, text="Starting…")
            try:
                for i, device in enumerate(selected_devices):
                    progress.progress(
                        i / len(selected_devices),
                        text=f"Processing {device['name']} ({i + 1}/{len(selected_devices)})…",
                    )
                    url = generate_report(
                        token,
                        title=f"{title.strip()} – {device['name']}",
                        report_type=53,
                        format="xls",
                        device_ids=[device["id"]],
                        date_from=str(date_from),
                        date_to=str(date_to),
                        geofence_ids=geofence_ids,
                    )
                    if url is None:
                        error_msg = f"No URL returned for device {device['name']}."
                        break
                    raw_bytes = requests.get(url).content
                    df = process_speed_limit_report(raw_bytes, device["name"], speed_limits_df)
                    all_frames.append(df)

                progress.progress(1.0, text="Done.")
            except requests.exceptions.HTTPError as e:
                try:
                    error_msg = e.response.json().get("message", str(e))
                except Exception:
                    error_msg = str(e)
            except Exception as e:
                error_msg = str(e)

            if error_msg:
                st.error(f"Report generation failed: {error_msg}")
            elif all_frames:
                combined = pd.concat(all_frames, ignore_index=True)
                xlsx_bytes = to_xlsx(combined)
                st.success("Report ready!")
                st.download_button(
                    "Download Report",
                    data=xlsx_bytes,
                    file_name="speed_limit_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.warning("No geofence visits found for the selected devices and date range.")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT PENALTY REPORT — DEVICE SELECTION
# ════════════════════════════════════════════════════════════
def load_slp_device_data(token):
    if st.session_state["slp_device_data"] is not None:
        return st.session_state["slp_device_data"]

    with st.spinner("Loading devices..."):
        devices = get_devices(token)

    st.session_state["slp_device_data"] = {"devices": devices}
    return st.session_state["slp_device_data"]


def show_speed_limit_penalty_devices():
    if st.button("← Back"):
        go_to("menu")

    st.title("Speed Limit Penalty Report")
    st.write("Select the racers participating in the event.")

    token = st.session_state["token"]
    all_devices = load_slp_device_data(token)["devices"]

    # ── Naming-convention filter ─────────────────────────────
    only_racing = st.checkbox(
        "Show only devices following the racing naming convention "
        "(XXX-CCC-PILOT / COPILOT)",
        value=True,
    )

    if only_racing:
        candidates = filter_racing_devices(all_devices)

        classes = unique_racer_classes(candidates)
        selected_class = st.selectbox("Racer Class", ["— All classes —"] + classes)

        if selected_class != "— All classes —":
            visible_devices = [
                d for d in candidates if get_racer_class(d) == selected_class
            ]
        else:
            visible_devices = candidates

        if not candidates:
            st.warning("No devices match the racing naming convention.")
    else:
        visible_devices = all_devices

    # ── Device selection ─────────────────────────────────────
    visible_devices = sorted(visible_devices, key=lambda d: d["name"])
    device_options = [d["name"] for d in visible_devices]
    selected_names = st.multiselect("Devices", device_options)

    st.caption(f"{len(device_options)} device(s) available.")

    # ── Button ───────────────────────────────────────────────
    st.divider()
    if st.button("Save Devices", use_container_width=True, type="primary"):
        if not selected_names:
            st.error("Please select at least one device.")
        else:
            st.session_state["slp_selected_devices"] = [
                d for d in visible_devices if d["name"] in selected_names
            ]
            go_to("speed_limit_penalty_geofences")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT PENALTY REPORT — GEOFENCE SELECTION
# ════════════════════════════════════════════════════════════
def show_speed_limit_penalty_geofences():
    if st.button("← Back"):
        go_to("speed_limit_penalty_devices")

    st.title("Select Geofences")

    _show_full_multiselect_labels()

    token = st.session_state["token"]
    data = load_sl_data(token)
    groups = data["groups"]
    all_geofences = data["geofences"]

    # ── Group + geofence selectors side by side ──────────────
    col1, col2 = st.columns(2)

    with col1:
        selected_group_titles = st.multiselect(
            "Geofence Groups",
            [g["title"] for g in groups],
            help="Leave empty to show every geofence. Selecting several groups "
                 "shows the geofences of all of them.",
        )

    # Geofences of all selected groups; no selection = no filter
    if selected_group_titles:
        selected_group_ids = {
            str(g["id"]) for g in groups if g["title"] in selected_group_titles
        }
        visible_geofences = [
            gf for gf in all_geofences if str(gf.get("group_id")) in selected_group_ids
        ]
    else:
        visible_geofences = all_geofences

    with col2:
        gf_options = [gf["name"] for gf in visible_geofences]
        selected_names = st.multiselect("Geofences", gf_options)

    # ── Button ───────────────────────────────────────────────
    st.divider()
    if st.button("Define Speed Limits", use_container_width=True, type="primary"):
        if not selected_names:
            st.error("Please select at least one geofence.")
        else:
            selected_gf = [gf for gf in visible_geofences if gf["name"] in selected_names]
            st.session_state["slp_selected_geofences"] = selected_gf
            go_to("speed_limit_penalty_table")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT PENALTY REPORT — SPEED LIMIT TABLE
# ════════════════════════════════════════════════════════════
def show_speed_limit_penalty_table():
    if st.button("← Back"):
        go_to("speed_limit_penalty_geofences")

    st.title("Speed Limits")

    selected_gf = st.session_state["slp_selected_geofences"]

    if not selected_gf:
        st.warning("No geofences selected. Go back and select at least one.")
        return

    # Speed limits are read from the geofence name (SL XX_AA_day B_ccccc);
    # names that do not follow the convention fall back to the default.
    selected_gf_sorted = sorted(selected_gf, key=lambda gf: gf["name"])
    unparsed = [gf["name"] for gf in selected_gf_sorted
                if parse_geofence_name(gf["name"]) is None]

    df = pd.DataFrame({
        "Geofence Name": [gf["name"] for gf in selected_gf_sorted],
        "Speed Limit": [speed_limit_from_name(gf["name"]) for gf in selected_gf_sorted],
    })

    st.write(
        "Speed limits were read from the geofence names. "
        "Edit any value below if it is wrong."
    )
    if unparsed:
        st.warning(
            f"{len(unparsed)} geofence name(s) do not follow the naming convention "
            f"(SL XX_AA_day B_ccccc or SL_XX_AA_day B_ccccc), "
            f"so they default to {DEFAULT_SPEED_LIMIT} km/h: "
            + ", ".join(unparsed)
        )

    edited_df = st.data_editor(
        df,
        column_config={
            "Geofence Name": st.column_config.TextColumn(disabled=True),
            "Speed Limit": st.column_config.NumberColumn(
                min_value=0,
                max_value=999,
                step=1,
                format="%d km/h",
                required=True,
            ),
        },
        hide_index=True,
        use_container_width=True,
    )

    st.divider()
    if st.button("Save", use_container_width=True, type="primary"):
        # Merge speed limits back with full geofence data
        speed_limit_map = dict(zip(edited_df["Geofence Name"], edited_df["Speed Limit"]))

        rows = []
        for gf in selected_gf_sorted:
            row = dict(gf)
            row["speed_limit"] = int(speed_limit_map[gf["name"]])
            rows.append(row)

        st.session_state["slp_speed_limits"] = pd.DataFrame(rows)
        go_to("speed_limit_penalty_generate")


# ════════════════════════════════════════════════════════════
# SPEED LIMIT PENALTY REPORT — GENERATE
# ════════════════════════════════════════════════════════════
def _safe_filename(title):
    """Turn a report title into a safe .xlsx file name."""
    cleaned = "".join(c for c in title if c not in r'\/:*?"<>|').strip()
    return f"{cleaned or 'speed_limit_penalty_report'}.xlsx"


def show_speed_limit_penalty_generate():
    if st.button("← Back"):
        go_to("speed_limit_penalty_table")

    st.title("Speed Limit Penalty Report")

    speed_limits_df = st.session_state["slp_speed_limits"]
    selected_devices = st.session_state["slp_selected_devices"]

    if speed_limits_df is None or not selected_devices:
        st.warning("Missing data. Please go back and complete the previous steps.")
        return

    # ── Date range ───────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("Date From", value=datetime.date.today())
    with col2:
        date_to = st.date_input("Date To", value=datetime.date.today(), min_value=date_from)

    # ── Title (also the downloaded file name) ────────────────
    title = st.text_input("Report Title", placeholder="Enter report title")

    # ── Geofence speed limits (still editable) ───────────────
    st.subheader("Geofence Speed Limits")
    gf_df = speed_limits_df[["name", "speed_limit"]].copy()
    gf_df.columns = ["Geofence Name", "Speed Limit"]

    edited_gf = st.data_editor(
        gf_df,
        column_config={
            "Geofence Name": st.column_config.TextColumn(disabled=True),
            "Speed Limit": st.column_config.NumberColumn(
                min_value=0,
                max_value=999,
                step=1,
                format="%d km/h",
                required=True,
            ),
        },
        hide_index=True,
        use_container_width=True,
        key="slp_generate_speed_limits",
    )

    # ── Selected devices, split by naming convention ─────────
    st.subheader("Selected Devices")
    device_rows = []
    for d in selected_devices:
        parsed = parse_device_name(d["name"]) or {}
        device_rows.append({
            "Device Name": d["name"],
            "Racing Number": parsed.get("racing_id", ""),
            "Class": parsed.get("racer_class", ""),
            "Pilot": parsed.get("pilot", ""),
            "Copilot": parsed.get("copilot", ""),
        })
    st.dataframe(pd.DataFrame(device_rows), use_container_width=True, hide_index=True)

    # ── Generate ─────────────────────────────────────────────
    st.divider()
    if st.button("Generate Report", use_container_width=True, type="primary"):
        if not title.strip():
            st.error("Please enter a report title.")
        elif date_to < date_from:
            st.error("Date To must be equal to or later than Date From.")
        else:
            # Apply any edits made on this page before generating
            limits_df = speed_limits_df.copy()
            limits_df["speed_limit"] = (
                limits_df["name"]
                .map(dict(zip(edited_gf["Geofence Name"], edited_gf["Speed Limit"])))
                .astype(int)
            )

            token = st.session_state["token"]
            geofence_ids = list(limits_df["id"].astype(int))
            all_frames = []
            error_msg = None

            progress = st.progress(0, text="Starting…")
            try:
                for i, device in enumerate(selected_devices):
                    progress.progress(
                        i / len(selected_devices),
                        text=f"Processing {device['name']} ({i + 1}/{len(selected_devices)})…",
                    )
                    url = generate_report(
                        token,
                        title=f"{title.strip()} – {device['name']}",
                        report_type=53,
                        format="xls",
                        device_ids=[device["id"]],
                        date_from=str(date_from),
                        date_to=str(date_to),
                        geofence_ids=geofence_ids,
                    )
                    if url is None:
                        error_msg = f"No URL returned for device {device['name']}."
                        break
                    raw_bytes = requests.get(url).content
                    df = process_speed_limit_penalty_report(
                        raw_bytes, device["name"], limits_df
                    )
                    all_frames.append(df)

                progress.progress(1.0, text="Done.")
            except requests.exceptions.HTTPError as e:
                try:
                    error_msg = e.response.json().get("message", str(e))
                except Exception:
                    error_msg = str(e)
            except Exception as e:
                error_msg = str(e)

            if error_msg:
                st.error(f"Report generation failed: {error_msg}")
            elif all_frames:
                combined = pd.concat(all_frames, ignore_index=True)
                xlsx_bytes = to_styled_xlsx(
                    combined,
                    sheet_name="Speed Limit Penalty",
                    table_name="SpeedLimitPenalty",
                )
                st.success("Report ready!")
                st.download_button(
                    "Download Report",
                    data=xlsx_bytes,
                    file_name=_safe_filename(title.strip()),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.warning("No geofence visits found for the selected devices and date range.")


# ════════════════════════════════════════════════════════════
# GENERAL REPORT PAGE
# ════════════════════════════════════════════════════════════
def load_report_data(token):
    if st.session_state["report_data"] is not None:
        return st.session_state["report_data"]

    with st.spinner("Loading data..."):
        _, types = get_reports(token)
        devices = get_devices(token)
        geofences = get_geofences(token)

    st.session_state["report_data"] = {
        "types": types,
        "devices": devices,
        "geofences": geofences,
    }
    return st.session_state["report_data"]


def show_report():
    if st.button("← Back"):
        go_to("menu")

    st.title("General Report")

    token = st.session_state["token"]
    data = load_report_data(token)

    types = data["types"]
    devices = data["devices"]
    geofences = data["geofences"]

    col1, col2 = st.columns(2)
    with col1:
        date_from = st.date_input("Date From", value=datetime.date.today())
    with col2:
        date_to = st.date_input("Date To", value=datetime.date.today(), min_value=date_from)

    title = st.text_input("Report Title", placeholder="Enter report title")

    col3, col4 = st.columns(2)
    with col3:
        type_names = [t["title"] for t in types]
        selected_type_name = st.selectbox("Report Type", type_names)
        selected_type_id = next(t["id"] for t in types if t["title"] == selected_type_name)
    with col4:
        fmt = st.radio("Format", ["PDF", "XLS"], horizontal=True)

    device_options = {f"{d['name']} (ID: {d['id']})": d["id"] for d in devices}
    selected_device_labels = st.multiselect("Devices", list(device_options.keys()))
    selected_device_ids = [device_options[label] for label in selected_device_labels]

    geofence_options = {f"{gf['name']} (ID: {gf['id']})": gf["id"] for gf in geofences}
    selected_geofence_labels = st.multiselect("Geofences (optional)", list(geofence_options.keys()))
    selected_geofence_ids = [geofence_options[label] for label in selected_geofence_labels]

    st.divider()
    if st.button("Generate Report", use_container_width=True, type="primary"):
        if not title.strip():
            st.error("Please enter a report title.")
        elif date_to < date_from:
            st.error("Date To must be equal to or later than Date From.")
        elif not selected_device_ids:
            st.error("Please select at least one device.")
        else:
            with st.spinner("Generating report..."):
                try:
                    url = generate_report(
                        token,
                        title=title.strip(),
                        report_type=selected_type_id,
                        format=fmt.lower(),
                        device_ids=selected_device_ids,
                        date_from=str(date_from),
                        date_to=str(date_to),
                        geofence_ids=selected_geofence_ids if selected_geofence_ids else None,
                    )
                    if url:
                        st.success("Report ready!")
                        st.link_button("Download Report", url, use_container_width=True)
                    else:
                        st.error("Report generation failed. The server returned no URL.")
                except requests.exceptions.HTTPError as e:
                    try:
                        msg = e.response.json().get("message", str(e))
                    except Exception:
                        msg = str(e)
                    st.error(f"Report generation failed: {msg}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")


# ════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════
page = st.session_state["page"]

if page == "login":
    show_login()
elif st.session_state["token"] is None:
    go_to("login")
elif page == "menu":
    show_menu()
elif page == "speed_limit":
    show_speed_limit()
elif page == "speed_limit_table":
    show_speed_limit_table()
elif page == "speed_limit_devices":
    show_speed_limit_devices()
elif page == "speed_limit_generate":
    show_speed_limit_generate()
elif page == "speed_limit_penalty_devices":
    show_speed_limit_penalty_devices()
elif page == "speed_limit_penalty_geofences":
    show_speed_limit_penalty_geofences()
elif page == "speed_limit_penalty_table":
    show_speed_limit_penalty_table()
elif page == "speed_limit_penalty_generate":
    show_speed_limit_penalty_generate()
elif page == "waypoint":
    show_placeholder("Waypoint Report")
elif page == "report":
    show_report()
