"""Setup layout: conditional checkpoint field, live summary and preserved inputs."""

from __future__ import annotations

import os
from pathlib import Path

from common import Check, chrome, open_context, server

check = Check()


def run(base: str, browser) -> None:
    context, page, _ = open_context(
        browser, "setup-layout", {"width": 1440, "height": 900}
    )
    page.goto(base)
    page.wait_for_selector("#seat-selects select")
    page.wait_for_function(
        "document.querySelectorAll('#seat-selects select').length === 4"
    )
    check.ok(
        page.evaluate(
            "[...document.querySelectorAll('#seat-selects select')].map((s) => s.value)"
        )
        == ["human", "app_ai", "app_ai", "app_ai"],
        "the open server's default seats are one human and three app AIs",
    )
    check.ok(
        page.is_hidden("#opt-checkpoint-row"), "ordinary AI hides the checkpoint field"
    )
    check.ok(
        page.inner_text("#setup-summary") == "사람 1명 · AI 3명 · 규칙 옵션 8개 선택",
        "summary describes the unchanged default configuration",
    )
    for width in (1440, 900, 600):
        page.set_viewport_size({"width": width, "height": 900})
        check.ok(
            page.evaluate("document.body.scrollWidth <= innerWidth"),
            f"{width}px: setup has no horizontal overflow",
        )
        if shots := os.environ.get("E2E_SHOTS_DIR"):
            Path(shots).mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(Path(shots) / f"setup-{width}.png"), full_page=True
            )

    page.set_viewport_size({"width": 1440, "height": 900})
    seat = "#seat-selects select[data-seat='1']"
    page.select_option(seat, "checkpoint")
    check.ok(
        page.is_visible("#opt-checkpoint-row"), "checkpoint AI reveals its path field"
    )
    page.fill("#opt-checkpoint", "checkpoints/personal.pt")
    page.fill("#opt-seed", "42")
    page.uncheck("#opt-bloodlines")
    check.ok(
        page.inner_text("#setup-summary") == "사람 1명 · AI 3명 · 규칙 옵션 6개 선택",
        "summary also counts the dependent Tech option being cleared",
    )
    page.click("#language-toggle")
    check.ok(
        page.inner_text("#setup-summary") == "1 human · 3 AI · 6 rule options selected",
        "summary follows the chosen language",
    )
    check.ok(
        page.input_value(seat) == "checkpoint"
        and page.input_value("#opt-checkpoint") == "checkpoints/personal.pt"
        and page.input_value("#opt-seed") == "42",
        "language changes preserve the seat, checkpoint and seed",
    )
    page.select_option(seat, "human")
    check.ok(
        page.is_hidden("#opt-checkpoint-row"), "leaving checkpoint AI hides the field"
    )
    page.select_option(seat, "checkpoint")
    check.ok(
        page.input_value("#opt-checkpoint") == "checkpoints/personal.pt",
        "temporarily hiding the path does not erase it",
    )
    # The hidden value must not turn an ordinary AI into a checkpoint seat.
    # Seats 2-3 keep the open server's default AI, the app AI at Hard.
    page.select_option(seat, "heuristic")
    with page.expect_request(
        lambda request: request.method == "POST" and request.url.endswith("/games")
    ) as sent:
        page.click("#create-game")
    payload = sent.value.post_data_json
    check.ok(
        payload["seats"] == ["human", "heuristic", "app_ai", "app_ai"]
        and payload["game_seed"] == 42
        and payload["bloodlines"] is False
        and payload["tech_module"] is False,
        "the start button submits exactly the selected configuration",
        payload,
    )
    page.wait_for_selector("#game-screen:not([hidden])")
    context.close()


def main() -> None:
    with server() as (base, _), chrome() as browser:
        run(base, browser)
    check.finish()


if __name__ == "__main__":
    main()
