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
from dune_imperium.display.tokens import reveal_effect_text
from dune_imperium.display.tokens_ko import reveal_effect_text_ko
from dune_imperium.display.unavailable import unavailable_choices
from dune_imperium.rules import UprisingRulesEngine
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
    # A finished card is in the original game's deck or Row (plan 16.1); which
    # of the two depends on the setup shuffle.
    start = _start()[1]
    held = (*start.imperium_deck, *start.imperium_row)
    assert any("arrakis_recruiter" in card for card in held)


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
    """"Agent 아이콘이 없는 카드는 Agent turn에 낼 수 없다" [DI p. 9]
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
    """"Fremen Bond = another Fremen card in play" [DI p. 16] (imperium-base.md
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
    """"Trash(...비용이거나 카드가 자기를 trash하라고 할 때만 의무)" (imperium-base.md
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
    """"Spacing Guild Influence 2: [draw 1] [draw 1]": the Influence condition
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
    """"조건은 해결할 때 판정한다(OQ-028)" (imperium-base.md 16): the Influence
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
    """"Influence 조건" [DI p. 16] (imperium-base.md 11): the first line holds
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
    """"Conflict에 troop이 하나도 없으면 0" [DI p. 11]: the 4 swords join the
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
    """"-OR-" is a must-pick-one choice (P0 sweep: "choose one (must)";
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
    chosen = _do(
        engine, placed, "choose_agent_card_influence", faction="spacing_guild"
    )
    after = chosen.players[0]
    assert after.influence.spacing_guild == before.influence.spacing_guild + 1
    assert after.resources.spice == before.resources.spice
    assert "resolve_agent_card_effect" not in _ids(engine, chosen)
    assert "choose_agent_card_influence" not in _ids(engine, chosen)


def test_guild_ambassador_at_the_top_of_the_track_offers_the_spice_alone() -> None:
    """"6칸 진영은 Influence를 내지 않는다(OQ-060)" (imperium-base.md 16): at 6
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
    """"비용 화살표" [DI p. 16] (imperium-base.md 11): with the Spacing Guild
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
    """"Alliance 조건" [DI p. 16] (11): without the Spacing Guild Alliance
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
    """"[troop 2][draw 1]": separate icons (OQ-027), the hidden draw apart from
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
    """"비용 화살표" [DI p. 16] (imperium-base.md 11), optional [DI p. 9] and
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
    """"May deploy": the recruited troops stay in the garrison when not
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
    seated = replace(
        held, intrigue_deck=("intrigue:bribery:0", "intrigue:bribery:1")
    )
    return _place(engine, seated, "wealth", "imperial_spy")


def test_imperial_spy_trashes_itself_to_draw_an_intrigue_card() -> None:
    """"Trash this card -> [Intrigue card]": an arrow cost, optional [DI p. 9]
    [FAQ p. 3]; the card trashes itself as its own cost, so its draw is still
    paid (imperium-base.md 16, OQ-022's own-effect case) and, a hidden draw,
    is a step of its own (OQ-106): the turn cannot end before it is taken."""

    engine, state = _start()
    placed = _spy_placed(engine, state)
    me = "imperium:imperial_spy:0"
    assert dict(next(
        action.arguments
        for action in _wholes(engine, placed)
        if action.action_id == "trash_agent_card"
    )) == {"card_id": me}
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
    """"이 카드로 자신을 trash해야 Intrigue; 다른 수단으로 trash되면 없음" (FAQ p.
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
    """"Agent 아이콘이 없는 카드는 Agent turn에 낼 수 없다" [DI p. 9]
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
    """"다른 수단으로 trash해야 4 Solari" (imperium-base.md 13.2, [FAQ p. 1]): a
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
    seated = _seat(
        held, hand=(*owner.hand, mission), resources=Resources(spice=2)
    )
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
    """"another Bene Gesserit card in play" (imperium-base.md 16, OQ-028; the
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
    """"조건은 해결할 때 판정한다(OQ-028)": if the other Bene Gesserit card has
    left play before the choice, the box offers nothing and the turn's end
    fizzles it (OQ-057 (1))."""

    engine, state = _start()
    placed = _missionaria_placed(engine, state, bene_gesserit=True)
    gone = _seat(placed, in_play=())
    assert not _influence_rows(engine, gone)


def test_missionaria_protectiva_does_not_offer_a_faction_at_the_top() -> None:
    """"6칸 진영은 Influence를 내지 않는다(OQ-060)" (imperium-base.md 16)."""

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
