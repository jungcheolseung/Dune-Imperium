"""Tests for the Immortality Imperium cards with choice boxes (slice 5b-2).

Rule source: the card faces transcribed in
``docs/implementation-audits/immortality.md``; OQ-052 (a short Intrigue
deck) and OQ-053 (the Surgeon's two troops from one zone).
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
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
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.observation import observe_state, peeked_intrigue_ids
from dune_imperium.rules.acquisition import (
    apply_agent_card_acquisition,
    legal_agent_card_acquisitions,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_influence,
    apply_agent_card_payment,
    legal_agent_card_influence_actions,
    legal_agent_card_payment_actions,
    resolve_agent_card_effect,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft import apply_graft_partner, legal_graft_partner_actions
from dune_imperium.rules.intrigue_peek import (
    apply_intrigue_peek,
    legal_intrigue_peek_actions,
)
from dune_imperium.rules.reveal_turn import (
    apply_reveal_gain,
    apply_reveal_influence_loss,
    apply_reveal_troop_move,
    apply_reveal_troop_sacrifice,
    begin_reveal_turn,
    legal_reveal_gain_actions,
    legal_reveal_influence_loss_actions,
    legal_reveal_troop_move_actions,
    legal_reveal_troop_sacrifice_actions,
)
from dune_imperium.simulation.invariants import check_observation_privacy

IMMORTALITY = RulesetConfig(immortality=True)
STARTERS = starting_deck_instance_ids(0, immortality=True)
DAGGER = next(card for card in STARTERS if "dagger:0" in card)
FACE_DANCER = "tleilaxu:face_dancer:0"
INTRIGUE = intrigue_deck_instance_ids(False, immortality=True)


def _card(card_id: str, copy: int = 0) -> str:
    return f"imperium:{card_id}:{copy}"


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


def _state(owner: PlayerState, *others: PlayerState, **overrides: object) -> GameState:
    imperium = imperium_deck_instance_ids(False)
    seats = [owner, *others]
    seats.extend(_seat(seat) for seat in range(len(seats), 4))
    values: dict[str, object] = {
        "config": IMMORTALITY,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": INTRIGUE[:6],
        "imperium_row": imperium[:5],
        "imperium_deck": imperium[5:20],
        "tleilaxu_track_spice": 2,
        "reserve_stacks": (("prepare_the_way", 8), ("the_spice_must_flow", 10)),
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


def _reveal(state: GameState) -> GameState:
    return begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state


def _payment(state: GameState, action_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_card_payment_actions(state, 0)
        if action.action_id == action_id
    )


def test_dissecting_kit_trashes_the_partner_for_a_specimen() -> None:
    kit = _card("dissecting_kit")
    # A Graft card "can't be played alone" [Immortality p. 10].
    alone = _state(_owner((kit,)))
    assert not any(
        dict(a.arguments)["card_id"] == kit for a in legal_agent_actions(alone, 0)
    )

    grafted = _graft(
        _state(_owner((kit, FACE_DANCER))),
        kit,
        "arrakeen",
        FACE_DANCER,
    )
    assert {a.action_id for a in legal_agent_card_payment_actions(grafted, 0)} == {
        "decline_agent_card_payment",
        "trash_grafted_card_for_specimen",
    }
    result = apply_agent_card_payment(
        grafted, _payment(grafted, "trash_grafted_card_for_specimen")
    )
    owner = result.state.players[0]
    assert FACE_DANCER in owner.trashed and FACE_DANCER not in owner.in_play
    assert owner.specimens == 1
    # The partner's un-activated box expired with it (OQ-022).
    _, context = current_agent_effect_context(result.state)
    assert context["graft_pending_effect"] is False
    assert "card_trashed" in {event.kind for event in result.events}

    marked = _reveal(_state(_owner((kit,), research_space="c4r2")))
    gains = dict(marked.decision_stack[-1].context)["reveal_pending_gains"]
    assert str(gains).startswith("tleilaxu|1|")


def test_for_humanity_chooses_influence_and_trades_influence_for_a_vp() -> None:
    humanity = _card("for_humanity")
    placed = _place(_state(_owner((humanity,))), humanity, "assembly_hall")
    picks = {
        dict(a.arguments)["faction"]
        for a in legal_agent_card_influence_actions(placed, 0)
    }
    assert picks == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}

    plain = _reveal(_state(_owner((humanity,), influence=Influence(fremen=1))))
    assert plain.decision_stack[-1].kind == FrameKind.REVEAL
    allied = _reveal(
        _state(
            _owner(
                (humanity,),
                influence=Influence(bene_gesserit=4, fremen=1),
                alliance_faction_ids=("bene_gesserit",),
            )
        )
    )
    assert allied.decision_stack[-1].kind == FrameKind.REVEAL_CHOICE
    actions = legal_reveal_influence_loss_actions(allied, 0)
    assert {a.action_id for a in actions} == {
        "decline_reveal_influence_loss",
        "lose_reveal_influence_for_vp",
    }
    lose = next(a for a in actions if dict(a.arguments).get("faction") == "fremen")
    result = apply_reveal_influence_loss(allied, lose)
    owner = result.state.players[0]
    # Every seat starts the game with one Victory Point.
    assert owner.influence.fremen == 0 and owner.victory_points == 2
    assert result.state.decision_stack[-1].kind == FrameKind.REVEAL
    declined = apply_reveal_influence_loss(allied, actions[0]).state
    assert declined.players[0].victory_points == 1


def test_high_priority_travel_offers_the_draw_or_the_combat_icon() -> None:
    travel = _card("high_priority_travel")
    low = _place(_state(_owner((travel,))), travel, "assembly_hall")
    assert legal_agent_card_payment_actions(low, 0) == ()
    assert (
        resolve_agent_card_effect(low).events[0].kind == "agent_card_effect_unavailable"
    )

    high = _place(
        _state(
            _owner(
                (travel,),
                influence=Influence(spacing_guild=2),
                troops_garrison=2,
                troops_supply=10,
            )
        ),
        travel,
        "assembly_hall",
    )
    assert {a.action_id for a in legal_agent_card_payment_actions(high, 0)} == {
        "resolve_agent_card_effect",
        "take_agent_card_combat_icon",
    }
    drawn = resolve_agent_card_effect(high)
    assert len(drawn.state.players[0].hand) == 1
    combat = apply_agent_card_payment(
        high, _payment(high, "take_agent_card_combat_icon")
    )
    _, context = current_agent_effect_context(combat.state)
    assert context["pending_combat_deployment"] is True
    assert len(combat.state.players[0].hand) == 0
    revealed = _reveal(_state(_owner((travel,))))
    assert (
        dict(revealed.decision_stack[-1].context)["reveal_pending_gains"]
        == "resources|1/0/0|imperium:high_priority_travel:0"
    )


def test_imperium_ceremony_peeks_two_intrigue_cards_and_keeps_one() -> None:
    ceremony = _card("imperium_ceremony")
    placed = _place(_state(_owner((ceremony,))), ceremony, "assembly_hall")
    result = resolve_agent_card_effect(placed)
    state = result.state
    assert state.decision_stack[-1].kind == FrameKind.INTRIGUE_PEEK
    assert peeked_intrigue_ids(state, 0) == INTRIGUE[:2]
    assert peeked_intrigue_ids(state, 1) == ()
    own_view = observe_state(state, 0).private
    other_view = observe_state(state, 1).private
    assert own_view is not None and own_view.peeked_intrigue_ids == INTRIGUE[:2]
    assert other_view is not None and other_view.peeked_intrigue_ids == ()
    check_observation_privacy(state)
    actions = legal_intrigue_peek_actions(state, 0)
    assert [dict(a.arguments)["instance_id"] for a in actions] == list(INTRIGUE[:2])
    kept = apply_intrigue_peek(state, actions[1])
    owner = kept.state.players[0]
    assert owner.intrigue_cards == (INTRIGUE[1],)
    assert kept.state.intrigue_deck == (INTRIGUE[0], *INTRIGUE[2:6])
    assert kept.state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    private = [event for event in kept.events if event.visible_to is not None]
    assert private[0].kind == "intrigue_card_kept" and private[0].visible_to == (0,)
    assert not any(
        "card_id" in dict(event.payload)
        for event in kept.events
        if event.visible_to is None
    )
    codec = ActionCodec(IMMORTALITY)
    for action in actions:
        assert codec.decode(codec.encode(action), 0) == action

    # OQ-052 (user ruling): with one card face down and a discard pile, the
    # discard is shuffled into a new deck beneath that card and the peek
    # then looks at two — the old top card first.
    short = resolve_agent_card_effect(
        _place(
            _state(
                _owner((ceremony,)),
                intrigue_deck=INTRIGUE[:1],
                intrigue_discard=INTRIGUE[1:4],
            ),
            ceremony,
            "assembly_hall",
        )
    )
    assert short.state.decision_stack[-1].kind == FrameKind.INTRIGUE_RESHUFFLE
    assert dict(short.state.decision_stack[-1].context)["purpose"] == "peek"
    engine = UprisingRulesEngine()
    decision = engine.current_decision(short.state)
    assert isinstance(decision, ChanceDecision)
    shuffled = engine.apply(short.state, ChanceResolver(seed=5).resolve(decision)).state
    assert shuffled.decision_stack[-1].kind == FrameKind.INTRIGUE_PEEK
    assert shuffled.intrigue_discard == ()
    peeked = peeked_intrigue_ids(shuffled, 0)
    assert peeked[0] == INTRIGUE[0] and peeked[1] in INTRIGUE[1:4]
    assert len(shuffled.intrigue_deck) == 4
    # An empty deck shuffles too; with nothing to shuffle the single card
    # is simply kept.
    empty = resolve_agent_card_effect(
        _place(
            _state(
                _owner((ceremony,)), intrigue_deck=(), intrigue_discard=INTRIGUE[:3]
            ),
            ceremony,
            "assembly_hall",
        )
    )
    assert empty.state.decision_stack[-1].kind == FrameKind.INTRIGUE_RESHUFFLE
    lone = resolve_agent_card_effect(
        _place(
            _state(
                _owner((ceremony,)), intrigue_deck=INTRIGUE[:1], intrigue_discard=()
            ),
            ceremony,
            "assembly_hall",
        )
    )
    assert lone.state.players[0].intrigue_cards == (INTRIGUE[0],)
    assert lone.state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS


def test_imperium_ceremony_through_the_engine() -> None:
    ceremony = _card("imperium_ceremony")
    engine = UprisingRulesEngine()
    state = resolve_agent_card_effect(
        _place(_state(_owner((ceremony,))), ceremony, "assembly_hall")
    ).state
    legal = engine.legal_actions(state, 0)
    assert {a.action_id for a in legal} == {"keep_peeked_intrigue"}
    after = engine.apply(state, legal[0])
    assert after.state.players[0].intrigue_cards == (INTRIGUE[0],)


def test_interstellar_conspiracy_needs_an_emperor_or_guild_partner() -> None:
    conspiracy = _card("interstellar_conspiracy")
    wrong = _graft(_state(_owner((conspiracy, DAGGER))), conspiracy, "arrakeen", DAGGER)
    assert legal_agent_card_influence_actions(wrong, 0) == ()
    resolved = resolve_agent_card_effect(wrong)
    assert resolved.state.players[0].resources.spice == 3
    assert resolved.events[0].kind == "agent_card_effect_resolved"
    keys = _card("keys_to_power")  # Spacing Guild, Bene Gesserit
    right = _graft(_state(_owner((conspiracy, keys))), conspiracy, "arrakeen", keys)
    picks = legal_agent_card_influence_actions(right, 0)
    assert {dict(a.arguments)["faction"] for a in picks} == {
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    }
    chosen = apply_agent_card_influence(
        right, next(a for a in picks if dict(a.arguments)["faction"] == "fremen")
    )
    owner = chosen.state.players[0]
    assert owner.influence.fremen == 1 and owner.resources.spice == 3


def test_shadout_mapes_deploys_or_retreats_one_troop_at_reveal() -> None:
    mapes = _card("shadout_mapes")
    none = _reveal(_state(_owner((mapes,), troops_garrison=0, troops_supply=12)))
    assert none.decision_stack[-1].kind == FrameKind.REVEAL

    revealed = _reveal(
        _state(_owner((mapes,), troops_garrison=2, troops_conflict=1, troops_supply=9))
    )
    assert revealed.decision_stack[-1].kind == FrameKind.REVEAL_CHOICE
    actions = legal_reveal_troop_move_actions(revealed, 0)
    assert {a.action_id for a in actions} == {
        "decline_reveal_troop_move",
        "deploy_reveal_card_troop",
        "retreat_reveal_card_troop",
    }
    deployed = apply_reveal_troop_move(revealed, actions[1])
    owner = deployed.state.players[0]
    assert owner.troops_conflict == 2 and owner.troops_garrison == 1
    assert dict(deployed.state.decision_stack[-1].context)["strength"] == 2 * 2 + 1
    retreated = apply_reveal_troop_move(revealed, actions[2])
    owner = retreated.state.players[0]
    assert owner.troops_conflict == 0 and owner.troops_garrison == 3
    assert owner.combat_strength == 0
    assert dict(retreated.state.decision_stack[-1].context)["strength"] == 0
    declined = apply_reveal_troop_move(revealed, actions[0]).state
    assert declined.decision_stack[-1].kind == FrameKind.REVEAL


def test_tleilaxu_master_acquires_a_cheap_card_and_researches_at_reveal() -> None:
    master = _card("tleilaxu_master")
    unmarked = _place(_state(_owner((master,))), master, "assembly_hall")
    assert legal_agent_card_acquisitions(unmarked, 0) == ()
    assert (
        resolve_agent_card_effect(unmarked).events[0].kind
        == "agent_card_effect_unavailable"
    )

    imperium = imperium_deck_instance_ids(False)
    row = (_card("spiritual_fervor"), _card("for_humanity"), *imperium[2:5])
    one = _place(
        _state(_owner((master,), research_space="c4r2"), imperium_row=row),
        master,
        "assembly_hall",
    )
    actions = legal_agent_card_acquisitions(one, 0)
    ids = {
        (
            a.action_id,
            dict(a.arguments).get("instance_id", dict(a.arguments).get("card_id")),
        )
        for a in actions
    }
    assert ("decline_agent_card_acquisition", None) in ids
    assert ("acquire_imperium_by_card", _card("spiritual_fervor")) in ids  # cost 3
    assert ("acquire_imperium_by_card", _card("for_humanity")) not in ids  # cost 7
    assert ("acquire_reserve_by_card", "prepare_the_way") in ids
    acquire = next(
        a
        for a in actions
        if dict(a.arguments).get("instance_id") == _card("spiritual_fervor")
    )
    result = apply_agent_card_acquisition(one, acquire)
    owner = result.state.players[0]
    assert _card("spiritual_fervor") in owner.discard_pile
    # Spiritual Fervor's Research acquire box opened above the turn.
    assert result.state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE

    two = _place(
        _state(_owner((master,), research_space="c8r4"), imperium_row=row),
        master,
        "assembly_hall",
    )
    acquire = next(
        a
        for a in legal_agent_card_acquisitions(two, 0)
        if dict(a.arguments).get("card_id") == "prepare_the_way"
    )
    owner = apply_agent_card_acquisition(two, acquire).state.players[0]
    assert any(card.startswith("reserve:prepare_the_way") for card in owner.hand)
    assert any(card.startswith("reserve:prepare_the_way") for card in owner.hand_public)

    revealed = _reveal(_state(_owner((master,))))
    assert (
        dict(revealed.decision_stack[-1].context)["reveal_pending_gains"]
        == "research|2|imperium:tleilaxu_master:0"
    )


def test_tleilaxu_surgeon_spends_specimens_and_sacrifices_troops() -> None:
    surgeon = _card("tleilaxu_surgeon")
    dry = _place(
        _state(_owner((surgeon,), specimens=1, troops_supply=8)), surgeon, "arrakeen"
    )
    assert [a.action_id for a in legal_agent_card_payment_actions(dry, 0)] == [
        "decline_agent_card_payment"
    ]
    wet = _place(
        _state(_owner((surgeon,), specimens=2, troops_supply=7)), surgeon, "arrakeen"
    )
    paid = apply_agent_card_payment(wet, _payment(wet, "pay_agent_card_two_specimens"))
    owner = paid.state.players[0]
    assert owner.specimens == 0 and owner.troops_supply == 9
    assert owner.tleilaxu_space == 2
    assert len(owner.intrigue_cards) == 1  # the track's second space

    revealed = _reveal(
        _state(
            _owner((surgeon,), troops_garrison=2, troops_conflict=2, troops_supply=8)
        )
    )
    assert revealed.decision_stack[-1].kind == FrameKind.REVEAL_CHOICE
    actions = legal_reveal_troop_sacrifice_actions(revealed, 0)
    assert [(a.action_id, dict(a.arguments).get("zones")) for a in actions] == [
        ("decline_reveal_troop_sacrifice", None),
        ("lose_reveal_troops_for_specimens", "garrison,garrison"),
        ("lose_reveal_troops_for_specimens", "garrison,conflict"),
        ("lose_reveal_troops_for_specimens", "conflict,conflict"),
    ]
    garrison = apply_reveal_troop_sacrifice(revealed, actions[1]).state.players[0]
    assert garrison.troops_garrison == 0 and garrison.specimens == 2
    assert garrison.troops_supply == 8  # two lost, two into the tanks
    conflict = apply_reveal_troop_sacrifice(revealed, actions[3])
    owner = conflict.state.players[0]
    assert owner.troops_conflict == 0 and owner.specimens == 2
    assert dict(conflict.state.decision_stack[-1].context)["strength"] == 0
    # One from each zone (OQ-053, user ruling): the Conflict troop's two
    # strength leaves with it.
    mixed = apply_reveal_troop_sacrifice(revealed, actions[2])
    owner = mixed.state.players[0]
    assert owner.troops_garrison == 1 and owner.troops_conflict == 1
    assert owner.specimens == 2
    assert dict(mixed.state.decision_stack[-1].context)["strength"] == 2
    one_each = _reveal(
        _state(
            _owner((surgeon,), troops_garrison=1, troops_conflict=1, troops_supply=10)
        )
    )
    # A troop in each zone still makes two (OQ-053).
    assert one_each.decision_stack[-1].kind == FrameKind.REVEAL_CHOICE
    assert [
        dict(a.arguments).get("zones")
        for a in legal_reveal_troop_sacrifice_actions(one_each, 0)
    ] == [None, "garrison,conflict"]


def test_the_codec_holds_the_slice_choices_only_with_immortality() -> None:
    codec = ActionCodec(IMMORTALITY)
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    for action in (
        DomainAction("pay_agent_card_two_specimens", 0),
        DomainAction("trash_grafted_card_for_specimen", 0),
        DomainAction("take_agent_card_combat_icon", 0),
        DomainAction("acquire_reserve_by_card", 0, (("card_id", "prepare_the_way"),)),
        DomainAction(
            "acquire_imperium_by_card", 0, (("instance_id", _card("for_humanity")),)
        ),
        DomainAction("lose_reveal_influence_for_vp", 0, (("faction", "fremen"),)),
        DomainAction(
            "lose_reveal_influence_for_vp",
            0,
            (("alliance_recipient", 2), ("faction", "fremen")),
        ),
        DomainAction("deploy_reveal_card_troop", 0),
        DomainAction("retreat_reveal_card_troop", 0),
        DomainAction(
            "lose_reveal_troops_for_specimens", 0, (("zones", "garrison,conflict"),)
        ),
        DomainAction("decline_reveal_troop_sacrifice", 0),
        DomainAction(
            "resume_reveal_choice", 0, (("effect", "may_deploy_or_retreat_one_troop"),)
        ),
    ):
        assert codec.decode(codec.encode(action), 0) == action
        assert (
            action.action_id not in base or action.action_id == "resume_reveal_choice"
        )
    assert "may_deploy_or_retreat_one_troop" not in {
        dict(template.arguments).get("effect")
        for template in ActionCodec(RulesetConfig()).catalog
        if template.action_id == "resume_reveal_choice"
    }


def test_an_acquired_research_box_stacks_above_the_acquiring_frame() -> None:
    """Spiritual Fervor's Research direction never buries the acquirer's frame.

    Found by the 2026-09-08 heuristic soak (seed 11): an Intrigue
    acquisition raised "buried its choice frame" once the acquire box
    opened its direction choice.
    """

    fervor = _card("spiritual_fervor")
    imperium = imperium_deck_instance_ids(False)
    row = (fervor, *imperium[1:5])
    engine = UprisingRulesEngine()

    # Inspire Awe: "acquire a card costing 3 or less" (an Intrigue slot).
    awe = next(card for card in INTRIGUE if ":inspire_awe:" in card)
    # From c1r3 the research forks (c2r2 / c2r4), so a direction frame opens.
    state = _state(
        _owner((DAGGER,), intrigue_cards=(awe,), research_space="c1r3"),
        imperium_row=row,
    )
    play = DomainAction("play_intrigue", 0, (("card_id", awe), ("option", 0)))
    opened = engine.apply(state, play).state
    assert opened.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    acquire = next(
        a
        for a in engine.legal_actions(opened, 0)
        if dict(a.arguments).get("instance_id") == fervor
    )
    done = engine.apply(opened, acquire).state
    assert [frame.kind for frame in done.decision_stack] == [
        FrameKind.TURN,
        FrameKind.RESEARCH_ADVANCE,
    ]
    assert fervor in done.players[0].discard_pile
    assert awe in done.intrigue_discard

    # Price is No Object: "acquire a card to your hand, paying Solari".
    price = _card("price_is_no_object")
    state = _state(
        _owner((price,), resources=Resources(solari=5), research_space="c1r3"),
        imperium_row=row,
    )
    placed = _place(state, price, "dutiful_service")
    acquire = next(
        a
        for a in engine.legal_actions(placed, 0)
        if a.action_id == "acquire_imperium_with_solari"
        and dict(a.arguments)["instance_id"] == fervor
    )
    done = engine.apply(placed, acquire).state
    assert done.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE
    below = done.decision_stack[-2]
    assert below.kind == FrameKind.AGENT_EFFECTS
    assert dict(below.context)["pending_agent_effect"] is False
    assert fervor in done.players[0].hand


def test_reveal_research_icons_resolve_one_per_action_and_share_a_shuffle() -> None:
    """Tleilaxu Master's two Reveal Research icons resolve apart (designer
    ruling, OQ-057): each action advances once. Past the second marker each
    advance draws; with an empty deck the first draw shuffles the discard and
    the second draws from the new deck without a second shuffle."""

    from dune_imperium.core.chance import ChanceOutcome
    from dune_imperium.rules.card_draw import apply_personal_draw_reshuffle

    master = _card("tleilaxu_master")
    discard = tuple(card for card in STARTERS if "dagger" not in card)[:4]
    owner = _owner((master,), deck=(), discard_pile=discard, research_space="c8r4")
    revealed = _reveal(_state(owner))

    first = apply_reveal_gain(revealed, legal_reveal_gain_actions(revealed, 0)[0]).state
    reveal = next(frame for frame in first.decision_stack if frame.kind == "reveal")
    assert dict(reveal.context)["reveal_pending_gains"] == (
        "research|1|imperium:tleilaxu_master:0"
    )
    reshuffle = first.decision_stack[-1]
    assert reshuffle.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
    assert dict(reshuffle.context)["count"] == 1
    assert isinstance(reshuffle.decision, ChanceDecision)

    shuffled = apply_personal_draw_reshuffle(
        first, ChanceOutcome(reshuffle.decision.decision_id, discard)
    ).state
    # A card drawn during the owner's Reveal is revealed at once [FAQ p. 3].
    assert len(shuffled.players[0].in_play) == 2
    assert shuffled.decision_stack[-1].kind == "reveal"
    actions = legal_reveal_gain_actions(shuffled, 0)
    assert [action.action_id for action in actions] == ["advance_reveal_research"]
    second = apply_reveal_gain(shuffled, actions[0]).state
    assert len(second.players[0].in_play) == 3
    assert not any(
        frame.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
        for frame in second.decision_stack
    )
    assert legal_reveal_gain_actions(second, 0) == ()


def test_imperium_ceremony_keep_owes_a_suspensor_suits_troop() -> None:
    # Designer ruling (Message from designer, OQ-057): Imperium Ceremony's
    # "keep one" is an Intrigue draw, so Suspensor Suits pays its troop.
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.rules.tech import deploy_suspensor_troops

    ceremony = _card("imperium_ceremony")
    base = _state(_owner((ceremony,)))
    state = replace(
        base,
        config=RulesetConfig(immortality=True, bloodlines=True, tech_module=True),
        tech_stacks=(("glowglobes",), (), ()),
        players=(
            replace(base.players[0], tech_ids=("suspensor_suits",)),
            *base.players[1:],
        ),
    )
    placed = _place(state, ceremony, "assembly_hall")
    peeking = resolve_agent_card_effect(placed).state
    kept = apply_intrigue_peek(peeking, legal_intrigue_peek_actions(peeking, 0)[0])
    owner = kept.state.players[0]
    assert len(owner.intrigue_cards) == 1
    assert owner.suspensor_owed == 1

    deployed = deploy_suspensor_troops(RuleResult(state=kept.state)).state
    assert deployed.players[0].suspensor_owed == 0
    assert deployed.players[0].troops_conflict == 1
    assert deployed.players[0].troops_supply == 8


