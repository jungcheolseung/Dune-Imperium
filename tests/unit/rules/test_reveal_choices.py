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

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.content.uprising.types import (
    MANDATORY_REVEAL_CHOICES,
    OPTIONAL_REVEAL_CHOICES,
    PersonalCardRevealChoiceEffect,
)
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
from dune_imperium.rules.engine import ACTION_HANDLERS, UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_turn import (
    REVEAL_CHOICE_ACTION_IDS,
    REVEAL_CHOICE_EFFECT_ACTIONS,
    SOURCE_ARGUMENT,
    SOURCED_REVEAL_ACTION_IDS,
    _build_reveal_choice_frame,
    pending_reveal_choices,
    reveal_choice_providers,
    reveal_late_arrivals,
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
    return ENGINE.legal_actions(state, 0)


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


def test_every_reveal_choice_is_optional_or_mandatory_with_a_reason() -> None:
    optional = set(OPTIONAL_REVEAL_CHOICES)
    mandatory = set(MANDATORY_REVEAL_CHOICES)
    assert not optional & mandatory
    assert optional | mandatory == set(PersonalCardRevealChoiceEffect)
    assert len(optional) == 16
    assert len(mandatory) == 10
    assert set(REVEAL_CHOICE_EFFECT_ACTIONS) == set(PersonalCardRevealChoiceEffect)
    assert all(
        reason.strip()
        for reason in (
            *OPTIONAL_REVEAL_CHOICES.values(),
            *MANDATORY_REVEAL_CHOICES.values(),
        )
    )
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
    } == mandatory


def test_removed_reveal_actions_have_no_handler() -> None:
    # Codec v147 keeps their catalog rows as never-legal ones.
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

# Action ids two different cards produce with the same outcome, so they carry
# no ``source``: either card's entry resolves the action the same way.
INTERCHANGEABLE: dict[str, str] = {
    "gain_reveal_influence": (
        "Pointing the Way's Command and Ixian Ambassador both gain one Influence "
        "of the owner's choice, both mandatory"
    ),
    "deploy_reveal_card_troop": (
        "Unswerving Loyalty's Fremen Bond line is Shadout Mapes' troop move"
    ),
    "retreat_reveal_card_troop": (
        "Unswerving Loyalty's Fremen Bond line is Shadout Mapes' troop move"
    ),
    "decline_reveal_spy_recall": (
        "only a plain Spy icon (Public Spectacle, Wheels within Wheels, Covert "
        "Operation, Intelligence Training) passes up its empty-supply "
        "recall-first; each leaves the same Spy icons behind"
    ),
}


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
                for provider in reveal_choice_providers():
                    for action in provider(state, 0):
                        produced.setdefault(action.action_id, {}).setdefault(
                            entry.card.card_id, []
                        ).append(action)
                        assert action.action_id in REVEAL_CHOICE_EFFECT_ACTIONS[
                            effect
                        ], (entry.card.card_id, action)
    return produced


def test_an_id_two_cards_produce_names_its_card_unless_interchangeable() -> None:
    # With every pending choice offered at once, an id that different cards
    # produce with different outcomes must say which card's choice it takes
    # (``source``, the card's definition id), or the engine could resolve it
    # on the wrong card. Every such action carries it.
    produced = _produced_by_card()
    assert set(produced) == REVEAL_CHOICE_ACTION_IDS
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
        if len(by_card) > 1:
            assert action_id in INTERCHANGEABLE, (action_id, sorted(by_card))
    assert {
        action_id
        for action_id in SOURCED_REVEAL_ACTION_IDS
        if len(produced[action_id]) > 1
    } == SOURCED_REVEAL_ACTION_IDS


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
    paid = ENGINE.apply(revealed, pays[0]).state
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
    placed = ENGINE.apply(revealed, place).state
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
    chosen = ENGINE.apply(
        revealed, DomainAction(action_id="decline_reveal_sandworm", actor=0)
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

    chosen = ENGINE.apply(
        revealed, DomainAction(action_id="decline_reveal_sandworm", actor=0)
    ).state
    ids = _ids(chosen)
    assert "gain_reveal_influence" in ids
    # Pointing the Way's gain is mandatory once it can be taken.
    assert "finish_reveal" not in ids
    gained = ENGINE.apply(chosen, _first(chosen, "gain_reveal_influence")).state
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
    recalled = ENGINE.apply(revealed, by_observer).state
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
    retreated = ENGINE.apply(revealed, by_center).state
    # Command Center's two Persuasion, not Chani's four swords.
    context = dict(retreated.decision_stack[-1].context)
    assert context["persuasion"] == persuasion + 2
    assert context["optional_sword_strength"] == 0
    assert _pending(retreated) == (
        (chani, "may_retreat_two_troops_for_four_strength"),
    )


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
    committed = ENGINE.apply(revealed, recall).state
    top = committed.decision_stack[-1]
    assert top.kind == FrameKind.REVEAL_CHOICE
    legal = _legal(committed)
    assert legal
    assert {a.action_id for a in legal} == {"place_reveal_spy"}
    assert {dict(a.arguments)[SOURCE_ARGUMENT] for a in legal} == {
        "wheels_within_wheels"
    }

    passed = ENGINE.apply(
        revealed, DomainAction(action_id="decline_reveal_spy_recall", actor=0)
    )
    assert passed.state.decision_stack[-1].kind == FrameKind.REVEAL
    assert [e.kind for e in passed.events] == ["reveal_spy_recall_declined"]
    assert "finish_reveal" in _ids(passed.state)


def test_covert_operations_second_spy_is_a_pending_row_again() -> None:
    covert = _card("covert_operation")
    revealed = _reveal(_state(PlayerState(player_id=0, hand=(covert,))))
    first = _first(revealed, "place_reveal_spy", post_id=POSTS[0])
    placed = ENGINE.apply(revealed, first).state
    assert placed.decision_stack[-1].kind == FrameKind.REVEAL
    assert _pending(placed) == ((covert, "place_spy"),)
    assert "finish_reveal" not in _ids(placed)
    second = _first(placed, "place_reveal_spy", post_id=POSTS[1])
    assert dict(second.arguments)[SOURCE_ARGUMENT] == "covert_operation"
    done = ENGINE.apply(placed, second).state
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
    acquired = ENGINE.apply(revealed, acquire).state
    assert acquired.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY
    assert {a.action_id for a in _legal(acquired)} == {"place_acquisition_spy"}
    assert miracle not in acquired.players[0].in_play
