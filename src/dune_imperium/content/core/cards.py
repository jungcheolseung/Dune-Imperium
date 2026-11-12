"""Card entry schemas shared by every base game's and expansion's cards
(docs/content-core-refactor-plan.md 2.1): personal cards (starting,
Reserve, Imperium), Intrigue, Leaders, Conflicts and Contracts, with the
Intrigue option builders and the record checks the sets' tables call.
"""

from dataclasses import dataclass, replace

from dune_imperium.content.core.abilities import Ability, AbilityStructure
from dune_imperium.content.core.effects import (
    AcquiredCard,
    AllConditions,
    AllianceTaken,
    AtBoardSpace,
    AtMakerSpace,
    Condition,
    ContractTaken,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    Freighter,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    IntrigueOption,
    IntrigueTiming,
    PayResources,
    PlaceNegotiator,
    PlaceSpy,
    RecallAgent,
    RecallSpy,
    RecruitTroops,
    TakeContract,
    TakeControl,
    TakeMentat,
    TrashIntrigueCard,
    TrashPersonalCard,
    Trigger,
)
from dune_imperium.content.core.icons import (
    AgentIcon,
    BattleIcon,
    ConflictTier,
    Faction,
)
from dune_imperium.content.core.schema import (
    CardDefinition,
    DeckCardEntry,
    GameOption,
    SourceDocument,
    SourceRef,
    check_requires,
)


@dataclass(frozen=True, slots=True)
class StartingCardEntry:
    """One starting-card definition and its per-player quantity."""

    card: CardDefinition
    copies: int
    factions: tuple[Faction, ...] = ()
    agent_icons: tuple[AgentIcon, ...] = ()
    agent_spy_factions: tuple[Faction, ...] = ()
    reveal_persuasion: int = 0
    reveal_strength: int = 0

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("starting-card copies must be positive")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("starting-card Agent icons must be unique")
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("starting-card Factions must be unique")
        if len(self.agent_spy_factions) != len(set(self.agent_spy_factions)):
            raise ValueError("starting-card Spy target Factions must be unique")
        if min(self.reveal_persuasion, self.reveal_strength) < 0:
            raise ValueError("starting-card Reveal values must not be negative")


@dataclass(frozen=True, slots=True)
class ReserveStackDefinition:
    """One face-up Reserve stack and its physical quantity."""

    card: CardDefinition
    copies: int
    acquisition_cost: int
    acquisition_vp: int = 0
    factions: tuple[Faction, ...] = ()
    agent_icons: tuple[AgentIcon, ...] = ()
    agent_spy_factions: tuple[Faction, ...] = ()
    reveal_persuasion: int = 0
    reveal_strength: int = 0
    # Gained only through its own icon, never bought with Persuasion or
    # Solari nor taken by a "card that costs N or less" effect: the original
    # game's Foldspace [DI pp. 11, 16] [FAQ p. 2] (OQ-125).
    icon_only: bool = False

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("reserve stack copies must be positive")
        if min(
            self.acquisition_cost,
            self.acquisition_vp,
            self.reveal_persuasion,
            self.reveal_strength,
        ) < 0:
            raise ValueError("Reserve acquisition values must not be negative")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("Reserve Agent icons must be unique")
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("Reserve Factions must be unique")
        if len(self.agent_spy_factions) != len(set(self.agent_spy_factions)):
            raise ValueError("Reserve Spy target Factions must be unique")


@dataclass(frozen=True, slots=True)
class ImperiumCardEntry(DeckCardEntry):
    """One shared-deck card plus independently verified play-facing data."""

    factions: tuple[Faction, ...] = ()
    agent_icons: tuple[AgentIcon, ...] = ()
    # Set only on Ghola's runtime copy that borrows the other grafted card's
    # Agent box (``rules.effects.borrowed_agent_card``), never in card data:
    # a card's own box is found by its id (``content.registry.card_abilities``).
    borrowed_agent_box: str | None = None
    agent_spy_factions: tuple[Faction, ...] = ()
    ignores_influence_requirements: bool = False
    allows_recruited_troop_deployment: bool = False
    reveal_persuasion: int = 0
    reveal_strength: int = 0
    play_data_complete: bool = False
    # Delivery Logistics: its Agent icons are those of the owner's
    # incomplete Contracts, judged when the card is played.
    agent_icons_from_contracts: bool = False
    # Immortality: a Graft Agent box — the card is played together with a
    # second card and never alone [Immortality p. 10].
    graft: bool = False
    # Immortality: greyed Agent icons that a printed condition turns on
    # (Long Reach, Show of Strength); ``agent_icons`` lists them and the
    # condition is judged at play time.
    # The original game's Kwisatz Haderach: "Send one of your Agents from
    # anywhere to ANY board space (even if occupied)" -- no Agent icon, the
    # Agent from the Leader or from a board space, playable with none left on
    # the Leader [DI p. 13] (docs/rules/imperium-base.md 13.1, 16).
    sends_agent_anywhere: bool = False
    # Rise of Ix: only these printed icons ignore enemy Agents [Ix p. 7].
    # Identity metadata may precede the full play transcription; incomplete
    # entries stay out of the deck, and ordinary/granted icons gain no bypass.
    infiltration_icons: tuple[AgentIcon, ...] = ()
    # Rise of Ix: the Reveal box is marked Unload -- gained also when the card
    # is discarded or trashed [Rise of Ix p. 7] (``rules.unload``).
    unload: bool = False
    # Rise of Ix's Guild Accord: "It costs [2 spice] less to send an Agent to
    # the Heighliner board space with this card." [Steam app text] -- a
    # placement rule (``agent_turn``), not a box resolved after it.
    heighliner_spice_discount: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("Imperium-card Factions must be unique")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("Imperium-card Agent icons must be unique")
        if len(self.infiltration_icons) != len(set(self.infiltration_icons)):
            raise ValueError("Imperium-card Infiltration icons must be unique")
        if self.play_data_complete and not set(self.infiltration_icons) <= set(
            self.agent_icons
        ):
            raise ValueError("Infiltration icons must be printed Agent icons")
        if len(self.agent_spy_factions) != len(set(self.agent_spy_factions)):
            raise ValueError("Imperium-card Spy target Factions must be unique")
        if not isinstance(self.ignores_influence_requirements, bool):
            raise TypeError("Influence-requirement override must be a boolean")
        if not isinstance(self.allows_recruited_troop_deployment, bool):
            raise TypeError("recruited-troop deployment permission must be a boolean")
        if not isinstance(self.sends_agent_anywhere, bool):
            raise TypeError("the send-from-anywhere flag must be a boolean")
        if not isinstance(self.unload, bool):
            raise TypeError("the Unload mark must be a boolean")
        if self.heighliner_spice_discount < 0:
            raise ValueError("a Heighliner discount must not be negative")
        if self.sends_agent_anywhere and self.agent_icons:
            raise ValueError("a send-from-anywhere card has no Agent icons")
        if min(self.reveal_persuasion, self.reveal_strength) < 0:
            raise ValueError("Imperium-card Reveal values must not be negative")
        if not self.play_data_complete and (
            self.factions
            or self.agent_icons
            or self.agent_spy_factions
            or self.ignores_influence_requirements
            or self.allows_recruited_troop_deployment
            or self.sends_agent_anywhere
            or self.reveal_persuasion
            or self.reveal_strength
            or self.unload
            or self.heighliner_spice_discount
        ):
            raise ValueError("partial Imperium-card play data must not be exposed")


@dataclass(frozen=True, slots=True)
class IntrigueCardEntry(DeckCardEntry):
    """One Intrigue identity plus its transcribed play options.

    ``options`` lists the alternative ways to play the card. A card printed as
    ``A —OR— B`` has two options; a card with several stacked lines has one
    option with several sections. ``play_data_complete`` marks that every
    printed option is transcribed and executable by the rules engine.
    """

    options: tuple[IntrigueOption, ...] = ()
    # Piter De Vries' Twisted Intrigue: never in the shared deck, dealt from
    # his own face-down deck; still an Intrigue card once held.
    twisted: bool = False
    # Steersman Y'rkoon's Navigation cards: not Intrigue cards at all, but
    # transcribed in the same effect DSL and resolved by the same choice
    # frames (``rules.navigation``).
    navigation: bool = False

    @property
    def play_data_complete(self) -> bool:
        """Return whether every printed option is transcribed."""

        return bool(self.options)

    @property
    def timings(self) -> frozenset[IntrigueTiming]:
        """Return every timing at which some option can be played."""

        return frozenset(option.timing for option in self.options)


def plot_option(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.PLOT, sections=sections)


def plot_lines_option(*sections: EffectSection) -> IntrigueOption:
    """Separate printed lines (no ``—OR—``), each used on its own (OQ-058)."""

    return IntrigueOption(timing=IntrigueTiming.PLOT, sections=sections, separate=True)


def combat_lines_option(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(
        timing=IntrigueTiming.COMBAT, sections=sections, separate=True
    )


def plot_trigger_option(trigger: Trigger, *sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(
        timing=IntrigueTiming.PLOT, sections=sections, trigger=trigger
    )


def combat_option(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.COMBAT, sections=sections)


def combat_trigger_option(trigger: Trigger, *sections: EffectSection) -> IntrigueOption:
    """A Combat card played at its trigger, not in the Combat Intrigue rounds
    (a winning Intrigue, ``OnConflictWon``: the winner's reward window)."""

    return IntrigueOption(
        timing=IntrigueTiming.COMBAT, sections=sections, trigger=trigger
    )


def endgame_option(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.ENDGAME, sections=sections)


@dataclass(frozen=True, slots=True)
class LeaderDefinition:
    """Identity and transcribed ability names of one physical Leader card.

    ``ability_name`` and ``signet_name`` record the two printed abilities
    [Main p. 6] once their text has been verified against the card image at
    ``catalog_url``; both stay ``None`` until that verification happens. The
    ability behaviour itself lives in ``rules/leader_abilities.py`` keyed by
    ``leader_id``.
    """

    leader_id: str
    name: str
    catalog_url: str
    # The options the Leader needs on: Bloodlines Leaders join the pool only
    # with that option on; Kota Odax of Ix needs the Tech Module as well
    # [Bloodlines p. 6].
    requires: frozenset[GameOption] = frozenset()
    setup_face_id: str | None = None
    alternate_face_id: str | None = None
    uses_feyd_token: bool = False
    ability_name: str | None = None
    signet_name: str | None = None
    alternate_ability_name: str | None = None
    alternate_signet_name: str | None = None
    # Starting cards this Leader's printed setup rule removes from their
    # ten-card deck (Staban Tuek's Limited Allies).
    removed_starting_card_ids: tuple[str, ...] = ()
    # Printed setup deviations: Steersman Y'rkoon starts with no water;
    # Chani's Tactics token starts on the four-player space of her track.
    starting_water: int = 1
    # Glossu Rabban's Arrakis Fiefdom (the original game): he starts with 1
    # spice and 1 Solari more [Rabban card] (docs/rules/imperium-base.md 4;
    # the app's ``ArrakisFiefdomAbility`` gains both at game start).
    extra_starting_spice: int = 0
    extra_starting_solari: int = 0
    uses_tactics_track: bool = False
    # Piter De Vries deals himself the Twisted Intrigue deck.
    uses_twisted_intrigue: bool = False
    sources: tuple[SourceRef, ...] = (
        SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 17)),
    )

    def __post_init__(self) -> None:
        if not self.leader_id or not self.name:
            raise ValueError("leaders require stable IDs and names")
        if not self.catalog_url.startswith("https://"):
            raise ValueError("leader catalog URLs must use HTTPS")
        if (self.ability_name is None) != (self.signet_name is None):
            raise ValueError("leader abilities are transcribed as a pair")
        if (self.alternate_ability_name is None) != (
            self.alternate_signet_name is None
        ):
            raise ValueError("alternate-face abilities are transcribed as a pair")
        if self.alternate_ability_name is not None and (
            self.alternate_face_id is None or self.ability_name is None
        ):
            raise ValueError(
                "alternate-face abilities require an alternate face and the "
                "setup face's abilities"
            )
        if len(self.removed_starting_card_ids) != len(
            set(self.removed_starting_card_ids)
        ):
            raise ValueError("removed starting cards must be unique")
        if not self.sources:
            raise ValueError("leaders require official source references")
        check_requires(self.requires, "Leaders")


type RewardRows = tuple[Ability, Ability, Ability]


@dataclass(frozen=True, slots=True)
class ConflictDefinition:
    """Conflict identity, battle icon, and optional transcribed reward rows."""

    card: CardDefinition
    tier: ConflictTier
    # ``None``: the card prints no battle icon (Economic Supremacy; OQ-094).
    battle_icon: BattleIcon | None = None
    shield_wall_protected: bool = False
    # The first, second and third place rows as their ability records
    # (``conflict_abilities``): what the payer, the card text and the codec
    # read. ``None``: the rows are not transcribed.
    reward_rows: RewardRows | None = None
    # The options that add it to the tier pool: Bloodlines [Bloodlines p. 3],
    # the Epic Game [Main p. 18].
    requires: frozenset[GameOption] = frozenset()

    def __post_init__(self) -> None:
        for row in self.reward_rows or ():
            check_conflict_reward_row(row)

    @property
    def control_space_id(self) -> str | None:
        """The board space the first place takes control of, if it does."""

        if self.reward_rows is None:
            return None
        for line in self.reward_rows[0].sections:
            for reward in line.rewards:
                if isinstance(reward, TakeControl):
                    return reward.space_id
        return None


def check_conflict_reward_row(row: Ability) -> None:
    """Refuse a reward row the payer and the card text cannot read.

    A row's lines print no condition. A line with a cost is an optional
    "cost -> VP" arrow [FAQ p. 3] (Solari, spice, or Spies recalled), and a
    row's arrows share one VP value (Economic Supremacy prints two). The other
    lines give resources, Intrigue cards, troops, Spies (with or without Deep
    Cover), Contracts, trashes, VP, chosen, distinct or one Faction's
    Influence, or control of a space; each is printed once on the row but
    Spies, trashes, Rise of Ix's Freighters and chosen Influence, which may
    repeat. A row gives something. (The checks the compiled ``ConflictReward``
    ran until the reward totals cleanup, 2026-10-21.)

    The original game adds the Mentat icon, one Faction's two Influence and
    rows of alternatives: a printed "-OR-" (``ONE_OF``) or "Choose two:"
    (``CHOOSE_TWO``) row's lines are each checked as a row of their own, with
    no arrow, and offer at least as many lines as are taken.
    """

    if row.structure in (AbilityStructure.ONE_OF, AbilityStructure.CHOOSE_TWO):
        taken = 2 if row.structure is AbilityStructure.CHOOSE_TWO else 1
        if len(row.sections) <= taken:
            raise ValueError("a Conflict reward row of alternatives offers too few")
        for line in row.sections:
            if line.costs:
                raise ValueError("a Conflict reward alternative prints no arrow")
            check_conflict_reward_row(
                replace(row, sections=(line,), structure=AbilityStructure.SEQUENCE)
            )
        return
    if row.structure is not AbilityStructure.SEQUENCE:
        raise ValueError(f"a Conflict reward row is not {row.structure}")
    printed: set[str] = set()

    def once(key: str) -> None:
        if key in printed:
            raise ValueError(f"a Conflict reward row prints {key} twice")
        printed.add(key)

    arrow_points: set[int] = set()
    gives = False
    for line in row.sections:
        if line.condition is not None:
            raise ValueError("a Conflict reward row prints no condition")
        if line.costs:
            match line.costs, line.rewards:
                case (PayResources(solari=solari, spice=0, water=0),), (
                    GainVictoryPoints(amount=points),
                ) if solari:
                    once("optional_solari_cost")
                case (PayResources(solari=0, spice=spice, water=0),), (
                    GainVictoryPoints(amount=points),
                ) if spice:
                    once("optional_spice_cost")
                case (RecallSpy(),), (GainVictoryPoints(amount=points),):
                    once("optional_recall_spies")
                case _:
                    raise TypeError(f"{line!r} is not a Conflict reward arrow")
            arrow_points.add(points)
            gives = True
            continue
        for reward in line.rewards:
            match reward:
                case GainResources(solari=solari, spice=spice, water=water):
                    once("resources")
                    if min(solari, spice, water) < 0:
                        raise ValueError(
                            "Conflict reward quantities must not be negative"
                        )
                case DrawIntrigueCards():
                    once("intrigue")
                case RecruitTroops():
                    once("troops")
                case PlaceSpy() if reward in (PlaceSpy(), PlaceSpy(shared_post=True)):
                    pass
                case Freighter():
                    # Rise of Ix's icon, printed once or twice on a row
                    # (Trade Monopoly's first place).
                    pass
                case TakeContract():
                    once("contracts")
                case TrashPersonalCard() if reward == TrashPersonalCard():
                    pass
                case GainVictoryPoints():
                    once("victory_points")
                case GainInfluence(one_faction=True) if reward == replace(
                    reward, factions=None, distinct=False
                ) and reward.times > 1 and not reward.where_opponent_leads:
                    once("one_faction_influence")
                case GainInfluence() if reward == GainInfluence(
                    times=reward.times, distinct=True
                ):
                    once("choose_distinct_influence")
                case TakeMentat():
                    once("mentat")
                case GainInfluence(times=times, factions=(faction,)) if (
                    reward == GainInfluence(times=times, factions=(faction,))
                ):
                    once("faction_influence")
                case GainInfluence() if reward == GainInfluence():
                    pass
                case TakeControl(space_id=space_id):
                    if not space_id:
                        raise ValueError("control space ID must not be empty")
                    once("control")
                case _:
                    raise TypeError(f"{reward!r} is not a Conflict reward")
            gives = True
    if len(arrow_points) > 1:
        raise ValueError("a Conflict reward row's arrows share one VP value")
    if not gives:
        raise ValueError("a Conflict reward row must contain a reward")


@dataclass(frozen=True, slots=True)
class ContractDefinition:
    """One standard Contract tile.

    Each physical tile has its own id, so two copies of one printed face are
    two definitions; ``copy_of`` names the first copy's id, whose picture,
    Korean name and record the second copy shares. ``terms`` is the tile's
    ability record (``contract_abilities``): its ``requirement`` is the
    completion condition and its one line the reward. The rules, the card
    text and the codec read it (the compiled ``ContractCondition`` /
    ``ContractReward`` copies are gone since the reward totals cleanup,
    2026-10-21).
    """

    card: CardDefinition
    terms: Ability
    # Bloodlines' Contracts join the bank only with that option on.
    requires: frozenset[GameOption] = frozenset()
    copy_of: str | None = None
    # One of the ten Rise of Ix tiles, dealt at setup and never in the bank
    # [Main p. 16].
    rise_of_ix_only: bool = False

    def __post_init__(self) -> None:
        check_contract_terms(self.terms)

    @property
    def requirement(self) -> Condition:
        """The printed completion condition."""

        requirement = self.terms.requirement
        assert requirement is not None  # ``check_contract_terms``
        return requirement

    @property
    def reward_line(self) -> EffectSection:
        """The printed reward line (its cost, Bloodlines' Immediate trash)."""

        (line,) = self.terms.sections
        return line

    @property
    def board_space(self) -> str | None:
        """The board space an Agent visit completes the tile at, if any."""

        requirement = self.requirement
        return requirement.space_id if isinstance(requirement, AtBoardSpace) else None

    @property
    def harvest_spice(self) -> int:
        """The spice a Maker-space visit must gain that turn ("Harvest"), or 0
        for a tile completed otherwise."""

        match self.requirement:
            case AllConditions(
                conditions=(AtMakerSpace(), GainedSpiceThisTurn(amount=n))
            ):
                return n
        return 0

    @property
    def acquire_card(self) -> str | None:
        """The card whose acquisition completes the tile, if any."""

        requirement = self.requirement
        return requirement.card_id if isinstance(requirement, AcquiredCard) else None

    @property
    def earns_alliance(self) -> bool:
        """Whether taking an Alliance token completes the tile (Bloodlines'
        "Earn any Alliance" [Bloodlines p. 2])."""

        return isinstance(self.requirement, AllianceTaken)

    @property
    def completes_immediately(self) -> bool:
        """Return whether taking this Contract completes it immediately."""

        return isinstance(self.requirement, ContractTaken)

    @property
    def requires_intrigue_trash(self) -> bool:
        """Return whether taking this Contract costs an Intrigue card from hand
        (the Bloodlines Immediate tile [Bloodlines p. 2])."""

        return self.completes_immediately and bool(self.reward_line.costs)


def check_contract_terms(terms: Ability) -> None:
    """Refuse a Contract record the rules and the card text cannot read.

    One reward line with no condition of its own and no cost, but the
    Intrigue card the Bloodlines Immediate tile trashes when taken. The
    requirement is an Agent visit to a board space, a Maker-space visit
    gaining spice that turn, a named card acquired, the tile taken
    (Immediate), or an Alliance taken. The reward gives Solari, water,
    troops, cards, Intrigue cards, Contracts, Spies (with or without Deep
    Cover), Agent recalls, one Faction's Influence or a Rise of Ix
    Negotiator -- each printed once but Spies and recalls, which may
    repeat -- and gives something. (The
    checks the compiled condition and reward ran until the reward totals
    cleanup, 2026-10-21.)
    """

    if len(terms.sections) != 1:
        raise ValueError("a Contract prints one reward line")
    (line,) = terms.sections
    requirement = terms.requirement
    if line.condition is not None:
        raise ValueError("a Contract's reward line has no condition of its own")
    if line.costs and not (
        isinstance(requirement, ContractTaken) and line.costs == (TrashIntrigueCard(),)
    ):
        raise ValueError(f"no Contract pays {line.costs!r}")
    match requirement:
        case AtBoardSpace(space_id=space_id) if space_id:
            pass
        case AllConditions(
            conditions=(AtMakerSpace(), GainedSpiceThisTurn(amount=n))
        ) if n >= 1:
            pass
        case AcquiredCard(card_id=card_id) if card_id:
            pass
        case ContractTaken() | AllianceTaken():
            pass
        case _:
            raise TypeError(f"{requirement!r} is not a Contract condition")
    printed: set[str] = set()
    gained = 0
    for reward in line.rewards:
        match reward:
            case GainResources(solari=solari, spice=0, water=water):
                key = "resources"
                if min(solari, water) < 0:
                    raise ValueError("Contract rewards must not be negative")
                gained += solari + water
            case RecruitTroops(count=count):
                key, gained = "troops", gained + count
            case GainInfluence(
                times=times,
                factions=(_,),
                distinct=False,
                where_opponent_leads=False,
                different_from_trigger=False,
                minimum_own=0,
            ):
                key, gained = "influence", gained + times
            case DrawIntrigueCards(count=count):
                key, gained = "intrigue_cards", gained + count
            case DrawPersonalCards(count=count):
                key, gained = "personal_cards", gained + count
            case TakeContract(count=count):
                key, gained = "contracts", gained + count
            case PlaceSpy() if reward in (PlaceSpy(), PlaceSpy(shared_post=True)):
                gained += 1
                continue
            case RecallAgent() if reward == RecallAgent():
                gained += 1
                continue
            case PlaceNegotiator():
                key, gained = "negotiator", gained + 1
            case _:
                raise TypeError(f"{reward!r} is not a Contract reward")
        if key in printed:
            raise ValueError(f"a Contract prints {key} twice")
        printed.add(key)
    if gained <= 0:
        raise ValueError("a Contract reward must grant something")


type PersonalCardDefinition = (
    StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry
)


def imperium_card_entry(
    catalog_id: int | None,
    slug: str,
    name: str,
    acquisition_cost: int,
    *,
    catalog_set: str,
    sources: tuple[SourceRef, ...],
    copies: int = 1,
    requires: frozenset[GameOption] = frozenset(),
    has_acquisition_bonus: bool = False,
    factions: tuple[Faction, ...] = (),
    agent_icons: tuple[AgentIcon, ...] = (),
    agent_spy_factions: tuple[Faction, ...] = (),
    ignores_influence_requirements: bool = False,
    allows_recruited_troop_deployment: bool = False,
    reveal_persuasion: int = 0,
    reveal_strength: int = 0,
    play_data_complete: bool = False,
    agent_icons_from_contracts: bool = False,
    graft: bool = False,
) -> ImperiumCardEntry:
    """One Imperium card of the Uprising-format deck (Uprising, Bloodlines,
    Immortality): ``sources`` and the Dune Cards Hub ``catalog_set`` come from
    the set that prints it."""

    return ImperiumCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=sources,
            catalog_url=(
                None
                if catalog_id is None
                else f"https://dunecardshub.com/cards/{catalog_id}/"
                f"{catalog_set}-{slug}"
            ),
        ),
        copies=copies,
        requires=requires,
        acquisition_cost=acquisition_cost,
        has_acquisition_bonus=has_acquisition_bonus,
        factions=factions,
        agent_icons=agent_icons,
        agent_spy_factions=agent_spy_factions,
        ignores_influence_requirements=ignores_influence_requirements,
        allows_recruited_troop_deployment=allows_recruited_troop_deployment,
        reveal_persuasion=reveal_persuasion,
        reveal_strength=reveal_strength,
        play_data_complete=play_data_complete,
        agent_icons_from_contracts=agent_icons_from_contracts,
        graft=graft,
    )


def intrigue_card_entry(
    catalog_id: int,
    slug: str,
    name: str,
    *,
    catalog_set: str,
    sources: tuple[SourceRef, ...],
    copies: int = 1,
    requires: frozenset[GameOption] = frozenset(),
    options: tuple[IntrigueOption, ...] = (),
    twisted: bool = False,
) -> IntrigueCardEntry:
    """One Intrigue card of the Uprising-format deck: ``sources`` and the Dune
    Cards Hub ``catalog_set`` come from the set that prints it."""

    return IntrigueCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=sources,
            catalog_url=f"https://dunecardshub.com/cards/{catalog_id}/{catalog_set}-{slug}",
        ),
        copies=copies,
        requires=requires,
        options=options,
        twisted=twisted,
    )
