from io import BytesIO
import pandas as pd

HEADER_MARKER = "Име на геозона"

OUTPUT_COLUMNS = [
    "Геозона",
    "Влизане в зоната",
    "Излизане от зоната",
    "Продължителност",
    "Изминат път",
    "Най-висока скорост",
    "Средна скорост",
    "Средна скорост (d/t)",
    "Устройство",
    "Speed Limit (km/h)",
]


def _calculate_penalty(avg_speed_str: str, speed_limit) -> float:
    """Return penalty in minutes for exceeding the speed limit.

    First 10 km/h over limit: 2 min per km/h.
    Each km/h beyond 10 over: 5 min per km/h.
    """
    try:
        avg = float(str(avg_speed_str).split()[0])
        limit = float(speed_limit)
        diff = avg - limit
    except (ValueError, IndexError):
        return 0

    if diff <= 0:
        return 0
    if diff <= 10:
        return diff * 2
    return 10 * 2 + (diff - 10) * 5


def _load_raw(raw_bytes: bytes) -> pd.DataFrame:
    """Parse report bytes into a DataFrame using the calamine engine (handles OLE2 .xls)."""
    return pd.read_excel(BytesIO(raw_bytes), header=None, dtype=str, engine="calamine")


def process_speed_limit_report(
    raw_bytes: bytes,
    device_name: str,
    speed_limits_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Parse one per-device geofence report and return a flat DataFrame.

    Device name is passed in directly (known from the API call), so no
    'Устройство:' row parsing is needed. Blank rows, the column header row,
    and summary (totals) rows are all dropped.
    """
    raw = _load_raw(raw_bytes)

    sl_map = dict(zip(speed_limits_df["name"], speed_limits_df["speed_limit"].astype(int)))

    rows = []
    for _, row in raw.iterrows():
        cell0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

        # Skip blank rows, column header rows, and device-header rows
        if cell0 == "" or cell0 == HEADER_MARKER or cell0 == "Устройство:":
            continue

        geofence_name = cell0
        speed_limit = sl_map.get(geofence_name, "")

        rows.append([
            geofence_name,
            row.iloc[1], row.iloc[2], row.iloc[3],
            row.iloc[4], row.iloc[5], row.iloc[6], row.iloc[7],
            device_name,
            speed_limit,
        ])

    result_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    result_df["Penalty (min)"] = result_df.apply(
        lambda r: _calculate_penalty(r["Средна скорост"], r["Speed Limit (km/h)"]), axis=1
    )
    return result_df


def to_xlsx(df: pd.DataFrame) -> bytes:
    """Write a DataFrame to XLSX bytes (in memory, no temp files)."""
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Speed Limit Report")
    return out.getvalue()
