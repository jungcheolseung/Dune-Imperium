"""The Arrakeen Scouts decision windows of app_ai (``windows/scouts.py``).

Spec: docs/app-ai/scouts.md §3 (the windows), applying docs/app-ai-plan.md
§11.4/§11.5 (the app has no Scouts; every answer is the app-style
extension). Each test takes a real game state of a Scouts game with every
other option on, opens the window with the engine's own frame builders, and
checks the action the handler gives against the ported evaluator (run on a
fresh profile with the same RNG seed) and against the rule it implements.
"""

import copy
import random
from collections.abc import Sequence
from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.abilities import scouts as sc
from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.generic import (
    RecallAgentAbility,
    TrashCustomAbility,
)
from dune_imperium.agents.app_ai.abilities.intrigue import choose_faction_influence
from dune_imperium.agents.app_ai.agent import app_offered
from dune_imperium.agents.app_ai.catalog import (
    agent_entity,
    card_entity,
    intrigue_entity,
    scouts_line_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, AppContext
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import handler_for
from dune_imperium.agents.app_ai.windows import scouts as W
from dune_imperium.agents.app_ai.windows.immortality import optional_trash
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.agents.determinize import determinize
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts_auctions import (
    offer_bid,
    offer_call,
    offer_retreat,
    offer_take,
)
from dune_imperium.rules.scouts_effects import (
    advance_scouts_effect,
    offer_only_line,
    offer_scouts_choice,
    push_scouts_effect,
    scouts_effect_can_advance,
)
from dune_imperium.rules.scouts_missions import offer_mission_join
from dune_imperium.rules.scouts_secrets import offer_secret_pick
from dune_imperium.simulation.runner import run_policy_game

#: A Scouts game with every other option on (the task's census cell).
SCOUTS = RulesetConfig(
    choam_module=True,
    bloodlines=True,
    tech_module=True,
    arrakeen_scouts=True,
    promo_cards=True,
    immortality=True,
)
ME = 0  # the first seat to decide in round 1 of seed 1
SOURCE = "round:1:scouts:test"
SCOUTS_KINDS = frozenset(W.HANDLERS) | {"optional_trash"}


@cache
def _base() -> GameState:
    """Round 1, seat 0's first Agent turn (hand: Diplomacy, Convincing
    Argument x2, Experimentation, Dagger; 1 water)."""

    return first_decision("turn", config=SCOUTS)


def _me(state: GameState, **changes: object) -> GameState:
    return with_player(state, ME, **changes)


def _troops(
    supply: int, garrison: int = 0, conflict: int = 0, specimens: int = 0
) -> dict[str, int]:
    """Troop fields that keep the 12-troop total."""

    assert supply + garrison + conflict + specimens == 12
    return {
        "troops_supply": supply,
        "troops_garrison": garrison,
        "troops_conflict": conflict,
        "specimens": specimens,
    }


def _resources(state: GameState, **amounts: int) -> GameState:
    me = state.players[ME]
    return _me(state, resources=replace(me.resources, **amounts))


def _frame(kind: FrameKind, *context: tuple[str, ActionValue]) -> DecisionFrame:
    return DecisionFrame(
        kind=kind,
        frame_id=f"{SOURCE}:{kind}",
        decision=PlayerDecision(owner=ME, prompt="test"),
        context=tuple(sorted(context, key=lambda item: item[0])),
    )


def _effect(state: GameState, item: str, option: int, step: int = 0) -> GameState:
    """A ``scouts_effect`` frame of ``item``'s line at ``step``."""

    pushed = push_scouts_effect(state, ME, item, option, source=SOURCE)
    frame = pushed.decision_stack[-1]
    context = dict(frame.context)
    context["step"] = step
    moved = replace(frame, context=tuple(sorted(context.items())))
    return replace(pushed, decision_stack=(*pushed.decision_stack[:-1], moved))


def _run(
    state: GameState, *, rng_seed: int = 0, memory: Memory | None = None
) -> DecisionRun:
    profile = make_profile(state, ME, rng_seed=rng_seed)
    actions = app_offered(ENGINE.legal_actions(state, ME))
    return DecisionRun(profile.ctx, profile, actions, profile.rng, memory or Memory())


def _fresh(state: GameState, rng_seed: int = 0) -> Profile:
    return make_profile(state, ME, rng_seed=rng_seed)


def _decide(
    state: GameState, *, rng_seed: int = 0, memory: Memory | None = None
) -> DomainAction | None:
    kind = state.decision_stack[-1].kind
    handler = handler_for(str(kind))
    assert handler is not None
    run = _run(state, rng_seed=rng_seed, memory=memory)
    action = handler(run)
    assert action is None or action in run.legal
    return action


def _arg(action: DomainAction | None, name: str) -> object:
    assert action is not None
    return arg(action, name)


def _request(entities: Sequence[Entity]) -> Request:
    info = TargetInfo(entities=tuple(entities), min_select=1, max_select=1, forced=True)
    return Request(infos=(info,), forced=True)


def _first(answer: Answer) -> object:
    response = answer.response
    assert response
    return response[0][0]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_every_scouts_window_is_registered() -> None:
    for kind in (
        "scouts_choice",
        "scouts_effect",
        "scouts_subcommittee",
        "scouts_mission",
        "scouts_secret",
        "scouts_bid",
        "scouts_retreat",
        "scouts_call",
        "scouts_market",
        "scouts_four_bonus",
    ):
        assert handler_for(kind) is W.HANDLERS[kind]


# ---------------------------------------------------------------------------
# scouts_choice (§3.1)
# ---------------------------------------------------------------------------


def test_rebuild_infrastructure_always_passes() -> None:
    """Rebuild's line is ``Spi(-1) - BWV`` < 0, so the seat passes (§3.1,
    D28; computed from the line, not hard-coded)."""

    state = _resources(with_state(_base(), shield_wall_present=False), spice=3)
    state = offer_scouts_choice(
        state, ME, "rebuild_infrastructure", source=SOURCE
    ).state
    run = _run(state)
    assert {a.action_id for a in run.legal} == {"scouts_pass", "scouts_choose_option"}
    assert _fresh(state).scouts_item_line_value("rebuild_infrastructure", 0) < 0
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_pass"


def test_passable_sale_takes_the_best_positive_line() -> None:
    state = _resources(_base(), spice=6, solari=6)
    state = offer_scouts_choice(state, ME, "secrets_for_sale", source=SOURCE).state
    expected = sc.ScoutsChoiceEvaluator.evaluate(
        _fresh(state), "secrets_for_sale", [0, 1], passable=True
    )
    action = _decide(state)
    assert action is not None
    if expected.response is None:
        assert action.action_id == "scouts_pass"
    else:
        assert action.action_id == "scouts_choose_option"
        assert _arg(action, "option") == _first(expected)


def test_mandatory_influence_reduction_is_least_loss() -> None:
    """Water for Spice Smugglers: no pass; both lines lose, so the least
    loss is taken (§3.1, D15)."""

    state = _me(
        _resources(_base(), water=2),
        influence=Influence(emperor=0, spacing_guild=2, bene_gesserit=0, fremen=0),
    )
    state = offer_scouts_choice(
        state, ME, "water_for_spice_smugglers", source=SOURCE
    ).state
    run = _run(state)
    assert "scouts_pass" not in {a.action_id for a in run.legal}
    p = _fresh(state)
    values = [p.scouts_item_line_value("water_for_spice_smugglers", k) for k in (0, 1)]
    assert all(v <= 0 for v in values) and values[0] != values[1]
    action = _decide(state)
    assert _arg(action, "option") == values.index(max(values))


def test_revealed_secret_cost_line_is_an_optional_only_line() -> None:
    """Covert Operation 2 (discard 1 -> recruit 3) at resolution: take it iff
    its line is worth more than 0."""

    state = offer_only_line(_base(), ME, "covert_operation", 2, source=SOURCE).state
    assert dict(state.decision_stack[-1].context)["only_option"] == 2
    value = _fresh(state).scouts_item_line_value("covert_operation", 2)
    action = _decide(state)
    assert action is not None
    if value > 0:
        assert action.action_id == "scouts_choose_option"
        assert _arg(action, "option") == 2
    else:
        assert action.action_id == "scouts_pass"


def test_unknown_scouts_item_falls_back() -> None:
    """An item without a line archetype is never answered by default."""

    state = _base().push_decision(
        _frame(FrameKind.SCOUTS_CHOICE, ("item", "not_an_item"), ("player", ME))
    )
    profile = _fresh(state)
    legal = (
        DomainAction(action_id="scouts_pass", actor=ME),
        DomainAction(
            action_id="scouts_choose_option", actor=ME, arguments=(("option", 0),)
        ),
    )
    run = DecisionRun(profile.ctx, profile, legal, profile.rng, Memory())
    assert W.scouts_choice(run) is None


# ---------------------------------------------------------------------------
# scouts_effect (§3.2)
# ---------------------------------------------------------------------------


def test_discard_step_is_the_first_of_the_discard_order() -> None:
    state = _effect(_base(), "appropriations", 0)
    p = _fresh(state)
    hand = [card_entity(ref, ME) for ref in state.players[ME].hand]
    expected = p.discard_order(hand, False)[0].ref
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_discard"
    assert _arg(action, "card_id") == expected


def test_forced_hand_trash_step_uses_the_line_ability() -> None:
    state = _effect(_base(), "funeral_rites", 0)
    hand = [card_entity(ref, ME) for ref in state.players[ME].hand]
    ability = sc.TrashFromHandCostAbility(scouts_line_entity("funeral_rites", 0, ME))
    expected = ability.evaluate(_fresh(state), _request(hand))
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_trash_card"
    assert _arg(action, "card_id") == _first(expected)


def test_intrigue_trash_step_takes_junk_first() -> None:
    intrigues = ("intrigue:depart_for_arrakis:0", "intrigue:secure_spice_trade:0")
    state = _effect(_me(_base(), intrigue_cards=intrigues), "contingencies", 0)
    ability = sc.TrashIntrigueCostAbility(scouts_line_entity("contingencies", 0, ME))
    expected = ability.evaluate(
        _fresh(state), _request([intrigue_entity(i, ME) for i in intrigues])
    )
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_trash_intrigue"
    assert _arg(action, "card_id") == _first(expected)


def test_spy_recall_step_recalls_the_worst_spy() -> None:
    posts = ("arrakis-imperial-basin", "landsraad-assembly-hall-gather-support")
    state = _me(_base(), spy_post_ids=posts, spies_supply=1)
    state = _effect(state, "oversight", 0)
    run = _run(state)
    assert {_arg(a, "post_id") for a in run.legal} == set(posts)
    spy, _ = _fresh(state).recall_spy([spy_entity(p, ME) for p in posts])
    assert spy is not None
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_recall_spy"
    assert _arg(action, "post_id") == spy.ref


def test_any_faction_step_is_the_gain_picker() -> None:
    """Relations, after its spice cost: GainAnyInfluence's Evaluate."""

    state = _effect(_base(), "relations", 0, step=1)
    expected = choose_faction_influence(
        _fresh(state), [track_entity(f) for f in FACTIONS]
    )
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_choose_faction"
    assert _arg(action, "faction") == _first(expected)


def test_lowest_faction_tie_is_the_gain_picker() -> None:
    """Covert Operation 3 with two tied lowest tracks (D47)."""

    state = _me(
        _base(),
        influence=Influence(emperor=2, spacing_guild=0, bene_gesserit=1, fremen=0),
    )
    state = _effect(state, "covert_operation", 3)
    run = _run(state)
    offered = [_arg(a, "faction") for a in run.legal]
    assert offered == ["spacing_guild", "fremen"]
    expected = choose_faction_influence(
        _fresh(state), [track_entity(str(f)) for f in offered]
    )
    action = _decide(state)
    assert _arg(action, "faction") == _first(expected)


def test_recall_agent_step_is_recall_agent_evaluate() -> None:
    """Contingencies' recall (D48): ``GetRecallAgent ?? first``."""

    spaces = ("imperial_basin", "gather_support", "high_council")
    state = _me(
        _base(), agent_locations=spaces, agents_available=0, swordmaster_acquired=True
    )
    state = _effect(state, "contingencies", 0, step=1)
    pushed = state.decision_stack[-1]
    context = dict(pushed.context)
    context["exclude_space"] = "high_council"
    state = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(pushed, context=tuple(sorted(context.items()))),
        ),
    )
    run = _run(state)
    offered = [str(_arg(a, "space_id")) for a in run.legal]
    assert offered == ["imperial_basin", "gather_support"]
    ability = RecallAgentAbility(scouts_line_entity("contingencies", 0, ME))
    expected = ability.evaluate(
        _fresh(state), _request([agent_entity(s, ME) for s in offered])
    )
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_recall_agent"
    assert _arg(action, "space_id") == _first(expected)


def _alliance_tie(state: GameState) -> GameState:
    """Seat 0 holds the Emperor Alliance at 4; seats 1 and 2 are at 4 too."""

    players = list(state.players)
    for seat in (0, 1, 2):
        player = players[seat]
        players[seat] = replace(player, influence=replace(player.influence, emperor=4))
    players[0] = replace(players[0], alliance_faction_ids=("emperor",))
    return replace(state, players=tuple(players))


def test_named_faction_loss_takes_the_first_alliance_recipient() -> None:
    """Crackdown's Emperor loss with a recipient tie: the first offered
    action (plan §11.5, D17)."""

    state = _effect(_alliance_tie(_base()), "crackdown", 1)
    run = _run(state)
    assert [a.action_id for a in run.legal] == ["scouts_lose_influence_to"] * 2
    action = _decide(state)
    assert action == run.legal[0]


def test_highest_track_tie_is_least_loss() -> None:
    """Political Equilibrium with two tied highest tracks (§3.2, D16)."""

    state = _me(
        _base(),
        influence=Influence(emperor=2, spacing_guild=0, bene_gesserit=2, fremen=1),
    )
    state = _effect(state, "political_equilibrium", 0)
    run = _run(state)
    offered = [str(_arg(a, "faction")) for a in run.legal]
    assert offered == ["emperor", "bene_gesserit"]
    expected = sc.lose_influence_answer(_fresh(state), offered)
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_lose_influence"
    assert _arg(action, "faction") == _first(expected)


def test_highest_track_loss_split_by_recipient_takes_the_first() -> None:
    state = _effect(_alliance_tie(_base()), "political_equilibrium", 0)
    run = _run(state)
    assert {a.action_id for a in run.legal} == {"scouts_lose_influence_to"}
    action = _decide(state)
    assert action == run.legal[0]


def test_recruit_top_up_returns_the_largest_count() -> None:
    """Covert Operation 2's recruit 3 with one troop in supply (D39)."""

    state = _me(_base(), **_troops(supply=1, garrison=8, specimens=3))
    state = _effect(state, "covert_operation", 2, step=1)
    run = _run(state)
    assert [_arg(a, "count") for a in run.legal] == [0, 1, 2]
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_return_specimens"
    assert _arg(action, "count") == 2


# ---------------------------------------------------------------------------
# scouts_subcommittee (§3.3)
# ---------------------------------------------------------------------------


def _subcommittee_frame(state: GameState) -> GameState:
    return state.push_decision(
        _frame(
            FrameKind.SCOUTS_SUBCOMMITTEE,
            ("exclude_space", "high_council"),
            ("player", ME),
            ("source", SOURCE),
        )
    )


def _rich(state: GameState) -> GameState:
    return _resources(state, solari=6, spice=6)


def test_subcommittee_takes_the_turn_prompts_pick() -> None:
    state = _subcommittee_frame(_rich(_base()))
    run = _run(state)
    joinable = [str(_arg(a, "subcommittee_id")) for a in run.by_id("join_subcommittee")]
    assert len(joinable) > 1
    memory = Memory()
    key = (W.SUBCOMMITTEE_INTENT, state.round_number, ME)
    memory.intents[key] = joinable[-1]
    action = _decide(state, memory=memory)
    assert _arg(action, "subcommittee_id") == joinable[-1]
    assert key not in memory.intents


def test_subcommittee_without_intent_is_the_evaluator() -> None:
    state = _subcommittee_frame(_rich(_base()))
    joinable = [
        str(_arg(a, "subcommittee_id")) for a in _run(state).by_id("join_subcommittee")
    ]
    expected = sc.SubcommitteeEvaluator.evaluate(_fresh(state), joinable)
    action = _decide(state)
    assert action is not None
    if expected.response is None:
        assert action.action_id == "decline_subcommittee"
    else:
        assert _arg(action, "subcommittee_id") == _first(expected)


def test_subcommittee_declines_without_a_positive_line() -> None:
    state = _subcommittee_frame(_rich(_base()))
    run = _run(state)
    run.profile.scouts_item_line_value = lambda *_a, **_k: -1.0  # type: ignore[method-assign]
    action = W.scouts_subcommittee(run)
    assert action is not None and action.action_id == "decline_subcommittee"


# ---------------------------------------------------------------------------
# scouts_mission (§3.4)
# ---------------------------------------------------------------------------


def _escort(state: GameState) -> GameState:
    """CHOAM Escort with a supply troop and two own Contracts."""

    contracts = state.face_up_contract_ids
    state = with_state(state, face_up_contract_ids=())
    state = _me(state, active_contract_ids=contracts)
    return offer_mission_join(state, ME, "choam_escort", source=SOURCE).state


def test_mission_join_is_the_evaluator() -> None:
    state = _escort(_base())
    run = _run(state)
    targets = [str(_arg(a, "target")) for a in run.by_id("scouts_join_mission")]
    assert targets[0] == "recruit" and len(targets) == 3
    expected = sc.MissionJoinEvaluator.evaluate(_fresh(state), "choam_escort", targets)
    action = _decide(state)
    assert action is not None
    if expected.response is None:
        assert action.action_id == "scouts_decline_mission"
    else:
        assert (action.action_id, _arg(action, "target")) == expected.response[0]


def test_mission_declines_without_a_positive_join() -> None:
    state = _escort(_base())
    run = _run(state)
    run.profile.scouts_line_value = lambda *_a, **_k: Summer(-1.0)  # type: ignore[method-assign]
    action = W.scouts_mission(run)
    assert action is not None and action.action_id == "scouts_decline_mission"


def test_mission_top_up_then_joins_the_troop_way() -> None:
    """Weirding Warfare needs 2 supply troops; with 1 and specimens the
    top-up is the troop way, and the next decision joins (plan §4 rule 6)."""

    state = _resources(_base(), solari=4)
    state = _me(state, **_troops(supply=1, garrison=9, specimens=2))
    state = offer_mission_join(state, ME, "weirding_warfare", source=SOURCE).state
    run = _run(state)
    assert {a.action_id for a in run.legal} == {
        "scouts_decline_mission",
        "scouts_return_specimens",
    }
    run.profile.scouts_line_value = lambda *_a, **_k: Summer(50.0)  # type: ignore[method-assign]
    action = W.scouts_mission(run)
    assert action is not None and action.action_id == "scouts_return_specimens"
    assert _arg(action, "count") == 1
    key = (W.MISSION_JOIN_INTENT, state.round_number, "weirding_warfare", ME)
    assert run.memory.intents[key] == ""
    topped = ENGINE.apply(state, action).state
    assert topped.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION
    again = _run(topped, memory=run.memory)
    join = W.scouts_mission(again)
    assert join is not None and join.action_id == "scouts_join_mission"
    assert key not in run.memory.intents


# ---------------------------------------------------------------------------
# scouts_secret, scouts_bid (§3.6, §3.7)
# ---------------------------------------------------------------------------


def test_secret_pick_is_the_evaluator() -> None:
    state = offer_secret_pick(_base(), ME, "covert_operation", source=SOURCE).state
    expected = sc.SecretPickEvaluator.evaluate(
        _fresh(state), "covert_operation", [0, 1, 2, 3]
    )
    action = _decide(state)
    assert _arg(action, "pick") == _first(expected)


def _auction(state: GameState, auction_id: str) -> GameState:
    state = with_state(state, scouts_item=auction_id)
    return offer_bid(state, ME, auction_id, source=SOURCE).state


def test_sealed_bid_bids_then_confirms() -> None:
    state = _auction(_resources(_base(), solari=8), "spies_for_hire_mid")
    best = sc.SealedBidEvaluator.best_bid(_fresh(state), "spies_for_hire_mid", 8)
    assert best > 0
    first = _decide(state, rng_seed=1)
    assert first is not None and first.action_id == "scouts_bid"
    assert _arg(first, "count") == best
    placed = ENGINE.apply(state, first).state
    second = _decide(placed, rng_seed=7)
    assert second is not None and second.action_id == "confirm_scouts_bid"


def test_sealed_bid_without_surplus_confirms_zero() -> None:
    state = _auction(_resources(_base(), solari=8), "spies_for_hire_mid")
    run = _run(state)
    run.profile.scouts_item_line_value = lambda *_a, **_k: 0.0  # type: ignore[method-assign]
    action = W.scouts_bid(run)
    assert action is not None and action.action_id == "confirm_scouts_bid"


def test_mercenaries_bid_is_the_mercenaries_evaluator() -> None:
    state = _auction(_resources(_base(), spice=5), "mercenaries")
    run = _run(state)
    cap = max(int(str(_arg(a, "count"))) for a in run.by_id("scouts_bid"))
    best = sc.MercenariesBidEvaluator.best_bid(_fresh(state), cap)
    action = _decide(state)
    assert action is not None
    if best == 0:
        assert action.action_id == "confirm_scouts_bid"
    else:
        assert action.action_id == "scouts_bid" and _arg(action, "count") == best


# ---------------------------------------------------------------------------
# scouts_retreat, scouts_call, scouts_market, scouts_four_bonus (§3.8-3.11)
# ---------------------------------------------------------------------------


def test_retreat_is_get_troops_to_retreat() -> None:
    state = _me(_base(), **_troops(supply=6, garrison=3, conflict=3))
    state = offer_retreat(state, f"retreat:{ME}:3").state
    expected = min(_fresh(state).troops_to_retreat(3), 3)
    action = _decide(state)
    assert _arg(action, "count") == expected


def _market(state: GameState, auction_id: str = "critical_moment_mid") -> GameState:
    deck = state.imperium_deck
    return with_state(
        state,
        scouts_item=auction_id,
        imperium_deck=deck[2:],
        scouts_market_cards=deck[:2],
    )


def test_call_is_the_critical_moment_evaluator() -> None:
    state = _market(_resources(_base(), spice=6))
    state = offer_call(state, ME, source=SOURCE).state
    run = _run(state)
    amounts = [int(str(_arg(a, "count"))) for a in run.legal]
    expected = sc.CriticalMomentCallEvaluator.evaluate(_fresh(state), amounts)
    action = _decide(state)
    assert _arg(action, "count") == _first(expected)


def test_market_winner_takes_a_card() -> None:
    state = _market(_resources(_base(), spice=6))
    state = offer_take(state, f"take:{ME}:2:0").state
    expected = sc.CriticalMomentTakeEvaluator.evaluate(_fresh(state), [0, 1], 2, 0)
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_take_card"
    assert _arg(action, "slot") == _first(expected)


def test_market_second_place_declines_a_card_not_worth_its_call() -> None:
    state = _market(_resources(_base(), spice=6), "critical_moment_late")
    state = offer_take(state, f"take:{ME}:6:1").state
    run = _run(state)
    run.profile.acquire_to_hand_value = lambda *_a, **_k: 0.5  # type: ignore[method-assign]
    action = W.scouts_market(run)
    assert action is not None and action.action_id == "scouts_decline_card"


def test_four_bonus_is_the_evaluator() -> None:
    state = _base().push_decision(
        _frame(FrameKind.SCOUTS_FOUR_BONUS, ("reached", "fremen"), ("source", SOURCE))
    )
    expected = sc.FourBonusEvaluator.evaluate(_fresh(state), list(FACTIONS))
    action = _decide(state)
    assert _arg(action, "faction") == _first(expected)


# ---------------------------------------------------------------------------
# optional_trash from a Scouts line (§3.13)
# ---------------------------------------------------------------------------


def _water_discipline_trash() -> GameState:
    """Water Discipline's line run up to its optional trash icon."""

    state = push_scouts_effect(_base(), ME, "water_discipline", 0, source=SOURCE)
    while scouts_effect_can_advance(state):
        state = advance_scouts_effect(state).state
        if state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH:
            return state
    raise AssertionError("the trash icon never opened")


def test_scouts_trash_icon_is_the_lines_trash_ability() -> None:
    state = _water_discipline_trash()
    run = _run(state)
    source = str(run.ctx.top_frame_context["source"])
    from_scouts, ability = W.scouts_trash_source(run, source)
    assert from_scouts and isinstance(ability, TrashCustomAbility)
    assert ability.owner == scouts_line_entity("water_discipline", 0, ME)
    refs = [str(_arg(a, "card_id")) for a in run.by_id("trash_optional_card")]
    card, _ = _fresh(state).card_to_trash([card_entity(r, ME) for r in refs], 1.0)
    action = optional_trash(_run(state))
    assert action is not None
    if card is None:
        assert action.action_id == "decline_optional_trash"
    else:
        assert _arg(action, "card_id") == card.ref


def test_other_trash_sources_are_not_scouts_lines() -> None:
    state = _water_discipline_trash()
    run = _run(state)
    assert W.scouts_trash_source(run, "round:1:player:0:research:c3r3") == (
        False,
        None,
    )


# ---------------------------------------------------------------------------
# AppContext reads the Scouts state it was built on (plan §11.8)
# ---------------------------------------------------------------------------


def test_scouts_accessors_read_the_contexts_state() -> None:
    base = _base()
    view = ENGINE.observe(base, ME)
    goods = (("urban_surveillance", "post:imperial_basin", "solari", 1, -1),)
    cards = (
        ("emperors_schemes", "sardaukar", "intrigue:choam_profits:0"),
        ("emperors_schemes", "sardaukar", "intrigue:illicit_dealings:0"),
    )
    deck = tuple(
        c
        for c in base.intrigue_deck
        if c not in ("intrigue:choam_profits:0", "intrigue:illicit_dealings:0")
    )
    hypothetical = with_state(
        base,
        scouts_goods=goods,
        scouts_goods_cards=cards,
        intrigue_deck=deck,
        scouts_item="highest_bidder_mid",
        scouts_bids=((1, 5, False), (ME, 2, False)),
    )
    ctx = AppContext(hypothetical, ME, view)
    assert ctx.scouts_goods == goods
    assert ctx.scouts_board_card_counts == (("emperors_schemes", "sardaukar", 2),)
    assert ctx.scouts_item == "highest_bidder_mid"
    assert ctx.own_scouts_bid() == 2
    assert AppContext(base, ME, view).own_scouts_bid() == -1


# ---------------------------------------------------------------------------
# A whole game: every Scouts window answered by the app-style mirror
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [3])
def test_scouts_game_has_no_scouts_fallback(seed: int) -> None:
    agents = [AppAIAgent(seed=seed * 4 + s) for s in range(4)]
    run_policy_game(ENGINE, SCOUTS, seed, agents)
    fallbacks = {
        kind for agent in agents for kind in agent.fallbacks if kind in SCOUTS_KINDS
    }
    mirrored = {
        kind for agent in agents for kind in agent.mirrored if kind in SCOUTS_KINDS
    }
    assert not fallbacks
    assert {"scouts_choice", "scouts_bid"} <= mirrored


# ---------------------------------------------------------------------------
# Branches the first suite left unpinned (independent verification)
# ---------------------------------------------------------------------------


def _hand_run(state: GameState, legal: Sequence[DomainAction]) -> DecisionRun:
    """A run over hand-built legal actions (frames the engine cannot open)."""

    profile = _fresh(state)
    return DecisionRun(profile.ctx, profile, tuple(legal), profile.rng, Memory())


def _act(action_id: str, **arguments: ActionValue) -> DomainAction:
    return DomainAction(
        action_id=action_id, actor=ME, arguments=tuple(arguments.items())
    )


def test_mandatory_non_loss_item_without_a_positive_line_is_random() -> None:
    """Smoke and Mirrors is mandatory and not an Influence Reduction event:
    with no line worth more than 0 the answer is ``DefaultRandomChoice``
    over the offered lines (§3.1, D40), the evaluator's own draw."""

    state = _resources(_base(), solari=3)
    state = offer_scouts_choice(state, ME, "smoke_and_mirrors", source=SOURCE).state
    run = _run(state, rng_seed=5)
    assert [a.action_id for a in run.legal] == ["scouts_choose_option"] * 2
    run.profile.scouts_item_line_value = lambda *_a, **_k: -1.0  # type: ignore[method-assign]
    expected_profile = _fresh(state, rng_seed=5)
    expected_profile.scouts_item_line_value = lambda *_a, **_k: -1.0  # type: ignore[method-assign]
    expected = sc.ScoutsChoiceEvaluator.evaluate(
        expected_profile, "smoke_and_mirrors", [0, 1], passable=False
    )
    assert "DefaultRandomChoice" in expected.label
    action = W.scouts_choice(run)
    assert action is not None and _arg(action, "option") == _first(expected)


def test_recruit_to_conflict_top_up_returns_the_largest_count() -> None:
    """Shadow Warfare's recruit straight to the Conflict with an empty
    supply: the specimen top-up returns the whole shortfall (D39)."""

    state = _me(_base(), **_troops(supply=0, garrison=10, specimens=2))
    state = _effect(state, "shadow_warfare", 0, step=1)
    run = _run(state)
    assert [_arg(a, "count") for a in run.legal] == [0, 1]
    action = _decide(state)
    assert action is not None and action.action_id == "scouts_return_specimens"
    assert _arg(action, "count") == 1


def test_stale_subcommittee_intent_is_dropped_for_the_evaluator() -> None:
    """A stored pick that is no longer joinable is not forced through: the
    evaluator answers, and the intent is dropped (plan §4 rule 6)."""

    state = _subcommittee_frame(_rich(_base()))
    joinable = [
        str(_arg(a, "subcommittee_id")) for a in _run(state).by_id("join_subcommittee")
    ]
    stale = next(s for s in state.scouts_subcommittees if s not in joinable)
    memory = Memory()
    key = (W.SUBCOMMITTEE_INTENT, state.round_number, ME)
    memory.intents[key] = stale
    expected = sc.SubcommitteeEvaluator.evaluate(_fresh(state), joinable)
    action = _decide(state, memory=memory)
    assert key not in memory.intents
    assert action is not None
    if expected.response is None:
        assert action.action_id == "decline_subcommittee"
    else:
        assert _arg(action, "subcommittee_id") == _first(expected)


def test_mercenaries_bid_then_confirms() -> None:
    """The two Mercenaries steps agree without an intent (§3.7)."""

    state = _auction(_resources(_base(), spice=5), "mercenaries")
    first = _decide(state, rng_seed=2)
    assert first is not None
    if first.action_id == "confirm_scouts_bid":
        return  # b* = 0: one step
    placed = ENGINE.apply(state, first).state
    second = _decide(placed, rng_seed=9)
    assert second is not None and second.action_id == "confirm_scouts_bid"


def test_market_second_place_buys_a_card_worth_its_call() -> None:
    state = _market(_resources(_base(), spice=6), "critical_moment_late")
    state = offer_take(state, f"take:{ME}:1:1").state
    run = _run(state, rng_seed=4)
    assert {a.action_id for a in run.legal} == {
        "scouts_decline_card",
        "scouts_take_card",
    }
    expected_profile = _fresh(state, rng_seed=4)
    expected = sc.CriticalMomentTakeEvaluator.evaluate(expected_profile, [0, 1], 1, 1)
    assert expected.response is not None  # Spi(-1) leaves a revealed card > 0
    action = W.scouts_market(run)
    assert action is not None and action.action_id == "scouts_take_card"
    assert _arg(action, "slot") == _first(expected)


def test_scouts_line_trash_without_the_icon_falls_back() -> None:
    """An ``optional_trash`` frame granted by a Scouts line step that is not
    its optional trash icon has no line ability to answer it: counted
    fallback, never the generic answer (no silent default)."""

    state = _me(_base(), spy_post_ids=("arrakis-imperial-basin",), spies_supply=2)
    state = _effect(state, "oversight", 0, step=1)  # step 0 = the Spy recall
    state = state.push_decision(
        _frame(FrameKind.OPTIONAL_TRASH, ("player", ME), ("source", f"{SOURCE}:0"))
    )
    run = _run(state)
    assert W.scouts_trash_source(run, f"{SOURCE}:0") == (True, None)
    assert optional_trash(run) is None


def test_unrecognised_scouts_ids_fall_back() -> None:
    """Every window returns None (a counted fallback) for an item, auction,
    mission, event or step it has no archetype for, or an action id outside
    its own ids."""

    base = _base()
    hand = base.players[ME].hand

    effect = base.push_decision(
        _frame(
            FrameKind.SCOUTS_EFFECT,
            ("item", "not_an_item"),
            ("option", 0),
            ("player", ME),
            ("source", SOURCE),
            ("step", 0),
        )
    )
    discards = [_act("scouts_discard", card_id=c) for c in hand[:2]]
    assert W.scouts_effect(_hand_run(effect, discards)) is None

    mission = base.push_decision(
        _frame(FrameKind.SCOUTS_MISSION, ("mission_id", "not_a_mission"))
    )
    joins = [_act("scouts_decline_mission"), _act("scouts_join_mission", target="")]
    assert W.scouts_mission(_hand_run(mission, joins)) is None

    bids = [_act("confirm_scouts_bid"), _act("scouts_bid", count=0)]
    for auction_id in ("not_an_auction", "critical_moment_mid"):
        bid = base.push_decision(
            _frame(FrameKind.SCOUTS_BID, ("auction_id", auction_id))
        )
        assert W.scouts_bid(_hand_run(bid, bids)) is None

    secret = base.push_decision(
        _frame(FrameKind.SCOUTS_SECRET, ("event_id", "private_stock"))
    )
    picks = [_act("scouts_secret_pick", pick=k) for k in range(4)]
    assert W.scouts_secret(_hand_run(secret, picks)) is None

    market = _market(_resources(base, spice=6))
    unknown = with_state(
        market,
        scouts_market_cards=("imperium:not_a_card:0", *market.scouts_market_cards),
    )
    call = offer_call(unknown, ME, source=SOURCE).state
    calls = [_act("scouts_call", count=k) for k in range(3)]
    assert W.scouts_call(_hand_run(call, calls)) is None

    choice = offer_scouts_choice(
        _resources(base, spice=6, solari=6), ME, "secrets_for_sale", source=SOURCE
    ).state
    foreign = (*_run(choice).legal, _act("finish_agent_turn"))
    assert W.scouts_choice(_hand_run(choice, foreign)) is None


def test_scouts_answers_ignore_hidden_information() -> None:
    """Every Scouts window answers the same when ``determinize`` re-deals
    what the seat cannot see: other seats' secret picks and sealed bids, the
    face-down mission cards, hands, decks (plan §4 rule 8)."""

    config = RulesetConfig(choam_module=True, immortality=True, arrakeen_scouts=True)
    agents = [AppAIAgent(seed=300 + seat) for seat in range(4)]
    state = ENGINE.reset(config, 6)
    chance = ChanceResolver(seed=6)
    rng = random.Random(11)
    checked: set[str] = set()
    while state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        actions = ENGINE.legal_actions(state, seat)
        view = ENGINE.observe(state, seat)
        kind = str(view.decision_kind)
        if kind in SCOUTS_KINDS and len(actions) > 1:
            twin = determinize(state, seat, rng)
            assert ENGINE.observe(twin, seat) == view
            on_twin = copy.deepcopy(agents[seat]).choose_action_with_state(
                twin, view, actions
            )
            real = copy.deepcopy(agents[seat]).choose_action_with_state(
                state, view, actions
            )
            assert on_twin == real, kind
            checked.add(kind)
        action = agents[seat].choose_action_with_state(state, view, actions)
        state = ENGINE.apply(state, action, legal_actions=actions).state
    assert {"scouts_choice", "scouts_bid", "scouts_mission"} <= checked
