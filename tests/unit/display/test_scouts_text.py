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
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.display.actions import effect_action_text, effect_action_text_ko
from dune_imperium.display.scouts import (
    SCOUTS_ITEM_NAMES_KO,
    scouts_item_lines,
    scouts_item_name,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.catalog import build_catalog

_GLOSSARY = Path(__file__).resolve().parents[3] / "docs/rules/glossary-ko.md"


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


def _with_frame(kind: FrameKind, **context: str) -> GameState:
    frame = DecisionFrame(
        kind=kind,
        frame_id="test",
        decision=PlayerDecision(owner=0, prompt="test"),
        context=tuple(sorted(context.items())),
    )
    return GameState(
        config=RulesetConfig(arrakeen_scouts=True), seed=0, decision_stack=(frame,)
    )


def test_a_secret_pick_names_its_line_for_the_chooser() -> None:
    state = _with_frame(FrameKind.SCOUTS_SECRET, event_id="covert_operation")
    pick = DomainAction(
        action_id="scouts_secret_pick", actor=0, arguments=(("pick", 2),)
    )
    assert effect_action_text(state, pick) == (
        "in two rounds: Discard a card → Recruit 3 troops"
    )
    assert effect_action_text_ko(state, pick) == (
        "두 라운드 뒤: 카드 1장 {discard} → {troop:3}"
    )
    assert len(EVENTS_BY_ID["covert_operation"].secret_choices) == 4


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


def test_korean_scouts_text_leaves_no_rules_word_in_english() -> None:
    """The Korean Scouts texts say rules words in Korean ("supply" is 개인
    공급처, the research track 연구 트랙; docs/rules/glossary-ko.md) or
    through a {term} token. Board space and card names printed on the
    English board scan stay as printed (capitalised), and so pass."""

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
    assert not stray, stray
