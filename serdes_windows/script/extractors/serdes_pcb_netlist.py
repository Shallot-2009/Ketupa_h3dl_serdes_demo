#!/usr/bin/env python3
"""Convert SerDes reports/layouts, including SDS_RXnP/N, to netlist Excel."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import csv
import hashlib
import os
import re
import subprocess
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from artifact_paths import artifact_path, NO_SIGNALS, NoMatchingSignals, extractor_exit
from cadence_runtime import resolve_cadence_export_command as _resolve_cadence_export_command
from signal_identity import accepts_signal_family, parse_serdes_network_name

csv.field_size_limit(64 * 1024 * 1024)

FORMAT_VERSION = "ketupa-serdes-netlist-v4"
SORT_CONTRACT = "CHIP -> SDS family/index -> RX/TX lane -> P/N (P then N)"
PROJECT_ROOT = Path(os.environ["KETUPA_WORKFLOW_INPUT"]).resolve()
DESIGN_SUFFIXES = {".brd", ".mcm", ".sip"}
REPORT_CODES = {"netlist": "net", "component": "cmp"}
REPORT_PREFIXES = {
    "netlist": "SerDesNetListReport",
    "component": "ComponentReport",
}
VARIANT_SUFFIX = re.compile(r"_v(?P<version>[12])$", re.I)
SDS_NET = re.compile(
    r"(?:^|[_\-.])SDS[_\-.]?(?P<sds>\d+)[_\-.]+"
    r"(?P<direction>TX|RX)[_\-.]?(?P<lane>\d+)"
    r"[_\-.]+(?:IN|OUT|D)?[_\-.]?(?P<polarity>P|N)$",
    re.I,
)
SDS_BASE_NET = re.compile(
    r"(?:^|[_\-.])SDS[_\-.]+(?P<direction>TX|RX)"
    r"[_\-.]?(?P<lane>\d+)[_\-.]?(?P<polarity>P|N)$",
    re.I,
)
LEGACY_SERDES_NET = re.compile(
    r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]?(?P<lane>\d+)"
    r"[_\-.]+(?P<polarity>P|N)$",
    re.I,
)
UNNUMBERED_SERDES_NET = re.compile(
    r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]+D?(?P<polarity>P|N)$",
    re.I,
)
VECTOR_SERDES_NET = re.compile(
    r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]+D?(?P<polarity>P|N)"
    r"<(?P<lane>\d+)>$",
    re.I,
)
DIRECTION_RANK = {"RX": 0, "TX": 1}
POLARITY_RANK = {"P": 0, "N": 1}
LEGACY_DIE_SUFFIX = re.compile(r"(?:_|-|\.)D(?P<index>\d+)$", re.I)
LEGACY_CHIP_SUFFIX = re.compile(r"(?:_|-|\.)G(?P<index>\d*)$", re.I)
PIN = re.compile(r"^(?P<refdes>[^.\s]+)\.(?P<pin>\S+)$")
# This SerDes PCB workflow has no dedicated gold-finger stage.  A J* component
# may still be a legitimate direct endpoint (for example a coax/test
# connector), so only an intermediate capacitor is forbidden.
FORBIDDEN_INTERMEDIATE = re.compile(r"^C\d+(?:[_\-.][A-Z0-9]+)*$", re.I)
CHIP_REFDES = re.compile(r"^U[A-Z0-9_.-]*$", re.I)
CONNECTOR_REFDES = re.compile(r"^J[A-Z0-9_.-]*$", re.I)
HEADERS = ("Net Name", "PIN 1", "PIN 2", "Signal Type", "M Group", "Chip Partition")

HEADER_COLOR = "17365D"
HEADER_ACCENT = "4472C4"
TEXT_COLOR = "243447"
GRID_COLOR = "D6DEE8"
BLOCK_COLORS = (
    "D9EAF7",
    "E2F0D9",
    "FCE4D6",
    "E4DFEC",
    "FFF2CC",
    "DDEBF7",
    "EADCF8",
    "F4CCCC",
    "D9EAD3",
    "D0E0E3",
    "FCE5CD",
    "DDEBF1",
)
CHIP_COLORS = (
    "E2F0D9",
    "FCE4D6",
    "DDEBF7",
    "E4DFEC",
    "FFF2CC",
    "D9EAD3",
)
CHANNEL_ACCENTS = ("4472C4", "70AD47", "ED7D31", "A64D79", "5B9BD5")


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.row = None
        self.cell = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        del attrs
        tag = tag.casefold()
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).replace("\xa0", " ").split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None


def _clean_cell(value):
    return " ".join(str(value).replace("\xa0", " ").split())


def _decode_report(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Cannot decode Cadence report: {0}".format(path))


def report_variant(path, text=None):
    path = Path(path)
    text = _decode_report(path) if text is None else text
    content_variant = "v1" if "<table" in text.casefold() else "v2"
    suffix_match = VARIANT_SUFFIX.search(path.stem)
    if suffix_match is not None:
        named_variant = "v" + suffix_match.group("version")
        if named_variant != content_variant:
            raise ValueError(
                "Report suffix/content mismatch for {0}: name={1}, content={2}".format(
                    path, named_variant, content_variant
                )
            )
    return content_variant


def canonical_report_stem(path):
    return VARIANT_SUFFIX.sub("", Path(path).stem)


def canonical_xlsx_path(path, output_path=None):
    path = Path(path).resolve()
    selected = (
        Path(output_path).resolve()
        if output_path is not None
        else path.with_name(canonical_report_stem(path) + ".xlsx")
    )
    if selected.suffix.casefold() != ".xlsx":
        raise ValueError("Output must use .xlsx: {0}".format(selected))
    return selected


def _records_from_rows(rows, required_headers):
    requested = tuple(str(header).strip() for header in required_headers)
    required = {header.casefold() for header in requested}
    for index, row in enumerate(rows):
        normalized = [_clean_cell(value).casefold() for value in row]
        if not required.issubset(set(normalized)):
            continue
        positions = {
            header: normalized.index(header.casefold()) for header in requested
        }
        last_column = max(positions.values())
        records = []
        for values in rows[index + 1 :]:
            cleaned = [_clean_cell(value) for value in values]
            if len(cleaned) <= last_column or not any(cleaned):
                continue
            records.append(
                {header: cleaned[column] for header, column in positions.items()}
            )
        if records:
            return records
    raise ValueError(
        "Cadence report does not contain the required columns: {0}".format(
            ", ".join(requested)
        )
    )


def read_report_table(path, required_headers):
    path = Path(path).resolve()
    if path.suffix.casefold() not in {".htm", ".html"} or not path.is_file():
        raise ValueError("Report must be an existing .htm/.html file: {0}".format(path))
    text = _decode_report(path)
    if report_variant(path, text) == "v1":
        parser = TableParser()
        parser.feed(text)
        rows = parser.rows
    else:
        rows = list(csv.reader(text.splitlines()))
    return _records_from_rows(rows, required_headers)


def resolve_cadence_export_command(design=None):
    return _resolve_cadence_export_command(design)


def default_design_output(project_root, design_path, report_kind):
    return artifact_path(project_root, design_path, report_kind, "serdes")


@contextmanager
def temporary_v2_report(design_path, report_kind, project_root=None):
    del project_root
    design_path = Path(design_path).resolve()
    if design_path.suffix.casefold() not in DESIGN_SUFFIXES or not design_path.is_file():
        raise ValueError(
            "Design must be an existing .brd/.mcm/.sip file: {0}".format(
                design_path
            )
        )
    executable = resolve_cadence_export_command(design_path)
    with tempfile.TemporaryDirectory(prefix="ketupa_cadence_report_") as directory:
        report_path = Path(directory) / "{0}_{1}_v2.htm".format(
            REPORT_PREFIXES[report_kind], design_path.stem
        )
        completed = subprocess.run(
            [
                str(executable),
                "-v",
                REPORT_CODES[report_kind],
                str(design_path),
                str(report_path),
            ],
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            check=False,
        )
        if completed.returncode != 0 or not report_path.is_file():
            raise RuntimeError(
                "Cadence export failed ({0}): {1}".format(
                    completed.returncode,
                    completed.stdout.strip() or "no diagnostic output",
                )
            )
        report_variant(report_path)
        try:
            yield report_path
        finally:
            pass


def read_table(path, required_headers):
    return read_report_table(path, required_headers)


def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _hex(values):
    return "".join("{0:02X}".format(max(0, min(255, value))) for value in values)


def _darken(color, amount=0.28):
    return _hex(tuple(round(value * (1 - amount)) for value in _rgb(color)))


def _channel_color(channel):
    number = sum(ord(character) for character in str(channel).upper())
    return CHANNEL_ACCENTS[number % len(CHANNEL_ACCENTS)]


def color_block_key(record):
    net = record.net
    return net.sds, net.chip, net.direction, net.lane


def style_netlist_sheet(sheet, records):
    for cell in sheet[1][:6]:
        cell.font = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=HEADER_COLOR)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=Side(style="medium", color=HEADER_ACCENT))
    sheet.row_dimensions[1].height = 28
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:F{0}".format(sheet.max_row)
    sheet.sheet_view.showGridLines = False
    sheet.sheet_view.zoomScale = 90
    for column, width in zip("ABCDEF", (34, 30, 44, 14, 12, 18)):
        sheet.column_dimensions[column].width = width
    if not records:
        sheet.sheet_properties.tabColor = HEADER_COLOR
        return

    block_keys = list(dict.fromkeys(color_block_key(record) for record in records))
    block_colors = {
        key: BLOCK_COLORS[index % len(BLOCK_COLORS)]
        for index, key in enumerate(block_keys)
    }
    previous = None
    for row_index, record in enumerate(records, start=2):
        net = record.net
        block_color = block_colors[color_block_key(record)]
        chip_color = CHIP_COLORS[(net.chip - 1) % len(CHIP_COLORS)]
        channel_color = _channel_color(sds_display(net.sds))
        sds_changed = previous is None or previous.net.sds != net.sds
        chip_changed = sds_changed or previous.net.chip != net.chip
        group_changed = (
            chip_changed
            or previous.net.direction != net.direction
            or previous.net.lane != net.lane
        )
        block_changed = group_changed or previous.net.direction != net.direction
        next_record = records[row_index - 1] if row_index - 1 < len(records) else None
        block_ends = next_record is None or color_block_key(
            next_record
        ) != color_block_key(record)
        top_color = _darken(chip_color) if chip_changed else _darken(block_color)
        for column_index in range(1, 7):
            cell = sheet.cell(row_index, column_index)
            cell.font = Font(
                name="Microsoft YaHei",
                size=9,
                color=TEXT_COLOR,
                bold=column_index in {1, 5, 6},
            )
            cell.fill = PatternFill(
                "solid", fgColor=chip_color if column_index == 6 else block_color
            )
            cell.alignment = Alignment(
                horizontal="center" if column_index >= 4 else "left",
                vertical="center",
            )
            cell.border = Border(
                left=(
                    Side(style="medium", color=channel_color)
                    if column_index == 1
                    else Side()
                ),
                top=(
                    Side(
                        style="medium",
                        color=top_color
                        if chip_changed or group_changed
                        else channel_color,
                    )
                    if block_changed
                    else Side()
                ),
                bottom=Side(
                    style="medium" if block_ends else "hair",
                    color=_darken(block_color) if block_ends else GRID_COLOR,
                ),
            )
        sheet.row_dimensions[row_index].height = 19
        previous = record
    sheet.sheet_properties.tabColor = (
        HEADER_COLOR
        if sheet.title == "ALL"
        else _darken(BLOCK_COLORS[records[0].net.lane % len(BLOCK_COLORS)], 0.15)
    )


@dataclass(frozen=True)
class NetRecord:
    name: str
    pins: tuple[str, ...]
    sds: int | str | None
    direction: str
    lane: int
    polarity: str
    signal_type: str
    partition: str
    chip: int


@dataclass(frozen=True)
class ExcelRecord:
    net: NetRecord
    pin1: str
    pin2: str

    def values(self):
        if self.net.sds == "":
            group_name = "SDS_{0}{1}".format(
                self.net.direction, self.net.lane
            )
        elif self.net.sds is not None:
            group_name = "SDS{0}_{1}{2}".format(
                self.net.sds, self.net.direction, self.net.lane
            )
        else:
            group_name = "{0}{1}".format(self.net.direction, self.net.lane)
        return (
            self.net.name,
            self.pin1,
            self.pin2,
            self.net.signal_type,
            group_name,
            self.net.partition,
        )


def natural_key(value):
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", str(value))
        if part
    )


def sds_sort_key(value):
    """Sort unnumbered SDS first, numbered SDS next, then legacy names."""
    if value == "":
        return 0, -1
    if value is not None:
        return 0, int(value)
    return 1, 0


def sds_display(value):
    if value == "":
        return "SDS"
    if value is not None:
        return "SDS{0}".format(value)
    return "LEGACY"


def refdes(pin):
    match = PIN.fullmatch(pin)
    if not match:
        raise ValueError("Invalid RefDes.Pin token: {0}".format(pin))
    return match.group("refdes")


def parse_net_name(name):
    parsed = parse_serdes_network_name(name)
    if parsed is None:
        return None
    sds, direction, lane, polarity, chip = parsed
    return (
        sds,
        direction,
        lane,
        polarity,
        "DIFF_{0}".format(polarity),
        "CHIP_{0}".format(chip),
        chip,
    )


def parse_group_selection(value):
    text = str(value).strip().casefold()
    if text in {"", "auto", "all"}:
        return None
    selected = set()
    for token in text.split(","):
        token = token.strip().removeprefix("lane")
        if "-" in token:
            start, end = token.split("-", 1)
            start_number = int(start.removeprefix("lane"))
            end_number = int(end.removeprefix("lane"))
            if start_number > end_number:
                raise ValueError("Descending SerDes lane range: {0}".format(token))
            selected.update(range(start_number, end_number + 1))
        else:
            selected.add(int(token))
    invalid = sorted(lane for lane in selected if lane < 0)
    if invalid:
        raise ValueError("SerDes lanes must be non-negative: {0}".format(invalid))
    return selected


def load_net_records(path, selected_groups=None):
    records = []
    seen = set()
    skipped_single_pin = []
    skipped_vector_capacitor = []
    for row in read_table(path, ("Net Name", "Net Pins")):
        name = row["Net Name"].strip()
        parsed = parse_net_name(name)
        if parsed is None:
            continue
        sds, direction, lane, polarity, category, partition, chip = parsed
        if selected_groups is not None and lane not in selected_groups:
            continue
        key = name.casefold()
        if key in seen:
            raise ValueError("Duplicate SerDes network: {0}".format(name))
        seen.add(key)
        pins = tuple(
            token for token in re.split(r"[\s,;|]+", row["Net Pins"].strip()) if token
        )
        if len(pins) < 2:
            skipped_single_pin.append(name)
            continue
        forbidden = sorted(
            {
                refdes(pin)
                for pin in pins
                if FORBIDDEN_INTERMEDIATE.fullmatch(refdes(pin))
            },
            key=natural_key,
        )
        if forbidden:
            if VECTOR_SERDES_NET.search(name):
                skipped_vector_capacitor.append(name)
                continue
            raise ValueError(
                "SerDes PCB routes must not contain intermediate capacitors: "
                "{0}: {1}".format(
                    name, ", ".join(forbidden)
                )
            )
        records.append(
            NetRecord(
                name,
                pins,
                sds,
                direction,
                lane,
                polarity,
                category,
                partition,
                chip,
            )
        )
    if not records:
        raise NoMatchingSignals("No SerDes SDS TX/RX lane networks were found in {0}".format(path))
    if skipped_single_pin:
        print(
            "Skipped single-pin package nets: {0} ({1})".format(
                len(skipped_single_pin), ", ".join(skipped_single_pin)
            )
        )
    if skipped_vector_capacitor:
        print(
            "Skipped capacitor-terminated vector nets: {0} ({1})".format(
                len(skipped_vector_capacitor), ", ".join(skipped_vector_capacitor)
            )
        )
    validate_differential_pairs(records)
    return records


def validate_differential_pairs(records):
    """Require exactly one case-insensitive P/N net for every selected lane."""
    pairs = {}
    for record in records:
        key = (record.sds, record.partition, record.direction, record.lane)
        pairs.setdefault(key, []).append(record.polarity)
    invalid = [
        "{0}:{1}:{2}{3}={4}".format(
            sds_display(sds),
            partition,
            direction,
            lane,
            sorted(polarities),
        )
        for (sds, partition, direction, lane), polarities in sorted(
            pairs.items(),
            key=lambda item: (
                sds_sort_key(item[0][0]),
                natural_key(item[0][1]),
                DIRECTION_RANK[item[0][2]],
                item[0][3],
            ),
        )
        if sorted(polarities) != ["N", "P"]
    ]
    if invalid:
        raise ValueError(
            "Every SerDes lane must contain exactly one P and one N net: {0}".format(
                "; ".join(invalid)
            )
        )


def build_excel_records(records):
    output = []
    for record in records:
        chip_pins = [
            pin for pin in record.pins if CHIP_REFDES.fullmatch(refdes(pin))
        ]
        connector_pins = [
            pin for pin in record.pins if CONNECTOR_REFDES.fullmatch(refdes(pin))
        ]
        classified_count = len(chip_pins) + len(connector_pins)
        if (
            len(chip_pins) != 1
            or len(connector_pins) != 1
            or classified_count != len(record.pins)
        ):
            raise ValueError(
                "SerDes PCB net {0} must contain exactly one U* CHIP pin and "
                "one J* CONNECTOR pin, with no intermediate component; found "
                "CHIP={1}, CONNECTOR={2}, all={3}".format(
                    record.name, chip_pins, connector_pins, list(record.pins)
                )
            )
        output.append(ExcelRecord(record, chip_pins[0], connector_pins[0]))
    return output


def row_sort_key(record):
    net = record.net
    return (
        net.chip,
        sds_sort_key(net.sds),
        DIRECTION_RANK[net.direction],
        net.lane,
        POLARITY_RANK[net.polarity],
        natural_key(net.name),
    )


def records_fingerprint(records):
    digest = hashlib.sha256()
    digest.update(FORMAT_VERSION.encode("ascii"))
    for record in sorted(records, key=row_sort_key):
        for value in record.values():
            digest.update(str(value).encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest().upper()


def output_is_current(path, fingerprint):
    if not path.is_file():
        return False
    try:
        workbook = load_workbook(path, read_only=True)
        current = workbook.properties.keywords == "source-sha256=" + fingerprint
        workbook.close()
        return current
    except Exception:
        return False


def write_sheet(workbook, title, records):
    sheet = workbook.create_sheet(title)
    sheet.append(HEADERS)
    for record in records:
        sheet.append(record.values())
    style_netlist_sheet(sheet, records)


def create_workbook(records, fingerprint):
    workbook = Workbook()
    workbook.remove(workbook.active)
    ordered = sorted(records, key=row_sort_key)
    write_sheet(workbook, "ALL", ordered)
    write_sheet(workbook, "RX", [row for row in ordered if row.net.direction == "RX"])
    write_sheet(workbook, "TX", [row for row in ordered if row.net.direction == "TX"])
    workbook.properties.title = "Ketupa SerDes Differential Netlist Classification"
    workbook.properties.keywords = "source-sha256=" + fingerprint
    return workbook


def verify_workbook(path, records):
    workbook = load_workbook(path, read_only=False, data_only=True)
    expected_sheets = ["ALL", "RX", "TX"]
    if workbook.sheetnames != expected_sheets:
        raise AssertionError(
            "Unexpected worksheet order: {0}".format(workbook.sheetnames)
        )
    all_rows = list(workbook["ALL"].iter_rows(values_only=True))
    if all_rows[0] != HEADERS:
        raise AssertionError("The six-column workbook contract changed")
    expected = [row.values() for row in sorted(records, key=row_sort_key)]
    if all_rows[1:] != expected:
        raise AssertionError("ALL worksheet rows do not match the parsed report")
    for direction_sheet in workbook.sheetnames[1:]:
        actual = list(workbook[direction_sheet].iter_rows(min_row=2, values_only=True))
        wanted = [
            row.values()
            for row in sorted(records, key=row_sort_key)
            if row.net.direction == direction_sheet
        ]
        if actual != wanted:
            raise AssertionError(
                "Worksheet {0} is not grouped correctly".format(direction_sheet)
            )
    ordered = sorted(records, key=row_sort_key)
    for sheet_name in workbook.sheetnames:
        sheet_records = (
            ordered
            if sheet_name == "ALL"
            else [row for row in ordered if row.net.direction == sheet_name]
        )
        blocks = []
        for record in sheet_records:
            key = color_block_key(record)
            if not blocks or blocks[-1][0] != key:
                blocks.append((key, []))
            blocks[-1][1].append(record)
        row_number = 2
        previous_color = None
        for key, block_records in blocks:
            start_row = row_number
            end_row = start_row + len(block_records) - 1
            colors = {
                workbook[sheet_name].cell(row, column).fill.fgColor.rgb
                for row in range(start_row, end_row + 1)
                for column in range(1, 6)
            }
            if len(colors) != 1:
                raise AssertionError(
                    "Worksheet {0} block {1} does not use one background color".format(
                        sheet_name, key
                    )
                )
            color = next(iter(colors))
            if color == previous_color:
                raise AssertionError(
                    "Worksheet {0} adjacent blocks share one color: {1}".format(
                        sheet_name, key
                    )
                )
            if workbook[sheet_name].cell(start_row, 1).border.top.style != "medium":
                raise AssertionError(
                    "Worksheet {0} block {1} has no top separator".format(
                        sheet_name, key
                    )
                )
            if workbook[sheet_name].cell(end_row, 1).border.bottom.style != "medium":
                raise AssertionError(
                    "Worksheet {0} block {1} has no bottom separator".format(
                        sheet_name, key
                    )
                )
            previous_color = color
            row_number = end_row + 1
    workbook.close()


def _legacy_convert(input_path, output_path=None, groups="auto", force=False):
    input_path = Path(input_path).resolve()
    if (
        input_path.suffix.casefold() not in {".htm", ".html"}
        or not input_path.is_file()
    ):
        raise ValueError(
            "Input must be an existing .htm or .html file: {0}".format(input_path)
        )
    output_path = canonical_xlsx_path(input_path, output_path)
    records = build_excel_records(
        load_net_records(input_path, parse_group_selection(groups))
    )
    fingerprint = records_fingerprint(records)
    if not force and output_is_current(output_path, fingerprint):
        print("Unchanged: {0}".format(output_path))
        return output_path
    temporary = output_path.with_name(".{0}.tmp.xlsx".format(output_path.stem))
    workbook = create_workbook(records, fingerprint)
    try:
        workbook.save(temporary)
        verify_workbook(temporary, records)
        temporary.replace(output_path)
    finally:
        workbook.close()
        if temporary.exists():
            temporary.unlink()
    counts = Counter(record.net.direction for record in records)
    print("Created: {0}".format(output_path))
    print(
        "Networks: {0}; sheets: {1}".format(
            len(records),
            "ALL, RX, TX",
        )
    )
    print(
        "Directions: "
        + ", ".join(
            "{0}={1}".format(direction, counts[direction])
            for direction in ("RX", "TX")
        )
    )
    print("Output order: {0}".format(SORT_CONTRACT))
    return output_path


def convert(input_path, output_path=None, groups="auto", force=False):
    from script.data_adapter.runtime import convert_with_fallback
    selected = canonical_xlsx_path(input_path, output_path)
    return convert_with_fallback(lambda: _legacy_convert(input_path, selected, groups, force), input_path, selected, family="serdes", topology='pcb', groups=groups, force=force)


def convert_source(
    input_path,
    output_path=None,
    groups="auto",
    force=False,
):
    """Convert one v1/v2 report or export one BRD/MCM/SIP layout."""
    input_path = Path(input_path).resolve()
    if input_path.suffix.casefold() in DESIGN_SUFFIXES:
        output_path = Path(
            output_path
            or default_design_output(PROJECT_ROOT, input_path, "netlist")
        ).resolve()
        with temporary_v2_report(
            input_path,
            "netlist",
            PROJECT_ROOT,
        ) as report_path:
            result = convert(report_path, output_path, groups, force)
        print("Removed temporary v2 report.")
        return result
    return convert(input_path, output_path, groups, force)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=PROJECT_ROOT,
        help=(
            "one _v1/_v2 report or BRD/MCM/SIP layout; "
            "default: active PCB folder"
        ),
    )
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--groups",
        "--lanes",
        dest="groups",
        default="auto",
        help="SerDes lane indexes: auto, 0,2, 0-15, or any non-negative index",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = args.input.resolve()
    if input_path.suffix.casefold() in {".htm", ".html"} | DESIGN_SUFFIXES:
        try:
            convert_source(
                input_path,
                args.output,
                args.groups,
                args.force,
            )
        except NoMatchingSignals as error:
            print("[SKIPPED] {0}: {1}".format(input_path.name, error))
            return NO_SIGNALS
        except Exception as error:
            print("[FAILED] {0}: {1}".format(input_path.name, error))
            return 1
        return 0

    input_path.mkdir(parents=True, exist_ok=True)
    reports = sorted(
        (
            path
            for path in input_path.iterdir()
            if path.is_file() and path.suffix.casefold() in {".htm", ".html"}
        ),
        key=lambda path: path.name.casefold(),
    )
    if not reports:
        print("No netlist .htm/.html files found in: {0}".format(input_path))
        print("Put _v1.htm or _v2.htm files there, then double-click 01 again.")
        return 0

    output_directory = args.output.resolve() if args.output is not None else None
    if output_directory is not None:
        if output_directory.exists() and not output_directory.is_dir():
            print("[FAILED] Batch output must be a directory: {0}".format(output_directory))
            return 1
        output_directory.mkdir(parents=True, exist_ok=True)

    failures = 0
    skipped = 0
    for report in reports:
        print("[NETLIST] {0}".format(report.name))
        output_path = (
            output_directory / (canonical_report_stem(report) + ".xlsx")
            if output_directory is not None
            else None
        )
        try:
            convert_source(
                report,
                output_path,
                groups=args.groups,
                force=args.force,
            )
        except NoMatchingSignals as error:
            skipped += 1
            print("[SKIPPED] {0}: {1}".format(report.name, error))
        except Exception as error:
            failures += 1
            print("[FAILED] {0}: {1}".format(report.name, error))
    print(
        "Netlist reports: {0}  Succeeded: {1}  Failed: {2}".format(
            len(reports), len(reports) - failures - skipped, failures
        )
    )
    print("Skipped: {0}".format(skipped))
    return 1 if failures else NO_SIGNALS if skipped == len(reports) else 0


if __name__ == "__main__":
    raise SystemExit(extractor_exit(main))
