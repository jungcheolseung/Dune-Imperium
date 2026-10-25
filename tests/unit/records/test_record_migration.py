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
  ``OQ106_FIXTURES``, one or more for each OQ-106 bridge;
- afea63de (v145): ``v145-no-immortality-no-go_to_11-heuristic-208`` from
  the v145-afea63de corpus (``no-immortality.h4.208``): Reverend Mother's
  repeat on Desert Tactics after its Fedaykin Assistance troops, whose
  empty second mission collection codec v146 drops, and the v146 optional
  refusals.
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
from itertools import islice
from pathlib import Path

import pytest
from tests.support.reward_windows import settle_reward_window
from tests.unit.rules.test_bloodlines_leaders import RECON as LIET_RECON
from tests.unit.rules.test_bloodlines_leaders import _turn_state as _liet_turn_state
from tests.unit.rules.test_contracts import _agent_contract_state
from tests.unit.rules.test_contracts import _place_agent as _place_contract_agent
from tests.unit.rules.test_immortality import _agent_research, _at
from tests.unit.rules.test_immortality_intrigue import (
    HARVEST_CELLS,
    PLAIN,
)
from tests.unit.rules.test_immortality_intrigue import _combat_state as _window_combat
from tests.unit.rules.test_immortality_intrigue import _fighter as _window_fighter
from tests.unit.rules.test_immortality_intrigue import _offer as _window_offer
from tests.unit.rules.test_tech import (
    _bought_glowglobes,
    _combat_acquire_frame,
    _planetary_array_conflict_end,
)

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
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
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash
from dune_imperium.records import migration
from dune_imperium.records.migration import migrate_record, replayed, walk
from dune_imperium.rules import UprisingRulesEngine, turn_rows
from dune_imperium.rules.agent_effect_frame import route_box_action
from dune_imperium.rules.agent_effects import resolves_boost_draw
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.board_effects import BOARD_ICON_IMPERIAL_PRIVILEGE
from dune_imperium.rules.contracts import begin_contract_gain, legal_contract_actions
from dune_imperium.rules.effect_steps import (
    completed_whole,
    path_of,
    picked_rows,
    steps_for,
    without_pick,
)
from dune_imperium.rules.effects import board_icon_is_pending
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft_boxes import active_box, tagged
from dune_imperium.rules.immortality import (
    OWED_ORIGIN_RESEARCH,
    advance_research,
    pending_research_bonuses,
)
from dune_imperium.rules.intrigue import current_intrigue_choice_slot
from dune_imperium.rules.leader_abilities import legal_leader_signet_actions
from dune_imperium.rules.pauses import CONTINUE
from dune_imperium.rules.reveal_turn import reveal_pending_gains
from dune_imperium.rules.scouts_effects import SCOUTS_NO_OPTION, reward_was_chosen
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
    # Desert summon for Liet Kynes (two Intrigue cards) at 199: both wait on
    # the Agent turn as rows since codec v149 (cleanup-2b), so both are
    # taken right after the summon (one window at a time before). The Intrigue
    # trash of c7r3 at 233 holds its card and Intrigue card as two owed draws
    # of the research space since codec v149 (cleanup-2b, rule decision 5), and
    # the same bridge takes them right after it, the Intrigue card first.
    "v141-no-tech_module-app_ai-9711": {
        "piter_reward": [169, 170, 368, 368],
        "reshuffle_renamed": [170, 369],
        "planetologist_intrigue": [199, 199],
        "owed_draw": [233, 233, 235, 290, 371],
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
    # 272 trashes from hand in an Intrigue choice that offers no owed draw;
    # the reshuffle of an Agent box's draw at 195 is named after the box
    # (codec v149, cleanup-2c-2).
    "v141-app_ai-1050": {"owed_draw": [225, 269], "reshuffle_renamed": [195]},
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
# Bridges of codec v149 a fixture of ``OQ106_FIXTURES`` also uses (kept out of
# that table, which records where each OQ-106 bridge fires): the Harvest Cells
# acquisition its recorded cleanup answered, taken right after the play.
V149_FIXTURE_BRIDGES: dict[str, set[str]] = {
    "v141-no-tech_module-app_ai-9711": {"harvest_cells_at_once"},
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


def _this_engine_game(seed: int, config: RulesetConfig = FULL) -> GameReplay:
    """A whole heuristic game on this engine, stamped as its saves are."""

    agents = [make_agent("heuristic", 10 + seat) for seat in range(4)]
    replay = run_policy_game(ENGINE, config, seed, agents).replay
    return replace(replay, action_codec_version=ACTION_CODEC_VERSION)


@pytest.fixture(scope="module")
def game() -> GameReplay:
    """A whole heuristic game on this engine with every module on.

    Seed 187; seed 1 until codec v146: optional Agent-turn effects no longer
    offer a refusal (OQ-095 (2), user ruling 2026-10-14), which moved seed
    1's game off these tests' preconditions -- a seat now deploys troops
    before drawing the Intrigue card a Research owes it (an older engine
    drew it inside the Research, so the bridge takes it first), and no seat
    places with Navigation Chamber's discount any more. Seed 102 then, until
    codec v149 (cleanup-2a) asked Scouts seats with nothing to take, an
    extra decision that moved 102's game off them the same way; of the
    seeds that met them then (95, 96, 102, 141, 149, 154, 182, 186, 187,
    194), 95 still did. Seed 95 until cleanup-2b kept an in-turn optional
    trash on the turn as rows (a seat now takes a Reveal's Research before
    an owed Intrigue card); of those ten, 187 still meets them all. The
    triggered-draw test needs a game whose only split steps are owed draws
    and has a seed of its own.
    """

    return _this_engine_game(187)


def _states(replay: GameReplay) -> list[GameState]:
    """The state before every recorded step."""

    states = [ENGINE.reset(replay.ruleset, replay.seed)]
    for step in replay.steps:
        states.append(ENGINE.apply(states[-1], step).state)
    return states[:-1]


EFFECT_BRIDGES = ("effect_step", "effect_last_step")


@functools.cache
def _effect_runs(replay: GameReplay) -> dict[int, tuple[DomainAction, tuple[int, ...]]]:
    """The whole actions this engine's Agent-turn effect rows stand for (stage
    B3, OQ-111): each step that ends one, with the whole action and the steps
    before it that picked its effect and targets. An engine before codec v150
    recorded the whole action in one step. A whole action that is its own
    one step (a Commander's Skill, ``choose_skill``, stage B3d-2a) is
    recorded alike."""

    runs: dict[int, tuple[DomainAction, tuple[int, ...]]] = {}
    for index, (state, step) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        if not isinstance(step, DomainAction):
            continue
        whole = completed_whole(state, step, ENGINE.whole_actions(state, step.actor))
        if whole is not None and whole != step:
            picks = len(picked_rows(state))
            runs[index] = (whole, tuple(range(index - picks, index)))
    return runs


def _effect_pick_steps(replay: GameReplay) -> set[int]:
    """The steps that only pick toward a whole action (``_effect_runs``)."""

    return {pick for _, picks in _effect_runs(replay).values() for pick in picks}


def _whole(replay: GameReplay, index: int) -> DomainAction:
    """Step ``index`` as an engine before codec v150 recorded it: the whole
    action it ends, or the step itself."""

    run = _effect_runs(replay).get(index)
    if run is not None:
        return run[0]
    step = replay.steps[index]
    assert isinstance(step, DomainAction)
    return step


@functools.cache
def _held_steps(replay: GameReplay) -> dict[int, str]:
    """This engine's steps an engine before v142 made inside another step.

    Codec v142 (OQ-106) holds a hidden draw (and a Scouts auction reward)
    as a step of its own; a record of an older engine has no such step, and
    the ``follows`` bridge named here adds it back.
    """

    held: dict[int, str] = {}
    runs = _effect_runs(replay)
    for index, (state, recorded) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        if isinstance(recorded, ChanceOutcome):
            if recorded.decision_id.endswith(":scouts_reward:pause"):
                held[index] = "scouts_reward_pause"
            continue
        # An engine before v142 held these as whole actions (stage B3).
        step = runs[index][0] if index in runs else recorded
        state = without_pick(state)
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


# The ``follows`` bridges of codec v152 (engine audit 2026-10-22, P4-P6).
_V152_FOLLOWS = (
    ("conspiracy_spice", migration._conspiracy_spice),
    ("breakthrough_research", migration._breakthrough_research),
    ("guild_envoy_draw", migration._guild_envoy_draw),
)


@functools.cache
def _v152_split_steps(replay: GameReplay) -> dict[int, str]:
    """This engine's steps an engine before v152 made inside the step before
    them: Interstellar Conspiracy's spice after its Faction choice,
    Scientific Breakthrough's Research after its trash, Guild Envoy's draw
    after its discard. Each is the whole action the ``follows`` bridge named
    here adds after the previous one; one this engine's seat took later
    stays recorded (no older engine recorded that order)."""

    runs = _effect_runs(replay)
    picks = _effect_pick_steps(replay)
    states = _states(replay)
    split: dict[int, str] = {}
    previous: DomainAction | None = None
    for index, recorded in enumerate(replay.steps):
        if index in picks:
            continue
        if not isinstance(recorded, DomainAction):
            previous = None
            continue
        whole = runs[index][0] if index in runs else recorded
        if previous is not None:
            state = without_pick(states[index])
            decision = ENGINE.current_decision(state)
            assert decision is not None
            for name, follow in _V152_FOLLOWS:
                if follow(ENGINE, state, decision, previous) == whole:
                    split[index] = name
                    break
        previous = whole
    return split


def _pass_alone_steps(replay: GameReplay) -> set[int]:
    """This engine's passes of a Scouts mission window that offered a seat
    the pass alone (OQ-131); an engine before v152 skipped the seat."""

    return _only_choice_in(replay, FrameKind.SCOUTS_MISSION, "scouts_decline_mission")


@functools.cache
def _equilibrium_alone_steps(replay: GameReplay) -> frozenset[int]:
    """This engine's answers of a Political Equilibrium window with one row
    (OQ-131, user decision 2026-10-25); an engine before v152 took a lone
    highest track's loss itself and skipped a seat with every track at 0."""

    found = set()
    for index, (state, step) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        frame = state.decision_stack[-1] if state.decision_stack else None
        if (
            isinstance(step, DomainAction)
            and frame is not None
            and frame.kind == FrameKind.SCOUTS_EFFECT
            and dict(frame.context).get("item") == "political_equilibrium"
            and len(ENGINE.whole_actions(state, step.actor)) == 1
        ):
            found.add(index)
    return frozenset(found)


def _never_asked_steps(replay: GameReplay) -> set[int]:
    return _pass_alone_steps(replay) | set(_equilibrium_alone_steps(replay))


def _v152_counts(replay: GameReplay) -> Counter[str]:
    """The bridge counts of those steps in a record before v152."""

    counts = Counter(_v152_split_steps(replay).values())
    passes = len(_pass_alone_steps(replay))
    if passes:
        counts[migration.MISSION_PASS_ALONE] = passes
    alone = len(_equilibrium_alone_steps(replay))
    if alone:
        counts[migration.EQUILIBRIUM_ALONE] = alone
    return counts


def _dropped(replay: GameReplay, codec: int, drop: set[int] | None = None) -> set[int]:
    """The steps of ``replay`` an engine of ``codec`` would not have recorded:
    before v142 the steps it made inside another (``_held_steps``), before
    v149 the confirms of a Scouts choice with nothing to take, which it
    skipped unasked (``_no_option_steps``), and before v150 the icon rows
    of a reward it paid in one step (``_reward_icon_steps``) and the steps
    that only pick toward a whole action (``_effect_pick_steps``), and
    before v152 the parts of an Agent box it did inside the step before
    them (``_v152_split_steps``)."""

    return (
        set(drop or ())
        | (set(_v152_split_steps(replay)) if codec < 152 else set())
        | (_never_asked_steps(replay) if codec < 152 else set())
        | (set(_held_steps(replay)) if codec < 142 else set())
        | (_no_option_steps(replay) if codec < 149 else set())
        | (_reward_icon_steps(replay) if codec < 150 else set())
        | (_effect_pick_steps(replay) if codec < 150 else set())
    )


REWARD_ICON_BRIDGES = ("combat_reward_icon_follow", "combat_reward_icon")


@functools.cache
def _reward_icon_steps(replay: GameReplay) -> frozenset[int]:
    """The icon rows of a Conflict or Contract reward's window (stage B2,
    OQ-112), and the effect rows of a Contract's icons waiting on its
    owner's turn (stage B3b, OQ-112 (4)). The heuristic answers them in the
    order an engine before v150 paid the reward (``agents.engine_order``),
    which the reward bridges replay."""

    rewards = ("resolve_combat_reward_icon", "resolve_contract_reward_icon")
    runs = _effect_runs(replay)
    return frozenset(
        index
        for index, step in enumerate(replay.steps)
        if isinstance(step, DomainAction)
        and (
            step.action_id in rewards
            or (index in runs and runs[index][0].action_id in rewards)
        )
    )


def _effect_counts(replay: GameReplay, codec: int) -> dict[str, int]:
    """The effect bridges' counts for ``_older(replay, codec)`` (stage B3): one
    ``effect_step`` for each pick before a whole action's last step, one
    ``effect_last_step`` for each whole action. A whole action a ``follows``
    bridge takes back (``_held_steps``) is that bridge's step, not these, and
    neither is the confirm of a Scouts choice with nothing to take, which an
    engine before v149 skipped unasked (``_no_option_steps``; since stage
    B3d-3 it is a ``confirm_empty`` row, so it is a run of its own), nor a
    part an engine before v152 did inside the step before it
    (``_v152_split_steps``)."""

    held = set(_held_steps(replay)) if codec < 142 else set()
    if codec < 152:
        held |= set(_v152_split_steps(replay)) | _never_asked_steps(replay)
    # A Contract's in-turn icon row is the reward bridges' (stage B3b).
    rewards = _reward_icon_steps(replay) if codec < 150 else frozenset()
    skipped = _no_option_steps(replay) if codec < 149 else set()
    runs = [
        picks
        for index, (_, picks) in _effect_runs(replay).items()
        if index not in held and index not in rewards and index not in skipped
    ]
    return {
        "effect_step": sum(len(picks) for picks in runs),
        "effect_last_step": len(runs),
    }


def _reward_icon_counts(
    record: migration.MigratedRecord, replay: GameReplay
) -> Counter[str]:
    """``record``'s bridge counts less those of the reward bridges, which
    between them must have added every icon row back, those of the effect
    bridges (stage B3), which must have expanded every whole action, and
    those of the v152 bridges, which must have added every part an older
    engine did inside the step before it and every mission pass it never
    asked for."""

    counts = Counter(record.bridge_counts())
    added = sum(counts.pop(name, 0) for name in REWARD_ICON_BRIDGES)
    assert added == len(_reward_icon_steps(replay))
    expected = _effect_counts(replay, record.replay.action_codec_version)
    assert {name: counts.pop(name, 0) for name in EFFECT_BRIDGES} == expected
    split = (
        _v152_counts(replay)
        if record.replay.action_codec_version < 152
        else Counter[str]()
    )
    v152 = [name for name, _ in _V152_FOLLOWS] + [
        migration.MISSION_PASS_ALONE,
        migration.EQUILIBRIUM_ALONE,
    ]
    assert {name: counts.pop(name, 0) for name in v152} == {
        name: split[name] for name in v152
    }
    return counts


def _no_option_steps(replay: GameReplay) -> set[int]:
    return _only_choice_in(replay, FrameKind.SCOUTS_CHOICE, SCOUTS_NO_OPTION)


def _no_option_counts(replay: GameReplay) -> dict[str, int]:
    """The bridge counts of those confirms in a record before v149."""

    found = len(_no_option_steps(replay))
    return {"scouts_no_option_window": found} if found else {}


def _older(replay: GameReplay, codec: int, drop: set[int] | None = None) -> GameReplay:
    """``replay`` as an engine of ``codec`` would have recorded it.

    Besides ``drop``, a record older than v142 loses the steps that engine
    made inside another (``_held_steps``), and one older than v150 holds each
    whole action in one step (``_effect_runs``) instead of its effect and
    target rows.
    """

    dropped = _dropped(replay, codec, drop)
    runs = _effect_runs(replay) if codec < 150 else {}
    steps = tuple(
        runs[index][0] if index in runs else step
        for index, step in enumerate(replay.steps)
        if index not in dropped
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
    """Steps answering ``frame`` with ``action_id`` where nothing else was legal.

    Stage B3d-3: a refusal or empty confirmation is recorded as its
    ``decline`` or ``confirm_empty`` row, so ``action_id`` is read off the
    whole action the step ends (``_whole``)."""

    found = set()
    for index, (state, step) in enumerate(
        zip(_states(replay), replay.steps, strict=True)
    ):
        if (
            isinstance(step, DomainAction)
            and _whole(replay, index).action_id == action_id
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
    assert _reward_icon_counts(record, game) == {
        "pause": len(pauses - set(_held_steps(game))),
        **_held_counts(game),
        **_no_option_counts(game),
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


def test_a_scouts_seat_with_nothing_to_take_is_answered_only_before_v149(
    game: GameReplay,
) -> None:
    # Cleanup-2a asks such a seat; an older engine skipped it unasked.
    confirms = _only_choice_in(game, FrameKind.SCOUTS_CHOICE, SCOUTS_NO_OPTION)
    assert confirms

    before = migrate_record(_older(game, 148))
    assert before.complete
    assert before.bridge_counts()["scouts_no_option_window"] == len(confirms)
    assert [migrated.step for migrated in before.steps] == _steps(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    after = migrate_record(_older(game, 149, confirms))
    assert after.divergence is not None
    first = min(confirms)
    assert after.divergence.recorded_index == first - sum(
        1 for index in _dropped(game, 149, confirms) if index < first
    )


def test_an_in_turn_research_decline_is_dropped_only_before_v149(
    game: GameReplay,
) -> None:
    # Cleanup-2b: a research bonus raised in its owner's turn waits on the
    # turn with no refusal, so an older engine's in-turn
    # ``decline_research_bonus`` has no counterpart; it leaves the same
    # state, and is dropped once this engine refuses it.
    states = _states(game)
    index = next(
        i
        for i, (state, step) in enumerate(zip(states, game.steps, strict=True))
        if isinstance(step, DomainAction)
        and pending_research_bonuses(state, step.actor)
    )
    seat = _actor(game, index)
    decline = DomainAction(action_id="decline_research_bonus", actor=seat)

    def with_decline(codec: int) -> tuple[GameReplay, int]:
        older = _older(game, codec)
        position = _position(game, codec, index)
        steps = (*older.steps[:position], decline, *older.steps[position:])
        return replace(older, steps=steps), position

    before, position = with_decline(148)
    record = migrate_record(before)
    assert record.complete, record.divergence
    assert (position, "turn_row_refusal") in record.dropped
    assert [migrated.step for migrated in record.steps] == _steps(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash

    after, position = with_decline(149)
    stamped = migrate_record(after)
    assert stamped.divergence is not None
    assert stamped.divergence.recorded_index == position


def test_an_in_turn_trash_decline_is_dropped_only_before_v149(
    game: GameReplay,
) -> None:
    # Cleanup-2b: an optional trash raised in its owner's turn waits on the
    # turn with no refusal, so an older engine's in-turn
    # ``decline_optional_trash`` has no counterpart either.
    states = _states(game)
    index = next(
        i
        for i, (state, step) in enumerate(zip(states, game.steps, strict=True))
        if isinstance(step, DomainAction)
        and (frame := turn_rows.rows_frame(state, step.actor)) is not None
        and any(
            kind == turn_rows.OPTIONAL_TRASH for kind, _, _ in turn_rows.pending(frame)
        )
    )
    seat = _actor(game, index)
    decline = DomainAction(action_id="decline_optional_trash", actor=seat)

    def with_decline(codec: int) -> tuple[GameReplay, int]:
        older = _older(game, codec)
        position = _position(game, codec, index)
        steps = (*older.steps[:position], decline, *older.steps[position:])
        return replace(older, steps=steps), position

    before, position = with_decline(148)
    record = migrate_record(before)
    assert record.complete, record.divergence
    assert (position, "turn_row_refusal") in record.dropped
    assert [migrated.step for migrated in record.steps] == _steps(game.steps)
    assert canonical_state_hash(record.state) == game.expected_state_hash

    after, position = with_decline(149)
    stamped = migrate_record(after)
    assert stamped.divergence is not None
    assert stamped.divergence.recorded_index == position


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
    assert _reward_icon_counts(before, game) == {
        "combat_intrigue_pass": 1,
        **_held_counts(game),
        **_no_option_counts(game),
    }
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
    """Steps ending a whole action that names an icon where it was the only
    icon offered (a placed card's box: a graft partner's box 1 rows carry
    ``box=1``, codec v143). The whole action is what an engine before codec
    v150 recorded (``_effect_runs``)."""

    states = _states(game)
    return [
        index
        for index, (whole, _) in sorted(_effect_runs(game).items())
        if whole.action_id == "resolve_agent_card_effect"
        and tuple(key for key, _ in whole.arguments) == ("effect",)
        and [
            action
            for action in ENGINE.whole_actions(states[index], whole.actor)
            if action.action_id == "resolve_agent_card_effect"
        ]
        == [whole]
    ]


def test_a_card_effect_recorded_before_v137_named_its_icon_is_rewritten(
    game: GameReplay,
) -> None:
    index = _card_effect_steps(game)[0]
    recorded = _whole(game, index)
    plain = DomainAction(action_id=recorded.action_id, actor=recorded.actor)
    state = _states(game)[index]
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    # The bridge names the icon; the whole action it names is then this
    # engine's effect row (stage B3), which is the migrated step.
    assert migration._named_card_effect(ENGINE, state, decision, plain) == recorded

    older, position = _older_with(game, 136, index, plain)
    before = migrate_record(older)
    assert before.complete
    # ``effect_last_step`` rewrote the step last, so it names it (and counts
    # in ``_reward_icon_counts``) where the icon's bridge did before it.
    assert _reward_icon_counts(before, game) == {
        **_held_counts(game),
        **_no_option_counts(game),
    }
    assert before.steps[index].step == game.steps[index]
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
    rows = _reward_icon_steps(replay)
    picks = _effect_pick_steps(replay)
    unasked = _no_option_steps(replay)
    runs = _effect_runs(replay)
    for index, step in enumerate(replay.steps):
        # A whole action is one step before codec v150 (``_effect_runs``).
        whole = runs[index][0] if index in runs else step
        if index in rows or index in picks or index in unasked:
            # Paid in one step, picked toward a whole action, or skipped
            # unasked (``_dropped``).
            pass
        elif isinstance(whole, DomainAction):
            _, plain, box = route_box_action(without_pick(state), whole)
            if box is not None and box != active:
                steps.append(DomainAction("switch_graft_card", whole.actor))
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

    picks = _effect_pick_steps(game)
    runs = _effect_runs(game)
    boxed = sum(
        isinstance(step, DomainAction)
        and ("box", 1) in _whole(game, index).arguments
        for index, step in enumerate(game.steps)
        if index not in picks
    )
    assert boxed
    # A whole action of box 1 is tagged, then rewritten to its rows by
    # ``effect_last_step``, which names the step last (stage B3); the other
    # steps of box 1 keep ``graft_box``.
    tagged_directly = sum(
        isinstance(step, DomainAction) and ("box", 1) in step.arguments
        for index, step in enumerate(game.steps)
        if index not in picks and index not in runs
    )
    older = _with_graft_switches(game)
    switches = sum(
        isinstance(step, DomainAction) and step.action_id == "switch_graft_card"
        for step in older.steps
    )
    assert switches >= boxed > 0

    record = migrate_record(older)

    assert record.complete, record.divergence
    assert [migrated.step for migrated in record.steps] == list(game.steps)
    assert _reward_icon_counts(record, game) == {
        "graft_switch": switches,
        **({"graft_box": tagged_directly} if tagged_directly else {}),
        **_no_option_counts(game),
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
    # The older engine's move is a whole action (``_effect_runs``); box 1's
    # carries ``box=1`` here.
    index, (step, _) = next(
        (index, run)
        for index, run in sorted(_effect_runs(game).items())
        if ("box", 1) in run[0].arguments
    )
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
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == placed
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    state = apply_placement(ENGINE, state, placement).state
    choice = DomainAction("choose_graft_partner", 0, arguments=(("card_id", partner),))
    return apply_whole(ENGINE, state, choice).state


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

    start = apply_whole(
        ENGINE, _grafted_turn(_PITER, _INFILTRATOR, "assembly_hall"), _PAY_PITER
    ).state
    # Taken as recorded the step would draw Piter's two cards.
    assert _CARDS in ENGINE.whole_actions(start, 0)
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
    # The paid troop is box 1's whole action, taken as this engine's row.
    paid = DomainAction(
        "lose_agent_card_troop", 0, arguments=(("box", 1), ("zone", "garrison"))
    )
    rows = path_of(start, paid)
    assert rows is not None
    assert [migrated.step for migrated in record.steps] == list(rows)
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
    assert set(record.bridge_counts()) <= {
        *_held_counts(game),
        *_no_option_counts(game),
        *REWARD_ICON_BRIDGES,
        *EFFECT_BRIDGES,
    }
    assert [migrated.step for migrated in record.steps] == _steps(game.steps[:index])


def test_a_triggered_draw_an_older_engine_drew_at_once_follows_its_trigger() -> None:
    # Codec v142 (user ruling 2026-10-10, OQ-106) holds a triggered draw as
    # the owner's own ``draw_owed_*`` step; an older engine drew it inside
    # the trigger, so its record has no such step. Dropped from this
    # engine's record (whose heuristic takes each at once), each is taken
    # right after its trigger again, so the game comes back step for step.
    # Seed 21's game (one owed draw, the Intrigue card of a research space);
    # its other split steps are dropped with the draw and taken back by
    # their own bridges. (Seed 10 until codec v149, whose game
    # split nothing but its three owed draws, one of three such seeds of
    # 1-200; cleanup-2a's Scouts confirms moved every game, none of 1-200
    # splits only owed draws now, and seed 10's heuristic takes one owed
    # Intrigue card a step late. Seeds 5, 6 and 20 were then the first that
    # brought every owed draw back; cleanup-2b's turn rows moved them too,
    # and of 1-60 seeds 4, 12, 21, 22, 26, 43, 48 and 53 did; the
    # Conflict-end change (2026-10-18: troops back before the windows,
    # Harvest Cells resolving as it is played) moved them again, and of
    # 1-60 seeds 21, 22 and 48 do. The fixture's
    # seed 1 drew one a step late until codec v146, OQ-095 (2).)
    game = _this_engine_game(21)
    # Since stage B3d-4 (D-3) an owed draw is a ``draw`` row naming what
    # earned it; the whole action it stands for is still ``draw_owed_*``.
    owed = {
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction)
        and _whole(game, index).action_id.startswith("draw_owed_")
    }
    assert owed
    held = _held_steps(game)
    assert {index for index, name in held.items() if name == "owed_draw"} == owed

    before = migrate_record(_older(game, 141))
    assert before.complete, before.divergence
    assert _reward_icon_counts(before, game) == {
        **_held_counts(game),
        **_no_option_counts(game),
    }
    assert before.bridge_counts()["owed_draw"] == len(owed)
    assert [migrated.step for migrated in before.steps] == _steps(game.steps)
    assert canonical_state_hash(before.state) == game.expected_state_hash

    # A v142 record took every such draw itself.
    after = migrate_record(_older(game, 142, owed))
    assert after.divergence is not None


def test_a_scouts_line_draw_an_older_engine_drew_at_once_follows_its_choice() -> None:
    # Codec v142 (user ruling 2026-10-10, OQ-106) holds a draw printed after
    # one of an Arrakeen Scouts line's reward choices as the line's own
    # ``scouts_rewards_first``, then its only action; an older engine drew
    # it in the choice's step, so its record has no such step. Seed 3's
    # heuristic game without Immortality holds one (see the seed history
    # below). Dropped from this engine's
    # record with the game's other held steps, each is taken right after
    # the same choice again. (Seed 3 until codec v146: optional Agent-turn
    # effects offer no refusal since then, OQ-095 (2), and seed 3's game no
    # longer holds such a draw; seed 5, whose game held two (round 4, Water
    # Discipline's card after its trash; round 8, Leverage's Intrigue card),
    # was the first of 1-200 that did until the Conflict-end change
    # (2026-10-18: troops back before the windows, Harvest Cells resolving
    # as it is played) moved every game; of 1-60 seeds 15, 29, 48, 50 and 60
    # hold one that comes back step for step, and 15 is the first. Codec
    # v152's Political Equilibrium windows, OQ-131, moved seed 15 too, and
    # none of seeds 1-600 meets this test with every module on: wherever a
    # Scouts draw is held, a seat also takes an Immortality research
    # space's icons after another move, an order no engine before v149
    # recorded (it resolved them inside the research). The game leaves
    # Immortality, and Go to 11 with it, out; of seeds 1-60 then 3, 27 and
    # 57 meet it, and 3 is the first.)
    game = _this_engine_game(
        3, replace(FULL, immortality=False, go_to_11=False)
    )
    held = _held_steps(game)
    scouts = [index for index, name in held.items() if name == "scouts_held_draw"]
    assert scouts

    before = migrate_record(_older(game, 141))
    assert before.complete, before.divergence
    assert _reward_icon_counts(before, game) == {
        **_held_counts(game),
        **_no_option_counts(game),
    }
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
    "path", sorted(DATA.glob("*.json")), ids=lambda path: path.stem
)
def test_walk_yields_the_states_a_replay_of_the_record_reaches(path: Path) -> None:
    # ``walk`` yields the states ``migrate_record`` took its steps from
    # instead of replaying the record (2026-10-21). Every bridge path of the
    # older engines' records -- answers, follows, held turn rows, steps asked
    # earlier, effect steps -- records the state it applied each step to, so
    # these are the states a replay from the reset reaches.
    # States compare equal field by field (stricter than the state hash, and
    # far cheaper: hashing every state took seconds a record).
    document = json.loads(path.read_text(encoding="utf-8"))
    record = migrate_record(parse_save_document(document, check_versions=False).replay)

    kept = list(walk(record, ENGINE))
    again = list(replayed(record, ENGINE))

    assert record.walked is not None and record.walked[0] is record.steps
    assert [m for _, m in kept] == [m for _, m in again] == list(record.steps)
    assert all(a == b for (a, _), (b, _) in zip(kept, again, strict=True))


def test_walk_replays_a_record_rebuilt_with_other_steps(game: GameReplay) -> None:
    # A migration module may rebuild the record with steps of its own
    # (tests/unit/records/test_corpus_check.py); the kept states belong to
    # the steps they were taken for, so ``walk`` replays the new ones.
    record = migrate_record(game)
    shorter = replace(record, steps=record.steps[:200])

    walked = list(walk(shorter, ENGINE))

    assert shorter.walked is record.walked
    assert [m for _, m in walked] == list(shorter.steps)
    assert all(
        a == b
        for (a, _), (b, _) in zip(walked, replayed(shorter, ENGINE), strict=True)
    )
    assert walked[0][0] == ENGINE.reset(game.ruleset, game.seed)


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
        *(
            (name, 141, set(fired) | V149_FIXTURE_BRIDGES.get(name, set()))
            for name, fired in OQ106_FIXTURES.items()
        ),
        ("v145-no-immortality-no-go_to_11-heuristic-208", 145, set()),
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
    # pending and the recorded turn end lapses it; and (OQ-019) the empty
    # second Scouts mission collection Reverend Mother's repeat queued.
    # Codec v147 (OQ-095 (7) addition) drops a Reveal choice's defer and
    # resume and an optional Reveal choice's refusal: every pending choice is
    # offered at once and the recorded ``finish_reveal`` lapses one left
    # unused. Codec v149 (cleanup-2b) drops an in-turn refusal of a research
    # bonus or an optional trash: it waits on the turn as rows and the
    # recorded turn end lapses it. Codec v149 (user decision 2026-10-18:
    # Harvest Cells resolves as it is played) also drops the
    # ``resolve_intrigue_rewards`` an older engine asked at its cleanup for
    # a Harvest Cells played in the Conflict-end window: its specimens come
    # with the play here, so the step has no counterpart. Every other
    # recorded step applies.
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
            ("scouts_collect_mission", migration.REPEATED_MISSION_DROPPED),
            ("defer_reveal_choice", migration.REVEAL_DEFER_DROPPED),
            ("resume_reveal_choice", migration.REVEAL_RESUME_DROPPED),
            *(
                (refusal, migration.REVEAL_REFUSAL_DROPPED)
                for refusal in migration._OPTIONAL_REVEAL_REFUSALS
            ),
            ("decline_reveal_spy_recall", migration.REVEAL_REFUSAL_BY_ORDER),
            *(
                (refusal, migration.TURN_ROW_REFUSAL_DROPPED)
                for refusal in migration._TURN_ROW_REFUSALS
            ),
            ("resolve_intrigue_rewards", migration.HARVEST_CELLS_REWARDS_DROPPED),
        ), (index, step, reason)
    assert [
        index
        for index, reason in record.dropped
        if reason == migration.GRAFT_SWITCH_DROPPED
    ] == switches
    dropped = [index for index, _ in record.dropped]
    assert sorted((*recorded, *dropped)) == list(range(len(replay.steps)))


def test_a_signet_ring_effect_recorded_without_its_icon_is_named_then_expanded() -> (
    None
):
    # v135-app_ai-3 step 134: seat 3's Signet Ring (Lady Amber Metulli) resolved
    # its solari icon as a plain ``resolve_agent_card_effect``, the only icon
    # offered then (``agent_card_effect_named``, codec v137). The bridge names
    # the icon and ``effect_last_step`` takes its row (stage B3), which names
    # the step last, so the fixture's bridge counts do not hold the icon's.
    replay = _fixture("v135-app_ai-3")
    recorded = replay.steps[134]
    assert recorded == DomainAction("resolve_agent_card_effect", 3)

    record = migrate_record(replay)

    assert record.complete, record.divergence
    migrated = next(m for m in record.steps if m.recorded_index == 134)
    assert migrated.bridge == "effect_last_step"
    assert migrated.step == DomainAction(
        "gain",
        3,
        (
            ("icon", "solari"),
            ("printed", "lady_amber_metulli"),
            ("source", "leader"),
        ),
    )


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
        # The recorded recall, which this engine takes as its target row.
        recorded = replay.steps[before.recorded_index]
        assert isinstance(recorded, DomainAction)
        assert "imperial_privilege" in recorded.action_id


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
        # The rules' whole action: the mission window shows the plain way as
        # its ``join`` effect row (stage B3d-2b).
        and DomainAction(
            action_id="scouts_join_mission",
            actor=migrated.step.actor,
            arguments=(("target", ""),),
        )
        in engine.whole_actions(state, migrated.step.actor)
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
    # with a reward missing. Since codec v150 a Conflict reward's icon rows
    # follow the step that paid the reward too (stage B2), so the first
    # step that needs two follows comes earlier, and the record stops there.
    replay = _fixture("v141-heuristic-150")
    complete = migrate_record(replay)
    assert _fired_after(complete, "piter_reward") == [557, 557]
    follows = Counter(
        after
        for bridge in migration.BRIDGES
        if bridge.follows
        for after in _fired_after(complete, bridge.name)
    )
    assert follows[557] == 2
    first = min(index for index, count in follows.items() if count >= 2)
    assert first < 557
    before = next(
        state for state, migrated in walk(complete) if migrated.recorded_index == first
    )
    monkeypatch.setattr(migration, "MAX_FOLLOWS_PER_STEP", 1)

    record = migrate_record(replay)

    assert record.divergence is not None
    assert record.divergence.recorded_index == first
    assert "did not settle" in record.divergence.reason
    assert record.steps[-1].recorded_index == first - 1
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
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == dagger
        and dict(action.arguments)["space_id"] == "assembly_hall"
        and "graft" not in dict(action.arguments)
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    state = apply_placement(ENGINE, state, placement).state
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
    migrated = migration._Taken()
    followed = migration._follow(ENGINE, pressed.state, _PRESS, older, migrated)
    assert followed is not None
    assert [step.bridge for step in migrated.steps] == ["owed_draw"]
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
    # The seat's own step in the reopened turn is not the next seat's (an
    # older record's step is a whole action, stage B3).
    own = next(
        action for action in ENGINE.whole_actions(followed, 0) if action != _PRESS
    )
    own_bridge = migration._bridge(ENGINE, followed, own, older)
    # (An older record's whole action is taken as its effect steps, B3.)
    assert own_bridge is None or own_bridge[0].name == "effect_step"
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
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == placed
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    state = apply_placement(ENGINE, state, placement).state
    state = apply_whole(
        ENGINE, state, DomainAction("choose_graft_partner", 0, (("card_id", partner),))
    ).state
    while rest := [
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id
        in (
            "resolve_board_effect",
            "resolve_agent_card_effect",
            "resolve_faction_influence",
        )
        and action not in skip
    ]:
        state = apply_whole(ENGINE, state, rest[0]).state
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
    drawn = apply_whole(ENGINE, state, _PARTNER_DRAW).state
    assert _PRESS in ENGINE.legal_actions(drawn, 0)
    # Only before the press, and only for a record before codec v144.
    other = next(
        action for action in ENGINE.whole_actions(state, 0) if action != _PARTNER_DRAW
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
    drawn = apply_whole(ENGINE, state, _GHOLA_COPY_DRAW).state
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
    migrated = migration._Taken()
    choice = DomainAction(
        "choose_graft_partner", 0, (("card_id", "imperium:truthtrance:0"),)
    )

    followed = migration._follow(ENGINE, placed, choice, _bridges_for(141), migrated)

    assert followed is not None
    assert [step.bridge for step in migrated.steps] == []


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
    # Its own box's trash icon (stage B3c-2b: the row names the icon).
    trash = DomainAction(
        "trash_optional_card",
        0,
        (
            ("card_id", throne),
            ("printed", "throne_room_politics"),
            ("source", "agent_card"),
        ),
    )
    decline = DomainAction("decline_optional_trash", 0)
    while True:
        legal = ENGINE.whole_actions(state, 0)
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
        state = apply_whole(ENGINE, state, step).state
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
            # Two replacements in the Agent turn, both drawn after the
            # summon (cleanup-2b; [211, 212] while each had its window).
            {"intrigue_held_rewards": [46], "planetologist_intrigue": [211, 211]},
        ),
        (
            "v141-heuristic-150",
            # The reshuffle at 420 is an Agent box icon's draw, named after
            # the box (codec v149, cleanup-2c-3).
            {
                "piter_reward": [557, 557],
                "owed_draw": [558],
                "reshuffle_renamed": [420],
            },
        ),
        (
            "v141-no-immortality-no-go_to_11-heuristic-1211",
            # The reshuffle at 789 is an Agent box's, named after the box
            # (codec v149, cleanup-2c-2).
            {
                "scouts_held_draw": [471],
                "owed_draw": [710],
                "reshuffle_renamed": [789],
            },
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
def test_a_migrated_record_stamped_with_this_codec_needs_no_bridge(name: str) -> None:
    # The migrated steps, with every split step in its place, are a record
    # of this engine: stamped with its codec they replay as they are. A
    # follows bridge open to them would take a split step before the record
    # does. (Stamped v142 until codec v149 made a research space's icons
    # steps of their own: a record of v142 to v148 has none of those rows, so
    # the ``research_icon_order`` follows bridge, open to it, would add the
    # row the migrated steps already hold. The v142 bridges alone are kept
    # away from a v142 stamp by the test above.)
    migrated = migrate_record(_fixture(name))
    replay = replace(
        migrated.replay,
        steps=tuple(step.step for step in migrated.steps),
        expected_state_hash=canonical_state_hash(migrated.state),
        action_codec_version=ACTION_CODEC_VERSION,
    )

    assert migrate_record(replay).exact


def test_a_recorded_reshuffle_takes_the_id_of_the_one_this_engine_asks() -> None:
    # Insider Information's held draw reshuffles under ``...:rewards`` (the
    # line's own ``:draw`` dropped, codec v149 cleanup-2c-5); v141 recorded
    # the same seat's same pile under ``...:draw``.
    replay = _fixture("v141-heuristic-1027")
    recorded = replay.steps[108]
    assert isinstance(recorded, ChanceOutcome)

    record = migrate_record(replay)

    renamed = next(step for step in record.steps if step.recorded_index == 108)
    assert renamed.bridge == "reshuffle_renamed"
    assert isinstance(renamed.step, ChanceOutcome)
    assert renamed.step == ChanceOutcome(
        recorded.decision_id.replace(":draw:", ":rewards:"), recorded.values
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
        # This engine's own steps up to the reshuffle, its old id kept, but
        # the reward icon rows a v142 engine did not have (codec v150).
        migrated = migrate_record(replace(replay, steps=replay.steps[:108]))
        replay = replace(
            replay,
            steps=(
                *(
                    step.step
                    for step in migrated.steps
                    if step.bridge not in REWARD_ICON_BRIDGES
                ),
                recorded,
            ),
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


def test_a_repeat_s_empty_mission_collection_is_dropped() -> None:
    """Reverend Mother's repeat on Desert Tactics, after the seat collected
    its Fedaykin Assistance troops there, queued the Scouts collection
    again on a recording engine before codec v146; the second collection
    took nothing. This engine does not queue it (OQ-019, user ruling
    2026-10-14), so that one recorded step is dropped and the game still
    ends in the recorded state."""

    name = "v145-no-immortality-no-go_to_11-heuristic-208"
    document = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    replay = parse_save_document(document, check_versions=False).replay

    record = migrate_record(replay)

    assert record.complete, record.divergence
    drops = [
        index
        for index, reason in record.dropped
        if reason == migration.REPEATED_MISSION_DROPPED
    ]
    assert drops == [555]
    step = replay.steps[555]
    assert isinstance(step, DomainAction)
    assert step.action_id == "scouts_collect_mission"
    # The repeat was paid earlier in the same turn.
    assert any(
        isinstance(earlier, DomainAction)
        and earlier.action_id == "pay_leader_board_repeat"
        for earlier in replay.steps[540:555]
    )


@pytest.mark.parametrize(
    ("name", "ordered"),
    [
        (
            "v141-no-immortality-no-go_to_11-heuristic-1211",
            # Calculus of Power's trash of Sardaukar Coordination, which
            # Shrouded Counsel's Command trash offered too.
            {830: "calculus_of_power"},
        ),
        (
            "v145-no-immortality-no-go_to_11-heuristic-208",
            # A Public Spectacle placement beside Intelligence Training's,
            # and Intelligence Training's recall-first beside another icon's.
            {600: "public_spectacle", 891: "intelligence_training"},
        ),
    ],
)
def test_a_reveal_choice_takes_the_card_the_recording_engine_had_on_top(
    name: str, ordered: dict[int, str]
) -> None:
    """Codec v147 (OQ-095 (7) addition) offers every pending Reveal choice at
    once and names the card of seven ids with ``source``. A recorded step of
    such an id gets the one card that offers it here, or -- when several
    pending cards do -- the card of the frame the recording engine had on
    top (``_RevealSlot``: its frames in hand order, defers to the queue's
    end, resumes back on top). Every other choice step applies as recorded,
    and the game ends in the recorded state."""

    document = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
    replay = parse_save_document(document, check_versions=False).replay

    record = migrate_record(replay)

    assert record.complete, record.divergence
    # The Reveal frame takes a named whole action as its effect steps (stage
    # B3b-2): the step that ends it is the ``effect_last_step`` bridge's,
    # with the naming bridge and the whole action beside it.
    def naming(migrated: migration.MigratedStep) -> str | None:
        if migrated.named_by is not None:
            assert migrated.bridge == migration.EFFECT_LAST_STEP
            return migrated.named_by
        return migrated.bridge

    def named(migrated: migration.MigratedStep) -> DomainAction:
        whole = migrated.whole or migrated.step
        assert isinstance(whole, DomainAction)
        return whole

    by_order = {
        migrated.recorded_index: dict(named(migrated).arguments)["source"]
        for migrated in record.steps
        if naming(migrated) == migration.REVEAL_SOURCE_BY_ORDER
    }
    assert by_order == ordered
    for migrated in record.steps:
        if naming(migrated) in migration.REVEAL_SOURCE_NAMES:
            whole = named(migrated)
            recorded = replay.steps[migrated.recorded_index or 0]
            assert isinstance(recorded, DomainAction)
            source = dict(whole.arguments).pop("source")
            assert source == migrated.reveal_source
            assert tuple(
                item for item in whole.arguments if item[0] != "source"
            ) == recorded.arguments
    # Stamped v147 the record claims this engine's flow: no v147 step runs.
    stamped = migrate_record(replace(replay, action_codec_version=147))
    assert not {
        name
        for name in stamped.bridge_counts()
        if name.startswith("reveal_")
    }


def _plain_spies_beside_spy_network(*plain: str) -> GameState:
    """Seat 0 revealed the ``plain`` Spy icon cards and Spy Network with an
    empty Spy supply and three Spies on the board: each plain Spy icon may
    pass its recall-first (OQ-057 (14)), Spy Network may recall."""

    from dune_imperium.content.uprising.board import OBSERVATION_POSTS

    owner = PlayerState(
        player_id=0,
        hand=(
            *(f"imperium:{card}:0" for card in plain),
            "imperium:spy_network:0",
        ),
        spies_supply=0,
        spy_post_ids=tuple(post.post_id for post in OBSERVATION_POSTS[:3]),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    return ENGINE.apply(state, DomainAction("reveal_turn", 0)).state


def test_a_recorded_recall_pass_takes_the_plain_spy_icon_on_top() -> None:
    """Codec v147 names the card of a plain Spy icon's pass of its
    empty-supply recall-first (``decline_reveal_spy_recall``) with
    ``source``. A recording engine's pass answered its top frame: a plain
    icon's names that card here; Spy Network's refusal of its optional
    recall has no counterpart, though a plain icon could pass beside it."""

    state = _plain_spies_beside_spy_network("public_spectacle", "covert_operation")
    recorded = DomainAction("decline_reveal_spy_recall", 0)
    for source in ("public_spectacle", "covert_operation"):
        assert migration.rewrite_step(
            ENGINE, state, recorded, 146, reveal_source=source
        ) == DomainAction("decline_reveal_spy_recall", 0, (("source", source),))
    alone = _plain_spies_beside_spy_network("public_spectacle")
    assert migration.rewrite_step(
        ENGINE, alone, recorded, 146, reveal_source="public_spectacle"
    ) == DomainAction("decline_reveal_spy_recall", 0, (("source", "public_spectacle"),))
    for top in (state, alone):
        assert (
            migration.rewrite_step(
                ENGINE, top, recorded, 146, reveal_source="spy_network"
            )
            is None
        )

    # Migrating, the slot drops Spy Network's refusal, by the recording
    # engine's frame order where a plain icon's pass is offered beside it.
    slot = migration._RevealSlot(
        player=0,
        frames=[
            ("imperium:spy_network:0", "recall_spy_to_draw_intrigue_if_two_placed")
        ],
    )
    assert (
        slot.refuses_optional_recall(ENGINE, state, recorded)
        == migration.REVEAL_REFUSAL_BY_ORDER
    )
    assert slot.frames == []


# --- an Influence picked at the top (cleanup-2b, codec v149) -----------------
# User decision 2026-10-17 (composed-effects plan 5, rule decision 1; OQ-060,
# OQ-057 (1)): Shipping's and a Tech tile's acquire "Influence with any
# Faction" no longer offer a Faction at 6. An older engine let a record pick
# one (nothing gained); this engine drops that step in a turn, where the
# recorded turn end lapses the icon, and confirms it in Combat's acquire
# frame, which has no turn end.

_TOP = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
_TECH_PICK = DomainAction(
    "resolve_tech_acquire_effect",
    0,
    (("effect", "influence"), ("faction", "emperor"), ("tech_id", "glowglobes")),
)


def test_influence_at_the_top_names_a_pick_of_a_faction_at_six() -> None:
    state = _bought_glowglobes(replace(_TOP, fremen=2))
    shipping = DomainAction(
        "choose_shipping_influence", 0, (("faction", "emperor"),)
    )
    assert migration._influence_at_the_top(state, shipping)
    assert migration._influence_at_the_top(state, _TECH_PICK)
    # A Faction below 6 was a real gain; so is another seat's pick (seat 1
    # holds no cube at 6), another effect, and an action without a Faction.
    below = DomainAction("choose_shipping_influence", 0, (("faction", "fremen"),))
    assert not migration._influence_at_the_top(state, below)
    assert not migration._influence_at_the_top(
        state, replace(_TECH_PICK, actor=1)
    )
    solari = DomainAction(
        "resolve_tech_acquire_effect",
        0,
        (("effect", "solari"), ("tech_id", "plasteel_blades")),
    )
    assert not migration._influence_at_the_top(state, solari)
    assert not migration._influence_at_the_top(state, _PRESS)


def test_a_combat_tech_influence_picked_at_the_top_is_confirmed_instead() -> None:
    combat = _combat_acquire_frame(_TOP)
    decision = combat.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    confirm = DomainAction("resolve_tech_influence_without_faction", 0)

    assert migration._tech_influence_confirm(ENGINE, combat, decision, _TECH_PICK) == (
        confirm
    )
    # A Faction that can still rise was a real pick, and this engine offers
    # no confirm for it.
    open_combat = _combat_acquire_frame(replace(_TOP, emperor=3, fremen=5))
    open_decision = open_combat.decision_stack[-1].decision
    assert isinstance(open_decision, PlayerDecision)
    assert (
        migration._tech_influence_confirm(
            ENGINE, open_combat, open_decision, _TECH_PICK
        )
        is None
    )
    # In a turn the bridge stays out: the step is dropped instead.
    turn = _bought_glowglobes(_TOP)
    turn_decision = turn.decision_stack[-1].decision
    assert isinstance(turn_decision, PlayerDecision)
    assert (
        migration._tech_influence_confirm(ENGINE, turn, turn_decision, _TECH_PICK)
        is None
    )

    # Walked as a codec v148 record: the pick comes back as the confirm,
    # which this engine shows as its ``confirm_empty`` row (stage B3d-3), the
    # step that ends the whole action (``MigratedStep.whole``).
    record = migrate_record(
        _v142_record(combat, _TECH_PICK, codec=148), _StartingAt(combat)
    )
    assert record.divergence is None
    assert [(m.whole, m.bridge) for m in record.steps] == [
        (confirm, "effect_last_step")
    ]
    assert [m.step for m in record.steps] == [
        DomainAction(
            "confirm_empty",
            0,
            (("of", "gain_influence"), ("printed", "glowglobes"), ("source", "tech")),
        )
    ]


def test_a_turn_tech_influence_picked_at_the_top_is_dropped_before_the_press() -> None:
    turn = _bought_glowglobes(_TOP)

    record = migrate_record(
        _v142_record(turn, _TECH_PICK, _PRESS, codec=148), _StartingAt(turn)
    )

    assert record.divergence is None
    assert record.dropped == ((0, migration.INFLUENCE_AT_TOP_DROPPED),)
    assert [m.step for m in record.steps] == [_PRESS]
    # A record of codec v149 met the decision itself: nothing is dropped.
    current = migrate_record(
        _v142_record(turn, _TECH_PICK, codec=149), _StartingAt(turn)
    )
    assert current.dropped == ()
    assert current.divergence is not None


def test_a_turn_tech_influence_picked_at_the_top_beside_a_free_faction_diverges() -> (
    None
):
    # Known divergence (cleanup-2b, rule decision 1; OQ-060): an older engine
    # offered a Faction at 6 beside one that could still rise and the record
    # picked it, gaining nothing. This engine offers only the Faction below 6
    # and the icon holds the turn end until taken, so the recorded press has
    # no counterpart: the pick is dropped and the record stops at the press.
    turn = _bought_glowglobes(Influence(emperor=6, spacing_guild=6, bene_gesserit=6))

    record = migrate_record(
        _v142_record(turn, _TECH_PICK, _PRESS, codec=148), _StartingAt(turn)
    )

    assert record.dropped == ((0, migration.INFLUENCE_AT_TOP_DROPPED),)
    assert record.divergence is not None
    assert record.divergence.recorded_index == 1


def test_a_window_step_answered_above_another_frame_waits_for_the_turn() -> None:
    # Cleanup-2b (rule decision 2, OQ-095 (2)): Liet Kynes' replacement from
    # Unexpected Allies' sandworm waits on the turn as rows, offered once the
    # card's Shield Wall choice is answered; an older engine opened the
    # replacement's window above that choice and the record drew and trashed
    # there. Those steps are held and applied as soon as this engine offers
    # them, before the next recorded step (``TURN_ROW_HELD``).
    card = "intrigue:unexpected_allies:0"
    turn = _liet_turn_state(
        PlayerState(
            player_id=0,
            leader_id="liet_kynes",
            hand=(LIET_RECON,),
            intrigue_cards=(card,),
            resources=Resources(water=2),
        )
    )
    # A play is its window, card and option steps (stage B3c-1).
    play = next(
        a
        for a in ENGINE.whole_actions(turn, 0)
        if a.action_id == "play_intrigue" and dict(a.arguments)["card_id"] == card
    )
    opened = apply_whole(ENGINE, turn, play).state
    legal = ENGINE.legal_actions(opened, 0)
    # The sandworm first, the Shield Wall choice still open. The card's
    # automatic rewards are its effect row (stage B3d-2a); the record holds
    # the whole action that row stands for.
    rewards = next(
        a
        for a in ENGINE.whole_actions(opened, 0)
        if a.action_id == "resolve_intrigue_rewards"
    )
    rewards_path = path_of(opened, rewards)
    assert rewards_path is not None and len(rewards_path) == 1
    assert rewards_path[0] in legal
    # Stage B3d-3: the Shield Wall refusal is shown as the ``decline`` row of
    # the destroy it refuses; the record holds the whole action.
    keep = next(
        a
        for a in ENGINE.whole_actions(opened, 0)
        if a.action_id == "keep_shield_wall"
    )
    (keep_row,) = steps_for(keep, "unexpected_allies")
    assert keep_row.action_id == "decline"
    assert dict(keep_row.arguments) == {
        "of": "destroy_shield_wall",
        "printed": "unexpected_allies",
        "source": "intrigue",
    }
    assert keep_row in legal
    draw = DomainAction(action_id="draw_planetologist_intrigue", actor=0)
    draw_row = DomainAction(
        "draw",
        0,
        (("icon", "intrigue"), ("printed", "liet_kynes"), ("source", "leader")),
    )
    trash = DomainAction(
        action_id="trash_optional_card", actor=0, arguments=(("card_id", LIET_RECON),)
    )
    trash_row = DomainAction(
        "trash", 0, (("printed", "liet_kynes"), ("source", "leader"))
    )
    pick_card = DomainAction("choose_personal_card", 0, (("card_id", LIET_RECON),))

    record = migrate_record(
        _v142_record(turn, play, rewards, draw, trash, keep, codec=148),
        _StartingAt(turn),
    )

    assert record.divergence is None, record.divergence
    # The recorded play is taken as its window, card and option steps
    # (stage B3c-1): the last ends the recorded whole action.
    path = path_of(turn, play)
    assert path is not None and len(path) == 3
    assert [(m.step, m.recorded_index, m.bridge) for m in record.steps] == [
        (path[0], None, "effect_step"),
        (path[1], None, "effect_step"),
        (path[2], 0, migration.EFFECT_LAST_STEP),
        (rewards_path[0], 1, migration.EFFECT_LAST_STEP),
        (keep_row, 4, migration.EFFECT_LAST_STEP),
        (draw_row, 2, migration.TURN_ROW_HELD),
        (trash_row, None, "effect_step"),
        (pick_card, 3, migration.TURN_ROW_HELD),
    ]
    # The held draw is taken as its effect row (stage B3c-2a), and the held
    # trash as the leader's trash icon, then the card (stage B3c-2b): each
    # last step ends the recorded whole action, the trash with the icon the
    # recording engine used.
    assert record.steps[3].whole == rewards
    assert record.steps[4].whole == keep
    assert record.steps[5].whole == draw
    assert record.steps[7].whole == DomainAction(
        "trash_optional_card",
        0,
        (
            ("card_id", LIET_RECON),
            ("printed", "liet_kynes"),
            ("source", "leader"),
        ),
    )
    assert record.state.players[0].trashed == (LIET_RECON,)
    assert len(record.state.players[0].intrigue_cards) == 1


# --- a research space's icons, each its own step (cleanup-2b, codec v149) ----
# User decision 2026-10-17, composed-effects plan 5, rule decision 5; OQ-027
# [Main p. 9] ("한 공간에 인쇄된 아이콘은 각각 독립된 효과이며, 소유자는 각
# 아이콘을 별개 행동으로 원하는 순서에 해결한다"): a pair space's specimen,
# Tleilaxu advance and optional trash, and c7r3's card and Intrigue card, are
# separate steps in the owner's order. An older engine resolved them inside the
# step that moved the token or paid the cost, in ``RESEARCH_ICON_ORDER``.

_HELD = "intrigue:ambush:1"


def _icon_row(effect: str, space: str) -> DomainAction:
    """This engine's action for a research icon: it names the research space
    that printed it (codec v150, stage B3e-1); the recorded steps of an older
    engine's record name none."""

    return DomainAction(
        "resolve_research_icon",
        0,
        (("effect", effect), ("printed", space), ("source", "research")),
    )


def _draw(deck: str) -> DomainAction:
    """This engine's action for c7r3's owed draw of ``deck``: it names the
    research space that earned it (codec v150, stage B3e-1)."""

    return DomainAction(
        f"draw_owed_{deck}", 0, (("printed", "c7r3"), ("source", "research"))
    )


def _icon_order(state: GameState) -> ReplayStep | None:
    """What the ``research_icon_order`` bridge adds now, after a recorded step."""

    decision = ENGINE.current_decision(state)
    assert decision is not None
    return migration._research_icon_order(ENGINE, state, decision, _PRESS)


def _on_another_turn(space: str, **owner: object) -> GameState:
    """Seat 0 on ``space`` while seat 1 is the turn's owner: seat 0's research
    is no turn of its own, so a research space opens its window."""

    turn = DecisionFrame(
        kind="turn",
        frame_id="round:1:turn:1",
        decision=PlayerDecision(owner=1, prompt="Choose a turn"),
    )
    return replace(_at(space, **owner), decision_stack=(turn,))


def _agent_fork(space: str, target: str, **owner: object) -> GameState:
    """Seat 0's Agent turn, its token on ``space`` moved on to ``target``."""

    fork = _agent_research(space, **owner)
    return apply_whole(
        ENGINE,
        fork,
        DomainAction("choose_research_space", 0, (("space_id", target),)),
    ).state


def _answers(state: GameState, *, steps: int) -> list[ReplayStep | None]:
    """The bridge's answers one after another, each applied to the state."""

    answers: list[ReplayStep | None] = []
    for _ in range(steps):
        answer = _icon_order(state)
        answers.append(answer)
        if answer is None:
            break
        # The bridge speaks whole actions; a turn frame offers the icon
        # effect first (stage B3c-2a).
        state = apply_whole(ENGINE, state, answer).state
    return answers


def test_a_pairs_icons_follow_in_the_order_an_older_engine_resolved_them() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9].
    # c3r5 in the Agent turn: the specimen, then the Tleilaxu advance.
    tleilaxu = _agent_fork("c2r4", "c3r5")
    assert _answers(tleilaxu, steps=3) == [
        _icon_row("specimen", "c3r5"),
        _icon_row("tleilaxu", "c3r5"),
        None,
    ]
    # c3r3: only the specimen; its optional trash stays the owner's own step,
    # answered by the record.
    trash = _agent_fork("c2r4", "c3r3")
    assert _answers(trash, steps=2) == [_icon_row("specimen", "c3r3"), None]


def test_a_window_s_icons_follow_in_the_same_order() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9].
    # Outside the owner's turn the window offers the rows; the trash icon too,
    # which opens the optional-trash window the record answers.
    for target, expected in (
        ("c3r5", ["specimen", "tleilaxu"]),
        ("c3r3", ["specimen", "trash"]),
    ):
        fork = _on_another_turn("c2r4")
        advanced = advance_research(fork, 0, source="test").state
        window = apply_whole(
            ENGINE,
            advanced,
            DomainAction("choose_research_space", 0, (("space_id", target),)),
        ).state
        assert window.decision_stack[-1].kind == FrameKind.RESEARCH_BONUS
        assert _answers(window, steps=2) == [
            _icon_row(effect, target) for effect in expected
        ]


def test_c7r3_s_rewards_follow_as_its_owed_draws_or_its_window_rows() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9].
    pay = DomainAction("trash_intrigue_for_research_bonus", 0, (("card_id", _HELD),))
    # In the Agent turn: the Intrigue card, then the card, then nothing.
    turn = apply_whole(
        ENGINE, _agent_fork("c6r2", "c7r3", intrigue_cards=(_HELD,)), pay
    ).state
    assert _answers(turn, steps=3) == [_draw("intrigue"), _draw("card"), None]
    # Outside the turn: the window's two rows in the same order.
    fork = _on_another_turn("c6r2", intrigue_cards=(_HELD,))
    advanced = advance_research(fork, 0, source="test").state
    arrow = apply_whole(
        ENGINE,
        advanced,
        DomainAction("choose_research_space", 0, (("space_id", "c7r3"),)),
    ).state
    window = apply_whole(ENGINE, arrow, pay).state
    assert _answers(window, steps=3) == [
        _icon_row("intrigue", "c7r3"),
        _icon_row("cards", "c7r3"),
        None,
    ]


def test_the_research_icon_bridge_adds_nothing_where_nothing_waits() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9].
    # No icon row and no c7r3 draw: a turn with nothing owed, the fork's own
    # direction frame, and a draw owed by something else.
    assert _icon_order(_at("c0r3")) is None
    fork = _agent_research("c2r4")
    assert _icon_order(fork) is None
    owner = fork.players[0]
    other = replace(owner, owed_draws=(("card", "tleilaxu_track", "test:other"),))
    assert _icon_order(replace(fork, players=(other, *fork.players[1:]))) is None
    # A c7r3 draw that is not offered on this frame is not forced either.
    stuck = replace(
        owner, owed_draws=(("card", OWED_ORIGIN_RESEARCH, "test:card"),)
    )
    stuck_state = replace(fork, players=(stuck, *fork.players[1:]))
    assert _draw("card") not in ENGINE.whole_actions(stuck_state, 0)
    assert _icon_order(stuck_state) is None
    # A pending chance is not a seat's decision.
    chance = ChanceDecision("test:chance", "Shuffle", ("a", "b"))
    assert migration._research_icon_order(ENGINE, fork, chance, _PRESS) is None


def test_a_record_before_v149_gets_the_icons_right_after_the_moving_step() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9].
    # An older engine's record: the move to c3r5 alone, then the turn's end.
    # The bridge adds the specimen and the Tleilaxu advance right after the
    # move; a record of codec v149 has its own rows, and meets the held end.
    fork = _agent_research("c2r4")
    move = DomainAction("choose_research_space", 0, (("space_id", "c3r5"),))

    record = migrate_record(
        _v142_record(fork, move, _PRESS, codec=148), _StartingAt(fork)
    )

    assert record.divergence is None
    # The recorded move is a whole action of the research window, taken as
    # its one target row (stage B3d-2a); the bridge's whole actions are taken
    # as their effect rows (stage B3c-2a): each icon is printed on c3r5.
    move_path = path_of(fork, move)
    assert move_path is not None and len(move_path) == 1
    ref = (("printed", "c3r5"), ("source", "research"))
    assert [(m.step, m.bridge) for m in record.steps] == [
        (move_path[0], migration.EFFECT_LAST_STEP),
        (
            DomainAction("generate_specimens", 0, (("icon", "specimen"), *ref)),
            "research_icon_order",
        ),
        (
            DomainAction("advance", 0, (("icon", "tleilaxu"), *ref)),
            "research_icon_order",
        ),
        (_PRESS, None),
    ]
    owner = record.state.players[0]
    assert (owner.specimens, owner.tleilaxu_space) == (1, 1)

    current = migrate_record(
        _v142_record(fork, move, _PRESS, codec=149), _StartingAt(fork)
    )
    assert current.divergence is not None
    assert current.divergence.recorded_index == 1
    assert "research_icon_order" not in current.bridge_counts()


# --- Harvest Cells resolves as it is played (codec v149, 2026-10-18) ---------
# User decision 2026-10-18: the Conflict's troops go back before the
# Conflict-end windows, and Harvest Cells gives its two specimens as it is
# played and asks only "You may also acquire a Tleilaxu card" [Harvest Cells
# card; Immortality p. 8; FAQ p. 1]. An older engine fired a played copy at its
# cleanup, after every window: its recorded acquisition answer comes after the
# other seats' windows, behind a "resolve the rewards" step this engine has no
# counterpart for, and its window's press after a play was the decline again.

_HARVEST_CELLS_RECORD = "v141-no-tech_module-app_ai-9711"


def _harvest_cells_play_in(replay: GameReplay) -> int:
    """The index of the record's one Harvest Cells play in a Conflict-end
    window."""

    plays = [
        index
        for index, step in enumerate(replay.steps)
        if isinstance(step, DomainAction)
        and step.action_id == "play_conflict_end_intrigue"
    ]
    assert len(plays) == 1
    assert str(dict(_step_of(replay, plays[0]).arguments)["card_id"]).startswith(
        "intrigue:harvest_cells:"
    )
    return plays[0]


def _step_of(replay: GameReplay, index: int) -> DomainAction:
    step = replay.steps[index]
    assert isinstance(step, DomainAction)
    return step


def test_a_harvest_cells_acquisition_recorded_at_the_cleanup_follows_its_play() -> (
    None
):
    # v141-no-tech_module-app_ai-9711: seat 1 plays Harvest Cells at 148, seat
    # 2 declines its window at 149, and the recording engine's cleanup asks
    # seat 1 "resolve the rewards" (150) and then the acquisition (151).
    # This engine asks the acquisition right after the play (the specimens
    # already taken), so the owner's later answer is applied there and
    # skipped where it was recorded.
    replay = _fixture(_HARVEST_CELLS_RECORD)
    play = _harvest_cells_play_in(replay)
    answer = _step_of(replay, play + 3)
    assert (play, answer.action_id, answer.actor) == (
        148,
        "acquire_intrigue_tleilaxu",
        _actor(replay, play),
    )
    assert _step_of(replay, play + 1).action_id == "decline_conflict_end_intrigue"
    assert _actor(replay, play + 1) != answer.actor
    assert _step_of(replay, play + 2).action_id == "resolve_intrigue_rewards"

    record = migrate_record(replay)

    assert record.complete, record.divergence
    position = next(
        position
        for position, migrated in enumerate(record.steps)
        if migrated.recorded_index == play
    )
    asked, window = record.steps[position + 1], record.steps[position + 2]
    assert asked.bridge == migration.HARVEST_CELLS_AT_ONCE
    # The window (opened for one effect, stage B3d-2a) takes the recorded
    # answer as its one target row.
    assert asked.whole == answer
    assert (asked.step,) == steps_for(answer, effect_row=False)
    assert asked.recorded_index == play + 3 > play
    # The other seat's recorded window comes after the pulled-forward answer;
    # its recorded decline is taken as this engine's ``decline`` row (stage
    # B3d-3), the step that ends the recorded whole action.
    assert (window.recorded_index, window.bridge, window.whole) == (
        play + 1,
        migration.EFFECT_LAST_STEP,
        _step_of(replay, play + 1),
    )
    assert isinstance(window.step, DomainAction)
    assert window.step.action_id == "decline"
    assert record.bridge_counts()[migration.HARVEST_CELLS_AT_ONCE] == 1
    # The record's answer applies once: its own place holds no second step.
    assert [migrated.recorded_index for migrated in record.steps].count(play + 3) == 1
    # This engine asked it: the Harvest Cells acquisition sat on the window,
    # with the play's two specimens already taken.
    before, _migrated = next(islice(walk(record), position + 1, None))
    top = before.decision_stack[-1]
    assert top.kind == FrameKind.INTRIGUE_CHOICE
    assert ":conflict_end:" in str(dict(top.context)["source"])
    assert isinstance(top.decision, PlayerDecision)
    assert top.decision.owner == answer.actor
    assert any(
        event.kind == "specimens_generated" for event in before.event_log[-3:]
    )


def test_the_rewards_step_asked_at_a_harvest_cells_cleanup_is_dropped() -> None:
    replay = _fixture(_HARVEST_CELLS_RECORD)
    play = _harvest_cells_play_in(replay)
    rewards = play + 2
    step = _step_of(replay, rewards)
    assert step.action_id == "resolve_intrigue_rewards"
    assert step.actor == _actor(replay, play)

    record = migrate_record(replay)

    assert record.complete, record.divergence
    assert [
        (index, reason)
        for index, reason in record.dropped
        if reason == migration.HARVEST_CELLS_REWARDS_DROPPED
    ] == [(rewards, migration.HARVEST_CELLS_REWARDS_DROPPED)]
    assert rewards not in {migrated.recorded_index for migrated in record.steps}


def test_a_decline_recorded_after_a_play_is_rewritten_to_the_finish() -> None:
    # An older engine offered the window's decline again after a card was
    # played in it (the window stays open while the seat holds Intrigue,
    # OQ-103); this engine's press there reads "finish". Seed 28: seat 2
    # plays a Harvest Cells (1039), declines its Tleilaxu card (1040), and
    # ends the window with ``finish_conflict_end_intrigue`` (1041). (Seed 4
    # until codec v152 asked a seat that cannot join a Scouts mission, OQ-131,
    # which moved its game; 28 is the first of 1-120 that meets this test
    # and the next.) No fixture of ``data/`` has a window that stayed open
    # after a play, so the record is this engine's own game, with that press
    # recorded as the decline.
    game = _this_engine_game(28)
    finishes = [
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, DomainAction)
        and step.action_id == "finish_conflict_end_intrigue"
    ]
    assert len(finishes) == 1  # the one press this test turns into a decline
    finish = finishes[0]
    seat = _actor(game, finish)
    # The play's last step (its card, stage B3c-1) ends the whole action.
    assert _whole(game, finish - 2).action_id == "play_conflict_end_intrigue"
    assert _actor(game, finish - 2) == seat
    declined = DomainAction("decline_conflict_end_intrigue", seat)
    older, position = _older_with(game, 148, finish, declined)

    record = migrate_record(older)

    assert record.complete, record.divergence
    assert record.bridge_counts()["conflict_end_finish"] == 1
    assert [migrated.step for migrated in record.steps] == _steps(game.steps)
    rewritten = record.steps[finish]
    assert rewritten.recorded_index == position
    assert rewritten.bridge == "conflict_end_finish"
    assert rewritten.step == _step_of(game, finish)
    assert canonical_state_hash(record.state) == game.expected_state_hash

    # Stamped with this codec the decline is not legal there, and no bridge
    # of the older engines answers it.
    steps = list(game.steps)
    steps[finish] = declined
    current = migrate_record(replace(game, steps=tuple(steps)))
    assert current.divergence is not None
    assert current.divergence.recorded_index == finish
    assert "conflict_end_finish" not in current.bridge_counts()


def test_a_decline_is_rewritten_only_where_the_window_stays_open_after_a_play() -> (
    None
):
    game = _this_engine_game(28)
    states = _states(game)
    declines = finishes = 0
    for index, step in enumerate(game.steps):
        if not isinstance(step, DomainAction):
            continue
        # A decline is recorded as its ``decline`` row (stage B3d-3): read the
        # whole action the step ends.
        whole = _whole(game, index)
        if whole.action_id not in (
            "decline_conflict_end_intrigue",
            "finish_conflict_end_intrigue",
        ):
            continue
        state = states[index]
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, PlayerDecision)
        press = migration._conflict_end_finish(
            ENGINE,
            state,
            decision,
            DomainAction("decline_conflict_end_intrigue", step.actor),
        )
        if whole.action_id == "finish_conflict_end_intrigue":
            # After a play: the recorded decline reads as the finish.
            assert press == step
            finishes += 1
        else:
            # Before any play the decline is legal as it is recorded.
            assert press is None
            declines += 1
    assert declines and finishes


def test_another_cards_rewards_step_is_not_taken_for_a_harvest_cells() -> None:
    # A record's Harvest Cells owes its "resolve the rewards" step until the
    # next recorded Round Start pause; a record of an engine before v140 has no
    # pauses, so the count stays. Another Intrigue card's own rewards step by
    # that seat -- its choice frame on top -- must still apply. Seed 131:
    # seat 2 plays Harvest Cells in round 1 (117) and Insider Information in
    # round 9 (rewards at 1185); the pauses of the game are left out of its
    # record as an older engine left them out. (Seed 175 until codec v152
    # asked a seat that cannot join a Scouts mission, OQ-131, which moved
    # its game; 131 is the first of 1-500 that meets this test again, the
    # notes below are 175's history.) Seed 65 until
    # cleanup-2d split three Agent boxes per icon (2026-10-18) moved its game
    # (its step 575 is now seat 1's Agent turn); 175 is the first seed of
    # 1-500 meeting every precondition below, the v148 record of its game
    # migrating completely. (Codec v150, stage B1, makes every Agent turn two
    # steps, so this game's step numbers are later than they were -- 87, 821
    # and round starts 90 ... 794 -- and its moves are the same; stage B2's
    # reward icon rows moved them again, from 95, 891 and 98 ... 862,
    # stage B3's effect rows again, from 102, 947 and 105 ... 918, stage
    # B3b-2's Reveal effect rows again, from 104, 980 and 107 ... 949, and
    # stage B3c-1's played cards again, from 111, 1045 and 114 ... 1014,
    # stage B3c-2b's optional trash icon rows again, from 1106 and 953,
    # 1073, stage B3d-1's reward-window effect rows again, from 1107 and 806,
    # 954, 1074, and stage B3d-2a's one-effect windows' target rows again,
    # from 1108 and 375, 495, 649, 807, 955, 1075 (the rewards step is now
    # the card's effect row, ``resolve``);
    # ``play`` is the step that ends the Harvest Cells play, its card.)
    game = _this_engine_game(131)
    play, rewards = 117, 1185
    assert _whole(game, play).action_id == "play_conflict_end_intrigue"
    assert _whole(game, rewards).action_id == "resolve_intrigue_rewards"
    assert _actor(game, rewards) == _actor(game, play)
    top = _states(game)[rewards].decision_stack[-1]
    assert top.kind == FrameKind.INTRIGUE_CHOICE
    assert dict(top.context)["card_id"] == "intrigue:insider_information:0"
    starts = {
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, ChanceOutcome) and ":round_start:" in step.decision_id
    }
    # round starts between the two
    assert {119, 226, 346, 478, 627, 749, 898, 1064} <= starts
    older = _older(game, 148, starts)

    record = migrate_record(older)

    assert record.complete, record.divergence
    assert migration.HARVEST_CELLS_REWARDS_DROPPED not in {
        reason for _, reason in record.dropped
    }
    # The migrated steps are the game's own, the bridged pauses back in
    # their places; the rewards step is the record's, taken as the card's
    # effect row like any other whole action of its window, and kept.
    assert [migrated.step for migrated in record.steps] == _steps(game.steps)
    assert record.steps[rewards].step == _step_of(game, rewards)
    assert record.steps[rewards].whole == _whole(game, rewards)
    assert record.steps[rewards].bridge == migration.EFFECT_LAST_STEP


def test_another_cards_rewards_step_is_dropped_without_its_choice_on_top(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The same record as above, with the check for the seat's Intrigue choice
    # on top removed: the due count would drop Insider Information's rewards
    # step as if it were a Harvest Cells', and the record would stop there.
    # That is what the check keeps from happening.
    game = _this_engine_game(131)
    rewards = 1185
    starts = {
        index
        for index, step in enumerate(game.steps)
        if isinstance(step, ChanceOutcome) and ":round_start:" in step.decision_id
    }
    older = _older(game, 148, starts)
    # The record's index of that step: the pauses and the Scouts confirms the
    # record left out are before it.
    before = sum(1 for start in starts if start < rewards)
    index = _position(game, 148, rewards) - before
    assert older.steps[index] == _whole(game, rewards)
    monkeypatch.setattr(
        migration, "_intrigue_choice_on_top", lambda state, player: False
    )

    record = migrate_record(older)

    assert (index, migration.HARVEST_CELLS_REWARDS_DROPPED) in record.dropped
    assert record.divergence is not None


# --- The Conflict card first, and a window that stays open (codec v149) --------
# User decision 2026-10-18 ("그래 둘다 B가 맞겠다"): the winner takes the Conflict
# card, and Planetary Array's card is drawn, as the Conflict-end step opens
# (OQ-108); a window a card was played in stays open while its seat holds an
# Intrigue card, judged as it comes back on top (OQ-109). An older engine drew
# that card at its cleanup or after the next round's hand, so its reshuffle of
# the seat's discard comes under another decision, and it had closed a window
# this engine keeps open. The three bridges below answer those.


def _planetary_array_reshuffle() -> tuple[GameState, ChanceDecision, tuple[str, ...]]:
    """The state at Planetary Array's tech-draw reshuffle, the decision this
    engine asks as the Conflict card is awarded, and the recorded order."""

    discard = starting_deck_instance_ids(0)[5:8]
    _engine, offered = _planetary_array_conflict_end((), discard)
    decision = ENGINE.current_decision(offered.state)
    assert isinstance(decision, ChanceDecision)
    assert decision.decision_id == "round:1:player:0:tech_draw:discard_shuffle"
    return offered.state, decision, tuple(reversed(discard))


def _asking(state: GameState, decision_id: str) -> tuple[GameState, ChanceDecision]:
    """The same state, the chance on top asking under another decision id."""

    top = state.decision_stack[-1]
    assert isinstance(top.decision, ChanceDecision)
    renamed = replace(top, decision=replace(top.decision, decision_id=decision_id))
    asked = replace(state, decision_stack=(*state.decision_stack[:-1], renamed))
    decision = ENGINE.current_decision(asked)
    assert isinstance(decision, ChanceDecision)
    return asked, decision


def test_a_window_this_engine_keeps_open_is_finished_where_the_record_went_on() -> (
    None
):
    # Seat 0 plays a Harvest Cells holding another Intrigue card and answers
    # its acquisition: the window comes back on top and stays open (OQ-109).
    window = _window_offer(
        ENGINE,
        _window_combat(_window_fighter(3, intrigue_cards=(HARVEST_CELLS[0], PLAIN))),
    ).state
    played = apply_whole(
        ENGINE,
        window,
        DomainAction("play_conflict_end_intrigue", 0, (("card_id", HARVEST_CELLS[0]),)),
    ).state
    after_play = ENGINE.current_decision(played)
    assert after_play is not None
    opened = ENGINE.current_decision(window)
    assert opened is not None
    kept = apply_whole(
        ENGINE, played, DomainAction("decline_intrigue_tleilaxu", 0)
    ).state
    decision = ENGINE.current_decision(kept)
    finish = DomainAction("finish_conflict_end_intrigue", 0)
    assert isinstance(decision, PlayerDecision) and decision.owner == 0
    assert kept.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert finish in ENGINE.legal_actions(kept, 0)

    def reopened(step: ReplayStep) -> ReplayStep | None:
        return migration._conflict_end_reopened(ENGINE, kept, decision, step)

    # The recording engine had closed the window, so its next step belongs to
    # another seat, or to a chance: this engine answers the finish first.
    other_window = DomainAction("decline_conflict_end_intrigue", 1)
    play_there = DomainAction(
        "play_conflict_end_intrigue", 1, (("card_id", HARVEST_CELLS[1]),)
    )
    pause = ChanceOutcome("round:1:conflict_end:pause", (CONTINUE,))
    for later in (other_window, play_there, pause):
        assert reopened(later) == finish
    # The seat's own window step answers the window itself.
    for own in (
        finish,
        DomainAction("decline_conflict_end_intrigue", 0),
        DomainAction("play_conflict_end_intrigue", 0, (("card_id", PLAIN),)),
    ):
        assert reopened(own) is None

    # Only a window a card was played in: the unplayed one, or the acquisition
    # choice on top of the played one, is no reopened window.
    assert (
        migration._conflict_end_reopened(ENGINE, window, opened, other_window) is None
    )
    assert (
        migration._conflict_end_reopened(ENGINE, played, after_play, other_window)
        is None
    )
    # Nor a chance on top.
    chance_state, chance, _ = _planetary_array_reshuffle()
    assert migration._conflict_end_reopened(ENGINE, chance_state, chance, pause) is None
    # It is a bridge of the older records only, run before the recorded step.
    bridge = next(b for b in migration.BRIDGES if b.name == "conflict_end_reopened")
    assert (bridge.before_codec, bridge.rewrites, bridge.follows) == (149, False, False)

    # Through the dispatch an older record sees: another seat's recorded
    # decline is that seat's, so ``conflict_end_finish`` (a rewrite, earlier
    # in BRIDGES) leaves it and the reopened window is finished before it
    # (it used to take that decline as seat 0's finish, 2026-10-18 review).
    older = tuple(
        b for b in migration.BRIDGES if b.before_codec is None or 148 < b.before_codec
    )
    bridged = migration._bridge(ENGINE, kept, other_window, older)
    assert bridged is not None
    assert (bridged[0].name, bridged[1]) == ("conflict_end_reopened", finish)
    # The seat's own recorded decline is still rewritten to its finish.
    own_bridged = migration._bridge(
        ENGINE, kept, DomainAction("decline_conflict_end_intrigue", 0), older
    )
    assert own_bridged is not None
    assert (own_bridged[0].name, own_bridged[1]) == ("conflict_end_finish", finish)


def test_a_frame_over_contract_rows_takes_its_recorded_pick_first() -> None:
    # Codec v150 (stage B3b, OQ-112 (4)): a Contract completed in its owner's
    # turn waits on it as rows, offered once the turn frame is on top again.
    # A recording engine paid the reward at the completion, so where another
    # frame of the owner's (a market taking a second tile) stood over the
    # completion, the record went on with the reward's own chance steps
    # before that frame's next pick; that pick is taken first.
    state = replace(
        _place_contract_agent(
            _agent_contract_state(
                "reserve:prepare_the_way:7", "contract:arrakeen_i"
            ),
            "arrakeen",
        ),
        face_up_contract_ids=("contract:high_council_i", "contract:heighliner_i"),
        contract_bank=("contract:deliver_supplies",),
    )
    item = (turn_rows.CONTRACT_ICON, "round:1:test", "contract:arrakeen_i|resources")
    waiting = turn_rows.queue(state, 0, item)
    assert waiting is not None
    market = begin_contract_gain(waiting, 0, 1, source="round:1:test:market").state
    take = legal_contract_actions(market, 0)[0]
    shuffle = ChanceOutcome("round:1:player:0:test:discard_shuffle", ("a", "b"))

    def earlier(at: GameState, steps: tuple[ReplayStep, ...]) -> object:
        return migration._asked_earlier(
            ENGINE,
            at,
            steps,
            0,
            set(),
            turn_rows_codec=False,
            contract_rows_codec=True,
        )

    assert earlier(market, (shuffle, take)) == (
        1,
        take,
        migration.CONTRACT_FRAME_FIRST,
    )
    # Not another seat's step, nor without rows waiting under the frame.
    other = DomainAction("finish_agent_turn", 1)
    assert earlier(market, (shuffle, other, take)) is None
    bare = begin_contract_gain(state, 0, 1, source="round:1:test:market").state
    assert earlier(bare, (shuffle, take)) is None
    # Nor once the rows' own turn frame is on top.
    assert earlier(waiting, (shuffle, take)) is None


def test_a_planetary_array_reshuffle_recorded_at_the_cleanup_is_taken_at_the_win() -> (
    None
):
    # The recording engine drew Planetary Array's card at a cleanup that also
    # fired a Harvest Cells, under the same decision this engine asks as the
    # Conflict card is awarded.
    state, decision, shuffled = _planetary_array_reshuffle()
    recorded = ChanceOutcome(decision.decision_id, shuffled)
    elsewhere = ChanceOutcome("round:2:player:0:discard_shuffle", shuffled)
    pause = ChanceOutcome("round:1:conflict_end:pause", (CONTINUE,))
    filler = DomainAction("finish_conflict_end_intrigue", 0)

    def earlier(
        steps: tuple[ReplayStep, ...], index: int = 0, consumed: set[int] | None = None
    ) -> tuple[int, ReplayStep] | None:
        return migration._tech_draw_earlier(
            ENGINE, state, steps, index, consumed or set()
        )

    assert earlier((filler, elsewhere, recorded)) == (2, recorded)
    # Looked for from the step the record stands at, and taken once.
    assert earlier((recorded, filler), index=1) is None
    assert earlier((filler, recorded), consumed={1}) is None
    # None is looked for past the recording's next pause.
    assert earlier((pause, recorded)) is None
    # Only the draw of the win: not another chance, another phase, or a state
    # whose windows were not offered yet.
    plain, _ = _asking(state, "round:2:player:0:discard_shuffle")
    assert (
        migration._tech_draw_earlier(ENGINE, plain, (recorded,), 0, set()) is None
    )
    for changed in (
        replace(state, phase=GamePhase.MAKERS),
        replace(state, combat_end_triggers_offered=False),
    ):
        assert (
            migration._tech_draw_earlier(ENGINE, changed, (recorded,), 0, set())
            is None
        )
    # The bridge names tell the two apart: the same decision, or the same
    # cards under another one.
    assert migration._asked_earlier_bridge(recorded, recorded) == (
        migration.TECH_DRAW_AT_THE_WIN
    )
    moved = ChanceOutcome(decision.decision_id, shuffled)
    assert migration._asked_earlier_bridge(moved, elsewhere) == (
        migration.RESHUFFLE_MOVED
    )
    harvest = DomainAction("acquire_intrigue_tleilaxu", 0)
    assert migration._asked_earlier_bridge(harvest, harvest) == (
        migration.HARVEST_CELLS_AT_ONCE
    )
    # The dispatch tries the same decision first, then the moved reshuffle,
    # and names the bridge.
    def asked_earlier(steps: tuple[ReplayStep, ...]) -> object:
        return migration._asked_earlier(
            ENGINE,
            state,
            steps,
            0,
            set(),
            turn_rows_codec=True,
            contract_rows_codec=False,
        )

    assert asked_earlier((filler, recorded)) == (
        1,
        recorded,
        migration.TECH_DRAW_AT_THE_WIN,
    )
    assert asked_earlier((filler, elsewhere)) == (
        1,
        ChanceOutcome(decision.decision_id, shuffled),
        migration.RESHUFFLE_MOVED,
    )


def test_a_reshuffle_of_the_same_cards_is_taken_under_this_engines_decision() -> None:
    # This engine takes a seat's deck card a round earlier than the recording
    # engine did, so it shuffles the discard at the win (or at the next Round
    # Start) where the recording engine shuffled the same cards for that
    # card after the next round's hand, under another decision. The recorded
    # permutation is taken now.
    state, decision, shuffled = _planetary_array_reshuffle()
    cards = tuple(sorted(decision.options))
    filler = DomainAction("finish_conflict_end_intrigue", 0)
    later = ChanceOutcome("round:2:player:0:discard_shuffle", shuffled)
    taken = ChanceOutcome(decision.decision_id, shuffled)

    def moved(
        steps: tuple[ReplayStep, ...],
        *,
        asked: tuple[GameState, ChanceDecision] | None = None,
        consumed: set[int] | None = None,
    ) -> tuple[int, ReplayStep] | None:
        at = asked[0] if asked else state
        return migration._reshuffle_earlier(ENGINE, at, steps, 0, consumed or set())

    assert moved((filler, later)) == (1, taken)
    # The order is the record's, whatever order the engine lists the cards in.
    assert sorted(shuffled) == list(cards)
    assert moved((later,), consumed={0}) is None

    # Another seat's reshuffle is not this seat's.
    assert moved((ChanceOutcome("round:2:player:1:discard_shuffle", shuffled),)) is None
    # Other cards: one the engine's shuffle does not hold, or one fewer.
    swapped = (*shuffled[:-1], "player:0:starter:other:9")
    assert moved((ChanceOutcome("round:2:player:0:discard_shuffle", swapped),)) is None
    assert (
        moved((ChanceOutcome("round:2:player:0:discard_shuffle", shuffled[:-1]),))
        is None
    )
    # Not a personal reshuffle of the seat (an Intrigue deck's, a pause).
    assert moved((ChanceOutcome("round:2:intrigue:discard_shuffle", shuffled),)) is None
    assert moved((ChanceOutcome("round:2:player:0:pause", shuffled),)) is None

    # Only a seat holding Planetary Array: the card comes from the tile.
    seat = state.players[0]
    bare = replace(
        state,
        players=(replace(seat, tech_ids=()), *state.players[1:]),
    )
    assert migration._reshuffle_earlier(ENGINE, bare, (later,), 0, set()) is None

    # One of the two reshuffles must be that card's draw. Neither is when this
    # engine asks the round start's own shuffle and the record has another
    # round's; the other way round, this engine's draw takes a round start's.
    plain = _asking(state, "round:2:player:0:discard_shuffle")
    next_round = ChanceOutcome("round:3:player:0:discard_shuffle", shuffled)
    assert moved((next_round,), asked=plain) is None
    drawn = ChanceOutcome("round:2:player:0:tech_draw:discard_shuffle", shuffled)
    assert moved((drawn,), asked=plain) == (
        0,
        ChanceOutcome("round:2:player:0:discard_shuffle", shuffled),
    )

    # Looked for within the recording's next rounds only.
    reach = migration._RESHUFFLE_LOOKAHEAD
    assert moved((filler,) * (reach - 1) + (later,)) == (reach - 1, taken)
    assert moved((filler,) * reach + (later,)) is None

    # Not a chance at all: the window it stands before is no reshuffle.
    window = _window_offer(
        ENGINE, _window_combat(_window_fighter(3, intrigue_cards=(PLAIN,)))
    ).state
    assert migration._reshuffle_earlier(ENGINE, window, (later,), 0, set()) is None


_DISCARD = ":discard_shuffle"
_INTRIGUE = ":intrigue_shuffle"


@pytest.mark.parametrize(
    ("old", "new", "suffix", "renamed"),
    (
        # A caller's extra word dropped (cleanup-2c-5, 2c-6), with a seat in
        # the name or none (an Arrakeen Scouts reward's).
        ("round:2:player:1:x:draw", "round:2:player:1:x", _DISCARD, True),
        ("round:2:scouts:a:draw", "round:2:scouts:a", _DISCARD, True),
        (
            "round:2:player:1:intrigue:a:0:1:intrigue",
            "round:2:player:1:intrigue:a:0:1",
            _INTRIGUE,
            True,
        ),
        (
            "round:2:player:1:leader_signet:intrigue_draw",
            "round:2:player:1:leader_signet",
            _INTRIGUE,
            True,
        ),
        # A research pair's icon: the opener's name, now the track space's.
        (
            "round:2:player:1:board:research_station:research:c3r3:card",
            "round:2:player:1:research:c3r3",
            _DISCARD,
            True,
        ),
        (
            "round:2:player:1:board:research_station:research:c7r3:intrigue",
            "round:2:player:1:research:c7r3",
            _INTRIGUE,
            True,
        ),
        # A Tleilaxu space's draw: the mover's name, now the track space's.
        (
            "round:2:player:1:agent_card:imperium:x:0:tleilaxu:3",
            "round:2:player:1:tleilaxu:3",
            _INTRIGUE,
            True,
        ),
        # An Arrakeen Scouts reward's research (no seat in the name) moved
        # the seat's token (corpus record full.ha.75).
        (
            "round:5:scouts:competitive_study_late:reward:research:research:c7r3:card",
            "round:5:player:2:research:c7r3",
            _DISCARD,
            True,
        ),
        # Esmar Tuek's draw for a visit: the visitor's seat, now Esmar's.
        (
            "round:2:player:3:tuek_sietch_visit",
            "round:2:player:1:leader:esmar_tuek",
            _INTRIGUE,
            True,
        ),
        # Not renames: another seat, another space, another round's Esmar
        # draw, an unrelated name.
        (
            "round:2:player:0:board:research_station:research:c3r3:card",
            "round:2:player:1:research:c3r3",
            _DISCARD,
            False,
        ),
        (
            "round:2:player:1:board:research_station:research:c3r1:card",
            "round:2:player:1:research:c3r3",
            _DISCARD,
            False,
        ),
        (
            "round:1:player:3:tuek_sietch_visit",
            "round:2:player:1:leader:esmar_tuek",
            _INTRIGUE,
            False,
        ),
        ("round:2:player:1:board:arrakeen", "round:2:player:1:x", _DISCARD, False),
        # A seated name never becomes a seatless one.
        (
            "round:2:player:1:research:c3r3:card",
            "round:2:scouts:x:research:c3r3",
            _DISCARD,
            False,
        ),
    ),
)
def test_cleanup2c_renames_only_a_draw_it_explains(
    old: str, new: str, suffix: str, renamed: bool
) -> None:
    """Codec v149 renamed draws by the event grammar, and the reshuffle a
    short draw asks for with them (2026-10-18 review: the Intrigue
    reshuffle's renames had no bridge)."""

    assert migration._cleanup2c_renamed(old + suffix, new + suffix, suffix) is renamed


# --- Codec v149: the split boxes and the confirms (cleanup-2d-5, 2f) -----------
# An older engine resolved Clandestine Meeting, Occupation and In High Places
# with one ``resolve_agent_card_effect`` (In High Places' Spy in the shared
# placement frame), refused a Signet stage with nothing to do, and either
# skipped a Conflict trash with no card or offered only its refusal there.


def _decided(state: GameState) -> PlayerDecision | ChanceDecision:
    decision = ENGINE.current_decision(state)
    assert decision is not None
    return decision


def _box_args(action: ReplayStep) -> dict[str, object]:
    assert isinstance(action, DomainAction)
    return dict(action.arguments)


def test_a_recorded_box_resolution_plays_its_icons_one_by_one() -> None:
    from tests.unit.rules.test_immortality_imperium import (
        FACE_DANCER,
        _card,
        _graft,
        _owner,
        _place,
        _state,
    )

    occupation = _card("occupation")
    state = _place(
        _state(_owner((occupation,), troops_garrison=3)), occupation, "arrakeen"
    )
    plain = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    first = migration._split_box_icon(
        ENGINE, state, _decided(state), plain
    )
    assert first == DomainAction(action_id="take_agent_card_combat_icon", actor=0)
    after = apply_whole(ENGINE, state, first).state
    follow = migration._split_box_follow(
        ENGINE, after, _decided(after), first
    )
    assert follow == DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("effect", "cards"),)
    )
    done = apply_whole(ENGINE, after, follow).state
    assert (
        migration._split_box_follow(ENGINE, done, _decided(done), follow)
        is None
    )

    # Box 1 of a grafted turn: Clandestine Meeting's Influence, then its card.
    meeting = _card("clandestine_meeting")
    grafted = _graft(
        _state(_owner((FACE_DANCER, meeting))), FACE_DANCER, "dutiful_service", meeting
    )
    plain_box1 = DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("box", 1),)
    )
    first = migration._split_box_icon(
        ENGINE, grafted, _decided(grafted), plain_box1
    )
    assert isinstance(first, DomainAction)
    assert first.action_id == "choose_agent_card_influence"
    assert _box_args(first) == {"box": 1, "faction": "bene_gesserit"}
    after = apply_whole(ENGINE, grafted, first).state
    follow = migration._split_box_follow(
        ENGINE, after, _decided(after), first
    )
    assert follow is not None and _box_args(follow) == {"box": 1, "effect": "intrigue"}


def test_in_high_places_old_spy_frame_moves_are_its_spy_rows() -> None:
    from tests.unit.rules.test_agent_effects import _in_high_places_on_secrets

    placed, _ = _in_high_places_on_secrets()
    plain = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    draw = migration._split_box_icon(
        ENGINE, placed, _decided(placed), plain
    )
    assert draw == DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("effect", "cards"),)
    )
    drawn = apply_whole(ENGINE, placed, draw).state
    # The Spy waits for the record's frame step, not for a follow.
    assert (
        migration._split_box_follow(ENGINE, drawn, _decided(drawn), draw)
        is None
    )
    post = (("post_id", "bene-gesserit-espionage-secrets"),)
    spy = migration._split_box_spy(
        ENGINE,
        drawn,
        _decided(drawn),
        DomainAction(action_id="place_spy_on_space", actor=0, arguments=post),
    )
    assert spy == DomainAction(
        action_id="place_agent_card_spy", actor=0, arguments=post
    )


def test_the_cleanup_2f_refusals_are_the_confirms() -> None:
    from tests.unit.rules.test_bloodlines_leaders import SIGNET, _esmar_state, _play
    from tests.unit.rules.test_combat import _reward_state

    esmar = PlayerState(player_id=0, leader_id="esmar_tuek", hand=(SIGNET,))
    state = _play(
        _esmar_state(
            esmar,
            maker_bonus_spice=(
                ("deep_desert", 0),
                ("hagga_basin", 0),
                ("imperial_basin", 0),
            ),
        ),
        SIGNET,
        "arrakeen",
    )
    assert migration._signet_without_option(
        ENGINE,
        state,
        _decided(state),
        DomainAction(action_id="decline_leader_signet_payment", actor=0),
    ) == DomainAction(action_id="resolve_leader_signet_without_option", actor=0)

    from dune_imperium.rules.combat import resolve_combat_rewards

    # The reward's resources and Contract rows first, up to its trash.
    rewarded = settle_reward_window(
        resolve_combat_rewards(_reward_state("trade_dispute")).state
    )
    decision = _decided(rewarded)
    confirm = DomainAction(action_id="resolve_combat_trash_without_card", actor=0)
    # The recorded refusal of a trash with no card left is the confirm; a
    # record that never had the window gets it answered before its next step.
    assert (
        migration._combat_trash_declined_without_card(
            ENGINE,
            rewarded,
            decision,
            DomainAction(action_id="decline_combat_reward_trash", actor=0),
        )
        == confirm
    )
    window = next(
        bridge
        for bridge in migration.BRIDGES
        if bridge.name == "combat_trash_without_card"
    )
    assert (
        window.answer(
            ENGINE, rewarded, decision, DomainAction(action_id="reveal_turn", actor=1)
        )
        == confirm
    )


# --- The Agent turn as a card pick and a space pick (codec v150) ---------------
# Stage B1 (OQ-111): a placement is ``choose_agent_card`` and then
# ``place_agent``; a record of an older engine holds it as one ``agent_turn``
# (the card, its graft choice and the space's arguments), which the bridges
# ``agent_card_pick`` and ``agent_space_pick`` split.


def _as_one_agent_turn(game: GameReplay) -> tuple[GameReplay, int]:
    """``game`` as a v149 engine recorded it: each card pick and the space
    pick right after it merged into the one ``agent_turn``, no reward icon
    rows and each whole action in one step (``_dropped``, ``_effect_runs``).
    Returns the record and the number of placements."""

    steps: list[ReplayStep] = []
    merged = 0
    index = 0
    rows = _reward_icon_steps(game) | _effect_pick_steps(game)
    runs = _effect_runs(game)
    while index < len(game.steps):
        step = game.steps[index]
        if index in rows:
            index += 1
            continue
        if isinstance(step, DomainAction) and step.action_id == "choose_agent_card":
            space = game.steps[index + 1]
            assert isinstance(space, DomainAction) and space.action_id == "place_agent"
            steps.append(
                DomainAction(
                    action_id="agent_turn",
                    actor=step.actor,
                    arguments=tuple(sorted((*step.arguments, *space.arguments))),
                )
            )
            merged += 1
            index += 2
            continue
        steps.append(runs[index][0] if index in runs else step)
        index += 1
    return replace(game, steps=tuple(steps), action_codec_version=149), merged


def test_a_recorded_agent_turn_is_split_into_its_card_and_space_picks(
    game: GameReplay,
) -> None:
    older, placements = _as_one_agent_turn(game)
    assert placements >= 20
    assert not any(
        isinstance(step, DomainAction)
        and step.action_id in ("choose_agent_card", "place_agent")
        for step in older.steps
    )

    record = migrate_record(older)

    assert record.complete, record.divergence
    assert [migrated.step for migrated in record.steps] == _steps(game.steps)
    assert _reward_icon_counts(record, game) == {
        "agent_card_pick": placements,
        "agent_space_pick": placements,
    }
    assert canonical_state_hash(record.state) == game.expected_state_hash
    # The space pick is the record's own step, rewritten; the card pick is
    # added before it.
    rewritten = [m for m in record.steps if m.bridge == "agent_space_pick"]
    assert rewritten and all(
        isinstance(m.step, DomainAction) and m.step.action_id == "place_agent"
        for m in rewritten
    )


def test_a_record_stamped_with_this_codec_gets_no_agent_turn_bridges(
    game: GameReplay,
) -> None:
    older, _ = _as_one_agent_turn(game)
    # The record stops at the first step this engine does not offer as it is:
    # an ``agent_turn``, or a whole action a window shows by its steps (stage
    # B3d-2a: the leader draft's ``pick_leader`` comes first).
    collapsed = {whole for whole, _ in _effect_runs(game).values()}
    first = next(
        index
        for index, step in enumerate(older.steps)
        if isinstance(step, DomainAction)
        and (step.action_id == "agent_turn" or step in collapsed)
    )

    current = migrate_record(replace(older, action_codec_version=ACTION_CODEC_VERSION))

    # Neither is an action of this engine: no bridge of the older engines
    # answers or rewrites it, and the record stops there.
    assert current.divergence is not None
    assert current.divergence.recorded_index == first
    assert not current.bridge_counts()


# --- A waiting effect is picked before its target (codec v150) -----------------
# Stage B3 (OQ-111): in an Agent turn's effect frame the seat picks the waiting
# effect (an effect row naming its verb and the entity that printed it), then
# each of its targets (a target row); the last row applies the effect. A
# record of an older engine holds the whole action in one step, which the
# bridges ``effect_step`` (the effect and each target but the last, added
# before it) and ``effect_last_step`` (the whole action rewritten as its last
# row) expand. The runs below are this engine's own game (``_effect_runs``).


def _first_run(
    game: GameReplay, action_id: str, picks: int
) -> tuple[int, DomainAction, GameState]:
    """The first whole action of ``action_id`` with ``picks`` steps before its
    last, with the step that ends it and the state before its first step."""

    index, (whole, steps) = next(
        (index, run)
        for index, run in sorted(_effect_runs(game).items())
        if run[0].action_id == action_id and len(run[1]) == picks
    )
    return index, whole, _states(game)[steps[0] if steps else index]


def _expanded(
    game: GameReplay, action_id: str, picks: int, codec: int = 149
) -> tuple[migration.MigratedRecord, list[DomainAction], GameState]:
    """The record of one whole action ``_first_run`` finds, migrated from the
    state before it, the rows this engine took for it, and the state after
    them."""

    index, whole, start = _first_run(game, action_id, picks)
    rows = [_step_of(game, step) for step in range(index - picks, index + 1)]
    after = _states(game)[index + 1]
    record = migrate_record(
        _v142_record(start, whole, codec=codec), _StartingAt(start)
    )
    return record, rows, after


def test_a_whole_action_with_a_target_is_its_effect_row_then_its_target_row(
    game: GameReplay,
) -> None:
    record, rows, after = _expanded(game, "trash_agent_card", 1)

    assert record.complete, record.divergence
    assert [row.action_id for row in rows] == ["trash", "choose_personal_card"]
    assert [migrated.step for migrated in record.steps] == rows
    # The effect row is added before the recorded step, which is rewritten as
    # the target row.
    assert [
        (migrated.bridge, migrated.recorded_index) for migrated in record.steps
    ] == [("effect_step", None), ("effect_last_step", 0)]
    assert record.bridge_counts() == {"effect_step": 1, "effect_last_step": 1}
    assert canonical_state_hash(record.state) == canonical_state_hash(after)


def test_a_whole_action_with_two_targets_picks_each_before_the_last(
    game: GameReplay,
) -> None:
    # A Tech tile acquired at a board space names the tile, then the post it
    # asks for: two targets, so the effect row and the first target are added
    # and the second is the recorded step.
    record, rows, after = _expanded(game, "acquire_tech", 2)

    assert record.complete, record.divergence
    assert [row.action_id for row in rows] == [
        "acquire",
        "choose_tech",
        "choose_post",
    ]
    assert [migrated.step for migrated in record.steps] == rows
    assert [
        (migrated.bridge, migrated.recorded_index) for migrated in record.steps
    ] == [("effect_step", None), ("effect_step", None), ("effect_last_step", 0)]
    assert canonical_state_hash(record.state) == canonical_state_hash(after)


def test_a_whole_action_without_a_target_is_its_effect_row(game: GameReplay) -> None:
    record, rows, after = _expanded(game, "resolve_board_effect", 0)

    assert record.complete, record.divergence
    (row,) = rows
    assert row.action_id != "resolve_board_effect"
    assert [migrated.step for migrated in record.steps] == rows
    assert [
        (migrated.bridge, migrated.recorded_index) for migrated in record.steps
    ] == [("effect_last_step", 0)]
    assert record.bridge_counts() == {"effect_last_step": 1}
    assert canonical_state_hash(record.state) == canonical_state_hash(after)


def test_a_whole_action_is_expanded_only_for_records_before_v150(
    game: GameReplay,
) -> None:
    _, whole, start = _first_run(game, "trash_agent_card", 1)

    current = migrate_record(
        _v142_record(start, whole, codec=ACTION_CODEC_VERSION), _StartingAt(start)
    )

    # Stamped with this codec the whole action is not an action of this engine:
    # no effect bridge answers it and the record stops on it.
    assert current.divergence is not None
    assert current.divergence.recorded_index == 0
    assert current.divergence.step == whole
    assert not current.bridge_counts()
    assert current.steps == ()


def test_a_target_the_effect_does_not_offer_ends_the_record_there(
    game: GameReplay,
) -> None:
    _, whole, start = _first_run(game, "trash_agent_card", 1)
    elsewhere = DomainAction(
        whole.action_id,
        whole.actor,
        (("card_id", "player:0:starter:not_a_card:9"),),
    )

    record = migrate_record(
        _v142_record(start, elsewhere, codec=149), _StartingAt(start)
    )

    # The effect row was this engine's question; the recorded card is no
    # answer to it, which a rule change made, so the record diverges on it.
    assert record.divergence is not None
    assert record.divergence.recorded_index == 0
    assert record.divergence.step == elsewhere
    assert [migrated.bridge for migrated in record.steps] == ["effect_step"]
    assert "effect_last_step" not in record.bridge_counts()


# --- CHOAM Transports' card before a Contract's reward rows (codec v150) -------
# User decision 2026-10-19 ("A로 가자"): the card is the owner's only step right
# after the completion, before every row of the reward (OQ-106 13, OQ-112). An
# older engine paid the reward's automatic part inside the completion and drew
# the card after it.


def _transports_completed(*, empty_deck: bool) -> GameState:
    """Seat 0 has just completed Arrakeen I with CHOAM Transports in play."""

    from tests.unit.rules.test_owed_draws import _transports_turn

    placed = _transports_turn()
    if empty_deck:
        seat = placed.players[0]
        placed = replace(
            placed,
            players=(
                replace(seat, deck=(), discard_pile=(*seat.discard_pile, *seat.deck)),
                *placed.players[1:],
            ),
        )
    complete = DomainAction(
        "complete_contract", 0, (("instance_id", "contract:arrakeen_i"),)
    )
    return apply_whole(ENGINE, placed, complete).state


def test_a_step_recorded_behind_the_transports_card_takes_the_card_first() -> None:
    state = _transports_completed(empty_deck=False)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    draw = DomainAction(
        "draw_owed_card", 0, (("printed", "choam_transports"), ("source", "tech"))
    )
    assert ENGINE.whole_actions(state, 0) == (draw,)
    # Since stage B3d-4 (D-3) the seat answers it by its ``draw`` row naming
    # CHOAM Transports; an older record holds the whole action.
    assert ENGINE.legal_actions(state, 0) == (
        DomainAction(
            "draw",
            0,
            (("icon", "cards"), ("printed", "choam_transports"), ("source", "tech")),
        ),
    )
    row = DomainAction("resolve_contract_reward_icon", 0, (("effect", "resources"),))
    shuffle = ChanceOutcome(
        "round:1:player:0:contract:x:reward:personal_draw:discard_shuffle",
        ("player:0:starter:dagger:0",),
    )
    for recorded in (row, shuffle):
        taken = migration._transports_card_first(ENGINE, state, decision, recorded)
        assert taken == draw
    # The record's own draw is the card itself, applied as recorded.
    assert migration._transports_card_first(ENGINE, state, decision, draw) is None
    # Once drawn, nothing waits behind it.
    drawn = apply_whole(ENGINE, state, draw).state
    after = ENGINE.current_decision(drawn)
    assert isinstance(after, PlayerDecision)
    assert migration._transports_card_first(ENGINE, drawn, after, row) is None


def test_a_reshuffle_is_renamed_only_between_transports_and_a_reward_draw() -> None:
    state = _transports_completed(empty_deck=True)
    transports = DomainAction(
        "draw_owed_card", 0, (("printed", "choam_transports"), ("source", "tech"))
    )
    state = apply_whole(ENGINE, state, transports).state
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, ChanceDecision)
    assert decision.decision_id.endswith(":tech_draw:discard_shuffle")
    pile = tuple(decision.options)
    reward = "round:1:player:0:contract:contract:x:reward:personal_draw:discard_shuffle"
    renamed = migration._transports_reshuffle_renamed(
        ENGINE, state, decision, ChanceOutcome(reward, pile)
    )
    assert renamed == ChanceOutcome(decision.decision_id, pile)
    # Not another pile, and not between two other draws.
    assert (
        migration._transports_reshuffle_renamed(
            ENGINE, state, decision, ChanceOutcome(reward, pile[:-1])
        )
        is None
    )
    other = "round:1:player:0:board:x:discard_shuffle"
    assert (
        migration._transports_reshuffle_renamed(
            ENGINE, state, decision, ChanceOutcome(other, pile)
        )
        is None
    )


# --- Codec v152: the engine audit's split boxes and asked windows ---------------
# An older engine paid Interstellar Conspiracy's spice with its Faction choice
# (or as its plain resolution), did Scientific Breakthrough's owed Research in
# its trash and drew Guild Envoy's two cards in its Spacing Guild discard
# (engine audit 2026-10-22, P4-P6); it gave Overthrow's +1 beside the space's
# 1 (OQ-128) and skipped a seat that could not join a Scouts mission (OQ-131).


def test_a_recorded_conspiracy_resolution_is_its_spice_then_its_influence() -> None:
    from tests.unit.rules.test_immortality_imperium_choices import (
        DAGGER,
        _card,
        _graft,
        _owner,
        _state,
    )

    conspiracy = _card("interstellar_conspiracy")
    spice = DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("effect", "spice"),)
    )
    # Without an Emperor or Spacing Guild partner the plain resolution was
    # the spice: it is the spice icon's row, in either recorded form.
    alone = _graft(_state(_owner((conspiracy, DAGGER))), conspiracy, "arrakeen", DAGGER)
    named = DomainAction(
        action_id="resolve",
        actor=0,
        arguments=(("printed", "interstellar_conspiracy"), ("source", "agent_card")),
    )
    plain = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    for recorded in (plain, named):
        row = migration._conspiracy_icon(ENGINE, alone, _decided(alone), recorded)
        assert isinstance(row, DomainAction) and row in ENGINE.legal_actions(alone, 0)
        paid = ENGINE.apply(alone, row).state
        assert paid.players[0].resources.spice == alone.players[0].resources.spice + 1
        assert migration._conspiracy_spice(ENGINE, paid, _decided(paid), row) is None

    # With one, the Faction choice paid the spice too: it follows at once.
    keys = _card("keys_to_power")
    partnered = _graft(_state(_owner((conspiracy, keys))), conspiracy, "arrakeen", keys)
    choice = DomainAction(
        action_id="choose_agent_card_influence",
        actor=0,
        arguments=(("faction", "fremen"),),
    )
    chosen = apply_whole(ENGINE, partnered, choice).state
    follow = migration._conspiracy_spice(ENGINE, chosen, _decided(chosen), choice)
    assert follow == spice
    done = apply_whole(ENGINE, chosen, follow).state
    assert done.players[0].resources.spice == partnered.players[0].resources.spice + 1
    assert done.players[0].influence.fremen == 1
    assert migration._conspiracy_spice(ENGINE, done, _decided(done), follow) is None


def test_a_recorded_breakthrough_trash_takes_its_research_after() -> None:
    from tests.unit.rules.test_immortality_tleilaxu_cards import (
        _owner,
        _place,
        _state,
        _tleilaxu,
    )

    breakthrough = _tleilaxu("scientific_breakthrough")
    placed = _place(
        _state(_owner((breakthrough,), research_space="c8r4")), breakthrough, "arrakeen"
    )
    research = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    named = DomainAction(
        action_id="trash",
        actor=0,
        arguments=(("printed", "scientific_breakthrough"), ("source", "agent_card")),
    )
    whole = DomainAction(action_id="trash_agent_card_self_for_vp", actor=0)
    trashed = apply_whole(ENGINE, placed, whole).state
    for recorded in (whole, named):
        assert (
            migration._breakthrough_research(
                ENGINE, trashed, _decided(trashed), recorded
            )
            == research
        )
    researched = apply_whole(ENGINE, trashed, research).state
    assert len(researched.players[0].hand) == 1  # past the second marker
    assert (
        migration._breakthrough_research(
            ENGINE, researched, _decided(researched), whole
        )
        is None
    )
    # Not after another step of the box.
    assert (
        migration._breakthrough_research(ENGINE, placed, _decided(placed), research)
        is None
    )


@pytest.mark.parametrize(
    ("discarded", "draws"),
    [("reserve:the_spice_must_flow:9", True), ("player:0:starter:dagger:0", False)],
)
def test_a_recorded_guild_envoy_discard_draws_after_a_guild_card(
    discarded: str, draws: bool
) -> None:
    from tests.unit.rules.test_agent_effects import (
        _action_to,
        _imperium_instance,
        _instance,
    )

    from dune_imperium.rules.agent_turn import apply_agent_action

    envoy = _imperium_instance("guild_envoy")
    owner = PlayerState(
        player_id=0,
        hand=(envoy, discarded),
        deck=(_instance("convincing_argument"), _instance("reconnaissance")),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "deliver_supplies")).state
    discard = DomainAction(
        action_id="discard_agent_card", actor=0, arguments=(("card_id", discarded),)
    )
    after = apply_whole(ENGINE, placed, discard).state
    follow = migration._guild_envoy_draw(ENGINE, after, _decided(after), discard)
    if not draws:
        assert follow is None
        return
    assert follow == DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("effect", "cards"),)
    )
    drawn = apply_whole(ENGINE, after, follow).state
    assert len(drawn.players[0].hand) == 2
    assert migration._guild_envoy_draw(ENGINE, drawn, _decided(drawn), follow) is None


def _overthrow_on_secrets(bene_gesserit: int = 0) -> tuple[GameState, str]:
    """Seat 0 sends Overthrow to Secrets (a Bene Gesserit space)."""

    from tests.unit.rules.test_agent_effects import _action_to, _imperium_instance

    from dune_imperium.rules.agent_turn import apply_agent_action

    overthrow = _imperium_instance("overthrow")
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(
                player_id=0,
                hand=(overthrow,),
                influence=Influence(bene_gesserit=bene_gesserit),
            ),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    return apply_agent_action(state, _action_to(state, "secrets")).state, overthrow


_SPACE_STEP = DomainAction(
    action_id="gain_influence",
    actor=0,
    arguments=(
        ("icon", "faction"),
        ("printed", "secrets"),
        ("source", "board_space"),
    ),
)
_OVERTHROW_STEP = DomainAction(
    action_id="resolve",
    actor=0,
    arguments=(("printed", "overthrow"), ("source", "agent_card")),
)
_FINISH = DomainAction(action_id="finish_agent_turn", actor=0)


def test_overthrow_lands_its_two_where_an_older_engine_reached_even() -> None:
    # OQ-128: "Gain two Influence instead of one." replaces the space's one;
    # a recording engine gave the space's 1 and the card's +1 as two steps.
    # The two land on the part where its +1 reached an even Influence (the
    # track's 2 and 4), the other part is dropped.
    even, _ = _overthrow_on_secrets(0)
    odd, _ = _overthrow_on_secrets(1)
    plan = migration._overthrow_plan
    for first, second in (
        (_SPACE_STEP, _OVERTHROW_STEP),
        (_OVERTHROW_STEP, _SPACE_STEP),
    ):
        steps = (first, second, _FINISH)
        assert plan(even, steps, 0, 0) == migration.OVERTHROW_DEFERRED
    # Odd: the first part takes the two -- the space's step as the box, the
    # box's own step as recorded.
    assert plan(odd, (_SPACE_STEP, _OVERTHROW_STEP, _FINISH), 0, 0) == (
        migration.OVERTHROW_FOR_SPACE
    )
    assert plan(odd, (_OVERTHROW_STEP, _SPACE_STEP, _FINISH), 0, 0) is None
    # After a deferred first part the second takes the two, whichever it is
    # (its pair is behind it, so no lookahead finds it).
    assert plan(even, (_OVERTHROW_STEP, _SPACE_STEP, _FINISH), 1, 0) is None
    assert plan(even, (_OVERTHROW_STEP, _SPACE_STEP, _FINISH), 1, 0, deferred=True) == (
        migration.OVERTHROW_FOR_SPACE
    )
    assert plan(even, (_SPACE_STEP, _OVERTHROW_STEP, _FINISH), 1, 0, deferred=True) == (
        migration._OVERTHROW_SECOND
    )
    row = migration._overthrow_space_row(ENGINE, odd, 0)
    assert row == _OVERTHROW_STEP
    gained = ENGINE.apply(odd, row).state
    assert gained.players[0].influence.bene_gesserit == 3
    assert migration._overthrow_part_done(gained, _OVERTHROW_STEP)
    boxed = ENGINE.apply(odd, _OVERTHROW_STEP).state
    assert migration._overthrow_part_done(boxed, _SPACE_STEP)


def test_overthrow_is_planned_only_when_both_parts_are_recorded() -> None:
    # The recording engine lapsed the box when another effect trashed the
    # card first (OQ-022): the space's step is left as recorded, so the
    # record stops where this engine holds it behind the box, rather than
    # gain two it never gained (review of codec v152).
    even, overthrow = _overthrow_on_secrets(0)
    plan = migration._overthrow_plan
    trash = DomainAction(
        action_id="choose_personal_card", actor=0, arguments=(("card_id", overthrow),)
    )
    assert plan(even, (_SPACE_STEP, trash, _FINISH), 0, 0) is None
    assert _SPACE_STEP not in ENGINE.legal_actions(even, 0)
    # A step between that names the card lands the two on the first part:
    # deferred, the box could lapse before them.
    assert plan(even, (_OVERTHROW_STEP, trash, _SPACE_STEP, _FINISH), 0, 0) is None
    assert plan(even, (_SPACE_STEP, trash, _OVERTHROW_STEP, _FINISH), 0, 0) == (
        migration.OVERTHROW_FOR_SPACE
    )
    # Another seat's steps and chance between do not count.
    other = DomainAction(action_id="pass_combat_intrigue", actor=1)
    assert plan(even, (_OVERTHROW_STEP, other, _SPACE_STEP, _FINISH), 0, 0) == (
        migration.OVERTHROW_DEFERRED
    )


def test_a_graft_slot_reads_an_untagged_box_1_step_as_box_1s() -> None:
    # Before codec v143 a grafted turn's box 1 steps carried no tag while
    # that engine had box 1 active (_GraftSlot): the partner's plain
    # resolution is not Overthrow's box 0 part (review of codec v152).
    from tests.unit.rules.test_immortality_imperium_choices import (
        _card,
        _graft,
        _owner,
        _state,
    )

    overthrow = _card("overthrow")
    partner = _card("interstellar_conspiracy")
    grafted = _graft(
        _state(_owner((overthrow, partner))), overthrow, "secrets", partner
    )
    plain = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    space = DomainAction(action_id="resolve_faction_influence", actor=0)
    steps = (plain, space, _FINISH)
    assert migration._overthrow_plan(grafted, steps, 0, 1) is None
    assert migration._overthrow_plan(grafted, steps, 0, 0) == (
        migration.OVERTHROW_DEFERRED
    )
    assert migration._slot_tagged(plain, 1) == tagged(plain, 1)
    assert migration._slot_tagged(_FINISH, 1) == _FINISH


def test_another_cards_two_instead_of_one_is_no_overthrow_part() -> None:
    # Subversive Advisor's box replaces the space's one too: a refused
    # space step there is not Overthrow's to drop (review of codec v152).
    from tests.unit.rules.test_immortality_tleilaxu_cards import (
        FACE_DANCER,
        SUBVERSIVE,
        _graft,
        _owner,
        _state,
    )

    grafted = _graft(
        _state(_owner((FACE_DANCER, SUBVERSIVE))),
        FACE_DANCER,
        "dutiful_service",
        SUBVERSIVE,
    )
    resolved = apply_whole(
        ENGINE,
        grafted,
        tagged(DomainAction(action_id="resolve_agent_card_effect", actor=0), 1),
    ).state
    space = DomainAction(action_id="resolve_faction_influence", actor=0)
    assert not migration._overthrow_part_done(resolved, space)


def test_a_mission_window_with_the_pass_alone_is_passed_before_the_record() -> None:
    # OQ-131: a seat that cannot join a Scouts mission is asked, with the
    # pass alone; an older engine skipped it unasked, so the window is never
    # the record's to answer -- a recorded pass of that seat belongs to a
    # later mission (review of codec v152).
    from tests.unit.rules import test_scouts_missions as missions

    base = missions._base()
    empty = replace(base.players[1], troops_supply=0, troops_garrison=12)
    state = missions._reveal(
        replace(base, players=(base.players[0], empty, *base.players[2:])),
        "security_detail",
    )
    taken = migration._Taken()
    # Seat 0 can join: its window is the record's.
    assert missions._owner(state) == 0
    assert migration._answer_windows_never_asked(ENGINE, state, taken) is state
    state = missions._act(state, "scouts_decline_mission")
    assert missions._owner(state) == 1
    passed = migration._answer_windows_never_asked(ENGINE, state, taken)
    assert missions._owner(passed) == 2
    assert [step.bridge for step in taken.steps] == [migration.MISSION_PASS_ALONE]


def test_political_equilibrium_windows_an_older_engine_never_opened() -> None:
    # Codec v152 asks every seat (OQ-131, user decision 2026-10-25): an older
    # engine took a lone highest track's loss itself and skipped a seat with
    # every track at 0, but asked a tie. The one-row windows are answered
    # before the record's next step; a tie is the record's.
    from tests.unit.rules import test_scouts_choices as choices

    state = choices._base(
        **{
            "0": {"influence": Influence(fremen=3, emperor=1)},
            "1": {"influence": Influence(spacing_guild=2, bene_gesserit=2)},
            "2": {"influence": Influence()},
            "3": {"influence": Influence(fremen=1)},
        }
    )
    state = choices._reveal(state, "political_equilibrium")
    taken = migration._Taken()
    tied = migration._answer_windows_never_asked(ENGINE, state, taken)
    assert choices._owner(tied) == 1
    assert tied.players[0].influence == Influence(fremen=2, emperor=1)
    state = choices._act(tied, "scouts_lose_influence", faction="bene_gesserit")
    done = migration._answer_windows_never_asked(ENGINE, state, taken)
    assert choices._on_turn(done)
    assert done.players[3].influence == Influence()
    assert [step.bridge for step in taken.steps] == [migration.EQUILIBRIUM_ALONE] * 3


def test_a_recorded_scouts_pass_is_the_confirm_where_every_line_is_withheld() -> None:
    # P2 (OQ-071) withholds a Scouts cost line whose rewards buy nothing; a
    # pass recorded where every line an older engine offered is withheld is
    # the confirm of taking nothing.
    from tests.unit.rules import test_scouts_choices as choices

    poor = {"resources": Resources(solari=1, spice=0, water=1)}
    state = choices._reveal(choices._base(**{"0": poor}), "royal_delegation")
    decision = _decided(state)
    recorded = DomainAction(action_id="scouts_pass", actor=0)
    confirm = migration._scouts_pass_without_option(
        ENGINE, state, decision, recorded
    )
    assert confirm is not None and confirm in ENGINE.legal_actions(state, 0)
    # Not where a line is offered.
    rich = choices._reveal(choices._base(), "royal_delegation")
    assert (
        migration._scouts_pass_without_option(ENGINE, rich, _decided(rich), recorded)
        is None
    )


def test_a_navigation_reshuffle_is_renamed_only_for_overthrows_gain() -> None:
    # A Navigation card's draw is named after the gain that triggered it;
    # Overthrow's two (OQ-128) move that gain to the card's box.
    state, _, pile = _planetary_array_reshuffle()
    old = "round:1:player:0:influence:bene_gesserit:navigation:0:discard_shuffle"
    new = (
        "round:1:player:0:agent_card:imperium:overthrow:0:influence:bene_gesserit"
        ":navigation:1:discard_shuffle"
    )
    renamed = migration._navigation_reshuffle_renamed

    def asking(decision_id: str) -> ChanceDecision:
        return ChanceDecision(
            decision_id=decision_id, prompt="Shuffle", options=pile, count=len(pile)
        )

    recorded = ChanceOutcome(old, pile)
    assert renamed(ENGINE, state, asking(new), recorded) == ChanceOutcome(new, pile)
    # Not another Faction's, not a draw outside a card's box.
    other = ChanceOutcome(old.replace("bene_gesserit", "fremen"), pile)
    assert renamed(ENGINE, state, asking(new), other) is None
    space = "round:1:player:0:influence:bene_gesserit:navigation:1:discard_shuffle"
    assert renamed(ENGINE, state, asking(space), recorded) is None
