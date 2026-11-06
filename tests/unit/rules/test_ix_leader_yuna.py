""" "Princess" Yuna Moritani, a Rise of Ix Leader (stage P4e).

docs/rules/rise-of-ix.md 10: ""Princess" Yuna Moritani (2) | Smuggling
Operation: water 없이 시작; 자기 turn에 Solari를 얻을 때마다 1 더 | Final
Delivery: 7 Solari → Influence 1(골라)·troop 1·spice 1 | `[FAQ p. 3]`;
Dividends로 남의 turn에 받는 1 Solari에는 붙지 않는다(OQ-042·OQ-063 "your
turn")". Played through ``UprisingRulesEngine`` in an original game with Rise
of Ix, Yuna at seat 0; every offered row round-trips through ``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    Resources,
    RuleResult,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat_deployment import (
    legal_agent_turn_finish_actions,
    legal_combat_deployments,
)
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.leader_abilities import grant_smuggling_operation
from dune_imperium.rules.shipping_track import recall_freighter

YUNA = "princess_yuna_moritani"
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (YUNA, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, including the intermediate card/space/effect
    choices consumed by apply_whole."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _start(leaders: tuple[str, ...] = LEADERS) -> tuple[_Engine, GameState]:
    engine = _Engine(leader_ids=leaders)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _with_card(state: GameState, card_id: str, seat: int = 0) -> GameState:
    """``seat`` with its starting ``card_id`` in hand (from its deck)."""

    owner = state.players[seat]
    if any(f":{card_id}:" in card for card in owner.hand):
        return state
    instance = next(card for card in owner.deck if f":{card_id}:" in card)
    return _seat(
        state,
        seat,
        hand=(*owner.hand, instance),
        deck=tuple(card for card in owner.deck if card != instance),
    )


def _place(engine: _Engine, state: GameState, space_id: str, card_id: str) -> GameState:
    engine.legal_actions(state, 0)
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and f":{card_id}:" in str(dict(placement.arguments)["card_id"])
    )
    placed = apply_placement(engine, state, placement).state
    engine.legal_actions(placed, 0)
    return placed


def _rows(engine: _Engine, state: GameState) -> tuple[DomainAction, ...]:
    engine.legal_actions(state, 0)
    return engine.whole_actions(state, 0)


def _do(engine: _Engine, state: GameState, action_id: str, **args: object) -> GameState:
    row = next(
        row
        for row in _rows(engine, state)
        if row.action_id == action_id
        and all(dict(row.arguments).get(key) == value for key, value in args.items())
    )
    result = apply_whole(engine, state, row).state
    engine.legal_actions(result, 0)
    return result


# --- Setup and the offer -------------------------------------------------------


def test_yuna_is_offered_with_rise_of_ix_and_starts_with_no_water() -> None:
    """ "Smuggling Operation: water 없이 시작" (rise-of-ix.md 10; 3: "Ix Leader의
    setup: ... "Princess" Yuna Moritani(water 없이 시작)" `[Leader cards]`).
    She joins the original game's Leaders only with Rise of Ix [Rise of Ix
    p. 3]; the others keep their one water."""

    assert YUNA in {leader.leader_id for leader in content_for(CONFIG).leaders}
    plain = RulesetConfig(base_game=BaseGame.IMPERIUM)
    assert YUNA not in {leader.leader_id for leader in content_for(plain).leaders}
    _, state = _start()
    assert state.players[0].leader_id == YUNA
    assert state.players[0].resources.water == 0
    assert [seat.resources.water for seat in state.players[1:]] == [1, 1, 1]


# --- Smuggling Operation -------------------------------------------------------


def test_smuggling_operation_adds_one_solari_to_a_space_s_gain() -> None:
    """ "자기 turn에 Solari를 얻을 때마다 1 더" [FAQ p. 3]: Wealth's 2 Solari
    (an Emperor space) arrive as 3 in her Agent turn, the extra one its own
    gain named after her."""

    engine, state = _start()
    state = _with_card(_seat(state, resources=Resources()), "diplomacy")
    placed = _place(engine, state, "wealth", "diplomacy")
    solari = placed.players[0].resources.solari
    result = apply_whole(
        engine,
        placed,
        next(
            row
            for row in _rows(engine, placed)
            if row.action_id == "resolve_board_effect"
            and dict(row.arguments).get("effect") == "resources"
        ),
    )
    assert result.state.players[0].resources.solari == solari + 2 + 1
    (bonus,) = (
        event
        for event in result.events
        if event.kind == "resources_gained"
        and f":leader:{YUNA}:" in str(dict(event.payload)["source"])
    )
    assert dict(bonus.payload)["solari"] == 1
    assert dict(bonus.payload)["player"] == 0


def test_smuggling_operation_adds_one_to_her_own_dividends_only() -> None:
    """ "예: Freighter 회수의 5 Solari" [FAQ p. 3]: her Dividends pay her 6 in
    her turn, while each opponent's 1 Solari is no gain of hers."""

    engine, state = _start()
    state = recall_freighter(_seat(state, freighter_space=1), 0, source="s").state
    before = [seat.resources.solari for seat in state.players]
    row = DomainAction("resolve_shipping_reward", 0, (("effect", "dividends"),))
    assert row in engine.legal_actions(state, 0)
    paid = engine.apply(state, row).state
    assert paid.players[0].resources.solari == before[0] + 5 + 1
    for seat in (1, 2, 3):
        assert paid.players[seat].resources.solari == before[seat] + 1


def test_smuggling_operation_misses_an_opponent_s_dividends() -> None:
    """ "Dividends로 남의 turn에 받는 1 Solari에는 붙지 않는다(OQ-042·OQ-063 "your
    turn")" (rise-of-ix.md 10): an opponent's recall in their own turn pays
    her the plain 1 Solari."""

    engine, state = _start(
        ("glossu_rabban", YUNA, "count_ilban_richese", "earl_memnon_thorvald")
    )
    assert state.players[1].leader_id == YUNA
    state = recall_freighter(_seat(state, freighter_space=1), 0, source="s").state
    solari = state.players[1].resources.solari
    row = DomainAction("resolve_shipping_reward", 0, (("effect", "dividends"),))
    paid = engine.apply(state, row)
    assert paid.state.players[1].resources.solari == solari + 1
    assert not any(f":leader:{YUNA}:" in event.event_id for event in paid.events)


def _gain(player: int, solari: int, source: str) -> GameEvent:
    return resources_gained_event(source, player, solari=solari)


def test_smuggling_operation_counts_each_gain_and_stops_when_her_reveal_ends() -> None:
    """Each Solari gain of her turn adds one ("Whenever you gain [Solari] on
    your turn", app text) -- two gains, two more -- and a Reveal turn's end
    ends her turn: the Combat phase is no turn [Main p. 8] (OQ-063), so a
    Solari the same transition pays after ``reveal_finished`` gains none."""

    _, state = _start()
    events = (
        _gain(0, 2, "a"),
        _gain(1, 3, "b"),
        _gain(0, 1, "c"),
        GameEvent("r", "reveal_finished", (("player", 0),)),
        _gain(0, 4, "combat"),
    )
    solari = state.players[0].resources.solari
    granted = grant_smuggling_operation(RuleResult(state=state, events=events), state)
    assert granted.state.players[0].resources.solari == solari + 2
    assert granted.state.players[1].resources == state.players[1].resources
    assert len(granted.events) == len(events) + 2

    # A transition begun outside her turn (here in the Combat phase, no
    # turn [Main p. 8]) adds nothing.
    combat = replace(state, phase=GamePhase.COMBAT)
    plain = RuleResult(state=combat, events=(_gain(0, 2, "a"),))
    assert grant_smuggling_operation(plain, combat) is plain


def test_smuggling_operation_adds_one_to_an_influence_track_bonus() -> None:
    """The Spacing Guild track's 4-space bonus is 3 Solari [DI p. 7]; reached
    in her turn it is a Solari gain like any other (rise-of-ix.md 10)."""

    _, state = _start()
    bonus = GameEvent(
        "t",
        "influence_track_bonus_gained",
        (("faction", "spacing_guild"), ("player", 0), ("solari", 3)),
    )
    solari = state.players[0].resources.solari
    granted = grant_smuggling_operation(RuleResult(state=state, events=(bonus,)), state)
    assert granted.state.players[0].resources.solari == solari + 1


# --- Final Delivery ------------------------------------------------------------


def _signet(engine: _Engine, state: GameState, **changes: object) -> GameState:
    """Seat 0 sends the Signet Ring to Arrakeen (a Combat space)."""

    state = _seat(_with_card(state, "signet_ring"), **changes)
    return _place(engine, state, "arrakeen", "signet_ring")


def _offered(engine: _Engine, state: GameState) -> set[tuple[str, str | None]]:
    signet = {
        "decline_leader_signet_payment",
        "choose_leader_signet_influence",
        "pay_leader_signet_solari",
    }
    return {
        (row.action_id, dict(row.arguments).get("faction"))  # type: ignore[misc]
        for row in _rows(engine, state)
        if row.action_id in signet
    }


def test_final_delivery_buys_an_influence_a_troop_and_a_spice() -> None:
    """ "Final Delivery: 7 Solari → Influence 1(골라)·troop 1·spice 1"
    (rise-of-ix.md 10): an arrow, so never forced -- unused, it offers no
    refusal in an Agent turn and lapses with it (OQ-095 (2)); the Influence
    is any Faction but one at the top (OQ-060, rise-of-ix.md 15), and a
    troop recruited while visiting a Combat space may deploy [FAQ p. 4]."""

    engine, state = _start()
    placed = _signet(
        engine, state, resources=Resources(solari=7), influence=Influence(fremen=6)
    )
    assert _offered(engine, placed) == {
        ("choose_leader_signet_influence", "emperor"),
        ("choose_leader_signet_influence", "spacing_guild"),
        ("choose_leader_signet_influence", "bene_gesserit"),
    }
    owner = placed.players[0]
    paid = _do(engine, placed, "choose_leader_signet_influence", faction="emperor")
    after = paid.players[0]
    assert after.resources.solari == 0
    assert after.resources.spice == owner.resources.spice + 1
    assert after.influence.emperor == 1
    assert after.troops_garrison == owner.troops_garrison + 1
    assert after.troops_supply == owner.troops_supply - 1
    assert legal_combat_deployments(paid, 0)


def test_final_delivery_without_seven_solari_offers_only_the_refusal() -> None:
    """The arrow's 7 Solari must be paid (rise-of-ix.md 10): with 6 nothing
    is offered, and once the space's own effects are done the turn may end
    with the Signet unused (OQ-095 (2))."""

    engine, state = _start()
    placed = _signet(engine, state, resources=Resources(solari=6))
    assert _offered(engine, placed) == set()
    while not legal_agent_turn_finish_actions(placed, 0):
        effect = next(
            row
            for row in _rows(engine, placed)
            if row.action_id == "resolve_board_effect"
        )
        placed = _do(engine, placed, effect.action_id, **dict(effect.arguments))
    assert placed.players[0].resources.solari == 6


def test_final_delivery_with_every_faction_at_the_top_still_pays_the_rest() -> None:
    """With every Faction at the top its Influence is lost (OQ-060), but the
    troop and the spice are still bought: one row pays the 7 Solari."""

    engine, state = _start()
    top = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    placed = _signet(engine, state, resources=Resources(solari=7), influence=top)
    assert _offered(engine, placed) == {("pay_leader_signet_solari", None)}
    owner = placed.players[0]
    paid = _do(engine, placed, "pay_leader_signet_solari").players[0]
    assert paid.resources.solari == 0
    assert paid.resources.spice == owner.resources.spice + 1
    assert paid.troops_garrison == owner.troops_garrison + 1
    assert paid.influence == top
