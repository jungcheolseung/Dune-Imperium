"""Tests for the basic Reveal-turn transition."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import (
    STARTING_DECK,
    starting_deck_instance_ids,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules.card_draw import (
    apply_personal_draw_reshuffle,
    draw_or_request_personal_cards,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import (
    apply_contract_reveal_choice,
    apply_corrinth_city_reveal,
    apply_reveal_card_trash,
    apply_reveal_influence_exchange,
    apply_reveal_sandworm_action,
    apply_reveal_spice_influence,
    apply_reveal_spy_action,
    apply_reveal_troop_move,
    apply_reveal_troop_retreat,
    begin_reveal_turn,
    finish_reveal_turn,
    grant_late_reveal_effects,
    legal_contract_reveal_choice_actions,
    legal_corrinth_city_reveal_actions,
    legal_defer_reveal_choice_actions,
    legal_finish_reveal_actions,
    legal_resume_reveal_choice_actions,
    legal_reveal_actions,
    legal_reveal_card_trash_actions,
    legal_reveal_influence_exchange_actions,
    legal_reveal_sandworm_actions,
    legal_reveal_spice_influence_actions,
    legal_reveal_spy_actions,
    legal_reveal_troop_move_actions,
    legal_reveal_troop_retreat_actions,
    reveal_late_arrivals,
    reveal_pending_gains,
)


def test_corrinth_city_can_take_high_council_during_current_reveal() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city,),
        resources=Resources(solari=5),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_corrinth_city_reveal_actions(revealed, 0)

    assert tuple(action.action_id for action in actions) == (
        "gain_five_reveal_solari",
        "take_high_council_from_reveal",
    )
    take_seat = actions[1]
    result = apply_corrinth_city_reveal(revealed, take_seat)
    resolved = result.state.players[0]

    assert resolved.high_council is True
    assert resolved.resources.solari == 0
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.events[0].kind == "high_council_acquired"


def test_corrinth_city_gains_five_solari_when_seat_is_unavailable() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city,),
        resources=Resources(solari=2),
        high_council=True,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_corrinth_city_reveal_actions(revealed, 0)

    assert tuple(action.action_id for action in actions) == (
        "gain_five_reveal_solari",
    )
    result = apply_corrinth_city_reveal(revealed, actions[0])

    assert result.state.players[0].resources.solari == 7
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.events[0].kind == "reveal_solari_gained"


def test_desert_power_can_keep_persuasion_or_pay_water_for_a_sandworm() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(
        _state(owner),
        current_conflict_ids=("propaganda",),
        shield_wall_present=True,
    )
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))

    actions = legal_reveal_sandworm_actions(revealed.state, 0)
    assert tuple(action.action_id for action in actions) == (
        "decline_reveal_sandworm",
        "pay_reveal_water_for_sandworm",
    )

    declined = apply_reveal_sandworm_action(revealed.state, actions[0])
    assert dict(declined.state.decision_stack[-1].context)["persuasion"] == 2
    assert declined.state.players[0].sandworms_conflict == 0

    deployed = apply_reveal_sandworm_action(revealed.state, actions[1])
    context = dict(deployed.state.decision_stack[-1].context)
    owner_after = deployed.state.players[0]
    assert owner_after.resources.water == 0
    assert owner_after.maker_hooks is True
    assert owner_after.sandworms_conflict == 1
    assert owner_after.combat_strength == 3
    assert context["persuasion"] == 0
    assert context["strength"] == 3
    assert tuple(event.kind for event in deployed.events) == (
        "reveal_sandworm_deployed",
        "reveal_strength_gained",
    )


@pytest.mark.parametrize("extra_persuasion", [False, True])
def test_desert_power_sandworm_closes_once_its_two_persuasion_are_spent(
    extra_persuasion: bool,
) -> None:
    # "[2 Persuasion] -OR- [Maker Hooks]: [water] -> [sandworm]" [Desert Power
    # card] (player-turns.md: "Desert Power는 Reveal에서 Persuasion 2를
    # 얻거나, ... sandworm 1개를 소환" [Desert Power card] [Main pp. 10, 20]).
    # Effects resolve in any order and "you may use Persuasion that you've
    # gained to acquire new cards" [Main p. 12], but the 2 spent on Prepare
    # the Way were the Persuasion branch: the sandworm, which gives them
    # back, no longer opens. Before the fix the seat bought the card and then
    # still took the sandworm, leaving the Reveal at -2 Persuasion. With 2
    # more Persuasion unspent (Convincing Argument) the sandworm stays open.
    desert_power = _imperium_instance("desert_power")
    hand = (desert_power, _instance("convincing_argument")) if extra_persuasion else (
        desert_power,
    )
    owner = PlayerState(
        player_id=0, hand=hand, maker_hooks=True, resources=Resources(water=2)
    )
    state = replace(
        _state(owner),
        current_conflict_ids=("propaganda",),
        reserve_stacks=(("prepare_the_way", 7),),
    )
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    deferred = engine.apply(
        revealed.state, DomainAction(action_id="defer_reveal_choice", actor=0)
    ).state
    bought = engine.apply(
        deferred,
        DomainAction(
            action_id="acquire_reserve",
            actor=0,
            arguments=(("card_id", "prepare_the_way"),),
        ),
    ).state
    persuasion = dict(bought.decision_stack[-1].context)["persuasion"]
    assert persuasion == (2 if extra_persuasion else 0)
    resumes = legal_resume_reveal_choice_actions(bought, 0)
    if not extra_persuasion:
        assert resumes == ()
        finish = engine.legal_actions(bought, 0)
        assert DomainAction(action_id="finish_reveal", actor=0) in finish
        return
    resumed = engine.apply(bought, resumes[0]).state
    sandworm = DomainAction(action_id="pay_reveal_water_for_sandworm", actor=0)
    assert sandworm in legal_reveal_sandworm_actions(resumed, 0)
    worm = engine.apply(resumed, sandworm).state
    assert worm.players[0].sandworms_conflict == 1
    assert dict(worm.decision_stack[-1].context)["persuasion"] == 0


def test_desert_power_recalculates_sword_strength_when_sandworm_is_first_unit() -> None:
    desert_power = _imperium_instance("desert_power")
    maula_pistol = _imperium_instance("maula_pistol")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power, maula_pistol),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))

    assert dict(revealed.state.decision_stack[-2].context)["strength"] == 0
    action = legal_reveal_sandworm_actions(revealed.state, 0)[1]
    deployed = apply_reveal_sandworm_action(revealed.state, action)

    assert deployed.state.players[0].combat_strength == 4
    assert dict(deployed.state.decision_stack[-1].context)["strength"] == 4


def test_desert_power_adds_three_strength_to_existing_conflict_units() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
        troops_supply=8,
        troops_conflict=1,
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    deployed = apply_reveal_sandworm_action(
        revealed.state,
        legal_reveal_sandworm_actions(revealed.state, 0)[1],
    )

    assert deployed.state.players[0].combat_strength == 5
    assert dict(deployed.state.decision_stack[-1].context)["strength"] == 5


def test_desert_power_reveal_sandworm_is_blocked_by_shield_wall() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(
        _state(owner),
        current_conflict_ids=("siege_of_arrakeen",),
        shield_wall_present=True,
    )
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))

    assert legal_reveal_sandworm_actions(revealed.state, 0) == ()
    assert dict(revealed.state.decision_stack[-1].context)["persuasion"] == 2


def test_desert_power_reveal_sandworm_requires_water_and_maker_hooks() -> None:
    desert_power = _imperium_instance("desert_power")
    for owner in (
        PlayerState(
            player_id=0,
            hand=(desert_power,),
            maker_hooks=False,
            resources=Resources(water=1),
        ),
        PlayerState(
            player_id=0,
            hand=(desert_power,),
            maker_hooks=True,
            resources=Resources(water=0),
        ),
    ):
        state = replace(_state(owner), current_conflict_ids=("propaganda",))
        revealed = begin_reveal_turn(
            state,
            DomainAction(action_id="reveal_turn", actor=0),
        )

        assert legal_reveal_sandworm_actions(revealed.state, 0) == ()


def test_engine_dispatches_desert_power_reveal_sandworm_choice() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    engine = UprisingRulesEngine()
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    action = next(
        candidate
        for candidate in engine.legal_actions(revealed.state, 0)
        if candidate.action_id == "pay_reveal_water_for_sandworm"
    )

    transition = engine.apply(revealed.state, action)

    assert transition.state.players[0].sandworms_conflict == 1
    assert transition.state.players[0].resources.water == 0


def test_calculus_of_power_trashes_another_emperor_for_strength() -> None:
    calculus = _imperium_instance("calculus_of_power")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
        hand=(calculus, sardaukar),
    )
    state = replace(_state(owner), intrigue_deck=("intrigue:test",))
    revealed = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_reveal_card_trash_actions(revealed, 0)

    assert {action.action_id for action in actions} == {
        "decline_reveal_card_trash",
        "trash_reveal_card",
    }
    trash = next(
        action for action in actions if action.action_id == "trash_reveal_card"
    )
    assert dict(trash.arguments)["card_id"] == sardaukar

    result = apply_reveal_card_trash(revealed, trash)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].in_play == (calculus,)
    assert result.state.players[0].trashed == (sardaukar,)
    assert result.state.players[0].intrigue_cards == ("intrigue:test",)
    assert result.state.players[0].combat_strength == 6
    assert context["strength"] == 6
    assert context["optional_sword_strength"] == 3
    assert [event.kind for event in result.events] == [
        "card_trashed",
        "intrigue_card_drawn",
        "reveal_strength_gained",
    ]



def test_leadership_counts_sword_cards_once_and_ignores_a_later_trash() -> None:
    # Designer ruling (In person, designer-rulings-audit.md): Leadership
    # counts the other sword cards at one moment and a trashed card cannot be
    # counted. Counting at the Reveal's start gives the same +1 as counting
    # after Calculus of Power trashes Sardaukar Soldier (Calculus then shows
    # swords, Sardaukar is gone), and Sardaukar's already-pooled sword stays
    # (OQ-022).
    leadership = _imperium_instance("leadership")
    calculus = _imperium_instance("calculus_of_power")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
        hand=(leadership, calculus, sardaukar),
    )
    state = replace(_state(owner), intrigue_deck=("intrigue:test",))
    revealed = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    reveal = next(frame for frame in revealed.decision_stack if frame.kind == "reveal")
    # troop 2 + Leadership 1 + Sardaukar 1 + Leadership's one other sword card.
    assert dict(reveal.context)["sword_strength"] == 3
    assert revealed.players[0].combat_strength == 5

    trash = next(
        action
        for action in legal_reveal_card_trash_actions(revealed, 0)
        if action.action_id == "trash_reveal_card"
    )
    result = apply_reveal_card_trash(revealed, trash)
    reveal = next(
        frame for frame in result.state.decision_stack if frame.kind == "reveal"
    )
    assert result.state.players[0].trashed == (sardaukar,)
    assert dict(reveal.context)["sword_strength"] == 3
    assert dict(reveal.context)["optional_sword_strength"] == 3
    # Not 9: Calculus becoming a sword card does not recount Leadership.
    assert result.state.players[0].combat_strength == 8

# Leadership: "+[sword] for each other revealed card that provides one or
# more [sword] this turn." [Leadership card]. A card whose Reveal choice gave
# swords provides them this turn too, and Leadership "counts at one moment"
# (designer ruling, designer-rulings-audit.md; OQ-057) of the owner's
# choosing [Main p. 12], so it can count after that choice.
def _leadership_reveal(*hand: str, troops_conflict: int) -> GameState:
    leadership = _imperium_instance("leadership")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(leadership, *hand),
            troops_supply=9 - troops_conflict,
            troops_conflict=troops_conflict,
        )
    )
    return begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state


def _apply_first(state: GameState, action_id: str) -> GameState:
    engine = UprisingRulesEngine()
    action = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == action_id
    )
    return engine.apply(state, action).state


def test_leadership_counts_undercover_assets_chosen_swords() -> None:
    revealed = _leadership_reveal(
        _imperium_instance("undercover_asset"), troops_conflict=1
    )
    # troop 2 + Leadership 1: Undercover Asset has provided no sword yet.
    assert revealed.players[0].combat_strength == 3
    chose = _apply_first(revealed, "gain_two_reveal_strength")
    # + Undercover Asset's 2 swords + Leadership's 1 for it (5 before the fix).
    assert chose.players[0].combat_strength == 6
    context = dict(chose.decision_stack[-1].context)
    assert context["strength"] == 6
    # Counted once: a later step adds nothing more.
    assert _apply_first(chose, "finish_reveal").players[0].combat_strength == 6


def test_leadership_does_not_count_undercover_asset_taking_the_spy() -> None:
    revealed = _leadership_reveal(
        _imperium_instance("undercover_asset"), troops_conflict=1
    )
    placed = _apply_first(revealed, "place_reveal_spy")
    assert placed.players[0].combat_strength == 3


def test_leadership_counts_chanis_retreat_swords() -> None:
    revealed = _leadership_reveal(
        _imperium_instance("chani_clever_tactician"), troops_conflict=4
    )
    # troops 8 + Leadership 1.
    assert revealed.players[0].combat_strength == 9
    retreated = _apply_first(revealed, "retreat_two_troops_for_reveal")
    # Two troops (4) leave, Chani's 4 swords arrive, Leadership +1 for Chani.
    assert retreated.players[0].combat_strength == 10
    assert retreated.players[0].troops_conflict == 2


def test_leadership_through_the_engine_still_counts_calculus_once() -> None:
    # The designer's example (see the test above): after Calculus of Power
    # trashes Sardaukar Soldier, Calculus is a sword card and Sardaukar is
    # gone, so the best single moment is still one card: 8, not 9.
    calculus = _imperium_instance("calculus_of_power")
    sardaukar = _imperium_instance("sardaukar_soldier")
    revealed = _leadership_reveal(calculus, sardaukar, troops_conflict=1)
    assert revealed.players[0].combat_strength == 5
    trashed = _apply_first(revealed, "trash_reveal_card")
    assert trashed.players[0].trashed == (sardaukar,)
    assert trashed.players[0].combat_strength == 8


def test_calculus_of_power_cannot_pay_with_itself() -> None:
    calculus = _imperium_instance("calculus_of_power")
    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(calculus,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    assert legal_reveal_card_trash_actions(revealed, 0) == ()
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2


def test_calculus_of_power_cannot_pay_with_overthrow() -> None:
    # Overthrow prints no affiliation banner under its title [card face; BGG
    # inventory row blank] and is no longer an Emperor card, so it is not a
    # candidate for Calculus of Power's "trash another Emperor card" Reveal
    # choice. With no eligible Emperor card in play, the optional trash
    # choice never opens at all, same as when Calculus is alone in hand.
    calculus = _imperium_instance("calculus_of_power")
    overthrow = _imperium_instance("overthrow")
    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(calculus, overthrow))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    assert overthrow in revealed.players[0].in_play
    assert legal_reveal_card_trash_actions(revealed, 0) == ()


def test_desert_power_recounts_calculus_sword_when_it_adds_the_first_unit() -> None:
    desert_power = _imperium_instance("desert_power")
    calculus = _imperium_instance("calculus_of_power")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        hand=(calculus, desert_power),
        in_play=(sardaukar,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    calculus_trash = next(
        action
        for action in legal_reveal_card_trash_actions(revealed, 0)
        if action.action_id == "trash_reveal_card"
    )
    after_calculus = apply_reveal_card_trash(revealed, calculus_trash).state
    context = dict(after_calculus.decision_stack[-2].context)

    assert context["strength"] == 0
    assert context["optional_sword_strength"] == 3
    desert_action = legal_reveal_sandworm_actions(after_calculus, 0)[1]
    deployed = apply_reveal_sandworm_action(after_calculus, desert_action)

    assert deployed.state.players[0].combat_strength == 6
    assert dict(deployed.state.decision_stack[-1].context)["strength"] == 6


def test_captured_mentat_may_exchange_influence_on_reveal() -> None:
    mentat = _imperium_instance("captured_mentat")
    owner = PlayerState(
        player_id=0,
        hand=(mentat,),
        influence=Influence(emperor=1),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_reveal_influence_exchange_actions(revealed, 0)

    assert len(actions) == 5
    assert any(
        dict(action.arguments)
        == {"gained_faction": "emperor", "lost_faction": "emperor"}
        for action in actions
    )
    exchange = next(
        action
        for action in actions
        if dict(action.arguments)
        == {"gained_faction": "fremen", "lost_faction": "emperor"}
    )
    result = apply_reveal_influence_exchange(revealed, exchange)

    assert result.state.players[0].influence.emperor == 0
    assert result.state.players[0].influence.fremen == 1
    assert [event.kind for event in result.events] == [
        "influence_lost",
        "influence_gained",
    ]


def test_captured_mentat_skips_influence_choice_with_no_payable_cost() -> None:
    mentat = _imperium_instance("captured_mentat")

    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(mentat,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    assert legal_reveal_influence_exchange_actions(revealed, 0) == ()
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 1


def test_captured_mentat_selects_between_tied_alliance_recipients() -> None:
    mentat = _imperium_instance("captured_mentat")
    owner = PlayerState(
        player_id=0,
        hand=(mentat,),
        influence=Influence(emperor=4),
        alliance_faction_ids=(Faction.EMPEROR.value,),
        victory_points=2,
    )
    state = _state(owner)
    players = list(state.players)
    players[1] = replace(players[1], influence=Influence(emperor=4))
    players[2] = replace(players[2], influence=Influence(emperor=4))
    state = replace(state, players=tuple(players))
    revealed = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    exchange = next(
        action
        for action in legal_reveal_influence_exchange_actions(revealed, 0)
        if dict(action.arguments)
        == {
            "alliance_recipient": 2,
            "gained_faction": "fremen",
            "lost_faction": "emperor",
        }
    )

    result = apply_reveal_influence_exchange(revealed, exchange).state

    assert result.players[0].alliance_faction_ids == ()
    assert result.players[2].alliance_faction_ids == (Faction.EMPEROR.value,)
    assert result.players[0].influence.fremen == 1


def test_spacing_guilds_favor_may_pay_three_spice_for_influence() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(favor,),
        resources=Resources(spice=3),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_reveal_spice_influence_actions(revealed, 0)

    assert len(actions) == 5
    payment = next(
        action
        for action in actions
        if dict(action.arguments).get("faction") == Faction.FREMEN.value
    )
    result = apply_reveal_spice_influence(revealed, payment)

    assert result.state.players[0].resources.spice == 0
    assert result.state.players[0].influence.fremen == 1
    assert [event.kind for event in result.events] == [
        "reveal_spice_paid",
        "influence_gained",
    ]


def test_spacing_guilds_favor_cleanup_does_not_trigger_discard_effect() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(favor,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    result = finish_reveal_turn(
        revealed,
        DomainAction(action_id="finish_reveal", actor=0),
    ).state

    assert result.players[0].discard_pile == (favor,)
    assert result.players[0].resources.spice == 0


def test_two_spacing_guild_favors_cannot_spend_same_spice_twice() -> None:
    favors = tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if ":spacing_guild_s_favor:" in instance_id
    )
    owner = PlayerState(
        player_id=0,
        hand=favors,
        resources=Resources(spice=3),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    payment = next(
        action
        for action in legal_reveal_spice_influence_actions(revealed, 0)
        if dict(action.arguments).get("faction") == Faction.EMPEROR.value
    )

    paid = apply_reveal_spice_influence(revealed, payment).state

    assert legal_reveal_spice_influence_actions(paid, 0) == (
        DomainAction(action_id="decline_reveal_spice_influence", actor=0),
    )


def _instance(card_id: str, copy: int = 0) -> str:
    return tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )[copy]


def _imperium_instance(
    card_id: str,
    copy: int = 0,
    *,
    choam_module: bool = False,
) -> str:
    return tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(choam_module)
        if f":{card_id}:" in instance_id
    )[copy]


def _take_reveal_gains(state: GameState) -> GameState:
    """Take every pending Reveal gain (troops, Intrigue, resources; OQ-045)."""

    return _with_gains(RuleResult(state=state)).state


def _with_gains(result: RuleResult) -> RuleResult:
    """Take every pending Reveal gain, keeping the events in order."""

    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )

    state = result.state
    events = list(result.events)
    while actions := legal_reveal_gain_actions(state, 0):
        step = apply_reveal_gain(state, actions[0])
        state = step.state
        events.extend(step.events)
    return RuleResult(state=state, events=tuple(events))


def _state(player: PlayerState, *, choam_module: bool = False) -> GameState:
    return GameState(
        config=RulesetConfig(choam_module=choam_module),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def test_reveal_is_available_even_with_agents_remaining() -> None:
    state = _state(PlayerState(player_id=0))

    assert legal_reveal_actions(state, 0) == (
        DomainAction(action_id="reveal_turn", actor=0),
    )
    assert legal_reveal_actions(state, 1) == ()


def test_treacherous_maneuver_reveal_draws_intrigue() -> None:
    maneuver = _imperium_instance("treacherous_maneuver")
    owner = PlayerState(player_id=0, hand=(maneuver,))
    state = replace(_state(owner), intrigue_deck=("intrigue:test",))

    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )

    result = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    )

    # The draw waits for the owner's order in the Reveal (OQ-045).
    assert result.state.players[0].intrigue_cards == ()
    assert [event.kind for event in result.events] == ["reveal_started"]
    (gain,) = legal_reveal_gain_actions(result.state, 0)
    assert gain.action_id == "draw_reveal_intrigue"
    drawn = apply_reveal_gain(result.state, gain)
    assert drawn.state.players[0].intrigue_cards == ("intrigue:test",)
    assert drawn.state.intrigue_deck == ()
    assert dict(drawn.state.decision_stack[-1].context)["persuasion"] == 1
    assert [event.kind for event in drawn.events] == ["intrigue_card_drawn"]
    assert legal_reveal_gain_actions(drawn.state, 0) == ()


def test_treacherous_maneuver_reveal_tolerates_an_empty_intrigue_deck() -> None:
    maneuver = _imperium_instance("treacherous_maneuver")

    from dune_imperium.rules.reveal_turn import apply_reveal_gain

    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(maneuver,))),
        DomainAction(action_id="reveal_turn", actor=0),
    )
    result = apply_reveal_gain(
        revealed.state, DomainAction(action_id="draw_reveal_intrigue", actor=0)
    )

    assert result.state.players[0].intrigue_cards == ()
    # With the deck empty the draw is owed to the dispatcher, which reshuffles
    # the discard [FAQ p. 2] or stops short when there is nothing to shuffle.
    assert result.events == ()
    (owed,) = result.state.pending_intrigue_draws
    assert owed[:2] == (0, 1)
    assert owed[2].endswith("reveal_gain:imperium:treacherous_maneuver:0")


def test_chani_retreats_two_troops_for_four_strength() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    owner = PlayerState(
        player_id=0,
        hand=(chani,),
        troops_supply=8,
        troops_garrison=2,
        troops_conflict=2,
        sandworms_conflict=1,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    actions = legal_reveal_troop_retreat_actions(revealed, 0)
    assert {action.action_id for action in actions} == {
        "decline_reveal_troop_retreat",
        "retreat_two_troops_for_reveal",
    }
    retreat = next(
        action
        for action in actions
        if action.action_id == "retreat_two_troops_for_reveal"
    )
    result = apply_reveal_troop_retreat(revealed, retreat)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].sandworms_conflict == 1
    assert result.state.players[0].troops_garrison == 4
    assert result.state.players[0].combat_strength == 7
    assert context["strength"] == 7
    assert context["optional_sword_strength"] == 4
    assert [event.kind for event in result.events] == [
        "troops_retreated",
        "reveal_strength_gained",
    ]


def test_chani_retreat_clears_strength_when_no_unit_remains() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    owner = PlayerState(
        player_id=0,
        hand=(chani,),
        troops_supply=8,
        troops_garrison=2,
        troops_conflict=2,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    retreat = next(
        action
        for action in legal_reveal_troop_retreat_actions(revealed, 0)
        if action.action_id == "retreat_two_troops_for_reveal"
    )

    result = apply_reveal_troop_retreat(revealed, retreat)

    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].combat_strength == 0
    context = dict(result.state.decision_stack[-1].context)
    assert context["strength"] == 0
    assert context["optional_sword_strength"] == 4


def test_chani_fremen_bond_adds_two_persuasion() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    fremen = _imperium_instance("desert_survival")

    result = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(chani, fremen))),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3


def test_steersman_reveal_gains_persuasion_and_spice() -> None:
    steersman = _imperium_instance("steersman")

    result = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(steersman,))),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    result = _with_gains(result)

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].resources.spice == 2


def test_junction_headquarters_reveal_gains_water_and_recruits() -> None:
    junction = _imperium_instance("junction_headquarters")

    result = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(junction,))),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    # Both the water and the troop are the owner's own Reveal actions.
    assert result.state.players[0].resources.water == 1
    assert result.state.players[0].troops_garrison == 3
    state = _take_reveal_gains(result.state)
    owner = state.players[0]
    assert dict(state.decision_stack[-1].context)["persuasion"] == 1
    assert owner.troops_supply == 8
    assert owner.troops_garrison == 4


def test_reveal_moves_hand_to_in_play_and_totals_persuasion() -> None:
    argument = _instance("convincing_argument")
    diplomacy = _instance("diplomacy")
    state = _state(PlayerState(player_id=0, hand=(argument, diplomacy)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert owner.hand == ()
    assert owner.in_play == (argument, diplomacy)
    assert context["persuasion"] == 3
    assert context["revealed_card_count"] == 2
    assert context["revealed_card_000"] == argument
    assert context["revealed_card_001"] == diplomacy


def test_bene_gesserit_operative_gains_persuasion_with_two_placed_spies() -> None:
    operative = _imperium_instance("bene_gesserit_operative")
    without_spies = _state(PlayerState(player_id=0, hand=(operative,)))
    with_spies = _state(
        PlayerState(
            player_id=0,
            hand=(operative,),
            spies_supply=1,
            spy_post_ids=(
                "emperor-sardaukar-dutiful-service",
                "bene-gesserit-espionage-secrets",
            ),
        )
    )

    base = begin_reveal_turn(
        without_spies,
        legal_reveal_actions(without_spies, 0)[0],
    )
    bonus = begin_reveal_turn(
        with_spies,
        legal_reveal_actions(with_spies, 0)[0],
    )

    assert dict(base.state.decision_stack[-1].context)["persuasion"] == 1
    assert dict(bonus.state.decision_stack[-1].context)["persuasion"] == 3


def test_reliable_informant_reveals_for_persuasion_and_solari() -> None:
    informant = _imperium_instance("reliable_informant")
    state = _state(PlayerState(player_id=0, hand=(informant,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    result = _with_gains(result)

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].resources.solari == 1


def test_strike_fleet_reveals_for_persuasion_and_strength() -> None:
    strike_fleet = _imperium_instance("strike_fleet")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(strike_fleet,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].combat_strength == 5


def test_imperial_spymaster_reveals_for_persuasion_and_strength() -> None:
    spymaster = _imperium_instance("imperial_spymaster")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spymaster,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].combat_strength == 3


def test_spy_network_recalls_one_of_two_spies_and_draws_intrigue() -> None:
    spy_network = _imperium_instance("spy_network")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spy_network,),
            troops_supply=8,
            troops_conflict=1,
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    state = replace(state, intrigue_deck=("intrigue:test:0",))

    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    engine = UprisingRulesEngine()
    choices = tuple(
        action
        for action in engine.legal_actions(revealed.state, 0)
        if action.action_id != "defer_reveal_choice"
    )
    selected = next(
        action
        for action in choices
        if dict(action.arguments).get("post_id") == posts[1]
    )
    result = engine.apply(revealed.state, selected)

    # The recall is an arrow cost, so declining is offered first [Spy
    # Network card] [Main p. 20].
    assert tuple(action.action_id for action in choices) == (
        "decline_reveal_spy_recall",
        "recall_spy_for_reveal",
        "recall_spy_for_reveal",
    )
    assert {dict(action.arguments)["post_id"] for action in choices[1:]} == set(
        posts
    )
    assert result.state.players[0].spy_post_ids == (posts[0],)
    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].combat_strength == 3
    assert tuple(event.kind for event in result.events) == (
        "spy_recalled",
        "intrigue_card_drawn",
    )


def test_spy_network_recall_may_be_declined_with_two_spies_placed() -> None:
    # Spy Network: "If you have two or more Spies on the board: [recall Spy]
    # -> [Intrigue card]" [Spy Network card]. The recall is left of an arrow,
    # and "You do not have to pay such a cost on a card" [Main p. 20]; paying
    # an arrow cost is optional [FAQ p. 3]. Declining keeps both Spies, draws
    # nothing and lets the Reveal finish.
    spy_network = _imperium_instance("spy_network")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spy_network,),
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    state = replace(state, intrigue_deck=("intrigue:test:0",))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()

    declined = engine.apply(
        revealed, DomainAction(action_id="decline_reveal_spy_recall", actor=0)
    ).state

    assert declined.players[0].spy_post_ids == posts
    assert declined.players[0].intrigue_cards == ()
    assert declined.intrigue_deck == ("intrigue:test:0",)
    assert declined.decision_stack[-1].kind == "reveal"
    assert "finish_reveal" in {
        action.action_id for action in engine.legal_actions(declined, 0)
    }


def test_spy_network_recall_becomes_unavailable_when_spies_drop_mid_reveal() -> None:
    # The two-Spy condition is judged again when the queued choice resolves
    # in the owner's chosen Reveal order [Main p. 12] [Main pp. 9, 20]; In
    # High Places can recall both remaining Spies first, and the optional
    # recall and Intrigue draw are then unavailable.
    in_high_places = _imperium_instance("in_high_places")
    spy_network = _imperium_instance("spy_network")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places, spy_network),
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    state = replace(state, intrigue_deck=("intrigue:test:0",))

    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    engine = UprisingRulesEngine()
    pair = next(
        action
        for action in engine.legal_actions(revealed.state, 0)
        if action.action_id == "recall_spies_for_reveal"
    )
    drained = engine.apply(revealed.state, pair).state
    assert drained.players[0].spy_post_ids == ()

    choices = engine.legal_actions(drained, 0)
    assert [action.action_id for action in choices] == [
        "defer_reveal_choice",
        "decline_reveal_spy_recall",
    ]
    resolved = engine.apply(drained, choices[0]).state
    assert resolved.players[0].intrigue_cards == ()
    assert resolved.intrigue_deck == ("intrigue:test:0",)
    assert resolved.players[0].spies_supply == 3
    assert resolved.decision_stack[-1].kind == "reveal"


def test_spy_network_has_no_recall_effect_with_only_one_spy() -> None:
    spy_network = _imperium_instance("spy_network")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spy_network,),
            spies_supply=2,
            spy_post_ids=("arrakis-hagga-basin",),
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert legal_reveal_spy_actions(result.state, 0) == ()
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2


def test_in_high_places_may_recall_two_spies_for_three_persuasion() -> None:
    in_high_places = _imperium_instance("in_high_places")
    posts = (
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places,),
            spies_supply=0,
            spy_post_ids=posts,
        )
    )

    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    choices = legal_reveal_spy_actions(revealed.state, 0)
    recall = next(
        action for action in choices if action.action_id == "recall_spies_for_reveal"
    )
    result = apply_reveal_spy_action(revealed.state, recall)

    assert len(choices) == 4
    assert result.state.players[0].spies_supply == 2
    assert len(result.state.players[0].spy_post_ids) == 1
    # "[recall Spy] [recall Spy] -> +3 Persuasion" on top of the printed 2
    # [In High Places card]; the engine used to add only 2.
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 5
    assert tuple(event.kind for event in result.events) == (
        "spy_recalled",
        "spy_recalled",
        "reveal_persuasion_gained",
    )
    assert dict(result.events[-1].payload)["amount"] == 3


def test_in_high_places_reveal_spy_recall_may_be_declined() -> None:
    in_high_places = _imperium_instance("in_high_places")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places,),
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    decline = next(
        action
        for action in legal_reveal_spy_actions(revealed.state, 0)
        if action.action_id == "decline_reveal_spy_recall"
    )

    result = apply_reveal_spy_action(revealed.state, decline)

    assert result.state.players[0].spy_post_ids == posts
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.events[0].kind == "reveal_spy_recall_declined"


def test_rebel_supplier_reveals_for_spice_and_strength() -> None:
    supplier = _imperium_instance("rebel_supplier")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(supplier,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    result = _with_gains(result)

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0
    assert result.state.players[0].resources.spice == 1
    assert result.state.players[0].combat_strength == 3


def test_dangerous_rhetoric_reveals_for_persuasion_and_strength() -> None:
    rhetoric = _imperium_instance("dangerous_rhetoric")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(rhetoric,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].combat_strength == 3


def test_public_spectacle_reveal_places_a_spy() -> None:
    spectacle = _imperium_instance("public_spectacle")
    state = _state(PlayerState(player_id=0, hand=(spectacle,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    engine = UprisingRulesEngine()
    choices = engine.legal_actions(revealed.state, 0)
    selected = next(
        action
        for action in choices
        if dict(action.arguments).get("post_id")
        == "emperor-sardaukar-dutiful-service"
    )

    result = engine.apply(revealed.state, selected)

    assert {action.action_id for action in choices} == {
        "defer_reveal_choice",
        "place_reveal_spy",
    }
    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (
        "emperor-sardaukar-dutiful-service",
    )
    assert result.events[0].kind == "spy_placed"
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_public_spectacle_reveal_recalls_before_placing_with_empty_supply() -> None:
    spectacle = _imperium_instance("public_spectacle")
    original_posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spectacle,),
            spies_supply=0,
            spy_post_ids=original_posts,
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    recall = next(
        action
        for action in legal_reveal_spy_actions(revealed.state, 0)
        if action.action_id == "recall_spy_for_reveal_placement"
    )

    recalled = apply_reveal_spy_action(revealed.state, recall)
    placements = legal_reveal_spy_actions(recalled.state, 0)
    destination = next(
        action
        for action in placements
        if dict(action.arguments)["post_id"] not in original_posts
    )
    result = apply_reveal_spy_action(recalled.state, destination)

    recalled_post = dict(recall.arguments)["post_id"]
    destination_post = dict(destination.arguments)["post_id"]
    assert recall.action_id == "recall_spy_for_reveal_placement"
    assert {action.action_id for action in placements} == {"place_reveal_spy"}
    assert result.state.players[0].spies_supply == 0
    assert result.state.players[0].spy_post_ids == (
        *(post_id for post_id in original_posts if post_id != recalled_post),
        destination_post,
    )
    assert tuple(event.kind for event in (*recalled.events, *result.events)) == (
        "spy_recalled",
        "spy_placed",
    )


def test_public_spectacle_reveal_may_pass_without_a_spy_in_supply() -> None:
    # Spy icon: "If you have no Spies in your supply, you may first recall
    # one of your Spies for no effect" [Main p. 20] [Main p. 11]; the Spy is
    # mandatory only while one is in the supply (OQ-057 (14)), so with all
    # three Spies on the board the owner may decline and keep them.
    spectacle = _imperium_instance("public_spectacle")
    original_posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spectacle,),
            spies_supply=0,
            spy_post_ids=original_posts,
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    choices = legal_reveal_spy_actions(revealed, 0)

    assert tuple(action.action_id for action in choices) == (
        "decline_reveal_spy_recall",
        *("recall_spy_for_reveal_placement",) * 3,
    )
    declined = engine.apply(revealed, choices[0]).state

    assert declined.players[0].spy_post_ids == original_posts
    assert declined.players[0].spies_supply == 0
    assert declined.decision_stack[-1].kind == "reveal"
    assert "finish_reveal" in {
        action.action_id for action in engine.legal_actions(declined, 0)
    }


def _post_choice(actions: tuple[DomainAction, ...], post_id: str) -> DomainAction:
    return next(
        action
        for action in actions
        if action.action_id == "place_reveal_spy"
        and dict(action.arguments)["post_id"] == post_id
    )


def test_covert_operation_reveal_places_two_spies_and_no_persuasion() -> None:
    # Covert Operation's Reveal box prints two Spy icons and no Persuasion
    # [Covert Operation card] (BGG inventory: "+2 Spies"). "Spy. Place one
    # Spy; take it from your supply and put it on an unoccupied observation
    # post" [Main p. 20]: one placement per icon. The engine used to give two
    # Persuasion and no Spy.
    covert = _imperium_instance("covert_operation")
    state = _state(PlayerState(player_id=0, hand=(covert,)))
    engine = UprisingRulesEngine()
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    first_post, second_post = (post.post_id for post in OBSERVATION_POSTS[:2])

    first_choices = engine.legal_actions(revealed, 0)
    first = engine.apply(revealed, _post_choice(first_choices, first_post))
    second_choices = engine.legal_actions(first.state, 0)
    second = engine.apply(first.state, _post_choice(second_choices, second_post))

    assert dict(revealed.decision_stack[-2].context)["persuasion"] == 0
    assert {action.action_id for action in first_choices} == {
        "defer_reveal_choice",
        "place_reveal_spy",
    }
    # The second icon is a placement of its own, on another empty post.
    assert {action.action_id for action in second_choices} == {
        "defer_reveal_choice",
        "place_reveal_spy",
    }
    assert first_post not in {
        dict(action.arguments).get("post_id") for action in second_choices
    }
    owner = second.state.players[0]
    assert owner.spies_supply == 1
    assert owner.spy_post_ids == (first_post, second_post)
    assert [event.kind for event in (*first.events, *second.events)] == [
        "spy_placed",
        "spy_placed",
    ]
    assert dict(second.state.decision_stack[-1].context)["persuasion"] == 0
    assert legal_finish_reveal_actions(second.state, 0)


def test_covert_operation_second_spy_waits_like_any_reveal_choice() -> None:
    # Reveal effects resolve in any order [Main p. 12]: the second Spy icon
    # can be put off, and the Reveal cannot finish while it can still open.
    covert = _imperium_instance("covert_operation")
    state = _state(PlayerState(player_id=0, hand=(covert,)))
    engine = UprisingRulesEngine()
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    first_post = OBSERVATION_POSTS[0].post_id
    first = engine.apply(
        revealed, _post_choice(engine.legal_actions(revealed, 0), first_post)
    )

    deferred = engine.apply(
        first.state, DomainAction(action_id="defer_reveal_choice", actor=0)
    )

    assert legal_finish_reveal_actions(deferred.state, 0) == ()
    assert DomainAction(
        action_id="resume_reveal_choice",
        actor=0,
        arguments=(("effect", "place_spy"),),
    ) in engine.legal_actions(deferred.state, 0)


def test_covert_operation_spy_icons_follow_the_plain_reveal_spy_rules() -> None:
    # Each icon is the plain Spy icon, like Public Spectacle's: "If you have
    # no Spies in your supply, you may first recall one of your Spies for no
    # effect" [Main pp. 11, 20] (uprising-systems.md, OQ-057 (14)). Both of
    # Covert Operation's icons offer exactly Public Spectacle's choices.
    posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])

    def revealed_with(card_id: str, supply: int, placed: tuple[str, ...]) -> GameState:
        card = _imperium_instance(card_id)
        state = _state(
            PlayerState(
                player_id=0, hand=(card,), spies_supply=supply, spy_post_ids=placed
            )
        )
        return begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state

    covert_empty = revealed_with("covert_operation", 0, posts)
    spectacle_empty = revealed_with("public_spectacle", 0, posts)
    assert legal_reveal_spy_actions(covert_empty, 0) == legal_reveal_spy_actions(
        spectacle_empty, 0
    )

    # The first icon takes the last Spy in supply; the second then meets an
    # empty supply exactly as Public Spectacle's icon would.
    covert_one = revealed_with("covert_operation", 1, posts[:2])
    first = apply_reveal_spy_action(
        covert_one,
        _post_choice(legal_reveal_spy_actions(covert_one, 0), posts[2]),
    ).state
    assert first.players[0].spies_supply == 0
    assert legal_reveal_spy_actions(first, 0) == legal_reveal_spy_actions(
        spectacle_empty, 0
    )
    recall = next(
        action
        for action in legal_reveal_spy_actions(first, 0)
        if action.action_id == "recall_spy_for_reveal_placement"
    )
    recalled = apply_reveal_spy_action(first, recall).state
    target = next(
        action
        for action in legal_reveal_spy_actions(recalled, 0)
        if dict(action.arguments)["post_id"] not in posts
    )
    placed = apply_reveal_spy_action(recalled, target).state
    assert len(placed.players[0].spy_post_ids) == 3
    assert legal_finish_reveal_actions(placed, 0)


def test_wheels_within_wheels_reveals_for_persuasion_and_places_a_spy() -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    state = _state(PlayerState(player_id=0, hand=(wheels,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    placement = legal_reveal_spy_actions(revealed.state, 0)[0]

    result = apply_reveal_spy_action(revealed.state, placement)

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (
        dict(placement.arguments)["post_id"],
    )


def test_undercover_asset_reveal_may_place_a_spy() -> None:
    undercover = _imperium_instance("undercover_asset")
    state = _state(PlayerState(player_id=0, hand=(undercover,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    actions = legal_reveal_spy_actions(revealed.state, 0)

    assert {action.action_id for action in actions} == {
        "gain_two_reveal_strength",
        "place_reveal_spy",
    }
    placement = next(
        action for action in actions if action.action_id == "place_reveal_spy"
    )
    result = apply_reveal_spy_action(revealed.state, placement)

    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (
        dict(placement.arguments)["post_id"],
    )


def test_undercover_asset_reveal_may_gain_two_strength() -> None:
    undercover = _imperium_instance("undercover_asset")
    owner = PlayerState(
        player_id=0,
        hand=(undercover,),
        troops_supply=8,
        troops_conflict=1,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    strength = next(
        action
        for action in legal_reveal_spy_actions(revealed, 0)
        if action.action_id == "gain_two_reveal_strength"
    )

    result = apply_reveal_spy_action(revealed, strength)

    assert result.state.players[0].combat_strength == 4
    context = dict(result.state.decision_stack[-1].context)
    assert context["strength"] == 4
    assert context["optional_sword_strength"] == 2
    assert tuple(event.kind for event in result.events) == (
        "reveal_strength_gained",
    )


def test_undercover_asset_reveal_strength_needs_a_conflict_unit() -> None:
    undercover = _imperium_instance("undercover_asset")
    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(undercover,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    strength = next(
        action
        for action in legal_reveal_spy_actions(revealed, 0)
        if action.action_id == "gain_two_reveal_strength"
    )

    result = apply_reveal_spy_action(revealed, strength)

    assert result.state.players[0].combat_strength == 0
    context = dict(result.state.decision_stack[-1].context)
    assert context["strength"] == 0
    assert context["optional_sword_strength"] == 2


def test_undercover_asset_commits_to_spy_after_empty_supply_recall() -> None:
    undercover = _imperium_instance("undercover_asset")
    original_posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    owner = PlayerState(
        player_id=0,
        hand=(undercover,),
        spies_supply=0,
        spy_post_ids=original_posts,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    recall = next(
        action
        for action in legal_reveal_spy_actions(revealed, 0)
        if action.action_id == "recall_spy_for_reveal_placement"
    )

    recalled = apply_reveal_spy_action(revealed, recall).state

    assert {action.action_id for action in legal_reveal_spy_actions(recalled, 0)} == {
        "place_reveal_spy"
    }


def test_unswerving_loyalty_reveals_for_persuasion_and_recruits_one() -> None:
    loyalty = _imperium_instance("unswerving_loyalty")
    state = _state(PlayerState(player_id=0, hand=(loyalty,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    revealed = _take_reveal_gains(result.state)

    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 1
    assert revealed.players[0].troops_supply == 8
    assert revealed.players[0].troops_garrison == 4


_LOYALTY_MOVE = "may_deploy_or_retreat_one_troop_if_fremen_bond"


def test_unswerving_loyalty_fremen_bond_deploys_or_retreats_one_troop() -> None:
    # "Fremen Bond : You may deploy or retreat one of your troops."
    # [Unswerving Loyalty card]. "Fremen Bond -- You may use this effect if
    # you have one or more other Fremen cards in play" [Main p. 20]
    # (uprising-systems.md); here Maula Pistol, played on an Agent turn.
    # The engine used to offer no such choice.
    loyalty = _imperium_instance("unswerving_loyalty")
    maula = _imperium_instance("maula_pistol")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(loyalty,),
            in_play=(maula,),
            troops_supply=9,
            troops_garrison=2,
            troops_conflict=1,
            combat_strength=2,
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state

    top = revealed.decision_stack[-1]
    assert dict(top.context)["reveal_choice_effect"] == _LOYALTY_MOVE
    actions = legal_reveal_troop_move_actions(revealed, 0)
    assert [action.action_id for action in actions] == [
        "decline_reveal_troop_move",
        "deploy_reveal_card_troop",
        "retreat_reveal_card_troop",
    ]
    deployed = apply_reveal_troop_move(revealed, actions[1]).state
    owner = deployed.players[0]
    assert (owner.troops_garrison, owner.troops_conflict) == (1, 2)
    assert dict(deployed.decision_stack[-1].context)["strength"] == 4
    retreated = apply_reveal_troop_move(revealed, actions[2]).state
    owner = retreated.players[0]
    assert (owner.troops_garrison, owner.troops_conflict) == (3, 0)
    assert dict(retreated.decision_stack[-1].context)["strength"] == 0
    declined = apply_reveal_troop_move(revealed, actions[0]).state
    assert declined.players[0] == revealed.players[0]
    assert declined.decision_stack[-1].kind == "reveal"


def test_unswerving_loyalty_moves_a_commander_in_a_bloodlines_only_catalog() -> None:
    # "You may deploy or retreat one of your troops" [Unswerving Loyalty
    # card]; a Sardaukar Commander "is a 'troop'" [Bloodlines p. 4]. The
    # card is in every ruleset, so its Commander moves must encode without
    # Immortality too (a merge-time gap between two audit slices).
    from dune_imperium.adapters.action_codec import ActionCodec

    config = RulesetConfig(bloodlines=True)
    loyalty = _imperium_instance("unswerving_loyalty")
    maula = _imperium_instance("maula_pistol")
    owner = PlayerState(
        player_id=0,
        hand=(loyalty,),
        in_play=(maula,),
        commanders_supply=0,
        commanders_garrison=1,
        commanders_conflict=1,
        combat_strength=2,
    )
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=_state(PlayerState(player_id=0)).decision_stack,
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    actions = legal_reveal_troop_move_actions(revealed, 0)
    assert {
        (action.action_id, dict(action.arguments).get("commanders"))
        for action in actions
    } >= {("deploy_reveal_card_troop", 1), ("retreat_reveal_card_troop", 1)}
    codec = ActionCodec(config)
    for action in actions:
        assert codec.decode(codec.encode(action), actor=0) == action


def test_unswerving_loyalty_offers_no_troop_move_without_a_fremen_bond() -> None:
    # No other Fremen card in play: the Bond line does nothing [Main p. 20].
    loyalty = _imperium_instance("unswerving_loyalty")
    state = _state(
        PlayerState(player_id=0, hand=(loyalty,), troops_supply=9, troops_garrison=3)
    )
    revealed = _take_reveal_gains(
        begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    )

    actions = UprisingRulesEngine().legal_actions(revealed, 0)
    assert revealed.decision_stack[-1].kind == "reveal"
    assert legal_reveal_troop_move_actions(revealed, 0) == ()
    assert "resume_reveal_choice" not in {action.action_id for action in actions}
    assert "finish_reveal" in {action.action_id for action in actions}


def test_two_unswerving_loyalties_bond_each_other() -> None:
    # "Two cards with Fremen Bond can activate one another, regardless of
    # order played." [Main p. 20]
    first = _imperium_instance("unswerving_loyalty", 0)
    second = _imperium_instance("unswerving_loyalty", 1)
    state = _state(
        PlayerState(
            player_id=0, hand=(first, second), troops_supply=9, troops_garrison=3
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state

    choices = [
        dict(frame.context)
        for frame in revealed.decision_stack
        if dict(frame.context).get("reveal_choice_effect") == _LOYALTY_MOVE
    ]
    assert sorted(context["reveal_card_id"] for context in choices) == sorted(
        (first, second)
    )


def test_unswerving_loyalty_may_deploy_the_troop_it_recruits() -> None:
    # With no troop yet, the Bond move waits in the deferred queue [Main p. 12]
    # until the card's own recruit (taken in the owner's order, OQ-045) gives
    # it one to deploy.
    loyalty = _imperium_instance("unswerving_loyalty")
    maula = _imperium_instance("maula_pistol")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(loyalty,),
            in_play=(maula,),
            troops_supply=12,
            troops_garrison=0,
        )
    )
    engine = UprisingRulesEngine()
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.decision_stack[-1].kind == "reveal"
    assert "resume_reveal_choice" not in {
        action.action_id for action in engine.legal_actions(revealed, 0)
    }

    recruited = _take_reveal_gains(revealed)
    resume = DomainAction(
        action_id="resume_reveal_choice",
        actor=0,
        arguments=(("effect", _LOYALTY_MOVE),),
    )
    assert recruited.players[0].troops_garrison == 1
    assert resume in engine.legal_actions(recruited, 0)
    assert "finish_reveal" not in {
        action.action_id for action in engine.legal_actions(recruited, 0)
    }
    resumed = engine.apply(recruited, resume).state
    deployed = engine.apply(
        resumed, DomainAction(action_id="deploy_reveal_card_troop", actor=0)
    ).state
    assert deployed.players[0].troops_conflict == 1
    assert deployed.players[0].troops_garrison == 0


def test_stilgar_counts_fremen_cards_played_on_agent_turns() -> None:
    # Stilgar, The Devoted: "2 Persuasion for each Fremen card you have in
    # play (including this one)" [Stilgar, The Devoted card]. In play is
    # "Cards you play on Agent turns and reveal during your Reveal turn"
    # [Main p. 20] (docs/rules/uprising-systems.md: "Agent turn에 play한
    # 카드와 현재 Reveal turn에 reveal한 카드는 ... in play다"), and the FAQ
    # rules the same wording on Liet Kynes: "Cards from your Agent turns this
    # round and your current Reveal turn count" [FAQ p. 2]. Unswerving
    # Loyalty played on an Agent turn is the third Fremen card: 3 x 2 plus
    # Maula Pistol's and Truthtrance's printed Persuasion. The old reading
    # counted only the revealed cards and gave 6.
    stilgar = _imperium_instance("stilgar_the_devoted")
    maula = _imperium_instance("maula_pistol")
    truthtrance = _imperium_instance("truthtrance")
    previously_played_fremen = _imperium_instance("unswerving_loyalty")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(stilgar, maula, truthtrance),
            in_play=(previously_played_fremen,),
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 8


def test_stilgar_counts_itself_as_a_revealed_fremen_card() -> None:
    stilgar = _imperium_instance("stilgar_the_devoted")
    state = _state(PlayerState(player_id=0, hand=(stilgar,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2


def test_leadership_gains_strength_per_other_revealed_sword_card() -> None:
    leadership = _imperium_instance("leadership")
    dagger = _instance("dagger")
    rhetoric = _imperium_instance("dangerous_rhetoric")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(leadership, dagger, rhetoric),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3
    assert result.state.players[0].combat_strength == 7


def test_leadership_does_not_count_itself_or_an_agent_card_for_bonus() -> None:
    leadership = _imperium_instance("leadership")
    played_dagger = _instance("dagger")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(leadership,),
            in_play=(played_dagger,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert result.state.players[0].combat_strength == 3


def test_sardaukar_coordination_counts_each_revealed_emperor_card() -> None:
    first = _imperium_instance("sardaukar_coordination", 0)
    second = _imperium_instance("sardaukar_coordination", 1)
    soldier = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        hand=(first, second, soldier),
        troops_supply=8,
        troops_conflict=1,
    )

    result = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    # Reveal box: Persuasion 2 (no base sword) plus "+[sword] for each
    # Emperor card you revealed (including this one)" [card face]. All three
    # cards are Emperor, so each Coordination adds 3 swords: 3 + 3 from the
    # two Coordinations, + 1 from the Soldier's printed sword, + 2 from the
    # one troop in the Conflict = 9. Persuasion: 2 + 2 (Coordinations) + 1
    # (Soldier) = 5.
    assert result.state.players[0].combat_strength == 9
    assert dict(result.state.decision_stack[-1].context)["strength"] == 9
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 5


def test_sardaukar_coordination_ignores_emperor_agent_cards_in_play() -> None:
    coordination = _imperium_instance("sardaukar_coordination")
    played_soldier = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        hand=(coordination,),
        in_play=(played_soldier,),
        troops_supply=8,
        troops_conflict=1,
    )

    result = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    # The Soldier in play (not revealed this turn) does not count toward the
    # per-revealed-Emperor multiplier: 1 troop (strength 2) + 1 sword from
    # the lone revealed Coordination = 3.
    assert result.state.players[0].combat_strength == 3


def test_sardaukar_coordination_ignores_a_revealed_overthrow() -> None:
    # Overthrow prints no affiliation banner [card face; BGG inventory row
    # blank] and is no longer an Emperor card, so revealing it alongside
    # Sardaukar Coordination must not add to the "+[sword] for each Emperor
    # card you revealed (including this one)" count: only the lone
    # Coordination counts itself, for 1 sword. Overthrow's own printed Reveal
    # (2 Persuasion, 2 strength) still applies on its own. Total: 1 troop
    # (strength 2) + 1 (Coordination's own count) + 2 (Overthrow's own
    # sword) = 5 strength; 2 (Coordination) + 2 (Overthrow) = 4 Persuasion.
    coordination = _imperium_instance("sardaukar_coordination")
    overthrow = _imperium_instance("overthrow")
    owner = PlayerState(
        player_id=0,
        hand=(coordination, overthrow),
        troops_supply=8,
        troops_conflict=1,
    )

    result = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert result.state.players[0].combat_strength == 5
    assert dict(result.state.decision_stack[-1].context)["strength"] == 5
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 4


def test_shishakli_reveal_gains_fremen_influence_only_with_bond() -> None:
    shishakli = _imperium_instance("shishakli")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(
        PlayerState(
            player_id=0,
            hand=(shishakli,),
            troops_supply=8,
            troops_conflict=1,
        )
    )
    with_bond = _state(
        PlayerState(
            player_id=0,
            hand=(shishakli, maula),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )
    with_result = _with_gains(
        begin_reveal_turn(
            with_bond,
            legal_reveal_actions(with_bond, 0)[0],
        )
    )

    assert without_result.state.players[0].influence.fremen == 0
    assert without_result.state.players[0].combat_strength == 4
    # The Bond Influence is a Reveal gain the owner takes (OQ-045).
    assert with_result.state.players[0].influence.fremen == 1
    assert with_result.state.players[0].combat_strength == 5
    assert tuple(event.kind for event in with_result.events) == (
        "reveal_started",
        "influence_gained",
    )


def test_tread_in_darkness_reveals_for_persuasion_and_strength() -> None:
    tread = _imperium_instance("tread_in_darkness")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(tread,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].combat_strength == 3


def test_space_time_folding_reveals_for_one_persuasion() -> None:
    folding = _imperium_instance("space_time_folding")
    state = _state(PlayerState(player_id=0, hand=(folding,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_high_council_and_assembly_hall_add_reveal_persuasion() -> None:
    state = _state(
        PlayerState(
            player_id=0,
            high_council=True,
            agents_available=1,
            agent_locations=("assembly_hall",),
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3


def test_reveal_strength_requires_a_unit_in_conflict() -> None:
    dagger = _instance("dagger")
    without_unit = _state(PlayerState(player_id=0, hand=(dagger,)))

    no_unit_result = begin_reveal_turn(
        without_unit,
        legal_reveal_actions(without_unit, 0)[0],
    )
    assert no_unit_result.state.players[0].combat_strength == 0

    with_unit = _state(
        PlayerState(
            player_id=0,
            hand=(dagger,),
            troops_supply=8,
            troops_conflict=1,
        )
    )
    unit_result = begin_reveal_turn(
        with_unit,
        legal_reveal_actions(with_unit, 0)[0],
    )
    assert unit_result.state.players[0].combat_strength == 3


def test_reserve_cards_contribute_their_printed_reveal_values() -> None:
    prepare = "reserve:prepare_the_way:7"
    spice = "reserve:the_spice_must_flow:9"
    state = _state(
        PlayerState(
            player_id=0,
            hand=(prepare, spice),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 2
    # The Spice Must Flow's Reveal box is a spice hexagon "1" [Main p. 20],
    # not a sword, so only the 1 troop's own strength (2) counts here.
    assert context["strength"] == 2

    taken = _with_gains(result)
    assert taken.state.players[0].resources.spice == 1


def test_transcribed_imperium_cards_contribute_reveal_values() -> None:
    maula = _imperium_instance("maula_pistol")
    truthtrance = _imperium_instance("truthtrance")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(maula, truthtrance),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 2
    assert context["strength"] == 3


def test_sardaukar_soldier_contributes_reveal_values() -> None:
    sardaukar = _imperium_instance("sardaukar_soldier")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(sardaukar,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_hidden_missive_contributes_reveal_values() -> None:
    hidden_missive = _imperium_instance("hidden_missive")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(hidden_missive,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_desert_survival_contributes_reveal_values() -> None:
    desert_survival = _imperium_instance("desert_survival")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(desert_survival,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_smugglers_harvester_contributes_reveal_persuasion() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")
    state = _state(PlayerState(player_id=0, hand=(harvester,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_smugglers_haven_gains_spice_while_spying_on_a_maker_space() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        spies_supply=2,
        spy_post_ids=("arrakis-hagga-basin",),
    )
    state = _state(owner)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    result = _with_gains(result)

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].resources.spice == 2


def test_smugglers_haven_has_no_spice_bonus_at_a_non_maker_post() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    state = _state(owner)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].resources.spice == 0


def test_price_is_no_object_reveals_for_persuasion_and_solari() -> None:
    price = _imperium_instance("price_is_no_object")
    state = _state(PlayerState(player_id=0, hand=(price,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    result = _with_gains(result)

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].resources.solari == 2


def test_subversive_advisor_reveals_for_one_persuasion() -> None:
    subversive = _imperium_instance("subversive_advisor")
    state = _state(PlayerState(player_id=0, hand=(subversive,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    result = _with_gains(result)

    # The Reveal band prints a single blue Persuasion diamond "1" [card
    # face], not a Solari coin.
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].resources.solari == 0


def test_interstellar_trade_persuasion_uses_completed_contracts_at_reveal() -> None:
    interstellar = _imperium_instance(
        "interstellar_trade",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(interstellar,),
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
        ),
    )
    state = _state(owner, choam_module=True)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3


def test_delivery_agreement_below_four_contracts_pays_spice_by_its_choice() -> None:
    # "[1 spice] -OR- If you have completed four or more contracts: Trash
    # this card -> [1 VP]" [Delivery Agreement card]: the spice is one branch
    # of the choice (docs/rules/player-turns.md: "completed Contract가 4개
    # 이상이면 그 Spice 대신 해당 card를 trash하고 Victory Point 1을 얻을 수
    # 있다"), so it is paid by keeping, never as a separate automatic gain.
    # With fewer than four Contracts keeping is the only branch.
    delivery = _imperium_instance(
        "delivery_agreement",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(delivery,),
        resources=Resources(spice=2),
        completed_contract_ids=("contract:arrakeen_i",),
    )
    state = _state(owner, choam_module=True)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert reveal_pending_gains(dict(result.state.decision_stack[-2].context)) == ()
    (keep,) = legal_contract_reveal_choice_actions(result.state, 0)
    assert keep.action_id == "keep_contract_reveal_spice"
    kept = apply_contract_reveal_choice(result.state, keep).state
    assert kept.players[0].resources.spice == 3
    assert dict(kept.decision_stack[-1].context)["persuasion"] == 0


@pytest.mark.parametrize(
    ("card_id", "spice"), (("priority_contracts", 2), ("delivery_agreement", 1))
)
@pytest.mark.parametrize(
    "pick", ("keep_contract_reveal_spice", "trash_contract_reveal_for_vp")
)
def test_a_fourth_contract_completed_mid_reveal_offers_spice_or_vp_never_both(
    card_id: str, spice: int, pick: str
) -> None:
    # "[spice] -OR- If you have completed four or more contracts: Trash this
    # card -> [1 VP]" [Priority Contracts card] [Delivery Agreement card]:
    # exactly one branch. With three Contracts the owner may put the choice
    # off, acquire The Spice Must Flow to complete the Acquire contract, and
    # then trash for the Victory Point (OQ-028 (b)); the spice was paid on top
    # of the Victory Point, or twice on keeping, before 2026-09-26.
    card = _imperium_instance(card_id, choam_module=True)
    owner = PlayerState(
        player_id=0,
        hand=(card,),
        active_contract_ids=("contract:acquire",),
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
        ),
        reveal_persuasion_bonus=9,
    )
    state = replace(
        _state(owner, choam_module=True),
        reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 10)),
    )
    engine = UprisingRulesEngine()

    def take(current: GameState, action_id: str, argument: str = "") -> GameState:
        action = next(
            action
            for action in engine.legal_actions(current, 0)
            if action.action_id == action_id and argument in str(action.arguments)
        )
        return engine.apply(current, action).state

    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert tuple(
        action.action_id for action in legal_contract_reveal_choice_actions(revealed, 0)
    ) == ("keep_contract_reveal_spice",)
    deferred = take(revealed, "defer_reveal_choice")
    assert reveal_pending_gains(dict(deferred.decision_stack[-1].context)) == ()
    bought = take(deferred, "acquire_reserve", "the_spice_must_flow")
    assert len(bought.players[0].completed_contract_ids) == 4
    resumed = take(bought, "resume_reveal_choice")
    assert tuple(
        action.action_id for action in legal_contract_reveal_choice_actions(resumed, 0)
    ) == ("keep_contract_reveal_spice", "trash_contract_reveal_for_vp")

    done = _take_reveal_gains(take(resumed, pick))
    before, after = bought.players[0], done.players[0]
    if pick == "keep_contract_reveal_spice":
        assert after.resources.spice == before.resources.spice + spice
        assert after.victory_points == before.victory_points
    else:
        assert after.resources.spice == before.resources.spice
        assert after.victory_points == before.victory_points + 1
        assert card in after.trashed
    assert legal_contract_reveal_choice_actions(done, 0) == ()
    assert "finish_reveal" in {
        action.action_id for action in engine.legal_actions(done, 0)
    }


def test_four_contract_reveal_can_keep_spice_or_trash_the_card_for_vp() -> None:
    priority = _imperium_instance(
        "priority_contracts",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(priority,),
        resources=Resources(spice=3),
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
            "contract:espionage_i",
        ),
    )
    state = _state(owner, choam_module=True)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    actions = legal_contract_reveal_choice_actions(revealed, 0)

    assert tuple(action.action_id for action in actions) == (
        "keep_contract_reveal_spice",
        "trash_contract_reveal_for_vp",
    )
    assert revealed.players[0].resources.spice == 3

    kept = apply_contract_reveal_choice(revealed, actions[0])
    assert kept.state.players[0].resources.spice == 5
    assert priority in kept.state.players[0].in_play
    assert kept.events[0].kind == "contract_reveal_spice_gained"

    trashed = apply_contract_reveal_choice(revealed, actions[1])
    assert trashed.state.players[0].resources.spice == 3
    assert trashed.state.players[0].victory_points == owner.victory_points + 1
    assert trashed.state.players[0].in_play == ()
    assert trashed.state.players[0].trashed == (priority,)


def test_four_contract_trash_for_vp_is_withheld_once_the_card_is_gone() -> None:
    # The self-trash is the Victory Point's cost, adjudicated at resolution
    # time [Main pp. 9, 20]: once another effect trashed the card while this
    # choice was pending, only the Spice branch remains.
    priority = _imperium_instance(
        "priority_contracts",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(priority,),
        resources=Resources(spice=3),
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
            "contract:espionage_i",
        ),
    )
    state = _state(owner, choam_module=True)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    gone = replace(
        revealed,
        players=(
            replace(revealed.players[0], in_play=(), trashed=(priority,)),
            *revealed.players[1:],
        ),
    )

    actions = legal_contract_reveal_choice_actions(gone, 0)

    assert tuple(action.action_id for action in actions) == (
        "keep_contract_reveal_spice",
    )


def test_fedaykin_stilltent_gains_water_when_revealed() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    state = _state(PlayerState(player_id=0, hand=(stilltent,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    result = _with_gains(result)

    assert result.state.players[0].resources.water == 2
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0


def test_northern_watermaster_gains_spice_only_with_fremen_bond() -> None:
    watermaster = _imperium_instance("northern_watermaster")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(PlayerState(player_id=0, hand=(watermaster,)))
    with_bond = _state(PlayerState(player_id=0, hand=(watermaster, maula)))

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )

    without_result = _with_gains(without_result)
    with_result = begin_reveal_turn(
        with_bond,
        legal_reveal_actions(with_bond, 0)[0],
    )
    with_result = _with_gains(with_result)

    assert without_result.state.players[0].resources.spice == 0
    assert with_result.state.players[0].resources.spice == 2
    assert dict(with_result.state.decision_stack[-1].context)["persuasion"] == 2


def test_maker_keeper_contributes_two_reveal_persuasion() -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    state = _state(PlayerState(player_id=0, hand=(maker_keeper,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2


def test_southern_elders_applies_unconditional_and_bond_reveal_effects() -> None:
    southern_elders = _imperium_instance("southern_elders")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(PlayerState(player_id=0, hand=(southern_elders,)))
    with_bond = _state(PlayerState(player_id=0, hand=(southern_elders, maula)))

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )

    without_result = _with_gains(without_result)
    with_result = begin_reveal_turn(
        with_bond,
        legal_reveal_actions(with_bond, 0)[0],
    )
    with_result = _with_gains(with_result)

    assert without_result.state.players[0].resources.water == 2
    assert dict(without_result.state.decision_stack[-1].context)["persuasion"] == 0
    assert with_result.state.players[0].resources.water == 2
    assert dict(with_result.state.decision_stack[-1].context)["persuasion"] == 3


def test_weirding_woman_contributes_reveal_values() -> None:
    weirding_woman = _imperium_instance("weirding_woman")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(weirding_woman,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_ecological_testing_station_gains_water_with_fremen_bond() -> None:
    station = _imperium_instance("ecological_testing_station")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(PlayerState(player_id=0, hand=(station,)))
    with_bond = _state(PlayerState(player_id=0, hand=(station, maula)))

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )

    without_result = _with_gains(without_result)
    with_result = begin_reveal_turn(
        with_bond,
        legal_reveal_actions(with_bond, 0)[0],
    )
    with_result = _with_gains(with_result)

    assert without_result.state.players[0].resources.water == 1
    assert with_result.state.players[0].resources.water == 2
    assert dict(with_result.state.decision_stack[-1].context)["persuasion"] == 2


def test_paracompass_reveal_scales_with_council_and_swordmaster() -> None:
    paracompass = _imperium_instance("paracompass")
    neither = _state(PlayerState(player_id=0, hand=(paracompass,)))
    council = _state(
        PlayerState(player_id=0, hand=(paracompass,), high_council=True)
    )
    both = _state(
        PlayerState(
            player_id=0,
            hand=(paracompass,),
            high_council=True,
            swordmaster_acquired=True,
            agents_available=3,
        )
    )

    neither_result = begin_reveal_turn(
        neither,
        legal_reveal_actions(neither, 0)[0],
    )
    council_result = begin_reveal_turn(
        council,
        legal_reveal_actions(council, 0)[0],
    )
    both_result = begin_reveal_turn(
        both,
        legal_reveal_actions(both, 0)[0],
    )

    assert dict(neither_result.state.decision_stack[-1].context)["persuasion"] == 0
    assert dict(council_result.state.decision_stack[-1].context)["persuasion"] == 4
    assert dict(both_result.state.decision_stack[-1].context)["persuasion"] == 5


def test_overthrow_recruits_and_contributes_reveal_values() -> None:
    overthrow = _imperium_instance("overthrow")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(overthrow,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    revealed = _take_reveal_gains(result.state)
    owner = revealed.players[0]
    context = dict(revealed.decision_stack[-1].context)

    assert owner.troops_supply == 7
    assert owner.troops_garrison == 4
    assert context["persuasion"] == 2
    assert context["strength"] == 4


def test_reveal_preserves_agent_cards_already_in_play() -> None:
    played = _instance("dagger", 0)
    revealed = _instance("dagger", 1)
    state = _state(PlayerState(player_id=0, hand=(revealed,), in_play=(played,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert result.state.players[0].in_play == (played, revealed)


def test_reveal_cleanup_discards_in_play_but_preserves_late_drawn_hand() -> None:
    revealed = _instance("diplomacy")
    retained = _instance("dagger")
    state = _state(PlayerState(player_id=0, hand=(revealed,)))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    owner = replace(state.players[0], hand=(retained,))
    state = replace(state, players=(owner, *state.players[1:]))

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])
    owner = result.state.players[0]

    assert owner.has_revealed is True
    assert result.state.reveal_order == (0,)
    assert owner.in_play == ()
    assert owner.discard_pile == (revealed,)
    assert owner.hand == (retained,)


def test_reveal_cleanup_skips_players_who_already_revealed() -> None:
    state = _state(PlayerState(player_id=0))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    players = (
        state.players[0],
        replace(state.players[1], has_revealed=True),
        state.players[2],
        replace(state.players[3], has_revealed=True),
    )
    state = replace(state, players=players)

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])

    decision = result.state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 2


def test_last_reveal_cleanup_enters_combat_without_pending_decision() -> None:
    state = _state(PlayerState(player_id=0))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    players = (
        state.players[0],
        *(replace(player, has_revealed=True) for player in state.players[1:]),
    )
    state = replace(state, players=players)

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])

    assert result.state.phase is GamePhase.COMBAT
    assert result.state.decision_stack == ()
    assert all(player.has_revealed for player in result.state.players)


def test_four_empty_reveal_turns_follow_seat_order_into_combat() -> None:
    state = _state(PlayerState(player_id=0))
    state = replace(
        state,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:2",
                decision=PlayerDecision(owner=2, prompt="Choose a turn"),
            ),
        ),
    )

    visited: list[int] = []
    for player in (2, 3, 0, 1):
        decision = state.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        visited.append(decision.owner)
        state = begin_reveal_turn(
            state,
            legal_reveal_actions(state, player)[0],
        ).state
        state = finish_reveal_turn(
            state,
            legal_finish_reveal_actions(state, player)[0],
        ).state

    assert visited == [2, 3, 0, 1]
    assert state.reveal_order == (2, 3, 0, 1)
    assert state.phase is GamePhase.COMBAT
    assert state.decision_stack == ()


# --- Immediate reveal of cards that arrive during a Reveal turn [FAQ p. 3] --


def _with_late_hand(state: GameState, card_id: str) -> GameState:
    """Simulate a card landing in seat 0's hand mid-Reveal, before revealing it."""

    players = tuple(
        replace(player, hand=(card_id,)) if player.player_id == 0 else player
        for player in state.players
    )
    return replace(state, players=players)


def test_late_reveal_stilgar_gains_a_persuasion_increment_from_a_fremen_arrival() -> (
    None
):
    # Stilgar, The Devoted (per_in_play_faction=FREMEN) is already revealed;
    # a late-arriving Fremen card [FAQ p. 3] adds the increment its own
    # arrival causes on top of its own printed values, without recomputing
    # Stilgar's already-granted amount.
    stilgar = _imperium_instance("stilgar_the_devoted")
    maula = _imperium_instance("maula_pistol")
    state = _state(PlayerState(player_id=0, hand=(stilgar,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2

    arrived = _with_late_hand(revealed, maula)
    result = reveal_late_arrivals(arrived, 0, (maula,))
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].hand == ()
    assert result.state.players[0].in_play == (stilgar, maula)
    # maula's own Persuasion (1) plus the +2 Stilgar increment.
    assert context["persuasion"] == 2 + 1 + 2
    assert context["revealed_card_count"] == 2
    assert context["revealed_card_001"] == maula


def test_late_reveal_leadership_gains_strength_from_a_late_sword_card() -> None:
    # Leadership (strength_per_other_sword_card=1) is already revealed; a
    # late-arriving card with positive strength adds +1 to the group's
    # strength beyond that card's own value [FAQ p. 3].
    leadership = _imperium_instance("leadership")
    dagger = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(leadership,),
        troops_supply=8,
        troops_conflict=1,
    )
    state = _state(owner)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.players[0].combat_strength == 3

    arrived = _with_late_hand(revealed, dagger)
    result = reveal_late_arrivals(arrived, 0, (dagger,))
    context = dict(result.state.decision_stack[-1].context)

    # dagger's own strength (1) plus the +1 Leadership increment.
    assert result.state.players[0].combat_strength == 3 + 2
    assert context["strength"] == 5
    assert context["sword_strength"] == 3


def test_late_reveal_leadership_counts_an_already_revealed_sword_card() -> None:
    # Leadership arrives late; its own strength_per_other_sword_card effect
    # counts the already-revealed dagger's strength, recomputed purely over
    # the current revealed set [FAQ p. 3].
    leadership = _imperium_instance("leadership")
    dagger = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        troops_supply=8,
        troops_conflict=1,
    )
    state = _state(owner)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.players[0].combat_strength == 3

    arrived = _with_late_hand(revealed, leadership)
    result = reveal_late_arrivals(arrived, 0, (leadership,))
    context = dict(result.state.decision_stack[-1].context)

    # leadership's own strength (1) plus +1 for the already-revealed dagger.
    assert result.state.players[0].combat_strength == 3 + 2
    assert context["persuasion"] == 2
    assert context["strength"] == 5


def test_late_reveal_pushes_a_resolvable_reveal_choice_frame() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    state = _state(PlayerState(player_id=0, resources=Resources(solari=5)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.decision_stack[-1].kind == "reveal"

    arrived = _with_late_hand(revealed, corrinth_city)
    result = reveal_late_arrivals(arrived, 0, (corrinth_city,))

    assert result.state.decision_stack[-1].kind == "reveal_choice"
    actions = legal_corrinth_city_reveal_actions(result.state, 0)
    assert tuple(action.action_id for action in actions) == (
        "gain_five_reveal_solari",
        "take_high_council_from_reveal",
    )
    take_seat = actions[1]
    resolved = apply_corrinth_city_reveal(result.state, take_seat)

    assert resolved.state.players[0].high_council is True
    assert resolved.state.decision_stack[-1].kind == "reveal"


def test_late_reveal_grants_resource_effects_at_arrival() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    state = _state(PlayerState(player_id=0))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state

    arrived = _with_late_hand(revealed, stilltent)
    result = _with_gains(reveal_late_arrivals(arrived, 0, (stilltent,)))

    assert result.state.players[0].resources.water == 2
    assert result.state.players[0].in_play == (stilltent,)


def test_late_reveal_works_through_the_personal_draw_reshuffle_chance() -> None:
    # An empty personal deck routes the reveal-time draw through the
    # PERSONAL_DRAW_RESHUFFLE chance; the late-reveal hook on the
    # completion path [FAQ p. 3] must still fire once it resolves.
    discarded = _instance("dagger", 1)
    owner = PlayerState(player_id=0, discard_pile=(discarded,))
    state = _state(owner)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.decision_stack[-1].kind == "reveal"

    pending = draw_or_request_personal_cards(
        revealed, 0, 1, source="test:late_draw"
    )
    assert pending.state.decision_stack[-1].kind == "personal_draw_reshuffle"
    decision = pending.state.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)

    outcome = ChanceOutcome(decision.decision_id, (discarded,))
    result = apply_personal_draw_reshuffle(pending.state, outcome)

    assert result.state.decision_stack[-1].kind == "reveal"
    owner_after = result.state.players[0]
    assert owner_after.hand == ()
    assert owner_after.in_play == (discarded,)
    context = dict(result.state.decision_stack[-1].context)
    assert context["revealed_card_count"] == 1
    assert context["revealed_card_000"] == discarded


def test_cross_scaling_reveal_effects_have_no_eligibility_gates() -> None:
    # The late-reveal cross-increment path [FAQ p. 3] re-adjudicates a
    # per_revealed_faction/per_in_play_faction/strength_per_other_sword_card
    # effect's eligibility gates at arrival but never revokes an
    # already-granted amount. Today every such effect is unconditional, so
    # re-adjudication is vacuous; this pin fails the suite if future content
    # adds a gated one, which would need the increment logic to also track
    # revocation.
    entries = (*STARTING_DECK, *RESERVE_STACKS, *IMPERIUM_CARDS)
    scaling_effects = [
        effect
        for entry in entries
        for effect in entry.reveal_effects
        if effect.per_revealed_faction is not None
        or effect.per_in_play_faction is not None
        or effect.strength_per_other_sword_card
    ]

    assert len(scaling_effects) == 3
    for effect in scaling_effects:
        assert effect.requires_high_council is False
        assert effect.requires_swordmaster is False
        assert effect.minimum_spies_placed == 0
        assert effect.required_faction_bond is None
        assert effect.requires_spying_on_maker_space is False


# ---------------------------------------------------------------- free order


def test_reveal_choice_can_be_deferred_and_resumed_in_the_owners_order() -> None:
    # Two Spacing Guild's Favor copies each queue "pay 3 Spice for Influence".
    # Reveal effects resolve in any order the owner likes [Main p. 12]: the
    # first copy's choice is put off, the second resolves, the Reveal frame
    # stays open for acquisitions, and the deferred choice comes back later.
    first = _imperium_instance("spacing_guild_s_favor", 0)
    second = _imperium_instance("spacing_guild_s_favor", 1)
    state = _state(
        PlayerState(player_id=0, hand=(first, second), resources=Resources(spice=6))
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    top = revealed.decision_stack[-1]
    assert top.kind == "reveal_choice"
    assert dict(top.context)["reveal_card_id"] == first
    defer = DomainAction(action_id="defer_reveal_choice", actor=0)
    assert defer in engine.legal_actions(revealed, 0)

    deferred = engine.apply(revealed, defer)
    assert [event.kind for event in deferred.events] == ["reveal_choice_deferred"]
    assert dict(deferred.state.decision_stack[-1].context)["reveal_card_id"] == second
    reveal_frame = deferred.state.decision_stack[-2]
    assert reveal_frame.kind == "reveal"
    assert dict(reveal_frame.context)["deferred_reveal_choices"] == (
        f"{first}|may_pay_three_spice_for_influence"
    )

    pay = next(
        action
        for action in engine.legal_actions(deferred.state, 0)
        if action.action_id == "pay_reveal_spice_influence"
        and dict(action.arguments)["faction"] == "emperor"
    )
    paid = engine.apply(deferred.state, pay).state
    assert paid.decision_stack[-1].kind == "reveal"
    assert paid.players[0].resources.spice == 3
    actions = engine.legal_actions(paid, 0)
    action_ids = {action.action_id for action in actions}
    assert "finish_reveal" not in action_ids
    with pytest.raises(ValueError, match="not a legal Reveal cleanup"):
        finish_reveal_turn(paid, DomainAction(action_id="finish_reveal", actor=0))
    # This bare state has nothing to acquire, so the Reveal frame offers just
    # the resumption; with a market it would also list the acquisitions.
    assert [action.action_id for action in actions] == ["resume_reveal_choice"]
    resume = actions[0]
    assert dict(resume.arguments) == {"effect": "may_pay_three_spice_for_influence"}

    resumed = engine.apply(paid, resume)
    assert [event.kind for event in resumed.events] == ["reveal_choice_resumed"]
    top = resumed.state.decision_stack[-1]
    assert top.kind == "reveal_choice"
    assert dict(top.context)["reveal_card_id"] == first
    assert dict(top.context)["reveal_choice_resumed"] is True
    reveal_context = dict(resumed.state.decision_stack[-2].context)
    assert reveal_context["deferred_reveal_choices"] == ""
    action_ids = {action.action_id for action in engine.legal_actions(resumed.state, 0)}
    # A resumed choice cannot be put off again, so the Reveal cannot cycle.
    assert "defer_reveal_choice" not in action_ids
    assert "pay_reveal_spice_influence" in action_ids

    declined = engine.apply(
        resumed.state,
        DomainAction(action_id="decline_reveal_spice_influence", actor=0),
    ).state
    assert declined.decision_stack[-1].kind == "reveal"
    assert "finish_reveal" in {
        action.action_id for action in engine.legal_actions(declined, 0)
    }


def test_a_started_spy_placement_cannot_be_deferred() -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    posts = (
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(player_id=0, hand=(wheels,), spies_supply=0, spy_post_ids=posts)
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    assert legal_defer_reveal_choice_actions(revealed, 0) == (
        DomainAction(action_id="defer_reveal_choice", actor=0),
    )

    recall = next(
        action
        for action in engine.legal_actions(revealed, 0)
        if action.action_id == "recall_spy_for_reveal_placement"
    )
    committed = engine.apply(revealed, recall).state

    # The recall committed the placement; only the post choice remains.
    assert legal_defer_reveal_choice_actions(committed, 0) == ()
    assert "defer_reveal_choice" not in {
        action.action_id for action in engine.legal_actions(committed, 0)
    }


def test_a_deferred_choice_whose_condition_lapsed_waits_and_lapses_at_finish() -> (
    None
):
    # In High Places' two-Spy recall is deferred, Spy Network's optional
    # recall resolves first and leaves one Spy. The deferred choice cannot
    # be brought back while its condition fails (judged at resolution
    # [Main p. 12]), it does not block the Reveal's end, and it lapses when
    # the Reveal finishes.
    in_high_places = _imperium_instance("in_high_places")
    spy_network = _imperium_instance("spy_network")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places, spy_network),
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    state = replace(state, intrigue_deck=("intrigue:test:0",))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    assert dict(revealed.decision_stack[-1].context)["reveal_choice_effect"] == (
        "may_recall_two_spies_for_three_persuasion"
    )

    deferred = engine.apply(
        revealed, DomainAction(action_id="defer_reveal_choice", actor=0)
    ).state
    assert dict(deferred.decision_stack[-1].context)["reveal_choice_effect"] == (
        "recall_spy_to_draw_intrigue_if_two_placed"
    )
    recall = next(
        action
        for action in engine.legal_actions(deferred, 0)
        if action.action_id == "recall_spy_for_reveal"
    )
    recalled = engine.apply(deferred, recall).state
    assert len(recalled.players[0].spy_post_ids) == 1
    assert recalled.decision_stack[-1].kind == "reveal"

    action_ids = {action.action_id for action in engine.legal_actions(recalled, 0)}
    assert "resume_reveal_choice" not in action_ids
    assert "finish_reveal" in action_ids
    reveal_context = dict(recalled.decision_stack[-1].context)
    assert reveal_context["deferred_reveal_choices"] == (
        f"{in_high_places}|may_recall_two_spies_for_three_persuasion"
    )

    finished = engine.apply(
        recalled, DomainAction(action_id="finish_reveal", actor=0)
    )
    assert finished.events[0].kind == "reveal_choice_unavailable"
    assert dict(finished.events[0].payload)["card_id"] == in_high_places
    assert finished.state.players[0].has_revealed is True


def test_an_unavailable_choice_opens_once_its_condition_holds() -> None:
    # In High Places' two-Spy recall fails at Reveal start (one Spy placed)
    # and waits in the deferred queue instead of lapsing; Wheels Within
    # Wheels' Reveal placement then puts a second Spy out, after which the
    # owner may bring the recall back and take its three Persuasion
    # [Main p. 12] [In High Places card] — the owner's own choices can still
    # satisfy a printed condition later in the same Reveal.
    in_high_places = _imperium_instance("in_high_places")
    wheels = _imperium_instance("wheels_within_wheels")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places, wheels),
            spies_supply=2,
            spy_post_ids=("arrakis-hagga-basin",),
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    top = revealed.decision_stack[-1]
    assert dict(top.context)["reveal_choice_effect"] == "place_spy"
    reveal_context = dict(revealed.decision_stack[-2].context)
    assert reveal_context["persuasion"] == 3
    assert reveal_context["deferred_reveal_choices"] == (
        f"{in_high_places}|may_recall_two_spies_for_three_persuasion"
    )

    placement = next(
        action
        for action in engine.legal_actions(revealed, 0)
        if action.action_id == "place_reveal_spy"
    )
    placed = engine.apply(revealed, placement).state
    assert len(placed.players[0].spy_post_ids) == 2
    assert placed.decision_stack[-1].kind == "reveal"
    actions = engine.legal_actions(placed, 0)
    action_ids = {action.action_id for action in actions}
    assert "finish_reveal" not in action_ids
    resume = next(
        action for action in actions if action.action_id == "resume_reveal_choice"
    )
    assert dict(resume.arguments) == {
        "effect": "may_recall_two_spies_for_three_persuasion"
    }

    resumed = engine.apply(placed, resume).state
    assert dict(resumed.decision_stack[-1].context)["reveal_choice_effect"] == (
        "may_recall_two_spies_for_three_persuasion"
    )
    pair = next(
        action
        for action in engine.legal_actions(resumed, 0)
        if action.action_id == "recall_spies_for_reveal"
    )
    paid = engine.apply(resumed, pair).state
    assert paid.decision_stack[-1].kind == "reveal"
    assert dict(paid.decision_stack[-1].context)["persuasion"] == 3 + 3
    assert paid.players[0].spy_post_ids == ()
    assert "finish_reveal" in {
        action.action_id for action in engine.legal_actions(paid, 0)
    }


# ---------------------------------------------------------------- late conditions


def test_operatives_spy_bonus_pays_out_once_a_reveal_placement_reaches_two_spies() -> (
    None
):
    # Bene Gesserit Operative's "+2 Persuasion while two Spies are placed"
    # fails at Reveal start with one Spy out; Wheels Within Wheels' Reveal
    # placement puts the second Spy out and the bonus then pays at once,
    # exactly once [Main p. 12] (OQ-028).
    operative = _imperium_instance("bene_gesserit_operative")
    wheels = _imperium_instance("wheels_within_wheels")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(operative, wheels),
            spies_supply=2,
            spy_post_ids=("arrakis-hagga-basin",),
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    assert dict(revealed.decision_stack[-2].context)["persuasion"] == 2

    placement = next(
        action
        for action in engine.legal_actions(revealed, 0)
        if action.action_id == "place_reveal_spy"
    )
    placed = engine.apply(revealed, placement)

    assert placed.state.decision_stack[-1].kind == "reveal"
    context = dict(placed.state.decision_stack[-1].context)
    assert context["persuasion"] == 4
    late = [
        event for event in placed.events if event.kind == "reveal_effect_granted_late"
    ]
    assert [dict(event.payload)["card_id"] for event in late] == [operative]
    assert dict(late[0].payload)["persuasion"] == 2
    # Recorded on the frame: another transition does not pay it again.
    again = grant_late_reveal_effects(RuleResult(state=placed.state))
    assert again.state == placed.state
    assert again.events == ()


def test_paracompass_pays_out_after_a_council_seat_bought_this_reveal() -> None:
    # Paracompass' High Council Persuasion (and its Swordmaster extra) fails
    # at Reveal start; buying the seat through Corrinth City's Reveal choice
    # satisfies it in the same Reveal, so it pays on top of the seat's own
    # two Persuasion (OQ-028).
    paracompass = _imperium_instance("paracompass")
    corrinth = _imperium_instance("corrinth_city")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(paracompass, corrinth),
            resources=Resources(solari=5),
            swordmaster_acquired=True,
            agents_available=3,
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    assert dict(revealed.decision_stack[-2].context)["persuasion"] == 0

    seat = next(
        action
        for action in engine.legal_actions(revealed, 0)
        if action.action_id == "take_high_council_from_reveal"
    )
    seated = engine.apply(revealed, seat)

    assert seated.state.players[0].high_council is True
    context = dict(seated.state.decision_stack[-1].context)
    # Seat bonus 2 + Paracompass 2 + its Swordmaster extra 1.
    assert context["persuasion"] == 5
    late = [
        event for event in seated.events if event.kind == "reveal_effect_granted_late"
    ]
    assert [dict(event.payload)["effect_index"] for event in late] == [0, 1]


def test_a_late_fremen_arrival_completes_northern_watermasters_bond() -> None:
    # Northern Watermaster's Fremen-Bond Spice fails at Reveal start; a Fremen
    # card revealed late [FAQ p. 3] creates the Bond and the Spice pays out
    # through the late-condition pass (OQ-028).
    watermaster = _imperium_instance("northern_watermaster")
    maula = _imperium_instance("maula_pistol")
    state = _state(PlayerState(player_id=0, hand=(watermaster,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.players[0].resources.spice == 0

    arrived = reveal_late_arrivals(_with_late_hand(revealed, maula), 0, (maula,))
    granted = grant_late_reveal_effects(arrived)

    late = [e for e in granted.events if e.kind == "reveal_effect_granted_late"]
    assert dict(late[-1].payload)["spice"] == 2
    # The spice waits as a Reveal gain the owner takes (OQ-045).
    assert granted.state.players[0].resources.spice == 0
    taken = _with_gains(granted)
    assert taken.state.players[0].resources.spice == 2
    assert dict(taken.state.decision_stack[-1].context)["persuasion"] == 2
    assert grant_late_reveal_effects(RuleResult(state=taken.state)).events == ()


def test_interstellar_trade_counts_its_contracts_once_at_the_reveal() -> None:
    # Designer ruling (In person, OQ-057): Interstellar Trade "triggers
    # once" — a Contract completed later in the same Reveal (an Acquire
    # Contract met by buying The Spice Must Flow) adds no Persuasion.
    interstellar = _imperium_instance("interstellar_trade", choam_module=True)
    owner = PlayerState(
        player_id=0,
        hand=(interstellar,),
        completed_contract_ids=("contract:arrakeen_i", "contract:arrakeen_ii"),
    )
    state = _state(owner, choam_module=True)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2

    completing = replace(
        revealed.players[0],
        completed_contract_ids=(
            *revealed.players[0].completed_contract_ids,
            "contract:x",
        ),
    )
    completed = replace(revealed, players=(completing, *revealed.players[1:]))
    granted = grant_late_reveal_effects(RuleResult(state=completed))

    assert dict(granted.state.decision_stack[-1].context)["persuasion"] == 2
    assert granted.events == ()

