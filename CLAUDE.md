# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão geral

Scraper de perfis do LinkedIn em duas camadas: **Python + Selenium** navega e salva o HTML de cada seção do perfil; **parsers em Go** (um binário por seção) leem esse HTML e geram JSON. Documentação de uso e schemas dos JSON de saída estão no `README.md`.

## Comandos

```bash
pipenv install                        # dependências Python (Python 3.12)
export LINKEDIN_EMAIL=... LINKEDIN_PASSWORD=...   # obrigatórias nos dois scripts
pipenv run python main.py [<url>]     # scraping completo, headless; sem <url> pede via input()
pipenv run python main.py --visible   # abre o Chrome visível (necessário p/ resolver checkpoint/2FA)
pipenv run python linkedin.py <url>   # baixa o PDF do perfil para ./resumes/
```

Os parsers Go **não têm `go.mod`** e todos os arquivos são `package main` com funções duplicadas (`cleanHTML`, `processHTMLFile`, `saveToJSON`, …). Por isso cada um precisa ser compilado isoladamente, passando o arquivo — `go build ./...` ou `go build .` falham:

```bash
go build -o linkedin-parser   main.go
go build -o experience-parser experience_parser.go
go build -o education-parser  education_parser.go
go build -o language-parser   language_parser.go
```

Não há testes nem lint configurados. Para validar mudança em um parser, recompile e rode contra um HTML já salvo em `output/<username>/`:

```bash
./experience-parser output/<username>/experience.html /tmp/out.json
```

## Arquitetura

- **`main.py`** (`LinkedInScraper`): reutiliza primeiro a sessão do perfil persistente do Chrome (`--user-data-dir` com caminho absoluto fixo em `/home/weslei/...`), depois `linkedin_cookies.json`, e só faz login com usuário/senha se ambos falharem. Login é detectado pela URL (`/feed`), não por classes CSS.
  - Fluxo: abre as seções de detalhe (`DETAIL_SECTIONS`) em abas via `window.open` para carregarem em paralelo, carrega o perfil na aba principal e depois visita cada aba para expandir conteúdo (scroll / "Load more" / "more") e gravar `output/<username>/<secao>.html`. Cada parser Go roda em background (`subprocess.Popen`) assim que o HTML é salvo; os binários precisam estar compilados na raiz do repo e o script rodar a partir dela.
  - Sem `time.sleep` fixos: as esperas usam `wait_until_stable()` (DOM sem mudar de tamanho por um intervalo). Ao mexer em scroll/expansão, manter esse padrão.
  - Mapeamento seção → URL → binário: perfil (`<url>`) → `linkedin-parser`; `details/experience/` → `experience-parser`; `details/education/` → `education-parser`; `details/languages/` → `language-parser`.
- **`linkedin.py`**: script independente (não compartilha código com `main.py`) que abre o menu "Mais ações" do perfil e baixa o PDF via "Salvar como PDF". Tem lista de seletores alternativos PT/EN para lidar com variações da UI.
- **Parsers Go**: extraem dados com regex/manipulação de string sobre o HTML bruto (sem parser de DOM), então são sensíveis a mudanças de markup do LinkedIn. Assumem textos em pt-BR (datas, níveis de proficiência, graus acadêmicos). Uso: `<parser> <input.html> [output.json]`.
  - O LinkedIn ignora `?locale=pt_BR` e serve as páginas em inglês ("May 2019 - Present"); parsers novos/ajustados devem aceitar inglês e pt-BR.
  - `experience_parser.go` é o modelo para a marcação atual: cada item é um `div[componentkey^="entity-collection-item"]` (recortado por balanceamento de `<div>`), com os `<p>` em ordem cargo → "Empresa · Tipo" → datas → local; empresa com vários cargos vem como cabeçalho + um `<li>` por cargo. Descrição em `data-testid="expandable-text-box"`. HTMLs reais para teste ficam em `output/*/experience.html`. `language_parser.go` segue o mesmo esquema (`<p>` = [idioma, nível]); os 5 níveis do LinkedIn mapeiam 1:1 para `BASIC`…`FLUENT`.
  - `education_parser.go` também: `<p>` = [instituição, "Grau, Área"?, datas?]. Sem itens reconhecidos devolve `[]` (não há mais fallback com dados de exemplo). A ordem dos `case` em `normalizeDegreeLevel` importa ("Pós-graduação" contém "graduação").

## Cuidados

- Credenciais vêm só de `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` — nunca voltar a colocá-las no código. `linkedin_cookies.json` contém sessão ativa e, junto com `output/`, `resumes/` e os binários Go, está no `.gitignore`.
