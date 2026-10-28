"""The original game's The Voice and Infiltrate (stage P3).

docs/rules/imperium-base.md 13.1 ("The Voice -- 고른 칸에 각 상대의 이번 라운드
다음 Agent 배치 한 번을 막는다", OQ-116, 2026-10-22 user ruling B), 15 ("The
Voice | 낸 좌석 | 아무 칸 하나 | 'Choose any board space' [The Voice card]"),
13.3 and 16 (OQ-113 (C): the cost-free Infiltrate Plot "Agent를 놓은 뒤에도
낸다"), 12 (Helena Richese's Eyes Everywhere) and 9 (the Mentat is an Agent
for all purposes). The printed values are the Steam app's attribute table and
card text (docs/base-game-and-ix-plan.md 2.4, 16.3).

The Voice blocks a space for each opponent's next Agent placement (a pass
without an Agent, a Reveal turn, keeps it; the round's end clears it) and no
Agent is involved, so nothing that lets a seat ignore occupying Agents --
Uprising's Spy Infiltrate, Eyes Everywhere, Tleilaxu Infiltrator, the
Infiltrate Intrigue -- beats it.
"""

from dataclasses import replace

from tests.unit.rules import test_graft_boxes as graft_tests

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    BlockChosenSpaceForOpponentsNextAgent,
    IgnoreEnemyAgentsNextPlacement,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.core.engine import RuleResult, Transition
from dune_imperium.display import intrigue_card_text
from dune_imperium.display.effect_dsl_text import reward_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko
from dune_imperium.display.tokens import AGENT_EFFECT_TEXT
from dune_imperium.display.tokens_ko import AGENT_EFFECT_TEXT_KO
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_box_abilities import box_ability
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.board_table import board_spaces_on_table
from dune_imperium.rules.effect_interpreter import play_changes_nothing
from dune_imperium.rules.graft_boxes import BOX_ACTION_IDS, row_box
from dune_imperium.rules.intrigue import legal_intrigue_play_actions
from dune_imperium.rules.phases import resolve_recall_or_endgame

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
VOICE = "imperium:the_voice:0"
VOICE_TWO = "imperium:the_voice:1"
# City-only cards: a seat with them can reach Arrakeen, Carthag and the
# Research Station (2 water), whatever the shuffle dealt.
RECRUITER = "imperium:arrakis_recruiter:0"
RECRUITER_TWO = "imperium:arrakis_recruiter:1"
INFILTRATE = "intrigue:infiltrate:0"
BINDU = "intrigue:bindu_suspension:0"
SPY_POST = "arrakis-spice-refinery-arrakeen"
BLOCK = "block_agent_card_space"
_TURN_STEPS = (
    "resolve_board_effect",
    "harvest_maker_spice",
    "resolve_agent_card_effect",
    "draw_owed_card",
    "draw_owed_intrigue",
)


def _start(
    leaders: tuple[str, ...] = LEADERS, seed: int = 3
) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an original game at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=leaders)
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


def _spaces(state: GameState, seat: int) -> set[str]:
    return {
        str(dict(placement.arguments)["space_id"])
        for placement in executable_placements(state, seat)
    }


def _place_as(
    engine: UprisingRulesEngine,
    state: GameState,
    seat: int,
    space_id: str,
    card_id: str,
) -> RuleResult:
    placement = next(
        placement
        for placement in executable_placements(state, seat)
        if dict(placement.arguments)["space_id"] == space_id
        and dict(placement.arguments)["card_id"] == card_id
        and "infiltrate_post_id" not in dict(placement.arguments)
    )
    return apply_placement(engine, state, placement)


def _do_as(
    engine: UprisingRulesEngine,
    state: GameState,
    seat: int,
    action_id: str,
    **arguments: object,
) -> Transition:
    action = next(
        action
        for action in engine.whole_actions(state, seat)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return apply_whole(engine, state, action)


def _finish(
    engine: UprisingRulesEngine, state: GameState, seat: int, end: str
) -> GameState:
    """Resolve what the turn still owes (board effects, a harvest, the Agent
    box, owed draws), then press ``end``."""

    for _ in range(14):
        actions = engine.whole_actions(state, seat)
        ended = [action for action in actions if action.action_id == end]
        if ended:
            return apply_whole(engine, state, ended[0]).state
        step = next(action for action in actions if action.action_id in _TURN_STEPS)
        state = apply_whole(engine, state, step).state
    raise AssertionError("the turn did not reach its end")


def _voice_played(
    engine: UprisingRulesEngine,
    state: GameState,
    blocked: str,
    *,
    at: str = "imperial_basin",
    voice: str = VOICE,
) -> Transition:
    """Seat 0 sends ``voice`` to ``at`` and chooses ``blocked``."""

    placed = _place_as(engine, state, 0, at, voice).state
    return _do_as(engine, placed, 0, BLOCK, space_id=blocked)


def _blocked(state: GameState) -> list[tuple[str, ...]]:
    return [seat.voice_blocked_space_ids for seat in state.players]


def _opponents_turn() -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 sent The Voice to Imperial Basin, blocked Carthag and ended its
    turn: seat 1 (two City cards, two water) is on turn, and seats 0, 2 and 3
    have revealed, so the turn comes back to seat 1 after each of its own."""

    engine, state = _start()
    state = _seat(state, 0, hand=(VOICE,))
    state = _seat(
        state, 1, hand=(RECRUITER, RECRUITER_TWO), resources=Resources(water=2)
    )
    done = _finish(
        engine, _voice_played(engine, state, "carthag").state, 0, "finish_agent_turn"
    )
    assert dict(done.decision_stack[-1].context)["turn_owner"] == 1
    revealed = replace(
        done,
        players=tuple(
            replace(seat, has_revealed=True) if seat.player_id != 1 else seat
            for seat in done.players
        ),
    )
    return engine, revealed


# --- The Voice ---------------------------------------------------------------------


def test_the_voice_matches_the_app_table_and_text() -> None:
    # App attribute table: cost 2, 2 copies, Bene Gesserit, City and Spice
    # Trade, Reveal 2 Persuasion; Agent "Choose any board space. Opponents
    # can't send their next Agents there this round."
    entry = IMPERIUM_CARDS_BY_ID["the_voice"]
    assert entry.card.name == "The Voice"
    assert entry.acquisition_cost == 2
    assert entry.copies == 2
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    effect = PersonalCardAgentEffect.BLOCK_CHOSEN_SPACE_FOR_OPPONENTS_NEXT_AGENT
    assert entry.agent_effect is effect
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    deck = content_for(CONFIG).imperium_deck_instance_ids
    assert {VOICE, VOICE_TWO} <= set(deck)
    # Its record: one mandatory line choosing the space, in the printed words.
    ability = box_ability(effect)
    assert ability is not None
    (reward,) = ability.sections[0].rewards
    assert isinstance(reward, BlockChosenSpaceForOpponentsNextAgent)
    printed = (
        "Choose any board space. Opponents can't send their next Agents there "
        "this round"
    )
    assert AGENT_EFFECT_TEXT[effect] == reward_text(reward) == printed
    assert AGENT_EFFECT_TEXT_KO[effect] == reward_text_ko(reward)
    assert BLOCK in BOX_ACTION_IDS


def test_the_voice_reveals_two_persuasion() -> None:
    engine, state = _start()
    state = _seat(state, 0, hand=(VOICE,))
    revealed = _do_as(engine, state, 0, "reveal_turn").state
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2


def test_the_voice_offers_every_board_space_and_no_way_out() -> None:
    """ "Choose any board space" (imperium-base.md 15): a mandatory choice
    among every space on the table, occupied (seat 1 sits on Carthag) or not,
    the owner's own Agent's space (Imperial Basin) included; no refusal and no
    plain resolution, and the turn does not end before it is made."""

    engine, state = _start()
    state = _seat(state, 0, hand=(VOICE,))
    state = _seat(state, 1, agent_locations=("carthag",), agents_available=1)
    placed = _place_as(engine, state, 0, "imperial_basin", VOICE).state
    chosen = {
        str(dict(action.arguments)["space_id"])
        for action in engine.whole_actions(placed, 0)
        if action.action_id == BLOCK
    }
    assert chosen == {space.space_id for space in content_for(CONFIG).board_spaces}
    assert {"carthag", "imperial_basin"} <= chosen
    ids = {action.action_id for action in engine.whole_actions(placed, 0)}
    assert "resolve_agent_card_effect" not in ids
    assert not {i for i in ids if i.startswith("decline_")}
    harvested = _do_as(engine, placed, 0, "harvest_maker_spice").state
    assert "finish_agent_turn" not in {
        action.action_id for action in engine.whole_actions(harvested, 0)
    }


def test_a_leaders_space_is_a_choice_only_with_its_leader() -> None:
    """Tuek's Sietch is on the table only with Esmar Tuek (the skip of
    ``agent_turn._placements_for_card``, shared by The Voice's choice)."""

    state = graft_tests._state((graft_tests.GHOLA, VOICE))
    assert "tuek_sietch" not in {s.space_id for s in board_spaces_on_table(state)}
    players = list(state.players)
    players[2] = replace(players[2], leader_id="esmar_tuek")
    esmar = replace(state, players=tuple(players))
    assert "tuek_sietch" in {s.space_id for s in board_spaces_on_table(esmar)}
    assert len(board_spaces_on_table(esmar)) == len(board_spaces_on_table(state)) + 1


def test_the_voice_blocks_every_opponent_and_never_the_owner() -> None:
    """ "각 상대의 이번 라운드 다음 Agent 배치 한 번을 막는다" (imperium-base.md
    13.1): all three opponents are bound, the owner is not, and one public
    event names the space and the seats."""

    engine, state = _start()
    state = _seat(state, 0, hand=(VOICE,))
    played = _voice_played(engine, state, "carthag")
    assert _blocked(played.state) == [(), ("carthag",), ("carthag",), ("carthag",)]
    (event,) = (e for e in played.events if e.kind == "space_blocked_for_opponents")
    assert dict(event.payload) == {
        "blocked_players": (1, 2, 3),
        "player": 0,
        "space_id": "carthag",
    }
    assert event.visible_to is None


def test_an_opponents_next_placement_cannot_use_the_space_a_later_one_can() -> None:
    """The block lasts until that opponent's next Agent placement (OQ-116):
    seat 1's first Agent cannot go to Carthag, whichever card it holds, and
    sending it elsewhere lifts the block, so its second Agent can."""

    engine, state = _opponents_turn()
    assert state.players[1].voice_blocked_space_ids == ("carthag",)
    assert _spaces(state, 1) == {"arrakeen", "imperium_research_station"}
    first = _place_as(engine, state, 1, "arrakeen", RECRUITER)
    assert first.state.players[1].voice_blocked_space_ids == ()
    again = _finish(engine, first.state, 1, "finish_agent_turn")
    assert dict(again.decision_stack[-1].context)["turn_owner"] == 1
    assert "carthag" in _spaces(again, 1)


def test_a_pass_without_an_agent_keeps_the_block() -> None:
    """ "Bindu·Litany Against Fear 등으로 Agent를 보내지 않고 turn을 넘기면 그
    상대의 봉쇄는 남는다" (imperium-base.md 13.1): Bindu Suspension passes the
    turn, which comes straight back to seat 1 as every other seat revealed;
    Carthag is still closed to it."""

    engine, state = _opponents_turn()
    state = _seat(state, 1, intrigue_cards=(BINDU,))
    play = DomainAction("play_intrigue", 1, (("card_id", BINDU), ("option", 0)))
    assert play in legal_intrigue_play_actions(state, 1)
    opened = apply_whole(engine, state, play).state
    passed = _do_as(engine, opened, 1, "pass_turn_intrigue")
    assert "turn_passed" in [event.kind for event in passed.events]
    assert dict(passed.state.decision_stack[-1].context)["turn_owner"] == 1
    assert passed.state.players[1].voice_blocked_space_ids == ("carthag",)
    assert "carthag" not in _spaces(passed.state, 1)


def test_a_reveal_turn_does_not_use_the_block_up() -> None:
    """Only an Agent placement lifts it: seat 1's Reveal turn leaves the block
    on its seat while the round goes on (cleared at the round's end)."""

    engine, state = _opponents_turn()
    state = replace(
        state,
        players=tuple(replace(seat, has_revealed=False) for seat in state.players),
    )
    revealed = _do_as(engine, state, 1, "reveal_turn").state
    finished = _finish(engine, revealed, 1, "finish_reveal")
    assert dict(finished.decision_stack[-1].context)["turn_owner"] == 2
    assert finished.players[1].voice_blocked_space_ids == ("carthag",)


def test_the_end_of_the_round_clears_every_block() -> None:
    engine, state = _start()
    players = tuple(
        replace(
            seat,
            voice_blocked_space_ids=("carthag", "arrakeen"),
            enemy_agents_ignored_turn=seat.player_id == 2,
            has_revealed=True,
        )
        for seat in state.players
    )
    recall = replace(
        state, phase=GamePhase.RECALL_OR_ENDGAME, decision_stack=(), players=players
    )
    recalled = resolve_recall_or_endgame(recall).state
    assert recalled.phase is GamePhase.ROUND_START
    assert _blocked(recalled) == [()] * 4
    assert [seat.enemy_agents_ignored_turn for seat in recalled.players] == [False] * 4


def _two_voices(
    second_space: str,
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 blocks Carthag with a Voice and ends its turn; seat 1 sends the
    other Voice (to Imperial Basin, taken by seat 0's Agent, so to Arrakeen)
    and blocks ``second_space``. Seat 2 holds a City card."""

    engine, state = _start()
    state = _seat(state, 0, hand=(VOICE,))
    state = _seat(state, 1, hand=(VOICE_TWO,))
    state = _seat(state, 2, hand=(RECRUITER,), resources=Resources(water=2))
    first = _finish(
        engine, _voice_played(engine, state, "carthag").state, 0, "finish_agent_turn"
    )
    assert "imperial_basin" not in _spaces(first, 1)
    placed = _place_as(engine, first, 1, "arrakeen", VOICE_TWO).state
    assert placed.players[1].voice_blocked_space_ids == ()
    return engine, _do_as(engine, placed, 1, BLOCK, space_id=second_space).state


def test_blocking_a_space_twice_binds_it_once() -> None:
    _, state = _two_voices("carthag")
    assert _blocked(state) == [("carthag",), (), ("carthag",), ("carthag",)]


def test_two_voices_on_two_spaces_both_lift_at_the_next_placement() -> None:
    """Each Voice blocks "their next Agents": seat 1 plays the second Voice in
    its own turn (its Agent lifts its block), and seat 2, bound by both
    spaces, is released from both by one placement."""

    engine, second = _two_voices("imperial_basin")
    assert _blocked(second) == [
        ("imperial_basin",),
        (),
        ("carthag", "imperial_basin"),
        ("carthag", "imperial_basin"),
    ]
    turn = _finish(engine, second, 1, "finish_agent_turn")
    assert dict(turn.decision_stack[-1].context)["turn_owner"] == 2
    assert not {"carthag", "imperial_basin"} & _spaces(turn, 2)
    lifted = _place_as(engine, turn, 2, "imperium_research_station", RECRUITER).state
    assert lifted.players[2].voice_blocked_space_ids == ()
    # The seats that have not sent an Agent since stay bound.
    assert lifted.players[3].voice_blocked_space_ids == ("carthag", "imperial_basin")


def test_a_spy_infiltrate_does_not_open_a_voice_space() -> None:
    """The Voice is not an Agent: Uprising's Infiltrate (recall a connected
    Spy to enter a space an opponent's Agent holds, [Main p. 11]) is offered
    on an occupied space and is not on a space The Voice closed."""

    engine, state = _start()
    state = _seat(
        state,
        0,
        hand=(RECRUITER,),
        spy_post_ids=(SPY_POST,),
        spies_supply=2,
    )
    state = _seat(state, 1, agent_locations=("arrakeen",), agents_available=1)
    rows = [dict(p.arguments) for p in executable_placements(state, 0)]
    assert {
        row.get("infiltrate_post_id") for row in rows if row["space_id"] == "arrakeen"
    } == {SPY_POST}
    closed = _seat(state, 0, voice_blocked_space_ids=("arrakeen",))
    assert "arrakeen" not in _spaces(closed, 0)
    assert "carthag" in _spaces(closed, 0)


def test_eyes_everywhere_does_not_open_a_voice_space() -> None:
    """Helena Richese's Eyes Everywhere ignores opponents on Landsraad and
    City spaces (imperium-base.md 12); The Voice still closes the space."""

    engine, state = _start(("helena_richese", *LEADERS[1:]))
    state = _seat(state, 0, hand=(RECRUITER,))
    state = _seat(state, 1, agent_locations=("carthag",), agents_available=1)
    assert "carthag" in _spaces(state, 0)
    closed = _seat(state, 0, voice_blocked_space_ids=("carthag",))
    assert "carthag" not in _spaces(closed, 0)
    # Another seat, without her ability, is stopped by the occupant as ever.
    assert "carthag" not in _spaces(_seat(state, 0, leader_id="glossu_rabban"), 0)


def test_the_infiltrate_intrigue_does_not_open_a_voice_space() -> None:
    engine, state = _start()
    state = _seat(
        state,
        0,
        hand=(RECRUITER,),
        enemy_agents_ignored_turn=True,
        voice_blocked_space_ids=("carthag",),
    )
    state = _seat(state, 1, agent_locations=("arrakeen",), agents_available=1)
    spaces = _spaces(state, 0)
    assert "arrakeen" in spaces  # the opponent's Agent is ignored
    assert "carthag" not in spaces  # The Voice is not


def test_tleilaxu_infiltrator_does_not_open_a_voice_space() -> None:
    """Immortality's Tleilaxu Infiltrator ("Enemy Agents don't block your
    Agent this turn") lets a graft pair enter an occupied space; The Voice is
    no Agent, so it still closes the space."""

    state = graft_tests._state((graft_tests.INFILTRATOR, graft_tests.DAGGER))
    state = _seat(state, 1, agent_locations=("arrakeen",), agents_available=1)
    assert "arrakeen" in _spaces(state, 0)
    closed = _seat(state, 0, voice_blocked_space_ids=("arrakeen",))
    assert "arrakeen" not in _spaces(closed, 0)


def test_a_grafted_voice_works_in_either_box() -> None:
    """Immortality [Immortality pp. 10-11]: both cards' effects are gained.
    Ghola copies The Voice's box, so the box is offered twice (box 0 and box
    1, each its own once), each blocking the space it names; the row is in
    ``BOX_ACTION_IDS`` (a Firm Grip row once missed it). The original game
    takes Immortality from stage P7: the state is the graft tests' Uprising +
    Immortality one with the original card in hand."""

    ghola = graft_tests.GHOLA
    state = graft_tests._graft(
        graft_tests._state((ghola, VOICE)), ghola, "arrakeen", VOICE
    )
    offered = {
        row_box(action)
        for action in graft_tests.ENGINE.whole_actions(state, 0)
        if action.action_id == BLOCK
    }
    assert offered == {0, 1}
    # Both boxes' rows are in the original + Immortality catalog (the box 1
    # twin comes of ``BOX_ACTION_IDS``).
    original = ActionCodec(RulesetConfig(base_game=BaseGame.IMPERIUM, immortality=True))
    effects = [
        row
        for row in graft_tests.ENGINE.legal_actions(state, 0)
        if row.action_id == "choose"
    ]
    # Ghola's copy (box 0, printed on Ghola) and The Voice itself (box 1).
    assert {(dict(row.arguments)["printed"], row_box(row)) for row in effects} == {
        ("ghola", 0),
        ("the_voice", 1),
    }
    for row in effects:
        assert original.decode(original.encode(row), 0) == row
    spaces = {
        str(dict(action.arguments)["space_id"])
        for action in graft_tests.ENGINE.whole_actions(state, 0)
        if action.action_id == BLOCK
    }
    assert "arrakeen" in spaces and "tuek_sietch" not in spaces
    partner = graft_tests._apply(state, BLOCK, box=1, space_id="arrakeen")
    assert _blocked(partner) == [(), ("arrakeen",), ("arrakeen",), ("arrakeen",)]
    assert {
        row_box(action)
        for action in graft_tests.ENGINE.whole_actions(partner, 0)
        if action.action_id == BLOCK
    } == {0}
    both = graft_tests._apply(partner, BLOCK, box=0, space_id="imperial_basin")
    assert _blocked(both)[1] == ("arrakeen", "imperial_basin")
    assert both.players[0].voice_blocked_space_ids == ()


def test_the_voice_rows_are_in_the_original_codec_only() -> None:
    """The Voice's rows exist only in catalogs that hold the original cards:
    the Uprising catalogs name no row of it, and every row of the pending box
    round-trips in the original one."""

    engine, state = _start()
    state = _seat(state, 0, hand=(VOICE,))
    placed = _place_as(engine, state, 0, "imperial_basin", VOICE).state
    rows = engine.legal_actions(placed, 0)
    assert any(dict(row.arguments).get("printed") == "the_voice" for row in rows)
    codec = ActionCodec(CONFIG)
    for row in rows:
        assert codec.decode(codec.encode(row), 0) == row
    uprising = ActionCodec(RulesetConfig())
    assert not any(
        dict(template.arguments).get("printed") == "the_voice"
        for template in uprising.catalog
    )
    assert not any(template.action_id == BLOCK for template in uprising.catalog)


# --- Infiltrate --------------------------------------------------------------------


def _infiltrate_turn() -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 holds Infiltrate and two City cards and a Spy on Spice
    Refinery/Arrakeen; seat 1's Agent sits on Arrakeen."""

    engine, state = _start()
    state = _seat(
        state,
        0,
        hand=(RECRUITER, RECRUITER_TWO),
        intrigue_cards=(INFILTRATE,),
        spy_post_ids=(SPY_POST,),
        spies_supply=2,
        resources=Resources(water=2),
    )
    state = _seat(state, 1, agent_locations=("arrakeen",), agents_available=1)
    return engine, state


def _play_infiltrate(engine: UprisingRulesEngine, state: GameState) -> GameState:
    play = DomainAction("play_intrigue", 0, (("card_id", INFILTRATE), ("option", 0)))
    assert play in legal_intrigue_play_actions(state, 0)
    return apply_whole(engine, state, play).state


def test_infiltrate_is_a_cost_free_plot_with_the_printed_text() -> None:
    # "Enemy Agents don't block your next Agent at board spaces this turn"
    # [Infiltrate card, app text]; 1 copy [DI p. 3]; a Plot with no cost
    # (imperium-base.md 13.3, OQ-113 (C)).
    entry = intrigue_card_for_instance(INFILTRATE)
    assert entry.card.name == "Infiltrate"
    assert entry.copies == 1
    assert entry.play_data_complete
    (option,) = entry.options
    assert option.timing.value == "plot"
    (section,) = option.sections
    assert not section.costs
    (reward,) = section.rewards
    assert isinstance(reward, IgnoreEnemyAgentsNextPlacement)
    assert intrigue_card_text(entry) == [
        "Plot — Enemy Agents don't block your next Agent at board spaces this turn"
    ]
    assert reward_text_ko(reward) == (
        "이번 차례에 다른 플레이어의 {agent}가 당신의 다음 {agent}를 막지 않음"
    )


def test_infiltrate_opens_an_occupied_space_for_the_next_placement_only() -> None:
    """Before it, seat 0 can enter Arrakeen only by recalling its Spy
    (Uprising's Infiltrate); after it the plain placement is legal and no
    Spy-recall row is offered there. The placement spends it."""

    engine, state = _infiltrate_turn()
    rows = [dict(p.arguments) for p in executable_placements(state, 0)]
    arrakeen = [row for row in rows if row["space_id"] == "arrakeen"]
    assert arrakeen
    assert all(row.get("infiltrate_post_id") == SPY_POST for row in arrakeen)

    played = _play_infiltrate(engine, state)
    assert played.players[0].enemy_agents_ignored_turn is True
    assert played.players[0].intrigue_cards == ()
    rows = [dict(p.arguments) for p in executable_placements(played, 0)]
    arrakeen = [row for row in rows if row["space_id"] == "arrakeen"]
    assert arrakeen and all("infiltrate_post_id" not in row for row in arrakeen)
    assert not any("infiltrate_post_id" in row for row in rows)

    placed = _place_as(engine, played, 0, "arrakeen", RECRUITER).state
    assert placed.players[0].enemy_agents_ignored_turn is False
    # The Spy stayed where it was: nothing was recalled.
    assert placed.players[0].spy_post_ids == (SPY_POST,)


def test_infiltrate_does_not_outlast_the_turn() -> None:
    """Played after the Agent was sent it does nothing, and it is gone when
    the turn ends: the seat's next turn (here at once, every other seat
    revealed) has to deal with the occupant again."""

    engine, state = _infiltrate_turn()
    state = _seat(state, 0, hand=(RECRUITER, RECRUITER_TWO))
    placed = _place_as(engine, state, 0, "imperium_research_station", RECRUITER).state
    sections = intrigue_card_for_instance(INFILTRATE).options[0].sections
    # The page warns only when playing it could not change the turn.
    assert not play_changes_nothing(state, 0, sections)
    played = _play_infiltrate(engine, placed)
    assert played.players[0].enemy_agents_ignored_turn is True
    assert play_changes_nothing(played, 0, sections)
    revealed = replace(
        played,
        players=tuple(
            replace(seat, has_revealed=True) if seat.player_id != 0 else seat
            for seat in played.players
        ),
    )
    ended = _finish(engine, revealed, 0, "finish_agent_turn")
    assert dict(ended.decision_stack[-1].context)["turn_owner"] == 0
    assert ended.players[0].enemy_agents_ignored_turn is False
    plain = {
        dict(p.arguments)["space_id"]
        for p in executable_placements(ended, 0)
        if "infiltrate_post_id" not in dict(p.arguments)
    }
    assert "arrakeen" not in plain


def test_infiltrate_is_played_in_the_reveal_turn_and_does_nothing() -> None:
    """ "Infiltrate는 Agent를 놓은 뒤에도 낸다" (imperium-base.md 13.3): a
    Reveal turn takes no Agent, so the Plot is played and fizzles, and no
    seat carries it over."""

    engine, state = _infiltrate_turn()
    revealed = _do_as(engine, state, 0, "reveal_turn").state
    assert DomainAction(
        "play_intrigue", 0, (("card_id", INFILTRATE), ("option", 0))
    ) in legal_intrigue_play_actions(revealed, 0)
    played = _play_infiltrate(engine, revealed)
    assert played.players[0].enemy_agents_ignored_turn is True
    after = _finish(engine, played, 0, "finish_reveal")
    assert [seat.enemy_agents_ignored_turn for seat in after.players] == [False] * 4


def test_infiltrate_leaves_the_owners_own_agent_and_the_requirements() -> None:
    """Only "enemy" Agents stop blocking: the owner's own Agent still holds its
    space, and an Influence requirement (Sietch Tabr: Fremen 2) still
    applies; an opponent's Mentat is an enemy Agent like any other."""

    engine, state = _infiltrate_turn()
    state = _seat(
        state,
        0,
        enemy_agents_ignored_turn=True,
        agent_locations=("carthag",),
        agents_available=1,
        resources=Resources(water=2),
    )
    state = _seat(
        state, 1, mentat=True, agent_locations=("arrakeen",), agents_available=2
    )
    spaces = _spaces(state, 0)
    assert "carthag" not in spaces  # its own Agent
    assert "imperium_sietch_tabr" not in spaces  # Fremen Influence 2 unmet
    assert "arrakeen" in spaces  # the Mentat's Agent is an enemy one
    assert "imperium_research_station" in spaces
    met = _seat(state, 0, influence=replace(state.players[0].influence, fremen=2))
    assert "imperium_sietch_tabr" in _spaces(met, 0)
