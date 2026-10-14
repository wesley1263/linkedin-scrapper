# ADR-0007: Cache de perfis com TTL

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

Cada coleta custa ~25s, consome cota da conta do LinkedIn e aumenta o risco de restrição
([ADR-0005](0005-gestao-de-sessao-e-limite-de-ritmo.md)). Para enriquecimento de cadastro, perfis mudam pouco em
semanas, e o mesmo candidato pode ser solicitado mais de uma vez.

## Decisão

- Antes de enfileirar, verificar se o perfil (URL normalizada) foi coletado com sucesso há menos de **N dias**
  (configurável; sugestão inicial: 30). Se sim, devolver o resultado armazenado.
- Parâmetro `force_refresh` na API para ignorar o cache quando necessário.
- O cache respeita a política de retenção do [ADR-0009](0009-conformidade-e-construir-vs-comprar.md).

## Consequências

- **+** Menos acessos ao LinkedIn, resposta imediata para perfis recentes.
- **−** Dados podem estar até N dias desatualizados.
