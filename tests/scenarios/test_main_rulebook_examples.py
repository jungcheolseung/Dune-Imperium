"""Golden scenarios derived from the official Uprising rulebook examples."""

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules import UprisingRulesEngine


def _starting_card(player: int, card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(player)
        if f":{card_id}:" in instance_id
    )


def _imperium_card(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def test_main_page_11_imperial_basin_deploys_at_most_two_garrison_troops() -> None:
    """John visits Imperial Basin and deploys two troops without recruiting."""

    john = PlayerState(
        player_id=0,
        hand=(_starting_card(0, "dune_the_desert_planet"),),
        troops_supply=9,
        troops_garrison=3,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=11,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        first_player=0,
        players=(john, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        current_conflict_ids=("propaganda",),
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 0),
            ("imperial_basin", 1),
        ),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
                context=(("round", 1), ("turn_owner", 0)),
            ),
        ),
    )
    engine = UprisingRulesEngine()
    visit = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("space_id") == "imperial_basin"
    )

    state = engine.apply(state, visit).state
    effect_actions = engine.legal_actions(state, 0)
    assert "summon_maker_sandworms" not in {
        action.action_id for action in effect_actions
    }
    harvest = next(
        action for action in effect_actions if action.action_id == "harvest_maker_spice"
    )
    state = engine.apply(state, harvest).state
    deployments = engine.legal_actions(state, 0)

    assert tuple(dict(action.arguments)["count"] for action in deployments) == (
        0,
        1,
        2,
    )
    deploy_two = DomainAction(
        action_id="deploy_troops",
        actor=0,
        arguments=(("count", 2),),
    )
    state = engine.apply(state, deploy_two).state

    assert state.players[0].resources.spice == 2
    assert state.players[0].troops_garrison == 1
    assert state.players[0].troops_conflict == 2
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1


def test_main_page_13_reveal_acquires_and_immediately_refills_the_row() -> None:
    """Three Persuasion buys a cost-two card and leaves one unspent."""

    argument = _starting_card(0, "convincing_argument")
    diplomacy = _starting_card(0, "diplomacy")
    desert_survival = _imperium_card("desert_survival")
    all_imperium = imperium_deck_instance_ids(False)
    other_cards = tuple(card for card in all_imperium if card != desert_survival)
    row = (desert_survival, *other_cards[:4])
    replacement = other_cards[4]
    john = PlayerState(
        player_id=0,
        hand=(argument, diplomacy),
        troops_supply=10,
        troops_garrison=0,
        troops_conflict=2,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=13,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        first_player=0,
        players=(john, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        current_conflict_ids=("propaganda",),
        imperium_row=row,
        imperium_deck=(replacement, *other_cards[5:]),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
                context=(("round", 1), ("turn_owner", 0)),
            ),
        ),
    )
    engine = UprisingRulesEngine()
    reveal = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "reveal_turn"
    )

    state = engine.apply(state, reveal).state
    context = dict(state.decision_stack[-1].context)
    assert context["persuasion"] == 3
    assert state.players[0].combat_strength == 4
    acquire = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == desert_survival
    )
    state = engine.apply(state, acquire).state

    assert state.imperium_row == (replacement, *row[1:])
    assert state.imperium_deck == other_cards[5:]
    assert state.players[0].discard_pile == (desert_survival,)
    assert dict(state.decision_stack[-1].context)["persuasion"] == 1

    finish = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "finish_reveal"
    )
    state = engine.apply(state, finish).state

    assert state.players[0].discard_pile == (
        desert_survival,
        argument,
        diplomacy,
    )
    assert state.players[0].has_revealed is True
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
