# ADR-0009: Conformidade (LGPD e termos de uso) e construir vs. comprar

- **Status:** Proposto
- **Data:** 2026-10-14

## Contexto

- O serviço trata **dados pessoais de terceiros** (histórico profissional, formação, foto, localização). Hoje esses
  dados ficam em `output/` numa máquina local, sem prazo de retenção nem processo de exclusão.
- A coleta usa uma conta autenticada e automação de navegador, o que **contraria os termos de uso do LinkedIn**. Em
  baixo volume (enriquecer um cadastro), o risco principal é a restrição da conta. Em volume alto, escalar exige várias
  contas, o que torna a violação explícita e aumenta o risco jurídico.
- Credencial da conta já vazou no histórico do git (commit `f0c6bef`).
- Com o modelo de conta do próprio usuário ([ADR-0005](0005-gestao-de-sessao-e-limite-de-ritmo.md),
  [ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)), o serviço passa a automatizar contas de terceiros e a guardar
  sessões deles. Os termos do LinkedIn proíbem compartilhar acesso à conta e o acesso automatizado; o risco de
  restrição recai sobre a conta de cada usuário.
- Os dados de exemplo do repositório (`education.json`) apontam para `assets.enrichlayer.com`, indicando que um
  fornecedor de enriquecimento já foi usado.

## Decisão

1. **Antes da Fase 2 (enriquecimento em massa) e antes de oferecer a API como SaaS, obter parecer jurídico** sobre o
   uso pretendido.
2. **LGPD desde a Fase 1:**
   - base legal documentada (ex.: legítimo interesse para recrutamento);
   - minimização: coletar só os campos usados no cadastro;
   - retenção definida para HTML bruto e resultados, com expurgo automático;
   - processo para atender pedido de exclusão do titular (remover HTML, JSON e cache);
   - termo de consentimento explícito na conexão da conta, informando que o acesso será automatizado com a conta do
     usuário e quais riscos isso traz para ela.
3. **Avaliar construir vs. comprar** antes de investir em escala: comparar custo por perfil de um fornecedor de
   enriquecimento com o custo de manter contas, sessões e parsers (que quebram a cada mudança de layout).
4. **Imediato:** trocar a senha da conta e avaliar remover a credencial do histórico (`git filter-repo` + force push).

## Consequências

- **+** Reduz exposição jurídica e de reputação; decisão de escala passa a ser informada por custo real.
- **−** Pode concluir que a Fase 2 deve ser atendida por fornecedor, limitando este projeto ao enriquecimento sob
  demanda.
