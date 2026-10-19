"""Tests for the three Uprising promo Imperium cards (card faces; OQ-024..026).

Arrakis Revolt, The Beast's Spoils and Pivotal Gambit are not in the retail
deck; ``RulesetConfig(promo_cards=True)`` shuffles them in. Their Agent
boxes are transcribed from the printed cards (see
``docs/implementation-audits/personal-cards.md``); the rulings the official
documents leave open are recorded in ``docs/rules/open-questions.md``.
"""

from dataclasses import replace

import pytest
from tests.support.reward_windows import settle_reward_window

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_whole
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
from dune_imperium.rules import turn_rows
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
from dune_imperium.rules.box_events import BoxOutcome, agent_box_event
from dune_imperium.rules.combat import (
    apply_combat_reward_influence,
    face_up_battle_icons,
    finish_combat,
    legal_combat_reward_influence_actions,
    offer_conflict_end_triggers,
    resolve_combat_rewards,
)
from dune_imperium.rules.effect_steps import steps_for
from dune_imperium.rules.effects import agent_card_source
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind, top_frame
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.optional_trash import apply_optional_trash
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
    """The Influence choices the recipient's reward window opens, one after
    the other (stage B2, OQ-112: each is a row of the window), each answered
    with its first legal Faction so the next one opens."""

    frames: list[DecisionFrame] = []
    while True:
        state = settle_reward_window(state)
        frame = top_frame(state)
        if frame is None or frame.kind != FrameKind.COMBAT_REWARD_INFLUENCE:
            return frames
        frames.append(frame)
        assert isinstance(frame.decision, PlayerDecision)
        choice = legal_combat_reward_influence_actions(state, frame.decision.owner)[0]
        state = apply_combat_reward_influence(state, choice).state


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


def test_liet_may_pay_arrakis_revolt_and_keep_the_wall_behind_it() -> None:
    # Arrakis Planetologist: "You summon no sandworms. For each one you would,
    # instead: [trash] [1 spice] [Intrigue]. (Even when the Conflict is
    # protected by the Shield Wall.)" [Liet Kynes card]. The replacement pays
    # behind the wall, so keeping it is a live choice for Liet even where the
    # worm alone "does nothing" [Main p. 20] (OQ-026 withholds it only for
    # the other seats).
    revolt = _promo_instance("arrakis_revolt")
    owner = PlayerState(
        player_id=0,
        leader_id="liet_kynes",
        hand=(revolt,),
        maker_hooks=True,
        resources=Resources(spice=2),
    )
    placed = _place(
        _turn_state(
            owner,
            current_conflict_ids=("siege_of_arrakeen",),
            intrigue_deck=("intrigue:bribery:0",),
        ),
        "arrakeen",
    )
    assert _payment_ids(placed) == [
        "decline_agent_card_payment",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
        "pay_agent_card_spice_for_sandworm",
    ]
    kept = apply_agent_card_payment(
        placed,
        DomainAction(action_id="pay_agent_card_spice_for_sandworm", actor=0),
    )
    liet = kept.state.players[0]
    assert kept.state.shield_wall_present is True
    assert liet.sandworms_conflict == 0
    assert liet.resources.spice == 1  # 2 paid, 1 from the replacement
    # The replacement's Intrigue card waits as its own step beside its trash
    # (user ruling 2026-10-10, OQ-106), both on the owner's Agent turn as rows
    # (user decision 2026-10-17, cleanup-2b).
    assert liet.intrigue_cards == ()
    assert kept.state.decision_stack[-1].kind == "agent_effects"
    assert [
        kind
        for kind, _source, _value in turn_rows.pending(kept.state.decision_stack[-1])
    ] == [turn_rows.OPTIONAL_TRASH, turn_rows.PLANETOLOGIST_INTRIGUE]
    drawn = apply_optional_trash(
        kept.state, DomainAction(action_id="draw_planetologist_intrigue", actor=0)
    ).state
    assert drawn.players[0].intrigue_cards == ("intrigue:bribery:0",)


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
    assert [event.kind for event in result.events] == [
        "resources_paid",
        "shield_wall_destroyed",
        "sandworm_deployed",
        "agent_card_effect_resolved",
    ]
    assert result.events[-1] == agent_box_event(
        agent_card_source(1, 0, revolt), revolt, 0, BoxOutcome.RESOLVED
    )


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
        "resources_paid",
        "sandworm_deployed",
        "agent_card_effect_resolved",
    ]

    declined = apply_agent_card_payment(placed, actions["decline_agent_card_payment"])
    assert declined.state.players[0].resources.spice == 2
    assert declined.state.players[0].sandworms_conflict == 0
    assert declined.events == (
        agent_box_event(
            agent_card_source(1, 0, revolt), revolt, 0, BoxOutcome.DECLINED
        ),
    )


def _revolt_under_emperor_ban(**state_fields: object) -> GameState:
    """Place Arrakis Revolt after Servo-Receivers used Shaddam's Signet Ring.

    Rapid Engineering (a Plot, "[discard] → [-1] [Tech]" [Rapid Engineering
    card]) buys Servo-Receivers before the Agent is placed; its Signet Ring
    icon uses Emperor of the Known Universe, whose "Units can't be deployed
    to the Conflict this turn" [Shaddam Corrino IV card] covers the Agent
    turn that follows (OQ-062 (b)).
    """

    rapid_engineering = "intrigue:rapid_engineering:0"
    dagger = _starter("dagger")
    revolt = _promo_instance("arrakis_revolt")
    owner = PlayerState(
        player_id=0,
        leader_id="shaddam_corrino_iv",
        hand=(revolt, dagger),
        maker_hooks=True,
        intrigue_cards=(rapid_engineering,),
        resources=Resources(solari=4, spice=6),
    )
    state = replace(
        _turn_state(owner, **state_fields),
        config=RulesetConfig(bloodlines=True, tech_module=True, promo_cards=True),
        tech_stacks=(("servo_receivers",), (), ()),
    )
    engine = UprisingRulesEngine()
    for action_id, arguments in (
        ("play_intrigue", (("card_id", rapid_engineering),)),
        ("choose_intrigue_discard", (("card_id", dagger),)),
        ("acquire_tech", (("tech_id", "servo_receivers"),)),
        ("resolve_tech_acquire_effect", (("effect", "signet"),)),
        ("gain_leader_signet_troop", ()),
        ("choose_agent_card", (("card_id", revolt),)),
        ("place_agent", (("space_id", "arrakeen"),)),
    ):
        action = next(
            action
            for action in engine.whole_actions(state, 0)
            if action.action_id == action_id
            and all(dict(action.arguments)[key] == value for key, value in arguments)
        )
        state = apply_whole(engine, state, action).state
    assert _context(state)["units_deploy_blocked"] is True
    return state


def test_arrakis_revolt_keeps_no_wall_payment_under_the_emperor_ban() -> None:
    # The summoned worm is withheld while Emperor of the Known Universe
    # blocks deployment [Main p. 17], so paying 2 spice to keep the wall
    # would buy nothing (OQ-026: "2 spice로 아무것도 얻지 못하는 선택은
    # 규칙상 가능하더라도 행동 공간에서 뺀다"). Removing the wall still does
    # something ("You may remove the Shield Wall" [Main p. 20]) and stays,
    # like the Maker space withholding its summon under the same ban.
    placed = _revolt_under_emperor_ban()
    assert _payment_ids(placed) == [
        "decline_agent_card_payment",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
    ]
    removed = apply_agent_card_payment(
        placed,
        DomainAction(
            action_id="pay_agent_card_spice_for_sandworm_and_shield_wall", actor=0
        ),
    )
    assert removed.state.shield_wall_present is False
    assert removed.state.players[0].sandworms_conflict == 0
    assert [event.kind for event in removed.events] == [
        "resources_paid",
        "shield_wall_destroyed",
        "sandworm_summon_unavailable",
        "agent_card_effect_resolved",
    ]

    # Without the wall the payment could only summon, so only declining is
    # left.
    no_wall = _revolt_under_emperor_ban(shield_wall_present=False)
    assert _payment_ids(no_wall) == ["decline_agent_card_payment"]


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
    # The winner takes the Conflict card as the Conflict-end step opens
    # (OQ-108, user decision 2026-10-18); the cleanup after it only closes
    # the Combat.
    offered = offer_conflict_end_triggers(state)
    assert offered.state.conflict_first_place_influence_bonus == 0
    assert [event.kind for event in offered.events] == ["conflict_won"]
    finished = finish_combat(offered.state)
    assert finished.state.conflict_first_place_influence_bonus == 0
    assert [event.kind for event in finished.events] == ["combat_cleaned_up"]


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
    assert _context(resolved.state)["trashes_remaining"] == 1
    # The hook step pays the spice as a gain of the box; the box is not over
    # (its trash is still to be answered), so it leaves no box event yet.
    box = agent_card_source(1, 0, spoils)
    assert resolved.events == (resources_gained_event(box, 0, spice=1),)

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
    assert "trashes_remaining" not in _context(trashed.state)
    # The trash answer closes the box: its event comes last.
    assert [event.kind for event in trashed.events] == [
        "card_trashed",
        "agent_card_effect_resolved",
    ]
    assert trashed.events[-1] == agent_box_event(box, spoils, 0, BoxOutcome.RESOLVED)

    declined = apply_agent_card_trash(
        resolved.state,
        next(a for a in actions if a.action_id == "decline_agent_card_trash"),
    )
    assert _context(declined.state)["pending_agent_effect"] is False
    assert declined.state.players[0].trashed == ()
    assert declined.events == (agent_box_event(box, spoils, 0, BoxOutcome.DECLINED),)


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
    # v97 Occupation's Reveal bundle; v100 skip + Change Allegiances' third option.
    # v103 separate lines. v106: trash_intrigue_for_agent_card joins one
    # template per Intrigue instance (+40), and Branching Path's corrected
    # City icon shifts its agent_turn space coverage by +1 (see
    # test_action_codec.test_catalog_is_fixed_and_versioned_for_a_ruleset).
    # v107: +27, the generic Spy placement frame in every catalog.
    # v108 (2026-09-26 card-transcription audit): -36 + 15 + 5, the same
    # net change as the base catalog (see test_action_codec.
    # test_catalog_is_fixed_and_versioned_for_a_ruleset); the CHOAM catalog
    # also gains decline_contract_spy (+1).
    # decline_acquisition_spy: an acquisition-bonus Spy may pass up the
    # recall-first without a Spy in supply [Main pp. 11, 20] (+1).
    # v110: an Agent-box Spy may pass up the recall-first too, when the box
    # resolves (decline_agent_card_spy, +1).
    # v125 (L2): the recall confirms, resolve_imperial_privilege_without_recall
    # (+1) and, with CHOAM, resolve_contract_without_recall (+1).
    # v125 (L2): a Conflict reward Influence choice with every eligible
    # Faction at the top is confirmed
    # (resolve_combat_influence_without_faction, +1).
    # v129 (OQ-016, user ruling 2026-10-03): Distraction plays once its
    # deployment condition holds and places its Spy through the Intrigue
    # choice, so decline_intrigue_trigger and the 13 + 13 place/recall
    # trigger templates leave every catalog (-27).
    # v130 (OQ-005, user ruling 2026-10-04): flip_battle_card gains one
    # template per Objective, which counts as a won Conflict card (+4).
    # v131 (user ruling 2026-10-04, overriding OQ-057 (15)): the owner's
    # waiting Emperor track Spy is opened by place_track_spy (+1).
    # v134: finish_leader_draft confirms the last pick (+1).
    assert codec.size == (
        4454 + 12 + 1 + 1 + 2 + 1 + 40 + 1 + 27 - 36 + 15 + 5 + 1 + 1 + 1 + 1 - 27 + 4
        + 1
        + 1  # v134: finish_leader_draft
        + 1  # v137: the cards_second icon key
        + 1  # v137: the research icon key
        + 1  # v137: the return_self icon key
        + 1  # v137: the Intrigue Influence confirm
        + 1  # v137: Tactical Option retreats 0
        + 1  # v137: an "up to" deploy of 0
        + 1  # v142: draw_owed_intrigue (OQ-106)
        # v147: the base catalog's 140 ``source``-named Reveal rows, and
        # Calculus of Power may trash the promo Emperor card too (+1).
        + 141
        - 2  # v149 cleanup-2f: four refusals out, two confirms in
        # v150 (stage B1): the promo catalog's 1,806 ``agent_turn`` rows
        # become 132 card and space picks.
        - 1806
        + 132
        # v150 (stage B2, OQ-112): ``resolve_combat_reward_icon``, a row per
        # icon a Conflict reward prints (14 here; Bloodlines adds the Deep
        # Cover Spy).
        + 14
        # v150 (stage B3a, OQ-111): the Agent-effect frame's effect and target
        # rows replace the whole templates of the ids in
        # ``effect_steps.STEP_SPECS`` that no other frame still offers as they
        # are (see test_action_codec.test_catalog_is_fixed...): 810 leave and
        # 983 rows join (the promo cards add their own effect rows).
        - 810
        + 983
        # v150 (stage B3b-2): the Reveal frame's effect rows: 152 whole
        # templates leave and 28 rows join.
        - 152
        + 28
    )
    # v130 (OQ-021, user ruling 2026-10-04): the CHOAM catalog loses
    # take_exhausted_contract_solari (-1).
    choam_promo = ActionCodec(RulesetConfig(choam_module=True, promo_cards=True))
    assert choam_promo.size == (
        4740 + 12 + 1 + 1 + 2 + 1 + 44 + 1 + 27 - 36 + 15 + 5 + 1 + 1 + 1 + 2 + 1
        - 27
        - 1
        + 4
        + 1
        + 1  # v134: finish_leader_draft
        + 1  # v137: the cards_second icon key
        + 1  # v137: the research icon key
        + 1  # v137: the return_self icon key
        + 1  # v137: the Intrigue Influence confirm
        + 1  # v137: Tactical Option retreats 0
        + 1  # v137: an "up to" deploy of 0
        + 1  # v142: draw_owed_intrigue (OQ-106)
        # v147: the CHOAM catalog's 144 ``source``-named Reveal rows, and
        # Calculus of Power may trash the promo Emperor card too (+1).
        + 145
        - 2  # v149 cleanup-2f: four refusals out, two confirms in
        # v150 (stage B1): the CHOAM promo catalog's 1,911 ``agent_turn``
        # rows become 136 card and space picks.
        - 1911
        + 136
        # v150 (stage B2, OQ-112): ``resolve_combat_reward_icon`` (14) and,
        # with the CHOAM module, ``resolve_contract_reward_icon`` (9).
        + 14
        + 9
        # v150 (stage B3a, OQ-111): 866 whole templates leave and 1,043 rows
        # join (see above).
        - 866
        + 1043
        # v150 (stage B3b, OQ-112 (4)): the in-turn Contract rows, 23 whole
        # templates and their 23 effect rows.
        + 23
        + 23
        # v150 (stage B3b-2): 160 whole templates leave and 32 rows join.
        - 160
        + 32
    )
    # Stage B3a: Arrakis Revolt's two payments are ``pay`` effect rows naming
    # the card (an effect without a target is one row). The other cards that
    # print a sandworm payment hold theirs in every catalog; the promo cards
    # add only the rows that name them.
    base = ActionCodec(RulesetConfig())
    for action_id, option in (
        ("pay_agent_card_spice_for_sandworm", "sandworm"),
        (
            "pay_agent_card_spice_for_sandworm_and_shield_wall",
            "sandworm_and_shield_wall",
        ),
    ):
        action = DomainAction(action_id=action_id, actor=1)
        (row,) = steps_for(action, "arrakis_revolt")
        assert dict(row.arguments)["option"] == option
        assert codec.decode(codec.encode(row), actor=1) == row
        with pytest.raises(ValueError, match="not present"):
            base.encode(row)
        (shared,) = steps_for(action, "branching_path")
        assert base.decode(base.encode(shared), actor=1) == shared
        assert codec.decode(codec.encode(shared), actor=1) == shared
    # Pivotal Gambit's trash: the effect row, then any card of the promo
    # catalog as its target.
    play = DomainAction(
        action_id="trash_agent_card",
        actor=2,
        arguments=(("card_id", _promo_instance("pivotal_gambit")),),
    )
    rows = steps_for(play, "pivotal_gambit")
    assert [row.action_id for row in rows] == ["trash", "choose_personal_card"]
    for row in rows:
        assert codec.decode(codec.encode(row), actor=2) == row


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
