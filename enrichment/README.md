# linkedin-enrichment

Parsers Go que transformam o HTML de uma seção do perfil do LinkedIn em JSON (ADR-0001/0013).

```bash
for p in linkedin-parser experience-parser education-parser language-parser; do go build -o bin/$p ./cmd/$p; done
go test ./...                 # golden tests; `-update` regrava os *.golden.json
./bin/experience-parser input.html [output.json]
```

Contrato: stdout = uma linha JSON `{section,status,items,duration_ms,error?}`; exit 0 ok/empty, 3 failed, 1 erro de I/O.
Fixtures em `cmd/*/testdata/` são anonimizados (`tools/anonymize_fixture.py`); nunca commitar HTML bruto.
