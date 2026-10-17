package main

import (
	"os"
	"strings"
	"testing"

	"linkedin-enrichment/internal/golden"
)

func loadProfile(t *testing.T) Profile {
	t.Helper()
	html, err := os.ReadFile("testdata/profile.html")
	if err != nil {
		t.Fatal(err)
	}
	return parseProfile(string(html))
}

func TestParseProfileGolden(t *testing.T) {
	golden.Check(t, "testdata/profile.golden.json", loadProfile(t))
}

// Valores conferidos à mão contra o HTML original: o golden sozinho só trava o que já está lá
func TestParseProfileFields(t *testing.T) {
	p := loadProfile(t)

	checks := map[string][2]string{
		"first_name":   {p.FirstName, "Pessoa"},
		"last_name":    {p.LastName, "Exemplo"},
		"linkedin_url": {p.LinkedInURL, "https://www.linkedin.com/in/pessoa-exemplo"},
		"headline":     {p.Headline, "CEO & Founder - Empresa Exemplo"},
		"company":      {p.Company, "Empresa Exemplo"},
		"university":   {p.University, "Universidade Exemplo"},
		"address.name": {p.Address.Name, "Cidade Exemplo, Estado Exemplo, Brazil"},
		"region":       {p.Address.Region, "Estado Exemplo"},
		"locality":     {p.Address.Locality, "Brazil"},
	}
	for field, c := range checks {
		if c[0] != c[1] {
			t.Errorf("%s = %q, esperado %q", field, c[0], c[1])
		}
	}

	// Maior resolução do srcset, uma única URL, sem &amp;
	if !strings.HasSuffix(p.AvatarURL, "profile-displayphoto-crop_800_800.png") || strings.ContainsAny(p.AvatarURL, " ,") {
		t.Errorf("avatar_url = %q, esperada a URL única de 800x800", p.AvatarURL)
	}
	if !strings.HasPrefix(p.Description, "Linha de descrição de exemplo.") || strings.Contains(p.Description, "Habilidade") {
		t.Errorf("description = %q, deveria ser só o texto do About", p.Description)
	}
	if len(p.EmailAddresses) != 0 || len(p.Phones) != 0 {
		t.Errorf("emails/telefones deveriam estar vazios: %v %v", p.EmailAddresses, p.Phones)
	}
}

func TestParseProfileEmpty(t *testing.T) {
	p := parseProfile(`<html><body><p>nada</p></body></html>`)
	if p.FirstName != "" || p.LinkedInURL != "" || p.Description != "" || p.EmailAddresses == nil || p.Phones == nil {
		t.Errorf("HTML sem perfil deveria devolver campos vazios (e listas não-nulas): %+v", p)
	}
}
