"""The windows that answer Rise of Ix's Tech tiles (plan §13): Flip and
trash activations in the turn, Agent-turn and Reveal windows, the acquire
effects, Disposal Facility, Sonic Snoopers' pick and Tech acquisition."""

import logging
from collections import Counter

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import ix
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.config import BaseGame
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True, leader_draft=True
)
#: Windows whose Rise of Ix decisions are the Tech tiles' and the board's.
TECH_WINDOWS = (
    "turn",
    "reveal",
    "tech_acquisition",
    "intrigue_bottom_pick",
    "freighter_move",
    "shipping_reward_icons",
    "dreadnought_control_choice",
)


@pytest.fixture(scope="module")
def fallbacks() -> Counter[str]:
    counted: Counter[str] = Counter()
    previous = logging.getLogger("dune_imperium.agents.app_ai.agent").level
    try:
        for seed in (8000, 8001, 8002, 8003):
            agents = tuple(AppAIAgent(seed=seed * 10 + s) for s in range(4))
            run_policy_game(UprisingRulesEngine(), IX, seed, agents)
            for agent in agents:
                counted.update(agent.fallbacks)
    finally:
        logging.getLogger("dune_imperium.agents.app_ai.agent").setLevel(previous)
    return counted


def test_the_tech_and_board_windows_never_fall_back(fallbacks: Counter[str]) -> None:
    assert {k: n for k, n in fallbacks.items() if k in TECH_WINDOWS} == {}
    assert not [k for k in fallbacks if k.startswith("error:")]


def _bottom_run(monkeypatch: pytest.MonkeyPatch, bad: list[str]) -> DecisionRun:
    p = make_profile(first_decision("turn", config=IX))
    seat = p.ctx.seat
    cards = [Entity(Kind.INTRIGUE, ref, None, seat) for ref in bad]
    monkeypatch.setattr(p, "bad_intrigue_cards_in_hand", lambda: cards)
    legal = (
        DomainAction(
            action_id="put_intrigue_on_bottom",
            actor=seat,
            arguments=(("card_id", "intrigue:a:0"),),
        ),
        DomainAction(
            action_id="put_intrigue_on_bottom",
            actor=seat,
            arguments=(("card_id", "intrigue:b:0"),),
        ),
        DomainAction(action_id="finish_intrigue_bottom", actor=seat),
    )
    return DecisionRun(p.ctx, p, legal, p.rng, Memory())


def test_sonic_snoopers_puts_the_bad_cards_then_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen = ix.intrigue_bottom_pick(_bottom_run(monkeypatch, ["intrigue:b:0"]))
    assert chosen is not None and dict(chosen.arguments) == {"card_id": "intrigue:b:0"}
    done = ix.intrigue_bottom_pick(_bottom_run(monkeypatch, []))
    assert done is not None and done.action_id == "finish_intrigue_bottom"


def _choice_run(actions: list[DomainAction]) -> DecisionRun:
    p = make_profile(first_decision("turn", config=IX))
    return DecisionRun(p.ctx, p, tuple(actions), p.rng, Memory())


def test_an_intrigue_freighter_follows_the_plays_item1() -> None:
    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.windows import intrigue

    rows = [
        DomainAction(action_id=a, actor=0)
        for a in (
            "advance_intrigue_freighter",
            "recall_intrigue_freighter",
            "decline_intrigue_freighter",
        )
    ]
    run = _choice_run(rows)
    recall = intrigue._intrigue_freighter(run, lambda: Answer(4.2, ((1,),), ""))
    advance = intrigue._intrigue_freighter(run, lambda: Answer(4.2, ((0,),), ""))
    assert recall is not None and recall.action_id == "recall_intrigue_freighter"
    assert advance is not None and advance.action_id == "advance_intrigue_freighter"


def test_strongarm_loses_the_troop_from_the_answered_zone() -> None:
    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.windows import intrigue

    rows = [
        DomainAction(action_id="lose_intrigue_troop", actor=0, arguments=(("zone", z),))
        for z in ("garrison", "conflict")
    ]
    run = _choice_run(rows)
    deployed = intrigue._lose_troops(run, "strongarm", lambda: Answer(1.0, ((1,),), ""))
    garrison = intrigue._lose_troops(run, "strongarm", lambda: Answer(1.0, ((0,),), ""))
    assert deployed is not None and dict(deployed.arguments) == {"zone": "conflict"}
    assert garrison is not None and dict(garrison.arguments) == {"zone": "garrison"}


def test_urgent_mission_recalls_the_agent_its_play_named() -> None:
    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.windows import intrigue

    rows = [
        DomainAction(
            action_id="recall_agent_for_intrigue", actor=0, arguments=(("space_id", s),)
        )
        for s in ("carthag", "dreadnought")
    ]
    run = _choice_run(rows)
    named = intrigue._recall_your_agent(
        run, lambda: Answer(100.0, (("dreadnought",),), "")
    )
    assert named is not None and dict(named.arguments) == {"space_id": "dreadnought"}
    again = intrigue._recall_your_agent(run, lambda: Answer(0.0, None, ""))
    assert again in rows


def test_troop_transports_answers_a_shipping_deployment_off_a_combat_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P4's ruling on seed 8100 (P4 ``87581ad9``): a Freighter recall at
    Interstellar Shipping recruited troops that Troop Transports lets deploy
    (rise-of-ix.md 15). The app asks ``TroopTransportsAbility``; without the
    tile, nothing."""

    from dune_imperium.agents.app_ai.catalog import space_entity
    from dune_imperium.agents.app_ai.windows import agent_effects

    p = make_profile(first_decision("turn", config=IX))
    seat = p.ctx.seat
    rows = tuple(
        DomainAction(action_id="deploy_troops", actor=seat, arguments=(("count", n),))
        for n in (1, 2, 3)
    )
    run = DecisionRun(p.ctx, p, rows, p.rng, Memory())

    def turn() -> agent_effects._Turn:
        return agent_effects._Turn(
            run=run,
            context={"combat_troops_deployed": 0},
            card_ref=None,
            card_short=None,
            card=None,
            space_id="interstellar_shipping",
            space=space_entity("interstellar_shipping", p.ctx.board),
            leader=None,
        )

    without = turn()
    agent_effects._deploy(without)
    assert not without.sources and not without.unmapped
    monkeypatch.setattr(type(p.ctx), "has_tech", lambda self, tech, seat=None: True)
    held = turn()
    agent_effects._deploy(held)
    assert [s.label for s in held.sources] == ["Troop Transports"]


def test_blackmail_cull_and_finesse_get_their_app_targets() -> None:
    """Review 2026-10-30: without infos the three evaluates were empty, so the
    cards were never played."""

    from dune_imperium.agents.app_ai.windows.intrigue import intrigue_request

    p = make_profile(first_decision("turn", config=IX))
    assert len(intrigue_request(p.ctx, "intrigue:blackmail:0", True).infos) == 1
    assert len(intrigue_request(p.ctx, "intrigue:cull:0", False).infos) == 1
    finesse = intrigue_request(p.ctx, "intrigue:finesse:0", False).infos
    assert len(finesse) == 2 and finesse[1].entities


def test_finesse_replays_its_exchange_in_the_influence_slots() -> None:
    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.windows import intrigue

    rows = [
        DomainAction(
            action_id="choose_intrigue_faction", actor=0, arguments=(("faction", f),)
        )
        for f in ("emperor", "fremen")
    ]
    run = _choice_run(rows)
    exchange = Answer(3.0, (("emperor",), ("fremen",)), "")
    lose = intrigue._lose_influence(run, "finesse", lambda: exchange, 0)
    gain = intrigue._gain_influence(
        run, "finesse", "intrigue:finesse:0", lambda: exchange, 0
    )
    assert lose is not None and dict(lose.arguments) == {"faction": "emperor"}
    assert gain is not None and dict(gain.arguments) == {"faction": "fremen"}


def test_local_fence_takes_the_row_of_the_apps_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``LocalFenceAbility::Evaluate``: option 0 "2 spice -> 5 Solari", option
    1 "5 Solari -> 4 spice" (IntTargetResponse 0 then 1 in the asm)."""

    from dune_imperium.agents.app_ai.abilities import ix_imperium
    from dune_imperium.agents.app_ai.catalog import card_entity
    from dune_imperium.agents.app_ai.windows import agent_effects

    p = make_profile(first_decision("turn", config=IX))
    seat = p.ctx.seat
    rows = tuple(
        DomainAction(action_id=a, actor=seat)
        for a in ("pay_agent_card_spice_for_solari", "pay_agent_card_solari_for_spice")
    )
    run = DecisionRun(p.ctx, p, rows, p.rng, Memory())
    fence = card_entity("imperium:local_fence:0", seat)
    for spice, solari, expected in ((1.0, 0.1, 1), (0.1, 1.0, 0)):
        monkeypatch.setattr(p, "spice_value", lambda n, s=spice: s * n)
        monkeypatch.setattr(p, "solari_value", lambda n, s=solari: s * n)
        t = agent_effects._Turn(
            run=run,
            context={},
            card_ref=fence.ref,
            card_short="local_fence",
            card=fence,
            space_id=None,
            space=None,
            leader=None,
        )
        agent_effects._ix_card_rows(t)
        [source] = t.sources
        assert source.evaluate is not None
        _value, action = source.evaluate()
        assert action is rows[expected]
    assert ix_imperium.LOCAL_FENCE_SPICE_TO_SOLARI == 0


def test_unload_rows_are_taken_in_order() -> None:
    rows = [
        DomainAction(
            action_id="resolve_unload_icon",
            actor=0,
            arguments=(("card_id", "imperium:water_peddler:0"), ("effect", e)),
        )
        for e in ("water", "spice")
    ]
    run = _choice_run(rows)
    assert ix.unload_icons(run) is rows[0]
