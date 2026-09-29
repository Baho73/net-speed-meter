"""Тесты на локальном HTTP-сервере, интернет не нужен: python -m unittest -v"""
import contextlib
import http.server
import io
import threading
import unittest

import speedmeter

BODY = b"x" * 2_000_000


class Handler(http.server.BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):
        Handler.hits += 1
        if self.path.startswith("/short"):  # обещаем больше, чем отдаем
            self.send_response(200)
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b"abcd")
            return
        if self.path.startswith("/partial"):
            self.send_response(206)
        elif self.path.startswith("/flaky") and Handler.hits % 2 == 0:
            self.send_response(500)
            self.end_headers()
            return
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)

    def log_message(self, *args):
        pass


class SpeedMeterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        Handler.hits = 0

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = speedmeter.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_speed_is_total_bytes_over_total_time(self):
        # 1 МБ за 1 с и 1 МБ за 3 с: 2 МБ / 4 с = 0.5 МБ/с (среднее скоростей дало бы 0.67)
        s = speedmeter.summarize([(1.0, 1_000_000), (3.0, 1_000_000)])
        self.assertAlmostEqual(s["mb_per_s"], 0.5)
        self.assertAlmostEqual(s["avg_time"], 2.0)
        self.assertAlmostEqual(s["total_mb"], 2.0)

    def test_full_download(self):
        t, size = speedmeter.fetch(f"{self.base}/big.jpg", timeout=5)
        self.assertEqual(size, len(BODY))
        self.assertGreater(t, 0)

    def test_truncated_body_is_error(self):
        with self.assertRaises(speedmeter.IncompleteDownload):
            speedmeter.fetch(f"{self.base}/short", timeout=5)

    def test_partial_content_is_error(self):
        with self.assertRaises(speedmeter.IncompleteDownload):
            speedmeter.fetch(f"{self.base}/partial", timeout=5)

    def test_ten_sequential_requests_by_default(self):
        code, out, _ = self.run_main(f"{self.base}/big.jpg")
        self.assertEqual(code, 0)
        self.assertEqual(Handler.hits, 10)
        self.assertIn("Успешных загрузок: 10 из 10", out)

    def test_partial_failure_returns_1(self):
        code, out, err = self.run_main(f"{self.base}/flaky", "-n", "4")
        self.assertEqual(code, 1)
        self.assertIn("Успешных загрузок: 2 из 4", out)
        self.assertIn("ошибка", err)

    def test_total_failure_returns_1(self):
        code, _, err = self.run_main(f"{self.base}/short", "-n", "2")
        self.assertEqual(code, 1)
        self.assertIn("Ни одна загрузка не прошла", err)

    def test_rejects_bad_arguments(self):
        for argv in (["ftp://x/f"], ["data:,x"], [f"{self.base}/f", "-n", "0"], [f"{self.base}/f", "-t", "-1"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                self.run_main(*argv)


if __name__ == "__main__":
    unittest.main()
