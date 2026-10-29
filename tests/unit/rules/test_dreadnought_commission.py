"""Rise of Ix dreadnoughts: commissioning and deploying them (stage P4b-2).

Rules: docs/rules/rise-of-ix.md 6, ``[Rise of Ix p. 6]`` and
docs/base-game-and-ix-plan.md 17.6 item 2 and 17.9 (P4b-2). Setup refuses
``rise_of_ix`` until stage P4c, so every state is the original game's round
one at seat 0's first turn with its config switched to ``rise_of_ix=True``
and its seats given the dreadnoughts by ``dataclasses.replace`` (the state
checks accept them). No card or space prints the Dreadnought icon yet (stages
P4c and P4d), so the commission goes through the executor's piece with a
hand-built ability, and the Agent turn's own checks through a commission made
on the turn frame directly.
"""

from collections.abc import Callable, MutableMapping
from dataclasses import replace
from typing import cast

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec, ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.abilities import Ability, AbilityTiming
from dune_imperium.content.uprising.effect_dsl import (
    CommissionDreadnought,
    EffectSection,
    PayResources,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules import UprisingRulesEngine, ability_executor
from dune_imperium.rules.ability_executor import (
    IN_TURN,
    STACKED,
    PendingAbility,
    ability_rows,
    apply_piece,
    current_piece,
    entry_pieces,
    piece_rows,
)
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat_deployment import (
    DEPLOYED_DREADNOUGHTS_KEY,
    WITHDRAWABLE_DREADNOUGHTS_KEY,
    apply_agent_turn_finish,
    deployment_rooms,
    legal_agent_turn_finish_actions,
    legal_combat_deployments,
    legal_dreadnought_deployments,
    legal_dreadnought_withdrawals,
    legal_troop_withdrawals,
    reconcile_deployment_after_retreat,
    settle_finishing_agent_turn,
    unit_deployment_rooms,
)
from dune_imperium.rules.dreadnought_commission import (
    commission_block,
    commission_dreadnought,
)
from dune_imperium.rules.effect_interpreter import rewards_with_no_effect
from dune_imperium.rules.effects import OptionalBlockKind
from dune_imperium.rules.frames import (
    DREADNOUGHTS_COMMISSIONED_KEY,
    FrameKind,
    credit_commissioned_dreadnoughts,
)
from dune_imperium.rules.masterstroke import masterstroke_is_due

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
DREADNOUGHT_ROWS = ("deploy_dreadnoughts", "withdraw_dreadnoughts")


def _start(*, rise_of_ix: bool = True) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an original game at seat 0's first turn, with or without
    Rise of Ix switched on."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(ORIGINAL, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, replace(state, config=replace(state.config, rise_of_ix=rise_of_ix))


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _context(state: GameState) -> dict[str, object]:
    return dict(state.decision_stack[-1].context)


def _with_standard(
    state: GameState, *, supply: int, garrison: int, **changes: object
) -> GameState:
    """Seat 0 with only Sardaukar Standard in hand (an Emperor and City card
    whose Agent box prints nothing) and ``supply`` and ``garrison``
    dreadnoughts."""

    return _seat(
        state,
        hand=(f"imperium:{STANDARD}:0",),
        resources=Resources(water=2),
        dreadnoughts_supply=supply,
        dreadnoughts_garrison=garrison,
        **changes,
    )


def _place(engine: UprisingRulesEngine, state: GameState, space_id: str) -> GameState:
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
    )
    return apply_placement(engine, state, placement).state


def _do(
    engine: UprisingRulesEngine, state: GameState, action_id: str, **arguments: object
) -> GameState:
    action = next(
        action
        for action in engine.whole_actions(state, 0)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return apply_whole(engine, state, action).state


def _turn(
    *,
    supply: int = 0,
    garrison: int = 0,
    space: str = RESEARCH_STATION,
    rise_of_ix: bool = True,
    **changes: object,
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0's Agent turn at ``space`` (a Combat space by default) with its
    printed effects still pending."""

    engine, state = _start(rise_of_ix=rise_of_ix)
    state = _with_standard(state, supply=supply, garrison=garrison, **changes)
    return engine, _place(engine, state, space)


def _settled(engine: UprisingRulesEngine, state: GameState) -> GameState:
    """The Research Station's three card draws taken, so nothing mandatory
    is left in the turn."""

    for _ in range(3):
        state = _do(engine, state, "resolve_board_effect", effect="cards")
    return state


def _commissioned(state: GameState) -> GameState:
    """Seat 0 commissions one dreadnought in its open turn."""

    return commission_dreadnought(state, 0, source="test").state


def _counts(actions: tuple[DomainAction, ...], action_id: str) -> list[int]:
    return [
        cast(int, dict(action.arguments)["count"])
        for action in actions
        if action.action_id == action_id
    ]


def _deploy(
    engine: UprisingRulesEngine, state: GameState, kind: str, count: int
) -> GameState:
    return _do(engine, state, f"deploy_{kind}", count=count)


def _withdraw(
    engine: UprisingRulesEngine, state: GameState, kind: str, count: int
) -> GameState:
    return _do(engine, state, f"withdraw_{kind}", count=count)


# --- The piece and its executor ----------------------------------------------


def _ability(icons: int) -> Ability:
    """A hand-built Plot of ``icons`` Dreadnought icons."""

    return Ability(
        AbilityTiming.PLOT,
        (EffectSection(rewards=(CommissionDreadnought(),) * icons),),
    )


@pytest.fixture
def printed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the executor read hand-built abilities for Intrigue entries: ref
    ``ix#1`` prints one icon, ``ix#2`` two, ``ix#paid`` an icon behind 3
    Solari."""

    abilities = {
        "ix#1": _ability(1),
        "ix#2": _ability(2),
        "ix#paid": Ability(
            AbilityTiming.PLOT,
            (
                EffectSection(
                    rewards=(CommissionDreadnought(),),
                    costs=(PayResources(solari=3),),
                ),
            ),
        ),
    }
    monkeypatch.setitem(
        cast(
            MutableMapping[Source, Callable[[str], Ability]],
            ability_executor._ABILITIES,
        ),
        Source.INTRIGUE,
        lambda ref: abilities[ref],
    )


def _entry(ref: str = "ix#1") -> PendingAbility:
    return PendingAbility(Source.INTRIGUE, ref, (0,))


COMMISSION = DomainAction("commission_intrigue_dreadnought", 0)
DECLINE = DomainAction("decline_intrigue_dreadnought", 0)


@pytest.mark.usefixtures("printed")
def test_a_commission_moves_a_dreadnought_from_the_supply_to_the_garrison() -> None:
    """ "Dreadnought 아이콘마다 supply의 dreadnought 하나를 garrison에
    commission할 수 있다" [Rise of Ix p. 6]: one dreadnought a taken icon,
    from the owner's supply to its garrison; a second icon is a second
    choice."""

    _, state = _start()
    state = _seat(state, dreadnoughts_supply=2)
    entry = _entry("ix#2")
    assert entry_pieces(entry) == (CommissionDreadnought(), CommissionDreadnought())
    assert COMMISSION in ability_rows(state, 0, entry, STACKED)

    first = apply_piece(state, 0, entry, COMMISSION, source="s")
    owner = first.result.state.players[0]
    assert (owner.dreadnoughts_supply, owner.dreadnoughts_garrison) == (1, 1)
    assert [(e.event_id, e.kind) for e in first.result.events] == [
        ("s:slot:0:dreadnought_commissioned", "dreadnought_commissioned")
    ]
    assert dict(first.result.events[0].payload) == {"player": 0}
    assert current_piece(first.entry) == CommissionDreadnought()

    second = apply_piece(first.result.state, 0, first.entry, COMMISSION, source="s")
    owner = second.result.state.players[0]
    assert (owner.dreadnoughts_supply, owner.dreadnoughts_garrison) == (0, 2)
    assert current_piece(second.entry) is None


@pytest.mark.usefixtures("printed")
def test_the_icon_is_a_may() -> None:
    """ "commission할 수 있다("may")" [Rise of Ix p. 6]: a frame stacked on
    the turn offers the commission and its refusal; the refusal moves
    nothing; the owner's own turn offers no refusal, and the turn's end
    lapses an icon left unused (OQ-095 (2))."""

    _, state = _start()
    state = _seat(state, dreadnoughts_supply=2)
    entry = _entry()
    assert ability_rows(state, 0, entry, STACKED) == (COMMISSION, DECLINE)
    assert ability_rows(state, 0, entry, IN_TURN) == (COMMISSION,)

    declined = apply_piece(state, 0, entry, DECLINE, source="s")
    assert declined.result.state is state
    assert [(e.event_id, e.kind) for e in declined.result.events] == [
        ("s:slot:0:dreadnought_declined", "intrigue_dreadnought_declined")
    ]
    assert current_piece(declined.entry) is None


@pytest.mark.usefixtures("printed")
def test_an_empty_supply_makes_the_icon_fizzle() -> None:
    """ "supply에 없으면 더 얻지 못한다. Dreadnought 칸은 둘이 이미 있어도
    갈 수 있고 그 아이콘만 불발한다" (디자이너 판정, BGG forum) [Rise of Ix
    p. 6]: with no dreadnought in the supply the icon has no row to take,
    only its refusal is left in a stacked frame, nothing is left in the
    owner's own turn, and the block names why. A line that pays for the icon
    is not played (OQ-113 (C)), one that does not still is."""

    _, state = _start()
    state = _seat(state, dreadnoughts_garrison=1, dreadnoughts_conflict=1)
    block = commission_block(state, 0)
    assert block is not None
    assert block.kind is OptionalBlockKind.NO_DREADNOUGHT_TO_COMMISSION
    assert ability_rows(state, 0, _entry(), STACKED) == (DECLINE,)
    assert ability_rows(state, 0, _entry(), IN_TURN) == ()
    with pytest.raises(ValueError, match="no dreadnought is left in the supply"):
        commission_dreadnought(state, 0, source="s")
    with pytest.raises(ValueError, match="no dreadnought is left in the supply"):
        apply_piece(state, 0, _entry(), COMMISSION, source="s")

    unpaid = (EffectSection(rewards=(CommissionDreadnought(),)),)
    assert rewards_with_no_effect(state, 0, unpaid) == (CommissionDreadnought(),)
    stocked = _seat(state, dreadnoughts_supply=1, dreadnoughts_garrison=0)
    assert rewards_with_no_effect(stocked, 0, unpaid) == ()
    assert commission_block(stocked, 0) is None


def test_the_executor_names_the_icon_only_for_the_sources_that_print_it() -> None:
    """The piece is named through the shape table: an Intrigue slot has its
    rows now, and a source whose icon is a later stage's (an Agent box, a
    board space) stops the executor until its rows are added."""

    _, state = _start()
    state = _seat(state, dreadnoughts_supply=1)
    rows = piece_rows(state, 0, CommissionDreadnought(), Source.INTRIGUE, refusals=True)
    assert rows == (COMMISSION, DECLINE)
    with pytest.raises(LookupError, match="templates answer recruit"):
        piece_rows(state, 0, CommissionDreadnought(), Source.AGENT_CARD, refusals=False)


# --- Recording the commission in the Agent turn --------------------------------


@pytest.mark.usefixtures("printed")
def test_a_commission_before_the_placement_follows_the_agent_to_its_space() -> None:
    """ "If you commissioned the dreadnought while sending an Agent to a Combat
    space, you may deploy it to the Conflict" [Rise of Ix p. 6]: a dreadnought
    commissioned on the turn frame (a Plot played first) is recorded there,
    and the placement carries it to the Agent-turn frame the way a recruited
    Commander is carried (OQ-070)."""

    engine, state = _start()
    state = _with_standard(state, supply=2, garrison=0)
    assert state.decision_stack[-1].kind == FrameKind.TURN
    commissioned = apply_piece(state, 0, _entry(), COMMISSION, source="s")
    on_turn = commissioned.result.state
    assert _context(on_turn)[DREADNOUGHTS_COMMISSIONED_KEY] == 1

    placed = _place(engine, on_turn, RESEARCH_STATION)
    assert placed.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _context(placed)[DREADNOUGHTS_COMMISSIONED_KEY] == 1
    assert _counts(legal_dreadnought_deployments(placed, 0), "deploy_dreadnoughts") == [
        1
    ]


def test_a_commission_in_the_agent_turn_is_recorded_on_its_frame() -> None:
    """ "Dreadnought 아이콘마다 ... commission" [Rise of Ix p. 6]: each icon
    taken in the Agent turn adds one to the turn frame's count, which the
    deployment reads, and no other counter moves."""

    _, state = _turn(supply=2)
    assert DREADNOUGHTS_COMMISSIONED_KEY not in _context(state)
    one = _commissioned(state)
    assert _context(one)[DREADNOUGHTS_COMMISSIONED_KEY] == 1
    two = _commissioned(one)
    assert _context(two)[DREADNOUGHTS_COMMISSIONED_KEY] == 2
    assert two.players[0].dreadnoughts_garrison == 2
    assert two.players[0].dreadnoughts_supply == 0
    assert two.players[0].units_deployed_turn == 0
    assert _context(two)["troops_recruited"] == 0


def test_a_commission_outside_the_owners_agent_turn_is_not_recorded() -> None:
    """A Reveal turn has no deployment of a dreadnought, and another seat's
    turn is not the owner's: "If you commissioned the dreadnought while
    sending an Agent to a Combat space" [Rise of Ix p. 6]. The dreadnought
    still moves to the garrison, the turn keeps no count."""

    engine, state = _start()
    state = _seat(
        _with_standard(state, supply=2, garrison=0),
        1,
        dreadnoughts_supply=2,
    )
    revealed = _do(engine, state, "reveal_turn")
    assert revealed.decision_stack[-1].kind == FrameKind.REVEAL
    result = commission_dreadnought(revealed, 0, source="test")
    assert result.state.players[0].dreadnoughts_garrison == 1
    assert DREADNOUGHTS_COMMISSIONED_KEY not in _context(result.state)
    assert legal_dreadnought_deployments(result.state, 0) == ()

    other = commission_dreadnought(state, 1, source="test")
    assert other.state.players[1].dreadnoughts_garrison == 1
    assert DREADNOUGHTS_COMMISSIONED_KEY not in _context(other.state)
    assert credit_commissioned_dreadnoughts(state, 1, 1) is state


# --- Deploying a dreadnought ----------------------------------------------------


def test_a_commissioned_dreadnought_deploys_outside_the_garrison_two() -> None:
    """ "You may deploy any or all units recruited during your current turn
    ... plus up to two more units from your garrison" and "If you
    commissioned the dreadnought while sending an Agent to a Combat space,
    you may deploy it to the Conflict" [Rise of Ix p. 6]: the dreadnought
    commissioned this turn has a slot of its own, so the two garrison troops
    still deploy beside it; it moves from the garrison to the Conflict at 3
    strength."""

    engine, state = _turn(supply=1)
    assert legal_dreadnought_deployments(state, 0) == ()
    state = _commissioned(state)
    assert _counts(legal_dreadnought_deployments(state, 0), "deploy_dreadnoughts") == [
        1
    ]
    assert _counts(legal_combat_deployments(state, 0), "deploy_troops") == [1, 2]

    deployed = _deploy(engine, state, "dreadnoughts", 1)
    owner = deployed.players[0]
    assert (owner.dreadnoughts_garrison, owner.dreadnoughts_conflict) == (0, 1)
    assert owner.combat_strength == 3
    context = _context(deployed)
    assert context[DEPLOYED_DREADNOUGHTS_KEY] == 1
    assert context[WITHDRAWABLE_DREADNOUGHTS_KEY] == 1
    # Its own slot took it: both garrison troops still deploy.
    assert _counts(legal_combat_deployments(deployed, 0), "deploy_troops") == [1, 2]
    assert legal_dreadnought_deployments(deployed, 0) == ()
    both = _deploy(engine, deployed, "troops", 2)
    assert both.players[0].troops_conflict == 2
    assert both.players[0].combat_strength == 3 + 2 * 2


def test_a_second_dreadnought_uses_the_garrison_share() -> None:
    """ "...plus up to two more units from your garrison" [Rise of Ix p. 6]:
    a dreadnought already in the garrison, and the commissioned one past its
    own slot, take the garrison two, which the troops share
    (docs/base-game-and-ix-plan.md 17.6 item 2)."""

    engine, state = _turn(supply=1, garrison=1)
    state = _commissioned(state)
    assert state.players[0].dreadnoughts_garrison == 2
    assert _counts(legal_dreadnought_deployments(state, 0), "deploy_dreadnoughts") == [
        1,
        2,
    ]
    both = _deploy(engine, state, "dreadnoughts", 2)
    assert both.players[0].dreadnoughts_conflict == 2
    assert both.players[0].combat_strength == 6
    # One dreadnought used the slot, the other a garrison place: one place
    # is left to a troop, and none to a third unit.
    assert _counts(legal_combat_deployments(both, 0), "deploy_troops") == [1]
    one_troop = _deploy(engine, both, "troops", 1)
    assert legal_combat_deployments(one_troop, 0) == ()
    assert legal_dreadnought_deployments(one_troop, 0) == ()


def test_the_garrison_two_are_shared_by_troops_and_dreadnoughts() -> None:
    """ "...up to two more units from your garrison" [Rise of Ix p. 6]
    (OQ-070's garrison share, widened to the third kind): with no dreadnought
    commissioned this turn, a garrison dreadnought and a garrison troop are
    the limit, and a third garrison unit of either kind is refused."""

    engine, state = _turn(garrison=2)
    assert _counts(legal_dreadnought_deployments(state, 0), "deploy_dreadnoughts") == [
        1,
        2,
    ]
    assert _counts(legal_combat_deployments(state, 0), "deploy_troops") == [1, 2]

    one = _deploy(engine, state, "dreadnoughts", 1)
    assert _counts(legal_dreadnought_deployments(one, 0), "deploy_dreadnoughts") == [1]
    assert _counts(legal_combat_deployments(one, 0), "deploy_troops") == [1]

    full = _deploy(engine, one, "troops", 1)
    assert legal_dreadnought_deployments(full, 0) == ()
    assert legal_combat_deployments(full, 0) == ()
    assert full.players[0].dreadnoughts_garrison == 1
    assert full.players[0].troops_garrison >= 1
    assert not any(
        action.action_id in ("deploy_dreadnoughts", "deploy_troops")
        for action in engine.legal_actions(full, 0)
    )
    third = DomainAction("deploy_dreadnoughts", 0, (("count", 1),))
    with pytest.raises(ValueError):
        engine.apply(full, third)


def test_a_withdrawal_returns_the_kind_it_names() -> None:
    """ "...plus up to two more units from your garrison" [Rise of Ix p. 6]
    with OQ-029's adjustable deployment: a withdrawal undoes one kind's
    deployment only, and gives that kind's room back."""

    engine, state = _turn(garrison=1)
    both = _deploy(engine, _deploy(engine, state, "dreadnoughts", 1), "troops", 1)
    owner = both.players[0]
    assert (owner.troops_conflict, owner.dreadnoughts_conflict) == (1, 1)
    assert _counts(legal_dreadnought_withdrawals(both, 0), "withdraw_dreadnoughts") == [
        1
    ]
    assert _counts(legal_troop_withdrawals(both, 0), "withdraw_troops") == [1]

    back = _withdraw(engine, both, "dreadnoughts", 1)
    owner = back.players[0]
    assert (owner.troops_conflict, owner.dreadnoughts_conflict) == (1, 0)
    assert owner.dreadnoughts_garrison == 1
    assert owner.combat_strength == 2
    assert legal_dreadnought_withdrawals(back, 0) == ()
    assert _counts(legal_troop_withdrawals(back, 0), "withdraw_troops") == [1]
    assert _counts(legal_dreadnought_deployments(back, 0), "deploy_dreadnoughts") == [1]
    assert _context(back)[DEPLOYED_DREADNOUGHTS_KEY] == 0

    troop_back = _withdraw(engine, both, "troops", 1)
    assert troop_back.players[0].dreadnoughts_conflict == 1
    assert troop_back.players[0].troops_conflict == 0


def test_only_this_turns_dreadnoughts_may_be_withdrawn() -> None:
    """The withdrawal undoes "this turn's" deployment (OQ-029): a dreadnought
    already in the Conflict from an earlier turn is not offered, and a retreat
    ("Each kind's withdrawable share shrinks only by its own retreated
    units", OQ-070) takes the retreated dreadnought out of the share too."""

    engine, state = _turn(garrison=1, dreadnoughts_conflict=1)
    assert legal_dreadnought_withdrawals(state, 0) == ()
    deployed = _deploy(engine, state, "dreadnoughts", 1)
    assert deployed.players[0].dreadnoughts_conflict == 2
    assert _counts(
        legal_dreadnought_withdrawals(deployed, 0), "withdraw_dreadnoughts"
    ) == [1]

    retreated = _seat(deployed, dreadnoughts_conflict=1, dreadnoughts_garrison=1)
    after = reconcile_deployment_after_retreat(retreated, 0, troops=0, dreadnoughts=1)
    assert _context(after)[WITHDRAWABLE_DREADNOUGHTS_KEY] == 0
    assert legal_dreadnought_withdrawals(after, 0) == ()
    # The allowance does not come back with the retreat (OQ-029): the
    # deployed count stays.
    assert _context(after)[DEPLOYED_DREADNOUGHTS_KEY] == 1
    # A retreat of a troop leaves the dreadnoughts' share alone.
    untouched = reconcile_deployment_after_retreat(deployed, 0, troops=1)
    assert _context(untouched)[WITHDRAWABLE_DREADNOUGHTS_KEY] == 1


def test_a_commission_outside_a_combat_turn_cannot_be_deployed() -> None:
    """ "Combat 칸에 Agent를 보낸 turn이면 Conflict에 배치할 수 있다"
    (docs/rules/rise-of-ix.md 6, [Rise of Ix p. 6]): at a space with no
    Combat icon there is no deployment, so neither the dreadnought
    commissioned this turn nor one already in the garrison may deploy."""

    engine, state = _turn(supply=1, garrison=1, space="wealth")
    assert _context(state)["pending_combat_deployment"] is False
    state = _commissioned(state)
    assert _context(state)[DREADNOUGHTS_COMMISSIONED_KEY] == 1
    assert state.players[0].dreadnoughts_garrison == 2
    assert legal_dreadnought_deployments(state, 0) == ()
    assert legal_dreadnought_withdrawals(state, 0) == ()
    assert not any(
        action.action_id in ("deploy_dreadnoughts", "deploy_troops")
        for action in engine.legal_actions(state, 0)
    )


def test_a_game_without_rise_of_ix_offers_no_dreadnought_row() -> None:
    """The Dreadnought rules are Rise of Ix's ([Rise of Ix p. 6]): an original
    game without the expansion offers no dreadnought row, even to a seat
    holding one, and the two-kind rooms are what they were."""

    engine, state = _turn(garrison=1, rise_of_ix=False)
    assert _counts(legal_combat_deployments(state, 0), "deploy_troops") == [1, 2]
    assert legal_dreadnought_deployments(state, 0) == ()
    assert legal_dreadnought_withdrawals(state, 0) == ()
    assert not any(
        action.action_id in DREADNOUGHT_ROWS
        for action in engine.legal_actions(state, 0)
    )
    for recruited in range(3):
        for deployed in range(4):
            for commanders in range(3):
                for commanders_deployed in range(3):
                    for limit in range(3):
                        two = deployment_rooms(
                            troops_recruited=recruited,
                            commanders_recruited=commanders,
                            existing_limit=limit,
                            troops_deployed=deployed,
                            commanders_deployed=commanders_deployed,
                        )
                        three = unit_deployment_rooms(
                            recruited=(recruited, commanders, 0),
                            deployed=(deployed, commanders_deployed, 0),
                            existing_limit=limit,
                        )
                        assert two == three[:2]
    assert not any(
        template.action_id in DREADNOUGHT_ROWS or "dreadnought" in template.action_id
        for config in (
            RulesetConfig(base_game=BaseGame.IMPERIUM),
            RulesetConfig(base_game=BaseGame.IMPERIUM, promo_cards=True),
            RulesetConfig(),
            RulesetConfig(bloodlines=True, immortality=True),
        )
        for template in ActionCodec(config).catalog
        if template.action_id != "place_combat_reward_dreadnought"
    )


def test_the_unit_rooms_give_each_kind_its_slot_and_share_the_garrison_two() -> None:
    """ "...units recruited during your current turn ..., plus up to two more
    units from your garrison" [Rise of Ix p. 6]: each kind's own recruited
    slots first, then the garrison share of two for any kind."""

    rooms = unit_deployment_rooms
    assert rooms(recruited=(0, 0, 0), deployed=(0, 0, 0), existing_limit=2) == (2, 2, 2)
    assert rooms(recruited=(0, 0, 1), deployed=(0, 0, 0), existing_limit=2) == (2, 2, 3)
    assert rooms(recruited=(0, 0, 1), deployed=(0, 0, 1), existing_limit=2) == (2, 2, 2)
    assert rooms(recruited=(0, 0, 1), deployed=(0, 0, 2), existing_limit=2) == (1, 1, 1)
    # One unit past its slot takes one of the two places, two take both.
    assert rooms(recruited=(1, 1, 1), deployed=(2, 1, 1), existing_limit=2) == (
        1,
        1,
        1,
    )
    assert rooms(recruited=(1, 1, 1), deployed=(2, 1, 2), existing_limit=2) == (
        0,
        0,
        0,
    )
    assert rooms(recruited=(0, 0, 0), deployed=(1, 1, 0), existing_limit=2) == (
        0,
        0,
        0,
    )
    assert rooms(recruited=(0, 0, 0), deployed=(0, 0, 0), existing_limit=0) == (0, 0, 0)


# --- What a dreadnought does not touch -------------------------------------------


def test_the_masterstroke_does_not_count_a_dreadnought() -> None:
    """ "When you deploy 4+ troops to the Conflict in a turn" [Baron Vladimir
    Harkonnen card]; Baron Harkonnen's row of docs/rules/rise-of-ix.md 6's
    table: the dreadnought is not a troop ("원판 카드의 'troop'은 유닛을
    뜻하지 않아 dreadnought에 작용하지 않는다" [Rise of Ix p. 6]). Two
    dreadnoughts and two troops stand in the Conflict, yet the turn's troop
    count, peak and floor read 2 and the Masterstroke stays hidden."""

    engine, state = _start()
    state = _with_standard(
        state,
        supply=1,
        garrison=1,
        masterstroke_factions=("emperor", "fremen"),
    )
    state = _place(engine, state, "arrakeen")
    state = _do(engine, state, "resolve_board_effect", effect="troops")
    state = _commissioned(state)
    assert _context(state)["troops_recruited"] == 1
    assert state.players[0].dreadnoughts_garrison == 2

    state = _deploy(engine, state, "dreadnoughts", 2)
    state = _deploy(engine, state, "troops", 2)
    owner = state.players[0]
    assert (owner.dreadnoughts_conflict, owner.troops_conflict) == (2, 2)
    assert owner.units_in_conflict == 4
    assert owner.units_deployed_turn == 2
    assert owner.units_deployed_peak == 2
    assert owner.units_deployed_committed == 0
    assert not owner.masterstroke_revealed
    assert not masterstroke_is_due(state, 0)

    # A third troop is what makes it four troops: the Masterstroke is due
    # with the dreadnoughts' count untouched.
    troops_only = _seat(state, units_deployed_turn=4, units_deployed_peak=4)
    assert masterstroke_is_due(troops_only, 0)


def test_a_dreadnought_withdrawal_leaves_the_troop_floor_alone() -> None:
    """The floor a played card used (Distraction, Coercive Negotiation) bounds
    the troops' withdrawal ([Distraction card], OQ-029) and never a
    dreadnought's: a dreadnought is no troop (docs/rules/rise-of-ix.md 6)."""

    engine, state = _turn(garrison=1)
    state = _deploy(engine, state, "dreadnoughts", 1)
    committed = _seat(state, units_deployed_committed=3)
    assert _counts(
        legal_dreadnought_withdrawals(committed, 0), "withdraw_dreadnoughts"
    ) == [1]
    back = _withdraw(engine, committed, "dreadnoughts", 1)
    owner = back.players[0]
    assert (owner.units_deployed_turn, owner.units_deployed_peak) == (0, 0)
    assert owner.units_deployed_committed == 3


# --- The turn's end -------------------------------------------------------------


def test_the_turn_end_is_offered_beside_the_dreadnought_rows() -> None:
    """The deployment window stays open until the one press (OQ-029,
    OQ-095): a dreadnought left in the garrison holds no end back, and the
    withdrawal comes last of the rows (a "first legal action" walk
    deploys and finishes instead of cycling)."""

    engine, state = _turn(supply=1, garrison=1)
    state = _commissioned(_settled(engine, state))
    legal = engine.legal_actions(state, 0)
    ids = [action.action_id for action in legal]
    assert ids.count("deploy_dreadnoughts") == 2
    assert "finish_agent_turn" in ids
    assert ids.index("deploy_dreadnoughts") < ids.index("finish_agent_turn")

    deployed = _deploy(engine, state, "dreadnoughts", 1)
    ids = [action.action_id for action in engine.legal_actions(deployed, 0)]
    assert ids[-1] == "withdraw_dreadnoughts"
    assert "finish_agent_turn" in ids

    pressed = engine.apply(deployed, DomainAction("finish_agent_turn", 0)).state
    assert pressed.players[0].dreadnoughts_conflict == 1
    assert pressed.decision_stack[-1].kind == FrameKind.TURN
    assert DREADNOUGHTS_COMMISSIONED_KEY not in _context(pressed)


def test_a_commission_made_by_the_press_reopens_the_turn_for_its_deployment() -> None:
    """ "If you commissioned the dreadnought while sending an Agent to a Combat
    space, you may deploy it to the Conflict" [Rise of Ix p. 6]: a dreadnought
    the end press's own steps commissioned is the turn's too, so the turn
    reopens for its deployment, as for a troop or a Commander recruited
    then (OQ-029, OQ-095 (5)). With nothing to deploy it closes."""

    engine, state = _turn(supply=1, troops_garrison=0, troops_supply=12)
    settled = _settled(engine, state)
    assert legal_combat_deployments(settled, 0) == ()
    finish = DomainAction("finish_agent_turn", 0)
    assert finish in legal_agent_turn_finish_actions(settled, 0)
    pressed = apply_agent_turn_finish(settled, finish)
    assert _context(pressed.state)["finishing"] is True

    commissioned = commission_dreadnought(pressed.state, 0, source="press")
    settled_again = settle_finishing_agent_turn(
        RuleResult(state=commissioned.state, events=commissioned.events)
    )
    assert settled_again.state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert "finishing" not in _context(settled_again.state)
    assert [e.kind for e in settled_again.events][-1] == "agent_turn_reopened"
    assert _counts(
        legal_dreadnought_deployments(settled_again.state, 0), "deploy_dreadnoughts"
    ) == [1]

    nothing = settle_finishing_agent_turn(RuleResult(state=pressed.state))
    assert nothing.state.decision_stack[-1].kind == FrameKind.TURN


# --- The engine and the codec ---------------------------------------------------


def test_the_rows_run_through_the_engine_and_the_codec() -> None:
    """ "If you commissioned the dreadnought while sending an Agent to a Combat
    space, you may deploy it to the Conflict" [Rise of Ix p. 6]: the engine
    offers the deployment rows of a commissioned dreadnought in the Agent turn,
    applies them, and every row it offers encodes and decodes to itself in the
    original game's Rise of Ix catalog."""

    engine, state = _turn(supply=2)
    state = _commissioned(_settled(engine, state))
    codec = ActionCodec(state.config)

    def round_trip(actions: tuple[DomainAction, ...]) -> None:
        assert actions
        for action in actions:
            assert codec.decode(codec.encode(action), action.actor) == action

    legal = engine.legal_actions(state, 0)
    deploys = tuple(a for a in legal if a.action_id == "deploy_dreadnoughts")
    assert deploys == (DomainAction("deploy_dreadnoughts", 0, (("count", 1),)),)
    round_trip(legal)

    deployed = engine.apply(state, deploys[0]).state
    assert deployed.players[0].dreadnoughts_conflict == 1
    assert deployed.players[0].combat_strength == 3
    legal = engine.legal_actions(deployed, 0)
    withdraws = tuple(a for a in legal if a.action_id == "withdraw_dreadnoughts")
    assert withdraws == (DomainAction("withdraw_dreadnoughts", 0, (("count", 1),)),)
    round_trip(legal)

    undone = engine.apply(deployed, withdraws[0]).state
    assert undone.players[0].dreadnoughts_garrison == 1
    assert undone.players[0].combat_strength == 0
    assert [e.kind for e in engine.apply(deployed, withdraws[0]).events] == [
        "dreadnoughts_withdrawn"
    ]
    assert [e.kind for e in engine.apply(state, deploys[0]).events] == [
        "dreadnoughts_deployed"
    ]


def test_only_a_rise_of_ix_catalog_holds_the_dreadnought_rows() -> None:
    """The dreadnought is Rise of Ix's ([Rise of Ix p. 6]): the deploy and
    withdraw rows (one per dreadnought a seat has) are in the original game's
    Rise of Ix catalogs, and the Intrigue slot's commission and refusal are
    shown by the cards that print them (none yet), so no catalog holds their
    whole rows."""

    ix = ActionCodec(IX).catalog
    for action_id in DREADNOUGHT_ROWS:
        assert {t for t in ix if t.action_id == action_id} == {
            ActionTemplate(action_id, (("count", count),)) for count in (1, 2)
        }
    assert not any(
        t.action_id
        in ("commission_intrigue_dreadnought", "decline_intrigue_dreadnought")
        for t in ix
    )
