"""The display text of the original game's content (stage P5a of
docs/base-game-and-ix-plan.md): every space, Conflict, card and Leader the
original game plays gets English text and its generated Korean twin, with
no engine id leaking into a line.

The rows the generators had not met before the original game: a Conflict
reward printed with "-OR-" or "Choose two:" between its icon groups
(docs/rules/imperium-base.md 10.1, OQ-114), Grand Vision's two-chevron
Influence (one Faction, twice [DI p. 16]), Sort Through the Chaos's Mentat
(taken at the next round's start [FAQ p. 4]), and the board spaces whose
visit is more than the engine's static table (imperium-base.md 8).
"""

import re
import sys
from pathlib import Path
from typing import Any

import pytest

from dune_imperium.content.imperium.board import IMPERIUM_BOARD_SPACES
from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.imperium.leaders import IMPERIUM_LEADERS
from dune_imperium.content.imperium.reserve import IMPERIUM_RESERVE_STACKS
from dune_imperium.display import personal_card_text, personal_card_text_ko
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
from dune_imperium.display.leaders import LEADER_FACE_TEXTS
from dune_imperium.display.spaces import (
    space_notes,
    space_notes_ko,
    space_option_count,
    space_option_effects,
    space_option_effects_ko,
)
from dune_imperium.display.structs import (
    conflict_rewards_texts,
    conflict_rewards_texts_ko,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_placeholders_are_terms,
    terms_keys,
)

# An engine id outside a {term} placeholder ("spice_trade").
_RAW_ID = re.compile(r"(?<![{_a-z])[a-z]+_[a-z_]+(?![a-z_:]*\})")


def _clean_english(line: str) -> None:
    assert line.strip(), line
    assert not _RAW_ID.search(line), line
    assert "not transcribed" not in line, line


def _clean_korean(line: str) -> None:
    assert line.strip(), line
    assert_placeholders_are_terms(line, terms_keys())
    # The original game's spaces, the Mentat and the Foldspace card read in
    # its Korean rulebook's words [DI-ko pp. 16-18].
    assert_no_stray_latin(line)


@pytest.mark.parametrize(
    "space", IMPERIUM_BOARD_SPACES, ids=lambda space: space.space_id
)
def test_every_original_space_has_one_line_per_cost_option(space: Any) -> None:
    english = space_option_effects(space.space_id, choam_module=False)
    korean = space_option_effects_ko(space.space_id, choam_module=False)
    assert len(english) == len(korean) == space_option_count(space.space_id)
    for line in (*english, *space_notes(space.space_id)):
        _clean_english(line)
    for line in (*korean, *space_notes_ko(space.space_id)):
        _clean_korean(line)
    assert len(space_notes(space.space_id)) == len(space_notes_ko(space.space_id))


def test_original_spaces_say_what_the_static_table_leaves_out() -> None:
    # [DI pp. 17-18], docs/rules/imperium-base.md 8 and 9.
    def line(space_id: str) -> str:
        (text,) = space_option_effects(space_id, choam_module=False)
        return text

    assert "Acquire a Foldspace card" in line("foldspace")
    assert "You may trash a card → Draw 2 cards" in line("selective_breeding")
    assert "Take the Mentat if it is here" in line("mentat")
    assert line("imperium_swordmaster").startswith("Once per game")
    assert "+2 Persuasion" in line("imperium_high_council")
    assert line("imperium_hagga_basin") == "Gain 2 spice plus all bonus spice here"
    assert line("the_great_flat") == "Gain 3 spice plus all bonus spice here"
    # Carthag's controller and the Hall of Oratory's passive [DI pp. 10, 17].
    assert space_notes("carthag") == space_notes("arrakeen")
    assert "+1 Persuasion" in space_notes("hall_of_oratory")[0]


@pytest.mark.parametrize("conflict", IMPERIUM_CONFLICTS, ids=lambda c: c.card.card_id)
def test_every_original_conflict_has_three_reward_lines(conflict: Any) -> None:
    english = conflict_rewards_texts(conflict)
    korean = conflict_rewards_texts_ko(conflict)
    assert english is not None and korean is not None
    assert len(english) == len(korean) == 3
    for text in english:
        _clean_english(text)
    for text in korean:
        _clean_korean(text)


def test_original_conflict_choice_rows_say_choose() -> None:
    # A printed "-OR-" takes one, "Choose two:" two different ones (OQ-114);
    # imperium-base.md 10.1's table.
    texts = {
        c.card.card_id: conflict_rewards_texts(c) or [] for c in IMPERIUM_CONFLICTS
    }
    texts_ko = {
        c.card.card_id: conflict_rewards_texts_ko(c) or [] for c in IMPERIUM_CONFLICTS
    }
    assert texts["cloak_and_dagger"][2] == (
        "3rd: Choose one: Draw 1 Intrigue card / Gain 1 spice"
    )
    assert texts_ko["cloak_and_dagger"][2] == (
        "3등: 하나 선택: {intrigue:1} / {spice:1}"
    )
    assert texts["imperium_battle_for_arrakeen"][1] == (
        "2nd: Choose two: Draw 1 Intrigue card / Gain 2 spice / Gain 3 solari"
    )
    assert texts_ko["imperium_battle_for_arrakeen"][1] == (
        "2등: 둘 선택: {intrigue:1} / {spice:2} / {solari:3}"
    )
    # Grand Vision: two Influence with one chosen Faction [DI p. 16].
    assert "Gain 2 Influence (choose a Faction once)" in texts["grand_vision"][0]
    assert "{influence_any:2} (4개의 팩션 중 하나 한 번 선택)" in (
        texts_ko["grand_vision"][0]
    )
    # Sort Through the Chaos: the Mentat, at the next round's start.
    assert "Take the Mentat at the next round's start" in (
        texts["sort_through_the_chaos"][0]
    )
    # Machinations' Choose two over the Faction icons stays one distinct gain.
    assert texts["machinations"][0] == (
        "1st: Gain 2 Influence (choose a different Faction each time)"
    )


@pytest.mark.parametrize(
    "entry",
    (*IMPERIUM_BASE_CARDS, *IMPERIUM_RESERVE_STACKS),
    ids=lambda entry: entry.card.card_id,
)
def test_every_original_card_has_clean_text(entry: Any) -> None:
    english = personal_card_text(entry)
    korean = personal_card_text_ko(entry)
    assert len(english) == len(korean)
    for line in english:
        _clean_english(line)
    for line in korean:
        _clean_korean(line)


@pytest.mark.parametrize(
    "entry", IMPERIUM_INTRIGUE_CARDS, ids=lambda entry: entry.card.card_id
)
def test_every_original_intrigue_card_has_clean_text(entry: Any) -> None:
    english = intrigue_card_text(entry)
    korean = intrigue_card_text_ko(entry)
    assert len(english) == len(korean)
    for line in english:
        _clean_english(line)
    for line in korean:
        _clean_korean(line)


def test_agent_icons_are_named_not_spelled_as_ids() -> None:
    # "has the following icons: Emperor, Spacing Guild, Bene Gesserit,
    # Fremen" [Dispatch an Envoy card].
    (envoy,) = (
        entry
        for entry in IMPERIUM_INTRIGUE_CARDS
        if entry.card.card_id == "dispatch_an_envoy"
    )
    assert intrigue_card_text(envoy) == [
        "Plot — The card you play this turn has the Emperor, Spacing Guild,"
        " Bene Gesserit, Fremen icons",
    ]


def test_every_original_leader_has_face_text() -> None:
    for leader in IMPERIUM_LEADERS:
        text = LEADER_FACE_TEXTS[leader.leader_id]
        _clean_english(text.ability_text)
        _clean_english(text.signet_text)
