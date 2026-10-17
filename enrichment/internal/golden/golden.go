// Package golden compara a saída de um parser com um arquivo .golden.json.
// Rode os testes com -update para regravar os arquivos esperados.
package golden

import (
	"encoding/json"
	"flag"
	"os"
	"testing"
)

var update = flag.Bool("update", false, "regrava os arquivos .golden.json")

// Check serializa got como JSON indentado e compara com o conteúdo de path
func Check(t *testing.T, path string, got any) {
	t.Helper()
	data, err := json.MarshalIndent(got, "", "  ")
	if err != nil {
		t.Fatalf("erro ao gerar JSON: %v", err)
	}
	data = append(data, '\n')

	if *update {
		if err := os.WriteFile(path, data, 0o644); err != nil {
			t.Fatalf("erro ao gravar %s: %v", path, err)
		}
		return
	}

	want, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("erro ao ler %s (rode com -update para criar): %v", path, err)
	}
	if string(want) != string(data) {
		t.Errorf("saída difere de %s (rode com -update para regravar após conferir o diff)\n--- obtido ---\n%s", path, data)
	}
}
