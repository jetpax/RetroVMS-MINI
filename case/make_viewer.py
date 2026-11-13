#!/usr/bin/env python3
"""Build the RetroVMS Mini Case viewer page (three.js, STLs embedded) from the
case build: build/tray.stl and build/cover.stl in the case frame, the board's
compacted GLB (build/board.glb, export_board_glb.py) and build/case.json.
build.sh runs it last.

    python3 make_viewer.py        needs: numpy

Writes viewer/rvms_mini_case_viewer.html and, beside it, the board model as
viewer/board.glb.gz.b64.js (gzipped GLB as base64 text in a one-line script:
the artifact host serves text, and a <script src> also loads from disk where
browsers refuse fetch()). Publish both, the script as a supporting file.
"""
import base64, datetime, gzip, hashlib, json, os, struct
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "viewer")
TEMPLATE = os.path.join(OUT, "viewer_template.html")
PARTS = (("base", "tray.stl"), ("cover", "cover.stl"))


def read_stl(path):
    data = open(path, "rb").read()
    n = struct.unpack_from("<I", data, 80)[0]
    if 84 + 50 * n == len(data):
        rec = np.frombuffer(data, dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")], count=n, offset=84)
        return rec["v"].astype(np.float64)
    v = [list(map(float, l.split()[1:4])) for l in data.decode().splitlines() if l.strip().startswith("vertex")]
    return np.array(v).reshape(-1, 3, 3)


def binary_stl(tris):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    rec["n"], rec["v"] = n, tris
    return b"\0" * 80 + struct.pack("<I", len(tris)) + rec.tobytes()


def volume(tris):
    return abs(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum()) / 6.0


def fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def main():
    html = open(TEMPLATE).read()
    case = json.load(open(os.path.join(B, "case.json")))
    meta = {}
    for key, f in PARTS:
        tris = read_stl(os.path.join(B, f))
        b = binary_stl(tris)
        html = html.replace("__B64_%s__" % key.upper(), base64.b64encode(b).decode())
        pts = tris.reshape(-1, 3)
        meta[key] = dict(tris=len(tris), bounds=[[round(v, 2) for v in pts.min(axis=0)], [round(v, 2) for v in pts.max(axis=0)]],
                         vol=round(volume(tris), 1))
        print("%-5s %5d tris  %7d bytes binary" % (key, len(tris), len(b)))
    lo = np.min([meta[k]["bounds"][0] for k in meta], axis=0)
    hi = np.max([meta[k]["bounds"][1] for k in meta], axis=0)
    html = html.replace("__OUTER__", "%s × %s × %s mm" % (fmt(hi[0] - lo[0]), fmt(hi[1] - lo[1]), fmt(hi[2] - lo[2])))
    ranges = dict(x=[int(np.floor(lo[0])), int(np.ceil(hi[0]))], y=[int(np.floor(lo[1])), int(np.ceil(hi[1]))],
                  z=[int(np.floor(lo[2])), int(np.ceil(hi[2]))])
    html = html.replace("__RANGES__", json.dumps(ranges)).replace("__GRID_Z__", json.dumps(case["mount_z"] - 0.05))
    html = html.replace("__WORLD__", "null")
    off = case["kicad_offset_on_J1"]
    facts = [
        ("Mounting", "4 ears, 114.2 × 62.5 mm, Ø7"),
        ("Fixing", "4 × M3 × %d up through the board into inserts in the cover" % case["screw_length"]),
        ("Low lid", "%s mm above the mount face" % fmt(case["lid_top"] - case["mount_z"])),
        ("Hood", "%s mm above the mount face" % fmt(case["hood_top"] - case["mount_z"])),
        ("Lid", "%s mm bevel, label recess %s × %s mm" % (fmt(case["bevel"]), fmt(case["label"][0]), fmt(case["label"][1]))),
        ("Openings", "USB-C, microSD"),
        ("Print", "tray on its floor, cover on its connector end, no support"),
        ("KiCad", "rvms_mini_case.step on J1, offset %s, %s, %s" % tuple(fmt(v) for v in off)),
    ]
    html = html.replace("__FACTS__", "".join("<dt>%s</dt><dd>%s</dd>" % f for f in facts))
    board = None
    glb = os.path.join(B, "board.glb")
    if os.path.exists(glb):
        packed = gzip.compress(open(glb, "rb").read(), 9, mtime=0)
        js = os.path.join(OUT, "board.glb.gz.b64.js")
        open(js, "wb").write(b"window.RVMS_BOARD_B64=\"" + base64.b64encode(packed) + b"\";\n")
        board = dict(matrix=json.load(open(os.path.join(B, "board_frame.json")))["matrix"], bytes=len(packed),
                     src="board.glb.gz.b64.js?v=" + hashlib.sha1(packed).hexdigest()[:10])
        print("board %d bytes gzipped, %d as base64 text" % (len(packed), os.path.getsize(js)))
    html = html.replace("__BOARD_META__", json.dumps(board))
    html = html.replace("__META__", json.dumps(meta)).replace("__BUILT__", datetime.date.today().isoformat())
    out = os.path.join(OUT, "rvms_mini_case_viewer.html")
    open(out, "w").write(html)
    print("wrote", out, len(html), "bytes")


if __name__ == "__main__":
    main()
