package parser

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestClassify(t *testing.T) {
	cases := []struct {
		name       string
		html       string
		items      int
		allowEmpty bool
		want       Status
	}{
		{"com itens", "<p>x</p>", 3, true, StatusOK},
		{"vazio em inglês", "<p>Nothing to see for now</p>", 0, true, StatusEmpty},
		{"vazio em português", "<p>Nada para ver por enquanto</p>", 0, true, StatusEmpty},
		{"sem itens e sem marca é falha", "<p>layout novo</p>", 0, true, StatusFailed},
		{"itens vencem a marca", "<p>Nothing to see for now</p>", 2, true, StatusOK},
		{"perfil não pode ser vazio", "<p>Nothing to see for now</p>", 0, false, StatusFailed},
	}
	for _, c := range cases {
		if got := Classify(c.html, c.items, c.allowEmpty); got != c.want {
			t.Errorf("%s: Classify = %s, esperado %s", c.name, got, c.want)
		}
	}
}

func run(t *testing.T, spec Spec, html string) (code int, res Result, out string) {
	t.Helper()
	dir := t.TempDir()
	in := filepath.Join(dir, "in.html")
	out = filepath.Join(dir, "out.json")
	if err := os.WriteFile(in, []byte(html), 0o644); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code = RunSection(spec, []string{in, out}, &stdout, &stderr)
	if err := json.Unmarshal(stdout.Bytes(), &res); err != nil {
		t.Fatalf("stdout deveria ser uma linha JSON, obteve %q: %v", stdout.String(), err)
	}
	return code, res, out
}

func itemsSpec(allowEmpty bool, n int) Spec {
	return Spec{Section: "teste", AllowEmpty: allowEmpty, Parse: func(string) (any, int) {
		return make([]int, n), n
	}}
}

func TestRunSectionStatuses(t *testing.T) {
	code, res, out := run(t, itemsSpec(true, 2), "<p>x</p>")
	if code != ExitOK || res.Status != StatusOK || res.Items != 2 {
		t.Errorf("ok: code=%d res=%+v", code, res)
	}
	if _, err := os.Stat(out); err != nil {
		t.Errorf("JSON de dados deveria ser gravado: %v", err)
	}

	code, res, _ = run(t, itemsSpec(true, 0), "Nothing to see for now")
	if code != ExitOK || res.Status != StatusEmpty {
		t.Errorf("empty: code=%d res=%+v", code, res)
	}

	code, res, _ = run(t, itemsSpec(true, 0), "<p>layout desconhecido</p>")
	if code != ExitFailed || res.Status != StatusFailed || res.Error == "" {
		t.Errorf("failed: code=%d res=%+v", code, res)
	}
}

func TestRunSectionPanicBecomesFailed(t *testing.T) {
	spec := Spec{Section: "teste", Parse: func(string) (any, int) { panic("boom") }}
	code, res, _ := run(t, spec, "<p>x</p>")
	if code != ExitFailed || res.Status != StatusFailed || !strings.Contains(res.Error, "boom") {
		t.Errorf("panic: code=%d res=%+v", code, res)
	}
}

func TestRunSectionMissingInput(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := RunSection(itemsSpec(true, 1), []string{"/nao/existe.html"}, &stdout, &stderr)
	var res Result
	if err := json.Unmarshal(stdout.Bytes(), &res); err != nil {
		t.Fatalf("stdout deveria ter a linha de status mesmo com erro de I/O: %v", err)
	}
	if code != ExitIO || res.Status != StatusFailed {
		t.Errorf("code=%d res=%+v", code, res)
	}
}
