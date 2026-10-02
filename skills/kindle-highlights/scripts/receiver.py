#!/usr/bin/env python3
"""Localhost capture receiver for the kindle-highlights skill: POST /page saves a binary PNG (query ?name=...), POST /json saves JSON text (query ?name=...).
Files land in SCRATCH/pages/. Answers CORS/PNA preflights from ALLOWED_ORIGINS only.
Every other request is refused with 403 before its body is read, including one with no Origin header, so a manual
test must send one: curl -H "Origin: https://read.amazon.com" ..."""
import http.server
import os
import re
from urllib.parse import urlparse, parse_qs

SCRATCH = os.getcwd()  # captures land in ./pages under the launch directory
PAGES = os.path.join(SCRATCH, "pages")
os.makedirs(PAGES, exist_ok=True)
PORT = 8931
# the notebook (read.amazon.com/notebook) and the Cloud Reader (read.amazon.com/?asin=) are the only pages that POST
# here. A text/plain POST is sent without a preflight, so the Origin check in do_POST is what stops a foreign page
# writing into PAGES. Access-Control-Allow-Origin alone only hides the response from it.
ALLOWED_ORIGINS = {"https://read.amazon.com"}


class H(http.server.BaseHTTPRequestHandler):
    def _allowed(self):
        return self.headers.get("Origin") in ALLOWED_ORIGINS

    def _refuse(self):
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"origin not allowed")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        if not self._allowed():
            return self._refuse()
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if not self._allowed():
            return self._refuse()
        u = urlparse(self.path)
        q = parse_qs(u.query)
        # basename + allowlist strip any path components from the client-supplied name
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename((q.get("name") or ["unnamed"])[0]))
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if u.path == "/page":
            out = os.path.join(PAGES, name if name.endswith(".png") else name + ".png")
        else:
            out = os.path.join(PAGES, name if name.endswith(".json") else name + ".json")
        # resolve and confirm the final path stays inside PAGES (path-injection guard)
        out = os.path.realpath(out)
        if not out.startswith(os.path.realpath(PAGES) + os.sep):
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(b"bad name")
            return
        with open(out, "wb") as f:
            f.write(body)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(("saved %s %d" % (os.path.basename(out), len(body))).encode())

    def log_message(self, *a):
        pass


http.server.HTTPServer(("127.0.0.1", PORT), H).serve_forever()
