# ADR-0005: Sessões por conta de usuário e limite de ritmo

- **Status:** Proposto
- **Data:** 2026-10-15
- **Revisão:** a versão anterior pressupunha contas do próprio serviço; agora cada solicitante usa a própria conta.

## Contexto

Hoje a coleta usa uma conta pessoal fixa, com credenciais em variáveis de ambiente, um perfil de Chrome em caminho
fixo e um `linkedin_cookies.json` na raiz do projeto. Escalar esse modelo exigiria criar contas "fantasmas", o que
viola diretamente os termos do LinkedIn, tende a ser bloqueado rápido e concentra o risco numa conta robótica que,
quando cai, derruba o serviço.

## Decisão

- **Não há contas do serviço.** Cada solicitante conecta a **própria conta do LinkedIn**, e os jobs dele são coletados
  com a sessão dele. As credenciais em variáveis de ambiente ficam só para desenvolvimento local.
- **Guardamos a sessão, não a senha** ([ADR-0011](0011-guardar-sessao-nao-senha.md)). A conexão é interativa, para que
  o usuário resolva ele mesmo as etapas de segurança do LinkedIn (2FA, código por e-mail)
  ([ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)).
- **Uma sessão, um coletor por vez:** os jobs de uma conta são processados em série (fila por conta ou lock). A mesma
  conta em uso paralelo é um sinal forte de automação.
- **Limite de ritmo por conta**, próximo do uso humano: intervalo mínimo entre perfis e teto diário configuráveis.
  Isso também vira regra de produto: cada usuário enriquece no volume do seu uso normal.
- **IP de saída estável por conta**: uma sessão que aparece de IPs diferentes a cada uso tende a ser derrubada.
- **Saúde da sessão** verificada antes de cada job (URL `/feed`, como no `main.py`). Sessão expirada ou checkpoint:
  a conta vai para `auth_required`, os jobs dela ficam aguardando e o usuário é notificado para reconectar.

## Consequências

- **+** Não existe ponto único de falha numa conta robótica; o volume se distribui pelas contas dos usuários.
- **+** Elimina o trabalho de criar e manter contas fantasmas.
- **−** O throughput de cada usuário é limitado pelo ritmo da própria conta.
- **−** O risco de restrição passa para a conta de cada usuário, o que exige consentimento explícito
  ([ADR-0009](0009-conformidade-e-construir-vs-comprar.md)).
- **−** Reconectar a conta é uma ação manual do usuário (quando a sessão expira, em até ~1 ano, ou quando o LinkedIn a invalida antes).
