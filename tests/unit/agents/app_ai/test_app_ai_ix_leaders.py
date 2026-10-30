"""Rise of Ix's leader ports (abilities/ix_leaders.py).

Real original + Rise of Ix ``GameState`` plus stubbed ``Profile`` prices, as
in ``test_app_ai_original_leaders.py``: each branch, literal and constant of
the decompiled methods is pinned by hand (the addresses are in the port's
docstrings).
"""

import math
from collections.abc import Callable, Sequence
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import (
    PORTS,
    Ability,
    SelectionMode,
    Timing,
    UnportedAbility,
    abilities_of,
    generic,
)
from dune_imperium.agents.app_ai.abilities import ix_leaders as ixl
from dune_imperium.agents.app_ai.abilities import leaders as leaders_module
from dune_imperium.agents.app_ai.abilities import original_intrigue as oi
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    TriggeredAbility,
)
from dune_imperium.agents.app_ai.abilities.leaders import SignetAbility
from dune_imperium.agents.app_ai.abilities.tech import IxianTechnologyAbility
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    intrigue_entity,
    leader_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True, leader_draft=True
)
BOARD = Board.of(IX)
ENGINE = UprisingRulesEngine()
AA = "worm.canis.abilities.ActivatedAbilities.RiseOfIx."
TA = "worm.canis.abilities.TriggeredAbilities.RiseOfIx."
PA = "worm.canis.abilities.PlayAbilities.RiseOfIx."

#: ``ConscriptBeforeLateValue`` of the default level's table (constants.py).
BEFORE_LATE = 1.75


def _stubs() -> dict[str, Callable[..., Any]]:
    return {
        "is_climax": lambda: False,
        "game_arc": lambda: 1,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            {"none": 2.5}.get(f, 2.0) * n
        ),
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "foldspace_value": lambda: 3.25,
        "freighter_value": lambda: 4.2,
        "freighter_selections": lambda space=-1: (1, 0, "Level 3"),
        "acquire_value": lambda card: Summer(card.int_attr("PersuasionCost") + 0.5),
        "can_agent_ability_be_played_with_space": lambda space, attr, n: True,
        "card_to_trash": lambda targets, minimum: (
            (targets[0], 1.5) if targets else (None, minimum)
        ),
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """The first original + Ix ``turn`` decision (round 1), its Imperium Row
    pinned to ``FIXTURE_ROW`` (the deck takes back what the setup laid out),
    so the content P4 adds cannot reshuffle it."""

    state = first_decision("turn", config=IX)
    deck = tuple(
        c for c in (*state.imperium_deck, *state.imperium_row) if c not in FIXTURE_ROW
    )
    return with_state(state, imperium_row=FIXTURE_ROW, imperium_deck=deck)


#: Lady Jessica 7, Guild Bankers 3, Sayyadina 3, CHOAM Directorship 8, Piter
#: de Vries 5.
FIXTURE_ROW = (
    "imperium:lady_jessica_card:0",
    "imperium:guild_bankers:0",
    "imperium:sayyadina:0",
    "imperium:choam_directorship:0",
    "imperium:piter_de_vries_card:0",
)


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, **stub overrides) -> Profile`` for the deciding seat."""

    def build(state: GameState, **overrides: Callable[..., Any]) -> Profile:
        profile = make_profile(state, _seat(state))
        stubs = _stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


@pytest.fixture
def signet(monkeypatch: pytest.MonkeyPatch) -> Callable[[bool], None]:
    """Set ``HasSignet`` (``SignetAbility::Cost``) for the signet ports."""

    def set_signet(held: bool) -> None:
        monkeypatch.setattr(leaders_module, "_has_signet_icon", lambda p: held)

    return set_signet


def me(state: GameState, **changes: Any) -> GameState:
    return with_player(state, _seat(state), **changes)


def ab[A: Ability](leader_id: str, cls: type[A]) -> A:
    for candidate in abilities_of(leader_entity(leader_id)):
        if isinstance(candidate, cls):
            return candidate
    raise AssertionError(f"{leader_id} has no {cls.__name__}")


def cards(*refs: str) -> TargetInfo:
    return TargetInfo(tuple(card_entity(ref, 0) for ref in refs))


def run(
    answer_of: Callable[[Profile, Request], Any], p: Profile, *infos: TargetInfo
) -> tuple[float, Any]:
    answer = answer_of(p, Request(infos))
    return answer.value, answer.response


# ---------------------------------------------------------------------------
# Coverage, registration, bases and flags
# ---------------------------------------------------------------------------

#: leader id -> its ability ports in archetype order.
LEADERS: dict[str, list[type[Ability]]] = {
    "archduke_armand_ecaz": [ixl.CoordinationAbility, ixl.ConscriptAbility],
    "ilesa_ecaz": [
        ixl.GuildContactsAbility,
        ixl.OneStepAheadRoundAbility,
        ixl.OneStepAheadTurnAbility,
        ixl.OneStepAheadSendAbility,
    ],
    "prince_rhombur_vernius": [ixl.HeavyLasgunCannonsAbility, IxianTechnologyAbility],
    "princess_yuna_moritani": [
        ixl.FinalDeliveryAbility,
        ixl.SmugglingOperationSolariAbility,
        ixl.SmugglingOperationWaterAbility,
    ],
    "viscount_hundro_moritani": [ixl.CouriersAbility, ixl.IntelligenceAbility],
    "tessia_vernius": [
        ixl.CarefulObeservationSetupAbility,
        ixl.CarefulObservationEmperorAbility,
        ixl.CarefulObservationSpacingGuildAbility,
        ixl.CarefulObservationBeneGesseritAbility,
        ixl.CarefulObservationFremenAbility,
        ixl.CarefulObservationTriggeredAbility,
        ixl.CarefulObservationOppTriggeredAbility,
        ixl.DuplicityAbility,
    ],
}

#: ``ActivatedAbilities.BaseSet.`` (Tessia's ``DuplicityAbility``).
AB = "worm.canis.abilities.ActivatedAbilities.BaseSet."

#: The module's port -> (app namespace prefix, app base port).
PORTED: dict[type[Ability], tuple[str, type[Ability]]] = {
    ixl.CoordinationAbility: (AA, DeferredAbility),
    ixl.ConscriptAbility: (AA, SignetAbility),
    ixl.GuildContactsAbility: (AA, SignetAbility),
    ixl.FinalDeliveryAbility: (AA, SignetAbility),
    ixl.CouriersAbility: (AA, SignetAbility),
    ixl.OneStepAheadRoundAbility: (TA, TriggeredAbility),
    ixl.OneStepAheadTurnAbility: (TA, TriggeredAbility),
    ixl.OneStepAheadSendAbility: (TA, TriggeredAbility),
    ixl.HeavyLasgunCannonsAbility: (TA, TriggeredAbility),
    ixl.IntelligenceAbility: (TA, TriggeredAbility),
    ixl.SmugglingOperationSolariAbility: (PA, TriggeredAbility),
    ixl.SmugglingOperationWaterAbility: (PA, TriggeredAbility),
    ixl.CarefulObservationFactionAbility: (AA, DeferredAbility),
    ixl.CarefulObservationEmperorAbility: (AA, ixl.CarefulObservationFactionAbility),
    ixl.CarefulObservationSpacingGuildAbility: (
        AA,
        ixl.CarefulObservationFactionAbility,
    ),
    ixl.CarefulObservationBeneGesseritAbility: (
        AA,
        ixl.CarefulObservationFactionAbility,
    ),
    ixl.CarefulObservationFremenAbility: (AA, ixl.CarefulObservationFactionAbility),
    ixl.CarefulObeservationSetupAbility: (TA, TriggeredAbility),
    ixl.CarefulObservationTriggeredAbility: (PA, TriggeredAbility),
    ixl.CarefulObservationOppTriggeredAbility: (PA, TriggeredAbility),
    ixl.DuplicityAbility: (AB, SignetAbility),
}


def test_every_ix_leader_ability_resolves_to_a_port() -> None:
    for leader_id, expected in LEADERS.items():
        found = abilities_of(leader_entity(leader_id))
        assert not any(isinstance(a, UnportedAbility) for a in found), leader_id
        assert [type(a) for a in found] == expected, leader_id


@pytest.mark.parametrize(("cls", "where"), list(PORTED.items()))
def test_each_port_is_registered_under_its_app_class(
    cls: type[Ability], where: tuple[str, type[Ability]]
) -> None:
    prefix, base = where
    assert cls.APP_CLASS == prefix + cls.__name__
    assert PORTS[cls.APP_CLASS] is cls
    assert issubclass(cls, base)


def test_the_twenty_one_classes_are_the_module_ports() -> None:
    # The 20 classes the six Leaders list and Tessia's abstract
    # CarefulObservationFactionAbility.
    ports = {
        cls
        for cls in vars(ixl).values()
        if isinstance(cls, type)
        and issubclass(cls, Ability)
        and cls.__module__ == ixl.__name__
        and PORTS.get(cls.APP_CLASS) is cls
    }
    assert ports == set(PORTED)
    assert len(ports) == 21


def test_timings_and_flags() -> None:
    # Coordination's .ctor stores AbilityTiming 2; the Signets inherit
    # SignetAbility's Agent timing; Smuggling Operation (Water)'s .ctor
    # stores 2; the other triggered .ctors store none.
    assert ixl.CoordinationAbility.timing is Timing.REVEAL
    for signet_cls in (
        ixl.ConscriptAbility,
        ixl.GuildContactsAbility,
        ixl.FinalDeliveryAbility,
        ixl.CouriersAbility,
    ):
        assert signet_cls.timing is Timing.AGENT
        assert not signet_cls.always_run_immediately
        assert not signet_cls.contextually_deferred
    assert not ixl.CoordinationAbility.always_run_immediately
    assert ixl.SmugglingOperationWaterAbility.timing is Timing.REVEAL
    for cls in (
        ixl.OneStepAheadRoundAbility,
        ixl.OneStepAheadTurnAbility,
        ixl.OneStepAheadSendAbility,
        ixl.HeavyLasgunCannonsAbility,
        ixl.IntelligenceAbility,
        ixl.SmugglingOperationSolariAbility,
    ):
        assert cls.timing is Timing.NONE
    # get_ShouldExhaust = false (xor eax, eax) where the class overrides it.
    exhausting: tuple[type[TriggeredAbility], ...] = (
        ixl.OneStepAheadSendAbility,
        ixl.SmugglingOperationSolariAbility,
        ixl.SmugglingOperationWaterAbility,
    )
    for trig in exhausting:
        assert vars(trig)["should_exhaust"] is False
    for trig in (
        ixl.OneStepAheadRoundAbility,
        ixl.OneStepAheadTurnAbility,
        ixl.HeavyLasgunCannonsAbility,
        ixl.IntelligenceAbility,
    ):
        assert not hasattr(trig, "should_exhaust")


def test_triggered_abilities_without_an_ai_member() -> None:
    for cls in (
        ixl.OneStepAheadTurnAbility,
        ixl.OneStepAheadSendAbility,
        ixl.HeavyLasgunCannonsAbility,
        ixl.SmugglingOperationSolariAbility,
        ixl.SmugglingOperationWaterAbility,
        ixl.IntelligenceAbility,  # its evaluator is evaluate_intrigue
    ):
        assert cls.evaluate is Ability.evaluate
        assert cls.value_for_player is Ability.value_for_player
    assert ixl.OneStepAheadRoundAbility.value_for_player is Ability.value_for_player
    assert ixl.CoordinationAbility.value_for_player is Ability.value_for_player


def test_every_deferred_port_is_optional(turn_state: GameState) -> None:
    p = make_profile(turn_state)
    for leader_id, cls in (
        ("archduke_armand_ecaz", ixl.CoordinationAbility),
        ("archduke_armand_ecaz", ixl.ConscriptAbility),
        ("ilesa_ecaz", ixl.GuildContactsAbility),
        ("princess_yuna_moritani", ixl.FinalDeliveryAbility),
        ("viscount_hundro_moritani", ixl.CouriersAbility),
    ):
        assert ab(leader_id, cls).selection_mode(p) is SelectionMode.OPTIONAL


# ---------------------------------------------------------------------------
# Archduke Armand Ecaz
# ---------------------------------------------------------------------------


def _agents(state: GameState, *locations: str, swordmaster: bool = False) -> GameState:
    """The deciding seat with Agents on ``locations`` (active count kept)."""

    player = state.players[_seat(state)]
    active = player.agents_available + len(player.agent_locations)
    if swordmaster and not player.swordmaster_acquired:
        active += 1
    return me(
        state,
        agent_locations=tuple(locations),
        agents_available=active - len(locations),
        swordmaster_acquired=swordmaster,
    )


def test_has_two_pct_agents(turn_state: GameState) -> None:
    def two(state: GameState) -> bool:
        return ixl.has_two_pct_agents(make_profile(state))

    # City (Circle) + Spice Trade (Triangle); Landsraad (Pentagon) + City.
    assert two(_agents(turn_state, "arrakeen", "imperial_basin"))
    assert two(_agents(turn_state, "mentat", "carthag"))
    # The Ix board's Landsraad spaces count too.
    assert two(_agents(turn_state, "dreadnought", "smuggling"))
    # One PCT space and a faction space: one is not more than one.
    assert not two(_agents(turn_state, "arrakeen", "conspire"))
    assert not two(_agents(turn_state, "arrakeen"))
    assert not two(_agents(turn_state))
    # Without the Swordmaster attribute its space is not counted.
    assert not two(_agents(turn_state, "imperium_swordmaster", "arrakeen"))
    assert two(
        _agents(turn_state, "imperium_swordmaster", "arrakeen", swordmaster=True)
    )


def test_coordination_cost_and_evaluate(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch, prof: ProfileFactory
) -> None:
    ability = ab("archduke_armand_ecaz", ixl.CoordinationAbility)
    placed = _agents(turn_state, "arrakeen", "imperial_basin")
    # Cost: the Reveal turn (IsInPlayerTurn(2)) and HasTwoPCTAgents.
    monkeypatch.setattr(ixl, "_in_reveal_turn", lambda p: True)
    assert ability.meets_cost(prof(placed))
    assert not ability.meets_cost(prof(_agents(turn_state, "arrakeen")))
    monkeypatch.setattr(ixl, "_in_reveal_turn", lambda p: False)
    assert not ability.meets_cost(prof(placed))
    # Evaluate: GetCardToTrash(targets, 1.0); its value with the card, or an
    # empty target array (trash nothing) without one.
    seen: list[tuple[tuple[str, ...], float]] = []

    def trash(targets: Sequence[Entity], minimum: float) -> tuple[Entity | None, float]:
        seen.append((tuple(t.ref for t in targets), minimum))
        return (targets[-1], 2.75) if targets else (None, minimum)

    p = prof(turn_state, card_to_trash=trash)
    infos = cards("player:0:starter:dagger:1", "player:0:starter:diplomacy:0")
    assert run(ability.evaluate, p, infos) == (
        2.75,
        (("player:0:starter:diplomacy:0",),),
    )
    assert seen == [
        (("player:0:starter:dagger:1", "player:0:starter:diplomacy:0"), 1.0)
    ]
    assert run(ability.evaluate, p) == (1.0, ((),))
    junkless = prof(turn_state, card_to_trash=lambda targets, minimum: (None, 1.0))
    assert run(ability.evaluate, junkless, infos) == (1.0, ((),))


ROW_CHEAP = ("imperium:guild_bankers:0", "imperium:sayyadina:0")  # cost 3 each


def test_conscript_targets(turn_state: GameState) -> None:
    # The fixture's Row: Lady Jessica 7, Guild Bankers 3, Sayyadina 3, CHOAM
    # Directorship 8, Piter de Vries 5; Reserve: Arrakis Liaison 2, The Spice
    # Must Flow 9, Foldspace (no cost: 99, and left out by ArchID).
    targets = ixl.conscript_targets(make_profile(turn_state))
    assert [c.ref for c in targets] == [*ROW_CHEAP, "reserve:arrakis_liaison"]
    empty = with_state(
        turn_state,
        reserve_stacks=tuple((r, 0) for r, _ in turn_state.reserve_stacks),
    )
    assert [c.ref for c in ixl.conscript_targets(make_profile(empty))] == [*ROW_CHEAP]


def test_conscript_value_for_player(
    turn_state: GameState, signet: Callable[[bool], None], prof: ProfileFactory
) -> None:
    ability = ab("archduke_armand_ecaz", ixl.ConscriptAbility)
    # Cost: the plain SignetAbility::Cost.
    signet(True)
    assert ability.meets_cost(prof(turn_state))
    signet(False)
    assert not ability.meets_cost(prof(turn_state))
    # The best AcquireValue (3 + 0.5) and, before the Late arc, 1.75.
    assert ability.value_for_player(prof(turn_state)).sum == pytest.approx(
        3.5 + BEFORE_LATE
    )
    late = prof(turn_state, game_arc=lambda: 2)
    assert ability.value_for_player(late).sum == pytest.approx(3.5)
    early = prof(turn_state, game_arc=lambda: 0)
    assert ability.value_for_player(early).sum == pytest.approx(3.5 + BEFORE_LATE)
    # No target: nothing, not even the arc term.
    bare = with_state(
        turn_state,
        imperium_row=(),
        reserve_stacks=tuple((r, 0) for r, _ in turn_state.reserve_stacks),
    )
    assert ability.value_for_player(prof(bare)).sum == 0.0


def test_conscript_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("archduke_armand_ecaz", ixl.ConscriptAbility)
    infos = cards(
        "reserve:arrakis_liaison",  # 2
        "imperium:piter_de_vries_card:0",  # 5: skipped (cmp 3; jg)
        "imperium:guild_bankers:0",  # 3
        "imperium:sayyadina:0",  # 3: equal, not better
    )
    # AcquireValue + 1.75 before the Late arc; [card, Int(0)].
    value, response = run(ability.evaluate, prof(turn_state), infos)
    assert value == pytest.approx(3.5 + BEFORE_LATE)
    assert response == (("imperium:guild_bankers:0",), (0,))
    late = prof(turn_state, game_arc=lambda: 2)
    value, response = run(ability.evaluate, late, infos)
    assert value == pytest.approx(3.5)
    assert response == (("imperium:guild_bankers:0",), (0,))
    # Evaluate reads PersuasionCost with default 0: a cost-less card passes.
    value, response = run(ability.evaluate, late, cards("reserve:foldspace_card"))
    assert value == pytest.approx(0.5)
    assert response == (("reserve:foldspace_card",), (0,))
    assert run(ability.evaluate, late, cards("imperium:piter_de_vries_card:0")) == (
        0.0,
        None,
    )


# ---------------------------------------------------------------------------
# Ilesa Ecaz
# ---------------------------------------------------------------------------


def test_guild_contacts_cost(
    turn_state: GameState, signet: Callable[[bool], None], prof: ProfileFactory
) -> None:
    ability = ab("ilesa_ecaz", ixl.GuildContactsAbility)
    rich = me(turn_state, resources=Resources(solari=1))
    signet(True)
    assert ability.meets_cost(prof(rich))
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(solari=0))))
    no_fold = with_state(
        rich,
        reserve_stacks=tuple(
            (r, 0 if r == "foldspace_card" else n) for r, n in rich.reserve_stacks
        ),
    )
    assert not ability.meets_cost(prof(no_fold))
    signet(False)
    assert not ability.meets_cost(prof(rich))


def test_guild_contacts_value_and_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("ilesa_ecaz", ixl.GuildContactsAbility)
    # GetSolariValue(-1) + FoldspaceValue, whatever the Solari held.
    broke = me(turn_state, resources=Resources(solari=0))
    assert ability.value_for_player(prof(broke)).sum == pytest.approx(-0.25 + 3.25)
    seen: list[tuple[str, Attr, int]] = []

    def blocked(space: Entity, attr: Attr, amount: int) -> bool:
        seen.append((space.ref, attr, amount))
        return False

    arrakeen = space_entity("arrakeen", BOARD)
    p = prof(turn_state, can_agent_ability_be_played_with_space=blocked)
    assert ability.value_for_player(p, (arrakeen,)).sum == 0.0
    assert seen == [("arrakeen", Attr.SOLARI, 1)]
    assert ability.value_for_player(prof(turn_state), (arrakeen,)).sum == (
        pytest.approx(3.0)
    )
    # Evaluate: 100.0 with IntTargetResponse(0) before the Late arc and the
    # climax, else nothing.
    assert run(ability.evaluate, prof(turn_state)) == (100.0, ((0,),))
    assert run(ability.evaluate, prof(turn_state, game_arc=lambda: 0)) == (
        100.0,
        ((0,),),
    )
    assert run(ability.evaluate, prof(turn_state, game_arc=lambda: 2)) == (0.0, None)
    assert run(ability.evaluate, prof(turn_state, is_climax=lambda: True)) == (
        0.0,
        None,
    )


DAGGER = "player:0:starter:dagger:1"  # one icon (Pentagon)
DUNE = "player:0:starter:dune_the_desert_planet:0"  # one icon (Triangle)
RECON = "player:0:starter:reconnaissance:0"  # one icon (Circle)
DIPLOMACY = "player:0:starter:diplomacy:0"  # four icons
LIAISON = "reserve:arrakis_liaison"  # two icons
FOLDSPACE = "reserve:foldspace_card"  # seven icons


def test_agent_box_value(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make_profile(turn_state)
    monkeypatch.setattr(
        generic.AgentAbility,
        "value_for_player",
        lambda self, p, with_entities=(): Summer(2.5 if with_entities == () else -9.0),
    )
    assert ixl._agent_box_value(p, card_entity(DAGGER, 0)) == 2.5
    # No AgentAbility (an Intrigue card's abilities): 0.0.
    assert ixl._agent_box_value(p, intrigue_entity("intrigue:cull:0", 0)) == 0.0


def test_one_step_ahead_round_evaluate(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = ab("ilesa_ecaz", ixl.OneStepAheadRoundAbility)
    values: dict[str, float] = {}
    monkeypatch.setattr(ixl, "_agent_box_value", lambda p, card: values[card.ref])
    calls: list[tuple[str, ...]] = []
    best: list[str | None] = [None]

    def best_option(p: Profile, hand: Sequence[Entity] | None = None) -> Any:
        assert hand is not None
        calls.append(tuple(c.ref for c in hand))
        pick = None if best[0] is None else card_entity(best[0], 0)
        return (pick, None, 0.0 if pick is None else 2.0)

    monkeypatch.setattr(oi, "best_option", best_option)
    p = make_profile(turn_state)

    def pick(**hand: float) -> tuple[float, Any]:
        values.clear()
        refs = {"dagger": DAGGER, "dune": DUNE, "recon": RECON, "dip": DIPLOMACY}
        refs |= {"liaison": LIAISON, "fold": FOLDSPACE}
        values.update({refs[k]: v for k, v in hand.items()})
        return run(ability.evaluate, p, cards(*(refs[k] for k in hand)))

    # The first one-icon card among the three best Agent boxes, at 100.0.
    assert pick(dagger=3.0, dip=5.0, recon=2.0, dune=4.0) == (100.0, ((DUNE,),))
    assert calls == []
    # Equal values keep the hand order (stable sort).
    assert pick(dip=1.0, liaison=1.0, dagger=1.0) == (100.0, ((DAGGER,),))
    # No one-icon card in the top three: GetBestOption's card leaves the
    # sorted list and its first card is set aside.
    best[0] = DIPLOMACY
    assert pick(dagger=1.0, dip=5.0, liaison=4.0, fold=3.0) == (100.0, ((LIAISON,),))
    assert calls == [(DIPLOMACY, LIAISON, FOLDSPACE, DAGGER)]
    best[0] = None
    assert pick(dagger=1.0, dip=5.0, liaison=4.0, fold=3.0) == (
        100.0,
        ((DIPLOMACY,),),
    )
    # A best card outside the list removes nothing.
    best[0] = RECON
    assert pick(dagger=1.0, dip=5.0, liaison=4.0, fold=3.0) == (
        100.0,
        ((DIPLOMACY,),),
    )
    # NaN sorts last (Comparer<double>.Default): the one-icon dagger is 4th.
    best[0] = None
    assert pick(dagger=math.nan, liaison=1.0, dip=2.0, fold=0.5) == (
        100.0,
        ((DIPLOMACY,),),
    )
    # The only card removed: nothing stored.
    best[0] = DIPLOMACY
    assert pick(dip=1.0) == (0.0, None)
    best[0] = None
    assert pick() == (0.0, None)


# ---------------------------------------------------------------------------
# "Princess" Yuna Moritani
# ---------------------------------------------------------------------------


def test_final_delivery_cost(
    turn_state: GameState, signet: Callable[[bool], None], prof: ProfileFactory
) -> None:
    ability = ab("princess_yuna_moritani", ixl.FinalDeliveryAbility)
    signet(True)
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(solari=7))))
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(solari=6))))
    signet(False)
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(solari=7))))


def test_final_delivery_value_for_player(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab("princess_yuna_moritani", ixl.FinalDeliveryAbility)
    # -7 Solari + 1 spice + 1 troop + G(None, +1), whatever the Solari held.
    expected = -7 * 0.25 + 0.5 + 0.9 + 2.5
    broke = me(turn_state, resources=Resources(solari=0))
    assert ability.value_for_player(prof(broke)).sum == pytest.approx(expected)
    seen: list[tuple[str, Attr, int]] = []

    def blocked(space: Entity, attr: Attr, amount: int) -> bool:
        seen.append((space.ref, attr, amount))
        return False

    space = space_entity("imperium_swordmaster", BOARD)
    p = prof(turn_state, can_agent_ability_be_played_with_space=blocked)
    assert ability.value_for_player(p, (space,)).sum == 0.0
    assert seen == [("imperium_swordmaster", Attr.SOLARI, 7)]


def test_final_delivery_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab("princess_yuna_moritani", ixl.FinalDeliveryAbility)
    infos = TargetInfo(tuple(track_entity(f) for f in ("emperor", "fremen")))
    # Only the track's G(track, +1).Sum is stored: the built -7 Solari /
    # spice / troop summer is never read.
    keen = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(
            {"fremen": 3.0}.get(f, 2.0) * n
        ),
        solari_value=lambda n: 100.0 * n,
    )
    assert run(ability.evaluate, keen, infos) == (3.0, (("fremen",),))
    # No threshold: a negative best still stores (the first sticks).
    sour = prof(
        turn_state,
        gain_influence_value=lambda f, n, rank=-1, alliance=False: Summer(-1.0),
    )
    assert run(ability.evaluate, sour, infos) == (-1.0, (("emperor",),))
    assert run(ability.evaluate, keen) == (0.0, None)


# ---------------------------------------------------------------------------
# Viscount Hundro Moritani
# ---------------------------------------------------------------------------


def test_couriers(
    turn_state: GameState, signet: Callable[[bool], None], prof: ProfileFactory
) -> None:
    ability = ab("viscount_hundro_moritani", ixl.CouriersAbility)
    signet(True)
    assert ability.meets_cost(prof(me(turn_state, resources=Resources(spice=1))))
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(spice=0))))
    signet(False)
    assert not ability.meets_cost(prof(me(turn_state, resources=Resources(spice=1))))
    # V: -GetSpiceValue(1) (not GetSpiceValue(-1)) + FreighterValue.
    bent = prof(turn_state, spice_value=lambda n: 0.5 * n + 0.1)
    assert ability.value_for_player(bent).sum == pytest.approx(-(0.5 + 0.1) + 4.2)
    seen: list[tuple[str, Attr, int]] = []

    def blocked(space: Entity, attr: Attr, amount: int) -> bool:
        seen.append((space.ref, attr, amount))
        return False

    space = space_entity("smuggling", BOARD)
    p = prof(turn_state, can_agent_ability_be_played_with_space=blocked)
    assert ability.value_for_player(p, (space,)).sum == 0.0
    assert seen == [("smuggling", Attr.SPICE, 1)]
    # E: GetFreighterSelections(-1).Item1 at FreighterValue.
    asked: list[int] = []

    def selections(space: int = -1) -> tuple[int, int, str]:
        asked.append(space)
        return (1, 0, "Level 3")

    assert run(ability.evaluate, prof(turn_state, freighter_selections=selections)) == (
        4.2,
        ((1,),),
    )
    assert asked == [-1]
    advance = prof(turn_state, freighter_selections=lambda space=-1: (0, 1, "x"))
    assert run(ability.evaluate, advance) == (4.2, ((0,),))


def test_intelligence_keeps_the_highest_rating(turn_state: GameState) -> None:
    ability = ab("viscount_hundro_moritani", ixl.IntelligenceAbility)
    p = make_profile(turn_state)

    def keep(*names: str) -> tuple[float, Any]:
        info = TargetInfo(tuple(intrigue_entity(f"intrigue:{n}:0", 0) for n in names))
        return run(ability.evaluate_intrigue, p, info)

    # Ratings: Blackmail 1, Cull 3, Diversion 4, Second Wave 4.
    assert keep("blackmail", "diversion", "second_wave") == (
        4.0,
        (("intrigue:diversion:0",),),
    )
    assert keep("cull", "blackmail") == (3.0, (("intrigue:cull:0",),))
    assert keep("blackmail") == (1.0, (("intrigue:blackmail:0",),))
    assert keep() == (0.0, None)


# ---------------------------------------------------------------------------
# Tessia Vernius
# ---------------------------------------------------------------------------

TESSIA = "tessia_vernius"
FACTION_CLASSES: dict[str, type[ixl.CarefulObservationFactionAbility]] = {
    "emperor": ixl.CarefulObservationEmperorAbility,
    "spacing_guild": ixl.CarefulObservationSpacingGuildAbility,
    "bene_gesserit": ixl.CarefulObservationBeneGesseritAbility,
    "fremen": ixl.CarefulObservationFremenAbility,
}


def tessia(state: GameState, *tokens: str, **changes: Any) -> GameState:
    """The deciding seat as Tessia Vernius with Snooper tokens on
    ``tokens``."""

    return me(state, leader_id=TESSIA, snooper_faction_ids=tokens, **changes)


def snooper_row(state: GameState, faction: str) -> GameState:
    """Reward (1) of ``faction``'s token waiting on her own turn frame."""

    queued = turn_rows.queue(
        state, _seat(state), (turn_rows.SNOOPER_DISCARD, f"src:{faction}", faction)
    )
    assert queued is not None
    return queued


def snooper_window(
    state: GameState, faction: str, owner: int | None = None
) -> GameState:
    """Reward (1) of ``faction``'s token in the ``OPTIONAL_DISCARD`` window."""

    seat = _seat(state) if owner is None else owner
    return state.push_decision(
        DecisionFrame(
            kind=FrameKind.OPTIONAL_DISCARD,
            frame_id=f"src:{faction}:optional_discard",
            decision=PlayerDecision(owner=seat, prompt="Snooper reward"),
            context=(("faction", faction), ("player", seat), ("source", "src")),
        )
    )


def test_tessia_timings_and_flags() -> None:
    # The faction abilities' .ctor stores no AbilityTiming; Duplicity
    # inherits SignetAbility's Agent timing; the own-turn and opponent-turn
    # triggers store 2; the setup trigger stores none.
    faction_classes: list[type[ixl.CarefulObservationFactionAbility]] = [
        ixl.CarefulObservationFactionAbility,
        *FACTION_CLASSES.values(),
    ]
    for cls in faction_classes:
        assert cls.timing is Timing.NONE
        assert not cls.always_run_immediately
        assert not cls.contextually_deferred
        assert cls.value_for_player is Ability.value_for_player
    assert ixl.DuplicityAbility.timing is Timing.AGENT
    assert not ixl.DuplicityAbility.always_run_immediately
    assert not ixl.DuplicityAbility.contextually_deferred
    assert ixl.CarefulObeservationSetupAbility.timing is Timing.NONE
    assert not hasattr(ixl.CarefulObeservationSetupAbility, "should_exhaust")
    for trig in (
        ixl.CarefulObservationTriggeredAbility,
        ixl.CarefulObservationOppTriggeredAbility,
    ):
        assert trig.timing is Timing.REVEAL
        assert vars(trig)["should_exhaust"] is False
    for bare in (
        ixl.CarefulObeservationSetupAbility,
        ixl.CarefulObservationTriggeredAbility,
        ixl.CarefulObservationOppTriggeredAbility,
    ):
        assert bare.evaluate is Ability.evaluate
        assert bare.value_for_player is Ability.value_for_player


def test_each_faction_class_names_its_snooper_track() -> None:
    # get_SnooperFaction: 1-4 in the subclasses, Factions.None in the base.
    assert ixl.CarefulObservationFactionAbility.snooper_faction == "none"
    for faction, cls in FACTION_CLASSES.items():
        assert cls.snooper_faction == faction
        assert ab(TESSIA, cls).snooper_faction == faction
        # Each subclass overrides only get_SnooperFaction (and its .ctors).
        own = {name for name in vars(cls) if not name.startswith("__")}
        assert own == {"snooper_faction", "APP_CLASS"}


def test_snooper_discards_waiting_and_factions_used(turn_state: GameState) -> None:
    def waiting(state: GameState, seat: int | None = None) -> tuple[str, ...]:
        return ixl.snooper_discards_waiting(make_profile(state, seat))

    def used(state: GameState) -> tuple[str, ...]:
        return ixl.snooper_factions_used(make_profile(state))

    three = tessia(turn_state, "spacing_guild", "bene_gesserit", "fremen")
    # Nothing waits: every reached token's reward has been paid.
    assert waiting(three) == ()
    assert used(three) == ("emperor",)
    assert used(tessia(turn_state, "fremen")) == (
        "emperor",
        "spacing_guild",
        "bene_gesserit",
    )
    assert used(tessia(turn_state)) == (
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    )
    assert (
        used(tessia(turn_state, "emperor", "spacing_guild", "bene_gesserit", "fremen"))
        == ()
    )
    # Reward (1) waiting on her turn frame or in her own window: the app's
    # first run, before which SnooperFactionsUsed is empty.
    row = snooper_row(three, "emperor")
    assert waiting(row) == ("emperor",)
    assert used(row) == ()
    two = tessia(turn_state, "bene_gesserit", "fremen")
    assert used(snooper_row(two, "emperor")) == ()
    window = snooper_window(three, "emperor")
    assert waiting(window) == ("emperor",)
    assert used(window) == ()
    # Another seat's window is not hers.
    seat = _seat(turn_state)
    other = (seat + 1) % len(turn_state.players)
    assert waiting(snooper_window(three, "emperor", owner=other), seat) == ()
    # A leader without the list (the app's null) has used nothing.
    assert used(me(turn_state, snooper_faction_ids=("fremen",))) == ()


def test_careful_observation_selection_mode_and_run_immediately(
    turn_state: GameState,
) -> None:
    ability = ab(TESSIA, ixl.CarefulObservationFremenAbility)
    all_four = ("emperor", "spacing_guild", "bene_gesserit", "fremen")

    def mode(state: GameState) -> SelectionMode:
        return ability.selection_mode(make_profile(state))

    # SnooperFactions.Count >= 3 (jge) -> Optional; fewer -> Explicit.
    assert mode(tessia(turn_state, *all_four)) is SelectionMode.OPTIONAL
    assert mode(tessia(turn_state, *all_four[:3])) is SelectionMode.OPTIONAL
    assert mode(tessia(turn_state, *all_four[:2])) is SelectionMode.EXPLICIT
    assert mode(tessia(turn_state, "fremen")) is SelectionMode.EXPLICIT
    assert mode(tessia(turn_state)) is SelectionMode.EXPLICIT
    # A leader without the list: Optional.
    assert mode(me(turn_state, snooper_faction_ids=())) is SelectionMode.OPTIONAL

    def immediately(state: GameState) -> bool:
        return ability.can_run_immediately(make_profile(state))

    # HandCount == 0 and SnooperFactions.Count == 3 (sete).
    assert immediately(tessia(turn_state, *all_four[:3], hand=()))
    assert not immediately(tessia(turn_state, *all_four[:3]))
    assert not immediately(tessia(turn_state, *all_four, hand=()))
    assert not immediately(tessia(turn_state, *all_four[:2], hand=()))
    assert not immediately(me(turn_state, snooper_faction_ids=all_four[:3], hand=()))


def test_careful_observation_cost(turn_state: GameState) -> None:
    three = tessia(turn_state, "spacing_guild", "bene_gesserit", "fremen")
    emperor = ab(TESSIA, ixl.CarefulObservationEmperorAbility)
    fremen = ab(TESSIA, ixl.CarefulObservationFremenAbility)
    # HasCustomAbility(this): the track's reward (1) waits; then the track is
    # not in SnooperFactionsUsed.
    for state in (snooper_row(three, "emperor"), snooper_window(three, "emperor")):
        p = make_profile(state)
        assert emperor.has_custom_ability(p)
        assert emperor.meets_cost(p)
        assert not fremen.meets_cost(p)
    assert not emperor.meets_cost(make_profile(three))


def test_careful_observation_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab(TESSIA, ixl.CarefulObservationEmperorAbility)
    first = snooper_row(
        tessia(turn_state, "spacing_guild", "bene_gesserit", "fremen"), "emperor"
    )
    hand = (DAGGER, DIPLOMACY, RECON)
    infos = cards(*hand)
    seen: list[tuple[tuple[str, ...], bool]] = []

    def order(targets: Sequence[Entity], sg_bonus: bool) -> list[Entity]:
        seen.append((tuple(t.ref for t in targets), sg_bonus))
        return list(reversed(targets))

    def at(discard: float, spice: float, **more: Callable[..., Any]) -> Profile:
        return prof(
            first,
            discard_value=lambda: discard,
            spice_value=lambda n: spice * n,
            discard_order=more.pop("discard_order", order),
            **more,
        )

    # The first reward: GetDiscardOrder(P, targets, false)'s first card at
    # 1.0 whatever the summer, when DiscardValue + GetSpiceValue(1) > 0.
    assert run(ability.evaluate, at(-0.5, 2.0), infos) == (1.0, ((RECON,),))
    assert seen == [(hand, False)]
    assert run(ability.evaluate, at(30.0, 0.0), infos) == (1.0, ((RECON,),))
    # 0.0 >= Sum (jae): an empty target array, still at 1.0.
    assert run(ability.evaluate, at(-2.0, 2.0), infos) == (1.0, ((),))
    assert run(ability.evaluate, at(-3.0, 2.0), infos) == (1.0, ((),))
    # ucomisd with a NaN sum: unordered, jae not taken -> the card.
    assert run(ability.evaluate, at(math.nan, 2.0), infos) == (1.0, ((RECON,),))
    # No card in the order: the empty target array.
    empty = at(-0.5, 2.0, discard_order=lambda targets, sg: [])
    assert run(ability.evaluate, empty, infos) == (1.0, ((),))
    # No target (no information or an empty one): (1.0, null).
    assert run(ability.evaluate, at(-0.5, 2.0)) == (1.0, ())
    assert run(ability.evaluate, at(-0.5, 2.0), TargetInfo()) == (1.0, ())
    # Not the first reward (SnooperFactionsUsed not empty): (1.0, null), the
    # summer and the targets unread.
    later = tessia(turn_state, "bene_gesserit", "fremen")
    unread = prof(
        later,
        discard_value=lambda: pytest.fail("DiscardValue read"),
        discard_order=lambda targets, sg: pytest.fail("GetDiscardOrder read"),
    )
    assert run(ability.evaluate, unread, infos) == (1.0, ())


def test_duplicity_cost(
    turn_state: GameState, signet: Callable[[bool], None], prof: ProfileFactory
) -> None:
    ability = ab(TESSIA, ixl.DuplicityAbility)
    assert ability.selection_mode(make_profile(turn_state)) is SelectionMode.OPTIONAL
    fremen_one = Influence(fremen=1)
    held = tessia(turn_state, "emperor", influence=fremen_one)
    signet(True)
    assert ability.meets_cost(prof(held))
    for faction in ("emperor", "spacing_guild", "bene_gesserit", "fremen"):
        state = tessia(turn_state, "fremen", influence=Influence(**{faction: 1}))
        assert ability.meets_cost(prof(state)), faction
    # No Influence anywhere (AtLeast(F, 1) for none of the four).
    assert not ability.meets_cost(prof(tessia(turn_state, "emperor")))
    # No Snooper token left (Count > 0, setg), or no list at all.
    assert not ability.meets_cost(prof(tessia(turn_state, influence=fremen_one)))
    no_list = me(turn_state, snooper_faction_ids=("emperor",), influence=fremen_one)
    assert not ability.meets_cost(prof(no_list))
    signet(False)
    assert not ability.meets_cost(prof(held))


def test_duplicity_value_for_player(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ab(TESSIA, ixl.DuplicityAbility)
    asked: list[tuple[int, int, Any, Any]] = []
    value = [2.5]

    def exchange(
        lose: int, gain: int, lose_f: Any = None, gain_f: Any = None
    ) -> tuple[str | None, str | None, float]:
        asked.append((lose, gain, lose_f, gain_f))
        return ("fremen", "emperor", value[0])

    def v(*tokens: str) -> Summer:
        p = prof(tessia(turn_state, *tokens), best_influence_exchange=exchange)
        return ability.value_for_player(p, (space_entity("arrakeen", BOARD),))

    # GetBestInfluenceExchange(-1, 1, false, null, SnooperFactions).
    assert v("spacing_guild", "fremen").sum == 2.5
    assert asked == [(-1, 1, None, ["spacing_guild", "fremen"])]
    # Math.Max(0.0, value): a negative best is 0, a NaN stays.
    value[0] = -1.0
    assert v("emperor").sum == 0.0
    value[0] = math.nan
    assert math.isnan(v("emperor").sum)
    # Only the Spacing Guild token, or none: nothing, and no exchange asked.
    asked.clear()
    assert v("spacing_guild").sum == 0.0
    assert v().sum == 0.0
    assert asked == []
    no_list = me(turn_state, snooper_faction_ids=("emperor",))
    assert (
        ability.value_for_player(prof(no_list, best_influence_exchange=exchange)).sum
        == 0.0
    )
    assert asked == []


def test_duplicity_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ab(TESSIA, ixl.DuplicityAbility)
    asked: list[tuple[int, int, Any, Any]] = []
    best: list[tuple[str | None, str | None, float]] = [("fremen", "emperor", 1.75)]

    def exchange(
        lose: int, gain: int, lose_f: Any = None, gain_f: Any = None
    ) -> tuple[str | None, str | None, float]:
        asked.append((lose, gain, lose_f, gain_f))
        return best[0]

    p = prof(turn_state, best_influence_exchange=exchange)

    def tracks(*factions: str) -> TargetInfo:
        return TargetInfo(tuple(track_entity(f) for f in factions))

    lose = tracks("emperor", "fremen")
    gain = tracks("emperor", "bene_gesserit")
    # GetBestInfluenceExchange(-1, 1, true, loseFactions, gainFactions); the
    # answer [EntityList([lose]), EntityList([gain])] at its value.
    assert run(ability.evaluate, p, lose, gain) == (1.75, (("fremen",), ("emperor",)))
    assert asked == [(-1, 1, ["emperor", "fremen"], ["emperor", "bene_gesserit"])]
    # One Faction lost and gained.
    best[0] = ("emperor", "emperor", 0.5)
    assert run(ability.evaluate, p, lose, gain) == (0.5, (("emperor",), ("emperor",)))
    # No exchange above 0 (Factions.None matches no track), or a Faction the
    # tracks do not hold: nothing.
    best[0] = (None, None, 0.0)
    assert run(ability.evaluate, p, lose, gain) == (0.0, None)
    best[0] = ("spacing_guild", "emperor", 3.0)
    assert run(ability.evaluate, p, lose, gain) == (0.0, None)
    best[0] = ("fremen", "fremen", 3.0)
    assert run(ability.evaluate, p, lose, gain) == (0.0, None)
    # The lose tracks exactly one Spacing Guild track: nothing, nothing asked.
    asked.clear()
    best[0] = ("spacing_guild", "emperor", 3.0)
    assert run(ability.evaluate, p, tracks("spacing_guild"), gain) == (0.0, None)
    # Missing informations: nothing.
    assert run(ability.evaluate, p) == (0.0, None)
    assert run(ability.evaluate, p, lose) == (0.0, None)
    assert asked == []
    # Two lose tracks with the Spacing Guild: asked as usual.
    assert run(ability.evaluate, p, tracks("spacing_guild", "fremen"), gain) == (
        3.0,
        (("spacing_guild",), ("emperor",)),
    )
