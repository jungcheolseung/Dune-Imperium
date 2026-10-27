"""The original Dune: Imperium's Leaders (stages P2a and P2b).

docs/rules/imperium-base.md 12 (and its 13.2 FAQ rows) and
docs/base-game-and-ix-plan.md 15.1: Glossu Rabban, Count Ilban Richese, Earl
Memnon Thorvald and Countess Ariana Thorvald (P2a), then Duke Leto Atreides,
Helena Richese and Paul Atreides (P2b). Each is seated at seat 0.
"""

from dataclasses import replace
from typing import Any

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.board_effects import legal_maker_space_actions
from dune_imperium.rules.combat_deployment import legal_agent_turn_finish_actions

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)


def _start(leader: str, seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 with ``leader`` at seat 0, at its first turn."""

    seats = (leader, *(other for other in LEADERS if other != leader))[:4]
    engine = UprisingRulesEngine(leader_ids=seats)
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.players[0].leader_id == leader
    return engine, state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _with_card(state: GameState, card_id: str) -> GameState:
    """Seat 0 with its starting ``card_id`` in hand (from its deck)."""

    owner = state.players[0]
    if any(f":{card_id}:" in card for card in owner.hand):
        return state
    instance = next(card for card in owner.deck if f":{card_id}:" in card)
    return _seat(
        state,
        hand=(*owner.hand, instance),
        deck=tuple(card for card in owner.deck if card != instance),
    )


def _place(
    engine: UprisingRulesEngine,
    state: GameState,
    space_id: str,
    card_id: str | None = None,
) -> GameState:
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and (
            card_id is None
            or f":{card_id}:" in str(dict(placement.arguments)["card_id"])
        )
    )
    return apply_placement(engine, state, placement).state


def _wholes(engine: UprisingRulesEngine, state: GameState) -> tuple[DomainAction, ...]:
    return engine.whole_actions(state, 0)


def _ids(engine: UprisingRulesEngine, state: GameState) -> set[str]:
    return {action.action_id for action in _wholes(engine, state)}


def _do(
    engine: UprisingRulesEngine, state: GameState, action_id: str, **arguments: object
) -> GameState:
    action = next(
        action
        for action in _wholes(engine, state)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return apply_whole(engine, state, action).state


def _signet(leader: str, **changes: Any) -> GameState:
    """Seat 0 (``leader``) plays its Signet Ring to Secure Contract and
    resolves the box."""

    engine, state = _start(leader)
    state = _seat(_with_card(state, "signet_ring"), **changes)
    placed = _place(engine, state, "secure_contract", "signet_ring")
    return _do(engine, placed, "resolve_agent_card_effect")


# --- Glossu "The Beast" Rabban ----------------------------------------------


def test_brutality_recruits_one_troop_or_two_with_an_alliance() -> None:
    # Brutality: one troop, two with any Faction Alliance (imperium-base.md
    # 12); its "-OR-" is no choice (P0 sweep L7), judged as it resolves.
    alone = _signet("glossu_rabban")
    assert alone.players[0].troops_garrison == 3 + 1
    allied = _signet(
        "glossu_rabban",
        influence=Influence(fremen=4),
        alliance_faction_ids=("fremen",),
    )
    assert allied.players[0].troops_garrison == 3 + 2


# --- Count Ilban Richese -----------------------------------------------------


def test_manufacturing_gains_a_solari() -> None:
    engine, state = _start("count_ilban_richese")
    solari = state.players[0].resources.solari
    resolved = _signet("count_ilban_richese")
    # Secure Contract's own 3 Solari wait as the space's icon.
    assert resolved.players[0].resources.solari == solari + 1


def test_ruthless_negotiator_draws_when_solari_pay_a_space_s_cost() -> None:
    # "보드 칸의 비용으로 Solari를 낼 때마다 카드 1장", printed cost only
    # [FAQ p. 2]; the card is its own step after the placement (OQ-106).
    engine, state = _start("count_ilban_richese")
    state = _seat(_with_card(state, "dagger"), resources=Resources(solari=2))
    placed = _place(engine, state, "mentat")
    assert placed.players[0].owed_draws
    assert "draw_owed_card" in _ids(engine, placed)
    hand = len(placed.players[0].hand)
    drawn = _do(engine, placed, "draw_owed_card")
    assert len(drawn.players[0].hand) == hand + 1
    assert drawn.players[0].owed_draws == ()


def test_ruthless_negotiator_ignores_a_cost_paid_in_spice_or_water() -> None:
    engine, state = _start("count_ilban_richese")
    state = _seat(state, resources=Resources(spice=4))
    placed = _place(engine, state, "conspire")
    assert placed.players[0].owed_draws == ()


# --- Earl Memnon Thorvald ----------------------------------------------------


def test_spice_hoard_gains_a_spice() -> None:
    engine, state = _start("earl_memnon_thorvald")
    spice = state.players[0].resources.spice
    assert _signet("earl_memnon_thorvald").players[0].resources.spice == spice + 1


def test_connections_gives_a_chosen_influence_with_the_high_council_seat() -> None:
    # Connections: on taking a High Council seat, Influence with a Faction
    # of the owner's choice (imperium-base.md 12).
    engine, state = _start("earl_memnon_thorvald")
    state = _seat(_with_card(state, "dagger"), resources=Resources(solari=5))
    placed = _place(engine, state, "imperium_high_council")
    seated = _do(engine, placed, "resolve_board_effect", effect="high_council")
    assert seated.players[0].high_council is True
    factions = {
        dict(action.arguments)["faction"]
        for action in _wholes(engine, seated)
        if action.action_id == "choose_connections_influence"
    }
    assert factions == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    # It holds the turn's end until it is taken.
    assert not legal_agent_turn_finish_actions(seated, 0)
    gained = _do(engine, seated, "choose_connections_influence", faction="fremen")
    assert gained.players[0].influence.fremen == 1
    assert legal_agent_turn_finish_actions(gained, 0)


def test_connections_with_every_faction_at_the_top_lapses() -> None:
    # A Faction at 6 gains nothing and is never offered (OQ-060); with every
    # cube there the icon waits and lapses at the turn's end.
    engine, state = _start("earl_memnon_thorvald")
    state = _seat(
        _with_card(state, "dagger"),
        resources=Resources(solari=5),
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
    )
    placed = _place(engine, state, "imperium_high_council")
    seated = _do(engine, placed, "resolve_board_effect", effect="high_council")
    assert "choose_connections_influence" not in _ids(engine, seated)
    assert legal_agent_turn_finish_actions(seated, 0)


def test_other_leaders_take_the_seat_without_connections() -> None:
    engine, state = _start("glossu_rabban")
    state = _seat(_with_card(state, "dagger"), resources=Resources(solari=5))
    placed = _place(engine, state, "imperium_high_council")
    seated = _do(engine, placed, "resolve_board_effect", effect="high_council")
    assert "choose_connections_influence" not in _ids(engine, seated)


# --- Countess Ariana Thorvald ------------------------------------------------


def test_hidden_reservoir_gains_a_water() -> None:
    engine, state = _start("countess_ariana_thorvald")
    water = state.players[0].resources.water
    resolved = _signet("countess_ariana_thorvald")
    assert resolved.players[0].resources.water == water + 1


def test_spice_addict_harvests_one_less_and_draws() -> None:
    # Spice Addict: mandatory, a Maker space's harvest only [FAQ p. 2]; Hagga
    # Basin's 2 spice plus 1 bonus, less 1; the card is its own step.
    engine, state = _start("countess_ariana_thorvald")
    state = _seat(
        _with_card(state, "dune_the_desert_planet"), resources=Resources(water=1)
    )
    state = replace(
        state,
        maker_bonus_spice=tuple(
            (space, 1 if space == "imperium_hagga_basin" else bonus)
            for space, bonus in state.maker_bonus_spice
        ),
    )
    placed = _place(engine, state, "imperium_hagga_basin")
    (harvest,) = legal_maker_space_actions(placed, 0)
    harvested = apply_whole(engine, placed, harvest).state
    assert harvested.players[0].resources.spice == 2 + 1 - 1
    assert harvested.players[0].owed_draws
    hand = len(harvested.players[0].hand)
    drawn = _do(engine, harvested, "draw_owed_card")
    assert len(drawn.players[0].hand) == hand + 1


def test_spice_addict_leaves_the_control_bonus_whole() -> None:
    # "Control spice is not a harvest" (P0 sweep L4, [FAQ p. 2]): Ariana
    # controlling Imperial Basin gains its 1 spice whole when another seat
    # visits.
    engine, state = _start("glossu_rabban")
    ariana = next(
        seat.player_id
        for seat in state.players
        if seat.leader_id == "countess_ariana_thorvald"
    )
    state = _seat(
        _with_card(state, "dune_the_desert_planet"),
        ariana,
        control_space_ids=("imperial_basin",),
    )
    spice = state.players[ariana].resources.spice
    placed = _place(engine, state, "imperial_basin")
    assert placed.players[ariana].resources.spice == spice + 1
    assert placed.players[ariana].owed_draws == ()


# --- Duke Leto Atreides (P2b) -------------------------------------------------


def test_landsraad_popularity_takes_a_solari_off_landsraad_spaces() -> None:
    # "Landsraad 칸에 보내는 비용 1 Solari 적게" (imperium-base.md 12), never
    # optional (P0 sweep L5): the Mentat space for 1, Rally Troops for 3; a
    # space with no Solari cost (Hall of Oratory) or another icon is unchanged.
    engine, state = _start("duke_leto_atreides")
    state = _seat(_with_card(state, "dagger"), resources=Resources(solari=1))
    spaces = {
        dict(placement.arguments)["space_id"]
        for placement in executable_placements(state, 0)
    }
    assert {"mentat", "hall_of_oratory"} <= spaces
    assert "rally_troops" not in spaces
    placed = _place(engine, state, "mentat")
    assert placed.players[0].resources.solari == 0


def test_prudent_diplomacy_buys_influence_where_an_opponent_leads() -> None:
    # "spice 1 → 상대가 나보다 Influence가 많은 진영에 Influence 1": an arrow,
    # declined freely, judged as it resolves (OQ-028); never a Faction at the
    # top (OQ-060, P0 sweep L5).
    engine, state = _start("duke_leto_atreides")
    state = _seat(
        _with_card(state, "signet_ring"),
        resources=Resources(spice=1),
        influence=Influence(fremen=6),
    )
    state = _seat(state, 1, influence=Influence(emperor=2, fremen=6))
    state = _seat(state, 2, influence=Influence(spacing_guild=1))
    placed = _place(engine, state, "secure_contract", "signet_ring")
    offered = {
        dict(action.arguments)["faction"]
        for action in _wholes(engine, placed)
        if action.action_id == "choose_leader_signet_influence"
    }
    assert offered == {"emperor", "spacing_guild"}
    gained = _do(engine, placed, "choose_leader_signet_influence", faction="emperor")
    owner = gained.players[0]
    assert owner.influence.emperor == 1
    assert owner.resources.spice == 0


def test_prudent_diplomacy_without_spice_offers_nothing_and_lapses() -> None:
    # An unused optional effect offers no refusal in an Agent turn and lapses
    # when the turn ends (OQ-095 (2)).
    engine, state = _start("duke_leto_atreides")
    state = _seat(_with_card(state, "signet_ring"), resources=Resources())
    state = _seat(state, 1, influence=Influence(emperor=2))
    placed = _place(engine, state, "secure_contract", "signet_ring")
    placed = _do(engine, placed, "resolve_board_effect", effect="resources")
    assert "choose_leader_signet_influence" not in _ids(engine, placed)
    assert legal_agent_turn_finish_actions(placed, 0)


# --- Helena Richese (P2b) -----------------------------------------------------


def test_eyes_everywhere_ignores_opponents_on_landsraad_and_city_spaces() -> None:
    # "상대 Agent가 Landsraad·City 칸에서 내 Agent를 막지 않는다"
    # (imperium-base.md 12); her own Agent and other icons still block (P0
    # sweep L8).
    engine, state = _start("helena_richese")
    for card_id in ("reconnaissance", "dagger", "diplomacy"):
        state = _with_card(state, card_id)
    state = _seat(state, resources=Resources(solari=4))
    state = _seat(
        state, 1, agent_locations=("carthag", "rally_troops"), agents_available=0
    )
    state = _seat(state, 2, agent_locations=("stillsuits",), agents_available=1)
    spaces = {
        dict(placement.arguments)["space_id"]
        for placement in executable_placements(state, 0)
    }
    assert {"carthag", "rally_troops"} <= spaces
    assert "stillsuits" not in spaces
    own = _seat(state, agent_locations=("carthag",), agents_available=1)
    assert "carthag" not in {
        dict(placement.arguments)["space_id"]
        for placement in executable_placements(own, 0)
    }


def test_manipulate_with_an_empty_row_is_confirmed() -> None:
    # The original game's Row is empty until stage P3: the set-aside fizzles
    # and is confirmed, as the Intrigue card's (OQ-113 (C), [FAQ p. 3]).
    engine, state = _start("helena_richese")
    state = _with_card(state, "signet_ring")
    placed = _place(engine, state, "secure_contract", "signet_ring")
    assert "set_aside_leader_imperium" not in _ids(engine, placed)
    confirmed = _do(engine, placed, "resolve_leader_signet_without_option")
    assert confirmed.players[0].imperium_set_aside == ()


def test_manipulate_sets_a_row_card_aside_and_refills_the_row() -> None:
    # "Imperium Row 카드 하나를 치우고 채움" (imperium-base.md 12); the card
    # waits for her Reveal turn at 1 Persuasion less, as the Uprising
    # Intrigue card's [FAQ p. 3]. A test Row (Uprising cards) stands in for
    # the original deck of stage P3.
    engine, state = _start("helena_richese")
    cards = imperium_deck_instance_ids(False)[:6]
    state = replace(
        _with_card(state, "signet_ring"),
        imperium_row=cards[:5],
        imperium_deck=cards[5:],
    )
    placed = _place(engine, state, "secure_contract", "signet_ring")
    offered = {
        dict(action.arguments)["instance_id"]
        for action in _wholes(engine, placed)
        if action.action_id == "set_aside_leader_imperium"
    }
    assert offered == set(cards[:5])
    taken = _do(engine, placed, "set_aside_leader_imperium", instance_id=cards[2])
    assert taken.players[0].imperium_set_aside == (cards[2],)
    assert taken.imperium_row == (*cards[:2], cards[5], *cards[3:5])
    assert taken.imperium_deck == ()


# --- Paul Atreides (P2b) ------------------------------------------------------


def test_prescience_shows_paul_his_deck_s_top_card() -> None:
    # "자기 덱 맨 위 카드를 언제든 볼 수 있다"; "덱이 비면 볼 수 없다
    # (discard를 섞지 않는다) [DI p. 13]" (imperium-base.md 12).
    engine, state = _start("paul_atreides")
    top = state.players[0].deck[0]
    private = engine.observe(state, 0).private
    assert private is not None and private.peeked_card_id == top
    empty = _seat(state, deck=(), discard_pile=state.players[0].deck)
    private = engine.observe(empty, 0).private
    assert private is not None and private.peeked_card_id == ""


def test_prescience_shows_the_opponents_nothing() -> None:
    # Hidden information (imperium-base.md 14): every other seat sees the
    # same whichever card lies on top.
    engine, state = _start("paul_atreides")
    deck = state.players[0].deck
    turned = _seat(state, deck=(*deck[1:], deck[0]))
    for seat in range(1, 4):
        assert engine.observe(state, seat) == engine.observe(turned, seat)
    assert engine.observe(state, 0) != engine.observe(turned, 0)


def test_discipline_draws_a_card() -> None:
    engine, state = _start("paul_atreides")
    state = _with_card(state, "signet_ring")
    hand = len(state.players[0].hand)
    placed = _place(engine, state, "secure_contract", "signet_ring")
    drawn = _do(engine, placed, "resolve_agent_card_effect")
    assert len(drawn.players[0].hand) == hand - 1 + 1
