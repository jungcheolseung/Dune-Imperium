"""Rise of Ix Tech tiles' abilities, the first half (stage P4c-2a).

Rules: docs/rules/rise-of-ix.md 4 (the tile table and its "쓰기" and "Round
Start 순서" bullets), ``[Rise of Ix p. 4]``, OQ-114 (Shuttle Fleet's two
different Factions), OQ-121 ruling 3 (Detonation Devices), OQ-122 (Round Start
order) and OQ-126 (Disposal Facility), and docs/base-game-and-ix-plan.md 17.10
item 2. Setup refuses ``rise_of_ix`` until stage P4c-5, so every state is built
by hand: the original game's opening state (or round one at seat 0's first
turn) with its config switched to ``rise_of_ix=True`` and the tiles put on a
seat by ``dataclasses.replace`` (the state checks accept them).

Stage P4c-2b adds the four Endgame tiles, the four Flip tiles and OQ-150 (2)'s
late Reveal tiles (the sections at the end of this file).

Stage P4c-2c adds Sonic Snoopers, Spy Satellites' first ability and Spaceport
(the section at the end of this file).

Not in these slices (stage P4c-3): Troop Transports. The designer ruling of
docs/rules/rise-of-ix.md 12 -- a Windtraps taken through a Freighter reward in
the same win also gives this win's water -- needs the Freighter reward (stage
P4c-3) and is tested there.
"""

from dataclasses import replace
from typing import Any

import pytest
from tests.support.pauses import pause_outcome

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec, ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.bloodlines.tech import TECH_TILES
from dune_imperium.content.rise_of_ix.tech import IX_TECH_TILES
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    Resources,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import known_card_seats, known_intrigue_places
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules import tech as tech_rules
from dune_imperium.rules.acquisition import deck_top_offered
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.combat import (
    begin_combat_intrigue,
    legacy_combat_reward_icon,
)
from dune_imperium.rules.deck_top import settle_public_deck_tops
from dune_imperium.rules.endgame import final_standings
from dune_imperium.rules.frames import FrameKind, reset_turn_counters
from dune_imperium.rules.pauses import pause_is_pending
from dune_imperium.rules.phases import (
    draw_round_hands,
    resolve_recall_or_endgame,
    turn_frame,
)
from dune_imperium.rules.reveal_turn import (
    begin_reveal_turn,
    grant_late_reveal_effects,
    legal_reveal_actions,
)
from dune_imperium.rules.tech import (
    apply_endgame_tech_effects,
    legal_tech_acquire_effect_actions,
    legal_tech_flip_actions,
    legal_tech_reveal_actions,
    push_tech_acquisition,
)
from dune_imperium.rules.turn_rows import tech_influence_blocked
from dune_imperium.simulation.invariants import check_observation_privacy

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
ENGINE = UprisingRulesEngine()
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
# A card's refusal names its printer; no card of the original game prints the
# Acquire Tech icon yet, so the frame borrows a Bloodlines Intrigue's.
PRINTER = printer_value(Source.INTRIGUE, "battlefield_research")


def _original(*, rise_of_ix: bool = True) -> GameState:
    """An original game's opening state, with or without Rise of Ix."""

    state = ENGINE.reset(RulesetConfig(base_game=BaseGame.IMPERIUM), 3)
    return replace(state, config=replace(state.config, rise_of_ix=rise_of_ix))


def _seat(state: GameState, seat: int, **changes: Any) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def _round_trips(state: GameState, *seats: int) -> None:
    """Every row the engine offers ``seats`` encodes and decodes to itself in
    the state's own catalog (the original game with Rise of Ix)."""

    codec = ActionCodec(state.config)
    for seat in seats:
        for action in ENGINE.legal_actions(state, seat):
            assert codec.decode(codec.encode(action), action.actor) == action


# --- Acquire effects: Windtraps' water, Shuttle Fleet's two Factions ---------


def _start() -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an original game at seat 0's first turn with Rise of Ix
    switched on (the acquisition tests' start)."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(ORIGINAL, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, replace(state, config=replace(state.config, rise_of_ix=True))


def _acquired(tile: str, **seat: Any) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 with 9 spice buys ``tile`` (top of a stack of its own) with an
    Acquire Tech icon; the acquire effect it owes is pending on its turn."""

    engine, state = _start()
    owner = state.players[0]
    state = replace(
        _seat(
            state,
            0,
            resources=replace(owner.resources, spice=9),
            **seat,
        ),
        tech_stacks=((tile,), (), ()),
    )
    state = push_tech_acquisition(
        state, 0, discount=0, source="s", printer=PRINTER
    ).state
    result = tech_rules.apply_tech_acquisition(
        state, DomainAction("acquire_tech", 0, (("tech_id", tile),))
    )
    return engine, result.state


def test_windtraps_gives_one_water_when_it_is_acquired() -> None:
    """Windtraps -- spice 2, acquire effect "water 1" [Rise of Ix p. 4]
    (docs/rules/rise-of-ix.md 4): the tile queues its ``water`` key, and
    resolving it pays one water on the owner's turn."""

    engine, state = _acquired("windtraps")
    owner = state.players[0]
    assert owner.tech_ids == ("windtraps",)
    assert tech_rules.pending_tech_acquire_effects(state.decision_stack[-1]) == (
        "windtraps:water",
    )
    resolve = DomainAction(
        "resolve_tech_acquire_effect",
        0,
        (("effect", "water"), ("tech_id", "windtraps")),
    )
    assert resolve in legal_tech_acquire_effect_actions(state, 0)

    paid = apply_whole(engine, state, resolve)
    assert paid.state.players[0].resources.water == owner.resources.water + 1
    assert [event.kind for event in paid.events] == ["tech_acquire_effect_resolved"]
    assert dict(paid.events[0].payload)["water"] == 1
    assert not tech_rules.pending_tech_acquire_effects(paid.state.decision_stack[-1])


def _choose(state: GameState, faction: str, effect: str) -> DomainAction:
    row = DomainAction(effect, 0, (("faction", faction),))
    assert row in ENGINE.legal_actions(state, 0), (faction, effect)
    return row


def test_shuttle_fleet_names_two_different_factions_then_pays_both() -> None:
    """Shuttle Fleet -- spice 6, acquire effect "서로 다른 진영 둘을 먼저 골라
    Influence 1씩 (OQ-114, 2026-10-22 사용자 확정)" (docs/rules/rise-of-ix.md
    4): after the effect's own row the seat picks a Faction, then a second one
    that is not the first (the engine's steps), and both Influence are paid
    only once both are named."""

    engine, state = _acquired("shuttle_fleet")
    assert tech_rules.pending_tech_acquire_effects(state.decision_stack[-1]) == (
        "shuttle_fleet:distinct_influence",
    )
    icon = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "gain_influence"
    )
    assert dict(icon.arguments) == {
        "icon": "distinct_influence",
        "printed": "shuttle_fleet",
        "source": "tech",
    }
    before = state.players[0].influence
    state = engine.apply(state, icon).state

    # The first pick: any of the four Factions.
    first = {
        dict(action.arguments)["faction"]
        for action in engine.legal_actions(state, 0)
        if action.action_id == "choose_faction"
    }
    assert first == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    picked = engine.apply(state, _choose(state, "fremen", "choose_faction"))
    # Nothing is paid by the first pick alone, and the second cannot repeat it.
    assert picked.state.players[0].influence == before
    assert not [e for e in picked.events if e.kind == "influence_gained"]
    second = {
        dict(action.arguments)["faction"]
        for action in engine.legal_actions(picked.state, 0)
        if action.action_id == "choose_faction"
    }
    assert second == {"emperor", "spacing_guild", "bene_gesserit"}

    done = engine.apply(
        picked.state, _choose(picked.state, "emperor", "choose_faction")
    )
    assert [e.kind for e in done.events] == [
        "tech_acquire_effect_resolved",
        "influence_gained",
        "influence_gained",
    ]
    after = done.state.players[0].influence
    assert (after.fremen, after.emperor) == (before.fremen + 1, before.emperor + 1)
    assert (after.spacing_guild, after.bene_gesserit) == (
        before.spacing_guild,
        before.bene_gesserit,
    )
    assert not tech_rules.pending_tech_acquire_effects(done.state.decision_stack[-1])


def test_shuttle_fleet_pays_the_one_faction_that_can_still_rise() -> None:
    """OQ-060 (a cube at the top of its track cannot rise; "choose a Faction"
    never offers one) with OQ-114's "Choose two": with three Factions at the
    top only the fourth is offered, alone, and pays one Influence; with all
    four at the top nothing is offered and the effect is blocked (the turn's
    end press lapses it)."""

    top = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=1)
    _, state = _acquired("shuttle_fleet", influence=top)
    offered = legal_tech_acquire_effect_actions(state, 0)
    assert [dict(action.arguments).get("second_faction") for action in offered] == [
        None
    ]
    assert [dict(action.arguments)["faction"] for action in offered] == ["fremen"]
    assert not tech_influence_blocked(
        "shuttle_fleet:distinct_influence", state.players[0]
    )
    paid = tech_rules.apply_tech_acquire_effect(state, offered[0])
    assert paid.state.players[0].influence.fremen == 2
    assert [e.kind for e in paid.events].count("influence_gained") == 1

    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    _, state = _acquired("shuttle_fleet", influence=full)
    assert legal_tech_acquire_effect_actions(state, 0) == ()
    assert tech_influence_blocked("shuttle_fleet:distinct_influence", state.players[0])


def test_a_second_faction_alone_or_the_same_twice_is_not_a_legal_row() -> None:
    """ "서로 다른 진영 둘" (OQ-114): with every Faction able to rise, the rows
    name two different ones, never one alone and never the same twice."""

    _, state = _acquired("shuttle_fleet")
    rows = legal_tech_acquire_effect_actions(state, 0)
    pairs = {
        (
            dict(action.arguments)["faction"],
            dict(action.arguments).get("second_faction"),
        )
        for action in rows
    }
    assert len(rows) == len(pairs) == 12
    assert all(second is not None and first != second for first, second in pairs)


# --- Round Start: Holtzman Engine's card, Shuttle Fleet's 2 Solari -----------


def _round_start(first_player: int = 0, **tiles: tuple[str, ...]) -> GameState:
    """Round 2's Round Start with every seat's hand empty and the deck at the
    top, ``first_player`` leading; ``tiles`` maps ``seat<N>`` to its tiles."""

    state = replace(
        _original(),
        phase=GamePhase.ROUND_START,
        round_number=2,
        first_player=first_player,
        decision_stack=(),
    )
    for name, held in tiles.items():
        state = _seat(state, int(name.removeprefix("seat")), tech_ids=held)
    return state


def test_holtzman_engine_draws_a_card_and_shuttle_fleet_pays_two_solari() -> None:
    """Holtzman Engine -- "Round Start: 카드 1장"; Shuttle Fleet -- "Round
    Start: 2 Solari" (docs/rules/rise-of-ix.md 4, OQ-122): after the five-card
    draw the holder has six cards, or two more Solari; a seat without either
    tile has five cards and its Solari."""

    state = _round_start(seat0=("holtzman_engine",), seat1=("shuttle_fleet",))
    solari = [seat.resources.solari for seat in state.players]
    after = draw_round_hands(state).state

    assert [len(seat.hand) for seat in after.players] == [6, 5, 5, 5]
    assert [seat.resources.solari for seat in after.players] == [
        solari[0],
        solari[1] + 2,
        solari[2],
        solari[3],
    ]
    # The sixth card is the next one of the deck.
    assert after.players[0].hand == state.players[0].deck[:6]
    assert after.phase is GamePhase.PLAYER_TURNS


def test_the_round_start_lines_follow_the_draw_from_the_first_player() -> None:
    """OQ-122 (user ruling 2026-10-23, the app's order): "Conflict 공개 →
    Control 방어 → 각자 5장 → Holtzman Engine의 카드 1장·Shuttle Fleet의 2 Solari
    → ... → 첫 turn. 좌석 사이는 First Player부터": every seat's five cards come
    first, then the tiles' lines seat by seat from the First Player (seat 2):
    Shuttle Fleet's seat 3 before Holtzman Engine's seat 0, which seat-number
    order would put the other way round."""

    state = _round_start(2, seat0=("holtzman_engine",), seat3=("shuttle_fleet",))
    result = draw_round_hands(state)

    ids = [event.event_id for event in result.events]
    assert ids == [
        *(f"round:2:player:{seat}:draw" for seat in range(4)),
        "round:2:player:3:tech:shuttle_fleet:resources",
        "round:2:player:0:tech:holtzman_engine:draw",
    ]
    assert [len(seat.hand) for seat in result.state.players] == [6, 5, 5, 5]


def test_one_seats_two_lines_are_the_card_and_then_the_solari() -> None:
    """OQ-122 names "Holtzman Engine의 카드 1장·Shuttle Fleet의 2 Solari" in that
    order, after the five-card draw: a seat holding both gets the card, then
    the Solari."""

    state = _round_start(1, seat1=("holtzman_engine", "shuttle_fleet"))
    solari = state.players[1].resources.solari
    result = draw_round_hands(state)

    ids = [event.event_id for event in result.events]
    assert ids[4:] == [
        "round:2:player:1:tech:holtzman_engine:draw",
        "round:2:player:1:tech:shuttle_fleet:resources",
    ]
    seat = result.state.players[1]
    assert len(seat.hand) == 6
    assert seat.resources.solari == solari + 2


def test_holtzman_engines_card_may_need_the_discard_pile_shuffled() -> None:
    """Holtzman Engine's card from a deck the five-card draw emptied is the
    in-turn personal draw: its discard pile is shuffled by a chance step
    (docs/rules/rise-of-ix.md 4, OQ-122), and the card is drawn from the new
    deck."""

    state = _round_start(seat0=("holtzman_engine",))
    owner = state.players[0]
    deck, discard = owner.deck[:5], owner.deck[5:8]
    state = _seat(state, 0, deck=deck, discard_pile=discard)
    after = draw_round_hands(state).state

    assert len(after.players[0].hand) == 5
    frame = after.decision_stack[-1]
    assert frame.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
    assert isinstance(frame.decision, ChanceDecision)
    resolved = ENGINE.apply(after, ChanceResolver(seed=1).resolve(frame.decision))
    seat = resolved.state.players[0]
    assert len(seat.hand) == 6 and len(seat.deck) == 2 and seat.discard_pile == ()
    assert set(seat.hand[5:]) <= set(discard)
    assert resolved.state.decision_stack[-1].kind == FrameKind.TURN


def test_an_empty_deck_and_discard_gives_holtzman_engine_nothing() -> None:
    """With neither deck nor discard pile left there is no card to draw."""

    state = _round_start(seat0=("holtzman_engine",))
    owner = state.players[0]
    state = _seat(state, 0, deck=owner.deck[:5], discard_pile=())
    after = draw_round_hands(state)
    assert len(after.state.players[0].hand) == 5
    assert not any("holtzman_engine" in event.event_id for event in after.events)
    assert after.state.decision_stack[-1].kind == FrameKind.TURN


def test_the_tiles_need_rise_of_ix_to_be_held() -> None:
    """Nothing changes without Rise of Ix: a game whose config has neither the
    expansion nor the Tech Module cannot hold a tile at all, so no Round Start,
    Reveal or Combat line of these tiles can run there."""

    state = replace(
        _original(rise_of_ix=False),
        config=RulesetConfig(base_game=BaseGame.IMPERIUM),
    )
    with pytest.raises(ValueError, match="Tech tiles require the Tech Module"):
        _seat(state, 0, tech_ids=("windtraps",))


# --- Reveal turn: Artillery, Minimic Film, Restricted Ordnance, Disposal -----

DAGGER_0 = "player:0:starter:dagger:0"
DAGGER_1 = "player:0:starter:dagger:1"
CONVINCING_0 = "player:0:starter:convincing_argument:0"
CONVINCING_1 = "player:0:starter:convincing_argument:1"
RECON = "player:0:starter:reconnaissance:0"
DIPLOMACY = "player:0:starter:diplomacy:0"
# Two swords (the Daggers) and four Persuasion (2 + 1 + 1).
HAND = (DAGGER_0, DAGGER_1, CONVINCING_0, RECON, DIPLOMACY)


def _revealing(
    *,
    tiles: tuple[str, ...] = (),
    high_council: bool = False,
    unit: bool = True,
    hand: tuple[str, ...] = HAND,
    deck_top: tuple[str, ...] = (),
) -> GameState:
    """Seat 0's Reveal turn over ``hand`` with a troop in the Conflict (two
    strength) unless ``unit`` is False; ``deck_top`` leads its deck."""

    state = replace(
        _original(),
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        decision_stack=(turn_frame(1, 0),),
    )
    owner = state.players[0]
    rest = tuple(card for card in owner.deck if card not in (*hand, *deck_top))
    state = _seat(
        state,
        0,
        hand=hand,
        deck=(*deck_top, *rest),
        tech_ids=tiles,
        high_council=high_council,
        **(
            {
                "troops_garrison": owner.troops_garrison - 1,
                "troops_conflict": 1,
                "combat_strength": 2,
            }
            if unit
            else {}
        ),
    )
    return begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state


def _context(state: GameState) -> dict[str, Any]:
    return dict(state.decision_stack[-1].context)


def _strength(state: GameState) -> int:
    return state.players[0].combat_strength


def test_minimic_film_gives_one_persuasion() -> None:
    """Minimic Film -- "Reveal turn: Persuasion 1" [Rise of Ix p. 4]
    (docs/rules/rise-of-ix.md 4): the Reveal's Persuasion, spendable and
    counted among the turn's generated Persuasion, is one more."""

    base = _context(_revealing())
    film = _context(_revealing(tiles=("minimic_film",)))
    assert base["persuasion"] == 4
    assert film["persuasion"] == film["persuasion_generated"] == 5
    assert _strength(_revealing(tiles=("minimic_film",))) == _strength(_revealing())


def test_restricted_ordnance_gives_four_swords_with_a_high_council_seat() -> None:
    """Restricted Ordnance -- "Reveal turn: High Council 자리가 있으면 sword 4"
    [Rise of Ix p. 4] (docs/rules/rise-of-ix.md 4): four swords with the seat,
    none without it, and the swords count only with a unit in the Conflict
    ("Conflict에 unit이 하나도 없으면 sword가 있어도 strength는 0이다"
    [Main p. 12]) while the Reveal still records them."""

    tile = ("restricted_ordnance",)
    plain = _revealing(high_council=True)
    seated = _revealing(tiles=tile, high_council=True)
    unseated = _revealing(tiles=tile)

    assert _strength(seated) == _strength(plain) + 4
    assert _context(seated)["sword_strength"] == _context(plain)["sword_strength"] + 4
    assert _strength(unseated) == _strength(_revealing())
    assert (
        _context(unseated)["sword_strength"] == _context(_revealing())["sword_strength"]
    )
    assert _context(seated)["tech_granted"] == "restricted_ordnance"

    lonely = _revealing(tiles=tile, high_council=True, unit=False)
    assert _strength(lonely) == 0
    assert _context(lonely)["sword_strength"] == _context(seated)["sword_strength"]


def test_a_high_council_seat_taken_later_in_the_reveal_pays_the_swords_then() -> None:
    """The Reveal's effects resolve in any order ([Main p. 12]; OQ-095 (7)): a
    High Council seat that comes after the Reveal began opens Restricted
    Ordnance's swords at that moment, once."""

    started = _revealing(tiles=("restricted_ordnance",))
    assert _context(started).get("tech_granted", "") == ""
    seated = _seat(started, 0, high_council=True)
    late = grant_late_reveal_effects(RuleResult(state=seated))

    assert _strength(late.state) == _strength(started) + 4
    assert [event.kind for event in late.events] == ["tech_reveal_bonus"]
    assert _context(late.state)["tech_granted"] == "restricted_ordnance"
    again = grant_late_reveal_effects(RuleResult(state=late.state))
    assert _strength(again.state) == _strength(late.state)
    assert not again.events


def test_artillery_gives_a_sword_for_each_revealed_card_giving_swords() -> None:
    """Artillery -- "Reveal turn: sword를 주는 공개 카드마다 sword 1" [Rise of
    Ix p. 4] (docs/rules/rise-of-ix.md 4): two Daggers reveal two sword cards,
    so two more swords (the three cards with Persuasion only give none); the
    swords need a unit in the Conflict."""

    plain = _revealing()
    artillery = _revealing(tiles=("artillery",))
    assert _strength(artillery) == _strength(plain) + 2
    assert (
        _context(artillery)["sword_strength"] == _context(plain)["sword_strength"] + 2
    )
    assert _context(artillery)["artillery_counted"] == 2

    no_sword = _revealing(tiles=("artillery",), hand=(CONVINCING_0, RECON, DIPLOMACY))
    assert _context(no_sword)["sword_strength"] == 0
    lonely = _revealing(tiles=("artillery",), unit=False)
    assert _strength(lonely) == 0
    assert _context(lonely)["sword_strength"] == _context(artillery)["sword_strength"]


def test_artillery_counts_a_sword_card_that_arrives_late_once() -> None:
    """A card drawn in the owner's own Reveal is revealed and used at once
    ([FAQ p. 3]) and, if it gives swords, is one more revealed card giving
    swords: Artillery tops its count up (as Leadership does, never taking a
    sword back), paying one sword for the Dagger on top of the Dagger's own."""

    started = _revealing(
        tiles=("artillery",),
        hand=(DAGGER_0, CONVINCING_0, RECON, DIPLOMACY),
        deck_top=(DAGGER_1,),
    )
    assert _context(started)["artillery_counted"] == 1
    drawn = draw_or_request_personal_cards(started, 0, 1, source="late")

    assert _context(drawn.state)["artillery_counted"] == 2
    # The late Dagger's own sword and the Artillery sword it adds.
    assert _strength(drawn.state) == _strength(started) + 2


def test_a_reveal_without_these_tiles_is_what_it_was() -> None:
    """Nothing changes without the tiles: a Reveal with a Tech Module tile or
    none holds no Ix key on its frame."""

    context = _context(_revealing())
    assert "artillery_counted" not in context
    assert context["tech_reveal_pending"] == ""
    assert context["tech_granted"] == ""


def _rows(state: GameState) -> list[DomainAction]:
    return [
        action
        for action in legal_tech_reveal_actions(state, 0)
        if action.action_id == "trash_disposal_facility_card"
    ]


def test_disposal_facility_trashes_a_card_in_play_with_six_persuasion() -> None:
    """Disposal Facility -- "Reveal turn: 그 turn에 얻은 Persuasion 합계(쓴 것
    포함)가 6 이상이면 in play 카드 하나를 trash할 수 있다 (OQ-126)"
    (docs/rules/rise-of-ix.md 4): below six nothing is offered; at six the seat
    may trash one card in play (not a card in its discard pile), once."""

    tile = ("disposal_facility",)
    below = _revealing(tiles=tile)
    assert _context(below)["persuasion_generated"] == 4
    assert _rows(below) == []

    state = _revealing(tiles=tile, high_council=True)
    assert _context(state)["persuasion_generated"] == 6
    owner = state.players[0]
    resting = owner.deck[0]
    state = _seat(state, 0, deck=owner.deck[1:], discard_pile=(resting,))
    rows = _rows(state)
    assert {dict(row.arguments)["card_id"] for row in rows} == set(owner.in_play)
    assert len(rows) == 5

    trash = DomainAction("trash_disposal_facility_card", 0, (("card_id", DAGGER_1),))
    assert trash in ENGINE.whole_actions(state, 0)
    trashed = apply_whole(ENGINE, state, trash).state
    assert DAGGER_1 not in trashed.players[0].in_play
    assert trashed.players[0].discard_pile == (resting,)
    assert _rows(trashed) == []
    assert _context(trashed)["tech_reveal_pending"] == ""


def test_disposal_facility_counts_persuasion_already_spent() -> None:
    """OQ-126: the total is what the turn generated, "구매에 쓴 것 포함", and
    "카드를 산 뒤에도 쓸 수 있고, 순서가 결과를 바꾸지 않는다": buying a card
    with Persuasion leaves the rows open."""

    state = _revealing(tiles=("disposal_facility",), high_council=True)
    bought = apply_whole(
        ENGINE,
        state,
        DomainAction("acquire_reserve", 0, (("card_id", "arrakis_liaison"),)),
    ).state
    assert _context(bought)["persuasion"] < _context(bought)["persuasion_generated"]
    assert _context(bought)["persuasion_generated"] == 6
    # The bought card goes to the discard pile, not into play.
    assert len(_rows(bought)) == 5


def test_disposal_facility_opens_when_persuasion_reaches_six_later() -> None:
    """OQ-126's implementation note: "합계가 같은 Reveal turn 안에서 나중에 6에
    이르면 그때 쓸 수 있다": a card drawn in the Reveal and revealed at once
    (2 Persuasion) lifts four to six, and the rows open then."""

    started = _revealing(tiles=("disposal_facility",), deck_top=(CONVINCING_1,))
    assert _rows(started) == []
    drawn = draw_or_request_personal_cards(started, 0, 1, source="late")
    assert _context(drawn.state)["persuasion_generated"] == 6
    assert len(_rows(drawn.state)) == 6


def test_disposal_facility_is_a_may_that_never_holds_the_turn() -> None:
    """ "you may trash" (a "may"): the seat ends its Reveal without using it."""

    state = _revealing(tiles=("disposal_facility",), high_council=True)
    assert _rows(state)
    assert any(
        action.action_id == "finish_reveal" for action in ENGINE.legal_actions(state, 0)
    )


def test_the_reveal_rows_run_through_the_engine_and_the_codec() -> None:
    """The Reveal with Disposal Facility at six Persuasion offers the trash as
    the tile's effect row and the card as its target row; every row it
    offers encodes and decodes to itself in the original game with Rise of
    Ix's catalog."""

    state = _revealing(tiles=("disposal_facility",), high_council=True)
    legal = ENGINE.legal_actions(state, 0)
    effect = DomainAction(
        "trash", 0, (("printed", "disposal_facility"), ("source", "tech"))
    )
    assert effect in legal
    after = ENGINE.apply(state, effect).state
    targets = [
        action
        for action in ENGINE.legal_actions(after, 0)
        if action.action_id == "choose_personal_card"
    ]
    assert len(targets) == 5
    _round_trips(state, 0)
    _round_trips(after, 0)
    done = ENGINE.apply(after, targets[0])
    assert len(done.state.players[0].in_play) == 4


# --- Conflict won: Windtraps' water, Detonation Devices ----------------------

CHOICE = FrameKind.DREADNOUGHT_CONTROL_CHOICE
WINDOW = FrameKind.COMBAT_REWARD_ICONS


def _combat() -> GameState:
    state = _original()
    return replace(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != "skirmish_a"),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != "skirmish_a"
        ),
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        decision_stack=(),
        current_conflict_ids=("skirmish_a",),
        combat_intrigue_complete=False,
        combat_rewards_resolved=False,
        combat_end_triggers_offered=False,
        dreadnought_control=(),
    )


def _fight(
    *,
    winner_tiles: tuple[str, ...] = (),
    loser_tiles: tuple[str, ...] = (),
    winner_dreadnoughts: int = 1,
) -> GameState:
    """Seat 0 (a troop and its dreadnoughts) wins over seat 1's dreadnought;
    the winner's window is on top (the Combat Intrigue passes answered)."""

    state = _combat()
    winner = state.players[0]
    state = _seat(
        state,
        0,
        troops_garrison=winner.troops_garrison - 1,
        troops_conflict=1,
        dreadnoughts_conflict=winner_dreadnoughts,
        combat_strength=2 + 3 * winner_dreadnoughts,
        tech_ids=winner_tiles,
    )
    state = _seat(
        state, 1, dreadnoughts_conflict=1, combat_strength=3, tech_ids=loser_tiles
    )
    state = begin_combat_intrigue(state).state
    while state.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE:
        owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        state = apply_whole(
            ENGINE, state, DomainAction("pass_combat_intrigue", owner)
        ).state
    assert state.decision_stack[-1].kind == WINDOW
    return state


def _icon(kind: str) -> DomainAction:
    return DomainAction("resolve_combat_reward_icon", 0, (("effect", kind),))


def _icons(state: GameState) -> list[str]:
    text = str(dict(state.decision_stack[-1].context)["icons"])
    return text.split(",") if text else []


def test_windtraps_pays_one_water_to_the_sole_winner() -> None:
    """Windtraps -- "Conflict를 이기면 water 1" [Rise of Ix p. 4]
    (docs/rules/rise-of-ix.md 4), a row of the winner's window like Planetary
    Array's ("고를 것 없는 자동 줄", OQ-121 ruling 6 (1)): the sole winner's
    window holds a ``windtraps`` row, resolving it pays one water."""

    state = _fight(winner_tiles=("windtraps",))
    assert "windtraps" in _icons(state)
    assert _icon("windtraps") in ENGINE.whole_actions(state, 0)

    water = state.players[0].resources.water
    paid = apply_whole(ENGINE, state, _icon("windtraps"))
    assert paid.state.players[0].resources.water == water + 1
    kinds = [event.kind for event in paid.events]
    assert "resources_gained" in kinds
    gained = next(e for e in paid.events if e.kind == "resources_gained")
    assert dict(gained.payload)["water"] == 1
    assert "windtraps" not in _icons(paid.state)


def test_windtraps_pays_only_the_winner() -> None:
    """ "Conflict를 이기면": a seat that holds the tile but does not win gets no
    row, and a winner without the tile gets none either."""

    loser = _fight(loser_tiles=("windtraps",))
    assert "windtraps" not in _icons(loser)
    # Seat 0 resolves its whole window; the second place's window follows.
    state = loser
    while state.decision_stack[-1].kind == WINDOW and (
        state.decision_stack[-1].decision.owner == 0  # type: ignore[union-attr]
    ):
        row = legacy_combat_reward_icon(state, 0)
        assert row is not None
        state = apply_whole(ENGINE, state, row).state
        if state.decision_stack and state.decision_stack[-1].kind == CHOICE:
            state = apply_whole(
                ENGINE,
                state,
                DomainAction(
                    "place_combat_reward_dreadnought",
                    0,
                    (("space_id", "arrakeen"),),
                ),
            ).state
    if pause_is_pending(state):
        state = ENGINE.apply(state, pause_outcome(state)).state
    assert state.decision_stack[-1].decision.owner == 1  # type: ignore[union-attr]
    assert "windtraps" not in _icons(state)


def _choice(
    tiles: tuple[str, ...] = ("detonation_devices",), **fight: Any
) -> GameState:
    """The winner's choice of a Control space with its dreadnought."""

    state = _fight(winner_tiles=tiles, **fight)
    after = apply_whole(ENGINE, state, _icon("dreadnought_control")).state
    assert after.decision_stack[-1].kind == CHOICE
    return after


DETONATE = DomainAction("detonate_combat_reward_dreadnought", 0)


def test_detonation_devices_returns_the_dreadnought_for_one_victory_point() -> None:
    """Detonation Devices -- "dreadnought로 이겼을 때 칸을 지배하는 대신
    dreadnought 하나를 supply로 돌려 1 VP("may")" [Rise of Ix p. 4]
    (docs/rules/rise-of-ix.md 4, OQ-121 ruling 3): inside the winner's choice of
    a Control space the seat may send the Conflict dreadnought back to its
    supply for 1 VP; no space is controlled by it."""

    state = _choice()
    assert DETONATE in ENGINE.whole_actions(state, 0)
    owner = state.players[0]

    done = apply_whole(ENGINE, state, DETONATE)
    seat = done.state.players[0]
    assert seat.dreadnoughts_conflict == owner.dreadnoughts_conflict - 1 == 0
    assert seat.dreadnoughts_supply == owner.dreadnoughts_supply + 1
    assert seat.victory_points == owner.victory_points + 1
    assert done.state.dreadnought_control == ()
    assert [event.kind for event in done.events] == [
        "dreadnought_detonated",
        "resources_gained",
    ]
    assert dict(done.events[1].payload)["victory_points"] == 1
    # The choice is made: the frame is gone and the window goes on.
    assert done.state.decision_stack[-1].kind == WINDOW


def test_detonation_devices_may_be_declined_for_a_control_space() -> None:
    """The Detonation is a "may": the same choice still offers every Control
    space holding no dreadnought, and taking one controls it as without the
    tile (OQ-121 ruling 3: "Detonation과 상관없이" the rest is unchanged)."""

    state = _choice()
    place = DomainAction(
        "place_combat_reward_dreadnought", 0, (("space_id", "arrakeen"),)
    )
    assert place in ENGINE.whole_actions(state, 0)
    owner = state.players[0]

    done = apply_whole(ENGINE, state, place)
    seat = done.state.players[0]
    assert done.state.dreadnought_control == (("arrakeen", 0, False),)
    assert seat.dreadnoughts_supply == owner.dreadnoughts_supply
    assert seat.victory_points == owner.victory_points


def test_there_is_no_detonation_without_the_tile() -> None:
    """A winner without Detonation Devices (a different tile instead) is
    offered the Control spaces only."""

    state = _choice(tiles=("windtraps",))
    assert DETONATE not in ENGINE.whole_actions(state, 0)
    assert all(
        action.action_id == "place_combat_reward_dreadnought"
        for action in ENGINE.whole_actions(state, 0)
    )


def test_a_second_dreadnought_goes_to_the_garrison_after_a_detonation() -> None:
    """With two dreadnoughts in the Conflict one is sent back to the supply by
    Detonation Devices; the other, which would not have gone to a space either,
    returns to the garrison with the troops when the Conflict is cleaned up
    ("Conflict에 남은 dreadnought는 정리 때 troop과 함께 garrison으로", OQ-121
    ruling 2)."""

    state = _choice(winner_dreadnoughts=2)
    detonated = apply_whole(ENGINE, state, DETONATE).state
    assert detonated.players[0].dreadnoughts_conflict == 1

    for _ in range(40):
        if detonated.phase is not GamePhase.COMBAT:
            break
        if pause_is_pending(detonated):
            detonated = ENGINE.apply(detonated, pause_outcome(detonated)).state
            continue
        owner = detonated.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        row = legacy_combat_reward_icon(detonated, owner)
        assert row is not None
        detonated = apply_whole(ENGINE, detonated, row).state
    seat = detonated.players[0]
    assert (seat.dreadnoughts_conflict, seat.dreadnoughts_garrison) == (0, 1)
    assert seat.dreadnoughts_supply == 1


def test_the_combat_rows_run_through_the_engine_and_the_codec() -> None:
    """The winner's window with Windtraps, and the choice with Detonation
    Devices, offer rows that encode and decode to themselves in the original
    game with Rise of Ix's catalog; the original game's own catalog holds none
    of the new rows."""

    window = _fight(winner_tiles=("windtraps", "detonation_devices"))
    _round_trips(window, 0)
    choice = apply_whole(ENGINE, window, _icon("dreadnought_control")).state
    _round_trips(choice, 0)
    plain = ActionCodec(RulesetConfig(base_game=BaseGame.IMPERIUM)).catalog
    ix = ActionCodec(IX).catalog
    for action_id in (
        "detonate_combat_reward_dreadnought",
        "trash_disposal_facility_card",
    ):
        assert not any(t.action_id == action_id for t in plain)
    assert not any(dict(t.arguments).get("printed") == "windtraps" for t in plain)
    assert any(
        t.action_id == "gain"
        and dict(t.arguments).get("printed") == "detonation_devices"
        for t in ix
    )
    assert any(
        t.action_id == "gain" and dict(t.arguments).get("icon") == "windtraps"
        for t in ix
    )


def test_the_tech_module_rows_are_what_they_were() -> None:
    """The Tech Module's 18 tiles keep their sixteen acquire keys, and the
    Ix tiles hold one more key each only where the tile prints the icon
    (``water``, ``distinct_influence``)."""

    assert sum(len(tile.acquire_effect_keys) for tile in TECH_TILES) == 16
    assert sum(len(tile.acquire_effect_keys) for tile in IX_TECH_TILES) == 9


# --- Endgame: Chaumurky, Holtzman Engine, Memocorders, Spy Satellites --------

SPICE_MUST_FLOW = "reserve:imperium_the_spice_must_flow:"


def _endgame(**seats: dict[str, Any]) -> GameState:
    """The original game's Endgame with Rise of Ix; ``seats`` maps
    ``seat<N>`` to that seat's changes."""

    state = replace(_original(), phase=GamePhase.ENDGAME, reveal_order=(0, 1, 2, 3))
    for name, changes in seats.items():
        state = _seat(state, int(name.removeprefix("seat")), **changes)
    return state


def _vp(state: GameState, seat: int = 0) -> int:
    """Victory Points gained since the opening state (each seat starts on 1)."""

    return state.players[seat].victory_points - _original().players[seat].victory_points


def test_chaumurky_wins_a_victory_point_tie_before_every_other_tie_break() -> None:
    """Chaumurky -- "Endgame: 동률을 이긴다(다른 동률 기준보다 먼저 [FAQ p. 1])"
    (docs/rules/rise-of-ix.md 4): of two seats tied on Victory Points the
    holder ranks first even though the other has more spice, Solari, water,
    garrisoned troops and the later Reveal, which break a tie without it
    ([DI p. 13], [FAQ p. 2])."""

    rich = {
        "victory_points": 5,
        "resources": replace(
            _original().players[1].resources, spice=9, solari=9, water=9
        ),
        "troops_supply": 0,
        "troops_garrison": 12,
    }
    holder = {"victory_points": 5, "tech_ids": ("chaumurky",)}
    without = _endgame(seat0={"victory_points": 5}, seat1=rich)
    assert [s.player for s in final_standings(without)][:2] == [1, 0]

    state = _endgame(seat0=holder, seat1=rich)
    # The later Reveal is seat 3's; seat 1's Reveal is earlier, so make seat 1
    # the most recent Revealer too: nothing but the tile may decide.
    state = replace(state, reveal_order=(0, 2, 3, 1))
    order = final_standings(state)
    assert [s.player for s in order][:2] == [0, 1]
    assert order[0].rank == 1


def test_chaumurky_does_not_beat_a_victory_point_lead() -> None:
    """Chaumurky breaks ties only: "동률을" -- a seat one Victory Point ahead
    still ranks above the holder."""

    state = _endgame(
        seat0={"victory_points": 5, "tech_ids": ("chaumurky",)},
        seat1={"victory_points": 6},
    )
    assert [s.player for s in final_standings(state)][:2] == [1, 0]


def test_holtzman_engine_pays_one_vp_with_two_spice_must_flow() -> None:
    """Holtzman Engine -- "Endgame: The Spice Must Flow 2장 이상이면 1 VP"
    (docs/rules/rise-of-ix.md 4), the copies counted as OQ-123 rules (deck,
    hand, discard pile and in play; not trashed): one copy pays nothing, two
    anywhere pay one VP."""

    tile = ("holtzman_engine",)
    one = _endgame(seat0={"tech_ids": tile, "hand": (f"{SPICE_MUST_FLOW}0",)})
    assert _vp(apply_endgame_tech_effects(one).state) == 0

    two = _endgame(
        seat0={
            "tech_ids": tile,
            "hand": (f"{SPICE_MUST_FLOW}0",),
            "discard_pile": (f"{SPICE_MUST_FLOW}1",),
        }
    )
    result = apply_endgame_tech_effects(two)
    assert _vp(result.state) == 1
    assert [event.kind for event in result.events] == ["resources_gained"]
    # Another seat's copies are not the holder's.
    other = _endgame(
        seat0={"tech_ids": tile},
        seat1={"hand": (f"{SPICE_MUST_FLOW}0", f"{SPICE_MUST_FLOW}1")},
    )
    assert _vp(apply_endgame_tech_effects(other).state) == 0


def test_memocorders_pays_one_vp_with_three_influence_on_all_four_tracks() -> None:
    """Memocorders -- "Endgame: 네 track 모두 Influence 3 이상이면 1 VP"
    (docs/rules/rise-of-ix.md 4): 3 on every track pays one VP; a track at 2
    pays nothing."""

    tile = ("memocorders",)
    full = Influence(emperor=3, spacing_guild=3, bene_gesserit=4, fremen=3)
    paid = apply_endgame_tech_effects(
        _endgame(seat0={"tech_ids": tile, "influence": full})
    )
    assert _vp(paid.state) == 1
    short = replace(full, fremen=2)
    unpaid = _endgame(seat0={"tech_ids": tile, "influence": short})
    assert _vp(apply_endgame_tech_effects(unpaid).state) == 0
    assert (
        _vp(apply_endgame_tech_effects(_endgame(seat0={"influence": full})).state) == 0
    )


def test_spy_satellites_pays_one_vp_for_each_faction_at_one_influence_or_less() -> None:
    """Spy Satellites -- "Endgame: Influence 1 이하인 진영마다 1 VP"
    (docs/rules/rise-of-ix.md 4): a track at 0 or 1 counts, at 2 does not."""

    tile = ("spy_satellites",)
    influence = Influence(emperor=0, spacing_guild=1, bene_gesserit=2, fremen=5)
    state = _endgame(seat0={"tech_ids": tile, "influence": influence})
    result = apply_endgame_tech_effects(state)
    assert _vp(result.state) == 2
    high = Influence(emperor=2, spacing_guild=2, bene_gesserit=2, fremen=2)
    none = _endgame(seat0={"tech_ids": tile, "influence": high})
    assert _vp(apply_endgame_tech_effects(none).state) == 0


def test_the_endgame_tiles_pay_as_the_endgame_opens() -> None:
    """The Endgame lines pay as the Endgame opens, before its Intrigue window
    (OQ-040's convention), whether it opens on 10 Victory Points; a seat
    without the tiles scores nothing and the Tech Module's tiles are as
    they were."""

    full = Influence(emperor=3, spacing_guild=3, bene_gesserit=3, fremen=3)
    state = replace(
        _original(),
        phase=GamePhase.RECALL_OR_ENDGAME,
        first_player=0,
        decision_stack=(),
    )
    state = _seat(
        state, 0, victory_points=10, tech_ids=("memocorders",), influence=full
    )
    result = resolve_recall_or_endgame(state)
    assert result.state.phase is GamePhase.ENDGAME
    assert [seat.victory_points for seat in result.state.players] == [11, 1, 1, 1]
    assert [event.kind for event in result.events] == [
        "endgame_started",
        "resources_gained",
    ]


# --- Flip tiles: Flagship, Holoprojectors, Invasion Ships, Training Drones ---

DESERT_0 = "player:0:starter:dune_the_desert_planet:0"
DESERT_1 = "player:0:starter:dune_the_desert_planet:1"
SIGNET = "player:0:starter:signet_ring:0"


def _turn(*tiles: str, supply: int | None = None, **seat: Any) -> GameState:
    """Round 1 at seat 0's first turn (the turn frame), holding ``tiles``;
    ``supply`` leaves that many troops in its supply (the rest in the
    garrison)."""

    _, state = _start()
    owner = state.players[0]
    if supply is not None:
        seat["troops_supply"] = supply
        seat["troops_garrison"] = owner.troops_garrison + owner.troops_supply - supply
    return _seat(state, 0, tech_ids=tiles, **seat)


def _placed(state: GameState) -> GameState:
    """Seat 0 sends the Desert Planet card's Agent: the Agent-turn effect frame."""

    chosen = apply_whole(
        ENGINE, state, DomainAction("choose_agent_card", 0, (("card_id", DESERT_0),))
    ).state
    return apply_whole(
        ENGINE,
        chosen,
        DomainAction("place_agent", 0, (("space_id", "imperial_basin"),)),
    ).state


def _flip(tile: str, card: str | None = None) -> DomainAction:
    arguments = (
        (("tech_id", tile),)
        if card is None
        else (
            ("card_id", card),
            ("tech_id", tile),
        )
    )
    return DomainAction("flip_tech", 0, arguments)


def _flip_rows(state: GameState, tile: str) -> list[DomainAction]:
    return [
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "flip_tech" and dict(action.arguments)["tech_id"] == tile
    ]


def _solari(state: GameState, amount: int) -> GameState:
    owner = state.players[0]
    return _seat(state, 0, resources=replace(owner.resources, solari=amount))


def _flipped_back_at_round_start(tile: str) -> None:
    """ "다음 라운드 Round Start에 되돌린다" [Rise of Ix p. 4]."""

    state = _seat(_round_start(seat0=(tile,)), 0, tech_flipped=(tile,))
    assert draw_round_hands(state).state.players[0].tech_flipped == ()


def test_training_drones_recruits_a_troop_once_a_round() -> None:
    """Training Drones -- "troop 1" with the Flip icon [Rise of Ix p. 4]
    (docs/rules/rise-of-ix.md 4: "자기 turn(Agent·Reveal) 가운데 라운드에 한
    번, 쓰면 뒷면으로 뒤집고 다음 라운드 Round Start에 되돌린다" [FAQ p. 1]):
    offered in the Agent turn (before and after the placement) and the Reveal
    turn, one troop to the garrison, then face down and not offered again."""

    tile = "training_drones"
    turn = _turn(tile)
    for state in (turn, _placed(turn), _revealing(tiles=(tile,))):
        before = state.players[0]
        assert _flip(tile) in ENGINE.whole_actions(state, 0)
        flipped = apply_whole(ENGINE, state, _flip(tile)).state
        after = flipped.players[0]
        assert after.tech_flipped == (tile,)
        assert after.troops_garrison == before.troops_garrison + 1
        assert after.troops_supply == before.troops_supply - 1
        assert _flip_rows(flipped, tile) == []
    _flipped_back_at_round_start(tile)


def test_training_drones_owes_the_troop_the_supply_lacks() -> None:
    """The recruit is every recruit's: an empty supply owes the troop (OQ-030)
    and the tile still flips (it costs nothing)."""

    state = _turn("training_drones", supply=0)
    flipped = apply_whole(ENGINE, state, _flip("training_drones"))
    assert flipped.state.players[0].troops_garrison == state.players[0].troops_garrison
    assert flipped.state.players[0].ungained_troops == 1
    assert "troops_recruit_short" in [event.kind for event in flipped.events]


def test_flagship_pays_four_solari_for_three_troops() -> None:
    """Flagship -- "4 Solari -> troop 3" with the Flip icon (docs/rules/
    rise-of-ix.md 4): a paid line, offered with 4 Solari and a troop to take
    (OQ-071), in the Agent turn and the Reveal turn; it pays 4 Solari, recruits
    3 troops, flips, and is not offered again this round."""

    tile = "flagship"
    assert _flip_rows(_solari(_turn(tile), 3), tile) == []
    assert _flip_rows(_solari(_turn(tile, supply=0), 4), tile) == []
    turn = _solari(_turn(tile), 5)
    reveal = _solari(_revealing(tiles=(tile,)), 5)
    for state in (turn, _placed(turn), reveal):
        before = state.players[0]
        assert _flip(tile) in ENGINE.whole_actions(state, 0)
        flipped = apply_whole(ENGINE, state, _flip(tile))
        after = flipped.state.players[0]
        assert after.resources.solari == 1
        assert after.troops_garrison == before.troops_garrison + 3
        assert after.troops_supply == before.troops_supply - 3
        assert after.tech_flipped == (tile,)
        assert "resources_paid" in [event.kind for event in flipped.events]
        assert _flip_rows(flipped.state, tile) == []
    _flipped_back_at_round_start(tile)


def test_flagship_recruits_what_the_supply_has_and_owes_the_rest() -> None:
    state = _solari(_turn("flagship", supply=2), 4)
    after = apply_whole(ENGINE, state, _flip("flagship")).state.players[0]
    assert after.troops_garrison == state.players[0].troops_garrison + 2
    assert after.ungained_troops == 1


def test_holoprojectors_discards_a_hand_card_to_draw_one() -> None:
    """Holoprojectors -- "discard -> 카드 1장" with the Flip icon (docs/rules/
    rise-of-ix.md 4): one row for each card in hand (the cost is a hand
    card), in the Agent turn; the card goes to the discard pile, the deck's
    top card joins the hand, the tile is face down and not offered again, and
    it returns at Round Start. A Reveal turn has revealed the hand: no card
    is left to discard."""

    tile = "holoprojectors"
    turn = _turn(tile)
    hand = turn.players[0].hand
    top = turn.players[0].deck[0]
    assert {dict(row.arguments)["card_id"] for row in _flip_rows(turn, tile)} == set(
        hand
    )
    for state in (turn, _placed(turn)):
        owner = state.players[0]
        card = owner.hand[-1]
        flipped = apply_whole(ENGINE, state, _flip(tile, card)).state
        after = flipped.players[0]
        assert len(after.hand) == len(owner.hand)
        assert card not in after.hand
        assert card == after.discard_pile[-1]
        assert owner.deck[0] in after.hand
        assert after.tech_flipped == (tile,)
        assert _flip_rows(flipped, tile) == []
    assert top in apply_whole(ENGINE, turn, _flip(tile, hand[0])).state.players[0].hand
    assert _flip_rows(_revealing(tiles=(tile,)), tile) == []
    assert _flip_rows(_turn(tile, hand=()), tile) == []
    _flipped_back_at_round_start(tile)


def test_holoprojectors_draws_the_discarded_card_back_when_the_piles_are_empty() -> (
    None
):
    """With the deck empty the discard is shuffled for the draw, the card just
    paid included (a chance step, as every short draw)."""

    state = _turn("holoprojectors", deck=())
    owner = state.players[0]
    state = _seat(state, 0, discard_pile=())
    card = owner.hand[0]
    flipped = apply_whole(ENGINE, state, _flip("holoprojectors", card)).state
    decision = ENGINE.current_decision(flipped)
    assert isinstance(decision, ChanceDecision)
    assert decision.options == (card,)


def test_invasion_ships_lets_the_agent_go_where_an_opponent_stands_this_turn() -> None:
    """Invasion Ships -- "discard -> 이번 turn 상대 Agent가 내 Agent를 막지 않는다"
    with the Flip icon (docs/rules/rise-of-ix.md 4): the Infiltrate
    mechanism (``enemy_agents_ignored_turn``): after the flip the seat's Agent
    may go to a space an opponent's Agent occupies, and the placement spends
    it."""

    tile = "invasion_ships"
    occupied = {"agent_locations": ("imperial_basin",), "agents_available": 1}

    def spaces(state: GameState) -> set[object]:
        chosen = apply_whole(
            ENGINE,
            state,
            DomainAction("choose_agent_card", 0, (("card_id", DESERT_0),)),
        ).state
        return {
            dict(action.arguments)["space_id"]
            for action in ENGINE.whole_actions(chosen, 0)
            if action.action_id == "place_agent"
        }

    state = _seat(_turn(tile), 1, **occupied)
    assert spaces(state) == {"imperium_hagga_basin"}
    flipped = apply_whole(ENGINE, state, _flip(tile, DESERT_1)).state
    seat = flipped.players[0]
    assert seat.tech_flipped == (tile,)
    assert seat.enemy_agents_ignored_turn is True
    assert DESERT_1 in seat.discard_pile and DESERT_1 not in seat.hand
    assert spaces(flipped) == {"imperial_basin", "imperium_hagga_basin"}
    placed = apply_whole(
        ENGINE,
        apply_whole(
            ENGINE,
            flipped,
            DomainAction("choose_agent_card", 0, (("card_id", DESERT_0),)),
        ).state,
        DomainAction("place_agent", 0, (("space_id", "imperial_basin"),)),
    ).state
    assert placed.players[0].enemy_agents_ignored_turn is False
    assert _flip_rows(placed, tile) == []
    # This turn only: a turn that opens without the placement clears it.
    lapsed = reset_turn_counters(flipped.players, 1)
    assert lapsed[0].enemy_agents_ignored_turn is False
    _flipped_back_at_round_start(tile)


def test_invasion_ships_needs_a_hand_card_and_the_turn_before_the_agent() -> None:
    """The cost is a hand card, and the effect matters only before the turn's
    Agent is placed: it is not offered with an empty hand, after the placement
    or in a Reveal turn (which has revealed the hand)."""

    tile = "invasion_ships"
    turn = _turn(tile)
    assert len(_flip_rows(turn, tile)) == len(turn.players[0].hand)
    assert _flip_rows(_turn(tile, hand=()), tile) == []
    assert _flip_rows(_placed(turn), tile) == []
    assert _flip_rows(_revealing(tiles=(tile,)), tile) == []


def test_flip_tiles_are_once_a_round_and_never_without_rise_of_ix() -> None:
    """Nothing changes without Rise of Ix: no flip is offered in a game that
    cannot hold the tiles, and the catalogs without the expansion hold no
    Ix flip row while the one with it holds the four."""

    plain = replace(_turn(), config=ORIGINAL)
    assert legal_tech_flip_actions(plain, 0) == ()
    rows = tuple(
        ActionTemplate("flip", (("printed", tile), ("source", "tech")))
        for tile in ("flagship", "holoprojectors", "invasion_ships", "training_drones")
    )
    original = ActionCodec(ORIGINAL).catalog
    with_ix = ActionCodec(IX).catalog
    assert not set(rows) & set(original)
    assert set(rows) <= set(with_ix)


def test_the_flip_rows_run_through_the_engine_and_the_codec() -> None:
    """A flip drives through ``UprisingRulesEngine`` as its effect row and,
    for a discard cost, the card as the target row; every row it offers
    encodes and decodes to itself in the original game with Rise of Ix's
    catalog."""

    state = _solari(
        _turn("flagship", "holoprojectors", "invasion_ships", "training_drones"), 4
    )
    legal = ENGINE.legal_actions(state, 0)
    effect = DomainAction(
        "flip", 0, (("printed", "holoprojectors"), ("source", "tech"))
    )
    assert effect in legal
    assert {
        dict(action.arguments)["printed"]
        for action in legal
        if action.action_id == "flip"
    } == {"flagship", "holoprojectors", "invasion_ships", "training_drones"}
    after = ENGINE.apply(state, effect).state
    targets = [
        action
        for action in ENGINE.legal_actions(after, 0)
        if action.action_id == "choose_personal_card"
    ]
    assert len(targets) == 5
    _round_trips(state, 0)
    _round_trips(after, 0)
    done = ENGINE.apply(after, targets[0]).state
    assert done.players[0].tech_flipped == ("holoprojectors",)
    assert len(done.players[0].hand) == 5


# --- A tile acquired in the Reveal works in that Reveal (OQ-150 (2)) ---------


def _acquired_late(state: GameState, tile: str) -> RuleResult:
    """``tile`` joins the seat during its Reveal, as in the Restricted
    Ordnance test above, and the Reveal sweeps for what it now owes."""

    held = _seat(state, 0, tech_ids=(*state.players[0].tech_ids, tile))
    return grant_late_reveal_effects(RuleResult(state=held))


def _bought_in_the_reveal(tile: str, **reveal: Any) -> GameState:
    """Seat 0's Reveal turn buys ``tile`` with an Acquire Tech (9 spice)."""

    state = _revealing(**reveal)
    owner = state.players[0]
    state = replace(
        _seat(state, 0, resources=replace(owner.resources, spice=9)),
        tech_stacks=((tile,), (), ()),
    )
    state = push_tech_acquisition(
        state, 0, discount=0, source="s", printer=PRINTER
    ).state
    return apply_whole(
        ENGINE, state, DomainAction("acquire_tech", 0, (("tech_id", tile),))
    ).state


def test_minimic_film_acquired_in_the_reveal_gives_its_persuasion_then() -> None:
    """OQ-150 (2), user ruling 2026-10-29 "(가) 모두 듣기": a tile acquired in a
    Reveal applies its Reveal turn ability in that same Reveal.

    Minimic Film -- "Reveal turn: Persuasion 1" [Rise of Ix p. 4]:
    acquired after the Reveal began, the Persuasion arrives then (spendable
    and generated), once; held from the start it is paid once at the start."""

    started = _revealing()
    late = _acquired_late(started, "minimic_film")
    assert _context(late.state)["persuasion"] == _context(started)["persuasion"] + 1
    assert (
        _context(late.state)["persuasion_generated"]
        == _context(started)["persuasion_generated"] + 1
    )
    assert _context(late.state)["tech_granted"] == "minimic_film"
    assert [event.kind for event in late.events] == ["tech_reveal_bonus"]
    again = grant_late_reveal_effects(RuleResult(state=late.state))
    assert _context(again.state) == _context(late.state)
    assert not again.events

    held = _revealing(tiles=("minimic_film",))
    assert _context(held)["tech_granted"] == "minimic_film"
    assert (
        _context(grant_late_reveal_effects(RuleResult(state=held)).state)["persuasion"]
        == _context(held)["persuasion"]
    )

    bought = _bought_in_the_reveal("minimic_film")
    assert _context(bought)["persuasion"] == _context(started)["persuasion"] + 1


def test_a_late_minimic_film_counts_toward_the_generated_persuasion() -> None:
    """The late Persuasion is generated Persuasion: it lifts a turn from five to
    six, which opens Disposal Facility's rows (OQ-126)."""

    state = _revealing(
        tiles=("disposal_facility",),
        hand=(DAGGER_0, CONVINCING_0, CONVINCING_1, RECON),
    )
    assert _context(state)["persuasion_generated"] == 5
    assert _rows(state) == []
    late = _acquired_late(state, "minimic_film")
    assert _context(late.state)["persuasion_generated"] == 6
    assert len(_rows(late.state)) == 4


def test_artillery_acquired_in_the_reveal_counts_the_sword_cards_so_far() -> None:
    """OQ-150 (2), user ruling 2026-10-29 "(가) 모두 듣기": a tile acquired in a
    Reveal applies its Reveal turn ability in that same Reveal.

    Artillery -- "Reveal turn: sword를 주는 공개 카드마다 sword 1"
    [Rise of Ix p. 4]: bought after the Reveal began, it pays a sword for each
    card revealed so far that gives swords (two Daggers: two swords), once;
    OQ-150 (1)'s top-up stays: a sword card drawn later adds one more."""

    started = _revealing()
    late = _acquired_late(started, "artillery")
    assert _strength(late.state) == _strength(started) + 2
    assert _context(late.state)["artillery_counted"] == 2
    assert (
        _context(late.state)["sword_strength"]
        == _context(started)["sword_strength"] + 2
    )
    again = grant_late_reveal_effects(RuleResult(state=late.state))
    assert _strength(again.state) == _strength(late.state)

    bought = _bought_in_the_reveal("artillery")
    assert _strength(bought) == _strength(started) + 2
    assert _context(bought)["artillery_counted"] == 2

    topped = _acquired_late(
        _revealing(
            hand=(DAGGER_0, CONVINCING_0, RECON, DIPLOMACY), deck_top=(DAGGER_1,)
        ),
        "artillery",
    ).state
    assert _context(topped)["artillery_counted"] == 1
    drawn = draw_or_request_personal_cards(topped, 0, 1, source="late")
    assert _context(drawn.state)["artillery_counted"] == 2
    # The late Dagger's own sword and the Artillery sword it adds.
    assert _strength(drawn.state) == _strength(topped) + 2


def test_artillery_acquired_with_no_sword_card_pays_nothing_yet() -> None:
    state = _revealing(hand=(CONVINCING_0, RECON, DIPLOMACY))
    late = _acquired_late(state, "artillery")
    assert _strength(late.state) == _strength(state)
    assert not late.events


def test_disposal_facility_acquired_in_the_reveal_opens_its_trash_then() -> None:
    """OQ-150 (2), user ruling 2026-10-29 "(가) 모두 듣기": a tile acquired in a
    Reveal applies its Reveal turn ability in that same Reveal.

    Disposal Facility -- "Reveal turn: 그 turn에 얻은 Persuasion 합계(쓴 것
    포함)가 6 이상이면 in play 카드 하나를 trash할 수 있다" (OQ-126):
    bought after the Reveal began with six Persuasion generated, its trash row
    opens then; it never reopens after the trash is used."""

    started = _revealing(high_council=True)
    assert _context(started)["persuasion_generated"] == 6
    late = _acquired_late(started, "disposal_facility")
    assert len(_rows(late.state)) == 5
    assert _context(late.state)["tech_reveal_pending"] == "disposal_facility"
    assert _context(late.state)["tech_granted"] == "disposal_facility"

    bought = _bought_in_the_reveal("disposal_facility", high_council=True)
    assert len(_rows(bought)) == 5
    trash = DomainAction("trash_disposal_facility_card", 0, (("card_id", DAGGER_1),))
    used = apply_whole(ENGINE, bought, trash).state
    assert _rows(used) == []
    again = grant_late_reveal_effects(RuleResult(state=used))
    assert _rows(again.state) == []
    assert _context(again.state)["tech_reveal_pending"] == ""

    low = _acquired_late(_revealing(), "disposal_facility")
    assert _rows(low.state) == []
    assert _context(low.state)["tech_reveal_pending"] == "disposal_facility"


# --- Sonic Snoopers, Spy Satellites' trade and Spaceport (stage P4c-2c) ------

BYPASS = "intrigue:bypass_protocol:0"
TRASH_SNOOPERS = DomainAction(
    "trash", 0, (("printed", "sonic_snoopers"), ("source", "tech"))
)
TRASH_SATELLITES = DomainAction(
    "trash", 0, (("printed", "spy_satellites"), ("source", "tech"))
)
STOP_SNOOPERS = DomainAction(
    "finish", 0, (("printed", "sonic_snoopers"), ("source", "tech"))
)


def _holding(state: GameState, count: int, seat: int = 0) -> GameState:
    """``seat`` also holds the Intrigue deck's top ``count`` cards."""

    taken = state.intrigue_deck[:count]
    held = state.players[seat].intrigue_cards
    return _seat(
        replace(state, intrigue_deck=state.intrigue_deck[count:]),
        seat,
        intrigue_cards=(*held, *taken),
    )


def _put(card: str) -> DomainAction:
    return DomainAction("choose_intrigue_card", 0, (("card_id", card),))


def _snoopers(count: int, **seat: Any) -> GameState:
    """Seat 0's turn holding Sonic Snoopers and ``count`` Intrigue cards."""

    return _holding(_turn("sonic_snoopers", **seat), count)


def _stack(state: GameState, *actions: DomainAction) -> GameState:
    for action in actions:
        state = ENGINE.apply(state, action).state
    return state


def _trash_rows(state: GameState, seat: int = 0) -> list[DomainAction]:
    return [
        action
        for action in ENGINE.legal_actions(state, seat)
        if action.action_id == "trash"
    ]


def test_sonic_snoopers_is_offered_in_its_owners_turn_with_an_intrigue_card() -> None:
    """"때를 적지 않은 능력은 자기 turn 가운데 쓴다" [FAQ p. 4] (rise-of-ix.md
    4): the turn frame and the Agent-effect frame offer the trash; an opponent's
    turn, a hand with no Intrigue card to put (OQ-071: the trash would buy
    nothing) and a game without Rise of Ix do not."""

    state = _snoopers(1)
    assert _trash_rows(state) == [TRASH_SNOOPERS]
    assert _trash_rows(_placed(state)) == [TRASH_SNOOPERS]
    assert _trash_rows(state, 1) == []
    opponent = _holding(_seat(_turn(), 1, tech_ids=("sonic_snoopers",)), 1, seat=1)
    assert tech_rules.legal_tech_trash_actions(opponent, 1) == ()
    assert _trash_rows(_snoopers(0)) == []
    # A game without Rise of Ix cannot even hold the tile.
    plain = replace(_turn(), config=ORIGINAL)
    assert tech_rules.legal_tech_trash_actions(plain, 0) == ()


def test_sonic_snoopers_may_put_no_card_and_draws_none() -> None:
    """"Intrigue 몇 장이든 덱 맨 아래로, 그만큼 뽑기": any number, none too. The
    tile is trashed first, the cost."""

    state = _snoopers(2)
    hand, deck = state.players[0].intrigue_cards, state.intrigue_deck
    opened = ENGINE.apply(state, TRASH_SNOOPERS)
    assert opened.state.decision_stack[-1].kind == FrameKind.INTRIGUE_BOTTOM_PICK
    assert opened.state.players[0].tech_ids == ()
    assert opened.state.tech_trash == ("sonic_snoopers",)
    assert [event.kind for event in opened.events] == ["tech_trashed"]
    done = ENGINE.apply(opened.state, STOP_SNOOPERS).state
    assert done.decision_stack[-1].kind == FrameKind.TURN
    assert done.players[0].intrigue_cards == hand
    assert done.intrigue_deck == deck
    assert done.players[0].known_intrigue_ids == ()


def test_sonic_snoopers_puts_one_card_under_the_deck_and_draws_one() -> None:
    """One card goes to the bottom, one is drawn from the top. Its seat knows
    the card now at the bottom, nobody else does (rise-of-ix.md 13)."""

    state = _snoopers(2)
    first, second = state.players[0].intrigue_cards
    top = state.intrigue_deck[0]
    opened = _stack(state, TRASH_SNOOPERS)
    putting = ENGINE.apply(opened, _put(first))
    assert [event.kind for event in putting.events] == ["intrigue_put_on_bottom"]
    assert "card_id" not in dict(putting.events[0].payload)
    assert putting.state.intrigue_deck[-1] == first
    assert putting.state.players[0].intrigue_cards == (second,)
    done = _stack(putting.state, STOP_SNOOPERS)
    assert done.players[0].intrigue_cards == (second, top)
    assert done.intrigue_deck[-1] == first and top not in done.intrigue_deck
    assert known_intrigue_places(done, done.players[0])[1] == ((0, first),)
    assert done.players[0].known_intrigue_ids == (first,)
    assert all(not done.players[seat].known_intrigue_ids for seat in (1, 2, 3))
    assert known_card_seats(done)[first] == frozenset({0})
    check_observation_privacy(done)


def test_sonic_snoopers_keeps_the_order_it_was_put_in_and_draws_that_many() -> None:
    """Several cards, one at a time in the order chosen, each under the last;
    the seat knows each one's depth from the bottom and draws as many from the
    top."""

    state = _snoopers(3)
    first, second, third = state.players[0].intrigue_cards
    top = state.intrigue_deck[:3]
    opened = _stack(state, TRASH_SNOOPERS)
    putting = _stack(opened, _put(third), _put(first))
    assert putting.intrigue_deck[-2:] == (third, first)
    assert putting.decision_stack[-1].kind == FrameKind.INTRIGUE_BOTTOM_PICK
    putting = _stack(putting, _put(second))
    assert putting.players[0].intrigue_cards == ()
    # With no card left in the hand only the stop remains.
    assert [row.action_id for row in ENGINE.legal_actions(putting, 0)] == ["finish"]
    done = _stack(putting, STOP_SNOOPERS)
    assert done.intrigue_deck[-3:] == (third, first, second)
    assert done.players[0].intrigue_cards == top
    assert known_intrigue_places(done, done.players[0])[1] == (
        (0, second),
        (1, first),
        (2, third),
    )
    assert all(not done.players[seat].known_intrigue_ids for seat in (1, 2, 3))
    check_observation_privacy(putting)
    check_observation_privacy(done)


def test_the_other_seats_forget_the_cards_they_knew_in_its_hand() -> None:
    """The other seats cannot tell which cards went down: what they knew of
    this hand is lost, so a card they knew there that stays is still known."""

    state = _snoopers(2)
    first, second = state.players[0].intrigue_cards
    state = _seat(state, 1, known_intrigue_ids=(first, second))
    state = _seat(state, 2, known_intrigue_ids=(first,))
    opened = _stack(state, TRASH_SNOOPERS)
    assert known_card_seats(opened)[first] == frozenset({0, 1, 2})
    putting = _stack(opened, _put(first))
    assert putting.players[1].known_intrigue_ids == (second,)
    assert putting.players[2].known_intrigue_ids == ()
    assert known_card_seats(putting)[first] == frozenset({0})
    assert known_card_seats(putting)[second] == frozenset({0, 1})
    check_observation_privacy(putting)


def test_a_draw_that_reaches_the_cards_just_put_gives_them_back_known_to_none() -> None:
    """With no card left in the deck the draw takes the cards just put, in the
    order they went down; once in its own hand the seat's record of them is
    dropped (``settle_known_intrigue``)."""

    state = replace(_snoopers(2), intrigue_deck=())
    first, second = state.players[0].intrigue_cards
    putting = _stack(_stack(state, TRASH_SNOOPERS), _put(second), _put(first))
    assert putting.players[0].known_intrigue_ids == (second, first)
    done = _stack(putting, STOP_SNOOPERS)
    assert done.players[0].intrigue_cards == (second, first)
    assert done.intrigue_deck == ()
    assert done.players[0].known_intrigue_ids == ()


def test_sonic_snoopers_is_offered_in_a_reveal_turn_too() -> None:
    """The Reveal turn is one of its owner's turns."""

    state = _holding(_revealing(tiles=("sonic_snoopers",)), 1)
    assert _trash_rows(state) == [TRASH_SNOOPERS]
    opened = _stack(state, TRASH_SNOOPERS)
    done = _stack(opened, STOP_SNOOPERS)
    assert done.decision_stack[-1].kind == FrameKind.REVEAL


def _satellites(spice: int, **seat: Any) -> GameState:
    state = _turn("spy_satellites", **seat)
    return _seat(
        state, 0, resources=replace(state.players[0].resources, spice=spice)
    )


def test_spy_satellites_pays_three_spice_and_the_tile_for_a_victory_point() -> None:
    """"spice 3 + 이 타일 trash → 1 VP (자기 turn에)" (rise-of-ix.md 4)."""

    state = _satellites(4)
    owner = state.players[0]
    assert _trash_rows(state) == [TRASH_SATELLITES]
    result = ENGINE.apply(state, TRASH_SATELLITES)
    paid = result.state.players[0]
    assert paid.resources.spice == 1
    assert paid.victory_points == owner.victory_points + 1
    assert paid.tech_ids == () and result.state.tech_trash == ("spy_satellites",)
    # The spice left counts as spent in this turn (``spice_spent_turn``).
    assert paid.spice_spent_turn == owner.spice_spent_turn + 3
    assert [event.kind for event in result.events] == [
        "tech_trashed",
        "resources_paid",
        "resources_gained",
    ]
    assert dict(result.events[1].payload)["spice"] == 3
    assert dict(result.events[2].payload)["victory_points"] == 1
    assert result.state.decision_stack[-1].kind == FrameKind.TURN


def test_spy_satellites_needs_its_three_spice() -> None:
    """Without the 3 spice the trade is not offered, nor to a seat whose turn
    it is not; the Reveal turn is one of its owner's turns."""

    assert _trash_rows(_satellites(2)) == []
    state = _satellites(3)
    assert _trash_rows(state) == [TRASH_SATELLITES]
    assert _trash_rows(state, 1) == []
    reveal = _revealing(tiles=("spy_satellites",))
    owner = reveal.players[0]
    reveal = _seat(
        reveal, 0, resources=replace(owner.resources, spice=3)
    )
    assert _trash_rows(reveal) == [TRASH_SATELLITES]


def test_the_trash_rows_run_through_the_engine_and_the_codec() -> None:
    """Both tiles drive through ``UprisingRulesEngine`` as an effect row and,
    for Sonic Snoopers, the pick's target rows and its stop; every row
    encodes and decodes to itself in the original game with Rise of Ix's
    catalog, which alone holds them."""

    state = _holding(_turn("sonic_snoopers", "spy_satellites"), 2)
    state = _seat(
        state, 0, resources=replace(state.players[0].resources, spice=3)
    )
    assert _trash_rows(state) == [TRASH_SNOOPERS, TRASH_SATELLITES]
    opened = _stack(state, TRASH_SNOOPERS)
    first = state.players[0].intrigue_cards[0]
    assert [row.action_id for row in ENGINE.legal_actions(opened, 0)] == [
        "choose_intrigue_card",
        "choose_intrigue_card",
        "finish",
    ]
    putting = _stack(opened, _put(first))
    for seen in (state, opened, putting):
        _round_trips(seen, 0)
    rows = (
        ActionTemplate("trash", (("printed", "sonic_snoopers"), ("source", "tech"))),
        ActionTemplate("trash", (("printed", "spy_satellites"), ("source", "tech"))),
        ActionTemplate("finish", (("printed", "sonic_snoopers"), ("source", "tech"))),
    )
    assert not set(rows) & set(ActionCodec(ORIGINAL).catalog)
    assert set(rows) <= set(ActionCodec(IX).catalog)


def _reserve_rows(state: GameState) -> list[DomainAction]:
    return [
        row
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == "acquire_reserve"
        and dict(row.arguments)["card_id"] == "arrakis_liaison"
    ]


def test_spaceport_lets_its_owner_put_an_acquired_card_on_top_of_its_deck() -> None:
    """"얻는 카드를 덱 위에 놓을 수 있다" (rise-of-ix.md 4): every card its owner
    acquires has the deck-top twin beside the plain row, and a card put there
    is public until it is drawn (OQ-145, ``rules.deck_top``)."""

    without = _reserve_rows(_revealing())
    assert [dict(row.arguments).get("to_deck_top") for row in without] == [None]
    state = _revealing(tiles=("spaceport",))
    plain, twin = _reserve_rows(state)
    assert dict(twin.arguments)["to_deck_top"] is True and plain.arguments == (
        ("card_id", "arrakis_liaison"),
    )
    before = state.players[0]
    taken = apply_whole(ENGINE, state, twin).state
    owner = taken.players[0]
    card = owner.deck[0]
    assert card.startswith("reserve:arrakis_liaison:")
    assert owner.deck_public_top == (card,)
    assert owner.discard_pile == before.discard_pile
    assert card not in known_card_seats(taken)  # public: every seat knows it
    check_observation_privacy(taken)
    # Drawn outside a Reveal (a drawn card is revealed at once in one), it
    # stays public in the hand.
    turn = replace(taken, decision_stack=(turn_frame(1, 0),))
    drawn = settle_public_deck_tops(
        draw_or_request_personal_cards(turn, 0, 1, source="s").state
    )
    assert drawn.players[0].hand[-1] == card
    assert card in drawn.players[0].hand_public
    discarded = apply_whole(ENGINE, state, plain).state.players[0]
    assert card not in discarded.deck and discarded.deck_public_top == ()
    assert discarded.discard_pile[-1].startswith("reserve:arrakis_liaison:")


def test_spaceport_needs_no_open_reveal_and_the_tile() -> None:
    """The tile prints no round or turn: its choice stands outside the Reveal
    too, and only with the tile in a game with Rise of Ix."""

    state = _turn("spaceport")
    assert deck_top_offered(state, 0)
    assert not deck_top_offered(state, 1)
    assert not deck_top_offered(_turn(), 0)
    assert not deck_top_offered(_seat(state, 0, tech_ids=()), 0)


def test_bypass_protocol_and_spaceport_both_apply_without_doubling() -> None:
    """Bypass Protocol's second option puts its card on top by its own text, so
    Spaceport adds no row to it; the first option, which has no destination of
    its own, gains the deck-top twin. Either way a card is placed once."""

    state = _turn("spaceport", intrigue_cards=(BYPASS,), resources=Resources(spice=2))
    first = apply_whole(ENGINE, state, _bypass_play(0)).state
    rows = [
        row
        for row in ENGINE.whole_actions(first, 0)
        if row.action_id in ("acquire_intrigue_imperium", "acquire_intrigue_reserve")
    ]
    plain = [row for row in rows if "to_deck_top" not in dict(row.arguments)]
    twins = [row for row in rows if dict(row.arguments).get("to_deck_top")]
    assert plain and len(twins) == len(plain)
    second = apply_whole(ENGINE, state, _bypass_play(1)).state
    forced = [
        row
        for row in ENGINE.whole_actions(second, 0)
        if row.action_id in ("acquire_intrigue_imperium", "acquire_intrigue_reserve")
    ]
    assert forced and all(dict(row.arguments).get("to_deck_top") for row in forced)
    assert len(forced) == len(set(forced))
    taken = apply_whole(ENGINE, second, forced[0]).state.players[0]
    assert len(taken.deck_public_top) == 1 and taken.deck[0] == taken.deck_public_top[0]


def _bypass_play(option: int) -> DomainAction:
    return DomainAction("play_intrigue", 0, (("card_id", BYPASS), ("option", option)))


def test_the_deck_top_twins_are_the_original_games_rows_without_spaceport() -> None:
    """Nothing changes without Rise of Ix: a game without the tile offers the
    rows it always did, and the original game's catalog holds the twin rows
    Spaceport uses already (the catalogs gain no row for it)."""

    plain = replace(_revealing(), config=ORIGINAL)
    assert not any(
        dict(row.arguments).get("to_deck_top") for row in _reserve_rows(plain)
    )
    twin = ActionTemplate(
        "choose_reserve_card", (("card_id", "arrakis_liaison"), ("to_deck_top", True))
    )
    assert twin in set(ActionCodec(ORIGINAL).catalog)
    state = _revealing(tiles=("spaceport",))
    _round_trips(state, 0)
