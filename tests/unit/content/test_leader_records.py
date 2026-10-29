"""The Leaders' printed abilities as ability records (composed A6c, A6e)."""

from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.bloodlines.tech import TECH_TILES_BY_ID
from dune_imperium.content.rulesets import IX_LEADER_IDS_OFFERED, content_for
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    DrawPersonalCards,
    DrawTwistedIntrigueCards,
    EffectSection,
    GainResources,
    HasAlliance,
    OnAgentSentTo,
    OnCardTrashed,
    OnConflictWon,
    OnContractCompleted,
    OnOpponentAgentAtSpiedMakerSpace,
    OnReachInfluence,
    OnRoundStart,
    OnSpiceGainedInTurnAtLeast,
    PayResources,
    PlaceSpy,
    RecruitTroops,
    RecruitUndeployableTroops,
    StrengthInConflictAtLeast,
    SummonSandworm,
    Trigger,
    TroopToMemory,
    VisitedSpaceHasIcon,
)
from dune_imperium.content.uprising.leader_abilities import (
    LEADER_ABILITIES,
    SIGNET_ABILITIES,
    leader_triggers,
)
from dune_imperium.content.uprising.leaders import LEADERS
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.display.bloodlines import tech_ability_text, tech_ability_text_ko
from dune_imperium.display.effect_dsl_text import (
    condition_text,
    reward_text,
    trigger_text,
)
from dune_imperium.display.effect_dsl_text_ko import (
    condition_text_ko,
    reward_text_ko,
    trigger_text_ko,
)
from dune_imperium.display.leaders import LEADER_FACE_TEXTS
from dune_imperium.display.leaders_ko import LEADER_FACE_TEXTS_KO
from dune_imperium.rules import influence, leader_abilities
from dune_imperium.rules.agent_effects import _SIGNET_ICONS, _STAGED_SIGNETS
from dune_imperium.rules.leader_abilities import LEADER_HOOKS, SIGNET_HOOKS

# The original game's Leaders the engine plays (stage P2a of
# docs/base-game-and-ix-plan.md; P2b adds the other four, one at a time).
_IMPERIUM_PLAYED = frozenset(
    leader.leader_id
    for leader in content_for(RulesetConfig(base_game=BaseGame.IMPERIUM)).leaders
)
# Rise of Ix's Leaders the engine plays (stage P4e, one at a time;
# ``rulesets.IX_LEADER_IDS_OFFERED``).
_IX_PLAYED = IX_LEADER_IDS_OFFERED


def test_every_leader_face_but_the_steersman_prints_a_signet_record() -> None:
    faces = {
        face
        for leader in LEADERS
        for face in (leader.setup_face_id or leader.leader_id, leader.alternate_face_id)
        if face is not None
    }
    assert (
        set(SIGNET_ABILITIES)
        == faces - {"steersman_y_rkoon"} | _IMPERIUM_PLAYED | _IX_PLAYED
    )
    assert len(SIGNET_ABILITIES) == 18 + len(_IMPERIUM_PLAYED) + len(_IX_PLAYED)
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
        # The original game's Prudent Diplomacy and Scheme (arrows).
        "duke_leto_atreides",
        "baron_vladimir_harkonnen",
        # Rise of Ix's Final Delivery (an arrow).
        "princess_yuna_moritani",
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
        # The original game's: Brutality (its "-OR-" is no choice), and the
        # three single gains, and Discipline (Prudent Diplomacy, Manipulate
        # and Scheme are hooks).
        *(
            _IMPERIUM_PLAYED
            - {"duke_leto_atreides", "helena_richese", "baron_vladimir_harkonnen"}
        ),
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
        # A recruit line with a condition: only resource lines are judged.
        replace(
            SIGNET_ABILITIES["gurney_halleck"],
            sections=(
                EffectSection(rewards=(RecruitTroops(1),), condition=HasAlliance()),
            ),
        ),
        # A condition the shape cannot judge.
        replace(
            SIGNET_ABILITIES["liet_kynes"],
            sections=(
                EffectSection(
                    rewards=(GainResources(solari=1),),
                    condition=HasAlliance(Faction.FREMEN),
                ),
            ),
        ),
    ],
)
def test_the_signet_rules_refuse_records_they_cannot_resolve(
    record: Ability, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leader_abilities, "SIGNET_ABILITIES", {"face": record})
    with pytest.raises(ValueError):
        leader_abilities._check_signet_records()


@pytest.mark.parametrize(
    ("face", "record"),
    [
        # Spice Agony's payment is offered on Lady Jessica's faces only.
        ("chani", SIGNET_ABILITIES["lady_jessica"]),
        # Arrakis Informant's rows are Lady Margot Fenring's.
        ("piter_de_vries", SIGNET_ABILITIES["lady_margot_fenring"]),
        # A Spy line with a cost the rows would not charge.
        (
            "lady_margot_fenring",
            replace(
                SIGNET_ABILITIES["lady_margot_fenring"],
                sections=(
                    EffectSection(
                        rewards=(PlaceSpy(agent_icons=(AgentIcon.CITY,)),),
                        costs=(PayResources(spice=1),),
                    ),
                ),
            ),
        ),
        # Icons on a face that is not its Leader's id (read by Leader id).
        ("reverend_mother_jessica", SIGNET_ABILITIES["lady_amber_metulli"]),
    ],
)
def test_signet_records_are_refused_on_faces_nothing_offers_them_on(
    face: str, record: Ability, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leader_abilities, "SIGNET_ABILITIES", {face: record})
    with pytest.raises(ValueError):
        leader_abilities._check_signet_records()


def test_every_leader_face_prints_its_left_box_as_records() -> None:
    """Triggered abilities with a fixed reward and two automatic Reveal
    lines are data; six flows are hooks; five rule changes are standing
    records (composed A6e)."""

    faces = {
        face
        for leader in LEADERS
        for face in (leader.setup_face_id or leader.leader_id, leader.alternate_face_id)
        if face is not None
    }
    # Glossu Rabban's Arrakis Fiefdom is setup fields, no record.
    assert set(LEADER_ABILITIES) == faces | (_IMPERIUM_PLAYED - {"glossu_rabban"}) | (
        _IX_PLAYED
    )
    records = [
        record for abilities in LEADER_ABILITIES.values() for record in abilities
    ]
    # The original game's: Ruthless Negotiator, Connections, Spice Addict's
    # standing record and its draw, and the standing Landsraad Popularity,
    # Eyes Everywhere, Prescience and Masterstroke. Rise of Ix's: the
    # standing Smuggling Operation.
    assert len(records) == 21 + 8 + 1
    assert {
        record.hook
        for record in records
        if record.hook and record.timing is not AbilityTiming.STANDING
    } == LEADER_HOOKS
    assert {
        face
        for face, abilities in LEADER_ABILITIES.items()
        for record in abilities
        if record.timing is AbilityTiming.STANDING
    } == {
        "shaddam_corrino_iv",
        "duncan_idaho",
        "gaius_helen_mohiam",
        "liet_kynes",
        "kota_odax_of_ix",
        "countess_ariana_thorvald",
        "duke_leto_atreides",
        "helena_richese",
        "paul_atreides",
        "baron_vladimir_harkonnen",
        "princess_yuna_moritani",
    }
    triggered = [record for record in records if record.trigger is not None]
    assert len(triggered) == 8 + 3
    assert all(record.mark is AbilityMark.AUTOMATIC for record in triggered)
    assert leader_triggers("lady_margot_fenring", OnReachInfluence) == (
        (OnReachInfluence(Faction.BENE_GESSERIT, 2), (GainResources(spice=2),)),
    )
    assert leader_triggers("muad_dib", OnReachInfluence) == ()


def test_the_trigger_pieces_read_as_the_cards_print_them() -> None:
    """Each trigger quotes its Leader's (or Tech tile's) printed clause."""

    english: dict[str, Trigger] = {
        "lady_margot_fenring": OnReachInfluence(Faction.BENE_GESSERIT, 2),
        "princess_irulan": OnReachInfluence(Faction.EMPEROR, 2),
        "staban_tuek": OnOpponentAgentAtSpiedMakerSpace(),
        "count_hasimir_fenring": OnCardTrashed(),
        "esmar_tuek": OnAgentSentTo("tuek_sietch"),
    }
    for face, trigger in english.items():
        printed = LEADER_FACE_TEXTS[face].ability_text
        assert trigger_text(trigger) in printed, face
        # Esmar's asterisk marks a six-player teammate (four-player here).
        printed_ko = LEADER_FACE_TEXTS_KO[face].ability_text.replace(
            "당신*이", "당신이"
        )
        assert trigger_text_ko(trigger) in printed_ko, face
    assert trigger_text(OnSpiceGainedInTurnAtLeast(3)).lower() in (
        LEADER_FACE_TEXTS["steersman_y_rkoon"].ability_text.lower()
    )
    assert trigger_text_ko(OnSpiceGainedInTurnAtLeast(3)) in (
        LEADER_FACE_TEXTS_KO["steersman_y_rkoon"].ability_text
    )
    assert trigger_text(OnRoundStart()).lower() in (
        LEADER_FACE_TEXTS["piter_de_vries"].ability_text.lower()
    )
    assert reward_text(DrawTwistedIntrigueCards(1)).lower() in (
        LEADER_FACE_TEXTS["piter_de_vries"].ability_text.lower()
    )
    assert condition_text(StrengthInConflictAtLeast(6)) in (
        LEADER_FACE_TEXTS["gurney_halleck"].ability_text
    )
    assert condition_text_ko(StrengthInConflictAtLeast(6)) in (
        LEADER_FACE_TEXTS_KO["gurney_halleck"].ability_text.replace("6*", "6")
    )
    choam = TECH_TILES_BY_ID["choam_transports"]
    assert tech_ability_text(choam).startswith(trigger_text(OnContractCompleted()))
    assert tech_ability_text_ko(choam).startswith(
        trigger_text_ko(OnContractCompleted())
    )
    array = TECH_TILES_BY_ID["planetary_array"]
    assert tech_ability_text(array).startswith(trigger_text(OnConflictWon()))
    assert tech_ability_text_ko(array).startswith(trigger_text_ko(OnConflictWon()))


@pytest.mark.parametrize(
    "record",
    [
        # A hook nobody registered.
        replace(LEADER_ABILITIES["chani"][0], hook="unknown"),
        # A trigger no firing site watches.
        Ability(
            timing=AbilityTiming.TRIGGERED,
            sections=(EffectSection(rewards=(GainResources(spice=1),)),),
            mark=AbilityMark.AUTOMATIC,
            trigger=OnConflictWon(),
        ),
        # Smuggle Spice paying in cards.
        replace(
            LEADER_ABILITIES["staban_tuek"][0],
            sections=(EffectSection(rewards=(DrawTwistedIntrigueCards(1),)),),
        ),
        # A held draw of two cards.
        replace(
            LEADER_ABILITIES["steersman_y_rkoon"][0],
            sections=(EffectSection(rewards=(DrawPersonalCards(2),)),),
        ),
        # An automatic Reveal line the passive grant does not pay.
        replace(
            LEADER_ABILITIES["gurney_halleck"][0],
            sections=(
                EffectSection(
                    rewards=(GainResources(spice=1),),
                    condition=StrengthInConflictAtLeast(6),
                ),
            ),
        ),
        # A standing record printing a line.
        replace(
            LEADER_ABILITIES["duncan_idaho"][0],
            sections=(EffectSection(rewards=(GainResources(spice=1),)),),
        ),
        # Assassin paying spice: the site reads Solari.
        replace(
            LEADER_ABILITIES["count_hasimir_fenring"][0],
            sections=(EffectSection(rewards=(GainResources(spice=1),)),),
        ),
        # A visit trigger on a space the visit code does not watch.
        replace(
            LEADER_ABILITIES["esmar_tuek"][0], trigger=OnAgentSentTo("sietch_tabr")
        ),
        # Smuggle Spice and the Twisted draw on another face: their sites
        # name their Leader.
        LEADER_ABILITIES["staban_tuek"][0],
        LEADER_ABILITIES["piter_de_vries"][0],
    ],
)
def test_the_leader_rules_refuse_left_boxes_they_cannot_resolve(
    record: Ability, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leader_abilities, "LEADER_ABILITIES", {"face": (record,)})
    with pytest.raises(ValueError):
        leader_abilities._check_leader_records()


def test_reaching_two_influence_pays_only_what_the_rules_can_pay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = replace(
        LEADER_ABILITIES["princess_irulan"][0],
        trigger=OnReachInfluence(Faction.EMPEROR, 3),
    )
    monkeypatch.setattr(influence, "LEADER_ABILITIES", {"face": (record,)})
    with pytest.raises(ValueError):
        influence._check_reach_bonuses()
