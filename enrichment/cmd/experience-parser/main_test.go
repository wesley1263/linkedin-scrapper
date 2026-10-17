package main

import (
	"os"
	"testing"

	"linkedin-enrichment/internal/golden"
)

func TestParseExperiencesGolden(t *testing.T) {
	html, err := os.ReadFile("testdata/experience.html")
	if err != nil {
		t.Fatal(err)
	}
	golden.Check(t, "testdata/experience.golden.json", parseExperiences(string(html)))
}

func TestParseExperiencesEmpty(t *testing.T) {
	if got := parseExperiences(`<p>Nothing to see for now</p>`); len(got) != 0 {
		t.Errorf("seção vazia deveria devolver 0 experiências, obteve %d", len(got))
	}
}

func TestParseDateLine(t *testing.T) {
	str := func(s string) *string { return &s }
	cases := []struct {
		line    string
		start   string
		end     *string
		current bool
	}{
		{"Mar 2023 - Present · 3 yrs 8 mos", "2023-03-01T00:00:00.000Z", nil, true},
		{"mai de 2019 - o momento", "2019-05-01T00:00:00.000Z", nil, true},
		{"Mar 2008 - Jun 2009 · 1 yr 4 mos", "2008-03-01T00:00:00.000Z", str("2009-06-30T00:00:00.000Z"), false},
		{"2023 – 2024", "2023-01-01T00:00:00.000Z", str("2024-12-31T00:00:00.000Z"), false},
		{"jan de 2020 - dez de 2021", "2020-01-01T00:00:00.000Z", str("2021-12-31T00:00:00.000Z"), false},
		{"2021", "2021-01-01T00:00:00.000Z", str("2021-12-31T00:00:00.000Z"), false},
	}
	for _, c := range cases {
		if !isDateLine(c.line) {
			t.Errorf("%q deveria ser linha de data", c.line)
			continue
		}
		start, end, current := parseDateLine(c.line)
		if start != c.start || current != c.current || (end == nil) != (c.end == nil) || (end != nil && *end != *c.end) {
			t.Errorf("%q: obteve (%s, %v, %v)", c.line, start, end, current)
		}
	}
	for _, line := range []string{"Belo Horizonte, Brazil", "CEO & Founder", "Xyz 2020"} {
		if isDateLine(line) {
			t.Errorf("%q não deveria ser linha de data", line)
		}
	}
}
