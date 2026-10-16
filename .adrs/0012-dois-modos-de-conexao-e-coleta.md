# ADR-0012: Dois modos de conexão e coleta (interface própria e API)

- **Status:** Proposto
- **Data:** 2026-10-15
- **Sequência:** os dois modos ficam para depois da primeira versão ([ADR-0015](0015-escopo-da-primeira-versao.md)), que usa login interativo com o coletor em modo visível.

## Contexto

O produto terá dois tipos de consumidor:

1. **Interface própria (front-end do produto):** o usuário entra no nosso sistema e enriquece candidatos ali, sem
   integrar nada.
2. **API (SaaS):** outro sistema chama o serviço para enriquecer candidatos; quem conecta a conta do LinkedIn é o
   usuário final desse sistema.

Nos dois casos a coleta usa a conta do próprio usuário ([ADR-0005](0005-gestao-de-sessao-e-limite-de-ritmo.md)) e só a
sessão é guardada ([ADR-0011](0011-guardar-sessao-nao-senha.md)).

**Restrição técnica importante:** uma página HTML rodando no front-end do cliente **não consegue capturar a sessão do
LinkedIn** do navegador do usuário. A política de mesma origem impede ler cookies de `linkedin.com` a partir de outro
domínio, e o cookie de sessão é `HttpOnly`. Só uma extensão de navegador tem esse acesso. Além disso, se a página de
login rodasse no código do cliente, o cliente teria acesso à senha do usuário.

## Decisão

### Modo A — Interface própria + extensão de navegador

- O usuário instala a extensão do produto.
- Ao enriquecer um candidato, a extensão abre o perfil **no navegador do próprio usuário**, salva os HTMLs, monta o
  zip com manifest (`collector.type = "extension"`, [ADR-0010](0010-contrato-zip-e-manifest.md)) e envia ao storage.
- Daí em diante o pipeline é o mesmo: fila `parse`, parser Go, banco.
- **Nenhuma sessão ou senha sai da máquina do usuário**, e o acesso vem do IP e do navegador reais dele, o padrão
  menos suspeito possível.
- Limite: só coleta com o navegador do usuário aberto; não serve para lotes.
- Usuários da interface que não queiram instalar a extensão podem usar o fluxo de conexão do Modo B.

### Modo B — API (SaaS) + conexão hospedada (Connect)

Padrão de "link hospedado", semelhante ao usado por agregadores bancários:

1. O **back-end do cliente** chama `POST /connect-sessions {external_user_id}` com sua API key e recebe uma URL de
   conexão de uso único e curta duração.
2. O **front-end do cliente** abre essa URL em popup, redirecionamento ou iframe. A página é **nossa, hospedada no
   nosso domínio**; o cliente só a exibe e nunca vê a senha.
3. Na página, o usuário vê o termo de consentimento e faz login no LinkedIn por um **navegador remoto**: um Chrome
   rodando no nosso servidor, com a tela transmitida para a página. Ele digita a senha e resolve 2FA ou código ali.
   Como o login acontece no mesmo ambiente (IP e navegador) que depois fará a coleta, a sessão fica estável.
4. Concluído o login, guardamos só a sessão cifrada e notificamos o cliente (webhook `account.connected` e
   redirecionamento) com um `account_id`.
5. O cliente usa esse `account_id` em `POST /enrichments` ([ADR-0003](0003-processamento-assincrono-api-fila-workers.md));
   a coleta é feita pelo coletor do servidor com a sessão daquele usuário.
6. Sessão expirada ou checkpoint: webhook `account.reconnect_required`; o cliente gera uma nova URL de conexão para o
   mesmo `account_id`.

### Comum aos dois modos

- **Multi-tenant:** cliente (tenant) → usuários/contas conectadas → jobs. Uma API key só enxerga as contas e os
  resultados do próprio tenant.
- O resultado do parsing é o mesmo nos dois modos; o modo de coleta fica registrado no manifest.

## Consequências

- **+** Atende os dois produtos (interface e API) com um único pipeline de parsing e armazenamento.
- **+** Em nenhum dos modos o serviço ou o cliente guardam a senha do usuário.
- **+** O Modo A elimina o problema de credenciais em vez de protegê-lo.
- **−** Duas formas de coleta para manter: extensão (Chrome Web Store, atualização de versões) e coletor de servidor.
- **−** O navegador remoto do Modo B é a peça mais complexa: streaming de tela, isolamento por sessão e custo de
  infraestrutura por conexão ativa.
- **−** Como SaaS, o serviço automatiza contas de usuários de terceiros, o que eleva o risco jurídico e de termos de
  uso; parecer jurídico obrigatório antes do lançamento ([ADR-0009](0009-conformidade-e-construir-vs-comprar.md)).
  Existem fornecedores que oferecem esse modelo de conexão hospedada para LinkedIn, o que entra na avaliação de
  construir vs. comprar.
