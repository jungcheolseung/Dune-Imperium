"""Records made by older engines replay on this one (records.migration).

Two kinds of evidence. Records made on *this* engine and then stripped of
what an older engine never recorded (its pauses, the Conflict-end windows
it never opened, the Combat Intrigue pass it never asked for, the draws
codec v142 split off into steps of their own) must come back step for step
through the bridges, while the codec gates keep each bridge away from
records that did meet the decision. And records made by the older engines
themselves (``data/``, written by ``scripts/records/old_engine_record.py``)
must replay to their end:
- master 37727846 (codec v135): ``v135-app_ai-3``;
- 5a2dfc19 (v139): ``v139-heuristic-1``;
- 6b033158 (v140): ``v140-heuristic-1``;
- 21eccca4 (v141): ``v141-heuristic-21`` (Imperial Privilege, each recall
  followed by its reshuffle), ``v141-heuristic-1023`` (a recall followed by
  a step the engine accepts; Insider Information; a Deep Desert summon for
  Arrakis Planetologist), ``v141-heuristic-150`` (Bene Gesserit
  Treachery with a troop and a Commander in the garrison; Piter) and
  ``v141-no-immortality-no-go_to_11-heuristic-1211`` (Prison Planet, a
  seat with only Commanders) and ``v141-no-immortality-no-go_to_11-app_ai-6005``
  (Prison Planet, a seat with a troop and a Commander, asked by both);
- a02e802a (v141, the same engine as 21eccca4): the eleven records of
  ``OQ106_FIXTURES``, one or more for each OQ-106 bridge.
Replayed on their own engines, the v141 ones match the migrated public
state at every recorded step (all seat fields), except the one step after
a Deep Desert summon for Arrakis Planetologist that sees the second
Intrigue card still held (``v141-heuristic-1023`` at 212,
``v141-no-tech_module-app_ai-9711`` at 200; docs/human-records.md).

When an engine change makes a ``data/`` record stop, read the module
docstring of ``records.migration`` and docs/human-records.md before
touching this test: a new question the old engine never asked needs a
bridge; a recorded choice a rule change made illegal is a real divergence.
"""

import functools
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, is_fixed_outcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash
from dune_imperium.records import migration
from dune_imperium.records.migration import migrate_record, walk
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_effect_frame import route_box_action
from dune_imperium.rules.agent_effects import resolves_boost_draw
from dune_imperium.rules.board_effects import BOARD_ICON_IMPERIAL_PRIVILEGE
from dune_imperium.rules.effects import board_icon_is_pending
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft_boxes import active_box
from dune_imperium.rules.intrigue import current_intrigue_choice_slot
from dune_imperium.rules.leader_abilities import legal_leader_signet_actions
from dune_imperium.rules.reveal_turn import reveal_pending_gains
from dune_imperium.rules.scouts_effects import reward_was_chosen
from dune_imperium.server.persistence import parse_save_document
from dune_imperium.simulation.runner import run_policy_game

DATA = Path(__file__).parent / "data"
# The bridges only a record older than codec v142 may use.
V142_BRIDGES = frozenset(
    {
        "imperial_privilege_draw",
        "garrison_unit_troop",
        "prison_planet_commanders_only",
        "shigawire_draw",
        "planetologist_intrigue",
        "intrigue_held_rewards",
        "piter_reward",
        "reverse_engineering_reward",
        "scouts_held_draw",
        "scouts_reward_pause",
        "owed_draw",
        "unpredictable_foe_draw",
        "reshuffle_renamed",
        "refinish_agent_turn",
    }
)
# v141 records written for the OQ-106 bridges, with the recorded step each
# follows bridge adds a step after (a rewrite: the recorded step it renames).
OQ106_FIXTURES: dict[str, dict[str, list[int]]] = {
    # Urgent Shigawire's added card, after the boosted Prepare the Way's
    # placement (round 3); the next step, a board icon, is accepted.
    "v141-no-immortality-no-go_to_11-app_ai-2002": {"shigawire_draw": [193]},
    # Insider Information's trash (round 2); its draw reshuffles, recorded
    # at 108 under the old id.
    "v141-heuristic-1027": {
        "intrigue_held_rewards": [107],
        "reshuffle_renamed": [108],
    },
    # Piter's troop loss (round 3): the cards reshuffle (recorded 170 under
    # the payment's id), and the Research follows that chance; at 368
    # (round 5) a Research past the second genetic marker settles first and
    # the cards' reshuffle (369) comes after it, as v141 drew them. A Deep
    # Desert summon for Liet Kynes (two Intrigue cards) at 199.
    "v141-no-tech_module-app_ai-9711": {
        "piter_reward": [169, 170, 368, 368],
        "reshuffle_renamed": [170, 369],
        "planetologist_intrigue": [199, 200],
        "owed_draw": [235, 290, 371],
    },
    # Reverse Engineering in a Servo-Receivers frame (round 1).
    "v141-no-immortality-no-go_to_11-random-4094": {
        "reverse_engineering_reward": [20, 20],
    },
    # Reverse Engineering in the Signet Ring's box (round 4); the card's
    # reshuffle is recorded at 298 under the Signet's id.
    "v141-random-3038": {
        "scouts_held_draw": [293],
        "reverse_engineering_reward": [297, 297],
        "reshuffle_renamed": [298],
        "owed_draw": [312],
    },
    # Water Discipline's draw after a decline and two trashes (round 4); the
    # second one's reshuffle is the recorded chance at 223.
    "v141-no-tech_module-no-immortality-no-go_to_11-app_ai-9515": {
        "scouts_held_draw": [220, 222, 225],
    },
    # A sealed auction's later winner (round 5).
    "v141-no-tech_module-no-immortality-no-go_to_11-app_ai-9504": {
        "intrigue_held_rewards": [135],
        "reshuffle_renamed": [136],
        "scouts_reward_pause": [307],
    },
    # Imperial Birthright (225) and Overthrow's card (269), which recorded
    # 272 trashes from hand in an Intrigue choice that offers no owed draw.
    "v141-app_ai-1050": {"owed_draw": [225, 269]},
    # Hungry for Spice (round 4), whose draw reshuffles: the recorded chance
    # at 257 answers it.
    "v141-no-tech_module-no-immortality-no-go_to_11-random-9167": {
        "owed_draw": [256],
    },
    # Muad'Dib's Unpredictable Foe at his Reveal (round 2); the next step
    # (an acquisition) is accepted.
    "v141-no-tech_module-no-immortality-no-go_to_11-heuristic-9273": {
        "unpredictable_foe_draw": [149],
    },
    # Unpredictable Foe again (round 5): a revealed card's Intrigue entry
    # is older than the Foe's, so the bridged draw takes it and the Foe
    # entry waits for the record's own draw; drawn once per grant.
    "v141-app_ai-1009": {
        "scouts_held_draw": [259, 261, 263],
        "unpredictable_foe_draw": [430],
    },
}
FULL = RulesetConfig(
    players=4,
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)
ENGINE = UprisingRulesEngine()


def _this_engine_game(seed: int) -> GameReplay:
    """A whole heuristic game on this engine, stamped as its saves are."""

    agents = [make_agent("heuristic", 10 + seat) for seat in range(4)]
    replay = run_policy_game(ENGINE, FULL, seed, agents).replay
    return replace(replay, action_codec_version=ACTION_CODEC_VERSION)


@pytest.fixture(scope="module")
def game() -> GameReplay:
    """A whole heuristic game on this engine with every module on.

    Seed 102, seed 1 until codec v146: optional Agent-turn effects no longer
    offer a refusal (OQ-095 (2), user ruling 2026-10-14), which moved seed
    1's game off these tests' preconditions -- a seat now deploys troops
    before drawing the Intrigue card a Research owes it (an older engine
    drew it inside the Research, so the bridge takes it first), and no seat
    places with Navigation Chamber's discount any more. Of seeds 1-200,
    95, 96, 102, 141, 149, 154, 182, 186, 187 and 194 meet every test on
    this fixture but the triggered-draw one, which needs a game whose only
    split steps are owed draws and has a seed of its own; 102's game also
    holds an Imperial Privilege draw and an Arrakeen Scouts line draw, so
    the older records built from it take those bridges too.
    """

    return _this_engine_game(102)


def _states(replay: GameReplay) -> list[GameState]:
    """The state before every recorded step."""

    states = [ENGINE.reset(replay.ruleset, replay.seed)]
    for step in replay.steps:
        states.append(ENGINE.apply(states[-1], step).state)
    return states[:-1]


@functools.cache
def _held_steps(replay: GameReplay) -> dict[int, str]:
    """This engine's steps an engine before v142 made inside another step.

    Codec v142 (OQ-106) holds a hidden draw (and a Scouts auction reward)
    as a step of its own; a record of an older engine has no such step, and
    the ``follows`` bridge named here adds it back.
    """

    held: dict[int, str] = {}
    for index, (state, step) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        if isinstance(step, ChanceOutcome):
            if step.decision_id.endswith(":scouts_reward:pause"):
                held[index] = "scouts_reward_pause"
            continue
        top = state.decision_stack[-1]
        context = dict(top.context)
        effect = dict(step.arguments).get("effect")
        oldest_intrigue = next(
            (
                source
                for kind, _, source in reveal_pending_gains(context)
                if kind == "intrigue"
            ),
            None,
        )
        name = {
            "draw_owed_intrigue": "owed_draw",
            "draw_owed_card": "owed_draw",
            "draw_planetologist_intrigue": "planetologist_intrigue",
        }.get(step.action_id)
        if name is not None:
            held[index] = name
        elif step.action_id == "scouts_rewards_first" and (
            top.kind == FrameKind.SCOUTS_EFFECT
            and reward_was_chosen(top)
            and ENGINE.legal_actions(state, step.actor) == (step,)
        ):
            held[index] = "scouts_held_draw"
        elif step.action_id == "resolve_intrigue_rewards" and (
            top.kind == FrameKind.INTRIGUE_CHOICE
            and current_intrigue_choice_slot(state, step.actor) is None
        ):
            held[index] = "intrigue_held_rewards"
        elif step.action_id == "resolve_agent_card_effect" and resolves_boost_draw(
            state, step
        ):
            held[index] = "shigawire_draw"
        elif (
            step.action_id == "resolve_agent_card_effect"
            and top.kind == FrameKind.AGENT_EFFECTS
            and "piter_genius_advisor" in str(context.get("card_id"))
            and effect in ("cards", "research")
        ):
            held[index] = "piter_reward"
        elif step.action_id == "resolve_agent_card_effect" and step in (
            legal_leader_signet_actions(state, step.actor)
        ):
            held[index] = "reverse_engineering_reward"
        elif step.action_id == "draw_reveal_intrigue" and (
            oldest_intrigue == "leader_reveal:unpredictable_foe"
        ):
            held[index] = "unpredictable_foe_draw"
        elif (
            step.action_id == "resolve_board_effect"
            and effect == "cards"
            and top.kind == FrameKind.AGENT_EFFECTS
            and context.get("space_id") == "imperial_privilege"
            and not board_icon_is_pending(context, BOARD_ICON_IMPERIAL_PRIVILEGE)
        ):
            # Before v142 the recall (or its confirm) drew the card, so only
            # a draw taken once the recall is done was made inside it; one
            # this engine's seat took before the recall stays recorded (no
            # older engine recorded that order, and the bridge, which
            # follows the recall, then finds nothing left to draw).
            held[index] = "imperial_privilege_draw"
    return held


def _dropped(replay: GameReplay, codec: int, drop: set[int] | None = None) -> set[int]:
    """The steps of ``replay`` an engine of ``codec`` would not have recorded."""

    return set(drop or ()) | (set(_held_steps(replay)) if codec < 142 else set())


def _older(replay: GameReplay, codec: int, drop: set[int] | None = None) -> GameReplay:
    """``replay`` as an engine of ``codec`` would have recorded it.

    Besides ``drop``, a record older than v142 loses the steps that engine
    made inside another (``_held_steps``).
    """

    dropped = _dropped(replay, codec, drop)
    steps = tuple(
        step for index, step in enumerate(replay.steps) if index not in dropped
    )
    return replace(replay, steps=steps, action_codec_version=codec)


def _held_counts(replay: GameReplay) -> Counter[str]:
    return Counter(_held_steps(replay).values())


def _position(replay: GameReplay, codec: int, index: int) -> int:
    """Where ``replay``'s step ``index`` sits in ``_older(replay, codec)``."""

    return index - sum(1 for dropped in _dropped(replay, codec) if dropped < index)


def _older_with(
    replay: GameReplay, codec: int, index: int, step: ReplayStep
) -> tuple[GameReplay, int]:
    """``_older(replay, codec)`` with ``step`` in place of step ``index``."""

    older = _older(replay, codec)
    position = _position(replay, codec, index)
    steps = list(older.steps)
    steps[position] = step
    return replace(older, steps=tuple(steps)), position


def _pause_indices(replay: GameReplay) -> set[int]:
    return {
        index
        for index, (state, step) in enumerate(
            zip(_states(replay), replay.steps, strict=True)
        )
        if isinstance(step, ChanceOutcome)
        and isinstance(decision := ENGINE.current_decision(state), ChanceDecision)
        and is_fixed_outcome(decision)
    }


def _only_choice_in(replay: GameReplay, frame: FrameKind, action_id: str) -> set[int]:
    """Steps answering ``frame`` with ``action_id`` where nothing else was legal."""

    found = set()
    for index, (state, step) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        if (
            isinstance(step, DomainAction)
            and step.action_id == action_id
            and state.decision_stack[-1].kind == frame
            and ENGINE.legal_actions(state, step.actor) == (step,)
        ):
            found.add(index)
    return found


def _actor(replay: GameReplay, index: int) -> int:
    step = replay.steps[index]
    assert isinstance(step, DomainAction)
    return step.actor


def _steps(record_steps: tuple[ReplayStep, ...]) -> list[ReplayStep]:
    return list(record_steps)


def test_a_record_of_this_engine_replays_exactly(game: GameReplay) -> None:
    record = migrate_record(game)

    assert record.exact
    assert not record.bridge_counts()
    assert [migrated.recorded_index for migrated in record.steps] == list(
        range(len(game.steps))
    )


def test_pauses_an_older_engine_never_recorded_are_answered(
    game: GameReplay,
) -> None:
    pauses = _pause_indices(game)
    assert len(pauses) >= 10

    record = migrate_record(_older(game, 139, pauses))

    assert record.complete
    assert record.bridge_counts() == {
        "pause": len(pauses - set(_held_steps(game))),
        **_held_counts(game),
    }
    assert [migrated.step for migrated in record.steps] == _steps(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash


def test_conflict_end_windows_are_declined_only_for_records_before_v141(
    game: GameReplay,
) -> None:
    declines = _only_choice_in(
        game, FrameKind.CONFLICT_END_TRIGGER, "decline_conflict_end_intrigue"
    )
    assert declines
    drop = _pause_indices(game) | declines

    before = migrate_record(_older(game, 140, drop))
    assert before.complete
    assert before.bridge_counts()["conflict_end_window"] == len(declines)
    assert [migrated.step for migrated in before.steps] == _steps(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    # A v141 record met the window, so a missing decline is not a bridge's.
    after = migrate_record(_older(game, 141, drop))
    assert after.divergence is not None
    first = min(declines)
    assert after.divergence.recorded_index == first - sum(
        1 for index in _dropped(game, 141, drop) if index < first
    )


def test_a_combat_intrigue_pass_is_answered_only_for_records_before_v139(
    game: GameReplay,
) -> None:
    # A pass followed by another seat's step: dropping it leaves that seat's
    # Combat Intrigue question unanswered in the record.
    passes = sorted(
        index
        for index, step in enumerate(game.steps[:-1])
        if isinstance(step, DomainAction)
        and step.action_id == "pass_combat_intrigue"
        and getattr(game.steps[index + 1], "actor", None) != step.actor
    )
    dropped = passes[0]

    before = migrate_record(_older(game, 138, {dropped}))
    assert before.complete
    assert before.bridge_counts() == {"combat_intrigue_pass": 1, **_held_counts(game)}
    assert [migrated.step for migrated in before.steps] == _steps(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    after = migrate_record(_older(game, 139, {dropped}))
    assert after.divergence is not None
    assert after.divergence.recorded_index == _position(game, 139, dropped)


def test_a_bridge_never_answers_the_decision_the_recorded_step_was_for(
    game: GameReplay,
) -> None:
    # The seat passed here; its recorded answer now carries an argument no
    # pass takes. The pass bridge is open for a v138 record, but the step
    # was this decision's own answer, so the migration must stop on it.
    index = next(
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction) and step.action_id == "pass_combat_intrigue"
    )
    recorded = game.steps[index]
    assert isinstance(recorded, DomainAction)
    broken = DomainAction(
        action_id="pass_combat_intrigue",
        actor=recorded.actor,
        arguments=(("card_id", "intrigue:not_a_card:0"),),
    )
    older, position = _older_with(game, 138, index, broken)
    record = migrate_record(older)

    assert record.divergence is not None
    assert record.divergence.recorded_index == position
    assert record.divergence.step == broken
    assert isinstance(record.divergence.pending, PlayerDecision)
    assert [migrated.step for migrated in record.steps] == _steps(game.steps[:index])
    before = _states(game)[index]
    assert canonical_state_hash(record.state) == canonical_state_hash(before)


@pytest.mark.parametrize(
    ("frame", "answer", "codec"),
    [
        (FrameKind.COMBAT_INTRIGUE, "pass_combat_intrigue", 138),
        (FrameKind.CONFLICT_END_TRIGGER, "decline_conflict_end_intrigue", 140),
    ],
)
def test_a_bridge_never_answers_a_decision_whose_answer_a_rule_change_removed(
    game: GameReplay, frame: FrameKind, answer: str, codec: int
) -> None:
    # The seat could only decline here; its recorded answer becomes a card
    # play the decision does not offer at all (as if a rule change had taken
    # every such play away). The decline bridge is open for this codec, but
    # the step was this decision's own answer.
    play = {
        FrameKind.COMBAT_INTRIGUE: "play_intrigue",
        FrameKind.CONFLICT_END_TRIGGER: "play_conflict_end_intrigue",
    }[frame]
    states = _states(game)
    index = next(
        index
        for index in sorted(_only_choice_in(game, frame, answer))
        if not any(
            action.action_id == play
            for action in ENGINE.legal_actions(states[index], _actor(game, index))
        )
    )
    recorded = game.steps[index]
    assert isinstance(recorded, DomainAction)
    broken = DomainAction(
        action_id=play,
        actor=recorded.actor,
        arguments=(("card_id", "intrigue:not_a_card:0"),),
    )
    older, position = _older_with(game, codec, index, broken)
    record = migrate_record(older)

    assert record.divergence is not None
    assert record.divergence.recorded_index == position
    assert [migrated.step for migrated in record.steps] == _steps(game.steps[:index])
    pending = record.divergence.pending
    assert isinstance(pending, PlayerDecision)
    assert pending.owner == recorded.actor
    assert record.state.decision_stack[-1].kind == frame


def _card_effect_steps(game: GameReplay) -> list[int]:
    """Steps naming an icon where it was the only icon offered (a placed
    card's box: a graft partner's box 1 rows carry ``box=1``, codec v143)."""

    states = _states(game)
    return [
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction)
        and step.action_id == "resolve_agent_card_effect"
        and tuple(key for key, _ in step.arguments) == ("effect",)
        and [
            action
            for action in ENGINE.legal_actions(states[index], step.actor)
            if action.action_id == "resolve_agent_card_effect"
        ]
        == [step]
    ]


def test_a_card_effect_recorded_before_v137_named_its_icon_is_rewritten(
    game: GameReplay,
) -> None:
    index = _card_effect_steps(game)[0]
    recorded = game.steps[index]
    assert isinstance(recorded, DomainAction)
    plain = DomainAction(action_id=recorded.action_id, actor=recorded.actor)

    older, position = _older_with(game, 136, index, plain)
    before = migrate_record(older)
    assert before.complete
    assert before.bridge_counts() == {
        "agent_card_effect_named": 1,
        **_held_counts(game),
    }
    assert before.steps[index].step == recorded
    assert before.steps[index].recorded_index == position
    assert canonical_state_hash(before.state) == game.expected_state_hash

    after = migrate_record(replace(older, action_codec_version=137))
    assert after.divergence is not None
    assert after.divergence.recorded_index == position


def _with_graft_switches(replay: GameReplay) -> GameReplay:
    """``replay`` as an engine before codec v143 recorded it.

    That engine resolved one grafted box at a time, the placed card's first,
    and ``switch_graft_card`` made the other one active: each run of box 1's
    rows (``box=1``) is preceded by a switch and untagged, and a switch back
    precedes box 0's next row. Its turn end switched to a pending partner box
    as this engine's does, so the active box after a press is the frame's.
    """

    state = ENGINE.reset(replay.ruleset, replay.seed)
    steps: list[ReplayStep] = []
    active = 0
    for step in replay.steps:
        if isinstance(step, DomainAction):
            _, plain, box = route_box_action(state, step)
            if box is not None and box != active:
                steps.append(DomainAction("switch_graft_card", step.actor))
                active = box
            steps.append(plain)
        else:
            steps.append(step)
        state = ENGINE.apply(state, step).state
        if isinstance(step, DomainAction):
            if step.action_id in ("agent_turn", "choose_graft_partner"):
                active = 0
            elif step.action_id == "finish_agent_turn":
                top = state.decision_stack[-1] if state.decision_stack else None
                active = (
                    active_box(dict(top.context))
                    if top is not None and top.kind == FrameKind.AGENT_EFFECTS
                    else 0
                )
    return replace(replay, steps=tuple(steps), action_codec_version=142)


def test_a_record_with_graft_switches_migrates_to_the_box_rows(
    game: GameReplay,
) -> None:
    """Codec v143 offers both grafted boxes at once (docs/graft-boxes-plan.md
    4.10): an older record's switches are dropped and the steps box 1 took
    become its ``box=1`` rows, the same game."""

    boxed = sum(
        isinstance(step, DomainAction) and ("box", 1) in step.arguments
        for step in game.steps
    )
    assert boxed
    older = _with_graft_switches(game)
    switches = sum(
        isinstance(step, DomainAction) and step.action_id == "switch_graft_card"
        for step in older.steps
    )
    assert switches >= boxed > 0

    record = migrate_record(older)

    assert record.complete, record.divergence
    assert [migrated.step for migrated in record.steps] == list(game.steps)
    assert record.bridge_counts() == {
        "graft_switch": switches,
        "graft_box": boxed,
    }
    assert canonical_state_hash(record.state) == game.expected_state_hash
    # Stamped v143 the same steps are this engine's: the switch is no action.
    current = migrate_record(replace(older, action_codec_version=143))
    assert current.divergence is not None
    assert current.divergence.step == DomainAction(
        "switch_graft_card", current.divergence.step.actor  # type: ignore[union-attr]
    )


def test_a_network_move_judged_on_box_one_is_rewritten_to_its_row(
    game: GameReplay,
) -> None:
    """``rewrite_step`` reads an older engine's move by the graft box that
    engine had active (``MigratedStep.graft_box``); a switch has no row."""

    states = _states(game)
    index = next(
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction) and ("box", 1) in step.arguments
    )
    step = game.steps[index]
    assert isinstance(step, DomainAction)
    plain = DomainAction(
        step.action_id,
        step.actor,
        tuple(item for item in step.arguments if item != ("box", 1)),
    )
    state = states[index]
    assert migration.rewrite_step(ENGINE, state, plain, 142, graft_box=1) == step
    assert (
        migration.rewrite_step(
            ENGINE, state, DomainAction("switch_graft_card", step.actor), 142
        )
        is None
    )
    assert migration.rewrite_step(ENGINE, state, plain, 143, graft_box=1) is None


_PITER = "tleilaxu:piter_genius_advisor:0"
_INFILTRATOR = "tleilaxu:tleilaxu_infiltrator:0"


def _grafted_turn(placed: str, partner: str, space_id: str) -> GameState:
    """Seat 0's grafted Agent turn: ``placed`` (box 0) with ``partner``
    (box 1) at ``space_id``, no box resolved yet."""

    starters = starting_deck_instance_ids(0, immortality=True)
    imperium = imperium_deck_instance_ids(False)

    def seat(player: int, **extra: object) -> PlayerState:
        values: dict[str, object] = {
            "player_id": player,
            "research_space": RESEARCH_START_ID,
            "family_atomics": True,
        }
        values.update(extra)
        return PlayerState(**values)  # type: ignore[arg-type]

    owner = seat(
        0,
        hand=(placed, partner),
        deck=starters,
        resources=Resources(solari=4, spice=2, water=2),
    )
    state = GameState(
        config=RulesetConfig(immortality=True, promo_cards=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        tleilaxu_track_spice=2,
        players=(owner, *(seat(player) for player in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.TURN,
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placement = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["card_id"] == placed
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    state = ENGINE.apply(state, placement).state
    choice = DomainAction("choose_graft_partner", 0, arguments=(("card_id", partner),))
    return ENGINE.apply(state, choice).state


_PAY_PITER = DomainAction("lose_agent_card_troop", 0, arguments=(("zone", "garrison"),))
_CARDS = DomainAction("resolve_agent_card_effect", 0, arguments=(("effect", "cards"),))
_SWITCH = DomainAction("switch_graft_card", 0)


class _StartingAt(UprisingRulesEngine):
    """An engine whose every game starts at ``start`` (a built position)."""

    def __init__(self, start: GameState) -> None:
        super().__init__()
        self._start = start

    def reset(self, config: RulesetConfig, seed: int) -> GameState:
        return self._start


def _v142_record(start: GameState, *steps: ReplayStep, codec: int = 142) -> GameReplay:
    return GameReplay(
        ruleset=start.config,
        seed=1,
        steps=steps,
        expected_state_hash="unused",
        action_codec_version=codec,
    )


def test_a_box_step_held_behind_the_other_box_s_selection_diverges() -> None:
    """An engine before codec v143 let a switch leave Piter's paid arrow
    with its rewards waiting and resolve Tleilaxu Infiltrator's own card
    draw (box 1). This engine holds box 1 until Piter's rewards are taken
    (docs/graft-boxes-plan.md 4.3), and the same untagged ``effect=cards``
    is Piter's two-card reward here, so the record stops at that step
    instead of playing on as another move."""

    start = ENGINE.apply(
        _grafted_turn(_PITER, _INFILTRATOR, "assembly_hall"), _PAY_PITER
    ).state
    # Taken as recorded the step would draw Piter's two cards.
    assert _CARDS in ENGINE.legal_actions(start, 0)
    assert route_box_action(start, _CARDS)[2] == 0

    record = migrate_record(
        _v142_record(start, _SWITCH, _CARDS), _StartingAt(start)
    )

    assert record.divergence is not None
    assert record.divergence.recorded_index == 1
    assert "waits here" in record.divergence.reason
    assert record.dropped == ((0, "graft_switch"),)
    assert record.steps == ()
    # The network's move judged on box 1 there has no row either.
    assert migration.graft_box_held(ENGINE, start, _CARDS, 1) is not None
    assert migration.rewrite_step(ENGINE, start, _CARDS, 142, graft_box=1) is None
    # Box 0's own step is Piter's, as recorded.
    assert migration.graft_box_held(ENGINE, start, _CARDS, 0) is None


def test_box_zero_s_step_held_behind_box_one_s_selection_diverges() -> None:
    """The mirror: Piter is the partner (box 1). The record switched to
    it, paid the troop, switched back and took Tleilaxu Infiltrator's draw
    (box 0) while Piter's rewards waited; this engine holds box 0 there."""

    start = _grafted_turn(_INFILTRATOR, _PITER, "arrakeen")
    record = migrate_record(
        _v142_record(start, _SWITCH, _PAY_PITER, _SWITCH, _CARDS),
        _StartingAt(start),
    )

    assert record.divergence is not None
    assert record.divergence.recorded_index == 3
    assert "box 0's" in record.divergence.reason
    assert [migrated.step for migrated in record.steps] == [
        DomainAction(
            "lose_agent_card_troop", 0, arguments=(("box", 1), ("zone", "garrison"))
        )
    ]
    assert record.dropped == ((0, "graft_switch"), (2, "graft_switch"))


def test_a_missing_argument_elsewhere_is_a_choice_not_a_gap(
    game: GameReplay,
) -> None:
    # No ``discount`` means the seat did not use one; the record must stop
    # there rather than be rewritten into the discounted play.
    states = _states(game)
    index, recorded = next(
        (index, step)
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction)
        and dict(step.arguments).get("discount") is not None
        and DomainAction(
            action_id=step.action_id,
            actor=step.actor,
            arguments=tuple(pair for pair in step.arguments if pair[0] != "discount"),
        )
        not in ENGINE.legal_actions(states[index], step.actor)
    )
    plain = DomainAction(
        action_id=recorded.action_id,
        actor=recorded.actor,
        arguments=tuple(pair for pair in recorded.arguments if pair[0] != "discount"),
    )
    older, position = _older_with(game, 130, index, plain)

    record = migrate_record(older)

    assert record.divergence is not None
    assert record.divergence.recorded_index == position
    assert set(record.bridge_counts()) <= set(_held_counts(game))
    assert [migrated.step for migrated in record.steps] == _steps(game.steps[:index])


def test_a_triggered_draw_an_older_engine_drew_at_once_follows_its_trigger() -> None:
    # Codec v142 (user ruling 2026-10-10, OQ-106) holds a triggered draw as
    # the owner's own ``draw_owed_*`` step; an older engine drew it inside
    # the trigger, so its record has no such step. Dropped from this
    # engine's record (whose heuristic takes each at once), each is taken
    # right after its trigger again, so the game comes back step for step.
    # Seed 10's game, whose only split steps are its three owed draws: this
    # test ran on the fixture's seed 1 until codec v146 (OQ-095 (2), user
    # ruling 2026-10-14), whose game then also held an Imperial Privilege
    # draw and a Scouts reward pause and drew one owed Intrigue card a step
    # late. Of seeds 1-200 only 2, 10 and 88 split nothing but owed draws,
    # and seed 2 takes one late.
    game = _this_engine_game(10)
    owed = {
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction) and step.action_id.startswith("draw_owed_")
    }
    assert owed
    assert set(_held_steps(game)) == owed

    before = migrate_record(_older(game, 141, owed))
    assert before.complete, before.divergence
    assert before.bridge_counts() == {"owed_draw": len(owed)}
    assert [migrated.step for migrated in before.steps] == _steps(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    # A v142 record took every such draw itself.
    after = migrate_record(_older(game, 142, owed))
    assert after.divergence is not None


def test_a_scouts_line_draw_an_older_engine_drew_at_once_follows_its_choice() -> None:
    # Codec v142 (user ruling 2026-10-10, OQ-106) holds a draw printed after
    # one of an Arrakeen Scouts line's reward choices as the line's own
    # ``scouts_rewards_first``, then its only action; an older engine drew
    # it in the choice's step, so its record has no such step. Seed 5's
    # heuristic game holds two (round 4, Water Discipline's card after its
    # trash; round 8, Leverage's Intrigue card). Dropped from this engine's
    # record with the game's other held steps, each is taken right after
    # the same choice again. (Seed 3 until codec v146: optional Agent-turn
    # effects offer no refusal since then, OQ-095 (2), and seed 3's game no
    # longer holds such a draw; seed 5 is the first of 1-200 that does.)
    game = _this_engine_game(5)
    held = _held_steps(game)
    scouts = [index for index, name in held.items() if name == "scouts_held_draw"]
    assert scouts

    before = migrate_record(_older(game, 141))
    assert before.complete, before.divergence
    assert before.bridge_counts() == _held_counts(game)
    choices = [
        previous.step
        for previous, migrated in zip(before.steps, before.steps[1:], strict=False)
        if migrated.bridge == "scouts_held_draw"
    ]
    assert choices == [game.steps[index - 1] for index in scouts]

    # A v142 record took every such draw itself.
    after = migrate_record(_older(game, 142, set(held)))
    assert after.divergence is not None


def test_walk_yields_the_state_before_each_migrated_step(game: GameReplay) -> None:
    record = migrate_record(_older(game, 139, _pause_indices(game)))
    walked = list(walk(record))

    assert [migrated for _, migrated in walked] == list(record.steps)
    expected = ENGINE.reset(game.ruleset, game.seed)
    for state, migrated in walked[:200]:
        assert canonical_state_hash(state) == canonical_state_hash(expected)
        expected = ENGINE.apply(expected, migrated.step).state


@pytest.mark.parametrize(
    ("name", "codec", "bridges"),
    [
        (
            "v135-app_ai-3",
            135,
            {
                "pause",
                "conflict_end_window",
                "combat_intrigue_pass",
                "agent_card_effect_named",
                # Codec v142 (OQ-106): a triggered draw is its own step.
                "owed_draw",
            },
        ),
        ("v139-heuristic-1", 139, {"pause", "conflict_end_window"}),
        ("v140-heuristic-1", 140, {"conflict_end_window"}),
        ("v141-heuristic-21", 141, {"imperial_privilege_draw"}),
        (
            "v141-heuristic-1023",
            141,
            {
                "imperial_privilege_draw",
                "intrigue_held_rewards",
                "planetologist_intrigue",
            },
        ),
        ("v141-heuristic-150", 141, {"garrison_unit_troop", "piter_reward"}),
        (
            "v141-no-immortality-no-go_to_11-heuristic-1211",
            141,
            {"prison_planet_commanders_only", "scouts_held_draw", "owed_draw"},
        ),
        *((name, 141, set(fired)) for name, fired in OQ106_FIXTURES.items()),
    ],
)
def test_records_of_older_engines_replay_to_their_end(
    name: str, codec: int, bridges: set[str]
) -> None:
    document = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    replay = parse_save_document(document, check_versions=False).replay
    assert replay.action_codec_version == codec < ACTION_CODEC_VERSION

    record = migrate_record(replay)

    assert record.complete, record.divergence
    assert bridges <= set(record.bridge_counts())
    recorded = [m.recorded_index for m in record.steps if m.recorded_index is not None]
    # Codec v143 drops every recorded ``switch_graft_card`` (both grafted
    # boxes are offered at once). Codec v146 (OQ-095 (2)) drops a refusal of
    # an optional effect this engine no longer offers: the effect stays
    # pending and the recorded turn end lapses it. Every other recorded step
    # applies.
    switches = [
        index
        for index, step in enumerate(replay.steps)
        if isinstance(step, DomainAction) and step.action_id == "switch_graft_card"
    ]
    for index, reason in record.dropped:
        step = replay.steps[index]
        assert isinstance(step, DomainAction)
        assert (step.action_id, reason) in (
            (migration.GRAFT_SWITCH, migration.GRAFT_SWITCH_DROPPED),
            *(
                (refusal, migration.OPTIONAL_REFUSAL_DROPPED)
                for refusal in migration._OPTIONAL_REFUSALS
            ),
        ), (index, step, reason)
    assert [
        index
        for index, reason in record.dropped
        if reason == migration.GRAFT_SWITCH_DROPPED
    ] == switches
    dropped = [index for index, _ in record.dropped]
    assert sorted((*recorded, *dropped)) == list(range(len(replay.steps)))


@pytest.mark.parametrize(
    "name",
    [
        "v141-heuristic-21",
        "v141-heuristic-150",
        "v141-no-immortality-no-go_to_11-heuristic-1211",
        *OQ106_FIXTURES,
    ],
)
def test_the_v142_bridges_stay_away_from_v142_records(name: str) -> None:
    # Stamped v142, the same steps claim this engine's flow, so the engine's
    # new questions are the record's own to answer, and it stops there.
    document = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    replay = parse_save_document(document, check_versions=False).replay

    record = migrate_record(replace(replay, action_codec_version=142))

    assert record.divergence is not None
    assert not V142_BRIDGES & set(record.bridge_counts())


@pytest.mark.parametrize("name", ["v141-heuristic-21", "v141-heuristic-1023"])
def test_imperial_privilege_draws_right_after_the_recorded_recall(name: str) -> None:
    # The recording engine drew inside the recall, so the draw must come
    # right after it. In v141-heuristic-1023 the recall is followed by a
    # step this engine accepts (``decline_tech``): a bridge that waited for
    # a refusal would draw only after it, a step late.
    document = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    replay = parse_save_document(document, check_versions=False).replay

    record = migrate_record(replay)

    assert record.complete
    draws = [
        position
        for position, migrated in enumerate(record.steps)
        if migrated.bridge == "imperial_privilege_draw"
    ]
    assert draws
    for position in draws:
        before = record.steps[position - 1]
        assert before.recorded_index is not None
        assert isinstance(before.step, DomainAction)
        assert "imperial_privilege" in before.step.action_id


def _fixture(name: str) -> GameReplay:
    document = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    return parse_save_document(document, check_versions=False).replay


def _first_bridged(replay: GameReplay, bridge: str) -> tuple[int, int]:
    """The recorded index a bridge first answered before, and its seat."""

    record = migrate_record(replay)
    for position, migrated in enumerate(record.steps):
        if migrated.bridge == bridge:
            step = migrated.step
            assert isinstance(step, DomainAction)
            following = next(
                later
                for later in record.steps[position + 1 :]
                if later.recorded_index is not None
            )
            assert following.recorded_index is not None
            return following.recorded_index, step.actor
    raise AssertionError(f"{bridge} never answered")


@pytest.mark.parametrize(
    ("name", "bridge", "own_answer"),
    [
        (
            "v141-heuristic-150",
            "garrison_unit_troop",
            DomainAction(
                action_id="scouts_lose_garrison_unit",
                actor=0,
                arguments=(("commanders", 2),),
            ),
        ),
        (
            "v141-no-immortality-no-go_to_11-heuristic-1211",
            "prison_planet_commanders_only",
            DomainAction(
                action_id="scouts_join_mission",
                actor=0,
                arguments=(("target", "elsewhere"),),
            ),
        ),
    ],
)
def test_the_oq105_bridges_never_answer_the_seat_own_recorded_answer(
    name: str, bridge: str, own_answer: DomainAction
) -> None:
    # Where the bridge answered, the record now holds the seat's own answer
    # to that very decision, one this engine refuses: the bridge must not
    # answer in its place, and the migration stops on that step.
    replay = _fixture(name)
    index, seat = _first_bridged(replay, bridge)
    answer = replace(own_answer, actor=seat)
    steps = list(replay.steps)
    steps.insert(index, answer)

    record = migrate_record(replace(replay, steps=tuple(steps)))

    assert record.divergence is not None
    assert record.divergence.recorded_index == index
    assert record.divergence.step == answer
    assert bridge not in record.bridge_counts()


@pytest.mark.parametrize(
    "name",
    [
        "v141-no-immortality-no-go_to_11-heuristic-1211",
        "v141-no-immortality-no-go_to_11-app_ai-6005",
    ],
)
def test_prison_planet_is_not_declined_for_a_seat_that_could_join_with_a_troop(
    name: str,
) -> None:
    # The older engine asked this seat too (it held a troop), so the record
    # has its answer; with that answer gone the next step is refused, and
    # the bridge must not decline for a seat the old engine did ask. In
    # app_ai-6005 the seat also holds a Commander, so this engine offers the
    # Commander as well: only the troop target tells the two cases apart.
    replay = _fixture(name)
    engine = UprisingRulesEngine()
    asked = next(
        migrated.recorded_index
        for state, migrated in walk(migrate_record(replay, engine), engine)
        if migrated.recorded_index is not None
        and isinstance(migrated.step, DomainAction)
        and state.decision_stack
        and state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION
        and DomainAction(
            action_id="scouts_join_mission",
            actor=migrated.step.actor,
            arguments=(("target", ""),),
        )
        in engine.legal_actions(state, migrated.step.actor)
    )
    steps = list(replay.steps)
    del steps[asked]

    record = migrate_record(replace(replay, steps=tuple(steps)))

    assert record.divergence is not None
    assert record.divergence.recorded_index == asked
    assert "prison_planet_commanders_only" not in record.bridge_counts()


def _fired_after(record: migration.MigratedRecord, bridge: str) -> list[int]:
    """For each step ``bridge`` added, the recorded step it came after."""

    after: list[int] = []
    last = -1
    for migrated in record.steps:
        if migrated.recorded_index is not None:
            last = migrated.recorded_index
        elif migrated.bridge == bridge:
            after.append(last)
    return after


def test_follows_bridges_that_never_settle_end_the_record_at_their_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Piter's troop loss (recorded 557) is followed by two rewards; with
    # room for one, the step's follows do not settle, so the record stops
    # on that step, in the state before it, instead of looping or going on
    # with a reward missing.
    replay = _fixture("v141-heuristic-150")
    complete = migrate_record(replay)
    assert _fired_after(complete, "piter_reward") == [557, 557]
    before = next(
        state for state, migrated in walk(complete) if migrated.recorded_index == 557
    )
    monkeypatch.setattr(migration, "MAX_FOLLOWS_PER_STEP", 1)

    record = migrate_record(replay)

    assert record.divergence is not None
    assert record.divergence.recorded_index == 557
    assert "did not settle" in record.divergence.reason
    assert record.steps[-1].recorded_index == 556
    assert canonical_state_hash(record.state) == canonical_state_hash(before)


def _usurped_eyes_turn() -> GameState:
    """Seat 0's Agent turn whose Usurped Replacement Eyes the end trashes.

    Its "When this card is trashed: Tleilaxu" [card face] moves the token
    from space 1 onto the track's Intrigue space [Immortality pp. 4, 7].
    """

    eyes = "imperium:replacement_eyes:0"
    starters = starting_deck_instance_ids(0, immortality=True)
    dagger = next(card for card in starters if "dagger:0" in card)
    imperium = tuple(card for card in imperium_deck_instance_ids(False) if card != eyes)

    def seat(player: int, **extra: object) -> PlayerState:
        values: dict[str, object] = {
            "player_id": player,
            "research_space": RESEARCH_START_ID,
            "family_atomics": True,
        }
        values.update(extra)
        return PlayerState(**values)  # type: ignore[arg-type]

    owner = seat(
        0,
        hand=(dagger,),
        deck=tuple(card for card in starters if card != dagger),
        resources=Resources(solari=4, spice=2, water=2),
        tleilaxu_space=1,
    )
    state = GameState(
        config=RulesetConfig(immortality=True, promo_cards=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        tleilaxu_track_spice=2,
        players=(owner, *(seat(player) for player in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.TURN,
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placement = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["card_id"] == dagger
        and dict(action.arguments)["space_id"] == "assembly_hall"
        and "graft" not in dict(action.arguments)
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    state = ENGINE.apply(state, placement).state
    owner = state.players[0]
    borrowed = replace(owner, in_play=(*owner.in_play, eyes), usurped_row_card_id=eyes)
    state = replace(state, players=(borrowed, *state.players[1:]))
    while _PRESS not in (actions := ENGINE.legal_actions(state, 0)):
        state = ENGINE.apply(state, actions[0]).state
    return state


_PRESS = DomainAction(action_id="finish_agent_turn", actor=0)


def _bridges_for(codec: int) -> tuple[migration.Bridge, ...]:
    return tuple(
        bridge
        for bridge in migration.BRIDGES
        if bridge.before_codec is None or codec < bridge.before_codec
    )


def test_a_turn_reopened_only_for_its_held_draw_is_ended_again() -> None:
    # An older engine drew a card the turn-end press earned inside the
    # press and closed the turn. Codec v142 (OQ-106) holds it, so the turn
    # reopens; the owed draw follows the press, and once the record's next
    # step (another seat's) shows the turn was over, it is ended again. No
    # v141 record holds this (the corpus has none), so the state is built.
    ready = _usurped_eyes_turn()
    pressed = ENGINE.apply(ready, _PRESS)
    assert "agent_turn_reopened" in {event.kind for event in pressed.events}
    assert [origin for _, origin, _ in pressed.state.players[0].owed_draws] == [
        "tleilaxu_track"
    ]
    older = _bridges_for(141)
    migrated: list[migration.MigratedStep] = []
    followed = migration._follow(ENGINE, pressed.state, _PRESS, older, migrated)
    assert followed is not None
    assert [step.bridge for step in migrated] == ["owed_draw"]
    assert ENGINE.legal_actions(followed, 1) == ()
    next_seat = DomainAction(
        action_id="agent_turn",
        actor=1,
        arguments=(("card_id", "imperium:any:0"), ("space_id", "arrakeen")),
    )

    bridged = migration._bridge(ENGINE, followed, next_seat, older)

    assert bridged is not None
    assert (bridged[0].name, bridged[1]) == ("refinish_agent_turn", _PRESS)
    closed = ENGINE.apply(followed, _PRESS).state
    assert closed.decision_stack[-1].kind == FrameKind.TURN
    assert ENGINE.legal_actions(closed, 1)
    # The seat's own step in the reopened turn is not the next seat's.
    own = next(
        action for action in ENGINE.legal_actions(followed, 0) if action != _PRESS
    )
    assert migration._bridge(ENGINE, followed, own, older) is None
    # A v142 record presses the end again itself.
    assert migration._bridge(ENGINE, followed, next_seat, _bridges_for(142)) is None
    # A turn whose end was never pressed is not ended for the record.
    assert migration._bridge(ENGINE, ready, next_seat, older) is None


def _arrakeen_graft(
    placed: str,
    partner: str,
    *,
    skip: tuple[DomainAction, ...] = (),
    space_id: str = "arrakeen",
    **owner: object,
) -> GameState:
    """Seat 0 grafts ``partner`` to ``placed`` at ``space_id`` (Arrakeen)
    and resolves the space and every box resolution but ``skip``."""

    starters = starting_deck_instance_ids(0, immortality=True)
    imperium = tuple(
        card
        for card in imperium_deck_instance_ids(False)
        if card not in (placed, partner)
    )

    def seat(player: int, **extra: object) -> PlayerState:
        values: dict[str, object] = {
            "player_id": player,
            "research_space": RESEARCH_START_ID,
            "family_atomics": True,
        }
        values.update(extra)
        return PlayerState(**values)  # type: ignore[arg-type]

    seat_zero = seat(
        0,
        hand=(placed, partner),
        deck=tuple(card for card in starters if card not in (placed, partner)),
        resources=Resources(solari=4, spice=2, water=2),
        **owner,
    )
    state = GameState(
        config=RulesetConfig(immortality=True, promo_cards=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        tleilaxu_track_spice=2,
        players=(seat_zero, *(seat(player) for player in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.TURN,
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placement = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["card_id"] == placed
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    state = ENGINE.apply(state, placement).state
    state = ENGINE.apply(
        state, DomainAction("choose_graft_partner", 0, (("card_id", partner),))
    ).state
    while rest := [
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id
        in (
            "resolve_board_effect",
            "resolve_agent_card_effect",
            "resolve_faction_influence",
        )
        and action not in skip
    ]:
        state = ENGINE.apply(state, rest[0]).state
    return state


def _bene_gesserit_partner_turn() -> GameState:
    """Seat 0 grafts Truthtrance (Bene Gesserit) to Tleilaxu Infiltrator
    with Urgent Shigawire's boost pending, and resolves everything but the
    partner's added draw (codec v144, OQ-107)."""

    return _arrakeen_graft(
        "tleilaxu:tleilaxu_infiltrator:0",
        "imperium:truthtrance:0",
        skip=(_PARTNER_DRAW,),
        bene_gesserit_boost_pending=True,
    )


_PARTNER_DRAW = DomainAction(
    "resolve_agent_card_effect", 0, (("box", 1), ("effect", "cards"))
)


def test_a_bene_gesserit_partner_s_draw_comes_right_before_the_recorded_end() -> (
    None
):
    # Codec v144 (OQ-107) gives the Bene Gesserit partner the pending boost;
    # its added draw holds the turn end. An older engine's record never took
    # it and pressed the end: the draw is taken right before that press.
    # No corpus record is known to hold this, so the state is built.
    state = _bene_gesserit_partner_turn()
    assert resolves_boost_draw(state, _PARTNER_DRAW)
    assert _PRESS not in ENGINE.legal_actions(state, 0)
    older = _bridges_for(143)

    bridged = migration._bridge(ENGINE, state, _PRESS, older)

    assert bridged is not None
    assert (bridged[0].name, bridged[1]) == ("shigawire_partner_draw", _PARTNER_DRAW)
    drawn = ENGINE.apply(state, _PARTNER_DRAW).state
    assert _PRESS in ENGINE.legal_actions(drawn, 0)
    # Only before the press, and only for a record before codec v144.
    other = next(
        action for action in ENGINE.legal_actions(state, 0) if action != _PARTNER_DRAW
    )
    assert migration._bridge(ENGINE, state, other, older) is None
    assert migration._bridge(ENGINE, state, _PRESS, _bridges_for(144)) is None


_GHOLA_COPY_DRAW = DomainAction("resolve_agent_card_effect", 0, (("effect", "cards"),))


def test_a_ghola_copy_s_draw_comes_right_before_the_recorded_end() -> None:
    # Codec v145 (user ruling 2026-10-12, OQ-107): Ghola, placed, copies
    # the draw added to its boosted Bene Gesserit partner's box, and that
    # copy holds the turn end. An older engine's record took the partner's
    # draw only and pressed the end: the copy's draw (box 0, Ghola's) is
    # taken right before that press. The state is built.
    state = _arrakeen_graft(
        "tleilaxu:ghola:0",
        "imperium:truthtrance:0",
        skip=(_GHOLA_COPY_DRAW,),
        bene_gesserit_boost_pending=True,
    )
    assert resolves_boost_draw(state, _GHOLA_COPY_DRAW)
    assert not resolves_boost_draw(state, _PARTNER_DRAW)
    assert _PRESS not in ENGINE.legal_actions(state, 0)

    bridged = migration._bridge(ENGINE, state, _PRESS, _bridges_for(144))

    assert bridged is not None
    assert (bridged[0].name, bridged[1]) == (
        "boost_draw_at_turn_end",
        _GHOLA_COPY_DRAW,
    )
    drawn = ENGINE.apply(state, _GHOLA_COPY_DRAW).state
    assert _PRESS in ENGINE.legal_actions(drawn, 0)
    assert migration._bridge(ENGINE, state, _PRESS, _bridges_for(145)) is None


def test_a_ghola_partner_s_copy_is_the_v145_bridge_s_not_the_partner_s() -> None:
    # Planned Coupling, boosted, is placed; Ghola, its partner, copies the
    # added draw (codec v145). In a record before codec v144 the box-1 draw
    # waiting at the press is that copy, not a boosted Bene Gesserit
    # partner's: ``boost_draw_at_turn_end`` takes it, not
    # ``shigawire_partner_draw``.
    state = _arrakeen_graft(
        "imperium:planned_coupling:0",
        "tleilaxu:ghola:0",
        skip=(_PARTNER_DRAW,),
        bene_gesserit_boost_pending=True,
    )
    assert resolves_boost_draw(state, _PARTNER_DRAW)

    bridged = migration._bridge(ENGINE, state, _PRESS, _bridges_for(143))

    assert bridged is not None
    assert (bridged[0].name, bridged[1]) == ("boost_draw_at_turn_end", _PARTNER_DRAW)


def test_a_placed_ghola_s_copy_waits_past_the_v142_draw_bridge() -> None:
    # Before codec v142 the boosted card's placement drew the added card at
    # once, and ``shigawire_draw`` takes it right after the step this engine
    # asks first. A placed Ghola's copy (codec v145) had no draw at all in
    # such a record, so taking it there would shift the turn's later draws
    # by a card: it waits for the recorded turn end instead.
    placed = _arrakeen_graft(
        "tleilaxu:ghola:0",
        "imperium:truthtrance:0",
        skip=(_GHOLA_COPY_DRAW, _PARTNER_DRAW),
        bene_gesserit_boost_pending=True,
    )
    assert resolves_boost_draw(placed, _GHOLA_COPY_DRAW)
    migrated: list[migration.MigratedStep] = []
    choice = DomainAction(
        "choose_graft_partner", 0, (("card_id", "imperium:truthtrance:0"),)
    )

    followed = migration._follow(ENGINE, placed, choice, _bridges_for(141), migrated)

    assert followed is not None
    assert [step.bridge for step in migrated] == []


def test_a_card_s_own_trash_keeps_its_draw_for_the_recorded_end() -> None:
    # Throne Room Politics, boosted, is placed with Ghola and trashes itself
    # with its own optional trash icon. Codec v145 keeps its added draw
    # ("자기 효과로 자신을 trash하는 경우 인쇄된 이득은 정상 지급",
    # OQ-022); an older engine lapsed it, so its record pressed the end with
    # nothing to draw for it. Ghola's copied trash is declined.
    throne = "imperium:throne_room_politics:0"
    draws = (_GHOLA_COPY_DRAW, _PARTNER_DRAW)
    state = _arrakeen_graft(
        throne, "tleilaxu:ghola:0", skip=draws, bene_gesserit_boost_pending=True
    )
    trash = DomainAction("trash_optional_card", 0, (("card_id", throne),))
    decline = DomainAction("decline_optional_trash", 0)
    while True:
        legal = ENGINE.legal_actions(state, 0)
        if trash in legal:
            step = trash
        elif decline in legal:
            step = decline
        else:
            rest = [
                action
                for action in legal
                if action.action_id
                in ("resolve_agent_card_effect", "resolve_board_effect")
                and action not in draws
            ]
            if not rest:
                break
            step = rest[0]
        state = ENGINE.apply(state, step).state
    assert throne in state.players[0].trashed
    assert resolves_boost_draw(state, _GHOLA_COPY_DRAW)

    bridged = migration._bridge(ENGINE, state, _PRESS, _bridges_for(144))

    assert bridged is not None
    assert (bridged[0].name, bridged[1]) == (
        "boost_draw_at_turn_end",
        _GHOLA_COPY_DRAW,
    )
    assert migration._bridge(ENGINE, state, _PRESS, _bridges_for(145)) is None


_KIT = "imperium:dissecting_kit:0"


@pytest.mark.parametrize(
    ("partner", "lapsed"),
    [
        ("player:0:starter:dagger:0", (_KIT,)),
        # Ghola copies Dissecting Kit's box as box 1: both boxes lapse.
        ("tleilaxu:ghola:0", (_KIT, "tleilaxu:ghola:0")),
    ],
)
def test_an_optional_box_lapses_at_an_older_record_s_turn_end(
    partner: str, lapsed: tuple[str, ...]
) -> None:
    """Codec v144 (OQ-057 (1)) held the turn end while Dissecting Kit could
    still trash its partner for a specimen. An older engine offered the end
    beside the box and its press fizzled it, so a record before v144 had the
    box refused right before that press (``box_refused_at_turn_end``).
    Codec v146 (user ruling 2026-10-14, OQ-095 (2)) offers the end beside
    the optional box again and the press lapses it unused: the recorded
    press applies as it is, no bridge refuses anything, and the turn ends
    as the refusal left it -- nothing trashed, no specimen gained, both
    cards still in play. A record whose seat refused the boxes itself
    (codec v143 to v145) loses those refusals (``optional_refusal``) and
    ends in the same state."""

    state = _arrakeen_graft(_KIT, partner)
    owner = state.players[0]
    assert _PRESS in ENGINE.legal_actions(state, 0)
    assert migration._bridge(ENGINE, state, _PRESS, _bridges_for(143)) is None
    pressed = ENGINE.apply(state, _PRESS)
    assert [
        dict(event.payload)["card_id"]
        for event in pressed.events
        if event.kind == "agent_card_effect_lapsed"
    ] == list(lapsed)
    ended = pressed.state
    assert ended.decision_stack[-1].kind == FrameKind.TURN
    after = ended.players[0]
    assert (after.specimens, after.trashed) == (owner.specimens, owner.trashed)
    assert {_KIT, partner} <= set(after.in_play)

    record = migrate_record(_v142_record(state, _PRESS, codec=143), _StartingAt(state))

    assert record.complete, record.divergence
    assert not record.bridge_counts()
    assert [migrated.step for migrated in record.steps] == [_PRESS]
    assert canonical_state_hash(record.state) == canonical_state_hash(ended)

    refusals = (
        DomainAction("decline_agent_card_payment", 0),
        DomainAction("decline_agent_card_payment", 0, (("box", 1),)),
    )[: len(lapsed)]
    for codec in (143, 145):
        refused = migrate_record(
            _v142_record(state, *refusals, _PRESS, codec=codec), _StartingAt(state)
        )
        assert refused.complete, refused.divergence
        assert refused.dropped == tuple(
            (index, migration.OPTIONAL_REFUSAL_DROPPED)
            for index in range(len(refusals))
        )
        assert [migrated.step for migrated in refused.steps] == [_PRESS]
        assert canonical_state_hash(refused.state) == canonical_state_hash(ended)
    # Stamped v146 the refusals are this engine's own steps, which it no
    # longer offers: the record stops on the first.
    current = migrate_record(
        _v142_record(state, *refusals, _PRESS, codec=146), _StartingAt(state)
    )
    assert current.divergence is not None
    assert current.divergence.recorded_index == 0


@pytest.mark.parametrize(
    ("placed", "partner", "space_id"),
    [
        ("tleilaxu:stitched_horror:0", "player:0:starter:dagger:0", "arrakeen"),
        # Beguiling Pheromones' trash on a Faction space, beside a Tleilaxu
        # Surgeon one specimen short: the Surgeon offers only its refusal,
        # so it does not hold the end and is not refused for the record.
        (
            "imperium:tleilaxu_surgeon:0",
            "tleilaxu:beguiling_pheromones:0",
            "dutiful_service",
        ),
    ],
)
def test_a_mandatory_box_skipped_by_an_older_turn_end_diverges(
    placed: str, partner: str, space_id: str
) -> None:
    # Stitched Horror's "Choose two" and Beguiling Pheromones' trash are
    # mandatory and have no refusal: an older engine's press skipped them,
    # which this engine no longer allows (OQ-057 (1), OQ-095 2), so no
    # bridge answers before that press.
    state = _arrakeen_graft(
        placed, partner, space_id=space_id, specimens=1, troops_supply=8
    )
    assert _PRESS not in ENGINE.legal_actions(state, 0)

    assert migration._bridge(ENGINE, state, _PRESS, _bridges_for(143)) is None


_OQ106_BRIDGES = V142_BRIDGES - {
    "imperial_privilege_draw",
    "garrison_unit_troop",
    "prison_planet_commanders_only",
}


def _where(record: migration.MigratedRecord) -> dict[str, list[int]]:
    """Each OQ-106 bridge's places: the recorded step it followed or rewrote."""

    where: dict[str, list[int]] = {}
    last = -1
    for migrated in record.steps:
        if migrated.recorded_index is not None:
            last = migrated.recorded_index
        if migrated.bridge in _OQ106_BRIDGES:
            where.setdefault(migrated.bridge, []).append(last)
    return where


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        *OQ106_FIXTURES.items(),
        (
            "v141-heuristic-1023",
            {"intrigue_held_rewards": [46], "planetologist_intrigue": [211, 212]},
        ),
        ("v141-heuristic-150", {"piter_reward": [557, 557], "owed_draw": [558]}),
        (
            "v141-no-immortality-no-go_to_11-heuristic-1211",
            {"scouts_held_draw": [471], "owed_draw": [710]},
        ),
        ("v135-app_ai-3", {"owed_draw": [195]}),
    ],
)
def test_oq106_bridges_add_each_split_step_right_after_its_recorded_step(
    name: str, expected: dict[str, list[int]]
) -> None:
    # Codec v142 (OQ-106) splits a hidden draw off the step an older engine
    # made it in. The ``follows`` bridges add it right after that recorded
    # step (several after one step: both of Piter's rewards after 557, both
    # of Reverse Engineering's), before the next recorded step sees the
    # hand; a bridge that waited for a refusal would come later or never
    # (the next step is accepted in 2002, 9273 and 1023, a chance in 9167
    # and 9515). A renamed reshuffle is the recorded step itself.
    record = migrate_record(_fixture(name))

    assert record.complete, record.divergence
    assert _where(record) == expected


@pytest.mark.parametrize("name", ["v141-heuristic-150", *OQ106_FIXTURES])
def test_a_migrated_record_stamped_v142_needs_no_bridge(name: str) -> None:
    # The migrated steps, with every split step in its place, are a record
    # of this engine: stamped v142 they replay as they are. A follows bridge
    # open to them would take a split step before the record does.
    migrated = migrate_record(_fixture(name))
    replay = replace(
        migrated.replay,
        steps=tuple(step.step for step in migrated.steps),
        expected_state_hash=canonical_state_hash(migrated.state),
        action_codec_version=142,
    )

    assert migrate_record(replay).exact


def test_a_recorded_reshuffle_takes_the_id_of_the_one_this_engine_asks() -> None:
    # Insider Information's held draw reshuffles under ``...:rewards:draw``;
    # v141 recorded the same seat's same pile under ``...:draw``.
    replay = _fixture("v141-heuristic-1027")
    recorded = replay.steps[108]
    assert isinstance(recorded, ChanceOutcome)

    record = migrate_record(replay)

    renamed = next(step for step in record.steps if step.recorded_index == 108)
    assert renamed.bridge == "reshuffle_renamed"
    assert isinstance(renamed.step, ChanceOutcome)
    assert renamed.step == ChanceOutcome(
        recorded.decision_id.replace(":draw:", ":rewards:draw:"), recorded.values
    )


def _recorded_chance(
    replay: GameReplay, index: int, outcome: ChanceOutcome
) -> GameReplay:
    steps = list(replay.steps)
    steps[index] = outcome
    return replace(replay, steps=tuple(steps))


@pytest.mark.parametrize(
    "change",
    ["another seat", "another pile", "an Intrigue shuffle", "a v142 record"],
)
def test_a_reshuffle_is_renamed_only_for_the_same_seat_and_pile(change: str) -> None:
    replay = _fixture("v141-heuristic-1027")
    recorded = replay.steps[108]
    assert isinstance(recorded, ChanceOutcome)
    assert recorded.decision_id.startswith("round:2:player:0:")
    changed = {
        "another seat": ChanceOutcome(
            recorded.decision_id.replace(":player:0:", ":player:1:"), recorded.values
        ),
        "another pile": ChanceOutcome(
            recorded.decision_id, (*recorded.values, recorded.values[0])
        ),
        "an Intrigue shuffle": ChanceOutcome(
            recorded.decision_id.replace(":discard_shuffle", ":intrigue_shuffle"),
            recorded.values,
        ),
        "a v142 record": recorded,
    }[change]
    if change == "a v142 record":
        # This engine's own steps up to the reshuffle, its old id kept.
        migrated = migrate_record(replace(replay, steps=replay.steps[:108]))
        replay = replace(
            replay,
            steps=(*(step.step for step in migrated.steps), recorded),
            action_codec_version=142,
        )
        index = len(replay.steps) - 1
    else:
        index = 108
        replay = _recorded_chance(replay, index, changed)

    record = migrate_record(replay)

    assert record.divergence is not None
    assert record.divergence.recorded_index == index
    assert "reshuffle_renamed" not in record.bridge_counts()


@pytest.mark.parametrize(
    ("name", "bridge", "index"),
    [
        ("v141-no-immortality-no-go_to_11-app_ai-2002", "shigawire_draw", 193),
        ("v141-heuristic-1023", "planetologist_intrigue", 211),
        ("v141-heuristic-1023", "intrigue_held_rewards", 46),
        ("v141-heuristic-150", "piter_reward", 557),
        (
            "v141-no-immortality-no-go_to_11-random-4094",
            "reverse_engineering_reward",
            20,
        ),
        (
            "v141-no-tech_module-no-immortality-no-go_to_11-app_ai-9515",
            "scouts_held_draw",
            220,
        ),
        (
            "v141-no-tech_module-no-immortality-no-go_to_11-app_ai-9504",
            "scouts_reward_pause",
            307,
        ),
        ("v141-app_ai-1050", "owed_draw", 225),
        (
            "v141-no-tech_module-no-immortality-no-go_to_11-heuristic-9273",
            "unpredictable_foe_draw",
            149,
        ),
    ],
)
def test_a_record_ending_on_a_split_step_ends_with_what_that_step_did(
    name: str, bridge: str, index: int
) -> None:
    # A save made right after such a step (a human save mid-turn) has no
    # next step to be refused, so only a ``follows`` bridge adds what the
    # older engine did inside it: the Intrigue choice finished with its
    # draw, a later auction winner paid, and so on.
    replay = _fixture(name)

    record = migrate_record(replace(replay, steps=replay.steps[: index + 1]))

    assert record.complete
    assert _where(record)[bridge][-1] == index
    assert record.steps[-1].recorded_index is None
    decision = ENGINE.current_decision(record.state)
    assert not (
        isinstance(decision, ChanceDecision)
        and decision.decision_id.endswith(":scouts_reward:pause")
    )
