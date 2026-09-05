from io import BytesIO
import pandas as pd

from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from device_names import parse_device_name
from results_sheet import build_results_sheet

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


PENALTY_OUTPUT_COLUMNS = [
    "Racing Number",
    "Class",
    "Pilot",
    "Copilot",
    "Геозона",
    "Влизане в зоната",
    "Излизане от зоната",
    "Продължителност",
    "Най-висока скорост",
    "Средна скорост",
    "Устройство",
    "Speed Limit (km/h)",
]


def _format_penalty_hours(minutes) -> str:
    """Render a penalty given in minutes as HH:MM:SS (80 -> '01:20:00')."""
    try:
        total_seconds = int(round(float(minutes) * 60))
    except (TypeError, ValueError):
        return "00:00:00"

    hours, remainder = divmod(total_seconds, 3600)
    mins, secs = divmod(remainder, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}"


def process_speed_limit_penalty_report(
    raw_bytes: bytes,
    device_name: str,
    speed_limits_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Parse one per-device geofence report for the Speed Limit Penalty Report.

    Same source data as process_speed_limit_report, but the device name is
    split into its racing number / class / pilot / copilot parts, the
    distance and d/t average speed columns are dropped, and the penalty is
    reported both in minutes and as HH:MM:SS.
    """
    raw = _load_raw(raw_bytes)

    sl_map = dict(zip(speed_limits_df["name"], speed_limits_df["speed_limit"].astype(int)))

    # Device names that do not follow the convention leave the split columns blank
    parsed = parse_device_name(device_name) or {}
    racing_id = parsed.get("racing_id", "")
    racer_class = parsed.get("racer_class", "")
    pilot = parsed.get("pilot", "")
    copilot = parsed.get("copilot", "")

    rows = []
    for _, row in raw.iterrows():
        cell0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

        # Skip blank rows, column header rows, and device-header rows
        if cell0 == "" or cell0 == HEADER_MARKER or cell0 == "Устройство:":
            continue

        geofence_name = cell0
        speed_limit = sl_map.get(geofence_name, "")

        rows.append([
            racing_id, racer_class, pilot, copilot,
            geofence_name,
            row.iloc[1], row.iloc[2], row.iloc[3],
            row.iloc[5], row.iloc[6],
            device_name,
            speed_limit,
        ])

    result_df = pd.DataFrame(rows, columns=PENALTY_OUTPUT_COLUMNS)
    result_df["Penalty (min)"] = result_df.apply(
        lambda r: _calculate_penalty(r["Средна скорост"], r["Speed Limit (km/h)"]), axis=1
    )
    result_df["Penalty (h)"] = result_df["Penalty (min)"].apply(_format_penalty_hours)
    return result_df


def to_xlsx(df: pd.DataFrame, sheet_name: str = "Speed Limit Report") -> bytes:
    """Write a DataFrame to XLSX bytes (in memory, no temp files)."""
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return out.getvalue()


MAX_COLUMN_WIDTH = 60


def _autofit_columns(worksheet, df: pd.DataFrame) -> None:
    """Set each column's width to fit its widest cell, capped at MAX_COLUMN_WIDTH."""
    for idx, column in enumerate(df.columns, start=1):
        longest = max(
            [len(str(column))] + [len(str(v)) for v in df[column] if v is not None]
        )
        width = min(longest + 3, MAX_COLUMN_WIDTH)  # +3 leaves room for the filter arrow
        worksheet.column_dimensions[get_column_letter(idx)].width = width


def _write_styled_sheet(writer, df: pd.DataFrame, sheet_name: str,
                        table_name: str) -> None:
    """Write df to a sheet as an Excel table (Table Style Light 15)."""
    df.to_excel(writer, index=False, sheet_name=sheet_name)
    worksheet = writer.sheets[sheet_name]

    for cell in worksheet[1]:
        cell.font = Font(bold=True)

    # An Excel table needs at least one data row
    if not df.empty:
        ref = f"A1:{get_column_letter(len(df.columns))}{len(df) + 1}"
        table = Table(displayName=table_name, ref=ref)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleLight15",
            showRowStripes=True,      # alternating white / light grey rows
            showColumnStripes=False,
            showFirstColumn=False,
            showLastColumn=False,
        )
        worksheet.add_table(table)
    else:
        worksheet.auto_filter.ref = f"A1:{get_column_letter(len(df.columns))}1"

    _autofit_columns(worksheet, df)


def to_styled_xlsx(df: pd.DataFrame, sheet_name: str = "Report",
                   table_name: str = "Report") -> bytes:
    """Write a DataFrame to XLSX bytes formatted as an Excel table.

    Uses Table Style Light 15 (white, banded rows) with a header row and
    filter buttons, bold headers, and columns sized to their content.
    """
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        _write_styled_sheet(writer, df, sheet_name, table_name)
    return out.getvalue()


def to_penalty_xlsx(penalty_df: pd.DataFrame, sheet_name: str = "Report",
                    table_name: str = "Report", results_df=None,
                    geofence_names=None) -> bytes:
    """Write the penalty sheet, optionally followed by "Results Raw Data".

    The penalty sheet is produced by the same code as to_styled_xlsx, so it is
    unaffected by the presence of the results sheet.
    """
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        _write_styled_sheet(writer, penalty_df, sheet_name, table_name)

        if results_df is not None and not results_df.empty:
            build_results_sheet(
                writer.book, penalty_df, results_df, geofence_names or []
            )

    return out.getvalue()
