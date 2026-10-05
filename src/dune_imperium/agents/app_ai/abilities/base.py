"""Base of every ability port: the defaults of ``WormAbilityDefinition``.

Each app ability class the AI touches gets a port class registered under its
full app class name with ``@port(...)``. Ports mirror the app's inheritance
(``TrashAgentAbility`` -> ``TrashAbility`` -> ``DeferredAbility`` -> ...), so
an override inherited in the app is inherited here too. A class without a
port behaves like ``WormAbilityDefinition``: value 0, never chosen on an
optional prompt; ``UNPORTED`` counts such lookups so coverage can be checked.

Hook names follow the app (snake_case): ``value_for_player``
(``ValueForPlayer``), ``evaluate`` (``Evaluate``),
``value_in_pile_for_other_play`` (``ValueInPileForOtherPlay``),
``specific_acquire_value`` (``SpecificAcquireValue``), plus the engine-side
members the AI depends on (``DeferValue``, ``SelectionMode``,
``CanRunImmediately``, ``AbilityTiming``).
"""

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile


class SelectionMode(IntEnum):
    """``DeferredAbility.SelectionMode`` (app enum values)."""

    OPTIONAL = 0
    WARN = 1
    IMPLICIT = 2
    EXPLICIT = 3


class Timing(IntEnum):
    """``AbilityTiming`` (app enum values as stored in the ``.ctor`` chains)."""

    NONE = 0
    AGENT = 1
    REVEAL = 2
    COMBAT_RESOLUTION = 3
    ENDGAME = 4  # ``ChaumurkyAbility..ctor`` (rix-tech.md §8.2); Endgame halves
    COMBAT = 5


class Pile(StrEnum):
    """Where ``ValueInPileForOtherPlay`` looks (the app passes a zone)."""

    DECK = "deck"  # every owned card (GetSynergyMod passes player.Deck)
    PLAY_AREA = (
        "play_area"  # cards in play this turn (AgentAbility's Imperium Play Bonus)
    )


@dataclass(frozen=True, slots=True)
class TargetInfo:
    """One target information of a prompt, as the app's evaluators see it.

    ``entities`` are the valid entities in the app's order; ``options`` the
    custom-choice indices offered. ``min_select``/``max_select`` follow the
    app's ``EntityListTargetInformation`` (``NumberToSelect`` is the max).
    """

    entities: tuple[Entity, ...] = ()
    options: tuple[int, ...] = ()
    min_select: int = 0
    max_select: int = 1
    forced: bool = False


@dataclass(frozen=True, slots=True)
class Request:
    """The prompt an ``evaluate`` answers: the ability's target infos."""

    infos: tuple[TargetInfo, ...] = ()
    forced: bool = False


type ResponseItem = tuple[str | int, ...]


@dataclass(frozen=True, slots=True)
class Answer:
    """``WormAIChoiceSelectionWithTargets``: a value and the response.

    ``response`` holds one item per target info: the chosen entity refs or
    option indices, in order. ``response is None`` is the app's empty
    response (choose nothing / decline). A value of 0 or less is never
    chosen on an optional prompt.
    """

    value: float
    response: tuple[ResponseItem, ...] | None = None
    label: str = ""


class Ability:
    """Port of ``worm.canis.abilities.WormAbilityDefinition`` (defaults)."""

    APP_CLASS: ClassVar[str] = "worm.canis.abilities.WormAbilityDefinition"

    def __init__(self, owner: Entity) -> None:
        self.owner = owner

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.owner.ref!r})"

    # -- AI hooks -------------------------------------------------------------------

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer`` @0x4a88470: empty by default."""

        return Summer()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``Evaluate`` @0x4a88ef0: an empty choice worth 0 by default."""

        return Answer(0.0, None, f"{type(self).__name__} default")

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``WormAbilityDefinition::ValueInPileForOtherPlay`` @0x4a88480.

        Spec ``generic-abilities.md`` §1.1 (re-read in the disassembly). The
        default tag synergy: ``self.owner`` is the card (intrigue, contract)
        that carries this ability, ``card`` the candidate. ``GetSynergyMod``
        calls it with ``Pile.DECK`` once per ability object of every owned
        card; ``AgentAbility``'s "Imperium Play Bonus" calls it with
        ``Pile.PLAY_AREA``, where the default adds nothing. The three
        ``multiply`` calls scale only the terms this call added so far.
        """

        s = Summer()
        if pile is not Pile.DECK:  # vslot 31 ``pile.Is(EntityNames.Deck)``
            return s
        c = p.C
        owner_tags = self.owner.list_attr("Tags")
        card_tags = card.list_attr("Tags")
        if "WantTSMF" in owner_tags:
            # ``WormEntityExtensions::IsTheSpiceMustFlowImperium`` @0x482f1b0:
            # an Imperium playable whose ArchID is either TSMF archetype.
            if card.kind == "card" and card.short in (
                "ImperiumArchetypes.BaseSet.TheSpiceMustFlow",
                "ImperiumArchetypes.Uprising.TheSpiceMustFlowUP",
            ):
                s.add("TSMF CardValue", c.SynergyTSMFCardValue)
            persuasion = card.int_attr("Persuasion")
            if persuasion >= 2:  # ``cmp eax, 2; jl`` -> taken when >= 2
                s.add("CTM High Persuasion Granted", c.SynergyTSMFHighPersuasionValue)
            # ``cmp eax, 2; jg`` then ``cmp PersuasionCost, 7; jle``: both non-strict.
            if persuasion <= 2 and card.int_attr("PersuasionCost") <= 7:
                s.add("CTM Low Persuasion High Cost", -c.SynergyTSMFHighPersuasionValue)
        if p.is_climax():
            return s
        factions = self.owner.list_attr("FactionList")
        if "Fremen" in factions:
            if "FremenBond" in card_tags:
                s.add("Fremen Bond in Deck Synergy", c.SynergyBondWithFremenInDeck)
            if "WantF" in card_tags:
                s.add("Fremen in Deck Synergy", c.SynergyWithFactionInDeck)
        if "BeneGesserit" in factions and "WantBG" in card_tags:
            s.add("Bene Gesserit in Deck Synergy", c.SynergyWithFactionInDeck)
        if "SpacingGuild" in factions and "WantSG" in card_tags:
            s.add("Spacing Guild in Deck Synergy", c.SynergyWithFactionInDeck)
        if "Emperor" in factions and "WantE" in card_tags:
            s.add("Emperor in Deck Synergy", c.SynergyWithFactionInDeck)
        if "DiscardEnabler" in owner_tags and "IncentiveDiscard" in card_tags:
            s.multiply("Discard Enabler", c.DiscardEnablerMod)
        if "IncentiveDiscard" in owner_tags and "DiscardEnabler" in card_tags:
            s.multiply("Discard Incentive", c.DiscardIncentiveMod)
        if "Graft" in owner_tags and "WantsGraft" in card_tags:  # Immortality
            s.multiply("Graft Incentive", c.SynergyGraftMod)
        if "WantsGraft" in owner_tags and "Graft" in card_tags:  # Immortality
            s.multiply("Wants Graft Incentive", c.SynergyWantsGraftMod)
        if "Spy" in owner_tags and "WantSpy" in card_tags:
            s.add("Spy Card Incentive", c.SynergySpyCardMod)
        return s

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``SpecificAcquireValue`` @0x4a88ee0: empty by default."""

        return Summer()

    # -- engine-side members the AI depends on -----------------------------------------

    timing: ClassVar[Timing] = Timing.NONE

    def can_be_run(self, p: Profile) -> bool:
        """``CanBeRun`` (MeetsCost && HasTargets && IsUnexhausted).

        The engine decides legality; ports override this only where the app's
        gate is narrower than ours and the AI must not consider the option.
        """

        return True


class UnportedAbility(Ability):
    """Stand-in for an app ability class with no port yet."""

    def __init__(self, owner: Entity, app_class: str) -> None:
        super().__init__(owner)
        self.app_class = app_class

    def __repr__(self) -> str:
        return f"UnportedAbility({self.app_class!r}, {self.owner.ref!r})"


PORTS: dict[str, type[Ability]] = {}
UNPORTED: Counter[str] = Counter()


def port[A: Ability](app_class: str) -> Callable[[type[A]], type[A]]:
    """Register a port class for the app ability class ``app_class``."""

    def register(cls: type[A]) -> type[A]:
        if app_class in PORTS:
            raise ValueError(f"two ports for {app_class}")
        cls.APP_CLASS = app_class
        PORTS[app_class] = cls
        return cls

    return register


def ability_for(app_class: str, owner: Entity) -> Ability:
    """An instance of the port of ``app_class`` attached to ``owner``."""

    cls = PORTS.get(app_class)
    if cls is None:
        UNPORTED[app_class] += 1
        return UnportedAbility(owner, app_class)
    return cls(owner)


def abilities_of(owner: Entity) -> tuple[Ability, ...]:
    """The owner's abilities in archetype order (``WormAbilityIDs``)."""

    return tuple(ability_for(name, owner) for name in owner.ability_ids)
