"""Post-transition hooks do what they did before stage C (2026-11-11 engine speed).

Stage C made a few hooks and automatic-step predicates do less work when
nothing is due: the Skill strength lines are read once per tile, the
revealing seats are found in one pass, deployment peaks and public deck tops
build no tuple when no seat changes, and two Arrakeen Scouts predicates skip
what cannot be due. Each hook is wrapped here while seeded games of both
boards play, and every input the engine hands it is also given to the
function as it was before stage C (copied below): the answers must be equal,
and a hook that returned its input unchanged must still return that very
object.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from copy import replace
from typing import Any

import pytest
from tests.unit.rules.test_kept_answers import FULL, IMPERIUM_IX, played_states

from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.bloodlines.sardaukar import skill_for_instance
from dune_imperium.content.core.abilities import AbilityTiming
from dune_imperium.content.core.effects import (
    AgentOnSpaceWithIcon,
    Condition,
    GainCombatStrength,
    InfluenceAtLeast,
    OpponentSandwormInConflict,
)
from dune_imperium.content.registry.board import BOARD_SPACES_BY_ID
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import (
    combat_deployment,
    deck_top,
    scouts_effects,
    scouts_missions,
    strength,
)
from dune_imperium.rules import engine as rules_engine
from dune_imperium.rules.deck_top import settle_deck_top
from dune_imperium.rules.influence import influence_amount
from dune_imperium.rules.scouts_effects import _payout_open
from dune_imperium.rules.scouts_missions import (
    _escort_due,
    _post_occupant,
    owed_payouts,
)
from dune_imperium.rules.strength import (
    _shift_reveal_strength,
    reveal_in_progress,
    units_strength,
)

IX_BLOODLINES = RulesetConfig(
    rise_of_ix=True,
    leader_draft=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    arrakeen_scouts=True,
)
IMPERIUM_BLOODLINES = RulesetConfig(
    base_game=BaseGame.IMPERIUM,
    rise_of_ix=True,
    bloodlines=True,
    arrakeen_scouts=True,
)

# --- the functions as they were before stage C ------------------------------


def _old_skill_strength(players: tuple[PlayerState, ...], player: int) -> int:
    owner = players[player]
    if owner.commanders_conflict <= 0 or not owner.skill_ids:
        return 0

    def holds(condition: Condition | None) -> bool:
        match condition:
            case None:
                return True
            case AgentOnSpaceWithIcon(icon=icon):
                return any(
                    BOARD_SPACES_BY_ID[space_id].agent_icon is icon
                    for space_id in owner.agent_locations
                    if space_id in BOARD_SPACES_BY_ID
                )
            case OpponentSandwormInConflict():
                return any(
                    candidate.sandworms_conflict > 0
                    for candidate in players
                    if candidate.player_id != player
                )
            case InfluenceAtLeast(faction=faction, amount=amount):
                return influence_amount(owner.influence, faction) >= amount
        raise ValueError(f"no Skill strength checks {condition!r}")

    total = 0
    for instance_id in owner.skill_ids:
        ability = skill_for_instance(instance_id).ability
        if ability.timing is not AbilityTiming.IN_CONFLICT:
            continue
        for line in ability.sections:
            if holds(line.condition):
                total += sum(
                    reward.amount
                    for reward in line.rewards
                    if isinstance(reward, GainCombatStrength)
                )
    return total


def _old_with_skill_strength(
    players: tuple[PlayerState, ...], player: int
) -> PlayerState:
    owner = players[player]
    if owner.units_in_conflict <= 0:
        if owner.skill_strength_applied == 0:
            return owner
        return replace(owner, skill_strength_applied=0)
    target = _old_skill_strength(players, player)
    if target == owner.skill_strength_applied:
        return owner
    return replace(
        owner,
        combat_strength=owner.combat_strength - owner.skill_strength_applied + target,
        skill_strength_applied=target,
    )


def _old_refresh_pre_reveal_strength(result: RuleResult) -> RuleResult:
    state = result.state
    if state.phase not in (
        GamePhase.ROUND_START,
        GamePhase.PLAYER_TURNS,
        GamePhase.COMBAT,
    ):
        return result
    if state.phase is GamePhase.COMBAT and state.combat_end_triggers_offered:
        return result
    players = list(state.players)
    stack = state.decision_stack
    for player in state.players:
        seat = player.player_id
        if (
            state.phase is not GamePhase.COMBAT
            and not player.has_revealed
            and not reveal_in_progress(state, seat)
        ):
            base = units_strength(player)
            if player.combat_strength != base or player.skill_strength_applied:
                players[seat] = replace(
                    player, combat_strength=base, skill_strength_applied=0
                )
        if not state.config.bloodlines:
            continue
        before = players[seat].combat_strength
        players[seat] = _old_with_skill_strength(tuple(players), seat)
        if players[seat].combat_strength != before:
            stack = _shift_reveal_strength(
                stack, seat, players[seat].combat_strength - before
            )
    next_players = tuple(players)
    if next_players == state.players and stack == state.decision_stack:
        return result
    return replace(
        result, state=replace(state, players=next_players, decision_stack=stack)
    )


def _old_record_deployment_peak(result: RuleResult) -> RuleResult:
    state = result.state
    players = tuple(
        combat_deployment._raise_peaks(state, seat) for seat in state.players
    )
    if all(new is old for new, old in zip(players, state.players, strict=True)):
        return result
    return RuleResult(state=replace(state, players=players), events=result.events)


def _old_settle_public_deck_tops(state: GameState) -> GameState:
    players = state.players
    settled = tuple(settle_deck_top(player) for player in players)
    if all(after is before for after, before in zip(settled, players, strict=True)):
        return state
    return replace(state, players=settled)


def _old_mission_goods_are_due(state: GameState) -> bool:
    if not state.scouts_goods:
        return False
    for row in state.scouts_goods:
        if row[1].startswith("post:") and _post_occupant(state, row[1]) is not None:
            return True
        if row[1].startswith("contract:") and _escort_due(state, row):
            return True
    return False


def _old_scouts_payout_is_due(state: GameState) -> bool:
    if state.decision_stack and isinstance(
        state.decision_stack[-1].decision, ChanceDecision
    ):
        return False
    return any(
        not _payout_open(state, seat, mission_id)
        for seat, mission_id in owed_payouts(state)
    )


# --- the comparison -----------------------------------------------------------


def _same(new: Any, old: Any, given: Any) -> None:
    assert new == old
    if old is given:
        assert new is given
    else:
        assert new is not given


@contextmanager
def _compared(
    module: Any, name: str, old: Callable[[Any], Any], seen: list[int]
) -> Iterator[None]:
    """Wrap ``module.name`` so every call also runs ``old`` and compares."""

    current = getattr(module, name)

    def both(given: Any) -> Any:
        new = current(given)
        _same(new, old(given), given)
        seen.append(1)
        return new

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module, name, both)
        yield


HOOKS: tuple[tuple[Any, str, Callable[[Any], Any]], ...] = (
    (rules_engine, "refresh_pre_reveal_strength", _old_refresh_pre_reveal_strength),
    (rules_engine, "record_deployment_peak", _old_record_deployment_peak),
    (rules_engine, "settle_public_deck_tops", _old_settle_public_deck_tops),
    (rules_engine, "mission_goods_are_due", _old_mission_goods_are_due),
    (rules_engine, "scouts_payout_is_due", _old_scouts_payout_is_due),
)


@pytest.mark.parametrize(
    ("config", "seed"),
    [(FULL, 41), (IX_BLOODLINES, 42), (IMPERIUM_BLOODLINES, 43), (IMPERIUM_IX, 44)],
)
@pytest.mark.parametrize(
    ("module", "name", "old"), HOOKS, ids=[hook[1] for hook in HOOKS]
)
def test_a_hook_answers_as_before_stage_c(
    config: RulesetConfig,
    seed: int,
    module: Any,
    name: str,
    old: Callable[[Any], Any],
) -> None:
    seen: list[int] = []
    assert hasattr(module, name)
    with _compared(module, name, old, seen):
        for _ in played_states(config, seed, 1500):
            pass
    assert seen


def test_the_skill_strength_is_the_old_one_on_every_seat() -> None:
    compared = 0
    for config, seed in ((FULL, 45), (IX_BLOODLINES, 46)):
        for state in played_states(config, seed, 1500):
            for seat in range(len(state.players)):
                assert strength.skill_strength(
                    state.players, seat
                ) == _old_skill_strength(state.players, seat)
                compared += bool(state.players[seat].skill_ids)
    assert compared > 100


def test_the_hooks_named_here_are_the_ones_the_engine_calls() -> None:
    # The engine imports each hook by name; the patched names above must be
    # those it calls (and their modules' own definitions).
    owners = {
        "refresh_pre_reveal_strength": strength,
        "record_deployment_peak": combat_deployment,
        "settle_public_deck_tops": deck_top,
        "mission_goods_are_due": scouts_missions,
        "scouts_payout_is_due": scouts_effects,
    }
    for name, owner in owners.items():
        assert getattr(rules_engine, name) is getattr(owner, name)


def test_odd_frame_kinds_or_owners_fall_back_to_the_per_seat_scan() -> None:
    """Codex review r2: the revealing owners are gathered in one pass only
    when no comparison can raise or have an effect; otherwise the refresh
    asks ``reveal_in_progress`` seat by seat, as before."""

    from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
    from dune_imperium.rules.frames import FrameKind

    state = next(
        s
        for s in played_states(FULL, 47, 400)
        if s.phase is GamePhase.PLAYER_TURNS and s.decision_stack
    )
    reveal = DecisionFrame(FrameKind.REVEAL, "r", PlayerDecision(2, "p"))
    plain = replace(state, decision_stack=(*state.decision_stack, reveal))
    assert strength._revealing_owners(plain) == (2,)

    class Owner(int):
        pass

    odd_owner = replace(
        state,
        decision_stack=(
            *state.decision_stack,
            DecisionFrame(FrameKind.REVEAL, "r", PlayerDecision(Owner(2), "p")),
        ),
    )
    assert strength._revealing_owners(odd_owner) is None
    for given in (plain, odd_owner):
        result = RuleResult(given)
        _same(
            strength.refresh_pre_reveal_strength(result),
            _old_refresh_pre_reveal_strength(result),
            result,
        )


def test_a_frame_subclass_falls_back_to_the_per_seat_scan() -> None:
    """Codex review r3: the one-pass scan reads only plain ``DecisionFrame``s."""

    from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
    from dune_imperium.rules.frames import FrameKind

    class Frame(DecisionFrame):
        __slots__ = ()

    state = next(
        s
        for s in played_states(FULL, 48, 400)
        if s.phase is GamePhase.PLAYER_TURNS and s.decision_stack
    )
    sub = Frame(FrameKind.REVEAL, "r", PlayerDecision(1, "p"))
    given = replace(state, decision_stack=(*state.decision_stack, sub))
    assert strength._revealing_owners(given) is None
    result = RuleResult(given)
    _same(
        strength.refresh_pre_reveal_strength(result),
        _old_refresh_pre_reveal_strength(result),
        result,
    )
