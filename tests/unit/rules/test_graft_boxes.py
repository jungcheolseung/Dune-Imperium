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
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.action_codec import ActionTemplate
from dune_imperium.agents import RandomAgent
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GameState,
    PlayerState,
    Resources,
)
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


def _graft(state: GameState, card_id: str, space_id: str, partner: str) -> GameState:
    placement = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments).get("graft") is True
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    placed = ENGINE.apply(state, placement).state
    choice = DomainAction(
        "choose_graft_partner", 0, arguments=(("card_id", partner),)
    )
    return ENGINE.apply(placed, choice).state


def _row(state: GameState, action_id: str, box: int = 0, **arguments: object) -> (
    DomainAction
):
    return next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == action_id
        and dict(action.arguments).get("box", 0) == box
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )


def _apply(state: GameState, action_id: str, box: int = 0, **arguments: object) -> (
    GameState
):
    return ENGINE.apply(state, _row(state, action_id, box, **arguments)).state


def _boxes_offered(state: GameState, action_id: str) -> set[int]:
    return {
        row_box(action)
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == action_id
    }


def test_both_boxes_are_offered_from_the_start_in_either_order() -> None:
    """Ghola copies From the Tanks' box, so both boxes offer the same plain
    resolution: box 0's untagged, box 1's with ``box=1``. Either may go
    first, and each resolves its own box once (no switch, no loop)."""

    state = _graft(_state((GHOLA, TANKS), troops_supply=9), GHOLA, "arrakeen", TANKS)
    assert _boxes_offered(state, "resolve_agent_card_effect") == {0, 1}
    assert "switch_graft_card" not in {
        action.action_id for action in ENGINE.legal_actions(state, 0)
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
        action.action_id for action in ENGINE.legal_actions(both, 0)
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
        for action in ENGINE.legal_actions(first, 0)
    )
    second = _apply(first, "choose_agent_card_reward", box=1, reward="troop")
    owner = second.players[0]
    assert (owner.resources.water, owner.troops_garrison) == (3, 4)
    # Box 0 (Stitched Horror) names its own two from all four.
    assert {
        dict(action.arguments)["reward"]
        for action in ENGINE.legal_actions(second, 0)
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
        ("box", 1) in action.arguments for action in ENGINE.legal_actions(paid, 0)
    )
    drew = _apply(paid, "resolve_agent_card_effect", effect="cards")
    assert not any(
        ("box", 1) in action.arguments for action in ENGINE.legal_actions(drew, 0)
    )
    researched = _apply(drew, "resolve_agent_card_effect", effect="research")
    while researched.decision_stack[-1].kind != FrameKind.AGENT_EFFECTS:
        decision = ENGINE.current_decision(researched)
        assert isinstance(decision, PlayerDecision)
        researched = ENGINE.apply(
            researched, ENGINE.legal_actions(researched, decision.owner)[0]
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
        for action in ENGINE.legal_actions(state, 0)
    ):
        state = _apply(state, "resolve_board_effect")
    assert "finish_agent_turn" in {
        action.action_id for action in ENGINE.legal_actions(state, 0)
    }
    finished = ENGINE.apply(state, DomainAction("finish_agent_turn", 0))
    assert "agent_card_effect_unavailable" in {
        event.kind for event in finished.events
    }
    assert finished.state.decision_stack[-1].kind == FrameKind.TURN


def test_box_one_s_card_draw_is_never_urgent_shigawire_s() -> None:
    """Urgent Shigawire adds its draw to the boosted card's box: the placed
    Planned Coupling, box 0. Box 0 prints no card-draw icon, so the untagged
    ``effect=cards`` is the added draw; box 1's (Tleilaxu Infiltrator's) is
    its own icon and leaves the added draw waiting (OQ-106 1)."""

    state = _graft(
        _state((COUPLING, INFILTRATOR), bene_gesserit_boost_pending=True),
        COUPLING,
        "arrakeen",
        INFILTRATOR,
    )
    _, context = current_agent_effect_context(state)
    assert context["boost_draw_card_id"] == COUPLING
    rows = ENGINE.legal_actions(state, 0)
    cards = (("effect", "cards"),)
    assert DomainAction("resolve_agent_card_effect", 0, cards) in rows
    assert (
        DomainAction("resolve_agent_card_effect", 0, (("box", 1), *cards)) in rows
    )
    partner = ENGINE.apply(
        state, DomainAction("resolve_agent_card_effect", 0, (("box", 1), *cards))
    ).state
    _, context = current_agent_effect_context(partner)
    assert context["boost_draw_card_id"] == COUPLING
    assert context["card_id"] == INFILTRATOR
    assert "cards" not in str(context["pending_agent_icons"])
    added = ENGINE.apply(
        partner, DomainAction("resolve_agent_card_effect", 0, cards)
    ).state
    _, context = current_agent_effect_context(added)
    assert "boost_draw_card_id" not in context
    assert len(added.players[0].hand) == len(partner.players[0].hand) + 1


def test_the_codec_holds_box_one_twins_in_immortality_catalogs_only() -> None:
    plain = ActionCodec(RulesetConfig(choam_module=True, bloodlines=True))
    assert not any(
        ("box", 1) in template.arguments for template in plain.catalog
    )
    assert ActionCodec(RulesetConfig()).size == 4413
    codec = ActionCodec(IMMORTALITY)
    templates = set(codec.catalog)
    twins = {t for t in codec.catalog if ("box", 1) in t.arguments}
    assert twins
    assert all(t.action_id in BOX_ACTION_IDS for t in twins)
    for template in codec.catalog:
        if template.action_id in BOX_ACTION_IDS and template not in twins:
            twin = ActionTemplate(
                template.action_id,
                tuple(sorted((*template.arguments, ("box", 1)))),
            )
            assert twin in templates
    assert "switch_graft_card" not in {t.action_id for t in codec.catalog}
