"""Part of Rise of Ix beside the Tech Module (docs/base-game-and-ix-plan.md
20.5 P8-1).

The user's ruling (2026-11-01): "그 모든 조합이 가능하게 하자. 대신 아라킨
스카웃 활성화 했을 때는 ix 리더 + 기술 옵션 / ix 모든 옵션 이 중에서만 선택할
수 있고, 아라킨 스카웃 활성화 안 했을 때는 원래 공식 조합(기술만/모든옵션) + ix
리더 + 기술 옵션". With Bloodlines' Tech Module and Rise of Ix a game takes
all of Rise of Ix (``rise_of_ix``), its Tech tiles alone (``ix_tech_tiles``)
or its Leaders and Tech tiles (``ix_leaders`` too).

- The Tech tiles alone are official: "Rise of Ix의 Tech 타일만 쓸 때(Ix의 다른
  구성물 없이): Detonation Devices와 Troop Transports를 빼고 나머지 16장을
  Bloodlines 타일과 섞는다" [Bloodlines p. 7] (docs/rules/rise-of-ix.md 10a);
  "두 모듈의 Tech 타일을 모두 섞어 될 수 있는 대로 고르게 큰 더미 셋으로
  나눈다"; only "Rise of Ix를 모두 쓸 때" leaves the Ixian Embassy out.
- The Leaders and Tech mode is the Game Room app's ("I'm using only the
  Leaders and Tech tiles from Rise of Ix."), a project option: OQ-165 (user
  2026-11-01) -- the same 16 tiles, and the Leaders but Hundro Moritani and
  Rhombur Vernius, whose abilities need the Ix board.
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.content.arrakeen_scouts import (
    missions_for,
    scouts_pool,
    scouts_rise_of_ix,
)
from dune_imperium.content.bloodlines.tech import IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD
from dune_imperium.content.registry.tech import (
    TECH_TILES_BY_ID,
    ixian_embassy_in_play,
    tech_tile_pool,
)
from dune_imperium.content.rise_of_ix.board import IX_SPACE_IDS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.leaders import IX_LEADERS
from dune_imperium.content.rise_of_ix.tech import IX_TECH_IDS
from dune_imperium.content.rulesets import (
    IX_LEADER_IDS_OFFERED,
    IX_LEADER_IDS_WITHOUT_IX_BOARD,
    content_for,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.phases import draw_round_hands
from dune_imperium.rules.setup import create_initial_state, tech_tile_pool_of
from dune_imperium.rules.tech import (
    legal_tech_acquisition_actions,
    legal_tech_trash_actions,
    tech_cost,
)

UPRISING_TECH = RulesetConfig(bloodlines=True, tech_module=True)
ORIGINAL_TECH = replace(UPRISING_TECH, base_game=BaseGame.IMPERIUM)
HUNDRO = "viscount_hundro_moritani"
RHOMBUR = "prince_rhombur_vernius"
FOUR = {
    "archduke_armand_ecaz",
    "ilesa_ecaz",
    "princess_yuna_moritani",
    "tessia_vernius",
}
# Leaders with no setup pick of their own, on each board.
PLAIN_LEADERS = {
    BaseGame.UPRISING: (
        "feyd_rautha_harkonnen",
        "gurney_halleck",
        "lady_amber_metulli",
        "lady_jessica",
    ),
    BaseGame.IMPERIUM: (
        "paul_atreides",
        "duke_leto_atreides",
        "glossu_rabban",
        "chani",
    ),
}


def _tech(base: RulesetConfig, *, leaders: bool = False, **flags: Any) -> RulesetConfig:
    """``base`` with Rise of Ix's Tech tiles alone, or its Leaders too."""

    return replace(base, ix_tech_tiles=True, ix_leaders=leaders, **flags)


# --- The options and their combinations -------------------------------------


def test_the_three_modes_need_the_tech_module_and_exclude_each_other() -> None:
    # "Bloodlines Tech와 Ix를 함께 켰을 때" (the user's ruling): both parts
    # need the Tech Module, neither combines with all of Rise of Ix, and the
    # Leaders come only with the tiles (the ruling names no Leaders-only mode).
    with pytest.raises(ValueError, match="Tech Module"):
        RulesetConfig(bloodlines=True, ix_tech_tiles=True)
    with pytest.raises(ValueError, match="all of Rise of Ix"):
        _tech(UPRISING_TECH, rise_of_ix=True)
    with pytest.raises(ValueError, match="only its Tech tiles"):
        replace(UPRISING_TECH, ix_leaders=True)
    for base in (UPRISING_TECH, ORIGINAL_TECH):
        assert _tech(base).ix_tech_in_play and not _tech(base).ix_leaders_in_play
        assert _tech(base, leaders=True).ix_leaders_in_play
        assert not _tech(base, leaders=True).rise_of_ix


def test_arrakeen_scouts_takes_all_of_ix_or_its_leaders_and_tech() -> None:
    # User ruling 2026-11-01: "아라킨 스카웃 활성화 했을 때는 ix 리더 + 기술
    # 옵션 / ix 모든 옵션 이 중에서만 선택할 수 있고".
    for base in (UPRISING_TECH, ORIGINAL_TECH):
        with pytest.raises(ValueError, match="Arrakeen Scouts"):
            _tech(base, arrakeen_scouts=True)
        _tech(base, leaders=True, arrakeen_scouts=True)
        replace(base, rise_of_ix=True, arrakeen_scouts=True)


def test_identifiers_name_the_parts_and_leave_older_ones_alone() -> None:
    config = _tech(UPRISING_TECH, leaders=True)
    assert config.identifier == "uprising-4p-base+bloodlines+tech+ixtech+ixleaders"
    assert RulesetConfig.from_identifier(config.identifier) == config
    original = _tech(ORIGINAL_TECH)
    assert original.identifier == "imperium-4p-base+bloodlines+tech+ixtech"
    assert RulesetConfig.from_identifier(original.identifier) == original
    assert replace(UPRISING_TECH, rise_of_ix=True).identifier == (
        "uprising-4p-base+ix+bloodlines+tech"
    )


# --- The Tech tiles -----------------------------------------------------------


def test_the_tiles_alone_are_sixteen_beside_the_tech_modules() -> None:
    # [Bloodlines p. 7]: 16 Rise of Ix tiles, Detonation Devices and Troop
    # Transports out; the Tech Module's are its usual pool (CHOAM Transports
    # with CHOAM; the original board's 12 [Bloodlines p. 6]).
    def pool(base_game: BaseGame, **flags: bool) -> tuple[str, ...]:
        options = {"choam_module": False, "tech_module": True, "rise_of_ix": False}
        options.update(flags)
        return tech_tile_pool(base_game, ix_tech_tiles=True, **options)

    sixteen = set(IX_TECH_IDS) - {"detonation_devices", "troop_transports"}
    assert IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD == {
        "detonation_devices",
        "troop_transports",
    }
    assert len(sixteen) == 16
    for base_game, choam, size in (
        (BaseGame.UPRISING, True, 34),
        (BaseGame.UPRISING, False, 33),
        (BaseGame.IMPERIUM, False, 28),
    ):
        tiles = pool(base_game, choam_module=choam)
        assert len(tiles) == len(set(tiles)) == size
        assert set(tiles) & set(IX_TECH_IDS) == sixteen
        plain = tech_tile_pool(
            base_game, choam_module=choam, tech_module=True, rise_of_ix=False
        )
        assert set(tiles) - set(IX_TECH_IDS) == set(plain)


@pytest.mark.parametrize("leaders", [False, True])
@pytest.mark.parametrize(
    ("config", "sizes"),
    [
        (replace(UPRISING_TECH, choam_module=True), (12, 11, 11)),
        (UPRISING_TECH, (11, 11, 11)),
        (ORIGINAL_TECH, (10, 9, 9)),
    ],
)
def test_setup_deals_both_modules_onto_the_ixian_embassy(
    config: RulesetConfig, sizes: tuple[int, int, int], leaders: bool
) -> None:
    # "될 수 있는 대로 고르게 큰 더미 셋으로" [Bloodlines p. 7]; the Embassy
    # stays, as only "Rise of Ix를 모두 쓸 때" leaves it out; no Ix board, so
    # no dreadnought or Freighter (rise-of-ix.md 10a).
    config = _tech(config, leaders=leaders)
    state = create_initial_state(config, 5, PLAIN_LEADERS[config.base_game]).state
    assert tuple(len(stack) for stack in state.tech_stacks) == sizes
    dealt = sorted(tile for stack in state.tech_stacks for tile in stack)
    assert dealt == sorted(tech_tile_pool_of(config))
    assert ixian_embassy_in_play(config)
    for seat in state.players:
        assert seat.dreadnoughts_supply == 0
        assert seat.freighter_space == 0
    assert not set(IX_SPACE_IDS) & {
        space.space_id for space in content_for(config).board_spaces
    }


# --- The Leaders and the rest of Rise of Ix ------------------------------------


def test_the_leaders_mode_offers_four_ix_leaders_without_hundro_and_rhombur() -> None:
    # OQ-165 (user 2026-11-01): Hundro Moritani (Couriers: spice 1 ->
    # Freighter, no Shipping track) and Rhombur Vernius (dreadnoughts, Tech
    # Negotiation, no Ix board) are left out; the other four call no Ix
    # component (rise-of-ix.md 10).
    assert IX_LEADER_IDS_WITHOUT_IX_BOARD == FOUR
    assert FOUR | {HUNDRO, RHOMBUR} == IX_LEADER_IDS_OFFERED
    ix_ids = {leader.leader_id for leader in IX_LEADERS}
    for base in (UPRISING_TECH, ORIGINAL_TECH):
        leaders = {leader.leader_id for leader in content_for(_tech(base)).leaders}
        assert not leaders & ix_ids
        leaders = {
            leader.leader_id
            for leader in content_for(_tech(base, leaders=True)).leaders
        }
        assert leaders & ix_ids == FOUR
        everything = content_for(replace(base, rise_of_ix=True)).leaders
        assert {leader.leader_id for leader in everything} & ix_ids == ix_ids


@pytest.mark.parametrize("leaders", [False, True])
@pytest.mark.parametrize("base", [UPRISING_TECH, ORIGINAL_TECH])
def test_no_other_rise_of_ix_component_joins(
    base: RulesetConfig, leaders: bool
) -> None:
    # "Ix의 다른 구성물 없이" [Bloodlines p. 7]; the app's "only the Leaders and
    # Tech tiles": no Ix board, Conflict, Imperium or Intrigue card, contract,
    # or the Ix promo Boundless Ambition (``promo_cards`` on).
    base = replace(base, promo_cards=True, immortality=True)
    plain = content_for(base)
    content = content_for(_tech(base, leaders=leaders))
    assert content.board_spaces == plain.board_spaces
    assert content.conflict_pool == plain.conflict_pool
    assert content.imperium_deck_instance_ids == plain.imperium_deck_instance_ids
    assert content.intrigue_deck_instance_ids == plain.intrigue_deck_instance_ids
    assert content.ix_contract_instance_ids == ()
    ix_cards = {
        entry.card.card_id for entry in (*IX_IMPERIUM_CARDS, *IX_INTRIGUE_CARDS)
    }
    decks = {
        instance.split(":")[1]
        for instance in (
            *content.imperium_deck_instance_ids,
            *content.intrigue_deck_instance_ids,
        )
    }
    assert not decks & ix_cards
    assert "boundless_ambition" not in decks


def test_uprising_takes_the_foldspace_stack_for_ilesa_ecaz() -> None:
    # "Using Ilesa Ecaz requires the Foldspace cards from DUNE: IMPERIUM"
    # [Main p. 18] (rise-of-ix.md 17): with her among the Leaders, Uprising's
    # Reserve takes the original Foldspace stack, as with all of Rise of Ix.
    stacks = [
        stack.card.card_id
        for stack in content_for(_tech(UPRISING_TECH, leaders=True)).reserve_stacks
    ]
    assert stacks[-1] == "foldspace_card"
    tiles_only = content_for(_tech(UPRISING_TECH)).reserve_stacks
    assert "foldspace_card" not in {stack.card.card_id for stack in tiles_only}


def test_the_scouts_pool_is_the_one_without_rise_of_ix() -> None:
    # The Game Room app drops Rise of Ix's bit from the pool with "Leaders and
    # Tech only" (plan 20.1 items 3 and 6): no Ix mission; all of Rise of Ix
    # keeps its pool.
    for base in (UPRISING_TECH, ORIGINAL_TECH):
        config = _tech(base, leaders=True, arrakeen_scouts=True)
        assert not scouts_rise_of_ix(config)
        everything = replace(base, rise_of_ix=True, arrakeen_scouts=True)
        assert scouts_rise_of_ix(everything)
        missions = missions_for(scouts_pool(config), choam=False, rise_of_ix=False)
        assert not any(mission.rise_of_ix_only for mission in missions)


@pytest.mark.parametrize("leaders", [False, True])
def test_epic_takes_the_parts_on_uprising_only(leaders: bool) -> None:
    # Epic Game Mode "is Rise of Ix's" [Rise of Ix p. 10] (rise-of-ix.md 11):
    # the original game takes it with all of Rise of Ix only, and these modes
    # are "Ix의 다른 구성물 없이" (decision 2026-11-01, plan 20.5
    # P8-1). Uprising takes Epic alone (OQ-092), so with them too.
    engine = UprisingRulesEngine(leader_ids=PLAIN_LEADERS[BaseGame.IMPERIUM])
    with pytest.raises(NotImplementedError, match="epic_game only with rise_of_ix"):
        engine.reset(_tech(ORIGINAL_TECH, leaders=leaders, epic_game=True), 3)
    engine = UprisingRulesEngine(leader_ids=PLAIN_LEADERS[BaseGame.UPRISING])
    state = engine.reset(_tech(UPRISING_TECH, leaders=leaders, epic_game=True), 3)
    assert state.config.epic_game


# --- Rules on the Ixian Embassy -------------------------------------------------


def _first_turn(
    config: RulesetConfig, stacks: tuple[tuple[str, ...], ...]
) -> GameState:
    """Seat 0's first turn of round one with its whole deck in hand, 10
    Solari, 9 spice and two Influence everywhere, the Tech stacks ``stacks``."""

    engine = UprisingRulesEngine(leader_ids=PLAIN_LEADERS[config.base_game])
    state = engine.reset(replace(config, first_player_seat_zero=True), 5)
    chance = ChanceResolver(seed=5)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    owner = state.players[0]
    owner = replace(
        owner,
        hand=(*owner.hand, *owner.deck),
        deck=(),
        resources=Resources(solari=10, spice=9, water=2),
        influence=Influence(emperor=2, spacing_guild=2, bene_gesserit=2, fremen=2),
    )
    return replace(
        state,
        players=(owner, *state.players[1:]),
        tech_stacks=stacks,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(
                state.decision_stack[-1],
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
        first_player=0,
    )


def test_a_high_council_visit_buys_an_ix_tile_at_the_embassys_discount() -> None:
    # "Landsraad board space에 Agent를 보낸 turn에 Tech tile 하나를 acquire할 수
    # 있다"; "High Council 자리가 있으면 ... tile마다 spice 1을 덜 낸다"
    # [Bloodlines pp. 7, 12] (bloodlines.md 5) -- for a Rise of Ix tile on the
    # Embassy too, with no Negotiator to return.
    config = _tech(ORIGINAL_TECH)
    state = _first_turn(config, (("minimic_film",), ("windtraps",), ("chaumurky",)))
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "imperium_high_council"
    )
    state = apply_agent_action(state, action).state
    for effect in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, effect).state
    owner = state.players[0]
    assert owner.high_council
    assert tech_cost(owner, TECH_TILES_BY_ID["chaumurky"]) == 3
    rows = legal_tech_acquisition_actions(state, 0)
    offered = {dict(row.arguments).get("tech_id") for row in rows}
    assert offered >= {"minimic_film", "windtraps", "chaumurky"}
    assert not any("negotiators" in dict(row.arguments) for row in rows)


def test_ix_tiles_round_start_lines_pay_without_the_ix_board() -> None:
    # Holtzman Engine "Round Start: 카드 1장", Shuttle Fleet "Round Start: 2
    # Solari" (rise-of-ix.md 4, OQ-122) are the tiles', not the board's.
    state = create_initial_state(
        _tech(ORIGINAL_TECH), 3, PLAIN_LEADERS[BaseGame.IMPERIUM]
    ).state
    players = list(state.players)
    players[0] = replace(players[0], tech_ids=("holtzman_engine",), hand=())
    players[1] = replace(players[1], tech_ids=("shuttle_fleet",), hand=())
    state = replace(
        state,
        players=tuple(players),
        tech_stacks=((), (), ()),
        phase=GamePhase.ROUND_START,
        round_number=2,
        first_player=0,
        decision_stack=(),
    )
    solari = state.players[1].resources.solari
    after = draw_round_hands(state).state
    assert len(after.players[0].hand) == 6
    assert after.players[1].resources.solari == solari + 2


def test_spy_satellites_trash_is_offered_without_the_ix_board() -> None:
    # "Spy Satellites: spice 3 + 이 타일 trash -> 1 VP(자기 turn에)" (rise-of-ix.md
    # 4): a tile's ability, offered in the owner's turn.
    config = _tech(UPRISING_TECH)
    state = _first_turn(config, ((), (), ()))
    owner = replace(state.players[0], tech_ids=("spy_satellites",))
    state = replace(state, players=(owner, *state.players[1:]))
    rows = legal_tech_trash_actions(state, 0)
    assert DomainAction("trash_tech", 0, (("tech_id", "spy_satellites"),)) in rows


# --- The Leaders on a game without the Ix board -------------------------------


def _round_one(config: RulesetConfig, leaders: tuple[str, ...]) -> GameState:
    """The game until the first player decision of round one (chance first)."""

    engine = UprisingRulesEngine(leader_ids=leaders)
    state = engine.reset(config, 7)
    chance = ChanceResolver(seed=7)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return state


@pytest.mark.parametrize("base", [UPRISING_TECH, ORIGINAL_TECH])
def test_ilesa_sets_a_card_aside_and_tessia_takes_her_snoopers(
    base: RulesetConfig,
) -> None:
    # One Step Ahead: "Round Start에 손의 카드 하나를 따로 둔다" (rise-of-ix.md
    # 10, OQ-122); Careful Observation: "시작에 Snooper token을 각 track의
    # Influence 2 칸에" -- the Leaders' own pieces, no Ix board needed.
    leaders = ("ilesa_ecaz", "tessia_vernius", "duncan_idaho", "chani")
    state = _round_one(_tech(base, leaders=True), leaders)
    assert state.phase is GamePhase.PLAYER_TURNS
    assert any(
        frame.kind == FrameKind.ROUND_START_SET_ASIDE for frame in state.decision_stack
    )
    tessia = next(seat for seat in state.players if seat.leader_id == "tessia_vernius")
    assert len(tessia.snooper_faction_ids) == 4


def test_the_catalogs_hold_the_parts_rows_only() -> None:
    # No Negotiator row without the Ix board and no row for the two tiles
    # left out; Ilesa's set-aside rows only where she plays.
    def rows(config: RulesetConfig) -> set[tuple[str, tuple[tuple[str, object], ...]]]:
        return {
            (template.action_id, template.arguments)
            for template in ActionCodec(config).catalog
        }

    for base in (UPRISING_TECH, ORIGINAL_TECH):
        for leaders in (False, True):
            catalog = rows(_tech(base, leaders=leaders))
            assert ("choose_tech", (("tech_id", "minimic_film"),)) in catalog
            assert not any(
                dict(arguments).get("tech_id") in IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD
                for _, arguments in catalog
            )
            assert not any("negotiators" in dict(arguments) for _, arguments in catalog)
        everything = rows(replace(base, rise_of_ix=True))
        assert any("negotiators" in dict(arguments) for _, arguments in everything)


@pytest.mark.parametrize("leaders", [False, True])
def test_spaceport_puts_an_acquired_card_on_the_deck_in_the_catalog(
    leaders: bool,
) -> None:
    # Spaceport: "얻는 카드를 덱 위에 놓을 수 있다" (docs/rules/rise-of-ix.md 4) --
    # a tile's, so the deck-top twins of an acquisition stand in these
    # catalogs too: a Row or Reserve card on Uprising's board (a P8-1 gate
    # soak advertised them with no row), and the original board's Foldspace
    # space's card.
    def rows(config: RulesetConfig) -> set[tuple[str, tuple[tuple[str, object], ...]]]:
        return {
            (template.action_id, template.arguments)
            for template in ActionCodec(config).catalog
        }

    uprising = rows(_tech(UPRISING_TECH, leaders=leaders))
    assert (
        "choose_imperium_card",
        (("instance_id", "imperium:bombast:0"), ("to_deck_top", True)),
    ) in uprising
    assert (
        "choose_reserve_card",
        (("card_id", "prepare_the_way"), ("to_deck_top", True)),
    ) in uprising
    original = rows(_tech(ORIGINAL_TECH, leaders=leaders))
    assert (
        "acquire",
        (
            ("icon", "foldspace"),
            ("option", "deck_top"),
            ("printed", "foldspace"),
            ("source", "board_space"),
        ),
    ) in original
