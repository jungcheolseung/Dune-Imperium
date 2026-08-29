"""Uprising Leader identities used during four-player setup."""

from dataclasses import dataclass
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
    ),
    LeaderDefinition(
        "lady_margot_fenring",
        "Lady Margot Fenring",
        _catalog(198, "uprising-lady-margot-fenring"),
    ),
    LeaderDefinition(
        "muad_dib",
        "Muad'Dib",
        _catalog(180, "uprising-muad-dib"),
    ),
    LeaderDefinition(
        "princess_irulan",
        "Princess Irulan",
        _catalog(196, "uprising-princess-irulan"),
    ),
    LeaderDefinition(
        "staban_tuek",
        "Staban Tuek",
        _catalog(197, "uprising-staban-tuek"),
    ),
    LeaderDefinition(
        "shaddam_corrino_iv",
        "Shaddam Corrino IV",
        _catalog(202, "uprising-shaddam-corrino-iv"),
        choam_only=True,
    ),
)


LEADERS_BY_ID: Final = {leader.leader_id: leader for leader in LEADERS}


def leaders_for_choam(choam_module: bool) -> tuple[LeaderDefinition, ...]:
    """Return Leader cards legal for the selected setup."""

    return tuple(leader for leader in LEADERS if choam_module or not leader.choam_only)
