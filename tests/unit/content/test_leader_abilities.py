"""The Leaders' Signet Ring abilities as ability records (composed A6c)."""

from dataclasses import replace

import pytest

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
)
from dune_imperium.content.uprising.effect_dsl import (
    EffectSection,
    GainResources,
    PayResources,
    PlaceSpy,
    RecruitUndeployableTroops,
    SummonSandworm,
    TroopToMemory,
    VisitedSpaceHasIcon,
)
from dune_imperium.content.uprising.leader_abilities import SIGNET_ABILITIES
from dune_imperium.content.uprising.leaders import LEADERS
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.display.effect_dsl_text import condition_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko
from dune_imperium.display.leaders import LEADER_FACE_TEXTS
from dune_imperium.display.leaders_ko import LEADER_FACE_TEXTS_KO
from dune_imperium.rules import leader_abilities
from dune_imperium.rules.agent_effects import _SIGNET_ICONS, _STAGED_SIGNETS
from dune_imperium.rules.leader_abilities import SIGNET_HOOKS


def test_every_leader_face_but_the_steersman_prints_a_signet_record() -> None:
    faces = {
        face
        for leader in LEADERS
        for face in (leader.setup_face_id or leader.leader_id, leader.alternate_face_id)
        if face is not None
    }
    assert set(SIGNET_ABILITIES) == faces - {"steersman_y_rkoon"}
    assert len(SIGNET_ABILITIES) == 18
    for record in SIGNET_ABILITIES.values():
        assert record.timing is AbilityTiming.AGENT_BOX
    assert {
        record.hook for record in SIGNET_ABILITIES.values() if record.hook
    } == SIGNET_HOOKS
    assert _STAGED_SIGNETS <= SIGNET_HOOKS


def test_the_records_say_which_signets_are_optional_and_which_print_icons() -> None:
    """Optional throughout: Spice Agony, Water of Life, Chronicler's Insight,
    Fedaykin Maneuver, Into the Fray; Fill Coffers alone resolves icon by
    icon in the Signet Ring's box (OQ-027, OQ-028)."""

    assert {
        face
        for face, record in SIGNET_ABILITIES.items()
        if record.mark is AbilityMark.OPTIONAL and record.hook not in _STAGED_SIGNETS
    } == {
        "lady_jessica",
        "reverend_mother_jessica",
        "princess_irulan",
        "chani",
        "duncan_idaho",
    }
    assert dict(_SIGNET_ICONS) == {"lady_amber_metulli": ("solari", "spice")}
    assert {
        face
        for face, record in SIGNET_ABILITIES.items()
        if record.mark is AbilityMark.AUTOMATIC
    } == {
        "gurney_halleck",
        "lady_amber_metulli",
        "muad_dib",
        "piter_de_vries",
        "liet_kynes",
    }


def test_the_new_signet_pieces_read_as_the_faces_print_them() -> None:
    piter = SIGNET_ABILITIES["piter_de_vries"].sections[0].rewards[0]
    assert piter == RecruitUndeployableTroops(1)
    assert reward_text(piter) == LEADER_FACE_TEXTS["piter_de_vries"].signet_text
    assert reward_text_ko(piter).endswith(
        LEADER_FACE_TEXTS_KO["piter_de_vries"]
        .signet_text.removeprefix("{troop}")
        .removesuffix(".")
    )
    memory = TroopToMemory()
    assert reward_text(memory).lower() in (
        LEADER_FACE_TEXTS["lady_jessica"].signet_text.lower()
    )
    assert reward_text_ko(memory) in LEADER_FACE_TEXTS_KO["lady_jessica"].signet_text
    assert condition_text(VisitedSpaceHasIcon(AgentIcon.SPICE_TRADE)) == (
        "you sent an Agent to a Spice Trade space this turn"
    )


@pytest.mark.parametrize(
    "record",
    [
        # A hook nobody registered.
        replace(SIGNET_ABILITIES["chani"], hook="unknown"),
        # An automatic Signet line the shape does not resolve.
        Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(EffectSection(rewards=(SummonSandworm(),)),),
            mark=AbilityMark.AUTOMATIC,
        ),
        # A Signet draw beside another gain.
        replace(
            SIGNET_ABILITIES["muad_dib"],
            sections=(
                *SIGNET_ABILITIES["muad_dib"].sections,
                EffectSection(rewards=(GainResources(solari=1),)),
            ),
        ),
        # A payment the payment handler does not pay.
        replace(
            SIGNET_ABILITIES["reverend_mother_jessica"],
            sections=(
                EffectSection(
                    rewards=(GainResources(solari=1),), costs=(PayResources(spice=1),)
                ),
            ),
        ),
        # A mandatory Signet that is not a single Spy line.
        replace(
            SIGNET_ABILITIES["lady_margot_fenring"],
            sections=(EffectSection(rewards=(PlaceSpy(),)),),
        ),
    ],
)
def test_the_signet_rules_refuse_records_they_cannot_resolve(
    record: Ability, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leader_abilities, "SIGNET_ABILITIES", {"face": record})
    with pytest.raises(ValueError):
        leader_abilities._check_signet_records()
