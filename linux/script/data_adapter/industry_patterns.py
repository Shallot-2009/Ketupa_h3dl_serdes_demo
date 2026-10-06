"""Conservative recognizers for common industry DDR, PCIe, SerDes, and clock names.

The selected workflow supplies the family.  These recognizers never infer a
workflow from a name and return ``None`` when the name lacks enough structure.
Project-specific profiles remain the authoritative path for private naming.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


_DDR_DOMAIN = re.compile(r"(?:LPDDR[2-6X]?|DDR[2-6X]?|GDDR[3-7X]?|MEM(?:ORY)?|DRAM)", re.I)
_DDR_STRUCTURE = re.compile(r"(?:^|_)(?:CH(?:ANNEL)?[A-Z0-9]+|BYTE[0-9]+|DQS|DQ[0-9]+)(?:_|$)", re.I)
_DDR_SIGNAL = re.compile(
    r"(?:^|_)(?P<signal>RDQS|DQS|WCK|DBI|DMI|DM|DQ|CA|CKE|CK|CS|ODT|RESET|RST|"
    r"ALERT|ACT|PAR|TEN|ZQ|RAS|CAS|WE|BG|BA|A)(?P<index>[0-9]+)?(?:_|$)",
    re.I,
)
_CONTROLLER = re.compile(r"(?:^|_)(?:MEMC|MC|M)(?P<value>[0-9]+)(?:_|$)", re.I)
_CHANNEL = re.compile(r"(?:^|_)CH(?:ANNEL)?_?(?P<value>[A-Z0-9]+)(?:_|$)", re.I)
_BYTE = re.compile(r"(?:^|_)(?:BYTE|BY|B)_?(?P<value>[0-9]+)(?:_|$)", re.I)
_RANK = re.compile(r"(?:^|_)(?:RANK|RK|CS)_?(?P<value>[0-9]+)(?:_|$)", re.I)

_PCIE_DOMAIN = re.compile(r"(?:PCIE|PCI_EXPRESS|PEX|PCIEGEN[1-7]|GEN[1-7]_PCIE)", re.I)
_SERDES_DOMAIN = re.compile(
    r"(?:SERDES|SDS[0-9]*|HSS|HSIO|XFI|SFI|CEI|KR[1248]?|PHY[0-9]*|"
    r"USB(?:3|4)?|SATA|UFS|ETH(?:ERNET)?)",
    re.I,
)
_SERDES_SDS_IO_DIE = re.compile(
    r"^SDS_?(?P<sds>[0-9]+)_+"
    r"(?P<direction>TX|RX)_?(?P<lane>[0-9]+)_+"
    r"(?P<flow>IN|OUT)_?(?P<polarity>P|N)_+"
    r"D(?P<die>[1-5])$",
    re.I,
)
_SERDES_IO_POLARITY = re.compile(
    r"(?:^|_)(?:IN|OUT)_?(?P<polarity>P|N)(?:_|$)", re.I
)
_CLOCK_DOMAIN = re.compile(r"(?:REF_?CLK|PCIE_?CLK|CLK|CLOCK|PLL|XTAL|OSC|XO)", re.I)
_CLOCK_EXCLUDE = re.compile(
    r"(?:^|_)(?:CLKREQ|REQ|ENABLE|EN|RESET|RST|GOOD|LOCK|[A-Z0-9]*(?:VDD|VSS))(?:_|$)",
    re.I,
)


def _canonical(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).upper().strip()
    text = text.replace("+", "_P").replace("*", "_N")
    text = re.sub(r"\bPLUS\b|\bPOS(?:ITIVE)?\b", "P", text)
    text = re.sub(r"\bMINUS\b|\bNEG(?:ATIVE)?\b", "N", text)
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _value(pattern: re.Pattern[str], text: str, default: str) -> str:
    match = pattern.search(text)
    return match.group("value") if match else default


def _polarity(text: str) -> str:
    patterns = (
        _SERDES_IO_POLARITY,
        r"(?:^|_)(?:D)?(?P<polarity>P|N)$",
        r"(?:^|_)D?(?P<polarity>P|N)(?:_)?(?P<vector>[0-9]+)$",
    )
    for pattern in patterns:
        match = (
            pattern.search(text)
            if isinstance(pattern, re.Pattern)
            else re.search(pattern, text, re.I)
        )
        if match:
            value = match.group("polarity").upper()
            return value
    return ""


def _direction_lane(text: str) -> tuple[str, str] | None:
    patterns = (
        r"(?:^|_)(?P<direction>TX|RX)(?:_?LANE)?_?(?P<lane>[0-9]+)(?:_|$)",
        r"(?:^|_)LANE_?(?P<lane>[0-9]+)_(?P<direction>TX|RX)(?:_|$)",
        r"(?:^|_)(?P<direction>TX|RX)_(?:D?[PN])_?(?P<lane>[0-9]+)(?:_|$)",
        r"(?:^|_)(?P<direction>TX|RX)(?:D?[PN])(?P<lane>[0-9]+)(?:_|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group("direction").upper(), str(int(match.group("lane")))
    return None


def _partition(source_partition: str, endpoint_a: list[str], default: str) -> str:
    if str(source_partition).strip():
        return str(source_partition).strip()
    if endpoint_a:
        refdes = str(endpoint_a[0]).partition(".")[0].strip().upper()
        if refdes:
            return "ENDPOINT_" + re.sub(r"[^A-Z0-9]+", "_", refdes).strip("_")
    return default


def identify(
    *,
    name: str,
    family: str,
    topology: str,
    endpoint_a: list[str],
    source_signal_type: str = "",
    source_group: str = "",
    source_partition: str = "",
) -> dict[str, str] | None:
    """Return canonical identity fields for a recognized common net name."""
    text = _canonical(name)
    segment = "package" if topology == "pkg" else "board"
    if family == "lpddr":
        if not _DDR_DOMAIN.search(text) and not _DDR_STRUCTURE.search(text):
            return None
        signal_match = _DDR_SIGNAL.search(text)
        if signal_match is None:
            return None
        generation_match = _DDR_DOMAIN.search(text)
        generation = generation_match.group(0).upper() if generation_match else "DDR"
        signal = signal_match.group("signal").upper().replace("RST", "RESET")
        index = signal_match.group("index") or ""
        controller = _value(_CONTROLLER, text, "0")
        channel = _value(_CHANNEL, text, "ALL")
        byte = _value(_BYTE, text, "ALL")
        rank = _value(_RANK, text, "ALL")
        polarity = _polarity(text) if signal in {"DQS", "RDQS", "WCK", "CK"} else ""
        suffix = polarity or index or "0"
        return {
            "logical_id": f"ddr:{generation}:mc{controller}:ch{channel}:rk{rank}:by{byte}:{signal}:{suffix}",
            "group": source_group or f"M{controller}",
            "signal_type": source_signal_type or (f"DIFF_{polarity}" if polarity else signal),
            "partition": _partition(source_partition, endpoint_a, "CHIP_1"),
            "polarity": polarity,
            "segment": segment,
            "rule_id": "industry-ddr",
        }

    if family in {"pcie", "serdes"}:
        domain = _PCIE_DOMAIN if family == "pcie" else _SERDES_DOMAIN
        if domain.search(text) is None:
            return None
        structured = _SERDES_SDS_IO_DIE.fullmatch(text) if family == "serdes" else None
        if structured is not None:
            direction = structured.group("direction").upper()
            flow = structured.group("flow").upper()
            if (direction, flow) not in {("RX", "IN"), ("TX", "OUT")}:
                return None
            sds = str(int(structured.group("sds")))
            lane = str(int(structured.group("lane")))
            polarity = structured.group("polarity").upper()
            die = str(int(structured.group("die")))
            return {
                "logical_id": f"serdes:sds{sds}:die{die}:{direction}:{lane}:{polarity}",
                "group": source_group or f"SDS{sds}_{direction}{lane}",
                "signal_type": source_signal_type or f"DIFF_{polarity}",
                "partition": source_partition or f"{'DIE' if topology == 'pkg' else 'CHIP'}_{die}",
                "polarity": polarity,
                "segment": segment,
                "rule_id": "industry-serdes-sds-io-die",
            }
        identity = _direction_lane(text)
        polarity = _polarity(text)
        if identity is None or polarity not in {"P", "N"}:
            return None
        direction, lane = identity
        return {
            "logical_id": f"{family}:{direction}:{lane}:{polarity}",
            "group": source_group or f"{direction}{lane}",
            "signal_type": source_signal_type or f"DIFF_{polarity}",
            "partition": _partition(source_partition, endpoint_a, "CHIP_1"),
            "polarity": polarity,
            "segment": segment,
            "rule_id": f"industry-{family}",
        }

    if family == "pll_clk":
        if _CLOCK_DOMAIN.search(text) is None or _CLOCK_EXCLUDE.search(text) is not None:
            return None
        polarity = _polarity(text)
        if polarity not in {"P", "N"}:
            return None
        base = re.sub(r"(?:_D?[PN]|_[PN][0-9]*)$", "", text)
        base = re.sub(r"_(?:T|C)$", "", base)
        if not base:
            return None
        group = source_group or base
        return {
            "logical_id": f"pll_clk:{base}:{polarity}",
            "group": group,
            "signal_type": source_signal_type or f"DIFF_{polarity}",
            "partition": _partition(source_partition, endpoint_a, "CHIP_1"),
            "polarity": polarity,
            "segment": segment,
            "rule_id": "industry-pll-clk",
        }
    return None


def recognized(name: str, family: str) -> bool:
    """Lightweight classifier evidence independent of endpoint information."""
    result = identify(
        name=name,
        family=family,
        topology="pcb",
        endpoint_a=["AUTO.0"],
    )
    return result is not None


__all__ = ["identify", "recognized"]
