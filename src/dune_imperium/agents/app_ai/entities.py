"""App entities: our ids paired with the app archetype the AI reads.

The app AI values entities (cards, spaces, spies, agents, contracts, faction
tracks) through archetype attributes (``WormAttributes.*``) and the abilities
attached to them. An ``Entity`` carries our id (``ref``) for mapping answers
back to legal actions and the matching app archetype for every read.
"""

from dataclasses import dataclass
from enum import StrEnum

from dune_imperium.agents.app_ai.data.archetypes import Archetype


class Kind(StrEnum):
    """What an entity is, in the app's terms."""

    CARD = "card"  # personal card: starter/reserve/Imperium (WormImperiumPlayable)
    INTRIGUE = "intrigue"  # WormIntriguePlayable
    CONTRACT = "contract"  # WormContractPlayable
    SPACE = "space"  # WormSpace (ref = space_id)
    CONFLICT = "conflict"  # WormConflictPlayable (ref = conflict card id)
    LEADER = "leader"  # leader archetype (ref = leader_id)
    POST = "post"  # WormObservationPost (ref = post_id)
    SPY = "spy"  # WormSpy (ref = post_id it stands on)
    AGENT = "agent"  # WormAgent (ref = space_id it stands on)
    TRACK = "track"  # WormFactionTrack (ref = faction id)
    # App-style extensions (docs/app-ai-plan.md §11.3: synthetic archetypes in
    # ``data/synthetic.py``; the app has no class for them).
    TECH = "tech"  # a Bloodlines Tech tile (WormTechTilePlayable; ref = tech_id)
    COMMANDER = "commander"  # a Sardaukar Commander (ref: see catalog)
    SKILL = "skill"  # a Commander Skill tile (ref = skill id or tile instance id)
    NAVIGATION = "navigation"  # Y'rkoon's Navigation card (ref = instance id)
    SCOUTS = "scouts"  # one Arrakeen Scouts line (ref = "<item id>:<line>")


class Attr(StrEnum):
    """Resource attribute keys of ``GetResourceValue`` (app names)."""

    PERSUASION = "Persuasion"
    STRENGTH = "Strength"
    SOLARI = "Solari"
    SPICE = "Spice"
    WATER = "Water"
    TROOPS = "Troops"
    DREADNOUGHT = "Dreadnought"
    SANDWORMS = "SandWorms"
    SPECIMEN = "Specimen"
    INTRIGUE_CARD = "IntrigueCard"
    VICTORY_POINTS = "VictoryPoints"


@dataclass(frozen=True, slots=True)
class Entity:
    """One app entity.

    ``ref`` is our identifier (card instance id, space id, post id, leader
    id, conflict id or faction id). ``owner`` is the seat that owns or
    controls it where that matters (a card's owner, a spy's or agent's seat).
    ``archetype`` is None only for entities the app has no archetype for
    (spies, agents and faction tracks are plain engine objects in the app).
    Items the app does not have carry a synthetic archetype
    (``data/synthetic.py``) with the same attribute names.
    """

    kind: Kind
    ref: str
    archetype: Archetype | None = None
    owner: int | None = None

    # -- archetype attribute access (the app's GetAttributeValue / Has) -------

    def has(self, name: str) -> bool:
        return self.archetype is not None and name in self.archetype.attributes

    def attr(self, name: str, default: object = None) -> object:
        if self.archetype is None:
            return default
        return self.archetype.attributes.get(name, default)

    def int_attr(self, name: str, default: int = 0) -> int:
        value = self.attr(name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            return default
        return value

    def float_attr(self, name: str, default: float = 0.0) -> float:
        value = self.attr(name, default)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return default
        return float(value)

    def opt_float_attr(self, name: str) -> float | None:
        """A ``Nullable<double>`` attribute: None when absent."""

        value = self.attr(name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        return float(value)

    def list_attr(self, name: str) -> tuple[str, ...]:
        value = self.attr(name, ())
        if isinstance(value, tuple):
            return tuple(str(item) for item in value)
        if isinstance(value, str):
            return (value,)
        return ()

    @property
    def short(self) -> str | None:
        return None if self.archetype is None else self.archetype.short

    @property
    def ability_ids(self) -> tuple[str, ...]:
        """``WormAbilityIDs`` (cards, spaces, leaders) or ``CustomAbilityIDs``."""

        own = self.list_attr("WormAbilityIDs")
        return own if own else self.list_attr("CustomAbilityIDs")
