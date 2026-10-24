"""Millimetre and mil conversions for Altium .RUL length fields.

Altium stores rule lengths as mil text (``3.9370mil``) and object-clearance
overrides as integer internal units, where 1 mil = 10 000 units.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

MM_PER_MIL = Decimal("0.0254")
INTERNAL_PER_MIL = Decimal(10000)

_MIL = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*mil$", re.IGNORECASE)
_MM = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*mm$", re.IGNORECASE)
_NUM = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")

# Global field is spelled PREFEREDWIDTH in Altium exports. Layer fields use PREFWIDTH.
_LENGTH_KEYS = {
    "GAP",
    "GENERICCLEARANCE",
    "CLEARANCE",
    "MINIMUMRING",
    "HOLEWIDTH",
    "WIDTH",
    "MINHOLEWIDTH",
    "MINWIDTH",
    "MAXHOLEWIDTH",
    "MAXWIDTH",
    "MAXLIMIT",
    "MINLIMIT",
    "PREFEREDWIDTH",
    "RELIEFEXPANSION",
    "RELIEFCONDUCTORWIDTH",
    "RELIEFAIRGAP",
    "AIRGAPWIDTH",
    "EXPANSION",
    "MINSOLDERMASKWIDTH",
    "MINSILKSCREENTOMASKGAP",
    "SILKTOSILKCLEARANCE",
    "NETANTENNAETOLERANCE",
    "MINSETBACK",
    "MAXSETBACK",
}

_BOOL_KEYS = {
    "SELECTION",
    "LOCKED",
    "POLYGONOUTLINE",
    "USERROUTED",
    "KEEPOUT",
    "ENABLED",
    "DEFINEDBYLOGICALDOCUMENT",
    "IGNOREPADTOPADCLEARANCEINFOOTPRINT",
    "ISTENTINGTOP",
    "ALLOWED",
    "ABSOLUTEVALUES",
    "ENFORCE",
    "ALLOWSTACKEDMICROVIAS",
    "CLEARANCETOEXPOSEDCOPPER",
}


def is_length_key(key: str) -> bool:
    if key in _LENGTH_KEYS:
        return True
    return key.endswith(("_MINWIDTH", "_MAXWIDTH", "_PREFWIDTH"))


def is_bool_key(key: str) -> bool:
    return key in _BOOL_KEYS or key.endswith("_V5")


def is_percent_key(key: str) -> bool:
    return key in {"MAXPERCENT", "MINPERCENT"}


def parse_length(text: str, plain_is_mm: bool = False) -> Decimal | None:
    """Parse a stored or typed length into millimetres."""
    raw = text.strip()
    match = _MIL.match(raw)
    if match:
        return Decimal(match.group(1)) * MM_PER_MIL
    match = _MM.match(raw)
    if match:
        return Decimal(match.group(1))
    if plain_is_mm and _NUM.match(raw):
        return Decimal(raw)
    return None


def format_mil(mm: Decimal) -> str:
    mil = (mm / MM_PER_MIL).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return format(mil, "f") + "mil"


def format_mm(mm: Decimal, places: str = "0.0001") -> str:
    shown = mm.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    return format(shown, "f")


def length_mil(text: str) -> Decimal | None:
    mm = parse_length(text)
    if mm is None:
        return None
    return (mm / MM_PER_MIL).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def lengths_equal(left: str, right: str) -> bool:
    a = length_mil(left)
    b = length_mil(right)
    if a is None or b is None:
        return left.strip() == right.strip()
    return a == b


def display_mm(text: str) -> str | None:
    mm = parse_length(text)
    if mm is None:
        return None
    return format_mm(mm)


def mm_to_internal(mm: Decimal) -> int:
    mil = (mm / MM_PER_MIL).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return int((mil * INTERNAL_PER_MIL).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def internal_to_mm(value: int) -> Decimal:
    mil = Decimal(value) / INTERNAL_PER_MIL
    return mil * MM_PER_MIL


CLEARANCE_PREFIX = "ClearanceObj_"


def parse_object_clearances(text: str) -> list[tuple[str, str, str]]:
    """Parse ``ClearanceObj_A-ClearanceObj_B:118110`` pairs.

    The third item is the raw internal-unit token so an unchanged rule can
    be written back exactly.
    """
    body = text.strip()
    if not body:
        return []
    rows: list[tuple[str, str, str]] = []
    for item in body.split(";"):
        item = item.strip()
        if not item:
            continue
        pair, separator, token = item.partition(":")
        if not separator:
            rows.append((item, "", ""))
            continue
        left, dash, right = pair.partition("-")
        if not dash:
            rows.append((pair, "", token))
            continue
        rows.append((_strip_object(left), _strip_object(right), token.strip()))
    return rows


def serialize_object_clearances(rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return " "
    parts = []
    for left, right, token in rows:
        parts.append(f"{_object_name(left)}-{_object_name(right)}:{token}")
    return ";".join(parts)


def object_clearance_mm(token: str) -> Decimal | None:
    try:
        return internal_to_mm(int(Decimal(token)))
    except Exception:
        return None


def _strip_object(name: str) -> str:
    name = name.strip()
    if name.startswith(CLEARANCE_PREFIX):
        return name[len(CLEARANCE_PREFIX) :]
    return name


def _object_name(name: str) -> str:
    name = name.strip()
    if name.startswith(CLEARANCE_PREFIX):
        return name
    return CLEARANCE_PREFIX + name


def format_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def parse_bool(text: str) -> bool | None:
    token = text.strip().lower()
    if token in {"true", "yes", "1", "on"}:
        return True
    if token in {"false", "no", "0", "off"}:
        return False
    return None
