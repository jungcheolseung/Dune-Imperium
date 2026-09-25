"""English detail text for legal actions that resolve one printed icon.

The play server attaches this to each legal action so the browser can show
which printed effect a keyed resolution (``resolve_board_effect`` /
``resolve_agent_card_effect`` with an ``effect`` argument) stands for. It is
derived from the same engine tables and card data the rules execute.
"""

from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import (
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.display.spaces import (
    board_effect_action_text,
    board_effect_action_text_ko,
)
from dune_imperium.rules.effects import current_agent_effect_context
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
}


def agent_card_icon_text(effect: PersonalCardAgentEffect | None, key: str) -> str:
    """Render one printed Agent-box icon of a multi-icon card."""

    match key:
        case "cards":
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
        case "cards":
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


def effect_action_text(state: GameState, action: DomainAction) -> str | None:
    """Describe a keyed icon resolution; None for every other action."""

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
