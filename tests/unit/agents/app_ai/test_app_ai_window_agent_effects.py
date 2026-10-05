"""The ``agent_effects`` window: the app's Agent-turn order and its prompt.

Each test reaches a real Agent turn (the first turn of a game, with the
deciding seat's hand, resources and board pieces adjusted, then a real
``agent_turn``), builds the ``DecisionRun`` the agent would build, and
asserts the exact action the window answers. Profile values a branch depends
on are pinned on the fresh ``Profile`` instance. ``intrigue_play_sources``
(another window's, possibly unfinished) is stubbed.
"""

import random
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import agent as agent_module
from dune_imperium.agents.app_ai.agent import AppAIAgent
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import agent_effects as ae
from dune_imperium.agents.app_ai.windows.common import Source, Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.evaluation.tournament import _rotated_leader_ids
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

type Patches = Mapping[str, object]


@pytest.fixture(autouse=True)
def no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    """``intrigue_play_sources`` belongs to the intrigue window: stub it."""

    monkeypatch.setattr(ae, "intrigue_play_sources", lambda run, plays, combat: [])


# ---------------------------------------------------------------------------
# Real states
# ---------------------------------------------------------------------------


def _first_turn(*, choam: bool = True) -> tuple[GameState, int]:
    state = first_decision("turn", choam=choam, seed=1)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return state, decision.owner


def _take(state: GameState, seat: int, card: str) -> tuple[GameState, str]:
    """Move one copy of ``card`` into ``seat``'s hand (from its own piles or
    the Imperium deck/Row) and return its instance id."""

    me = state.players[seat]
    for zone in ("hand", "deck", "discard_pile"):
        for ref in getattr(me, zone):
            if f":{card}:" in ref:
                if zone == "hand":
                    return state, ref
                rest = tuple(r for r in getattr(me, zone) if r != ref)
                return with_player(
                    state, seat, **{zone: rest}, hand=(ref, *me.hand)
                ), ref
    for zone in ("imperium_deck", "imperium_row"):
        for ref in getattr(state, zone):
            if ref.startswith(f"imperium:{card}:"):
                rest = tuple(r for r in getattr(state, zone) if r != ref)
                state = with_state(state, **{zone: rest})
                hand = (ref, *state.players[seat].hand)
                return with_player(state, seat, hand=hand), ref
    raise KeyError(card)


def _settle(state: GameState) -> GameState:
    chance = ChanceResolver(seed=1)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _apply(state: GameState, seat: int, action: DomainAction) -> GameState:
    legal = ENGINE.legal_actions(state, seat)
    return _settle(ENGINE.apply(state, action, legal_actions=legal).state)


def _place(
    card: str,
    space: str,
    *,
    choam: bool = True,
    extra: tuple[str, ...] = (),
    state_changes: Mapping[str, object] | None = None,
    **changes: object,
) -> tuple[GameState, int, str]:
    """The first turn's seat sends ``card`` to ``space``; ``changes`` adjust
    the seat before placement, ``extra`` cards join its hand."""

    state, seat = _first_turn(choam=choam)
    for other in extra:
        state, _ = _take(state, seat, other)
    state, ref = _take(state, seat, card)
    if changes:
        state = with_player(state, seat, **changes)
    if state_changes:
        state = with_state(state, **state_changes)
    legal = ENGINE.legal_actions(state, seat)
    for action in legal:
        args = dict(action.arguments)
        if (
            action.action_id == "agent_turn"
            and args.get("card_id") == ref
            and args.get("space_id") == space
        ):
            state = ENGINE.apply(state, action, legal_actions=legal).state
            return _settle(state), seat, ref
    raise AssertionError(f"{card} cannot go to {space}")


def _run(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> DecisionRun:
    profile = make_profile(state, seat)
    for name, value in (patches or {}).items():
        setattr(profile, name, value)
    legal = ENGINE.legal_actions(state, seat)
    return DecisionRun(
        profile.ctx, profile, legal, random.Random(0), memory or Memory()
    )


def _answer(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> DomainAction | None:
    return ae.agent_effects_window(_run(state, seat, patches, memory))


def _must(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> DomainAction:
    action = _answer(state, seat, patches, memory)
    assert action is not None
    return action


def _a(seat: int, action_id: str, **arguments: str | int) -> DomainAction:
    """The action ``action_id(arguments)`` of ``seat``."""

    return DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(arguments.items())
    )


def _drive(
    state: GameState, seat: int, patches: Patches | None = None, limit: int = 30
) -> tuple[list[DomainAction], GameState]:
    """Answer the seat's Agent turn to its end with the window."""

    memory = Memory()
    taken: list[DomainAction] = []
    for _ in range(limit):
        decision = ENGINE.current_decision(state)
        if (
            not isinstance(decision, PlayerDecision)
            or decision.owner != seat
            or state.decision_stack[-1].kind != "agent_effects"
        ):
            break
        legal = ENGINE.legal_actions(state, seat)
        action = legal[0] if len(legal) == 1 else _answer(state, seat, patches, memory)
        assert action is not None and action in legal
        taken.append(action)
        state = _apply(state, seat, action)
        if action.action_id == "finish_agent_turn":
            break
    return taken, state


def _const(value: float) -> Callable[..., float]:
    return lambda *args, **kwargs: value


def _summer(value: float) -> Callable[..., Summer]:
    def make(*args: object, **kwargs: object) -> Summer:
        s = Summer()
        s.add("pinned", value)
        return s

    return make


def _ids(actions: list[DomainAction]) -> list[str]:
    return [a.action_id + "".join(f":{v}" for _, v in a.arguments) for a in actions]


def _sources(
    state: GameState, seat: int, patches: Patches | None = None
) -> Iterator[Source]:
    """The window's sources for this decision (for stage/value checks)."""

    turn = ae._turn(_run(state, seat, patches))
    for build in (
        ae._board_icons,
        ae._faction_influence_source,
        ae._card_box,
        ae._card_choices,
        ae._leader_choices,
        ae._track_spy,
        ae._contracts,
        ae._deploy,
    ):
        build(turn)
    yield from turn.sources


NO_DEPLOY: Patches = {"units_to_deploy": lambda garrison, maximum: 0}


# ---------------------------------------------------------------------------
# The fixed order: 400 space, 500 agent box, 600 immediates, then the prompt
# ---------------------------------------------------------------------------


def test_space_gains_then_influence_then_intrigue() -> None:
    """Sardaukar: the troops (400), then the space influence before the
    Intrigue card (600, ``OrderBy(WillClearUndo)``: the draw clears undo)."""

    state, seat, _ = _place(
        "diplomacy", "sardaukar", resources=Resources(solari=0, spice=4, water=1)
    )
    taken, _ = _drive(state, seat, NO_DEPLOY)
    assert _ids(taken) == [
        "resolve_board_effect:troops",
        "resolve_faction_influence",
        "resolve_board_effect:intrigue",
        "finish_agent_turn",
    ]


def test_agent_box_between_space_and_immediates() -> None:
    """Paracompass at Arrakeen: troops (400), its ``AgentSolari`` box (500),
    the space's draw (600, Arrakeen DeferValue 1 < 3), then the prompt."""

    state, seat, _ = _place("paracompass", "arrakeen")
    taken, _ = _drive(state, seat, NO_DEPLOY)
    assert _ids(taken) == [
        "resolve_board_effect:troops",
        "resolve_agent_card_effect",
        "resolve_board_effect:cards",
        "finish_agent_turn",
    ]


def test_threshold_moves_the_space_draw_into_the_prompt() -> None:
    """The Signet Ring (DeferValue 3) reaches the threshold: Arrakeen's draw
    waits in the prompt as an Explicit key at its DeferValue (1), while
    Gurney's Warmaster still runs at 600; the draw (1.0) beats the deploy
    (0.5)."""

    state, seat, _ = _place(
        "signet_ring",
        "arrakeen",
        leader_id="gurney_halleck",
        leader_face_id="gurney_halleck",
    )
    deploy_two: Patches = {"units_to_deploy": lambda garrison, maximum: 2}
    stages = {s.label: s for s in _sources(state, seat, deploy_two)}
    assert stages["board cards"].stage is Stage.PROMPT
    assert stages["board cards"].extra["explicit"] is True
    assert stages["signet gurney_halleck"].stage is Stage.IMMEDIATE
    taken, _ = _drive(state, seat, deploy_two)
    assert _ids(taken) == [
        "resolve_board_effect:troops",
        "resolve_agent_card_effect",
        "resolve_board_effect:cards",
        "deploy_troops:2",
        "finish_agent_turn",
    ]


def test_threshold_counts_intrigue_cards_in_hand() -> None:
    """``DeferredThresholdReached`` sums the hand's intrigue DeferValues: two
    DeferValue-1 intrigues and Arrakeen's 1 reach 3."""

    state, seat, _ = _place("reconnaissance", "arrakeen")
    labels = {s.label: s.stage for s in _sources(state, seat)}
    assert labels["board cards"] is Stage.IMMEDIATE
    held = with_player(
        state,
        seat,
        intrigue_cards=("intrigue:buy_access:0", "intrigue:impress:0"),
    )
    labels = {s.label: s.stage for s in _sources(held, seat)}
    assert labels["board cards"] is Stage.PROMPT


def test_deploy_once_with_units_to_deploy_count() -> None:
    """``DeployUnitsAbility``: 0.5 with ``GetUnitsToDeploy``'s count, used once
    (the rest of the room is never offered again)."""

    state, seat, _ = _place("paracompass", "arrakeen")
    deploy_one: Patches = {"units_to_deploy": lambda garrison, maximum: 1}
    taken, after = _drive(state, seat, deploy_one)
    assert _ids(taken)[-2:] == ["deploy_troops:1", "finish_agent_turn"]
    assert after.players[seat].troops_conflict == 1


def test_deploy_request_offers_the_garrison_and_the_room() -> None:
    state, seat, _ = _place("paracompass", "arrakeen")
    seen: list[tuple[int, int]] = []

    def units(garrison: int, maximum: int) -> int:
        seen.append((garrison, maximum))
        return 9

    for _ in range(3):  # troops, box, cards
        state = _apply(state, seat, _must(state, seat, NO_DEPLOY))
    assert _answer(state, seat, {"units_to_deploy": units}) == _a(
        seat, "deploy_troops", count=3
    )
    # 4 garrison troops (3 + Arrakeen's recruit), room 2 + 1 recruited.
    assert seen == [(4, 3)]


def test_sardaukar_coordination_deploys_the_recruited_troops_once() -> None:
    """Sardaukar has no ``DeployUnitsAbility``: the deploy key is Sardaukar
    Coordination's ``SardaukarCoordinationAgentAbility`` (Optional, 0.5),
    whose targets are ``GetGarrisonUnits().Take(TroopDeployNumber)``: the 4
    recruited troops, not the 7-troop garrison."""

    state, seat, _ = _place(
        "sardaukar_coordination",
        "sardaukar",
        resources=Resources(solari=0, spice=4, water=1),
    )
    state = _apply(state, seat, _a(seat, "resolve_board_effect", effect="troops"))
    assert state.players[seat].troops_garrison == 7
    seen: list[tuple[int, int]] = []

    def units(garrison: int, maximum: int) -> int:
        seen.append((garrison, maximum))
        return 2

    patches: Patches = {"units_to_deploy": units}
    (deploy,) = _sources_with(state, seat, ae._deploy)
    assert (deploy.label, deploy.stage) == ("Deploy Units", Stage.PROMPT)
    assert deploy.extra["explicit"] is False
    turn = ae._turn(_run(state, seat, patches))
    ae._deploy(turn)
    (deploy,) = turn.sources
    assert deploy.evaluate is not None
    assert deploy.evaluate() == (0.5, _a(seat, "deploy_troops", count=2))
    assert seen == [(4, 4)]
    taken, after = _drive(state, seat, patches)
    assert _ids(taken) == [
        "resolve_faction_influence",
        "resolve_board_effect:intrigue",
        "deploy_troops:2",
        "finish_agent_turn",
    ]
    assert after.players[seat].troops_conflict == 2
    # Once used, the source is gone although the engine still offers the
    # other two recruited troops.
    state = _apply(state, seat, _a(seat, "resolve_faction_influence"))
    state = _apply(state, seat, _a(seat, "resolve_board_effect", effect="intrigue"))
    state = _apply(state, seat, _a(seat, "deploy_troops", count=2))
    assert any(
        a.action_id == "deploy_troops" for a in ENGINE.legal_actions(state, seat)
    )
    assert _sources_with(state, seat, ae._deploy) == []
    assert _must(state, seat, patches) == _a(seat, "finish_agent_turn")


def test_seek_allies_trash_is_an_end_of_turn_chore() -> None:
    """Seek Allies' ``TrashSelfAbility`` is Implicit (after End Turn): the
    space's gains and influence come first, the trash when nothing is left."""

    state, seat, ref = _place("seek_allies", "deliver_supplies")
    taken, after = _drive(state, seat, NO_DEPLOY)
    assert _ids(taken) == [
        "resolve_board_effect:resources",
        "resolve_faction_influence",
        "resolve_agent_card_effect",
        "finish_agent_turn",
    ]
    assert ref not in after.players[seat].in_play


# ---------------------------------------------------------------------------
# Gather Intelligence (state 260)
# ---------------------------------------------------------------------------

_RESEARCH_POSTS = (
    "arrakis-research-station-spice-refinery",
    "arrakis-research-station-sietch-tabr",
)


def _research_station_with_spies() -> tuple[GameState, int]:
    state, seat, _ = _place(
        "reconnaissance",
        "research_station",
        resources=Resources(solari=0, spice=0, water=2),
        spy_post_ids=_RESEARCH_POSTS,
        spies_supply=1,
    )
    return state, seat


def test_gather_intelligence_recalls_get_recall_spy_s_spy() -> None:
    """``CardDrawValueWithBuyGains - SpyValue > 0``: option 1 with the Spy
    ``GetRecallSpy`` names among the observing Spies."""

    state, seat = _research_station_with_spies()
    offered: list[tuple[str, ...]] = []

    def recall_spy(spies: list[Entity]) -> tuple[Entity, float]:
        offered.append(tuple(spy.ref for spy in spies))
        return spies[1], 0.0

    patches: Patches = {
        "card_draw_value_with_buy_gains": _const(3.0),
        "spy_value": _summer(1.0),
        "recall_spy": recall_spy,
    }
    assert _must(state, seat, patches) == _a(
        seat, "gather_intelligence", post_id=_RESEARCH_POSTS[1]
    )
    assert offered == [_RESEARCH_POSTS]


def test_gather_intelligence_declines_when_the_spy_is_worth_more() -> None:
    state, seat = _research_station_with_spies()
    patches: Patches = {
        "card_draw_value_with_buy_gains": _const(1.0),
        "spy_value": _summer(1.0),
    }
    assert _must(state, seat, patches) == _a(seat, "decline_gather_intelligence")


def test_gather_intelligence_with_three_spies_out_always_recalls() -> None:
    """+100 with three or more Spies deployed."""

    state, seat = _research_station_with_spies()
    state = with_player(
        state,
        seat,
        spy_post_ids=(*_RESEARCH_POSTS, "arrakis-hagga-basin"),
        spies_supply=0,
    )
    patches: Patches = {
        "card_draw_value_with_buy_gains": _const(1.0),
        "spy_value": _summer(5.0),
        "recall_spy": lambda spies: (spies[0], 0.0),
    }
    assert _must(state, seat, patches) == _a(
        seat, "gather_intelligence", post_id=_RESEARCH_POSTS[0]
    )


# ---------------------------------------------------------------------------
# Space choices in the prompt
# ---------------------------------------------------------------------------


def _espionage(**changes: Any) -> tuple[GameState, int]:
    state, seat, _ = _place(
        "diplomacy",
        "espionage",
        resources=Resources(solari=0, spice=1, water=1),
        leader_id="gurney_halleck",
        leader_face_id="gurney_halleck",
        **changes,
    )
    return state, seat


def _until(state: GameState, seat: int, action_id: str, patches: Patches) -> GameState:
    """Answer with the window until ``action_id`` is the window's answer."""

    for _ in range(10):
        action = _must(state, seat, patches)
        if action.action_id == action_id:
            return state
        state = _apply(state, seat, action)
    raise AssertionError(f"{action_id} never chosen")


def test_espionage_places_on_get_best_post() -> None:
    state, seat = _espionage()
    best = "landsraad-assembly-hall-gather-support"

    def best_post(posts: list[Entity], unseen: bool = False) -> tuple[Entity, float]:
        assert unseen is False
        return next(p for p in posts if p.ref == best), 1.0

    patches: Patches = {**NO_DEPLOY, "best_post": best_post, "spy_value": _summer(2.0)}
    state = _until(state, seat, "resolve_espionage_place_spy", patches)
    assert _must(state, seat, patches) == _a(
        seat, "resolve_espionage_place_spy", post_id=best
    )


def test_espionage_spy_is_forced_even_when_worth_nothing() -> None:
    """An Explicit key forces the prompt: with nothing worth more than 0 the
    app answers at random among its keys, never End Turn."""

    state, seat = _espionage()
    patches: Patches = {**NO_DEPLOY, "spy_value": _summer(-1.0)}
    for _ in range(3):  # influence, cards (immediate)
        action = _must(state, seat, patches)
        if action.action_id == "resolve_espionage_place_spy":
            break
        state = _apply(state, seat, action)
    assert _must(state, seat, patches).action_id == "resolve_espionage_place_spy"


def test_espionage_with_an_empty_supply_recalls_first_then_places() -> None:
    """The app never declines: ``RecallSpyEvaluator`` recalls the Spy on the
    worst post, then the placement is the rest of the same ``PlaceSpy``."""

    posts = ("arrakis-hagga-basin", "arrakis-deep-desert", "arrakis-imperial-basin")
    state, seat = _espionage(spies_supply=0, spy_post_ids=posts)
    patches: Patches = {
        **NO_DEPLOY,
        "spy_value": _summer(2.0),
        "recall_spy": lambda spies: (spies[1], 0.0),
    }
    state = _until(state, seat, "recall_spy_for_espionage", patches)
    assert _must(state, seat, patches) == _a(
        seat, "recall_spy_for_espionage", post_id=posts[1]
    )
    state = _apply(state, seat, _must(state, seat, patches))
    # Now only the placement is left of that answer: it is a follow-up even
    # when SpyValue would no longer rank it first.
    low: Patches = {**patches, "spy_value": _summer(-5.0)}
    (follow_up,) = _sources_with(state, seat, ae._espionage)
    assert (follow_up.stage, follow_up.order) == (Stage.COST_FIRST, -1)
    assert _must(state, seat, low).action_id == "resolve_espionage_place_spy"


def _sietch(**changes: Any) -> tuple[GameState, int]:
    state, seat, _ = _place(
        "reconnaissance", "sietch_tabr", influence=Influence(fremen=2), **changes
    )
    return state, seat


@pytest.mark.parametrize(
    ("hooks", "wall", "should_blow", "expected"),
    [
        (5.0, 0.0, True, "take_sietch_tabr_supplies"),
        (0.0, 5.0, True, "take_sietch_tabr_water_and_destroy_wall"),
        (0.0, 5.0, False, "take_sietch_tabr_water"),
        (1.0, 1.0, True, "take_sietch_tabr_supplies"),  # a tie keeps option 0
    ],
)
def test_sietch_tabr_choice(
    hooks: float, wall: float, should_blow: bool, expected: str
) -> None:
    state, seat = _sietch()
    patches: Patches = {
        **NO_DEPLOY,
        "maker_hooks_value": _const(hooks),
        "blow_wall_value": _summer(wall),
        "should_blow_wall": lambda: should_blow,
    }
    assert _must(state, seat, patches) == _a(seat, expected)


@pytest.mark.parametrize(
    ("worm", "expected"),
    [(10.0, "summon_maker_sandworms"), (0.1, "harvest_maker_spice")],
)
def test_maker_space_spice_or_sandworm(worm: float, expected: str) -> None:
    state, seat, _ = _place("dune_the_desert_planet", "hagga_basin", maker_hooks=True)
    patches: Patches = {**NO_DEPLOY, "sandworm_value": _const(worm)}
    assert _must(state, seat, patches) == _a(seat, expected, space_id="hagga_basin")


def test_imperial_basin_harvest_is_the_space_ability() -> None:
    state, seat, _ = _place("dune_the_desert_planet", "imperial_basin")
    labels = {s.label: s.stage for s in _sources_with(state, seat, ae._maker)}
    assert labels == {"Imperial Basin spice": Stage.SPACE}


def _sources_with(
    state: GameState, seat: int, *builders: Callable[[ae._Turn], None]
) -> list[Source]:
    turn = ae._turn(_run(state, seat))
    for build in builders:
        build(turn)
    return turn.sources


def test_shipping_takes_its_5_solari_then_the_best_influence() -> None:
    state, seat, _ = _place(
        "dune_the_desert_planet",
        "shipping",
        influence=Influence(spacing_guild=2),
        resources=Resources(solari=0, spice=3, water=1),
    )

    def gain(
        faction: str, amount: int, rank: int = -1, alliance: bool = False
    ) -> Summer:
        s = Summer()
        s.add("pinned", 3.0 if faction == "fremen" else 1.0)
        return s

    patches: Patches = {**NO_DEPLOY, "gain_influence_value": gain}
    taken, _ = _drive(state, seat, patches)
    assert _ids(taken) == [
        "resolve_board_effect:resources",
        "choose_shipping_influence:fremen",
        "finish_agent_turn",
    ]


@pytest.mark.parametrize("junk", [True, False])
def test_desert_tactics_trash(junk: bool) -> None:
    """``TrashAgentAbility``: the junk card, or "trash nothing" at 1.0."""

    state, seat, _ = _place("diplomacy", "desert_tactics")
    dagger = next(c for c in state.players[seat].hand if ":dagger:" in c)

    def card_to_trash(
        cards: list[Entity], minimum: float
    ) -> tuple[Entity | None, float]:
        assert minimum == 1.0
        if junk:
            return next(c for c in cards if c.ref == dagger), 5.0
        return None, 1.0

    patches: Patches = {**NO_DEPLOY, "card_to_trash": card_to_trash}
    taken, _ = _drive(state, seat, patches)
    expected = (
        f"trash_card_for_desert_tactics:{dagger}"
        if junk
        else "resolve_desert_tactics_without_trash"
    )
    assert _ids(taken) == [
        "resolve_board_effect:troops",
        "resolve_faction_influence",
        expected,
        "finish_agent_turn",
    ]


def _privilege(**changes: Any) -> tuple[GameState, int]:
    base: dict[str, Any] = {
        "influence": Influence(emperor=2),
        "resources": Resources(solari=3, spice=0, water=1),
    }
    base.update(changes)
    state, seat, _ = _place("dagger", "imperial_privilege", **base)
    return state, seat


def test_imperial_privilege_trashes_a_bad_intrigue() -> None:
    held = ("intrigue:buy_access:0", "intrigue:impress:0")
    state, seat = _privilege(intrigue_cards=held)

    def bad() -> list[Entity]:
        from dune_imperium.agents.app_ai.catalog import intrigue_entity

        return [intrigue_entity(held[1], seat)]

    patches: Patches = {**NO_DEPLOY, "bad_intrigue_cards_in_hand": bad}
    assert _must(state, seat, patches) == _a(
        seat, "trash_intrigue_for_imperial_privilege", card_id=held[1]
    )
    patches = {**NO_DEPLOY, "bad_intrigue_cards_in_hand": lambda: []}
    assert _must(state, seat, patches) == _a(
        seat, "decline_imperial_privilege_intrigue"
    )


def test_imperial_privilege_recall_uses_get_recall_agent() -> None:
    state, seat = _privilege(
        agent_locations=("arrakeen", "sardaukar"),
        agents_available=1,
        swordmaster_acquired=True,
    )
    state = _apply(state, seat, _a(seat, "decline_imperial_privilege_intrigue"))
    patches: Patches = {
        **NO_DEPLOY,
        "recall_agent": lambda agents: agents[1],
        "recall_agent_value": _const(2.0),
    }
    assert _must(state, seat, patches) == _a(
        seat, "recall_agent_for_imperial_privilege", space_id="sardaukar"
    )


def test_imperial_privilege_without_a_recall_is_the_draw() -> None:
    state, seat = _privilege()
    state = _apply(state, seat, _a(seat, "decline_imperial_privilege_intrigue"))
    labels = {
        s.label: s.stage for s in _sources_with(state, seat, ae._imperial_privilege)
    }
    assert labels == {"Imperial Privilege draw": Stage.IMMEDIATE}


# ---------------------------------------------------------------------------
# The card's Agent box
# ---------------------------------------------------------------------------


def _hand_card(state: GameState, seat: int, card: str) -> str:
    return next(ref for ref in state.players[seat].hand if f":{card}:" in ref)


def _trash(
    target: str | None, value: float
) -> Callable[..., tuple[Entity | None, float]]:
    def card_to_trash(
        cards: list[Entity], minimum: float
    ) -> tuple[Entity | None, float]:
        found = next((c for c in cards if c.ref == target), None)
        if target is not None and found is None:
            return None, 0.0  # the target is not among these candidates
        return found, value

    return card_to_trash


def test_calculus_of_power_trash_beats_the_deferred_draw() -> None:
    """Calculus of Power (DeferValue 2) at Arrakeen (1) reaches the
    threshold: the draw waits in the prompt at 1.0 and the junk trash (5.0)
    goes first; without junk ``TrashAbility`` answers "nothing" at 1.0, our
    decline."""

    state, seat, _ = _place("calculus_of_power", "arrakeen")
    dagger = _hand_card(state, seat, "dagger")
    junk: Patches = {**NO_DEPLOY, "card_to_trash": _trash(dagger, 5.0)}
    assert _must(state, seat, junk) == _a(seat, "resolve_board_effect", effect="troops")
    state = _apply(state, seat, _a(seat, "resolve_board_effect", effect="troops"))
    assert _must(state, seat, junk) == _a(seat, "trash_agent_card", card_id=dagger)
    nothing: Patches = {**NO_DEPLOY, "card_to_trash": _trash(None, 1.0)}
    trash = next(s for s in _sources(state, seat, nothing) if s.label.endswith("trash"))
    assert trash.evaluate is not None
    assert trash.evaluate() == (1.0, _a(seat, "decline_agent_card_trash"))


@pytest.mark.parametrize(("trash_value", "used"), [(3.0, True), (-5.0, False)])
def test_shishakli_is_optional(trash_value: float, used: bool) -> None:
    """``ShishakliAgentAbility`` (Optional): Trash Value + one draw; unused
    when not positive, then declined at End Turn."""

    state, seat, _ = _place("shishakli", "arrakeen")
    dagger = _hand_card(state, seat, "dagger")
    patches: Patches = {
        **NO_DEPLOY,
        "card_to_trash": _trash(dagger, trash_value),
        "card_draw_value_with_buy_gains": _const(1.0),
    }
    taken, _ = _drive(state, seat, patches)
    trash = f"trash_agent_card:{dagger}" if used else "decline_agent_card_trash"
    assert trash in _ids(taken)
    if not used:
        assert _ids(taken)[-2:] == ["decline_agent_card_trash", "finish_agent_turn"]


def test_shishakli_targets_are_hand_then_in_play_then_discard() -> None:
    state, seat, ref = _place("shishakli", "arrakeen")
    discard = state.players[seat].hand[-1]
    hand = tuple(c for c in state.players[seat].hand if c != discard)
    state = with_player(state, seat, hand=hand, discard_pile=(discard,))
    order: list[tuple[str, ...]] = []

    def card_to_trash(cards: list[Entity], minimum: float) -> tuple[None, float]:
        order.append(tuple(c.ref for c in cards))
        return None, 0.0

    trash = next(
        s
        for s in _sources(state, seat, {"card_to_trash": card_to_trash})
        if s.label == "shishakli trash"
    )
    assert trash.evaluate is not None
    trash.evaluate()
    assert order == [(*hand, ref, discard)]


def test_treacherous_maneuver_trashes_a_cheap_emperor_card() -> None:
    """``TreacherousManeuverAbility`` (Optional): an Emperor card costing less
    than 4 (Imperial Spymaster, 2) at 200."""

    state, seat, _ = _place(
        "treacherous_maneuver",
        "sardaukar",
        extra=("imperial_spymaster",),
        resources=Resources(solari=0, spice=4, water=1),
    )
    spymaster = _hand_card(state, seat, "imperial_spymaster")
    patches: Patches = {**NO_DEPLOY, "card_to_trash": _trash(None, 0.0)}
    taken, _ = _drive(state, seat, patches)
    assert f"trash_agent_card:{spymaster}" in _ids(taken)


@pytest.mark.parametrize("junk", [True, False])
def test_tread_in_darkness_trash_is_explicit(junk: bool) -> None:
    state, seat, _ = _place(
        "tread_in_darkness", "arrakeen", in_play=("imperium:bene_gesserit_operative:1",)
    )
    dagger = _hand_card(state, seat, "dagger")
    patches: Patches = {
        **NO_DEPLOY,
        "card_to_trash": _trash(dagger if junk else None, 4.0 if junk else 1.0),
    }
    taken, _ = _drive(state, seat, patches)
    expected = f"trash_agent_card:{dagger}" if junk else "decline_agent_card_trash"
    assert expected in _ids(taken)
    # The draw is its own icon (``BeneGesseritDrawAbility``).
    assert "resolve_agent_card_effect:cards" in _ids(taken)


def test_guild_envoy_discards_the_first_of_get_discard_order() -> None:
    state, seat, _ = _place("guild_envoy", "deliver_supplies")
    recon = _hand_card(state, seat, "reconnaissance")

    def order(cards: list[Entity], spacing_guild: bool) -> list[Entity]:
        assert spacing_guild is True
        return sorted(cards, key=lambda c: c.ref != recon)

    taken, _ = _drive(state, seat, {**NO_DEPLOY, "discard_order": order})
    assert _ids(taken) == [
        "resolve_board_effect:resources",
        "resolve_faction_influence",
        f"discard_agent_card:{recon}",
        "finish_agent_turn",
    ]


def test_captured_mentat_rewards_follow_the_discard() -> None:
    """The discard is the app's one answer; the armed Intrigue and card icons
    are the rest of it (follow-ups)."""

    state, seat, _ = _place("captured_mentat", "assembly_hall")
    dagger = _hand_card(state, seat, "dagger")
    patches: Patches = {
        **NO_DEPLOY,
        "discard_order": lambda cards, sg: sorted(cards, key=lambda c: c.ref != dagger),
    }
    taken, _ = _drive(state, seat, patches)
    assert _ids(taken) == [
        "resolve_board_effect:intrigue",
        f"discard_agent_card:{dagger}",
        "resolve_agent_card_effect:intrigue",
        "resolve_agent_card_effect:cards",
        "finish_agent_turn",
    ]


def test_space_time_folding_unused_is_declined() -> None:
    state, seat, _ = _place("space_time_folding", "deliver_supplies")
    patches: Patches = {
        **NO_DEPLOY,
        "discard_value": _const(-10.0),
        "card_draw_value": _const(1.0),
        "buy_gains": _const(0.0),
    }
    taken, _ = _drive(state, seat, patches)
    assert _ids(taken)[-2:] == ["decline_agent_card_discard", "finish_agent_turn"]


def test_corrinth_city_two_discards_from_one_answer() -> None:
    state, seat, _ = _place(
        "corrinth_city",
        "assembly_hall",
        resources=Resources(solari=6, spice=0, water=1),
    )
    recon = _hand_card(state, seat, "reconnaissance")
    dagger = _hand_card(state, seat, "dagger")
    preferred = (dagger, recon)

    def order(cards: list[Entity], sg: bool) -> list[Entity]:
        return sorted(
            cards, key=lambda c: preferred.index(c.ref) if c.ref in preferred else 9
        )

    patches: Patches = {
        **NO_DEPLOY,
        "discard_order": order,
        "victory_point_value": _const(20.0),
    }
    taken, _ = _drive(state, seat, patches)
    assert _ids(taken) == [
        "resolve_board_effect:intrigue",
        f"select_corrinth_city_discard:{dagger}",
        f"pay_corrinth_city:{recon}",
        "finish_agent_turn",
    ]


def test_corrinth_city_not_worth_it_is_declined() -> None:
    state, seat, _ = _place(
        "corrinth_city",
        "assembly_hall",
        resources=Resources(solari=6, spice=0, water=1),
    )
    patches: Patches = {**NO_DEPLOY, "victory_point_value": _const(-20.0)}
    taken, _ = _drive(state, seat, patches)
    assert _ids(taken)[-2:] == ["decline_corrinth_city_payment", "finish_agent_turn"]


def test_branching_path_always_trashes_an_intrigue() -> None:
    """``BranchingPathAbility``: 1.0 for any held intrigue (5.0 if bad)."""

    state, seat, _ = _place(
        "branching_path",
        "arrakeen",
        alliance_faction_ids=("bene_gesserit",),
        influence=Influence(bene_gesserit=4),
        intrigue_cards=("intrigue:buy_access:0",),
    )
    taken, _ = _drive(state, seat, NO_DEPLOY)
    assert "trash_intrigue_for_agent_card:intrigue:buy_access:0" in _ids(taken)
    # The armed Intrigue and spice icons follow at once.
    at = _ids(taken).index("trash_intrigue_for_agent_card:intrigue:buy_access:0")
    assert _ids(taken)[at + 1].startswith("resolve_agent_card_effect:")


@pytest.mark.parametrize(
    ("water", "expected"),
    [(5.0, "decline_agent_card_payment"), (0.1, "pay_agent_card_water")],
)
def test_ecological_testing_station_pays_when_positive(
    water: float, expected: str
) -> None:
    state, seat, _ = _place(
        "ecological_testing_station",
        "arrakeen",
        resources=Resources(solari=0, spice=0, water=2),
    )
    patches: Patches = {
        **NO_DEPLOY,
        "water_value": lambda n: water * n,
        "card_draw_value": _const(1.0),
        "buy_gains": _const(0.0),
    }
    taken, _ = _drive(state, seat, patches)
    assert expected in _ids(taken)


def test_smuggler_s_haven_always_pays() -> None:
    state, seat, _ = _place(
        "smuggler_s_haven",
        "deliver_supplies",
        resources=Resources(solari=0, spice=4, water=1),
    )
    taken, _ = _drive(state, seat, NO_DEPLOY)
    assert "pay_agent_card_spice" in _ids(taken)


def test_price_is_no_object_buys_the_best_card_or_declines() -> None:
    state, seat, _ = _place(
        "price_is_no_object", "secrets", resources=Resources(solari=5, spice=0, water=1)
    )

    def acquire(value_of: Mapping[str, float]) -> Callable[[Entity], Summer]:
        def acquire_value(card: Entity) -> Summer:
            s = Summer()
            s.add("pinned", value_of.get(card.ref, 0.0))
            return s

        return acquire_value

    patches: Patches = {
        **NO_DEPLOY,
        "solari_value": lambda n: 0.1 * n,
        "acquire_value": acquire({"reserve:prepare_the_way": 9.0}),
        "lady_jessica_return_memories": lambda: False,
    }
    taken, _ = _drive(state, seat, patches)
    assert "acquire_reserve_with_solari:prepare_the_way" in _ids(taken)
    patches = {**patches, "acquire_value": acquire({})}
    taken, _ = _drive(state, seat, patches)
    assert "decline_agent_card_acquisition" in _ids(taken)


def test_steersman_card_draw_runs_before_the_space_draw_then_recalls() -> None:
    """Row 1 order: the card's abilities before the space's; the recall is an
    Explicit prompt key."""

    state, seat, _ = _place(
        "steersman",
        "arrakeen",
        agent_locations=("sardaukar",),
        agents_available=1,
    )
    patches: Patches = {
        **NO_DEPLOY,
        "recall_agent_value": _const(3.0),
        "recall_agent": lambda agents: agents[0],
    }
    taken, _ = _drive(state, seat, patches)
    assert _ids(taken) == [
        "resolve_board_effect:troops",
        "resolve_agent_card_effect:cards",
        "resolve_board_effect:cards",
        "recall_agent_for_agent_card:sardaukar",
        "finish_agent_turn",
    ]


def test_hidden_missive_troop_runs_before_the_draws() -> None:
    state, seat, _ = _place(
        "hidden_missive", "assembly_hall", influence=Influence(bene_gesserit=2)
    )
    taken, _ = _drive(state, seat, NO_DEPLOY)
    assert _ids(taken) == [
        "resolve_agent_card_effect:troops",
        "resolve_agent_card_effect:cards",
        "resolve_board_effect:intrigue",
        "finish_agent_turn",
    ]


def test_maker_keeper_riders_run_immediately() -> None:
    state, seat, _ = _place(
        "maker_keeper", "arrakeen", influence=Influence(bene_gesserit=2, fremen=2)
    )
    taken, _ = _drive(state, seat, NO_DEPLOY)
    assert _ids(taken) == [
        "resolve_board_effect:troops",
        "resolve_agent_card_effect:water",
        "resolve_agent_card_effect:spice",
        "resolve_board_effect:cards",
        "finish_agent_turn",
    ]


def test_interstellar_trade_influence_beats_the_deferred_draw() -> None:
    """Interstellar Trade (DeferValue 2) at Arrakeen: threshold reached; the
    influence key (+100) goes before the draw (1.0), to the best faction."""

    state, seat, _ = _place("interstellar_trade", "arrakeen")

    def gain(
        faction: str, amount: int, rank: int = -1, alliance: bool = False
    ) -> Summer:
        s = Summer()
        s.add("pinned", 2.0 if faction == "bene_gesserit" else 1.0)
        return s

    taken, _ = _drive(state, seat, {**NO_DEPLOY, "gain_influence_value": gain})
    assert _ids(taken) == [
        "resolve_board_effect:troops",
        "choose_agent_card_influence:bene_gesserit",
        "resolve_board_effect:cards",
        "finish_agent_turn",
    ]


def test_dangerous_rhetoric_trash_self_is_the_last_chore() -> None:
    state, seat, _ = _place("dangerous_rhetoric", "assembly_hall")
    taken, _ = _drive(state, seat, NO_DEPLOY)
    assert _ids(taken)[0] == "resolve_board_effect:intrigue"
    assert _ids(taken)[1].startswith("choose_agent_card_influence:")
    assert _ids(taken)[2:] == [
        "resolve_agent_card_effect:trash_self",
        "finish_agent_turn",
    ]


@pytest.mark.parametrize(
    ("card", "space", "changes", "patches", "stage", "value"),
    [
        (
            "rebel_supplier",
            "arrakeen",
            {"spies_recalled_turn": 1},
            {},
            Stage.IMMEDIATE,
            None,
        ),
        ("desert_power", "hagga_basin", {}, {}, Stage.IMMEDIATE, None),
        ("priority_contracts", "assembly_hall", {}, {}, Stage.IMMEDIATE, None),
        ("stilgar_the_devoted", "arrakeen", {}, {}, Stage.AGENT_BOX, None),
        (
            "imperial_spymaster",
            "sardaukar",
            {"spies_recalled_turn": 1, "resources": Resources(spice=4)},
            {},
            Stage.PROMPT,
            100.0,
        ),
        (
            "weirding_woman",
            "arrakeen",
            {"in_play": ("imperium:bene_gesserit_operative:1",)},
            {},
            Stage.PROMPT,
            100.0,
        ),
        ("long_live_the_fighters", "arrakeen", {}, {}, Stage.PROMPT, 100.0),
        (
            "leadership",
            "desert_tactics",
            {"sandworms_conflict": 1},
            {"sandworm_value": _const(4.0)},
            Stage.PROMPT,
            3.0,
        ),
        (
            "chani_clever_tactician",
            "arrakeen",
            {"troops_conflict": 3, "troops_garrison": 0},
            {"intrigue_value": _const(2.5)},
            Stage.PROMPT,
            2.5,
        ),
        (
            "in_high_places",
            "secrets",
            {"in_play": ("imperium:bene_gesserit_operative:1",)},
            {"spy_value": _summer(1.5)},
            Stage.PROMPT,
            1.5,
        ),
    ],
)
def test_single_box_stage_and_value(
    card: str,
    space: str,
    changes: dict[str, Any],
    patches: Patches,
    stage: Stage,
    value: float | None,
) -> None:
    state, seat, _ = _place(card, space, **changes)
    (box,) = (s for s in _sources(state, seat, patches) if s.label == f"{card} box")
    assert box.stage is stage
    if value is not None:
        assert box.evaluate is not None
        got, action = box.evaluate()
        assert got == pytest.approx(value)
        assert action == _a(seat, "resolve_agent_card_effect")


def test_covert_operation_is_valued_at_its_defer_value() -> None:
    state, seat, _ = _place(
        "covert_operation",
        "arrakeen",
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
        spies_supply=2,
    )
    state = _apply(state, seat, _a(seat, "decline_gather_intelligence"))
    (box,) = (s for s in _sources(state, seat) if s.label == "covert_operation box")
    assert box.stage is Stage.PROMPT and box.extra["explicit"] is True
    assert box.evaluate is not None and box.evaluate()[0] == 2.0


@pytest.mark.parametrize(
    ("card", "space"),
    [("reliable_informant", "deliver_supplies"), ("double_agent", "arrakeen")],
)
def test_card_spy_places_on_the_best_offered_post(card: str, space: str) -> None:
    state, seat, _ = _place(card, space)
    offered: list[tuple[str, ...]] = []

    def best_post(posts: list[Entity], unseen: bool = False) -> tuple[Entity, float]:
        offered.append(tuple(p.ref for p in posts))
        return posts[-1], 1.0

    patches: Patches = {**NO_DEPLOY, "best_post": best_post, "spy_value": _summer(3.0)}
    taken, _ = _drive(state, seat, patches)
    spy = [a for a in taken if a.action_id == "place_agent_card_spy"]
    assert len(spy) == 1 and spy[0].arguments == (("post_id", offered[-1][-1]),)


_FULL_POSTS = ("arrakis-hagga-basin", "arrakis-deep-desert", "arrakis-imperial-basin")


def _recalled_card_spy() -> tuple[GameState, int]:
    state, seat, _ = _place(
        "reliable_informant",
        "deliver_supplies",
        spies_supply=0,
        spy_post_ids=_FULL_POSTS,
    )
    recall = _a(seat, "recall_spy_for_agent_card", post_id=_FULL_POSTS[1])
    return _apply(state, seat, recall), seat


def _recalled_leader_spy() -> tuple[GameState, int]:
    state, seat = _signet(
        "lady_margot_fenring", spies_supply=0, spy_post_ids=_FULL_POSTS
    )
    recall = _a(seat, "recall_spy_for_leader_placement", post_id=_FULL_POSTS[1])
    return _apply(state, seat, recall), seat


def _recalled_feyd_spy() -> tuple[GameState, int]:
    state, seat = _signet(
        "feyd_rautha_harkonnen", spies_supply=0, spy_post_ids=_FULL_POSTS
    )
    state = _apply(state, seat, _a(seat, "advance_feyd_track", space_id="first_spy"))
    recall = _a(seat, "recall_spy_for_leader_placement", post_id=_FULL_POSTS[1])
    return _apply(state, seat, recall), seat


@pytest.mark.parametrize(
    ("setup", "flag", "place_id"),
    [
        (_recalled_card_spy, "agent_card_spy_recalled", "place_agent_card_spy"),
        (_recalled_leader_spy, "leader_spy_recalled", "place_leader_spy"),
        (_recalled_feyd_spy, "feyd_spy_recalled", "place_leader_spy"),
    ],
)
def test_placement_after_a_recall_first_is_a_follow_up(
    setup: Callable[[], tuple[GameState, int]], flag: str, place_id: str
) -> None:
    """With an empty supply the app's one ``PlaceSpy`` answer recalls first
    (``SelectSpy``) then places (``SelectPost``): once our engine has taken
    the recall, the placement on ``GetBestPost``'s post is the rest of that
    answer, ahead of the space's pending icons and whatever ``SpyValue``."""

    state, seat = setup()
    assert dict(state.decision_stack[-1].context)[flag] is True
    offered: list[tuple[str, ...]] = []

    def best_post(posts: list[Entity], unseen: bool = False) -> tuple[Entity, float]:
        offered.append(tuple(p.ref for p in posts))
        return posts[-1], 1.0

    patches: Patches = {
        **NO_DEPLOY,
        "best_post": best_post,
        "spy_value": _summer(-50.0),
    }
    legal = ENGINE.legal_actions(state, seat)
    places = [a for a in legal if a.action_id == place_id]
    assert len(places) > 1
    assert any(a.action_id == "resolve_board_effect" for a in legal)
    answer = _must(state, seat, patches)
    assert offered, "the follow-up must come from GetBestPost"
    assert answer == _a(seat, place_id, post_id=offered[-1][-1])
    assert offered[-1] == tuple(str(dict(a.arguments)["post_id"]) for a in places)
    (follow_up,) = (s for s in _sources(state, seat) if s.label.endswith("recall"))
    assert (follow_up.stage, follow_up.order) == (Stage.COST_FIRST, -1)


@pytest.mark.parametrize("ordered", [True, False])
def test_corrinth_city_second_discard_without_a_stored_answer(
    ordered: bool,
) -> None:
    """No stored answer (the first discard was not ours): the second discard
    is the first of ``GetDiscardOrder`` (Spacing Guild false) over what is
    left, still a follow-up; an empty order takes the first offered card."""

    state, seat, _ = _place(
        "corrinth_city",
        "assembly_hall",
        resources=Resources(solari=6, spice=0, water=1),
    )
    dagger = _hand_card(state, seat, "dagger")
    state = _apply(
        state, seat, _a(seat, "select_corrinth_city_discard", card_id=dagger)
    )
    pays = [
        a
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "pay_corrinth_city"
    ]
    target = str(dict(pays[2].arguments)["card_id"])
    calls: list[tuple[tuple[str, ...], bool]] = []

    def order(cards: list[Entity], spacing_guild: bool) -> list[Entity]:
        calls.append((tuple(c.ref for c in cards), spacing_guild))
        if not ordered:
            return []
        return sorted(cards, key=lambda c: c.ref != target)

    memory = Memory()
    answer = _must(state, seat, {**NO_DEPLOY, "discard_order": order}, memory)
    expected = target if ordered else str(dict(pays[0].arguments)["card_id"])
    assert answer == _a(seat, "pay_corrinth_city", card_id=expected)
    assert calls == [(tuple(str(dict(a.arguments)["card_id"]) for a in pays), False)]
    assert memory.intents == {}


def _junction(intrigues: tuple[str, ...]) -> tuple[GameState, int]:
    state, seat, _ = _place(
        "junction_headquarters",
        "arrakeen",
        alliance_faction_ids=("spacing_guild",),
        influence=Influence(spacing_guild=4),
        resources=Resources(solari=0, spice=2, water=1),
        intrigue_cards=intrigues,
    )
    deck = tuple(c for c in state.intrigue_deck if c not in intrigues)
    return with_state(state, intrigue_deck=deck), seat


@pytest.mark.parametrize(
    ("held", "climax", "value", "trashed"),
    [
        # Devour is bad without maker hooks at the climax: 5.0.
        (("intrigue:spice_is_power:0", "intrigue:devour:0"), True, 5.0, 1),
        # No bad intrigue: the held one at 1.0.
        (("intrigue:spice_is_power:0",), False, 1.0, 0),
    ],
)
def test_junction_headquarters_pays_with_branching_path_s_pick(
    held: tuple[str, ...], climax: bool, value: float, trashed: int
) -> None:
    """``JunctionHeadquartersAbility`` (Optional): Branching Path's E over
    the held intrigues; the pick maps to ``pay_agent_card_intrigue_and_spice``
    with that intrigue."""

    state, seat = _junction(held)
    patches: Patches = {**NO_DEPLOY, "is_climax": lambda: climax}
    (source,) = (
        s
        for s in _sources(state, seat, patches)
        if s.label == "junction_headquarters intrigue"
    )
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is False
    assert source.evaluate is not None
    assert source.evaluate() == (
        value,
        _a(seat, "pay_agent_card_intrigue_and_spice", intrigue_card_id=held[trashed]),
    )


# ---------------------------------------------------------------------------
# The leader
# ---------------------------------------------------------------------------


def _signet(
    leader: str, face: str | None = None, **changes: Any
) -> tuple[GameState, int]:
    state, seat, _ = _place(
        "signet_ring",
        "arrakeen",
        leader_id=leader,
        leader_face_id=face or leader,
        **changes,
    )
    return state, seat


def test_muad_dib_lead_the_way_waits_in_the_prompt() -> None:
    """``LeadTheWayAbility`` (Discipline) is threshold-gated: the Signet
    Ring's DeferValue 3 keeps it in the prompt at the default 1.0."""

    state, seat = _signet("muad_dib")
    (signet,) = (s for s in _sources(state, seat) if s.label == "signet muad_dib")
    assert signet.stage is Stage.PROMPT and signet.extra["explicit"] is True
    assert signet.evaluate is not None
    assert signet.evaluate() == (1.0, _a(seat, "resolve_agent_card_effect"))


def test_amber_fill_coffers_runs_immediately() -> None:
    state, seat = _signet("lady_amber_metulli")
    (signet,) = (s for s in _sources(state, seat) if s.label.startswith("signet"))
    assert signet.stage is Stage.IMMEDIATE


@pytest.mark.parametrize(
    ("trash", "spy", "expected"),
    [(5.0, 1.0, "paid_trash"), (0.5, 5.0, "first_spy")],
)
def test_feyd_personal_training_picks_the_best_next_space(
    trash: float, spy: float, expected: str
) -> None:
    state, seat = _signet(
        "feyd_rautha_harkonnen", resources=Resources(solari=2, spice=0, water=1)
    )
    patches: Patches = {
        **NO_DEPLOY,
        "trash_card_value": _const(trash),
        "spy_value": _summer(spy),
        "solari_value": lambda n: 0.1 * n,
    }
    state = _until(state, seat, "advance_feyd_track", patches)
    assert _must(state, seat, patches) == _a(
        seat, "advance_feyd_track", space_id=expected
    )


@pytest.mark.parametrize("junk", [True, False])
def test_feyd_pay_to_trash_empty_pick_is_the_decline(junk: bool) -> None:
    """``PersonalTrainingPayToTrashAbility`` answers "nothing" at 1.0: our
    engine cannot pay the Solari for nothing, so the decline (plan §10)."""

    state, seat = _signet(
        "feyd_rautha_harkonnen", resources=Resources(solari=2, spice=0, water=1)
    )
    patches: Patches = {**NO_DEPLOY, "trash_card_value": _const(5.0)}
    state = _until(state, seat, "advance_feyd_track", patches)
    state = _apply(state, seat, _a(seat, "advance_feyd_track", space_id="paid_trash"))
    dagger = _hand_card(state, seat, "dagger")
    trash: Patches = {
        **NO_DEPLOY,
        "card_to_trash": _trash(dagger if junk else None, 3.0 if junk else 1.0),
    }
    state = _until(
        state,
        seat,
        "decline_leader_card_trash" if not junk else "trash_leader_card",
        trash,
    )
    expected = (
        _a(seat, "trash_leader_card", card_id=dagger)
        if junk
        else _a(seat, "decline_leader_card_trash")
    )
    assert _must(state, seat, trash) == expected


def test_feyd_spy_stage_places_with_place_spy_custom() -> None:
    state, seat = _signet("feyd_rautha_harkonnen")
    patches: Patches = {
        **NO_DEPLOY,
        "spy_value": _summer(9.0),
        "best_post": lambda posts, unseen=False: (posts[0], 1.0),
    }
    state = _until(state, seat, "advance_feyd_track", patches)
    state = _apply(state, seat, _a(seat, "advance_feyd_track", space_id="first_spy"))
    action = _must(state, seat, patches)
    assert action.action_id == "place_leader_spy"


def test_margot_places_on_the_best_city_post() -> None:
    state, seat = _signet("lady_margot_fenring")
    patches: Patches = {
        **NO_DEPLOY,
        "spy_value": _summer(3.0),
        "best_post": lambda posts, unseen=False: (posts[1], 1.0),
    }
    taken, _ = _drive(state, seat, patches)
    spy = [a for a in taken if a.action_id == "place_leader_spy"]
    assert spy == [
        _a(seat, "place_leader_spy", post_id="arrakis-research-station-sietch-tabr")
    ]


def test_staban_uses_the_unseen_network_post_value_then_pays() -> None:
    state, seat = _signet(
        "staban_tuek", resources=Resources(solari=0, spice=2, water=1)
    )
    flags: list[bool] = []
    landsraad = "landsraad-assembly-hall-gather-support"

    def best_post(posts: list[Entity], unseen: bool = False) -> tuple[Entity, float]:
        flags.append(unseen)
        return next(p for p in posts if p.ref == landsraad), 1.0

    patches: Patches = {
        **NO_DEPLOY,
        "spy_value": _summer(3.0),
        "best_post": best_post,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 1.0 * n,
    }
    taken, _ = _drive(state, seat, patches)
    assert flags == [True]
    at = _ids(taken).index(f"place_leader_spy:{landsraad}")
    assert _ids(taken)[at + 1] == "pay_leader_signet_spice"


def test_staban_landsraad_trade_not_worth_it_is_declined() -> None:
    state, seat = _signet(
        "staban_tuek", resources=Resources(solari=0, spice=2, water=1)
    )
    landsraad = "landsraad-assembly-hall-gather-support"
    patches: Patches = {
        **NO_DEPLOY,
        "spy_value": _summer(3.0),
        "best_post": lambda posts, unseen=False: (
            next(p for p in posts if p.ref == landsraad),
            1.0,
        ),
        "spice_value": lambda n: 5.0 * n,
        "solari_value": lambda n: 0.1 * n,
    }
    taken, _ = _drive(state, seat, patches)
    assert "decline_leader_signet_payment" in _ids(taken)


def test_irulan_trashes_a_junk_starter() -> None:
    state, seat = _signet("princess_irulan")
    dagger = _hand_card(state, seat, "dagger")
    patches: Patches = {**NO_DEPLOY, "card_to_trash": _trash(dagger, 4.0)}
    taken, _ = _drive(state, seat, patches)
    assert f"trash_leader_card:{dagger}" in _ids(taken)


def test_irulan_acquires_with_the_acquire_ability_s_pick() -> None:
    state, seat = _signet("princess_irulan")
    row = state.imperium_row
    cheap = "imperium:unswerving_loyalty:0"
    state = with_state(
        state,
        imperium_row=(cheap, *row[1:]),
        imperium_deck=tuple(c for c in state.imperium_deck if c != cheap) + (row[0],),
    )
    state = with_player(state, seat, hand=())
    patches: Patches = {**NO_DEPLOY, "card_to_trash": _trash(None, 0.0)}
    taken, _ = _drive(state, seat, patches)
    assert f"acquire_leader_imperium:{cheap}" in _ids(taken)


@pytest.mark.parametrize(
    ("bonus", "expected"),
    [
        (0.0, ("gain_leader_signet_troop", {})),
        (20.0, ("choose_leader_signet_influence", {"faction": "fremen"})),
    ],
)
def test_shaddam_signet(bonus: float, expected: tuple[str, dict[str, str]]) -> None:
    state, seat = _signet(
        "shaddam_corrino_iv", resources=Resources(solari=3, spice=0, water=1)
    )

    def gain(
        faction: str, amount: int, rank: int = -1, alliance: bool = False
    ) -> Summer:
        s = Summer()
        s.add("pinned", bonus if faction == "fremen" else 0.0)
        return s

    patches: Patches = {**NO_DEPLOY, "gain_influence_value": gain}
    state = _until(state, seat, expected[0], patches)
    assert _must(state, seat, patches) == _a(seat, expected[0], **expected[1])


@pytest.mark.parametrize(("spice", "pays"), [(2, True), (1, False)])
def test_lady_jessica_spice_agony_pays_only_above_one_spice(
    spice: int, pays: bool
) -> None:
    state, seat = _signet(
        "lady_jessica", resources=Resources(solari=0, spice=spice, water=1)
    )
    taken, _ = _drive(state, seat, NO_DEPLOY)
    expected = "pay_leader_signet_spice" if pays else "decline_leader_signet_payment"
    assert expected in _ids(taken)


@pytest.mark.parametrize(("water", "pays"), [(3.0, True), (0.1, False)])
def test_water_of_life_pays_when_positive(water: float, pays: bool) -> None:
    state, seat = _signet(
        "lady_jessica",
        "reverend_mother_jessica",
        resources=Resources(solari=0, spice=2, water=1),
    )
    patches: Patches = {
        **NO_DEPLOY,
        "water_value": lambda n: water * n,
        "spice_value": lambda n: 1.0 * n,
    }
    taken, _ = _drive(state, seat, patches)
    expected = "pay_leader_signet_spice" if pays else "decline_leader_signet_payment"
    assert expected in _ids(taken)


@pytest.mark.parametrize("returns", [True, False])
def test_other_memories(returns: bool) -> None:
    state, seat, _ = _place("diplomacy", "secrets")
    patches: Patches = {**NO_DEPLOY, "lady_jessica_return_memories": lambda: returns}
    taken, _ = _drive(state, seat, patches)
    expected = "use_other_memories" if returns else "decline_other_memories"
    assert expected in _ids(taken)


@pytest.mark.parametrize(("intrigue", "pays"), [(9.0, True), (0.0, False)])
def test_reverend_mother_repeat(intrigue: float, pays: bool) -> None:
    state, seat, _ = _place(
        "diplomacy",
        "secrets",
        leader_face_id="reverend_mother_jessica",
        resources=Resources(solari=0, spice=0, water=2),
    )
    patches: Patches = {
        **NO_DEPLOY,
        "water_value": lambda n: 1.0 * n,
        "intrigue_value": _const(intrigue),
    }
    taken, _ = _drive(state, seat, patches)
    expected = "pay_leader_board_repeat" if pays else "decline_leader_board_repeat"
    assert expected in _ids(taken)


# ---------------------------------------------------------------------------
# Contracts and the Emperor-4 Spy
# ---------------------------------------------------------------------------


def _holding(
    contracts: tuple[str, ...], **state_changes: object
) -> tuple[GameState, int]:
    state, seat = _first_turn()

    def drop(zone: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(c for c in zone if c not in contracts)

    state = with_state(
        state,
        face_up_contract_ids=drop(state.face_up_contract_ids),
        contract_bank=drop(state.contract_bank),
        **state_changes,
    )
    state = with_player(state, seat, active_contract_ids=contracts)
    state, ref = _take(state, seat, "reconnaissance")
    legal = ENGINE.legal_actions(state, seat)
    action = next(
        a
        for a in legal
        if a.action_id == "agent_turn"
        and dict(a.arguments).get("card_id") == ref
        and dict(a.arguments).get("space_id") == "arrakeen"
    )
    return _apply(state, seat, action), seat


def test_plain_contracts_run_immediately_spy_contracts_wait() -> None:
    state, seat = _holding(("contract:arrakeen_i", "contract:arrakeen_ii"))
    stages = {s.label: s.stage for s in _sources(state, seat)}
    assert stages["contract contract:arrakeen_i"] is Stage.IMMEDIATE
    assert stages["contract contract:arrakeen_ii"] is Stage.PROMPT
    taken, _ = _drive(state, seat, {**NO_DEPLOY, "spy_value": _summer(2.0)})
    assert _ids(taken)[:3] == [
        "resolve_board_effect:troops",
        "complete_contract:contract:arrakeen_i",
        "resolve_board_effect:cards",
    ]
    assert _ids(taken)[3] == "complete_contract:contract:arrakeen_ii"


def test_recall_agent_contract_offers_the_other_agents() -> None:
    """Sardaukar II (``RecallAgentContractAbility``, ContractBase_13) never
    runs by itself: an Explicit prompt key at ``RecallAgentValue + 1``,
    offering every Agent of ours on the board except this turn's."""

    from dune_imperium.agents.app_ai.catalog import agent_entity

    state, seat = _first_turn()
    held = ("contract:sardaukar_ii",)

    def drop(zone: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(c for c in zone if c not in held)

    state = with_state(
        state,
        face_up_contract_ids=drop(state.face_up_contract_ids),
        contract_bank=drop(state.contract_bank),
    )
    state = with_player(
        state,
        seat,
        active_contract_ids=held,
        agent_locations=("arrakeen",),
        agents_available=1,
        resources=Resources(solari=0, spice=4, water=1),
    )
    state, ref = _take(state, seat, "diplomacy")
    action = next(
        a
        for a in ENGINE.legal_actions(state, seat)
        if dict(a.arguments).get("card_id") == ref
        and dict(a.arguments).get("space_id") == "sardaukar"
    )
    state = _apply(state, seat, action)
    assert state.players[seat].agent_locations == ("arrakeen", "sardaukar")
    offered: list[tuple[str, ...]] = []

    def recall_agent(agents: list[Entity]) -> Entity:
        offered.append(tuple(a.ref for a in agents))
        return agents[0]

    patches: Patches = {
        **NO_DEPLOY,
        "recall_agent": recall_agent,
        "recall_agent_value": _const(2.0),
    }
    (contract,) = (
        s
        for s in _sources(state, seat, patches)
        if s.label == "contract contract:sardaukar_ii"
    )
    assert contract.stage is Stage.PROMPT and contract.extra["explicit"] is True
    assert contract.evaluate is not None
    assert contract.evaluate() == (
        3.0,
        _a(seat, "complete_contract", instance_id="contract:sardaukar_ii"),
    )
    assert offered == [(agent_entity("arrakeen", seat).ref,)]


def test_emperor_track_spy_is_an_explicit_prompt_key() -> None:
    state, seat = _holding((), pending_track_spies=((_first_turn()[1], "test"),))
    (spy,) = (s for s in _sources(state, seat) if s.label == "Emperor track spy")
    assert spy.stage is Stage.PROMPT and spy.extra["explicit"] is True
    taken, _ = _drive(state, seat, {**NO_DEPLOY, "spy_value": _summer(2.0)})
    assert _ids(taken)[-1] == "place_track_spy"


def test_contract_runs_before_a_clearing_influence_step() -> None:
    """``OrderBy(WillClearUndo)``: the space influence clears the undo stack
    when it reaches Bene Gesserit 4 (an Intrigue card), so the plain contract
    of the contract area (row 4, not clearing) runs before it."""

    def turn(bene_gesserit: int) -> list[str]:
        state, seat = _first_turn()
        held = ("contract:espionage_i",)
        state = with_state(
            state, contract_bank=tuple(c for c in state.contract_bank if c not in held)
        )
        state = with_player(
            state,
            seat,
            active_contract_ids=held,
            leader_id="gurney_halleck",
            leader_face_id="gurney_halleck",
            influence=Influence(bene_gesserit=bene_gesserit),
            resources=Resources(solari=0, spice=1, water=1),
        )
        state, ref = _take(state, seat, "diplomacy")
        action = next(
            a
            for a in ENGINE.legal_actions(state, seat)
            if dict(a.arguments).get("card_id") == ref
            and dict(a.arguments).get("space_id") == "espionage"
        )
        state = _apply(state, seat, action)
        taken, _ = _drive(
            state, seat, {**NO_DEPLOY, "spy_value": _summer(1.0)}, limit=3
        )
        return _ids(taken)

    assert turn(1)[:2] == [
        "resolve_faction_influence",
        "complete_contract:contract:espionage_i",
    ]
    assert turn(3)[:2] == [
        "complete_contract:contract:espionage_i",
        "resolve_faction_influence",
    ]


@pytest.mark.parametrize(
    ("leader", "emperor", "bene_gesserit", "space", "extra", "clears"),
    [
        ("princess_irulan", 1, 0, "sardaukar", False, True),  # Imperial Birthright
        ("princess_irulan", 2, 0, "sardaukar", False, False),
        ("princess_irulan", 0, 0, "sardaukar", False, False),
        ("princess_irulan", 0, 0, "sardaukar", True, True),  # 0 with the extra
        ("princess_irulan", 0, 0, "secrets", True, False),  # no Emperor gain
        ("gurney_halleck", 1, 0, "sardaukar", False, False),
        ("gurney_halleck", 0, 0, "sardaukar", True, False),
        ("gurney_halleck", 0, 3, "secrets", False, True),  # the 4-step Intrigue
        ("gurney_halleck", 0, 2, "secrets", False, False),
        ("gurney_halleck", 0, 2, "secrets", True, True),  # extra and BG == 2
        # The ``extra and BG == 2`` tail does not test the space's faction.
        ("gurney_halleck", 0, 2, "sardaukar", True, True),
        ("gurney_halleck", 0, 3, "sardaukar", True, False),
    ],
)
def test_gain_influence_will_clear_undo(
    leader: str,
    emperor: int,
    bene_gesserit: int,
    space: str,
    extra: bool,
    clears: bool,
) -> None:
    """``GainInfluenceAbility::WillClearUndo`` @0x4bad640, ``extra`` =
    ``player.AdditionalSpaceInfluence``."""

    from dune_imperium.agents.app_ai.abilities.generic import GainInfluenceAbility
    from dune_imperium.agents.app_ai.catalog import space_entity

    state, seat = _first_turn()
    state = with_player(
        state,
        seat,
        leader_id=leader,
        leader_face_id=leader,
        influence=Influence(emperor=emperor, bene_gesserit=bene_gesserit),
    )
    found = ae._first_of(space_entity(space, Board(True)), GainInfluenceAbility)
    assert found is not None and isinstance(found[0], GainInfluenceAbility)
    profile = make_profile(state, seat)
    assert ae._gain_influence_clears_undo(found[0], profile, extra) is clears


def _contract_turn(card: str, bene_gesserit: int) -> list[str]:
    """``card`` to Deliver Supplies (Spacing Guild) holding the plain Deliver
    Supplies contract (3 Solari, completes at once, never clears undo)."""

    state, seat = _first_turn()
    held = ("contract:deliver_supplies",)

    def drop(zone: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(c for c in zone if c not in held)

    state = with_state(
        state,
        contract_bank=drop(state.contract_bank),
        face_up_contract_ids=drop(state.face_up_contract_ids),
    )
    state = with_player(
        state,
        seat,
        active_contract_ids=held,
        leader_id="gurney_halleck",
        leader_face_id="gurney_halleck",
        influence=Influence(bene_gesserit=bene_gesserit),
    )
    state, ref = _take(state, seat, card)
    action = next(
        a
        for a in ENGINE.legal_actions(state, seat)
        if dict(a.arguments).get("card_id") == ref
        and dict(a.arguments).get("space_id") == "deliver_supplies"
    )
    taken, _ = _drive(_apply(state, seat, action), seat, NO_DEPLOY)
    return _ids(taken)


@pytest.mark.parametrize(
    ("card", "bene_gesserit", "contract_first"),
    [
        ("overthrow", 2, True),  # PowerPlay set the flag; BG == 2 clears
        ("overthrow", 1, False),
        ("diplomacy", 2, False),  # no PowerPlay: the flag stays false
    ],
)
def test_power_play_box_makes_the_influence_step_clear_undo(
    card: str, bene_gesserit: int, contract_first: bool
) -> None:
    """Overthrow's ``PowerPlayAgentAbility`` (state 500) sets
    ``AdditionalSpaceInfluence``; with Bene Gesserit influence 2 the Spacing
    Guild space's influence step then clears undo (``extra and BG == 2``,
    whatever faction the space gives), so ``OrderBy(WillClearUndo)`` runs
    the contract area's plain contract (row 4) before it."""

    taken = _contract_turn(card, bene_gesserit)
    steps = [
        "complete_contract:contract:deliver_supplies",
        "resolve_faction_influence",
    ]
    if not contract_first:
        steps.reverse()
    box = ["resolve_agent_card_effect"] if card == "overthrow" else []
    assert taken == [
        "resolve_board_effect:resources",
        *box,
        *steps,
        "finish_agent_turn",
    ]


def test_additional_space_influence_follows_the_turn() -> None:
    """The flag is false until the PowerPlay box resolves; Treacherous
    Maneuver sets it only when used (it then trashes itself), not when
    declined; any other card leaves it false."""

    def flag(state: GameState, seat: int) -> bool:
        return ae._turn(_run(state, seat)).additional_space_influence

    state, seat, _ = _place("overthrow", "deliver_supplies")
    assert flag(state, seat) is False
    state = _apply(state, seat, _a(seat, "resolve_agent_card_effect"))
    assert flag(state, seat) is True

    tm, seat, _ = _place(
        "treacherous_maneuver",
        "sardaukar",
        extra=("imperial_spymaster",),
        resources=Resources(solari=0, spice=4, water=1),
    )
    assert flag(tm, seat) is False
    spymaster = _hand_card(tm, seat, "imperial_spymaster")
    used = _apply(tm, seat, _a(seat, "trash_agent_card", card_id=spymaster))
    assert flag(used, seat) is True
    declined = _apply(tm, seat, _a(seat, "decline_agent_card_trash"))
    assert flag(declined, seat) is False

    state, seat, _ = _place("diplomacy", "deliver_supplies")
    assert flag(state, seat) is False


# ---------------------------------------------------------------------------
# Plots, End Turn
# ---------------------------------------------------------------------------


def test_plots_join_the_prompt_only_once_the_turn_can_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def plots(
        run: DecisionRun, plays: tuple[DomainAction, ...], combat: bool
    ) -> list[Source]:
        assert combat is False
        calls.append(len(plays))
        return [Source("plot", Stage.PROMPT, plays, evaluate=lambda: (50.0, plays[0]))]

    monkeypatch.setattr(ae, "intrigue_play_sources", plots)
    card = "intrigue:crysknife:0"
    state, seat, _ = _place(
        "diplomacy",
        "sardaukar",
        resources=Resources(solari=0, spice=4, water=1),
        intrigue_cards=(card,),
    )
    state = with_state(
        state, intrigue_deck=tuple(c for c in state.intrigue_deck if c != card)
    )
    taken, _ = _drive(state, seat, NO_DEPLOY, limit=4)
    # The Plot (50.0) waits for the space's gains and influence, then wins.
    assert _ids(taken)[:3] == [
        "resolve_board_effect:troops",
        "resolve_faction_influence",
        "resolve_board_effect:intrigue",
    ]
    assert taken[3].action_id == "play_intrigue"
    assert calls and calls[0] >= 1
    assert len(calls) == 1  # never consulted before ``finish_agent_turn``


def test_withdraw_is_never_used_and_end_turn_is_the_empty_answer() -> None:
    state, seat, _ = _place("paracompass", "arrakeen")
    deploy: Patches = {"units_to_deploy": lambda garrison, maximum: 2}
    taken, after = _drive(state, seat, deploy)
    assert not any(a.action_id == "withdraw_troops" for a in taken)
    assert taken[-1].action_id == "finish_agent_turn"
    assert after.players[seat].troops_conflict == 2


# ---------------------------------------------------------------------------
# Coverage: full games
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("game", range(6))
def test_full_games_never_fall_back_in_agent_effects(
    game: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Four app_ai seats finish a game (base and CHOAM, rotated leaders);
    this window answers every ``agent_effects`` decision. Other windows are
    left to the fallback here (they are other modules' business)."""

    monkeypatch.setattr(
        agent_module,
        "handler_for",
        lambda kind: ae.agent_effects_window if kind == "agent_effects" else None,
    )
    choam = game % 2 == 1
    seed = 40 + game
    engine = UprisingRulesEngine(leader_ids=_rotated_leader_ids(seed, choam))
    agents = tuple(AppAIAgent(seed=500 + 4 * game + seat) for seat in range(4))
    result = run_policy_game(engine, RulesetConfig(choam_module=choam), seed, agents)
    assert result.state.phase is GamePhase.FINISHED
    mirrored: Counter[str] = Counter()
    for agent in agents:
        assert agent.fallbacks["agent_effects"] == 0
        mirrored.update(agent.mirrored)
    assert mirrored["agent_effects"] > 50


def test_priority_contracts_in_the_prompt_values_the_contract_options() -> None:
    """With the threshold reached (two DeferValue-2 intrigues), Priority
    Contracts' ``GainContractAbility`` waits in the prompt at
    ``ContractEvaluate`` over the face-up contracts."""

    state, seat, _ = _place(
        "priority_contracts",
        "assembly_hall",
        intrigue_cards=("intrigue:cunning:0", "intrigue:mercenaries:0"),
    )
    seen: list[tuple[str, ...]] = []

    def best_contract(contracts: list[Entity], forced: bool) -> tuple[Entity, float]:
        assert forced is True
        seen.append(tuple(c.ref for c in contracts))
        return contracts[0], 7.0

    patches: Patches = {"best_contract": best_contract}
    (box,) = (
        s for s in _sources(state, seat, patches) if s.label == "priority_contracts box"
    )
    assert box.stage is Stage.PROMPT and box.evaluate is not None
    assert box.evaluate() == (7.0, _a(seat, "resolve_agent_card_effect"))
    assert seen == [state.face_up_contract_ids]
