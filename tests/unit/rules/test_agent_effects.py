"""Tests for Agent-card, Faction, and effect-frame completion."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
    RuleResult,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_discard,
    apply_agent_card_influence,
    apply_agent_card_intrigue_payment,
    apply_agent_card_long_live_action,
    apply_agent_card_payment,
    apply_agent_card_recall,
    apply_agent_card_spy_action,
    apply_agent_card_trash,
    apply_corrinth_city_payment,
    expire_trashed_card_effects,
    legal_agent_card_discard_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_intrigue_payment_actions,
    legal_agent_card_long_live_actions,
    legal_agent_card_payment_actions,
    legal_agent_card_recall_actions,
    legal_agent_card_spy_actions,
    legal_agent_card_trash_actions,
    legal_corrinth_city_payment_actions,
    resolve_agent_card_effect,
    resolve_faction_influence,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import resolve_board_effect
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.combat_deployment import (
    apply_combat_deployment,
    legal_combat_deployments,
)
from dune_imperium.rules.contracts import (
    apply_contract_action,
    apply_contract_completion,
    legal_contract_actions,
    legal_contract_completion_actions,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.spies import (
    apply_gather_intelligence_action,
    legal_gather_intelligence_actions,
)


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _imperium_instance(card_id: str, *, choam_module: bool = False) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(choam_module)
        if f":{card_id}:" in instance_id
    )


def _state(card_id: str, influence: Influence | None = None) -> GameState:
    card = _instance(card_id)
    starting_influence = influence or Influence()
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=(card,), influence=starting_influence),
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


def _action_to(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )


def test_seek_allies_trashes_itself_from_in_play() -> None:
    state = _state("seek_allies")
    card = state.players[0].hand[0]
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_agent_card_effect(placed).state

    assert card not in resolved.players[0].in_play
    assert resolved.players[0].trashed == (card,)
    assert dict(resolved.decision_stack[-1].context)["pending_agent_effect"] is False


def test_corrinth_city_atomically_discards_two_and_pays_five_for_vp() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    dagger = _instance("dagger")
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city, favor, dagger),
        resources=Resources(solari=5),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    actions = legal_corrinth_city_payment_actions(placed, 0)

    assert {action.action_id for action in actions} == {
        "decline_corrinth_city_payment",
        "select_corrinth_city_discard",
    }
    selection = next(
        action
        for action in actions
        if dict(action.arguments).get("card_id") == favor
    )
    selected = apply_corrinth_city_payment(placed, selection)
    assert selected.state.players[0].hand == (favor, dagger)
    assert selected.state.players[0].resources.solari == 5
    assert selected.events[0].kind == "corrinth_city_payment_started"

    payment = next(
        action
        for action in legal_corrinth_city_payment_actions(selected.state, 0)
        if action.action_id == "pay_corrinth_city"
    )
    result = apply_corrinth_city_payment(selected.state, payment)
    resolved = result.state.players[0]

    assert resolved.hand == ()
    assert set(resolved.discard_pile) == {dagger, favor}
    assert resolved.resources.solari == 0
    assert resolved.resources.spice == 2
    assert resolved.victory_points == owner.victory_points + 1
    assert (
        dict(result.state.decision_stack[-1].context)["pending_agent_effect"] is False
    )
    assert [event.kind for event in result.events] == [
        "card_discarded",
        "personal_card_discard_effect_resolved",
        "card_discarded",
        "corrinth_city_payment_resolved",
    ]


def test_corrinth_city_cost_must_be_available_before_discard_effects() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city, favor, _instance("dagger")),
        resources=Resources(solari=4),
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

    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    assert legal_corrinth_city_payment_actions(placed, 0) == ()
    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_faction_influence_reaches_friendship_and_awards_vp() -> None:
    state = _state("diplomacy", Influence(emperor=1))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_faction_influence(placed).state

    assert resolved.players[0].influence.emperor == 2
    assert resolved.players[0].victory_points == 2


def test_finishing_all_effect_groups_opens_clockwise_players_turn() -> None:
    state = _state("seek_allies")
    state = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    state = resolve_agent_card_effect(state).state
    state = resolve_faction_influence(state).state
    state = resolve_board_effect(state).state

    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
    assert state.decision_stack[-1].context == (("round", 1), ("turn_owner", 1))


def test_influence_four_grants_emperor_bonus_and_alliance() -> None:
    state = _state("diplomacy", Influence(emperor=3))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_faction_influence(placed).state

    owner = resolved.players[0]
    assert owner.influence.emperor == 4
    assert owner.troops_supply == 7
    assert owner.troops_garrison == 5
    assert owner.alliance_faction_ids == ("emperor",)
    assert owner.victory_points == 2


def test_rising_above_an_opponent_transfers_the_alliance_vp() -> None:
    state = _state("diplomacy", Influence(emperor=4))
    challenger = replace(state.players[0], victory_points=2)
    holder = replace(
        state.players[1],
        influence=Influence(emperor=4),
        alliance_faction_ids=("emperor",),
        victory_points=2,
    )
    state = replace(state, players=(challenger, holder, *state.players[2:]))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_faction_influence(placed).state

    assert resolved.players[0].influence.emperor == 5
    assert resolved.players[0].alliance_faction_ids == ("emperor",)
    assert resolved.players[0].victory_points == 3
    assert resolved.players[1].alliance_faction_ids == ()
    assert resolved.players[1].victory_points == 1


def test_signet_effect_waits_for_leader_implementations() -> None:
    # The seat has no implemented Leader, so the Signet Ring ability cannot
    # resolve; the dispatcher withholds such placements via
    # ``leader_signet_is_implemented``.
    state = _state("signet_ring")
    placed = apply_agent_action(state, _action_to(state, "spice_refinery")).state

    with pytest.raises(RuntimeError, match="not implemented"):
        resolve_agent_card_effect(placed)


def test_prepare_the_way_draws_with_two_bene_gesserit_influence() -> None:
    prepare = "reserve:prepare_the_way:7"
    drawn = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(prepare,),
        deck=(drawn,),
        influence=Influence(bene_gesserit=2),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    resolved = resolve_agent_card_effect(placed)

    assert resolved.state.players[0].hand == (drawn,)
    assert resolved.state.players[0].deck == ()
    assert resolved.events[0].kind == "agent_card_effect_resolved"


def test_prepare_the_way_has_no_agent_effect_below_required_influence() -> None:
    prepare = "reserve:prepare_the_way:7"
    owner = PlayerState(
        player_id=0,
        hand=(prepare,),
        influence=Influence(bene_gesserit=1),
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

    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_prepare_the_way_draw_is_lost_when_influence_drops_before_resolving() -> None:
    # The Influence condition is judged when the effect resolves in the
    # player's chosen order [Main pp. 7, 9]; a mid-frame Influence loss (for
    # example an Intrigue cost) therefore forfeits the conditional draw
    # instead of failing the advertised resolution.
    prepare = "reserve:prepare_the_way:7"
    undrawn = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(prepare,),
        deck=(undrawn,),
        influence=Influence(bene_gesserit=2),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is True

    lowered_owner = replace(
        placed.players[0], influence=Influence(bene_gesserit=1)
    )
    lowered = replace(
        placed,
        players=(lowered_owner, *placed.players[1:]),
    )

    resolved = resolve_agent_card_effect(lowered)

    assert resolved.state.players[0].hand == ()
    assert resolved.state.players[0].deck == (undrawn,)
    assert resolved.events[0].kind == "agent_card_effect_unavailable"
    context = dict(resolved.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False


def test_maula_pistol_agent_effect_draws_one_personal_card() -> None:
    maula = _imperium_instance("maula_pistol")
    drawn = _instance("dagger")
    owner = PlayerState(player_id=0, hand=(maula,), deck=(drawn,))
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    resolved = resolve_agent_card_effect(placed)

    assert resolved.state.players[0].hand == (drawn,)
    assert resolved.state.players[0].deck == ()
    assert resolved.events[0].kind == "agent_card_effect_resolved"


def test_hidden_missive_recruits_and_draws_with_required_influence() -> None:
    hidden_missive = _imperium_instance("hidden_missive")
    drawn = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(hidden_missive,),
        deck=(drawn,),
        influence=Influence(bene_gesserit=2),
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
    placed = apply_agent_action(state, _action_to(state, "gather_support")).state

    resolved = resolve_agent_card_effect(placed)
    context = dict(resolved.state.decision_stack[-1].context)

    assert resolved.state.players[0].troops_supply == 8
    assert resolved.state.players[0].troops_garrison == 4
    assert resolved.state.players[0].hand == (drawn,)
    assert resolved.state.players[0].deck == ()
    assert context["troops_recruited"] == 1
    assert resolved.events[0].kind == "agent_card_effect_resolved"


def test_hidden_missive_has_no_agent_effect_below_required_influence() -> None:
    hidden_missive = _imperium_instance("hidden_missive")
    owner = PlayerState(
        player_id=0,
        hand=(hidden_missive,),
        influence=Influence(bene_gesserit=1),
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

    placed = apply_agent_action(state, _action_to(state, "gather_support")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_desert_survival_may_trash_from_any_eligible_zone() -> None:
    desert_survival = _imperium_instance("desert_survival")
    hand_card = _instance("dagger")
    discarded_card = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(desert_survival, hand_card),
        discard_pile=(discarded_card,),
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
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    actions = legal_agent_card_trash_actions(placed, 0)
    trash_ids = {
        dict(action.arguments)["card_id"]
        for action in actions
        if action.action_id == "trash_agent_card"
    }

    assert {hand_card, discarded_card, desert_survival} == trash_ids

    action = next(
        action
        for action in actions
        if dict(action.arguments).get("card_id") == discarded_card
    )
    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].discard_pile == ()
    assert result.state.players[0].trashed == (discarded_card,)
    assert result.state.players[0].in_play == (desert_survival,)
    assert result.events[0].kind == "card_trashed"
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False


def test_desert_survival_trash_may_be_declined() -> None:
    desert_survival = _imperium_instance("desert_survival")
    owner = PlayerState(player_id=0, hand=(desert_survival,))
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
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state
    action = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if action.action_id == "decline_agent_card_trash"
    )

    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].in_play == (desert_survival,)
    assert result.state.players[0].trashed == ()
    assert result.events[0].kind == "agent_card_trash_declined"


def test_treacherous_maneuver_pays_both_cards_for_extra_influence() -> None:
    maneuver = _imperium_instance("treacherous_maneuver")
    sardaukar = _imperium_instance("sardaukar_soldier")
    non_emperor = _imperium_instance("desert_survival")
    discarded_emperor = _imperium_instance("imperial_spymaster")
    owner = PlayerState(
        player_id=0,
        hand=(maneuver, sardaukar, non_emperor),
        discard_pile=(discarded_emperor,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:test",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    actions = legal_agent_card_trash_actions(placed, 0)
    assert {
        dict(action.arguments).get("card_id")
        for action in actions
        if action.action_id == "trash_agent_card"
    } == {sardaukar}

    trash = next(
        action for action in actions if action.action_id == "trash_agent_card"
    )
    paid = apply_agent_card_trash(placed, trash)

    assert paid.state.players[0].hand == (non_emperor,)
    assert paid.state.players[0].in_play == ()
    assert paid.state.players[0].trashed == (sardaukar, maneuver)
    assert paid.state.players[0].intrigue_cards == ("intrigue:test",)
    assert paid.state.players[0].influence.emperor == 1
    assert [event.kind for event in paid.events] == [
        "card_trashed",
        "intrigue_card_drawn",
        "card_trashed",
        "influence_gained",
    ]

    resolved = resolve_faction_influence(paid.state).state
    assert resolved.players[0].influence.emperor == 2
    assert resolved.players[0].victory_points == 2


def test_treacherous_maneuver_box_expires_when_trashed_mid_frame() -> None:
    # A freely ordered Intrigue trash slot can trash the played card before
    # its trash choice resolves; the un-activated Agent box then expires
    # without any of its effects, because you can't receive or activate an
    # effect from a card that is already trashed (OQ-022 designer ruling).
    # The collision was found by the leader-draft heuristic sweep (CHOAM
    # seed 198).
    maneuver = _imperium_instance("treacherous_maneuver")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(player_id=0, hand=(maneuver, sardaukar))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:test",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state
    trashed_owner = replace(
        placed.players[0],
        in_play=tuple(
            candidate
            for candidate in placed.players[0].in_play
            if candidate != maneuver
        ),
        trashed=(maneuver,),
    )
    lowered = replace(placed, players=(trashed_owner, *placed.players[1:]))

    expired = expire_trashed_card_effects(RuleResult(state=lowered))

    assert expired.events[-1].kind == "agent_card_effect_expired"
    context = dict(expired.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert legal_agent_card_trash_actions(expired.state, 0) == ()
    assert expired.state.players[0].hand == (sardaukar,)
    assert expired.state.players[0].trashed == (maneuver,)
    assert expired.state.players[0].influence.emperor == 0


def test_dangerous_rhetoric_box_expires_when_trashed_mid_frame() -> None:
    # A freely ordered effect can trash Dangerous Rhetoric itself before its
    # Agent box resolves (Desert Tactics' board trash reaches it when the
    # card was played there via its Spy icon); the un-activated box then
    # expires, so its chosen-Influence choice is never offered (OQ-022
    # designer ruling). The collision was found by the 2026-09-01 random
    # sweep (CHOAM seed 2735).
    rhetoric = _imperium_instance("dangerous_rhetoric")
    owner = PlayerState(player_id=0, hand=(rhetoric,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:test",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    trashed_owner = replace(
        placed.players[0],
        in_play=tuple(
            candidate
            for candidate in placed.players[0].in_play
            if candidate != rhetoric
        ),
        trashed=(rhetoric,),
    )
    lowered = replace(placed, players=(trashed_owner, *placed.players[1:]))

    expired = expire_trashed_card_effects(RuleResult(state=lowered))

    assert expired.events[-1].kind == "agent_card_effect_expired"
    context = dict(expired.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert legal_agent_card_influence_actions(expired.state, 0) == ()
    assert expired.state.players[0].trashed == (rhetoric,)
    assert expired.state.players[0].influence.spacing_guild == 0


def test_bond_box_expires_with_its_trashed_source_card() -> None:
    # A source card trashed by a freely ordered effect before its Bond box
    # resolves expires with the box: you can't receive or activate an effect
    # from a card that is already trashed (OQ-022 designer ruling). Bond
    # checks for cards that stay in play keep counting only OTHER Faction
    # cards [Main p. 20]. The collision was found by the 2026-09-01 random
    # sweep (seeds 2934/2590).
    elders = _imperium_instance("southern_elders")
    partner = _imperium_instance("tread_in_darkness")
    owner = PlayerState(player_id=0, hand=(elders,), in_play=(partner,))
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
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state
    trashed_owner = replace(
        placed.players[0],
        in_play=tuple(
            candidate
            for candidate in placed.players[0].in_play
            if candidate != elders
        ),
        trashed=(elders,),
    )
    lowered = replace(placed, players=(trashed_owner, *placed.players[1:]))
    garrison_before = trashed_owner.troops_garrison

    expired = expire_trashed_card_effects(RuleResult(state=lowered))

    assert expired.events[-1].kind == "agent_card_effect_expired"
    context = dict(expired.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert expired.state.players[0].troops_garrison == garrison_before


def test_treacherous_maneuver_may_be_declined_for_only_normal_influence() -> None:
    maneuver = _imperium_instance("treacherous_maneuver")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(player_id=0, hand=(maneuver, sardaukar))
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
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state
    decline = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if action.action_id == "decline_agent_card_trash"
    )

    declined = apply_agent_card_trash(placed, decline).state
    resolved = resolve_faction_influence(declined).state

    assert resolved.players[0].hand == (sardaukar,)
    assert resolved.players[0].in_play == (maneuver,)
    assert resolved.players[0].trashed == ()
    assert resolved.players[0].influence.emperor == 1


def test_treacherous_maneuver_needs_an_emperor_payment() -> None:
    maneuver = _imperium_instance("treacherous_maneuver")
    non_emperor = _imperium_instance("desert_survival")
    owner = PlayerState(player_id=0, hand=(maneuver, non_emperor))
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

    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    assert legal_agent_card_trash_actions(placed, 0) == ()
    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_chani_draws_intrigue_after_deploying_a_third_unit() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    owner = PlayerState(
        player_id=0,
        hand=(chani,),
        troops_supply=7,
        troops_garrison=4,
        troops_conflict=1,
        sandworms_conflict=1,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:test",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    deploy_one = next(
        action
        for action in legal_combat_deployments(placed, 0)
        if dict(action.arguments)["count"] == 1
    )
    deployed = apply_combat_deployment(placed, deploy_one).state

    result = resolve_agent_card_effect(deployed)

    assert result.state.players[0].troops_conflict == 2
    assert result.state.players[0].sandworms_conflict == 1
    assert result.state.players[0].intrigue_cards == ("intrigue:test",)
    assert result.state.intrigue_deck == ()
    assert [event.kind for event in result.events] == [
        "agent_card_effect_resolved",
        "intrigue_card_drawn",
    ]


def test_chani_agent_effect_is_unavailable_below_three_units() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    owner = PlayerState(
        player_id=0,
        hand=(chani,),
        troops_supply=8,
        troops_garrison=2,
        troops_conflict=2,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:test",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].intrigue_cards == ()
    assert result.events[0].kind == "agent_card_effect_unavailable"


def test_steersman_draws_and_may_recall_its_just_placed_agent() -> None:
    steersman = _imperium_instance("steersman")
    drawn_card = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        agents_available=1,
        agent_locations=("dutiful_service",),
        hand=(steersman,),
        deck=(drawn_card,),
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

    actions = legal_agent_card_recall_actions(placed, 0)
    assert {
        dict(action.arguments)["space_id"] for action in actions
    } == {"dutiful_service", "deliver_supplies"}
    recall_new = next(
        action
        for action in actions
        if dict(action.arguments)["space_id"] == "deliver_supplies"
    )
    assert recall_new in UprisingRulesEngine().legal_actions(placed, 0)

    result = apply_agent_card_recall(placed, recall_new)

    assert result.state.players[0].agents_available == 1
    assert result.state.players[0].agent_locations == ("dutiful_service",)
    assert result.state.players[0].hand == (drawn_card,)
    assert result.state.players[0].in_play == (steersman,)
    assert [event.kind for event in result.events] == ["agent_recalled"]


def test_junction_headquarters_may_pay_intrigue_and_spice_for_vp() -> None:
    junction = _imperium_instance("junction_headquarters")
    first_intrigue = "intrigue:cunning:0"
    second_intrigue = "intrigue:buy_access:0"
    owner = PlayerState(
        player_id=0,
        hand=(junction,),
        resources=Resources(spice=2),
        alliance_faction_ids=(Faction.SPACING_GUILD.value,),
        intrigue_cards=(first_intrigue, second_intrigue),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_discard=("intrigue:old",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    actions = legal_agent_card_intrigue_payment_actions(placed, 0)
    assert {action.action_id for action in actions} == {
        "decline_agent_card_intrigue_payment",
        "pay_agent_card_intrigue_and_spice",
    }
    assert {
        dict(action.arguments).get("intrigue_card_id")
        for action in actions
        if action.action_id == "pay_agent_card_intrigue_and_spice"
    } == {first_intrigue, second_intrigue}
    pay = next(
        action
        for action in actions
        if dict(action.arguments).get("intrigue_card_id") == second_intrigue
    )
    assert pay in UprisingRulesEngine().legal_actions(placed, 0)

    paid = apply_agent_card_intrigue_payment(placed, pay)
    declined = apply_agent_card_intrigue_payment(placed, actions[0])

    assert paid.state.players[0].resources.spice == 0
    assert paid.state.players[0].victory_points == 2
    assert paid.state.players[0].intrigue_cards == (first_intrigue,)
    assert paid.state.intrigue_discard == ("intrigue:old",)
    assert paid.state.intrigue_trash == (second_intrigue,)
    assert [event.kind for event in paid.events] == [
        "intrigue_card_trashed",
        "agent_card_payment_resolved",
    ]
    assert declined.state.players[0].resources.spice == 2
    assert declined.state.players[0].victory_points == 1
    assert declined.state.players[0].intrigue_cards == (
        first_intrigue,
        second_intrigue,
    )


@pytest.mark.parametrize(
    ("alliance_faction_ids", "spice", "intrigue_cards"),
    (
        ((), 2, ("intrigue:cunning:0",)),
        ((Faction.SPACING_GUILD.value,), 1, ("intrigue:cunning:0",)),
        ((Faction.SPACING_GUILD.value,), 2, ()),
    ),
)
def test_junction_headquarters_requires_its_complete_cost(
    alliance_faction_ids: tuple[str, ...],
    spice: int,
    intrigue_cards: tuple[str, ...],
) -> None:
    junction = _imperium_instance("junction_headquarters")
    owner = PlayerState(
        player_id=0,
        hand=(junction,),
        resources=Resources(spice=spice),
        alliance_faction_ids=alliance_faction_ids,
        intrigue_cards=intrigue_cards,
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

    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    assert legal_agent_card_intrigue_payment_actions(placed, 0) == ()
    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def _junction_pending_state(
    *,
    spice: int,
    intrigue_cards: tuple[str, ...],
) -> GameState:
    junction = _imperium_instance("junction_headquarters")
    owner = PlayerState(
        player_id=0,
        hand=(junction,),
        resources=Resources(spice=spice),
        alliance_faction_ids=(Faction.SPACING_GUILD.value,),
        intrigue_cards=intrigue_cards,
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
    return apply_agent_action(state, _action_to(state, "assembly_hall")).state


def test_junction_headquarters_payment_discharges_the_pending_arrow() -> None:
    # One arrow cost and its effect may be chosen only once per turn
    # [Main p. 9] [FAQ p. 3]; paying or skipping ends the pending effect
    # instead of offering the payment again.
    placed = _junction_pending_state(
        spice=4,
        intrigue_cards=("intrigue:cunning:0", "intrigue:buy_access:0"),
    )
    actions = legal_agent_card_intrigue_payment_actions(placed, 0)

    paid = apply_agent_card_intrigue_payment(placed, actions[1]).state
    assert paid.players[0].victory_points == 2
    assert dict(paid.decision_stack[-1].context)["pending_agent_effect"] is False
    assert legal_agent_card_intrigue_payment_actions(paid, 0) == ()
    assert UprisingRulesEngine().legal_actions(paid, 0)

    declined = apply_agent_card_intrigue_payment(placed, actions[0]).state
    assert declined.players[0].victory_points == 1
    assert dict(declined.decision_stack[-1].context)["pending_agent_effect"] is False
    assert legal_agent_card_intrigue_payment_actions(declined, 0) == ()


def test_junction_headquarters_offers_only_decline_once_unaffordable() -> None:
    # The Alliance condition and the full arrow cost are judged again when
    # the pending payment resolves in the player's chosen effect order
    # [Main pp. 9, 20]; a mid-frame Spice loss leaves only the skip.
    placed = _junction_pending_state(
        spice=2,
        intrigue_cards=("intrigue:cunning:0",),
    )
    drained = replace(placed.players[0], resources=Resources(spice=1))
    lowered = replace(placed, players=(drained, *placed.players[1:]))

    actions = legal_agent_card_intrigue_payment_actions(lowered, 0)
    assert [action.action_id for action in actions] == [
        "decline_agent_card_intrigue_payment"
    ]
    declined = apply_agent_card_intrigue_payment(lowered, actions[0])
    assert declined.events[0].kind == "agent_card_payment_declined"
    assert (
        dict(declined.state.decision_stack[-1].context)["pending_agent_effect"]
        is False
    )


def test_smugglers_haven_offers_only_decline_once_unaffordable() -> None:
    # The arrow cost is judged again at resolution [Main pp. 9, 20]; a
    # mid-frame Spice loss leaves only the skip.
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        resources=Resources(spice=4),
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
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state
    drained = replace(placed.players[0], resources=Resources(spice=3))
    lowered = replace(placed, players=(drained, *placed.players[1:]))

    actions = legal_agent_card_payment_actions(lowered, 0)
    assert [action.action_id for action in actions] == ["decline_agent_card_payment"]
    declined = apply_agent_card_payment(lowered, actions[0])
    assert declined.events[0].kind == "agent_card_payment_declined"
    assert (
        dict(declined.state.decision_stack[-1].context)["pending_agent_effect"]
        is False
    )


def test_corrinth_city_offers_only_decline_once_unaffordable() -> None:
    # The full cost must still be payable at resolution [Main pp. 9, 20]; a
    # mid-frame Solari loss leaves only the skip.
    corrinth_city = _imperium_instance("corrinth_city")
    dagger = _instance("dagger")
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city, favor, dagger),
        resources=Resources(solari=5),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    drained = replace(placed.players[0], resources=Resources(solari=4))
    lowered = replace(placed, players=(drained, *placed.players[1:]))

    actions = legal_corrinth_city_payment_actions(lowered, 0)
    assert [action.action_id for action in actions] == [
        "decline_corrinth_city_payment"
    ]
    declined = apply_corrinth_city_payment(lowered, actions[0])
    assert declined.events[0].kind == "corrinth_city_payment_declined"
    assert (
        dict(declined.state.decision_stack[-1].context)["pending_agent_effect"]
        is False
    )


def test_smugglers_harvester_gains_spice_at_a_maker_space() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")
    owner = PlayerState(player_id=0, hand=(harvester,))
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
    placed = apply_agent_action(state, _action_to(state, "hagga_basin")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.spice == 1
    assert result.events[0].kind == "agent_card_effect_resolved"


def test_smugglers_harvester_has_no_agent_effect_away_from_maker_spaces() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")
    owner = PlayerState(player_id=0, hand=(harvester,))
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

    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_smugglers_haven_may_pay_four_spice_for_one_vp() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        resources=Resources(spice=4),
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
    payment = next(
        action
        for action in legal_agent_card_payment_actions(placed, 0)
        if action.action_id == "pay_agent_card_spice"
    )

    result = apply_agent_card_payment(placed, payment)

    assert result.state.players[0].resources.spice == 0
    assert result.state.players[0].victory_points == 2
    assert result.events[0].kind == "agent_card_payment_resolved"


def test_smugglers_haven_trade_may_be_declined() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        resources=Resources(spice=4),
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
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state
    decline = next(
        action
        for action in legal_agent_card_payment_actions(placed, 0)
        if action.action_id == "decline_agent_card_payment"
    )

    result = apply_agent_card_payment(placed, decline)

    assert result.state.players[0].resources.spice == 4
    assert result.state.players[0].victory_points == 1
    assert result.events[0].kind == "agent_card_payment_declined"


def test_smugglers_haven_skips_unaffordable_trade() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        resources=Resources(spice=3),
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

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False
    assert legal_agent_card_payment_actions(placed, 0) == ()


def test_smugglers_haven_checks_trade_after_paying_the_board_space_cost() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        resources=Resources(spice=4),
        influence=Influence(spacing_guild=2),
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

    placed = apply_agent_action(state, _action_to(state, "shipping")).state

    assert placed.players[0].resources.spice == 1
    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False
    assert legal_agent_card_payment_actions(placed, 0) == ()


def test_fedaykin_stilltent_recruits_a_deployable_troop_at_a_maker_space() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    owner = PlayerState(player_id=0, hand=(stilltent,))
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
    placed = apply_agent_action(state, _action_to(state, "imperial_basin")).state

    result = resolve_agent_card_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].troops_supply == 8
    assert result.state.players[0].troops_garrison == 4
    assert context["troops_recruited"] == 1


def test_fedaykin_stilltent_has_no_agent_effect_away_from_maker_spaces() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    owner = PlayerState(player_id=0, hand=(stilltent,))
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

    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_northern_watermaster_gains_water_on_its_agent_turn() -> None:
    watermaster = _imperium_instance("northern_watermaster")
    owner = PlayerState(player_id=0, hand=(watermaster,))
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.water == 2
    assert result.events[0].kind == "agent_card_effect_resolved"


def test_maker_keeper_gains_each_reward_for_its_matching_influence() -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    owner = PlayerState(
        player_id=0,
        hand=(maker_keeper,),
        influence=Influence(bene_gesserit=2, fremen=2),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.spice == 1
    assert result.state.players[0].resources.water == 2


@pytest.mark.parametrize(
    ("influence", "expected_spice", "expected_water"),
    (
        (Influence(bene_gesserit=2), 0, 2),
        (Influence(fremen=2), 1, 1),
    ),
)
def test_maker_keeper_rewards_are_independent(
    influence: Influence,
    expected_spice: int,
    expected_water: int,
) -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    owner = PlayerState(
        player_id=0,
        hand=(maker_keeper,),
        influence=influence,
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.spice == expected_spice
    assert result.state.players[0].resources.water == expected_water


def test_maker_keeper_has_no_agent_effect_without_matching_influence() -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    owner = PlayerState(player_id=0, hand=(maker_keeper,))
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

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_southern_elders_recruits_with_bene_gesserit_bond() -> None:
    southern_elders = _imperium_instance("southern_elders")
    truthtrance = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(southern_elders,),
        in_play=(truthtrance,),
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
    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    result = resolve_agent_card_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].troops_supply == 7
    assert result.state.players[0].troops_garrison == 5
    assert context["troops_recruited"] == 2


def test_southern_elders_has_no_agent_effect_without_bene_gesserit_bond() -> None:
    southern_elders = _imperium_instance("southern_elders")
    owner = PlayerState(player_id=0, hand=(southern_elders,))
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

    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_weirding_woman_returns_to_hand_with_bene_gesserit_bond() -> None:
    weirding_woman = _imperium_instance("weirding_woman")
    truthtrance = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(weirding_woman,),
        in_play=(truthtrance,),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].hand == (weirding_woman,)
    assert result.state.players[0].in_play == (truthtrance,)


def test_weirding_woman_has_no_agent_effect_without_bene_gesserit_bond() -> None:
    weirding_woman = _imperium_instance("weirding_woman")
    owner = PlayerState(player_id=0, hand=(weirding_woman,))
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

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_ecological_testing_station_may_pay_water_to_draw_two() -> None:
    station = _imperium_instance("ecological_testing_station")
    first = _instance("dagger")
    second = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(station,),
        deck=(first, second),
        resources=Resources(water=2),
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
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state
    action = next(
        action
        for action in legal_agent_card_payment_actions(placed, 0)
        if action.action_id == "pay_agent_card_water"
    )

    result = apply_agent_card_payment(placed, action)

    assert result.state.players[0].resources.water == 0
    assert result.state.players[0].hand == (first, second)
    assert result.state.players[0].deck == ()
    assert result.events[0].kind == "agent_card_payment_resolved"


def test_ecological_testing_station_payment_may_be_declined() -> None:
    station = _imperium_instance("ecological_testing_station")
    owner = PlayerState(
        player_id=0,
        hand=(station,),
        resources=Resources(water=2),
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
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state
    action = next(
        action
        for action in legal_agent_card_payment_actions(placed, 0)
        if action.action_id == "decline_agent_card_payment"
    )

    result = apply_agent_card_payment(placed, action)

    assert result.state.players[0].resources.water == 2
    assert result.events[0].kind == "agent_card_payment_declined"


def test_ecological_testing_station_has_no_payment_without_two_water() -> None:
    station = _imperium_instance("ecological_testing_station")
    owner = PlayerState(player_id=0, hand=(station,))
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

    placed = apply_agent_action(state, _action_to(state, "fremkit")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_paracompass_gains_two_solari_on_its_agent_turn() -> None:
    paracompass = _imperium_instance("paracompass")
    owner = PlayerState(player_id=0, hand=(paracompass,))
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.solari == 2


def test_overthrow_gains_extra_influence_with_the_visited_faction() -> None:
    overthrow = _imperium_instance("overthrow")
    owner = PlayerState(player_id=0, hand=(overthrow,))
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
    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    result = resolve_agent_card_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].influence.bene_gesserit == 1
    assert context["pending_faction_influence"] is True


def test_bene_gesserit_operative_places_a_spy_on_an_empty_post() -> None:
    operative = _imperium_instance("bene_gesserit_operative")
    owner = PlayerState(player_id=0, hand=(operative,))
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
    placed_agent = apply_agent_action(state, _action_to(state, "secrets")).state
    engine = UprisingRulesEngine()
    choices = engine.legal_actions(placed_agent, 0)

    result = engine.apply(placed_agent, choices[0])
    post_id = dict(choices[0].arguments)["post_id"]

    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (post_id,)
    assert result.events[0].kind == "spy_placed"
    assert (
        dict(result.state.decision_stack[-1].context)["pending_agent_effect"] is False
    )


def test_bene_gesserit_operative_recalls_before_placing_when_supply_is_empty() -> None:
    operative = _imperium_instance("bene_gesserit_operative")
    posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    owner = PlayerState(
        player_id=0,
        hand=(operative,),
        spies_supply=0,
        spy_post_ids=posts,
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
    placed_agent = apply_agent_action(state, _action_to(state, "secrets")).state
    recall_action = legal_agent_card_spy_actions(placed_agent, 0)[0]

    recalled = apply_agent_card_spy_action(placed_agent, recall_action)
    recalled_post = dict(recall_action.arguments)["post_id"]
    placement = next(
        action
        for action in legal_agent_card_spy_actions(recalled.state, 0)
        if dict(action.arguments)["post_id"] == recalled_post
    )
    replaced = apply_agent_card_spy_action(recalled.state, placement)

    assert recalled.events[0].kind == "spy_recalled"
    assert replaced.state.players[0].spies_supply == 0
    assert set(replaced.state.players[0].spy_post_ids) == set(posts)


def test_reliable_informant_limits_spy_placement_to_three_faction_posts() -> None:
    informant = _imperium_instance("reliable_informant")
    owner = PlayerState(player_id=0, hand=(informant,))
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
    placed_agent = apply_agent_action(
        state,
        _action_to(state, "deliver_supplies"),
    ).state

    post_ids = {
        dict(action.arguments)["post_id"]
        for action in legal_agent_card_spy_actions(placed_agent, 0)
    }

    assert post_ids == {
        "emperor-sardaukar-dutiful-service",
        "spacing-guild-heighliner-deliver-supplies",
        "bene-gesserit-espionage-secrets",
    }


def test_reliable_informant_can_only_recall_a_spy_that_opens_a_target_post() -> None:
    informant = _imperium_instance("reliable_informant")
    target_posts = (
        "emperor-sardaukar-dutiful-service",
        "spacing-guild-heighliner-deliver-supplies",
        "bene-gesserit-espionage-secrets",
    )
    owner = PlayerState(
        player_id=0,
        hand=(informant,),
        spies_supply=0,
        spy_post_ids=(target_posts[0], "arrakis-hagga-basin", "arrakis-deep-desert"),
    )
    opponents = (
        PlayerState(player_id=1, spies_supply=2, spy_post_ids=(target_posts[1],)),
        PlayerState(player_id=2, spies_supply=2, spy_post_ids=(target_posts[2],)),
        PlayerState(player_id=3),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *opponents),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(
        state,
        _action_to(state, "deliver_supplies"),
    ).state

    actions = legal_agent_card_spy_actions(placed_agent, 0)

    assert tuple(dict(action.arguments)["post_id"] for action in actions) == (
        target_posts[0],
    )


def test_reliable_informant_finishes_when_every_target_post_is_unavailable() -> None:
    informant = _imperium_instance("reliable_informant")
    target_posts = (
        "emperor-sardaukar-dutiful-service",
        "spacing-guild-heighliner-deliver-supplies",
        "bene-gesserit-espionage-secrets",
    )
    owner = PlayerState(player_id=0, hand=(informant,))
    opponents = tuple(
        PlayerState(player_id=seat, spies_supply=2, spy_post_ids=(post_id,))
        for seat, post_id in enumerate(target_posts, start=1)
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *opponents),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(
        state,
        _action_to(state, "deliver_supplies"),
    ).state
    engine = UprisingRulesEngine()
    unavailable = next(
        action
        for action in engine.legal_actions(placed_agent, 0)
        if action.action_id == "resolve_agent_card_effect"
    )

    result = engine.apply(placed_agent, unavailable)

    assert result.events[0].kind == "agent_card_effect_unavailable"
    assert (
        dict(result.state.decision_stack[-1].context)["pending_agent_effect"] is False
    )


def test_strike_fleet_recruits_three_after_gathering_intelligence() -> None:
    strike_fleet = _imperium_instance("strike_fleet")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(strike_fleet,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
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
    placed_agent = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed_agent, 0)
        if action.action_id == "gather_intelligence"
    )

    gathered = apply_gather_intelligence_action(placed_agent, gather)
    result = resolve_agent_card_effect(gathered.state)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].spy_post_ids == ()
    assert result.state.players[0].hand == (drawn,)
    assert result.state.players[0].troops_supply == 6
    assert result.state.players[0].troops_garrison == 6
    assert context["troops_recruited"] == 3


def test_imperial_spymaster_draws_intrigue_after_gathering_intelligence() -> None:
    spymaster = _imperium_instance("imperial_spymaster")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(spymaster,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:test:0",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed_agent, 0)
        if action.action_id == "gather_intelligence"
    )

    gathered = apply_gather_intelligence_action(placed_agent, gather)
    result = resolve_agent_card_effect(gathered.state)

    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert tuple(event.kind for event in result.events) == (
        "agent_card_effect_resolved",
        "intrigue_card_drawn",
    )


def test_maker_keeper_resolves_as_unavailable_after_influence_drops() -> None:
    # Both Influence conditions are judged when the effect resolves in the
    # player's chosen order [Main pp. 7, 9]; a mid-frame Influence loss (for
    # example an Intrigue cost) forfeits the queued conditional gains.
    maker_keeper = _imperium_instance("maker_keeper")
    owner = PlayerState(
        player_id=0,
        hand=(maker_keeper,),
        influence=Influence(fremen=2),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    lowered_owner = replace(placed.players[0], influence=Influence())
    lowered = replace(placed, players=(lowered_owner, *placed.players[1:]))

    result = resolve_agent_card_effect(lowered)

    assert result.state.players[0].resources.spice == 0
    assert result.state.players[0].resources.water == 1
    assert result.events[0].kind == "agent_card_effect_unavailable"


def test_in_high_places_bond_is_judged_when_the_effect_resolves() -> None:
    # Trashing the bonded card mid-frame (for example through an Intrigue
    # trash slot) forfeits the conditional gain [Main pp. 9, 20].
    in_high_places = _imperium_instance("in_high_places")
    truthtrance = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(in_high_places,),
        in_play=(truthtrance,),
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
    placed = apply_agent_action(state, _action_to(state, "secrets")).state
    trashed_owner = replace(
        placed.players[0],
        in_play=tuple(
            card for card in placed.players[0].in_play if card != truthtrance
        ),
        trashed=(truthtrance,),
    )
    lowered = replace(placed, players=(trashed_owner, *placed.players[1:]))

    result = resolve_agent_card_effect(lowered)

    assert result.state.players[0].resources.water == 1
    assert result.events[0].kind == "agent_card_effect_unavailable"


def test_seek_allies_box_expires_after_a_mid_frame_trash() -> None:
    # A freely ordered Intrigue trash slot can trash the played card before
    # its Agent box resolves; the un-activated box then expires instead of
    # resolving, because you can't receive or activate an effect from a card
    # that is already trashed (OQ-022 designer ruling).
    state = _state("seek_allies")
    card = state.players[0].hand[0]
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state
    trashed_owner = replace(
        placed.players[0],
        in_play=tuple(
            candidate for candidate in placed.players[0].in_play if candidate != card
        ),
        trashed=(card,),
    )
    lowered = replace(placed, players=(trashed_owner, *placed.players[1:]))

    expired = expire_trashed_card_effects(RuleResult(state=lowered))

    assert expired.state.players[0].trashed == (card,)
    assert [event.kind for event in expired.events] == ["agent_card_effect_expired"]
    assert (
        dict(expired.state.decision_stack[-1].context)["pending_agent_effect"]
        is False
    )


def test_corrinth_city_first_selection_resets_when_the_card_leaves_hand() -> None:
    # A freely ordered effect (for example an Intrigue discard cost) can
    # consume the stored first selection before the payment completes; the
    # atomic cost then restarts from no selection [Main pp. 9, 20].
    corrinth_city = _imperium_instance("corrinth_city")
    dagger = _instance("dagger")
    diplomacy = _instance("diplomacy")
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city, favor, dagger, diplomacy),
        resources=Resources(solari=5),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    selection = next(
        action
        for action in legal_corrinth_city_payment_actions(placed, 0)
        if dict(action.arguments).get("card_id") == favor
    )
    selected = apply_corrinth_city_payment(placed, selection).state

    discarded_owner = replace(
        selected.players[0],
        hand=tuple(card for card in selected.players[0].hand if card != favor),
        discard_pile=(favor,),
    )
    lowered = replace(selected, players=(discarded_owner, *selected.players[1:]))

    actions = legal_corrinth_city_payment_actions(lowered, 0)
    assert {action.action_id for action in actions} == {
        "decline_corrinth_city_payment",
        "select_corrinth_city_discard",
    }
    assert {
        dict(action.arguments).get("card_id")
        for action in actions
        if action.action_id == "select_corrinth_city_discard"
    } == {dagger, diplomacy}


def test_in_high_places_gains_water_with_bene_gesserit_bond() -> None:
    in_high_places = _imperium_instance("in_high_places")
    truthtrance = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(in_high_places,),
        in_play=(truthtrance,),
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
    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.water == 2


def test_rebel_supplier_recruits_two_after_gathering_intelligence() -> None:
    supplier = _imperium_instance("rebel_supplier")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(supplier,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
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
    placed_agent = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed_agent, 0)
        if action.action_id == "gather_intelligence"
    )

    gathered = apply_gather_intelligence_action(placed_agent, gather)
    result = resolve_agent_card_effect(gathered.state)

    assert result.state.players[0].troops_supply == 7
    assert result.state.players[0].troops_garrison == 5
    assert dict(result.state.decision_stack[-1].context)["troops_recruited"] == 2


def test_dangerous_rhetoric_trashes_itself_for_chosen_influence() -> None:
    rhetoric = _imperium_instance("dangerous_rhetoric")
    owner = PlayerState(player_id=0, hand=(rhetoric,))
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    choices = legal_agent_card_influence_actions(placed, 0)
    action = next(
        action
        for action in choices
        if dict(action.arguments)["faction"] == "fremen"
    )

    result = apply_agent_card_influence(placed, action)
    resolved_owner = result.state.players[0]

    assert len(choices) == 4
    assert rhetoric not in resolved_owner.in_play
    assert resolved_owner.trashed == (rhetoric,)
    assert resolved_owner.influence.fremen == 1
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False
    assert tuple(event.kind for event in result.events) == (
        "card_trashed",
        "influence_gained",
    )


def test_public_spectacle_gains_chosen_influence_after_spy_recall() -> None:
    spectacle = _imperium_instance("public_spectacle")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(spectacle,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed, 0)
        if action.action_id == "gather_intelligence"
    )
    gathered = apply_gather_intelligence_action(placed, gather).state
    engine = UprisingRulesEngine()
    choice = next(
        action
        for action in engine.legal_actions(gathered, 0)
        if dict(action.arguments).get("faction") == "spacing_guild"
    )

    result = engine.apply(gathered, choice)

    assert result.state.players[0].influence.spacing_guild == 1
    assert result.state.players[0].in_play == (spectacle,)
    assert result.events[0].kind == "influence_gained"


def test_public_spectacle_influence_is_unavailable_without_spy_recall() -> None:
    spectacle = _imperium_instance("public_spectacle")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(spectacle,),
        spies_supply=2,
        spy_post_ids=(post_id,),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].influence == Influence()
    assert result.events[0].kind == "agent_card_effect_unavailable"


@pytest.mark.parametrize(
    ("influence", "expected_solari", "expected_spice"),
    (
        (Influence(emperor=2), 2, 0),
        (Influence(spacing_guild=2), 0, 1),
        (Influence(emperor=2, spacing_guild=2), 2, 1),
    ),
)
def test_wheels_within_wheels_rewards_are_independent(
    influence: Influence,
    expected_solari: int,
    expected_spice: int,
) -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    owner = PlayerState(
        player_id=0,
        hand=(wheels,),
        influence=influence,
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.solari == expected_solari
    assert result.state.players[0].resources.spice == expected_spice


def test_wheels_within_wheels_has_no_agent_effect_below_both_thresholds() -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    owner = PlayerState(
        player_id=0,
        hand=(wheels,),
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
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

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_stilgar_recruits_two_deployable_troops() -> None:
    stilgar = _imperium_instance("stilgar_the_devoted")
    owner = PlayerState(player_id=0, hand=(stilgar,))
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].troops_supply == 7
    assert result.state.players[0].troops_garrison == 5
    assert dict(result.state.decision_stack[-1].context)["troops_recruited"] == 2


def test_leadership_draws_one_card_per_sandworm_in_conflict() -> None:
    leadership = _imperium_instance("leadership")
    first = _instance("dagger")
    second = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(leadership,),
        deck=(first, second),
        sandworms_conflict=2,
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
    placed = apply_agent_action(state, _action_to(state, "hagga_basin")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].hand == (first, second)
    assert result.state.players[0].deck == ()
    assert tuple(event.kind for event in result.events) == (
        "agent_card_effect_resolved",
    )


def test_leadership_has_no_agent_effect_without_a_sandworm() -> None:
    leadership = _imperium_instance("leadership")
    owner = PlayerState(player_id=0, hand=(leadership,))
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

    placed = apply_agent_action(state, _action_to(state, "hagga_basin")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_desert_power_gains_two_spice_on_a_maker_space() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(player_id=0, hand=(desert_power,))
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

    placed = apply_agent_action(state, _action_to(state, "hagga_basin")).state
    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.spice == 2
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_desert_power_has_no_agent_effect_on_a_non_maker_space() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(player_id=0, hand=(desert_power,))
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

    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def _subversive_state(
    *,
    influence: Influence | None = None,
    spy_post_id: str = "emperor-sardaukar-dutiful-service",
) -> GameState:
    subversive = _imperium_instance("subversive_advisor")
    owner = PlayerState(
        player_id=0,
        hand=(subversive,),
        influence=influence if influence is not None else Influence(),
        spies_supply=2,
        spy_post_ids=(spy_post_id,),
    )
    return GameState(
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


def test_subversive_advisor_replaces_faction_influence_and_trashes_itself() -> None:
    state = _subversive_state()
    subversive = state.players[0].hand[0]
    opponent = replace(
        state.players[1],
        agents_available=1,
        agent_locations=("dutiful_service",),
    )
    state = replace(state, players=(state.players[0], opponent, *state.players[2:]))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state
    engine = UprisingRulesEngine()

    context = dict(placed.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert context["pending_faction_influence"] is False
    assert {
        action.action_id for action in engine.legal_actions(placed, 0)
    } == {"resolve_agent_card_effect", "resolve_board_effect"}

    result = engine.apply(
        placed,
        DomainAction(action_id="resolve_agent_card_effect", actor=0),
    )
    owner = result.state.players[0]

    assert owner.influence.emperor == 2
    assert owner.in_play == ()
    assert owner.trashed == (subversive,)
    assert dict(result.state.decision_stack[-1].context)[
        "pending_faction_influence"
    ] is False
    assert [event.kind for event in result.events] == [
        "influence_gained",
        "card_trashed",
    ]
    assert {
        action.action_id for action in engine.legal_actions(result.state, 0)
    } == {"resolve_board_effect"}


def test_subversive_advisor_box_expires_after_a_mid_frame_trash() -> None:
    # When a freely ordered Intrigue trash slot already trashed this card,
    # its un-activated Agent box expires without the Influence gain: you
    # can't receive or activate an effect from a card that is already
    # trashed (OQ-022 designer ruling).
    state = _subversive_state()
    subversive = state.players[0].hand[0]
    opponent = replace(
        state.players[1],
        agents_available=1,
        agent_locations=("dutiful_service",),
    )
    state = replace(state, players=(state.players[0], opponent, *state.players[2:]))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state
    trashed_owner = replace(
        placed.players[0],
        in_play=tuple(
            card for card in placed.players[0].in_play if card != subversive
        ),
        trashed=(subversive,),
    )
    lowered = replace(placed, players=(trashed_owner, *placed.players[1:]))

    expired = expire_trashed_card_effects(RuleResult(state=lowered))
    owner = expired.state.players[0]

    assert owner.influence.emperor == 0
    assert owner.trashed == (subversive,)
    assert expired.events[-1].kind == "agent_card_effect_expired"
    assert (
        dict(expired.state.decision_stack[-1].context)["pending_agent_effect"]
        is False
    )


def test_subversive_advisor_uses_shared_influence_boundary_and_alliance_rules() -> None:
    state = _subversive_state(influence=Influence(emperor=3))
    challenger = replace(state.players[0], victory_points=1)
    holder = replace(
        state.players[1],
        influence=Influence(emperor=4),
        alliance_faction_ids=(Faction.EMPEROR.value,),
        victory_points=2,
    )
    state = replace(state, players=(challenger, holder, *state.players[2:]))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].influence.emperor == 5
    assert result.state.players[0].alliance_faction_ids == (Faction.EMPEROR.value,)
    assert result.state.players[0].victory_points == 2
    assert result.state.players[1].alliance_faction_ids == ()
    assert result.state.players[1].victory_points == 1


def test_subversive_advisor_is_unavailable_on_a_non_faction_spy_destination() -> None:
    state = _subversive_state(
        spy_post_id="choam-shipping-accept-contract",
    )
    subversive = state.players[0].hand[0]
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    context = dict(placed.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert context["pending_faction_influence"] is False
    assert placed.players[0].in_play == (subversive,)
    assert placed.players[0].trashed == ()
    assert all(
        action.action_id != "resolve_agent_card_effect"
        for action in UprisingRulesEngine().legal_actions(placed, 0)
    )


def _long_live_state(
    deck: tuple[str, ...],
    *,
    discard_pile: tuple[str, ...] = (),
    intrigue_deck: tuple[str, ...] = (),
) -> GameState:
    long_live = _imperium_instance("long_live_the_fighters")
    owner = PlayerState(
        player_id=0,
        hand=(long_live,),
        deck=deck,
        discard_pile=discard_pile,
    )
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=intrigue_deck,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def test_long_live_the_fighters_commits_draw_discard_and_trash_atomically() -> None:
    first = _instance("dagger")
    second = _instance("convincing_argument")
    third = _instance("dune_the_desert_planet")
    tail = _instance("reconnaissance")
    state = _long_live_state((first, second, third, tail))
    engine = UprisingRulesEngine()

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    assert {
        action.action_id for action in engine.legal_actions(placed, 0)
    } == {"resolve_agent_card_effect", "resolve_board_effect", "deploy_troops"}

    ready = engine.apply(
        placed,
        DomainAction(action_id="resolve_agent_card_effect", actor=0),
    ).state
    first_actions = legal_agent_card_long_live_actions(ready, 0)
    assert {dict(action.arguments)["card_id"] for action in first_actions} == {
        first,
        second,
        third,
    }

    selected = engine.apply(
        ready,
        next(
            action
            for action in first_actions
            if dict(action.arguments)["card_id"] == first
        ),
    )
    selected_owner = selected.state.players[0]
    assert selected_owner.deck == (first, second, third, tail)
    assert selected_owner.hand == ()
    assert selected_owner.discard_pile == ()
    assert selected_owner.trashed == ()
    assert {
        action.action_id for action in engine.legal_actions(selected.state, 0)
    } == {"select_long_live_fighters_discard"}

    discard = next(
        action
        for action in legal_agent_card_long_live_actions(selected.state, 0)
        if dict(action.arguments)["card_id"] == second
    )
    result = engine.apply(selected.state, discard)
    owner = result.state.players[0]
    assert owner.deck == (tail,)
    assert owner.hand == (first,)
    assert owner.discard_pile == (second,)
    assert owner.trashed == (third,)
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert "long_live_fighters_draw_card_id" not in context
    assert "long_live_fighters_selection_started" not in context
    assert context["pending_board_effect"] is True
    assert [event.kind for event in result.events] == [
        "card_discarded",
        "card_trashed",
        "agent_card_effect_resolved",
    ]


def test_long_live_the_fighters_only_offers_the_top_three_and_preserves_tail() -> None:
    first = _instance("dagger")
    second = _instance("convincing_argument")
    third = _instance("dune_the_desert_planet")
    tail = _instance("reconnaissance")
    state = _long_live_state((first, second, third, tail))
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    ready = resolve_agent_card_effect(placed).state
    selected = apply_agent_card_long_live_action(
        ready,
        next(
            action
            for action in legal_agent_card_long_live_actions(ready, 0)
            if dict(action.arguments)["card_id"] == first
        ),
    ).state

    discard_actions = legal_agent_card_long_live_actions(selected, 0)
    assert {dict(action.arguments)["card_id"] for action in discard_actions} == {
        second,
        third,
    }
    with pytest.raises(ValueError, match="not a legal Long Live"):
        apply_agent_card_long_live_action(
            selected,
            DomainAction(
                action_id="select_long_live_fighters_discard",
                actor=0,
                arguments=(("card_id", tail),),
            ),
        )


def test_long_live_the_fighters_skips_effect_without_three_deck_cards() -> None:
    first = _instance("dagger")
    second = _instance("convincing_argument")
    state = _long_live_state(
        (first, second),
        discard_pile=(_instance("reconnaissance"),),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].deck == (first, second)
    assert result.state.players[0].discard_pile == (_instance("reconnaissance"),)
    assert result.state.decision_stack[-1].frame_id == (
        "round:1:player:0:agent_effects"
    )
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False
    assert isinstance(result.state.decision_stack[-1].decision, PlayerDecision)
    assert result.state.decision_stack[-1].decision.owner == 0
    assert result.events[0].kind == "agent_card_effect_unavailable"


def test_personal_card_trash_rejects_deck_without_explicit_permission() -> None:
    deck_card = _instance("dagger")
    state = _long_live_state((deck_card,))

    with pytest.raises(ValueError, match="eligible owned zone"):
        trash_personal_card(
            state,
            0,
            deck_card,
            source="test:trash",
        )


def test_long_live_the_fighters_rechecks_deck_after_a_board_draw() -> None:
    first = _instance("dagger")
    second = _instance("convincing_argument")
    third = _instance("dune_the_desert_planet")
    state = _long_live_state((first, second, third))
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    after_board = resolve_board_effect(placed).state
    assert after_board.players[0].deck == (second, third)
    assert after_board.players[0].hand == (first,)

    result = resolve_agent_card_effect(after_board)

    assert result.state.players[0].deck == (second, third)
    assert result.state.players[0].hand == (first,)
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_long_live_the_fighters_can_start_after_board_draw_reshuffles_discard() -> None:
    first = _instance("dagger")
    second = _instance("convincing_argument")
    third = _instance("dune_the_desert_planet")
    fourth = _instance("reconnaissance")
    state = _long_live_state((), discard_pile=(first, second, third, fourth))
    engine = UprisingRulesEngine()
    placed = engine.apply(
        state,
        _action_to(state, "arrakeen"),
    ).state

    board_action = next(
        action
        for action in engine.legal_actions(placed, 0)
        if action.action_id == "resolve_board_effect"
    )
    pending = engine.apply(placed, board_action).state
    chance = engine.current_decision(pending)
    assert isinstance(chance, ChanceDecision)
    assert chance.count == 4

    reshuffled = engine.apply(
        pending,
        ChanceOutcome(chance.decision_id, (fourth, third, second, first)),
    ).state
    assert reshuffled.players[0].deck == (third, second, first)
    assert reshuffled.players[0].hand == (fourth,)
    assert reshuffled.players[0].discard_pile == ()

    resolve = next(
        action
        for action in engine.legal_actions(reshuffled, 0)
        if action.action_id == "resolve_agent_card_effect"
    )
    ready = engine.apply(reshuffled, resolve).state
    actions = engine.legal_actions(ready, 0)
    assert {action.action_id for action in actions} == {
        "select_long_live_fighters_draw"
    }
    assert {
        dict(action.arguments)["card_id"] for action in actions
    } == {third, second, first}


def test_long_live_the_fighters_trashes_from_deck_with_shared_trash_triggers() -> None:
    draw_card = _instance("dagger")
    discard_card = _instance("convincing_argument")
    sardaukar = _imperium_instance("sardaukar_soldier")
    state = _long_live_state(
        (draw_card, discard_card, sardaukar),
        intrigue_deck=("intrigue:test",),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    ready = resolve_agent_card_effect(placed).state
    first_selected = apply_agent_card_long_live_action(
        ready,
        next(
            action
            for action in legal_agent_card_long_live_actions(ready, 0)
            if dict(action.arguments)["card_id"] == draw_card
        ),
    ).state
    result = apply_agent_card_long_live_action(
        first_selected,
        next(
            action
            for action in legal_agent_card_long_live_actions(first_selected, 0)
            if dict(action.arguments)["card_id"] == discard_card
        ),
    )

    owner = result.state.players[0]
    assert owner.hand == (draw_card,)
    assert owner.discard_pile == (discard_card,)
    assert owner.trashed == (sardaukar,)
    assert owner.intrigue_cards == ("intrigue:test",)
    assert result.state.intrigue_deck == ()
    assert [event.kind for event in result.events] == [
        "card_discarded",
        "card_trashed",
        "intrigue_card_drawn",
        "agent_card_effect_resolved",
    ]


def test_long_live_the_fighters_returns_a_trashed_reserve_card_to_its_stack() -> None:
    draw_card = _instance("dagger")
    discard_card = _instance("convincing_argument")
    reserve_card = "reserve:prepare_the_way:7"
    state = _long_live_state((draw_card, discard_card, reserve_card))
    state = replace(
        state,
        reserve_stacks=(
            ("prepare_the_way", 7),
            ("the_spice_must_flow", 10),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    ready = resolve_agent_card_effect(placed).state
    selected = apply_agent_card_long_live_action(
        ready,
        next(
            action
            for action in legal_agent_card_long_live_actions(ready, 0)
            if dict(action.arguments)["card_id"] == draw_card
        ),
    ).state
    result = apply_agent_card_long_live_action(
        selected,
        next(
            action
            for action in legal_agent_card_long_live_actions(selected, 0)
            if dict(action.arguments)["card_id"] == discard_card
        ),
    )

    assert result.state.players[0].trashed == ()
    assert dict(result.state.reserve_stacks)["prepare_the_way"] == 8


def test_long_live_the_fighters_top_three_discard_skips_hand_discard_trigger() -> None:
    draw_card = _instance("dagger")
    favor = _imperium_instance("spacing_guild_s_favor")
    trash_card = _instance("convincing_argument")
    state = _long_live_state((draw_card, favor, trash_card))
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    ready = resolve_agent_card_effect(placed).state
    selected = apply_agent_card_long_live_action(
        ready,
        next(
            action
            for action in legal_agent_card_long_live_actions(ready, 0)
            if dict(action.arguments)["card_id"] == draw_card
        ),
    ).state
    result = apply_agent_card_long_live_action(
        selected,
        next(
            action
            for action in legal_agent_card_long_live_actions(selected, 0)
            if dict(action.arguments)["card_id"] == favor
        ),
    )

    assert result.state.players[0].discard_pile == (favor,)
    assert result.state.players[0].resources.spice == 0
    assert [event.kind for event in result.events] == [
        "card_discarded",
        "card_trashed",
        "agent_card_effect_resolved",
    ]


def test_shishakli_may_trash_a_personal_card_to_draw_one() -> None:
    shishakli = _imperium_instance("shishakli")
    trashed_card = _instance("dagger")
    drawn_card = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(shishakli, trashed_card),
        deck=(drawn_card,),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    action = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if dict(action.arguments).get("card_id") == trashed_card
    )

    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].trashed == (trashed_card,)
    assert result.state.players[0].hand == (drawn_card,)
    assert result.state.players[0].deck == ()
    assert result.events[0].kind == "card_trashed"


def test_shishakli_trash_draw_may_be_declined() -> None:
    shishakli = _imperium_instance("shishakli")
    drawn_card = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(shishakli,),
        deck=(drawn_card,),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    decline = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if action.action_id == "decline_agent_card_trash"
    )

    result = apply_agent_card_trash(placed, decline)

    assert result.state.players[0].hand == ()
    assert result.state.players[0].deck == (drawn_card,)
    assert result.state.players[0].trashed == ()


def test_tread_in_darkness_may_trash_and_draw_with_bene_gesserit_bond() -> None:
    tread = _imperium_instance("tread_in_darkness")
    bond_card = _imperium_instance("truthtrance")
    trashed_card = _instance("dagger")
    drawn_card = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(tread, trashed_card),
        deck=(drawn_card,),
        in_play=(bond_card,),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    action = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if dict(action.arguments).get("card_id") == trashed_card
    )

    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].trashed == (trashed_card,)
    assert result.state.players[0].hand == (drawn_card,)
    assert result.state.players[0].in_play == (bond_card, tread)


def test_tread_in_darkness_has_no_agent_effect_without_bond() -> None:
    tread = _imperium_instance("tread_in_darkness")
    owner = PlayerState(player_id=0, hand=(tread,))
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

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


@pytest.mark.parametrize(
    ("discarded_card_id", "expected_hand_count", "expected_deck_count"),
    (
        ("dagger", 1, 1),
        ("reliable_informant", 2, 0),
    ),
)
def test_space_time_folding_draw_depends_on_discarded_card_faction(
    discarded_card_id: str,
    expected_hand_count: int,
    expected_deck_count: int,
) -> None:
    folding = _imperium_instance("space_time_folding")
    discarded = (
        _instance(discarded_card_id)
        if discarded_card_id == "dagger"
        else _imperium_instance(discarded_card_id)
    )
    first = _instance("convincing_argument")
    second = _instance("reconnaissance")
    owner = PlayerState(
        player_id=0,
        hand=(folding, discarded),
        deck=(first, second),
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
    action = next(
        action
        for action in legal_agent_card_discard_actions(placed, 0)
        if action.action_id == "discard_agent_card"
    )

    result = apply_agent_card_discard(placed, action)

    assert result.state.players[0].discard_pile == (discarded,)
    assert len(result.state.players[0].hand) == expected_hand_count
    assert len(result.state.players[0].deck) == expected_deck_count
    assert result.events[0].kind == "card_discarded"


def test_space_time_folding_has_no_agent_effect_without_another_hand_card() -> None:
    folding = _imperium_instance("space_time_folding")
    owner = PlayerState(player_id=0, hand=(folding,))
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

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


@pytest.mark.parametrize(
    ("discarded_card_id", "expected_hand_count", "expected_deck_count"),
    (
        ("dagger", 0, 2),
        ("reliable_informant", 2, 0),
    ),
)
def test_guild_envoy_requires_discard_and_only_draws_for_spacing_guild(
    discarded_card_id: str,
    expected_hand_count: int,
    expected_deck_count: int,
) -> None:
    envoy = _imperium_instance("guild_envoy")
    discarded = (
        _instance(discarded_card_id)
        if discarded_card_id == "dagger"
        else _imperium_instance(discarded_card_id)
    )
    first = _instance("convincing_argument")
    second = _instance("reconnaissance")
    owner = PlayerState(
        player_id=0,
        hand=(envoy, discarded),
        deck=(first, second),
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
    actions = legal_agent_card_discard_actions(placed, 0)

    assert {action.action_id for action in actions} == {"discard_agent_card"}
    result = apply_agent_card_discard(placed, actions[0])

    assert result.state.players[0].discard_pile == (discarded,)
    assert len(result.state.players[0].hand) == expected_hand_count
    assert len(result.state.players[0].deck) == expected_deck_count


def test_guild_envoy_has_no_agent_effect_without_another_hand_card() -> None:
    envoy = _imperium_instance("guild_envoy")
    owner = PlayerState(player_id=0, hand=(envoy,))
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

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_captured_mentat_may_discard_to_draw_intrigue_and_personal_card() -> None:
    mentat = _imperium_instance("captured_mentat")
    discarded = _instance("dagger")
    drawn = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(mentat, discarded),
        deck=(drawn,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:plot",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    actions = legal_agent_card_discard_actions(placed, 0)

    assert {action.action_id for action in actions} == {
        "decline_agent_card_discard",
        "discard_agent_card",
    }
    result = apply_agent_card_discard(
        placed,
        next(action for action in actions if action.action_id == "discard_agent_card"),
    )

    assert result.state.players[0].discard_pile == (discarded,)
    assert result.state.players[0].hand == (drawn,)
    assert result.state.players[0].intrigue_cards == ("intrigue:plot",)
    assert result.state.intrigue_deck == ()
    assert [event.kind for event in result.events] == [
        "card_discarded",
        "intrigue_card_drawn",
    ]


def test_captured_mentat_cannot_pay_discard_without_intrigue_reward() -> None:
    mentat = _imperium_instance("captured_mentat")
    owner = PlayerState(player_id=0, hand=(mentat, _instance("dagger")))
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

    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    assert legal_agent_card_discard_actions(placed, 0) == (
        DomainAction(action_id="decline_agent_card_discard", actor=0),
    )


@pytest.mark.parametrize(
    ("discarded_card_id", "draws_intrigue"),
    (
        ("dagger", False),
        ("reliable_informant", True),
    ),
)
def test_guild_spy_may_cycle_and_draws_intrigue_for_guild_discard(
    discarded_card_id: str,
    draws_intrigue: bool,
) -> None:
    guild_spy = _imperium_instance("guild_spy")
    discarded = (
        _instance(discarded_card_id)
        if discarded_card_id == "dagger"
        else _imperium_instance(discarded_card_id)
    )
    drawn = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(guild_spy, discarded),
        deck=(drawn,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:plot",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    actions = legal_agent_card_discard_actions(placed, 0)

    assert {action.action_id for action in actions} == {
        "decline_agent_card_discard",
        "discard_agent_card",
    }
    result = apply_agent_card_discard(
        placed,
        next(action for action in actions if action.action_id == "discard_agent_card"),
    )

    assert result.state.players[0].discard_pile == (discarded,)
    assert result.state.players[0].hand == (drawn,)
    assert result.state.players[0].intrigue_cards == (
        ("intrigue:plot",) if draws_intrigue else ()
    )
    assert [event.kind for event in result.events] == [
        "card_discarded",
        *(["intrigue_card_drawn"] if draws_intrigue else []),
    ]


def test_guild_spy_cannot_discard_guild_card_without_intrigue_reward() -> None:
    guild_spy = _imperium_instance("guild_spy")
    guild_card = _imperium_instance("reliable_informant")
    non_guild_card = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(guild_spy, guild_card, non_guild_card),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    actions = legal_agent_card_discard_actions(placed, 0)

    assert tuple(
        dict(action.arguments).get("card_id")
        for action in actions
        if action.action_id == "discard_agent_card"
    ) == (non_guild_card,)


def test_covert_operation_makes_opponents_with_cards_discard_clockwise() -> None:
    covert_operation = _imperium_instance("covert_operation")
    first_discard = _instance("dagger").replace("player:0:", "player:1:")
    second_discard = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(covert_operation,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            owner,
            PlayerState(player_id=1, hand=(first_discard,)),
            PlayerState(player_id=2, hand=(second_discard,)),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    pending = resolve_agent_card_effect(placed)
    engine = UprisingRulesEngine()

    assert pending.state.decision_stack[-1].decision == PlayerDecision(
        owner=1,
        prompt="Choose a card to discard for Covert Operation",
    )
    assert engine.legal_actions(pending.state, 2) == ()
    first = engine.apply(pending.state, engine.legal_actions(pending.state, 1)[0])
    assert first.state.players[1].discard_pile == (first_discard,)
    assert first.state.decision_stack[-1].decision == PlayerDecision(
        owner=2,
        prompt="Choose a card to discard for Covert Operation",
    )

    second = engine.apply(first.state, engine.legal_actions(first.state, 2)[0])

    assert second.state.players[2].discard_pile == (second_discard,)
    assert second.state.players[2].resources.spice == 2
    resumed = second.state.decision_stack[-1].decision
    assert isinstance(resumed, PlayerDecision)
    assert resumed.owner == 0
    assert [event.kind for event in second.events] == [
        "card_discarded",
        "personal_card_discard_effect_resolved",
    ]


def test_covert_operation_resolved_last_still_ends_the_agent_turn() -> None:
    covert_operation = _imperium_instance("covert_operation")
    first_discard = _instance("dagger").replace("player:0:", "player:1:")
    second_discard = _instance("dagger").replace("player:0:", "player:2:")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(covert_operation,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        intrigue_deck=intrigue_deck_instance_ids(False)[:1],
        players=(
            owner,
            PlayerState(player_id=1, hand=(first_discard,)),
            PlayerState(player_id=2, hand=(second_discard,)),
            PlayerState(player_id=3),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    engine = UprisingRulesEngine()
    current = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    # Resolve every other pending group first so the card effect is last.
    while True:
        others = [
            action
            for action in engine.legal_actions(current, 0)
            if action.action_id != "resolve_agent_card_effect"
        ]
        if not others:
            break
        current = engine.apply(current, others[0]).state
    current = engine.apply(
        current, DomainAction(action_id="resolve_agent_card_effect", actor=0)
    ).state
    current = engine.apply(current, engine.legal_actions(current, 1)[0]).state
    current = engine.apply(current, engine.legal_actions(current, 2)[0]).state

    top = current.decision_stack[-1]
    assert top.kind == "turn"
    assert isinstance(top.decision, PlayerDecision)
    assert top.decision.owner == 1
    assert engine.legal_actions(current, 1)


def test_spacing_guilds_favor_draws_one_on_agent_turn() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    drawn = _instance("dagger")
    owner = PlayerState(player_id=0, hand=(favor,), deck=(drawn,))
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
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].hand == (drawn,)
    assert result.state.players[0].in_play == (favor,)


def test_agent_card_discard_resolves_spacing_guilds_favor_trigger() -> None:
    envoy = _imperium_instance("guild_envoy")
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(envoy, favor),
        deck=(_instance("dagger"), _instance("reconnaissance")),
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
    discard = next(
        action
        for action in legal_agent_card_discard_actions(placed, 0)
        if dict(action.arguments).get("card_id") == favor
    )

    result = apply_agent_card_discard(placed, discard)

    assert result.state.players[0].resources.spice == 2
    assert len(result.state.players[0].hand) == 2
    assert result.state.players[0].discard_pile == (favor,)
    assert [event.kind for event in result.events[:2]] == [
        "card_discarded",
        "personal_card_discard_effect_resolved",
    ]


def test_double_agent_may_share_opponent_post_when_spying_on_visited_space() -> None:
    double_agent = _imperium_instance("double_agent")
    connected = "landsraad-assembly-hall-gather-support"
    opponent_post = "emperor-sardaukar-dutiful-service"
    owner = PlayerState(
        player_id=0,
        hand=(double_agent,),
        spies_supply=2,
        spy_post_ids=(connected,),
    )
    opponent = PlayerState(
        player_id=1,
        spies_supply=2,
        spy_post_ids=(opponent_post,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, opponent, PlayerState(player_id=2), PlayerState(player_id=3)),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    shared = next(
        action
        for action in legal_agent_card_spy_actions(placed, 0)
        if dict(action.arguments)["post_id"] == opponent_post
    )

    result = apply_agent_card_spy_action(placed, shared).state

    assert opponent_post in result.players[0].spy_post_ids
    assert opponent_post in result.players[1].spy_post_ids


def test_double_agent_cannot_share_post_without_spying_on_visited_space() -> None:
    double_agent = _imperium_instance("double_agent")
    opponent_post = "emperor-sardaukar-dutiful-service"
    owner = PlayerState(player_id=0, hand=(double_agent,))
    opponent = PlayerState(
        player_id=1,
        spies_supply=2,
        spy_post_ids=(opponent_post,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, opponent, PlayerState(player_id=2), PlayerState(player_id=3)),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    post_ids = {
        dict(action.arguments)["post_id"]
        for action in legal_agent_card_spy_actions(placed, 0)
    }

    assert opponent_post not in post_ids


def test_calculus_of_power_trashes_itself_on_agent_turn() -> None:
    calculus = _imperium_instance("calculus_of_power")
    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        hand=(calculus,),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].in_play == ()
    assert result.state.players[0].trashed == (calculus,)
    assert result.events[0].kind == "card_trashed"


def test_branching_path_alliance_trash_draws_intrigue_and_recruits_two() -> None:
    branching_path = _imperium_instance("branching_path")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        alliance_faction_ids=(Faction.BENE_GESSERIT.value,),
        hand=(branching_path, sardaukar),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:trash", "intrigue:reward"),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    action = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if dict(action.arguments).get("card_id") == sardaukar
    )

    result = apply_agent_card_trash(placed, action)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].trashed == (sardaukar,)
    assert result.state.players[0].intrigue_cards == (
        "intrigue:trash",
        "intrigue:reward",
    )
    assert result.state.players[0].troops_supply == 7
    assert result.state.players[0].troops_garrison == 5
    assert context["troops_recruited"] == 2
    assert [event.kind for event in result.events] == [
        "card_trashed",
        "intrigue_card_drawn",
        "intrigue_card_drawn",
    ]


def test_branching_path_agent_effect_requires_bene_gesserit_alliance() -> None:
    branching_path = _imperium_instance("branching_path")
    owner = PlayerState(player_id=0, hand=(branching_path, _instance("dagger")))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:reward",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    assert legal_agent_card_trash_actions(placed, 0) == ()
    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_branching_path_cannot_trash_without_intrigue_reward() -> None:
    branching_path = _imperium_instance("branching_path")
    owner = PlayerState(
        player_id=0,
        alliance_faction_ids=(Faction.BENE_GESSERIT.value,),
        hand=(branching_path, _instance("dagger")),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    assert legal_agent_card_trash_actions(placed, 0) == (
        DomainAction(action_id="decline_agent_card_trash", actor=0),
    )


def test_cargo_runner_draws_up_to_two_cards_for_completed_contracts() -> None:
    cargo_runner = _imperium_instance("cargo_runner", choam_module=True)
    draws = (
        _imperium_instance("truthtrance"),
        _imperium_instance("sardaukar_soldier"),
    )
    owner = PlayerState(
        player_id=0,
        hand=(cargo_runner,),
        deck=draws,
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
            "contract:espionage_i",
            "contract:espionage_ii",
        ),
    )
    state = GameState(
        config=RulesetConfig(choam_module=True),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    result = resolve_agent_card_effect(placed)

    assert len(result.state.players[0].hand) == 2
    assert result.state.players[0].deck == ()
    assert result.events[-1].kind == "agent_card_effect_resolved"


def test_cargo_runner_counts_a_contract_completed_earlier_in_the_turn() -> None:
    cargo_runner = _imperium_instance("cargo_runner", choam_module=True)
    drawn = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(cargo_runner,),
        deck=(drawn,),
        active_contract_ids=("contract:arrakeen_i",),
        completed_contract_ids=("contract:deliver_supplies",),
    )
    state = GameState(
        config=RulesetConfig(choam_module=True),
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
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    completion = legal_contract_completion_actions(placed, 0)[0]
    completed = apply_contract_completion(placed, completion).state

    result = resolve_agent_card_effect(completed)

    assert result.state.players[0].completed_contract_ids == (
        "contract:deliver_supplies",
        "contract:arrakeen_i",
    )
    assert result.state.players[0].hand == (drawn,)


def test_delivery_agreement_discards_a_card_to_take_a_contract() -> None:
    delivery = _imperium_instance("delivery_agreement", choam_module=True)
    dagger = _instance("dagger")
    owner = PlayerState(player_id=0, hand=(delivery, dagger))
    state = GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        contract_bank=("contract:arrakeen_ii",),
        face_up_contract_ids=("contract:arrakeen_i",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    discard = next(
        action
        for action in legal_agent_card_discard_actions(placed, 0)
        if dict(action.arguments).get("card_id") == dagger
    )

    discarded = apply_agent_card_discard(placed, discard).state
    contract = legal_contract_actions(discarded, 0)[0]
    result = apply_contract_action(discarded, contract)

    assert result.state.players[0].discard_pile == (dagger,)
    assert result.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert result.state.face_up_contract_ids == ("contract:arrakeen_ii",)


def test_interstellar_trade_agent_effect_gains_chosen_influence() -> None:
    interstellar = _imperium_instance("interstellar_trade", choam_module=True)
    owner = PlayerState(player_id=0, hand=(interstellar,))
    state = GameState(
        config=RulesetConfig(choam_module=True),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    action = next(
        action
        for action in legal_agent_card_influence_actions(placed, 0)
        if dict(action.arguments).get("faction") == Faction.FREMEN.value
    )

    result = apply_agent_card_influence(placed, action)

    assert result.state.players[0].influence.fremen == 1


def test_priority_contracts_takes_a_contract_or_converts_an_empty_market() -> None:
    priority = _imperium_instance("priority_contracts", choam_module=True)
    owner = PlayerState(player_id=0, hand=(priority,))
    state = GameState(
        config=RulesetConfig(choam_module=True),
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
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.solari == 2
    assert result.events[-1].kind == "contract_icons_converted_to_solari"


def test_agent_card_spy_placement_needs_a_spy_in_supply_at_that_moment() -> None:
    # Placing a Spy without one in supply first recalls a placed Spy
    # [Main pp. 11, 20]. If the Espionage board effect consumes that recalled
    # Spy before the card effect resolves, the card must offer another recall
    # rather than an impossible placement.
    operative = _imperium_instance("bene_gesserit_operative")
    owner = PlayerState(
        player_id=0,
        hand=(operative,),
        resources=Resources(spice=1),
        spies_supply=0,
        spy_post_ids=(
            "landsraad-assembly-hall-gather-support",
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
        ),
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
    engine = UprisingRulesEngine()
    placed = engine.apply(state, _action_to(state, "espionage")).state

    recalled = engine.apply(
        placed,
        DomainAction(
            action_id="recall_spy_for_agent_card",
            actor=0,
            arguments=(("post_id", "landsraad-assembly-hall-gather-support"),),
        ),
    ).state
    assert recalled.players[0].spies_supply == 1

    spied = engine.apply(
        recalled,
        DomainAction(
            action_id="resolve_espionage_place_spy",
            actor=0,
            arguments=(("post_id", "landsraad-assembly-hall-gather-support"),),
        ),
    ).state
    assert spied.players[0].spies_supply == 0

    offered = {a.action_id for a in engine.legal_actions(spied, 0)}
    assert "place_agent_card_spy" not in offered
    assert "recall_spy_for_agent_card" in offered

