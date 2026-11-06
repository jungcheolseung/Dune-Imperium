"""Bloodlines and its Tech Module on the original game (stage P7c).

Rules: docs/rules/bloodlines.md 2a ("When playing BLOODLINES with DUNE:
IMPERIUM" [Bloodlines p. 3]) and 5 (the Tech Module, the original game's
exclusion line [Bloodlines p. 6]); docs/rules/rise-of-ix.md 10a (Tech Module +
Rise of Ix [Bloodlines p. 7]); docs/base-game-and-ix-plan.md 19.2 row P7c.
"""

from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_SETUP_SPACE_IDS,
    COMMANDER_TOTAL,
    commander_setup_space_ids,
    skill_tile_instance_ids,
)
from dune_imperium.content.bloodlines.tech import (
    ORIGINAL_GAME_LEFT_OUT_TECH_IDS,
    TECH_IDS,
)
from dune_imperium.content.core.icons import AgentIcon
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.registry.board import BOARD_SPACES_BY_ID
from dune_imperium.content.registry.conflicts import CONFLICTS
from dune_imperium.content.registry.intrigue import navigation_card_instance_ids
from dune_imperium.content.registry.tech import (
    TECH_TILES_BY_ID,
    ixian_embassy_in_play,
    tech_tile_pool,
)
from dune_imperium.content.rise_of_ix.tech import IX_TECH_IDS
from dune_imperium.content.rulesets import content_for
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
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import ix_negotiators_returnable
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.combat_deployment import (
    apply_combat_deployment,
    apply_commander_deployment,
    apply_dreadnought_deployment,
    legal_combat_deployments,
    legal_commander_deployments,
    legal_dreadnought_deployments,
)
from dune_imperium.rules.dreadnought_commission import commission_dreadnought
from dune_imperium.rules.effects import BOARD_ICON_TECH
from dune_imperium.rules.navigation import (
    apply_navigation_play,
    begin_navigation_play,
    legal_navigation_play_actions,
)
from dune_imperium.rules.reveal_turn import TECH_PENDING_KEY, grant_late_reveal_effects
from dune_imperium.rules.setup import (
    create_draft_initial_state,
    create_initial_state,
    deal_tech_pool_stacks,
    tech_tile_pool_of,
)
from dune_imperium.rules.tech import (
    apply_tech_acquisition,
    ix_tech_cost,
    legal_tech_acquisition_actions,
    push_tech_acquisition,
    tech_cost,
)

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
BLOODLINES = replace(ORIGINAL, bloodlines=True)
TECH = replace(BLOODLINES, tech_module=True)
TECH_IX = replace(TECH, rise_of_ix=True)
# Leaders with no setup pick of their own (the Baron's Masterstroke, the
# Navigation cards and the Secret Project pause the setup).
PLAIN_LEADERS = ("paul_atreides", "duke_leto_atreides", "glossu_rabban", "chani")


# --- Commander setup spaces ----------------------------------------------------


def test_commander_setup_spaces_follow_the_board_and_rise_of_ix() -> None:
    # "Sardaukar Commander 다섯을 원판 칸 Conspire, Wealth, Foldspace, High
    # Council, Rally Troops에 하나씩 둔다. 4인이면 여섯째를 Hall of Oratory에
    # 둔다" [Bloodlines p. 3] (bloodlines.md 2a); "Rise of Ix를 모두 쓰면 덮개가
    # Rally Troops·Hall of Oratory를 덮으므로 그 둘의 Commander를 Dreadnought와
    # (4인) Tech Negotiation으로 옮긴다" (2a, [Bloodlines p. 7], rise-of-ix.md
    # 10a). On Uprising's board the overlay covers Gather Support and Assembly
    # Hall [Main p. 18] (rise-of-ix.md 17).
    assert commander_setup_space_ids(BaseGame.UPRISING, rise_of_ix=False) == (
        COMMANDER_SETUP_SPACE_IDS
    )
    assert commander_setup_space_ids(BaseGame.IMPERIUM, rise_of_ix=False) == (
        "conspire",
        "wealth",
        "foldspace",
        "imperium_high_council",
        "rally_troops",
        "hall_of_oratory",
    )
    assert commander_setup_space_ids(BaseGame.IMPERIUM, rise_of_ix=True) == (
        "conspire",
        "wealth",
        "foldspace",
        "imperium_high_council",
        "dreadnought",
        "tech_negotiation",
    )
    assert commander_setup_space_ids(BaseGame.UPRISING, rise_of_ix=True) == (
        "sardaukar",
        "dutiful_service",
        "deliver_supplies",
        "high_council",
        "dreadnought",
        "tech_negotiation",
    )
    # Five printed spaces; the sixth is the four-player one.
    assert commander_setup_space_ids(BaseGame.IMPERIUM, rise_of_ix=True, players=3) == (
        "conspire",
        "wealth",
        "foldspace",
        "imperium_high_council",
        "dreadnought",
    )
    for base_game in BaseGame:
        for rise_of_ix in (False, True):
            config = RulesetConfig(base_game=base_game, rise_of_ix=rise_of_ix)
            board = {space.space_id for space in content_for(config).board_spaces}
            if base_game is BaseGame.UPRISING and rise_of_ix:
                # Uprising's board takes the overlay in another lane (P7f).
                board |= {"dreadnought", "tech_negotiation"}
            assert (
                set(commander_setup_space_ids(base_game, rise_of_ix=rise_of_ix))
                <= board
            )


@pytest.mark.parametrize(
    ("config", "spaces"),
    [
        (
            BLOODLINES,
            (
                "conspire",
                "wealth",
                "foldspace",
                "imperium_high_council",
                "rally_troops",
                "hall_of_oratory",
            ),
        ),
        (
            replace(BLOODLINES, rise_of_ix=True),
            (
                "conspire",
                "wealth",
                "foldspace",
                "imperium_high_council",
                "dreadnought",
                "tech_negotiation",
            ),
        ),
    ],
)
def test_setup_places_six_commanders_and_banks_the_seventh(
    config: RulesetConfig, spaces: tuple[str, ...]
) -> None:
    state = create_initial_state(config, 5, PLAIN_LEADERS).state
    assert state.sardaukar_commander_space_ids == spaces
    # "마지막 하나는 bank에 둔다" [Bloodlines p. 3].
    assert state.sardaukar_commanders_bank == COMMANDER_TOTAL - 6 == 1
    draft = create_draft_initial_state(replace(config, leader_draft=True), 5).state
    assert draft.sardaukar_commander_space_ids == spaces


# --- What the original game leaves out (2a) -----------------------------------


def test_setup_leaves_out_both_fierce_skills_and_the_spy_navigation_card() -> None:
    # "2단계: "Fierce" Sardaukar Commander Skill 둘을 뺀다"; "Steersman Y'rkoon을
    # 쓰면 Spy를 놓거나 회수하는 Navigation 카드를 뺀다" [Bloodlines p. 3]
    # (bloodlines.md 2a) -- Navigation card 2 places a Spy or recalls one.
    state = create_initial_state(BLOODLINES, 5, PLAIN_LEADERS).state
    skills = (*state.skill_face_up, *state.skill_stack)
    assert sorted(skills) == sorted(skill_tile_instance_ids(BaseGame.IMPERIUM))
    assert len(skills) == 12
    assert not any(skill.startswith("skill:fierce:") for skill in skills)
    assert len(skill_tile_instance_ids()) == 14
    assert sorted(state.navigation_stock) == sorted(
        navigation_card_instance_ids(BaseGame.IMPERIUM)
    )
    assert "intrigue:navigation_card_2:0" not in state.navigation_stock
    assert len(state.navigation_stock) == 9
    assert len(navigation_card_instance_ids()) == 10


def test_the_original_decks_take_bloodlines_cards_but_the_left_out_ones() -> None:
    # "3단계를 건너뛴다: Bloodlines의 새 Conflict 카드를 넣지 않는다. 4단계: CHOAM
    # 모듈 구성물을 모두 빼고, Intrigue 다섯(False Orders, Grasp Arrakis, Insider
    # Information, Ripples in the Sand, Sleeper Unit), Imperium 일곱(Arrakis
    # Observer, Eliminate Allies, Holy War, Intelligence Training 둘, Pointing the
    # Way, Shrouded Counsel), 지도자 셋(Count Hasimir Fenring, Gaius Helen
    # Mohiam, Liet Kynes)을 뺀다" [Bloodlines p. 3] (bloodlines.md 2a).
    plain = content_for(ORIGINAL)
    content = content_for(BLOODLINES)
    added_imperium = set(content.imperium_deck_instance_ids) - set(
        plain.imperium_deck_instance_ids
    )
    added_intrigue = set(content.intrigue_deck_instance_ids) - set(
        plain.intrigue_deck_instance_ids
    )
    # Bloodlines' 25 Imperium cards less the seven; its 15 Intrigue less five.
    assert len(added_imperium) == 25 - 7 == 18
    assert len(added_intrigue) == 15 - 5 == 10
    for card_id in (
        "arrakis_observer",
        "eliminate_allies",
        "holy_war",
        "intelligence_training",
        "pointing_the_way",
        "shrouded_counsel",
        # The CHOAM Module's.
        "choam_demands",
        "corrupt_bureaucrat",
        "delivery_logistics",
        "mercantile_affairs",
        # The Tech Module's and the promo, without their options.
        "ixian_ambassador",
        "ruthless_leadership",
    ):
        assert not any(f":{card_id}:" in card for card in added_imperium), card_id
    for card_id in (
        "false_orders",
        "grasp_arrakis",
        "insider_information",
        "ripples_in_the_sand",
        "sleeper_unit",
        "coercive_negotiation",
        "battlefield_research",
        "rapid_engineering",
    ):
        assert not any(f":{card_id}:" in card for card in added_intrigue), card_id
    assert "imperium:sardaukar_standard:0" in added_imperium
    assert "intrigue:honor_guard:0" in added_intrigue
    leaders = [leader.leader_id for leader in content.leaders]
    assert leaders[8:] == [
        "chani",
        "duncan_idaho",
        "esmar_tuek",
        "piter_de_vries",
        "steersman_y_rkoon",
    ]
    # No Bloodlines Conflict card, no CHOAM contract.
    assert content.conflicts == plain.conflicts
    assert not set(content.conflict_pool) - set(plain.conflict_pool)
    bloodlines_conflicts = {
        conflict.card.card_id
        for conflict in CONFLICTS
        if (GameOption.BLOODLINES in conflict.requires)
    }
    assert bloodlines_conflicts
    assert not bloodlines_conflicts & {
        conflict.card.card_id for conflict in content.conflict_pool
    }
    assert content.contract_instance_ids == ()
    # Esmar Tuek's Tuek's Sietch joins the board, on the table with him only
    # [Bloodlines p. 12].
    assert content.board_spaces[-1] is BOARD_SPACES_BY_ID["tuek_sietch"]
    assert content.maker_bonus_spice_for(("esmar_tuek",))[-1] == ("tuek_sietch", 0)


def test_the_tech_module_adds_its_cards_kota_odax_and_the_promo_its_card() -> None:
    # "Tech 전용 Intrigue 2장과 Imperium 2장을 각 deck에 섞고, Kota Odax of Ix를
    # Leader로 고를 수 있다" [Bloodlines p. 6] (bloodlines.md 5); the promo
    # Ruthless Leadership with ``promo_cards`` (bloodlines.md 1).
    content = content_for(TECH)
    assert {"imperium:ixian_ambassador:0", "imperium:ixian_ambassador:1"} <= set(
        content.imperium_deck_instance_ids
    )
    assert {"intrigue:battlefield_research:0", "intrigue:rapid_engineering:0"} <= set(
        content.intrigue_deck_instance_ids
    )
    assert content.leaders[-1].leader_id == "kota_odax_of_ix"
    promo = content_for(replace(TECH, promo_cards=True))
    assert set(promo.imperium_deck_instance_ids) - set(
        content.imperium_deck_instance_ids
    ) == {
        "imperium:duncan_loyal_blade:0",
        "imperium:jessica_of_arrakis:0",
        "imperium:thumper:0",
        "imperium:ruthless_leadership:0",
    }


# --- The Tech tile pool ---------------------------------------------------------


def test_the_tech_tile_pool_of_every_board_and_module() -> None:
    # The Tech Module: 18 tiles, CHOAM Transports only with CHOAM [Bloodlines
    # pp. 2, 6]; on the original game "exclude Advanced Data Analysis,
    # Forbidden Weapons, Ornithopter Fleet, Panopticon, and Spy Drones"
    # [Bloodlines p. 6] and no CHOAM: 12. With Rise of Ix "두 모듈의 Tech 타일을
    # 모두 섞어 될 수 있는 대로 고르게 큰 더미 셋으로 나눈다" [Bloodlines p. 7]
    # (rise-of-ix.md 10a): 30 on the original board, 36 on Uprising's (35
    # without CHOAM).
    def pool(base_game: BaseGame, **flags: bool) -> tuple[str, ...]:
        options = {"choam_module": False, "tech_module": False, "rise_of_ix": False}
        options.update(flags)
        return tech_tile_pool(base_game, **options)

    assert pool(BaseGame.UPRISING) == pool(BaseGame.IMPERIUM) == ()
    assert len(pool(BaseGame.UPRISING, tech_module=True, choam_module=True)) == 18
    assert len(pool(BaseGame.UPRISING, tech_module=True)) == 17
    assert pool(BaseGame.UPRISING, rise_of_ix=True) == IX_TECH_IDS
    assert pool(BaseGame.IMPERIUM, rise_of_ix=True) == IX_TECH_IDS
    both = pool(BaseGame.UPRISING, tech_module=True, rise_of_ix=True, choam_module=True)
    assert len(both) == 36 and set(both) == {*TECH_IDS, *IX_TECH_IDS}
    assert len(pool(BaseGame.UPRISING, tech_module=True, rise_of_ix=True)) == 35
    original = pool(BaseGame.IMPERIUM, tech_module=True)
    assert len(original) == 12
    assert set(original) == set(TECH_IDS) - ORIGINAL_GAME_LEFT_OUT_TECH_IDS - {
        "choam_transports"
    }
    # The original board never takes CHOAM Transports (2a: no CHOAM component).
    assert pool(BaseGame.IMPERIUM, tech_module=True, choam_module=True) == original
    mixed = pool(BaseGame.IMPERIUM, tech_module=True, rise_of_ix=True)
    assert len(mixed) == 30 and set(mixed) == {*original, *IX_TECH_IDS}


@pytest.mark.parametrize(
    ("config", "sizes"),
    [
        (TECH, (4, 4, 4)),
        (TECH_IX, (10, 10, 10)),
        (replace(BLOODLINES, rise_of_ix=True), (6, 6, 6)),
    ],
)
def test_setup_deals_the_pool_into_three_even_stacks(
    config: RulesetConfig, sizes: tuple[int, int, int]
) -> None:
    state = create_initial_state(config, 5, PLAIN_LEADERS).state
    assert tuple(len(stack) for stack in state.tech_stacks) == sizes
    dealt = [tile for stack in state.tech_stacks for tile in stack]
    assert sorted(dealt) == sorted(tech_tile_pool_of(config))
    # Uprising's mixed 36 and 35 split as evenly.
    uprising = RulesetConfig(bloodlines=True, tech_module=True, rise_of_ix=True)
    assert [
        len(stack)
        for stack in deal_tech_pool_stacks(uprising, tech_tile_pool_of(uprising))
    ] == [12, 12, 11]
    with pytest.raises(ValueError, match="pool"):
        deal_tech_pool_stacks(config, tech_tile_pool_of(config)[1:])


def test_every_original_landsraad_space_is_a_landsraad_space() -> None:
    # The Ixian Embassy's offer reads the game's own board (plan 16.10 15):
    # Hall of Oratory, Rally Troops, Mentat, Swordmaster and High Council
    # print the Landsraad icon on the original board.
    landsraad = [
        space.space_id
        for space in content_for(TECH).board_spaces
        if space.agent_icon is AgentIcon.LANDSRAAD
    ]
    assert landsraad == [
        "hall_of_oratory",
        "rally_troops",
        "mentat",
        "imperium_swordmaster",
        "imperium_high_council",
    ]


# --- The Tech framework on the original board -----------------------------------

# Costs: Glowglobes 2, Training Depot 1 | Delivery Bay 3, Servo-Receivers 2 |
# Sardaukar High Command 7, Self-Destroying Messages 4.
ORIGINAL_STACKS = (
    ("glowglobes", "training_depot"),
    ("delivery_bay", "servo_receivers"),
    ("sardaukar_high_command", "self_destroying_messages"),
)
INTRIGUE_PRINTER = printer_value(Source.INTRIGUE, "battlefield_research")


def _first_turn(config: RulesetConfig, **seat: object) -> GameState:
    """Seat 0's first turn of round one, its whole starting deck in hand and
    ``seat``'s fields set, the Tech stacks ``ORIGINAL_STACKS`` (with
    ``rise_of_ix``, a Rise of Ix tile under two of them)."""

    engine = UprisingRulesEngine(leader_ids=PLAIN_LEADERS)
    state = engine.reset(config, 5)
    chance = ChanceResolver(seed=5)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    owner = state.players[0]
    owner = replace(
        owner,
        hand=(*owner.hand, *owner.deck),
        deck=(),
        resources=Resources(solari=10, spice=0, water=2),
        influence=Influence(emperor=2, spacing_guild=2, bene_gesserit=2, fremen=2),
    )
    owner = replace(owner, **seat)  # type: ignore[arg-type]
    stacks: tuple[tuple[str, ...], ...] = (
        ORIGINAL_STACKS if config.tech_module else state.tech_stacks
    )
    if config.rise_of_ix and config.tech_module:
        stacks = ((*stacks[0], "artillery"), (*stacks[1], "windtraps"), stacks[2])
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


def _placed(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_agent_action(state, action).state


def _pending_icons(state: GameState) -> tuple[str, ...]:
    icons = dict(state.decision_stack[-1].context)["pending_board_icons"]
    assert isinstance(icons, str)
    return tuple(icons.split(","))


@pytest.mark.parametrize(
    "space_id",
    [
        "hall_of_oratory",
        "rally_troops",
        "mentat",
        "imperium_swordmaster",
        "imperium_high_council",
    ],
)
def test_every_original_landsraad_visit_offers_the_ixian_embassys_tech(
    space_id: str,
) -> None:
    # "The Ixian Embassy board gives you this option each time you send an
    # Agent to a [Landsraad] board space" [Bloodlines p. 12] (bloodlines.md
    # 5): the original board's five Landsraad spaces.
    state = _placed(
        _first_turn(TECH, resources=Resources(solari=10, spice=2)), space_id
    )
    assert BOARD_ICON_TECH in _pending_icons(state)
    offered = {
        dict(action.arguments)["tech_id"]
        for action in legal_tech_acquisition_actions(state, 0)
    }
    assert "glowglobes" in offered


def test_a_non_landsraad_visit_offers_no_tile_on_the_original_board() -> None:
    state = _placed(_first_turn(TECH, resources=Resources(spice=2)), "secrets")
    assert BOARD_ICON_TECH not in _pending_icons(state)
    assert legal_tech_acquisition_actions(state, 0) == ()


def test_the_original_high_council_seat_takes_the_embassys_discount() -> None:
    # "If you have a High Council seat, each Tech tile costs you 1 less spice"
    # [Bloodlines p. 7] -- and the first visit counts, "Because he now has a
    # High Council seat, the Tech tile costs him 1 less Spice" [Bloodlines
    # p. 7]: the original High Council seat [DI p. 17].
    state = _placed(
        _first_turn(TECH, resources=Resources(solari=5, spice=1)),
        "imperium_high_council",
    )
    for action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, action).state
    owner = state.players[0]
    assert owner.high_council
    assert tech_cost(owner, TECH_TILES_BY_ID["glowglobes"]) == 1
    offered = {
        dict(action.arguments)["tech_id"]
        for action in legal_tech_acquisition_actions(state, 0)
    }
    assert offered == {"glowglobes"}


def test_with_rise_of_ix_no_landsraad_visit_offers_a_tile() -> None:
    # "Rise of Ix를 모두 쓸 때: Bloodlines의 Ixian Embassy 보드를 쓰지 않고 세
    # 더미를 Ix 보드에 둔다" [Bloodlines p. 7] (rise-of-ix.md 10a): no Embassy,
    # no Landsraad Acquire Tech.
    assert ixian_embassy_in_play(TECH)
    assert not ixian_embassy_in_play(TECH_IX)
    assert not ixian_embassy_in_play(replace(ORIGINAL, rise_of_ix=True))
    state = _placed(
        _first_turn(TECH_IX, resources=Resources(solari=10, spice=9)), "mentat"
    )
    assert BOARD_ICON_TECH not in _pending_icons(state)
    assert legal_tech_acquisition_actions(state, 0) == ()


def _offered(state: GameState) -> set[tuple[str, int]]:
    """The (tile, Negotiators returned) rows the engine offers seat 0, each
    encoded and decoded to itself by the game's catalog (the Negotiator rows
    of a Tech Module tile, stage P7c)."""

    codec = ActionCodec(state.config)
    rows = set()
    for action in UprisingRulesEngine().legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action
        if action.action_id == "choose_tech":
            arguments = dict(action.arguments)
            rows.add((str(arguments["tech_id"]), int(arguments.get("negotiators", 0))))
    return rows


def test_with_rise_of_ix_both_modules_tiles_take_negotiators_and_no_seat_discount() -> (
    None
):
    # "Tech Negotiation의 할인은 쓰고, High Council 자리에 따른 Ixian Embassy
    # 할인은 없다" [Bloodlines p. 7] (rise-of-ix.md 10a); a Negotiator takes
    # one spice off [Rise of Ix p. 4]; a card's Tech Discount icon one more
    # [Bloodlines pp. 7, 12].
    state = _first_turn(
        TECH_IX,
        resources=Resources(solari=10, spice=1),
        high_council=True,
        negotiators=2,
        troops_supply=7,
    )
    owner = state.players[0]
    glowglobes = TECH_TILES_BY_ID["glowglobes"]
    assert ix_tech_cost(owner, glowglobes, discount=0, negotiators=0) == 2
    pushed = push_tech_acquisition(
        state, 0, discount=1, source="test", printer=INTRIGUE_PRINTER
    ).state
    # Glowglobes 2 - 1 = 1: the spice or a Negotiator; Delivery Bay 3 - 1 = 2:
    # one Negotiator and the spice, or both; Sardaukar High Command 7 - 1 - 2
    # is out of reach. The High Council seat takes nothing off.
    assert _offered(pushed) == {
        ("glowglobes", 0),
        ("glowglobes", 1),
        ("delivery_bay", 1),
        ("delivery_bay", 2),
    }
    bought = apply_tech_acquisition(
        pushed,
        DomainAction(
            action_id="acquire_tech",
            actor=0,
            arguments=(("negotiators", 1), ("tech_id", "delivery_bay")),
        ),
    ).state
    seat = bought.players[0]
    assert seat.tech_ids == ("delivery_bay",)
    # 3 - 1 (the card) - 1 (the Negotiator) = 1 spice.
    assert seat.resources.spice == 0
    assert (seat.negotiators, seat.troops_supply) == (1, 8)
    assert bought.tech_stacks[1] == ("servo_receivers", "windtraps")


def test_with_rise_of_ix_kota_odaxs_secret_project_is_on_offer() -> None:
    # Kota Odax's Secret Project: "Tech tile을 acquire할 수 있을 때마다 이 tile을
    # 고를 수 있고, 비용이 spice 1 적다" (bloodlines.md 5) -- on the Ix board's
    # Acquire Tech too, with Negotiators; the tile may be a Rise of Ix one, as
    # the stacks mix both modules' [Bloodlines p. 7].
    def kota(spice: int) -> GameState:
        state = _first_turn(
            TECH_IX,
            resources=Resources(solari=10, spice=spice),
            secret_project_tech_id="flagship",
            negotiators=2,
            troops_supply=7,
        )
        return push_tech_acquisition(
            state, 0, discount=1, source="test", printer=INTRIGUE_PRINTER
        ).state

    # Flagship 8 - 1 (card) - 1 (Secret Project) - 2 = 4.
    assert not any(tech_id == "flagship" for tech_id, _ in _offered(kota(3)))
    assert ("flagship", 2) in _offered(kota(4))
    action = DomainAction(
        action_id="acquire_tech",
        actor=0,
        arguments=(("negotiators", 2), ("tech_id", "flagship")),
    )
    bought = apply_tech_acquisition(kota(4), action).state
    seat = bought.players[0]
    assert seat.secret_project_tech_id == ""
    assert seat.tech_ids == ("flagship",)
    assert seat.resources.spice == 0
    assert bought.tech_stacks == kota(4).tech_stacks
    # The seat's own view counts the Secret Project among the tiles its
    # Negotiators may still lower: Glowglobes alone on the stacks costs 1 at
    # the card's discount, Flagship 6.
    cheap = replace(kota(4), tech_stacks=(("glowglobes",), (), ()))
    assert ix_negotiators_returnable(cheap, 0, 1) == 2
    plain = replace(
        cheap,
        players=(
            replace(cheap.players[0], secret_project_tech_id=""),
            *cheap.players[1:],
        ),
    )
    assert ix_negotiators_returnable(plain, 0, 1) == 1


# --- A Tech Module tile acquired in the Reveal (OQ-150 (2)) --------------------


def _reveal_and_buy(
    config: RulesetConfig, tech_id: str, *, held: bool = False
) -> tuple[GameState, GameState]:
    """Seat 0's Reveal before and after an Acquire Tech of ``tech_id`` (the
    top of the first stack) opened in it -- or, with ``held``, the Reveal of
    a seat that held the tile from the start and buys nothing."""

    engine = UprisingRulesEngine()
    stacks: tuple[tuple[str, ...], ...] = ((tech_id,), (), ())
    state = _first_turn(config, resources=Resources(solari=0, spice=9))
    state = replace(state, tech_stacks=() if held else stacks)
    if held:
        owner = state.players[0]
        state = replace(
            state,
            players=(replace(owner, tech_ids=(tech_id,)), *state.players[1:]),
        )
    reveal = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "reveal_turn"
    )
    revealed = engine.apply(state, reveal).state
    if held:
        return revealed, revealed
    opened = push_tech_acquisition(
        revealed, 0, discount=0, source="test", printer=INTRIGUE_PRINTER
    ).state
    buy = next(
        action
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "choose_tech"
        and dict(action.arguments) == {"tech_id": tech_id}
    )
    return revealed, engine.apply(opened, buy).state


def test_self_destroying_messages_bought_in_the_reveal_pays_its_persuasion() -> None:
    # "Reveal 도중 Acquire Tech로 얻은 타일도 그 Reveal turn의 Reveal 능력이 모두
    # 듣는다" (OQ-150 (2), user ruling 2026-10-29 "(가) 모두 듣기") -- the Tech
    # Module's Self-Destroying Messages, "Reveal Turn: Persuasion 1"
    # (bloodlines.md 5), as Rise of Ix's Minimic Film (plan 17.10's P7 note).
    before, after = _reveal_and_buy(TECH_IX, "self_destroying_messages")
    persuasion = dict(before.decision_stack[-1].context)["persuasion"]
    assert isinstance(persuasion, int)
    assert after.players[0].tech_ids == ("self_destroying_messages",)
    assert dict(after.decision_stack[-1].context)["persuasion"] == persuasion + 1
    # Paid once: the next step pays nothing more.
    again = grant_late_reveal_effects(RuleResult(state=after)).state
    assert dict(again.decision_stack[-1].context)["persuasion"] == persuasion + 1


def test_self_destroying_messages_held_from_the_start_pays_once() -> None:
    start, _ = _reveal_and_buy(TECH, "self_destroying_messages", held=True)
    plain, _ = _reveal_and_buy(TECH, "glowglobes", held=True)
    persuasion = dict(start.decision_stack[-1].context)["persuasion"]
    without = dict(plain.decision_stack[-1].context)["persuasion"]
    assert isinstance(persuasion, int) and isinstance(without, int)
    assert persuasion == without + 1
    again = grant_late_reveal_effects(RuleResult(state=start)).state
    assert dict(again.decision_stack[-1].context)["persuasion"] == persuasion


@pytest.mark.parametrize("tech_id", ["forbidden_weapons", "panopticon"])
def test_a_reveal_tiles_pending_effect_opens_when_bought_in_the_reveal(
    tech_id: str,
) -> None:
    # The same ruling for the two Tech Module tiles whose Reveal Turn effect
    # waits on the Reveal frame (OQ-044): Forbidden Weapons' "반드시 선택"
    # and Panopticon's Spy and troop (bloodlines.md 5). The original game
    # leaves both out [Bloodlines p. 6]; the frame is built here for the
    # rule's sake, with the original game's config.
    _, after = _reveal_and_buy(TECH_IX, tech_id)
    context = dict(after.decision_stack[-1].context)
    assert tech_id in str(context[TECH_PENDING_KEY]).split(",")
    again = grant_late_reveal_effects(RuleResult(state=after)).state
    assert (
        str(dict(again.decision_stack[-1].context)[TECH_PENDING_KEY])
        .split(",")
        .count(tech_id)
        == 1
    )


# --- Navigation card 4 and Recruitment Mission (plan 16.10 item 7) -------------

NAVIGATION_FOUR = "intrigue:navigation_card_4:0"


def _navigation_four(*, recruitment_mission: bool) -> GameState:
    """Steersman Y'rkoon's seat 0 in its Reveal turn, its first Navigation
    play (card 4) owed, Recruitment Mission played this round or not."""

    engine = UprisingRulesEngine()
    state = _first_turn(BLOODLINES)
    reveal = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "reveal_turn"
    )
    state = engine.apply(state, reveal).state
    owner = replace(
        state.players[0],
        leader_id="steersman_y_rkoon",
        leader_face_id="steersman_y_rkoon",
        navigation_slots=(NAVIGATION_FOUR,),
        acquire_to_deck_top_round=recruitment_mission,
    )
    state = replace(
        state,
        players=(owner, *state.players[1:]),
        pending_navigation_plays=((0, "emperor", "test:navigation"),),
    )
    return begin_navigation_play(state).state


def test_navigation_card_four_offers_the_deck_top_under_recruitment_mission() -> None:
    # Navigation card 4's slot-1 option "pay 1 water: acquire The Spice Must
    # Flow" (bloodlines.md 6) gained the card with no step, so with
    # Recruitment Mission -- "You may put cards you acquire on top of your
    # deck", for each card acquired the owner chooses [FAQ p. 3]
    # (imperium-base.md 13.2) -- the owner could not choose (plan 16.10
    # item 7). Its row now has the deck-top twin, as an Intrigue card's
    # acquisition does.
    state = _navigation_four(recruitment_mission=True)
    plays = legal_navigation_play_actions(state, 0)
    twin = DomainAction("play_navigation", 0, (("option", 1), ("to_deck_top", True)))
    assert DomainAction("play_navigation", 0, (("option", 1),)) in plays
    assert twin in plays
    codec = ActionCodec(state.config)
    for action in UprisingRulesEngine().legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action
    owner = state.players[0]
    played = apply_navigation_play(state, twin).state
    seat = played.players[0]
    # The card names The Spice Must Flow; the original game's Reserve holds
    # its own printing (``reserve_printing``; as ``ReserveCostDiscount``
    # names both), so the option is playable there at all.
    assert seat.deck[0].startswith("reserve:imperium_the_spice_must_flow:")
    assert not any("the_spice_must_flow" in card for card in seat.discard_pile)
    # "Gain 1 VP when you acquire this card" [Main p. 20]; the water paid.
    assert seat.victory_points == owner.victory_points + 1
    assert seat.resources.water == owner.resources.water - 1
    plain = apply_navigation_play(
        state, DomainAction("play_navigation", 0, (("option", 1),))
    ).state.players[0]
    assert plain.discard_pile[-1].startswith("reserve:imperium_the_spice_must_flow:")
    assert plain.deck == owner.deck


def test_navigation_card_four_has_no_twin_without_a_deck_top_effect() -> None:
    state = _navigation_four(recruitment_mission=False)
    plays = legal_navigation_play_actions(state, 0)
    assert DomainAction("play_navigation", 0, (("option", 1),)) in plays
    assert not any(dict(play.arguments).get("to_deck_top") for play in plays)


# --- Commanders and dreadnoughts share the garrison two (plan 17.6 item 2) ------


def _combat_visit(*, dreadnoughts_garrison: int = 0) -> tuple[GameState, int]:
    """Seat 0 of an original + Bloodlines + Rise of Ix game at a Combat space,
    a Commander (the bank's) and troops in its garrison, a dreadnought in its
    supply; and the Conflict's strength before any deployment."""

    config = replace(BLOODLINES, rise_of_ix=True)
    state = _first_turn(
        config,
        commanders_garrison=1,
        dreadnoughts_supply=2 - dreadnoughts_garrison,
        dreadnoughts_garrison=dreadnoughts_garrison,
    )
    state = replace(state, sardaukar_commanders_bank=0)
    space_id = next(
        str(dict(action.arguments)["space_id"])
        for action in legal_agent_actions(state, 0)
        if BOARD_SPACES_BY_ID[str(dict(action.arguments)["space_id"])].combat
    )
    placed = _placed(state, space_id)
    return placed, placed.players[0].combat_strength


def _deploy_counts(state: GameState) -> dict[str, list[int]]:
    counts: dict[str, list[int]] = {}
    for action in (
        *legal_combat_deployments(state, 0),
        *legal_commander_deployments(state, 0),
        *legal_dreadnought_deployments(state, 0),
    ):
        count = dict(action.arguments)["count"]
        assert isinstance(count, int)
        counts.setdefault(action.action_id, []).append(count)
    return counts


def _deploy(state: GameState, action_id: str, count: int) -> GameState:
    action = DomainAction(action_id, 0, (("count", count),))
    if action_id == "deploy_dreadnoughts":
        return apply_dreadnought_deployment(state, action).state
    if action_id == "deploy_commanders":
        return apply_commander_deployment(state, action).state
    return apply_combat_deployment(state, action).state


def test_a_commissioned_dreadnought_deploys_beside_a_commander_and_a_troop() -> None:
    # "You may deploy any or all units recruited during your current turn ...,
    # plus up to two more units from your garrison" and "If you commissioned
    # the dreadnought while sending an Agent to a Combat space, you may deploy
    # it to the Conflict" [Rise of Ix p. 6]; a Commander is a "troop"
    # [Bloodlines p. 4], a dreadnought is not (rise-of-ix.md 6). So the
    # garrison two are shared by troops, Commanders and dreadnoughts, and the
    # dreadnought commissioned this turn deploys outside them (plan 17.6
    # item 2, OQ-070's share widened to the third kind).
    state, _ = _combat_visit()
    state = commission_dreadnought(state, 0, source="test").state
    assert _deploy_counts(state) == {
        "deploy_troops": [1, 2],
        "deploy_commanders": [1],
        "deploy_dreadnoughts": [1],
    }
    state = _deploy(state, "deploy_dreadnoughts", 1)
    # Its own slot: the garrison two are untouched.
    assert _deploy_counts(state) == {"deploy_troops": [1, 2], "deploy_commanders": [1]}
    state = _deploy(state, "deploy_commanders", 1)
    assert _deploy_counts(state) == {"deploy_troops": [1]}
    state = _deploy(state, "deploy_troops", 1)
    assert _deploy_counts(state) == {}
    owner = state.players[0]
    assert (owner.dreadnoughts_conflict, owner.commanders_conflict) == (1, 1)
    assert owner.troops_conflict == 1


def test_a_garrison_dreadnought_and_a_commander_fill_the_garrison_two() -> None:
    # Without a commission this turn the dreadnought comes from the garrison
    # share like the others [Rise of Ix p. 6].
    state, _ = _combat_visit(dreadnoughts_garrison=1)
    assert _deploy_counts(state) == {
        "deploy_troops": [1, 2],
        "deploy_commanders": [1],
        "deploy_dreadnoughts": [1],
    }
    state = _deploy(state, "deploy_dreadnoughts", 1)
    assert _deploy_counts(state) == {"deploy_troops": [1], "deploy_commanders": [1]}
    state = _deploy(state, "deploy_commanders", 1)
    assert _deploy_counts(state) == {}
