"""Tests for the Bloodlines Imperium cards transcribed in M12 slice 4b.

Card text is transcribed from the card faces (``docs/rules/bloodlines.md``,
``docs/implementation-audits/bloodlines.md``); "Command (6+)" follows
[Bloodlines pp. 5, 12].
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_discard,
    legal_agent_card_discard_actions,
    legal_agent_card_icon_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import (
    apply_reveal_card_trash,
    apply_reveal_influence_gain,
    apply_reveal_troop_retreat,
    begin_reveal_turn,
    legal_finish_reveal_actions,
    legal_reveal_card_trash_actions,
    legal_reveal_influence_gain_actions,
    legal_reveal_spy_actions,
    legal_reveal_troop_retreat_actions,
)
from dune_imperium.simulation.sweep import run_checked_game

BLOODLINES = RulesetConfig(bloodlines=True)
CHOAM_BLOODLINES = RulesetConfig(bloodlines=True, choam_module=True)
LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)
STARTERS = starting_deck_instance_ids(0)


def _card(card_id: str, copy: int = 0) -> str:
    return f"imperium:{card_id}:{copy}"


def _state(owner: PlayerState, config: RulesetConfig = BLOODLINES) -> GameState:
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        sardaukar_commander_space_ids=(),
        sardaukar_commanders_bank=1,
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _owner(**overrides: object) -> PlayerState:
    values: dict[str, object] = {"player_id": 0, "deck": STARTERS[:4]}
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _play(state: GameState, card_id: str, space_id: str | None = None) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if (space_id is None or dict(action.arguments)["space_id"] == space_id)
        and dict(action.arguments)["card_id"] == card_id
    )
    state = apply_agent_action(state, action).state
    for board_action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, board_action).state
    return state


def _reveal(state: GameState) -> GameState:
    return begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state


def _reveal_context(state: GameState) -> dict[str, object]:
    return {
        key: value
        for frame in state.decision_stack
        if frame.kind == "reveal"
        for key, value in frame.context
    }


# --- Quash Rebellion -------------------------------------------------------


def test_quash_rebellion_pays_two_solari_and_needs_a_commander_for_persuasion() -> None:
    card = _card("quash_rebellion")
    state = _play(_state(_owner(hand=(card,))), card, "assembly_hall")
    resolved = resolve_agent_card_effect(state).state
    assert resolved.players[0].resources.solari == 2

    revealed = _reveal(_state(_owner(hand=(card,))))
    context = _reveal_context(revealed)
    assert context["persuasion"] == 0
    assert context["sword_strength"] == 2

    with_commander = _reveal(
        _state(_owner(hand=(card,), commanders_conflict=1, combat_strength=2))
    )
    assert _reveal_context(with_commander)["persuasion"] == 2


# --- Command (6+) ----------------------------------------------------------


def _six_persuasion_hand(*extra: str) -> PlayerState:
    # Two Sandwalks bond each other (+1 each) on top of their printed 1s.
    return _owner(
        hand=(_card("sandwalk"), _card("sandwalk", 1), *extra), high_council=True
    )


def test_shrouded_counsel_command_trash_opens_at_six_persuasion() -> None:
    card = _card("shrouded_counsel")
    revealed = _reveal(_state(_six_persuasion_hand(card)))
    assert _reveal_context(revealed)["persuasion"] == 2 + 2 + 2 + 1
    frame = revealed.decision_stack[-1]
    assert frame.kind == "reveal_choice"
    assert dict(frame.context)["reveal_choice_effect"] == "command_may_trash_card"
    actions = legal_reveal_card_trash_actions(revealed, 0)
    assert actions[0].action_id == "decline_reveal_card_trash"
    targets = {dict(a.arguments)["card_id"] for a in actions[1:]}
    assert targets == set(revealed.players[0].in_play)
    trashed = apply_reveal_card_trash(revealed, actions[1]).state
    assert len(trashed.players[0].trashed) == 1
    assert trashed.decision_stack[-1].kind == "reveal"


def test_command_choices_wait_below_six_persuasion() -> None:
    card = _card("shrouded_counsel")
    revealed = _reveal(_state(_owner(hand=(card, _card("sandwalk")))))
    assert _reveal_context(revealed)["persuasion"] == 2
    assert revealed.decision_stack[-1].kind == "reveal"
    # The Command choice is queued, and lapses when the Reveal ends.
    assert "command_may_trash_card" in str(
        _reveal_context(revealed)["deferred_reveal_choices"]
    )
    assert legal_finish_reveal_actions(revealed, 0) != ()


def test_i_believe_discards_to_draw_and_recruits_two_on_command() -> None:
    card = _card("i_believe")
    filler = STARTERS[4]
    state = _play(_state(_owner(hand=(card, filler))), card, "arrakeen")
    actions = legal_agent_card_discard_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_discard"
    discard = next(a for a in actions if a.action_id == "discard_agent_card")
    before = len(state.players[0].hand)
    drawn = apply_agent_card_discard(state, discard).state.players[0]
    assert filler in drawn.discard_pile
    assert len(drawn.hand) == before  # one discarded, one drawn from the deck

    revealed = _reveal(_state(_six_persuasion_hand(card)))
    owner = revealed.players[0]
    assert owner.troops_garrison == 3 + 2
    below = _reveal(_state(_owner(hand=(card,))))
    assert below.players[0].troops_garrison == 3


def test_intelligence_training_command_places_a_spy() -> None:
    card = _card("intelligence_training")
    revealed = _reveal(_state(_six_persuasion_hand(card)))
    frame = revealed.decision_stack[-1]
    assert dict(frame.context)["reveal_choice_effect"] == "command_place_spy"
    actions = legal_reveal_spy_actions(revealed, 0)
    assert {a.action_id for a in actions} == {"place_reveal_spy"}
    # Its own sword plus the two Sandwalks' swords.
    assert _reveal_context(revealed)["sword_strength"] == 1 + 2


def test_pointing_the_way_needs_a_sandworm_and_commands_influence() -> None:
    card = _card("pointing_the_way")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    result = resolve_agent_card_effect(state)
    assert result.events[0].kind == "agent_card_effect_unavailable"

    with_worm = _play(
        _state(_owner(hand=(card,), sandworms_conflict=1)), card, "arrakeen"
    )
    result = resolve_agent_card_effect(with_worm)
    assert result.events[0].kind == "agent_card_effect_resolved"
    assert len(result.state.players[0].intrigue_cards) == 1

    revealed = _reveal(_state(_six_persuasion_hand(card)))
    actions = legal_reveal_influence_gain_actions(revealed, 0)
    assert [dict(a.arguments)["faction"] for a in actions] == [
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    gained = apply_reveal_influence_gain(revealed, actions[3]).state
    assert gained.players[0].influence.fremen == 1
    assert gained.decision_stack[-1].kind == "reveal"


# --- Command Center ----------------------------------------------------------


def test_command_center_recruits_at_two_emperor_influence() -> None:
    card = _card("command_center")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    assert (
        resolve_agent_card_effect(state).events[0].kind
        == "agent_card_effect_unavailable"
    )
    loyal = _play(
        _state(_owner(hand=(card,), influence=Influence(emperor=2))), card, "arrakeen"
    )
    before = loyal.players[0].troops_garrison
    resolved = resolve_agent_card_effect(loyal).state
    assert resolved.players[0].troops_garrison == before + 1


def test_command_center_retreats_two_troops_for_two_persuasion() -> None:
    card = _card("command_center")
    owner = _owner(hand=(card,), troops_supply=7, troops_conflict=2, combat_strength=4)
    revealed = _reveal(_state(owner))
    actions = legal_reveal_troop_retreat_actions(revealed, 0)
    retreat = next(a for a in actions if a.action_id == "retreat_two_troops_for_reveal")
    result = apply_reveal_troop_retreat(revealed, retreat)
    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].troops_garrison == 5
    assert _reveal_context(result.state)["persuasion"] == 1 + 2
    assert result.events[1].kind == "reveal_persuasion_gained"


# --- trash, discard, acquisition triggers -------------------------------------


def test_eliminate_allies_recruits_two_troops_when_trashed() -> None:
    card = _card("eliminate_allies")
    # A Spy-icon card follows the owner's Spy [Main p. 11]: one watches
    # Sardaukar / Dutiful Service.
    owner = _owner(
        hand=(card,),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    state = _play(_state(owner), card, "dutiful_service")
    before = state.players[0].troops_garrison
    result = trash_personal_card(state, 0, card, source="test")
    owner = result.state.players[0]
    assert owner.troops_garrison == before + 2
    assert card in owner.trashed
    # Recruited during the Agent turn: they join the deployable count
    assert dict(result.state.decision_stack[-1].context)["troops_recruited"] == 2


def test_corrupt_bureaucrat_discard_pays_three_solari() -> None:
    card = _card("corrupt_bureaucrat")
    state = _state(_owner(hand=(card,)), CHOAM_BLOODLINES)
    result = discard_personal_card_from_hand(state, 0, card, source="test")
    assert result.state.players[0].resources.solari == 3


def test_corrupt_bureaucrat_takes_a_contract_after_a_spy_recall() -> None:
    card = _card("corrupt_bureaucrat")
    contracts = ("contract:deliver_supplies:0", "contract:harvest_3:0")
    base = replace(
        _state(_owner(hand=(card,)), CHOAM_BLOODLINES),
        face_up_contract_ids=contracts,
    )
    state = _play(base, card, "assembly_hall")
    assert (
        resolve_agent_card_effect(state).events[0].kind
        == "agent_card_effect_unavailable"
    )
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["spy_recalled_this_turn"] = True
    recalled = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )
    result = resolve_agent_card_effect(recalled)
    assert result.state.decision_stack[-1].kind == "contract_market"


def test_mercantile_affairs_draws_intrigue_after_a_contract_completed_this_turn() -> (
    None
):
    card = _card("mercantile_affairs")
    state = _play(_state(_owner(hand=(card,)), CHOAM_BLOODLINES), card, "arrakeen")
    assert (
        resolve_agent_card_effect(state).events[0].kind
        == "agent_card_effect_unavailable"
    )
    completed = replace(
        state,
        players=(
            replace(state.players[0], contracts_completed_turn=1),
            *state.players[1:],
        ),
    )
    result = resolve_agent_card_effect(completed)
    assert len(result.state.players[0].intrigue_cards) == 1


def test_imperial_throneship_rewards_a_large_garrison() -> None:
    card = _card("imperial_throneship")
    revealed = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(revealed)["persuasion"] == 2
    big = _reveal(_state(_owner(hand=(card,), commanders_garrison=1)))
    assert _reveal_context(big)["persuasion"] == 3
    assert big.players[0].resources.solari == 3


# --- spice gained this turn ---------------------------------------------------


def test_sandwalk_draws_after_two_spice_gained_this_turn() -> None:
    card = _card("sandwalk")
    poor = _play(_state(_owner(hand=(card,))), card)
    assert (
        resolve_agent_card_effect(poor).events[0].kind
        == "agent_card_effect_unavailable"
    )
    rich = _play(
        _state(_owner(hand=(card,), resources=Resources(spice=2, water=1))), card
    )
    before = len(rich.players[0].hand)
    result = resolve_agent_card_effect(rich)
    assert result.events[0].kind == "agent_card_effect_resolved"
    assert len(result.state.players[0].hand) == before + 1


def test_fremen_war_name_icons_need_two_spice_gained() -> None:
    card = _card("fremen_war_name")
    rich = _play(
        _state(_owner(hand=(card,), resources=Resources(spice=3, water=1))), card
    )
    keys = {dict(a.arguments)["effect"] for a in legal_agent_card_icon_actions(rich, 0)}
    assert keys == {"troops", "cards"}
    troops = next(
        a
        for a in legal_agent_card_icon_actions(rich, 0)
        if dict(a.arguments)["effect"] == "troops"
    )
    before = rich.players[0].troops_garrison
    resolved = resolve_agent_card_icon(rich, troops).state
    assert resolved.players[0].troops_garrison == before + 1

    poor = _play(_state(_owner(hand=(card,))), card)
    troops = next(
        a
        for a in legal_agent_card_icon_actions(poor, 0)
        if dict(a.arguments)["effect"] == "troops"
    )
    before = poor.players[0].troops_garrison
    result = resolve_agent_card_icon(poor, troops)
    assert result.state.players[0].troops_garrison == before
    assert result.events[0].kind == "agent_card_effect_unavailable"


# --- soak ---------------------------------------------------------------------


@pytest.mark.parametrize("game_seed", [31, 32])
def test_random_bloodlines_games_with_the_new_cards_finish(game_seed: int) -> None:
    report = run_checked_game(
        BLOODLINES,
        game_seed=game_seed,
        policy_seed=900_000 + game_seed,
        privacy_interval=10,
        soundness_interval=10,
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.rounds >= 1


def test_heuristic_choam_bloodlines_game_finishes() -> None:
    report = run_checked_game(
        CHOAM_BLOODLINES,
        game_seed=41,
        policy_seed=900_041,
        privacy_interval=0,
        policy="heuristic",
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.rounds >= 1
