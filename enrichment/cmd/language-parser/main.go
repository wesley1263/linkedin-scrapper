package main

import (
	"linkedin-enrichment/internal/parser"
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
	// Os 5 níveis do LinkedIn (en/pt), do mais alto para o mais baixo
	case strings.Contains(proficiencyText, "native or bilingual") || strings.Contains(proficiencyText, "nativo ou bilíngue"):
		return FLUENT
	case strings.Contains(proficiencyText, "full professional") || strings.Contains(proficiencyText, "profissional completa"):
		return ADVANCED
	case strings.Contains(proficiencyText, "professional working") || strings.Contains(proficiencyText, "proficiência profissional"):
		return INTERMEDIATE
	case strings.Contains(proficiencyText, "limited working") || strings.Contains(proficiencyText, "limitada"):
		return BASIC_INT
	case strings.Contains(proficiencyText, "elementary proficiency") || strings.Contains(proficiencyText, "elementar"):
		return BASIC

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
	languageName = regexp.MustCompile(`[^\p{L}\s-]`).ReplaceAllString(languageName, "")
	languageName = strings.Join(strings.Fields(languageName), " ")

	// Procura no mapa de códigos
	if code, exists := languageCodeMap[languageName]; exists {
		return code
	}

	// Procura por palavras parciais (ignora códigos curtos como "de"/"no", que casam em qualquer nome)
	for name, code := range languageCodeMap {
		if len([]rune(name)) < 4 {
			continue
		}
		if strings.Contains(languageName, name) {
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

var (
	itemKeyRe = regexp.MustCompile(`componentkey="entity-collection-item`)
	pRe       = regexp.MustCompile(`(?s)<p\b[^>]*>(.*?)</p>`)
	tagRe     = regexp.MustCompile(`<[^>]+>`)
	spaceRe   = regexp.MustCompile(`\s+`)
)

// extractStructuredLanguages extrai os idiomas dos itens da lista
// (div com componentkey="entity-collection-item-..."), cujos <p> são [idioma, nível?]
func (lp *LanguageParser) extractStructuredLanguages() []Language {
	var languages []Language

	content := lp.htmlContent
	if i := strings.Index(content, `data-testid="profile_LanguageDetails`); i >= 0 {
		content = content[i:]
	}

	lastEnd := 0
	for _, loc := range itemKeyRe.FindAllStringIndex(content, -1) {
		start := strings.LastIndex(content[:loc[0]], "<div")
		if start < lastEnd {
			continue // item aninhado em outro já extraído
		}
		block := parser.BalancedBlock(content, start, "div")
		lastEnd = start + len(block)

		var texts []string
		for _, match := range pRe.FindAllStringSubmatch(block, -1) {
			if text := parser.CleanText(match[1]); text != "" {
				texts = append(texts, text)
			}
		}
		if len(texts) == 0 {
			continue
		}

		lang := Language{
			Language:     getLanguageCode(texts[0]),
			LanguageText: texts[0],
			Proficiency:  EMPTY,
		}
		if len(texts) > 1 {
			lang.Proficiency = normalizeProficiencyLevel(texts[1])
		}
		if lp.isValidLanguage(lang) {
			languages = append(languages, lang)
		}
	}

	return languages
}

func (lp *LanguageParser) isValidLanguage(lang Language) bool {
	return lang.LanguageText != "" && len([]rune(lang.LanguageText)) <= 50
}

func main() {
	os.Exit(parser.RunSection(parser.Spec{
		Section:       "languages",
		DefaultOutput: "languages.json",
		AllowEmpty:    true,
		Parse: func(htmlContent string) (any, int) {
			languages := NewLanguageParser(htmlContent).extractLanguageData()
			if languages == nil {
				languages = []Language{}
			}
			return languages, len(languages)
		},
	}, os.Args[1:], os.Stdout, os.Stderr))
}
