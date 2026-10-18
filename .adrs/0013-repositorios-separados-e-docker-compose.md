# ADR-0013: Repositórios separados por serviço e ambiente integrado com Docker Compose

- **Status:** Proposto
- **Data:** 2026-10-15

## Contexto

Com coleta e parsing separados ([ADR-0001](0001-separar-coleta-python-e-parsing-go.md)), as duas camadas têm
linguagens, ciclos de release, dependências e riscos diferentes. Hoje convivem no mesmo repositório: os scripts Python
e os parsers Go como arquivos `package main` soltos, sem `go.mod`. O sistema completo tem várias peças de
infraestrutura (Postgres, storage de objetos, fila, KMS) que precisam subir juntas para desenvolver e testar o fluxo
de ponta a ponta.

## Ajuste (2026-10-17)

O repositório `linkedin-enrichment-dev` foi **adiado**: com só dois serviços, um terceiro repositório para um compose e
um schema JSON é custo sem ganho. Por ora o compose de infra fica em `dev/` do coletor e o schema do manifest em
`schemas/` do coletor; o `linkedin-enrichment` terá uma cópia do schema, com teste que a compare, quando passar a ler o
zip. O repositório `-dev` volta a fazer sentido quando houver Dockerfiles dos serviços e o compose integrado rodar de
verdade. Além disso, o MinIO deixou de publicar imagens (Docker Hub e Quay), então o compose usa `adobe/s3mock` (serviço `s3`, endpoint `http://s3:9090`, bucket `raw-profiles` criado na subida), e o `minio-init` deixou de existir; os trechos com MinIO abaixo valem como referência de S3 local. O restante da decisão continua valendo.

## Decisão

### Um repositório por serviço

| Repositório | Linguagem | Conteúdo |
|---|---|---|
| `linkedin-collector` | Python | Coletor (consome `collect`, gera zip + manifest, publica em `parse`). **Este repositório** evolui para ele: os scripts Python atuais são a base, e os parsers Go saem daqui. |
| `linkedin-enrichment` | Go | API (`cmd/api`), parser worker (`cmd/parser-worker`), `internal/parser`, migrações do Postgres, webhooks. Recebe os parsers Go deste repositório e seus testes. |
| `linkedin-enrichment-dev` | YAML | Ambiente integrado: o `docker-compose.yml` abaixo, scripts de inicialização e o schema JSON compartilhado do manifest ([ADR-0010](0010-contrato-zip-e-manifest.md)). |

- Nada de monorepo: cada serviço tem seu próprio CI, versionamento e imagem Docker.
- Cada repositório de serviço tem um `docker-compose.yml` mínimo só com as dependências de que precisa para
  desenvolver sozinho (ex.: o coletor sobe só fila e MinIO).
- O contrato entre os serviços (manifest e mensagens das filas) é versionado no repositório `linkedin-enrichment-dev` e
  validado no CI dos dois serviços.
- A extensão de navegador do Modo A ([ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)), quando existir, também terá
  repositório próprio.

### Ambiente integrado (`linkedin-enrichment-dev/docker-compose.yml`)

Os repositórios ficam clonados lado a lado (`../linkedin-collector`, `../linkedin-enrichment`), e o compose constrói as
imagens a partir deles:

```yaml
name: linkedin-enrichment

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: enrichment
      POSTGRES_USER: enrichment
      POSTGRES_PASSWORD: enrichment          # só desenvolvimento local
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U enrichment"]
      interval: 5s

  minio:                                     # storage S3 compatível para os zips
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio12345
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]

  minio-init:                                # cria o bucket na primeira subida
    image: minio/mc
    depends_on: [minio]
    entrypoint: >
      sh -c "mc alias set local http://minio:9000 minio minio12345 &&
             mc mb --ignore-existing local/raw-profiles"

  rabbitmq:                                  # filas "collect" e "parse"
    image: rabbitmq:3-management
    ports: ["5672:5672", "15672:15672"]
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s

  vault:                                     # KMS local (Transit) para cifrar sessões, ADR-0011
    image: hashicorp/vault
    command: server -dev -dev-root-token-id=dev-root
    cap_add: [IPC_LOCK]
    ports: ["8200:8200"]

  api:
    build: ../linkedin-enrichment
    command: ["/app/api"]
    depends_on:
      postgres: {condition: service_healthy}
      rabbitmq: {condition: service_healthy}
    environment: &go-env
      QUEUE_DRIVER: rabbitmq
      STORAGE_DRIVER: s3
      DATABASE_URL: postgres://enrichment:enrichment@postgres:5432/enrichment?sslmode=disable
      AMQP_URL: amqp://guest:guest@rabbitmq:5672/
      S3_ENDPOINT: http://minio:9000
      S3_BUCKET: raw-profiles
      S3_ACCESS_KEY: minio
      S3_SECRET_KEY: minio12345
    ports: ["8080:8080"]

  parser-worker:
    build: ../linkedin-enrichment
    command: ["/app/parser-worker"]
    depends_on:
      postgres: {condition: service_healthy}
      rabbitmq: {condition: service_healthy}
    environment: *go-env
    # sem acesso ao Vault: o parser nunca vê sessões

  collector:
    build: ../linkedin-collector
    depends_on:
      rabbitmq: {condition: service_healthy}
      minio-init: {condition: service_completed_successfully}
    shm_size: 2gb                            # Chrome precisa de /dev/shm maior
    environment:
      QUEUE_DRIVER: rabbitmq
      STORAGE_DRIVER: s3
      AMQP_URL: amqp://guest:guest@rabbitmq:5672/
      S3_ENDPOINT: http://minio:9000
      S3_BUCKET: raw-profiles
      S3_ACCESS_KEY: minio
      S3_SECRET_KEY: minio12345
      VAULT_ADDR: http://vault:8200
      VAULT_TOKEN: dev-root                  # só desenvolvimento local
      HEADLESS: "true"
      MIN_SECONDS_BETWEEN_PROFILES: "30"
      MAX_PROFILES_PER_DAY: "100"

volumes:
  pgdata:
  miniodata:
```

Notas:

- **Fila e storage são plugáveis** ([ADR-0014](0014-camada-plugavel-de-fila-e-storage.md)): o compose usa RabbitMQ e
  MinIO, e a produção pode usar SQS, Pub/Sub, S3 ou GCS mudando só `QUEUE_DRIVER`, `STORAGE_DRIVER` e as variáveis de
  conexão. Para reproduzir AWS localmente, basta trocar os serviços por LocalStack e ajustar as mesmas variáveis.
- **Vault em modo dev** guarda tudo em memória e usa um token fixo; serve só para desenvolver a cifragem de sessões.
  Em produção, o coletor usa o KMS da nuvem ou um Vault real, com permissão só de descriptografar.
- O navegador remoto da conexão hospedada (Modo B, [ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)) fica fora da
  primeira versão ([ADR-0015](0015-escopo-da-primeira-versao.md)) e entra no compose quando for desenvolvido.
- Senhas e tokens do compose são valores fixos de desenvolvimento e nunca são reutilizados em outro ambiente.

## Consequências

- **+** Cada serviço evolui, testa e é implantado de forma independente, com seu próprio CI.
- **+** Um único `docker compose up` sobe o fluxo de ponta a ponta para desenvolvimento e testes de integração.
- **−** Mudanças que atravessam os dois serviços (ex.: nova versão do manifest) exigem PRs coordenados em mais de um
  repositório.
- **−** Três repositórios para manter, e o desenvolvedor precisa clonar os três lado a lado.
