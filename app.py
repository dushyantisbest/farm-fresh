"""Local inventory dashboard. Run with python app.py."""
import json
import os
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from forecast import planning
from inventory import calculate_stock, change, connect, initialize, snapshot

ROOT = Path(__file__).resolve().parent
ASSETS = {"/": ("index.html","text/html"), "/app.js": ("app.js","text/javascript"), "/style.css": ("style.css","text/css")}


class Handler(BaseHTTPRequestHandler):
    def send_data(self, code, data, mime="application/json"):
        if mime == "application/json":
            data = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ASSETS:
            name, mime = ASSETS[path]
            return self.send_data(200,(ROOT/"static"/name).read_bytes(),mime)
        if path in ("/health","/api/dashboard"):
            with closing(connect(self.server.database)) as db, db:
                db.execute("BEGIN")
                result = snapshot(db) if path == "/api/dashboard" else {"ok": bool(db.execute("SELECT COUNT(*) FROM products").fetchone())}
                if path == "/api/dashboard":
                    result["planning"] = planning(db,result)
            return self.send_data(200,result)
        self.send_data(404,{"error":"Page not found."})

    def do_POST(self):
        actions = {"/api/"+a:a for a in ("product","sale","order","receive")}
        if self.path not in actions:
            return self.send_data(404,{"error":"Unknown operation."})
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            return self.send_data(403,{"error":"Cross-origin write refused."})
        if self.headers.get_content_type() != "application/json":
            return self.send_data(415,{"error":"Expected JSON."})
        try:
            length = int(self.headers.get("Content-Length","0"))
            if not 0 < length <= 8192:
                return self.send_data(413,{"error":"Invalid request size."})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise ValueError("Expected a JSON object.")
            with closing(connect(self.server.database)) as db:
                change(db,actions[self.path],data)
        except sqlite3.IntegrityError:
            return self.send_data(409,{"error":"A product with this name already exists."})
        except (ValueError,UnicodeError) as error:
            return self.send_data(400,{"error":str(error)})
        self.send_data(200,{"ok":True})


def create_server(database, host="127.0.0.1", port=8000):
    Path(database).parent.mkdir(parents=True,exist_ok=True)
    with closing(connect(database)) as db:
        initialize(db)
    server = ThreadingHTTPServer((host,port),Handler)
    server.database = database
    return server


if __name__ == "__main__":
    with create_server(os.getenv("INVENTORY_DB",str(ROOT/"data"/"inventory.db")),os.getenv("HOST","127.0.0.1"),int(os.getenv("PORT","8000"))) as httpd:
        print("Inventory dashboard at http://%s:%s" % httpd.server_address, flush=True)
        httpd.serve_forever()

