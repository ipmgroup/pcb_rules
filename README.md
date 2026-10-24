# PCB rules and stackups

Altium Designer design rules (`.RUL`) and layer-stack files (`.stackup`) for a few board houses, plus a Python editor for the rule files.

Rule files live in one folder per supplier:

| Folder | Contents |
| --- | --- |
| `BetaLayout/` | Beta LAYOUT rules (`beta_layout.RUL`, `beta_PCB-OVERSEAS.RUL`) |
| `JLCPCB/` | JLCPCB 4- and 6-layer 1 oz rules |
| `WEdirekt/` | Würth Elektronik rules, including V-score variants |
| `BetaLayout_stackup/`, `JLCPCB_stackup/`, `MultiCB_stackup/` | Generated Altium stackups |

`rul_editor/` is the editor. The `*_stackup.py` scripts at the repository root regenerate the stackup folders.

## Rule editor

The editor loads and saves `.RUL` files without changing bytes it does not edit. Lengths are shown and typed in millimetres and stored as Altium mil text (`0.10` mm is `3.9370mil`). Within one rule kind, priority 1 is the highest.

Requires Python 3.11 or newer. From the repository root:

```
python -m pip install -r rul_editor/requirements.txt
```

On Windows, `rul_editor\rul.cmd` starts the same program.

### Window

```
python -m rul_editor
python -m rul_editor BetaLayout/beta_layout.RUL
```

The window edits one file. Rules are grouped by kind. Length fields show millimetres, with the stored mil text beside them. Changing Gap also updates Generic clearance while the two values still match.

**File → Compare RUL** asks for files to compare. In that window, **Load RUL** and **Load folder** add more files. A folder load is not recursive. You can also drop files onto the compare window. The matrix hides matching rules unless **Only differences** is turned off. **Save CSV** writes the matrix.

### Commands

Run these from the repository root.

```
python -m rul_editor list BetaLayout/beta_layout.RUL
python -m rul_editor show BetaLayout/beta_layout.RUL --name Clearance
python -m rul_editor set BetaLayout/beta_layout.RUL --name Clearance --set GAP=0.10mm -o out.RUL
python -m rul_editor add BetaLayout/beta_layout.RUL --kind Width --name Width_BGA -o out.RUL
python -m rul_editor remove out.RUL --name Width_BGA --in-place
python -m rul_editor diff BetaLayout/beta_layout.RUL JLCPCB/JLCPCB_4L_6L_1oz.RUL
python -m rul_editor compare BetaLayout JLCPCB --csv rules.csv
python -m rul_editor compare BetaLayout/beta_layout.RUL JLCPCB/JLCPCB_4L_6L_1oz.RUL --gui
```

`set`, `add`, and `remove` write a new file with `-o` or replace the input with `--in-place`. A length can be `0.10mm`, `3.9370mil`, or a plain number in millimetres.

`diff` prints field changes and exits 1 when the files differ. `compare` accepts any number of files, or one directory of `*.RUL` / `*.rul` (that directory only). `--all` includes rules that match. `--ignore-comments` skips comment text. Comparison ignores `SELECTION` and `UNIQUEID`.

`python -m rul_editor --help` lists every command.

### Tests

```
python -m unittest rul_editor.tests.test_model
```

## Stackups

Each script reads its preset data and rewrites the matching `*_stackup` folder. Run it from the repository root:

```
python beta_stackup.py
python jlc_stackup.py
python mcb_stackup.py
```

`beta_stackup.py` writes the presets in `beta_presets.py` and `beta_pool_presets.py`. `jlc_stackup.py` and `mcb_stackup.py` write the presets at the top of each script.
