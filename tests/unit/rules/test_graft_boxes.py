"""The box-scoped keys of a grafted Agent turn (docs/graft-boxes-plan.md 4.2).

"You gain the effects on both cards, in addition to the board space
effects, in any order you choose." [Immortality pp. 10-11]. Each key of the
Agent-turn effect frame is one box's, a card's, or the turn's
(``rules.graft_boxes``); swapping the boxes must move every box-scoped key,
so these tests keep a new key from riding along unclassified.
"""

import ast
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import RandomAgent
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
from dune_imperium.rules import (
    UprisingRulesEngine,
    agent_effects,
    combat_deployment,
    effects,
    frames,
    leader_abilities,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft_boxes import (
    ACTIVE_BOX_KEY,
    BOX_KEY_PAIRS,
    BOX_KEYS,
    CARD_KEYS,
    TURN_KEYS,
    active_box,
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
        "choice_sword_card_ids",
        "chose",
        "chosen_factions",
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
        "deferred_factions",
        "deferred_reveal_choices",
        "exclude_space",
        "excluded_space_id",
        "granted_reveal_effects",
        "guild_spy_fired",
        "hand",
        "infiltrate_post_id",
        "intrigue_pending",
        "leader_intrigue_granted",
        "leader_persuasion_granted",
        "leader_reveal_ability_used",
        "long_live_fighters_draw_card_id",
        "occupied",
        "only_option",
        "optional_sword_strength",
        "partner_waives_influence",
        "persuasion",
        "persuasion_generated",
        "picked",
        "placed_reaches",
        "played_at_priority",
        "player",
        "purpose",
        "remaining",
        "resource",
        "reveal_card_id",
        "reveal_choice_effect",
        "reveal_choice_resumed",
        "reveal_commanders_deployed",
        "reveal_commanders_recruited",
        "reveal_pending_gains",
        "reveal_spy_recalled",
        "reveal_troops_recruited",
        "reveal_units_deployed",
        "revealed_card_count",
        "rewards_applied",
        "separate_effect",
        "shield_wall_at_play",
        "skill_reveal_granted",
        "slot",
        "source",
        "spice_must_flow_acquired",
        "step",
        "stop",
        "strength",
        "sword_strength",
        "tactics_lost",
        "tech_granted",
        "tech_reveal_pending",
        "turn_agent_in_conflict",
        "turn_start_over",
        "used",
    }
)


def _module_string_constants() -> dict[str, str]:
    constants: dict[str, str] = {}
    for path in sorted(RULES.glob("*.py")):
        for node in ast.parse(path.read_text()).body:
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
    return constants


def _context_keys_in_rules() -> dict[str, set[str]]:
    """Every string key read or written on a ``*context*`` mapping of rules/."""

    constants = _module_string_constants()
    found: dict[str, set[str]] = {}
    for path in sorted(RULES.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            base: ast.expr | None = None
            key: ast.expr | None = None
            if isinstance(node, ast.Subscript):
                base, key = node.value, node.slice
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("get", "pop", "setdefault")
                and node.args
            ):
                base, key = node.func.value, node.args[0]
            elif (
                isinstance(node, ast.Compare)
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.In | ast.NotIn)
            ):
                base, key = node.comparators[0], node.left
            if not isinstance(base, ast.Name) or "context" not in base.id:
                continue
            name: str | None = None
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                name = key.value
            elif isinstance(key, ast.Name) and key.id in constants:
                name = constants[key.id]
            if name is not None:
                found.setdefault(name, set()).add(path.name)
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
        "boost_draw_card_id": "a",
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
        "boost_draw_card_id": "a",
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
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        legal = engine.legal_actions(state, decision.owner)
        action = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), legal
        )
        state = engine.apply(state, action, legal_actions=legal).state
    assert state.phase is GamePhase.FINISHED
    assert unclassified_keys(dict.fromkeys(seen, 0)) == ()
