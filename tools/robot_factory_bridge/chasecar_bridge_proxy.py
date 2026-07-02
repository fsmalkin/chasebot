"""Reverse proxy: laptop 0.0.0.0:8790 -> robot factory bridge 192.168.1.11:8765.

Lets the jog page be reached over Tailscale (http://100.112.221.6:8790/jog).
Forwards all GET/POST verbatim so the page's same-origin /motors, /camera.jpg,
/health calls hit the bridge.
"""
import http.server
import socketserver
import urllib.error
import urllib.request

TARGET = "http://192.168.1.11:8765"


class Proxy(http.server.BaseHTTPRequestHandler):
    def _forward(self, method):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(TARGET + self.path, data=body, method=method)
        ct = self.headers.get("Content-Type")
        if ct:
            req.add_header("Content-Type", ct)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", r.headers.get("Content-Type", "application/octet-stream"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            msg = ("proxy_error: " + str(e)).encode()
            self.send_response(502)
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def log_message(self, *args):
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print("proxy up on 0.0.0.0:8790 -> " + TARGET, flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8790), Proxy).serve_forever()
