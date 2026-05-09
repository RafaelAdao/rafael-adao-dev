#!/usr/bin/env python3
"""Download remote images referenced in content/**/*.md into static/images/posts and rewrite markdown."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
STATIC_POSTS = ROOT / "static" / "images" / "posts"

IMG_MD = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")

CT_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def stem_for_url(url: str) -> str:
    p = urlparse(url)
    path = unquote(p.path)
    if "substack-post-media" in p.netloc and "/public/images/" in path:
        return path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if "substackcdn.com" in p.netloc:
        dec = unquote(p.path)
        if "/public/images/" in dec:
            return dec.split("/public/images/")[-1].rsplit(".", 1)[0]
        if "images%2F" in url:
            tail = unquote(url.split("images%2F", 1)[-1].split("&")[0])
            return tail.split("/")[-1].rsplit(".", 1)[0]
    if "miro.medium.com" in p.netloc:
        tail = path.rstrip("/").split("/")[-1]
        return "medium-" + tail.replace("*", "-").rsplit(".", 1)[0]
    tail = path.rstrip("/").split("/")[-1] or "image"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", tail).rsplit(".", 1)[0]


def pick_ext(data: bytes, content_type: str | None, url: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in CT_EXT:
        return CT_EXT[ct]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    suf = Path(urlparse(url).path).suffix.lower()
    if suf == ".jpeg":
        return ".jpg"
    if suf in {".png", ".jpg", ".gif", ".webp", ".svg"}:
        return suf
    return ".bin"


def url_extension_trusted(url: str) -> bool:
    return urlparse(url).netloc == "substack-post-media.s3.amazonaws.com"


def fetch(url: str) -> tuple[bytes, str | None]:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; rafael-adao-dev/1.0)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=120) as resp:
        return resp.read(), resp.headers.get("Content-Type")


def main() -> int:
    STATIC_POSTS.mkdir(parents=True, exist_ok=True)

    url_to_rel: dict[str, str] = {}
    by_file: dict[Path, list[tuple[str, str, str]]] = {}

    for md in sorted(CONTENT.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        for m in IMG_MD.finditer(text):
            alt, url = m.group(1), m.group(2)
            if not url.startswith("http"):
                continue
            by_file.setdefault(md, []).append((m.group(0), alt, url))
            url_to_rel.setdefault(url, "")

    for url in sorted(url_to_rel):
        print("fetch", url[:90], "...")
        try:
            data, ct = fetch(url)
        except Exception as e:
            print("FAIL", url, e, file=sys.stderr)
            return 1

        if url_extension_trusted(url):
            name = urlparse(url).path.rsplit("/", 1)[-1]
            dest = STATIC_POSTS / unquote(name)
        else:
            ext = pick_ext(data, ct, url)
            dest = STATIC_POSTS / (stem_for_url(url) + ext)

        if dest.exists() and dest.read_bytes() != data:
            stem, sfx = dest.stem, dest.suffix
            n = 2
            while True:
                cand = STATIC_POSTS / f"{stem}-{n}{sfx}"
                if not cand.exists():
                    dest = cand
                    break
                if cand.read_bytes() == data:
                    dest = cand
                    break
                n += 1

        dest.write_bytes(data)
        rel = "/images/posts/" + dest.name
        url_to_rel[url] = rel
        print("  ->", dest.name, len(data), "bytes")

    for md, items in by_file.items():
        text = md.read_text(encoding="utf-8")
        for full, alt, url in items:
            rel = url_to_rel.get(url)
            if not rel:
                continue
            new = f"![{alt}]({rel})"
            text = text.replace(full, new, 1)
        md.write_text(text, encoding="utf-8")

    print("done; touched", len(by_file), "markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
