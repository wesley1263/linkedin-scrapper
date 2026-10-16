# ADR-0010: Contrato entre coleta e parsing (zip + manifest)

- **Status:** Proposto
- **Data:** 2026-10-15

## Contexto

Com coleta e parsing separados ([ADR-0001](0001-separar-coleta-python-e-parsing-go.md)), o zip de HTML bruto passa a
ser o contrato entre as duas camadas, que podem ser produzidas por coletores diferentes (servidor ou extensão de
navegador, [ADR-0012](0012-dois-modos-de-conexao-e-coleta.md)). Sem metadados, o parser teria de adivinhar se uma
seção falta porque o perfil não a tem, porque a coleta falhou ou porque a página redirecionou.

## Decisão

Cada coleta gera **um zip imutável** com os HTMLs e um `manifest.json` na raiz:

```json
{
  "schema_version": 1,
  "job_id": "…",
  "account_id": "…",
  "linkedin_url": "https://www.linkedin.com/in/fulano/",
  "collected_at": "2026-10-15T14:02:11Z",
  "collector": {"type": "server", "version": "1.4.0"},
  "sections": {
    "profile":    {"file": "profile.html",    "status": "ok"},
    "experience": {"file": "experience.html", "status": "ok"},
    "education":  {"file": "education.html",  "status": "ok"},
    "languages":  {"file": "languages.html",  "status": "redirected", "final_url": "…"}
  }
}
```

- `collector.type`: `server` (coletor Python) ou `extension` (extensão de navegador).
- `sections.*.status`: `ok`, `redirected`, `timeout`, `not_collected`. Decidir se a seção está vazia ("Nothing to see
  for now") é papel do parser, não do coletor.
- Chave no storage: `raw/<perfil-normalizado>/<collected_at>.zip`. Zips nunca são sobrescritos.
- O manifest **não** contém sessão, cookies nem qualquer credencial.
- Mudança incompatível no formato incrementa `schema_version`; o parser suporta as versões em uso.

## Consequências

- **+** O parser não depende de como a coleta foi feita; os dois tipos de coletor produzem o mesmo artefato.
- **+** Falhas de coleta ficam explícitas e auditáveis.
- **−** O formato precisa ser versionado e validado dos dois lados (schema JSON compartilhado).
