"""English display text for the 22 Uprising board spaces.

Spaces whose printed effect is fully covered by the engine's static
automatic-effect table render their text from that same table, so the shown
effect cannot drift from what the engine executes. Spaces resolved through
dedicated choice frames or imperative code carry hand-authored lines whose
wording follows ``docs/rules/board-spaces.md`` (Board Space Guide citations).
Implementation flags are always computed from the engine table, never
authored, so an unimplemented space is marked automatically.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import assert_never

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.rules.board_effects import (
    BOARD_ICON_CONTRACT,
    BOARD_ICON_HIGH_COUNCIL,
    BOARD_ICON_INFLUENCE,
    BOARD_ICON_SPY,
    BOARD_ICON_SWORDMASTER,
    BOARD_ICON_TRASH,
    CHOICE_DRIVEN_SPACE_IDS,
    board_icon_for_effect,
    static_board_effects,
    visit_board_effects,
)
from dune_imperium.rules.effects import (
    AutomaticEffect,
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    RecruitTroopsEffect,
    current_agent_effect_context,
)

FACTION_NAMES: Mapping[Faction, str] = MappingProxyType(
    {
        Faction.EMPEROR: "Emperor",
        Faction.SPACING_GUILD: "Spacing Guild",
        Faction.BENE_GESSERIT: "Bene Gesserit",
        Faction.FREMEN: "Fremen",
    }
)

# Hand-authored effect lines, keyed by (space_id, choam_module) with None
# meaning both rulesets, holding one string per cost option. Wording follows
# docs/rules/board-spaces.md; the faction-visit Influence line is included
# where the space has a faction Agent icon.
_AUTHORED_OPTION_EFFECTS: Mapping[
    tuple[str, bool | None],
    tuple[str, ...],
] = MappingProxyType(
    {
        ("dutiful_service", True): (
            "Gain 1 Emperor Influence. Take a face-up Contract"
            " (Gain 2 solari if none is available)",
        ),
        ("accept_contract", True): (
            "Draw 1 card. Take a face-up Contract"
            " (Gain 2 solari if none is available)",
        ),
        ("espionage", None): (
            "Gain 1 Bene Gesserit Influence, Draw 1 card."
            " You may place a Spy",
        ),
        ("secrets", None): (
            "Gain 1 Bene Gesserit Influence, Draw 1 Intrigue card."
            " Each opponent holding 4 or more Intrigue cards gives you one"
            " at random",
        ),
        ("desert_tactics", None): (
            "Gain 1 Fremen Influence, Recruit 1 troop."
            " You may trash a card",
        ),
        ("high_council", None): (
            "First visit: seat your Councilor for +2 Persuasion at every"
            " Reveal turn. Later visits: Gain 2 spice, Draw 1 Intrigue card,"
            " Recruit 3 troops",
        ),
        ("imperial_privilege", None): (
            "You may discard an Intrigue card to draw an Intrigue card."
            " Recall one of your other Agents and Draw 1 card",
        ),
        ("swordmaster", None): (
            "Once per game: take your third Agent, usable from this round",
        )
        * 2,
        ("sietch_tabr", None): (
            "Choose one: take the Maker Hooks token (if you lack it),"
            " Recruit 1 troop and Gain 1 water — or Gain 1 water,"
            " optionally destroying the Shield Wall",
        ),
        ("deep_desert", None): (
            "Take all bonus spice here, then choose: Gain 4 spice — or,"
            " with Maker Hooks, summon 2 sandworms into the Conflict",
        ),
        ("hagga_basin", None): (
            "Take all bonus spice here, then choose: Gain 2 spice — or,"
            " with Maker Hooks, summon 1 sandworm into the Conflict",
        ),
        ("imperial_basin", None): ("Gain 1 spice plus all bonus spice here",),
        ("shipping", None): (
            "Gain 5 solari, Gain 1 Influence with a Faction of your choice",
        ),
    }
)

# Printed facts outside the automatic-effects channel, each verified against
# its implementing rules module (reveal_turn.py persuasion passives,
# agent_turn.py control visit bonus).
SPACE_NOTES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "assembly_hall": (
            "While your Agent is here: +1 Persuasion at your Reveal turn",
        ),
        "arrakeen": (
            "Control: whenever an Agent is sent here, the controller"
            " gains 1 solari",
        ),
        "spice_refinery": (
            "Control: whenever an Agent is sent here, the controller"
            " gains 1 solari",
        ),
        "imperial_basin": (
            "Control: whenever an Agent is sent here, the controller"
            " gains 1 spice",
        ),
    }
)


# English lines for the printed icons outside the automatic-effects table,
# worded after docs/rules/board-spaces.md (Board Space Guide citations).
_ICON_TEXTS: Mapping[str, str] = MappingProxyType(
    {
        BOARD_ICON_CONTRACT: (
            "Take a face-up Contract (Gain 2 solari if none is available)"
        ),
        BOARD_ICON_HIGH_COUNCIL: (
            "Seat your Councilor for +2 Persuasion at every Reveal turn"
        ),
        BOARD_ICON_SWORDMASTER: "Take your third Agent, usable from this round",
        BOARD_ICON_SPY: "You may place a Spy",
        BOARD_ICON_TRASH: "You may trash a card",
        BOARD_ICON_INFLUENCE: "Gain 1 Influence with a Faction of your choice",
    }
)


def board_icon_text(key: str, effects: tuple[AutomaticEffect, ...]) -> str:
    """Render one printed icon of a visit as an English effect fragment.

    Automatic icons read their amount from ``effects`` (the visit's entries
    of the engine table); the choice and one-off icons use the authored
    lines above.
    """

    for effect in effects:
        if board_icon_for_effect(effect) == key:
            return ", ".join(automatic_effect_texts(effect))
    return _ICON_TEXTS[key]


def board_effect_action_text(state: GameState, action: DomainAction) -> str | None:
    """Describe a ``resolve_board_effect`` action by the icon it resolves.

    Returns None for any other action or outside an Agent-turn effect frame.
    """

    if action.action_id != "resolve_board_effect":
        return None
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    space_id = context.get("space_id")
    cost_option = context.get("cost_option")
    key = dict(action.arguments).get("effect")
    if (
        not isinstance(space_id, str)
        or isinstance(cost_option, bool)
        or not isinstance(cost_option, int)
        or not isinstance(key, str)
    ):
        return None
    effects = visit_board_effects(
        state.players[action.actor],
        space_id,
        cost_option,
        choam_module=state.config.choam_module,
    )
    return board_icon_text(key, effects)


def space_option_count(space_id: str) -> int:
    """Return how many paid cost options the space offers (at least one)."""

    return max(1, len(BOARD_SPACES_BY_ID[space_id].cost_options))


def space_option_effects(
    space_id: str,
    *,
    choam_module: bool,
) -> tuple[str, ...]:
    """Return one English effect line per cost option of the space."""

    authored = _AUTHORED_OPTION_EFFECTS.get(
        (space_id, choam_module)
    ) or _AUTHORED_OPTION_EFFECTS.get((space_id, None))
    if authored is not None:
        return authored
    return tuple(
        _automatic_option_text(space_id, option, choam_module=choam_module)
        for option in range(space_option_count(space_id))
    )


def space_is_implemented(space_id: str, *, choam_module: bool) -> bool:
    """Mirror the engine's placement gate for every option of the space."""

    if space_id in CHOICE_DRIVEN_SPACE_IDS:
        return True
    for option in range(space_option_count(space_id)):
        try:
            static_board_effects(space_id, option, choam_module=choam_module)
        except NotImplementedError:
            return False
    return True


def space_notes(space_id: str) -> tuple[str, ...]:
    """Return printed always-on facts that are not part of the visit effect."""

    return SPACE_NOTES.get(space_id, ())


def _automatic_option_text(
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
) -> str:
    fragments: list[str] = []
    faction = BOARD_SPACES_BY_ID[space_id].faction
    if faction is not None:
        fragments.append(f"Gain 1 {FACTION_NAMES[faction]} Influence")
    for effect in static_board_effects(
        space_id,
        cost_option,
        choam_module=choam_module,
    ):
        fragments.extend(automatic_effect_texts(effect))
    return ", ".join(fragments)


def automatic_effect_texts(effect: AutomaticEffect) -> tuple[str, ...]:
    """Render one engine automatic effect as display fragments."""

    match effect:
        case GainResourcesEffect():
            return tuple(
                f"Gain {amount} {resource}"
                for resource, amount in (
                    ("solari", effect.solari),
                    ("spice", effect.spice),
                    ("water", effect.water),
                )
                if amount
            )
        case RecruitTroopsEffect():
            noun = "troop" if effect.count == 1 else "troops"
            return (f"Recruit {effect.count} {noun}",)
        case DrawImperiumCardsEffect():
            noun = "card" if effect.count == 1 else "cards"
            return (f"Draw {effect.count} {noun}",)
        case DrawIntrigueCardsEffect():
            noun = "Intrigue card" if effect.count == 1 else "Intrigue cards"
            return (f"Draw {effect.count} {noun}",)
        case _:
            assert_never(effect)
