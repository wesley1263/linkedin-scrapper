# ADR-0008: Configuração por ambiente e execução em container

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

O projeto só roda na máquina de quem o escreveu: caminho absoluto do perfil do Chrome (`/home/weslei/...`), binários
chamados como `./linkedin-parser` (dependem do diretório atual), versão do Chrome/driver não fixada e saída em
`./output` relativo.

## Decisão

- **Toda configuração por variável de ambiente** (12-factor): diretório de perfil, storage, banco, fila, limites de
  ritmo, TTL de cache, modo headless.
- **Imagem Docker** com Chrome/Chromium e driver (ou Playwright) em **versões fixadas**, rodando headless.
- Nenhum caminho relativo ao diretório de execução; nenhum caminho de usuário no código.
- `docker compose` para desenvolvimento local (API, worker, Redis, Postgres).

## Consequências

- **+** Reprodutível em qualquer máquina e em produção; mais de um worker passa a ser trivial.
- **+** Atualização do navegador vira mudança explícita e testável.
- **−** Imagem com navegador é grande (~1 GB) e precisa de `--shm-size`/`--disable-dev-shm-usage`.
