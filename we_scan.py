"""Parse WEdirekt shop stackup PDFs into layer rows.

The shop sheets are not the BASIC sales stackups. Thickness, material
number and copper tags are text. The material name is drawn as a picture,
so glass style is filled in later from an OCR pass.
"""

import os
import re

import pymupdf

ROOT = r"C:\Users\Andrew\Documents\Altium\wedirekt-stack-ups"
TAG = re.compile(r"^(VS|RS|L\d+)$")
PROC = re.compile(r"^[AB]\d+$")
MAT = re.compile(r"^\d{8}$")
INT = re.compile(r"^\d+$")


def pdfs(root):
    found = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".pdf") and not name.startswith("01_"):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def cluster(words, tol=3.2):
    words = sorted(words, key=lambda w: (w[1], w[0]))
    bands = []
    for w in words:
        if not bands or abs(w[1] - bands[-1][0]) > tol:
            bands.append([w[1], []])
        bands[-1][1].append(w)
    return bands


def parse_page(path):
    doc = pymupdf.open(path)
    if doc.page_count != 1:
        raise ValueError(f"{path} has {doc.page_count} pages")
    page = doc[0]
    words = page.get_text("words")
    nominal = None
    footer_y = 720
    for i, w in enumerate(words):
        if w[4] == "nominal:" and i + 1 < len(words) and INT.match(words[i + 1][4]):
            nominal = int(words[i + 1][4])
        if w[4] == "Thickness":
            footer_y = min(footer_y, w[1])
    date = None
    for w in words:
        if re.match(r"\d{2}\.\d{2}\.\d{4}$", w[4]):
            date = w[4]
    # Row numbers sit at x >= 290. Thickness sits near x 255.
    # The tolerance block (B00: 890 µm, Tol 100 µm) sits below the bottom foil.
    tag_ys = [w[1] for w in words if TAG.match(w[4])]
    stack_bottom = max(tag_ys) + 8 if tag_ys else footer_y
    body = [
        w for w in words
        if 120 < w[1] <= stack_bottom and w[1] < footer_y - 8
        and not (INT.match(w[4]) and w[0] >= 290)
    ]
    body = [w for w in body if w[4] not in ("Mat.", "Nr.", "µm", "Stackup", "Process", "overview", "Material", "Text")]
    bands = cluster(body)
    rows = []
    for y, group in bands:
        group = sorted(group, key=lambda w: w[0])
        mat = None
        tag = None
        thick = []
        for w in group:
            text = w[4]
            if MAT.match(text):
                mat = text
            elif TAG.match(text):
                tag = text
            elif PROC.match(text):
                continue
            elif INT.match(text):
                thick.append(int(text))
        if mat is None and tag is None and not thick:
            continue
        # The core cell prints its thickness twice, once on each side.
        uniq = []
        for value in thick:
            if value not in uniq:
                uniq.append(value)
        if len(uniq) > 1:
            raise ValueError(f"{os.path.basename(path)} y={y:.0f} thicknesses {uniq}")
        um = uniq[0] if uniq else None
        rows.append({"y": y, "mat": mat, "um": um, "tag": tag})
    return {"nominal": nominal, "date": date, "rows": rows, "page": page}


def groups(rows):
    """Copper rows and the dielectric plies between them."""
    out = []
    pending = []

    def flush():
        if not pending:
            return
        positive = [row["um"] for row in pending if row["um"]]
        out.append({
            "kind": "dielectric",
            "um": sum(positive),
            "plies": [(row["mat"], row["um"]) for row in pending],
        })
        pending.clear()

    for row in rows:
        if row["tag"]:
            flush()
            if row["um"] is None:
                raise ValueError(f"copper {row['tag']} has no thickness")
            out.append({"kind": "cu", "um": row["um"], "tag": row["tag"], "mat": row["mat"]})
        else:
            if row["mat"] is None or row["um"] is None:
                raise ValueError(f"dielectric row incomplete: {row}")
            pending.append(row)
    flush()
    return out


def material_sites(root):
    """First place each material number is drawn, for the name crop."""
    sites = {}
    for path in pdfs(root):
        if "Flex-rigid" in path or "Stiffener" in path:
            continue
        parsed = parse_page(path)
        for row in parsed["rows"]:
            if row["mat"] and row["mat"] not in sites:
                sites[row["mat"]] = (path, row["y"])
    return sites


def render_material_crops(root, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for mat, (path, y) in material_sites(root).items():
        doc = pymupdf.open(path)
        page = doc[0]
        clip = pymupdf.Rect(12, y - 3, 208, y + 11)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(4, 4), clip=clip)
        dest = os.path.join(out_dir, mat + ".png")
        pix.save(dest)
        paths.append(dest)
    return paths


def filename_copper(name):
    """Finished outer and inner copper in µm, from the PDF name."""
    text = name.replace(",", ".")
    outer = inner = None
    match = re.search(r"(\d+)\s*outer.*?(\d+)\s*inner", text, re.I)
    if match:
        outer, inner = int(match.group(1)), int(match.group(2))
    else:
        match = re.search(r"(\d+)\s*[_ ]\s*(\d+)\s+HDI", text, re.I)
        if match:
            outer, inner = int(match.group(1)), int(match.group(2))
        else:
            match = re.search(r"(\d+)\s*end", text, re.I)
            if match:
                outer = int(match.group(1))
    thick = None
    match = re.search(r"(\d+(?:\.\d+)?)\s*mm", text, re.I)
    if not match:
        match = re.search(r"(\d+\.\d+)_end", text, re.I)
    if not match:
        match = re.search(r"\d+L_(\d+\.\d+)", text, re.I)
    if match:
        thick = float(match.group(1))
    layers = None
    match = re.search(r"(\d+)\s*L", text, re.I)
    if match:
        layers = int(match.group(1))
    match = re.search(r"(\d+)F", text)
    flex = match.group(1) if match else None
    return {"outer": outer, "inner": inner, "mm": thick, "layers": layers, "flex": flex}


if __name__ == "__main__":
    problems = 0
    mats = {}
    for path in pdfs(ROOT):
        rel = os.path.relpath(path, ROOT)
        try:
            parsed = parse_page(path)
            built = groups(parsed["rows"])
        except ValueError as exc:
            problems += 1
            print("FAIL", rel, exc)
            continue
        cu = [item for item in built if item["kind"] == "cu"]
        drawn = sum(item["um"] for item in built)
        nominal = parsed["nominal"]
        flag = ""
        if nominal is not None and drawn != nominal:
            flag += f" sum {drawn} != nominal {nominal}"
        info = filename_copper(os.path.basename(path))
        if info["layers"] and len(cu) != info["layers"]:
            flag += f" cu {len(cu)} != name {info['layers']}"
        inners = [item["um"] for item in cu[1:-1]]
        if info["inner"] and inners and any(value != info["inner"] for value in inners):
            flag += f" inner {inners} != name {info['inner']}"
        if flag:
            problems += 1
            print("MISMATCH", rel, flag)
        for item in built:
            if item["kind"] != "dielectric":
                if item["mat"]:
                    mats.setdefault(item["mat"], rel)
                continue
            for mat, _um in item["plies"]:
                mats.setdefault(mat, rel)
    print(f"pdfs {len(pdfs(ROOT))} problems {problems} mats {len(mats)}")
    for mat, rel in sorted(mats.items()):
        print(mat, rel)
