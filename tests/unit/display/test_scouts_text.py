"""Arrakeen Scouts in words (slice 9): names, lines and choice details.

The Korean item names are the app's official terms recorded in
docs/rules/glossary-ko.md (the "항목 이름" table); every item a game can draw
must have its names and at least one line, and a seat choosing a line must
see what it does rather than a bare index.
"""

import re
from pathlib import Path

from dune_imperium import RulesetConfig
from dune_imperium.adapters.observation_encoding import SCOUTS_ITEM_IDS
from dune_imperium.content.arrakeen_scouts import EVENTS_BY_ID
from dune_imperium.content.registry.board import BOARD_SPACES_BY_ID
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.display.actions import effect_action_text, effect_action_text_ko
from dune_imperium.display.scouts import (
    SCOUTS_ITEM_NAMES_KO,
    scouts_item_lines,
    scouts_item_name,
    secret_due_text,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.catalog import build_catalog

_GLOSSARY = Path(__file__).resolve().parents[3] / "docs/rules/glossary-ko.md"
_SPACE_NAMES = frozenset(space.name for space in BOARD_SPACES_BY_ID.values())


def test_every_item_has_names_and_lines() -> None:
    for item_id in SCOUTS_ITEM_IDS:
        english, korean = scouts_item_lines(item_id)
        assert english and len(english) == len(korean), item_id
        assert all(english) and all(korean), item_id
        assert scouts_item_name(item_id) and SCOUTS_ITEM_NAMES_KO[item_id]


def test_korean_names_are_the_glossary_terms() -> None:
    text = _GLOSSARY.read_text(encoding="utf-8")
    terms = dict(
        re.findall(
            r"^\| ([^|]+?) \| ([^|]+?) \| `\[KO app: spice\."
            r"(?:subcommittees|mission|event|auction|sale)\.",
            text,
            re.M,
        )
    )
    for item_id in SCOUTS_ITEM_IDS:
        assert terms[scouts_item_name(item_id)] == SCOUTS_ITEM_NAMES_KO[item_id]


def test_the_catalog_carries_every_item() -> None:
    items = build_catalog()["scouts_items"]
    assert isinstance(items, dict)
    assert set(items) == set(SCOUTS_ITEM_IDS)
    entry = items["spies_for_hire_late"]
    assert isinstance(entry, dict)
    assert entry["kind"] == "auction"
    assert entry["lines"] == [
        "1st: Place a Spy, Draw 1 Intrigue card",
        "2nd: Place a Spy",
    ]


def test_auction_catalog_exposes_the_bid_currency_beside_prize_lines() -> None:
    # docs/rules/arrakeen-scouts.md 8.1's currency column: these sealed
    # auctions use Solari; 8.2 Mercenaries and 8.3 Critical Moment use spice.
    # UI metadata only: the reward lines intentionally do not contain a cost.
    items = build_catalog()["scouts_items"]
    assert isinstance(items, dict)
    expected = {
        "highest_bidder_mid": "solari",
        "highest_bidder_late": "solari",
        "spies_for_hire_mid": "solari",
        "spies_for_hire_late": "solari",
        "choam_negotiations_mid": "solari",
        "choam_negotiations_late": "solari",
        "competitive_study_mid": "solari",
        "competitive_study_late": "solari",
        # The original game's Treachery bids spice (stage P8b).
        "treachery_mid": "spice",
        "treachery_late": "spice",
        # Its open Mentat auction calls Solari mid, spice late (9a).
        "mentat_mid": "solari",
        "mentat_late": "spice",
        "mercenaries": "spice",
        "critical_moment_mid": "spice",
        "critical_moment_late": "spice",
    }
    currencies = {
        item_id: entry["currency"]
        for item_id, entry in items.items()
        if isinstance(entry, dict) and "currency" in entry
    }
    assert currencies == expected


def _with_frame(
    kind: FrameKind, round_number: int = 0, **context: str
) -> GameState:
    frame = DecisionFrame(
        kind=kind,
        frame_id="test",
        decision=PlayerDecision(owner=0, prompt="test"),
        context=tuple(sorted(context.items())),
    )
    return GameState(
        config=RulesetConfig(arrakeen_scouts=True),
        seed=0,
        round_number=round_number,
        decision_stack=(frame,),
    )


def test_a_secret_pick_names_its_line_for_the_chooser() -> None:
    # Picked in round 4 (the event's round, docs/rules/arrakeen-scouts.md
    # 7.1), a two-round line falls due in round 6 (7.2) and says so: "in
    # two rounds" read as round 7 in a real game (user report 2026-11-01).
    state = _with_frame(
        FrameKind.SCOUTS_SECRET, round_number=4, event_id="covert_operation"
    )
    pick = DomainAction(
        action_id="scouts_secret_pick", actor=0, arguments=(("pick", 2),)
    )
    assert effect_action_text(state, pick) == (
        "Round 6: Discard a card → Recruit 3 troops"
    )
    assert effect_action_text_ko(state, pick) == (
        "6라운드: 카드 1장 {discard} → {troop:3}"
    )
    next_round = DomainAction(
        action_id="scouts_secret_pick", actor=0, arguments=(("pick", 0),)
    )
    assert effect_action_text(state, next_round) == "Round 5: Place a Spy"
    assert effect_action_text_ko(state, next_round) == "5라운드: {spy} 배치"
    assert len(EVENTS_BY_ID["covert_operation"].secret_choices) == 4


def test_a_named_faction_pick_is_dated_too() -> None:
    # The original game's Covert Operation names a Faction with the pick
    # (stage P8c); its chooser's line names the Faction and the due round.
    state = _with_frame(
        FrameKind.SCOUTS_SECRET,
        round_number=5,
        event_id="imperium_covert_operation",
    )
    pick = DomainAction(
        action_id="scouts_secret_pick",
        actor=0,
        arguments=(("faction", "emperor"), ("pick", 3)),
    )
    assert effect_action_text(state, pick) == (
        "Round 7: Discard 2 cards → Gain 2 Emperor Influence"
    )
    assert effect_action_text_ko(state, pick) == (
        "7라운드: 카드 2장 {discard} → {influence_emperor:2}"
    )


def test_secret_lines_are_relative_only_without_a_round() -> None:
    # The catalog's lines serve pages that do not know the event's round;
    # its secret_lines carry each line's delay and words for those that do.
    assert secret_due_text(1) == ("next round: ", "다음 라운드: ")
    assert secret_due_text(2) == ("in two rounds: ", "두 라운드 뒤: ")
    assert secret_due_text(2, 7) == ("Round 9: ", "9라운드: ")
    items = build_catalog()["scouts_items"]
    assert isinstance(items, dict)
    secret_events = sorted(
        item_id
        for item_id, entry in items.items()
        if isinstance(entry, dict) and "secret_lines" in entry
    )
    assert secret_events == sorted(
        event_id for event_id, event in EVENTS_BY_ID.items() if event.secret_choices
    )
    for event_id in secret_events:
        entry = items[event_id]
        assert isinstance(entry, dict)
        secret, english, korean = (
            entry["secret_lines"],
            entry["lines"],
            entry["lines_ko"],
        )
        assert isinstance(secret, list)
        assert isinstance(english, list) and isinstance(korean, list)
        choices = EVENTS_BY_ID[event_id].secret_choices
        assert [line["delay"] for line in secret if isinstance(line, dict)] == [
            choice.delay for choice in choices
        ]
        for line, relative, relative_ko in zip(secret, english, korean, strict=True):
            assert isinstance(line, dict) and isinstance(relative, str)
            assert isinstance(relative_ko, str)
            assert relative.endswith(str(line["line"])), (relative, line)
            assert relative_ko.endswith(str(line["line_ko"])), (relative_ko, line)


def test_an_event_line_and_a_subcommittee_are_described() -> None:
    state = _with_frame(FrameKind.SCOUTS_CHOICE, item="unravel_the_future")
    line = DomainAction(
        action_id="scouts_choose_option", actor=0, arguments=(("option", 1),)
    )
    assert effect_action_text(state, line) == "Pay 3 spice → Draw 2 cards"
    join = DomainAction(
        action_id="join_subcommittee",
        actor=0,
        arguments=(("subcommittee_id", "oversight"),),
    )
    assert effect_action_text_ko(state, join) == (
        "관리감독: {spy} 소환 → 카드 1장 {trash}, {spice:1}"
    )


def _collecting(item: str, option: int) -> GameState:
    """A line received later waiting for seat 0's collect click (OQ-164)."""

    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_EFFECT,
        frame_id="test",
        decision=PlayerDecision(owner=0, prompt="test"),
        context=(("collect", 1), ("item", item), ("option", option)),
    )
    return GameState(
        config=RulesetConfig(arrakeen_scouts=True), seed=0, decision_stack=(frame,)
    )


def test_a_collect_click_names_the_line_it_receives() -> None:
    """User decision 2026-11-01 (OQ-164): a revealed pick's line and an
    auction winner's line wait for the seat's "받기"; the row names the line,
    so the seat sees what it receives before it clicks."""

    collect = DomainAction(action_id="scouts_collect_reward", actor=0)
    pick = _collecting("offworld_operation", 2)
    assert effect_action_text(pick, collect) == (
        "Tleilaxu (advance your Tleilaxu token)"
    )
    assert effect_action_text_ko(pick, collect) == "{tleilaxu} (트랙 전진)"
    won = _collecting("highest_bidder_mid", 0)
    assert effect_action_text(won, collect) == "Draw 1 card"
    assert effect_action_text_ko(won, collect) == "{draw:1}"


def test_a_payout_collect_click_names_the_mission_and_its_goods() -> None:
    """OQ-164 (b) (user decisions 2026-11-01): a mission's owed payout waits
    for its seat's "받기"; the row names the mission and what it pays."""

    def payout(mission_id: str, **owed: object) -> GameState:
        frame = DecisionFrame(
            kind=FrameKind.SCOUTS_EFFECT,
            frame_id="test",
            decision=PlayerDecision(owner=1, prompt="test"),
            context=(
                ("collect", 1),
                ("item", mission_id),
                ("payout", 1),
                ("player", 1),
                ("source", "test"),
            ),
        )
        return GameState(
            config=RulesetConfig(arrakeen_scouts=True),
            seed=0,
            decision_stack=(frame,),
            **owed,  # type: ignore[arg-type]
        )

    collect = DomainAction(action_id="scouts_collect_reward", actor=1)
    escort = payout(
        "choam_escort",
        scouts_goods=(
            ("choam_escort", "owed:test", "solari", 1, 1),
            ("choam_escort", "owed:test", "spice", 1, 1),
        ),
    )
    assert effect_action_text(escort, collect) == "CHOAM Escort: 1 Solari, 1 spice"
    assert effect_action_text_ko(escort, collect) == (
        "초암 호송대: {solari:1}, {spice:1}"
    )
    offering = payout(
        "tleilaxu_offering",
        scouts_parked=(("tleilaxu_offering", 1, "owed:test", 2),),
    )
    assert effect_action_text(offering, collect) == "Tleilaxu Offering: 2 specimens"
    assert effect_action_text_ko(offering, collect) == "틀레이락스의 공물: {specimen:2}"


def test_korean_scouts_text_leaves_no_rules_word_in_english() -> None:
    """The Korean Scouts texts say rules words in Korean ("supply" is 개인
    공급처, the research track 연구 트랙; docs/rules/glossary-ko.md) or
    through a {term} token. A board space goes by its Korean name (the
    Korean Board Space Guide, display.names_ko), never the English one on
    the board scan; card names without a known Korean print stay English
    (capitalised), and so pass."""

    source = (
        Path(__file__).resolve().parents[3]
        / "src/dune_imperium/display/scouts.py"
    ).read_text(encoding="utf-8")
    stray: list[tuple[int, str]] = []
    for number, line in enumerate(source.splitlines(), 1):
        for text in re.findall(r'"([^"]*)"', line):
            if not re.search(r"[가-힣]", text):
                continue
            bare = re.sub(r"\{[^}]*\}", " ", text)
            stray += [(number, word) for word in re.findall(r"\b[a-z]{2,}\b", bare)]
            stray += [(number, name) for name in _SPACE_NAMES if name in bare]
    assert not stray, stray
