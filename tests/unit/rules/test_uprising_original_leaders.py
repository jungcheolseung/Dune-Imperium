"""The original game's Leaders and cards on the Uprising board (stage P7e).

An Uprising game with ``imperium_cards`` (docs/rules/imperium-base.md 13.4,
OQ-155: "옵션 하나로 원판 Imperium·Intrigue 전부(Calculated Hire 빼고)를 섞고
원판 지도자 여덟도 고를 수 있게 한다"). Each Leader sits at seat 0; the
rulings that only this board reaches are docs/base-game-and-ix-plan.md 16.10.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
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

CONFIG = RulesetConfig(imperium_cards=True, first_player_seat_zero=True)
OTHERS = ("muad_dib", "gurney_halleck", "lady_jessica")


def _start(
    leader: str, seed: int = 3, config: RulesetConfig = CONFIG
) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an Uprising game with ``leader`` at seat 0, at its turn."""

    engine = UprisingRulesEngine(leader_ids=(leader, *OTHERS))
    state = engine.reset(config, seed)
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


def _with_card(state: GameState, card_id: str, seat: int = 0) -> GameState:
    """Seat ``seat`` with its starting ``card_id`` in hand (from its deck)."""

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


def _placements(
    state: GameState, space_id: str, card_id: str | None = None
) -> list[DomainAction]:
    return [
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and (
            card_id is None
            or f":{card_id}:" in str(dict(placement.arguments)["card_id"])
        )
    ]


def _wholes(engine: UprisingRulesEngine, state: GameState) -> tuple[DomainAction, ...]:
    return engine.whole_actions(state, 0)


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


# --- Duke Leto Atreides -------------------------------------------------------


def test_landsraad_popularity_takes_a_solari_off_uprisings_swordmaster() -> None:
    # "Landsraad Popularity: Landsraad 칸에 보내는 비용 1 Solari 적게"
    # (imperium-base.md 12): Uprising's Swordmaster is a Landsraad space of
    # "cost 8 Solari, 한 명이라도 얻은 뒤에는 6 Solari" (board-spaces.md,
    # [Board Guide p. 2]) -- 7 and 5 for Leto.
    engine, state = _start("duke_leto_atreides")
    state = _seat(_with_card(state, "dagger"), resources=Resources(solari=7))
    (placement,) = _placements(state, "swordmaster", "dagger")
    placed = apply_placement(engine, state, placement).state
    assert placed.players[0].resources.solari == 0
    opponent = state.players[1]
    held = _seat(
        _seat(
            state,
            1,
            swordmaster_acquired=True,
            agents_available=opponent.agents_available + 1,
        ),
        resources=Resources(solari=5),
    )
    (placement,) = _placements(held, "swordmaster", "dagger")
    placed = apply_placement(engine, held, placement).state
    assert placed.players[0].resources.solari == 0
    # Another Leader pays the printed 8.
    _, other = _start("glossu_rabban")
    other = _seat(_with_card(other, "dagger"), resources=Resources(solari=7))
    assert _placements(other, "swordmaster") == []


# --- Baron Vladimir Harkonnen -----------------------------------------------

BARON = "baron_vladimir_harkonnen"
MOBILIZATION = "intrigue:rapid_mobilization:0"


def _start_baron(
    picks: tuple[str, str] = ("emperor", "fremen"), seed: int = 3
) -> tuple[UprisingRulesEngine, GameState]:
    """The Baron at seat 0 of an Uprising game chooses ``picks`` before the
    first round [FAQ p. 1]."""

    engine = UprisingRulesEngine(leader_ids=(BARON, *OTHERS))
    state = engine.reset(CONFIG, seed)
    for faction in picks:
        state = engine.apply(
            state,
            DomainAction("choose_masterstroke_faction", 0, (("faction", faction),)),
        ).state
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _baron_at_deep_desert() -> tuple[UprisingRulesEngine, GameState]:
    """The Baron's Agent at Deep Desert with Maker Hooks, six troops in his
    garrison and Rapid Mobilization in hand; no Shield Wall in the way."""

    engine, state = _start_baron()
    owner = state.players[0]
    state = _seat(
        _with_card(replace(state, shield_wall_present=False), "dune_the_desert_planet"),
        resources=Resources(water=3),
        maker_hooks=True,
        troops_garrison=6,
        troops_supply=owner.troops_supply + owner.troops_garrison - 6,
        intrigue_cards=(MOBILIZATION,),
    )
    (placement,) = _placements(state, "deep_desert", "dune_the_desert_planet")
    return engine, apply_placement(engine, state, placement).state


def _summon(engine: UprisingRulesEngine, state: GameState) -> GameState:
    action = DomainAction("summon_maker_sandworms", 0, (("space_id", "deep_desert"),))
    return apply_whole(engine, state, action).state


def _mobilize(engine: UprisingRulesEngine, state: GameState, count: int) -> GameState:
    opened = _do(engine, state, "play_intrigue", card_id=MOBILIZATION)
    action = DomainAction("deploy_intrigue_troops", 0, (("count", count),))
    return apply_whole(engine, opened, action).state


def test_masterstroke_leaves_the_sandworms_out_of_his_count() -> None:
    # OQ-115 (user ruling 2026-10-22): troops and Commanders, "현재
    # UnitsDeployedThisTurnAtLeast는 sandworm까지 세는 unit 조건이므로 그 전체
    # 유닛 합계를 Baron의 troop 수와 혼동하지 않는다"; plan 16.10 12: the
    # sandworms of an Uprising board stay out. Two sandworms and two troops
    # are four units, not four troops.
    engine, state = _baron_at_deep_desert()
    summoned = _summon(engine, state)
    assert summoned.players[0].sandworms_conflict == 2
    assert summoned.players[0].masterstroke_sandworms_turn == 2
    deploy = DomainAction("deploy_troops", 0, (("count", 2),))
    two = engine.apply(summoned, deploy).state
    assert two.players[0].units_deployed_turn == 4
    assert two.players[0].masterstroke_revealed is False
    # Two more troops make four: revealed, an Influence with each Faction.
    four = _mobilize(engine, two, 2)
    baron = four.players[0]
    assert baron.masterstroke_revealed is True
    assert baron.influence.emperor == 1 and baron.influence.fremen == 1
    # "조건을 사용한 뒤의 회수 제한을 동일하게 적용" (OQ-115, OQ-029): the four
    # troops stay; the sandworms are never withdrawn.
    assert baron.units_deployed_committed == 4 + 2
    assert not any(
        action.action_id == "withdraw_troops" for action in _wholes(engine, four)
    )


def test_masterstrokes_four_troops_stay_when_sandworms_join_them_later() -> None:
    # The same floor (OQ-029) when the sandworms come after the reveal in
    # the turn: four troops revealed it, so none of them may go back.
    engine, state = _baron_at_deep_desert()
    two = engine.apply(state, DomainAction("deploy_troops", 0, (("count", 2),))).state
    four = _mobilize(engine, two, 2)
    assert four.players[0].masterstroke_revealed is True
    assert four.players[0].units_deployed_committed == 4
    summoned = _summon(engine, four)
    baron = summoned.players[0]
    assert baron.units_deployed_turn == 6
    assert baron.units_deployed_committed == 6
    assert not any(
        action.action_id == "withdraw_troops" for action in _wholes(engine, summoned)
    )


def test_other_seats_count_no_masterstroke_sandworms() -> None:
    # Only the Baron's count leaves them out; every other seat's sandworms
    # stay in its unit count alone (Distraction's "units").
    engine, state = _start("glossu_rabban")
    state = _seat(
        _with_card(replace(state, shield_wall_present=False), "dune_the_desert_planet"),
        resources=Resources(water=3),
        maker_hooks=True,
    )
    (placement,) = _placements(state, "deep_desert", "dune_the_desert_planet")
    summoned = _summon(engine, apply_placement(engine, state, placement).state)
    assert summoned.players[0].units_deployed_turn == 2
    assert summoned.players[0].masterstroke_sandworms_turn == 0


# --- Earl Memnon Thorvald ------------------------------------------------------

MEMNON = "earl_memnon_thorvald"


def _corrinth_reveal(
    leader: str = MEMNON, influence: Influence | None = None
) -> tuple[UprisingRulesEngine, GameState]:
    """``leader`` at seat 0 reveals Corrinth City (an Uprising card) with 5
    Solari and takes its High Council seat."""

    engine, state = _start(leader)
    corrinth = next(
        card
        for card in (*state.imperium_deck, *state.imperium_row)
        if card.startswith("imperium:corrinth_city:")
    )
    owner = state.players[0]
    state = _seat(
        replace(
            state,
            imperium_deck=tuple(c for c in state.imperium_deck if c != corrinth),
            imperium_row=tuple(c for c in state.imperium_row if c != corrinth),
        ),
        hand=(corrinth,),
        deck=(*owner.hand, *owner.deck),
        resources=Resources(solari=5),
        influence=influence or owner.influence,
    )
    revealed = _do(engine, state, "reveal_turn")
    seated = _do(engine, revealed, "take_high_council_from_reveal")
    assert seated.players[0].high_council is True
    return engine, seated


def test_connections_follows_a_seat_taken_off_the_high_council_space() -> None:
    # "Connections: High Council 자리를 얻을 때 Influence 1(진영 골라)"
    # (imperium-base.md 12) is the seat wherever it comes from: plan 16.10
    # 14 -- Uprising's Corrinth City takes one in the Reveal turn, and the
    # Steam app treats both the same way.
    engine, seated = _corrinth_reveal()
    factions = {
        dict(action.arguments)["faction"]
        for action in _wholes(engine, seated)
        if action.action_id == "choose_connections_influence"
    }
    assert factions == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    # It holds the Reveal's end until it is taken, in any order with the
    # Reveal's other effects.
    ids = {action.action_id for action in _wholes(engine, seated)}
    assert "finish_reveal" not in ids
    gained = _do(engine, seated, "choose_connections_influence", faction="emperor")
    before = seated.players[0].influence.emperor
    assert gained.players[0].influence.emperor == before + 1
    ids = {action.action_id for action in _wholes(engine, gained)}
    assert "finish_reveal" in ids
    assert "choose_connections_influence" not in ids


def test_connections_off_the_space_with_every_faction_at_the_top_lapses() -> None:
    # A Faction at 6 gains nothing and is never offered (OQ-060): the row
    # waits and the press lapses it, as on the space.
    engine, seated = _corrinth_reveal(
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    )
    ids = {action.action_id for action in _wholes(engine, seated)}
    assert "choose_connections_influence" not in ids
    assert "finish_reveal" in ids
    finished = engine.apply(seated, DomainAction("finish_reveal", 0))
    assert any(
        event.kind == "leader_ability_lapsed" for event in finished.events
    )


def test_corrinth_citys_seat_owes_no_connections_to_other_leaders() -> None:
    engine, seated = _corrinth_reveal("glossu_rabban")
    ids = {action.action_id for action in _wholes(engine, seated)}
    assert "choose_connections_influence" not in ids
    assert "finish_reveal" in ids


# --- Kwisatz Haderach and Into the Fray ---------------------------------------

BLOODLINES = replace(CONFIG, bloodlines=True)
DUNCAN = "duncan_idaho"


def _duncan_with_kwisatz() -> tuple[UprisingRulesEngine, GameState]:
    """Duncan Idaho (Bloodlines) at seat 0 with Kwisatz Haderach in hand, an
    earlier turn's Into the Fray Agent and a troop in the Conflict."""

    engine, state = _start(DUNCAN, config=BLOODLINES)
    kwisatz = next(
        card
        for card in (*state.imperium_deck, *state.imperium_row)
        if card.startswith("imperium:kwisatz_haderach:")
    )
    owner = state.players[0]
    state = _seat(
        replace(
            state,
            imperium_deck=tuple(c for c in state.imperium_deck if c != kwisatz),
            imperium_row=tuple(c for c in state.imperium_row if c != kwisatz),
        ),
        hand=(kwisatz,),
        deck=(*owner.hand, *owner.deck),
        agents_available=owner.agents_available - 1,
        agent_in_conflict=1,
        troops_garrison=owner.troops_garrison - 1,
        troops_conflict=1,
        combat_strength=2 + 2,
    )
    return engine, state


def test_kwisatz_haderach_sends_the_into_the_fray_agent_out_of_the_conflict() -> None:
    # OQ-146 (가) (user ruling 2026-10-28, "소환도 되는데 퀴사츠 헤더락도
    # 가능하지"): "Conflict에 있는 Into the Fray의 Agent도 Kwisatz Haderach의
    # 출발점이고, 옮기면 유닛으로서 Conflict를 떠난다(recall과 같은 처리, 전투력
    # 갱신)" -- it fought as "a 2 strength unit" [Duncan Idaho card].
    engine, state = _duncan_with_kwisatz()
    sources = {
        dict(placement.arguments).get("from_space")
        for placement in _placements(state, "arrakeen", "kwisatz_haderach")
    }
    assert sources == {None, "conflict"}
    (placement,) = (
        placement
        for placement in _placements(state, "arrakeen", "kwisatz_haderach")
        if dict(placement.arguments).get("from_space") == "conflict"
    )
    moved = apply_placement(engine, state, placement)
    duncan = moved.state.players[0]
    assert duncan.agent_in_conflict == 0
    assert duncan.agent_locations == ("arrakeen",)
    assert duncan.agents_available == state.players[0].agents_available
    # The troop fights on alone, 2 strength.
    assert duncan.combat_strength == 2
    # With no Agent on the Leader, the Conflict's Agents alone let Kwisatz
    # Haderach be played (13.1: "Agent가 남지 않아도 낼 수 있다").
    assert state.players[0].agents_available == 1
    stranded = _seat(state, agents_available=0, agent_in_conflict=2)
    alone = {
        dict(placement.arguments).get("from_space")
        for placement in _placements(stranded, "arrakeen", "kwisatz_haderach")
    }
    assert alone == {"conflict"}


def test_into_the_fray_takes_one_agent_off_a_space_holding_two() -> None:
    # Plan 16.10 8: Kwisatz Haderach can put two of the seat's Agents on one
    # space ("내 다른 Agent가 있는 칸에도", imperium-base.md 16); "You may take
    # the Agent you sent this turn and deploy it to the Conflict" [Duncan
    # Idaho card] moves that one, and the other stays.
    engine, state = _start(DUNCAN, config=BLOODLINES)
    state = _with_card(state, "signet_ring")
    (placement,) = _placements(state, "arrakeen", "signet_ring")[:1]
    placed = apply_placement(engine, state, placement).state
    owner = placed.players[0]
    assert owner.agent_locations == ("arrakeen",)
    # An earlier turn's Kwisatz Haderach had sent another Agent there.
    doubled = _seat(
        placed,
        agents_available=owner.agents_available - 1,
        agent_locations=("arrakeen", "arrakeen"),
    )
    fought = _do(engine, doubled, "deploy_leader_agent")
    duncan = fought.players[0]
    assert duncan.agent_locations == ("arrakeen",)
    assert duncan.agent_in_conflict == 1


# --- The sandworm side of a Maker space: Thumper and Spice Addict ------------

PROMOS = replace(CONFIG, promo_cards=True)
ARIANA = "countess_ariana_thorvald"
_NO_BONUS_SPICE_FAQ = (
    "When playing Uprising, it is possible to harvest no spice from Deep "
    "Desert and Hagga Basin (if there is no bonus spice there, and you choose "
    "to summon a sandworm rather than take base spice). In such a case, you "
    "did not “harvest spice”"
)


def _at_hagga_basin(
    leader: str, card_id: str, bonus: int, config: RulesetConfig = CONFIG
) -> tuple[UprisingRulesEngine, GameState]:
    """``leader``'s Agent at Hagga Basin with ``card_id`` (a starting card or
    one taken from the Imperium deck), Maker Hooks and ``bonus`` spice
    there; no Shield Wall in the way."""

    engine, state = _start(leader, config=config)
    owner = state.players[0]
    if any(f":{card_id}:" in card for card in owner.deck):
        state = _with_card(state, card_id)
    else:
        card = next(
            card
            for card in (*state.imperium_deck, *state.imperium_row)
            if f":{card_id}:" in card
        )
        state = _seat(
            replace(
                state,
                imperium_deck=tuple(c for c in state.imperium_deck if c != card),
                imperium_row=tuple(c for c in state.imperium_row if c != card),
            ),
            hand=(*owner.hand, card),
        )
    state = _seat(
        replace(
            state,
            shield_wall_present=False,
            maker_bonus_spice=tuple(
                (space, bonus if space == "hagga_basin" else amount)
                for space, amount in state.maker_bonus_spice
            ),
        ),
        resources=Resources(water=1),
        maker_hooks=True,
    )
    (placement,) = _placements(state, "hagga_basin", card_id)[:1]
    return engine, apply_placement(engine, state, placement).state


def _summon_at_hagga(engine: UprisingRulesEngine, state: GameState) -> GameState:
    action = DomainAction("summon_maker_sandworms", 0, (("space_id", "hagga_basin"),))
    return apply_whole(engine, state, action).state


def test_thumper_doubles_the_bonus_spice_a_sandworm_visit_harvests() -> None:
    # Plan 16.10 11, from the official FAQ (Countess Ariana): a sandworm in
    # place of the base spice still harvests the bonus spice there
    # (``_NO_BONUS_SPICE_FAQ``: only with none it harvests nothing). Thumper:
    # "Double the bonus spice you harvest with this Agent" -- on that side
    # too.
    engine, state = _at_hagga_basin("glossu_rabban", "thumper", 2, PROMOS)
    spice = state.players[0].resources.spice
    summoned = _summon_at_hagga(engine, state)
    assert summoned.players[0].sandworms_conflict == 1
    assert summoned.players[0].resources.spice == spice + 2 * 2
    # The base-spice side as before: base 2, the bonus doubled.
    harvest = DomainAction("harvest_maker_spice", 0, (("space_id", "hagga_basin"),))
    harvested = apply_whole(engine, state, harvest).state
    assert harvested.players[0].resources.spice == spice + 2 + 2 * 2


def test_spice_addict_takes_one_from_a_sandworm_visits_bonus_spice() -> None:
    # Spice Addict: "spice를 harvest할 때마다 spice 1 덜 얻고 카드 1장"
    # (imperium-base.md 12): a sandworm visit with bonus spice harvests it.
    engine, state = _at_hagga_basin(ARIANA, "dune_the_desert_planet", 2)
    spice = state.players[0].resources.spice
    summoned = _summon_at_hagga(engine, state)
    assert summoned.players[0].sandworms_conflict == 1
    assert summoned.players[0].resources.spice == spice + 2 - 1
    assert summoned.players[0].owed_draws


def test_spice_addict_skips_a_sandworm_visit_without_bonus_spice() -> None:
    # "... In such a case, you did not “harvest spice” … so the “Spice
    # Addict” ability does not apply." (official FAQ, Countess Ariana)
    assert "you did not “harvest spice”" in _NO_BONUS_SPICE_FAQ
    engine, state = _at_hagga_basin(ARIANA, "dune_the_desert_planet", 0)
    spice = state.players[0].resources.spice
    summoned = _summon_at_hagga(engine, state)
    assert summoned.players[0].sandworms_conflict == 1
    assert summoned.players[0].resources.spice == spice
    assert summoned.players[0].owed_draws == ()


def test_spice_addict_comes_off_thumpers_doubled_bonus_on_the_sandworm_side() -> None:
    # "Countess Ariana의 −1은 Carryall·Thumper로 두 배를 한 뒤 harvest 전체에서 한
    # 번 뺀다" (imperium-base.md 16).
    engine, state = _at_hagga_basin(ARIANA, "thumper", 3, PROMOS)
    spice = state.players[0].resources.spice
    summoned = _summon_at_hagga(engine, state)
    assert summoned.players[0].resources.spice == spice + 3 * 2 - 1
    assert summoned.players[0].owed_draws


# --- The original cards grafted (Uprising + Immortality) ---------------------

IMMORTALITY = replace(CONFIG, immortality=True, promo_cards=True)
GHOLA = "tleilaxu:ghola:0"


def _take(state: GameState, *cards: str) -> GameState:
    """Seat 0 with ``cards`` (Imperium or Tleilaxu instances) in hand."""

    owner = state.players[0]
    return _seat(
        replace(
            state,
            imperium_deck=tuple(c for c in state.imperium_deck if c not in cards),
            imperium_row=tuple(c for c in state.imperium_row if c not in cards),
            tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c not in cards),
            tleilaxu_row=tuple(c for c in state.tleilaxu_row if c not in cards),
        ),
        hand=(*owner.hand, *cards),
    )


def _instance(state: GameState, card_id: str) -> str:
    return next(
        card
        for card in (*state.imperium_deck, *state.imperium_row)
        if card.startswith(f"imperium:{card_id}:")
    )


def _grafted(
    engine: UprisingRulesEngine,
    state: GameState,
    card: str,
    space_id: str,
    partner: str,
    **arguments: object,
) -> GameState:
    """Seat 0 places ``card`` grafted at ``space_id`` and takes ``partner``."""

    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and dict(placement.arguments)["card_id"] == card
        and dict(placement.arguments).get("graft") is True
        and all(dict(placement.arguments).get(k) == v for k, v in arguments.items())
    )
    placed = apply_placement(engine, state, placement).state
    return _do(engine, placed, "choose_graft_partner", card_id=partner)


def _hagga_graft(card_id: str, bonus: int) -> tuple[UprisingRulesEngine, GameState]:
    engine, state = _start("glossu_rabban", config=IMMORTALITY)
    card = _instance(state, card_id)
    state = _seat(
        replace(
            _take(state, card, GHOLA),
            maker_bonus_spice=tuple(
                (space, bonus if space == "hagga_basin" else amount)
                for space, amount in state.maker_bonus_spice
            ),
        ),
        resources=Resources(water=1),
    )
    return engine, _grafted(engine, state, card, "hagga_basin", GHOLA)


def test_ghola_grafted_to_carryall_harvests_four_times_the_base_spice() -> None:
    # "Ghola — When grafted to Carryall, you get four times the base spice you
    # harvest with your Agent." [FAQ p. 2]: the harvest reads both grafted
    # boxes and the doublings multiply (plan 16.10 9). Hagga Basin's base is 2.
    engine, state = _hagga_graft("carryall", 1)
    spice = state.players[0].resources.spice
    harvest = DomainAction("harvest_maker_spice", 0, (("space_id", "hagga_basin"),))
    harvested = apply_whole(engine, state, harvest).state
    assert harvested.players[0].resources.spice == spice + 2 * 4 + 1


def test_ghola_grafted_to_thumper_harvests_four_times_the_bonus_spice() -> None:
    # Thumper's "Double the bonus spice you harvest with this Agent" stacks
    # the same way (plan 16.10 9, a project convention: the FAQ names
    # Carryall).
    engine, state = _hagga_graft("thumper", 3)
    spice = state.players[0].resources.spice
    harvest = DomainAction("harvest_maker_spice", 0, (("space_id", "hagga_basin"),))
    harvested = apply_whole(engine, state, harvest).state
    assert harvested.players[0].resources.spice == spice + 2 + 3 * 4


def test_ghola_grafted_to_power_play_gains_only_two_influence() -> None:
    # "If you graft this card with Power Play to send an Agent to a faction
    # board space, you gain only 2 Influence with that faction, the same as
    # if you'd played Power Play alone." [Immortality p. 14]
    engine, state = _start("glossu_rabban", config=IMMORTALITY)
    power_play = _instance(state, "power_play")
    state = _take(state, power_play, GHOLA)
    grafted = _grafted(engine, state, power_play, "secrets", GHOLA)
    before = grafted.players[0].influence.bene_gesserit
    # Both boxes, each its own row (Power Play's, then Ghola's copy).
    first = apply_whole(
        engine, grafted, DomainAction("resolve_agent_card_effect", 0)
    ).state
    done = apply_whole(
        engine, first, DomainAction("resolve_agent_card_effect", 0, (("box", 1),))
    ).state
    ids = {action.action_id for action in _wholes(engine, done)}
    assert "resolve_faction_influence" not in ids
    assert done.players[0].influence.bene_gesserit == before + 2


def test_ghola_grafted_to_kwisatz_haderach_sends_one_agent_and_draws_two() -> None:
    # "When grafted to Kwisatz Haderach, you still send only one Agent on your
    # turn (though you draw two cards)." [FAQ p. 2]
    engine, state = _start("glossu_rabban", config=IMMORTALITY)
    kwisatz = _instance(state, "kwisatz_haderach")
    state = _take(state, kwisatz, GHOLA)
    owner = state.players[0]
    grafted = _grafted(engine, state, kwisatz, "arrakeen", GHOLA)
    seat = grafted.players[0]
    assert seat.agents_available == owner.agents_available - 1
    assert seat.agent_locations == (*owner.agent_locations, "arrakeen")
    hand = len(seat.hand)
    drawn = grafted
    for box in ((), (("box", 1),)):
        drawn = apply_whole(
            engine, drawn, DomainAction("resolve_agent_card_effect", 0, box)
        ).state
    assert len(drawn.players[0].hand) == hand + 2
    assert drawn.players[0].agent_locations == seat.agent_locations


def test_twisted_mentat_names_once_a_space_holding_two_of_the_seats_agents() -> None:
    # Plan 16.10 8: grafted to Kwisatz Haderach, Twisted Mentat's Agent may
    # join the seat's other Agent ("내 다른 Agent가 있는 칸에도", imperium-base.md
    # 16); "You may recall the Agent you sent this turn." [Twisted Mentat card]
    # names that space once (two equal rows broke the staged step, 761cba10)
    # and recalls one of the two.
    engine, state = _start("glossu_rabban", config=IMMORTALITY)
    kwisatz = _instance(state, "kwisatz_haderach")
    mentat = "tleilaxu:twisted_mentat:0"
    owner = state.players[0]
    state = _seat(
        _take(state, kwisatz, mentat),
        agents_available=owner.agents_available - 1,
        agent_locations=("arrakeen",),
    )
    grafted = _grafted(engine, state, kwisatz, "arrakeen", mentat, from_space=None)
    assert grafted.players[0].agent_locations == ("arrakeen", "arrakeen")
    recalls = [
        action
        for action in _wholes(engine, grafted)
        if action.action_id == "recall_agent_for_agent_card"
    ]
    assert recalls == [
        DomainAction(
            "recall_agent_for_agent_card",
            0,
            (("box", 1), ("space_id", "arrakeen")),
        )
    ]
    recalled = apply_whole(engine, grafted, recalls[0]).state
    assert recalled.players[0].agent_locations == ("arrakeen",)
    assert recalled.players[0].agents_available == owner.agents_available - 1
