"""Command line for the Altium .RUL editor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rul_editor.diff import compare_documents, format_diff, format_matrix, matrix_csv
from rul_editor.model import (
    UserError,
    assign_value,
    collect_rul_paths,
    load,
    make_rule,
    next_priority,
    parse_assignments,
)
from rul_editor.schema import kind_sort_key, known_kinds, summary_for
from rul_editor.units import display_mm, is_length_key

USAGE = """
examples:
  python -m rul_editor
  python -m rul_editor gui beta_layout.RUL
  python -m rul_editor list beta_layout.RUL
  python -m rul_editor show beta_layout.RUL --name Clearance
  python -m rul_editor set beta_layout.RUL --name Clearance --set GAP=0.10mm -o out.RUL
  python -m rul_editor diff beta_layout.RUL JLCPCB_4L_6L_1oz.RUL
  python -m rul_editor compare .
  python -m rul_editor compare beta_layout.RUL JLCPCB_4L_6L_1oz.RUL --gui

In the window, File → Compare RUL asks for the files to compare.
Load RUL in that window adds more files. Several files can be selected at once.

Lengths accept 0.10mm, 3.9370mil, or a plain number in millimetres.
Editing GAP also updates GENERICCLEARANCE when the two still match.
diff exits 1 when the files differ.
""".strip()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "gui":
        paths = argv[1:] if argv and argv[0] == "gui" else list(argv)
        from rul_editor.gui import run

        return run(paths)
    if argv[0] not in _COMMANDS and not argv[0].startswith("-"):
        from rul_editor.gui import run

        return run(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except UserError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rul-editor",
        description="Edit and compare Altium Designer .RUL PCB rule files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=USAGE,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List rules with millimetre summaries")
    list_cmd.add_argument("file")
    list_cmd.set_defaults(handler=cmd_list)

    show = sub.add_parser("show", help="Print one rule")
    show.add_argument("file")
    _add_selector(show)
    show.set_defaults(handler=cmd_show)

    edit = sub.add_parser("set", help="Change fields on one rule")
    edit.add_argument("file")
    _add_selector(edit)
    edit.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    edit.add_argument("--no-link", action="store_true", help="Do not keep GENERICCLEARANCE equal to GAP")
    _add_output(edit)
    edit.set_defaults(handler=cmd_set)

    add = sub.add_parser("add", help="Append a rule")
    add.add_argument("file")
    add.add_argument("--kind", required=True, choices=known_kinds())
    add.add_argument("--name", default="")
    add.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    _add_output(add)
    add.set_defaults(handler=cmd_add)

    remove = sub.add_parser("remove", help="Delete a rule")
    remove.add_argument("file")
    _add_selector(remove)
    _add_output(remove)
    remove.set_defaults(handler=cmd_remove)

    diff = sub.add_parser("diff", help="Compare two files field by field")
    diff.add_argument("files", nargs="+")
    diff.add_argument("--ignore-comments", action="store_true")
    diff.add_argument("--gui", action="store_true", help="Open the comparison window")
    diff.set_defaults(handler=cmd_diff)

    compare = sub.add_parser("compare", help="Compare any number of .RUL files or a directory")
    compare.add_argument("files", nargs="+")
    compare.add_argument("--all", action="store_true", help="Include rules that match")
    compare.add_argument("--ignore-comments", action="store_true")
    compare.add_argument("--csv", metavar="FILE", help="Also write a CSV matrix")
    compare.add_argument("--gui", action="store_true", help="Open the comparison window")
    compare.set_defaults(handler=cmd_compare)

    gui = sub.add_parser("gui", help="Open the Qt editor")
    gui.add_argument("files", nargs="*")
    gui.set_defaults(handler=cmd_gui)
    return parser


_COMMANDS = {"list", "show", "set", "add", "remove", "diff", "compare", "gui"}


def _add_selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help="Rule NAME")
    parser.add_argument("--id", help="Rule UNIQUEID")


def _add_output(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-o", "--output", help="Write a new file")
    group.add_argument("--in-place", action="store_true", help="Overwrite the input file")


def _selected(document, args):
    if not args.name and not args.id:
        raise UserError("Pass --name or --id.")
    return document.find(name=args.name, unique_id=args.id)


def _write(document, args) -> None:
    previous = document.encoding
    if args.in_place:
        if document.path is None:
            raise UserError("This document has no path to overwrite.")
        destination = document.path
    else:
        destination = Path(args.output)
    used = document.save(destination)
    print(f"Wrote {destination} ({used})")
    if used != previous:
        print("Encoding changed to UTF-8 so every character could be stored.")


def _labels(paths: list[Path]) -> list[str]:
    names = [path.name for path in paths]
    if len(names) == len(set(names)):
        return names
    return [f"{path.parent.name}/{path.name}" for path in paths]


def cmd_list(args) -> int:
    document = load(args.file)
    newline = "CRLF" if document.newline == "\r\n" else "LF"
    print(f"{Path(args.file).name}  {len(document.rules)} rules  {document.encoding}  {newline}")
    ordered = sorted(document.rules, key=lambda rule: (kind_sort_key(rule.kind), rule.priority))
    for rule in ordered:
        enabled = "" if (rule.get("ENABLED") or "TRUE").upper() == "TRUE" else "  disabled"
        print(f"{rule.priority:>2}  {rule.kind:<28}  {rule.name:<32}  {summary_for(rule)}{enabled}")
    return 0


def cmd_show(args) -> int:
    document = load(args.file)
    rule = _selected(document, args)
    print(f"{rule.kind} / {rule.name}")
    for key, value in rule.items:
        suffix = ""
        if is_length_key(key):
            shown = display_mm(value)
            if shown is not None:
                suffix = f"    {shown} mm"
        print(f"{key}={value}{suffix}")
    return 0


def cmd_set(args) -> int:
    if not args.set:
        raise UserError("Pass at least one --set KEY=VALUE.")
    document = load(args.file)
    rule = _selected(document, args)
    for key, value in parse_assignments(args.set):
        assign_value(rule, key, value, link=not args.no_link)
    _write(document, args)
    return 0


def cmd_add(args) -> int:
    document = load(args.file)
    name = args.name or args.kind
    rule = make_rule(args.kind, name, next_priority(document, args.kind))
    for key, value in parse_assignments(args.set):
        assign_value(rule, key, value, link=not args.no_link)
    document.rules.append(rule)
    _write(document, args)
    return 0


def cmd_remove(args) -> int:
    document = load(args.file)
    rule = _selected(document, args)
    document.rules.remove(rule)
    _write(document, args)
    return 0


def cmd_diff(args) -> int:
    paths = collect_rul_paths(args.files)
    if args.gui:
        return _open_gui(paths)
    if len(paths) != 2:
        raise UserError("diff compares exactly two files. Use compare for a directory or more files.")
    documents = [load(path) for path in paths]
    labels = _labels(paths)
    matrix = compare_documents(documents, ignore_comments=args.ignore_comments)
    print(format_diff(matrix, labels))
    return 1 if matrix.difference_count else 0


def cmd_compare(args) -> int:
    paths = collect_rul_paths(args.files)
    if args.gui:
        return _open_gui(paths)
    documents = [load(path) for path in paths]
    labels = _labels(paths)
    matrix = compare_documents(documents, ignore_comments=args.ignore_comments)
    if args.csv:
        Path(args.csv).write_text(matrix_csv(matrix, labels), encoding="utf-8")
        print(f"Wrote {args.csv}")
    print(format_matrix(matrix, labels, only_changes=not args.all and len(documents) > 1))
    return 0


def cmd_gui(args) -> int:
    from rul_editor.gui import run

    return run(args.files)


def _open_gui(paths: list[Path]) -> int:
    from rul_editor.gui import run

    return run([str(path) for path in paths])
