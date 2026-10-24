"""Build Altium .stackup files for Beta LAYOUT PCB-OVERSEAS.

Read 2026-10-20 from the PCB-OVERSEAS tab:
  https://de.beta-layout.com/leiterplatten/infos/spezifikationen/#2

Er and Df for S1000-2 and KB-6164 are the typicals on the datasheets
linked from the Datenblaetter tab:
  https://de.beta-layout.com/leiterplatten/infos/spezifikationen/#5
  S1000-2  Er 4.4 Df 0.015 at 1 GHz, specimen 1.6 mm 8x7628
  KB-6164  Er 4.6 Df 0.016 at 1 GHz, RC50%, same specimen
The tab has no S1141 sheet. Those builds keep the Shengyi S1141 typical.

PCB-POOL and PCB-OVERSEAS publish separate solder-mask tables.
Overseas mask thickness is 30 um, the middle of that table's 20-40 um
on the laminate. Er 4.3 and Df 0.029 are the TAIYO PSR-2000 CD08G-HF1
initial values at 1 MHz. The same table requires at least 10 um on a
trace. The PCB-POOL mask table is applied only to the DE104 builds.

One core cell is printed as "0, mm"; it uses the other cores in that
table. One inner copper is printed as 3 um in a 35 um build, and one
prepreg is printed as 32116; both follow the matching layer on the
other side of that stack.

PCB-POOL builds are the three Lagenaufbau tables on tab #1:
  https://de.beta-layout.com/leiterplatten/infos/spezifikationen/#1
All three name ISOLA 104 ML. Dk and Df come from the DE104 datasheet
linked there. A core uses the matching glass row. A prepreg with no
row of its own says so in the layer note. The mask is Peters Elpemer
2467, not the overseas TAIYO mask.
"""

import os
import re
import uuid
from html.parser import HTMLParser

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BetaLayout_stackup")
HTML = [
    "_cat_77.html",
    "_cat_78.html",
    "_cat_74.html",
    "_cat_75.html",
    "_cat_76.html",
]

# er, df, Tg from the page label, datasheet note
MATERIALS = {
    "S1000-2": (
        4.4, 0.015, 180,
        "Beta datasheet SHENGYI S1000-2. Er 4.4 Df 0.015 at 1 GHz, IPC-TM-650 2.5.5.9, 1.6 mm 8x7628. "
        "Stackup page label TG170. Datasheet Tg DSC 180 C, DMA 185 C",
    ),
    "KB-6164": (
        4.6, 0.016, 140,
        "Beta datasheet KB-6164, prepreg KB-6064. Er 4.6 Df 0.016 at 1 GHz, RC50%, 1.6 mm 8x7628. "
        "Stackup page label TG135. Datasheet Tg DSC 140 C",
    ),
    "S1141": (
        4.4, 0.013, 135,
        "No S1141 datasheet on the Beta datasheet tab. Er 4.4 Df 0.013 are the Shengyi S1141 typical at 1 GHz, 1.6 mm 8x7628",
    ),
    "S1141-2": (
        4.4, 0.013, 135,
        "No S1141-2 datasheet on the Beta datasheet tab. Er 4.4 Df 0.013 are the Shengyi S1141 typical at 1 GHz, 1.6 mm 8x7628",
    ),
    "DE104": (
        4.37, 0.022, 135,
        "Beta datasheet ISOLA DE104. Product typical Dk 4.37 Df 0.022 at 1 GHz, IPC-TM-650 2.5.5.9. Tg DSC 135 C",
        "Isola",
    ),
}

# TAIYO PSR-2000 CD08G-HF1 green. Thickness is the PCB-OVERSEAS
# mask rule: middle of 20-40 um on the laminate.
MASK_MM = 0.030
MASK_ER = 4.3
MASK_DF = 0.029

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


def clean(text):
    return " ".join(text.replace("\xa0", " ").replace("\u03bc", "um").split())


def number_before(text, unit):
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*" + unit, clean(text))
    if not match:
        raise ValueError(text)
    return float(match.group(1).replace(",", "."))


def construction(text):
    parts = re.findall(r"(\d+)\s*x\s*(\d{3,5})", clean(text))
    if not parts:
        return "Core", ""
    bits = []
    note = ""
    for count, glass in parts:
        if glass == "32116":
            note = "Page prints glass 32116. The matching prepreg on the other side is 2116 at the same thickness"
            glass = "2116"
        bits.append(f"{glass} x{count}")
    return " + ".join(bits), note


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.stack = []
        self.capture = None
        self.heading = ""
        self.in_h = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append({
                "caption": "",
                "rows": [],
                "row": None,
                "cell": None,
                "heading": self.heading,
            })
        elif tag == "h4":
            self.in_h = True
            self.heading = ""
        elif tag == "tr" and self.stack:
            self.stack[-1]["row"] = []
        elif tag in ("td", "th") and self.stack and self.stack[-1]["row"] is not None:
            self.stack[-1]["cell"] = ""
        elif tag == "caption" and self.stack:
            self.stack[-1]["cell"] = ""
            self.capture = "caption"

    def handle_endtag(self, tag):
        if tag == "h4":
            self.in_h = False
        elif tag == "caption" and self.stack:
            self.stack[-1]["caption"] = clean(self.stack[-1].get("cell") or "")
            self.capture = None
        elif tag in ("td", "th") and self.stack and self.stack[-1]["row"] is not None:
            self.stack[-1]["row"].append((self.stack[-1].get("cell") or "").strip())
            self.stack[-1]["cell"] = None
        elif tag == "tr" and self.stack and self.stack[-1]["row"] is not None:
            cells = [c for c in self.stack[-1]["row"] if c]
            if cells:
                self.stack[-1]["rows"].append(cells)
            self.stack[-1]["row"] = None
        elif tag == "table" and self.stack:
            table = self.stack.pop()
            if "Lagenaufbau" in table["caption"]:
                self.tables.append(table)

    def handle_data(self, data):
        if self.in_h:
            self.heading += data
        if not self.stack:
            return
        if self.capture == "caption" or self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"] = (self.stack[-1].get("cell") or "") + data


def parse_table(table):
    nominal = number_before(table["caption"].split("fur", 1)[-1] if "fur" in clean(table["caption"]) else table["caption"].split("für", 1)[1], "mm")
    layers = []
    material = None
    started = False
    for cells in table["rows"]:
        joined = clean(" ".join(cells))
        low = joined.lower()
        if not started:
            if low.startswith("lage"):
                started = True
            continue
        if "kupfer" in low and "dicke kupfer" not in low:
            plated = "galvanik" in low
            note = ""
            try:
                thick = number_before(joined, "u") / 1000.0
            except ValueError:
                bare = re.search(r"\b(35|70)\b", joined)
                if not bare:
                    raise ValueError(joined)
                thick = int(bare.group(1)) / 1000.0
            if abs(thick - 0.003) < 1e-6:
                thick = 0.035
                note = "Page prints 3 um. The other copper in this 35 um build is 35 um"
            layers.append(("cu", thick, plated, note))
        elif "prepreg" in low:
            glass, note = construction(joined)
            layers.append(("pp", number_before(joined, "mm"), glass, note))
        elif "kern" in low:
            if re.search(r"0,\s*mm", joined):
                layers.append(("core", None, "Core", ""))
            else:
                glass, note = construction(joined)
                layers.append(("core", number_before(joined, "mm"), glass, note))
        elif re.search(r"S1000-2|KB-6164|S1141", joined):
            material = re.search(r"(S1000-2|KB-6164|S1141-2|S1141)", joined).group(1)
    cores = [layer[1] for layer in layers if layer[0] == "core" and layer[1] is not None]
    for i, layer in enumerate(layers):
        if layer[0] == "core" and layer[1] is None:
            if len(set(cores)) != 1:
                raise ValueError("blank core in " + table["caption"])
            layers[i] = (
                "core",
                cores[0],
                "Core",
                "Page prints 0, mm for this core. Thickness is the other cores in the same table",
            )
    return {
        "nominal": nominal,
        "material": material,
        "layers": layers,
    }


def load_builds():
    root = os.path.dirname(os.path.abspath(__file__))
    builds = []
    for name in HTML:
        parser = Tables()
        parser.feed(open(os.path.join(root, name), encoding="utf-8").read())
        for table in parser.tables:
            builds.append(parse_table(table))
    return builds


def nominal_label(mm):
    label = f"{mm:.2f}".rstrip("0").rstrip(".")
    if "." not in label:
        label += ".0"
    return label + "mm"


def copper_tag(layers):
    cu = [layer[1] for layer in layers if layer[0] == "cu"]
    if len(set(cu)) == 1:
        return f"{int(round(cu[0] * 1000))}um"
    if len(set(cu[1:-1])) == 1:
        return f"{int(round(cu[0] * 1000))}-{int(round(cu[1] * 1000))}um"
    return "-".join(str(int(round(v * 1000))) for v in cu) + "um"


def base_name(build):
    cu_n = sum(1 for layer in build["layers"] if layer[0] == "cu")
    return f"BL-{cu_n}L-{copper_tag(build['layers'])}-{build['material']}-{nominal_label(build['nominal'])}"


def signature(build):
    return tuple((layer[0], round(layer[1], 4), layer[2]) for layer in build["layers"])


def named_builds(builds):
    unique = []
    seen = set()
    for build in builds:
        key = (build["material"], round(build["nominal"], 3), signature(build))
        if key in seen:
            continue
        seen.add(key)
        unique.append(build)
    groups = {}
    for build in unique:
        groups.setdefault(base_name(build), []).append(build)
    named = []
    for name, group in groups.items():
        if len(group) == 1:
            named.append((name, group[0]))
            continue
        for build in group:
            core = next(layer[1] for layer in build["layers"] if layer[0] == "core")
            named.append((f"{name}-core{nominal_label(core)[:-2]}", build))
    return named


def gid():
    return "{" + str(uuid.uuid4()).upper() + "}"


def mil(mm):
    return f"{mm / 0.0254:.4f}mil"


def weight_label(mm):
    if abs(mm - 0.035) < 1e-6:
        return "1oz"
    if abs(mm - 0.070) < 1e-6:
        return "2oz"
    return f"{mm:.3f}mm"


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


def is_symmetric(layers):
    rev = list(reversed(layers))
    for left, right in zip(layers, rev):
        if left[0] != right[0] or abs(left[1] - right[1]) > 1e-6:
            return False
        if left[0] != "cu" and left[2] != right[2]:
            return False
    return True


def build(code, build_spec):
    layers = build_spec["layers"]
    material = build_spec["material"]
    row = MATERIALS[material]
    er, df, tg, source = row[:4]
    mfr = row[4] if len(row) > 4 else "Beta LAYOUT"
    mask = build_spec.get("mask") or {
        "mm": MASK_MM,
        "er": MASK_ER,
        "df": MASK_DF,
        "material": "TAIYO-PSR2000-CD08G",
        "color": "#FF008000",
        "freq": "1MHz",
        "mfr": "TAIYO",
        "desc": "PSR-2000 CD08G-HF1 green. 30 um, middle of the PCB-OVERSEAS mask rule 20-40 um on the laminate",
        "note": "Er 4.3 Df 0.029 at 1 MHz, initial. Conditioned Er 5.3 Df 0.037. Datasheet range on copper after cure is 10-20 um. Rule G is at least 10 um on a trace and 8 um at a corner",
    }
    cu_i = [i for i, layer in enumerate(layers) if layer[0] == "cu"]
    if len(cu_i) not in (2, 4, 6, 8, 10):
        raise ValueError(f"{code} has {len(cu_i)} copper layers")
    orient = copper_orientation(layers)
    sub = gid()
    doc = gid()
    symmetric = "True" if is_symmetric(layers) else "False"
    fields = [
        "STACKUPVERSION=1",
        f"STACKUPDOCUMENTID={doc}",
        f"STACKUPDOCUMENTREVISIONID={gid()}",
        "STACKUPDOCUMENTREVISIONDATE=10/20/2026",
        f"FEATURE_0ID={gid()}",
        "FEATURE_0NAME=Standard Stackup",
        f"FEATURE_1ID={gid()}",
        "FEATURE_1NAME=Impedance Calculator",
        f"LAYERMASTERSTACK_V8ID={doc}",
        "LAYERMASTERSTACK_V8TYPE=0",
        f"LAYERMASTERSTACK_V8NAME={code}",
        "LAYERMASTERSTACK_V8ISFLEX=False",
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
        "LAYERSUBSTACK_V8_0ISFLEX=False",
        "LAYERSUBSTACK_V8_0SHOWTOPDIELECTRIC=False",
        "LAYERSUBSTACK_V8_0SHOWBOTTOMDIELECTRIC=False",
        "LAYERSUBSTACK_V8_0TYPE=0",
        "LAYERSUBSTACK_V8_0USEDBYPRIMS=False",
        "LAYERSUBSTACK_V8_0SERVICE=False",
        "LAYERSUBSTACK_V8_0LIBRARYCOMPLIED=False",
        f"LAYERSUBSTACK_V8_0TEMPLATEID={gid()}",
    ]

    def ctx(n, name):
        tag = "LAYER_V8_" + str(n) + "_" + sub
        fields.extend([
            tag + "CONTEXT=0",
            tag + "USEDBYPRIMS=False",
            tag + "NAME=" + name,
            tag + "SHARED=0",
        ])

    n = 0
    diel_n = 0
    pp_n = 0
    core_n = 0
    cu_n = 0
    cu_ids = []

    def add_overlay(name, layer_id):
        nonlocal n
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={TYPE_OVERLAY}",
            f"LAYER_V8_{n}NAME={name}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
        ])
        ctx(n, name)
        n += 1

    def add_mask(name, layer_id):
        nonlocal n
        thick = mil(mask["mm"])
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={TYPE_SOLDER}",
            f"LAYER_V8_{n}NAME={name}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE=3",
            f"LAYER_V8_{n}DIELHEIGHT={thick}",
            f"LAYER_V8_{n}DIELCONST={mask['er']}",
            f"LAYER_V8_{n}DIELMATERIAL={mask['material']}",
            f"LAYER_V8_{n}$LSM$Thickness={thick}",
            f"LAYER_V8_{n}$LSM$DielectricConstant={mask['er']}",
            f"LAYER_V8_{n}$LSM$Material={mask['material']}",
        ])
        if mask.get("color"):
            fields.append(f"LAYER_V8_{n}$LSM$Material.Color={mask['color']}")
        fields.extend([
            f"LAYER_V8_{n}$LSM$Material.Frequency={mask['freq']}",
            f"LAYER_V8_{n}$LSM$LossTangent={mask['df']}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer={mask['mfr']}",
            f"LAYER_V8_{n}$LSM$Material.Description={mask['desc']}",
            f"LAYER_V8_{n}$LSM$Note={mask['note']}",
        ])
        ctx(n, name)
        n += 1

    def add_copper(index):
        nonlocal n, cu_n
        lid = gid()
        cu_ids.append(lid)
        _, thick_mm, plated, extra = layers[index]
        thick = mil(thick_mm)
        weight = weight_label(thick_mm)
        if cu_n == 0:
            name, layer_id, place = "Top Layer", ID_TOP, 1
        elif cu_n == len(cu_i) - 1:
            name, layer_id, place = "Bottom Layer", ID_BOTTOM, 2
        else:
            name, layer_id, place = f"Inner Layer {cu_n}", ID_TOP + cu_n, 0
        if place == 0 and not plated:
            process = "Base foil"
            desc = f"Base foil {thick_mm:.3f} mm"
        else:
            process = "Plated base foil"
            desc = f"Finished {thick_mm:.3f} mm including plating"
        if extra:
            desc += ". " + extra
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={lid}",
            f"LAYER_V8_{n}TYPEID={TYPE_COPPER}",
            f"LAYER_V8_{n}NAME={name}",
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
            f"LAYER_V8_{n}$LSM$Weight={weight}",
            f"LAYER_V8_{n}$LSM$Material=BL-CU",
            f"LAYER_V8_{n}$LSM$Process={process}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=Beta LAYOUT",
            f"LAYER_V8_{n}$LSM$Material.Description={desc}",
        ])
        ctx(n, name)
        n += 1
        cu_n += 1

    def add_dielectric(layer):
        nonlocal n, diel_n, pp_n, core_n
        kind, thick_mm, glass, extra = layer[:4]
        layer_er = er if len(layer) < 5 or layer[4] is None else layer[4]
        layer_df = df if len(layer) < 6 or layer[5] is None else layer[5]
        if kind == "core":
            core_n += 1
            name = f"Core {core_n}"
        else:
            pp_n += 1
            name = f"Dielectric {pp_n}"
        type_id = TYPE_CORE if kind == "core" else TYPE_PREPREG
        diel_type = 1 if kind == "core" else 2
        thick = mil(thick_mm)
        mat = "BL-" + material
        if len(layer) >= 5 and layer[4] is not None:
            note = extra or source
        else:
            note = source + ". Same typical on core and prepreg"
            if extra:
                note += ". " + extra
        fields.extend([
            f"LAYER_V8_{n}LAYERID={ID_DIELECTRIC0 + diel_n}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={type_id}",
            f"LAYER_V8_{n}NAME={name}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE={diel_type}",
            f"LAYER_V8_{n}DIELHEIGHT={thick}",
            f"LAYER_V8_{n}DIELCONST={layer_er:.2f}",
            f"LAYER_V8_{n}DIELMATERIAL={mat}",
            f"LAYER_V8_{n}$LSM$Thickness={thick}",
            f"LAYER_V8_{n}$LSM$DielectricConstant={layer_er:.2f}",
            f"LAYER_V8_{n}$LSM$Material={mat}",
            f"LAYER_V8_{n}$LSM$Material.Constructions={glass}",
            f"LAYER_V8_{n}$LSM$Material.Frequency=1GHz",
            f"LAYER_V8_{n}$LSM$LossTangent={layer_df}",
            f"LAYER_V8_{n}$LSM$Material.GlassTransTemp={tg}C",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer={mfr}",
            f"LAYER_V8_{n}$LSM$Material.Description={glass}, {thick_mm:.3f} mm, Er {layer_er:.2f}, Df {layer_df}",
            f"LAYER_V8_{n}$LSM$Note={note}",
        ])
        ctx(n, name)
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
        raise ValueError(code + " is not ASCII")
    return text


def collect():
    from beta_pool_presets import PRESETS as POOL
    from beta_presets import PRESETS
    return list(PRESETS) + list(POOL)


def emit(presets):
    os.makedirs(OUT, exist_ok=True)
    names = [name for name, _ in presets]
    if len(names) != len(set(names)):
        raise ValueError("duplicate stackup name")
    for name, spec in presets:
        spec = dict(spec)
        spec["layers"] = [tuple(layer) for layer in spec["layers"]]
        text = build(name, spec)
        open(os.path.join(OUT, name + ".stackup"), "w", encoding="ascii", newline="\n").write(text + "\n")
    return names


def main():
    names = emit(collect())
    keep = set(names)
    for old in os.listdir(OUT):
        if old.endswith(".stackup") and old[:-8] not in keep:
            os.remove(os.path.join(OUT, old))
    print(f"{len(names)} stackups")


if __name__ == "__main__":
    main()
