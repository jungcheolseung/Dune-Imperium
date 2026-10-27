"""The original Dune: Imperium's board and flow (stage P2a).

docs/base-game-and-ix-plan.md 15 and docs/rules/imperium-base.md: the
original board's spaces [DI pp. 17-18], the Mentat [DI pp. 6, 13, 16, 18],
its Reserve [DI pp. 3, 11], its Influence 4 bonuses (the Steam app's,
plan 15.3), its setup [DI pp. 4-5] and its Conflict rewards [DI pp. 8, 12].
"""

from dataclasses import replace

from tests.support.pauses import pause_outcome

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquisition import (
    AcquireBlock,
    legal_reserve_acquisitions,
    reserve_acquisition_block,
)
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.board_effects import legal_maker_space_actions
from dune_imperium.rules.combat import (
    apply_combat_reward_icon,
    apply_combat_reward_influence,
    legal_combat_reward_icon_actions,
    legal_combat_reward_influence_actions,
    offer_conflict_end_triggers,
    resolve_combat_rewards,
)
from dune_imperium.rules.frames import FrameKind, top_frame
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.phases import begin_round, resolve_recall_or_endgame
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
# Seated as named: no Leader at seat 0 changes a space's cost.
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)


def _start(seed: int = 3) -> GameState:
    """Round 1, seat 0's first turn (the hands drawn)."""

    state = ENGINE.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _place(
    state: GameState, space_id: str, cost_option: int | None = None
) -> GameState:
    """Seat 0 sends an Agent to ``space_id`` with any card that can. If the
    hand the setup dealt has none (the deal moves as stage P3 fills the
    original decks), the starting card that can is taken from the deck."""

    def placements(state: GameState) -> list[DomainAction]:
        return [
            placement
            for placement in executable_placements(state, 0)
            if dict(placement.arguments)["space_id"] == space_id
            and dict(placement.arguments).get("cost_option") == cost_option
        ]

    found = placements(state)
    owner = state.players[0]
    for card in (c for c in owner.deck if ":starter:" in c):
        if found:
            break
        tried = _seat(
            state,
            hand=(*owner.hand, card),
            deck=tuple(c for c in owner.deck if c != card),
        )
        if placements(tried):
            state, found = tried, placements(tried)
    return apply_placement(ENGINE, state, found[0]).state


def _with_card(state: GameState, card_id: str) -> GameState:
    """Seat 0 with its starting ``card_id`` in hand (from its deck if the
    setup did not deal it; the deal moves as stage P3 fills the decks)."""

    owner = state.players[0]
    if any(f":{card_id}:" in card for card in owner.hand):
        return state
    instance = next(card for card in owner.deck if f":{card_id}:" in card)
    return _seat(
        state,
        hand=(*owner.hand, instance),
        deck=tuple(card for card in owner.deck if card != instance),
    )


def _wholes(state: GameState, player: int = 0) -> tuple[DomainAction, ...]:
    return ENGINE.whole_actions(state, player)


def _do(
    state: GameState, action_id: str, player: int = 0, **arguments: object
) -> GameState:
    """Apply ``player``'s whole action ``action_id`` with ``arguments``."""

    action = next(
        action
        for action in _wholes(state, player)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return apply_whole(ENGINE, state, action).state


def _effects(state: GameState) -> set[object]:
    return {
        dict(action.arguments).get("effect")
        for action in _wholes(state)
        if action.action_id == "resolve_board_effect"
    }


# --- Setup [DI pp. 4-5] ------------------------------------------------------


def test_the_first_player_is_random_and_no_shield_wall_is_printed() -> None:
    # "Determine a first player randomly" [DI p. 5] (imperium-base.md 4 H);
    # the original board prints no Shield Wall (imperium-base.md 2).
    config = RulesetConfig(base_game=BaseGame.IMPERIUM)
    seats = set()
    for seed in range(12):
        setup = create_initial_state(config, seed, LEADERS)
        (outcome,) = (
            outcome
            for outcome in setup.chance_outcomes
            if outcome.decision_id == "setup:first_player"
        )
        assert setup.state.first_player == int(outcome.values[0])
        assert setup.state.shield_wall_present is False
        seats.add(setup.state.first_player)
    assert len(seats) > 1
    # ``first_player_seat_zero`` seats seat 0 first without a draw (OQ-132).
    pinned = create_initial_state(CONFIG, 0, LEADERS)
    assert pinned.state.first_player == 0
    assert all(
        outcome.decision_id != "setup:first_player"
        for outcome in pinned.chance_outcomes
    )


def test_rabban_starts_with_one_spice_and_one_solari_more() -> None:
    # Arrakis Fiefdom [Rabban card] (imperium-base.md 4, 12).
    state = create_initial_state(CONFIG, 0, LEADERS).state
    assert state.players[0].resources == Resources(solari=1, spice=1, water=1)
    assert all(seat.resources == Resources(water=1) for seat in state.players[1:])


def test_the_original_game_deals_its_own_reserve_and_no_objective() -> None:
    state = _start()
    # Arrakis Liaison 8, The Spice Must Flow 10, Foldspace 6 [DI p. 3].
    assert dict(state.reserve_stacks) == {
        "arrakis_liaison": 8,
        "imperium_the_spice_must_flow": 10,
        "foldspace_card": 6,
    }
    assert all(seat.objective_ids == () for seat in state.players)
    assert state.current_conflict_ids[0] in {
        "skirmish_a",
        "skirmish_b",
        "skirmish_c",
        "skirmish_d",
    }


# --- Influence [DI p. 7] ------------------------------------------------------


def test_the_emperor_track_s_fourth_space_recruits_two_troops() -> None:
    # The original board's Emperor bonus (the Steam app's
    # ``FactionTrackBonusAction``; plan 15.3): two troops, no Spy.
    state = _seat(_start(), influence=Influence(emperor=3))
    owner = state.players[0]
    gained = gain_faction_influence(
        state, 0, Faction.EMPEROR, 1, event_prefix="test"
    ).state.players[0]
    assert gained.influence.emperor == 4
    assert gained.troops_garrison == owner.troops_garrison + 2
    assert gained.troops_supply == owner.troops_supply - 2
    assert gained.spies_supply == owner.spies_supply


def test_the_spacing_guild_and_fremen_fourth_spaces() -> None:
    state = _seat(_start(), influence=Influence(spacing_guild=3, fremen=3))
    owner = state.players[0]
    state = gain_faction_influence(
        state, 0, Faction.SPACING_GUILD, 1, event_prefix="guild"
    ).state
    state = gain_faction_influence(
        state, 0, Faction.FREMEN, 1, event_prefix="fremen"
    ).state
    assert state.players[0].resources == replace(
        owner.resources,
        solari=owner.resources.solari + 3,
        water=owner.resources.water + 1,
    )


# --- The Mentat [DI pp. 6, 13, 16, 18] ----------------------------------------


def test_the_mentat_space_draws_and_takes_the_resting_mentat() -> None:
    # "Draw a card. If the Mentat is here, take it" [DI p. 18]; "this round,
    # you may use it as one of your Agents".
    # A Dagger (Landsraad) in hand: the setup deal moves as the decks fill.
    state = _seat(_with_card(_start(), "dagger"), resources=Resources(solari=2))
    placed = _place(state, "mentat")
    assert placed.players[0].resources.solari == 0
    assert _effects(placed) == {"cards", "mentat"}
    taken = _do(placed, "resolve_board_effect", effect="mentat")
    owner = taken.players[0]
    assert owner.mentat is True
    # One Agent on the Mentat space, one on the Leader and the Mentat.
    assert owner.agents_available == 2
    drawn = _do(taken, "resolve_board_effect", effect="cards")
    assert len(drawn.players[0].hand) == len(taken.players[0].hand) + 1


def test_a_taken_mentat_leaves_only_the_draw_on_its_space() -> None:
    # The Mentat is taken only from its space (imperium-base.md 9); a seat
    # sending an Agent there while another holds it only draws (OQ-124).
    state = _seat(_with_card(_start(), "dagger"), resources=Resources(solari=2))
    state = _seat(state, 2, mentat=True, agents_available=3)
    placed = _place(state, "mentat")
    assert _effects(placed) == {"cards"}


def test_recall_returns_the_mentat_to_its_space() -> None:
    # "Return the Mentat to its designated space in the Landsraad (if it's
    # not already there)", then recall the Agents [DI p. 13].
    state = _seat(
        _start(),
        mentat=True,
        agents_available=0,
        agent_locations=("mentat", "wealth", "secure_contract"),
    )
    state = replace(state, phase=GamePhase.RECALL_OR_ENDGAME, decision_stack=())
    recalled = resolve_recall_or_endgame(state).state
    owner = recalled.players[0]
    assert owner.mentat is False
    assert owner.agents_available == 2
    assert owner.agent_locations == ()


# --- Board spaces [DI pp. 17-18] ----------------------------------------------


def test_selective_breeding_draws_its_two_cards_only_after_the_trash() -> None:
    # "Trash one card to draw two cards" [DI p. 18]: the trash is the arrow's
    # cost, never forced [DI p. 9]; the public trash and the hidden draw are
    # separate steps (OQ-106).
    state = _seat(_start(), resources=Resources(spice=2))
    placed = _place(state, "selective_breeding")
    assert _effects(placed) == set()
    trashes = [
        action
        for action in _wholes(placed)
        if action.action_id == "trash_card_for_desert_tactics"
    ]
    assert trashes
    hand = placed.players[0].hand
    trashed = apply_whole(ENGINE, placed, trashes[0]).state
    assert _effects(trashed) == {"cards"}
    assert len(trashed.players[0].hand) == len(hand) - (
        dict(trashes[0].arguments)["card_id"] in hand
    )
    drawn = _do(trashed, "resolve_board_effect", effect="cards")
    assert len(drawn.players[0].hand) == len(trashed.players[0].hand) + 2


def test_the_foldspace_space_acquires_a_foldspace_card() -> None:
    # "Acquire a Foldspace card from the Reserve" [DI p. 17], to the discard
    # pile; with the stack empty there is nothing to take.
    state = _start()
    placed = _place(state, "foldspace")
    assert "foldspace" in _effects(placed)
    acquired = _do(placed, "resolve_board_effect", effect="foldspace")
    assert dict(acquired.reserve_stacks)["foldspace_card"] == 5
    assert any(":foldspace_card:" in card for card in acquired.players[0].discard_pile)

    empty = replace(
        state,
        reserve_stacks=tuple(
            (card_id, 0 if card_id == "foldspace_card" else count)
            for card_id, count in state.reserve_stacks
        ),
    )
    placed = _place(empty, "foldspace")
    unchanged = _do(placed, "resolve_board_effect", effect="foldspace")
    assert unchanged.players[0].discard_pile == placed.players[0].discard_pile


def test_foldspace_is_never_bought_in_the_reveal_shop() -> None:
    # "(Foldspace is acquired at the board space of the same name ...)"
    # [DI p. 11]; only through its icon [FAQ p. 2] (OQ-125).
    state = _start()
    revealed = _do(state, "reveal_turn")
    offered = {
        dict(action.arguments)["card_id"]
        for action in legal_reserve_acquisitions(revealed, 0)
    }
    assert "foldspace_card" not in offered
    assert (
        reserve_acquisition_block(revealed, "foldspace_card", 6, 10)
        is AcquireBlock.NO_COST
    )


def test_the_original_high_council_and_swordmaster_are_once_per_game() -> None:
    # "only once per game" [DI pp. 17-18].
    state = _seat(_with_card(_start(), "dagger"), resources=Resources(solari=20))
    spaces = {
        dict(placement.arguments)["space_id"]
        for placement in executable_placements(state, 0)
    }
    assert {"imperium_high_council", "imperium_swordmaster"} <= spaces
    state = _seat(
        state, high_council=True, swordmaster_acquired=True, agents_available=3
    )
    spaces = {
        dict(placement.arguments)["space_id"]
        for placement in executable_placements(state, 0)
    }
    assert not spaces & {"imperium_high_council", "imperium_swordmaster"}


def test_sell_melange_pays_by_the_spice_sold() -> None:
    # "Pay 2 to 5 spice" [DI p. 18]; 6, 8, 10 or 12 Solari (the app's
    # ``SellMelangeSpaceAbility``, plan 15.3).
    for option, (spice, solari) in enumerate(((2, 6), (3, 8), (4, 10), (5, 12))):
        state = _seat(_start(), resources=Resources(spice=5))
        placed = _place(state, "sell_melange", option)
        paid = _do(placed, "resolve_board_effect", effect="resources")
        assert paid.players[0].resources == Resources(spice=5 - spice, solari=solari)


def test_the_original_maker_spaces_harvest_without_a_sandworm() -> None:
    # Hagga Basin 2 and The Great Flat 3 spice plus the bonus [DI p. 17]
    # [FAQ p. 1]; the original board prints no sandworm (imperium-base.md 2).
    for space_id, base, water in (
        ("imperium_hagga_basin", 2, 1),
        ("the_great_flat", 3, 2),
    ):
        state = _seat(_start(), resources=Resources(water=water))
        state = replace(
            state,
            maker_bonus_spice=tuple(
                (maker, 2 if maker == space_id else bonus)
                for maker, bonus in state.maker_bonus_spice
            ),
        )
        placed = _place(state, space_id)
        (harvest,) = legal_maker_space_actions(placed, 0)
        assert harvest.action_id == "harvest_maker_spice"
        harvested = apply_whole(ENGINE, placed, harvest).state
        assert harvested.players[0].resources.spice == base + 2
        assert dict(harvested.maker_bonus_spice)[space_id] == 0


def test_carthag_pays_its_controller_a_solari() -> None:
    # "Arrakeen and Carthag 1 Solari" to the controller [DI p. 10].
    state = _seat(
        _with_card(_start(), "reconnaissance"), 1, control_space_ids=("carthag",)
    )
    solari = state.players[1].resources.solari
    placed = _place(state, "carthag")
    assert placed.players[1].resources.solari == solari + 1


# --- Conflict rewards [DI pp. 8, 12] ------------------------------------------


def _reward_state(conflict_id: str) -> GameState:
    config = RulesetConfig(base_game=BaseGame.IMPERIUM)
    return GameState(
        config=config,
        seed=1,
        maker_bonus_spice=content_for(config).maker_bonus_spice_for(LEADERS),
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=tuple(
            PlayerState(player_id=seat, combat_strength=strength)
            for seat, strength in enumerate((8, 6, 4, 0))
        ),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1", "intrigue:2", "intrigue:3"),
    )


def _icon(state: GameState, player: int, kind: str) -> GameState:
    return apply_combat_reward_icon(
        state,
        DomainAction("resolve_combat_reward_icon", player, (("effect", kind),)),
    ).state


def _offered(state: GameState, player: int) -> set[object]:
    return {
        dict(action.arguments)["effect"]
        for action in legal_combat_reward_icon_actions(state, player)
    }


def _window_of(state: GameState, player: int) -> GameState:
    """Pay the places before ``player``'s through the engine (their first
    offered answers, the pauses between recipients answered) and open
    ``player``'s reward window."""

    state = resolve_combat_rewards(state).state
    for _ in range(64):
        frame = top_frame(state)
        assert frame is not None
        if frame.kind == FrameKind.PAUSE:
            state = ENGINE.apply(state, pause_outcome(state)).state
            continue
        assert isinstance(frame.decision, PlayerDecision)
        owner = frame.decision.owner
        if frame.kind == FrameKind.COMBAT_REWARD_ICONS and owner == player:
            return state
        state = apply_whole(ENGINE, state, _wholes(state, owner)[0]).state
    raise AssertionError("the reward window did not open")


def test_an_or_reward_takes_one_of_its_lines() -> None:
    # Cloak and Dagger's third place prints "Intrigue -OR- 1 spice" (P0
    # sweep; a ONE_OF row).
    state = _window_of(_reward_state("cloak_and_dagger"), 2)
    assert _offered(state, 2) == {"line_0", "line_1"}
    chosen = _icon(state, 2, "line_1")
    assert _offered(chosen, 2) == {"resources"}
    paid = _icon(chosen, 2, "resources")
    assert paid.players[2].resources.spice == 1
    assert paid.players[2].intrigue_cards == ()


def test_choose_two_names_both_lines_before_either_is_paid() -> None:
    # Battle for Arrakeen's second place: "Choose two:" Intrigue, 2 spice,
    # 3 Solari -- two different ones, named before either is paid (OQ-114,
    # OQ-057 (4)).
    state = _window_of(_reward_state("imperium_battle_for_arrakeen"), 1)
    assert _offered(state, 1) == {"line_0", "line_1", "line_2"}
    first = _icon(state, 1, "line_2")
    assert first.players[1] == state.players[1]
    assert _offered(first, 1) == {"line_0", "line_1"}
    second = _icon(first, 1, "line_0")
    assert _offered(second, 1) == {"resources", "intrigue"}
    paid = _icon(_icon(second, 1, "resources"), 1, "intrigue")
    assert paid.players[1].resources == Resources(solari=3)
    assert len(paid.players[1].intrigue_cards) == 1


def test_grand_vision_gives_two_influence_with_one_faction() -> None:
    # The two-chevron Influence icon is one Faction twice [DI p. 16].
    state = resolve_combat_rewards(_reward_state("grand_vision")).state
    assert "one_faction_influence" in _offered(state, 0)
    state = _icon(state, 0, "one_faction_influence")
    (fremen,) = (
        action
        for action in legal_combat_reward_influence_actions(state, 0)
        if dict(action.arguments)["faction"] == "fremen"
    )
    gained = apply_combat_reward_influence(state, fremen).state
    assert gained.players[0].influence.fremen == 2
    assert gained.players[0].influence.emperor == 0


def test_sort_through_the_chaos_gives_the_mentat_at_the_next_round_start() -> None:
    # "you take the Mentat at the start of the next round" [FAQ p. 4] and
    # "keep it as an Agent for next round" [DI p. 16].
    state = resolve_combat_rewards(_reward_state("sort_through_the_chaos")).state
    assert "mentat" in _offered(state, 0)
    won = _icon(state, 0, "mentat")
    assert won.mentat_owed_to == 0
    assert won.players[0].mentat is False

    upcoming = replace(
        won,
        phase=GamePhase.ROUND_START,
        decision_stack=(),
        conflict_deck=("guild_bank_raid",),
        players=tuple(
            replace(seat, agents_available=2, combat_strength=0) for seat in won.players
        ),
    )
    started = begin_round(upcoming).state
    assert started.mentat_owed_to is None
    assert started.players[0].mentat is True
    assert started.players[0].agents_available == 3


def test_the_conflict_card_stays_on_the_board() -> None:
    # "on top of any Conflict cards from previous rounds" [DI p. 8]: no
    # winner takes the card (imperium-base.md 2, 10).
    state = replace(
        _reward_state("guild_bank_raid"),
        combat_rewards_resolved=True,
    )
    offered = offer_conflict_end_triggers(state)
    assert all(seat.won_conflict_ids == () for seat in offered.state.players)
    assert offered.state.current_conflict_ids == ("guild_bank_raid",)
    assert [event.kind for event in offered.events].count("conflict_won") == 1


def test_the_original_game_drafts_six_of_its_eight_leaders() -> None:
    # The Leader draft (OQ-007) deals six of the original game's eight once
    # stage P2b has them all (plan 15.4).
    config = RulesetConfig(base_game=BaseGame.IMPERIUM, leader_draft=True)
    state = create_draft_initial_state(config, 5).state
    assert state.phase is GamePhase.SETUP
    pool = set(state.leader_draft_pool)
    assert len(pool) == 6
    assert pool <= {leader.leader_id for leader in content_for(config).leaders}
    assert dict(state.maker_bonus_spice) == {
        "the_great_flat": 0,
        "imperium_hagga_basin": 0,
        "imperial_basin": 0,
    }
