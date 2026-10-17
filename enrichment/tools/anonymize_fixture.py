#!/usr/bin/env python3
"""Gera um fixture anonimizado a partir de um HTML coletado em output/<username>/<secao>.html.

Uso:
    anonymize_fixture.py <input.html> <output.html> --name "Nome Completo" [--sub "real=>falso" ...]

Recorta só a lista de itens (o resto da página tem anúncios e outras pessoas) e troca nomes, slugs, URLs de
imagem e de empresa/escola, nomes de empresa/instituição (lidos de `alt="X logo"`) e textos livres por
placeholders, preservando a estrutura de markup que os parsers usam. O original nunca vai para o git.
"""
import argparse
import re
import sys

ITEM_KEY = "componentkey=\"entity-collection-item"
SECTION_MARKER = 'data-testid="profile_'


def balanced_block(s, start, tag):
    depth = 0
    for m in re.finditer(r"<%s\b|</%s>" % (tag, tag), s[start:]):
        depth += -1 if s[start + m.start() + 1] == "/" else 1
        if depth == 0:
            return s[start:start + m.end()]
    return s[start:]


def slice_profile(s):
    """Do <main> até o fim da seção About: card do topo + sobre (o resto tem atividade e outras pessoas)."""
    start = s.find("<main")
    about = s.find(">About</h2>")
    if start < 0 or about < 0:
        sys.exit("<main> ou seção About não encontrados")
    sec = s.rfind("<section", 0, about)
    return s[start:sec] + balanced_block(s, sec, "section")


def slice_items(s):
    """Do início do container da seção (ou do primeiro item) até o fim do último item."""
    first = s.find(ITEM_KEY)
    if first < 0:
        sys.exit("nenhum item entity-collection-item encontrado")
    start = s.rfind("<div", 0, first)
    marker = s.find(SECTION_MARKER)
    if 0 <= marker < start:
        start = s.rfind("<", 0, marker)

    end, last_end = start, start
    for m in re.finditer(re.escape(ITEM_KEY), s):
        item_start = s.rfind("<div", 0, m.start())
        if item_start < last_end:
            continue  # aninhado em item já contado
        block = balanced_block(s, item_start, "div")
        last_end = item_start + len(block)
        end = last_end
    return s[start:end]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--profile", action="store_true", help="fixture da página de perfil (card do topo + About)")
    ap.add_argument("--name", action="append", default=[], help="nome da pessoa coletada (repetível)")
    ap.add_argument("--sub", action="append", default=[], help="substituição literal extra: 'real=>falso'")
    args = ap.parse_args()

    s = open(args.input, encoding="utf-8").read()
    title = re.search(r"<title>[^<]*</title>", s)
    s = slice_profile(s) if args.profile else slice_items(s)
    if args.profile and title:
        s = title.group(0) + "\n" + s  # o parser usa o <title> como fallback do nome

    # Empresas/instituições: os nomes aparecem em alt="X logo"; troca em todo o recorte
    entities = []
    for name in re.findall(r'(?:alt|aria-label)="([^"]+) logo"', s):
        if name not in entities:
            entities.append(name)
    for name in sorted(entities, key=len, reverse=True):
        s = s.replace(name, "Organização %d" % (entities.index(name) + 1))

    # Mídias anexadas ("Thumbnail for <título>"): o título pode citar terceiros
    for i, title in enumerate(dict.fromkeys(re.findall(r'Thumbnail for ([^"<]+)', s)), 1):
        s = s.replace(title, "Mídia de exemplo %d" % i)

    # Pessoa: nome completo e cada parte, slug do perfil
    for full in args.name:
        slug = re.sub(r"[^a-z0-9]+", "-", full.lower()).strip("-")
        s = s.replace(slug, "pessoa-exemplo")
        s = re.sub(re.escape(full), "Pessoa Exemplo", s, flags=re.I)
        for part in full.split():
            if len(part) >= 3:
                s = re.sub(r"\b%s\b" % re.escape(part), "Exemplo", s, flags=re.I)

    for rule in args.sub:
        real, fake = rule.split("=>", 1)
        s = s.replace(real, fake)

    # URLs: imagens e páginas de empresa/escola/perfil
    counter = {"img": 0}

    def img(m):
        counter["img"] += 1
        # Mantém só o tipo/tamanho (profile-displayphoto-scale_200_200, company-logo_100_100), que os parsers usam
        kind = re.search(r"(?:profile-displayphoto|company-logo)[-a-z]*_\d+_\d+", m.group(0))
        return "https://media.example.com/img/%d/%s.png" % (counter["img"], kind.group(0) if kind else "image")

    s = re.sub(r"https://media\.licdn\.com/[^\"'\s<>)]*", img, s)
    ids = {}

    def entity_url(m):
        key = m.group(1) + m.group(2)
        ids.setdefault(key, 1000 + len(ids))
        return "https://www.linkedin.com/%s/%d" % (m.group(1), ids[key])

    s = re.sub(r"https://www\.linkedin\.com/(company|school)/([^\"'/\s<>?]+)/?", entity_url, s)
    s = re.sub(r"https://www\.linkedin\.com/in/[^\"'/\s<>?]+", "https://www.linkedin.com/in/pessoa-exemplo", s)
    s = re.sub(r"ACoAA[A-Za-z0-9_-]+", "ACoAAExemplo", s)  # ids internos de membro (profileUrn)

    # Texto livre: descrição expansível vira linhas de exemplo (mantém as quebras de linha)
    def free_text(m):
        body = re.split(r"<br\s*/?>", m.group(2))
        return m.group(1) + "<br>".join("Linha de descrição de exemplo." for _ in body) + m.group(3)

    s = re.sub(
        r'(data-testid="expandable-text-box"[^>]*>)(.*?)((?:</span>)?</p>)', free_text, s, flags=re.S
    )

    out = "<!DOCTYPE html>\n<html><body>\n%s\n</body></html>\n" % s
    open(args.output, "w", encoding="utf-8").write(out)
    print("%s: %d bytes, %d imagens, %d organizações" % (args.output, len(out), counter["img"], len(entities)))


if __name__ == "__main__":
    main()
