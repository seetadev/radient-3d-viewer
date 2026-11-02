__author__ = 'sdpatro'
import asyncio
import mimetypes
import os

import tornado.web
from tornado.web import GZipContentEncoding
from tornado.httpserver import HTTPServer
from tornado.web import Application, RequestHandler

from modules import uimodules

# Minimal images (python:slim) have no /etc/mime.types; without this .glb is served as octet-stream.
mimetypes.add_type("model/gltf-binary", ".glb")

# Compress text assets and the binary glTF models (~2 MB of vendored three.js, ~4 MB of GLB).
GZipContentEncoding.CONTENT_TYPES = set(GZipContentEncoding.CONTENT_TYPES) | {"model/gltf-binary"}

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class LandingHandler(RequestHandler):
    def get(self, *args, **kwargs):
        self.redirect("/main")


class MainHandler(RequestHandler):
    def get(self, *args, **kwargs):
        self.render(os.path.join(ROOT_DIR, "templates", "main.html"))


class ApiHandler(RequestHandler):
    def post(self):
        pass


def make_app(debug=False):
    return Application(
        [
            (r"/api", ApiHandler),
            (r"/main", MainHandler),
            (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": os.path.join(ROOT_DIR, "static")}),
            (r"/models/(.*)", tornado.web.StaticFileHandler, {"path": os.path.join(ROOT_DIR, "models")}),
            (r"/(.*)", LandingHandler),
        ],
        ui_modules=uimodules,
        autoreload=debug,
        compress_response=True,
        debug=debug,
    )


async def serve(port, debug=False):
    server = HTTPServer(make_app(debug))
    server.listen(int(port))
    print("Radient running at http://localhost:%s" % port)
    await asyncio.Event().wait()


def run(port, debug=False):
    asyncio.run(serve(port, debug))
