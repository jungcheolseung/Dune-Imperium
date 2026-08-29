"""Uprising Leader identities used during four-player setup."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef


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
    choam_only: bool = False
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


def _catalog(card_id: int, slug: str) -> str:
    return f"https://dunecardshub.com/cards/{card_id}/{slug}"


LEADERS: Final = (
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
        choam_only=True,
    ),
)


LEADERS_BY_ID: Final = {leader.leader_id: leader for leader in LEADERS}


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


def leaders_for_choam(choam_module: bool) -> tuple[LeaderDefinition, ...]:
    """Return Leader cards legal for the selected setup."""

    return tuple(leader for leader in LEADERS if choam_module or not leader.choam_only)
