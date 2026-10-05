"""Tech purchases and their freely ordered rewards (user ruling OQ-098).

docs/rules/bloodlines.md §5: "획득 효과의 각 아이콘은 그 turn 안에서 다른
효과와 원하는 순서로 해결한다" [Bloodlines p. 7] [Main p. 9]. This is a
project convention requested by the user, rather than the rulebook's
immediate acquire-effect example. Reward choices belong to the owner.
"""

from dataclasses import replace

import pytest

from dune_imperium.adapters import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.content.bloodlines.tech import TECH_TILES
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.tech import (
    legal_tech_acquire_effect_actions,
    push_tech_acquisition,
)

ENGINE = UprisingRulesEngine()
CONFIG = RulesetConfig(bloodlines=True, tech_module=True, choam_module=True)


def turn(*tech_ids: str, **owner_fields: object) -> GameState:
    fields: dict[str, object] = dict(
        player_id=0,
        leader_id="gurney_halleck",
        hand=starting_deck_instance_ids(0)[:5],
        deck=starting_deck_instance_ids(0)[5:],
        resources=Resources(solari=8, spice=20, water=2),
    )
    fields.update(owner_fields)
    owner = PlayerState(**fields)  # type: ignore[arg-type]
    return GameState(
        config=CONFIG,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        first_player=0,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(True)[:5],
        players=(owner, *(PlayerState(player_id=i) for i in range(1, 4))),
        tech_stacks=(tech_ids, (), ()),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def act(state: GameState, action_id: str, **args: object) -> GameState:
    action = next(
        action
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in args.items())
    )
    return ENGINE.apply(state, action).state


def buy(state: GameState, tech_id: str) -> GameState:
    opened = push_tech_acquisition(state, 0, discount=0, source=f"test:{tech_id}").state
    return act(opened, "acquire_tech", tech_id=tech_id)


def place(state: GameState) -> GameState:
    return act(state, "agent_turn", space_id="assembly_hall")


@pytest.mark.parametrize("tech_id", ["glowglobes", "navigation_chamber"])
@pytest.mark.parametrize("faction", list(Faction))
def test_influence_is_unchanged_until_the_owner_selects_a_faction(
    tech_id: str, faction: Faction
) -> None:
    placed = place(turn(tech_id))
    bought = act(placed, "acquire_tech", tech_id=tech_id)
    assert bought.players[0].influence == Influence()
    assert bought.players[0].tech_ids == (tech_id,)
    rewards = legal_tech_acquire_effect_actions(bought, 0)
    assert {dict(a.arguments)["faction"] for a in rewards} == {f.value for f in Faction}
    assert legal_tech_acquire_effect_actions(bought, 1) == ()
    assert not any(
        a.action_id == "finish_agent_turn" for a in ENGINE.legal_actions(bought, 0)
    )
    # Another effect may resolve between buying and gaining Influence.
    after_board = act(bought, "resolve_board_effect", effect="intrigue")
    assert after_board.players[0].influence == Influence()
    chosen = next(a for a in rewards if dict(a.arguments)["faction"] == faction.value)
    resolved = ENGINE.apply(after_board, chosen).state
    assert resolved.players[0].influence == replace(Influence(), **{faction.value: 1})
    assert legal_tech_acquire_effect_actions(resolved, 0) == ()
    with pytest.raises(ValueError):
        ENGINE.apply(resolved, chosen)


@pytest.mark.parametrize("tile", TECH_TILES, ids=lambda tile: tile.tech_id)
def test_purchase_never_pays_any_acquire_reward(tile: object) -> None:
    from dune_imperium.content.bloodlines.tech import TechTile

    assert isinstance(tile, TechTile)
    state = turn(tile.tech_id, spy_post_ids=("arrakis-deep-desert",), spies_supply=2)
    before = state.players[0]
    opened = push_tech_acquisition(state, 0, discount=0, source="test").state
    bought = act(opened, "acquire_tech", tech_id=tile.tech_id)
    after = bought.players[0]
    assert after.resources.solari == before.resources.solari
    assert after.troops_garrison == before.troops_garrison
    assert after.intrigue_cards == before.intrigue_cards
    assert after.hand == before.hand and after.deck == before.deck
    assert after.victory_points == before.victory_points
    assert after.influence == before.influence
    assert after.spies_supply == before.spies_supply
    assert after.active_contract_ids == before.active_contract_ids
    assert bought.shield_wall_present
    assert not any(frame.kind == "leader_signet" for frame in bought.decision_stack)
    # The Advanced Data Analysis prerequisite is paid during purchase.
    if tile.acquire_requires_spy_trash:
        assert after.spy_post_ids == () and after.spies_boxed == 1
    codec = ActionCodec(CONFIG)
    for action in ENGINE.legal_actions(bought, 0):
        assert codec.decode(codec.encode(action), 0) == action


@pytest.mark.parametrize("transition", ["agent_turn", "reveal_turn"])
def test_rewards_bought_before_placement_survive_the_turn_transition(
    transition: str,
) -> None:
    bought = buy(turn("rapid_dropships", combat_icon_turn=True), "rapid_dropships")
    assert bought.players[0].troops_garrison == 3
    if transition == "agent_turn":
        changed = place(bought)
        finish = "finish_agent_turn"
    else:
        changed = act(bought, "reveal_turn")
        finish = "finish_reveal"
    assert not any(a.action_id == finish for a in ENGINE.legal_actions(changed, 0))
    resolved = act(changed, "resolve_tech_acquire_effect", effect="troops")
    assert resolved.players[0].troops_garrison == 5
    deploy = [
        a for a in ENGINE.legal_actions(resolved, 0) if a.action_id == "deploy_troops"
    ]
    assert max(int(dict(a.arguments)["count"]) for a in deploy) == 4


def test_two_purchases_rewards_can_be_resolved_in_reverse_order() -> None:
    state = buy(
        buy(turn("glowglobes", "plasteel_blades"), "glowglobes"), "plasteel_blades"
    )
    assert state.players[0].influence == Influence()
    assert state.players[0].resources.solari == 8
    state = act(state, "resolve_tech_acquire_effect", tech_id="plasteel_blades")
    assert state.players[0].resources.solari == 12
    assert state.players[0].influence == Influence()
    state = act(state, "resolve_tech_acquire_effect", faction="fremen")
    assert state.players[0].influence.fremen == 1


def test_forbidden_weapons_icons_are_independent_and_use_live_supply() -> None:
    bought = act(
        place(turn("forbidden_weapons", combat_icon_turn=True)), "acquire_tech"
    )
    assert bought.players[0].troops_garrison == 3 and bought.shield_wall_present
    # Destroy the wall first, then the troop; both orders are available.
    destroyed = act(bought, "resolve_tech_acquire_effect", destroy_shield_wall=True)
    assert (
        not destroyed.shield_wall_present and destroyed.players[0].troops_garrison == 3
    )
    recruited = act(destroyed, "resolve_tech_acquire_effect", effect="troops")
    assert recruited.players[0].troops_garrison == 4
    assert dict(recruited.decision_stack[-1].context)["troops_recruited"] == 1


@pytest.mark.parametrize("choice", ["card", "intrigue"])
def test_gene_locked_vault_choice_and_draw_wait_for_resolution(choice: str) -> None:
    bought = buy(turn("gene_locked_vault"), "gene_locked_vault")
    assert len(bought.players[0].hand) == 5
    assert bought.players[0].intrigue_cards == ()
    resolved = act(bought, "resolve_tech_acquire_effect", choice=choice)
    assert len(resolved.players[0].hand) == 5 + (choice == "card")
    assert len(resolved.players[0].intrigue_cards) == (choice == "intrigue")


def test_combat_purchase_has_an_explicit_effect_window_before_resuming() -> None:
    state = turn("glowglobes")
    state = replace(
        state,
        players=(
            replace(state.players[0], troops_garrison=2, troops_conflict=1),
            *state.players[1:],
        ),
    )
    combat = begin_combat_intrigue(
        replace(state, phase=GamePhase.COMBAT, decision_stack=())
    ).state
    bought = buy(combat, "glowglobes")
    assert bought.decision_stack[-1].kind == "tech_acquisition"
    assert {a.action_id for a in ENGINE.legal_actions(bought, 0)} == {
        "resolve_tech_acquire_effect"
    }
    resolved = act(bought, "resolve_tech_acquire_effect", faction="spacing_guild")
    assert resolved.decision_stack[-1].kind == "combat_intrigue"
    assert resolved.players[0].influence.spacing_guild == 1


def test_servo_signet_reads_the_placement_made_after_the_purchase() -> None:
    bought = buy(
        turn("servo_receivers", leader_id="liet_kynes", influence=Influence(emperor=2)),
        "servo_receivers",
    )
    assert bought.players[0].resources.water == 2
    placed = place(bought)
    resolved = act(placed, "resolve_tech_acquire_effect", effect="signet")
    assert resolved.players[0].resources.water == 3


def test_already_acquired_rewards_survive_trashing_the_tile() -> None:
    bought = buy(turn("forbidden_weapons"), "forbidden_weapons")
    revealed = act(bought, "reveal_turn")
    trashed = act(revealed, "choose_tech_trash")
    assert "forbidden_weapons" not in trashed.players[0].tech_ids
    assert {
        dict(a.arguments)["effect"]
        for a in legal_tech_acquire_effect_actions(trashed, 0)
    } == {"troops", "shield_wall"}
    resolved = act(trashed, "resolve_tech_acquire_effect", effect="troops")
    assert resolved.players[0].troops_garrison == 4
    resolved = act(resolved, "resolve_tech_acquire_effect", effect="shield_wall")
    assert legal_tech_acquire_effect_actions(resolved, 0) == ()
