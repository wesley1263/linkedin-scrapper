"""Logging e status de coleta (ADR-0006): lógica pura, sem Selenium, para poder ser testada isolada."""
import json
import logging
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

# Status do job
SUCCESS = "success"
PARTIAL = "partial"
FAILED = "failed"
AUTH_REQUIRED = "auth_required"
NOT_FOUND = "not_found"

# Status de parsing de uma seção (vem da linha JSON que cada binário Go imprime no stdout)
PARSE_OK = "ok"
PARSE_EMPTY = "empty"
PARSE_FAILED = "failed"


@dataclass
class SectionResult:
    section: str
    collect_status: str = "ok"          # "ok" ou "failed" (erro ao abrir/expandir/salvar a página)
    parse_status: Optional[str] = None  # ok / empty / failed; None se não chegou a parsear
    items: int = 0
    duration_ms: int = 0
    error: Optional[str] = None

    @property
    def ok(self):
        return self.collect_status == "ok" and self.parse_status in (PARSE_OK, PARSE_EMPTY)


def job_status(sections, auth_ok=True, found=True):
    """Status do job a partir do resultado de cada seção."""
    if not auth_ok:
        return AUTH_REQUIRED
    if not found:
        return NOT_FOUND
    if not sections:
        return FAILED
    good = sum(1 for s in sections if s.ok)
    if good == len(sections):
        return SUCCESS
    return PARTIAL if good else FAILED


def exit_code(status):
    """0 só para success; 2 para partial (há dados, mas incompletos); 1 para o resto."""
    return {SUCCESS: 0, PARTIAL: 2}.get(status, 1)


def run_parser(binary, html_path, json_path, section, timeout=60):
    """Roda o parser Go e devolve o SectionResult com o status da linha JSON do stdout.

    Sem linha de status (panic, binário ausente, timeout) a seção é `failed` e o stderr vai em `error`.
    """
    result = SectionResult(section=section)
    try:
        proc = subprocess.run([binary, html_path, json_path], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        result.parse_status, result.error = PARSE_FAILED, f"{type(e).__name__}: {e}"
        return result

    status = parse_status_line(proc.stdout)
    if status is None:
        result.parse_status = PARSE_FAILED
        result.error = f"parser saiu com código {proc.returncode} sem linha de status: {proc.stderr.strip()[-300:]}"
        return result

    result.parse_status = status.get("status", PARSE_FAILED)
    result.items = int(status.get("items", 0))
    result.duration_ms = int(status.get("duration_ms", 0))
    result.error = status.get("error") or None
    return result


def parse_status_line(stdout):
    """Última linha de stdout que seja um JSON com a chave `status` (ou None)."""
    for line in reversed(stdout.strip().splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and "status" in data:
            return data
    return None


def write_status_json(path, job_id, profile_url, status, sections, started_at, duration_ms):
    payload = {
        "job_id": job_id,
        "profile": profile_url,
        "status": status,
        "started_at": started_at.isoformat(),
        "duration_ms": duration_ms,
        "sections": {s.section: {k: v for k, v in asdict(s).items() if k != "section"} for s in sections},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


# --- logging ---------------------------------------------------------------------------------------------

# Campos de contexto (job_id, profile, section, duration_ms) que entram em toda linha de log
CONTEXT = {"job_id": None, "profile": None}
EXTRA_FIELDS = ("job_id", "profile", "section", "duration_ms")


class _ContextFilter(logging.Filter):
    def filter(self, record):
        for key, value in CONTEXT.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                entry[field] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class _ConsoleFormatter(logging.Formatter):
    def format(self, record):
        section = getattr(record, "section", None)
        prefix = f"[{section}] " if section else ""
        line = f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:<7} {prefix}{record.getMessage()}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging():
    """Console legível por padrão; LOG_FORMAT=json para uma linha JSON por evento; LOG_LEVEL ajusta o nível."""
    handler = logging.StreamHandler()
    handler.addFilter(_ContextFilter())
    handler.setFormatter(JsonFormatter() if os.environ.get("LOG_FORMAT", "").lower() == "json" else _ConsoleFormatter())
    root = logging.getLogger("scraper")
    root.handlers[:] = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    root.propagate = False
    return root
