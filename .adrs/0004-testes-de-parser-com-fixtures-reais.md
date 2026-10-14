# ADR-0004: Testes de parser com fixtures reais anonimizadas

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

Não há nenhum teste no projeto. Quando o LinkedIn mudou o layout, três parsers passaram a retornar dados errados ou
vazios — e o de formação devolvia **dados fictícios** de exemplo — sem que nada sinalizasse. As correções foram
validadas manualmente rodando os binários contra HTMLs em `output/`.

## Decisão

- Criar uma suíte de **testes golden**: para cada seção, HTMLs reais como entrada e o JSON esperado como saída.
- Os fixtures vêm dos HTMLs coletados, **anonimizados** antes de entrar no repositório (nomes, URLs de perfil, fotos e
  textos livres substituídos), preservando a estrutura do markup.
- Cobrir explicitamente os formatos conhecidos: cargo único e vários cargos na mesma empresa; datas só com ano, com mês,
  "Present" e data única; seção vazia ("Nothing to see for now"); textos em inglês e português.
- Toda correção de parser por mudança de layout começa adicionando o fixture novo que reproduz o problema.
- Rodar em CI a cada push.

## Consequências

- **+** Mudanças de layout viram testes falhando, não dados errados no cadastro.
- **+** Viabiliza a reescrita do [ADR-0001](0001-unificar-coleta-e-parsing-em-python.md) com garantia de paridade.
- **−** Esforço inicial de anonimização; fixtures precisam ser atualizados quando o layout muda.
- **Atenção:** HTML não anonimizado de terceiros **não** deve ser commitado (`output/` está no `.gitignore`).
