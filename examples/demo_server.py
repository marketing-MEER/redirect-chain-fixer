"""A tiny local web server that plays back examples/redirects.csv, so live mode can be tried offline.

    python examples/demo_server.py            # serves http://127.0.0.1:8001
    redirect-chain-fixer --urls examples/urls.txt

Sources in the map redirect (with their status code), these pages answer 200, everything else is 404.
Absolute targets on brightcrm.io (a made-up domain) are served locally.
"""
import csv
import http.server
import sys
from pathlib import Path
from urllib.parse import urlsplit

LIVE = {"/pricing", "/platform", "/blog/crm-basics", "/signup", "/contact", "/support"}


def load(path):
    rules = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rules.setdefault(row["source"], (row["target"], int(row["status"])))
    return rules


def make_handler(rules):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path in rules:
                target, status = rules[path]
                if urlsplit(target).netloc == "brightcrm.io":
                    target = urlsplit(target).path
                self.send_response(status)
                self.send_header("Location", target)
                self.end_headers()
            elif path in LIVE:
                body = f"<html><head><title>{path}</title></head><body>Demo page {path}</body></html>".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    return Handler


def server(port=8001, rules_file=None):
    rules = load(rules_file or Path(__file__).with_name("redirects.csv"))
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), make_handler(rules))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    print(f"Demo redirects on http://127.0.0.1:{port} (Ctrl+C to stop)")
    server(port).serve_forever()
