#!/usr/bin/env python3
"""Regenera content/_index.md (pt-BR, idioma padrão) e _index.en.md a partir dos posts em content/AAAA/MM/DD/.

Posts em PT: <slug>.md. Traduções: <slug>.en.md.

Opções:
  --future   inclui posts com data no futuro
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
INDEX_DEFAULT = CONTENT / "_index.md"
INDEX_EN = CONTENT / "_index.en.md"
DELIM = "---"

PT_MONTHS = [
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]

INCLUDE_FUTURE = "--future" in sys.argv


def escape_md(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]")


def _parse_scalar(val: str):
    val = val.strip()
    if val in ("true", "false"):
        return val == "true"
    if val.startswith('"') and val.endswith('"'):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val[1:-1]
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1].replace("''", "'")
    return val


def parse_frontmatter_block(block: str) -> dict:
    """Extrai apenas campos usados pelo índice (evita depender de PyYAML)."""
    fm: dict = {}
    for key in ("title", "date", "draft", "type", "slug"):
        m = re.search(rf"^{re.escape(key)}:\s*(.+)$", block, re.M)
        if not m:
            continue
        fm[key] = _parse_scalar(m.group(1))
    return fm


def extract_frontmatter(raw: str) -> tuple[dict, str] | None:
    if not raw.startswith(f"{DELIM}\n"):
        return None
    rest = raw[4:]
    end = rest.find(f"\n{DELIM}\n")
    if end == -1:
        return None
    fm = parse_frontmatter_block(rest[:end])
    body = rest[end + 4 :]
    return fm, body


def parse_date(val) -> date:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()[:10]
    return date.fromisoformat(s)


def parse_post(path: Path, lang: str) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Ignorado {path}: {e}", file=sys.stderr)
        return None
    parsed = extract_frontmatter(raw)
    if not parsed:
        return None
    fm, _ = parsed
    if not fm.get("title") or not fm.get("date"):
        return None
    if fm.get("type") and str(fm["type"]) != "blog":
        return None
    if fm.get("draft") is True or str(fm.get("draft")).lower() == "true":
        return None

    d = parse_date(fm["date"])
    slug = str(fm.get("slug") or "").strip()
    if not slug:
        n = path.name
        if n.endswith(".en.md"):
            slug = n[: -len(".en.md")]
        elif n.endswith(".md"):
            slug = n[: -len(".md")]
        else:
            slug = n

    rel = path.relative_to(CONTENT)
    parts = rel.parts
    if len(parts) != 4 or not re.match(r"^\d{4}$", parts[0]):
        return None
    if not re.match(r"^\d{2}$", parts[1]) or not re.match(r"^\d{2}$", parts[2]):
        return None

    y, m, day = parts[0], parts[1], parts[2]
    if lang == "en":
        url = f"/en/{y}/{m}/{day}/{slug}/"
    else:
        url = f"/{y}/{m}/{day}/{slug}/"

    return {"title": fm["title"], "url": url, "date": d, "lang": lang}


def collect(lang: str) -> list[dict]:
    now = datetime.now()
    posts: list[dict] = []
    if lang == "en":
        candidates = CONTENT.rglob("*.en.md")
    else:
        candidates = (
            p for p in CONTENT.rglob("*.md") if not p.name.endswith(".en.md")
        )
    for path in candidates:
        if path.name.startswith("_index"):
            continue
        rel = path.relative_to(CONTENT)
        if len(rel.parts) != 4:
            continue
        post = parse_post(path, lang)
        if not post:
            continue
        if not INCLUDE_FUTURE:
            dt = datetime(post["date"].year, post["date"].month, post["date"].day)
            if dt > now:
                continue
        posts.append(post)
    return posts


def group_by_month(posts: list[dict]) -> dict[tuple[int, int], list[dict]]:
    posts = sorted(posts, key=lambda p: p["date"], reverse=True)
    g: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for p in posts:
        g[(p["date"].year, p["date"].month)].append(p)
    return dict(g)


def render_months(grouped: dict[tuple[int, int], list[dict]], lang: str) -> str:
    lines: list[str] = []
    for year, month in sorted(grouped.keys(), reverse=True):
        mname = PT_MONTHS[month] if lang == "pt" else date(2000, month, 1).strftime("%B")
        lines.append(f"## {year} - {mname}\n")
        for post in grouped[(year, month)]:
            t = escape_md(str(post["title"]))
            lines.append(f"- [{t}]({post['url']})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_index(path: Path, title: str, lang: str, grouped: dict) -> None:
    body = render_months(grouped, lang)
    lines = [
        DELIM,
        f"title: {json.dumps(title, ensure_ascii=False)}",
        "translationKey: home",
        "toc: true",
        "sidebar:",
        "  hide: true",
        f"{DELIM}\n",
        body,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    n = sum(len(v) for v in grouped.values())
    print(f"Gerado {path} ({n} posts).")


def main() -> None:
    grouped_pt = group_by_month(collect("pt"))
    write_index(INDEX_DEFAULT, "Rafael Adão — Blog", "pt", grouped_pt)
    grouped_en = group_by_month(collect("en"))
    write_index(INDEX_EN, "Rafael Adão — Blog", "en", grouped_en)


if __name__ == "__main__":
    main()
