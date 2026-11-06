"""Generic ability ports: spec/generic-abilities.md (abilities/generic.py).

Every test builds a real ``GameState`` (``app_ai.testing``), adjusts the
fields the formula reads, and stubs the ``Profile`` methods other areas own with simple
linear prices so each expected value can be checked by hand.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any, ClassVar

import pytest

from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Ability,
    Answer,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    agent_entity,
    card_entity,
    conflict_entity,
    contract_entity,
    intrigue_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import AppContext, Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------

PRICES = {
    Attr.WATER: 1.0,
    Attr.SPICE: 0.5,
    Attr.SOLARI: 0.25,
    Attr.PERSUASION: 0.75,
    Attr.STRENGTH: 0.66,
    Attr.TROOPS: 0.9,
    Attr.SPECIMEN: 0.1,
}
INFLUENCE = {"emperor": 2.0, "spacing_guild": 2.5, "bene_gesserit": 3.0, "fremen": 1.0}
SEAT = 3  # the first player of seed 1 (Lady Jessica)


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "victory_point_value": lambda n: 6.0 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "card_draw_value_with_buy_gains": lambda: 1.8,
        "intrigue_value": lambda: 2.25,
        "trash_card_value": lambda: 2.75,
        "trash_mod": lambda: 1.0,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "spy_value": lambda: Summer(1.66),
        "recall_spy_value": lambda: Summer(-1.66),
        "recall_agent_value": lambda: 5.0,
        "recall_agent": lambda agents: None,
        "deploy_value": lambda owner: 1.25,
        "units_to_deploy": lambda garrison, max_units: min(garrison, max_units),
        "want_contract_count": lambda: 1,
        "gain_contract_value": lambda: Summer(2.0),
        "best_contract": lambda cs, forced: (cs[0], 3.5) if cs else (None, 1.0),
        "is_climax": lambda: False,
        "game_arc": lambda: 0,
        "control_solari_value": lambda: 4.0,
        "battle_icon_value": lambda icon: Summer(2.5),
        "abundance_level": lambda attr: 1,
        "deck_agent_icons": lambda: {},
        "acquire_value": lambda card: Summer(3.0),
        "card_to_trash": lambda targets, minimum: (None, minimum),
        "recall_spies": lambda spies, take: (list(spies[:take]), 0.0),
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 3's first ``turn`` decision (round 1, CHOAM on)."""

    state = first_decision("turn")
    return with_state(
        state,
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 0),
            ("imperial_basin", 0),
        ),
    )


@pytest.fixture(scope="module")
def effects_state() -> GameState:
    """Seat 3's first ``agent_effects``: Reconnaissance at Arrakeen."""

    return first_decision("agent_effects")


@pytest.fixture(scope="module")
def combat_state() -> GameState:
    return first_decision("combat_intrigue")


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, decision_kind=None, **stub overrides) -> Profile``."""

    def build(
        state: GameState,
        seat: int = SEAT,
        decision_kind: str | None = None,
        **overrides: Callable[..., Any],
    ) -> Profile:
        profile = make_profile(state, seat)
        if decision_kind is not None:
            view = replace(profile.ctx.view, decision_kind=decision_kind)
            profile.ctx = AppContext(state, seat, view)
        stubs = _base_stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


def synth(kind: Kind, ref: str, **attrs: object) -> Entity:
    """An entity with a hand-made archetype (isolates a formula)."""

    archetype = Archetype(
        short=f"Test.{ref}",
        kind="test",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(dict(attrs)),
    )
    return Entity(kind, ref, archetype, SEAT)


def with_frame(state: GameState, **changes: str | int | bool) -> GameState:
    """``state`` with keys of the top frame's context replaced."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    new = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], new))


def give_contracts(
    state: GameState,
    seat: int,
    active: tuple[str, ...] = (),
    completed: tuple[str, ...] = (),
) -> GameState:
    """Move contracts out of the shared zones into a seat's contract area."""

    taken = {*active, *completed}
    state = with_state(
        state,
        contract_bank=tuple(c for c in state.contract_bank if c not in taken),
        face_up_contract_ids=tuple(
            c for c in state.face_up_contract_ids if c not in taken
        ),
        sardaukar_contract_ids=tuple(
            c for c in state.sardaukar_contract_ids if c not in taken
        ),
    )
    return with_player(
        state, seat, active_contract_ids=active, completed_contract_ids=completed
    )


def set_conflict(state: GameState, conflict_id: str | None) -> GameState:
    """``conflict_id`` face up (taken out of the Conflict deck), or none."""

    current = () if conflict_id is None else (conflict_id,)
    return with_state(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        current_conflict_ids=current,
    )


def with_spies(state: GameState, seat: int, *posts: str) -> GameState:
    return with_player(state, seat, spy_post_ids=posts, spies_supply=3 - len(posts))


def req(
    *entities: Entity, options: tuple[int, ...] = (), max_select: int = 1
) -> Request:
    return Request((TargetInfo(tuple(entities), options, 0, max_select),))


def space(space_id: str) -> Entity:
    return space_entity(space_id, Board(True))


def starter(name: str, copy: int = 0) -> Entity:
    return card_entity(f"player:{SEAT}:starter:{name}:{copy}", SEAT)


def imperium(name: str) -> Entity:
    return card_entity(f"imperium:{name}:0", SEAT)


AG = "worm.canis.abilities."


# ---------------------------------------------------------------------------
# Helpers and registration
# ---------------------------------------------------------------------------


def test_every_generic_port_is_registered_under_its_app_name() -> None:
    expected = {
        "PlayAbilities.PlayAbility": g.PlayAbility,
        "PlayAbilities.AgentAbility": g.AgentAbility,
        "PlayAbilities.BaseSet.PowerPlayAgentAbility": g.PowerPlayAgentAbility,
        "PlayAbilities.RevealAbility": g.RevealAbility,
        "ActivatedAbilities.DeferredAbility": g.DeferredAbility,
        "ActivatedAbilities.DrawAbility": g.DrawAbility,
        "SpaceAbilities.SpaceAbility": g.SpaceAbility,
        "SpaceAbilities.GainInfluenceAbility": g.GainInfluenceAbility,
        "ConflictAbilities.Uprising.TrashConflictCustomAbility": (
            g.TrashConflictCustomAbility
        ),
        "ActivatedAbilities.Uprising.ContractAbilities.Draw2ContractAbility": (
            g.Draw2ContractAbility
        ),
        "ConflictAbilities.Uprising.Pay6SolariToGain1VPAbility": (
            g.Pay6SolariToGain1VPAbility
        ),
    }
    for name, cls in expected.items():
        assert PORTS[AG + name] is cls
        assert cls.APP_CLASS == AG + name
    # The app hierarchy is the MRO.
    assert issubclass(g.TrashConflictCustomAbility, g.TrashCustomAbility)
    assert issubclass(g.TrashCustomAbility, g.TrashAbility)
    assert issubclass(g.GainContractCustomAbility, g.DeferredAbility)
    assert not issubclass(
        g.CargoRunner4ContractsDrawAbility, g.CargoRunner2ContractsDrawAbility
    )
    assert not issubclass(g.RevealAbility, g.PlayAbility)


def test_app_isinstance_follows_registered_bases_and_unported_names() -> None:
    owner = imperium("in_high_places")
    draw = g.BeneGesseritDrawAbility(owner)
    assert g.app_isinstance(draw, AG + "ActivatedAbilities.DrawAbility")
    assert g.app_isinstance(draw, AG + "ActivatedAbilities.DeferredAbility")
    assert not g.app_isinstance(draw, AG + "ActivatedAbilities.TrashAbility")
    stand_in = UnportedAbility(owner, "X.Y")
    assert g.app_isinstance(stand_in, "X.Y")
    assert g.ability_id(stand_in) == "X.Y"
    assert g.ability_id(draw) == AG + "ActivatedAbilities.BeneGesseritDrawAbility"


def test_collect_first_and_signet_icons() -> None:
    dagger = starter("dagger")
    arrakeen = space("arrakeen")
    assert g.collect_first((dagger, arrakeen), Kind.SPACE) is arrakeen
    assert g.collect_first((dagger,), Kind.SPACE) is None
    assert g.signet_icons(starter("signet_ring")) == 1
    assert g.signet_icons(dagger) == 0
    assert g.signet_icons(synth(Kind.CARD, "x", SignetIcons=2)) == 2


def test_contract_spaces_follow_referenced_archetypes(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    harvest = contract_entity("contract:harvest_3")
    refs = [s.ref for s in g.contract_spaces(p, harvest)]
    assert refs == ["deep_desert", "hagga_basin", "imperial_basin"]
    research = contract_entity("contract:research_station_ii")
    assert [s.ref for s in g.contract_spaces(p, research)] == ["research_station"]
    assert g.contract_spaces(p, contract_entity("contract:immediate")) == []


# ---------------------------------------------------------------------------
# WormAbilityDefinition default ValueInPileForOtherPlay (base.py, spec §1.1)
# ---------------------------------------------------------------------------


def _default_p(owner: Entity) -> Ability:
    return UnportedAbility(owner, "Test.Default")


def test_default_synergy_is_empty_outside_the_deck(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = synth(Kind.CARD, "o", Tags=("WantTSMF", "Spy"), FactionList=("Emperor",))
    card = synth(Kind.CARD, "c", Tags=("WantE", "WantSpy"), Persuasion=3)
    s = _default_p(owner).value_in_pile_for_other_play(
        prof(turn_state), Pile.PLAY_AREA, card
    )
    assert s.sum == 0.0


def test_default_synergy_tsmf_terms(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    owner = contract_entity("contract:acquire")  # ContractBase_20: WantTSMF
    tsmf = card_entity("reserve:the_spice_must_flow:0", SEAT)  # Persuasion 0, cost 9
    ab = _default_p(owner)
    assert ab.value_in_pile_for_other_play(p, Pile.DECK, tsmf).sum == pytest.approx(2.0)
    high = synth(Kind.CARD, "h", Persuasion=3, PersuasionCost=9)
    assert ab.value_in_pile_for_other_play(p, Pile.DECK, high).sum == pytest.approx(0.5)
    # Persuasion 2: both the >= 2 bonus and the <= 2 / cost <= 7 penalty.
    both = synth(Kind.CARD, "b", Persuasion=2, PersuasionCost=7)
    assert ab.value_in_pile_for_other_play(p, Pile.DECK, both).sum == pytest.approx(0.0)
    low = synth(Kind.CARD, "l", Persuasion=1, PersuasionCost=7)
    assert ab.value_in_pile_for_other_play(p, Pile.DECK, low).sum == pytest.approx(-0.5)
    dear = synth(Kind.CARD, "d", Persuasion=1, PersuasionCost=8)
    assert ab.value_in_pile_for_other_play(p, Pile.DECK, dear).sum == 0.0


def test_default_synergy_faction_terms_stop_at_climax(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = synth(Kind.CARD, "o", FactionList=("Fremen", "BeneGesserit"))
    card = synth(Kind.CARD, "c", Tags=("FremenBond", "WantF", "WantBG", "WantSG"))
    ab = _default_p(owner)
    normal = ab.value_in_pile_for_other_play(prof(turn_state), Pile.DECK, card)
    assert normal.sum == pytest.approx(0.66 + 0.5 + 0.5)
    climax = prof(turn_state, is_climax=lambda: True)
    assert ab.value_in_pile_for_other_play(climax, Pile.DECK, card).sum == 0.0


@pytest.mark.parametrize(
    ("faction", "tag"),
    [("SpacingGuild", "WantSG"), ("Emperor", "WantE"), ("BeneGesserit", "WantBG")],
)
def test_default_synergy_each_faction_tag(
    turn_state: GameState, prof: ProfileFactory, faction: str, tag: str
) -> None:
    owner = synth(Kind.CARD, "o", FactionList=(faction,))
    card = synth(Kind.CARD, "c", Tags=(tag,))
    s = _default_p(owner).value_in_pile_for_other_play(
        prof(turn_state), Pile.DECK, card
    )
    assert s.sum == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("owner_tags", "card_tags"),
    [
        (("DiscardEnabler",), ("IncentiveDiscard",)),
        (("IncentiveDiscard",), ("DiscardEnabler",)),
        (("Graft",), ("WantsGraft",)),
        (("WantsGraft",), ("Graft",)),
    ],
)
def test_default_synergy_multipliers_scale_only_earlier_terms(
    turn_state: GameState,
    prof: ProfileFactory,
    owner_tags: tuple[str, ...],
    card_tags: tuple[str, ...],
) -> None:
    owner = synth(Kind.CARD, "o", FactionList=("Emperor",), Tags=(*owner_tags, "Spy"))
    card = synth(Kind.CARD, "c", Tags=("WantE", *card_tags, "WantSpy"))
    s = _default_p(owner).value_in_pile_for_other_play(
        prof(turn_state), Pile.DECK, card
    )
    # 0.5 (Emperor in deck) x 1.1, then the spy incentive 0.25 is added unscaled.
    assert s.sum == pytest.approx(0.5 * 1.1 + 0.25)


# ---------------------------------------------------------------------------
# DeferredThresholdReached (engine-order §4.1) and CanRunImmediately
# ---------------------------------------------------------------------------


def test_threshold_counts_intrigue_hand_outside_an_agent_turn(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    three = with_player(
        turn_state,
        SEAT,
        intrigue_cards=("intrigue:change_allegiances:0", "intrigue:buy_access:0"),
    )
    assert g.deferred_threshold_reached(prof(three))
    one = with_player(turn_state, SEAT, intrigue_cards=("intrigue:buy_access:0",))
    assert not g.deferred_threshold_reached(prof(one))


def test_threshold_counts_this_turns_card_and_space(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    # Reconnaissance (no DeferValue) at Arrakeen (DeferValue 1).
    assert not g.deferred_threshold_reached(prof(effects_state))
    signet = with_frame(effects_state, card_id=f"player:{SEAT}:starter:signet_ring:0")
    assert g.deferred_threshold_reached(prof(signet))  # 3 + 1


def test_threshold_irulan_extra_at_emperor_space(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    state = with_frame(effects_state, space_id="dutiful_service")  # DeferValue 1
    state = with_player(state, SEAT, leader_id="princess_irulan", leader_face_id=None)
    assert g.deferred_threshold_reached(prof(state))  # 1 + 2
    seated = with_player(state, SEAT, influence=Influence(emperor=2))
    assert not g.deferred_threshold_reached(prof(seated))


def test_threshold_counts_face_up_contracts_of_the_turn_space(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    state = with_frame(effects_state, space_id="spice_refinery")
    state = with_player(state, SEAT, intrigue_cards=("intrigue:buy_access:0",))
    # Draw-2 contract, DeferValue 2.
    state = give_contracts(state, SEAT, active=("contract:spice_refinery_i",))
    assert g.deferred_threshold_reached(prof(state))
    done = give_contracts(state, SEAT, completed=("contract:spice_refinery_i",))
    assert not g.deferred_threshold_reached(prof(done))


def test_threshold_gated_abilities_run_unless_threshold(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    arrakeen = space("arrakeen")
    gated = (
        g.DrawAbility(arrakeen),
        g.GainInfluenceAbility(space("fremkit")),
        g.GainContractAbility(space("accept_contract")),
    )
    calm = prof(effects_state)
    assert all(a.can_run_immediately(calm) for a in gated)
    piled = with_frame(effects_state, card_id=f"player:{SEAT}:starter:signet_ring:0")
    assert not any(a.can_run_immediately(prof(piled)) for a in gated)
    revealed = with_player(piled, SEAT, has_revealed=True)
    assert all(a.can_run_immediately(prof(revealed)) for a in gated)
    no_turn = with_state(piled, phase=GamePhase.COMBAT)
    assert all(a.can_run_immediately(prof(no_turn)) for a in gated)
    # Draw-2 contracts have no Reveal-turn exemption.
    draw2 = g.Draw2ContractAbility(contract_entity("contract:spice_refinery_i"))
    assert not draw2.can_run_immediately(prof(revealed))
    assert draw2.can_run_immediately(prof(no_turn))
    assert draw2.can_run_immediately(calm)


def test_combat_phase_custom_rewards_run_immediately(
    turn_state: GameState, combat_state: GameState, prof: ProfileFactory
) -> None:
    owner = conflict_entity("seize_spice_refinery", True)
    for ability in (g.PlaceSpyCustomAbility(owner), g.GainContractCustomAbility(owner)):
        assert ability.can_run_immediately(prof(combat_state, seat=0))
        assert not ability.can_run_immediately(prof(turn_state))
    assert g.GainAnyInfluenceConflictAbility(owner).can_run_immediately(
        prof(turn_state)
    )


_FLAGS: list[tuple[type[g.DeferredAbility], SelectionMode, bool, Timing, bool]] = [
    (g.DrawAbility, SelectionMode.EXPLICIT, False, Timing.AGENT, True),
    (g.GainInfluenceAbility, SelectionMode.EXPLICIT, False, Timing.AGENT, True),
    (
        g.GainAnyInfluenceAgentAbility,
        SelectionMode.EXPLICIT,
        False,
        Timing.AGENT,
        False,
    ),
    (
        g.GainAnyInfluenceRevealAbility,
        SelectionMode.EXPLICIT,
        False,
        Timing.REVEAL,
        False,
    ),
    (
        g.GainAnyInfluenceConflictAbility,
        SelectionMode.EXPLICIT,
        False,
        Timing.COMBAT_RESOLUTION,
        False,
    ),
    (g.AgentGainIntrigueAbility, SelectionMode.EXPLICIT, True, Timing.AGENT, False),
    (g.RevealGainIntrigueAbility, SelectionMode.EXPLICIT, True, Timing.REVEAL, False),
    (g.GainIntrigueCustomAbility, SelectionMode.EXPLICIT, False, Timing.NONE, False),
    (g.DeployUnitsAbility, SelectionMode.OPTIONAL, False, Timing.AGENT, False),
    (g.TrashAgentAbility, SelectionMode.EXPLICIT, False, Timing.AGENT, False),
    (g.TrashConflictCustomAbility, SelectionMode.EXPLICIT, False, Timing.NONE, False),
    (g.TrashSelfAbility, SelectionMode.IMPLICIT, True, Timing.AGENT, False),
    (g.PlaceSpyAgentAbility, SelectionMode.EXPLICIT, False, Timing.AGENT, False),
    (g.PlaceSpyRevealAbility, SelectionMode.EXPLICIT, False, Timing.REVEAL, False),
    (g.PlaceSpyCustomAbility, SelectionMode.EXPLICIT, False, Timing.NONE, False),
    (
        g.PlaceSpyCombatResolutionAbility,
        SelectionMode.EXPLICIT,
        False,
        Timing.COMBAT_RESOLUTION,
        False,
    ),
    (g.RecallAgentAbility, SelectionMode.EXPLICIT, False, Timing.AGENT, False),
    (g.GainContractAbility, SelectionMode.EXPLICIT, False, Timing.AGENT, True),
    (g.GainContractCustomAbility, SelectionMode.EXPLICIT, False, Timing.NONE, False),
    (g.ContractAbility, SelectionMode.EXPLICIT, True, Timing.NONE, False),
    (g.Draw2ContractAbility, SelectionMode.EXPLICIT, False, Timing.NONE, False),
    (g.PlaceSpyContractAbility, SelectionMode.EXPLICIT, False, Timing.NONE, False),
    (
        g.Recall2SpiesVPAbility,
        SelectionMode.OPTIONAL,
        False,
        Timing.COMBAT_RESOLUTION,
        False,
    ),
    (g.BlowWallCustomAbility, SelectionMode.OPTIONAL, False, Timing.AGENT, False),
    (
        g.Pay3SpiceToGain1VPAbility,
        SelectionMode.OPTIONAL,
        False,
        Timing.COMBAT_RESOLUTION,
        False,
    ),
]


@pytest.mark.parametrize(("cls", "mode", "always", "timing", "contextual"), _FLAGS)
def test_engine_side_members(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[g.DeferredAbility],
    mode: SelectionMode,
    always: bool,
    timing: Timing,
    contextual: bool,
) -> None:
    ability = cls(space("arrakeen"))
    assert ability.selection_mode(prof(turn_state)) == mode
    assert ability.always_run_immediately is always
    assert ability.timing == timing
    assert ability.contextually_deferred is contextual
    if cls in (g.ContractAbility, g.AgentGainIntrigueAbility, g.TrashSelfAbility):
        assert ability.can_run_immediately(prof(turn_state))
    if cls in (g.DeployUnitsAbility, g.PlaceSpyContractAbility, g.RecallAgentAbility):
        assert not ability.can_run_immediately(prof(turn_state))


def test_play_reveal_timings() -> None:
    assert g.AgentAbility.timing == Timing.AGENT
    assert g.RevealAbility.timing == Timing.REVEAL


def test_abstract_selection_mode_raises(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    with pytest.raises(NotImplementedError):
        g.DeferredAbility(space("arrakeen")).selection_mode(prof(turn_state))


# ---------------------------------------------------------------------------
# DeferredAbility.Evaluate (DeferValue)
# ---------------------------------------------------------------------------


def test_deferred_evaluate_answers_the_owner_defer_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    assert g.DrawAbility(space("arrakeen")).evaluate(p, Request()) == Answer(
        1.0, (), "DrawAbility defer"
    )
    assert g.DrawAbility(space("research_station")).evaluate(p, Request()).value == 2.0
    # Explicit without a DeferValue: 1; Implicit without: 0.
    assert (
        g.GainInfluenceAbility(space("deliver_supplies")).evaluate(p, Request()).value
        == 1.0
    )
    assert (
        g.TrashSelfAbility(starter("seek_allies")).evaluate(p, Request()).value == 0.0
    )
    # Optional with a DeferValue on the owner: the attribute wins.
    assert g.DeployUnitsAbility(space("fremkit")).defer_value(p) == 1


# ---------------------------------------------------------------------------
# Draws (spec §7)
# ---------------------------------------------------------------------------


def test_draw_value_gated_by_a_drawable_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    draw = g.DrawAbility(space("arrakeen"))
    assert draw.value_for_player(prof(turn_state)).sum == pytest.approx(1.5 + 0.3)
    deck = turn_state.players[SEAT].deck
    empty = with_player(turn_state, SEAT, deck=(), discard_pile=(), trashed=deck)
    assert draw.value_for_player(prof(empty)).sum == 0.0
    discard_only = with_player(turn_state, SEAT, deck=(), discard_pile=deck)
    assert draw.value_for_player(prof(discard_only)).sum == pytest.approx(1.8)


def test_draw_subclass_costs(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("hidden_missive")
    bg = g.BeneGesseritInfluenceDrawAbility(owner)
    assert bg.value_for_player(prof(turn_state)).sum == 0.0
    allied = with_player(turn_state, SEAT, influence=Influence(bene_gesserit=2))
    assert bg.value_for_player(prof(allied)).sum == pytest.approx(1.8)
    runner = imperium("cargo_runner")
    two = give_contracts(
        turn_state, SEAT, completed=("contract:immediate", "contract:acquire")
    )
    assert g.CargoRunner2ContractsDrawAbility(runner).value_for_player(
        prof(two)
    ).sum == pytest.approx(1.8)
    assert (
        g.CargoRunner4ContractsDrawAbility(runner).value_for_player(prof(two)).sum
        == 0.0
    )
    # The Guild Envoy grant is never held at valuation.
    envoy = g.SpacingGuildDiscardDrawAbility(imperium("guild_envoy"))
    assert envoy.value_for_player(prof(turn_state)).sum == 0.0


def test_bene_gesserit_draw_needs_another_bg_card_in_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    draw = g.BeneGesseritDrawAbility(imperium("in_high_places"))
    assert draw.value_for_player(prof(turn_state)).sum == 0.0
    other = with_player(
        turn_state, SEAT, in_play=("imperium:bene_gesserit_operative:0",)
    )
    assert draw.value_for_player(prof(other)).sum == pytest.approx(1.8)
    # Only the owner in play: V's test passes, the Cost (another BG card) fails.
    alone = with_player(turn_state, SEAT, in_play=("imperium:in_high_places:0",))
    assert draw.value_for_player(prof(alone)).sum == 0.0


def test_bene_gesserit_draw_pile_synergy(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    draw = g.BeneGesseritDrawAbility(imperium("in_high_places"))
    bg_card = imperium("bene_gesserit_operative")
    other = starter("dagger")
    p = prof(turn_state)
    played = 0.75 * (1.5 + 0.3)
    assert draw.value_in_pile_for_other_play(p, Pile.PLAY_AREA, bg_card).sum == (
        pytest.approx(played)
    )
    assert draw.value_in_pile_for_other_play(p, Pile.PLAY_AREA, other).sum == 0.0
    one_agent = with_player(
        turn_state, SEAT, agents_available=1, agent_locations=("secrets",)
    )
    assert (
        draw.value_in_pile_for_other_play(prof(one_agent), Pile.PLAY_AREA, bg_card).sum
        == 0.0
    )
    bg_in_play = with_player(
        turn_state, SEAT, in_play=("imperium:bene_gesserit_operative:1",)
    )
    assert (
        draw.value_in_pile_for_other_play(prof(bg_in_play), Pile.PLAY_AREA, bg_card).sum
        == 0.0
    )
    assert draw.value_in_pile_for_other_play(p, Pile.DECK, bg_card).sum == (
        pytest.approx(0.75)
    )
    climax = prof(turn_state, is_climax=lambda: True)
    assert draw.value_in_pile_for_other_play(climax, Pile.DECK, bg_card).sum == 0.0


# ---------------------------------------------------------------------------
# Influence (spec §8, §9)
# ---------------------------------------------------------------------------


def test_space_influence_value(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    assert g.GainInfluenceAbility(space("secrets")).value_for_player(p).sum == 3.0
    assert g.GainInfluenceAbility(space("fremkit")).value_for_player(p).sum == 1.0
    assert g.GainInfluenceAbility(space("arrakeen")).value_for_player(p).sum == 0.0


def test_gain_any_influence_value_is_the_best_faction(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    ability = g.GainAnyInfluenceAgentAbility(space("shipping"))
    assert ability.value_for_player(p).sum == 3.0  # Bene Gesserit
    assert g.gain_any_influence_value(p, -1).sum == -3.0  # min: Bene Gesserit


def test_gain_any_influence_evaluate_static_boost_first_strict_max(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    ability = g.GainAnyInfluenceAgentAbility(space("shipping"))
    answer = ability.evaluate(
        p, req(track_entity("emperor"), track_entity("bene_gesserit"))
    )
    assert answer.value == pytest.approx(103.0)
    assert answer.response == (("bene_gesserit",),)
    flat = prof(
        turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(1.0)
    )
    tie = ability.evaluate(flat, req(track_entity("fremen"), track_entity("emperor")))
    assert tie.response == (("fremen",),)
    assert ability.evaluate(p, Request()).response is None


# ---------------------------------------------------------------------------
# Intrigue (spec §10)
# ---------------------------------------------------------------------------


def test_gain_intrigue_value_and_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    ability = g.AgentGainIntrigueAbility(space("sardaukar"))
    assert ability.value_for_player(p).sum == 2.25
    assert ability.evaluate(p, Request()) == Answer(
        100.0, (), "GainIntrigueAbility | 100"
    )


def test_custom_intrigue_value_needs_the_custom_grant(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = prof(turn_state)
    ability = g.GainIntrigueCustomAbility(space("sardaukar"))
    # Cost @0x4ce0ae0 = NoCost.Then(HasCustomAbility): no grant, no value.
    assert not ability.meets_cost(p)
    assert ability.value_for_player(p).sum == 0.0
    monkeypatch.setattr(ability, "has_custom_ability", lambda _p: True)
    assert ability.meets_cost(p)
    assert ability.value_for_player(p).sum == 2.25
    assert ability.evaluate(p, Request()) == Answer(
        100.0, (), "GainIntrigueAbility | 100"
    )


def test_high_council_intrigue_only_on_a_repeat_visit(
    turn_state: GameState, effects_state: GameState, prof: ProfileFactory
) -> None:
    ability = g.HighCouncilGainIntrigueAbility(space("high_council"))
    p = prof(turn_state)
    assert ability.value_for_player(p).sum == 0.0
    assert ability.selection_mode(p) == SelectionMode.IMPLICIT
    seated = prof(with_player(turn_state, SEAT, high_council=True))
    assert ability.value_for_player(seated).sum == 2.25
    assert ability.selection_mode(seated) == SelectionMode.EXPLICIT
    first_visit = with_frame(
        effects_state, space_id="high_council", board_icons="high_council"
    )
    first_visit = with_player(first_visit, SEAT, high_council=True)
    assert ability.value_for_player(prof(first_visit)).sum == 0.0


# ---------------------------------------------------------------------------
# Deploy (spec §11)
# ---------------------------------------------------------------------------


def test_deploy_value_and_the_shaddam_gap(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = g.DeployUnitsAbility(space("arrakeen"))
    dagger = starter("dagger")
    assert ability.value_for_player(prof(turn_state), (dagger,)).sum == 1.25
    shaddam = with_player(
        turn_state, SEAT, leader_id="shaddam_corrino_iv", leader_face_id=None
    )
    assert ability.value_for_player(prof(shaddam), (dagger,)).sum == 0.0
    signet = starter("signet_ring")
    assert ability.value_for_player(prof(shaddam), (signet,)).sum == 1.25
    assert ability.value_for_player(prof(shaddam)).sum == 1.25


def test_deploy_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = g.DeployUnitsAbility(space("arrakeen"))
    p = prof(turn_state)
    answer = ability.evaluate(p, req(options=(0, 1, 2), max_select=2))
    assert answer.value == 0.5
    assert answer.response == ((0, 1),)
    none = prof(turn_state, units_to_deploy=lambda garrison, max_units: 0)
    assert ability.evaluate(none, req(options=(0, 1))).response is None
    assert ability.evaluate(none, req(options=(0, 1))).value == 0.0
    assert ability.evaluate(p, Request()).value == 0.0


# ---------------------------------------------------------------------------
# Trash (spec §12)
# ---------------------------------------------------------------------------


def test_trash_value_and_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = g.TrashAgentAbility(space("desert_tactics"))
    p = prof(turn_state)
    assert ability.value_for_player(p).sum == pytest.approx(2.75 + 1.0)
    dagger = starter("dagger")
    found = prof(turn_state, card_to_trash=lambda targets, minimum: (targets[0], 10.5))
    assert ability.evaluate(found, req(dagger)) == Answer(
        10.5, ((dagger.ref,),), f"Trash {dagger.ref}"
    )
    # Nothing worth trashing: "use" at the start value 1.0 and trash nothing.
    seen: list[float] = []

    def nothing(targets: Sequence[Entity], minimum: float) -> tuple[None, float]:
        seen.append(minimum)
        return None, minimum

    answer = g.TrashConflictCustomAbility(space("arrakeen")).evaluate(
        prof(turn_state, card_to_trash=nothing), req(dagger)
    )
    assert answer.value == 1.0
    assert answer.response == ((),)
    assert seen == [1.0]


# ---------------------------------------------------------------------------
# Spies (spec §13) and agent recall (spec §14)
# ---------------------------------------------------------------------------


def test_place_spy_value_and_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    ability = g.PlaceSpyAgentAbility(space("espionage"))
    assert ability.value_for_player(p).sum == 1.66
    assert ability.evaluate(p, req(space("espionage"))) == Answer(1.66, (), "Place Spy")


def test_recall_agent_value_and_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = g.RecallAgentAbility(space("imperial_privilege"))
    p = prof(turn_state)
    assert ability.value_for_player(p).sum == 5.0
    a1 = agent_entity("arrakeen", SEAT)
    a2 = agent_entity("secrets", SEAT)
    assert ability.evaluate(p, req(a1, a2)).response == (("arrakeen",),)
    pick = prof(turn_state, recall_agent=lambda agents: agents[1])
    answer = ability.evaluate(pick, req(a1, a2))
    assert answer.response == (("secrets",),)
    assert answer.value == 5.0
    assert ability.evaluate(p, req()).response is None


# ---------------------------------------------------------------------------
# Contracts (spec §15, §16; board.md §3)
# ---------------------------------------------------------------------------


def test_gain_contract_value_needs_contract_options(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = g.GainContractAbility(space("accept_contract"))
    assert ability.value_for_player(prof(turn_state)).sum == 2.0
    empty = with_state(turn_state, face_up_contract_ids=())
    assert ability.value_for_player(prof(empty)).sum == 0.5  # 2 Solari
    shaddam = with_player(
        empty, SEAT, leader_id="shaddam_corrino_iv", leader_face_id=None
    )
    shaddam = give_contracts(shaddam, SEAT)
    bank = tuple(c for c in shaddam.contract_bank if c != "contract:sardaukar_i")
    shaddam = with_state(
        shaddam, contract_bank=bank, sardaukar_contract_ids=("contract:sardaukar_i",)
    )
    assert ability.value_for_player(prof(shaddam)).sum == 2.0
    custom = g.GainContractCustomAbility(conflict_entity("choam_security", True))
    assert custom.value_for_player(prof(empty)).sum == 0.5


def test_contract_evaluate_branches(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = g.GainContractAbility(space("accept_contract"))
    c1 = contract_entity("contract:immediate")
    c2 = contract_entity("contract:arrakeen_i")
    forced: list[bool] = []

    def best(cs: Sequence[Entity], f: bool) -> tuple[Entity | None, float]:
        forced.append(f)
        return (cs[1], 2.5) if cs else (None, 1.0)

    answer = ability.evaluate(prof(turn_state, best_contract=best), req(c1, c2))
    assert answer.value == 2.5
    assert answer.response == ((c2.ref,),)
    assert forced == [True]
    no_targets = ability.evaluate(prof(turn_state), req())
    assert no_targets.value == 0.5
    assert no_targets.response == ()
    no_best = prof(turn_state, best_contract=lambda cs, f: (None, 0.0))
    assert ability.evaluate(no_best, req(c1)) == Answer(0.0, None, "No contract chosen")
    assert g.contract_evaluate(prof(turn_state, best_contract=best), req(c1, c2), False)
    assert forced[-1] is False


def test_contract_completion_value(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    immediate = g.ContractAbility(contract_entity("contract:immediate"))  # Solari 2
    assert immediate.value_for_player(p).sum == 0.5
    water = g.ContractAbility(contract_entity("contract:arrakeen_i"))  # Water 1
    assert water.value_for_player(p, (space("arrakeen"),)).sum == 1.0
    assert water.value_for_player(p, (space("imperial_basin"),)).sum == 0.0
    assert water.value_for_player(p).sum == 0.0
    assert water.evaluate(p, Request()).value == 100.0
    draw2 = g.Draw2ContractAbility(contract_entity("contract:spice_refinery_i"))
    # 2 x CardDrawValue and GetBuyGains(2 x PossiblePersuasionGain) (disassembly).
    assert draw2.resource_value(p).sum == pytest.approx(2 * 1.5 + 0.1 * 6)
    spy = g.PlaceSpyContractAbility(contract_entity("contract:arrakeen_ii"))  # Troop 1
    assert spy.resource_value(p).sum == pytest.approx(0.9 + 1.66)
    assert spy.evaluate(p, Request()) == Answer(1.66, (), "Place Spy Contract")


def test_contract_specific_acquire_value_immediate_and_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    immediate = g.ContractAbility(contract_entity("contract:immediate"))
    assert immediate.specific_acquire_value(p).sum == 0.5
    # Espionage I (Solari 3, BG icon), round 1: k = 1.0.
    espionage = g.ContractAbility(contract_entity("contract:espionage_i"))
    reward = 0.5 * 0.75 * 1.0
    assert espionage.specific_acquire_value(p).sum == pytest.approx(reward - 5 * 0.17)
    icons = prof(turn_state, deck_agent_icons=lambda: {"BeneGesserit": 3})
    assert espionage.specific_acquire_value(icons).sum == pytest.approx(reward + 0.34)
    spied = with_spies(turn_state, SEAT, "bene-gesserit-espionage-secrets")
    assert espionage.specific_acquire_value(prof(spied)).sum == pytest.approx(
        reward - 0.85 + 2 * 0.16
    )
    late = with_state(turn_state, round_number=8)  # k floors at 0.25
    assert espionage.specific_acquire_value(prof(late)).sum == pytest.approx(
        0.5 * 0.75 * 0.25 - 0.85
    )


def test_contract_specific_acquire_value_resource_mods(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    heighliner = g.ContractAbility(contract_entity("contract:heighliner_i"))  # Water 2
    two_icons = {"SpacingGuild": 2}
    rich = prof(turn_state, deck_agent_icons=lambda: two_icons)
    assert heighliner.specific_acquire_value(rich).sum == pytest.approx(1.0 + 0.48)
    poor = prof(
        turn_state, deck_agent_icons=lambda: two_icons, abundance_level=lambda a: 0
    )
    assert heighliner.specific_acquire_value(poor).sum == pytest.approx(1.0 - 0.48)
    none = prof(
        turn_state, deck_agent_icons=lambda: two_icons, abundance_level=lambda a: -1
    )
    assert heighliner.specific_acquire_value(none).sum == pytest.approx(1.0)
    refinery = g.ContractAbility(
        contract_entity("contract:spice_refinery_ii")
    )  # Water 1
    assert refinery.specific_acquire_value(prof(turn_state)).sum == pytest.approx(
        0.5 - 0.48
    )
    dear = prof(turn_state, solari_value=lambda n: 0.95 * n)
    assert refinery.specific_acquire_value(dear).sum == pytest.approx(0.5 + 0.48)


def test_contract_specific_acquire_value_harvest_and_acquire(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    bonus = with_state(
        turn_state,
        maker_bonus_spice=(
            ("deep_desert", 1),
            ("hagga_basin", 2),
            ("imperial_basin", 0),
        ),
    )
    harvest = g.ContractAbility(contract_entity("contract:harvest_3"))  # Solari 3
    assert harvest.specific_acquire_value(prof(bonus)).sum == pytest.approx(
        0.5 * 0.75 - 3 * 0.33 + 0.33 * 0.33 * 3
    )
    acquire = g.ContractAbility(contract_entity("contract:acquire"))  # Solari 3
    assert acquire.specific_acquire_value(prof(turn_state)).sum == pytest.approx(
        0.34 * 0.75 - 0.99 - 0.99
    )
    seated = with_player(turn_state, SEAT, high_council=True)
    late = prof(seated, game_arc=lambda: 2)
    assert acquire.specific_acquire_value(late).sum == pytest.approx(
        0.34 * 0.75 + 0.99 + 0.99
    )
    mid = prof(turn_state, game_arc=lambda: 1)
    assert acquire.specific_acquire_value(mid).sum == pytest.approx(0.34 * 0.75 - 0.99)


# ---------------------------------------------------------------------------
# Battle for Arrakeen, Shield Wall (spec §21, §22)
# ---------------------------------------------------------------------------


def test_recall_two_spies_for_vp(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = conflict_entity("battle_for_arrakeen", True)
    ability = g.Recall2SpiesVPAbility(owner)
    two = with_spies(turn_state, SEAT, "arrakis-deep-desert", "arrakis-hagga-basin")
    # Not granted at placement valuation.
    assert ability.value_for_player(prof(two)).sum == 0.0
    granted = prof(two, decision_kind="combat_reward_spy_recall")
    assert ability.value_for_player(granted).sum == pytest.approx(6.0 - 2 * 1.66)
    spies = (
        spy_entity("arrakis-deep-desert", SEAT),
        spy_entity("arrakis-hagga-basin", SEAT),
    )
    answer = ability.evaluate(granted, req(*spies))
    assert answer.value == pytest.approx(6.0 - 3.32)
    assert answer.response == (("arrakis-deep-desert", "arrakis-hagga-basin"),)
    one = prof(two, recall_spies=lambda s, take: ([s[0]], 0.0))
    assert ability.evaluate(one, req(*spies)).response is None
    assert ability.possible_conflict_vp(prof(two), False) == 1
    assert ability.possible_conflict_vp(prof(two), True) == 0
    assert ability.possible_conflict_vp(prof(turn_state), False) == 0


def test_blow_wall_always_used(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = g.BlowWallCustomAbility(space("sietch_tabr"))
    p = prof(turn_state)
    assert ability.evaluate(p, Request()).value == 100.0
    assert ability.value_for_player(p).sum == 0.0
    assert ability.meets_cost(p)
    assert not ability.meets_cost(
        prof(with_state(turn_state, shield_wall_present=False))
    )


# ---------------------------------------------------------------------------
# SpaceAbility (spec §6.1)
# ---------------------------------------------------------------------------


def _space_v(p: Profile, space_id: str) -> float:
    return g.SpaceAbility(space(space_id)).value_for_player(p).sum


def test_space_printed_gains_and_costs(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    assert _space_v(p, "arrakeen") == pytest.approx(0.9)
    assert _space_v(p, "sardaukar") == pytest.approx(4 * 0.9 - 4 * 0.5)
    assert _space_v(p, "shipping") == pytest.approx(5 * 0.25 - 3 * 0.5)
    assert _space_v(p, "deliver_supplies") == pytest.approx(1.0)
    assert _space_v(p, "hagga_basin") == pytest.approx(-1.0)  # no spice, water cost
    assert _space_v(p, "imperial_privilege") == pytest.approx(-0.75)
    assert _space_v(p, "imperial_basin") == pytest.approx(0.5)


def test_space_bonus_spice_is_scaled(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    bonus = with_state(
        turn_state,
        maker_bonus_spice=(
            ("deep_desert", 3),
            ("hagga_basin", 0),
            ("imperial_basin", 2),
        ),
    )
    p = prof(bonus)
    assert _space_v(p, "imperial_basin") == pytest.approx((1 + 2 * 1.25) * 0.5)
    assert _space_v(p, "deep_desert") == pytest.approx(3 * 1.25 * 0.5 - 3.0)


def test_swordmaster_cost_drops_after_the_first(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    assert _space_v(prof(turn_state), "swordmaster") == pytest.approx(-2.0)
    taken = with_player(turn_state, 0, swordmaster_acquired=True, agents_available=3)
    assert _space_v(prof(taken), "swordmaster") == pytest.approx(-1.5)


def test_space_contracts_count_even_when_completed(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    held = give_contracts(turn_state, SEAT, active=("contract:arrakeen_i",))
    assert _space_v(prof(held), "arrakeen") == pytest.approx(0.9 + 1.0 + 1.0)
    both = give_contracts(
        turn_state,
        SEAT,
        active=("contract:arrakeen_i",),
        completed=("contract:arrakeen_ii",),
    )
    assert _space_v(prof(both), "arrakeen") == pytest.approx(
        0.9 + (0.9 + 1.66) + 1.0 + 1.0 + 1.0
    )
    assert _space_v(prof(both), "imperial_basin") == pytest.approx(0.5)


def test_space_infiltration_and_gather_intelligence(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    occupied = with_player(
        turn_state, 0, agent_locations=("arrakeen",), agents_available=1
    )
    assert _space_v(prof(occupied), "arrakeen") == pytest.approx(0.9 - 0.33 * 1.66)
    posts = (
        "arrakis-spice-refinery-arrakeen",
        "arrakis-deep-desert",
        "arrakis-hagga-basin",
    )
    three = with_spies(occupied, SEAT, *posts)
    # 3 spies: flat -0.5; the one observing spy is used up by the infiltration.
    assert _space_v(prof(three), "arrakeen") == pytest.approx(0.9 - 0.5)
    watching = with_spies(turn_state, SEAT, "arrakis-spice-refinery-arrakeen")
    assert _space_v(prof(watching), "arrakeen") == pytest.approx(0.9 + 1.25)
    cheap_draw = prof(watching, card_draw_value_with_buy_gains=lambda: 1.0)
    assert _space_v(cheap_draw, "arrakeen") == pytest.approx(0.9)
    watching_three = with_spies(turn_state, SEAT, *posts)
    three_cheap = prof(watching_three, card_draw_value_with_buy_gains=lambda: 1.0)
    assert _space_v(three_cheap, "arrakeen") == pytest.approx(0.9 + 1.25)


class _FakeReverendMother(g.DeferredAbility):
    APP_CLASS: ClassVar[str] = (
        "worm.canis.abilities.ActivatedAbilities.Uprising.ReverendMotherAbility"
    )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        assert [e.ref for e in with_entities] == ["secrets"]
        return Summer(0.8)


def test_space_reverend_mother_term(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(PORTS, _FakeReverendMother.APP_CLASS, _FakeReverendMother)
    flipped = with_player(turn_state, SEAT, leader_face_id="reverend_mother_jessica")
    assert _space_v(prof(flipped), "secrets") == pytest.approx(0.8)
    assert _space_v(prof(turn_state), "secrets") == 0.0
    # An Emperor space never takes the term.
    assert _space_v(prof(flipped), "dutiful_service") == 0.0


# ---------------------------------------------------------------------------
# AgentAbility, PowerPlayAgentAbility, RevealAbility (spec §2, §3)
# ---------------------------------------------------------------------------


def test_agent_value_reveal_penalty(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    dagger = g.AgentAbility(starter("dagger"))
    v = dagger.value_for_player(prof(turn_state), (space("arrakeen"),))
    assert v.sum == pytest.approx(-0.5 * 0.66)


def test_agent_value_merges_agent_timed_deferred_abilities(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    steersman = g.AgentAbility(imperium("steersman"))  # Draw + Recall Agent (Agent)
    v = steersman.value_for_player(prof(turn_state), (space("arrakeen"),))
    reveal = 2 * 0.75 + 2 * 0.5  # Persuasion 2, Spice 2
    assert v.sum == pytest.approx(1.8 + 5.0 - 0.5 * reveal)


def test_agent_value_printed_agent_box(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    card = synth(
        Kind.CARD,
        "box",
        AgentWater=1,
        AgentSpice=2,
        AgentSolari=3,
        AgentTroops=2,
        WormAbilityIDs=(AG + "PlayAbilities.AgentAbility",),
    )
    v = g.AgentAbility(card).value_for_player(prof(turn_state), (space("arrakeen"),))
    assert v.sum == pytest.approx(1.0 + 1.0 + 0.75 + 1.8)


class _FakeSignetBase(g.DeferredAbility):
    APP_CLASS: ClassVar[str] = "worm.canis.abilities.ActivatedAbilities.SignetAbility"


class _FakeSpiceAgony(_FakeSignetBase):
    APP_CLASS: ClassVar[str] = (
        "worm.canis.abilities.ActivatedAbilities.Uprising.SpiceAgonyAbility"
    )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        assert [e.ref for e in with_entities] == ["arrakeen"]
        return Summer(0.7)


def test_agent_value_merges_the_leader_signet_for_signet_cards(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(PORTS, _FakeSpiceAgony.APP_CLASS, _FakeSpiceAgony)
    signet = g.AgentAbility(starter("signet_ring"))
    v = signet.value_for_player(prof(turn_state), (space("arrakeen"),))
    assert v.sum == pytest.approx(0.7 - 0.5 * 0.75)
    dagger = g.AgentAbility(starter("dagger"))
    assert dagger.value_for_player(prof(turn_state), (space("arrakeen"),)).sum == (
        pytest.approx(-0.33)
    )


def test_agent_value_imperium_play_bonus(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = synth(
        Kind.CARD,
        "bg",
        FactionList=("BeneGesserit",),
        WormAbilityIDs=(AG + "PlayAbilities.AgentAbility",),
    )
    helper = synth(
        Kind.CARD,
        "helper",
        WormAbilityIDs=(
            AG + "ActivatedAbilities.BeneGesseritDrawAbility",
            AG + "ActivatedAbilities.DeployUnitsAbility",
        ),
    )
    monkeypatch.setattr(g, "_hand_cards", lambda p: [owner, helper])
    ability = g.AgentAbility(owner)
    v = ability.value_for_player(prof(turn_state), (space("arrakeen"),))
    assert v.sum == pytest.approx(0.75 * 1.8)
    # The owner itself is skipped: alone in hand, no bonus.
    monkeypatch.setattr(g, "_hand_cards", lambda p: [owner])
    assert ability.value_for_player(prof(turn_state), ()).sum == 0.0
    # Bonus terms are added only when one is strictly positive.
    one_agent = with_player(
        turn_state, SEAT, agents_available=1, agent_locations=("secrets",)
    )
    monkeypatch.setattr(g, "_hand_cards", lambda p: [owner, helper])
    assert ability.value_for_player(prof(one_agent), ()).sum == 0.0


def test_agent_evaluate_space_loop(turn_state: GameState, prof: ProfileFactory) -> None:
    dagger = g.AgentAbility(starter("dagger"))
    p = prof(turn_state)
    answer = dagger.evaluate(p, req(space("imperial_basin"), space("arrakeen")))
    # Arrakeen: deploy 1.25 + draw 1.8 + troop 0.9; card -0.33.
    assert answer.value == pytest.approx(1.25 + 1.8 + 0.9 - 0.33)
    assert answer.response == (("arrakeen",),)
    assert dagger.evaluate(p, Request()).response is None


def test_agent_evaluate_first_candidate_sticks_and_ties_keep_it(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    zero = {
        name: (lambda *a, **k: 0.0)
        for name in ("resource_value", "deploy_value", "card_draw_value", "buy_gains")
    }
    p = prof(
        turn_state,
        troop_value=lambda n, i=False: 0.0,
        spice_value=lambda n: 0.0,
        **zero,
    )
    dagger = g.AgentAbility(starter("dagger"))
    answer = dagger.evaluate(p, req(space("imperial_basin"), space("arrakeen")))
    assert answer.value == 0.0
    assert answer.response == (("imperial_basin",),)
    negative = prof(turn_state, deploy_value=lambda owner: -5.0)
    worst = dagger.evaluate(negative, req(space("imperial_basin")))
    assert worst.value < 0
    assert worst.response == (("imperial_basin",),)


def test_agent_evaluate_skips_spaces_without_a_runnable_space_ability(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        g.SpaceAbility, "can_be_run", lambda self, p: self.owner.ref != "arrakeen"
    )
    dagger = g.AgentAbility(starter("dagger"))
    answer = dagger.evaluate(
        prof(turn_state), req(space("arrakeen"), space("imperial_basin"))
    )
    assert answer.response == (("imperial_basin",),)
    # Assembly Hall holds no SpaceAbility-derived port of ours: skipped.
    bare = synth(
        Kind.SPACE, "bare", WormAbilityIDs=(AG + "ActivatedAbilities.DrawAbility",)
    )
    assert dagger.evaluate(prof(turn_state), req(bare)).response is None


def test_power_play_bonus_influence(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    overthrow = imperium("overthrow")
    power = g.PowerPlayAgentAbility(overthrow)
    plain = g.AgentAbility(overthrow)
    p = prof(turn_state)
    secrets = (space("secrets"),)
    reveal = -0.5 * (2 * 0.75 + 2 * 0.66 + 0.9)
    assert plain.value_for_player(p, secrets).sum == pytest.approx(reveal)
    assert power.value_for_player(p, secrets).sum == pytest.approx(reveal + 6.0 - 3.0)
    arrakeen = (space("arrakeen"),)
    assert power.value_for_player(p, arrakeen).sum == pytest.approx(reveal)


class _FakeRevealTrigger(g.TriggeredAbility):
    timing: ClassVar[Timing] = Timing.REVEAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        return Summer(0.4)


def test_reveal_value(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(PORTS, "Test.RevealTrigger", _FakeRevealTrigger)
    card = synth(
        Kind.CARD,
        "rv",
        Water=1,
        Spice=1,
        Solari=1,
        Persuasion=1,
        Strength=1,
        Troops=1,
        Specimen=1,
        WormAbilityIDs=(
            AG + "PlayAbilities.RevealAbility",
            AG + "ActivatedAbilities.RevealGainIntrigueAbility",
            AG + "ActivatedAbilities.AgentGainIntrigueAbility",
            "Test.RevealTrigger",
        ),
    )
    v = g.RevealAbility(card).value_for_player(prof(turn_state))
    printed = 1.0 + 0.5 + 0.25 + 0.75 + 0.66 + 0.1 + 0.9
    assert v.sum == pytest.approx(printed + 2.25 + 0.4)
    assert g.value_for_reveal_abilities(card, prof(turn_state)).sum == pytest.approx(
        printed + 2.25 + 0.4
    )


# ---------------------------------------------------------------------------
# AcquireAbility (spec §4)
# ---------------------------------------------------------------------------


def test_acquire_evaluate(
    turn_state: GameState, combat_state: GameState, prof: ProfileFactory
) -> None:
    dagger = g.AcquireAbility(starter("dagger"))
    p = prof(turn_state)
    assert dagger.evaluate(p, Request()).value == 3.0
    assert dagger.evaluate(p, Request()).response == ()
    picker = req(options=(0, 1))
    assert dagger.evaluate(p, picker).response == ((0,),)
    tsmf = g.AcquireAbility(card_entity("reserve:the_spice_must_flow:0", SEAT))
    assert tsmf.evaluate(p, picker).response == ((1,),)
    poor = prof(turn_state, acquire_value=lambda card: Summer(-2.0))
    assert dagger.evaluate(poor, picker).value == -2.0
    combat = prof(combat_state, seat=0, acquire_value=lambda card: Summer(-2.0))
    assert dagger.evaluate(combat, picker).value == 1.0
    assert dagger.evaluate(combat, Request()).value == -2.0


# ---------------------------------------------------------------------------
# Triggered: BondAbility (spec §17)
# ---------------------------------------------------------------------------


class _FremenBond(g.BondAbility):
    bond_faction: ClassVar[str | None] = "Fremen"


class _EmperorBond(g.BondAbility):
    bond_faction: ClassVar[str | None] = "Emperor"


def test_bond_pile_synergy(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("northern_watermaster")
    fremen = imperium("stilgar_the_devoted")
    p = prof(turn_state)
    assert (
        _FremenBond(owner).value_in_pile_for_other_play(p, Pile.DECK, fremen).sum == 0.5
    )
    assert (
        _FremenBond(owner).value_in_pile_for_other_play(p, Pile.PLAY_AREA, fremen).sum
        == 0.0
    )
    assert (
        _EmperorBond(owner).value_in_pile_for_other_play(p, Pile.DECK, fremen).sum
        == 0.0
    )
    climax = prof(turn_state, is_climax=lambda: True)
    assert (
        _FremenBond(owner).value_in_pile_for_other_play(climax, Pile.DECK, fremen).sum
        == 0.0
    )
    # The default tag synergy is not added: Northern Watermaster is Fremen and
    # Stilgar carries no Want tag, but a FremenBond candidate would.
    shishakli = imperium("shishakli")
    assert (
        _FremenBond(owner).value_in_pile_for_other_play(p, Pile.DECK, shishakli).sum
        == 0.5
    )


# ---------------------------------------------------------------------------
# Conflict rewards (spec §18-§20)
# ---------------------------------------------------------------------------


def _conflict(state: GameState, conflict_id: str) -> GameState:
    return set_conflict(state, conflict_id)


def test_generic_conflict_reward_values(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    sietches = conflict_entity("protect_the_sietches", True)
    first = g.GenericConflictFirstAbility(sietches).value_for_player(p).sum
    assert first == pytest.approx(1.0 + 1.0 + 0.9 + 2.5)  # water, Fremen, troop, icon
    second = g.GenericConflictSecondAbility(sietches).value_for_player(p).sum
    assert second == pytest.approx(3 * 0.5 + 0.9)
    third = g.GenericConflictThirdAbility(sietches).value_for_player(p).sum
    assert third == pytest.approx(2 * 0.5)
    icons: list[str] = []

    def icon(name: str) -> Summer:
        icons.append(name)
        return Summer(2.5)

    skirmish = conflict_entity("skirmish_crysknife", True)
    assert g.GenericConflictFirstAbility(skirmish).value_for_player(
        prof(turn_state, battle_icon_value=icon)
    ).sum == pytest.approx(3.0 + 2.5)  # GainAnyInfluenceConflict: best faction
    assert icons == ["Crysknife"]


def test_take_control_reads_the_current_conflict(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    siege = conflict_entity("siege_of_arrakeen", True)
    first = g.GenericConflictFirstAbility(siege)
    current = prof(_conflict(turn_state, "siege_of_arrakeen"))
    assert first.value_for_player(current).sum == pytest.approx(0.5 + 1.8 + 4.0 + 2.5)
    other = prof(_conflict(turn_state, "skirmish_crysknife"))
    assert first.value_for_player(other).sum == pytest.approx(0.5 + 1.8 + 2.5)
    take = g.TakeControlConflictAbility(siege)
    basin = prof(_conflict(turn_state, "battle_for_imperial_basin"))
    assert take.value_for_player(basin).sum == 4.0  # spice control priced as Solari
    assert take.value_for_player(prof(set_conflict(turn_state, None))).sum == 0


def test_battle_for_imperial_basin_first_place(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    rich = with_player(turn_state, SEAT, resources=Resources(spice=5))
    p = prof(_conflict(rich, "battle_for_imperial_basin"))
    battle = conflict_entity("battle_for_imperial_basin", True)
    first = g.GenericConflictFirstAbility(battle)
    # VP 6 + take control 4 + (pay 4 spice -2 + VP 6) + battle icon 2.5.
    assert first.value_for_player(p).sum == pytest.approx(6.0 + 4.0 + 4.0 + 2.5)
    assert first.possible_reward_vp(p, False) == 2
    assert first.possible_reward_vp(p, True) == 1
    assert g.GenericConflictSecondAbility(battle).possible_reward_vp(p, False) == 0


def test_battle_for_arrakeen_possible_reward_vp(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    battle = conflict_entity("battle_for_arrakeen", True)
    first = g.GenericConflictFirstAbility(battle)
    two = with_spies(turn_state, SEAT, "arrakis-deep-desert", "arrakis-hagga-basin")
    assert first.possible_reward_vp(prof(two), False) == 2
    assert first.possible_reward_vp(prof(two), True) == 1
    assert first.possible_reward_vp(prof(turn_state), False) == 1


def test_conflict_ability_base_reward_vp(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    class _First(g.ConflictAbility):
        place: ClassVar[int | None] = 1

    owner = synth(Kind.CONFLICT, "c", VictoryPoints=2)
    assert _First(owner).possible_reward_vp(prof(turn_state), False) == 2
    assert (
        g.TakeControlConflictAbility(owner).possible_reward_vp(prof(turn_state), False)
        == 0
    )


def test_value_for_rewards_from_every_term(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    reward = synth(
        Kind.CONFLICT,
        "reward",
        VictoryPoints=1,
        Water=1,
        Spice=2,
        Solari=3,
        FactionInfluence={"Emperor": 1, "Fremen": 0},
        Troops=2,
        IntrigueCard=2,
        CustomAbilityIDs=(AG + "ActivatedAbilities.GainAnyInfluenceConflictAbility",),
    )
    conflict = conflict_entity("skirmish_crysknife", True)
    flat = prof(
        turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(10.0)
    )
    v = g.value_for_rewards_from(flat, reward, conflict)
    # VP 6, resources 1 + 1 + 0.75, influence 10 + 10 (n = 0 still added),
    # troops 1.8, intrigue 4.5, custom "any influence" 10.
    assert v.sum == pytest.approx(6.0 + 2.75 + 20.0 + 1.8 + 4.5 + 10.0)


def test_pay_to_gain_vp(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = conflict_entity("battle_for_spice_refinery", True)
    solari = g.Pay6SolariToGain1VPAbility(owner)
    rich = with_player(turn_state, SEAT, resources=Resources(solari=7, spice=3))
    poor = with_player(turn_state, SEAT, resources=Resources(solari=5))
    assert solari.value_for_player(prof(rich)).sum == pytest.approx(-1.5 + 6.0)
    assert solari.value_for_player(prof(poor)).sum == pytest.approx(6.0)  # quirk
    spice = g.Pay3SpiceToGain1VPAbility(owner)
    assert spice.value_for_player(prof(rich)).sum == pytest.approx(-1.5 + 6.0)
    assert solari.evaluate(prof(poor), Request()).value == 100.0
    assert not solari.meets_cost(prof(rich))
    assert solari.meets_cost(prof(rich, decision_kind="combat_reward_optional"))
    assert not solari.meets_cost(prof(poor, decision_kind="combat_reward_optional"))
    four = g.Pay4SpiceToGain1VPAbility(owner)
    five = with_player(turn_state, SEAT, resources=Resources(spice=5))
    assert four.possible_conflict_vp(prof(five), False) == 1
    assert four.possible_conflict_vp(prof(five), True) == 0
    twelve = with_player(turn_state, SEAT, resources=Resources(solari=12))
    assert solari.possible_conflict_vp(prof(twelve), True) == 1
    assert solari.possible_conflict_vp(prof(poor), False) == 0


def test_conflict_reward_lookup_uses_the_place(turn_state: GameState) -> None:
    sietches = conflict_entity("protect_the_sietches", True)
    assert g.conflict_reward(sietches, 2).short == (
        "ConflictArchetypes.Uprising.ProtecttheSietchesUPSecond"
    )
    assert (
        g.conflict_reward(sietches, 1).archetype
        is ARCHETYPES["ConflictArchetypes.Uprising.ProtecttheSietchesUPFirst"]
    )


def test_contract_trigger_has_no_ai_hook(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    contract = contract_entity("contract:arrakeen_i")
    trigger = g.ActivateContractTriggeredAbility(contract)
    p = prof(turn_state)
    assert isinstance(trigger, g.TriggeredAbility)
    assert trigger.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    assert trigger.evaluate(p, Request()).value == 0.0
    # The completion ability is the contract's first ContractAbility.
    assert type(g._first_contract_ability(contract)) is g.ContractAbility


def test_intrigue_entities_carry_defer_values() -> None:
    assert intrigue_entity("intrigue:change_allegiances:0").int_attr("DeferValue") == 2
