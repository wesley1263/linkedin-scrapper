# ADR-0001: Unificar coleta e parsing em um único runtime Python

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

A coleta é feita em Python (Selenium) e o parsing em quatro binários Go independentes, chamados via `subprocess` e
conversando por arquivos HTML/JSON em disco. Consequências observadas:

- Dois runtimes para instalar, compilar e versionar; os binários são gerados à mão e não estão no repositório.
- Os arquivos Go são todos `package main`, sem `go.mod`, com funções duplicadas (`cleanHTML`, `balancedBlock`,
  parsing de datas) — `go build ./...` falha e cada correção precisa ser replicada.
- Erros no Go não chegam ao Python: um `panic` no `linkedin-parser` deixou `profile.json` sem ser gerado e o fluxo
  seguiu como sucesso.
- Os parsers usam regex sobre HTML bruto; foi preciso implementar recorte por balanceamento de `<div>` para compensar a
  falta de um parser de DOM.

## Decisão

Consolidar coleta e parsing em **um único pacote Python**:

- **Playwright** no lugar do Selenium para a coleta (esperas nativas por seletor/rede, contextos isolados por sessão,
  melhor suporte a headless).
- **selectolax** (ou lxml) para parsing via DOM e seletores CSS, no lugar de regex.
- Um módulo por seção (`profile`, `experience`, `education`, `languages`) com utilitários compartilhados (datas en/pt,
  limpeza de texto, recorte de itens `entity-collection-item`).
- Modelos de saída em **pydantic**, que passam a ser o contrato do JSON.
- `linkedin.py` (download de PDF) passa a reutilizar o mesmo módulo de sessão/driver.

A alternativa de unificar em Go (com `rod`/`chromedp` + `goquery`) é tecnicamente equivalente; a escolha por Python se
deve ao scraper e ao provável framework de API (FastAPI) já estarem em Python.

## Consequências

- **+** Um runtime, um deploy, uma suíte de testes; erros de parsing viram exceções tratáveis no mesmo processo.
- **+** Parsing por DOM é mais legível e menos sensível a detalhes do markup.
- **−** Reescrever os quatro parsers (a lógica atual em Go serve de especificação, e os fixtures do
  [ADR-0004](0004-testes-de-parser-com-fixtures-reais.md) garantem paridade).
- **−** Migração Selenium → Playwright exige revalidar login, reutilização de sessão e expansão de conteúdo.
