# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Toda implementação ou refatoração entra em
`[Unreleased]` no mesmo branch que a fez (ver `CLAUDE.md`). Ao publicar uma versão, `[Unreleased]` vira `[x.y.z] - data`.

## [Unreleased]

### Added
- Ambiente local em Docker Compose (`docker-compose.yml` na raiz, que inclui o do `linkedin-enrichment`): coletor em container (`Dockerfile` com Chromium headless, sessão em volume `/data`) e serviço `collector-test` para os testes. `dev/docker-compose.yml` removido (a infra agora vem do repo irmão). `CHROME_BIN` opcional em `main.py`; `S3_ENDPOINT` nos testes de integração. README com os modos local e remoto.
- Limite de ritmo por conta (ADR-0005) no modo worker: intervalo mínimo entre perfis (`MIN_SECONDS_BETWEEN_PROFILES`, padrão 30) e teto diário UTC (`MAX_PROFILES_PER_DAY`, padrão 100), por `account_id` (sem conta: `default`), `0` desliga cada limite; estado em arquivo (`RATE_STATE_FILE`, padrão `./output/.ratelimit.json`, escrita atômica, sobrevive a reinício). Conta acima do ritmo adia a mensagem sem mexer no job (continua `queued`). Implementado em `ratelimit.py`.
- `infra.Defer`: o handler adia uma mensagem sem contar como falha (não incrementa `attempt`, não vai para a DLQ). No RabbitMQ usa a fila `<topic>.retry` (TTL `retry_delay`, 30 s, com dead-letter de volta para `<topic>`); no `MemoryQueue`, `deferred` + `release_deferred`.
- Modo serviço `python main.py --worker` (ADR-0003): consome o tópico `collect` (job criado pela API), coleta o perfil sem rodar os parsers locais, grava o zip no storage, marca o job `collected` e só então publica em `parse`. Status do job pela API (`api_client.py`, endpoint interno do enrichment): `queued → collecting → collected | collect_failed | auth_required`. Mensagem repetida é segura (job `collecting` é retomado, outros status são ignorados); perfil inexistente, falha total ou erro inesperado viram `collect_failed` com o motivo, e `auth_required` quando o login é necessário. Lógica em `collect_worker.py` (testada sem Selenium).
- `bundle.store_bundle`, `bundle.expected_urls`/`SECTION_PATHS` e `observability.CollectOutcome`/`collect_job_status` (status do job só pelo `collect_status`, já que o parsing é do parser worker).
- Fila e storage plugáveis (ADR-0014): pacote `infra/` com portas `Queue`/`ObjectStorage`, fábricas por `QUEUE_DRIVER`/`STORAGE_DRIVER` e adaptadores `memory`, `fs`, `s3` (boto3, escrita condicional) e `rabbitmq` (pika, DLQ e retentativa com backoff); testes de integração em `tests/test_integration_adapters.py`.
- Zip imutável + `manifest.json` por coleta (ADR-0010): `bundle.py`, schema em `schemas/manifest.v1.schema.json`, publicação da mensagem `parse` com a chave do zip.
- Status explícito e observabilidade (ADR-0006): `observability.py`, `status.json` por job, exit codes 0/2/1, logging estruturado (`LOG_FORMAT=json`), screenshot/HTML das seções que falham.
- `PARSER_BIN_DIR` para apontar os binários dos parsers Go.
- CI dos testes Python (`collector-tests.yml`) e compose de infra local em `dev/`.
- Regras de fluxo no `CLAUDE.md` (branch por tarefa, sem commit automático, testes primeiro).

### Changed
- Convenção registrada no `CLAUDE.md`: APIs HTTP do coletor Python usam FastAPI (o serviço Go segue com Gin).
- `main.py` separado em `scrape_profile()` (coleta, devolve `CollectOutcome`) e os modos CLI/worker; o CLI continua coletando, parseando localmente e publicando em `parse` como antes.
- Parsers Go extraídos para o repositório `linkedin-enrichment` (ADR-0001/0013); o repositório `-dev` foi adiado.
- Compose usa `adobe/s3mock` no lugar do MinIO (que deixou de publicar imagens).
- Parsers rodam de forma síncrona logo após salvar cada seção; falha em uma seção não derruba as outras.

### Fixed
- Caminho do perfil do Chrome no macOS (`~/.linkedin_chrome_profile`, `CHROME_PROFILE_DIR`).
- Login com o novo layout (campos com ids aleatórios e formulário duplicado); credenciais lidas do `.env`.
- `profile.html` saindo como a página "Post": só o "more" do About é clicado.
