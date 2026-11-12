"""Arrakeen Scouts on the original game: the missions that reuse the module's
mechanisms (stage P8b-2).

The app's original pools hold these missions (docs/rules/arrakeen-scouts.md
9a): Space Travel Deal, Muster an Army (Spice Incentive and Strongarmed
Alliance), Botanical Testing - Secrets in the Desert, Genetic Research, Guild
Maneuvers, Coordinate With The Emperor (the original wording, Immortality
only) and Sapho Juice. Each runs an Uprising mission's mechanism on the
original board's spaces.

The rules the tests quote:

- "임무로 놓인 조각은 라운드가 끝나도 남는다. 보상은 받을 때까지 유효하다."
  [Scouts help] (docs/rules/arrakeen-scouts.md 5).
- Participation is each seat's choice, in turn order; a seat that cannot pay
  is asked with the pass alone (OQ-088, OQ-131). A mission whose text has no
  "may" is not asked: each seat places its piece, and a seat that cannot place
  it places nothing (docs/rules/arrakeen-scouts.md 9a, OQ-088, OQ-161) --
  except that with Immortality a Strongarmed Alliance seat with an empty
  supply and a specimen is asked whether to return it first (9a, OQ-074 (a)).
- "세 번째 지배 칸에 marker가 필요한데 아직 Mentat 칸에 있으면 그것을 가져다
  쓰고, 그 좌석은 임무를 더 못 하며 spice를 받지 못한다" (9a; 5절 Prison
  Planet의 project convention과 같다).
- With Rise of Ix the app's pools drop the Muster missions (the half overlay
  covers Rally Troops [Main p. 18]) and Guild Maneuvers (9a).
"""

import json
from dataclasses import replace
from typing import Any

import pytest
from tests.unit.rules.test_combat import _answer_window

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.agent_turn_steps import (
    apply_placement,
    apply_whole,
    steps_after,
)
from dune_imperium.content.arrakeen_scouts import (
    MISSIONS_BY_ID,
    ScoutsPool,
    missions_for,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import known_card_seats
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash
from dune_imperium.display.scouts import scouts_choice_lines
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat import resolve_combat_rewards
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts_missions import mission_collectable
from dune_imperium.server.persistence import deserialize_step, serialize_step
from dune_imperium.simulation import run_random_game
from dune_imperium.simulation.sweep import run_checked_game

# Seated as named, so no Leader changes a cost and no Leader draft is dealt.
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
ORIGINAL = RulesetConfig(
    base_game=BaseGame.IMPERIUM, arrakeen_scouts=True, first_player_seat_zero=True
)
ORIGINAL_IMMORTALITY = replace(ORIGINAL, immortality=True)
ORIGINAL_BLOODLINES = replace(ORIGINAL, bloodlines=True)
ORIGINAL_BLOODLINES_IMMORTALITY = replace(ORIGINAL_BLOODLINES, immortality=True)
ORIGINAL_IX = replace(ORIGINAL, rise_of_ix=True)
ORIGINAL_IX_IMMORTALITY = replace(ORIGINAL_IX, immortality=True)

# Two earlier missions of one type, so that the round-3 mission may be of the
# other: the schedule's last mission differs in type from the one before
# [Scouts schedule]. Neither shares a family with a mission revealed below.
_TYPE_ZERO_FIRST = ((2, "space_travel_deal"), (2, "botanical_secrets_in_the_desert"))
_TYPE_ONE_FIRST = ((2, "genetic_research"), (2, "sapho_juice"))


def _start(config: RulesetConfig, seed: int = 31) -> GameState:
    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = apply_whole(ENGINE, state, chance.resolve(decision)).state
    return state


def _base(config: RulesetConfig = ORIGINAL, round_number: int = 3) -> GameState:
    """A Scouts step about to reveal a mission; seat 0 is First Player. Every
    seat holds its whole starting deck (any space it needs is in reach)."""

    state = _start(config)
    players = tuple(
        replace(
            player,
            resources=Resources(solari=12, spice=12, water=4),
            hand=(*player.hand, *player.deck),
            deck=(),
        )
        for player in state.players
    )
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        players=players,
        decision_stack=(),
        scouts_opening=True,
        # Round 3's single mission slot is the only one left to fill.
        scouts_mission_rounds=(2, 2, 3),
        scouts_revealed=_TYPE_ONE_FIRST,
    )


def _draw_decision(state: GameState) -> ChanceDecision:
    advanced = _advance_automatic(RuleResult(state=state)).state
    frame = advanced.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    assert isinstance(frame.decision, ChanceDecision)
    return frame.decision


def _reveal(state: GameState, mission_id: str, **fields: Any) -> GameState:
    """Reveal ``mission_id`` as the round-3 mission, the two earlier ones
    being of the other type."""

    earlier = (
        _TYPE_ONE_FIRST
        if MISSIONS_BY_ID[mission_id].mission_type == 0
        else _TYPE_ZERO_FIRST
    )
    fields.setdefault("scouts_revealed", earlier)
    decision = _draw_decision(replace(state, **fields))
    assert mission_id in decision.options, decision.options
    advanced = _advance_automatic(RuleResult(state=replace(state, **fields))).state
    return apply_whole(
        ENGINE,
        advanced,
        ChanceOutcome(decision_id=decision.decision_id, values=(mission_id,)),
    ).state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = ENGINE.whole_actions(state, seat)
    assert action in legal, (action, legal)
    return apply_whole(ENGINE, state, action, legal_actions=legal).state


def _answer(state: GameState, joins: dict[int, str]) -> GameState:
    """Answer every participation frame: join with ``joins[seat]`` or pass."""

    while state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION:
        seat = _owner(state)
        if seat in joins:
            state = _act(state, "scouts_join_mission", target=joins[seat])
        else:
            state = _act(state, "scouts_decline_mission")
    return state


def _asked(state: GameState) -> list[int]:
    """The seats asked to take part, passing each in turn."""

    seats = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION:
        seats.append(_owner(state))
        state = _act(state, "scouts_decline_mission")
    return seats


def _turn_for(state: GameState, seat: int = 0) -> GameState:
    """Give ``seat`` the turn (the Scouts step is over)."""

    return replace(
        state,
        scouts_opening=False,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id=f"round:{state.round_number}:turn:{seat}",
                decision=PlayerDecision(owner=seat, prompt="Choose a turn"),
            ),
        ),
    )


def _send_agent(state: GameState, space_id: str, seat: int = 0) -> GameState:
    placement = next(
        a
        for a in executable_placements(state, seat)
        if dict(a.arguments)["space_id"] == space_id
    )
    return apply_placement(ENGINE, state, placement).state


def _collect_actions(state: GameState, seat: int) -> list[DomainAction]:
    return [
        a
        for a in ENGINE.whole_actions(state, seat)
        if a.action_id == "scouts_collect_mission"
    ]


def _visit(
    state: GameState, space_id: str, seat: int = 0, choice: str = ""
) -> GameState:
    """``seat`` sends an Agent to ``space_id`` and collects its mission pieces."""

    state = _send_agent(_turn_for(state, seat), space_id, seat)
    offered = _collect_actions(state, seat)
    assert offered, ENGINE.whole_actions(state, seat)
    action = next(a for a in offered if dict(a.arguments)["choice"] == choice)
    return apply_whole(ENGINE, state, action).state


def _later_round(state: GameState) -> GameState:
    """The Agents are back, every card is in hand again and the seats can pay
    for any space, as in a later round; the missions' pieces stay where they
    are [Scouts help]."""

    return replace(
        state,
        players=tuple(
            replace(
                player,
                agents_available=2,
                agent_locations=(),
                resources=replace(player.resources, solari=12, spice=12, water=4),
                hand=(*player.hand, *player.discard_pile, *player.in_play),
                discard_pile=(),
                in_play=(),
            )
            for player in state.players
        ),
        decision_stack=(),
    )


def _no_mission_icon_on_a_later_visit(
    state: GameState, space_id: str, seat: int
) -> None:
    """In a later round ``seat`` sends an Agent to the space again: it offers no
    mission piece."""

    cleared = _later_round(state)
    assert not mission_collectable(cleared, seat, space_id)
    visited = _send_agent(_turn_for(cleared, seat), space_id, seat)
    assert _collect_actions(visited, seat) == []


def _taken(state: GameState) -> list[tuple[str, int]]:
    """The resources a mission paid, in order: each ``scouts_mission_goods_taken``
    follows the ``resources_gained`` that carried them."""

    taken: list[tuple[str, int]] = []
    log = state.event_log
    for index, event in enumerate(log):
        if event.kind != "scouts_mission_goods_taken":
            continue
        gained = dict(log[index - 1].payload)
        assert log[index - 1].kind == "resources_gained"
        ((resource, amount),) = (
            (key, value)
            for key, value in gained.items()
            if key in ("solari", "spice", "water")
        )
        taken.append((resource, int(str(amount))))
    return taken


def _no_question(state: GameState) -> bool:
    """No seat was asked: the step ended and the first turn is open."""

    return state.decision_stack[-1].kind == FrameKind.TURN


def _seat(state: GameState, seat: int, **fields: Any) -> GameState:
    return replace(
        state,
        players=tuple(
            replace(player, **fields) if player.player_id == seat else player
            for player in state.players
        ),
    )


# --- Space Travel Deal and Muster an Army - Spice Incentive ---------------------------


@pytest.mark.parametrize(
    ("mission_id", "space_id", "resource", "amount"),
    [
        ("space_travel_deal", "imperium_heighliner", "solari", 3),
        ("muster_spice_incentive", "rally_troops", "spice", 2),
    ],
)
def test_the_next_visitor_takes_the_banks_goods_and_a_second_visit_nothing(
    mission_id: str, space_id: str, resource: str, amount: int
) -> None:
    """The bank's goods wait on the space for whoever sends an Agent there
    next (the Secret Stash mechanism; docs/rules/arrakeen-scouts.md 9a): no
    seat is asked, nothing is parked, and the first visit takes them."""

    state = _reveal(_base(), mission_id)
    assert state.scouts_goods == ((mission_id, space_id, resource, amount, -1),)
    assert state.scouts_parked == ()
    assert _no_question(state)
    # Seat 2, not the First Player, is the next visitor.
    held = getattr(state.players[2].resources, resource)
    state = _visit(state, space_id, seat=2)
    assert state.scouts_goods == ()
    assert _taken(state) == [(resource, amount)]
    assert getattr(state.players[2].resources, resource) == held + amount
    for seat in range(4):
        assert not mission_collectable(state, seat, space_id)
    _no_mission_icon_on_a_later_visit(state, space_id, seat=0)


# --- Muster an Army - Strongarmed Alliance --------------------------------------------


def test_strongarmed_alliance_parks_every_seats_supply_troop_without_a_question() -> (
    None
):
    """Each seat must move one troop from its supply to the Rally Troops space
    (the app's text has no "may"; docs/rules/arrakeen-scouts.md 9a): no seat is
    asked. The seat's first Agent to Rally Troops deploys it to the Conflict
    beside the space's own effect; a second visit gives nothing."""

    base = _base()
    supply = [player.troops_supply for player in base.players]
    state = _reveal(base, "muster_strongarmed_alliance")
    assert _no_question(state)
    assert state.scouts_parked == tuple(
        ("muster_strongarmed_alliance", seat, "rally_troops", 1) for seat in range(4)
    )
    assert state.scouts_goods == ()
    for seat, player in enumerate(state.players):
        assert (player.troops_supply, player.troops_parked) == (supply[seat] - 1, 1)

    state = _visit(state, "rally_troops", seat=1)
    visitor = state.players[1]
    assert (visitor.troops_parked, visitor.troops_conflict) == (0, 1)
    assert [row[1] for row in state.scouts_parked] == [0, 2, 3]
    # The other seats' troops wait for their own first visit.
    assert mission_collectable(state, 0, "rally_troops")
    assert not mission_collectable(state, 1, "rally_troops")
    assert [e.kind for e in state.event_log if e.kind == "scouts_mission_troops"]
    _no_mission_icon_on_a_later_visit(state, "rally_troops", seat=1)


def test_a_seat_with_an_empty_supply_places_no_strongarmed_troop() -> None:
    """A seat with no troop in its supply parks nothing and is not asked
    (OQ-088, OQ-161, as Armed Escort's dreadnought)."""

    base = _base()
    seat = replace(base.players[1], troops_supply=0, troops_garrison=12)
    state = _reveal(_seat_with(base, 1, seat), "muster_strongarmed_alliance")
    assert _no_question(state)
    assert [row[1] for row in state.scouts_parked] == [0, 2, 3]
    assert state.players[1].troops_parked == 0
    assert not mission_collectable(state, 1, "rally_troops")
    assert mission_collectable(state, 0, "rally_troops")


def _seat_with(state: GameState, index: int, seat: Any) -> GameState:
    players = list(state.players)
    players[index] = seat
    return replace(state, players=tuple(players))


def test_an_empty_supply_with_a_specimen_is_asked_only_to_return_it() -> None:
    """9a (OQ-074 (a) 보강): "Immortality에서 supply가 비고 specimen이 있으면 그
    좌석은 먼저 specimen 1을 supply로 되돌릴 수 있다 — ... 그 선택만 묻는다". The
    seats with a supply troop are still not asked; the returned specimen is the
    troop the mission parks."""

    base = _base(ORIGINAL_IMMORTALITY)
    held = base.players[1]
    seat = replace(
        held,
        troops_supply=0,
        troops_garrison=held.troops_garrison + held.troops_supply - 2,
        specimens=2,
    )
    state = _reveal(_seat_with(base, 1, seat), "muster_strongarmed_alliance")
    # Seats 0, 2 and 3 parked their supply troop without a question.
    assert [row[1] for row in state.scouts_parked] == [0, 2, 3]
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION
    assert _owner(state) == 1
    assert ENGINE.whole_actions(state, 1) == (
        DomainAction(action_id="scouts_decline_mission", actor=1),
        DomainAction(
            action_id="scouts_return_specimens", actor=1, arguments=(("count", 1),)
        ),
    )
    codec = ActionCodec(ORIGINAL_IMMORTALITY)
    for action in ENGINE.legal_actions(state, 1):
        assert codec.decode(codec.encode(action), 1) == action
    # The page shows that one choice beside the pass.
    shown = scouts_choice_lines(state, 1, ENGINE.whole_actions(state, 1))
    assert shown is not None
    lines = shown["lines"]
    assert isinstance(lines, list)
    assert [(line["action_id"], line["enabled"]) for line in lines] == [
        ("scouts_return_specimens", True)
    ]
    state = _act(state, "scouts_return_specimens", count=1)
    assert _no_question(state)
    seat = state.players[1]
    assert (seat.specimens, seat.troops_supply, seat.troops_parked) == (1, 0, 1)
    assert [row[1] for row in state.scouts_parked] == [0, 2, 3, 1]
    assert mission_collectable(state, 1, "rally_troops")


def test_a_seat_may_keep_its_specimens_and_park_no_strongarmed_troop() -> None:
    base = _base(ORIGINAL_IMMORTALITY)
    held = base.players[1]
    seat = replace(
        held,
        troops_supply=0,
        troops_garrison=held.troops_garrison + held.troops_supply - 2,
        specimens=2,
    )
    state = _reveal(_seat_with(base, 1, seat), "muster_strongarmed_alliance")
    state = _act(state, "scouts_decline_mission")
    assert _no_question(state)
    assert [row[1] for row in state.scouts_parked] == [0, 2, 3]
    assert (state.players[1].specimens, state.players[1].troops_parked) == (2, 0)
    assert not mission_collectable(state, 1, "rally_troops")


def test_an_empty_supply_without_specimens_is_not_asked_for_strongarmed() -> None:
    base = _base(ORIGINAL_IMMORTALITY)
    held = base.players[1]
    seat = replace(
        held,
        troops_supply=0,
        troops_garrison=held.troops_garrison + held.troops_supply + held.specimens,
        specimens=0,
    )
    state = _reveal(_seat_with(base, 1, seat), "muster_strongarmed_alliance")
    assert _no_question(state)
    assert [row[1] for row in state.scouts_parked] == [0, 2, 3]


# --- Botanical Testing - Secrets in the Desert ----------------------------------------


def test_secrets_in_the_desert_hides_two_intrigue_cards_taken_by_two_visits() -> None:
    """The top two Intrigue cards wait face down on the Research Station;
    each of the next two visits may take one, and the same seat may take
    both (the English text rules, docs/rules/arrakeen-scouts.md 9a)."""

    base = _base()
    deck = base.intrigue_deck
    state = _reveal(base, "botanical_secrets_in_the_desert")
    assert _no_question(state)
    assert state.scouts_goods == ()
    assert state.scouts_goods_cards == tuple(
        ("botanical_secrets_in_the_desert", "imperium_research_station", card)
        for card in deck[:2]
    )
    assert state.intrigue_deck == deck[2:]
    known = known_card_seats(state)
    assert all(known[card] == frozenset() for card in deck[:2])

    held = len(state.players[0].intrigue_cards)
    state = _visit(state, "imperium_research_station", choice="take")
    assert state.players[0].intrigue_cards[-1] == deck[0]
    assert len(state.players[0].intrigue_cards) == held + 1
    assert [card for _, _, card in state.scouts_goods_cards] == [deck[1]]

    # A later visit by the same seat takes the second card.
    state = _visit(_later_round(state), "imperium_research_station", choice="take")
    assert state.players[0].intrigue_cards[-2:] == (deck[0], deck[1])
    assert state.scouts_goods_cards == ()
    _no_mission_icon_on_a_later_visit(state, "imperium_research_station", seat=0)


def test_a_visit_may_leave_the_secrets_card_where_it_is() -> None:
    """The text says the visitor may draw one: beside the take the visit is
    offered a decline, and the card stays for a later visit (the pieces stay
    until claimed [Scouts help]). Emperor's Schemes' text has no "may", so its
    take is the only action."""

    state = _reveal(_base(), "botanical_secrets_in_the_desert")
    deck = [card for _, _, card in state.scouts_goods_cards]
    visiting = _send_agent(_turn_for(state, 0), "imperium_research_station")
    assert sorted(
        dict(a.arguments)["choice"] for a in _collect_actions(visiting, 0)
    ) == [
        "decline",
        "take",
    ]
    held = len(state.players[0].intrigue_cards)
    state = _visit(state, "imperium_research_station", choice="decline")
    assert len(state.players[0].intrigue_cards) == held
    assert [card for _, _, card in state.scouts_goods_cards] == deck
    # The icon is spent; the visit offers nothing more of the mission.
    assert _collect_actions(state, 0) == []

    # The next seat to visit takes the first card.
    state = _visit(
        _later_round(state), "imperium_research_station", seat=1, choice="take"
    )
    assert state.players[1].intrigue_cards[-1] == deck[0]


def test_the_secrets_take_and_decline_rows_are_in_the_original_catalog_only() -> None:
    """The visit's mission icon opens the take and the decline as target rows
    (``choose_option``): the original game's Scouts catalog expresses both and
    an Uprising Scouts catalog, which never offers them, does not."""

    visiting = _send_agent(
        _turn_for(_reveal(_base(), "botanical_secrets_in_the_desert")),
        "imperium_research_station",
    )
    collect = next(
        a for a in ENGINE.legal_actions(visiting, 0) if a.action_id == "collect"
    )
    rows = ENGINE.legal_actions(ENGINE.apply(visiting, collect).state, 0)
    assert [dict(a.arguments)["option"] for a in rows] == ["take", "decline"]
    original = ActionCodec(ORIGINAL)
    uprising = ActionCodec(RulesetConfig(arrakeen_scouts=True))
    for row in rows:
        assert original.decode(original.encode(row), 0) == row
        with pytest.raises(ValueError, match="not present"):
            uprising.encode(row)


def test_secrets_in_the_desert_shuffles_the_discard_when_the_deck_is_short() -> None:
    """As Emperor's Schemes does (OQ-078, OQ-097): with fewer than two cards in
    the deck the discard is shuffled into a new deck first, through the
    Intrigue reshuffle chance frame, and the mission then places two."""

    base = _base()
    deck = base.intrigue_deck
    top, discard, rest = deck[0], deck[1:6], deck[6:]
    last = base.players[3]
    state = replace(
        base,
        intrigue_deck=(top,),
        intrigue_discard=discard,
        players=(
            *base.players[:3],
            replace(last, intrigue_cards=(*last.intrigue_cards, *rest)),
        ),
    )
    state = _reveal(state, "botanical_secrets_in_the_desert")
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.INTRIGUE_RESHUFFLE
    shuffle = frame.decision
    assert isinstance(shuffle, ChanceDecision)
    assert sorted(shuffle.options) == sorted(discard)
    assert state.scouts_goods_cards == ()
    order = tuple(reversed(discard))
    state = apply_whole(
        ENGINE, state, ChanceOutcome(decision_id=shuffle.decision_id, values=order)
    ).state
    assert tuple(card for _, _, card in state.scouts_goods_cards) == (top, order[0])
    assert state.intrigue_deck == order[1:]
    assert state.decision_stack[-1].kind == FrameKind.TURN


# --- Genetic Research -----------------------------------------------------------------


def test_genetic_research_moves_a_garrison_troop_and_two_solari_to_the_conflict() -> (
    None
):
    """Each seat may move a garrison troop to Selective Breeding with the
    bank's 2 Solari under it; its first visit gains the Solari and deploys
    the troop to the Conflict (docs/rules/arrakeen-scouts.md 9a)."""

    state = _reveal(_base(), "genetic_research")
    assert _owner(state) == 0
    joined = [
        dict(a.arguments)["target"]
        for a in ENGINE.whole_actions(state, 0)
        if a.action_id == "scouts_join_mission"
    ]
    assert joined == [""]
    garrison = state.players[0].troops_garrison
    state = _answer(state, {0: ""})
    seat = state.players[0]
    assert (seat.troops_garrison, seat.troops_parked) == (garrison - 1, 1)
    assert state.scouts_parked == (("genetic_research", 0, "selective_breeding", 1),)
    assert state.scouts_goods == (
        ("genetic_research", "selective_breeding", "solari", 2, 0),
    )
    # A seat that did not join has nothing there.
    assert not mission_collectable(state, 1, "selective_breeding")

    solari = state.players[0].resources.solari
    state = _visit(state, "selective_breeding")
    seat = state.players[0]
    assert (seat.troops_parked, seat.troops_conflict) == (0, 1)
    assert seat.resources.solari == solari + 2
    assert _taken(state) == [("solari", 2)]
    assert state.scouts_parked == () and state.scouts_goods == ()
    _no_mission_icon_on_a_later_visit(state, "selective_breeding", seat=0)


def test_a_seat_with_no_garrison_troop_is_asked_to_pass_for_genetic_research() -> None:
    base = _base()
    seat = replace(base.players[1], troops_garrison=0, troops_supply=12)
    state = _reveal(_seat_with(base, 1, seat), "genetic_research")
    state = _act(state, "scouts_join_mission", target="")
    assert _owner(state) == 1
    assert ENGINE.whole_actions(state, 1) == (
        DomainAction(action_id="scouts_decline_mission", actor=1),
    )


# --- Guild Maneuvers ------------------------------------------------------------------


def test_guild_maneuvers_pays_a_spice_for_two_troops_that_move_to_the_conflict() -> (
    None
):
    """Each seat may pay 1 spice and park 2 supply troops on Foldspace; its
    Agent there moves them to the Conflict (docs/rules/arrakeen-scouts.md
    9a)."""

    state = _reveal(_base(), "guild_maneuvers")
    seat = state.players[0]
    supply, spice = seat.troops_supply, seat.resources.spice
    state = _answer(state, {0: ""})
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked) == (supply - 2, 2)
    assert seat.resources.spice == spice - 1
    assert state.scouts_parked == (("guild_maneuvers", 0, "foldspace", 2),)
    assert state.scouts_goods == ()

    state = _visit(state, "foldspace")
    seat = state.players[0]
    assert (seat.troops_parked, seat.troops_conflict) == (0, 2)
    assert state.scouts_parked == ()
    _no_mission_icon_on_a_later_visit(state, "foldspace", seat=0)


def test_a_seat_without_the_spice_or_troops_passes_for_guild_maneuvers() -> None:
    base = _base()
    poor = replace(base.players[1], resources=Resources(solari=12, spice=0, water=4))
    few = replace(base.players[2], troops_supply=1, troops_garrison=11)
    state = _reveal(_seat_with(_seat_with(base, 1, poor), 2, few), "guild_maneuvers")
    state = _act(state, "scouts_decline_mission")
    for seat in (1, 2):
        assert _owner(state) == seat
        assert ENGINE.whole_actions(state, seat) == (
            DomainAction(action_id="scouts_decline_mission", actor=seat),
        )
        state = _act(state, "scouts_decline_mission")


def test_immortality_offers_the_specimen_shortfall_before_guild_maneuvers() -> None:
    """A seat short of the two supply troops may return specimens first
    ("at any time" [Immortality p. 8], OQ-074): the window offers the return
    beside the pass, and the seat joins once it has the troops."""

    base = _base(ORIGINAL_IMMORTALITY)
    held = base.players[0]
    seat = replace(
        held,
        troops_supply=1,
        troops_garrison=held.troops_garrison + held.troops_supply - 2,
        specimens=1,
    )
    state = _reveal(_seat_with(base, 0, seat), "guild_maneuvers")
    ids = [a.action_id for a in ENGINE.whole_actions(state, 0)]
    assert "scouts_join_mission" not in ids
    assert ids.count("scouts_return_specimens") == 1
    state = _act(state, "scouts_return_specimens", count=1)
    assert _owner(state) == 0
    state = _act(state, "scouts_join_mission", target="")
    assert (state.players[0].troops_parked, state.players[0].specimens) == (2, 0)


# --- Coordinate With The Emperor (the original game's) --------------------------------


def test_the_original_coordinate_with_the_emperor_needs_immortality() -> None:
    # After two missions of type 0 the round-3 mission is of type 1.
    def options(config: RulesetConfig) -> tuple[str, ...]:
        return _draw_decision(
            replace(_base(config), scouts_revealed=_TYPE_ZERO_FIRST)
        ).options

    plain = options(ORIGINAL)
    assert "imperium_coordinate_with_the_emperor" not in plain
    assert set(plain) == {"genetic_research", "sapho_juice", "guild_maneuvers"}
    immortal = options(ORIGINAL_IMMORTALITY)
    assert "imperium_coordinate_with_the_emperor" in immortal
    assert set(immortal) == {
        "genetic_research",
        "sapho_juice",
        "guild_maneuvers",
        "imperium_coordinate_with_the_emperor",
        "tleilaxu_offering",
    } - {"tleilaxu_offering"}


def test_the_original_coordinate_with_the_emperor_parks_a_specimen() -> None:
    """The Uprising mission's mechanism on Conspire: a specimen and the bank's
    2 Solari wait there; the first visit gains the Solari and recruits the
    troop to the garrison, as this turn's recruit."""

    base = _base(ORIGINAL_IMMORTALITY)
    seat = replace(
        base.players[0], specimens=1, troops_supply=base.players[0].troops_supply - 1
    )
    state = _reveal(_seat_with(base, 0, seat), "imperium_coordinate_with_the_emperor")
    state = _answer(state, {0: ""})
    seat = state.players[0]
    assert (seat.specimens, seat.troops_parked) == (0, 1)
    assert state.scouts_parked == (
        ("imperium_coordinate_with_the_emperor", 0, "conspire", 1),
    )
    assert state.scouts_goods == (
        ("imperium_coordinate_with_the_emperor", "conspire", "solari", 2, 0),
    )
    garrison = seat.troops_garrison
    state = _visit(state, "conspire")
    seat = state.players[0]
    assert (seat.troops_garrison, seat.troops_parked) == (garrison + 1, 0)
    assert _taken(state) == [("solari", 2)]
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    recruited = dict(frame.context)["troops_recruited"]
    assert isinstance(recruited, int) and recruited >= 1
    _no_mission_icon_on_a_later_visit(state, "conspire", seat=0)


def test_a_seat_without_a_specimen_passes_for_coordinate_with_the_emperor() -> None:
    state = _reveal(_base(ORIGINAL_IMMORTALITY), "imperium_coordinate_with_the_emperor")
    assert _owner(state) == 0
    assert ENGINE.whole_actions(state, 0) == (
        DomainAction(action_id="scouts_decline_mission", actor=0),
    )


# --- Sapho Juice ----------------------------------------------------------------------


def test_sapho_juice_puts_each_seats_control_marker_and_spice_on_the_mentat_space() -> (
    None
):
    """Each seat puts one of its own Control markers on Mentat with the bank's
    spice on it, with no question (docs/rules/arrakeen-scouts.md 9a); its Agent
    there takes the marker and the spice back, and a second visit gives
    nothing."""

    state = _reveal(_base(), "sapho_juice")
    assert _no_question(state)
    assert state.scouts_parked == ()
    for seat in range(4):
        assert sorted(row[2:] for row in state.scouts_goods if row[4] == seat) == [
            ("marker", 1, seat),
            ("spice", 1, seat),
        ]
    assert {row[1] for row in state.scouts_goods} == {"mentat"}

    spice = state.players[0].resources.spice
    state = _visit(state, "mentat")
    assert state.players[0].resources.spice == spice + 1
    assert _taken(state) == [("spice", 1)]
    assert [e.kind for e in state.event_log if e.kind == "scouts_marker_returned"]
    assert not [row for row in state.scouts_goods if row[4] == 0]
    # The other seats' markers wait for their own visits.
    assert len([row for row in state.scouts_goods if row[4] != 0]) == 6
    _no_mission_icon_on_a_later_visit(state, "mentat", seat=0)


def test_a_seat_with_no_free_control_marker_places_none_for_sapho_juice() -> None:
    """Three Control markers a seat have, one a control space each: a seat
    holding all three places nothing (Prison Planet's check, ``join_targets``)."""

    base = _base()
    held = _seat(base, 1, control_space_ids=("arrakeen", "carthag", "imperial_basin"))
    state = _reveal(held, "sapho_juice")
    assert _no_question(state)
    assert {row[4] for row in state.scouts_goods} == {0, 2, 3}
    assert not mission_collectable(state, 1, "mentat")
    # Two control spaces leave the third marker to put.
    two = _seat(base, 1, control_space_ids=("arrakeen", "carthag"))
    assert {row[4] for row in _reveal(two, "sapho_juice").scouts_goods} == {0, 1, 2, 3}


# Its first place takes control of the Imperial Basin [DI p. 16].
_BASIN_CONFLICT = "imperium_battle_for_imperial_basin"


def test_sapho_juices_marker_is_taken_back_for_a_third_control_space() -> None:
    """[Scouts help] (docs/rules/arrakeen-scouts.md 9a): taking control of a
    third space while the marker is still on the Mentat space takes that marker
    for the control space, and the mission gives that seat no spice. The
    original game's Conflict reward takes control through the same path as
    Uprising's."""

    base = _base()
    seat = replace(base.players[0], control_space_ids=("arrakeen", "carthag"))
    state = _reveal(_seat_with(base, 0, seat), "sapho_juice")
    assert sorted(row[2] for row in state.scouts_goods if row[4] == 0) == [
        "marker",
        "spice",
    ]
    players = [
        replace(player, combat_strength=strength)
        for player, strength in zip(state.players, (8, 6, 4, 0), strict=True)
    ]
    state = replace(
        state,
        players=tuple(players),
        phase=GamePhase.COMBAT,
        scouts_opening=False,
        decision_stack=(),
        conflict_deck=(
            *(c for c in state.conflict_deck if c != _BASIN_CONFLICT),
            *state.current_conflict_ids,
        ),
        current_conflict_ids=(_BASIN_CONFLICT,),
        combat_intrigue_complete=True,
    )
    opened = resolve_combat_rewards(state)
    answered = _answer_window(opened.state)
    after = answered.state
    assert after.players[0].control_space_ids == (
        "arrakeen",
        "carthag",
        "imperial_basin",
    )
    assert not [row for row in after.scouts_goods if row[4] == 0]
    taken = [
        dict(e.payload)
        for e in (*opened.events, *answered.events)
        if e.kind == "scouts_sapho_marker_taken"
    ]
    assert taken == [{"player": 0, "spice_returned": 1}]
    # The others' markers are still out.
    assert {row[4] for row in after.scouts_goods} == {1, 2, 3}


def test_a_second_control_space_leaves_the_sapho_marker_in_place() -> None:
    """With one marker out and one control space the seat still has a free
    marker for a second control space: the mission is not ended."""

    base = _base()
    seat = replace(base.players[0], control_space_ids=("arrakeen",))
    state = _reveal(_seat_with(base, 0, seat), "sapho_juice")
    players = [
        replace(player, combat_strength=strength)
        for player, strength in zip(state.players, (8, 6, 4, 0), strict=True)
    ]
    state = replace(
        state,
        players=tuple(players),
        phase=GamePhase.COMBAT,
        scouts_opening=False,
        decision_stack=(),
        conflict_deck=(
            *(c for c in state.conflict_deck if c != _BASIN_CONFLICT),
            *state.current_conflict_ids,
        ),
        current_conflict_ids=(_BASIN_CONFLICT,),
        combat_intrigue_complete=True,
    )
    answered = _answer_window(resolve_combat_rewards(state).state)
    after = answered.state
    assert after.players[0].control_space_ids == ("arrakeen", "imperial_basin")
    assert sorted(row[2] for row in after.scouts_goods if row[4] == 0) == [
        "marker",
        "spice",
    ]


# --- The pools ------------------------------------------------------------------------


def _round_two(config: RulesetConfig) -> GameState:
    state = _base(config, round_number=2)
    return replace(state, scouts_revealed=())


def test_rise_of_ix_drops_the_muster_missions_and_guild_maneuvers() -> None:
    """With Rise of Ix the app's original pools hold neither Muster an Army
    (the half overlay covers Rally Troops [Main p. 18]) nor Guild Maneuvers
    (docs/rules/arrakeen-scouts.md 9a), and add Rise of Ix's three; the draw
    offers exactly the pool's missions that fit its round."""

    missing = {
        "muster_spice_incentive",
        "muster_strongarmed_alliance",
        "guild_maneuvers",
    }
    for config in (ORIGINAL_IX, ORIGINAL_IX_IMMORTALITY):
        pool = {
            entry.mission_id
            for entry in missions_for(
                ScoutsPool.IMPERIUM_IMMORTALITY
                if config.immortality
                else ScoutsPool.IMPERIUM,
                choam=False,
                rise_of_ix=True,
            )
        }
        assert not pool & missing
        assert {"secret_stash", "armed_escort", "stowaways"} <= pool
        two = set(_draw_decision(_round_two(config)).options)
        assert two == {m for m in pool if MISSIONS_BY_ID[m].rounds[0] <= 2}
        three = set(_draw_decision(_base(config)).options)
        assert not three & missing
        assert three == {
            m
            for m in pool
            if MISSIONS_BY_ID[m].mission_type == 0
            and MISSIONS_BY_ID[m].rounds[1] >= 3
            and MISSIONS_BY_ID[m].app.family not in {3, 4}
        }
    # Without Rise of Ix the round-two draw holds the Muster pair, and the
    # round-three draw Guild Maneuvers.
    plain_two = set(_draw_decision(_round_two(ORIGINAL)).options)
    assert {"muster_spice_incentive", "muster_strongarmed_alliance"} <= plain_two
    assert "guild_maneuvers" not in plain_two
    three_after_type_zero = replace(_base(ORIGINAL), scouts_revealed=_TYPE_ZERO_FIRST)
    assert "guild_maneuvers" in set(_draw_decision(three_after_type_zero).options)


def test_the_round_two_draw_always_finds_an_original_mission() -> None:
    """The known gap since P8b-1: the original pools held no mission and the
    round-two draw raised "no mission can fill the schedule slot". Every slot
    of every schedule layout, with and without Immortality, Rise of Ix and
    CHOAM's absence, now has a candidate."""

    for config in (
        ORIGINAL,
        ORIGINAL_IMMORTALITY,
        ORIGINAL_IX,
        ORIGINAL_IX_IMMORTALITY,
    ):
        for rounds in ((2, 2, 3), (2, 3, 3)):
            state = replace(_base(config, round_number=2), scouts_mission_rounds=rounds)
            state = replace(state, scouts_revealed=())
            first = _draw_decision(state)
            assert first.options
            for pick in first.options:
                second_state = replace(
                    state,
                    round_number=rounds[1],
                    scouts_revealed=((2, pick),),
                )
                second = _draw_decision(second_state)
                assert second.options
                for pick_two in second.options:
                    third_state = replace(
                        second_state,
                        round_number=3,
                        scouts_revealed=((2, pick), (rounds[1], pick_two)),
                    )
                    assert _draw_decision(third_state).options, (
                        config.identifier,
                        rounds,
                        pick,
                        pick_two,
                    )


# --- Bloodlines: a Commander on the mission space -------------------------------------


@pytest.mark.parametrize(
    ("config", "mission_id", "space_id", "joins"),
    [
        (ORIGINAL_BLOODLINES, "muster_strongarmed_alliance", "rally_troops", {}),
        (ORIGINAL_BLOODLINES, "guild_maneuvers", "foldspace", {0: ""}),
        (ORIGINAL_BLOODLINES, "muster_spice_incentive", "rally_troops", {}),
    ],
)
def test_a_visit_resolves_the_commander_and_the_mission_pieces(
    config: RulesetConfig, mission_id: str, space_id: str, joins: dict[int, str]
) -> None:
    """The original board's Sardaukar Commanders sit on Conspire, Foldspace and
    Rally Troops [Bloodlines p. 3] (docs/rules/bloodlines.md 2a): a visit to
    one of them may buy the Commander and collects the mission pieces, as
    two effects of the visit in either order (a Bloodlines Uprising game does
    the same on Gather Support)."""

    state = _reveal(_base(config), mission_id)
    assert space_id in state.sardaukar_commander_space_ids
    state = _answer(state, joins)
    visiting = _send_agent(_turn_for(state, 0), space_id)
    ids = [a.action_id for a in ENGINE.whole_actions(visiting, 0)]
    assert "scouts_collect_mission" in ids
    assert "acquire_sardaukar_commander" in ids

    # The mission first, then the Commander.
    collected = apply_whole(ENGINE, visiting, _collect_actions(visiting, 0)[0]).state
    assert not mission_collectable(collected, 0, space_id)
    commander = next(
        a
        for a in ENGINE.whole_actions(collected, 0)
        if a.action_id == "acquire_sardaukar_commander"
    )
    bought = apply_whole(ENGINE, collected, commander).state
    assert bought.players[0].commanders_garrison == 1
    assert space_id not in bought.sardaukar_commander_space_ids

    # The Commander first, then the mission.
    commander = next(
        a
        for a in ENGINE.whole_actions(visiting, 0)
        if a.action_id == "acquire_sardaukar_commander"
    )
    bought = apply_whole(ENGINE, visiting, commander).state
    assert bought.players[0].commanders_garrison == 1
    mission_action = _collect_actions(bought, 0)
    assert mission_action
    both = apply_whole(ENGINE, bought, mission_action[0]).state
    assert not mission_collectable(both, 0, space_id)


def test_a_commander_on_conspire_and_the_original_coordinate_mission_both_resolve() -> (
    None
):
    base = _base(ORIGINAL_BLOODLINES_IMMORTALITY)
    seat = replace(
        base.players[0], specimens=1, troops_supply=base.players[0].troops_supply - 1
    )
    state = _reveal(_seat_with(base, 0, seat), "imperium_coordinate_with_the_emperor")
    assert "conspire" in state.sardaukar_commander_space_ids
    state = _answer(state, {0: ""})
    visiting = _send_agent(_turn_for(state, 0), "conspire")
    ids = [a.action_id for a in ENGINE.whole_actions(visiting, 0)]
    assert {"scouts_collect_mission", "acquire_sardaukar_commander"} <= set(ids)
    collected = apply_whole(ENGINE, visiting, _collect_actions(visiting, 0)[0]).state
    assert collected.players[0].troops_parked == 0
    assert "acquire_sardaukar_commander" in [
        a.action_id for a in ENGINE.whole_actions(collected, 0)
    ]


# --- Whole games ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "config",
    [
        ORIGINAL,
        ORIGINAL_IMMORTALITY,
        ORIGINAL_IX,
        ORIGINAL_BLOODLINES,
    ],
    ids=lambda config: config.identifier,
)
@pytest.mark.parametrize(("seed", "policy"), [(4, "random"), (9, "heuristic")])
def test_an_original_scouts_game_plays_to_the_end(
    config: RulesetConfig, seed: int, policy: str
) -> None:
    """The original game's pools hold their missions now, so the round-two draw
    no longer runs dry: games on either pool, with the checks of the sweep
    (state invariants, privacy, replay and a sample of codec soundness),
    finish."""

    report = run_checked_game(config, seed, seed, policy=policy, soundness_interval=6)
    assert report.rounds >= 3


@pytest.mark.parametrize("config", [ORIGINAL, ORIGINAL_IMMORTALITY])
def test_a_random_original_game_reveals_three_missions_of_its_pool(
    config: RulesetConfig,
) -> None:
    from dune_imperium.content.arrakeen_scouts import scouts_pool
    from dune_imperium.rules.scouts import item_kind

    state = run_random_game(UprisingRulesEngine(), config, 12, 13).state
    assert state.phase is GamePhase.FINISHED
    missions = [
        item for _, item in state.scouts_revealed if item_kind(item) == "mission"
    ]
    pool = {
        entry.mission_id for entry in missions_for(scouts_pool(config), choam=False)
    }
    assert len(missions) == 3
    assert set(missions) <= pool
    assert len({MISSIONS_BY_ID[mission].app.family for mission in missions}) == 3


# --- Botanical Testing - Stationed Support (stage P8c) --------------------------------


def test_stationed_support_discards_a_chosen_card_and_parks_two_troops() -> None:
    """9a: "각자 원하면 손의 카드 1장을 버리고 supply의 troop 2를 Research Station
    칸에 세운다". The join opens the Scouts line whose cost is the card the seat
    picks (``scouts_discard``); the troops are parked after the discard."""

    state = _reveal(_base(), "botanical_stationed_support")
    seat = state.players[0]
    supply, hand = seat.troops_supply, seat.hand
    assert ENGINE.whole_actions(state, 0) == (
        DomainAction(action_id="scouts_decline_mission", actor=0),
        DomainAction(
            action_id="scouts_join_mission", actor=0, arguments=(("target", ""),)
        ),
    )
    state = _act(state, "scouts_join_mission", target="")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    assert _owner(state) == 0
    offered = ENGINE.whole_actions(state, 0)
    assert {a.action_id for a in offered} == {"scouts_discard"}
    assert {dict(a.arguments)["card_id"] for a in offered} == set(hand)
    card = hand[-1]
    state = _act(state, "scouts_discard", card_id=card)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked) == (supply - 2, 2)
    assert card not in seat.hand and card in seat.discard_pile
    assert len(seat.hand) == len(hand) - 1
    assert state.scouts_parked == (
        ("botanical_stationed_support", 0, "imperium_research_station", 2),
    )
    # The next seat is asked next.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION
    assert _owner(state) == 1


def test_stationed_supports_discard_rows_are_in_the_original_catalog() -> None:
    state = _act(
        _reveal(_base(), "botanical_stationed_support"),
        "scouts_join_mission",
        target="",
    )
    codec = ActionCodec(ORIGINAL)
    for action in ENGINE.legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action


def test_an_empty_hand_can_only_pass_stationed_support() -> None:
    """OQ-088: "비용을 낼 수 없거나 세울 troop이 없는 좌석" cannot take part; it is
    asked with the pass alone (OQ-131)."""

    base = _base()
    empty = replace(
        base.players[0],
        discard_pile=(*base.players[0].discard_pile, *base.players[0].hand),
        hand=(),
    )
    state = _reveal(_seat_with(base, 0, empty), "botanical_stationed_support")
    assert ENGINE.whole_actions(state, 0) == (
        DomainAction(action_id="scouts_decline_mission", actor=0),
    )
    supply = state.players[0].troops_supply
    state = _act(state, "scouts_decline_mission")
    assert state.players[0].troops_supply == supply
    assert state.players[0].troops_parked == 0


def test_stationed_supports_first_visit_deploys_its_troops() -> None:
    state = _reveal(_base(), "botanical_stationed_support")
    state = _act(state, "scouts_join_mission", target="")
    state = _act(state, "scouts_discard", card_id=state.players[0].hand[0])
    state = _asked_after(state)
    state = _visit(_later_round(state), "imperium_research_station")
    seat = state.players[0]
    assert (seat.troops_parked, seat.troops_conflict) == (0, 2)
    assert state.scouts_parked == ()
    deployed = [
        dict(e.payload) for e in state.event_log if e.kind == "scouts_mission_troops"
    ]
    assert deployed[-1]["to"] == "conflict"
    _no_mission_icon_on_a_later_visit(state, "imperium_research_station", seat=0)


def _asked_after(state: GameState) -> GameState:
    """Every later seat passes the mission."""

    while state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION:
        state = _act(state, "scouts_decline_mission")
    return state


def test_immortality_tops_up_the_supply_before_stationed_support() -> None:
    """A seat short of the two supply troops may return specimens first
    (OQ-074, 5: "Immortality에서는 supply에 모자란 만큼 specimen을 supply로
    되돌려 채울 수 있다"), then joins and discards."""

    base = _base(ORIGINAL_IMMORTALITY)
    held = base.players[0]
    seat = replace(
        held,
        troops_supply=1,
        troops_garrison=held.troops_garrison + held.troops_supply - 2,
        specimens=1,
    )
    state = _reveal(_seat_with(base, 0, seat), "botanical_stationed_support")
    ids = [a.action_id for a in ENGINE.whole_actions(state, 0)]
    assert "scouts_join_mission" not in ids
    assert ids.count("scouts_return_specimens") == 1
    state = _act(state, "scouts_return_specimens", count=1)
    state = _act(state, "scouts_join_mission", target="")
    state = _act(state, "scouts_discard", card_id=state.players[0].hand[0])
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked, seat.specimens) == (0, 2, 0)


def test_an_empty_hand_gets_no_specimen_top_up_either() -> None:
    base = _base(ORIGINAL_IMMORTALITY)
    held = base.players[0]
    seat = replace(
        held,
        troops_supply=1,
        troops_garrison=held.troops_garrison + held.troops_supply - 2,
        specimens=1,
        discard_pile=(*held.discard_pile, *held.hand),
        hand=(),
    )
    state = _reveal(_seat_with(base, 0, seat), "botanical_stationed_support")
    assert ENGINE.whole_actions(state, 0) == (
        DomainAction(action_id="scouts_decline_mission", actor=0),
    )


# --- Stationed Support's order: the discard first, then the parking (P8c-2) --------

TREACHERY = "imperium:treachery:0"


def _with_card_in_hand(state: GameState, card: str) -> GameState:
    """``card`` out of the Row and the deck, into seat 0's hand."""

    state = replace(
        state,
        imperium_row=tuple(c for c in state.imperium_row if c != card),
        imperium_deck=tuple(c for c in state.imperium_deck if c != card),
    )
    held = state.players[0]
    return _seat_with(state, 0, replace(held, hand=(card, *held.hand)))


def _supply_of(state: GameState, supply: int, specimens: int = 0) -> GameState:
    """Seat 0 with ``supply`` supply troops and ``specimens`` specimens (the
    rest of its twelve in the garrison)."""

    held = state.players[0]
    outside = held.troops_garrison + held.troops_supply
    seat = replace(
        held,
        troops_supply=supply,
        specimens=specimens,
        troops_garrison=outside - supply - specimens,
    )
    return _seat_with(state, 0, seat)


def _stationed_join(state: GameState) -> GameState:
    return _act(state, "scouts_join_mission", target="")


def test_stationed_support_pays_its_discard_before_it_parks_the_troops() -> None:
    """9a: "버리기가 비용이라 먼저다("비용은 효과보다 먼저" [DI p. 9])". Between
    the join and the discard nothing is parked and the supply is whole; the
    log then reads the discard first and the parking after it."""

    state = _stationed_join(_reveal(_base(), "botanical_stationed_support"))
    seat = state.players[0]
    supply = seat.troops_supply
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    assert (seat.troops_supply, seat.troops_parked) == (supply, 0)
    assert state.scouts_parked == ()
    card = seat.hand[0]
    state = _act(state, "scouts_discard", card_id=card)
    kinds = [event.kind for event in state.event_log]
    joined = kinds.index("scouts_mission_joined")
    discarded = kinds.index("card_discarded")
    parked = kinds.index("scouts_mission_troops_parked")
    assert joined < discarded < parked
    (event,) = [e for e in state.event_log if e.kind == "scouts_mission_troops_parked"]
    assert dict(event.payload) == {
        "count": 2,
        "mission_id": "botanical_stationed_support",
        "player": 0,
    }
    assert state.players[0].troops_supply == supply - 2


def test_an_unload_card_that_deploys_supply_troops_leaves_fewer_to_park() -> None:
    """Rise of Ix: a discarded card's Unload resolves completely before the
    effect ("비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한
    뒤 오른쪽으로 간다", docs/rules/rise-of-ix.md 7), and Treachery's Unload
    deploys two supply troops to the Conflict. The seat then parks what its
    supply holds (9a: "그 사이 supply가 2보다 적어지면 있는 만큼만 세운다",
    OQ-030, OQ-074 (a))."""

    state = _with_card_in_hand(_base(ORIGINAL_IX), TREACHERY)
    state = _supply_of(state, 3)
    state = _stationed_join(_reveal(state, "botanical_stationed_support"))
    state = _act(state, "scouts_discard", card_id=TREACHERY)
    seat = state.players[0]
    assert TREACHERY in seat.discard_pile
    assert seat.troops_conflict == 2  # the Unload's deployment came first
    assert (seat.troops_supply, seat.troops_parked) == (0, 1)
    assert state.scouts_parked == (
        ("botanical_stationed_support", 0, "imperium_research_station", 1),
    )
    kinds = [event.kind for event in state.event_log]
    assert kinds.index("card_unloaded") < kinds.index("scouts_mission_troops_parked")


def test_a_supply_emptied_by_the_unload_parks_nothing() -> None:
    """Two supply troops, both deployed by Treachery's Unload: nothing is left
    to park (OQ-030), and the log says so."""

    state = _with_card_in_hand(_base(ORIGINAL_IX), TREACHERY)
    state = _supply_of(state, 2)
    state = _stationed_join(_reveal(state, "botanical_stationed_support"))
    state = _act(state, "scouts_discard", card_id=TREACHERY)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked, seat.troops_conflict) == (0, 0, 2)
    assert state.scouts_parked == ()
    (event,) = [e for e in state.event_log if e.kind == "scouts_mission_troops_parked"]
    assert dict(event.payload)["count"] == 0
    # The seat took part: the next seat is asked.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION
    assert _owner(state) == 1


def test_immortality_tops_up_a_supply_the_unload_emptied_before_it_parks() -> None:
    """With Immortality a seat asked to park more troops than its supply holds
    may first return specimens for the shortfall (9a; OQ-074 (a), OQ-088):
    after Treachery's Unload took two of three supply troops, one specimen
    returned makes the two it parks."""

    state = _with_card_in_hand(_base(ORIGINAL_IX_IMMORTALITY), TREACHERY)
    state = _supply_of(state, 3, specimens=2)
    state = _stationed_join(_reveal(state, "botanical_stationed_support"))
    state = _act(state, "scouts_discard", card_id=TREACHERY)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_conflict) == (1, 2)
    offered = ENGINE.whole_actions(state, 0)
    assert [(a.action_id, dict(a.arguments)["count"]) for a in offered] == [
        ("scouts_return_specimens", 0),
        ("scouts_return_specimens", 1),
    ]
    state = _act(state, "scouts_return_specimens", count=1)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked, seat.specimens) == (0, 2, 1)
    assert state.scouts_parked == (
        ("botanical_stationed_support", 0, "imperium_research_station", 2),
    )


def test_a_seat_may_decline_the_top_up_and_park_what_the_supply_holds() -> None:
    """"may first return": returning none is an answer, and the seat parks the
    one troop that is left."""

    state = _with_card_in_hand(_base(ORIGINAL_IX_IMMORTALITY), TREACHERY)
    state = _supply_of(state, 3, specimens=2)
    state = _stationed_join(_reveal(state, "botanical_stationed_support"))
    state = _act(state, "scouts_discard", card_id=TREACHERY)
    state = _act(state, "scouts_return_specimens", count=0)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked, seat.specimens) == (0, 1, 2)


def test_without_a_specimen_the_shortfall_is_parked_short_unasked() -> None:
    """Immortality but no specimen to return: nothing to ask."""

    state = _with_card_in_hand(_base(ORIGINAL_IX_IMMORTALITY), TREACHERY)
    state = _supply_of(state, 3, specimens=0)
    state = _stationed_join(_reveal(state, "botanical_stationed_support"))
    state = _act(state, "scouts_discard", card_id=TREACHERY)
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked) == (0, 1)
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION


# --- Stationed Support with an Unload card whose Unload is a decision --------------

FLEET = "imperium:freighter_fleet:0"
COMPACT = "imperium:ix_guild_compact:0"
_NEGOTIATOR = "negotiator"


def _parked_events(state: GameState) -> list[dict[str, Any]]:
    return [
        dict(e.payload)
        for e in state.event_log
        if e.kind == "scouts_mission_troops_parked"
    ]


def _unload_start(card: str, supply: int) -> GameState:
    """The Stationed Support join is asked of seat 0, who holds ``card`` (an
    Unload card) with ``supply`` troops in its supply."""

    state = _supply_of(_with_card_in_hand(_base(ORIGINAL_IX), card), supply)
    return _reveal(state, "botanical_stationed_support")


def _recorded(
    state: GameState, action_id: str, **arguments: Any
) -> tuple[GameState, tuple[DomainAction, ...]]:
    """``_act``'s whole action and the steps it took: what a save records."""

    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    assert action in ENGINE.whole_actions(state, seat), (action_id, arguments)
    steps: list[DomainAction] = []
    while True:
        rows = ENGINE.legal_actions(state, seat)
        left = 0 if action in rows else steps_after(state, action)
        row = action if action in rows else first_step(state, action)
        assert row in rows
        state = ENGINE.apply(state, row).state
        steps.append(row)
        if left == 0:
            return state, tuple(steps)


def _loaded(start: GameState, steps: tuple[DomainAction, ...]) -> GameState:
    """A save writes the steps from its start as JSON (``server.persistence``)
    and a load replays them (the steps of ``tests/unit/rules/
    test_ix_unload_hold_paths.py``'s ``_loaded``)."""

    saved = json.dumps([serialize_step(step) for step in steps])
    state = start
    for index, value in enumerate(json.loads(saved)):
        state = ENGINE.apply(state, deserialize_step(value, index)).state
    return state


@pytest.mark.parametrize("answer", ["advance_freighter", "decline_freighter"])
def test_stationed_support_parks_nothing_while_a_freighters_unload_is_open(
    answer: str,
) -> None:
    """Freighter Fleet's Unload is the Freighter's move, a decision of its own
    ("you may move your Freighter in one of two ways", [Rise of Ix p. 5]). "비용
    → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (docs/rules/rise-of-ix.md 7), and Stationed Support's discard
    is the cost, its parking the right side (docs/rules/arrakeen-scouts.md 9a):
    while the move is open no troop is parked and the supply is whole; once the
    seat answers, either way, the two troops are parked, once."""

    state = _unload_start(FLEET, 12)
    state = _stationed_join(state)
    supply = state.players[0].troops_supply
    state = _act(state, "scouts_discard", card_id=FLEET)

    assert state.decision_stack[-1].kind == FrameKind.FREIGHTER_MOVE
    assert _owner(state) == 0
    assert {a.action_id for a in ENGINE.whole_actions(state, 0)} == {
        "advance_freighter",
        "decline_freighter",
    }
    codec = ActionCodec(ORIGINAL_IX)
    for row in ENGINE.legal_actions(state, 0):
        assert codec.decode(codec.encode(row), 0) == row
    seat = state.players[0]
    assert FLEET in seat.discard_pile
    assert (seat.troops_supply, seat.troops_parked) == (supply, 0)
    assert state.scouts_parked == ()
    assert _parked_events(state) == []

    state = _act(state, answer)
    seat = state.players[0]
    assert seat.freighter_space == (1 if answer == "advance_freighter" else 0)
    assert (seat.troops_supply, seat.troops_parked) == (supply - 2, 2)
    assert state.scouts_parked == (
        ("botanical_stationed_support", 0, "imperium_research_station", 2),
    )
    assert _parked_events(state) == [
        {"count": 2, "mission_id": "botanical_stationed_support", "player": 0}
    ]
    kinds = [event.kind for event in state.event_log]
    assert kinds.index("card_unloaded") < kinds.index("scouts_mission_troops_parked")
    if answer == "advance_freighter":
        assert kinds.index("freighter_moved") < kinds.index(
            "scouts_mission_troops_parked"
        )
    # The seat took part: the next seat is asked.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION
    assert _owner(state) == 1


@pytest.mark.parametrize("placed", [0, 1, 2])
def test_an_unload_decision_that_takes_supply_troops_leaves_fewer_to_park(
    placed: int,
) -> None:
    """Ix-Guild Compact's Unload is two Tech Negotiation icons, each "you may
    take a troop from your supply and place it on the Ix board" ([Rise of Ix
    p. 4]): decisions that spend the supply. They are answered completely
    before Stationed Support parks (docs/rules/rise-of-ix.md 7), which parks
    what the supply then holds (9a: "그 사이 supply가 2보다 적어지면 있는 만큼만
    세운다", OQ-030, OQ-074 (a)): of three supply troops, the Negotiators first
    and then the parking take what is left, never more."""

    state = _stationed_join(_unload_start(COMPACT, 3))
    negotiators = state.players[0].negotiators
    state = _act(state, "scouts_discard", card_id=COMPACT)
    assert state.decision_stack[-1].kind == FrameKind.UNLOAD_ICONS
    seat = state.players[0]
    assert (seat.troops_supply, seat.troops_parked) == (3, 0)

    for icon in range(2):
        # Open while any icon is: nothing parked, the owner the only asked.
        assert state.decision_stack[-1].kind == FrameKind.UNLOAD_ICONS
        assert _owner(state) == 0
        assert state.scouts_parked == () and _parked_events(state) == []
        state = _act(
            state,
            "resolve_unload_icon" if icon < placed else "decline_unload_icon",
            card_id=COMPACT,
            effect=_NEGOTIATOR,
        )

    parked = min(2, 3 - placed)
    seat = state.players[0]
    assert seat.negotiators == negotiators + placed
    assert (seat.troops_supply, seat.troops_parked) == (3 - placed - parked, parked)
    assert _parked_events(state) == [
        {"count": parked, "mission_id": "botanical_stationed_support", "player": 0}
    ]
    assert state.scouts_parked == (
        ("botanical_stationed_support", 0, "imperium_research_station", parked),
    )
    kinds = [event.kind for event in state.event_log]
    if placed:
        assert kinds.index("negotiator_placed") < kinds.index(
            "scouts_mission_troops_parked"
        )
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION
    assert _owner(state) == 1


@pytest.mark.parametrize(
    ("card", "supply", "answers", "parked"),
    [
        (FLEET, 12, [("advance_freighter", {})], 2),
        (
            COMPACT,
            3,
            [
                ("resolve_unload_icon", {"card_id": COMPACT, "effect": _NEGOTIATOR}),
                ("resolve_unload_icon", {"card_id": COMPACT, "effect": _NEGOTIATOR}),
            ],
            1,
        ),
    ],
    ids=["freighter-fleet", "ix-guild-compact"],
)
def test_a_save_made_with_the_unload_open_resumes_in_it_and_parks_once(
    card: str, supply: int, answers: list[tuple[str, dict[str, str]]], parked: int
) -> None:
    """A save is the steps of the game, replayed on a load. Saved with the
    Unload's decision open (right after the discard, and between the two
    Negotiators), the loaded game is in the same window with the same rows,
    nothing parked; answered, it parks exactly what the unsaved game does."""

    start = _unload_start(card, supply)
    state = start
    steps: tuple[DomainAction, ...] = ()
    waiting: list[tuple[GameState, tuple[DomainAction, ...], int]] = []
    plan = [
        ("scouts_join_mission", {"target": ""}),
        ("scouts_discard", {"card_id": card}),
        *answers,
    ]
    for index, (action_id, arguments) in enumerate(plan):
        state, taken = _recorded(state, action_id, **arguments)
        steps = (*steps, *taken)
        if 1 <= index < len(plan) - 1:
            waiting.append((state, steps, index + 1))
    done = state
    assert _parked_events(done) == [
        {"count": parked, "mission_id": "botanical_stationed_support", "player": 0}
    ]
    assert len(waiting) == len(answers)

    for open_state, saved_steps, resume_from in waiting:
        loaded = _loaded(start, saved_steps)
        assert canonical_state_hash(loaded) == canonical_state_hash(open_state)
        assert loaded.decision_stack[-1].kind == open_state.decision_stack[-1].kind
        assert ENGINE.whole_actions(loaded, 0) == ENGINE.whole_actions(open_state, 0)
        assert loaded.scouts_parked == () and _parked_events(loaded) == []
        for action_id, arguments in plan[resume_from:]:
            loaded = _act(loaded, action_id, **arguments)
        assert canonical_state_hash(loaded) == canonical_state_hash(done)
        assert _parked_events(loaded) == _parked_events(done)

    # Saved once everything is answered, the game replays to the same state.
    assert canonical_state_hash(_loaded(start, steps)) == canonical_state_hash(done)
