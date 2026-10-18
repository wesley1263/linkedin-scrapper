"""Consumidor do tópico `collect` (ADR-0003): lógica pura, sem Selenium; scrape/api/storage/queue são injetados.

Contrato de status do job (o enrichment valida a máquina de estados; 409 = transição inválida):
  queued -> collecting -> collected (zip no storage, ANTES de publicar em `parse`) | collect_failed | auth_required
Mensagem repetida é segura: job `collecting` é retomado (a tentativa anterior caiu), qualquer outro status ≠ queued é ignorado.
"""
import json
import logging
import time

import bundle
import observability as obs
from api_client import ApiError

COLLECT_TOPIC = "collect"
PARSE_TOPIC = "parse"

log = logging.getLogger("scraper.collect")


def parse_request(body):
    """Valida a mensagem de `collect`; ValueError se inválida (a mensagem vai para a DLQ do adaptador)."""
    try:
        data = json.loads(body)
    except ValueError as e:
        raise ValueError(f"mensagem collect inválida: {e}") from e
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(f"schema_version não suportada: {data.get('schema_version') if isinstance(data, dict) else data!r}")
    for key in ("job_id", "linkedin_url"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError(f"{key} ausente na mensagem collect")
    return data


def _failure_summary(results):
    errors = [f"{r.section}: {r.error}" for r in results if r.error]
    return "; ".join(errors) or "nenhum HTML coletado"


def _publish_with_retry(queue, body, attempts, sleep):
    for attempt in range(attempts):
        try:
            queue.publish(PARSE_TOPIC, body)
            return
        except Exception:
            if attempt == attempts - 1:
                raise
            log.warning("Falha ao publicar em parse (tentativa %d/%d)", attempt + 1, attempts, exc_info=True)
            sleep(2 ** attempt)


def handle_collect(body, *, api, scrape, storage, queue, sleep=time.sleep, publish_attempts=3):
    """Processa uma mensagem `collect`. Levanta exceção só para o que vale reentregar (infra fora do ar, mensagem inválida)."""
    req = parse_request(body)
    job_id, url = req["job_id"], req["linkedin_url"]
    extra = {"job_id": job_id}

    status = api.get_job(job_id).get("status")
    if status == "queued":
        try:
            api.set_status(job_id, "collecting")
        except ApiError as e:
            if e.status == 409:
                log.info("Outra entrega assumiu o job (%s): ignorando", e.current_status, extra=extra)
                return "skipped"
            raise
    elif status == "collecting":
        log.warning("Job já estava collecting: retomando a coleta", extra=extra)
    else:
        log.info("Job em %s: nada a coletar", status, extra=extra)
        return "skipped"

    try:
        outcome = scrape(url, job_id)
    except Exception as e:
        log.exception("Erro inesperado na coleta", extra=extra)
        api.set_status(job_id, "collect_failed", f"{type(e).__name__}: {e}")
        return "collect_failed"

    if outcome.status == obs.AUTH_REQUIRED:
        api.set_status(job_id, "auth_required", "login do LinkedIn necessário (sessão ausente ou expirada)")
        return "auth_required"
    if outcome.status == obs.NOT_FOUND:
        api.set_status(job_id, "collect_failed", "perfil não encontrado")
        return "collect_failed"

    stored = bundle.store_bundle(storage, job_id, req.get("account_id") or None, outcome.base_url,
                                 outcome.dir_name, outcome.output_dir, outcome.started_at, outcome.results)
    if stored is None:
        api.set_status(job_id, "collect_failed", _failure_summary(outcome.results))
        return "collect_failed"
    key, manifest = stored
    log.info("Zip gravado: %s", key, extra=extra)

    # O job precisa estar `collected` quando o worker de parsing receber a mensagem (ele recusa outros status)
    api.set_status(job_id, "collected")
    _publish_with_retry(queue, bundle.parse_message(manifest, key), publish_attempts, sleep)
    log.info("Publicado em parse: %s", key, extra=extra)
    return "collected"
