"""Tests for the three Uprising promo Imperium cards (card faces; OQ-024..026).

Arrakis Revolt, The Beast's Spoils and Pivotal Gambit are not in the retail
deck; ``RulesetConfig(promo_cards=True)`` shuffles them in. Their Agent
boxes are transcribed from the printed cards (see
``docs/implementation-audits/personal-cards.md``); the rulings the official
documents leave open are recorded in ``docs/rules/open-questions.md``.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS_BY_ID,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.content.uprising.types import (
    BattleIcon,
    PersonalCardAcquisitionEffect,
)
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.acquisition import (
    apply_imperium_acquisition,
    legal_imperium_acquisitions,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_payment,
    apply_agent_card_trash,
    legal_agent_card_icon_actions,
    legal_agent_card_payment_actions,
    legal_agent_card_trash_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.combat import (
    face_up_battle_icons,
    finish_combat,
    resolve_combat_rewards,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import begin_reveal_turn, legal_reveal_actions
from dune_imperium.simulation import run_random_game

PROMO = RulesetConfig(promo_cards=True)


def _promo_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False, True)
        if f":{card_id}:" in instance_id
    )


def _starter(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _turn_state(owner: PlayerState, **state_fields: object) -> GameState:
    fields: dict[str, object] = {
        "current_conflict_ids": ("propaganda",),
        **state_fields,
    }
    return GameState(
        config=PROMO,
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
        **fields,  # type: ignore[arg-type]
    )


def _place(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_agent_action(state, action).state


def _context(state: GameState) -> dict[str, object]:
    return dict(state.decision_stack[-1].context)


def _influence_frames(state: GameState) -> list[DecisionFrame]:
    return [
        frame
        for frame in state.decision_stack
        if frame.kind == "combat_reward_influence"
    ]


def _payment_ids(state: GameState) -> list[str]:
    return [action.action_id for action in legal_agent_card_payment_actions(state, 0)]


# ---------------------------------------------------------------- manifest


def test_promo_cards_are_transcribed_and_opt_in() -> None:
    revolt = IMPERIUM_CARDS_BY_ID["arrakis_revolt"]
    spoils = IMPERIUM_CARDS_BY_ID["the_beast_s_spoils"]
    gambit = IMPERIUM_CARDS_BY_ID["pivotal_gambit"]
    for entry in (revolt, spoils, gambit):
        assert entry.promo and not entry.choam_only and entry.play_data_complete
        assert entry.card.catalog_url is None
    assert (revolt.acquisition_cost, revolt.reveal_persuasion) == (6, 1)
    assert revolt.reveal_strength == 3
    assert revolt.acquisition_effect is PersonalCardAcquisitionEffect.RECRUIT_ONE_TROOP
    assert (spoils.acquisition_cost, spoils.reveal_persuasion) == (3, 0)
    assert spoils.reveal_strength == 3
    assert (gambit.acquisition_cost, gambit.reveal_persuasion) == (3, 1)
    assert gambit.reveal_strength == 2
    assert [icon.value for icon in gambit.agent_icons] == ["fremen", "city"]

    base_ids = set(imperium_deck_instance_ids(False))
    promo_ids = set(imperium_deck_instance_ids(False, True))
    assert {instance.split(":")[1] for instance in promo_ids - base_ids} == {
        "arrakis_revolt",
        "pivotal_gambit",
        "the_beast_s_spoils",
    }
    assert RulesetConfig().identifier == "uprising-4p-base"
    assert PROMO.identifier == "uprising-4p-base+promo"
    assert RulesetConfig(choam_module=True, promo_cards=True).identifier == (
        "uprising-4p-choam+promo"
    )


# ------------------------------------------------------------ Arrakis Revolt


def test_arrakis_revolt_requires_maker_hooks_and_two_spice_to_open() -> None:
    revolt = _promo_instance("arrakis_revolt")
    for owner in (
        PlayerState(player_id=0, hand=(revolt,), resources=Resources(spice=2)),
        PlayerState(
            player_id=0, hand=(revolt,), maker_hooks=True, resources=Resources(spice=1)
        ),
    ):
        placed = _place(_turn_state(owner), "arrakeen")
        # Maker Hooks and the Spice are judged when the payment resolves
        # (OQ-028): Sietch Tabr's supplies or a Maker harvest earlier in the
        # turn can still open it, so only declining is offered until then.
        assert _context(placed)["pending_agent_effect"] is True
        assert legal_agent_card_payment_actions(placed, 0) == (
            DomainAction(action_id="decline_agent_card_payment", actor=0),
        )


def test_arrakis_revolt_offers_wall_removal_only_while_the_wall_stands() -> None:
    revolt = _promo_instance("arrakis_revolt")
    owner = PlayerState(
        player_id=0, hand=(revolt,), maker_hooks=True, resources=Resources(spice=3)
    )
    placed = _place(_turn_state(owner), "arrakeen")
    assert _payment_ids(placed) == [
        "decline_agent_card_payment",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
        "pay_agent_card_spice_for_sandworm",
    ]

    no_wall = _place(_turn_state(owner, shield_wall_present=False), "arrakeen")
    assert _payment_ids(no_wall) == [
        "decline_agent_card_payment",
        "pay_agent_card_spice_for_sandworm",
    ]

    # Against a protected Conflict the worm alone would do nothing [Main
    # p. 20], so only the removal variant is worth offering (OQ-026).
    protected = _place(
        _turn_state(owner, current_conflict_ids=("siege_of_arrakeen",)), "arrakeen"
    )
    assert _payment_ids(protected) == [
        "decline_agent_card_payment",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
    ]


def test_arrakis_revolt_pays_two_spice_to_destroy_the_wall_and_summon() -> None:
    revolt = _promo_instance("arrakis_revolt")
    owner = PlayerState(
        player_id=0, hand=(revolt,), maker_hooks=True, resources=Resources(spice=3)
    )
    placed = _place(
        _turn_state(owner, current_conflict_ids=("siege_of_arrakeen",)), "arrakeen"
    )
    pay = next(
        action
        for action in legal_agent_card_payment_actions(placed, 0)
        if action.action_id == "pay_agent_card_spice_for_sandworm_and_shield_wall"
    )

    result = apply_agent_card_payment(placed, pay)
    after = result.state.players[0]

    assert result.state.shield_wall_present is False
    assert after.resources.spice == 1
    assert after.spice_spent_turn == 2
    assert after.sandworms_conflict == 1
    assert after.units_deployed_turn == 1
    assert _context(result.state)["pending_agent_effect"] is False
    assert _context(result.state)["spice_spent_after_placement"] == 2
    assert [event.kind for event in result.events] == [
        "agent_card_payment_resolved",
        "shield_wall_destroyed",
        "sandworm_deployed",
    ]


def test_arrakis_revolt_may_keep_the_wall_or_decline() -> None:
    revolt = _promo_instance("arrakis_revolt")
    owner = PlayerState(
        player_id=0, hand=(revolt,), maker_hooks=True, resources=Resources(spice=2)
    )
    placed = _place(_turn_state(owner), "arrakeen")
    actions = {
        action.action_id: action
        for action in legal_agent_card_payment_actions(placed, 0)
    }

    kept = apply_agent_card_payment(
        placed, actions["pay_agent_card_spice_for_sandworm"]
    )
    assert kept.state.shield_wall_present is True
    assert kept.state.players[0].sandworms_conflict == 1
    assert kept.state.players[0].resources.spice == 0
    assert [event.kind for event in kept.events] == [
        "agent_card_payment_resolved",
        "sandworm_deployed",
    ]

    declined = apply_agent_card_payment(placed, actions["decline_agent_card_payment"])
    assert declined.state.players[0].resources.spice == 2
    assert declined.state.players[0].sandworms_conflict == 0
    assert declined.events[0].kind == "agent_card_payment_declined"


def test_arrakis_revolt_acquisition_recruits_one_troop() -> None:
    cards = tuple(_starter("convincing_argument") for _ in range(1)) + (
        _starter("dune_the_desert_planet"),
    )
    state = GameState(
        config=PROMO,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=cards, resources=Resources(solari=0)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 10)),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    # Convincing Argument reveals 2 Persuasion, Dune the Desert Planet 1: lift
    # the frame to Arrakis Revolt's cost of 6 through the frame context.
    frame = revealed.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = 6
    lifted = replace(frame, context=tuple(sorted(context.items())))
    revealed = replace(
        revealed, decision_stack=(*revealed.decision_stack[:-1], lifted)
    )
    revolt = _promo_instance("arrakis_revolt")
    instances = imperium_deck_instance_ids(False, True)
    others = tuple(card for card in instances if card != revolt)
    revealed = replace(
        revealed, imperium_row=(revolt, *others[:4]), imperium_deck=others[4:]
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(revealed, 0)
        if dict(action.arguments)["instance_id"] == revolt
    )

    result = apply_imperium_acquisition(revealed, action)

    assert result.state.players[0].discard_pile == (revolt,)
    assert result.state.players[0].troops_garrison == 4
    assert result.state.players[0].troops_supply == 8
    assert [event.kind for event in result.events] == [
        "card_acquired",
        "acquisition_troop_recruited",
    ]


# ---------------------------------------------------------- Pivotal Gambit


def test_pivotal_gambit_trashes_itself_for_a_troop_and_a_wild_pledge() -> None:
    gambit = _promo_instance("pivotal_gambit")
    dagger = _starter("dagger")
    owner = PlayerState(player_id=0, hand=(gambit, dagger))
    placed = _place(_turn_state(owner), "arrakeen")

    actions = legal_agent_card_trash_actions(placed, 0)
    assert [action.action_id for action in actions] == [
        "decline_agent_card_trash",
        "trash_agent_card",
    ]
    assert dict(actions[1].arguments) == {"card_id": gambit}

    result = apply_agent_card_trash(placed, actions[1])
    after = result.state.players[0]

    # The self-trash is the arrow cost; the troop and the first-place pledge
    # are independent reward icons queued for their own actions (OQ-027).
    assert after.trashed == (gambit,)
    assert after.in_play == ()
    assert after.troops_garrison == owner.troops_garrison
    assert result.state.conflict_first_place_influence_bonus == 0
    assert _context(result.state)["pending_agent_icons"] == "troops,pledge"
    assert _context(result.state)["pending_agent_effect"] is True
    assert [event.kind for event in result.events] == ["card_trashed"]

    icon_actions = legal_agent_card_icon_actions(result.state, 0)
    assert [dict(action.arguments)["effect"] for action in icon_actions] == [
        "troops",
        "pledge",
    ]
    pledged = resolve_agent_card_icon(result.state, icon_actions[1])
    assert pledged.state.conflict_first_place_influence_bonus == 1
    assert pledged.events[0].kind == "first_place_influence_pledged"
    recruited = resolve_agent_card_icon(
        pledged.state, legal_agent_card_icon_actions(pledged.state, 0)[0]
    )
    assert recruited.state.players[0].troops_garrison == owner.troops_garrison + 1
    assert _context(recruited.state)["troops_recruited"] == 1
    assert _context(recruited.state)["pending_agent_effect"] is False

    declined = apply_agent_card_trash(placed, actions[0])
    assert declined.state.conflict_first_place_influence_bonus == 0
    assert declined.state.players[0].in_play == (gambit,)


def test_pledged_influence_joins_the_first_place_reward() -> None:
    players = tuple(
        PlayerState(player_id=player, combat_strength=strength)
        for player, strength in enumerate((8, 6, 0, 0))
    )
    state = GameState(
        config=PROMO,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=players,
        current_conflict_ids=("skirmish_crysknife",),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1"),
        conflict_first_place_influence_bonus=1,
    )

    result = resolve_combat_rewards(state)
    baseline = resolve_combat_rewards(
        replace(state, conflict_first_place_influence_bonus=0)
    )

    # The pledge adds exactly one Influence choice to the printed first-place
    # reward, owned by the winner, and is then cleared.
    frames = _influence_frames(result.state)
    assert len(frames) == len(_influence_frames(baseline.state)) + 1
    assert all(
        isinstance(frame.decision, PlayerDecision) and frame.decision.owner == 0
        for frame in frames
    )
    assert result.state.conflict_first_place_influence_bonus == 0

    tied = replace(
        state,
        players=tuple(
            replace(player, combat_strength=8 if player.player_id < 2 else 0)
            for player in players
        ),
    )
    no_winner = resolve_combat_rewards(tied)
    tied_baseline = resolve_combat_rewards(
        replace(tied, conflict_first_place_influence_bonus=0)
    )
    assert len(_influence_frames(no_winner.state)) == len(
        _influence_frames(tied_baseline.state)
    )
    assert no_winner.state.conflict_first_place_influence_bonus == 0


def test_a_sandworm_doubles_the_pledged_influence_like_the_printed_reward() -> None:
    players = tuple(
        PlayerState(
            player_id=player,
            combat_strength=strength,
            sandworms_conflict=1 if player == 0 else 0,
        )
        for player, strength in enumerate((8, 6, 0, 0))
    )
    state = GameState(
        config=PROMO,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=players,
        current_conflict_ids=("skirmish_crysknife",),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1"),
        conflict_first_place_influence_bonus=1,
    )

    result = resolve_combat_rewards(state)
    baseline = resolve_combat_rewards(
        replace(state, conflict_first_place_influence_bonus=0)
    )

    assert len(_influence_frames(result.state)) == (
        len(_influence_frames(baseline.state)) + 2
    )


def test_a_new_conflict_and_combat_cleanup_carry_no_stale_pledge() -> None:
    players = tuple(
        PlayerState(player_id=player, combat_strength=strength)
        for player, strength in enumerate((8, 6, 0, 0))
    )
    state = GameState(
        config=PROMO,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=players,
        current_conflict_ids=("skirmish_crysknife",),
        combat_intrigue_complete=True,
        combat_rewards_resolved=True,
    )
    finished = finish_combat(state)
    assert finished.state.conflict_first_place_influence_bonus == 0
    assert [event.kind for event in finished.events] == [
        "conflict_won",
        "combat_cleaned_up",
    ]


# --------------------------------------------------------- The Beast's Spoils


def test_face_up_icons_ignore_face_down_cards() -> None:
    player = PlayerState(
        player_id=0,
        objective_ids=("objective_crysknife_1", "objective_desert_mouse"),
        won_conflict_ids=("skirmish_ornithopter", "propaganda"),
        face_down_battle_card_ids=("objective_desert_mouse",),
    )
    assert face_up_battle_icons(player) == {
        BattleIcon.CRYSKNIFE,
        BattleIcon.ORNITHOPTER,
        BattleIcon.WILD,
    }


def test_beasts_spoils_pays_out_per_face_up_icon_then_offers_the_trash() -> None:
    spoils = _promo_instance("the_beast_s_spoils")
    dagger = _starter("dagger")
    # One face-up card per icon, as immediate matching guarantees; the wild
    # Propaganda counts as none of the three (OQ-024).
    owner = PlayerState(
        player_id=0,
        hand=(spoils, dagger),
        discard_pile=(_starter("diplomacy"),),
        objective_ids=("objective_crysknife_1",),
        won_conflict_ids=(
            "skirmish_desert_mouse",
            "skirmish_ornithopter",
            "propaganda",
        ),
    )
    placed = _place(
        _turn_state(owner, current_conflict_ids=("skirmish_crysknife",)),
        "arrakeen",
    )
    # The trash choices wait for the automatic part to resolve first.
    assert legal_agent_card_trash_actions(placed, 0) == ()

    resolved = resolve_agent_card_effect(placed)
    after = resolved.state.players[0]
    assert after.resources.spice == 1
    assert after.troops_garrison == owner.troops_garrison + 1
    assert _context(resolved.state)["troops_recruited"] == 1
    assert _context(resolved.state)["pending_agent_effect"] is True
    assert _context(resolved.state)["crysknife_trashes_remaining"] == 1
    assert dict(resolved.events[0].payload) == {
        "card_id": spoils,
        "crysknife": 1,
        "player": 0,
        "spice": 1,
        "troops": 1,
    }

    actions = legal_agent_card_trash_actions(resolved.state, 0)
    assert {dict(action.arguments).get("card_id") for action in actions} == {
        None,
        dagger,
        _starter("diplomacy"),
        spoils,
    }
    trashed = apply_agent_card_trash(
        resolved.state,
        next(a for a in actions if dict(a.arguments).get("card_id") == dagger),
    )
    assert trashed.state.players[0].trashed == (dagger,)
    assert _context(trashed.state)["pending_agent_effect"] is False
    assert "crysknife_trashes_remaining" not in _context(trashed.state)

    declined = apply_agent_card_trash(
        resolved.state,
        next(a for a in actions if a.action_id == "decline_agent_card_trash"),
    )
    assert _context(declined.state)["pending_agent_effect"] is False
    assert declined.state.players[0].trashed == ()


def test_beasts_spoils_with_no_face_up_icons_does_nothing() -> None:
    spoils = _promo_instance("the_beast_s_spoils")
    owner = PlayerState(
        player_id=0,
        hand=(spoils,),
        won_conflict_ids=("propaganda",),
    )
    placed = _place(
        _turn_state(owner, current_conflict_ids=("skirmish_desert_mouse",)),
        "arrakeen",
    )

    resolved = resolve_agent_card_effect(placed)

    assert resolved.state.players[0].resources.spice == 0
    assert _context(resolved.state)["pending_agent_effect"] is False
    assert resolved.events[0].kind == "agent_card_effect_unavailable"


# ------------------------------------------------------------- integration


def test_promo_actions_round_trip_through_the_codec() -> None:
    codec = ActionCodec(PROMO)
    assert codec.size == 4442
    assert ActionCodec(RulesetConfig(choam_module=True, promo_cards=True)).size == 4728
    for action_id in (
        "pay_agent_card_spice_for_sandworm",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
    ):
        action = DomainAction(action_id=action_id, actor=1)
        assert codec.decode(codec.encode(action), actor=1) == action
        base = ActionCodec(RulesetConfig())
        assert base.decode(base.encode(action), actor=1) == action
    play = DomainAction(
        action_id="trash_agent_card",
        actor=2,
        arguments=(("card_id", _promo_instance("pivotal_gambit")),),
    )
    assert codec.decode(codec.encode(play), actor=2) == play


def test_random_games_finish_with_the_promo_cards_in_both_rulesets() -> None:
    engine = UprisingRulesEngine()
    for choam_module in (False, True):
        config = RulesetConfig(choam_module=choam_module, promo_cards=True)
        for seed in (1, 2):
            simulation = run_random_game(engine, config, seed, seed + 100)
            assert simulation.state.phase is GamePhase.FINISHED
            dealt = {
                instance.split(":")[1]
                for instance in (
                    *simulation.state.imperium_deck,
                    *simulation.state.imperium_row,
                    *simulation.state.imperium_removed,
                    *(
                        card
                        for player in simulation.state.players
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
            assert {"arrakis_revolt", "pivotal_gambit", "the_beast_s_spoils"} <= dealt
