# ADR-0001: Separar coleta (Python) e parsing (Go), com o HTML bruto como fronteira

- **Status:** Proposto
- **Data:** 2026-10-15
- **Revisão:** substitui a proposta anterior deste ADR ("unificar coleta e parsing em Python"), descartada antes de ser aceita.

## Contexto

A coleta é feita em Python (Selenium) e o parsing em quatro binários Go, chamados via `subprocess` e trocando arquivos
soltos em disco. Problemas observados:

- Erros do Go não chegam ao Python: um `panic` no `linkedin-parser` deixou `profile.json` sem ser gerado e o fluxo
  seguiu como sucesso.
- Os arquivos Go são todos `package main`, sem `go.mod`, com funções duplicadas; `go build ./...` falha.
- Os parsers usam regex sobre HTML bruto e quebraram com a mudança de layout de outubro/2026.

O problema não é ter duas linguagens, e sim o **acoplamento**: as duas camadas rodam juntas, no mesmo fluxo, sem
contrato. E elas têm naturezas muito diferentes:

| | Coleta | Parsing |
|---|---|---|
| Acessa o LinkedIn | Sim, é a única parte que acessa | Nunca |
| Estado | Sessão, navegador, conta | Nenhum: recebe o HTML e devolve JSON |
| Por que falha | Bloqueio, checkpoint, timeout | Mudança de layout |
| Como escala | Limitada por conta e ritmo | Livre, é só CPU |
| Como se recupera de falha | Coletar de novo, com cuidado | Reprocessar o HTML já salvo |

## Decisão

Separar em duas camadas independentes, com o **zip de HTML bruto num storage de objetos** como fronteira:

- **Coleta (Python):** só abre o perfil, expande o conteúdo e salva os HTMLs num zip com `manifest.json`
  ([ADR-0010](0010-contrato-zip-e-manifest.md)), envia para o storage e publica uma mensagem na fila de parsing.
  Nenhuma regra de negócio nem acesso ao banco. A coleta também pode ser feita por uma extensão de navegador
  ([ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)), que produz o mesmo zip.
- **Parsing (Go):** projeto Go de verdade, com `go.mod`, `internal/parser/` (helpers compartilhados: datas en/pt,
  recorte de itens `entity-collection-item`, limpeza de texto), parsing por DOM com **goquery** no lugar de regex, e
  testes golden ([ADR-0004](0004-testes-de-parser-com-fixtures-reais.md)).
- O serviço Go também é dono da API, dos jobs e do banco ([ADR-0003](0003-processamento-assincrono-api-fila-workers.md)),
  para que a camada Python, a mais arriscada, tenha o mínimo de responsabilidades.

## Consequências

- **+** Corrigir um parser não exige coletar de novo: basta reprocessar os zips ([ADR-0002](0002-armazenar-html-bruto-e-versionar-parsers.md)).
- **+** Cada camada escala, falha e é implantada de forma independente.
- **+** O parser vira uma função pura sobre um arquivo, fácil de testar.
- **−** Dois deploys, dois pipelines de CI e um contrato (manifest + JSON de saída) que precisa ser versionado com disciplina.
- **−** Infraestrutura adicional: storage de objetos e fila.
