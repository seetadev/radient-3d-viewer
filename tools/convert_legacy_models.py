#!/usr/bin/env python3
"""Convert legacy three.js JSON v3 models (models/legacy/*.js) to binary glTF (GLB).

Reproducible, dependency-free (standard library only):

    python tools/convert_legacy_models.py                 # all of models/legacy -> models/
    python tools/convert_legacy_models.py in.js out.glb   # one file

Follows three.js JSONLoader semantics (r75..r124): face type bitmask, quads split
as (a,b,d),(b,c,d), vertices multiplied by 1/`scale` (JSONLoader: scale = 1 / json.scale). One glTF primitive per
material. Texture file names (e.g. mapDiffuse) are kept in material `extras`;
the texture files themselves are not part of this repository.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_faces(data):
    """Yield (material, [(v, n, uv), ...]) triangles, n/uv may be None."""
    faces = data["faces"]
    uv_layers = data.get("uvs") or []
    n_uv_layers = len(uv_layers[0]) and len([l for l in uv_layers if l]) or 0
    i, n = 0, len(faces)
    while i < n:
        t = faces[i]; i += 1
        is_quad, has_mat = t & 1, t & 2
        has_face_uv, has_vtx_uv = t & 4, t & 8
        has_face_n, has_vtx_n = t & 16, t & 32
        has_face_c, has_vtx_c = t & 64, t & 128
        nv = 4 if is_quad else 3
        v = faces[i:i + nv]; i += nv
        mat = 0
        if has_mat:
            mat = faces[i]; i += 1
        uv = [None] * nv
        if has_face_uv:
            i += n_uv_layers  # per-face uv: unused by the viewer
        if has_vtx_uv:
            for layer in range(n_uv_layers):
                idx = faces[i:i + nv]; i += nv
                if layer == 0:
                    uv = idx
        nrm = [None] * nv
        if has_face_n:
            i += 1
        if has_vtx_n:
            nrm = faces[i:i + nv]; i += nv
        if has_face_c:
            i += 1
        if has_vtx_c:
            i += nv
        corners = list(zip(v, nrm, uv))
        if is_quad:
            yield mat, [corners[0], corners[1], corners[3]]
            yield mat, [corners[1], corners[2], corners[3]]
        else:
            yield mat, corners


def pad4(b, fill=b"\x00"):
    return b + fill * (-len(b) % 4)


def build_glb(data, name):
    scale = 1.0 / data["scale"] if data.get("scale") else 1.0  # JSONLoader semantics
    verts, normals = data["vertices"], data.get("normals") or []
    uvs = (data.get("uvs") or [[]])[0] if data.get("uvs") else []
    prims = {}  # material -> (dedupe dict, corner list, indices)
    for mat, tri in parse_faces(data):
        seen, corners, idx = prims.setdefault(mat, ({}, [], []))
        for c in tri:
            k = seen.get(c)
            if k is None:
                k = seen[c] = len(corners)
                corners.append(c)
            idx.append(k)

    bin_chunks, views, accessors, primitives = [], [], [], []
    offset = 0

    def add_view(blob, target):
        nonlocal offset
        blob = pad4(blob)
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(blob), "target": target})
        bin_chunks.append(blob)
        offset += len(blob)
        return len(views) - 1

    def add_acc(view, ctype, count, atype, **kw):
        accessors.append({"bufferView": view, "componentType": ctype, "count": count, "type": atype, **kw})
        return len(accessors) - 1

    for mat in sorted(prims):
        _, corners, idx = prims[mat]
        pos = []
        for v, _n, _u in corners:
            pos += (verts[3 * v] * scale, verts[3 * v + 1] * scale, verts[3 * v + 2] * scale)
        mins = [min(pos[a::3]) for a in range(3)]
        maxs = [max(pos[a::3]) for a in range(3)]
        attrs = {"POSITION": add_acc(add_view(struct.pack("<%df" % len(pos), *pos), 34962),
                                     5126, len(corners), "VEC3", min=mins, max=maxs)}
        if normals and corners[0][1] is not None:
            nn = []
            for _v, nidx, _u in corners:
                nn += normals[3 * nidx:3 * nidx + 3]
            attrs["NORMAL"] = add_acc(add_view(struct.pack("<%df" % len(nn), *nn), 34962), 5126, len(corners), "VEC3")
        if uvs and corners[0][2] is not None:
            uu = []
            for _v, _n, uidx in corners:
                uu += (uvs[2 * uidx], 1.0 - uvs[2 * uidx + 1])  # glTF uv origin is top-left
            attrs["TEXCOORD_0"] = add_acc(add_view(struct.pack("<%df" % len(uu), *uu), 34962), 5126, len(corners), "VEC2")
        ind = add_acc(add_view(struct.pack("<%dI" % len(idx), *idx), 34963), 5125, len(idx), "SCALAR")
        primitives.append({"attributes": attrs, "indices": ind, "material": mat, "mode": 4})

    materials = []
    for m in data.get("materials", []):
        d = m.get("colorDiffuse", [0.64, 0.64, 0.64])
        extras = {k: m[k] for k in ("mapDiffuse", "mapBump", "mapNormal") if k in m}
        entry = {"name": m.get("DbgName", "material"),
                 "pbrMetallicRoughness": {"baseColorFactor": [*d, 1.0], "metallicFactor": 0.0, "roughnessFactor": 1.0},
                 "doubleSided": True}
        if extras:
            entry["extras"] = extras
        materials.append(entry)

    gltf = {"asset": {"version": "2.0", "generator": "radient-3d-viewer tools/convert_legacy_models.py"},
            "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": name}],
            "meshes": [{"name": name, "primitives": primitives}], "materials": materials,
            "buffers": [{"byteLength": offset}], "bufferViews": views, "accessors": accessors}
    js = pad4(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    binary = b"".join(bin_chunks)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary), sum(len(p[2]) // 3 for p in prims.values())


def convert(src, dst):
    data = json.loads(Path(src).read_text())
    glb, tris = build_glb(data, Path(src).stem)
    Path(dst).write_bytes(glb)
    print("%-28s -> %-24s %8d triangles %9d bytes" % (Path(src).relative_to(ROOT) if Path(src).is_absolute() else src,
                                                    Path(dst).name, tris, len(glb)))
    return tris


if __name__ == "__main__":
    if len(sys.argv) == 3:
        convert(sys.argv[1], sys.argv[2])
    else:
        for f in sorted((ROOT / "models" / "legacy").glob("*.js")):
            convert(f, ROOT / "models" / (f.stem + ".glb"))
