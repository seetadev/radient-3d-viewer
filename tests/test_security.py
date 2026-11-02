"""Security regression tests: headers/CSP, XSRF on the only POST route, server banner."""
import os
import re
from unittest import mock

from tornado.testing import AsyncHTTPTestCase

from controllers.main import make_app

REQUIRED = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class HeadersTest(AsyncHTTPTestCase):
    def get_app(self):
        return make_app()

    def assert_secure_headers(self, r, path):
        for k, v in REQUIRED.items():
            self.assertEqual(r.headers.get(k), v, "%s missing on %s" % (k, path))
        self.assertIn("frame-ancestors 'none'", r.headers.get("Content-Security-Policy", ""), path)
        self.assertIn("camera=()", r.headers.get("Permissions-Policy", ""), path)

    def test_every_kind_of_response_has_security_headers(self):
        for path, code in [("/main", 200), ("/static/app.js", 200), ("/static/vendor/three/build/three.core.js", 200),
                           ("/models/spacesuit.glb", 200), ("/static/cubemap/px.jpg", 200),
                           ("/models/nope.glb", 404), ("/static/../run.py", 403), ("/api", 405)]:
            r = self.fetch(path, follow_redirects=False)
            self.assertEqual(r.code, code, path)
            self.assert_secure_headers(r, path)
        r = self.fetch("/", follow_redirects=False)   # redirect
        self.assertEqual(r.code, 302)
        self.assert_secure_headers(r, "/")

    def test_server_version_is_not_advertised(self):
        for path in ("/main", "/static/app.js", "/nope.glb"):
            self.assertNotIn("Server", self.fetch(path, follow_redirects=False).headers, path)

    def test_page_csp_is_strict(self):
        csp = self.fetch("/main").headers["Content-Security-Policy"]
        script_src = re.search(r"script-src ([^;]+)", csp).group(1)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)
        self.assertNotIn("*", csp)
        self.assertIn("'self'", script_src)
        for directive in ("default-src 'none'", "object-src 'none'", "base-uri 'none'", "frame-ancestors 'none'"):
            self.assertIn(directive, csp)

    def test_csp_nonce_matches_import_map_and_changes_per_request(self):
        nonces = []
        for _ in range(2):
            r = self.fetch("/main")
            nonce = re.search(r"'nonce-([^']+)'", r.headers["Content-Security-Policy"]).group(1)
            self.assertIn('<script type="importmap" nonce="%s">' % nonce, r.body.decode())
            nonces.append(nonce)
        self.assertNotEqual(nonces[0], nonces[1])
        self.assertGreaterEqual(len(nonces[0]), 16)

    def test_page_has_no_inline_handlers_or_inline_scripts_besides_import_map(self):
        body = self.fetch("/main").body.decode()
        self.assertIsNone(re.search(r"\son(click|mousedown|change|load)=", body))
        inline = [m for m in re.findall(r"<script(?![^>]*\ssrc=)[^>]*>", body)]
        self.assertEqual(len(inline), 1)
        self.assertIn("importmap", inline[0])


class HstsTest(AsyncHTTPTestCase):
    """HSTS is opt-in; includeSubDomains is a separate opt-in; preload is never sent."""
    ENV = {}

    def get_app(self):
        with mock.patch.dict(os.environ, self.ENV):
            return make_app()

    def hsts(self):
        return self.fetch("/main").headers.get("Strict-Transport-Security")


class HstsOffByDefaultTest(HstsTest):
    def test_no_hsts_header(self):
        self.assertIsNone(self.hsts())


class HstsZeroTest(HstsTest):
    ENV = {"HSTS_SECONDS": "0", "HSTS_INCLUDE_SUBDOMAINS": "1"}

    def test_zero_means_off_even_if_subdomains_flag_set(self):
        self.assertIsNone(self.hsts())


class HstsSecondsOnlyTest(HstsTest):
    ENV = {"HSTS_SECONDS": "3600"}

    def test_max_age_only(self):
        self.assertEqual(self.hsts(), "max-age=3600")  # no includeSubDomains, no preload


class HstsWithSubdomainsTest(HstsTest):
    ENV = {"HSTS_SECONDS": "3600", "HSTS_INCLUDE_SUBDOMAINS": "1"}

    def test_include_subdomains_only_when_asked(self):
        self.assertEqual(self.hsts(), "max-age=3600; includeSubDomains")
        self.assertNotIn("preload", self.hsts())


class HstsValidationTest(AsyncHTTPTestCase):
    def get_app(self):
        return make_app()

    def test_invalid_values_refuse_to_start(self):
        for bad in ("abc", "-5", "1.5"):
            with mock.patch.dict(os.environ, {"HSTS_SECONDS": bad}):
                with self.assertRaises(SystemExit):
                    make_app()


class SecureCookieTest(AsyncHTTPTestCase):
    def get_app(self):
        with mock.patch.dict(os.environ, {"SECURE_COOKIES": "1"}):
            return make_app()

    def test_xsrf_cookie_secure_when_enabled(self):
        cookie = [c for c in self.fetch("/main").headers.get_list("Set-Cookie") if c.startswith("_xsrf=")][0]
        self.assertIn("Secure", cookie)


class XsrfTest(AsyncHTTPTestCase):
    def get_app(self):
        return make_app()

    def test_post_api_without_token_is_rejected(self):
        r = self.fetch("/api", method="POST", body="")
        self.assertEqual(r.code, 403)

    def test_post_api_with_wrong_token_is_rejected(self):
        r = self.fetch("/api", method="POST", body="", headers={"X-XSRFToken": "forged", "Cookie": "_xsrf=other"})
        self.assertEqual(r.code, 403)

    def test_post_api_with_valid_token_is_accepted(self):
        page = self.fetch("/main")
        cookie = [c for c in page.headers.get_list("Set-Cookie") if c.startswith("_xsrf=")][0]
        token = cookie.split(";")[0].split("=", 1)[1]
        r = self.fetch("/api", method="POST", body="", headers={"X-XSRFToken": token, "Cookie": "_xsrf=" + token})
        self.assertEqual(r.code, 200)

    def test_xsrf_cookie_is_issued_by_the_page(self):
        cookies = self.fetch("/main").headers.get_list("Set-Cookie")
        self.assertTrue(any(c.startswith("_xsrf=") for c in cookies))

    def test_xsrf_cookie_is_samesite_strict(self):
        cookie = [c for c in self.fetch("/main").headers.get_list("Set-Cookie") if c.startswith("_xsrf=")][0]
        self.assertIn("SameSite=Strict", cookie)
