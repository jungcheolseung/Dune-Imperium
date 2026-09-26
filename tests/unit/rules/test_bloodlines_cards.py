"""Tests for the Bloodlines Imperium cards transcribed in M12 slice 4b.

Card text is transcribed from the card faces (``docs/rules/bloodlines.md``,
``docs/implementation-audits/bloodlines.md``); "Command (6+)" follows
[Bloodlines pp. 5, 12].
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.content.uprising.types import PersonalCardTrashEffect
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules import card_trash
from dune_imperium.rules.acquisition import apply_reserve_acquisition
from dune_imperium.rules.agent_effects import (
    apply_agent_card_discard,
    apply_agent_card_trash,
    legal_agent_card_discard_actions,
    legal_agent_card_icon_actions,
    legal_agent_card_trash_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.combat import (
    apply_combat_reward_spy,
    legal_combat_reward_spy_actions,
    resolve_combat_rewards,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind, replace_player
from dune_imperium.rules.reveal_turn import (
    apply_defer_reveal_choice,
    apply_resume_reveal_choice,
    apply_reveal_card_trash,
    apply_reveal_influence_gain,
    apply_reveal_troop_retreat,
    begin_reveal_turn,
    legal_finish_reveal_actions,
    legal_resume_reveal_choice_actions,
    legal_reveal_card_trash_actions,
    legal_reveal_influence_gain_actions,
    legal_reveal_sandworm_actions,
    legal_reveal_spy_actions,
    legal_reveal_troop_retreat_actions,
    reveal_pending_gains,
)
from dune_imperium.simulation.sweep import run_checked_game

BLOODLINES = RulesetConfig(bloodlines=True)
CHOAM_BLOODLINES = RulesetConfig(bloodlines=True, choam_module=True)
LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)
STARTERS = starting_deck_instance_ids(0)


def _card(card_id: str, copy: int = 0) -> str:
    return f"imperium:{card_id}:{copy}"


def _state(owner: PlayerState, config: RulesetConfig = BLOODLINES) -> GameState:
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        sardaukar_commander_space_ids=(),
        sardaukar_commanders_bank=1,
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _owner(**overrides: object) -> PlayerState:
    values: dict[str, object] = {"player_id": 0, "deck": STARTERS[:4]}
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _play(state: GameState, card_id: str, space_id: str | None = None) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if (space_id is None or dict(action.arguments)["space_id"] == space_id)
        and dict(action.arguments)["card_id"] == card_id
    )
    state = apply_agent_action(state, action).state
    for board_action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, board_action).state
    return state


def _reveal(state: GameState) -> GameState:
    """Reveal and take every pending troop recruit and Intrigue draw at once."""

    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )

    revealed = begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    while actions := legal_reveal_gain_actions(revealed, 0):
        revealed = apply_reveal_gain(revealed, actions[0]).state
    return revealed


def _reveal_context(state: GameState) -> dict[str, object]:
    return {
        key: value
        for frame in state.decision_stack
        if frame.kind == "reveal"
        for key, value in frame.context
    }


# --- Quash Rebellion -------------------------------------------------------


def test_quash_rebellion_pays_two_solari_and_needs_a_commander_for_persuasion() -> None:
    card = _card("quash_rebellion")
    state = _play(_state(_owner(hand=(card,))), card, "assembly_hall")
    resolved = resolve_agent_card_effect(state).state
    assert resolved.players[0].resources.solari == 2

    revealed = _reveal(_state(_owner(hand=(card,))))
    context = _reveal_context(revealed)
    assert context["persuasion"] == 0
    assert context["sword_strength"] == 2

    with_commander = _reveal(
        _state(_owner(hand=(card,), commanders_conflict=1, combat_strength=2))
    )
    assert _reveal_context(with_commander)["persuasion"] == 2


# --- Command (6+) ----------------------------------------------------------


def _six_persuasion_hand(*extra: str) -> PlayerState:
    # Two Sandwalks bond each other (+1 each) on top of their printed 1s.
    return _owner(
        hand=(_card("sandwalk"), _card("sandwalk", 1), *extra), high_council=True
    )


def test_shrouded_counsel_command_trash_opens_at_six_persuasion() -> None:
    card = _card("shrouded_counsel")
    revealed = _reveal(_state(_six_persuasion_hand(card)))
    assert _reveal_context(revealed)["persuasion"] == 2 + 2 + 2 + 1
    frame = revealed.decision_stack[-1]
    assert frame.kind == "reveal_choice"
    assert dict(frame.context)["reveal_choice_effect"] == "command_may_trash_card"
    actions = legal_reveal_card_trash_actions(revealed, 0)
    assert actions[0].action_id == "decline_reveal_card_trash"
    targets = {dict(a.arguments)["card_id"] for a in actions[1:]}
    assert targets == set(revealed.players[0].in_play)
    trashed = apply_reveal_card_trash(revealed, actions[1]).state
    assert len(trashed.players[0].trashed) == 1
    assert trashed.decision_stack[-1].kind == "reveal"


def test_shrouded_counsel_command_trash_of_eliminate_allies_joins_the_reveal() -> None:
    # Eliminate Allies: "When this card is trashed: 2 troops" [Eliminate
    # Allies card]. Shrouded Counsel's Command trash runs from its own
    # "reveal_choice" frame, not a Reveal or Agent-turn effect frame, so
    # ``trash_personal_card``'s own AGENT_EFFECTS-only crediting never ran
    # for it: "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에
    # deploy할 수 있다" [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md:
    # 137), and the Combat 아이콘 deploys "이번 turn에 recruit한 유닛
    # 전부와 garrison에서 최대 두 개" [Bloodlines pp. 5, 12].
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    card = _card("shrouded_counsel")
    eliminate_allies = _card("eliminate_allies")
    owner = replace(
        _six_persuasion_hand(card, eliminate_allies), combat_icon_turn=True
    )
    revealed = _reveal(_state(owner))
    frame = revealed.decision_stack[-1]
    assert dict(frame.context)["reveal_choice_effect"] == "command_may_trash_card"
    action = next(
        a
        for a in legal_reveal_card_trash_actions(revealed, 0)
        if dict(a.arguments).get("card_id") == eliminate_allies
    )

    trashed = apply_reveal_card_trash(revealed, action).state

    assert trashed.decision_stack[-1].kind == "reveal"
    assert trashed.players[0].troops_garrison == 3 + 2
    assert _reveal_context(trashed)["reveal_troops_recruited"] == 2
    assert {
        dict(a.arguments)["count"]
        for a in legal_reveal_deployments(trashed, 0)
        if a.action_id == "deploy_troops"
    } == {1, 2, 3, 4}


def test_command_choices_wait_below_six_persuasion() -> None:
    card = _card("shrouded_counsel")
    revealed = _reveal(_state(_owner(hand=(card, _card("sandwalk")))))
    assert _reveal_context(revealed)["persuasion"] == 2
    assert revealed.decision_stack[-1].kind == "reveal"
    # The Command choice is queued, and lapses when the Reveal ends.
    assert "command_may_trash_card" in str(
        _reveal_context(revealed)["deferred_reveal_choices"]
    )
    assert legal_finish_reveal_actions(revealed, 0) != ()


def test_i_believe_discards_to_draw_and_recruits_two_on_command() -> None:
    card = _card("i_believe")
    filler = STARTERS[4]
    state = _play(_state(_owner(hand=(card, filler))), card, "arrakeen")
    actions = legal_agent_card_discard_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_discard"
    discard = next(a for a in actions if a.action_id == "discard_agent_card")
    before = len(state.players[0].hand)
    drawn = apply_agent_card_discard(state, discard).state.players[0]
    assert filler in drawn.discard_pile
    assert len(drawn.hand) == before  # one discarded, one drawn from the deck

    revealed = _reveal(_state(_six_persuasion_hand(card)))
    owner = revealed.players[0]
    assert owner.troops_garrison == 3 + 2
    below = _reveal(_state(_owner(hand=(card,))))
    assert below.players[0].troops_garrison == 3


@pytest.mark.parametrize(
    ("card_name", "gain"),
    [
        ("i_believe", ("troops", "2")),
        ("southern_faith", ("resources", "0/2/0")),
        ("bombast", ("resources", "3/0/0")),
    ],
)
def test_a_card_drawn_mid_reveal_pays_its_command_once(
    card_name: str, gain: tuple[str, str]
) -> None:
    # "Command (6+)": "In a Reveal turn, you use the effect that follows if
    # you generate 6 Persuasion or more" [Bloodlines p. 5] (bloodlines.md §4),
    # and a card drawn during the Reveal is revealed and used at once
    # [FAQ p. 3]. Each face prints one Command line (I Believe "2 troops",
    # Southern Faith "2 spice", Bombast "3 Solari and trash this card"), so
    # it pays once. Before the fix the arrival paid it without recording it
    # and grant_late_reveal_effects paid it again: 4 troops, 4 spice, 6
    # Solari.
    card = _card(card_name)
    cunning = _intrigue("cunning")
    owner = replace(_six_persuasion_hand(), deck=(card,), intrigue_cards=(cunning,))
    engine = UprisingRulesEngine()
    revealed = engine.apply(
        _state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _reveal_context(revealed)["persuasion_generated"] == 6
    drawn = engine.apply(revealed, _play_intrigue(cunning)).state
    (reveal,) = (f for f in drawn.decision_stack if f.kind == FrameKind.REVEAL)
    pending = reveal_pending_gains(dict(reveal.context))
    assert [entry for entry in pending if entry[2] == card] == [(*gain, card)]
    player = drawn.players[0]
    if card_name == "bombast":
        assert player.trashed.count(card) == 1
        assert card not in player.in_play
    else:
        assert card in player.in_play


def test_ruthless_leadership_drawn_mid_reveal_still_commands_the_combat_icon() -> None:
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    # Paid and recorded at arrival, "Command (6+): [Combat]" [Ruthless
    # Leadership card] still opens this Reveal's deployment [Bloodlines p. 5].
    card = _card("ruthless_leadership")
    cunning = _intrigue("cunning")
    owner = replace(_six_persuasion_hand(), deck=(card,), intrigue_cards=(cunning,))
    engine = UprisingRulesEngine()
    revealed = engine.apply(
        _state(owner, PROMO_BLOODLINES), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    drawn = engine.apply(revealed, _play_intrigue(cunning)).state
    assert _reveal_context(drawn)["combat_deployment"] is True
    assert {a.action_id for a in legal_reveal_deployments(drawn, 0)} == {
        "deploy_troops"
    }


def test_intelligence_training_command_places_a_spy() -> None:
    card = _card("intelligence_training")
    revealed = _reveal(_state(_six_persuasion_hand(card)))
    frame = revealed.decision_stack[-1]
    assert dict(frame.context)["reveal_choice_effect"] == "command_place_spy"
    actions = legal_reveal_spy_actions(revealed, 0)
    assert {a.action_id for a in actions} == {"place_reveal_spy"}
    # Its own sword plus the two Sandwalks' swords.
    assert _reveal_context(revealed)["sword_strength"] == 1 + 2


_RESERVE = (("prepare_the_way", 7), ("the_spice_must_flow", 10))


def test_a_deferred_command_choice_survives_persuasion_spent_below_six() -> None:
    # "Command (6+) — You may use this effect only in a Reveal turn in which
    # you generate 6 Persuasion or more" [Bloodlines p. 12] [Bloodlines p. 5]
    # (docs/rules/bloodlines.md: "그 Reveal turn에 Persuasion을 6 이상 생성했을
    # 때"). Persuasion spent on a purchase was still generated, so buying
    # Prepare the Way (2) out of 7 does not close Intelligence Training's
    # Command Spy again; before the fix the choice lapsed at 5 left.
    card = _card("intelligence_training")
    state = replace(_state(_six_persuasion_hand(card)), reserve_stacks=_RESERVE)
    revealed = _reveal(state)
    assert _reveal_context(revealed)["persuasion"] == 7
    deferred = apply_defer_reveal_choice(
        revealed, DomainAction(action_id="defer_reveal_choice", actor=0)
    ).state
    bought = apply_reserve_acquisition(
        deferred,
        DomainAction(
            action_id="acquire_reserve",
            actor=0,
            arguments=(("card_id", "prepare_the_way"),),
        ),
    ).state
    assert _reveal_context(bought)["persuasion"] == 5
    assert _reveal_context(bought)["persuasion_generated"] == 7
    assert legal_finish_reveal_actions(bought, 0) == ()
    (resume,) = legal_resume_reveal_choice_actions(bought, 0)
    resumed = apply_resume_reveal_choice(bought, resume).state
    place = legal_reveal_spy_actions(resumed, 0)[0]
    assert place.action_id == "place_reveal_spy"
    placed = UprisingRulesEngine().apply(resumed, place).state
    assert len(placed.players[0].spy_post_ids) == 1


def test_a_late_command_counts_persuasion_spent_before_it() -> None:
    # Command (6+) counts the Persuasion the Reveal turn generates [Bloodlines
    # pp. 5, 12]: I Believe (1) + Command Center (1) + High Council (2) is 4,
    # 2 of it spent on Prepare the Way, then Command Center's retreat adds 2.
    # The turn has generated 6, so I Believe's "Command (6+): 2 troops" pays
    # late (OQ-033) although only 4 is left to spend.
    owner = _owner(
        hand=(_card("i_believe"), _card("command_center")),
        high_council=True,
        troops_supply=7,
        troops_conflict=2,
        combat_strength=4,
    )
    engine = UprisingRulesEngine()
    revealed = _reveal(replace(_state(owner), reserve_stacks=_RESERVE))
    assert _reveal_context(revealed)["persuasion"] == 4
    deferred = engine.apply(
        revealed, DomainAction(action_id="defer_reveal_choice", actor=0)
    ).state
    bought = engine.apply(
        deferred,
        DomainAction(
            action_id="acquire_reserve",
            actor=0,
            arguments=(("card_id", "prepare_the_way"),),
        ),
    ).state
    (resume,) = legal_resume_reveal_choice_actions(bought, 0)
    resumed = engine.apply(bought, resume).state
    retreat = next(
        a
        for a in legal_reveal_troop_retreat_actions(resumed, 0)
        if a.action_id == "retreat_two_troops_for_reveal"
    )
    retreated = engine.apply(resumed, retreat).state
    context = _reveal_context(retreated)
    assert context["persuasion"] == 4
    assert context["persuasion_generated"] == 6
    pending = reveal_pending_gains(dict(retreated.decision_stack[-1].context))
    assert ("troops", "2", _card("i_believe")) in pending


# --- Desert Power's Command (6+) timing (OQ-069) ---------------------------


def _desert_power_owner(**overrides: object) -> PlayerState:
    diplomacy = next(instance for instance in STARTERS if ":diplomacy:" in instance)
    values: dict[str, object] = {
        "hand": (_card("desert_power"), _card("i_believe"), diplomacy),
        "high_council": True,
        "maker_hooks": True,
        "resources": Resources(water=1),
    }
    values.update(overrides)
    return _owner(**values)


def _desert_power_state(**owner_overrides: object) -> GameState:
    return replace(
        _state(_desert_power_owner(**owner_overrides)),
        current_conflict_ids=("propaganda",),
    )


def test_desert_power_defers_i_believes_command_below_six_persuasion() -> None:
    # OQ-069 (user ruling 2026-09-26): "(A)가 맞지 ... 근데 설득력을 선택하기
    # 전에 총 설득력이 6 미만이라면 당연히 통솔(+6)도 발동되면 안 되겠지. 그러다
    # 설득력으로 최종 선택했고 그때 총 설득력이 6 이상이면 효과 발동되게 해야지".
    # "[2 Persuasion] -OR- [water] -> [sandworm]" [Desert Power card]
    # [Main pp. 10, 20]: with Maker Hooks the choice may be deferred, so the
    # 2 Persuasion do not count until it is resolved. I Believe (1) +
    # Diplomacy (1) + High Council (2) is 4 without them, below Command's 6,
    # so I Believe's "Command (6+): recruit two troops" [I Believe card]
    # [Bloodlines pp. 5, 12] does not queue yet.
    revealed = _reveal(_desert_power_state())
    context = _reveal_context(revealed)
    assert context["persuasion_generated"] == 4
    assert context["persuasion"] == 4
    (reveal,) = (f for f in revealed.decision_stack if f.kind == FrameKind.REVEAL)
    pending = reveal_pending_gains(dict(reveal.context))
    assert not any(entry[2] == _card("i_believe") for entry in pending)
    frame = revealed.decision_stack[-1]
    assert frame.kind == "reveal_choice"
    assert dict(frame.context)["reveal_choice_effect"] == "may_pay_water_for_sandworm"


def test_desert_power_sandworm_branch_never_commands_i_believe() -> None:
    # Paying Water for the sandworm keeps the 2 Persuasion out of the total
    # for good, so Command (6+) never opens for them this Reveal.
    revealed = _reveal(_desert_power_state())
    sandworm = next(
        action
        for action in legal_reveal_sandworm_actions(revealed, 0)
        if action.action_id == "pay_reveal_water_for_sandworm"
    )
    engine = UprisingRulesEngine()
    deployed = engine.apply(revealed, sandworm).state
    context = _reveal_context(deployed)
    assert context["persuasion_generated"] == 4
    (reveal,) = (f for f in deployed.decision_stack if f.kind == FrameKind.REVEAL)
    pending = reveal_pending_gains(dict(reveal.context))
    assert not any(entry[2] == _card("i_believe") for entry in pending)
    assert deployed.players[0].troops_garrison == 3
    assert deployed.players[0].sandworms_conflict == 1


def test_desert_power_persuasion_branch_commands_i_believe() -> None:
    # Choosing the Persuasion branch gains Desert Power's 2 from then on, so
    # the turn's generated Persuasion reaches 6 and I Believe's Command
    # troops become pending through the late grant (grant_late_reveal_effects).
    revealed = _reveal(_desert_power_state())
    engine = UprisingRulesEngine()
    declined = engine.apply(
        revealed, DomainAction(action_id="decline_reveal_sandworm", actor=0)
    ).state
    context = _reveal_context(declined)
    assert context["persuasion_generated"] == 6
    assert context["persuasion"] == 6
    pending = reveal_pending_gains(dict(declined.decision_stack[-1].context))
    assert ("troops", "2", _card("i_believe")) in pending


def test_desert_power_deferred_choice_still_commands_i_believe_once_resumed() -> None:
    # Deferring the choice and resuming it later reaches the same result as
    # deciding immediately (the resumed choice always opens with Maker
    # Hooks, so it cannot lapse).
    revealed = _reveal(_desert_power_state())
    engine = UprisingRulesEngine()
    deferred = engine.apply(
        revealed, DomainAction(action_id="defer_reveal_choice", actor=0)
    ).state
    assert deferred.decision_stack[-1].kind == "reveal"
    (resume,) = legal_resume_reveal_choice_actions(deferred, 0)
    resumed = engine.apply(deferred, resume).state
    declined = engine.apply(
        resumed, DomainAction(action_id="decline_reveal_sandworm", actor=0)
    ).state
    context = _reveal_context(declined)
    assert context["persuasion_generated"] == 6
    pending = reveal_pending_gains(dict(declined.decision_stack[-1].context))
    assert ("troops", "2", _card("i_believe")) in pending


def test_desert_power_without_maker_hooks_commands_i_believe_immediately() -> None:
    # Without Maker Hooks the sandworm branch can never be taken, so the
    # card is simply 2 Persuasion counted at the Reveal start (unchanged by
    # OQ-069): I Believe (1) + Diplomacy (1) + High Council (2) + Desert
    # Power (2) reaches 6 immediately and Command pays at once. ``_reveal``
    # takes every pending gain, so the paid-out troops show up on the owner.
    revealed = _reveal(_desert_power_state(maker_hooks=False))
    context = _reveal_context(revealed)
    assert context["persuasion_generated"] == 6
    assert revealed.decision_stack[-1].kind == "reveal"
    assert revealed.players[0].troops_garrison == 3 + 2


def test_desert_power_persuasion_branch_reopens_pointing_the_ways_command() -> None:
    # OQ-069 counterpart for a Command *choice* frame, not an automatic
    # effect: Pointing the Way's "Command: choose a Faction to gain one
    # Influence with" [Pointing the Way card] queues deferred below 6
    # Persuasion (Command (6+) [Bloodlines pp. 5, 12]); Pointing the Way (1)
    # + Diplomacy (1) + High Council (2) is 4 without Desert Power's 2, so
    # the choice cannot open until the owner picks the Persuasion branch.
    diplomacy = next(instance for instance in STARTERS if ":diplomacy:" in instance)
    owner = _owner(
        hand=(_card("desert_power"), _card("pointing_the_way"), diplomacy),
        high_council=True,
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = _reveal(state)
    context = _reveal_context(revealed)
    assert context["persuasion_generated"] == 4
    assert legal_reveal_influence_gain_actions(revealed, 0) == ()

    engine = UprisingRulesEngine()
    declined = engine.apply(
        revealed, DomainAction(action_id="decline_reveal_sandworm", actor=0)
    ).state
    resume = next(
        action
        for action in legal_resume_reveal_choice_actions(declined, 0)
        if dict(action.arguments)["effect"] == "command_gain_chosen_influence"
    )
    resumed = engine.apply(declined, resume).state
    assert legal_reveal_influence_gain_actions(resumed, 0) != ()
    assert legal_finish_reveal_actions(resumed, 0) == ()


def test_desert_power_sandworm_branch_never_reopens_pointing_the_ways_command() -> None:
    # Counterpart: paying Water for the sandworm keeps the total at 4 for
    # good, so Pointing the Way's Command choice never resumes this Reveal.
    diplomacy = next(instance for instance in STARTERS if ":diplomacy:" in instance)
    owner = _owner(
        hand=(_card("desert_power"), _card("pointing_the_way"), diplomacy),
        high_council=True,
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = _reveal(state)

    engine = UprisingRulesEngine()
    sandworm = next(
        action
        for action in legal_reveal_sandworm_actions(revealed, 0)
        if action.action_id == "pay_reveal_water_for_sandworm"
    )
    paid = engine.apply(revealed, sandworm).state
    context = _reveal_context(paid)
    assert context["persuasion_generated"] == 4
    assert legal_resume_reveal_choice_actions(paid, 0) == ()
    # Pointing the Way's Command choice must stay correctly deferred (never
    # forced open) rather than sitting unresolved on the stack, so nothing
    # blocks finishing the Reveal turn.
    assert legal_finish_reveal_actions(paid, 0) != ()


def test_pointing_the_way_needs_a_sandworm_and_commands_influence() -> None:
    card = _card("pointing_the_way")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    result = resolve_agent_card_effect(state)
    assert result.events[0].kind == "agent_card_effect_unavailable"

    with_worm = _play(
        _state(_owner(hand=(card,), sandworms_conflict=1)), card, "arrakeen"
    )
    result = resolve_agent_card_effect(with_worm)
    assert result.events[0].kind == "agent_card_effect_resolved"
    assert len(result.state.players[0].intrigue_cards) == 1

    revealed = _reveal(_state(_six_persuasion_hand(card)))
    actions = legal_reveal_influence_gain_actions(revealed, 0)
    assert [dict(a.arguments)["faction"] for a in actions] == [
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    gained = apply_reveal_influence_gain(revealed, actions[3]).state
    assert gained.players[0].influence.fremen == 1
    assert gained.decision_stack[-1].kind == "reveal"


# --- Command Center ----------------------------------------------------------


def test_command_center_recruits_at_two_emperor_influence() -> None:
    card = _card("command_center")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    assert (
        resolve_agent_card_effect(state).events[0].kind
        == "agent_card_effect_unavailable"
    )
    loyal = _play(
        _state(_owner(hand=(card,), influence=Influence(emperor=2))), card, "arrakeen"
    )
    before = loyal.players[0].troops_garrison
    resolved = resolve_agent_card_effect(loyal).state
    assert resolved.players[0].troops_garrison == before + 1


def test_command_center_retreats_two_troops_for_two_persuasion() -> None:
    card = _card("command_center")
    owner = _owner(hand=(card,), troops_supply=7, troops_conflict=2, combat_strength=4)
    revealed = _reveal(_state(owner))
    actions = legal_reveal_troop_retreat_actions(revealed, 0)
    retreat = next(a for a in actions if a.action_id == "retreat_two_troops_for_reveal")
    result = apply_reveal_troop_retreat(revealed, retreat)
    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].troops_garrison == 5
    assert _reveal_context(result.state)["persuasion"] == 1 + 2
    assert result.events[1].kind == "reveal_persuasion_gained"


@pytest.mark.parametrize("commanders", [0, 1])
def test_command_center_retreat_takes_the_two_units_strength(commanders: int) -> None:
    # "Retreat two troops -> +2 [Persuasion]" [Command Center card] gives no
    # swords, and "Each troop is worth 2 strength" [Main p. 12]
    # (player-turns.md: "Conflict의 troop 하나는 strength 2"); a Commander is
    # "a 'troop' that's worth 2 strength" [Bloodlines p. 4]. "If a card changes
    # the number of units a player has in the Conflict ... they adjust their
    # Combat marker accordingly" [Main p. 14]. Three units (6) retreating two
    # leave one troop: strength 2. Before the fix the strength stayed at 6.
    card = _card("command_center")
    owner = _owner(
        hand=(card,),
        troops_supply=6 + commanders,
        troops_conflict=3 - commanders,
        commanders_conflict=commanders,
        combat_strength=6,
    )
    engine = UprisingRulesEngine()
    revealed = _reveal(_state(owner))
    retreat = DomainAction(
        action_id="retreat_two_troops_for_reveal",
        actor=0,
        arguments=(("commanders", commanders),) if commanders else (),
    )
    assert retreat in legal_reveal_troop_retreat_actions(revealed, 0)
    retreated = engine.apply(revealed, retreat).state
    player = retreated.players[0]
    assert player.troops_conflict + player.commanders_conflict == 1
    assert player.combat_strength == 2
    assert _reveal_context(retreated)["strength"] == 2
    assert _reveal_context(retreated)["persuasion"] == 1 + 2


@pytest.mark.parametrize(
    ("card_name", "start", "commanders", "space", "spice"),
    [
        ("command_center", 2, 0, 4, 0),
        ("chani_clever_tactician", 2, 0, 4, 0),
        # From the fourth space the two reach the sixth, which pays a spice.
        ("chani_clever_tactician", 3, 0, 5, 1),
        # A Commander is a troop [Bloodlines p. 4] and moves the token too.
        ("command_center", 2, 1, 4, 0),
    ],
)
def test_reveal_two_troop_retreats_advance_chanis_tactics_token(
    card_name: str, start: int, commanders: int, space: int, spice: int
) -> None:
    # Tactician: "Whenever you retreat or lose any number of troops from the
    # Conflict, advance your Tactics token that many spaces, earning rewards
    # as you reach them" [Chani card]; "Each different source of retreating
    # or losing troops is handled separately" [FAQ p. 1] (bloodlines.md §6),
    # so one "Retreat two troops" [Command Center card] / "Retreat two of
    # your troops" [Chani, Clever Tactician card] moves it two spaces, once.
    # Before the fix both Reveal retreats left the token where it was.
    card = _card(card_name)
    owner = _owner(
        leader_id="chani",
        tactics_track_space=start,
        hand=(card,),
        troops_supply=6 + commanders,
        troops_conflict=3 - commanders,
        commanders_conflict=commanders,
        combat_strength=6,
    )
    revealed = _reveal(_state(owner))
    retreat = DomainAction(
        action_id="retreat_two_troops_for_reveal",
        actor=0,
        arguments=(("commanders", commanders),) if commanders else (),
    )
    result = apply_reveal_troop_retreat(revealed, retreat)
    player = result.state.players[0]
    assert player.tactics_track_space == space
    assert player.resources.spice == revealed.players[0].resources.spice + spice
    advanced = [e for e in result.events if e.kind == "tactics_token_advanced"]
    assert len(advanced) == 1
    assert dict(advanced[0].payload)["count"] == 2


# --- trash, discard, acquisition triggers -------------------------------------


def test_eliminate_allies_recruits_two_troops_when_trashed() -> None:
    card = _card("eliminate_allies")
    # A Spy-icon card follows the owner's Spy [Main p. 11]: one watches
    # Sardaukar / Dutiful Service.
    owner = _owner(
        hand=(card,),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    state = _play(_state(owner), card, "dutiful_service")
    before = state.players[0].troops_garrison
    result = trash_personal_card(state, 0, card, source="test")
    owner = result.state.players[0]
    assert owner.troops_garrison == before + 2
    assert card in owner.trashed
    # Recruited during the Agent turn: they join the deployable count
    assert dict(result.state.decision_stack[-1].context)["troops_recruited"] == 2


def test_eliminate_allies_box_may_trash_itself_and_keep_its_troops() -> None:
    # Its own trash icon may pick the card itself: "일반 trash 아이콘은
    # hand, discard pile, in play 가운데 카드 1장을 대상으로 한다", and a
    # card played on an Agent turn is in play [Main p. 20]
    # (docs/rules/uprising-systems.md:17-18). The two troops join the
    # turn's allowance [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md:
    # 137) through the box's chosen-card trash, whose context is read before
    # the trash (``keep_trash_recruits``).
    card = _card("eliminate_allies")
    owner = _owner(
        hand=(card,),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    state = _play(_state(owner), card, "dutiful_service")
    before = state.players[0].troops_garrison
    action = next(
        a
        for a in legal_agent_card_trash_actions(state, 0)
        if dict(a.arguments).get("card_id") == card
    )

    result = apply_agent_card_trash(state, action).state

    assert card in result.players[0].trashed
    assert result.players[0].troops_garrison == before + 2
    frame = result.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    assert dict(frame.context)["troops_recruited"] == 2


def test_corrupt_bureaucrat_discard_pays_three_solari() -> None:
    card = _card("corrupt_bureaucrat")
    state = _state(_owner(hand=(card,)), CHOAM_BLOODLINES)
    result = discard_personal_card_from_hand(state, 0, card, source="test")
    assert result.state.players[0].resources.solari == 3


def test_corrupt_bureaucrat_takes_a_contract_after_a_spy_recall() -> None:
    card = _card("corrupt_bureaucrat")
    contracts = ("contract:deliver_supplies:0", "contract:harvest_3:0")
    base = replace(
        _state(_owner(hand=(card,)), CHOAM_BLOODLINES),
        face_up_contract_ids=contracts,
    )
    state = _play(base, card, "assembly_hall")
    assert (
        resolve_agent_card_effect(state).events[0].kind
        == "agent_card_effect_unavailable"
    )
    # "If you recalled a Spy this turn:" reads the seat's per-turn recall
    # count (OQ-044 (d)), which every recall path raises.
    recalled = replace(
        state,
        players=(
            replace(state.players[0], spies_recalled_turn=1),
            *state.players[1:],
        ),
    )
    result = resolve_agent_card_effect(recalled)
    assert result.state.decision_stack[-1].kind == "contract_market"


def test_corrupt_bureaucrat_counts_a_plot_recall_during_its_agent_turn() -> None:
    # [Corrupt Bureaucrat card] "If you recalled a Spy this turn: [contract]"
    # names no way of recalling; "When the Recall Spy icon appears on a card,
    # you may return one of your Spies from an observation post to your
    # supply." [Main p. 11]. Sleeper Unit's "[Spy recall] -> 2 troops" Plot,
    # played while the box waits (OQ-057), meets the condition.
    card = _card("corrupt_bureaucrat")
    sleeper = _intrigue("sleeper_unit")
    contracts = ("contract:deliver_supplies:0", "contract:harvest_3:0")
    base = replace(
        _state(
            _owner(
                hand=(card,),
                intrigue_cards=(sleeper,),
                spies_supply=2,
                spy_post_ids=("emperor-sardaukar-dutiful-service",),
            ),
            CHOAM_BLOODLINES,
        ),
        face_up_contract_ids=contracts,
    )
    state = _play(base, card, "assembly_hall")
    engine = UprisingRulesEngine()
    assert "resolve_agent_card_effect" not in {
        action.action_id for action in engine.legal_actions(state, 0)
    }

    opened = engine.apply(state, _play_intrigue(sleeper, 1)).state
    recall = next(
        action
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "recall_spy_for_intrigue"
    )
    recalled = engine.apply(opened, recall).state
    assert recalled.players[0].spies_recalled_turn == 1
    assert "resolve_agent_card_effect" in {
        action.action_id for action in engine.legal_actions(recalled, 0)
    }

    result = resolve_agent_card_effect(recalled)
    assert result.state.decision_stack[-1].kind == "contract_market"


def test_mercantile_affairs_draws_intrigue_after_a_contract_completed_this_turn() -> (
    None
):
    card = _card("mercantile_affairs")
    state = _play(_state(_owner(hand=(card,)), CHOAM_BLOODLINES), card, "arrakeen")
    assert (
        resolve_agent_card_effect(state).events[0].kind
        == "agent_card_effect_unavailable"
    )
    completed = replace(
        state,
        players=(
            replace(state.players[0], contracts_completed_turn=1),
            *state.players[1:],
        ),
    )
    result = resolve_agent_card_effect(completed)
    assert len(result.state.players[0].intrigue_cards) == 1


def test_imperial_throneship_rewards_a_large_garrison() -> None:
    card = _card("imperial_throneship")
    revealed = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(revealed)["persuasion"] == 2
    big = _reveal(_state(_owner(hand=(card,), commanders_garrison=1)))
    assert _reveal_context(big)["persuasion"] == 3
    assert big.players[0].resources.solari == 3


# --- spice gained this turn ---------------------------------------------------


def test_sandwalk_draws_after_two_spice_gained_this_turn() -> None:
    card = _card("sandwalk")
    poor = _play(_state(_owner(hand=(card,))), card)
    assert (
        resolve_agent_card_effect(poor).events[0].kind
        == "agent_card_effect_unavailable"
    )
    rich = _play(
        _state(_owner(hand=(card,), resources=Resources(spice=2, water=1))), card
    )
    before = len(rich.players[0].hand)
    result = resolve_agent_card_effect(rich)
    assert result.events[0].kind == "agent_card_effect_resolved"
    assert len(result.state.players[0].hand) == before + 1


def test_fremen_war_name_icons_need_two_spice_gained() -> None:
    card = _card("fremen_war_name")
    rich = _play(
        _state(_owner(hand=(card,), resources=Resources(spice=3, water=1))), card
    )
    keys = {dict(a.arguments)["effect"] for a in legal_agent_card_icon_actions(rich, 0)}
    assert keys == {"troops", "cards"}
    troops = next(
        a
        for a in legal_agent_card_icon_actions(rich, 0)
        if dict(a.arguments)["effect"] == "troops"
    )
    before = rich.players[0].troops_garrison
    resolved = resolve_agent_card_icon(rich, troops).state
    assert resolved.players[0].troops_garrison == before + 1

    # "If you gained [2 spice] or more this turn: [troop] [draw a card]"
    # [Fremen War Name card] prints no "may": once the condition holds both
    # icons are mandatory. While it is false they are not offered to fire and
    # fizzle; the box waits for the turn's end (OQ-057 (1), designer ruling
    # "조건이 거짓인 의무 Agent box는 turn 종료까지 보류").
    from dune_imperium.rules.agent_effects import (
        agent_card_effect_is_unavailable,
        fizzle_pending_agent_icons,
    )

    poor = _play(_state(_owner(hand=(card,))), card)
    assert legal_agent_card_icon_actions(poor, 0) == ()
    assert agent_card_effect_is_unavailable(poor)
    ended = fizzle_pending_agent_icons(poor)
    assert {dict(e.payload)["effect"] for e in ended.events} == {"troops", "cards"}
    assert {e.kind for e in ended.events} == {"agent_card_effect_unavailable"}
    assert ended.state.players[0].troops_garrison == poor.players[0].troops_garrison


def test_fremen_war_name_icons_become_mandatory_after_a_later_spice_gain() -> None:
    # The same box sent to Hagga Basin: before the Maker harvest the owner
    # has gained no spice, so the icons are held rather than fizzled
    # (OQ-057 (1)); the harvest meets "If you gained [2 spice] or more this
    # turn:" [Fremen War Name card] and both icons then resolve.
    from dune_imperium.rules.agent_effect_frame import legal_agent_effect_frame_actions

    card = _card("fremen_war_name")
    state = _state(_owner(hand=(card,), resources=Resources(water=1)))
    placed = apply_agent_action(
        state,
        next(
            action
            for action in legal_agent_actions(state, 0)
            if dict(action.arguments)["space_id"] == "hagga_basin"
        ),
    ).state
    assert legal_agent_card_icon_actions(placed, 0) == ()
    harvested = UprisingRulesEngine().apply(
        placed,
        next(
            action
            for action in legal_agent_effect_frame_actions(placed, 0)
            if action.action_id == "harvest_maker_spice"
        ),
    ).state
    assert harvested.players[0].resources.spice >= 2
    icons = legal_agent_card_icon_actions(harvested, 0)
    assert {dict(action.arguments)["effect"] for action in icons} == {
        "troops",
        "cards",
    }
    assert DomainAction(
        action_id="finish_agent_turn", actor=0
    ) not in legal_agent_effect_frame_actions(harvested, 0)
    troops = next(a for a in icons if dict(a.arguments)["effect"] == "troops")
    recruited = resolve_agent_card_icon(harvested, troops).state
    assert (
        recruited.players[0].troops_garrison
        == harvested.players[0].troops_garrison + 1
    )


# --- soak ---------------------------------------------------------------------


@pytest.mark.parametrize("game_seed", [31, 32])
def test_random_bloodlines_games_with_the_new_cards_finish(game_seed: int) -> None:
    report = run_checked_game(
        BLOODLINES,
        game_seed=game_seed,
        policy_seed=900_000 + game_seed,
        privacy_interval=10,
        soundness_interval=10,
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.rounds >= 1


def test_heuristic_choam_bloodlines_game_finishes() -> None:
    report = run_checked_game(
        CHOAM_BLOODLINES,
        game_seed=41,
        policy_seed=900_041,
        privacy_interval=0,
        policy="heuristic",
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.rounds >= 1


# --- Bloodlines Intrigue (slice 4c-1) ---------------------------------------


def _intrigue(card_id: str) -> str:
    return f"intrigue:{card_id}:0"


def _play_intrigue(card_id: str, option: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card_id), ("option", option)),
    )


def _combat_state(owner: PlayerState, *others: PlayerState) -> GameState:
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.rules.combat import begin_combat_intrigue

    seats = [owner, *others]
    seats.extend(PlayerState(player_id=seat) for seat in range(len(seats), 4))
    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=tuple(replace(seat, has_revealed=True) for seat in seats),
    )
    return begin_combat_intrigue(state).state


def _endgame_window(owner: PlayerState) -> GameState:
    from dune_imperium.rules.endgame import begin_endgame_intrigue

    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )
    return begin_endgame_intrigue(state).state


def _fighter(troops: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "troops_supply": 12 - troops,
        "troops_garrison": 0,
        "troops_conflict": troops,
        "combat_strength": 2 * troops,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def test_desert_support_pays_water_for_five_swords() -> None:
    card = _intrigue("desert_support")
    state = _combat_state(
        _fighter(1, intrigue_cards=(card,), resources=Resources(water=1))
    )
    engine = UprisingRulesEngine()
    done = engine.apply(state, _play_intrigue(card)).state
    assert done.players[0].resources.water == 0
    assert done.players[0].combat_strength == 2 + 5


def test_ripples_in_the_sand_adds_intrigue_with_a_sandworm() -> None:
    card = _intrigue("ripples_in_the_sand")
    engine = UprisingRulesEngine()
    plain = engine.apply(
        _combat_state(_fighter(1, intrigue_cards=(card,))), _play_intrigue(card)
    ).state
    assert plain.players[0].combat_strength == 5
    assert plain.players[0].intrigue_cards == ()

    worm = _fighter(1, intrigue_cards=(card,), sandworms_conflict=1, combat_strength=5)
    with_worm = engine.apply(_combat_state(worm), _play_intrigue(card)).state
    assert with_worm.players[0].combat_strength == 8
    assert len(with_worm.players[0].intrigue_cards) == 1


def test_return_the_favor_counts_factions_at_two_influence() -> None:
    card = _intrigue("return_the_favor")
    owner = _fighter(
        1,
        intrigue_cards=(card,),
        influence=Influence(emperor=2, fremen=3, bene_gesserit=1),
    )
    done = UprisingRulesEngine().apply(_combat_state(owner), _play_intrigue(card)).state
    assert done.players[0].combat_strength == 2 + 1 + 2


def test_sacred_pools_discards_for_water_or_scores_at_three_water() -> None:
    card = _intrigue("sacred_pools")
    filler = STARTERS[5]
    state = _state(_owner(hand=(filler,), intrigue_cards=(card,)))
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play_intrigue(card, 0)).state
    discard = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "choose_intrigue_discard"
    )
    done = engine.apply(opened, discard).state
    assert done.players[0].resources.water == 2
    assert filler in done.players[0].discard_pile

    dry = _endgame_window(_owner(intrigue_cards=(card,), resources=Resources(water=2)))
    assert [a.action_id for a in engine.legal_actions(dry, 0)] == [
        "pass_endgame_intrigue"
    ]
    wet = _endgame_window(_owner(intrigue_cards=(card,), resources=Resources(water=3)))
    scored = engine.apply(wet, _play_intrigue(card, 1)).state
    assert scored.players[0].victory_points == 2


def test_seize_production_spice_needs_a_commander_in_the_conflict() -> None:
    card = _intrigue("seize_production")
    engine = UprisingRulesEngine()
    plain = _state(_owner(intrigue_cards=(card,)))
    assert [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(plain, 0)
        if a.action_id == "play_intrigue"
    ] == [0]
    solari = engine.apply(plain, _play_intrigue(card, 0)).state
    assert solari.players[0].resources.solari == 2

    commanded = _state(_owner(intrigue_cards=(card,), commanders_conflict=1))
    spice = engine.apply(commanded, _play_intrigue(card, 1)).state
    assert spice.players[0].resources.spice == 2


def test_sleeper_unit_pays_for_a_spy_or_recalls_one_for_troops() -> None:
    card = _intrigue("sleeper_unit")
    engine = UprisingRulesEngine()
    paying = _state(_owner(intrigue_cards=(card,), resources=Resources(solari=1)))
    opened = engine.apply(paying, _play_intrigue(card, 0)).state
    assert opened.players[0].resources.solari == 0
    # Paid for with a Spy in the supply: the placement is mandatory (the
    # designer's erratum to [Main p. 11], adopted with OQ-057).
    assert {a.action_id for a in engine.legal_actions(opened, 0)} == {
        "place_intrigue_spy",
    }

    posted = _state(
        _owner(
            intrigue_cards=(card,),
            spies_supply=2,
            spy_post_ids=("emperor-sardaukar-dutiful-service",),
        )
    )
    recalled = engine.apply(posted, _play_intrigue(card, 1)).state
    recall = next(
        a
        for a in engine.legal_actions(recalled, 0)
        if a.action_id == "recall_spy_for_intrigue"
    )
    done = engine.apply(recalled, recall).state
    assert done.players[0].spies_supply == 3
    assert done.players[0].troops_garrison == 5


def test_tenuous_bond_trashes_a_costly_discard_for_four_swords() -> None:
    card = _intrigue("tenuous_bond")
    engine = UprisingRulesEngine()
    cheap = _fighter(1, intrigue_cards=(card,), discard_pile=(STARTERS[0],))
    # Starting cards have no printed cost: only the Influence swap is playable.
    options = [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(_combat_state(cheap), 0)
        if a.action_id == "play_intrigue"
    ]
    assert options == []  # no Influence to lose either
    costly = _fighter(
        1,
        intrigue_cards=(card,),
        discard_pile=(STARTERS[0], _card("sandwalk")),
        influence=Influence(fremen=1),
    )
    state = _combat_state(costly)
    options = [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(state, 0)
        if a.action_id == "play_intrigue"
    ]
    # The gold Influence band is Plot and the red trash band is Combat
    # ("PLOT / COMBAT" footer) [Tenuous Bond card; Main p. 7]: in Combat only
    # the trash for four swords is offered, even with Influence to swap.
    assert options == [1]
    opened = engine.apply(state, _play_intrigue(card, 1)).state
    trash_actions = engine.legal_actions(opened, 0)
    assert [dict(a.arguments)["card_id"] for a in trash_actions] == [_card("sandwalk")]
    done = engine.apply(opened, trash_actions[0]).state
    assert done.players[0].trashed == (_card("sandwalk"),)
    assert done.players[0].combat_strength == 2 + 4


def test_tenuous_bond_swaps_influence_only_as_a_plot() -> None:
    # Plot half: the gold band's "[lose 1 Influence] -> [gain 1 Influence]";
    # the red four-sword band is not a Plot [Tenuous Bond card; Main p. 7].
    card = _intrigue("tenuous_bond")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,),
        discard_pile=(_card("sandwalk"),),
        influence=Influence(fremen=1),
    )
    state = _state(owner)
    options = [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(state, 0)
        if a.action_id == "play_intrigue"
    ]
    assert options == [0]


def test_the_strong_survive_retreats_one_troop_to_trash_a_card() -> None:
    card = _intrigue("the_strong_survive")
    engine = UprisingRulesEngine()
    owner = _fighter(2, intrigue_cards=(card,), hand=(STARTERS[0],))
    state = _combat_state(owner)
    swords = engine.apply(state, _play_intrigue(card, 0)).state
    assert swords.players[0].combat_strength == 4 + 3

    opened = engine.apply(state, _play_intrigue(card, 1)).state
    retreat = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "retreat_intrigue_troops"
    )
    retreated = engine.apply(opened, retreat).state
    assert retreated.players[0].troops_conflict == 1
    assert retreated.players[0].combat_strength == 2
    trash = next(
        a
        for a in engine.legal_actions(retreated, 0)
        if a.action_id == "trash_intrigue_card"
    )
    done = engine.apply(retreated, trash).state
    assert done.players[0].trashed == (STARTERS[0],)


def test_withdrawal_agreement_retreats_three_for_influence() -> None:
    card = _intrigue("withdrawal_agreement")
    engine = UprisingRulesEngine()
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        legal_intrigue_choice_actions,
    )

    state = _combat_state(_fighter(3, intrigue_cards=(card,)))
    opened = engine.apply(state, _play_intrigue(card)).state
    retreat = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "retreat_intrigue_troops"
    )
    assert dict(retreat.arguments)["count"] == 3
    # Resolve the slots without the dispatcher: the last unit leaving the
    # Conflict would otherwise run the round to its end.
    retreated = apply_intrigue_choice(opened, retreat).state
    choice = next(
        a
        for a in legal_intrigue_choice_actions(retreated, 0)
        if a.action_id == "choose_intrigue_faction"
        and dict(a.arguments)["faction"] == "emperor"
    )
    done = apply_intrigue_choice(retreated, choice).state
    assert done.players[0].influence.emperor == 1
    assert done.players[0].troops_garrison == 3
    assert done.players[0].combat_strength == 0


def test_grasp_arrakis_flips_two_conflict_cards_for_a_point() -> None:
    card = _intrigue("grasp_arrakis")
    engine = UprisingRulesEngine()
    owner = _fighter(
        1,
        intrigue_cards=(card,),
        won_conflict_ids=("skirmish_ornithopter", "storms_in_the_south"),
    )
    state = _combat_state(owner)
    options = [
        dict(a.arguments)["option"]
        for a in engine.legal_actions(state, 0)
        if a.action_id == "play_intrigue"
    ]
    # The red band (three swords) is Combat; the dark-green flip band is
    # Endgame ("COMBAT / ENDGAME" footer) [Grasp Arrakis card; Main p. 7].
    assert options == [0]
    endgame = _endgame_window(
        _owner(
            intrigue_cards=(card,),
            won_conflict_ids=("skirmish_ornithopter", "storms_in_the_south"),
        )
    )
    opened = engine.apply(endgame, _play_intrigue(card, 1)).state
    first = engine.legal_actions(opened, 0)
    assert {dict(a.arguments)["card_id"] for a in first} == {
        "skirmish_ornithopter",
        "storms_in_the_south",
    }
    flipped_one = engine.apply(opened, first[0]).state
    second = engine.legal_actions(flipped_one, 0)
    assert len(second) == 1
    done = engine.apply(flipped_one, second[0]).state
    assert done.players[0].victory_points == 2
    assert set(done.players[0].face_down_battle_card_ids) == {
        "skirmish_ornithopter",
        "storms_in_the_south",
    }
    # With one card left face up the Endgame half is not offered.
    single = _endgame_window(
        _owner(intrigue_cards=(card,), won_conflict_ids=("skirmish_ornithopter",))
    )
    assert [a.action_id for a in engine.legal_actions(single, 0)] == [
        "pass_endgame_intrigue"
    ]


# --- turn-scoped Plot modifiers (slice 4c-2a) --------------------------------


def test_honor_guard_recruits_and_discounts_the_commander_this_turn() -> None:
    from dune_imperium.rules.sardaukar import (
        apply_sardaukar_commander_action,
        legal_sardaukar_commander_actions,
    )

    card = _intrigue("honor_guard")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,), hand=STARTERS[4:10], resources=Resources(solari=1)
    )
    state = replace(
        _state(owner),
        sardaukar_commander_space_ids=("dutiful_service",),
        skill_face_up=("skill:canny:0",),
    )
    played = engine.apply(state, _play_intrigue(card)).state
    assert played.players[0].troops_garrison == 4
    assert played.players[0].commander_discount_turn == 1

    # Any card that reaches Dutiful Service works; pick the first legal one.
    action = next(
        a
        for a in legal_agent_actions(played, 0)
        if dict(a.arguments)["space_id"] == "dutiful_service"
    )
    visited = apply_agent_action(played, action).state
    for board_action in legal_board_effect_actions(visited, 0):
        visited = resolve_board_effect(visited, board_action).state
    buy = next(
        a
        for a in legal_sardaukar_commander_actions(visited, 0)
        if a.action_id == "acquire_sardaukar_commander"
    )
    bought = apply_sardaukar_commander_action(visited, buy)
    assert bought.state.players[0].resources.solari == 1 + 2 - 1
    assert dict(bought.events[0].payload)["solari"] == 1


def test_insider_information_waives_influence_requirements_this_turn() -> None:
    card = _intrigue("insider_information")
    engine = UprisingRulesEngine()
    owner = _owner(intrigue_cards=(card,), hand=STARTERS[4:10])
    state = _state(owner)
    # Sietch Tabr needs two Fremen Influence [Board Guide p. 1].
    assert not any(
        dict(a.arguments)["space_id"] == "sietch_tabr"
        for a in legal_agent_actions(state, 0)
    )
    waived = engine.apply(state, _play_intrigue(card, 1)).state
    assert waived.players[0].ignores_influence_requirements_turn is True
    assert any(
        dict(a.arguments)["space_id"] == "sietch_tabr"
        for a in legal_agent_actions(waived, 0)
    )


def test_insider_information_recalls_a_spy_to_trash_and_draw() -> None:
    card = _intrigue("insider_information")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,),
        hand=(STARTERS[4],),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    opened = engine.apply(_state(owner), _play_intrigue(card, 0)).state
    recall = next(
        a
        for a in engine.legal_actions(opened, 0)
        if a.action_id == "recall_spy_for_intrigue"
    )
    recalled = engine.apply(opened, recall).state
    trash = next(
        a
        for a in engine.legal_actions(recalled, 0)
        if a.action_id == "trash_intrigue_card"
        and dict(a.arguments)["card_id"] == STARTERS[4]
    )
    done = engine.apply(recalled, trash).state
    owner_after = done.players[0]
    assert owner_after.spies_supply == 3
    assert owner_after.trashed == (STARTERS[4],)
    assert len(owner_after.hand) == 1  # the drawn card


def test_emperors_invitation_lends_the_emperor_icon_for_the_turn() -> None:
    from dune_imperium.adapters import ActionCodec

    card = _intrigue("emperor_s_invitation")
    engine = UprisingRulesEngine()
    dagger = next(c for c in STARTERS if ":dagger:" in c)
    state = _state(_owner(intrigue_cards=(card,), hand=(dagger,), deck=()))
    assert not any(
        dict(a.arguments)["space_id"] == "dutiful_service"
        for a in legal_agent_actions(state, 0)
    )
    invited = engine.apply(state, _play_intrigue(card, 1)).state
    assert invited.players[0].granted_agent_icon_turn == "emperor"
    action = next(
        a
        for a in legal_agent_actions(invited, 0)
        if dict(a.arguments)["space_id"] == "dutiful_service"
    )
    codec = ActionCodec(BLOODLINES)
    assert codec.decode(codec.encode(action), 0) == action
    placed = apply_agent_action(invited, action).state
    assert "dutiful_service" in placed.players[0].agent_locations


# --- Combat icon (slice 4c-2b) ----------------------------------------------


def test_adaptive_tactics_before_placement_opens_a_deployment_at_any_space() -> None:
    from dune_imperium.rules.combat_deployment import legal_combat_deployments

    card = _intrigue("adaptive_tactics")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,), hand=STARTERS[4:10], resources=Resources(spice=1)
    )
    played = engine.apply(_state(owner), _play_intrigue(card)).state
    assert played.players[0].combat_icon_turn is True
    assert played.players[0].troops_garrison == 4
    # Dutiful Service is not a Combat space, yet the icon opens the window:
    # the recruited troop plus up to two from the garrison.
    visited = _play(played, STARTERS[4], "dutiful_service")
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(visited, 0)
    ] == [1, 2, 3]


def test_adaptive_tactics_before_reveal_joins_the_reveals_allowance() -> None:
    # Played from the bare "turn" frame, before the owner has chosen an
    # Agent or a Reveal turn: the recruit lands in the TURN frame's own
    # ``troops_recruited`` (``update_turn_recruits``'s TURN branch). "그
    # turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수
    # 있다" [Main p. 10] [FAQ p. 4] and the Combat 아이콘 "Reveal
    # turn에서도 쓸 수 있다" [Bloodlines pp. 5, 12]: choosing Reveal next
    # must carry that count in, not reset it to 0.
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    card = _intrigue("adaptive_tactics")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,), hand=(STARTERS[4],), resources=Resources(spice=1)
    )
    played = engine.apply(_state(owner), _play_intrigue(card)).state
    assert played.decision_stack[-1].kind == "turn"
    assert played.players[0].combat_icon_turn is True
    assert played.players[0].troops_garrison == 4

    revealed = _reveal(played)

    context = _reveal_context(revealed)
    assert context["combat_deployment"] is True
    assert context["reveal_troops_recruited"] == 1
    assert {
        dict(a.arguments)["count"]
        for a in legal_reveal_deployments(revealed, 0)
        if a.action_id == "deploy_troops"
    } == {1, 2, 3}


def test_adaptive_tactics_during_the_reveal_deploys_with_strength() -> None:
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_deployment,
        legal_reveal_deployments,
    )

    card = _intrigue("adaptive_tactics")
    engine = UprisingRulesEngine()
    owner = _owner(
        intrigue_cards=(card,),
        hand=(STARTERS[4],),
        resources=Resources(spice=1),
        commanders_garrison=1,
    )
    revealed = _reveal(_state(owner))
    assert legal_reveal_deployments(revealed, 0) == ()
    played = engine.apply(revealed, _play_intrigue(card)).state
    context = _reveal_context(played)
    assert context["combat_deployment"] is True
    assert context["reveal_troops_recruited"] == 1
    counts = {
        (a.action_id, dict(a.arguments)["count"])
        for a in legal_reveal_deployments(played, 0)
    }
    # One recruited troop plus two from the garrison: three troops, or the
    # Commander as one of the garrison units.
    assert counts == {
        ("deploy_troops", 1),
        ("deploy_troops", 2),
        ("deploy_troops", 3),
        ("deploy_commanders", 1),
    }
    deployed = apply_reveal_deployment(
        played, DomainAction("deploy_commanders", 0, (("count", 1),))
    ).state
    assert deployed.players[0].commanders_conflict == 1
    sword_strength = _reveal_context(deployed)["sword_strength"]
    assert isinstance(sword_strength, int)
    assert deployed.players[0].combat_strength == 2 + sword_strength
    more = apply_reveal_deployment(
        deployed, DomainAction("deploy_troops", 0, (("count", 2),))
    ).state
    assert more.players[0].troops_conflict == 2
    assert _reveal_context(more)["reveal_units_deployed"] == 3
    assert legal_reveal_deployments(more, 0) == ()


def test_elite_forces_rewards_an_emperor_trash_from_hand() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_trash,
        legal_agent_card_trash_actions,
    )
    from dune_imperium.rules.combat_deployment import legal_combat_deployments

    card = _card("elite_forces")
    emperor = _card("quash_rebellion")
    state = _play(
        _state(_owner(hand=(card, emperor, STARTERS[4]))), card, "dutiful_service"
    )
    actions = legal_agent_card_trash_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_trash"
    assert {dict(a.arguments)["card_id"] for a in actions[1:]} == {emperor, STARTERS[4]}
    trash_emperor = next(
        a for a in actions[1:] if dict(a.arguments)["card_id"] == emperor
    )
    rewarded = apply_agent_card_trash(state, trash_emperor).state
    keys = {
        dict(a.arguments)["effect"] for a in legal_agent_card_icon_actions(rewarded, 0)
    }
    assert keys == {"intrigue", "troops"}
    assert (
        dict(rewarded.decision_stack[-1].context)["pending_combat_deployment"] is True
    )
    # Resolve the troop icon: the recruit may then deploy (Combat icon).
    troops = next(
        a
        for a in legal_agent_card_icon_actions(rewarded, 0)
        if dict(a.arguments)["effect"] == "troops"
    )
    resolved = resolve_agent_card_icon(rewarded, troops).state
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(resolved, 0)
    ] == [1, 2, 3]

    plain = next(a for a in actions[1:] if dict(a.arguments)["card_id"] == STARTERS[4])
    nothing = apply_agent_card_trash(state, plain).state
    assert legal_agent_card_icon_actions(nothing, 0) == ()
    assert (
        dict(nothing.decision_stack[-1].context)["pending_combat_deployment"] is False
    )


def test_disruption_tactics_forces_an_enemy_unit_back_and_trashes_for_the_icon() -> (
    None
):
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_opponent_retreat,
        legal_agent_card_opponent_retreat_actions,
    )
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_card_trash,
        legal_reveal_card_trash_actions,
        legal_reveal_deployments,
    )

    card = _card("disruption_tactics")
    enemy = replace(
        PlayerState(player_id=1),
        troops_supply=8,
        troops_conflict=1,
        commanders_conflict=1,
        combat_strength=4,
    )
    base = _state(_owner(hand=(card,)))
    base = replace(base, players=(base.players[0], enemy, *base.players[2:]))
    state = _play(base, card)
    actions = legal_agent_card_opponent_retreat_actions(state, 0)
    assert {tuple(dict(a.arguments).items()) for a in actions} == {
        (("player", 1),),
        (("commanders", 1), ("player", 1)),
    }
    pushed = apply_agent_card_opponent_retreat(state, actions[1]).state
    assert pushed.players[1].commanders_conflict == 0
    assert pushed.players[1].commanders_garrison == 1
    assert pushed.players[1].combat_strength == 2

    revealed = _reveal(_state(_owner(hand=(card,), troops_garrison=3)))
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"] == "may_trash_self_for_combat_icon"
    )
    trash_actions = legal_reveal_card_trash_actions(revealed, 0)
    assert [a.action_id for a in trash_actions] == [
        "decline_reveal_card_trash",
        "trash_reveal_card",
    ]
    trashed = apply_reveal_card_trash(revealed, trash_actions[1]).state
    assert card in trashed.players[0].trashed
    assert [
        dict(a.arguments)["count"] for a in legal_reveal_deployments(trashed, 0)
    ] == [1, 2]


# --- Bloodlines Imperium (slice 4d-1) --------------------------------------


def test_arrakis_observer_discard_places_a_deep_cover_spy() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_spy_action,
        legal_agent_card_spy_actions,
    )

    card = _card("arrakis_observer")
    guild = _card("guild_envoy")
    filler = STARTERS[4]
    rival = replace(
        PlayerState(player_id=1),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    base = _state(
        _owner(
            hand=(card, guild, filler),
            spies_supply=2,
            spy_post_ids=("landsraad-assembly-hall-gather-support",),
        )
    )
    base = replace(base, players=(base.players[0], rival, *base.players[2:]))
    state = _play(base, card, "arrakeen")
    actions = legal_agent_card_discard_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_discard"
    discard_guild = next(
        a for a in actions[1:] if dict(a.arguments)["card_id"] == guild
    )
    discarded = apply_agent_card_discard(state, discard_guild).state
    assert discarded.players[0].resources.spice == 2
    # The Spy with Deep Cover may share a post with a rival, never with its
    # own Spy; the discard offer is spent.
    assert legal_agent_card_discard_actions(discarded, 0) == ()
    posts = {
        dict(a.arguments)["post_id"] for a in legal_agent_card_spy_actions(discarded, 0)
    }
    assert "emperor-sardaukar-dutiful-service" in posts
    assert "landsraad-assembly-hall-gather-support" not in posts
    placed = apply_agent_card_spy_action(
        discarded,
        DomainAction(
            action_id="place_agent_card_spy",
            actor=0,
            arguments=(("post_id", "emperor-sardaukar-dutiful-service"),),
        ),
    ).state
    assert "emperor-sardaukar-dutiful-service" in placed.players[0].spy_post_ids
    assert legal_agent_card_spy_actions(placed, 0) == ()

    # A non-Guild discard still buys the Spy, without spice.
    discard_plain = next(
        a for a in actions[1:] if dict(a.arguments)["card_id"] == filler
    )
    plain = apply_agent_card_discard(state, discard_plain).state
    assert plain.players[0].resources.spice == 0
    assert legal_agent_card_spy_actions(plain, 0) != ()


def test_arrakis_observer_spy_may_pass_up_the_recall_with_an_empty_supply() -> None:
    # "If you have no Spies in your supply when you need to place one, you
    # may first recall one of your Spies for no effect." [Main p. 11];
    # docs/rules/uprising-systems.md: with an empty supply the recall stays
    # optional, so the owner may pass without placing (OQ-057 (14)). After
    # the paid discard the Deep Cover Spy used to have no way to lapse: the
    # recall was the only choice and the turn could not end.
    card = _card("arrakis_observer")
    filler = STARTERS[4]
    posts = (
        "emperor-sardaukar-dutiful-service",
        "fremen-desert-tactics-fremkit",
        "landsraad-assembly-hall-gather-support",
    )
    state = _play(
        _state(_owner(hand=(card, filler), spies_supply=0, spy_post_ids=posts)),
        card,
        "arrakeen",
    )
    discard = next(
        action
        for action in legal_agent_card_discard_actions(state, 0)
        if dict(action.arguments).get("card_id") == filler
    )
    discarded = apply_agent_card_discard(state, discard).state
    engine = UprisingRulesEngine()
    offered = {action.action_id for action in engine.legal_actions(discarded, 0)}
    assert {"recall_spy_for_agent_card", "finish_agent_turn"} <= offered

    passed = engine.apply(
        discarded, DomainAction(action_id="finish_agent_turn", actor=0)
    ).state
    assert passed.players[0].spy_post_ids == posts
    assert passed.players[0].spies_recalled_turn == 0
    assert passed.decision_stack[-1].kind == FrameKind.TURN


def test_arrakis_observer_recalls_a_spy_for_three_swords() -> None:
    from dune_imperium.rules.reveal_turn import apply_reveal_spy_action

    card = _card("arrakis_observer")
    owner = _owner(
        hand=(card,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        troops_supply=8,
        troops_conflict=1,
        combat_strength=2,
    )
    revealed = _reveal(_state(owner))
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"]
        == "may_recall_spy_for_three_strength"
    )
    actions = legal_reveal_spy_actions(revealed, 0)
    assert [a.action_id for a in actions] == [
        "decline_reveal_spy_recall",
        "recall_spy_for_reveal",
    ]
    recalled = apply_reveal_spy_action(revealed, actions[1]).state
    assert recalled.players[0].spy_post_ids == ()
    assert recalled.players[0].combat_strength == 2 + 3
    assert _reveal_context(recalled)["strength"] == 2 + 3
    assert _reveal_context(recalled)["optional_sword_strength"] == 3
    # No Spy on the board: the arrow cost cannot be paid, no choice opens.
    none = _reveal(_state(_owner(hand=(card,), spies_supply=3)))
    assert none.decision_stack[-1].kind == "reveal"


def test_bombast_command_pays_three_solari_and_trashes_itself() -> None:
    card = _card("bombast")
    revealed = _reveal(_state(_six_persuasion_hand(card)))
    owner = revealed.players[0]
    assert owner.resources.solari == 3
    assert card in owner.trashed
    assert card not in owner.in_play
    below = _reveal(_state(_owner(hand=(card,))))
    assert below.players[0].resources.solari == 0
    assert card in below.players[0].in_play


def test_engineered_miracle_discards_for_water_and_commands_a_row_card() -> None:
    from dune_imperium.rules.acquisition import (
        apply_reveal_command_acquisition,
        legal_reveal_command_acquisition_actions,
    )

    card = _card("engineered_miracle")
    filler = STARTERS[4]
    state = _play(_state(_owner(hand=(card, filler))), card)
    discard = next(
        a
        for a in legal_agent_card_discard_actions(state, 0)
        if a.action_id == "discard_agent_card"
    )
    assert (
        apply_agent_card_discard(state, discard).state.players[0].resources.water == 1
    )

    row = (_card("guild_envoy"), _card("sandwalk", 1))
    base = replace(_state(_six_persuasion_hand(card)), imperium_row=row)
    revealed = _reveal(base)
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"]
        == "command_may_trash_self_to_acquire_row_card"
    )
    actions = legal_reveal_command_acquisition_actions(revealed, 0)
    assert actions[0].action_id == "decline_command_acquisition"
    assert {dict(a.arguments)["instance_id"] for a in actions[1:]} == set(row)
    acquired = apply_reveal_command_acquisition(revealed, actions[1]).state
    owner = acquired.players[0]
    assert card in owner.trashed
    assert row[0] in owner.discard_pile
    assert row[0] not in acquired.imperium_row
    assert acquired.decision_stack[-1].kind == "reveal"
    # Persuasion is untouched: the card came for free.
    assert _reveal_context(acquired)["persuasion"] == 7
    declined = apply_reveal_command_acquisition(revealed, actions[0]).state
    assert card in declined.players[0].in_play
    # Below Command the choice waits; an empty Row offers nothing.
    assert _reveal(_state(_owner(hand=(card,)))).decision_stack[-1].kind == "reveal"
    assert _reveal(_state(_six_persuasion_hand(card))).decision_stack[-1].kind == (
        "reveal"
    )


def test_engineered_miracle_command_troop_joins_the_reveals_allowance() -> None:
    # "Command: Trash this card -> Acquire a card from the Imperium Row"
    # (any cost, no Persuasion) [Engineered Miracle card]; Arrakis Revolt's
    # acquire box recruits one troop [Main p. 20]. "그 turn에 어떤
    # 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수 있다"
    # [Main p. 10] [FAQ p. 4], and the Combat 아이콘 deploys "이번 turn에
    # recruit한 유닛 전부와 garrison에서 최대 두 개 ... Reveal turn에서도
    # 쓸 수 있다" [Bloodlines pp. 5, 12]. This Command acquisition used to
    # leave ``reveal_troops_recruited`` at 0.
    from dune_imperium.rules.acquisition import (
        apply_reveal_command_acquisition,
        legal_reveal_command_acquisition_actions,
    )
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    card = _card("engineered_miracle")
    arrakis_revolt = "imperium:arrakis_revolt:0"
    owner = replace(_six_persuasion_hand(card), combat_icon_turn=True)
    base = replace(_state(owner), imperium_row=(arrakis_revolt,))
    revealed = _reveal(base)
    acquire = next(
        a
        for a in legal_reveal_command_acquisition_actions(revealed, 0)
        if dict(a.arguments).get("instance_id") == arrakis_revolt
    )

    result = apply_reveal_command_acquisition(revealed, acquire).state

    assert result.players[0].troops_garrison == 4
    assert _reveal_context(result)["reveal_troops_recruited"] == 1
    assert {
        dict(action.arguments)["count"]
        for action in legal_reveal_deployments(result, 0)
        if action.action_id == "deploy_troops"
    } == {1, 2, 3}


# A Reveal-turn self-trash resolves with no AGENT_EFFECTS frame on top, so
# ``trash_personal_card`` credits a trash trigger's troops to nothing. No
# shipped card both trashes itself and recruits when trashed, so these tests
# give the self-trashing card Eliminate Allies' "When this card is trashed:
# 2 troops" (fabricated data, like ``test_acquisition.py``'s
# ``_fake_troop_contract``): "그 turn에 어떤 출처에서 recruit했든 새 troop은
# Conflict에 deploy할 수 있다" [Main p. 10] [FAQ p. 4]
# (docs/rules/player-turns.md:137), and the Combat 아이콘 deploys "이번
# turn에 recruit한 유닛 전부" [Bloodlines pp. 5, 12].


def _recruits_two_when_trashed(monkeypatch: pytest.MonkeyPatch, card_id: str) -> None:
    shipped = card_trash._trash_effect

    def fabricated(candidate: str) -> PersonalCardTrashEffect | None:
        if candidate == card_id:
            return PersonalCardTrashEffect.RECRUIT_TWO_TROOPS
        return shipped(candidate)

    monkeypatch.setattr(card_trash, "_trash_effect", fabricated)


def test_bombast_reveal_self_trash_keeps_its_trash_troops_in_the_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = _card("bombast")
    _recruits_two_when_trashed(monkeypatch, card)

    revealed = _reveal(_state(_six_persuasion_hand(card)))

    assert card in revealed.players[0].trashed
    assert revealed.players[0].troops_garrison == 3 + 2
    assert _reveal_context(revealed)["reveal_troops_recruited"] == 2


def test_bombast_drawn_mid_reveal_keeps_its_trash_troops_in_the_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = _card("bombast")
    _recruits_two_when_trashed(monkeypatch, card)
    cunning = _intrigue("cunning")
    owner = replace(_six_persuasion_hand(), deck=(card,), intrigue_cards=(cunning,))
    engine = UprisingRulesEngine()
    revealed = engine.apply(
        _state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state

    drawn = engine.apply(revealed, _play_intrigue(cunning)).state

    assert drawn.players[0].trashed.count(card) == 1
    assert drawn.players[0].troops_garrison == 3 + 2
    assert _reveal_context(drawn)["reveal_troops_recruited"] == 2


def test_bombast_command_met_late_keeps_its_trash_troops_in_the_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Five Persuasion at the Reveal's start; the drawn Convincing Argument's
    # two lift it past Command (6+), which then pays out late
    # (``grant_late_reveal_effects``) [Bloodlines p. 5].
    card = _card("bombast")
    _recruits_two_when_trashed(monkeypatch, card)
    argument = next(c for c in STARTERS if ":convincing_argument:" in c)
    cunning = _intrigue("cunning")
    owner = _owner(
        hand=(_card("sandwalk"), _card("sandwalk", 1), card),
        deck=(argument,),
        intrigue_cards=(cunning,),
    )
    engine = UprisingRulesEngine()
    revealed = engine.apply(
        _state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _reveal_context(revealed)["persuasion_generated"] == 5
    assert card in revealed.players[0].in_play

    drawn = engine.apply(revealed, _play_intrigue(cunning)).state

    assert drawn.players[0].trashed.count(card) == 1
    assert drawn.players[0].troops_garrison == 3 + 2
    assert _reveal_context(drawn)["reveal_troops_recruited"] == 2


def test_engineered_miracle_command_self_trash_keeps_its_trash_troops_in_the_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dune_imperium.rules.acquisition import (
        apply_reveal_command_acquisition,
        legal_reveal_command_acquisition_actions,
    )
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    card = _card("engineered_miracle")
    _recruits_two_when_trashed(monkeypatch, card)
    envoy = _card("guild_envoy")
    owner = replace(_six_persuasion_hand(card), combat_icon_turn=True)
    revealed = _reveal(replace(_state(owner), imperium_row=(envoy,)))
    acquire = next(
        a
        for a in legal_reveal_command_acquisition_actions(revealed, 0)
        if dict(a.arguments).get("instance_id") == envoy
    )

    result = apply_reveal_command_acquisition(revealed, acquire).state

    assert card in result.players[0].trashed
    assert result.players[0].troops_garrison == 3 + 2
    assert _reveal_context(result)["reveal_troops_recruited"] == 2
    # Two recruited plus up to two more from the garrison [Main p. 10].
    assert {
        dict(action.arguments)["count"]
        for action in legal_reveal_deployments(result, 0)
        if action.action_id == "deploy_troops"
    } == {1, 2, 3, 4}


def test_southern_faith_draws_or_takes_bene_gesserit_influence_with_a_bond() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_influence,
        legal_agent_card_influence_actions,
    )

    card = _card("southern_faith")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    assert legal_agent_card_influence_actions(state, 0) == ()
    before = len(state.players[0].hand)
    assert len(resolve_agent_card_effect(state).state.players[0].hand) == before + 1

    bonded = _play(
        _state(_owner(hand=(card,), in_play=(_card("branching_path"),))),
        card,
        "arrakeen",
    )
    actions = legal_agent_card_influence_actions(bonded, 0)
    assert [a.action_id for a in actions] == [
        "resolve_agent_card_effect",
        "choose_agent_card_influence",
    ]
    assert dict(actions[1].arguments)["faction"] == "bene_gesserit"
    gained = apply_agent_card_influence(bonded, actions[1]).state
    assert gained.players[0].influence.bene_gesserit == 1
    assert len(gained.players[0].hand) == len(bonded.players[0].hand)

    revealed = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(revealed)["persuasion"] == 1
    assert _reveal_context(revealed)["sword_strength"] == 2
    assert revealed.players[0].resources.spice == 0
    commanded = _reveal(_state(_six_persuasion_hand(card)))
    assert commanded.players[0].resources.spice == 2


def test_possible_futures_pays_both_halves_with_a_bene_gesserit_bond() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_influence,
        legal_agent_card_influence_actions,
    )

    card = _card("possible_futures")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    actions = legal_agent_card_influence_actions(state, 0)
    assert actions[0].action_id == "resolve_agent_card_effect"
    assert len(actions) == 1 + 4
    # Arrakeen already recruited one troop.
    garrison = state.players[0].troops_garrison
    troops = resolve_agent_card_effect(state).state.players[0]
    assert troops.troops_garrison == garrison + 2
    assert troops.influence.emperor == 0
    only_influence = apply_agent_card_influence(state, actions[1]).state.players[0]
    assert only_influence.troops_garrison == garrison
    assert only_influence.influence.emperor == 1

    bonded = _play(
        _state(_owner(hand=(card,), in_play=(_card("branching_path"),))),
        card,
        "arrakeen",
    )
    actions = legal_agent_card_influence_actions(bonded, 0)
    assert all(a.action_id == "choose_agent_card_influence" for a in actions)
    both = apply_agent_card_influence(bonded, actions[0]).state
    assert both.players[0].troops_garrison == garrison + 2
    assert both.players[0].influence.emperor == 1
    assert dict(both.decision_stack[-1].context)["troops_recruited"] == 1 + 2

    revealed = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(revealed)["persuasion"] == 2
    assert revealed.players[0].resources.water == 1 + 1


# --- Bloodlines Imperium (slice 4d-2) --------------------------------------


def test_urgent_shigawire_boosts_the_next_bene_gesserit_card() -> None:
    from dune_imperium.rules.agent_turn import legal_agent_actions as legal

    card = _card("urgent_shigawire")
    state = _play(_state(_owner(hand=(card,))), card, "arrakeen")
    armed = resolve_agent_card_effect(state).state
    assert armed.players[0].bene_gesserit_boost_pending is True

    # Truthtrance prints Emperor, Spacing Guild, Bene Gesserit and Fremen
    # icons (no City, no Agent-box text); boosted it reaches a City space
    # too, and the boost's own effect draws a card.
    bene_gesserit = _card("truthtrance")
    guild = _card("guild_envoy")
    boosted = _state(
        _owner(hand=(bene_gesserit, guild), bene_gesserit_boost_pending=True)
    )
    spaces = {
        dict(a.arguments)["space_id"]
        for a in legal(boosted, 0)
        if dict(a.arguments)["card_id"] == bene_gesserit
    }
    assert "arrakeen" in spaces
    # A non-Bene Gesserit card keeps its printed icons.
    guild_spaces = {
        dict(a.arguments)["space_id"]
        for a in legal(boosted, 0)
        if dict(a.arguments)["card_id"] == guild
    }
    assert "arrakeen" not in guild_spaces
    played = _play(boosted, bene_gesserit, "arrakeen")
    owner = played.players[0]
    assert owner.bene_gesserit_boost_pending is False
    # Arrakeen's own draw plus the boost's draw: the hand lost one card and
    # gained two.
    assert len(owner.hand) == 2 - 1 + 2


def test_sardaukar_standard_acquires_the_bank_commander_when_trashed() -> None:
    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.rules.sardaukar import (
        apply_skill_choice,
        begin_skill_choice,
        legal_skill_choice_actions,
    )

    card = _card("sardaukar_standard")
    skills = skill_tile_instance_ids()
    base = replace(
        _state(_owner(hand=(card,))),
        skill_face_up=skills[:4],
        skill_stack=skills[4:],
    )
    state = _play(base, card, "arrakeen")
    result = trash_personal_card(state, 0, card, source="test")
    # The trashing effect still owns the top frame; the choice is queued and
    # the engine opens it afterwards.
    assert result.state.decision_stack[-1].kind == "agent_effects"
    assert result.state.pending_skill_choices == (
        (0, card, "test:trash:" + card, False),
    )
    opened = begin_skill_choice(result.state).state
    assert opened.pending_skill_choices == ()
    frame = opened.decision_stack[-1]
    assert frame.kind == "skill_choice"
    actions = legal_skill_choice_actions(opened, 0)
    assert len(actions) == len({dict(a.arguments)["skill_id"] for a in actions})
    chosen = apply_skill_choice(opened, actions[0]).state
    owner = chosen.players[0]
    assert chosen.sardaukar_commanders_bank == 0
    assert owner.commanders_garrison == 1
    assert len(owner.skill_ids) == 1
    assert chosen.decision_stack[-1].kind == "agent_effects"
    # Recruited this turn: it joins the basic deployment count.
    assert dict(chosen.decision_stack[-1].context)["troops_recruited"] == 1 + 1

    empty = replace(state, sardaukar_commanders_bank=0)
    nothing = trash_personal_card(empty, 0, card, source="test")
    assert nothing.state.pending_skill_choices == ()
    assert nothing.events[-1].kind == "sardaukar_commander_unavailable"

    # Every face-up Skill already held: the Commander comes without a Skill
    # and no choice frame opens (OQ-031, OQ-035).
    held = replace(
        state,
        skill_face_up=(skills[1], skills[3]),
        players=replace_player(
            state.players, replace(state.players[0], skill_ids=(skills[0], skills[2]))
        ),
    )
    queued = trash_personal_card(held, 0, card, source="test").state
    direct = begin_skill_choice(queued)
    assert direct.state.decision_stack[-1].kind == "agent_effects"
    assert direct.state.sardaukar_commanders_bank == 0
    assert direct.state.players[0].commanders_garrison == 1
    assert len(direct.state.players[0].skill_ids) == 2
    assert direct.events[0].kind == "sardaukar_commander_acquired"


def test_sardaukar_standard_bank_commander_joins_the_reveals_allowance() -> None:
    # Finding 2 (2026-09-26 review round 3): ``_acquire_bank_commander``'s
    # ``with_recruited_units`` call only credits an AGENT_EFFECTS frame
    # directly on top; the Skill choice this box owes is queued and opened
    # by the engine afterwards (``begin_skill_choice``), so a bank Commander
    # acquired while a Reveal frame sits underneath used to reach the
    # garrison without ever joining the Combat 아이콘's shared deploy
    # allowance. "이번 turn에 recruit한 유닛 전부와 garrison에서 최대 두
    # 개" [Bloodlines pp. 5, 12] applies to an Agent or a Reveal turn alike
    # (docs/rules/player-turns.md:137) [Main p. 10] [FAQ p. 4].
    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.rules.sardaukar import (
        apply_skill_choice,
        begin_skill_choice,
        legal_skill_choice_actions,
    )

    card = _card("sardaukar_standard")
    skills = skill_tile_instance_ids()
    base = replace(
        _state(_owner(hand=(card,))),
        skill_face_up=skills[:4],
        skill_stack=skills[4:],
    )
    revealed = _reveal(base)
    result = trash_personal_card(revealed, 0, card, source="test")
    # The trashing effect resolves from the Reveal frame, not an
    # AGENT_EFFECTS one; the choice is still queued and opened afterwards.
    assert result.state.decision_stack[-1].kind == "reveal"
    assert result.state.pending_skill_choices == (
        (0, card, "test:trash:" + card, False),
    )
    opened = begin_skill_choice(result.state).state
    assert opened.decision_stack[-1].kind == "skill_choice"
    actions = legal_skill_choice_actions(opened, 0)
    chosen = apply_skill_choice(opened, actions[0]).state

    assert chosen.decision_stack[-1].kind == "reveal"
    assert chosen.players[0].commanders_garrison == 1
    # 1 from Sardaukar Standard's own "Reveal: 2 Persuasion + troop 1"
    # [card face] (already taken before the trash below) plus 1 from the
    # bank Commander this fix now credits.
    assert dict(chosen.decision_stack[-1].context)["reveal_troops_recruited"] == 2


def test_sardaukar_standard_trashed_before_the_turn_closes_credits_nothing() -> None:
    # 2026-09-26 review round 4, Finding 1 (Sardaukar Commander), probe B: a
    # Sardaukar Standard trashed by a caller that does *not* go through an
    # ``OPTIONAL_TRASH`` frame at all (a card's own agent-effect box, like
    # Desert Survival at Accept Contract in the reviewer's probe) reaches the
    # same closed-turn hole. The trash runs, and only *afterward* does the
    # caller's own ``advance_after_effect`` decide the turn is over, so
    # nothing at trash time could mark the queued Skill choice; the
    # retroactive flag ``advance_after_effect`` now sets on the owner's
    # currently pending ``pending_skill_choices`` (and ``pending_navigation_
    # plays``) entries when it closes a turn is what has to catch this one.
    # "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할
    # 수 있다..." [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md:137).
    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.rules.agent_effects import resolve_faction_influence
    from dune_imperium.rules.sardaukar import (
        apply_skill_choice,
        begin_skill_choice,
        legal_skill_choice_actions,
    )

    card = _card("sardaukar_standard")
    skills = skill_tile_instance_ids()
    state = replace(
        _state(_owner(hand=(card,))),
        skill_face_up=skills[:4],
        skill_stack=skills[4:],
        players=(
            _owner(hand=(card,)),
            PlayerState(player_id=1, has_revealed=True),
            PlayerState(player_id=2, has_revealed=True),
            PlayerState(player_id=3, has_revealed=True),
        ),
    )
    # Dutiful Service's own resources icon leaves only the Faction Influence
    # gain pending; Sardaukar Standard carries no Agent-turn effect of its
    # own [card face], so nothing else keeps the box open once it resolves.
    placed = _play(state, card, "dutiful_service")
    for board_action in legal_board_effect_actions(placed, 0):
        placed = resolve_board_effect(placed, board_action).state
    assert dict(placed.decision_stack[-1].context)["pending_faction_influence"] is True

    trashed = trash_personal_card(placed, 0, card, source="test:trash")
    assert trashed.state.decision_stack[-1].kind == "agent_effects"
    assert trashed.state.pending_skill_choices[0][3] is False

    closed = resolve_faction_influence(trashed.state).state
    assert closed.decision_stack[-1].kind == "turn"
    assert dict(closed.decision_stack[-1].context)["turn_owner"] == 0
    # Retroactively flagged: the trash ran before this call decided the
    # effect frame was done (OQ-044 (d)).
    assert closed.pending_skill_choices[0][3] is True

    opened = begin_skill_choice(closed).state
    assert dict(opened.decision_stack[-1].context).get("turn_closed") is True
    actions = legal_skill_choice_actions(opened, 0)
    chosen = apply_skill_choice(opened, actions[0]).state

    assert chosen.players[0].commanders_garrison == 1
    top = chosen.decision_stack[-1]
    assert top.kind == "turn"
    assert dict(top.context)["turn_owner"] == 0
    assert dict(top.context).get("troops_recruited") in (None, 0)


def test_litany_against_fear_draws_and_passes_the_turn() -> None:
    from dune_imperium.rules.agent_turn import (
        apply_turn_start_card,
        legal_turn_start_card_actions,
    )

    card = _card("litany_against_fear")
    state = _state(_owner(hand=(card,)))
    actions = legal_turn_start_card_actions(state, 0)
    assert [dict(a.arguments)["card_id"] for a in actions] == [card]
    assert actions[0] in UprisingRulesEngine().legal_actions(state, 0)
    # No Agent icons: the card cannot be sent anywhere.
    assert legal_agent_actions(state, 0) == ()
    passed = apply_turn_start_card(state, actions[0]).state
    owner = passed.players[0]
    assert card in owner.in_play
    assert len(owner.hand) == 1
    assert owner.agents_available == 2
    assert owner.has_revealed is False
    frame = passed.decision_stack[-1]
    assert frame.kind == "turn"
    assert dict(frame.context)["turn_owner"] == 1


def test_delivery_logistics_borrows_its_contract_icons() -> None:
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_persuasion_or_contract,
        legal_reveal_persuasion_or_contract_actions,
    )

    card = _card("delivery_logistics")
    none = _state(_owner(hand=(card,)), CHOAM_BLOODLINES)
    assert legal_agent_actions(none, 0) == ()
    contracted = _state(
        _owner(
            hand=(card,),
            active_contract_ids=("contract:arrakeen_i", "contract:harvest_3"),
        ),
        CHOAM_BLOODLINES,
    )
    spaces = {dict(a.arguments)["space_id"] for a in legal_agent_actions(contracted, 0)}
    assert {"arrakeen", "imperial_basin"} <= spaces
    assert "assembly_hall" not in spaces

    revealed = _reveal(
        replace(
            _state(_owner(hand=(card,)), CHOAM_BLOODLINES),
            face_up_contract_ids=("contract:heighliner_i",),
        )
    )
    frame = revealed.decision_stack[-1]
    assert dict(frame.context)["reveal_choice_effect"] == "persuasion_or_contract"
    actions = legal_reveal_persuasion_or_contract_actions(revealed, 0)
    assert [a.action_id for a in actions] == [
        "gain_reveal_persuasion",
        "take_reveal_contract",
    ]
    persuaded = apply_reveal_persuasion_or_contract(revealed, actions[0]).state
    assert _reveal_context(persuaded)["persuasion"] == 1
    assert persuaded.decision_stack[-1].kind == "reveal"
    contracted_reveal = apply_reveal_persuasion_or_contract(revealed, actions[1]).state
    assert contracted_reveal.decision_stack[-1].kind == "contract_market"
    assert _reveal_context(contracted_reveal)["persuasion"] == 0


def test_choam_demands_completes_a_contract_and_trashes_for_influence() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_contract_completion,
        legal_agent_card_contract_completion_actions,
    )

    card = _card("choam_demands")
    idle = _play(_state(_owner(hand=(card,)), CHOAM_BLOODLINES), card, "arrakeen")
    assert legal_agent_card_contract_completion_actions(idle, 0) == ()
    assert (
        resolve_agent_card_effect(idle).events[0].kind
        == "agent_card_effect_unavailable"
    )

    contracted = _play(
        _state(
            _owner(hand=(card,), active_contract_ids=("contract:heighliner_ii",)),
            CHOAM_BLOODLINES,
        ),
        card,
        "arrakeen",
    )
    actions = legal_agent_card_contract_completion_actions(contracted, 0)
    assert [dict(a.arguments)["instance_id"] for a in actions] == [
        "contract:heighliner_ii"
    ]
    garrison = contracted.players[0].troops_garrison
    completed = apply_agent_card_contract_completion(contracted, actions[0]).state
    owner = completed.players[0]
    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == ("contract:heighliner_ii",)
    assert owner.troops_garrison == garrison + 2
    assert owner.contracts_completed_turn == 1
    context = dict(completed.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    assert context["troops_recruited"] == 1 + 2

    four = (
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
        "contract:harvest_3",
        "contract:harvest_4",
    )
    revealed = _reveal(
        _state(_owner(hand=(card,), completed_contract_ids=four), CHOAM_BLOODLINES)
    )
    frame = revealed.decision_stack[-1]
    assert (
        dict(frame.context)["reveal_choice_effect"]
        == "may_trash_self_for_four_influence_if_four_contracts"
    )
    actions = legal_reveal_card_trash_actions(revealed, 0)
    assert [a.action_id for a in actions] == [
        "decline_reveal_card_trash",
        "trash_reveal_card",
    ]
    trashed = apply_reveal_card_trash(revealed, actions[1]).state
    owner = trashed.players[0]
    assert card in owner.trashed
    assert owner.influence == Influence(
        emperor=1, spacing_guild=1, bene_gesserit=1, fremen=1
    )
    below = _reveal(
        _state(_owner(hand=(card,), completed_contract_ids=four[:3]), CHOAM_BLOODLINES)
    )
    assert below.decision_stack[-1].kind == "reveal"


@pytest.mark.parametrize(
    "contract_id", ("contract:sardaukar_ii", "contract:bloodlines_high_council")
)
def test_choam_demands_recall_reward_never_takes_this_turns_agent(
    contract_id: str,
) -> None:
    # Sardaukar II (and the Bloodlines High Council token) print the Recall
    # Agent icon [Sardaukar II card]: "Return one of your other Agents on the
    # board to your Leader (not the Agent you sent during this turn)"
    # [Main p. 20]. Completed by CHOAM Demands' Agent box, the Agent just
    # sent to Arrakeen used to be a legal target.
    #
    # User ruling (2026-09-26, verbatim): "Duncan Idaho(Bloodlines) Into the
    # Fray의 Agent를 Imperial Privilege로 recall 가능 이니까 recall agent
    # 기능으로 되는건 모두 같게 동작해야지. 사다우카 계약 완료보상이나 원로회
    # 계약 완료보상에 있는 recall agent도 마찬가지겠지" (OQ-068): an earlier
    # turn's Into the Fray Agent in the Conflict (OQ-037 (d)) is one of
    # "your Agents" the reward may recall too, so it no longer fizzles when
    # that Conflict Agent is the only other one.
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_contract_completion,
        legal_agent_card_contract_completion_actions,
    )
    from dune_imperium.rules.contracts import (
        apply_contract_recall_action,
        legal_contract_recall_actions,
    )

    card = _card("choam_demands")

    def complete(**overrides: object) -> tuple[GameState, tuple[str, ...]]:
        state = _play(
            _state(
                _owner(hand=(card,), active_contract_ids=(contract_id,), **overrides),
                CHOAM_BLOODLINES,
            ),
            card,
            "arrakeen",
        )
        action = legal_agent_card_contract_completion_actions(state, 0)[0]
        result = apply_agent_card_contract_completion(state, action)
        return result.state, tuple(event.kind for event in result.events)

    alone, kinds = complete()
    assert alone.players[0].agent_locations == ("arrakeen",)
    assert "contract_recall_unavailable" in kinds
    assert alone.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert legal_contract_recall_actions(alone, 0) == ()

    earlier, _ = complete(agent_locations=("hagga_basin",), agents_available=1)
    assert earlier.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_RECALL
    assert [
        dict(action.arguments)["space_id"]
        for action in legal_contract_recall_actions(earlier, 0)
    ] == ["hagga_basin"]

    # An earlier turn's Into the Fray Agent, alone in the Conflict, used to
    # leave the reward with nothing to recall and it fizzled (OQ-068 fixes
    # this); it is never this turn's own Agent, which stayed on Arrakeen.
    conflict, conflict_kinds = complete(agent_in_conflict=1, agents_available=1)
    assert "contract_recall_unavailable" not in conflict_kinds
    assert conflict.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_RECALL
    recalls = legal_contract_recall_actions(conflict, 0)
    assert [action.action_id for action in recalls] == [
        "recall_conflict_agent_for_contract"
    ]
    resolved = apply_contract_recall_action(conflict, recalls[0]).state.players[0]
    assert resolved.agent_in_conflict == 0
    assert resolved.agents_available == 1
    assert resolved.agent_locations == ("arrakeen",)


_FAR_POSTS = (
    "emperor-sardaukar-dutiful-service",
    "arrakis-hagga-basin",
    "arrakis-deep-desert",
)


def _last_to_reveal(state: GameState) -> GameState:
    return replace(
        state,
        players=(
            state.players[0],
            *(replace(seat, has_revealed=True) for seat in state.players[1:]),
        ),
    )


def _recall_and_place_contract_spy(state: GameState) -> GameState:
    engine = UprisingRulesEngine()
    assert state.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_SPY
    assert state.decision_stack[-2].kind == FrameKind.TURN
    recall = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "recall_spy_for_contract"
    )
    recalled = engine.apply(state, recall).state
    return engine.apply(recalled, engine.legal_actions(recalled, 0)[0]).state


def test_a_contract_spy_recall_after_the_turn_closed_is_not_the_next_turns() -> None:
    # "If a contract's condition is sending an Agent to a board space, the
    # contract is another effect of your Agent turn." [FAQ p. 1], and "If
    # you recalled a Spy this turn" counts the seat's recalls in its own
    # turn (OQ-044 (d)). Completed as the turn's last effect by the last
    # seat to reveal, the reward's recall-first ("you may first recall one
    # of your Spies for no effect" [Main pp. 11, 20]) resolved after the
    # seat's next turn had opened, and counted for that next turn.
    seek_allies = next(card for card in STARTERS if ":seek_allies:" in card)
    state = _last_to_reveal(
        _state(
            _owner(
                hand=(seek_allies,),
                spies_supply=0,
                spy_post_ids=_FAR_POSTS,
                active_contract_ids=("contract:bloodlines_deliver_supplies",),
            ),
            CHOAM_BLOODLINES,
        )
    )
    engine = UprisingRulesEngine()
    current = _play(state, seek_allies, "deliver_supplies")
    for _ in range(10):
        if current.decision_stack[-1].kind != FrameKind.AGENT_EFFECTS:
            break
        offered = engine.legal_actions(current, 0)
        pick = next(
            (a for a in offered if a.action_id != "complete_contract"), offered[0]
        )
        current = engine.apply(current, pick).state
    placed = _recall_and_place_contract_spy(current)

    seat = placed.players[0]
    assert placed.decision_stack[-1].kind == FrameKind.TURN
    assert seat.spies_supply == 0 and len(seat.spy_post_ids) == 3
    assert seat.spies_recalled_turn == 0


def test_choam_demands_spy_recall_after_the_turn_closed_is_not_the_next_turns() -> (
    None
):
    # The same for a Contract completed by CHOAM Demands' Agent box
    # ("Complete one of your contracts." [CHOAM Demands card]) as the turn's
    # last effect: its Spy frame is re-pushed above the next turn (OQ-044
    # (d)).
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_contract_completion,
        legal_agent_card_contract_completion_actions,
    )

    card = _card("choam_demands")
    state = _last_to_reveal(
        _state(
            _owner(
                hand=(card,),
                spies_supply=0,
                spy_post_ids=_FAR_POSTS,
                active_contract_ids=("contract:arrakeen_ii",),
            ),
            CHOAM_BLOODLINES,
        )
    )
    played = _play(state, card, "assembly_hall")
    completion = legal_agent_card_contract_completion_actions(played, 0)[0]
    completed = apply_agent_card_contract_completion(played, completion).state
    placed = _recall_and_place_contract_spy(completed)

    assert placed.decision_stack[-1].kind == FrameKind.TURN
    assert placed.players[0].spies_recalled_turn == 0


# --- Bloodlines slice 4d-3: Holy War, False Orders, Coercive Negotiation --


ASSEMBLY_POST = "landsraad-assembly-hall-gather-support"


def test_holy_war_makes_each_opponent_lose_a_unit_and_move_its_spy() -> None:
    from dune_imperium.rules.spy_moves import apply_spy_move, legal_spy_move_actions
    from dune_imperium.rules.unit_loss import (
        apply_unit_loss,
        legal_unit_loss_actions,
    )

    card = _card("holy_war")
    watcher = replace(
        PlayerState(player_id=1),
        spies_supply=2,
        spy_post_ids=(ASSEMBLY_POST,),
        troops_supply=8,
        troops_garrison=2,
        troops_conflict=2,
        commanders_supply=0,
        commanders_conflict=1,
        combat_strength=6,
    )
    garrisoned = replace(PlayerState(player_id=2), troops_supply=11, troops_garrison=1)
    empty = replace(PlayerState(player_id=3), troops_supply=12, troops_garrison=0)
    base = _state(_owner(hand=(card,)))
    base = replace(base, players=(base.players[0], watcher, garrisoned, empty))
    state = _play(base, card, "assembly_hall")
    result = resolve_agent_card_effect(state)
    kinds = [event.kind for event in result.events]
    assert "unit_lost" in kinds and "unit_loss_unavailable" in kinds
    # Seat 2 lost its only-zone troop at once; seat 3 had nothing to lose.
    assert result.state.players[2].troops_garrison == 0
    assert result.state.players[2].troops_supply == 12
    # Seat 1 moves its Spy, then chooses the zone; both frames are on top.
    stack = result.state.decision_stack
    assert [frame.kind for frame in stack[-2:]] == [
        "opponent_unit_loss",
        "opponent_spy_move",
    ]
    moves = legal_spy_move_actions(result.state, 1)
    targets = {dict(a.arguments)["post_id"] for a in moves}
    assert ASSEMBLY_POST not in targets and targets
    moved = apply_spy_move(result.state, moves[0]).state
    assert ASSEMBLY_POST not in moved.players[1].spy_post_ids
    assert len(moved.players[1].spy_post_ids) == 1
    # The loser picks the zone and the unit kind (OQ-036).
    actions = legal_unit_loss_actions(moved, 1)
    assert [tuple(a.arguments) for a in actions] == [
        (("zone", "garrison"),),
        (("zone", "conflict"),),
        (("commanders", 1), ("zone", "conflict")),
    ]
    lost = apply_unit_loss(moved, actions[2]).state
    assert lost.players[1].commanders_conflict == 0
    assert lost.players[1].commanders_supply == 1
    assert lost.players[1].troops_conflict == 2
    assert lost.players[1].combat_strength == 4
    # Nothing else was pending in the Agent turn, so the next turn opened.
    assert lost.decision_stack[-1].kind == "turn"


def test_a_forced_spy_move_is_not_a_recall_for_the_next_seats_turn() -> None:
    # Holy War: "Each opponent spying on the board space where you sent an
    # Agent this turn must move that Spy." [Holy War card]; the FAQ calls it
    # a move "to an empty observation post" [FAQ p. 2], not a return "from
    # an observation post to your supply" (Recall Spy, [Main p. 11]), and
    # "If you recalled a Spy this turn" counts the seat's own recalls in its
    # own turn (OQ-044 (d)). Resolved as the turn's last effect, Holy War's
    # move runs after seat 1's turn has opened; the move used to count as
    # seat 1's recall, so Rebel Supplier recruited for free.
    from dune_imperium.rules.spy_moves import apply_spy_move, legal_spy_move_actions

    card = _card("holy_war")
    supplier = _card("rebel_supplier")
    watcher = replace(
        PlayerState(player_id=1),
        hand=(supplier,),
        spies_supply=2,
        spy_post_ids=(ASSEMBLY_POST,),
    )
    base = _state(_owner(hand=(card,)))
    base = replace(base, players=(base.players[0], watcher, *base.players[2:]))
    result = resolve_agent_card_effect(_play(base, card, "assembly_hall"))
    stack = result.state.decision_stack[-2:]
    assert [frame.kind for frame in stack] == ["turn", "opponent_spy_move"]
    assert all(
        isinstance(frame.decision, PlayerDecision) and frame.decision.owner == 1
        for frame in stack
    )
    move = next(
        action
        for action in legal_spy_move_actions(result.state, 1)
        if dict(action.arguments)["post_id"] == "arrakis-deep-desert"
    )
    moved = apply_spy_move(result.state, move).state
    assert moved.players[1].spy_post_ids == ("arrakis-deep-desert",)
    assert moved.players[1].spies_recalled_turn == 0

    engine = UprisingRulesEngine()
    sent = engine.apply(
        moved,
        next(
            action
            for action in legal_agent_actions(moved, 1)
            if dict(action.arguments)["space_id"] == "arrakeen"
            and dict(action.arguments)["card_id"] == supplier
        ),
    ).state
    offered = {action.action_id for action in engine.legal_actions(sent, 1)}
    assert "resolve_agent_card_effect" not in offered


def test_holy_war_reveal_recruits_and_bonds_for_the_combat_icon() -> None:
    card = _card("holy_war")
    plain = _reveal(_state(_owner(hand=(card,))))
    assert _reveal_context(plain)["persuasion"] == 1
    assert plain.players[0].troops_garrison == 3 + 1
    assert _reveal_context(plain)["combat_deployment"] is False
    bonded = _reveal(_state(_owner(hand=(card,), in_play=(_card("desert_power"),))))
    assert _reveal_context(bonded)["combat_deployment"] is True


@pytest.mark.parametrize("bonded", [True, False])
def test_holy_war_drawn_mid_reveal_still_bonds_for_the_combat_icon(
    bonded: bool,
) -> None:
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    # "If you draw a card during your Reveal turn ... you must immediately
    # reveal that card and use it this turn" [FAQ p. 3]; Holy War's "Fremen
    # Bond: [Combat]" [Holy War card] lets this Reveal "deploy troops to the
    # Conflict as though you'd sent an Agent to a Combat space" [Bloodlines
    # p. 5] (bloodlines.md §4). Stilgar, The Devoted (Fremen) is revealed,
    # Cunning's Plot draws Holy War: before the fix its Bond line was recorded
    # as paid but the deployment window never opened.
    card = _card("holy_war")
    revealed_card = _card("stilgar_the_devoted") if bonded else STARTERS[0]
    cunning = _intrigue("cunning")
    owner = _owner(hand=(revealed_card,), deck=(card,), intrigue_cards=(cunning,))
    engine = UprisingRulesEngine()
    revealed = engine.apply(
        _state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _reveal_context(revealed)["combat_deployment"] is False
    drawn = engine.apply(revealed, _play_intrigue(cunning)).state
    assert card in drawn.players[0].in_play
    assert _reveal_context(drawn)["combat_deployment"] is bonded
    deployments = {
        a.action_id for a in engine.legal_actions(drawn, 0)
    } & {a.action_id for a in legal_reveal_deployments(drawn, 0)}
    assert ("deploy_troops" in deployments) is bonded


def test_false_orders_moves_watching_spies_then_places_one() -> None:
    from dune_imperium.rules.intrigue import legal_intrigue_play_actions
    from dune_imperium.rules.spy_moves import (
        apply_spy_move,
        apply_spy_placement,
        legal_spy_move_actions,
        legal_spy_placement_actions,
    )

    card = _intrigue("false_orders")
    watcher = replace(
        PlayerState(player_id=1), spies_supply=2, spy_post_ids=(ASSEMBLY_POST,)
    )
    # Branching Path no longer prints the Landsraad icon (re-transcribed
    # 2026-09-19: Bene Gesserit + City); Sardaukar Coordination has no
    # Agent-box text either, so it stands in as an inert Landsraad card.
    landsraad = _card("sardaukar_coordination")
    base = _state(_owner(hand=(landsraad,), intrigue_cards=(card,)))
    base = replace(base, players=(base.players[0], watcher, *base.players[2:]))
    # Before any placement there is no "space where you sent an Agent".
    assert _play_intrigue(card) not in legal_intrigue_play_actions(base, 0)
    state = _play(base, landsraad, "assembly_hall")
    assert _play_intrigue(card) in legal_intrigue_play_actions(state, 0)
    engine = UprisingRulesEngine()
    played = engine.apply(state, _play_intrigue(card)).state
    assert [frame.kind for frame in played.decision_stack[-2:]] == [
        "spy_placement",
        "opponent_spy_move",
    ]
    moves = legal_spy_move_actions(played, 1)
    moved = apply_spy_move(played, moves[0]).state
    assert ASSEMBLY_POST not in moved.players[1].spy_post_ids
    placements = legal_spy_placement_actions(moved, 0)
    assert [dict(a.arguments)["post_id"] for a in placements] == [ASSEMBLY_POST]
    placed = apply_spy_placement(moved, placements[0]).state
    assert ASSEMBLY_POST in placed.players[0].spy_post_ids
    assert placed.decision_stack[-1].kind == "agent_effects"


REFINERY_POSTS = (
    "arrakis-research-station-spice-refinery",
    "arrakis-spice-refinery-arrakeen",
)


def test_false_orders_moves_the_spy_off_every_post_of_the_space() -> None:
    # "Each opponent affected by this card must move their Spy to an empty
    # observation post that isn't connected to the space where you sent an
    # Agent this turn." [FAQ p. 2]. Spice Refinery watches two posts; the
    # watcher used to be allowed onto the other one and keep spying.
    from dune_imperium.rules.spy_moves import (
        apply_spy_move,
        apply_spy_placement,
        legal_spy_move_actions,
        legal_spy_placement_actions,
    )

    card = _intrigue("false_orders")
    city = STARTERS[7]  # Reconnaissance: the City Agent icon.
    watcher = replace(
        PlayerState(player_id=1), spies_supply=2, spy_post_ids=(REFINERY_POSTS[0],)
    )
    base = _state(_owner(hand=(city,), intrigue_cards=(card,)))
    base = replace(base, players=(base.players[0], watcher, *base.players[2:]))
    state = _play(base, city, "spice_refinery")
    played = UprisingRulesEngine().apply(state, _play_intrigue(card)).state
    moves = legal_spy_move_actions(played, 1)
    targets = {dict(a.arguments)["post_id"] for a in moves}
    assert targets
    assert not targets & set(REFINERY_POSTS)
    moved = apply_spy_move(played, moves[0]).state
    assert not set(moved.players[1].spy_post_ids) & set(REFINERY_POSTS)
    # "Then you [Spy] on that space": both of its posts are free now.
    placements = legal_spy_placement_actions(moved, 0)
    assert {dict(a.arguments)["post_id"] for a in placements} == set(REFINERY_POSTS)
    placed = apply_spy_placement(moved, placements[0]).state
    assert placed.players[0].spy_post_ids == (REFINERY_POSTS[0],)


def test_holy_war_moves_the_spy_off_every_post_of_the_space() -> None:
    # Holy War prints the same sentence as False Orders ("Each opponent
    # spying on the board space where you sent an Agent this turn must move
    # that Spy." [Holy War card]); the user extended the FAQ's destination
    # [FAQ p. 2] to it on 2026-09-26 (OQ-036 (b)).
    from dune_imperium.rules.spy_moves import legal_spy_move_actions

    card = _card("holy_war")
    watcher = replace(
        PlayerState(player_id=1),
        spies_supply=2,
        spy_post_ids=(REFINERY_POSTS[1],),
        troops_supply=12,
        troops_garrison=0,
    )
    # A granted City icon (as Emperor's Invitation grants one) sends Holy War
    # to the two-post Spice Refinery.
    owner = _owner(hand=(card,), granted_agent_icon_turn="city")
    base = _state(owner)
    base = replace(base, players=(base.players[0], watcher, *base.players[2:]))
    state = _play(base, card, "spice_refinery")
    result = resolve_agent_card_effect(state)
    assert result.state.decision_stack[-1].kind == "opponent_spy_move"
    targets = {
        dict(a.arguments)["post_id"]
        for a in legal_spy_move_actions(result.state, 1)
    }
    assert targets
    assert not targets & set(REFINERY_POSTS)


def test_a_forced_spy_move_with_no_post_off_the_space_loses_the_spy() -> None:
    # All twelve Spies are out and every post not connected to Spice
    # Refinery is taken: the FAQ's destination [FAQ p. 2] does not exist, so
    # the Spy is lost to its owner's supply, like a Rival's ("If all other
    # Faction observation posts are full, the Spy is lost." [Bloodlines
    # p. 8]; OQ-065).
    from dune_imperium.content.uprising.board import OBSERVATION_POSTS
    from dune_imperium.rules.spy_moves import (
        apply_spy_move,
        legal_spy_move_actions,
        turn_space_spy_frames,
    )

    off_space = [
        post.post_id
        for post in OBSERVATION_POSTS
        if post.post_id not in REFINERY_POSTS
    ]
    assert len(off_space) == 11
    seats = (
        _owner(spies_supply=0, spy_post_ids=tuple(off_space[0:3])),
        PlayerState(
            player_id=1,
            spies_supply=0,
            spy_post_ids=(REFINERY_POSTS[0], *off_space[3:5]),
        ),
        PlayerState(player_id=2, spies_supply=0, spy_post_ids=tuple(off_space[5:8])),
        PlayerState(player_id=3, spies_supply=0, spy_post_ids=tuple(off_space[8:11])),
    )
    state = replace(_state(seats[0]), players=seats)
    pushed = turn_space_spy_frames(state, 0, "spice_refinery", source="test").state
    actions = legal_spy_move_actions(pushed, 1)
    assert [a.action_id for a in actions] == ["lose_moved_spy"]
    lost = apply_spy_move(pushed, actions[0])
    assert lost.state.players[1].spy_post_ids == tuple(off_space[3:5])
    assert lost.state.players[1].spies_supply == 1
    # Lost to a forced move, not recalled by its owner (OQ-044 (d)).
    assert lost.state.players[1].spies_recalled_turn == 0
    assert lost.state.decision_stack == state.decision_stack
    assert "spy_lost" in [event.kind for event in lost.events]


def test_forced_spy_moves_go_seat_by_seat_from_the_next_seat() -> None:
    # User ruling 2026-09-26 (OQ-036 (b), OQ-065): "스파이 옮기는건 카드 쓴
    # 다음 사람부터 순서대로 하는걸로. 한 사람이 여러 스파이를 옮겨야하면 그
    # 사람 차례에 모두 옮길 수 있도록. 갈 곳 없는 스파이는 공급처로 되돌아가게
    # 하기." The FAQ orders Mohiam's opponent discards the same way,
    # "beginning with the player to your left and proceeding clockwise"
    # [FAQ p. 3]. Seat 1 has a Spy on both Spice Refinery posts and seat 2 a
    # Spy with Deep Cover on one of them; the other nine Spies leave two of
    # the eleven unconnected posts empty [FAQ p. 2], so seat 1 moves both
    # of its Spies first and seat 2, last, loses its Spy to its supply.
    from dune_imperium.content.uprising.board import OBSERVATION_POSTS
    from dune_imperium.rules.spy_moves import (
        apply_spy_move,
        legal_spy_move_actions,
        turn_space_spy_frames,
    )

    off_space = [
        post.post_id
        for post in OBSERVATION_POSTS
        if post.post_id not in REFINERY_POSTS
    ]
    seats = (
        _owner(spies_supply=0, spy_post_ids=tuple(off_space[0:3])),
        PlayerState(
            player_id=1,
            spies_supply=0,
            spy_post_ids=(*REFINERY_POSTS, off_space[3]),
        ),
        PlayerState(
            player_id=2,
            spies_supply=0,
            spy_post_ids=(REFINERY_POSTS[0], *off_space[4:6]),
        ),
        PlayerState(player_id=3, spies_supply=0, spy_post_ids=tuple(off_space[6:9])),
    )
    state = replace(_state(seats[0]), players=seats)
    pushed = turn_space_spy_frames(state, 0, "spice_refinery", source="test").state
    added = pushed.decision_stack[len(state.decision_stack) :]
    # Top of the stack first: seat 1's two moves, then seat 2's.
    owners = [
        frame.decision.owner
        for frame in reversed(added)
        if isinstance(frame.decision, PlayerDecision)
    ]
    assert owners == [1, 1, 2]

    moving = pushed
    for destination in off_space[9:11]:
        move = next(
            action
            for action in legal_spy_move_actions(moving, 1)
            if dict(action.arguments).get("post_id") == destination
        )
        moving = apply_spy_move(moving, move).state
    assert set(moving.players[1].spy_post_ids) == {off_space[3], *off_space[9:11]}
    actions = legal_spy_move_actions(moving, 2)
    assert [action.action_id for action in actions] == ["lose_moved_spy"]
    lost = apply_spy_move(moving, actions[0]).state
    assert lost.players[2].spy_post_ids == tuple(off_space[4:6])
    assert lost.players[2].spies_supply == 1
    assert lost.decision_stack == state.decision_stack


def test_coercive_negotiation_reveals_three_contracts_on_a_big_deployment() -> None:
    from dune_imperium.content.uprising.contracts import contract_instance_ids
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.rules.intrigue_triggers import (
        apply_trigger_contract_action,
        legal_trigger_contract_actions,
        offer_deployment_triggers,
    )

    card = _intrigue("coercive_negotiation")
    bank = contract_instance_ids()[:5]
    base = replace(
        _state(
            _owner(intrigue_faceup=(card,), units_deployed_turn=3), CHOAM_BLOODLINES
        ),
        contract_bank=bank,
    )
    offered = offer_deployment_triggers(RuleResult(state=base)).state
    frame = offered.decision_stack[-1]
    assert frame.kind == "intrigue_trigger_contract"
    actions = legal_trigger_contract_actions(offered, 0)
    # No "may" on the card ("Reveal three contracts from the bank. Take one
    # and trash the other two." [Coercive Negotiation card]), and "Most
    # effects from a board space or card you play are mandatory, unless a
    # card says 'you may' do something" [FAQ p. 3]: no decline is offered
    # while a revealed Contract can be taken (it used to be).
    assert {a.action_id for a in actions} == {"take_trigger_contract"}
    assert [dict(a.arguments)["instance_id"] for a in actions] == list(bank[:3])
    taken = apply_trigger_contract_action(offered, actions[1]).state
    owner = taken.players[0]
    assert owner.active_contract_ids == (bank[1],)
    assert owner.intrigue_faceup == ()
    assert card in taken.intrigue_discard
    assert taken.contract_bank == bank[3:]
    assert taken.contract_trash == (bank[0], bank[2])
    # The decline action is gone altogether (OQ-064).
    from dune_imperium.adapters import ActionCodec

    assert "decline_intrigue_contract_trigger" not in {
        template.action_id for template in ActionCodec(CHOAM_BLOODLINES).catalog
    }
    # Without the CHOAM bank the trigger has nothing to reveal.
    quiet = offer_deployment_triggers(
        RuleResult(state=replace(base, contract_bank=()))
    ).state
    assert quiet.decision_stack[-1].kind == "turn"


def test_engineered_miracle_command_lapses_once_the_card_left_play() -> None:
    # The Command choice waits in the freely ordered Reveal; if another
    # effect trashes Engineered Miracle first, its box can't be activated
    # any more (OQ-022), so only the refusal remains (soak seed 901).
    from dune_imperium.rules.acquisition import (
        apply_reveal_command_acquisition,
        legal_reveal_command_acquisition_actions,
    )

    card = _card("engineered_miracle")
    row = (_card("guild_envoy"),)
    revealed = _reveal(replace(_state(_six_persuasion_hand(card)), imperium_row=row))
    assert len(legal_reveal_command_acquisition_actions(revealed, 0)) == 2
    gone = trash_personal_card(revealed, 0, card, source="test").state
    actions = legal_reveal_command_acquisition_actions(gone, 0)
    assert [a.action_id for a in actions] == ["decline_command_acquisition"]
    declined = apply_reveal_command_acquisition(gone, actions[0]).state
    assert declined.decision_stack[-1].kind == "reveal"
    assert declined.imperium_row == row


# --- Ruthless Leadership (Bloodlines promo, card face) ------------------------

PROMO_BLOODLINES = RulesetConfig(bloodlines=True, promo_cards=True)


def test_ruthless_leadership_is_transcribed_and_needs_both_options() -> None:
    from dune_imperium.content.uprising.imperium import (
        IMPERIUM_CARDS_BY_ID,
        imperium_deck_instance_ids,
    )

    entry = IMPERIUM_CARDS_BY_ID["ruthless_leadership"]
    assert entry.promo and entry.bloodlines_only and entry.play_data_complete
    assert entry.card.catalog_url is None
    assert (entry.acquisition_cost, entry.reveal_persuasion, entry.reveal_strength) == (
        4,
        1,
        1,
    )
    assert [icon.value for icon in entry.agent_icons] == ["city", "spice_trade"]
    (command,) = entry.reveal_effects
    assert command.requires_command and command.grants_combat_icon
    card = _card("ruthless_leadership")
    # Outside the retail decks: dealt only with the promo option and the
    # expansion together, since its Agent box reads the Commanders.
    assert card not in imperium_deck_instance_ids(False, True)
    assert card not in imperium_deck_instance_ids(False, False, bloodlines=True)
    assert card in imperium_deck_instance_ids(False, True, bloodlines=True)
    assert card in imperium_deck_instance_ids(
        True, True, bloodlines=True, tech_module=True
    )
    assert PROMO_BLOODLINES.identifier == "uprising-4p-base+promo+bloodlines"


def test_ruthless_leadership_trashes_up_to_two_cards_with_a_commander() -> None:
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_trash,
        legal_agent_card_trash_actions,
    )

    card = _card("ruthless_leadership")
    filler = STARTERS[4]
    discarded = STARTERS[5]
    owner = _owner(
        hand=(card, filler), discard_pile=(discarded,), commanders_conflict=1
    )
    state = _play(_state(owner, PROMO_BLOODLINES), card, "imperial_basin")
    # Two black trash icons: each an optional trash from hand, discard pile
    # or in play [Main p. 20], offered one at a time.
    actions = legal_agent_card_trash_actions(state, 0)
    assert actions[0].action_id == "decline_agent_card_trash"
    assert {dict(a.arguments)["card_id"] for a in actions[1:]} == {
        card,
        filler,
        discarded,
    }
    first = next(a for a in actions[1:] if dict(a.arguments)["card_id"] == discarded)
    once = apply_agent_card_trash(state, first).state
    assert discarded in once.players[0].trashed
    context = dict(once.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert context["trashes_remaining"] == 1
    again = legal_agent_card_trash_actions(once, 0)
    assert again[0].action_id == "decline_agent_card_trash"
    assert {dict(a.arguments)["card_id"] for a in again[1:]} == {card, filler}
    second = next(a for a in again[1:] if dict(a.arguments)["card_id"] == card)
    twice = apply_agent_card_trash(once, second).state
    assert {discarded, card} <= set(twice.players[0].trashed)
    assert legal_agent_card_trash_actions(twice, 0) == ()
    assert all("trashes_remaining" not in dict(f.context) for f in twice.decision_stack)
    # Declining after the first trash closes the box with the card in play.
    declined = apply_agent_card_trash(once, again[0]).state
    assert legal_agent_card_trash_actions(declined, 0) == ()
    assert card in declined.players[0].in_play
    assert declined.players[0].trashed == (discarded,)


def test_ruthless_leadership_without_a_commander_resolves_without_effect() -> None:
    from dune_imperium.rules.agent_effect_frame import legal_agent_effect_frame_actions
    from dune_imperium.rules.agent_effects import legal_agent_card_trash_actions

    card = _card("ruthless_leadership")
    state = _play(
        _state(_owner(hand=(card, STARTERS[4])), PROMO_BLOODLINES),
        card,
        "imperial_basin",
    )
    # The condition is judged when the box resolves (OQ-028); a Commander in
    # the garrison or the supply does not count.
    garrisoned = replace_player(
        state.players, replace(state.players[0], commanders_garrison=1)
    )
    state = replace(state, players=garrisoned)
    assert legal_agent_card_trash_actions(state, 0) == ()
    # The stalled mandatory box is not offered to fizzle on demand; only the
    # explicit turn end resolves it (designer ruling, OQ-057).
    resolve = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    frame_actions = legal_agent_effect_frame_actions(state, 0)
    assert resolve not in frame_actions
    finish = DomainAction(action_id="finish_agent_turn", actor=0)
    assert finish not in frame_actions  # the Maker harvest is still pending
    harvested = UprisingRulesEngine().apply(
        state,
        next(a for a in frame_actions if a.action_id == "harvest_maker_spice"),
    ).state
    assert finish in legal_agent_effect_frame_actions(harvested, 0)
    result = resolve_agent_card_effect(state)
    kinds = [e.kind for e in result.events if e.kind.startswith("agent_card_effect")]
    assert kinds == ["agent_card_effect_unavailable"]
    assert result.state.players[0].trashed == ()
    assert card in result.state.players[0].in_play


def test_ruthless_leadership_reveal_gives_a_sword_and_commands_the_combat_icon() -> (
    None
):
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    card = _card("ruthless_leadership")
    below = _reveal(_state(_owner(hand=(card,)), PROMO_BLOODLINES))
    context = _reveal_context(below)
    assert context["persuasion"] == 1
    assert context["sword_strength"] == 1
    assert context["combat_deployment"] is False
    assert legal_reveal_deployments(below, 0) == ()
    # Command (6+): the Combat icon opens this Reveal's deployment window
    # for up to two garrison units [Bloodlines pp. 5, 12].
    commanded = _reveal(_state(_six_persuasion_hand(card), PROMO_BLOODLINES))
    context = _reveal_context(commanded)
    assert context["persuasion"] == 2 + 2 + 2 + 1
    assert context["combat_deployment"] is True
    counts = {
        (a.action_id, dict(a.arguments)["count"])
        for a in legal_reveal_deployments(commanded, 0)
    }
    assert counts == {("deploy_troops", 1), ("deploy_troops", 2)}


def test_ruthless_leadership_round_trips_and_is_dealt_in_random_games() -> None:
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.simulation import run_random_game

    codec = ActionCodec(PROMO_BLOODLINES)
    # v97 Occupation bundle, v99 Duncan recall, v100 skip + Change Allegiances.
    # v103 separate lines, v104 the 19-unit retreat range.
    # v105: Fedaykin Maneuver's Commander-share retreats reach 19 units (+28).
    # v106: trash_intrigue_for_agent_card joins one template per Intrigue
    # instance in this catalog (+67); Branching Path's corrected City icon
    # does not change its agent_turn coverage under Bloodlines (every Bene
    # Gesserit card already gets every Agent icon's placements there, for
    # Urgent Shigawire's boost).
    # v108 (2026-09-26 card-transcription audit): the Conflict reward and
    # Leader Spies' recall-first (+15, see the base catalog test), Covert
    # Operation and Unswerving Loyalty (+5), Unswerving Loyalty's and Shadout
    # Mapes' Commander moves in every Bloodlines catalog (+2, a Commander "is
    # a 'troop'" [Bloodlines p. 4]); one timing per printed band for Grasp
    # Arrakis and Tenuous Bond (-3 play_intrigue), a forced Spy move with no
    # post off the Agent's space loses the Spy (+1 lose_moved_spy, OQ-065),
    # Navigation card 10's arrow cost may be declined (+1), Coercive
    # Negotiation is mandatory (-1 decline, OQ-064).
    # decline_acquisition_spy: an acquisition-bonus Spy may pass up the
    # recall-first without a Spy in supply [Main pp. 11, 20] (+1).
    # v109 (OQ-068, 2026-09-26 user ruling): Steersman's Recall Agent icon
    # and Twisted Mentat may also recall an Into the Fray Agent from the
    # Conflict (+1); the Contract reward's twin needs the CHOAM Module too,
    # which this catalog lacks.
    assert codec.size == (
        10159 + 292 + 1 + 1 + 1 + 2 + 1 + 28 + 28 + 67 + 15 + 5 + 2 - 3 + 1 + 1 - 1
        + 1 + 1
    )
    action = DomainAction(
        action_id="trash_agent_card",
        actor=2,
        arguments=(("card_id", _card("ruthless_leadership")),),
    )
    assert codec.decode(codec.encode(action), actor=2) == action
    for config in (
        PROMO_BLOODLINES,
        RulesetConfig(
            choam_module=True, promo_cards=True, bloodlines=True, tech_module=True
        ),
    ):
        report = run_checked_game(
            config,
            game_seed=41,
            policy_seed=900_041,
            privacy_interval=10,
            soundness_interval=10,
            engine=UprisingRulesEngine(leader_ids=LEADERS),
        )
        assert report.rounds >= 1
        state = run_random_game(UprisingRulesEngine(), config, 41, 141).state
        assert state.phase is GamePhase.FINISHED
        dealt = {
            instance.split(":")[1]
            for instance in (
                *state.imperium_deck,
                *state.imperium_row,
                *state.imperium_removed,
                *(
                    card
                    for player in state.players
                    for card in (
                        *player.hand,
                        *player.deck,
                        *player.discard_pile,
                        *player.in_play,
                        *player.trashed,
                    )
                ),
            )
        }
        assert "ruthless_leadership" in dealt


# --- Bloodlines Conflict cards ------------------------------------------------


def test_storms_in_the_south_first_place_spy_has_deep_cover() -> None:
    # The first-place reward prints a gold Spy behind a grey one (the Spy
    # with Deep Cover of Deliver Supplies) and 2 spice [Storms in the South
    # card]. Deep Cover places a Spy by the normal rules but may "ignore any
    # opponents' Spies"; a post holding the owner's own Spy stays closed
    # [Bloodlines pp. 5, 12] (docs/rules/bloodlines.md §4).
    rival_post = "emperor-sardaukar-dutiful-service"
    own_post = "choam-shipping-accept-contract"
    players = (
        PlayerState(
            player_id=0, combat_strength=8, spies_supply=2, spy_post_ids=(own_post,)
        ),
        PlayerState(
            player_id=1, combat_strength=6, spies_supply=2, spy_post_ids=(rival_post,)
        ),
        PlayerState(player_id=2, combat_strength=4),
        PlayerState(player_id=3),
    )
    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=3,
        first_player=0,
        players=players,
        current_conflict_ids=("storms_in_the_south",),
        combat_intrigue_complete=True,
        intrigue_deck=intrigue_deck_instance_ids(False)[:4],
    )
    rewarded = resolve_combat_rewards(state).state
    assert rewarded.players[0].resources.spice == 2
    frame = rewarded.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_REWARD_SPY
    assert dict(frame.context)["deep_cover"] is True
    posts = {
        dict(a.arguments)["post_id"]: a
        for a in legal_combat_reward_spy_actions(rewarded, 0)
    }
    assert rival_post in posts
    assert own_post not in posts
    assert len(posts) == 12
    placed = apply_combat_reward_spy(rewarded, posts[rival_post]).state
    assert placed.players[0].spy_post_ids == (own_post, rival_post)
    assert placed.players[1].spy_post_ids == (rival_post,)


def test_storms_in_the_south_deep_cover_spy_may_recall_first_without_supply() -> None:
    # The Deep Cover Spy is still a Spy icon [Storms in the South card]: "If
    # you have no Spies in your supply, you may first recall one of your
    # Spies for no effect" [Main pp. 11, 20], optional (docs/rules/
    # uprising-systems.md, OQ-057 (14)). With all three Spies on the board
    # the reward used to open no frame and the Spy was lost.
    from dune_imperium.rules.combat import combat_reward_spy_is_unavailable

    rival_post = "emperor-sardaukar-dutiful-service"
    own_posts = (
        "choam-shipping-accept-contract",
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
    )
    players = (
        PlayerState(
            player_id=0, combat_strength=8, spies_supply=0, spy_post_ids=own_posts
        ),
        PlayerState(
            player_id=1, combat_strength=6, spies_supply=2, spy_post_ids=(rival_post,)
        ),
        PlayerState(player_id=2, combat_strength=4),
        PlayerState(player_id=3),
    )
    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=3,
        first_player=0,
        players=players,
        current_conflict_ids=("storms_in_the_south",),
        combat_intrigue_complete=True,
        intrigue_deck=intrigue_deck_instance_ids(False)[:4],
    )
    rewarded = resolve_combat_rewards(state).state
    frame = rewarded.decision_stack[-1]
    assert frame.kind == FrameKind.COMBAT_REWARD_SPY
    assert dict(frame.context)["deep_cover"] is True
    assert not combat_reward_spy_is_unavailable(rewarded)
    actions = legal_combat_reward_spy_actions(rewarded, 0)
    assert [action.action_id for action in actions] == [
        "decline_combat_reward_spy",
        *("recall_spy_for_combat_reward",) * 3,
    ]

    recalled = apply_combat_reward_spy(rewarded, actions[1]).state
    targets = {
        dict(action.arguments)["post_id"]
        for action in legal_combat_reward_spy_actions(recalled, 0)
    }
    # Deep Cover [Bloodlines pp. 5, 12]: the rival's post and the one just
    # left are open, the owner's other posts are not.
    assert {rival_post, own_posts[0]} <= targets
    assert not targets & set(own_posts[1:])
    placed = apply_combat_reward_spy(
        recalled,
        DomainAction(
            action_id="place_combat_reward_spy",
            actor=0,
            arguments=(("post_id", rival_post),),
        ),
    ).state
    assert placed.players[0].spy_post_ids == (*own_posts[1:], rival_post)
    assert placed.players[1].spy_post_ids == (rival_post,)
