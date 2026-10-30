"""Rise of Ix Tech tiles: the acquisition framework on Ix's stacks (stage P4c-1).

Rules: docs/rules/rise-of-ix.md 4 ("Tech tile"), ``[Rise of Ix p. 4]``
``[FAQ p. 4]`` and docs/base-game-and-ix-plan.md 17.10 item 1. Written before
setup took ``rise_of_ix`` (stage P4c-5), every state here is the original
game's round one at seat 0's first turn with its config switched to
``rise_of_ix=True`` and Ix's tiles laid on ``tech_stacks`` by
``dataclasses.replace`` (the state checks accept them). No space or card
prints the Acquire Tech or Tech Negotiation icon yet (stages P4c-4 and P4d),
so the icons go through the executor with hand-built abilities, and an open
acquisition is pushed as the frame an icon opens.
"""

from collections.abc import Callable, MutableMapping
from dataclasses import replace
from typing import cast

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec, ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.bloodlines.tech import TECH_IDS, TECH_TILES_BY_ID
from dune_imperium.content.rise_of_ix.tech import IX_TECH_IDS, IX_TECH_TILES_BY_ID
from dune_imperium.content.uprising.abilities import Ability, AbilityTiming
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTech,
    EffectSection,
    PlaceNegotiator,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.core.observation import (
    NEGOTIATORS_RETURNABLE_KEY,
    NO_IX_PENDING,
    IxPending,
    ix_negotiators_returnable,
    ix_pending_of,
)
from dune_imperium.rules import UprisingRulesEngine, ability_executor
from dune_imperium.rules import tech as tech_rules
from dune_imperium.rules.ability_executor import (
    IN_TURN,
    STACKED,
    PendingAbility,
    ability_rows,
    apply_automatic_rewards,
    apply_piece,
    current_piece,
    entry_pieces,
    piece_rows,
)
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.effect_interpreter import rewards_with_no_effect
from dune_imperium.rules.effects import BOARD_ICON_TECH, OptionalBlockKind
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.negotiators import negotiator_block, place_negotiator
from dune_imperium.rules.optional_trash import optional_trash_frame, trash_printer
from dune_imperium.rules.setup import deal_ix_tech_stacks
from dune_imperium.rules.tech import (
    ix_tech_cost,
    landsraad_tech_block,
    legal_tech_acquisition_actions,
    push_tech_acquisition,
    tech_acquisition_possible,
)
from dune_imperium.simulation.invariants import (
    CardCensus,
    InvariantViolation,
    check_state_invariants,
)

LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
# A card's refusal names its printer (stage B3d-3). The frames here are an
# icon's "may", so they borrow the Dreadnought space's: an Intrigue card's
# icon (Machine Culture's) is no "may" while a tile is in reach, see
# ``test_ix_intrigue_e.py`` (designer ruling, OQ-057 (9)).
PRINTER = printer_value(Source.BOARD_SPACE, "dreadnought")
# Costs: Detonation Devices 3, Artillery 1, Chaumurky 4 | Holtzman Engine 6,
# Invasion Ships 5, Memocorders 2 | Restricted Ordnance 4, Minimic Film 2,
# Flagship 8.
STACKS = (
    ("detonation_devices", "artillery", "chaumurky"),
    ("holtzman_engine", "invasion_ships", "memocorders"),
    ("restricted_ordnance", "minimic_film", "flagship"),
)


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


def _with_stacks(
    state: GameState, stacks: tuple[tuple[str, ...], ...] = STACKS
) -> GameState:
    return replace(state, tech_stacks=stacks)


def _holding(
    *, spice: int, negotiators: int = 0, stacks: tuple[tuple[str, ...], ...] = STACKS
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 with ``spice`` and ``negotiators`` (taken from its supply)."""

    engine, state = _start()
    owner = state.players[0]
    state = _seat(
        state,
        resources=replace(owner.resources, spice=spice),
        troops_supply=owner.troops_supply - negotiators,
        negotiators=negotiators,
    )
    return engine, _with_stacks(state, stacks)


def _open(state: GameState, discount: int = 0) -> GameState:
    """The acquisition an Acquire Tech icon of ``discount`` opens for seat 0."""

    return push_tech_acquisition(
        state, 0, discount=discount, source="s", printer=PRINTER
    ).state


def _buy(tech_id: str, negotiators: int = 0) -> DomainAction:
    arguments: tuple[tuple[str, int | str], ...] = (("tech_id", tech_id),)
    if negotiators:
        arguments = (("negotiators", negotiators), *arguments)
    return DomainAction("acquire_tech", 0, arguments)


DECLINE = DomainAction("decline_tech", 0)


def _context(state: GameState) -> dict[str, object]:
    return dict(state.decision_stack[-1].context)


def _offered(state: GameState) -> list[tuple[str, int]]:
    """(tile, Negotiators returned) of every purchase the frame offers."""

    return [
        (
            cast(str, dict(action.arguments)["tech_id"]),
            cast(int, dict(action.arguments).get("negotiators", 0)),
        )
        for action in legal_tech_acquisition_actions(state, 0)
        if action.action_id == "acquire_tech"
    ]


def _take(state: GameState, action: DomainAction) -> tuple[GameState, list[str]]:
    result = tech_rules.apply_tech_acquisition(state, action)
    return result.state, [event.kind for event in result.events]


# --- The Acquire Tech icon ----------------------------------------------------


def test_an_acquisition_pays_the_cost_less_the_discount_and_flips_the_next_tile() -> (
    None
):
    """ "아이콘마다 Ix board의 세 더미 맨 위 앞면 타일 하나를 얻을 수 있다.
    spice 비용을 내고 supply에 공개로 두고, 그 더미의 다음 타일을 앞면으로
    뒤집는다" and "Tech Discount: −1·−2가 붙은 Acquire Tech 아이콘은 그 한 번의
    구매를 깎는다" [Rise of Ix p. 4]: Detonation Devices (3 spice) at a
    discount of 1 costs 2; it goes to the seat's supply of tiles, and the
    stack's next tile, Artillery, is the face-up top."""

    _, state = _holding(spice=5)
    state = _open(state, discount=1)
    after, kinds = _take(state, _buy("detonation_devices"))

    owner = after.players[0]
    assert owner.resources.spice == 3
    assert owner.tech_ids == ("detonation_devices",)
    assert after.tech_stacks[0] == ("artillery", "chaumurky")
    assert tech_rules.face_up_tech_ids(after) == (
        "artillery",
        "holtzman_engine",
        "restricted_ordnance",
    )
    assert after.decision_stack == state.decision_stack[:-1]
    assert kinds == ["tech_acquired", "tech_revealed"]


def test_the_acquisition_events_say_what_was_paid_and_returned() -> None:
    """The ``tech_acquired`` event names the tile, the spice paid and the
    Negotiators returned (a Rise of Ix game only; the Tech Module's event is
    as it was) [Rise of Ix p. 4]."""

    _, state = _holding(spice=5, negotiators=1)
    result = tech_rules.apply_tech_acquisition(
        _open(state, discount=1), _buy("detonation_devices", 1)
    )
    first, second = result.events
    assert dict(first.payload) == {
        "negotiators": 1,
        "player": 0,
        "secret_project": False,
        "spice": 1,
        "tech_id": "detonation_devices",
    }
    assert (second.kind, dict(second.payload)) == (
        "tech_revealed",
        {"stack": 0, "tech_id": "artillery"},
    )


def test_the_cost_never_drops_below_nothing() -> None:
    """ "비용은 0보다 낮아지지 않는다" [Rise of Ix p. 4]: a discount of 2 on
    Artillery (1 spice) leaves it free, and spice is not gained back."""

    _, state = _holding(spice=0)
    artillery = IX_TECH_TILES_BY_ID["artillery"]
    owner = state.players[0]
    assert ix_tech_cost(owner, artillery, discount=2, negotiators=0) == 0
    assert ix_tech_cost(owner, artillery, discount=0, negotiators=3) == 0

    stacks = (("artillery", "chaumurky"), STACKS[1], STACKS[2])
    _, state = _holding(spice=2, stacks=stacks)
    state = _open(state, discount=2)
    after, _ = _take(state, _buy("artillery"))
    assert after.players[0].resources.spice == 2
    assert after.players[0].tech_ids == ("artillery",)


def test_a_discount_is_for_its_own_purchase_and_icons_do_not_add_up() -> None:
    """ "그 한 번의 구매를 깎는다. 여러 아이콘의 할인은 합치지 못한다"
    [Rise of Ix p. 4]: two Acquire Tech icons of discount 1 are two purchases
    of 1 off each, never one purchase 2 off; the cheapest price a frame offers
    is its own tile's cost less its own discount."""

    _, state = _holding(spice=9)
    state = _open(_open(state, discount=1), discount=1)
    assert [frame.kind for frame in state.decision_stack[-2:]] == [
        FrameKind.TECH_ACQUISITION
    ] * 2

    first, _ = _take(state, _buy("holtzman_engine"))
    assert first.players[0].resources.spice == 4  # 9 - (6 - 1)
    assert _context(first)["tech_discount"] == 1
    second, _ = _take(first, _buy("restricted_ordnance"))
    assert second.players[0].resources.spice == 1  # 4 - (4 - 1)
    assert second.players[0].tech_ids == ("holtzman_engine", "restricted_ordnance")
    assert second.decision_stack == state.decision_stack[:-2]


def test_the_discount_is_not_a_choice() -> None:
    """ "'may'가 없으므로 의무 할인이다" (OQ-104의 원칙) [Rise of Ix p. 4]: no
    row buys a tile at the cost without the discount; a seat with exactly the
    discounted price can buy and one with a spice less cannot."""

    _, state = _holding(spice=1)
    # Detonation Devices (3) at a discount of 2 is 1 spice.
    assert ("detonation_devices", 0) in _offered(_open(state, discount=2))
    _, poor = _holding(spice=0)
    assert ("detonation_devices", 0) not in _offered(_open(poor, discount=2))
    # A seat that could pay more is not asked to: the one row of the tile
    # pays the discounted price.
    rich = _open(_holding(spice=9)[1], discount=2)
    (event, _) = tech_rules.apply_tech_acquisition(
        rich, _buy("detonation_devices")
    ).events
    assert dict(event.payload)["spice"] == 1


def test_negotiators_returned_lower_the_cost_one_each_with_the_discount() -> None:
    """ "원하는 만큼("any number") Negotiator를 supply로 돌려 하나에 spice
    1씩 깎는다. Tech Discount와 합칠 수 있다" [Rise of Ix p. 4]: Holtzman
    Engine (6) at a discount of 1 and three Negotiators returned costs 2; the
    Negotiators go back to the supply, which keeps the seat's 12 troops."""

    _, state = _holding(spice=2, negotiators=3)
    supply = state.players[0].troops_supply
    state = _open(state, discount=1)
    assert _offered(state) == [
        ("detonation_devices", 0),
        ("detonation_devices", 1),
        ("detonation_devices", 2),
        ("holtzman_engine", 3),
        ("restricted_ordnance", 1),
        ("restricted_ordnance", 2),
        ("restricted_ordnance", 3),
    ]
    after, _ = _take(state, _buy("holtzman_engine", 3))

    owner = after.players[0]
    assert owner.resources.spice == 0
    assert (owner.negotiators, owner.troops_supply) == (0, supply + 3)
    assert owner.tech_ids == ("holtzman_engine",)
    assert after.tech_stacks[1] == ("invasion_ships", "memocorders")


def test_only_the_negotiators_that_still_lower_the_cost_are_offered() -> None:
    """ "Negotiator ... 하나에 spice 1씩 깎는다" [Rise of Ix p. 4], from none
    up to the fewest of those held and what the tile still costs: Artillery
    (1) at no discount takes at most one, a tile the discount makes free
    takes none, and a seat with one Negotiator never sees two."""

    stacks = (("artillery", "chaumurky"), ("memocorders", "minimic_film"), ())
    _, state = _holding(spice=9, negotiators=5, stacks=stacks)
    assert _offered(_open(state)) == [
        ("artillery", 0),
        ("artillery", 1),
        ("memocorders", 0),
        ("memocorders", 1),
        ("memocorders", 2),
    ]
    assert _offered(_open(state, discount=2)) == [("artillery", 0), ("memocorders", 0)]
    _, one = _holding(spice=9, negotiators=1, stacks=stacks)
    assert ("memocorders", 2) not in _offered(_open(one))


def test_negotiators_can_make_up_the_price_the_spice_does_not_reach() -> None:
    """A seat with 1 spice and 2 Negotiators reaches Memocorders (2): the
    rows that return too few for its spice are not offered, and the rows that
    return more than needed are (a Negotiator beyond the price is simply not
    among them) [Rise of Ix p. 4]."""

    stacks = (("memocorders", "artillery"), (), ())
    _, state = _holding(spice=1, negotiators=2, stacks=stacks)
    assert _offered(_open(state)) == [("memocorders", 1), ("memocorders", 2)]
    _, none = _holding(spice=0, negotiators=1, stacks=stacks)
    assert _offered(_open(none)) == []


def test_declining_leaves_everything_as_it_was() -> None:
    """ "얻을 수 있다("may")" [Rise of Ix p. 4]: the refusal is always offered,
    first, with a tile the seat can pay for or not; taking it moves nothing and
    closes the frame."""

    _, state = _holding(spice=9, negotiators=2)
    open_state = _open(state)
    assert legal_tech_acquisition_actions(open_state, 0)[0] == DECLINE
    after, kinds = _take(open_state, DECLINE)
    assert kinds == ["tech_declined"]
    assert after.players == state.players
    assert after.tech_stacks == state.tech_stacks
    assert after.decision_stack == state.decision_stack

    _, empty = _holding(spice=0, stacks=((), (), ()))
    assert legal_tech_acquisition_actions(_open(empty), 0) == (DECLINE,)


def test_an_empty_stack_offers_nothing() -> None:
    """ "더미가 비면 고를 것이 줄 뿐이다" [Rise of Ix p. 4]: a stack with no
    tile is passed over, taking a stack's last tile reveals nothing, and with
    every stack empty the acquisition offers only its refusal."""

    stacks = (("artillery",), (), ("minimic_film", "flagship"))
    _, state = _holding(spice=9, stacks=stacks)
    state = _open(state)
    assert _offered(state) == [("artillery", 0), ("minimic_film", 0)]
    after, kinds = _take(state, _buy("artillery"))
    assert after.tech_stacks == ((), (), ("minimic_film", "flagship"))
    assert kinds == ["tech_acquired"]
    assert tech_rules.face_up_tech_ids(after) == ("minimic_film",)
    assert not tech_acquisition_possible(
        _with_stacks(state, ((), (), ())), state.players[0], 0
    )


def test_there_is_no_limit_on_the_tiles_a_seat_takes() -> None:
    """ "개수 제한 없음" [Rise of Ix p. 4]: a seat holding tiles is offered
    more, one icon at a time."""

    _, state = _holding(spice=13)
    state = _open(_open(_open(state)))
    for tech_id in ("detonation_devices", "holtzman_engine", "restricted_ordnance"):
        state, _ = _take(state, _buy(tech_id))
    assert state.players[0].tech_ids == (
        "detonation_devices",
        "holtzman_engine",
        "restricted_ordnance",
    )
    assert state.decision_stack[-1].kind != FrameKind.TECH_ACQUISITION
    assert state.players[0].resources.spice == 0


def test_an_acquire_effect_is_paid_as_the_tech_module_pays_it() -> None:
    """Flagship's acquire effect (1 Victory Point; docs/rules/rise-of-ix.md 4)
    is queued by the purchase and resolved by ``resolve_tech_acquire_effect``,
    as the Tech Module's acquire icons are."""

    stacks = (("flagship", "artillery"), STACKS[1], STACKS[2][:2])
    engine, state = _holding(spice=9, stacks=stacks)
    state = _open(state)
    after, _ = _take(state, _buy("flagship"))
    assert after.players[0].resources.spice == 1
    pending = tech_rules.pending_tech_acquire_effects(after.decision_stack[-1])
    assert pending == ("flagship:victory_points",)
    resolve = DomainAction(
        "resolve_tech_acquire_effect",
        0,
        (("effect", "victory_points"), ("tech_id", "flagship")),
    )
    assert resolve in tech_rules.legal_tech_acquire_effect_actions(after, 0)
    paid = apply_whole(engine, after, resolve).state
    assert paid.players[0].victory_points == state.players[0].victory_points + 1
    assert not tech_rules.pending_tech_acquire_effects(paid.decision_stack[-1])


def test_windtraps_and_shuttle_fleet_queue_the_keys_p4c_2a_added() -> None:
    """Windtraps' water and Shuttle Fleet's two different Factions (OQ-114)
    had no acquire key before stage P4c-2a and were refused rather than drop
    the water or pay one Influence for two; each tile now queues its own key
    (``tests/unit/rules/test_ix_tech_abilities.py`` pays them)."""

    for tile, key in (
        ("windtraps", "windtraps:water"),
        ("shuttle_fleet", "shuttle_fleet:distinct_influence"),
    ):
        stacks = ((tile,), (), ())
        _, state = _holding(spice=9, stacks=stacks)
        after, _ = _take(_open(state), _buy(tile))
        assert tech_rules.pending_tech_acquire_effects(after.decision_stack[-1]) == (
            key,
        )


# --- The open decision, as the seat sees it ----------------------------------


def test_the_open_decision_shows_the_discount_the_payment_and_the_negotiators() -> None:
    """The frame the seat decides in carries ``TECH_DISCOUNT_KEY`` and
    ``TECH_PAYMENT_KEY`` (spice) for ``ix_pending_of`` (plan 17.8 item 4), which
    counts the returnable Negotiators from the state: a discount of 2, three
    Negotiators held and the dearest tile Holtzman Engine (6 less 2) show 3
    returnable, and one held shows 1. The frame keeps no count of them."""

    _, state = _holding(spice=9, negotiators=3)
    opened = _open(state, discount=2)
    assert NEGOTIATORS_RETURNABLE_KEY not in dict(opened.decision_stack[-1].context)
    assert ix_pending_of(opened, 0) == IxPending(
        tech_discount=2, tech_payment="spice", negotiators_returnable=3
    )
    assert ix_pending_of(opened, 1) == NO_IX_PENDING
    assert ix_pending_of(state, 0) == NO_IX_PENDING

    _, one = _holding(spice=9, negotiators=1)
    assert ix_pending_of(_open(one, discount=2), 0).negotiators_returnable == 1
    # No more than the dearest tile costs still lowers it.
    stacks = (("artillery",), (), ())
    _, cheap = _holding(spice=9, negotiators=3, stacks=stacks)
    assert ix_negotiators_returnable(cheap, 0, 0) == 1
    assert ix_pending_of(_open(cheap), 0) == IxPending(
        tech_discount=0, tech_payment="spice", negotiators_returnable=1
    )
    # With no tile left there is nothing to lower.
    _, none = _holding(spice=9, negotiators=3, stacks=((), (), ()))
    assert ix_negotiators_returnable(none, 0, 0) == 0

    after, _ = _take(opened, DECLINE)
    assert ix_pending_of(after, 0) == NO_IX_PENDING


def test_the_stacks_are_ixs_three_of_six() -> None:
    """ "Ix board의 세 더미" [Rise of Ix p. 4]: the helper deals the 18 tiles
    into three stacks of six in the order given, the first of each its top;
    anything but those 18 tiles once each is refused."""

    order = tuple(reversed(IX_TECH_IDS))
    stacks = deal_ix_tech_stacks(order)
    assert [len(stack) for stack in stacks] == [6, 6, 6]
    assert tuple(tile for stack in stacks for tile in stack) == order
    assert tuple(stack[0] for stack in stacks) == (order[0], order[6], order[12])
    with pytest.raises(ValueError, match="18 Rise of Ix Tech tiles"):
        deal_ix_tech_stacks(IX_TECH_IDS[:17])
    with pytest.raises(ValueError, match="18 Rise of Ix Tech tiles"):
        deal_ix_tech_stacks((*IX_TECH_IDS[:17], IX_TECH_IDS[0]))
    with pytest.raises(ValueError, match="18 Rise of Ix Tech tiles"):
        deal_ix_tech_stacks((*IX_TECH_IDS[:17], TECH_IDS[0]))


# --- The Tech Negotiation icon ------------------------------------------------


def _ability(icons: int) -> Ability:
    """A hand-built Plot of ``icons`` Tech Negotiation icons."""

    return Ability(
        AbilityTiming.PLOT,
        (EffectSection(rewards=(PlaceNegotiator(),) * icons),),
    )


@pytest.fixture
def printed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the executor read hand-built abilities for Intrigue entries: ref
    ``ix#1`` prints one icon, ``ix#2`` two."""

    abilities = {"ix#1": _ability(1), "ix#2": _ability(2)}
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


PLACE = DomainAction("place_intrigue_negotiator", 0)
REFUSE = DomainAction("decline_intrigue_negotiator", 0)


@pytest.mark.usefixtures("printed")
def test_a_negotiator_is_a_troop_of_the_supply_on_the_ix_board() -> None:
    """ "아이콘마다 supply의 troop 하나를 Ix board에 Negotiator로 놓을 수
    있다" [Rise of Ix p. 4]: one troop a taken icon, from the supply to the
    Ix board, so the seat still accounts for its 12 troops; a second icon is a
    second choice."""

    _, state = _start()
    entry = _entry("ix#2")
    assert entry_pieces(entry) == (PlaceNegotiator(), PlaceNegotiator())
    assert PLACE in ability_rows(state, 0, entry, STACKED)
    before = state.players[0]

    first = apply_piece(state, 0, entry, PLACE, source="s")
    owner = first.result.state.players[0]
    assert (owner.troops_supply, owner.negotiators) == (
        before.troops_supply - 1,
        1,
    )
    assert owner.troops_garrison == before.troops_garrison
    assert [(e.event_id, e.kind) for e in first.result.events] == [
        ("s:slot:0:negotiator_placed", "negotiator_placed")
    ]
    assert dict(first.result.events[0].payload) == {"player": 0}
    assert current_piece(first.entry) == PlaceNegotiator()

    second = apply_piece(first.result.state, 0, first.entry, PLACE, source="s")
    owner = second.result.state.players[0]
    assert (owner.troops_supply, owner.negotiators) == (before.troops_supply - 2, 2)
    assert current_piece(second.entry) is None
    assert (
        owner.troops_supply
        + owner.troops_garrison
        + owner.troops_conflict
        + owner.negotiators
        == 12
    )


@pytest.mark.usefixtures("printed")
def test_the_icon_is_a_may() -> None:
    """ "놓을 수 있다("may")" [Rise of Ix p. 4]: a frame stacked on the turn
    offers the Negotiator and its refusal; the refusal moves nothing; the
    owner's own turn offers no refusal, and the turn's end lapses an icon left
    unused (OQ-095 (2))."""

    _, state = _start()
    entry = _entry()
    assert ability_rows(state, 0, entry, STACKED) == (PLACE, REFUSE)
    assert ability_rows(state, 0, entry, IN_TURN) == (PLACE,)

    declined = apply_piece(state, 0, entry, REFUSE, source="s")
    assert declined.result.state is state
    assert [(e.event_id, e.kind) for e in declined.result.events] == [
        ("s:slot:0:negotiator_declined", "intrigue_negotiator_declined")
    ]
    assert current_piece(declined.entry) is None


@pytest.mark.usefixtures("printed")
def test_an_empty_supply_makes_the_icon_do_nothing() -> None:
    """ "supply가 비면 아무 일도 없다" [Rise of Ix p. 4]: with no troop in
    the supply the icon has no row to take, only its refusal is left in a
    stacked frame and nothing in the owner's own turn; the block names why. A
    line that pays for the icon is not played (OQ-113 (C)), one that does not
    still is."""

    _, state = _start()
    owner = state.players[0]
    state = _seat(
        state,
        troops_supply=0,
        troops_garrison=owner.troops_garrison + owner.troops_supply,
    )
    block = negotiator_block(state, 0)
    assert block is not None
    assert block.kind is OptionalBlockKind.NO_TROOP_FOR_NEGOTIATOR
    assert ability_rows(state, 0, _entry(), STACKED) == (REFUSE,)
    assert ability_rows(state, 0, _entry(), IN_TURN) == ()
    with pytest.raises(ValueError, match="no troop is left in the supply"):
        place_negotiator(state, 0, source="s")
    with pytest.raises(ValueError, match="no troop is left in the supply"):
        apply_piece(state, 0, _entry(), PLACE, source="s")

    unpaid = (EffectSection(rewards=(PlaceNegotiator(),)),)
    assert rewards_with_no_effect(state, 0, unpaid) == (PlaceNegotiator(),)
    stocked = _seat(
        state, troops_supply=1, troops_garrison=state.players[0].troops_garrison - 1
    )
    assert rewards_with_no_effect(stocked, 0, unpaid) == ()
    assert negotiator_block(stocked, 0) is None


def test_the_executor_names_the_negotiator_only_for_the_sources_that_print_it() -> None:
    """An Intrigue slot has its rows now; a source whose icon is a later
    stage's (an Agent box, a board space) stops the executor until its rows
    are added."""

    _, state = _start()
    rows = piece_rows(state, 0, PlaceNegotiator(), Source.INTRIGUE, refusals=True)
    assert rows == (PLACE, REFUSE)
    with pytest.raises(LookupError, match="templates answer recruit"):
        piece_rows(state, 0, PlaceNegotiator(), Source.AGENT_CARD, refusals=False)


def test_an_acquire_tech_icon_opens_the_ix_acquisition() -> None:
    """ "Acquire Tech 아이콘이 유일한 길이다. 아이콘마다 ... 얻을 수
    있다("may")" [Rise of Ix p. 4]: an Acquire Tech piece the executor applies
    opens the acquisition frame at its discount, with the Ix keys; a piece
    whose purchase nothing pays for is a line that changes nothing."""

    engine, state = _holding(spice=3, negotiators=2)
    section = EffectSection(rewards=(AcquireTech(1),))
    opened = apply_automatic_rewards(
        state, 0, (section,), "s", played_card_id=state.intrigue_deck[0]
    ).state
    top = opened.decision_stack[-1]
    assert top.kind == FrameKind.TECH_ACQUISITION
    assert ix_pending_of(opened, 0) == IxPending(
        tech_discount=1, tech_payment="spice", negotiators_returnable=2
    )
    # The executor opens an Intrigue card's icon, which must be used once a
    # tile is in reach (Machine Culture, OQ-057 (9)): no refusal beside the
    # purchases, and only the refusal once none is.
    assert DECLINE not in engine.whole_actions(opened, 0)
    broke_open = apply_automatic_rewards(
        _holding(spice=0)[1], 0, (section,), "s", played_card_id=state.intrigue_deck[0]
    ).state
    assert engine.whole_actions(broke_open, 0) == (DECLINE,)

    owner = state.players[0]
    assert rewards_with_no_effect(state, 0, (section,)) == ()
    broke = _holding(spice=0, stacks=STACKS)[1]
    assert rewards_with_no_effect(broke, 0, (section,)) == (AcquireTech(1),)
    assert tech_acquisition_possible(state, owner, 1)


# --- The engine and the codec ------------------------------------------------


def test_the_rows_run_through_the_engine_and_the_codec() -> None:
    """The original game's Rise of Ix engine offers each purchase as the step
    that picks its tile (and the Negotiators it returns), applies it, and every
    tile row it offers encodes and decodes to itself in that game's catalog."""

    engine, state = _holding(spice=2, negotiators=3)
    state = _open(state, discount=1)
    codec = ActionCodec(state.config)

    legal = engine.legal_actions(state, 0)
    picks = [action for action in legal if action.action_id == "choose_tech"]
    assert [
        (
            dict(action.arguments)["tech_id"],
            dict(action.arguments).get("negotiators", 0),
        )
        for action in picks
    ] == _offered(state)
    assert any(action.action_id == "decline" for action in legal)
    for action in picks:
        assert codec.decode(codec.encode(action), action.actor) == action

    buy = DomainAction(
        "choose_tech", 0, (("negotiators", 3), ("tech_id", "holtzman_engine"))
    )
    assert buy in picks
    result = engine.apply(state, buy)
    owner = result.state.players[0]
    assert owner.tech_ids == ("holtzman_engine",)
    assert owner.resources.spice == 0
    assert owner.negotiators == 0
    assert [event.kind for event in result.events][:2] == [
        "tech_acquired",
        "tech_revealed",
    ]
    assert not any(
        action.action_id == "choose_tech"
        for action in engine.legal_actions(result.state, 0)
    )


def test_disposal_facility_acquire_trash_rows_are_in_the_ix_catalog() -> None:
    """ "| Disposal Facility | 3 | trash 1 |" (docs/rules/rise-of-ix.md 4): the
    acquire icon's optional trash waits on the owner's turn as a row, or in a
    window of its own elsewhere (a Conflict reward's acquisition); its row,
    its refusal and every card it may trash encode and decode to themselves
    in the original game's Rise of Ix catalog, which holds them only through
    the tile (the 40-game sweep's seed 14 found the refusal missing)."""

    engine, state = _holding(spice=3, stacks=(("disposal_facility",), (), ()))
    after, _ = _take(_open(state), _buy("disposal_facility"))
    assert tech_rules.pending_tech_acquire_effects(after.decision_stack[-1]) == (
        "disposal_facility:trash",
    )
    resolve = DomainAction(
        "resolve_tech_acquire_effect",
        0,
        (("effect", "trash"), ("tech_id", "disposal_facility")),
    )
    waiting = apply_whole(engine, after, resolve).state
    codec = ActionCodec(IX)
    row = DomainAction(
        "trash", 0, (("printed", "disposal_facility"), ("source", "tech"))
    )
    assert row in engine.legal_actions(waiting, 0)
    picked = engine.apply(waiting, row).state
    for action in (row, *engine.legal_actions(picked, 0)):
        assert codec.decode(codec.encode(action), action.actor) == action

    printer = trash_printer(Source.TECH, "disposal_facility")
    window = state.push_decision(optional_trash_frame(0, "s", printer=printer))
    legal = engine.legal_actions(window, 0)
    assert {action.action_id for action in legal} == {
        "decline",
        "choose_personal_card",
    }
    for action in legal:
        assert codec.decode(codec.encode(action), action.actor) == action
    decline = next(action for action in legal if action.action_id == "decline")
    declined = engine.apply(window, decline).state
    assert [frame.kind for frame in declined.decision_stack] == [FrameKind.TURN]
    assert declined.players == state.players


def test_the_rows_of_the_ix_tiles_are_in_the_original_catalog_with_rise_of_ix() -> None:
    """Only a Rise of Ix catalog holds the Ix tiles' rows: each tile bought
    with no Negotiator or with one up to its price, and the acquire icons that
    a key pays (every tile's since stage P4c-2a), with the two rows of a tile's
    ability that choose (Detonation Devices, Disposal Facility) and the four
    Flip tiles' effect rows (stage P4c-2b), and the trash rows of Spy
    Satellites and Sonic Snoopers (stage P4c-2c); the original game alone has
    none of them [Rise of Ix p. 4]."""

    plain = ActionCodec(ORIGINAL).catalog
    ix = ActionCodec(IX).catalog
    ix_only = set(ix) - set(plain)
    chosen = {
        (dict(t.arguments)["tech_id"], dict(t.arguments).get("negotiators", 0))
        for t in ix
        if t.action_id == "choose_tech"
    }
    assert chosen == {
        (tile.tech_id, returned)
        for tile in IX_TECH_TILES_BY_ID.values()
        for returned in range(tile.cost + 1)
    }
    assert not any(t.action_id == "choose_tech" for t in plain)
    # The acquire icons' effect rows name their tile as the printed entity.
    effects = {
        dict(t.arguments)["printed"]
        for t in ix_only
        if dict(t.arguments).get("source") == "tech"
    }
    assert effects == {
        "chaumurky",
        "detonation_devices",
        "disposal_facility",
        "flagship",
        # The Flip tiles' effect rows (stage P4c-2b): the four of them.
        "holoprojectors",
        "invasion_ships",
        "memocorders",
        "shuttle_fleet",
        "sonic_snoopers",
        "spaceport",
        # Spy Satellites' trash for a VP (stage P4c-2c).
        "spy_satellites",
        "training_drones",
        "windtraps",
    }
    assert not {tile for tile in effects if tile in TECH_IDS}
    assert ActionTemplate("choose_tech", (("tech_id", "flagship"),)) in ix_only


def test_no_catalog_holds_the_negotiator_whole_rows_until_a_card_prints_them() -> None:
    """The Intrigue slot's Negotiator and its refusal are shown by the cards
    that print the icon (none yet, stages P4c-4 and P4d), so no catalog holds
    their whole rows; the executor still answers them (Rise of Ix p. 4)."""

    names = ("place_intrigue_negotiator", "decline_intrigue_negotiator")
    for config in (ORIGINAL, IX):
        assert not any(t.action_id in names for t in ActionCodec(config).catalog)


# --- Where the Tech Module's offer does not reach ----------------------------


def test_the_landsraad_offer_never_fires_without_the_tech_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Tech Module's Landsraad visit offers an Acquire Tech
    ([Bloodlines p. 7]); an original game with Rise of Ix has no Tech Module
    (it is refused for the original game until stage P7), so even a visit
    whose Tech icon looks pending offers no acquisition, no block and no
    row."""

    _, state = _holding(spice=9)
    frame = state.decision_stack[-1]
    monkeypatch.setattr(
        tech_rules,
        "current_agent_effect_context",
        lambda _: (
            frame,
            {"pending_board_icons": BOARD_ICON_TECH, "space_id": "landsraad"},
        ),
    )
    assert state.config.tech_module is False
    assert landsraad_tech_block(state, 0) is None
    assert legal_tech_acquisition_actions(state, 0) == ()


def test_the_tech_module_is_unchanged_without_rise_of_ix() -> None:
    """Nothing changes without Rise of Ix: an original game offers no
    acquisition at all, refuses to open one, and its seats keep the rows and
    keys of the game before this stage."""

    _, state = _start(rise_of_ix=False)
    assert legal_tech_acquisition_actions(state, 0) == ()
    with pytest.raises(ValueError, match="requires the Tech Module or Rise of Ix"):
        push_tech_acquisition(state, 0, discount=0, source="s", printer=PRINTER)
    assert ix_pending_of(state, 0) == NO_IX_PENDING
    assert not any(
        t.action_id in ("place_intrigue_negotiator", "choose_tech")
        or dict(t.arguments).get("negotiators")
        for t in ActionCodec(state.config).catalog
    )
    assert TECH_TILES_BY_ID["artillery"].cost == 1
    assert (
        tech_rules.tech_cost(
            _seat(state, high_council=True).players[0],
            TECH_TILES_BY_ID["flagship"],
        )
        == 7
    )  # the Tech Module's Ixian Embassy discount, unchanged


def test_a_high_council_seat_has_no_ixian_embassy_discount() -> None:
    """The Ixian Embassy's High Council discount is the Tech Module's board
    ([Bloodlines p. 7]); the Ix board has none (docs/rules/rise-of-ix.md 10a):
    a High Council seat pays an Ix tile its full price."""

    _, state = _holding(spice=9)
    state = _seat(state, high_council=True)
    owner = state.players[0]
    flagship = IX_TECH_TILES_BY_ID["flagship"]
    assert ix_tech_cost(owner, flagship, discount=0, negotiators=0) == 8
    after, _ = _take(_open(state), _buy("restricted_ordnance"))
    assert after.players[0].resources.spice == 5  # 9 - 4


# --- Conservation ------------------------------------------------------------


def test_negotiators_and_tiles_are_conserved() -> None:
    """A Negotiator is one of the seat's 12 troops ([Rise of Ix p. 4]: it
    leaves the supply and returns to it), and the 18 Ix tiles stay across the
    stacks, the seats' tiles and the trash through a purchase: the invariants
    hold after a placement, a purchase returning it, and a purchase that
    pays only spice."""

    _, state = _start()
    state = replace(
        state,
        tech_stacks=deal_ix_tech_stacks(IX_TECH_IDS),
        # Setup gives each seat its two dreadnoughts [Rise of Ix p. 3].
        players=tuple(
            replace(player, dreadnoughts_supply=2) for player in state.players
        ),
    )
    census = CardCensus.from_state(state)
    assert census.tech == frozenset(IX_TECH_IDS)
    state = _seat(state, resources=Resources(spice=10))
    placed = place_negotiator(state, 0, source="s").state
    check_state_invariants(placed, census)

    opened = _open(placed)
    tops = tech_rules.face_up_tech_ids(opened)
    cheapest = min(tops, key=lambda tech_id: IX_TECH_TILES_BY_ID[tech_id].cost)
    assert tops == ("artillery", "holtzman_engine", "sonic_snoopers")
    for returned in (0, 1):
        bought, _ = _take(opened, _buy(cheapest, returned))
        check_state_invariants(bought, census)
        owner = bought.players[0]
        assert (
            owner.troops_supply
            + owner.troops_garrison
            + owner.troops_conflict
            + owner.negotiators
            == 12
        )
        assert owner.negotiators == 1 - returned
        assert sorted(
            (
                *(t for stack in bought.tech_stacks for t in stack),
                *bought.tech_trash,
                *(t for seat in bought.players for t in seat.tech_ids),
            )
        ) == sorted(IX_TECH_IDS)


def test_a_tile_of_the_other_module_breaks_the_invariants() -> None:
    """Rise of Ix's tiles lie only in a Rise of Ix game, and a Rise of Ix game
    without the Tech Module holds none of the Tech Module's: the Ix board
    holds its stacks ([Rise of Ix p. 4]; docs/rules/rise-of-ix.md 4). A Tech
    Module game with an Ix tile on a stack, and an original game with Rise of
    Ix holding a Tech Module tile, both fail."""

    engine = UprisingRulesEngine(
        leader_ids=(
            "feyd_rautha_harkonnen",
            "gurney_halleck",
            "lady_amber_metulli",
            "lady_jessica",
        )
    )
    tech = engine.reset(RulesetConfig(bloodlines=True, tech_module=True), 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(tech), ChanceDecision):
        tech = engine.apply(tech, chance.resolve(decision)).state
    check_state_invariants(tech, CardCensus.from_state(tech))
    stack = tech.tech_stacks[0]
    stray = replace(
        tech, tech_stacks=((*stack[:-1], IX_TECH_IDS[0]), *tech.tech_stacks[1:])
    )
    with pytest.raises(InvariantViolation, match="outside a Rise of Ix game"):
        check_state_invariants(stray, CardCensus.from_state(stray))

    _, ix = _start()
    ix = _with_stacks(ix, (("glowglobes", "artillery"), (), ()))
    with pytest.raises(InvariantViolation, match="without the Tech Module"):
        check_state_invariants(ix, CardCensus.from_state(ix))
