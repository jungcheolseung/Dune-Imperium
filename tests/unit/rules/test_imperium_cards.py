"""The original Dune: Imperium's Imperium cards (stage P3, trial transcription).

docs/rules/imperium-base.md 7, 11, 13.2 and docs/base-game-and-ix-plan.md 16.
The cards are not in the original game's deck yet (plan 16.1), so each test
puts the card instance into seat 0's hand of an original-game round; the
printed values are the Steam app's attribute table (plan 2.4, D1).
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import (
    AgentIcon,
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
    # The deck lists no original card until stage P3a (plan 16.1).
    assert not any("arrakis_recruiter" in card for card in _start()[1].imperium_deck)


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
