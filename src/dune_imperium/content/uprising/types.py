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
    LEADER_SIGNET = "leader_signet"
    PAY_TWO_WATER_TO_DRAW_TWO = "pay_two_water_to_draw_two"
    DRAW_PERSONAL_CARD = "draw_personal_card"
    GAIN_SPICE_IF_MAKER_SPACE = "gain_spice_if_maker_space"
    GAIN_TWO_SOLARI = "gain_two_solari"
    PLACE_SPY = "place_spy"
    RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN = (
        "recruit_three_if_spy_recalled_this_turn"
    )
    GAIN_VISITED_FACTION_INFLUENCE = "gain_visited_faction_influence"
    GAIN_WATER = "gain_water"
    GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO = (
        "gain_by_bene_gesserit_and_fremen_influence_two"
    )
    RECRUIT_ONE_IF_MAKER_SPACE = "recruit_one_if_maker_space"
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


@dataclass(frozen=True, slots=True)
class PersonalCardRevealEffect:
    """Automatic public gains produced when a personal card is revealed."""

    solari: int = 0
    spice: int = 0
    water: int = 0
    persuasion: int = 0
    recruit_troops: int = 0
    required_faction_bond: PersonalCardBond | None = None
    requires_high_council: bool = False
    requires_swordmaster: bool = False
    minimum_spies_placed: int = 0

    def __post_init__(self) -> None:
        if self.required_faction_bond is not None and not isinstance(
            self.required_faction_bond,
            PersonalCardBond,
        ):
            raise TypeError("Faction Bond requirement must use PersonalCardBond")
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
