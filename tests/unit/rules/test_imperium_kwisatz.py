"""The original game's Kwisatz Haderach (stage P3).

The printed values are the Steam app's attribute table and card text (cost
8, 1 copy, Bene Gesserit, no Agent icons, no Reveal values; Agent: "Send one
of your Agents from anywhere to ANY board space (even if occupied)." and
[draw 1]; docs/base-game-and-ix-plan.md 2.4). The rulings are
docs/rules/imperium-base.md:

- 13.1 [DI p. 13]: "Kwisatz Haderach — Agent가 남지 않아도 낼 수 있다(이미
  칸에 있는 Agent를 보낸다). 방금 있던 칸으로 되돌려 보낼 수 있다. 게임에 한
  번인 칸(High Council, Swordmaster)에 두 번 보낼 수 없고, The Voice를 넘지
  못한다. Maker 칸을 떠난 뒤 Phase 4까지 비어 있으면 bonus spice가 쌓인다.
  디자이너 판정: Agent를 먼저 놓고 카드를 뽑는다; Interstellar Shipping·Sietch
  Tabr의 Influence 요구는 넘지 못한다".
- 16: "Kwisatz Haderach는 내 다른 Agent가 있는 칸에도 보낼 수 있다("ANY board
  space (even if occupied)" [Kwisatz Haderach card]; 앱도 같다)."
- 9 and OQ-139 (가): the Mentat a seat took is one of its Agents for all
  purposes ("Kwisatz Haderach가 Mentat을 옮길 수 있다"); the engine does not
  tell it apart from the seat's other Agents.

A send from a board space names it as the placement's ``from_space``; a send
from the Leader names none.
"""

from dataclasses import replace

from tests.unit.rules import test_graft_boxes as graft_tests

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.core.engine import RuleResult, Transition
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.board_table import board_spaces_on_table
from dune_imperium.rules.effects import recall_board_agent
from dune_imperium.rules.phases import resolve_makers, resolve_recall_or_endgame

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
KWISATZ = "imperium:kwisatz_haderach:0"
# City only: Arrakeen, Carthag and the Research Station (2 water).
RECRUITER = "imperium:arrakis_recruiter:0"
_TURN_STEPS = (
    "resolve_board_effect",
    "resolve_faction_influence",
    "harvest_maker_spice",
    "resolve_agent_card_effect",
    "draw_owed_card",
    "draw_owed_intrigue",
)


def _start(seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an original game at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _kwisatz_turn(
    *, hand: tuple[str, ...] = (KWISATZ,), **seat_zero: object
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 on turn with ``hand`` and ``seat_zero``'s fields."""

    engine, state = _start()
    return engine, _seat(state, 0, hand=hand, **seat_zero)


def _rows(state: GameState, seat: int = 0) -> list[dict[str, object]]:
    """Kwisatz Haderach's placements, as argument mappings."""

    return [
        dict(placement.arguments)
        for placement in executable_placements(state, seat)
        if dict(placement.arguments)["card_id"] == KWISATZ
    ]


def _destinations(state: GameState, from_space: str | None = None) -> set[str]:
    return {
        str(row["space_id"])
        for row in _rows(state)
        if row.get("from_space") == from_space
    }


def _send(
    engine: UprisingRulesEngine,
    state: GameState,
    space_id: str,
    from_space: str | None = None,
) -> RuleResult:
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == KWISATZ
        and dict(placement.arguments)["space_id"] == space_id
        and dict(placement.arguments).get("from_space") == from_space
    )
    return apply_placement(engine, state, placement)


def _do(engine: UprisingRulesEngine, state: GameState, action_id: str) -> Transition:
    action = next(
        action
        for action in engine.whole_actions(state, 0)
        if action.action_id == action_id
    )
    return apply_whole(engine, state, action)


def _resolve_all(engine: UprisingRulesEngine, state: GameState) -> GameState:
    """Resolve every effect the turn still owes, in the offered order."""

    for _ in range(14):
        steps = [
            action
            for action in engine.whole_actions(state, 0)
            if action.action_id in _TURN_STEPS
        ]
        if not steps:
            return state
        state = apply_whole(engine, state, steps[0]).state
    raise AssertionError("the turn kept owing effects")


def _finish(engine: UprisingRulesEngine, state: GameState) -> GameState:
    resolved = _resolve_all(engine, state)
    return _do(engine, resolved, "finish_agent_turn").state


# --- The card ------------------------------------------------------------------


def test_kwisatz_haderach_matches_the_app_table_and_text() -> None:
    entry = IMPERIUM_CARDS_BY_ID["kwisatz_haderach"]
    assert entry.card.name == "Kwisatz Haderach"
    assert (entry.acquisition_cost, entry.copies) == (8, 1)
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == ()
    assert entry.agent_effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD
    assert entry.sends_agent_anywhere
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert KWISATZ in content_for(CONFIG).imperium_deck_instance_ids
    send = "Send one of your Agents from anywhere to ANY board space (even if occupied)"
    text = personal_card_text(entry)
    assert text[0] == send
    assert len(text) == len(personal_card_text_ko(entry)) == 2


def test_kwisatz_haderach_reveals_nothing() -> None:
    engine, state = _kwisatz_turn()
    revealed = _do(engine, state, "reveal_turn").state
    context = dict(revealed.decision_stack[-1].context)
    assert context["persuasion"] == 0


# --- Where the Agent comes from -----------------------------------------------------


def test_from_the_leader_to_an_opponent_occupied_space() -> None:
    """ "ANY board space (even if occupied)": seat 1's Agent on Wealth does not
    stop it, as it stops a plain card; both Agents stand there."""

    engine, state = _kwisatz_turn(hand=(KWISATZ, RECRUITER))
    state = _seat(state, 1, agent_locations=("carthag",), agents_available=1)
    rows = _rows(state)
    assert rows and all("from_space" not in row for row in rows)
    assert "carthag" in _destinations(state)
    plain = {
        dict(p.arguments)["space_id"]
        for p in executable_placements(state, 0)
        if dict(p.arguments)["card_id"] == RECRUITER
    }
    assert "carthag" not in plain
    placed = _send(engine, state, "carthag")
    owner = placed.state.players[0]
    assert owner.agent_locations == ("carthag",)
    assert owner.agents_available == 1
    assert placed.state.players[1].agent_locations == ("carthag",)
    (event,) = (e for e in placed.events if e.kind == "agent_placed")
    assert dict(event.payload) == {
        "card_id": KWISATZ,
        "player": 0,
        "space_id": "carthag",
    }


def test_from_a_board_space_to_another_frees_the_old_one() -> None:
    """The Agent leaves Carthag for Wealth: Wealth's 2 Solari, its Emperor
    Influence and the card's draw all resolve; nothing gained at Carthag is
    undone; Carthag is empty, so the seat's next Agent (the turn comes back,
    every other seat revealed) may go there with a plain City card."""

    engine, state = _kwisatz_turn(
        hand=(KWISATZ, RECRUITER),
        agent_locations=("carthag",),
        agents_available=1,
    )
    state = replace(
        state,
        players=tuple(
            replace(seat, has_revealed=seat.player_id != 0) for seat in state.players
        ),
    )
    owner = state.players[0]
    assert "wealth" in _destinations(state, "carthag")
    moved = _send(engine, state, "wealth", from_space="carthag")
    after = moved.state.players[0]
    assert after.agent_locations == ("wealth",)
    assert after.agents_available == 1
    (event,) = (e for e in moved.events if e.kind == "agent_placed")
    assert dict(event.payload)["from_space"] == "carthag"
    resolved = _resolve_all(engine, moved.state).players[0]
    assert resolved.resources.solari == owner.resources.solari + 2
    assert resolved.influence.emperor == owner.influence.emperor + 1
    assert len(resolved.hand) == 2  # the Arrakis Recruiter and the draw
    assert resolved.troops_garrison == owner.troops_garrison
    ended = _finish(engine, moved.state)
    assert dict(ended.decision_stack[-1].context)["turn_owner"] == 0
    assert all("carthag" not in seat.agent_locations for seat in ended.players)
    plain = {
        dict(p.arguments)["space_id"]
        for p in executable_placements(ended, 0)
        if dict(p.arguments)["card_id"] == RECRUITER
    }
    assert "carthag" in plain


def test_back_to_the_space_it_just_left() -> None:
    """ "방금 있던 칸으로 되돌려 보낼 수 있다": Wealth again, its effects again."""

    engine, state = _kwisatz_turn(agent_locations=("wealth",), agents_available=1)
    owner = state.players[0]
    assert "wealth" in _destinations(state, "wealth")
    # From the Leader the seat's own Agent there is no obstacle either (16).
    assert "wealth" in _destinations(state)
    moved = _send(engine, state, "wealth", from_space="wealth")
    after = moved.state.players[0]
    assert after.agent_locations == ("wealth",)
    assert after.agents_available == 1
    resolved = _resolve_all(engine, moved.state).players[0]
    assert resolved.resources.solari == owner.resources.solari + 2
    assert resolved.influence.emperor == owner.influence.emperor + 1


def test_to_a_space_holding_the_seats_own_other_agent() -> None:
    """ "내 다른 Agent가 있는 칸에도 보낼 수 있다" (16): from the Leader and from
    another space, two of the seat's Agents share Wealth until Recall."""

    engine, state = _kwisatz_turn(agent_locations=("wealth",), agents_available=1)
    doubled = _send(engine, state, "wealth").state.players[0]
    assert doubled.agent_locations == ("wealth", "wealth")
    assert doubled.agents_available == 0

    engine, state = _kwisatz_turn(
        agent_locations=("carthag", "wealth"), agents_available=0
    )
    moved = _send(engine, state, "wealth", from_space="carthag").state
    assert moved.players[0].agent_locations == ("wealth", "wealth")
    assert moved.players[0].agents_available == 0
    recall = replace(
        moved,
        phase=GamePhase.RECALL_OR_ENDGAME,
        decision_stack=(),
        players=tuple(replace(seat, has_revealed=True) for seat in moved.players),
    )
    recalled = resolve_recall_or_endgame(recall).state.players[0]
    assert (recalled.agent_locations, recalled.agents_available) == ((), 2)
    # A recall effect brings one of the two back, not both [Main p. 20].
    one, _ = recall_board_agent(
        moved.players[0], "wealth", player=0, source="test", event_id="test"
    )
    assert (one.agent_locations, one.agents_available) == (("wealth",), 1)


def test_with_an_empty_leader_the_agent_turn_is_offered() -> None:
    """ "Agent가 남지 않아도 낼 수 있다(이미 칸에 있는 Agent를 보낸다)": with both
    Agents on the board the seat may still take an Agent turn with Kwisatz
    Haderach -- and with it alone; every row moves a board Agent."""

    engine, state = _kwisatz_turn(
        hand=(KWISATZ, RECRUITER),
        agent_locations=("carthag", "wealth"),
        agents_available=0,
    )
    picks = [
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "choose_agent_card"
    ]
    assert picks == [
        DomainAction("choose_agent_card", 0, (("card_id", KWISATZ),)),
    ]
    assert "reveal_turn" in {a.action_id for a in engine.legal_actions(state, 0)}
    rows = [dict(p.arguments) for p in executable_placements(state, 0)]
    assert rows and {row["card_id"] for row in rows} == {KWISATZ}
    assert {row.get("from_space") for row in rows} == {"carthag", "wealth"}
    moved = _send(engine, state, "imperial_basin", from_space="wealth").state
    assert moved.players[0].agent_locations == ("carthag", "imperial_basin")
    assert moved.players[0].agents_available == 0
    # Without Kwisatz Haderach the empty Leader leaves the Reveal turn only.
    plain = _seat(state, 0, hand=(RECRUITER,))
    assert executable_placements(plain, 0) == ()
    assert "choose_agent_card" not in {
        a.action_id for a in engine.legal_actions(plain, 0)
    }


# --- What still stops it -----------------------------------------------------------


def test_the_space_cost_is_paid_and_refused_when_unaffordable() -> None:
    """The Research Station costs 2 water, paid as for any send [DI p. 9]."""

    engine, state = _kwisatz_turn(
        agent_locations=("carthag",), agents_available=1, resources=Resources(water=2)
    )
    assert "imperium_research_station" in _destinations(state, "carthag")
    assert "imperium_research_station" in _destinations(state)
    paid = _send(engine, state, "imperium_research_station", from_space="carthag")
    assert paid.state.players[0].resources.water == 0
    poor = _seat(state, 0, resources=Resources(water=1))
    assert "imperium_research_station" not in _destinations(poor, "carthag")
    assert "imperium_research_station" not in _destinations(poor)
    assert "imperium_heighliner" not in _destinations(poor)  # 6 spice


def test_the_influence_requirement_still_applies() -> None:
    """ "Interstellar Shipping·Sietch Tabr의 Influence 요구는 넘지 못한다": the
    original Sietch Tabr asks Fremen Influence 2."""

    engine, state = _kwisatz_turn(agent_locations=("carthag",), agents_available=1)
    owner = state.players[0]
    low = _seat(state, 0, influence=replace(owner.influence, fremen=1))
    assert "imperium_sietch_tabr" not in _destinations(low)
    assert "imperium_sietch_tabr" not in _destinations(low, "carthag")
    met = _seat(state, 0, influence=replace(owner.influence, fremen=2))
    assert "imperium_sietch_tabr" in _destinations(met)
    assert "imperium_sietch_tabr" in _destinations(met, "carthag")


def test_once_per_game_spaces_refuse_a_second_visit() -> None:
    """ "게임에 한 번인 칸(High Council, Swordmaster)에 두 번 보낼 수 없고"
    [DI pp. 17-18]: a seated seat cannot go back to the High Council, even
    from it, nor a Swordmaster-holding seat to the Swordmaster."""

    engine, state = _kwisatz_turn(
        agent_locations=("imperium_high_council",),
        agents_available=1,
        resources=Resources(solari=10),
    )
    fresh = _destinations(state, "imperium_high_council")
    assert {"imperium_high_council", "imperium_swordmaster"} <= fresh
    seated = _seat(state, 0, high_council=True)
    for source in (None, "imperium_high_council"):
        assert "imperium_high_council" not in _destinations(seated, source)
        assert "imperium_swordmaster" in _destinations(seated, source)
    sworded = _seat(state, 0, swordmaster_acquired=True, agents_available=2)
    for source in (None, "imperium_high_council"):
        assert "imperium_swordmaster" not in _destinations(sworded, source)
        assert "imperium_high_council" in _destinations(sworded, source)


def test_the_voice_stops_it_and_a_kwisatz_send_uses_the_block_up() -> None:
    """ "The Voice를 넘지 못한다": a space The Voice closed to the seat is no
    destination, from the Leader or the board (its own Agent may still leave
    it); the send, an Agent placement, lifts the seat's blocks (OQ-116)."""

    engine, state = _kwisatz_turn(
        agent_locations=("wealth",),
        agents_available=1,
        voice_blocked_space_ids=("carthag", "wealth"),
    )
    for source in (None, "wealth"):
        destinations = _destinations(state, source)
        assert not {"carthag", "wealth"} & destinations
        assert "arrakeen" in destinations
    moved = _send(engine, state, "arrakeen", from_space="wealth").state
    assert moved.players[0].voice_blocked_space_ids == ()


def test_the_mentat_is_one_of_the_seats_agents() -> None:
    """Section 9 and OQ-139 (가): the seat holding the Mentat has three Agents,
    told apart nowhere; Kwisatz Haderach moves any one off the board, or
    sends the one still on the Leader."""

    engine, state = _kwisatz_turn(
        mentat=True,
        agent_locations=("carthag", "wealth", "secrets"),
        agents_available=0,
    )
    assert {row.get("from_space") for row in _rows(state)} == {
        "carthag",
        "wealth",
        "secrets",
    }
    moved = _send(engine, state, "foldspace", from_space="secrets").state
    owner = moved.players[0]
    assert owner.mentat
    assert (owner.agent_locations, owner.agents_available) == (
        ("carthag", "wealth", "foldspace"),
        0,
    )
    on_leader = _seat(
        state, 0, agent_locations=("carthag", "wealth"), agents_available=1
    )
    assert {row.get("from_space") for row in _rows(on_leader)} == {
        None,
        "carthag",
        "wealth",
    }
    sent = _send(engine, on_leader, "foldspace").state.players[0]
    assert (sent.agent_locations, sent.agents_available) == (
        ("carthag", "wealth", "foldspace"),
        0,
    )


# --- Order and what the move leaves behind ------------------------------------------


def test_the_card_is_drawn_after_the_placement() -> None:
    """ "Agent를 먼저 놓고 카드를 뽑는다" (designer ruling): the placement draws
    nothing; the draw is the Agent box, its own step (OQ-106)."""

    engine, state = _kwisatz_turn(agent_locations=("carthag",), agents_available=1)
    top = state.players[0].deck[0]
    placed = _send(engine, state, "wealth", from_space="carthag")
    assert placed.state.players[0].hand == ()
    assert "resolve_agent_card_effect" in {
        a.action_id for a in engine.whole_actions(placed.state, 0)
    }
    drawn = _do(engine, placed.state, "resolve_agent_card_effect").state
    assert drawn.players[0].hand == (top,)


def test_a_maker_space_it_left_gathers_bonus_spice() -> None:
    """ "Maker 칸을 떠난 뒤 Phase 4까지 비어 있으면 bonus spice가 쌓인다": the
    Agent leaves Imperial Basin, which then gains its spice at Makers; had it
    stayed, the space would not."""

    engine, state = _kwisatz_turn(
        agent_locations=("imperial_basin",), agents_available=1
    )

    def makers(after: GameState) -> int:
        phase = replace(after, phase=GamePhase.MAKERS, decision_stack=())
        return dict(resolve_makers(phase).state.maker_bonus_spice)["imperial_basin"]

    before = dict(state.maker_bonus_spice)["imperial_basin"]
    moved = _send(engine, state, "wealth", from_space="imperial_basin").state
    assert "imperial_basin" not in moved.players[0].agent_locations
    assert makers(moved) == before + 1
    stayed = _send(engine, state, "wealth").state
    assert makers(stayed) == before


# --- Codec and combinations ----------------------------------------------------------


def test_the_new_rows_round_trip_in_the_original_codec_only() -> None:
    """Every row of a Kwisatz turn encodes in the original game's catalog,
    which holds a ``from_space`` row for every space to every space; no
    Uprising catalog names one."""

    engine, state = _kwisatz_turn(
        agent_locations=("carthag", "wealth"),
        agents_available=0,
        resources=Resources(solari=10, spice=10, water=5),
    )
    codec = ActionCodec(CONFIG)
    rows = engine.legal_actions(state, 0)
    picked = apply_whole(
        engine, state, DomainAction("choose_agent_card", 0, (("card_id", KWISATZ),))
    ).state
    spaces = engine.legal_actions(picked, 0)
    assert {a.action_id for a in spaces} >= {"place_agent"}
    moves = [a for a in spaces if "from_space" in dict(a.arguments)]
    assert moves
    for action in (*rows, *spaces):
        assert codec.decode(codec.encode(action), 0) == action
    space_ids = {space.space_id for space in board_spaces_on_table(state)}
    from_rows = {
        (dict(t.arguments)["from_space"], dict(t.arguments)["space_id"])
        for t in codec.catalog
        if t.action_id == "place_agent" and "from_space" in dict(t.arguments)
    }
    assert from_rows == {(a, b) for a in space_ids for b in space_ids}
    for config in (RulesetConfig(), RulesetConfig(bloodlines=True, immortality=True)):
        uprising = ActionCodec(config)
        assert not any("from_space" in dict(t.arguments) for t in uprising.catalog)


def test_kwisatz_haderach_is_never_grafted_nor_a_partner() -> None:
    """The original game takes Immortality from stage P7; until then Kwisatz
    Haderach is neither grafted nor a Graft card's partner (the graft tests'
    Uprising + Immortality state with the original card in hand). Ghola, a
    Graft card, has no partner then and no placement."""

    state = graft_tests._state((graft_tests.GHOLA, KWISATZ))
    rows = [dict(p.arguments) for p in executable_placements(state, 0)]
    assert rows and {row["card_id"] for row in rows} == {KWISATZ}
    assert not any(row.get("graft") for row in rows)
