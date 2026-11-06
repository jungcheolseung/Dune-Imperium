"""The Freighter and the Shipping track (abilities/ix_board.py, windows/ix.py;
docs/app-ai-plan.md §13): ``GetFreighterSelections``/``get_FreighterValue``
(spec/rix-tech.md §4.6-4.7) and the ports that answer with them."""

from collections.abc import Sequence
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Request,
    SelectionMode,
)
from dune_imperium.agents.app_ai.abilities.generic import GainAnyInfluenceAbility
from dune_imperium.agents.app_ai.abilities.ix_board import (
    FreighterAgentAbility,
    FreighterCustomAbility,
    FreighterRevealAbility,
    ShippingTrackAbility1,
    ShippingTrackAbility2,
    ShippingTrackAbility3,
)
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
)
from dune_imperium.agents.app_ai.windows import ix
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.config import BaseGame
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
OWNER = Entity(Kind.SPACE, "shipping_track", None, 0)


def _state(**changes: object) -> tuple[GameState, int]:
    state = first_decision("turn", config=IX)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    return with_player(state, seat, **changes), seat


def _profile(**changes: object) -> Profile:
    state, seat = _state(**changes)
    return make_profile(state, seat)


def test_the_freighter_classes_are_registered_with_their_app_names() -> None:
    aa = "worm.canis.abilities.ActivatedAbilities.RiseOfIx."
    assert PORTS[aa + "FreighterAgentAbility"] is FreighterAgentAbility
    assert PORTS[aa + "FreighterRevealAbility"] is FreighterRevealAbility
    assert PORTS[aa + "FreighterCustomAbility"] is FreighterCustomAbility
    assert PORTS[aa + "ShippingTrackAbility1"] is ShippingTrackAbility1
    assert PORTS[aa + "ShippingTrackAbility2"] is ShippingTrackAbility2
    assert PORTS[aa + "ShippingTrackAbility3"] is ShippingTrackAbility3
    assert issubclass(ShippingTrackAbility2, GainAnyInfluenceAbility)


@pytest.mark.parametrize("space", [0, 1, 2, 3])
def test_selections_by_track_space(space: int) -> None:
    p = _profile(freighter_space=space)
    recall, choice, _log = p.freighter_selections(-1)
    if space == 0:
        assert (recall, choice) == (0, 0)
    elif space == 3:
        assert recall == 1
        assert choice == int(not p.is_solari_short())
    elif space == 1 and not p.is_final_round():
        assert recall in (0, 1)
    assert p.freighter_selections(space)[:2] == (recall, choice) or space == 2


def test_level_one_recalls_for_the_swordmaster_with_three_to_seven_solari() -> None:
    state, seat = _state(freighter_space=1)
    me = state.players[seat]
    for solari, expected in ((2, None), (3, (1, 0)), (7, (1, 0))):
        changed = with_player(
            state, seat, resources=replace(me.resources, solari=solari)
        )
        got = make_profile(changed, seat).freighter_selections(-1)
        if expected is not None:
            assert got[:2] == expected
            assert got[2] == "Level 1 - No Swordmaster"
        else:
            assert got[2] != "Level 1 - No Swordmaster"


def test_level_two_draws_the_match_coin_before_the_climax() -> None:
    p = _profile(freighter_space=2)
    if p.is_climax():
        assert p.freighter_selections(-1)[0] == 1
    else:
        draws = {p.freighter_selections(-1)[0] for _ in range(32)}
        assert draws == {0, 1}


def test_freighter_value_is_immediacy_when_recalling() -> None:
    p = _profile(freighter_space=3)
    c = p.C
    arc = (c.FreighterEarly, c.FreighterMid, c.FreighterLate)[p.game_arc()]
    assert p.freighter_value() == pytest.approx(c.ImmediacyModValue * arc)
    q = _profile(freighter_space=0)
    assert q.freighter_value() == pytest.approx(
        (c.FreighterEarly, c.FreighterMid, c.FreighterLate)[q.game_arc()]
    )


def test_freighter_ability_answers_item1_at_freighter_value() -> None:
    p = _profile(freighter_space=3)
    ability = FreighterCustomAbility(OWNER)
    assert ability.selection_mode(p) is SelectionMode.EXPLICIT
    assert ability.value_for_player(p).sum == pytest.approx(p.freighter_value())
    answer = ability.evaluate(p, Request())
    assert answer.response == ((1,),)
    assert answer.value == pytest.approx(p.freighter_value())


def test_shipping_track_one_answers_item2_of_the_recall_space() -> None:
    p = _profile(resources=Resources(solari=0, spice=0, water=0))
    answer = ShippingTrackAbility1(OWNER, 3).evaluate(p, Request())
    assert answer.value == 100.0
    assert answer.response == ((int(not p.is_solari_short()),),)
    assert ShippingTrackAbility3(OWNER).evaluate(p, Request()).value == 100.0


def _run(state: GameState, seat: int, actions: Sequence[DomainAction]) -> DecisionRun:
    p = make_profile(state, seat)
    return DecisionRun(p.ctx, p, tuple(actions), p.rng, Memory())


def test_freighter_move_window_recalls_from_the_top_and_advances_from_the_bottom() -> (
    None
):
    for space, expected in ((3, ix.RECALL), (0, ix.ADVANCE)):
        state, seat = _state(freighter_space=space)
        actions = [
            DomainAction(action_id=a, actor=seat)
            for a in (ix.ADVANCE, ix.RECALL, ix.DECLINE)
            if not (space == 3 and a == ix.ADVANCE)
        ]
        chosen = ix.freighter_move(_run(state, seat, actions))
        assert chosen is not None and chosen.action_id == expected


def test_shipping_window_takes_space_one_by_item2_first() -> None:
    state, seat = _state()
    rows = [
        DomainAction(action_id=ix.REWARD, actor=seat, arguments=(("effect", e),))
        for e in ("dividends", "spice", "tech")
    ]
    run = _run(state, seat, rows)
    chosen = ix.shipping_reward_icons(run)
    assert chosen is not None
    effect = dict(chosen.arguments)["effect"]
    item2 = run.profile.freighter_selections(3)[1]
    assert effect in ("dividends", "spice", "tech")
    if effect != "tech":
        assert effect == ("dividends" if item2 == 0 else "spice")
