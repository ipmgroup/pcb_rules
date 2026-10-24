"""Export an Altium .RUL document to a KiCad custom-rules file.

KiCad evaluates custom rules from the bottom of the file upward. The last
matching rule of a given constraint wins, so Altium priority 1 is written last.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from rul_editor.schema import LAYER_TITLES, ROUTING_LAYER_KEYS
from rul_editor.units import (
    format_mm,
    length_mil,
    lengths_equal,
    object_clearance_mm,
    parse_bool,
    parse_length,
    parse_object_clearances,
)

_INTRO = (
    "KiCad reads custom rules from the bottom up, so Altium priority 1 is written last.",
    "Custom rules are DRC checks. The interactive router uses opt track width and opt via size when a rule matches.",
)

_SKIPPED_KINDS = {
    "RoutingCorners": "corner style is a router preference",
    "RoutingTopology": "topology is a router preference",
    "UnRoutedNet": "KiCad already checks unconnected items",
    "LayerPairs": "KiCad has no layer-pair constraint",
    "NetAntennae": "KiCad has no net-antenna constraint",
}

_ZONE_STYLE = {
    "direct": "solid",
    "relief": "thermal_reliefs",
    "none": "none",
    "no connect": "none",
}

_RENDER = {
    "isvia": "{o}.Type == 'Via'",
    "istrack": "({o}.Type == 'Track' || {o}.Type == 'Arc')",
    "isarc": "{o}.Type == 'Arc'",
    "ispad": "{o}.Type == 'Pad'",
    "istext": "{o}.Type == 'Text'",
    "isfill": "{o}.Type == 'Zone'",
    "ispoly": "{o}.Type == 'Zone'",
    "isregion": "{o}.Type == 'Zone'",
    "onmultilayer": "({o}.Type == 'Via' || {o}.Pad_Type == 'Through-hole' || {o}.Pad_Type == 'NPTH, mechanical')",
    "ispadholevalid": "({o}.Type == 'Via' || ({o}.Type == 'Pad' && {o}.Pad_Type != 'SMD'))",
    "padisplated": "{o}.isPlated()",
    "notpadisplated": "!{o}.isPlated()",
    "hole0": "({o}.Type == 'Pad' && {o}.Pad_Type == 'SMD')",
}

_OBJECT_EXPR = {
    "arc": "{o}.Type == 'Arc'",
    "track": "{o}.Type == 'Track'",
    "smdpad": "{o}.Type == 'Pad' && {o}.Pad_Type == 'SMD'",
    "thpad": "{o}.Type == 'Pad' && {o}.Pad_Type == 'Through-hole'",
    "via": "{o}.Type == 'Via'",
    "fill": "{o}.Type == 'Zone'",
    "poly": "{o}.Type == 'Zone'",
    "region": "{o}.Type == 'Zone'",
    "text": "{o}.Type == 'Text'",
}
_ALL_COPPER = frozenset(_OBJECT_EXPR)

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_LAYERS = {"onmid": "inner", "onouter": "outer", "ontop": "F.Cu", "onbottom": "B.Cu"}


class ScopeError(Exception):
    pass


class _Skip:
    pass


_SKIP = _Skip()


@dataclass
class Scope:
    ok: bool = True
    layer: str | None = None
    expr: str | None = None
    error: str = ""


@dataclass
class OutRule:
    name: str
    priority: int
    specificity: int
    rank: int
    sequence: int
    layer: str | None
    constraints: list[str]
    condition: str | None


class ExportResult:
    def __init__(self, text: str, notes: list[str], rule_count: int):
        self.text = text
        self.notes = notes
        self.rule_count = rule_count


def export_document(document) -> ExportResult:
    return _Exporter(document).build()


def translate_scope(text: str | None) -> Scope:
    """Translate one Altium scope expression. ``expr`` uses ``{o}`` for the object."""
    raw = (text or "").strip() or "All"
    try:
        node = _Parser(raw).parse()
    except ScopeError as exc:
        return Scope(False, error=str(exc))
    return _compile(node)


def _enabled(rule) -> bool:
    return (rule.get("ENABLED") or "TRUE").upper() == "TRUE"


def mm_token(text: str | None) -> str | None:
    mm = quant_mm(text)
    if mm is None:
        return None
    return format_mm(mm) + "mm"


def quant_mm(text: str | None) -> Decimal | None:
    if text is None or not str(text).strip():
        return None
    mm = parse_length(str(text))
    if mm is None:
        return None
    return mm.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def is_unlimited(text: str | None) -> bool:
    if text is None or not str(text).strip():
        return False
    mil = length_mil(str(text))
    return mil is not None and mil >= Decimal("390")


def _dq(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _sq(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _apply(expr: str, obj: str) -> str:
    return expr.replace("{o}", obj)


def and_cond(left: str | None, right: str | None) -> str | None:
    if not left:
        return right
    if not right:
        return left
    if left == right:
        return left
    return f"({left}) && ({right})"


def _layer_clause(layer: str) -> str:
    if layer in ("inner", "outer"):
        return f"(layer {layer})"
    return "(layer " + _dq(layer) + ")"


def _contains(group: str, specific: str) -> bool:
    if group == "inner":
        return specific.startswith("In") and specific.endswith(".Cu")
    if group == "outer":
        return specific in {"F.Cu", "B.Cu"}
    return False


def resolve_layer(scope_layer: str | None, group_layer: str | None):
    if scope_layer is None:
        return group_layer
    if group_layer is None:
        return scope_layer
    if scope_layer == group_layer:
        return group_layer
    if _contains(scope_layer, group_layer):
        return group_layer
    if _contains(group_layer, scope_layer):
        return scope_layer
    return _SKIP


def _scope_key(text: str | None) -> str:
    return " ".join((text or "All").split()).lower()


def _copper_layer(title: str) -> str:
    if title == "Top":
        return "F.Cu"
    if title == "Bottom":
        return "B.Cu"
    return f"In{title.split()[-1]}.Cu"


def _triple(rule, prefix: str) -> tuple[str | None, str | None, str | None]:
    return (
        rule.get(f"{prefix}_MINWIDTH") or rule.get("MINLIMIT"),
        rule.get(f"{prefix}_PREFWIDTH") or rule.get("PREFEREDWIDTH"),
        rule.get(f"{prefix}_MAXWIDTH") or rule.get("MAXLIMIT"),
    )


def _same_triple(left, right) -> bool:
    return all(lengths_equal((a or "").strip(), (b or "").strip()) for a, b in zip(left, right))


def width_groups(rule) -> list[tuple[str | None, tuple]]:
    top = _triple(rule, "TOPLAYER")
    bottom = _triple(rule, "BOTTOMLAYER")
    mids = [_triple(rule, f"MIDLAYER{index}") for index in range(1, 31)]
    if all(_same_triple(mid, mids[0]) for mid in mids):
        inner = mids[0]
        if _same_triple(top, bottom) and _same_triple(top, inner):
            return [(None, top)]
        if _same_triple(top, bottom):
            return [("outer", top), ("inner", inner)]
        return [("F.Cu", top), ("B.Cu", bottom), ("inner", inner)]
    groups = [("outer", top)] if _same_triple(top, bottom) else [("F.Cu", top), ("B.Cu", bottom)]
    for index, mid in enumerate(mids, start=1):
        groups.append((f"In{index}.Cu", mid))
    return groups


class _Parser:
    def __init__(self, text: str):
        self.tokens = _tokenize(text)
        self.i = 0

    def peek(self):
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def pop(self):
        token = self.peek()
        if token is None:
            raise ScopeError("unexpected end of scope")
        self.i += 1
        return token

    def expect(self, kind: str) -> str:
        token = self.pop()
        if token[0] != kind:
            raise ScopeError(f"expected {kind}, found {token[1]!r}")
        return token[1]

    def parse(self):
        if not self.tokens:
            return ("id", "All")
        node = self._parse_or()
        if self.peek() is not None:
            raise ScopeError("unexpected text after the scope")
        return node

    def _parse_or(self):
        node = self._parse_and()
        while self.peek() and self.peek()[0] == "or":
            self.pop()
            node = ("or", node, self._parse_and())
        return node

    def _parse_and(self):
        node = self._parse_unary()
        while self.peek() and self.peek()[0] == "and":
            self.pop()
            node = ("and", node, self._parse_unary())
        return node

    def _parse_unary(self):
        if self.peek() and self.peek()[0] == "not":
            self.pop()
            return ("not", self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self):
        token = self.peek()
        if token is None:
            raise ScopeError("unexpected end of scope")
        if token[0] == "lp":
            self.pop()
            node = self._parse_or()
            self.expect("rp")
            return node
        if token[0] != "id":
            raise ScopeError(f"unexpected {token[1]!r}")
        ident = self.pop()[1]
        nxt = self.peek()
        if nxt and nxt[0] == "eq":
            self.pop()
            return ("cmp", ident, self.expect("num"))
        if nxt and nxt[0] == "lp":
            self.pop()
            arg = self.expect("str")
            self.expect("rp")
            return ("call", ident, arg)
        return ("id", ident)


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens = []
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "()":
            tokens.append(("lp" if char == "(" else "rp", char))
            index += 1
            continue
        if char == "=":
            tokens.append(("eq", "="))
            index += 1
            continue
        if char in "'\"":
            quote = char
            index += 1
            chars = []
            while index < size and text[index] != quote:
                if text[index] == "\\" and index + 1 < size:
                    chars.append(text[index + 1])
                    index += 2
                    continue
                chars.append(text[index])
                index += 1
            if index >= size:
                raise ScopeError("unterminated string in scope")
            index += 1
            tokens.append(("str", "".join(chars)))
            continue
        if char.isdigit():
            match = _NUM.match(text, index)
            tokens.append(("num", match.group(0)))
            index = match.end()
            continue
        match = _WORD.match(text, index)
        if not match:
            raise ScopeError(f"unexpected {char!r} in scope")
        word = match.group(0)
        index = match.end()
        if word.lower() in {"and", "or", "not"}:
            tokens.append((word.lower(), word))
        else:
            tokens.append(("id", word))
    return tokens


def _bad(message: str) -> Scope:
    return Scope(False, error=message)


def _flatten_and(node) -> list:
    if node[0] == "and":
        return _flatten_and(node[1]) + _flatten_and(node[2])
    return [node]


def _is_simple(node) -> bool:
    if node[0] in {"id", "call", "cmp"}:
        return True
    return node[0] == "not" and node[1][0] in {"id", "call", "cmp"}


def _render_leaf(node) -> str | None:
    if node[0] == "id":
        return _RENDER.get(node[1].lower())
    if node[0] == "call":
        arg = _sq(node[2])
        name = node[1].lower()
        if name == "innetclass":
            return "{o}.NetClass == " + arg
        if name == "innet":
            return "{o}.Net == " + arg
        return None
    if node[0] == "cmp" and node[1].lower() == "holediameter" and node[2] == "0":
        return _RENDER["hole0"]
    return None


def _compile_and(parts) -> Scope:
    names: set[str] = set()
    extras: list[str] = []
    for part in parts:
        if part[0] == "not":
            inner = part[1]
            if inner[0] == "id" and inner[1].lower() == "padisplated":
                names.add("notpadisplated")
                continue
            rendered = _render_leaf(inner)
            label = inner[1] if inner[0] in {"id", "call"} else "expression"
            if rendered is None:
                return _bad(f"cannot negate {label}")
            extras.append(f"!({rendered})")
            continue
        if part[0] == "id":
            names.add(part[1].lower())
            continue
        if part[0] == "call":
            rendered = _render_leaf(part)
            if rendered is None:
                return _bad(f"unknown scope function {part[1]}")
            extras.append(rendered)
            continue
        if part[0] == "cmp":
            if part[1].lower() == "holediameter" and part[2] == "0":
                names.add("hole0")
                continue
            return _bad(f"cannot translate {part[1]} = {part[2]}")
        return _bad("unsupported scope syntax")

    pieces: list[str] = []
    if {"ispad", "notpadisplated"} <= names and names & {"onmultilayer", "ispadholevalid"}:
        pieces.append("{o}.Type == 'Pad' && {o}.Pad_Type == 'NPTH, mechanical'")
        names -= {"ispad", "notpadisplated", "onmultilayer", "ispadholevalid"}
    elif {"ispad", "padisplated"} <= names and names & {"onmultilayer", "ispadholevalid"}:
        pieces.append("{o}.Type == 'Pad' && {o}.Pad_Type == 'Through-hole'")
        names -= {"ispad", "padisplated", "onmultilayer", "ispadholevalid"}
    elif {"ispad", "hole0"} <= names:
        pieces.append("{o}.Type == 'Pad' && {o}.Pad_Type == 'SMD'")
        names -= {"ispad", "hole0"}
    elif {"ispad", "onmultilayer"} <= names:
        pieces.append(
            "{o}.Type == 'Pad' && ({o}.Pad_Type == 'Through-hole' || {o}.Pad_Type == 'NPTH, mechanical')"
        )
        names -= {"ispad", "onmultilayer"}

    layer = None
    for token, value in _LAYERS.items():
        if token not in names:
            continue
        if layer and layer != value:
            return _bad("scope selects more than one layer group")
        layer = value
        names.remove(token)
    names.discard("all")
    for name in sorted(names):
        rendered = _RENDER.get(name)
        if rendered is None:
            return _bad(f"unknown scope term {name}")
        pieces.append(rendered)
    pieces.extend(extras)
    if not pieces:
        expr = None
    elif len(pieces) == 1:
        expr = pieces[0]
    else:
        expr = " && ".join(f"({piece})" for piece in pieces)
    return Scope(True, layer, expr)


def _merge_and(left: Scope, right: Scope) -> Scope:
    if not left.ok:
        return left
    if not right.ok:
        return right
    if left.layer and right.layer and left.layer != right.layer:
        return _bad("scope selects more than one layer group")
    if left.expr and right.expr:
        expr = f"({left.expr}) && ({right.expr})"
    else:
        expr = left.expr or right.expr
    return Scope(True, left.layer or right.layer, expr)


def _merge_or(left: Scope, right: Scope) -> Scope:
    if not left.ok:
        return left
    if not right.ok:
        return right
    if left.layer or right.layer:
        return _bad("a layer test combined with Or has no KiCad layer clause")
    if not left.expr or not right.expr:
        return Scope(True)
    return Scope(True, expr=f"({left.expr}) || ({right.expr})")


def _compile(node) -> Scope:
    kind = node[0]
    if kind == "or":
        return _merge_or(_compile(node[1]), _compile(node[2]))
    if kind == "and":
        parts = _flatten_and(node)
        if all(_is_simple(part) for part in parts):
            return _compile_and(parts)
        acc = None
        for part in parts:
            piece = _compile(part)
            acc = piece if acc is None else _merge_and(acc, piece)
        return acc if acc is not None else _bad("empty scope")
    if kind == "not":
        if _is_simple(node):
            return _compile_and([node])
        inner = _compile(node[1])
        if not inner.ok:
            return inner
        if inner.layer or not inner.expr:
            return _bad("Not cannot be applied to this scope")
        return Scope(True, expr=f"!({inner.expr})")
    return _compile_and([node])


def combine_scopes(left: Scope, right: Scope, binary: bool) -> tuple[str | None, str | None, str | None]:
    if not left.ok:
        return None, None, left.error or "could not translate the first scope"
    if not right.ok:
        return None, None, right.error or "could not translate the second scope"
    if left.layer and right.layer and left.layer != right.layer:
        return None, None, "the two scopes select different layers"
    layer = left.layer or right.layer
    if not binary:
        parts = [_apply(scope.expr, "A") for scope in (left, right) if scope.expr]
        condition = " && ".join(f"({part})" for part in parts) if parts else None
        return layer, condition, None
    return layer, _binary_condition(left.expr, right.expr), None


def _binary_condition(left: str | None, right: str | None) -> str | None:
    if left is None and right is None:
        return None
    if left is None:
        one = _apply(right or "", "A")
        other = _apply(right or "", "B")
        if one == other:
            return one
        return f"({one}) || ({other})"
    if right is None:
        return _binary_condition(None, left)
    if left == right:
        return f"({_apply(left, 'A')}) && ({_apply(left, 'B')})"
    return (
        f"(({_apply(left, 'A')}) && ({_apply(right, 'B')})) || "
        f"(({_apply(left, 'B')}) && ({_apply(right, 'A')}))"
    )


def _broad_gaps(document) -> tuple[Decimal | None, Decimal | None]:
    all_gap = None
    inner_gap = None
    for rule in document.rules:
        if rule.kind != "Clearance" or not _enabled(rule):
            continue
        if (rule.get("NETSCOPE") or "").strip() != "DifferentNets":
            continue
        pair = {_scope_key(rule.get("SCOPE1EXPRESSION")), _scope_key(rule.get("SCOPE2EXPRESSION"))}
        if pair == {"all"}:
            slot = "all"
        elif "onmid" in pair and pair <= {"all", "onmid"}:
            slot = "inner"
        else:
            continue
        gap = quant_mm(rule.get("GAP"))
        if gap is None:
            continue
        current = all_gap if slot == "all" else inner_gap
        if current is None or rule.priority < current[0]:
            current = (rule.priority, gap)
        if slot == "all":
            all_gap = current
        else:
            inner_gap = current
    return (
        None if all_gap is None else all_gap[1],
        None if inner_gap is None else inner_gap[1],
    )


class _Exporter:
    def __init__(self, document):
        self.document = document
        self.rules: list[OutRule] = []
        self.detail: list[str] = []
        self.skipped: list[tuple[str, str]] = []
        self.unlimited: set[str] = set()
        self.sequence = 0
        self.silk_mask = False
        self.silk_silk = False
        self.zone_styles: dict[str, str] = {}
        self.all_gap, self.inner_gap = _broad_gaps(document)

    def build(self) -> ExportResult:
        for rule in self.document.rules:
            if not _enabled(rule):
                self.detail.append(f"Skipped disabled rule {rule.name} ({rule.kind}).")
                continue
            self._dispatch(rule)
        return ExportResult(self._render(), self._notes(), len(self.rules))

    def _notes(self) -> list[str]:
        notes = list(_INTRO)
        if self.skipped:
            body = "; ".join(f"{kind} ({reason})" for kind, reason in self.skipped)
            notes.append("Not exported: " + body + ".")
        if self.unlimited:
            names = ", ".join(sorted(self.unlimited))
            notes.append(f"Altium's unlimited maximum (10 mm) was left open for: {names}.")
        if self.silk_mask and self.silk_silk:
            notes.append(
                "Silk-to-mask and silk-to-silk share KiCad's silk_clearance constraint. "
                "The later rule wins where both match."
            )
        plane = self.zone_styles.get("plane")
        polygon = self.zone_styles.get("polygon")
        if plane and polygon and plane.lower() != polygon.lower():
            notes.append(
                f"PlaneConnect is {plane} and PolygonConnect is {polygon}. "
                "KiCad has one zone connection; the polygon rule is written last and applies to every zone."
            )
        notes.extend(self.detail)
        return notes

    def _render(self) -> str:
        ordered = sorted(self.rules, key=lambda item: (-item.priority, item.specificity, item.rank, item.sequence))
        used: set[str] = set()
        blocks = ["(version 1)"]
        for item in ordered:
            name = _unique_name(item.name, used)
            blocks.append(_render_rule(item, name))
        return "\n".join(blocks) + "\n"

    def add(
        self,
        name: str,
        priority: int,
        constraints: list[str],
        layer: str | None = None,
        condition: str | None = None,
        specificity: int = 0,
        rank: int = 0,
    ) -> None:
        kept = [item for item in constraints if item]
        if not kept:
            return
        self.rules.append(
            OutRule(
                (name or "rule").strip() or "rule",
                int(priority),
                specificity,
                rank,
                self.sequence,
                layer,
                kept,
                condition,
            )
        )
        self.sequence += 1

    def skip_kind(self, kind: str, reason: str) -> None:
        if any(item[0] == kind for item in self.skipped):
            return
        self.skipped.append((kind, reason))

    def _scopes(self, rule, binary: bool):
        raw1 = rule.get("SCOPE1EXPRESSION") or "All"
        raw2 = rule.get("SCOPE2EXPRESSION") or "All"
        layer, condition, error = combine_scopes(translate_scope(raw1), translate_scope(raw2), binary)
        if error:
            self.detail.append(
                f"{rule.name} ({rule.kind}): could not translate scope ({raw1!r} / {raw2!r}): {error}. "
                "The rule was not exported."
            )
            return None
        return layer, condition

    def _range(self, source: str, constraint: str, minimum, preferred, maximum) -> str:
        parts = []
        for key, text in (("min", minimum), ("opt", preferred), ("max", maximum)):
            if text is None or not str(text).strip():
                continue
            if key == "max" and is_unlimited(text):
                self.unlimited.add(source)
                continue
            token = mm_token(text)
            if token:
                parts.append(f"({key} {token})")
            else:
                self.detail.append(f"{source}: could not read {constraint} {key} value {text!r}.")
        if not parts:
            return ""
        return f"(constraint {constraint} {' '.join(parts)})"

    def _tighter(self, mm: Decimal, layer: str | None) -> bool:
        refs = []
        if layer == "inner" or (isinstance(layer, str) and layer.startswith("In")):
            refs.append(self.inner_gap if self.inner_gap is not None else self.all_gap)
        elif layer is None:
            refs.append(self.all_gap)
            refs.append(self.inner_gap)
        else:
            refs.append(self.all_gap)
        refs = [ref for ref in refs if ref is not None]
        if not refs:
            return True
        return all(mm > ref for ref in refs)

    def _dispatch(self, rule) -> None:
        kind = rule.kind
        if kind == "Clearance":
            self._clearance(rule, edge=False)
        elif kind == "BoardOutlineClearance":
            self._clearance(rule, edge=True)
        elif kind == "Width":
            self._width(rule)
        elif kind == "RoutingVias":
            self._vias(rule)
        elif kind == "HoleSize":
            self._hole_size(rule)
        elif kind == "MinimumAnnularRing":
            self._annular(rule)
        elif kind == "HoleToHoleClearance":
            self._hole_to_hole(rule)
        elif kind == "PlaneClearance":
            self._plane_clearance(rule)
        elif kind == "PlaneConnect":
            self._connect(rule, "plane")
        elif kind == "PolygonConnect":
            self._connect(rule, "polygon")
        elif kind == "SolderMaskExpansion":
            self._mask(rule)
        elif kind == "PasteMaskExpansion":
            self._paste(rule)
        elif kind == "MinimumSolderMaskSliver":
            self._sliver(rule)
        elif kind == "SilkToSolderMaskClearance":
            self._silk(rule, "MINSILKSCREENTOMASKGAP", "silk to mask")
        elif kind == "SilkToSilkClearance":
            self._silk(rule, "SILKTOSILKCLEARANCE", "silk to silk")
        elif kind == "RoutingLayers":
            self._routing_layers(rule)
        elif kind == "ShortCircuit":
            self._short(rule)
        elif kind in _SKIPPED_KINDS:
            self.skip_kind(kind, _SKIPPED_KINDS[kind])
        else:
            self.skip_kind(kind or "unknown", "no KiCad constraint")

    def _clearance(self, rule, edge: bool) -> None:
        prepared = self._scopes(rule, binary=not edge)
        if prepared is None:
            return
        layer, condition = prepared
        netscope = (rule.get("NETSCOPE") or "AnyNet").strip() or "AnyNet"
        gap_text = rule.get("GAP")
        generic = rule.get("GENERICCLEARANCE")
        if generic and gap_text and not lengths_equal(generic, gap_text):
            self.detail.append(f"{rule.name}: GAP and GENERICCLEARANCE differ; KiCad uses GAP.")
        if (rule.get("IGNOREPADTOPADCLEARANCEINFOOTPRINT") or "").upper() == "TRUE":
            self.detail.append(
                f"{rule.name}: KiCad has no switch for ignoring pad-to-pad clearance inside a footprint."
            )
        if edge:
            constraint = "edge_clearance"
        elif netscope == "DifferentNets":
            constraint = "clearance"
        else:
            constraint = "physical_clearance"
        if not edge and netscope == "SameNet":
            condition = and_cond(condition, "A.Net == B.Net")
        token = mm_token(gap_text)
        if token:
            self.add(rule.name, rule.priority, [f"(constraint {constraint} (min {token}))"], layer, condition)
        elif not (rule.get("OBJECTCLEARANCES") or "").strip():
            self.detail.append(f"{rule.name}: no gap to export.")
        self._object_pairs(rule, layer, condition, netscope, edge, constraint)

    def _object_pairs(self, rule, layer, condition, netscope: str, edge: bool, constraint: str) -> None:
        raw = rule.get("OBJECTCLEARANCES")
        if raw is None or not raw.strip():
            return
        holes: dict[str, set[str]] = {}
        others: dict[tuple[str, str], str] = {}
        for left, right, token in parse_object_clearances(raw):
            mm = object_clearance_mm(token) if token else None
            if not left or not right or mm is None:
                self.detail.append(f"{rule.name}: skipped an object-clearance entry {left}-{right}.")
                continue
            shown = format_mm(mm) + "mm"
            pair = {left.strip().lower(), right.strip().lower()}
            if "hole" in pair:
                if edge or pair == {"hole"}:
                    self.detail.append(f"{rule.name}: skipped object clearance {left}-{right}.")
                    continue
                other = next(iter(pair - {"hole"}))
                if other not in _OBJECT_EXPR:
                    self.detail.append(f"{rule.name}: skipped object clearance {left}-{right}.")
                    continue
                holes.setdefault(shown, set()).add(other)
                continue
            if any(name not in _OBJECT_EXPR for name in pair):
                self.detail.append(f"{rule.name}: skipped object clearance {left}-{right}.")
                continue
            key = "-".join(sorted(pair))
            others[(key, shown)] = shown
        hole_names = list(holes)
        for shown, types in holes.items():
            hole_name = "hole_clearance" if netscope == "DifferentNets" else "physical_hole_clearance"
            type_condition = _copper_condition(types)
            label = f"{rule.name} hole" if len(hole_names) == 1 else f"{rule.name} hole {shown}"
            self.add(
                label,
                rule.priority,
                [f"(constraint {hole_name} (min {shown}))"],
                layer,
                and_cond(condition, type_condition),
                specificity=0 if type_condition is None else 1,
            )
        for (key, shown), _value in others.items():
            left, _dash, right = key.partition("-")
            self.add(
                f"{rule.name} {key}",
                rule.priority,
                [f"(constraint {constraint} (min {shown}))"],
                layer,
                and_cond(condition, _pair_condition(left, right)),
                specificity=1,
            )

    def _width(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        scope_layer, condition = prepared
        resolved = []
        for group_layer, triple in width_groups(rule):
            chosen = resolve_layer(scope_layer, group_layer)
            if chosen is _SKIP:
                continue
            resolved.append((chosen, triple))
        if not resolved:
            self.detail.append(f"{rule.name}: no track width matches its layer scope.")
            return
        written = 0
        for layer, (minimum, preferred, maximum) in resolved:
            clause = self._range(rule.name, "track_width", minimum, preferred, maximum)
            if not clause:
                continue
            name = rule.name if len(resolved) == 1 or layer is None else f"{rule.name} {layer}"
            specificity = 0 if layer in (None, "inner", "outer") else 1
            self.add(name, rule.priority, [clause], layer, condition, specificity=specificity)
            written += 1
        if written == 0:
            self.detail.append(f"{rule.name}: no track width to export.")

    def _vias(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        layer, condition = prepared
        hole = self._range(rule.name, "hole_size", rule.get("MINHOLEWIDTH"), rule.get("HOLEWIDTH"), rule.get("MAXHOLEWIDTH"))
        diameter = self._range(rule.name, "via_diameter", rule.get("MINWIDTH"), rule.get("WIDTH"), rule.get("MAXWIDTH"))
        clauses = [item for item in (hole, diameter) if item]
        if not clauses:
            self.detail.append(f"{rule.name}: no via size to export.")
            return
        if not condition or "Via" not in condition:
            condition = and_cond(condition, "A.Type == 'Via'")
        style = (rule.get("VIASTYLE") or "").strip()
        if style and style.lower() not in {"through hole", "through-hole", "throughhole"}:
            self.detail.append(f"{rule.name}: via style {style} applies to every via in the exported size check.")
        self.add(rule.name, rule.priority, clauses, layer, condition)

    def _hole_size(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        layer, condition = prepared
        if parse_bool(rule.get("ABSOLUTEVALUES") or "TRUE") is False:
            self.detail.append(f"{rule.name}: percent hole size has no KiCad equivalent, so the rule was not exported.")
            return
        clause = self._range(rule.name, "hole_size", rule.get("MINLIMIT"), None, rule.get("MAXLIMIT"))
        if not clause:
            self.detail.append(f"{rule.name}: no absolute hole size to export.")
            return
        if condition is None:
            condition = "A.Type == 'Pad' && A.Pad_Type != 'SMD'"
        elif "Pad_Type" not in condition and "Via" not in condition:
            condition = and_cond(condition, "A.Type == 'Pad'")
        self.add(rule.name, rule.priority, [clause], layer, condition)

    def _annular(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        layer, condition = prepared
        token = mm_token(rule.get("MINIMUMRING"))
        if not token:
            self.detail.append(f"{rule.name}: no annular ring to export.")
            return
        self.add(rule.name, rule.priority, [f"(constraint annular_width (min {token}))"], layer, condition)

    def _hole_to_hole(self, rule) -> None:
        prepared = self._scopes(rule, binary=True)
        if prepared is None:
            return
        layer, condition = prepared
        token = mm_token(rule.get("GAP"))
        if not token:
            self.detail.append(f"{rule.name}: no hole-to-hole gap to export.")
            return
        self.add(rule.name, rule.priority, [f"(constraint hole_to_hole (min {token}))"], layer, condition)
        if parse_bool(rule.get("ALLOWSTACKEDMICROVIAS") or "FALSE") is True:
            self.detail.append(
                f"{rule.name}: stacked microvias are allowed in Altium. "
                "KiCad has no matching allowance; the hole-to-hole gap was still exported."
            )

    def _plane_clearance(self, rule) -> None:
        prepared = self._scopes(rule, binary=True)
        if prepared is None:
            return
        layer, condition = prepared
        mm = quant_mm(rule.get("CLEARANCE"))
        token = mm_token(rule.get("CLEARANCE"))
        if mm is None or not token:
            self.detail.append(f"{rule.name}: no plane clearance to export.")
            return
        target = layer or "inner"
        if not self._tighter(mm, target):
            reference = self.inner_gap if target == "inner" and self.inner_gap is not None else self.all_gap
            suffix = f" ({format_mm(reference)} mm)" if reference is not None else ""
            self.detail.append(
                f"{rule.name}: plane clearance {token} is not tighter than the copper clearance{suffix}, "
                "so it was not written."
            )
            return
        zone = "A.Type == 'Zone' || B.Type == 'Zone'"
        self.add(
            rule.name,
            rule.priority,
            [f"(constraint clearance (min {token}))"],
            target,
            and_cond(condition, zone),
            rank=2,
        )

    def _connect(self, rule, kind: str) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        layer, condition = prepared
        field = "PLANECONNECTSTYLE" if kind == "plane" else "CONNECTSTYLE"
        raw = (rule.get(field) or "").strip()
        style = _ZONE_STYLE.get(raw.lower())
        if style is None:
            self.detail.append(f"{rule.name}: unknown connect style {raw!r}.")
            return
        self.zone_styles[kind] = raw or style
        clauses = [f"(constraint zone_connection {style})"]
        if style == "thermal_reliefs":
            expansion = mm_token(rule.get("RELIEFEXPANSION")) if kind == "plane" else None
            if expansion:
                clauses.append(f"(constraint thermal_relief_gap (min {expansion}))")
            air = mm_token(rule.get("RELIEFAIRGAP")) if kind == "plane" else None
            if air and expansion and air != expansion:
                self.detail.append(
                    f"{rule.name}: relief air gap {air} has no KiCad constraint; "
                    f"thermal_relief_gap uses the expansion {expansion}."
                )
            spoke = mm_token(rule.get("RELIEFCONDUCTORWIDTH"))
            if spoke:
                clauses.append(f"(constraint thermal_spoke_width (opt {spoke}))")
            entries = (rule.get("RELIEFENTRIES") or "").strip()
            if entries.lstrip("-").isdigit():
                clauses.append(f"(constraint min_resolved_spokes {int(entries)})")
            if kind == "polygon" and (rule.get("POLYGONRELIEFANGLE") or "").strip():
                self.detail.append(
                    f"{rule.name}: relief angle {rule.get('POLYGONRELIEFANGLE')} has no KiCad constraint."
                )
        self.add(rule.name, rule.priority, clauses, layer, condition, rank=1 if kind == "polygon" else 0)
        if kind == "polygon":
            self._pour_gap(rule, layer, condition)

    def _pour_gap(self, rule, layer, condition) -> None:
        mm = quant_mm(rule.get("AIRGAPWIDTH"))
        token = mm_token(rule.get("AIRGAPWIDTH"))
        if mm is None or not token:
            return
        if not self._tighter(mm, layer):
            self.detail.append(f"{rule.name}: pour gap {token} is already covered by the copper clearance rules.")
            return
        zone = "A.Type == 'Zone' || B.Type == 'Zone'"
        self.add(
            f"{rule.name} pour",
            rule.priority,
            [f"(constraint clearance (min {token}))"],
            layer,
            and_cond(condition, zone),
            rank=1,
        )

    def _mask(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        layer, condition = prepared
        token = mm_token(rule.get("EXPANSION"))
        if not token:
            self.detail.append(f"{rule.name}: no solder-mask expansion to export.")
            return
        self.add(rule.name, rule.priority, [f"(constraint solder_mask_expansion (opt {token}))"], layer, condition)
        top = parse_bool(rule.get("ISTENTINGTOP") or "FALSE") is True
        bottom_text = rule.get("ISTENTINGBOTTOM")
        bottom = parse_bool(bottom_text) is True if bottom_text is not None else False
        if not top and not bottom:
            return
        if condition and "Via" in condition:
            return
        expansion = quant_mm(rule.get("EXPANSION"))
        if expansion == Decimal("0.0000"):
            self.detail.append(f"{rule.name}: via tenting is enabled and the mask expansion is already 0.")
            return
        self.add(
            f"{rule.name} tented",
            rule.priority,
            ["(constraint solder_mask_expansion (opt 0.0000mm))"],
            layer,
            and_cond(condition, "A.Type == 'Via'"),
            specificity=1,
        )
        if top and not bottom:
            self.detail.append(
                f"{rule.name}: Altium tents the top side only. KiCad applies the 0 mm via expansion to both sides."
            )

    def _paste(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        layer, condition = prepared
        token = mm_token(rule.get("EXPANSION"))
        if not token:
            self.detail.append(f"{rule.name}: no paste expansion to export.")
            return
        self.add(rule.name, rule.priority, [f"(constraint solder_paste_abs_margin (opt {token}))"], layer, condition)

    def _sliver(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        layer, condition = prepared
        token = mm_token(rule.get("MINSOLDERMASKWIDTH"))
        if not token:
            self.detail.append(f"{rule.name}: no solder-mask sliver to export.")
            return
        self.add(rule.name, rule.priority, [f"(constraint solder_mask_sliver (min {token}))"], layer, condition)

    def _silk(self, rule, field: str, which: str) -> None:
        prepared = self._scopes(rule, binary=True)
        if prepared is None:
            return
        layer, condition = prepared
        mm = quant_mm(rule.get(field))
        token = mm_token(rule.get(field))
        if mm is None or not token:
            self.detail.append(f"{rule.name}: no {which} gap to export.")
            return
        if mm == 0:
            self.detail.append(
                f"{rule.name}: {which} is 0 mm, so it was not exported. KiCad has one silk_clearance constraint."
            )
            return
        self.add(
            rule.name,
            rule.priority,
            [f"(constraint silk_clearance (min {token}))"],
            layer,
            condition,
            rank=1 if which == "silk to mask" else 0,
        )
        if which == "silk to mask":
            self.silk_mask = True
        else:
            self.silk_silk = True

    def _routing_layers(self, rule) -> None:
        prepared = self._scopes(rule, binary=False)
        if prepared is None:
            return
        scope_layer, condition = prepared
        blocked = []
        for title, key in zip(LAYER_TITLES, ROUTING_LAYER_KEYS):
            if parse_bool(rule.get(key) or "TRUE") is not False:
                continue
            chosen = resolve_layer(scope_layer, _copper_layer(title))
            if chosen is _SKIP or not isinstance(chosen, str):
                continue
            blocked.append(chosen)
        if not blocked:
            self.skip_kind("RoutingLayers", "every copper layer is already allowed")
            return
        for copper in blocked:
            self.add(
                f"{rule.name} {copper}",
                rule.priority,
                ["(constraint disallow track)"],
                copper,
                condition,
            )

    def _short(self, rule) -> None:
        if (rule.get("ALLOWED") or "FALSE").upper() == "TRUE":
            self.detail.append(
                f"{rule.name}: shorts are allowed in Altium. KiCad still reports short circuits, so no rule was written."
            )
            return
        self.skip_kind("ShortCircuit", "KiCad already checks short circuits")


def _copper_condition(types: set[str]) -> str | None:
    if types >= _ALL_COPPER:
        return None
    parts = []
    seen = set()
    for name in sorted(types):
        one = _OBJECT_EXPR[name].replace("{o}", "A")
        other = _OBJECT_EXPR[name].replace("{o}", "B")
        clause = f"({one})" if one == other else f"({one}) || ({other})"
        if clause not in seen:
            seen.add(clause)
            parts.append(clause)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return " || ".join(parts)


def _pair_condition(left: str, right: str) -> str:
    if left == right:
        return f"({_OBJECT_EXPR[left].replace('{o}', 'A')}) && ({_OBJECT_EXPR[right].replace('{o}', 'B')})"
    forward = f"({_OBJECT_EXPR[left].replace('{o}', 'A')}) && ({_OBJECT_EXPR[right].replace('{o}', 'B')})"
    backward = f"({_OBJECT_EXPR[left].replace('{o}', 'B')}) && ({_OBJECT_EXPR[right].replace('{o}', 'A')})"
    return f"({forward}) || ({backward})"


def _unique_name(name: str, used: set[str]) -> str:
    candidate = name
    number = 2
    while candidate in used:
        candidate = f"{name} {number}"
        number += 1
    used.add(candidate)
    return candidate


def _render_rule(rule: OutRule, name: str) -> str:
    lines = ["(rule " + _dq(name)]
    if rule.layer:
        lines.append("    " + _layer_clause(rule.layer))
    for clause in rule.constraints:
        lines.append("    " + clause)
    if rule.condition:
        lines.append("    (condition " + _dq(rule.condition) + ")")
    lines.append(")")
    return "\n".join(lines)
