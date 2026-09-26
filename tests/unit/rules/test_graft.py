"""Tests for Graft: two-card Agent turns [Immortality pp. 10-11, 14].

Rule source: ``docs/rules/immortality.md`` section 5 and the card faces of
Face Dancer, Face Dancer Initiate, Corrino Genes, Unnatural Reflexes,
Tleilaxu Infiltrator, Twisted Mentat, Bene Tleilax Researcher, and Planned
Coupling.
"""

from dataclasses import replace

import pytest

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
from dune_imperium.rules.agent_effect_frame import legal_agent_effect_frame_actions
from dune_imperium.rules.agent_effects import (
    agent_card_effect_is_unavailable,
    apply_agent_card_recall,
    fizzle_pending_agent_icons,
    legal_agent_card_icon_actions,
    legal_agent_card_recall_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft import (
    apply_graft_partner,
    apply_graft_switch,
    legal_graft_partner_actions,
    legal_graft_switch_actions,
)
from dune_imperium.rules.leader_abilities import (
    apply_leader_agent_deploy,
    legal_leader_signet_actions,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.simulation.sweep import run_checked_game

IMMORTALITY = RulesetConfig(immortality=True)
FACE_DANCER = "tleilaxu:face_dancer:0"
INITIATE = "tleilaxu:face_dancer_initiate:0"
CORRINO_GENES = "tleilaxu:corrino_genes:0"
REFLEXES = "tleilaxu:unnatural_reflexes:0"
INFILTRATOR = "tleilaxu:tleilaxu_infiltrator:0"
MENTAT = "tleilaxu:twisted_mentat:0"
RESEARCHER = "imperium:bene_tleilax_researcher:0"
STARTERS = starting_deck_instance_ids(0, immortality=True)
DAGGER = next(card for card in STARTERS if "dagger:0" in card)
DIPLOMACY = next(card for card in STARTERS if "diplomacy" in card)
SIGNET = next(card for card in STARTERS if "signet_ring" in card)


def _owner(hand: tuple[str, ...], **overrides: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "hand": hand,
        "deck": tuple(card for card in STARTERS if card not in hand),
        "resources": Resources(solari=4, spice=2, water=2),
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _state(owner: PlayerState, **overrides: object) -> GameState:
    imperium = imperium_deck_instance_ids(False)
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
        "players": (
            owner,
            *(
                PlayerState(
                    player_id=seat,
                    research_space=RESEARCH_START_ID,
                    family_atomics=True,
                )
                for seat in range(1, 4)
            ),
        ),
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


def _placements(state: GameState) -> dict[tuple[str, str, bool], DomainAction]:
    keyed: dict[tuple[str, str, bool], DomainAction] = {}
    for action in legal_agent_actions(state, 0):
        arguments = dict(action.arguments)
        if "infiltrate_post_id" in arguments:
            continue
        keyed[
            (
                str(arguments["card_id"]),
                str(arguments["space_id"]),
                arguments.get("graft") is True,
            )
        ] = action
    return keyed


def _partners(state: GameState) -> dict[str, DomainAction]:
    return {
        str(dict(action.arguments)["card_id"]): action
        for action in legal_graft_partner_actions(state, 0)
    }


def _graft(state: GameState, card_id: str, space_id: str, partner_id: str) -> GameState:
    placed = apply_agent_action(state, _placements(state)[(card_id, space_id, True)])
    return apply_graft_partner(placed.state, _partners(placed.state)[partner_id]).state


def test_a_graft_card_cannot_be_played_alone() -> None:
    state = _state(_owner((FACE_DANCER, DAGGER)))
    placements = _placements(state)
    assert (FACE_DANCER, "dutiful_service", False) not in placements
    assert (FACE_DANCER, "dutiful_service", True) in placements
    # The plain card may be played alone or grafted to the Graft card.
    assert (DAGGER, "assembly_hall", False) in placements
    assert (DAGGER, "assembly_hall", True) in placements
    # Two plain cards never graft.
    plain = _placements(_state(_owner((DAGGER, DIPLOMACY))))
    assert not any(graft for _, _, graft in plain)
    # A lone Graft card has no play at all.
    assert _placements(_state(_owner((FACE_DANCER,)))) == {}


def test_the_partner_is_chosen_after_the_placement_and_joins_play() -> None:
    state = _state(_owner((FACE_DANCER, DAGGER, DIPLOMACY)))
    placed = apply_agent_action(
        state, _placements(state)[(DAGGER, "assembly_hall", True)]
    )
    assert placed.state.decision_stack[-1].kind == FrameKind.GRAFT_PARTNER
    # Diplomacy is not a Graft card, so it cannot partner Dagger.
    assert set(_partners(placed.state)) == {FACE_DANCER}

    grafted = apply_graft_partner(placed.state, _partners(placed.state)[FACE_DANCER])
    owner = grafted.state.players[0]
    assert set(owner.in_play) == {DAGGER, FACE_DANCER}
    assert owner.hand == (DIPLOMACY,)
    _, context = current_agent_effect_context(grafted.state)
    assert context["card_id"] == DAGGER
    assert context["graft_card_id"] == FACE_DANCER
    assert context["graft_pending_effect"] is True
    assert grafted.events[0].kind == "card_grafted"


def test_either_card_may_provide_the_icon() -> None:
    # Dagger has only the Landsraad icon; grafted, Face Dancer's Faction
    # icons open Dutiful Service for the pair.
    state = _state(_owner((FACE_DANCER, DAGGER)))
    assert (FACE_DANCER, "dutiful_service", True) in _placements(state)
    grafted = _graft(state, FACE_DANCER, "dutiful_service", DAGGER)
    assert "dutiful_service" in grafted.players[0].agent_locations


def test_the_partners_box_resolves_after_a_switch_in_the_owners_order() -> None:
    state = _state(_owner((FACE_DANCER, DAGGER)))
    grafted = _graft(state, DAGGER, "assembly_hall", FACE_DANCER)
    switch = legal_graft_switch_actions(grafted, 0)
    assert [action.action_id for action in switch] == ["switch_graft_card"]
    assert any(
        action.action_id == "switch_graft_card"
        for action in legal_agent_effect_frame_actions(grafted, 0)
    )
    switched = apply_graft_switch(grafted, switch[0]).state
    _, context = current_agent_effect_context(switched)
    assert context["card_id"] == FACE_DANCER
    assert context["graft_card_id"] == DAGGER
    assert context["pending_agent_effect"] is True
    assert context["graft_pending_effect"] is False
    assert legal_graft_switch_actions(switched, 0) == ()

    hand_before = len(switched.players[0].hand)
    drawn = resolve_agent_card_effect(switched)
    assert len(drawn.state.players[0].hand) == hand_before + 1


def test_corrino_genes_advances_only_when_grafted() -> None:
    alone = _state(_owner((CORRINO_GENES, DAGGER)))
    placed = apply_agent_action(
        alone, _placements(alone)[(CORRINO_GENES, "dutiful_service", False)]
    )
    resolved = resolve_agent_card_effect(placed.state)
    assert resolved.state.players[0].tleilaxu_space == 0
    assert resolved.events[0].kind == "agent_card_effect_unavailable"

    grafted = _graft(
        _state(_owner((CORRINO_GENES, FACE_DANCER))),
        CORRINO_GENES,
        "dutiful_service",
        FACE_DANCER,
    )
    resolved = resolve_agent_card_effect(grafted)
    assert resolved.state.players[0].tleilaxu_space == 1


def test_unnatural_reflexes_draws_two_at_the_first_marker() -> None:
    marked = _graft(
        _state(_owner((REFLEXES, DAGGER), research_space="c4r4")),
        REFLEXES,
        "hagga_basin",
        DAGGER,
    )
    hand_before = len(marked.players[0].hand)
    drawn = resolve_agent_card_effect(marked)
    assert len(drawn.state.players[0].hand) == hand_before + 2
    unmarked = _graft(
        _state(_owner((REFLEXES, DAGGER))), REFLEXES, "hagga_basin", DAGGER
    )
    unresolved = resolve_agent_card_effect(unmarked)
    assert len(unresolved.state.players[0].hand) == len(unmarked.players[0].hand)


def test_tleilaxu_infiltrator_enters_an_occupied_space_and_draws() -> None:
    blocker = PlayerState(
        player_id=1,
        research_space=RESEARCH_START_ID,
        family_atomics=True,
        agents_available=1,
        agent_locations=("arrakeen",),
    )
    state = _state(_owner((INFILTRATOR, DAGGER)))
    state = replace(state, players=(state.players[0], blocker, *state.players[2:]))
    placements = _placements(state)
    assert (DAGGER, "arrakeen", False) not in placements
    assert (INFILTRATOR, "arrakeen", True) in placements
    assert (DAGGER, "arrakeen", True) not in placements  # Dagger has no City icon
    grafted = _graft(state, INFILTRATOR, "arrakeen", DAGGER)
    _, context = current_agent_effect_context(grafted)
    assert context["pending_agent_icons"] == "cards,intrigue"
    hand_before = len(grafted.players[0].hand)
    drawn = resolve_agent_card_icon(
        grafted,
        DomainAction(
            action_id="resolve_agent_card_effect",
            actor=0,
            arguments=(("effect", "cards"),),
        ),
    )
    assert len(drawn.state.players[0].hand) == hand_before + 1
    # "[card] -AND- [2 genetic markers]: [Intrigue]" [Tleilaxu Infiltrator
    # card]: without both markers the mandatory Intrigue icon is not offered
    # to fire and fizzle; it waits for the turn's end and fizzles there
    # (OQ-057 (1)).
    assert legal_agent_card_icon_actions(drawn.state, 0) == ()
    assert agent_card_effect_is_unavailable(drawn.state)
    intrigue = fizzle_pending_agent_icons(drawn.state)
    assert [dict(e.payload)["effect"] for e in intrigue.events] == ["intrigue"]
    assert intrigue.state.players[0].intrigue_cards == ()


def test_an_occupied_space_needs_the_infiltrator_as_a_partner() -> None:
    blocker = PlayerState(
        player_id=1,
        research_space=RESEARCH_START_ID,
        family_atomics=True,
        agents_available=1,
        agent_locations=("assembly_hall",),
    )
    state = _state(_owner((INFILTRATOR, FACE_DANCER, DAGGER)))
    state = replace(state, players=(state.players[0], blocker, *state.players[2:]))
    placed = apply_agent_action(
        state, _placements(state)[(DAGGER, "assembly_hall", True)]
    )
    assert set(_partners(placed.state)) == {INFILTRATOR}


def test_an_occupied_space_is_not_offered_on_two_different_promises() -> None:
    # Long Reach's icons are Bene Gesserit Bond icons: in hand they switch on
    # only on the promise that Ghola will be the partner (OQ-057). An occupied
    # space is entered on the promise that Tleilaxu Infiltrator will be the
    # partner. A turn plays two cards only [Immortality p. 10], so one
    # partner cannot keep both promises and the placement is not offered;
    # offering it left the partner choice with no legal action (2026-09-16
    # all-expansion baseline, game seed 42).
    long_reach = "imperium:long_reach:0"
    ghola = "tleilaxu:ghola:0"
    blocker = PlayerState(
        player_id=1,
        research_space=RESEARCH_START_ID,
        family_atomics=True,
        agents_available=1,
        agent_locations=("arrakeen",),
    )
    open_state = _state(_owner((long_reach, ghola, INFILTRATOR)))
    blocked = replace(
        open_state, players=(open_state.players[0], blocker, *open_state.players[2:])
    )

    # Unoccupied: Long Reach enters on Ghola's promise and Ghola is the partner.
    assert (long_reach, "arrakeen", True) in _placements(open_state)
    placed = apply_agent_action(
        open_state, _placements(open_state)[(long_reach, "arrakeen", True)]
    )
    assert set(_partners(placed.state)) == {ghola}
    # Occupied: the two promises need two different partners, so no offer;
    # the Infiltrator itself still enters on its own City icon.
    blocked_placements = _placements(blocked)
    assert (long_reach, "arrakeen", True) not in blocked_placements
    assert (INFILTRATOR, "arrakeen", True) in blocked_placements


def test_twisted_mentat_may_recall_the_agent_sent_this_turn() -> None:
    state = _state(
        _owner((MENTAT, DAGGER), agent_locations=("arrakeen",), agents_available=1)
    )
    grafted = _graft(state, MENTAT, "assembly_hall", DAGGER)
    actions = legal_agent_card_recall_actions(grafted, 0)
    assert {action.action_id for action in actions} == {
        "decline_agent_card_recall",
        "recall_agent_for_agent_card",
    }
    assert {
        dict(action.arguments).get("space_id")
        for action in actions
        if action.action_id == "recall_agent_for_agent_card"
    } == {"assembly_hall"}
    recalled = apply_agent_card_recall(
        grafted,
        next(a for a in actions if a.action_id == "recall_agent_for_agent_card"),
    )
    owner = recalled.state.players[0]
    assert owner.agent_locations == ("arrakeen",)
    assert owner.agents_available == 1
    declined = apply_agent_card_recall(grafted, actions[0])
    assert "assembly_hall" in declined.state.players[0].agent_locations


def test_imperial_privilege_recalls_the_fray_agent_after_a_mentat_recall() -> None:
    # Twisted Mentat: "You may recall the Agent you sent this turn."
    # [Twisted Mentat card]. Imperial Privilege: "Recall one of your other
    # Agents from the board, and draw a card." [Board Guide p. 2]; OQ-037
    # (d): an Into the Fray Agent in the Conflict is still "자신의 Agent" and
    # may be recalled "뒤의 turn에" (on a later turn). Once the Mentat has
    # sent this turn's Agent home, the Agent Duncan sent Into the Fray on an
    # earlier turn is an "other" Agent. The Conflict count used to take this
    # turn's Agent off the space as Into the Fray's and hid that Agent, so
    # the recall was skipped.
    from dune_imperium.rules.board_effects import (
        apply_imperial_privilege_action,
        legal_imperial_privilege_actions,
    )

    config = RulesetConfig(immortality=True, bloodlines=True)
    state = _state(
        _owner(
            (MENTAT, DAGGER),
            leader_id="duncan_idaho",
            influence=Influence(emperor=2),
            agents_available=1,
            agent_in_conflict=1,
        ),
        config=config,
    )
    grafted = _graft(state, MENTAT, "imperial_privilege", DAGGER)
    mentat_recall = next(
        action
        for action in legal_agent_card_recall_actions(grafted, 0)
        if action.action_id == "recall_agent_for_agent_card"
    )
    home = apply_agent_card_recall(grafted, mentat_recall).state
    assert home.players[0].agent_locations == ()
    assert home.players[0].agents_available == 1
    decline = next(
        action
        for action in legal_imperial_privilege_actions(home, 0)
        if action.action_id == "decline_imperial_privilege_intrigue"
    )
    declined = apply_imperial_privilege_action(home, decline)
    assert "imperial_privilege_recall_skipped" not in {
        event.kind for event in declined.events
    }

    recalls = legal_imperial_privilege_actions(declined.state, 0)
    assert [action.action_id for action in recalls] == [
        "recall_conflict_agent_for_imperial_privilege"
    ]
    hand_before = len(declined.state.players[0].hand)
    seat = apply_imperial_privilege_action(declined.state, recalls[0]).state.players[0]
    assert seat.agent_in_conflict == 0
    assert seat.agents_available == 2
    assert len(seat.hand) == hand_before + 1


def test_twisted_mentat_recalls_this_turns_agent_from_the_conflict() -> None:
    # Twisted Mentat: "You may recall the Agent you sent this turn."
    # [Twisted Mentat card]. Into the Fray (Duncan Idaho) may move that very
    # Agent into the Conflict before the Mentat's own box resolves, where it
    # is still "the Agent you sent this turn" (2026-09-26 user ruling,
    # OQ-068): the Mentat's recall follows it there.
    config = RulesetConfig(immortality=True, bloodlines=True)
    state = _state(
        _owner(
            (MENTAT, SIGNET),
            leader_id="duncan_idaho",
            influence=Influence(emperor=2),
            agents_available=2,
        ),
        config=config,
    )
    grafted = _graft(state, MENTAT, "assembly_hall", SIGNET)
    # The Mentat's box is active first; switch to the Signet's box for Into
    # the Fray (OQ-027 lets the owner order a multi-box turn).
    switched = apply_graft_switch(
        grafted, next(iter(legal_graft_switch_actions(grafted, 0)))
    ).state
    deploy = next(
        action
        for action in legal_leader_signet_actions(switched, 0)
        if action.action_id == "deploy_leader_agent"
    )
    deployed = apply_leader_agent_deploy(switched, deploy).state
    assert deployed.players[0].agent_locations == ()
    assert deployed.players[0].agent_in_conflict == 1

    # Switch back to the Mentat's still-pending box.
    fighting = apply_graft_switch(
        deployed, next(iter(legal_graft_switch_actions(deployed, 0)))
    ).state
    actions = legal_agent_card_recall_actions(fighting, 0)
    assert {action.action_id for action in actions} == {
        "decline_agent_card_recall",
        "recall_conflict_agent_for_agent_card",
    }

    recalled = apply_agent_card_recall(
        fighting,
        next(
            action
            for action in actions
            if action.action_id == "recall_conflict_agent_for_agent_card"
        ),
    )
    owner = recalled.state.players[0]
    assert owner.agent_in_conflict == 0
    assert owner.agents_available == 2
    assert owner.agent_locations == ()
    recalled_event = next(
        event for event in recalled.events if event.kind == "agent_recalled"
    )
    assert dict(recalled_event.payload)["space_id"] == "conflict"

    # Imperial Privilege then treats every remaining Conflict Agent as an
    # earlier turn's, exactly as after a board recall (OQ-037 (d)).
    assert dict(recalled.state.decision_stack[-1].context)["turn_agent_recalled"] is (
        True
    )


def test_sardaukar_ii_never_recalls_this_turns_into_the_fray_agent() -> None:
    # User ruling (2026-09-26, verbatim): "Duncan Idaho(Bloodlines) Into the
    # Fray의 Agent를 Imperial Privilege로 recall 가능 이니까 recall agent
    # 기능으로 되는건 모두 같게 동작해야지. 사다우카 계약 완료보상이나 원로회
    # 계약 완료보상에 있는 recall agent도 마찬가지겠지" (OQ-068): Sardaukar
    # II's "recall one of your Agents" [Main p. 20] excludes the Agent sent
    # this turn exactly like Imperial Privilege (OQ-037 (d)). With an earlier
    # turn's Into the Fray Agent also in the Conflict, the reward recalls
    # that one and never this turn's -- which stays in the Conflict.
    from dune_imperium.rules.contracts import (
        apply_contract_completion,
        apply_contract_recall_action,
        legal_contract_completion_actions,
        legal_contract_recall_actions,
    )

    config = RulesetConfig(immortality=True, bloodlines=True, choam_module=True)
    state = _state(
        _owner(
            (FACE_DANCER, SIGNET),
            leader_id="duncan_idaho",
            influence=Influence(emperor=2),
            resources=Resources(solari=4, spice=4, water=2),
            agents_available=1,
            agent_in_conflict=1,
            active_contract_ids=("contract:sardaukar_ii",),
        ),
        config=config,
    )
    # Face Dancer has the Emperor icon Sardaukar needs; the Signet Ring is
    # its Graft partner, sending Into the Fray this same turn -- joining the
    # earlier turn's Agent already in the Conflict (OQ-037 (e)).
    grafted = _graft(state, FACE_DANCER, "sardaukar", SIGNET)
    switched = apply_graft_switch(
        grafted, next(iter(legal_graft_switch_actions(grafted, 0)))
    ).state
    deploy = next(
        action
        for action in legal_leader_signet_actions(switched, 0)
        if action.action_id == "deploy_leader_agent"
    )
    fighting = apply_leader_agent_deploy(switched, deploy).state
    assert fighting.players[0].agent_locations == ()
    assert fighting.players[0].agent_in_conflict == 2

    completion = next(
        action
        for action in legal_contract_completion_actions(fighting, 0)
        if dict(action.arguments)["instance_id"] == "contract:sardaukar_ii"
    )
    completed = apply_contract_completion(fighting, completion)

    # The reward no longer fizzles: the earlier turn's Conflict Agent is
    # recallable, even though there is no board Agent at all (OQ-068).
    assert not any(
        event.kind == "contract_recall_unavailable" for event in completed.events
    )
    recalls = legal_contract_recall_actions(completed.state, 0)
    assert [action.action_id for action in recalls] == [
        "recall_conflict_agent_for_contract"
    ]
    resolved = apply_contract_recall_action(completed.state, recalls[0]).state
    seat = resolved.players[0]
    # One Agent came home -- the earlier turn's, never this turn's, which
    # stays in the Conflict (OQ-037 (d)).
    assert seat.agent_in_conflict == 1
    assert seat.agents_available == 1


def test_sardaukar_ii_reward_still_fizzles_with_no_earlier_conflict_agent() -> None:
    # Review round 1 major finding: with no board Agent and no earlier
    # turn's Conflict Agent, Sardaukar II's "recall one of your Agents"
    # [Main p. 20] must still fizzle -- it is never this turn's own Agent,
    # even though Into the Fray moved it to the Conflict (OQ-037 (d),
    # extended to every Recall Agent effect by the 2026-09-26 user ruling,
    # OQ-068). Unlike
    # test_sardaukar_ii_never_recalls_this_turns_into_the_fray_agent, there
    # is no earlier turn's Conflict Agent here, so the reward has nothing at
    # all to recall.
    from dune_imperium.rules.contracts import (
        apply_contract_completion,
        legal_contract_completion_actions,
        legal_contract_recall_actions,
    )

    config = RulesetConfig(immortality=True, bloodlines=True, choam_module=True)
    state = _state(
        _owner(
            (FACE_DANCER, SIGNET),
            leader_id="duncan_idaho",
            influence=Influence(emperor=2),
            resources=Resources(solari=4, spice=4, water=2),
            agents_available=2,
            agent_in_conflict=0,
            active_contract_ids=("contract:sardaukar_ii",),
        ),
        config=config,
    )
    grafted = _graft(state, FACE_DANCER, "sardaukar", SIGNET)
    switched = apply_graft_switch(
        grafted, next(iter(legal_graft_switch_actions(grafted, 0)))
    ).state
    deploy = next(
        action
        for action in legal_leader_signet_actions(switched, 0)
        if action.action_id == "deploy_leader_agent"
    )
    fighting = apply_leader_agent_deploy(switched, deploy).state
    assert fighting.players[0].agent_locations == ()
    assert fighting.players[0].agent_in_conflict == 1

    completion = next(
        action
        for action in legal_contract_completion_actions(fighting, 0)
        if dict(action.arguments)["instance_id"] == "contract:sardaukar_ii"
    )
    completed = apply_contract_completion(fighting, completion)

    assert any(
        event.kind == "contract_recall_unavailable" for event in completed.events
    )
    assert legal_contract_recall_actions(completed.state, 0) == ()
    assert completed.state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS


def test_twisted_mentat_never_offers_an_earlier_turns_conflict_agent() -> None:
    # Review round 1 major finding: Twisted Mentat may recall only "the
    # Agent you sent this turn" [Twisted Mentat card]. While that Agent is
    # still on its space (no Into the Fray this turn), an earlier turn's
    # Conflict Agent must never be offered, even though the seat has one.
    state = _state(
        _owner(
            (MENTAT, DAGGER),
            agent_locations=(),
            agents_available=1,
            agent_in_conflict=1,
        )
    )
    grafted = _graft(state, MENTAT, "assembly_hall", DAGGER)
    actions = legal_agent_card_recall_actions(grafted, 0)
    assert {action.action_id for action in actions} == {
        "decline_agent_card_recall",
        "recall_agent_for_agent_card",
    }
    assert {
        dict(action.arguments).get("space_id")
        for action in actions
        if action.action_id == "recall_agent_for_agent_card"
    } == {"assembly_hall"}


def test_a_trashed_partner_loses_its_unactivated_box() -> None:
    state = _state(_owner((FACE_DANCER, DAGGER)))
    grafted = _graft(state, DAGGER, "assembly_hall", FACE_DANCER)
    trashed = trash_personal_card(grafted, 0, FACE_DANCER, source="test")
    from dune_imperium.rules.agent_effects import expire_trashed_card_effects

    expired = expire_trashed_card_effects(trashed)
    _, context = current_agent_effect_context(expired.state)
    assert context["graft_pending_effect"] is False
    assert expired.events[-1].kind == "agent_card_effect_expired"
    assert legal_graft_switch_actions(expired.state, 0) == ()


def test_bene_tleilax_researcher_reveals_marker_persuasion() -> None:
    for space, expected in ((RESEARCH_START_ID, 1), ("c4r2", 2), ("c8r4", 3)):
        state = _state(_owner((RESEARCHER,), research_space=space))
        revealed = begin_reveal_turn(
            state, DomainAction(action_id="reveal_turn", actor=0)
        )
        assert dict(revealed.state.decision_stack[-1].context)["persuasion"] == expected


def test_grafted_cards_round_trip_through_the_codec() -> None:
    codec = ActionCodec(IMMORTALITY)
    state = _state(_owner((FACE_DANCER, INITIATE, DAGGER)))
    for action in legal_agent_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action
    placed = apply_agent_action(
        state, _placements(state)[(INITIATE, "dutiful_service", True)]
    )
    for action in legal_graft_partner_actions(placed.state, 0):
        assert codec.decode(codec.encode(action), 0) == action
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    assert "choose_graft_partner" not in base
    assert not any(
        dict(template.arguments).get("graft")
        for template in ActionCodec(RulesetConfig()).catalog
    )


@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_checked_games_graft(policy: str) -> None:
    grafted = 0
    for seed in range(3):
        report = run_checked_game(
            IMMORTALITY,
            seed,
            700_000 + seed,
            policy=policy,
            soundness_interval=5,
            collect_coverage=True,
        )
        assert report.winner is not None
        assert report.coverage is not None
        grafted += report.coverage["event_kinds"].get("card_grafted", 0)
    assert grafted > 0


def test_the_engine_never_offers_a_lone_graft_card() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(IMMORTALITY, seed=4)
    for _ in range(60):
        frame = state.decision_stack[-1]
        if not isinstance(frame.decision, PlayerDecision):
            break
        actions = engine.legal_actions(state, frame.decision.owner)
        assert actions
        state = engine.apply(state, actions[-1]).state


def test_a_graft_placed_on_a_leaders_icon_keeps_its_partners() -> None:
    # Mohiam's Clandestine gives "Each card you play has the Spy icon"
    # [Gaius Helen Mohiam card], so a starter with no printed icon of its own
    # reaches a Bene Gesserit space through a connected Spy -- and Infiltrate's
    # cost recalls that very Spy [Main p. 11]. The partner choice used to infer
    # space access from the placed card's printed icons, find none, and demand a
    # partner that fit Bene Gesserit; with none in hand the turn had no legal
    # action at all and the game died with "current player decision has no
    # legal actions" (2026-09-10 all-expansion A/B, game seed 499).
    placed = "player:0:starter:convincing_argument:0"
    partner = "tleilaxu:chairdog:0"
    owner = _owner(
        (placed, partner),
        leader_id="gaius_helen_mohiam",
        leader_face_id="gaius_helen_mohiam",
        spy_post_ids=("bene-gesserit-espionage-secrets",),
        spies_supply=2,
    )
    # An opponent Agent on Secrets makes Infiltrate the only way in, so the
    # placement spends the Spy that granted the icon.
    blocker = PlayerState(
        player_id=1,
        research_space=RESEARCH_START_ID,
        family_atomics=True,
        agents_available=1,
        agent_locations=("secrets",),
    )
    state = _state(
        owner,
        players=(
            owner,
            blocker,
            *(
                PlayerState(
                    player_id=seat,
                    research_space=RESEARCH_START_ID,
                    family_atomics=True,
                )
                for seat in (2, 3)
            ),
        ),
    )

    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments).get("space_id") == "secrets"
        and dict(action.arguments).get("card_id") == placed
        and dict(action.arguments).get("graft") is True
    )
    opened = apply_agent_action(state, placement).state

    # The Spy that granted access is gone when the partner is chosen, so the
    # frame has to carry the placement's own answer.
    assert opened.players[0].spy_post_ids == ()
    assert opened.decision_stack[-1].kind == "graft_partner"
    assert dict(opened.decision_stack[-1].context)["placed_reaches"] is True
    assert set(_partners(opened)) == {partner}


def test_an_infiltrating_usurp_keeps_the_partner_whose_spy_let_it_in() -> None:
    # The partner-side half of the same trap. Usurp prints no Agent icon at
    # all, so the access is always the partner's: Guild Spy's Spy icon reaches
    # "현재 자신의 Spy가 놓인 관측소와 연결된 공간" and "이 아이콘을 사용하기
    # 위해 Spy를 회수하지는 않는다" [Main p. 11]. Infiltrate on the same
    # placement does recall that Spy as its own cost [Main p. 11] [FAQ p. 4],
    # so re-deriving partner access afterwards filtered every candidate out and
    # the turn had no legal action (2026-09-10 Immortality A/B, game seeds
    # 70254 and 70804).
    placed = "tleilaxu:usurp:0"
    partner = "imperium:guild_spy:0"
    owner = _owner(
        (placed, partner),
        spy_post_ids=("bene-gesserit-espionage-secrets",),
        spies_supply=2,
    )
    blocker = PlayerState(
        player_id=1,
        research_space=RESEARCH_START_ID,
        family_atomics=True,
        agents_available=1,
        agent_locations=("secrets",),
    )
    state = _state(
        owner,
        players=(
            owner,
            blocker,
            *(
                PlayerState(
                    player_id=seat,
                    research_space=RESEARCH_START_ID,
                    family_atomics=True,
                )
                for seat in (2, 3)
            ),
        ),
    )

    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments).get("space_id") == "secrets"
        and dict(action.arguments).get("card_id") == placed
        and dict(action.arguments).get("graft") is True
    )
    opened = apply_agent_action(state, placement).state

    # Usurp reaches nothing on its own, and the Spy that let the partner in is
    # spent -- so the frame has to carry the post it was recalled from.
    assert opened.players[0].spy_post_ids == ()
    context = dict(opened.decision_stack[-1].context)
    assert context["placed_reaches"] is False
    assert context["infiltrate_post_id"] == "bene-gesserit-espionage-secrets"
    assert partner in _partners(opened)
