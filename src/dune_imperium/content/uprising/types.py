"""Types shared by Uprising card manifests."""

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AgentIcon(StrEnum):
    """Agent icons shared by cards and board spaces."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"
    LANDSRAAD = "landsraad"
    CITY = "city"
    SPICE_TRADE = "spice_trade"
    SPY = "spy"


class PersonalCardBond(StrEnum):
    """Faction affiliation required from another card in play."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"


class PersonalCardAgentEffect(StrEnum):
    """Typed Agent-box effects currently transcribed for personal cards."""

    TRASH_SELF = "trash_self"
    TRASH_PERSONAL_CARD = "trash_personal_card"
    TRASH_PERSONAL_CARD_TO_DRAW_ONE = "trash_personal_card_to_draw_one"
    TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND = (
        "trash_personal_card_to_draw_one_if_bene_gesserit_bond"
    )
    TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE = (
        "trash_self_and_gain_chosen_influence"
    )
    GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN = (
        "gain_chosen_influence_if_spy_recalled_this_turn"
    )
    LEADER_SIGNET = "leader_signet"
    PAY_TWO_WATER_TO_DRAW_TWO = "pay_two_water_to_draw_two"
    DRAW_PERSONAL_CARD = "draw_personal_card"
    DRAW_PER_SANDWORM_IN_CONFLICT = "draw_per_sandworm_in_conflict"
    DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD = (
        "discard_to_draw_one_or_two_if_spacing_guild"
    )
    DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD = (
        "discard_one_draw_two_if_spacing_guild"
    )
    MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD = (
        "may_discard_to_draw_intrigue_and_personal_card"
    )
    GAIN_SPICE_IF_MAKER_SPACE = "gain_spice_if_maker_space"
    GAIN_TWO_SOLARI = "gain_two_solari"
    PLACE_SPY = "place_spy"
    RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN = (
        "recruit_three_if_spy_recalled_this_turn"
    )
    RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN = (
        "recruit_two_if_spy_recalled_this_turn"
    )
    DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN = (
        "draw_intrigue_if_spy_recalled_this_turn"
    )
    GAIN_WATER_IF_BENE_GESSERIT_BOND = "gain_water_if_bene_gesserit_bond"
    GAIN_VISITED_FACTION_INFLUENCE = "gain_visited_faction_influence"
    GAIN_WATER = "gain_water"
    GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO = (
        "gain_by_bene_gesserit_and_fremen_influence_two"
    )
    GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO = (
        "gain_by_emperor_and_spacing_guild_influence_two"
    )
    RECRUIT_ONE_IF_MAKER_SPACE = "recruit_one_if_maker_space"
    RECRUIT_TWO_TROOPS = "recruit_two_troops"
    RECRUIT_TWO_IF_BENE_GESSERIT_BOND = "recruit_two_if_bene_gesserit_bond"
    RETURN_SELF_IF_BENE_GESSERIT_BOND = "return_self_if_bene_gesserit_bond"
    DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO = (
        "draw_if_bene_gesserit_influence_two"
    )
    RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO = (
        "recruit_one_and_draw_if_bene_gesserit_influence_two"
    )


class PersonalCardTrashEffect(StrEnum):
    """Typed effects triggered when a personal card is trashed."""

    DRAW_INTRIGUE_CARD = "draw_intrigue_card"


class PersonalCardAcquisitionEffect(StrEnum):
    """Typed effects resolved immediately after acquiring an Imperium card."""

    DRAW_INTRIGUE_CARD = "draw_intrigue_card"
    PLACE_SPY = "place_spy"


class PersonalCardRevealChoiceEffect(StrEnum):
    """Reveal effects that require a player-owned serial decision."""

    RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED = (
        "recall_spy_to_draw_intrigue_if_two_placed"
    )
    MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION = (
        "may_recall_two_spies_for_two_persuasion"
    )
    PLACE_SPY = "place_spy"
    MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE = (
        "may_lose_influence_to_gain_influence"
    )


@dataclass(frozen=True, slots=True)
class PersonalCardRevealEffect:
    """Automatic public gains produced when a personal card is revealed."""

    solari: int = 0
    spice: int = 0
    water: int = 0
    persuasion: int = 0
    recruit_troops: int = 0
    strength: int = 0
    strength_per_other_sword_card: int = 0
    influence: int = 0
    influence_faction: PersonalCardBond | None = None
    required_faction_bond: PersonalCardBond | None = None
    requires_high_council: bool = False
    requires_swordmaster: bool = False
    minimum_spies_placed: int = 0
    per_revealed_faction: PersonalCardBond | None = None

    def __post_init__(self) -> None:
        if self.required_faction_bond is not None and not isinstance(
            self.required_faction_bond,
            PersonalCardBond,
        ):
            raise TypeError("Faction Bond requirement must use PersonalCardBond")
        if self.per_revealed_faction is not None and not isinstance(
            self.per_revealed_faction,
            PersonalCardBond,
        ):
            raise TypeError("counted Reveal Faction must use PersonalCardBond")
        if self.per_revealed_faction is not None and self.persuasion == 0:
            raise ValueError("counted Reveal Faction requires Persuasion")
        if self.influence_faction is not None and not isinstance(
            self.influence_faction,
            PersonalCardBond,
        ):
            raise TypeError("Reveal Influence Faction must use PersonalCardBond")
        if (self.influence == 0) != (self.influence_faction is None):
            raise ValueError("Reveal Influence amount and Faction must be paired")
        if not isinstance(self.requires_high_council, bool) or not isinstance(
            self.requires_swordmaster,
            bool,
        ):
            raise TypeError("Reveal state requirements must be booleans")
        if self.requires_swordmaster and not self.requires_high_council:
            raise ValueError("Swordmaster Reveal requirement also needs High Council")
        gains = (
            self.solari,
            self.spice,
            self.water,
            self.persuasion,
            self.recruit_troops,
            self.strength,
            self.strength_per_other_sword_card,
            self.influence,
        )
        if min((*gains, self.minimum_spies_placed)) < 0:
            raise ValueError("personal-card Reveal gains must not be negative")
        if max(gains) == 0:
            raise ValueError("personal-card Reveal effect must gain something")


class BattleIcon(StrEnum):
    """Icons paired by Objective and won Conflict cards."""

    CRYSKNIFE = "crysknife"
    DESERT_MOUSE = "desert_mouse"
    ORNITHOPTER = "ornithopter"
    WILD = "wild"


class ConflictTier(IntEnum):
    """The three Conflict deck backs."""

    ONE = 1
    TWO = 2
    THREE = 3
