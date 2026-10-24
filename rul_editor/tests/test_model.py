import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from rul_editor.diff import compare_documents
from rul_editor.model import assign_value, load, make_rule
from rul_editor.units import (
    format_mil,
    mm_to_internal,
    object_clearance_mm,
    parse_object_clearances,
    serialize_object_clearances,
)

ROOT = Path(__file__).resolve().parents[2]


class UnitsTest(unittest.TestCase):
    def test_known_fab_lengths(self):
        expected = {
            "0.03": "1.1811mil",
            "0.05": "1.9685mil",
            "0.07": "2.7559mil",
            "0.076": "2.9921mil",
            "0.09": "3.5433mil",
            "0.10": "3.9370mil",
            "0.125": "4.9213mil",
            "0.15": "5.9055mil",
            "0.20": "7.8740mil",
            "0.25": "9.8425mil",
            "0.30": "11.8110mil",
            "0.45": "17.7165mil",
            "0.50": "19.6850mil",
            "0.60": "23.6220mil",
            "6.0": "236.2205mil",
            "6.3": "248.0315mil",
            "10": "393.7008mil",
        }
        for mm, mil in expected.items():
            self.assertEqual(format_mil(Decimal(mm)), mil)

    def test_object_clearance_units(self):
        self.assertEqual(mm_to_internal(Decimal("0.30")), 118110)
        shown = object_clearance_mm("118110")
        self.assertEqual(format(shown.quantize(Decimal("0.0001")), "f"), "0.3000")


class FileTest(unittest.TestCase):
    def test_roundtrip_every_file(self):
        paths = sorted(ROOT.glob("*.RUL"))
        self.assertGreaterEqual(len(paths), 10)
        for path in paths:
            original = path.read_bytes()
            document = load(path)
            payload, encoding = document.to_bytes()
            self.assertEqual(encoding, document.encoding, path.name)
            if payload != original:
                limit = min(len(payload), len(original))
                index = next(i for i in range(limit) if payload[i] != original[i])
                self.fail(f"{path.name} differs at byte {index}: {payload[index:index+16]!r} vs {original[index:index+16]!r}")

    def test_clearance_pairs_roundtrip(self):
        for path in sorted(ROOT.glob("*.RUL")):
            for rule in load(path).rules:
                raw = rule.get("OBJECTCLEARANCES")
                if raw is None:
                    continue
                rows = parse_object_clearances(raw)
                if not rows:
                    self.assertEqual(raw.strip(), "")
                else:
                    self.assertEqual(serialize_object_clearances(rows), raw.strip())

    def test_gap_link_tracks_generic_only_while_equal(self):
        rule = make_rule("Clearance", "Clearance")
        assign_value(rule, "GENERICCLEARANCE", "0.2mm")
        assign_value(rule, "GAP", "0.1mm")
        self.assertEqual(rule.get("GAP"), "3.9370mil")
        self.assertEqual(rule.get("GENERICCLEARANCE"), "7.8740mil")
        assign_value(rule, "GAP", "0.15mm")
        self.assertEqual(rule.get("GAP"), "5.9055mil")
        self.assertEqual(rule.get("GENERICCLEARANCE"), "7.8740mil")

    def test_gap_link_updates_when_values_match(self):
        rule = make_rule("Clearance", "Clearance")
        assign_value(rule, "GAP", "0.2mm")
        self.assertEqual(rule.get("GAP"), "7.8740mil")
        self.assertEqual(rule.get("GENERICCLEARANCE"), "7.8740mil")

    def test_beta_and_jlc_clearance_differ(self):
        beta = load(ROOT / "beta_layout.RUL")
        jlc = load(ROOT / "JLCPCB_4L_6L_1oz.RUL")
        matrix = compare_documents([beta, jlc])
        clearance = next(row for row in matrix.rows if row.kind == "Clearance" and row.name == "Clearance")
        self.assertTrue(clearance.differs)
        gap = next(change for change in clearance.changes if change.key == "GAP")
        self.assertEqual(gap.values[0], "3.9370mil")
        self.assertEqual(gap.values[1], "3.5433mil")
        self.assertTrue(any(row.rules[1] is None and row.name == "Clearance_Inner" for row in matrix.rows))
        self.assertTrue(any(row.rules[0] is None and row.name == "Clearance_BGATrack" for row in matrix.rows))

    def test_cli_set_and_diff(self):
        from rul_editor.cli import main

        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "out.RUL"
            code = main([
                "set",
                str(ROOT / "beta_layout.RUL"),
                "--name",
                "Clearance",
                "--set",
                "GAP=0.2mm",
                "-o",
                str(destination),
            ])
            self.assertEqual(code, 0)
            edited = load(destination)
            rule = edited.find(name="Clearance")
            self.assertEqual(rule.get("GAP"), "7.8740mil")
            self.assertEqual(rule.get("GENERICCLEARANCE"), "7.8740mil")
            same = main(["diff", str(ROOT / "beta_layout.RUL"), str(ROOT / "beta_layout.RUL")])
            self.assertEqual(same, 0)
            changed = main(["diff", str(ROOT / "beta_layout.RUL"), str(destination)])
            self.assertEqual(changed, 1)


class GuiTest(unittest.TestCase):
    def test_edit_gap_and_compare(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication
            from rul_editor.compare_view import CompareDialog
            from rul_editor.gui import MainWindow
        except Exception as exc:
            self.skipTest(str(exc))
        try:
            app = QApplication.instance() or QApplication([])
        except Exception as exc:
            self.skipTest(str(exc))

        window = MainWindow()
        window.open_path(ROOT / "beta_layout.RUL")
        self.assertGreater(window.tree.topLevelItemCount(), 3)
        self.assertFalse(window.dirty)
        item = _find_item(window.tree, "Clearance", "Clearance")
        self.assertIsNotNone(item)
        window.tree.setCurrentItem(item)
        app.processEvents()
        self.assertEqual(window.rule.name, "Clearance")
        window._editors["GAP"].spin.setValue(0.2)
        self.assertEqual(window.rule.get("GAP"), "7.8740mil")
        self.assertEqual(window.rule.get("GENERICCLEARANCE"), "7.8740mil")
        self.assertTrue(window.dirty)
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "edited.RUL"
            window.save_to(destination)
            self.assertFalse(window.dirty)
            reloaded = load(destination)
            self.assertEqual(reloaded.find(name="Clearance").get("GAP"), "7.8740mil")

        window.open_path(ROOT / "JLCPCB_4L_6L_1oz.RUL")
        window.tree.setCurrentItem(_find_item(window.tree, "Clearance", "Clearance"))
        app.processEvents()
        overrides = window._editors["OBJECTCLEARANCES"]
        self.assertGreater(overrides.table.rowCount(), 0)

        width = _find_item(window.tree, "Width", "Width")
        window.tree.setCurrentItem(width)
        app.processEvents()
        self.assertGreaterEqual(window._editors["__width__"].table.rowCount(), 3)

        dialog = CompareDialog()
        self.assertEqual(Path(dialog._browse_directory()), ROOT)
        dialog.add_paths([ROOT / "beta_layout.RUL", ROOT / "JLCPCB_4L_6L_1oz.RUL"])
        dialog.add_paths([ROOT / "beta_layout.RUL"])
        self.assertEqual(dialog.files.count(), 2)
        self.assertGreater(dialog.difference_count(), 0)
        self.assertGreater(dialog.matrix.rowCount(), 0)
        window.dirty = False
        window.close()
        dialog.close()


def _find_item(tree, kind: str, name: str):
    for group_index in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(group_index)
        if group.text(0) != kind:
            continue
        for child_index in range(group.childCount()):
            child = group.child(child_index)
            if child.text(0) == name:
                return child
    return None


if __name__ == "__main__":
    unittest.main()
