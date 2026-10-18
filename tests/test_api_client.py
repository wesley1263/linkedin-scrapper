import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from api_client import ApiClient, ApiError

JOB_ID = "3ed143b7-c006-4884-aa5c-7bf3161bf278"


class FakeApi:
    """Servidor HTTP local: guarda as requisições e responde conforme `responses[(método, caminho)]`."""

    def __init__(self):
        self.requests = []
        self.responses = {}
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode() if length else ""
                api.requests.append({"method": self.command, "path": self.path, "body": body,
                                     "auth": self.headers.get("Authorization"),
                                     "content_type": self.headers.get("Content-Type")})
                status, payload = api.responses.get((self.command, self.path), (404, {"error": "nada"}))
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _handle

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ApiClientTest(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.addCleanup(self.api.close)
        self.client = ApiClient(self.api.url + "/", api_token="publico", internal_token="interno")

    def test_get_job_returns_json_with_api_token(self):
        self.api.responses[("GET", f"/enrichments/{JOB_ID}")] = (200, {"job_id": JOB_ID, "status": "queued"})
        job = self.client.get_job(JOB_ID)
        self.assertEqual(job["status"], "queued")
        req = self.api.requests[0]
        self.assertEqual(req["auth"], "Bearer publico")

    def test_get_job_unknown_raises_api_error_with_status(self):
        with self.assertRaises(ApiError) as ctx:
            self.client.get_job(JOB_ID)
        self.assertEqual(ctx.exception.status, 404)

    def test_set_status_posts_json_with_internal_token(self):
        self.api.responses[("POST", f"/internal/jobs/{JOB_ID}/status")] = (200, {"job_id": JOB_ID, "status": "collecting"})
        out = self.client.set_status(JOB_ID, "collecting")
        self.assertEqual(out["status"], "collecting")
        req = self.api.requests[0]
        self.assertEqual(req["auth"], "Bearer interno")
        self.assertEqual(req["content_type"], "application/json")
        self.assertEqual(json.loads(req["body"]), {"status": "collecting", "error": ""})

    def test_set_status_sends_error_message(self):
        self.api.responses[("POST", f"/internal/jobs/{JOB_ID}/status")] = (200, {})
        self.client.set_status(JOB_ID, "auth_required", "sessão expirada")
        self.assertEqual(json.loads(self.api.requests[0]["body"])["error"], "sessão expirada")

    def test_conflict_exposes_current_status(self):
        self.api.responses[("POST", f"/internal/jobs/{JOB_ID}/status")] = (
            409, {"error": "transição de status inválida", "current_status": "collected"})
        with self.assertRaises(ApiError) as ctx:
            self.client.set_status(JOB_ID, "collecting")
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.current_status, "collected")

    def test_server_error_is_api_error(self):
        self.api.responses[("GET", f"/enrichments/{JOB_ID}")] = (500, {"error": "erro interno"})
        with self.assertRaises(ApiError) as ctx:
            self.client.get_job(JOB_ID)
        self.assertEqual(ctx.exception.status, 500)

    def test_network_failure_is_api_error_without_status(self):
        client = ApiClient("http://127.0.0.1:1", api_token="x", internal_token="y", timeout=2)
        with self.assertRaises(ApiError) as ctx:
            client.get_job(JOB_ID)
        self.assertIsNone(ctx.exception.status)

    def test_job_id_is_url_encoded(self):
        with self.assertRaises(ApiError):
            self.client.get_job("../../internal/x")
        self.assertNotIn("/internal/x", self.api.requests[0]["path"].replace("%2F", ""))
        self.assertIn("%2F", self.api.requests[0]["path"])

    def test_missing_tokens_send_no_authorization(self):
        client = ApiClient(self.api.url)
        with self.assertRaises(ApiError):
            client.get_job(JOB_ID)
        self.assertIsNone(self.api.requests[0]["auth"])


if __name__ == "__main__":
    unittest.main()
