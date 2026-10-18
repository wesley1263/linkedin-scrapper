# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Toda implementação ou refatoração entra em
`[Unreleased]` no mesmo branch que a fez (ver `CLAUDE.md`). Ao publicar uma versão, `[Unreleased]` vira `[x.y.z] - data`.

## [Unreleased]

### Added
- Fila e storage plugáveis (ADR-0014): pacote `infra/` com portas `Queue`/`ObjectStorage`, fábricas por `QUEUE_DRIVER`/`STORAGE_DRIVER` e adaptadores `memory`, `fs`, `s3` (boto3, escrita condicional) e `rabbitmq` (pika, DLQ e retentativa com backoff); testes de integração em `tests/test_integration_adapters.py`.
- Zip imutável + `manifest.json` por coleta (ADR-0010): `bundle.py`, schema em `schemas/manifest.v1.schema.json`, publicação da mensagem `parse` com a chave do zip.
- Status explícito e observabilidade (ADR-0006): `observability.py`, `status.json` por job, exit codes 0/2/1, logging estruturado (`LOG_FORMAT=json`), screenshot/HTML das seções que falham.
- `PARSER_BIN_DIR` para apontar os binários dos parsers Go.
- CI dos testes Python (`collector-tests.yml`) e compose de infra local em `dev/`.
- Regras de fluxo no `CLAUDE.md` (branch por tarefa, sem commit automático, testes primeiro).

### Changed
- Parsers Go extraídos para o repositório `linkedin-enrichment` (ADR-0001/0013); o repositório `-dev` foi adiado.
- Compose usa `adobe/s3mock` no lugar do MinIO (que deixou de publicar imagens).
- Parsers rodam de forma síncrona logo após salvar cada seção; falha em uma seção não derruba as outras.

### Fixed
- Caminho do perfil do Chrome no macOS (`~/.linkedin_chrome_profile`, `CHROME_PROFILE_DIR`).
- Login com o novo layout (campos com ids aleatórios e formulário duplicado); credenciais lidas do `.env`.
- `profile.html` saindo como a página "Post": só o "more" do About é clicado.
