#!/usr/bin/env bash
# Cria content/AAAA/MM/DD/<slug>.md (pt-BR, idioma padrão) a partir do título (data = hoje no fuso local).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TITLE="${*:-}"

if [[ -z "${TITLE// }" ]]; then
  echo "Uso: $(basename "$0") \"Título do post\"" >&2
  exit 1
fi

export ROOT TITLE
python3 <<'PY'
import json, os, re, sys, unicodedata
from datetime import date

root = os.environ["ROOT"]
title = os.environ["TITLE"]

def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    slug = s.strip("-") or "post"
    return slug[:80].rstrip("-")

slug = slugify(title)
today = date.today()
y, m, d = today.year, f"{today.month:02d}", f"{today.day:02d}"
date_iso = today.isoformat()

rel = f"content/{y}/{m}/{d}/{slug}.md"
path = os.path.join(root, rel)
os.makedirs(os.path.dirname(path), exist_ok=True)
if os.path.exists(path):
    print(f"Erro: já existe {path}", file=sys.stderr)
    sys.exit(1)

body = f"""---
type: blog
title: {json.dumps(title, ensure_ascii=False)}
slug: {slug}
date: {date_iso}
description: Rascunho.
translationKey: {slug}
draft: false
toc: true
sidebar:
  hide: true
---

Escreva o post aqui.

"""
with open(path, "w", encoding="utf-8") as f:
    f.write(body)

print(f"Criado: {path}")
print("draft: false para aparecer no hugo server e no índice; use draft: true se for commitar sem publicar.")
PY
