# ADR-0005: Gestão de sessão e limite de ritmo por conta

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

A sessão hoje depende de um perfil de Chrome em caminho fixo (`/home/weslei/.linkedin_chrome_profile`) e de um
`linkedin_cookies.json` na raiz do projeto. Problemas já observados: cookies antigos sobrescrevendo uma sessão válida,
login falhando por depender de classe CSS, e verificação de segurança (checkpoint) que no modo headless não tem como
ser resolvida. A conta usada é pessoal; se for restringida, o serviço para.

## Decisão

- **Sessão como recurso gerenciado:** cada conta tem seu diretório de perfil em volume dedicado e seus cookies em um
  armazenamento de segredos/DB (não em arquivo no repositório).
- **Verificação de saúde** da sessão antes de cada job (URL `/feed`, como já feito no `main.py`).
- **Checkpoint:** a conta é marcada como `auth_required`, sai do pool e dispara alerta para resolução manual
  (`--visible`); jobs vão para outro worker ou aguardam.
- **Limite de ritmo por conta:** um job por vez por conta, intervalo mínimo entre perfis e teto diário configuráveis.
- **Credenciais** só por variável de ambiente/segredo (já em vigor: `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD`).

## Consequências

- **+** Reduz a chance de restrição da conta e torna falhas de sessão visíveis em vez de silenciosas.
- **+** Pré-requisito para mais de um worker.
- **−** Throughput limitado pelo teto por conta; escalar exige mais contas — o que tem implicações discutidas no
  [ADR-0009](0009-conformidade-e-construir-vs-comprar.md).
- **−** Resolução de checkpoint continua manual.
