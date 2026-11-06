"""Uprising with Rise of Ix and the options stage P7f left refused (stage
P7f-2, docs/base-game-and-ix-plan.md 19.2): the Tech Module, the CHOAM
module and Arrakeen Scouts.

Rules: docs/rules/rise-of-ix.md 10a and 17, docs/rules/bloodlines.md 5,
docs/rules/choam-module.md and docs/rules/arrakeen-scouts.md, with OQ-153.
States start from a real setup and are moved by hand into the moment a test
needs (``dataclasses.replace``); every offered row round-trips through the
game's ``ActionCodec``.
"""

import random
from dataclasses import replace
from functools import cache

from tests.unit.rules import test_scouts_missions as scouts_missions_test

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.agents.determinize import determinize
from dune_imperium.content.arrakeen_scouts import (
    missions_for,
    scouts_rise_of_ix,
)
from dune_imperium.content.arrakeen_scouts.types import UPRISING_POOLS
from dune_imperium.content.core.effects import GainResources
from dune_imperium.content.core.icons import Faction
from dune_imperium.content.rise_of_ix.contracts import IX_CONTRACTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import (
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    Resources,
)
from dune_imperium.core.observation import (
    PrivatePlayerView,
    known_card_seats,
    observe_state,
)
from dune_imperium.core.player import Influence
from dune_imperium.rules import UprisingRulesEngine, turn_rows
from dune_imperium.rules.acquire_icons import queue_acquire_icons
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.contracts import complete_contract_by_effect
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.phases import resolve_recall_or_endgame
from dune_imperium.rules.starting_contracts import deal_starting_contracts
from dune_imperium.rules.tech import (
    legal_tech_acquisition_actions,
    push_tech_acquisition,
)
from dune_imperium.simulation.invariants import check_observation_privacy

TECH = RulesetConfig(
    rise_of_ix=True, bloodlines=True, tech_module=True, first_player_seat_zero=True
)
DREADNOUGHT_SPACE = printer_value(Source.BOARD_SPACE, "dreadnought")
TESSIA_LEADERS = (
    "tessia_vernius",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class CheckedEngine(UprisingRulesEngine):
    """Round-trip every offered row through the game's codec."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _owning(state: GameState, seat: int, *tech_ids: str) -> GameState:
    """``seat`` holding ``tech_ids``, taken off the stacks and the trash."""

    state = replace(
        state,
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile not in tech_ids)
            for stack in state.tech_stacks
        ),
        tech_trash=tuple(tile for tile in state.tech_trash if tile not in tech_ids),
    )
    return _seat(state, seat, tech_ids=tech_ids)


def _start(
    config: RulesetConfig, leader_ids: tuple[str, ...] | None = None
) -> tuple[CheckedEngine, GameState]:
    engine = CheckedEngine(leader_ids=leader_ids) if leader_ids else CheckedEngine()
    state = engine.reset(config, 3)
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


# --- The Tech Module ---------------------------------------------------------------


def _panopticon_endgame(config: RulesetConfig) -> tuple[CheckedEngine, GameState]:
    """Seat 0 (Tessia Vernius) holds Panopticon as the Endgame opens, at 1
    Influence with the Emperor and the Bene Gesserit, 2 with the others,
    two Snooper tokens taken (the next reached pays reward 3, the one after
    it reward 4: docs/rules/rise-of-ix.md 10)."""

    engine, state = _start(config, TESSIA_LEADERS)
    state = _seat(
        _owning(state, 0, "panopticon"),
        0,
        influence=Influence(emperor=1, spacing_guild=2, bene_gesserit=1, fremen=2),
        snooper_faction_ids=(Faction.EMPEROR.value, Faction.BENE_GESSERIT.value),
    )
    state = replace(
        state,
        phase=GamePhase.RECALL_OR_ENDGAME,
        conflict_deck=(),
        decision_stack=(),
        config=config,
    )
    return engine, resolve_recall_or_endgame(state).state


def _track_spy_open(state: GameState) -> bool:
    return bool(state.pending_track_spies) or any(
        frame.kind == FrameKind.SPY_PLACEMENT for frame in state.decision_stack
    )


def _gain(engine: CheckedEngine, state: GameState, faction: Faction) -> GameState:
    row = DomainAction("resolve_effect_influence", 0, (("faction", faction.value),))
    assert row in engine.legal_actions(state, 0)
    return engine.apply(state, row).state


def test_panopticon_with_rise_of_ix_is_a_row_per_faction_in_the_owners_order() -> (
    None
):
    """Panopticon: "Endgame: Influence 1 이하인 진영마다 Influence 1"
    (docs/rules/bloodlines.md 5). With Rise of Ix, Tessia Vernius' Snoopers
    can sit on the tracks, and OQ-153's combination note decides: "들 수
    있으면 같은 원칙(진영마다 줄)을 따르고" -- "진영을 모두 정해 주는 효과(Quid Pro
    Quo)는 진영마다 줄 하나를 내고 소유자가 원하는 순서로 받는다". The order
    decides which track takes which Snooper reward ("그 token에 도달할 때마다
    Snooper track의 맨 위 덮이지 않은 보상을 받는다(① discard → spice 1, ② 그
    track의 4칸 보너스, ③ 그 track에 Influence 1, ④ ②와 ③)", rise-of-ix.md 10;
    on Uprising's board the Emperor's 4 bonus is the Spy, the Bene
    Gesserit's an Intrigue card [Main p. 7])."""

    engine, state = _panopticon_endgame(TECH)
    assert state.phase is GamePhase.ENDGAME
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.EFFECT_INFLUENCE_WINDOW
    assert {
        dict(row.arguments)["faction"] for row in engine.legal_actions(state, 0)
    } == {Faction.EMPEROR.value, Faction.BENE_GESSERIT.value}
    intrigue = len(state.players[0].intrigue_cards)

    emperor_first = _gain(
        engine, _gain(engine, state, Faction.EMPEROR), Faction.BENE_GESSERIT
    )
    seat = emperor_first.players[0]
    # Emperor reached first: reward 3 (+1 there); the Bene Gesserit reward 4
    # (its 4 bonus, an Intrigue card, and +1 there).
    assert (seat.influence.emperor, seat.influence.bene_gesserit) == (3, 3)
    assert len(seat.intrigue_cards) == intrigue + 1
    assert _track_spy_open(emperor_first) is False

    bene_gesserit_first = _gain(
        engine, _gain(engine, state, Faction.BENE_GESSERIT), Faction.EMPEROR
    )
    seat = bene_gesserit_first.players[0]
    assert (seat.influence.emperor, seat.influence.bene_gesserit) == (3, 3)
    assert len(seat.intrigue_cards) == intrigue
    # The Emperor's 4 bonus, its Spy, opens at once outside a turn.
    assert _track_spy_open(bene_gesserit_first) is True


def test_the_window_holds_the_endgame_lines_after_panopticon() -> None:
    """The Endgame lines are paid seat by seat as the Endgame opens (OQ-040):
    the owner's Rise of Ix tiles after its Tech Module line, so Spy
    Satellites ("Endgame: Influence 1 이하인 진영마다 1 VP", rise-of-ix.md 4)
    counts the Factions Panopticon has raised -- here none is left at 1 or
    less -- once the window's last row is taken."""

    def ended(*tech_ids: str) -> GameState:
        engine, state = _panopticon_endgame(TECH)
        # The Endgame opened before the tiles changed: open it again.
        state = _owning(state, 0, *tech_ids)
        state = replace(state, phase=GamePhase.RECALL_OR_ENDGAME, decision_stack=())
        state = resolve_recall_or_endgame(state).state
        state = _gain(engine, state, Faction.EMPEROR)
        assert state.decision_stack[-1].kind == FrameKind.EFFECT_INFLUENCE_WINDOW
        state = _gain(engine, state, Faction.BENE_GESSERIT)
        assert all(
            frame.kind != FrameKind.EFFECT_INFLUENCE_WINDOW
            for frame in state.decision_stack
        )
        return state

    assert (
        ended("panopticon", "spy_satellites").players[0].victory_points
        == ended("panopticon").players[0].victory_points
    )


def test_without_rise_of_ix_panopticon_pays_every_faction_at_once() -> None:
    """Every game without Rise of Ix (no Tessia) keeps the automatic Endgame
    line, Faction by Faction in seat order (OQ-044, OQ-040)."""

    config = RulesetConfig(
        bloodlines=True, tech_module=True, first_player_seat_zero=True
    )
    engine, state = _start(config)
    state = _seat(
        _owning(state, 0, "panopticon"),
        0,
        influence=Influence(emperor=1, spacing_guild=2, bene_gesserit=0, fremen=3),
    )
    state = replace(
        state, phase=GamePhase.RECALL_OR_ENDGAME, conflict_deck=(), decision_stack=()
    )
    ended = resolve_recall_or_endgame(state).state
    assert not ended.decision_stack
    seat = ended.players[0]
    assert (seat.influence.emperor, seat.influence.bene_gesserit) == (2, 1)
    assert (seat.influence.spacing_guild, seat.influence.fremen) == (2, 3)


def test_advanced_data_analysis_offers_its_spies_on_the_ix_acquisition() -> None:
    """With Rise of Ix the two modules' tiles share the Ix board's stacks:
    "두 모듈의 Tech 타일을 모두 섞어 세 더미" [Bloodlines p. 7]
    (docs/rules/rise-of-ix.md 10a), and Advanced Data Analysis keeps its
    acquire cost, "You must trash one of your Spies from the board" [Tech
    tile] (docs/rules/bloodlines.md 5): a row per Spy, Negotiators beside
    it ("Ix 판의 Acquire Tech가 두 모듈 타일 모두에 Negotiator 할인",
    rise-of-ix.md 10a). Plan 17.10 found the Ix branch offering it without
    the Spy (``KeyError`` when chosen); this is the merged branch."""

    engine, state = _start(TECH)
    posts = (
        "landsraad-tech-negotiation-dreadnought",
        "arrakis-spice-refinery-arrakeen",
    )
    owner = state.players[0]
    state = _seat(
        state,
        0,
        resources=Resources(spice=4, solari=0, water=0),
        spy_post_ids=posts,
        spies_supply=owner.spies_supply - len(posts),
        troops_supply=owner.troops_supply - 1,
        negotiators=1,
    )
    state = replace(
        state, tech_stacks=(("advanced_data_analysis",), ("artillery",), ())
    )
    state = push_tech_acquisition(
        state, 0, discount=0, source="s", printer=DREADNOUGHT_SPACE
    ).state
    rows = [
        row
        for row in engine.whole_actions(state, 0)
        if dict(row.arguments).get("tech_id") == "advanced_data_analysis"
    ]
    assert {
        (dict(row.arguments)["post_id"], dict(row.arguments).get("negotiators", 0))
        for row in rows
    } == {(post, returned) for post in posts for returned in (0, 1)}
    assert set(rows) <= set(legal_tech_acquisition_actions(state, 0))
    chosen = next(
        row
        for row in rows
        if dict(row.arguments) == {
            "tech_id": "advanced_data_analysis",
            "post_id": posts[1],
            "negotiators": 1,
        }
    )
    bought = apply_whole(engine, state, chosen).state.players[0]
    assert bought.tech_ids == ("advanced_data_analysis",)
    assert bought.spy_post_ids == (posts[0],)
    assert bought.spies_boxed == 1
    assert bought.negotiators == 0


# --- The CHOAM Module: the ten Rise of Ix Contracts [Main p. 16] -----------------

CHOAM = RulesetConfig(rise_of_ix=True, choam_module=True, first_player_seat_zero=True)
DREADNOUGHT = "contract:ix_dreadnought"


def _choosing() -> tuple[CheckedEngine, GameState]:
    engine = CheckedEngine()
    state = engine.reset(CHOAM, 3)
    assert state.phase is GamePhase.SETUP
    return engine, state


def _private(state: GameState, seat: int) -> PrivatePlayerView:
    private = observe_state(state, seat).private
    assert private is not None
    return private


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def test_the_ten_rise_of_ix_contracts_are_transcribed_with_their_jumpstart() -> None:
    """ "UPRISING includes 10 additional contracts (with different backs) to
    use specifically when playing with RISE OF IX" [Main p. 16]: every one
    prints "+1 Contract" and none sits in the bank (docs/rules/choam-module.md;
    read from the Steam app's ``ContractRoI_1``-``_10`` archetypes and their
    layouts, the faces on Dune Cards Hub)."""

    terms = {
        contract.card.name: (
            contract.board_space or f"harvest {contract.harvest_spice}+",
            [type(piece).__name__ for piece in contract.reward_line.rewards],
        )
        for contract in IX_CONTRACTS
    }
    assert terms == {
        "Dreadnought": ("dreadnought", ["PlaceNegotiator", "TakeContract"]),
        "Espionage II": ("espionage", ["GainResources", "TakeContract"]),
        "Harvest 3+": ("harvest 3+", ["TakeContract"]),
        "Harvest 4+": ("harvest 4+", ["GainResources", "TakeContract"]),
        "Heighliner III": ("heighliner", ["GainResources", "TakeContract"]),
        "High Council III": ("high_council", ["PlaceNegotiator", "TakeContract"]),
        "Interstellar Shipping": (
            "interstellar_shipping",
            ["PlaceNegotiator", "TakeContract"],
        ),
        "Secrets": ("secrets", ["TakeContract"]),
        "Smuggling": ("smuggling", ["TakeContract"]),
        "Tech Negotiation": ("tech_negotiation", ["TakeContract"]),
    }
    solari = {
        contract.card.name: next(
            (
                piece.solari
                for piece in contract.reward_line.rewards
                if isinstance(piece, GainResources)
            ),
            0,
        )
        for contract in IX_CONTRACTS
    }
    assert {name: n for name, n in solari.items() if n} == {
        "Espionage II": 1,
        "Harvest 4+": 2,
        "Heighliner III": 3,
    }
    ids = set(content_for(CHOAM).ix_contract_instance_ids)
    assert len(ids) == 10
    assert not ids & set(content_for(CHOAM).contract_instance_ids)


def test_setup_gives_each_player_two_and_each_sees_only_its_own() -> None:
    """ "After setting up the 20 standard contracts, shuffle the 10 RISE OF IX
    contracts and give two to each player. Each player looks at the two
    they've been given" [Main p. 16]: two to each seat, two left in the box,
    the bank the 20 standard tiles; a seat's two are its own (the view, the
    privacy registry), the box is nobody's."""

    _, state = _choosing()
    dealt = [seat.starting_contract_ids for seat in state.players]
    assert all(len(pair) == 2 for pair in dealt)
    assert len(state.contract_box) == 2
    assert len({*state.contract_box, *(card for pair in dealt for card in pair)}) == 10
    assert len(state.contract_bank) + len(state.face_up_contract_ids) == 20
    known = known_card_seats(state)
    for seat, pair in enumerate(dealt):
        assert _private(state, seat).starting_contract_ids == pair
        assert all(known[card] == frozenset({seat}) for card in pair)
    assert all(known[card] == frozenset() for card in state.contract_box)
    check_observation_privacy(state)


def test_the_choice_is_sealed_until_every_player_has_chosen() -> None:
    """ "choosing simultaneously which contract they want to begin the game
    with (placing it face up in their supply). Return all of the unchosen
    RISE OF IX contracts to the box." [Main p. 16]: each seat chooses in turn
    from the First Player, its choice its own until the last one; then every
    choice is an active Contract, face up, and the unchosen go to the box."""

    engine, state = _choosing()
    assert _owner(state) == 0
    first_pick = state.players[0].starting_contract_ids[1]
    result = engine.apply(
        state,
        DomainAction("choose_starting_contract", 0, (("instance_id", first_pick),)),
    )
    state = result.state
    identity = next(e for e in result.events if e.kind == "starting_contract_identity")
    assert identity.visible_to == (0,)
    chosen = next(e for e in result.events if e.kind == "starting_contract_chosen")
    assert chosen.visible_to is None and "contract_id" not in dict(chosen.payload)
    assert _owner(state) == 1
    assert _private(state, 0).starting_contract_pick == first_pick
    assert _private(state, 1).starting_contract_pick == ""
    assert known_card_seats(state)[first_pick] == frozenset({0})
    check_observation_privacy(state)
    picks = {0: first_pick}
    for seat in (1, 2, 3):
        assert _owner(state) == seat
        picks[seat] = state.players[seat].starting_contract_ids[0]
        result = engine.apply(
            state,
            DomainAction(
                "choose_starting_contract", seat, (("instance_id", picks[seat]),)
            ),
        )
        state = result.state
    assert state.phase is not GamePhase.SETUP
    for seat, pick in picks.items():
        assert state.players[seat].active_contract_ids == (pick,)
        assert state.players[seat].starting_contract_ids == ()
    revealed = {
        dict(e.payload)["player"]: dict(e.payload)["contract_id"]
        for e in result.events
        if e.kind == "starting_contract_revealed"
    }
    assert revealed == picks
    assert len(state.contract_box) == 2 + 4
    assert not set(picks.values()) & set(state.contract_box)
    known = known_card_seats(state)
    assert all(known[card] == frozenset() for card in state.contract_box)


def test_the_choice_is_dealt_after_the_leader_draft() -> None:
    """The deal waits until every Leader is known, as Epic Game Mode's setup
    Intrigue card does [Rise of Ix p. 10] (``rules.starting_contracts``):
    no seat picks its Leader holding its two."""

    engine = CheckedEngine()
    state = engine.reset(replace(CHOAM, leader_draft=True), 3)
    assert all(not seat.starting_contract_ids for seat in state.players)
    assert len(state.contract_box) == 10
    while state.decision_stack[-1].kind == FrameKind.LEADER_DRAFT:
        owner = _owner(state)
        state = engine.apply(state, engine.legal_actions(state, owner)[0]).state
    assert state.decision_stack[-1].kind == FrameKind.STARTING_CONTRACT
    assert all(len(seat.starting_contract_ids) == 2 for seat in state.players)
    assert len(state.contract_box) == 2


def test_the_deal_starts_from_the_first_player() -> None:
    """The box's top two go to the First Player, then clockwise -- the order
    the seats choose in (OQ-161 (2), (3)), as the app deals (P7g A6) -- and
    the First Player chooses first."""

    state = replace(_drafting(), first_player=2)
    box = state.contract_box
    dealt = deal_starting_contracts(state)
    assert [dealt.players[seat].starting_contract_ids for seat in (2, 3, 0, 1)] == [
        box[0:2],
        box[2:4],
        box[4:6],
        box[6:8],
    ]
    assert dealt.contract_box == box[8:]
    assert _owner(dealt) == 2


def test_the_determinizer_keeps_the_observers_two_and_redeals_the_rest() -> None:
    _, state = _choosing()
    engine = CheckedEngine()
    pick = state.players[0].starting_contract_ids[0]
    state = engine.apply(
        state, DomainAction("choose_starting_contract", 0, (("instance_id", pick),))
    ).state
    own = state.players[1].starting_contract_ids
    hidden = {
        *state.contract_box,
        *(
            card
            for seat in (0, 2, 3)
            for card in state.players[seat].starting_contract_ids
        ),
    }
    seen = set()
    for seed in range(20):
        sample = determinize(state, 1, random.Random(seed))
        assert sample.players[1].starting_contract_ids == own
        dealt = {
            *sample.contract_box,
            *(
                card
                for seat in (0, 2, 3)
                for card in sample.players[seat].starting_contract_ids
            ),
        }
        assert dealt == hidden
        chosen = sample.players[0].starting_contract_pick
        assert chosen in sample.players[0].starting_contract_ids
        assert sample.players[2].starting_contract_pick == ""
        seen.add(chosen)
    assert len(seen) > 1


def _drafting() -> GameState:
    """Uprising with Rise of Ix, the CHOAM Module and the Leader draft, at
    the draft's first pick: every Rise of Ix tile still in the box."""

    state = CheckedEngine().reset(replace(CHOAM, leader_draft=True), 3)
    assert state.decision_stack[-1].kind == FrameKind.LEADER_DRAFT
    assert len(state.contract_box) == len(IX_CONTRACTS)
    return state


def _contract_sample(state: GameState) -> tuple[object, ...]:
    return (
        state.contract_box,
        tuple(
            (seat.starting_contract_ids, seat.starting_contract_pick)
            for seat in state.players
        ),
    )


def test_the_determinizer_reshuffles_the_box_before_the_deal() -> None:
    """During the Leader draft the box's order is the deal to come, known to
    nobody [Main p. 16] (no seat picks its Leader holding its two, OQ-161
    (1)): a sample's box does not depend on it -- two states that differ
    only in it give the same sample from the same draws -- and is not the
    real order (Codex review of P7f-2, finding 1)."""

    state = _drafting()
    twin = replace(state, contract_box=tuple(reversed(state.contract_box)))
    assert observe_state(state, 0) == observe_state(twin, 0)
    moved = 0
    for seed in range(5):
        sample = determinize(state, 0, random.Random(seed))
        assert _contract_sample(sample) == _contract_sample(
            determinize(twin, 0, random.Random(seed))
        )
        assert sorted(sample.contract_box) == sorted(state.contract_box)
        moved += sample.contract_box != state.contract_box
    assert moved == 5


def test_the_determinizer_s_contract_sample_ignores_the_sealed_pairs() -> None:
    """While the seats choose, another seat's two and its sealed choice are
    as unknown as the box: twin states that trade a tile between seat 2's
    pair and the box and change seat 0's choice give observer 1 the same
    sample; its own two stay."""

    engine, state = _choosing()
    pick = state.players[0].starting_contract_ids[0]
    state = engine.apply(
        state, DomainAction("choose_starting_contract", 0, (("instance_id", pick),))
    ).state
    other = state.players[0].starting_contract_ids[1]
    pair = state.players[2].starting_contract_ids
    players = list(state.players)
    players[0] = replace(players[0], starting_contract_pick=other)
    players[2] = replace(
        players[2], starting_contract_ids=(state.contract_box[0], pair[1])
    )
    twin = replace(
        state,
        players=tuple(players),
        contract_box=(pair[0], *state.contract_box[1:]),
    )
    assert observe_state(state, 1) == observe_state(twin, 1)
    for seed in range(5):
        sample = determinize(state, 1, random.Random(seed))
        assert _contract_sample(sample) == _contract_sample(
            determinize(twin, 1, random.Random(seed))
        )
        assert sample.players[1].starting_contract_ids == (
            state.players[1].starting_contract_ids
        )


def test_no_view_shows_another_seat_s_pair_or_the_box() -> None:
    """Every seat's view is the same on a state whose box and other seats'
    pairs and sealed choices are scrambled (``check_observation_privacy``)
    -- before the deal, once dealt, after a sealed choice, and once every
    choice is revealed."""

    check_observation_privacy(_drafting())
    engine, state = _choosing()
    check_observation_privacy(state)
    pick = state.players[0].starting_contract_ids[0]
    state = engine.apply(
        state, DomainAction("choose_starting_contract", 0, (("instance_id", pick),))
    ).state
    check_observation_privacy(state)
    check_observation_privacy(_picked_all(engine, state))


def _completed(state: GameState, seat: int = 0) -> GameState:
    """``seat`` completing the Dreadnought tile (Negotiator + Contract)."""

    state = _seat(state, seat, active_contract_ids=(DREADNOUGHT,))
    return complete_contract_by_effect(state, seat, DREADNOUGHT, source="t").state


def _picked_all(engine: CheckedEngine, state: GameState) -> GameState:
    while state.decision_stack and state.decision_stack[-1].kind == (
        FrameKind.STARTING_CONTRACT
    ):
        owner = _owner(state)
        state = engine.apply(state, engine.legal_actions(state, owner)[0]).state
    return state


def _without_ix_tiles_in_hands(state: GameState) -> GameState:
    """Every seat's active Rise of Ix tile back to the box (to hand one out)."""

    box = list(state.contract_box)
    for seat in range(4):
        active = state.players[seat].active_contract_ids
        box.extend(active)
        state = _seat(state, seat, active_contract_ids=())
    return replace(state, contract_box=tuple(box))


def test_the_negotiator_icon_is_a_may_in_its_window() -> None:
    """The Tech Negotiation icon: "you may take a troop from your supply and
    place it on the Ix board" [Rise of Ix p. 4] (docs/rules/rise-of-ix.md 4):
    outside its owner's turn the reward's window offers it with a refusal,
    and with no troop in the supply ("supply가 비면 아무 일도 없다") only the
    refusal."""

    engine, state = _choosing()
    state = _without_ix_tiles_in_hands(_picked_all(engine, state))
    box = tuple(card for card in state.contract_box if card != DREADNOUGHT)
    state = replace(state, contract_box=box, decision_stack=())
    window = _completed(state, 1)
    assert window.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_ICONS
    rows = {
        (row.action_id, dict(row.arguments)["effect"])
        for row in engine.whole_actions(window, 1)
    }
    assert {
        ("resolve_contract_reward_icon", "negotiator"),
        ("decline_contract_reward_icon", "negotiator"),
        ("resolve_contract_reward_icon", "contract"),
    } <= rows
    placed = apply_whole(
        engine,
        window,
        DomainAction("resolve_contract_reward_icon", 1, (("effect", "negotiator"),)),
    ).state
    assert placed.players[1].negotiators == 1
    assert placed.players[1].troops_supply == window.players[1].troops_supply - 1
    declined = apply_whole(
        engine,
        window,
        DomainAction("decline_contract_reward_icon", 1, (("effect", "negotiator"),)),
    )
    assert declined.state.players[1].negotiators == 0
    assert "contract_reward_icon_declined" in [e.kind for e in declined.events]
    owner = window.players[1]
    empty = _seat(
        window,
        1,
        troops_supply=0,
        troops_garrison=owner.troops_garrison + owner.troops_supply,
    )
    negotiator_rows = {
        row.action_id
        for row in engine.whole_actions(empty, 1)
        if dict(row.arguments).get("effect") == "negotiator"
    }
    assert negotiator_rows == {"decline_contract_reward_icon"}


def test_the_negotiator_icon_holds_no_turn_end_and_lapses() -> None:
    """In its owner's own turn a Contract's icons are rows of that turn
    (OQ-112 (4)); a "may" icon holds no turn end back and lapses at the
    press (OQ-095 (2)), as an Unload box's Tech Negotiation does."""

    engine, state = _choosing()
    state = _without_ix_tiles_in_hands(_picked_all(engine, state))
    box = tuple(card for card in state.contract_box if card != DREADNOUGHT)
    state = replace(state, contract_box=box)
    assert state.phase is GamePhase.PLAYER_TURNS
    turn = _completed(state, 0)
    assert turn_rows.holds_the_end(turn, 0)
    rows = {
        dict(row.arguments).get("effect")
        for row in engine.whole_actions(turn, 0)
        if dict(row.arguments).get("contract_id") == DREADNOUGHT
    }
    assert rows == {"negotiator", "contract"}
    pending = turn_rows.rows_frame(turn, 0)
    assert pending is not None
    contract_row = next(
        item
        for item in turn_rows.pending(pending)
        if item[0] == turn_rows.CONTRACT_ICON and item[2].endswith("|contract")
    )
    only_negotiator = turn_rows.take(turn, 0, contract_row)
    assert not turn_rows.holds_the_end(only_negotiator, 0)
    lapsed = turn_rows.lapse(only_negotiator, 0)
    assert [e.kind for e in lapsed.events] == ["contract_reward_icon_lapsed"]
    # With no troop in the supply the row is not offered at all.
    owner = turn.players[0]
    empty = _seat(
        turn,
        0,
        troops_supply=0,
        troops_garrison=owner.troops_garrison + owner.troops_supply,
    )
    assert all(
        dict(row.arguments).get("effect") != "negotiator"
        for row in engine.whole_actions(empty, 0)
    )


# --- Arrakeen Scouts: the Uprising+Ix mission pool ---------------------------------

SCOUTS = RulesetConfig(arrakeen_scouts=True, rise_of_ix=True)


def _scouts_visit(state: GameState, space_id: str) -> GameState:
    """Seat 0 sends an Agent to an Ix space (Smuggling with Dune, the Desert
    Planet; Dreadnought with Dagger) and collects its mission pieces."""

    card = {
        "smuggling": "player:0:starter:dune_the_desert_planet:0",
        "dreadnought": "player:0:starter:dagger:0",
    }[space_id]
    placement = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments)["card_id"] == card
    )
    state = apply_placement(SCOUTS_ENGINE, state, placement).state
    collect = next(
        action
        for action in SCOUTS_ENGINE.whole_actions(state, 0)
        if action.action_id == "scouts_collect_mission"
    )
    return apply_whole(SCOUTS_ENGINE, state, collect).state


SCOUTS_ENGINE = UprisingRulesEngine()
# Two type-1 missions of the Uprising+Ix pool revealed in round 2, so the
# round-3 slot draws a type-0 one [Scouts schedule].
_TYPE_ONE_FIRST = ((2, "weirding_warfare"), (2, "stowaways"))


def test_the_rise_of_ix_pool_trades_send_for_aid_for_three_missions() -> None:
    """The app's Uprising+Ix pools drop Send for Aid (its Gather Support is
    under the half overlay [Main p. 18]) and add Secret Stash, Armed Escort
    and Stowaways; every other list is the Uprising one [Scouts schedule]
    (docs/rules/arrakeen-scouts.md 2.2, 5)."""

    # The original game's pools trade their own missions (stage P8).
    for pool in UPRISING_POOLS:
        plain = {m.mission_id for m in missions_for(pool, choam=True)}
        with_ix = {
            m.mission_id for m in missions_for(pool, choam=True, rise_of_ix=True)
        }
        assert plain - with_ix == {"send_for_aid"}
        assert with_ix - plain == {"secret_stash", "armed_escort", "stowaways"}
    state = scouts_missions_test._reveal(
        scouts_missions_test._base(SCOUTS), "stowaways"
    )
    assert state.config.rise_of_ix
    # Either base game plays its Rise of Ix pools (stage P8).
    assert scouts_rise_of_ix(SCOUTS)
    original = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
    assert scouts_rise_of_ix(original)
    assert not scouts_rise_of_ix(RulesetConfig(base_game=BaseGame.IMPERIUM))


def test_secret_stash_leaves_two_spice_for_the_next_smuggling_visitor() -> None:
    """Secret Stash: the bank's 2 spice on Smuggling, gained by the next
    seat that sends an Agent there [Scouts mission: Secret Stash]."""

    state = scouts_missions_test._reveal(
        scouts_missions_test._base(SCOUTS),
        "secret_stash",
        scouts_revealed=_TYPE_ONE_FIRST,
    )
    assert state.scouts_goods == (("secret_stash", "smuggling", "spice", 2, -1),)
    assert state.decision_stack[-1].kind != FrameKind.SCOUTS_MISSION
    visited = _scouts_visit(scouts_missions_test._turn_for(state), "smuggling")
    assert visited.scouts_goods == ()
    assert ("spice", 2) in scouts_missions_test._taken(visited)


def test_stowaways_park_two_paid_troops_that_reach_the_conflict() -> None:
    """Stowaways: each seat may pay 1 spice to put two troops of its supply
    on Smuggling; its next visit there moves them into the Conflict [Scouts
    mission: Stowaways], as Weirding Warfare's (OQ-077)."""

    state = scouts_missions_test._reveal(
        scouts_missions_test._base(SCOUTS), "stowaways"
    )
    spice = state.players[0].resources.spice
    supply = state.players[0].troops_supply
    state = scouts_missions_test._answer(state, {0: ""})
    owner = state.players[0]
    assert (owner.resources.spice, owner.troops_supply, owner.troops_parked) == (
        spice - 1,
        supply - 2,
        2,
    )
    assert state.scouts_parked == (("stowaways", 0, "smuggling", 2),)
    visited = _scouts_visit(scouts_missions_test._turn_for(state), "smuggling")
    assert visited.players[0].troops_conflict == 2
    assert visited.players[0].troops_parked == 0


def test_armed_escort_moves_every_seats_dreadnought_and_deploys_it_on_a_visit() -> (
    None
):
    """Armed Escort: each seat moves a dreadnought of its supply to the
    Dreadnought space with the bank's spice under it -- no "may", so no seat
    is asked; its first visit there takes the spice and deploys the
    dreadnought to the Conflict [Scouts mission: Armed Escort]. A seat with
    no dreadnought in its supply places nothing (OQ-088's principle)."""

    base = scouts_missions_test._base(SCOUTS)
    base = _seat(base, 3, dreadnoughts_supply=0, dreadnoughts_garrison=2)
    state = scouts_missions_test._reveal(
        base, "armed_escort", scouts_revealed=_TYPE_ONE_FIRST
    )
    assert all(
        frame.kind != FrameKind.SCOUTS_MISSION for frame in state.decision_stack
    )
    assert [seat.dreadnoughts_parked for seat in state.players] == [1, 1, 1, 0]
    assert [seat.dreadnoughts_supply for seat in state.players] == [1, 1, 1, 0]
    assert sorted(state.scouts_parked) == [
        ("armed_escort", seat, "dreadnought", 1) for seat in (0, 1, 2)
    ]
    assert sorted(state.scouts_goods) == [
        ("armed_escort", "dreadnought", "spice", 1, seat) for seat in (0, 1, 2)
    ]
    visited = _scouts_visit(scouts_missions_test._turn_for(state), "dreadnought")
    owner = visited.players[0]
    assert owner.dreadnoughts_parked == 0
    assert owner.dreadnoughts_conflict == 1
    assert ("spice", 1) in scouts_missions_test._taken(visited)
    assert [row[1] for row in visited.scouts_parked] == [1, 2]


def test_an_acquire_box_bought_outside_its_owners_turn_opens_a_window() -> None:
    """ "When you acquire a card, you immediately resolve its acquire box,
    once" [DI p. 16]; its icons are rows its owner takes in any order
    (OQ-141). Arrakeen Scouts' market buys outside the buyer's turn, so with
    Rise of Ix's Full-Scale Assault -- "Dreadnought 아이콘마다 supply의
    dreadnought 하나를 garrison에 commission할 수 있다("may")"
    (docs/rules/rise-of-ix.md 6) -- the box opens a window of its own there,
    the "may" with its refusal (the soak's seed 7 had stopped on it)."""

    engine = CheckedEngine()
    state = engine.reset(SCOUTS, 3)
    entry = next(e for e in IX_IMPERIUM_CARDS if e.card.card_id == "full_scale_assault")
    # Seat 1 buys while seat 0's turn is open.
    window = queue_acquire_icons(state, 1, entry, source="market")
    assert window.decision_stack[-1].kind == FrameKind.ACQUIRE_ICONS_WINDOW
    rows = {row.action_id for row in engine.whole_actions(window, 1)}
    assert rows == {"resolve_acquire_icon", "decline_acquire_icon"}
    commissioned = apply_whole(
        engine,
        window,
        DomainAction(
            "resolve_acquire_icon",
            1,
            (("acquired_card_id", "full_scale_assault"), ("effect", "dreadnought")),
        ),
    ).state
    assert commissioned.players[1].dreadnoughts_garrison == 1
    assert all(
        frame.kind != FrameKind.ACQUIRE_ICONS_WINDOW
        for frame in commissioned.decision_stack
    )
    declined = apply_whole(
        engine,
        window,
        DomainAction(
            "decline_acquire_icon",
            1,
            (("acquired_card_id", "full_scale_assault"), ("effect", "dreadnought")),
        ),
    )
    assert declined.state.players[1].dreadnoughts_garrison == 0
    assert "acquire_icon_declined" in [event.kind for event in declined.events]
