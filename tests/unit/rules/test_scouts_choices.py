"""Arrakeen Scouts: turn-order choices of events and sales (slice 5).

docs/rules/arrakeen-scouts.md 6 and 9: "각자 선택"인 이벤트와 판매는 First
Player부터 차례로 한 가지를 고른다; "또는 패스"가 있으면 선택하지 않아도
된다; 패스가 없으면 반드시 하나를 해야 하며, 할 수 없는 쪽은 고를 수 없다
(OQ-071). Political Equilibrium, Rebuild Infrastructure (OQ-084).
"""

from dataclasses import replace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.content.arrakeen_scouts import EVENTS_BY_ID
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts_effects import SCOUTS_NO_OPTION

ENGINE = UprisingRulesEngine()
SCOUTS = RulesetConfig(arrakeen_scouts=True)


def _base(**seat_fields: Any) -> GameState:
    """Round 4's Scouts step about to draw its event; seat 0 is First Player."""

    return _base_for(SCOUTS, seat_fields)


def _base_for(config: RulesetConfig, seat_fields: dict[str, Any]) -> GameState:
    """``_base`` under ``config``."""

    state = ENGINE.reset(config, 21)
    resolver = ChanceResolver(seed=21)
    while isinstance(ENGINE.current_decision(state), ChanceDecision):
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = ENGINE.apply(state, resolver.resolve(decision)).state
    rich = Resources(solari=5, spice=5, water=2)
    players = tuple(
        replace(
            player,
            **{"resources": rich, **seat_fields.get(str(player.player_id), {})},
        )
        for player in state.players
    )
    return replace(
        state,
        round_number=4,
        first_player=0,
        players=players,
        decision_stack=(),
        scouts_opening=True,
    )


def _reveal(state: GameState, item_id: str) -> GameState:
    advanced = _advance_automatic(RuleResult(state=state)).state
    frame = advanced.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    ticket = next(o for o in decision.options if o.split("#")[0] == item_id)
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(ticket,))
    ).state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _offered(state: GameState) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
    return [
        (a.action_id, a.arguments) for a in ENGINE.legal_actions(state, _owner(state))
    ]


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = ENGINE.legal_actions(state, seat)
    assert action in legal, (action, legal)
    return ENGINE.apply(state, action, legal_actions=legal).state


def _on_turn(state: GameState) -> bool:
    return state.decision_stack[-1].kind == FrameKind.TURN


def _takes_nothing(state: GameState, seat: int) -> GameState:
    """Cleanup-2a (OQ-071 addendum, the 2026-09-30 ruling "결정 창 없이 자동으로
    넘어가는 곳도 모두 결정 창을 연다"): a seat with no line it can take is
    asked too; its one row takes nothing and emits the skip."""

    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == seat
    assert _offered(state) == [(SCOUTS_NO_OPTION, ())]
    after = _act(state, SCOUTS_NO_OPTION)
    new = after.event_log[len(state.event_log) :]
    assert [
        dict(e.payload)["player"] for e in new if e.kind == "scouts_choice_skipped"
    ] == [seat]
    return after


def test_royal_delegation_goes_round_the_table_and_may_be_passed() -> None:
    state = _reveal(_base(), "royal_delegation")
    seats = []
    while not _on_turn(state):
        assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
        seats.append(_owner(state))
        assert _offered(state) == [
            ("scouts_pass", ()),
            ("scouts_choose_option", (("option", 0),)),
        ]
        if _owner(state) == 1:
            solari = state.players[1].resources.solari
            state = _act(state, "scouts_choose_option", option=0)
            assert state.players[1].resources.solari == solari - 2
            assert state.players[1].influence.emperor == 1
        else:
            state = _act(state, "scouts_pass")
    assert seats == [0, 1, 2, 3]


def test_a_seat_that_cannot_pay_is_asked_and_takes_nothing() -> None:
    poor = {"resources": Resources(solari=1, spice=0, water=1)}
    state = _reveal(_base(**{"0": poor}), "royal_delegation")
    state = _takes_nothing(state, 0)
    assert _owner(state) == 1


def test_private_stock_must_take_one_of_its_two_lines() -> None:
    state = _reveal(_base(), "private_stock")
    assert _offered(state) == [
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
    ]
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.spice == spice + 1


def test_crackdown_still_asks_a_seat_with_only_one_possible_loss() -> None:
    """OQ-071, user ruling 2026-09-29: when one of a mandatory event's two
    lines is impossible, the seat still gets the choice, with that line
    shown but not selectable; only a seat that can do neither is skipped.
    Seat 0 has no Spy on the board, so the Emperor loss is its one legal
    line. Seat 1 holds a Spy and Emperor Influence: both lines."""

    from dune_imperium.display.scouts import scouts_choice_lines

    state = _base(
        **{
            "0": {"influence": Influence(emperor=2)},
            "1": {
                "influence": Influence(emperor=1),
                "spies_supply": 2,
                "spy_post_ids": ("arrakis-deep-desert",),
            },
            "2": {"influence": Influence()},
            "3": {"influence": Influence()},
        }
    )
    state = _reveal(state, "crackdown")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == 0
    assert state.players[0].influence.emperor == 2  # nothing taken yet
    assert _offered(state) == [("scouts_choose_option", (("option", 1),))]
    legal = ENGINE.legal_actions(state, 0)
    info = scouts_choice_lines(state, 0, legal)
    assert info is not None
    lines = info["lines"]
    assert isinstance(lines, list)
    spy, emperor = lines
    assert not spy["enabled"] and spy["reason"]
    assert emperor["enabled"]
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[0].influence.emperor == 1
    assert state.players[0].victory_points == 0  # dropped below 2
    assert _owner(state) == 1
    assert {action for action, _ in _offered(state)} == {"scouts_choose_option"}
    assert len(_offered(state)) == 2
    state = _act(state, "scouts_choose_option", option=0)
    state = _act(state, "scouts_recall_spy", post_id="arrakis-deep-desert")
    assert state.players[1].spy_post_ids == ()
    assert state.players[1].influence.emperor == 1
    # Seats 2 and 3 can do neither: each confirms taking nothing, then the
    # turn opens.
    state = _takes_nothing(_takes_nothing(state, 2), 3)
    assert _on_turn(state)


def test_political_equilibrium_lowers_the_highest_track_and_asks_on_a_tie() -> None:
    state = _base(
        **{
            "0": {"influence": Influence(fremen=3, emperor=1)},
            "1": {"influence": Influence(spacing_guild=2, bene_gesserit=2)},
            "2": {"influence": Influence()},
            "3": {"influence": Influence(fremen=1)},
        }
    )
    state = _reveal(state, "political_equilibrium")
    assert state.players[0].influence == Influence(fremen=2, emperor=1)
    assert _owner(state) == 1
    assert {dict(args)["faction"] for _, args in _offered(state)} == {
        "spacing_guild",
        "bene_gesserit",
    }
    state = _act(state, "scouts_lose_influence", faction="bene_gesserit")
    assert state.players[1].influence == Influence(spacing_guild=2, bene_gesserit=1)
    assert state.players[3].influence == Influence()
    assert _on_turn(state)


def test_political_equilibrium_transfers_the_alliance_to_the_first_loser() -> None:
    """FAQ p.1, as implemented by ``rules/influence.py``'s
    ``lose_faction_influence``: First Player order decides an Alliance's new
    holder when the holder and another seat tie for the losing seat's
    highest track (OQ-071, OQ-002)."""
    state = _base(
        **{
            "0": {
                "influence": Influence(emperor=5),
                "alliance_faction_ids": ("emperor",),
            },
            "1": {"influence": Influence(emperor=5)},
            "2": {"influence": Influence()},
            "3": {"influence": Influence()},
        }
    )
    state = _reveal(state, "political_equilibrium")
    # Seat 0 (First Player) loses first, while seat 1 is still tied at 5:
    # the Alliance transfers to seat 1, not returned to the bank.
    assert state.players[0].influence.emperor == 4
    assert state.players[0].alliance_faction_ids == ()
    assert state.players[1].influence.emperor == 4
    assert state.players[1].alliance_faction_ids == ("emperor",)
    assert _on_turn(state)


def test_rebuild_infrastructure_needs_two_seats_to_pay() -> None:
    assert EVENTS_BY_ID["rebuild_infrastructure"].rounds == (7, 7)
    state = replace(_base(), round_number=7, shield_wall_present=False)
    state = _reveal(state, "rebuild_infrastructure")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    spice = [player.resources.spice for player in state.players]
    state = _act(state, "scouts_pass")  # seat 0
    state = _act(state, "scouts_choose_option", option=0)  # seat 1 agrees
    assert state.players[1].resources.spice == spice[1]  # nobody pays yet
    state = _act(state, "scouts_choose_option", option=0)  # seat 2 agrees
    assert state.shield_wall_present
    assert state.players[1].resources.spice == spice[1] - 1
    assert state.players[2].resources.spice == spice[2] - 1
    assert _on_turn(state)  # seat 3 is not asked


def test_rebuild_infrastructure_with_one_volunteer_pays_nothing() -> None:
    state = replace(_base(), round_number=7, shield_wall_present=False)
    state = _reveal(state, "rebuild_infrastructure")
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=0)
    for _ in range(3):
        state = _act(state, "scouts_pass")
    assert not state.shield_wall_present
    assert state.players[0].resources.spice == spice
    assert _on_turn(state)


def test_rebuild_infrastructure_does_nothing_with_the_wall_standing() -> None:
    state = _reveal(replace(_base(), round_number=7), "rebuild_infrastructure")
    assert _on_turn(state)
    assert any(e.kind == "scouts_item_moot" for e in state.event_log)


def test_moment_of_revelation_puts_prepare_the_way_in_hand() -> None:
    state = _reveal(_base(), "moment_of_revelation")
    before = dict(state.reserve_stacks)["prepare_the_way"]
    state = _act(state, "scouts_choose_option", option=0)
    assert any(
        card.startswith("reserve:prepare_the_way") for card in state.players[0].hand
    )
    assert dict(state.reserve_stacks)["prepare_the_way"] == before - 1


def test_moment_of_revelation_is_skipped_with_an_empty_reserve_stack() -> None:
    """OQ-022's direction, the Moment of Revelation ruling of 2026-09-29: a
    cost that buys nothing (Prepare the Way exhausted) is not offered
    [Main p. 20]; every seat takes nothing and nobody pays."""
    base = _base()
    empty_stack = tuple(
        (card_id, 0) if card_id == "prepare_the_way" else (card_id, count)
        for card_id, count in base.reserve_stacks
    )
    spice_before = [player.resources.spice for player in base.players]
    state = _reveal(replace(base, reserve_stacks=empty_stack), "moment_of_revelation")
    for seat in range(4):
        state = _takes_nothing(state, seat)
    assert _on_turn(state)
    assert [player.resources.spice for player in state.players] == spice_before


def _late(state: GameState) -> GameState:
    """Round 9 with the late auction in round 8: the sale is drawn now."""

    return replace(
        state,
        round_number=9,
        scouts_mid_auction_round=5,
        scouts_late_auction_round=8,
    )


def _reveal_sale(state: GameState, sale_id: str) -> GameState:
    advanced = _advance_automatic(RuleResult(state=state)).state
    decision = advanced.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    assert sale_id in decision.options
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(sale_id,))
    ).state


def test_secrets_for_sale_buys_two_intrigue_for_three_spice() -> None:
    state = _reveal_sale(_late(_base()), "secrets_for_sale")
    intrigue = len(state.players[0].intrigue_cards)
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[0].resources.spice == spice - 3
    assert len(state.players[0].intrigue_cards) == intrigue + 2


def test_shadow_warfare_sends_its_recruits_to_the_conflict() -> None:
    spies = {
        "spies_supply": 1,
        "spy_post_ids": ("arrakis-deep-desert", "arrakis-hagga-basin"),
    }
    state = _reveal_sale(_late(_base(**{"0": spies})), "shadow_warfare")
    conflict = state.players[0].troops_conflict
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=1)
    state = _act(state, "scouts_recall_spy", post_id="arrakis-deep-desert")
    state = _act(state, "scouts_recall_spy", post_id="arrakis-hagga-basin")
    assert state.players[0].troops_conflict == conflict + 3
    assert state.players[0].resources.spice == spice + 2


def test_betrayal_trades_bene_gesserit_influence_for_the_tleilaxu_track() -> None:
    config = RulesetConfig(arrakeen_scouts=True, immortality=True)
    state = ENGINE.reset(config, 21)
    resolver = ChanceResolver(seed=21)
    while isinstance(ENGINE.current_decision(state), ChanceDecision):
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = ENGINE.apply(state, resolver.resolve(decision)).state
    seat = replace(state.players[0], influence=Influence(bene_gesserit=2))
    state = replace(
        state,
        round_number=4,
        first_player=0,
        players=(seat, *state.players[1:]),
        decision_stack=(),
        scouts_opening=True,
    )
    start = state.players[0].tleilaxu_space
    state = _reveal(state, "betrayal")
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].influence.bene_gesserit == 1
    assert state.players[0].tleilaxu_space != start
    assert isinstance(state.players[0], PlayerState)


def test_royal_delegation_is_not_offered_at_the_top_of_the_emperor_track() -> None:
    """The user's arrow-cost ruling of 2026-09-29 (OQ-071, OQ-046): a line
    whose reward cannot happen is not offered, so a seat already at the top
    of the Emperor track (the gain would be lost, OQ-060) keeps its Solari."""
    state = _base(**{"0": {"influence": Influence(emperor=6)}})
    solari = state.players[0].resources.solari
    state = _takes_nothing(_reveal(state, "royal_delegation"), 0)
    assert _owner(state) == 1
    assert state.players[0].resources.solari == solari


def _water_discipline(**seat_fields: Any) -> GameState:
    """Seat 0 has taken Water Discipline's line and paid its water."""

    state = _reveal(_base(**seat_fields), "water_discipline")
    assert _owner(state) == 0
    state = _act(state, "scouts_choose_option", option=0)
    assert state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    return state


def test_water_discipline_may_draw_before_trashing_the_drawn_card() -> None:
    """OQ-100 (user ruling 2026-10-05): "아라킨 스카웃 효과 결정 때, 순서
    자유로". Icons of one line are independent effects whose order the owner
    picks once the arrow cost is paid (OQ-015 (d), [Main p. 9]): Water
    Discipline's card is drawn first and the drawn card is then trashed."""
    before = _base().players[0]
    state = _water_discipline()
    assert state.players[0].resources.water == before.resources.water - 1
    assert ("scouts_rewards_first", ()) in _offered(state)
    top_card = before.deck[0]
    state = _act(state, "scouts_rewards_first")
    seat = state.players[0]
    assert top_card in seat.hand and len(seat.hand) == len(before.hand) + 1
    # The trash icon is still open, now with the drawn card among its targets,
    # and the draw is not offered twice.
    assert state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    assert ("trash_optional_card", (("card_id", top_card),)) in _offered(state)
    assert ("scouts_rewards_first", ()) not in _offered(state)
    state = _act(state, "trash_optional_card", card_id=top_card)
    seat = state.players[0]
    assert top_card in seat.trashed and top_card not in seat.hand
    assert len(seat.hand) == len(before.hand)
    # The line closed with no second draw; the next seat chooses.
    assert any(
        e.kind == "scouts_effect_resolved" and dict(e.payload)["player"] == 0
        for e in state.event_log
    )
    assert _owner(state) == 1


def test_water_discipline_trash_first_leaves_the_draw_its_own_step() -> None:
    """User ruling 2026-10-10 (OQ-106, project convention): "그 외에는 전부
    나누자. 특히 카드 드로우는 나눠야하는게, 드로우 하기 전에 버림더미 카드를
    폐기하고 싶을 수 있잖아." The trash and the draw are separate icons of
    the line (OQ-100); trashing first no longer draws the card in the same
    step, so the trash stays undoable (OQ-010). The draw waits as the line's
    own ``scouts_rewards_first`` and nothing else is offered."""
    before = _base().players[0]
    state = _water_discipline()
    discarded = before.hand[0]
    state = _act(state, "trash_optional_card", card_id=discarded)
    seat = state.players[0]
    assert discarded in seat.trashed
    assert seat.deck == before.deck
    assert len(seat.hand) == len(before.hand) - 1
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    assert _offered(state) == [("scouts_rewards_first", ())]
    state = _act(state, "scouts_rewards_first")
    seat = state.players[0]
    assert before.deck[0] in seat.hand
    assert len(seat.hand) == len(before.hand)
    assert _owner(state) == 1


def test_rotating_doors_draws_with_its_arrow_cost() -> None:
    """The boundary of OQ-106: a choice among a line's costs is the price of
    what it buys, so Rotating Doors' "trash an Intrigue card -> [Intrigue]
    [draw 1]" stays one unit (the 2026-10-10 audit's arrow cost->reward
    units, kept by the user's instruction)."""
    base = _base()
    held = base.intrigue_deck[0]
    state = _reveal(
        replace(
            base,
            intrigue_deck=base.intrigue_deck[1:],
            players=(
                replace(base.players[0], intrigue_cards=(held,)),
                *base.players[1:],
            ),
        ),
        "rotating_doors",
    )
    assert _owner(state) == 0
    state = _act(state, "scouts_choose_option", option=0)
    hand = state.players[0].hand
    state = _act(state, "scouts_trash_intrigue", card_id=held)
    seat = state.players[0]
    assert len(seat.intrigue_cards) == 1 and held not in seat.intrigue_cards
    assert len(seat.hand) == len(hand) + 1
    assert not any(f.kind == FrameKind.SCOUTS_EFFECT for f in state.decision_stack)


def test_water_discipline_declined_trash_still_waits_for_the_draw() -> None:
    """Declining the trash icon is the line's choice too (OQ-106)."""
    before = _base().players[0]
    state = _act(_water_discipline(), "decline_optional_trash")
    assert state.players[0].hand == before.hand
    assert _offered(state) == [("scouts_rewards_first", ())]
    state = _act(state, "scouts_rewards_first")
    assert state.players[0].hand == (*before.hand, before.deck[0])
    assert _owner(state) == 1


def test_water_discipline_trashes_a_discard_card_before_the_draw_shuffles() -> None:
    """The user's reason for the split (OQ-106): with the deck empty, a card
    trashed from the discard pile before the draw stays out of the reshuffle
    the draw makes [Main p. 6]. Drawn once."""
    base = _base()
    seat0 = base.players[0]
    pile = (*seat0.deck, *seat0.discard_pile)
    state = _water_discipline(**{"0": {"deck": (), "discard_pile": pile}})
    trashed = pile[0]
    state = _act(state, "trash_optional_card", card_id=trashed)
    assert state.players[0].discard_pile == pile[1:]
    state = _act(state, "scouts_rewards_first")
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    assert trashed not in decision.options
    state = ENGINE.apply(
        state,
        ChanceOutcome(decision_id=decision.decision_id, values=decision.options),
    ).state
    seat = state.players[0]
    assert trashed in seat.trashed
    assert trashed not in (*seat.hand, *seat.deck, *seat.discard_pile)
    assert len(seat.hand) == len(seat0.hand) + 1
    assert _owner(state) == 1


def test_water_discipline_draw_first_reshuffles_under_the_open_trash() -> None:
    """With the deck empty the early draw shuffles the discard pile into a new
    deck [Main p. 6]; the trash icon waits above and then offers the drawn
    card."""
    base = _base()
    seat0 = base.players[0]
    pile = (*seat0.deck, *seat0.discard_pile)
    state = _water_discipline(**{"0": {"deck": (), "discard_pile": pile}})
    state = _act(state, "scouts_rewards_first")
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    state = ENGINE.apply(
        state,
        ChanceOutcome(decision_id=decision.decision_id, values=decision.options),
    ).state
    assert state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    seat = state.players[0]
    drawn = pile[0]
    assert seat.discard_pile == () and drawn in seat.hand
    assert ("trash_optional_card", (("card_id", drawn),)) in _offered(state)
    assert ("scouts_rewards_first", ()) not in _offered(state)
    state = _act(state, "decline_optional_trash")
    assert _owner(state) == 1
    assert len(state.players[0].hand) == len(seat0.hand) + 1


# OQ-105, user ruling 2026-10-10: "3은 그럼 통일해야지. 지휘관도 낼 수 있게
# 해야지". docs/rules/bloodlines.md 3: "Commander는 Conflict에서 strength 2인
# "troop"이다. troop을 대상으로 하는 효과(예: Go to Ground의 retreat)는
# Commander에도 적용된다." [Bloodlines p. 4]; a garrison Commander is one of
# the garrison's "up to two" units [Bloodlines p. 4]. Bene Gesserit
# Treachery: "각자 선택: garrison의 troop 1 잃기, 또는 Bene Gesserit −1"
# (docs/rules/arrakeen-scouts.md 6).
SCOUTS_BLOODLINES = RulesetConfig(arrakeen_scouts=True, bloodlines=True)


def _treachery(**seat0: Any) -> GameState:
    """Bene Gesserit Treachery revealed; no seat holds Bene Gesserit
    Influence, so the garrison troop is each seat's only line."""

    others = {str(seat): {"influence": Influence()} for seat in (1, 2, 3)}
    state = _base_for(
        SCOUTS_BLOODLINES, {"0": {"influence": Influence(), **seat0}, **others}
    )
    return _reveal(state, "bene_gesserit_treachery")


def test_bene_gesserit_treachery_takes_a_garrison_commander_alone() -> None:
    """A garrison holding only a Sardaukar Commander pays the troop line; the
    Commander goes back to its owner's supply (OQ-105)."""

    state = _treachery(troops_garrison=0, troops_supply=12, commanders_garrison=1)
    assert _owner(state) == 0
    assert _offered(state) == [("scouts_choose_option", (("option", 0),))]
    state = _act(state, "scouts_choose_option", option=0)
    seat = state.players[0]
    assert (seat.commanders_garrison, seat.commanders_supply) == (0, 1)
    assert (seat.troops_garrison, seat.troops_supply) == (0, 12)
    assert [
        dict(e.payload)
        for e in state.event_log
        if e.kind == "unit_lost" and dict(e.payload)["player"] == 0
    ] == [{"commanders": 1, "player": 0, "zone": "garrison"}]
    assert _owner(state) == 1


def test_bene_gesserit_treachery_asks_troop_or_commander_when_both() -> None:
    state = _treachery(troops_garrison=2, troops_supply=10, commanders_garrison=1)
    state = _act(state, "scouts_choose_option", option=0)
    assert _owner(state) == 0
    assert _offered(state) == [
        ("scouts_lose_garrison_unit", ()),
        ("scouts_lose_garrison_unit", (("commanders", 1),)),
    ]
    commander = _act(state, "scouts_lose_garrison_unit", commanders=1)
    seat = commander.players[0]
    assert (seat.troops_garrison, seat.commanders_garrison) == (2, 0)
    assert seat.commanders_supply == 1
    assert _owner(commander) == 1
    troop = _act(state, "scouts_lose_garrison_unit")
    seat = troop.players[0]
    assert (seat.troops_garrison, seat.commanders_garrison) == (1, 1)
    assert seat.troops_supply == 11
    assert _owner(troop) == 1


def test_bene_gesserit_treachery_with_troops_only_takes_a_troop_unasked() -> None:
    state = _treachery(troops_garrison=2, troops_supply=10)
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].troops_garrison == 1
    assert _owner(state) == 1  # no unit choice: the next seat is asked


def test_bene_gesserit_treachery_asks_a_seat_with_no_garrison_unit() -> None:
    from dune_imperium.display.scouts import scouts_choice_lines

    state = _treachery(troops_garrison=0, troops_supply=12)
    # Seat 0's line is greyed with its reason beside the confirm.
    info = scouts_choice_lines(state, 0, ENGINE.legal_actions(state, 0))
    assert info is not None
    lines = info["lines"]
    assert isinstance(lines, list)
    assert not lines[0]["enabled"] and lines[0]["reason"]
    state = _takes_nothing(state, 0)
    assert _owner(state) == 1
    # Seat 1 has troops: its troop line is enabled.
    info = scouts_choice_lines(state, 1, ENGINE.legal_actions(state, 1))
    assert info is not None
    lines = info["lines"]
    assert isinstance(lines, list)
    assert lines[0]["enabled"]
