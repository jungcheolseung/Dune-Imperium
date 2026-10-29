"""Reveal choices as rows of the Reveal frame (codec v147).

"Reveal 효과는 원하는 순서로 처리한다. Persuasion을 사용한 acquire는 Reveal
효과의 전, 사이, 뒤 어느 때든 할 수 있다. [Main p. 12]"
(docs/rules/player-turns.md, Reveal turn 4). User ruling 2026-10-14 ("그래 그
구조로 진행하자", OQ-095 (7) addition): every choice effect of a revealed card
waits on the Reveal frame and is offered there beside the purchases, gains and
Plots; an optional effect ("may", an arrow cost or a black trash icon
[FAQ p. 3]) offers no refusal and lapses at ``finish_reveal``; a mandatory one
holds the end while it offers something.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.uprising.abilities import AbilityMark
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
from dune_imperium.content.uprising.reveal_choice_abilities import (
    REVEAL_CHOICE_ABILITIES,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.content.uprising.types import (
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    IllegalActionError,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.display.effect_dsl_text import cost_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import cost_text_ko, reward_text_ko
from dune_imperium.display.tokens import REVEAL_CHOICE_EFFECT_TEXT
from dune_imperium.display.tokens_ko import REVEAL_CHOICE_EFFECT_TEXT_KO
from dune_imperium.rules.engine import ACTION_HANDLERS, UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_turn import (
    REVEAL_CHOICE_ACTION_IDS,
    REVEAL_CHOICE_EFFECT_ACTIONS,
    REVEAL_CHOICE_HOOKS,
    SOURCE_ARGUMENT,
    SOURCED_REVEAL_ACTION_IDS,
    _build_reveal_choice_frame,
    pending_reveal_choices,
    reveal_choice_providers,
    reveal_late_arrivals,
    target_reward_choice,
)

ENGINE = UprisingRulesEngine()
# The engine-driven tests play Bloodlines with CHOAM; the provider probe reads
# every card with all options on.
CONFIG = RulesetConfig(bloodlines=True, choam_module=True)
ALL_OPTIONS = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
)
STARTERS = starting_deck_instance_ids(0)
POSTS = tuple(post.post_id for post in OBSERVATION_POSTS)
_Choice = PersonalCardRevealChoiceEffect


def _card(card_id: str, copy: int = 0) -> str:
    return f"imperium:{card_id}:{copy}"


def _starter(card_id: str, copy: int = 0) -> str:
    return tuple(i for i in STARTERS if f":{card_id}:" in i)[copy]


def _state(owner: PlayerState, config: RulesetConfig = CONFIG) -> GameState:
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _reveal(state: GameState) -> GameState:
    return ENGINE.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state


def _legal(state: GameState) -> tuple[DomainAction, ...]:
    return ENGINE.whole_actions(state, 0)


def _ids(state: GameState) -> set[str]:
    return {action.action_id for action in _legal(state)}


def _pending(state: GameState) -> tuple[tuple[str, str], ...]:
    frame = next(f for f in state.decision_stack if f.kind == FrameKind.REVEAL)
    return pending_reveal_choices(dict(frame.context))


def _first(state: GameState, action_id: str, **arguments: object) -> DomainAction:
    return next(
        action
        for action in _legal(state)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )


FINISH = DomainAction(action_id="finish_reveal", actor=0)


# --- data ------------------------------------------------------------------


def test_every_reveal_choice_is_optional_or_mandatory() -> None:
    """Every Reveal choice has its record, marked optional or mandatory
    (composed effects, A4d)."""

    assert set(REVEAL_CHOICE_ABILITIES) == set(PersonalCardRevealChoiceEffect)
    optional = {
        effect
        for effect, ability in REVEAL_CHOICE_ABILITIES.items()
        if ability.mark is AbilityMark.OPTIONAL
    }
    mandatory = {
        effect
        for effect, ability in REVEAL_CHOICE_ABILITIES.items()
        if ability.mark is AbilityMark.MANDATORY
    }
    assert optional | mandatory == set(PersonalCardRevealChoiceEffect)
    # Sixteen of the Uprising family's, Gun Thopter's deploy, Opulence's and
    # Guild Ambassador's Victory Point, Gurney Halleck's troops, and Sardaukar
    # Legion's, Scout's and Chani's counts of troops (stage P3), and the promo
    # Duncan, Loyal Blade's trash for a count of troops; Rise of Ix's Guild
    # Chief Administrator's Freighter icon ("may" [Rise of Ix p. 5]),
    # Negotiated Withdrawal's arrow and Ixian Engineer's trash for a Victory
    # Point (stage P4d).
    assert len(optional) == 16 + 8 + 3
    # Ten of the Uprising family's, Bene Gesserit Sister's -OR- (stage P3) and
    # Rise of Ix's Web of Power's wild Influence icon (stage P4d).
    assert len(mandatory) == 10 + 1 + 1
    assert set(REVEAL_CHOICE_EFFECT_ACTIONS) == set(PersonalCardRevealChoiceEffect)
    # A printed "-OR-" choice and a gain are mandatory; the Spy icons too
    # (OQ-057 (14)); "may" and arrows are optional [FAQ p. 3].
    assert {
        _Choice.PLACE_SPY,
        _Choice.PLACE_TWO_SPIES,
        _Choice.COMMAND_PLACE_SPY,
        _Choice.PLACE_SPY_OR_GAIN_TWO_STRENGTH,
        _Choice.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL,
        _Choice.MAY_PAY_WATER_FOR_SANDWORM,
        _Choice.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS,
        _Choice.PERSUASION_OR_CONTRACT,
        _Choice.COMMAND_GAIN_CHOSEN_INFLUENCE,
        _Choice.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH,
        # The original game's (stage P3): Bene Gesserit Sister.
        _Choice.CHOOSE_TWO_PERSUASION_OR_TWO_STRENGTH,
        # Rise of Ix's (stage P4d): Web of Power's wild Influence icon.
        _Choice.GAIN_CHOSEN_INFLUENCE,
    } == mandatory


def test_removed_reveal_actions_have_no_handler() -> None:
    # Codec v147 kept their catalog rows as never-legal ones; stage B3d-3
    # dropped the eight refusals no handler answered from the catalog.
    for action_id in (
        "defer_reveal_choice",
        "resume_reveal_choice",
        "decline_reveal_card_trash",
        "decline_reveal_influence_exchange",
        "decline_reveal_influence_loss",
        "decline_reveal_spice_influence",
        "decline_reveal_troop_move",
        "decline_reveal_troop_retreat",
        "decline_reveal_troop_sacrifice",
        "decline_command_acquisition",
    ):
        assert action_id not in ACTION_HANDLERS
    # The empty-supply recall-first keeps its refusal (OQ-057 (14)).
    assert "decline_reveal_spy_recall" in ACTION_HANDLERS


# --- which card's effect -----------------------------------------------------

def _probe_owners() -> tuple[PlayerState, ...]:
    """Owners that open every branch of every Reveal choice."""

    rich = PlayerState(
        player_id=0,
        resources=Resources(solari=9, spice=9, water=3),
        influence=Influence(emperor=2, spacing_guild=2, bene_gesserit=2, fremen=2),
        alliance_faction_ids=("bene_gesserit",),
        victory_points=5,
        troops_supply=6,
        troops_garrison=3,
        troops_conflict=3,
        commanders_garrison=1,
        commanders_conflict=2,
        maker_hooks=True,
        tech_ids=("tech:a", "tech:b"),
        completed_contract_ids=("c1", "c2", "c3", "c4"),
        discard_pile=(_starter("dagger"),),
        spies_supply=1,
        spy_post_ids=POSTS[:2],
    )
    return (rich, replace(rich, spies_supply=0, spy_post_ids=POSTS[:3]))


def _produced_by_card() -> dict[str, dict[str, list[DomainAction]]]:
    """Every action each card's Reveal choice can offer, by id and card."""

    produced: dict[str, dict[str, list[DomainAction]]] = {}
    for entry in IMPERIUM_CARDS:
        for effect in entry.reveal_choice_effects:
            card_id = _card(entry.card.card_id)
            for owner in _probe_owners():
                owner = replace(
                    owner, in_play=(card_id, _card("public_spectacle", 1))
                )
                state = replace(
                    _state(owner, ALL_OPTIONS),
                    current_conflict_ids=("propaganda",),
                    imperium_row=(_card("strike_fleet"),),
                    # Spy Network's recall needs an Intrigue card to draw
                    # (OQ-071; engine audit 2026-10-22, P8).
                    intrigue_deck=("intrigue:test:0",),
                )
                reveal_frame = DecisionFrame(
                    kind=FrameKind.REVEAL,
                    frame_id="round:1:player:0:reveal",
                    decision=PlayerDecision(owner=0, prompt="Reveal"),
                    context=(
                        ("persuasion", 9),
                        ("persuasion_generated", 9),
                        ("revealed_card_count", 0),
                        ("strength", 0),
                        ("turn_owner", 0),
                    ),
                )
                state = replace(
                    state,
                    decision_stack=(
                        reveal_frame,
                        _build_reveal_choice_frame(1, 0, card_id, effect),
                    ),
                )
                offered = [
                    action
                    for provider in reveal_choice_providers()
                    for action in provider(state, 0)
                ]
                # Each row comes from one provider: a pending entry lists
                # what its frame offers, so a row two providers gave would
                # show twice there (composed A4d).
                assert len(offered) == len(set(offered)), entry.card.card_id
                for action in offered:
                    produced.setdefault(action.action_id, {}).setdefault(
                        entry.card.card_id, []
                    ).append(action)
                    assert action.action_id in REVEAL_CHOICE_EFFECT_ACTIONS[
                        effect
                    ], (entry.card.card_id, action)
    return produced


def test_an_id_two_cards_produce_always_names_its_card() -> None:
    # With every pending choice offered at once, an id that different cards
    # produce must say which card's choice it takes (``source``, the card's
    # definition id): the engine uses up that card's entry and its events
    # name that card. Even where both cards' outcomes match (Pointing the
    # Way's and Ixian Ambassador's Influence), the entry left behind differs
    # (Unswerving Loyalty's troop move needs a Fremen Bond, Covert
    # Operation's pass leaves its second icon), so no id two cards produce is
    # left without it.
    produced = _produced_by_card()
    # Bene Gesserit Sister's -OR- rows, Opulence's payment and the counted troop
    # moves of Sardaukar Legion, Scout and Chani (the original game, stage P3)
    # belong to no card of the Uprising deck read here; their tests are in
    # ``test_imperium_cards.py``.
    original_only = {
        "gain_two_reveal_persuasion",
        "gain_two_reveal_swords",
        "pay_reveal_solari_for_vp",
        "pay_reveal_spice_for_vp",
        "pay_reveal_solari_for_troops",
        "deploy_reveal_card_troops",
        "retreat_reveal_card_troops",
        # Rise of Ix's Guild Chief Administrator and Freighter Fleet (their
        # Freighter icon), on the original game (P4d).
        "advance_reveal_freighter",
        "recall_reveal_freighter",
        "retreat_reveal_units_for_influence",
    }
    assert set(produced) == REVEAL_CHOICE_ACTION_IDS - original_only
    for action_id, by_card in produced.items():
        actions = [action for found in by_card.values() for action in found]
        sourced = [
            action for action in actions if SOURCE_ARGUMENT in dict(action.arguments)
        ]
        if action_id in SOURCED_REVEAL_ACTION_IDS:
            assert sourced == actions, action_id
            for card, found in by_card.items():
                assert {dict(a.arguments)[SOURCE_ARGUMENT] for a in found} == {card}
            continue
        assert not sourced, action_id
        assert len(by_card) == 1, (action_id, sorted(by_card))
    assert {
        action_id
        for action_id in SOURCED_REVEAL_ACTION_IDS - original_only
        if len(produced[action_id]) > 1
    } == SOURCED_REVEAL_ACTION_IDS - original_only


# --- the Reveal frame offers the choices -------------------------------------


def test_choices_are_rows_of_the_reveal_frame_beside_a_purchase() -> None:
    favor = _card("spacing_guild_s_favor")
    owner = PlayerState(player_id=0, hand=(favor,), resources=Resources(spice=3))
    state = replace(_state(owner), reserve_stacks=(("prepare_the_way", 7),))
    revealed = _reveal(state)

    assert revealed.decision_stack[-1].kind == FrameKind.REVEAL
    assert _pending(revealed) == ((favor, "may_pay_three_spice_for_influence"),)
    ids = _ids(revealed)
    assert "pay_reveal_spice_influence" in ids
    assert "acquire_reserve" in ids
    assert "defer_reveal_choice" not in ids
    assert "resume_reveal_choice" not in ids


def test_an_optional_choice_offers_no_refusal_and_lapses_at_the_end() -> None:
    favor = _card("spacing_guild_s_favor")
    revealed = _reveal(
        _state(PlayerState(player_id=0, hand=(favor,), resources=Resources(spice=3)))
    )
    ids = _ids(revealed)
    assert "pay_reveal_spice_influence" in ids
    assert "decline_reveal_spice_influence" not in ids
    assert "finish_reveal" in ids

    finished = ENGINE.apply(revealed, FINISH)
    lapsed = [e for e in finished.events if e.kind == "reveal_choice_lapsed"]
    assert [dict(e.payload) for e in lapsed] == [
        {
            "card_id": favor,
            "effect": "may_pay_three_spice_for_influence",
            "player": 0,
        }
    ]
    assert finished.state.players[0].resources.spice == 3


def test_two_copies_offer_their_rows_once_and_resolve_in_pending_order() -> None:
    first = _card("spacing_guild_s_favor")
    second = _card("spacing_guild_s_favor", 1)
    revealed = _reveal(
        _state(
            PlayerState(
                player_id=0, hand=(first, second), resources=Resources(spice=6)
            )
        )
    )
    pays = [a for a in _legal(revealed) if a.action_id == "pay_reveal_spice_influence"]
    assert len(pays) == len(set(pays)) == 4
    paid = apply_whole(ENGINE, revealed, pays[0]).state
    assert paid.decision_stack[-1].kind == FrameKind.REVEAL
    assert _pending(paid) == ((second, "may_pay_three_spice_for_influence"),)


def test_a_plain_spy_with_a_spy_in_supply_holds_the_end_until_placed() -> None:
    spectacle = _card("public_spectacle")
    revealed = _reveal(_state(PlayerState(player_id=0, hand=(spectacle,))))
    ids = _ids(revealed)
    assert "place_reveal_spy" in ids
    assert "finish_reveal" not in ids
    place = _first(revealed, "place_reveal_spy", post_id=POSTS[0])
    assert dict(place.arguments)[SOURCE_ARGUMENT] == "public_spectacle"
    placed = apply_whole(ENGINE, revealed, place).state
    assert placed.players[0].spy_post_ids == (POSTS[0],)
    assert _pending(placed) == ()
    assert "finish_reveal" in _ids(placed)


def test_desert_power_holds_the_end_until_a_branch_is_chosen() -> None:
    # OQ-069: "고르기 전에는 Reveal을 끝낼 수 없다"; the Persuasion branch is
    # ``decline_reveal_sandworm``.
    desert_power = _card("desert_power")
    revealed = _reveal(_state(PlayerState(player_id=0, hand=(desert_power,))))
    ids = _ids(revealed)
    assert "decline_reveal_sandworm" in ids
    assert "finish_reveal" not in ids
    chosen = apply_whole(
        ENGINE, revealed, DomainAction(action_id="decline_reveal_sandworm", actor=0)
    ).state
    assert dict(chosen.decision_stack[-1].context)["persuasion"] == 2
    assert "finish_reveal" in _ids(chosen)


def test_a_command_choice_opens_once_six_persuasion_is_generated() -> None:
    # "Command (6+)" is judged on the Persuasion the Reveal turn generates
    # [Bloodlines pp. 5, 12]; Desert Power's 2 count only once its
    # Persuasion branch is chosen (OQ-069).
    desert_power = _card("desert_power")
    pointing = _card("pointing_the_way")
    argument = _starter("convincing_argument")
    argument2 = _starter("convincing_argument", 1)
    owner = PlayerState(
        player_id=0, hand=(desert_power, pointing, argument, argument2)
    )
    revealed = _reveal(_state(owner))
    assert dict(revealed.decision_stack[-1].context)["persuasion_generated"] == 5
    ids = _ids(revealed)
    assert "gain_reveal_influence" not in ids
    assert "finish_reveal" not in ids

    chosen = apply_whole(
        ENGINE, revealed, DomainAction(action_id="decline_reveal_sandworm", actor=0)
    ).state
    ids = _ids(chosen)
    assert "gain_reveal_influence" in ids
    # Pointing the Way's gain is mandatory once it can be taken.
    assert "finish_reveal" not in ids
    gained = apply_whole(ENGINE, chosen, _first(chosen, "gain_reveal_influence")).state
    assert gained.players[0].influence.emperor == 1
    assert "finish_reveal" in _ids(gained)


def test_a_command_choice_never_reached_lapses_at_the_end() -> None:
    pointing = _card("pointing_the_way")
    revealed = _reveal(_state(PlayerState(player_id=0, hand=(pointing,))))
    assert "finish_reveal" in _ids(revealed)
    finished = ENGINE.apply(revealed, FINISH)
    assert [e.kind for e in finished.events][0] == "reveal_choice_lapsed"


# --- source ------------------------------------------------------------------


def test_source_tells_spy_network_from_arrakis_observer() -> None:
    network = _card("spy_network")
    observer = _card("arrakis_observer")
    owner = PlayerState(
        player_id=0, hand=(network, observer), spies_supply=1, spy_post_ids=POSTS[:2]
    )
    revealed = _reveal(replace(_state(owner), intrigue_deck=("intrigue:test:0",)))
    recalls = [a for a in _legal(revealed) if a.action_id == "recall_spy_for_reveal"]
    assert {dict(a.arguments)[SOURCE_ARGUMENT] for a in recalls} == {
        "spy_network",
        "arrakis_observer",
    }
    by_observer = _first(
        revealed, "recall_spy_for_reveal", post_id=POSTS[0], source="arrakis_observer"
    )
    recalled = apply_whole(ENGINE, revealed, by_observer).state
    # Arrakis Observer's three swords, not Spy Network's Intrigue card.
    assert recalled.players[0].intrigue_cards == ()
    reveal_context = dict(recalled.decision_stack[-1].context)
    assert reveal_context["optional_sword_strength"] == 3
    assert _pending(recalled) == (
        (network, "recall_spy_to_draw_intrigue_if_two_placed"),
    )


def test_source_tells_chani_from_command_center() -> None:
    chani = _card("chani_clever_tactician")
    center = _card("command_center")
    owner = PlayerState(
        player_id=0,
        hand=(chani, center),
        troops_conflict=4,
        troops_supply=5,
        combat_strength=8,
    )
    revealed = _reveal(_state(owner))
    retreats = {
        dict(a.arguments)[SOURCE_ARGUMENT]
        for a in _legal(revealed)
        if a.action_id == "retreat_two_troops_for_reveal"
    }
    assert retreats == {"chani_clever_tactician", "command_center"}
    persuasion = dict(revealed.decision_stack[-1].context)["persuasion"]
    assert isinstance(persuasion, int)
    by_center = _first(
        revealed, "retreat_two_troops_for_reveal", source="command_center"
    )
    retreated = apply_whole(ENGINE, revealed, by_center).state
    # Command Center's two Persuasion, not Chani's four swords.
    context = dict(retreated.decision_stack[-1].context)
    assert context["persuasion"] == persuasion + 2
    assert context["optional_sword_strength"] == 0
    assert _pending(retreated) == (
        (chani, "may_retreat_two_troops_for_four_strength"),
    )


def test_source_tells_pointing_the_way_from_ixian_ambassador() -> None:
    # Both gain one Influence of the owner's choice, both mandatory; the row
    # says whose gain it is, that entry is used up and its event names it.
    pointing = _card("pointing_the_way")
    ambassador = _card("ixian_ambassador")
    owner = PlayerState(
        player_id=0,
        hand=(
            pointing,
            ambassador,
            _starter("convincing_argument"),
            _starter("convincing_argument", 1),
        ),
        tech_ids=("glowglobes", "training_depot"),
    )
    revealed = _reveal(_state(owner, replace(CONFIG, tech_module=True)))
    gains = [a for a in _legal(revealed) if a.action_id == "gain_reveal_influence"]
    assert len(gains) == 8
    assert {dict(a.arguments)[SOURCE_ARGUMENT] for a in gains} == {
        "pointing_the_way",
        "ixian_ambassador",
    }
    by_ambassador = _first(
        revealed, "gain_reveal_influence", faction="fremen", source="ixian_ambassador"
    )
    gained = apply_whole(ENGINE, revealed, by_ambassador)
    assert gained.state.players[0].influence.fremen == 1
    # (the seat-only effect_picked events of the pick steps are not compared)
    assert all(
        ambassador in event.event_id
        for event in gained.events
        if event.kind != "effect_picked"
    )
    assert _pending(gained.state) == ((pointing, "command_gain_chosen_influence"),)
    assert {
        dict(a.arguments)[SOURCE_ARGUMENT]
        for a in _legal(gained.state)
        if a.action_id == "gain_reveal_influence"
    } == {"pointing_the_way"}


def test_source_tells_shadout_mapes_from_unswerving_loyalty() -> None:
    # Unswerving Loyalty's Fremen Bond line is Shadout Mapes' troop move, but
    # only one of the two entries is used up by a move.
    mapes = _card("shadout_mapes")
    loyalty = _card("unswerving_loyalty")
    owner = PlayerState(
        player_id=0, hand=(mapes, loyalty), troops_garrison=2, troops_conflict=1
    )
    revealed = _reveal(_state(owner))
    moves = {
        (a.action_id, dict(a.arguments)[SOURCE_ARGUMENT])
        for a in _legal(revealed)
        if a.action_id in ("deploy_reveal_card_troop", "retreat_reveal_card_troop")
    }
    assert moves == {
        (action_id, source)
        for action_id in ("deploy_reveal_card_troop", "retreat_reveal_card_troop")
        for source in ("shadout_mapes", "unswerving_loyalty")
    }
    by_loyalty = _first(
        revealed, "deploy_reveal_card_troop", source="unswerving_loyalty"
    )
    moved = apply_whole(ENGINE, revealed, by_loyalty).state
    assert moved.players[0].troops_conflict == 2
    assert _pending(moved) == ((mapes, "may_deploy_or_retreat_one_troop"),)


def test_source_tells_which_plain_spy_icon_passes_its_recall() -> None:
    # With an empty supply each plain Spy icon may pass up its recall-first
    # (OQ-057 (14)); passing Covert Operation's first icon leaves its second,
    # passing Public Spectacle's leaves Covert Operation's two.
    spectacle = _card("public_spectacle")
    covert = _card("covert_operation")
    owner = PlayerState(
        player_id=0, hand=(spectacle, covert), spies_supply=0, spy_post_ids=POSTS[:3]
    )
    revealed = _reveal(_state(owner))
    declines = [
        a for a in _legal(revealed) if a.action_id == "decline_reveal_spy_recall"
    ]
    assert {dict(a.arguments)[SOURCE_ARGUMENT] for a in declines} == {
        "public_spectacle",
        "covert_operation",
    }
    by_covert = _first(
        revealed, "decline_reveal_spy_recall", source="covert_operation"
    )
    passed = apply_whole(ENGINE, revealed, by_covert)
    assert all(covert in event.event_id for event in passed.events)
    assert _pending(passed.state) == (
        (spectacle, "place_spy"),
        (covert, "place_spy"),
    )


# --- a card another effect trashed -------------------------------------------
#
# "you can't receive or activate an effect from a card that is already
# trashed" (designer ruling, OQ-022), applied to the Reveal's freely ordered
# choices (its 2026-09-07 addition); "늦게 성립한 Reveal 효과는 그 출처 카드가
# 아직 in play일 때만 지급한다 — trash된 카드의 효과는 받지 못한다(OQ-022)"
# (OQ-028 re-ruling 2026-10-04). A pending choice whose card another effect
# trashed offers nothing, does not hold the end and lapses there.


def test_corrinth_city_trashed_by_calculus_of_power_offers_nothing() -> None:
    calculus = _card("calculus_of_power")
    corrinth = _card("corrinth_city")
    owner = PlayerState(
        player_id=0,
        hand=(calculus, corrinth),
        resources=Resources(solari=9),
        troops_supply=8,
        troops_conflict=1,
    )
    revealed = _reveal(_state(owner))
    assert "finish_reveal" not in _ids(revealed)
    trash = _first(
        revealed, "trash_reveal_card", card_id=corrinth, source="calculus_of_power"
    )
    trashed = apply_whole(ENGINE, revealed, trash).state
    assert corrinth not in trashed.players[0].in_play
    assert _pending(trashed) == ((corrinth, "gain_five_solari_or_take_high_council"),)
    ids = _ids(trashed)
    # Corrinth City's mandatory "-OR-" no longer holds the end (OQ-022).
    assert "gain_five_reveal_solari" not in ids
    assert "take_high_council_from_reveal" not in ids
    assert "finish_reveal" in ids
    with pytest.raises(IllegalActionError):
        apply_whole(
            ENGINE,
            trashed,
            DomainAction(action_id="gain_five_reveal_solari", actor=0),
        )
    finished = ENGINE.apply(trashed, FINISH)
    assert [
        dict(e.payload)["card_id"]
        for e in finished.events
        if e.kind == "reveal_choice_lapsed"
    ] == [corrinth]
    assert finished.state.players[0].resources.solari == 9


def test_pointing_the_way_trashed_by_shrouded_counsel_no_longer_holds_the_end() -> (
    None
):
    pointing = _card("pointing_the_way")
    counsel = _card("shrouded_counsel")
    owner = PlayerState(
        player_id=0,
        hand=(
            pointing,
            counsel,
            _starter("convincing_argument"),
            _starter("convincing_argument", 1),
        ),
    )
    revealed = _reveal(_state(owner))
    ids = _ids(revealed)
    assert "gain_reveal_influence" in ids
    assert "finish_reveal" not in ids
    trash = _first(
        revealed, "trash_reveal_card", card_id=pointing, source="shrouded_counsel"
    )
    trashed = apply_whole(ENGINE, revealed, trash).state
    assert pointing not in trashed.players[0].in_play
    ids = _ids(trashed)
    assert "gain_reveal_influence" not in ids
    assert "finish_reveal" in ids
    finished = ENGINE.apply(trashed, FINISH)
    assert [
        (dict(e.payload)["card_id"], dict(e.payload)["effect"])
        for e in finished.events
        if e.kind == "reveal_choice_lapsed"
    ] == [(pointing, "command_gain_chosen_influence")]
    assert finished.state.players[0].influence == Influence()


def test_a_calculus_of_power_its_twin_trashed_cannot_trash_back() -> None:
    first = _card("calculus_of_power")
    second = _card("calculus_of_power", 1)
    owner = PlayerState(
        player_id=0, hand=(first, second), troops_supply=8, troops_conflict=1
    )
    revealed = _reveal(_state(owner))
    trashes = [a for a in _legal(revealed) if a.action_id == "trash_reveal_card"]
    assert {dict(a.arguments)["card_id"] for a in trashes} == {first, second}
    strength = revealed.players[0].combat_strength
    trashed = apply_whole(
        ENGINE,
        revealed,
        _first(revealed, "trash_reveal_card", card_id=second),
    ).state
    assert trashed.players[0].combat_strength == strength + 3
    # The first copy's entry is used up; the second copy's is the trashed
    # card's and offers nothing.
    assert _pending(trashed) == (
        (second, "may_trash_other_emperor_for_three_strength"),
    )
    assert "trash_reveal_card" not in _ids(trashed)
    assert first in trashed.players[0].in_play
    finished = ENGINE.apply(trashed, FINISH)
    assert [
        dict(e.payload)["card_id"]
        for e in finished.events
        if e.kind == "reveal_choice_lapsed"
    ] == [second]


# --- continuations stay modal -------------------------------------------------


def test_an_empty_supply_keeps_its_refusal_and_a_recall_commits_the_placement() -> (
    None
):
    wheels = _card("wheels_within_wheels")
    posts = POSTS[:3]
    revealed = _reveal(
        _state(
            PlayerState(
                player_id=0, hand=(wheels,), spies_supply=0, spy_post_ids=posts
            )
        )
    )
    ids = _ids(revealed)
    assert "decline_reveal_spy_recall" in ids
    assert "recall_spy_for_reveal_placement" in ids
    assert "finish_reveal" not in ids

    recall = _first(revealed, "recall_spy_for_reveal_placement", post_id=posts[0])
    committed = apply_whole(ENGINE, revealed, recall).state
    top = committed.decision_stack[-1]
    assert top.kind == FrameKind.REVEAL_CHOICE
    legal = _legal(committed)
    assert legal
    assert {a.action_id for a in legal} == {"place_reveal_spy"}
    assert {dict(a.arguments)[SOURCE_ARGUMENT] for a in legal} == {
        "wheels_within_wheels"
    }

    decline = _first(revealed, "decline_reveal_spy_recall")
    assert dict(decline.arguments)[SOURCE_ARGUMENT] == "wheels_within_wheels"
    passed = apply_whole(ENGINE, revealed, decline)
    assert passed.state.decision_stack[-1].kind == FrameKind.REVEAL
    assert [e.kind for e in passed.events] == ["reveal_spy_recall_declined"]
    assert "finish_reveal" in _ids(passed.state)


def test_covert_operations_second_spy_is_a_pending_row_again() -> None:
    covert = _card("covert_operation")
    revealed = _reveal(_state(PlayerState(player_id=0, hand=(covert,))))
    first = _first(revealed, "place_reveal_spy", post_id=POSTS[0])
    placed = apply_whole(ENGINE, revealed, first).state
    assert placed.decision_stack[-1].kind == FrameKind.REVEAL
    assert _pending(placed) == ((covert, "place_spy"),)
    assert "finish_reveal" not in _ids(placed)
    second = _first(placed, "place_reveal_spy", post_id=POSTS[1])
    assert dict(second.arguments)[SOURCE_ARGUMENT] == "covert_operation"
    done = apply_whole(ENGINE, placed, second).state
    assert done.players[0].spy_post_ids == POSTS[:2]
    assert "finish_reveal" in _ids(done)


def test_a_late_revealed_cards_choice_becomes_a_row() -> None:
    favor = _card("spacing_guild_s_favor")
    revealed = _reveal(
        _state(PlayerState(player_id=0, resources=Resources(spice=3)))
    )
    owner = revealed.players[0]
    with_hand = replace(
        revealed,
        players=(replace(owner, hand=(favor,)), *revealed.players[1:]),
    )
    arrived = reveal_late_arrivals(with_hand, 0, (favor,)).state
    assert arrived.decision_stack[-1].kind == FrameKind.REVEAL
    assert _pending(arrived) == ((favor, "may_pay_three_spice_for_influence"),)
    assert "pay_reveal_spice_influence" in _ids(arrived)


def test_an_acquisitions_spy_frame_stacks_on_top_of_its_choice() -> None:
    # Engineered Miracle's Command acquisition of a Spy-bonus card: the
    # acquisition's own Spy placement opens on top, as it must follow at once.
    miracle = _card("engineered_miracle")
    argument = _starter("convincing_argument")
    argument2 = _starter("convincing_argument", 1)
    fleet = _card("strike_fleet")
    owner = PlayerState(
        player_id=0,
        hand=(miracle, argument, argument2),
        high_council=True,
    )
    state = replace(_state(owner), imperium_row=(fleet,))
    revealed = _reveal(state)
    acquire = _first(revealed, "command_acquire_row_card", instance_id=fleet)
    assert "decline_command_acquisition" not in _ids(revealed)
    acquired = apply_whole(ENGINE, revealed, acquire).state
    assert acquired.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY
    assert {a.action_id for a in _legal(acquired)} == {"place_acquisition_spy"}
    assert miracle not in acquired.players[0].in_play


def test_reveal_choice_hooks_name_flows_kept_as_code() -> None:
    """A record's ``hook`` names one of ``reveal_turn``'s kept flows, and
    each such flow has its records (composed effects, A4d)."""

    named = {
        ability.hook
        for ability in REVEAL_CHOICE_ABILITIES.values()
        if ability.hook is not None
    }
    assert named == REVEAL_CHOICE_HOOKS


def test_the_new_reveal_choice_pieces_read_as_the_cards_print_them() -> None:
    """Calculus of Power's "another Emperor card in play" and Corrinth City's
    seat, in both languages."""

    calculus = _Choice.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH
    (trash,) = REVEAL_CHOICE_ABILITIES[calculus].sections[0].costs
    assert cost_text(trash).lower() in REVEAL_CHOICE_EFFECT_TEXT[calculus].lower()
    assert cost_text_ko(trash) in REVEAL_CHOICE_EFFECT_TEXT_KO[calculus]
    corrinth = _Choice.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL
    (seat,) = REVEAL_CHOICE_ABILITIES[corrinth].sections[1].rewards
    assert reward_text(seat) in REVEAL_CHOICE_EFFECT_TEXT[corrinth]
    assert reward_text_ko(seat) in REVEAL_CHOICE_EFFECT_TEXT_KO[corrinth]


def test_the_reveal_choices_paying_one_target_for_their_reward() -> None:
    """Composed A4d: the choices that recall a Spy, trash a card or name a
    Faction for their reward resolve by the shared "target -> reward" shape;
    the Spy icons, the printed "-OR-"s and the hooks do not."""

    assert {
        effect
        for effect, ability in REVEAL_CHOICE_ABILITIES.items()
        if target_reward_choice(ability)
    } == {
        _Choice.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED,
        _Choice.MAY_RECALL_SPY_FOR_THREE_STRENGTH,
        _Choice.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH,
        _Choice.COMMAND_MAY_TRASH_CARD,
        _Choice.MAY_TRASH_SELF_FOR_COMBAT_ICON,
        _Choice.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS,
        _Choice.COMMAND_GAIN_CHOSEN_INFLUENCE,
        _Choice.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH,
        # Rise of Ix's Web of Power (stage P4d): the wild Influence icon.
        _Choice.GAIN_CHOSEN_INFLUENCE,
        # Rise of Ix's Ixian Engineer (stage P4d): CHOAM Demands' arrow with a
        # Victory Point.
        _Choice.MAY_TRASH_SELF_FOR_VICTORY_POINT_IF_THREE_TECH_TILES,
    }
