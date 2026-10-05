"""Tests for one printed Agent-box icon's English/Korean detail text."""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.bloodlines.tech import TECH_TILES_BY_ID
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
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
from dune_imperium.display.actions import (
    _ICON_CONDITIONS,
    _ICON_CONDITIONS_KO,
    agent_card_icon_text,
    agent_card_icon_text_ko,
    effect_action_text,
    effect_action_text_ko,
)
from dune_imperium.rules.engine import UprisingRulesEngine

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/unit/display/test_struct_text.py's identical comment).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)

_KEYS = (
    "cards",
    "cards_second",
    "intrigue",
    "troops",
    "solari",
    "spice",
    "water",
    "research",
    "return_self",
    "trash_self",
    "pledge",
)

# One representative effect per _ICON_CONDITIONS row, plus None (no
# condition suffix) and a member with no row at all.
_EFFECTS = (
    None,
    PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
    PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
    PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO,
    PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO,
    PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN,
    (
        PersonalCardAgentEffect
        .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
    ),
    PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO,
    PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND,
    PersonalCardAgentEffect.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED,
    PersonalCardAgentEffect.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE,
)


def test_icon_conditions_ko_covers_the_same_pairs_as_english() -> None:
    assert set(_ICON_CONDITIONS_KO.keys()) == set(_ICON_CONDITIONS.keys())


def test_agent_card_icon_text_ko_matches_every_english_case() -> None:
    terms = terms_keys()
    for effect in _EFFECTS:
        for key in _KEYS:
            en = agent_card_icon_text(effect, key)
            ko = agent_card_icon_text_ko(effect, key)

            assert isinstance(ko, str) and ko.strip(), (effect, key)
            assert_placeholders_are_terms(ko, terms)
            assert_no_stray_latin(ko)
            assert_trash_and_discard_match(en, ko)


def test_agent_card_icon_text_ko_golden_base_cases() -> None:
    assert agent_card_icon_text_ko(None, "cards") == "{draw:1}"
    assert agent_card_icon_text_ko(None, "intrigue") == "{intrigue:1}"
    assert agent_card_icon_text_ko(None, "troops") == "{troop:1}"
    assert agent_card_icon_text_ko(None, "solari") == "{solari:2}"
    assert agent_card_icon_text_ko(None, "spice") == "{spice:1}"
    assert agent_card_icon_text_ko(None, "water") == "{water:1}"
    assert agent_card_icon_text_ko(None, "trash_self") == "이 카드 {trash}"
    assert (
        agent_card_icon_text_ko(None, "pledge")
        == "1등 보상에 {influence_any} 선택 추가"
    )


def test_agent_card_icon_text_ko_bene_gesserit_alliance_spice_is_two() -> None:
    # The only member whose "spice" base text differs by which card holds
    # it (English: "Gain 2 spice" instead of "Gain 1 spice").
    effect = (
        PersonalCardAgentEffect
        .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
    )

    assert agent_card_icon_text(effect, "spice") == "Gain 2 spice"
    assert agent_card_icon_text_ko(effect, "spice") == "{spice:2}"


def test_agent_card_icon_text_ko_appends_the_influence_condition() -> None:
    effect = PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO

    assert (
        agent_card_icon_text(effect, "troops")
        == "Recruit 1 troop (at 2 Bene Gesserit Influence)"
    )
    assert (
        agent_card_icon_text_ko(effect, "troops")
        == "{troop:1} ({influence_bene_gesserit:2}일 때)"
    )


def test_agent_card_icon_text_ko_appends_the_spice_this_turn_condition() -> None:
    effect = (
        PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN
    )

    assert (
        agent_card_icon_text(effect, "cards")
        == "Draw 1 card (if you gained 2 or more spice this turn)"
    )
    assert (
        agent_card_icon_text_ko(effect, "cards")
        == "{draw:1} (이번 차례에 {spice}를 2 이상 얻었다면)"
    )


def test_agent_card_icon_text_names_each_cargo_runner_line() -> None:
    # Two printed lines, one icon each (OQ-027): two and four contracts.
    effect = PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO

    assert agent_card_icon_text(effect, "cards") == (
        "Draw 1 card (if you have completed 2 or more contracts)"
    )
    assert agent_card_icon_text(effect, "cards_second") == (
        "Draw 1 card (if you have completed 4 or more contracts)"
    )
    assert agent_card_icon_text_ko(effect, "cards_second") == (
        "{draw:1} ({contract} 넷 이상 완수했다면)"
    )


def test_agent_card_icon_text_ko_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        agent_card_icon_text_ko(None, "not_a_real_key")


_ENGINE = UprisingRulesEngine()


def _pay_spice(
    config: RulesetConfig, card: str, space_id: str
) -> tuple[GameState, DomainAction]:
    """Seat 0 sends ``card`` to ``space_id``; return the spice payment then."""

    owner = PlayerState(player_id=0, hand=(card,), resources=Resources(spice=4))
    imperium = imperium_deck_instance_ids(False)
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=("choam_security",),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    place = next(
        action
        for action in _ENGINE.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments) == {"card_id": card, "space_id": space_id}
    )
    placed = _ENGINE.apply(state, place).state
    payment = next(
        action
        for action in _ENGINE.legal_actions(placed, 0)
        if action.action_id == "pay_agent_card_spice"
    )
    return placed, payment


def test_control_the_spice_payment_says_what_it_buys() -> None:
    # The shared pay_agent_card_spice is labelled for Smuggler's Haven's
    # "4 spice -> 1 VP"; on Control the Spice it pays 1 spice to trash a card
    # (black X, still optional [FAQ p. 3]) and recruit a troop
    # (docs/rules/epic-game-mode.md 6), and the detail replaces the label.
    placed, payment = _pay_spice(
        RulesetConfig(epic_game=True),
        "player:0:starter:control_the_spice:0",
        "accept_contract",
    )

    english = effect_action_text(placed, payment)
    korean = effect_action_text_ko(placed, payment)

    assert english == "Pay 1 spice → Trash a card (optional) + Recruit 1 troop"
    assert korean == "{spice:1} 지불 {arrow_right} 카드 {trash} (선택) + {troop:1}"
    assert_placeholders_are_terms(korean, terms_keys())
    assert_no_stray_latin(korean)
    assert_trash_and_discard_match(english, korean)


def test_smugglers_haven_payment_says_what_it_buys() -> None:
    haven = next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if ":smuggler_s_haven:" in instance_id
    )
    placed, payment = _pay_spice(RulesetConfig(), haven, "deliver_supplies")

    # The shared action's client label only says a cost is paid, so the
    # button names this card's reward too.
    assert effect_action_text(placed, payment) == "Pay 4 spice → Gain 1 VP"
    assert effect_action_text_ko(placed, payment) == (
        "{spice:4} 지불 {arrow_right} {victory_point:1}"
    )


def test_tenuous_bond_distinguishes_its_influence_cost_and_reward() -> None:
    card = "intrigue:tenuous_bond:0"
    state = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(
                player_id=0,
                intrigue_cards=(card,),
                influence=Influence(fremen=2),
            ),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    state = _ENGINE.apply(
        state, DomainAction("play_intrigue", 0, (("card_id", card), ("option", 0)))
    ).state
    loss = _ENGINE.legal_actions(state, 0)[0]
    assert loss.action_id == "choose_intrigue_faction"
    assert effect_action_text(state, loss) == "Lose 1 Influence"
    assert effect_action_text_ko(state, loss) == "{influence_lose:1} 하락"
    assert effect_action_text(state, replace(loss, actor=1)) is None

    gained = _ENGINE.apply(state, loss).state
    for gain in _ENGINE.legal_actions(gained, 0):
        # Same action id on the very next step; a global loss label would
        # fix the cost but incorrectly mark every reward as a loss.
        assert gain.action_id == loss.action_id
        assert effect_action_text(gained, gain) == "Gain 1 Influence"
        assert effect_action_text_ko(gained, gain) == "{influence_any:1} 상승"
    assert gained.players[0].influence.fremen == 1


@pytest.mark.parametrize("tech_id", sorted(TECH_TILES_BY_ID))
def test_tech_acquire_icons_have_english_and_korean_details(tech_id: str) -> None:
    from dune_imperium.rules.tech import tech_acquire_effect_arguments

    tile = TECH_TILES_BY_ID[tech_id]
    state = GameState(config=RulesetConfig(bloodlines=True, tech_module=True), seed=0)
    terms = terms_keys()
    for effect in tile.acquire_effect_keys:
        details: set[str] = set()
        for arguments in tech_acquire_effect_arguments(tile, effect):
            action = DomainAction(
                action_id="resolve_tech_acquire_effect", actor=0, arguments=arguments
            )
            en = effect_action_text(state, action)
            ko = effect_action_text_ko(state, action)
            assert en and ko, (tech_id, effect)
            assert_placeholders_are_terms(ko, terms)
            assert_no_stray_latin(ko)
            assert_trash_and_discard_match(en, ko)
            details.add(en)
        if effect in ("intrigue_or_card", "shield_wall"):
            assert len(details) == 2
