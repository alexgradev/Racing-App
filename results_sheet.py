"""Builder for the "Results Raw Data" sheet of the Speed Limit Penalty Report.

The sheet pivots the penalty rows so that every geofence becomes a group of
three merged columns (SPEED LIMIT / OVERSPEED / PENALTY), one row per device,
preceded by the crew details entered in the app and closed by a TOTAL TIME
column that sums the crew's stage time and every penalty.

TIME and TOTAL TIME are written as real Excel formulas whenever the inputs
allow it, so the organizer can keep editing the sheet after download.

The banded look is painted by hand rather than with a real Excel table: a
table would rewrite the three-row merged header into its own single-row
header and destroy the geofence groups.
"""

import datetime
import re

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SHEET_NAME = "Results Raw Data"

# Sheet column -> key in the results DataFrame (None means always blank)
IDENTITY_COLUMNS = [
    ("Racing Number", "Racing Number"),
    ("Pilot", "Pilot"),
    ("Copilot", "Copilot"),
    ("MACHINE", "MACHINE"),
    ("CLUB", None),
    ("CLASS", "Class"),
    ("START", "START"),
    ("FINAL", "FINAL"),
    ("TIME", "TIME"),
]
IDENTITY_NAMES = [name for name, _ in IDENTITY_COLUMNS]

SUB_HEADERS = ["SPEED LIMIT", "OVERSPEED", "PENALTY"]
SUB_UNITS = ["km/h", "km/h", "min"]
TOTAL_COLUMN = "TOTAL TIME"

HEADER_ROWS = 3          # geofence name / sub header / unit
DATA_START_ROW = HEADER_ROWS + 1

TIME_FORMAT = "[h]:mm:ss"
CLOCK_FORMAT = "h:mm:ss"
MAX_COLUMN_WIDTH = 40

# Table Style Light 15 look-alike
BAND_FILL = PatternFill("solid", fgColor="F2F2F2")
GRID_SIDE = Side(style="thin", color="D9D9D9")
EDGE_SIDE = Side(style="medium", color="808080")
GRID_BORDER = Border(left=GRID_SIDE, right=GRID_SIDE, top=GRID_SIDE, bottom=GRID_SIDE)

HHMMSS_PATTERN = re.compile(r"^\s*(\d{1,2}):([0-5]?\d):([0-5]?\d)\s*$")
NUMBER_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)")


def parse_hhmmss(value):
    """Parse an ``HH:MM:SS`` string into a ``datetime.time``, or return None.

    Anything that is not a well formed time — an empty cell, "DNF", a typo —
    yields None, which callers treat as "leave it to the user".
    """
    if value is None:
        return None

    match = HHMMSS_PATTERN.match(str(value))
    if not match:
        return None

    hours, minutes, seconds = (int(g) for g in match.groups())
    if hours > 23:
        return None
    return datetime.time(hours, minutes, seconds)


def time_difference(start, final):
    """Return FINAL - START as ``HH:MM:SS``, or "" if either side is unusable.

    Wraps around midnight so a stage finishing after 00:00 still works.
    """
    start_time = parse_hhmmss(start)
    final_time = parse_hhmmss(final)
    if start_time is None or final_time is None:
        return ""

    base = datetime.date(2000, 1, 1)
    delta = (datetime.datetime.combine(base, final_time)
             - datetime.datetime.combine(base, start_time))
    seconds = int(delta.total_seconds()) % (24 * 3600)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _to_number(value):
    """Pull the leading number out of a value ("61 kph" -> 61), else None."""
    if value is None:
        return None

    match = NUMBER_PATTERN.search(str(value))
    if not match:
        return None

    number = float(match.group(1).replace(",", "."))
    return int(number) if number.is_integer() else number


def _blank(value):
    """True for values that should leave the cell empty."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def _pivot_penalties(penalty_df, geofence_names):
    """Map (device, geofence) -> (speed limit, overspeed, penalty).

    A device that passes the same zone more than once has its penalties summed
    and its worst average speed kept.
    """
    lookup = {}
    if penalty_df is None or penalty_df.empty:
        return lookup

    for (device, geofence), rows in penalty_df.groupby(["Устройство", "Геозона"], sort=False):
        if geofence not in geofence_names:
            continue

        speed_limit = _to_number(rows["Speed Limit (km/h)"].iloc[0])
        penalty = pd.to_numeric(rows["Penalty (min)"], errors="coerce").fillna(0).sum()

        speeds = [_to_number(v) for v in rows["Средна скорост"]]
        measured = [s for s in speeds if s is not None]
        overspeed = max(measured) if measured else None

        lookup[(device, geofence)] = (speed_limit, overspeed, penalty)

    return lookup


def _write_headers(worksheet, geofence_names, first_geofence_col, total_col):
    """Write and merge the three header rows."""
    centered = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def style_header(cell, value, bold=True):
        cell.value = value
        cell.font = Font(bold=bold)
        cell.alignment = centered

    for idx, name in enumerate(IDENTITY_NAMES, start=1):
        worksheet.merge_cells(start_row=1, end_row=HEADER_ROWS, start_column=idx, end_column=idx)
        style_header(worksheet.cell(row=1, column=idx), name)

    for gf_idx, geofence in enumerate(geofence_names):
        left = first_geofence_col + 3 * gf_idx
        worksheet.merge_cells(start_row=1, end_row=1, start_column=left, end_column=left + 2)
        style_header(worksheet.cell(row=1, column=left), geofence)

        for offset, (sub, unit) in enumerate(zip(SUB_HEADERS, SUB_UNITS)):
            style_header(worksheet.cell(row=2, column=left + offset), sub)
            style_header(worksheet.cell(row=3, column=left + offset), unit, bold=False)

    worksheet.merge_cells(start_row=1, end_row=HEADER_ROWS,
                          start_column=total_col, end_column=total_col)
    style_header(worksheet.cell(row=1, column=total_col), TOTAL_COLUMN)


BOTTOM_EDGE_BORDER = Border(left=GRID_SIDE, right=GRID_SIDE,
                            top=GRID_SIDE, bottom=EDGE_SIDE)


def _apply_table_look(worksheet, total_col, last_row):
    """Bold header block, banded data rows and light borders throughout."""
    for row in range(1, last_row + 1):
        banded = row >= DATA_START_ROW and (row - DATA_START_ROW) % 2 == 1
        closes_block = row == HEADER_ROWS or (row == last_row and row >= DATA_START_ROW)

        for col in range(1, total_col + 1):
            cell = worksheet.cell(row=row, column=col)
            cell.border = BOTTOM_EDGE_BORDER if closes_block else GRID_BORDER

            if banded:
                cell.fill = BAND_FILL

    # openpyxl draws a merged range's outline from its top-left cell, so the
    # columns merged down the whole header block need the edge set on row 1
    for merged in worksheet.merged_cells.ranges:
        if merged.max_row == HEADER_ROWS:
            worksheet.cell(row=merged.min_row, column=merged.min_col).border = BOTTOM_EDGE_BORDER


def build_results_sheet(workbook, penalty_df, results_df, geofence_names):
    """Add the "Results Raw Data" sheet to an open openpyxl workbook."""
    worksheet = workbook.create_sheet(SHEET_NAME)

    geofence_names = list(geofence_names)
    lookup = _pivot_penalties(penalty_df, set(geofence_names))

    identity_count = len(IDENTITY_COLUMNS)
    first_geofence_col = identity_count + 1
    total_col = first_geofence_col + 3 * len(geofence_names)

    _write_headers(worksheet, geofence_names, first_geofence_col, total_col)

    start_letter = get_column_letter(IDENTITY_NAMES.index("START") + 1)
    final_letter = get_column_letter(IDENTITY_NAMES.index("FINAL") + 1)
    time_letter = get_column_letter(IDENTITY_NAMES.index("TIME") + 1)

    # ── Data rows ────────────────────────────────────────────
    for row_idx, (_, entry) in enumerate(results_df.iterrows(), start=DATA_START_ROW):
        device = entry.get("Device Name", "")

        # Everything up to CLASS; the time columns are handled below
        for col_idx, (name, source) in enumerate(IDENTITY_COLUMNS, start=1):
            if name in ("START", "FINAL", "TIME") or source is None:
                continue
            value = entry.get(source, "")
            if not _blank(value):
                worksheet.cell(row=row_idx, column=col_idx, value=value)

        # START / FINAL as real times when they parse, otherwise as typed
        start_raw, final_raw = entry.get("START", ""), entry.get("FINAL", "")
        start_time, final_time = parse_hhmmss(start_raw), parse_hhmmss(final_raw)

        for letter, raw, parsed in (
            (start_letter, start_raw, start_time),
            (final_letter, final_raw, final_time),
        ):
            if parsed is not None:
                cell = worksheet[f"{letter}{row_idx}"]
                cell.value = parsed
                cell.number_format = CLOCK_FORMAT
            elif not _blank(raw):
                worksheet[f"{letter}{row_idx}"] = str(raw)

        # TIME: a formula when it was derived from valid START/FINAL,
        # otherwise whatever the user typed (as a time value if it parses)
        time_cell = worksheet[f"{time_letter}{row_idx}"]
        time_raw = entry.get("TIME", "")
        auto_time = bool(entry.get("TIME_IS_AUTO", False))

        if auto_time and start_time is not None and final_time is not None:
            time_cell.value = (
                f'=IF(OR({start_letter}{row_idx}="",{final_letter}{row_idx}=""),"",'
                f'MOD({final_letter}{row_idx}-{start_letter}{row_idx},1))'
            )
            time_cell.number_format = TIME_FORMAT
        elif not _blank(time_raw):
            parsed_manual = parse_hhmmss(time_raw)
            if parsed_manual is not None:
                time_cell.value = parsed_manual
                time_cell.number_format = TIME_FORMAT
            else:
                time_cell.value = str(time_raw)

        # ── Geofence blocks ──────────────────────────────────
        penalty_refs = []
        for gf_idx, geofence in enumerate(geofence_names):
            left = first_geofence_col + 3 * gf_idx
            penalty_refs.append(f"{get_column_letter(left + 2)}{row_idx}")

            values = lookup.get((device, geofence))
            if values is None:
                continue

            for offset, value in enumerate(values):
                if not _blank(value):
                    worksheet.cell(row=row_idx, column=left + offset, value=value)

        # ── TOTAL TIME = stage time + all penalties (minutes -> days) ──
        total_cell = worksheet.cell(row=row_idx, column=total_col)
        sum_part = f"+SUM({','.join(penalty_refs)})/1440" if penalty_refs else ""
        total_cell.value = f'=IFERROR({time_letter}{row_idx}{sum_part},"")'
        total_cell.number_format = TIME_FORMAT

    last_row = HEADER_ROWS + len(results_df)
    _apply_table_look(worksheet, total_col, last_row)

    # ── Column widths ────────────────────────────────────────
    for col_idx in range(1, total_col + 1):
        letter = get_column_letter(col_idx)
        lengths = [
            len(str(worksheet.cell(row=r, column=col_idx).value or ""))
            for r in range(2, last_row + 1)
        ]
        # Merged geofence titles span three columns, so they need no full width
        header_len = 0
        if col_idx <= identity_count or col_idx == total_col:
            header_len = len(str(worksheet.cell(row=1, column=col_idx).value or ""))
        worksheet.column_dimensions[letter].width = min(
            max([header_len] + lengths + [8]) + 3, MAX_COLUMN_WIDTH
        )

    worksheet.freeze_panes = worksheet.cell(row=DATA_START_ROW, column=first_geofence_col)
