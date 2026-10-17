package main

import (
	"os"
	"testing"

	"linkedin-enrichment/internal/golden"
)

func TestEducationGolden(t *testing.T) {
	html, err := os.ReadFile("testdata/education.html")
	if err != nil {
		t.Fatal(err)
	}
	golden.Check(t, "testdata/education.golden.json", NewEducationParser(string(html)).extractEducationData())
}

func TestEducationEmpty(t *testing.T) {
	if got := NewEducationParser(`<p>Nothing to see for now</p>`).extractEducationData(); len(got) != 0 {
		t.Errorf("seção vazia deveria devolver 0 formações, obteve %d", len(got))
	}
}

func TestNormalizeDegreeLevel(t *testing.T) {
	cases := map[string]DegreeLevel{
		"Graduação":     BACHELOR,
		"Bacharelado":   BACHELOR,
		"Pós-graduação": POST_BACHELOR,
		"MBA":           MBA,
		"Mestrado":      MASTER,
		"Doutorado":     DOCTORATE,
	}
	for in, want := range cases {
		if got := normalizeDegreeLevel(in); got != want {
			t.Errorf("normalizeDegreeLevel(%q) = %s, esperado %s", in, got, want)
		}
	}
}
