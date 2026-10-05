"""English detail text for legal actions that resolve one printed icon.

The play server attaches this to each legal action so the browser can show
which printed effect a keyed resolution (``resolve_board_effect`` /
``resolve_agent_card_effect`` with an ``effect`` argument) stands for, or
what a payment shared by several Agent boxes buys on the card resolving
(``_PAYMENT_TEXT``). It is derived from the same engine tables and card data
the rules execute.
"""

from dune_imperium.content.bloodlines.tech import TECH_TILES_BY_ID
from dune_imperium.content.uprising.effect_dsl import GainInfluence, LoseInfluence
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import (
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.display.scouts import scouts_action_text
from dune_imperium.display.spaces import (
    board_effect_action_text,
    board_effect_action_text_ko,
)
from dune_imperium.rules.effects import (
    active_agent_card,
    current_agent_effect_context,
)
from dune_imperium.rules.intrigue import current_intrigue_choice_slot
from dune_imperium.rules.reveal_turn import reveal_choice_prompt

_BOX = PersonalCardAgentEffect

# Printed conditions of the multi-icon Agent boxes, judged when the icon
# resolves (OQ-027); shown after the icon's effect.
_ICON_CONDITIONS: dict[tuple[PersonalCardAgentEffect, str], str] = {
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "troops"): (
        "at 2 Bene Gesserit Influence"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "cards"): (
        "at 2 Bene Gesserit Influence"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "water"): (
        "at 2 Bene Gesserit Influence"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "spice"): (
        "at 2 Fremen Influence"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "solari"): (
        "at 2 Emperor Influence"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "spice"): (
        "at 2 Spacing Guild Influence"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "troops"): (
        "if you gained 2 or more spice this turn"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "cards"): (
        "if you gained 2 or more spice this turn"
    ),
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards"): (
        "if you have completed 2 or more contracts"
    ),
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards_second"): (
        "if you have completed 4 or more contracts"
    ),
}

# Korean twin of _ICON_CONDITIONS. The Influence-count suffixes use a
# *counted* {term:count} placeholder ("at 2 Bene Gesserit Influence" has the
# digit directly before "Bene Gesserit Influence", the exact adjacency
# render.js's ICON_RULES needs to draw a counted icon in English, unlike a
# "2 or more X Influence" threshold, which draws a bare one — see
# tokens_ko.py's module docstring). The spice-this-turn condition is that
# threshold shape (bare {spice} + a plain digit), matching the identical
# "이번 차례에 {spice}를 2 이상 얻었다면" phrasing tokens_ko.py's
# RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN entry already uses
# for the same condition as an "If ...:" prefix; here it is a parenthetical
# suffix instead, matching English's own parenthetical placement.
_ICON_CONDITIONS_KO: dict[tuple[PersonalCardAgentEffect, str], str] = {
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "troops"): (
        "{influence_bene_gesserit:2}일 때"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "cards"): (
        "{influence_bene_gesserit:2}일 때"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "water"): (
        "{influence_bene_gesserit:2}일 때"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "spice"): (
        "{influence_fremen:2}일 때"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "solari"): (
        "{influence_emperor:2}일 때"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "spice"): (
        "{influence_spacing_guild:2}일 때"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "troops"): (
        "이번 차례에 {spice}를 2 이상 얻었다면"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "cards"): (
        "이번 차례에 {spice}를 2 이상 얻었다면"
    ),
    # Cargo Runner's lines, in tokens_ko.py's own words for the same box.
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards"): (
        "{contract} 둘 이상 완수했다면"
    ),
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards_second"): (
        "{contract} 넷 이상 완수했다면"
    ),
}


# Payments whose action id several Agent boxes share. ``pay_agent_card_spice``
# pays Smuggler's Haven's 4 spice for a Victory Point and, in Epic Game Mode,
# Control the Spice's 1 spice to trash a card and recruit a troop, the trash
# still optional after paying [FAQ p. 3] (docs/rules/epic-game-mode.md 6).
# The client's label only says a card effect's cost is paid (it is all the
# action log has); on the buttons this detail replaces it (static/core.js
# describeAction). English is card wording for iconize(), in the printed
# order; Korean keeps tokens_ko.py's words for the same boxes and labels.js's
# "카드 {trash} (선택)".
_PAYMENT_TEXT: dict[tuple[str, PersonalCardAgentEffect], tuple[str, str]] = {
    ("pay_agent_card_spice", _BOX.MAY_PAY_FOUR_SPICE_FOR_VP): (
        "Pay 4 spice → Gain 1 VP",
        "{spice:4} 지불 {arrow_right} {victory_point:1}",
    ),
    ("pay_agent_card_spice", _BOX.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT): (
        "Pay 1 spice → Trash a card (optional) + Recruit 1 troop",
        "{spice:1} 지불 {arrow_right} 카드 {trash} (선택) + {troop:1}",
    ),
}
_PAYMENT_ACTION_IDS = frozenset(action_id for action_id, _ in _PAYMENT_TEXT)


def agent_card_payment_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Name what a shared Agent-box payment buys on the resolving card.

    Returns the English and Korean text, or None when the action is no such
    payment.
    """

    if action.action_id not in _PAYMENT_ACTION_IDS:
        return None
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        return None
    # The box resolving, a Ghola's borrowed one included (the engine's own
    # payment choice reads it the same way).
    effect = active_agent_card(context).agent_effect
    if effect is None:
        return None
    return _PAYMENT_TEXT.get((action.action_id, effect))


def agent_card_icon_text(effect: PersonalCardAgentEffect | None, key: str) -> str:
    """Render one printed Agent-box icon of a multi-icon card."""

    match key:
        case "cards" | "cards_second":
            base = "Draw 1 card"
        case "intrigue":
            base = "Draw 1 Intrigue card"
        case "troops":
            base = "Recruit 1 troop"
        case "solari":
            base = "Gain 2 solari"
        case "spice":
            base = (
                "Gain 2 spice"
                if effect
                is (
                    _BOX
                    .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
                )
                else "Gain 1 spice"
            )
        case "water":
            base = "Gain 1 water"
        case "trash_self":
            base = "Trash this card"
        case "pledge":
            base = (
                "Add 1 Influence of your choice to this Conflict's"
                " first-place reward"
            )
        case _:
            raise KeyError(key)
    condition = _ICON_CONDITIONS.get((effect, key)) if effect is not None else None
    return f"{base} ({condition})" if condition else base


def agent_card_icon_text_ko(effect: PersonalCardAgentEffect | None, key: str) -> str:
    """Korean twin of ``agent_card_icon_text``.

    Every ``base`` case mirrors an English wording ``ICON_RULES``
    (``static/render.js``) draws a counted icon for ("Draw 1 card", "Recruit
    1 troop", "Gain 2 solari", …), so each becomes the matching
    ``{term:count}``. "trash_self" reuses this project's own established
    Korean for the same concept: ``labels.js`` ``EFFECT_ICON_LABELS``
    ``trash_self``: "이 카드 {trash}" (that table is the Korean *fallback*
    label for this key when ``detail`` is null; this function supplies the
    real ``detail_ko``, so the wording matches on purpose rather than by
    coincidence). "pledge" instead uses ``docs/rules/glossary-ko.md``'s own
    "first / second / third place | 1등 / 2등 / 3등 칸 | `[Main p. 14]`" —
    not ``labels.js``'s ``pledge``/``first_place_influence_pledged``, which
    say "1위" (a pre-existing mismatch noted for a separate fix, 2026-09-25
    review); Pivotal Gambit's own popover line (this module's
    ``tokens_ko.py`` twin) already reads "1등 보상에", so this function
    matches it rather than the other, wronger, precedent.
    """

    match key:
        case "cards" | "cards_second":
            base = "{draw:1}"
        case "intrigue":
            base = "{intrigue:1}"
        case "troops":
            base = "{troop:1}"
        case "solari":
            base = "{solari:2}"
        case "spice":
            base = (
                "{spice:2}"
                if effect
                is (
                    _BOX
                    .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
                )
                else "{spice:1}"
            )
        case "water":
            base = "{water:1}"
        case "trash_self":
            base = "이 카드 {trash}"
        case "pledge":
            base = "1등 보상에 {influence_any} 선택 추가"
        case _:
            raise KeyError(key)
    condition = _ICON_CONDITIONS_KO.get((effect, key)) if effect is not None else None
    return f"{base} ({condition})" if condition else base


def tech_acquire_action_text(action: DomainAction) -> tuple[str, str] | None:
    """Describe one queued Tech reward and its currently chosen branch."""

    if action.action_id != "resolve_tech_acquire_effect":
        return None
    args = dict(action.arguments)
    tile = TECH_TILES_BY_ID[str(args["tech_id"])]
    effect = str(args["effect"])
    match effect:
        case "solari":
            return (
                f"Gain {tile.acquire_solari} solari",
                f"{{solari:{tile.acquire_solari}}}",
            )
        case "troops":
            return (
                f"Recruit {tile.acquire_troops} troops",
                f"{{troop:{tile.acquire_troops}}}",
            )
        case "intrigue":
            count = tile.acquire_intrigue
            return f"Draw {count} Intrigue cards", f"{{intrigue:{count}}}"
        case "cards":
            return f"Draw {tile.acquire_cards} cards", f"{{draw:{tile.acquire_cards}}}"
        case "victory_points":
            count = tile.acquire_victory_points
            return f"Gain {count} VP", f"{{victory_point:{count}}}"
        case "contracts":
            count = tile.acquire_contracts
            return f"Gain {count} contract", f"{{contract:{count}}}"
        case "influence":
            return "Gain 1 Influence", "{influence_any:1}"
        case "intrigue_or_card":
            if args["choice"] == "intrigue":
                return "Draw 1 Intrigue card", "{intrigue:1}"
            return "Draw 1 card", "{draw:1}"
        case "shield_wall":
            if args.get("destroy_shield_wall") is True:
                return "Destroy the Shield Wall", "{shield_wall} 파괴"
            return "Keep the Shield Wall", "{shield_wall} 유지"
        case "signet":
            return (
                "Use your Leader's Signet Ring ability",
                "지도자의 {signet_ring} 능력 사용",
            )
        case "trash":
            return "Trash a card (optional)", "카드 {trash} (선택)"
        case _:
            if effect.startswith("spy_"):
                return "Place a Spy with Deep Cover", "{spy} 배치 (잠복 스파이)"
            raise ValueError(f"unknown Tech acquire effect: {effect}")


def intrigue_faction_choice_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Distinguish the cost and reward behind the shared Faction choice.

    Each slot resolves one Influence, even when the card has several slots.
    Faction and any Alliance recipient remain the action's normal arguments.
    """

    if action.action_id != "choose_intrigue_faction":
        return None
    match current_intrigue_choice_slot(state, action.actor):
        case LoseInfluence():
            return "Lose 1 Influence", "{influence_lose:1} 하락"
        case GainInfluence():
            return "Gain 1 Influence", "{influence_any:1} 상승"
        case _:
            return None


def effect_action_text(state: GameState, action: DomainAction) -> str | None:
    """Describe an icon, a shared payment, a Faction or a Scouts choice.

    None otherwise.
    """

    faction = intrigue_faction_choice_text(state, action)
    if faction is not None:
        return faction[0]
    tech = tech_acquire_action_text(action)
    if tech is not None:
        return tech[0]
    scouts = scouts_action_text(state, action)
    if scouts is not None:
        return scouts[0]
    payment = agent_card_payment_text(state, action)
    if payment is not None:
        return payment[0]
    key = dict(action.arguments).get("effect")
    if not isinstance(key, str):
        return None
    if action.action_id == "resolve_board_effect":
        return board_effect_action_text(state, action)
    if action.action_id == "resume_reveal_choice":
        return reveal_choice_prompt(PersonalCardRevealChoiceEffect(key))
    if action.action_id != "resolve_agent_card_effect":
        return None
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str):
        return None
    return agent_card_icon_text(personal_card_for_instance(card_id).agent_effect, key)


def effect_action_text_ko(state: GameState, action: DomainAction) -> str | None:
    """Korean twin of ``effect_action_text``.

    ``resolve_agent_card_effect`` (Step K2) resolves through
    ``agent_card_icon_text_ko``; ``resolve_board_effect`` (Step K4) now
    resolves through ``spaces.py``'s ``board_effect_action_text_ko``.
    ``resume_reveal_choice``'s detail is an engine prompt, already
    translated client-side by ``promptText()`` (``i18n.js``) rather than
    through this field, so it stays ``None`` here regardless; the client's
    ``detail_ko`` falls back to the English ``detail`` whenever this
    returns ``None`` (``static/render.js`` ``effectNode``).
    """

    faction = intrigue_faction_choice_text(state, action)
    if faction is not None:
        return faction[1]
    tech = tech_acquire_action_text(action)
    if tech is not None:
        return tech[1]
    scouts = scouts_action_text(state, action)
    if scouts is not None:
        return scouts[1]
    payment = agent_card_payment_text(state, action)
    if payment is not None:
        return payment[1]
    key = dict(action.arguments).get("effect")
    if not isinstance(key, str):
        return None
    if action.action_id == "resolve_board_effect":
        return board_effect_action_text_ko(state, action)
    if action.action_id != "resolve_agent_card_effect":
        return None
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str):
        return None
    card = personal_card_for_instance(card_id)
    return agent_card_icon_text_ko(card.agent_effect, key)
