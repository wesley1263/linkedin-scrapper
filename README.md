# LinkedIn Profile Scraper

Sistema automatizado para extração e parsing de dados de perfis do LinkedIn, incluindo informações de perfil, experiências profissionais, formação acadêmica e idiomas.

## Descrição

Este projeto combina web scraping (Python + Selenium) com parsers especializados (Go) para coletar e estruturar dados de perfis do LinkedIn em formato JSON. O sistema realiza scraping automatizado das páginas do LinkedIn e extrai informações estruturadas através de parsers dedicados.

## Funcionalidades

- **Extração de Perfil Completo**: Coleta dados básicos do perfil (nome, localização, headline, descrição, foto)
- **Experiências Profissionais**: Lista completa de cargos, empresas, períodos e descrições
- **Formação Acadêmica**: Instituições, cursos, períodos e descrições
- **Idiomas**: Proficiência em idiomas listados no perfil
- **Download de PDF**: Capacidade de baixar o perfil em formato PDF
- **Anti-detecção**: Configurações para evitar bloqueios do LinkedIn

## Estrutura do Projeto

```
linkedin/
├── main.py                   # Script principal de scraping
├── linkedin.py              # Script alternativo para download de PDF
├── linkedin-parser          # Parser de perfil (executável Go)
├── experience-parser        # Parser de experiências (executável Go)
├── education-parser         # Parser de formação acadêmica (executável Go)
├── language-parser          # Parser de idiomas (executável Go)
├── main.go                  # Código fonte do parser de perfil
├── experience_parser.go     # Código fonte do parser de experiências
├── education_parser.go      # Código fonte do parser de formação
├── language_parser.go       # Código fonte do parser de idiomas
├── Pipfile                  # Dependências Python
└── output/                  # Diretório de saída dos dados coletados
```

## Requisitos

### Python
- Python 3.12+
- Selenium
- Requests
- Chrome/Chromium WebDriver

### Go
- Go 1.16+ (para compilar os parsers)

## Instalação

### 1. Instalar dependências Python

```bash
# Usando pipenv
pipenv install

# Ou usando pip
pip install selenium requests pywebcopy
```

### 2. Compilar os parsers Go

```bash
cd enrichment
for p in linkedin-parser experience-parser education-parser language-parser; do
  go build -o bin/$p ./cmd/$p
done
```

### 3. Configurar ChromeDriver

Certifique-se de ter o ChromeDriver instalado e disponível no PATH do sistema.

```bash
# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver
```

## Configuração

### Credenciais do LinkedIn

As credenciais são lidas das variáveis de ambiente `LINKEDIN_EMAIL` e `LINKEDIN_PASSWORD` (obrigatórias em `main.py` e `linkedin.py`):

```bash
export LINKEDIN_EMAIL="seu-email@example.com"
export LINKEDIN_PASSWORD="sua-senha"
```

**ATENÇÃO**: Nunca compartilhe suas credenciais publicamente ou faça commit delas no repositório!

## Uso

### Scraping de Perfil Completo

```bash
python main.py https://www.linkedin.com/in/username/
```

Roda sem abrir o navegador (headless). Sem a URL como argumento, o script a solicita:

```
Insira o URL do perfil a ser analisado: https://www.linkedin.com/in/username/
```

### Download de PDF do Perfil

```bash
python linkedin.py https://www.linkedin.com/in/username/
```

### Uso dos Parsers Individualmente

```bash
# Parser de perfil
./enrichment/bin/linkedin-parser input.html output.json

# Parser de experiências
./enrichment/bin/experience-parser experience.html experiences.json

# Parser de formação
./enrichment/bin/education-parser education.html education.json

# Parser de idiomas
./enrichment/bin/language-parser languages.html languages.json
```

## Estrutura de Dados

### Perfil (profile.json)

```json
{
  "first_name": "Nome",
  "last_name": "Sobrenome",
  "email_addresses": ["email@example.com"],
  "avatar_url": "https://...",
  "address": {
    "name": "São Paulo, São Paulo, Brasil",
    "locality": "Brasil",
    "region": "São Paulo"
  },
  "phones": [],
  "linkedin_url": "https://www.linkedin.com/in/username",
  "description": "Descrição do perfil...",
  "headline": "Cargo atual",
  "company": "Empresa Atual",
  "university": "Universidade"
}
```

### Experiências (experience.json)

```json
[
  {
    "role_name": "Cargo",
    "start_date": "2023-01-01T00:00:00.000Z",
    "is_current": true,
    "end_date": null,
    "description": "Descrição das atividades...",
    "job_location": "São Paulo, Brasil",
    "company": {
      "name": "Nome da Empresa"
    },
    "linkedin_url": "https://www.linkedin.com/company/...",
    "avatar_url": "https://..."
  }
]
```

### Formação Acadêmica (education.json)

```json
[
  {
    "degree": "Bacharelado",
    "field_of_study": "Área de Estudo",
    "institution_name": "Nome da Instituição",
    "start_date": "2015-01-01T00:00:00.000Z",
    "end_date": "2019-12-31T23:59:59.000Z",
    "description": "Descrição...",
    "institution_url": "https://www.linkedin.com/school/...",
    "avatar_url": "https://..."
  }
]
```

### Idiomas (languages.json)

```json
[
  {
    "name": "Português",
    "proficiency": "Nativo ou bilíngue"
  },
  {
    "name": "Inglês",
    "proficiency": "Proficiência profissional completa"
  }
]
```

## Fluxo de Funcionamento

1. **Login Automático**: O script faz login no LinkedIn usando as credenciais fornecidas
2. **Navegação**: Acessa as diferentes seções do perfil (perfil principal, experiências, formação, idiomas)
3. **Carregamento de Conteúdo**: Executa scroll e clica em botões "Load more" para carregar todo o conteúdo
4. **Salvamento HTML**: Salva o HTML de cada seção
5. **Parsing**: Executa os parsers Go para extrair dados estruturados
6. **Geração JSON**: Cria arquivos JSON com os dados extraídos
7. **Limpeza**: Remove arquivos HTML temporários

## Diretório de Saída

Os dados extraídos são salvos em `output/<username>/`:

```
output/
└── username/
    ├── profile.json
    ├── experience.json
    ├── education.json
    ├── languages.json
    ├── status.json          # status do job e de cada seção
    └── failures/            # screenshot e HTML das seções que falharam
```

### Status e logs

Um perfil incompleto não passa mais por completo. Cada seção termina com um status de coleta (`collect_status`: `ok`/`failed`) e de parsing (`parse_status`):

- `ok`: itens extraídos;
- `empty`: o perfil não tem a seção ("Nothing to see for now");
- `failed`: nenhum item extraído sem a marca de seção vazia (possível mudança de layout) ou erro de coleta.

O job fica em `output/<username>/status.json` como `success`, `partial`, `failed`, `auth_required` ou `not_found`, e o `main.py` sai com código `0` (success), `2` (partial) ou `1` (demais). Cada parser imprime uma linha JSON de status no stdout (`{"section":"experience","status":"ok","items":4,...}`) e sai com `3` quando a seção falha.

Os logs saem legíveis no terminal; use `LOG_FORMAT=json` para uma linha JSON por evento (com `job_id`, `profile`, `section`, `duration_ms`) e `LOG_LEVEL=DEBUG` para mais detalhe.

## Recursos de Anti-detecção

O scraper implementa várias técnicas para evitar detecção:

- User-Agent personalizado
- Remoção de propriedades de automação do navegador
- Delays aleatórios entre ações
- Desativação de indicadores de automação do Selenium
- Comportamento de scroll simulando usuário real

## Limitações e Considerações

- **Taxa de Requisições**: O LinkedIn pode bloquear temporariamente contas que fazem muitas requisições em curto período
- **Mudanças na Interface**: O LinkedIn frequentemente atualiza sua interface, o que pode quebrar os seletores CSS/XPath
- **Termos de Serviço**: Verifique os termos de serviço do LinkedIn antes de usar este scraper
- **Dados Privados**: Respeite a privacidade dos usuários e use os dados de forma responsável
- **Login Manual**: Em caso de verificação de segurança, pode ser necessário login manual

## Problemas Comuns

### ChromeDriver não encontrado
```bash
# Verificar se o ChromeDriver está no PATH
which chromedriver
```

### Seletores não funcionando
- O LinkedIn pode ter mudado a estrutura HTML
- Verifique os logs para identificar elementos que não foram encontrados
- Atualize os seletores nos arquivos de parser

### Timeout durante o scraping
- Aumente o tempo de espera no código
- Verifique sua conexão com a internet
- O LinkedIn pode estar lento ou bloqueando requisições

## Desenvolvimento

### Adicionar novos campos ao parser

1. Identifique o padrão HTML no código fonte da página
2. Adicione a regex ou seletor apropriado no arquivo Go correspondente
3. Recompile o parser
4. Teste com diferentes perfis

### Debugging

O `main.py` roda em modo headless por padrão. Para ver o navegador (ou resolver uma verificação de segurança/2FA do LinkedIn):

```bash
python main.py --visible https://www.linkedin.com/in/username/
```

## Segurança

- **Nunca compartilhe suas credenciais do LinkedIn**
- **Use variáveis de ambiente para credenciais em produção**
- **Não faça commit de arquivos com credenciais**
- **Considere usar autenticação OAuth quando disponível**

## Exemplo de Uso com Variáveis de Ambiente

```python
import os

email = os.getenv('LINKEDIN_EMAIL')
password = os.getenv('LINKEDIN_PASSWORD')
```

```bash
export LINKEDIN_EMAIL="seu-email@example.com"
export LINKEDIN_PASSWORD="sua-senha"
python main.py
```

## Licença

Este projeto é fornecido como está, sem garantias. Use por sua conta e risco.

## Aviso Legal

Este projeto é apenas para fins educacionais. O scraping de dados do LinkedIn pode violar seus termos de serviço. Use com responsabilidade e em conformidade com as leis aplicáveis e os termos de serviço do LinkedIn.

## Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para:

- Reportar bugs
- Sugerir novos recursos
- Melhorar a documentação
- Enviar pull requests

## Autor

Desenvolvido por Weslei Souza

## Contato

Para dúvidas ou sugestões, abra uma issue no repositório.
