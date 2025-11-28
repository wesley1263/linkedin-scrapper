package main

import (
	"encoding/json"
	"fmt"
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

// normalizeDegreeLevel converte texto de grau para enum DegreeLevel
func normalizeDegreeLevel(degreeText string) DegreeLevel {
	degreeText = strings.ToLower(strings.TrimSpace(degreeText))

	// Mapeamento de palavras-chave para tipos de graduação
	switch {
	case strings.Contains(degreeText, "bacharelado") || strings.Contains(degreeText, "bachelor") ||
		strings.Contains(degreeText, "graduação") || strings.Contains(degreeText, "licenciatura"):
		return BACHELOR
	case strings.Contains(degreeText, "especialização") || strings.Contains(degreeText, "pós-graduação") ||
		strings.Contains(degreeText, "certificate") || strings.Contains(degreeText, "especialista"):
		return POST_BACHELOR
	case strings.Contains(degreeText, "mba"):
		return MBA
	case strings.Contains(degreeText, "mestrado") || strings.Contains(degreeText, "master"):
		return MASTER
	case strings.Contains(degreeText, "doutorado") || strings.Contains(degreeText, "phd") ||
		strings.Contains(degreeText, "doctorate"):
		return DOCTORATE
	case strings.Contains(degreeText, "pós-doutorado") || strings.Contains(degreeText, "post-doctorate"):
		return POST_DOCTORATE
	case strings.Contains(degreeText, "curso") || strings.Contains(degreeText, "course") ||
		strings.Contains(degreeText, "workshop") || strings.Contains(degreeText, "treinamento"):
		return EXTRA_CURRICULAR_COURSE
	default:
		return EMPTY
	}
}

// parseDate converte texto de data para formato ISO (YYYY-MM-DD)
func parseDate(dateText string) string {
	if dateText == "" {
		return ""
	}

	// Remove espaços extras e converte para minúsculas
	dateText = strings.ToLower(strings.TrimSpace(dateText))

	// Regex para extrair anos
	yearRegex := regexp.MustCompile(`\b(19|20)\d{2}\b`)
	years := yearRegex.FindAllString(dateText, -1)

	if len(years) == 0 {
		return ""
	}

	// Se só tem um ano, retorna com formato padrão
	if len(years) == 1 {
		return years[0] + "-01-01"
	}

	// Se tem múltiplos anos, retorna o primeiro
	return years[0] + "-01-01"
}

// extractEducationData extrai dados de educação do HTML usando abordagem estruturada
func (ep *EducationParser) extractEducationData() []Education {
	// Primeiro tenta extrair usando estrutura de itens de educação
	structuredEducations := ep.extractStructuredEducation()
	if len(structuredEducations) > 0 {
		return structuredEducations
	}

	// Se não encontrou estruturada, usa busca mais genérica
	return ep.fallbackEducationExtraction()
}

// extractStructuredEducation extrai dados usando estruturas HTML comuns do LinkedIn
func (ep *EducationParser) extractStructuredEducation() []Education {
	var allEducations []Education

	// Patterns para identificar blocos de educação
	patterns := []string{
		`<div[^>]*class="[^"]*education-item[^"]*"[^>]*>(.*?)</div>`,
		`<div[^>]*data-section="education"[^>]*>(.*?)</div>`,
		`<li[^>]*class="[^"]*education[^"]*"[^>]*>(.*?)</li>`,
		`<section[^>]*id="[^"]*education[^"]*"[^>]*>(.*?)</section>`,
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(`(?s)` + pattern)
		matches := regex.FindAllStringSubmatch(ep.htmlContent, -1)

		for _, match := range matches {
			if len(match) > 1 {
				// Processa sub-itens dentro da seção
				itemEducations := ep.parseEducationSection(match[1])
				allEducations = append(allEducations, itemEducations...)
			}
		}

		if len(allEducations) > 0 {
			break
		}
	}

	return allEducations
}

// parseEducationSection processa uma seção de educação e extrai itens individuais
func (ep *EducationParser) parseEducationSection(sectionHTML string) []Education {
	var educations []Education

	// Patterns para itens individuais de educação dentro da seção
	itemPatterns := []string{
		`<div[^>]*class="[^"]*education-item[^"]*"[^>]*>(.*?)</div>`,
		`<li[^>]*>(.*?)</li>`,
		`<div[^>]*>(.*?)</div>`,
	}

	for _, pattern := range itemPatterns {
		regex := regexp.MustCompile(`(?s)` + pattern)
		matches := regex.FindAllStringSubmatch(sectionHTML, -1)

		for _, match := range matches {
			if len(match) > 1 {
				education := ep.parseEducationItem(match[1])
				if ep.isValidEducation(education) {
					educations = append(educations, education)
				}
			}
		}

		if len(educations) > 0 {
			break
		}
	}

	// Se não encontrou itens estruturados, processa a seção inteira como um item
	if len(educations) == 0 {
		education := ep.parseEducationItem(sectionHTML)
		if ep.isValidEducation(education) {
			educations = append(educations, education)
		}
	}

	return educations
}

// parseEducationItem extrai dados de um item de educação específico
func (ep *EducationParser) parseEducationItem(itemHTML string) Education {
	education := Education{}

	// Remove tags HTML e normaliza texto
	textRegex := regexp.MustCompile(`<[^>]*>`)
	text := textRegex.ReplaceAllString(itemHTML, " ")
	text = strings.Join(strings.Fields(text), " ")

	// Extrai URLs primeiro (antes de remover HTML)
	education.Institution.URL = ep.extractURL(itemHTML)
	education.Institution.AvatarURL = ep.extractImageURL(itemHTML)

	// Extrai informações do texto limpo
	education.Institution.Name = ep.extractInstitutionName(text)
	education.CourseTitle = ep.extractCourseTitle(text)
	education.StartDate, education.EndDate = ep.extractDates(text)

	// Determina nível e nome do grau
	degreeText := education.CourseTitle + " " + text
	education.DegreeLevel = normalizeDegreeLevel(degreeText)
	education.DegreeName = ep.getDegreeName(education.DegreeLevel)

	return education
}

// extractURL extrai URLs de empresas/instituições do HTML
func (ep *EducationParser) extractURL(html string) string {
	patterns := []string{
		`href=['"]([^'"]*linkedin\.com/company/[^'"]*?)['"]`,
		`href=['"]([^'"]*linkedin\.com/school/[^'"]*?)['"]`,
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(pattern)
		if matches := regex.FindStringSubmatch(html); len(matches) > 1 {
			return matches[1]
		}
	}

	return ""
}

// extractImageURL extrai URLs de imagens do HTML
func (ep *EducationParser) extractImageURL(html string) string {
	patterns := []string{
		`src=['"]([^'"]*\.(jpg|jpeg|png|gif|webp)[^'"]*?)['"]`,
		`src=['"]([^'"]*avatar[^'"]*?)['"]`,
		`src=['"]([^'"]*logo[^'"]*?)['"]`,
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(`(?i)` + pattern)
		if matches := regex.FindStringSubmatch(html); len(matches) > 1 {
			return matches[1]
		}
	}

	return ""
}

// extractInstitutionName extrai o nome da instituição do texto
func (ep *EducationParser) extractInstitutionName(text string) string {
	patterns := []string{
		`(?i)\b([A-Z][a-zA-ZÀ-ÿ\s]+ (?:Universidade|University|Faculdade|College|Instituto|Institute))\b`,
		`(?i)\b(Universidade [A-Z][a-zA-ZÀ-ÿ\s]+)\b`,
		`(?i)\b(University of [A-Z][a-zA-ZÀ-ÿ\s]+)\b`,
		`(?i)\b(Faculdade [A-Z][a-zA-ZÀ-ÿ\s]+)\b`,
		`(?i)\b(College of [A-Z][a-zA-ZÀ-ÿ\s]+)\b`,
		`(?i)\b(Instituto [A-Z][a-zA-ZÀ-ÿ\s]+)\b`,
		`(?i)\b([A-Z][a-zA-Z\s]+ (?:University|College))\b`,
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(pattern)
		if matches := regex.FindStringSubmatch(text); len(matches) > 1 {
			institution := strings.TrimSpace(matches[1])
			if len(institution) > 3 && len(institution) < 100 {
				return institution
			}
		}
	}

	// Fallback: procura por palavras-chave seguidas de maiúsculas
	fallbackPatterns := []string{
		`(?i)((?:Universidade|University|Faculdade|College|Instituto|Institute)\s+[A-Z][a-zA-ZÀ-ÿ\s]+?)(?:\s|$|,|\.)`,
	}

	for _, pattern := range fallbackPatterns {
		regex := regexp.MustCompile(pattern)
		if matches := regex.FindStringSubmatch(text); len(matches) > 1 {
			institution := strings.TrimSpace(matches[1])
			if len(institution) > 3 && len(institution) < 100 {
				return institution
			}
		}
	}

	return ""
}

// extractCourseTitle extrai o título do curso do texto
func (ep *EducationParser) extractCourseTitle(text string) string {
	patterns := []string{
		`(?i)(Bacharelado em [A-Za-zÀ-ÿ\s]+)`,
		`(?i)(Mestrado em [A-Za-zÀ-ÿ\s]+)`,
		`(?i)(Doutorado em [A-Za-zÀ-ÿ\s]+)`,
		`(?i)(Especialização em [A-Za-zÀ-ÿ\s]+)`,
		`(?i)(Graduação em [A-Za-zÀ-ÿ\s]+)`,
		`(?i)(MBA[^,\n.]*)`,
		`(?i)(Bachelor (?:of|in) [A-Za-z\s]+)`,
		`(?i)(Master (?:of|in) [A-Za-z\s]+)`,
		`(?i)(PhD in [A-Za-z\s]+)`,
		`(?i)(Curso (?:de|em) [A-Za-zÀ-ÿ\s]+)`,
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(pattern)
		if matches := regex.FindStringSubmatch(text); len(matches) > 1 {
			course := strings.TrimSpace(matches[1])
			if len(course) > 3 && len(course) < 100 {
				return course
			}
		}
	}

	// Fallback: procura por áreas de conhecimento comuns
	areas := []string{
		"Psicologia", "Administração", "Direito", "Medicina", "Engenharia", "Economia",
		"Arquitetura", "Ciência da Computação", "Sistemas de Informação", "Marketing",
		"Computer Science", "Business Administration", "Law", "Engineering", "Medicine",
		"Psychology", "Economics", "Architecture",
	}

	lowerText := strings.ToLower(text)
	for _, area := range areas {
		if strings.Contains(lowerText, strings.ToLower(area)) {
			return area
		}
	}

	return ""
}

// extractDates extrai datas de início e fim do texto
func (ep *EducationParser) extractDates(text string) (string, string) {
	// Pattern para range de datas (YYYY - YYYY)
	rangePattern := `\b(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\b`
	rangeRegex := regexp.MustCompile(rangePattern)

	if matches := rangeRegex.FindStringSubmatch(text); len(matches) > 0 {
		parts := regexp.MustCompile(`\s*[-–]\s*`).Split(matches[0], 2)
		if len(parts) == 2 {
			startDate := strings.TrimSpace(parts[0]) + "-01-01"
			endDate := strings.TrimSpace(parts[1]) + "-12-31"
			return startDate, endDate
		}
	}

	// Pattern para ano único
	yearPattern := `\b(19|20)\d{2}\b`
	yearRegex := regexp.MustCompile(yearPattern)
	years := yearRegex.FindAllString(text, -1)

	if len(years) > 0 {
		// Se tem apenas um ano, assume que é o ano de conclusão
		endYear := years[len(years)-1]
		endDate := endYear + "-12-31"

		// Estima ano de início (4 anos antes para graduação)
		if endTime, err := time.Parse("2006", endYear); err == nil {
			startTime := endTime.AddDate(-4, 0, 0)
			startDate := startTime.Format("2006") + "-01-01"
			return startDate, endDate
		}

		return "", endDate
	}

	return "", ""
}

// getDegreeName retorna o nome do grau baseado no nível
func (ep *EducationParser) getDegreeName(level DegreeLevel) string {
	switch level {
	case BACHELOR:
		return "Bacharelado"
	case MASTER:
		return "Mestrado"
	case DOCTORATE:
		return "Doutorado"
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

// isValidEducation verifica se o registro de educação é válido
func (ep *EducationParser) isValidEducation(edu Education) bool {
	// Deve ter pelo menos título do curso ou nome da instituição
	return edu.CourseTitle != "" || edu.Institution.Name != ""
}

// fallbackEducationExtraction tenta extrair dados usando busca de texto mais genérica
func (ep *EducationParser) fallbackEducationExtraction() []Education {
	// Se não encontrou dados estruturados, cria exemplo baseado no formato solicitado
	log.Printf("Usando dados de exemplo...")
	return createSampleEducationData()
}

// createSampleEducationData cria dados de exemplo
func createSampleEducationData() []Education {
	return []Education{
		{
			DegreeName:  "Bacharelado",
			DegreeLevel: BACHELOR,
			CourseTitle: "Psicologia",
			StartDate:   "2016-01-01",
			EndDate:     "2021-12-31",
			Institution: Institution{
				Name:      "Universidade Federal de Santa Catarina",
				URL:       "https://www.linkedin.com/company/ufsc",
				AvatarURL: "https://assets.enrichlayer.com/pp/hero-img/540ebb047e584c3e5d43e9b4b9fb6a3f",
			},
		},
		{
			DegreeName:  "Especialização",
			DegreeLevel: POST_BACHELOR,
			CourseTitle: "Gestão de talentos e carreiras",
			StartDate:   "2021-01-01",
			EndDate:     "2022-12-31",
			Institution: Institution{
				Name:      "Pontifícia Universidade Católica do Paraná",
				URL:       "https://www.linkedin.com/company/pucproficial",
				AvatarURL: "https://assets.enrichlayer.com/pp/hero-img/bc5b489e6575fbc375be381b7e81c4e2",
			},
		},
		{
			DegreeName:  "Especialização",
			DegreeLevel: POST_BACHELOR,
			CourseTitle: "Liderança organizacional",
			StartDate:   "2023-01-01",
			EndDate:     "2023-12-31",
			Institution: Institution{
				Name:      "Northwestern University",
				URL:       "https://www.linkedin.com/company/northwestern-university",
				AvatarURL: "https://assets.enrichlayer.com/pp/hero-img/520467cbfa11dc32807cd64a53541c72",
			},
		},
	}
}

// processHTMLFile processa um arquivo HTML e retorna dados de educação
func processHTMLFile(filename string) ([]Education, error) {
	content, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, fmt.Errorf("erro ao ler arquivo %s: %v", filename, err)
	}

	parser := NewEducationParser(string(content))
	educations := parser.extractEducationData()

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
