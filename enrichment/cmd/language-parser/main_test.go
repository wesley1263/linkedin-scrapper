package main

import (
	"os"
	"testing"

	"linkedin-enrichment/internal/golden"
)

func TestLanguagesGolden(t *testing.T) {
	html, err := os.ReadFile("testdata/languages.html")
	if err != nil {
		t.Fatal(err)
	}
	golden.Check(t, "testdata/languages.golden.json", NewLanguageParser(string(html)).extractLanguageData())
}

func TestLanguagesEmpty(t *testing.T) {
	if got := NewLanguageParser(`<p>Nothing to see for now</p>`).extractLanguageData(); len(got) != 0 {
		t.Errorf("seção vazia deveria devolver 0 idiomas, obteve %d", len(got))
	}
}
