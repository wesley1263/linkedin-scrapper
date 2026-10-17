# linkedin-enrichment-dev

Ambiente integrado e contrato compartilhado entre os serviços (ADR-0013).

- `docker-compose.yml`: infraestrutura local (Postgres, MinIO, RabbitMQ, Vault dev). `docker compose up -d`.
- `schemas/manifest.v1.schema.json`: schema do `manifest.json` do zip de coleta (ADR-0010), validado no CI do coletor e do enrichment.
