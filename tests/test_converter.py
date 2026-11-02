"""The JSON->GLB converter must reproduce the committed GLBs exactly and keep every triangle."""
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "convert_legacy_models.py"
# Triangle counts: tri faces + 2 per quad, cross-checked against each model's metadata.
TRIANGLES = {"spacesuit": 5746, "lamborghini": 32870, "leeperrysmith": 17684, "factory": 10300, "elephant": 86352}


def read_glb(path):
    d = Path(path).read_bytes()
    magic, version, length = struct.unpack("<III", d[:12])
    assert magic == 0x46546C67 and version == 2 and length == len(d)
    n, kind = struct.unpack("<II", d[12:20])
    assert kind == 0x4E4F534A
    return json.loads(d[20:20 + n])


class ConverterTest(unittest.TestCase):
    def test_regenerated_glbs_match_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in TRIANGLES:
                out = Path(tmp) / (name + ".glb")
                subprocess.run([sys.executable, str(SCRIPT), str(ROOT / "models" / "legacy" / (name + ".js")), str(out)],
                               check=True, capture_output=True)
                self.assertEqual(out.read_bytes(), (ROOT / "models" / (name + ".glb")).read_bytes(),
                                 name + ".glb is not reproducible from models/legacy")

    def test_triangle_counts_and_bounds(self):
        for name, tris in TRIANGLES.items():
            g = read_glb(ROOT / "models" / (name + ".glb"))
            idx = [g["accessors"][p["indices"]]["count"] for p in g["meshes"][0]["primitives"]]
            self.assertEqual(sum(idx) // 3, tris, name)
            for a in g["accessors"]:
                if "min" in a:
                    self.assertTrue(all(lo <= hi for lo, hi in zip(a["min"], a["max"])), name)

    def test_scale_is_applied_like_jsonloader(self):
        # leeperrysmith has "scale": 0.053 -> JSONLoader multiplies by 1/0.053
        src = json.loads((ROOT / "models" / "legacy" / "leeperrysmith.js").read_text())
        self.assertEqual(src["scale"], 0.053)
        g = read_glb(ROOT / "models" / "leeperrysmith.glb")
        hi = max(max(a["max"]) for a in g["accessors"] if "max" in a)
        self.assertAlmostEqual(hi, max(src["vertices"]) / 0.053, delta=1e-3 * hi)

    def test_texture_names_preserved(self):
        g = read_glb(ROOT / "models" / "spacesuit.glb")
        maps = sorted(m["extras"]["mapDiffuse"] for m in g["materials"])
        self.assertEqual(maps, ["Spacesuit_Body_D.tga", "Spacesuit_Glove_D.tga", "Spacesuit_Helmet_D.tga"])


if __name__ == "__main__":
    unittest.main()
