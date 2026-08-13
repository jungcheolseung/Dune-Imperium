"""Authoritative per-player state and component invariants."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Resources:
    """Spendable resources held by one player."""

    solari: int = 0
    spice: int = 0
    water: int = 1

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("player resources must not be negative")


@dataclass(frozen=True, slots=True)
class Influence:
    """Influence positions in fixed rules order."""

    emperor: int = 0
    spacing_guild: int = 0
    bene_gesserit: int = 0
    fremen: int = 0

    def __post_init__(self) -> None:
        if (
            min(
                self.emperor,
                self.spacing_guild,
                self.bene_gesserit,
                self.fremen,
            )
            < 0
        ):
            raise ValueError("influence must not be negative")


@dataclass(frozen=True, slots=True)
class PlayerState:
    """All public and private state owned by one player."""

    player_id: int
    leader_id: str | None = None
    victory_points: int = 1
    resources: Resources = Resources()
    influence: Influence = Influence()
    agents_available: int = 2
    agent_locations: tuple[str, ...] = ()
    swordmaster_acquired: bool = False
    troops_supply: int = 9
    troops_garrison: int = 3
    troops_conflict: int = 0
    sandworms_conflict: int = 0
    spies_supply: int = 3
    spy_post_ids: tuple[str, ...] = ()
    control_space_ids: tuple[str, ...] = ()
    combat_strength: int = 0
    has_revealed: bool = False
    high_council: bool = False
    maker_hooks: bool = False
    deck: tuple[str, ...] = ()
    hand: tuple[str, ...] = ()
    discard_pile: tuple[str, ...] = ()
    in_play: tuple[str, ...] = ()
    trashed: tuple[str, ...] = ()
    intrigue_cards: tuple[str, ...] = ()
    objective_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.player_id < 0:
            raise ValueError("player_id must not be negative")
        quantities = (
            self.victory_points,
            self.agents_available,
            self.troops_supply,
            self.troops_garrison,
            self.troops_conflict,
            self.sandworms_conflict,
            self.spies_supply,
            self.combat_strength,
        )
        if min(quantities) < 0:
            raise ValueError("player component quantities must not be negative")

        active_agents = 3 if self.swordmaster_acquired else 2
        if self.agents_available + len(self.agent_locations) != active_agents:
            raise ValueError("available and placed agents must equal active agents")
        if len(self.agent_locations) != len(set(self.agent_locations)):
            raise ValueError("a player cannot place two agents in one space")
        if self.troops_supply + self.troops_garrison + self.troops_conflict != 12:
            raise ValueError("a player must always account for all 12 troops")
        if self.spies_supply + len(self.spy_post_ids) != 3:
            raise ValueError("a player must always account for all three spies")
        if len(self.spy_post_ids) != len(set(self.spy_post_ids)):
            raise ValueError("a player cannot place two spies on one post")
        if len(self.control_space_ids) > 3:
            raise ValueError("a player has only three control markers")
        if len(self.control_space_ids) != len(set(self.control_space_ids)):
            raise ValueError("control marker locations must be unique")

        imperium_cards = (
            *self.deck,
            *self.hand,
            *self.discard_pile,
            *self.in_play,
            *self.trashed,
        )
        if len(imperium_cards) != len(set(imperium_cards)):
            raise ValueError("an Imperium card instance cannot occupy two zones")
