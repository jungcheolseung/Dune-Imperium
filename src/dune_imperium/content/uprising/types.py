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

    GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF = (
        "gain_two_visited_faction_influence_and_trash_self"
    )
    LOOK_AT_TOP_THREE = "look_at_top_three"
    TRASH_SELF = "trash_self"
    TRASH_PERSONAL_CARD = "trash_personal_card"
    TRASH_PERSONAL_CARD_TO_DRAW_ONE = "trash_personal_card_to_draw_one"
    TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND = (
        "trash_personal_card_to_draw_one_if_bene_gesserit_bond"
    )
    MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE = (
        "may_trash_for_intrigue_and_two_troops_if_bene_gesserit_alliance"
    )
    TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE = (
        "trash_self_and_emperor_from_hand_for_extra_influence"
    )
    TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE = (
        "trash_self_and_gain_chosen_influence"
    )
    GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN = (
        "gain_chosen_influence_if_spy_recalled_this_turn"
    )
    LEADER_SIGNET = "leader_signet"
    PAY_TWO_WATER_TO_DRAW_TWO = "pay_two_water_to_draw_two"
    MAY_PAY_FOUR_SPICE_FOR_VP = "may_pay_four_spice_for_vp"
    MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP = (
        "may_discard_two_and_pay_five_solari_for_vp"
    )
    MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE = (
        "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
    )
    ACQUIRE_WITH_SOLARI_TO_HAND = "acquire_with_solari_to_hand"
    TAKE_CONTRACT = "take_contract"
    MAY_DISCARD_TO_TAKE_CONTRACT = "may_discard_to_take_contract"
    DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO = (
        "draw_per_two_completed_contracts_up_to_two"
    )
    GAIN_CHOSEN_INFLUENCE = "gain_chosen_influence"
    DRAW_ONE_AND_RECALL_AGENT = "draw_one_and_recall_agent"
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
    MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD = (
        "may_discard_to_draw_one_and_intrigue_if_spacing_guild"
    )
    EACH_OPPONENT_DISCARDS_PERSONAL_CARD = "each_opponent_discards_personal_card"
    GAIN_SPICE_IF_MAKER_SPACE = "gain_spice_if_maker_space"
    GAIN_TWO_SPICE_IF_MAKER_SPACE = "gain_two_spice_if_maker_space"
    GAIN_TWO_SOLARI = "gain_two_solari"
    PLACE_SPY = "place_spy"
    PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE = (
        "place_spy_allow_shared_if_spying_on_visited_space"
    )
    RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN = (
        "recruit_three_if_spy_recalled_this_turn"
    )
    RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN = (
        "recruit_two_if_spy_recalled_this_turn"
    )
    # Uprising promo cards (card faces; see docs/rules/open-questions.md
    # OQ-024 to OQ-026 for the project rulings behind each).
    MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS = (
        "may_pay_two_spice_for_shield_wall_and_sandworm_if_maker_hooks"
    )
    GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON = "gain_rewards_per_face_up_battle_icon"
    MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE = (
        "may_trash_self_for_troop_and_first_place_influence"
    )
    DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN = (
        "draw_intrigue_if_spy_recalled_this_turn"
    )
    DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT = (
        "draw_intrigue_if_three_units_in_conflict"
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


class PersonalCardDiscardEffect(StrEnum):
    """Typed effects triggered when a personal card is discarded from hand."""

    GAIN_TWO_SPICE = "gain_two_spice"


class PersonalCardAcquisitionEffect(StrEnum):
    """Typed effects resolved immediately after acquiring an Imperium card."""

    DRAW_INTRIGUE_CARD = "draw_intrigue_card"
    GAIN_TWO_SOLARI = "gain_two_solari"
    PLACE_SPY = "place_spy"
    GAIN_SPACING_GUILD_INFLUENCE = "gain_spacing_guild_influence"
    TAKE_CONTRACT = "take_contract"
    RECRUIT_ONE_TROOP = "recruit_one_troop"


class PersonalCardRevealChoiceEffect(StrEnum):
    """Reveal effects that require a player-owned serial decision."""

    RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED = (
        "recall_spy_to_draw_intrigue_if_two_placed"
    )
    MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION = (
        "may_recall_two_spies_for_two_persuasion"
    )
    PLACE_SPY = "place_spy"
    PLACE_SPY_OR_GAIN_TWO_STRENGTH = "place_spy_or_gain_two_strength"
    MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE = (
        "may_lose_influence_to_gain_influence"
    )
    MAY_PAY_THREE_SPICE_FOR_INFLUENCE = "may_pay_three_spice_for_influence"
    MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH = (
        "may_trash_other_emperor_for_three_strength"
    )
    MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH = (
        "may_retreat_two_troops_for_four_strength"
    )
    GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL = (
        "gain_five_solari_or_take_high_council"
    )
    MAY_PAY_WATER_FOR_SANDWORM = "may_pay_water_for_sandworm"
    KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS = (
        "keep_spice_or_trash_self_for_vp_if_four_contracts"
    )


class PersonalCardRevealAcquisitionEffect(StrEnum):
    """Typed effects triggered by an acquisition during the current Reveal."""

    GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW = (
        "gain_influence_for_each_spied_faction_on_spice_must_flow"
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
    draw_intrigue: int = 0
    influence: int = 0
    influence_faction: PersonalCardBond | None = None
    required_faction_bond: PersonalCardBond | None = None
    requires_high_council: bool = False
    requires_swordmaster: bool = False
    minimum_spies_placed: int = 0
    requires_spying_on_maker_space: bool = False
    per_revealed_faction: PersonalCardBond | None = None
    persuasion_per_completed_contract: int = 0

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
        if (
            self.per_revealed_faction is not None
            and self.persuasion == 0
            and self.strength == 0
        ):
            raise ValueError("counted Reveal Faction requires Persuasion or strength")
        if self.influence_faction is not None and not isinstance(
            self.influence_faction,
            PersonalCardBond,
        ):
            raise TypeError("Reveal Influence Faction must use PersonalCardBond")
        if (self.influence == 0) != (self.influence_faction is None):
            raise ValueError("Reveal Influence amount and Faction must be paired")
        if (
            not isinstance(self.requires_high_council, bool)
            or not isinstance(self.requires_swordmaster, bool)
            or not isinstance(self.requires_spying_on_maker_space, bool)
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
            self.draw_intrigue,
            self.influence,
            self.persuasion_per_completed_contract,
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
