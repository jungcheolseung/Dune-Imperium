"""The app AI's Heighliner graft placements with a promised partner cut
(P7g, OQ-158): Guild Accord's 2 spice as a graft partner, 4 with Ghola.

Our engine offers such a placement once per cut its possible partners give
(``partner_discount``) and keeps for each only the partners that give that
cut. The app picks the partner first and prices the pair after
(``HeighlinerSpaceAbility.GetSpiceReduction``), so the AI picks its
partner over every variant's partners and plays the variant holding it
(``windows.turn._promised_cut``)."""

from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai import agent as app_agent
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.immortality import graft_card_evaluate
from dune_imperium.agents.app_ai.catalog import card_entity, space_entity
from dune_imperium.agents.app_ai.testing import make_profile
from dune_imperium.agents.app_ai.windows import turn
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.core import ChanceDecision, ChanceResolver
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import (
    PARTNER_DISCOUNT_KEY,
    apply_agent_action,
    executable_placements,
    heighliner_partner_discount,
)
from dune_imperium.rules.graft import legal_graft_partner_actions
from dune_imperium.simulation.runner import run_policy_game

ENGINE = UprisingRulesEngine(
    leader_ids=(
        "glossu_rabban",
        "count_ilban_richese",
        "earl_memnon_thorvald",
        "countess_ariana_thorvald",
    )
)
ORIGINAL_IX_IMMORTALITY = RulesetConfig(
    base_game=BaseGame.IMPERIUM,
    first_player_seat_zero=True,
    immortality=True,
    rise_of_ix=True,
)
USURP = "tleilaxu:usurp:0"
GHOLA = "tleilaxu:ghola:0"
GUILD_ACCORD = "imperium:guild_accord:0"
HEIGHLINER = "imperium_heighliner"  # 6 spice [DI p. 17]


def _cut(action: DomainAction) -> int:
    value = dict(action.arguments).get(PARTNER_DISCOUNT_KEY, 0)
    assert isinstance(value, int)
    return value


def _table(hand: tuple[str, ...], spice: int, row: tuple[str, ...] = ()) -> GameState:
    """Round 1, seat 0's turn on the original board with Rise of Ix and
    Immortality, ``row`` leading the Imperium Row, ``hand`` added and
    ``spice`` spice."""

    state = ENGINE.reset(ORIGINAL_IX_IMMORTALITY, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    moved = {*hand, *row}
    others = [c for c in (*state.imperium_row, *state.imperium_deck) if c not in moved]
    keep = 5 - len(row)
    state = replace(
        state,
        imperium_row=(*row, *others[:keep]),
        imperium_deck=tuple(others[keep:]),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c not in moved),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c not in moved),
    )
    owner = state.players[0]
    players = list(state.players)
    players[0] = replace(
        owner,
        hand=(*owner.hand, *hand),
        resources=replace(owner.resources, spice=spice),
    )
    return replace(state, players=tuple(players))


def _partners(state: GameState, placement: DomainAction) -> list[str]:
    placed = apply_agent_action(state, placement).state
    return [
        str(dict(a.arguments)["card_id"])
        for a in legal_graft_partner_actions(placed, placement.actor)
    ]


def _heighliner_grafts(
    state: GameState, card_id: str
) -> tuple[tuple[DomainAction, ...], list[DomainAction]]:
    """The executable placements, and ``card_id``'s graft ones on the
    Heighliner (no infiltration)."""

    placements = executable_placements(state, 0)
    return placements, [
        a
        for a in placements
        if dict(a.arguments)["card_id"] == card_id
        and dict(a.arguments)["space_id"] == HEIGHLINER
        and dict(a.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(a.arguments)
    ]


def test_usurp_plays_the_cut_of_the_row_partner_the_app_picks() -> None:
    """Usurp (a Graft card: its partner prompt is forced) on the Heighliner
    with Guild Accord leading the Imperium Row and spice for the full cost:
    the uncut variant keeps the partners that cut nothing (here hand cards,
    which Usurp may graft too [Immortality p. 14]), the cut-2 one only Guild
    Accord. ``GraftCardEvaluator`` picks over all of them, and the variant
    played promises its pick's cut."""

    state = _table((USURP,), spice=6, row=(GUILD_ACCORD,))
    legal, grafts = _heighliner_grafts(state, USURP)
    by_cut = {_cut(a): _partners(state, a) for a in grafts}
    assert set(by_cut) == {0, 2}
    assert by_cut[2] == [GUILD_ACCORD]
    assert by_cut[0] and GUILD_ACCORD not in by_cut[0]
    p = make_profile(state, 0)
    run = DecisionRun(p.ctx, p, legal, p.rng, Memory())
    played = turn._realise(run, grafts[0])
    assert played in grafts
    pool = [*by_cut[0], *by_cut[2]]
    request = Request(
        infos=(TargetInfo(entities=tuple(card_entity(c) for c in pool)),),
        forced=True,
    )
    answer = graft_card_evaluate(
        make_profile(state, 0),
        request,
        card_entity(USURP, 0),
        space_entity(HEIGHLINER, p.ctx.board),
    )
    assert answer.value > 0.0 and answer.response
    picked = str(answer.response[0][0])
    assert picked in _partners(state, played)
    assert _cut(played) == heighliner_partner_discount(HEIGHLINER, USURP, picked)
    key = (turn.GRAFT_PARTNER_INTENT, p.ctx.round_number, USURP)
    if len(_partners(state, played)) > 1:
        assert run.memory.intents[key] == picked


def test_guild_accord_takes_ghola_only_when_it_cannot_go_alone() -> None:
    """Ghola "copies the entire Agent box" [Immortality p. 14], Guild
    Accord's cut included (OQ-158): placed Guild Accord with Ghola takes 2
    more off the Heighliner. Guild Accord is no Graft card, so the app's
    partner prompt is forced only when the space needs a partner
    (``_graft_choice``): with 2 spice it cannot go alone, and its one graft
    placement promises Ghola's cut."""

    state = _table((GHOLA, GUILD_ACCORD), spice=2)
    legal, grafts = _heighliner_grafts(state, GUILD_ACCORD)
    assert [_cut(a) for a in grafts] == [2]
    assert _partners(state, grafts[0]) == [GHOLA]
    alone = [
        a
        for a in legal
        if dict(a.arguments)["card_id"] == GUILD_ACCORD
        and dict(a.arguments)["space_id"] == HEIGHLINER
        and dict(a.arguments).get("graft") is not True
    ]
    assert alone == []
    p = make_profile(state, 0)
    run = DecisionRun(p.ctx, p, legal, p.rng, Memory())
    assert turn._realise(run, grafts[0]) == grafts[0]
    assert heighliner_partner_discount(HEIGHLINER, GUILD_ACCORD, GHOLA) == 2


class _Reached(Exception):
    """The census game reached the seat's promised-cut decision."""


def test_usurp_takes_the_row_s_guild_accord_in_a_census_game(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real app AI game (census seed 5105, Uprising + Rise of Ix +
    Immortality, promos and Leader draft, all seats Hard): in round 5 seat 2
    Usurps the Imperium Row's Guild Accord onto the Heighliner. Its
    placement promises Guild Accord's 2 spice and its partner is Guild
    Accord ("Both played cards are considered to have "sent" the Agent"
    [Immortality p. 10])."""

    config = RulesetConfig(
        promo_cards=True, leader_draft=True, immortality=True, rise_of_ix=True
    )
    seed, round_number, seat = 5105, 5, 2
    agents = tuple(AppAIAgent(seed=seed * 10 + p, level=2) for p in range(4))
    original = app_agent.AppAIAgent._choose_with_state

    def stop(
        self: AppAIAgent,
        state: GameState,
        observation: object,
        actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        decision = state.decision_stack[-1].decision
        if (
            isinstance(decision, PlayerDecision)
            and decision.owner == seat
            and state.round_number == round_number
            and any(_cut(a) for a in actions if a.action_id == "agent_turn")
        ):
            raise _Reached(state)
        return original(self, state, observation, actions)  # type: ignore[arg-type]

    monkeypatch.setattr(app_agent.AppAIAgent, "_choose_with_state", stop)
    engine = UprisingRulesEngine()
    with pytest.raises(_Reached) as reached:
        run_policy_game(engine, config, seed, agents)
    monkeypatch.setattr(app_agent.AppAIAgent, "_choose_with_state", original)
    (state,) = reached.value.args
    ai = agents[seat]
    steps: list[DomainAction] = []
    for _ in range(10):
        legal = engine.legal_actions(state, seat)
        step = ai.choose_action_with_state(state, engine.observe(state, seat), legal)
        steps.append(step)
        if step.action_id == "choose_personal_card":
            break
        state = engine.apply(state, step, legal_actions=legal).state
    else:
        raise AssertionError(f"seed {seed} no longer reaches the partner pick")
    card, place, partner = steps[-3], steps[-2], steps[-1]
    assert dict(card.arguments) == {"card_id": USURP, "graft": True}
    assert dict(place.arguments) == {"space_id": "heighliner", "partner_discount": 2}
    assert dict(partner.arguments) == {"card_id": GUILD_ACCORD}


def test_duplicity_on_a_grafted_signet_ring_keeps_its_gain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tessia Vernius' Duplicity answers its loss and its gain at once and
    keeps the gain for the step after the loss. A grafted Signet Ring's other
    box is evaluated on a copy of the memory, so the gain is kept only when
    the loss is the row chosen (``on_choose``). Census seed 2003 (Uprising +
    Rise of Ix + Immortality, promos and Leader draft, all seats Normal):
    in round 8 seat 1 grafts Stitched Horror to the Signet Ring, loses
    Emperor Influence in the Signet box, and the gain step there fell back
    at random before."""

    config = RulesetConfig(
        promo_cards=True, leader_draft=True, immortality=True, rise_of_ix=True
    )
    seed, seat = 2003, 1
    agents = tuple(AppAIAgent(seed=seed * 10 + p, level=1) for p in range(4))
    original = app_agent.AppAIAgent._choose_with_state

    def stop(
        self: AppAIAgent,
        state: GameState,
        observation: object,
        actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        decision = state.decision_stack[-1].decision
        if (
            isinstance(decision, PlayerDecision)
            and decision.owner == seat
            and any(
                a.action_id == "choose_leader_signet_influence"
                and dict(a.arguments).get("box") == 1
                for a in actions
            )
        ):
            raise _Reached(state, observation, actions, self)
        return original(self, state, observation, actions)  # type: ignore[arg-type]

    def no_fallback(self: AppAIAgent, key: str, legal: object) -> DomainAction:
        raise AssertionError(f"fallback {key}")

    monkeypatch.setattr(app_agent.AppAIAgent, "_choose_with_state", stop)
    with pytest.raises(_Reached) as reached:
        run_policy_game(UprisingRulesEngine(), config, seed, agents)
    monkeypatch.setattr(app_agent.AppAIAgent, "_choose_with_state", original)
    monkeypatch.setattr(app_agent.AppAIAgent, "_random_answer", no_fallback)
    state, observation, actions, ai = reached.value.args
    assert state.players[seat].leader_id == "tessia_vernius"
    chosen = ai._choose_with_state(state, observation, actions)
    assert chosen.action_id == "choose_leader_signet_influence"
