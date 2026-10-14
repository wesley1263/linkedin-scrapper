# Melhorias: do script ao serviço de enriquecimento

_Data: 2026-10-14_

## Resumo

Para enriquecer um cadastro sob demanda, o fluxo atual já funciona: cerca de 23s por perfil, com experiências, formação
e idiomas extraídos corretamente após as correções de parser de outubro/2026. O que separa o projeto de um serviço não
é o scraping em si, mas o que está em volta: contrato de saída, isolamento, armazenamento, observabilidade e gestão de
risco (conta, LGPD, termos de uso).

## Diagnóstico da arquitetura atual

| Problema | Consequência |
|---|---|
| Python (Selenium) e Go (parsers) conversando por arquivo e `subprocess` | Dois runtimes no deploy, binários compilados à mão; erros do Go não chegam ao Python (um `panic` no parser de perfil passou despercebido). |
| Parsers com regex sobre HTML bruto | Frágeis a qualquer mudança de markup; em outubro/2026 três dos quatro parsers quebraram com o layout novo do LinkedIn. |
| Código duplicado entre parsers (datas, limpeza de texto, recorte de itens), sem `go.mod` e sem testes | Cada correção precisa ser repetida em vários arquivos; regressões só aparecem em produção. |
| `except:` genéricos e `print` no `main.py` | Falhas silenciosas: perfil incompleto é indistinguível de perfil completo. |
| Caminhos fixos (`/home/weslei/...`, `./linkedin-parser`) e um único perfil de Chrome | Não roda em outra máquina, em container nem com mais de um worker. |
| `linkedin.py` duplica login e setup do driver | Duas implementações para manter. |
| Sem contrato de saída | O JSON pode mudar ou vir vazio sem nenhum erro (ex.: `profile.json` hoje sai quase vazio). |
| Conta pessoal do LinkedIn como dependência | Restrição da conta derruba o serviço; credencial já vazou no histórico do git (commit `f0c6bef`). |

## Arquitetura proposta

```
Cliente (cadastro) ──POST /enrichments {linkedin_url}──▶ API (FastAPI)
                    ◀── 202 {job_id} · GET /enrichments/{id} · webhook
                                   │
                              Fila (Redis/RQ ou SQS)
                                   │
                 Worker(s): 1 navegador + 1 sessão por worker
                   ├─ coleta → HTML bruto no storage (S3/disco)
                   ├─ parse (mesmo processo) → JSON validado (pydantic)
                   └─ Postgres: perfil, seções, status, parser_version
```

Decisões detalhadas nos ADRs:

- [ADR-0001](0001-unificar-coleta-e-parsing-em-python.md) — um único runtime Python (Playwright + selectolax)
- [ADR-0002](0002-armazenar-html-bruto-e-versionar-parsers.md) — guardar HTML bruto e versionar parsers
- [ADR-0003](0003-processamento-assincrono-api-fila-workers.md) — API assíncrona com fila e workers
- [ADR-0004](0004-testes-de-parser-com-fixtures-reais.md) — testes de parser com fixtures reais anonimizadas
- [ADR-0005](0005-gestao-de-sessao-e-limite-de-ritmo.md) — sessão como recurso gerenciado e limite de ritmo
- [ADR-0006](0006-status-explicito-e-observabilidade.md) — status por seção e detecção de mudança de layout
- [ADR-0007](0007-cache-com-ttl.md) — cache com TTL
- [ADR-0008](0008-configuracao-por-ambiente-e-container.md) — configuração por ambiente e container
- [ADR-0009](0009-conformidade-e-construir-vs-comprar.md) — LGPD, termos de uso e construir vs. comprar

## Próximos passos (em ordem)

1. **Testes de parser com fixtures** dos HTMLs de `output/`, anonimizados ([ADR-0004](0004-testes-de-parser-com-fixtures-reais.md)).
   ~meio dia. É a rede de segurança para todas as outras mudanças.
2. **Atualizar o parser de perfil (`main.go`)** — único ainda quebrado; endereço, descrição e `linkedin_url` saem vazios,
   e são justamente os campos centrais para o cadastro. ~2h.
3. **Tornar falhas visíveis** — trocar `except:` e `print` por logging e emitir status por seção
   ([ADR-0006](0006-status-explicito-e-observabilidade.md)). ~2h.
4. **Unificar em um pacote Python e expor API + fila + worker** ([ADR-0001](0001-unificar-coleta-e-parsing-em-python.md),
   [ADR-0003](0003-processamento-assincrono-api-fila-workers.md)). Alguns dias; só faz sentido depois de 1–3.

Fora da ordem, mas urgente: **trocar a senha da conta do LinkedIn** (continua no histórico do git).

## Roteiro por fase

**Fase 0 — Higiene (1–2 dias):** passos 1 a 3 acima, mais remoção de caminhos fixos e da dependência do diretório atual.

**Fase 1 — Serviço para enriquecer cadastro:** pacote Python único com testes, API + fila + 1 worker, Postgres + storage
de HTML bruto, cache com TTL, imagem Docker. Atende o caso "enriquecer o cadastro quando entra um candidato".

**Fase 2 — Escala / enriquecimento em massa:** pool de workers e contas com limite de ritmo, reprocessamento por versão
de parser, alertas de mudança de layout. Antes de investir aqui, fechar a questão jurídica e a comparação com
fornecedor ([ADR-0009](0009-conformidade-e-construir-vs-comprar.md)).
