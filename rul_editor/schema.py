"""Field metadata and factories for Altium PCB rule kinds."""

from __future__ import annotations

from dataclasses import dataclass

from rul_editor.units import (
    display_mm,
    format_mm,
    is_length_key,
    lengths_equal,
    object_clearance_mm,
    parse_length,
    parse_object_clearances,
)

HEADER_KEYS = (
    "SELECTION",
    "LAYER",
    "LOCKED",
    "POLYGONOUTLINE",
    "USERROUTED",
    "KEEPOUT",
    "UNIONINDEX",
    "RULEKIND",
    "NETSCOPE",
    "LAYERKIND",
    "SCOPE1EXPRESSION",
    "SCOPE2EXPRESSION",
    "NAME",
    "ENABLED",
    "PRIORITY",
    "COMMENT",
    "UNIQUEID",
    "DEFINEDBYLOGICALDOCUMENT",
)

KIND_ORDER = (
    "Clearance",
    "Width",
    "RoutingVias",
    "RoutingCorners",
    "RoutingLayers",
    "RoutingTopology",
    "HoleSize",
    "HoleToHoleClearance",
    "MinimumAnnularRing",
    "PlaneClearance",
    "PlaneConnect",
    "PolygonConnect",
    "SolderMaskExpansion",
    "PasteMaskExpansion",
    "MinimumSolderMaskSliver",
    "SilkToSolderMaskClearance",
    "SilkToSilkClearance",
    "BoardOutlineClearance",
    "ShortCircuit",
    "UnRoutedNet",
    "LayerPairs",
    "NetAntennae",
)

LAYER_PREFIXES = (
    ["TOPLAYER"]
    + [f"MIDLAYER{index}" for index in range(1, 31)]
    + ["BOTTOMLAYER"]
)
LAYER_TITLES = (
    ["Top"]
    + [f"Mid {index}" for index in range(1, 31)]
    + ["Bottom"]
)

CLEARANCE_OBJECTS = (
    "Arc",
    "Track",
    "SMDPad",
    "THPad",
    "Via",
    "Fill",
    "Poly",
    "Region",
    "Text",
    "Hole",
)

# Kinds whose generic clearance is kept equal to GAP from the form.
CLEARANCE_KINDS = {"Clearance", "BoardOutlineClearance"}


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    editor: str  # length, bool, enum, int, percent, text
    choices: tuple[str, ...] = ()


NET_SCOPE_CHOICES = ("AnyNet", "SameNet", "DifferentNets")
LAYER_KIND_CHOICES = ("SameLayer",)
CONNECT_CHOICES = ("Direct", "Relief", "None")
PLANE_CHOICES = ("Direct", "Relief")
VIA_CHOICES = ("Through Hole", "Blind", "Buried")
CORNER_CHOICES = ("45-Degree", "90-Degree", "Rounded")
TOPOLOGY_CHOICES = (
    "Shortest",
    "Horizontal",
    "Vertical",
    "Daisy-Simple",
    "Daisy-MidDriven",
    "Daisy-Balanced",
    "Starburst",
)
ANGLE_CHOICES = ("90 Angle", "45 Angle")


def routing_layer_key(title: str) -> str:
    if title == "Top":
        return "TOP LAYER_V5"
    if title == "Bottom":
        return "BOTTOM LAYER_V5"
    index = title.split()[-1]
    return f"MID LAYER {index}_V5"


ROUTING_LAYER_KEYS = tuple(routing_layer_key(title) for title in LAYER_TITLES)


def _spec(key: str, label: str, editor: str, choices: tuple[str, ...] = ()) -> FieldSpec:
    return FieldSpec(key, label, editor, choices)


_CLEARANCE_FIELDS = (
    _spec("GAP", "Gap", "length"),
    _spec("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "Ignore pad-to-pad clearance in footprint", "bool"),
)
_WIDTH_FIELDS = (
    _spec("MINLIMIT", "Minimum", "length"),
    _spec("PREFEREDWIDTH", "Preferred", "length"),
    _spec("MAXLIMIT", "Maximum", "length"),
)
_VIA_FIELDS = (
    _spec("HOLEWIDTH", "Preferred hole", "length"),
    _spec("WIDTH", "Preferred diameter", "length"),
    _spec("VIASTYLE", "Via style", "enum", VIA_CHOICES),
    _spec("MINHOLEWIDTH", "Minimum hole", "length"),
    _spec("MINWIDTH", "Minimum diameter", "length"),
    _spec("MAXHOLEWIDTH", "Maximum hole", "length"),
    _spec("MAXWIDTH", "Maximum diameter", "length"),
)
_HOLE_FIELDS = (
    _spec("ABSOLUTEVALUES", "Absolute hole size", "bool"),
    _spec("MINLIMIT", "Minimum", "length"),
    _spec("MAXLIMIT", "Maximum", "length"),
    _spec("MINPERCENT", "Minimum percent", "percent"),
    _spec("MAXPERCENT", "Maximum percent", "percent"),
)
_RING_FIELDS = (_spec("MINIMUMRING", "Minimum annular ring", "length"),)
_PLANE_CLEARANCE_FIELDS = (_spec("CLEARANCE", "Clearance", "length"),)
_PLANE_CONNECT_FIELDS = (
    _spec("PLANECONNECTSTYLE", "Connect style", "enum", PLANE_CHOICES),
    _spec("RELIEFEXPANSION", "Relief expansion", "length"),
    _spec("RELIEFENTRIES", "Relief entries", "int"),
    _spec("RELIEFCONDUCTORWIDTH", "Conductor width", "length"),
    _spec("RELIEFAIRGAP", "Air gap", "length"),
)
_POLYGON_FIELDS = (
    _spec("CONNECTSTYLE", "Connect style", "enum", CONNECT_CHOICES),
    _spec("RELIEFCONDUCTORWIDTH", "Conductor width", "length"),
    _spec("RELIEFENTRIES", "Relief entries", "int"),
    _spec("POLYGONRELIEFANGLE", "Relief angle", "enum", ANGLE_CHOICES),
    _spec("AIRGAPWIDTH", "Air gap", "length"),
)
_MASK_FIELDS = (
    _spec("EXPANSION", "Expansion", "length"),
    _spec("ISTENTINGTOP", "Tent vias on top", "bool"),
)
_PASTE_FIELDS = (_spec("EXPANSION", "Expansion", "length"),)
_SLIVER_FIELDS = (_spec("MINSOLDERMASKWIDTH", "Minimum solder-mask sliver", "length"),)
_SILK_MASK_FIELDS = (
    _spec("MINSILKSCREENTOMASKGAP", "Silk to mask gap", "length"),
    _spec("CLEARANCETOEXPOSEDCOPPER", "Clearance to exposed copper", "bool"),
)
_SILK_SILK_FIELDS = (_spec("SILKTOSILKCLEARANCE", "Silk to silk clearance", "length"),)
_HOLE_TO_HOLE_FIELDS = (
    _spec("GAP", "Gap", "length"),
    _spec("ALLOWSTACKEDMICROVIAS", "Allow stacked microvias", "bool"),
)
_CORNER_FIELDS = (
    _spec("CORNERSTYLE", "Corner style", "enum", CORNER_CHOICES),
    _spec("MINSETBACK", "Minimum setback", "length"),
    _spec("MAXSETBACK", "Maximum setback", "length"),
)
_TOPOLOGY_FIELDS = (_spec("TOPOLOGY", "Topology", "enum", TOPOLOGY_CHOICES),)
_SHORT_FIELDS = (_spec("ALLOWED", "Allow short circuit", "bool"),)
_PAIR_FIELDS = (_spec("ENFORCE", "Enforce layer pairs", "bool"),)
_ANTENNA_FIELDS = (_spec("NETANTENNAETOLERANCE", "Antenna tolerance", "length"),)

KIND_FIELDS: dict[str, tuple[FieldSpec, ...]] = {
    "Clearance": _CLEARANCE_FIELDS,
    "BoardOutlineClearance": _CLEARANCE_FIELDS,
    "Width": _WIDTH_FIELDS,
    "RoutingVias": _VIA_FIELDS,
    "HoleSize": _HOLE_FIELDS,
    "MinimumAnnularRing": _RING_FIELDS,
    "PlaneClearance": _PLANE_CLEARANCE_FIELDS,
    "PlaneConnect": _PLANE_CONNECT_FIELDS,
    "PolygonConnect": _POLYGON_FIELDS,
    "SolderMaskExpansion": _MASK_FIELDS,
    "PasteMaskExpansion": _PASTE_FIELDS,
    "MinimumSolderMaskSliver": _SLIVER_FIELDS,
    "SilkToSolderMaskClearance": _SILK_MASK_FIELDS,
    "SilkToSilkClearance": _SILK_SILK_FIELDS,
    "HoleToHoleClearance": _HOLE_TO_HOLE_FIELDS,
    "RoutingCorners": _CORNER_FIELDS,
    "RoutingTopology": _TOPOLOGY_FIELDS,
    "RoutingLayers": (),
    "ShortCircuit": _SHORT_FIELDS,
    "UnRoutedNet": (),
    "LayerPairs": _PAIR_FIELDS,
    "NetAntennae": _ANTENNA_FIELDS,
}

# Altium's usual parameter order, used when creating a rule.
_KIND_TAIL: dict[str, tuple[tuple[str, str], ...]] = {
    "Clearance": (
        ("GAP", "3.9370mil"),
        ("GENERICCLEARANCE", "3.9370mil"),
        ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
        ("OBJECTCLEARANCES", " "),
    ),
    "BoardOutlineClearance": (
        ("GAP", "7.8740mil"),
        ("GENERICCLEARANCE", "7.8740mil"),
        ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
        ("OBJECTCLEARANCES", " "),
    ),
    "RoutingVias": (
        ("HOLEWIDTH", "11.8110mil"),
        ("WIDTH", "23.6220mil"),
        ("VIASTYLE", "Through Hole"),
        ("MINHOLEWIDTH", "7.8740mil"),
        ("MINWIDTH", "15.7480mil"),
        ("MAXHOLEWIDTH", "248.0315mil"),
        ("MAXWIDTH", "393.7008mil"),
    ),
    "HoleSize": (
        ("ABSOLUTEVALUES", "TRUE"),
        ("MAXLIMIT", "248.0315mil"),
        ("MINLIMIT", "7.8740mil"),
        ("MAXPERCENT", "80.000"),
        ("MINPERCENT", "20.000"),
    ),
    "MinimumAnnularRing": (("MINIMUMRING", "3.9370mil"),),
    "PlaneClearance": (("CLEARANCE", "7.8740mil"),),
    "PlaneConnect": (
        ("PLANECONNECTSTYLE", "Relief"),
        ("RELIEFEXPANSION", "7.8740mil"),
        ("RELIEFENTRIES", "4"),
        ("RELIEFCONDUCTORWIDTH", "5.9055mil"),
        ("RELIEFAIRGAP", "4.9213mil"),
    ),
    "PolygonConnect": (
        ("CONNECTSTYLE", "Direct"),
        ("RELIEFCONDUCTORWIDTH", "7.8740mil"),
        ("RELIEFENTRIES", "4"),
        ("POLYGONRELIEFANGLE", "90 Angle"),
        ("AIRGAPWIDTH", "3.9370mil"),
    ),
    "SolderMaskExpansion": (("EXPANSION", "0mil"), ("ISTENTINGTOP", "FALSE")),
    "PasteMaskExpansion": (("EXPANSION", "0mil"),),
    "MinimumSolderMaskSliver": (("MINSOLDERMASKWIDTH", "3.9370mil"),),
    "SilkToSolderMaskClearance": (
        ("MINSILKSCREENTOMASKGAP", "3.9370mil"),
        ("CLEARANCETOEXPOSEDCOPPER", "TRUE"),
    ),
    "SilkToSilkClearance": (("SILKTOSILKCLEARANCE", "0mil"),),
    "HoleToHoleClearance": (("GAP", "7.8740mil"), ("ALLOWSTACKEDMICROVIAS", "FALSE")),
    "RoutingCorners": (
        ("CORNERSTYLE", "45-Degree"),
        ("MINSETBACK", "100mil"),
        ("MAXSETBACK", "100mil"),
    ),
    "RoutingTopology": (("TOPOLOGY", "Shortest"),),
    "ShortCircuit": (("ALLOWED", "FALSE"),),
    "UnRoutedNet": (),
    "LayerPairs": (("ENFORCE", "TRUE"),),
    "NetAntennae": (("NETANTENNAETOLERANCE", "0mil"),),
}


def width_tail(min_mil: str = "3.9370mil", pref_mil: str = "5.9055mil", max_mil: str = "393.7008mil") -> tuple[tuple[str, str], ...]:
    items = [("MAXLIMIT", max_mil), ("MINLIMIT", min_mil), ("PREFEREDWIDTH", pref_mil)]
    for prefix in LAYER_PREFIXES:
        items.append((f"{prefix}_MINWIDTH", min_mil))
        items.append((f"{prefix}_MAXWIDTH", max_mil))
        items.append((f"{prefix}_PREFWIDTH", pref_mil))
    return tuple(items)


def routing_tail() -> tuple[tuple[str, str], ...]:
    return tuple((key, "TRUE") for key in ROUTING_LAYER_KEYS)


def kind_tail(kind: str) -> tuple[tuple[str, str], ...]:
    if kind == "Width":
        return width_tail()
    if kind == "RoutingLayers":
        return routing_tail()
    if kind not in _KIND_TAIL:
        raise KeyError(kind)
    return _KIND_TAIL[kind]


def known_kinds() -> tuple[str, ...]:
    return KIND_ORDER


def fields_for(kind: str) -> tuple[FieldSpec, ...]:
    return KIND_FIELDS.get(kind, ())


def special_keys(kind: str) -> set[str]:
    keys = set(HEADER_KEYS)
    if kind in CLEARANCE_KINDS:
        keys.add("GENERICCLEARANCE")
        keys.add("OBJECTCLEARANCES")
    if kind == "Width":
        for prefix in LAYER_PREFIXES:
            keys.add(f"{prefix}_MINWIDTH")
            keys.add(f"{prefix}_MAXWIDTH")
            keys.add(f"{prefix}_PREFWIDTH")
    if kind == "RoutingLayers":
        keys.update(ROUTING_LAYER_KEYS)
    return keys


def kind_sort_key(kind: str) -> tuple[int, str]:
    try:
        return (KIND_ORDER.index(kind), kind)
    except ValueError:
        return (len(KIND_ORDER), kind)


def _mm(rule, key: str) -> str | None:
    raw = rule.get(key)
    if raw is None or parse_length(raw) is None:
        return None
    return display_mm(raw)


def _clip(text: str, limit: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def summary_for(rule) -> str:
    kind = rule.kind
    if kind == "Width":
        text = _width_summary(rule)
    elif kind == "RoutingVias":
        text = _join_mm(
            (
                ("hole", "HOLEWIDTH"),
                ("dia", "WIDTH"),
                ("min hole", "MINHOLEWIDTH"),
                ("min dia", "MINWIDTH"),
            ),
            rule,
        )
    elif kind in CLEARANCE_KINDS or kind == "HoleToHoleClearance":
        text = _clearance_summary(rule)
    elif kind == "HoleSize":
        text = _span(rule, "MINLIMIT", "MAXLIMIT")
    elif kind == "RoutingLayers":
        enabled = sum(1 for key in ROUTING_LAYER_KEYS if (rule.get(key) or "").upper() == "TRUE")
        text = f"{enabled}/{len(ROUTING_LAYER_KEYS)} layers"
    elif kind == "ShortCircuit":
        text = "allowed" if (rule.get("ALLOWED") or "").upper() == "TRUE" else "not allowed"
    elif kind == "LayerPairs":
        text = "enforce" if (rule.get("ENFORCE") or "").upper() == "TRUE" else "do not enforce"
    elif kind == "UnRoutedNet":
        text = "unrouted nets"
    else:
        parts = []
        for spec in fields_for(kind):
            raw = rule.get(spec.key)
            if raw is None or raw.strip() == "":
                continue
            if spec.editor == "length":
                shown = display_mm(raw)
                if shown is not None:
                    parts.append(f"{spec.label.lower()} {shown} mm")
            elif spec.editor == "bool":
                parts.append(f"{spec.label.lower()} {'yes' if raw.upper() == 'TRUE' else 'no'}")
            elif spec.editor != "percent":
                parts.append(f"{spec.label.lower()} {raw}")
        text = ", ".join(parts)
    scope = _scope_summary(rule)
    if scope:
        text = f"{text}  [{scope}]" if text else scope
    if (rule.get("ENABLED") or "TRUE").upper() == "FALSE":
        text = (text + ", disabled") if text else "disabled"
    return text or kind


def _join_mm(pairs: tuple[tuple[str, str], ...], rule) -> str:
    bits = []
    for label, key in pairs:
        shown = _mm(rule, key)
        if shown is not None:
            bits.append(f"{label} {shown} mm")
    return ", ".join(bits)


def _span(rule, min_key: str, max_key: str) -> str:
    low = _mm(rule, min_key)
    high = _mm(rule, max_key)
    if low and high:
        return f"{low} .. {high} mm"
    return _join_mm((("min", min_key), ("max", max_key)), rule)


def _clearance_summary(rule) -> str:
    shown = _mm(rule, "GAP")
    text = f"gap {shown} mm" if shown else "gap"
    raw = rule.get("OBJECTCLEARANCES") or ""
    rows = parse_object_clearances(raw)
    if not rows:
        return text
    millis = []
    for _left, _right, token in rows:
        mm = object_clearance_mm(token)
        millis.append(format_mm(mm) if mm is not None else token)
    unique = set(millis)
    if len(unique) == 1:
        return f"{text}, object override {millis[0]} mm x{len(rows)}"
    return f"{text}, {len(rows)} object overrides"


def _width_summary(rule) -> str:
    pref = _mm(rule, "PREFEREDWIDTH")
    top = _mm(rule, "TOPLAYER_MINWIDTH") or _mm(rule, "MINLIMIT")
    inner = _mm(rule, "MIDLAYER1_MINWIDTH") or top
    bottom = _mm(rule, "BOTTOMLAYER_MINWIDTH") or top
    pref_bit = f", pref {pref} mm" if pref else ""
    if top and inner and bottom and top == inner == bottom:
        return f"min {top} mm{pref_bit}"
    if top and bottom and top == bottom and inner:
        return f"outer min {top} mm, inner min {inner} mm{pref_bit}"
    bits = []
    if top:
        bits.append(f"top {top}")
    if inner:
        bits.append(f"inner {inner}")
    if bottom:
        bits.append(f"bottom {bottom}")
    body = " / ".join(bits)
    return f"{body} mm{pref_bit}" if body else (f"pref {pref} mm" if pref else "width")


def _scope_summary(rule) -> str:
    left = (rule.get("SCOPE1EXPRESSION") or "All").strip()
    right = (rule.get("SCOPE2EXPRESSION") or "All").strip()
    if left == "All" and right == "All":
        return ""
    if right == "All":
        return _clip(left)
    return _clip(f"{left} | {right}")


def label_for(key: str) -> str:
    for specs in KIND_FIELDS.values():
        for spec in specs:
            if spec.key == key:
                return spec.label
    names = {
        "GENERICCLEARANCE": "Generic clearance",
        "OBJECTCLEARANCES": "Object clearances",
        "SCOPE1EXPRESSION": "Scope 1",
        "SCOPE2EXPRESSION": "Scope 2",
        "NETSCOPE": "Net scope",
        "LAYERKIND": "Layer kind",
        "COMMENT": "Comment",
        "PRIORITY": "Priority",
        "UNIQUEID": "Unique ID",
        "NAME": "Name",
        "ENABLED": "Enabled",
    }
    return names.get(key, key)


def values_equal(key: str, left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if key == "OBJECTCLEARANCES":
        return _clearance_key(parse_object_clearances(left)) == _clearance_key(parse_object_clearances(right))
    if is_length_key(key):
        return lengths_equal(left, right)
    return left.strip() == right.strip()


def _clearance_key(rows: list[tuple[str, str, str]]) -> tuple:
    cooked = []
    for left, right, token in rows:
        mm = object_clearance_mm(token)
        if mm is None:
            cooked.append((left, right, token))
        else:
            cooked.append((left, right, format_mm(mm, "0.000001")))
    return tuple(cooked)
