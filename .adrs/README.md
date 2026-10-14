# Architecture Decision Records

Decisões de arquitetura para transformar o scraper em um serviço de enriquecimento de cadastro.
O contexto geral, o diagnóstico e o roteiro estão em [melhorias.md](melhorias.md).

Formato: [Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) — Contexto, Decisão, Consequências.
Status possíveis: **Proposto**, **Aceito**, **Rejeitado**, **Substituído por ADR-XXXX**.

| ADR | Título | Status |
|---|---|---|
| [0001](0001-unificar-coleta-e-parsing-em-python.md) | Unificar coleta e parsing em um único runtime Python | Proposto |
| [0002](0002-armazenar-html-bruto-e-versionar-parsers.md) | Armazenar o HTML bruto e versionar os parsers | Proposto |
| [0003](0003-processamento-assincrono-api-fila-workers.md) | Processamento assíncrono com API, fila e workers | Proposto |
| [0004](0004-testes-de-parser-com-fixtures-reais.md) | Testes de parser com fixtures reais anonimizadas | Proposto |
| [0005](0005-gestao-de-sessao-e-limite-de-ritmo.md) | Gestão de sessão e limite de ritmo por conta | Proposto |
| [0006](0006-status-explicito-e-observabilidade.md) | Status explícito por seção e observabilidade | Proposto |
| [0007](0007-cache-com-ttl.md) | Cache de perfis com TTL | Proposto |
| [0008](0008-configuracao-por-ambiente-e-container.md) | Configuração por ambiente e execução em container | Proposto |
| [0009](0009-conformidade-e-construir-vs-comprar.md) | Conformidade (LGPD e termos de uso) e construir vs. comprar | Proposto |

Para um novo ADR: copie a estrutura de um existente, use o próximo número e adicione a linha nesta tabela.
