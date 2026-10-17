package main

import (
	"fmt"
	"html"
	"linkedin-enrichment/internal/parser"
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

// Marcadores do layout atual (SDUI) da página de perfil
var (
	// <div componentkey="ProfileVerificationTriggerRef-<slug>">...<h2>Nome</h2>: ancora o card do topo e dá o slug do perfil
	nameBlockRe = regexp.MustCompile(`(?s)componentkey="ProfileVerificationTriggerRef-([^"]+)".*?<h2\b[^>]*>(.*?)</h2>`)
	// <p>Cidade, Estado, País</p><p>·</p><p><a href=".../overlay/contact-info/">: localização, sempre antes do "Contact info"
	locationRe  = regexp.MustCompile(`<p\b[^>]*>([^<]+)</p>\s*<p\b[^>]*>·</p>\s*<p\b[^>]*><a\b[^>]*contact-info`)
	paragraphRe = regexp.MustCompile(`(?s)<p\b[^>]*>(.*?)</p>`)
	// ícones company-accent/school-accent identificam a empresa e a universidade atuais; o <p> seguinte tem o nome
	companyRe    = regexp.MustCompile(`(?s)id="company-accent-\d+".*?<p\b[^>]*>(.*?)</p>`)
	universityRe = regexp.MustCompile(`(?s)id="school-accent-\d+".*?<p\b[^>]*>(.*?)</p>`)
	moreSuffixRe = regexp.MustCompile(`\s*\+\s*\d+\s+(?:more|mais)$`)
	titleRe      = regexp.MustCompile(`<title>([^|<]+)\s*\|\s*LinkedIn</title>`)
	notifCountRe = regexp.MustCompile(`^\(\d+\+?\)\s*`)
	// avatar: profile-displayphoto-scale_200_200 / -crop_800_800 (a URL termina em aspas ou espaço, pois vem em srcset)
	avatarRe    = regexp.MustCompile(`https://[^"\s]*profile-displayphoto-[a-z]+_(\d+)_\d+[^"\s]*`)
	aboutTextRe = regexp.MustCompile(`(?s)data-testid="expandable-text-box"[^>]*>(.*?)</span>`)
)

func parseProfile(htmlContent string) Profile {
	profile := Profile{
		EmailAddresses: []string{},
		Phones:         []string{},
	}

	// Só a região do perfil em si (card do topo + About); o resto da página tem atividade e outras pessoas
	region := profileRegion(htmlContent)
	card := topCard(region)

	profile.FirstName, profile.LastName = extractName(htmlContent, region)
	profile.LinkedInURL = extractLinkedInURL(region)
	profile.Address = extractAddress(card)
	profile.AvatarURL = extractAvatarURL(card)
	profile.Headline = extractHeadline(card)
	profile.Company = firstGroup(companyRe, card, moreSuffixRe)
	profile.University = firstGroup(universityRe, card, moreSuffixRe)
	profile.Description = extractDescription(region)
	profile.EmailAddresses = extractEmails(region)
	profile.Phones = extractPhones(region)

	return profile
}

// profileRegion vai do início do <main> até o fim da seção About (ou, sem About, até logo após o card do topo)
func profileRegion(htmlContent string) string {
	start := strings.Index(htmlContent, "<main")
	if start < 0 {
		start = 0
	}
	rest := htmlContent[start:]

	if i := strings.Index(rest, ">About</h2>"); i >= 0 {
		if sec := strings.LastIndex(rest[:i], "<section"); sec >= 0 {
			return rest[:sec] + parser.BalancedBlock(rest, sec, "section")
		}
	}
	end := len(rest)
	if i := strings.Index(rest, "contact-info"); i >= 0 && i+4000 < end {
		end = i + 4000
	}
	return rest[:end]
}

// topCard devolve o trecho do início da região até o link "Contact info" (e os ícones de empresa/universidade que o seguem)
func topCard(region string) string {
	end := len(region)
	if i := strings.Index(region, "contact-info"); i >= 0 {
		end = i
		// Empresa/universidade vêm logo depois do contact info; para antes do bloco de conexões/botões
		if j := strings.Index(region[i:], "connections"); j >= 0 {
			end = i + j
		} else if i+4000 < len(region) {
			end = i + 4000
		}
	}
	return region[:end]
}

func extractName(htmlContent, region string) (firstName, lastName string) {
	fullName := ""
	if m := nameBlockRe.FindStringSubmatch(region); m != nil {
		fullName = parser.CleanText(m[2])
	} else if m := titleRe.FindStringSubmatch(htmlContent); m != nil {
		// <title>(26) Nome Sobrenome | LinkedIn</title>: remove o contador de notificações
		fullName = notifCountRe.ReplaceAllString(strings.TrimSpace(m[1]), "")
	}
	parts := strings.SplitN(fullName, " ", 2)
	firstName = parts[0]
	if len(parts) > 1 {
		lastName = parts[1]
	}
	return
}

func extractLinkedInURL(region string) string {
	if m := nameBlockRe.FindStringSubmatch(region); m != nil {
		return "https://www.linkedin.com/in/" + decodeURL(m[1])
	}
	return ""
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

// extractAddress lê "Cidade, Estado, País"; Locality guarda o país e Region o estado (contrato do README)
func extractAddress(card string) Address {
	addr := Address{}
	m := locationRe.FindStringSubmatch(card)
	if m == nil {
		return addr
	}
	location := parser.CleanText(m[1])
	parts := strings.Split(location, ",")
	if len(parts) < 2 {
		return addr
	}
	addr.Name = location
	addr.Locality = strings.TrimSpace(parts[len(parts)-1])
	if len(parts) >= 3 {
		addr.Region = strings.TrimSpace(parts[1])
	}
	return addr
}

// extractAvatarURL escolhe a maior resolução entre as URLs de foto de perfil (src e srcset)
func extractAvatarURL(card string) string {
	bestURL, bestSize := "", 0
	for _, m := range avatarRe.FindAllStringSubmatch(card, -1) {
		size := 0
		fmt.Sscanf(m[1], "%d", &size)
		if size > bestSize {
			bestSize, bestURL = size, html.UnescapeString(m[0])
		}
	}
	return bestURL
}

// extractHeadline: primeiro <p> após o nome que não é o grau de conexão ("· 3rd")
func extractHeadline(card string) string {
	loc := nameBlockRe.FindStringIndex(card)
	if loc == nil {
		return ""
	}
	for _, m := range paragraphRe.FindAllStringSubmatch(card[loc[1]:], -1) {
		text := parser.CleanText(m[1])
		if text != "" && !strings.HasPrefix(text, "·") {
			return text
		}
	}
	return ""
}

// firstGroup devolve o texto limpo do primeiro grupo de re em s, sem o sufixo "+ N more"
func firstGroup(re *regexp.Regexp, s string, suffix *regexp.Regexp) string {
	if m := re.FindStringSubmatch(s); m != nil {
		return suffix.ReplaceAllString(parser.CleanText(m[1]), "")
	}
	return ""
}

// extractDescription devolve o texto expandido da seção About
func extractDescription(region string) string {
	i := strings.Index(region, ">About</h2>")
	if i < 0 {
		return ""
	}
	if m := aboutTextRe.FindStringSubmatch(region[i:]); m != nil {
		return parser.CleanText(m[1])
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

func main() {
	os.Exit(parser.RunSection(parser.Spec{
		Section:       "profile",
		DefaultOutput: "profile.json",
		// O perfil nunca é "vazio": sem nome e URL o layout mudou ou a página não é um perfil
		AllowEmpty: false,
		Parse: func(htmlContent string) (any, int) {
			profile := parseProfile(htmlContent)
			items := 0
			if profile.FirstName != "" && profile.LinkedInURL != "" {
				items = 1
			}
			return profile, items
		},
	}, os.Args[1:], os.Stdout, os.Stderr))
}
