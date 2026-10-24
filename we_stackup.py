"""Build Altium .stackup files for the WEdirekt shop layer builds.

The shop sheets are not the BASIC sales stackups. Source PDFs live in
the WEdirekt stack-up zip (wedirekt-stack-ups). Thickness and material
numbers are text on the sheet. Glass style was read from the material
name on each drawing.

Outer copper in the Altium file is the finished thickness from the PDF
name. The drawing shows the starting foil. Inner copper is the thickness
printed on the sheet. Where those two disagree, the sheet wins and the
file name is kept in the layer note.

Dk and Df are not printed on the drawings. FR4 uses the WEdirekt TG150
datasheet at 1 MHz (IPC-4101 E/128): under 0.5 mm the typical band is
Er 4.4-4.6, and from 0.5 mm it is Er 4.6-4.9. Df is 0.015-0.020 in both.
The files use Er 4.5 or 4.7 and Df 0.02, inside those bands. That is not
a gigahertz value.

Solder mask is Peters Elpemer 2467, linked from the WEdirekt technology
page. The drawings do not print a mask thickness, so the mask height is
0 and it does not move an impedance result.

Flex-rigid sheets and flex-with-stiffener sheets are not written. Their
coverlay or stiffener thickness is not a complete text row, so a stack
built from the text would be short of the printed nominal.

Refresh the presets from the PDF folder, then rewrite WEdirekt_stackup/:

    python we_stackup.py --from-pdfs C:\\Users\\Andrew\\Documents\\Altium\\wedirekt-stack-ups

    python we_stackup.py
"""

import argparse
import os
import uuid

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WEdirekt_stackup")

# Material number -> (kind, construction). Kind is foil, pp, core, or flex.
# Glass and resin come from the material name drawn on the sheet.
MATERIALS = {
    "50200050": ("flex", "Pyralux AP8525"),
    "50200238": ("foil", "18"),
    "50200242": ("foil", "35"),
    "50200246": ("foil", "70"),
    "50200761": ("flex", "Pyralux AP9121"),
    "50201012": ("foil", "9"),
    "50202535": ("pp", "1080 Panasonic"),
    "50202536": ("pp", "2116 H50 Panasonic"),
    "50202542": ("core", "FR4 TG150"),
    "50202557": ("core", "FR4 TG150"),
    "50202586": ("pp", "7628 Panasonic"),
    "50202593": ("core", "FR4 TG150"),
    "50202749": ("core", "FR4 TG150"),
    "50202996": ("pp", "106 H71"),
    "50203000": ("pp", "1080 H63"),
    "50203001": ("pp", "2116 H53"),
    "50203002": ("pp", "7628 H45"),
    "50203003": ("core", "FR4 TG150"),
    "50203004": ("core", "FR4 TG150"),
    "50203006": ("core", "FR4 TG150"),
    "50203007": ("core", "FR4 TG150"),
    "50203008": ("core", "FR4 TG150"),
    "50203018": ("core", "FR4 TG150"),
    "50203019": ("core", "FR4 TG150"),
    "50203020": ("core", "FR4 TG150"),
    "50203021": ("core", "FR4 TG150"),
    "50203022": ("core", "FR4 TG150"),
    "50203023": ("core", "FR4 TG150"),
    "50203026": ("core", "FR4 TG150"),
    "50203027": ("core", "FR4 TG150"),
    "50203028": ("core", "FR4 TG150"),
    "50203029": ("core", "FR4 TG150"),
    "50203030": ("core", "FR4 TG150"),
    "50203031": ("core", "FR4 TG150"),
    "50203032": ("core", "FR4 TG150"),
    "50203033": ("core", "FR4 TG150"),
    "50203053": ("core", "FR4 TG150"),
    "50203054": ("core", "FR4 TG150"),
    "50203055": ("core", "FR4 TG150"),
    "50203056": ("core", "FR4 TG150"),
    "50203059": ("core", "FR4 TG150"),
    "50203083": ("core", "FR4 TG150"),
    "50203085": ("core", "FR4 TG150"),
    "50203086": ("core", "FR4 TG150"),
    "50203087": ("core", "FR4 TG150"),
    "50203106": ("core", "FR4 TG150"),
    "50203118": ("core", "FR4 TG150"),
    "50203119": ("core", "FR4 TG150"),
    "50203120": ("core", "FR4 TG150"),
    "50203122": ("core", "FR4 TG150"),
    "50203124": ("core", "FR4 TG150"),
    "50203125": ("core", "FR4 TG150"),
    "50203129": ("core", "FR4 TG150"),
    "50203130": ("core", "FR4 TG150"),
    "50203135": ("core", "FR4 TG150"),
    "50203136": ("core", "FR4 TG150"),
    "50203137": ("core", "FR4 TG150"),
    "50203141": ("core", "FR4 TG150"),
    "50203142": ("core", "FR4 TG150"),
    "50203144": ("core", "FR4 TG150"),
    "50203145": ("core", "FR4 TG150"),
    "50203146": ("core", "FR4 TG150"),
    "50203148": ("core", "FR4 TG150"),
    "50203149": ("core", "FR4 TG150"),
    "50203150": ("core", "FR4 TG150"),
    "50203151": ("core", "FR4 TG150"),
    "50203152": ("core", "FR4 TG150"),
    "50203153": ("core", "FR4 TG150"),
    "50203154": ("core", "FR4 TG150"),
    "50203156": ("core", "FR4 TG150"),
    "50203157": ("core", "FR4 TG150"),
    "50203158": ("core", "FR4 TG150"),
    "50203159": ("core", "FR4 TG150"),
    "50203160": ("core", "FR4 TG150"),
    "50203315": ("core", "FR4 TG150"),
}

THIN = (
    "WEdirekt FR4 TG150 datasheet, IPC-4101 E/128, at 1 MHz. "
    "Dielectric under 0.5 mm is typically Er 4.4-4.6 and Df 0.015-0.020. "
    "Er 4.5 and Df 0.02 are inside that band. Not a GHz value"
)
THICK = (
    "WEdirekt FR4 TG150 datasheet, IPC-4101 E/128, at 1 MHz. "
    "Dielectric 0.5 mm and thicker is typically Er 4.6-4.9 and Df 0.015-0.020. "
    "Er 4.7 is the middle of that band. Df 0.02 is inside it. Not a GHz value"
)
FLEX_NOTE = (
    "Pyralux AP. The WEdirekt sheet does not print Dk. "
    "DuPont AP typical is about Er 3.4 and Df 0.003 at 1 MHz"
)

MASK = {
    "mm": 0.0,
    "er": 3.7,
    "df": 0.029,
    "material": "PETERS-2467",
    "freq": "1MHz",
    "mfr": "Peters",
    "desc": "Elpemer 2467. Shop technology page. Er 3.7 Df 0.029 at 1 MHz",
    "note": "Height 0. The stackup drawing does not print a mask thickness, so the mask does not move impedance",
}

TYPE_OVERLAY = "{C7EF040E-8D00-490B-B00C-A7E7823FF174}"
TYPE_SOLDER = "{7B384237-13D8-4318-8BCB-ACCD8D9A51E7}"
TYPE_COPPER = "{F4ECCD87-2CFB-4F37-BE50-4F3A272B4D01}"
TYPE_PREPREG = "{1A79611A-039D-4D40-A204-53C26C50F8B5}"
TYPE_CORE = "{136C62EF-1FA6-4897-AE71-7E797B632B92}"

ID_TOP = 16777217
ID_BOTTOM = 16842751
ID_OVERLAY_TOP = 16973830
ID_OVERLAY_BOTTOM = 16973831
ID_SOLDER_TOP = 16973834
ID_SOLDER_BOTTOM = 16973835
ID_DIELECTRIC0 = 17039361


def gid():
    return "{" + str(uuid.uuid4()).upper() + "}"


def mil(mm):
    return f"{mm / 0.0254:.4f}mil"


def weight_label(mm):
    for key, label in ((0.018, "0.5oz"), (0.035, "1oz"), (0.070, "2oz"), (0.105, "3oz")):
        if abs(mm - key) < 0.002:
            return label
    return f"{mm * 1000:.0f}um"


def mm_label(value):
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text + "mm"


def collapse(labels):
    groups = []
    for label in labels:
        if groups and groups[-1][0] == label:
            groups[-1][1] += 1
        else:
            groups.append([label, 1])
    bits = []
    for label, count in groups:
        bits.append(label if count == 1 else f"{label} x{count}")
    return " + ".join(bits)


def constants(kind, mm):
    if kind == "flex":
        return 3.4, 0.003, FLEX_NOTE, "WE-PYRALUX-AP", "DuPont", "1MHz", ""
    if mm < 0.5:
        return 4.5, 0.02, THIN, "WE-FR4-TG150", "WEdirekt", "1MHz", "150"
    return 4.7, 0.02, THICK, "WE-FR4-TG150", "WEdirekt", "1MHz", "150"


def family_of(rel):
    rel = rel.replace("\\", "/")
    if rel.startswith("HDIMicrovia1-xb-1"):
        return "HDI1xb1"
    if rel.startswith("HDIMicrovia1-x-1"):
        return "HDI1x1"
    if "/Flex/" in "/" + rel or rel.startswith("Flex/Flex/"):
        return "FLEX"
    return ""


def skip_reason(rel):
    rel = rel.replace("\\", "/")
    if "Starrflex" in rel or "Flex-rigid" in rel:
        return "flex-rigid coverlay row has no material number"
    if "Stiffener" in rel:
        return "stiffener thickness is not in the text rows"
    return ""


def join_um(values):
    out = []
    for value in values:
        if not out or out[-1] != value:
            out.append(value)
    return "-".join(str(value) for value in out)


def sheet_layers(built, info):
    """Drop empty copper. Plate the outer foils up to the finished weight."""
    rows = [item for item in built if not (item["kind"] == "cu" and item["um"] == 0)]
    cu_at = [i for i, item in enumerate(rows) if item["kind"] == "cu"]
    if not cu_at:
        raise ValueError("no copper")
    target = info["outer"]
    notes = []
    if info["inner"]:
        inners = [rows[i]["um"] for i in cu_at[1:-1]]
        if inners and any(value != info["inner"] for value in inners):
            notes.append(
                f"PDF name says inner {info['inner']} um. The sheet prints {join_um(inners)} um"
            )
    layers = []
    for index, item in enumerate(rows):
        if item["kind"] == "cu":
            base = item["um"]
            outer = index == cu_at[0] or index == cu_at[-1]
            thick = base
            plated = False
            extra = ""
            if outer and target and target >= base and target != base:
                thick = target
                plated = True
                extra = f"Starting foil {base} um, finished {target} um"
            elif outer and target and target < base:
                notes.append(f"PDF name says outer {target} um. The sheet prints {base} um")
                extra = f"Base foil {base} um"
            elif item["mat"] and MATERIALS[item["mat"]][0] == "foil":
                foil = int(MATERIALS[item["mat"]][1])
                extra = f"Base foil {base} um"
                if foil != base:
                    extra += f". Material {item['mat']} is the {foil} um foil"
            else:
                extra = f"Base foil {base} um"
            layers.append(("cu", thick / 1000.0, plated, extra))
            continue
        labels = []
        kinds = set()
        for mat, _um in item["plies"]:
            kind, label = MATERIALS[mat]
            if kind == "foil":
                raise ValueError(f"foil {mat} inside a dielectric")
            kinds.add("flex" if kind == "flex" else ("core" if kind == "core" else "pp"))
            labels.append(label)
        if len(kinds) != 1:
            raise ValueError(f"mixed dielectric {kinds}")
        kind = kinds.pop()
        stack_kind = "core" if kind == "core" else "pp"
        mm = item["um"] / 1000.0
        er, df, note, _mat, _mfr, _freq, _tg = constants(kind, mm)
        glass = collapse(labels)
        if "Panasonic" in glass:
            note += ". Material name reads Panasonic, not EM-37B. The sheet prints no separate Dk"
        layers.append((stack_kind, mm, glass, note, er, df))
    return layers, notes


def stack_name(info, layers, rel):
    cu = [layer for layer in layers if layer[0] == "cu"]
    outers = [round(layer[1] * 1000) for layer in (cu[0], cu[-1])] if len(cu) > 1 else [round(cu[0][1] * 1000)]
    inners = [round(layer[1] * 1000) for layer in cu[1:-1]]
    copper = join_um(outers) + ("-" + join_um(inners) if inners else "")
    fam = family_of(rel)
    if fam == "FLEX":
        count = info["flex"] or str(len(cu))
        return f"WE-{count}F-{copper}um-{mm_label(info['mm'])}"
    count = len(cu)
    middle = f"-{fam}" if fam else ""
    return f"WE-{count}L{middle}-{copper}um-{mm_label(info['mm'])}"


def signature(layers):
    out = []
    for layer in layers:
        if layer[0] == "cu":
            out.append(("cu", round(layer[1], 4)))
        else:
            out.append((layer[0], round(layer[1], 4), layer[2]))
    return tuple(out)


def collect(root):
    from we_scan import filename_copper, groups, parse_page, pdfs

    presets = []
    by_name = {}
    skipped = []
    for path in pdfs(root):
        rel = os.path.relpath(path, root)
        reason = skip_reason(rel)
        if reason:
            skipped.append((rel, reason))
            continue
        info = filename_copper(os.path.basename(path))
        parsed = parse_page(path)
        built = groups(parsed["rows"])
        drawn = sum(item["um"] for item in built)
        if parsed["nominal"] is not None and drawn != parsed["nominal"]:
            skipped.append((rel, f"drawn {drawn} um, nominal {parsed['nominal']} um"))
            continue
        if info["mm"] is None:
            skipped.append((rel, "no thickness in the file name"))
            continue
        layers, notes = sheet_layers(built, info)
        name = stack_name(info, layers, rel)
        sig = signature(layers)
        sheet = os.path.basename(path) + (f", {parsed['date']}" if parsed["date"] else "")
        head = f"Sheet {sheet}. Pressed foil stack {parsed['nominal']} um"
        if notes:
            head += ". " + ". ".join(notes)
        # Hang the sheet citation on the first dielectric.
        hung = False
        rewritten = []
        for layer in layers:
            if not hung and layer[0] != "cu":
                kind, mm, glass, note, er, df = layer
                rewritten.append((kind, mm, glass, head + ". " + note, er, df))
                hung = True
            else:
                rewritten.append(layer)
        if not hung:
            kind, mm, plated, extra = rewritten[0]
            rewritten[0] = (kind, mm, plated, head + ". " + extra)
        spec = {"nominal": info["mm"], "source": rel.replace("\\", "/"), "layers": rewritten}
        previous = by_name.get(name)
        if previous and signature(previous["layers"]) == sig:
            skipped.append((rel, f"same stack as {name}"))
            continue
        if previous:
            name = name + "-b"
            if name in by_name:
                raise ValueError(f"third stack named {name}")
        by_name[name] = spec
        presets.append((name, spec))
    presets.sort(key=lambda item: item[0])
    return presets, skipped


def write_presets(presets, skipped):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "we_presets.py")
    lines = [
        '"""WEdirekt shop stacks parsed from the stack-up PDFs.',
        "",
        "Generated by we_stackup.py --from-pdfs. Do not edit by hand.",
        '"""',
        "",
        "PRESETS = [",
    ]
    for name, spec in presets:
        lines.append(f"    ({name!r}, {{")
        lines.append(f"        'nominal': {spec['nominal']!r},")
        lines.append(f"        'source': {spec['source']!r},")
        lines.append("        'layers': [")
        for layer in spec["layers"]:
            lines.append(f"            {layer!r},")
        lines.append("        ],")
        lines.append("    }),")
    lines.append("]")
    lines.append("")
    text = "\n".join(lines)
    if any(ord(ch) > 127 for ch in text):
        raise ValueError("presets are not ASCII")
    open(path, "w", encoding="ascii", newline="\n").write(text)
    print(f"wrote {len(presets)} presets, skipped {len(skipped)}")
    for rel, reason in skipped:
        print(f"  skip {rel}: {reason}")


def copper_orientation(layers):
    indexes = [i for i, layer in enumerate(layers) if layer[0] == "cu"]
    orient = {}
    for n, i in enumerate(indexes):
        if n == 0:
            orient[i] = 0
        elif n == len(indexes) - 1:
            orient[i] = 1
        elif i + 1 < len(layers) and layers[i + 1][0] == "core":
            orient[i] = 0
        elif i > 0 and layers[i - 1][0] == "core":
            orient[i] = 1
        else:
            orient[i] = 0
    return orient


def expand_glass(glass):
    parts = []
    for bit in glass.split(" + "):
        if " x" in bit:
            label, count = bit.rsplit(" x", 1)
            parts.extend([label] * int(count))
        else:
            parts.append(bit)
    return parts


def mirror_match(layers):
    """A mirrored prepreg pair is still a symmetric stack."""
    rev = list(reversed(layers))
    for left, right in zip(layers, rev):
        if left[0] != right[0] or abs(left[1] - right[1]) > 1e-6:
            return False
        if left[0] != "cu" and expand_glass(left[2]) != list(reversed(expand_glass(right[2]))):
            return False
    return True


def is_flex(name):
    return "-1F-" in name or "-2F-" in name


def build(name, spec):
    layers = spec["layers"]
    cu_i = [i for i, layer in enumerate(layers) if layer[0] == "cu"]
    if not cu_i:
        raise ValueError(f"{name} has no copper")
    orient = copper_orientation(layers)
    flex = "True" if is_flex(name) else "False"
    symmetric = "True" if mirror_match(layers) else "False"
    sub = gid()
    doc = gid()
    fields = [
        "STACKUPVERSION=1",
        f"STACKUPDOCUMENTID={doc}",
        f"STACKUPDOCUMENTREVISIONID={gid()}",
        "STACKUPDOCUMENTREVISIONDATE=10/24/2026",
        f"FEATURE_0ID={gid()}",
        "FEATURE_0NAME=Standard Stackup",
        f"FEATURE_1ID={gid()}",
        "FEATURE_1NAME=Impedance Calculator",
        f"LAYERMASTERSTACK_V8ID={doc}",
        "LAYERMASTERSTACK_V8TYPE=0",
        f"LAYERMASTERSTACK_V8NAME={name}",
        f"LAYERMASTERSTACK_V8ISFLEX={flex}",
        "LAYERMASTERSTACK_V8SHOWTOPDIELECTRIC=False",
        "LAYERMASTERSTACK_V8SHOWBOTTOMDIELECTRIC=False",
        "LAYERMASTERSTACK_V8STYLE=3",
        "DISPLAYUNIT=1",
        "LAYERMASTERSTACK_V8ROUGHNESSTYPE=NoRoughness",
        "LAYERMASTERSTACK_V8ROUGHNESSFACTORSR=0um",
        "LAYERMASTERSTACK_V8ROUGHNESSFACTORRF=1%",
        "LAYERMASTERSTACK_V8REALISTICRATIO=True",
        "LAYERMASTERSTACK_V8COPPERRESISTANCE=17.24nohm",
        "LAYERMASTERSTACK_V8VIAPLATINGTHICKNESS=0.7874mil",
        "LAYERMASTERSTACK_V8AMBIENTTEMPERATURE=20C",
        "LAYERMASTERSTACK_V8TEMPERATURERISE=50C",
        f"LAYERSUBSTACK_V8_0ID={sub}",
        "LAYERSUBSTACK_V8_0NAME=Board Layer Stack",
        f"LAYERSUBSTACK_V8_0SYMMETRIC={symmetric}",
        f"LAYERSUBSTACK_V8_0ISFLEX={flex}",
        "LAYERSUBSTACK_V8_0SHOWTOPDIELECTRIC=False",
        "LAYERSUBSTACK_V8_0SHOWBOTTOMDIELECTRIC=False",
        "LAYERSUBSTACK_V8_0TYPE=0",
        "LAYERSUBSTACK_V8_0USEDBYPRIMS=False",
        "LAYERSUBSTACK_V8_0SERVICE=False",
        "LAYERSUBSTACK_V8_0LIBRARYCOMPLIED=False",
        f"LAYERSUBSTACK_V8_0TEMPLATEID={gid()}",
    ]

    def ctx(n, title):
        tag = "LAYER_V8_" + str(n) + "_" + sub
        fields.extend([
            tag + "CONTEXT=0",
            tag + "USEDBYPRIMS=False",
            tag + "NAME=" + title,
            tag + "SHARED=0",
        ])

    n = 0
    diel_n = 0
    pp_n = 0
    core_n = 0
    cu_n = 0
    cu_ids = []

    def add_overlay(title, layer_id):
        nonlocal n
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={TYPE_OVERLAY}",
            f"LAYER_V8_{n}NAME={title}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
        ])
        ctx(n, title)
        n += 1

    def add_mask(title, layer_id):
        nonlocal n
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={TYPE_SOLDER}",
            f"LAYER_V8_{n}NAME={title}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE=3",
            f"LAYER_V8_{n}DIELHEIGHT={mil(MASK['mm'])}",
            f"LAYER_V8_{n}DIELCONST={MASK['er']}",
            f"LAYER_V8_{n}DIELMATERIAL={MASK['material']}",
            f"LAYER_V8_{n}$LSM$Thickness={mil(MASK['mm'])}",
            f"LAYER_V8_{n}$LSM$DielectricConstant={MASK['er']}",
            f"LAYER_V8_{n}$LSM$Material={MASK['material']}",
            f"LAYER_V8_{n}$LSM$Material.Frequency={MASK['freq']}",
            f"LAYER_V8_{n}$LSM$LossTangent={MASK['df']}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer={MASK['mfr']}",
            f"LAYER_V8_{n}$LSM$Material.Description={MASK['desc']}",
            f"LAYER_V8_{n}$LSM$Note={MASK['note']}",
        ])
        ctx(n, title)
        n += 1

    def add_copper(index):
        nonlocal n, cu_n
        lid = gid()
        cu_ids.append(lid)
        _kind, thick_mm, plated, extra = layers[index]
        thick = mil(thick_mm)
        if cu_n == 0:
            title, layer_id, place = "Top Layer", ID_TOP, 1
        elif cu_n == len(cu_i) - 1 and len(cu_i) > 1:
            title, layer_id, place = "Bottom Layer", ID_BOTTOM, 2
        else:
            title, layer_id, place = f"Inner Layer {cu_n}", ID_TOP + cu_n, 0
        process = "Plated base foil" if plated else "Base foil"
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={lid}",
            f"LAYER_V8_{n}TYPEID={TYPE_COPPER}",
            f"LAYER_V8_{n}NAME={title}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}COPTHICK={thick}",
            f"LAYER_V8_{n}COMPONENTPLACEMENT={place}",
        ])
        if place == 0:
            fields.append(f"LAYER_V8_{n}PULLBACKDISTANCE=0mil")
        fields.extend([
            f"LAYER_V8_{n}COPPERORIENTATION={orient[index]}",
            f"LAYER_V8_{n}$LSM$Thickness={thick}",
            f"LAYER_V8_{n}$LSM$ComponentPlacement={place}",
        ])
        if place == 0:
            fields.append(f"LAYER_V8_{n}$LSM$PullbackDistance=0mil")
        fields.extend([
            f"LAYER_V8_{n}$LSM$CopperOrientation={orient[index]}",
            f"LAYER_V8_{n}$LSM$Weight={weight_label(thick_mm)}",
            f"LAYER_V8_{n}$LSM$Material=WE-CU",
            f"LAYER_V8_{n}$LSM$Process={process}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=WEdirekt",
            f"LAYER_V8_{n}$LSM$Material.Description={extra}",
        ])
        ctx(n, title)
        n += 1
        cu_n += 1

    def add_dielectric(layer):
        nonlocal n, diel_n, pp_n, core_n
        kind, thick_mm, glass, note, er, df = layer
        if kind == "core":
            core_n += 1
            title = f"Core {core_n}"
        else:
            pp_n += 1
            title = f"Dielectric {pp_n}"
        _er, _df, _note, material, mfr, freq, tg = constants("flex" if "Pyralux" in glass else kind, thick_mm)
        type_id = TYPE_CORE if kind == "core" else TYPE_PREPREG
        diel_type = 1 if kind == "core" else 2
        fields.extend([
            f"LAYER_V8_{n}LAYERID={ID_DIELECTRIC0 + diel_n}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={type_id}",
            f"LAYER_V8_{n}NAME={title}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE={diel_type}",
            f"LAYER_V8_{n}DIELHEIGHT={mil(thick_mm)}",
            f"LAYER_V8_{n}DIELCONST={er:.2f}",
            f"LAYER_V8_{n}DIELMATERIAL={material}",
            f"LAYER_V8_{n}$LSM$Thickness={mil(thick_mm)}",
            f"LAYER_V8_{n}$LSM$DielectricConstant={er:.2f}",
            f"LAYER_V8_{n}$LSM$Material={material}",
            f"LAYER_V8_{n}$LSM$Material.Constructions={glass}",
            f"LAYER_V8_{n}$LSM$Material.Frequency={freq}",
            f"LAYER_V8_{n}$LSM$LossTangent={df}",
        ])
        if tg:
            fields.append(f"LAYER_V8_{n}$LSM$Material.GlassTransTemp={tg}C")
        fields.extend([
            f"LAYER_V8_{n}$LSM$Material.Manufacturer={mfr}",
            f"LAYER_V8_{n}$LSM$Material.Description={glass}, {thick_mm:.3f} mm, Er {er:.2f}, Df {df}",
            f"LAYER_V8_{n}$LSM$Note={note}",
        ])
        ctx(n, title)
        n += 1
        diel_n += 1

    add_overlay("Top Overlay", ID_OVERLAY_TOP)
    add_mask("Top Solder", ID_SOLDER_TOP)
    for i, layer in enumerate(layers):
        if layer[0] == "cu":
            add_copper(i)
        else:
            add_dielectric(layer)
    add_mask("Bottom Solder", ID_SOLDER_BOTTOM)
    add_overlay("Bottom Overlay", ID_OVERLAY_BOTTOM)
    if len(cu_ids) >= 2:
        fields.extend([
            "VIASPAN_V8_" + sub + "_0ID=" + gid(),
            "VIASPAN_V8_" + sub + "_0NAME=Thru 1:" + str(len(cu_i)),
            "VIASPAN_V8_" + sub + "_0TYPE=0",
            "VIASPAN_V8_" + sub + "_0FIRSTLAYERID=" + cu_ids[0],
            "VIASPAN_V8_" + sub + "_0LASTLAYERID=" + cu_ids[-1],
            "VIASPAN_V8_" + sub + "_0SYMMETRIC=False",
        ])
    branch = gid()
    section = gid()
    prefix = "BRANCHSECTIONSTACK_V8_" + branch + "_" + section
    fields.extend([
        "BRANCH_V8_0ID=" + branch,
        "BRANCH_V8_0NAME=Board",
        "BRANCHSECTION_V8_" + branch + "_0ID=" + section,
        "BRANCHSECTION_V8_" + branch + "_0NAME=Branch Section-1",
        prefix + "_0ID=" + gid(),
        prefix + "_0SOURCE=0",
        prefix + "_0DESCRIPTION=Board Layer Stack",
        prefix + "_0ISLEFTINTRUSUONSLINKED=True",
        prefix + "_0INTRUSIONLEFTBOTTOM=0m",
        prefix + "_0INTRUSIONLEFTTOP=0m",
        prefix + "_0ISRIGHTINTRUSIONLINKED=True",
        prefix + "_0INTRUSIONRIGHTBOTTOM=0m",
        prefix + "_0INTRUSIONRIGHTTOP=0m",
        prefix + "_0LAYERSTACKID=" + sub,
        prefix + "_0MATERIALUSAGE=0",
    ])
    text = "|".join(fields)
    if any(ord(ch) > 127 for ch in text):
        raise ValueError(name + " is not ASCII")
    return text


def emit(presets):
    os.makedirs(OUT, exist_ok=True)
    names = [name for name, _spec in presets]
    if len(names) != len(set(names)):
        raise ValueError("duplicate stackup name")
    for name, spec in presets:
        text = build(name, spec)
        open(os.path.join(OUT, name + ".stackup"), "w", encoding="ascii", newline="\n").write(text + "\n")
    keep = set(names)
    for old in os.listdir(OUT):
        if old.endswith(".stackup") and old[:-8] not in keep:
            os.remove(os.path.join(OUT, old))
    print(f"{len(names)} stackups")


def main():
    parser = argparse.ArgumentParser(description="Write WEdirekt Altium stackups")
    parser.add_argument("--from-pdfs", metavar="DIR", help="Reread the shop PDF folder and rewrite we_presets.py")
    args = parser.parse_args()
    if args.from_pdfs:
        presets, skipped = collect(args.from_pdfs)
        write_presets(presets, skipped)
    else:
        from we_presets import PRESETS as presets
    emit(presets)


if __name__ == "__main__":
    main()
