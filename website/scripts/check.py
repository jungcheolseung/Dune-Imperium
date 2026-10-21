"""Check a built site without installing the game or third-party packages."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree


class Page(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.path = path
        self.ids: list[str] = []
        self.links: list[str] = []
        self.h1s = 0
        self.main = False
        self.lang = ""
        self.canonical = ""
        self.alternates: dict[str, str] = {}
        self.redirect = ""
        self.feed(path.read_text())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        for attr in ("href", "src", "data-search-index"):
            if values.get(attr):
                self.links.append(values[attr] or "")
        if tag == "h1":
            self.h1s += 1
        if tag == "main":
            self.main = True
        if tag == "html":
            self.lang = values.get("lang") or ""
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href") or ""
        if tag == "link" and values.get("rel") == "alternate" and values.get("hreflang"):
            self.alternates[values["hreflang"] or ""] = values.get("href") or ""
        if tag == "meta" and (values.get("http-equiv") or "").lower() == "refresh":
            self.redirect = values.get("content") or ""


def check(directory: Path, base_url: str) -> list[str]:
    root = directory.resolve()
    base = urlsplit(base_url)
    prefix = base.path.rstrip("/") + "/"
    errors: list[str] = []
    pages = {path.resolve(): Page(path) for path in root.rglob("*.html")}
    checked = 0
    for path, page in pages.items():
        relative = path.relative_to(root)
        if relative.as_posix() == "ko/index.html":
            if page.canonical != base_url or page.redirect != f"0; url={base_url}":
                errors.append("default-language alias must redirect to the existing Korean home")
            continue
        expected_lang = "en" if relative.parts[0] == "en" else "ko"
        if page.h1s != 1 or not page.main or page.lang != expected_lang:
            errors.append(f"{relative}: expected one h1, main and {expected_lang} language")
        if relative.name != "404.html" and set(page.alternates) != {"ko", "en"}:
            errors.append(f"{relative}: missing paired language alternates")
        if duplicates := [name for name, count in Counter(page.ids).items() if count > 1]:
            errors.append(f"{relative}: duplicate ids {duplicates}")
        raw = path.read_text()
        for marker in ("{{<", "[object Object]", "params.source_ref", "localhost:"):
            if marker in raw:
                errors.append(f"{relative}: leaked template or local value {marker}")
        page_url = urljoin(base_url, str(relative))
        for link in page.links:
            target = urlsplit(urljoin(page_url, link))
            if target.scheme not in ("http", "https") or target.netloc != base.netloc:
                continue
            checked += 1
            if not target.path.startswith(prefix):
                errors.append(f"{relative}: URL leaves project path: {link}")
                continue
            location = (root / unquote(target.path[len(prefix):])).resolve()
            if not location.is_relative_to(root):
                errors.append(f"{relative}: URL escapes build: {link}")
                continue
            if location.is_dir():
                location /= "index.html"
            if not location.is_file():
                errors.append(f"{relative}: missing target: {link}")
            elif target.fragment and location in pages:
                if unquote(target.fragment) not in pages[location].ids:
                    errors.append(f"{relative}: missing fragment: {link}")

    for required in ("index.html", "404.html", "index.json", "index.xml", "sitemap.xml", "robots.txt", "search/index.html", "devlog/index.html", "en/index.html", "en/404.html", "en/index.json", "en/index.xml", "en/search/index.html", "en/devlog/index.html", "images/sandworm.svg"):
        if not (root / required).is_file():
            errors.append(f"missing required output: {required}")

    indexes: dict[str, list[dict[str, str]]] = {}
    for lang, directory in (("ko", root), ("en", root / "en")):
        index_file = directory / "index.json"
        if not index_file.exists():
            continue
        index = json.loads(index_file.read_text())
        indexes[lang] = index
        language_prefix = prefix + ("en/" if lang == "en" else "")
        if len(index) < 17:
            errors.append(f"{lang}: search index omits original content")
        for item in index:
            if not item["title"] or not item["url"].startswith(language_prefix):
                errors.append(f"invalid search item: {item}")
            if lang == "ko" and item["url"].startswith(prefix + "en/"):
                errors.append("English page in Korean search index")
            if "sources" in item or "source_ref" in item:
                errors.append("editorial metadata leaked into search index")
        feed = directory / "index.xml"
        if feed.exists():
            channel = ElementTree.fromstring(feed.read_text())
            expected = {item["url"] for item in index if item["section"] in {"posts", "updates", "devlog"} and item["url"] != f"{language_prefix}{item['section']}/"}
            actual = {urlsplit(item.findtext("link", "")).path for item in channel.findall("channel/item")}
            if actual != expected:
                errors.append(f"{lang}: RSS omits articles or includes other-language/section pages")
            if channel.findtext("channel/language") != {"ko": "ko-KR", "en": "en-US"}[lang]:
                errors.append(f"{lang}: wrong RSS language")
    if set(indexes) == {"ko", "en"}:
        ko_paths = {item["url"][len(prefix):] for item in indexes["ko"]}
        en_paths = {item["url"][len(prefix + 'en/'):] for item in indexes["en"]}
        if ko_paths != en_paths:
            errors.append("Korean and English published content must have matching translations")
    for path in root.rglob("*.xml"):
        ElementTree.fromstring(path.read_text())
    forbidden = {"assets", "checkpoints", "saves", "local", ".git", "docs", "README.md", "hugo.toml"}
    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(f"symlink in public output: {path.relative_to(root)}")
        if forbidden.intersection(path.relative_to(root).parts):
            errors.append(f"non-public path in output: {path.relative_to(root)}")
    print(f"Checked {len(pages)} HTML pages and {checked} internal references")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--base-url", default="https://jungcheolseung.github.io/Dune-Imperium/")
    arguments = parser.parse_args()
    errors = check(arguments.directory, arguments.base_url)
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print("Site output, paths, fragments, search data and feeds: PASS")


if __name__ == "__main__":
    main()
