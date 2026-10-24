"""Build Altium .stackup files from the JLCPCB 1.6 mm impedance presets.

Source, read 2026-10-19:
  https://jlcpcb.com/impedance
  https://jlcpcb.com/help/article/multi-layer-pcb-standard-laminated-structures
  https://jlcpcb.com/help/article/user-guide-to-the-jlcpcb-impedance-calculator

The impedance page lists these builds for 1.6 mm, outer 1 oz, inner 0.5 oz.
Other thicknesses and copper weights are chosen in the page and were not in
the static listing.

Finished copper follows the laminate article of 2026-09-09, not the 0.035 mm
label still printed on the stackup diagram:
  outer 1 oz = 1.6 mil, inner 0.5 oz = 0.6 mil (0.0152 mm after deoxidation).
Pressed prepreg and core thicknesses are the diagram values.
Dk is JLCPCB's effective value. Df is not published; 0.02 is only there so
the Altium solver has a number.
2313 uses the same Dk as 3313, per JLCPCB.
The 4-layer "No requirement" build matches JLC04161H-7628, so it is not
written twice. The 6-layer "No requirement" build does not match 3313.
"""

import os
import uuid

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "JLCPCB_stackup")

ER = {
    "7628": 4.4,
    "3313": 4.1,
    "1080": 3.91,
    "2116": 4.16,
    "2313": 4.1,
}
CORE_ER = 4.6
# Finished copper from the 2026-09-09 laminate article.
OUTER_MM = 1.6 * 0.0254
INNER_MM = 0.0152
MASK_MIL = 1.2
MASK_ER = 3.8
DF_PLACEHOLDER = 0.02

# Top copper to bottom copper. "cu" is inserted by position:
# first and last are outer 1 oz, the rest are inner 0.5 oz.
PRESETS = {
    "JLC04161H-7628": "cu | pp:7628:0.21040 | cu | core:1.065 | cu | pp:7628:0.21040 | cu",
    "JLC04161H-3313": "cu | pp:3313:0.09940 | cu | core:1.265 | cu | pp:3313:0.09940 | cu",
    "JLC04161H-1080": "cu | pp:1080:0.07640 | cu | core:1.265 | cu | pp:1080:0.07640 | cu",
    "JLC04161H-7628A": "cu | pp:7628:0.218 | pp:1080:0.07640 | cu | core:0.865 | cu | pp:1080:0.07640 | pp:7628:0.218 | cu",
    "JLC04161H-3313A": "cu | pp:3313:0.107 | pp:3313:0.09940 | cu | core:1.065 | cu | pp:3313:0.09940 | pp:3313:0.107 | cu",
    "JLC04161H-1080A": "cu | pp:1080:0.084 | pp:1080:0.07640 | cu | core:1.065 | cu | pp:1080:0.07640 | pp:1080:0.084 | cu",
    "JLC04161H-7628B": "cu | pp:7628:0.218 | pp:7628:0.218 | pp:2116:0.11640 | cu | core:0.4 | cu | pp:2116:0.11640 | pp:7628:0.218 | pp:7628:0.218 | cu",
    "JLC04161H-2116A": "cu | pp:2116:0.124 | pp:7628:0.218 | pp:2116:0.11640 | cu | core:0.6 | cu | pp:2116:0.11640 | pp:7628:0.218 | pp:2116:0.124 | cu",
    "JLC04161H-2116B": "cu | pp:2116:0.124 | pp:7628:0.21040 | cu | core:0.865 | cu | pp:7628:0.21040 | pp:2116:0.124 | cu",
    "JLC04161H-2116C": "cu | pp:2116:0.124 | pp:1080:0.07640 | cu | core:1.065 | cu | pp:1080:0.07640 | pp:2116:0.124 | cu",
    "JLC04161H-1080B": "cu | pp:1080:0.084 | pp:1080:0.084 | pp:1080:0.07640 | cu | core:1.065 | cu | pp:1080:0.07640 | pp:1080:0.084 | pp:1080:0.084 | cu",
    "JLC04161H-7628G": "cu | pp:7628:0.218 | pp:7628:0.218 | pp:1080:0.07640 | cu | core:0.5 | cu | pp:1080:0.07640 | pp:7628:0.218 | pp:7628:0.218 | cu",
    "JLC04161H-2116": "cu | pp:2116:0.11640 | cu | core:1.265 | cu | pp:2116:0.11640 | cu",
    "JLC04161H-7628E": "cu | pp:7628:0.218 | pp:7628:0.21040 | cu | core:0.6 | cu | pp:7628:0.21040 | pp:7628:0.218 | cu",
    "JLC04161H-2116D": "cu | pp:2116:0.124 | pp:7628:0.21040 | cu | core:0.7 | cu | pp:7628:0.21040 | pp:2116:0.124 | cu",
    "JLC04161H-7628F": "cu | pp:7628:0.218 | pp:7628:0.218 | pp:7628:0.21040 | cu | core:0.25 | cu | pp:7628:0.21040 | pp:7628:0.218 | pp:7628:0.218 | cu",
    "JLC04161H-2116E": "cu | pp:2116:0.124 | pp:2116:0.11640 | cu | core:0.865 | cu | pp:2116:0.11640 | pp:2116:0.124 | cu",
    "JLC04161H-7628C": "cu | pp:7628:0.218 | pp:7628:0.218 | pp:7628:0.21040 | cu | core:0.15 | cu | pp:7628:0.21040 | pp:7628:0.218 | pp:7628:0.218 | cu",
    "JLC06161H-NoRequirement": "cu | pp:3313:0.09940 | cu | core:0.55 | cu | pp:2116:0.11640 | cu | core:0.55 | cu | pp:3313:0.09940 | cu",
    "JLC06161H-3313": "cu | pp:3313:0.09940 | cu | core:0.55 | cu | pp:2116:0.1088 | cu | core:0.55 | cu | pp:3313:0.09940 | cu",
    "JLC06161H-7628": "cu | pp:7628:0.21040 | cu | core:0.4 | cu | pp:7628:0.2028 | cu | core:0.4 | cu | pp:7628:0.21040 | cu",
    "JLC06161H-7628D": "cu | pp:7628:0.216 | pp:7628:0.20840 | cu | core:0.2 | cu | pp:7628:0.20080 | cu | core:0.2 | cu | pp:7628:0.20840 | pp:7628:0.216 | cu",
    "JLC06161H-1080": "cu | pp:1080:0.07640 | cu | core:0.55 | cu | pp:7628:0.21040 | cu | core:0.55 | cu | pp:1080:0.07640 | cu",
    "JLC06161H-2116A": "cu | pp:2116:0.11640 | cu | core:0.13 | cu | pp:2116:0.11640 | core:0.7 | pp:2116:0.11640 | cu | core:0.13 | cu | pp:2116:0.11640 | cu",
    "JLC06161H-1080A": "cu | pp:1080:0.07640 | cu | core:0.6 | cu | pp:3313:0.09940 | cu | core:0.6 | cu | pp:1080:0.07640 | cu",
    "JLC06161H-3313C": "cu | pp:3313:0.107 | pp:1080:0.07640 | cu | core:0.4 | cu | pp:1080:0.07640 | pp:1080:0.07640 | cu | core:0.4 | cu | pp:1080:0.07840 | pp:3313:0.107 | cu",
    "JLC06161H-1080B": "cu | pp:1080:0.07640 | cu | core:0.1 | cu | pp:7628:0.21040 | core:0.7 | pp:7628:0.21040 | cu | core:0.1 | cu | pp:1080:0.07640 | cu",
    "JLC06161H-3313E": "cu | pp:3313:0.09940 | cu | core:0.1 | cu | pp:7628:0.21040 | core:0.7 | pp:7628:0.21040 | cu | core:0.1 | cu | pp:3313:0.09940 | cu",
    "JLC06161H-1080C": "cu | pp:1080:0.07640 | cu | core:0.075 | cu | pp:7628:0.21040 | core:0.7 | pp:7628:0.21040 | cu | core:0.075 | cu | pp:1080:0.07640 | cu",
    "JLC06161H-2116B": "cu | pp:2116:0.11640 | cu | core:0.5 | cu | pp:1080:0.07640 | pp:1080:0.07640 | cu | core:0.5 | cu | pp:2116:0.11640 | cu",
    "JLC06161H-2116": "cu | pp:2116:0.127 | pp:2313:0.09640 | cu | core:0.3 | cu | pp:7628:0.20840 | pp:7628:0.20840 | cu | core:0.3 | cu | pp:2313:0.09640 | pp:2116:0.127 | cu",
    "JLC06161H-7628B": "cu | pp:7628:0.218 | pp:1080:0.07640 | cu | core:0.35 | cu | pp:1080:0.07640 | pp:1080:0.07640 | cu | core:0.35 | cu | pp:1080:0.07640 | pp:7628:0.218 | cu",
    "JLC06161H-3313D": "cu | pp:3313:0.107 | pp:1080:0.07640 | cu | core:0.25 | cu | pp:7628:0.21040 | pp:2116:0.124 | pp:7628:0.21040 | cu | core:0.25 | cu | pp:1080:0.07640 | pp:3313:0.107 | cu",
    "JLC06161H-2116C": "cu | pp:2116:0.127 | pp:2116:0.11940 | cu | core:0.3 | cu | pp:2116:0.11940 | pp:2116:0.127 | pp:2116:0.11940 | cu | core:0.3 | cu | pp:2116:0.11940 | pp:2116:0.127 | cu",
    "JLC06161H-7628A": "cu | pp:7628:0.218 | pp:7628:0.218 | pp:1080:0.07640 | cu | core:0.1 | cu | pp:2116:0.11640 | pp:2116:0.11640 | cu | core:0.1 | cu | pp:1080:0.07640 | pp:7628:0.218 | pp:7628:0.218 | cu",
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


def parse(spec):
    layers = []
    for part in spec.split("|"):
        part = part.strip()
        kind, _, rest = part.partition(":")
        if kind == "cu":
            layers.append(("cu",))
        elif kind == "pp":
            style, thick = rest.split(":")
            layers.append(("pp", style, float(thick)))
        elif kind == "core":
            layers.append(("core", float(rest)))
        else:
            raise ValueError(part)
    return layers


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


def build(code, spec):
    layers = parse(spec)
    cu_i = [i for i, layer in enumerate(layers) if layer[0] == "cu"]
    if len(cu_i) not in (4, 6):
        raise ValueError(f"{code} has {len(cu_i)} copper layers")
    orient = copper_orientation(layers)
    sub = gid()
    doc = gid()
    top_cu = gid()
    bot_cu = gid()
    fields = [
        "STACKUPVERSION=1",
        f"STACKUPDOCUMENTID={doc}",
        f"STACKUPDOCUMENTREVISIONID={gid()}",
        "STACKUPDOCUMENTREVISIONDATE=10/19/2026",
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
        "LAYERSUBSTACK_V8_0SYMMETRIC=True",
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
        lid = gid()
        thick = f"{MASK_MIL:.4f}mil"
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={lid}",
            f"LAYER_V8_{n}TYPEID={TYPE_SOLDER}",
            f"LAYER_V8_{n}NAME={name}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE=3",
            f"LAYER_V8_{n}DIELHEIGHT={thick}",
            f"LAYER_V8_{n}DIELCONST={MASK_ER}",
            f"LAYER_V8_{n}DIELMATERIAL=JLC-SM",
            f"LAYER_V8_{n}$LSM$Thickness={thick}",
            f"LAYER_V8_{n}$LSM$DielectricConstant={MASK_ER}",
            f"LAYER_V8_{n}$LSM$Material=JLC-SM",
            f"LAYER_V8_{n}$LSM$Material.Color=#FF008000",
            f"LAYER_V8_{n}$LSM$Material.Frequency=1GHz",
            f"LAYER_V8_{n}$LSM$LossTangent={DF_PLACEHOLDER}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=JLCPCB",
            f"LAYER_V8_{n}$LSM$Material.Description=C1 and C3 1.2mil, C2 over copper 0.6mil, Er 3.8",
            f"LAYER_V8_{n}$LSM$Note=Df {DF_PLACEHOLDER} is not published by JLCPCB",
        ])
        ctx(n, name)
        n += 1

    def add_copper(index, is_outer):
        nonlocal n, cu_n
        lid = gid()
        cu_ids.append(lid)
        if cu_n == 0:
            name, layer_id, place = "Top Layer", ID_TOP, 1
            weight, thick_mm = "1oz", OUTER_MM
            process = "Plated base foil"
        elif cu_n == len(cu_i) - 1:
            name, layer_id, place = "Bottom Layer", ID_BOTTOM, 2
            weight, thick_mm = "1oz", OUTER_MM
            process = "Plated base foil"
        else:
            name, layer_id, place = f"Inner Layer {cu_n}", ID_TOP + cu_n, 0
            weight, thick_mm = "0.5oz", INNER_MM
            process = "Base foil"
        thick = mil(thick_mm)
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
        if not is_outer:
            fields.append(f"LAYER_V8_{n}PULLBACKDISTANCE=0mil")
        fields.extend([
            f"LAYER_V8_{n}COPPERORIENTATION={orient[index]}",
            f"LAYER_V8_{n}$LSM$Thickness={thick}",
            f"LAYER_V8_{n}$LSM$ComponentPlacement={place}",
        ])
        if not is_outer:
            fields.append(f"LAYER_V8_{n}$LSM$PullbackDistance=0mil")
        fields.extend([
            f"LAYER_V8_{n}$LSM$CopperOrientation={orient[index]}",
            f"LAYER_V8_{n}$LSM$Weight={weight}",
            f"LAYER_V8_{n}$LSM$Material=JLC-CU",
            f"LAYER_V8_{n}$LSM$Process={process}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=JLCPCB",
            f"LAYER_V8_{n}$LSM$Material.Description=Finished {weight}, {thick_mm:.4f} mm",
        ])
        ctx(n, name)
        n += 1
        cu_n += 1

    def add_dielectric(kind, style, thick_mm):
        nonlocal n, diel_n, pp_n, core_n
        er = CORE_ER if kind == "core" else ER[style]
        if kind == "core":
            core_n += 1
            name = f"Core {core_n}"
        else:
            pp_n += 1
            name = f"Dielectric {pp_n}"
        type_id = TYPE_CORE if kind == "core" else TYPE_PREPREG
        diel_type = 1 if kind == "core" else 2
        thick = mil(thick_mm)
        construction = "Core" if kind == "core" else f"{style} x1"
        fields.extend([
            f"LAYER_V8_{n}LAYERID={ID_DIELECTRIC0 + diel_n}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={type_id}",
            f"LAYER_V8_{n}NAME={name}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE={diel_type}",
            f"LAYER_V8_{n}DIELHEIGHT={thick}",
            f"LAYER_V8_{n}DIELCONST={er}",
            f"LAYER_V8_{n}DIELMATERIAL=JLC-{style if kind == 'pp' else 'CORE'}",
            f"LAYER_V8_{n}$LSM$Thickness={thick}",
            f"LAYER_V8_{n}$LSM$DielectricConstant={er}",
            f"LAYER_V8_{n}$LSM$Material=JLC-{style if kind == 'pp' else 'CORE'}",
            f"LAYER_V8_{n}$LSM$Material.Constructions={construction}",
            f"LAYER_V8_{n}$LSM$Material.Frequency=1GHz",
            f"LAYER_V8_{n}$LSM$LossTangent={DF_PLACEHOLDER}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=JLCPCB",
            f"LAYER_V8_{n}$LSM$Material.Description={construction}, pressed thickness {thick_mm} mm, Dk {er}",
            f"LAYER_V8_{n}$LSM$Note=Dk from JLCPCB. Df {DF_PLACEHOLDER} is not published",
        ])
        ctx(n, name)
        n += 1
        diel_n += 1

    add_overlay("Top Overlay", ID_OVERLAY_TOP)
    add_mask("Top Solder", ID_SOLDER_TOP)
    for i, layer in enumerate(layers):
        if layer[0] == "cu":
            add_copper(i, cu_n in (0, len(cu_i) - 1))
        elif layer[0] == "pp":
            add_dielectric("pp", layer[1], layer[2])
        else:
            add_dielectric("core", "core", layer[1])
    add_mask("Bottom Solder", ID_SOLDER_BOTTOM)
    add_overlay("Bottom Overlay", ID_OVERLAY_BOTTOM)

    span = gid()
    fields.extend([
        "VIASPAN_V8_" + sub + "_0ID=" + span,
        "VIASPAN_V8_" + sub + "_0NAME=Thru 1:" + str(len(cu_i)),
        "VIASPAN_V8_" + sub + "_0TYPE=0",
        "VIASPAN_V8_" + sub + "_0FIRSTLAYERID=" + cu_ids[0],
        "VIASPAN_V8_" + sub + "_0LASTLAYERID=" + cu_ids[-1],
        "VIASPAN_V8_" + sub + "_0SYMMETRIC=False",
    ])
    branch = gid()
    section = gid()
    stack_id = gid()
    prefix = "BRANCHSECTIONSTACK_V8_" + branch + "_" + section
    fields.extend([
        "BRANCH_V8_0ID=" + branch,
        "BRANCH_V8_0NAME=Board",
        "BRANCHSECTION_V8_" + branch + "_0ID=" + section,
        "BRANCHSECTION_V8_" + branch + "_0NAME=Branch Section-1",
        prefix + "_0ID=" + stack_id,
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
    return "|".join(fields)


def thickness_mm(spec):
    total = 2 * MASK_MIL * 0.0254
    for layer in parse(spec):
        if layer[0] == "cu":
            total += 0
        elif layer[0] == "pp":
            total += layer[2]
        else:
            total += layer[1]
    cu = sum(1 for layer in parse(spec) if layer[0] == "cu")
    total += OUTER_MM * 2 + INNER_MM * (cu - 2)
    return total


def main():
    os.makedirs(OUT, exist_ok=True)
    for code, spec in PRESETS.items():
        text = build(code, spec)
        path = os.path.join(OUT, code + ".stackup")
        open(path, "w", encoding="ascii", newline="\n").write(text + "\n")
        cu = sum(1 for layer in parse(spec) if layer[0] == "cu")
        print(f"{code:24} {cu}L  {thickness_mm(spec):.3f} mm")


if __name__ == "__main__":
    main()
