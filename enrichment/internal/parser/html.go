// Package parser reúne os helpers compartilhados pelos parsers de HTML do LinkedIn.
package parser

import (
	"html"
	"regexp"
	"strings"
)

var (
	tagRe   = regexp.MustCompile(`<[^>]+>`)
	spaceRe = regexp.MustCompile(`\s+`)
)

// BalancedBlock retorna o elemento <tag> que começa em start, até a tag de fechamento correspondente
func BalancedBlock(s string, start int, tag string) string {
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

// CleanText remove tags, decodifica entidades, tira zero-width spaces e colapsa espaços
func CleanText(s string) string {
	s = html.UnescapeString(tagRe.ReplaceAllString(s, " "))
	s = strings.ReplaceAll(s, "​", "")
	return strings.TrimSpace(spaceRe.ReplaceAllString(s, " "))
}
