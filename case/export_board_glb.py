#!/usr/bin/env python3
"""Compact the board's KiCad GLB for the case viewer and record the matrix
that places it in the case frame. Run by build.sh after the GLB export:

    python3 export_board_glb.py build/board_raw.glb build/board.glb      needs: numpy

KiCad's GLB carries unreferenced buffer data and float normals, so the export
is compacted before the viewer embeds it: each mesh's primitives are merged
per material, only referenced data is kept, normals become 8-bit
(KHR_mesh_quantization) and indices 16-bit where they fit. Positions stay
float32, so nothing moves. (Same compaction as the CaffiMax case viewer's.)
"""
import json, os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# KiCad's 3D viewer draws the pads in its default surface-finish colour (the
# board's stackup sets no copper finish); its GLB export writes them plain grey
SURFACE_FINISH = (0.75, 0.61, 0.23)     # sRGB

COMPONENTS = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def read_glb(path):
    data = open(path, "rb").read()
    json_len = struct.unpack_from("<I", data, 12)[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_at = 20 + json_len
    bin_len = struct.unpack_from("<I", data, bin_at)[0]
    return gltf, data[bin_at + 8:bin_at + 8 + bin_len]


def accessor_array(gltf, binary, index):
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    dtype = np.dtype(COMPONENTS[acc["componentType"]])
    width = WIDTH[acc["type"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", dtype.itemsize * width)
    rows = np.ndarray((acc["count"], width), dtype=dtype, buffer=binary, offset=start, strides=(stride, dtype.itemsize))
    return rows.copy()


def srgb_to_linear(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def compact(src, dst):
    gltf, binary = read_glb(src)
    blob = bytearray()
    views, accessors = [], []

    def add(array, component, type_, normalized=False, stride=None, target=None, bounds=False):
        while len(blob) % 4:
            blob.append(0)
        view = {"buffer": 0, "byteOffset": len(blob), "byteLength": array.nbytes}
        if stride:
            view["byteStride"] = stride
        if target:
            view["target"] = target
        blob.extend(array.tobytes())
        views.append(view)
        acc = {"bufferView": len(views) - 1, "componentType": component, "count": len(array), "type": type_}
        if normalized:
            acc["normalized"] = True
        if bounds:
            acc["min"] = array[:, :3].min(axis=0).astype(float).tolist()
            acc["max"] = array[:, :3].max(axis=0).astype(float).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    # models KiCad exports with no material (the Molex connector here), which
    # glTF would draw as rough white metal: KiCad's own render shows them grey
    materials = gltf.setdefault("materials", [])
    unset = None

    # KiCad writes every pad, track piece and face as its own primitive (about
    # 12,000, which made the JSON alone 6 MB); merge each mesh's primitives
    # per material into one
    for mesh in gltf["meshes"]:
        groups = {}
        for prim in mesh["primitives"]:
            groups.setdefault(prim.get("material"), []).append(prim)
        merged = []
        for material, prims in groups.items():
            pos, nrm, idx, base = [], [], [], 0
            has_normals = all("NORMAL" in p["attributes"] for p in prims)
            for prim in prims:
                v = accessor_array(gltf, binary, prim["attributes"]["POSITION"])
                pos.append(v)
                if has_normals:
                    nrm.append(accessor_array(gltf, binary, prim["attributes"]["NORMAL"]))
                i = accessor_array(gltf, binary, prim["indices"]).ravel() if "indices" in prim else np.arange(len(v))
                idx.append(i.astype(np.uint32) + base)
                base += len(v)
            out = {"attributes": {"POSITION": add(np.vstack(pos).astype(np.float32), 5126, "VEC3", target=34962, bounds=True)}}
            if has_normals:
                # 8-bit normalized, padded to 4 bytes for vertex alignment
                values = np.vstack(nrm)
                n = np.zeros((len(values), 4), dtype=np.int8)
                n[:, :3] = np.clip(np.round(values * 127), -127, 127)
                out["attributes"]["NORMAL"] = add(n, 5120, "VEC3", normalized=True, stride=4, target=34962)
            idx = np.concatenate(idx)
            small = base < 65536
            out["indices"] = add(idx.astype(np.uint16 if small else np.uint32), 5123 if small else 5125, "SCALAR", target=34963)
            if material is None:
                if unset is None:
                    materials.append({"name": "unset", "doubleSided": True,
                                      "pbrMetallicRoughness": {"baseColorFactor": [0.16, 0.17, 0.18, 1]}})
                    unset = len(materials) - 1
                material = unset
            out["material"] = material
            merged.append(out)
        mesh["primitives"] = merged

    # KiCad writes two kinds of material. The board's own layers (mask, silk,
    # copper, substrate) come with metallic/roughness set and an sRGB colour,
    # where glTF wants linear: convert it, and name them "board:..." for the
    # viewer (three.js r128 keeps names, not extras). The pads are the only
    # metallic one. 3D-model materials come with neither, their colour already
    # linear; give them a plastic finish: left unset, glTF makes them fully
    # metallic, and a dark metal renders near black.
    for m in materials:
        pbr = m.setdefault("pbrMetallicRoughness", {})
        if "metallicFactor" in pbr:
            m["name"] = "board:" + m.get("name", "")
            if pbr["metallicFactor"] == 1:
                pbr["baseColorFactor"] = list(SURFACE_FINISH) + [1]
            if "baseColorFactor" in pbr:
                c = pbr["baseColorFactor"]
                pbr["baseColorFactor"] = [srgb_to_linear(v) for v in c[:3]] + c[3:]
        else:
            pbr["metallicFactor"] = 0.0
            pbr.setdefault("roughnessFactor", 0.6)

    gltf["accessors"], gltf["bufferViews"] = accessors, views
    while len(blob) % 4:
        blob.append(0)
    gltf["buffers"] = [{"byteLength": len(blob)}]
    for key in ("extensionsUsed", "extensionsRequired"):
        gltf[key] = sorted(set(gltf.get(key, [])) | {"KHR_mesh_quantization"})
    text = json.dumps(gltf, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    total = 12 + 8 + len(text) + 8 + len(blob)
    with open(dst, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(text), 0x4E4F534A) + text)
        f.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


def main(src, dst):
    compact(src, dst)
    # glTF from KiCad: metres, x = the board file's x, y up (0 at the board's
    # underside), z = the board file's y. The case frame: x + Tx, -y + Ty, up.
    tx, ty = json.load(open(os.path.join(HERE, "build", "frame.json")))["translate"][:2]
    matrix = [[1000, 0, 0, tx], [0, 0, -1000, ty], [0, 1000, 0, 0], [0, 0, 0, 1]]
    json.dump({"matrix": matrix}, open(os.path.join(HERE, "build", "board_frame.json"), "w"), indent=1)
    print("wrote %s: %d bytes (KiCad export %d)" % (dst, os.path.getsize(dst), os.path.getsize(src)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
