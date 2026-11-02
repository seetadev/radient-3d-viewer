"""Security headers shared by every response (pages, static files, errors, redirects)."""
import os

# Strict default for everything that is not the viewer page (assets, models, errors, redirects).
BASE_CSP = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"


def page_csp(nonce):
    """Policy for the viewer page. The only inline script is the import map, allowed by nonce."""
    return "; ".join([
        "default-src 'none'",
        "script-src 'self' 'nonce-%s'" % nonce,   # no 'unsafe-inline' / 'unsafe-eval'
        "style-src 'self'",
        "img-src 'self' data: blob:",
        "connect-src 'self'",                     # fetching the GLB models
        "worker-src 'self' blob:",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'none'",
    ])


class SecureHeadersMixin:
    def set_default_headers(self):
        self.clear_header("Server")  # do not advertise TornadoServer/<version>
        self.set_header("Content-Security-Policy", BASE_CSP)
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("X-Frame-Options", "DENY")
        self.set_header("Referrer-Policy", "no-referrer")
        self.set_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        self.set_header("Cross-Origin-Opener-Policy", "same-origin")
        if os.environ.get("ENABLE_HSTS", "").lower() in ("1", "true", "yes"):
            # Only enable when the app is served over HTTPS (e.g. behind a TLS-terminating proxy).
            self.set_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
