"""The Immortality ability ports (``abilities/immortality.py``).

Spec (assets checkout, ``analysis/ai/spec/``): ``immortality.md`` §3-§7 and
the AI notes of §8-§9 (the Errata at the end of the file override its body).
Each test builds a real Immortality game state, adjusts the fields a hook
reads and stubs the profile methods it calls, so the ported arithmetic and
branches are pinned with the spec's numbers (Hard level).
"""

from collections.abc import Sequence
from dataclasses import replace
from functools import cache
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import testing as _t
from dune_imperium.agents.app_ai.abilities import (
    PORTS,
    Ability,
    Answer,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
    abilities_of,
    ability_for,
)
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import immortality as imm
from dune_imperium.agents.app_ai.abilities import intrigue as intr
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    card_entity,
    intrigue_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import RECLAIMED_FORCES_REF, Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.data.constants import HARD
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.immortality import (
    GAIN_ANY_FACTION_INFLUENCE_CUSTOM,
    GAIN_RESEARCH_CUSTOM,
    GAIN_TLEILAXU_CUSTOM,
    PAY_SOLARI_FOR_TLEILAXU,
    TRASH_CUSTOM,
    TRASH_INTRIGUE_FOR_DRAW_AND_INTRIGUE,
)
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.state import GameState
from dune_imperium.rules.agent_turn import legal_agent_actions_for_card

ME = 3  # the first seat to decide in round 1 of these Immortality games
IMMORTALITY = RulesetConfig(immortality=True)
BOARD = Board(choam=False, immortality=True)
_AA = "worm.canis.abilities.ActivatedAbilities."
_PA = "worm.canis.abilities.PlayAbilities."
_TA = "worm.canis.abilities.TriggeredAbilities."


# -- states and helpers -------------------------------------------------------------


@cache
def imm_state() -> GameState:
    """Round 1, seat 3's first Agent turn of an Immortality game."""

    return _t.first_decision("turn", config=IMMORTALITY)


@cache
def effects_state() -> GameState:
    """Seat 3's first ``agent_effects`` frame (Seek Allies at the Fremkit)."""

    return _t.first_decision("agent_effects", config=IMMORTALITY)


@cache
def base_state() -> GameState:
    return _t.first_decision("turn", choam=True)


def with_me(state: GameState, **changes: object) -> GameState:
    return _t.with_player(state, ME, **changes)


def with_hand(state: GameState, *refs: str) -> GameState:
    """Seat 3 holding ``refs``; its other hand cards go to the deck (no card
    sits in two zones)."""

    me = state.players[ME]
    rest = tuple(c for c in (*me.hand, *me.deck) if c not in refs)
    discard = tuple(c for c in me.discard_pile if c not in refs)
    return with_me(state, hand=refs, deck=rest, discard_pile=discard)


def specimens(n: int) -> dict[str, int]:
    """Specimen fields keeping the 12-troop invariant (3 in the garrison)."""

    return {"specimens": n, "troops_supply": 9 - n}


def at_round(round_number: int, **changes: object) -> GameState:
    return with_me(_t.with_state(imm_state(), round_number=round_number), **changes)


def late(**changes: object) -> GameState:
    """Round 9: the Late arc."""

    return at_round(9, **changes)


def prof(state: GameState | None = None, seat: int = ME) -> Profile:
    profile = _t.make_profile(imm_state() if state is None else state, seat)
    stub(profile, is_climax=False, is_final_round=False)
    return profile


def stub(profile: Profile, **methods: object) -> Profile:
    """Replace methods on the instance; a non-callable becomes a constant."""

    for name, value in methods.items():
        if isinstance(value, Summer):
            total = value.sum
            setattr(profile, name, lambda *_a, _t=total, **_k: Summer(_t))
        elif callable(value):
            setattr(profile, name, value)
        else:
            setattr(profile, name, lambda *_a, _v=value, **_k: _v)
    return profile


def card(ref: str) -> Entity:
    return card_entity(ref, ME)


def imperium(name: str, copy: int = 0) -> str:
    return f"imperium:{name}:{copy}"


def tleilaxu(name: str, copy: int = 0) -> str:
    return f"tleilaxu:{name}:{copy}"


def intrigue(name: str, copy: int = 0) -> str:
    return f"intrigue:{name}:{copy}"


def research(space_id: str) -> Entity:
    return Entity(Kind.SPACE, f"research:{space_id}", None)


def space(space_id: str) -> Entity:
    return space_entity(space_id, BOARD)


def req(*entities: Entity, options: tuple[int, ...] = ()) -> Request:
    return Request(infos=(TargetInfo(entities=tuple(entities), options=options),))


def ability(cls: type[Any], owner: Entity) -> Any:
    return cls(owner)


def with_frame(**changes: str) -> GameState:
    """Seat 3's ``agent_effects`` frame with its context changed."""

    state = effects_state()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    changed = replace(frame, context=tuple(sorted(context.items())))
    return _t.with_state(state, decision_stack=(*state.decision_stack[:-1], changed))


def with_graft(card_ref: str, partner_ref: str) -> GameState:
    """Seat 3's open Agent turn grafting ``card_ref`` with ``partner_ref``."""

    return with_frame(card_id=card_ref, graft_card_id=partner_ref)


# =================================================================================
# Coverage
# =================================================================================

_PLAYMAT = (
    _AA + "Immortality.ReturnSpecimenAbility",
    _AA + "Immortality.FamilyAtomicsAbility",
    _AA + "UsurpTrashAbility",
    _TA + "Immortality.ChairdogReturnAbility",
    GAIN_TLEILAXU_CUSTOM,
    GAIN_RESEARCH_CUSTOM,
    GAIN_ANY_FACTION_INFLUENCE_CUSTOM,
    TRASH_INTRIGUE_FOR_DRAW_AND_INTRIGUE,
    PAY_SOLARI_FOR_TLEILAXU,
    TRASH_CUSTOM,
    _AA + "GainIntrigueCustomAbility",
    _AA + "HighPriorityTravelDeployUnitsCustomAbility",
)


def _immortality_archetypes() -> list[str]:
    shorts = [
        short
        for short in (*CARD_ARCHETYPES.values(), *INTRIGUE_ARCHETYPES.values())
        if ".Immortality." in short or short.startswith("TleilaxuArchetypes.")
    ]
    shorts.append("SpaceArchetypes.Immortality.ResearchStationImmortality")
    return shorts


def test_every_immortality_ability_resolves_to_a_port() -> None:
    shorts = _immortality_archetypes()
    assert len(shorts) == 26 + 20 + 11 + 1  # Imperium + Tleilaxu + Intrigue + space
    for short in shorts:
        owner = Entity(Kind.CARD, short, ARCHETYPES[short])
        ids = owner.list_attr("WormAbilityIDs")
        assert ids, short
        for ability_id in ids:
            port = ability_for(ability_id, owner)
            assert not isinstance(port, UnportedAbility), (short, ability_id)
    for ability_id in _PLAYMAT:
        assert ability_id in PORTS, ability_id


def test_ports_mirror_the_app_inheritance() -> None:
    """``worm-canis.dll.cs`` base classes."""

    assert issubclass(imm.ChairdogAgentAbility, imm.GraftAgentAbility)
    assert issubclass(imm.GholaAgentAbility, imm.GraftAgentAbility)
    assert issubclass(imm.UsurpAgentAbility, imm.GraftAgentAbility)
    assert issubclass(imm.GraftAgentAbility, g.AgentAbility)
    assert issubclass(imm.SpecimenGraftedAgentAbility, imm.SpecimenAgentAbility)
    assert issubclass(imm.GainResearchCustomAbility, imm.GainResearchAbility)
    assert issubclass(
        imm.GainTleilaxuInfluenceCustomAbility, imm.GainTleilaxuInfluenceAbility
    )
    assert issubclass(imm.ReclaimedForcesAcquireAbility, g.AcquireAbility)
    assert issubclass(imm.ForHumanityAgentAbility, g.GainAnyInfluenceAbility)
    assert issubclass(imm.InterstellarConspiracyAbility, g.GainAnyInfluenceAbility)
    assert issubclass(
        imm.GainAnyFactionInfluenceCustomAbility, g.GainAnyInfluenceCustomAbility
    )
    assert issubclass(imm.SardaukarQuartermasterDrawAbility, g.DrawAbility)
    assert issubclass(imm.UnnaturalReflexesAbility, g.DrawAbility)
    assert issubclass(
        imm.HighPriorityTravelDeployUnitsCustomAbility, g.DeployUnitsAbility
    )
    assert issubclass(imm.LisanAlGaibRevealAbility, g.BondAbility)
    assert issubclass(imm.StillsuitManufacturerRevealAbility, g.BondAbility)
    assert issubclass(imm.CounterattackCombatAbility, intr.StrengthIntrigueAbility)
    assert issubclass(imm.ViciousTalentsAbility, intr.StrengthIntrigueAbility)
    assert not issubclass(
        imm.EconomicPositioningCombatAbility, intr.StrengthIntrigueAbility
    )
    assert issubclass(imm.BeneTleilaxResearcherRevealAbility, g.RevealAbility)


# Engine-side members read from each ``.ctor`` / override (asm scan).
_ENGINE_MEMBERS: list[tuple[type[Any], Timing, SelectionMode | None, bool]] = [
    (imm.GainResearchAgentAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.GainResearchRevealAbility, Timing.REVEAL, SelectionMode.EXPLICIT, False),
    (imm.GainResearchCustomAbility, Timing.NONE, SelectionMode.EXPLICIT, False),
    (
        imm.GainTleilaxuInfluenceAgentAbility,
        Timing.AGENT,
        SelectionMode.EXPLICIT,
        False,
    ),
    (imm.GainTleilaxuInfluenceCustomAbility, Timing.NONE, SelectionMode.EXPLICIT, True),
    (imm.TrashIntrigueForDrawAndIntrigue, Timing.NONE, SelectionMode.OPTIONAL, False),
    (imm.PaySolariForTleilaxuInfluence, Timing.NONE, SelectionMode.OPTIONAL, False),
    (imm.ReturnSpecimenAbility, Timing.NONE, SelectionMode.OPTIONAL, False),
    (imm.FamilyAtomicsAbility, Timing.NONE, SelectionMode.OPTIONAL, False),
    (imm.UsurpTrashAbility, Timing.AGENT, SelectionMode.IMPLICIT, True),
    (imm.BeneTleilaxLabAbility, Timing.REVEAL, SelectionMode.EXPLICIT, True),
    (imm.CorruptSmugglerAbility, Timing.AGENT, SelectionMode.EXPLICIT, True),
    (imm.DissectingKitAgentAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.DissectingKitRevealAbility, Timing.REVEAL, SelectionMode.EXPLICIT, False),
    (imm.ForHumanityAgentAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.ForHumanityRevealAbility, Timing.REVEAL, SelectionMode.OPTIONAL, False),
    (imm.HighPriorityTravelAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.ImperiumCeremonyAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.InterstellarConspiracyAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.KeysToPowerAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.LisanAlGaibAgentAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.LongReachAgentAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.OrganMerchantsAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.ReplacementEyesAgentAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (
        imm.SardaukarQuartermasterTroopAbility,
        Timing.AGENT,
        SelectionMode.EXPLICIT,
        True,
    ),
    (
        imm.StillsuitManufacturerAgentAbility,
        Timing.AGENT,
        SelectionMode.EXPLICIT,
        False,
    ),
    (imm.InTheShadowsRevealAbility, Timing.REVEAL, SelectionMode.EXPLICIT, False),
    (imm.TleilaxuMasterAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.TleilaxuSurgeonAgentAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.TleilaxuSurgeonRevealAbility, Timing.REVEAL, SelectionMode.OPTIONAL, False),
    (imm.BeguilingPheromonesAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.CorrinoGenesAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.GuildImpersonatorAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (
        imm.IndustrialEspionageResearchAbility,
        Timing.AGENT,
        SelectionMode.EXPLICIT,
        False,
    ),
    (imm.ScientificBreakthroughAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.SligFarmerSolariAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.SligFarmerTleilaxuAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.StitchedHorrorAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.SubjectX137Ability, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.TleilaxuInfiltratorAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (imm.TwistedMentatAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.PiterGeniusAdvisorAbility, Timing.AGENT, SelectionMode.OPTIONAL, False),
    (imm.UnnaturalReflexesAbility, Timing.AGENT, SelectionMode.EXPLICIT, False),
    (
        imm.SardaukarQuartermasterDrawAbility,
        Timing.AGENT,
        SelectionMode.EXPLICIT,
        False,
    ),
    (imm.LisanAlGaibRevealAbility, Timing.REVEAL, None, False),
    (imm.StillsuitManufacturerRevealAbility, Timing.REVEAL, None, False),
    (imm.BeneTleilaxResearcherRevealHelixAbility, Timing.REVEAL, None, False),
    (imm.BeneTleilaxResearcherRevealDoubleHelixAbility, Timing.REVEAL, None, False),
    (imm.ShowOfStrengthAbility, Timing.AGENT, None, False),
    (imm.HarvestCellsAbility, Timing.COMBAT_RESOLUTION, None, False),
    (imm.EconomicPositioningCombatAbility, Timing.COMBAT, None, False),
    (imm.GruesomeSacrificeAbility, Timing.COMBAT, None, False),
]


@pytest.mark.parametrize(("cls", "timing", "mode", "always"), _ENGINE_MEMBERS)
def test_engine_members(
    cls: type[Any], timing: Timing, mode: SelectionMode | None, always: bool
) -> None:
    port = cls(card(imperium("dissecting_kit")))
    p = prof()
    assert port.timing == timing
    if mode is not None:
        assert port.selection_mode(p) == mode
        assert port.always_run_immediately is always


def test_twisted_mentat_is_contextually_deferred() -> None:
    assert imm.TwistedMentatAbility.contextually_deferred is True


def test_constants_used_by_the_abilities() -> None:
    """immortality.md §10 (equal on all three levels)."""

    c = HARD
    assert c.ResearchTrackSpace17NoBadIntrigueMod == 1.0
    assert c.ResearchTrackSpace21ThirdSpaceMod == 0.33
    assert c.TwistedMentatBonus == 5.0
    assert c.AcquireTleilaxuReserveThreshold == 1.0
    assert c.AcquireTleilaxuReservePenalty == -5.0
    assert c.GraftFewRemainingSpaceTargetsPenalty == -4.0
    assert c.GraftBothCardsHaveGraftPenalty == -1.5
    assert c.GraftAgentIconsPenalty == -3.0
    assert c.TleilaxuHighCostCardsSynergyMod == 0.5
    assert c.TleilaxuSwordmasterSynergyBonus == 1.0
    assert c.TleilaxuSligFarmerCardCountOffset == 2.0
    assert c.TleilaxuSligFarmerCardCountMod == 0.5
    assert c.TleilaxuReclaimForcesLateGameBonus == 0.5
    assert c.TleilaxuReclaimForcesNotLateGameMod == -0.5
    assert c.TleilaxuReclaimForcesVPBonus == 2.0
    assert c.ChairdogGraftRevealMod == 0.66
    assert c.DissectingKitCardCostMod == -0.5
    assert c.HighPriorityTravelAgentMod == 0.5
    assert c.ReplacementEyesAgentMod == 3.5
    assert c.ImperiumCeremonyMod == 1.33
    assert c.StillsuitManufacturerMod == 1.0


# =================================================================================
# §3.1 Research and §3.2 Tleilaxu
# =================================================================================


def test_gain_research_value_is_research_value() -> None:
    p = stub(prof(), research_value=Summer(2.25 + 0.75))
    port = imm.GainResearchAgentAbility(card(imperium("experimentation")))
    assert port.value_for_player(p, ()).sum == 3.0


def test_gain_research_picks_the_best_next_space_with_the_floor() -> None:
    values = {"c2r2": 1.25, "c2r4": 2.25}
    p = stub(prof(), research_space_value=lambda sid: Summer(values[sid]))
    port = imm.GainResearchCustomAbility(research("c1r3"))
    answer = port.evaluate(p, req(research("c2r2"), research("c2r4")))
    assert answer.value == 2.25 + 1.0
    assert answer.response == (("research:c2r4",),)


def test_gain_research_keeps_no_space_when_a_space_is_worth_nothing() -> None:
    """Errata §3.1: the baseline stores an empty entity list (Array.Empty), so
    a space at exactly 1.0 (SpaceValue 0) does not replace it."""

    p = stub(prof(), research_space_value=lambda sid: Summer(0.0))
    port = imm.GainResearchAgentAbility(card(imperium("experimentation")))
    answer = port.evaluate(p, req(research("c1r3")))
    assert answer.value == 1.0
    assert answer.response == ((),)


def test_gain_research_ties_keep_the_first_space() -> None:
    p = stub(prof(), research_space_value=lambda sid: Summer(1.0))
    port = imm.GainResearchAgentAbility(card(imperium("experimentation")))
    answer = port.evaluate(p, req(research("c2r2"), research("c2r4")))
    assert answer.response == (("research:c2r2",),)


def test_gain_research_cost_needs_a_drawable_card_after_two_markers() -> None:
    port = imm.GainResearchAgentAbility(card(imperium("experimentation")))
    assert port.meets_cost(prof())
    two = with_me(imm_state(), research_space="c8r2", deck=(), discard_pile=())
    assert not port.meets_cost(prof(two))


def test_gain_research_with_the_real_space_value() -> None:
    """End to end: research space c1r3 grants one specimen (Poor x 1.25)."""

    p = prof()
    port = imm.GainResearchAgentAbility(card(imperium("experimentation")))
    answer = port.evaluate(p, req(research("c1r3")))
    assert answer.value == p.research_space_value("c1r3").sum + 1.0
    assert answer.response == (("research:c1r3",),)


def test_gain_tleilaxu_influence_value_and_defer_value() -> None:
    p = stub(prof(), tleilaxu_value=lambda n: Summer(2.25 * n + 0.5))
    contaminator = card(tleilaxu("contaminator"))
    port = imm.GainTleilaxuInfluenceAgentAbility(contaminator)
    assert port.value_for_player(p, ()).sum == 2.75
    # E is DeferredAbility::Evaluate: the card's DeferValue (1).
    assert port.evaluate(p, Request()).value == 1.0
    assert port.meets_cost(p)
    assert not port.meets_cost(prof(with_me(imm_state(), tleilaxu_space=7)))


# =================================================================================
# §3.4 Playmat abilities
# =================================================================================


def _intrigue_hand(*names: str) -> GameState:
    return with_me(imm_state(), intrigue_cards=tuple(intrigue(n) for n in names))


def test_trash_intrigue_value_with_and_without_junk() -> None:
    port = imm.TrashIntrigueForDrawAndIntrigue(research("c7r3"))
    # Harvest Cells is junk in the Late arc.
    junk = stub(
        prof(_t.with_state(_intrigue_hand("harvest_cells"), round_number=9)),
        card_draw_value=1.5,
        buy_gains=0.25,
        possible_persuasion_gain=2,
        intrigue_value=2.0,
    )
    assert port.value_for_player(junk, ()).sum == 1.5 + 0.25 + 2.0
    clean = prof(_intrigue_hand("harvest_cells"))
    assert port.value_for_player(clean, ()).sum == 1.0


def test_trash_intrigue_picks_a_junk_card_at_five() -> None:
    state = _t.with_state(
        _intrigue_hand("harvest_cells", "breakthrough"), round_number=9
    )
    port = imm.TrashIntrigueForDrawAndIntrigue(research("c7r3"))
    targets = [
        intrigue_entity(intrigue(n), ME) for n in ("breakthrough", "harvest_cells")
    ]
    answer = port.evaluate(prof(state), req(*targets))
    assert answer.value == 5.0
    assert answer.response == ((intrigue("harvest_cells"),),)
    # No junk: no answer (the key is never chosen).
    early = prof(_intrigue_hand("harvest_cells", "breakthrough"))
    assert port.evaluate(early, req(*targets)).response is None


@pytest.mark.parametrize(
    ("solari", "rank", "priced"),
    [(7, 0, True), (7, 5, True), (6, 0, False), (7, 3, False), (7, 6, False)],
)
def test_pay_solari_for_tleilaxu(solari: int, rank: int, priced: bool) -> None:
    state = with_me(imm_state(), tleilaxu_space=rank)
    me = state.players[ME]
    state = with_me(state, resources=replace(me.resources, solari=solari))
    p = prof(state)
    port = imm.PaySolariForTleilaxuInfluence(research("c8r6"))
    value = port.value_for_player(p, ()).sum
    if priced:
        two, three = p.tleilaxu_value(2).sum, p.tleilaxu_value(3).sum
        assert value == two + 0.33 * (three - two)
    else:
        assert value == 0.0
    assert port.evaluate(p, Request()).value == value


def test_pay_solari_from_rank_zero_with_real_numbers() -> None:
    """Rank 0, Early: two steps 4.5 + the intrigue at 2 (1.0) = 5.5; three
    steps 6.75 + 1.0 = 7.75; 5.5 + 0.33 x 2.25."""

    state = with_me(imm_state(), tleilaxu_space=0)
    me = state.players[ME]
    state = with_me(state, resources=replace(me.resources, solari=8))
    port = imm.PaySolariForTleilaxuInfluence(research("c8r6"))
    assert port.value_for_player(prof(state), ()).sum == pytest.approx(5.5 + 0.7425)


def test_return_specimen_returns_exactly_the_shortfall() -> None:
    port = imm.ReturnSpecimenAbility(research("c0r3"))
    request = req(options=(0, 1, 2))
    assert port.evaluate(prof(), request).response is None
    short = prof(with_me(imm_state(), ungained_troops=2, **specimens(3)))
    answer = port.evaluate(short, request)
    assert answer.value == 1.0
    assert answer.response == ((0, 1),)


def _family_atomics(
    monkeypatch: pytest.MonkeyPatch, persuasion: int, reveal: bool = True
) -> None:
    monkeypatch.setattr(imm, "_persuasion", lambda p: persuasion)
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: reveal and turn == 2)


@pytest.mark.parametrize(
    ("persuasion", "values", "expected"),
    [
        (3, [], None),  # below 4
        (9, [], None),  # above 8
        (4, [], 100.0),  # nothing to buy
        (6, [3.0], 100.0),  # Calculus of Power (cost 3): ratio 1.0 is kept
        (6, [3.3], 0.0),  # ratio 1.1 > 1.0
        (8, [3.0, 1.5], 100.0),  # + Spy Network (cost 2): 4.5 / 5
        (8, [3.0, 2.5], 0.0),  # 5.5 / 5
    ],
)
def test_family_atomics(
    monkeypatch: pytest.MonkeyPatch,
    persuasion: int,
    values: list[float],
    expected: float | None,
) -> None:
    _family_atomics(monkeypatch, persuasion)
    cards = [card(imperium(n)) for n in ("calculus_of_power", "spy_network")]
    buys = cards[: len(values)]
    acquire = {c.ref: v for c, v in zip(buys, values, strict=True)}
    p = stub(
        prof(),
        predict_card_buys=lambda n: buys,
        acquire_value=lambda c: Summer(acquire[c.ref]),
    )
    answer = imm.FamilyAtomicsAbility(research("c0r3")).evaluate(p, Request())
    if expected is None:
        assert answer.response is None
        return
    assert answer.value == expected
    assert answer.response == ((1,),)


def test_family_atomics_only_in_the_reveal_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _family_atomics(monkeypatch, 6, reveal=False)
    answer = imm.FamilyAtomicsAbility(research("c0r3")).evaluate(prof(), Request())
    assert answer.response is None


def test_usurp_trash_and_chairdog_return_have_no_ai_hook() -> None:
    p = prof()
    for cls in (imm.UsurpTrashAbility, imm.ChairdogReturnAbility):
        port = cls(card(tleilaxu("usurp")))
        assert port.value_for_player(p, ()).sum == 0.0


# =================================================================================
# §3.5 AcquireAbility (Tleilaxu lines) and §3.6 Reclaimed Forces
# =================================================================================


def _row(*cards: str) -> GameState:
    state = imm_state()
    return _t.with_state(
        state,
        tleilaxu_row=cards,
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c not in cards),
    )


def test_acquire_imperium_card_is_never_penalised() -> None:
    """Errata §3.5: the Save Up Specimens line needs a Tleilaxu card."""

    state = _row(tleilaxu("twisted_mentat"), tleilaxu("usurp"))
    p = stub(
        prof(state), acquire_value=lambda c: Summer(9.0 if "tleilaxu" in c.ref else 3.0)
    )
    answer = g.AcquireAbility(card(imperium("calculus_of_power"))).evaluate(
        p, Request()
    )
    assert answer.value == 3.0


def test_acquire_tleilaxu_card_saves_up_for_a_better_one() -> None:
    state = _row(tleilaxu("contaminator"), tleilaxu("usurp"))
    values = {
        tleilaxu("contaminator"): 2.0,
        tleilaxu("usurp"): 3.5,  # costs 4 > 0 specimens; 3.5 > 2.0 + 1.0
        RECLAIMED_FORCES_REF: 0.0,
    }
    p = stub(prof(state), acquire_value=lambda c: Summer(values[c.ref]))
    contaminator = card(tleilaxu("contaminator"))
    answer = g.AcquireAbility(contaminator).evaluate(p, Request())
    assert answer.value == 2.0 - 5.0
    # Worth exactly current + 1.0: not strictly more, no penalty.
    values[tleilaxu("usurp")] = 3.0
    assert g.AcquireAbility(contaminator).evaluate(p, Request()).value == 2.0
    # Affordable (specimens == cost): no penalty.
    values[tleilaxu("usurp")] = 9.0
    rich = stub(
        prof(with_me(state, **specimens(4))),
        acquire_value=lambda c: Summer(values[c.ref]),
    )
    assert g.AcquireAbility(contaminator).evaluate(rich, Request()).value == 2.0


def test_acquire_tleilaxu_card_in_the_final_round_values_its_effects() -> None:
    state = _row(tleilaxu("subject_x_137"), tleilaxu("usurp"))
    p = stub(
        prof(state),
        is_final_round=True,
        acquire_value=lambda c: Summer(7.0),
        acquire_effects_value=lambda c: Summer(2.25),
    )
    answer = g.AcquireAbility(card(tleilaxu("subject_x_137"))).evaluate(p, Request())
    assert answer.value == 2.25


def test_acquire_tleilaxu_destination_picker_takes_option_zero() -> None:
    state = _row(tleilaxu("contaminator"), tleilaxu("usurp"))
    p = stub(prof(state), acquire_value=lambda c: Summer(1.0))
    picker = Request(infos=(TargetInfo(options=(0, 1)),))
    answer = g.AcquireAbility(card(tleilaxu("contaminator"))).evaluate(p, picker)
    assert answer.response == ((0,),)


def test_reclaimed_forces_specific_acquire_value() -> None:
    port = imm.ReclaimedForcesAcquireAbility(card(RECLAIMED_FORCES_REF))
    assert port.specific_acquire_value(prof()).sum == -0.5
    assert port.specific_acquire_value(prof(late())).sum == 0.5
    assert port.specific_acquire_value(prof(late(tleilaxu_space=3))).sum == 2.5
    assert port.specific_acquire_value(prof(at_round(1, tleilaxu_space=6))).sum == 1.5
    assert port.specific_acquire_value(prof(late(tleilaxu_space=4))).sum == 0.5


def test_reclaimed_forces_value_for_player_read_in_the_binary() -> None:
    port = imm.ReclaimedForcesAcquireAbility(card(RECLAIMED_FORCES_REF))
    assert port.value_for_player(prof(), ()).sum == 0.0
    assert port.value_for_player(prof(late()), ()).sum == 0.5


def test_reclaimed_forces_acquire_value_through_the_profile() -> None:
    """§2.5: SpecimenCost 3 is the base, plus its own S (-0.5 early)."""

    entity = card_entity(RECLAIMED_FORCES_REF)
    assert prof().acquire_value(entity).sum == 3.0 - 0.5


@pytest.mark.parametrize(
    ("troops", "tleilaxu_v", "option"),
    [(3.0, 2.25, 0), (2.25, 2.25, 1), (2.0, 2.25, 1)],
)
def test_reclaimed_forces_option(troops: float, tleilaxu_v: float, option: int) -> None:
    p = stub(
        prof(),
        acquire_value=lambda c: Summer(2.5),
        troop_value=lambda n, posture=False: troops,
        tleilaxu_value=lambda n: Summer(tleilaxu_v),
    )
    answer = imm.ReclaimedForcesAcquireAbility(card(RECLAIMED_FORCES_REF)).evaluate(
        p, Request()
    )
    assert answer.value == 2.5
    assert answer.response == ((option,),)


def test_reclaimed_forces_floor_outside_the_reveal_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = stub(
        prof(),
        acquire_value=lambda c: Summer(-1.0),
        troop_value=lambda n, posture=False: 1.0,
        tleilaxu_value=lambda n: Summer(1.0),
    )
    port = imm.ReclaimedForcesAcquireAbility(card(RECLAIMED_FORCES_REF))
    assert port.evaluate(p, Request()).value == 1.0
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: turn == 2)
    assert port.evaluate(p, Request()).value == -1.0


# =================================================================================
# §4 Graft
# =================================================================================


class _FakeBox:
    """A stand-in agent box recording the ``with`` entities it was valued with."""

    def __init__(self, value: float) -> None:
        self.value = value
        self.calls: list[tuple[str, ...]] = []

    def value_for_player(self, p: Profile, with_entities: Sequence[Entity]) -> Summer:
        self.calls.append(tuple(e.ref for e in with_entities))
        return Summer(self.value)


def _graft_hand(*refs: str, agents: int = 2) -> GameState:
    state = with_hand(imm_state(), *refs)
    if agents == 1:  # one Agent already placed
        state = with_me(state, agents_available=1, agent_locations=("arrakeen",))
    return state


def test_graft_cards_value_merges_both_boxes_in_graft_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boxes = {"A": _FakeBox(3.0), "B": _FakeBox(4.5)}
    a = card(imperium("dissecting_kit"))  # Graft; Pentagon, Circle
    b = card(imperium("calculus_of_power"))  # not Graft
    monkeypatch.setattr(
        imm,
        "_first_agent_ability",
        lambda c: boxes["A"] if c.ref == a.ref else boxes["B"],
    )
    monkeypatch.setattr(imm, "valid_space_ids", lambda p, ref, cache: frozenset())
    p = prof(_graft_hand(a.ref, b.ref, agents=1))
    where = space("fremkit")
    s = imm.graft_cards_value(p, a, b, where)
    assert s.sum == 100.0 + 3.0 + 4.5  # one Agent left: no penalty
    assert boxes["A"].calls == [(b.ref, "fremkit")]
    assert boxes["B"].calls == [(a.ref, "fremkit")]


def _penalty_case(
    monkeypatch: pytest.MonkeyPatch,
    a_ref: str,
    b_ref: str,
    spaces: frozenset[str],
    hand: tuple[str, ...],
) -> float:
    monkeypatch.setattr(imm, "_first_agent_ability", lambda c: None)
    monkeypatch.setattr(imm, "valid_space_ids", lambda p, ref, cache: spaces)
    p = prof(_graft_hand(*hand))
    return imm.graft_cards_value(p, card(a_ref), card(b_ref), space("fremkit")).sum


def test_graft_penalties(monkeypatch: pytest.MonkeyPatch) -> None:
    kit = imperium("dissecting_kit")  # Graft; Pentagon, Circle
    calculus = imperium("calculus_of_power")  # Emperor icon
    researcher = imperium("bene_tleilax_researcher")  # Graft; Pentagon
    other = imperium("spy_network")
    two = frozenset({"fremkit", "arrakeen"})
    one = frozenset({"fremkit"})
    # The Graft card's icons are not all on the partner: no penalty.
    assert _penalty_case(monkeypatch, kit, calculus, two, (kit, calculus, other)) == 100
    # Few remaining spaces: -4.
    assert (
        _penalty_case(monkeypatch, kit, calculus, one, (kit, calculus, other)) == 96.0
    )
    # Both Graft: -1.5 (the icon test is skipped).
    assert (
        _penalty_case(monkeypatch, kit, researcher, two, (kit, researcher, other))
        == 98.5
    )


def test_graft_icon_penalty_when_the_partner_covers_every_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interstellar Conspiracy (Graft; Circle) with Occupation (not Graft;
    Circle among its icons): the Graft card adds no icon, -3."""

    conspiracy = imperium("interstellar_conspiracy")
    occupation = imperium("occupation")
    other = "player:3:starter:dagger:0"
    hand = (conspiracy, occupation, other)
    two = frozenset({"a", "b"})
    assert _penalty_case(monkeypatch, conspiracy, occupation, two, hand) == 97.0
    # B the Graft card (the state-50 evaluator's order): the same test.
    assert _penalty_case(monkeypatch, occupation, conspiracy, two, hand) == 97.0
    # The last hand cards gone: few spaces left too (-4).
    assert _penalty_case(monkeypatch, conspiracy, occupation, two, hand[:2]) == 93.0


def test_usurp_without_icons_always_gets_the_icon_penalty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usurp = tleilaxu("usurp")
    calculus = imperium("calculus_of_power")
    hand = (usurp, calculus, "player:3:starter:dagger:0")
    two = frozenset({"a", "b"})
    assert _penalty_case(monkeypatch, usurp, calculus, two, hand) == 97.0


def test_graft_card_evaluator(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {imperium("calculus_of_power"): 104.0, imperium("spy_network"): 104.0}
    monkeypatch.setattr(
        imm,
        "graft_cards_value",
        lambda p, first, second, where, cache=None: Summer(values[first.ref]),
    )
    p = prof()
    targets = req(*(card(r) for r in values))
    played = card(imperium("dissecting_kit"))
    answer = imm.graft_card_evaluate(p, targets, played, space("fremkit"))
    assert answer.value == 104.0
    assert answer.response == ((imperium("calculus_of_power"),),)  # first wins ties
    # A card without the Graft tag never takes an optional partner.
    plain = card(imperium("calculus_of_power"))
    assert imm.graft_card_evaluate(p, targets, plain, space("fremkit")).response is None


def test_graft_agent_ability_values_spaces_with_the_best_partner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit = imperium("dissecting_kit")
    partners = (imperium("calculus_of_power"), imperium("spy_network"))
    pair = {
        ("fremkit", partners[0]): 103.0,
        ("fremkit", partners[1]): 105.0,
        ("arrakeen", partners[0]): 0.0,  # never kept: not above 0
        ("arrakeen", partners[1]): -2.0,
    }
    monkeypatch.setattr(
        imm,
        "graft_cards_value",
        lambda p, first, second, where, cache=None: Summer(
            pair[(where.ref, second.ref)]
        ),
    )
    p = prof(with_hand(imm_state(), kit, *partners))
    port = imm.GraftAgentAbility(card(kit))
    request = req(space("fremkit"), space("arrakeen"))
    best = port.best_partners(p, request)
    assert [(s.ref, c.ref) for s, c, _ in best] == [("fremkit", partners[1])]
    fremkit_v = Summer()
    for a in abilities_of(space("fremkit")):
        fremkit_v.merge(a.value_for_player(p, ()))
    assert best[0][2] == fremkit_v.sum + 105.0
    answer = port.evaluate(p, request)
    assert answer.value == fremkit_v.sum + 105.0
    assert answer.response == (("fremkit",),)


def test_graft_card_without_a_partner_is_never_played() -> None:
    kit = imperium("dissecting_kit")
    p = prof(with_hand(imm_state(), kit))
    answer = imm.GraftAgentAbility(card(kit)).evaluate(p, req(space("fremkit")))
    assert answer.response is None


def test_graft_agent_ability_end_to_end() -> None:
    """Real boxes and real valid spaces: base 100 dominates."""

    kit = imperium("dissecting_kit")
    hand = (kit, "player:3:starter:dagger:0", "player:3:starter:diplomacy:0")
    p = prof(with_hand(imm_state(), *hand))
    answer = imm.GraftAgentAbility(card(kit)).evaluate(p, req(space("fremkit")))
    assert answer.value > 100.0
    assert answer.response == (("fremkit",),)


def test_valid_space_ids_reads_the_engine_placements() -> None:
    """``WormBoard::ValidSpaces(card, P, null)``: the engine's placements of
    a hand card played alone."""

    state = imm_state()
    cache: imm.SpaceCache = {}
    p = prof(state)
    for ref in state.players[ME].hand:
        legal = {
            str(dict(a.arguments)["space_id"])
            for a in legal_agent_actions_for_card(state, ME, ref)
        }
        assert imm.valid_space_ids(p, ref, cache) == legal, ref
    assert set(cache) == set(state.players[ME].hand)


def test_usurp_graft_targets_include_the_imperium_row() -> None:
    usurp = tleilaxu("usurp")
    state = with_hand(imm_state(), usurp, imperium("dissecting_kit"))
    port = imm.UsurpAgentAbility(card(usurp))
    refs = [c.ref for c in port.graft_targets(prof(state))]
    assert refs == [imperium("dissecting_kit"), *state.imperium_row]


def test_usurp_values_a_row_partner_at_four() -> None:
    state = imm_state()
    usurp = card(tleilaxu("usurp"))
    port = imm.UsurpAgentAbility(usurp)
    p = prof(state)
    row_card = card_entity(state.imperium_row[0])
    plain = port.value_for_player(
        p, (card(imperium("dissecting_kit")), space("fremkit"))
    )
    with_row = port.value_for_player(p, (row_card, space("fremkit")))
    assert with_row.sum - plain.sum == 4.0


def test_chairdog_values_the_partner_reveal() -> None:
    """The partner's first reveal box x ``ChairdogGraftRevealMod`` (0.66)."""

    chairdog = card(tleilaxu("chairdog"))
    partner = card(imperium("calculus_of_power"))
    port = imm.ChairdogAgentAbility(chairdog)
    p = prof()
    alone = port.value_for_player(p, (space("fremkit"),)).sum
    grafted = port.value_for_player(p, (partner, space("fremkit"))).sum
    reveal_box = next(
        a for a in abilities_of(partner) if isinstance(a, g.RevealAbility)
    )
    t = reveal_box.value_for_player(p, ())
    assert t.sum > 0.0
    t.multiply("x", 0.66)
    assert grafted - alone == pytest.approx(t.sum)


def test_chairdog_and_ghola_specific_acquire_value() -> None:
    expensive = (imperium("keys_to_power"), imperium("for_humanity"))  # 5 and 7
    state = with_me(imm_state(), discard_pile=expensive)
    for cls in (imm.ChairdogAgentAbility, imm.GholaAgentAbility):
        port = cls(card(tleilaxu("chairdog")))
        assert port.specific_acquire_value(prof(state)).sum == 1.0
        assert port.specific_acquire_value(prof()).sum == 0.0


@pytest.mark.parametrize(
    ("partner", "penalty"),
    [
        (imperium("dissecting_kit"), -1),
        (imperium("tleilaxu_surgeon"), -1),
        (imperium("occupation"), -3),
        ("player:3:starter:seek_allies:0", -5),
        (tleilaxu("usurp"), -5),
        (imperium("calculus_of_power"), 0),
    ],
)
def test_ghola_graft_penalty_lists(partner: str, penalty: int) -> None:
    port = imm.GholaAgentAbility(card(tleilaxu("ghola")))
    assert port.ghola_graft_penalty(prof(), card(partner).short, None) == penalty


def test_ghola_graft_penalty_conditions() -> None:
    port = imm.GholaAgentAbility(card(tleilaxu("ghola")))
    haven = "ImperiumArchetypes.Uprising.SmugglersHaven"
    poor = prof()
    assert port.ghola_graft_penalty(poor, haven, None) == -5
    me = imm_state().players[ME]
    rich = with_me(imm_state(), resources=replace(me.resources, spice=8))
    assert port.ghola_graft_penalty(prof(rich), haven, None) == 0
    price = "ImperiumArchetypes.Uprising.PriceisNoObject"
    assert port.ghola_graft_penalty(poor, price, None) == -5
    fighters = "ImperiumArchetypes.Uprising.LongLivetheFighters"
    assert port.ghola_graft_penalty(poor, fighters, None) == -5  # 3 cards in deck
    junction = "ImperiumArchetypes.Uprising.JunctionHeadquarters"
    assert port.ghola_graft_penalty(poor, junction, None) == -5  # no Guild alliance


def test_ghola_copies_the_partner_box_as_grafted() -> None:
    ghola = card(tleilaxu("ghola"))
    partner = card(imperium("calculus_of_power"))
    port = imm.GholaAgentAbility(ghola)
    p = prof()
    where = space("fremkit")
    alone = g.AgentAbility.value_for_player(port, p, (partner, where)).sum
    copied = _first_box(partner).value_for_player(p, (ghola, where)).sum
    assert port.value_for_player(p, (partner, where)).sum == pytest.approx(
        alone + copied
    )
    # A Ghola partner is not copied.
    other = card(tleilaxu("ghola", 1))
    assert port.value_for_player(p, (other, where)).sum == pytest.approx(
        g.AgentAbility.value_for_player(port, p, (other, where)).sum
    )


@pytest.mark.parametrize(
    ("partner", "penalty"),
    [
        (imperium("dissecting_kit"), -1.0),
        (imperium("occupation"), -3.0),
        ("player:3:starter:seek_allies:0", -5.0),
    ],
)
def test_ghola_penalty_replaces_the_copied_box(partner: str, penalty: float) -> None:
    """``GholaAgentAbility::ValueForPlayer @0x4c6da30``: a non-zero copy
    penalty is added and the method returns (``jmp 0x4c6de60``); the
    partner's box is copied only when the penalty is 0."""

    ghola = card(tleilaxu("ghola"))
    other = card(partner)
    port = imm.GholaAgentAbility(ghola)
    p = prof()
    where = space("fremkit")
    alone = g.AgentAbility.value_for_player(port, p, (other, where)).sum
    assert _first_box(other).value_for_player(p, (ghola, where)).sum != 0.0
    assert port.value_for_player(p, (other, where)).sum == pytest.approx(
        alone + penalty
    )


def _first_box(c: Entity) -> g.AgentAbility:
    box = next(a for a in abilities_of(c) if isinstance(a, g.AgentAbility))
    assert isinstance(box, g.AgentAbility)
    return box


def test_convert_specimen_takes_every_specimen() -> None:
    answer = imm.convert_specimen_evaluate(req(options=(0, 1)))
    assert answer.value == 100.0
    assert answer.response == ((0, 1),)


def test_deferred_threshold_counts_the_graft_partner() -> None:
    """engine-order §4.1: Seek Allies (no DeferValue) grafted with Replacement
    Eyes (2) at the Fremkit (1): 3 reaches the threshold."""

    state = effects_state()
    assert not g.deferred_threshold_reached(prof(state))
    grafted = with_graft("player:3:starter:seek_allies:0", imperium("replacement_eyes"))
    assert g.deferred_threshold_reached(prof(grafted))


# =================================================================================
# §5 Imperium cards
# =================================================================================


def test_bene_tleilax_lab_spice_with_a_marker() -> None:
    port = imm.BeneTleilaxLabAbility(card(imperium("bene_tleilax_lab")))
    assert port.value_for_player(prof(), ()).sum == 0.0
    marked = prof(with_me(imm_state(), research_space="c4r2"))
    assert port.value_for_player(marked, ()).sum == marked.spice_value(1)


@pytest.mark.parametrize(
    ("cls", "markers", "priced"),
    [
        (imm.BeneTleilaxResearcherRevealHelixAbility, 0, False),
        (imm.BeneTleilaxResearcherRevealHelixAbility, 1, True),
        (imm.BeneTleilaxResearcherRevealDoubleHelixAbility, 1, False),
        (imm.BeneTleilaxResearcherRevealDoubleHelixAbility, 2, True),
    ],
)
def test_bene_tleilax_researcher_persuasion(
    cls: type[Any], markers: int, priced: bool
) -> None:
    research_space = {0: "c0r3", 1: "c4r2", 2: "c8r2"}[markers]
    p = prof(with_me(imm_state(), research_space=research_space))
    port = cls(card(imperium("bene_tleilax_researcher")))
    assert port.value_for_player(p, ()).sum == (p.persuasion_value(1) if priced else 0)


def test_corrupt_smuggler_spice_only_grafted() -> None:
    p = prof()
    port = imm.CorruptSmugglerAbility(card(imperium("corrupt_smuggler")))
    assert port.value_for_player(p, (space("fremkit"),)).sum == 0.0
    grafted = port.value_for_player(p, (card(tleilaxu("chairdog")), space("fremkit")))
    assert grafted.sum == p.spice_value(2)


def test_dissecting_kit_agent_value() -> None:
    p = stub(prof(), specimen_value=lambda n: 1.25 * n)
    port = imm.DissectingKitAgentAbility(card(imperium("dissecting_kit")))
    assert port.value_for_player(p, (space("fremkit"),)).sum == 0.0
    # Calculus of Power: no TrashValue, PersuasionCost 3: 3 x -0.5.
    imperium_partner = card(imperium("calculus_of_power"))
    value = port.value_for_player(p, (imperium_partner, space("fremkit"))).sum
    assert value == 3 * -0.5 + 0.0 + 1.25
    # A Tleilaxu partner: 1.5 x SpecimenCost (Chairdog 2) x -0.5.
    chairdog = card(tleilaxu("chairdog"))
    value = port.value_for_player(p, (chairdog, space("fremkit"))).sum
    assert value == 1.5 * 2 * -0.5 + 1.25
    # Replacement Eyes has TrashValue 0.1: no cost term.
    eyes = card(imperium("replacement_eyes"))
    assert port.value_for_player(p, (eyes, space("fremkit"))).sum == 0.1 + 1.25
    assert port.evaluate(p, Request()).value == 100.0


def test_dissecting_kit_reveal() -> None:
    port = imm.DissectingKitRevealAbility(card(imperium("dissecting_kit")))
    assert port.value_for_player(prof(), ()).sum == 0.0
    marked = prof(with_me(imm_state(), research_space="c4r2"))
    assert port.value_for_player(marked, ()).sum == marked.tleilaxu_value(1).sum


def test_for_humanity_reveal() -> None:
    port = imm.ForHumanityRevealAbility(card(imperium("for_humanity")))
    assert port.value_for_player(prof(), ()).sum == 0.0
    allied = with_me(imm_state(), alliance_faction_ids=("bene_gesserit",))
    p = prof(allied)
    expected = g.gain_any_influence_value(p, -2).sum + p.victory_point_value(1)
    assert port.value_for_player(p, ()).sum == expected
    tracks = [track_entity(f) for f in ("emperor", "fremen")]
    answer = port.evaluate(p, req(*tracks))
    values = [
        p.victory_point_value(1) + p.gain_influence_value(f, -2, -1, False).sum
        for f in ("emperor", "fremen")
    ]
    assert answer.value == max(values)


def test_high_priority_travel_value() -> None:
    port = imm.HighPriorityTravelAbility(card(imperium("high_priority_travel")))
    assert port.value_for_player(prof(), ()).sum == 0.0
    me = imm_state().players[ME]
    guild = with_me(imm_state(), influence=replace(me.influence, spacing_guild=2))
    p = stub(prof(guild), card_draw_value_with_buy_gains=1.75, combat_positioning=2.5)
    assert port.value_for_player(p, ()).sum == 2.5 + 0.5


def test_high_priority_travel_evaluate() -> None:
    port = imm.HighPriorityTravelAbility(card(imperium("high_priority_travel")))
    state = with_me(
        with_frame(space_id="imperial_privilege"), troops_garrison=2, troops_supply=10
    )
    keen = stub(
        prof(state),
        conflict_posture_bounds=(1.0, 3.0),
        current_conflict_interest=Summer(1.5),
        card_draw_value_with_buy_gains=1.75,
    )
    answer = port.evaluate(keen, Request())
    assert (answer.value, answer.response) == (1.0, ((1,),))
    cool = stub(
        prof(state),
        conflict_posture_bounds=(1.5, 3.0),
        current_conflict_interest=Summer(1.5),
        card_draw_value_with_buy_gains=1.75,
    )
    answer = port.evaluate(cool, Request())
    assert (answer.value, answer.response) == (1.75, ((0,),))


def test_imperium_ceremony() -> None:
    port = imm.ImperiumCeremonyAbility(card(imperium("imperium_ceremony")))
    p = stub(prof(), intrigue_value=2.0)
    assert port.value_for_player(p, ()).sum == 2.0 * 1.33
    assert port.evaluate(p, Request()).value == 2.0 * 1.33


def test_imperium_ceremony_keeps_a_good_intrigue() -> None:
    state = _t.with_state(
        _intrigue_hand("harvest_cells", "breakthrough"), round_number=9
    )
    port = imm.ImperiumCeremonyAbility(card(imperium("imperium_ceremony")))
    targets = [
        intrigue_entity(intrigue(n), ME) for n in ("harvest_cells", "breakthrough")
    ]
    for seed in range(6):
        p = _t.make_profile(state, ME, rng_seed=seed)
        answer = port.evaluate_intrigue(p, req(*targets))
        assert answer.value == 50.0
        assert answer.response == ((intrigue("breakthrough"),),)


def test_interstellar_conspiracy_value_needs_a_faction_partner() -> None:
    """Errata §5.8: a space never triggers the influence term."""

    port = imm.InterstellarConspiracyAbility(card(imperium("interstellar_conspiracy")))
    p = prof()
    base = g.gain_any_influence_value(p, 1).sum + p.spice_value(1)
    assert port.value_for_player(p, (space("imperial_privilege"),)).sum == base
    emperor = card(imperium("sardaukar_quartermaster"))  # Emperor faction
    grafted = port.value_for_player(p, (emperor, space("fremkit"))).sum
    assert grafted == base + g.gain_any_influence_value(p, 1).sum


def test_interstellar_conspiracy_pile_value() -> None:
    port = imm.InterstellarConspiracyAbility(card(imperium("interstellar_conspiracy")))
    p = prof()
    emperor = card(imperium("sardaukar_quartermaster"))
    plain = card(imperium("bene_tleilax_lab"))
    spice = p.spice_value(1)
    assert port.value_in_pile_for_other_play(p, Pile.DECK, plain).sum == spice
    assert port.value_in_pile_for_other_play(p, Pile.DECK, emperor).sum == spice + 0.75
    # The "Played" term tests the Hand pile, which the AI never passes.
    assert port.value_in_pile_for_other_play(p, Pile.PLAY_AREA, emperor).sum == spice


def test_interstellar_conspiracy_evaluate_falls_back_to_half() -> None:
    port = imm.InterstellarConspiracyAbility(card(imperium("interstellar_conspiracy")))
    p = stub(prof(), gain_influence_value=lambda *a: Summer(-1.0))
    answer = port.evaluate(p, req(track_entity("emperor")))
    assert answer.value == 0.5
    assert answer.response == ()


def test_keys_to_power() -> None:
    port = imm.KeysToPowerAbility(card(imperium("keys_to_power")))
    assert port.value_for_player(prof(), ()).sum == 0.0
    me = imm_state().players[ME]
    p = prof(with_me(imm_state(), influence=replace(me.influence, emperor=2)))
    assert port.value_for_player(p, ()).sum == p.spice_value(2)


def test_lisan_al_gaib_agent_and_reveal() -> None:
    lisan = imperium("lisan_al_gaib")
    port = imm.LisanAlGaibAgentAbility(card(lisan))
    assert port.value_for_player(prof(), ()).sum == 0.0
    bg_in_play = with_me(imm_state(), in_play=(imperium("clandestine_meeting"),))
    p = prof(bg_in_play)
    assert (
        port.value_for_player(p, ()).sum
        == p.gain_influence_value("fremen", 1, -1, False).sum
    )
    reveal = imm.LisanAlGaibRevealAbility(card(lisan))
    assert reveal.bond_faction == "Fremen"
    assert reveal.value_for_player(prof(), ()).sum == 0.0
    fremen = with_hand(imm_state(), lisan, imperium("shadout_mapes"))
    pf = prof(fremen)
    assert reveal.value_for_player(pf, ()).sum == pf.strength_value(2)


def test_long_reach_takes_the_two_best_influences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {"emperor": 1.0, "spacing_guild": 3.0, "bene_gesserit": 3.0, "fremen": 2.0}
    p = stub(prof(), gain_influence_value=lambda f, *a: Summer(values[f]))
    port = imm.LongReachAgentAbility(card(imperium("long_reach")))
    assert port.value_for_player(p, ()).sum == 6.0
    tracks = [track_entity(f) for f in values]
    answer = port.evaluate(p, req(*tracks))
    assert answer.value == 6.0
    assert set(answer.response[0]) == {"spacing_guild", "bene_gesserit"}  # type: ignore[index]
    assert port.evaluate(p, Request()).value == 0.5
    low = stub(prof(), gain_influence_value=lambda f, *a: Summer(0.1))
    assert port.evaluate(low, req(*tracks)).value == 0.5


def test_long_reach_pile_value() -> None:
    port = imm.LongReachAgentAbility(card(imperium("long_reach")))
    values = {"emperor": 1.0, "spacing_guild": 3.0, "bene_gesserit": 2.5, "fremen": 2.0}
    p = stub(prof(), gain_influence_value=lambda f, *a: Summer(values[f]))
    bg = card(imperium("clandestine_meeting"))
    assert port.value_in_pile_for_other_play(p, Pile.PLAY_AREA, bg).sum == 0.75 * 5.5
    assert port.value_in_pile_for_other_play(p, Pile.DECK, bg).sum == 0.75


def test_organ_merchants() -> None:
    port = imm.OrganMerchantsAbility(card(imperium("organ_merchants")))
    p = stub(prof(), specimen_value=lambda n: 1.25 * n, solari_value=lambda n: 0.5 * n)
    assert port.value_for_player(p, (space("fremkit"),)).sum == -1.25 + 2.0
    assert port.evaluate(p, Request()).value == -1.25 + 2.0


def test_replacement_eyes() -> None:
    port = imm.ReplacementEyesAgentAbility(card(imperium("replacement_eyes")))
    p = stub(
        prof(),
        trash_card_value=1.0,
        trash_mod=0.5,
        card_draw_value=1.5,
        buy_gains=0.25,
        possible_persuasion_gain=2,
    )
    assert port.value_for_player(p, ()).sum == 1.0 + 0.5 + 1.5 + 0.25 + 3.5
    targets = [card("player:3:starter:dagger:0"), card("player:3:starter:diplomacy:0")]
    no_junk = stub(
        p,
        card_to_trash=lambda t, m: (None, 1.0),
        acquire_value=lambda c: Summer(2.0 if "dagger" in c.ref else 1.0),
    )
    answer = port.evaluate(no_junk, req(*targets))
    assert answer.value == 1.0 + 1.5 + 0.25
    assert answer.response == (("player:3:starter:diplomacy:0",),)


def test_sardaukar_quartermaster() -> None:
    owner = card(imperium("sardaukar_quartermaster"))
    troop = imm.SardaukarQuartermasterTroopAbility(owner)
    p = prof()
    assert troop.value_for_player(p, (space("fremkit"),)).sum == 0.0
    grafted = troop.value_for_player(p, (card(tleilaxu("ghola")), space("fremkit")))
    assert grafted.sum == p.troop_value(1, False)
    draw = imm.SardaukarQuartermasterDrawAbility(owner)
    assert draw.value_for_player(p, ()).sum == 0.0  # no graft this turn
    turn = prof(with_graft("player:3:starter:seek_allies:0", owner.ref))
    assert draw.value_for_player(turn, ()).sum > 0.0


def test_has_grafted_needs_the_owner_in_the_pair() -> None:
    """``HasGrafted::CanBePaid @0x4a79c60`` reads the ability's own card
    (``GraftedTo != Empty``): another card's graft this turn does not pay
    it, and ``GetGraftedCard`` of a card outside the pair is null."""

    other_pair = prof(
        with_graft("player:3:starter:seek_allies:0", imperium("dissecting_kit"))
    )
    quartermaster = card(imperium("sardaukar_quartermaster"))
    draw = imm.SardaukarQuartermasterDrawAbility(quartermaster)
    assert not draw.meets_cost(other_pair)
    assert draw.value_for_player(other_pair, ()).sum == 0.0
    assert not imm.CorruptSmugglerAbility(
        card(imperium("corrupt_smuggler"))
    ).meets_cost(other_pair)
    assert not imm.CorrinoGenesAbility(card(tleilaxu("corrino_genes"))).meets_cost(
        other_pair
    )
    # Dissecting Kit is in the pair; Interstellar Conspiracy is not.
    kit = imm.DissectingKitAgentAbility(card(imperium("dissecting_kit")))
    assert kit.meets_cost(other_pair)
    conspiracy = imm.InterstellarConspiracyAbility(
        card(imperium("interstellar_conspiracy"))
    )
    assert imm._grafted_partner_of(other_pair, conspiracy.owner.ref) is None
    assert not conspiracy.meets_cost(other_pair)


def test_stillsuit_manufacturer() -> None:
    owner = card(imperium("stillsuit_manufacturer"))
    port = imm.StillsuitManufacturerAgentAbility(owner)
    p = prof()
    assert port.value_for_player(p, (space("fremkit"),)).sum == 0.0
    allied = prof(with_me(imm_state(), alliance_faction_ids=("fremen",)))
    reveal = next(a for a in abilities_of(owner) if isinstance(a, g.RevealAbility))
    expected = reveal.value_for_player(allied, ()).sum + 1.0
    assert port.value_for_player(allied, (space("fremkit"),)).sum == expected
    assert port.evaluate(allied, Request()).value == 100.0
    bond = imm.StillsuitManufacturerRevealAbility(owner)
    assert bond.value_for_player(p, ()).sum == 0.0
    fremen = prof(with_me(imm_state(), in_play=(imperium("shadout_mapes"),)))
    assert bond.value_for_player(fremen, ()).sum == fremen.spice_value(2)


def test_stillsuit_manufacturer_would_gain_the_alliance_at_a_fremen_space() -> None:
    owner = card(imperium("stillsuit_manufacturer"))
    me = imm_state().players[ME]
    three = with_me(imm_state(), influence=replace(me.influence, fremen=3))
    p = prof(three)
    port = imm.StillsuitManufacturerAgentAbility(owner)
    assert port.value_for_player(p, (space("fremkit"),)).sum > 0.0  # Fremen space
    assert port.value_for_player(p, (space("arrakeen"),)).sum == 0.0


def test_in_the_shadows_reveal() -> None:
    port = imm.InTheShadowsRevealAbility(card(imperium("throne_room_politics")))
    p = prof()
    assert (
        port.value_for_player(p, ()).sum
        == p.gain_influence_value("bene_gesserit", 1, -1, False).sum
    )
    assert port.evaluate(p, Request()).value == 100.0


def test_tleilaxu_master() -> None:
    state = imm_state()
    port = imm.TleilaxuMasterAbility(card(imperium("tleilaxu_master")))
    assert port.value_for_player(prof(state), ()).sum == 0.0
    values = {ref: float(i) for i, ref in enumerate(state.imperium_row)}
    one = stub(
        prof(with_me(state, research_space="c4r2")),
        acquire_value=lambda c: Summer(values[c.ref]),
    )
    cheap = [
        r for r in state.imperium_row if card_entity(r).int_attr("PersuasionCost") < 7
    ]
    best = max(cheap, key=lambda r: values[r])
    assert port.value_for_player(one, ()).sum == values[best]
    targets = req(*(card_entity(r) for r in cheap))
    answer = port.evaluate(one, targets)
    assert answer.response == ((best,), (0,))
    two = stub(
        prof(with_me(state, research_space="c8r2")),
        acquire_value=lambda c: Summer(values[c.ref]),
    )
    picker = Request(
        infos=(
            TargetInfo(entities=tuple(card_entity(r) for r in cheap)),
            TargetInfo(options=(0, 1)),
        )
    )
    assert port.evaluate(two, picker).response == ((best,), (1,))


def test_tleilaxu_surgeon_agent() -> None:
    port = imm.TleilaxuSurgeonAgentAbility(card(imperium("tleilaxu_surgeon")))
    p = stub(
        prof(), specimen_value=lambda n: 1.25 * n, tleilaxu_value=lambda n: Summer(4.0)
    )
    assert port.value_for_player(p, (space("fremkit"),)).sum == -2.5 + 4.0
    assert port.evaluate(p, Request()).value == -2.5 + 4.0
    weak = stub(p, tleilaxu_value=lambda n: Summer(2.5))
    assert port.value_for_player(weak, (space("fremkit"),)).sum == 0.0


def test_tleilaxu_surgeon_reveal() -> None:
    port = imm.TleilaxuSurgeonRevealAbility(card(imperium("tleilaxu_surgeon")))
    p = stub(
        prof(),
        troop_value=lambda n, posture=False: 1.0 * n,
        specimen_value=lambda n: 1.25 * n,
        conflict_posture_bounds=(0.0, 1.0),
        current_conflict_interest=Summer(1.0),
        estimated_conflict_rank=lambda bonus=0: 2,
    )
    assert port.value_for_player(p, ()).sum == -2.0 + 2.5
    # Garrison first when the AI expects to place.
    answer = port.evaluate(p, req(options=(0, 0, 1, 1)))
    assert (answer.value, answer.response) == (0.5, ((0, 0),))
    nowhere = stub(p, estimated_conflict_rank=lambda bonus=0: None)
    assert port.evaluate(nowhere, req(options=(0, 0, 1, 1))).response == ((1, 1),)
    assert port.evaluate(nowhere, req(options=(0, 1))).response == ((0, 1),)
    # Little interest and a thin garrison: not worth it.
    shy = stub(
        prof(with_me(imm_state(), troops_garrison=1, troops_supply=11)),
        conflict_posture_bounds=(2.0, 3.0),
        current_conflict_interest=Summer(1.0),
    )
    assert port.value_for_player(shy, ()).sum == 0.0


# =================================================================================
# §6 Tleilaxu cards
# =================================================================================


def test_beguiling_pheromones_trash_choice() -> None:
    owner = card(tleilaxu("beguiling_pheromones"))
    port = imm.BeguilingPheromonesAbility(owner)
    p = stub(prof(), trash_card_value=1.0, trash_mod=0.25)
    assert port.value_for_player(p, ()).sum == 1.25
    cheap = card(imperium("calculus_of_power"))  # cost 4 < 5
    p = stub(p, card_to_trash=lambda t, m: (None, 1.0))
    answer = port.evaluate(p, req(owner, cheap))
    assert (answer.value, answer.response) == (6.0, ((cheap.ref,),))
    dear = card(imperium("keys_to_power"))  # cost 5: table 1.0, not above itself
    answer = port.evaluate(p, req(owner, dear))
    assert (answer.value, answer.response) == (1.0, ((owner.ref,),))
    junk = stub(p, card_to_trash=lambda t, m: (t[0], 11.5))
    assert port.evaluate(junk, req(owner, dear)).value == 12.5


def test_corrino_genes() -> None:
    owner = card(tleilaxu("corrino_genes"))
    port = imm.CorrinoGenesAbility(owner)
    p = prof()
    assert port.value_for_player(p, (space("fremkit"),)).sum == 0.0
    grafted = port.value_for_player(p, (card(tleilaxu("ghola")), space("fremkit")))
    assert grafted.sum == p.tleilaxu_value(1).sum
    assert port.specific_acquire_value(p).sum == 0.0
    sword = prof(with_me(imm_state(), swordmaster_acquired=True, agents_available=3))
    assert port.specific_acquire_value(sword).sum == 1.0


def test_corrino_genes_acquire_value() -> None:
    """§2.5 table: 1 + 0.5 x #Shadow + 0.75 x #Graft + S (no Swordmaster)."""

    p = prof()
    assert p.acquire_value(card_entity(tleilaxu("corrino_genes"))).sum == 1.0


def test_guild_impersonator_at_a_maker_space() -> None:
    port = imm.GuildImpersonatorAbility(card(tleilaxu("guild_impersonator")))
    p = prof()
    assert port.value_for_player(p, (space("fremkit"),)).sum == 0.0
    maker = port.value_for_player(p, (space("deep_desert"),)).sum
    assert maker == p.gain_influence_value("spacing_guild", 1, -1, False).sum
    assert port.evaluate(p, Request()).value == 100.0


def test_industrial_espionage() -> None:
    owner = card(tleilaxu("industrial_espionage"))
    port = imm.IndustrialEspionageResearchAbility(owner)
    p = stub(
        prof(), research_value=Summer(3.0), research_space_value=lambda s: Summer(1.0)
    )
    assert port.value_for_player(p, (space("fremkit"),)).sum == 0.0
    assert (
        port.value_for_player(p, (card(tleilaxu("ghola")), space("fremkit"))).sum == 3.0
    )
    # No +1.0 floor: a space at 1.0 does not beat the Array.Empty baseline.
    assert port.evaluate(p, req(research("c1r3"))).response == ((),)
    better = stub(p, research_space_value=lambda s: Summer(1.25))
    assert port.evaluate(better, req(research("c1r3"))).response == (
        ("research:c1r3",),
    )


@pytest.mark.parametrize(
    ("research_space", "where", "priced"),
    [
        ("c3r5", "fremkit", False),  # rank 6
        ("c3r5", "research_station", True),  # rank 6 at the Research Station
        ("c4r2", "fremkit", True),  # rank 7
    ],
)
def test_scientific_breakthrough(research_space: str, where: str, priced: bool) -> None:
    p = prof(with_me(imm_state(), research_space=research_space))
    port = imm.ScientificBreakthroughAbility(card(tleilaxu("scientific_breakthrough")))
    value = port.value_for_player(p, (space(where),)).sum
    assert value == (p.victory_point_value(1) if priced else 0.0)
    assert port.evaluate(p, Request()).value == 100.0


def test_scientific_breakthrough_without_a_space_prices_nothing() -> None:
    """V @0x4e1c4d0 returns the base value when ``with`` holds no space
    (0x4e1c606 ``je 0x4e1c720``), even past research rank 6: the discard
    order's ``AgentAbility::ValueForPlayer(P, [])`` never sees the VP."""

    p = prof(with_me(imm_state(), research_space="c4r2"))  # rank 7
    owner = card(tleilaxu("scientific_breakthrough"))
    port = imm.ScientificBreakthroughAbility(owner)
    assert p.victory_point_value(1) > 0
    assert port.value_for_player(p, ()).sum == 0.0
    assert port.value_for_player(p, (owner,)).sum == 0.0  # a card is no space
    assert port.value_for_player(p, (space("fremkit"),)).sum == (
        p.victory_point_value(1)
    )


def test_slig_farmer_solari() -> None:
    owner = card(tleilaxu("slig_farmer"))
    port = imm.SligFarmerSolariAbility(owner)
    p = prof()
    partner = card(imperium("occupation"))  # six icons
    value = port.value_for_player(p, (partner, space("fremkit"))).sum
    assert value == p.solari_value(6)
    # Starters with 3+ icons: Diplomacy, Seek Allies, Signet Ring -> (3 - 2) x 0.5.
    assert port.specific_acquire_value(p).sum == 0.5
    few = prof(with_me(imm_state(), deck=(), discard_pile=(), hand=()))
    assert port.specific_acquire_value(few).sum == -1.0  # may be negative
    assert port.can_run_immediately(
        prof(with_graft(owner.ref, imperium("dissecting_kit")))
    )
    show = prof(with_graft(owner.ref, imperium("show_of_strength")))
    assert not port.can_run_immediately(show)


def test_slig_farmer_tleilaxu() -> None:
    port = imm.SligFarmerTleilaxuAbility(card(tleilaxu("slig_farmer")))
    me = imm_state().players[ME]
    rich = with_me(imm_state(), resources=replace(me.resources, solari=5))
    p = stub(
        prof(rich),
        solari_value=lambda n: 0.5 * n,
        tleilaxu_value=lambda n: Summer(2.25),
    )
    assert port.value_for_player(p, ()).sum == -5.0 * 0.5 + 2.25
    assert port.evaluate(p, Request()).value == -2.5 + 2.25
    assert (
        port.value_for_player(stub(prof(), solari_value=lambda n: 0.5 * n), ()).sum == 0
    )


def test_stitched_horror_value_is_the_best_resource() -> None:
    port = imm.StitchedHorrorAbility(card(tleilaxu("stitched_horror")))
    p = stub(
        prof(),
        water_value=lambda n: 1.0,
        troop_value=lambda n, posture=False: 1.5,
        discard_value=0.5,
        tleilaxu_value=lambda n: Summer(2.25),
    )
    assert port.value_for_player(p, ()).sum == 2.25


def test_stitched_horror_picks_the_two_best_stably() -> None:
    """Errata §6.11: no RNG; ties keep water, troop, trash, Tleilaxu."""

    port = imm.StitchedHorrorAbility(card(tleilaxu("stitched_horror")))
    p = stub(
        prof(),
        water_value=lambda n: 2.0,
        troop_value=lambda n, posture=False: 2.0,
        tleilaxu_value=lambda n: Summer(2.0),
        card_to_trash=lambda t, m: (None, 1.0),
        trash_card_value=1.0,
    )
    answer = port.evaluate(p, Request(infos=(TargetInfo(options=(0, 1, 2, 3)),)))
    assert (answer.value, answer.response) == (4.0, ((0, 1),))
    dagger = card("player:3:starter:dagger:0")
    junk = stub(p, card_to_trash=lambda t, m: (dagger, 11.0))
    request = Request(
        infos=(TargetInfo(options=(0, 1, 2, 3)), TargetInfo(entities=(dagger,)))
    )
    answer = port.evaluate(junk, request)
    assert answer.value == 12.0 + 2.0
    assert answer.response == ((2, 0), (dagger.ref,))


def test_stitched_horror_trash_is_zero_without_a_card_to_trash() -> None:
    """E @0x4e22150: when ``GetCardToTrash`` returns no card the trash option
    stays 0.0 (0x4e22637 ``je 0x4e2267d`` skips ``tv + TrashCardValue``)."""

    port = imm.StitchedHorrorAbility(card(tleilaxu("stitched_horror")))
    p = stub(
        prof(),
        water_value=lambda n: 0.5,
        troop_value=lambda n, posture=False: 0.4,
        tleilaxu_value=lambda n: Summer(0.3),
        card_to_trash=lambda t, m: (None, 1.0),  # nothing reaches the 1.0 floor
        trash_card_value=3.0,
    )
    dagger = card("player:3:starter:dagger:0")
    request = Request(
        infos=(TargetInfo(options=(0, 1, 2, 3)), TargetInfo(entities=(dagger,)))
    )
    answer = port.evaluate(p, request)
    # Water and troop; the old ``1.0 + TrashCardValue`` (4.0) put trash first.
    assert answer.value == 0.5 + 0.4
    assert answer.response == ((0, 1),)


def test_subject_x_137_and_tleilaxu_infiltrator() -> None:
    subject = imm.SubjectX137Ability(card(tleilaxu("subject_x_137")))
    infiltrator = imm.TleilaxuInfiltratorAbility(card(tleilaxu("tleilaxu_infiltrator")))
    p0 = prof()
    assert subject.value_for_player(p0, ()).sum == 0.0
    assert subject.evaluate(p0, Request()).value == 100.0
    p1 = prof(with_me(imm_state(), research_space="c4r2"))
    assert subject.value_for_player(p1, ()).sum == p1.tleilaxu_value(1).sum
    assert infiltrator.value_for_player(p1, ()).sum == 0.0
    p2 = prof(with_me(imm_state(), research_space="c8r2"))
    assert infiltrator.value_for_player(p2, ()).sum == p2.intrigue_value()


def test_twisted_mentat() -> None:
    port = imm.TwistedMentatAbility(card(tleilaxu("twisted_mentat")))
    assert port.value_for_player(prof(), ()).sum == 5.0  # five cards in hand
    short = prof(with_hand(imm_state(), "player:3:starter:dagger:0"))
    assert port.value_for_player(short, ()).sum == 0.0
    assert port.evaluate(short, Request()).value == 100.0


def test_unnatural_reflexes_needs_a_marker() -> None:
    port = imm.UnnaturalReflexesAbility(card(tleilaxu("unnatural_reflexes")))
    assert port.value_for_player(prof(), ()).sum == 0.0
    marked = prof(with_me(imm_state(), research_space="c4r2"))
    assert port.value_for_player(marked, ()).sum > 0.0


def test_piter_genius_advisor() -> None:
    port = imm.PiterGeniusAdvisorAbility(card(tleilaxu("piter_genius_advisor")))
    p = stub(
        prof(),
        troop_value=lambda n, posture=False: 1.0 * n,
        card_draw_value_with_buy_gains=1.5,
        research_value=Summer(2.25),
        estimated_conflict_rank=lambda bonus=0: None,
    )
    assert port.value_for_player(p, ()).sum == -1.0 + 3.0 + 2.25
    answer = port.evaluate(p, req(options=(0, 0, 0)))
    assert (answer.value, answer.response) == (4.25, ((0,),))
    # Exactly two targets are answered as they are (app quirk).
    assert port.evaluate(p, req(options=(0, 1))).response == ((0, 1),)


# =================================================================================
# §7 Intrigues
# =================================================================================


def test_breakthrough_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    port = imm.BreakthroughAbility(intrigue_entity(intrigue("breakthrough"), ME))
    p = stub(prof(), research_space_value=lambda s: Summer(2.0))
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: False)
    assert port.evaluate(p, req(research("c1r3"))).response is None
    final = stub(p, is_final_round=True)
    assert port.evaluate(final, req(research("c1r3"))).value == 2.0
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: turn == 0)
    assert port.evaluate(p, req(research("c1r3"))).response == (("research:c1r3",),)


def test_counterattack(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = intrigue_entity(intrigue("counterattack"), ME)
    plot = imm.CounterattackPlotAbility(owner)
    assert plot.troop_value(prof()) == 4
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: turn == 2)
    ranks = {0: 2, 4: 1}
    p = stub(
        prof(),
        conflict_posture_bounds=(1.0, 2.0),
        current_conflict_interest=Summer(1.5),
        estimated_conflict_rank=lambda bonus=0: ranks[bonus],
        units_to_deploy=lambda n, m: m,
    )
    answer = plot.evaluate(p, req(options=(0, 1, 2)))
    assert (answer.value, answer.response) == (10.0, ((0, 1),))
    first = stub(p, estimated_conflict_rank=lambda bonus=0: 1)
    assert plot.evaluate(first, req(options=(0, 1, 2))).response is None
    climax = stub(first, is_climax=True)
    assert plot.evaluate(climax, req(options=(0,))).response == ((0,),)
    combat = imm.CounterattackCombatAbility(owner)
    assert combat.strength_value(prof()) == 0
    played = _t.with_state(imm_state(), combat_intrigue_players=(1,))
    assert combat.strength_value(prof(played)) == 4
    own = _t.with_state(imm_state(), combat_intrigue_players=(ME,))
    assert combat.strength_value(prof(own)) == 0


@pytest.mark.parametrize(
    ("markers", "hand_size", "spice", "rank", "expected"),
    [
        (1, 1, 2, 3, 1.0),  # turn start, poor, early on the track
        (1, 1, 5, 3, None),  # too much spice
        (1, 1, 2, 5, None),  # research rank 5
        (1, 4, 9, 9, 1.0),  # 4+ Intrigue skips the gate
    ],
)
def test_disguised_bureaucrat(
    monkeypatch: pytest.MonkeyPatch,
    markers: int,
    hand_size: int,
    spice: int,
    rank: int,
    expected: float | None,
) -> None:
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: turn == 0)
    monkeypatch.setattr(imm, "_markers", lambda p: markers)
    me = imm_state().players[ME]
    state = with_me(
        imm_state(),
        resources=replace(me.resources, spice=spice),
        intrigue_cards=tuple(
            intrigue("disguised_bureaucrat", i) for i in range(hand_size)
        ),
    )
    p = stub(prof(state))
    p.ctx.research_rank = lambda seat=None: rank  # type: ignore[method-assign]
    port = imm.DisguisedBureaucratAbility(
        intrigue_entity(intrigue("disguised_bureaucrat"), ME)
    )
    answer = port.evaluate(p, req(track_entity("emperor")))
    if expected is None:
        assert answer.response is None
    else:
        assert (answer.value, answer.response) == (expected, ())


def test_disguised_bureaucrat_two_markers_picks_a_track() -> None:
    state = with_me(imm_state(), research_space="c8r2")
    values = {"emperor": 1.0, "fremen": 2.0}
    p = stub(prof(state), gain_influence_value=lambda f, *a: Summer(values[f]))
    port = imm.DisguisedBureaucratAbility(
        intrigue_entity(intrigue("disguised_bureaucrat"), ME)
    )
    answer = port.evaluate(p, req(*(track_entity(f) for f in values)))
    assert (answer.value, answer.response) == (2.0, (("fremen",),))


@pytest.mark.parametrize(
    ("ranks", "units", "expected"),
    [
        ({0: None}, 0, 1.0),  # not placing
        ({0: 2}, 2, None),  # placing with fewer than 3 units
        ({0: 2, -6: 2}, 3, 5.0),  # losing six strength keeps the place
        ({0: 2, -6: 3}, 3, None),  # it would cost the 2nd place
        ({0: 3, -6: 4}, 3, 1.0),  # 3rd: losing it is cheap
    ],
)
def test_gruesome_sacrifice(
    ranks: dict[int, int | None], units: int, expected: float | None
) -> None:
    state = with_me(imm_state(), troops_conflict=units, troops_supply=9 - units)
    p = stub(prof(state), current_conflict_rank=lambda bonus=0: ranks[bonus])
    port = imm.GruesomeSacrificeAbility(
        intrigue_entity(intrigue("gruesome_sacrifice"), ME)
    )
    answer = port.evaluate(p, Request())
    if expected is None:
        assert answer.response is None
    else:
        assert (answer.value, answer.response) == (expected, ())


def test_economic_positioning_combat_holds_late() -> None:
    owner = intrigue_entity(intrigue("economic_positioning"), ME)
    port = imm.EconomicPositioningCombatAbility(owner)
    p = stub(prof(), current_conflict_rank=lambda bonus=0: None)
    assert port.evaluate(p, Request()).value == 1.0
    lp = stub(prof(late()), current_conflict_rank=lambda bonus=0: None)
    assert port.evaluate(lp, Request()).response is None


def test_harvest_cells() -> None:
    owner = intrigue_entity(intrigue("harvest_cells"), ME)
    port = imm.HarvestCellsAbility(owner)
    assert port.has_matching_timing(3)  # CombatTurn
    assert not port.has_matching_timing(0)
    assert intr.ability_for_prompt(owner, combat_turn=True) is not None
    p = stub(
        prof(),
        specimen_value=lambda n: 1.25 * n,
        acquire_value=lambda c: Summer(0.0),
    )
    cheap = card(tleilaxu("contaminator"))
    answer = port.evaluate(p, req(cheap))
    # 0.0 + 2.5 does not beat the stored "no acquire" 2.5 (strict).
    assert (answer.value, answer.response) == (2.5, ((),))
    p2 = stub(p, acquire_value=lambda c: Summer(0.5))
    answer = port.evaluate(p2, req(cheap))
    assert (answer.value, answer.response) == (3.0, ((cheap.ref,),))


def test_illicit_dealings(monkeypatch: pytest.MonkeyPatch) -> None:
    port = imm.IllicitDealingsAbility(intrigue_entity(intrigue("illicit_dealings"), ME))
    assert port.evaluate(prof(), Request()).response is None  # rank 0
    p = prof(with_me(imm_state(), tleilaxu_space=1))
    assert port.evaluate(p, Request()).value == p.tleilaxu_value(1).sum
    assert not port.is_bad_intrigue(prof(late(tleilaxu_space=3)))
    assert port.is_bad_intrigue(prof(late(tleilaxu_space=2)))


def test_shadowy_bargain(monkeypatch: pytest.MonkeyPatch) -> None:
    port = imm.ShadowyBargainPlotAbility(
        intrigue_entity(intrigue("shadowy_bargain"), ME)
    )
    assert port.evaluate(prof(), Request()).response is None
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: turn == 2)
    p = prof()
    assert port.evaluate(p, Request()).value == p.specimen_value(1)
    assert port.evaluate(prof(late(tleilaxu_space=3)), Request()).response is None


def test_study_melange(monkeypatch: pytest.MonkeyPatch) -> None:
    port = imm.StudyMelangePlotAbility(intrigue_entity(intrigue("study_melange"), ME))
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: turn == 0)
    p = prof()
    assert port.evaluate(p, Request()).value == p.spice_value(1)
    past = prof(with_me(imm_state(), research_space="c3r5"))  # rank 6
    assert port.evaluate(past, Request()).response is None
    at_five = prof(with_me(imm_state(), research_space="c3r3"))
    assert port.evaluate(at_five, Request()).response is None
    final = stub(prof(with_me(imm_state(), research_space="c3r3")), is_final_round=True)
    assert port.evaluate(final, Request()).response == ()


def test_tleilaxu_puppet(monkeypatch: pytest.MonkeyPatch) -> None:
    port = imm.TleilaxuPuppetPlotAbility(
        intrigue_entity(intrigue("tleilaxu_puppet"), ME)
    )
    monkeypatch.setattr(imm, "_in_player_turn", lambda p, turn: turn == 2)
    assert port.evaluate(stub(prof(), buy_gains=1.33), Request()).value == 10.0
    assert port.evaluate(stub(prof(), buy_gains=1.32), Request()).response is None


@pytest.mark.parametrize(
    ("research_space", "strength", "combat"),
    [("c0r3", 2, 2.0), ("c4r2", 4, 5.25), ("c8r2", 6, 7.0)],
)
def test_vicious_talents(research_space: str, strength: int, combat: float) -> None:
    p = prof(with_me(imm_state(), research_space=research_space))
    port = imm.ViciousTalentsAbility(intrigue_entity(intrigue("vicious_talents"), ME))
    assert port.strength_value(p) == strength
    assert port.combat_value(p) == combat


@pytest.mark.parametrize(
    ("cls", "name", "changes", "bad"),
    [
        (imm.DisguisedBureaucratAbility, "disguised_bureaucrat", {}, True),
        (
            imm.DisguisedBureaucratAbility,
            "disguised_bureaucrat",
            {"research_space": "c3r3"},
            False,
        ),
        (imm.GruesomeSacrificeAbility, "gruesome_sacrifice", {}, True),
        (
            imm.GruesomeSacrificeAbility,
            "gruesome_sacrifice",
            {"tleilaxu_space": 6},
            False,
        ),
        (imm.HarvestCellsAbility, "harvest_cells", {}, True),
        (imm.ShadowyBargainEndgameAbility, "shadowy_bargain", {}, True),
        (
            imm.ShadowyBargainEndgameAbility,
            "shadowy_bargain",
            {"tleilaxu_space": 3},
            False,
        ),
        (imm.StudyMelangeEndgameAbility, "study_melange", {}, True),
        (imm.TleilaxuPuppetEndgameAbility, "tleilaxu_puppet", {}, False),
        (
            imm.TleilaxuPuppetEndgameAbility,
            "tleilaxu_puppet",
            {"high_council": True},
            True,
        ),
        (imm.EconomicPositioningEndgameAbility, "economic_positioning", {}, True),
    ],
)
def test_is_bad_intrigue_late(
    cls: type[Any], name: str, changes: dict[str, object], bad: bool
) -> None:
    port = cls(intrigue_entity(intrigue(name), ME))
    assert port.is_bad_intrigue(prof(late(**changes))) is bad
    assert port.is_bad_intrigue(prof()) is False  # never before the Late arc


def test_endgame_halves_have_endgame_timing() -> None:
    for cls in (
        imm.EconomicPositioningEndgameAbility,
        imm.ShadowyBargainEndgameAbility,
        imm.StudyMelangeEndgameAbility,
        imm.TleilaxuPuppetEndgameAbility,
    ):
        assert cls.ability_timing == intr.ENDGAME_TIMING


def test_has_matching_timing_table() -> None:
    """``HasMatchingTiming @0x4a89f30`` jump table."""

    table = {0: {0, 1, 2}, 1: {1}, 2: {2}, 3: {3}, 4: {4}, 5: {3}, 6: {0, 1, 2, 3, 4}}
    for timing, turns in table.items():
        probe_cls = type("_Probe", (intr.IntrigueAbility,), {"ability_timing": timing})
        probe = probe_cls(intrigue_entity(intrigue("breakthrough"), ME))
        for turn in range(5):
            assert probe.has_matching_timing(turn) is (turn in turns), (timing, turn)


# =================================================================================
# Uprising without Immortality is unchanged
# =================================================================================


def test_uprising_acquire_and_threshold_unchanged() -> None:
    state = base_state()
    p = _t.make_profile(state, ME)
    row_card = card_entity(state.imperium_row[0], ME)
    answer = g.AcquireAbility(row_card).evaluate(p, Request())
    assert answer.value == p.acquire_value(row_card).sum
    assert p.ctx.graft_cards() is None


def test_answers_are_answers() -> None:
    """Every evaluate returns an ``Answer`` (smoke over the module)."""

    p = prof()
    owner = card(imperium("dissecting_kit"))
    for name in dir(imm):
        cls = getattr(imm, name)
        if not isinstance(cls, type) or not issubclass(cls, Ability):
            continue
        if cls.__module__ != imm.__name__ or "APP_CLASS" not in vars(cls):
            continue
        port = cls(owner)
        try:
            answer = port.evaluate(p, Request())
        except NotImplementedError:
            continue
        assert isinstance(answer, Answer), name
