"""The original game's Intrigue cards (stage P3).

docs/base-game-and-ix-plan.md 16: 34 kinds, 40 cards [DI p. 3]. Per D1
(plan 2.4) the printed effects come from the Steam app's screen pieces and
English text; the rules behind them are docs/rules/imperium-base.md, the
Plot / Combat / Endgame timings [DI pp. 13-14] those of Uprising.

Every card has an entry from stage P3a on; one not yet transcribed has no
options. The original game's Intrigue deck takes the transcribed ones
(``rulesets``), and the observation lists them all from v37 (plan 16.1,
16.4). ``content.uprising.intrigue``'s ``INTRIGUE_CARDS_BY_ID`` and
``INTRIGUE_CARDS_BY_INSTANCE`` resolve them; code that lists Uprising's own
cards iterates ``INTRIGUE_CARDS`` instead.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireToDeckTopThisRound,
    DeployFromGarrison,
    DeployFromSupply,
    DeployTheseTroops,
    DrawPersonalCards,
    EffectSection,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GrantAgentIconsThisTurn,
    HasAlliance,
    HasHighCouncil,
    InfluenceAtLeastOnTracks,
    IntrigueOption,
    IntrigueTiming,
    LoseTroops,
    MoreSpiceMustFlowThanEachOpponent,
    OnConflictWon,
    OpponentHasTroopInConflict,
    OpponentLosesTroop,
    PassTurn,
    PayResources,
    PeekTopCard,
    RecruitTroops,
    RetreatTroops,
    RevealPersuasionThisRound,
    ShuffleDiscardIntoDeck,
    SpiceMustFlowCardsAtLeast,
)
from dune_imperium.content.uprising.intrigue import (
    IntrigueCardEntry,
    _combat,
    _combat_trigger,
    _endgame,
    _plot,
)
from dune_imperium.content.uprising.types import AgentIcon

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
        # "If you have a Faction Alliance: 2 spice -> +7 swords" [Allied
        # Armada card, app text]: a Combat cost line under a condition; an
        # Alliance with any Faction counts and both the Alliance and the two
        # spice are needed to play it (imperium-base.md 13.3, FAQ p. 2).
        options=(
            _combat(
                EffectSection(
                    condition=HasAlliance(),
                    costs=(PayResources(spice=2),),
                    rewards=(GainCombatStrength(7),),
                )
            ),
        ),
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
        # "At the start of your turn: [draw 1]. You may pass your turn.
        # (Instead of taking an Agent or Reveal turn.)" [Bindu Suspension
        # card, app text]: OQ-117 (user ruling C, 2026-10-22). It is played
        # only as the first action of the turn, before anything else is done
        # (imperium-base.md 13.1: "차례 시작의 첫 행동으로만 낸다. 다른 행동을
        # 하면 사용할 수 없다", the OQ-095 (6) turn-start rule Withdrawn
        # shares: ``turn_start_only``), also in a turn the seat must reveal.
        # The card draws, then "you may choose to pass your turn or play your
        # turn normally" (13.3): the pass is the owner's choice after the draw
        # (``PassTurn.optional``) and is not forced. A pass sends no Agent, so
        # it uses up no block of The Voice (OQ-116).
        options=(
            IntrigueOption(
                timing=IntrigueTiming.PLOT,
                sections=(
                    EffectSection(
                        rewards=(DrawPersonalCards(1), PassTurn(optional=True))
                    ),
                ),
                turn_start_only=True,
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("bypass_protocol", "Bypass Protocol"),
        copies=1,
        # "Acquire a card that costs [Persuasion 3] or less." -OR- "[2 spice]
        # -> Acquire a card that costs [Persuasion 5] or less to the top of
        # your deck." [Bypass Protocol card, app text]: two exclusive Plot
        # options (OQ-058; imperium-base.md 16 lists the card among the -OR-
        # cards). "A card that costs N or less" is the Imperium Row's five
        # cards and the Reserve's Arrakis Liaison and The Spice Must Flow,
        # never Foldspace [DI p. 11] [FAQ p. 2] (OQ-125, decided 2026-10-23:
        # ``AcquireCardUpTo``, Impress's piece). The first option has no
        # cost, so it is played even with nothing to acquire (OQ-113 (C),
        # imperium-base.md 16); the second is a cost line, played only with
        # two spice and a card of cost 5 or less to take (OQ-071). The card
        # goes on top of the deck, placed before its acquire box resolves
        # (``to_deck_top``); the top of the deck is as hidden as any deck
        # card (imperium-base.md 14).
        options=(
            _plot(EffectSection(rewards=(AcquireCardUpTo(3),))),
            _plot(
                EffectSection(
                    costs=(PayResources(spice=2),),
                    rewards=(AcquireCardUpTo(5, to_deck_top=True),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("choam_shares", "CHOAM Shares"),
        copies=1,
        # "7 Solari -> 1 Victory Point" [CHOAM Shares card, app text]: a cost
        # arrow line, required once the card is played [FAQ p. 3]; "pay its
        # costs" [FAQ p. 2] (imperium-base.md 13.3).
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=7),),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("calculated_hire", "Calculated Hire"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("charisma", "Charisma"),
        copies=1,
        # "Gain 2 Persuasion during your Reveal turn this round" [Charisma
        # card, app text]: Persuasion that waits for the owner's Reveal turn,
        # so the played card stays face up until that turn ends [FAQ p. 2]
        # (the shape of Immortality's Tleilaxu Puppet). It is played without
        # spending the Persuasion (imperium-base.md 13.3).
        options=(_plot(EffectSection(rewards=(RevealPersuasionThisRound(2),))),),
    ),
    IntrigueCardEntry(
        card=intrigue_card("corner_the_market", "Corner the Market"),
        copies=1,
        # "If you have at least two The Spice Must Flow: 1 VP" and "If you have
        # more The Spice Must Flow than each opponent: 1 VP" [Corner the Market
        # card, app text]: two stacked Endgame lines, each its own 1 VP
        # (imperium-base.md 13.2: "두 조건은 따로 1 VP씩"; OQ-058). The copies
        # are every one the seat owns, deck, hand, discard pile and play area
        # (OQ-123), and an opponent with as many fails the second line
        # (`[FAQ p. 2]`: each opponent separately).
        options=(
            _endgame(
                EffectSection(
                    condition=SpiceMustFlowCardsAtLeast(2),
                    rewards=(GainVictoryPoints(1),),
                ),
                EffectSection(
                    condition=MoreSpiceMustFlowThanEachOpponent(),
                    rewards=(GainVictoryPoints(1),),
                ),
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("councilors_dispensation", "Councilor's Dispensation"),
        copies=1,
        # "If you have a seat on the High Council: +2 spice" [Councilor's
        # Dispensation card, app text]: the seat is a condition the official
        # documents set (FAQ p. 2's example), so without it the card is not
        # played (OQ-113 (C); Uprising's Councilor's Ambition has this shape).
        options=(
            _plot(
                EffectSection(
                    condition=HasHighCouncil(),
                    rewards=(GainResources(spice=2),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("demand_respect", "Demand Respect"),
        copies=1,
        # "When you win a Conflict:" then "1 Influence (any Faction) -OR-
        # 2 spice -> 2 Influence" [Demand Respect card, app text]: a winning
        # Intrigue, played from the hand in the sole winner's reward window
        # [DI p. 12] (OQ-121), never in a Combat Intrigue round, and two
        # exclusive options (OQ-058). The two chevrons are one Faction's two
        # Influence [DI p. 16] ("you can't choose two different Factions");
        # the spice may be the reward's own [DI p. 13] (imperium-base.md 13.1)
        # and the arrow's line needs a live reward (OQ-113 (C)); a Faction at
        # the top of its track is not offered (OQ-060).
        options=(
            _combat_trigger(OnConflictWon(), EffectSection(rewards=(GainInfluence(),))),
            _combat_trigger(
                OnConflictWon(),
                EffectSection(
                    costs=(PayResources(spice=2),),
                    rewards=(GainInfluence(times=2, one_faction=True),),
                ),
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("dispatch_an_envoy", "Dispatch an Envoy"),
        copies=2,
        # "The card you play this turn has the following icons: Emperor,
        # Spacing Guild, Bene Gesserit, Fremen" [Dispatch an Envoy card, app
        # text]: the four Faction Agent icons added to the card, none
        # removed and none repeated [FAQ p. 2] -- Resourceful's shape with
        # other icons. A cost-free Plot, played even after the Agent is sent
        # or in the Reveal turn (OQ-113 (C), (3); imperium-base.md 13.3).
        options=(
            _plot(
                EffectSection(
                    rewards=(
                        GrantAgentIconsThisTurn(
                            (
                                AgentIcon.EMPEROR,
                                AgentIcon.SPACING_GUILD,
                                AgentIcon.BENE_GESSERIT,
                                AgentIcon.FREMEN,
                            )
                        ),
                    )
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("double_cross", "Double Cross"),
        copies=1,
        # "1 Solari -> An opponent of your choice loses one troop in the
        # Conflict and you deploy one troop from your supply to the
        # Conflict." [Double Cross card, app text]: a cost arrow line [DI
        # p. 16], paid once played [FAQ p. 2]. "상대 하나 이상이 Conflict에
        # troop이 있어야 낸다; 내 supply는 비어도 된다" `[FAQ p. 2]`
        # (imperium-base.md 13.2, 16): the opponent's troop is an official
        # condition of the card, the empty supply is not one (the deployment
        # then deploys nothing). The lost troop returns to its owner's supply
        # [DI p. 16]; the two icons are independent effects in the owner's
        # order (OQ-015).
        options=(
            _plot(
                EffectSection(
                    condition=OpponentHasTroopInConflict(),
                    costs=(PayResources(solari=1),),
                    rewards=(OpponentLosesTroop(), DeployFromSupply(1)),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("favored_subject", "Favored Subject"),
        copies=1,
        # "+1 Emperor Influence" [Favored Subject card, app text]: a cost-free
        # Plot naming its Faction, so it is played even with the Emperor track
        # at the top and then gains nothing (OQ-113 (C), imperium-base.md
        # 13.3's Know Their Ways row).
        options=(
            _plot(EffectSection(rewards=(GainInfluence(factions=(Faction.EMPEROR,)),))),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("guild_authorization", "Guild Authorization"),
        copies=1,
        # "+1 Spacing Guild Influence" [Guild Authorization card, app text]:
        # a cost-free Plot naming its Faction, played even with the Spacing
        # Guild track at the top and then gaining nothing (OQ-113 (C),
        # imperium-base.md 13.3).
        options=(
            _plot(
                EffectSection(
                    rewards=(GainInfluence(factions=(Faction.SPACING_GUILD,)),)
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("infiltrate", "Infiltrate"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("know_their_ways", "Know Their Ways"),
        copies=1,
        # "+1 Fremen Influence" [Know Their Ways card, app text]: a cost-free
        # Plot naming its Faction. The designer ruling that it is played with
        # the Fremen track at the top (the effect then fizzles) is OQ-113
        # (3), imperium-base.md 13.3.
        options=(
            _plot(
                EffectSection(rewards=(GainInfluence(factions=(Faction.FREMEN,)),))
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("plans_within_plans", "Plans Within Plans"),
        copies=1,
        # "3 Influence (or more) on three Faction tracks: 1 VP -OR- ... on four
        # Faction tracks: 2 VP" [Plans Within Plans card, app text]: two
        # exclusive Endgame options, each carrying its own condition
        # (OQ-058: "—OR—로 나뉜 카드는 그대로 배타 option", imperium-base.md
        # 16, so at most 2 VP). "Influence 3 = VP 칸 바로 위 칸" (13.2).
        options=(
            _endgame(
                EffectSection(
                    condition=InfluenceAtLeastOnTracks(3, 3),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
            _endgame(
                EffectSection(
                    condition=InfluenceAtLeastOnTracks(3, 4),
                    rewards=(GainVictoryPoints(2),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("poison_snooper", "Poison Snooper"),
        copies=2,
        # "Look at the top card of your deck. Draw or trash it." [Poison
        # Snooper card, app text]: a cost-free Plot whose one choice is
        # mandatory -- no "may", and the black trash icon is not printed,
        # the card says "trash it" in words (P0 sheet; imperium-base.md 15
        # "Poison Snooper | 낸 좌석 | 뽑기 -OR- trash"). Only the playing seat
        # is told the card (imperium-base.md 14), through the same private
        # ``peeked_card_id`` Controlled uses; "덱이 비면 맨 위를 볼 수 없다"
        # (13.1), so with an empty deck the cost-free look is played and
        # fizzles (OQ-113 (C) (1), the empty-deck Controlled's ruling (2) 7).
        # A card drawn in the Reveal turn is revealed at once [FAQ p. 3]
        # (13.2 "Poison Snooper → Reveal turn").
        options=(_plot(EffectSection(rewards=(PeekTopCard(draw_or_trash=True),))),),
    ),
    IntrigueCardEntry(
        card=intrigue_card("private_army", "Private Army"),
        copies=2,
        # "2 spice -> +5 swords" [Private Army card, app text]: a Combat cost
        # line, paid once the card is played [FAQ p. 3] (imperium-base.md
        # 13.3's Allied Armada row, the same shape).
        options=(
            _combat(
                EffectSection(
                    costs=(PayResources(spice=2),),
                    rewards=(GainCombatStrength(5),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("rapid_mobilization", "Rapid Mobilization"),
        copies=1,
        # "Deploy any number of your garrisoned troops to the Conflict"
        # [Rapid Mobilization card, app text]: a cost-free Plot. "Any number"
        # allows zero [FAQ p. 3], and a cost-free effect is played even with
        # an empty garrison (OQ-113 (C), (2) 1; imperium-base.md 13.3).
        options=(_plot(EffectSection(rewards=(DeployFromGarrison(up_to=None),))),),
    ),
    IntrigueCardEntry(
        card=intrigue_card("recruitment_mission", "Recruitment Mission"),
        copies=1,
        # "Gain [Persuasion 1] during your Reveal turn this round." and "You
        # may put cards you acquire on top of your deck." [Recruitment
        # Mission card, app text]: one cost-free Plot whose whole effect
        # waits for the owner's Reveal turn this round [FAQ p. 2], so the
        # played card stays face up until that turn ends (Charisma's and
        # Tleilaxu Puppet's shape, ``waits_for_reveal_turn``). For each card
        # acquired the owner chooses top of the deck or the discard pile
        # [FAQ p. 3] (imperium-base.md 13.2); the option is not retroactive:
        # a card acquired before the Plot was played is unaffected (13.3).
        options=(
            _plot(
                EffectSection(
                    rewards=(RevealPersuasionThisRound(1), AcquireToDeckTopThisRound())
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("refocus", "Refocus"),
        copies=1,
        # "Shuffle your discard pile into your deck, then: [draw 1]" [Refocus
        # card, app text]: a cost-free Plot, so it is played even with both
        # piles empty and then fizzles (OQ-113 (C)). The deck is shuffled
        # along with the discard pile -- "discard가 비었으면 덱을 섞는다"
        # [FAQ p. 3] (imperium-base.md 13.2) -- and nobody learns an order:
        # the shuffle is a chance step (imperium-base.md 14, "Refocus |
        # 아무도 | — | 섞기").
        options=(_plot(EffectSection(rewards=(ShuffleDiscardIntoDeck(1),))),),
    ),
    IntrigueCardEntry(
        card=intrigue_card("reinforcements", "Reinforcements"),
        copies=1,
        # "3 Solari -> 3 troops. If it's your Reveal turn, you may deploy any
        # of these troops to the Conflict." [Reinforcements card, app text]: a
        # cost arrow line [DI p. 16] whose recruit is as many as the supply
        # holds (OQ-030); in an Agent turn the troops deploy by the Combat
        # space rule [FAQ p. 4] (``DeployTheseTroops``).
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=3),),
                    rewards=(RecruitTroops(3), DeployTheseTroops()),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("secret_of_the_sisterhood", "Secret of the Sisterhood"),
        copies=1,
        # "+1 Bene Gesserit Influence" [Secret of the Sisterhood card, app
        # text]: a cost-free Plot naming its Faction, played even with the
        # Bene Gesserit track at the top and then gaining nothing (OQ-113
        # (C), imperium-base.md 13.3).
        options=(
            _plot(
                EffectSection(
                    rewards=(GainInfluence(factions=(Faction.BENE_GESSERIT,)),)
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("staged_incident", "Staged Incident"),
        copies=1,
        # "Lose three of your troops in the Conflict -> 1 Victory Point"
        # [Staged Incident card, app text]: the loss is the cost, so all
        # three must be in the Conflict to play it [FAQ p. 2]; the strength
        # marker moves down with them [FAQ p. 4] (imperium-base.md 13.2).
        options=(
            _combat(
                EffectSection(
                    costs=(LoseTroops(3, from_conflict=True),),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("the_sleeper_must_awaken", "The Sleeper Must Awaken"),
        copies=1,
        # "4 spice -> 1 Victory Point" [The Sleeper Must Awaken card, app
        # text]: a cost arrow line, required once played [FAQ p. 3].
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(spice=4),),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("tiebreaker", "Tiebreaker"),
        copies=1,
        # "Combat: +2 swords -OR- Endgame: +10 spice" [Tiebreaker card, app
        # text]: one card, two exclusive options (OQ-058), a Combat face and
        # an Endgame face, neither with a cost. Spice is the first Endgame
        # tiebreaker [DI p. 13] (imperium-base.md 10, 16).
        options=(
            _combat(EffectSection(rewards=(GainCombatStrength(2),))),
            _endgame(EffectSection(rewards=(GainResources(spice=10),))),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("to_the_victor", "To the Victor..."),
        copies=1,
        # "When you win a Conflict: 3 spice" [To the Victor... card, app
        # text]: a cost-free winning Intrigue, played from the hand in the
        # sole winner's reward window [DI p. 12] (OQ-121); it may be played
        # at once when the Conflict reward drew it [FAQ p. 4] and its spice
        # may pay Demand Respect (imperium-base.md 13.1).
        options=(
            _combat_trigger(
                OnConflictWon(), EffectSection(rewards=(GainResources(spice=3),))
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("urgent_mission", "Urgent Mission"),
        copies=1,
    ),
    IntrigueCardEntry(
        card=intrigue_card("water_peddlers_union", "Water Peddlers Union"),
        copies=1,
        # "+1 water" [Water Peddlers Union card, app text]: a cost-free Plot.
        options=(_plot(EffectSection(rewards=(GainResources(water=1),))),),
    ),
    IntrigueCardEntry(
        card=intrigue_card("water_of_life", "Water of Life"),
        copies=1,
        # "1 water + 1 spice -> draw 3 cards" [Water of Life card, app text]:
        # one cost line paying both resources, so a draw with both piles
        # empty is a cost with no live reward and the card is not played
        # (OQ-113 (C), imperium-base.md 13.3).
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(water=1, spice=1),),
                    rewards=(DrawPersonalCards(3),),
                )
            ),
        ),
    ),
    IntrigueCardEntry(
        card=intrigue_card("windfall", "Windfall"),
        copies=1,
        # "+2 Solari" [Windfall card, app text]: a cost-free Plot.
        options=(_plot(EffectSection(rewards=(GainResources(solari=2),))),),
    ),
)
