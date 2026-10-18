"""Zip imutável + manifest.json de uma coleta (ADR-0010): o contrato entre coleta e parsing. Só stdlib."""
import io
import json
import os
import zipfile
from urllib.parse import unquote, urlsplit

SCHEMA_VERSION = 1
COLLECTOR_VERSION = "0.1.0"

# Status de coleta de uma seção no manifest
OK = "ok"
REDIRECTED = "redirected"
TIMEOUT = "timeout"
NOT_COLLECTED = "not_collected"
SECTION_STATUSES = (OK, REDIRECTED, TIMEOUT, NOT_COLLECTED)


def _same_page(expected, actual):
    """Compara duas URLs ignorando query, barra final, maiúsculas e percent-encoding."""
    def norm(url):
        parts = urlsplit(url)
        return (parts.netloc.lower(), unquote(parts.path).rstrip("/").lower())
    return norm(expected) == norm(actual)


def section_status(result, expected_url):
    """Status de coleta da seção para o manifest, a partir do SectionResult e da URL esperada.

    Se a coleta falhou, a seção não tem HTML confiável. Se terminou numa URL diferente da pedida
    (ex.: perfil privado redirecionando para login), o HTML existe mas não é da seção.
    """
    if result.collect_status != "ok":
        return TIMEOUT if (result.error or "").startswith("TimeoutException") else NOT_COLLECTED
    if result.final_url and not _same_page(expected_url, result.final_url):
        return REDIRECTED
    return OK


def build_manifest(job_id, account_id, linkedin_url, collected_at, sections, collector_type="server"):
    """`sections`: {nome: (arquivo, status, final_url)}. Seções sem HTML (not_collected/timeout) levam file=None."""
    manifest_sections = {}
    for name, (filename, status, final_url) in sections.items():
        entry = {"file": filename if status in (OK, REDIRECTED) else None, "status": status}
        if status == REDIRECTED:
            entry["final_url"] = final_url
        manifest_sections[name] = entry
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "account_id": account_id,
        "linkedin_url": linkedin_url,
        "collected_at": collected_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "collector": {"type": collector_type, "version": COLLECTOR_VERSION},
        "sections": manifest_sections,
    }


def validate_manifest(manifest):
    """Devolve a lista de problemas do manifest (vazia se válido). Sem dependências, espelha schemas/manifest.v1.schema.json."""
    if not isinstance(manifest, dict):
        return ["manifest não é um objeto"]
    problems = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version {manifest.get('schema_version')!r} não suportada")
    for key in ("job_id", "linkedin_url", "collected_at"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            problems.append(f"{key} ausente ou vazio")
    if manifest.get("account_id") is not None and not isinstance(manifest["account_id"], str):
        problems.append("account_id deve ser string ou null")
    collector = manifest.get("collector")
    if not isinstance(collector, dict) or collector.get("type") not in ("server", "extension") \
            or not isinstance(collector.get("version"), str):
        problems.append("collector inválido (type server|extension e version)")
    sections = manifest.get("sections")
    if not isinstance(sections, dict) or not sections:
        problems.append("sections ausente ou vazio")
        return problems
    for name, entry in sections.items():
        if not isinstance(entry, dict) or entry.get("status") not in SECTION_STATUSES:
            problems.append(f"sections.{name}.status inválido")
            continue
        has_file = entry.get("file") is not None
        if has_file != (entry["status"] in (OK, REDIRECTED)):
            problems.append(f"sections.{name}: file deve existir só para ok/redirected")
        if entry["status"] == REDIRECTED and not entry.get("final_url"):
            problems.append(f"sections.{name}: redirected exige final_url")
    return problems


def bundle_key(profile, manifest):
    """Chave no storage: `raw/<perfil-normalizado>/<collected_at>.zip` (colunas e hífens do timestamp removidos)."""
    stamp = manifest["collected_at"].replace("-", "").replace(":", "")
    return f"raw/{profile}/{stamp}.zip"


def build_zip(source_dir, manifest):
    """Zip em memória com o manifest e os HTMLs listados nele (lidos de `source_dir`)."""
    problems = validate_manifest(manifest)
    if problems:
        raise ValueError("manifest inválido: " + "; ".join(problems))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for entry in manifest["sections"].values():
            if entry["file"]:
                zf.write(os.path.join(source_dir, entry["file"]), entry["file"])
    return buf.getvalue()


def parse_message(manifest, zip_key):
    """Mensagem do tópico `parse` (ADR-0014: só IDs e a chave do zip, nunca o conteúdo)."""
    return json.dumps({
        "schema_version": SCHEMA_VERSION,
        "job_id": manifest["job_id"],
        "linkedin_url": manifest["linkedin_url"],
        "zip_key": zip_key,
    }).encode()


# Seção -> caminho relativo ao perfil (fonte única; main.DETAIL_SECTIONS deriva daqui)
SECTION_PATHS = {
    "experience": "details/experience/",
    "education": "details/education/",
    "languages": "details/languages/",
}


def expected_urls(base_url):
    return {"profile": base_url, **{name: f"{base_url}{path}" for name, path in SECTION_PATHS.items()}}


def store_bundle(storage, job_id, account_id, base_url, dir_name, output_dir, collected_at, results):
    """Monta manifest + zip dos HTMLs coletados e grava no storage. Devolve (key, manifest), ou None se não há HTML.

    Não publica em `parse` (quem chama decide a ordem em relação ao status do job). Erros de storage propagam.
    """
    expected = expected_urls(base_url)
    sections = {
        r.section: (f"{r.section}.html", section_status(r, expected[r.section]), r.final_url)
        for r in results
    }
    if not any(status in (OK, REDIRECTED) for _, status, _ in sections.values()):
        return None
    manifest = build_manifest(job_id, account_id, base_url, collected_at, sections)
    key = bundle_key(dir_name, manifest)
    storage.put(key, build_zip(output_dir, manifest))
    return key, manifest
