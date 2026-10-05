"""Tests for the Immortality Imperium cards with single-box play data.

Rule source: the card faces transcribed in
``docs/implementation-audits/immortality.md`` (Imperium table).
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import Transition
from dune_imperium.rules.acquisition import (
    apply_imperium_acquisition,
    legal_imperium_acquisitions,
)
from dune_imperium.rules.agent_effects import (
    agent_card_effect_is_unavailable,
    apply_agent_card_influence,
    apply_agent_card_payment,
    fizzle_pending_agent_icons,
    legal_agent_card_icon_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_payment_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
    resolve_faction_influence,
)
from dune_imperium.rules.agent_icons import effective_agent_icons
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft import apply_graft_partner, legal_graft_partner_actions
from dune_imperium.rules.reveal_turn import (
    apply_reveal_gain,
    begin_reveal_turn,
    legal_reveal_gain_actions,
)

IMMORTALITY = RulesetConfig(immortality=True)
STARTERS = starting_deck_instance_ids(0, immortality=True)
DAGGER = next(card for card in STARTERS if "dagger:0" in card)
FACE_DANCER = "tleilaxu:face_dancer:0"


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
        "intrigue_deck": intrigue_deck_instance_ids(False)[:6],
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


def _reveal(state: GameState) -> GameState:
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    return revealed.state


def _take_gains(state: GameState) -> GameState:
    while actions := legal_reveal_gain_actions(state, 0):
        state = apply_reveal_gain(state, actions[0]).state
    return state


def _persuasion(state: GameState) -> int:
    return int(dict(state.decision_stack[-1].context)["persuasion"])


def test_bene_tleilax_lab_generates_a_specimen_and_marks_spice() -> None:
    lab = _card("bene_tleilax_lab")
    state = _place(_state(_owner((lab,))), lab, "arrakeen")
    resolved = resolve_agent_card_effect(state)
    assert resolved.state.players[0].specimens == 1

    plain = _take_gains(_reveal(_state(_owner((lab,)))))
    assert plain.players[0].resources.spice == 2
    marked = _take_gains(_reveal(_state(_owner((lab,), research_space="c4r2"))))
    assert marked.players[0].resources.spice == 3


def test_blank_slate_gains_the_faction_icons_only_when_grafted() -> None:
    slate = _card("blank_slate")
    owner = _owner((slate, FACE_DANCER))
    from dune_imperium.content.uprising.personal_cards import personal_card_for_instance

    card = personal_card_for_instance(slate)
    assert len(effective_agent_icons(card, owner)) == 3
    assert len(effective_agent_icons(card, owner, grafted=True)) == 7
    state = _state(owner)
    spaces = {
        dict(action.arguments)["space_id"]
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["card_id"] == slate
        and dict(action.arguments).get("graft") is True
    }
    assert "dutiful_service" in spaces


def test_clandestine_meeting_needs_a_graft_and_pays_influence_and_intrigue() -> None:
    meeting = _card("clandestine_meeting")
    alone = _state(_owner((meeting,)))
    assert not any(
        dict(a.arguments)["card_id"] == meeting for a in legal_agent_actions(alone, 0)
    )
    state = _graft(
        _state(_owner((FACE_DANCER, meeting))), FACE_DANCER, "dutiful_service", meeting
    )
    from dune_imperium.rules.graft import apply_graft_switch, legal_graft_switch_actions

    switched = apply_graft_switch(state, legal_graft_switch_actions(state, 0)[0]).state
    resolved = resolve_agent_card_effect(switched)
    owner = resolved.state.players[0]
    assert owner.influence.bene_gesserit == 1
    assert len(owner.intrigue_cards) == 1


def test_corrupt_smuggler_and_keys_to_power_conditions() -> None:
    smuggler = _card("corrupt_smuggler")
    alone = resolve_agent_card_effect(
        _place(_state(_owner((smuggler,))), smuggler, "hagga_basin")
    )
    assert alone.state.players[0].resources.spice == 2  # Hagga Basin is still pending
    assert alone.events[0].kind == "agent_card_effect_unavailable"
    grafted = _graft(
        _state(_owner((smuggler, FACE_DANCER))), smuggler, "hagga_basin", FACE_DANCER
    )
    resolved = resolve_agent_card_effect(grafted)
    assert resolved.state.players[0].resources.spice == 2 + 2

    keys = _card("keys_to_power")
    low = resolve_agent_card_effect(
        _place(_state(_owner((keys,))), keys, "assembly_hall")
    )
    assert low.events[0].kind == "agent_card_effect_unavailable"
    high = resolve_agent_card_effect(
        _place(
            _state(_owner((keys,), influence=Influence(emperor=2))),
            keys,
            "assembly_hall",
        )
    )
    assert high.state.players[0].resources.spice == 4


def test_lisan_al_gaib_bond_and_acquire_box() -> None:
    lisan = _card("lisan_al_gaib")
    alone = resolve_agent_card_effect(
        _place(_state(_owner((lisan,))), lisan, "arrakeen")
    )
    assert alone.events[0].kind == "agent_card_effect_unavailable"
    with_bond = _state(_owner((lisan,), in_play=(_card("planned_coupling"),)))
    resolved = resolve_agent_card_effect(_place(with_bond, lisan, "arrakeen"))
    assert resolved.state.players[0].influence.fremen == 1
    # The grafted partner may provide the Bond after the placement.
    grafted = _graft(
        _state(_owner((lisan, _card("planned_coupling")))),
        lisan,
        "arrakeen",
        _card("planned_coupling"),
    )
    resolved = resolve_agent_card_effect(grafted)
    assert resolved.state.players[0].influence.fremen == 1

    state = _reveal(
        _state(_owner((DAGGER,), resources=Resources(solari=0, spice=0, water=1)))
    )
    imperium = imperium_deck_instance_ids(False)
    state = replace(state, imperium_row=(lisan, *imperium[1:5]))
    context = dict(state.decision_stack[-1].context)
    context["persuasion"] = 4
    state = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(state.decision_stack[-1], context=tuple(sorted(context.items()))),
        ),
    )
    action = next(
        a
        for a in legal_imperium_acquisitions(state, 0)
        if dict(a.arguments)["instance_id"] == lisan
    )
    acquired = apply_imperium_acquisition(state, action)
    assert acquired.state.players[0].resources.spice == 1


def test_long_reach_icons_and_two_distinct_influences() -> None:
    reach = _card("long_reach")
    alone = _state(_owner((reach,)))
    assert not any(
        dict(a.arguments)["card_id"] == reach for a in legal_agent_actions(alone, 0)
    )
    bonded = _place(
        _state(_owner((reach,), in_play=(_card("planned_coupling"),))),
        reach,
        "assembly_hall",
    )
    picks = {
        dict(a.arguments)["faction"]: a
        for a in legal_agent_card_influence_actions(bonded, 0)
    }
    assert set(picks) == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    first = apply_agent_card_influence(bonded, picks["fremen"]).state
    _, context = current_agent_effect_context(first)
    assert context["pending_agent_effect"] is True
    # "Choose two": both picks first, then both gains (designer ruling, OQ-057).
    assert first.players[0].influence.fremen == 0
    second_picks = {
        dict(a.arguments)["faction"]
        for a in legal_agent_card_influence_actions(first, 0)
    }
    assert "fremen" not in second_picks
    done = apply_agent_card_influence(
        first,
        next(
            a
            for a in legal_agent_card_influence_actions(first, 0)
            if dict(a.arguments)["faction"] == "emperor"
        ),
    ).state
    owner = done.players[0]
    assert owner.influence.fremen == 1 and owner.influence.emperor == 1



def test_long_reach_with_one_faction_below_the_top_pays_it_at_the_turn_end() -> (
    None
):
    """"Choose two" never names a Faction at the top (OQ-060). With one
    below it that one is named; no second pick is left, so the box waits
    (a later effect of the turn may lower a cube, OQ-057 (1)) and the turn's
    end pays the named Faction and loses the other, as OQ-060 pays a
    Conflict reward's first named Faction."""

    reach = _card("long_reach")
    owner = _owner(
        (reach,),
        in_play=(_card("planned_coupling"),),
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=3),
    )
    bonded = _place(_state(owner), reach, "assembly_hall")
    (only,) = legal_agent_card_influence_actions(bonded, 0)
    assert dict(only.arguments)["faction"] == "fremen"
    named = apply_agent_card_influence(bonded, only).state
    assert named.players[0].influence.fremen == 3
    assert legal_agent_card_influence_actions(named, 0) == ()
    assert agent_card_effect_is_unavailable(named)
    engine = UprisingRulesEngine()
    actions = engine.legal_actions(named, 0)
    assert DomainAction("resolve_agent_card_effect", 0) not in actions
    while board := [a for a in actions if a.action_id == "resolve_board_effect"]:
        named = engine.apply(named, board[0]).state
        actions = engine.legal_actions(named, 0)
    finished = engine.apply(named, DomainAction("finish_agent_turn", 0))
    assert finished.state.players[0].influence.fremen == 4
    assert finished.state.players[0].influence.emperor == 6
    assert "agent_card_effect_unavailable" in {e.kind for e in finished.events}


def test_ghola_grafted_to_long_reach_turns_its_greyed_icons_on() -> None:
    # Designer ruling (Email, TTS Discord; OQ-057): Long Reach grafted with
    # Ghola has all three icons. With Ghola in hand the graft placement
    # reaches the Landsraad, and only Ghola may then be the partner.
    reach = _card("long_reach")
    ghola = "tleilaxu:ghola:0"
    state = _state(_owner((reach, ghola, DAGGER)))
    placements = {
        (dict(a.arguments)["space_id"], dict(a.arguments).get("graft"))
        for a in legal_agent_actions(state, 0)
        if dict(a.arguments)["card_id"] == reach
    }
    assert ("assembly_hall", True) in placements
    assert ("assembly_hall", None) not in placements
    assert ("arrakeen", True) in placements

    placed = _place(state, reach, "assembly_hall", graft=True)
    partners = [
        dict(a.arguments)["card_id"] for a in legal_graft_partner_actions(placed, 0)
    ]
    assert partners == [ghola]
    grafted = apply_graft_partner(placed, legal_graft_partner_actions(placed, 0)[0])
    _, context = current_agent_effect_context(grafted.state)
    assert context["pending_agent_effect"] is True
    picks = {
        dict(a.arguments)["faction"]
        for a in legal_agent_card_influence_actions(grafted.state, 0)
    }
    assert picks == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}

    # Without Ghola a plain Dagger partner leaves the greyed icons off.
    plain = _state(_owner((reach, DAGGER)))
    assert not any(
        dict(a.arguments)["card_id"] == reach for a in legal_agent_actions(plain, 0)
    )


def test_long_reach_grafted_with_a_bene_gesserit_card_has_its_icons() -> None:
    # "If you have another Bene Gesserit card in play, this has [Landsraad],
    # [City], and [Spice Trade]." [Long Reach card]. A Graft pair is played
    # together and "You may use an Agent icon from either card to send your
    # Agent" [Immortality p. 10]; the Ghola clarification counts the Bene
    # Gesserit card it is grafted to as in play for "if you have a Bene
    # Gesserit card in play" [Immortality p. 14]. So Planned Coupling (a Bene
    # Gesserit Graft card) grafted with Long Reach turns the icons on, and
    # the space they reach keeps Planned Coupling as the only partner.
    reach = _card("long_reach")
    coupling = _card("planned_coupling")
    state = _state(_owner((reach, coupling, DAGGER)))
    placements = {
        (dict(a.arguments)["space_id"], dict(a.arguments).get("graft"))
        for a in legal_agent_actions(state, 0)
        if dict(a.arguments)["card_id"] == reach
    }
    assert {("assembly_hall", True), ("arrakeen", True), ("imperial_basin", True)} <= (
        placements
    )
    assert ("assembly_hall", None) not in placements

    placed = _place(state, reach, "assembly_hall", graft=True)
    partners = [
        dict(a.arguments)["card_id"] for a in legal_graft_partner_actions(placed, 0)
    ]
    assert partners == [coupling]
    grafted = apply_graft_partner(placed, legal_graft_partner_actions(placed, 0)[0])
    picks = {
        dict(a.arguments)["faction"]
        for a in legal_agent_card_influence_actions(grafted.state, 0)
    }
    assert picks == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}


def test_long_reach_in_play_is_not_its_own_other_bene_gesserit_card() -> None:
    # "If you have another Bene Gesserit card in play" [Long Reach card]:
    # Long Reach is itself a Bene Gesserit card, so once in play it does not
    # meet its own condition (Slig Farmer counts the grafted Long Reach's
    # icons, OQ-055).
    reach = _card("long_reach")
    card = personal_card_for_instance(reach)
    alone = _owner((), in_play=(reach,))
    assert effective_agent_icons(card, alone, card_instance_id=reach) == ()
    bonded = _owner((), in_play=(reach, _card("planned_coupling")))
    assert len(effective_agent_icons(card, bonded, card_instance_id=reach)) == 3


def test_occupation_draws_and_grants_the_combat_icon() -> None:
    occupation = _card("occupation")
    state = _place(
        _state(_owner((occupation,), troops_garrison=3)), occupation, "arrakeen"
    )
    resolved = resolve_agent_card_effect(state)
    owner = resolved.state.players[0]
    assert len(owner.hand) == 1
    _, context = current_agent_effect_context(resolved.state)
    assert context["pending_combat_deployment"] is True
    revealed = _take_gains(_reveal(_state(_owner((occupation,)))))
    assert revealed.players[0].resources.water == 3
    assert revealed.players[0].troops_garrison == 4


def test_organ_merchants_pays_a_specimen_for_four_solari() -> None:
    merchants = _card("organ_merchants")
    dry = _place(_state(_owner((merchants,))), merchants, "arrakeen")
    assert [a.action_id for a in legal_agent_card_payment_actions(dry, 0)] == [
        "decline_agent_card_payment"
    ]
    wet = _place(
        _state(_owner((merchants,), specimens=1, troops_supply=8)),
        merchants,
        "arrakeen",
    )
    pay = next(
        a
        for a in legal_agent_card_payment_actions(wet, 0)
        if a.action_id == "pay_agent_card_specimen"
    )
    paid = apply_agent_card_payment(wet, pay).state.players[0]
    assert paid.specimens == 0 and paid.troops_supply == 9
    assert paid.resources.solari == 4 + 4


def test_replacement_eyes_advances_when_trashed() -> None:
    eyes = _card("replacement_eyes")
    state = _state(_owner((eyes,)))
    trashed = trash_personal_card(state, 0, eyes, source="test")
    assert trashed.state.players[0].tleilaxu_space == 1


def test_sardaukar_quartermaster_needs_the_graft() -> None:
    quartermaster = _card("sardaukar_quartermaster")
    alone = _place(_state(_owner((quartermaster,))), quartermaster, "arrakeen")
    _, context = current_agent_effect_context(alone)
    assert context["pending_agent_icons"] == "troops,cards"
    # "If grafted: [troop] [card]" [Sardaukar Quartermaster card]: ungrafted,
    # the mandatory icons are not offered to fire and fizzle; they wait for
    # the turn's end and fizzle there (OQ-057 (1)).
    assert legal_agent_card_icon_actions(alone, 0) == ()
    fizzled = fizzle_pending_agent_icons(alone)
    assert [e.kind for e in fizzled.events] == ["agent_card_effect_unavailable"] * 2
    assert fizzled.state.players[0].troops_garrison == 3  # Arrakeen is still pending
    grafted = _graft(
        _state(_owner((quartermaster, FACE_DANCER))),
        quartermaster,
        "arrakeen",
        FACE_DANCER,
    )
    troops = resolve_agent_card_icon(
        grafted,
        DomainAction(
            action_id="resolve_agent_card_effect",
            actor=0,
            arguments=(("effect", "troops"),),
        ),
    )
    assert troops.state.players[0].troops_garrison == 3 + 1


def test_show_of_strength_icons_need_the_deployment_lead() -> None:
    show = _card("show_of_strength")
    behind = _state(
        _owner((show,), troops_conflict=1, troops_supply=8),
        _seat(1, troops_conflict=1, troops_supply=8),
    )
    assert not any(
        dict(a.arguments)["card_id"] == show for a in legal_agent_actions(behind, 0)
    )
    ahead = _state(
        _owner((show,), troops_conflict=2, troops_supply=7),
        _seat(1, troops_conflict=1, troops_supply=8),
    )
    placed = _place(ahead, show, "assembly_hall")
    resolved = resolve_agent_card_effect(placed)
    assert len(resolved.state.players[0].hand) == 2


def test_spiritual_fervor_reveals_a_specimen_and_researches_on_acquisition() -> None:
    fervor = _card("spiritual_fervor")
    revealed = _take_gains(_reveal(_state(_owner((fervor,)))))
    assert revealed.players[0].specimens == 1
    state = _reveal(_state(_owner((DAGGER,))))
    imperium = imperium_deck_instance_ids(False)
    state = replace(state, imperium_row=(fervor, *imperium[1:5]))
    context = dict(state.decision_stack[-1].context)
    context["persuasion"] = 3
    state = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(state.decision_stack[-1], context=tuple(sorted(context.items()))),
        ),
    )
    action = next(
        a
        for a in legal_imperium_acquisitions(state, 0)
        if dict(a.arguments)["instance_id"] == fervor
    )
    acquired = apply_imperium_acquisition(state, action)
    assert acquired.state.players[0].research_space == "c1r3"


CALL_TO_ARMS = "intrigue:call_to_arms:0"


def _fervor_reveal(**owner: object) -> tuple[GameState, str]:
    """A Reveal with 3 Persuasion and Spiritual Fervor in the Row."""

    fervor = _card("spiritual_fervor")
    state = _reveal(_state(_owner((DAGGER,), **owner)))
    imperium = imperium_deck_instance_ids(False)
    state = replace(
        state,
        imperium_row=(fervor, *[card for card in imperium[1:6] if card != fervor][:4]),
    )
    context = dict(state.decision_stack[-1].context)
    context["persuasion"] = 3
    state = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(state.decision_stack[-1], context=tuple(sorted(context.items()))),
        ),
    )
    return state, fervor


def _buy(state: GameState, instance_id: str) -> Transition:
    return UprisingRulesEngine().apply(
        state,
        DomainAction(
            action_id="acquire_imperium",
            actor=0,
            arguments=(("instance_id", instance_id),),
        ),
    )


def _research(state: GameState, space_id: str) -> Transition:
    return UprisingRulesEngine().apply(
        state,
        DomainAction(
            action_id="choose_research_space",
            actor=0,
            arguments=(("space_id", space_id),),
        ),
    )


def test_call_to_arms_waits_for_spiritual_fervor_s_research_direction() -> None:
    # OQ-012: "획득한 카드 자신의 acquire 보상 → … → face-up trigger
    # Intrigue(Call to Arms의 troop recruit)", kept when the card's own
    # acquisition effect opens a choice (user ruling 2026-10-04, "선택 뒤로
    # 맞춤"). Spiritual Fervor's acquire box researches; from c1r3 the token
    # may go to c2r2 (specimen) or c2r4 (Tleilaxu). With one troop left in
    # the supply the specimen takes it, and Call to Arms' troop is short.
    # It used to be recruited before the choice, leaving the specimen short.
    state, fervor = _fervor_reveal(
        research_space="c1r3",
        intrigue_faceup=(CALL_TO_ARMS,),
        troops_supply=1,
        troops_garrison=11,
    )

    bought = _buy(state, fervor)
    assert [event.kind for event in bought.events] == ["card_acquired"]
    assert bought.state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE
    owner = bought.state.players[0]
    assert (owner.troops_supply, owner.troops_garrison) == (1, 11)

    chosen = _research(bought.state, "c2r2")
    assert [event.kind for event in chosen.events] == [
        "research_advanced",
        "specimens_generated",
        "intrigue_triggered",
        "troops_recruit_short",
    ]
    owner = chosen.state.players[0]
    assert owner.specimens == 1 and owner.ungained_specimens == 0
    assert owner.troops_supply == 0 and owner.troops_garrison == 11
    # The short troop waits for troops to come back this turn (OQ-030,
    # user ruling 2026-10-04).
    assert owner.ungained_troops == 1
    triggered = chosen.events[2]
    assert dict(triggered.payload)["troops"] == 0
    reveal = chosen.state.decision_stack[-1]
    assert reveal.kind == FrameKind.REVEAL
    assert dict(reveal.context)["reveal_troops_recruited"] == 0
    assert "deferred_acquisition_triggers" not in dict(reveal.context)


def test_call_to_arms_follows_spiritual_fervor_s_research_with_troops_left() -> (
    None
):
    state, fervor = _fervor_reveal(
        research_space="c1r3", intrigue_faceup=(CALL_TO_ARMS,)
    )
    supply = state.players[0].troops_supply
    garrison = state.players[0].troops_garrison

    bought = _buy(state, fervor)
    assert "intrigue_triggered" not in [event.kind for event in bought.events]
    assert bought.state.players[0].troops_garrison == garrison

    chosen = _research(bought.state, "c2r2")
    assert [event.kind for event in chosen.events] == [
        "research_advanced",
        "specimens_generated",
        "intrigue_triggered",
    ]
    triggered = chosen.events[-1]
    # The event an acquisition without a frame emits.
    assert triggered.event_id == (
        f"round:1:player:0:acquire:{fervor}:reveal_trigger:{CALL_TO_ARMS}"
    )
    assert dict(triggered.payload)["troops"] == 1
    owner = chosen.state.players[0]
    assert owner.specimens == 1 and owner.troops_garrison == garrison + 1
    assert owner.troops_supply == supply - 2
    context = dict(chosen.state.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 1
    assert "deferred_acquisition_triggers" not in context


def test_call_to_arms_waits_for_spiritual_fervor_s_research_draw_reshuffle() -> (
    None
):
    # Past the second genetic marker the Research icon draws a card instead
    # [Immortality p. 6]. With a card in the deck the draw, its reveal and
    # then Call to Arms all land in the acquisition; with an empty deck the
    # reshuffle is a chance frame the card's own effect opened, so Call to
    # Arms waits for it and keeps the same order (OQ-012, user ruling
    # 2026-10-04).
    others = tuple(card for card in STARTERS if card != DAGGER)
    state, fervor = _fervor_reveal(
        research_space="c8r2", intrigue_faceup=(CALL_TO_ARMS,), deck=others[:3]
    )
    assert [event.kind for event in _buy(state, fervor).events] == [
        "card_acquired",
        "research_drew_card",
        "personal_card_late_revealed",
        "intrigue_triggered",
    ]

    state, fervor = _fervor_reveal(
        research_space="c8r2",
        intrigue_faceup=(CALL_TO_ARMS,),
        deck=(),
        discard_pile=others[:3],
    )
    garrison = state.players[0].troops_garrison
    bought = _buy(state, fervor)
    assert [event.kind for event in bought.events] == [
        "card_acquired",
        "research_drew_card",
    ]
    frame = bought.state.decision_stack[-1]
    assert isinstance(frame.decision, ChanceDecision)
    shuffled = UprisingRulesEngine().apply(
        bought.state, ChanceResolver(seed=3).resolve(frame.decision)
    )
    assert [event.kind for event in shuffled.events] == [
        "personal_discard_shuffled",
        "personal_card_late_revealed",
        "intrigue_triggered",
    ]
    assert shuffled.state.players[0].troops_garrison == garrison + 1
    assert shuffled.state.decision_stack[-1].kind == FrameKind.REVEAL


def test_spiritual_fervor_s_single_research_step_keeps_call_to_arms_in_place() -> (
    None
):
    # From the start space the token has one way to go, so no frame opens and
    # Call to Arms fires inside the acquisition, after the research, as before.
    state, fervor = _fervor_reveal(intrigue_faceup=(CALL_TO_ARMS,))
    garrison = state.players[0].troops_garrison

    bought = _buy(state, fervor)
    kinds = [event.kind for event in bought.events]
    assert kinds[0] == "card_acquired" and kinds[-1] == "intrigue_triggered"
    assert kinds.index("research_advanced") < kinds.index("intrigue_triggered")
    assert bought.state.players[0].research_space == "c1r3"
    assert bought.state.players[0].troops_garrison == garrison + 1
    assert bought.state.decision_stack[-1].kind == FrameKind.REVEAL


def test_call_to_arms_comes_before_the_choice_of_a_card_fervor_s_research_drew() -> (
    None
):
    # Past the second genetic marker Spiritual Fervor's Research draws a card
    # [Immortality p. 6], and the drawn Corrinth City is revealed with its
    # own Reveal choice. That choice belongs to Corrinth City, not to the
    # acquired card: Call to Arms waits only for the acquired card's own
    # effects and the decisions they open (OQ-012, user ruling 2026-10-04,
    # "선택 뒤로 맞춤"), so its troop comes after the research and before
    # Corrinth City's choice.
    corrinth = _card("corrinth_city")
    state, fervor = _fervor_reveal(
        research_space="c8r2", intrigue_faceup=(CALL_TO_ARMS,), deck=(corrinth,)
    )
    garrison = state.players[0].troops_garrison

    bought = _buy(state, fervor)
    assert [event.kind for event in bought.events] == [
        "card_acquired",
        "research_drew_card",
        "personal_card_late_revealed",
        "intrigue_triggered",
    ]
    assert bought.events[-1].event_id == (
        f"round:1:player:0:acquire:{fervor}:reveal_trigger:{CALL_TO_ARMS}"
    )
    assert bought.state.players[0].troops_garrison == garrison + 1
    top = bought.state.decision_stack[-1]
    assert top.kind == FrameKind.REVEAL_CHOICE
    assert dict(top.context)["reveal_card_id"] == corrinth
    reveal = bought.state.decision_stack[-2]
    assert reveal.kind == FrameKind.REVEAL
    assert dict(reveal.context)["reveal_troops_recruited"] == 1
    assert "deferred_acquisition_triggers" not in dict(reveal.context)


def test_call_to_arms_waits_for_an_inspire_awe_fervor_s_research_direction() -> None:
    # Inspire Awe takes Spiritual Fervor: its Research direction opens inside
    # the Intrigue card's acquisition slot, above the Intrigue choice frame,
    # and is still open once the Intrigue card has resolved. Call to Arms
    # waits for it as on the Row (OQ-012, user ruling 2026-10-04).
    awe = "intrigue:inspire_awe:0"
    state, fervor = _fervor_reveal(
        research_space="c1r3", intrigue_faceup=(CALL_TO_ARMS,), intrigue_cards=(awe,)
    )
    garrison = state.players[0].troops_garrison
    engine = UprisingRulesEngine()
    opened = engine.apply(
        state,
        DomainAction(
            action_id="play_intrigue",
            actor=0,
            arguments=(("card_id", awe), ("option", 0)),
        ),
    ).state
    acquire = next(
        action
        for action in engine.legal_actions(opened, 0)
        if dict(action.arguments).get("instance_id") == fervor
    )

    acquired = engine.apply(opened, acquire)
    assert [event.kind for event in acquired.events] == ["card_acquired"]
    assert [frame.kind for frame in acquired.state.decision_stack] == [
        FrameKind.REVEAL,
        FrameKind.RESEARCH_ADVANCE,
    ]
    assert awe in acquired.state.intrigue_discard
    assert acquired.state.players[0].troops_garrison == garrison

    chosen = _research(acquired.state, "c2r2")
    assert [event.kind for event in chosen.events] == [
        "research_advanced",
        "specimens_generated",
        "intrigue_triggered",
    ]
    assert chosen.events[-1].event_id == (
        f"round:1:player:0:intrigue:{awe}:slot:0:reveal_trigger:{CALL_TO_ARMS}"
    )
    assert chosen.state.players[0].troops_garrison == garrison + 1
    reveal = chosen.state.decision_stack[-1]
    assert reveal.kind == FrameKind.REVEAL
    assert dict(reveal.context)["reveal_troops_recruited"] == 1
    assert "deferred_acquisition_triggers" not in dict(reveal.context)


def _icon_keys(state: GameState) -> set[str]:
    return {
        str(dict(action.arguments)["effect"])
        for action in legal_agent_card_icon_actions(state, 0)
    }


def _icon(state: GameState, key: str) -> DomainAction:
    return DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("effect", key),)
    )


def test_stillsuit_manufacturer_returns_with_the_fremen_alliance() -> None:
    # "[water] —AND— [Fremen] Alliance: Return this card from play to your
    # hand." [Stillsuit Manufacturer card]: two icons (OQ-027), the return
    # judged when it resolves (OQ-028).
    stillsuit = _card("stillsuit_manufacturer")
    placed = _place(_state(_owner((stillsuit,))), stillsuit, "arrakeen")
    assert dict(placed.decision_stack[-1].context)["pending_agent_icons"] == (
        "water,return_self"
    )
    assert _icon_keys(placed) == {"water"}
    plain = resolve_agent_card_icon(placed, _icon(placed, "water"))
    owner = plain.state.players[0]
    assert owner.resources.water == 3 and stillsuit in owner.in_play

    allied_state = _place(
        _state(_owner((stillsuit,), alliance_faction_ids=("fremen",))),
        stillsuit,
        "arrakeen",
    )
    assert _icon_keys(allied_state) == {"water", "return_self"}
    returned = resolve_agent_card_icon(allied_state, _icon(allied_state, "return_self"))
    owner = returned.state.players[0]
    assert stillsuit in owner.hand and stillsuit in owner.hand_public
    assert stillsuit not in owner.in_play
    # Back in hand by its own icon: the water still pays out.
    allied = resolve_agent_card_icon(returned.state, _icon(returned.state, "water"))
    assert allied.state.players[0].resources.water == 3
    bonded = _take_gains(_reveal(_state(_owner((stillsuit, _card("lisan_al_gaib"))))))
    assert bonded.players[0].resources.spice == 2 + 2


def test_stillsuit_manufacturer_return_waits_for_a_later_fremen_alliance() -> None:
    # Water first, then the visit's Fremen Influence reaches four and takes
    # the Alliance: the waiting return is offered, and it is mandatory then
    # (OQ-057 (1)).
    stillsuit = _card("stillsuit_manufacturer")
    owner = _owner((stillsuit,), influence=Influence(fremen=3))
    placed = _place(_state(owner), stillsuit, "fremkit")
    watered = resolve_agent_card_icon(placed, _icon(placed, "water")).state
    assert _icon_keys(watered) == set()
    assert agent_card_effect_is_unavailable(watered)

    allied = resolve_faction_influence(watered).state
    assert "fremen" in allied.players[0].alliance_faction_ids
    assert _icon_keys(allied) == {"return_self"}
    engine = UprisingRulesEngine()
    assert DomainAction("finish_agent_turn", 0) not in engine.legal_actions(allied, 0)

    returned = resolve_agent_card_icon(allied, _icon(allied, "return_self")).state
    assert stillsuit in returned.players[0].hand
    assert stillsuit not in returned.players[0].in_play
    assert returned.players[0].resources == allied.players[0].resources


def test_stillsuit_manufacturer_return_lapses_without_the_alliance() -> None:
    stillsuit = _card("stillsuit_manufacturer")
    placed = _place(_state(_owner((stillsuit,))), stillsuit, "arrakeen")
    watered = resolve_agent_card_icon(placed, _icon(placed, "water")).state
    engine = UprisingRulesEngine()
    finish = DomainAction("finish_agent_turn", 0)
    while finish not in (legal := engine.legal_actions(watered, 0)):
        watered = engine.apply(
            watered,
            next(a for a in legal if not a.action_id.startswith("deploy")),
        ).state

    closed = engine.apply(watered, finish)

    assert [
        dict(event.payload)["effect"]
        for event in closed.events
        if event.kind == "agent_card_effect_unavailable"
    ] == ["return_self"]
    owner = closed.state.players[0]
    assert stillsuit in owner.in_play and stillsuit not in owner.hand


def test_throne_room_politics_recruits_then_offers_a_trash() -> None:
    throne = _card("throne_room_politics")
    resolved = resolve_agent_card_effect(
        _place(_state(_owner((throne,))), throne, "dutiful_service")
    )
    assert resolved.state.players[0].troops_garrison == 4
    assert resolved.state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    revealed = _take_gains(_reveal(_state(_owner((throne,)))))
    assert revealed.players[0].influence.bene_gesserit == 1


def test_the_codec_holds_the_new_choices() -> None:
    codec = ActionCodec(IMMORTALITY)
    merchants = _card("organ_merchants")
    wet = _place(
        _state(_owner((merchants,), specimens=1, troops_supply=8)),
        merchants,
        "arrakeen",
    )
    for action in legal_agent_card_payment_actions(wet, 0):
        assert codec.decode(codec.encode(action), 0) == action
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    assert "pay_agent_card_specimen" not in base
