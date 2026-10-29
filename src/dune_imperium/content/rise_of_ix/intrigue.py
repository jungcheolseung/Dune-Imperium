"""Rise of Ix's Intrigue cards (stage P4a).

docs/base-game-and-ix-plan.md 17.1 and 17.7: 17 kinds, 17 cards shuffled
into the Intrigue deck [Rise of Ix p. 2] (docs/rules/rise-of-ix.md 2).
Advanced Weaponry, Finesse, Machine Culture and War Chest are two-timing
cards. Per D1 (plan 2.4) the printed effects come from the Steam app's
screen pieces and English text when a card is transcribed; the rules behind
them are docs/rules/rise-of-ix.md.

These began as stage P4a identity entries: each holds its identity (name and
copies) and, once transcribed in stage P4d, its options; the skeleton came
from ``scripts/dwgr/imperium_entries.py --set ix skeleton``. With
``rise_of_ix`` the original game's Intrigue deck takes only the transcribed
cards (``rulesets._imperium_intrigue_cards``, stage P4a's board axis), and
the observation lists them all from v39
(plan 17.1, 17.4); setup takes Rise of Ix on the original game since stage
P4c-5. ``content.uprising.intrigue``'s ``INTRIGUE_CARDS_BY_ID`` and
``INTRIGUE_CARDS_BY_INSTANCE`` resolve them; code that lists Uprising's own
cards iterates ``INTRIGUE_CARDS`` instead.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.effect_dsl import (
    DiscardFromHand,
    DrawPersonalCards,
    EffectSection,
    Freighter,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    HasHighCouncil,
    LoseInfluence,
    LoseTroops,
    PayResources,
    RecruitTroops,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.intrigue import (
    IntrigueCardEntry,
    _combat,
    _plot,
)

IX_INTRIGUE_SOURCES: Final = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2,)),)


def ix_intrigue_card(card_id: str, name: str) -> CardDefinition:
    """The identity of a Rise of Ix Intrigue card."""

    return CardDefinition(card_id=card_id, name=name, sources=IX_INTRIGUE_SOURCES)


# Typed: ``content.uprising.intrigue`` reads it while both modules load.
IX_INTRIGUE_CARDS: Final[tuple[IntrigueCardEntry, ...]] = (
    IntrigueCardEntry(
        card=ix_intrigue_card("advanced_weaponry", "Advanced Weaponry"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("blackmail", "Blackmail"),
        copies=1,
        # "Choose a Faction to lose 1 Influence with" -> 5 swords [Blackmail
        # card, app text and screen pieces]: one Combat cost line. The Faction
        # is the player's choice and a seat with no Influence on any track
        # cannot pay it (the FAQ's "pay its costs" [FAQ p. 2]); the swords are
        # always live in a Conflict (OQ-071).
        options=(
            _combat(
                EffectSection(
                    costs=(LoseInfluence(1),),
                    rewards=(GainCombatStrength(5),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("cannon_turrets", "Cannon Turrets"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("cull", "Cull"),
        copies=1,
        # "Played Cull and spent 1 Solari to trash [card]" [Cull card, app log
        # line; the card prints icons only]: one Plot cost line, 1 Solari ->
        # the black Trash icon. The trash is optional like any Trash icon
        # [Main p. 20], but the line is offered only when a card can be
        # trashed (OQ-071, OQ-113 (C); rise-of-ix.md 9: "Cull is played only
        # if it trashes"), from the hand, the discard pile or play.
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=1),),
                    rewards=(TrashPersonalCard(),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("diversion", "Diversion"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("expedite", "Expedite"),
        copies=1,
        # "1 spice -> Freighter" [Steam app screen pieces]. One paid Plot
        # line; each icon offers an advance or recall [Rise of Ix p. 5].
        options=(
            _plot(
                EffectSection(costs=(PayResources(spice=1),), rewards=(Freighter(),))
            ),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("finesse", "Finesse"),
        copies=1,
        # Plot: lose 1 Influence -> gain 1 Influence; -OR- Combat: 2 swords
        # [Steam app screen pieces]. The same Faction may be lost and gained
        # (imperium-base.md 16, [FAQ p. 4]); the cost resolves first.
        options=(
            _plot(
                EffectSection(costs=(LoseInfluence(1),), rewards=(GainInfluence(),))
            ),
            _combat(EffectSection(rewards=(GainCombatStrength(2),))),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("glimpse_the_path", "Glimpse the Path"),
        copies=1,
        # "Played Glimpse the Path and spent 1 spice to gain 1 water and draw
        # a card" [Glimpse the Path card, app log line; the card prints icons
        # only]: one Plot cost line, 1 spice -> 1 water and 1 card. The water
        # is always a live reward (OQ-071), so the line is played even with
        # no card left to draw.
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(spice=1),),
                    rewards=(GainResources(water=1), DrawPersonalCards(1)),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("grand_conspiracy", "Grand Conspiracy"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("ixian_probe", "Ixian Probe"),
        copies=1,
        # App screen pieces: [PLOT] Discard, Discard -> draw 2 cards.
        # Both hand cards must be available before playing, and both costs
        # precede the draw [Rise of Ix p. 7] [FAQ p. 2].
        options=(
            _plot(
                EffectSection(
                    costs=(DiscardFromHand(2),),
                    rewards=(DrawPersonalCards(2),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("machine_culture", "Machine Culture"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("quid_pro_quo", "Quid Pro Quo"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("second_wave", "Second Wave"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("secret_forces", "Secret Forces"),
        copies=1,
        # "If you have a seat on the High Council:" then two troops
        # [Steam app text and screen pieces]. The printed condition is
        # mandatory [FAQ p. 2]; a free recruit may fizzle (OQ-113 (C)).
        options=(
            _plot(
                EffectSection(condition=HasHighCouncil(), rewards=(RecruitTroops(2),))
            ),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("strategic_push", "Strategic Push"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("strongarm", "Strongarm"),
        copies=1,
        # "Lose a troop" -> "Gain one Influence with a Faction whose board
        # space you sent an Agent to this turn." [Steam app text]. The
        # existing visited-space gain names that Faction; without it the
        # cost line has no reward (rise-of-ix.md 9.3, OQ-071).
        options=(
            _plot(
                EffectSection(
                    costs=(LoseTroops(1),),
                    rewards=(GainInfluence(visited_space=True),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=ix_intrigue_card("war_chest", "War Chest"),
        copies=1,
    ),
)
