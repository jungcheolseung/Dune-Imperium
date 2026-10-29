"""Rise of Ix's Strategic Push, through the original + Ix engine and ActionCodec.

The card [Steam app text and card table: Strength 2, Combat]: 2 swords and
"If you win this Conflict:" 2 Solari; the app logs "played Strategic Push to
gain 2 swords. If they win the Conflict they will gain 2 Solari" and "gained 2
Solari with Strategic Push for winning the Conflict". A Combat Intrigue played
before the Conflict is resolved: the swords are Combat strength at once, and
the Solari are pledged and paid only to the Conflict's sole winner.

Rules:

- docs/rules/open-questions.md OQ-121 ruling 6 (1), the winner's window:
  "**Strategic Push**의 "If you win this Conflict" 몫(Solari 2)은 고를 것 없는
  자동 줄이다", beside "보상 아이콘 줄", "**dreadnought 지배**는 의무 줄이다" and
  Windtraps; "공동 1위면 승리 효과 줄이 없다 `[FAQ p. 4]`. 의무 줄과 자동 줄을 다
  받아야 창이 닫힌다."
- docs/rules/rise-of-ix.md 12: "승자의 창 | 승자 | 보상 아이콘·지배·Windtraps·
  Strategic Push의 승리 몫·승리 책략 줄의 순서".
- open-questions.md OQ-142 (닿는 곳): the card is no winning Intrigue held in
  hand -- "이 카드는 Conflict 전에 내는 Combat 카드이고 승리 몫은 창의 자동 줄이다".

The states are built by hand as in ``test_ix_conflicts.py``: an original game
with Rise of Ix, moved into the Combat phase with the seats' units in the
Conflict, then run through the engine's Combat Intrigue rounds.
"""

import json
from dataclasses import replace
from typing import Any

import pytest
from tests.support.pauses import pause_outcome

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec, ActionTemplate
from dune_imperium.agents import HeuristicAgent
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.agents.app_ai.agent import AppAIAgent
from dune_imperium.agents.engine_order import engine_order_answer
from dune_imperium.agents.random_agent import RandomAgent
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.effect_dsl import (
    GainCombatStrength,
    PledgeConflictWinSolari,
)
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core import DomainAction, GamePhase, GameState
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.replay import ReplayStep, replay_game
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.display.actions import combat_reward_icon_action_text
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import (
    STRATEGIC_PUSH,
    _winning_intrigue_instances,
    add_late_windtraps_row,
    begin_combat_intrigue,
    legacy_combat_reward_icon,
)
from dune_imperium.rules.effect_interpreter import apply_rewards
from dune_imperium.rules.effect_steps import first_step, presents_steps
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.pauses import pause_is_pending
from dune_imperium.server.persistence import (
    build_save_document,
    parse_save_document,
)
from dune_imperium.simulation.invariants import (
    CardCensus,
    InvariantViolation,
    check_state_invariants,
)

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
ENGINE = UprisingRulesEngine()
CODEC = ActionCodec(CONFIG)
CARD = "intrigue:strategic_push:0"
WINDOW = FrameKind.COMBAT_REWARD_ICONS
# Windtraps (cost 2) on top of the first stack, as in ``test_ix_conflicts.py``.
STACKS = (
    ("windtraps", "artillery", "chaumurky"),
    ("detonation_devices", "holtzman_engine", "memocorders"),
    ("restricted_ordnance", "minimic_film", "flagship"),
)


# --- Building a Combat -------------------------------------------------------


def _seat(state: GameState, seat: int, **changes: Any) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def _combat(
    units: dict[int, tuple[int, int]],
    *,
    holder: int | None = 0,
    conflict_id: str = "skirmish_a",
    tiles: tuple[tuple[int, str], ...] = (),
    closing_row: bool = True,
) -> GameState:
    """The Combat Intrigue rounds of an original + Ix game, the First Player
    (seat 0) first: ``conflict_id`` revealed, ``units`` (seat -> troops,
    dreadnoughts; 2 strength a troop, 3 a dreadnought) in the Conflict, and
    ``holder`` holding Strategic Push (None: the card stays in the Intrigue
    deck). ``tiles`` gives seats a Tech tile;
    ``closing_row`` False takes the winning Intrigue cards (To the Victor...,
    Demand Respect) out of play, so the winner's window has no closing row."""

    state = ENGINE.reset(CONFIG, 3)
    winning = _winning_intrigue_instances() if not closing_row else frozenset()
    state = replace(
        state,
        tech_stacks=STACKS,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        intrigue_deck=tuple(
            c
            for c in state.intrigue_deck
            if c not in winning and (holder is None or c != CARD)
        ),
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        decision_stack=(),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=False,
        combat_rewards_resolved=False,
        combat_end_triggers_offered=False,
    )
    for seat, tech_id in tiles:
        stacks = tuple(
            tuple(tile for tile in stack if tile != tech_id)
            for stack in state.tech_stacks
        )
        held = (*state.players[seat].tech_ids, tech_id)
        state = _seat(replace(state, tech_stacks=stacks), seat, tech_ids=held)
    for seat, (troops, dreadnoughts) in units.items():
        owner = state.players[seat]
        state = _seat(
            state,
            seat,
            troops_garrison=owner.troops_garrison - troops,
            troops_conflict=troops,
            dreadnoughts_supply=owner.dreadnoughts_supply - dreadnoughts,
            dreadnoughts_conflict=dreadnoughts,
            combat_strength=2 * troops + 3 * dreadnoughts,
        )
    for player in state.players:
        held_cards = tuple(c for c in player.intrigue_cards if c not in winning)
        if player.player_id == holder:
            held_cards = (*held_cards, CARD)
        state = _seat(state, player.player_id, intrigue_cards=held_cards)
    return begin_combat_intrigue(state).state


def _play(state: GameState) -> GameState:
    """The holder of Strategic Push plays it at its first priority; every
    other answer is a pass, until the Combat Intrigue rounds end."""

    while state.decision_stack and state.decision_stack[-1].kind == (
        FrameKind.COMBAT_INTRIGUE
    ):
        owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        play = DomainAction("play_intrigue", owner, (("card_id", CARD), ("option", 0)))
        if play in ENGINE.whole_actions(state, owner):
            state = _do(state, play)
        else:
            state = _do(state, DomainAction("pass_combat_intrigue", owner))
    return state


def _fight(units: dict[int, tuple[int, int]], **options: Any) -> GameState:
    """``_combat`` with the card played, at the first reward window."""

    state = _play(_combat(units, **options))
    assert state.decision_stack[-1].kind == WINDOW
    return state


# --- Answering ---------------------------------------------------------------


def _do(state: GameState, action: DomainAction) -> GameState:
    """Apply a whole action the engine offers ``action.actor`` now; every
    legal row of the result encodes and decodes to itself."""

    offered = ENGINE.whole_actions(state, action.actor)
    assert action in offered, (action, offered)
    result = apply_whole(ENGINE, state, action).state
    for seat in range(CONFIG.players):
        for row in ENGINE.legal_actions(result, seat):
            assert CODEC.decode(CODEC.encode(row), seat) == row
    return result


def _icon(kind: str, actor: int = 0) -> DomainAction:
    return DomainAction("resolve_combat_reward_icon", actor, (("effect", kind),))


def _icons(state: GameState) -> list[str]:
    context = dict(state.decision_stack[-1].context)
    return [icon for icon in str(context["icons"]).split(",") if icon]


def _printed(state: GameState) -> list[str]:
    return str(dict(state.decision_stack[-1].context)["printed"]).split(",")


def _offered_icons(state: GameState, seat: int = 0) -> list[str]:
    return [
        str(dict(action.arguments)["effect"])
        for action in ENGINE.whole_actions(state, seat)
        if action.action_id == "resolve_combat_reward_icon"
    ]


def _settle(state: GameState) -> tuple[GameState, list[GameEvent]]:
    """Answer every pause and window the older engine's way until the Combat
    phase is over; the events on the way."""

    events: list[GameEvent] = []
    for _ in range(80):
        if state.phase is not GamePhase.COMBAT:
            return state, events
        if pause_is_pending(state):
            step = ENGINE.apply(state, pause_outcome(state))
        else:
            owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
            answer = engine_order_answer(
                state, owner, ENGINE.legal_actions(state, owner)
            )
            assert answer is not None, state.decision_stack[-1].kind
            step = ENGINE.apply(state, answer)
        state = step.state
        events.extend(step.events)
    raise AssertionError("the Combat did not end")


def _solari_gained(events: list[GameEvent], seat: int, suffix: str) -> int:
    """The Solari ``seat`` gained in ``events`` from sources ending in
    ``suffix`` (``resources_gained``)."""

    total = 0
    for event in events:
        payload = dict(event.payload)
        if (
            event.kind == "resources_gained"
            and payload["player"] == seat
            and str(payload["source"]).endswith(suffix)
        ):
            solari = payload.get("solari", 0)
            assert isinstance(solari, int)
            total += solari
    return total


# --- The card ----------------------------------------------------------------


def test_strategic_push_is_a_combat_card_of_the_ix_deck() -> None:
    """[COMBAT] 2 swords, "If you win this Conflict:" 2 Solari [Steam app text
    and card table]; one copy, shuffled in with Rise of Ix only [Rise of Ix
    p. 2]. It is no "When you win a Conflict" card held in hand (OQ-142: "이
    카드는 Conflict 전에 내는 Combat 카드이고 승리 몫은 창의 자동 줄이다")."""

    entry = intrigue_card_for_instance(CARD)
    assert entry.play_data_complete
    assert entry.copies == 1
    (option,) = entry.options
    assert option.timing.value == "combat"
    (section,) = option.sections
    assert section.costs == () and section.condition is None
    assert section.rewards == (GainCombatStrength(2), PledgeConflictWinSolari(2))
    assert CARD in content_for(CONFIG).intrigue_deck_instance_ids
    assert CARD not in content_for(ORIGINAL).intrigue_deck_instance_ids
    assert CARD not in _winning_intrigue_instances()
    assert intrigue_card_text(entry) == [
        "Combat — Gain 2 swords, If you win this Conflict: Gain 2 solari"
    ]
    assert intrigue_card_text_ko(entry) == [
        "전투 — {sword:2}, 이번 {conflict}에서 승리한다면: {solari:2}"
    ]


def test_the_card_adds_two_swords_and_pledges_two_solari() -> None:
    """The swords count at once, as every Combat Intrigue's [Main p. 14]; the
    Solari are only pledged (the app's "If they win the Conflict they will
    gain"), so nothing is gained yet, and the card is discarded."""

    state = _combat({0: (1, 0), 1: (2, 0)})
    before = state.players[0]
    played = _do(
        state, DomainAction("play_intrigue", 0, (("card_id", CARD), ("option", 0)))
    )
    owner = played.players[0]
    assert owner.combat_strength == before.combat_strength + 2
    assert owner.strategic_push_solari == 2
    assert owner.resources == before.resources
    assert CARD in played.intrigue_discard
    assert CARD not in owner.intrigue_cards
    assert all(seat.strategic_push_solari == 0 for seat in played.players[1:])


def test_two_copies_would_pledge_four() -> None:
    """One copy is printed, but each pledge adds its own Solari: two pieces
    pledge 4 on the same seat."""

    state = _combat({0: (1, 0)})
    pledge = PledgeConflictWinSolari(2)
    outcome = apply_rewards(state, 0, (pledge, pledge), source="test:pledge")
    owner = outcome.result.state.players[0]
    assert owner.strategic_push_solari == 4
    assert owner.resources == state.players[0].resources


# --- The winner's window -------------------------------------------------------


def test_the_sole_winner_gets_the_automatic_row_and_two_solari() -> None:
    """OQ-121 ruling 6 (1): Strategic Push's "If you win this Conflict" share
    (2 Solari) is "고를 것 없는 자동 줄" of the sole winner's window, and "의무
    줄과 자동 줄을 다 받아야 창이 닫힌다": the closing row waits until it is
    taken. Seat 0 wins with 2 troops and the 2 swords (6 against 4)."""

    state = _fight({0: (2, 0), 1: (2, 0)})
    context = dict(state.decision_stack[-1].context)
    assert (state.decision_stack[-1].decision.owner, context["rank"]) == (0, 1)  # type: ignore[union-attr]
    assert _icons(state) == ["victory_points", STRATEGIC_PUSH, "winning_intrigue"]
    assert _offered_icons(state) == ["victory_points", STRATEGIC_PUSH]

    paid = apply_whole(ENGINE, state, _icon(STRATEGIC_PUSH))
    after = paid.state
    assert after.players[0].resources.solari == state.players[0].resources.solari + 2
    assert after.players[0].strategic_push_solari == 0
    assert _solari_gained(list(paid.events), 0, ":strategic_push") == 2
    assert STRATEGIC_PUSH not in _icons(after)
    # The row is no choice: the window still waits for the reward icon, and
    # only then for its close.
    assert _offered_icons(after) == ["victory_points"]
    after = _do(after, _icon("victory_points"))
    assert _offered_icons(after) == ["winning_intrigue"]


def test_the_row_shows_the_pledge() -> None:
    """The row reads "Strategic Push: Gain 2 solari" (the card has no Korean
    edition, so its name stays English)."""

    state = _fight({0: (2, 0), 1: (2, 0)})
    assert combat_reward_icon_action_text(state, _icon(STRATEGIC_PUSH)) == (
        "Strategic Push: Gain 2 solari",
        "Strategic Push: {solari:2}",
    )


@pytest.mark.parametrize("first", ["strategic_push", "victory_points", "control"])
def test_the_winner_orders_the_row_among_the_windows_rows(first: str) -> None:
    """rise-of-ix.md 12: the winner orders "보상 아이콘·지배·Windtraps·Strategic
    Push의 승리 몫·승리 책략 줄". With a dreadnought in the Conflict and Windtraps
    held, the window holds the reward icon, Windtraps' water, the pledge and
    the dreadnought's mandatory Control row; each can be taken first, and
    every order pays the same."""

    state = _fight({0: (1, 1), 1: (2, 0)}, tiles=((0, "windtraps"),))
    rows = ["victory_points", "windtraps", STRATEGIC_PUSH, "dreadnought_control"]
    assert _printed(state) == [*rows, "winning_intrigue"]
    assert _offered_icons(state) == rows
    before = state.players[0]
    order = {
        "strategic_push": [STRATEGIC_PUSH, "dreadnought_control", "victory_points"],
        "victory_points": ["victory_points", STRATEGIC_PUSH, "dreadnought_control"],
        "control": ["dreadnought_control", "victory_points", STRATEGIC_PUSH],
    }[first]
    for kind in (*order, "windtraps"):
        state = _do(state, _icon(kind))
        if kind == "dreadnought_control":
            (place, *_rest) = [
                action
                for action in ENGINE.whole_actions(state, 0)
                if action.action_id == "place_combat_reward_dreadnought"
            ]
            state = _do(state, place)
    assert _offered_icons(state) == ["winning_intrigue"]
    owner = state.players[0]
    assert owner.resources.solari == before.resources.solari + 2
    assert owner.resources.water == before.resources.water + 1
    assert owner.victory_points == before.victory_points + 1
    assert owner.strategic_push_solari == 0
    assert len(state.dreadnought_control) == 1


def test_a_late_windtraps_row_keeps_the_windows_order() -> None:
    """A Windtraps taken inside the winner's own window gets this win's water
    too (rise-of-ix.md 12); its row goes where ``_reward_window`` lays it,
    before the pledge's."""

    state = _fight({0: (2, 0), 1: (2, 0)})
    state = replace(
        state,
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile != "windtraps")
            for stack in state.tech_stacks
        ),
    )
    late = add_late_windtraps_row(_seat(state, 0, tech_ids=("windtraps",)), 0)
    assert _icons(late) == [
        "victory_points",
        "windtraps",
        STRATEGIC_PUSH,
        "winning_intrigue",
    ]


def test_a_tie_for_first_gives_nothing_and_the_pledge_lapses() -> None:
    """ "공동 1위면 승리 효과 줄이 없다 `[FAQ p. 4]`" (OQ-121 ruling 6 (1)): seat 0
    ties seat 1 at 4 (one troop and the 2 swords against two troops); both take
    the second place's reward, no window holds the row, and the pledge lapses
    when the Combat is cleaned up."""

    state = _fight({0: (1, 0), 1: (2, 0), 2: (1, 0)})
    assert dict(state.decision_stack[-1].context)["rank"] == 2
    assert STRATEGIC_PUSH not in _icons(state)
    before = state.players[0].resources.solari
    seen: list[list[str]] = []
    while state.phase is GamePhase.COMBAT and state.decision_stack:
        if state.decision_stack[-1].kind == WINDOW:
            seen.append(_icons(state))
        if pause_is_pending(state):
            state = ENGINE.apply(state, pause_outcome(state)).state
            continue
        owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        answer = engine_order_answer(state, owner, ENGINE.legal_actions(state, owner))
        assert answer is not None
        state = ENGINE.apply(state, answer).state
    assert seen and all(STRATEGIC_PUSH not in icons for icons in seen)
    assert state.phase is not GamePhase.COMBAT
    assert state.players[0].resources.solari == before
    assert all(seat.strategic_push_solari == 0 for seat in state.players)


def test_a_losers_pledge_lapses_and_does_not_reach_the_next_conflict() -> None:
    """Seat 1 plays the card and still loses (4 against seat 0's 6): its
    second-place window has no row, and the pledge is gone once the Combat is
    cleaned up, so no later Conflict pays it."""

    state = _fight({0: (3, 0), 1: (1, 0)}, holder=1)
    assert state.players[1].strategic_push_solari == 2
    assert STRATEGIC_PUSH not in _icons(state)
    settled, events = _settle(state)
    windows = [
        dict(event.payload)
        for event in events
        if event.kind == "combat_reward_icon_resolved"
    ]
    assert all(window["effect"] != STRATEGIC_PUSH for window in windows)
    assert _solari_gained(events, 1, ":strategic_push") == 0
    assert all(seat.strategic_push_solari == 0 for seat in settled.players)
    check_state_invariants(settled, CardCensus.from_state(settled))

    # The next Conflict, seat 1 the sole winner without the card: no row.
    later = _seat(
        _combat({0: (1, 0), 1: (3, 0)}, holder=None),
        1,
        strategic_push_solari=settled.players[1].strategic_push_solari,
    )
    later = _play(later)
    assert later.decision_stack[-1].decision.owner == 1  # type: ignore[union-attr]
    assert STRATEGIC_PUSH not in _icons(later)


def test_two_pledges_pay_only_the_sole_winner() -> None:
    """Seat 0 plays the card and seat 2 holds a pledge as a second copy would
    give it: seat 0 wins and is paid its own 2 Solari; seat 2's window (second
    place) has no row and its pledge lapses at the clean-up."""

    state = _combat({0: (2, 0), 1: (1, 0), 2: (2, 0)}, closing_row=False)
    state = _seat(state, 2, strategic_push_solari=2)
    state = _play(state)
    assert [seat.strategic_push_solari for seat in state.players] == [2, 0, 2, 0]
    assert _icons(state) == ["victory_points", STRATEGIC_PUSH]
    settled, events = _settle(state)
    assert _solari_gained(events, 0, ":strategic_push") == 2
    assert _solari_gained(events, 2, ":strategic_push") == 0
    assert all(seat.strategic_push_solari == 0 for seat in settled.players)


def test_no_pledge_outlives_the_combat_phase() -> None:
    """The sweep's invariants: a pledge only lives in a Rise of Ix game's
    Combat phase."""

    state = _combat({0: (1, 0)})
    census = CardCensus.from_state(state)
    check_state_invariants(_seat(state, 0, strategic_push_solari=2), census)
    with pytest.raises(InvariantViolation, match="outside the Combat phase"):
        check_state_invariants(
            replace(_seat(state, 0, strategic_push_solari=2), phase=GamePhase.MAKERS),
            census,
        )
    original = ENGINE.reset(ORIGINAL, 3)
    with pytest.raises(InvariantViolation, match="outside a Rise of Ix game"):
        check_state_invariants(
            _seat(original, 1, strategic_push_solari=2),
            CardCensus.from_state(original),
        )


# --- The codec and the scripted seats -------------------------------------------


def test_the_row_round_trips_through_the_codec_of_rise_of_ix_only() -> None:
    """The window offers the row as a step row (its effect, printed by the
    Conflict card, as Windtraps' row), which the original + Ix catalog holds
    for every Conflict of its pool; no catalog without Rise of Ix holds it."""

    state = _fight({0: (2, 0), 1: (2, 0)})
    rows = ENGINE.legal_actions(state, 0)
    row = DomainAction(
        "gain",
        0,
        (("icon", STRATEGIC_PUSH), ("printed", "skirmish_a"), ("source", "conflict")),
    )
    assert row in rows
    for action in rows:
        assert CODEC.decode(CODEC.encode(action), 0) == action
    for conflict in content_for(CONFIG).conflicts_in_play():
        assert (
            ActionTemplate(
                "gain",
                (
                    ("icon", STRATEGIC_PUSH),
                    ("printed", conflict.card.card_id),
                    ("source", "conflict"),
                ),
            )
            in CODEC.catalog
        ), conflict.card.card_id
    paid = ENGINE.apply(state, row).state
    assert paid.players[0].resources.solari == state.players[0].resources.solari + 2
    for config in (
        ORIGINAL,
        RulesetConfig(),
        RulesetConfig(bloodlines=True, tech_module=True, immortality=True),
    ):
        assert not any(
            ("icon", STRATEGIC_PUSH) in template.arguments
            or ("effect", STRATEGIC_PUSH) in template.arguments
            for template in ActionCodec(config).catalog
        ), config.identifier


def test_the_ai_seats_fixed_order_takes_the_row() -> None:
    """The heuristic, app AI and rollout seats answer a reward window in the
    older engine's fixed order (``agents.engine_order``): the window's icons
    as laid, so the reward icon, then the pledge, then the close."""

    state = _fight({0: (2, 0), 1: (2, 0)})
    assert legacy_combat_reward_icon(state, 0) == _icon("victory_points")
    state = _do(state, _icon("victory_points"))
    assert legacy_combat_reward_icon(state, 0) == _icon(STRATEGIC_PUSH)
    answer = engine_order_answer(state, 0, ENGINE.legal_actions(state, 0))
    assert answer is not None
    assert dict(answer.arguments)["icon"] == STRATEGIC_PUSH
    before = state.players[0].resources.solari
    state = ENGINE.apply(state, answer).state
    assert state.players[0].resources.solari == before + 2
    assert legacy_combat_reward_icon(state, 0) == _icon("winning_intrigue")


def test_the_scripted_seats_end_the_combat_with_the_pledge_paid() -> None:
    """The random, heuristic and app AI seats answer the window with legal
    rows only, and the Combat ends with the winner paid."""

    for agent in (RandomAgent(seed=1), HeuristicAgent(seed=1), AppAIAgent(seed=1)):
        state = _fight({0: (2, 0), 1: (2, 0)})
        before = state.players[0].resources.solari
        for _ in range(60):
            if state.phase is not GamePhase.COMBAT:
                break
            if pause_is_pending(state):
                state = ENGINE.apply(state, pause_outcome(state)).state
                continue
            owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
            legal = ENGINE.legal_actions(state, owner)
            view = ENGINE.observe(state, owner)
            if isinstance(agent, RandomAgent):
                action = agent.choose_action(view, legal)
            else:
                action = agent.choose_action_with_state(state, view, legal)
            assert action in legal
            state = ENGINE.apply(state, action).state
        else:
            raise AssertionError(f"{type(agent).__name__} did not end the Combat")
        assert state.players[0].resources.solari == before + 2, type(agent).__name__
        assert all(seat.strategic_push_solari == 0 for seat in state.players)


# --- Saves --------------------------------------------------------------------


def _game_to_a_pledge() -> tuple[int, tuple[ReplayStep, ...], GameState]:
    """A seeded original + Ix game of random seats, Strategic Push played by
    whoever can at the first chance, run until a seat holds the pledge: the
    seed, the recorded steps and the state. Seeds with the card near the top
    of the Intrigue deck are tried in turn."""

    for seed in range(1, 400):
        state = ENGINE.reset(CONFIG, seed)
        if state.intrigue_deck.index(CARD) > 3:
            continue
        agents = [RandomAgent(seed=seed * 10 + seat) for seat in range(4)]
        chance = ChanceResolver(seed=seed)
        steps: list[ReplayStep] = []
        while state.phase is not GamePhase.FINISHED and len(steps) < 3000:
            if any(seat.strategic_push_solari for seat in state.players):
                return seed, tuple(steps), state
            decision = ENGINE.current_decision(state)
            if isinstance(decision, ChanceDecision):
                outcome = chance.resolve(decision)
                steps.append(outcome)
                state = ENGINE.apply(state, outcome).state
                continue
            owner = decision.owner  # type: ignore[union-attr]
            rows = ENGINE.legal_actions(state, owner)
            play = DomainAction(
                "play_intrigue", owner, (("card_id", CARD), ("option", 0))
            )
            action: DomainAction | None = None
            if play in ENGINE.whole_actions(state, owner):
                step = first_step(state, play) if presents_steps(state) else play
                action = step if step in rows else None
            if action is None:
                action = agents[owner].choose_action(ENGINE.observe(state, owner), rows)
            steps.append(action)
            state = ENGINE.apply(state, action).state
    raise AssertionError("no seeded game reached a Strategic Push pledge")


def test_a_save_keeps_the_pledge_and_an_undo_takes_it_back() -> None:
    """A save is the game's steps and its state hash; the pledge is part of
    the state, so a saved and loaded game replays to it (its hash checked),
    and replaying the steps before the play -- an undo -- has none."""

    seed, steps, state = _game_to_a_pledge()
    (holder,) = [seat for seat in state.players if seat.strategic_push_solari]
    assert holder.strategic_push_solari == 2
    assert state.phase is GamePhase.COMBAT
    document = build_save_document(
        config=CONFIG,
        game_seed=seed,
        policy_seed=0,
        seats=("random",) * 4,
        steps=steps,
        expected_state_hash=canonical_state_hash(state),
        source_game_id="strategic-push",
        round_number=state.round_number,
        phase=state.phase.value,
        finished=False,
        log=(),
    )
    parsed = parse_save_document(json.loads(json.dumps(document)))
    loaded = replay_game(ENGINE, parsed.replay)
    assert loaded == state
    assert loaded.players[holder.player_id].strategic_push_solari == 2

    undone = ENGINE.reset(CONFIG, seed)
    for step in steps[:-1]:
        undone = ENGINE.apply(undone, step).state
    assert all(seat.strategic_push_solari == 0 for seat in undone.players)
    assert canonical_state_hash(undone) != canonical_state_hash(state)
