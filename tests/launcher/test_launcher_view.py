"""What the launcher window enables and says in each state (no display)."""

import pytest

from dune_imperium.launcher.command import Problem
from dune_imperium.launcher.controller import Phase
from dune_imperium.launcher.settings import Window
from dune_imperium.launcher.view import (
    address_choice,
    address_from_choice,
    controls,
    problem_lines,
    status,
    window_geometry,
)


def test_only_an_idle_launcher_takes_new_settings() -> None:
    idle = controls(Phase.IDLE, "remote")
    assert idle.editable and idle.remote_fields and idle.can_start
    assert not idle.can_stop and not idle.links
    for phase in (Phase.CHECKING, Phase.STARTING, Phase.RUNNING, Phase.STOPPING):
        busy = controls(phase, "remote")
        assert not busy.editable and not busy.remote_fields and not busy.can_start


def test_the_remote_fields_follow_the_mode() -> None:
    assert not controls(Phase.IDLE, "local").remote_fields
    assert controls(Phase.IDLE, "remote").remote_fields


def test_a_start_can_be_called_off_until_the_server_is_stopping() -> None:
    assert controls(Phase.CHECKING, "local").can_stop
    assert controls(Phase.STARTING, "local").can_stop
    assert controls(Phase.RUNNING, "local").can_stop
    assert not controls(Phase.STOPPING, "local").can_stop


def test_the_links_show_only_while_the_server_runs() -> None:
    assert controls(Phase.RUNNING, "local").links
    assert not controls(Phase.STARTING, "local").links


@pytest.mark.parametrize("phase", list(Phase))
def test_every_state_is_said_in_words_not_colour_alone(phase: Phase) -> None:
    text, _tone = status(phase)
    assert any(word in text for word in ("꺼짐", "켜짐", "중"))


def test_a_failed_start_stays_on_the_status_line() -> None:
    text, tone = status(Phase.IDLE, error="포트가 이미 쓰이고 있습니다")
    assert "포트가 이미" in text and tone == "bad"


def test_problems_are_labelled_by_level() -> None:
    lines = problem_lines(
        [Problem("error", "a"), Problem("warning", "b"), Problem("note", "c")]
    )
    assert lines == [("[오류] a", "bad"), ("[주의] b", "warn"), ("[참고] c", "plain")]


@pytest.mark.parametrize(
    ("text", "address"),
    [
        ("Tailscale — 100.87.236.12", "100.87.236.12"),
        ("같은 네트워크(LAN) — 192.168.0.64", "192.168.0.64"),
        ("  192.168.0.9 ", "192.168.0.9"),
        ("", ""),
    ],
)
def test_the_address_is_read_from_a_label_or_as_typed(text: str, address: str) -> None:
    assert address_from_choice(text) == address


def test_a_label_and_its_address_round_trip() -> None:
    assert address_from_choice(address_choice("LAN", "10.0.0.2")) == "10.0.0.2"


def test_a_saved_window_comes_back_where_it_was() -> None:
    assert window_geometry(Window(100, 50, 700, 600), 1920, 1080) == "700x600+100+50"


def test_a_window_off_the_screen_is_pulled_back() -> None:
    # Saved on a wider screen, or on another machine.
    geometry = window_geometry(Window(3000, 2000, 900, 900), 1280, 800)
    size, x, y = geometry.split("+")
    assert size == "900x800" and int(x) <= 1280 - 80 and int(y) <= 800 - 80


def test_without_a_saved_window_it_opens_centred() -> None:
    assert window_geometry(None, 1920, 1080) == "1000x640+460+146"
