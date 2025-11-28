package main

import (
	"encoding/json"
	"fmt"
	"html"
	"os"
	"regexp"
	"strings"
)

// Profile representa a estrutura do perfil normalizado
type Profile struct {
	FirstName      string   `json:"first_name"`
	LastName       string   `json:"last_name"`
	BirthDate      string   `json:"birth_date"`
	EmailAddresses []string `json:"email_addresses"`
	AvatarURL      string   `json:"avatar_url"`
	Address        Address  `json:"address"`
	Phones         []string `json:"phones"`
	LinkedInURL    string   `json:"linkedin_url"`
	Description    string   `json:"description"`
	Headline       string   `json:"headline,omitempty"`
	Company        string   `json:"company,omitempty"`
	University     string   `json:"university,omitempty"`
}

// Address representa o endereço
type Address struct {
	Name         string `json:"name"`
	Street       string `json:"street"`
	PostalCode   string `json:"postal_code"`
	Region       string `json:"region"`
	Neighborhood string `json:"neighborhood"`
	Locality     string `json:"locality"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Uso: linkedin-parser <arquivo.html> [output.json]")
		os.Exit(1)
	}

	inputFile := os.Args[1]
	outputFile := "profile.json"
	if len(os.Args) >= 3 {
		outputFile = os.Args[2]
	}

	content, err := os.ReadFile(inputFile)
	if err != nil {
		fmt.Printf("Erro ao ler arquivo: %v\n", err)
		os.Exit(1)
	}

	htmlContent := string(content)
	profile := parseProfile(htmlContent)

	jsonData, err := json.MarshalIndent(profile, "", "  ")
	if err != nil {
		fmt.Printf("Erro ao gerar JSON: %v\n", err)
		os.Exit(1)
	}

	err = os.WriteFile(outputFile, jsonData, 0644)
	if err != nil {
		fmt.Printf("Erro ao salvar arquivo: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Perfil extraído com sucesso: %s\n", outputFile)

}

func parseProfile(htmlContent string) Profile {
	profile := Profile{
		EmailAddresses: []string{},
		Phones:         []string{},
		Address: Address{
			Street:       "",
			PostalCode:   "",
			Region:       "",
			Neighborhood: "",
		},
	}

	// Extrair nome completo do título
	profile.FirstName, profile.LastName = extractName(htmlContent)

	// Extrair LinkedIn URL (usa firstName para encontrar o perfil correto)
	profile.LinkedInURL = extractLinkedInURL(htmlContent, profile.FirstName)

	// Extrair localização
	profile.Address = extractAddress(htmlContent)

	// Extrair foto de perfil (maior resolução)
	profile.AvatarURL = extractAvatarURL(htmlContent)

	// Extrair headline
	profile.Headline = extractHeadline(htmlContent)

	// Extrair empresa e universidade
	profile.Company, profile.University = extractCompanyAndUniversity(htmlContent)

	// Extrair descrição/about
	profile.Description = extractDescription(htmlContent)

	// Extrair emails do texto
	profile.EmailAddresses = extractEmails(htmlContent)

	// Extrair telefones
	profile.Phones = extractPhones(htmlContent)

	return profile
}

func extractName(html string) (firstName, lastName string) {
	// Padrão: <title>Nome Sobrenome | LinkedIn</title>
	re := regexp.MustCompile(`<title>([^|<]+)\s*\|\s*LinkedIn</title>`)
	matches := re.FindStringSubmatch(html)
	if len(matches) > 1 {
		fullName := strings.TrimSpace(matches[1])
		parts := strings.SplitN(fullName, " ", 2)
		firstName = parts[0]
		if len(parts) > 1 {
			lastName = parts[1]
		}
	}
	return
}

func extractLinkedInURL(htmlContent string, firstName string) string {
	// Procura por linkedin.com/in/username - prioriza URLs que contêm parte do nome
	re := regexp.MustCompile(`href="(https://www\.linkedin\.com/in/([^"/]+))/?"`)
	matches := re.FindAllStringSubmatch(htmlContent, -1)

	// Normaliza o primeiro nome para comparação
	firstNameLower := strings.ToLower(firstName)
	firstNameNorm := normalizeString(firstNameLower)

	for _, match := range matches {
		if len(match) > 2 {
			username := strings.ToLower(match[2])
			usernameNorm := normalizeString(username)

			// Verifica se o username contém o primeiro nome
			if strings.Contains(usernameNorm, firstNameNorm) {
				url := match[1]
				return decodeURL(url)
			}
		}
	}

	// Fallback: retorna o primeiro URL encontrado
	if len(matches) > 0 && len(matches[0]) > 1 {
		return decodeURL(matches[0][1])
	}

	return ""
}

func normalizeString(s string) string {
	replacer := strings.NewReplacer(
		"á", "a", "à", "a", "ã", "a", "â", "a",
		"é", "e", "è", "e", "ê", "e",
		"í", "i", "ì", "i", "î", "i",
		"ó", "o", "ò", "o", "õ", "o", "ô", "o",
		"ú", "u", "ù", "u", "û", "u",
		"ç", "c",
		"%c3%a1", "a", "%c3%a0", "a", "%c3%a3", "a", "%c3%a2", "a",
		"%c3%a9", "e", "%c3%a8", "e", "%c3%aa", "e",
		"%c3%ad", "i", "%c3%ac", "i", "%c3%ae", "i",
		"%c3%b3", "o", "%c3%b2", "o", "%c3%b5", "o", "%c3%b4", "o",
		"%c3%ba", "u", "%c3%b9", "u", "%c3%bb", "u",
		"%c3%a7", "c",
	)
	return replacer.Replace(strings.ToLower(s))
}

func decodeURL(url string) string {
	replacer := strings.NewReplacer(
		"%C3%A1", "á", "%C3%A0", "à", "%C3%A3", "ã", "%C3%A2", "â",
		"%C3%A9", "é", "%C3%A8", "è", "%C3%AA", "ê",
		"%C3%AD", "í", "%C3%AC", "ì", "%C3%AE", "î",
		"%C3%B3", "ó", "%C3%B2", "ò", "%C3%B5", "õ", "%C3%B4", "ô",
		"%C3%BA", "ú", "%C3%B9", "ù", "%C3%BB", "û",
		"%C3%A7", "ç",
		"%c3%a1", "á", "%c3%a0", "à", "%c3%a3", "ã", "%c3%a2", "â",
		"%c3%a9", "é", "%c3%a8", "è", "%c3%aa", "ê",
		"%c3%ad", "í", "%c3%ac", "ì", "%c3%ae", "î",
		"%c3%b3", "ó", "%c3%b2", "ò", "%c3%b5", "õ", "%c3%b4", "ô",
		"%c3%ba", "ú", "%c3%b9", "ù", "%c3%bb", "û",
		"%c3%a7", "ç",
	)
	return replacer.Replace(url)
}

func extractAddress(htmlContent string) Address {
	addr := Address{
		Street:       "",
		PostalCode:   "",
		Neighborhood: "",
	}

	// Padrão: City, State, Country em um <p>
	re := regexp.MustCompile(`>([^<>]+,\s*[^<>]+,\s*[A-Za-z]+)</p>`)
	matches := re.FindAllStringSubmatch(htmlContent, -1)

	for _, match := range matches {
		if len(match) > 1 {
			location := strings.TrimSpace(match[1])
			// Verificar se parece uma localização (tem vírgulas separando partes)
			parts := strings.Split(location, ",")
			if len(parts) >= 2 {
				lastPart := strings.TrimSpace(parts[len(parts)-1])
				// Verificar se a última parte é um país
				if isCountry(lastPart) {
					addr.Name = location
					addr.Locality = lastPart
					if len(parts) >= 3 {
						addr.Region = strings.TrimSpace(parts[1])
					}
					break
				}
			}
		}
	}

	return addr
}

func isCountry(s string) bool {
	countries := []string{
		"Brazil", "Brasil", "USA", "United States", "UK", "United Kingdom",
		"Canada", "Germany", "France", "Spain", "Portugal", "Italy",
		"Argentina", "Mexico", "Chile", "Colombia", "Peru",
	}
	for _, c := range countries {
		if strings.EqualFold(s, c) {
			return true
		}
	}
	return false
}

func extractAvatarURL(htmlContent string) string {
	// Procura pela maior resolução de foto de perfil
	re := regexp.MustCompile(`(https://media\.licdn\.com/dms/image/[^"]*profile-displayphoto[^"]*)`)
	matches := re.FindAllString(htmlContent, -1)

	bestURL := ""
	bestSize := 0

	for _, url := range matches {
		// Decodificar &amp;
		url = strings.ReplaceAll(url, "&amp;", "&")

		// Verificar tamanho pela URL
		sizeRe := regexp.MustCompile(`(\d+)_(\d+)`)
		sizeMatch := sizeRe.FindStringSubmatch(url)
		if len(sizeMatch) > 1 {
			size := 0
			fmt.Sscanf(sizeMatch[1], "%d", &size)
			if size > bestSize {
				bestSize = size
				bestURL = url
			}
		}
	}

	if bestURL == "" && len(matches) > 0 {
		bestURL = strings.ReplaceAll(matches[0], "&amp;", "&")
	}

	return bestURL
}

func extractHeadline(htmlContent string) string {
	// Procura headline após o nome
	patterns := []string{
		`aria-label="[^"]+">.*?<p[^>]*>([^<]+)</p>.*?<p[^>]*>([^<]{20,})</p>`,
		`>([^<]*(?:Senior|Manager|Director|Engineer|Developer|Founder|CEO|CTO|Recruiter|Talent|Tech)[^<]*)</p>`,
	}

	for _, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		matches := re.FindStringSubmatch(htmlContent)
		if len(matches) > 1 {
			headline := strings.TrimSpace(matches[len(matches)-1])
			if len(headline) > 20 && len(headline) < 300 {
				return cleanHTML(headline)
			}
		}
	}

	// Busca alternativa
	re := regexp.MustCompile(`>([^<]*\|[^<]*\|[^<]*)</p>`)
	matches := re.FindStringSubmatch(htmlContent)
	if len(matches) > 1 {
		return cleanHTML(strings.TrimSpace(matches[1]))
	}

	return ""
}

func extractCompanyAndUniversity(htmlContent string) (company, university string) {
	// Padrão comum: "Company · University"
	re := regexp.MustCompile(`>([^<]+)\s*·\s*([^<]+)</p>`)
	matches := re.FindStringSubmatch(htmlContent)
	if len(matches) > 2 {
		company = strings.TrimSpace(matches[1])
		university = strings.TrimSpace(matches[2])
	}
	return
}

func extractDescription(htmlContent string) string {
	// Procura pelo about/description no expandable-text-box
	re := regexp.MustCompile(`data-testid="expandable-text-box"[^>]*>([^<]+(?:<[^>]+>[^<]*)*?)(?:</span>|<button)`)
	matches := re.FindStringSubmatch(htmlContent)
	if len(matches) > 1 {
		desc := matches[1]
		// Limpar HTML
		desc = cleanHTML(desc)
		// Converter quebras de linha
		desc = strings.ReplaceAll(desc, "\n", "<br><br>")
		// Remover <br><br> repetidos
		for strings.Contains(desc, "<br><br><br>") {
			desc = strings.ReplaceAll(desc, "<br><br><br>", "<br><br>")
		}
		return strings.TrimSpace(desc)
	}

	// Busca alternativa pelo padrão "My career" ou "Minha carreira"
	patterns := []string{
		`(?is)(my career[^<]{50,1500})`,
		`(?is)(minha carreira[^<]{50,1500})`,
	}

	for _, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		matches := re.FindStringSubmatch(htmlContent)
		if len(matches) > 1 {
			return cleanHTML(matches[1])
		}
	}

	return ""
}

func extractEmails(htmlContent string) []string {
	// Decodificar HTML entities primeiro
	htmlContent = html.UnescapeString(htmlContent)

	re := regexp.MustCompile(`[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`)
	matches := re.FindAllString(htmlContent, -1)

	// Remover duplicatas
	seen := make(map[string]bool)
	unique := []string{}
	for _, email := range matches {
		emailLower := strings.ToLower(email)
		// Ignorar emails do LinkedIn e outros domínios de sistema
		if !strings.Contains(emailLower, "linkedin") &&
			!strings.Contains(emailLower, "licdn") &&
			!strings.Contains(emailLower, "@example") &&
			!seen[emailLower] {
			seen[emailLower] = true
			unique = append(unique, emailLower)
		}
	}

	return unique
}

func extractPhones(htmlContent string) []string {
	// Padrões brasileiros e internacionais
	patterns := []string{
		`\+55\s*\d{2}\s*\d{4,5}[-\s]?\d{4}`,
		`\(\d{2}\)\s*\d{4,5}[-\s]?\d{4}`,
		`\+1[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{4}`,
	}

	phones := []string{}
	for _, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		matches := re.FindAllString(htmlContent, -1)
		phones = append(phones, matches...)
	}

	return phones
}

func cleanHTML(s string) string {
	// Remove tags HTML
	re := regexp.MustCompile(`<[^>]+>`)
	s = re.ReplaceAllString(s, " ")

	// Decodificar entidades HTML
	s = html.UnescapeString(s)

	// Limpar espaços extras
	re = regexp.MustCompile(`\s+`)
	s = re.ReplaceAllString(s, " ")

	return strings.TrimSpace(s)
}
