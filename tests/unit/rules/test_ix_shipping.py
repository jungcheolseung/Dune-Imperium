"""Rise of Ix's Shipping track and Freighter (stage P4c-3).

Rules: docs/rules/rise-of-ix.md 5 ("Shipping track"), ``[Rise of Ix p. 5]``
``[FAQ p. 3]`` ``[FAQ p. 4]``, the Troop Transports row of its section 4 and
docs/base-game-and-ix-plan.md 17.10 item 3. Setup refuses ``rise_of_ix`` until
stage P4c-5, so every state is the original game's round one at seat 0's first
turn with its config switched to ``rise_of_ix=True`` and the Freighter, tiles
and troops laid on the seats by ``dataclasses.replace``. No space or card
prints the Freighter icon yet (stages P4c-4 and P4d), so the icon goes through
the executor with hand-built abilities, a recall's rewards are taken as the
rows the engine offers, and the out-of-turn window opens the way a Conflict
reward's icon will.
"""

from collections.abc import Callable, MutableMapping
from dataclasses import replace
from typing import cast

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement
from dune_imperium.content.uprising.abilities import Ability, AbilityTiming
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import EffectSection, Freighter
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    Resources,
)
from dune_imperium.core.observation import NO_IX_PENDING, ix_pending_of
from dune_imperium.rules import UprisingRulesEngine, ability_executor, turn_rows
from dune_imperium.rules import tech as tech_rules
from dune_imperium.rules.ability_executor import (
    IN_TURN,
    STACKED,
    PendingAbility,
    ability_rows,
    apply_piece,
    current_piece,
    entry_pieces,
)
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat_deployment import (
    RECRUITS_DEPLOYABLE_KEY,
    RECRUITS_OWED_KEY,
    legal_combat_deployments,
)
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.shipping_track import (
    freighter_can_advance,
    freighter_can_recall,
    move_freighter_up,
    open_freighter_move,
    recall_freighter,
    shipping_troops,
)
from dune_imperium.rules.shortfall import refill_shortfall

LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
STANDARD = "sardaukar_standard"
RESEARCH_STATION = "imperium_research_station"
# Costs: Detonation Devices 3, Artillery 1, Chaumurky 4 | Holtzman Engine 6,
# Invasion Ships 5, Memocorders 2 | Restricted Ordnance 4, Minimic Film 2,
# Flagship 8.
STACKS = (
    ("detonation_devices", "artillery", "chaumurky"),
    ("holtzman_engine", "invasion_ships", "memocorders"),
    ("restricted_ordnance", "minimic_film", "flagship"),
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)


def _start(*, rise_of_ix: bool = True) -> GameState:
    """Round 1 of an original game at seat 0's first turn, with or without
    Rise of Ix switched on, the Ix stacks laid."""

    state = ENGINE.reset(ORIGINAL, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    state = replace(state, config=replace(state.config, rise_of_ix=rise_of_ix))
    return replace(state, tech_stacks=STACKS)


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _at(space: int, **changes: object) -> GameState:
    """Seat 0's open turn with its Freighter on ``space``."""

    return _seat(_start(), freighter_space=space, **changes)


def _recalled(state: GameState) -> GameState:
    return recall_freighter(state, 0, source="s").state


def _rows(state: GameState, seat: int = 0) -> list[DomainAction]:
    return [
        action
        for action in ENGINE.legal_actions(state, seat)
        if action.action_id == "resolve_shipping_reward"
    ]


def _claim(state: GameState, effect: str, faction: str | None = None) -> GameState:
    """Seat 0 takes the reward row ``effect`` (naming ``faction``)."""

    arguments: tuple[tuple[str, str], ...] = (("effect", effect),)
    if faction is not None:
        arguments = (*arguments, ("faction", faction))
    row = DomainAction("resolve_shipping_reward", 0, arguments)
    assert row in ENGINE.legal_actions(state, 0)
    return ENGINE.apply(state, row).state


def _declined(state: GameState) -> GameState:
    """The open Acquire Tech refused."""

    return tech_rules.apply_tech_acquisition(
        state, DomainAction("decline_tech", 0)
    ).state


def _kinds(state: GameState) -> list[str]:
    return [frame.kind for frame in state.decision_stack]


def _context_of(state: GameState) -> dict[str, object]:
    return dict(state.decision_stack[-1].context)


def _owed(state: GameState, seat: int = 0) -> tuple[int, ...]:
    return ix_pending_of(state, seat).shipping_rewards


def _round_trips(state: GameState, *seats: int) -> None:
    """Every row the engine offers ``seats`` encodes and decodes to itself in
    the state's own catalog (the original game with Rise of Ix)."""

    codec = ActionCodec(state.config)
    for seat in seats:
        for action in ENGINE.legal_actions(state, seat):
            assert codec.decode(codec.encode(action), action.actor) == action


# --- The Freighter icon through the executor -----------------------------------


def _ability(icons: int) -> Ability:
    """A hand-built Plot of ``icons`` Freighter icons."""

    return Ability(AbilityTiming.PLOT, (EffectSection(rewards=(Freighter(),) * icons),))


@pytest.fixture
def printed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the executor read hand-built abilities for Intrigue entries: ref
    ``fr#1`` prints one Freighter icon, ``fr#2`` two."""

    abilities = {"fr#1": _ability(1), "fr#2": _ability(2)}
    monkeypatch.setitem(
        cast(
            MutableMapping[Source, Callable[[str], Ability]],
            ability_executor._ABILITIES,
        ),
        Source.INTRIGUE,
        lambda ref: abilities[ref],
    )


def _entry(ref: str = "fr#1") -> PendingAbility:
    return PendingAbility(Source.INTRIGUE, ref, (0,))


ADVANCE = DomainAction("advance_intrigue_freighter", 0)
RECALL = DomainAction("recall_intrigue_freighter", 0)
DECLINE = DomainAction("decline_intrigue_freighter", 0)


@pytest.mark.usefixtures("printed")
def test_a_freighter_icon_moves_the_freighter_up_one_space() -> None:
    """ "Freighter 아이콘마다 Freighter를 둘 가운데 하나로 움직일 수
    있다("may"): 한 칸 위로 ..." [Rise of Ix p. 5]: each icon is one choice, and
    a taken up-move moves the Freighter one space, the rest of the track left
    alone. From the bottom the recall has nothing to take (it moves nothing and
    pays nothing), so only the up-move and, in a stacked frame, the refusal
    are offered."""

    state = _at(0)
    entry = _entry("fr#2")
    assert entry_pieces(entry) == (Freighter(), Freighter())
    assert ability_rows(state, 0, entry, STACKED) == (ADVANCE, DECLINE)
    assert ability_rows(state, 0, entry, IN_TURN) == (ADVANCE,)

    first = apply_piece(state, 0, entry, ADVANCE, source="s")
    assert first.result.state.players[0].freighter_space == 1
    assert [(e.event_id, e.kind) for e in first.result.events] == [
        ("s:slot:0:freighter_moved", "freighter_moved")
    ]
    assert dict(first.result.events[0].payload) == {"player": 0, "space": 1}
    assert current_piece(first.entry) == Freighter()
    # With the Freighter on space 1 the second icon may also recall.
    assert ability_rows(first.result.state, 0, first.entry, STACKED) == (
        ADVANCE,
        RECALL,
        DECLINE,
    )
    second = apply_piece(first.result.state, 0, first.entry, ADVANCE, source="s")
    assert second.result.state.players[0].freighter_space == 2
    assert current_piece(second.entry) is None


@pytest.mark.usefixtures("printed")
def test_at_the_top_the_freighter_cannot_move_up() -> None:
    """ "한 칸 위로(맨 위면 불가)" [Rise of Ix p. 5]: from space 3 no up-move
    is offered, only the recall and the refusal, and the rule refuses one."""

    state = _at(3)
    assert not freighter_can_advance(state, 0)
    assert ability_rows(state, 0, _entry(), STACKED) == (RECALL, DECLINE)
    assert ability_rows(state, 0, _entry(), IN_TURN) == (RECALL,)
    with pytest.raises(ValueError, match="top space"):
        move_freighter_up(state, 0, source="s")
    with pytest.raises(ValueError, match="top space"):
        apply_piece(state, 0, _entry(), ADVANCE, source="s")


@pytest.mark.usefixtures("printed")
def test_a_freighter_icon_may_be_left_unused() -> None:
    """ "움직일 수 있다("may")" [Rise of Ix p. 5] and docs/rules/rise-of-ix.md
    14 ("위로 한 칸 -OR- 회수 -OR- 쓰지 않음"): the refusal moves nothing and
    owes nothing; the owner's own turn offers no refusal -- the icon lapses at
    the turn's end (OQ-095 (2))."""

    state = _at(2)
    declined = apply_piece(state, 0, _entry(), DECLINE, source="s")
    assert declined.result.state is state
    assert [(e.event_id, e.kind) for e in declined.result.events] == [
        ("s:slot:0:freighter_declined", "intrigue_freighter_declined")
    ]
    assert current_piece(declined.entry) is None
    assert DECLINE not in ability_rows(state, 0, _entry(), IN_TURN)


@pytest.mark.usefixtures("printed")
def test_the_executor_recall_owes_the_rewards_of_a_stacked_frames_owner() -> None:
    """ "회수하면 지금 칸과 그 아래 모든 칸의 보상을 받는다" [Rise of Ix p. 5]:
    the recall an icon's piece makes is the rule's recall (the Freighter goes to
    the bottom, the rewards are owed on the owner's open turn)."""

    state = _at(2)
    taken = apply_piece(state, 0, _entry(), RECALL, source="s")
    after = taken.result.state
    assert after.players[0].freighter_space == 0
    assert [e.kind for e in taken.result.events] == ["freighter_recalled"]
    assert _owed(after) == (1, 2)


# --- The recall and its rewards in the owner's turn ----------------------------


@pytest.mark.parametrize("space", [1, 2, 3])
def test_a_recall_owes_the_rewards_of_its_space_and_every_space_below(
    space: int,
) -> None:
    """ "회수하면 지금 칸과 그 아래 모든 칸의 보상을 원하는 순서로 받는다"
    [Rise of Ix p. 5]: the Freighter returns to the bottom, each owed space is
    a reward waiting on the turn, ``ix_pending_of`` shows the spaces still owed,
    and every owed space's rows are offered at once."""

    state = _at(space)
    result = recall_freighter(state, 0, source="s")
    after = result.state
    assert after.players[0].freighter_space == 0
    assert [e.kind for e in result.events] == ["freighter_recalled"]
    assert dict(result.events[0].payload) == {"from_space": space, "player": 0}
    assert _owed(after) == tuple(range(1, space + 1))
    effects = {dict(row.arguments)["effect"] for row in _rows(after)}
    assert (
        effects
        == {
            1: {"dividends", "spice"},
            2: {"dividends", "spice", "recruit", "influence"},
            3: {"dividends", "spice", "recruit", "influence", "tech"},
        }[space]
    )
    _round_trips(after, 0)


def test_a_recall_from_the_bottom_pays_nothing() -> None:
    """The Freighter starts on the bottom, which pays nothing ("현재 칸과 그
    아래 모든 칸" has no space under it, [Rise of Ix p. 5]): no recall is
    offered there and the rule refuses one."""

    state = _at(0)
    assert not freighter_can_recall(state, 0)
    with pytest.raises(ValueError, match="bottom"):
        recall_freighter(state, 0, source="s")


def test_the_rewards_may_be_taken_in_any_order() -> None:
    """ "보상을 원하는 순서로 받는다" [Rise of Ix p. 5]: the rewards of a recall
    from space 3 taken spice, recruit, Influence, Acquire Tech and the other
    way round -- Acquire Tech first, then the Influence, then the recruit,
    then the spice -- leave the same state, and the spaces still owed shrink
    as their last reward is taken (space 2 prints two)."""

    ordered = _recalled(_at(3, tech_ids=()))
    assert _owed(ordered) == (1, 2, 3)
    ordered = _claim(ordered, "spice")
    assert _owed(ordered) == (2, 3)
    ordered = _claim(ordered, "recruit")
    assert _owed(ordered) == (2, 3)
    ordered = _claim(ordered, "influence", "fremen")
    assert _owed(ordered) == (3,)
    ordered = _claim(ordered, "tech")
    assert ordered.decision_stack[-1].kind == FrameKind.TECH_ACQUISITION
    ordered = _declined(ordered)
    assert _owed(ordered) == ()

    reversed_ = _claim(_recalled(_at(3, tech_ids=())), "tech")
    # The Tech window opens on top of the turn; its refusal leaves the rest.
    assert reversed_.decision_stack[-1].kind == FrameKind.TECH_ACQUISITION
    reversed_ = _declined(reversed_)
    assert _owed(reversed_) == (1, 2)
    reversed_ = _claim(reversed_, "influence", "fremen")
    assert _owed(reversed_) == (1, 2)
    reversed_ = _claim(reversed_, "recruit")
    assert _owed(reversed_) == (1,)
    reversed_ = _claim(reversed_, "spice")
    assert _owed(reversed_) == ()
    assert reversed_.players == ordered.players


def test_space_one_is_dividends_or_two_spice_and_is_paid_once() -> None:
    """ "1. 고르기: Dividends(5 Solari, 상대마다 1 Solari) -OR- spice 2"
    [Rise of Ix p. 5]: Dividends gives the seat 5 Solari and every opponent 1;
    the spice gives 2 spice and nobody else anything; either settles the
    space, so the other is not offered after it."""

    base = _recalled(_at(1))
    before = [seat.resources for seat in base.players]

    paid = _claim(base, "dividends")
    assert paid.players[0].resources.solari == before[0].solari + 5
    for seat in (1, 2, 3):
        assert paid.players[seat].resources.solari == before[seat].solari + 1
        assert paid.players[seat].resources.spice == before[seat].spice
    assert paid.players[0].resources.spice == before[0].spice
    assert _rows(paid) == []
    assert _owed(paid) == ()

    spiced = _claim(base, "spice")
    assert spiced.players[0].resources.spice == before[0].spice + 2
    assert spiced.players[0].resources.solari == before[0].solari
    assert [seat.resources for seat in spiced.players[1:]] == before[1:]
    assert _rows(spiced) == []


def _of(state: GameState, effect: str) -> list[DomainAction]:
    return [row for row in _rows(state) if dict(row.arguments)["effect"] == effect]


def test_space_two_prints_a_recruit_and_an_influence_as_two_rewards() -> None:
    """ "2. troop 2 recruit + 진영 하나에 Influence 1" [Rise of Ix p. 5] and the
    OQ-148 ruling (separately printed rewards are resolved in the owner's
    order): the two troops and the Influence are two owed rows of their own,
    each its own entry waiting on the turn, and the troops move from the
    supply to the garrison without the Influence having been taken."""

    state = _recalled(_at(2, troops_garrison=1, troops_supply=11))
    frame = state.decision_stack[-1]
    assert [value for _, _, value in turn_rows.pending(frame)] == [
        "1",
        "2:recruit",
        "2:influence",
    ]
    assert [row.arguments for row in _of(state, "recruit")] == [
        (("effect", "recruit"),)
    ]
    fremen = state.players[0].influence.fremen

    after = _claim(state, "recruit")
    owner = after.players[0]
    assert (owner.troops_garrison, owner.troops_supply) == (3, 9)
    assert owner.influence.fremen == fremen
    assert _of(after, "recruit") == []
    assert _of(after, "influence") != []
    assert _owed(after) == (1, 2)
    assert turn_rows.holds_the_end(_claim(after, "spice"), 0)


def test_space_twos_influence_goes_to_a_faction_that_can_rise() -> None:
    """ "진영 하나에 Influence 1" [Rise of Ix p. 5]: one row for each Faction
    that can still rise ("진영을 고르는 보상은 6칸 진영을 제외한다", OQ-060);
    with every cube at the top the Influence is lost and its owner confirms it
    with one row without a Faction, which holds the turn's end like any other
    mandatory reward."""

    state = _recalled(_at(2))
    factions = {dict(row.arguments).get("faction") for row in _of(state, "influence")}
    assert factions == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    after = _claim(state, "influence", "emperor")
    assert after.players[0].influence.emperor == state.players[0].influence.emperor + 1

    topped = _recalled(
        _at(
            2,
            influence=Influence(emperor=2, spacing_guild=2, bene_gesserit=2, fremen=6),
        )
    )
    offered = {dict(row.arguments).get("faction") for row in _of(topped, "influence")}
    assert offered == {"emperor", "spacing_guild", "bene_gesserit"}

    full = _recalled(
        _at(
            2,
            influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
        )
    )
    assert [row.arguments for row in _of(full, "influence")] == [
        (("effect", "influence"),)
    ]
    lost = ENGINE.apply(full, _of(full, "influence")[0])
    assert [e.kind for e in lost.events] == ["shipping_influence_unavailable"]
    assert lost.state.players[0].influence == full.players[0].influence
    assert _owed(lost.state) == (1, 2)


def test_space_twos_two_rewards_are_taken_in_the_seats_order() -> None:
    """The OQ-148 ruling and "보상을 원하는 순서로 받는다" [Rise of Ix p. 5]:
    the recruit then the Influence, and the Influence then the recruit, leave
    the same state."""

    base = _recalled(_at(2, troops_garrison=1, troops_supply=11))
    base = _claim(base, "spice")
    first = _claim(_claim(base, "recruit"), "influence", "fremen")
    second = _claim(_claim(base, "influence", "fremen"), "recruit")
    assert first.players == second.players
    assert _owed(first) == ()
    assert first.players[0].troops_garrison == 3
    assert first.players[0].influence.fremen == base.players[0].influence.fremen + 1


def test_space_three_opens_an_acquire_tech_at_discount_two() -> None:
    """ "3. Tech Discount 2로 Acquire Tech" [Rise of Ix p. 5]: the reward opens
    the Acquire Tech frame at a Tech Discount of 2, which ``ix_pending_of``
    shows; Detonation Devices (3 spice) then costs 1, and it may be refused
    ("may", [Rise of Ix p. 4])."""

    state = _claim(_recalled(_at(3, resources=Resources(spice=1))), "tech")
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.TECH_ACQUISITION
    assert dict(frame.context)["discount"] == 2
    assert ix_pending_of(state, 0).tech_discount == 2
    offered = {
        dict(action.arguments)["tech_id"]
        for action in tech_rules.legal_tech_acquisition_actions(state, 0)
        if action.action_id == "acquire_tech"
    }
    assert "detonation_devices" in offered  # 3 - 2 = 1 spice, which it holds
    assert "chaumurky" not in offered  # 4 - 2 = 2 spice, which it does not
    assert DomainAction("decline_tech", 0) in (
        tech_rules.legal_tech_acquisition_actions(state, 0)
    )
    bought = tech_rules.apply_tech_acquisition(
        state, DomainAction("acquire_tech", 0, (("tech_id", "detonation_devices"),))
    ).state
    assert bought.players[0].tech_ids == ("detonation_devices",)
    assert bought.players[0].resources.spice == 0


def test_the_end_of_the_turn_waits_for_spaces_one_and_two_only() -> None:
    """The recall is the owner's choice, but its rewards are received
    ([Rise of Ix p. 5]); only the Acquire Tech is "may" ([Rise of Ix p. 4]).
    So space 1's choice and space 2's recruit and Influence hold the turn's
    end, while space 3's Acquire Tech waits unused: the turn-end press lapses
    it with an event (OQ-095 (2))."""

    state = _recalled(_at(3))
    assert turn_rows.holds_the_end(state, 0)
    state = _claim(state, "spice")
    assert turn_rows.holds_the_end(state, 0)
    state = _claim(state, "recruit")
    assert turn_rows.holds_the_end(state, 0)
    state = _claim(state, "influence", "fremen")
    assert not turn_rows.holds_the_end(state, 0)
    assert _owed(state) == (3,)
    lapsed = turn_rows.lapse(state, 0)
    assert [(e.kind, dict(e.payload)) for e in lapsed.events] == [
        ("shipping_reward_lapsed", {"player": 0, "space": 3})
    ]
    assert _owed(lapsed.state) == ()


# --- Deployment of the recruited troops ---------------------------------------


def _agent_turn(
    space: str,
    before: Callable[[GameState], GameState] | None = None,
    **changes: object,
) -> GameState:
    """Seat 0's Agent turn at ``space`` with its printed effects pending and
    Sardaukar Standard (whose Agent box prints nothing) played; ``before`` acts
    on the turn frame first (a recall made before the placement)."""

    state = _seat(
        _start(),
        hand=(f"imperium:{STANDARD}:0",),
        resources=Resources(water=2),
        **changes,
    )
    if before is not None:
        state = before(state)
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space
    )
    return apply_placement(ENGINE, state, placement).state


def _recalled_from(space: int) -> Callable[[GameState], GameState]:
    """A recall of seat 0's Freighter from ``space``."""

    return lambda state: (
        recall_freighter(_seat(state, freighter_space=space), 0, source="s").state
    )


def _deploy(state: GameState, count: int) -> GameState:
    return ENGINE.apply(
        state, DomainAction("deploy_troops", 0, (("count", count),))
    ).state


def _withdrawable(state: GameState) -> list[int]:
    return [
        cast(int, dict(action.arguments)["count"])
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "withdraw_troops"
    ]


def _deployable(state: GameState) -> list[int]:
    return [
        cast(int, dict(action.arguments)["count"])
        for action in legal_combat_deployments(state, 0)
    ]


def test_troops_recruited_by_a_recall_deploy_in_a_combat_space_turn() -> None:
    """ "회수로 recruit한 troop은 Combat 칸에 Agent를 보낸 turn이면 배치할 수
    있다 [FAQ p. 4]": in an Agent turn at a Combat space the two recruited
    troops join the deployment allowance beside the garrison's two, so a seat
    with two garrison troops may deploy up to four; at a space with no Combat
    icon there is no deployment at all."""

    combat = _agent_turn(RESEARCH_STATION, troops_garrison=2, troops_supply=10)
    assert _deployable(combat) == [1, 2]
    combat = _claim(
        recall_freighter(_seat(combat, freighter_space=2), 0, source="s").state,
        "recruit",
    )
    assert combat.players[0].troops_garrison == 4
    assert _deployable(combat) == [1, 2, 3, 4]

    quiet = _agent_turn("wealth", troops_garrison=2, troops_supply=10)
    quiet = _claim(
        recall_freighter(_seat(quiet, freighter_space=2), 0, source="s").state,
        "recruit",
    )
    assert quiet.players[0].troops_garrison == 4
    assert _deployable(quiet) == []
    assert not any(
        action.action_id == "deploy_troops" for action in ENGINE.legal_actions(quiet, 0)
    )


def test_troop_transports_recruits_one_more_troop() -> None:
    """ "Shipping track에서 troop을 recruit할 때마다 하나 더" (Troop Transports,
    [Rise of Ix p. 4]): the tile's ability is ``SHIPPING_EXTRA_TROOP``, a
    space-2 recruit gives three troops instead of two, and in a Combat-space
    turn all of them deploy."""

    assert shipping_troops(()) == 2
    assert shipping_troops(("troop_transports",)) == 3
    assert shipping_troops(("artillery", "troop_transports")) == 3

    combat = _agent_turn(
        RESEARCH_STATION,
        troops_garrison=0,
        troops_supply=12,
        tech_ids=("troop_transports",),
    )
    combat = _claim(
        recall_freighter(_seat(combat, freighter_space=2), 0, source="s").state,
        "recruit",
    )
    assert combat.players[0].troops_garrison == 3
    assert _deployable(combat) == [1, 2, 3]

    plain = _claim(_recalled(_at(2, troops_garrison=0, troops_supply=12)), "recruit")
    assert plain.players[0].troops_garrison == 2


def test_troop_transports_troops_deploy_in_a_turn_without_a_combat_space() -> None:
    """ "Troop Transports의 'You may deploy any of them to the Conflict'는 카드
    문장이 배치를 허락하므로 Combat 칸에 Agent를 보내지 않은 turn에도 배치할 수
    있다" (docs/rules/rise-of-ix.md 15, [DI p. 6]): at a space with no Combat
    icon the three troops of a recall's recruit (the extra one included) may
    deploy, each with a room of its own -- the two troops already in the
    garrison are not offered beside them (no garrison share) -- and a deployed
    troop is in the Conflict."""

    quiet = _agent_turn(
        "wealth", troops_garrison=2, troops_supply=10, tech_ids=("troop_transports",)
    )
    assert _deployable(quiet) == []
    quiet = _claim(_recalled_from(2)(quiet), "recruit")
    assert quiet.players[0].troops_garrison == 5
    assert _context_of(quiet)["shipping_troops_recruited"] == 3
    assert _deployable(quiet) == [1, 2, 3]

    deployed = _deploy(quiet, 2)
    owner = deployed.players[0]
    assert (owner.troops_garrison, owner.troops_conflict) == (3, 2)
    assert _deployable(deployed) == [1]
    assert _deploy(deployed, 1).players[0].troops_conflict == 3
    assert _deployable(_deploy(deployed, 1)) == []


def test_without_troop_transports_a_recall_deploys_nothing_in_such_a_turn() -> None:
    """ "회수로 recruit한 troop은 Combat 칸에 Agent를 보낸 turn이면 배치할 수
    있다" [FAQ p. 4]: with no Troop Transports -- or another tile -- the troops
    stay in the garrison at a space with no Combat icon."""

    for tiles in ((), ("windtraps",)):
        quiet = _agent_turn(
            "wealth", troops_garrison=2, troops_supply=10, tech_ids=tiles
        )
        quiet = _claim(_recalled_from(2)(quiet), "recruit")
        assert quiet.players[0].troops_garrison == 4
        assert "shipping_troops_recruited" not in _context_of(quiet)
        assert _deployable(quiet) == []
        assert not any(
            action.action_id == "deploy_troops"
            for action in ENGINE.legal_actions(quiet, 0)
        )


def test_a_withdrawal_gives_the_troop_transports_room_back() -> None:
    """The withdrawal of a deployment frees its room (OQ-029): troops deployed
    with Troop Transports' allowance in a turn with no Combat space return to
    the garrison, and may deploy again."""

    quiet = _agent_turn(
        "wealth", troops_garrison=0, troops_supply=12, tech_ids=("troop_transports",)
    )
    quiet = _deploy(_claim(_recalled_from(2)(quiet), "recruit"), 3)
    assert _deployable(quiet) == []
    assert _withdrawable(quiet) == [1, 2, 3]
    back = ENGINE.apply(
        quiet, DomainAction("withdraw_troops", 0, (("count", 2),))
    ).state
    owner = back.players[0]
    assert (owner.troops_garrison, owner.troops_conflict) == (2, 1)
    assert _deployable(back) == [1, 2]
    assert _withdrawable(back) == [1]


def test_troops_recruited_before_the_placement_deploy_wherever_the_agent_goes() -> None:
    """The recall made on the turn frame, before the Agent is sent, carries
    the Troop Transports troops over the placement (docs/rules/rise-of-ix.md
    15): they deploy at a space with no Combat icon, and at a Combat space they
    are plain recruits beside the garrison's two."""

    quiet = _agent_turn(
        "wealth",
        lambda state: _claim(_recalled_from(2)(state), "recruit"),
        troops_garrison=2,
        troops_supply=10,
        tech_ids=("troop_transports",),
    )
    assert _deployable(quiet) == [1, 2, 3]
    combat = _agent_turn(
        RESEARCH_STATION,
        lambda state: _claim(_recalled_from(2)(state), "recruit"),
        troops_garrison=2,
        troops_supply=10,
        tech_ids=("troop_transports",),
    )
    assert _deployable(combat) == [1, 2, 3, 4, 5]


def test_troop_transports_troops_deploy_in_a_reveal_turn_without_a_combat_icon() -> (
    None
):
    """The same sentence in the owner's Reveal turn
    (docs/rules/rise-of-ix.md 15): with no Combat icon the troops a Shipping
    recruit brings in deploy as "these troops" do (OQ-140), any of them and
    none of the garrison; without Troop Transports there is no deployment."""

    def reveal(tiles: tuple[str, ...]) -> GameState:
        state = _seat(
            _start(),
            freighter_space=2,
            hand=(f"imperium:{STANDARD}:0",),
            troops_garrison=2,
            troops_supply=10,
            tech_ids=tiles,
        )
        opened = ENGINE.apply(state, DomainAction("reveal_turn", 0)).state
        assert opened.decision_stack[-1].kind == FrameKind.REVEAL
        return _claim(recall_freighter(opened, 0, source="s").state, "recruit")

    def counts(state: GameState) -> list[int]:
        return [
            cast(int, dict(action.arguments)["count"])
            for action in ENGINE.legal_actions(state, 0)
            if action.action_id == "deploy_troops"
        ]

    assert counts(reveal(("troop_transports",))) == [1, 2, 3]
    assert counts(reveal(())) == []


def _with_context(state: GameState, **changes: bool | int | str) -> GameState:
    """``state`` with ``changes`` written into its top frame's context."""

    frame = state.decision_stack[-1]
    context = {**dict(frame.context), **changes}
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def test_the_troop_transports_window_closes_with_the_press_and_with_a_block() -> None:
    """The press closes the deployment window (OQ-029): a turn that is finishing
    offers no deployment, with Troop Transports' troops too; and a turn whose
    deployment is blocked ("can't", [Main p. 17]) keeps the block over the
    card's "may" (a choice the documents do not settle, reported)."""

    quiet = _agent_turn(
        "wealth", troops_garrison=0, troops_supply=12, tech_ids=("troop_transports",)
    )
    quiet = _claim(_recalled_from(2)(quiet), "recruit")
    assert _deployable(quiet) == [1, 2, 3]
    assert _deployable(_with_context(quiet, finishing=True)) == []
    assert _deployable(_with_context(quiet, units_deploy_blocked=True)) == []


def test_a_recall_before_a_reveal_carries_the_troop_transports_troops() -> None:
    """The recall made on the turn frame before the Reveal carries the troops
    into the Reveal turn (docs/rules/rise-of-ix.md 15): they deploy there with
    no Combat icon, and without Troop Transports they do not."""

    def counts(tiles: tuple[str, ...]) -> list[int]:
        state = _seat(
            _start(),
            freighter_space=2,
            hand=(f"imperium:{STANDARD}:0",),
            troops_garrison=2,
            troops_supply=10,
            tech_ids=tiles,
        )
        state = _claim(recall_freighter(state, 0, source="s").state, "recruit")
        opened = ENGINE.apply(state, DomainAction("reveal_turn", 0)).state
        assert opened.decision_stack[-1].kind == FrameKind.REVEAL
        return [
            cast(int, dict(action.arguments)["count"])
            for action in ENGINE.legal_actions(opened, 0)
            if action.action_id == "deploy_troops"
        ]

    assert counts(("troop_transports",)) == [1, 2, 3]
    assert counts(()) == []


def test_the_turns_end_leaves_undeployed_troop_transports_troops_in_the_garrison() -> (
    None
):
    """The window is the turn's: the press closes it (OQ-029), the turn passes
    to the next seat, and the troops left undeployed wait in the garrison."""

    quiet = _agent_turn(
        "wealth", troops_garrison=0, troops_supply=12, tech_ids=("troop_transports",)
    )
    quiet = _claim(_recalled_from(2)(quiet), "spice")
    quiet = _claim(_claim(quiet, "recruit"), "influence", "fremen")
    finish = DomainAction("finish_agent_turn", 0)
    while finish not in ENGINE.legal_actions(quiet, 0):
        # The space's own gains are taken first.
        row = next(
            action
            for action in ENGINE.legal_actions(quiet, 0)
            if action.action_id in ("gain", "gain_influence")
        )
        quiet = ENGINE.apply(quiet, row).state
    after = ENGINE.apply(quiet, finish).state
    assert after.players[0].troops_garrison == 3
    assert after.players[0].troops_conflict == 0
    assert dict(after.decision_stack[-1].context)["turn_owner"] != 0


# --- A recruit the supply could not give ---------------------------------------

TROOP_TRANSPORTS = ("troop_transports",)


def _after_a_short_recruit(tiles: tuple[str, ...]) -> GameState:
    """Seat 0's Agent turn at a space with no Combat icon, one troop in its
    supply, two Negotiators and nine in the garrison; the Freighter recalled
    from space 3 and its recruit taken: Troop Transports' three troops (two
    without it) of which the supply gives the one it holds."""

    state = _agent_turn(
        "wealth",
        troops_garrison=9,
        troops_supply=1,
        negotiators=2,
        tech_ids=tiles,
    )
    state = _seat(state, resources=Resources(water=2, spice=2))
    return _claim(_recalled_from(3)(state), "recruit")


def _bought_returning_both(state: GameState) -> GameState:
    """Space 3's Acquire Tech (discount 2) taking Holtzman Engine, 6 less 2 and
    less the two Negotiators it returns to the supply."""

    state = _claim(state, "tech")
    buy = DomainAction(
        "choose_tech", 0, (("negotiators", 2), ("tech_id", "holtzman_engine"))
    )
    assert buy in ENGINE.legal_actions(state, 0)
    return ENGINE.apply(state, buy).state


def _refilled(state: GameState, troops: int) -> GameState:
    """``troops`` return to seat 0's supply from its garrison and the engine's
    refill takes the shortfall from them (``shortfall.refill_shortfall``)."""

    owner = state.players[0]
    state = _seat(
        state,
        troops_supply=owner.troops_supply + troops,
        troops_garrison=owner.troops_garrison - troops,
    )
    return refill_shortfall(state, 0).state


def test_the_shortfall_of_a_troop_transports_recruit_joins_its_allowance() -> None:
    """OQ-030's re-ruling (2026-10-04): a refilled troop is "이번 turn의
    recruit이므로 turn 주인의 좌석이면 Combat 배치 몫(troops_recruited)에
    들어간다"; Troop Transports' "You may deploy any of them to the Conflict"
    lets every troop of a Shipping recruit deploy (docs/rules/rise-of-ix.md
    15). So the troops the supply could not give join that allowance when a
    later refill pays them (Codex's example): one supply troop and two
    Negotiators, a recall from space 3 on the seat's own turn at a space with no
    Combat icon recruits 1 of 3 at once, and the tile bought with both
    Negotiators makes the two refilled troops deployable too."""

    short = _after_a_short_recruit(TROOP_TRANSPORTS)
    owner = short.players[0]
    assert (owner.troops_garrison, owner.troops_supply) == (10, 0)
    assert owner.ungained_troops == 2
    assert _context_of(short)["shipping_troops_recruited"] == 1
    assert _context_of(short)["shipping_troops_ungained"] == 2
    assert _deployable(short) == [1]

    bought = _bought_returning_both(short)
    owner = bought.players[0]
    assert owner.tech_ids == ("troop_transports", "holtzman_engine")
    assert (owner.troops_garrison, owner.troops_supply, owner.negotiators) == (12, 0, 0)
    assert owner.ungained_troops == 0
    context = _context_of(bought)
    assert context["shipping_troops_recruited"] == 3
    assert "shipping_troops_ungained" not in context
    assert _deployable(bought) == [1, 2, 3]
    deployed = _deploy(bought, 3)
    assert deployed.players[0].troops_conflict == 3
    assert _deployable(deployed) == []


def test_without_troop_transports_a_refilled_recruit_gets_no_allowance() -> None:
    """Without Troop Transports nothing changes: the recall's recruit is two
    troops, the supply's one comes at once and the other waits, and the refilled
    troop is a plain recruit that cannot deploy at a space with no Combat icon
    ([FAQ p. 4]); nothing is kept on the frame."""

    short = _after_a_short_recruit(())
    assert short.players[0].ungained_troops == 1
    assert "shipping_troops_ungained" not in _context_of(short)
    assert "shipping_troops_recruited" not in _context_of(short)
    bought = _bought_returning_both(short)
    owner = bought.players[0]
    assert (owner.troops_garrison, owner.troops_supply) == (11, 1)
    assert owner.ungained_troops == 0
    assert "shipping_troops_recruited" not in _context_of(bought)
    assert "shipping_troops_ungained" not in _context_of(bought)
    assert _deployable(bought) == []


def test_a_plain_shortfall_beside_it_is_not_added_to_the_allowance() -> None:
    """Only the part of the shortfall a Shipping recruit left joins Troop
    Transports' allowance: a plain recruit the empty supply could not give
    either waits beside it and, once refilled, stays a plain recruit (no Combat
    icon, so no deployment). A partial refill takes Troop Transports' troops
    first (the documents are silent; the order follows OQ-038's, in the owner's
    favour)."""

    short = _after_a_short_recruit(TROOP_TRANSPORTS)
    owner, recruited = recruit_troops(short.players[0], 2)
    assert recruited == 0
    both = _seat(short, ungained_troops=owner.ungained_troops)
    assert both.players[0].ungained_troops == 4

    one = _refilled(both, 1)
    assert _context_of(one)["shipping_troops_recruited"] == 2
    assert _context_of(one)["shipping_troops_ungained"] == 1
    assert one.players[0].ungained_troops == 3
    three = _refilled(one, 2)
    assert _context_of(three)["shipping_troops_recruited"] == 3
    assert "shipping_troops_ungained" not in _context_of(three)
    assert three.players[0].ungained_troops == 1
    rest = _refilled(three, 1)
    assert rest.players[0].ungained_troops == 0
    assert _context_of(rest)["shipping_troops_recruited"] == 3
    assert _deployable(rest) == [1, 2, 3]


def test_the_shortfall_noted_before_the_placement_carries_over_it() -> None:
    """The recall made on the turn frame before the Agent is sent keeps both
    counts over the placement (as ``shipping_troops_recruited`` and a Harkonnen
    Advisor troop's ``undeployable_troops_ungained`` are), so a refill at a
    space with no Combat icon still gives the allowance."""

    quiet = _agent_turn(
        "wealth",
        lambda state: _claim(_recalled_from(3)(state), "recruit"),
        troops_garrison=9,
        troops_supply=1,
        negotiators=2,
        tech_ids=TROOP_TRANSPORTS,
    )
    assert _context_of(quiet)["shipping_troops_recruited"] == 1
    assert _context_of(quiet)["shipping_troops_ungained"] == 2
    assert _deployable(quiet) == [1]
    refilled = _refilled(quiet, 2)
    assert _context_of(refilled)["shipping_troops_recruited"] == 3
    assert "shipping_troops_ungained" not in _context_of(refilled)
    assert _deployable(refilled) == [1, 2, 3]


def _reveal_after_a_short_recruit(*, before_the_reveal: bool) -> GameState:
    """Seat 0's Reveal turn with Troop Transports, Freighter on space 3, one
    supply troop and two Negotiators: the recall's recruit (1 of 3) made on the
    turn frame before the Reveal, or inside the Reveal turn."""

    state = _seat(
        _start(),
        freighter_space=3,
        hand=(f"imperium:{STANDARD}:0",),
        troops_garrison=9,
        troops_supply=1,
        negotiators=2,
        tech_ids=TROOP_TRANSPORTS,
    )
    if before_the_reveal:
        state = _claim(recall_freighter(state, 0, source="s").state, "recruit")
    state = ENGINE.apply(state, DomainAction("reveal_turn", 0)).state
    assert state.decision_stack[-1].kind == FrameKind.REVEAL
    if before_the_reveal:
        return state
    return _claim(recall_freighter(state, 0, source="s").state, "recruit")


def _reveal_counts(state: GameState) -> list[int]:
    return [
        cast(int, dict(action.arguments)["count"])
        for action in ENGINE.legal_actions(state, 0)
        if action.action_id == "deploy_troops"
    ]


@pytest.mark.parametrize("before_the_reveal", [False, True])
def test_a_refilled_troop_transports_recruit_deploys_in_a_reveal_turn(
    before_the_reveal: bool,
) -> None:
    """The same in the owner's Reveal turn (docs/rules/rise-of-ix.md 15): the
    count waits on the Reveal frame, whether the recall was made inside the
    Reveal or on the turn frame before it, and the refilled troops deploy as
    "these troops" (``RECRUITS_DEPLOYABLE_KEY``) with no Combat icon."""

    state = _reveal_after_a_short_recruit(before_the_reveal=before_the_reveal)
    context = _context_of(state)
    assert context["shipping_troops_ungained"] == 2
    assert context[RECRUITS_DEPLOYABLE_KEY] == 1
    assert _reveal_counts(state) == [1]
    refilled = _refilled(state, 2)
    context = _context_of(refilled)
    assert "shipping_troops_ungained" not in context
    assert context[RECRUITS_DEPLOYABLE_KEY] == 3
    assert _reveal_counts(refilled) == [1, 2, 3]


def test_a_reveal_lines_owed_troops_come_before_troop_transports() -> None:
    """In a Reveal turn a refill goes to the ``DeployTheseTroops`` lines' owed
    troops first (OQ-140, "이 카드들 몫 먼저"), and a troop is counted once: the
    one the owed line takes does not also join Troop Transports' allowance."""

    state = _reveal_after_a_short_recruit(before_the_reveal=False)
    # One more troop owed to a line, as an empty supply leaves it.
    frame = state.decision_stack[-1]
    owing = {**dict(frame.context), RECRUITS_OWED_KEY: 1}
    state = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(owing.items()))),
        ),
    )
    state = _seat(state, ungained_troops=state.players[0].ungained_troops + 1)

    first = _refilled(state, 1)
    context = _context_of(first)
    assert context[RECRUITS_DEPLOYABLE_KEY] == 2
    assert RECRUITS_OWED_KEY not in context
    assert context["shipping_troops_ungained"] == 2
    second = _refilled(first, 2)
    context = _context_of(second)
    assert context[RECRUITS_DEPLOYABLE_KEY] == 4
    assert "shipping_troops_ungained" not in context
    assert second.players[0].ungained_troops == 0


# --- Outside the owner's turn -------------------------------------------------


def _combat() -> GameState:
    """A Combat phase with no turn open: where a Conflict reward's Freighter
    icon is gained [FAQ p. 3]."""

    state = _start()
    return replace(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != "skirmish_a"),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != "skirmish_a"
        ),
        phase=GamePhase.COMBAT,
        decision_stack=(),
        current_conflict_ids=("skirmish_a",),
        combat_intrigue_complete=False,
        combat_rewards_resolved=False,
        combat_end_triggers_offered=False,
    )


def test_a_freighter_icon_outside_the_turn_opens_its_own_window() -> None:
    """ "자기 turn 밖의 회수(Conflict 보상의 Freighter)" [Rise of Ix p. 5]
    [FAQ p. 3]: the icon opens a window with its three answers -- up (never
    from the top), recall (never from the bottom) or neither."""

    state = open_freighter_move(_seat(_combat(), freighter_space=1), 0, source="s")
    assert state.decision_stack[-1].kind == FrameKind.FREIGHTER_MOVE
    assert [a.action_id for a in ENGINE.legal_actions(state, 0)] == [
        "advance_freighter",
        "recall_freighter",
        "decline_freighter",
    ]
    top = open_freighter_move(_seat(_combat(), freighter_space=3), 0, source="s")
    assert [a.action_id for a in ENGINE.legal_actions(top, 0)] == [
        "recall_freighter",
        "decline_freighter",
    ]
    bottom = open_freighter_move(_seat(_combat(), freighter_space=0), 0, source="s")
    assert [a.action_id for a in ENGINE.legal_actions(bottom, 0)] == [
        "advance_freighter",
        "decline_freighter",
    ]

    moved = ENGINE.apply(state, DomainAction("advance_freighter", 0))
    assert moved.state.players[0].freighter_space == 2
    assert FrameKind.FREIGHTER_MOVE not in _kinds(moved.state)
    assert moved.events[0].kind == "freighter_moved"
    left = ENGINE.apply(state, DomainAction("decline_freighter", 0))
    assert left.state.players[0].freighter_space == 1
    assert left.events[0].kind == "freighter_declined"
    _round_trips(state, 0)


def test_an_out_of_turn_recall_opens_the_rewards_window() -> None:
    """ "자기 turn 밖의 회수: Tech를 얻을 수 있고 ..." [Rise of Ix p. 5]
    [FAQ p. 3]: the recall closes the Freighter window and opens the rewards
    window with the owed spaces (``ix_pending_of``), one row each in any order;
    the Acquire Tech opens on top of it at discount 2, so a Tech tile is
    acquirable, and the window closes with its last reward."""

    state = open_freighter_move(_seat(_combat(), freighter_space=3), 0, source="s")
    state = ENGINE.apply(state, DomainAction("recall_freighter", 0)).state
    assert state.players[0].freighter_space == 0
    assert state.decision_stack[-1].kind == FrameKind.SHIPPING_REWARD_ICONS
    assert _owed(state) == (1, 2, 3)
    assert {dict(row.arguments)["effect"] for row in _rows(state)} == {
        "dividends",
        "spice",
        "recruit",
        "influence",
        "tech",
    }
    _round_trips(state, 0)

    state = ENGINE.apply(
        state, DomainAction("resolve_shipping_reward", 0, (("effect", "tech"),))
    ).state
    assert state.decision_stack[-1].kind == FrameKind.TECH_ACQUISITION
    assert ix_pending_of(state, 0).tech_discount == 2
    _round_trips(state, 0)
    state = _declined(state)
    assert state.decision_stack[-1].kind == FrameKind.SHIPPING_REWARD_ICONS
    assert _owed(state) == (1, 2)

    state = _claim(state, "spice")
    state = _claim(state, "influence", "emperor")
    assert FrameKind.SHIPPING_REWARD_ICONS in _kinds(state)
    state = ENGINE.apply(
        state, DomainAction("resolve_shipping_reward", 0, (("effect", "recruit"),))
    ).state
    # The last reward closes the window (the Combat phase then moves on).
    assert FrameKind.SHIPPING_REWARD_ICONS not in _kinds(state)


def test_troops_recruited_in_combat_wait_in_the_garrison() -> None:
    """ "Combat 중에 recruit한 troop은 garrison으로 (디자이너 판정, BGG forum)"
    [Rise of Ix p. 5]: a recruit in the rewards window puts the troops in the
    garrison, with Troop Transports' extra one, and credits no turn's
    deployment (the Conflict seat's troops stay as they were)."""

    state = open_freighter_move(
        _seat(
            _combat(),
            freighter_space=2,
            troops_garrison=0,
            troops_supply=11,
            troops_conflict=1,
            tech_ids=("troop_transports",),
        ),
        0,
        source="s",
    )
    fremen = state.players[0].influence.fremen
    state = ENGINE.apply(state, DomainAction("recall_freighter", 0)).state
    state = ENGINE.apply(
        state, DomainAction("resolve_shipping_reward", 0, (("effect", "recruit"),))
    ).state
    state = ENGINE.apply(
        state,
        DomainAction(
            "resolve_shipping_reward",
            0,
            (("effect", "influence"), ("faction", "fremen")),
        ),
    ).state
    owner = state.players[0]
    assert (owner.troops_garrison, owner.troops_supply, owner.troops_conflict) == (
        3,
        8,
        1,
    )
    assert owner.influence.fremen == fremen + 1


# --- Rise of Ix only ----------------------------------------------------------


def test_nothing_changes_without_rise_of_ix() -> None:
    """The Shipping track is Rise of Ix's ([Rise of Ix p. 5]): no catalog
    without the expansion holds a Freighter or reward row, a game without it
    owes no recall reward in its observation, and the original game's Rise of
    Ix catalog holds them: the Freighter window's three rows and the reward
    rows (Dividends, spice, the recruit, the Influence for each Faction and
    without one, the Acquire Tech)."""

    names = {
        "advance_freighter",
        "recall_freighter",
        "decline_freighter",
        "resolve_shipping_reward",
    }
    assert not any(t.action_id in names for t in ActionCodec(ORIGINAL).catalog)
    ix = [t for t in ActionCodec(IX).catalog if t.action_id in names]
    assert sorted(t.action_id for t in ix) == sorted(
        [
            "advance_freighter",
            "recall_freighter",
            "decline_freighter",
            *["resolve_shipping_reward"] * 5,
            *["resolve_shipping_reward"] * len(Faction),
        ]
    )
    plain = _recalled(_at(2))
    plain = replace(
        plain, tech_stacks=(), config=replace(plain.config, rise_of_ix=False)
    )
    assert ix_pending_of(plain, 0) is NO_IX_PENDING


def test_the_rows_run_through_the_engine_and_the_codec() -> None:
    """A recall in a Combat-space Agent turn: the engine offers each reward as
    the row that names it, applies it, and every row it offers encodes and
    decodes to itself in the original game's Rise of Ix catalog."""

    state = _agent_turn(RESEARCH_STATION, troops_garrison=2, troops_supply=10)
    state = recall_freighter(_seat(state, freighter_space=2), 0, source="s").state
    _round_trips(state, 0)
    rows = _rows(state)
    assert [row.arguments for row in rows[:2]] == [
        (("effect", "dividends"),),
        (("effect", "spice"),),
    ]
    paid = ENGINE.apply(state, rows[0])
    assert paid.state.players[0].resources.solari == (
        state.players[0].resources.solari + 5
    )
    assert [e.kind for e in paid.events] == ["resources_gained"] * 4
    _round_trips(paid.state, 0)
