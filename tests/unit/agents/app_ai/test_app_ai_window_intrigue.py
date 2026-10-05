"""Intrigue plays and the ``intrigue_choice`` / ``intrigue_effects`` windows.

Every follow-up test plays the card for real: the app's answer is fixed by
patching the card's ability ``evaluate``, ``intrigue_play_sources`` maps it
to a ``play_intrigue`` action and records the intent, the engine applies the
play, and the window handler must replay the answer (or ask the app's own
evaluator) on the resulting frame.
"""

import random
from collections import Counter
from collections.abc import Callable
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai import agent as agent_module
from dune_imperium.agents.app_ai.abilities import intrigue as I
from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    contract_entity,
    intrigue_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.choice import Candidate, make_choice
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    play_until,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import intrigue as W
from dune_imperium.agents.app_ai.windows.common import Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler, Memory
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.acquisition import acquirable_imperium_instance_ids
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

SEAT = 3  # the deciding seat of every fixture below (seed 1)
CITY = (
    "arrakis-research-station-sietch-tabr",
    "arrakis-research-station-spice-refinery",
    "arrakis-spice-refinery-arrakeen",
)
POST_A = "emperor-sardaukar-dutiful-service"
POST_B = "spacing-guild-heighliner-deliver-supplies"
POST_C = "bene-gesserit-espionage-secrets"


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 3's first ``turn`` (round 1, CHOAM on, wall standing, 3 garrison)."""

    return first_decision("turn")


@pytest.fixture(scope="module")
def combat_state() -> GameState:
    """Seat 3's first ``combat_intrigue`` (3 troops in the Conflict)."""

    return first_decision("combat_intrigue")


@pytest.fixture(scope="module")
def endgame_state() -> GameState:
    """Seat 3's ``endgame_intrigue`` (won Conflicts with Crysknife icons)."""

    return play_until(lambda s, o: s.decision_stack[-1].kind == "endgame_intrigue")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def iid(name: str) -> str:
    return name if ":" in name else f"intrigue:{name}:0"


def give(state: GameState, *names: str, **changes: Any) -> GameState:
    """Seat 3 holds exactly ``names`` (taken out of every other zone)."""

    held = tuple(iid(n) for n in names)
    state = with_state(
        state,
        intrigue_deck=tuple(i for i in state.intrigue_deck if i not in held),
        intrigue_discard=tuple(i for i in state.intrigue_discard if i not in held),
    )
    for seat in range(4):
        if seat != SEAT:
            cards = state.players[seat].intrigue_cards
            state = with_player(
                state, seat, intrigue_cards=tuple(i for i in cards if i not in held)
            )
    return with_player(state, SEAT, intrigue_cards=held, **changes)


def act(action_id: str, **arguments: ActionValue) -> DomainAction:
    return DomainAction(
        action_id=action_id, actor=SEAT, arguments=tuple(sorted(arguments.items()))
    )


def make_run(
    state: GameState,
    memory: Memory | None = None,
    legal: tuple[DomainAction, ...] | None = None,
    **stubs: Callable[..., Any],
) -> DecisionRun:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == SEAT
    if legal is None:
        legal = ENGINE.legal_actions(state, SEAT)
    ctx = AppContext(state, SEAT, ENGINE.observe(state, SEAT))
    profile = Profile(ctx, TABLES[2], random.Random(0))
    for name, fn in stubs.items():
        setattr(profile, name, fn)
    return DecisionRun(ctx, profile, legal, random.Random(0), memory or Memory())


def fix_answer(
    monkeypatch: pytest.MonkeyPatch, name: str, answer: Answer, combat: bool = False
) -> list[Request]:
    """Make the card's prompt ability answer ``answer``; returns the requests."""

    ability = I.ability_for_prompt(intrigue_entity(iid(name), SEAT), combat)
    assert ability is not None
    seen: list[Request] = []

    def evaluate(self: object, p: Profile, request: Request) -> Answer:
        seen.append(request)
        return answer

    monkeypatch.setattr(type(ability), "evaluate", evaluate)
    return seen


def app_play(
    state: GameState,
    memory: Memory,
    name: str,
    *,
    combat: bool = False,
    **stubs: Callable[..., Any],
) -> GameState:
    """Play ``name`` the way the app answered (``intrigue_play_sources``)."""

    run = make_run(state, memory, None, **stubs)
    sources = W.intrigue_play_sources(run, run.legal, combat=combat)
    source = next(s for s in sources if s.label == f"intrigue {iid(name)}")
    assert source.evaluate is not None
    _, action = source.evaluate()
    assert action is not None
    return ENGINE.apply(state, action, legal_actions=run.legal).state


def step(state: GameState, action: DomainAction) -> GameState:
    legal = ENGINE.legal_actions(state, SEAT)
    assert action in legal, (action, legal)
    return ENGINE.apply(state, action, legal_actions=legal).state


def kind(state: GameState) -> str:
    return state.decision_stack[-1].kind


def g_values(**values: float) -> Callable[..., Summer]:
    return lambda f, n, rank=-1, alliance=False: Summer(values.get(f, 0.0) * n)


def swap_pick(memory: Memory) -> tuple[float, Any]:
    """Change Allegiances' recorded swap gain pick: (value, response)."""

    answer = memory.intents[(W.INTENT_SWAP_GAIN, iid("change_allegiances"))]
    assert isinstance(answer, Answer)
    return answer.value, answer.response


# ---------------------------------------------------------------------------
# intrigue_play_sources
# ---------------------------------------------------------------------------


def test_handlers_are_registered() -> None:
    assert W.HANDLERS == {
        "intrigue_choice": W.intrigue_choice,
        "intrigue_effects": W.intrigue_effects,
    }


def test_sources_one_per_card_values_actions_and_intents(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state,
        "market_opportunity",
        "imperium_politics",
        "contingency_plan",
        "call_to_arms",
        resources=Resources(solari=6, spice=3, water=1),
    )
    fix_answer(monkeypatch, "market_opportunity", Answer(7.0, ((1,),)))
    fix_answer(monkeypatch, "imperium_politics", Answer(12.0, (("spacing_guild",),)))
    fix_answer(monkeypatch, "contingency_plan", Answer(0.0, None))
    fix_answer(monkeypatch, "call_to_arms", Answer(100.0, ()))
    memory = Memory()
    run = make_run(state, memory)
    sources = W.intrigue_play_sources(run, run.legal, combat=False)
    assert [s.label for s in sources] == [
        f"intrigue {iid(n)}"
        for n in (
            "market_opportunity",
            "imperium_politics",
            "contingency_plan",
            "call_to_arms",
        )
    ]
    assert all(s.stage is Stage.PROMPT for s in sources)
    assert sources[0].actions == (
        act("play_intrigue", card_id=iid("market_opportunity"), option=0),
        act("play_intrigue", card_id=iid("market_opportunity"), option=1),
    )
    results = [s.evaluate() for s in sources if s.evaluate is not None]
    assert results == [
        (7.0, act("play_intrigue", card_id=iid("market_opportunity"), option=1)),
        (12.0, act("play_intrigue", card_id=iid("imperium_politics"), option=0)),
        (0.0, None),
        (100.0, act("play_intrigue", card_id=iid("call_to_arms"), option=0)),
    ]
    assert memory.intents[("intrigue", iid("imperium_politics"))] == Answer(
        12.0, (("spacing_guild",),)
    )
    assert memory.intents[("intrigue_at", iid("imperium_politics"))] == len(
        state.event_log
    )


def test_sources_skip_cards_the_app_cannot_run(turn_state: GameState) -> None:
    # Imperium Politics' app Cost needs Emperor < 6 or Guild < 6; ours only 1 Solari.
    state = give(
        turn_state,
        "imperium_politics",
        "contingency_plan",
        resources=Resources(solari=1, spice=0, water=1),
        influence=Influence(emperor=6, spacing_guild=6),
    )
    run = make_run(state)
    play = act("play_intrigue", card_id=iid("imperium_politics"), option=0)
    assert play in run.legal
    sources = W.intrigue_play_sources(run, run.legal, combat=False)
    assert [s.label for s in sources] == [f"intrigue {iid('contingency_plan')}"]


def test_combat_sources_use_the_combat_half(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(combat_state, "contingency_plan")
    seen = fix_answer(monkeypatch, "contingency_plan", Answer(4.0, ()), combat=True)
    run = make_run(state)
    (source,) = W.intrigue_play_sources(run, run.legal, combat=True)
    assert source.evaluate is not None
    assert source.evaluate() == (
        4.0,
        act("play_intrigue", card_id=iid("contingency_plan"), option=1),
    )
    assert seen == [Request(())]


def test_an_answer_on_an_illegal_option_has_no_action(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 2 spice, 3 Solari: only option 0 (pay 2 spice) is legal.
    state = give(
        turn_state, "market_opportunity", resources=Resources(solari=3, spice=2)
    )
    fix_answer(monkeypatch, "market_opportunity", Answer(3.0, ((1,),)))
    run = make_run(state)
    (source,) = W.intrigue_play_sources(run, run.legal, combat=False)
    assert source.evaluate is not None
    assert source.evaluate() == (3.0, None)


def test_sources_skip_cards_without_an_app_prompt_ability(
    turn_state: GameState,
) -> None:
    run = make_run(turn_state)
    unknown = act("play_intrigue", card_id="intrigue:not_an_app_card:0", option=0)
    # An Endgame-only card has no ability matching a Combat prompt.
    endgame = act("play_intrigue", card_id=iid("choam_profits"), option=0)
    assert W.intrigue_play_sources(run, (unknown,), combat=False) == []
    assert W.intrigue_play_sources(run, (endgame,), combat=True) == []


def _option(name: str, request: Request, answer: Answer, combat: bool) -> int | None:
    return W._answer_option(iid(name), request, answer, combat)


def test_answer_option_mapping() -> None:
    both = Request((TargetInfo((), (0, 1)), TargetInfo((), (0, 1, 2))))
    one = Request((TargetInfo((), (0, 1, 2)),))
    empty = Request(())
    assert _option("cunning", empty, Answer(2.0, ((1,),)), False) == 1
    assert _option("cunning", empty, Answer(2.0, ((0,),)), False) == 0
    assert _option("market_opportunity", empty, Answer(1.0, ((1,),)), False) == 1
    assert _option("spice_is_power", empty, Answer(150.0, ((0,),)), True) == 0
    assert _option("spice_is_power", empty, Answer(5.0, ((1,),)), True) == 1
    assert _option("spice_is_power", empty, Answer(5.0, ((2,),)), True) is None
    assert _option("tactical_option", both, Answer(150.0, ((1,), (0,))), True) == 1
    assert _option("tactical_option", both, Answer(3.0, ((0,),)), True) == 0
    assert _option("detonation", both, Answer(100.0, ((0,),)), False) == 0
    assert _option("detonation", both, Answer(100.0, ((1,), (0, 1))), False) == 1
    assert _option("detonation", one, Answer(100.0, ((0,),)), False) == 1
    spies = Request((TargetInfo((), (0, 1)), TargetInfo(())))
    assert _option("special_mission", spies, Answer(2.0, ()), False) == 0
    assert _option("special_mission", spies, Answer(2.0, ((0,),)), False) == 0
    assert _option("special_mission", spies, Answer(4.0, ((1,), (POST_A,))), False) == 1
    recall_only = Request((TargetInfo(()),))
    assert (
        _option("special_mission", recall_only, Answer(4.0, ((POST_A,),)), False) == 1
    )
    assert _option("backed_by_choam", empty, Answer(101.0, (("fremen",),)), False) == 0
    assert _option("backed_by_choam", empty, Answer(10.0, ()), True) == 1
    assert _option("crysknife", empty, Answer(100.0, ()), False) == 0
    assert _option("weirding_combat", empty, Answer(9.0, ()), True) == 0
    assert _option("weirding_combat", empty, Answer(0.0, None), True) is None


def test_requests_name_the_targets_each_ability_reads(turn_state: GameState) -> None:
    state = give(
        turn_state,
        influence=Influence(emperor=1, spacing_guild=0, bene_gesserit=2, fremen=6),
        spy_post_ids=(POST_A, POST_B),
        spies_supply=1,
        troops_conflict=2,
        troops_garrison=1,
    )
    ctx = AppContext(state, SEAT, ENGINE.observe(state, SEAT))
    me = state.players[SEAT]

    def req(name: str, combat: bool = False) -> tuple[TargetInfo, ...]:
        return W.intrigue_request(ctx, iid(name), combat).infos

    def tracks(*fs: str) -> TargetInfo:
        return TargetInfo(tuple(track_entity(f) for f in fs))

    def opts(*o: int) -> TargetInfo:
        return TargetInfo((), o)

    lose = tracks("emperor", "bene_gesserit", "fremen")
    for name in ("change_allegiances", "opportunism", "questionable_methods"):
        assert req(name, name == "questionable_methods") == (lose,)
    assert req("backed_by_choam") == (lose,)
    assert req("backed_by_choam", True) == ()
    assert req("buy_access") == (tracks("emperor", "spacing_guild", "bene_gesserit"),)
    assert req("imperium_politics") == (tracks("emperor", "spacing_guild"),)
    hand = TargetInfo(tuple(card_entity(i, SEAT) for i in me.hand))
    assert req("sietch_ritual") == (hand, tracks("bene_gesserit"))
    row3 = acquirable_imperium_instance_ids(state, 3)
    assert req("impress", True) == (
        TargetInfo(
            (
                *(card_entity(i) for i in row3),
                card_entity("reserve:prepare_the_way"),
            )
        ),
    )
    assert req("inspire_awe") == req("impress", True)
    assert req("manipulate") == (
        TargetInfo(tuple(card_entity(i) for i in state.imperium_row)),
    )
    assert req("devour", True) == (hand,)
    spies = TargetInfo((spy_entity(POST_A, SEAT), spy_entity(POST_B, SEAT)))
    assert req("find_weakness", True) == (spies,)
    assert req("spring_the_trap", True) == (spies,)
    contracts = TargetInfo(
        tuple(contract_entity(c, SEAT) for c in state.face_up_contract_ids)
    )
    assert req("leverage") == (contracts,)
    assert req("tactical_option", True) == (opts(0, 1), opts(0, 1))
    assert req("go_to_ground", True) == (opts(0, 1),)
    assert req("reach_agreement", True) == (opts(0, 1), contracts)
    assert req("detonation") == (opts(0, 1), opts(0))
    assert req("special_mission") == (opts(0, 1), spies)
    for name in ("cunning", "market_opportunity", "spice_is_power", "mercenaries"):
        assert req(name, name == "spice_is_power") == ()
    # No Shield Wall: Detonation lists only the garrison troops; every City
    # post taken: Special Mission lists only the spies.
    blocked = with_state(state, shield_wall_present=False)
    blocked = with_player(blocked, 0, spy_post_ids=CITY, spies_supply=0)
    ctx = AppContext(blocked, SEAT, ENGINE.observe(blocked, SEAT))
    assert W.intrigue_request(ctx, iid("detonation"), False).infos == (opts(0),)
    assert W.intrigue_request(ctx, iid("special_mission"), False).infos == (spies,)


# ---------------------------------------------------------------------------
# intrigue_choice: influence, discard
# ---------------------------------------------------------------------------


def test_lose_influence_replays_the_answer_then_falls_back(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state, "backed_by_choam", influence=Influence(emperor=1, fremen=2)
    )
    fix_answer(monkeypatch, "backed_by_choam", Answer(101.0, (("fremen",),)))
    memory = Memory()
    choice = app_play(state, memory, "backed_by_choam")
    assert kind(choice) == "intrigue_choice"
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "choose_intrigue_faction", faction="fremen"
    )
    # Played outside an app prompt: the ability answers again (nothing here),
    # so the least painful G(f, -1) loses (Backed by CHOAM's pricing).
    fix_answer(monkeypatch, "backed_by_choam", Answer(0.0, None))
    fresh = Memory()
    run = make_run(
        choice, fresh, gain_influence_value=g_values(emperor=1.0, fremen=3.0)
    )
    assert W.intrigue_choice(run) == act("choose_intrigue_faction", faction="emperor")
    assert fresh.intents[("intrigue", iid("backed_by_choam"))] == Answer(0.0, None)
    assert fresh.intents[("intrigue_at", iid("backed_by_choam"))] == len(
        state.event_log
    )


def test_a_stale_intent_is_evaluated_again(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state, "backed_by_choam", influence=Influence(emperor=1, fremen=2)
    )
    fix_answer(monkeypatch, "backed_by_choam", Answer(101.0, (("emperor",),)))
    memory = Memory()
    choice = app_play(state, memory, "backed_by_choam")
    assert W.recorded_answer(make_run(choice, memory), iid("backed_by_choam")) == (
        Answer(101.0, (("emperor",),))
    )
    memory.intents[("intrigue_at", iid("backed_by_choam"))] = -1  # another play
    assert W.recorded_answer(make_run(choice, memory), iid("backed_by_choam")) is None
    fix_answer(monkeypatch, "backed_by_choam", Answer(101.0, (("fremen",),)))
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "choose_intrigue_faction", faction="fremen"
    )


def test_opportunism_loses_each_answered_track_in_turn(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state,
        "opportunism",
        influence=Influence(emperor=2, fremen=2),
        resources=Resources(solari=2),
    )
    fix_answer(monkeypatch, "opportunism", Answer(104.0, (("emperor",), ("fremen",))))
    memory = Memory()
    choice = app_play(state, memory, "opportunism")
    first = W.intrigue_choice(make_run(choice, memory))
    assert first == act("choose_intrigue_faction", faction="emperor")
    assert first is not None
    second = step(choice, first)
    assert W.intrigue_choice(make_run(second, memory)) == act(
        "choose_intrigue_faction", faction="fremen"
    )


def test_buy_access_gains_both_answered_tracks(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "buy_access", resources=Resources(solari=5))
    fix_answer(monkeypatch, "buy_access", Answer(1.0, (("fremen", "emperor"),)))
    memory = Memory()
    choice = app_play(state, memory, "buy_access")
    first = W.intrigue_choice(make_run(choice, memory))
    assert first == act("choose_intrigue_faction", faction="fremen")
    assert first is not None
    second = step(choice, first)
    assert W.intrigue_choice(make_run(second, memory)) == act(
        "choose_intrigue_faction", faction="emperor"
    )


def test_imperium_politics_gain_and_its_evaluator_fallback(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "imperium_politics", resources=Resources(solari=1))
    fix_answer(monkeypatch, "imperium_politics", Answer(12.0, (("emperor",),)))
    memory = Memory()
    choice = app_play(state, memory, "imperium_politics")
    g = g_values(emperor=1.0, spacing_guild=2.0)
    assert W.intrigue_choice(make_run(choice, memory, gain_influence_value=g)) == act(
        "choose_intrigue_faction", faction="emperor"
    )
    # No answer: ChooseFactionInfluenceEvaluator (G + 100, first strict best).
    fix_answer(monkeypatch, "imperium_politics", Answer(0.0, None))
    run = make_run(choice, Memory(), gain_influence_value=g)
    assert W.intrigue_choice(run) == act(
        "choose_intrigue_faction", faction="spacing_guild"
    )


def test_sietch_ritual_discards_then_gains_the_answer(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "sietch_ritual")
    hand = state.players[SEAT].hand
    fix_answer(monkeypatch, "sietch_ritual", Answer(13.0, ((hand[2],), ("fremen",))))
    memory = Memory()
    choice = app_play(state, memory, "sietch_ritual")
    discard = W.intrigue_choice(make_run(choice, memory))
    assert discard == act("choose_intrigue_discard", card_id=hand[2])
    assert discard is not None
    gain = step(choice, discard)
    assert W.intrigue_choice(make_run(gain, memory)) == act(
        "choose_intrigue_faction", faction="fremen"
    )
    # No answer: GetDiscardOrder's first card.
    fix_answer(monkeypatch, "sietch_ritual", Answer(0.0, None))
    run = make_run(
        choice, Memory(), discard_order=lambda cards, sg: list(reversed(cards))
    )
    assert W.intrigue_choice(run) == act("choose_intrigue_discard", card_id=hand[-1])


# ---------------------------------------------------------------------------
# intrigue_choice: wall, deploy, trash
# ---------------------------------------------------------------------------


def test_detonation_wall_follows_intrigue_blow_wall(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "detonation")
    fix_answer(monkeypatch, "detonation", Answer(100.0, ((0,),)))
    memory = Memory()
    choice = app_play(state, memory, "detonation")
    yes = make_run(choice, memory, intrigue_blow_wall=lambda: True)
    assert W.intrigue_choice(yes) == act("detonate_shield_wall")
    no = make_run(
        choice, memory, intrigue_blow_wall=lambda: False, should_blow_wall=lambda: True
    )
    assert W.intrigue_choice(no) == act("keep_shield_wall")


def test_other_wall_prompts_ask_should_blow_wall(turn_state: GameState) -> None:
    both = (act("detonate_shield_wall"), act("keep_shield_wall"))
    yes = make_run(turn_state, legal=both, should_blow_wall=lambda: True)
    assert W._shield_wall(yes, "arrakis_revolt") == both[0]
    no = make_run(turn_state, legal=both, should_blow_wall=lambda: False)
    assert W._shield_wall(no, "arrakis_revolt") == both[1]


def test_unexpected_allies_always_blows_the_wall_first(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "unexpected_allies", resources=Resources(water=2))
    fix_answer(monkeypatch, "unexpected_allies", Answer(100.0, ()))
    memory = Memory()
    choice = app_play(state, memory, "unexpected_allies")
    run = make_run(
        choice,
        memory,
        intrigue_blow_wall=lambda: False,
        should_blow_wall=lambda: False,
    )
    assert act("resolve_intrigue_rewards") in run.legal
    assert W.intrigue_choice(run) == act("detonate_shield_wall")


def test_detonation_deploys_the_answered_troops(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "detonation")
    fix_answer(monkeypatch, "detonation", Answer(100.0, ((1,), (0, 1))))
    memory = Memory()
    choice = app_play(state, memory, "detonation")
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "deploy_intrigue_troops", count=2
    )
    # No answer: IntrigueDeployTroops, clamped into our 0..3 ("Deploy up to
    # four troops" may deploy zero [Detonation card face]).
    fix_answer(monkeypatch, "detonation", Answer(0.0, None))
    monkeypatch.setattr(W, "intrigue_deploy_troops", lambda p, troops: 5)
    assert W.intrigue_choice(make_run(choice, Memory())) == act(
        "deploy_intrigue_troops", count=3
    )
    monkeypatch.setattr(W, "intrigue_deploy_troops", lambda p, troops: 0)
    assert W.intrigue_choice(make_run(choice, Memory())) == act(
        "deploy_intrigue_troops", count=0
    )


def test_detonation_without_the_wall_reads_the_troop_list(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = with_state(give(turn_state, "detonation"), shield_wall_present=False)
    fix_answer(monkeypatch, "detonation", Answer(100.0, ((0,),)))
    memory = Memory()
    choice = app_play(state, memory, "detonation")
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "deploy_intrigue_troops", count=1
    )


def test_cunning_trashes_through_its_trash_ability(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "cunning", resources=Resources(spice=1))
    hand = state.players[SEAT].hand
    fix_answer(monkeypatch, "cunning", Answer(5.0, ((1,),)))
    memory = Memory()
    choice = app_play(state, memory, "cunning")
    seen: list[list[str]] = []

    def to_trash(targets: list[Entity], minimum: float) -> tuple[Entity | None, float]:
        seen.append([t.ref for t in targets])
        assert minimum == 1.0
        return targets[3], 4.0

    run = make_run(choice, memory, card_to_trash=to_trash)
    assert act("resolve_intrigue_rewards") in run.legal
    assert W.intrigue_choice(run) == act("trash_intrigue_card", card_id=hand[3])
    assert seen == [list(hand)]
    keep = make_run(choice, memory, card_to_trash=lambda t, m: (None, 1.0))
    assert W.intrigue_choice(keep) == act("decline_intrigue_trash")


def test_devour_trashes_the_answered_card_or_declines(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(combat_state, "devour", sandworms_conflict=1)
    discard = state.players[SEAT].discard_pile
    fix_answer(monkeypatch, "devour", Answer(12.0, ((discard[4],),)), combat=True)
    memory = Memory()
    choice = app_play(state, memory, "devour", combat=True)
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "trash_intrigue_card", card_id=discard[4]
    )
    fix_answer(monkeypatch, "devour", Answer(10.0, ((),)), combat=True)
    memory = Memory()
    choice = app_play(state, memory, "devour", combat=True)
    assert W.intrigue_choice(make_run(choice, memory)) == act("decline_intrigue_trash")
    # No answer: GetCardToTrash(targets, 1.0).
    fix_answer(monkeypatch, "devour", Answer(0.0, None), combat=True)
    run = make_run(choice, Memory(), card_to_trash=lambda t, m: (t[1], 2.0))
    assert W.intrigue_choice(run) == act("trash_intrigue_card", card_id=discard[1])
    run = make_run(choice, Memory(), card_to_trash=lambda t, m: (None, 1.0))
    assert W.intrigue_choice(run) == act("decline_intrigue_trash")


# ---------------------------------------------------------------------------
# intrigue_choice: spies, retreats, acquisitions, flips
# ---------------------------------------------------------------------------


def test_go_to_ground_retreats_then_places_by_the_spy_evaluators(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(combat_state, "go_to_ground")
    fix_answer(monkeypatch, "go_to_ground", Answer(2.0, ((0, 1),)), combat=True)
    memory = Memory()
    choice = app_play(state, memory, "go_to_ground", combat=True)
    retreat = W.intrigue_choice(make_run(choice, memory))
    assert retreat == act("retreat_intrigue_troops", count=2)
    assert retreat is not None
    place = step(choice, retreat)

    def best(posts: list[Entity], unseen: bool = False) -> tuple[Entity, float]:
        assert unseen is False
        return next(p for p in posts if p.ref == POST_C), 3.0

    assert W.intrigue_choice(make_run(place, memory, best_post=best)) == act(
        "place_intrigue_spy", post_id=POST_C
    )
    # Empty supply: recall the spy on the worst post first (RecallSpyEvaluator).
    empty = with_player(
        place, SEAT, spies_supply=0, spy_post_ids=(POST_A, POST_B, POST_C)
    )
    run = make_run(
        empty,
        memory,
        recall_spy=lambda spies: (next(s for s in spies if s.ref == POST_B), 0.0),
    )
    assert W.intrigue_choice(run) == act("recall_spy_for_intrigue", post_id=POST_B)


def test_retreat_without_an_answer_asks_get_troops_to_retreat(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(combat_state, "tactical_option")
    fix_answer(
        monkeypatch, "tactical_option", Answer(150.0, ((1,), (0, 1))), combat=True
    )
    memory = Memory()
    choice = app_play(state, memory, "tactical_option", combat=True)
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "retreat_intrigue_troops", count=2
    )
    fix_answer(monkeypatch, "tactical_option", Answer(0.0, None), combat=True)
    asked: list[int] = []

    def troops_to_retreat(maximum: int) -> int:
        asked.append(maximum)
        return 9

    run = make_run(choice, Memory(), troops_to_retreat=troops_to_retreat)
    assert W.intrigue_choice(run) == act("retreat_intrigue_troops", count=3)
    assert asked == [3]


def test_spring_the_trap_recalls_the_answered_spies_in_order(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        combat_state,
        "spring_the_trap",
        spy_post_ids=(POST_A, POST_B, POST_C),
        spies_supply=0,
    )
    fix_answer(
        monkeypatch, "spring_the_trap", Answer(9.0, ((POST_C, POST_A),)), combat=True
    )
    memory = Memory()
    choice = app_play(state, memory, "spring_the_trap", combat=True)
    first = W.intrigue_choice(make_run(choice, memory))
    assert first == act("recall_spy_for_intrigue", post_id=POST_C)
    assert first is not None
    second = step(choice, first)
    assert W.intrigue_choice(make_run(second, memory)) == act(
        "recall_spy_for_intrigue", post_id=POST_A
    )
    # No answer: the spy on the worst post (GetRecallSpy).
    fix_answer(monkeypatch, "spring_the_trap", Answer(0.0, None), combat=True)
    run = make_run(
        choice,
        Memory(),
        recall_spies=lambda spies, take: ([spies[1]], 0.0),
    )
    assert W.intrigue_choice(run) == act("recall_spy_for_intrigue", post_id=POST_B)


def test_special_mission_recalls_the_answered_spy_then_asks_intrigue_blow_wall(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state, "special_mission", spy_post_ids=(POST_A, POST_B), spies_supply=1
    )
    fix_answer(monkeypatch, "special_mission", Answer(6.0, ((1,), (POST_B,))))
    memory = Memory()
    choice = app_play(state, memory, "special_mission")
    recall = W.intrigue_choice(make_run(choice, memory))
    assert recall == act("recall_spy_for_intrigue", post_id=POST_B)
    assert recall is not None
    wall = step(choice, recall)
    run = make_run(wall, memory, intrigue_blow_wall=lambda: False)
    assert act("resolve_intrigue_rewards") in run.legal
    assert W.intrigue_choice(run) == act("keep_shield_wall")
    run = make_run(wall, memory, intrigue_blow_wall=lambda: True)
    assert W.intrigue_choice(run) == act("detonate_shield_wall")


def test_special_mission_places_on_the_best_city_post(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "special_mission", spy_post_ids=(POST_A,), spies_supply=2)
    fix_answer(monkeypatch, "special_mission", Answer(2.0, ((0,),)))
    memory = Memory()
    choice = app_play(state, memory, "special_mission")

    def best(posts: list[Entity], unseen: bool = False) -> tuple[Entity, float]:
        assert sorted(p.ref for p in posts) == sorted(CITY)
        return posts[-1], 1.0

    run = make_run(choice, memory, best_post=best)
    places = run.by_id("place_intrigue_spy")
    assert W.intrigue_choice(run) == places[-1]


def test_impress_and_inspire_awe_acquire_the_answered_card(
    turn_state: GameState, combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "inspire_awe")
    fix_answer(
        monkeypatch, "inspire_awe", Answer(4.0, (("reserve:prepare_the_way",), (0,)))
    )
    memory = Memory()
    choice = app_play(state, memory, "inspire_awe")
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "acquire_intrigue_reserve", card_id="prepare_the_way"
    )
    row3 = acquirable_imperium_instance_ids(combat_state, 3)
    assert row3
    fight = give(combat_state, "impress")
    fix_answer(monkeypatch, "impress", Answer(3.0, ((row3[0],),)), combat=True)
    memory = Memory()
    choice = app_play(fight, memory, "impress", combat=True)
    run = make_run(choice, memory)
    assert act("resolve_intrigue_rewards") in run.legal
    assert W.intrigue_choice(run) == act(
        "acquire_intrigue_imperium", instance_id=row3[0]
    )
    # No answer: first strictly best AcquireValue (Row, then Reserve).
    fix_answer(monkeypatch, "impress", Answer(0.0, None), combat=True)
    values = {row3[0]: 1.0, "reserve:prepare_the_way": 2.0}
    run = make_run(
        choice,
        Memory(),
        acquire_value=lambda card: Summer(values.get(card.ref, 0.0)),
    )
    assert W.intrigue_choice(run) == act(
        "acquire_intrigue_reserve", card_id="prepare_the_way"
    )
    # Nothing within the cap: skip.
    only = (act("skip_intrigue_acquisition"), act("resolve_intrigue_rewards"))
    assert W.intrigue_choice(make_run(choice, memory, legal=only)) == only[0]


def test_manipulate_sets_aside_the_answer_or_the_best_card(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(turn_state, "manipulate")
    row = state.imperium_row
    fix_answer(monkeypatch, "manipulate", Answer(5.0, ((row[3],),)))
    memory = Memory()
    choice = app_play(state, memory, "manipulate")
    assert W.intrigue_choice(make_run(choice, memory)) == act(
        "manipulate_imperium_row", instance_id=row[3]
    )
    fix_answer(monkeypatch, "manipulate", Answer(0.0, None))
    values = {row[1]: 4.0, row[2]: 4.0}
    run = make_run(
        choice,
        Memory(),
        acquire_value=lambda card: Summer(values.get(card.ref, 0.0)),
    )
    assert W.intrigue_choice(run) == act("manipulate_imperium_row", instance_id=row[1])


def test_battle_icon_flip_pairs_like_score_battle_icons_pairs(
    endgame_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both won Crysknife Conflicts face up: they pair with each other in
    # ScoreBattleIconsPairs, so the card's icon finds no partner (None).
    state = give(
        endgame_state,
        "crysknife",
        face_down_battle_card_ids=("objective_desert_mouse", "protect_the_sietches"),
    )
    choice = step(state, act("play_intrigue", card_id=iid("crysknife"), option=1))
    run = make_run(choice)
    flips = run.by_id("flip_battle_card")
    assert [a.arguments for a in flips] == [
        (("card_id", "seize_spice_refinery"),),
        (("card_id", "battle_for_arrakeen"),),
    ]
    assert (
        I.complete_battle_icon_pair_card(
            run.profile, intrigue_entity(iid("crysknife"), SEAT)
        )
        is None
    )
    assert W.intrigue_choice(run) == flips[0]
    monkeypatch.setattr(
        W,
        "complete_battle_icon_pair_card",
        lambda p, card: str(flips[1].arguments[0][1]),
    )
    assert W.intrigue_choice(run) == flips[1]
    monkeypatch.setattr(W, "complete_battle_icon_pair_card", lambda p, card: None)
    assert W.intrigue_choice(run) == flips[0]


# ---------------------------------------------------------------------------
# intrigue_effects
# ---------------------------------------------------------------------------


def test_change_allegiances_swaps_then_buys_influence_with_spice(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state,
        "change_allegiances",
        influence=Influence(emperor=2),
        resources=Resources(spice=3),
    )
    fix_answer(monkeypatch, "change_allegiances", Answer(3.0, (("emperor",),)))
    memory = Memory()
    g = g_values(emperor=1.0, spacing_guild=1.0, bene_gesserit=3.0, fremen=2.0)
    # The swap pick is made with the answer (G + 100 over the gain targets).
    effects = app_play(state, memory, "change_allegiances", gain_influence_value=g)
    assert swap_pick(memory) == (103.0, (("bene_gesserit",),))
    assert kind(effects) == "intrigue_effects"
    line0 = W.intrigue_effects(make_run(effects, memory))
    assert line0 == act("use_intrigue_effect", section=0)
    assert line0 is not None
    lose = step(effects, line0)
    gain = step(lose, act("choose_intrigue_faction", faction="emperor"))
    pick = W.intrigue_choice(make_run(gain, memory))
    assert pick == act("choose_intrigue_faction", faction="bene_gesserit")
    assert pick is not None
    back = step(gain, pick)
    assert kind(back) == "intrigue_effects"
    assert W.intrigue_effects(make_run(back, memory)) == act(
        "use_intrigue_effect", section=1
    )
    # The spice branch without a track to lose: line 1 straight away, and
    # no swap pick is kept.
    fix_answer(monkeypatch, "change_allegiances", Answer(10.0, ((),)))
    memory = Memory()
    effects = app_play(state, memory, "change_allegiances")
    assert (W.INTENT_SWAP_GAIN, iid("change_allegiances")) not in memory.intents
    assert W.intrigue_effects(make_run(effects, memory)) == act(
        "use_intrigue_effect", section=1
    )


def test_change_allegiances_prices_the_swap_before_the_loss(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The app resolves the gain target (ChooseFactionInfluenceEvaluator)
    # before ChangeAllegiances/<execute>d__4 pays the loss. Lose Emperor at
    # 2: pre-loss G(emperor, +1) prices 2 -> 3 (2.25) below G(fremen, +1)
    # 0 -> 1 (2.7); post-loss it would price 1 -> 2 (2.8125) and win.
    state = give(
        turn_state,
        "change_allegiances",
        influence=Influence(emperor=2),
        resources=Resources(spice=0),
    )
    fix_answer(monkeypatch, "change_allegiances", Answer(3.0, (("emperor",),)))
    memory = Memory()
    effects = app_play(state, memory, "change_allegiances")
    value, response = swap_pick(memory)
    assert value == pytest.approx(102.7)
    assert response == (("fremen",),)
    # Effect line and loss each have one legal choice: the gain slot is the
    # first decision the agent is asked after the play.
    assert len(ENGINE.legal_actions(effects, SEAT)) == 1
    lose = step(effects, act("use_intrigue_effect", section=0))
    assert ENGINE.legal_actions(lose, SEAT) == (
        act("choose_intrigue_faction", faction="emperor"),
    )
    gain = step(lose, act("choose_intrigue_faction", faction="emperor"))
    assert gain.players[SEAT].influence.emperor == 1
    run = make_run(gain, memory)
    assert W.intrigue_choice(run) == act("choose_intrigue_faction", faction="fremen")
    # Priced on the post-loss state the evaluator would regain Emperor.
    actions = run.by_id("choose_intrigue_faction")
    assert W._evaluator_gain(run, actions) == act(
        "choose_intrigue_faction", faction="emperor"
    )


def test_change_allegiances_gain_targets_append_the_lost_track(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # MakeGainFactionTargeting: GetFactionTrackTargets() (rank <= 5), then
    # the lost track appended when missing (a track at 6 cannot gain).
    top = give(turn_state, "change_allegiances", influence=Influence(emperor=6))
    ctx = make_run(top).ctx
    assert [t.ref for t in W._gain_targeting(ctx, "emperor")] == [
        "spacing_guild",
        "bene_gesserit",
        "fremen",
        "emperor",
    ]
    assert [t.ref for t in W._gain_targeting(ctx, None)] == [
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    low = give(turn_state, "change_allegiances", influence=Influence(emperor=2))
    assert [t.ref for t in W._gain_targeting(make_run(low).ctx, "emperor")] == [
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    # The appended track is priced too (a rank-blind G stub makes it win).
    fix_answer(monkeypatch, "change_allegiances", Answer(3.0, (("emperor",),)))
    memory = Memory()
    g = g_values(emperor=5.0, fremen=1.0)
    app_play(top, memory, "change_allegiances", gain_influence_value=g)
    assert swap_pick(memory) == (105.0, (("emperor",),))


def test_change_allegiances_spice_gain_skips_tracks_at_the_top(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # PaySpiceForInfluence's picker starts from GetFactionTrackTargets():
    # Emperor at 6 is offered by our engine but is no app target.
    state = give(
        turn_state,
        "change_allegiances",
        influence=Influence(emperor=6),
        resources=Resources(spice=3),
    )
    fix_answer(monkeypatch, "change_allegiances", Answer(10.0, ((),)))
    memory = Memory()
    effects = app_play(state, memory, "change_allegiances")
    line1 = W.intrigue_effects(make_run(effects, memory))
    assert line1 == act("use_intrigue_effect", section=1)
    assert line1 is not None
    gain = step(effects, line1)
    assert act("choose_intrigue_faction", faction="emperor") in (
        ENGINE.legal_actions(gain, SEAT)
    )
    g = g_values(emperor=5.0, fremen=1.0)
    run = make_run(gain, memory, gain_influence_value=g)
    assert W.intrigue_choice(run) == act("choose_intrigue_faction", faction="fremen")


def test_change_allegiances_skips_the_spice_line_when_no_track_can_gain(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every track at 6: swap Emperor (6 -> 5, the appended lost track is the
    # only gain target, back to 6); then GetFactionTrackTargets().Any() is
    # false, so PaySpiceForInfluence does not pay (finish).
    state = give(
        turn_state,
        "change_allegiances",
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
        resources=Resources(spice=3),
    )
    fix_answer(monkeypatch, "change_allegiances", Answer(3.0, (("emperor",),)))
    memory = Memory()
    effects = app_play(state, memory, "change_allegiances")
    line0 = W.intrigue_effects(make_run(effects, memory))
    assert line0 == act("use_intrigue_effect", section=0)
    assert line0 is not None
    lose = step(effects, line0)
    loss = W.intrigue_choice(make_run(lose, memory))
    assert loss == act("choose_intrigue_faction", faction="emperor")
    assert loss is not None
    gain = step(lose, loss)
    pick = W.intrigue_choice(make_run(gain, memory))
    assert pick == act("choose_intrigue_faction", faction="emperor")
    assert pick is not None
    back = step(gain, pick)
    assert kind(back) == "intrigue_effects"
    assert act("use_intrigue_effect", section=1) in ENGINE.legal_actions(back, SEAT)
    assert W.intrigue_effects(make_run(back, memory)) == act("finish_intrigue_effects")


def test_change_allegiances_finishes_without_spice(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state,
        "change_allegiances",
        influence=Influence(emperor=2, fremen=1),
        resources=Resources(spice=0),
    )
    fix_answer(monkeypatch, "change_allegiances", Answer(3.0, (("fremen",),)))
    memory = Memory()
    effects = app_play(state, memory, "change_allegiances")
    # Only line 0 is usable: the engine does not ask (one legal action).
    assert ENGINE.legal_actions(effects, SEAT) == (
        act("use_intrigue_effect", section=0),
    )
    lose = step(effects, act("use_intrigue_effect", section=0))
    run = make_run(lose, memory)
    assert W.intrigue_choice(run) == act("choose_intrigue_faction", faction="fremen")


def test_depart_for_arrakis_buys_troops_only_on_int_1(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state,
        "depart_for_arrakis",
        influence=Influence(spacing_guild=3),
        resources=Resources(spice=2),
    )
    fix_answer(monkeypatch, "depart_for_arrakis", Answer(100.0, ((1,),)))
    memory = Memory()
    effects = app_play(state, memory, "depart_for_arrakis")
    assert W.intrigue_effects(make_run(effects, memory)) == act(
        "use_intrigue_effect", section=0
    )
    fix_answer(monkeypatch, "depart_for_arrakis", Answer(100.0, ((0,),)))
    memory = Memory()
    effects = app_play(state, memory, "depart_for_arrakis")
    assert W.intrigue_effects(make_run(effects, memory)) == act(
        "finish_intrigue_effects"
    )


def test_strategic_stockpiling_confirms_then_says_yes(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        turn_state,
        "strategic_stockpiling",
        influence=Influence(fremen=3),
        resources=Resources(spice=5, water=3),
    )
    fix_answer(monkeypatch, "strategic_stockpiling", Answer(100.0, ((1,),)))
    memory = Memory()
    effects = app_play(state, memory, "strategic_stockpiling")
    first = W.intrigue_effects(make_run(effects, memory))
    assert first == act("use_intrigue_effect", section=0)
    assert first is not None
    after = step(effects, first)
    assert W.intrigue_effects(make_run(after, memory)) == act(
        "use_intrigue_effect", section=1
    )


def test_find_weakness_always_recalls_the_answered_spy(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        combat_state, "find_weakness", spy_post_ids=(POST_A, POST_B), spies_supply=1
    )
    fix_answer(monkeypatch, "find_weakness", Answer(0.1, ((POST_B,),)), combat=True)
    memory = Memory()
    effects = app_play(state, memory, "find_weakness", combat=True)
    line = W.intrigue_effects(make_run(effects, memory))
    assert line == act("use_intrigue_effect", section=1)
    assert line is not None
    recall = step(effects, line)
    assert W.intrigue_choice(make_run(recall, memory)) == act(
        "recall_spy_for_intrigue", post_id=POST_B
    )


def test_questionable_methods_loses_the_answered_track_or_finishes(
    combat_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = give(
        combat_state, "questionable_methods", influence=Influence(emperor=1, fremen=1)
    )
    fix_answer(
        monkeypatch, "questionable_methods", Answer(5.3, (("fremen",),)), combat=True
    )
    memory = Memory()
    effects = app_play(state, memory, "questionable_methods", combat=True)
    line = W.intrigue_effects(make_run(effects, memory))
    assert line == act("use_intrigue_effect", section=1)
    assert line is not None
    lose = step(effects, line)
    assert W.intrigue_choice(make_run(lose, memory)) == act(
        "choose_intrigue_faction", faction="fremen"
    )
    fix_answer(monkeypatch, "questionable_methods", Answer(1.0, ((),)), combat=True)
    memory = Memory()
    effects = app_play(state, memory, "questionable_methods", combat=True)
    assert W.intrigue_effects(make_run(effects, memory)) == act(
        "finish_intrigue_effects"
    )


# ---------------------------------------------------------------------------
# Full games
# ---------------------------------------------------------------------------


def _play_window(window: str) -> Handler:
    """Test-only stand-in for the play windows: the app's best intrigue play
    (``intrigue_play_sources`` + ``make_choice``) or the heuristic."""

    def handler(run: DecisionRun) -> DomainAction | None:
        sources = W.intrigue_play_sources(
            run, run.by_id("play_intrigue"), combat=window == "combat_intrigue"
        )
        candidates = []
        for source in sources:
            assert source.evaluate is not None
            value, action = source.evaluate()
            if action is not None:
                candidates.append(Candidate(action, value, source.label))
        choice = make_choice(candidates, run.rng)
        return None if choice is None else choice.action

    return handler


def test_full_games_never_fall_back_in_the_intrigue_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handlers: dict[str, Handler] = dict(W.HANDLERS)
    for window in ("turn", "agent_effects", "reveal", "combat_intrigue"):
        handlers[window] = _play_window(window)
    # Only this module's windows (and the test play windows) are mirrored, so
    # other windows' work in progress cannot change these games.
    monkeypatch.setattr(
        agent_module, "handler_for", lambda kind: handlers.get(kind) if kind else None
    )
    engine = UprisingRulesEngine()
    mirrored: Counter[str] = Counter()
    for seed in range(1, 9):
        agents = tuple(AppAIAgent(seed=10 * seed + s) for s in range(4))
        config = RulesetConfig(choam_module=seed % 2 == 0)
        result = run_policy_game(engine, config, seed, agents)
        assert result.state.phase is GamePhase.FINISHED
        for agent in agents:
            assert agent.fallbacks["intrigue_choice"] == 0
            assert agent.fallbacks["intrigue_effects"] == 0
            mirrored.update(agent.mirrored)
    assert mirrored["intrigue_choice"] > 20
    assert mirrored["intrigue_effects"] > 0
