"""Cliente HTTP (stdlib) da API do enrichment: o coletor lê o job e informa o andamento da coleta."""
import json
import urllib.error
import urllib.request
from urllib.parse import quote


class ApiError(Exception):
    """Falha ao falar com a API. `status` é o código HTTP (None = erro de rede/timeout)."""

    def __init__(self, message, status=None, current_status=None):
        super().__init__(message)
        self.status = status
        self.current_status = current_status


class ApiClient:
    def __init__(self, base_url, api_token=None, internal_token=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.internal_token = internal_token
        self.timeout = timeout

    def get_job(self, job_id):
        """GET /enrichments/{id} (token público da API)."""
        return self._request("GET", f"/enrichments/{quote(job_id, safe='')}", token=self.api_token)

    def set_status(self, job_id, status, error=""):
        """POST /internal/jobs/{id}/status (token interno). 409 ⇒ ApiError com `current_status`."""
        payload = {"status": status, "error": error}
        return self._request("POST", f"/internal/jobs/{quote(job_id, safe='')}/status", payload, self.internal_token)

    def _request(self, method, path, payload=None, token=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            body = {}
            try:
                body = json.loads(e.read().decode() or "{}")
            except ValueError:
                pass
            message = body.get("error") if isinstance(body, dict) else None
            raise ApiError(f"{method} {path}: HTTP {e.code} {message or ''}".strip(), status=e.code,
                           current_status=body.get("current_status") if isinstance(body, dict) else None) from e
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise ApiError(f"{method} {path}: {type(e).__name__}: {e}") from e
