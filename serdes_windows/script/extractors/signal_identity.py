"""Keep explicit PCIe and SerDes names separate and parse common SerDes forms.

The public extractors use one ordered filter registry from this module. A new
company naming form can therefore be added once without letting the PCB and
PKG implementations drift apart. The first entries preserve the qualified
legacy and N2009 behaviour; broader industry spellings are accepted only when
the net contains an explicit SerDes-domain token.
"""

from __future__ import annotations

import re


_PCIE = re.compile(r"PCIE", re.I)
_SERDES = re.compile(
    r"SERDES|(?:^|[^A-Z0-9])(?:SDS|HSS|HSIO|XFI|SFI|CEI|"
    r"KR|PHY|USB|SATA|UFS|ETH(?:ERNET)?)(?:\d+)?(?=$|[^A-Z0-9])",
    re.I,
)
_SDS_IO_DIE = re.compile(
    r"(?:^|[_\-.])SDS[_\-.]?(?P<sds>\d+)[_\-.]+"
    r"(?P<direction>TX|RX)[_\-.]?(?P<lane>\d{1,2})[_\-.]+"
    r"(?P<flow>IN|OUT)[_\-.]?(?P<polarity>P|N)"
    r"[_\-.]+D(?P<die>[1-5])$",
    re.I,
)

_DIE_SUFFIX = re.compile(r"(?:_|-|\.)D(?P<index>\d+)$", re.I)
_LEGACY_CHIP_SUFFIX = re.compile(r"(?:_|-|\.)G(?P<index>\d*)$", re.I)

# (id, expression, SDS policy, lane policy, explicit-domain required)
#
# The registry is deliberately ordered from the most specific form to the
# broadest form. This is the core extraction loop shared by PCB and PKG.
_SERDES_FILTERS = (
    (
        "numbered-sds",
        re.compile(
            r"(?:^|[_\-.])SDS[_\-.]?(?P<sds>\d+)[_\-.]+"
            r"(?P<direction>TX|RX)[_\-.]?(?P<lane>\d+)"
            r"[_\-.]+(?:IN|OUT|D)?[_\-.]?(?P<polarity>P|N)$",
            re.I,
        ),
        "capture",
        "capture",
        False,
    ),
    (
        "plain-sds",
        re.compile(
            r"(?:^|[_\-.])SDS[_\-.]+(?P<direction>TX|RX)"
            r"[_\-.]?(?P<lane>\d+)[_\-.]?(?P<polarity>P|N)$",
            re.I,
        ),
        "plain",
        "capture",
        False,
    ),
    (
        "legacy-direction-lane",
        re.compile(
            r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]?(?P<lane>\d+)"
            r"[_\-.]+(?P<polarity>P|N)$",
            re.I,
        ),
        "none",
        "capture",
        False,
    ),
    (
        "vector-polarity-lane",
        re.compile(
            r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]+D?"
            r"(?P<polarity>P|N)[<\[](?P<lane>\d+)[>\]]$",
            re.I,
        ),
        "none",
        "capture",
        False,
    ),
    (
        "domain-direction-lane",
        re.compile(
            r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]+(?:LANE[_\-.]?)?"
            r"(?P<lane>\d+)[_\-.]+D?(?P<polarity>P|N)$",
            re.I,
        ),
        "none",
        "capture",
        True,
    ),
    (
        "domain-lane-direction",
        re.compile(
            r"(?:^|[_\-.])LANE[_\-.]?(?P<lane>\d+)[_\-.]+"
            r"(?P<direction>TX|RX)[_\-.]+D?(?P<polarity>P|N)$",
            re.I,
        ),
        "none",
        "capture",
        True,
    ),
    (
        "domain-compact",
        re.compile(
            r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]?"
            r"(?P<lane>\d+)[_\-.]?D?(?P<polarity>P|N)$",
            re.I,
        ),
        "none",
        "capture",
        True,
    ),
    (
        "domain-polarity-lane",
        re.compile(
            r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]+D?"
            r"(?P<polarity>P|N)[_\-.]?(?P<lane>\d+)$",
            re.I,
        ),
        "none",
        "capture",
        True,
    ),
    (
        "legacy-no-lane",
        re.compile(
            r"(?:^|[_\-.])(?P<direction>TX|RX)[_\-.]+D?"
            r"(?P<polarity>P|N)$",
            re.I,
        ),
        "none",
        "zero",
        False,
    ),
)


def explicit_signal_family(name):
    text = str(name).strip()
    is_pcie = _PCIE.search(text) is not None
    is_serdes = _SERDES.search(text) is not None
    if is_pcie and is_serdes:
        return "ambiguous"
    if is_pcie:
        return "pcie"
    if is_serdes:
        return "serdes"
    return None


def accepts_signal_family(name, expected):
    expected = str(expected).strip().casefold()
    if expected not in {"pcie", "serdes"}:
        raise ValueError("Signal family must be pcie or serdes")
    explicit = explicit_signal_family(name)
    return explicit is None or explicit == expected


def parse_sds_io_die_name(name):
    """Parse ``SDS0_RX0_INN_D1`` style SerDes identities.

    The returned tuple is ``(sds, direction, lane, polarity, die)``.  Keeping
    SDS and DIE explicit prevents unrelated NS2009 channels from collapsing
    onto the same RX/TX lane identity in PCB, PKG, and merge preprocessing.
    """
    match = _SDS_IO_DIE.search(str(name).strip())
    if match is None:
        return None
    direction = match.group("direction").upper()
    flow = match.group("flow").upper()
    if (direction, flow) not in {("RX", "IN"), ("TX", "OUT")}:
        raise ValueError(
            "Structured SDS name has an unsupported direction/flow pair: "
            "{0}".format(name)
        )
    return (
        int(match.group("sds")),
        direction,
        int(match.group("lane")),
        match.group("polarity").upper(),
        int(match.group("die")),
    )


def parse_serdes_network_name(name):
    """Return ``(sds, direction, lane, polarity, partition)`` or ``None``.

    ``sds`` is an integer for ``SDS0`` style names, an empty string for the
    historical ``SDS_RX0P`` family, and ``None`` for generic SerDes names.
    ``partition`` is the one-based DIE/CHIP number encoded by ``_D#`` or the
    legacy ``_G#`` suffix. N2009 is parsed first so its DIE suffix is never
    mistaken for a legacy suffix.
    """
    clean = str(name).strip()
    if not clean or not accepts_signal_family(clean, "serdes"):
        return None

    structured = parse_sds_io_die_name(clean)
    if structured is not None:
        sds, direction, lane, polarity, partition = structured
        return sds, direction, lane, polarity, partition

    partition = 1
    classified = clean
    suffix = _DIE_SUFFIX.search(classified)
    if suffix is not None:
        partition = int(suffix.group("index"))
        classified = classified[: suffix.start()]
    else:
        suffix = _LEGACY_CHIP_SUFFIX.search(classified)
        if suffix is not None:
            partition = int(suffix.group("index") or "1") + 1
            classified = classified[: suffix.start()]
    if not 1 <= partition <= 5:
        raise ValueError(
            "SerDes DIE/CHIP suffix must resolve to partition 1..5: "
            "{0}".format(name)
        )

    explicit_domain = _SERDES.search(classified) is not None
    for _rule_id, expression, sds_policy, lane_policy, domain_required in _SERDES_FILTERS:
        if domain_required and not explicit_domain:
            continue
        match = expression.search(classified)
        if match is None:
            continue
        if sds_policy == "capture":
            sds = int(match.group("sds"))
        elif sds_policy == "plain":
            sds = ""
        else:
            sds = None
        lane = 0 if lane_policy == "zero" else int(match.group("lane"))
        if lane > 255:
            raise ValueError("SerDes lane index is outside 0..255: {0}".format(name))
        return (
            sds,
            match.group("direction").upper(),
            lane,
            match.group("polarity").upper(),
            partition,
        )
    return None


__all__ = [
    "accepts_signal_family",
    "explicit_signal_family",
    "parse_serdes_network_name",
    "parse_sds_io_die_name",
]
