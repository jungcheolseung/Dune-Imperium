"""English detail text for legal actions that resolve one printed icon.

The play server attaches this to each legal action so the browser can show
which printed effect a keyed resolution (``resolve_board_effect`` /
``resolve_agent_card_effect`` with an ``effect`` argument) stands for. It is
derived from the same engine tables and card data the rules execute.
"""

from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.display.spaces import board_effect_action_text
from dune_imperium.rules.effects import current_agent_effect_context

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
}


def agent_card_icon_text(effect: PersonalCardAgentEffect | None, key: str) -> str:
    """Render one printed Agent-box icon of a multi-icon card."""

    match key:
        case "cards":
            base = "Draw 1 card"
        case "intrigue":
            base = "Draw 1 Intrigue card"
        case "troops":
            base = (
                "Recruit 2 troops"
                if effect
                is _BOX.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
                else "Recruit 1 troop"
            )
        case "solari":
            base = "Gain 2 solari"
        case "spice":
            base = "Gain 1 spice"
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


def effect_action_text(state: GameState, action: DomainAction) -> str | None:
    """Describe a keyed icon resolution; None for every other action."""

    key = dict(action.arguments).get("effect")
    if not isinstance(key, str):
        return None
    if action.action_id == "resolve_board_effect":
        return board_effect_action_text(state, action)
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
