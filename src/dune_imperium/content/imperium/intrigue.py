"""The original game's Intrigue cards (stage P3).

docs/base-game-and-ix-plan.md 16: 34 kinds, 40 cards [DI p. 3]. Per D1
(plan 2.4) the printed effects come from the Steam app's screen pieces and
English text; the rules behind them are docs/rules/imperium-base.md, the
Plot / Combat / Endgame timings [DI pp. 13-14] those of Uprising.

While stage P3 is a trial (plan 16.7) these cards are not in the original
game's Intrigue deck and not in the observation: both come with stage P3a
(plan 16.1, 16.8 2). ``content.uprising.intrigue``'s ``INTRIGUE_CARDS_BY_ID``
and ``INTRIGUE_CARDS_BY_INSTANCE`` resolve them; code that lists Uprising's
own cards iterates ``INTRIGUE_CARDS`` instead.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.effect_dsl import (
    EffectSection,
    GainCombatStrength,
    GainInfluence,
    PayResources,
    RetreatTroops,
)
from dune_imperium.content.uprising.intrigue import (
    IntrigueCardEntry,
    _combat,
    _plot,
)

IMPERIUM_INTRIGUE_SOURCES: Final = (
    SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (3, 13, 14)),
)


def intrigue_card(card_id: str, name: str) -> CardDefinition:
    """The identity of an original Intrigue card."""

    return CardDefinition(card_id=card_id, name=name, sources=IMPERIUM_INTRIGUE_SOURCES)


# Typed: ``content.uprising.intrigue`` reads it while both modules load.
IMPERIUM_INTRIGUE_CARDS: Final[tuple[IntrigueCardEntry, ...]] = (
    IntrigueCardEntry(
        card=intrigue_card("bribery", "Bribery"),
        copies=1,
        # "2 Solari -> 1 Influence (any Faction)" [Bribery card, app text]:
        # a cost arrow line [DI p. 16]; the Faction is the player's choice and
        # a line whose Influence cannot move is not played (OQ-060, OQ-071).
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=2),),
                    rewards=(GainInfluence(),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("master_tactician", "Master Tactician"),
        copies=3,
        # "+3 swords -OR- Retreat up to three of your troops." [Master
        # Tactician card, app text]: two exclusive Combat options like
        # Tactical Option (OQ-058). "Up to" allows zero [FAQ p. 3]
        # (imperium-base.md 13.2, the Chani and Rapid Mobilization rows).
        options=(
            _combat(EffectSection(rewards=(GainCombatStrength(3),))),
            _combat(EffectSection(rewards=(RetreatTroops(0, 3),))),
        ),
    ),
    # --- Identities only (stage P3a, plan 16.1): name, copies and cost from the
    # app's attribute table (scripts/dwgr/imperium_entries.py skeleton); each
    # card's play data replaces its entry when it is transcribed. ---
    IntrigueCardEntry(
        card=intrigue_card("allied_armada", "Allied Armada"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("ambush", "Ambush"),
        copies=2,
        # "+4 swords" [Ambush card, app text]: a cost-free Combat line.
        options=(_combat(EffectSection(rewards=(GainCombatStrength(4),))),),
    ),
    IntrigueCardEntry(
        card=intrigue_card("bindu_suspension", "Bindu Suspension"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("bypass_protocol", "Bypass Protocol"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("choam_shares", "CHOAM Shares"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("calculated_hire", "Calculated Hire"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("charisma", "Charisma"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("corner_the_market", "Corner the Market"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("councilors_dispensation", "Councilor's Dispensation"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("demand_respect", "Demand Respect"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("dispatch_an_envoy", "Dispatch an Envoy"),
        copies=2,
    ),
    IntrigueCardEntry(
        card=intrigue_card("double_cross", "Double Cross"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("favored_subject", "Favored Subject"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("guild_authorization", "Guild Authorization"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("infiltrate", "Infiltrate"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("know_their_ways", "Know Their Ways"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("plans_within_plans", "Plans Within Plans"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("poison_snooper", "Poison Snooper"),
        copies=2,
    ),
    IntrigueCardEntry(
        card=intrigue_card("private_army", "Private Army"),
        copies=2,
    ),
    IntrigueCardEntry(
        card=intrigue_card("rapid_mobilization", "Rapid Mobilization"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("recruitment_mission", "Recruitment Mission"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("refocus", "Refocus"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("reinforcements", "Reinforcements"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("secret_of_the_sisterhood", "Secret of the Sisterhood"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("staged_incident", "Staged Incident"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("the_sleeper_must_awaken", "The Sleeper Must Awaken"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("tiebreaker", "Tiebreaker"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("to_the_victor", "To the Victor..."),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("urgent_mission", "Urgent Mission"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("water_peddlers_union", "Water Peddlers Union"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("water_of_life", "Water of Life"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("windfall", "Windfall"),
        copies=1,
    ),
)
