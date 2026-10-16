# ADR-0015: Escopo da primeira versão — paridade com o script atual

- **Status:** Proposto
- **Data:** 2026-10-15

## Contexto

O script atual (`main.py` + parsers Go) já faz bem o essencial: abre o perfil de um candidato e extrai perfil,
experiências, formação e idiomas para arquivos JSON. Os ADRs descrevem um sistema bem maior (dois modos de conexão,
navegador remoto, extensão, multi-tenant). Construir tudo de uma vez atrasaria o valor e misturaria problemas
difíceis com o que já funciona.

## Decisão

A primeira versão dos serviços entrega **o que o script já faz, só que bem estruturado**: dados no banco, serviços
passando a bola por fila, falhas visíveis.

### Dentro do escopo

- **Coletor Python** (`linkedin-collector`): consome `collect`, coleta as 4 seções (lógica atual do `main.py`: abas
  paralelas, `wait_until_stable`, headless), gera zip + manifest ([ADR-0010](0010-contrato-zip-e-manifest.md)), envia
  ao storage e publica em `parse`.
- **Serviço Go** (`linkedin-enrichment`):
  - API: `POST /enrichments`, `GET /enrichments/{id}`, webhook opcional ([ADR-0003](0003-processamento-assincrono-api-fila-workers.md));
  - parser worker com os 4 parsers atuais migrados para um projeto Go com `go.mod` e testes golden
    ([ADR-0004](0004-testes-de-parser-com-fixtures-reais.md));
  - Postgres com jobs e resultado por seção (JSONB + `parser_version`).
- **Camada plugável** de fila e storage, com os adaptadores `rabbitmq` e `s3`
  ([ADR-0014](0014-camada-plugavel-de-fila-e-storage.md)).
- **Status por job e por seção** ([ADR-0006](0006-status-explicito-e-observabilidade.md)).
- **Sessão:** uma ou poucas contas internas, conectadas por **login interativo com o coletor em modo visível** (como o
  `--visible` de hoje); a sessão resultante é gravada cifrada ([ADR-0011](0011-guardar-sessao-nao-senha.md)). Senha
  nunca é persistida.
- **Docker Compose** integrado ([ADR-0013](0013-repositorios-separados-e-docker-compose.md)).

### Fora do escopo (depois que o fluxo estiver redondo)

- Navegador remoto e conexão hospedada (Modo B do [ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)).
- Extensão de navegador (Modo A).
- Multi-tenant, API keys por cliente e consentimento por usuário final.
- Cache com TTL ([ADR-0007](0007-cache-com-ttl.md)) e reprocessamento em lote por versão de parser (o reprocessamento
  manual de um zip já entra, porque é só republicar a mensagem em `parse`).
- Adaptadores de fila e storage além de `rabbitmq` e `s3`.

### Critério de pronto

- Um `POST /enrichments` com uma URL de perfil termina em `done` e o banco tem as 4 seções com o mesmo conteúdo que o
  script atual gera para os mesmos HTMLs (verificado pelos testes golden).
- Falha de coleta ou de parsing aparece no status do job, nunca como resultado vazio silencioso.

### Ponto a fechar antes da paridade

O parser de perfil (`main.go`) ainda é inconsistente com o layout atual: em coletas de outubro/2026 alguns perfis
saem completos e outros sem endereço, headline, empresa ou descrição. Os fixtures do
[ADR-0004](0004-testes-de-parser-com-fixtures-reais.md) devem cobrir esses casos e o parser deve ser corrigido na
migração.

## Consequências

- **+** Entrega valor cedo, sobre algo que já foi validado na prática.
- **+** A base (filas, storage, banco, contrato) fica pronta para os modos A e B sem retrabalho.
- **−** Enquanto os modos A e B não existem, conectar uma conta exige alguém rodar o coletor em modo visível.
