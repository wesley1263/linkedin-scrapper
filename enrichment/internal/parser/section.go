package parser

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"time"
)

// Status de uma seção após o parsing (ADR-0006)
type Status string

const (
	StatusOK     Status = "ok"     // extraiu itens
	StatusEmpty  Status = "empty"  // o perfil não tem a seção ("Nothing to see for now")
	StatusFailed Status = "failed" // esperava itens e não extraiu nenhum, ou erro de parsing
)

// Códigos de saída dos binários: ok e empty saem com 0; o Python lê a linha de status no stdout
const (
	ExitOK     = 0
	ExitIO     = 1 // arquivo de entrada/saída ou argumentos
	ExitFailed = 3 // seção com status failed
)

// emptyMarkers é o texto que o LinkedIn mostra numa seção de detalhe sem itens
var emptyMarkers = []string{"Nothing to see for now", "Nada para ver por enquanto"}

// Result é a linha JSON que cada binário imprime no stdout ao terminar
type Result struct {
	Section    string `json:"section"`
	Status     Status `json:"status"`
	Items      int    `json:"items"`
	DurationMS int64  `json:"duration_ms"`
	Error      string `json:"error,omitempty"`
}

// Classify decide o status: com itens é ok; sem itens, empty só se a página tem a marca de seção vazia
func Classify(htmlContent string, items int, allowEmpty bool) Status {
	if items > 0 {
		return StatusOK
	}
	if allowEmpty {
		for _, marker := range emptyMarkers {
			if strings.Contains(htmlContent, marker) {
				return StatusEmpty
			}
		}
	}
	return StatusFailed
}

// Spec descreve um parser de seção para RunSection
type Spec struct {
	Section       string
	DefaultOutput string
	// AllowEmpty: a seção pode legitimamente não ter itens (detalhes). O perfil nunca é "vazio".
	AllowEmpty bool
	// Parse devolve os dados a serializar (slice não-nulo, para sair "[]") e quantos itens extraiu
	Parse func(htmlContent string) (data any, items int)
}

// RunSection implementa o main de um parser: lê <input.html> [output.json], grava o JSON, imprime a
// linha de status em stdout e devolve o código de saída. Erros e diagnósticos vão para stderr.
func RunSection(spec Spec, args []string, stdout, stderr io.Writer) int {
	if len(args) < 1 {
		fmt.Fprintf(stderr, "Uso: %s-parser <arquivo.html> [output.json]\n", spec.Section)
		return ExitIO
	}
	input, output := args[0], spec.DefaultOutput
	if len(args) >= 2 {
		output = args[1]
	}

	start := time.Now()
	res := Result{Section: spec.Section}
	finish := func(code int) int {
		res.DurationMS = time.Since(start).Milliseconds()
		line, _ := json.Marshal(res)
		fmt.Fprintln(stdout, string(line))
		return code
	}

	content, err := os.ReadFile(input)
	if err != nil {
		res.Status, res.Error = StatusFailed, fmt.Sprintf("erro ao ler %s: %v", input, err)
		fmt.Fprintln(stderr, res.Error)
		return finish(ExitIO)
	}
	htmlContent := string(content)

	data, items, err := safeParse(spec.Parse, htmlContent)
	if err != nil {
		res.Status, res.Error = StatusFailed, err.Error()
		fmt.Fprintln(stderr, res.Error)
		return finish(ExitFailed)
	}
	res.Items = items

	jsonData, err := json.MarshalIndent(data, "", "  ")
	if err == nil {
		err = os.WriteFile(output, jsonData, 0o644)
	}
	if err != nil {
		res.Status, res.Error = StatusFailed, fmt.Sprintf("erro ao gravar %s: %v", output, err)
		fmt.Fprintln(stderr, res.Error)
		return finish(ExitIO)
	}

	res.Status = Classify(htmlContent, items, spec.AllowEmpty)
	if res.Status == StatusFailed {
		res.Error = "nenhum item extraído e a página não indica seção vazia (possível mudança de layout)"
		fmt.Fprintln(stderr, res.Error)
		return finish(ExitFailed)
	}
	return finish(ExitOK)
}

// safeParse converte um panic do parser em erro, para o status failed sair no stdout em vez de um stack trace
func safeParse(parse func(string) (any, int), htmlContent string) (data any, items int, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic no parser: %v", r)
		}
	}()
	data, items = parse(htmlContent)
	return
}
