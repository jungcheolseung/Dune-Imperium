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
from dune_imperium.rules.frames import replace_player
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
    """Reveal and take every pending troop recruit and Intrigue draw at once."""

    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )

    revealed = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    while actions := legal_reveal_gain_actions(revealed, 0):
        revealed = apply_reveal_gain(revealed, actions[0]).state
    return revealed


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


# --- Bloodlines Intrigue (slice 4c-1) ---------------------------------------


def _intrigue(card_id: str) -> str:
    return f"intrigue:{card_id}:0"


def _play_intrigue(card_id: str, option: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card_id), ("option", option)),
    )


def _combat_state(owner: PlayerState, *others: PlayerState) -> GameState:
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.rules.combat import begin_combat_intrigue

    seats = [owner, *others]
    seats.extend(PlayerState(player_id=seat) for seat in range(len(seats), 4))
    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=tuple(replace(seat, has_revealed=True) for seat in seats),
    )
    return begin_combat_intrigue(state).state


def _endgame_window(owner: PlayerState) -> GameState:
    from dune_imperium.rules.endgame import begin_endgame_intrigue

    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )
    return begin_endgame_intrigue(state).state


def _fighter(troops: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "troops_supply": 12 - troops,
        "troops_garrison": 0,
        "troops_conflict": troops,
        "combat_strength": 2 * troops,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def test_desert_support_pays_water_for_five_swords() -> None:
    card = _intrigue("desert_support")
    state = _combat_state(
        _fighter(1, intrigue_cards=(card,), resources=Resources(water=1))
    )
    engine = UprisingRulesEngine()
    done = engine.apply(state, _play_intrigue(card)).state
    assert done.players[0].resources.water == 0
    assert done.players[0].combat_strength == 2 + 5


def test_ripples_in_the_sand_adds_intrigue_with_a_sandworm() -> None:
    card = _intrigue("ripples_in_the_sand")
    engine = UprisingRulesEngine()
    plain = engine.apply(
        _combat_state(_fighter(1, intrigue_cards=(card,))), _play_intrigue(card)
    ).state
    assert plain.players[0].combat_strength == 5
    assert plain.players[0].intrigue_cards == ()

    worm = _fighter(1, intrigue_cards=(card,), sandworms_conflict=1, combat_strength=5)
    with_worm = engine.apply(_combat_state(worm), _play_intrigue(card)).state
    assert with_worm.players[0].combat_strength == 8
    assert len(with_worm.players[0].intrigue_cards) == 1


def test_return_the_favor_counts_factions_at_two_influence() -> None:
    card = _intrigue("return_the_favor")
    owner = _fighter(
        1,
        intrigue_cards=(card,),
        influence=Influence(emperor=2, fremen=3, bene_gesserit=1),
    )
    done = UprisingRulesEngine().apply(_combat_state(owner), _play_intrigue(card)).state
    assert done.players[0].combat_strength == 2 + 1 + 2


def test_sacred_pools_discards_for_water_or_scores_at_three_water() -> None:
    card = _intrigue("sacred_pools")
    filler = STARTERS[5]
    state = _state(_owner(hand=(filler,), intrigue_cards=(card,)))
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play_intrigue(card, 0)).state
    discard = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "choose_intrigue_discard"
    )
    done = engine.apply(opened, discard).state
    assert done.players[0].resources.water == 2
    assert filler in done.players[0].discard_pile

    dry = _endgame_window(_owner(intrigue_cards=(card,), resources=Resources(water=2)))
    assert [a.action_id for a in engine.legal_actions(dry, 0)] == [
        "pass_endgame_intrigue"
    ]
    wet = _endgame_window(_owner(intrigue_cards=(card,), resources=Resources(water=3)))
    scored = engine.apply(wet, _play_intrigue(card, 1)).state
    assert scored.players[0].victory_points == 2


def test_seize_production_spice_needs_a_commander_in_the_conflict() -> None:
    card = _intrigue("seize_production")
    engine = UprisingRulesEngine()
    plain = _state(_owner(intrigue_cards=(card,)))
    assert [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(plain, 0)
        if a.action_id == "play_intrigue"
    ] == [0]
    solari = engine.apply(plain, _play_intrigue(card, 0)).state
    assert solari.players[0].resources.solari == 2

    commanded = _state(_owner(intrigue_cards=(card,), commanders_conflict=1))
    spice = engine.apply(commanded, _play_intrigue(card, 1)).state
    assert spice.players[0].resources.spice == 2


def test_sleeper_unit_pays_for_a_spy_or_recalls_one_for_troops() -> None:
    card = _intrigue("sleeper_unit")
    engine = UprisingRulesEngine()
    paying = _state(_owner(intrigue_cards=(card,), resources=Resources(solari=1)))
    opened = engine.apply(paying, _play_intrigue(card, 0)).state
    assert opened.players[0].resources.solari == 0
    assert {a.action_id for a in engine.legal_actions(opened, 0)} == {
        "place_intrigue_spy",
        "decline_intrigue_spy",
    }

    posted = _state(
        _owner(
            intrigue_cards=(card,),
            spies_supply=2,
            spy_post_ids=("emperor-sardaukar-dutiful-service",),
        )
    )
    recalled = engine.apply(posted, _play_intrigue(card, 1)).state
    recall = next(
        a
        for a in engine.legal_actions(recalled, 0)
        if a.action_id == "recall_spy_for_intrigue"
    )
    done = engine.apply(recalled, recall).state
    assert done.players[0].spies_supply == 3
    assert done.players[0].troops_garrison == 5


def test_tenuous_bond_trashes_a_costly_discard_for_four_swords() -> None:
    card = _intrigue("tenuous_bond")
    engine = UprisingRulesEngine()
    cheap = _fighter(1, intrigue_cards=(card,), discard_pile=(STARTERS[0],))
    # Starting cards have no printed cost: only the Influence swap is playable.
    options = [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(_combat_state(cheap), 0)
        if a.action_id == "play_intrigue"
    ]
    assert options == []  # no Influence to lose either
    costly = _fighter(
        1,
        intrigue_cards=(card,),
        discard_pile=(STARTERS[0], _card("sandwalk")),
        influence=Influence(fremen=1),
    )
    state = _combat_state(costly)
    options = [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(state, 0)
        if a.action_id == "play_intrigue"
    ]
    assert options == [1, 3]
    opened = engine.apply(state, _play_intrigue(card, 3)).state
    trash_actions = engine.legal_actions(opened, 0)
    assert [dict(a.arguments)["card_id"] for a in trash_actions] == [_card("sandwalk")]
    done = engine.apply(opened, trash_actions[0]).state
    assert done.players[0].trashed == (_card("sandwalk"),)
    assert done.players[0].combat_strength == 2 + 4


def test_the_strong_survive_retreats_one_troop_to_trash_a_card() -> None:
    card = _intrigue("the_strong_survive")
    engine = UprisingRulesEngine()
    owner = _fighter(2, intrigue_cards=(card,), hand=(STARTERS[0],))
    state = _combat_state(owner)
    swords = engine.apply(state, _play_intrigue(card, 0)).state
    assert swords.players[0].combat_strength == 4 + 3

    opened = engine.apply(state, _play_intrigue(card, 1)).state
    retreat = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "retreat_intrigue_troops"
    )
    retreated = engine.apply(opened, retreat).state
    assert retreated.players[0].troops_conflict == 1
    assert retreated.players[0].combat_strength == 2
    trash = next(
        a
        for a in engine.legal_actions(retreated, 0)
        if a.action_id == "trash_intrigue_card"
    )
    done = engine.apply(retreated, trash).state
    assert done.players[0].trashed == (STARTERS[0],)


def test_withdrawal_agreement_retreats_three_for_influence() -> None:
    card = _intrigue("withdrawal_agreement")
    engine = UprisingRulesEngine()
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        legal_intrigue_choice_actions,
    )

    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    opened = engine.apply(state, _play_intrigue(card)).state
    retreat = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "retreat_intrigue_troops"
    )
    assert dict(retreat.arguments)["count"] == 3
    # Resolve the slots without the dispatcher: the last unit leaving the
    # Conflict would otherwise run the round to its end.
    retreated = apply_intrigue_choice(opened, retreat).state
    choice = next(
        a
        for a in legal_intrigue_choice_actions(retreated, 0)
        if a.action_id == "choose_intrigue_faction"
        and dict(a.arguments)["faction"] == "emperor"
    )
    done = apply_intrigue_choice(retreated, choice).state
    assert done.players[0].influence.emperor == 1
    assert done.players[0].troops_garrison == 3
    assert done.players[0].combat_strength == 0


def test_grasp_arrakis_flips_two_conflict_cards_for_a_point() -> None:
    card = _intrigue("grasp_arrakis")
    engine = UprisingRulesEngine()
    owner = _fighter(
        1,
        intrigue_cards=(card,),
        won_conflict_ids=("skirmish_ornithopter", "storms_in_the_south"),
    )
    state = _combat_state(owner)
    options = [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(state, 0)
        if a.action_id == "play_intrigue"
    ]
    assert options == [0, 1]
    opened = engine.apply(state, _play_intrigue(card, 1)).state
    first = engine.legal_actions(opened, 0)
    assert {dict(a.arguments)["card_id"] for a in first} == {
        "skirmish_ornithopter",
        "storms_in_the_south",
    }
    flipped_one = engine.apply(opened, first[0]).state
    second = engine.legal_actions(flipped_one, 0)
    assert len(second) == 1
    done = engine.apply(flipped_one, second[0]).state
    assert done.players[0].victory_points == 2
    assert set(done.players[0].face_down_battle_card_ids) == {
        "skirmish_ornithopter",
        "storms_in_the_south",
    }
    # With one card left face up the Endgame half is not offered.
    single = _endgame_window(
        _owner(intrigue_cards=(card,), won_conflict_ids=("skirmish_ornithopter",))
    )
    assert [a.action_id for a in engine.legal_actions(single, 0)] == [
        "pass_endgame_intrigue"
    ]


# --- turn-scoped Plot modifiers (slice 4c-2a) --------------------------------


def test_honor_guard_recruits_and_discounts_the_commander_this_turn() -> None:
    from dune_imperium.rules.sardaukar import (
        apply_sardaukar_commander_action,
        legal_sardaukar_commander_actions,
    )

    card = _intrigue("honor_guard")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,), hand=STARTERS[4:10], resources=Resources(solari=1)
    )
    state = replace(
        _state(owner),
        sardaukar_commander_space_ids=("dutiful_service",),
        skill_face_up=("skill:canny:0",),
    )
    played = engine.apply(state, _play_intrigue(card)).state
    assert played.players[0].troops_garrison == 4
    assert played.players[0].commander_discount_turn == 1

    # Any card that reaches Dutiful Service works; pick the first legal one.
    action = next(
        a
        for a in legal_agent_actions(played, 0)
        if dict(a.arguments)["space_id"] == "dutiful_service"
    )
    visited = apply_agent_action(played, action).state
    for board_action in legal_board_effect_actions(visited, 0):
        visited = resolve_board_effect(visited, board_action).state
    buy = next(
        a
        for a in legal_sardaukar_commander_actions(visited, 0)
        if a.action_id == "acquire_sardaukar_commander"
    )
    bought = apply_sardaukar_commander_action(visited, buy)
    assert bought.state.players[0].resources.solari == 1 + 2 - 1
    assert dict(bought.events[0].payload)["solari"] == 1


def test_insider_information_waives_influence_requirements_this_turn() -> None:
    card = _intrigue("insider_information")
    engine = UprisingRulesEngine()
    owner = _owner(intrigue_cards=(card,), hand=STARTERS[4:10])
    state = _state(owner)
    # Sietch Tabr needs two Fremen Influence [Board Guide p. 1].
    assert not any(
        dict(a.arguments)["space_id"] == "sietch_tabr"
        for a in legal_agent_actions(state, 0)
    )
    waived = engine.apply(state, _play_intrigue(card, 1)).state
    assert waived.players[0].ignores_influence_requirements_turn is True
    assert any(
        dict(a.arguments)["space_id"] == "sietch_tabr"
        for a in legal_agent_actions(waived, 0)
    )


def test_insider_information_recalls_a_spy_to_trash_and_draw() -> None:
    card = _intrigue("insider_information")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,),
        hand=(STARTERS[4],),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    opened = engine.apply(_state(owner), _play_intrigue(card, 0)).state
    recall = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "recall_spy_for_intrigue"
    )
    recalled = engine.apply(opened, recall).state
    trash = next(
        a
        for a in engine.legal_actions(recalled, 0)
        if a.action_id == "trash_intrigue_card"
        and dict(a.arguments)["card_id"] == STARTERS[4]
    )
    done = engine.apply(recalled, trash).state
    owner_after = done.players[0]
    assert owner_after.spies_supply == 3
    assert owner_after.trashed == (STARTERS[4],)
    assert len(owner_after.hand) == 1  # the drawn card


def test_emperors_invitation_lends_the_emperor_icon_for_the_turn() -> None:
    from dune_imperium.adapters import ActionCodec

    card = _intrigue("emperor_s_invitation")
    engine = UprisingRulesEngine()
    dagger = next(c for c in STARTERS if ":dagger:" in c)
    state = _state(_owner(intrigue_cards=(card,), hand=(dagger,), deck=()))
    assert not any(
        dict(a.arguments)["space_id"] == "dutiful_service"
        for a in legal_agent_actions(state, 0)
    )
    invited = engine.apply(state, _play_intrigue(card, 1)).state
    assert invited.players[0].granted_agent_icon_turn == "emperor"
    action = next(
        a
        for a in legal_agent_actions(invited, 0)
        if dict(a.arguments)["space_id"] == "dutiful_service"
    )
    codec = ActionCodec(BLOODLINES)
    assert codec.decode(codec.encode(action), 0) == action
    placed = apply_agent_action(invited, action).state
    assert "dutiful_service" in placed.players[0].agent_locations


# --- Combat icon (slice 4c-2b) ----------------------------------------------


def test_adaptive_tactics_before_placement_opens_a_deployment_at_any_space() -> None:
    from dune_imperium.rules.combat_deployment import legal_combat_deployments

    card = _intrigue("adaptive_tactics")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,), hand=STARTERS[4:10], resources=Resources(spice=1)
    )
    played = engine.apply(_state(owner), _play_intrigue(card)).state
    assert played.players[0].combat_icon_turn is True
    assert played.players[0].troops_garrison == 4
    # Dutiful Service is not a Combat space, yet the icon opens the window:
    # the recruited troop plus up to two from the garrison.
    visited = _play(played, STARTERS[4], "dutiful_service")
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(visited, 0)
    ] == [1, 2, 3]


def test_adaptive_tactics_during_the_reveal_deploys_with_strength() -> None:
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_deployment,
        legal_reveal_deployments,
    )

    card = _intrigue("adaptive_tactics")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,),
        hand=(STARTERS[4],),
        resources=Resources(spice=1),
        commanders_garrison=1,
    )
    revealed = _reveal(_state(owner))
    assert legal_reveal_deployments(revealed, 0) == ()
    played = engine.apply(revealed, _play_intrigue(card)).state
    context = _reveal_context(played)
    assert context["combat_deployment"] is True
    assert context["reveal_troops_recruited"] == 1
    counts = {
        (a.action_id, dict(a.arguments)["count"])
        for a in legal_reveal_deployments(played, 0)
    }
    # One recruited troop plus two from the garrison: three troops, or the
    # Commander as one of the garrison units.
    assert counts == {
        ("deploy_troops", 1),
        ("deploy_troops", 2),
        ("deploy_troops", 3),
        ("deploy_commanders", 1),
    }
    deployed = apply_reveal_deployment(
        played, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert deployed.players[0].commanders_conflict == 1
    sword_strength = _reveal_context(deployed)["sword_strength"]
    assert isinstance(sword_strength, int)
    assert deployed.players[0].combat_strength == 2 + sword_strength
    more = apply_reveal_deployment(
        deployed, DomainAction("deploy_troops", 0, (("count", 2),))
    ).state
    assert more.players[0].troops_conflict == 2
    assert _reveal_context(more)["reveal_units_deployed"] == 3
    assert legal_reveal_deployments(more, 0) == ()


def test_elite_forces_rewards_an_emperor_trash_from_hand() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_trash,
        legal_agent_card_trash_actions,
    )
    from dune_imperium.rules.combat_deployment import legal_combat_deployments

    card = _card("elite_forces")
    emperor = _card("quash_rebellion")
    state = _play(
        _state(_owner(hand=(card, emperor, STARTERS[4]))), card, "dutiful_service"
    )
    actions = legal_agent_card_trash_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_trash"
    assert {dict(a.arguments)["card_id"] for a in actions[1:]} == {emperor, STARTERS[4]}
    trash_emperor = next(
        a for a in actions[1:] if dict(a.arguments)["card_id"] == emperor
    )
    rewarded = apply_agent_card_trash(state, trash_emperor).state
    keys = {
        dict(a.arguments)["effect"] for a in legal_agent_card_icon_actions(rewarded, 0)
    }
    assert keys == {"intrigue", "troops"}
    assert (
        dict(rewarded.decision_stack[-1].context)["pending_combat_deployment"] is True
    )
    # Resolve the troop icon: the recruit may then deploy (Combat icon).
    troops = next(
        a
        for a in legal_agent_card_icon_actions(rewarded, 0)
        if dict(a.arguments)["effect"] == "troops"
    )
    resolved = resolve_agent_card_icon(rewarded, troops).state
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(resolved, 0)
    ] == [1, 2, 3]

    plain = next(a for a in actions[1:] if dict(a.arguments)["card_id"] == STARTERS[4])
    nothing = apply_agent_card_trash(state, plain).state
    assert legal_agent_card_icon_actions(nothing, 0) == ()
    assert (
        dict(nothing.decision_stack[-1].context)["pending_combat_deployment"] is False
    )


def test_disruption_tactics_forces_an_enemy_unit_back_and_trashes_for_the_icon() -> (
    None
):
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_opponent_retreat,
        legal_agent_card_opponent_retreat_actions,
    )
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_card_trash,
        legal_reveal_card_trash_actions,
        legal_reveal_deployments,
    )

    card = _card("disruption_tactics")
    enemy = replace(
        PlayerState(player_id=1),
        troops_supply=8,
        troops_conflict=1,
        commanders_conflict=1,
        combat_strength=4,
    )
    base = _state(_owner(hand=(card,)))
    base = replace(base, players=(base.players[0], enemy, *base.players[2:]))
    state = _play(base, card)
    actions = legal_agent_card_opponent_retreat_actions(state, 0)
    assert {tuple(dict(a.arguments).items()) for a in actions} == {
        (("player", 1),),
        (("commanders", 1), ("player", 1)),
    }
    pushed = apply_agent_card_opponent_retreat(state, actions[1]).state
    assert pushed.players[1].commanders_conflict == 0
    assert pushed.players[1].commanders_garrison == 1
    assert pushed.players[1].combat_strength == 2

    revealed = _reveal(_state(_owner(hand=(card,), troops_garrison=3)))
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"] == "may_trash_self_for_combat_icon"
    )
    trash_actions = legal_reveal_card_trash_actions(revealed, 0)
    assert [a.action_id for a in trash_actions] == [
        "decline_reveal_card_trash",
        "trash_reveal_card",
    ]
    trashed = apply_reveal_card_trash(revealed, trash_actions[1]).state
    assert card in trashed.players[0].trashed
    assert [
        dict(a.arguments)["count"] for a in legal_reveal_deployments(trashed, 0)
    ] == [1, 2]


# --- Bloodlines Imperium (slice 4d-1) --------------------------------------


def test_arrakis_observer_discard_places_a_deep_cover_spy() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_spy_action,
        legal_agent_card_spy_actions,
    )

    card = _card("arrakis_observer")
    guild = _card("guild_envoy")
    filler = STARTERS[4]
    rival = replace(
        PlayerState(player_id=1),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    base = _state(
        _owner(
            hand=(card, guild, filler),
            spies_supply=2,
            spy_post_ids=("landsraad-assembly-hall-gather-support",),
        )
    )
    base = replace(base, players=(base.players[0], rival, *base.players[2:]))
    state = _play(base, card, "arrakeen")
    actions = legal_agent_card_discard_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_discard"
    discard_guild = next(
        a for a in actions[1:] if dict(a.arguments)["card_id"] == guild
    )
    discarded = apply_agent_card_discard(state, discard_guild).state
    assert discarded.players[0].resources.spice == 2
    # The Spy with Deep Cover may share a post with a rival, never with its
    # own Spy; the discard offer is spent.
    assert legal_agent_card_discard_actions(discarded, 0) == ()
    posts = {
        dict(a.arguments)["post_id"] for a in legal_agent_card_spy_actions(discarded, 0)
    }
    assert "emperor-sardaukar-dutiful-service" in posts
    assert "landsraad-assembly-hall-gather-support" not in posts
    placed = apply_agent_card_spy_action(
        discarded,
        DomainAction(
            action_id="place_agent_card_spy",
            actor=0,
            arguments=(("post_id", "emperor-sardaukar-dutiful-service"),),
        ),
    ).state
    assert "emperor-sardaukar-dutiful-service" in placed.players[0].spy_post_ids
    assert legal_agent_card_spy_actions(placed, 0) == ()

    # A non-Guild discard still buys the Spy, without spice.
    discard_plain = next(
        a for a in actions[1:] if dict(a.arguments)["card_id"] == filler
    )
    plain = apply_agent_card_discard(state, discard_plain).state
    assert plain.players[0].resources.spice == 0
    assert legal_agent_card_spy_actions(plain, 0) != ()


def test_arrakis_observer_recalls_a_spy_for_three_swords() -> None:
    from dune_imperium.rules.reveal_turn import apply_reveal_spy_action

    card = _card("arrakis_observer")
    owner = _owner(
        hand=(card,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        troops_supply=8,
        troops_conflict=1,
        combat_strength=2,
    )
    revealed = _reveal(_state(owner))
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"]
        == "may_recall_spy_for_three_strength"
    )
    actions = legal_reveal_spy_actions(revealed, 0)
    assert [a.action_id for a in actions] == [
        "decline_reveal_spy_recall",
        "recall_spy_for_reveal",
    ]
    recalled = apply_reveal_spy_action(revealed, actions[1]).state
    assert recalled.players[0].spy_post_ids == ()
    assert recalled.players[0].combat_strength == 2 + 3
    assert _reveal_context(recalled)["strength"] == 2 + 3
    assert _reveal_context(recalled)["optional_sword_strength"] == 3
    # No Spy on the board: the arrow cost cannot be paid, no choice opens.
    none = _reveal(_state(_owner(hand=(card,), spies_supply=3)))
    assert none.decision_stack[-1].kind == "reveal"


def test_bombast_command_pays_three_solari_and_trashes_itself() -> None:
    card = _card("bombast")
    revealed = _reveal(_state(_six_persuasion_hand(card)))
    owner = revealed.players[0]
    assert owner.resources.solari == 3
    assert card in owner.trashed
    assert card not in owner.in_play
    below = _reveal(_state(_owner(hand=(card,))))
    assert below.players[0].resources.solari == 0
    assert card in below.players[0].in_play


def test_engineered_miracle_discards_for_water_and_commands_a_row_card() -> None:
    from dune_imperium.rules.acquisition import (
        apply_reveal_command_acquisition,
        legal_reveal_command_acquisition_actions,
    )

    card = _card("engineered_miracle")
    filler = STARTERS[4]
    state = _play(_state(_owner(hand=(card, filler))), card)
    discard = next(
        a
        for a in legal_agent_card_discard_actions(state, 0)
        if a.action_id == "discard_agent_card"
    )
    assert (
        apply_agent_card_discard(state, discard).state.players[0].resources.water == 1
    )

    row = (_card("guild_envoy"), _card("sandwalk", 1))
    base = replace(_state(_six_persuasion_hand(card)), imperium_row=row)
    revealed = _reveal(base)
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"]
        == "command_may_trash_self_to_acquire_row_card"
    )
    actions = legal_reveal_command_acquisition_actions(revealed, 0)
    assert actions[0].action_id == "decline_command_acquisition"
    assert {dict(a.arguments)["instance_id"] for a in actions[1:]} == set(row)
    acquired = apply_reveal_command_acquisition(revealed, actions[1]).state
    owner = acquired.players[0]
    assert card in owner.trashed
    assert row[0] in owner.discard_pile
    assert row[0] not in acquired.imperium_row
    assert acquired.decision_stack[-1].kind == "reveal"
    # Persuasion is untouched: the card came for free.
    assert _reveal_context(acquired)["persuasion"] == 7
    declined = apply_reveal_command_acquisition(revealed, actions[0]).state
    assert card in declined.players[0].in_play
    # Below Command the choice waits; an empty Row offers nothing.
    assert _reveal(_state(_owner(hand=(card,)))).decision_stack[-1].kind == "reveal"
    assert _reveal(_state(_six_persuasion_hand(card))).decision_stack[-1].kind == (
        "reveal"
    )


def test_southern_faith_draws_or_takes_bene_gesserit_influence_with_a_bond() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_influence,
        legal_agent_card_influence_actions,
    )

    card = _card("southern_faith")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    assert legal_agent_card_influence_actions(state, 0) == ()
    before = len(state.players[0].hand)
    assert len(resolve_agent_card_effect(state).state.players[0].hand) == before + 1

    bonded = _play(
        _state(_owner(hand=(card,), in_play=(_card("branching_path"),))),
        card,
        "arrakeen",
    )
    actions = legal_agent_card_influence_actions(bonded, 0)
    assert [a.action_id for a in actions] == [
        "resolve_agent_card_effect",
        "choose_agent_card_influence",
    ]
    assert dict(actions[1].arguments)["faction"] == "bene_gesserit"
    gained = apply_agent_card_influence(bonded, actions[1]).state
    assert gained.players[0].influence.bene_gesserit == 1
    assert len(gained.players[0].hand) == len(bonded.players[0].hand)

    revealed = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(revealed)["persuasion"] == 1
    assert _reveal_context(revealed)["sword_strength"] == 2
    assert revealed.players[0].resources.spice == 0
    commanded = _reveal(_state(_six_persuasion_hand(card)))
    assert commanded.players[0].resources.spice == 2


def test_possible_futures_pays_both_halves_with_a_bene_gesserit_bond() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_influence,
        legal_agent_card_influence_actions,
    )

    card = _card("possible_futures")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    actions = legal_agent_card_influence_actions(state, 0)
    assert actions[0].action_id == "resolve_agent_card_effect"
    assert len(actions) == 1 + 4
    # Arrakeen already recruited one troop.
    garrison = state.players[0].troops_garrison
    troops = resolve_agent_card_effect(state).state.players[0]
    assert troops.troops_garrison == garrison + 2
    assert troops.influence.emperor == 0
    only_influence = apply_agent_card_influence(state, actions[1]).state.players[0]
    assert only_influence.troops_garrison == garrison
    assert only_influence.influence.emperor == 1

    bonded = _play(
        _state(_owner(hand=(card,), in_play=(_card("branching_path"),))),
        card,
        "arrakeen",
    )
    actions = legal_agent_card_influence_actions(bonded, 0)
    assert all(a.action_id == "choose_agent_card_influence" for a in actions)
    both = apply_agent_card_influence(bonded, actions[0]).state
    assert both.players[0].troops_garrison == garrison + 2
    assert both.players[0].influence.emperor == 1
    assert dict(both.decision_stack[-1].context)["troops_recruited"] == 1 + 2

    revealed = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(revealed)["persuasion"] == 2
    assert revealed.players[0].resources.water == 1 + 1


# --- Bloodlines Imperium (slice 4d-2) --------------------------------------


def test_urgent_shigawire_boosts_the_next_bene_gesserit_card() -> None:
    from dune_imperium.rules.agent_turn import legal_agent_actions as legal

    card = _card("urgent_shigawire")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    armed = resolve_agent_card_effect(state).state
    assert armed.players[0].bene_gesserit_boost_pending is True

    # Branching Path prints Bene Gesserit + Landsraad; boosted it reaches a
    # City space too, and its Agent box draws a card.
    bene_gesserit = _card("branching_path")
    guild = _card("guild_envoy")
    boosted = _state(
        _owner(hand=(bene_gesserit, guild), bene_gesserit_boost_pending=True)
    )
    spaces = {
        dict(a.arguments)["space_id"]
        for a in legal(boosted, 0)
        if dict(a.arguments)["card_id"] == bene_gesserit
    }
    assert "arrakeen" in spaces
    # A non-Bene Gesserit card keeps its printed icons.
    guild_spaces = {
        dict(a.arguments)["space_id"]
        for a in legal(boosted, 0)
        if dict(a.arguments)["card_id"] == guild
    }
    assert "arrakeen" not in guild_spaces
    played = _play(boosted, bene_gesserit, "arrakeen")
    owner = played.players[0]
    assert owner.bene_gesserit_boost_pending is False
    # Arrakeen's own draw plus the boost's draw: the hand lost one card and
    # gained two.
    assert len(owner.hand) == 2 - 1 + 2


def test_sardaukar_standard_acquires_the_bank_commander_when_trashed() -> None:
    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.rules.sardaukar import (
        apply_skill_choice,
        begin_skill_choice,
        legal_skill_choice_actions,
    )

    card = _card("sardaukar_standard")
    skills = skill_tile_instance_ids()
    base = replace(
        _state(_owner(hand=(card,))),
        skill_face_up=skills[:4],
        skill_stack=skills[4:],
    )
    state = _play(base, card, "arrakeen")
    result = trash_personal_card(state, 0, card, source="test")
    # The trashing effect still owns the top frame; the choice is queued and
    # the engine opens it afterwards.
    assert result.state.decision_stack[-1].kind == "agent_effects"
    assert result.state.pending_skill_choices == ((0, card, "test:trash:" + card),)
    opened = begin_skill_choice(result.state).state
    assert opened.pending_skill_choices == ()
    frame = opened.decision_stack[-1]
    assert frame.kind == "skill_choice"
    actions = legal_skill_choice_actions(opened, 0)
    assert len(actions) == len({dict(a.arguments)["skill_id"] for a in actions})
    chosen = apply_skill_choice(opened, actions[0]).state
    owner = chosen.players[0]
    assert chosen.sardaukar_commanders_bank == 0
    assert owner.commanders_garrison == 1
    assert len(owner.skill_ids) == 1
    assert chosen.decision_stack[-1].kind == "agent_effects"
    # Recruited this turn: it joins the basic deployment count.
    assert dict(chosen.decision_stack[-1].context)["troops_recruited"] == 1 + 1

    empty = replace(state, sardaukar_commanders_bank=0)
    nothing = trash_personal_card(empty, 0, card, source="test")
    assert nothing.state.pending_skill_choices == ()
    assert nothing.events[-1].kind == "sardaukar_commander_unavailable"

    # Every face-up Skill already held: the Commander comes without a Skill
    # and no choice frame opens (OQ-031, OQ-035).
    held = replace(
        state,
        skill_face_up=(skills[1], skills[3]),
        players=replace_player(
            state.players, replace(state.players[0], skill_ids=(skills[0], skills[2]))
        ),
    )
    queued = trash_personal_card(held, 0, card, source="test").state
    direct = begin_skill_choice(queued)
    assert direct.state.decision_stack[-1].kind == "agent_effects"
    assert direct.state.sardaukar_commanders_bank == 0
    assert direct.state.players[0].commanders_garrison == 1
    assert len(direct.state.players[0].skill_ids) == 2
    assert direct.events[0].kind == "sardaukar_commander_acquired"


def test_litany_against_fear_draws_and_passes_the_turn() -> None:
    from dune_imperium.rules.agent_turn import (
        apply_turn_start_card,
        legal_turn_start_card_actions,
    )

    card = _card("litany_against_fear")
    state = _state(_owner(hand=(card,)))
    actions = legal_turn_start_card_actions(state, 0)
    assert [dict(a.arguments)["card_id"] for a in actions] == [card]
    assert actions[0] in UprisingRulesEngine().legal_actions(state, 0)
    # No Agent icons: the card cannot be sent anywhere.
    assert legal_agent_actions(state, 0) == ()
    passed = apply_turn_start_card(state, actions[0]).state
    owner = passed.players[0]
    assert card in owner.in_play
    assert len(owner.hand) == 1
    assert owner.agents_available == 2
    assert owner.has_revealed is False
    frame = passed.decision_stack[-1]
    assert frame.kind == "turn"
    assert dict(frame.context)["turn_owner"] == 1


def test_delivery_logistics_borrows_its_contract_icons() -> None:
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_persuasion_or_contract,
        legal_reveal_persuasion_or_contract_actions,
    )

    card = _card("delivery_logistics")
    none = _state(_owner(hand=(card,)), CHOAM_BLOODLINES)
    assert legal_agent_actions(none, 0) == ()
    contracted = _state(
        _owner(
            hand=(card,),
            active_contract_ids=("contract:arrakeen_i", "contract:harvest_3"),
        ),
        CHOAM_BLOODLINES,
    )
    spaces = {dict(a.arguments)["space_id"] for a in legal_agent_actions(contracted, 0)}
    assert {"arrakeen", "imperial_basin"} <= spaces
    assert "assembly_hall" not in spaces

    revealed = _reveal(
        replace(
            _state(_owner(hand=(card,)), CHOAM_BLOODLINES),
            face_up_contract_ids=("contract:heighliner_i",),
        )
    )
    frame = revealed.decision_stack[-1]
    assert dict(frame.context)["reveal_choice_effect"] == "persuasion_or_contract"
    actions = legal_reveal_persuasion_or_contract_actions(revealed, 0)
    assert [a.action_id for a in actions] == [
        "gain_reveal_persuasion",
        "take_reveal_contract",
    ]
    persuaded = apply_reveal_persuasion_or_contract(revealed, actions[0]).state
    assert _reveal_context(persuaded)["persuasion"] == 1
    assert persuaded.decision_stack[-1].kind == "reveal"
    contracted_reveal = apply_reveal_persuasion_or_contract(revealed, actions[1]).state
    assert contracted_reveal.decision_stack[-1].kind == "contract_market"
    assert _reveal_context(contracted_reveal)["persuasion"] == 0


def test_choam_demands_completes_a_contract_and_trashes_for_influence() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_contract_completion,
        legal_agent_card_contract_completion_actions,
    )

    card = _card("choam_demands")
    idle = _play(_state(_owner(hand=(card,)), CHOAM_BLOODLINES), card, "arrakeen")
    assert legal_agent_card_contract_completion_actions(idle, 0) == ()
    assert (
        resolve_agent_card_effect(idle).events[0].kind
        == "agent_card_effect_unavailable"
    )

    contracted = _play(
        _state(
            _owner(hand=(card,), active_contract_ids=("contract:heighliner_ii",)),
            CHOAM_BLOODLINES,
        ),
        card,
        "arrakeen",
    )
    actions = legal_agent_card_contract_completion_actions(contracted, 0)
    assert [dict(a.arguments)["instance_id"] for a in actions] == [
        "contract:heighliner_ii"
    ]
    garrison = contracted.players[0].troops_garrison
    completed = apply_agent_card_contract_completion(contracted, actions[0]).state
    owner = completed.players[0]
    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == ("contract:heighliner_ii",)
    assert owner.troops_garrison == garrison + 2
    assert owner.contracts_completed_turn == 1
    context = dict(completed.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert context["troops_recruited"] == 1 + 2

    four = (
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
        "contract:harvest_3",
        "contract:harvest_4",
    )
    revealed = _reveal(
        _state(_owner(hand=(card,), completed_contract_ids=four), CHOAM_BLOODLINES)
    )
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"]
        == "may_trash_self_for_four_influence_if_four_contracts"
    )
    actions = legal_reveal_card_trash_actions(revealed, 0)
    assert [a.action_id for a in actions] == [
        "decline_reveal_card_trash",
        "trash_reveal_card",
    ]
    trashed = apply_reveal_card_trash(revealed, actions[1]).state
    owner = trashed.players[0]
    assert card in owner.trashed
    assert owner.influence == Influence(
        emperor=1, spacing_guild=1, bene_gesserit=1, fremen=1
    )
    below = _reveal(
        _state(_owner(hand=(card,), completed_contract_ids=four[:3]), CHOAM_BLOODLINES)
    )
    assert below.decision_stack[-1].kind == "reveal"


# --- Bloodlines slice 4d-3: Holy War, False Orders, Coercive Negotiation --


ASSEMBLY_POST = "landsraad-assembly-hall-gather-support"


def test_holy_war_makes_each_opponent_lose_a_unit_and_move_its_spy() -> None:
    from dune_imperium.rules.spy_moves import apply_spy_move, legal_spy_move_actions
    from dune_imperium.rules.unit_loss import (
        apply_unit_loss,
        legal_unit_loss_actions,
    )

    card = _card("holy_war")
    watcher = replace(
        PlayerState(player_id=1),
        spies_supply=2,
        spy_post_ids=(ASSEMBLY_POST,),
        troops_supply=8,
        troops_garrison=2,
        troops_conflict=2,
        commanders_supply=0,
        commanders_conflict=1,
        combat_strength=6,
    )
    garrisoned = replace(PlayerState(player_id=2), troops_supply=11, troops_garrison=1)
    empty = replace(PlayerState(player_id=3), troops_supply=12, troops_garrison=0)
    base = _state(_owner(hand=(card,)))
    base = replace(base, players=(base.players[0], watcher, garrisoned, empty))
    state = _play(base, card, "assembly_hall")
    result = resolve_agent_card_effect(state)
    kinds = [event.kind for event in result.events]
    assert "unit_lost" in kinds and "unit_loss_unavailable" in kinds
    # Seat 2 lost its only-zone troop at once; seat 3 had nothing to lose.
    assert result.state.players[2].troops_garrison == 0
    assert result.state.players[2].troops_supply == 12
    # Seat 1 moves its Spy, then chooses the zone; both frames are on top.
    stack = result.state.decision_stack
    assert [frame.kind for frame in stack[-2:]] == [
        "opponent_unit_loss",
        "opponent_spy_move",
    ]
    moves = legal_spy_move_actions(result.state, 1)
    targets = {dict(a.arguments)["post_id"] for a in moves}
    assert ASSEMBLY_POST not in targets and targets
    moved = apply_spy_move(result.state, moves[0]).state
    assert ASSEMBLY_POST not in moved.players[1].spy_post_ids
    assert len(moved.players[1].spy_post_ids) == 1
    # The loser picks the zone and the unit kind (OQ-036).
    actions = legal_unit_loss_actions(moved, 1)
    assert [tuple(a.arguments) for a in actions] == [
        (("zone", "garrison"),),
        (("zone", "conflict"),),
        (("commanders", 1), ("zone", "conflict")),
    ]
    lost = apply_unit_loss(moved, actions[2]).state
    assert lost.players[1].commanders_conflict == 0
    assert lost.players[1].commanders_supply == 1
    assert lost.players[1].troops_conflict == 2
    assert lost.players[1].combat_strength == 4
    # Nothing else was pending in the Agent turn, so the next turn opened.
    assert lost.decision_stack[-1].kind == "turn"


def test_holy_war_reveal_recruits_and_bonds_for_the_combat_icon() -> None:
    card = _card("holy_war")
    plain = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(plain)["persuasion"] == 1
    assert plain.players[0].troops_garrison == 3 + 1
    assert _reveal_context(plain)["combat_deployment"] is False
    bonded = _reveal(_state(_owner(hand=(card,), in_play=(_card("desert_power"),))))
    assert _reveal_context(bonded)["combat_deployment"] is True


def test_false_orders_moves_watching_spies_then_places_one() -> None:
    from dune_imperium.rules.intrigue import legal_intrigue_play_actions
    from dune_imperium.rules.spy_moves import (
        apply_spy_move,
        apply_spy_placement,
        legal_spy_move_actions,
        legal_spy_placement_actions,
    )

    card = _intrigue("false_orders")
    watcher = replace(
        PlayerState(player_id=1), spies_supply=2, spy_post_ids=(ASSEMBLY_POST,)
    )
    landsraad = _card("branching_path")
    base = _state(_owner(hand=(landsraad,), intrigue_cards=(card,)))
    base = replace(base, players=(base.players[0], watcher, *base.players[2:]))
    # Before any placement there is no "space where you sent an Agent".
    assert _play_intrigue(card) not in legal_intrigue_play_actions(base, 0)
    state = _play(base, landsraad, "assembly_hall")
    assert _play_intrigue(card) in legal_intrigue_play_actions(state, 0)
    engine = UprisingRulesEngine()
    played = engine.apply(state, _play_intrigue(card)).state
    assert [frame.kind for frame in played.decision_stack[-2:]] == [
        "spy_placement",
        "opponent_spy_move",
    ]
    moves = legal_spy_move_actions(played, 1)
    moved = apply_spy_move(played, moves[0]).state
    assert ASSEMBLY_POST not in moved.players[1].spy_post_ids
    placements = legal_spy_placement_actions(moved, 0)
    assert [dict(a.arguments)["post_id"] for a in placements] == [ASSEMBLY_POST]
    placed = apply_spy_placement(moved, placements[0]).state
    assert ASSEMBLY_POST in placed.players[0].spy_post_ids
    assert placed.decision_stack[-1].kind == "agent_effects"


def test_coercive_negotiation_reveals_three_contracts_on_a_big_deployment() -> None:
    from dune_imperium.content.uprising.contracts import contract_instance_ids
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.rules.intrigue_triggers import (
        apply_trigger_contract_action,
        legal_trigger_contract_actions,
        offer_deployment_triggers,
    )

    card = _intrigue("coercive_negotiation")
    bank = contract_instance_ids()[:5]
    base = replace(
        _state(
            _owner(intrigue_faceup=(card,), units_deployed_turn=3), CHOAM_BLOODLINES
        ),
        contract_bank=bank,
    )
    offered = offer_deployment_triggers(RuleResult(state=base)).state
    frame = offered.decision_stack[-1]
    assert frame.kind == "intrigue_trigger_contract"
    actions = legal_trigger_contract_actions(offered, 0)
    assert actions[0].action_id == "decline_intrigue_contract_trigger"
    assert [dict(a.arguments)["instance_id"] for a in actions[1:]] == list(bank[:3])
    taken = apply_trigger_contract_action(offered, actions[2]).state
    owner = taken.players[0]
    assert owner.active_contract_ids == (bank[1],)
    assert owner.intrigue_faceup == ()
    assert card in taken.intrigue_discard
    assert taken.contract_bank == bank[3:]
    assert taken.contract_trash == (bank[0], bank[2])
    # Declining keeps the card face up for a later qualifying turn (OQ-016).
    declined = apply_trigger_contract_action(offered, actions[0]).state
    assert declined.players[0].intrigue_faceup == (card,)
    # Without the CHOAM bank the trigger has nothing to reveal.
    quiet = offer_deployment_triggers(
        RuleResult(state=replace(base, contract_bank=()))
    ).state
    assert quiet.decision_stack[-1].kind == "turn"


def test_engineered_miracle_command_lapses_once_the_card_left_play() -> None:
    # The Command choice waits in the freely ordered Reveal; if another
    # effect trashes Engineered Miracle first, its box can't be activated
    # any more (OQ-022), so only the refusal remains (soak seed 901).
    from dune_imperium.rules.acquisition import (
        apply_reveal_command_acquisition,
        legal_reveal_command_acquisition_actions,
    )

    card = _card("engineered_miracle")
    row = (_card("guild_envoy"),)
    revealed = _reveal(replace(_state(_six_persuasion_hand(card)), imperium_row=row))
    assert len(legal_reveal_command_acquisition_actions(revealed, 0)) == 2
    gone = trash_personal_card(revealed, 0, card, source="test").state
    actions = legal_reveal_command_acquisition_actions(gone, 0)
    assert [a.action_id for a in actions] == ["decline_command_acquisition"]
    declined = apply_reveal_command_acquisition(gone, actions[0]).state
    assert declined.decision_stack[-1].kind == "reveal"
    assert declined.imperium_row == row


# --- Ruthless Leadership (Bloodlines promo, card face) ------------------------

PROMO_BLOODLINES = RulesetConfig(bloodlines=True, promo_cards=True)


def test_ruthless_leadership_is_transcribed_and_needs_both_options() -> None:
    from dune_imperium.content.uprising.imperium import (
        IMPERIUM_CARDS_BY_ID,
        imperium_deck_instance_ids,
    )

    entry = IMPERIUM_CARDS_BY_ID["ruthless_leadership"]
    assert entry.promo and entry.bloodlines_only and entry.play_data_complete
    assert entry.card.catalog_url is None
    assert (entry.acquisition_cost, entry.reveal_persuasion, entry.reveal_strength) == (
        4,
        1,
        1,
    )
    assert [icon.value for icon in entry.agent_icons] == ["city", "spice_trade"]
    (command,) = entry.reveal_effects
    assert command.requires_command and command.grants_combat_icon
    card = _card("ruthless_leadership")
    # Outside the retail decks: dealt only with the promo option and the
    # expansion together, since its Agent box reads the Commanders.
    assert card not in imperium_deck_instance_ids(False, True)
    assert card not in imperium_deck_instance_ids(False, False, bloodlines=True)
    assert card in imperium_deck_instance_ids(False, True, bloodlines=True)
    assert card in imperium_deck_instance_ids(
        True, True, bloodlines=True, tech_module=True
    )
    assert PROMO_BLOODLINES.identifier == "uprising-4p-base+promo+bloodlines"


def test_ruthless_leadership_trashes_up_to_two_cards_with_a_commander() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_trash,
        legal_agent_card_trash_actions,
    )

    card = _card("ruthless_leadership")
    filler = STARTERS[4]
    discarded = STARTERS[5]
    owner = _owner(
        hand=(card, filler), discard_pile=(discarded,), commanders_conflict=1
    )
    state = _play(_state(owner, PROMO_BLOODLINES), card, "imperial_basin")
    # Two black trash icons: each an optional trash from hand, discard pile
    # or in play [Main p. 20], offered one at a time.
    actions = legal_agent_card_trash_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_trash"
    assert {dict(a.arguments)["card_id"] for a in actions[1:]} == {
        card,
        filler,
        discarded,
    }
    first = next(a for a in actions[1:] if dict(a.arguments)["card_id"] == discarded)
    once = apply_agent_card_trash(state, first).state
    assert discarded in once.players[0].trashed
    context = dict(once.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert context["trashes_remaining"] == 1
    again = legal_agent_card_trash_actions(once, 0)
    assert again[0].action_id == "decline_agent_card_trash"
    assert {dict(a.arguments)["card_id"] for a in again[1:]} == {card, filler}
    second = next(a for a in again[1:] if dict(a.arguments)["card_id"] == card)
    twice = apply_agent_card_trash(once, second).state
    assert {discarded, card} <= set(twice.players[0].trashed)
    assert legal_agent_card_trash_actions(twice, 0) == ()
    assert all("trashes_remaining" not in dict(f.context) for f in twice.decision_stack)
    # Declining after the first trash closes the box with the card in play.
    declined = apply_agent_card_trash(once, again[0]).state
    assert legal_agent_card_trash_actions(declined, 0) == ()
    assert card in declined.players[0].in_play
    assert declined.players[0].trashed == (discarded,)


def test_ruthless_leadership_without_a_commander_resolves_without_effect() -> None:
    from dune_imperium.rules.agent_effect_frame import legal_agent_effect_frame_actions
    from dune_imperium.rules.agent_effects import legal_agent_card_trash_actions

    card = _card("ruthless_leadership")
    state = _play(
        _state(_owner(hand=(card, STARTERS[4])), PROMO_BLOODLINES),
        card,
        "imperial_basin",
    )
    # The condition is judged when the box resolves (OQ-028); a Commander in
    # the garrison or the supply does not count.
    garrisoned = replace_player(
        state.players, replace(state.players[0], commanders_garrison=1)
    )
    state = replace(state, players=garrisoned)
    assert legal_agent_card_trash_actions(state, 0) == ()
    # The stalled mandatory box is not offered to fizzle on demand; only the
    # explicit turn end resolves it (designer ruling, OQ-057).
    resolve = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    frame_actions = legal_agent_effect_frame_actions(state, 0)
    assert resolve not in frame_actions
    finish = DomainAction(action_id="finish_agent_turn", actor=0)
    assert finish not in frame_actions  # the Maker harvest is still pending
    harvested = UprisingRulesEngine().apply(
        state,
        next(a for a in frame_actions if a.action_id == "harvest_maker_spice"),
    ).state
    assert finish in legal_agent_effect_frame_actions(harvested, 0)
    result = resolve_agent_card_effect(state)
    kinds = [e.kind for e in result.events if e.kind.startswith("agent_card_effect")]
    assert kinds == ["agent_card_effect_unavailable"]
    assert result.state.players[0].trashed == ()
    assert card in result.state.players[0].in_play


def test_ruthless_leadership_reveal_gives_a_sword_and_commands_the_combat_icon() -> (
    None
):
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    card = _card("ruthless_leadership")
    below = _reveal(_state(_owner(hand=(card,)), PROMO_BLOODLINES))
    context = _reveal_context(below)
    assert context["persuasion"] == 1
    assert context["sword_strength"] == 1
    assert context["combat_deployment"] is False
    assert legal_reveal_deployments(below, 0) == ()
    # Command (6+): the Combat icon opens this Reveal's deployment window
    # for up to two garrison units [Bloodlines pp. 5, 12].
    commanded = _reveal(_state(_six_persuasion_hand(card), PROMO_BLOODLINES))
    context = _reveal_context(commanded)
    assert context["persuasion"] == 2 + 2 + 2 + 1
    assert context["combat_deployment"] is True
    counts = {
        (a.action_id, dict(a.arguments)["count"])
        for a in legal_reveal_deployments(commanded, 0)
    }
    assert counts == {("deploy_troops", 1), ("deploy_troops", 2)}


def test_ruthless_leadership_round_trips_and_is_dealt_in_random_games() -> None:
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.simulation import run_random_game

    codec = ActionCodec(PROMO_BLOODLINES)
    # v97 Occupation bundle, v99 Duncan recall, v100 skip + Change Allegiances.
    assert codec.size == 10159 + 292 + 1 + 1 + 1 + 2 + 1  # v103 separate lines
    action = DomainAction(
        action_id="trash_agent_card",
        actor=2,
        arguments=(("card_id", _card("ruthless_leadership")),),
    )
    assert codec.decode(codec.encode(action), actor=2) == action
    for config in (
        PROMO_BLOODLINES,
        RulesetConfig(
            choam_module=True, promo_cards=True, bloodlines=True, tech_module=True
        ),
    ):
        report = run_checked_game(
            config,
            game_seed=41,
            policy_seed=900_041,
            privacy_interval=10,
            soundness_interval=10,
            engine=UprisingRulesEngine(leader_ids=LEADERS),
        )
        assert report.rounds >= 1
        state = run_random_game(UprisingRulesEngine(), config, 41, 141).state
        assert state.phase is GamePhase.FINISHED
        dealt = {
            instance.split(":")[1]
            for instance in (
                *state.imperium_deck,
                *state.imperium_row,
                *state.imperium_removed,
                *(
                    card
                    for player in state.players
                    for card in (
                        *player.hand,
                        *player.deck,
                        *player.discard_pile,
                        *player.in_play,
                        *player.trashed,
                    )
                ),
            )
        }
        assert "ruthless_leadership" in dealt
