"""Server tests: run the real Tornado app on an ephemeral port (no mocks)."""
import os
import re

from tornado.testing import AsyncHTTPTestCase

from controllers.main import make_app

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS = ["spacesuit", "lamborghini", "leeperrysmith", "factory", "elephant"]


class ServerTest(AsyncHTTPTestCase):
    def get_app(self):
        return make_app()

    def test_root_redirects_to_main(self):
        r = self.fetch("/", follow_redirects=False)
        self.assertEqual(r.code, 302)
        self.assertEqual(r.headers["Location"], "/main")

    def test_unknown_path_redirects_to_main(self):
        r = self.fetch("/no/such/page", follow_redirects=False)
        self.assertEqual(r.code, 302)

    def test_main_serves_module_viewer(self):
        r = self.fetch("/main")
        self.assertEqual(r.code, 200)
        body = r.body.decode()
        self.assertIn("RADIENT 3D VIEWER", body)
        self.assertIn('type="importmap"', body)
        self.assertIn('type="module" src="/static/app.js"', body)
        for m in MODELS:
            self.assertIn(">%s</button>" % m, body)

    def test_every_page_asset_resolves(self):
        body = self.fetch("/main").body.decode()
        urls = re.findall(r'(?:src|href)="(/static/[^"]+)"', body)
        urls += re.findall(r'"(/static/[^"]+)"', body)  # import map
        self.assertGreaterEqual(len(urls), 5)
        for u in set(urls):
            if u.endswith("/"):
                continue  # import-map prefix
            self.assertEqual(self.fetch(u).code, 200, u)

    def test_models_are_served_as_glb(self):
        for m in MODELS:
            r = self.fetch("/models/%s.glb" % m)
            self.assertEqual(r.code, 200, m)
            self.assertEqual(r.body[:4], b"glTF", m)

    def test_glb_content_type(self):
        # independent of the OS mime database (python:slim images have none)
        for m in MODELS:
            self.assertEqual(self.fetch("/models/%s.glb" % m).headers["Content-Type"], "model/gltf-binary", m)

    def test_cubemap_served(self):
        for f in ("px", "nx", "py", "ny", "pz", "nz"):
            self.assertEqual(self.fetch("/static/cubemap/%s.jpg" % f).code, 200, f)

    def test_legacy_models_not_served_as_models(self):
        # originals live in models/legacy and must stay reachable only as files, not break the GLB route
        self.assertEqual(self.fetch("/models/missing.glb").code, 404)

    # --- path traversal: must never expose files outside static/ and models/ -------------
    def test_path_traversal_is_blocked(self):
        attempts = [
            "/static/../run.py", "/models/../run.py",
            "/static/%2e%2e/run.py", "/models/%2e%2e/run.py",
            "/static/..%2frun.py", "/static/%2e%2e%2frun.py",
            "/static/../../etc/passwd", "/static//etc/passwd",
            "/static/....//run.py",
        ]
        for path in attempts:
            r = self.fetch(path, follow_redirects=False)
            self.assertNotEqual(r.code, 200, path)
            self.assertNotIn(b"asyncio", r.body, path)      # run.py / main.py content
            self.assertNotIn(b"root:", r.body, path)        # /etc/passwd content

    def test_hidden_and_source_files_not_exposed(self):
        for path in ("/static/vendor/../../requirements.txt", "/models/legacy/../../run.py"):
            self.assertNotEqual(self.fetch(path, follow_redirects=False).code, 200, path)

    def test_debug_and_autoreload_off_by_default(self):
        settings = self.get_app().settings
        self.assertFalse(settings.get("debug"))
        self.assertFalse(settings.get("autoreload"))

    def test_api_stub_rejects_get(self):
        self.assertEqual(self.fetch("/api").code, 405)


class CompressionTest(AsyncHTTPTestCase):
    def get_app(self):
        return make_app()

    def fetch_gz(self, path):
        # raw bytes + header: AsyncHTTPClient would transparently decode if decompress_response were on
        return self.fetch(path, headers={"Accept-Encoding": "gzip"}, decompress_response=False)

    def test_text_assets_are_gzipped(self):
        for path in ("/main", "/static/app.js", "/static/vendor/three/build/three.core.js",
                     "/static/vendor/bootstrap/bootstrap.min.css"):
            r = self.fetch_gz(path)
            self.assertEqual(r.code, 200, path)
            self.assertEqual(r.headers.get("Content-Encoding"), "gzip", path)

    def test_glb_models_are_gzipped_and_roundtrip(self):
        import gzip
        r = self.fetch_gz("/models/elephant.glb")
        self.assertEqual(r.headers.get("Content-Encoding"), "gzip")
        plain = open(os.path.join(ROOT, "models", "elephant.glb"), "rb").read()
        self.assertLess(len(r.body), len(plain))
        self.assertEqual(gzip.decompress(r.body), plain)

    def test_jpeg_is_not_recompressed(self):
        r = self.fetch_gz("/static/cubemap/px.jpg")
        self.assertIsNone(r.headers.get("Content-Encoding"))
