"""Uprising Leader identities used during four-player setup."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.core.cards import LeaderDefinition
from dune_imperium.content.core.schema import GameOption


def _catalog(card_id: int, slug: str) -> str:
    return f"https://dunecardshub.com/cards/{card_id}/{slug}"


# Uprising's own Leaders; Bloodlines' are ``content.bloodlines.leaders``, and
# ``content.registry.leaders.LEADERS`` joins them.
UPRISING_LEADERS: Final = (
    LeaderDefinition(
        "feyd_rautha_harkonnen",
        "Feyd-Rautha Harkonnen",
        _catalog(195, "uprising-feyd-rautha-harkonnen"),
        uses_feyd_token=True,
        ability_name="Devious Strength",
        signet_name="Personal Training",
    ),
    LeaderDefinition(
        "gurney_halleck",
        "Gurney Halleck",
        _catalog(199, "uprising-gurney-halleck"),
        ability_name="Always Smiling",
        signet_name="Warmaster",
    ),
    LeaderDefinition(
        "lady_amber_metulli",
        "Lady Amber Metulli",
        _catalog(194, "uprising-lady-amber-metulli"),
        ability_name="Desert Scouts",
        signet_name="Fill Coffers",
    ),
    LeaderDefinition(
        "lady_jessica",
        "Lady Jessica",
        _catalog(200, "uprising-lady-jessica"),
        setup_face_id="lady_jessica",
        alternate_face_id="reverend_mother_jessica",
        ability_name="Other Memories",
        signet_name="Spice Agony",
        alternate_ability_name="Reverend Mother",
        alternate_signet_name="Water of Life",
    ),
    LeaderDefinition(
        "lady_margot_fenring",
        "Lady Margot Fenring",
        _catalog(198, "uprising-lady-margot-fenring"),
        ability_name="Loyalty",
        signet_name="Arrakis Informant",
    ),
    LeaderDefinition(
        "muad_dib",
        "Muad'Dib",
        _catalog(180, "uprising-muad-dib"),
        ability_name="Unpredictable Foe",
        signet_name="Lead the Way",
    ),
    LeaderDefinition(
        "princess_irulan",
        "Princess Irulan",
        _catalog(196, "uprising-princess-irulan"),
        ability_name="Imperial Birthright",
        signet_name="Chronicler's Insight",
    ),
    LeaderDefinition(
        "staban_tuek",
        "Staban Tuek",
        _catalog(197, "uprising-staban-tuek"),
        ability_name="Smuggle Spice",
        signet_name="Unseen Network",
        # Limited Allies: "You start the game without Diplomacy in your deck."
        removed_starting_card_ids=("diplomacy",),
    ),
    LeaderDefinition(
        "shaddam_corrino_iv",
        "Shaddam Corrino IV",
        _catalog(202, "uprising-shaddam-corrino-iv"),
        requires=frozenset({GameOption.CHOAM_MODULE}),
        ability_name="Sardaukar Commander",
        signet_name="Emperor of the Known Universe",
    ),
)


class FeydTrackReward(StrEnum):
    """Printed reward of one Personal Training track space."""

    NONE = "none"
    PAY_SOLARI_TO_TRASH = "pay_solari_to_trash"
    PLACE_SPY = "place_spy"
    OPTIONAL_TRASH = "optional_trash"
    GAIN_TWO_SPICE = "gain_two_spice"
    TROOP_AND_SPY = "troop_and_spy"


@dataclass(frozen=True, slots=True)
class FeydTrackSpace:
    """One space of Feyd-Rautha's printed Training track.

    The track is a branching path: the Feyd token starts on the leftmost
    space and Personal Training moves it one space to the right along an
    edge of the player's choice, earning the reward on the new space
    [Feyd-Rautha Harkonnen card] [Main p. 17].
    """

    space_id: str
    reward: FeydTrackReward
    next_space_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.space_id:
            raise ValueError("Feyd track spaces require stable IDs")
        if len(self.next_space_ids) != len(set(self.next_space_ids)):
            raise ValueError("Feyd track edges must be unique")


# Transcribed from the card image: the start square forks into a paid-trash
# space (one Solari for a trash) above and a Spy space below, converges on a
# free-trash space, forks again into a trash space above and a Spy-then-two-
# Spice branch below, and both branches end on the troop-and-Spy space, where
# the token remains for the rest of the game [Main p. 17].
FEYD_TRAINING_TRACK: Final = (
    FeydTrackSpace("start", FeydTrackReward.NONE, ("paid_trash", "first_spy")),
    FeydTrackSpace("paid_trash", FeydTrackReward.PAY_SOLARI_TO_TRASH, ("mid_trash",)),
    FeydTrackSpace("first_spy", FeydTrackReward.PLACE_SPY, ("mid_trash",)),
    FeydTrackSpace(
        "mid_trash",
        FeydTrackReward.OPTIONAL_TRASH,
        ("late_trash", "second_spy"),
    ),
    FeydTrackSpace("late_trash", FeydTrackReward.OPTIONAL_TRASH, ("final",)),
    FeydTrackSpace("second_spy", FeydTrackReward.PLACE_SPY, ("double_spice",)),
    FeydTrackSpace("double_spice", FeydTrackReward.GAIN_TWO_SPICE, ("final",)),
    FeydTrackSpace("final", FeydTrackReward.TROOP_AND_SPY, ()),
)

FEYD_TRACK_BY_ID: Final = {space.space_id: space for space in FEYD_TRAINING_TRACK}

FEYD_TRACK_START: Final = "start"
