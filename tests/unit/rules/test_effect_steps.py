"""Stage B3: a waiting effect is picked before its target.

docs/stage-b-plan.md 3c ("B3a 세부 설계"), OQ-111: the Agent-turn effect
frame shows each whole action -- an effect and its target, as the rules
resolve it -- as an effect row (the verb and the place that points at the
effect) and then its target rows. The pick waits in the frame's context:
only its seat sees it (OQ-111 (4)), the turn's other effects and its end
wait for it, and one target still opens the target step (OQ-111 (2)).
"""

from dataclasses import replace

import pytest
from tests.unit.rules.test_board_effects import _espionage_state

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.core import DomainAction, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import (
    first_step,
    path_of,
    picked_rows,
    steps_for,
)

ENGINE = UprisingRulesEngine()
_PLACE = "resolve_espionage_place_spy"


def _ref(icon: str) -> tuple[tuple[str, str], ...]:
    return (("icon", icon), ("printed", "espionage"), ("source", "board_space"))


def test_each_waiting_effect_is_one_effect_row() -> None:
    state, _ = _espionage_state()

    rows = ENGINE.legal_actions(state, 0)

    # Espionage's draw and its Spy [Board Guide p. 1] wait as two effects
    # (OQ-027): the draw has no target and its row resolves it; the Spy
    # opens its posts.
    assert DomainAction("draw", 0, _ref("cards")) in rows
    assert DomainAction("place_spy", 0, _ref("spy")) in rows
    assert not any(row.action_id.startswith("choose_") for row in rows)
    assert not any(row.action_id == _PLACE for row in rows)
    # The whole actions behind the rows are the rules' own list.
    assert any(whole.action_id == _PLACE for whole in ENGINE.whole_actions(state, 0))


def test_a_picked_effect_offers_only_its_targets() -> None:
    state, _ = _espionage_state()
    spy = DomainAction("place_spy", 0, _ref("spy"))

    picked = ENGINE.apply(state, spy).state
    rows = ENGINE.legal_actions(picked, 0)

    posts = {
        dict(whole.arguments)["post_id"]
        for whole in ENGINE.whole_actions(state, 0)
        if whole.action_id == _PLACE
    }
    assert set(rows) == {
        DomainAction("choose_post", 0, (("post_id", post),)) for post in posts
    }
    # Nothing else of the turn -- the draw, the turn's end -- comes in between.
    assert picked_rows(picked) == (spy,)
    assert {whole.action_id for whole in ENGINE.whole_actions(picked, 0)} == {_PLACE}


def test_the_last_step_applies_the_whole_action() -> None:
    state, _ = _espionage_state()
    whole = next(w for w in ENGINE.whole_actions(state, 0) if w.action_id == _PLACE)
    post = dict(whole.arguments)["post_id"]

    stepped = apply_whole(ENGINE, state, whole)

    owner = stepped.state.players[0]
    assert post in owner.spy_post_ids
    assert owner.spies_supply == state.players[0].spies_supply - 1
    assert picked_rows(stepped.state) == ()
    assert [event.kind for event in stepped.events].count("effect_picked") == 1
    # The rules' handler ran on the state without the pick: the rest of the
    # visit (its draw) still waits.
    assert DomainAction("draw", 0, _ref("cards")) in ENGINE.legal_actions(
        stepped.state, 0
    )


def test_one_target_still_opens_the_target_step() -> None:
    # An empty supply with one Spy on a post: the recall-first has one post
    # to take it from [Main pp. 11, 20] (the other two are boxed, as
    # Advanced Data Analysis leaves them).
    state = _recall_state()
    owner = state.players[0]
    post = owner.spy_post_ids[0]
    owner = replace(owner, spy_post_ids=(post,), spies_boxed=2)
    state = replace(
        state,
        config=replace(state.config, bloodlines=True, tech_module=True),
        players=(owner, *state.players[1:]),
    )
    recall = DomainAction("recall_spy", 0, _ref("spy"))
    assert recall in ENGINE.legal_actions(state, 0)

    picked = ENGINE.apply(state, recall).state

    assert ENGINE.legal_actions(picked, 0) == (
        DomainAction("choose_post", 0, (("post_id", post),)),
    )


def test_only_the_seat_sees_its_picked_effect() -> None:
    state, _ = _espionage_state()
    spy = DomainAction("place_spy", 0, _ref("spy"))

    picked = ENGINE.apply(state, spy).state

    own = ENGINE.observe(picked, 0)
    assert own.private is not None
    assert own.private.effect_pick == ((spy.action_id, spy.arguments),)
    for seat in (1, 2, 3):
        before, after = ENGINE.observe(state, seat), ENGINE.observe(picked, seat)
        assert replace(after, revision=before.revision) == before
        assert encode_player_view(replace(after, revision=before.revision)) == (
            encode_player_view(before)
        )
    # The seat's own observation reads the pick (observation v33).
    assert encode_player_view(own) != encode_player_view(
        replace(ENGINE.observe(state, 0), revision=own.revision)
    )


def test_the_pick_event_is_the_seats_alone() -> None:
    state, _ = _espionage_state()

    result = ENGINE.apply(state, DomainAction("place_spy", 0, _ref("spy")))

    (event,) = result.events
    assert event.kind == "effect_picked"
    assert event.visible_to == (0,)


def test_a_row_that_is_no_step_of_an_offered_action_is_refused() -> None:
    state, _ = _espionage_state()
    picked = ENGINE.apply(state, DomainAction("place_spy", 0, _ref("spy"))).state

    with pytest.raises(Exception, match="not legal"):
        ENGINE.apply(picked, DomainAction("draw", 0, _ref("cards")))


def test_the_steps_name_targets_by_their_kind() -> None:
    state, _ = _espionage_state()
    whole = next(w for w in ENGINE.whole_actions(state, 0) if w.action_id == _PLACE)

    path = path_of(state, whole)

    assert path == steps_for(whole, "espionage")
    assert path is not None
    assert [row.action_id for row in path] == ["place_spy", "choose_post"]
    assert first_step(state, whole) == path[0]


def _recall_state() -> GameState:
    state, _ = _espionage_state(spies_supply=0)
    return state


def test_a_recall_first_is_its_own_effect_row() -> None:
    state = _recall_state()

    rows = ENGINE.legal_actions(state, 0)

    # With an empty supply the Spy's recall comes first [Main pp. 11, 20].
    assert DomainAction("recall_spy", 0, _ref("spy")) in rows
    picked = ENGINE.apply(state, DomainAction("recall_spy", 0, _ref("spy"))).state
    assert {row.action_id for row in ENGINE.legal_actions(picked, 0)} == {
        "choose_post"
    }
