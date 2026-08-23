#!/usr/bin/env python3
"""Localhost capture receiver for the kindle-highlights skill: POST /page saves a binary PNG (query ?name=...), POST /json saves JSON text (query ?name=...).
Files land in SCRATCH/pages/. Answers CORS/PNA preflights."""
import http.server
import os
import re
from urllib.parse import urlparse, parse_qs

SCRATCH = os.getcwd()  # captures land in ./pages under the launch directory
PAGES = os.path.join(SCRATCH, "pages")
os.makedirs(PAGES, exist_ok=True)
PORT = 8931


class H(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", (q.get("name") or ["unnamed"])[0])
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if u.path == "/page":
            out = os.path.join(PAGES, name if name.endswith(".png") else name + ".png")
        else:
            out = os.path.join(PAGES, name if name.endswith(".json") else name + ".json")
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
