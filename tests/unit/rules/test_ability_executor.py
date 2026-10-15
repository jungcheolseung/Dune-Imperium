"""The pending-ability executor (docs/composed-effects-plan.md 4.2-4.3, stage A0).

Stage A0 builds the executor without wiring it into the engine, so these
tests hold it to the engine's own behaviour on seeded games: the rows it
builds for an open Intrigue choice are ``legal_intrigue_choice_actions``
(stage A1 then moves the Intrigue choice frame onto it, and the engine
equivalence gate takes over from this comparison), and its pending-list
policy gives the Reveal frame's rows, its hold of ``finish_reveal`` and the
entry an action takes (until stage A4 moves the Reveal choices onto it).
"""

from collections import Counter
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import StateAgent
from dune_imperium.agents.registry import make_agent
from dune_imperium.content.uprising.effect_dsl import (
    SetAsideImperiumRowCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.types import (
    MANDATORY_REVEAL_CHOICES,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules import reveal_turn as reveal
from dune_imperium.rules.ability_executor import (
    IN_TURN,
    STACKED,
    PendingAbility,
    ability_of,
    ability_rows,
    current_piece,
    decode_pending,
    encode_pending,
    entry_pieces,
    entry_taking,
    holds_turn_end,
    intrigue_ref,
    pending_rows,
    piece_rows,
)
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue import legal_intrigue_choice_actions

_FULL = RulesetConfig(
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)


def test_a_pending_ability_round_trips_through_its_stored_form() -> None:
    entries = (
        PendingAbility(
            Source.INTRIGUE, intrigue_ref("intrigue:bribery:1", 0), (0, 2)
        ),
        PendingAbility(
            Source.INTRIGUE,
            intrigue_ref("intrigue:ambush:0", 1),
            (),
            step=3,
            chosen=("emperor", "fremen"),
            rewards_applied=True,
            shield_wall=False,
        ),
    )
    assert decode_pending(encode_pending(entries)) == entries
    assert decode_pending("") == ()
    for entry in entries:
        assert PendingAbility.decode(entry.encode()) == entry


def test_a_value_holding_a_separator_is_refused() -> None:
    for ref in ("a|b", "a,b", "a;b", ""):
        with pytest.raises(ValueError, match="cannot store"):
            PendingAbility(Source.INTRIGUE, ref, ())
    with pytest.raises(ValueError, match="cannot store"):
        PendingAbility(Source.INTRIGUE, "card#0", (), chosen=("x,y",))
    with pytest.raises(ValueError, match="negative"):
        PendingAbility(Source.INTRIGUE, "card#0", (), step=-1)
    with pytest.raises(ValueError, match="not a stored"):
        PendingAbility.decode("intrigue|card#0|0|0")


def test_an_intrigue_entry_reads_its_ability_and_pieces() -> None:
    entry = PendingAbility(
        Source.INTRIGUE, intrigue_ref("intrigue:tenuous_bond:0", 0), (0,)
    )
    ability = ability_of(entry)
    assert ability.sections
    pieces = entry_pieces(entry)
    assert current_piece(entry) == (pieces[0] if pieces else None)
    assert current_piece(replace(entry, step=len(pieces))) is None
    with pytest.raises(LookupError, match="no ability lookup"):
        ability_of(PendingAbility(Source.AGENT_CARD, "card", ()))


def _state_with_hand() -> GameState:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), 7)
    chance = ChanceResolver(seed=7)
    while not state.players[0].hand:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
        else:
            assert isinstance(decision, PlayerDecision)
            legal = engine.legal_actions(state, decision.owner)
            state = engine.apply(state, legal[0], legal_actions=legal).state
    return state


def test_one_piece_is_named_for_each_source() -> None:
    """Plan 4.3: the same trash is ``trash_intrigue_card`` for an Intrigue,
    ``trash_agent_card`` for an Agent box (tagged ``box`` for a grafted
    turn's second card) and ``trash_reveal_card`` for a revealed card
    (tagged with the card's ``source``)."""

    state = _state_with_hand()
    owner = state.players[0]
    piece = TrashPersonalCard()
    intrigue = piece_rows(state, 0, piece, Source.INTRIGUE, refusals=True)
    assert intrigue[0] == DomainAction("decline_intrigue_trash", 0)
    assert {row.action_id for row in intrigue[1:]} == {"trash_intrigue_card"}
    assert [dict(row.arguments)["card_id"] for row in intrigue[1:]] == list(owner.hand)
    agent = piece_rows(state, 0, piece, Source.AGENT_CARD, refusals=False)
    assert {row.action_id for row in agent} == {"trash_agent_card"}
    assert all("box" not in dict(row.arguments) for row in agent)
    partner = piece_rows(
        state, 0, piece, Source.AGENT_CARD, refusals=False, tag_value=1
    )
    assert all(dict(row.arguments)["box"] == 1 for row in partner)
    revealed = piece_rows(
        state, 0, piece, Source.REVEAL_CARD, refusals=False, tag_value="shrouded"
    )
    assert {row.action_id for row in revealed} == {"trash_reveal_card"}
    assert all(dict(row.arguments)["source"] == "shrouded" for row in revealed)
    # A mandatory trash never offers a refusal.
    must = piece_rows(
        state, 0, TrashPersonalCard(mandatory=True), Source.INTRIGUE, refusals=True
    )
    assert all(row.action_id == "trash_intrigue_card" for row in must)


def test_a_piece_its_source_cannot_name_stops_the_executor() -> None:
    state = _state_with_hand()
    with pytest.raises(LookupError, match="templates answer set_aside"):
        piece_rows(
            state, 0, SetAsideImperiumRowCard(), Source.AGENT_CARD, refusals=False
        )


def test_the_pending_list_policy() -> None:
    state = _state_with_hand()
    a = DomainAction("trash_reveal_card", 0, (("card_id", "x"),))
    b = DomainAction("trash_reveal_card", 0, (("card_id", "y"),))
    rows = {"first": (a,), "second": (a, b), "waiting": (), "last": (b,)}

    def rows_of(
        _state: GameState, _player: int, entry: str
    ) -> tuple[DomainAction, ...]:
        return rows[entry]

    entries = ("waiting", "first", "second", "last")
    assert pending_rows(state, 0, entries, rows_of) == (a, b)
    assert entry_taking(state, 0, entries, a, rows_of) == 1
    assert entry_taking(state, 0, entries, b, rows_of) == 2
    finish = DomainAction("finish_reveal", 0)
    assert entry_taking(state, 0, entries, finish, rows_of) is None
    assert holds_turn_end(state, 0, entries, rows_of, lambda entry: entry == "last")
    assert not holds_turn_end(
        state, 0, entries, rows_of, lambda entry: entry == "waiting"
    )


def _intrigue_entry(frame: DecisionFrame) -> tuple[PendingAbility, str]:
    """The Intrigue choice frame's state as a pending ability."""

    context = dict(frame.context)
    card_id, option = context["card_id"], context["option"]
    sections, chosen, slot = (
        context["sections"],
        context["chosen_factions"],
        context["slot"],
    )
    assert isinstance(card_id, str) and isinstance(option, int)
    assert isinstance(sections, str) and isinstance(chosen, str)
    assert isinstance(slot, int)
    entry = PendingAbility(
        Source.INTRIGUE,
        intrigue_ref(card_id, option),
        tuple(int(index) for index in sections.split(",") if index),
        step=slot,
        chosen=tuple(value for value in chosen.split(",") if value),
        rewards_applied=context.get("rewards_applied") is True,
        shield_wall=context.get("shield_wall_at_play", True) is True,
    )
    return entry, card_id


def _mandatory(entry: tuple[str, str]) -> bool:
    return PersonalCardRevealChoiceEffect(entry[1]) in MANDATORY_REVEAL_CHOICES


def test_the_executor_matches_the_engine_on_seeded_games() -> None:
    engine = UprisingRulesEngine()
    pieces: Counter[str] = Counter()
    reveal_states = reveal_takes = 0
    for seed in range(910_000, 910_012):
        state = engine.reset(_FULL, seed)
        agents = [make_agent("random", seed * 10 + seat, _FULL) for seat in range(4)]
        chance = ChanceResolver(seed=seed)
        while state.phase is not GamePhase.FINISHED:
            decision = engine.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = engine.apply(state, chance.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            player = decision.owner
            top = state.decision_stack[-1]
            if top.kind == FrameKind.INTRIGUE_CHOICE:
                entry, card_id = _intrigue_entry(top)
                piece = current_piece(entry)
                pieces[type(piece).__name__ if piece else "rewards"] += 1
                assert ability_rows(
                    state, player, entry, STACKED, played_card_id=card_id
                ) == legal_intrigue_choice_actions(state, player)
                # The owner's own turn offers no refusal and no rewards row.
                assert all(
                    not row.action_id.startswith("decline_")
                    or row.action_id == "decline_intrigue_spy"
                    for row in ability_rows(state, player, entry, IN_TURN)
                )
            by_entry = reveal.pending_choice_entries(state, player)
            if by_entry:
                reveal_states += 1
                offered = dict(by_entry)
                entries = tuple(entry for entry, _ in by_entry)

                def rows_of(
                    _state: GameState,
                    _player: int,
                    entry: tuple[str, str],
                    offered: dict[tuple[str, str], tuple[DomainAction, ...]] = offered,
                ) -> tuple[DomainAction, ...]:
                    return offered[entry]

                rows = pending_rows(state, player, entries, rows_of)
                assert rows == reveal.legal_pending_reveal_choice_actions(state, player)
                assert holds_turn_end(
                    state, player, entries, rows_of, _mandatory
                ) == reveal.mandatory_choice_is_pending(state, player)
                for row in rows:
                    index = entry_taking(state, player, entries, row, rows_of)
                    assert index is not None
                    opened = reveal.open_pending_reveal_choice(state, row)
                    left = reveal.pending_reveal_choices(
                        dict(opened.decision_stack[-2].context)
                    )
                    assert [entry for entry in entries if entry not in left] == [
                        entries[index]
                    ]
                    reveal_takes += 1
            legal = engine.legal_actions(state, player)
            agent = agents[player]
            view = engine.observe(state, player)
            action = (
                agent.choose_action_with_state(state, view, legal)
                if isinstance(agent, StateAgent)
                else agent.choose_action(view, legal)
            )
            state = engine.apply(state, action, legal_actions=legal).state
    # The common pieces were reached (200 such games reach all nineteen).
    assert {
        "GainInfluence",
        "LoseInfluence",
        "DiscardFromHand",
        "LoseTroops",
        "RetreatTroops",
        "PlaceSpy",
        "RecallSpy",
        "TrashPersonalCard",
        "DeployFromGarrison",
        "AcquireCardUpTo",
        "DestroyShieldWall",
    } <= set(pieces), pieces
    assert reveal_states > 100 and reveal_takes > 100
