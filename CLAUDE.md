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

Os parsers Go vivem em `enrichment/` (módulo `linkedin-enrichment`, futuro repositório próprio — ver ADR-0001/0013): um `cmd/<parser>/main.go` por binário e helpers compartilhados em `internal/parser/`. Compile para `enrichment/bin/` (de onde `main.py` os executa; rodar a partir da raiz do repo):

```bash
cd enrichment && for p in linkedin-parser experience-parser education-parser language-parser; do go build -o bin/$p ./cmd/$p; done
```

Testes golden dos parsers (lint não configurado), rodando de `enrichment/`:

```bash
go test ./...                          # um teste: go test ./cmd/experience-parser -run Golden
go test ./... -update                  # regrava os *.golden.json (conferir o diff antes de commitar)
python3 tools/anonymize_fixture.py <output/user/secao.html> cmd/<parser>/testdata/<secao>.html --name "Nome Real" [--sub "real=>falso"]
```

O CI (`.github/workflows/enrichment-tests.yml`) roda `gofmt`, `go vet` e `go test ./...` em `enrichment/` a cada push/PR que o toque.

Fixtures em `cmd/<parser>/testdata/` são HTML **anonimizado** (o script recorta só a lista de itens e troca nomes, empresas, URLs e textos); nunca commitar HTML bruto de `output/`. Depois de gerar, conferir com `grep -i` por nomes reais — o script não pega tudo (ex.: títulos de mídia, locais com texto livre; use `--sub`). Para validar contra um HTML real, recompile e rode:

```bash
./enrichment/bin/experience-parser output/<username>/experience.html /tmp/out.json
```

## Arquitetura

- **`main.py`** (`LinkedInScraper`): reutiliza primeiro a sessão do perfil persistente do Chrome (`--user-data-dir`, por padrão `~/.linkedin_chrome_profile`; sobrescreva com `CHROME_PROFILE_DIR`), depois `linkedin_cookies.json`, e só faz login com usuário/senha (lidos do `.env` via `python-dotenv`) se ambos falharem. Login é detectado pela URL (`/feed`), não por classes CSS.
  - A página `/login` não tem mais `#username`/`#password`: os campos têm ids aleatórios e o formulário é renderizado **duas vezes, uma oculta** — por isso `login()` usa o primeiro campo *visível* e envia com Enter. Em falha, grava `output/login_error.{png,html}` com o que o driver viu.
  - Fluxo: abre as seções de detalhe (`DETAIL_SECTIONS`) em abas via `window.open` para carregarem em paralelo, carrega o perfil na aba principal e depois visita cada aba para expandir conteúdo (scroll / "Load more" / "more" do About) e gravar `output/<username>/<secao>.html`. Cada parser Go roda em background (`subprocess.Popen`) assim que o HTML é salvo; os binários precisam estar compilados em `enrichment/bin/` e o script rodar a partir da raiz.
  - No perfil só o "… more" da seção About é clicado (`click_more_buttons`): os "more" dos posts da atividade navegam para fora do perfil e já fizeram o `profile.html` sair como a página "Post". Se um clique navegar, o script volta para a URL do perfil.
  - Sem `time.sleep` fixos: as esperas usam `wait_until_stable()` (DOM sem mudar de tamanho por um intervalo). Ao mexer em scroll/expansão, manter esse padrão.
  - Mapeamento seção → URL → binário: perfil (`<url>`) → `linkedin-parser`; `details/experience/` → `experience-parser`; `details/education/` → `education-parser`; `details/languages/` → `language-parser`.
- **`linkedin.py`**: script independente (não compartilha código com `main.py`) que abre o menu "Mais ações" do perfil e baixa o PDF via "Salvar como PDF". Tem lista de seletores alternativos PT/EN para lidar com variações da UI.
- **Parsers Go**: extraem dados com regex/manipulação de string sobre o HTML bruto (sem parser de DOM), então são sensíveis a mudanças de markup do LinkedIn. Assumem textos em pt-BR (datas, níveis de proficiência, graus acadêmicos). Uso: `<parser> <input.html> [output.json]`.
  - O LinkedIn ignora `?locale=pt_BR` e serve as páginas em inglês ("May 2019 - Present"); parsers novos/ajustados devem aceitar inglês e pt-BR.
  - `enrichment/cmd/experience-parser/main.go` é o modelo para a marcação atual: cada item é um `div[componentkey^="entity-collection-item"]` (recortado por balanceamento de `<div>`), com os `<p>` em ordem cargo → "Empresa · Tipo" → datas → local; empresa com vários cargos vem como cabeçalho + um `<li>` por cargo. Descrição em `data-testid="expandable-text-box"`. HTMLs reais para teste ficam em `output/*/experience.html`. `enrichment/cmd/language-parser/main.go` segue o mesmo esquema (`<p>` = [idioma, nível]); os 5 níveis do LinkedIn mapeiam 1:1 para `BASIC`…`FLUENT`.
  - `enrichment/cmd/linkedin-parser/main.go` lê só a região `<main>` → fim da seção About (o resto tem atividade e outras pessoas): nome e slug vêm de `componentkey="ProfileVerificationTriggerRef-<slug>"` + `<h2>`; headline é o 1º `<p>` após o nome que não começa com "·"; localização é o `<p>` antes de `<p>·</p>` + link `contact-info`; empresa/universidade vêm dos ícones `company-accent`/`school-accent` (sem o sufixo "+ N more"); avatar é a maior resolução do `srcset`. `address.locality` guarda o **país** e `region` o estado (contrato do README). Email/telefone ficam no overlay "Contact info", que o scraper não abre, então saem vazios.
  - `enrichment/cmd/education-parser/main.go` também: `<p>` = [instituição, "Grau, Área"?, datas?]. Sem itens reconhecidos devolve `[]` (não há mais fallback com dados de exemplo). A ordem dos `case` em `normalizeDegreeLevel` importa ("Pós-graduação" contém "graduação").

## Decisões de arquitetura

ADRs (todos com status Proposto) e o roteiro para virar serviço estão em `.adrs/` — ler `.adrs/melhorias.md` antes de mudanças estruturais.

## Fluxo de trabalho

- Ao iniciar uma tarefa nova, crie antes um branch a partir do estado atual com nome `<tipo>/<descricao-curta-em-kebab-case>` (`feat/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`), como já usado no histórico (`fix/education-parser-new-layout`, `docs/architecture-adrs`). Uma tarefa por branch.
- Não faça commit nem push: deixe as alterações no working tree para o usuário revisar e commitar. Só commite se ele pedir.

## Cuidados

- Credenciais vêm só de `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` — nunca voltar a colocá-las no código. `linkedin_cookies.json` contém sessão ativa e, junto com `output/`, `resumes/` e os binários Go, está no `.gitignore`.
