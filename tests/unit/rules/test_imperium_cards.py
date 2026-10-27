"""The original Dune: Imperium's Imperium cards (stage P3, trial transcription).

docs/rules/imperium-base.md 7, 11, 13.2 and docs/base-game-and-ix-plan.md 16.
The cards are not in the original game's deck yet (plan 16.1), so each test
puts the card instance into seat 0's hand of an original-game round; the
printed values are the Steam app's attribute table (plan 2.4, D1).
"""

from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
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
from dune_imperium.display.unavailable import unavailable_choices
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquire_icons import acquire_box_icons
from dune_imperium.rules.acquisition import acquire_imperium_for_intrigue
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat_deployment import legal_combat_deployments
from dune_imperium.rules.frames import FrameKind

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)


def _start(seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an original game at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _with_card(
    state: GameState, card_id: str, *, alone: bool = False
) -> tuple[GameState, str]:
    """Seat 0 with copy 0 of the Imperium card ``card_id`` in hand (the only
    card when ``alone``); returns the instance id too."""

    instance = f"imperium:{card_id}:0"
    owner = state.players[0]
    hand = (instance,) if alone else (*owner.hand, instance)
    return _seat(state, hand=hand), instance


def _place(
    engine: UprisingRulesEngine, state: GameState, space_id: str, card_id: str
) -> GameState:
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and f":{card_id}:" in str(dict(placement.arguments)["card_id"])
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


def _reveal(engine: UprisingRulesEngine, state: GameState) -> dict[str, object]:
    """The Reveal frame's context after seat 0 reveals its hand."""

    revealed = _do(engine, state, "reveal_turn")
    return dict(revealed.decision_stack[-1].context)


# --- Arrakis Recruiter ------------------------------------------------------------


def test_arrakis_recruiter_matches_the_app_table() -> None:
    # App attribute table: cost 2, 2 copies, City, no Faction, Reveal 1
    # Persuasion and 1 sword; AgentTroops 1.
    entry = IMPERIUM_CARDS_BY_ID["arrakis_recruiter"]
    assert entry.card.name == "Arrakis Recruiter"
    assert entry.acquisition_cost == 2
    assert entry.copies == 2
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is PersonalCardAgentEffect.RECRUIT_ONE_TROOP
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:arrakis_recruiter:1") is entry
    # From stage P3a the original deck holds it (plan 16.1).
    deck = content_for(CONFIG).imperium_deck_instance_ids
    assert "imperium:arrakis_recruiter:1" in deck


def test_arrakis_recruiter_recruits_one_troop() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "arrakis_recruiter")
    state = _seat(state, resources=Resources(water=2))
    owner = state.players[0]
    placed = _place(engine, state, "imperium_research_station", "arrakis_recruiter")
    assert placed.players[0].troops_garrison == owner.troops_garrison
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    after = resolved.players[0]
    assert after.troops_garrison == owner.troops_garrison + 1
    assert after.troops_supply == owner.troops_supply - 1


def test_arrakis_recruiter_troop_deploys_at_a_combat_space() -> None:
    """"Combat 칸(사막 그림과 교차한 칼)에 Agent를 보내면 이번 turn에 recruit한
    troop 전부와 garrison의 troop 둘까지를 Conflict에 배치할 수 있다."
    [DI pp. 10, 17-18] (imperium-base.md 7); Research Station is a Combat
    space. The card prints no deployment of its own, so the recruited troop
    joins the garrison's two: three in all."""

    engine, state = _start()
    state, _ = _with_card(state, "arrakis_recruiter")
    state = _seat(state, resources=Resources(water=2))
    placed = _place(engine, state, "imperium_research_station", "arrakis_recruiter")
    before = {
        int(dict(action.arguments)["count"])
        for action in legal_combat_deployments(placed, 0)
    }
    assert max(before) == 2
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    after = {
        int(dict(action.arguments)["count"])
        for action in legal_combat_deployments(resolved, 0)
    }
    assert max(after) == 3
    deployed = _do(engine, resolved, "deploy_troops", count=3)
    assert deployed.players[0].troops_conflict == 3


def test_arrakis_recruiter_reveals_one_persuasion_and_one_sword() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "arrakis_recruiter", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 1


# --- Spice Smugglers --------------------------------------------------------------


def _smugglers_placed(
    engine: UprisingRulesEngine,
    state: GameState,
    influence: Influence | None = None,
) -> GameState:
    """Seat 0 sends Spice Smugglers to Research Station (a City space; its
    two water are paid) with 3 spice, 1 Solari and the given Influence."""

    held, _ = _with_card(state, "spice_smugglers")
    seated = _seat(
        held,
        resources=Resources(water=2, spice=3, solari=1),
        influence=influence or Influence(),
    )
    return _place(engine, seated, "imperium_research_station", "spice_smugglers")


def test_spice_smugglers_matches_the_app_table() -> None:
    # App attribute table: cost 2, 2 copies, Spacing Guild, City, Reveal 1
    # Persuasion and 1 sword.
    entry = IMPERIUM_CARDS_BY_ID["spice_smugglers"]
    assert entry.card.name == "Spice Smugglers"
    assert entry.acquisition_cost == 2
    assert entry.copies == 2
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_PAY_TWO_SPICE_FOR_SPACING_GUILD_INFLUENCE_AND_THREE_SOLARI
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:spice_smugglers:1") is entry


def test_spice_smugglers_pays_two_spice_for_influence_and_three_solari() -> None:
    """"비용 화살표" [DI p. 16]: the arrow's cost is paid for its reward. Two
    spice buy one Spacing Guild Influence and 3 Solari."""

    engine, state = _start()
    placed = _smugglers_placed(engine, state)
    before = placed.players[0]
    assert "pay_agent_card_spice" in _ids(engine, placed)
    paid = _do(engine, placed, "pay_agent_card_spice")
    after = paid.players[0]
    assert after.resources.spice == before.resources.spice - 2
    assert after.resources.solari == before.resources.solari + 3
    assert after.influence.spacing_guild == before.influence.spacing_guild + 1
    assert after.influence == replace(before.influence, spacing_guild=1)
    assert after.spice_spent_turn == before.spice_spent_turn + 2


def test_spice_smugglers_arrow_is_paid_once() -> None:
    """"An arrow cost is optional [DI p. 9] and paid once [FAQ p. 3]": with
    spice for a second payment the arrow is no longer offered."""

    engine, state = _start()
    placed = _smugglers_placed(engine, state)
    rich = _seat(placed, resources=replace(placed.players[0].resources, spice=6))
    paid = _do(engine, rich, "pay_agent_card_spice")
    assert paid.players[0].resources.spice == 4
    assert "pay_agent_card_spice" not in _ids(engine, paid)


def test_spice_smugglers_arrow_is_optional() -> None:
    """The arrow cost is optional [DI p. 9]: the owner who does not pay ends
    the turn with spice, Solari and Influence as they were."""

    engine, state = _start()
    placed = _smugglers_placed(engine, state)
    before = placed.players[0]
    resolved = _do(engine, placed, "resolve_board_effect", effect="cards")
    assert "pay_agent_card_spice" in _ids(engine, resolved)
    finished = _do(engine, resolved, "finish_agent_turn")
    after = finished.players[0]
    assert after.resources.spice == before.resources.spice
    assert after.resources.solari == before.resources.solari
    assert after.influence == before.influence


def test_spice_smugglers_needs_two_spice_to_pay() -> None:
    engine, state = _start()
    placed = _smugglers_placed(engine, state)
    poor = _seat(placed, resources=replace(placed.players[0].resources, spice=1))
    assert "pay_agent_card_spice" not in _ids(engine, poor)
    exact = _seat(placed, resources=replace(placed.players[0].resources, spice=2))
    paid = _do(engine, exact, "pay_agent_card_spice")
    assert paid.players[0].resources.spice == 0


def test_spice_smugglers_at_the_top_of_the_track_still_pays_its_solari() -> None:
    """"비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다" (imperium-base.md
    16, OQ-071): the 3 Solari are a reward, so the arrow is offered with the
    Spacing Guild cube at 6. The Influence gain there is dropped: "엔진은 처음부터
    6에 있는 cube에 대한 Influence 획득을 버린다" (OQ-060)."""

    engine, state = _start()
    placed = _smugglers_placed(engine, state, Influence(spacing_guild=6))
    before = placed.players[0]
    assert "pay_agent_card_spice" in _ids(engine, placed)
    after = _do(engine, placed, "pay_agent_card_spice").players[0]
    assert after.influence.spacing_guild == 6
    assert after.resources.solari == before.resources.solari + 3
    assert after.resources.spice == before.resources.spice - 2


def test_spice_smugglers_influence_takes_the_normal_influence_path() -> None:
    # "처음 4에 도달한 플레이어가 Alliance token과 그 VP를 얻고" [DI p. 7]
    # (imperium-base.md 6): the paid Influence is an ordinary Faction gain.
    engine, state = _start()
    placed = _smugglers_placed(engine, state, Influence(spacing_guild=3))
    assert placed.players[0].alliance_faction_ids == ()
    paid = _do(engine, placed, "pay_agent_card_spice")
    assert paid.players[0].influence.spacing_guild == 4
    assert paid.players[0].alliance_faction_ids == ("spacing_guild",)


def test_spice_smugglers_reveals_one_persuasion_and_one_sword() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "spice_smugglers", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 1


# --- Gun Thopter ------------------------------------------------------------------


def _with_troops(
    state: GameState, seat: int, garrison: int, conflict: int = 0
) -> GameState:
    """``seat`` with that many troops in the garrison and the Conflict (the
    rest in its supply)."""

    return _seat(
        state,
        seat,
        troops_garrison=garrison,
        troops_conflict=conflict,
        troops_supply=12 - garrison - conflict,
    )


def _thopter_resolved(
    engine: UprisingRulesEngine, state: GameState
) -> tuple[GameState, GameState]:
    """The state before and after seat 0 plays Gun Thopter's Agent box at
    Secure Contract (a Spice Trade space), the opponents' windows open."""

    held, _ = _with_card(state, "gun_thopter")
    placed = _place(engine, held, "secure_contract", "gun_thopter")
    return placed, _do(engine, placed, "resolve_agent_card_effect")


def _answer(
    engine: UprisingRulesEngine, state: GameState, seat: int, action_id: str
) -> GameState:
    action = next(
        action
        for action in engine.whole_actions(state, seat)
        if action.action_id == action_id
    )
    return apply_whole(engine, state, action).state


def test_gun_thopter_matches_the_app_table() -> None:
    # App attribute table: cost 4, 2 copies, City and Spice Trade, no Faction,
    # Reveal 3 swords and no Persuasion.
    entry = IMPERIUM_CARDS_BY_ID["gun_thopter"]
    assert entry.card.name == "Gun Thopter"
    assert entry.acquisition_cost == 4
    assert entry.copies == 2
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.EACH_OPPONENT_LOSES_GARRISON_TROOP
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 3)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_DEPLOY_ONE_TROOP,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:gun_thopter:1") is entry


def test_gun_thopter_takes_one_garrisoned_troop_from_each_opponent() -> None:
    """"| Gun Thopter | 2 | garrison troop이 없는 상대는 영향 없음 |" [FAQ p. 2]
    (imperium-base.md 13.2); the lost troop goes to its owner's supply ("troop
    잃기(supply로)" [DI p. 16]); "\"each opponent\"는 다음 좌석부터 시계 방향"
    (imperium-base.md 16, OQ-036). The Conflict's troops are not touched."""

    engine, state = _start()
    for seat in (1, 2, 3):
        state = _with_troops(state, seat, garrison=2, conflict=1)
    _, resolved = _thopter_resolved(engine, state)
    # Seat 1, the next seat clockwise, answers first; each window is its own
    # seat's and the card's owner has none.
    assert resolved.decision_stack[-1].kind == FrameKind.OPPONENT_UNIT_LOSS
    owners = [
        frame.decision.owner
        for frame in resolved.decision_stack
        if frame.kind == FrameKind.OPPONENT_UNIT_LOSS
        and isinstance(frame.decision, PlayerDecision)
    ]
    assert owners == [3, 2, 1]
    for seat in (1, 2, 3):
        # Only the seat whose window is on top has anything to answer.
        assert [
            (action.action_id, dict(action.arguments))
            for action in engine.whole_actions(resolved, seat)
        ] == [("lose_unit", {"zone": "garrison"})]
        assert not engine.whole_actions(resolved, 0)
        resolved = _answer(engine, resolved, seat, "lose_unit")
        loser = resolved.players[seat]
        assert (loser.troops_garrison, loser.troops_conflict) == (1, 1)
        assert loser.troops_supply == 12 - 1 - 1
    assert resolved.players[0].troops_garrison == state.players[0].troops_garrison
    assert not any(
        frame.kind == FrameKind.OPPONENT_UNIT_LOSS for frame in resolved.decision_stack
    )


def test_gun_thopter_leaves_an_opponent_with_no_garrisoned_troop_alone() -> None:
    """"garrison troop이 없는 상대는 영향 없음" [FAQ p. 2]: its Conflict troops
    stay. The window still opens (OQ-036 (a), user ruling 2026-09-30: "선택지가 단
    하나여도 어쨌든 확인을 거치는 걸로"), offering the one confirmation."""

    engine, state = _start()
    state = _with_troops(state, 1, garrison=0, conflict=2)
    state = _with_troops(state, 2, garrison=0, conflict=0)
    state = _with_troops(state, 3, garrison=1)
    _, resolved = _thopter_resolved(engine, state)
    for seat in (1, 2):
        assert [
            action.action_id for action in engine.whole_actions(resolved, seat)
        ] == ["resolve_unit_loss_without_unit"]
        resolved = _answer(engine, resolved, seat, "resolve_unit_loss_without_unit")
    after = resolved.players
    assert (after[1].troops_garrison, after[1].troops_conflict) == (0, 2)
    assert after[1].troops_supply == state.players[1].troops_supply
    assert after[2].troops_supply == state.players[2].troops_supply
    resolved = _answer(engine, resolved, 3, "lose_unit")
    assert resolved.players[3].troops_garrison == 0
    assert resolved.players[3].troops_supply == 12


def test_gun_thopter_window_lists_the_garrison_alone() -> None:
    """The window lists the garrison's troop only: a seat with no Conflict
    troop gets no greyed Conflict row (Holy War's window would grey one; the
    Conflict is no option here), and a seat with no garrisoned troop gets the
    garrison row greyed with the window's "no unit" reason."""

    engine, state = _start()
    state = _with_troops(state, 1, garrison=3, conflict=0)
    state = _with_troops(state, 2, garrison=0, conflict=3)
    _, resolved = _thopter_resolved(engine, state)

    def rows(at: GameState, seat: int) -> dict[str, str]:
        found = unavailable_choices(at, seat, engine.whole_actions(at, seat))
        return (
            {}
            if found is None
            else {
                str(row["key"]): str(row["reason"])
                for row in found["rows"]  # type: ignore[attr-defined]
                if str(row["key"]).startswith("choice:lose_unit:")
            }
        )

    assert rows(resolved, 1) == {}
    after_one = _answer(engine, resolved, 1, "lose_unit")
    assert rows(after_one, 2) == {"choice:lose_unit:garrison:0": "No unit to lose"}


def test_gun_thopter_reveals_three_swords_and_may_deploy_a_garrison_troop() -> None:
    """The Reveal's swords count once a troop stands in the Conflict ("Conflict에
    troop이 하나도 없으면 0" [DI p. 11]); "You may deploy a troop from your
    garrison to the Conflict" [Gun Thopter card], optional, one troop (P0 sweep
    S14). Deploying it makes 2 for the troop and 3 swords: 5."""

    engine, state = _start()
    state, _ = _with_card(state, "gun_thopter", alone=True)
    garrison = state.players[0].troops_garrison
    revealed = _do(engine, state, "reveal_turn")
    assert dict(revealed.decision_stack[-1].context)["sword_strength"] == 3
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 0
    assert "deploy_reveal_card_troop" in _ids(engine, revealed)
    # Optional: the owner who does not deploy has no troop to fight with.
    declined = _do(engine, revealed, "finish_reveal")
    assert declined.players[0].combat_strength == 0
    deployed = _do(engine, revealed, "deploy_reveal_card_troop")
    assert deployed.players[0].troops_garrison == garrison - 1
    assert deployed.players[0].troops_conflict == 1
    # One troop only: the choice is used up.
    assert "deploy_reveal_card_troop" not in _ids(engine, deployed)
    finished = _do(engine, deployed, "finish_reveal")
    assert finished.players[0].combat_strength == 2 + 3


def test_gun_thopter_cannot_deploy_from_an_empty_garrison() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "gun_thopter", alone=True)
    state = _with_troops(state, 0, garrison=0)
    revealed = _do(engine, state, "reveal_turn")
    assert "deploy_reveal_card_troop" not in _ids(engine, revealed)
    assert "finish_reveal" in _ids(engine, revealed)


# --- Bene Gesserit Initiate -------------------------------------------------------


def test_bene_gesserit_initiate_matches_the_app_table() -> None:
    # App attribute table: cost 3, 2 copies, Bene Gesserit, Landsraad, City and
    # Spice Trade, Reveal 1 Persuasion and no swords.
    entry = IMPERIUM_CARDS_BY_ID["bene_gesserit_initiate"]
    assert entry.card.name == "Bene Gesserit Initiate"
    assert entry.acquisition_cost == 3
    assert entry.copies == 2
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:bene_gesserit_initiate:1") is entry


def test_bene_gesserit_initiate_draws_one_card() -> None:
    """P0 sweep: "AGENT: draw 1 (must; hidden draw, its own step -- OQ-106)".
    The draw icon is mandatory ("everything else mandatory" [FAQ p. 3]), a
    hidden draw (imperium-base.md 16, OQ-106), and takes the deck's top card."""

    engine, state = _start()
    state, _ = _with_card(state, "bene_gesserit_initiate")
    state = _seat(state, resources=Resources(water=2))
    owner = state.players[0]
    top = owner.deck[0]
    placed = _place(
        engine, state, "imperium_research_station", "bene_gesserit_initiate"
    )
    assert placed.players[0].hand == tuple(
        card for card in owner.hand if ":bene_gesserit_initiate:" not in card
    )
    # Mandatory: the turn cannot end with the draw still waiting.
    assert "resolve_agent_card_effect" in _ids(engine, placed)
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    after = resolved.players[0]
    assert after.hand == (*placed.players[0].hand, top)
    assert after.deck == owner.deck[1:]


def test_bene_gesserit_initiate_reveals_one_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "bene_gesserit_initiate", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 0


# --- Bene Gesserit Sister ---------------------------------------------------------


def test_bene_gesserit_sister_matches_the_app_table() -> None:
    # App attribute table: cost 3, 3 copies, Bene Gesserit, Bene Gesserit and
    # Landsraad, no fixed Reveal values (tag ConditionalStrength).
    entry = IMPERIUM_CARDS_BY_ID["bene_gesserit_sister"]
    assert entry.card.name == "Bene Gesserit Sister"
    assert entry.acquisition_cost == 3
    assert entry.copies == 3
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.LANDSRAAD)
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.CHOOSE_TWO_PERSUASION_OR_TWO_STRENGTH,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:bene_gesserit_sister:2") is entry


def test_bene_gesserit_sister_agent_box_is_empty() -> None:
    # P0 sweep: "AGENT: none"; the icons only send the Agent to a Bene
    # Gesserit or Landsraad space.
    engine, state = _start()
    state, _ = _with_card(state, "bene_gesserit_sister")
    placed = _place(engine, state, "secrets", "bene_gesserit_sister")
    assert "resolve_agent_card_effect" not in _ids(engine, placed)
    assert _place(engine, state, "hall_of_oratory", "bene_gesserit_sister")


def _sister_revealed(
    engine: UprisingRulesEngine, state: GameState, *, conflict: int = 0
) -> GameState:
    """Seat 0 reveals Bene Gesserit Sister alone, with ``conflict`` troops
    already in the Conflict."""

    state, _ = _with_card(state, "bene_gesserit_sister", alone=True)
    state = _with_troops(state, 0, garrison=0, conflict=conflict)
    return _do(engine, state, "reveal_turn")


def test_bene_gesserit_sister_must_pick_persuasion_or_swords() -> None:
    """"-OR-" is a must-pick-one choice (P0 sweep; imperium-base.md 16, OQ-058
    for the same shape on Intrigue): both rows are offered, nothing else holds
    the Reveal open, and the turn cannot finish before one is taken."""

    engine, state = _start()
    revealed = _sister_revealed(engine, state)
    assert _ids(engine, revealed) == {
        "gain_two_reveal_persuasion",
        "gain_two_reveal_swords",
    }
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (0, 0)


def test_bene_gesserit_sister_two_persuasion_branch() -> None:
    engine, state = _start()
    revealed = _sister_revealed(engine, state, conflict=1)
    chosen = _do(engine, revealed, "gain_two_reveal_persuasion")
    frame = dict(chosen.decision_stack[-1].context)
    assert frame["persuasion"] == 2
    # The other alternative is gone and the Reveal can end.
    assert "gain_two_reveal_swords" not in _ids(engine, chosen)
    assert "gain_two_reveal_persuasion" not in _ids(engine, chosen)
    assert "finish_reveal" in _ids(engine, chosen)
    # Only the troop's 2 count: the swords branch was not taken.
    assert _do(engine, chosen, "finish_reveal").players[0].combat_strength == 2


def test_bene_gesserit_sister_two_swords_branch() -> None:
    """The swords count once a troop stands in the Conflict ("Conflict에 troop이
    하나도 없으면 0" [DI p. 11]): with one there, 2 for the troop and 2 swords."""

    engine, state = _start()
    revealed = _sister_revealed(engine, state, conflict=1)
    chosen = _do(engine, revealed, "gain_two_reveal_swords")
    assert dict(chosen.decision_stack[-1].context)["persuasion"] == 0
    assert "gain_two_reveal_persuasion" not in _ids(engine, chosen)
    assert _do(engine, chosen, "finish_reveal").players[0].combat_strength == 2 + 2


def test_bene_gesserit_sister_swords_need_a_troop_in_the_conflict() -> None:
    engine, state = _start()
    revealed = _sister_revealed(engine, state, conflict=0)
    chosen = _do(engine, revealed, "gain_two_reveal_swords")
    finished = _do(engine, chosen, "finish_reveal")
    assert finished.players[0].combat_strength == 0


def test_two_bene_gesserit_sisters_each_settle_their_own_choice() -> None:
    engine, state = _start()
    both = _seat(
        state,
        hand=("imperium:bene_gesserit_sister:0", "imperium:bene_gesserit_sister:1"),
    )
    both = _with_troops(both, 0, garrison=0, conflict=1)
    revealed = _do(engine, both, "reveal_turn")
    first = _do(engine, revealed, "gain_two_reveal_persuasion")
    # The second copy still waits: its choice is its own.
    assert "finish_reveal" not in _ids(engine, first)
    second = _do(engine, first, "gain_two_reveal_swords")
    assert dict(second.decision_stack[-1].context)["persuasion"] == 2
    assert _do(engine, second, "finish_reveal").players[0].combat_strength == 2 + 2


# --- Crysknife --------------------------------------------------------------------


def test_crysknife_matches_the_app_table() -> None:
    # App attribute table: cost 3, 1 copy, Fremen, Fremen and Spice Trade,
    # Reveal 1 sword and no Persuasion; AgentSolari 1.
    entry = IMPERIUM_CARDS_BY_ID["crysknife_card"]
    assert entry.card.name == "Crysknife"
    assert entry.acquisition_cost == 3
    assert entry.copies == 1
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.FREMEN, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is PersonalCardAgentEffect.GAIN_ONE_SOLARI
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 1)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:crysknife_card:0") is entry


def test_crysknife_agent_box_gains_one_solari() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "crysknife_card")
    state = _seat(state, resources=Resources(water=2, solari=4))
    placed = _place(engine, state, "hardy_warriors", "crysknife_card")
    before = placed.players[0].resources
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].resources.solari == before.solari + 1
    assert resolved.players[0].resources.spice == before.spice


def _crysknife_revealed(
    engine: UprisingRulesEngine, state: GameState, *others: str
) -> GameState:
    """Seat 0 reveals Crysknife with the given other cards (instance ids)."""

    held, instance = _with_card(state, "crysknife_card", alone=True)
    held = _seat(held, hand=(instance, *others), influence=Influence(fremen=2))
    return _do(engine, held, "reveal_turn")


def test_crysknife_reveals_one_sword_and_no_persuasion() -> None:
    engine, state = _start()
    frame = dict(_crysknife_revealed(engine, state).decision_stack[-1].context)
    assert frame["persuasion"] == 0
    assert frame["sword_strength"] == 1


def test_crysknife_fremen_bond_gains_one_fremen_influence() -> None:
    """"Fremen Bond = another Fremen card in play" [DI p. 16] (imperium-base.md
    11); Influence is gained as an ordinary Faction gain ("Influence 얻기"
    [DI p. 16], 11): Fremen 2 becomes 3. Fedaykin Stilltent is another Fremen
    card."""

    engine, state = _start()
    revealed = _crysknife_revealed(engine, state, "imperium:fedaykin_stilltent:0")
    assert "gain_reveal_faction_influence" in _ids(engine, revealed)
    gained = _do(engine, revealed, "gain_reveal_faction_influence", faction="fremen")
    assert gained.players[0].influence.fremen == 3
    assert gained.players[0].influence == Influence(fremen=3)


def test_crysknife_without_a_bond_gains_no_influence() -> None:
    """Crysknife alone is no "another Fremen card"; a card of another Faction
    does not make the Bond either."""

    engine, state = _start()
    starter = state.players[0].hand[0]
    for others in ((), (starter,)):
        revealed = _crysknife_revealed(engine, state, *others)
        assert "gain_reveal_faction_influence" not in _ids(engine, revealed)
        assert _do(engine, revealed, "finish_reveal").players[0].influence == Influence(
            fremen=2
        )


# --- Dr. Yueh ---------------------------------------------------------------------


def test_dr_yueh_matches_the_app_table() -> None:
    # App attribute table: cost 1, 1 copy, no Faction, City, Reveal 1
    # Persuasion and no swords.
    entry = IMPERIUM_CARDS_BY_ID["dr_yueh"]
    assert entry.card.name == "Dr. Yueh"
    assert entry.acquisition_cost == 1
    assert entry.copies == 1
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:dr_yueh:0") is entry


def test_dr_yueh_draws_one_card() -> None:
    """P0 sweep: "AGENT: draw 1"; the draw icon is mandatory and a hidden draw
    is its own step ([FAQ p. 3], imperium-base.md 16, OQ-106)."""

    engine, state = _start()
    state, _ = _with_card(state, "dr_yueh")
    state = _seat(state, resources=Resources(water=2))
    top = state.players[0].deck[0]
    placed = _place(engine, state, "imperium_research_station", "dr_yueh")
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].hand == (*placed.players[0].hand, top)
    assert resolved.players[0].deck == placed.players[0].deck[1:]


def test_dr_yueh_reveals_one_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "dr_yueh", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 0


# --- Duncan Idaho -----------------------------------------------------------------


def _duncan_placed(
    engine: UprisingRulesEngine, state: GameState, water: int = 3
) -> GameState:
    """Seat 0 sends Duncan Idaho to Research Station (a City space; its two
    water are paid) holding ``water`` water."""

    held, _ = _with_card(state, "duncan_idaho_card")
    seated = _seat(held, resources=Resources(water=water))
    return _place(engine, seated, "imperium_research_station", "duncan_idaho_card")


def test_duncan_idaho_matches_the_app_table() -> None:
    # App attribute table: cost 4, 1 copy, no Faction, City, Reveal 2 swords
    # and 1 water (the app's 2 swords: the Dune Cards Hub scan's 3 is the known
    # bad scan, P0 sweep) and no Persuasion.
    entry = IMPERIUM_CARDS_BY_ID["duncan_idaho_card"]
    assert entry.card.name == "Duncan Idaho"
    assert entry.acquisition_cost == 4
    assert entry.copies == 1
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_PAY_ONE_WATER_FOR_TROOP_AND_DRAW_ONE
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 2)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:duncan_idaho_card:0") is entry


def test_duncan_idaho_pays_one_water_for_a_troop_and_a_card() -> None:
    """"An arrow cost is optional [DI p. 9] and paid once [FAQ p. 3]" (P0 sweep:
    "may pay 1 water (arrow) -> recruit 1 troop and draw 1"): one water buys
    the troop and the card."""

    engine, state = _start()
    placed = _duncan_placed(engine, state)
    before = placed.players[0]
    assert "pay_agent_card_water" in _ids(engine, placed)
    paid = _do(engine, placed, "pay_agent_card_water")
    assert paid.players[0].resources.water == before.resources.water - 1
    # Both rewards still wait: the arrow pays only its cost at once.
    assert paid.players[0].troops_garrison == before.troops_garrison
    assert paid.players[0].hand == before.hand
    recruited = _do(engine, paid, "resolve_agent_card_effect", effect="troops")
    assert recruited.players[0].troops_garrison == before.troops_garrison + 1
    assert recruited.players[0].troops_supply == before.troops_supply - 1
    drawn = _do(engine, recruited, "resolve_agent_card_effect", effect="cards")
    assert drawn.players[0].hand == (*before.hand, before.deck[0])


def test_duncan_idaho_troop_and_draw_are_separate_steps_in_any_order() -> None:
    """"Troop and draw are separate steps (OQ-027 (b), OQ-106)" (P0 sweep): a
    hidden draw is never bundled with the public choice, so the owner may draw
    first (to trash a discard card beforehand), and the turn cannot end while
    either waits."""

    engine, state = _start()
    paid = _do(engine, _duncan_placed(engine, state), "pay_agent_card_water")
    effects = {
        dict(action.arguments)["effect"]
        for action in _wholes(engine, paid)
        if action.action_id == "resolve_agent_card_effect"
    }
    assert effects == {"troops", "cards"}
    drawn_first = _do(engine, paid, "resolve_agent_card_effect", effect="cards")
    assert drawn_first.players[0].troops_garrison == paid.players[0].troops_garrison
    assert "finish_agent_turn" not in _ids(engine, drawn_first)
    done = _do(engine, drawn_first, "resolve_agent_card_effect", effect="troops")
    assert done.players[0].troops_garrison == paid.players[0].troops_garrison + 1


def test_duncan_idaho_arrow_is_paid_once() -> None:
    engine, state = _start()
    placed = _duncan_placed(engine, state, water=6)
    paid = _do(engine, placed, "pay_agent_card_water")
    assert paid.players[0].resources.water == 3
    assert "pay_agent_card_water" not in _ids(engine, paid)


def test_duncan_idaho_arrow_is_optional() -> None:
    """The arrow cost is optional [DI p. 9]: the owner who does not pay keeps
    the water and gets neither the troop nor the card."""

    engine, state = _start()
    placed = _duncan_placed(engine, state)
    before = placed.players[0]
    resolved = _do(engine, placed, "resolve_board_effect", effect="cards")
    assert "pay_agent_card_water" in _ids(engine, resolved)
    finished = _do(engine, resolved, "finish_agent_turn")
    after = finished.players[0]
    assert after.resources.water == before.resources.water
    assert after.troops_garrison == before.troops_garrison
    # The card's draw was never bought: the finish drew nothing.
    assert after.hand == resolved.players[0].hand


def test_duncan_idaho_needs_one_water_to_pay() -> None:
    engine, state = _start()
    # Research Station takes its two water first: none is left to pay with.
    assert "pay_agent_card_water" not in _ids(
        engine, _duncan_placed(engine, state, water=2)
    )
    exact = _duncan_placed(engine, state, water=3)
    assert _do(engine, exact, "pay_agent_card_water").players[0].resources.water == 0


def test_duncan_idaho_reveals_one_water_and_two_swords() -> None:
    """Reveal: "1 water" is a gain line and the swords count once a troop
    stands in the Conflict ("Conflict에 troop이 하나도 없으면 0" [DI p. 11])."""

    engine, state = _start()
    state, _ = _with_card(state, "duncan_idaho_card", alone=True)
    state = _with_troops(state, 0, garrison=0, conflict=1)
    water = state.players[0].resources.water
    revealed = _do(engine, state, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (0, 2)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert gained.players[0].resources.water == water + 1
    finished = _do(engine, gained, "finish_reveal")
    assert finished.players[0].combat_strength == 2 + 2


# --- Fedaykin Death Commando ------------------------------------------------------


def test_fedaykin_death_commando_matches_the_app_table() -> None:
    # App attribute table: cost 3, 2 copies, Fremen, City and Spice Trade,
    # Reveal 1 Persuasion and no fixed swords (tags FremenBond,
    # ConditionalStrength).
    entry = IMPERIUM_CARDS_BY_ID["fedaykin_death_commando"]
    assert entry.card.name == "Fedaykin Death Commando"
    assert entry.acquisition_cost == 3
    assert entry.copies == 2
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is PersonalCardAgentEffect.TRASH_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:fedaykin_death_commando:1") is entry


def _commando_placed(engine: UprisingRulesEngine, state: GameState) -> GameState:
    held, _ = _with_card(state, "fedaykin_death_commando")
    seated = _seat(held, resources=Resources(water=2))
    return _place(
        engine, seated, "imperium_research_station", "fedaykin_death_commando"
    )


def _trash_rows(engine: UprisingRulesEngine, state: GameState) -> set[object]:
    return {
        dict(action.arguments)["card_id"]
        for action in _wholes(engine, state)
        if action.action_id == "trash_agent_card"
    }


def test_fedaykin_death_commando_may_trash_a_card_of_the_hand() -> None:
    """"Trash(...비용이거나 카드가 자기를 trash하라고 할 때만 의무)" (imperium-base.md
    11, [DI p. 16]): the black trash icon is optional. Its rows are the hand's
    cards and the card itself in play."""

    engine, state = _start()
    placed = _commando_placed(engine, state)
    owner = placed.players[0]
    rows = _trash_rows(engine, placed)
    assert rows == {*owner.hand, "imperium:fedaykin_death_commando:0"}
    victim = owner.hand[0]
    trashed = _do(engine, placed, "trash_agent_card", card_id=victim)
    after = trashed.players[0]
    assert victim not in after.hand
    assert victim in after.trashed
    assert "imperium:fedaykin_death_commando:0" in after.in_play
    assert not _trash_rows(engine, trashed)


def test_fedaykin_death_commando_may_trash_itself() -> None:
    """The card may trash itself: it is the box's own icon, so nothing else of
    its box is lost (imperium-base.md 16, OQ-022's own-effect case; OQ-027)."""

    engine, state = _start()
    placed = _commando_placed(engine, state)
    me = "imperium:fedaykin_death_commando:0"
    trashed = _do(engine, placed, "trash_agent_card", card_id=me)
    after = trashed.players[0]
    assert me in after.trashed
    assert me not in after.in_play
    assert not _trash_rows(engine, trashed)


def test_fedaykin_death_commando_trash_is_optional() -> None:
    engine, state = _start()
    placed = _commando_placed(engine, state)
    before = placed.players[0]
    resolved = _do(engine, placed, "resolve_board_effect", effect="cards")
    assert _trash_rows(engine, resolved)
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].trashed == before.trashed


def _commando_revealed(
    engine: UprisingRulesEngine, state: GameState, *others: str
) -> GameState:
    """Seat 0 reveals Fedaykin Death Commando with the other cards, one troop
    already in the Conflict."""

    held, instance = _with_card(state, "fedaykin_death_commando", alone=True)
    held = _seat(held, hand=(instance, *others))
    held = _with_troops(held, 0, garrison=0, conflict=1)
    return _do(engine, held, "reveal_turn")


def test_fedaykin_death_commando_reveals_one_persuasion_and_no_bond_swords() -> None:
    engine, state = _start()
    # A starter card has no Faction, so it makes no Bond; its own Reveal
    # values add to the card's.
    starter = state.players[0].hand[0]
    other = personal_card_for_instance(starter)
    for others, persuasion, swords in (
        ((), 1, 0),
        ((starter,), 1 + other.reveal_persuasion, other.reveal_strength),
    ):
        revealed = _commando_revealed(engine, state, *others)
        frame = dict(revealed.decision_stack[-1].context)
        assert (frame["persuasion"], frame["sword_strength"]) == (persuasion, swords)
        # No Bond: only the troop in the Conflict and the other card's swords.
        finished = _do(engine, revealed, "finish_reveal")
        assert finished.players[0].combat_strength == 2 + swords


def test_fedaykin_death_commando_fremen_bond_gives_three_swords() -> None:
    """"Fremen Bond = another Fremen card in play" [DI p. 16] (imperium-base.md
    11), judged when the line resolves (OQ-028): with Fedaykin Stilltent also
    revealed the card's 3 swords join the troop's 2."""

    engine, state = _start()
    revealed = _commando_revealed(engine, state, "imperium:fedaykin_stilltent:0")
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (1, 3)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert _do(engine, gained, "finish_reveal").players[0].combat_strength == 2 + 3


# --- Fremen Camp ------------------------------------------------------------------


def _camp_placed(
    engine: UprisingRulesEngine, state: GameState, spice: int = 3
) -> GameState:
    """Seat 0 sends Fremen Camp to Secure Contract (a Spice Trade space)
    holding ``spice`` spice."""

    held, _ = _with_card(state, "fremen_camp")
    seated = _seat(held, resources=Resources(spice=spice))
    return _place(engine, seated, "secure_contract", "fremen_camp")


def test_fremen_camp_matches_the_app_table() -> None:
    # App attribute table: cost 4, 2 copies, Fremen, Spice Trade, Reveal 2
    # Persuasion and 1 sword.
    entry = IMPERIUM_CARDS_BY_ID["fremen_camp"]
    assert entry.card.name == "Fremen Camp"
    assert entry.acquisition_cost == 4
    assert entry.copies == 2
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_PAY_TWO_SPICE_FOR_THREE_TROOPS
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 1)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:fremen_camp:1") is entry


def test_fremen_camp_pays_two_spice_for_three_troops() -> None:
    """"비용 화살표" [DI p. 16]: the arrow's cost is paid for its reward; two
    spice buy 3 troops, recruited into the garrison."""

    engine, state = _start()
    placed = _camp_placed(engine, state)
    before = placed.players[0]
    assert "pay_agent_card_spice" in _ids(engine, placed)
    paid = _do(engine, placed, "pay_agent_card_spice")
    after = paid.players[0]
    assert after.resources.spice == before.resources.spice - 2
    assert after.troops_garrison == before.troops_garrison + 3
    assert after.troops_supply == before.troops_supply - 3


def test_fremen_camp_arrow_is_paid_once() -> None:
    """"An arrow cost is optional [DI p. 9] and paid once [FAQ p. 3]": with
    spice for a second payment the arrow is no longer offered."""

    engine, state = _start()
    placed = _camp_placed(engine, state, spice=6)
    paid = _do(engine, placed, "pay_agent_card_spice")
    assert paid.players[0].resources.spice == 4
    assert "pay_agent_card_spice" not in _ids(engine, paid)


def test_fremen_camp_arrow_is_optional() -> None:
    engine, state = _start()
    placed = _camp_placed(engine, state)
    before = placed.players[0]
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    assert "pay_agent_card_spice" in _ids(engine, resolved)
    after = _do(engine, resolved, "finish_agent_turn").players[0]
    assert after.troops_garrison == before.troops_garrison
    assert after.resources.spice == before.resources.spice


def test_fremen_camp_needs_two_spice_to_pay() -> None:
    engine, state = _start()
    assert "pay_agent_card_spice" not in _ids(engine, _camp_placed(engine, state, 1))
    exact = _camp_placed(engine, state, 2)
    assert _do(engine, exact, "pay_agent_card_spice").players[0].resources.spice == 0


def test_fremen_camp_reveals_two_persuasion_and_one_sword() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "fremen_camp", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 2
    assert frame["sword_strength"] == 1


# --- Guild Administrator ----------------------------------------------------------


def test_guild_administrator_matches_the_app_table() -> None:
    # App attribute table: cost 2, 2 copies, Spacing Guild, Spacing Guild and
    # Spice Trade, Reveal 1 Persuasion and no swords.
    entry = IMPERIUM_CARDS_BY_ID["guild_administrator"]
    assert entry.card.name == "Guild Administrator"
    assert entry.acquisition_cost == 2
    assert entry.copies == 2
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is PersonalCardAgentEffect.TRASH_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:guild_administrator:1") is entry


def _administrator_placed(engine: UprisingRulesEngine, state: GameState) -> GameState:
    held, _ = _with_card(state, "guild_administrator")
    return _place(engine, held, "secure_contract", "guild_administrator")


def test_guild_administrator_may_trash_a_card() -> None:
    """"Trash(...비용이거나 카드가 자기를 trash하라고 할 때만 의무)" (imperium-base.md
    11, [DI p. 16]): the black trash icon is optional ([FAQ p. 3]); its rows
    are the hand's cards and the card itself in play."""

    engine, state = _start()
    placed = _administrator_placed(engine, state)
    owner = placed.players[0]
    me = "imperium:guild_administrator:0"
    assert _trash_rows(engine, placed) == {*owner.hand, me}
    victim = owner.hand[0]
    trashed = _do(engine, placed, "trash_agent_card", card_id=victim)
    assert victim in trashed.players[0].trashed
    assert victim not in trashed.players[0].hand
    assert not _trash_rows(engine, trashed)


def test_guild_administrator_may_trash_itself() -> None:
    engine, state = _start()
    placed = _administrator_placed(engine, state)
    me = "imperium:guild_administrator:0"
    trashed = _do(engine, placed, "trash_agent_card", card_id=me)
    assert me in trashed.players[0].trashed
    assert me not in trashed.players[0].in_play


def test_guild_administrator_trash_is_optional() -> None:
    engine, state = _start()
    placed = _administrator_placed(engine, state)
    before = placed.players[0]
    assert _trash_rows(engine, placed)
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].trashed == before.trashed


def test_guild_administrator_reveals_one_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "guild_administrator", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 0


# --- Piter De Vries ---------------------------------------------------------------


def _piter_placed(
    engine: UprisingRulesEngine,
    state: GameState,
    intrigue_deck: tuple[str, ...] = ("intrigue:bribery:0", "intrigue:bribery:1"),
) -> GameState:
    """Seat 0 sends Piter De Vries to Research Station (a City space; its two
    water are paid) with the given Intrigue deck."""

    held, _ = _with_card(state, "piter_de_vries_card")
    seated = replace(
        _seat(held, resources=Resources(water=2)), intrigue_deck=intrigue_deck
    )
    return _place(engine, seated, "imperium_research_station", "piter_de_vries_card")


def test_piter_de_vries_matches_the_app_table() -> None:
    # App attribute table: cost 5, 1 copy, no Faction, Landsraad and City,
    # Reveal 3 Persuasion and 1 sword.
    entry = IMPERIUM_CARDS_BY_ID["piter_de_vries_card"]
    assert entry.card.name == "Piter De Vries"
    assert entry.acquisition_cost == 5
    assert entry.copies == 1
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.CITY)
    assert entry.agent_effect is PersonalCardAgentEffect.DRAW_INTRIGUE_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (3, 1)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:piter_de_vries_card:0") is entry


def test_piter_de_vries_draws_one_intrigue_card() -> None:
    """P0 sweep: "AGENT: draw 1 Intrigue"; the icon is mandatory ("everything
    else mandatory" [FAQ p. 3]) and a hidden draw is its own step (OQ-106):
    the owner takes the Intrigue deck's top card, the rest stays."""

    engine, state = _start()
    placed = _piter_placed(engine, state)
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].intrigue_cards == (
        *placed.players[0].intrigue_cards,
        "intrigue:bribery:0",
    )
    assert resolved.intrigue_deck == ("intrigue:bribery:1",)
    # The card's own box is done: no second draw is offered.
    assert "resolve_agent_card_effect" not in _ids(engine, resolved)


def test_piter_de_vries_with_no_intrigue_card_left_draws_nothing() -> None:
    """With the Intrigue deck and its discard pile both empty there is nothing
    to draw: the box still resolves and the owner's hand is unchanged (the
    engine's Intrigue draw, shared with every Uprising Intrigue-draw box)."""

    engine, state = _start()
    placed = _piter_placed(engine, state, intrigue_deck=())
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].intrigue_cards == placed.players[0].intrigue_cards
    assert resolved.intrigue_deck == ()


def test_piter_de_vries_reveals_three_persuasion_and_one_sword() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "piter_de_vries_card", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 3
    assert frame["sword_strength"] == 1


# --- Opulence ---------------------------------------------------------------------


def test_opulence_matches_the_app_table() -> None:
    # App attribute table: cost 6, 1 copy, Emperor, Emperor, Reveal 1
    # Persuasion and no swords; AgentSolari 3.
    entry = IMPERIUM_CARDS_BY_ID["opulence"]
    assert entry.card.name == "Opulence"
    assert entry.acquisition_cost == 6
    assert entry.copies == 1
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == (AgentIcon.EMPEROR,)
    assert entry.agent_effect is PersonalCardAgentEffect.GAIN_THREE_SOLARI
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_PAY_SIX_SOLARI_FOR_VICTORY_POINT,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:opulence:0") is entry


def test_opulence_agent_box_gains_three_solari() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "opulence")
    state = _seat(state, resources=Resources())
    placed = _place(engine, state, "wealth", "opulence")
    before = placed.players[0].resources
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].resources.solari == before.solari + 3


def _opulence_revealed(
    engine: UprisingRulesEngine, state: GameState, solari: int, *others: str
) -> GameState:
    """Seat 0 reveals Opulence (and the other cards) holding ``solari``."""

    held, instance = _with_card(state, "opulence", alone=True)
    held = _seat(
        held, hand=(instance, *others), resources=Resources(solari=solari)
    )
    return _do(engine, held, "reveal_turn")


def test_opulence_reveals_one_persuasion() -> None:
    engine, state = _start()
    frame = dict(_opulence_revealed(engine, state, 0).decision_stack[-1].context)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 0


def test_opulence_pays_six_solari_for_one_victory_point() -> None:
    """"비용 화살표" [DI p. 16] (imperium-base.md 11): the arrow's cost is paid
    for its reward; six Solari buy one Victory Point, once (the choice is used
    up)."""

    engine, state = _start()
    revealed = _opulence_revealed(engine, state, 6)
    before = revealed.players[0]
    assert "pay_reveal_solari_for_vp" in _ids(engine, revealed)
    paid = _do(engine, revealed, "pay_reveal_solari_for_vp")
    after = paid.players[0]
    assert after.resources.solari == before.resources.solari - 6
    assert after.victory_points == before.victory_points + 1
    assert "pay_reveal_solari_for_vp" not in _ids(engine, paid)


def test_opulence_arrow_is_optional() -> None:
    """The arrow cost is optional [DI p. 9] ("You do not have to pay such a
    cost on a card" [Main p. 20]): the Reveal ends with no refusal needed."""

    engine, state = _start()
    revealed = _opulence_revealed(engine, state, 9)
    before = revealed.players[0]
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].resources.solari == 9
    assert finished.players[0].victory_points == before.victory_points


def test_opulence_needs_six_solari_to_pay() -> None:
    engine, state = _start()
    revealed = _opulence_revealed(engine, state, 5)
    assert "pay_reveal_solari_for_vp" not in _ids(engine, revealed)
    assert _do(engine, revealed, "finish_reveal").players[0].victory_points == (
        revealed.players[0].victory_points
    )


def test_opulence_payment_opens_once_a_later_gain_makes_six_solari() -> None:
    """Reveal effects resolve in any order ([Main p. 12]; OQ-028: judged when
    asked): Price is No Object's 2 Solari bring 4 to the 6 the arrow costs."""

    engine, state = _start()
    revealed = _opulence_revealed(engine, state, 4, "imperium:price_is_no_object:0")
    assert "pay_reveal_solari_for_vp" not in _ids(engine, revealed)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert gained.players[0].resources.solari == 6
    paid = _do(engine, gained, "pay_reveal_solari_for_vp")
    assert paid.players[0].resources.solari == 0
    assert paid.players[0].victory_points == revealed.players[0].victory_points + 1


# --- CHOAM Directorship -----------------------------------------------------------

_CHOAM = "imperium:choam_directorship:0"
_CHOAM_ICONS = (
    "influence_emperor",
    "influence_spacing_guild",
    "influence_bene_gesserit",
    "influence_fremen",
)


def _buyer_revealed(
    engine: UprisingRulesEngine,
    state: GameState,
    card_id: str,
    *,
    persuasion: int = 20,
    influence: Influence | None = None,
) -> GameState:
    """Seat 0 mid-Reveal with ``persuasion`` to spend and the Imperium card
    ``card_id`` first in the Row."""

    held, _ = _with_card(state, "dr_yueh", alone=True)
    if influence is not None:
        held = _seat(held, influence=influence)
    instance = f"imperium:{card_id}:0"
    others = tuple(card for card in held.imperium_row if card != instance)
    held = replace(
        held,
        imperium_row=(instance, *others[:4]),
        imperium_deck=tuple(
            card for card in held.imperium_deck if card != instance
        ),
    )
    revealed = _do(engine, held, "reveal_turn")
    frame = revealed.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = persuasion
    frame = replace(frame, context=tuple(sorted(context.items())))
    return replace(revealed, decision_stack=(*revealed.decision_stack[:-1], frame))


def _acquire_rows(
    engine: UprisingRulesEngine, state: GameState
) -> tuple[DomainAction, ...]:
    return tuple(
        action
        for action in _wholes(engine, state)
        if action.action_id == "resolve_acquire_icon"
    )


def _take_icon(
    engine: UprisingRulesEngine, state: GameState, effect: str, **arguments: object
) -> GameState:
    return _do(engine, state, "resolve_acquire_icon", effect=effect, **arguments)


def test_choam_directorship_matches_the_app_table() -> None:
    # App attribute table: cost 8, 1 copy, no Faction, no Agent icons and no
    # fixed Reveal values (its Reveal is the "3 Solari" gain line); acquire
    # box: Influence with each of the four Factions (AcquireEffectList RankE,
    # RankSG, RankBG, RankF).
    entry = IMPERIUM_CARDS_BY_ID["choam_directorship"]
    assert entry.card.name == "CHOAM Directorship"
    assert entry.acquisition_cost == 8
    assert entry.copies == 1
    assert entry.factions == ()
    assert entry.agent_icons == ()
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.has_acquisition_bonus and entry.play_data_complete
    assert entry.acquisition_effect is (
        PersonalCardAcquisitionEffect.GAIN_INFLUENCE_WITH_EACH_FACTION
    )
    assert personal_card_for_instance("imperium:choam_directorship:0") is entry
    # Four separate icons, one row each (OQ-141); the original deck holds it.
    assert acquire_box_icons(entry) == _CHOAM_ICONS
    assert _CHOAM in content_for(CONFIG).imperium_deck_instance_ids


def test_choam_directorship_reveals_three_solari() -> None:
    """Reveal: "3 Solari" (P0 sweep); with no Agent icon the card is Reveal
    only [DI p. 9]."""

    engine, state = _start()
    held, _ = _with_card(state, "choam_directorship", alone=True)
    solari = held.players[0].resources.solari
    assert not any(
        action.action_id == "agent_turn" or action.action_id == "place_agent"
        for action in _wholes(engine, held)
    )
    revealed = _do(engine, held, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (0, 0)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert gained.players[0].resources.solari == solari + 3


def test_choam_directorship_bought_in_a_reveal_gives_four_rows_in_any_order() -> None:
    """"The acquisition bonus is paid once, when acquired" [DI p. 16]; its four
    printed icons are independent effects whose order the owner picks
    (OQ-141, the principle of OQ-027 and OQ-112). They are rows of the Reveal
    turn and hold its end until each is taken."""

    engine, state = _start()
    revealed = _buyer_revealed(engine, state, "choam_directorship")
    before = revealed.players[0]
    bought = _do(engine, revealed, "acquire_imperium", instance_id=_CHOAM)
    # The purchase gains nothing at once; the card is in the discard pile.
    assert bought.players[0].discard_pile[-1] == "imperium:choam_directorship:0"
    assert bought.players[0].influence == before.influence
    rows = _acquire_rows(engine, bought)
    assert {dict(row.arguments)["effect"] for row in rows} == set(_CHOAM_ICONS)
    assert {dict(row.arguments)["acquired_card_id"] for row in rows} == {
        "choam_directorship"
    }
    assert "finish_reveal" not in _ids(engine, bought)
    # The owner's order, not the printed one: Fremen, then the Emperor, ...
    state_now = bought
    expected = before.influence
    for effect, field in (
        ("influence_fremen", "fremen"),
        ("influence_emperor", "emperor"),
        ("influence_bene_gesserit", "bene_gesserit"),
    ):
        state_now = _take_icon(engine, state_now, effect)
        expected = replace(expected, **{field: getattr(expected, field) + 1})
        assert state_now.players[0].influence == expected
        assert "finish_reveal" not in _ids(engine, state_now)
    left = _acquire_rows(engine, state_now)
    assert [dict(row.arguments)["effect"] for row in left] == [
        "influence_spacing_guild"
    ]
    state_now = _take_icon(engine, state_now, "influence_spacing_guild")
    assert _acquire_rows(engine, state_now) == ()
    assert state_now.players[0].influence == Influence(
        emperor=before.influence.emperor + 1,
        spacing_guild=before.influence.spacing_guild + 1,
        bene_gesserit=before.influence.bene_gesserit + 1,
        fremen=before.influence.fremen + 1,
    )
    assert "finish_reveal" in _ids(engine, state_now)


def test_choam_directorship_icons_wait_beside_other_acquisitions() -> None:
    """The rows are the turn's, not a window: the Reveal still offers its other
    purchases beside them."""

    engine, state = _start()
    revealed = _buyer_revealed(engine, state, "choam_directorship")
    bought = _do(engine, revealed, "acquire_imperium", instance_id=_CHOAM)
    assert bought.decision_stack[-1].kind == FrameKind.REVEAL
    assert {"acquire_imperium", "resolve_acquire_icon"} <= _ids(engine, bought)


def test_choam_directorship_bought_in_an_agent_turn_waits_on_the_turn() -> None:
    """The same rows when an Agent turn took the card (Price is No Object:
    "acquire a card for Solari to hand"): beside the turn's other effects,
    holding its end."""

    engine, state = _start()
    state, _ = _with_card(state, "price_is_no_object", alone=True)
    state = _seat(state, resources=Resources(solari=20))
    instance = _CHOAM
    others = tuple(card for card in state.imperium_row if card != instance)
    state = replace(
        state,
        imperium_row=(instance, *others[:4]),
        imperium_deck=tuple(card for card in state.imperium_deck if card != instance),
    )
    placed = _place(engine, state, "wealth", "price_is_no_object")
    before = placed.players[0].influence
    bought = _do(engine, placed, "acquire_imperium_with_solari", instance_id=instance)
    assert bought.players[0].hand == (instance,)
    assert bought.players[0].influence == before
    assert bought.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    rows = _acquire_rows(engine, bought)
    assert {dict(row.arguments)["effect"] for row in rows} == set(_CHOAM_ICONS)
    # The turn's own effect is still offered beside the rows, and the turn
    # cannot end until every icon is taken.
    assert "resolve_board_effect" in _ids(engine, bought)
    taken = bought
    for effect in reversed(_CHOAM_ICONS):
        assert "finish_agent_turn" not in _ids(engine, taken)
        taken = _take_icon(engine, taken, effect)
    assert taken.players[0].influence == Influence(
        emperor=before.emperor + 1,
        spacing_guild=before.spacing_guild + 1,
        bene_gesserit=before.bene_gesserit + 1,
        fremen=before.fremen + 1,
    )
    resolved = _do(engine, taken, "resolve_board_effect")
    resolved = _do(engine, resolved, "resolve_faction_influence")
    assert "finish_agent_turn" in _ids(engine, resolved)


def test_choam_directorship_track_at_six_gains_nothing() -> None:
    """A Faction already at 6 gains nothing (OQ-060: "엔진은 6에 있는 cube에
    대한 Influence 획득을 버린다"): its icon is still a row, taking it changes
    nothing, and the other three icons are paid."""

    engine, state = _start()
    revealed = _buyer_revealed(
        engine,
        state,
        "choam_directorship",
        influence=Influence(emperor=6, fremen=1),
    )
    bought = _do(engine, revealed, "acquire_imperium", instance_id=_CHOAM)
    assert "influence_emperor" in {
        dict(row.arguments)["effect"] for row in _acquire_rows(engine, bought)
    }
    taken = bought
    for effect in _CHOAM_ICONS:
        taken = _take_icon(engine, taken, effect)
    assert taken.players[0].influence == Influence(
        emperor=6, spacing_guild=1, bene_gesserit=1, fremen=2
    )
    assert "finish_reveal" in _ids(engine, taken)


def test_an_uprising_one_icon_acquire_box_is_still_paid_at_once() -> None:
    """A box of one icon with nothing to choose resolves at once, exactly as
    before OQ-141 (Steersman: one Spacing Guild Influence): no row waits."""

    engine, state = _start()
    revealed = _buyer_revealed(engine, state, "steersman")
    before = revealed.players[0].influence
    bought = _do(
        engine, revealed, "acquire_imperium", instance_id="imperium:steersman:0"
    )
    assert bought.players[0].influence == replace(
        before, spacing_guild=before.spacing_guild + 1
    )
    assert _acquire_rows(engine, bought) == ()
    assert "finish_reveal" in _ids(engine, bought)


def test_choam_directorship_rows_come_from_every_acquisition_path() -> None:
    """Every path that pays an acquire box routes the four icons to rows: the
    Manipulate set-aside card bought in a Reveal and an Intrigue effect's
    acquisition inside an Agent turn; outside its owner's turn the rows have
    nowhere to wait and the acquisition refuses (OQ-141: no window yet)."""

    engine, state = _start()
    instance = _CHOAM
    drawn_off = replace(
        state, imperium_deck=tuple(c for c in state.imperium_deck if c != instance)
    )
    revealed = _buyer_revealed(engine, drawn_off, "dr_yueh")
    revealed = _seat(revealed, imperium_set_aside=(instance,))
    manipulated = _do(
        engine, revealed, "acquire_manipulated_imperium", instance_id=instance
    )
    assert len(_acquire_rows(engine, manipulated)) == 4

    held, _ = _with_card(drawn_off, "dr_yueh", alone=True)
    others = tuple(card for card in held.imperium_row if card != instance)
    held = replace(held, imperium_row=(instance, *others[:4]))
    space = str(dict(executable_placements(held, 0)[0].arguments)["space_id"])
    placed = _place(engine, held, space, "dr_yueh")
    acquired = acquire_imperium_for_intrigue(
        placed, 0, instance, to_hand=False, source="test"
    )
    assert len(_acquire_rows(engine, acquired.result.state)) == 4
    with pytest.raises(NotImplementedError, match="outside its owner's turn"):
        acquire_imperium_for_intrigue(
            replace(held, decision_stack=()), 0, instance, to_hand=False, source="test"
        )


# --- Lady Jessica -----------------------------------------------------------------

_JESSICA = "imperium:lady_jessica_card:0"


def _jessica_bought(
    engine: UprisingRulesEngine, state: GameState, influence: Influence
) -> GameState:
    """Seat 0 buys Lady Jessica in its Reveal holding ``influence``."""

    revealed = _buyer_revealed(
        engine, state, "lady_jessica_card", influence=influence
    )
    return _do(engine, revealed, "acquire_imperium", instance_id=_JESSICA)


def test_lady_jessica_matches_the_app_table() -> None:
    # App attribute table: cost 7, 1 copy, Bene Gesserit, Bene Gesserit,
    # Landsraad, City and Spice Trade, Reveal 3 Persuasion and 1 sword;
    # AcquireEffectList AnyRank (Influence with a Faction of the owner's
    # choice), abilities DrawAbility x2.
    entry = IMPERIUM_CARDS_BY_ID["lady_jessica_card"]
    assert entry.card.name == "Lady Jessica"
    assert entry.acquisition_cost == 7
    assert entry.copies == 1
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (
        AgentIcon.BENE_GESSERIT,
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is PersonalCardAgentEffect.DRAW_TWO_CARDS
    assert entry.acquisition_effect is (
        PersonalCardAcquisitionEffect.GAIN_INFLUENCE_WITH_CHOSEN_FACTION
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (3, 1)
    assert entry.has_acquisition_bonus and entry.play_data_complete
    assert personal_card_for_instance(_JESSICA) is entry
    assert acquire_box_icons(entry) == ("influence_any",)
    assert _JESSICA in content_for(CONFIG).imperium_deck_instance_ids


def test_lady_jessica_draws_two_cards_in_one_step() -> None:
    """Agent: "draw 2" (P0 sweep S30: the card-draw icon printed twice, a hidden
    draw that is its own step, OQ-106): one resolution takes the deck's top two
    cards."""

    engine, state = _start()
    state, _ = _with_card(state, "lady_jessica_card")
    owner = state.players[0]
    top = owner.deck[:2]
    space = next(
        str(dict(placement.arguments)["space_id"])
        for placement in executable_placements(state, 0)
        if ":lady_jessica_card:" in str(dict(placement.arguments)["card_id"])
    )
    placed = _place(engine, state, space, "lady_jessica_card")
    assert "resolve_agent_card_effect" in _ids(engine, placed)
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    after = resolved.players[0]
    assert after.hand == (*placed.players[0].hand, *top)
    assert after.deck == owner.deck[2:]


def test_lady_jessica_reveals_three_persuasion_and_one_sword() -> None:
    engine, state = _start()
    held, _ = _with_card(state, "lady_jessica_card", alone=True)
    held = _with_troops(held, 0, garrison=0, conflict=1)
    revealed = _do(engine, held, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (3, 1)


def test_lady_jessica_acquire_row_offers_every_faction_below_six() -> None:
    """Acquire: "+1 Influence, any Faction" -- one icon with a choice, so a row
    of the Reveal turn (OQ-141) that names the Faction; a Faction at 6 is not
    offered (OQ-060: "고를 수 있는 진영이 하나도 없을 때 ..." / imperium-base.md
    16). It holds the Reveal's end until taken."""

    engine, state = _start()
    bought = _jessica_bought(
        engine, state, Influence(emperor=6, fremen=6, bene_gesserit=2)
    )
    rows = _acquire_rows(engine, bought)
    assert {dict(row.arguments)["faction"] for row in rows} == {
        "spacing_guild",
        "bene_gesserit",
    }
    assert {dict(row.arguments)["acquired_card_id"] for row in rows} == {
        "lady_jessica_card"
    }
    assert "finish_reveal" not in _ids(engine, bought)
    # The Reveal still offers its other purchases beside the row.
    assert "acquire_imperium" in _ids(engine, bought)
    before = bought.players[0].influence
    taken = _take_icon(engine, bought, "influence_any", faction="spacing_guild")
    assert taken.players[0].influence == replace(
        before, spacing_guild=before.spacing_guild + 1
    )
    assert _acquire_rows(engine, taken) == ()
    assert "finish_reveal" in _ids(engine, taken)


def test_lady_jessica_acquire_waits_and_lapses_with_every_faction_at_six() -> None:
    """With every cube at the top the icon offers no row: it waits beside the
    turn greyed out (OQ-060), holds nothing back, and the press lapses it with
    an event, as every in-turn "Influence with any Faction" does."""

    engine, state = _start()
    bought = _jessica_bought(
        engine,
        state,
        Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
    )
    assert _acquire_rows(engine, bought) == ()
    assert "finish_reveal" in _ids(engine, bought)
    found = unavailable_choices(bought, 0, _wholes(engine, bought))
    assert found is not None
    waiting = [
        row
        for row in found["rows"]  # type: ignore[attr-defined]
        if str(row["key"]).startswith("waiting:acquire_icon:")
    ]
    assert len(waiting) == 1
    pressed = apply_whole(engine, bought, _do_action(engine, bought, "finish_reveal"))
    assert "acquire_icon_lapsed" in {event.kind for event in pressed.events}
    assert pressed.state.players[0].influence == bought.players[0].influence


def _do_action(
    engine: UprisingRulesEngine, state: GameState, action_id: str
) -> DomainAction:
    return next(a for a in _wholes(engine, state) if a.action_id == action_id)


def test_lady_jessica_and_choam_directorship_icons_share_a_turn() -> None:
    """Two acquire boxes in one Reveal turn (15 Persuasion): CHOAM's four fixed
    icons and Jessica's chosen one are five rows of the turn; a fixed Emperor
    icon and a chosen Emperor row are different rows, so each is taken on its
    own."""

    engine, state = _start()
    revealed = _buyer_revealed(engine, state, "choam_directorship")
    jessica = _JESSICA
    others = tuple(c for c in revealed.imperium_row if c != jessica)
    revealed = replace(
        revealed,
        imperium_row=(*revealed.imperium_row[:1], jessica, *others[1:4]),
        imperium_deck=tuple(c for c in revealed.imperium_deck if c != jessica),
    )
    bought = _do(engine, revealed, "acquire_imperium", instance_id=_CHOAM)
    bought = _do(engine, bought, "acquire_imperium", instance_id=jessica)
    rows = _acquire_rows(engine, bought)
    assert len([r for r in rows if "faction" not in dict(r.arguments)]) == 4
    assert len([r for r in rows if "faction" in dict(r.arguments)]) == 4
    before = bought.players[0].influence
    # Emperor via the chosen icon leaves CHOAM's own Emperor icon waiting.
    chosen = _take_icon(engine, bought, "influence_any", faction="emperor")
    assert chosen.players[0].influence.emperor == before.emperor + 1
    assert "influence_emperor" in {
        dict(row.arguments)["effect"] for row in _acquire_rows(engine, chosen)
    }
    assert "finish_reveal" not in _ids(engine, chosen)

