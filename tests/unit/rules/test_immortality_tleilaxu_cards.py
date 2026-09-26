"""Tests for the Tleilaxu deck cards of slice 5c-1.

Rule source: the card faces transcribed in
``docs/implementation-audits/immortality.md`` (Tleilaxu table); the Graft
rules [Immortality pp. 10-11] and the FAQ's Beguiling Pheromones ruling
[FAQ p. 1] (a trashed partner's un-activated box expires, OQ-022).
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
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.observation import observe_state
from dune_imperium.rules.agent_effects import (
    apply_agent_card_discard,
    apply_agent_card_payment,
    legal_agent_card_discard_actions,
    legal_agent_card_payment_actions,
    legal_agent_card_spy_actions,
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
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.spy_placement import observation_post_ids_for_factions

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


def _research_to(state: GameState, space_id: str) -> GameState:
    """Answer the research-direction frame the Research just opened."""

    assert state.decision_stack[-1].kind == FrameKind.RESEARCH_ADVANCE
    return UprisingRulesEngine().apply(
        state,
        DomainAction("choose_research_space", 0, (("space_id", space_id),)),
    ).state


def test_scientific_breakthrough_own_research_can_unlock_its_trash_line() -> None:
    # The box prints the Research icon and, on its own line, "[2 genetic
    # markers]: Trash this card -> 1 VP" [Scientific Breakthrough card].
    # "When your research token reaches a column with a genetic marker at the
    # bottom, for the rest of the game, any effects on cards marked with that
    # icon are active for you." [Immortality p. 6] (docs/rules/immortality.md
    # "token이 아래에 genetic marker가 있는 열에 도달하면 남은 게임 동안 그
    # 아이콘이 붙은 카드 효과가 활성화된다"), the owner carries out the
    # effects "in any order" [Main p. 9], and a condition is judged when its
    # effect resolves (OQ-028). The markers were judged once, before the
    # card's own Research, so a token one step short of the second marker
    # researched into it and the trash line was never offered.
    breakthrough = _tleilaxu("scientific_breakthrough")
    placed = _place(
        _state(_owner((breakthrough,), research_space="c7r3")),
        breakthrough,
        "arrakeen",
    )
    assert legal_agent_card_payment_actions(placed, 0) == ()
    researched = _research_to(resolve_agent_card_effect(placed).state, "c8r2")
    before = researched.players[0]
    assert before.research_space == "c8r2"

    assert {a.action_id for a in legal_agent_card_payment_actions(researched, 0)} == {
        "decline_agent_card_payment",
        "trash_agent_card_self_for_vp",
    }
    trashed = apply_agent_card_payment(
        researched, _payment(researched, "trash_agent_card_self_for_vp")
    )
    owner = trashed.state.players[0]
    assert breakthrough in owner.trashed and breakthrough not in owner.in_play
    assert owner.victory_points == before.victory_points + 1
    # The Research already resolved: the trash does not research again
    # (past the second marker that would draw a card).
    assert owner.hand == before.hand
    assert owner.research_space == "c8r2"

    # Declining keeps the card in play and gives nothing.
    declined = apply_agent_card_payment(
        researched, _payment(researched, "decline_agent_card_payment")
    ).state.players[0]
    assert breakthrough in declined.in_play
    assert declined.victory_points == before.victory_points


def test_scientific_breakthrough_trash_line_waits_for_the_turn_end() -> None:
    # A Research that stops short of the second marker leaves the line
    # closed; it waits for the turn's end (OQ-057 (1)) in case a later
    # effect of the turn reaches the marker, and lapses there.
    breakthrough = _tleilaxu("scientific_breakthrough")
    placed = _place(
        _state(_owner((breakthrough,), research_space="c4r2")),
        breakthrough,
        "arrakeen",
    )
    researched = _research_to(resolve_agent_card_effect(placed).state, "c5r3")
    engine = UprisingRulesEngine()
    card_actions = {
        "resolve_agent_card_effect",
        "decline_agent_card_payment",
        "trash_agent_card_self_for_vp",
    }
    offered = {
        a.action_id
        for a in engine.legal_actions(researched, 0)
        if not dict(a.arguments).get("effect")
    }
    assert not offered & card_actions
    _, context = current_agent_effect_context(researched)
    assert context["pending_agent_effect"] is True

    closed = _engine_finish_turn(researched)
    owner = closed.players[0]
    assert breakthrough in owner.in_play
    assert owner.victory_points == researched.players[0].victory_points


def test_ghola_copying_scientific_breakthrough_researches_on_its_own() -> None:
    # Ghola "copies the entire Agent box" [Immortality p. 14]: each box does
    # its own Research, so the first box's Research must not count as the
    # copy's.
    breakthrough = _tleilaxu("scientific_breakthrough")
    ghola = _tleilaxu("ghola")
    grafted = _graft(
        _state(_owner((breakthrough, ghola), research_space="c7r3")),
        breakthrough,
        "arrakeen",
        ghola,
    )
    researched = _research_to(resolve_agent_card_effect(grafted).state, "c8r2")
    assert {a.action_id for a in legal_agent_card_payment_actions(researched, 0)} == {
        "decline_agent_card_payment",
        "trash_agent_card_self_for_vp",
    }
    switched = _switch(researched)
    assert {a.action_id for a in legal_agent_card_payment_actions(switched, 0)} == {
        "resolve_agent_card_effect",
        "trash_agent_card_self_for_vp",
    }
    # Past the second marker Ghola's Research draws a card.
    hand = switched.players[0].hand
    drawn = resolve_agent_card_effect(switched).state
    assert len(drawn.players[0].hand) == len(hand) + 1


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

    spiced = (
        UprisingRulesEngine()
        .apply(
            switched,
            DomainAction("harvest_maker_spice", 0, (("space_id", "hagga_basin"),)),
        )
        .state
    )
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

    # Borrowed icons count too (OQ-055): Blank Slate grafted has its three
    # printed icons plus the four Faction icons.
    slate = "imperium:blank_slate:0"
    borrowed = _graft(
        _state(_owner((farmer, slate), resources=Resources(solari=0))),
        farmer,
        "assembly_hall",
        slate,
    )
    resolved = resolve_agent_card_effect(borrowed)
    assert resolved.state.players[0].resources.solari == 7


def test_slig_farmer_counts_mohiams_clandestine_spy_icon() -> None:
    # Clandestine: "Each card you play has the [Spy] icon" [Gaius Helen
    # Mohiam card]; Slig Farmer counts every Agent icon the other grafted
    # card has at that moment (OQ-055), so the Dagger's Landsraad icon and
    # the Spy make two.
    farmer = _tleilaxu("slig_farmer")
    both = RulesetConfig(bloodlines=True, immortality=True, promo_cards=True)
    mohiam = _graft(
        _state(
            _owner(
                (farmer, DAGGER),
                leader_id="gaius_helen_mohiam",
                resources=Resources(solari=0),
            ),
            config=both,
        ),
        farmer,
        "assembly_hall",
        DAGGER,
    )
    assert personal_card_for_instance(DAGGER).agent_icons == (AgentIcon.LANDSRAAD,)
    resolved = resolve_agent_card_effect(mohiam)
    assert resolved.state.players[0].resources.solari == 2

    # With three Solari the five-Solari Tleilaxu payment opens (3 + 2).
    richer = _graft(
        _state(
            _owner(
                (farmer, DAGGER),
                leader_id="gaius_helen_mohiam",
                resources=Resources(solari=3),
            ),
            config=both,
        ),
        farmer,
        "assembly_hall",
        DAGGER,
    )
    assert "pay_agent_card_five_solari_for_tleilaxu" in {
        action.action_id for action in legal_agent_card_payment_actions(richer, 0)
    }


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
    # "Choose two" names both before either pays out (designer ruling, OQ-057).
    assert owner.resources.water == 2
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
    assert owner.resources.water == 3
    assert owner.tleilaxu_space == 1
    _, context = current_agent_effect_context(second.state)
    assert context["pending_agent_effect"] is False

    trashing = apply_agent_card_payment(
        state, _payment(state, "choose_agent_card_reward", reward="trash")
    )
    # The trash waits for the second pick too.
    assert trashing.state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    trashed_and_troop = apply_agent_card_payment(
        trashing.state,
        _payment(trashing.state, "choose_agent_card_reward", reward="troop"),
    ).state
    assert trashed_and_troop.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    assert trashed_and_troop.decision_stack[-2].kind == FrameKind.AGENT_EFFECTS
    assert trashed_and_troop.players[0].troops_garrison == 4


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
    # "If you sent an Agent to a Faction board space this turn, trash one of
    # the grafted cards and gain an additional Influence with that Faction."
    # [Beguiling Pheromones card] has no "may", arrow or black-X icon, so it
    # is mandatory: "Most effects from a board space or card you play are
    # mandatory, unless: a card says "you may" do something; there's an
    # arrow in the effect ...; you're trashing a card using the "black X"
    # card icon" [FAQ p. 3]. The owner picks the card, never whether.
    assert [(a.action_id, dict(a.arguments).get("card_id")) for a in actions] == [
        ("trash_grafted_card_for_influence", pheromones),
        ("trash_grafted_card_for_influence", FACE_DANCER),
    ]
    engine = UprisingRulesEngine()
    legal_ids = {a.action_id for a in engine.legal_actions(switched, 0)}
    assert "decline_agent_card_payment" not in legal_ids
    assert "finish_agent_turn" not in legal_ids
    # Trashing the partner expires its un-activated draw (OQ-022, FAQ p. 1).
    partner = apply_agent_card_payment(switched, actions[1])
    owner = partner.state.players[0]
    assert FACE_DANCER in owner.trashed and owner.influence.emperor == 1
    _, context = current_agent_effect_context(partner.state)
    assert context["graft_pending_effect"] is False
    # Trashing itself keeps the Influence (its own cost).
    own = apply_agent_card_payment(switched, actions[0])
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


def _engine_finish_turn(state: GameState) -> GameState:
    """Resolve the owner's pending boxes through the engine until the turn closes."""

    engine = UprisingRulesEngine()
    for _ in range(20):
        frame = state.decision_stack[-1]
        if frame.kind == FrameKind.TURN:
            return state
        actions = engine.legal_actions(state, 0)
        preferred = [
            a
            for a in actions
            if a.action_id
            in (
                "resolve_agent_card_effect",
                "resolve_board_effect",
                "finish_agent_turn",
            )
        ] or [a for a in actions if not a.action_id.startswith("deploy")]
        state = engine.apply(state, preferred[0]).state
    raise AssertionError("the Agent turn did not close")


def test_sardaukar_coordination_lets_recruits_deploy_on_either_graft_side() -> None:
    # Graft: "Both played cards are considered to have 'sent' the Agent, no
    # matter which card's icon you use" and "You gain the effects on both
    # cards" [Immortality p. 10]. Sardaukar Coordination's Agent box reads
    # "You may deploy any troops you recruit this turn to the Conflict."
    # [Sardaukar Coordination card]. It used to count only as the placed
    # card, so grafted as Face Dancer's partner -- even at Deliver Supplies,
    # where its own Emperor icon cannot go -- its recruits stayed home.
    from dune_imperium.rules.combat_deployment import legal_combat_deployments
    from dune_imperium.rules.frames import with_context

    coordination = next(
        card
        for card in imperium_deck_instance_ids(False)
        if ":sardaukar_coordination:" in card
    )
    for placed_id, partner_id, space_id in (
        (FACE_DANCER, coordination, "deliver_supplies"),
        (FACE_DANCER, coordination, "dutiful_service"),
        (coordination, FACE_DANCER, "dutiful_service"),
    ):
        owner = _owner((placed_id, partner_id), troops_garrison=4, troops_supply=8)
        grafted = _graft(_state(owner), placed_id, space_id, partner_id)
        frame, context = current_agent_effect_context(grafted)
        assert context["pending_combat_deployment"] is True, (placed_id, space_id)
        assert context["existing_troop_deployment_limit"] == 0
        recruited = replace(
            grafted,
            decision_stack=(
                *grafted.decision_stack[:-1],
                with_context(frame, {**context, "troops_recruited": 2}),
            ),
        )
        counts = [
            dict(action.arguments)["count"]
            for action in legal_combat_deployments(recruited, 0)
        ]
        assert counts == [1, 2], (placed_id, space_id)

    # A turn whose unit deployment is banned (Emperor of the Known Universe,
    # applied "immediately" when the Agent is sent [Main p. 17] [FAQ p. 3])
    # gets no deployment window from the partner either.
    owner = _owner((FACE_DANCER, coordination), troops_garrison=4, troops_supply=8)
    placed = _place(_state(owner), FACE_DANCER, "deliver_supplies", graft=True)
    effect_frame = placed.decision_stack[-2]
    assert effect_frame.kind == FrameKind.AGENT_EFFECTS
    blocked = replace(
        placed,
        decision_stack=(
            *placed.decision_stack[:-2],
            with_context(
                effect_frame,
                {**dict(effect_frame.context), "units_deploy_blocked": True},
            ),
            placed.decision_stack[-1],
        ),
    )
    partner = next(
        action
        for action in legal_graft_partner_actions(blocked, 0)
        if dict(action.arguments)["card_id"] == coordination
    )
    _, context = current_agent_effect_context(
        apply_graft_partner(blocked, partner).state
    )
    assert context.get("pending_combat_deployment") is not True


def test_ghola_borrows_the_other_grafted_box_on_either_side() -> None:
    ghola = _tleilaxu("ghola")
    tanks = _tleilaxu("from_the_tanks")
    # Ghola placed first: its box is From the Tanks' two troops, then the
    # switch resolves From the Tanks' own box.
    grafted = _graft(
        _state(_owner((ghola, tanks), troops_supply=9)), ghola, "arrakeen", tanks
    )
    _, context = current_agent_effect_context(grafted)
    assert context["pending_agent_effect"] is True
    assert context["graft_pending_effect"] is True
    first = resolve_agent_card_effect(grafted)
    assert first.state.players[0].troops_garrison == 5
    switched = _switch(first.state)
    second = resolve_agent_card_effect(switched)
    assert second.state.players[0].troops_garrison == 7

    # Ghola as the partner of Face Dancer (placed on its Emperor icon): its
    # box draws a card too.
    grafted = _graft(
        _state(_owner((FACE_DANCER, ghola))), FACE_DANCER, "dutiful_service", ghola
    )
    _, context = current_agent_effect_context(grafted)
    assert context["graft_pending_effect"] is True
    drawn = resolve_agent_card_effect(_switch(resolve_agent_card_effect(grafted).state))
    assert len(drawn.state.players[0].hand) == 2

    # Without a partner box (Face Dancer Initiate's empty box) Ghola has none.
    initiate = _tleilaxu("face_dancer_initiate")
    grafted = _graft(_state(_owner((ghola, initiate))), ghola, "arrakeen", initiate)
    _, context = current_agent_effect_context(grafted)
    assert context["pending_agent_effect"] is False


def test_chairdog_returns_the_other_grafted_card_when_the_reveal_starts() -> None:
    chairdog = _tleilaxu("chairdog")
    grafted = _graft(_state(_owner((chairdog, DAGGER))), chairdog, "arrakeen", DAGGER)
    resolved = resolve_agent_card_effect(grafted)
    owner = resolved.state.players[0]
    assert owner.chairdog_return_card_ids == (DAGGER,)
    assert DAGGER in owner.in_play
    closed = _engine_finish_turn(resolved.state)
    # The next seat's turn opened; give seat 0 its Reveal turn directly.
    state = replace(
        closed,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0b",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    revealed = begin_reveal_turn(state, DomainAction("reveal_turn", 0))
    owner = revealed.state.players[0]
    # The card came back to the hand and was revealed with it.
    assert revealed.events[0].kind == "card_returned_to_hand"
    context = dict(revealed.state.decision_stack[-1].context)
    assert DAGGER in owner.in_play and owner.chairdog_return_card_ids == ()
    assert DAGGER in {
        value for key, value in context.items() if key.startswith("revealed_card_")
    }
    # The public seat view reports the pending return while it is scheduled.
    assert observe_state(resolved.state, 1).players[0].chairdog_return_card_ids == (
        DAGGER,
    )


def test_usurp_grafts_a_row_card_that_leaves_the_game_when_the_turn_closes() -> None:
    usurp = _tleilaxu("usurp")
    occupation = "imperium:occupation:0"
    imperium = imperium_deck_instance_ids(False)
    state = _state(
        _owner((usurp,), troops_supply=9),
        imperium_row=(occupation, *imperium[1:5]),
        imperium_deck=imperium[5:20],
    )
    # Usurp alone has no icons: only the graft variant, on the Row's icons.
    placements = {
        (dict(a.arguments)["space_id"], dict(a.arguments).get("graft"))
        for a in legal_agent_actions(state, 0)
        if dict(a.arguments)["card_id"] == usurp
    }
    assert ("arrakeen", True) in placements and ("arrakeen", None) not in placements
    placed = _place(state, usurp, "arrakeen", graft=True)
    partners = [
        dict(a.arguments)["card_id"] for a in legal_graft_partner_actions(placed, 0)
    ]
    # Only Row cards whose icons reach Arrakeen (Occupation's City icon).
    assert occupation in partners
    assert all(card in state.imperium_row for card in partners)
    grafted = apply_graft_partner(
        placed, DomainAction("choose_graft_partner", 0, (("card_id", occupation),))
    )
    owner = grafted.state.players[0]
    assert occupation in owner.in_play and owner.usurped_row_card_id == occupation
    assert occupation not in grafted.state.imperium_row
    assert len(grafted.state.imperium_row) == 5  # refilled at once
    assert dict(grafted.events[0].payload)["from_row"] is True
    _, context = current_agent_effect_context(grafted.state)
    assert context["graft_pending_effect"] is True

    # Occupation's box (draw and the Combat icon) resolves like any partner.
    drawn = resolve_agent_card_effect(_switch(grafted.state))
    assert len(drawn.state.players[0].hand) == 1
    closed = _engine_finish_turn(drawn.state)
    owner = closed.players[0]
    # The turn's close trashes the borrowed card automatically (OQ-054).
    assert occupation not in owner.in_play and occupation in owner.trashed
    assert occupation not in closed.imperium_removed
    assert owner.usurped_row_card_id == ""
    assert observe_state(closed, 1).players[0].usurped_row_card_id == ""



def test_usurps_borrowed_stillsuit_manufacturer_never_returns_to_hand() -> None:
    # Designer ruling (BGG, OQ-054): a Row card borrowed through Usurp is not
    # "in play", so Stillsuit Manufacturer's Fremen-Alliance return to hand
    # does not happen; the card is trashed when the turn closes.
    usurp = _tleilaxu("usurp")
    stillsuit = "imperium:stillsuit_manufacturer:0"
    imperium = imperium_deck_instance_ids(False)
    state = _state(
        _owner((usurp,), alliance_faction_ids=("fremen",)),
        imperium_row=(stillsuit, *imperium[1:5]),
        imperium_deck=imperium[5:20],
    )
    placed = _place(state, usurp, "arrakeen", graft=True)
    grafted = apply_graft_partner(
        placed, DomainAction("choose_graft_partner", 0, (("card_id", stillsuit),))
    ).state
    resolved = resolve_agent_card_effect(_switch(grafted))
    owner = resolved.state.players[0]
    assert owner.resources.water == 3
    assert stillsuit in owner.in_play and stillsuit not in owner.hand
    closed = _engine_finish_turn(resolved.state)
    owner = closed.players[0]
    assert stillsuit in owner.trashed
    assert stillsuit not in owner.hand and stillsuit not in owner.in_play

def test_usurp_trash_fires_the_borrowed_cards_trash_trigger() -> None:
    """Replacement Eyes' "when this card is trashed: Tleilaxu" resolves when
    Usurp's automatic end-of-turn trash removes it (user ruling, OQ-054)."""

    usurp = _tleilaxu("usurp")
    eyes = "imperium:replacement_eyes:0"
    imperium = imperium_deck_instance_ids(False)
    state = _state(
        _owner((usurp,)),
        imperium_row=(eyes, *imperium[1:5]),
        imperium_deck=imperium[5:20],
    )
    placed = _place(state, usurp, "arrakeen", graft=True)
    grafted = apply_graft_partner(
        placed, DomainAction("choose_graft_partner", 0, (("card_id", eyes),))
    ).state
    engine = UprisingRulesEngine()
    result = None
    for _ in range(20):
        if grafted.decision_stack[-1].kind == FrameKind.TURN:
            break
        actions = engine.legal_actions(grafted, 0)
        preferred = [a for a in actions if not a.action_id.startswith("deploy")]
        result = engine.apply(grafted, preferred[0])
        grafted = result.state
    owner = grafted.players[0]
    assert eyes in owner.trashed and owner.usurped_row_card_id == ""
    assert owner.tleilaxu_space == 1
    assert result is not None
    kinds = [event.kind for event in result.events]
    assert "usurped_card_trashed" in kinds and "card_trashed" in kinds


def test_usurp_trash_does_not_credit_a_bank_commander_to_the_next_turn() -> None:
    """2026-09-26 review round 5, Finding 1 (Usurp regression, major):
    ``resolve_usurp_trash`` only ever fires once ``_agent_turn_is_open_for``
    is False -- the owner's turn has always already closed by then -- but it
    called ``trash_personal_card`` with the default ``turn_closed=False``.
    Sardaukar Standard's trash trigger (Emperor Faction, ACQUIRE_BANK_
    COMMANDER) then queues an unmarked ``pending_skill_choices`` entry;
    ``begin_skill_choice`` opens on whatever frame sits on top when the
    engine gets to it, which -- once every other seat has revealed -- is the
    fresh "turn" frame ``advance_after_effect`` already reopened for this
    same player. "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에
    deploy할 수 있다. 이미 garrison에 있던 troop을 다시 recruit한 것으로
    취급해 두 개 제한을 우회할 수는 없다" [Main p. 10] [FAQ p. 4]
    (docs/rules/player-turns.md:137); a Sardaukar Commander is a "troop"
    worth 2 strength [Bloodlines p. 4].
    """

    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.rules.combat_deployment import legal_combat_deployments

    usurp = _tleilaxu("usurp")
    standard = "imperium:sardaukar_standard:0"
    experimentation = next(card for card in STARTERS if "experimentation:0" in card)
    imperium = imperium_deck_instance_ids(False)
    skills = skill_tile_instance_ids()
    owner = _owner((usurp, experimentation))
    state = _state(
        owner,
        imperium_row=(standard, *imperium[1:5]),
        imperium_deck=imperium[5:20],
        config=RulesetConfig(bloodlines=True, immortality=True, promo_cards=True),
        sardaukar_commanders_bank=1,
        skill_face_up=skills[:4],
        skill_stack=skills[4:],
        players=(
            owner,
            _seat(1, has_revealed=True),
            _seat(2, has_revealed=True),
            _seat(3, has_revealed=True),
        ),
    )
    placed = _place(state, usurp, "arrakeen", graft=True)
    grafted = apply_graft_partner(
        placed, DomainAction("choose_graft_partner", 0, (("card_id", standard),))
    ).state
    engine = UprisingRulesEngine()
    result = None
    for _ in range(20):
        if grafted.decision_stack[-1].kind == FrameKind.TURN:
            break
        actions = engine.legal_actions(grafted, 0)
        preferred = [a for a in actions if not a.action_id.startswith("deploy")]
        result = engine.apply(grafted, preferred[0])
        grafted = result.state

    top = grafted.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    owner_after = grafted.players[0]
    # The trash, and the Commander it acquires, still happen...
    assert standard in owner_after.trashed and owner_after.usurped_row_card_id == ""
    assert grafted.sardaukar_commanders_bank == 0
    assert owner_after.commanders_garrison == 1
    # ...but the Commander must not join the fresh "turn" frame's deploy
    # allowance, since it belongs to the turn that just closed.
    assert dict(top.context)["turn_owner"] == 0
    assert dict(top.context).get("troops_recruited") in (None, 0)

    next_placed = _place(grafted, experimentation, "imperial_basin")
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(next_placed, 0)
    ] == [1, 2]


def test_usurp_placed_first_may_take_a_hand_partner_instead_of_the_row() -> None:
    """ "You may graft ... with a card from the Imperium Row": the hand stays
    an option, and a hand partner is never trashed at the turn's end."""

    usurp = _tleilaxu("usurp")
    state = _state(_owner((usurp, FACE_DANCER)))
    placed = _place(state, usurp, "dutiful_service", graft=True)
    partners = {
        dict(a.arguments)["card_id"] for a in legal_graft_partner_actions(placed, 0)
    }
    assert FACE_DANCER in partners
    grafted = apply_graft_partner(
        placed, DomainAction("choose_graft_partner", 0, (("card_id", FACE_DANCER),))
    ).state
    owner = grafted.players[0]
    assert FACE_DANCER in owner.in_play and owner.usurped_row_card_id == ""
    assert len(grafted.imperium_row) == 5


def test_usurp_may_still_partner_a_hand_card_placed_first() -> None:
    usurp = _tleilaxu("usurp")
    grafted = _graft(
        _state(_owner((FACE_DANCER, usurp))), FACE_DANCER, "dutiful_service", usurp
    )
    owner = grafted.players[0]
    assert usurp in owner.in_play and owner.usurped_row_card_id == ""
    _, context = current_agent_effect_context(grafted)
    assert context["graft_pending_effect"] is False  # Usurp has no box


def test_usurp_is_offered_only_where_a_partner_can_follow() -> None:
    """An occupied space entered on Tleilaxu Infiltrator's promise needs the
    Infiltrator as the partner, so Usurp may go there only where the
    Infiltrator's own City icon reaches (2026-09-08 sweep seed 34 deadlock)."""

    usurp = _tleilaxu("usurp")
    infiltrator = _tleilaxu("tleilaxu_infiltrator")
    occupation = "imperium:occupation:0"
    imperium = imperium_deck_instance_ids(False)
    rival = replace(_seat(1), agent_locations=("assembly_hall",), agents_available=1)
    state = _state(
        _owner((usurp, infiltrator), troops_supply=9),
        imperium_row=(occupation, *imperium[1:5]),
        imperium_deck=imperium[5:20],
    )
    state = replace(state, players=(state.players[0], rival, *state.players[2:]))
    spaces = {
        dict(a.arguments)["space_id"]
        for a in legal_agent_actions(state, 0)
        if dict(a.arguments)["card_id"] == usurp
    }
    # Occupation's Landsraad icon would reach Assembly Hall, but the seat
    # there is occupied and the Infiltrator cannot follow: not offered.
    assert "assembly_hall" not in spaces
    assert "arrakeen" in spaces
    placed = _place(state, usurp, "arrakeen", graft=True)
    partners = {
        dict(a.arguments)["card_id"] for a in legal_graft_partner_actions(placed, 0)
    }
    assert occupation in partners and infiltrator in partners


def test_ghola_copying_steersman_can_end_the_turn_with_no_agent_to_recall() -> None:
    """Steersman's box is "draw a card, recall an Agent"; Ghola copies it,
    so the second box's recall icon has no Agent left once the first box
    recalled the only other one — the Agent sent this turn is never a target
    ("Return one of your other Agents on the board to your Leader (not the
    Agent you sent during this turn)." [Main p. 20]). A mandatory box whose
    condition is false waits for the turn's end and fizzles there (OQ-057),
    and before this the turn stalled with no legal action at all (soak seed
    78, --immortality)."""

    ghola = _tleilaxu("ghola")
    steersman = "imperium:steersman:0"
    engine = UprisingRulesEngine()
    state = _graft(
        _state(
            _owner(
                (steersman, ghola),
                family_atomics=False,
                agents_available=1,
                agent_locations=("dutiful_service",),
            )
        ),
        steersman,
        "arrakeen",
        ghola,
    )

    # Both boxes queue (cards, recall); resolve the active one and let its
    # recall take the seat's other Agent.
    def _apply(state: GameState, action_id: str, **arguments: object) -> GameState:
        action = next(
            action
            for action in engine.legal_actions(state, 0)
            if action.action_id == action_id
            and all(
                dict(action.arguments).get(key) == value
                for key, value in arguments.items()
            )
        )
        return engine.apply(state, action).state

    while any(
        action.action_id == "resolve_board_effect"
        for action in engine.legal_actions(state, 0)
    ):
        state = _apply(state, "resolve_board_effect")
    state = _apply(state, "resolve_agent_card_effect", effect="cards")
    assert not any(
        dict(action.arguments).get("space_id") == "arrakeen"
        for action in engine.legal_actions(state, 0)
        if action.action_id == "recall_agent_for_agent_card"
    )
    state = _apply(state, "recall_agent_for_agent_card", space_id="dutiful_service")
    assert state.players[0].agent_locations == ("arrakeen",)
    state = _apply(state, "switch_graft_card")
    state = _apply(state, "resolve_agent_card_effect", effect="cards")

    context = dict(state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert context["pending_agent_icons"] == "recall"
    # Nothing can resolve the icon, and no provider offers it; the turn end
    # is what carries the turn on (before the fix nothing was offered).
    offered = {action.action_id for action in engine.legal_actions(state, 0)}
    assert "finish_agent_turn" in offered
    assert not offered & {
        "resolve_agent_card_effect",
        "recall_agent_for_agent_card",
        "switch_graft_card",
    }
    finished = engine.apply(
        state, DomainAction(action_id="finish_agent_turn", actor=0)
    )
    assert [event.kind for event in finished.events] == [
        "agent_card_effect_unavailable",
        "agent_turn_finished",
    ]
    assert finished.state.decision_stack[-1].kind == "turn"


def test_ghola_pays_the_borrowed_box_in_the_borrowed_box_s_resource() -> None:
    # "Ghola는 상대 카드의 Agent box 전체("Trash this card" 포함)를 복사하고"
    # `[Immortality p. 14]` (docs/rules/immortality.md 88), so an arrow cost on
    # the borrowed box is the borrowed box's cost. The provider read that
    # through ``active_agent_card`` while the apply read Ghola's own empty
    # face, so a Ghola copying Ecological Testing Station's "2 water: draw 2"
    # was charged four spice and a Victory Point instead -- and crashed when
    # the seat had no spice to take (all-option tournament seed 70620).
    ghola = _tleilaxu("ghola")
    station = "imperium:ecological_testing_station:0"
    grafted = _graft(
        _state(
            _owner(
                (ghola, station),
                resources=Resources(solari=4, spice=1, water=2),
            )
        ),
        ghola,
        "arrakeen",
        station,
    )

    before = grafted.players[0]
    payment = _payment(grafted, "pay_agent_card_water")
    paid = apply_agent_card_payment(grafted, payment).state
    owner = paid.players[0]

    # Two water, not four spice; two cards drawn, and no Victory Point. Before
    # the fix this spent spice, scored a point, and drew nothing.
    assert owner.resources.water == before.resources.water - 2
    assert owner.resources.spice == before.resources.spice
    assert owner.victory_points == before.victory_points
    assert len(owner.hand) == len(before.hand) + 2


def test_ghola_borrowing_a_discard_box_still_pays_out_its_rewards() -> None:
    # The same borrowed box `[Immortality p. 14]` on the discard branch:
    # ``apply_agent_card_discard`` read the printed card too, so a Ghola
    # copying Captured Mentat spent the discard and gained nothing.
    ghola = _tleilaxu("ghola")
    mentat = "imperium:captured_mentat:0"
    grafted = _graft(
        _state(_owner((ghola, mentat, DAGGER))), ghola, "arrakeen", mentat
    )

    discard = next(
        action
        for action in legal_agent_card_discard_actions(grafted, 0)
        if dict(action.arguments).get("card_id") == DAGGER
    )
    after = apply_agent_card_discard(grafted, discard).state
    owner = after.players[0]
    _, context = current_agent_effect_context(after)

    assert DAGGER in owner.discard_pile
    # Captured Mentat pays an Intrigue card and a personal card for the
    # discard, queued as their own icons in the owner's order (OQ-027).
    # Before the fix the discard was spent and neither reward was queued.
    assert context["pending_agent_icons"] == "intrigue,cards"
    assert context["pending_agent_effect"] is True


def test_ghola_borrowing_a_restricted_spy_box_keeps_its_post_limit() -> None:
    # "This card has the same Agent box as the other grafted card." [Ghola
    # card] and "Ghola copies the entire Agent box of the card it's grafted
    # to" [Immortality p. 14] (docs/rules/immortality.md "Ghola는 상대 카드의
    # Agent box 전체 ... 를 복사하고"). Reliable Informant's box is a Spy with
    # a placement limit -- "[Spy] on [icon]" means "the observation post must
    # connect to a [icon] board space" [Main p. 20] -- so Ghola's copy is
    # limited the same way. The borrowed box took the effect alone, and
    # Ghola's Spy could go on any empty post (13 instead of 3).
    ghola = _tleilaxu("ghola")
    informant = "imperium:reliable_informant:0"
    grafted = _graft(_state(_owner((ghola, informant))), ghola, "arrakeen", informant)
    targets = set(
        observation_post_ids_for_factions(
            personal_card_for_instance(informant).agent_spy_factions
        )
    )

    def offered(state: GameState) -> set[str]:
        return {
            str(dict(action.arguments)["post_id"])
            for action in legal_agent_card_spy_actions(state, 0)
        }

    # Ghola's box is the active one first; the switch then offers the
    # Informant's own box with the same limit.
    assert targets
    assert offered(grafted) == targets
    assert offered(_switch(grafted)) == targets
