"""A Signet Ring grafted to Ghola offers every Leader's Signet rows in box 1.

"어느 카드의 Agent 아이콘으로든 Agent를 보낼 수 있다. 어느 아이콘을 썼든 두
카드 모두 Agent를 \"보낸\" 것으로 취급한다" [Immortality p. 10]
(docs/rules/immortality.md 5): Ghola copies the Signet Ring's Agent box, and
the Signet Ring's box is its Leader's Signet ability. A grafted turn offers
box 1's rows tagged ``box=1`` from the start (codec v143); a Leader row with no
``box=1`` template stopped the turn with a RuntimeError once Immortality met
the original game's and Rise of Ix's Leaders (stage P7, found by the P6 app AI
soaks: Helena Richese, Tessia Vernius, Prince Rhombur Vernius, Viscount
Hundro Moritani).
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec, action_codec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.effect_steps import STEP_SPECS, Printed
from dune_imperium.rules.frames import FrameKind, owned_top_frame
from dune_imperium.rules.graft_boxes import BOX_ACTION_IDS, row_box

GHOLA = "tleilaxu:ghola:0"
UPRISING = RulesetConfig(
    imperium_cards=True, immortality=True, first_player_seat_zero=True
)
ORIGINAL = RulesetConfig(
    base_game=BaseGame.IMPERIUM, immortality=True, first_player_seat_zero=True
)
ORIGINAL_IX = replace(ORIGINAL, rise_of_ix=True)
UPRISING_OTHERS = ("muad_dib", "gurney_halleck", "lady_jessica")
ORIGINAL_OTHERS = ("glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")

# The Leader rows no Agent box offers, so they need no ``box=1`` twin: a
# board visit's or a turn's row, Round Start, Reveal or a Leader ability
# outside the Signet Ring.
_NOT_BOX_ROWS = frozenset(
    {
        # The original game's Connections: the High Council visit's row.
        "choose_connections_influence",
        # Feyd-Rautha's Spy recall outside his Signet.
        "recall_spy_for_leader",
        # Lady Amber Metulli's retreats (Bloodlines), outside her Signet.
        "retreat_leader_troop",
        "retreat_leader_commander",
        # Rise of Ix's One Step Ahead (Round Start) and Coordination (Reveal).
        "set_aside_leader_card",
        "trash_leader_reveal_card",
        # Lady Jessica's Other Memory, Liet Kynes's Planetologist, Reverend
        # Mother Jessica's board repeat.
        "use_other_memories",
        "draw_planetologist_intrigue",
        "pay_leader_board_repeat",
    }
)


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


def test_every_leader_row_is_a_box_row_or_named_outside_the_boxes() -> None:
    # A new Leader row must say which: the effect frame refuses a box 1 row
    # outside BOX_ACTION_IDS at play time, so classify it here first. The
    # rows are read from the engine's step definitions (every whole action
    # whose printed entity is the Leader, ``effect_steps.STEP_SPECS``) and
    # from the codec's table of Leader rows, so a row missing from one of
    # them is still asked (Codex review, 2026-10-30).
    printed = {
        action_id
        for action_id, spec in STEP_SPECS.items()
        if spec.printed == Printed.LEADER
    }
    rows = printed | set(action_codec._LEADER_ROW_FACES)
    assert _NOT_BOX_ROWS <= rows
    assert not _NOT_BOX_ROWS & BOX_ACTION_IDS
    assert rows - _NOT_BOX_ROWS <= BOX_ACTION_IDS


# Every Leader a game with Immortality can seat: Uprising's, Bloodlines' and
# the original game's on the Uprising board, Rise of Ix's on the original.
_EVERY_UPRISING_LEADER = RulesetConfig(
    imperium_cards=True,
    immortality=True,
    bloodlines=True,
    tech_module=True,
    choam_module=True,
    promo_cards=True,
    first_player_seat_zero=True,
)
_EVERY_IX_LEADER = replace(ORIGINAL_IX, promo_cards=True)
# Steersman Y'rkoon's Plot Course prints no Signet Ring ability, and his
# starting deck has no Signet Ring (``leader_abilities``, Servo-Receivers).
_NO_SIGNET_RING = frozenset({"steersman_y_rkoon"})
_LEADER_GAMES = tuple(
    (config, leader.leader_id, others)
    for config in (_EVERY_UPRISING_LEADER, _EVERY_IX_LEADER)
    for leader in content_for(config).leaders
    if leader.leader_id not in _NO_SIGNET_RING
    for others in (
        tuple(
            other.leader_id
            for other in content_for(config).leaders
            if other.leader_id != leader.leader_id
        )[:3],
    )
)


@pytest.mark.parametrize(
    ("config", "leader", "others"),
    _LEADER_GAMES,
    ids=[f"{config.base_game.value}-{leader}" for config, leader, _ in _LEADER_GAMES],
)
def test_every_leader_s_grafted_signet_offers_coded_rows(
    config: RulesetConfig, leader: str, others: tuple[str, str, str]
) -> None:
    # The providers themselves: every Leader's Signet Ring grafted with
    # Ghola, its offered rows and those after each box 1 row, are legal and
    # coded -- a box 1 row outside BOX_ACTION_IDS raises at play time.
    engine, state = _grafted_signet(leader, config, others)
    codec = _codec(config)
    for row in engine.legal_actions(state, 0):
        assert codec.decode(codec.encode(row), 0) == row
    for row in engine.whole_actions(state, 0):
        if row_box(row) != 1:
            continue
        after = apply_whole(engine, state, row).state
        decision = engine.current_decision(after)
        if isinstance(decision, PlayerDecision):
            for step in engine.legal_actions(after, decision.owner):
                assert codec.decode(codec.encode(step), decision.owner) == step


def _grafted_signet(
    leader: str, config: RulesetConfig, others: tuple[str, str, str]
) -> tuple[UprisingRulesEngine, GameState]:
    """``leader`` at seat 0 sends the Signet Ring grafted with Ghola."""

    engine = UprisingRulesEngine(leader_ids=(leader, *others))
    state = engine.reset(config, 3)
    chance = ChanceResolver(seed=3)
    while (
        state.phase is not GamePhase.PLAYER_TURNS
        or owned_top_frame(state, FrameKind.TURN, 0) is None
    ):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
        else:
            # A setup or Round Start choice (Hundro's Intelligence, Ilesa's
            # set-aside, Steersman's Navigation): take the first offer.
            assert isinstance(decision, PlayerDecision)
            state = apply_whole(
                engine, state, engine.whole_actions(state, decision.owner)[0]
            ).state
    owner = state.players[0]
    assert owner.leader_id == leader
    signet = next(
        card for card in (*owner.hand, *owner.deck) if ":signet_ring:" in card
    )
    players = list(state.players)
    players[0] = replace(
        owner,
        hand=(*(c for c in owner.hand if c != signet), signet, GHOLA),
        deck=tuple(c for c in owner.deck if c != signet),
        resources=Resources(solari=10, spice=10, water=5),
        influence=Influence(emperor=2, spacing_guild=2, bene_gesserit=2, fremen=2),
    )
    state = replace(
        state,
        players=tuple(players),
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c != GHOLA),
        tleilaxu_row=tuple(c for c in state.tleilaxu_row if c != GHOLA),
    )
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == signet
        and dict(placement.arguments).get("graft") is True
    )
    placed = apply_placement(engine, state, placement).state
    choice = next(
        row
        for row in engine.whole_actions(placed, 0)
        if row.action_id == "choose_graft_partner"
        and dict(row.arguments)["card_id"] == GHOLA
    )
    return engine, apply_whole(engine, placed, choice).state


@pytest.mark.parametrize(
    ("leader", "config", "others", "action_id"),
    [
        ("helena_richese", UPRISING, UPRISING_OTHERS, "set_aside_leader_imperium"),
        ("helena_richese", ORIGINAL, ORIGINAL_OTHERS, "set_aside_leader_imperium"),
        ("tessia_vernius", ORIGINAL_IX, ORIGINAL_OTHERS, "lose_leader_influence"),
        ("prince_rhombur_vernius", ORIGINAL_IX, ORIGINAL_OTHERS, "acquire_leader_tech"),
        (
            "prince_rhombur_vernius",
            ORIGINAL_IX,
            ORIGINAL_OTHERS,
            "place_leader_negotiator",
        ),
        (
            "viscount_hundro_moritani",
            ORIGINAL_IX,
            ORIGINAL_OTHERS,
            "advance_leader_freighter",
        ),
    ],
)
def test_ghola_offers_the_signet_rows_in_box_one(
    leader: str,
    config: RulesetConfig,
    others: tuple[str, str, str],
    action_id: str,
) -> None:
    engine, state = _grafted_signet(leader, config, others)
    rows = engine.legal_actions(state, 0)
    codec = _codec(config)
    for row in rows:
        assert codec.decode(codec.encode(row), 0) == row
    offered = {(row.action_id, row_box(row)) for row in engine.whole_actions(state, 0)}
    assert (action_id, 0) in offered
    assert (action_id, 1) in offered
