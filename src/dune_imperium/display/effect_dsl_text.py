"""English text for the Intrigue effect DSL primitives.

Wording follows the shared display contract: short imperative fragments, no
trailing period, resources lowercase, game terms capitalized as printed.
Every per-primitive renderer is an exhaustive ``match`` over its DSL union so
``mypy`` fails the moment a new primitive is added without matching text
support.
"""

from typing import assert_never

from dune_imperium.content.immortality.board import TLEILAXU_SETUP_SPICE
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireBankCommander,
    AcquireCardForSolari,
    AcquireCardUpTo,
    AcquiredCard,
    AcquireReserveCard,
    AcquireReserveCardToHand,
    AcquireTech,
    AcquireTleilaxuCard,
    AdvanceTleilaxu,
    AgentOnSpaceWithIcon,
    AllConditions,
    AllianceTaken,
    AtBoardSpace,
    AtFactionSpace,
    AtMakerSpace,
    BoostNextBeneGesseritCard,
    CommanderDiscountThisTurn,
    CommandersInConflictAtLeast,
    CommandReached,
    CompleteContract,
    CompletedContractsAtLeast,
    Condition,
    ContractCompletedThisTurn,
    ContractTaken,
    Cost,
    DeployFromGarrison,
    DeployFromSupply,
    DeployTheseTroops,
    DestroyShieldWall,
    DiscardedCardHasFaction,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    DrawTwistedIntrigueCards,
    DuringAgentTurn,
    EachOpponentDiscardsCard,
    EachOpponentLosesTroop,
    EffectSection,
    FactionBond,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    ForceEnemyRetreat,
    GainCombatStrength,
    GainedSpiceThisTurn,
    GainInfluence,
    GainInfluenceWhereAtMost,
    GainLowestInfluence,
    GainResources,
    GainSolariPerPartnerAgentIcon,
    GainSolariPerUnitType,
    GainSpiceWithHelixBonus,
    GainVictoryPoints,
    GarrisonedUnitsAtLeast,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    GiveIntrigueToOpponent,
    Grafted,
    GraftedTrash,
    GraftedWithFaction,
    GrantAgentIconsThisTurn,
    GrantAgentIconThisTurn,
    GrantCombatDeployment,
    HasAlliance,
    HasHighCouncil,
    HasSwordmaster,
    IgnoreInfluenceRequirementsThisTurn,
    InfluenceAtLeast,
    InfluenceAtLeastOnTracks,
    InNavigationSlot,
    IntrigueOption,
    IntrigueTiming,
    KeepPrintedReveal,
    LookAtIntrigueKeepOne,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    LoseHighestInfluence,
    LoseInfluence,
    LoseTroops,
    MoreSpiceMustFlowThanEachOpponent,
    OnAgentSentTo,
    OnBoardSpaceSolariPaid,
    OnCardTrashed,
    OnConflictWon,
    OnContractCompleted,
    OnHighCouncilSeatTaken,
    OnMakerSpiceHarvested,
    OnOpponentAgentAtSpiedMakerSpace,
    OnReachInfluence,
    OnRevealAcquisitionThisRound,
    OnRoundStart,
    OnSpiceGainedInTurnAtLeast,
    OnTroopsLostAtConflictEnd,
    OpponentAllianceInfluenceAtLeast,
    OpponentHasTroopInConflict,
    OpponentLosesTroop,
    OpponentPlayedCombatIntrigue,
    OpponentSandwormInConflict,
    OpponentsMoveSpiesFromVisitedSpace,
    PassTurn,
    PayResources,
    PeekTopCard,
    PermanentRevealPersuasion,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecallAgent,
    RecallOtherAgent,
    RecallSpy,
    RecruitToConflict,
    RecruitTroops,
    RecruitUndeployableTroops,
    RedirectSpiesOnTurnSpace,
    Research,
    RetreatTroops,
    ReturnOtherGraftedCardAtRevealStart,
    ReturnThisCardToHand,
    RevealContractsTakeOne,
    RevealCount,
    RevealCountKind,
    RevealPersuasion,
    RevealPersuasionThisRound,
    RevealSwords,
    Reward,
    SandwormsInConflictAtLeast,
    SetAsideImperiumRowCard,
    ShuffleDiscardIntoDeck,
    SolariAtLeast,
    SpendSpecimens,
    SpiceAtLeast,
    SpiceMustFlowCardsAtLeast,
    SpiesPlacedAtLeast,
    SpyingOnMakerSpace,
    SpyRecalledThisTurn,
    StrengthInConflictAtLeast,
    SummonSandworm,
    TakeContract,
    TakeControl,
    TakeHighCouncilSeat,
    TakeMentat,
    TakeSetupSpice,
    TakeSwordmaster,
    TechTilesAtLeast,
    TrashCard,
    TrashDiscardPileCard,
    TrashedCardHasFaction,
    TrashIntrigueCard,
    TrashPersonalCard,
    TrashThisCard,
    Trigger,
    TriggeredByFaction,
    TroopToMemory,
    UnitsDeployedThisTurnAtLeast,
    UnitsInConflictAtLeast,
    UseSignetAbility,
    VisitedSpaceHasIcon,
    WaterAtLeast,
)
from dune_imperium.content.uprising.intrigue import IntrigueCardEntry
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.types import BattleIcon

_FACTION_NAMES: dict[Faction, str] = {
    Faction.EMPEROR: "Emperor",
    Faction.SPACING_GUILD: "Spacing Guild",
    Faction.BENE_GESSERIT: "Bene Gesserit",
    Faction.FREMEN: "Fremen",
}

_BATTLE_ICON_NAMES: dict[BattleIcon, str] = {
    BattleIcon.CRYSKNIFE: "Crysknife",
    BattleIcon.DESERT_MOUSE: "Desert Mouse",
    BattleIcon.ORNITHOPTER: "Ornithopter",
    BattleIcon.WILD: "Wild",
}

_TURN_START = "At the start of your turn"

_TIMING_LABELS: dict[IntrigueTiming, str] = {
    IntrigueTiming.PLOT: "Plot",
    IntrigueTiming.COMBAT: "Combat",
    IntrigueTiming.ENDGAME: "Endgame",
}


def _acquirable_name(card_id: str) -> str:
    """An Imperium or Reserve card's name (a Contract's acquisition)."""

    from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
    from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID

    if card_id in IMPERIUM_CARDS_BY_ID:
        return IMPERIUM_CARDS_BY_ID[card_id].card.name
    if card_id in RESERVE_STACKS_BY_ID:
        return RESERVE_STACKS_BY_ID[card_id].card.name
    raise ValueError(f"unknown acquirable card id: {card_id!r}")


def _faction_name(faction: Faction) -> str:
    return _FACTION_NAMES[faction]


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _retreat_troops_text(troops: RetreatTroops) -> str:
    if troops.maximum is None:
        # Zero is a legal choice of an "any number" retreat [Main p. 20]
        # [FAQ p. 3]; the printed text is the same.
        if troops.minimum <= 1:
            return "Retreat any number of troops"
        return f"Retreat any number of troops (at least {troops.minimum})"
    if troops.minimum == troops.maximum:
        return f"Retreat {troops.minimum} {_plural(troops.minimum, 'troop')}"
    if troops.minimum == 0:
        # "Retreat up to three of your troops" [Master Tactician card]: zero
        # is a legal choice of an "up to" retreat [FAQ p. 3].
        return f"Retreat up to {troops.maximum} {_plural(troops.maximum, 'troop')}"
    return f"Retreat {troops.minimum}-{troops.maximum} troops"


def _gain_influence_text(gain: GainInfluence) -> str:
    if gain.visited_space:
        # "Gain two Influence instead of one." [Overthrow card], "gain two
        # Influence instead of one" [Subversive Advisor card] (``tokens.py``):
        # the box's gain replaces the visited space's 1 (OQ-046, OQ-128).
        more = "" if gain.replaces_space else " additional"
        return f"Gain {gain.times}{more} Influence with the visited Faction"
    if gain.factions is not None and len(gain.factions) == 1:
        return f"Gain {gain.times} {_faction_name(gain.factions[0])} Influence"
    if gain.factions is None:
        choice = "any Faction"
    else:
        choice = " or ".join(_faction_name(faction) for faction in gain.factions)
    # Twisted Ambitious: "a Faction where an opponent has more Influence than
    # you" [Twisted Ambitious card face].
    if gain.where_opponent_leads:
        choice = "a Faction where an opponent has more Influence than you"
    # Navigation card 1: "a different Faction ... where you have 2+
    # Influence" [Navigation Card 1 face].
    elif gain.different_from_trigger or gain.minimum_own:
        choice = "a different Faction" if gain.different_from_trigger else choice
        if gain.minimum_own:
            choice += f" where you have {gain.minimum_own}+ Influence"
    if gain.times == 1:
        return f"Gain 1 Influence (choose {choice})"
    if gain.one_faction:
        # The original game's two-chevron icon: one Faction, both Influence
        # [DI p. 16] (Grand Vision).
        return f"Gain {gain.times} Influence (choose {choice} once)"
    suffix = ", distinct" if gain.distinct else ""
    return f"Gain {gain.times} Influence (choose {choice} each time{suffix})"


def _place_spy_text(spy: PlaceSpy) -> str:
    if spy.visited_space:
        # Double Agent's card text (``tokens.py``).
        text = (
            "Place a Spy on a post connected to the space you sent an Agent to "
            "this turn"
        )
        if spy.shared_post:
            text += " (may share a post with another player's Spy)"
        return text
    if spy.shared_post:
        return "Place a Spy (may share another player's Spy's post)"
    if spy.factions is not None:
        names = " or ".join(_faction_name(faction) for faction in spy.factions)
        return f"Place a Spy ({names} Observation Post)"
    if spy.agent_icons is not None:
        names = " or ".join(
            icon.value.replace("_", " ").title() for icon in spy.agent_icons
        )
        return f"Place a Spy ({names} Observation Post)"
    return "Place a Spy"


def condition_text(condition: Condition) -> str:
    """Render one Intrigue condition as a clause that follows "If "."""

    match condition:
        case InfluenceAtLeast(faction=faction, amount=amount):
            return f"you have {amount} or more {_faction_name(faction)} Influence"
        case InfluenceAtLeastOnTracks(influence=influence, tracks=tracks):
            # "3 Influence (or more) on three Faction tracks" [Plans Within
            # Plans card, app text]; the card's own "or more" is the count's.
            noun = "track" if tracks == 1 else "tracks"
            return (
                f"you have {influence} or more Influence on at least {tracks}"
                f" Faction {noun}"
            )
        case HasHighCouncil():
            return "you hold a High Council seat"
        case HasAlliance(faction=faction):
            if faction is None:
                return "you have an Alliance"
            # "[Fremen] Alliance:" [Stillsuit Manufacturer card].
            return f"you have the {_faction_name(faction)} Alliance"
        case InNavigationSlot(slot=slot):
            return f"this is in Navigation slot {slot}"
        case TriggeredByFaction(faction=faction):
            return (
                "you played this as a result of reaching 2 Influence with the"
                f" {_faction_name(faction)}"
            )
        case SpiesPlacedAtLeast(count=count):
            return f"you have {count} or more Spies on Observation Posts"
        case CompletedContractsAtLeast(count=count):
            return f"you have completed {count} or more Contracts"
        case SandwormsInConflictAtLeast(count=1):
            # "If you have one or more sandworms in the Conflict:" [Devour
            # card face] [Ripples in the Sand card face] — the owner's own
            # sandworms, per effect_interpreter.py's owner-only check.
            return "you have one or more sandworms in the Conflict"
        case SandwormsInConflictAtLeast(count=count):
            return f"you have {count} or more sandworms in the Conflict"
        case GainedSpiceThisTurn(amount=amount):
            return f"you have gained {amount} or more spice this turn"
        case UnitsDeployedThisTurnAtLeast(count=count):
            # "When you deploy three or more units to the Conflict in a
            # single turn:" [Distraction card], a play condition (OQ-016).
            return f"you have deployed {count} or more units to the Conflict this turn"
        case SpiceMustFlowCardsAtLeast(count=count):
            return f"you own {count} or more copies of The Spice Must Flow"
        case MoreSpiceMustFlowThanEachOpponent():
            # "If you have more The Spice Must Flow than each opponent"
            # [Corner the Market card, app text]; a tie with any opponent fails.
            return "you own more copies of The Spice Must Flow than each opponent"
        case OpponentAllianceInfluenceAtLeast(amount=amount):
            return (
                f"you have {amount} or more Influence on a Faction track whose "
                "Alliance token an opponent holds"
            )
        case WaterAtLeast(amount=amount):
            return f"you have {amount} or more water"
        case CommandersInConflictAtLeast(count=count):
            return f"you have {count} or more Sardaukar Commanders in the Conflict"
        case TechTilesAtLeast(count=count):
            return f"you have {count} or more Tech tiles"
        case GeneticMarkersAtLeast(count=count):
            noun = "marker" if count == 1 else "markers"
            return f"you have reached {count} genetic {noun}"
        case SolariAtLeast(amount=amount):
            return f"you have {amount} or more solari"
        case SpiceAtLeast(amount=amount):
            return f"you have {amount} or more spice"
        case AtMakerSpace():
            # "If you are at a Maker space:" [Desert Power card].
            return "you are at a Maker space"
        case AtFactionSpace():
            # Never printed: a visited Faction's gain needs one (OQ-046).
            return "you are at a Faction space"
        case FactionBond(faction=faction):
            # "If Bene Gesserit Bond:" (display/tokens.py, Southern Elders).
            return f"{_faction_name(faction)} Bond"
        case SpyRecalledThisTurn():
            return "you recalled a Spy this turn"
        case UnitsInConflictAtLeast(count=count):
            return f"you have {count} or more units in the Conflict"
        case TrashedCardHasFaction(faction=faction):
            # Elite Forces (``tokens.py``).
            name = _faction_name(faction)
            article = "an" if name[0] in "AEIOU" else "a"
            return f"you trash {article} {name} card"
        case DiscardedCardHasFaction(faction=faction):
            # Space-time Folding, Guild Envoy (``tokens.py``).
            return f"the discarded card has {_faction_name(faction)} affiliation"
        case ContractCompletedThisTurn():
            return "you completed a Contract this turn"
        case GraftedWithFaction(factions=factions):
            # Interstellar Conspiracy (``tokens.py``).
            names = " or ".join(_faction_name(faction) for faction in factions)
            article = "an" if names[0] in "AEIOU" else "a"
            return f"grafted with {article} {names} card"
        case Grafted():
            return "grafted"
        case OpponentPlayedCombatIntrigue():
            return "an opponent played a Combat Intrigue card in this Conflict"
        case HasSwordmaster():
            return "you have your Swordmaster"
        case SpyingOnMakerSpace():
            return "you are spying on a Maker space"
        case GarrisonedUnitsAtLeast(count=count):
            return f"you have {count} or more garrisoned units"
        case DuringAgentTurn():
            # Quotes ``display/bloodlines.py``'s Rapid Dropships line.
            return "Agent Turn"
        case VisitedSpaceHasIcon(icon=icon):
            # Quotes ``display/tokens.py``'s "If you sent an Agent to a
            # Faction space this turn:" (Liet Kynes' Signet the same).
            name = icon.value.replace("_", " ").title()
            return f"you sent an Agent to a {name} space this turn"
        case StrengthInConflictAtLeast(amount=amount):
            # Quotes ``display/leaders.py``'s Gurney Halleck line.
            return f"you have {amount} or more strength in the Conflict"
        case AgentOnSpaceWithIcon(icon=icon):
            # Quotes ``display/bloodlines.py``'s Canny line.
            name = icon.value.replace("_", " ").title()
            article = "an" if name[0] in "AEIOU" else "a"
            return f"you have an Agent on {article} {name} board space"
        case OpponentSandwormInConflict():
            # Quotes ``display/bloodlines.py``'s Fierce line.
            return "any opponent has a sandworm in the Conflict"
        case OpponentHasTroopInConflict():
            return "an opponent has a troop in the Conflict"
        case CommandReached():
            return "Command (6+ Persuasion)"
        case AtBoardSpace(space_id=space_id):
            return f"Send an Agent to {BOARD_SPACES_BY_ID[space_id].name}"
        case AcquiredCard(card_id=card_id):
            return f"Acquire {_acquirable_name(card_id)}"
        case ContractTaken():
            return "Complete immediately when taken"
        case AllianceTaken():
            return "Take an Alliance token you do not already hold"
        case AllConditions(conditions=conditions):
            return " and ".join(condition_text(item) for item in conditions)
        case _:
            assert_never(condition)


def cost_text(cost: Cost) -> str:
    """Render one Intrigue cost."""

    match cost:
        case PayResources(solari=solari, spice=spice, water=water):
            parts = []
            if solari:
                parts.append(f"{solari} solari")
            if spice:
                parts.append(f"{spice} spice")
            if water:
                parts.append(f"{water} water")
            return "Pay " + ", ".join(parts)
        case LoseInfluence(count=count, one_faction=True):
            # "lose 2 Influence with one Faction" [For Humanity card].
            return f"Lose {count} Influence with one Faction"
        case LoseInfluence(count=count):
            return f"Lose {count} Influence"
        case LoseTroops(count=count, from_conflict=from_conflict):
            where = " in the Conflict" if from_conflict else ""
            return f"Lose {count} {_plural(count, 'troop')}{where}"
        case GiveIntrigueToOpponent(bonus_spice_if_not_twisted=bonus):
            extra = f" (+{bonus} spice if it is not a Twisted card)" if bonus else ""
            return f"Give an opponent an Intrigue card from your hand{extra}"
        case TrashIntrigueCard(troops_if_not_twisted=troops):
            extra = (
                f" (Recruit {_plural(troops, 'troop')} if it is not a Twisted card)"
                if troops
                else ""
            )
            return f"Trash an Intrigue card from your hand{extra}"
        case DiscardFromHand(count=1):
            return "Discard a card"
        case DiscardFromHand(count=count):
            return f"Discard {count} cards"
        case RecallSpy(count=1):
            return "Recall a Spy"
        case RecallSpy(count=count):
            return f"Recall {count} Spies"
        case RetreatTroops() as troops:
            return _retreat_troops_text(troops)
        case FlipBattleCard(icon=icon):
            # "Flip one of your face-up [icon] or [Wild] Conflict cards"
            # [Crysknife card face] [Desert Mouse card face] [Ornithopter
            # card face]; the interpreter accepts the named icon or Wild
            # (effect_interpreter.py), so every card naming one icon also
            # takes a Wild-icon card.
            icon_name = _BATTLE_ICON_NAMES[icon]
            return (
                f"Flip a face-up won Conflict card ({icon_name} or Wild icon)"
                " face down"
            )
        case FlipFaceUpConflictCard(count=1):
            return "Flip a face-up won Conflict card face down"
        case FlipFaceUpConflictCard(count=count):
            return f"Flip {count} face-up won Conflict cards face down"
        case TrashDiscardPileCard(minimum_cost=minimum_cost):
            return (
                f"Trash a card from your discard pile that costs {minimum_cost} or more"
            )
        case TrashCard(other_in_play=faction) if faction is not None:
            return f"Trash another {_faction_name(faction)} card in play"
        case TrashCard(grafted=GraftedTrash.OTHER):
            # "You may trash the other grafted card" [Dissecting Kit card].
            return "Trash the other grafted card"
        case TrashCard(grafted=GraftedTrash.EITHER):
            # "Trash one of the grafted cards" [Beguiling Pheromones card].
            return "Trash one of the grafted cards"
        case TrashCard(hand_only=True, faction=faction) if faction is not None:
            # "an Emperor card from your hand" [Treacherous Maneuver card].
            return f"Trash an {_faction_name(faction)} card from your hand"
        case TrashCard(hand_only=True):
            return "Trash a card from your hand"
        case TrashCard(this_card=True):
            return "Trash this card"
        case TrashCard():
            return "Trash a card"
        case SpendSpecimens(count=count):
            # "You may spend 1 specimen" [Organ Merchants card].
            return f"Spend {count} {_plural(count, 'specimen')}"
        case LoseFactionInfluence(faction=faction, count=count):
            # The Scouts costs quote ``display/scouts.py``'s step texts.
            return f"Lose {count} {faction.value.replace('_', ' ').title()} Influence"
        case LoseHighestInfluence():
            return "Lose 1 Influence with your highest Faction"
        case LoseGarrisonTroops(count=count):
            return f"Lose {count} troop{'s' if count > 1 else ''} from your garrison"
        case _:
            assert_never(cost)


def reward_text(reward: Reward) -> str:
    """Render one Intrigue reward."""

    match reward:
        case GainResources(solari=solari, spice=spice, water=water):
            parts = []
            if solari:
                parts.append(f"{solari} solari")
            if spice:
                parts.append(f"{spice} spice")
            if water:
                parts.append(f"{water} water")
            return "Gain " + ", ".join(parts)
        case GainVictoryPoints(amount=amount):
            return f"Gain {amount} VP"
        case RecruitTroops(count=count):
            return f"Recruit {count} {_plural(count, 'troop')}"
        case DrawPersonalCards(count=count):
            return f"Draw {count} {_plural(count, 'card')}"
        case ShuffleDiscardIntoDeck(draw=draw):
            return (
                "Shuffle your discard pile into your deck, then draw "
                f"{draw} {_plural(draw, 'card')}"
            )
        case DrawIntrigueCards(count=count):
            return f"Draw {count} Intrigue {_plural(count, 'card')}"
        case GainCombatStrength(amount=amount):
            return f"Gain {amount} {_plural(amount, 'sword')}"
        case GainInfluence() as gain:
            return _gain_influence_text(gain)
        case DestroyShieldWall():
            return "Destroy the Shield Wall"
        case SummonSandworm(count=count, requires_maker_hooks=requires_maker_hooks):
            text = f"Summon {count} {_plural(count, 'sandworm')}"
            if requires_maker_hooks:
                text += " (Maker Hooks required)"
            return text
        case DeployFromGarrison(up_to=up_to):
            # "Deploy up to N troops from your garrison to the Conflict"
            # [Detonation card face] [Counterattack card face] [Twisted
            # Devious card face] — the player may deploy fewer.
            if up_to is None:
                # "Deploy any number of your garrisoned troops to the
                # Conflict" [Rapid Mobilization card].
                return "Deploy any number of troops from your garrison to the Conflict"
            return (
                f"Deploy up to {up_to} {_plural(up_to, 'troop')} from your"
                " garrison to the Conflict"
            )
        case TrashPersonalCard(
            hand_only=hand_only,
            bonus_spice=bonus_spice,
            bonus_minimum_cost=bonus_minimum_cost,
        ):
            # Twisted Devious: "Trash a card from your hand" [Twisted
            # Devious card face]. Navigation card 5: "If you trash a card
            # that costs 1 or more: 2 spice" [Navigation Card 5 face].
            text = "Trash a card from your hand" if hand_only else "Trash a card"
            if bonus_spice:
                text += (
                    f"; if it costs {bonus_minimum_cost} or more: "
                    f"Gain {bonus_spice} spice"
                )
            return text
        case PlaceSpy() as spy:
            return _place_spy_text(spy)
        case RetreatTroops() as troops:
            return _retreat_troops_text(troops)
        case TakeContract(count=count):
            # Every Contract taken is a face-up one, as the cards print it
            # ("Take 1 face-up Contract", the personal cards' own text).
            return f"Take {count} face-up {_plural(count, 'Contract')}"
        case AcquireCardUpTo(max_cost=max_cost, to_hand_if=to_hand_if):
            if to_hand_if is None:
                return f"Acquire a card costing {max_cost} or less"
            return (
                f"Acquire a card costing {max_cost} or less "
                f"(to hand if {condition_text(to_hand_if)})"
            )
        case CommanderDiscountThisTurn(amount=amount):
            return (
                f"Recruiting a Sardaukar Commander (including when you acquire one) "
                f"costs you {amount} less this turn"
            )
        case IgnoreInfluenceRequirementsThisTurn():
            return (
                "Ignore Influence requirements on board spaces when sending an "
                "Agent this turn"
            )
        case GrantAgentIconThisTurn(icon=icon):
            return f"The card you play this turn has the {icon.value} icon"
        case GrantCombatDeployment():
            return "Combat: deploy this turn as though at a Combat space"
        case DeployTheseTroops():
            return "In your Reveal turn, you may deploy these troops to the Conflict"
        case GainSolariPerUnitType():
            return "Gain 1 solari for each type of unit you have in the Conflict"
        case PeekTopCard(draw_or_trash=True):
            return "Look at the top card of your deck: draw it or trash it"
        case PeekTopCard():
            return (
                "Look at the top card of your deck: put it back, discard it, or"
                " pay 1 solari to draw it"
            )
        case GrantAgentIconsThisTurn(icons=icons):
            names = ", ".join(icon.value for icon in icons)
            return f"The card you play this turn has the {names} icons"
        case PassTurn(optional=True):
            return "you may pass your turn"
        case PassTurn():
            return "At the start of your turn: pass your turn"
        case PermanentRevealPersuasion(amount=amount):
            return (
                f"For the rest of the game, during each of your Reveal turns,"
                f" {amount} Persuasion"
            )
        case AcquireReserveCard(card_id=card_id):
            return f"Acquire {card_id.replace('_', ' ').title()}"
        case AcquireTech(discount=0):
            return "Acquire a Tech tile"
        case AcquireTech(discount=discount):
            return f"Acquire a Tech tile ({discount} spice off)"
        case RedirectSpiesOnTurnSpace():
            return (
                "Each opponent spying on the board space where you sent an Agent "
                "this turn must move that Spy. Then place a Spy on that space"
            )
        case RevealContractsTakeOne(count=count):
            return f"Reveal {count} contracts from the bank: take one, trash the others"
        case SetAsideImperiumRowCard(discount=discount):
            return (
                "Set aside an Imperium Row card "
                f"({discount} Persuasion off for you this round)"
            )
        case Research():
            return "Research (advance your research token)"
        case AdvanceTleilaxu(count=1):
            return "Tleilaxu (advance your Tleilaxu token)"
        case AdvanceTleilaxu(count=count):
            return f"Tleilaxu ×{count} (advance your Tleilaxu token {count} spaces)"
        case GenerateSpecimens(count=count):
            return f"Generate {count} {_plural(count, 'specimen')}"
        case AcquireTleilaxuCard():
            return "You may acquire a Tleilaxu card (paying its specimen cost)"
        case RevealPersuasionThisRound(amount=amount):
            return f"Gain {amount} Persuasion during your Reveal turn this round"
        case ReturnThisCardToHand():
            return "Return this card to your hand"
        case BoostNextBeneGesseritCard():
            return (
                "The next Bene Gesserit card you play this round has all Agent"
                " icons and, added to its Agent box: Draw 1 card"
            )
        case DrawPerSandwormInConflict():
            return "Draw 1 card per sandworm in the Conflict"
        case LookAtIntrigueKeepOne(count=count):
            return (
                f"Look at the top {count} Intrigue cards, keep 1 and put the"
                f" {'other' if count == 2 else 'others'} back on top"
            )
        case ForceEnemyRetreat():
            return "Force an enemy troop to retreat"
        case PledgeFirstPlaceInfluence():
            return (
                "Add 1 Influence of your choice to this Conflict's first-place"
                " reward"
            )
        case AcquireCardForSolari():
            return (
                "Acquire an Imperium Row or Reserve card to your hand, paying"
                " its cost in solari"
            )
        case TrashThisCard():
            return "Trash this card"
        case RecallAgent(sent_this_turn=True, optional=optional):
            text = "recall the Agent you sent this turn"
            return f"You may {text}" if optional else text.capitalize()
        case RecallAgent():
            return "Recall 1 Agent"
        case EachOpponentDiscardsCard(count=None):
            return "Each opponent discards a card"
        case EachOpponentDiscardsCard(count=count):
            return f"Each opponent discards {count} cards"
        case EachOpponentLosesTroop(garrison_only=garrison_only):
            return (
                "Each opponent loses one garrisoned troop"
                if garrison_only
                else "Each opponent loses one troop"
            )
        case OpponentLosesTroop():
            return "An opponent of your choice loses one troop in the Conflict"
        case DeployFromSupply(count=count):
            return (
                f"Deploy {count} {_plural(count, 'troop')} from your supply to the"
                " Conflict"
            )
        case OpponentsMoveSpiesFromVisitedSpace():
            return (
                "Each opponent spying on the board space where you sent an"
                " Agent this turn must move that Spy"
            )
        case KeepPrintedReveal(value=value):
            # "Keep the Persuasion" [Desert Power card], "Keep the spice"
            # [Priority Contracts card] (``tokens.py``).
            return f"Keep the {'Persuasion' if value == 'persuasion' else 'spice'}"
        case GainSolariPerPartnerAgentIcon():
            # Slig Farmer's card text (``tokens.py``).
            return "Gain 1 solari per Agent icon on the other grafted card"
        case ReturnOtherGraftedCardAtRevealStart():
            return (
                "At the start of your Reveal turn, return the other grafted"
                " card from play to your hand"
            )
        case AcquireBankCommander():
            return "Acquire and recruit the Sardaukar Commander in the bank"
        case RevealPersuasion(amount=amount, per=per):
            return f"+{amount} Persuasion{_reveal_count_text(per)}"
        case RevealSwords(amount=amount, per=per):
            return f"+{amount} {_plural(amount, 'sword')}{_reveal_count_text(per)}"
        case TakeHighCouncilSeat():
            return "Take the High Council seat"
        case TakeControl(space_id=space_id):
            return f"Take control of {BOARD_SPACES_BY_ID[space_id].name}"
        case TakeSwordmaster():
            return "Take your third Agent, usable from this round"
        case TakeMentat():
            # The original game's Mentat icon [DI p. 16].
            return "Take the Mentat from its space"
        case UseSignetAbility():
            # Quotes ``display/bloodlines.py``'s Servo-Receivers acquire line.
            return "Use your Leader's Signet Ring ability"
        case GainInfluenceWhereAtMost(maximum=maximum):
            # Quotes ``display/bloodlines.py``'s Panopticon line.
            return (
                "Gain 1 Influence with each Faction where you have "
                f"{maximum} or less Influence"
            )
        case RecruitUndeployableTroops(count=count):
            # Quotes ``display/leaders.py``'s Piter De Vries Signet line.
            them = "this troop" if count == 1 else "these troops"
            return (
                f"Recruit {count} {_plural(count, 'troop')}; you can't deploy"
                f" {them} to the Conflict this turn"
            )
        case TroopToMemory():
            # Quotes ``display/leaders.py``'s Lady Jessica Signet line.
            return (
                "Move 1 troop from your supply to the Bene Gesserit board area"
                " as a memory"
            )
        case DrawTwistedIntrigueCards(count=count):
            # Quotes ``display/leaders.py``'s Piter De Vries line.
            if count == 1:
                return "Draw a Twisted Intrigue card"
            return f"Draw {count} Twisted Intrigue cards"
        case TakeSetupSpice():
            # Quotes ``server/static/labels_en.js``'s Tleilaxu track label.
            return f"First to reach: {TLEILAXU_SETUP_SPICE} spice"
        case RecallOtherAgent():
            # The Scouts rewards quote ``display/scouts.py``'s step texts.
            return "Recall another of your Agents"
        case RecruitToConflict(count=count):
            return f"Put {count} troop{'s' if count > 1 else ''} into the Conflict"
        case AcquireReserveCardToHand(card_id=card_id):
            return f"Acquire {RESERVE_STACKS_BY_ID[card_id].card.name} to your hand"
        case GainLowestInfluence():
            return "+1 Influence with your lowest Faction"
        case GainSpiceWithHelixBonus(spice=spice, helix_spice=helix):
            return f"Gain {spice} spice ({helix} once you reach the Helix)"
        case CompleteContract():
            return "Complete one of your contracts"
        case _:
            assert_never(reward)


def trigger_text(trigger: Trigger) -> str:
    """Render one Intrigue trigger as a clause introducing the option line."""

    match trigger:
        case OnRevealAcquisitionThisRound():
            return "Whenever you acquire a card during your Reveal turn this round"
        case OnTroopsLostAtConflictEnd(minimum=minimum):
            return f"When you lose {minimum} or more troops at the end of a Conflict"
        # The Leaders' and Tech tiles' triggers quote ``display/leaders.py``
        # and ``display/bloodlines.py``.
        case OnReachInfluence(faction=faction, amount=amount):
            return f"When you reach {amount} {_faction_name(faction)} Influence"
        case OnOpponentAgentAtSpiedMakerSpace():
            return (
                "Whenever another player sends an Agent to a Maker board space you"
                " are spying on"
            )
        case OnCardTrashed():
            return "Whenever you trash a card"
        case OnAgentSentTo(space_id=space_id, opponent=opponent):
            who = "an opponent sends" if opponent else "you send"
            return f"Whenever {who} an Agent to {BOARD_SPACES_BY_ID[space_id].name}"
        case OnRoundStart():
            return "Round start"
        case OnSpiceGainedInTurnAtLeast(amount=amount):
            return f"Whenever you gain {amount} or more spice in a single turn"
        case OnContractCompleted():
            return "When you complete a contract"
        case OnConflictWon():
            return "When you win a Conflict"
        case OnBoardSpaceSolariPaid():
            return "Whenever you pay Solari for a board space's cost"
        case OnHighCouncilSeatTaken():
            return "When you take a seat on the High Council"
        case OnMakerSpiceHarvested():
            return "Whenever you harvest spice at a Maker space"
        case _:
            assert_never(trigger)


def section_text(section: EffectSection) -> str:
    """Render one printed Intrigue line: an optional condition, costs, rewards."""

    rewards = ", ".join(reward_text(reward) for reward in section.rewards)
    if section.costs:
        costs = ", ".join(cost_text(cost) for cost in section.costs)
        body = f"{costs} → {rewards}"
    else:
        body = rewards
    if section.condition is not None:
        return f"If {condition_text(section.condition)}: {body}"
    return body


def option_text(option: IntrigueOption, *, show_timing: bool = True) -> str:
    """Render one Intrigue option, prefixed by its timing.

    A triggered option (``option.trigger`` set) never resolves when played;
    its trigger clause introduces the sections that fire later instead.
    ``show_timing`` is false for Steersman Y'rkoon's Navigation cards: their
    faces print no Plot/Combat/Endgame banner (they are played automatically
    by Plot Course, not chosen by timing) [Navigation card faces].
    """

    body = "; ".join(section_text(section) for section in option.sections)
    if option.trigger is not None:
        body = f"{trigger_text(option.trigger)}: {body}"
    if option.turn_start_only and not body.startswith(_TURN_START):
        # A card that names its moment in no effect of its own (Bindu
        # Suspension's draw and optional pass).
        body = f"{_TURN_START}: {body}"
    if not show_timing:
        return body
    return f"{_TIMING_LABELS[option.timing]} — {body}"


def intrigue_card_text(entry: IntrigueCardEntry) -> list[str]:
    """Render one line of English text per printed Intrigue option.

    A Navigation card prints no timing banner -- Plot Course plays it when
    its owner reaches 2 Influence [Steersman Y'rkoon card] -- so its lines
    carry no timing prefix.
    """

    return [
        option_text(option, show_timing=not entry.navigation)
        for option in entry.options
    ]


def _reveal_count_text(per: RevealCount | None) -> str:
    """What a Reveal gain is counted per, as ``tokens.reveal_effect_text``
    prints it."""

    if per is None:
        return ""
    match per.kind:
        case RevealCountKind.REVEALED_FACTION_CARD:
            assert per.faction is not None
            return f" per revealed {_faction_name(per.faction)} card"
        case RevealCountKind.FACTION_CARD_IN_PLAY:
            assert per.faction is not None
            return f" per {_faction_name(per.faction)} card in play"
        case RevealCountKind.COMPLETED_CONTRACT:
            return " per completed Contract"
        case RevealCountKind.OTHER_SWORD_CARD:
            return " per other revealed sword card"
