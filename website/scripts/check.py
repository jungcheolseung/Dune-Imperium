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


def check(directory: Path, base_url: str) -> list[str]:
    root = directory.resolve()
    base = urlsplit(base_url)
    prefix = base.path.rstrip("/") + "/"
    errors: list[str] = []
    pages = {path.resolve(): Page(path) for path in root.rglob("*.html")}
    checked = 0
    for path, page in pages.items():
        relative = path.relative_to(root)
        if page.h1s != 1 or not page.main or page.lang != "ko":
            errors.append(f"{relative}: expected one h1, main and Korean language")
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

    for required in ("index.html", "404.html", "index.json", "index.xml", "sitemap.xml", "robots.txt", "search/index.html", "devlog/index.html"):
        if not (root / required).is_file():
            errors.append(f"missing required output: {required}")

    index_file = root / "index.json"
    if index_file.exists():
        index = json.loads(index_file.read_text())
        if len(index) < 17:
            errors.append("search index omits original content")
        for item in index:
            if not item["title"] or not item["url"].startswith(prefix):
                errors.append(f"invalid search item: {item}")
            if "sources" in item or "source_ref" in item:
                errors.append("editorial metadata leaked into search index")

    for name in ("index.xml", "sitemap.xml"):
        path = root / name
        if path.exists():
            ElementTree.fromstring(path.read_text())
    feed = root / "index.xml"
    if feed.exists() and index_file.exists():
        items = ElementTree.fromstring(feed.read_text()).findall("channel/item")
        expected = {item["url"] for item in index if item["section"] in {"posts", "updates", "devlog"} and item["url"] != f"{prefix}{item['section']}/"}
        actual = {urlsplit(item.findtext("link", "")).path for item in items}
        if actual != expected:
            errors.append("RSS omits published articles or includes section pages")
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
