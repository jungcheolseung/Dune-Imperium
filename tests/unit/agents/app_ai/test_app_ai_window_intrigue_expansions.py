"""The app_ai Intrigue windows with the Immortality intrigues
(``windows/intrigue.py``): requests, Plot keys, the follow-up slots and the
research direction a play's answer names.

Real Immortality games (``testing.play_until`` / ``first_decision``); the
played card is put in the seat's hand (taken out of the Intrigue deck) and
the engine's own frames follow.
"""

import random
from collections import Counter
from collections.abc import Callable
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai import agent as agent_module
from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.immortality import (
    BreakthroughAbility,
    DisguisedBureaucratAbility,
    HarvestCellsAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    intrigue_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.profile.immortality import research_space_entity
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    play_until,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import intrigue as W
from dune_imperium.agents.app_ai.windows import reveal
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import frame_context, replace_top_frame, with_context
from dune_imperium.simulation.runner import run_policy_game

IMMORTALITY = RulesetConfig(immortality=True, choam_module=True)
#: Research spaces with two rightward neighbours: before the first marker
#: (column 1), and past it (column 4).
TWO_WAYS = "c1r3"
ONE_MARKER = "c4r2"
TWO_MARKERS = "c8r2"


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _legal(state: GameState) -> tuple[DomainAction, ...]:
    return ENGINE.legal_actions(state, _seat(state))


def _run(state: GameState, memory: Memory | None = None) -> DecisionRun:
    seat = _seat(state)
    profile = make_profile(state, seat)
    return DecisionRun(
        profile.ctx, profile, _legal(state), profile.rng, memory or Memory()
    )


def _find(state: GameState, action_id: str, **args: object) -> DomainAction:
    for action in _legal(state):
        if action.action_id == action_id and all(
            dict(action.arguments).get(k) == v for k, v in args.items()
        ):
            return action
    raise AssertionError(f"{action_id} {args} is not legal")


def _apply(state: GameState, action: DomainAction) -> GameState:
    return ENGINE.apply(state, action, legal_actions=_legal(state)).state


def _holding(
    state: GameState, seat: int, *instances: str, **changes: object
) -> GameState:
    """``seat`` holds exactly ``instances`` (taken out of every other zone)."""

    players = state.players
    for other in players:
        if other.player_id != seat and set(other.intrigue_cards) & set(instances):
            state = with_player(
                state,
                other.player_id,
                intrigue_cards=tuple(
                    i for i in other.intrigue_cards if i not in instances
                ),
            )
    state = with_state(
        state,
        intrigue_deck=tuple(i for i in state.intrigue_deck if i not in instances),
        intrigue_discard=tuple(i for i in state.intrigue_discard if i not in instances),
    )
    return with_player(state, seat, intrigue_cards=tuple(instances), **changes)


def _turn(*instances: str, **changes: object) -> GameState:
    """Seat 0's first turn-start prompt of an Immortality game, holding
    ``instances``."""

    state = first_decision("turn", config=IMMORTALITY, seed=3)
    return _holding(state, _seat(state), *instances, **changes)


def _play_source(state: GameState, instance: str, memory: Memory) -> DomainAction:
    """The Plot key of ``instance`` (the turn-start prompt): its action."""

    run = _run(state, memory)
    plays = [a for a in run.by_id("play_intrigue") if arg(a, "card_id") == instance]
    (source,) = W.intrigue_play_sources(run, plays, combat=False)
    assert source.evaluate is not None
    _value, action = source.evaluate()
    assert action is not None
    return action


# ===========================================================================
# Requests
# ===========================================================================


def test_requests_of_the_immortality_intrigues() -> None:
    state = _turn(
        research_space=TWO_WAYS,
        specimens=1,
        troops_supply=8,
    )
    ctx = _run(state).ctx
    breakthrough = W.intrigue_request(ctx, "intrigue:breakthrough:0", False)
    assert [e.ref for e in breakthrough.infos[0].entities] == [
        "research:c2r2",
        "research:c2r4",
    ]
    counterattack = W.intrigue_request(ctx, "intrigue:counterattack:0", False)
    assert counterattack.infos[0].options == (0, 1, 2)
    assert W.intrigue_request(ctx, "intrigue:counterattack:0", True).infos == ()
    bureaucrat = W.intrigue_request(ctx, "intrigue:disguised_bureaucrat:0", False)
    assert [e.ref for e in bureaucrat.infos[0].entities] == list(FACTIONS)
    harvest = W.intrigue_request(ctx, "intrigue:harvest_cells:0", True)
    row = [
        i for i in state.tleilaxu_row if card_entity(i).int_attr("SpecimenCost") <= 3
    ]
    assert [e.ref for e in harvest.infos[0].entities] == row


# ===========================================================================
# Plot keys and their follow-ups
# ===========================================================================


def test_breakthrough_key_plays_and_names_the_research_space() -> None:
    instance = "intrigue:breakthrough:0"
    state = _turn(instance, research_space=TWO_WAYS)
    memory = Memory()
    run = _run(state, memory)
    plays = [a for a in run.by_id("play_intrigue") if arg(a, "card_id") == instance]
    (source,) = W.intrigue_play_sources(run, plays, combat=False)
    assert source.evaluate is not None
    value, action = source.evaluate()
    ability = BreakthroughAbility(intrigue_entity(instance, 0))
    spaces = tuple(research_space_entity(s) for s in ("c2r2", "c2r4"))
    answer = ability.evaluate(run.profile, Request((TargetInfo(entities=spaces),)))
    assert value == answer.value
    assert action == _find(state, "play_intrigue", card_id=instance, option=0)
    assert answer.response is not None
    named = str(answer.response[0][0]).removeprefix("research:")
    state = _apply(state, action)
    assert state.decision_stack[-1].kind == "research_advance"
    assert W.research_intent(_run(state, memory)) == named


def test_research_intent_of_a_reveal_research_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reveal, "intrigue_play_sources", lambda run, actions, combat: []
    )
    state = first_decision("turn", config=IMMORTALITY, seed=3)
    state = with_player(
        state, 0, hand=("imperium:tleilaxu_master:0",), research_space=TWO_WAYS
    )
    state = _apply(state, _find(state, "reveal_turn"))
    memory = Memory()
    action = reveal.reveal_window(_run(state, memory))
    assert action == _find(state, "advance_reveal_research")
    key = (W.RESEARCH_INTENT, state.round_number, 0)
    stored = memory.intents[key]
    state = _apply(state, action)
    assert state.decision_stack[-1].kind == "research_advance"
    assert W.research_intent(_run(state, memory)) == stored
    assert key not in memory.intents


def test_research_intent_replays_only_a_breakthrough_answer() -> None:
    """Another Intrigue's Research (e.g. the Research acquire effect of a
    card Impress bought) opens the frame with that Intrigue in its source:
    its recorded answer names a card, never a research space, and is not
    replayed even when its first ref happens to be one of the spaces."""

    instance = "intrigue:breakthrough:0"
    state = _turn(instance, research_space=TWO_WAYS)
    memory = Memory()
    state = _apply(state, _play_source(state, instance, memory))
    frame = state.decision_stack[-1]
    assert frame.kind == "research_advance"
    other = "intrigue:impress:0"
    context = frame_context(frame)
    context["source"] = str(context["source"]).replace(instance, other)
    seat = _seat(state)
    played = GameEvent(
        event_id="test:impress:played",
        kind="intrigue_played",
        payload=(("card_id", other), ("player", seat)),
    )
    state = with_state(
        replace_top_frame(state, with_context(frame, context)),
        event_log=(*state.event_log, played),
    )
    space = str(arg(_legal(state)[0], "space_id"))
    memory = Memory()
    memory.intents[(W.INTENT, other)] = Answer(9.0, ((f"research:{space}",),))
    memory.intents[(W.INTENT_AT, other)] = len(state.event_log) - 1
    assert W.recorded_answer(_run(state, memory), other) is not None
    assert W.research_intent(_run(state, memory)) is None


def test_research_intent_is_none_for_another_source() -> None:
    state = play_until(
        lambda s, owner: s.decision_stack[-1].kind == "research_advance",
        config=IMMORTALITY,
        seed=1,
    )
    source = str(dict(state.decision_stack[-1].context)["source"])
    if ":intrigue:intrigue:" in source or ":reveal_gain:" in source:
        pytest.skip("this research came from an answer-carrying source")
    memory = Memory()
    memory.intents[(W.RESEARCH_INTENT, state.round_number, _seat(state))] = "c2r2"
    assert W.research_intent(_run(state, memory)) is None


def test_disguised_bureaucrat_gains_on_the_answer_track() -> None:
    instance = "intrigue:disguised_bureaucrat:0"
    state = _turn(instance, research_space=TWO_MARKERS)
    memory = Memory()
    action = _play_source(state, instance, memory)
    run = _run(state, memory)
    tracks = tuple(
        track_entity(f) for f in FACTIONS if getattr(run.ctx.me.influence, f) <= 5
    )
    answer = DisguisedBureaucratAbility(intrigue_entity(instance, 0)).evaluate(
        run.profile, Request((TargetInfo(entities=tracks),))
    )
    assert answer.response is not None
    state = _apply(state, action)
    while state.decision_stack[-1].kind == "intrigue_choice" and not any(
        a.action_id == "choose_intrigue_faction" for a in _legal(state)
    ):
        state = _apply(state, _legal(state)[0])
    assert W.intrigue_choice(_run(state, memory)) == _find(
        state, "choose_intrigue_faction", faction=answer.response[0][0]
    )


@pytest.mark.parametrize("units", [(0,), (0, 1)])
def test_counterattack_deploys_the_answer_units(units: tuple[int, ...]) -> None:
    instance = "intrigue:counterattack:0"
    state = _turn(instance)
    memory = Memory()
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=0))
    assert state.decision_stack[-1].kind == "intrigue_choice"
    run = _run(state, memory)
    played_at = W._play_event_index(run.ctx, instance)
    memory.intents[(W.INTENT, instance)] = Answer(10.0, (units,))
    memory.intents[(W.INTENT_AT, instance)] = played_at
    action = W.intrigue_choice(_run(state, memory))
    assert action is not None and action.action_id == "deploy_intrigue_troops"
    assert arg(action, "count") == len(units)


# ===========================================================================
# Combat intrigues
# ===========================================================================


@cache
def _combat_turn() -> GameState:
    return play_until(
        lambda s, owner: s.decision_stack[-1].kind == "combat_intrigue",
        config=IMMORTALITY,
        seed=1,
    )


def test_gruesome_sacrifice_loses_conflict_troops() -> None:
    instance = "intrigue:gruesome_sacrifice:0"
    state = _combat_turn()
    seat = _seat(state)
    me = state.players[seat]
    state = _holding(
        state,
        seat,
        instance,
        troops_conflict=me.troops_conflict + 2,
        troops_supply=me.troops_supply - 2,
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance))
    assert state.decision_stack[-1].kind == "intrigue_choice"
    run = _run(state)
    assert W.intrigue_choice(run) == _find(
        state, "lose_intrigue_troop", zone="conflict"
    )


def test_gruesome_sacrifice_loses_a_commander_only_without_a_troop() -> None:
    """With Bloodlines a Sardaukar Commander may stand in for a troop: the
    plain troop is lost while one is in the Conflict, then the Commander."""

    instance = "intrigue:gruesome_sacrifice:0"
    state = play_until(
        lambda s, owner: s.decision_stack[-1].kind == "combat_intrigue",
        config=RulesetConfig(immortality=True, bloodlines=True),
        seed=1,
    )
    seat = _seat(state)
    me = state.players[seat]
    state = _holding(
        state,
        seat,
        instance,
        troops_conflict=1,
        commanders_conflict=1,
        troops_supply=me.troops_supply + me.troops_conflict - 1,
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance))
    troop = _find(state, "lose_intrigue_troop", zone="conflict")
    assert arg(troop, "commanders") is None
    assert W.intrigue_choice(_run(state)) == troop
    state = _apply(state, troop)
    assert state.decision_stack[-1].kind == "intrigue_choice"
    commander = _find(state, "lose_intrigue_troop", zone="conflict", commanders=1)
    assert W.intrigue_choice(_run(state)) == commander


def test_another_lose_troops_cost_is_not_mirrored() -> None:
    """Only Gruesome Sacrifice's ``LoseTroops`` cost has an app answer."""

    instance = "intrigue:gruesome_sacrifice:0"
    state = _combat_turn()
    seat = _seat(state)
    me = state.players[seat]
    state = _holding(
        state,
        seat,
        instance,
        troops_conflict=me.troops_conflict + 2,
        troops_supply=me.troops_supply - 2,
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance))
    run = _run(state)
    assert W._lose_troops(run, "gruesome_sacrifice") is not None
    assert W._lose_troops(run, "some_bloodlines_card") is None


def test_immortality_combat_intrigues_are_intrigue_keys() -> None:
    cards = ("intrigue:vicious_talents:0", "intrigue:gruesome_sacrifice:0")
    state = _combat_turn()
    seat = _seat(state)
    me = state.players[seat]
    state = _holding(
        state,
        seat,
        *cards,
        troops_conflict=me.troops_conflict + 2,
        troops_supply=me.troops_supply - 2,
    )
    run = _run(state)
    sources = W.intrigue_play_sources(run, run.by_id("play_intrigue"), combat=True)
    assert sorted(s.label for s in sources) == sorted(f"intrigue {c}" for c in cards)


# ===========================================================================
# Harvest Cells' acquisition at the Conflict's end
# ===========================================================================


@cache
def _harvest_frame() -> GameState:
    """Seed 6, round 4: seat 3's face-up Harvest Cells fires."""

    def predicate(state: GameState, owner: int) -> bool:
        frame = state.decision_stack[-1]
        card = str(dict(frame.context).get("card_id", ""))
        return frame.kind == "intrigue_choice" and card.startswith(
            "intrigue:harvest_cells"
        )

    return play_until(predicate, config=RulesetConfig(immortality=True), seed=6)


def _harvest(**changes: object) -> tuple[GameState, str]:
    state = _harvest_frame()
    seat = _seat(state)
    me = state.players[seat]
    specimens = int(str(changes.pop("specimens", me.specimens)))
    state = with_player(
        state,
        seat,
        specimens=specimens,
        troops_supply=me.troops_supply + me.specimens - specimens,
        **changes,
    )
    instance = str(dict(state.decision_stack[-1].context)["card_id"])
    return state, instance


def test_harvest_cells_takes_the_specimens_first() -> None:
    state, _instance = _harvest()
    run = _run(state)
    assert {a.action_id for a in run.legal} >= {"resolve_intrigue_rewards"}
    assert W.intrigue_choice(run) == _find(state, "resolve_intrigue_rewards")


def test_harvest_cells_acquires_the_card_its_evaluate_names() -> None:
    state, instance = _harvest(specimens=2)
    state = _apply(state, _find(state, "resolve_intrigue_rewards"))
    run = _run(state)
    offered = [
        str(arg(a, "instance_id")) for a in run.by_id("acquire_intrigue_tleilaxu")
    ]
    assert offered
    ability = HarvestCellsAbility(intrigue_entity(instance, run.ctx.seat))
    cards = tuple(card_entity(i) for i in dict.fromkeys(offered))
    answer = ability.evaluate(run.profile, Request((TargetInfo(cards),)))
    action = W.intrigue_choice(run)
    if answer.response and answer.response[0]:
        assert action == _find(
            state, "acquire_intrigue_tleilaxu", instance_id=answer.response[0][0]
        )
    else:
        assert action == _find(state, "decline_intrigue_tleilaxu")


def test_harvest_cells_replays_the_recorded_answer_on_top_of_the_deck() -> None:
    state, instance = _harvest(specimens=2, research_space=ONE_MARKER)
    state = _apply(state, _find(state, "resolve_intrigue_rewards"))
    run = _run(state)
    offered = list(
        dict.fromkeys(
            str(arg(a, "instance_id")) for a in run.by_id("acquire_intrigue_tleilaxu")
        )
    )
    memory = Memory()
    memory.intents[(W.INTENT, instance)] = Answer(9.0, ((offered[-1],),))
    memory.intents[(W.INTENT_AT, instance)] = W._play_event_index(run.ctx, instance)
    action = W.intrigue_choice(_run(state, memory))
    assert action == _find(
        state, "acquire_intrigue_tleilaxu", instance_id=offered[-1], to_deck_top=True
    )


def test_harvest_cells_reevaluates_when_the_recorded_card_is_gone() -> None:
    """The recorded answer names a card no longer offered: the ability is
    evaluated again over the offered cards."""

    state, instance = _harvest(specimens=2)
    state = _apply(state, _find(state, "resolve_intrigue_rewards"))
    run = _run(state)
    offered = list(
        dict.fromkeys(
            str(arg(a, "instance_id")) for a in run.by_id("acquire_intrigue_tleilaxu")
        )
    )
    memory = Memory()
    memory.intents[(W.INTENT, instance)] = Answer(9.0, (("tleilaxu:gone:0",),))
    memory.intents[(W.INTENT_AT, instance)] = W._play_event_index(run.ctx, instance)
    ability = HarvestCellsAbility(intrigue_entity(instance, run.ctx.seat))
    cards = tuple(card_entity(i) for i in offered)
    answer = ability.evaluate(run.profile, Request((TargetInfo(cards),)))
    action = W.intrigue_choice(_run(state, memory))
    if answer.response and answer.response[0]:
        assert action == _find(
            state, "acquire_intrigue_tleilaxu", instance_id=answer.response[0][0]
        )
    else:
        assert action == _find(state, "decline_intrigue_tleilaxu")


def test_harvest_cells_recorded_no_acquire_declines() -> None:
    state, instance = _harvest(specimens=2)
    state = _apply(state, _find(state, "resolve_intrigue_rewards"))
    run = _run(state)
    memory = Memory()
    memory.intents[(W.INTENT, instance)] = Answer(2.0, ((),))
    memory.intents[(W.INTENT_AT, instance)] = W._play_event_index(run.ctx, instance)
    assert W.intrigue_choice(_run(state, memory)) == _find(
        state, "decline_intrigue_tleilaxu"
    )


# ===========================================================================
# Full games
# ===========================================================================


@pytest.mark.parametrize(
    "options",
    [
        {"immortality": True},
        {"immortality": True, "go_to_11": True, "epic_game": True},
    ],
)
def test_option_games_never_fall_back_in_the_intrigue_windows(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, bool]
) -> None:
    """Four app_ai seats with only this module's handlers installed (every
    other window answers at random): no ``intrigue_choice`` /
    ``intrigue_effects`` decision falls back."""

    def only_intrigue(kind: str | None) -> Callable[[DecisionRun], object] | None:
        return None if kind is None else W.HANDLERS.get(kind)

    monkeypatch.setattr(agent_module, "handler_for", only_intrigue)
    mirrored: Counter[str] = Counter()
    for game in range(3):
        choam = game % 2 == 1
        seed = 90 + game
        leaders = tuple(
            random.Random(seed).sample(
                [leader.leader_id for leader in leaders_for_choam(choam)], k=4
            )
        )
        agents = tuple(AppAIAgent(seed=900 + 10 * game + seat) for seat in range(4))
        result = run_policy_game(
            UprisingRulesEngine(leader_ids=leaders),
            RulesetConfig(choam_module=choam, **options),
            seed,
            agents,
        )
        assert result.state.phase is GamePhase.FINISHED
        for agent in agents:
            for kind in W.HANDLERS:
                assert agent.fallbacks[kind] == 0, (game, kind)
                mirrored[kind] += agent.mirrored[kind]
    assert sum(mirrored.values()) > 0, mirrored
