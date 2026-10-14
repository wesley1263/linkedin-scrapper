package main

import (
	"encoding/json"
	"fmt"
	"html"
	"io/ioutil"
	"log"
	"os"
	"regexp"
	"strings"
	"time"
)

// DegreeLevel enum para os níveis de educação
type DegreeLevel string

const (
	BACHELOR                DegreeLevel = "BACHELOR"
	POST_BACHELOR           DegreeLevel = "POST_BACHELOR"
	MBA                     DegreeLevel = "MBA"
	MASTER                  DegreeLevel = "MASTER"
	DOCTORATE               DegreeLevel = "DOCTORATE"
	POST_DOCTORATE          DegreeLevel = "POST_DOCTORATE"
	EXTRA_CURRICULAR_COURSE DegreeLevel = "EXTRA_CURRICULAR_COURSE"
	EMPTY                   DegreeLevel = "EMPTY"
)

// Institution representa uma instituição de ensino
type Institution struct {
	Name      string `json:"name"`
	URL       string `json:"url"`
	AvatarURL string `json:"avatar_url"`
}

// Education representa um registro de educação
type Education struct {
	DegreeName  string      `json:"degree_name"`
	DegreeLevel DegreeLevel `json:"degree_level"`
	CourseTitle string      `json:"course_title"`
	StartDate   string      `json:"start_date"`
	EndDate     string      `json:"end_date"`
	Institution Institution `json:"institution"`
}

// EducationParser contém os métodos para fazer parse de HTML
type EducationParser struct {
	htmlContent string
}

// NewEducationParser cria uma nova instância do parser
func NewEducationParser(htmlContent string) *EducationParser {
	return &EducationParser{htmlContent: htmlContent}
}

var (
	itemKeyRe     = regexp.MustCompile(`componentkey="entity-collection-item`)
	pRe           = regexp.MustCompile(`(?s)<p\b[^>]*>(.*?)</p>`)
	tagRe         = regexp.MustCompile(`<[^>]+>`)
	spaceRe       = regexp.MustCompile(`\s+`)
	logoAltRe     = regexp.MustCompile(`alt="([^"]+) logo"`)
	avatarRe      = regexp.MustCompile(`alt="[^"]*logo[^"]*"\s+src="([^"]+)"`)
	institutionRe = regexp.MustCompile(`href="(https://www\.linkedin\.com/(?:school|company)/[^"/]+)/?"`)

	// "2013 – 2015", "Apr 2023 – Jul 2025", "Aug 2025 – Present", "Dec 2022", "mai de 2019 - o momento"
	datePart   = `(?:([A-Za-z]{3})[a-z]*\.?\s+(?:de\s+)?)?(\d{4})`
	dateLineRe = regexp.MustCompile(`(?i)^` + datePart + `(?:\s*[-–—]\s*(?:` + datePart + `|(present|o momento|atual)))?$`)
)

var monthNumbers = map[string]int{
	"jan": 1, "feb": 2, "fev": 2, "mar": 3, "apr": 4, "abr": 4,
	"may": 5, "mai": 5, "jun": 6, "jul": 7, "aug": 8, "ago": 8,
	"sep": 9, "set": 9, "oct": 10, "out": 10, "nov": 11, "dec": 12, "dez": 12,
}

// normalizeDegreeLevel converte texto de grau para enum DegreeLevel.
// A ordem importa: "Pós-graduação" contém "graduação" e "Master of Business Administration" contém "master"
func normalizeDegreeLevel(degreeText string) DegreeLevel {
	degreeText = strings.ToLower(strings.TrimSpace(degreeText))
	has := func(words ...string) bool {
		for _, w := range words {
			if strings.Contains(degreeText, w) {
				return true
			}
		}
		return false
	}

	switch {
	case has("pós-doutorado", "pós doutorado", "pos-doutorado", "post-doctorate", "postdoc"):
		return POST_DOCTORATE
	case has("doutorado", "phd", "ph.d", "doctorate", "doctor of"):
		return DOCTORATE
	case has("mba", "master of business administration"):
		return MBA
	case has("mestrado", "master", "mestre"):
		return MASTER
	case has("pós-graduação", "pós graduação", "pos-graduacao", "pos graduacao", "pós-graduado",
		"especialização", "especialista", "postgraduate", "post-graduate", "certificate"):
		return POST_BACHELOR
	case has("bacharel", "bachelor", "graduação", "graduacao", "licenciatura", "tecnólogo", "tecnologo"):
		return BACHELOR
	case has("curso", "course", "capacitação", "capacitacao", "workshop", "treinamento", "técnico", "technical"):
		return EXTRA_CURRICULAR_COURSE
	default:
		return EMPTY
	}
}

// getDegreeName retorna o nome do grau baseado no nível
func getDegreeName(level DegreeLevel) string {
	switch level {
	case BACHELOR:
		return "Bacharelado"
	case MASTER:
		return "Mestrado"
	case DOCTORATE:
		return "Doutorado"
	case POST_DOCTORATE:
		return "Pós-doutorado"
	case POST_BACHELOR:
		return "Especialização"
	case MBA:
		return "MBA"
	case EXTRA_CURRICULAR_COURSE:
		return "Curso"
	default:
		return ""
	}
}

// extractEducationData extrai os itens da lista de formação
// (div com componentkey="entity-collection-item-..."), cujos <p> são
// [instituição, "Grau, Área"?, datas?, atividades/descrição...]
func (ep *EducationParser) extractEducationData() []Education {
	var educations []Education

	content := ep.htmlContent
	if i := strings.Index(content, `data-testid="profile_EducationDetailsSection`); i >= 0 {
		content = content[i:]
	}

	lastEnd := 0
	for _, loc := range itemKeyRe.FindAllStringIndex(content, -1) {
		start := strings.LastIndex(content[:loc[0]], "<div")
		if start < lastEnd {
			continue // item aninhado em outro já extraído
		}
		block := balancedBlock(content, start, "div")
		lastEnd = start + len(block)

		if edu, ok := parseEducationItem(block); ok {
			educations = append(educations, edu)
		}
	}

	return educations
}

func parseEducationItem(block string) (Education, bool) {
	var texts []string
	for _, match := range pRe.FindAllStringSubmatch(block, -1) {
		if text := cleanText(match[1]); text != "" {
			texts = append(texts, text)
		}
	}

	edu := Education{}
	if match := institutionRe.FindStringSubmatch(block); len(match) > 1 {
		edu.Institution.URL = match[1]
	}
	if match := avatarRe.FindStringSubmatch(block); len(match) > 1 {
		edu.Institution.AvatarURL = html.UnescapeString(match[1])
	}

	if len(texts) > 0 {
		edu.Institution.Name = texts[0]
	} else if match := logoAltRe.FindStringSubmatch(block); len(match) > 1 {
		edu.Institution.Name = cleanText(match[1])
	}
	if edu.Institution.Name == "" {
		return edu, false
	}

	// Até 3 linhas após a instituição: grau/área e datas (qualquer um pode faltar)
	for _, text := range texts[1:min(len(texts), 3)] {
		if isDateLine(text) {
			edu.StartDate, edu.EndDate = parseDateLine(text)
			break
		}
		if edu.CourseTitle == "" {
			edu.DegreeLevel, edu.CourseTitle = parseDegreeLine(text)
		}
	}
	if edu.DegreeLevel == "" {
		edu.DegreeLevel = EMPTY
	}
	edu.DegreeName = getDegreeName(edu.DegreeLevel)

	return edu, true
}

// parseDegreeLine separa "Grau, Área". Se o trecho antes da vírgula não for um grau
// reconhecível (ex.: "Ciência da Computação, Tecnologia da Informação"), mantém a linha inteira como curso
func parseDegreeLine(text string) (DegreeLevel, string) {
	level := normalizeDegreeLevel(text)
	parts := strings.SplitN(text, ",", 2)
	if len(parts) == 2 && normalizeDegreeLevel(parts[0]) != EMPTY {
		if course := strings.TrimSpace(parts[1]); course != "" {
			return normalizeDegreeLevel(parts[0]), course
		}
	}
	return level, text
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

// parseDateLine retorna início e fim (YYYY-MM-DD). Data única é tratada como conclusão; "Present" deixa o fim vazio
func parseDateLine(line string) (startDate, endDate string) {
	match := dateLineRe.FindStringSubmatch(line)
	if match == nil {
		return
	}

	hasRange := match[4] != "" || match[5] != ""
	if !hasRange {
		return "", formatDate(match[1], match[2], 12, true)
	}

	startDate = formatDate(match[1], match[2], 1, false)
	if match[4] != "" {
		endDate = formatDate(match[3], match[4], 12, true)
	}
	return
}

// formatDate converte mês/ano para YYYY-MM-DD; sem mês usa defaultMonth. endOfMonth usa o último dia do mês
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
	return t.Format("2006-01-02")
}

// balancedBlock retorna o elemento <tag> que começa em start, até a tag de fechamento correspondente
func balancedBlock(s string, start int, tag string) string {
	re := regexp.MustCompile(`<` + tag + `\b|</` + tag + `>`)
	depth := 0
	for _, loc := range re.FindAllStringIndex(s[start:], -1) {
		if s[start+loc[0]+1] == '/' {
			depth--
		} else {
			depth++
		}
		if depth == 0 {
			return s[start : start+loc[1]]
		}
	}
	return s[start:]
}

func cleanText(s string) string {
	s = html.UnescapeString(tagRe.ReplaceAllString(s, " "))
	s = strings.ReplaceAll(s, "​", "")
	return strings.TrimSpace(spaceRe.ReplaceAllString(s, " "))
}

// processHTMLFile processa um arquivo HTML e retorna dados de educação
func processHTMLFile(filename string) ([]Education, error) {
	content, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, fmt.Errorf("erro ao ler arquivo %s: %v", filename, err)
	}

	parser := NewEducationParser(string(content))
	educations := parser.extractEducationData()
	if educations == nil {
		educations = []Education{}
	}

	return educations, nil
}

// saveToJSON salva os dados em formato JSON
func saveToJSON(educations []Education, filename string) error {
	jsonData, err := json.MarshalIndent(educations, "", "  ")
	if err != nil {
		return fmt.Errorf("erro ao converter para JSON: %v", err)
	}

	err = ioutil.WriteFile(filename, jsonData, 0644)
	if err != nil {
		return fmt.Errorf("erro ao salvar arquivo %s: %v", filename, err)
	}

	return nil
}

func main() {
	if len(os.Args) < 2 {
		log.Fatal("Uso: go run main.go <arquivo_html> [arquivo_saida.json]")
	}

	inputFile := os.Args[1]
	outputFile := "education.json"

	if len(os.Args) >= 3 {
		outputFile = os.Args[2]
	}

	fmt.Printf("Processando arquivo: %s\n", inputFile)

	educations, err := processHTMLFile(inputFile)
	if err != nil {
		log.Fatalf("Erro ao processar arquivo: %v", err)
	}

	fmt.Printf("Encontrados %d registros de educação\n", len(educations))

	err = saveToJSON(educations, outputFile)
	if err != nil {
		log.Fatalf("Erro ao salvar JSON: %v", err)
	}

	fmt.Printf("Dados salvos em: %s\n", outputFile)
}
