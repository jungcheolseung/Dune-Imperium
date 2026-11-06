"""Uprising with Rise of Ix (stage P7f, docs/base-game-and-ix-plan.md 19.2).

Rules: docs/rules/rise-of-ix.md 17 ("ADDING RISE OF IX" [Main p. 18]) and the
rest of that file for Rise of Ix's own systems. Setup takes ``rise_of_ix`` on
Uprising since stage P7f, so the states below start from a real setup and
are moved by hand into the moment a test needs (``dataclasses.replace``).
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.registry.board import BOARD_SPACES_BY_ID
from dune_imperium.content.registry.card_abilities import card_reveal_choices
from dune_imperium.content.registry.conflicts import CONFLICTS
from dune_imperium.content.rise_of_ix.board import IX_OBSERVATION_POSTS, IX_SPACE_IDS
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.tech import IX_TECH_IDS
from dune_imperium.content.rulesets import (
    IX_LEADER_IDS_OFFERED,
    UPRISING_IX_OVERLAID_SPACE_IDS,
    content_for,
)
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    Resources,
)
from dune_imperium.core.player import Influence
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.agent_effects import agent_card_effect_is_unavailable
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.combat_deployment import legal_dreadnought_deployments
from dune_imperium.rules.effect_interpreter import apply_rewards, condition_holds
from dune_imperium.rules.frames import FrameKind, owned_top_frame
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.sandworms import SandwormBlock, sandworm_block
from dune_imperium.rules.scouts_effects import push_scouts_effect
from dune_imperium.rules.spy_moves import spy_placement_frame
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    observation_post_ids_for_agent_icons,
    observation_post_ids_in_play,
)

IX = RulesetConfig(rise_of_ix=True, first_player_seat_zero=True)
COVERED_POST = "landsraad-assembly-hall-gather-support"
COVERED_CHOAM_POST = "choam-shipping-accept-contract"
SHIPPING_POST = "choam-interstellar-shipping-smuggling"
NEGOTIATION_POST = "landsraad-tech-negotiation-dreadnought"
DELEGATE = "imperium:choam_delegate:0"
PLANET = "player:0:starter:dune_the_desert_planet:0"
RECON = "player:0:starter:reconnaissance:0"


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class CheckedEngine(UprisingRulesEngine):
    """Round-trip every offered row through the Uprising + Ix codec."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _start(
    config: RulesetConfig = IX, leader_ids: tuple[str, ...] | None = None
) -> tuple[CheckedEngine, GameState]:
    engine = CheckedEngine(leader_ids=leader_ids) if leader_ids else CheckedEngine()
    state = engine.reset(config, 3)
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _take(state: GameState, card: str) -> GameState:
    """``card`` out of the Imperium Row and deck (into a test hand)."""

    return replace(
        state,
        imperium_row=tuple(c for c in state.imperium_row if c != card),
        imperium_deck=tuple(c for c in state.imperium_deck if c != card),
    )


# --- Setup and content ---------------------------------------------------------


def test_setup_lays_the_half_overlay_and_rise_of_ix_on_the_uprising_board() -> None:
    """ "keep the CHOAM board overlay folded in half and cover only the
    top-right corner of the UPRISING board. This will create a new CHOAM
    section and cover the Assembly Hall and Gather Support board spaces in
    the Landsraad, while leaving the rest of the Landsraad board spaces in
    UPRISING unchanged." [Main p. 18] (docs/rules/rise-of-ix.md 17); the new
    CHOAM section lies over Uprising's, Shipping and Accept Contract: "The
    RISE OF IX expansion replaces one of the locations on the UPRISING board
    where you can take a new contract." [Main p. 16], and "Remove these 5
    UPRISING cards: Accept Contract/Shipping (2 copies), Gather Support (2
    copies), and Assembly Hall." [Supplements p. 6]. Rise of Ix's own setup:
    "two dreadnoughts in their supply", the Freighter on the Shipping track's
    bottom space and three stacks of six Tech tiles [Rise of
    Ix p. 3] (rise-of-ix.md 3)."""

    _, state = _start()
    content = content_for(IX)
    spaces = [space.space_id for space in content.board_spaces]
    plain = [space.space_id for space in content_for(RulesetConfig()).board_spaces]

    assert UPRISING_IX_OVERLAID_SPACE_IDS == (
        "assembly_hall",
        "gather_support",
        "shipping",
        "accept_contract",
    )
    assert not set(UPRISING_IX_OVERLAID_SPACE_IDS) & set(spaces)
    # Uprising's other spaces stay, in their order; the four follow them.
    assert spaces == [
        *(space for space in plain if space not in UPRISING_IX_OVERLAID_SPACE_IDS),
        *IX_SPACE_IDS,
    ]
    for seat in state.players:
        assert (seat.dreadnoughts_supply, seat.dreadnoughts_garrison) == (2, 0)
        assert seat.freighter_space == 0
    assert [len(stack) for stack in state.tech_stacks] == [6, 6, 6]
    assert sorted(tile for stack in state.tech_stacks for tile in stack) == sorted(
        IX_TECH_IDS
    )


def test_the_decks_take_rise_of_ix_cards_and_leaders_but_not_its_conflicts() -> None:
    """ "Shuffle the Rise of Ix Imperium cards into the Imperium Deck" and its
    Intrigue cards [Rise of Ix p. 3]; "We recommend that you do not add the
    Conflict cards from RISE OF IX" [Main p. 18], which the user chose not to
    (plan 19.4 P7-3 (가)); Boundless Ambition, the promo, only with
    ``promo_cards``; the six Leaders join the offer."""

    content = content_for(IX)
    ix_ids = {
        entry.card.card_id
        for entry in IX_IMPERIUM_CARDS
        if GameOption.PROMO_CARDS not in entry.requires
    }
    in_deck = {
        instance.split(":")[1] for instance in content.imperium_deck_instance_ids
    }
    assert ix_ids <= in_deck
    assert "boundless_ambition" not in in_deck
    promo = content_for(replace(IX, promo_cards=True))
    assert "boundless_ambition" in {
        instance.split(":")[1] for instance in promo.imperium_deck_instance_ids
    }
    intrigue = {
        instance.split(":")[1] for instance in content.intrigue_deck_instance_ids
    }
    assert {entry.card.card_id for entry in IX_INTRIGUE_CARDS} <= intrigue
    assert IX_LEADER_IDS_OFFERED <= {leader.leader_id for leader in content.leaders}

    ix_conflicts = {conflict.card.card_id for conflict in IX_CONFLICTS}
    uprising = {conflict.card.card_id for conflict in CONFLICTS}
    _, state = _start()
    drawn = {*state.conflict_deck, *state.unused_conflict_ids}
    assert not drawn & ix_conflicts
    assert drawn <= uprising
    assert "economic_supremacy" not in drawn


def test_epic_game_mode_adds_only_economic_supremacy() -> None:
    """ "you will need one additional Conflict III card to play the Epic Game
    Mode. In this situation, you should add Economic Supremacy." [Main p. 18]
    -- Uprising's own Epic card (epic-game-mode.md); no other Rise of Ix
    Conflict (P7-3 (가))."""

    epic = replace(IX, epic_game=True)
    _, state = _start(epic)
    drawn = {*state.conflict_deck, *state.unused_conflict_ids}
    assert "economic_supremacy" in drawn
    assert not drawn & {conflict.card.card_id for conflict in IX_CONFLICTS}
    assert state.players[0].troops_garrison == 5


def test_ilesa_ecaz_has_the_original_foldspace_stack() -> None:
    """ "Using Ilesa Ecaz requires the Foldspace cards from DUNE: IMPERIUM.
    (Allow Ilesa Ecaz to acquire Foldspace cards, even though they can't be
    acquired by anyone else.)" [Main p. 18]: the six Foldspace cards wait in
    the Reserve, where no purchase reaches them, and her Guild Contacts
    ("1 Solari → Foldspace 획득", rise-of-ix.md 10) takes one."""

    engine, state = _start(
        leader_ids=(
            "ilesa_ecaz",
            "gurney_halleck",
            "lady_amber_metulli",
            "lady_jessica",
        )
    )
    assert dict(state.reserve_stacks)["foldspace_card"] == 6
    foldspace = next(
        stack for stack in content_for(IX).reserve_stacks if stack.icon_only
    )
    assert foldspace.card.card_id == "foldspace_card"
    # Nobody buys it in a Reveal turn: only the plain Reserve stacks are rows.
    codec = _codec(IX)
    assert not any(
        template.action_id in ("acquire_reserve", "acquire_reserve_with_solari")
        and dict(template.arguments).get("card_id") == "foldspace_card"
        for template in codec.catalog
    )
    # Her Signet Ring offers it (after her One Step Ahead set-aside, the
    # round's first decision while she is the First Player).
    set_aside = next(
        row
        for row in engine.legal_actions(state, 0)
        if row.action_id == "set_aside_leader_card"
        and dict(row.arguments)["card_id"] == "player:0:starter:dagger:1"
    )
    state = engine.apply(state, set_aside).state
    state = _seat(state, 0, resources=Resources(water=1, solari=2))
    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == "player:0:starter:signet_ring:0"
    )
    placed = apply_placement(engine, state, placement).state
    rows = {
        (row.action_id, dict(row.arguments).get("card_id"))
        for row in engine.whole_actions(placed, 0)
    }
    assert ("acquire_leader_reserve", "foldspace_card") in rows


@pytest.mark.parametrize(
    "options",
    [
        {"bloodlines": True, "tech_module": True},
        {"choam_module": True},
        {"arrakeen_scouts": True},
        {"choam_module": True, "arrakeen_scouts": True, "immortality": True},
    ],
)
def test_setup_takes_every_option(options: dict[str, bool]) -> None:
    """Stage P7f-2 opened the last three: the Tech Module, the CHOAM module
    and Arrakeen Scouts (``test_uprising_ix_options``)."""

    config = replace(IX, **options)  # type: ignore[arg-type]
    assert UprisingRulesEngine().reset(config, 1).config == config


def test_bloodlines_commanders_move_off_the_covered_spaces() -> None:
    """ "Rise of Ix를 모두 쓸 때 CHOAM 덮개가 Sardaukar Commander 자리 둘을
    덮으므로, setup에서 Commander 하나를 Dreadnought 칸에, 4인 판이면 다른
    하나를 Tech Negotiation 칸에 둔다" (rise-of-ix.md 10a, [Bloodlines p. 7]):
    on Uprising those are Gather Support's and Assembly Hall's, which the
    half overlay covers [Main p. 18]."""

    state = UprisingRulesEngine().reset(replace(IX, bloodlines=True), 1)
    assert state.sardaukar_commander_space_ids == (
        "sardaukar",
        "dutiful_service",
        "deliver_supplies",
        "high_council",
        "dreadnought",
        "tech_negotiation",
    )
    assert state.sardaukar_commanders_bank == 1


# --- Observation posts -----------------------------------------------------------


def test_two_observation_posts_join_and_the_covered_two_go() -> None:
    """ "Play as if there is one observation post on each of those boards: one
    observation post connects to Interstellar Shipping and Smuggling and the
    other connects to Tech Negotiation and Dreadnought." [Main p. 18]. The
    overlay covers "only the top-right corner of the UPRISING board" there,
    where the Landsraad post between Assembly Hall and Gather Support and the
    CHOAM post between Shipping and Accept Contract connect to covered spaces
    only: both go with them, and the corner's one post is the overlay's own
    (OQ-159, resolved by the rulebook)."""

    _, state = _start()
    posts = observation_post_ids_in_play(state)
    assert posts == (
        *(
            post.post_id
            for post in OBSERVATION_POSTS
            if post.post_id not in (COVERED_POST, COVERED_CHOAM_POST)
        ),
        SHIPPING_POST,
        NEGOTIATION_POST,
    )
    assert {
        post.post_id: post.connected_space_ids for post in IX_OBSERVATION_POSTS
    } == {
        SHIPPING_POST: ("interstellar_shipping", "smuggling"),
        NEGOTIATION_POST: ("tech_negotiation", "dreadnought"),
    }
    assert COVERED_POST not in empty_observation_post_ids(state)
    assert COVERED_CHOAM_POST not in empty_observation_post_ids(state)
    assert {SHIPPING_POST, NEGOTIATION_POST} <= set(empty_observation_post_ids(state))
    # "[Spy] on [Landsraad]" reaches the Tech Negotiation and Dreadnought post
    # (both Landsraad spaces [Rise of Ix p. 12]); Spice Trade the other.
    assert NEGOTIATION_POST in observation_post_ids_for_agent_icons(
        (AgentIcon.LANDSRAAD,)
    )
    assert SHIPPING_POST in observation_post_ids_for_agent_icons(
        (AgentIcon.SPICE_TRADE,)
    )
    # Uprising without Rise of Ix keeps its thirteen.
    _, plain = _start(RulesetConfig(first_player_seat_zero=True))
    assert observation_post_ids_in_play(plain) == tuple(
        post.post_id for post in OBSERVATION_POSTS
    )


def test_the_emperor_track_spy_may_go_on_a_new_post() -> None:
    """The Emperor track's Influence 4 Spy [Main p. 7] goes on any post of
    the board, the two counted ones included, never on the covered one: its
    window takes the game's posts (``spy_moves._open_track_spy``)."""

    engine, state = _start()
    state = _seat(state, 0, influence=Influence(emperor=3))
    gained = gain_faction_influence(state, 0, Faction.EMPEROR, 1, event_prefix="t")
    assert [seat for seat, _ in gained.state.pending_track_spies] == [0]
    window = spy_placement_frame(
        gained.state,
        0,
        observation_post_ids_in_play(gained.state),
        source="t",
        printer=printer_value(Source.INFLUENCE_TRACK, Faction.EMPEROR.value),
    )
    posts = {
        str(dict(row.arguments)["post_id"])
        for row in engine.legal_actions(window, 0)
        if "post_id" in dict(row.arguments)
    }
    assert {SHIPPING_POST, NEGOTIATION_POST} <= posts
    assert COVERED_POST not in posts
    assert COVERED_CHOAM_POST not in posts


def _occupied_smuggling(state: GameState, *, spy: bool = True) -> GameState:
    """Seat 1's Agent on Smuggling; seat 0 holds Dune, the Desert Planet
    (Spice Trade) and CHOAM Delegate (Spice Trade with the Infiltration icon
    [Rise of Ix p. 7]), and a Spy on the post Smuggling connects to."""

    state = _take(state, DELEGATE)
    owner = state.players[0]
    state = _seat(
        state,
        0,
        hand=(PLANET, DELEGATE),
        deck=tuple(card for card in owner.deck if card != PLANET),
        resources=Resources(water=1, spice=2, solari=4),
        spy_post_ids=(SHIPPING_POST,) if spy else (),
        spies_supply=2 if spy else 3,
    )
    other = state.players[1]
    return _seat(
        state,
        1,
        agent_locations=("smuggling",),
        agents_available=other.agents_available - 1,
    )


def _smuggling_rows(state: GameState, card: str) -> list[dict[str, object]]:
    return [
        dict(row.arguments)
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == card
        and dict(row.arguments)["space_id"] == "smuggling"
    ]


def test_a_spy_on_a_new_post_infiltrates_and_so_does_the_infiltration_icon() -> None:
    """Uprising's Infiltrate: "recall your Spy from an observation post
    connected to that space" to send an Agent where an opponent's Agent is
    [Main p. 11]; Rise of Ix's Infiltration icon lets the card's Agent
    "ignore opponents' Agents" on the icon's spaces [Rise of Ix p. 7]. Both
    reach Smuggling past seat 1's Agent (plan 17.5 item 4)."""

    engine, state = _start()
    state = _occupied_smuggling(state)
    engine.legal_actions(state, 0)

    planet = _smuggling_rows(state, PLANET)
    assert planet and all(
        row.get("infiltrate_post_id") == SHIPPING_POST for row in planet
    )
    delegate = _smuggling_rows(state, DELEGATE)
    assert any("infiltrate_post_id" not in row for row in delegate)

    # Without the Spy only the Infiltration icon opens it.
    bare = _occupied_smuggling(_start()[1], spy=False)
    assert _smuggling_rows(bare, PLANET) == []
    assert _smuggling_rows(bare, DELEGATE)


def test_neither_infiltration_passes_the_voice() -> None:
    """ "The Voice는 넘지 못한다" [Rise of Ix p. 7] and the Voice ruling [DI
    p. 13] (rise-of-ix.md 7, plan 17.5 item 4): with The Voice on Smuggling
    (the original card, in Uprising with ``imperium_cards``), neither the
    Spy's Infiltrate nor CHOAM Delegate's icon sends seat 0's Agent there."""

    _, state = _start(replace(IX, imperium_cards=True))
    state = _occupied_smuggling(state)
    assert _smuggling_rows(state, PLANET) and _smuggling_rows(state, DELEGATE)
    blocked = _seat(state, 0, voice_blocked_space_ids=("smuggling",))
    assert _smuggling_rows(blocked, PLANET) == []
    assert _smuggling_rows(blocked, DELEGATE) == []


# --- Dreadnoughts, sandworms and the Shield Wall ---------------------------------


def _combat(
    units: dict[int, tuple[int, int, int]],
    *,
    conflict_id: str = "skirmish_crysknife",
    tile: str | None = None,
    **seat_changes: object,
) -> GameState:
    """The Combat Intrigue rounds of an Uprising + Ix game: ``units`` (seat ->
    troops, dreadnoughts, sandworms; strength 2, 3 and 3) in the Conflict
    ``conflict_id``; ``seat_changes`` and the Tech ``tile`` go to seat 0."""

    state = UprisingRulesEngine().reset(IX, 3)
    if tile is not None:
        state = replace(
            state,
            tech_stacks=tuple(
                tuple(held for held in stack if held != tile)
                for stack in state.tech_stacks
            ),
        )
        state = _seat(state, 0, tech_ids=(tile,))
    state = replace(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
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
    for seat, (troops, dreadnoughts, sandworms) in units.items():
        owner = state.players[seat]
        state = _seat(
            state,
            seat,
            troops_garrison=owner.troops_garrison - troops,
            troops_conflict=troops,
            dreadnoughts_supply=owner.dreadnoughts_supply - dreadnoughts,
            dreadnoughts_conflict=dreadnoughts,
            sandworms_conflict=sandworms,
            combat_strength=2 * troops + 3 * dreadnoughts + 3 * sandworms,
        )
    if seat_changes:
        state = _seat(state, 0, **seat_changes)
    return begin_combat_intrigue(state).state


def _passed(engine: UprisingRulesEngine, state: GameState) -> GameState:
    while state.decision_stack and state.decision_stack[-1].kind == (
        FrameKind.COMBAT_INTRIGUE
    ):
        owner = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        (passed,) = (
            row
            for row in engine.legal_actions(state, owner)
            if row.action_id == "pass_combat_intrigue"
        )
        state = engine.apply(state, passed).state
    return state


def _resolve(engine: UprisingRulesEngine, state: GameState, effect: str) -> GameState:
    """Seat 0 resolves its reward window's ``effect`` row (a whole action)."""

    row = DomainAction("resolve_combat_reward_icon", 0, (("effect", effect),))
    assert row in engine.whole_actions(state, 0)
    return apply_whole(engine, state, row).state


def _window_icons(state: GameState) -> list[str]:
    context = dict(state.decision_stack[-1].context)
    return [icon for icon in str(context["icons"]).split(",") if icon]


def test_a_dreadnought_alone_fights_in_an_uprising_conflict() -> None:
    """ "A deployed dreadnought allows the same [strength, swords, Combat
    Intrigue], even if you have it in a conflict without any troops. However,
    a dreadnought in your garrison does none of these things" [FAQ p. 2]
    (rise-of-ix.md 17): a seat with only a dreadnought gets Combat Intrigue
    priority and wins on its 3 strength."""

    engine = CheckedEngine()
    state = _combat({1: (0, 1, 0)})
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_INTRIGUE
    assert frame.decision.owner == 1  # type: ignore[union-attr]
    assert state.players[1].combat_strength == 3
    window = _passed(engine, state)
    assert window.decision_stack[-1].decision.owner == 1  # type: ignore[union-attr]
    assert dict(window.decision_stack[-1].context)["rank"] == 1
    assert "dreadnought_control" in _window_icons(window)


def test_a_sandworm_doubles_the_reward_but_not_the_win_rows() -> None:
    """ "Most rewards can be doubled (but taking control of a location cannot,
    nor can battle icons on Conflict cards you win)" [Main p. 14]: the
    dreadnought's taking of a Control space is one row (rise-of-ix.md 17), and
    Strategic Push's pledge and Windtraps' water are the cards' own effects,
    not Conflict rewards (plan 17.10): one row each, paid once."""

    engine = CheckedEngine()
    state = _combat(
        {0: (1, 1, 1), 1: (1, 0, 0)},
        strategic_push_solari=2,
        tile="windtraps",
    )
    window = _passed(engine, state)
    context = dict(window.decision_stack[-1].context)
    assert (window.decision_stack[-1].decision.owner, context["rank"]) == (0, 1)  # type: ignore[union-attr]
    assert context["multiplier"] == 2
    icons = _window_icons(window)
    for row in ("dreadnought_control", "strategic_push", "windtraps"):
        assert icons.count(row) == 1, (row, icons)

    before = window.players[0].resources
    paid = _resolve(engine, window, "strategic_push")
    assert paid.players[0].resources.solari == before.solari + 2
    watered = _resolve(engine, paid, "windtraps")
    assert watered.players[0].resources.water == before.water + 1
    chosen = _resolve(engine, watered, "dreadnought_control")
    spaces = {
        dict(row.arguments).get("space_id")
        for row in engine.whole_actions(chosen, 0)
        if row.action_id == "place_combat_reward_dreadnought"
    }
    # Uprising's Control spaces [Main p. 10] (plan 17.5 item 1).
    assert spaces == {"arrakeen", "spice_refinery", "imperial_basin"}


def test_the_shield_wall_stops_sandworms_not_dreadnoughts() -> None:
    """ "no sandworms can be summoned to a Conflict at one of these three
    protected locations" [Main p. 10] (rise-of-ix.md 17): with the Shield Wall
    standing and the Siege of Arrakeen revealed, a garrison dreadnought
    still deploys with seat 0's Agent at Arrakeen, while a summon is
    blocked."""

    engine, state = _start()
    conflict = "siege_of_arrakeen"
    state = replace(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict
        ),
        current_conflict_ids=(conflict,),
    )
    assert state.shield_wall_present
    owner = state.players[0]
    state = _seat(
        state,
        0,
        hand=(RECON,),
        deck=tuple(card for card in owner.deck if card != RECON),
        dreadnoughts_supply=1,
        dreadnoughts_garrison=1,
        maker_hooks=True,
    )
    assert sandworm_block(state, 0) is SandwormBlock.SHIELD_WALL
    assert BOARD_SPACES_BY_ID["arrakeen"].combat
    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_placement(engine, state, placement).state
    deployments = legal_dreadnought_deployments(placed, 0)
    assert [dict(row.arguments)["count"] for row in deployments] == [1]
    deployed = engine.apply(placed, deployments[0]).state
    assert deployed.players[0].dreadnoughts_conflict == 1


# --- Uprising's unit cards ---------------------------------------------------------


def test_uprising_unit_cards_count_dreadnoughts_with_rise_of_ix() -> None:
    """ "There are two types of units: troops and sandworms. The RISE OF IX
    expansion includes another type of unit, called dreadnoughts." [Main
    p. 10]; "'unit'은 troop 또는 dreadnought다" [Rise of Ix p. 6]
    (rise-of-ix.md 6, plan 17.9): Distraction's "When you deploy three or more
    units to the Conflict in a single turn" counts this turn's dreadnoughts
    as Diversion's does; Calculating's kinds of unit take the dreadnought."""

    from dune_imperium.content.core.effects import (
        GainSolariPerUnitType,
        UnitsDeployedThisTurnAtLeast,
    )
    from dune_imperium.rules.combat_deployment import DEPLOYED_DREADNOUGHTS_KEY
    from dune_imperium.rules.frames import with_context

    _, state = _start()
    distraction = UnitsDeployedThisTurnAtLeast(3)
    state = _seat(state, 0, units_deployed_turn=2, units_deployed_peak=2)
    frame = next(
        frame
        for frame in reversed(state.decision_stack)
        if frame.kind == FrameKind.TURN
    )
    agent = replace(frame, kind=FrameKind.AGENT_EFFECTS)
    without = replace(state, decision_stack=(*state.decision_stack, agent))
    assert not condition_holds(without, 0, distraction)
    with_ship = replace(
        state,
        decision_stack=(
            *state.decision_stack,
            with_context(agent, {**dict(agent.context), DEPLOYED_DREADNOUGHTS_KEY: 1}),
        ),
    )
    assert condition_holds(with_ship, 0, distraction)
    # Uprising without the expansion reads the troops only (no seat has a
    # dreadnought there).
    plain = replace(
        with_ship,
        config=replace(with_ship.config, rise_of_ix=False),
        tech_stacks=(),
        players=tuple(
            replace(seat, dreadnoughts_supply=0, freighter_space=0)
            for seat in with_ship.players
        ),
    )
    assert not condition_holds(plain, 0, distraction)

    owner = _seat(
        state,
        0,
        troops_conflict=1,
        troops_garrison=2,
        dreadnoughts_conflict=1,
        dreadnoughts_supply=1,
    )
    calculated = apply_rewards(owner, 0, (GainSolariPerUnitType(),), source="t").result
    assert (
        calculated.state.players[0].resources.solari
        == owner.players[0].resources.solari + 2
    )


# --- Tessia Vernius' Snoopers on the Uprising tracks ------------------------------


@pytest.mark.parametrize(
    ("faction", "spy", "intrigue"),
    [(Faction.EMPEROR, 1, 0), (Faction.BENE_GESSERIT, 0, 1)],
)
def test_a_snoopers_track_bonus_is_the_uprising_boards_four_bonus(
    faction: Faction, spy: int, intrigue: int
) -> None:
    """Tessia's second Snooper reward is "그 track의 4칸 보너스"
    (rise-of-ix.md 10), the bonus the base game's board prints: on Uprising's
    the Emperor's is the Spy and the Bene Gesserit's an Intrigue card [Main
    p. 7] (plan 17.10: the same gain path)."""

    _, state = _start(
        leader_ids=(
            "tessia_vernius",
            "gurney_halleck",
            "lady_amber_metulli",
            "lady_jessica",
        )
    )
    owner = state.players[0]
    assert len(owner.snooper_faction_ids) == 4
    # One token taken already: the next one reached pays reward 2.
    left = tuple(f for f in owner.snooper_faction_ids if f != Faction.FREMEN.value)
    influence = (
        Influence(emperor=1)
        if faction is Faction.EMPEROR
        else Influence(bene_gesserit=1)
    )
    # Outside the seat's own turn: the bonus is paid at once.
    state = replace(state, decision_stack=())
    state = _seat(state, 0, snooper_faction_ids=left, influence=influence)
    gained = gain_faction_influence(state, 0, faction, 1, event_prefix="t").state
    assert len(gained.pending_track_spies) == spy
    assert len(gained.players[0].intrigue_cards) == len(owner.intrigue_cards) + intrigue


# --- Costs that trash an Unload card ------------------------------------------------


def _scouts_trash(card: str) -> tuple[GameState, list[str]]:
    """Seat 0 holding only ``card`` answers Funeral Rites' "trash a card from
    your hand" line (a cost, ``TrashCard`` [Scouts event: Funeral Rites]) in
    an Uprising + Ix game with Arrakeen Scouts (setup still refuses the
    combination, so the state is the Uprising + Ix one with the option on)."""

    engine = UprisingRulesEngine()
    state = engine.reset(IX, 3)
    state = replace(state, config=replace(state.config, arrakeen_scouts=True))
    state = _take(state, card)
    owner = state.players[0]
    state = _seat(
        state,
        0,
        hand=(card,),
        deck=(*owner.deck, *owner.hand),
        resources=Resources(),
    )
    state = push_scouts_effect(
        replace(state, decision_stack=()), 0, "funeral_rites", 0, source="t"
    )
    (row,) = engine.whole_actions(state, 0)
    assert row.action_id == "scouts_trash_card"
    result = apply_whole(engine, state, row)
    return result.state, [event.kind for event in result.events]


def test_a_scouts_trash_cost_pays_the_unload_box_at_once() -> None:
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한
    뒤 오른쪽으로 간다" (designer ruling, docs/rules/rise-of-ix.md 7; plan 17
    "P7 점검 목록"): Water Peddler's box (water) is paid inside the trash, and
    Freighter Fleet's Freighter, a decision, holds the line under its window
    (``rules.unload``)."""

    paid, events = _scouts_trash("imperium:water_peddler:0")
    assert "card_unloaded" in events
    assert paid.players[0].resources.water > 0

    held, _ = _scouts_trash("imperium:freighter_fleet:0")
    kinds = [frame.kind for frame in held.decision_stack]
    assert FrameKind.UNLOAD_ICONS in kinds


def test_no_unload_card_can_pay_a_reveal_trash_cost() -> None:
    """The Reveal choices' "trash → reward" lines (``reveal_turn.
    resolve_target_reward``) trash "this card" or Calculus of Power's other
    Emperor card in play; they now pay an Unload box at once, but no Unload
    card can be their target -- none is an Emperor card and none prints a
    trash cost of its own -- so the path has no hold to push."""

    from dune_imperium.content.core.effects import TrashCard
    from dune_imperium.content.registry.imperium import IMPERIUM_CARDS_BY_ID
    from dune_imperium.content.uprising.reveal_choice_abilities import (
        reveal_choice_ability,
    )

    unload = [entry for entry in IMPERIUM_CARDS_BY_ID.values() if entry.unload]
    assert len(unload) == 9
    for entry in unload:
        assert Faction.EMPEROR not in entry.factions
        for effect in card_reveal_choices(entry):
            ability = reveal_choice_ability(effect)
            assert not any(
                isinstance(cost, TrashCard)
                for section in ability.sections
                for cost in section.costs
            )


def test_the_catalog_holds_strongarms_troop_choice() -> None:
    """Strongarm (a Rise of Ix Intrigue) costs "Lose a troop", garrisoned or
    in the Conflict (OQ-036): the Uprising + Ix catalog holds the choice the
    original game's catalog has for its own cards (found by the P7f soak,
    random seed 18, without the Bloodlines or Immortality rows)."""

    rows = {(template.action_id, template.arguments) for template in _codec(IX).catalog}
    # The catalog lists the step rows its whole actions are shown by
    # (``effect_steps``), so the choice is ``choose_unit``.
    for zone in ("garrison", "conflict"):
        assert ("choose_unit", (("zone", zone),)) in rows



BOUNDLESS = "imperium:boundless_ambition:0"


def test_boundless_ambition_s_signet_box_does_nothing_for_steersman() -> None:
    """Boundless Ambition's Agent box is the Leader's Signet Ring ability
    [card face]; "Steersman Y'rkoon은 Signet Ring 카드 없이 시작하고 Signet
    자리의 Plot Course는 Signet Ring 능력을 인쇄하지 않으므로 아무 일도 일어나지
    않는다" (OQ-062 (c)), so for him the box can only fizzle and the turn
    ends on its press (a heuristic soak of Uprising + Ix + Bloodlines raised
    "this Leader's Signet Ring ability is not implemented" instead)."""

    config = replace(IX, bloodlines=True, promo_cards=True)
    leaders = ("steersman_y_rkoon", "ilesa_ecaz", "archduke_armand_ecaz", "muad_dib")
    engine = CheckedEngine(leader_ids=leaders)
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
            assert isinstance(decision, PlayerDecision)
            state = apply_whole(
                engine, state, engine.whole_actions(state, decision.owner)[0]
            ).state
    owner = state.players[0]
    assert owner.leader_id == "steersman_y_rkoon"
    state = replace(
        _take(state, BOUNDLESS),
        players=(replace(owner, hand=(*owner.hand, BOUNDLESS)), *state.players[1:]),
    )
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["card_id"] == BOUNDLESS
    )
    placed = apply_placement(engine, state, placement).state
    assert agent_card_effect_is_unavailable(placed)
    finish = DomainAction("finish_agent_turn", 0)
    while finish not in engine.whole_actions(placed, 0):
        step = next(
            row
            for row in engine.whole_actions(placed, 0)
            if row.action_id not in ("use_family_atomics", "return_specimen")
        )
        placed = apply_whole(engine, placed, step).state
    closed = apply_whole(engine, placed, finish).state
    frame = closed.decision_stack[-1]
    assert frame.kind == FrameKind.TURN
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 1
