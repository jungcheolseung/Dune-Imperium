"""The pending-ability executor (docs/composed-effects-plan.md 4.2-4.3).

Since stage A1 (codec v148) the engine resolves Intrigue cards through the
executor, so their rows are no longer compared with an engine copy: the
engine equivalence gate (``scripts/ab/engine_equivalence.py``) held the
stage to the engine before it. These tests pin the executor's own parts --
the stored entry, the pieces that wait for a later step, the source-named
rows and events -- and keep holding its pending-list policy to the Reveal
frame's rows, its hold of ``finish_reveal`` and the entry an action takes
(until stage A4 moves the Reveal choices onto it).
"""

from collections import Counter
from dataclasses import replace
from typing import cast

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import StateAgent
from dune_imperium.agents.registry import make_agent
from dune_imperium.content.uprising.effect_dsl import (
    SetAsideImperiumRowCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.reveal_choice_abilities import (
    reveal_choice_is_optional,
)
from dune_imperium.content.uprising.types import (
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import Influence
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules import reveal_turn as reveal
from dune_imperium.rules.ability_executor import (
    IN_TURN,
    STACKED,
    PendingAbility,
    ability_of,
    ability_rows,
    apply_piece,
    current_piece,
    decode_pending,
    encode_pending,
    entry_pieces,
    entry_taking,
    holds_turn_end,
    intrigue_ref,
    pending_rows,
    piece_rows,
    split_intrigue_ref,
)
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.frames import FrameKind, replace_player
from dune_imperium.rules.intrigue import pending_intrigue_ability

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
        PendingAbility(
            Source.INTRIGUE,
            intrigue_ref("intrigue:buy_access:0", 0),
            (0,),
            step=1,
            chosen=("emperor",),
            held=("emperor",),
            tally=2,
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
    with pytest.raises(ValueError, match="cannot store"):
        PendingAbility(Source.INTRIGUE, "card#0", (), held=("a;b",))
    with pytest.raises(ValueError, match="negative"):
        PendingAbility(Source.INTRIGUE, "card#0", (), step=-1)
    with pytest.raises(ValueError, match="negative"):
        PendingAbility(Source.INTRIGUE, "card#0", (), tally=-1)
    with pytest.raises(ValueError, match="not a stored"):
        PendingAbility.decode("intrigue|card#0|0|0")
    # The A0 form, without the held values and the tally.
    with pytest.raises(ValueError, match="not a stored"):
        PendingAbility.decode("intrigue|card#0|0|0||0|1")


def test_an_intrigue_reference_splits_back() -> None:
    ref = intrigue_ref("intrigue:twisted_ambitious:0", 1)
    assert split_intrigue_ref(ref) == ("intrigue:twisted_ambitious:0", 1)
    for bad in ("intrigue:bribery:1", "#0", "card#", "card#x"):
        with pytest.raises(ValueError, match="not an Intrigue option reference"):
            split_intrigue_ref(bad)


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


def _faction(value: str) -> DomainAction:
    return DomainAction("choose_intrigue_faction", 0, (("faction", value),))


def test_choose_two_names_both_factions_before_either_moves() -> None:
    """Buy Access's "Choose two" (``GainInfluence(times=2, distinct=True)``):
    both Factions are named before either Influence moves (designer ruling,
    OQ-057); the first waits in ``held`` and is not offered again."""

    state = _state_with_hand()
    entry = PendingAbility(
        Source.INTRIGUE, intrigue_ref("intrigue:buy_access:0", 0), (0,)
    )
    first = apply_piece(state, 0, entry, _faction("emperor"), source="s")
    assert [event.event_id for event in first.result.events] == [
        "s:slot:0:chosen:emperor"
    ]
    assert first.result.events[0].kind == "intrigue_influence_chosen"
    assert first.result.state.players[0].influence == state.players[0].influence
    assert first.entry == replace(entry, step=1, chosen=("emperor",), held=("emperor",))
    offered = ability_rows(first.result.state, 0, first.entry, STACKED)
    assert _faction("emperor") not in offered and _faction("fremen") in offered
    second = apply_piece(
        first.result.state, 0, first.entry, _faction("fremen"), source="s"
    )
    assert [event.event_id for event in second.result.events] == [
        "s:slot:1:gained:emperor:influence",
        "s:slot:1:gained:fremen:influence",
    ]
    gained = second.result.state.players[0].influence
    assert (gained.emperor, gained.fremen) == (1, 1)
    assert second.entry == replace(entry, step=2, chosen=("emperor", "fremen"))


def test_choose_two_with_no_second_faction_still_pays_the_first() -> None:
    """Every Faction but Fremen at the top: the second gain is lost (OQ-060)
    and its owner confirms it, while the Faction already named is paid
    ("서로 다른 진영 둘"은 먼저 이름 붙인 진영을 그대로 지급)."""

    state = _state_with_hand()
    owner = replace(
        state.players[0],
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6),
    )
    state = replace(state, players=replace_player(state.players, owner))
    entry = PendingAbility(
        Source.INTRIGUE, intrigue_ref("intrigue:buy_access:0", 0), (0,)
    )
    assert ability_rows(state, 0, entry, STACKED) == (_faction("fremen"),)
    first = apply_piece(state, 0, entry, _faction("fremen"), source="s")
    confirm = DomainAction("resolve_intrigue_influence_without_faction", 0)
    assert ability_rows(first.result.state, 0, first.entry, STACKED) == (confirm,)
    lost = apply_piece(first.result.state, 0, first.entry, confirm, source="s")
    assert [(event.event_id, event.kind) for event in lost.result.events] == [
        ("s:slot:1:influence_unavailable", "intrigue_influence_unavailable"),
        ("s:slot:1:gained:fremen:influence", "influence_gained"),
    ]
    assert lost.result.state.players[0].influence.fremen == 1
    assert lost.entry == replace(entry, step=2, chosen=("fremen",))


def test_a_lose_troops_cost_moves_the_tactics_token_once() -> None:
    """Twisted Ambitious's "lose three troops" is paid one troop per piece but
    is one source: Chani's Tactics token moves once, on the last piece, by
    the troops taken from the Conflict ("Each different source of retreating
    or losing troops is handled separately" [FAQ p. 1])."""

    state = _state_with_hand()
    chani = replace(
        state.players[0], leader_id="chani", troops_conflict=2, troops_garrison=1
    )
    state = replace(state, players=replace_player(state.players, chani))
    entry = PendingAbility(
        Source.INTRIGUE, intrigue_ref("intrigue:twisted_ambitious:0", 0), (0,)
    )
    tallies: list[int] = []
    advanced: list[tuple[int, int]] = []
    for zone in ("conflict", "garrison", "conflict"):
        lose = DomainAction("lose_intrigue_troop", 0, (("zone", zone),))
        assert lose in ability_rows(state, 0, entry, STACKED)
        applied = apply_piece(state, 0, entry, lose, source="s")
        state, entry = applied.result.state, applied.entry
        tallies.append(entry.tally)
        advanced.extend(
            (
                cast(int, dict(event.payload)["count"]),
                cast(int, dict(event.payload)["space"]),
            )
            for event in applied.result.events
            if event.kind == "tactics_token_advanced"
        )
    assert tallies == [1, 1, 0]
    assert advanced == [(2, chani.tactics_track_space + 2)]
    assert state.players[0].tactics_track_space == chani.tactics_track_space + 2


def test_a_refusal_announces_its_source_s_event() -> None:
    state = _state_with_hand()
    ref = intrigue_ref("intrigue:cunning:0", 1)
    entry = next(
        PendingAbility(Source.INTRIGUE, ref, (0,), step=step)
        for step, piece in enumerate(
            entry_pieces(PendingAbility(Source.INTRIGUE, ref, (0,)))
        )
        if isinstance(piece, TrashPersonalCard)
    )
    declined = apply_piece(
        state, 0, entry, DomainAction("decline_intrigue_trash", 0), source="s"
    )
    assert declined.result.state is state
    assert [(event.event_id, event.kind) for event in declined.result.events] == [
        (f"s:slot:{entry.step}:trash_declined", "optional_trash_declined")
    ]
    assert declined.entry == replace(entry, step=entry.step + 1)


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


def _mandatory(entry: tuple[str, str]) -> bool:
    return not reveal_choice_is_optional(PersonalCardRevealChoiceEffect(entry[1]))


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
                # The frame stores its progress as one pending ability.
                context = dict(top.context)
                entry = pending_intrigue_ability(context)
                assert entry is not None
                assert split_intrigue_ref(entry.ref)[0] == context["card_id"]
                assert not {"slot", "sections", "chosen_factions"} & set(context)
                piece = current_piece(entry)
                pieces[type(piece).__name__ if piece else "rewards"] += 1
                # The owner's own turn offers no refusal and no rewards row.
                assert all(
                    not row.action_id.startswith("decline_")
                    or row.action_id == "decline_intrigue_spy"
                    for row in ability_rows(state, player, entry, IN_TURN)
                )
            if top.kind == FrameKind.INTRIGUE_EFFECTS:
                # A separate-lines card waits as one entry per unused line.
                context = dict(top.context)
                lines = decode_pending(str(context["pending_lines"]))
                assert all(len(line.sections) == 1 for line in lines)
                assert pending_intrigue_ability(context) is None
                pieces["lines"] += 1
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
    # The common pieces were reached through the engine (200 such games
    # reach all nineteen).
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
        "lines",
    } <= set(pieces), pieces
    assert reveal_states > 100 and reveal_takes > 100
