# ADR-0002: Armazenar o HTML bruto e versionar os parsers

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

O LinkedIn muda o markup sem aviso. Em outubro/2026, os parsers de experiência, formação e idiomas pararam de
funcionar com o layout novo. Como os HTMLs coletados ainda estavam em `output/`, foi possível corrigir os parsers e
**reprocessar sem acessar o LinkedIn de novo** — o que economizou tempo e exposição da conta. Hoje isso foi sorte: o
código original removia os HTMLs após o parsing (linhas `os.remove` comentadas).

## Decisão

- Toda coleta grava o **HTML bruto de cada seção** em storage (S3 ou volume), com chave
  `<perfil>/<coletado_em>/<secao>.html`.
- Todo resultado de parsing registra a **`parser_version`** que o gerou.
- Existe um **job de reprocessamento**: dado um intervalo ou uma versão antiga de parser, refaz o parsing a partir do
  HTML armazenado e atualiza os registros.

## Consequências

- **+** Correção de parser não exige nova coleta; dados históricos podem ser corrigidos em lote.
- **+** HTML real disponível para depuração e para gerar fixtures ([ADR-0004](0004-testes-de-parser-com-fixtures-reais.md)).
- **−** Custo de storage (~100–600 KB por seção por perfil).
- **−** É dado pessoal armazenado: entra na política de retenção e exclusão do
  [ADR-0009](0009-conformidade-e-construir-vs-comprar.md).
