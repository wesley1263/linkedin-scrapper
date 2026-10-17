# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão geral

Scraper de perfis do LinkedIn em duas camadas: **Python + Selenium** navega e salva o HTML de cada seção do perfil; **parsers em Go** (um binário por seção) leem esse HTML e geram JSON. Documentação de uso e schemas dos JSON de saída estão no `README.md`.

## Comandos

```bash
pipenv install                        # dependências Python (Python 3.12)
export LINKEDIN_EMAIL=... LINKEDIN_PASSWORD=...   # obrigatórias nos dois scripts (ou defina no .env)
pipenv run python main.py [<url>]     # scraping completo, headless; sem <url> pede via input()
pipenv run python main.py --visible   # abre o Chrome visível (necessário p/ resolver checkpoint/2FA)
pipenv run python linkedin.py <url>   # baixa o PDF do perfil para ./resumes/
```

Os parsers Go vivem no repositório `linkedin-enrichment` (clonado ao lado: `../linkedin-enrichment`; ADR-0001/0013). Compile lá e o coletor os executa a partir de `PARSER_BIN_DIR` (padrão `../linkedin-enrichment/bin`; rodar `main.py` a partir da raiz deste repo):

```bash
cd ../linkedin-enrichment && for p in linkedin-parser experience-parser education-parser language-parser; do go build -o bin/$p ./cmd/$p; done
```

Testes Python (`observability.py`, stdlib `unittest`), rodando da raiz do repo: `pipenv run python -m unittest discover -s tests -t .`

O CI `collector-tests.yml` roda os testes Python (só stdlib: `observability.py` e `bundle.py` não podem importar Selenium). Testes e fixtures dos parsers ficam no `linkedin-enrichment`. Para validar um parser contra um HTML real coletado aqui:

```bash
../linkedin-enrichment/bin/experience-parser output/<username>/experience.html /tmp/out.json
```

## Arquitetura

- **`main.py`** (`LinkedInScraper`): reutiliza primeiro a sessão do perfil persistente do Chrome (`--user-data-dir`, por padrão `~/.linkedin_chrome_profile`; sobrescreva com `CHROME_PROFILE_DIR`), depois `linkedin_cookies.json`, e só faz login com usuário/senha (lidos do `.env` via `python-dotenv`) se ambos falharem. Login é detectado pela URL (`/feed`), não por classes CSS.
  - A página `/login` não tem mais `#username`/`#password`: os campos têm ids aleatórios e o formulário é renderizado **duas vezes, uma oculta** — por isso `login()` usa o primeiro campo *visível* e envia com Enter. Em falha, grava `output/login_error.{png,html}` com o que o driver viu.
  - Fluxo: abre as seções de detalhe (`DETAIL_SECTIONS`) em abas via `window.open` para carregarem em paralelo, carrega o perfil na aba principal e depois visita cada aba para expandir conteúdo (scroll / "Load more" / "more" do About) e gravar `output/<username>/<secao>.html`. Cada parser Go roda na hora (`observability.run_parser`, síncrono: leva ms e assim o screenshot de uma falha ainda é da aba da seção) assim que o HTML é salvo; os binários precisam estar compilados em `PARSER_BIN_DIR` e o script rodar a partir da raiz.
  - Status (ADR-0006): cada seção vira um `SectionResult` (`collect_status` + `parse_status`) e o job `success`/`partial`/`failed`/`auth_required`/`not_found` em `output/<perfil>/status.json`; exit code 0/2/1. Uma falha em uma seção não derruba as outras (`process_section`). Lógica pura em `observability.py` (testada sem Selenium). Logs com `logging` (`LOG_FORMAT=json`, `LOG_LEVEL`); não volte a usar `print` nem `except:` sem tipo. `rate_limited` ainda não é detectado (ADR-0005). `linkedin.py` ainda usa `print`.
  - Contrato coleta→parsing (ADR-0010, `bundle.py`, stdlib): no fim do job (se autenticou e o perfil existe) os HTMLs coletados + `manifest.json` viram `raw/<perfil>/<collected_at>.zip` no storage (`infra.new_storage().put`; no `fs` padrão cai em `output/raw/...` e o modo `x` impede sobrescrever). Status por seção no manifest: `ok`/`redirected` (URL final ≠ pedida)/`timeout`/`not_collected`; seção vazia é decidida pelo parser, não pelo coletor. `file` só existe para ok/redirected (HTML parcial não entra no zip). `account_id` vem de `LINKEDIN_ACCOUNT_ID` (null se ausente). Schema em `schemas/manifest.v1.schema.json`, espelhado por `bundle.validate_manifest`; mudança incompatível incrementa `schema_version`.
  - Fila e storage plugáveis (ADR-0014, pacote `infra/`, stdlib; **não** chame de `platform`, sombreia a stdlib): portas `Queue`/`ObjectStorage` + fábricas `new_queue()`/`new_storage()` por env. `STORAGE_DRIVER` (padrão `fs`, `STORAGE_FS_ROOT` padrão `./output`) e `QUEUE_DRIVER` (sem ele não publica; `memory` só para testes). Após gravar o zip o coletor publica em `parse` `{schema_version,job_id,linkedin_url,zip_key}` (só IDs e chave, nunca conteúdo). Drivers `s3`/`rabbitmq` (e sqs/gcs/pubsub) **ainda não existem**: driver desconhecido dá `ValueError`. Handlers devem ser idempotentes (entrega ≥1 vez, sem ordem). Adapter novo = classe fina na pasta `infra/` + ramo na fábrica + teste de integração contra o emulador.
  - Contrato dos binários Go (`internal/parser/section.go`, `RunSection`): stdout = uma linha JSON `{section,status,items,duration_ms,error?}`, exit 0 para ok/empty, 3 para failed, 1 para erro de I/O. `empty` só vale se a página tem "Nothing to see for now"/"Nada para ver por enquanto"; o `linkedin-parser` nunca é `empty`.
  - No perfil só o "… more" da seção About é clicado (`click_more_buttons`): os "more" dos posts da atividade navegam para fora do perfil e já fizeram o `profile.html` sair como a página "Post". Se um clique navegar, o script volta para a URL do perfil.
  - Sem `time.sleep` fixos: as esperas usam `wait_until_stable()` (DOM sem mudar de tamanho por um intervalo). Ao mexer em scroll/expansão, manter esse padrão.
  - Mapeamento seção → URL → binário: perfil (`<url>`) → `linkedin-parser`; `details/experience/` → `experience-parser`; `details/education/` → `education-parser`; `details/languages/` → `language-parser`.
- **`linkedin.py`**: script independente (não compartilha código com `main.py`) que abre o menu "Mais ações" do perfil e baixa o PDF via "Salvar como PDF". Tem lista de seletores alternativos PT/EN para lidar com variações da UI.
- **Parsers Go**: vivem no repositório `linkedin-enrichment` (lado a lado com este, `../linkedin-enrichment`); detalhes de markup, fixtures e testes estão no `CLAUDE.md` de lá. Este repositório só os executa (contrato abaixo).

## Decisões de arquitetura

ADRs (todos com status Proposto) e o roteiro para virar serviço estão em `.adrs/` — ler `.adrs/melhorias.md` antes de mudanças estruturais.

## Repositórios (ADR-0013, ajustado)

Coletor (este) e `linkedin-enrichment` (parsers Go) são repositórios separados, ligados só por `PARSER_BIN_DIR` e pelo contrato do manifest (`schemas/manifest.v1.schema.json`, ainda validado só aqui por `bundle.validate_manifest`; o Go vai precisar de uma cópia com teste que as compare quando passar a ler o zip). Não há repositório `linkedin-enrichment-dev`: o compose de infra local fica em `dev/docker-compose.yml` e será revisto quando houver Dockerfiles dos serviços.

## Fluxo de trabalho

- Ao iniciar uma tarefa nova, crie antes um branch a partir do estado atual com nome `<tipo>/<descricao-curta-em-kebab-case>` (`feat/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`), como já usado no histórico (`fix/education-parser-new-layout`, `docs/architecture-adrs`). Uma tarefa por branch.
- Não faça commit nem push: deixe as alterações no working tree para o usuário revisar e commitar. Só commite se ele pedir.

## Cuidados

- Credenciais vêm só de `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` — nunca voltar a colocá-las no código. `linkedin_cookies.json` contém sessão ativa e, junto com `output/`, `resumes/` e os binários Go, está no `.gitignore`.
