"""The Immortality tracks' bonuses and Reclaimed Forces as ability records
(composed A7c)."""

from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.content.immortality import board, tleilaxu
from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES,
    RESEARCH_START_ID,
    TLEILAXU_TRACK,
    ResearchBonus,
    TleilaxuBonus,
)
from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES_CHOICES,
    reclaimed_forces_reward,
)
from dune_imperium.content.immortality.track_abilities import (
    RECLAIMED_FORCES_ABILITY,
    RESEARCH_SPACE_ABILITIES,
    TLEILAXU_SPACE_ABILITIES,
)
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    EffectSection,
    GainResources,
    GenerateSpecimens,
    RecruitTroops,
    SummonSandworm,
    TakeSetupSpice,
)
from dune_imperium.display.effect_dsl_text import reward_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko

_STATIC = Path(__file__).parents[3] / "src" / "dune_imperium" / "server" / "static"


def test_every_printed_track_bonus_comes_from_its_record() -> None:
    assert set(RESEARCH_SPACE_ABILITIES) == {
        space.space_id
        for space in RESEARCH_SPACES
        if space.space_id != RESEARCH_START_ID
    }
    assert {space.bonus for space in RESEARCH_SPACES} == set(ResearchBonus)
    assert set(TLEILAXU_SPACE_ABILITIES) == {
        space
        for space, bonus in enumerate(TLEILAXU_TRACK)
        if bonus is not TleilaxuBonus.NONE
    }
    assert TLEILAXU_TRACK[4] is TleilaxuBonus.VICTORY_POINT_AND_FIRST_SPICE
    assert RECLAIMED_FORCES_CHOICES == ("troops", "tleilaxu")
    assert (
        reclaimed_forces_reward("troops"),
        reclaimed_forces_reward("tleilaxu"),
    ) == (RecruitTroops(2), AdvanceTleilaxu(1))
    assert len(RECLAIMED_FORCES_ABILITY.sections) == 2


def test_the_setup_spice_reads_as_the_board_label_prints_it() -> None:
    assert "first to reach" in reward_text(TakeSetupSpice()).lower()
    assert "first to reach: {spice}" in (_STATIC / "labels_en.js").read_text()
    assert reward_text_ko(TakeSetupSpice()).startswith("첫 도달 ")
    assert "첫 도달 {spice}" in (_STATIC / "labels.js").read_text()


@pytest.mark.parametrize(
    "record",
    [
        # Two specimens: no bonus prints them.
        replace(
            RESEARCH_SPACE_ABILITIES["c1r3"],
            sections=(EffectSection(rewards=(GenerateSpecimens(2),)),),
        ),
        # A reward no bonus holds.
        replace(
            RESEARCH_SPACE_ABILITIES["c1r3"],
            sections=(EffectSection(rewards=(SummonSandworm(),)),),
        ),
        # Spice and Solari together.
        replace(
            RESEARCH_SPACE_ABILITIES["c5r5"],
            sections=(EffectSection(rewards=(GainResources(solari=1, spice=1),)),),
        ),
    ],
)
def test_the_research_compiler_refuses_what_no_bonus_holds(
    record: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(board, "RESEARCH_SPACE_ABILITIES", {"c1r3": record})
    with pytest.raises(ValueError):
        board._research_bonus("c1r3")


def test_the_tleilaxu_and_reclaimed_forces_compilers_refuse_unknown_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    odd = replace(
        TLEILAXU_SPACE_ABILITIES[7],
        sections=(EffectSection(rewards=(GainResources(spice=2),)),),
    )
    monkeypatch.setattr(board, "TLEILAXU_SPACE_ABILITIES", {7: odd})
    with pytest.raises(ValueError):
        board._tleilaxu_bonus(7)
    doubled = replace(
        RECLAIMED_FORCES_ABILITY,
        sections=(RECLAIMED_FORCES_ABILITY.sections[0],) * 2,
    )
    monkeypatch.setattr(tleilaxu, "RECLAIMED_FORCES_ABILITY", doubled)
    with pytest.raises(ValueError):
        tleilaxu._reclaimed_forces_choices()
