import random
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass, field


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
    faction: list[Faction]
    agent_box: list
    reveal_box: list
    persuasion_cost: int
    acquire_effect: list
    agent_icons: list[AgentIcon] = field(default_factory=list)
    starting: bool = False
    reveal_persuation: int = 0
    reveal_swords: int = 0

    def __str__(self):
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

    def add_card(self, card: Card):
        self.deck.append(card)

    def pop_card(self) -> Card:
        return self.deck.pop()

    def shuffle(self):
        random.shuffle(self.deck)

    def __repr__(self) -> str:
        return repr(self.deck)


class Hand(Deck):
    def __init__(self) -> None:
        super().__init__()

    def discard(self, index: int) -> Card:
        return self.deck.pop(index)


@dataclass
class Player:
    imperium: Hand = field(default_factory=Hand)
    intrigue: Hand = field(default_factory=Hand)
    water: int = 1
    solari: int = 0
    spice: int = 0
    agents: int = 2
    cubes: int = 16


if __name__ == '__main__':
    i = Imperium('test', [Faction.BENE_GESSERIT, Faction.EMPEROR], [], [], 2, [], [AgentIcon.LANDSRAAD])
    print(i)
    test_hand = Hand()
    test_hand.add_card(i)
    player_1 = Player(imperium=test_hand, water=1)
    print(player_1)
    print(player_1.imperium.pop_card())
    print(player_1)
