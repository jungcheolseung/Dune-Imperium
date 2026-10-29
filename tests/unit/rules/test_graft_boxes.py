"""The box-scoped keys of a grafted Agent turn (docs/graft-boxes-plan.md 4.2).

"You gain the effects on both cards, in addition to the board space
effects, in any order you choose." [Immortality pp. 10-11]. Each key of the
Agent-turn effect frame is one box's, a card's, or the turn's
(``rules.graft_boxes``); swapping the boxes must move every box-scoped key,
so these tests keep a new key from riding along unclassified.
"""

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.action_codec import ActionTemplate
from dune_imperium.adapters.observation_encoding import (
    PERSONAL_CARD_IDS,
    encode_player_view,
    segment_slice,
)
from dune_imperium.agents import RandomAgent
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GameState,
    Influence,
    PlayerState,
    Resources,
)
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import Transition
from dune_imperium.core.state import GamePhase
from dune_imperium.rules import (
    UprisingRulesEngine,
    agent_effects,
    combat_deployment,
    effects,
    frames,
    leader_abilities,
)
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.agent_icons import card_is_boosted
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.box_events import BoxOutcome, agent_box_event
from dune_imperium.rules.effect_steps import steps_for
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft_boxes import (
    ACTIVE_BOX_KEY,
    BOX_ACTION_IDS,
    BOX_KEY_PAIRS,
    BOX_KEYS,
    CARD_KEYS,
    TURN_KEYS,
    active_box,
    row_box,
    swap_boxes,
    unclassified_keys,
)

RULES = Path(agent_effects.__file__).parent

# Keys the rule modules read or write on frames other than the Agent-turn
# effect frame (Reveal, Intrigue, Contract, graft partner, Scouts, Combat
# and the rest). Every key the scan below finds is either classified by
# ``rules.graft_boxes`` or listed here, so a new effect-frame key cannot be
# added without deciding whether it belongs to one box.
OTHER_FRAME_KEYS = frozenset(
    {
        "acquire_effects_only",
        "acquisition_card_id",
        "acquisition_spy_recalled",
        "advance_agent_frame",
        "artillery_counted",
        "choice_index",
        "choice_sword_card_ids",
        "chose",
        "chosen_factions",
        "chosen_lines",
        "chosen_mask",
        "combat_deployment",
        "consecutive_passes",
        "contract_id",
        "contract_spy_id",
        "contract_spy_recalled",
        "count",
        "covert_operation_card_id",
        "covert_operation_owner",
        "deep_cover",
        "deferred_acquisition_triggers",
        "deferred_reveal_choices",
        "exclude_space",
        "excluded_space_id",
        "granted_reveal_lines",
        "guild_spy_fired",
        "hand",
        "icons",
        "infiltrate_post_id",
        "intrigue_pending",
        "leader_intrigue_granted",
        "leader_persuasion_granted",
        "leader_reveal_ability_used",
        "lines_taken",
        "long_live_fighters_draw_card_id",
        "occupied",
        "only_option",
        "opponent_discards_remaining",
        "option",
        "optional_sword_strength",
        "or_lose_deployed_troop",
        "partner_waives_influence",
        "pending_ability",
        "pending_lines",
        "persuasion",
        "persuasion_generated",
        "picked",
        "placed_reaches",
        "played",
        "played_at_priority",
        "printed",
        "player",
        "purpose",
        "remaining",
        "research_icons",
        "resource",
        "reveal_card_id",
        "reveal_choice_effect",
        "reveal_commanders_deployed",
        "reveal_commanders_recruited",
        "reveal_pending_gains",
        "reveal_recruits_deployable",
        "reveal_recruits_owed",
        "reveal_spy_recalled",
        "reveal_troops_recruited",
        "reveal_units_deployed",
        "revealed_card_count",
        "separate_effect",
        # Refocus's reshuffle of the deck along with the discard pile
        # (``card_draw.SHUFFLE_DECK_KEY``).
        "shuffle_deck",
        "skill_reveal_granted",
        "source",
        "spice_must_flow_acquired",
        "step",
        "stop",
        "strength",
        "sword_strength",
        "tech_granted",
        "tech_reveal_pending",
        "turn_agent_in_conflict",
        "turn_start_over",
    }
)


def _string_tuple(value: ast.expr | None) -> tuple[str, ...] | None:
    if isinstance(value, ast.Tuple | ast.List) and all(
        isinstance(item, ast.Constant) and isinstance(item.value, str)
        for item in value.elts
    ):
        return tuple(
            str(item.value) for item in value.elts if isinstance(item, ast.Constant)
        )
    return None


def _module_string_constants(
    sources: dict[str, str],
) -> tuple[dict[str, str], dict[str, set[str]]]:
    """Module-level string names, and every name bound to a string tuple."""

    constants: dict[str, str] = {}
    tuples: dict[str, set[str]] = {}
    for source in sources.values():
        tree = ast.parse(source)
        for node in tree.body:
            target: ast.expr | None = None
            value: ast.expr | None = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            if (
                isinstance(target, ast.Name)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                constants[target.id] = value.value
        # A loop over a name bound to string tuples anywhere in rules/
        # (``for key in keys`` with ``keys = ("a", "b")`` in each branch).
        for inner in ast.walk(tree):
            if isinstance(inner, ast.Assign) and len(inner.targets) == 1:
                target, value = inner.targets[0], inner.value
            elif isinstance(inner, ast.AnnAssign):
                target, value = inner.target, inner.value
            else:
                continue
            names = _string_tuple(value)
            if isinstance(target, ast.Name) and names is not None:
                tuples.setdefault(target.id, set()).update(names)
    return constants, tuples


def _context_names(tree: ast.Module) -> set[str]:
    """Names bound to a copy of a frame's context (``host = dict(frame.context)``)."""

    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "dict"
            and node.value.args
            and "context" in ast.unparse(node.value.args[0])
        ):
            names.add(node.targets[0].id)
    return names


def _is_context(base: ast.expr | None, aliases: set[str]) -> bool:
    return isinstance(base, ast.Name) and (
        "context" in base.id or base.id in aliases
    )


def _key_names(
    key: ast.expr | None,
    constants: dict[str, str],
    loops: dict[str, set[str]],
) -> set[str]:
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return {key.value}
    if isinstance(key, ast.Name) and key.id in constants:
        return {constants[key.id]}
    if isinstance(key, ast.Name) and key.id in loops:
        return set(loops[key.id])
    return set()


def _context_keys_in_rules() -> dict[str, set[str]]:
    """Every string key read or written on a frame context of rules/."""

    return _context_keys_in(
        {path.name: path.read_text() for path in sorted(RULES.glob("*.py"))}
    )


def _context_keys_in(sources: dict[str, str]) -> dict[str, set[str]]:
    """Every string key read or written on a frame context of ``sources``.

    A context is a name containing ``context`` or one bound to a copy of a
    frame's context (``host = dict(frame.context)``). A key is read or
    written by subscript, ``get``/``pop``/``setdefault``, ``in``, a
    ``{**context, key: ...}`` literal or ``update``; it is a string, a
    module string constant, or a loop variable over string tuples.
    """

    constants, tuples = _module_string_constants(sources)
    found: dict[str, set[str]] = {}
    for file_name, source in sources.items():
        tree = ast.parse(source)
        aliases = _context_names(tree)
        loops: dict[str, set[str]] = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.For)
                and isinstance(node.target, ast.Name)
                and isinstance(node.iter, ast.Name)
                and node.iter.id in tuples
            ):
                loops.setdefault(node.target.id, set()).update(tuples[node.iter.id])

        for node in ast.walk(tree):
            keys: list[ast.expr | None] = []
            base: ast.expr | None = None
            if isinstance(node, ast.Subscript):
                base, keys = node.value, [node.slice]
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("get", "pop", "setdefault")
                and node.args
            ):
                base, keys = node.func.value, [node.args[0]]
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "update"
            ):
                base = node.func.value
                keys = [
                    ast.Constant(keyword.arg)
                    for keyword in node.keywords
                    if keyword.arg is not None
                ]
                for argument in node.args:
                    if isinstance(argument, ast.Dict):
                        keys.extend(argument.keys)
            elif (
                isinstance(node, ast.Compare)
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.In | ast.NotIn)
            ):
                base, keys = node.comparators[0], [node.left]
            elif isinstance(node, ast.Dict) and any(
                key is None and _is_context(value, aliases)
                for key, value in zip(node.keys, node.values, strict=True)
            ):
                # ``{**context, "key": value}``: a copy with keys written.
                base = next(
                    value
                    for key, value in zip(node.keys, node.values, strict=True)
                    if key is None and _is_context(value, aliases)
                )
                keys = [key for key in node.keys if key is not None]
            if not _is_context(base, aliases):
                continue
            for key in keys:
                for name in _key_names(key, constants, loops):
                    found.setdefault(name, set()).add(file_name)
    return found


def test_every_context_key_in_the_rules_is_classified() -> None:
    found = _context_keys_in_rules()
    classified = BOX_KEYS | CARD_KEYS | TURN_KEYS
    unknown = sorted(
        f"{key} ({', '.join(sorted(files))})"
        for key, files in found.items()
        if key not in classified and key not in OTHER_FRAME_KEYS
    )
    assert unknown == []
    # The list of other frames' keys stays current and disjoint.
    assert sorted(OTHER_FRAME_KEYS - set(found)) == []
    assert OTHER_FRAME_KEYS.isdisjoint(classified)


def test_the_key_scan_sees_every_way_a_rule_module_writes_a_context() -> None:
    """A copy of a frame's context under another name, a ``{**context}``
    literal, ``update`` and a loop over key tuples all count, so a new key
    written that way fails the classification test above instead of
    stopping a live game's swap (``swap_boxes``)."""

    source = (
        'KEY = "constant_key"\n'
        '_COUNTERS = ("loop_one", "loop_two")\n'
        "def write(frame, context):\n"
        "    host = dict(frame.context)\n"
        '    host["host_key"] = 1\n'
        "    for key in _COUNTERS:\n"
        "        host[key] = 2\n"
        '    reopened = {**context, "literal_key": True}\n'
        '    context.update({"update_key": 1}, keyword_key=2)\n'
        "    context[KEY] = reopened\n"
        '    other = {"unrelated": 1}\n'
        '    other["not_a_context"] = 1\n'
    )
    assert set(_context_keys_in({"module.py": source})) == {
        "constant_key",
        "loop_one",
        "loop_two",
        "host_key",
        "literal_key",
        "update_key",
        "keyword_key",
    }


def test_the_classes_are_disjoint_and_pair_each_box_key_once() -> None:
    assert BOX_KEYS.isdisjoint(CARD_KEYS)
    assert BOX_KEYS.isdisjoint(TURN_KEYS)
    assert CARD_KEYS.isdisjoint(TURN_KEYS)
    assert len(BOX_KEYS) == 2 * len(BOX_KEY_PAIRS)


def test_the_classified_names_match_the_rule_modules_constants() -> None:
    assert effects.BOOST_DRAW_KEY in CARD_KEYS
    assert agent_effects._RESEARCHED_BOXES in CARD_KEYS
    assert agent_effects._SPACE_INFLUENCE_REPLACED in TURN_KEYS
    assert ("signet_rewards", "graft_signet_rewards") in BOX_KEY_PAIRS
    assert leader_abilities.SIGNET_REWARDS_KEY == "signet_rewards"
    for key in (
        combat_deployment.FINISHING_KEY,
        combat_deployment.FINISH_DEPLOYMENT_KEY,
        combat_deployment.FINISH_RECRUITS_KEY,
        combat_deployment.DEPLOYED_UNITS_KEY,
        combat_deployment.DEPLOYED_COMMANDERS_KEY,
        combat_deployment.WITHDRAWABLE_UNITS_KEY,
        combat_deployment.WITHDRAWABLE_COMMANDERS_KEY,
        frames.COMMANDERS_RECRUITED_KEY,
        frames.TECH_ACQUIRE_PENDING_KEY,
        *effects.AGENT_EFFECT_CONTEXT_KEYS - BOX_KEYS,
    ):
        assert key in TURN_KEYS, key


def test_swap_boxes_moves_every_box_key_and_flips_the_active_box() -> None:
    context: dict[str, bool | int | str] = {
        "card_id": "a",
        "graft_card_id": "b",
        "pending_agent_effect": True,
        "graft_pending_effect": False,
        "pending_agent_icons": "cards",
        "graft_pending_icons": "",
        "rewards_chosen": "water",
        "graft_trashes_remaining": 1,
        "boost_draw_card_ids": "a",
        "space_id": "arrakeen",
    }
    swap_boxes(context)
    assert active_box(context) == 1
    assert context == {
        "card_id": "b",
        "graft_card_id": "a",
        "pending_agent_effect": False,
        "graft_pending_effect": True,
        "pending_agent_icons": "",
        "graft_pending_icons": "cards",
        "graft_rewards_chosen": "water",
        "trashes_remaining": 1,
        "boost_draw_card_ids": "a",
        "space_id": "arrakeen",
        ACTIVE_BOX_KEY: 1,
    }
    swap_boxes(context)
    assert active_box(context) == 0
    assert context["rewards_chosen"] == "water"
    assert "graft_trashes_remaining" in context


def test_swap_boxes_refuses_an_unclassified_key() -> None:
    context: dict[str, bool | int | str] = {"card_id": "a", "new_key": 1}
    assert unclassified_keys(context) == ("new_key",)
    with pytest.raises(RuntimeError, match="new_key"):
        swap_boxes(context)


@pytest.mark.parametrize("seed", [3, 11])
def test_every_key_of_a_played_effect_frame_is_classified(seed: int) -> None:
    """Random all-option games with Immortality: each effect frame met."""

    engine = UprisingRulesEngine()
    config = RulesetConfig(
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
    )
    state = engine.reset(config, seed)
    agents = [RandomAgent(seed=100 * seed + seat) for seat in range(4)]
    chance = ChanceResolver(seed=seed)
    seen: set[str] = set()
    for _ in range(30_000):
        if state.phase is GamePhase.FINISHED:
            break
        for frame in state.decision_stack:
            if frame.kind == FrameKind.AGENT_EFFECTS:
                seen.update(key for key, _ in frame.context)
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(engine, state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        legal = engine.whole_actions(state, decision.owner)
        action = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), legal
        )
        state = apply_whole(engine, state, action, legal_actions=legal).state
    assert state.phase is GamePhase.FINISHED
    assert unclassified_keys(dict.fromkeys(seen, 0)) == ()


# ---------------------------------------------------------------------------
# Both boxes offered from the start (docs/graft-boxes-plan.md 4.1-4.6)
# ---------------------------------------------------------------------------

IMMORTALITY = RulesetConfig(immortality=True, promo_cards=True)
STARTERS = starting_deck_instance_ids(0, immortality=True)
DAGGER = next(card for card in STARTERS if "dagger:0" in card)
GHOLA = "tleilaxu:ghola:0"
TANKS = "tleilaxu:from_the_tanks:0"
HORROR = "tleilaxu:stitched_horror:0"
PITER = "tleilaxu:piter_genius_advisor:0"
PHEROMONES = "tleilaxu:beguiling_pheromones:0"
INFILTRATOR = "tleilaxu:tleilaxu_infiltrator:0"
COUPLING = "imperium:planned_coupling:0"
LONG_REACH = "imperium:long_reach:0"
BEAST = "imperium:the_beast_s_spoils:0"
DISSECTING = "imperium:dissecting_kit:0"
CORRINTH = "imperium:corrinth_city:0"
ENGINE = UprisingRulesEngine()


def _seat(seat: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": seat,
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _state(hand: tuple[str, ...], **owner: object) -> GameState:
    imperium = imperium_deck_instance_ids(False)
    seats = [
        _seat(
            0,
            hand=hand,
            deck=tuple(card for card in STARTERS if card not in hand),
            resources=Resources(solari=4, spice=2, water=2),
            **owner,
        ),
        *(_seat(seat) for seat in range(1, 4)),
    ]
    return GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        first_player=0,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        tleilaxu_track_spice=2,
        players=tuple(seats),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _spaces_offered(state: GameState, card_id: str) -> set[str]:
    """The spaces the Agent turn offers ``card_id``: pick the card (each of
    its picks), read the ``place_agent`` rows (stage B1)."""

    spaces: set[str] = set()
    for pick in ENGINE.whole_actions(state, 0):
        if (
            pick.action_id == "choose_agent_card"
            and dict(pick.arguments)["card_id"] == card_id
        ):
            picked = apply_whole(ENGINE, state, pick).state
            spaces |= {
                str(dict(action.arguments)["space_id"])
                for action in ENGINE.whole_actions(picked, 0)
                if action.action_id == "place_agent"
            }
    return spaces


def _graft(state: GameState, card_id: str, space_id: str, partner: str) -> GameState:
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    placed = apply_placement(ENGINE, state, placement).state
    choice = DomainAction(
        "choose_graft_partner", 0, arguments=(("card_id", partner),)
    )
    return apply_whole(ENGINE, placed, choice).state


def _row(state: GameState, action_id: str, box: int = 0, **arguments: object) -> (
    DomainAction
):
    return next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == action_id
        and dict(action.arguments).get("box", 0) == box
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )


def _apply(state: GameState, action_id: str, box: int = 0, **arguments: object) -> (
    GameState
):
    return apply_whole(ENGINE, state, _row(state, action_id, box, **arguments)).state


def _boxes_offered(state: GameState, action_id: str) -> set[int]:
    return {
        row_box(action)
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == action_id
    }


def test_both_boxes_are_offered_from_the_start_in_either_order() -> None:
    """Ghola copies From the Tanks' box, so both boxes offer the same plain
    resolution: box 0's untagged, box 1's with ``box=1``. Either may go
    first, and each resolves its own box once (no switch, no loop)."""

    state = _graft(_state((GHOLA, TANKS), troops_supply=9), GHOLA, "arrakeen", TANKS)
    assert _boxes_offered(state, "resolve_agent_card_effect") == {0, 1}
    assert "switch_graft_card" not in {
        action.action_id for action in ENGINE.whole_actions(state, 0)
    }
    partner_first = _apply(state, "resolve_agent_card_effect", box=1)
    assert partner_first.players[0].troops_garrison == 5
    _, context = current_agent_effect_context(partner_first)
    assert (context["card_id"], context["graft_card_id"]) == (TANKS, GHOLA)
    assert _boxes_offered(partner_first, "resolve_agent_card_effect") == {0}
    # The untagged row is box 0's although box 1 is the active one now.
    both = _apply(partner_first, "resolve_agent_card_effect")
    assert both.players[0].troops_garrison == 7
    assert "resolve_agent_card_effect" not in {
        action.action_id for action in ENGINE.whole_actions(both, 0)
    }


def test_a_choose_two_box_keeps_the_other_box_waiting_until_its_second_pick() -> (
    None
):
    """"Choose two" names both before either resolves (OQ-057 (4)), and the
    other box waits meanwhile (user decision 2026-10-12, plan 4.3)."""

    state = _graft(
        _state((HORROR, GHOLA), troops_supply=9), HORROR, "arrakeen", GHOLA
    )
    assert _boxes_offered(state, "choose_agent_card_reward") == {0, 1}
    first = _apply(state, "choose_agent_card_reward", box=1, reward="water")
    assert _boxes_offered(first, "choose_agent_card_reward") == {1}
    assert not any(
        ("box", 1) not in action.arguments
        and action.action_id == "choose_agent_card_reward"
        for action in ENGINE.whole_actions(first, 0)
    )
    second = _apply(first, "choose_agent_card_reward", box=1, reward="troop")
    owner = second.players[0]
    assert (owner.resources.water, owner.troops_garrison) == (3, 4)
    # Box 0 (Stitched Horror) names its own two from all four.
    assert {
        dict(action.arguments)["reward"]
        for action in ENGINE.whole_actions(second, 0)
        if action.action_id == "choose_agent_card_reward"
    } == {"water", "troop", "trash", "tleilaxu"}
    third = _apply(second, "choose_agent_card_reward", reward="water")
    assert _boxes_offered(third, "choose_agent_card_reward") == {0}
    done = _apply(third, "choose_agent_card_reward", reward="tleilaxu")
    owner = done.players[0]
    assert (owner.resources.water, owner.troops_garrison) == (4, 4)
    assert owner.tleilaxu_space == 1


def test_an_arrow_s_rewards_keep_the_other_box_waiting() -> None:
    """Piter's "Lose a troop -> draw two cards and Research": once the troop
    is paid, its two rewards wait as icons and the Ghola copy's rows wait
    until both are taken (plan 4.3)."""

    state = _graft(_state((PITER, GHOLA)), PITER, "assembly_hall", GHOLA)
    assert _boxes_offered(state, "lose_agent_card_troop") == {0, 1}
    paid = _apply(state, "lose_agent_card_troop", zone="garrison")
    assert not any(
        ("box", 1) in action.arguments for action in ENGINE.whole_actions(paid, 0)
    )
    drew = _apply(paid, "resolve_agent_card_effect", effect="cards")
    assert not any(
        ("box", 1) in action.arguments for action in ENGINE.whole_actions(drew, 0)
    )
    researched = _apply(drew, "resolve_agent_card_effect", effect="research")
    while researched.decision_stack[-1].kind != FrameKind.AGENT_EFFECTS:
        decision = ENGINE.current_decision(researched)
        assert isinstance(decision, PlayerDecision)
        researched = apply_whole(ENGINE, 
            researched, ENGINE.whole_actions(researched, decision.owner)[0]
        ).state
    assert _boxes_offered(researched, "lose_agent_card_troop") == {1}


def test_the_turn_ends_while_only_the_partner_s_box_waits() -> None:
    """Beguiling Pheromones' box needs a Faction space; at the Assembly Hall
    it waits for the turn's end (OQ-057 (1)). With no other box pending the
    end is offered at once -- there is no switch to make it the active box
    first -- and the press fizzles it."""

    state = _graft(_state((DAGGER, PHEROMONES)), DAGGER, "assembly_hall", PHEROMONES)
    _, context = current_agent_effect_context(state)
    assert context["pending_agent_effect"] is False
    assert context["graft_pending_effect"] is True
    while any(
        action.action_id == "resolve_board_effect"
        for action in ENGINE.whole_actions(state, 0)
    ):
        state = _apply(state, "resolve_board_effect")
    assert "finish_agent_turn" in {
        action.action_id for action in ENGINE.whole_actions(state, 0)
    }
    finished = apply_whole(ENGINE, state, DomainAction("finish_agent_turn", 0))
    assert "agent_card_effect_unavailable" in {
        event.kind for event in finished.events
    }
    assert finished.state.decision_stack[-1].kind == FrameKind.TURN


def test_a_choose_two_that_cannot_go_on_frees_the_other_box_and_the_end() -> (
    None
):
    """Long Reach (box 1) names the Emperor first; the Secrets space then
    raises Bene Gesserit to the top, so no second Faction can be named. The
    selection waits for the turn's end like any box that can only fizzle
    (OQ-057 (1)) instead of holding box 0 back: box 0 is offered again, the
    turn can end, and the end pays the Faction already named (Long Reach's
    one named Faction is paid and the rest is lost, OQ-060). The lock held
    while box 0 could do nothing left no legal action at all."""

    influence = Influence(emperor=3, spacing_guild=6, bene_gesserit=5, fremen=6)
    state = _graft(
        _state((COUPLING, LONG_REACH), influence=influence),
        COUPLING,
        "secrets",
        LONG_REACH,
    )
    named = _apply(state, "choose_agent_card_influence", box=1, faction="emperor")
    # The second pick is still open: box 0 waits (plan 4.3).
    assert agent_effects.box_in_progress(named)
    assert _boxes_offered(named, "resolve_agent_card_effect") == set()
    assert named.players[0].influence.emperor == 3
    raised = apply_whole(
        ENGINE, named, DomainAction("resolve_faction_influence", 0)
    ).state
    assert raised.players[0].influence.bene_gesserit == 6
    assert not agent_effects.box_in_progress(raised)
    assert _boxes_offered(raised, "choose_agent_card_influence") == set()
    assert _boxes_offered(raised, "resolve_agent_card_effect") == {0}
    coupled = _apply(raised, "resolve_agent_card_effect")
    while _boxes_offered(coupled, "resolve_board_effect"):
        coupled = _apply(coupled, "resolve_board_effect")
    assert agent_effects.graft_boxes_are_stalled(coupled)
    finished = apply_whole(ENGINE, coupled, DomainAction("finish_agent_turn", 0))
    # The named Faction is paid first, then the box ends unavailable (the box's
    # event comes last among the events the box produced, cleanup-2c-2).
    assert finished.events[0].kind == "influence_gained"
    unavailable = agent_box_event(
        effects.agent_card_source(1, 0, LONG_REACH),
        LONG_REACH,
        0,
        BoxOutcome.UNAVAILABLE,
    )
    assert unavailable in finished.events
    assert finished.state.players[0].influence.emperor == 4


def _settle_all_but_box_one(state: GameState) -> GameState:
    """Resolve the visited space and box 0's automatic rows."""

    while True:
        legal = ENGINE.whole_actions(state, 0)
        rows = [
            action
            for action in legal
            if action.action_id in ("resolve_board_effect", "resolve_faction_influence")
            or (
                action.action_id == "resolve_agent_card_effect"
                and row_box(action) == 0
            )
        ]
        if not rows:
            return state
        state = apply_whole(ENGINE, state, rows[0], legal_actions=legal).state


@pytest.mark.parametrize(
    ("placed", "partner", "taken", "argument"),
    [
        (INFILTRATOR, PITER, "lose_agent_card_troop", ("zone", "garrison")),
        (BEAST, DISSECTING, "trash_grafted_card_for_specimen", None),
    ],
)
def test_a_partner_box_with_a_choice_stays_reachable(
    placed: str, partner: str, taken: str, argument: tuple[str, str] | None
) -> None:
    """"You gain the effects on both cards, in addition to the board space
    effects, in any order you choose." [Immortality pp. 10-11]. Piter's
    optional arrow and Dissecting Kit's trash are the partner's box to
    take. The engine before codec v143 hid its switch once a dry run called
    both boxes unavailable, which misread such choice boxes, so the
    partner's box could only fizzle at the turn's end; now its rows are
    offered. They are optional, so since the user ruling of 2026-10-14
    (OQ-095 (2), codec v146) they come without a refusal and the turn end
    lapses them (``test_an_optional_box_with_a_choice_stands_beside_the_turn_end``)."""

    state = _settle_all_but_box_one(
        _graft(_state((placed, partner), troops_supply=9), placed, "arrakeen", partner)
    )
    offered = {
        action.action_id
        for action in ENGINE.whole_actions(state, 0)
        if row_box(action) == 1
    }
    assert taken in offered
    assert "decline_agent_card_payment" not in offered
    row = next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == taken
        and row_box(action) == 1
        and (argument is None or argument in action.arguments)
    )
    before = state.players[0]
    after = apply_whole(ENGINE, state, row).state.players[0]
    if partner == PITER:
        assert after.troops_garrison == before.troops_garrison - 1
    else:
        assert after.specimens == before.specimens + 1
        assert placed in after.trashed


# A mandatory box that offers a choice holds the turn end (codec v144); an
# optional one stands beside it (codec v146, OQ-095 (2))
# ---------------------------------------------------------------------------

SURGEON = "imperium:tleilaxu_surgeon:0"
MASTER = "imperium:tleilaxu_master:0"
DIPLOMACY = next(card for card in STARTERS if "diplomacy:0" in card)
# The first research column with a genetic marker [Immortality p. 6].
FIRST_MARKER_SPACE = "c4r2"
FINISH = DomainAction("finish_agent_turn", 0)


def _settle_space(state: GameState) -> GameState:
    """Resolve the visited space's own effects and its Faction Influence."""

    while True:
        legal = ENGINE.whole_actions(state, 0)
        rows = [
            action
            for action in legal
            if action.action_id in ("resolve_board_effect", "resolve_faction_influence")
        ]
        if not rows:
            return state
        state = apply_whole(ENGINE, state, rows[0], legal_actions=legal).state


def _place_alone(state: GameState, card_id: str, space_id: str) -> GameState:
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is not True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    return apply_placement(ENGINE, state, placement).state


def test_stitched_horror_holds_the_turn_end_until_it_names_two() -> None:
    """Stitched Horror's box is "Choose two" of water, troop, trash and
    Tleilaxu (docs/rules/immortality.md, slice 5c-1), named before either
    resolves (OQ-057 (4)). It has no arrow and no condition, so it is a
    mandatory effect that can always resolve: "'턴 종료'는 의무 효과가 모두
    끝났을 때만 제시된다" (OQ-095 2), and a mandatory box fizzles at the end
    only when "turn이 끝날 때까지 불가능할 때만" (OQ-057 (1)). Before codec
    v144 the dry run behind the turn end tried the box's generic resolution,
    which a choice box does not take, read it as unavailable, and offered
    the end beside the four rewards; the press then fizzled the box with no
    reward (water, garrison and Tleilaxu unchanged)."""

    state = _settle_space(
        _graft(_state((HORROR, DAGGER), troops_supply=9), HORROR, "arrakeen", DAGGER)
    )
    assert not agent_effects.agent_card_effect_is_unavailable(state)
    assert not agent_effects.graft_boxes_are_stalled(state)
    legal = ENGINE.whole_actions(state, 0)
    assert FINISH not in legal
    assert {
        dict(action.arguments)["reward"]
        for action in legal
        if action.action_id == "choose_agent_card_reward"
    } == {"water", "troop", "trash", "tleilaxu"}
    named = _apply(state, "choose_agent_card_reward", reward="water")
    assert FINISH not in ENGINE.whole_actions(named, 0)
    done = _apply(named, "choose_agent_card_reward", reward="tleilaxu")
    assert FINISH in ENGINE.whole_actions(done, 0)
    owner = done.players[0]
    before = state.players[0]
    assert owner.resources.water == before.resources.water + 1
    assert owner.tleilaxu_space == before.tleilaxu_space + 1
    finished = apply_whole(ENGINE, done, FINISH)
    assert "agent_card_effect_unavailable" not in {
        event.kind for event in finished.events
    }


def test_ghola_s_copy_of_stitched_horror_holds_the_turn_end_too() -> None:
    """Ghola's copy is a box of its own (OQ-057 (12)): once Stitched Horror
    names its two, the copy's "Choose two" still holds the end."""

    state = _settle_space(
        _graft(_state((HORROR, GHOLA), troops_supply=9), HORROR, "arrakeen", GHOLA)
    )
    assert FINISH not in ENGINE.whole_actions(state, 0)
    first = _apply(state, "choose_agent_card_reward", reward="water")
    horror_done = _apply(first, "choose_agent_card_reward", reward="troop")
    assert _boxes_offered(horror_done, "choose_agent_card_reward") == {1}
    assert FINISH not in ENGINE.whole_actions(horror_done, 0)
    copy_first = _apply(horror_done, "choose_agent_card_reward", box=1, reward="water")
    both_done = _apply(copy_first, "choose_agent_card_reward", box=1, reward="tleilaxu")
    assert FINISH in ENGINE.whole_actions(both_done, 0)


def _arrow_box(case: str) -> GameState:
    if case == "piter":
        return _settle_space(
            _place_alone(_state((PITER, DAGGER)), PITER, "accept_contract")
        )
    if case == "piter_no_unit":
        return _settle_space(
            _place_alone(
                _state((PITER, DAGGER), troops_garrison=0, troops_supply=12),
                PITER,
                "accept_contract",
            )
        )
    if case == "surgeon":
        return _settle_space(
            _place_alone(
                _state((SURGEON, DAGGER), specimens=2, troops_supply=7),
                SURGEON,
                "dutiful_service",
            )
        )
    if case == "surgeon_one_specimen":
        return _settle_space(
            _place_alone(
                _state((SURGEON, DAGGER), specimens=1, troops_supply=8),
                SURGEON,
                "dutiful_service",
            )
        )
    if case == "tleilaxu_master":
        return _settle_space(
            _place_alone(
                _state((MASTER, DAGGER), research_space=FIRST_MARKER_SPACE),
                MASTER,
                "accept_contract",
            )
        )
    assert case == "dissecting_kit"
    return _settle_space(
        _graft(_state((DISSECTING, DAGGER)), DISSECTING, "arrakeen", DAGGER)
    )


_REFUSALS = {"decline_agent_card_payment", "decline_agent_card_acquisition"}


@pytest.mark.parametrize(
    ("case", "card", "row"),
    [
        ("piter", PITER, "lose_agent_card_troop"),
        ("surgeon", SURGEON, "pay_agent_card_two_specimens"),
        ("dissecting_kit", DISSECTING, "trash_grafted_card_for_specimen"),
        ("tleilaxu_master", MASTER, "acquire_imperium_by_card"),
    ],
)
def test_an_optional_box_with_a_choice_stands_beside_the_turn_end(
    case: str, card: str, row: str
) -> None:
    """Effects are mandatory unless they say "may", pay an arrow's cost or
    show the black trash icon [FAQ p. 3] (docs/rules/official-rulings-
    index.md). Piter's "Lose a troop -> draw two cards and Research",
    Tleilaxu Surgeon's "2 specimens -> Tleilaxu Tleilaxu", Dissecting Kit's
    "Trash the other grafted card -> a specimen" and Tleilaxu Master's
    "[one genetic marker]: you may acquire a card costing 6 or less" are
    optional. User ruling 2026-10-14 (OQ-095 (2)): an optional box offers
    its rows without a refusal, holds no turn end back, and the owner's
    press lapses it (``agent_card_effect_lapsed``). Codec v144 had made
    these boxes hold the end until paid or refused; before v144 the end's
    dry run misread them as unavailable. The box still can resolve, so it
    is not one that only fizzles."""

    state = _arrow_box(case)
    legal = ENGINE.whole_actions(state, 0)
    offered = {action.action_id for action in legal}
    assert row in offered
    assert not offered & _REFUSALS
    assert FINISH in legal
    assert not agent_effects.agent_card_effect_is_unavailable(state)
    finished = apply_whole(ENGINE, state, FINISH)
    assert [
        dict(event.payload)
        for event in finished.events
        if event.kind == "agent_card_effect_lapsed"
    ] == [{"card_id": card, "player": 0}]


@pytest.mark.parametrize(
    ("case", "card"),
    [("piter_no_unit", PITER), ("surgeon_one_specimen", SURGEON)],
)
def test_an_arrow_whose_cost_cannot_be_paid_still_lets_the_turn_end(
    case: str, card: str
) -> None:
    """With no unit to lose (Piter) or one specimen short of two (Tleilaxu
    Surgeon) the box's effect cannot happen this turn (OQ-057 (1)). Since
    the user ruling of 2026-10-14 (OQ-095 (2)) the optional box offers no
    row at all -- before codec v146 it offered only its refusal -- and the
    turn end lapses it, with nothing gained."""

    state = _arrow_box(case)
    legal = ENGINE.whole_actions(state, 0)
    assert not {action.action_id for action in legal} & _REFUSALS
    assert agent_effects.agent_card_effect_is_unavailable(state)
    assert FINISH in legal
    finished = apply_whole(ENGINE, state, FINISH)
    assert [
        dict(event.payload)
        for event in finished.events
        if event.kind == "agent_card_effect_lapsed"
    ] == [{"card_id": card, "player": 0}]
    owner, before = finished.state.players[0], state.players[0]
    assert (owner.troops_garrison, owner.specimens, owner.tleilaxu_space) == (
        before.troops_garrison,
        before.specimens,
        before.tleilaxu_space,
    )


def test_beguiling_pheromones_holds_the_turn_end_on_a_faction_space() -> None:
    """Beguiling Pheromones' "trash one of the grafted cards and gain an
    additional Influence" has no "may", arrow or black trash icon, so it is
    mandatory [FAQ p. 3] (``legal_agent_card_payment_actions``): on a
    Faction space it can resolve, so the turn end waits for the trash
    (OQ-095 2, OQ-057 (1)). Before codec v144 the end was offered beside
    the trash and the press fizzled the box."""

    state = _settle_space(
        _graft(_state((DIPLOMACY, PHEROMONES)), DIPLOMACY, "secrets", PHEROMONES)
    )
    legal = ENGINE.whole_actions(state, 0)
    assert FINISH not in legal
    assert _boxes_offered(state, "trash_grafted_card_for_influence") == {1}
    trashed = _apply(
        state, "trash_grafted_card_for_influence", box=1, card_id=PHEROMONES
    )
    assert trashed.players[0].influence.bene_gesserit == (
        state.players[0].influence.bene_gesserit + 1
    )
    assert FINISH in ENGINE.whole_actions(trashed, 0)


def test_dissecting_kit_without_its_partner_in_play_can_only_fizzle() -> None:
    """With no other grafted card in play Dissecting Kit's box offers
    nothing ("without a partner still in play the box does nothing",
    ``legal_agent_card_payment_actions``), so it is one that only fizzles
    and the turn end stays offered (OQ-057 (1))."""

    state = _graft(_state((DISSECTING, DAGGER)), DISSECTING, "arrakeen", DAGGER)
    owner = state.players[0]
    gone = replace(
        state,
        players=(
            replace(
                owner,
                in_play=tuple(card for card in owner.in_play if card != DAGGER),
                trashed=(*owner.trashed, DAGGER),
            ),
            *state.players[1:],
        ),
    )
    assert agent_effects.agent_card_effect_is_unavailable(gone)
    assert agent_effects.graft_boxes_are_stalled(_settle_space(gone))
    assert FINISH in ENGINE.whole_actions(_settle_space(gone), 0)


def test_ghola_s_copy_of_corrinth_city_picks_its_own_first_discard() -> None:
    """Ghola "copies the entire Agent box of the card it's grafted to"
    [Immortality p. 14]: the copy is a box of its own (OQ-057 (12)).
    Corrinth City selects its first discard and declines -- the refusal
    stays part way through the selection while the copy waits, so the
    owner can turn to it (OQ-095 (2), user ruling 2026-10-14); the copy
    then selects its own first discard, offered without a refusal like any
    optional box not yet begun (codec v146). Before codec v143 the two
    boxes shared the selection, so the copy could only pay with the first
    box's card."""

    other = next(card for card in STARTERS if card != DAGGER)
    state = _state((CORRINTH, GHOLA, DAGGER, other), troops_supply=9)
    owner = state.players[0]
    state = replace(
        state,
        players=(
            replace(owner, resources=replace(owner.resources, solari=12)),
            *state.players[1:],
        ),
    )
    state = _graft(state, CORRINTH, "assembly_hall", GHOLA)
    hand = state.players[0].hand
    assert len(hand) >= 2
    selected = _apply(state, "select_corrinth_city_discard", card_id=hand[0])
    declined = _apply(selected, "decline_corrinth_city_payment")
    copy_rows = {
        (action.action_id, dict(action.arguments).get("card_id"))
        for action in ENGINE.whole_actions(declined, 0)
        if row_box(action) == 1
    }
    assert copy_rows == {("select_corrinth_city_discard", card) for card in hand}


def test_box_one_s_own_card_draw_leaves_the_placed_card_s_added_draw() -> None:
    """Urgent Shigawire adds its draw to the boosted card's box: the placed
    Planned Coupling, box 0 (Tleilaxu Infiltrator, box 1, is no Bene
    Gesserit card, OQ-107). Box 0 prints no card-draw icon, so the untagged
    ``effect=cards`` is the added draw; box 1's is its own icon and leaves
    the added draw waiting (OQ-106 1)."""

    state = _graft(
        _state((COUPLING, INFILTRATOR), bene_gesserit_boost_pending=True),
        COUPLING,
        "arrakeen",
        INFILTRATOR,
    )
    _, context = current_agent_effect_context(state)
    assert context["boost_draw_card_ids"] == COUPLING
    rows = ENGINE.whole_actions(state, 0)
    cards = (("effect", "cards"),)
    assert DomainAction("resolve_agent_card_effect", 0, cards) in rows
    assert (
        DomainAction("resolve_agent_card_effect", 0, (("box", 1), *cards)) in rows
    )
    partner = apply_whole(ENGINE, 
        state, DomainAction("resolve_agent_card_effect", 0, (("box", 1), *cards))
    ).state
    _, context = current_agent_effect_context(partner)
    assert context["boost_draw_card_ids"] == COUPLING
    assert context["card_id"] == INFILTRATOR
    assert "cards" not in str(context["pending_agent_icons"])
    added = apply_whole(ENGINE, 
        partner, DomainAction("resolve_agent_card_effect", 0, cards)
    ).state
    _, context = current_agent_effect_context(added)
    assert "boost_draw_card_ids" not in context
    assert len(added.players[0].hand) == len(partner.players[0].hand) + 1


def test_the_codec_holds_box_one_twins_in_immortality_catalogs_only() -> None:
    plain = ActionCodec(RulesetConfig(choam_module=True, bloodlines=True))
    assert not any(
        ("box", 1) in template.arguments for template in plain.catalog
    )
    # v147 added the base catalog's ``source``-named Reveal rows (+140); v150
    # (stage B1) replaced the base catalog's 1,763 ``agent_turn`` rows with
    # 129 card and space picks (4,551 - 1,763 + 129); v150 (stage B2, OQ-112)
    # added a Conflict reward's 14 icon rows; v150 (stage B3a, OQ-111) traded
    # 792 whole templates for the 964 effect and target rows that stand for
    # them in the Agent-effect frame; v150 (stage B3b-2, OQ-111) traded 146
    # more for the 28 rows of the Reveal frame's effects, stage B3c-1 73 for
    # the 26 rows of played cards, stage B3d-1 228 for the 68 rows of the
    # windows that offer several effects at once, stage B3d-2a 1,466 for the
    # 54 rows of the windows opened for one effect, stage B3d-3 37 whole
    # refusal templates (five of them ids no handler ever answered) for the
    # 100 ``decline`` / ``confirm_empty`` rows that name the effect they answer;
    # v150 (stage B3d-4): the turn's owed draws and Emperor track Spy go by
    # their effect rows (draw_owed_intrigue and place_track_spy leave, four
    # rows join); v150 (stage B3e-1): a Reveal gain goes by the entity that
    # printed it (the 13 whole templates of the seven gain ids leave, the 16
    # rows naming their printers join).
    assert ActionCodec(RulesetConfig()).size == (
        2917
        + 14
        + (964 - 792)
        + (28 - 146)
        + (26 - 73)
        + (68 - 228)
        + (54 - 1466)
        + (100 - 37)
        + (4 - 2)
        + (16 - 13)
        # v154 (OQ-113 (C)): Manipulate's set-aside with an empty Imperium Row
        # is confirmed by a row of its own (skip_intrigue_set_aside).
        + 1
        # v155 (OQ-138): Covert Operation's confirm of an empty hand
        # (resolve_opponent_discard_without_card).
        + 1
    )
    codec = ActionCodec(IMMORTALITY)
    templates = set(codec.catalog)
    twins = {t for t in codec.catalog if ("box", 1) in t.arguments}
    assert twins
    # Stage B3a: a box's effect is offered as a row naming its source (the
    # card or, for a Signet Ring box, the leader), the box number in the row;
    # the actions the frame still offers as they are keep their ids.
    assert all(
        t.action_id in BOX_ACTION_IDS
        or dict(t.arguments).get("source") in {"agent_card", "leader"}
        for t in twins
    )
    # An opponent's window names the card that opened it, whichever box
    # resolved it (``effect_steps.Printed.WINDOW``), so Covert Operation's
    # confirm of an empty hand (OQ-138, codec v155) has no box 1 twin, as
    # Holy War's confirm of no unit has none.
    window_rows = {
        ActionTemplate(row.action_id, row.arguments)
        for card in ("covert_operation", "ghola")
        for row in steps_for(
            DomainAction("resolve_opponent_discard_without_card", 1),
            card,
            Source.AGENT_CARD,
        )
    }
    assert window_rows <= templates
    for template in codec.catalog:
        is_box_effect = dict(template.arguments).get("source") == "agent_card"
        if (
            (template.action_id in BOX_ACTION_IDS or is_box_effect)
            and template not in twins
            and template not in window_rows
        ):
            twin = ActionTemplate(
                template.action_id,
                tuple(sorted((*template.arguments, ("box", 1)))),
            )
            assert twin in templates
    assert "switch_graft_card" not in {t.action_id for t in codec.catalog}


FIRM_GRIP = "imperium:firm_grip:0"


def test_a_grafted_firm_grip_pays_its_solari_arrow_in_either_box() -> None:
    """Grafted cards give both their effects: "두 카드의 효과를 board space
    효과와 함께 원하는 순서로 얻는다" [Immortality p. 10] (immortality.md 5).
    The original game's Firm Grip ("[2 Solari] -> +1 Influence with the
    Spacing Guild, the Bene Gesserit or the Fremen", stage P3) as Ghola's
    partner offers its arrow in box 1, and Ghola's copy of it in box 0; each
    box pays its own 2 Solari and names its own Faction. The engine's state
    puts the original card in an Uprising + Immortality hand: the original
    game takes Immortality from stage P7, the rows are the same."""

    state = _graft(_state((GHOLA, FIRM_GRIP)), GHOLA, "arrakeen", FIRM_GRIP)
    assert _boxes_offered(state, "pay_agent_card_solari") == {0, 1}
    # The staged rows were always in the original + Immortality catalog; the
    # effect frame refused the box 1 action until it joined BOX_ACTION_IDS.
    original = ActionCodec(
        RulesetConfig(base_game=BaseGame.IMPERIUM, immortality=True)
    )
    for row in ENGINE.legal_actions(state, 0):
        if dict(row.arguments).get("printed") == "firm_grip":
            assert original.decode(original.encode(row), 0) == row
    paid = _apply(state, "pay_agent_card_solari", box=1)
    assert paid.players[0].resources.solari == 4 - 2
    chosen = _apply(paid, "choose_agent_card_influence", box=1, faction="fremen")
    assert chosen.players[0].influence.fremen == state.players[0].influence.fremen + 1
    assert _boxes_offered(chosen, "pay_agent_card_solari") == {0}
    again = _apply(chosen, "pay_agent_card_solari")
    assert again.players[0].resources.solari == 0


def test_ghola_s_copy_of_tread_in_darkness_counts_tread_for_the_bond() -> None:
    """immortality.md 5, [Immortality p. 14]: "Bene Gesserit 카드에 graft하면 그
    카드의 'BG 카드가 play 중이면' 조건은 그 카드 자신을 세지만 Ghola 자체는 BG
    카드가 아니다". Ghola's copy of Tread in Darkness's box has its Bond in
    Tread itself, so the copy's trash and draw are offered; Tread's own box
    needs another Bene Gesserit card, which Ghola is not, so it offers none
    (each icon judged when it resolves, OQ-028)."""

    tread = "imperium:tread_in_darkness:0"
    state = _graft(_state((GHOLA, tread)), GHOLA, "arrakeen", tread)
    assert _boxes_offered(state, "resolve_agent_card_effect") == {0}
    assert _boxes_offered(state, "trash_agent_card") == {0}


def test_the_observation_names_both_boxes_by_their_fixed_number() -> None:
    """Observation v31 (plan 4.7): box 0 the placed card, box 1 the partner,
    each with its pending flag, whichever box the frame holds in
    ``card_id``; public, like the cards in play."""

    state = _graft(_state((GHOLA, TANKS), troops_supply=9), GHOLA, "arrakeen", TANKS)
    assert ENGINE.observe(state, 1).agent_boxes == ((GHOLA, True), (TANKS, True))
    partner_first = _apply(state, "resolve_agent_card_effect", box=1)
    assert ENGINE.observe(partner_first, 2).agent_boxes == (
        (GHOLA, True),
        (TANKS, False),
    )
    boxes = encode_player_view(ENGINE.observe(partner_first, 0))[
        segment_slice("agent_boxes")
    ]
    assert boxes == (
        PERSONAL_CARD_IDS.index("ghola") + 1,
        PERSONAL_CARD_IDS.index("from_the_tanks") + 1,
        1,
        0,
    )


# Urgent Shigawire and a Bene Gesserit graft partner (OQ-107, codec v144)
# ---------------------------------------------------------------------------
#
# "The next Bene Gesserit card you play this round has all Agent icons and,
# added to its Agent box: draw a card." [Urgent Shigawire card]. A graft
# plays two cards -- "You must play two cards (and only two) on that turn"
# [Immortality p. 10] -- and "Both played cards are considered to have
# “sent” the Agent, no matter which card’s icon you use." [Immortality p.
# 10]. User ruling 2026-10-12 (OQ-107): "1. 짝도 받음" -- the partner is a
# card played, so a Bene Gesserit partner takes a boost still pending: its
# box gets the added draw (``box=1``) and the boost is spent. With two Bene
# Gesserit cards the placed one takes it.

TRUTHTRANCE = "imperium:truthtrance:0"
USURP = "tleilaxu:usurp:0"
CARDS = (("effect", "cards"),)
BOX_ZERO_DRAW = DomainAction("resolve_agent_card_effect", 0, CARDS)
PARTNER_DRAW = DomainAction("resolve_agent_card_effect", 0, (("box", 1), *CARDS))


def _placed(state: GameState, card_id: str, space_id: str) -> GameState:
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    return apply_placement(ENGINE, state, placement).state


def _choose_partner(state: GameState, partner: str) -> Transition:
    return apply_whole(ENGINE, 
        state, DomainAction("choose_graft_partner", 0, (("card_id", partner),))
    )


def _boost_consumed(result: Transition) -> list[object]:
    return [
        dict(event.payload)["card_id"]
        for event in result.events
        if event.kind == "agent_card_boost_consumed"
    ]


def test_a_bene_gesserit_partner_takes_the_boost_and_its_draw() -> None:
    """Tleilaxu Infiltrator (no Bene Gesserit card) is placed; Truthtrance
    (Bene Gesserit, no Agent box of its own) is its partner, so Truthtrance
    is "the next Bene Gesserit card you play": the boost is spent on it and
    its box, box 1, gets the added draw. The placed card's own card-draw
    icon stays its own (untagged); the turn end waits for the added draw;
    the boost is not carried to a later Bene Gesserit card."""

    placed = _placed(
        _state((INFILTRATOR, TRUTHTRANCE), bene_gesserit_boost_pending=True),
        INFILTRATOR,
        "arrakeen",
    )
    assert placed.players[0].bene_gesserit_boost_pending is True
    grafted = _choose_partner(placed, TRUTHTRANCE)
    assert _boost_consumed(grafted) == [TRUTHTRANCE]
    state = grafted.state
    owner = state.players[0]
    assert owner.bene_gesserit_boost_pending is False
    _, context = current_agent_effect_context(state)
    assert context["boost_draw_card_ids"] == TRUTHTRANCE
    legal = ENGINE.whole_actions(state, 0)
    assert PARTNER_DRAW in legal and BOX_ZERO_DRAW in legal
    assert agent_effects.resolves_boost_draw(state, PARTNER_DRAW)
    assert not agent_effects.resolves_boost_draw(state, BOX_ZERO_DRAW)
    assert FINISH not in legal

    drawn = apply_whole(ENGINE, state, PARTNER_DRAW)
    assert len(drawn.state.players[0].hand) == len(owner.hand) + 1
    assert any(
        event.kind == "agent_card_effect_resolved"
        and dict(event.payload)["card_id"] == TRUTHTRANCE
        for event in drawn.events
    )
    _, context = current_agent_effect_context(drawn.state)
    assert "boost_draw_card_ids" not in context
    # The draw is bound to its card: no box was made active for it.
    assert context["card_id"] == INFILTRATOR
    later = drawn.state
    assert PARTNER_DRAW not in ENGINE.whole_actions(later, 0)
    # Infiltrator's own card-draw icon is still box 0's to take.
    assert BOX_ZERO_DRAW in ENGINE.whole_actions(later, 0)
    # Spent: a Bene Gesserit card played later this round is not boosted.
    assert not card_is_boosted(
        personal_card_for_instance(COUPLING), later.players[0]
    )


def test_a_usurp_partner_from_the_row_takes_the_boost() -> None:
    """Usurp has no icons of its own; a boosted Bene Gesserit Row partner's
    "all Agent icons" send the Agent ("You may use an Agent icon from either
    card" [Immortality p. 10]), here to Arrakeen, which no candidate's
    printed icons reach. Before codec v144 Usurp's placement read only the
    candidates' printed icons, so the boosted partner's reach counted only
    where another candidate's printed icon opened the space. That partner
    is a card played, so it also spends the boost and gets the added draw
    in its box."""

    base = _state((USURP, DAGGER), bene_gesserit_boost_pending=True)
    # No other Row card (nor Dagger) prints a City icon or is Bene Gesserit.
    row = (
        TRUTHTRANCE,
        "imperium:captured_mentat:0",
        CORRINTH,
        "imperium:desert_power:0",
        "imperium:desert_survival:0",
    )
    base = replace(
        base,
        imperium_row=row,
        imperium_deck=tuple(
            card
            for card in (*base.imperium_row, *base.imperium_deck)
            if card not in row
        ),
    )
    unboosted = replace(
        base,
        players=(
            replace(base.players[0], bene_gesserit_boost_pending=False),
            *base.players[1:],
        ),
    )
    assert "arrakeen" not in _spaces_offered(unboosted, USURP)
    placed = _placed(base, USURP, "arrakeen")
    assert {
        dict(action.arguments)["card_id"]
        for action in ENGINE.whole_actions(placed, 0)
        if action.action_id == "choose_graft_partner"
    } == {TRUTHTRANCE}
    grafted = _choose_partner(placed, TRUTHTRANCE)
    assert _boost_consumed(grafted) == [TRUTHTRANCE]
    state = grafted.state
    assert state.players[0].bene_gesserit_boost_pending is False
    assert state.players[0].usurped_row_card_id == TRUTHTRANCE
    state = _settle_space(state)
    assert FINISH not in ENGINE.whole_actions(state, 0)
    drawn = apply_whole(ENGINE, state, PARTNER_DRAW).state
    assert len(drawn.players[0].hand) == len(state.players[0].hand) + 1
    assert FINISH in ENGINE.whole_actions(drawn, 0)


def test_with_two_bene_gesserit_cards_the_placed_one_takes_the_boost() -> None:
    """Planned Coupling (Bene Gesserit) is placed first and spends the boost
    at its placement; its Bene Gesserit partner finds none left."""

    placed = _placed(
        _state((COUPLING, TRUTHTRANCE), bene_gesserit_boost_pending=True),
        COUPLING,
        "arrakeen",
    )
    assert placed.players[0].bene_gesserit_boost_pending is False
    grafted = _choose_partner(placed, TRUTHTRANCE)
    assert _boost_consumed(grafted) == []
    _, context = current_agent_effect_context(grafted.state)
    assert context["boost_draw_card_ids"] == COUPLING
    legal = ENGINE.whole_actions(grafted.state, 0)
    assert PARTNER_DRAW not in legal
    assert BOX_ZERO_DRAW in legal
    assert agent_effects.resolves_boost_draw(grafted.state, BOX_ZERO_DRAW)


def test_a_partner_that_is_not_bene_gesserit_leaves_the_boost_pending() -> None:
    grafted = _choose_partner(
        _placed(
            _state((INFILTRATOR, DAGGER), bene_gesserit_boost_pending=True),
            INFILTRATOR,
            "arrakeen",
        ),
        DAGGER,
    )
    assert _boost_consumed(grafted) == []
    assert grafted.state.players[0].bene_gesserit_boost_pending is True
    _, context = current_agent_effect_context(grafted.state)
    assert "boost_draw_card_ids" not in context
    assert PARTNER_DRAW not in ENGINE.whole_actions(grafted.state, 0)


def test_a_partner_s_added_draw_lapses_when_another_effect_trashes_it() -> None:
    """The draw was "added to its Agent box" [Urgent Shigawire card]: when
    Dissecting Kit (box 0) trashes the boosted partner first, the partner's
    box and the added draw expire with it -- "you can't receive or activate
    an effect from a card that is already trashed" (OQ-022 designer ruling;
    OQ-106 1). Taken first, the draw stands and the trash still follows."""

    state = _choose_partner(
        _placed(
            _state((DISSECTING, TRUTHTRANCE), bene_gesserit_boost_pending=True),
            DISSECTING,
            "arrakeen",
        ),
        TRUTHTRANCE,
    ).state
    trash = DomainAction("trash_grafted_card_for_specimen", 0)
    assert PARTNER_DRAW in ENGINE.whole_actions(state, 0)

    trashed = apply_whole(ENGINE, state, trash)
    assert any(
        event.kind == "agent_card_effect_expired"
        and dict(event.payload)["card_id"] == TRUTHTRANCE
        for event in trashed.events
    )
    _, context = current_agent_effect_context(trashed.state)
    assert "boost_draw_card_ids" not in context
    assert PARTNER_DRAW not in ENGINE.whole_actions(trashed.state, 0)
    assert trashed.state.players[0].hand == state.players[0].hand

    drawn_first = apply_whole(ENGINE, state, PARTNER_DRAW).state
    assert len(drawn_first.players[0].hand) == len(state.players[0].hand) + 1
    after = apply_whole(ENGINE, drawn_first, trash).state
    assert TRUTHTRANCE in after.players[0].trashed


# A Ghola grafted to the boosted card (user ruling 2026-10-12, codec v145):
# "Ghola copies the entire Agent box of the card it's grafted to"
# [Immortality p. 14] and the draw was "added to its Agent box" [Urgent
# Shigawire card], so Ghola's copy draws a card too -- "그럼 부스트 받은거까지
# 복사되는게 맞는거 아니야?" -> "그래 고치자". Ghola itself is no Bene
# Gesserit card [Immortality p. 14] and never takes the boost.


def _drawn(result: Transition) -> list[object]:
    return [
        dict(event.payload)["card_id"]
        for event in result.events
        if event.kind == "agent_card_effect_resolved"
        and dict(event.payload).get("effect") == "cards"
    ]


def test_a_ghola_partner_copies_the_placed_card_s_added_draw() -> None:
    """Planned Coupling (Bene Gesserit, no card-draw icon of its own) is
    placed and spends the boost; Ghola, its partner, copies its box with
    the added draw, so box 0 and box 1 each draw a card, and the turn end
    waits for both."""

    state = _graft(
        _state((COUPLING, GHOLA), bene_gesserit_boost_pending=True),
        COUPLING,
        "arrakeen",
        GHOLA,
    )
    _, context = current_agent_effect_context(state)
    assert effects.pending_boost_draws(context) == (COUPLING, GHOLA)
    assert agent_effects.resolves_boost_draw(state, BOX_ZERO_DRAW)
    assert agent_effects.resolves_boost_draw(state, PARTNER_DRAW)
    state = _settle_space(state)
    hand = len(state.players[0].hand)

    copy = apply_whole(ENGINE, state, PARTNER_DRAW)
    assert _drawn(copy) == [GHOLA]
    assert FINISH not in ENGINE.whole_actions(copy.state, 0)
    assert PARTNER_DRAW not in ENGINE.whole_actions(copy.state, 0)
    added = apply_whole(ENGINE, copy.state, BOX_ZERO_DRAW)
    assert _drawn(added) == [COUPLING]
    assert len(added.state.players[0].hand) == hand + 2
    _, context = current_agent_effect_context(added.state)
    assert effects.BOOST_DRAW_KEY not in context


def test_a_placed_ghola_copies_its_boosted_partner_s_draw() -> None:
    """Ghola is placed; Truthtrance (Bene Gesserit, no Agent box of its own)
    is its partner and takes the boost (OQ-107), so its box 1 holds the
    added draw -- and Ghola's box 0, a copy of it, holds one too."""

    placed = _placed(
        _state((GHOLA, TRUTHTRANCE), bene_gesserit_boost_pending=True),
        GHOLA,
        "arrakeen",
    )
    assert placed.players[0].bene_gesserit_boost_pending is True
    grafted = _choose_partner(placed, TRUTHTRANCE)
    assert _boost_consumed(grafted) == [TRUTHTRANCE]
    state = grafted.state
    _, context = current_agent_effect_context(state)
    assert effects.pending_boost_draws(context) == (TRUTHTRANCE, GHOLA)
    state = _settle_space(state)
    hand = len(state.players[0].hand)
    assert FINISH not in ENGINE.whole_actions(state, 0)

    ghola = apply_whole(ENGINE, state, BOX_ZERO_DRAW)
    assert _drawn(ghola) == [GHOLA]
    partner = apply_whole(ENGINE, ghola.state, PARTNER_DRAW)
    assert _drawn(partner) == [TRUTHTRANCE]
    assert len(partner.state.players[0].hand) == hand + 2
    assert FINISH in ENGINE.whole_actions(partner.state, 0)


THRONE = "imperium:throne_room_politics:0"
BOX_ZERO = DomainAction("resolve_agent_card_effect", 0)
BOX_ONE = DomainAction("resolve_agent_card_effect", 0, (("box", 1),))


def _trash(card_id: str, printed: str, box: int = 0) -> DomainAction:
    """The waiting optional trash of ``printed``'s box (``box`` 1 for the
    graft partner) trashing ``card_id`` (stage B3c-2b: the row names the
    trash icon)."""

    return DomainAction(
        "trash_optional_card",
        0,
        tuple(
            sorted(
                (
                    ("card_id", card_id),
                    ("printed", printed),
                    ("source", "agent_card"),
                    *((("printed_box", 1),) if box else ()),
                )
            )
        ),
    )


def _expired(result: Transition) -> list[object]:
    return [
        dict(event.payload)["card_id"]
        for event in result.events
        if event.kind == "agent_card_effect_expired"
    ]


def test_throne_room_politics_trashing_itself_keeps_its_added_draw() -> None:
    """Throne Room Politics (Bene Gesserit) recruits and opens its optional
    trash icon; picking the card itself there is the card leaving play by
    its own icon, so the draw "added to its Agent box" still pays out --
    "카드가 자기 효과로 자신을 trash하는 경우 인쇄된 이득은 정상 지급"
    (OQ-022 designer ruling, OQ-106 1). Before this the trash lapsed it."""

    state = _place_alone(
        _state((THRONE,), bene_gesserit_boost_pending=True), THRONE, "arrakeen"
    )
    boxed = apply_whole(ENGINE, state, BOX_ZERO).state
    trashed = apply_whole(ENGINE, boxed, _trash(THRONE, "throne_room_politics"))
    assert THRONE in trashed.state.players[0].trashed
    assert _expired(trashed) == []
    assert agent_effects.resolves_boost_draw(trashed.state, BOX_ZERO_DRAW)
    drawn = apply_whole(ENGINE, trashed.state, BOX_ZERO_DRAW)
    assert _drawn(drawn) == [THRONE]


def test_a_ghola_copy_s_draw_lapses_only_with_ghola() -> None:
    """Throne Room Politics, boosted, is placed with Ghola, which copies its
    box with the added draw. Ghola's copied trash icon trashing Ghola is
    Ghola's own icon: its draw stays. The same icon trashing Throne Room
    Politics is another card's effect: Throne Room Politics' draw lapses
    with it (OQ-022), Ghola's stays. Without a boost Ghola's copy has no
    added draw."""

    state = _graft(
        _state((THRONE, GHOLA), bene_gesserit_boost_pending=True),
        THRONE,
        "arrakeen",
        GHOLA,
    )
    _, context = current_agent_effect_context(state)
    assert effects.pending_boost_draws(context) == (THRONE, GHOLA)
    copy = apply_whole(ENGINE, state, BOX_ONE).state

    # Ghola's copied trash icon is box 1's, printed on Ghola.
    own = apply_whole(ENGINE, copy, _trash(GHOLA, "ghola", 1))
    assert _expired(own) == []
    _, context = current_agent_effect_context(own.state)
    assert effects.pending_boost_draws(context) == (THRONE, GHOLA)

    other = apply_whole(ENGINE, copy, _trash(THRONE, "ghola", 1))
    assert _expired(other) == [THRONE]
    _, context = current_agent_effect_context(other.state)
    assert effects.pending_boost_draws(context) == (GHOLA,)
    assert agent_effects.resolves_boost_draw(other.state, PARTNER_DRAW)
    assert not agent_effects.resolves_boost_draw(other.state, BOX_ZERO_DRAW)

    plain = _graft(_state((GHOLA, COUPLING)), GHOLA, "arrakeen", COUPLING)
    _, context = current_agent_effect_context(plain)
    assert effects.pending_boost_draws(context) == ()
    assert not agent_effects.resolves_boost_draw(plain, BOX_ZERO_DRAW)
    assert not agent_effects.resolves_boost_draw(plain, PARTNER_DRAW)
