"""Load and save Altium Designer .RUL rule files.

A file is a sequence of records. Each record is ``KEY=VALUE`` fields joined by
``|`` and terminated by a pilcrow (U+00B6). Windows exports use CRLF and a
Latin-1 pilcrow byte. Some files in this project are UTF-8. Both round-trip.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from rul_editor.schema import HEADER_KEYS, kind_tail
from rul_editor.units import (
    format_bool,
    format_mil,
    is_bool_key,
    is_length_key,
    is_percent_key,
    lengths_equal,
    parse_bool,
    parse_length,
)

RECORD_MARK = "\u00b6"
_ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


class UserError(Exception):
    """A problem caused by the file or the command, not by the program."""


class Rule:
    def __init__(self, items: list[tuple[str, str]] | None = None):
        self.items: list[tuple[str, str]] = list(items or [])

    def get(self, key: str, default: str | None = None) -> str | None:
        for name, value in self.items:
            if name == key:
                return value
        return default

    def has(self, key: str) -> bool:
        return any(name == key for name, _value in self.items)

    def set(self, key: str, value: str) -> None:
        for index, (name, _value) in enumerate(self.items):
            if name == key:
                self.items[index] = (name, value)
                return
        self.items.append((key, value))

    def delete(self, key: str) -> None:
        self.items = [(name, value) for name, value in self.items if name != key]

    def clone(self) -> "Rule":
        return Rule(self.items)

    @property
    def kind(self) -> str:
        return self.get("RULEKIND") or ""

    @property
    def name(self) -> str:
        return self.get("NAME") or ""

    @property
    def priority(self) -> int:
        raw = self.get("PRIORITY") or "0"
        try:
            return int(raw)
        except ValueError:
            return 0

    def __repr__(self) -> str:
        return f"Rule({self.kind}:{self.name})"


class RulDocument:
    def __init__(self, rules: list[Rule] | None = None, encoding: str = "latin-1", newline: str = "\r\n"):
        self.rules = list(rules or [])
        self.encoding = encoding
        self.newline = newline
        self.path: Path | None = None

    def clone(self) -> "RulDocument":
        copy = RulDocument([rule.clone() for rule in self.rules], self.encoding, self.newline)
        copy.path = self.path
        return copy

    def find(self, name: str | None = None, unique_id: str | None = None) -> Rule:
        matches = []
        for rule in self.rules:
            if unique_id is not None and rule.get("UNIQUEID") == unique_id:
                matches.append(rule)
            elif unique_id is None and name is not None and rule.name == name:
                matches.append(rule)
        if not matches:
            target = unique_id or name or ""
            raise UserError(f"No rule named {target!r}.")
        if len(matches) > 1:
            target = unique_id or name or ""
            raise UserError(f"More than one rule matches {target!r}. Pass --id.")
        return matches[0]

    def dumps(self) -> str:
        chunks = []
        for rule in self.rules:
            body = "|".join(f"{key}={value}" for key, value in rule.items)
            chunks.append(body + RECORD_MARK + self.newline)
        return "".join(chunks)

    def to_bytes(self) -> tuple[bytes, str]:
        text = self.dumps()
        try:
            return text.encode(self.encoding), self.encoding
        except UnicodeEncodeError:
            return text.encode("utf-8"), "utf-8"

    def save(self, path: Path | str) -> str:
        destination = Path(path)
        payload, encoding = self.to_bytes()
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_bytes(payload)
        try:
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        self.encoding = encoding
        self.path = destination
        return encoding


def load(path: Path | str) -> RulDocument:
    source = Path(path)
    if not source.is_file():
        raise UserError(f"File not found: {source}")
    document = load_bytes(source.read_bytes())
    document.path = source
    return document


def load_bytes(data: bytes) -> RulDocument:
    if data.startswith(b"\xef\xbb\xbf"):
        text = data.decode("utf-8-sig")
        encoding = "utf-8-sig"
    else:
        try:
            text = data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = data.decode("latin-1")
            encoding = "latin-1"
    newline = "\r\n" if "\r\n" in text else "\n" if "\n" in text else "\r\n"
    rules = []
    for part in text.split(RECORD_MARK):
        body = _unwrap(part)
        if not body.strip():
            continue
        rules.append(_parse_record(body))
    return RulDocument(rules, encoding, newline)


def _unwrap(part: str) -> str:
    if part.startswith("\r\n"):
        part = part[2:]
    elif part.startswith("\n"):
        part = part[1:]
    if part.endswith("\r\n"):
        part = part[:-2]
    elif part.endswith("\n"):
        part = part[:-1]
    return part


def _parse_record(body: str) -> Rule:
    items: list[tuple[str, str]] = []
    for part in body.split("|"):
        if "=" not in part:
            raise UserError(f"A rule field has no '=': {part[:80]!r}")
        key, value = part.split("=", 1)
        items.append((key, value))
    return Rule(items)


def new_unique_id() -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(8))


def make_rule(kind: str, name: str, priority: int = 1, unique_id: str | None = None) -> Rule:
    if kind not in _known():
        raise UserError(f"Unknown rule kind {kind!r}. Known kinds: {', '.join(_known())}")
    netscope = "DifferentNets" if kind in {"Clearance", "BoardOutlineClearance"} else "AnyNet"
    header = {
        "SELECTION": "FALSE",
        "LAYER": "TOP",
        "LOCKED": "FALSE",
        "POLYGONOUTLINE": "FALSE",
        "USERROUTED": "TRUE",
        "KEEPOUT": "FALSE",
        "UNIONINDEX": "0",
        "RULEKIND": kind,
        "NETSCOPE": netscope,
        "LAYERKIND": "SameLayer",
        "SCOPE1EXPRESSION": "All",
        "SCOPE2EXPRESSION": "All",
        "NAME": name,
        "ENABLED": "TRUE",
        "PRIORITY": str(priority),
        "COMMENT": "",
        "UNIQUEID": unique_id or new_unique_id(),
        "DEFINEDBYLOGICALDOCUMENT": "FALSE",
    }
    items = [(key, header[key]) for key in HEADER_KEYS]
    items.extend(kind_tail(kind))
    return Rule(items)


def _known():
    from rul_editor.schema import known_kinds

    return known_kinds()


def next_priority(document: RulDocument, kind: str) -> int:
    values = [rule.priority for rule in document.rules if rule.kind == kind]
    return max(values, default=0) + 1


def unique_name(document: RulDocument, name: str) -> str:
    taken = {rule.name for rule in document.rules}
    if name not in taken:
        return name
    index = 2
    while f"{name}_{index}" in taken:
        index += 1
    return f"{name}_{index}"


def assign_value(rule: Rule, key: str, text: str, link: bool = True) -> None:
    """Store a user-typed value, converting lengths to mil text."""
    if is_length_key(key):
        mm = parse_length(text, plain_is_mm=True)
        if mm is None:
            raise UserError(f"{key} needs a length such as 0.10mm or 3.9370mil, not {text!r}.")
        stored = format_mil(mm)
        previous = rule.get(key)
        rule.set(key, stored)
        if link and key == "GAP" and rule.has("GENERICCLEARANCE"):
            generic = rule.get("GENERICCLEARANCE") or ""
            if previous is None or lengths_equal(previous, generic):
                rule.set("GENERICCLEARANCE", stored)
        return
    if is_bool_key(key):
        parsed = parse_bool(text)
        if parsed is None:
            raise UserError(f"{key} needs true or false, not {text!r}.")
        rule.set(key, format_bool(parsed))
        return
    if is_percent_key(key):
        token = text.strip().rstrip("%").strip()
        try:
            number = float(token)
        except ValueError as exc:
            raise UserError(f"{key} needs a number, not {text!r}.") from exc
        rule.set(key, f"{number:.3f}")
        return
    if key == "PRIORITY":
        try:
            number = int(text.strip())
        except ValueError as exc:
            raise UserError(f"Priority needs an integer, not {text!r}.") from exc
        rule.set(key, str(number))
        return
    rule.set(key, text)


def parse_assignments(pairs: list[str]) -> list[tuple[str, str]]:
    parsed = []
    for item in pairs:
        if "=" not in item:
            raise UserError(f"--set needs KEY=VALUE, not {item!r}.")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise UserError(f"--set needs a field name in {item!r}.")
        parsed.append((key, value))
    return parsed


def collect_rul_paths(arguments: list[str]) -> list[Path]:
    found: list[Path] = []
    for argument in arguments:
        path = Path(argument)
        if path.is_dir():
            candidates = sorted(path.glob("*.RUL")) + sorted(path.glob("*.rul"))
            if not candidates:
                raise UserError(f"No .RUL files in {path}")
            seen: set[Path] = set()
            for candidate in candidates:
                resolved = candidate.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                found.append(candidate)
        else:
            found.append(path)
    if not found:
        raise UserError("Name at least one .RUL file or a directory that contains them.")
    return found
