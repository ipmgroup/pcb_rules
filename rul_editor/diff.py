"""Compare Altium .RUL documents by rule kind and name."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from rul_editor.model import RulDocument, Rule
from rul_editor.schema import kind_sort_key, label_for, summary_for, values_equal
from rul_editor.units import display_mm, is_length_key, parse_object_clearances, object_clearance_mm, format_mm

# SELECTION is editor state. UNIQUEID is an Altium handle and differs on every export.
IGNORED_KEYS = {"SELECTION", "UNIQUEID"}


@dataclass
class FieldChange:
    key: str
    values: list[str | None]

    @property
    def differs(self) -> bool:
        present = [value for value in self.values if value is not None]
        if len(present) != len(self.values):
            return True
        first = present[0]
        return any(not values_equal(self.key, first, other) for other in present[1:])


@dataclass
class RuleRow:
    kind: str
    name: str
    rules: list[Rule | None]
    changes: list[FieldChange] = field(default_factory=list)

    @property
    def differs(self) -> bool:
        if any(rule is None for rule in self.rules):
            return True
        return any(change.differs for change in self.changes)

    def summaries(self) -> list[str]:
        return ["" if rule is None else summary_for(rule) for rule in self.rules]


@dataclass
class Matrix:
    rows: list[RuleRow]

    @property
    def difference_count(self) -> int:
        return sum(1 for row in self.rows if row.differs)


def compare_documents(documents: list[RulDocument], ignore_comments: bool = False) -> Matrix:
    grouped: list[dict[tuple[str, str, int], Rule]] = []
    for document in documents:
        counts: dict[tuple[str, str], int] = {}
        mapping: dict[tuple[str, str, int], Rule] = {}
        for rule in document.rules:
            identity = (rule.kind, rule.name)
            index = counts.get(identity, 0)
            counts[identity] = index + 1
            mapping[(rule.kind, rule.name, index)] = rule
        grouped.append(mapping)
    keys: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for mapping in grouped:
        for key in mapping:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    keys.sort(key=lambda item: (kind_sort_key(item[0]), item[1].lower(), item[2]))
    rows = []
    for key in keys:
        rules = [mapping.get(key) for mapping in grouped]
        label = key[1] if key[2] == 0 else f"{key[1]} [{key[2] + 1}]"
        row = RuleRow(key[0], label, rules)
        row.changes = _field_changes(rules, ignore_comments)
        rows.append(row)
    return Matrix(rows)


def _field_changes(rules: list[Rule | None], ignore_comments: bool) -> list[FieldChange]:
    skip = set(IGNORED_KEYS)
    if ignore_comments:
        skip.add("COMMENT")
    order: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        if rule is None:
            continue
        for key, _value in rule.items:
            if key in skip or key in seen:
                continue
            seen.add(key)
            order.append(key)
    changes = []
    for key in order:
        values = [None if rule is None else rule.get(key) for rule in rules]
        changes.append(FieldChange(key, values))
    return changes


def display_value(key: str, value: str | None) -> str:
    if value is None:
        return "(missing)"
    if key == "OBJECTCLEARANCES":
        return _display_clearances(value)
    if is_length_key(key):
        shown = display_mm(value)
        if shown is not None:
            return f"{shown} mm ({value})"
    compact = " ".join(value.split())
    if len(compact) > 180:
        return compact[:177] + "..."
    return compact


def _display_clearances(value: str) -> str:
    rows = parse_object_clearances(value)
    if not rows:
        return "(none)"
    bits = []
    for left, right, token in rows:
        mm = object_clearance_mm(token)
        gap = f"{format_mm(mm)} mm" if mm is not None else token
        bits.append(f"{left}-{right} {gap}")
    return "; ".join(bits)


def format_diff(matrix: Matrix, labels: list[str]) -> str:
    if len(labels) != 2:
        raise ValueError("format_diff expects two files")
    if not matrix.rows:
        return "Both files have no rules."
    lines: list[str] = []
    changes = [row for row in matrix.rows if row.differs]
    if not changes:
        lines.append(f"No differences between {labels[0]} and {labels[1]}.")
        return "\n".join(lines)
    lines.append(f"{len(changes)} differing rule(s) of {len(matrix.rows)}.")
    for row in changes:
        lines.append("")
        lines.append(f"{row.kind} / {row.name}")
        if row.rules[0] is None:
            lines.append(f"  only in {labels[1]}: {summary_for(row.rules[1])}")
            continue
        if row.rules[1] is None:
            lines.append(f"  only in {labels[0]}: {summary_for(row.rules[0])}")
            continue
        for change in row.changes:
            if not change.differs:
                continue
            left = display_value(change.key, change.values[0])
            right = display_value(change.key, change.values[1])
            lines.append(f"  {label_for(change.key)}")
            lines.append(f"    {labels[0]}: {left}")
            lines.append(f"    {labels[1]}: {right}")
    return "\n".join(lines)


def format_matrix(matrix: Matrix, labels: list[str], only_changes: bool = True) -> str:
    rows = [row for row in matrix.rows if row.differs] if only_changes else list(matrix.rows)
    if not rows:
        return "No differences."
    width = max(len(label) for label in labels)
    lines = [f"{len(rows)} rule(s)" + (" that differ." if only_changes else ".")]
    for row in rows:
        lines.append("")
        lines.append(f"{row.kind} / {row.name}")
        summaries = row.summaries()
        same_summary = len(set(summaries)) == 1 and all(rule is not None for rule in row.rules)
        if same_summary:
            lines.append(f"  {'same':<{width}}  {summaries[0]}")
        else:
            for label, summary, rule in zip(labels, summaries, row.rules):
                text = "(not in this file)" if rule is None else summary
                lines.append(f"  {label:<{width}}  {text}")
        extra = _extra_keys(row)
        if extra and all(rule is not None for rule in row.rules):
            lines.append("  also differs: " + ", ".join(extra))
    return "\n".join(lines)


def _extra_keys(row: RuleRow) -> list[str]:
    """Fields that differ and are not already visible in the measurement summary."""
    covered = {"GAP", "GENERICCLEARANCE", "OBJECTCLEARANCES"}
    names = []
    for change in row.changes:
        if not change.differs:
            continue
        if change.key in covered or is_length_key(change.key):
            continue
        names.append(change.key)
    return names


def matrix_csv(matrix: Matrix, labels: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Kind", "Name", "Status", *labels])
    for row in matrix.rows:
        status = "different" if row.differs else "same"
        writer.writerow([row.kind, row.name, status, *row.summaries()])
    return buffer.getvalue()
