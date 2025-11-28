package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"regexp"
	"strings"
)

// ProficiencyLevel enum para os níveis de proficiência em idiomas
type ProficiencyLevel string

const (
	BASIC        ProficiencyLevel = "BASIC"
	BASIC_INT    ProficiencyLevel = "BASIC_INT"
	INTERMEDIATE ProficiencyLevel = "INTERMEDIATE"
	ADVANCED     ProficiencyLevel = "ADVANCED"
	FLUENT       ProficiencyLevel = "FLUENT"
	EMPTY        ProficiencyLevel = "EMPTY"
)

// Language representa um idioma e seu nível de proficiência
type Language struct {
	Language     string           `json:"language"`
	LanguageText string           `json:"language_text"`
	Proficiency  ProficiencyLevel `json:"proficiency"`
}

// LanguageParser contém os métodos para fazer parse de HTML de idiomas
type LanguageParser struct {
	htmlContent string
}

// NewLanguageParser cria uma nova instância do parser
func NewLanguageParser(htmlContent string) *LanguageParser {
	return &LanguageParser{htmlContent: htmlContent}
}

// languageCodeMap mapeia nomes de idiomas para códigos ISO de 3 letras
var languageCodeMap = map[string]string{
	// Português
	"português":  "POR",
	"portuguese": "POR",
	"portugues":  "POR",
	"pt":         "POR",
	"pt-br":      "POR",
	"pt-pt":      "POR",

	// Inglês
	"inglês":  "ENG",
	"ingles":  "ENG",
	"english": "ENG",
	"en":      "ENG",
	"en-us":   "ENG",
	"en-gb":   "ENG",

	// Espanhol
	"espanhol":   "SPA",
	"spanish":    "SPA",
	"español":    "SPA",
	"es":         "SPA",
	"es-es":      "SPA",
	"es-mx":      "SPA",
	"castelhano": "SPA",
	"castellano": "SPA",

	// Francês
	"francês":  "FRA",
	"frances":  "FRA",
	"french":   "FRA",
	"français": "FRA",
	"fr":       "FRA",
	"fr-fr":    "FRA",

	// Alemão
	"alemão":  "GER",
	"alemao":  "GER",
	"german":  "GER",
	"deutsch": "GER",
	"de":      "GER",

	// Italiano
	"italiano": "ITA",
	"italian":  "ITA",
	"it":       "ITA",

	// Japonês
	"japonês":  "JPN",
	"japones":  "JPN",
	"japanese": "JPN",
	"日本語":      "JPN",
	"ja":       "JPN",

	// Chinês
	"chinês":   "CHI",
	"chines":   "CHI",
	"chinese":  "CHI",
	"mandarin": "CHI",
	"mandarim": "CHI",
	"中文":       "CHI",
	"zh":       "CHI",
	"zh-cn":    "CHI",
	"zh-tw":    "CHI",

	// Russo
	"russo":   "RUS",
	"russian": "RUS",
	"русский": "RUS",
	"ru":      "RUS",

	// Árabe
	"árabe":   "ARA",
	"arabe":   "ARA",
	"arabic":  "ARA",
	"العربية": "ARA",
	"ar":      "ARA",

	// Holandês
	"holandês":   "DUT",
	"holandes":   "DUT",
	"dutch":      "DUT",
	"nederlands": "DUT",
	"nl":         "DUT",

	// Sueco
	"sueco":   "SWE",
	"swedish": "SWE",
	"svenska": "SWE",
	"sv":      "SWE",

	// Norueguês
	"norueguês": "NOR",
	"noruegues": "NOR",
	"norwegian": "NOR",
	"norsk":     "NOR",
	"no":        "NOR",

	// Dinamarquês
	"dinamarquês": "DAN",
	"dinamarques": "DAN",
	"danish":      "DAN",
	"dansk":       "DAN",
	"da":          "DAN",

	// Coreano
	"coreano": "KOR",
	"korean":  "KOR",
	"한국어":     "KOR",
	"ko":      "KOR",

	// Hindi
	"hindi":  "HIN",
	"हिन्दी": "HIN",
	"hi":     "HIN",
}

// normalizeProficiencyLevel converte texto de proficiência para enum ProficiencyLevel
func normalizeProficiencyLevel(proficiencyText string) ProficiencyLevel {
	proficiencyText = strings.ToLower(strings.TrimSpace(proficiencyText))

	// Mapeamento de palavras-chave para níveis de proficiência
	switch {
	case strings.Contains(proficiencyText, "fluente") || strings.Contains(proficiencyText, "fluent") ||
		strings.Contains(proficiencyText, "nativo") || strings.Contains(proficiencyText, "native") ||
		strings.Contains(proficiencyText, "materno") || strings.Contains(proficiencyText, "mother") ||
		strings.Contains(proficiencyText, "língua materna"):
		return FLUENT
	case strings.Contains(proficiencyText, "avançado") || strings.Contains(proficiencyText, "advanced") ||
		strings.Contains(proficiencyText, "proficiente") || strings.Contains(proficiencyText, "proficient") ||
		strings.Contains(proficiencyText, "superior") || strings.Contains(proficiencyText, "upper"):
		return ADVANCED
	case strings.Contains(proficiencyText, "intermediário") || strings.Contains(proficiencyText, "intermediate") ||
		strings.Contains(proficiencyText, "médio") || strings.Contains(proficiencyText, "medio") ||
		strings.Contains(proficiencyText, "middle"):
		return INTERMEDIATE
	case strings.Contains(proficiencyText, "básico intermediário") || strings.Contains(proficiencyText, "basic intermediate") ||
		strings.Contains(proficiencyText, "pré-intermediário") || strings.Contains(proficiencyText, "pre-intermediate") ||
		strings.Contains(proficiencyText, "elementary") || strings.Contains(proficiencyText, "elementar"):
		return BASIC_INT
	case strings.Contains(proficiencyText, "básico") || strings.Contains(proficiencyText, "basic") ||
		strings.Contains(proficiencyText, "iniciante") || strings.Contains(proficiencyText, "beginner") ||
		strings.Contains(proficiencyText, "elementar") || strings.Contains(proficiencyText, "elementary"):
		return BASIC
	default:
		return EMPTY
	}
}

// getLanguageCode converte nome do idioma para código de 3 letras
func getLanguageCode(languageName string) string {
	languageName = strings.ToLower(strings.TrimSpace(languageName))

	// Remove caracteres especiais e espaços extras
	languageName = regexp.MustCompile(`[^\w\s-]`).ReplaceAllString(languageName, "")
	languageName = strings.Join(strings.Fields(languageName), " ")

	// Procura no mapa de códigos
	if code, exists := languageCodeMap[languageName]; exists {
		return code
	}

	// Procura por palavras parciais
	for name, code := range languageCodeMap {
		if strings.Contains(languageName, name) || strings.Contains(name, languageName) {
			return code
		}
	}

	// Se não encontrou, retorna as 3 primeiras letras em maiúscula
	if len(languageName) >= 3 {
		return strings.ToUpper(languageName[:3])
	}

	return "UNK" // Unknown
}

// extractLanguageData extrai dados de idiomas do HTML
func (lp *LanguageParser) extractLanguageData() []Language {
	// Primeiro tenta extrair usando estrutura de itens de idiomas
	structuredLanguages := lp.extractStructuredLanguages()
	if len(structuredLanguages) > 0 {
		return structuredLanguages
	}

	// Se não encontrou estruturada, usa busca mais genérica
	return nil
}

// extractStructuredLanguages extrai dados usando estruturas HTML comuns do LinkedIn
func (lp *LanguageParser) extractStructuredLanguages() []Language {
	var languages []Language

	// Patterns para identificar blocos de idiomas
	patterns := []string{
		`<div[^>]*class="[^"]*language[^"]*"[^>]*>(.*?)</div>`,
		`<div[^>]*data-section="language"[^>]*>(.*?)</div>`,
		`<li[^>]*class="[^"]*language[^"]*"[^>]*>(.*?)</li>`,
		`<section[^>]*id="[^"]*language[^"]*"[^>]*>(.*?)</section>`,
		`<div[^>]*class="[^"]*skill[^"]*"[^>]*>(.*?)</div>`,
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(`(?s)` + pattern)
		matches := regex.FindAllStringSubmatch(lp.htmlContent, -1)

		for _, match := range matches {
			if len(match) > 1 {
				// Processa sub-itens dentro da seção
				itemLanguages := lp.parseLanguageSection(match[1])
				languages = append(languages, itemLanguages...)
			}
		}

		if len(languages) > 0 {
			break
		}
	}

	return languages
}

// parseLanguageSection processa uma seção de idiomas e extrai itens individuais
func (lp *LanguageParser) parseLanguageSection(sectionHTML string) []Language {
	var languages []Language

	// Patterns para itens individuais de idiomas dentro da seção
	itemPatterns := []string{
		`<div[^>]*class="[^"]*language-item[^"]*"[^>]*>(.*?)</div>`,
		`<li[^>]*>(.*?)</li>`,
		`<div[^>]*>(.*?)</div>`,
	}

	for _, pattern := range itemPatterns {
		regex := regexp.MustCompile(`(?s)` + pattern)
		matches := regex.FindAllStringSubmatch(sectionHTML, -1)

		for _, match := range matches {
			if len(match) > 1 {
				language := lp.parseLanguageItem(match[1])
				if lp.isValidLanguage(language) {
					languages = append(languages, language)
				}
			}
		}

		if len(languages) > 0 {
			break
		}
	}

	// Se não encontrou itens estruturados, processa a seção inteira como um item
	if len(languages) == 0 {
		language := lp.parseLanguageItem(sectionHTML)
		if lp.isValidLanguage(language) {
			languages = append(languages, language)
		}
	}

	return languages
}

// parseLanguageItem extrai dados de um item de idioma específico
func (lp *LanguageParser) parseLanguageItem(itemHTML string) Language {
	language := Language{}

	// Remove tags HTML e normaliza texto
	textRegex := regexp.MustCompile(`<[^>]*>`)
	text := textRegex.ReplaceAllString(itemHTML, " ")
	text = strings.Join(strings.Fields(text), " ")

	// Extrai nome do idioma e nível de proficiência
	language.LanguageText = lp.extractLanguageName(text)
	language.Language = getLanguageCode(language.LanguageText)
	language.Proficiency = lp.extractProficiencyLevel(text)

	return language
}

// extractLanguageName extrai o nome do idioma do texto
func (lp *LanguageParser) extractLanguageName(text string) string {
	// Lista de idiomas comuns para identificar
	commonLanguages := []string{
		"português", "portuguese", "inglês", "english", "espanhol", "spanish", "español",
		"francês", "french", "français", "alemão", "german", "deutsch", "italiano", "italian",
		"japonês", "japanese", "chinês", "chinese", "mandarin", "mandarim", "russo", "russian",
		"árabe", "arabic", "holandês", "dutch", "coreano", "korean", "hindi",
		"sueco", "swedish", "norueguês", "norwegian", "dinamarquês", "danish",
	}

	lowerText := strings.ToLower(text)

	// Procura por idiomas conhecidos
	for _, lang := range commonLanguages {
		if strings.Contains(lowerText, strings.ToLower(lang)) {
			return lang
		}
	}

	// Pattern para capturar possíveis nomes de idiomas (palavras capitalizadas)
	patterns := []string{
		`\b([A-ZÀ-Ÿ][a-zà-ÿ]{3,15})\b`, // Palavra capitalizada de 4-16 caracteres
		`\b([A-Za-zÀ-ÿ]{4,15}ês)\b`,    // Palavras terminadas em "ês" (português, inglês, etc.)
		`\b([A-Za-zÀ-ÿ]{4,15}an)\b`,    // Palavras terminadas em "an" (german, etc.)
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(pattern)
		matches := regex.FindAllStringSubmatch(text, -1)

		for _, match := range matches {
			if len(match) > 1 {
				candidate := strings.TrimSpace(match[1])
				if len(candidate) >= 4 && len(candidate) <= 15 && !lp.isCommonWord(candidate) && !lp.isProficiencyWord(candidate) {
					return candidate
				}
			}
		}
	}

	// Como fallback, pega a primeira palavra significativa
	words := strings.Fields(text)
	for _, word := range words {
		if len(word) >= 4 && len(word) <= 15 && !lp.isCommonWord(word) && !lp.isProficiencyWord(word) {
			return word
		}
	}

	return ""
}

// isProficiencyWord verifica se uma palavra está relacionada a níveis de proficiência
func (lp *LanguageParser) isProficiencyWord(word string) bool {
	proficiencyWords := []string{
		"proficiency", "proficiência", "level", "nível", "skill", "habilidade",
		"fluent", "fluente", "advanced", "avançado", "intermediate", "intermediário",
		"basic", "básico", "beginner", "iniciante", "native", "nativo", "elementary",
		"elementar", "conversational", "conversação", "working", "professional",
		"profissional", "limited", "limitado", "functional", "funcional",
	}

	lowerWord := strings.ToLower(word)
	for _, profWord := range proficiencyWords {
		if lowerWord == profWord {
			return true
		}
	}

	return false
}

// extractProficiencyLevel extrai o nível de proficiência do texto
func (lp *LanguageParser) extractProficiencyLevel(text string) ProficiencyLevel {
	// Palavras-chave para níveis de proficiência em diferentes idiomas
	proficiencyKeywords := []string{
		"fluente", "fluent", "nativo", "native", "materno", "mother tongue",
		"avançado", "advanced", "proficiente", "proficient", "superior", "upper",
		"intermediário", "intermediate", "médio", "medium", "middle",
		"básico intermediário", "basic intermediate", "pré-intermediário", "pre-intermediate",
		"elementary", "elementar", "básico", "basic", "iniciante", "beginner",
	}

	lowerText := strings.ToLower(text)

	// Procura por palavras-chave de proficiência
	for _, keyword := range proficiencyKeywords {
		if strings.Contains(lowerText, keyword) {
			return normalizeProficiencyLevel(keyword)
		}
	}

	// Procura por patterns de nível
	patterns := []string{
		`(?i)(fluent|fluente|nativo|native)`,
		`(?i)(advanced|avançado|proficient|proficiente)`,
		`(?i)(intermediate|intermediário|médio)`,
		`(?i)(basic|básico|beginner|iniciante)`,
	}

	for _, pattern := range patterns {
		regex := regexp.MustCompile(pattern)
		if matches := regex.FindStringSubmatch(text); len(matches) > 0 {
			return normalizeProficiencyLevel(matches[0])
		}
	}

	return EMPTY
}

// isCommonWord verifica se uma palavra é muito comum para ser um nome de idioma
func (lp *LanguageParser) isCommonWord(word string) bool {
	commonWords := []string{
		"the", "and", "for", "with", "from", "about", "into", "through", "during",
		"before", "after", "above", "below", "between", "among", "around",
		"sobre", "para", "com", "por", "em", "de", "do", "da", "dos", "das",
		"que", "como", "mais", "menos", "muito", "pouco", "bem", "mal",
		"level", "skill", "language", "idioma", "língua", "proficiency", "proficiência",
		"fluent", "fluente", "advanced", "avançado", "intermediate", "intermediário",
		"basic", "básico", "beginner", "iniciante", "native", "nativo", "elementary",
		"elementar", "upper", "superior", "lower", "inferior", "medium", "médio",
		"conversational", "conversação", "working", "professional", "profissional",
		"limited", "limitado", "functional", "funcional", "business", "negócios",
	}

	lowerWord := strings.ToLower(word)
	for _, common := range commonWords {
		if lowerWord == common {
			return true
		}
	}

	// Verifica se a palavra é muito curta (provavelmente não é um idioma)
	if len(lowerWord) <= 2 {
		return true
	}

	return false
}

// isValidLanguage verifica se o registro de idioma é válido
func (lp *LanguageParser) isValidLanguage(lang Language) bool {
	// Deve ter pelo menos o nome do idioma
	return lang.LanguageText != "" && len(lang.LanguageText) >= 3
}

// fallbackLanguageExtraction tenta extrair dados usando busca de texto mais genérica
func (lp *LanguageParser) fallbackLanguageExtraction() []Language {
	// Se não encontrou dados estruturados, cria exemplo baseado no formato solicitado
	log.Printf("Usando dados de exemplo de idiomas...")
	return createSampleLanguageData()
}

// createSampleLanguageData cria dados de exemplo
func createSampleLanguageData() []Language {
	return []Language{
		{
			Language:     "ENG",
			LanguageText: "English",
			Proficiency:  ADVANCED,
		},
		{
			Language:     "POR",
			LanguageText: "Português",
			Proficiency:  FLUENT,
		},
		{
			Language:     "FRA",
			LanguageText: "Francês",
			Proficiency:  BASIC_INT,
		},
		{
			Language:     "SPA",
			LanguageText: "Espanhol",
			Proficiency:  BASIC_INT,
		},
	}
}

// processHTMLFile processa um arquivo HTML e retorna dados de idiomas
func processHTMLFile(filename string) ([]Language, error) {
	content, err := ioutil.ReadFile(filename)
	if err != nil {
		return nil, fmt.Errorf("erro ao ler arquivo %s: %v", filename, err)
	}

	parser := NewLanguageParser(string(content))
	languages := parser.extractLanguageData()

	if len(languages) == 0 {
		return []Language{}, nil
	}

	return languages, nil
}

// saveToJSON salva os dados em formato JSON
func saveToJSON(languages []Language, filename string) error {
	jsonData, err := json.MarshalIndent(languages, "", "  ")
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
	outputFile := "languages.json"

	if len(os.Args) >= 3 {
		outputFile = os.Args[2]
	}

	fmt.Printf("Processando arquivo: %s\n", inputFile)

	languages, err := processHTMLFile(inputFile)
	if err != nil {
		log.Fatalf("Erro ao processar arquivo: %v", err)
	}

	fmt.Printf("Encontrados %d idiomas\n", len(languages))

	err = saveToJSON(languages, outputFile)
	if err != nil {
		log.Fatalf("Erro ao salvar JSON: %v", err)
	}

	fmt.Printf("Dados salvos em: %s\n", outputFile)

}
