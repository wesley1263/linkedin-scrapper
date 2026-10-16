# ADR-0014: Camada plugável de fila e storage

- **Status:** Proposto
- **Data:** 2026-10-15

## Contexto

O pipeline depende de uma fila (`collect`, `parse`) e de um storage de objetos (zips de HTML). A tecnologia de
produção ainda não está decidida: RabbitMQ, SQS ou Pub/Sub do GCP para a fila; MinIO, S3 ou GCS para o storage. A
regra de negócio não pode depender dessa escolha, e trocar de provedor tem de ser simples, sem reescrever coletor nem
parser.

## Decisão

Padrão **portas e adaptadores**, o mais simples possível: **uma interface pequena por recurso** em cada serviço, um
adaptador por provedor e a escolha do adaptador por variável de ambiente. A regra de negócio só conhece a interface.

### Interfaces

Go (`linkedin-enrichment`, pacote `internal/platform`):

```go
type Message struct {
	ID      string
	Body    []byte // JSON com schema_version
	Attempt int
}

// Handler: retornar nil confirma a mensagem; retornar erro faz o adaptador reentregar (com backoff).
type Handler func(ctx context.Context, msg Message) error

type Queue interface {
	Publish(ctx context.Context, topic string, body []byte) error
	Consume(ctx context.Context, topic string, handle Handler) error // bloqueia até ctx ser cancelado
}

type ObjectStorage interface {
	Put(ctx context.Context, key string, r io.Reader) error
	Get(ctx context.Context, key string) (io.ReadCloser, error)
}
```

Python (`linkedin-collector`, módulo `platform`):

```python
class Queue(Protocol):
    def publish(self, topic: str, body: bytes) -> None: ...
    def consume(self, topic: str, handle: Callable[[Message], None]) -> None: ...  # exceção = reentrega

class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
```

### Adaptadores e configuração

| Variável | Valores | Observação |
|---|---|---|
| `QUEUE_DRIVER` | `rabbitmq`, `sqs`, `pubsub`, `memory` | `memory` para testes |
| `STORAGE_DRIVER` | `s3`, `gcs`, `fs` | `s3` atende MinIO, AWS S3 e LocalStack só trocando `S3_ENDPOINT`; `fs` para testes |

- Uma função de fábrica por recurso (`NewQueue(cfg)`, `NewObjectStorage(cfg)`) lê a variável e devolve o adaptador.
  É o único ponto do código que conhece os provedores.
- Só se implementa o adaptador que for de fato usado. O primeiro é `rabbitmq` + `s3` (MinIO), que é o do compose
  local ([ADR-0013](0013-repositorios-separados-e-docker-compose.md)).
- No Go, os adaptadores podem ser escritos sobre o **Go CDK** (`gocloud.dev/pubsub` e `gocloud.dev/blob`), que já
  suporta RabbitMQ, SQS, Pub/Sub, S3, GCS e sistema de arquivos. No Python não há equivalente maduro; cada adaptador é
  uma classe fina sobre o SDK do provedor (`pika`, `boto3`, `google-cloud-pubsub`).

### Regras para a troca ser de fato simples

A interface só vale se a regra de negócio não depender de recursos específicos de um provedor:

- **Entrega pelo menos uma vez**: todo handler é idempotente (o parser faz upsert; o coletor confere o status do job
  antes de coletar de novo).
- **Sem garantia de ordem.**
- **Mensagem pequena**: só IDs e a chave do zip no storage, nunca o conteúdo; cabe no limite de qualquer provedor.
- **Retentativa e fila de mensagens mortas (DLQ)** configuradas no adaptador e na infraestrutura, não no handler.
- Nada de recursos exclusivos (exchanges e routing keys do RabbitMQ, filas FIFO do SQS, filtros do Pub/Sub) na
  regra de negócio.

O mesmo padrão vale para a cifragem de sessões do [ADR-0011](0011-guardar-sessao-nao-senha.md): uma interface
`SessionCipher` com `Encrypt`/`Decrypt` e adaptadores `vault`, `aws-kms`, `gcp-kms`.

## Consequências

- **+** Trocar de provedor é implementar um adaptador e mudar variáveis de ambiente.
- **+** Testes de regra de negócio rodam com `memory` e `fs`, sem infraestrutura.
- **−** Recursos avançados de cada provedor ficam de fora, de propósito.
- **−** Cada adaptador novo precisa de um teste de integração contra o provedor real (ou o emulador).
