"""Exercise the built website in Chromium; Playwright is a QA-only dependency."""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

# The site scrolls smoothly unless the reader asks for reduced motion. A click right after an
# in-page jump then races that scroll: Playwright scrolls the target again on every retry, Chrome
# animates each of those scrolls, and the target never holds still long enough to count as stable
# (seen with an installed Chrome through --browser, for the site of 2026-10-20 as well).
MOTION = {"reduced_motion": "reduce"}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def check_languages_and_themes(browser, base: str, screenshots: Path | None) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="dark", **MOTION)
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "en/")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    assert page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(17, 27, 26)"
    if screenshots:
        page.screenshot(path=screenshots / "home-en-dark.png", full_page=True)
        page.locator(".brand img").screenshot(path=screenshots / "sandworm-icon.png")
    page.emulate_media(color_scheme="light")
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.get_by_role("button", name="Switch to dark mode").click()
    page.goto(base + "en/devlog/2026-10-12-training-speed/")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.locator(".prose")).to_contain_text("19.2–20.5 s to 9.1–9.5 s")
    page.get_by_role("link", name="한국어", exact=True).click()
    assert page.url == base + "devlog/2026-10-12-training-speed/"
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_role("link", name="English", exact=True).click()
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    other = context.new_page()
    other.goto(base + "en/about/")
    page.get_by_role("button", name="Switch to light mode").click()
    expect(other.locator("html")).to_have_attribute("data-theme", "light")
    other.close()
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    if screenshots:
        page.goto(base + "en/")
        page.screenshot(path=screenshots / "home-en-light.png", full_page=True)

    page.goto(base + "en/guides/first-game/")
    expect(page.get_by_role("heading", level=1)).to_have_text("Your first game")
    expect(page.locator(".prose")).to_contain_text("--autosave")
    guide_urls = page.locator(".prose a").evaluate_all("links => links.map(a => a.getAttribute('href'))")
    assert all(url.startswith("/Dune-Imperium/en/") for url in guide_urls if url.startswith("/Dune-Imperium/"))
    page.get_by_role("link", name="한국어", exact=True).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("처음 한 판 시작하기")
    page.get_by_role("link", name="English", exact=True).click()
    assert page.url == base + "en/guides/first-game/"

    page.goto(base + "en/search/?q=autosave")
    expect(page.locator("#search-results")).to_contain_text("Controls, saves, and updates")
    result_urls = page.locator("#search-results a").evaluate_all("links => links.map(a => a.getAttribute('href'))")
    assert result_urls and all("/Dune-Imperium/en/" in url for url in result_urls)
    page.get_by_label("Search query", exact=True).fill("not-a-real-query-789012")
    expect(page.locator("#search-status")).to_contain_text("No results")
    page.get_by_label("Search query", exact=True).fill("")
    expect(page.locator("#search-status")).to_have_text("Enter a search query.")

    page.goto(base + "en/posts/")
    page.get_by_role("navigation", name="Article categories").get_by_role("link", name="Rules engine", exact=True).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Rules engine")
    expect(page.locator(".listing-grid .story-card")).to_have_count(1)
    index = page.request.get(base + "en/index.json").json()
    journal_urls = {item["url"] for item in index if item["section"] == "devlog" and not item["url"].endswith("/en/devlog/")}
    page.goto(base + "en/devlog/")
    expect(page.locator(".journal-entry")).to_have_count(len(journal_urls))
    archive_urls = page.locator(".journal-entry h3 a").evaluate_all("links => links.map(link => link.getAttribute('href'))")
    assert set(archive_urls) == journal_urls
    page.locator(".journal-entry h3 a").last.click()
    page.get_by_role("link", name="Next work").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Rules specification, a one-round engine, and the first action codec")

    for language in ("", "en/"):
        for dark in (False, True):
            if (page.locator("html").get_attribute("data-theme") == "dark") != dark:
                page.locator(".theme-toggle").click()
            for width in (390, 320):
                page.set_viewport_size({"width": width, "height": 844})
                for route in ("", "devlog/", "guides/first-game/", "downloads/", "posts/learning-with-opponents/", "search/"):
                    page.goto(base + language + route)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (language, dark, width, route)
                    if screenshots and width == 390 and route in ("", "guides/first-game/"):
                        name = ("en" if language else "ko") + ("-dark" if dark else "-light")
                        page.screenshot(path=screenshots / f"{name}-{'home' if not route else 'guide'}-mobile.png", full_page=True)
                page.goto(base + language)
                page.locator(".mobile-nav summary").click()
                label = "Mobile navigation" if language else "모바일 주 메뉴"
                target = "Guides" if language else "사용법"
                page.get_by_role("navigation", name=label).get_by_role("link", name=target, exact=True).click()
                expect(page.get_by_role("heading", level=1)).to_have_text(target)
    assert not errors, errors
    context.close()

    blocked = browser.new_context(color_scheme="dark", **MOTION)
    blocked.add_init_script("Object.defineProperty(window, 'localStorage', {get() { throw new DOMException('Blocked', 'SecurityError'); }});")
    page = blocked.new_page()
    blocked_errors: list[str] = []
    page.on("pageerror", lambda error: blocked_errors.append(str(error)))
    page.goto(base + "en/")
    page.get_by_role("button", name="Switch to light mode").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    assert not blocked_errors, blocked_errors
    blocked.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Parent of the Dune-Imperium build directory")
    parser.add_argument("--browser", type=Path, help="Use an existing Chromium executable")
    parser.add_argument("--screenshots", type=Path)
    arguments = parser.parse_args()
    temporary = arguments.directory.resolve().parent / "website-browser"
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(temporary)
    tempfile.tempdir = str(temporary)
    handler = functools.partial(QuietHandler, directory=str(arguments.directory.resolve()))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/Dune-Imperium/"
    if arguments.screenshots:
        arguments.screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            options = {"headless": True, "args": ["--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"]}
            if arguments.browser:
                options["executable_path"] = str(arguments.browser)
            browser = playwright.chromium.launch(**options)
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ko-KR", color_scheme="light", **MOTION)
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            assert page.goto(base).status == 200
            expect(page.get_by_role("heading", level=1)).to_have_text("Dune: Imperium AI")
            expect(page.get_by_role("link", name="설치하고 시작하기")).to_have_attribute("href", "/Dune-Imperium/downloads/")
            expect(page.get_by_role("link", name="친구 방에 참여하기")).to_have_attribute("href", "/Dune-Imperium/guides/joining/")
            if arguments.screenshots:
                page.screenshot(path=arguments.screenshots / "home-desktop.png", full_page=True)

            # The archive and search must contain the same published journal entries.
            index = json.loads((arguments.directory / "Dune-Imperium/index.json").read_text())
            journal_urls = {item["url"] for item in index if item["section"] == "devlog" and item["url"] != "/Dune-Imperium/devlog/"}
            page.goto(base + "devlog/")
            expect(page.get_by_role("heading", level=1)).to_have_text("개발일지")
            archive_urls = page.locator(".journal-entry h3 a").evaluate_all("links => links.map(link => link.getAttribute('href'))")
            assert len(archive_urls) == len(journal_urls) and set(archive_urls) == journal_urls
            dates = page.locator(".journal-period").evaluate_all("rows => rows.map(row => [...row.querySelectorAll('time')].at(-1).dateTime)")
            assert dates == sorted(dates, reverse=True)
            page.get_by_role("navigation", name="개발일지 월별 목록").get_by_role("link", name="2026-08").click()
            assert page.url.endswith("#month-2026-08")
            page.locator(".journal-entry h3 a").last.click()
            expect(page.locator(".article-header")).to_contain_text("2023.03.24")
            expect(page.locator(".article-header")).to_contain_text("글 작성 2026.10.20")
            expect(page.locator('a[rel="prev"]')).to_have_count(0)
            page.get_by_role("link", name="다음 작업").click()
            expect(page.get_by_role("heading", level=1)).to_have_text("규칙 명세와 한 라운드 엔진, 첫 행동 codec")
            page.get_by_role("link", name="이전 작업").click()
            expect(page.get_by_role("heading", level=1)).to_have_text("2023년의 초기 시도와 중단")
            page.get_by_role("link", name="개발일지 목록", exact=True).click()
            if arguments.screenshots:
                page.screenshot(path=arguments.screenshots / "devlog-desktop.png", full_page=True)
            page.goto(base + "search/?q=학습률%20대조")
            expect(page.locator("#search-results")).to_contain_text("개체 기반 신경망 실험과 학습률 대조")
            page.goto(base)

            page.get_by_role("link", name="설치하고 시작하기").click()
            expect(page.get_by_role("heading", level=1)).to_have_text("다운로드·설치 준비")
            expect(page.locator(".prose")).to_contain_text("소스")
            page.goto(base + "guides/first-game/")
            expect(page.locator(".prose")).to_contain_text("--autosave")
            page.locator(".page-aside #TableOfContents a").first.click()
            assert page.url.split("#")[-1]

            page.goto(base + "search/?q=자동%20저장")
            expect(page.locator("#search-results li").first).to_be_visible()
            expect(page.locator("#search-results")).to_contain_text("기본 조작")
            field = page.get_by_label("검색어", exact=True)
            field.fill("일치하지않는검색어987654")
            expect(page.locator("#search-status")).to_contain_text("검색 결과가 없습니다")
            field.fill('<img src=x onerror="window.injected=true">')
            page.get_by_role("button", name="검색", exact=True).click()
            expect(page.locator("#search-status")).to_contain_text("검색 결과가 없습니다")
            assert page.evaluate("window.injected") is None
            assert page.locator("#search-results img").count() == 0
            field.fill("")
            expect(page.locator("#search-status")).to_have_text("검색어를 입력해 주세요.")
            field.dispatch_event("compositionstart")
            field.fill("탐색 AI")
            expect(page.locator("#search-status")).to_have_text("검색어를 입력해 주세요.")
            field.dispatch_event("compositionend")
            expect(page.locator("#search-results")).to_contain_text("AI는 어떻게 한 수를 고르는가")
            if arguments.screenshots:
                page.screenshot(path=arguments.screenshots / "search-desktop.png", full_page=True)

            page.goto(base + "posts/")
            page.get_by_role("navigation", name="글 분류").get_by_role("link", name="규칙 엔진", exact=True).click()
            expect(page.locator(".listing-grid .story-card")).to_have_count(1)
            expect(page.locator(".listing-grid")).to_contain_text("보드게임 규칙")

            for width in (1024, 1001, 1000, 768):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(base)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            routes = ["", "devlog/", "devlog/2026-10-14-entity-experiment/", "guides/first-game/", "posts/learning-with-opponents/", "downloads/", "search/"]
            for width in (390, 320):
                page.set_viewport_size({"width": width, "height": 844})
                for route in routes:
                    page.goto(base + route)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, route)
                page.goto(base)
                page.locator(".mobile-nav summary").click()
                expect(page.get_by_role("navigation", name="모바일 주 메뉴")).to_be_visible()
                page.get_by_role("navigation", name="모바일 주 메뉴").get_by_role("link", name="사용법", exact=True).click()
                expect(page.get_by_role("heading", level=1)).to_have_text("사용법")
                page.locator(".mobile-nav summary").click()
                page.keyboard.press("Escape")
                assert not page.locator(".mobile-nav").evaluate("element => element.open")
            if arguments.screenshots:
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(base)
                page.screenshot(path=arguments.screenshots / "home-mobile.png", full_page=True)
                page.goto(base + "guides/first-game/")
                page.screenshot(path=arguments.screenshots / "guide-mobile.png", full_page=True)
                page.goto(base + "devlog/")
                page.screenshot(path=arguments.screenshots / "devlog-mobile.png", full_page=True)
                page.goto(base + "devlog/2026-10-14-entity-experiment/")
                page.screenshot(path=arguments.screenshots / "devlog-article-mobile.png", full_page=True)
            page.goto(base + "404.html")
            expect(page.get_by_role("heading", level=1)).to_contain_text("페이지를 찾지")
            assert not errors, errors
            context.close()
            check_languages_and_themes(browser, base, arguments.screenshots)

            offline_js = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844}, color_scheme="dark", **MOTION)
            page = offline_js.new_page()
            page.goto(base)
            page.locator(".mobile-nav summary").click()
            page.get_by_role("navigation", name="모바일 주 메뉴").get_by_role("link", name="사용법", exact=True).click()
            expect(page.get_by_role("heading", level=1)).to_have_text("사용법")
            page.goto(base + "devlog/")
            expect(page.get_by_role("heading", level=1)).to_have_text("개발일지")
            page.get_by_role("navigation", name="개발일지 월별 목록").get_by_role("link", name="2023-04").click()
            page.locator(".journal-entry h3 a").last.click()
            page.get_by_role("link", name="다음 작업").click()
            expect(page.get_by_role("heading", level=1)).to_have_text("규칙 명세와 한 라운드 엔진, 첫 행동 codec")
            page.goto(base + "search/")
            expect(page.locator("[data-search-fallback]")).to_be_visible()
            expect(page.locator("[data-search-fallback]")).to_contain_text("JavaScript가 필요합니다")
            assert page.locator("body").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(17, 27, 26)"
            page.get_by_role("link", name="English", exact=True).click()
            expect(page.get_by_role("heading", level=1)).to_have_text("Search")
            expect(page.locator("[data-search-fallback]")).to_contain_text("Search requires JavaScript")
            expect(page.locator(".theme-toggle")).to_be_hidden()
            offline_js.close()
            browser.close()
            print("Browser: Korean/English, themes and persistence, journal, search/IME, responsive layout, 404 and no-JS: PASS")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
