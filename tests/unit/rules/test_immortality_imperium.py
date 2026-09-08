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
from dune_imperium.rules.acquisition import (
    apply_imperium_acquisition,
    legal_imperium_acquisitions,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_influence,
    apply_agent_card_payment,
    legal_agent_card_influence_actions,
    legal_agent_card_payment_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
)
from dune_imperium.rules.agent_icons import effective_agent_icons
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import current_agent_effect_context
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
    troops = resolve_agent_card_icon(
        alone,
        DomainAction(
            action_id="resolve_agent_card_effect",
            actor=0,
            arguments=(("effect", "troops"),),
        ),
    )
    assert troops.state.players[0].troops_garrison == 3  # Arrakeen is still pending
    assert troops.events[-1].kind == "agent_card_effect_unavailable"
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


def test_stillsuit_manufacturer_returns_with_the_fremen_alliance() -> None:
    stillsuit = _card("stillsuit_manufacturer")
    plain = resolve_agent_card_effect(
        _place(_state(_owner((stillsuit,))), stillsuit, "arrakeen")
    )
    owner = plain.state.players[0]
    assert owner.resources.water == 3 and stillsuit in owner.in_play
    allied = resolve_agent_card_effect(
        _place(
            _state(_owner((stillsuit,), alliance_faction_ids=("fremen",))),
            stillsuit,
            "arrakeen",
        )
    )
    owner = allied.state.players[0]
    assert stillsuit in owner.hand and stillsuit in owner.hand_public
    bonded = _take_gains(_reveal(_state(_owner((stillsuit, _card("lisan_al_gaib"))))))
    assert bonded.players[0].resources.spice == 2 + 2


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
