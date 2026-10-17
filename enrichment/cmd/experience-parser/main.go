package main

import (
	"fmt"
	"html"
	"linkedin-enrichment/internal/parser"
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

var (
	itemKeyRe = regexp.MustCompile(`componentkey="entity-collection-item`)
	pRe       = regexp.MustCompile(`(?s)<p\b[^>]*>(.*?)</p>`)
	liStartRe = regexp.MustCompile(`<li\b`)
	logoAltRe = regexp.MustCompile(`alt="([^"]+) logo"`)
	avatarRe  = regexp.MustCompile(`alt="[^"]*logo[^"]*"\s+src="([^"]+)"`)
	companyRe = regexp.MustCompile(`href="(https://www\.linkedin\.com/company/[^"/]+)/?"`)
	brRe      = regexp.MustCompile(`(?i)<br\s*/?>`)
	tagRe     = regexp.MustCompile(`<[^>]+>`)
	spaceRe   = regexp.MustCompile(`[ \t\r\f\v\x{00a0}]+`)

	// "May 2019 - Present · 7 yrs", "2023 – 2024", "mai de 2019 - o momento"
	datePart   = `(?:([A-Za-z]{3})[a-z]*\.?\s+(?:de\s+)?)?(\d{4})`
	dateLineRe = regexp.MustCompile(`(?i)^` + datePart + `(?:\s*[-–—]\s*(?:` + datePart + `|(present|o momento|atual)))?\s*(?:·.*)?$`)
)

var monthNumbers = map[string]int{
	"jan": 1, "feb": 2, "fev": 2, "mar": 3, "apr": 4, "abr": 4,
	"may": 5, "mai": 5, "jun": 6, "jul": 7, "aug": 8, "ago": 8,
	"sep": 9, "set": 9, "oct": 10, "out": 10, "nov": 11, "dec": 12, "dez": 12,
}

func parseExperiences(htmlContent string) []Experience {
	var experiences []Experience

	for _, block := range extractItemBlocks(htmlContent) {
		for _, exp := range parseItem(block) {
			if exp.RoleName != "" && exp.Company.Name != "" {
				experiences = append(experiences, exp)
			}
		}
	}

	return experiences
}

// extractItemBlocks retorna o HTML de cada item da lista de experiências
// (div com componentkey="entity-collection-item-..."), delimitado pelo fechamento da div
func extractItemBlocks(htmlContent string) []string {
	if i := strings.Index(htmlContent, `data-testid="profile_ExperienceDetailsSection`); i >= 0 {
		htmlContent = htmlContent[i:]
	}

	var blocks []string
	lastEnd := 0
	for _, loc := range itemKeyRe.FindAllStringIndex(htmlContent, -1) {
		start := strings.LastIndex(htmlContent[:loc[0]], "<div")
		if start < lastEnd {
			continue // item aninhado em outro já extraído
		}
		block := parser.BalancedBlock(htmlContent, start, "div")
		blocks = append(blocks, block)
		lastEnd = start + len(block)
	}

	return blocks
}

// parseItem trata os dois formatos de item:
//   - cargo único:   [cargo, "Empresa · Tipo", datas, local?]
//   - vários cargos: [empresa, "Tipo · duração", local?] + um <li> por cargo: [cargo, tipo?, datas, local?]
func parseItem(block string) []Experience {
	base := newExperience()
	if match := companyRe.FindStringSubmatch(block); len(match) > 1 {
		base.LinkedInURL = match[1]
	}
	if match := avatarRe.FindStringSubmatch(block); len(match) > 1 {
		base.AvatarURL = html.UnescapeString(match[1])
	}
	if match := logoAltRe.FindStringSubmatch(block); len(match) > 1 {
		base.Company.Name = parser.CleanText(match[1])
	}

	header := headerTexts(block)
	dateIdx := indexOfDateLine(header)

	// Cargo único
	if dateIdx >= 1 {
		exp := base
		exp.RoleName = header[0]
		if dateIdx >= 2 {
			exp.Company.Name = strings.Split(header[1], " · ")[0]
		}
		fillDatesAndLocation(&exp, header, dateIdx, "")
		exp.Description = extractDescription(block)
		return []Experience{exp}
	}

	// Vários cargos na mesma empresa
	if len(header) == 0 {
		return nil
	}
	base.Company.Name = header[0]
	groupLocation := ""
	if len(header) > 2 {
		groupLocation = locationText(header[2])
	}

	var experiences []Experience
	lastEnd := 0
	for _, loc := range liStartRe.FindAllStringIndex(block, -1) {
		if loc[0] < lastEnd {
			continue
		}
		li := parser.BalancedBlock(block, loc[0], "li")
		lastEnd = loc[0] + len(li)

		liHeader := headerTexts(li)
		idx := indexOfDateLine(liHeader)
		if idx < 1 {
			continue
		}
		exp := base
		exp.Realizations = []interface{}{}
		exp.RoleName = liHeader[0]
		fillDatesAndLocation(&exp, liHeader, idx, groupLocation)
		exp.Description = extractDescription(li)
		experiences = append(experiences, exp)
	}

	return experiences
}

func newExperience() Experience {
	return Experience{
		PersonID:              "",
		Salary:                Salary{Amount: 0, ContractType: "", Currency: "BRL", PaymentFrequency: ""},
		IncentiveCompensation: "",
		Conditions:            "",
		Realizations:          []interface{}{},
		Company:               Company{CorporationID: ""},
	}
}

// headerTexts retorna os textos dos <p> do cabeçalho do item (antes de descrição, skills, mídias anexadas e sub-cargos)
func headerTexts(block string) []string {
	end := len(block)
	for _, marker := range []string{`data-testid="expandable-text-box"`, "skill-associations-details", "<li", "Thumbnail for"} {
		// A partir de 1: o próprio bloco pode começar com <li
		if i := strings.Index(block[1:], marker); i >= 0 && i+1 < end {
			end = i + 1
		}
	}

	var texts []string
	for _, match := range pRe.FindAllStringSubmatch(block[:end], -1) {
		// <p> com link são skills ("X, Y and +1 skill"), não local
		if strings.Contains(match[1], "<a ") {
			continue
		}
		text := parser.CleanText(match[1])
		if text != "" && !strings.Contains(text, "helped me get this job") && !strings.HasPrefix(text, "Skills:") {
			texts = append(texts, text)
		}
	}
	return texts
}

func indexOfDateLine(texts []string) int {
	for i, text := range texts {
		if isDateLine(text) {
			return i
		}
	}
	return -1
}

func isDateLine(text string) bool {
	match := dateLineRe.FindStringSubmatch(text)
	if match == nil {
		return false
	}
	for _, month := range []string{match[1], match[3]} {
		if month != "" && monthNumbers[strings.ToLower(month)] == 0 {
			return false
		}
	}
	return true
}

func fillDatesAndLocation(exp *Experience, texts []string, dateIdx int, defaultLocation string) {
	exp.StartDate, exp.EndDate, exp.IsCurrent = parseDateLine(texts[dateIdx])
	exp.JobLocation = defaultLocation
	if dateIdx+1 < len(texts) {
		exp.JobLocation = locationText(texts[dateIdx+1])
	}
}

// locationText remove o modelo de trabalho ("São Paulo, Brazil · Hybrid" -> "São Paulo, Brazil")
func locationText(text string) string {
	return strings.TrimSpace(strings.Split(text, " · ")[0])
}

func parseDateLine(line string) (startDate string, endDate *string, isCurrent bool) {
	match := dateLineRe.FindStringSubmatch(line)
	if match == nil {
		return
	}

	startDate = formatDate(match[1], match[2], 1, false)

	switch {
	case match[5] != "":
		isCurrent = true
	case match[4] != "":
		end := formatDate(match[3], match[4], 12, true)
		endDate = &end
	default:
		// Data única: termina no fim do mesmo período
		end := formatDate(match[1], match[2], 12, true)
		endDate = &end
	}
	return
}

// formatDate converte mês/ano para ISO; sem mês usa defaultMonth. endOfMonth usa o último dia do mês
func formatDate(month, year string, defaultMonth int, endOfMonth bool) string {
	m := defaultMonth
	if month != "" {
		m = monthNumbers[strings.ToLower(month)]
	}
	var y int
	fmt.Sscanf(year, "%d", &y)

	t := time.Date(y, time.Month(m), 1, 0, 0, 0, 0, time.UTC)
	if endOfMonth {
		t = t.AddDate(0, 1, -1)
	}
	return t.Format("2006-01-02T15:04:05.000Z")
}

// extractDescription pega o texto expansível do item, preservando quebras de linha
func extractDescription(block string) string {
	i := strings.Index(block, `data-testid="expandable-text-box"`)
	if i < 0 {
		return ""
	}
	rest := block[i:]
	rest = rest[strings.Index(rest, ">")+1:]
	if end := strings.Index(rest, "</p>"); end >= 0 {
		rest = rest[:end]
	}

	rest = brRe.ReplaceAllString(rest, "\n")
	rest = html.UnescapeString(tagRe.ReplaceAllString(rest, " "))

	var lines []string
	for _, line := range strings.Split(rest, "\n") {
		line = strings.TrimSpace(spaceRe.ReplaceAllString(line, " "))
		if line != "" {
			lines = append(lines, line)
		}
	}
	return strings.Join(lines, "\n")
}

func main() {
	os.Exit(parser.RunSection(parser.Spec{
		Section:       "experience",
		DefaultOutput: "experiences.json",
		AllowEmpty:    true,
		Parse: func(htmlContent string) (any, int) {
			experiences := parseExperiences(htmlContent)
			if experiences == nil {
				experiences = []Experience{}
			}
			return experiences, len(experiences)
		},
	}, os.Args[1:], os.Stdout, os.Stderr))
}
