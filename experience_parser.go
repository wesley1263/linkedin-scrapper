package main

import (
	"encoding/json"
	"fmt"
	"html"
	"os"
	"regexp"
	"strings"
	"time"
)

// Experience representa uma experiência profissional
type Experience struct {
	PersonID              string        `json:"person_id"`
	RoleName              string        `json:"role_name"`
	StartDate             string        `json:"start_date"`
	IsCurrent             bool          `json:"is_current"`
	EndDate               *string       `json:"end_date"`
	Description           string        `json:"description"`
	JobLocation           string        `json:"job_location"`
	Salary                Salary        `json:"salary"`
	IncentiveCompensation string        `json:"incentive_compensation"`
	Conditions            string        `json:"conditions"`
	Realizations          []interface{} `json:"realizations"`
	LinkedInURL           string        `json:"linkedin_url"`
	AvatarURL             string        `json:"avatar_url"`
	Company               Company       `json:"company"`
}

// Salary representa informações de salário
type Salary struct {
	Amount           int    `json:"amount"`
	ContractType     string `json:"contract_type"`
	Currency         string `json:"currency"`
	PaymentFrequency string `json:"payment_frequency"`
}

// Company representa informações da empresa
type Company struct {
	CorporationID string `json:"corporation_id"`
	Name          string `json:"name"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Uso: experience-parser <arquivo.html> [output.json]")
		os.Exit(1)
	}

	inputFile := os.Args[1]
	outputFile := "experiences.json"
	if len(os.Args) >= 3 {
		outputFile = os.Args[2]
	}

	content, err := os.ReadFile(inputFile)
	if err != nil {
		fmt.Printf("Erro ao ler arquivo: %v\n", err)
		os.Exit(1)
	}

	htmlContent := string(content)
	experiences := parseExperiences(htmlContent)

	jsonData, err := json.MarshalIndent(experiences, "", "  ")
	if err != nil {
		fmt.Printf("Erro ao gerar JSON: %v\n", err)
		os.Exit(1)
	}

	err = os.WriteFile(outputFile, jsonData, 0644)
	if err != nil {
		fmt.Printf("Erro ao salvar arquivo: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Experiências extraídas com sucesso: %s (%d experiências)\n", outputFile, len(experiences))
}

func parseExperiences(htmlContent string) []Experience {
	var experiences []Experience

	// Decodificar HTML entities
	htmlContent = html.UnescapeString(htmlContent)

	// Extrair blocos de experiência
	// Padrão: empresa logo -> cargo -> empresa · tipo -> data -> descrição
	blocks := extractExperienceBlocks(htmlContent)

	for _, block := range blocks {
		exp := parseExperienceBlock(block)
		if exp.RoleName != "" && exp.Company.Name != "" {
			experiences = append(experiences, exp)
		}
	}

	return experiences
}

func extractExperienceBlocks(htmlContent string) []string {
	var blocks []string

	// Encontra todos os blocos de empresa pelo logo
	// aria-label="COMPANY logo"
	logoRe := regexp.MustCompile(`aria-label="([^"]+) logo"`)
	logoMatches := logoRe.FindAllStringSubmatchIndex(htmlContent, -1)

	for i, match := range logoMatches {
		start := match[0]
		var end int
		if i+1 < len(logoMatches) {
			end = logoMatches[i+1][0]
		} else {
			end = len(htmlContent)
		}

		block := htmlContent[start:end]
		// Verificar se o bloco contém dados de experiência (datas no formato "Mon YYYY")
		if containsDatePattern(block) {
			blocks = append(blocks, block)
		}
	}

	return blocks
}

func containsDatePattern(s string) bool {
	dateRe := regexp.MustCompile(`(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}`)
	return dateRe.MatchString(s)
}

func parseExperienceBlock(block string) Experience {
	exp := Experience{
		PersonID:              "",
		Salary:                Salary{Amount: 0, ContractType: "", Currency: "BRL", PaymentFrequency: ""},
		IncentiveCompensation: "",
		Conditions:            "",
		Realizations:          []interface{}{},
		Company:               Company{CorporationID: ""},
	}

	// Extrair nome da empresa do logo
	logoRe := regexp.MustCompile(`aria-label="([^"]+) logo"`)
	if match := logoRe.FindStringSubmatch(block); len(match) > 1 {
		exp.Company.Name = strings.TrimSpace(match[1])
	}

	// Extrair URL do LinkedIn da empresa
	companyURLRe := regexp.MustCompile(`href="(https://www\.linkedin\.com/company/[^"/]+)/?"`)
	if match := companyURLRe.FindStringSubmatch(block); len(match) > 1 {
		exp.LinkedInURL = match[1]
	}

	// Extrair avatar URL da empresa
	avatarRe := regexp.MustCompile(`alt="[^"]*logo[^"]*"\s+src="([^"]+)"`)
	if match := avatarRe.FindStringSubmatch(block); len(match) > 1 {
		exp.AvatarURL = strings.ReplaceAll(match[1], "&amp;", "&")
	}

	// Extrair cargo - geralmente está em um <p> antes da data
	// Padrões comuns:
	// 1. "Role Name</p>" antes de "Company · Type"
	// 2. "Role Name</p>" antes de "Mon YYYY"
	exp.RoleName = extractRoleName(block)

	// Extrair datas
	exp.StartDate, exp.EndDate, exp.IsCurrent = extractDates(block)

	// Extrair localização (se houver)
	exp.JobLocation = extractLocation(block)

	// Extrair descrição
	exp.Description = extractDescription(block)

	return exp
}

func extractRoleName(block string) string {
	// Converter para linhas para facilitar a análise
	lines := strings.Split(block, ">")

	// Padrões de cargo comuns
	rolePatterns := []string{
		`^((?:Senior|Junior|Lead|Staff|Principal|Head|Chief|Manager|Director|VP|Founder|Co-Founder|Intern|Trainee|Analyst|Engineer|Developer|Designer|Recruiter|Sourcer|Specialist|Coordinator|Consultant|Advisor|Assistant|Professor|Researcher|Scientist|Writer|Editor|Executive|Partner|Owner|CEO|CTO|CFO|COO|CMO|CIO|CHRO)?\s*[A-Za-zÀ-ÿ\s|@&-]+)(?:</p|$)`,
	}

	// Procurar padrões específicos de cargo
	specificRoles := []string{
		"Senior Technical Sourcer",
		"Tech Sourcer",
		"Co-Founder",
		"Content Creator",
		"Talent Acquisition",
		"Tech Recruiter",
		"Pesquisadora",
		"Bolsista de Iniciação Científica",
		"Assessora de Psicologia Organizacional",
		"Assistente administrativa",
		"Professora de inglês",
	}

	for _, line := range lines {
		cleanLine := strings.TrimSpace(line)
		for _, role := range specificRoles {
			if strings.Contains(cleanLine, role) {
				// Extrair o cargo completo
				re := regexp.MustCompile(`([^<>]+)(?:</p|$)`)
				if match := re.FindStringSubmatch(cleanLine); len(match) > 1 {
					candidate := strings.TrimSpace(match[1])
					// Verificar se não é uma empresa ou data
					if !strings.Contains(candidate, " · ") &&
						!strings.Contains(candidate, " - ") &&
						!containsDatePattern(candidate) &&
						len(candidate) > 3 &&
						len(candidate) < 100 {
						return cleanHTML(candidate)
					}
				}
			}
		}
	}

	// Busca genérica por padrões de cargo
	for _, line := range lines {
		cleanLine := strings.TrimSpace(line)
		for _, pattern := range rolePatterns {
			re := regexp.MustCompile(pattern)
			if match := re.FindStringSubmatch(cleanLine); len(match) > 1 {
				candidate := strings.TrimSpace(match[1])
				if isValidRoleName(candidate) {
					return cleanHTML(candidate)
				}
			}
		}
	}

	// Fallback: buscar qualquer texto antes de " · " que pareça cargo
	re := regexp.MustCompile(`>([^<>]+)</p>`)
	matches := re.FindAllStringSubmatch(block, -1)
	for _, match := range matches {
		candidate := strings.TrimSpace(match[1])
		if isValidRoleName(candidate) && !strings.Contains(candidate, " · ") {
			return cleanHTML(candidate)
		}
	}

	return ""
}

func isValidRoleName(s string) bool {
	s = strings.TrimSpace(s)

	// Muito curto ou muito longo
	if len(s) < 4 || len(s) > 100 {
		return false
	}

	// É uma data
	if containsDatePattern(s) {
		return false
	}

	// Contém padrões de não-cargo
	invalidPatterns := []string{
		" · ", "yrs", "mos", "Present",
		"http", "www.", ".com",
		"logo", "thumbnail",
	}
	for _, p := range invalidPatterns {
		if strings.Contains(s, p) {
			return false
		}
	}

	// Deve conter palavras típicas de cargo ou ser um nome simples
	roleIndicators := []string{
		"Senior", "Junior", "Lead", "Staff", "Principal", "Head", "Chief",
		"Manager", "Director", "VP", "Founder", "Co-Founder", "Intern",
		"Analyst", "Engineer", "Developer", "Designer", "Recruiter", "Sourcer",
		"Specialist", "Coordinator", "Consultant", "Advisor", "Assistant",
		"Professor", "Researcher", "Scientist", "Executive", "Partner",
		"Owner", "CEO", "CTO", "CFO", "Talent", "Tech", "Software",
		"Pesquisador", "Bolsista", "Assessor", "Assistente", "Estagiário",
	}

	for _, indicator := range roleIndicators {
		if strings.Contains(strings.ToLower(s), strings.ToLower(indicator)) {
			return true
		}
	}

	return false
}

func extractDates(block string) (startDate string, endDate *string, isCurrent bool) {
	// Padrão: "Mon YYYY - Mon YYYY" ou "Mon YYYY - Present"
	dateRe := regexp.MustCompile(`((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*-\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present)`)
	match := dateRe.FindStringSubmatch(block)

	if len(match) > 2 {
		startDate = formatDateISO(match[1])

		if match[2] == "Present" {
			isCurrent = true
			endDate = nil
		} else {
			isCurrent = false
			endDateStr := formatDateISO(match[2])
			// Ajustar para último dia do mês
			endDateStr = adjustEndDate(endDateStr)
			endDate = &endDateStr
		}
	}

	return
}

func formatDateISO(dateStr string) string {
	// Converter "Mon YYYY" para "YYYY-MM-01T00:00:00.000Z"
	months := map[string]string{
		"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
		"May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
		"Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
	}

	parts := strings.Fields(dateStr)
	if len(parts) == 2 {
		month := months[parts[0]]
		year := parts[1]
		if month != "" && year != "" {
			return fmt.Sprintf("%s-%s-01T00:00:00.000Z", year, month)
		}
	}

	return ""
}

func adjustEndDate(dateStr string) string {
	// Ajustar para o último dia do mês
	if dateStr == "" {
		return ""
	}

	// Parse a data
	t, err := time.Parse("2006-01-02T15:04:05.000Z", dateStr)
	if err != nil {
		return dateStr
	}

	// Ir para o próximo mês e voltar um dia
	nextMonth := t.AddDate(0, 1, 0)
	lastDay := nextMonth.AddDate(0, 0, -1)

	return lastDay.Format("2006-01-02T15:04:05.000Z")
}

func extractLocation(block string) string {
	// Padrões de localização
	locationPatterns := []string{
		`(São Paulo[^<]*Brasil)`,
		`(Florianópolis[^<]*Brasil)`,
		`(San Francisco[^<]*Estados Unidos)`,
		`(San Francisco[^<]*United States)`,
		`([A-Za-zÀ-ÿ\s]+,\s*[A-Za-zÀ-ÿ\s]+,\s*(?:Brasil|Brazil|Estados Unidos|United States|USA))`,
		`([A-Za-zÀ-ÿ\s]+\s+e\s+Região,\s*Brasil)`,
	}

	for _, pattern := range locationPatterns {
		re := regexp.MustCompile(pattern)
		if match := re.FindStringSubmatch(block); len(match) > 1 {
			return cleanHTML(strings.TrimSpace(match[1]))
		}
	}

	return ""
}

func extractDescription(block string) string {
	var descriptions []string

	// Procurar por textos descritivos (geralmente após as datas)
	// Textos longos entre tags
	re := regexp.MustCompile(`>([^<]{50,})<`)
	matches := re.FindAllStringSubmatch(block, -1)

	for _, match := range matches {
		text := strings.TrimSpace(match[1])
		// Filtrar textos que não são descrição
		if !strings.Contains(text, "css") &&
			!strings.Contains(text, "script") &&
			!strings.Contains(text, "{") &&
			!strings.Contains(text, "class=") &&
			!strings.HasPrefix(text, "http") &&
			len(text) > 50 {
			descriptions = append(descriptions, cleanHTML(text))
		}
	}

	// Juntar todas as descrições encontradas
	if len(descriptions) > 0 {
		return strings.Join(descriptions, "\n")
	}

	return ""
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
