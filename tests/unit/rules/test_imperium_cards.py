"""The original Dune: Imperium's Imperium cards (stage P3, trial transcription).

docs/rules/imperium-base.md 7, 11, 13.2 and docs/base-game-and-ix-plan.md 16.
The cards are not in the original game's deck yet (plan 16.1), so each test
puts the card instance into seat 0's hand of an original-game round; the
printed values are the Steam app's attribute table (plan 2.4, D1).
"""

from dataclasses import replace
from typing import Any, cast

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
    PersonalCardTrashEffect,
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
from dune_imperium.core.engine import RuleResult
from dune_imperium.display.tokens import REVEAL_CHOICE_EFFECT_TEXT, reveal_effect_text
from dune_imperium.display.tokens_ko import (
    REVEAL_CHOICE_EFFECT_TEXT_KO,
    reveal_effect_text_ko,
)
from dune_imperium.display.unavailable import unavailable_choices
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquire_icons import acquire_box_icons
from dune_imperium.rules.acquisition import acquire_imperium_for_intrigue
from dune_imperium.rules.agent_effects import expire_trashed_card_effects
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat_deployment import legal_combat_deployments
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_lines import reveal_lines

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
    """ "Combat 칸(사막 그림과 교차한 칼)에 Agent를 보내면 이번 turn에 recruit한
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
    """ "비용 화살표" [DI p. 16]: the arrow's cost is paid for its reward. Two
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
    """ "An arrow cost is optional [DI p. 9] and paid once [FAQ p. 3]": with
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
    """ "비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다" (imperium-base.md
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
    """ "| Gun Thopter | 2 | garrison troop이 없는 상대는 영향 없음 |" [FAQ p. 2]
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
    """ "garrison troop이 없는 상대는 영향 없음" [FAQ p. 2]: its Conflict troops
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
    """ "-OR-" is a must-pick-one choice (P0 sweep; imperium-base.md 16, OQ-058
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
    """ "Fremen Bond = another Fremen card in play" [DI p. 16] (imperium-base.md
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
    """ "An arrow cost is optional [DI p. 9] and paid once [FAQ p. 3]" (P0 sweep:
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
    """ "Troop and draw are separate steps (OQ-027 (b), OQ-106)" (P0 sweep): a
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
    """ "Trash(...비용이거나 카드가 자기를 trash하라고 할 때만 의무)" (imperium-base.md
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
    """ "Fremen Bond = another Fremen card in play" [DI p. 16] (imperium-base.md
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
    """ "비용 화살표" [DI p. 16]: the arrow's cost is paid for its reward; two
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
    """ "An arrow cost is optional [DI p. 9] and paid once [FAQ p. 3]": with
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
    """ "Trash(...비용이거나 카드가 자기를 trash하라고 할 때만 의무)" (imperium-base.md
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
    held = _seat(held, hand=(instance, *others), resources=Resources(solari=solari))
    return _do(engine, held, "reveal_turn")


def test_opulence_reveals_one_persuasion() -> None:
    engine, state = _start()
    frame = dict(_opulence_revealed(engine, state, 0).decision_stack[-1].context)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 0


def test_opulence_pays_six_solari_for_one_victory_point() -> None:
    """ "비용 화살표" [DI p. 16] (imperium-base.md 11): the arrow's cost is paid
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


# --- Sardaukar Infantry -----------------------------------------------------------


def test_sardaukar_infantry_matches_the_app_table() -> None:
    # App attribute table: cost 1, 2 copies, Emperor, no Agent icon, Reveal 1
    # Persuasion and 2 swords.
    entry = IMPERIUM_CARDS_BY_ID["sardaukar_infantry"]
    assert entry.card.name == "Sardaukar Infantry"
    assert entry.acquisition_cost == 1
    assert entry.copies == 2
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == ()
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 2)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:sardaukar_infantry:1") is entry


def test_sardaukar_infantry_cannot_be_sent_as_an_agent() -> None:
    """ "Agent 아이콘이 없는 카드는 Agent turn에 낼 수 없다" [DI p. 9]
    (imperium-base.md 5): the card is Reveal-only."""

    engine, state = _start()
    state, _ = _with_card(state, "sardaukar_infantry")
    assert not [
        placement
        for placement in executable_placements(state, 0)
        if ":sardaukar_infantry:" in str(dict(placement.arguments)["card_id"])
    ]


def test_sardaukar_infantry_reveals_one_persuasion_and_two_swords() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "sardaukar_infantry", alone=True)
    state = _with_troops(state, 0, garrison=0, conflict=1)
    revealed = _do(engine, state, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 2
    # Nothing else holds the Reveal open; the troop's 2 and the card's 2 swords.
    assert _do(engine, revealed, "finish_reveal").players[0].combat_strength == 2 + 2


# --- Space Travel -----------------------------------------------------------------


def test_space_travel_matches_the_app_table() -> None:
    # App attribute table: cost 3, 2 copies, Spacing Guild, Spacing Guild,
    # Reveal 2 Persuasion and no swords.
    entry = IMPERIUM_CARDS_BY_ID["space_travel"]
    assert entry.card.name == "Space Travel"
    assert entry.acquisition_cost == 3
    assert entry.copies == 2
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.SPACING_GUILD,)
    assert entry.agent_effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:space_travel:1") is entry


def test_space_travel_draws_one_card() -> None:
    """P0 sweep: "AGENT: draw 1"; the draw icon is mandatory and a hidden draw
    is its own step ([FAQ p. 3], imperium-base.md 16, OQ-106)."""

    engine, state = _start()
    state, _ = _with_card(state, "space_travel")
    top = state.players[0].deck[0]
    placed = _place(engine, state, "foldspace", "space_travel")
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].hand == (*placed.players[0].hand, top)
    assert resolved.players[0].deck == placed.players[0].deck[1:]


def test_space_travel_reveals_two_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "space_travel", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 2
    assert frame["sword_strength"] == 0


# --- Stilgar ----------------------------------------------------------------------


def test_stilgar_matches_the_app_table() -> None:
    # App attribute table: cost 5, 1 copy, Fremen, Fremen, City and Spice
    # Trade, Reveal 2 Persuasion and 3 swords; AgentWater 1.
    entry = IMPERIUM_CARDS_BY_ID["stilgar"]
    assert entry.card.name == "Stilgar"
    assert entry.acquisition_cost == 5
    assert entry.copies == 1
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (
        AgentIcon.FREMEN,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is PersonalCardAgentEffect.GAIN_WATER
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 3)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:stilgar:0") is entry


def test_stilgar_agent_box_gains_one_water() -> None:
    """P0 sweep: "AGENT: 1 water"; a plain, mandatory gain."""

    engine, state = _start()
    state, _ = _with_card(state, "stilgar")
    state = _seat(state, resources=Resources(water=2))
    placed = _place(engine, state, "imperium_research_station", "stilgar")
    before = placed.players[0].resources
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].resources.water == before.water + 1


def test_stilgar_reveals_two_persuasion_and_three_swords() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "stilgar", alone=True)
    state = _with_troops(state, 0, garrison=0, conflict=1)
    revealed = _do(engine, state, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert frame["persuasion"] == 2
    assert frame["sword_strength"] == 3
    assert _do(engine, revealed, "finish_reveal").players[0].combat_strength == 2 + 3


# --- Thufir Hawat -----------------------------------------------------------------


def test_thufir_hawat_matches_the_app_table() -> None:
    # App attribute table: cost 5, 1 copy, no Faction, Emperor, Spacing Guild,
    # Bene Gesserit, Fremen, City and Spice Trade (no Landsraad), Reveal 1
    # Persuasion and no swords.
    entry = IMPERIUM_CARDS_BY_ID["thufir_hawat"]
    assert entry.card.name == "Thufir Hawat"
    assert entry.acquisition_cost == 5
    assert entry.copies == 1
    assert entry.factions == ()
    assert entry.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:thufir_hawat:0") is entry


def test_thufir_hawat_draws_one_card() -> None:
    """P0 sweep: "AGENT: draw 1"; the draw icon is mandatory and a hidden draw
    is its own step ([FAQ p. 3], imperium-base.md 16, OQ-106)."""

    engine, state = _start()
    state, _ = _with_card(state, "thufir_hawat")
    top = state.players[0].deck[0]
    placed = _place(engine, state, "wealth", "thufir_hawat")
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].hand == (*placed.players[0].hand, top)
    assert resolved.players[0].deck == placed.players[0].deck[1:]


def test_thufir_hawat_has_no_landsraad_icon() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "thufir_hawat")
    spaces = {
        dict(placement.arguments)["space_id"]
        for placement in executable_placements(state, 0)
        if ":thufir_hawat:" in str(dict(placement.arguments)["card_id"])
    }
    assert {"wealth", "foldspace", "stillsuits", "carthag"} <= spaces
    assert not {"hall_of_oratory", "rally_troops"} & spaces


def _thufir_revealed(
    engine: UprisingRulesEngine,
    state: GameState,
    intrigue_deck: tuple[str, ...] = ("intrigue:bribery:0", "intrigue:bribery:1"),
) -> GameState:
    held, _ = _with_card(state, "thufir_hawat", alone=True)
    return _do(engine, replace(held, intrigue_deck=intrigue_deck), "reveal_turn")


def test_thufir_hawat_reveals_one_persuasion_and_an_intrigue_card() -> None:
    """P0 sweep: "REVEAL: P1; draw 1 Intrigue (the owner's own step, OQ-045)":
    the draw is a row of the Reveal turn (a hidden draw, OQ-106), taken in any
    order, and it takes the Intrigue deck's top card."""

    engine, state = _start()
    revealed = _thufir_revealed(engine, state)
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (1, 0)
    assert "draw_reveal_intrigue" in _ids(engine, revealed)
    drawn = _do(engine, revealed, "draw_reveal_intrigue")
    assert drawn.players[0].intrigue_cards == (
        *revealed.players[0].intrigue_cards,
        "intrigue:bribery:0",
    )
    assert drawn.intrigue_deck == ("intrigue:bribery:1",)
    assert "draw_reveal_intrigue" not in _ids(engine, drawn)


def test_thufir_hawat_with_no_intrigue_card_left_draws_nothing() -> None:
    """With the Intrigue deck and its discard pile both empty the draw row
    still settles (the engine's Intrigue draw, shared with every Reveal
    Intrigue draw) and the owner's Intrigue cards are unchanged."""

    engine, state = _start()
    revealed = _thufir_revealed(engine, state, intrigue_deck=())
    drawn = _do(engine, revealed, "draw_reveal_intrigue")
    assert drawn.players[0].intrigue_cards == revealed.players[0].intrigue_cards
    assert drawn.intrigue_deck == ()
    assert "draw_reveal_intrigue" not in _ids(engine, drawn)


# --- Spice Hunter -----------------------------------------------------------------


def test_spice_hunter_matches_the_app_table() -> None:
    # App attribute table: cost 2, 2 copies, Fremen, Fremen and Spice Trade,
    # Reveal 1 Persuasion and 1 sword (tag FremenBond); no Agent effect.
    entry = IMPERIUM_CARDS_BY_ID["spice_hunter"]
    assert entry.card.name == "Spice Hunter"
    assert entry.acquisition_cost == 2
    assert entry.copies == 2
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.FREMEN, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:spice_hunter:1") is entry


def test_spice_hunter_agent_box_is_empty() -> None:
    # P0 sweep: "AGENT: none"; the icons only send the Agent to a Fremen or
    # Spice Trade space.
    engine, state = _start()
    state, _ = _with_card(state, "spice_hunter")
    placed = _place(engine, state, "stillsuits", "spice_hunter")
    assert "resolve_agent_card_effect" not in _ids(engine, placed)


def _spice_hunter_revealed(
    engine: UprisingRulesEngine, state: GameState, *others: str
) -> GameState:
    """Seat 0 reveals Spice Hunter with the other cards, nothing in hand but
    them."""

    held, instance = _with_card(state, "spice_hunter", alone=True)
    held = _seat(held, hand=(instance, *others), resources=Resources())
    return _do(engine, held, "reveal_turn")


def test_spice_hunter_without_a_bond_gains_no_spice() -> None:
    """ "Fremen Bond = another Fremen card in play" [DI p. 16] (imperium-base.md
    11): alone, Spice Hunter has no Bond; it reveals its 1 Persuasion and 1
    sword and no gain row opens."""

    engine, state = _start()
    revealed = _spice_hunter_revealed(engine, state)
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (1, 1)
    assert "gain_reveal_resources" not in _ids(engine, revealed)
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].resources.spice == 0


def test_spice_hunter_fremen_bond_gains_one_spice() -> None:
    """The Bond is judged when the line resolves (imperium-base.md 16,
    OQ-028): with Fedaykin Stilltent also revealed the card gains 1 spice."""

    engine, state = _start()
    revealed = _spice_hunter_revealed(engine, state, "imperium:fedaykin_stilltent:0")
    before = revealed.players[0].resources
    gained = _do(engine, revealed, "gain_reveal_resources", printed="spice_hunter")
    assert gained.players[0].resources.spice == before.spice + 1
    assert gained.players[0].resources.water == before.water


# --- Sietch Reverend Mother -------------------------------------------------------


def test_sietch_reverend_mother_matches_the_app_table() -> None:
    # App attribute table: cost 4, 1 copy, Bene Gesserit and Fremen, Bene
    # Gesserit and Fremen, no fixed Reveal values (tag FremenBond).
    entry = IMPERIUM_CARDS_BY_ID["sietch_reverend_mother"]
    assert entry.card.name == "Sietch Reverend Mother"
    assert entry.acquisition_cost == 4
    assert entry.copies == 1
    assert entry.factions == (Faction.BENE_GESSERIT, Faction.FREMEN)
    assert entry.agent_icons == (AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN)
    assert entry.agent_effect is PersonalCardAgentEffect.TRASH_PERSONAL_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:sietch_reverend_mother:0") is entry


def _mother_placed(engine: UprisingRulesEngine, state: GameState) -> GameState:
    held, _ = _with_card(state, "sietch_reverend_mother")
    return _place(engine, held, "stillsuits", "sietch_reverend_mother")


def test_sietch_reverend_mother_may_trash_a_card() -> None:
    """ "Trash(...비용이거나 카드가 자기를 trash하라고 할 때만 의무)" (imperium-base.md
    11, [DI p. 16]): the black trash icon is optional ([FAQ p. 3]); its rows
    are the hand's cards and the card itself in play."""

    engine, state = _start()
    placed = _mother_placed(engine, state)
    owner = placed.players[0]
    me = "imperium:sietch_reverend_mother:0"
    assert _trash_rows(engine, placed) == {*owner.hand, me}
    victim = owner.hand[0]
    trashed = _do(engine, placed, "trash_agent_card", card_id=victim)
    assert victim in trashed.players[0].trashed
    assert victim not in trashed.players[0].hand
    assert not _trash_rows(engine, trashed)


def test_sietch_reverend_mother_trash_is_optional() -> None:
    engine, state = _start()
    placed = _mother_placed(engine, state)
    before = placed.players[0]
    assert _trash_rows(engine, placed)
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    resolved = _do(engine, resolved, "resolve_faction_influence")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].trashed == before.trashed


def _mother_revealed(
    engine: UprisingRulesEngine, state: GameState, *others: str
) -> GameState:
    held, instance = _with_card(state, "sietch_reverend_mother", alone=True)
    held = _seat(held, hand=(instance, *others), resources=Resources())
    return _do(engine, held, "reveal_turn")


def test_sietch_reverend_mother_without_a_bond_reveals_nothing() -> None:
    """Everything of its Reveal box is behind "Fremen Bond" [DI p. 16]
    (imperium-base.md 11): alone the card has no Bond, so no Persuasion and no
    spice."""

    engine, state = _start()
    revealed = _mother_revealed(engine, state)
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (0, 0)
    assert "gain_reveal_resources" not in _ids(engine, revealed)
    assert _do(engine, revealed, "finish_reveal").players[0].resources.spice == 0


def test_sietch_reverend_mother_fremen_bond_gives_three_persuasion_and_a_spice() -> (
    None
):
    """The Bond is judged when the line resolves (imperium-base.md 16,
    OQ-028): with Spice Hunter (Fremen) also revealed, the card's 3 Persuasion
    join the hunter's 1, and 1 spice is gained."""

    engine, state = _start()
    revealed = _mother_revealed(engine, state, "imperium:spice_hunter:0")
    frame = dict(revealed.decision_stack[-1].context)
    assert frame["persuasion"] == 3 + 1
    before = revealed.players[0].resources
    gained = _do(
        engine, revealed, "gain_reveal_resources", printed="sietch_reverend_mother"
    )
    assert gained.players[0].resources.spice == before.spice + 1


# --- Smuggler's Thopter -----------------------------------------------------------


def test_smugglers_thopter_matches_the_app_table() -> None:
    # App attribute table: cost 4, 2 copies, Spacing Guild, Spice Trade,
    # Reveal 1 Persuasion and no swords (tag SpacingGuildInfluence).
    entry = IMPERIUM_CARDS_BY_ID["smugglers_thopter"]
    assert entry.card.name == "Smuggler's Thopter"
    assert entry.acquisition_cost == 4
    assert entry.copies == 2
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.DRAW_TWO_IF_SPACING_GUILD_INFLUENCE_TWO
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:smugglers_thopter:1") is entry


def _thopter_placed(
    engine: UprisingRulesEngine, state: GameState, guild: int
) -> GameState:
    """Seat 0 sends Smuggler's Thopter to Secure Contract (a Spice Trade
    space, no cost) holding ``guild`` Spacing Guild Influence."""

    held, _ = _with_card(state, "smugglers_thopter")
    seated = _seat(held, influence=Influence(spacing_guild=guild))
    return _place(engine, seated, "secure_contract", "smugglers_thopter")


def _thopter_icons(engine: UprisingRulesEngine, state: GameState) -> list[object]:
    return [
        dict(action.arguments)["effect"]
        for action in _wholes(engine, state)
        if action.action_id == "resolve_agent_card_effect"
    ]


def test_smugglers_thopter_draws_two_cards_at_two_guild_influence() -> None:
    """ "Spacing Guild Influence 2: [draw 1] [draw 1]": the Influence condition
    holds at 2 ("Influence 조건" [DI p. 16], imperium-base.md 11) and each draw
    icon is its own step (OQ-027, OQ-106): both are offered, and each takes the
    deck's next card."""

    engine, state = _start()
    placed = _thopter_placed(engine, state, guild=2)
    owner = placed.players[0]
    assert sorted(str(icon) for icon in _thopter_icons(engine, placed)) == [
        "cards",
        "cards_second",
    ]
    assert "finish_agent_turn" not in _ids(engine, placed)
    first = _do(engine, placed, "resolve_agent_card_effect", effect="cards")
    assert first.players[0].hand == (*owner.hand, owner.deck[0])
    assert _thopter_icons(engine, first) == ["cards_second"]
    second = _do(engine, first, "resolve_agent_card_effect", effect="cards_second")
    assert second.players[0].hand == (*owner.hand, owner.deck[0], owner.deck[1])
    assert second.players[0].deck == owner.deck[2:]


def test_smugglers_thopter_draws_nothing_below_two_guild_influence() -> None:
    """One Spacing Guild Influence is short of the condition: neither icon is
    offered, and the box waits until the turn's end (OQ-057 (1))."""

    engine, state = _start()
    placed = _thopter_placed(engine, state, guild=1)
    owner = placed.players[0]
    assert _thopter_icons(engine, placed) == []
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].hand == resolved.players[0].hand
    assert finished.players[0].deck == owner.deck


def test_smugglers_thopter_icon_is_judged_when_it_resolves() -> None:
    """ "조건은 해결할 때 판정한다(OQ-028)" (imperium-base.md 16): the Influence
    is read for each icon when it resolves, so Secure Contract's own effect
    does not matter, but a drop below 2 between the icons closes the second."""

    engine, state = _start()
    placed = _thopter_placed(engine, state, guild=2)
    first = _do(engine, placed, "resolve_agent_card_effect", effect="cards")
    lowered = _seat(first, influence=Influence(spacing_guild=1))
    assert _thopter_icons(engine, lowered) == []
    raised = _seat(lowered, influence=Influence(spacing_guild=2))
    assert _thopter_icons(engine, raised) == ["cards_second"]


def test_smugglers_thopter_reveals_one_persuasion_and_one_spice() -> None:
    """P0 sweep: "REVEAL: P1, spice 1" ([DI p. 11] example): the spice is a
    gain row of the Reveal turn."""

    engine, state = _start()
    held, instance = _with_card(state, "smugglers_thopter", alone=True)
    held = _seat(held, resources=Resources())
    revealed = _do(engine, held, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (1, 0)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert gained.players[0].resources.spice == 1


# --- Worm Riders ------------------------------------------------------------------


def test_worm_riders_matches_the_app_table() -> None:
    # App attribute table: cost 6, 2 copies, Fremen, City and Spice Trade, no
    # fixed Reveal values (tags FremenInfluence, FremenAlliance,
    # ConditionalStrength); AgentSpice 2.
    entry = IMPERIUM_CARDS_BY_ID["worm_riders"]
    assert entry.card.name == "Worm Riders"
    assert entry.acquisition_cost == 6
    assert entry.copies == 2
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is PersonalCardAgentEffect.GAIN_TWO_SPICE
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:worm_riders:1") is entry


def test_worm_riders_agent_box_gains_two_spice() -> None:
    """P0 sweep: "AGENT: 2 spice"; a plain, mandatory gain."""

    engine, state = _start()
    state, _ = _with_card(state, "worm_riders")
    state = _seat(state, resources=Resources(water=2))
    placed = _place(engine, state, "imperium_research_station", "worm_riders")
    before = placed.players[0].resources
    assert "finish_agent_turn" not in _ids(engine, placed)
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].resources.spice == before.spice + 2


def _riders_swords(
    engine: UprisingRulesEngine,
    state: GameState,
    *,
    fremen: int = 0,
    alliance: bool = False,
) -> object:
    """The sword strength Worm Riders reveals for a seat with ``fremen``
    Fremen Influence (and the Fremen Alliance when ``alliance``)."""

    held, _ = _with_card(state, "worm_riders", alone=True)
    held = _seat(
        held,
        influence=Influence(fremen=fremen),
        alliance_faction_ids=("fremen",) if alliance else (),
    )
    return dict(_do(engine, held, "reveal_turn").decision_stack[-1].context)[
        "sword_strength"
    ]


def test_worm_riders_reveals_nothing_without_influence_or_alliance() -> None:
    """Nothing of its Reveal box is unconditional (P0 sweep): with 1 Fremen
    Influence and no Alliance the card reveals no Persuasion and no swords."""

    engine, state = _start()
    assert _riders_swords(engine, state, fremen=1) == 0
    held, _ = _with_card(state, "worm_riders", alone=True)
    frame = _reveal(engine, _seat(held, influence=Influence(fremen=1)))
    assert frame["persuasion"] == 0


def test_worm_riders_fremen_influence_two_gives_four_swords() -> None:
    """ "Influence 조건" [DI p. 16] (imperium-base.md 11): the first line holds
    at 2 Fremen Influence, without the Alliance."""

    engine, state = _start()
    assert _riders_swords(engine, state, fremen=2) == 4
    assert _riders_swords(engine, state, fremen=3) == 4


def test_worm_riders_fremen_alliance_adds_two_swords() -> None:
    """Two independent lines, each judged when resolved (OQ-028): the Alliance
    line adds 2 to the Influence line's 4. A seat holds the Alliance only at 4
    Influence or more, but each line is judged on its own."""

    engine, state = _start()
    assert _riders_swords(engine, state, fremen=4, alliance=True) == 4 + 2
    assert _riders_swords(engine, state, fremen=1, alliance=True) == 2


def test_worm_riders_swords_count_with_a_troop_in_the_conflict() -> None:
    """ "Conflict에 troop이 하나도 없으면 0" [DI p. 11]: the 4 swords join the
    troop's 2 once a troop stands in the Conflict, and are worth nothing
    without one."""

    engine, state = _start()
    for conflict, expected in ((1, 2 + 4), (0, 0)):
        held, _ = _with_card(state, "worm_riders", alone=True)
        held = _seat(held, influence=Influence(fremen=2))
        held = _with_troops(held, 0, garrison=0, conflict=conflict)
        revealed = _do(engine, held, "reveal_turn")
        finished = _do(engine, revealed, "finish_reveal")
        assert finished.players[0].combat_strength == expected


def test_worm_riders_reveal_text_names_its_two_conditions() -> None:
    lines = reveal_lines(IMPERIUM_CARDS_BY_ID["worm_riders"])
    assert [reveal_effect_text(line) for line in lines] == [
        "If you have 2 or more Fremen Influence: +4 swords",
        "If you have the Fremen Alliance: +2 swords",
    ]
    assert [reveal_effect_text_ko(line) for line in lines] == [
        "{influence_fremen} 2 이상이면: +{sword:4}",
        "프레멘 {alliance}이면: +{sword:2}",
    ]


# --- Guild Ambassador -------------------------------------------------------------


def test_guild_ambassador_matches_the_app_table() -> None:
    # App attribute table: cost 4, 1 copy, Spacing Guild, Landsraad, no fixed
    # Reveal values (tag SpacingGuildAlliance).
    entry = IMPERIUM_CARDS_BY_ID["guild_ambassador"]
    assert entry.card.name == "Guild Ambassador"
    assert entry.acquisition_cost == 4
    assert entry.copies == 1
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.LANDSRAAD,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.GAIN_SPACING_GUILD_INFLUENCE_OR_TWO_SPICE
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_VICTORY_POINT_IF_SPACING_GUILD_ALLIANCE,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:guild_ambassador:0") is entry


def _ambassador_placed(
    engine: UprisingRulesEngine, state: GameState, guild: int = 0
) -> GameState:
    """Seat 0 sends Guild Ambassador to Hall of Oratory (a Landsraad space, no
    cost) holding ``guild`` Spacing Guild Influence and no spice."""

    held, _ = _with_card(state, "guild_ambassador")
    seated = _seat(
        held, resources=Resources(), influence=Influence(spacing_guild=guild)
    )
    return _place(engine, seated, "hall_of_oratory", "guild_ambassador")


def test_guild_ambassador_must_pick_influence_or_two_spice() -> None:
    """ "-OR-" is a must-pick-one choice (P0 sweep: "choose one (must)";
    imperium-base.md 16, OQ-058 for the same shape on Intrigue): both the
    Spacing Guild Influence and the 2 spice are offered, and the turn cannot
    finish before one is taken."""

    engine, state = _start()
    placed = _ambassador_placed(engine, state, guild=1)
    ids = _ids(engine, placed)
    assert {"resolve_agent_card_effect", "choose_agent_card_influence"} <= ids
    assert "finish_agent_turn" not in ids
    influence_rows = [
        dict(action.arguments)["faction"]
        for action in _wholes(engine, placed)
        if action.action_id == "choose_agent_card_influence"
    ]
    assert influence_rows == ["spacing_guild"]


def test_guild_ambassador_two_spice_branch() -> None:
    engine, state = _start()
    placed = _ambassador_placed(engine, state, guild=1)
    before = placed.players[0]
    chosen = _do(engine, placed, "resolve_agent_card_effect")
    after = chosen.players[0]
    assert after.resources.spice == before.resources.spice + 2
    assert after.influence.spacing_guild == before.influence.spacing_guild
    # The other alternative is gone.
    assert "choose_agent_card_influence" not in _ids(engine, chosen)
    assert "resolve_agent_card_effect" not in _ids(engine, chosen)


def test_guild_ambassador_influence_branch() -> None:
    engine, state = _start()
    placed = _ambassador_placed(engine, state, guild=1)
    before = placed.players[0]
    chosen = _do(engine, placed, "choose_agent_card_influence", faction="spacing_guild")
    after = chosen.players[0]
    assert after.influence.spacing_guild == before.influence.spacing_guild + 1
    assert after.resources.spice == before.resources.spice
    assert "resolve_agent_card_effect" not in _ids(engine, chosen)
    assert "choose_agent_card_influence" not in _ids(engine, chosen)


def test_guild_ambassador_at_the_top_of_the_track_offers_the_spice_alone() -> None:
    """ "6칸 진영은 Influence를 내지 않는다(OQ-060)" (imperium-base.md 16): at 6
    the Influence option gains nothing, so only the 2 spice remain."""

    engine, state = _start()
    placed = _ambassador_placed(engine, state, guild=6)
    ids = _ids(engine, placed)
    assert "choose_agent_card_influence" not in ids
    assert "resolve_agent_card_effect" in ids
    chosen = _do(engine, placed, "resolve_agent_card_effect")
    assert chosen.players[0].resources.spice == 2
    assert chosen.players[0].influence.spacing_guild == 6


def _ambassador_revealed(
    engine: UprisingRulesEngine,
    state: GameState,
    spice: int,
    *,
    alliance: bool,
) -> GameState:
    """Seat 0 reveals Guild Ambassador alone holding ``spice`` spice, with or
    without the Spacing Guild Alliance."""

    held, instance = _with_card(state, "guild_ambassador", alone=True)
    held = _seat(
        held,
        resources=Resources(spice=spice),
        alliance_faction_ids=("spacing_guild",) if alliance else (),
    )
    return _do(engine, held, "reveal_turn")


def test_guild_ambassador_reveals_no_persuasion_or_swords() -> None:
    engine, state = _start()
    revealed = _ambassador_revealed(engine, state, 3, alliance=True)
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (0, 0)


def test_guild_ambassador_pays_three_spice_for_a_victory_point() -> None:
    """ "비용 화살표" [DI p. 16] (imperium-base.md 11): with the Spacing Guild
    Alliance three spice buy one Victory Point, once (the choice is used up)."""

    engine, state = _start()
    revealed = _ambassador_revealed(engine, state, 3, alliance=True)
    before = revealed.players[0]
    assert "pay_reveal_spice_for_vp" in _ids(engine, revealed)
    paid = _do(engine, revealed, "pay_reveal_spice_for_vp")
    after = paid.players[0]
    assert after.resources.spice == before.resources.spice - 3
    assert after.victory_points == before.victory_points + 1
    assert "pay_reveal_spice_for_vp" not in _ids(engine, paid)


def test_guild_ambassador_needs_the_alliance() -> None:
    """ "Alliance 조건" [DI p. 16] (11): without the Spacing Guild Alliance
    the payment is not offered, however much spice is held."""

    engine, state = _start()
    revealed = _ambassador_revealed(engine, state, 9, alliance=False)
    assert "pay_reveal_spice_for_vp" not in _ids(engine, revealed)
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].resources.spice == 9


def test_guild_ambassador_needs_three_spice_to_pay() -> None:
    engine, state = _start()
    revealed = _ambassador_revealed(engine, state, 2, alliance=True)
    assert "pay_reveal_spice_for_vp" not in _ids(engine, revealed)
    assert _do(engine, revealed, "finish_reveal").players[0].victory_points == (
        revealed.players[0].victory_points
    )


def test_guild_ambassador_arrow_is_optional() -> None:
    """The arrow cost is optional [DI p. 9] ("You do not have to pay such a
    cost on a card" [Main p. 20]): the Reveal ends with no refusal needed."""

    engine, state = _start()
    revealed = _ambassador_revealed(engine, state, 3, alliance=True)
    before = revealed.players[0]
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].resources.spice == 3
    assert finished.players[0].victory_points == before.victory_points


# --- Gurney Halleck ---------------------------------------------------------------


def test_gurney_halleck_matches_the_app_table() -> None:
    # App attribute table: cost 6, 1 copy, no Faction, City, Reveal 2
    # Persuasion and no swords; AgentTroops 2.
    entry = IMPERIUM_CARDS_BY_ID["gurney_halleck_card"]
    assert entry.card.name == "Gurney Halleck"
    assert entry.acquisition_cost == 6
    assert entry.copies == 1
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is PersonalCardAgentEffect.RECRUIT_TWO_AND_DRAW_ONE
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SOLARI_FOR_TWO_TROOPS_AND_DEPLOY,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:gurney_halleck_card:0") is entry


def _gurney_placed(engine: UprisingRulesEngine, state: GameState) -> GameState:
    """Seat 0 sends Gurney Halleck to Research Station (a City space; its two
    water are paid)."""

    held, _ = _with_card(state, "gurney_halleck_card")
    seated = _seat(held, resources=Resources(water=2))
    return _place(engine, seated, "imperium_research_station", "gurney_halleck_card")


def test_gurney_halleck_recruits_two_troops_and_draws_a_card_apart() -> None:
    """ "[troop 2][draw 1]": separate icons (OQ-027), the hidden draw apart from
    the public recruit (OQ-106, imperium-base.md 15): both icons are offered,
    in either order, and the turn cannot end while either waits."""

    engine, state = _start()
    placed = _gurney_placed(engine, state)
    owner = placed.players[0]
    icons = {
        dict(action.arguments)["effect"]
        for action in _wholes(engine, placed)
        if action.action_id == "resolve_agent_card_effect"
    }
    assert icons == {"troops", "cards"}
    assert "finish_agent_turn" not in _ids(engine, placed)
    drawn = _do(engine, placed, "resolve_agent_card_effect", effect="cards")
    assert drawn.players[0].hand == (*owner.hand, owner.deck[0])
    assert drawn.players[0].troops_garrison == owner.troops_garrison
    done = _do(engine, drawn, "resolve_agent_card_effect", effect="troops")
    assert done.players[0].troops_garrison == owner.troops_garrison + 2
    assert done.players[0].troops_supply == owner.troops_supply - 2


def test_gurney_halleck_recruited_troops_deploy_at_a_combat_space() -> None:
    """Research Station is a Combat space: "이번 turn에 recruit한 troop 전부와
    garrison의 troop 둘까지를 Conflict에 배치할 수 있다" [DI pp. 10, 17-18]
    (imperium-base.md 7): the two recruited and two from the garrison."""

    engine, state = _start()
    placed = _gurney_placed(engine, state)
    recruited = _do(engine, placed, "resolve_agent_card_effect", effect="troops")
    most = max(
        int(dict(action.arguments)["count"])
        for action in legal_combat_deployments(recruited, 0)
    )
    assert most == 2 + 2


def _gurney_revealed(
    engine: UprisingRulesEngine, state: GameState, solari: int
) -> GameState:
    held, _ = _with_card(state, "gurney_halleck_card", alone=True)
    held = _seat(held, resources=Resources(solari=solari))
    return _do(engine, held, "reveal_turn")


def test_gurney_halleck_reveals_two_persuasion() -> None:
    engine, state = _start()
    frame = dict(_gurney_revealed(engine, state, 0).decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (2, 0)


def test_gurney_halleck_pays_three_solari_for_two_troops_it_may_deploy() -> None:
    """ "비용 화살표" [DI p. 16] (imperium-base.md 11), optional [DI p. 9] and
    paid once [FAQ p. 3]: three Solari recruit two troops, and in the Reveal
    turn "you may deploy these troops to the Conflict" -- up to the two
    recruited, and no other garrison troop."""

    engine, state = _start()
    revealed = _gurney_revealed(engine, state, 3)
    before = revealed.players[0]
    assert "pay_reveal_solari_for_troops" in _ids(engine, revealed)
    # Nothing deploys before the payment: no Combat icon, no recruit.
    assert "deploy_troops" not in _ids(engine, revealed)
    paid = _do(engine, revealed, "pay_reveal_solari_for_troops")
    after = paid.players[0]
    assert after.resources.solari == 0
    assert after.troops_garrison == before.troops_garrison + 2
    assert after.troops_supply == before.troops_supply - 2
    assert "pay_reveal_solari_for_troops" not in _ids(engine, paid)
    counts = {
        int(dict(action.arguments)["count"])
        for action in _wholes(engine, paid)
        if action.action_id == "deploy_troops"
    }
    assert counts == {1, 2}
    deployed = _do(engine, paid, "deploy_troops", count=2)
    assert deployed.players[0].troops_conflict == before.troops_conflict + 2
    assert deployed.players[0].troops_garrison == before.troops_garrison
    finished = _do(engine, deployed, "finish_reveal")
    assert finished.players[0].combat_strength == 2 * 2


def test_gurney_halleck_deployment_is_optional() -> None:
    """ "May deploy": the recruited troops stay in the garrison when not
    deployed, and the Reveal ends without a refusal."""

    engine, state = _start()
    revealed = _gurney_revealed(engine, state, 3)
    paid = _do(engine, revealed, "pay_reveal_solari_for_troops")
    finished = _do(engine, paid, "finish_reveal")
    assert finished.players[0].troops_conflict == 0
    assert finished.players[0].troops_garrison == paid.players[0].troops_garrison


def test_gurney_halleck_arrow_is_optional() -> None:
    """The arrow cost is optional [DI p. 9] ("You do not have to pay such a
    cost on a card" [Main p. 20]): the Reveal ends with no refusal needed."""

    engine, state = _start()
    revealed = _gurney_revealed(engine, state, 5)
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].resources.solari == 5
    assert finished.players[0].troops_garrison == revealed.players[0].troops_garrison


def test_gurney_halleck_needs_three_solari_to_pay() -> None:
    engine, state = _start()
    revealed = _gurney_revealed(engine, state, 2)
    assert "pay_reveal_solari_for_troops" not in _ids(engine, revealed)


def test_gurney_halleck_payment_opens_once_a_later_gain_makes_three_solari() -> None:
    """Reveal effects resolve in any order ([Main p. 12]; OQ-028: judged when
    asked): Price is No Object's 2 Solari bring 1 to the 3 the arrow costs."""

    engine, state = _start()
    held, instance = _with_card(state, "gurney_halleck_card", alone=True)
    held = _seat(
        held,
        hand=(instance, "imperium:price_is_no_object:0"),
        resources=Resources(solari=1),
    )
    revealed = _do(engine, held, "reveal_turn")
    assert "pay_reveal_solari_for_troops" not in _ids(engine, revealed)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert gained.players[0].resources.solari == 3
    paid = _do(engine, gained, "pay_reveal_solari_for_troops")
    assert paid.players[0].resources.solari == 0


# --- Imperial Spy -----------------------------------------------------------------


def test_imperial_spy_matches_the_app_table() -> None:
    # App attribute table: cost 2, 2 copies, Emperor, Emperor, Reveal 1
    # Persuasion and 1 sword.
    entry = IMPERIUM_CARDS_BY_ID["imperial_spy"]
    assert entry.card.name == "Imperial Spy"
    assert entry.acquisition_cost == 2
    assert entry.copies == 2
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == (AgentIcon.EMPEROR,)
    assert entry.agent_effect is PersonalCardAgentEffect.MAY_TRASH_SELF_TO_DRAW_INTRIGUE
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:imperial_spy:1") is entry


def _spy_placed(engine: UprisingRulesEngine, state: GameState) -> GameState:
    """Seat 0 sends Imperial Spy to Wealth (an Emperor space, no cost) with a
    known Intrigue deck."""

    held, _ = _with_card(state, "imperial_spy")
    seated = replace(held, intrigue_deck=("intrigue:bribery:0", "intrigue:bribery:1"))
    return _place(engine, seated, "wealth", "imperial_spy")


def test_imperial_spy_trashes_itself_to_draw_an_intrigue_card() -> None:
    """ "Trash this card -> [Intrigue card]": an arrow cost, optional [DI p. 9]
    [FAQ p. 3]; the card trashes itself as its own cost, so its draw is still
    paid (imperium-base.md 16, OQ-022's own-effect case) and, a hidden draw,
    is a step of its own (OQ-106): the turn cannot end before it is taken."""

    engine, state = _start()
    placed = _spy_placed(engine, state)
    me = "imperium:imperial_spy:0"
    assert dict(
        next(
            action.arguments
            for action in _wholes(engine, placed)
            if action.action_id == "trash_agent_card"
        )
    ) == {"card_id": me}
    trashed = _do(engine, placed, "trash_agent_card", card_id=me)
    assert me in trashed.players[0].trashed
    assert me not in trashed.players[0].in_play
    assert trashed.players[0].intrigue_cards == placed.players[0].intrigue_cards
    assert "finish_agent_turn" not in _ids(engine, trashed)
    drawn = _do(engine, trashed, "resolve_agent_card_effect", effect="intrigue")
    assert drawn.players[0].intrigue_cards == (
        *placed.players[0].intrigue_cards,
        "intrigue:bribery:0",
    )
    assert drawn.intrigue_deck == ("intrigue:bribery:1",)


def test_imperial_spy_arrow_is_optional() -> None:
    engine, state = _start()
    placed = _spy_placed(engine, state)
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    resolved = _do(engine, resolved, "resolve_faction_influence")
    finished = _do(engine, resolved, "finish_agent_turn")
    after = finished.players[0]
    assert "imperium:imperial_spy:0" not in after.trashed
    assert after.intrigue_cards == placed.players[0].intrigue_cards
    assert finished.intrigue_deck == placed.intrigue_deck


def test_imperial_spy_trashed_by_another_effect_draws_nothing() -> None:
    """ "이 카드로 자신을 trash해야 Intrigue; 다른 수단으로 trash되면 없음" (FAQ p.
    2, imperium-base.md 13.2) and "다른 수단으로 먼저 trash하면 남은 효과는 없다"
    (16, OQ-022): once the Spy has left play by another effect, its arrow
    offers no trash."""

    engine, state = _start()
    placed = _spy_placed(engine, state)
    me = "imperium:imperial_spy:0"
    owner = placed.players[0]
    gone = _seat(
        placed,
        in_play=tuple(card for card in owner.in_play if card != me),
        trashed=(*owner.trashed, me),
    )
    assert "trash_agent_card" not in _ids(engine, gone)
    assert gone.players[0].intrigue_cards == placed.players[0].intrigue_cards


def test_imperial_spy_reveals_one_persuasion_and_one_sword() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "imperial_spy", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 1


# --- Assassination Mission --------------------------------------------------------


def test_assassination_mission_matches_the_app_table() -> None:
    # App attribute table: cost 1, 2 copies, no Faction, no Agent icon, Reveal
    # 1 sword and 1 Solari (the Solari is its Reveal gain), no Persuasion.
    entry = IMPERIUM_CARDS_BY_ID["assassination_mission"]
    assert entry.card.name == "Assassination Mission"
    assert entry.acquisition_cost == 1
    assert entry.copies == 2
    assert entry.factions == ()
    assert entry.agent_icons == ()
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 1)
    assert entry.trash_effect is PersonalCardTrashEffect.GAIN_FOUR_SOLARI
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:assassination_mission:1") is entry


def test_assassination_mission_cannot_be_sent_as_an_agent() -> None:
    """ "Agent 아이콘이 없는 카드는 Agent turn에 낼 수 없다" [DI p. 9]
    (imperium-base.md 5): the card is Reveal-only, and has no way to trash
    itself [FAQ p. 1]."""

    engine, state = _start()
    state, _ = _with_card(state, "assassination_mission")
    assert not [
        placement
        for placement in executable_placements(state, 0)
        if ":assassination_mission:" in str(dict(placement.arguments)["card_id"])
    ]


def test_assassination_mission_reveals_one_solari_and_one_sword() -> None:
    engine, state = _start()
    held, _ = _with_card(state, "assassination_mission", alone=True)
    held = _with_troops(_seat(held, resources=Resources()), 0, garrison=0, conflict=1)
    revealed = _do(engine, held, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (0, 1)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert gained.players[0].resources.solari == 1
    assert _do(engine, gained, "finish_reveal").players[0].combat_strength == 2 + 1


def _administrator_with_mission(
    engine: UprisingRulesEngine, state: GameState, *, zone: str
) -> GameState:
    """Seat 0 sends Guild Administrator (a black trash icon) with Assassination
    Mission in its ``zone`` and no Solari."""

    held, _ = _with_card(state, "guild_administrator")
    mission = "imperium:assassination_mission:0"
    owner = held.players[0]
    if zone == "hand":
        seated = _seat(held, hand=(*owner.hand, mission), resources=Resources())
    else:
        seated = _seat(
            held,
            discard_pile=(*owner.discard_pile, mission),
            resources=Resources(),
        )
    return _place(engine, seated, "secure_contract", "guild_administrator")


def test_assassination_mission_trashed_from_the_hand_pays_four_solari() -> None:
    """ "다른 수단으로 trash해야 4 Solari" (imperium-base.md 13.2, [FAQ p. 1]): a
    trash by another card's effect -- here Guild Administrator's black trash
    icon, optional ([DI p. 16], [FAQ p. 3]) -- pays 4 Solari to the owner."""

    engine, state = _start()
    placed = _administrator_with_mission(engine, state, zone="hand")
    mission = "imperium:assassination_mission:0"
    assert mission in _trash_rows(engine, placed)
    trashed = _do(engine, placed, "trash_agent_card", card_id=mission)
    after = trashed.players[0]
    assert mission in after.trashed
    assert after.resources.solari == 4
    # The gain survives the rest of the turn.
    finished = _do(engine, trashed, "resolve_board_effect", effect="resources")
    assert finished.players[0].resources.solari >= 4


def test_assassination_mission_trashed_from_the_discard_pile_pays_too() -> None:
    """The trigger fires "whenever this card is trashed (any zone, any effect)"
    (P0 sweep)."""

    engine, state = _start()
    placed = _administrator_with_mission(engine, state, zone="discard")
    mission = "imperium:assassination_mission:0"
    trashed = _do(engine, placed, "trash_agent_card", card_id=mission)
    assert trashed.players[0].resources.solari == 4
    assert mission in trashed.players[0].trashed
    assert mission not in trashed.players[0].discard_pile


def test_assassination_mission_pays_nothing_unless_trashed() -> None:
    engine, state = _start()
    placed = _administrator_with_mission(engine, state, zone="hand")
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert "imperium:assassination_mission:0" not in finished.players[0].trashed
    assert finished.players[0].resources.solari == resolved.players[0].resources.solari


def test_assassination_mission_trashed_at_selective_breeding_pays_four_solari() -> None:
    """The trash is any effect's, the board space's included: Selective
    Breeding's paid trash ("trash a card" for the 2 spice, [DI p. 18]) takes
    the Mission from the hand and the 4 Solari reach the owner."""

    engine, state = _start()
    held, _ = _with_card(state, "sietch_reverend_mother")
    mission = "imperium:assassination_mission:0"
    owner = held.players[0]
    seated = _seat(held, hand=(*owner.hand, mission), resources=Resources(spice=2))
    placed = _place(engine, seated, "selective_breeding", "sietch_reverend_mother")
    rows = [
        action
        for action in _wholes(engine, placed)
        if action.action_id == "trash_card_for_desert_tactics"
        and dict(action.arguments)["card_id"] == mission
    ]
    assert rows
    trashed = apply_whole(engine, placed, rows[0]).state
    assert mission in trashed.players[0].trashed
    assert trashed.players[0].resources.spice == 0
    assert trashed.players[0].resources.solari == placed.players[0].resources.solari + 4


# --- Missionaria Protectiva -------------------------------------------------------


def test_missionaria_protectiva_matches_the_app_table() -> None:
    # App attribute table: cost 1, 2 copies, Bene Gesserit (the first English
    # printing's missing band is errata, [FAQ p. 1]), City, Reveal 1 Persuasion
    # and no swords (tag WantBG).
    entry = IMPERIUM_CARDS_BY_ID["missionaria_protectiva"]
    assert entry.card.name == "Missionaria Protectiva"
    assert entry.acquisition_cost == 1
    assert entry.copies == 2
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_BENE_GESSERIT_BOND
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:missionaria_protectiva:1") is entry


def _missionaria_placed(
    engine: UprisingRulesEngine,
    state: GameState,
    *,
    bene_gesserit: bool,
    influence: Influence | None = None,
) -> GameState:
    """Seat 0 sends Missionaria Protectiva to Research Station (a City space;
    its two water are paid) with, or without, another Bene Gesserit card (Bene
    Gesserit Initiate) already in play."""

    held, _ = _with_card(state, "missionaria_protectiva")
    seated = _seat(
        held,
        in_play=("imperium:bene_gesserit_initiate:0",) if bene_gesserit else (),
        resources=Resources(water=2),
        influence=influence or Influence(),
    )
    return _place(engine, seated, "imperium_research_station", "missionaria_protectiva")


def _influence_rows(engine: UprisingRulesEngine, state: GameState) -> list[object]:
    return [
        dict(action.arguments)["faction"]
        for action in _wholes(engine, state)
        if action.action_id == "choose_agent_card_influence"
    ]


def test_missionaria_protectiva_gains_influence_with_another_bene_gesserit() -> None:
    """ "another Bene Gesserit card in play" (imperium-base.md 16, OQ-028; the
    Bond of [DI p. 16]): with one in play the owner chooses any Faction for 1
    Influence, and the turn cannot end before the choice."""

    engine, state = _start()
    placed = _missionaria_placed(engine, state, bene_gesserit=True)
    assert sorted(str(f) for f in _influence_rows(engine, placed)) == [
        "bene_gesserit",
        "emperor",
        "fremen",
        "spacing_guild",
    ]
    assert "finish_agent_turn" not in _ids(engine, placed)
    before = placed.players[0].influence
    chosen = _do(engine, placed, "choose_agent_card_influence", faction="fremen")
    after = chosen.players[0].influence
    assert after.fremen == before.fremen + 1
    assert after.emperor == before.emperor
    assert not _influence_rows(engine, chosen)


def test_missionaria_protectiva_alone_gains_nothing() -> None:
    """Without another Bene Gesserit card in play the condition fails at the
    placement: no row is offered and the turn ends freely."""

    engine, state = _start()
    placed = _missionaria_placed(engine, state, bene_gesserit=False)
    assert not _influence_rows(engine, placed)
    resolved = _do(engine, placed, "resolve_board_effect", effect="cards")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].influence == placed.players[0].influence


def test_missionaria_protectiva_condition_is_judged_when_it_resolves() -> None:
    """ "조건은 해결할 때 판정한다(OQ-028)": if the other Bene Gesserit card has
    left play before the choice, the box offers nothing and the turn's end
    fizzles it (OQ-057 (1))."""

    engine, state = _start()
    placed = _missionaria_placed(engine, state, bene_gesserit=True)
    initiate = "imperium:bene_gesserit_initiate:0"
    remaining = tuple(card for card in placed.players[0].in_play if card != initiate)
    gone = _seat(placed, in_play=remaining)
    assert not _influence_rows(engine, gone)


def test_missionaria_protectiva_does_not_offer_a_faction_at_the_top() -> None:
    """ "6칸 진영은 Influence를 내지 않는다(OQ-060)" (imperium-base.md 16)."""

    engine, state = _start()
    placed = _missionaria_placed(
        engine,
        state,
        bene_gesserit=True,
        influence=Influence(emperor=6, fremen=3),
    )
    rows = _influence_rows(engine, placed)
    assert "emperor" not in rows
    assert {"fremen", "spacing_guild", "bene_gesserit"} <= set(rows)


def test_missionaria_protectiva_reveals_one_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "missionaria_protectiva", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 1
    assert frame["sword_strength"] == 0


# --- Gene Manipulation ------------------------------------------------------------


def test_gene_manipulation_matches_the_app_table() -> None:
    # App attribute table: cost 3, 2 copies, Bene Gesserit, Landsraad and City,
    # Reveal 2 Persuasion and no swords (tag WantBG).
    entry = IMPERIUM_CARDS_BY_ID["gene_manipulation"]
    assert entry.card.name == "Gene Manipulation"
    assert entry.acquisition_cost == 3
    assert entry.copies == 2
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.CITY)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_TRASH_AND_GAIN_TWO_SPICE_IF_BENE_GESSERIT_BOND
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:gene_manipulation:1") is entry


def _manipulation_placed(
    engine: UprisingRulesEngine, state: GameState, *, bene_gesserit: bool
) -> GameState:
    """Seat 0 sends Gene Manipulation to Research Station (a City space; its
    two water are paid) with, or without, another Bene Gesserit card (Bene
    Gesserit Initiate) already in play, and no spice."""

    held, _ = _with_card(state, "gene_manipulation")
    seated = _seat(
        held,
        in_play=("imperium:bene_gesserit_initiate:0",) if bene_gesserit else (),
        resources=Resources(water=2),
    )
    return _place(engine, seated, "imperium_research_station", "gene_manipulation")


def _spice_icon(engine: UprisingRulesEngine, state: GameState) -> bool:
    return any(
        action.action_id == "resolve_agent_card_effect"
        and dict(action.arguments).get("effect") == "spice"
        for action in _wholes(engine, state)
    )


def test_gene_manipulation_trashes_and_gains_two_spice_apart() -> None:
    """ "[trash] AND ...[2 spice]": two printed icons, one action each in any
    order (OQ-027, imperium-base.md 15). The black trash icon is optional
    ([DI p. 16], [FAQ p. 3]); the spice icon is mandatory and needs another
    Bene Gesserit card in play (OQ-028)."""

    engine, state = _start()
    placed = _manipulation_placed(engine, state, bene_gesserit=True)
    assert _spice_icon(engine, placed)
    owner = placed.players[0]
    assert _trash_rows(engine, placed) >= {
        *owner.hand,
        "imperium:gene_manipulation:0",
        "imperium:bene_gesserit_initiate:0",
    }
    assert "finish_agent_turn" not in _ids(engine, placed)
    # Spice first, then the trash: neither waits for the other.
    gained = _do(engine, placed, "resolve_agent_card_effect", effect="spice")
    assert gained.players[0].resources.spice == owner.resources.spice + 2
    victim = owner.hand[0]
    trashed = _do(engine, gained, "trash_agent_card", card_id=victim)
    assert victim in trashed.players[0].trashed
    assert trashed.players[0].resources.spice == owner.resources.spice + 2
    assert not _trash_rows(engine, trashed)
    assert not _spice_icon(engine, trashed)


def test_gene_manipulation_without_another_bene_gesserit_gains_no_spice() -> None:
    engine, state = _start()
    placed = _manipulation_placed(engine, state, bene_gesserit=False)
    assert not _spice_icon(engine, placed)
    assert _trash_rows(engine, placed)
    # The trash is optional: the box is done once it is left unused.
    resolved = _do(engine, placed, "resolve_board_effect", effect="cards")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].trashed == placed.players[0].trashed
    assert finished.players[0].resources.spice == placed.players[0].resources.spice


def test_gene_manipulation_trashing_the_other_card_first_loses_the_spice() -> None:
    """ "조건은 해결할 때 판정한다(OQ-028)" (imperium-base.md 16, P0 sweep:
    "trashing the other BG card first loses the spice"): the Bond is read when
    the spice icon resolves, so the trash icon may break it first."""

    engine, state = _start()
    placed = _manipulation_placed(engine, state, bene_gesserit=True)
    trashed = _do(
        engine, placed, "trash_agent_card", card_id="imperium:bene_gesserit_initiate:0"
    )
    assert not _spice_icon(engine, trashed)


def test_gene_manipulation_may_trash_itself_and_still_gain_the_spice() -> None:
    """The card trashes itself by its own printed icon, so the other icon still
    pays out (imperium-base.md 16, OQ-022's own-effect case, OQ-027); the Bond
    asks for *another* Bene Gesserit card, which is still in play."""

    engine, state = _start()
    placed = _manipulation_placed(engine, state, bene_gesserit=True)
    me = "imperium:gene_manipulation:0"
    trashed = _do(engine, placed, "trash_agent_card", card_id=me)
    assert me in trashed.players[0].trashed
    assert _spice_icon(engine, trashed)
    gained = _do(engine, trashed, "resolve_agent_card_effect", effect="spice")
    assert gained.players[0].resources.spice == placed.players[0].resources.spice + 2


def test_gene_manipulation_reveals_two_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "gene_manipulation", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 2
    assert frame["sword_strength"] == 0


# --- Reverend Mother Mohiam -------------------------------------------------------


def test_reverend_mother_mohiam_matches_the_app_table() -> None:
    # App attribute table: cost 6, 1 copy, Emperor and Bene Gesserit, Emperor
    # and Bene Gesserit, Reveal 2 Persuasion and 2 spice (tags NamedCharacter,
    # WantBG).
    entry = IMPERIUM_CARDS_BY_ID["reverend_mother_mohiam"]
    assert entry.card.name == "Reverend Mother Mohiam"
    assert entry.acquisition_cost == 6
    assert entry.copies == 1
    assert entry.factions == (Faction.EMPEROR, Faction.BENE_GESSERIT)
    assert entry.agent_icons == (AgentIcon.EMPEROR, AgentIcon.BENE_GESSERIT)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_TWO_IF_BENE_GESSERIT_BOND
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:reverend_mother_mohiam:0") is entry


def _do_for(
    engine: UprisingRulesEngine,
    state: GameState,
    seat: int,
    action_id: str,
    **arguments: object,
) -> GameState:
    """``seat``'s own action (an opponent's window opened by seat 0's card)."""

    action = next(
        action
        for action in engine.whole_actions(state, seat)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )
    return apply_whole(engine, state, action).state


def _mohiam_played(
    engine: UprisingRulesEngine,
    state: GameState,
    hands: dict[int, tuple[str, ...]],
    *,
    bene_gesserit: bool = True,
) -> GameState:
    """Seat 0 sends Reverend Mother Mohiam to Secrets (a Bene Gesserit space,
    no cost) with, or without, another Bene Gesserit card in play, the
    opponents holding ``hands``; the box is resolved when the Bond holds."""

    held, _ = _with_card(state, "reverend_mother_mohiam")
    held = _seat(
        held,
        in_play=("imperium:bene_gesserit_initiate:0",) if bene_gesserit else (),
    )
    for seat, hand in hands.items():
        held = _seat(held, seat, hand=hand)
    return _place(engine, held, "secrets", "reverend_mother_mohiam")


_HAND = ("imperium:dr_yueh:0", "imperium:stilgar:0", "imperium:space_travel:0")


def test_reverend_mother_mohiam_each_opponent_discards_two_cards() -> None:
    """ "Mohiam | 상대가 버릴 카드를 고르고, 내 왼쪽부터 시계 방향" (imperium-base.md
    13.2, [FAQ p. 3]); OQ-118: two cards where the hand holds them, one where it
    holds one, and the opponent that has none confirms it discards nothing. The
    opponents are asked one after the other, the next seat first."""

    engine, state = _start()
    placed = _mohiam_played(
        engine,
        state,
        {1: _HAND, 2: ("imperium:space_travel:1",), 3: ()},
    )
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    top = resolved.decision_stack[-1]
    assert top.kind is FrameKind.OPPONENT_CARD_DISCARD
    assert top.decision.owner == 1  # type: ignore[union-attr]
    # Seat 1: two picks of its own, one card each.
    first = _do_for(engine, resolved, 1, "discard_opponent_card", card_id=_HAND[1])
    assert first.players[1].hand == (_HAND[0], _HAND[2])
    assert first.decision_stack[-1].decision.owner == 1  # type: ignore[union-attr]
    second = _do_for(engine, first, 1, "discard_opponent_card", card_id=_HAND[0])
    assert second.players[1].hand == (_HAND[2],)
    assert set(second.players[1].discard_pile) >= {_HAND[1], _HAND[0]}
    # Seat 2 holds one card: it discards it and is done.
    assert second.decision_stack[-1].decision.owner == 2  # type: ignore[union-attr]
    third = _do_for(
        engine, second, 2, "discard_opponent_card", card_id="imperium:space_travel:1"
    )
    assert third.players[2].hand == ()
    assert third.decision_stack[-1].decision.owner == 3  # type: ignore[union-attr]
    # Seat 3 holds none: its window opens and confirms there is nothing.
    done = _do_for(engine, third, 3, "resolve_opponent_discard_without_card")
    assert done.decision_stack[-1].kind is not FrameKind.OPPONENT_CARD_DISCARD
    assert done.players[0].hand == placed.players[0].hand


def test_reverend_mother_mohiam_opponent_with_two_cards_loses_them_both() -> None:
    engine, state = _start()
    two = _HAND[:2]
    placed = _mohiam_played(engine, state, {1: two, 2: (), 3: ()})
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    first = _do_for(engine, resolved, 1, "discard_opponent_card", card_id=two[0])
    second = _do_for(engine, first, 1, "discard_opponent_card", card_id=two[1])
    assert second.players[1].hand == ()
    assert second.decision_stack[-1].decision.owner == 2  # type: ignore[union-attr]


def test_reverend_mother_mohiam_without_another_bene_gesserit_does_nothing() -> None:
    """The Bond opens the box at the placement (OQ-028): alone, Mohiam makes no
    opponent discard, and the turn goes on."""

    engine, state = _start()
    placed = _mohiam_played(
        engine, state, {1: _HAND, 2: _HAND, 3: _HAND}, bene_gesserit=False
    )
    assert "resolve_agent_card_effect" not in _ids(engine, placed)
    assert placed.decision_stack[-1].kind is not FrameKind.OPPONENT_CARD_DISCARD
    assert all(placed.players[seat].hand == _HAND for seat in (1, 2, 3))


def test_reverend_mother_mohiam_condition_is_judged_when_it_resolves() -> None:
    """ "조건은 해결할 때 판정한다(OQ-028)" (imperium-base.md 16): with the other
    Bene Gesserit card gone from play before the box resolves, no opponent is
    asked."""

    engine, state = _start()
    placed = _mohiam_played(engine, state, {1: _HAND, 2: _HAND, 3: _HAND})
    initiate = "imperium:bene_gesserit_initiate:0"
    remaining = tuple(card for card in placed.players[0].in_play if card != initiate)
    gone = _seat(placed, in_play=remaining)
    assert "resolve_agent_card_effect" not in _ids(engine, gone)


def test_reverend_mother_mohiam_reveals_two_persuasion_and_two_spice() -> None:
    engine, state = _start()
    held, _ = _with_card(state, "reverend_mother_mohiam", alone=True)
    held = _seat(held, resources=Resources())
    revealed = _do(engine, held, "reveal_turn")
    frame = dict(revealed.decision_stack[-1].context)
    assert (frame["persuasion"], frame["sword_strength"]) == (2, 0)
    gained = _do(engine, revealed, "gain_reveal_resources")
    assert gained.players[0].resources.spice == 2


# --- Liet Kynes -------------------------------------------------------------------


def test_liet_kynes_matches_the_app_table() -> None:
    # App attribute table: cost 5, 1 copy, Emperor and Fremen, Fremen and City,
    # no fixed Reveal values, AcquireEffect RankE (one Emperor Influence).
    entry = IMPERIUM_CARDS_BY_ID["liet_kynes_card"]
    assert entry.card.name == "Liet Kynes"
    assert entry.acquisition_cost == 5
    assert entry.copies == 1
    assert entry.factions == (Faction.EMPEROR, Faction.FREMEN)
    assert entry.agent_icons == (AgentIcon.FREMEN, AgentIcon.CITY)
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.has_acquisition_bonus
    assert entry.acquisition_effect is (
        PersonalCardAcquisitionEffect.GAIN_EMPEROR_INFLUENCE
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:liet_kynes_card:0") is entry


def test_liet_kynes_agent_box_is_empty() -> None:
    # P0 sweep: "AGENT: none"; the icons only send the Agent to a Fremen or City
    # space.
    engine, state = _start()
    state, _ = _with_card(state, "liet_kynes_card")
    state = _seat(state, resources=Resources(water=2))
    placed = _place(engine, state, "imperium_research_station", "liet_kynes_card")
    assert "resolve_agent_card_effect" not in _ids(engine, placed)


def _liet_persuasion(
    engine: UprisingRulesEngine,
    state: GameState,
    *others: str,
    in_play: tuple[str, ...] = (),
) -> object:
    """The Persuasion Liet Kynes and ``others`` reveal, with ``in_play`` the
    cards played on this round's Agent turns."""

    held, instance = _with_card(state, "liet_kynes_card", alone=True)
    held = _seat(held, hand=(instance, *others), in_play=in_play)
    return dict(_do(engine, held, "reveal_turn").decision_stack[-1].context)[
        "persuasion"
    ]


def test_liet_kynes_counts_two_persuasion_for_each_fremen_card_in_play() -> None:
    """ "Liet Kynes | 이번 라운드 Agent turn의 카드와 지금 Reveal turn의 카드를 센다;
    장마다 Persuasion 2" (imperium-base.md 13.2, [FAQ p. 2]); the card counts
    itself ("including this one"): alone it is one Fremen card."""

    engine, state = _start()
    assert _liet_persuasion(engine, state) == 2


def test_liet_kynes_counts_the_other_fremen_cards_revealed() -> None:
    """Spice Hunter (Fremen) revealed beside it: two Fremen cards, 4
    Persuasion, and the hunter's own 1."""

    engine, state = _start()
    assert _liet_persuasion(engine, state, "imperium:spice_hunter:0") == 4 + 1
    # A card of another Faction adds nothing to the count.
    assert _liet_persuasion(engine, state, "imperium:space_travel:0") == 2 + 2


def test_liet_kynes_counts_this_rounds_agent_turn_cards() -> None:
    """The card an Agent turn of this round played is in play for the count
    ([FAQ p. 2])."""

    engine, state = _start()
    played = ("imperium:stilgar:0", "imperium:space_travel:0")
    assert _liet_persuasion(engine, state, in_play=played) == 2 * 2


def test_liet_kynes_acquisition_gains_one_emperor_influence() -> None:
    """ "AcquireEffect RankE" (app table): buying the card gives 1 Emperor
    Influence, once."""

    engine, state = _start()
    liet = "imperium:liet_kynes_card:0"
    others = tuple(card for card in state.imperium_row if card != liet)
    row = (liet, *others[:4])
    stocked = replace(
        state,
        imperium_row=row,
        imperium_deck=tuple(card for card in state.imperium_deck if card != liet),
    )
    hand = ("imperium:space_travel:0", "imperium:stilgar:0", "imperium:dr_yueh:0")
    held = _seat(stocked, hand=hand, resources=Resources())
    revealed = _do(engine, held, "reveal_turn")
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2 + 2 + 1
    before = revealed.players[0]
    bought = _do(engine, revealed, "acquire_imperium", instance_id=liet)
    after = bought.players[0]
    assert liet in after.discard_pile
    assert after.influence.emperor == before.influence.emperor + 1
    assert after.influence.fremen == before.influence.fremen


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
        imperium_deck=tuple(card for card in held.imperium_deck if card != instance),
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
    """ "The acquisition bonus is paid once, when acquired" [DI p. 16]; its four
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

    revealed = _buyer_revealed(engine, state, "lady_jessica_card", influence=influence)
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


# --- Guild Bankers ----------------------------------------------------------------

TSMF = "imperium_the_spice_must_flow"


def test_guild_bankers_matches_the_app_table() -> None:
    # App attribute table: cost 3, 1 copy, Spacing Guild, Emperor, Spacing
    # Guild and Landsraad, no fixed Reveal values; no Agent effect.
    entry = IMPERIUM_CARDS_BY_ID["guild_bankers"]
    assert entry.card.name == "Guild Bankers"
    assert entry.acquisition_cost == 3
    assert entry.copies == 1
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.LANDSRAAD,
    )
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:guild_bankers:0") is entry


def test_guild_bankers_agent_box_is_empty() -> None:
    # P0 sweep: "AGENT: none"; the icons only send the Agent to an Emperor,
    # Spacing Guild or Landsraad space.
    engine, state = _start()
    state, _ = _with_card(state, "guild_bankers")
    placed = _place(engine, state, "wealth", "guild_bankers")
    assert "resolve_agent_card_effect" not in _ids(engine, placed)


# Persuasion 12 beside the card: Piter De Vries 3, Stilgar 2, Space Travel 2
# twice, Dr. Yueh 1, Bene Gesserit Initiate 1, Opulence 1 (the printed values;
# none of them gains anything that must be taken before the Reveal ends).
_BANKERS_HAND = (
    "imperium:guild_bankers:0",
    "imperium:piter_de_vries_card:0",
    "imperium:stilgar:0",
    "imperium:space_travel:0",
    "imperium:space_travel:1",
    "imperium:dr_yueh:0",
    "imperium:bene_gesserit_initiate:0",
    "imperium:opulence:0",
)


def _bankers_revealed(
    engine: UprisingRulesEngine,
    state: GameState,
    hand: tuple[str, ...] = _BANKERS_HAND,
    in_play: tuple[str, ...] = (),
) -> GameState:
    """Seat 0 reveals ``hand`` (the bankers and 12 Persuasion by default)."""

    held = _seat(state, hand=hand, resources=Resources(), in_play=in_play)
    return _do(engine, held, "reveal_turn")


def _reserve_cost(state: GameState) -> int:
    from dune_imperium.rules.acquisition import reserve_cost

    return reserve_cost(state, TSMF)


def test_guild_bankers_reveal_lowers_the_spice_must_flow_by_three() -> None:
    """ "Guild Bankers | 2 | 이번 turn에 얻는 The Spice Must Flow마다 할인"
    (imperium-base.md 13.2, [FAQ p. 2]); the card prints "The Spice Must Flow
    costs 3 Persuasion less to acquire this turn", and the Reserve card costs 9
    (``imperium.reserve``): 6 in the Reveal turn."""

    engine, state = _start()
    assert _reserve_cost(state) == 9
    revealed = _bankers_revealed(engine, state)
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 12
    assert _reserve_cost(revealed) == 6
    # Not a cost it keeps: the Reveal over, the card costs 9 again.
    finished = _do(engine, revealed, "finish_reveal")
    assert _reserve_cost(finished) == 9


def test_guild_bankers_discount_makes_the_card_buyable_with_six() -> None:
    """With 6 Persuasion the card is offered only beside Guild Bankers (9
    Persuasion otherwise); the payment is the lowered cost."""

    engine, state = _start()
    six = ("imperium:piter_de_vries_card:0", "imperium:stilgar:0", "imperium:dr_yueh:0")
    plain = _bankers_revealed(engine, state, six)
    assert dict(plain.decision_stack[-1].context)["persuasion"] == 6
    assert ("acquire_reserve", TSMF) not in {
        (action.action_id, dict(action.arguments).get("card_id"))
        for action in _wholes(engine, plain)
    }
    with_bankers = _bankers_revealed(engine, state, ("imperium:guild_bankers:0", *six))
    assert dict(with_bankers.decision_stack[-1].context)["persuasion"] == 6
    bought = _do(engine, with_bankers, "acquire_reserve", card_id=TSMF)
    assert dict(bought.decision_stack[-1].context)["persuasion"] == 0
    discard = bought.players[0].discard_pile
    assert any(card.startswith(f"reserve:{TSMF}:") for card in discard)
    # The Victory Point the card gives when acquired ([FAQ p. 4]) is unchanged.
    gained = bought.players[0].victory_points - with_bankers.players[0].victory_points
    assert gained == 1
    # Market Opening's once-a-round flag is not the bankers' to set.
    assert not bought.scouts_discount_used


def test_guild_bankers_discount_holds_for_each_copy_bought() -> None:
    """ "마다": every copy acquired this turn costs 3 less, not the first only:
    12 Persuasion buys two at 6 each."""

    engine, state = _start()
    revealed = _bankers_revealed(engine, state)
    first = _do(engine, revealed, "acquire_reserve", card_id=TSMF)
    assert dict(first.decision_stack[-1].context)["persuasion"] == 6
    second = _do(engine, first, "acquire_reserve", card_id=TSMF)
    assert dict(second.decision_stack[-1].context)["persuasion"] == 0
    discard = second.players[0].discard_pile
    assert len([card for card in discard if f":{TSMF}:" in card]) == 2


def test_guild_bankers_played_as_an_agent_gives_no_discount() -> None:
    """The discount is the card's Reveal effect: the card in play from an
    earlier Agent turn does not lower the cost (its Agent box is empty)."""

    engine, state = _start()
    rest = _BANKERS_HAND[1:]
    revealed = _bankers_revealed(
        engine, state, rest, in_play=("imperium:guild_bankers:0",)
    )
    assert _reserve_cost(revealed) == 9


def test_guild_bankers_reveal_text_names_the_discount() -> None:
    line = reveal_lines(IMPERIUM_CARDS_BY_ID["guild_bankers"])[0]
    assert reveal_effect_text(line) == (
        "The Spice Must Flow costs 3 Persuasion less to acquire this turn"
    )
    korean = reveal_effect_text_ko(line)
    assert "{persuasion:3}" in korean
    assert "스파이스는 흘러야 한다" in korean


# --- Carryall ---------------------------------------------------------------------


def test_carryall_matches_the_app_table() -> None:
    # App attribute table: cost 5, 1 copy, no Faction, Spice Trade, Reveal 1
    # Persuasion and 1 spice.
    entry = IMPERIUM_CARDS_BY_ID["carryall"]
    assert entry.card.name == "Carryall"
    assert entry.acquisition_cost == 5
    assert entry.copies == 1
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.agent_effect is PersonalCardAgentEffect.DOUBLE_BASE_HARVEST_SPICE
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:carryall:0") is entry


def _carryall_harvest(
    space_id: str,
    water: int,
    *,
    bonus: int = 2,
    carryall: bool = True,
    leader: str | None = None,
) -> tuple[GameState, GameState]:
    """Seat 0 sends Carryall (or Spice Hunter, a Spice Trade card with no box) to
    the Maker space with ``bonus`` spice on it and harvests; returns the
    state before the harvest and after."""

    engine, state = _start()
    card = "carryall" if carryall else "spice_hunter"
    state, _ = _with_card(state, card)
    state = _seat(state, resources=Resources(water=water))
    if leader is not None:
        state = _seat(state, leader_id=leader, leader_face_id=leader)
    state = replace(
        state,
        maker_bonus_spice=tuple(
            (maker, bonus if maker == space_id else other)
            for maker, other in state.maker_bonus_spice
        ),
    )
    placed = _place(engine, state, space_id, card)
    return placed, _do(engine, placed, "harvest_maker_spice")


def _spice_gained(placed: GameState, harvested: GameState) -> int:
    return harvested.players[0].resources.spice - placed.players[0].resources.spice


def test_carryall_has_no_box_to_resolve() -> None:
    """The doubling is a modifier of the harvest, not a step of its own: the
    box never opens, so nothing waits for the owner (``AbilityMark.AUTOMATIC``)
    and the turn can end once the harvest is taken."""

    engine, state = _start()
    state, _ = _with_card(state, "carryall")
    placed = _place(engine, state, "imperial_basin", "carryall")
    assert "resolve_agent_card_effect" not in _ids(engine, placed)
    assert "harvest_maker_spice" in _ids(engine, placed)


def test_carryall_doubles_the_base_spice_not_the_bonus() -> None:
    """ "Carryall | 1 | 기본 spice: Imperial Basin 1, Hagga Basin 2, The Great Flat
    3" (imperium-base.md 13.2, [FAQ p. 1]); the card doubles the base, never the
    bonus spice the space has gathered: base 1/2/3 doubled to 2/4/6, beside a
    bonus of 2."""

    for space_id, water, base in (
        ("imperial_basin", 0, 1),
        ("imperium_hagga_basin", 1, 2),
        ("the_great_flat", 2, 3),
    ):
        placed, harvested = _carryall_harvest(space_id, water)
        assert _spice_gained(placed, harvested) == 2 * base + 2, space_id
        # The bonus is collected whatever the doubling.
        assert dict(harvested.maker_bonus_spice)[space_id] == 0


def test_a_plain_spice_trade_card_harvests_the_printed_base() -> None:
    """The control for the doubling: any other Spice Trade card at the same
    spaces takes the printed base and the bonus (here Hagga Basin: 2 + 2)."""

    placed, harvested = _carryall_harvest("imperium_hagga_basin", 1, carryall=False)
    assert _spice_gained(placed, harvested) == 2 + 2


def test_carryall_does_nothing_off_a_harvest() -> None:
    """ "Nothing at Secure Contract or Sell Melange" (P0 sweep, merged
    effect): the card at Secure Contract gains its 3 Solari and no spice."""

    engine, state = _start()
    state, _ = _with_card(state, "carryall")
    state = _seat(state, resources=Resources())
    placed = _place(engine, state, "secure_contract", "carryall")
    resolved = _do(engine, placed, "resolve_board_effect", effect="resources")
    assert resolved.players[0].resources == Resources(solari=3)


def test_carryall_leaves_the_control_bonus_alone() -> None:
    """The Imperial Basin control bonus is not a harvest (P0 sweep): its
    controller takes the printed 1 spice [DI p. 10], not a doubled one."""

    engine, state = _start()
    state, _ = _with_card(state, "carryall")
    state = _seat(state, 1, control_space_ids=("imperial_basin",))
    spice = state.players[1].resources.spice
    placed = _place(engine, state, "imperial_basin", "carryall")
    assert placed.players[1].resources.spice == spice + 1


def test_carryall_doubles_before_spice_addict_takes_one_less() -> None:
    """ "Countess Ariana의 −1은 Carryall·Thumper로 두 배를 한 뒤 harvest 전체에서
    한 번 뺀다" (imperium-base.md 16): Hagga Basin's base 2 doubled to 4, less 1,
    plus the bonus 2 -- 5, not 2*(2-1)+2 = 4."""

    placed, harvested = _carryall_harvest(
        "imperium_hagga_basin", 1, leader="countess_ariana_thorvald"
    )
    assert _spice_gained(placed, harvested) == (2 * 2 - 1) + 2


def test_carryall_reveal_gains_one_persuasion_and_one_spice() -> None:
    engine, state = _start()
    held, instance = _with_card(state, "carryall", alone=True)
    held = _seat(held, hand=(instance,), resources=Resources())
    revealed = _do(engine, held, "reveal_turn")
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 1
    gained = _do(engine, revealed, "gain_reveal_resources", printed="carryall")
    assert gained.players[0].resources.spice == 1


def test_carryall_text_names_the_doubling() -> None:
    from dune_imperium.display.tokens import AGENT_EFFECT_TEXT
    from dune_imperium.display.tokens_ko import AGENT_EFFECT_TEXT_KO

    effect = PersonalCardAgentEffect.DOUBLE_BASE_HARVEST_SPICE
    assert AGENT_EFFECT_TEXT[effect] == (
        "Double the base (not bonus) spice you harvest with this Agent"
    )
    assert "{spice}" in AGENT_EFFECT_TEXT_KO[effect]


# --- Power Play -------------------------------------------------------------------


def test_power_play_matches_the_app_table() -> None:
    # App attribute table: cost 5, 3 copies, no Faction, the four Faction
    # icons, no Reveal values.
    entry = IMPERIUM_CARDS_BY_ID["power_play"]
    assert entry.card.name == "Power Play"
    assert entry.acquisition_cost == 5
    assert entry.copies == 3
    assert entry.factions == ()
    assert entry.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert entry.agent_effect is (
        PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:power_play:2") is entry


def _power_play_placed(
    engine: UprisingRulesEngine, state: GameState, space_id: str = "wealth"
) -> GameState:
    held, _ = _with_card(state, "power_play")
    held = _seat(held, influence=Influence(), resources=Resources(water=1, spice=2))
    return _place(engine, held, space_id, "power_play")


def test_power_play_gives_two_influence_instead_of_the_spaces_one() -> None:
    """ "Gain two Influence instead of one." (card); "Power Play의 두 문장은 별개
    효과; Agent box는 Faction 칸에 보냈을 때만" and the box takes the shape of
    Subversive Advisor's (imperium-base.md 13.3, OQ-022's 2026-10-06
    reinforcement): the waiting box holds the space's own 1, so the space gives
    2 in all, never 3. One step of the owner's: the two Influence, then the
    card trashes itself."""

    engine, state = _start()
    for space_id, faction in (
        ("wealth", "emperor"),
        ("foldspace", "spacing_guild"),
        ("secrets", "bene_gesserit"),
        ("stillsuits", "fremen"),
    ):
        placed = _power_play_placed(engine, state, space_id)
        ids = _ids(engine, placed)
        assert "resolve_agent_card_effect" in ids, space_id
        assert "resolve_faction_influence" not in ids, space_id
        resolved = _do(engine, placed, "resolve_agent_card_effect")
        after = resolved.players[0]
        assert getattr(after.influence, faction) == 2, space_id
        # The space's own Influence was the box's to give; it does not come
        # again (a third point).
        assert "resolve_faction_influence" not in _ids(engine, resolved), space_id
        me = "imperium:power_play:0"
        assert me in after.trashed and me not in after.in_play, space_id


def test_power_play_trash_is_not_a_choice() -> None:
    """ "Trash this card" is mandatory [FAQ p. 3] (imperium-base.md 11): the
    box has no refusal, and the turn cannot end with the card still waiting."""

    engine, state = _start()
    placed = _power_play_placed(engine, state)
    ids = _ids(engine, placed)
    assert not {action_id for action_id in ids if action_id.startswith("decline_")}
    assert "finish_agent_turn" not in ids


def test_power_play_two_influence_pass_the_victory_point_once() -> None:
    """Both points are one effect that cannot be cut ("두 진영 Influence를 한꺼번에
    올리는 효과는 끊을 수 없는 한 효과", imperium-base.md 13.3): from 1 to 3
    Emperor Influence the 2-Influence Victory Point is gained once [DI p. 7]."""

    engine, state = _start()
    held, _ = _with_card(state, "power_play")
    held = _seat(
        held, influence=Influence(emperor=1), resources=Resources(water=1, spice=2)
    )
    placed = _place(engine, held, "wealth", "power_play")
    before = placed.players[0].victory_points
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    assert resolved.players[0].influence.emperor == 3
    assert resolved.players[0].victory_points == before + 1


def test_power_play_trashed_by_another_effect_leaves_the_spaces_influence() -> None:
    """ "다른 수단으로 먼저 trash하면 남은 효과는 없다" (imperium-base.md 16,
    OQ-022): another effect trashed the card before its box resolved, so the
    box expires; only the card's "instead" lapses, the space's own Influence
    is the board's rule and comes back ([Main p. 7])."""

    engine, state = _start()
    placed = _power_play_placed(engine, state)
    me = "imperium:power_play:0"
    owner = placed.players[0]
    lowered = _seat(
        placed,
        in_play=tuple(card for card in owner.in_play if card != me),
        trashed=(*owner.trashed, me),
    )
    expired = expire_trashed_card_effects(RuleResult(state=lowered)).state
    assert "resolve_agent_card_effect" not in _ids(engine, expired)
    assert "resolve_faction_influence" in _ids(engine, expired)
    gained = _do(engine, expired, "resolve_faction_influence")
    assert gained.players[0].influence.emperor == 1


def test_power_play_text_is_the_printed_pair_of_effects() -> None:
    from dune_imperium.display.tokens import AGENT_EFFECT_TEXT

    assert (
        AGENT_EFFECT_TEXT[
            PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF
        ]
        == "Gain 2 Influence with the visited Faction, Trash this card"
    )


# --- Test of Humanity -------------------------------------------------------------


def test_test_of_humanity_matches_the_app_table() -> None:
    # App attribute table: cost 3, 1 copy, Bene Gesserit, Bene Gesserit,
    # Landsraad and City, Reveal 2 Persuasion.
    entry = IMPERIUM_CARDS_BY_ID["test_of_humanity"]
    assert entry.card.name == "Test of Humanity"
    assert entry.acquisition_cost == 3
    assert entry.copies == 1
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (
        AgentIcon.BENE_GESSERIT,
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
    )
    assert entry.agent_effect is (
        PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_OR_LOSES_DEPLOYED_TROOP
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:test_of_humanity:0") is entry


def _humanity_played(
    engine: UprisingRulesEngine,
    state: GameState,
    seats: dict[int, tuple[tuple[str, ...], int]],
) -> GameState:
    """Seat 0 sends Test of Humanity to Hall of Oratory (a Landsraad space, no
    cost) and resolves its box; ``seats`` gives each opponent's hand and
    number of troops in the Conflict (the strength they make is its 2 each)."""

    held, _ = _with_card(state, "test_of_humanity")
    for seat, (hand, deployed) in seats.items():
        held = _seat(
            held,
            seat,
            hand=hand,
            troops_garrison=3 - deployed,
            troops_conflict=deployed,
            combat_strength=2 * deployed,
        )
    placed = _place(engine, held, "hall_of_oratory", "test_of_humanity")
    return _do(engine, placed, "resolve_agent_card_effect")


def _window_rows(
    engine: UprisingRulesEngine, state: GameState, seat: int
) -> set[tuple[str, tuple[tuple[str, object], ...]]]:
    return {
        (action.action_id, action.arguments)
        for action in engine.whole_actions(state, seat)
    }


def test_test_of_humanity_each_opponent_chooses_what_it_can_do() -> None:
    """ "상대는 내 왼쪽부터 시계 방향으로 고른다. 각자 할 수 있는 것을 골라야 한다
    (손이 비면 버리기 불가, 배치한 troop이 없으면 잃기 불가). 버리는 상대가 카드를
    고른다(무작위 아님)" (imperium-base.md 13.1, [DI p. 13]); "discard ...는 손의
    카드" ([FAQ p. 4], 13.2). Seat 1 holds cards and a deployed troop: both
    halves are offered; seat 2 a hand only: the discard alone; seat 3 a
    deployed troop only: the loss alone."""

    engine, state = _start()
    hand = ("imperium:dr_yueh:0", "imperium:stilgar:0")
    resolved = _humanity_played(
        engine,
        state,
        {1: (hand, 1), 2: (("imperium:space_travel:0",), 0), 3: ((), 2)},
    )
    top = resolved.decision_stack[-1]
    assert top.kind is FrameKind.OPPONENT_CARD_DISCARD
    assert top.decision.owner == 1  # type: ignore[union-attr]
    rows = _window_rows(engine, resolved, 1)
    assert rows == {
        ("discard_opponent_card", (("card_id", hand[0]),)),
        ("discard_opponent_card", (("card_id", hand[1]),)),
        ("lose_unit", (("zone", "conflict"),)),
    }
    # Seat 1 discards a card of its own choosing; its troop stays.
    first = _do_for(engine, resolved, 1, "discard_opponent_card", card_id=hand[1])
    assert first.players[1].hand == (hand[0],)
    assert hand[1] in first.players[1].discard_pile
    assert first.players[1].troops_conflict == 1
    # Seat 2 has no deployed troop: only its discard.
    assert first.decision_stack[-1].decision.owner == 2  # type: ignore[union-attr]
    assert _window_rows(engine, first, 2) == {
        ("discard_opponent_card", (("card_id", "imperium:space_travel:0"),))
    }
    second = _do_for(
        engine, first, 2, "discard_opponent_card", card_id="imperium:space_travel:0"
    )
    assert second.players[2].hand == ()
    # Seat 3 has no card: only the loss of a deployed troop, to the supply.
    assert second.decision_stack[-1].decision.owner == 3  # type: ignore[union-attr]
    assert _window_rows(engine, second, 3) == {("lose_unit", (("zone", "conflict"),))}
    third = _do_for(engine, second, 3, "lose_unit", zone="conflict")
    seat3 = third.players[3]
    assert (seat3.troops_conflict, seat3.troops_garrison, seat3.troops_supply) == (
        1,
        1,
        second.players[3].troops_supply + 1,
    )
    # Its strength follows the troop out of the Conflict.
    assert seat3.combat_strength == 2
    assert third.decision_stack[-1].kind is not FrameKind.OPPONENT_CARD_DISCARD


def test_test_of_humanity_loses_a_troop_instead_of_discarding() -> None:
    """An opponent holding both may take the loss instead: the card stays in
    hand, the troop leaves the Conflict for the supply."""

    engine, state = _start()
    hand = ("imperium:dr_yueh:0",)
    resolved = _humanity_played(engine, state, {1: (hand, 2), 2: ((), 0), 3: ((), 0)})
    lost = _do_for(engine, resolved, 1, "lose_unit", zone="conflict")
    seat = lost.players[1]
    assert seat.hand == hand and seat.discard_pile == ()
    assert (seat.troops_conflict, seat.combat_strength) == (1, 2)
    assert seat.troops_supply == resolved.players[1].troops_supply + 1


def test_test_of_humanity_never_offers_a_garrisoned_troop() -> None:
    """Only a deployed troop is lost ("Lose a deployed troop"): an opponent
    with troops in the garrison alone and no cards has nothing to choose and
    confirms it ("with neither possible, nothing", P0 sweep, [DI p. 13])."""

    engine, state = _start()
    resolved = _humanity_played(engine, state, {1: ((), 0), 2: ((), 0), 3: ((), 0)})
    assert resolved.players[1].troops_garrison == 3
    assert _window_rows(engine, resolved, 1) == {
        ("resolve_opponent_discard_without_card", ())
    }
    done = _do_for(engine, resolved, 1, "resolve_opponent_discard_without_card")
    assert done.players[1].troops_garrison == 3
    assert done.players[1].troops_supply == resolved.players[1].troops_supply
    assert done.decision_stack[-1].decision.owner == 2  # type: ignore[union-attr]


def _greyed(
    engine: UprisingRulesEngine, state: GameState, seat: int
) -> set[tuple[str, str]]:
    """The (action id, reason code) of each row the page greys out for ``seat``."""

    found = unavailable_choices(state, seat, engine.whole_actions(state, seat))
    if found is None:
        return set()
    rows = cast("list[dict[str, Any]]", found["rows"])
    return {(row["action"]["action_id"], row["code"]) for row in rows}


def test_test_of_humanity_window_greys_out_what_cannot_be_done() -> None:
    """The page shows each half that cannot be done greyed out, with its reason
    (``display.unavailable``); the confirm is the only legal row of a seat with
    neither."""

    engine, state = _start()
    hand = ("imperium:dr_yueh:0",)
    resolved = _humanity_played(engine, state, {1: (hand, 0), 2: ((), 1), 3: ((), 0)})
    assert _greyed(engine, resolved, 1) == {("lose_unit", "no_unit")}
    after = _do_for(engine, resolved, 1, "discard_opponent_card", card_id=hand[0])
    assert _greyed(engine, after, 2) == {("discard_opponent_card", "no_card")}
    both_missing = _do_for(engine, after, 2, "lose_unit", zone="conflict")
    assert _greyed(engine, both_missing, 3) == {
        ("discard_opponent_card", "no_card"),
        ("lose_unit", "no_unit"),
    }
    assert _window_rows(engine, both_missing, 3) == {
        ("resolve_opponent_discard_without_card", ())
    }


def test_test_of_humanity_reveals_two_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "test_of_humanity", alone=True)
    frame = _reveal(engine, state)
    assert frame["persuasion"] == 2
    assert frame["sword_strength"] == 0


def test_test_of_humanity_text_names_the_choice() -> None:
    from dune_imperium.display.tokens import AGENT_EFFECT_TEXT
    from dune_imperium.display.tokens_ko import AGENT_EFFECT_TEXT_KO

    effect = PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_OR_LOSES_DEPLOYED_TROOP
    assert AGENT_EFFECT_TEXT[effect] == (
        "Each opponent chooses: Discard a card -OR- Lose a deployed troop"
    )
    assert "{discard}" in AGENT_EFFECT_TEXT_KO[effect]


# --- Sardaukar Legion, Scout and Chani: troops moved by count ---------------------
#
# "Deploy up to three troops from your garrison to the Conflict" (Legion),
# "Retreat up to two of your troops" (Scout), "Retreat any number of your
# troops" (Chani): the owner picks the count, and "up to" / "any number" allow
# 0 [FAQ p. 3] (imperium-base.md 13.2: "Chani (Imperium) -> Retreat | 'any
# number'는 0 가능"); a retreat goes to the garrison [DI p. 16]; troops only (the
# original game has no Sardaukar Commander, P7 decides whether one counts).


def _counts(engine: UprisingRulesEngine, state: GameState, action_id: str) -> set[int]:
    """The counts the Reveal frame offers as ``action_id``."""

    return {
        int(dict(action.arguments)["count"])
        for action in _wholes(engine, state)
        if action.action_id == action_id
    }


def _revealed_alone(
    engine: UprisingRulesEngine,
    state: GameState,
    card_id: str,
    *,
    garrison: int,
    conflict: int = 0,
    copies: int = 1,
) -> GameState:
    """Seat 0 reveals ``copies`` of ``card_id`` and nothing else, holding that
    many troops in the garrison and the Conflict."""

    held = _with_troops(state, 0, garrison, conflict)
    hand = tuple(f"imperium:{card_id}:{copy}" for copy in range(copies))
    held = _seat(held, hand=hand, resources=Resources())
    return _do(engine, held, "reveal_turn")


# --- Sardaukar Legion


def test_sardaukar_legion_matches_the_app_table() -> None:
    # App attribute table: cost 5, 2 copies, Emperor, Emperor and Landsraad,
    # Reveal 1 Persuasion; AgentTroops 2.
    entry = IMPERIUM_CARDS_BY_ID["sardaukar_legion"]
    assert entry.card.name == "Sardaukar Legion"
    assert entry.acquisition_cost == 5
    assert entry.copies == 2
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == (AgentIcon.EMPEROR, AgentIcon.LANDSRAAD)
    assert entry.agent_effect is PersonalCardAgentEffect.RECRUIT_TWO_TROOPS
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_DEPLOY_UP_TO_THREE_TROOPS,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:sardaukar_legion:1") is entry


def test_sardaukar_legion_recruits_two_troops_that_stay_in_the_garrison() -> None:
    """Agent "[2 troops]"; "Emperor and Landsraad spaces are not Combat spaces"
    (P0 sweep, imperium-base.md 7): the two stay in the garrison."""

    engine, state = _start()
    state, _ = _with_card(state, "sardaukar_legion")
    garrison = state.players[0].troops_garrison
    placed = _place(engine, state, "wealth", "sardaukar_legion")
    resolved = _do(engine, placed, "resolve_agent_card_effect")
    after = resolved.players[0]
    assert after.troops_garrison == garrison + 2
    assert after.troops_conflict == 0
    assert not legal_combat_deployments(resolved, 0)


def test_sardaukar_legion_deploys_up_to_three_troops_by_count() -> None:
    """ "Deploy up to three troops from your garrison to the Conflict" [Sardaukar
    Legion card]: one row for each count the garrison allows, 1 to 3; three
    troops make 6 strength and the printed Persuasion is 1."""

    engine, state = _start()
    revealed = _revealed_alone(engine, state, "sardaukar_legion", garrison=5)
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 1
    assert _counts(engine, revealed, "deploy_reveal_card_troops") == {1, 2, 3}
    deployed = _do(engine, revealed, "deploy_reveal_card_troops", count=3)
    after = deployed.players[0]
    assert (after.troops_garrison, after.troops_conflict) == (2, 3)
    assert after.combat_strength == 6
    # The choice is used up.
    assert "deploy_reveal_card_troops" not in _ids(engine, deployed)
    finished = _do(engine, deployed, "finish_reveal")
    assert finished.players[0].combat_strength == 6


def test_sardaukar_legion_deploys_only_what_the_garrison_holds() -> None:
    engine, state = _start()
    revealed = _revealed_alone(engine, state, "sardaukar_legion", garrison=2)
    assert _counts(engine, revealed, "deploy_reveal_card_troops") == {1, 2}
    one = _do(engine, revealed, "deploy_reveal_card_troops", count=1)
    assert (one.players[0].troops_garrison, one.players[0].troops_conflict) == (1, 1)
    empty = _revealed_alone(engine, state, "sardaukar_legion", garrison=0)
    assert _counts(engine, empty, "deploy_reveal_card_troops") == set()
    assert "finish_reveal" in _ids(engine, empty)


def test_sardaukar_legion_may_deploy_none() -> None:
    """ "Up to" allows none [FAQ p. 3]: no refusal is offered (OQ-095 (7)); the
    owner who deploys nothing ends the Reveal and the choice lapses."""

    engine, state = _start()
    revealed = _revealed_alone(engine, state, "sardaukar_legion", garrison=3)
    assert not {a for a in _ids(engine, revealed) if a.startswith("decline_")}
    finished = _do(engine, revealed, "finish_reveal")
    after = finished.players[0]
    assert (after.troops_garrison, after.troops_conflict) == (3, 0)
    assert after.combat_strength == 0


def test_sardaukar_legion_deployed_troops_count_for_the_turn() -> None:
    """Troops deployed by a Reveal card are deployed this turn (OQ-115: the
    Baron's Masterstroke counts them)."""

    engine, state = _start()
    revealed = _revealed_alone(engine, state, "sardaukar_legion", garrison=4)
    deployed = _do(engine, revealed, "deploy_reveal_card_troops", count=3)
    assert deployed.players[0].units_deployed_turn == 3


def test_sardaukar_legion_text_names_the_count() -> None:
    effect = PersonalCardRevealChoiceEffect.MAY_DEPLOY_UP_TO_THREE_TROOPS
    assert REVEAL_CHOICE_EFFECT_TEXT[effect] == (
        "You may deploy up to 3 troops from your garrison to the Conflict"
    )
    assert "{troop:3}" in REVEAL_CHOICE_EFFECT_TEXT_KO[effect]


# --- Scout


def test_scout_matches_the_app_table() -> None:
    # App attribute table: cost 1, 2 copies, no Faction, City and Spice Trade,
    # Reveal 1 Persuasion and 1 sword.
    entry = IMPERIUM_CARDS_BY_ID["scout"]
    assert entry.card.name == "Scout"
    assert entry.acquisition_cost == 1
    assert entry.copies == 2
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_UP_TO_TWO_TROOPS,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:scout:1") is entry


def test_scout_agent_box_is_empty() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "scout")
    placed = _place(engine, state, "secure_contract", "scout")
    assert "resolve_agent_card_effect" not in _ids(engine, placed)


def test_scout_retreats_up_to_two_troops_to_the_garrison() -> None:
    """ "Retreat up to two of your troops" [Scout card]; the retreat goes to the
    garrison [DI p. 16]. Three troops stand in the Conflict: 6 strength and the
    sword make 7; retreating two leaves one troop, 2 and the sword, 3."""

    engine, state = _start()
    revealed = _revealed_alone(engine, state, "scout", garrison=0, conflict=3)
    context = dict(revealed.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (1, 1)
    assert revealed.players[0].combat_strength == 6 + 1
    assert _counts(engine, revealed, "retreat_reveal_card_troops") == {1, 2}
    retreated = _do(engine, revealed, "retreat_reveal_card_troops", count=2)
    after = retreated.players[0]
    assert (after.troops_garrison, after.troops_conflict) == (2, 1)
    assert after.troops_supply == revealed.players[0].troops_supply
    assert after.combat_strength == 2 + 1
    assert "retreat_reveal_card_troops" not in _ids(engine, retreated)


def test_scout_retreats_only_the_troops_in_the_conflict() -> None:
    engine, state = _start()
    one = _revealed_alone(engine, state, "scout", garrison=2, conflict=1)
    assert _counts(engine, one, "retreat_reveal_card_troops") == {1}
    none = _revealed_alone(engine, state, "scout", garrison=3, conflict=0)
    assert _counts(engine, none, "retreat_reveal_card_troops") == set()
    # With no troop left in the Conflict the sword counts for nothing
    # ("Conflict에 troop이 하나도 없으면 0" [DI p. 11]).
    alone = _do(engine, one, "retreat_reveal_card_troops", count=1)
    assert alone.players[0].troops_conflict == 0
    assert alone.players[0].combat_strength == 0


def test_scout_may_retreat_none() -> None:
    """ "Up to" allows none [FAQ p. 3]: the troops stay and no refusal exists."""

    engine, state = _start()
    revealed = _revealed_alone(engine, state, "scout", garrison=0, conflict=3)
    assert not {a for a in _ids(engine, revealed) if a.startswith("decline_")}
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].troops_conflict == 3
    assert finished.players[0].combat_strength == 6 + 1


def test_two_scouts_retreat_two_troops_each() -> None:
    """Each Scout is its own choice: the same row of both is offered once, and
    taking it uses one Scout up; the other still retreats two more."""

    engine, state = _start()
    revealed = _revealed_alone(engine, state, "scout", garrison=0, conflict=5, copies=2)
    assert _counts(engine, revealed, "retreat_reveal_card_troops") == {1, 2}
    first = _do(engine, revealed, "retreat_reveal_card_troops", count=2)
    assert _counts(engine, first, "retreat_reveal_card_troops") == {1, 2}
    second = _do(engine, first, "retreat_reveal_card_troops", count=2)
    after = second.players[0]
    assert (after.troops_garrison, after.troops_conflict) == (4, 1)
    assert "retreat_reveal_card_troops" not in _ids(engine, second)


# --- Chani


def test_chani_matches_the_app_table() -> None:
    # App attribute table: cost 5, 1 copy, Fremen, Fremen / City / Spice Trade,
    # Reveal 2 Persuasion, AcquireEffect Water.
    entry = IMPERIUM_CARDS_BY_ID["chani_card"]
    assert entry.card.name == "Chani"
    assert entry.acquisition_cost == 5
    assert entry.copies == 1
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (
        AgentIcon.FREMEN,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is None
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.has_acquisition_bonus
    assert entry.acquisition_effect is PersonalCardAcquisitionEffect.GAIN_ONE_WATER
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_ANY_NUMBER_OF_TROOPS,
    )
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:chani_card:0") is entry


def test_chani_retreats_any_number_of_troops() -> None:
    """ "Retreat any number of your troops" [Chani card]; "'any number'는 0
    가능" (imperium-base.md 13.2, [FAQ pp. 1, 3]): every count from 1 to the
    troops in the Conflict is a row, and the card's 2 Persuasion are printed."""

    engine, state = _start()
    revealed = _revealed_alone(engine, state, "chani_card", garrison=0, conflict=5)
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2
    assert _counts(engine, revealed, "retreat_reveal_card_troops") == {1, 2, 3, 4, 5}
    retreated = _do(engine, revealed, "retreat_reveal_card_troops", count=5)
    after = retreated.players[0]
    assert (after.troops_garrison, after.troops_conflict) == (5, 0)
    assert after.combat_strength == 0


def test_chani_may_retreat_none() -> None:
    engine, state = _start()
    revealed = _revealed_alone(engine, state, "chani_card", garrison=0, conflict=4)
    assert not {a for a in _ids(engine, revealed) if a.startswith("decline_")}
    finished = _do(engine, revealed, "finish_reveal")
    assert finished.players[0].troops_conflict == 4
    assert finished.players[0].combat_strength == 8


def test_chani_offers_no_retreat_without_a_deployed_troop() -> None:
    engine, state = _start()
    revealed = _revealed_alone(engine, state, "chani_card", garrison=3, conflict=0)
    assert _counts(engine, revealed, "retreat_reveal_card_troops") == set()
    assert "finish_reveal" in _ids(engine, revealed)


def test_chani_acquisition_gains_one_water() -> None:
    """ "AcquireEffect Water" (app table): buying the card gives 1 water, once."""

    engine, state = _start()
    chani = "imperium:chani_card:0"
    others = tuple(card for card in state.imperium_row if card != chani)
    row = (chani, *others[:4])
    stocked = replace(
        state,
        imperium_row=row,
        imperium_deck=tuple(card for card in state.imperium_deck if card != chani),
    )
    hand = (
        "imperium:space_travel:0",
        "imperium:stilgar:0",
        "imperium:dr_yueh:0",
    )
    held = _seat(stocked, hand=hand, resources=Resources())
    revealed = _do(engine, held, "reveal_turn")
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2 + 2 + 1
    water = revealed.players[0].resources.water
    bought = _do(engine, revealed, "acquire_imperium", instance_id=chani)
    after = bought.players[0]
    assert chani in after.discard_pile
    assert after.resources.water == water + 1


def test_the_counted_troop_moves_are_staged_rows_of_the_original_catalog() -> None:
    """The effect is one row, then the owner picks the count (``choose_count``,
    stage B3); every row encodes and decodes in the original game's catalog and
    the picked count moves that many troops. Legion 1-3, Scout 1-2, Chani every
    count up to the troops in the Conflict."""

    from dune_imperium.adapters import ActionCodec

    codec = ActionCodec(CONFIG)
    engine, state = _start()
    for card_id, verb, garrison, conflict, counts in (
        ("sardaukar_legion", "deploy", 5, 0, {1, 2, 3}),
        ("scout", "retreat", 0, 3, {1, 2}),
        ("chani_card", "retreat", 0, 5, {1, 2, 3, 4, 5}),
    ):
        revealed = _revealed_alone(
            engine, state, card_id, garrison=garrison, conflict=conflict
        )
        rows = engine.legal_actions(revealed, 0)
        for action in rows:
            assert codec.decode(codec.encode(action), 0) == action
        effect = next(
            action
            for action in rows
            if action.action_id == verb and dict(action.arguments)["printed"] == card_id
        )
        picked = engine.apply(revealed, effect).state
        offered = engine.legal_actions(picked, 0)
        assert {dict(a.arguments)["count"] for a in offered} == counts
        for action in offered:
            assert action.action_id == "choose_count"
            assert codec.decode(codec.encode(action), 0) == action
        moved = engine.apply(picked, offered[0]).state
        after = moved.players[0]
        # The first row is count 1: one troop crossed.
        assert abs(after.troops_conflict - conflict) == 1, card_id


# --- Firm Grip --------------------------------------------------------------------


def test_firm_grip_matches_the_app_table() -> None:
    # App attribute table: cost 4, 1 copy, Emperor, Emperor and Landsraad, no
    # fixed Reveal values (tag EmperorAlliance).
    entry = IMPERIUM_CARDS_BY_ID["firm_grip"]
    assert entry.card.name == "Firm Grip"
    assert entry.acquisition_cost == 4
    assert entry.copies == 1
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == (AgentIcon.EMPEROR, AgentIcon.LANDSRAAD)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_PAY_TWO_SOLARI_FOR_CHOSEN_INFLUENCE
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:firm_grip:0") is entry


def _grip_placed(
    engine: UprisingRulesEngine,
    state: GameState,
    *,
    solari: int = 3,
    influence: Influence | None = None,
    leader: str | None = None,
) -> GameState:
    """Seat 0 sends Firm Grip to Hall of Oratory (a Landsraad space, no cost,
    one troop) holding ``solari`` Solari."""

    held, _ = _with_card(state, "firm_grip")
    held = _seat(
        held, resources=Resources(solari=solari), influence=influence or Influence()
    )
    if leader is not None:
        held = _seat(held, leader_id=leader, leader_face_id=leader)
    return _place(engine, held, "hall_of_oratory", "firm_grip")


def test_firm_grip_pays_two_solari_for_one_influence_of_three_factions() -> None:
    """ "[2 Solari] -> Choose one: +1 Spacing Guild / +1 Bene Gesserit / +1
    Fremen Influence" (the card; P0 sweep): an arrow cost, optional [DI p. 9]
    and paid once [FAQ p. 3]. Paying leaves the choice of the three Factions --
    never the Emperor -- and the turn cannot end before it is made."""

    engine, state = _start()
    placed = _grip_placed(engine, state)
    assert "pay_agent_card_solari" in _ids(engine, placed)
    paid = _do(engine, placed, "pay_agent_card_solari")
    assert paid.players[0].resources.solari == 3 - 2
    assert paid.players[0].influence == placed.players[0].influence
    assert sorted(str(f) for f in _influence_rows(engine, paid)) == [
        "bene_gesserit",
        "fremen",
        "spacing_guild",
    ]
    assert "finish_agent_turn" not in _ids(engine, paid)
    chosen = _do(engine, paid, "choose_agent_card_influence", faction="bene_gesserit")
    after = chosen.players[0].influence
    assert after.bene_gesserit == placed.players[0].influence.bene_gesserit + 1
    assert after.emperor == placed.players[0].influence.emperor
    assert not _influence_rows(engine, chosen)


def test_firm_grip_arrow_is_paid_once() -> None:
    engine, state = _start()
    placed = _grip_placed(engine, state, solari=9)
    paid = _do(engine, placed, "pay_agent_card_solari")
    chosen = _do(engine, paid, "choose_agent_card_influence", faction="fremen")
    assert chosen.players[0].resources.solari == 7
    assert "pay_agent_card_solari" not in _ids(engine, paid)
    assert "pay_agent_card_solari" not in _ids(engine, chosen)


def test_firm_grip_arrow_is_optional_and_needs_two_solari() -> None:
    """The owner who does not pay keeps the Solari and gains nothing; one
    Solari is too few to offer the arrow."""

    engine, state = _start()
    placed = _grip_placed(engine, state)
    resolved = _do(engine, placed, "resolve_board_effect", effect="troops")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].resources.solari == 3
    assert finished.players[0].influence == placed.players[0].influence
    poor = _grip_placed(engine, state, solari=1)
    assert "pay_agent_card_solari" not in _ids(engine, poor)


def test_firm_grip_does_not_offer_a_faction_at_the_top() -> None:
    """ "6칸 진영은 Influence를 내지 않는다(OQ-060)" (imperium-base.md 16): with the
    Fremen track at 6 the choice is the other two."""

    engine, state = _start()
    placed = _grip_placed(engine, state, influence=Influence(fremen=6))
    paid = _do(engine, placed, "pay_agent_card_solari")
    assert sorted(str(f) for f in _influence_rows(engine, paid)) == [
        "bene_gesserit",
        "spacing_guild",
    ]


def test_firm_grip_arrow_is_not_offered_when_all_three_are_at_the_top() -> None:
    """ "비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다(OQ-071)"
    (imperium-base.md 16): with all three Factions at 6 the 2 Solari would buy
    nothing, so the arrow is withheld (the Emperor is no option of the card);
    the page greys it out with the reason."""

    engine, state = _start()
    top = Influence(spacing_guild=6, bene_gesserit=6, fremen=6)
    placed = _grip_placed(engine, state, influence=top)
    assert "pay_agent_card_solari" not in _ids(engine, placed)
    found = unavailable_choices(placed, 0, engine.whole_actions(placed, 0))
    assert found is not None
    rows = cast("list[dict[str, Any]]", found["rows"])
    assert {"top"} <= {row["code"] for row in rows}


def test_firm_grip_solari_are_not_a_board_spaces_cost() -> None:
    """ "The 2 Solari is not a board-space cost for Count Ilban [FAQ p. 2]":
    paying the arrow draws no card for a Count Ilban Richese seat."""

    engine, state = _start()
    placed = _grip_placed(engine, state, leader="count_ilban_richese")
    before = placed.players[0]
    paid = _do(engine, placed, "pay_agent_card_solari")
    after = paid.players[0]
    assert after.owed_draws == before.owed_draws
    assert after.hand == before.hand


def test_firm_grip_reveals_four_persuasion_with_the_emperor_alliance() -> None:
    """ "Emperor Alliance: [P4]" judged when the line resolves (OQ-028); the
    card prints no Persuasion of its own."""

    engine, state = _start()
    state, _ = _with_card(state, "firm_grip", alone=True)
    without = _reveal(engine, state)
    assert without["persuasion"] == 0
    allied = _seat(state, alliance_faction_ids=("emperor",))
    assert _reveal(engine, allied)["persuasion"] == 4


def test_firm_grip_text_names_the_arrow_and_the_alliance_line() -> None:
    from dune_imperium.display.tokens import AGENT_EFFECT_TEXT
    from dune_imperium.display.tokens_ko import AGENT_EFFECT_TEXT_KO

    effect = PersonalCardAgentEffect.MAY_PAY_TWO_SOLARI_FOR_CHOSEN_INFLUENCE
    assert "Spacing Guild" in AGENT_EFFECT_TEXT[effect]
    assert "Emperor" not in AGENT_EFFECT_TEXT[effect]
    assert "{solari:2}" in AGENT_EFFECT_TEXT_KO[effect]
    line = reveal_lines(IMPERIUM_CARDS_BY_ID["firm_grip"])[0]
    assert reveal_effect_text(line) == "If you have the Emperor Alliance: +4 Persuasion"


# --- Shifting Allegiances ---------------------------------------------------------


def test_shifting_allegiances_matches_the_app_table() -> None:
    # App attribute table: cost 3, 2 copies, no Faction, Landsraad and Spice
    # Trade, Reveal 2 Persuasion.
    entry = IMPERIUM_CARDS_BY_ID["shifting_allegiances"]
    assert entry.card.name == "Shifting Allegiances"
    assert entry.acquisition_cost == 3
    assert entry.copies == 2
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_LOSE_INFLUENCE_AND_PAY_TWO_SPICE_FOR_TWO_INFLUENCE
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.reveal_choice_effects == ()
    assert entry.play_data_complete
    assert personal_card_for_instance("imperium:shifting_allegiances:1") is entry
    deck = content_for(CONFIG).imperium_deck_instance_ids
    assert "imperium:shifting_allegiances:1" in deck


def _shifting_placed(
    engine: UprisingRulesEngine,
    state: GameState,
    *,
    spice: int = 2,
    influence: Influence | None = None,
    alliances: tuple[str, ...] = (),
) -> GameState:
    """Seat 0 sends Shifting Allegiances to Hall of Oratory (a Landsraad space,
    no cost, one troop) holding ``spice`` spice and ``influence``."""

    held, _ = _with_card(state, "shifting_allegiances")
    held = _seat(
        held,
        resources=Resources(spice=spice),
        influence=influence or Influence(fremen=3),
        alliance_faction_ids=alliances,
    )
    return _place(engine, held, "hall_of_oratory", "shifting_allegiances")


def _loss_rows(
    engine: UprisingRulesEngine, state: GameState
) -> list[dict[str, object]]:
    return [
        dict(action.arguments)
        for action in _wholes(engine, state)
        if action.action_id == "lose_agent_card_influence"
    ]


def test_shifting_allegiances_loses_one_and_pays_spice_for_two_on_one_faction() -> None:
    """ "[lose 1 Influence with a chosen Faction] [2 spice] -> [2 Influence with
    one chosen Faction]" (the card; P0 sweep): an arrow cost, optional [DI
    p. 9] and paid once [FAQ p. 3]. The cost is the Faction lost and the 2
    spice; paying leaves one pick of a Faction for both Influence ("두 진영
    Influence를 한꺼번에 올리는 효과(Power Play, Shifting Allegiances)는 끊을
    수 없는 한 효과", imperium-base.md 13.3), and the turn cannot end before it
    is made."""

    engine, state = _start()
    placed = _shifting_placed(engine, state, influence=Influence(fremen=3))
    assert _loss_rows(engine, placed) == [{"faction": "fremen"}]
    paid = _do(engine, placed, "lose_agent_card_influence", faction="fremen")
    owner = paid.players[0]
    assert owner.resources.spice == 0
    assert owner.spice_spent_turn == placed.players[0].spice_spent_turn + 2
    assert owner.influence.fremen == 2
    assert sorted(str(f) for f in _influence_rows(engine, paid)) == [
        "bene_gesserit",
        "emperor",
        "fremen",
        "spacing_guild",
    ]
    assert "finish_agent_turn" not in _ids(engine, paid)
    chosen = _do(engine, paid, "choose_agent_card_influence", faction="emperor")
    after = chosen.players[0].influence
    assert after.emperor == placed.players[0].influence.emperor + 2
    assert after.fremen == 2
    # One pick paid both Influence: nothing more is chosen.
    assert not _influence_rows(engine, chosen)
    settled = _do(engine, chosen, "resolve_board_effect", effect="troops")
    assert "finish_agent_turn" in _ids(engine, settled)


def test_shifting_allegiances_may_lose_and_gain_the_same_faction() -> None:
    """ "같은 진영을 잃고 얻을 수 있다(결과 +1)" (imperium-base.md 13.2, [FAQ p. 4]):
    losing Fremen and gaining on Fremen again nets one Influence."""

    engine, state = _start()
    placed = _shifting_placed(engine, state, influence=Influence(fremen=3))
    paid = _do(engine, placed, "lose_agent_card_influence", faction="fremen")
    assert "fremen" in {str(f) for f in _influence_rows(engine, paid)}
    chosen = _do(engine, paid, "choose_agent_card_influence", faction="fremen")
    assert chosen.players[0].influence.fremen == 3 + 1
    assert chosen.players[0].resources.spice == 0


def test_shifting_allegiances_at_the_top_regains_what_it_lost() -> None:
    """A track at 6 is not offered to gain (OQ-060), but the Influence just
    lost makes room for one: the Faction is offered again, and the second
    Influence on a cube at 5 is lost."""

    engine, state = _start()
    placed = _shifting_placed(engine, state, influence=Influence(fremen=6))
    paid = _do(engine, placed, "lose_agent_card_influence", faction="fremen")
    assert paid.players[0].influence.fremen == 5
    chosen = _do(engine, paid, "choose_agent_card_influence", faction="fremen")
    assert chosen.players[0].influence.fremen == 6


def test_shifting_allegiances_cannot_lose_a_faction_without_influence() -> None:
    """ "Influence가 없는 진영은 잃을 수 없다" (imperium-base.md 13.2): only the
    Factions the owner has Influence with are offered to lose."""

    engine, state = _start()
    placed = _shifting_placed(
        engine, state, influence=Influence(emperor=1, bene_gesserit=2)
    )
    assert [row["faction"] for row in _loss_rows(engine, placed)] == [
        "emperor",
        "bene_gesserit",
    ]


def test_shifting_allegiances_with_no_influence_is_not_offered() -> None:
    """With no Influence anywhere the cost cannot be paid: the arrow is not
    offered and the page greys it out with the reason."""

    engine, state = _start()
    placed = _shifting_placed(engine, state, influence=Influence())
    assert "lose_agent_card_influence" not in _ids(engine, placed)
    found = unavailable_choices(placed, 0, engine.whole_actions(placed, 0))
    assert found is not None
    rows = cast("list[dict[str, Any]]", found["rows"])
    assert {"cost"} <= {row["code"] for row in rows}


def test_shifting_allegiances_needs_two_spice() -> None:
    engine, state = _start()
    poor = _shifting_placed(engine, state, spice=1)
    assert "lose_agent_card_influence" not in _ids(engine, poor)
    rich = _shifting_placed(engine, state, spice=2)
    assert "lose_agent_card_influence" in _ids(engine, rich)


def test_shifting_allegiances_arrow_is_optional_and_paid_once() -> None:
    """Unused, the owner keeps the spice and the Influence [DI p. 9]; paid, the
    arrow is gone ([FAQ p. 3])."""

    engine, state = _start()
    placed = _shifting_placed(engine, state, spice=9)
    resolved = _do(engine, placed, "resolve_board_effect", effect="troops")
    finished = _do(engine, resolved, "finish_agent_turn")
    assert finished.players[0].resources.spice == 9
    assert finished.players[0].influence == placed.players[0].influence
    paid = _do(engine, placed, "lose_agent_card_influence", faction="fremen")
    chosen = _do(engine, paid, "choose_agent_card_influence", faction="bene_gesserit")
    assert chosen.players[0].resources.spice == 7
    assert "lose_agent_card_influence" not in _ids(engine, paid)
    assert "lose_agent_card_influence" not in _ids(engine, chosen)


def test_shifting_allegiances_victory_points_follow_the_tracks() -> None:
    """Dropping to 1 loses the Victory Point of the 2 space and reaching 2 on
    another track earns one (Influence passes its Victory Point space as in
    every loss and gain)."""

    engine, state = _start()
    placed = _shifting_placed(
        engine, state, influence=Influence(fremen=2, bene_gesserit=0)
    )
    paid = _do(engine, placed, "lose_agent_card_influence", faction="fremen")
    assert paid.players[0].victory_points == placed.players[0].victory_points - 1
    chosen = _do(engine, paid, "choose_agent_card_influence", faction="bene_gesserit")
    assert chosen.players[0].victory_points == placed.players[0].victory_points


def test_shifting_allegiances_loses_an_alliance_to_the_tied_seat() -> None:
    """Losing Influence can lose an Alliance (imperium-base.md 6, [FAQ p. 1]):
    where several tied seats could take the token the owner names one, as every
    Influence loss asks."""

    engine, state = _start()
    state = _seat(state, 1, influence=Influence(emperor=4))
    state = _seat(state, 2, influence=Influence(emperor=4))
    placed = _shifting_placed(
        engine,
        state,
        influence=Influence(emperor=4),
        alliances=("emperor",),
    )
    rows = _loss_rows(engine, placed)
    assert rows == [
        {"alliance_recipient": 1, "faction": "emperor"},
        {"alliance_recipient": 2, "faction": "emperor"},
    ]
    paid = _do(
        engine, placed, "lose_agent_card_influence", faction="emperor",
        alliance_recipient=2,
    )
    assert paid.players[0].influence.emperor == 3
    assert paid.players[0].alliance_faction_ids == ()
    assert "emperor" in paid.players[2].alliance_faction_ids


def test_shifting_allegiances_returns_an_unclaimed_alliance() -> None:
    """With nobody else at 4 the Alliance token goes back to the board."""

    engine, state = _start()
    placed = _shifting_placed(
        engine, state, influence=Influence(emperor=4), alliances=("emperor",)
    )
    assert _loss_rows(engine, placed) == [{"faction": "emperor"}]
    paid = _do(engine, placed, "lose_agent_card_influence", faction="emperor")
    assert paid.players[0].influence.emperor == 3
    assert paid.players[0].alliance_faction_ids == ()


def test_shifting_allegiances_reveals_two_persuasion() -> None:
    engine, state = _start()
    state, _ = _with_card(state, "shifting_allegiances", alone=True)
    assert _reveal(engine, state)["persuasion"] == 2


def test_shifting_allegiances_text_names_the_arrow() -> None:
    from dune_imperium.display.tokens import AGENT_EFFECT_TEXT
    from dune_imperium.display.tokens_ko import AGENT_EFFECT_TEXT_KO

    effect = (
        PersonalCardAgentEffect.MAY_LOSE_INFLUENCE_AND_PAY_TWO_SPICE_FOR_TWO_INFLUENCE
    )
    assert "lose 1 Influence" in AGENT_EFFECT_TEXT[effect]
    assert "2 spice" in AGENT_EFFECT_TEXT[effect]
    assert "Gain 2 Influence with one chosen Faction" in AGENT_EFFECT_TEXT[effect]
    assert "{spice:2}" in AGENT_EFFECT_TEXT_KO[effect]
    assert "{influence_any:2}" in AGENT_EFFECT_TEXT_KO[effect]
