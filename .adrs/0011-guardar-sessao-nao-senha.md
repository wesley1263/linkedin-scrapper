# ADR-0011: Guardar a sessão do LinkedIn, não a senha

- **Status:** Proposto
- **Data:** 2026-10-15

## Contexto

Cada usuário conecta a própria conta do LinkedIn ([ADR-0005](0005-gestao-de-sessao-e-limite-de-ritmo.md)). A primeira
ideia foi guardar login e senha criptografados e descriptografá-los para abrir sessões novas. Problemas:

1. **A senha sozinha não garante login automático.** Um login com usuário e senha vindo de um servidor (IP de
   datacenter, navegador novo) é exatamente o que dispara checkpoint, 2FA ou código por e-mail. O serviço teria a
   senha e mesmo assim precisaria do usuário.
2. **O estrago de um vazamento é muito maior.** A senha dá acesso total e permanente à conta, e costuma ser reutilizada
   em outros serviços. Uma sessão vazada é revogável: o usuário sai de todas as sessões no LinkedIn.
3. **A sessão dura bastante.** O cookie de sessão (`li_at`) observado no projeto vale cerca de 1 ano.

## Decisão

- **Nunca persistir a senha.** Ela é digitada pelo usuário numa conexão interativa
  ([ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)), existe só em memória durante o login e é descartada.
- **Persistir apenas a sessão** (cookies e, se necessário, o perfil do navegador), tratada com o mesmo rigor de uma
  senha, porque dá acesso à conta enquanto for válida:
  - **Envelope encryption com KMS** (AWS KMS, GCP KMS ou HashiCorp Vault Transit): cada sessão é cifrada com uma chave
    de dados própria; a chave de dados é cifrada por uma chave mestra que nunca sai do KMS. O banco só guarda dados
    cifrados.
  - **Só o coletor pode descriptografar.** A API e o parser não têm permissão no KMS. A sessão é aberta na memória do
    worker no momento de iniciar o navegador.
  - **Nada em log:** sessão, cookies e senha estão numa lista explícita de campos proibidos em log e em mensagens de fila.
  - **Auditoria:** toda descriptografia registra conta, job e horário (o KMS já oferece isso).
  - **Revogação:** o usuário pode desconectar a conta; o serviço apaga a sessão cifrada e a chave de dados. Isso também
    atende o pedido de exclusão da LGPD.
  - **Isolamento:** sessões numa tabela ou serviço separado, com acesso restrito, fora do banco de perfis.
- Na coleta por extensão de navegador, **nenhuma sessão sai da máquina do usuário** e nada disso se aplica.

## Consequências

- **+** Nenhuma senha de usuário sob guarda do serviço; superfície de ataque e responsabilidade menores.
- **+** 2FA e demais verificações do LinkedIn funcionam, porque o usuário as resolve na conexão.
- **−** Quando a sessão expira ou é invalidada, o usuário precisa reconectar; não há re-login automático.
- **−** Dependência de um KMS e da gestão de permissões em torno dele.
