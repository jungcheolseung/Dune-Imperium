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


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


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
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ko-KR")
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
            expect(page.get_by_role("heading", level=1)).to_have_text("규칙 명세와 한 라운드 엔진")
            page.get_by_role("link", name="이전 작업").click()
            expect(page.get_by_role("heading", level=1)).to_have_text("초기 코드와 프로젝트 구성")
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

            offline_js = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
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
            expect(page.get_by_role("heading", level=1)).to_have_text("규칙 명세와 한 라운드 엔진")
            page.goto(base + "search/")
            expect(page.locator("[data-search-fallback]")).to_be_visible()
            expect(page.locator("[data-search-fallback]")).to_contain_text("JavaScript가 필요합니다")
            offline_js.close()
            browser.close()
            print("Browser: journal archive/order/navigation, reading, search/IME, categories, responsive layout, 404 and no-JS: PASS")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
