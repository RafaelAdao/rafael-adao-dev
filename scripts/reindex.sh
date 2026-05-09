#!/usr/bin/env bash
# 1) Regenera listagens na home (_index.md / _index.en.md) — scripts/generate_index.py
# 2) Build Hugo com limpeza (--gc), p.ex. índice de pesquisa do tema.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 "${ROOT}/scripts/generate_index.py" "$@"
exec hugo --gc --minify "$@"
