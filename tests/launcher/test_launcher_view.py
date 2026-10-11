"""What the launcher window enables and says in each state (no display)."""

import pytest

from dune_imperium.launcher.command import Problem
from dune_imperium.launcher.controller import Phase
from dune_imperium.launcher.settings import Window
from dune_imperium.launcher.view import (
    address_choice,
    address_from_choice,
    close_question,
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


SCREEN = (0, 0, 1920, 1080)


def test_a_saved_window_comes_back_where_it_was() -> None:
    assert window_geometry(Window(100, 50, 700, 600), SCREEN) == "700x600+100+50"


def test_a_window_off_the_screen_is_pulled_back() -> None:
    # Saved on a wider screen, or on another machine.
    geometry = window_geometry(Window(3000, 2000, 900, 900), (0, 0, 1280, 800))
    size, x, y = geometry.split("+")
    assert size == "900x800" and int(x) <= 1280 - 80 and int(y) <= 800 - 80


def test_without_a_saved_window_it_opens_centred() -> None:
    assert window_geometry(None, SCREEN) == "1000x640+460+146"


def test_a_window_on_a_monitor_left_of_the_main_one_stays_there() -> None:
    # Windows' virtual screen starts at -1920 with a monitor on the left.
    desktop = (-1920, 0, 3840, 1080)
    assert window_geometry(Window(-1700, 100, 1000, 640), desktop) == (
        "1000x640-1700+100"
    )


def test_the_window_is_never_smaller_than_its_widgets_need() -> None:
    # A 150 % Windows display: the fonts grow, the saved size does not.
    geometry = window_geometry(Window(10, 10, 1000, 640), SCREEN, (1180, 720))
    assert geometry.startswith("1180x720")
    assert window_geometry(None, SCREEN, (1180, 720)).startswith("1180x720")


def test_each_open_game_gets_a_line_and_a_room_link() -> None:
    from dune_imperium.launcher.view import game_rows, room_link

    rows = game_rows(
        [
            {
                "game_id": "abcdef1234567890",
                "round_number": 3,
                "finished": False,
                "players": [
                    {"seat": 0, "kind": "human", "online": True},
                    {"seat": 1, "kind": "human", "online": False},
                    {"seat": 2, "kind": "app_ai", "online": False},
                ],
            },
            {"game_id": "ffff0000ffff0000", "finished": True, "players": []},
            {"no": "id"},
        ]
    )
    assert [row.text for row in rows] == [
        "3라운드 · 사람 2명(접속 1) · abcdef12",
        "끝남 · 사람 0명(접속 0) · ffff0000",
    ]
    assert rows[1].finished and not rows[0].finished
    assert (
        room_link("http://100.1.2.3:8000/", "abc")
        == "http://100.1.2.3:8000/#game=abc"
    )


def test_closing_says_what_is_lost_and_which_button_saves() -> None:
    local = close_question(2, mode="local", autosave=True)
    assert "진행 중인 게임이 2개" in local and "턴은 사라질 수" in local
    assert "'저장'" in local and "지금 저장" not in local
    remote = close_question(0, mode="remote", autosave=True)
    assert "진행 중인 게임" not in remote and "'지금 저장'" in remote
    # Without autosave nothing survives the server but what was saved by hand.
    unsaved = close_question(1, mode="local", autosave=False)
    assert "자동 저장이 꺼져" in unsaved and "모두 사라집니다" in unsaved
