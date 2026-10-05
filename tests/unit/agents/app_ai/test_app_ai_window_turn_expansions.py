"""The ``turn`` window on Immortality: graft placements and playmat keys.

Each test reaches the first TURN decision of an Immortality game, moves the
cards it needs into the deciding seat's hand and builds the ``DecisionRun``
the agent would build. The graft partner the window stores for the
``graft_partner`` window is checked against ``GraftCardEvaluator``
(``graft_card_evaluate``) over the engine's own legal partners for the
placed state.
"""

import random
from collections.abc import Sequence

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.immortality import graft_card_evaluate
from dune_imperium.agents.app_ai.catalog import card_entity, space_entity
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import turn
from dune_imperium.agents.app_ai.windows.common import Source, Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState

IMM = RulesetConfig(choam_module=False, immortality=True)


@pytest.fixture(autouse=True)
def no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the shared Plot sources (another window's)."""

    monkeypatch.setattr(turn, "intrigue_play_sources", lambda run, plays, combat: [])


def _turn_state(cards: Sequence[str]) -> tuple[GameState, int, list[str]]:
    """The first TURN decision with ``cards`` moved into the seat's hand."""

    state = first_decision("turn", config=IMM, seed=1)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    refs: list[str] = []
    for card in cards:
        state, ref = _take(state, seat, card)
        refs.append(ref)
    return state, seat, refs


def _take(state: GameState, seat: int, card: str) -> tuple[GameState, str]:
    me = state.players[seat]
    for zone in ("hand", "deck", "discard_pile"):
        for ref in getattr(me, zone):
            if f":{card}:" in ref:
                if zone == "hand":
                    return state, ref
                rest = tuple(r for r in getattr(me, zone) if r != ref)
                return with_player(
                    state, seat, **{zone: rest}, hand=(ref, *me.hand)
                ), ref
    for zone, prefix in (
        ("imperium_deck", "imperium"),
        ("tleilaxu_deck", "tleilaxu"),
        ("tleilaxu_row", "tleilaxu"),
    ):
        for ref in getattr(state, zone):
            if ref.startswith(f"{prefix}:{card}:"):
                rest = tuple(r for r in getattr(state, zone) if r != ref)
                state = with_state(state, **{zone: rest})
                hand = (ref, *state.players[seat].hand)
                return with_player(state, seat, hand=hand), ref
    raise KeyError(card)


def _run(state: GameState, seat: int, memory: Memory | None = None) -> DecisionRun:
    profile = make_profile(state, seat)
    legal = ENGINE.legal_actions(state, seat)
    return DecisionRun(
        profile.ctx, profile, legal, random.Random(0), memory or Memory()
    )


def _placements(run: DecisionRun, ref: str, *, graft: bool) -> list[DomainAction]:
    return [
        action
        for action in run.by_id("agent_turn")
        if arg(action, "card_id") == ref and (arg(action, "graft") is True) == graft
    ]


def _legal_partners(state: GameState, seat: int, placement: DomainAction) -> list[str]:
    placed = ENGINE.apply(
        state, placement, legal_actions=ENGINE.legal_actions(state, seat)
    ).state
    assert placed.decision_stack[-1].kind == "graft_partner"
    return [
        str(arg(action, "card_id"))
        for action in ENGINE.legal_actions(placed, seat)
        if action.action_id == "choose_graft_partner"
    ]


def _key(state: GameState, ref: str) -> tuple[object, ...]:
    return (turn.GRAFT_PARTNER_INTENT, state.round_number, ref)


def test_a_graft_card_is_grafted_with_graft_card_evaluators_partner() -> None:
    state, seat, (dagger, face_dancer) = _turn_state(("dagger", "face_dancer"))
    memory = Memory()
    run = _run(state, seat, memory)
    chosen = _placements(run, face_dancer, graft=True)[0]
    assert not _placements(run, face_dancer, graft=False)  # never alone
    realised = turn._realise(run, chosen)
    assert arg(realised, "graft") is True
    partners = _legal_partners(state, seat, realised)
    hand = set(state.players[seat].hand)
    answer = graft_card_evaluate(
        make_profile(state, seat),
        Request(
            infos=(
                TargetInfo(
                    entities=tuple(
                        card_entity(ref, seat if ref in hand else None)
                        for ref in partners
                    )
                ),
            )
        ),
        card_entity(face_dancer, seat),
        space_entity(str(arg(realised, "space_id")), run.ctx.board),
    )
    assert answer.value > 0 and answer.response is not None
    assert memory.intents[_key(state, face_dancer)] == answer.response[0][0]
    assert dagger in partners


def test_a_plain_card_is_played_alone_where_it_can_be() -> None:
    state, seat, (dagger, _face_dancer) = _turn_state(("dagger", "face_dancer"))
    memory = Memory()
    run = _run(state, seat, memory)
    grafted = _placements(run, dagger, graft=True)[0]
    assert _placements(run, dagger, graft=False)
    realised = turn._realise(run, grafted)
    assert arg(realised, "graft") is None
    assert arg(realised, "space_id") == arg(grafted, "space_id")
    assert _key(state, dagger) not in memory.intents


def test_a_forced_partner_with_no_positive_answer_is_a_random_legal_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # State 50 is forced for a Graft card; an evaluator answer worth nothing
    # leaves DefaultRandomChoice, which picks among the legal partners.
    state, seat, (_dagger, _coupling, face_dancer) = _turn_state(
        ("dagger", "planned_coupling", "face_dancer")
    )
    monkeypatch.setattr(
        turn, "graft_card_evaluate", lambda p, request, played, space: Answer(0.0, None)
    )
    memory = Memory()
    run = _run(state, seat, memory)
    for chosen in _placements(run, face_dancer, graft=True):
        if len(_legal_partners(state, seat, chosen)) > 1:
            break
    else:
        raise AssertionError("no placement with two legal partners")
    realised = turn._realise(run, chosen)
    assert arg(realised, "graft") is True
    partners = _legal_partners(state, seat, realised)
    assert len(partners) > 1
    assert memory.intents[_key(state, face_dancer)] in partners


def test_a_single_legal_partner_leaves_no_intent_behind() -> None:
    # Long Reach reaches a space only on its Bond partner's promise (Ghola),
    # its only legal partner: the agent answers that one-action decision
    # without the graft_partner window, which would never drop the entry
    # (regression: such entries piled up in Memory.intents).
    state, seat, (_ghola, long_reach) = _turn_state(("ghola", "long_reach"))
    memory = Memory()
    run = _run(state, seat, memory)
    assert not _placements(run, long_reach, graft=False)
    chosen = _placements(run, long_reach, graft=True)[0]
    realised = turn._realise(run, chosen)
    assert arg(realised, "graft") is True
    assert len(_legal_partners(state, seat, realised)) == 1
    assert _key(state, long_reach) not in memory.intents


def test_usurp_may_take_an_imperium_row_partner() -> None:
    state, seat, (usurp,) = _turn_state(("usurp",))
    memory = Memory()
    run = _run(state, seat, memory)
    for chosen in _placements(run, usurp, graft=True):
        partners = _legal_partners(state, seat, chosen)
        if any(ref in state.imperium_row for ref in partners):
            break
    else:
        raise AssertionError("no Usurp placement with a Row partner")
    realised = turn._realise(run, chosen)
    assert realised == chosen
    assert memory.intents[_key(state, usurp)] in partners


def test_return_specimen_is_a_key_only_for_a_troop_shortfall() -> None:
    state, seat, _refs = _turn_state(())
    me = state.players[seat]
    state = with_player(state, seat, specimens=1, troops_supply=me.troops_supply - 1)
    run = _run(state, seat)
    action = run.first("return_specimen")
    assert action is not None
    source = turn.return_specimen_source(run, action)
    assert source.stage is Stage.PROMPT and source.evaluate is not None
    assert source.evaluate() == (0.0, None)
    short = with_player(state, seat, ungained_troops=1)
    run = _run(short, seat)
    source = turn.return_specimen_source(run, action)
    assert source.evaluate is not None
    assert source.evaluate() == (1.0, action)


def test_family_atomics_is_never_used_at_the_turn_start() -> None:
    state, seat, _refs = _turn_state(())
    run = _run(state, seat)
    action = run.first("use_family_atomics")
    assert action is not None
    sources: list[Source] = turn.playmat_sources(run)
    (atomics,) = [s for s in sources if s.label == "Family Atomics"]
    assert atomics.evaluate is not None
    assert atomics.evaluate()[1] is None
    assert turn.turn_window(run) != action


def test_an_unknown_turn_action_falls_back_instead_of_being_passed_over() -> None:
    # Regression: a legal id with no app key (Bloodlines' play_turn_start_card,
    # tech actions) was simply never chosen, counted as a mirrored decision.
    state, seat, _refs = _turn_state(())
    run = _run(state, seat)
    assert turn.turn_window(run) is not None
    extra = DomainAction(action_id="play_turn_start_card", actor=seat)
    widened = DecisionRun(run.ctx, run.profile, (*run.legal, extra), run.rng, Memory())
    assert turn.turn_window(widened) is None


def test_tueks_sietch_joins_board_iteration_only_with_esmar_tuek() -> None:
    """Plan §11.8: Tuek's Sietch is a board space when Esmar Tuek plays,
    appended after the app's spaces; otherwise the board is the app's."""

    from dune_imperium import RulesetConfig
    from dune_imperium.agents.app_ai.catalog import board_space_ids
    from dune_imperium.agents.app_ai.context import AppContext, Board
    from dune_imperium.agents.app_ai.testing import ENGINE, play_until
    from dune_imperium.agents.app_ai.windows.turn import board_space_order

    def first_turn(leaders: tuple[str, ...]) -> GameState:
        from dataclasses import replace

        state = play_until(
            lambda st, owner: st.decision_stack[-1].kind == "turn",
            config=RulesetConfig(bloodlines=True),
        )
        players = tuple(
            replace(p, leader_id=leader)
            for p, leader in zip(state.players, leaders, strict=True)
        )
        return replace(state, players=players)

    with_esmar = first_turn(
        ("esmar_tuek", "muad_dib", "gurney_halleck", "lady_jessica")
    )
    without = first_turn(("muad_dib", "gurney_halleck", "lady_jessica", "staban_tuek"))
    board = AppContext(with_esmar, 0, ENGINE.observe(with_esmar, 0)).board
    plain = AppContext(without, 0, ENGINE.observe(without, 0)).board
    assert board.tueks_sietch and not plain.tueks_sietch
    assert board_space_order(board) == (*board_space_order(plain), "tuek_sietch")
    assert board_space_ids(board) == (*board_space_ids(plain), "tuek_sietch")
    assert "tuek_sietch" not in board_space_order(Board(True))
