"""The app AI on the original game's Arrakeen Scouts (stage P8): the
app-style answers of the new items (docs/app-ai-plan.md 15)."""

from collections.abc import Callable

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import scouts as sc
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo, abilities_of
from dune_imperium.agents.app_ai.catalog import (
    intrigue_entity,
    scouts_line_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import handler_for, scouts
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine, _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts_auctions import legal_call_actions, offer_call
from dune_imperium.rules.scouts_effects import (
    MENTAT_AWAY,
    legal_scouts_effect_actions,
    push_scouts_effect,
)
from dune_imperium.rules.scouts_missions import offer_mission_join
from dune_imperium.rules.scouts_secrets import (
    legal_secret_pick_actions,
    offer_secret_pick,
)

ORIGINAL_SCOUTS = RulesetConfig(base_game=BaseGame.IMPERIUM, arrakeen_scouts=True)
ENGINE = UprisingRulesEngine()


def _seat(state: GameState) -> int:
    return make_profile(state).ctx.seat


def _mentat_call(auction_id: str, solari: int, spice: int) -> tuple[GameState, int]:
    state = first_decision("turn", config=ORIGINAL_SCOUTS)
    seat = _seat(state)
    state = with_player(
        state, seat, resources=Resources(solari=solari, spice=spice, water=0)
    )
    state = with_state(state, scouts_item=auction_id)
    return offer_call(state, seat, source="test:call").state, seat


@pytest.mark.parametrize("auction_id", ["mentat_mid", "mentat_late"])
def test_the_mentat_call_is_the_mentat_evaluator(auction_id: str) -> None:
    """The open Mentat auction (OQ-162): the largest offered call whose
    price the prize still covers (plan §11.4), else a pass."""

    state, seat = _mentat_call(auction_id, solari=9, spice=9)
    legal = legal_call_actions(state, seat)
    p = make_profile(state, seat)
    run = DecisionRun(p.ctx, p, legal, p.rng, Memory())
    amounts = [int(str(dict(a.arguments)["count"])) for a in legal]
    expected = sc.MentatCallEvaluator.evaluate(
        make_profile(state, seat), auction_id, amounts
    )
    action = scouts.scouts_call(run)
    assert action is not None
    assert dict(action.arguments)["count"] == expected.response[0][0]  # type: ignore[index]


def test_the_mentat_call_stays_within_the_prize() -> None:
    state, seat = _mentat_call("mentat_mid", solari=9, spice=0)
    p = make_profile(state, seat)
    worth = sc.MentatCallEvaluator.prize_value(p, "mentat_mid")
    assert worth == p.mentat_value()  # the Mentat rests at the auction
    call = sc.MentatCallEvaluator.evaluate(p, "mentat_mid", range(10)).response
    assert call is not None
    amount = call[0][0]
    assert isinstance(amount, int)
    if amount:
        assert worth + p.solari_value(-amount) > 0.0
    assert worth + p.solari_value(-(amount + 1)) <= 0.0 or amount == 9
    late = sc.MentatCallEvaluator.prize_value(p, "mentat_late")
    assert late == worth + p.card_draw_value()


def test_two_influence_with_one_faction_values_two() -> None:
    """Political Affairs: 2 Influence with one Faction of choice, valued
    and picked at 2 (``GetGainInfluenceValue(..., 2)``)."""

    p = make_profile(first_decision("turn", config=ORIGINAL_SCOUTS))
    line = scouts_line_entity("political_affairs", 0, p.ctx.seat)
    [ability] = [
        a for a in abilities_of(line) if isinstance(a, sc.GainTwoInfluenceAbility)
    ]
    assert ability.value_for_player(p).sum == g.gain_any_influence_value(p, 2).sum
    tracks = tuple(track_entity(f) for f in FACTIONS)
    answer = ability.evaluate(p, Request((TargetInfo(entities=tracks),)))
    values = [p.gain_influence_value(f, 2, -1, False).sum for f in FACTIONS]
    best = FACTIONS[values.index(max(values))]
    assert answer.response == ((best,),)


def test_an_intrigue_discard_is_priced_and_picked_as_a_trash() -> None:
    """Rotating Doors and Intriguing Gift discard an Intrigue: the card
    leaves the hand as a trashed one does (plan §11.4's precedent)."""

    state = first_decision("turn", config=ORIGINAL_SCOUTS)
    seat = _seat(state)
    held = state.intrigue_deck[:3]
    state = with_player(state, seat, intrigue_cards=held)
    p = make_profile(state, seat)
    line = scouts_line_entity("intriguing_gift", 0, seat)
    [discard] = [
        a for a in abilities_of(line) if isinstance(a, sc.DiscardIntrigueCostAbility)
    ]
    trash = sc.TrashIntrigueCostAbility(line)
    assert discard.value_for_player(p).sum == trash.value_for_player(p).sum
    request = Request(
        (TargetInfo(entities=tuple(intrigue_entity(c, seat) for c in held)),)
    )
    assert (
        discard.evaluate(make_profile(state, seat), request).response
        == trash.evaluate(make_profile(state, seat), request).response
    )


def test_the_mentat_away_line_picks_its_influence() -> None:
    """The middle Mentat auction won with the Mentat away: one Influence of
    choice (OQ-162 (1)), the Faction ``GainAnyInfluenceAbility`` picks."""

    state = first_decision("turn", config=ORIGINAL_SCOUTS)
    seat = _seat(state)
    # Fremen at 3: one more reaches the Alliance, the best of the four.
    state = with_player(state, seat, influence=Influence(fremen=3))
    state = with_state(state, scouts_item="mentat_mid")
    state = push_scouts_effect(state, seat, "mentat_mid", MENTAT_AWAY, source="test")
    legal = legal_scouts_effect_actions(state, seat)
    assert {a.action_id for a in legal} == {"scouts_choose_faction"}
    p = make_profile(state, seat)
    run = DecisionRun(p.ctx, p, legal, p.rng, Memory())
    action = scouts.scouts_effect(run)
    assert action is not None
    factions = [str(dict(a.arguments)["faction"]) for a in legal]
    values = [p.gain_influence_value(f, 1, -1, False).sum for f in factions]
    assert dict(action.arguments)["faction"] == factions[values.index(max(values))]
    assert dict(action.arguments)["faction"] == "fremen"


@pytest.mark.parametrize("pick", [1, 3])
def test_a_covert_operation_pick_names_its_best_faction(pick: int) -> None:
    """The original Covert Operation's second and fourth lines name their
    Faction at the pick (9a): the line's Influence ability answers it."""

    state = first_decision("turn", config=ORIGINAL_SCOUTS)
    seat = _seat(state)
    event_id = "imperium_covert_operation"
    # Fremen at 3: one or two more are worth the most there, not in the
    # first Faction offered.
    state = with_player(state, seat, influence=Influence(fremen=3))
    state = offer_secret_pick(state, seat, event_id, source="test").state
    legal = tuple(
        a
        for a in legal_secret_pick_actions(state, seat)
        if dict(a.arguments)["pick"] == pick
    )
    assert len(legal) == len(FACTIONS)
    p = make_profile(state, seat)
    run = DecisionRun(p.ctx, p, legal, p.rng, Memory())
    action = scouts.scouts_secret(run)
    assert action is not None
    factions = [str(dict(a.arguments)["faction"]) for a in legal]
    gained = 1 if pick == 1 else 2
    values = [p.gain_influence_value(f, gained, -1, False).sum for f in factions]
    assert dict(action.arguments)["faction"] == factions[values.index(max(values))]
    assert dict(action.arguments)["faction"] == "fremen"


def _window(
    state: GameState, seat: int
) -> tuple[Callable[[DecisionRun], DomainAction | None], DecisionRun]:
    """The app AI's window for the top frame, as the agent dispatches it,
    and its run over the engine's offer."""

    handler = handler_for(str(state.decision_stack[-1].kind))
    assert handler is not None
    p = make_profile(state, seat)
    return handler, DecisionRun(
        p.ctx, p, ENGINE.whole_actions(state, seat), p.rng, Memory()
    )


@pytest.mark.parametrize("worth", [50.0, -50.0])
def test_strongarmed_alliance_returns_a_specimen_when_its_troop_is_worth_it(
    worth: float,
) -> None:
    """Strongarmed Alliance with an empty supply and specimens in the tanks
    asks only whether to return one (9a, OQ-074 (a)): the troop way of
    ``MissionJoinEvaluator`` -- the line's troop plus ``Spec(-1)`` -- or the
    pass."""

    config = RulesetConfig(
        base_game=BaseGame.IMPERIUM, arrakeen_scouts=True, immortality=True
    )
    state = first_decision("turn", config=config)
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        troops_supply=0,
        troops_garrison=me.troops_garrison + me.troops_supply - 2,
        specimens=2,
    )
    mission = "muster_strongarmed_alliance"
    state = offer_mission_join(state, seat, mission, source="test").state
    handler, run = _window(state, seat)
    assert {a.action_id for a in run.legal} == {
        "scouts_decline_mission",
        "scouts_return_specimens",
    }
    run.profile.scouts_line_value = lambda *_a, **_k: Summer(worth)  # type: ignore[method-assign]
    action = handler(run)
    assert action is not None
    if worth < 0:
        assert action.action_id == "scouts_decline_mission"
        return
    assert action == DomainAction(
        action_id="scouts_return_specimens", actor=seat, arguments=(("count", 1),)
    )
    after = apply_whole(ENGINE, state, action).state
    assert (after.players[seat].specimens, after.players[seat].troops_parked) == (1, 1)


def test_fremen_exchange_loses_the_least_valued_unit() -> None:
    """Fremen Exchange's troop line (OQ-163): the unit-loss window the seat
    opens itself, answered as Holy War's victim is -- the offered unit with
    the smallest ``LoseUnitValue`` (``LoseTroopsCostAbility``, plan §11.5)."""

    state = first_decision("turn", config=ORIGINAL_SCOUTS)
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        troops_garrison=3,
        troops_conflict=2,
        combat_strength=4,
        troops_supply=me.troops_supply + me.troops_garrison - 5,
    )
    state = push_scouts_effect(state, seat, "fremen_exchange", 0, source="test")
    state = _advance_automatic(RuleResult(state=state)).state
    assert state.decision_stack[-1].kind == FrameKind.OPPONENT_UNIT_LOSS
    handler, run = _window(state, seat)
    action = handler(run)
    assert action is not None and action.action_id == "lose_unit"
    zones = [str(dict(a.arguments)["zone"]) for a in run.legal]
    assert zones == ["garrison", "conflict"]
    values = [run.profile.lose_unit_value(zone, False) for zone in zones]
    assert dict(action.arguments)["zone"] == zones[values.index(min(values))]
