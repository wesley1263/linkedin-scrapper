# dev

`docker-compose.yml`: infraestrutura local que imita a nuvem (Postgres, MinIO ≈ S3, RabbitMQ ≈ SQS, Vault dev ≈ KMS), ADR-0013. `docker compose up -d`. Os serviços de aplicação entram quando tiverem Dockerfile e drivers de fila/storage (ADR-0014).
