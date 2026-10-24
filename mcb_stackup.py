"""Build Altium .stackup files for the Multi-CB defined layer builds.

Read 2026-10-20:
  https://www.multi-circuit-boards.eu/leiterplatten-design-hilfe/lagenaufbau/impedanzen-beispiele.html
  https://www.multi-circuit-boards.eu/fileadmin/pdf/leiterplatten_lagenaufbau/Multi-CB_Definierter_Lagenaufbau_Impedanzen_de.pdf
  https://www.multi-circuit-boards.eu/fileadmin/pdf/leiterplatten_lagenaufbau/Multi-CB_Definierter_Lagenaufbau-Hybrid_Impedanzen_en.pdf

Pressed prepreg thicknesses are after lamination at about 80% copper
coverage on the inner layers. Core thicknesses are marked nominal only.
Outer copper is 18 um foil plus plating, finished 35 um. FR4 inner copper
is 35 um. The Rogers cores carry 18 um foil.

The hybrid sheet prints Er and Df only on the Rogers 4350B cores. The 2116
prepreg uses the 1x 2116 figures from the FR4 impedance sheet. The
1080+2116 prepreg and the 710 um FR4 core have no published Er or Df;
4.5 and 0.02 are placeholders so Altium has a number.

Solder mask is drawn with no thickness, Er, or Df. Height is 0 so it does
not move the impedance result. The published width examples match a
microstrip that does not include mask.
"""

import os
import uuid

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MultiCB_stackup")

DF_FR4 = 0.02
DF_ROGERS = 0.0037
# Not printed on the hybrid sheet. Altium needs a number.
PLACEHOLDER_ER = 4.5
PLACEHOLDER_DF = 0.02

FR4_PP = (
    "Pressed thickness after lamination, about 80% inner copper. "
    "Er and Df from the Multi-CB impedance sheet"
)
FR4_CORE = (
    "Thickness is nominal only. Er and Df from the Multi-CB impedance sheet"
)
ROGERS = "Rogers 4350B. Er 3.48 and Df 0.0037 from the hybrid sheet"
H2116 = (
    "Thickness 0.120 mm from the hybrid sheet. "
    "Er 4.20 and Df 0.02 are the 1x 2116 figures from the FR4 sheet, "
    "not printed on the hybrid drawing"
)
HUNKNOWN = (
    "PLACEHOLDER Er 4.5 Df 0.02. Multi-CB does not print Er or Df for this layer"
)

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


def cu(mm):
    return ("cu", mm)


def pp(mm, er, df, material, construction, note):
    return ("pp", mm, er, df, material, construction, note)


def core(mm, er, df, material, construction, note):
    return ("core", mm, er, df, material, construction, note)


def fr4_pp(mm, er, material, construction):
    return pp(mm, er, DF_FR4, material, construction, FR4_PP)


def fr4_core(mm, er):
    return core(mm, er, DF_FR4, "MCB-CORE", "Core", FR4_CORE)


def rogers(mm):
    return core(mm, 3.48, DF_ROGERS, "MCB-RO4350B", "Rogers 4350B", ROGERS)


# Top copper to bottom copper.
PRESETS = {
    "MCB-4L-01": {
        "nominal_mm": 1.6,
        "layers": [
            cu(0.035),
            fr4_pp(0.140, 4.00, "MCB-1080", "1080 x2"),
            cu(0.035),
            fr4_core(1.200, 4.60),
            cu(0.035),
            fr4_pp(0.140, 4.00, "MCB-1080", "1080 x2"),
            cu(0.035),
        ],
    },
    "MCB-4L-02": {
        "nominal_mm": 1.0,
        "layers": [
            cu(0.035),
            fr4_pp(0.230, 4.25, "MCB-2116", "2116 x2"),
            cu(0.035),
            fr4_core(0.400, 4.50),
            cu(0.035),
            fr4_pp(0.230, 4.25, "MCB-2116", "2116 x2"),
            cu(0.035),
        ],
    },
    "MCB-6L-01": {
        "nominal_mm": 1.6,
        "layers": [
            cu(0.035),
            fr4_pp(0.230, 4.25, "MCB-2116", "2116 x2"),
            cu(0.035),
            fr4_core(0.300, 4.50),
            cu(0.035),
            fr4_pp(0.340, 4.25, "MCB-2116", "2116 x3"),
            cu(0.035),
            fr4_core(0.300, 4.50),
            cu(0.035),
            fr4_pp(0.230, 4.25, "MCB-2116", "2116 x2"),
            cu(0.035),
        ],
    },
    "MCB-8L-01": {
        "nominal_mm": 1.7,
        "layers": [
            cu(0.035),
            fr4_pp(0.140, 4.00, "MCB-1080", "1080 x2"),
            cu(0.035),
            fr4_core(0.200, 4.40),
            cu(0.035),
            fr4_pp(0.255, 4.10, "MCB-1080-2116", "1080+2116+1080"),
            cu(0.035),
            fr4_core(0.200, 4.40),
            cu(0.035),
            fr4_pp(0.255, 4.10, "MCB-1080-2116", "1080+2116+1080"),
            cu(0.035),
            fr4_core(0.200, 4.40),
            cu(0.035),
            fr4_pp(0.140, 4.00, "MCB-1080", "1080 x2"),
            cu(0.035),
        ],
    },
    "MCB-4L-H01": {
        "nominal_mm": 1.55,
        "layers": [
            cu(0.035),
            rogers(0.168),
            cu(0.018),
            pp(0.200, PLACEHOLDER_ER, PLACEHOLDER_DF, "MCB-1080-2116", "1080+2116", HUNKNOWN),
            core(0.710, PLACEHOLDER_ER, PLACEHOLDER_DF, "MCB-CORE", "FR4 core", HUNKNOWN),
            pp(0.200, PLACEHOLDER_ER, PLACEHOLDER_DF, "MCB-1080-2116", "1080+2116", HUNKNOWN),
            cu(0.018),
            rogers(0.168),
            cu(0.035),
        ],
    },
    "MCB-4L-H02": {
        "nominal_mm": 1.55,
        "layers": [
            cu(0.035),
            rogers(0.254),
            cu(0.018),
            pp(0.120, 4.20, DF_FR4, "MCB-2116", "2116 x1", H2116),
            core(0.710, PLACEHOLDER_ER, PLACEHOLDER_DF, "MCB-CORE", "FR4 core", HUNKNOWN),
            pp(0.120, 4.20, DF_FR4, "MCB-2116", "2116 x1", H2116),
            cu(0.018),
            rogers(0.254),
            cu(0.035),
        ],
    },
}


def gid():
    return "{" + str(uuid.uuid4()).upper() + "}"


def mil(mm):
    return f"{mm / 0.0254:.4f}mil"


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


def weight_label(mm):
    if abs(mm - 0.035) < 1e-6:
        return "1oz"
    if abs(mm - 0.018) < 1e-6:
        return "0.5oz"
    return f"{mm:.3f}mm"


def stack_name(code, nominal_mm):
    label = f"{nominal_mm:.2f}".rstrip("0").rstrip(".")
    if "." not in label:
        label += ".0"
    return f"{code}-{label}mm"


def build(code, layers):
    cu_i = [i for i, layer in enumerate(layers) if layer[0] == "cu"]
    if len(cu_i) not in (4, 6, 8):
        raise ValueError(f"{code} has {len(cu_i)} copper layers")
    orient = copper_orientation(layers)
    sub = gid()
    doc = gid()
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
        fields.extend([
            f"LAYER_V8_{n}LAYERID={layer_id}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={TYPE_SOLDER}",
            f"LAYER_V8_{n}NAME={name}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE=3",
            f"LAYER_V8_{n}DIELHEIGHT=0.0000mil",
            f"LAYER_V8_{n}DIELCONST=1",
            f"LAYER_V8_{n}DIELMATERIAL=MCB-SM",
            f"LAYER_V8_{n}$LSM$Thickness=0.0000mil",
            f"LAYER_V8_{n}$LSM$DielectricConstant=1",
            f"LAYER_V8_{n}$LSM$Material=MCB-SM",
            f"LAYER_V8_{n}$LSM$LossTangent=0",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=Multi-CB",
            f"LAYER_V8_{n}$LSM$Material.Description=Solder mask drawn with no thickness or Er",
            f"LAYER_V8_{n}$LSM$Note=Height 0. Published impedance examples do not include mask",
        ])
        ctx(n, name)
        n += 1

    def add_copper(index):
        nonlocal n, cu_n
        lid = gid()
        cu_ids.append(lid)
        thick_mm = layers[index][1]
        thick = mil(thick_mm)
        weight = weight_label(thick_mm)
        if cu_n == 0:
            name, layer_id, place = "Top Layer", ID_TOP, 1
            process = "Plated base foil"
            desc = f"18um foil + plating, finished {thick_mm:.3f} mm"
        elif cu_n == len(cu_i) - 1:
            name, layer_id, place = "Bottom Layer", ID_BOTTOM, 2
            process = "Plated base foil"
            desc = f"18um foil + plating, finished {thick_mm:.3f} mm"
        else:
            name, layer_id, place = f"Inner Layer {cu_n}", ID_TOP + cu_n, 0
            process = "Base foil"
            desc = f"Base foil {thick_mm:.3f} mm"
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
            f"LAYER_V8_{n}$LSM$Material=MCB-CU",
            f"LAYER_V8_{n}$LSM$Process={process}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=Multi-CB",
            f"LAYER_V8_{n}$LSM$Material.Description={desc}",
        ])
        ctx(n, name)
        n += 1
        cu_n += 1

    def add_dielectric(layer):
        nonlocal n, diel_n, pp_n, core_n
        kind, thick_mm, er, df, material, construction, note = layer
        if kind == "core":
            core_n += 1
            name = f"Core {core_n}"
        else:
            pp_n += 1
            name = f"Dielectric {pp_n}"
        type_id = TYPE_CORE if kind == "core" else TYPE_PREPREG
        diel_type = 1 if kind == "core" else 2
        thick = mil(thick_mm)
        fields.extend([
            f"LAYER_V8_{n}LAYERID={ID_DIELECTRIC0 + diel_n}",
            f"LAYER_V8_{n}ID={gid()}",
            f"LAYER_V8_{n}TYPEID={type_id}",
            f"LAYER_V8_{n}NAME={name}",
            f"LAYER_V8_{n}ISHIDDEN=False",
            f"LAYER_V8_{n}USEDBYPRIMS=False",
            f"LAYER_V8_{n}DIELTYPE={diel_type}",
            f"LAYER_V8_{n}DIELHEIGHT={thick}",
            f"LAYER_V8_{n}DIELCONST={er:.2f}",
            f"LAYER_V8_{n}DIELMATERIAL={material}",
            f"LAYER_V8_{n}$LSM$Thickness={thick}",
            f"LAYER_V8_{n}$LSM$DielectricConstant={er:.2f}",
            f"LAYER_V8_{n}$LSM$Material={material}",
            f"LAYER_V8_{n}$LSM$Material.Constructions={construction}",
            f"LAYER_V8_{n}$LSM$LossTangent={df}",
            f"LAYER_V8_{n}$LSM$Material.Manufacturer=Multi-CB",
            f"LAYER_V8_{n}$LSM$Material.Description={construction}, {thick_mm:.3f} mm, Er {er:.2f}, Df {df}",
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
    text = "|".join(fields)
    if any(ord(ch) > 127 for ch in text):
        raise ValueError(f"{code} is not ASCII")
    return text


def thickness_mm(layers):
    total = 0.0
    for layer in layers:
        if layer[0] == "cu":
            total += layer[1]
        else:
            total += layer[1]
    return total


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.endswith(".stackup"):
            os.remove(os.path.join(OUT, old))
    for code, preset in PRESETS.items():
        layers = preset["layers"]
        name = stack_name(code, preset["nominal_mm"])
        text = build(name, layers)
        path = os.path.join(OUT, name + ".stackup")
        open(path, "w", encoding="ascii", newline="\n").write(text + "\n")
        cu_n = sum(1 for layer in layers if layer[0] == "cu")
        got = thickness_mm(layers)
        print(f"{name:20} {cu_n}L  {got:.3f} mm")


if __name__ == "__main__":
    main()
