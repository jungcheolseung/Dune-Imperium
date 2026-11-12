"""Kept answers of pure lookups equal fresh ones (2026-11-11 engine speed, stage A).

``content.core.kept.kept_by_id`` keeps the content resolvers' answers by
instance id, ``rules.effect_steps`` keeps ``steps_for`` by its exact
arguments and ``decode_pick`` by its string, and ``rules.effects`` keeps
``_icon_keys``'s split. Each must return exactly what the function computes
afresh -- the same objects for the resolvers, values equal down to their
types (``True`` is not ``1``) for the rest -- and must keep nothing for a
call that raises.
"""

from collections.abc import Callable

import pytest
from tests.unit.rules.test_kept_answers import FULL, IMPERIUM_IX, played_states

from dune_imperium.config import RulesetConfig
from dune_imperium.content.bloodlines.sardaukar import skill_for_instance
from dune_imperium.content.immortality.tleilaxu import tleilaxu_card_for_instance
from dune_imperium.content.registry.imperium import imperium_card_for_instance
from dune_imperium.content.registry.personal_cards import personal_card_for_instance
from dune_imperium.content.registry.reserve import reserve_card_for_instance
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.rules import effect_steps, effects
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.engine import UprisingRulesEngine

RESOLVERS: tuple[Callable[[str], object], ...] = (
    personal_card_for_instance,
    imperium_card_for_instance,
    reserve_card_for_instance,
    starting_card_for_instance,
    tleilaxu_card_for_instance,
    skill_for_instance,
)


def _card_ids(config: RulesetConfig, seed: int) -> set[str]:
    ids: set[str] = set()
    for state in played_states(config, seed, 300):
        ids.update(state.imperium_row, state.tleilaxu_row)
        for seat in state.players:
            ids.update(seat.deck, seat.hand, seat.discard_pile, seat.in_play)
            ids.update(seat.trashed, seat.skill_ids)
    return ids


@pytest.mark.parametrize(("config", "seed"), [(FULL, 21), (IMPERIUM_IX, 22)])
def test_kept_resolvers_return_the_resolvers_own_objects(
    config: RulesetConfig, seed: int
) -> None:
    ids = _card_ids(config, seed)
    resolved = 0
    for instance_id in sorted(ids):
        for resolver in RESOLVERS:
            fresh = resolver.__wrapped__  # type: ignore[attr-defined]
            try:
                expected = fresh(instance_id)
            except ValueError, NotImplementedError:
                with pytest.raises((ValueError, NotImplementedError)):
                    resolver(instance_id)
                continue
            assert resolver(instance_id) is expected
            assert resolver(instance_id) is expected
            resolved += 1
    assert resolved > 50


@pytest.mark.parametrize("resolver", RESOLVERS)
def test_a_resolver_keeps_no_failure(resolver: Callable[[str], object]) -> None:
    fresh = resolver.__wrapped__  # type: ignore[attr-defined]
    for bad in ("imperium:no_such_card:0", "player:0:starter:nothing:0", "x", ""):
        for _ in range(2):
            with pytest.raises(Exception) as kept:
                resolver(bad)
            with pytest.raises(Exception) as direct:
                fresh(bad)
            assert type(kept.value) is type(direct.value)
            assert str(kept.value) == str(direct.value)


def test_a_resolver_passes_other_arguments_through() -> None:
    for argument in (None, 7):
        with pytest.raises(Exception) as kept:
            personal_card_for_instance(argument)  # type: ignore[arg-type]
        with pytest.raises(Exception) as direct:
            personal_card_for_instance.__wrapped__(argument)  # type: ignore[attr-defined]
        assert type(kept.value) is type(direct.value)
        assert str(kept.value) == str(direct.value)


@pytest.mark.parametrize(("config", "seed"), [(FULL, 23), (IMPERIUM_IX, 24)])
def test_kept_steps_equal_fresh_ones_through_a_game(
    config: RulesetConfig, seed: int
) -> None:
    """Every whole action's path, worked out with the steps kept (twice, the
    second from the table) and afresh, is the same down to its values' types."""

    engine = UprisingRulesEngine()
    compared = 0
    for state in played_states(config, seed, 400):
        decision = engine.current_decision(state)
        if not isinstance(decision, PlayerDecision) or not effect_steps.presents_steps(
            state
        ):
            continue
        rules_state = effect_steps.without_pick(state)
        for whole in engine._rules_of(state, decision.owner):
            effect_steps._KEPT_STEPS.clear()
            first = effect_steps._path_of(rules_state, whole)
            second = effect_steps._path_of(rules_state, whole)
            original = effect_steps.steps_for
            effect_steps.steps_for = effect_steps._steps_for
            try:
                fresh = effect_steps._path_of(rules_state, whole)
            finally:
                effect_steps.steps_for = original
            assert repr(first) == repr(fresh)
            assert repr(second) == repr(fresh)
            compared += first is not None
    assert compared > 100


def test_steps_are_kept_only_under_exact_arguments() -> None:
    whole = DomainAction("gain", 0, (("count", 1),))
    assert effect_steps._steps_key(whole, "card", Source.AGENT_CARD, True, None)
    assert effect_steps._steps_key(whole, None, None, False, "water")
    flagged = DomainAction("gain", 0, (("count", True),))
    assert effect_steps._steps_key(flagged, "card", None, True, None) is None
    assert effect_steps._steps_key(whole, True, None, True, None) is None
    assert effect_steps._steps_key(whole, "card", "agent_card", True, None) is None  # type: ignore[arg-type]
    assert effect_steps._steps_key(whole, "card", None, 1, None) is None  # type: ignore[arg-type]


def test_a_failing_step_keeps_nothing() -> None:
    effect_steps._KEPT_STEPS.clear()
    whole = DomainAction("pay_agent_card_spice", 0)
    for _ in range(2):
        with pytest.raises(ValueError, match="needs its printed entity"):
            effect_steps.steps_for(whole)
    assert not effect_steps._KEPT_STEPS


def test_kept_icon_keys_and_picks_equal_fresh_ones() -> None:
    context: dict[str, ActionValue] = {"pending_agent_icons": "water,,cards", "bad": 3}
    keys = effects._icon_keys(context, "pending_agent_icons")
    assert keys == ("water", "cards")
    assert effects._icon_keys(dict(context), "pending_agent_icons") is keys
    assert effects._icon_keys(context, "missing") == ()
    for _ in range(2):
        with pytest.raises(RuntimeError, match="invalid bad"):
            effects._icon_keys(context, "bad")
    encoded = '[["gain",[["count",1],["flag",true]]]]'
    rows = effect_steps.decode_pick(encoded)
    assert repr(rows) == repr(effect_steps._decode_pick(encoded))
    assert repr(rows) == "(('gain', (('count', 1), ('flag', True))),)"
    assert effect_steps.decode_pick(encoded) is rows
    for _ in range(2):
        with pytest.raises(ValueError):
            effect_steps.decode_pick("not json")


def test_odd_arguments_are_worked_out_as_before_and_not_kept() -> None:
    """Codex review r1: arguments in a list (which ``DomainAction`` accepts) and
    a malformed pick that decodes to a list take the old path, unkept."""

    effect_steps._KEPT_STEPS.clear()
    listed = DomainAction("deploy_intrigue_troops", 0, [("count", 1)])  # type: ignore[arg-type]
    assert effect_steps._steps_key(listed, None, None, True, None) is None
    assert repr(effect_steps.steps_for(listed)) == repr(effect_steps._steps_for(listed))
    assert not effect_steps._KEPT_STEPS
    malformed = "[[[],[]]]"
    first = effect_steps.decode_pick(malformed)
    assert malformed not in effect_steps._KEPT_PICKS
    first[0][0].append("changed")  # type: ignore[attr-defined]
    again: object = effect_steps.decode_pick(malformed)
    assert again == (([], ()),)


def test_long_strings_are_not_kept_so_the_digit_limit_still_applies() -> None:
    """Codex review r4: a string long enough to hold an integer of the parsing
    limit's lowest possible length is worked out every time."""

    import sys

    long_pick = '[["gain",[["count",' + "7" * 700 + "]]]]"
    long_id = "imperium:no_such_card:" + "1" * 700
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(0)
        effect_steps.decode_pick(long_pick)
        with pytest.raises(ValueError):
            personal_card_for_instance(long_id)
        sys.set_int_max_str_digits(640)
        with pytest.raises(ValueError):
            effect_steps.decode_pick(long_pick)
    finally:
        sys.set_int_max_str_digits(previous)
    assert long_pick not in effect_steps._KEPT_PICKS
