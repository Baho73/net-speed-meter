"""Проверка на локальном HTTP-сервере, без интернета: python test_speedmeter.py"""
import http.server
import threading

import speedmeter

PAYLOAD = b"x" * (2 * speedmeter.MB)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/big.jpg"

    t, size = speedmeter.fetch(url, timeout=5)
    assert size == len(PAYLOAD) and t > 0

    s = speedmeter.summarize([(1.0, speedmeter.MB), (1.0, 3 * speedmeter.MB)])
    assert s["avg_time"] == 1.0 and s["total_mb"] == 4.0 and s["mb_per_s"] == 2.0
    srv.shutdown()
    print("OK")
