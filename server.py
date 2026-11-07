import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from cc.compiler import compile_source
from cc.python_runner import run_python
from cc.parser import grammar_details

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")
EXAMPLES_DIR = os.path.join(ROOT, "examples")
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
COMPILE_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.path = self.path.split("?")[0]
        if self.path in ("/", "/index.html"):
            return self.send_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
        if self.path == "/api/grammar":
            return self.send_json(grammar_details())
        if self.path == "/api/examples":
            files = sorted(f for f in os.listdir(EXAMPLES_DIR) if f.endswith(".c"))
            return self.send_json(files)
        if self.path.startswith("/api/examples/"):
            name = os.path.basename(unquote(self.path[len("/api/examples/"):]))
            path = os.path.join(EXAMPLES_DIR, name)
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    return self.send_json({"name": name, "code": f.read()})
        name = os.path.basename(unquote(self.path))
        ext = os.path.splitext(name)[1]
        path = os.path.join(WEB_DIR, name)
        if ext in STATIC_TYPES and os.path.isfile(path):
            return self.send_file(path, STATIC_TYPES[ext])
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path not in ("/api/compile", "/api/run-python"):
            return self.send_json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            code = json.loads(self.rfile.read(length).decode("utf-8"))["code"]
        except (ValueError, KeyError):
            return self.send_json({"error": "очікується JSON {code: ...}"}, 400)
        if self.path == "/api/run-python":
            with COMPILE_LOCK:
                result = compile_source(code, run=False)
            if not result["ok"]:
                return self.send_json({"ok": False, "output": "", "error": "програма має помилки компіляції", "ms": 0})
            return self.send_json(run_python(result["python"]))
        with COMPILE_LOCK:
            result = compile_source(code)
        self.send_json(result)

    def log_message(self, fmt, *args):
        print(f"  {self.command} {self.path}")


def serve(port=8000):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Веб-інтерфейс: http://localhost:{port}   (Ctrl+C — зупинити)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nЗупинено.")


if __name__ == "__main__":
    serve()
