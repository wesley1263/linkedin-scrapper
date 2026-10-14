# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão geral

Scraper de perfis do LinkedIn em duas camadas: **Python + Selenium** navega e salva o HTML de cada seção do perfil; **parsers em Go** (um binário por seção) leem esse HTML e geram JSON. Documentação de uso e schemas dos JSON de saída estão no `README.md`.

## Comandos

```bash
pipenv install                        # dependências Python (Python 3.12)
export LINKEDIN_EMAIL=... LINKEDIN_PASSWORD=...   # obrigatórias nos dois scripts
pipenv run python main.py             # scraping completo; pede a URL do perfil via input()
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

- **`main.py`** (`LinkedInScraper`): reutiliza sessão via `linkedin_cookies.json` + perfil persistente do Chrome (`--user-data-dir` com caminho absoluto fixo em `/home/weslei/...`); só faz login com usuário/senha se a sessão expirou. Para cada seção visita a URL com `?locale=pt_BR`, expande conteúdo (scroll / "Load more" / "more"), grava o HTML em `output/<username>/<secao>.html` e chama o binário Go correspondente via `os.system`, a partir do diretório atual — os binários precisam estar compilados na raiz do repo.
  - Mapeamento seção → URL → binário: perfil (`<url>`) → `linkedin-parser`; `details/experience/` → `experience-parser`; `details/education/` → `education-parser`; `details/languages/` → `language-parser`.
  - A URL do perfil precisa terminar com `/`, pois os paths de detalhe são concatenados diretamente.
- **`linkedin.py`**: script independente (não compartilha código com `main.py`) que abre o menu "Mais ações" do perfil e baixa o PDF via "Salvar como PDF". Tem lista de seletores alternativos PT/EN para lidar com variações da UI.
- **Parsers Go**: extraem dados com regex/manipulação de string sobre o HTML bruto (sem parser de DOM), então são sensíveis a mudanças de markup do LinkedIn. Assumem textos em pt-BR (datas, níveis de proficiência, graus acadêmicos). Uso: `<parser> <input.html> [output.json]`.
  - Atenção: `education_parser.go` cai em `createSampleEducationData()` (dados fictícios) quando não encontra nada estruturado — saída "válida" pode ser placeholder.

## Cuidados

- Credenciais vêm só de `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` — nunca voltar a colocá-las no código. `linkedin_cookies.json` contém sessão ativa e, junto com `output/`, `resumes/` e os binários Go, está no `.gitignore`.
