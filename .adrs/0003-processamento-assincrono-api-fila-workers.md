# ADR-0003: Processamento assíncrono com API, fila e workers

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

O enriquecimento hoje é um script interativo (`python main.py` + `input()`), que leva cerca de 20–25s por perfil e
roda um navegador por vez na máquina de quem executa. Para ser consumido pelo cadastro, precisa de uma interface
programática. Uma requisição HTTP síncrona de 25s é frágil (timeouts, retentativas duplicadas) e acopla o cadastro à
disponibilidade do LinkedIn.

## Decisão

- **API (FastAPI):**
  - `POST /enrichments {linkedin_url, callback_url?}` → `202 {job_id}`
  - `GET /enrichments/{job_id}` → status e resultado
  - Webhook opcional ao concluir.
- **Fila** (Redis/RQ para começar; SQS se for para nuvem gerenciada) com retentativa e backoff.
- **Workers**: cada worker mantém **um navegador e uma sessão** ([ADR-0005](0005-gestao-de-sessao-e-limite-de-ritmo.md)),
  processa um job por vez e grava em **Postgres** (perfil, seções, status, `parser_version`) e no storage de HTML
  ([ADR-0002](0002-armazenar-html-bruto-e-versionar-parsers.md)).
- Idempotência: o mesmo `linkedin_url` normalizado com job em andamento retorna o `job_id` existente.

## Consequências

- **+** O cadastro não espera nem depende da latência do LinkedIn; falhas viram retentativas controladas.
- **+** Escala horizontal = mais workers (limitada pelo número de sessões/contas).
- **−** Novos componentes para operar: Redis/fila, Postgres, processo de API.
- **−** Cliente precisa lidar com resultado assíncrono (polling ou webhook).
