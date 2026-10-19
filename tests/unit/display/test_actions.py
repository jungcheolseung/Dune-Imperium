"""Tests for one printed Agent-box icon's English/Korean detail text."""

import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement
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
    _one_icon_per_effect_ko,
    agent_box_headers,
    agent_box_of_rows,
    agent_box_row_title,
    agent_card_icon_text,
    agent_card_icon_text_ko,
    effect_action_text,
    effect_action_text_ko,
    owed_draw_action_text,
    owed_draw_origin_text,
    research_icon_action_text,
)
from dune_imperium.display.tokens_ko import AGENT_EFFECT_TEXT_KO
from dune_imperium.rules.agent_turn import executable_placements
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
    PersonalCardAgentEffect.LEADER_SIGNET,
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
    assert agent_card_icon_text_ko(None, "trash_self") == "이 카드 폐기"
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


def test_agent_card_icon_text_names_fill_coffers_icons() -> None:
    # "FILL COFFERS — [1 Solari] —AND— If you have an Alliance: [1 spice]"
    # [Lady Amber Metulli card], the Signet Ring's two icons.
    effect = PersonalCardAgentEffect.LEADER_SIGNET

    assert agent_card_icon_text(effect, "solari") == "Gain 1 solari"
    assert agent_card_icon_text_ko(effect, "solari") == "{solari:1}"
    assert agent_card_icon_text(effect, "spice") == (
        "Gain 1 spice (if you have an Alliance)"
    )
    assert agent_card_icon_text_ko(effect, "spice") == (
        "{spice:1} ({alliance}이 있다면)"
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
        for action in executable_placements(state, 0)
        if dict(action.arguments) == {"card_id": card, "space_id": space_id}
    )
    placed = apply_placement(_ENGINE, state, place).state
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
    assert korean == "{spice:1} 지불 {arrow_right} {trash} (선택) + {troop:1}"
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


# User decision 2026-10-17, composed-effects plan 5, rule decision 5; OQ-027
# [Main p. 9]: a research space's paired icons and c7r3's rewards are each
# an independent effect the owner resolves as its own step.
_RESEARCH_ICON_TEXT = {
    "specimen": ("Gain 1 specimen", "{specimen}"),
    "tleilaxu": ("Advance on the Tleilaxu track", "{tleilaxu}"),
    "trash": ("Trash a card (optional)", "{trash} (선택)"),
    "intrigue": ("Draw 1 Intrigue card", "{intrigue:1}"),
    "cards": ("Draw 1 card", "{draw:1}"),
}


def _research_icon(effect: str, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="resolve_research_icon",
        actor=actor,
        arguments=(("effect", effect),),
    )


@pytest.mark.parametrize("effect", sorted(_RESEARCH_ICON_TEXT))
def test_research_icon_rows_say_which_icon_they_resolve(effect: str) -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9].
    english, korean = _RESEARCH_ICON_TEXT[effect]
    action = _research_icon(effect)
    assert research_icon_action_text(action) == (english, korean)
    # The same text reaches the button through the shared effect text.
    state = GameState(config=RulesetConfig(immortality=True), seed=0)
    assert effect_action_text(state, action) == english
    assert effect_action_text_ko(state, action) == korean
    assert_placeholders_are_terms(korean, terms_keys())
    assert_no_stray_latin(korean)
    assert_trash_and_discard_match(english, korean)


def test_research_icon_text_is_only_for_the_icon_rows() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]: the other research rows keep their own labels.
    assert research_icon_action_text(DomainAction("pay_research_bonus", 0)) is None
    assert research_icon_action_text(DomainAction("decline_research_bonus", 0)) is None


def test_a_c7r3_draw_names_its_research_space() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]; OQ-106: c7r3's Intrigue card and card wait as the
    # owner's draws, each naming the space that earned it.
    assert owed_draw_origin_text("research_c7r3") == (
        "Research space c7r3",
        "{research} c7r3",
    )
    state = GameState(
        config=RulesetConfig(immortality=True),
        seed=0,
        players=(
            PlayerState(
                player_id=0,
                owed_draws=(
                    ("intrigue", "research_c7r3", "test:intrigue"),
                    ("card", "research_c7r3", "test:card"),
                ),
            ),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
    )
    for action_id in ("draw_owed_intrigue", "draw_owed_card"):
        action = DomainAction(action_id=action_id, actor=0)
        assert owed_draw_action_text(state, action) == (
            "Research space c7r3",
            "{research} c7r3",
        )
        assert effect_action_text(state, action) == "Research space c7r3"
        assert effect_action_text_ko(state, action) == "{research} c7r3"
    assert_placeholders_are_terms("{research} c7r3", terms_keys())


_GHOLA = "tleilaxu:ghola:0"
_SIGNET = "player:0:starter:signet_ring:0"
_CARGO_RUNNER = "imperium:cargo_runner:0"


def _ghola_box(partner: str, **owner: object) -> GameState:
    """Seat 0 places Ghola grafted to ``partner``; Ghola's box is active."""

    config = RulesetConfig(immortality=True, choam_module=True)
    seat = PlayerState(
        player_id=0,
        hand=(partner, _GHOLA),
        resources=Resources(solari=4, spice=2, water=2),
        **owner,  # type: ignore[arg-type]
    )
    imperium = imperium_deck_instance_ids(True)
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=("choam_security",),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=(seat, *(PlayerState(player_id=other) for other in range(1, 4))),
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
        for action in executable_placements(state, 0)
        if dict(action.arguments).get("card_id") == _GHOLA
        and dict(action.arguments).get("graft") is True
    )
    placed = apply_placement(_ENGINE, state, place).state
    graft = next(
        action
        for action in _ENGINE.legal_actions(placed, 0)
        if action.action_id == "choose_graft_partner"
        and dict(action.arguments).get("card_id") == partner
    )
    grafted = _ENGINE.apply(placed, graft).state
    assert dict(grafted.decision_stack[-1].context)["card_id"] == _GHOLA
    return grafted


def _icon_text(state: GameState, key: str) -> tuple[str | None, str | None]:
    action = DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("effect", key),)
    )
    return effect_action_text(state, action), effect_action_text_ko(state, action)


def test_a_ghola_copy_of_fill_coffers_shows_the_copied_icons() -> None:
    # "This card has the same Agent box as the other grafted card" [Ghola
    # card]: copying the Signet Ring's Fill Coffers it pays 1 Solari, as the
    # engine does, and its spice keeps the Alliance condition. The text read
    # Ghola's own (empty) box, so it said 2 Solari and lost the condition.
    state = _ghola_box(_SIGNET, leader_id="lady_amber_metulli")

    assert _icon_text(state, "solari") == ("Gain 1 solari", "{solari:1}")
    assert _icon_text(state, "spice") == (
        "Gain 1 spice (if you have an Alliance)",
        "{spice:1} ({alliance}이 있다면)",
    )


def test_a_ghola_copy_of_cargo_runner_names_each_contract_line() -> None:
    state = _ghola_box(_CARGO_RUNNER)

    assert _icon_text(state, "cards") == (
        "Draw 1 card (if you have completed 2 or more contracts)",
        "{draw:1} ({contract} 둘 이상 완수했다면)",
    )
    assert _icon_text(state, "cards_second") == (
        "Draw 1 card (if you have completed 4 or more contracts)",
        "{draw:1} ({contract} 넷 이상 완수했다면)",
    )


def test_urgent_shigawire_draw_is_named_apart_from_the_box_draw() -> None:
    """The draw Urgent Shigawire adds to a boosted card's box is its own
    ``cards`` step (user ruling 2026-10-10, OQ-106) with no condition: below
    Hidden Missive's two Bene Gesserit Influence the one ``cards`` action is
    that added draw and says so; at the threshold it is the box's own."""

    missive = "imperium:hidden_missive:0"
    for influence, english, korean in (
        (0, "Draw 1 card (Urgent Shigawire)", "{draw:1} (다급한 시거와이어)"),
        (2, "Draw 1 card (at 2 Bene Gesserit Influence)", None),
    ):
        seat = PlayerState(
            player_id=0,
            hand=(missive,),
            deck=(_SIGNET,),
            influence=Influence(bene_gesserit=influence),
            bene_gesserit_boost_pending=True,
        )
        state = GameState(
            config=RulesetConfig(bloodlines=True),
            seed=1,
            phase=GamePhase.PLAYER_TURNS,
            round_number=1,
            intrigue_deck=intrigue_deck_instance_ids(False)[:3],
            players=(seat, *(PlayerState(player_id=other) for other in range(1, 4))),
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
            for action in executable_placements(state, 0)
            if dict(action.arguments).get("space_id") == "secrets"
        )
        placed = apply_placement(_ENGINE, state, place).state
        text, text_ko = _icon_text(placed, "cards")
        assert text == english
        if korean is not None:
            assert text_ko == korean


def test_piter_genius_advisor_reward_icons_say_what_they_give() -> None:
    """Piter's "draw two cards and Research" are armed icons after its troop
    cost (user ruling 2026-10-10, OQ-106): two cards, and a Research with
    no specimen (Industrial Espionage's line keeps its specimen)."""

    piter = PersonalCardAgentEffect.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH
    assert agent_card_icon_text(piter, "cards") == "Draw 2 cards"
    assert agent_card_icon_text_ko(piter, "cards") == "{draw:2}"
    assert agent_card_icon_text(piter, "research") == "Research"
    assert agent_card_icon_text_ko(piter, "research") == "{research}"
    espionage = PersonalCardAgentEffect.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED
    assert agent_card_icon_text(espionage, "research").startswith(
        "Research, Generate 1 specimen"
    )


# --- An Agent box's rows name the card and what its box does --------------
#
# User request 2026-10-11: "그냥 선택지에 카드 효과가 바로 보여지는게 낫지
# 않나? 접합했을 때도 왜 다른 접합한 카드 효과 보기를 또 눌러야 그렇게 되게
# 한거야." The argument-less ``resolve_agent_card_effect`` and the graft's
# ``switch_graft_card`` carry the box text of the card they work on, every
# box row carries that card's name (``agent_box_row_title``), and the page
# shows the pair as the button ("동맹 물색: 이 카드 폐기").

_IMMORTALITY = RulesetConfig(immortality=True, choam_module=True)
_SEEK_ALLIES = "player:0:starter:seek_allies:0"
_FACE_DANCER = "tleilaxu:face_dancer:0"
_RESOLVE_BOX = DomainAction(action_id="resolve_agent_card_effect", actor=0)
# Box 1's plain resolution on a grafted turn (codec v143).
_RESOLVE_BOX_ONE = DomainAction(
    action_id="resolve_agent_card_effect", actor=0, arguments=(("box", 1),)
)


def _turn(hand: tuple[str, ...]) -> GameState:
    seat = PlayerState(
        player_id=0, hand=hand, resources=Resources(solari=4, spice=2, water=2)
    )
    imperium = imperium_deck_instance_ids(True)
    return GameState(
        config=_IMMORTALITY,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=("choam_security",),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=(seat, *(PlayerState(player_id=other) for other in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _place(state: GameState, card: str, partner: str | None = None) -> GameState:
    """Seat 0 sends ``card`` to Dutiful Service (grafted with ``partner``)."""

    place = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments).get("card_id") == card
        and dict(action.arguments).get("space_id") == "dutiful_service"
        and (dict(action.arguments).get("graft") is True) == (partner is not None)
    )
    placed = apply_placement(_ENGINE, state, place).state
    if partner is None:
        return placed
    graft = next(
        action
        for action in _ENGINE.legal_actions(placed, 0)
        if action.action_id == "choose_graft_partner"
        and dict(action.arguments).get("card_id") == partner
    )
    return _ENGINE.apply(placed, graft).state


def _row(state: GameState, action: DomainAction) -> tuple[object, ...]:
    assert action in _ENGINE.legal_actions(state, 0)
    return (
        agent_box_row_title(state, action),
        effect_action_text(state, action),
        effect_action_text_ko(state, action),
    )


def test_seek_allies_box_row_reads_its_trash() -> None:
    # Seek Allies' Agent box is "Trash this card" [Seek Allies card]: its
    # one row names the card and the trash, as a word in Korean (one
    # rulebook icon per effect: the trash icon is "Trash one card").
    placed = _place(_turn((_SEEK_ALLIES,)), _SEEK_ALLIES)

    assert _row(placed, _RESOLVE_BOX) == (
        ("Seek Allies", "동맹 물색"),
        "Trash this card",
        "이 카드 폐기",
    )


def test_a_graft_pairs_two_rows_name_each_card_and_its_box() -> None:
    grafted = _place(_turn((_FACE_DANCER, _SEEK_ALLIES)), _FACE_DANCER, _SEEK_ALLIES)

    # Both cards' boxes are offered from the start (codec v143): the placed
    # card's untagged, the partner's with ``box=1``, each led by its card.
    assert _row(grafted, _RESOLVE_BOX) == (
        ("Face Dancer", "얼굴의 춤꾼"),
        "Draw 1 card",
        "{draw:1}",
    )
    assert _row(grafted, _RESOLVE_BOX_ONE) == (
        ("Seek Allies", "동맹 물색"),
        "Trash this card",
        "이 카드 폐기",
    )

    # With box 1 resolved (and active in the frame), box 0's row still names
    # Face Dancer: each row is read with its own box active.
    partner_done = _ENGINE.apply(grafted, _RESOLVE_BOX_ONE).state
    assert _row(partner_done, _RESOLVE_BOX) == (
        ("Face Dancer", "얼굴의 춤꾼"),
        "Draw 1 card",
        "{draw:1}",
    )
    assert _RESOLVE_BOX_ONE not in _ENGINE.legal_actions(partner_done, 0)


def test_a_bene_gesserit_partner_s_added_draw_names_its_card() -> None:
    # A Bene Gesserit graft partner takes a pending Urgent Shigawire boost
    # (user ruling 2026-10-12, OQ-107): the draw added to its box is its
    # ``box=1`` card-draw row, led by the partner and named as the added
    # draw, while the placed Face Dancer's box keeps its own row.
    truthtrance = "imperium:truthtrance:0"
    state = _turn((_FACE_DANCER, truthtrance))
    state = replace(
        state,
        players=(
            replace(state.players[0], bene_gesserit_boost_pending=True),
            *state.players[1:],
        ),
    )
    grafted = _place(state, _FACE_DANCER, truthtrance)
    added = DomainAction(
        action_id="resolve_agent_card_effect",
        actor=0,
        arguments=(("box", 1), ("effect", "cards")),
    )
    title, text, text_ko = _row(grafted, added)
    assert isinstance(title, tuple) and title[0] == "Truthtrance"
    assert text == "Draw 1 card (Urgent Shigawire)"
    assert text_ko == "{draw:1} (다급한 시거와이어)"
    assert _row(grafted, _RESOLVE_BOX)[0] == ("Face Dancer", "얼굴의 춤꾼")


def test_a_ghola_copy_of_the_added_draw_names_ghola() -> None:
    # Ghola grafted to the boosted card copies the draw added to its box
    # (user ruling 2026-10-12, OQ-107, codec v145): Truthtrance, boosted, is
    # placed with "all Agent icons" and keeps its draw (box 0); Ghola's copy
    # is box 1's row, led by Ghola.
    truthtrance = "imperium:truthtrance:0"
    ghola = "tleilaxu:ghola:0"
    state = _turn((truthtrance, ghola))
    state = replace(
        state,
        players=(
            replace(state.players[0], bene_gesserit_boost_pending=True),
            *state.players[1:],
        ),
    )
    grafted = _place(state, truthtrance, ghola)
    draw = (("effect", "cards"),)
    placed = DomainAction("resolve_agent_card_effect", 0, draw)
    copy = DomainAction("resolve_agent_card_effect", 0, (("box", 1), *draw))
    assert _row(grafted, placed) == (
        ("Truthtrance", "진실의 무아지경"),
        "Draw 1 card (Urgent Shigawire)",
        "{draw:1} (다급한 시거와이어)",
    )
    assert _row(grafted, copy) == (
        ("Ghola", "골라"),
        "Draw 1 card (Urgent Shigawire)",
        "{draw:1} (다급한 시거와이어)",
    )


def test_a_ghola_box_names_ghola_with_the_box_it_copies() -> None:
    # "This card has the same Agent box as the other grafted card" [Ghola
    # card]: Ghola's row (box 0) and Seek Allies' (box 1) both read Seek
    # Allies' box, each led by its own card.
    ghola = _ghola_box(_SEEK_ALLIES)
    assert _row(ghola, _RESOLVE_BOX) == (
        ("Ghola", "골라"),
        "Trash this card",
        "이 카드 폐기",
    )
    assert _row(ghola, _RESOLVE_BOX_ONE) == (
        ("Seek Allies", "동맹 물색"),
        "Trash this card",
        "이 카드 폐기",
    )


def test_a_grafted_payment_row_is_led_by_its_box_s_card() -> None:
    # A pick of a grafted box names its card even with no effect text of its
    # own, so Stitched Horror's and its Ghola copy's picks tell apart.
    horror = "tleilaxu:stitched_horror:0"
    ghola = _ghola_box(horror)
    rows = [
        action
        for action in _ENGINE.legal_actions(ghola, 0)
        if action.action_id == "choose_agent_card_reward"
    ]
    titles = {
        dict(action.arguments).get("box", 0): agent_box_row_title(ghola, action)
        for action in rows
    }
    assert titles == {
        0: ("Ghola", "골라"),
        1: ("Stitched Horror", "공포의 누더기 괴물"),
    }


def test_keyed_icon_rows_are_led_by_their_card() -> None:
    # Hidden Missive's two icons (OQ-027) keep their icon text and gain the
    # card's name.
    missive = "imperium:hidden_missive:0"
    seat = PlayerState(
        player_id=0, hand=(missive,), influence=Influence(bene_gesserit=2)
    )
    state = replace(
        _turn(()),
        config=RulesetConfig(),
        players=(seat, *(PlayerState(player_id=other) for other in range(1, 4))),
    )
    place = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments).get("space_id") == "assembly_hall"
    )
    placed = apply_placement(_ENGINE, state, place).state
    rows = {
        dict(action.arguments)["effect"]: _row(placed, action)
        for action in _ENGINE.legal_actions(placed, 0)
        if action.action_id == "resolve_agent_card_effect"
    }
    assert rows == {
        "troops": (
            ("Hidden Missive", "비밀 서신"),
            "Recruit 1 troop (at 2 Bene Gesserit Influence)",
            "{troop:1} ({influence_bene_gesserit:2}일 때)",
        ),
        "cards": (
            ("Hidden Missive", "비밀 서신"),
            "Draw 1 card (at 2 Bene Gesserit Influence)",
            "{draw:1} ({influence_bene_gesserit:2}일 때)",
        ),
    }


def test_other_rows_have_no_box_title() -> None:
    placed = _place(_turn((_SEEK_ALLIES,)), _SEEK_ALLIES)
    others = [
        action
        for action in _ENGINE.legal_actions(placed, 0)
        if action.action_id not in ("resolve_agent_card_effect", "switch_graft_card")
    ]
    assert others
    assert all(agent_box_row_title(placed, action) is None for action in others)


@pytest.mark.parametrize("effect", list(AGENT_EFFECT_TEXT_KO))
def test_box_text_on_a_button_writes_one_icon_per_effect(
    effect: PersonalCardAgentEffect,
) -> None:
    # The printed twin keeps the card's icons (popover); a button writes a
    # card's trash or discard beside the word 카드 as the word
    # (tests/server/test_label_icons.py, user 2026-10-11).
    text = _one_icon_per_effect_ko(AGENT_EFFECT_TEXT_KO[effect])
    for icon in ("trash", "discard"):
        assert not re.search(rf"카드를?(?: \d+장)? \{{{icon}\}}", text), text


# --- The decision panel groups an Agent turn's rows by box ----------------
#
# Plan stage 4 (docs/graft-boxes-plan.md 4.11, user request 2026-10-11): the
# page sets each Agent box's rows under a header naming its card, box 0 (the
# placed card) first, then box 1 (its graft partner). The server says which
# box each legal row is (``agent_box_of_rows``) and which boxes the turn has
# (``agent_box_headers``), so the page never guesses from the arguments.


def _boxes(state: GameState) -> dict[DomainAction, int | None]:
    legal = _ENGINE.legal_actions(state, 0)
    return dict(zip(legal, agent_box_of_rows(state, 0, legal), strict=True))


def test_each_row_of_a_grafted_turn_names_its_box() -> None:
    grafted = _place(_turn((_FACE_DANCER, _SEEK_ALLIES)), _FACE_DANCER, _SEEK_ALLIES)
    boxes = _boxes(grafted)

    assert boxes[_RESOLVE_BOX] == 0
    assert boxes[_RESOLVE_BOX_ONE] == 1
    # The space's effects, deployments, the turn's end: no box.
    others = [
        action
        for action in boxes
        if action.action_id != "resolve_agent_card_effect"
    ]
    assert others and all(boxes[action] is None for action in others)
    assert agent_box_headers(grafted, 0) == [
        {
            "box": 0,
            "card_id": _FACE_DANCER,
            "name": "Face Dancer",
            "name_ko": "얼굴의 춤꾼",
            "locked": False,
        },
        {
            "box": 1,
            "card_id": _SEEK_ALLIES,
            "name": "Seek Allies",
            "name_ko": "동맹 물색",
            "locked": False,
        },
    ]

    # Box 1 acted and is the active box now: the numbers stay fixed.
    partner_done = _ENGINE.apply(grafted, _RESOLVE_BOX_ONE).state
    assert _boxes(partner_done)[_RESOLVE_BOX] == 0
    headers = agent_box_headers(partner_done, 0)
    assert headers is not None
    assert [(entry["box"], entry["card_id"]) for entry in headers] == [
        (0, _FACE_DANCER),
        (1, _SEEK_ALLIES),
    ]


def test_a_single_card_turn_has_one_box() -> None:
    # Hidden Missive's two icons (OQ-027) are box 0's rows.
    missive = "imperium:hidden_missive:0"
    seat = PlayerState(
        player_id=0, hand=(missive,), influence=Influence(bene_gesserit=2)
    )
    state = replace(
        _turn(()),
        config=RulesetConfig(),
        players=(seat, *(PlayerState(player_id=other) for other in range(1, 4))),
    )
    place = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments).get("space_id") == "assembly_hall"
    )
    placed = apply_placement(_ENGINE, state, place).state
    boxes = _boxes(placed)

    icons = [
        action
        for action in boxes
        if action.action_id == "resolve_agent_card_effect"
    ]
    assert len(icons) == 2 and all(boxes[action] == 0 for action in icons)
    assert all(
        boxes[action] is None for action in boxes if action not in icons
    )
    assert agent_box_headers(placed, 0) == [
        {
            "box": 0,
            "card_id": missive,
            "name": "Hidden Missive",
            "name_ko": "비밀 서신",
            "locked": False,
        }
    ]


def test_a_box_held_back_by_the_other_box_s_choice_is_marked_locked() -> None:
    # "Choose two" names both before either resolves (OQ-057 (4)); the
    # other box's rows wait meanwhile (user decision 2026-10-12, plan 4.3).
    horror = "tleilaxu:stitched_horror:0"
    ghola = _ghola_box(horror)
    first_pick = next(
        action
        for action in _ENGINE.legal_actions(ghola, 0)
        if action.action_id == "choose_agent_card_reward"
        and dict(action.arguments).get("box") == 1
    )
    picked = _ENGINE.apply(ghola, first_pick).state
    boxes = _boxes(picked)

    assert {box for box in boxes.values() if box is not None} == {1}
    headers = agent_box_headers(picked, 0)
    assert headers is not None
    assert [(entry["box"], entry["name"], entry["locked"]) for entry in headers] == [
        (0, "Ghola", True),
        (1, "Stitched Horror", False),
    ]


def test_only_the_seat_deciding_the_effect_frame_gets_boxes() -> None:
    grafted = _place(_turn((_FACE_DANCER, _SEEK_ALLIES)), _FACE_DANCER, _SEEK_ALLIES)
    legal = _ENGINE.legal_actions(grafted, 0)

    assert agent_box_headers(grafted, 1) is None
    assert agent_box_of_rows(grafted, 1, legal) == (None,) * len(legal)
    # Before the placement the turn has no Agent box yet.
    start = _turn((_SEEK_ALLIES,))
    start_legal = _ENGINE.legal_actions(start, 0)
    assert agent_box_headers(start, 0) is None
    assert set(agent_box_of_rows(start, 0, start_legal)) == {None}
