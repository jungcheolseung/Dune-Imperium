"""Tests for the Tleilaxu deck cards of slice 5c-1.

Rule source: the card faces transcribed in
``docs/implementation-audits/immortality.md`` (Tleilaxu table); the Graft
rules [Immortality pp. 10-11] and the FAQ's Beguiling Pheromones ruling
[FAQ p. 1] (a trashed partner's un-activated box expires, OQ-022).
"""

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
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
from dune_imperium.rules.agent_effects import (
    apply_agent_card_payment,
    legal_agent_card_payment_actions,
    resolve_agent_card_effect,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft import (
    apply_graft_partner,
    apply_graft_switch,
    legal_graft_partner_actions,
    legal_graft_switch_actions,
)

IMMORTALITY = RulesetConfig(immortality=True, promo_cards=True)
STARTERS = starting_deck_instance_ids(0, immortality=True)
DAGGER = next(card for card in STARTERS if "dagger:0" in card)
FACE_DANCER = "tleilaxu:face_dancer:0"


def _tleilaxu(card_id: str) -> str:
    return f"tleilaxu:{card_id}:0"


def _seat(seat: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": seat,
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _owner(hand: tuple[str, ...], **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "hand": hand,
        "deck": tuple(card for card in STARTERS if card not in hand),
        "resources": Resources(solari=4, spice=2, water=2),
    }
    values.update(extra)
    return _seat(0, **values)


def _state(owner: PlayerState, **overrides: object) -> GameState:
    imperium = imperium_deck_instance_ids(False)
    seats = [owner, *(_seat(seat) for seat in range(1, 4))]
    values: dict[str, object] = {
        "config": IMMORTALITY,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": intrigue_deck_instance_ids(False, immortality=True)[:6],
        "imperium_row": imperium[:5],
        "imperium_deck": imperium[5:20],
        "tleilaxu_track_spice": 2,
        "players": tuple(seats),
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(overrides)
    return GameState(**values)  # type: ignore[arg-type]


def _place(
    state: GameState, card_id: str, space_id: str, *, graft: bool = False
) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and (dict(action.arguments).get("graft") is True) == graft
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    return apply_agent_action(state, action).state


def _graft(state: GameState, card_id: str, space_id: str, partner_id: str) -> GameState:
    placed = _place(state, card_id, space_id, graft=True)
    partner = next(
        action
        for action in legal_graft_partner_actions(placed, 0)
        if dict(action.arguments)["card_id"] == partner_id
    )
    return apply_graft_partner(placed, partner).state


def _switch(state: GameState) -> GameState:
    return apply_graft_switch(state, legal_graft_switch_actions(state, 0)[0]).state


def _payment(state: GameState, action_id: str, **arguments: object) -> DomainAction:
    return next(
        action
        for action in legal_agent_card_payment_actions(state, 0)
        if action.action_id == action_id
        and all(
            dict(action.arguments).get(key) == value for key, value in arguments.items()
        )
    )


def test_industrial_espionage_draws_and_researches_only_when_grafted() -> None:
    espionage = _tleilaxu("industrial_espionage")
    alone = resolve_agent_card_effect(
        _place(_state(_owner((espionage,))), espionage, "assembly_hall")
    )
    owner = alone.state.players[0]
    assert len(owner.hand) == 1 and owner.specimens == 0
    assert owner.research_space == RESEARCH_START_ID

    grafted = _graft(
        _state(_owner((espionage, FACE_DANCER), research_space="c1r3")),
        espionage,
        "assembly_hall",
        FACE_DANCER,
    )
    result = resolve_agent_card_effect(grafted)
    owner = result.state.players[0]
    assert len(owner.hand) == 1 and owner.specimens == 1
    # From c1r3 the research forks, so its direction frame sits on top.
    assert result.state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE


def test_scientific_breakthrough_researches_and_may_trash_itself_at_two_markers() -> (
    None
):
    breakthrough = _tleilaxu("scientific_breakthrough")
    one = _place(
        _state(_owner((breakthrough,), research_space="c4r2")), breakthrough, "arrakeen"
    )
    assert legal_agent_card_payment_actions(one, 0) == ()
    researched = resolve_agent_card_effect(one)
    # From c4r2 the research forks, so its direction frame opens.
    assert researched.state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE

    two = _place(
        _state(_owner((breakthrough,), research_space="c8r4")), breakthrough, "arrakeen"
    )
    assert {a.action_id for a in legal_agent_card_payment_actions(two, 0)} == {
        "resolve_agent_card_effect",
        "trash_agent_card_self_for_vp",
    }
    result = apply_agent_card_payment(
        two, _payment(two, "trash_agent_card_self_for_vp")
    )
    owner = result.state.players[0]
    assert breakthrough in owner.trashed and breakthrough not in owner.in_play
    assert owner.victory_points == 2  # one at setup plus the reward
    # Past the second genetic marker a Research icon draws a card instead.
    assert len(owner.hand) == 1
    assert "card_trashed" in {event.kind for event in result.events}
    kept = resolve_agent_card_effect(two).state.players[0]
    assert breakthrough in kept.in_play and kept.victory_points == 1


def test_guild_impersonator_needs_spice_gained_this_turn() -> None:
    impersonator = _tleilaxu("guild_impersonator")
    piter = _tleilaxu("piter_genius_advisor")
    # Piter's Spice Trade icon reaches Hagga Basin; the space's spice can be
    # taken before the Impersonator's box.
    grafted = _graft(
        _state(_owner((impersonator, piter), spice_at_turn_start=2)),
        piter,
        "hagga_basin",
        impersonator,
    )
    switched = _switch(grafted)
    early = resolve_agent_card_effect(switched)
    assert early.events[0].kind == "agent_card_effect_unavailable"
    assert early.state.players[0].influence.spacing_guild == 0

    spiced = UprisingRulesEngine().apply(
        switched,
        DomainAction("harvest_maker_spice", 0, (("space_id", "hagga_basin"),)),
    ).state
    late = resolve_agent_card_effect(spiced)
    assert late.events[0].kind == "agent_card_effect_resolved"
    assert late.state.players[0].influence.spacing_guild == 1


def test_slig_farmer_pays_per_partner_icon_and_may_buy_a_track_step() -> None:
    farmer = _tleilaxu("slig_farmer")
    poor = _graft(
        _state(_owner((farmer, DAGGER), resources=Resources(solari=1))),
        farmer,
        "assembly_hall",
        DAGGER,
    )
    assert legal_agent_card_payment_actions(poor, 0) == ()
    resolved = resolve_agent_card_effect(poor)
    dagger_icons = len(personal_card_for_instance(DAGGER).agent_icons)
    assert resolved.state.players[0].resources.solari == 1 + dagger_icons

    rich = _graft(
        _state(_owner((farmer, FACE_DANCER), resources=Resources(solari=2))),
        farmer,
        "assembly_hall",
        FACE_DANCER,
    )
    assert {a.action_id for a in legal_agent_card_payment_actions(rich, 0)} == {
        "resolve_agent_card_effect",
        "pay_agent_card_five_solari_for_tleilaxu",
    }
    paid = apply_agent_card_payment(
        rich, _payment(rich, "pay_agent_card_five_solari_for_tleilaxu")
    ).state.players[0]
    assert paid.resources.solari == 2 + 3 - 5  # Face Dancer: 3 icons
    assert paid.tleilaxu_space == 1


def test_stitched_horror_pays_two_distinct_rewards() -> None:
    horror = _tleilaxu("stitched_horror")
    state = _graft(
        _state(_owner((horror, DAGGER), troops_supply=9)), horror, "arrakeen", DAGGER
    )
    picks = {
        dict(a.arguments)["reward"] for a in legal_agent_card_payment_actions(state, 0)
    }
    assert picks == {"water", "troop", "trash", "tleilaxu"}
    first = apply_agent_card_payment(
        state, _payment(state, "choose_agent_card_reward", reward="water")
    )
    owner = first.state.players[0]
    assert owner.resources.water == 3
    _, context = current_agent_effect_context(first.state)
    assert context["pending_agent_effect"] is True
    second_picks = {
        dict(a.arguments)["reward"]
        for a in legal_agent_card_payment_actions(first.state, 0)
    }
    assert second_picks == {"troop", "trash", "tleilaxu"}
    second = apply_agent_card_payment(
        first.state,
        _payment(first.state, "choose_agent_card_reward", reward="tleilaxu"),
    )
    owner = second.state.players[0]
    assert owner.tleilaxu_space == 1
    _, context = current_agent_effect_context(second.state)
    assert context["pending_agent_effect"] is False

    trashing = apply_agent_card_payment(
        state, _payment(state, "choose_agent_card_reward", reward="trash")
    )
    assert trashing.state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    assert trashing.state.decision_stack[-2].kind == FrameKind.AGENT_EFFECTS
    troops = apply_agent_card_payment(
        state, _payment(state, "choose_agent_card_reward", reward="troop")
    ).state.players[0]
    assert troops.troops_garrison == 4


def test_beguiling_pheromones_trades_a_grafted_card_for_the_visited_faction() -> None:
    pheromones = _tleilaxu("beguiling_pheromones")
    # Arrakeen is no Faction space: nothing to trade.
    city = _graft(
        _state(_owner((pheromones, FACE_DANCER))), pheromones, "arrakeen", FACE_DANCER
    )
    assert legal_agent_card_payment_actions(city, 0) == ()
    assert (
        resolve_agent_card_effect(city).events[0].kind
        == "agent_card_effect_unavailable"
    )

    # Face Dancer's Emperor icon reaches Dutiful Service; Pheromones joins.
    grafted = _graft(
        _state(_owner((FACE_DANCER, pheromones))),
        FACE_DANCER,
        "dutiful_service",
        pheromones,
    )
    switched = _switch(grafted)
    actions = legal_agent_card_payment_actions(switched, 0)
    assert [(a.action_id, dict(a.arguments).get("card_id")) for a in actions] == [
        ("decline_agent_card_payment", None),
        ("trash_grafted_card_for_influence", pheromones),
        ("trash_grafted_card_for_influence", FACE_DANCER),
    ]
    # Trashing the partner expires its un-activated draw (OQ-022, FAQ p. 1).
    partner = apply_agent_card_payment(switched, actions[2])
    owner = partner.state.players[0]
    assert FACE_DANCER in owner.trashed and owner.influence.emperor == 1
    _, context = current_agent_effect_context(partner.state)
    assert context["graft_pending_effect"] is False
    # Trashing itself keeps the Influence (its own cost).
    own = apply_agent_card_payment(switched, actions[1])
    owner = own.state.players[0]
    assert pheromones in owner.trashed and owner.influence.emperor == 1
    _, context = current_agent_effect_context(own.state)
    assert context["graft_pending_effect"] is True


def test_piter_loses_a_troop_for_two_cards_and_research() -> None:
    piter = _tleilaxu("piter_genius_advisor")
    empty = _place(
        _state(_owner((piter,), troops_garrison=0, troops_supply=12)),
        piter,
        "assembly_hall",
    )
    assert [a.action_id for a in legal_agent_card_payment_actions(empty, 0)] == [
        "decline_agent_card_payment"
    ]
    state = _place(
        _state(
            _owner((piter,), troops_garrison=1, troops_conflict=1, troops_supply=10)
        ),
        piter,
        "assembly_hall",
    )
    zones = {
        dict(a.arguments).get("zone")
        for a in legal_agent_card_payment_actions(state, 0)
    }
    assert zones == {None, "garrison", "conflict"}
    result = apply_agent_card_payment(
        state, _payment(state, "lose_agent_card_troop", zone="conflict")
    )
    owner = result.state.players[0]
    # The lost troop returns to the supply; the first research space then
    # takes one specimen from it.
    assert owner.troops_conflict == 0 and owner.troops_supply == 10
    assert owner.specimens == 1
    assert len(owner.hand) == 2
    assert owner.research_space == "c1r3"
    assert "unit_lost" in {event.kind for event in result.events}


def test_the_codec_holds_the_tleilaxu_choices() -> None:
    codec = ActionCodec(IMMORTALITY)
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    for action in (
        DomainAction("trash_agent_card_self_for_vp", 0),
        DomainAction("pay_agent_card_five_solari_for_tleilaxu", 0),
        DomainAction(
            "trash_grafted_card_for_influence", 0, (("card_id", FACE_DANCER),)
        ),
        DomainAction("lose_agent_card_troop", 0, (("zone", "garrison"),)),
        DomainAction("choose_agent_card_reward", 0, (("reward", "trash"),)),
    ):
        assert codec.decode(codec.encode(action), 0) == action
        assert action.action_id not in base
