"""Tests for Reserve acquisition during Reveal turns."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.schema import CardDefinition
from dune_imperium.content.uprising.contracts import (
    CONTRACT_SOURCES,
    CONTRACTS_BY_ID,
    ContractCondition,
    ContractConditionKind,
    ContractDefinition,
    ContractReward,
)
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
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
    apply_acquisition_spy_action,
    apply_agent_card_acquisition,
    apply_imperium_acquisition,
    apply_manipulated_acquisition,
    apply_reserve_acquisition,
    legal_acquisition_spy_actions,
    legal_agent_card_acquisitions,
    legal_imperium_acquisitions,
    legal_manipulated_acquisitions,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.combat_deployment import (
    grant_combat_icon,
    legal_combat_deployments,
)
from dune_imperium.rules.contracts import apply_contract_action, legal_contract_actions
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_turn import (
    begin_reveal_turn,
    legal_reveal_actions,
    legal_reveal_deployments,
)


def _instance(card_id: str, copy: int = 0) -> str:
    return tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )[copy]


def _imperium_instance(card_id: str, *, choam_module: bool = False) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(choam_module)
        if f":{card_id}:" in instance_id
    )


def _reveal_state(*cards: str, choam_module: bool = False) -> GameState:
    state = GameState(
        config=RulesetConfig(choam_module=choam_module),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=cards),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        reserve_stacks=(
            ("prepare_the_way", 8),
            ("the_spice_must_flow", 10),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    return begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state


def _choam_interstellar_reveal_state(
    *,
    face_up_contract_ids: tuple[str, ...] = (
        "contract:arrakeen_i",
        "contract:high_council_ii",
    ),
    contract_bank: tuple[str, ...] = ("contract:research_station_i",),
) -> GameState:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("dune_the_desert_planet", 0),
        _instance("dune_the_desert_planet", 1),
        _instance("diplomacy"),
        choam_module=True,
    )
    instances = imperium_deck_instance_ids(True)
    interstellar = _imperium_instance(
        "interstellar_trade",
        choam_module=True,
    )
    others = tuple(instance for instance in instances if instance != interstellar)
    return replace(
        state,
        imperium_row=(interstellar, *others[:4]),
        imperium_deck=others[4:],
        contract_bank=contract_bank,
        face_up_contract_ids=face_up_contract_ids,
    )


def test_only_affordable_nonempty_reserve_stacks_are_legal() -> None:
    state = _reveal_state(_instance("convincing_argument"))

    actions = legal_reserve_acquisitions(state, 0)

    assert tuple(dict(action.arguments)["card_id"] for action in actions) == (
        "prepare_the_way",
    )
    assert legal_reserve_acquisitions(state, 1) == ()


def test_acquisition_spends_persuasion_decrements_stack_and_discards_card() -> None:
    state = _reveal_state(_instance("convincing_argument"))
    action = legal_reserve_acquisitions(state, 0)[0]

    result = apply_reserve_acquisition(state, action)
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 0
    assert dict(result.state.reserve_stacks)["prepare_the_way"] == 7
    assert result.state.players[0].discard_pile == (
        "reserve:prepare_the_way:7",
    )


def test_spice_must_flow_awards_its_acquisition_vp() -> None:
    arguments = tuple(_instance("convincing_argument", copy) for copy in range(2))
    dunes = tuple(_instance("dune_the_desert_planet", copy) for copy in range(2))
    cards = (
        *arguments,
        *dunes,
        _instance("diplomacy"),
        _instance("reconnaissance"),
        _instance("signet_ring"),
    )
    state = _reveal_state(*cards)
    action = next(
        action
        for action in legal_reserve_acquisitions(state, 0)
        if dict(action.arguments)["card_id"] == "the_spice_must_flow"
    )

    result = apply_reserve_acquisition(state, action)

    assert result.state.players[0].victory_points == 2
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0


def test_imperium_purchase_refills_same_row_position_immediately() -> None:
    state = _reveal_state(_instance("convincing_argument"))
    instances = imperium_deck_instance_ids(False)
    cheap = next(card for card in instances if ":sardaukar_soldier:" in card)
    expensive = next(card for card in instances if ":bene_gesserit_operative:" in card)
    others = tuple(card for card in instances if card not in {cheap, expensive})
    row = (expensive, cheap, *others[:3])
    replacement = others[3]
    state = replace(
        state,
        imperium_row=row,
        imperium_deck=(replacement, *others[4:]),
    )

    actions = legal_imperium_acquisitions(state, 0)
    assert tuple(dict(action.arguments)["instance_id"] for action in actions) == (
        cheap,
    )
    result = apply_imperium_acquisition(state, actions[0])

    assert result.state.players[0].discard_pile == (cheap,)
    assert result.state.imperium_row == (expensive, replacement, *others[:3])
    assert result.state.imperium_deck == others[4:]
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_imperium_purchase_with_an_empty_deck_shrinks_the_row() -> None:
    # OQ-004 convention: with the Imperium Deck exhausted there is nothing to
    # refill from [Main p. 13], so the Row keeps operating with fewer cards.
    state = _reveal_state(_instance("convincing_argument"))
    instances = imperium_deck_instance_ids(False)
    cheap = next(card for card in instances if ":sardaukar_soldier:" in card)
    others = tuple(card for card in instances if card != cheap)
    state = replace(
        state,
        imperium_row=(cheap, *others[:4]),
        imperium_deck=(),
    )

    actions = legal_imperium_acquisitions(state, 0)
    assert tuple(dict(action.arguments)["instance_id"] for action in actions) == (
        cheap,
    )
    result = apply_imperium_acquisition(state, actions[0])

    assert result.state.players[0].discard_pile == (cheap,)
    assert result.state.imperium_row == others[:4]
    assert result.state.imperium_deck == ()


def test_interstellar_trade_acquisition_opens_contract_market_and_refills_it() -> None:
    state = _choam_interstellar_reveal_state()
    interstellar = _imperium_instance(
        "interstellar_trade",
        choam_module=True,
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == interstellar
    )

    acquired = apply_imperium_acquisition(state, action)

    assert acquired.state.players[0].discard_pile == (interstellar,)
    assert acquired.state.players[0].resources.solari == 0
    assert dict(acquired.state.decision_stack[-2].context)["persuasion"] == 0
    contract_actions = legal_contract_actions(acquired.state, 0)
    assert tuple(
        dict(contract_action.arguments)["instance_id"]
        for contract_action in contract_actions
    ) == ("contract:arrakeen_i", "contract:high_council_ii")

    taken = apply_contract_action(acquired.state, contract_actions[0])

    assert taken.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert taken.state.face_up_contract_ids == (
        "contract:research_station_i",
        "contract:high_council_ii",
    )
    assert taken.state.contract_bank == ()


def test_interstellar_trade_acquisition_converts_exhausted_contract_icon_to_solari(
) -> None:
    state = _choam_interstellar_reveal_state(
        face_up_contract_ids=(),
        contract_bank=(),
    )
    interstellar = _imperium_instance(
        "interstellar_trade",
        choam_module=True,
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == interstellar
    )

    result = apply_imperium_acquisition(state, action)

    assert result.state.players[0].discard_pile == (interstellar,)
    assert result.state.players[0].resources.solari == 2
    assert [event.kind for event in result.events] == [
        "card_acquired",
        "contract_icons_converted_to_solari",
    ]


def test_acquired_transcribed_card_can_be_revealed_later() -> None:
    cards = (
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
    )
    state = _reveal_state(*cards)
    instances = imperium_deck_instance_ids(False)
    maula = next(card for card in instances if ":maula_pistol:" in card)
    others = tuple(card for card in instances if card != maula)
    state = replace(
        state,
        imperium_row=(maula, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == maula
    )
    acquired = apply_imperium_acquisition(state, action).state
    owner = replace(
        acquired.players[0],
        hand=(maula,),
        discard_pile=acquired.players[0].in_play,
        in_play=(),
    )
    later = replace(
        acquired,
        players=(owner, *acquired.players[1:]),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:2:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    revealed = begin_reveal_turn(later, legal_reveal_actions(later, 0)[0]).state

    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 1


def test_price_is_no_object_acquisition_gains_two_solari() -> None:
    cards = (
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("dune_the_desert_planet", 0),
        _instance("dune_the_desert_planet", 1),
    )
    state = _reveal_state(*cards)
    instances = imperium_deck_instance_ids(False)
    price = next(card for card in instances if ":price_is_no_object:" in card)
    others = tuple(card for card in instances if card != price)
    state = replace(
        state,
        imperium_row=(price, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == price
    )

    result = apply_imperium_acquisition(state, action)

    assert result.state.players[0].discard_pile == (price,)
    assert result.state.players[0].resources.solari == 2
    assert tuple(event.kind for event in result.events) == (
        "card_acquired",
        "acquisition_resource_gained",
    )


def _price_agent_state(
    *,
    solari: int,
    imperium_row: tuple[str, ...] = (),
    imperium_deck: tuple[str, ...] = (),
    intrigue_deck: tuple[str, ...] = (),
    choam_module: bool = False,
) -> GameState:
    price = _imperium_instance("price_is_no_object", choam_module=choam_module)
    state = GameState(
        config=RulesetConfig(choam_module=choam_module),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(
                player_id=0,
                hand=(price,),
                resources=Resources(solari=solari),
            ),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        reserve_stacks=(
            ("prepare_the_way", 8),
            ("the_spice_must_flow", 10),
        ),
        imperium_row=imperium_row,
        imperium_deck=imperium_deck,
        intrigue_deck=intrigue_deck,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    agent = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "dutiful_service"
    )
    return apply_agent_action(state, agent).state


def test_price_is_no_object_acquires_row_card_to_hand_with_solari() -> None:
    instances = imperium_deck_instance_ids(False)
    sardaukar = _imperium_instance("sardaukar_soldier")
    others = tuple(
        instance_id
        for instance_id in instances
        if instance_id not in {sardaukar, _imperium_instance("price_is_no_object")}
    )
    state = _price_agent_state(
        solari=1,
        imperium_row=(sardaukar, *others[:4]),
        imperium_deck=others[4:],
    )
    engine = UprisingRulesEngine()
    action = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == sardaukar
    )

    result = engine.apply(state, action)

    assert result.state.players[0].hand == (sardaukar,)
    # Taken face up from the Row straight to hand, so the identity stays
    # public while it sits there (OQ-010).
    assert result.state.players[0].hand_public == (sardaukar,)
    assert result.state.players[0].discard_pile == ()
    assert result.state.players[0].resources.solari == 0
    assert result.state.imperium_row[0] == others[4]
    assert legal_agent_card_acquisitions(result.state, 0) == ()


def test_price_is_no_object_spy_acquisition_ends_the_agent_turn() -> None:
    # After the Solari acquisition resolves an acquire-box Spy placement, the
    # effect frame has nothing pending and the Agent turn advances instead of
    # stalling without a legal action.
    instances = imperium_deck_instance_ids(False)
    strike_fleet = _imperium_instance("strike_fleet")
    others = tuple(
        instance_id
        for instance_id in instances
        if instance_id
        not in {strike_fleet, _imperium_instance("price_is_no_object")}
    )
    state = _price_agent_state(
        solari=9,
        imperium_row=(strike_fleet, *others[:4]),
        imperium_deck=others[4:],
    )
    engine = UprisingRulesEngine()
    for action_id in ("resolve_board_effect", "resolve_faction_influence"):
        action = next(
            candidate
            for candidate in engine.legal_actions(state, 0)
            if candidate.action_id == action_id
        )
        state = engine.apply(state, action).state
    acquire = next(
        candidate
        for candidate in engine.legal_actions(state, 0)
        if dict(candidate.arguments).get("instance_id") == strike_fleet
    )
    state = engine.apply(state, acquire).state
    placement = next(
        candidate
        for candidate in engine.legal_actions(state, 0)
        if candidate.action_id == "place_acquisition_spy"
    )
    ended = engine.apply(state, placement).state

    assert ended.players[0].hand == (strike_fleet,)
    assert len(ended.players[0].spy_post_ids) == 1
    assert ended.decision_stack[-1].kind == "turn"
    assert isinstance(ended.decision_stack[-1].decision, PlayerDecision)
    assert ended.decision_stack[-1].decision.owner == 1
    assert engine.legal_actions(ended, 1)


def test_price_is_no_object_can_take_interstellar_trade_and_open_contract_market(
) -> None:
    instances = imperium_deck_instance_ids(True)
    interstellar = _imperium_instance(
        "interstellar_trade",
        choam_module=True,
    )
    price = _imperium_instance("price_is_no_object", choam_module=True)
    others = tuple(
        instance_id
        for instance_id in instances
        if instance_id not in {interstellar, price}
    )
    state = _price_agent_state(
        solari=7,
        choam_module=True,
        imperium_row=(interstellar, *others[:4]),
        imperium_deck=others[4:],
    )
    state = replace(
        state,
        contract_bank=("contract:research_station_i",),
        face_up_contract_ids=(
            "contract:arrakeen_i",
            "contract:high_council_ii",
        ),
    )
    engine = UprisingRulesEngine()
    action = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == interstellar
    )

    acquired = engine.apply(state, action)

    assert acquired.state.players[0].hand == (interstellar,)
    assert acquired.state.players[0].in_play == (price,)
    assert acquired.state.players[0].resources.solari == 0
    contract_action = legal_contract_actions(acquired.state, 0)[0]
    taken = apply_contract_action(acquired.state, contract_action)

    assert taken.state.players[0].active_contract_ids == (
        "contract:arrakeen_i",
    )
    assert taken.state.face_up_contract_ids == (
        "contract:research_station_i",
        "contract:high_council_ii",
    )


def test_price_is_no_object_acquires_reserve_card_to_hand_with_solari() -> None:
    state = _price_agent_state(solari=9)
    action = next(
        action
        for action in legal_agent_card_acquisitions(state, 0)
        if dict(action.arguments).get("card_id") == "the_spice_must_flow"
    )

    result = apply_agent_card_acquisition(state, action)

    assert result.state.players[0].hand == ("reserve:the_spice_must_flow:9",)
    assert result.state.players[0].resources.solari == 0
    assert result.state.players[0].victory_points == 2
    assert dict(result.state.reserve_stacks)["the_spice_must_flow"] == 9


def test_price_is_no_object_resolves_the_acquired_cards_bonus() -> None:
    instances = imperium_deck_instance_ids(False)
    overthrow = _imperium_instance("overthrow")
    price = _imperium_instance("price_is_no_object")
    others = tuple(
        instance_id
        for instance_id in instances
        if instance_id not in {overthrow, price}
    )
    state = _price_agent_state(
        solari=8,
        imperium_row=(overthrow, *others[:4]),
        imperium_deck=others[4:],
        intrigue_deck=("intrigue:test:0",),
    )
    action = next(
        action
        for action in legal_agent_card_acquisitions(state, 0)
        if dict(action.arguments).get("instance_id") == overthrow
    )

    result = apply_agent_card_acquisition(state, action)

    assert result.state.players[0].hand == (overthrow,)
    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert tuple(event.kind for event in result.events) == (
        "card_acquired",
        "intrigue_card_drawn",
    )


def test_price_is_no_object_preserves_acquisition_spy_follow_up() -> None:
    instances = imperium_deck_instance_ids(False)
    strike_fleet = _imperium_instance("strike_fleet")
    price = _imperium_instance("price_is_no_object")
    others = tuple(
        instance_id
        for instance_id in instances
        if instance_id not in {strike_fleet, price}
    )
    state = _price_agent_state(
        solari=5,
        imperium_row=(strike_fleet, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_agent_card_acquisitions(state, 0)
        if dict(action.arguments).get("instance_id") == strike_fleet
    )

    acquired = apply_agent_card_acquisition(state, action).state
    placement = legal_acquisition_spy_actions(acquired, 0)[0]
    result = apply_acquisition_spy_action(acquired, placement)

    assert acquired.players[0].hand == (strike_fleet,)
    assert result.state.players[0].spies_supply == 2
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False


def test_subversive_advisor_normal_acquisition_opens_spy_placement() -> None:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("diplomacy"),
    )
    instances = imperium_deck_instance_ids(False)
    subversive = _imperium_instance("subversive_advisor")
    others = tuple(instance for instance in instances if instance != subversive)
    state = replace(
        state,
        imperium_row=(subversive, *others[:4]),
        imperium_deck=others[4:],
    )
    engine = UprisingRulesEngine()
    acquire = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == subversive
    )

    acquired = engine.apply(state, acquire)
    placement = legal_acquisition_spy_actions(acquired.state, 0)[0]
    result = apply_acquisition_spy_action(acquired.state, placement)

    assert acquired.state.players[0].discard_pile == (subversive,)
    assert {
        action.action_id
        for action in legal_acquisition_spy_actions(acquired.state, 0)
    } == {"place_acquisition_spy"}
    assert result.state.players[0].spies_supply == 2
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0


def test_price_can_acquire_subversive_advisor_to_hand_and_place_spy() -> None:
    instances = imperium_deck_instance_ids(False)
    subversive = _imperium_instance("subversive_advisor")
    price = _imperium_instance("price_is_no_object")
    others = tuple(
        instance_id
        for instance_id in instances
        if instance_id not in {subversive, price}
    )
    state = _price_agent_state(
        solari=5,
        imperium_row=(subversive, *others[:4]),
        imperium_deck=others[4:],
    )
    engine = UprisingRulesEngine()
    acquire = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == subversive
    )

    acquired = engine.apply(state, acquire)
    placement = legal_acquisition_spy_actions(acquired.state, 0)[0]
    result = apply_acquisition_spy_action(acquired.state, placement)

    assert acquired.state.players[0].hand == (subversive,)
    assert acquired.state.players[0].resources.solari == 0
    assert result.state.players[0].spies_supply == 2
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False


def test_price_is_no_object_may_decline_its_acquisition() -> None:
    state = _price_agent_state(solari=3)
    decline = DomainAction(action_id="decline_agent_card_acquisition", actor=0)

    result = apply_agent_card_acquisition(state, decline)

    assert result.state.players[0].resources.solari == 3
    assert result.state.players[0].hand == ()
    assert result.events[0].kind == "agent_card_acquisition_declined"


def test_price_is_no_object_skips_acquisition_without_solari() -> None:
    state = _price_agent_state(solari=0)

    # The Solari are judged when the box resolves (OQ-028): a freely ordered
    # board effect could still pay for a card, so the box stays pending and
    # only declining is offered until then.
    assert dict(state.decision_stack[-1].context)["pending_agent_effect"] is True
    assert legal_agent_card_acquisitions(state, 0) == (
        DomainAction(action_id="decline_agent_card_acquisition", actor=0),
    )


def test_overthrow_acquisition_draws_an_intrigue_card() -> None:
    arguments = tuple(_instance("convincing_argument", copy) for copy in range(2))
    dunes = tuple(_instance("dune_the_desert_planet", copy) for copy in range(2))
    state = _reveal_state(
        *arguments,
        *dunes,
        _instance("diplomacy"),
        _instance("reconnaissance"),
    )
    instances = imperium_deck_instance_ids(False)
    overthrow = next(card for card in instances if ":overthrow:" in card)
    others = tuple(card for card in instances if card != overthrow)
    state = replace(
        state,
        imperium_row=(overthrow, *others[:4]),
        imperium_deck=others[4:],
        intrigue_deck=("intrigue:test:0",),
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == overthrow
    )
    assert action in UprisingRulesEngine().legal_actions(state, 0)

    result = apply_imperium_acquisition(state, action)

    assert result.state.players[0].discard_pile == (overthrow,)
    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert tuple(event.kind for event in result.events) == (
        "card_acquired",
        "intrigue_card_drawn",
    )


def test_steersman_acquisition_gains_spacing_guild_influence() -> None:
    arguments = tuple(_instance("convincing_argument", copy) for copy in range(2))
    dunes = tuple(_instance("dune_the_desert_planet", copy) for copy in range(2))
    state = _reveal_state(
        *arguments,
        *dunes,
        _instance("diplomacy"),
        _instance("reconnaissance"),
    )
    instances = imperium_deck_instance_ids(False)
    steersman = _imperium_instance("steersman")
    others = tuple(card for card in instances if card != steersman)
    state = replace(
        state,
        imperium_row=(steersman, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == steersman
    )

    result = apply_imperium_acquisition(state, action)

    assert result.state.players[0].discard_pile == (steersman,)
    assert result.state.players[0].influence.spacing_guild == 1
    assert [event.kind for event in result.events] == [
        "card_acquired",
        "influence_gained",
    ]


def test_price_is_no_object_preserves_steersman_acquisition_influence() -> None:
    instances = imperium_deck_instance_ids(False)
    steersman = _imperium_instance("steersman")
    price = _imperium_instance("price_is_no_object")
    others = tuple(
        instance_id
        for instance_id in instances
        if instance_id not in {steersman, price}
    )
    state = _price_agent_state(
        solari=8,
        imperium_row=(steersman, *others[:4]),
        imperium_deck=others[4:],
    )
    action = next(
        action
        for action in legal_agent_card_acquisitions(state, 0)
        if dict(action.arguments).get("instance_id") == steersman
    )

    result = apply_agent_card_acquisition(state, action)

    assert result.state.players[0].hand == (steersman,)
    assert result.state.players[0].influence.spacing_guild == 1
    assert [event.kind for event in result.events] == [
        "card_acquired",
        "influence_gained",
    ]


def test_strike_fleet_acquisition_opens_and_resolves_spy_placement() -> None:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("diplomacy"),
    )
    instances = imperium_deck_instance_ids(False)
    strike_fleet = next(card for card in instances if ":strike_fleet:" in card)
    others = tuple(card for card in instances if card != strike_fleet)
    state = replace(
        state,
        imperium_row=(strike_fleet, *others[:4]),
        imperium_deck=others[4:],
    )
    engine = UprisingRulesEngine()
    acquire = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == strike_fleet
    )

    acquired = engine.apply(state, acquire)
    choices = legal_acquisition_spy_actions(acquired.state, 0)
    placed = apply_acquisition_spy_action(acquired.state, choices[0])
    post_id = dict(choices[0].arguments)["post_id"]

    assert acquired.state.players[0].discard_pile == (strike_fleet,)
    assert {action.action_id for action in choices} == {"place_acquisition_spy"}
    assert placed.state.players[0].spies_supply == 2
    assert placed.state.players[0].spy_post_ids == (post_id,)
    assert dict(placed.state.decision_stack[-1].context)["persuasion"] == 0


def test_guild_spy_acquisition_opens_spy_placement() -> None:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("diplomacy"),
    )
    instances = imperium_deck_instance_ids(False)
    guild_spy = next(card for card in instances if ":guild_spy:" in card)
    others = tuple(card for card in instances if card != guild_spy)
    state = replace(
        state,
        imperium_row=(guild_spy, *others[:4]),
        imperium_deck=others[4:],
    )
    acquire = next(
        action
        for action in UprisingRulesEngine().legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == guild_spy
    )

    acquired = UprisingRulesEngine().apply(state, acquire)

    assert acquired.state.players[0].discard_pile == (guild_spy,)
    assert {
        action.action_id
        for action in legal_acquisition_spy_actions(acquired.state, 0)
    } == {"place_acquisition_spy"}


def test_guild_spy_gains_influence_for_spied_factions_on_spice_must_flow() -> None:
    guild_spy = next(
        card for card in imperium_deck_instance_ids(False) if ":guild_spy:" in card
    )
    state = _reveal_state(
        guild_spy,
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("dune_the_desert_planet", 0),
        _instance("dune_the_desert_planet", 1),
        _instance("diplomacy"),
    )
    owner = replace(
        state.players[0],
        spies_supply=1,
        spy_post_ids=(
            "emperor-sardaukar-dutiful-service",
            "spacing-guild-heighliner-deliver-supplies",
        ),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    action = next(
        action
        for action in legal_reserve_acquisitions(state, 0)
        if dict(action.arguments)["card_id"] == "the_spice_must_flow"
    )

    result = apply_reserve_acquisition(state, action)
    influence = result.state.players[0].influence

    assert influence.emperor == 1
    assert influence.spacing_guild == 1
    assert influence.bene_gesserit == 0
    assert influence.fremen == 0
    assert [event.kind for event in result.events] == [
        "card_acquired",
        "influence_gained",
        "influence_gained",
    ]



def test_guild_spy_bumps_once_per_reveal_and_a_late_guild_spy_still_reacts() -> None:
    # Designer ruling (In person, OQ-057): buying The Spice Must Flow twice
    # bumps once per Guild Spy, and a Guild Spy revealed later in the Reveal
    # still reacts to the earlier purchase.
    from dune_imperium.rules.reveal_turn import reveal_late_arrivals

    guild_spy = next(
        card for card in imperium_deck_instance_ids(False) if ":guild_spy:" in card
    )
    posts = (
        "emperor-sardaukar-dutiful-service",
        "spacing-guild-heighliner-deliver-supplies",
    )

    def rich_reveal(*cards: str) -> GameState:
        state = _reveal_state(*cards)
        owner = replace(state.players[0], spies_supply=1, spy_post_ids=posts)
        frame = state.decision_stack[-1]
        context = dict(frame.context)
        context["persuasion"] = 20
        return replace(
            state,
            players=(owner, *state.players[1:]),
            decision_stack=(
                *state.decision_stack[:-1],
                replace(frame, context=tuple(sorted(context.items()))),
            ),
        )

    def buy(current: GameState) -> GameState:
        action = next(
            action
            for action in legal_reserve_acquisitions(current, 0)
            if dict(action.arguments)["card_id"] == "the_spice_must_flow"
        )
        return apply_reserve_acquisition(current, action).state

    once = buy(rich_reveal(guild_spy, _instance("diplomacy")))
    assert once.players[0].influence.emperor == 1
    assert once.players[0].influence.spacing_guild == 1
    twice = buy(once)
    assert twice.players[0].influence.emperor == 1
    assert twice.players[0].influence.spacing_guild == 1
    context = dict(twice.decision_stack[-1].context)
    assert context["spice_must_flow_acquired"] is True
    assert context["guild_spy_fired"] == guild_spy

    # Guild Spy drawn after the purchase is revealed at once [FAQ p. 3] and
    # reacts to the purchase already made this Reveal.
    bought_first = buy(rich_reveal(_instance("diplomacy")))
    assert bought_first.players[0].influence.emperor == 0
    holding = replace(bought_first.players[0], hand=(guild_spy,))
    arrived = reveal_late_arrivals(
        replace(bought_first, players=(holding, *bought_first.players[1:])),
        0,
        (guild_spy,),
    ).state
    assert arrived.players[0].influence.emperor == 1
    assert arrived.players[0].influence.spacing_guild == 1
    assert dict(arrived.decision_stack[-1].context)["guild_spy_fired"] == guild_spy
    # A further purchase does not bump the same copy again.
    again = buy(arrived)
    assert again.players[0].influence.emperor == 1

def _strike_fleet_bought_with_an_empty_supply() -> tuple[GameState, tuple[str, ...]]:
    state = _reveal_state(
        _instance("convincing_argument", 0),
        _instance("convincing_argument", 1),
        _instance("diplomacy"),
    )
    instances = imperium_deck_instance_ids(False)
    strike_fleet = next(card for card in instances if ":strike_fleet:" in card)
    others = tuple(card for card in instances if card != strike_fleet)
    posts = (
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
        "bene-gesserit-espionage-secrets",
    )
    owner = replace(state.players[0], spies_supply=0, spy_post_ids=posts)
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        imperium_row=(strike_fleet, *others[:4]),
        imperium_deck=others[4:],
    )
    acquire = next(
        action
        for action in UprisingRulesEngine().legal_actions(state, 0)
        if dict(action.arguments).get("instance_id") == strike_fleet
    )

    return apply_imperium_acquisition(state, acquire).state, posts


def test_strike_fleet_acquisition_recalls_before_placing_with_empty_supply() -> None:
    acquired, posts = _strike_fleet_bought_with_an_empty_supply()
    recall = next(
        action
        for action in legal_acquisition_spy_actions(acquired, 0)
        if action.action_id == "recall_spy_for_acquisition"
    )
    recalled = apply_acquisition_spy_action(acquired, recall)
    placement = next(
        action
        for action in legal_acquisition_spy_actions(recalled.state, 0)
        if dict(action.arguments)["post_id"] == dict(recall.arguments)["post_id"]
    )
    replaced = apply_acquisition_spy_action(recalled.state, placement)

    assert recalled.events[0].kind == "spy_recalled"
    assert replaced.state.players[0].spies_supply == 0
    assert set(replaced.state.players[0].spy_post_ids) == set(posts)
    assert dict(replaced.state.decision_stack[-1].context)["persuasion"] == 0
    # Once recalled, the Spy is in supply and must be placed (OQ-057 (14)).
    assert {
        action.action_id
        for action in legal_acquisition_spy_actions(recalled.state, 0)
    } == {"place_acquisition_spy"}


def test_strike_fleet_acquisition_spy_may_pass_up_the_recall_with_an_empty_supply() -> (
    None
):
    # "If you have no Spies in your supply when you need to place one, you
    # may first recall one of your Spies for no effect." [Main p. 11] (again
    # [Main p. 20]); docs/rules/uprising-systems.md: with an empty supply the
    # recall stays optional, so the owner may pass without placing (OQ-057
    # (14)). The acquisition Spy used to offer only the recalls.
    acquired, posts = _strike_fleet_bought_with_an_empty_supply()
    choices = legal_acquisition_spy_actions(acquired, 0)
    assert choices[0] == DomainAction(action_id="decline_acquisition_spy", actor=0)
    assert {action.action_id for action in choices[1:]} == {
        "recall_spy_for_acquisition"
    }

    passed = apply_acquisition_spy_action(acquired, choices[0])

    owner = passed.state.players[0]
    assert owner.spy_post_ids == posts
    assert owner.spies_supply == 0
    assert owner.spies_recalled_turn == 0
    assert passed.events[0].kind == "spy_placement_unavailable"
    assert passed.state.decision_stack[-1].kind == FrameKind.REVEAL
    assert dict(passed.state.decision_stack[-1].context)["persuasion"] == 0


def test_reserve_acquisition_never_reissues_an_owned_copy_id() -> None:
    from dune_imperium.rules.acquisition import next_reserve_instance_id

    # Player 0 owns copy 7 while a returned copy sits on the stack (count 1).
    owner = PlayerState(player_id=0, discard_pile=("reserve:prepare_the_way:7",))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        reserve_stacks=(("prepare_the_way", 1), ("the_spice_must_flow", 10)),
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )

    assert next_reserve_instance_id(state, "prepare_the_way") == (
        "reserve:prepare_the_way:6"
    )
    assert next_reserve_instance_id(state, "the_spice_must_flow") == (
        "reserve:the_spice_must_flow:9"
    )


def _combat_reveal_state(imperium_row: tuple[str, ...]) -> GameState:
    """A Reveal turn with a Combat icon already granted and ample Persuasion.

    ``combat_deployment`` mirrors what a Combat-icon-granting reveal effect
    (or the space visited before a Reveal, [Bloodlines p. 5]) would already
    have set; the acquisition itself is what this test exercises.
    """

    state = _reveal_state(_instance("convincing_argument"))
    owner = replace(state.players[0], troops_garrison=3)
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = 10
    context["combat_deployment"] = True
    return replace(
        state,
        players=(owner, *state.players[1:]),
        imperium_row=imperium_row,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def test_arrakis_revolt_in_a_combat_reveal_recruits_a_countable_troop() -> None:
    # Arrakis Revolt's acquire box recruits one troop [Arrakis Revolt card,
    # promo]. "Combat 아이콘...이번 turn에 recruit한 유닛 전부와 garrison
    # 에서 최대 두 개" [Bloodlines pp. 5, 12] does not carve out an
    # exception for a recruit from an acquire box, and "그 turn에 어떤
    # 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수 있다"
    # [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md). The engine used
    # to move the troop to the garrison without joining
    # ``reveal_troops_recruited``, so the Combat-icon deployment stayed
    # capped at the flat two from the garrison. Arrakis Revolt sits in the
    # Row here regardless of ``promo_cards``, a setup-only flag
    # (``AGENTS.md``): the acquisition path itself never gates on it.
    arrakis_revolt = "imperium:arrakis_revolt:0"
    state = _combat_reveal_state((arrakis_revolt,))

    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == arrakis_revolt
    )
    result = apply_imperium_acquisition(state, action)

    assert result.state.players[0].troops_garrison == 4
    context = dict(result.state.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 1
    assert [
        dict(a.arguments)["count"]
        for a in legal_reveal_deployments(result.state, 0)
        if a.action_id == "deploy_troops"
    ] == [1, 2, 3]


def test_occupation_in_a_combat_reveal_recruits_countable_troops() -> None:
    # Occupation's acquire box recruits three troops [Occupation card,
    # Immortality]; same citations as Arrakis Revolt above.
    occupation = "imperium:occupation:0"
    state = _combat_reveal_state((occupation,))

    action = next(
        action
        for action in legal_imperium_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == occupation
    )
    result = apply_imperium_acquisition(state, action)

    assert result.state.players[0].troops_garrison == 6
    context = dict(result.state.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 3
    assert [
        dict(a.arguments)["count"]
        for a in legal_reveal_deployments(result.state, 0)
        if a.action_id == "deploy_troops"
    ] == [1, 2, 3, 4, 5]


def test_manipulated_arrakis_revolt_recruits_a_countable_reveal_troop() -> None:
    # The manipulated (set-aside) acquisition path shares the same acquire
    # box resolution [Main p. 20] [Main p. 10] [FAQ p. 4]
    # (docs/rules/player-turns.md).
    arrakis_revolt = "imperium:arrakis_revolt:0"
    state = _combat_reveal_state(())
    owner = replace(state.players[0], imperium_set_aside=(arrakis_revolt,))
    state = replace(state, players=(owner, *state.players[1:]))

    action = next(
        action
        for action in legal_manipulated_acquisitions(state, 0)
        if dict(action.arguments)["instance_id"] == arrakis_revolt
    )
    result = apply_manipulated_acquisition(state, action)

    assert result.state.players[0].troops_garrison == 4
    context = dict(result.state.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 1


def test_price_is_no_object_acquired_troop_joins_a_combat_icons_allowance() -> None:
    # Price is No Object's Emperor/Bene Gesserit icons never lead to a
    # Combat space, so ``grant_combat_icon`` stands in for whatever other
    # source opened this Agent turn's deploy window (Devastator, a Skill
    # tile): the acquired card's own troop must still join it [Main p. 10]
    # [FAQ p. 4] (docs/rules/player-turns.md).
    arrakis_revolt = "imperium:arrakis_revolt:0"
    state = _price_agent_state(solari=6, imperium_row=(arrakis_revolt,))
    granted = grant_combat_icon(state, 0)

    action = next(
        action
        for action in legal_agent_card_acquisitions(granted, 0)
        if dict(action.arguments).get("instance_id") == arrakis_revolt
    )
    result = apply_agent_card_acquisition(granted, action)

    _, context = current_agent_effect_context(result.state)
    assert context["troops_recruited"] == 1
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(result.state, 0)
    ] == [1, 2, 3]


def _fake_troop_contract(card_id: str, target: str) -> ContractDefinition:
    return ContractDefinition(
        card=CardDefinition(
            card_id=card_id,
            name="Fake Troop Acquire",
            sources=CONTRACT_SOURCES,
        ),
        condition=ContractCondition(ContractConditionKind.ACQUIRE_CARD, target=target),
        reward=ContractReward(troops=1),
    )


def test_acquire_contract_troop_reward_joins_the_solari_imperium_acquisitions_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An Acquire Contract's own troop reward is unused by any current
    # Contract, but shares Arrakis Revolt's and Occupation's shape and must
    # join this Agent turn's recruit count the same way, not just the
    # garrison [Main p. 10] [FAQ p. 4]. ``complete_acquire_contracts``
    # credits the still-current Agent-turn effect frame directly through
    # ``turn_owner_of`` here, and ``_acquire_imperium_to_hand_with_solari``
    # also folds the same garrison diff into its own local ``context`` --
    # but that local copy is only written back through the
    # ``advance_after_effect`` call below, which replaces the frame
    # ``complete_acquire_contracts`` already updated, so exactly one credit
    # survives.
    sardaukar = _imperium_instance("sardaukar_soldier")
    monkeypatch.setitem(
        CONTRACTS_BY_ID,
        "fake_troop_acquire",
        _fake_troop_contract("fake_troop_acquire", "sardaukar_soldier"),
    )
    others = tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(True)
        if instance_id
        not in {sardaukar, _imperium_instance("price_is_no_object", choam_module=True)}
    )
    state = _price_agent_state(
        solari=1,
        choam_module=True,
        imperium_row=(sardaukar, *others[:4]),
        imperium_deck=others[4:],
    )
    owner = replace(
        state.players[0], active_contract_ids=("contract:fake_troop_acquire",)
    )
    state = replace(state, players=(owner, *state.players[1:]))
    garrison = state.players[0].troops_garrison

    action = next(
        action
        for action in legal_agent_card_acquisitions(state, 0)
        if dict(action.arguments).get("instance_id") == sardaukar
    )
    result = apply_agent_card_acquisition(state, action)

    assert result.state.players[0].troops_garrison == garrison + 1
    assert result.state.players[0].completed_contract_ids == (
        "contract:fake_troop_acquire",
    )
    _, context = current_agent_effect_context(result.state)
    assert context["troops_recruited"] == 1


def test_acquire_contract_troop_reward_joins_the_solari_places_spy_acquisitions_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same Contract reward as above, but through the acquisition-bonus
    # branch that pushes a Spy-placement frame instead of calling
    # ``advance_after_effect``: there the credit that survives is
    # ``complete_acquire_contracts``'s own, already written into the
    # Agent-turn effect frame before this handler's local ``context`` copy
    # is (harmlessly) discarded.
    strike_fleet = _imperium_instance("strike_fleet")
    monkeypatch.setitem(
        CONTRACTS_BY_ID,
        "fake_troop_acquire_spy",
        _fake_troop_contract("fake_troop_acquire_spy", "strike_fleet"),
    )
    others = tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(True)
        if instance_id
        not in {
            strike_fleet,
            _imperium_instance("price_is_no_object", choam_module=True),
        }
    )
    state = _price_agent_state(
        solari=5,
        choam_module=True,
        imperium_row=(strike_fleet, *others[:4]),
        imperium_deck=others[4:],
    )
    owner = replace(
        state.players[0], active_contract_ids=("contract:fake_troop_acquire_spy",)
    )
    state = replace(state, players=(owner, *state.players[1:]))
    garrison = state.players[0].troops_garrison

    action = next(
        action
        for action in legal_agent_card_acquisitions(state, 0)
        if dict(action.arguments).get("instance_id") == strike_fleet
    )
    result = apply_agent_card_acquisition(state, action)

    assert result.state.players[0].troops_garrison == garrison + 1
    assert result.state.players[0].completed_contract_ids == (
        "contract:fake_troop_acquire_spy",
    )
    assert result.state.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY
    context = dict(result.state.decision_stack[-2].context)
    assert context["troops_recruited"] == 1


def test_acquire_contract_troop_reward_joins_the_solari_reserve_acquisitions_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same Contract reward through the Reserve-with-Solari handler
    # (``_acquire_reserve_to_hand_with_solari``), which always calls
    # ``advance_after_effect`` and so always keeps its own local credit.
    monkeypatch.setitem(
        CONTRACTS_BY_ID,
        "fake_troop_acquire_reserve",
        _fake_troop_contract("fake_troop_acquire_reserve", "prepare_the_way"),
    )
    state = replace(
        _price_agent_state(solari=2, choam_module=True),
        reserve_stacks=(("prepare_the_way", 8),),
    )
    owner = replace(
        state.players[0],
        active_contract_ids=("contract:fake_troop_acquire_reserve",),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    garrison = state.players[0].troops_garrison

    action = next(
        action
        for action in legal_agent_card_acquisitions(state, 0)
        if action.action_id == "acquire_reserve_with_solari"
    )
    result = apply_agent_card_acquisition(state, action)

    assert result.state.players[0].troops_garrison == garrison + 1
    assert result.state.players[0].completed_contract_ids == (
        "contract:fake_troop_acquire_reserve",
    )
    _, context = current_agent_effect_context(result.state)
    assert context["troops_recruited"] == 1
