# ADR-0003: Processamento assíncrono com API Go, filas e workers

- **Status:** Proposto
- **Data:** 2026-10-15
- **Revisão:** a versão anterior previa um único worker Python fazendo coleta e parsing; agora as camadas são separadas ([ADR-0001](0001-separar-coleta-python-e-parsing-go.md)).

## Contexto

O enriquecimento hoje é um script interativo (`python main.py` + `input()`), de ~20–25s por perfil. Para ser
consumido por outros sistemas, precisa de uma interface programática. Uma requisição HTTP síncrona de 25s é frágil
(timeouts, retentativas duplicadas) e acopla o cliente à disponibilidade do LinkedIn.

## Decisão

```
Cliente ──POST /enrichments──▶ API (Go) ──▶ Postgres (jobs, resultados)
        ◀── 202 {job_id}         │  ▲
        ◀── webhook / GET        │  │
                                 ▼  │
                      fila "collect"│
                                 ▼  │
                    Coletor (Python, 1 sessão por vez)
                    ├─ zip + manifest ──▶ Storage (S3/MinIO)
                    └─ publica em "parse"
                                 ▼  │
                    Parser worker (Go) ──┘
```

- **API (Go):**
  - `POST /enrichments {linkedin_url, account_id, callback_url?}` → `202 {job_id}`
  - `GET /enrichments/{job_id}` → status e resultado
  - Webhook assinado com HMAC, com retentativas e espera crescente.
- **Duas filas:** `collect` (API → coletor) e `parse` (coletor → parser). SQS se a infraestrutura for AWS; senão
  RabbitMQ ou Redis Streams.
- O coletor **publica em `parse` só depois do upload do zip** concluído, em vez de depender do evento nativo do bucket.
- **Estados do job:** `queued → collecting → collected → parsing → done`, e as falhas `collect_failed`,
  `parse_failed` e `auth_required`.
  - `parse_failed` é recuperável sem tocar no LinkedIn: corrige o parser e reprocessa o zip.
  - `collect_failed` volta para a fila com espera crescente, respeitando o ritmo da conta ([ADR-0005](0005-gestao-de-sessao-e-limite-de-ritmo.md)).
  - `auth_required` aguarda o usuário reconectar a conta ([ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)).
- **Idempotência:** o mesmo `linkedin_url` normalizado com job em andamento retorna o `job_id` existente; o parser
  faz upsert, então reprocessar o mesmo zip não duplica dados.
- Resultado por seção em Postgres (JSONB) com `parser_version`; tabelas normalizadas quando o modelo do cadastro
  estiver definido.

## Consequências

- **+** O cliente não espera nem depende da latência do LinkedIn; falhas viram retentativas controladas.
- **+** Coleta e parsing escalam separadamente.
- **−** Componentes para operar: API, duas filas, storage, Postgres, dois tipos de worker.
- **−** O cliente precisa lidar com resultado assíncrono (polling ou webhook).
