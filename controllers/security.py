"""Security headers shared by every response (pages, static files, errors, redirects)."""
import os


def env_bool(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def hsts_header():
    """HSTS is opt-in: unset/0 = no header. includeSubDomains is a separate opt-in; preload is never sent.

    HSTS cannot be undone remotely (browsers remember it for max-age), and includeSubDomains also
    forces https on every subdomain, so both are off unless an operator asks for them.
    """
    raw = os.environ.get("HSTS_SECONDS", "").strip() or "0"
    try:
        seconds = int(raw)
    except ValueError:
        raise SystemExit("HSTS_SECONDS must be a non-negative integer, got %r" % raw)
    if seconds < 0:
        raise SystemExit("HSTS_SECONDS must be a non-negative integer, got %r" % raw)
    if seconds == 0:
        return None
    value = "max-age=%d" % seconds
    if env_bool("HSTS_INCLUDE_SUBDOMAINS"):
        value += "; includeSubDomains"
    return value


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
        hsts = self.settings.get("hsts")
        if hsts:
            self.set_header("Strict-Transport-Security", hsts)
