import random
from abc import ABC, abstractmethod
from enum import Enum, auto, IntEnum
from dataclasses import dataclass, field
from typing import Self


class Player(IntEnum):
    _1 = 0
    _2 = 1
    _3 = 2
    _4 = 3


class AgentIcon(Enum):
    EMPEROR = auto()
    SPACING_GUILD = auto()
    BENE_GESSERIT = auto()
    FREMEN = auto()
    LANDSRAAD = auto()
    CITY = auto()
    SPICE_TRADE = auto()


class Faction(Enum):
    EMPEROR = auto()
    SPACING_GUILD = auto()
    BENE_GESSERIT = auto()
    FREMEN = auto()


class IntrigueType(Enum):
    PLOT = auto()
    COMBAT = auto()
    ENDGAME = auto()


@dataclass
class Card(ABC):
    pass


@dataclass
class Imperium(Card):
    name: str
    faction: list[Faction] = field(default_factory=list)
    agent_box: list = field(default_factory=list)
    reveal_box: list = field(default_factory=list)
    persuasion_cost: int = 0
    acquire_effect: list = field(default_factory=list)
    agent_icons: list[AgentIcon] = field(default_factory=list)
    starting: bool = False
    reveal_persuation: int = 0
    reveal_swords: int = 0

    def __str__(self) -> str:
        return self.name


class Conflict(Card):
    def __init__(self, level: int) -> None:
        super().__init__()
        self.level = level


class Intrigue(Card):
    def __init__(self, type_: IntrigueType) -> None:
        super().__init__()
        self.__type = type_


class Deck:
    def __init__(self) -> None:
        self.deck: list[Card] = []

    def __len__(self) -> int:
        return len(self.deck)

    def add_card(self, card: Card) -> None:
        self.deck.append(card)

    def pop_card(self) -> Card:
        return self.deck.pop()

    def shuffle(self) -> None:
        random.shuffle(self.deck)

    def discard(self, index: int) -> Card:
        return self.deck.pop(index)

    def random_discard(self) -> Card:
        return self.discard(random.randrange(len(self.deck)))

    def swap(self, i: int, j: int) -> None:
        self.deck[i], self.deck[j] = self.deck[j], self.deck[i]

    def move(self, i: int, to: Self) -> None:
        to.add_card(self.discard(i))

    def __repr__(self) -> str:
        return repr(self.deck)


class Unit:
    troop: int = 0
    dreadnought: int = 0


@dataclass
class PlayerState:
    hand: Deck = field(default_factory=Deck)
    intrigue: Deck = field(default_factory=Deck)
    deck: Deck = field(default_factory=Deck)
    in_play: Deck = field(default_factory=Deck)
    discard_pile: Deck = field(default_factory=Deck)
    score: int = 0
    spice: int = 0
    solari: int = 0
    water: int = 1
    agent: int = 2
    troop: int = 12
    influence: dict = field(default_factory=lambda: {
        Faction.EMPEROR: 0,
        Faction.SPACING_GUILD: 0,
        Faction.BENE_GESSERIT: 0,
        Faction.FREMEN: 0
    })
    garrison: Unit = field(default_factory=Unit)
    conflict: Unit = field(default_factory=Unit)
    council_seat: bool = False


class GameState:
    def __init__(self, num_players: int, mode) -> None:
        self.num_players = num_players
        self.mode = mode
        self.imperium_deck: Deck = Deck()
        self.imperium_row: Deck = Deck()
        self.imperium_discarded: Deck = Deck()
        self.conflict_deck: Deck = Deck()
        self.conflict_discarded: Deck = Deck()
        self.intrigue_deck: Deck = Deck()
        self.intrigue_discarded: Deck = Deck()
        self.mentat: bool = True

    def init_players(self) -> None:
        pass

    def init_decks(self) -> None:
        pass


@dataclass
class BoardSpaceCost:
    spice: int = 0
    solari: int = 0
    water: int = 0


@dataclass
class BoardSpace:
    name: str
    agent_icon: AgentIcon
    combat_space: bool
    cost: BoardSpaceCost = field(default_factory=BoardSpaceCost)
    # gain
    faction: bool = field(init=False)

    def __post_init__(self):
        self.faction = self.agent_icon.name in Faction.__members__


class Leader:
    def __init__(self, name) -> None:
        self.name = name



# if __name__ == '__main__':
    # i = Imperium('test', [Faction.BENE_GESSERIT, Faction.EMPEROR], [], [], 2, [], [AgentIcon.LANDSRAAD])
    # print(i)
    # test_hand = Deck()
    # test_hand.add_card(i)
    # player_1 = Player(imperium=test_hand, water=1)
    # print(player_1)
    # print(player_1.imperium.pop_card())
    # print(player_1)
    # a = [0,1,1,1]
    # print(a[Player._4])
    # print(AgentIcon.EMPEROR.name in Faction.__members__)