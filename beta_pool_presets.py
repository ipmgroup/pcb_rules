"""PCB-POOL layer builds from the Lagenaufbau tables on tab #1.

https://de.beta-layout.com/leiterplatten/infos/spezifikationen/#1
Read 2026-10-22. All three tables name ISOLA 104 ML.

Dk and Df are from
https://de.beta-layout.com/download/spezifikation/Datenblatt/de104-laminate-and-prepreg.pdf
at 1 GHz. A core thickness matches a core-table row. 2 x 2116 has no
pressed row, so it uses the nearer single ply (2116, 50% resin, 0.120 mm).
Mixed prepreg has no row, so it uses the product typical.

Mask is Peters Elpemer 2467 from the PCB-POOL datasheet list.
"""

MASK = {
    "mm": 0.035,
    "er": 3.7,
    "df": 0.029,
    "material": "PETERS-2467",
    "freq": "1MHz",
    "mfr": "Peters",
    "desc": "Elpemer 2467. 35 um, middle of the PCB-POOL mask rule 20-50 um",
    "note": (
        "Datasheet ca. Er 3.7 at 1 MHz, loss factor ca. 0.029 from 1 to 100 MHz. "
        "PCB-POOL rule G over a trace is 8 um. Material section also says 10-30 um per side. "
        "The PCB-OVERSEAS mask table is separate"
    ),
}

CORE_4X7628 = (
    "Isola DE104 core table, 4 x 7628, 39% resin, 0.71 mm. "
    "Dk 4.67 Df 0.017 at 1 GHz"
)
CORE_2X7628 = (
    "Isola DE104 core table, 2 x 7628, 39% resin, 0.36 mm. "
    "Dk 4.67 Df 0.017 at 1 GHz"
)
PP_2116 = (
    "No pressed 2 x 2116 row in the DE104 tables. "
    "Nearest published ply is 2116, 50% resin, 0.120 mm: Dk 4.45 Df 0.019 at 1 GHz. "
    "Two such plies are 0.240 mm. The page pressed thickness is 0.23 mm"
)
PP_MIX_041 = (
    "No 1 x 7628 + 2 x 2116 row in the DE104 Dk tables. "
    "This layer uses the DE104 product typical at 1 GHz, Dk 4.37 Df 0.022, IPC-TM-650 2.5.5.9. "
    "Single plies at 1 GHz: 7628 45% 0.198 mm is 4.56/0.018, 2116 50% 0.120 mm is 4.45/0.019"
)
PP_MIX_030 = (
    "No 1 x 7628 + 1 x 2116 row in the DE104 Dk tables. "
    "This layer uses the DE104 product typical at 1 GHz, Dk 4.37 Df 0.022, IPC-TM-650 2.5.5.9. "
    "Single plies at 1 GHz: 7628 45% 0.198 mm is 4.56/0.018, 2116 50% 0.120 mm is 4.45/0.019"
)


def cu(plated, note=""):
    return ("cu", 0.035, plated, note)


def core(mm, glass, note):
    er, df = (4.67, 0.017)
    return ("core", mm, glass, note, er, df)


def pp(mm, glass, note, er, df):
    return ("pp", mm, glass, note, er, df)


PRESETS = [
    (
        "BL-4L-35um-DE104-1.68mm",
        {
            "nominal": 1.68,
            "material": "DE104",
            "mask": MASK,
            "layers": [
                cu(True, "Page total after plating is 1.676 mm. Printed layers sum to 1.670 mm"),
                pp(0.41, "7628 x1 + 2116 x2", PP_MIX_041, 4.37, 0.022),
                cu(False),
                core(0.71, "7628 x4", CORE_4X7628),
                cu(False),
                pp(0.41, "7628 x1 + 2116 x2", PP_MIX_041, 4.37, 0.022),
                cu(True),
            ],
        },
    ),
    (
        "BL-4L-35um-DE104-0.964mm",
        {
            "nominal": 0.964,
            "material": "DE104",
            "mask": MASK,
            "layers": [
                cu(True, "Page total after plating is 0.964 mm. Printed layers sum to 0.960 mm"),
                pp(0.23, "2116 x2", PP_2116, 4.45, 0.019),
                cu(False),
                core(0.36, "7628 x2", CORE_2X7628),
                cu(False),
                pp(0.23, "2116 x2", PP_2116, 4.45, 0.019),
                cu(True),
            ],
        },
    ),
    (
        "BL-6L-35um-DE104-1.69mm",
        {
            "nominal": 1.69,
            "material": "DE104",
            "mask": MASK,
            "layers": [
                cu(True, "Page total after plating is 1.692 mm. Printed layers sum to 1.690 mm"),
                pp(0.23, "2116 x2", PP_2116, 4.45, 0.019),
                cu(False),
                core(0.36, "7628 x2", CORE_2X7628),
                cu(False),
                pp(0.30, "7628 x1 + 2116 x1", PP_MIX_030, 4.37, 0.022),
                cu(False),
                core(0.36, "7628 x2", CORE_2X7628),
                cu(False),
                pp(0.23, "2116 x2", PP_2116, 4.45, 0.019),
                cu(True),
            ],
        },
    ),
]
