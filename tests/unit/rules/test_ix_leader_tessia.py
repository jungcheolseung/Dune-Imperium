"""Tessia Vernius, a Rise of Ix Leader (stage P4e).

docs/rules/rise-of-ix.md 10: "Tessia Vernius (4) | Careful Observation: 시작에
Snooper token을 각 track의 Influence 2 칸에. 그 token에 도달할 때마다 Snooper track의 맨
위 덮이지 않은 보상을 받는다(① discard → spice 1, ② 그 track의 4칸 보너스, ③ 그 track에
Influence 1, ④ ②와 ③) | Duplicity: Influence 1 잃기 → Snooper token이 있는 진영에
Influence 1 | 디자이너 판정 9.3. "도달"은 Influence를 한꺼번에 얻으며 지나가도 도달
(Uprising과 같다). 한 효과가 여러 진영을 함께 올리면 소유자가 순서를 고르고(Quid Pro
Quo는 진영마다 줄, "Choose two:"는 고른 순서), Duplicity는 같은 진영을 잃고 얻어도
된다(OQ-153)"; 9.3: "Tessia: 버릴 카드가 없을 때 첫 Snooper를 얻어도 token은 가져가 맨
위 칸을 덮고, spice는 못 받음(BGG Forum) | 채택"; 7: a discard gives an Unload
card's box, paid before the arrow's reward when it is the cost. Played through
``UprisingRulesEngine`` in an original game with Rise of Ix, Tessia at seat 0;
every offered row round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    Resources,
    RuleResult,
)
from dune_imperium.rules import UprisingRulesEngine, turn_rows
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.setup import create_draft_initial_state
from dune_imperium.rules.snoopers import settle_snooper_discards
from dune_imperium.simulation.invariants import check_observation_privacy

TESSIA = "tessia_vernius"
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (TESSIA, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")
ALL = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
DELEGATE = "imperium:choam_delegate:0"
QUID_PRO_QUO = "intrigue:quid_pro_quo:0"
NONE = Resources(solari=0, spice=0, water=0)


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, including the intermediate card/space/effect
    choices consumed by apply_whole."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _start() -> tuple[_Engine, GameState]:
    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _rows(engine: _Engine, state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    engine.legal_actions(state, seat)
    return engine.whole_actions(state, seat)


def _do(engine: _Engine, state: GameState, action_id: str, **args: object) -> GameState:
    row = next(
        row
        for row in _rows(engine, state)
        if row.action_id == action_id
        and all(dict(row.arguments).get(key) == value for key, value in args.items())
    )
    result = apply_whole(engine, state, row).state
    engine.legal_actions(result, 0)
    return result


def _gain(state: GameState, faction: str, amount: int = 1) -> RuleResult:
    return gain_faction_influence(
        state, 0, Faction(faction), amount, event_prefix=f"test:{faction}"
    )


def _reached(events: tuple[GameEvent, ...]) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for event in events:
        if event.kind != "snooper_token_reached":
            continue
        payload = dict(event.payload)
        reward = payload["reward"]
        assert isinstance(reward, int)
        found.append((str(payload["faction"]), reward))
    return found


# --- Setup ----------------------------------------------------------------------


def test_tessia_starts_with_a_snooper_token_on_each_track() -> None:
    """ "시작에 Snooper token을 각 track의 Influence 2 칸에" (rise-of-ix.md 10);
    the tokens are public (13). Offered only with Rise of Ix, on both setup
    paths."""

    assert TESSIA in {leader.leader_id for leader in content_for(CONFIG).leaders}
    plain = RulesetConfig(base_game=BaseGame.IMPERIUM)
    assert TESSIA not in {leader.leader_id for leader in content_for(plain).leaders}
    _, state = _start()
    assert state.players[0].snooper_faction_ids == ALL
    assert all(not seat.snooper_faction_ids for seat in state.players[1:])
    draft = create_draft_initial_state(replace(CONFIG, leader_draft=True), 3).state
    assert all(not seat.snooper_faction_ids for seat in draft.players)


# --- Reaching the tokens ------------------------------------------------------


def test_the_tokens_reached_take_the_snooper_rewards_in_order() -> None:
    """Each token reached takes the topmost uncovered reward: ① first, then ②
    (the track's Influence 4 bonus: the Fremen's water [DI p. 7]), ③ (one
    Influence more there) and ④ (both: the Spacing Guild's 3 Solari and an
    Influence) -- whichever track is reached first."""

    _, state = _start()
    state = _seat(state, influence=Influence(1, 1, 1, 1), resources=NONE)
    first = _gain(state, "bene_gesserit")
    assert _reached(first.events) == [("bene_gesserit", 1)]
    assert first.state.players[0].snooper_faction_ids == (
        "emperor",
        "spacing_guild",
        "fremen",
    )
    second = _gain(first.state, "fremen")
    assert _reached(second.events) == [("fremen", 2)]
    assert second.state.players[0].resources.water == 1
    assert second.state.players[0].influence.fremen == 2
    third = _gain(second.state, "emperor")
    assert _reached(third.events) == [("emperor", 3)]
    assert third.state.players[0].influence.emperor == 3
    fourth = _gain(third.state, "spacing_guild")
    assert _reached(fourth.events) == [("spacing_guild", 4)]
    owner = fourth.state.players[0]
    assert owner.influence.spacing_guild == 3
    assert owner.resources.solari == 3
    assert owner.snooper_faction_ids == ()
    # No token left: reaching 2 again pays nothing more.
    assert _reached(_gain(fourth.state, "bene_gesserit").events) == []


def test_a_gain_that_passes_the_token_reaches_it() -> None:
    """ "도달"은 Influence를 한꺼번에 얻으며 지나가도 도달 (rise-of-ix.md 10): two
    Influence from 1 pass the token on 2; its ③ then raises the track once
    more, to its Influence 4 bonus and Alliance [DI p. 7]."""

    _, state = _start()
    state = _seat(
        state,
        influence=Influence(emperor=1, spacing_guild=0, bene_gesserit=1, fremen=0),
        snooper_faction_ids=("emperor", "spacing_guild"),
        resources=NONE,
    )
    passed = _gain(state, "emperor", 2)
    assert _reached(passed.events) == [("emperor", 3)]
    owner = passed.state.players[0]
    assert owner.influence.emperor == 4
    assert "emperor" in owner.alliance_faction_ids


# --- Reward ①: the discard ------------------------------------------------------


def _wealth(engine: _Engine, state: GameState) -> GameState:
    """Seat 0 sends Diplomacy to Wealth (an Emperor space: its Influence)."""

    card = "player:0:starter:diplomacy:0"
    owner = state.players[0]
    if card not in owner.hand:
        state = _seat(
            state,
            hand=(*owner.hand, card),
            deck=tuple(held for held in owner.deck if held != card),
        )
    engine.legal_actions(state, 0)
    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["space_id"] == "wealth"
        and dict(row.arguments)["card_id"] == card
    )
    placed = apply_placement(engine, state, placement).state
    engine.legal_actions(placed, 0)
    return placed


def _snooper_rows(engine: _Engine, state: GameState) -> set[str]:
    return {
        str(dict(row.arguments).get("card_id", ""))
        for row in _rows(engine, state)
        if row.action_id in ("discard_snooper_card", "decline_snooper_discard")
    }


def test_the_first_reward_in_her_turn_is_a_row_with_no_refusal() -> None:
    """① "discard → spice 1" reached in her own turn waits on it, a row per hand
    card; an arrow holds no turn end back, offers no refusal and lapses unused
    (OQ-095 (2)). The card is discarded from her hand [FAQ p. 2]."""

    engine, state = _start()
    state = _seat(state, influence=Influence(emperor=1), resources=NONE)
    placed = _wealth(engine, state)
    reached = _do(engine, placed, "resolve_faction_influence")
    assert reached.players[0].influence.emperor == 2
    hand = reached.players[0].hand
    assert hand
    assert _snooper_rows(engine, reached) == set(hand)
    assert not turn_rows.holds_the_end(reached, 0)
    card = hand[0]
    paid = _do(engine, reached, "discard_snooper_card", card_id=card)
    owner = paid.players[0]
    assert card in owner.discard_pile and card not in owner.hand
    assert owner.resources.spice == 1
    assert _snooper_rows(engine, paid) == set()


def _outside(state: GameState) -> GameState:
    """Seat 0's token ① reached in the Combat phase (no turn [Main p. 8])."""

    combat = replace(state, phase=GamePhase.COMBAT, decision_stack=())
    gained = _gain(combat, "emperor")
    assert _reached(gained.events) == [("emperor", 1)]
    return settle_snooper_discards(gained).state


def test_outside_her_turn_the_first_reward_opens_a_window_with_a_refusal() -> None:
    """Outside her turn the arrow is the ``OPTIONAL_DISCARD`` window: a hand
    card, or the refusal. Its rows round-trip through the codec, and the
    window shows no other seat her hand."""

    engine, state = _start()
    state = _seat(
        state, influence=Influence(emperor=1), resources=NONE, hand=(DELEGATE,)
    )
    window = _outside(state)
    assert window.decision_stack[-1].kind == FrameKind.OPTIONAL_DISCARD
    check_observation_privacy(window)
    rows = engine.legal_actions(window, 0)
    assert {row.action_id for row in rows} == {
        "discard_snooper_card",
        "decline_snooper_discard",
    }
    declined = engine.apply(window, DomainAction("decline_snooper_discard", 0))
    assert declined.state.players[0].resources.spice == 0
    assert DELEGATE in declined.state.players[0].hand


def test_an_unload_card_discarded_for_the_first_reward_pays_its_box_first() -> None:
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (designer ruling, rise-of-ix.md 7): CHOAM Delegate's 3
    Solari come in the discard's own step, before the spice."""

    engine, state = _start()
    state = _seat(
        state, influence=Influence(emperor=1), resources=NONE, hand=(DELEGATE,)
    )
    window = _outside(state)
    result = engine.apply(
        window, DomainAction("discard_snooper_card", 0, (("card_id", DELEGATE),))
    )
    owner = result.state.players[0]
    assert owner.resources.solari == 3 and owner.resources.spice == 1
    gains = [
        dict(event.payload)
        for event in result.events
        if event.kind == "resources_gained"
    ]
    assert [gain.get("solari", 0) for gain in gains] == [3, 0]
    assert not any(
        row.action_id == "resolve_unload_icon"
        for row in engine.legal_actions(result.state, 0)
    )


def test_with_no_card_the_first_token_still_covers_its_reward() -> None:
    """ "버릴 카드가 없을 때 첫 Snooper를 얻어도 token은 가져가 맨 위 칸을 덮고, spice는
    못 받음" (rise-of-ix.md 9.3): no window, no spice, and the next token
    reached takes ②."""

    _, state = _start()
    state = _seat(
        state, influence=Influence(emperor=1, fremen=1), resources=NONE, hand=()
    )
    settled = _outside(state)
    assert settled.decision_stack == ()
    assert settled.players[0].resources.spice == 0
    assert _reached(_gain(settled, "fremen").events) == [("fremen", 2)]


# --- One effect, several Factions (OQ-153) -------------------------------------


def test_quid_pro_quo_s_rows_let_her_choose_which_track_takes_which_reward() -> None:
    """OQ-153: Quid Pro Quo gives one row per Faction, taken in the owner's
    order, so the track she raises first takes the first uncovered reward."""

    rewards = {}
    for first, second in (("emperor", "bene_gesserit"), ("bene_gesserit", "emperor")):
        engine, state = _start()
        state = _seat(
            state,
            influence=Influence(emperor=1, bene_gesserit=1),
            resources=Resources(spice=2),
            intrigue_cards=(QUID_PRO_QUO,),
            agent_locations=("wealth", "secrets"),
            agents_available=0,
        )
        played = _do(engine, state, "play_intrigue", card_id=QUID_PRO_QUO, option=0)
        engine.legal_actions(played, 0)
        events: list[GameEvent] = []
        for faction in (first, second):
            row = next(
                row
                for row in engine.whole_actions(played, 0)
                if row.action_id == "resolve_effect_influence"
                and dict(row.arguments)["faction"] == faction
            )
            result = apply_whole(engine, played, row)
            events.extend(result.events)
            played = result.state
        rewards[first] = _reached(tuple(events))
    assert rewards["emperor"] == [("emperor", 1), ("bene_gesserit", 2)]
    assert rewards["bene_gesserit"] == [("bene_gesserit", 1), ("emperor", 2)]


# --- Duplicity -------------------------------------------------------------------


def _signet(engine: _Engine, state: GameState, **changes: object) -> GameState:
    """Seat 0 sends the Signet Ring to Arrakeen."""

    state = _seat(state, **changes)
    owner = state.players[0]
    if not any(":signet_ring:" in card for card in owner.hand):
        signet = next(card for card in owner.deck if ":signet_ring:" in card)
        state = _seat(
            state,
            hand=(*owner.hand, signet),
            deck=tuple(card for card in owner.deck if card != signet),
        )
    engine.legal_actions(state, 0)
    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["space_id"] == "arrakeen"
        and ":signet_ring:" in str(dict(row.arguments)["card_id"])
    )
    placed = apply_placement(engine, state, placement).state
    engine.legal_actions(placed, 0)
    return placed


def _factions(engine: _Engine, state: GameState, action_id: str) -> set[str]:
    return {
        str(dict(row.arguments)["faction"])
        for row in _rows(engine, state)
        if row.action_id == action_id
    }


def test_duplicity_loses_an_influence_for_one_with_a_snooper_faction() -> None:
    """ "Duplicity: Influence 1 잃기 → Snooper token이 있는 진영에 Influence 1"
    (rise-of-ix.md 10): the loss first (any Faction she has Influence with),
    then the gain is owed with a Faction still holding a token; a gain that
    reaches the token pays its Snooper reward."""

    engine, state = _start()
    placed = _signet(
        engine,
        state,
        influence=Influence(emperor=3, fremen=1),
        snooper_faction_ids=("spacing_guild", "fremen"),
        resources=NONE,
    )
    assert _factions(engine, placed, "lose_leader_influence") == {"emperor", "fremen"}
    lost = _do(engine, placed, "lose_leader_influence", faction="emperor")
    assert lost.players[0].influence.emperor == 2
    assert _factions(engine, lost, "lose_leader_influence") == set()
    assert _factions(engine, lost, "choose_leader_signet_influence") == {
        "spacing_guild",
        "fremen",
    }
    gained = apply_whole(
        engine,
        lost,
        next(
            row
            for row in _rows(engine, lost)
            if row.action_id == "choose_leader_signet_influence"
            and dict(row.arguments)["faction"] == "fremen"
        ),
    )
    # Two tokens already taken: the Fremen token's reward is ③, one more.
    assert _reached(gained.events) == [("fremen", 3)]
    assert gained.state.players[0].influence.fremen == 3


def test_duplicity_may_lose_and_regain_the_same_faction() -> None:
    """OQ-153: "Duplicity로 같은 진영을 잃고 얻기: 허용한다" -- the card says no "other
    Faction", as Finesse and Shifting Allegiances [FAQ p. 4]."""

    engine, state = _start()
    placed = _signet(
        engine,
        state,
        influence=Influence(fremen=1),
        snooper_faction_ids=("fremen",),
        resources=NONE,
    )
    lost = _do(engine, placed, "lose_leader_influence", faction="fremen")
    assert lost.players[0].influence.fremen == 0
    regained = _do(engine, lost, "choose_leader_signet_influence", faction="fremen")
    assert regained.players[0].influence.fremen == 1


def test_duplicity_without_a_token_left_offers_no_loss() -> None:
    """With every token taken the loss would buy nothing: "비용만 내고 보상을 받을
    수 없는 화살표 줄은 내지 않는다" (rise-of-ix.md 15, OQ-071)."""

    engine, state = _start()
    placed = _signet(
        engine,
        state,
        influence=Influence(emperor=3),
        snooper_faction_ids=(),
        resources=NONE,
    )
    assert _factions(engine, placed, "lose_leader_influence") == set()


def test_an_unused_first_reward_lapses_with_her_turn() -> None:
    """The arrow is optional: unused, the turn-end press lapses it with an
    event (OQ-095 (2)); every observation stays blind to her hand."""

    engine, state = _start()
    state = _seat(state, influence=Influence(emperor=1), resources=NONE)
    reached = _do(engine, _wealth(engine, state), "resolve_faction_influence")
    check_observation_privacy(reached)
    while not any(
        row.action_id == "finish_agent_turn" for row in _rows(engine, reached)
    ):
        effect = next(
            row
            for row in _rows(engine, reached)
            if row.action_id == "resolve_board_effect"
        )
        reached = _do(engine, reached, effect.action_id, **dict(effect.arguments))
    finish = next(
        row for row in _rows(engine, reached) if row.action_id == "finish_agent_turn"
    )
    ended = apply_whole(engine, reached, finish)
    assert "snooper_discard_lapsed" in [event.kind for event in ended.events]
    assert ended.state.players[0].resources.spice == 0
