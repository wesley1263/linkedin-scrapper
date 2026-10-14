# ADR-0006: Status explícito por seção e observabilidade

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

O `main.py` usa `except:` genéricos e `print`; os parsers Go escrevem no stdout e seus códigos de saída são ignorados.
Na prática, um perfil incompleto é indistinguível de um completo. A quebra dos parsers por mudança de layout só foi
percebida porque alguém notou experiências faltando.

## Decisão

- **Status por job:** `success`, `partial`, `not_found`, `auth_required`, `rate_limited`, `failed`.
- **Status por seção:** `ok`, `empty` (o perfil não tem — ex.: "Nothing to see for now"), `failed` (esperava itens e
  não extraiu nenhum, ou erro de parsing).
- **Logging estruturado** (JSON) com `job_id`, perfil, seção e duração, no lugar de `print`; sem `except:` genérico.
- **Artefatos de falha:** HTML e screenshot da página salvos quando uma seção falha.
- **Métricas de qualidade** por seção: taxa de `failed`, média de itens extraídos, taxa de campos vazios. Um salto
  repentino indica **mudança de layout** e dispara alerta.

## Consequências

- **+** Falhas aparecem para o cliente e para a operação, em vez de virarem dados incompletos no cadastro.
- **+** Mudanças de layout são detectadas em horas, não quando alguém reclama.
- **−** Exige stack de logs/métricas (pode começar simples: logs JSON + uma consulta periódica no Postgres).
