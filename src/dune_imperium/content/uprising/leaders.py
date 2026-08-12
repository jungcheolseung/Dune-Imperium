"""Uprising Leader identities used during four-player setup."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef


@dataclass(frozen=True, slots=True)
class LeaderDefinition:
    """Setup-relevant identity of one physical Leader card."""

    leader_id: str
    name: str
    catalog_url: str
    choam_only: bool = False
    setup_face_id: str | None = None
    alternate_face_id: str | None = None
    uses_feyd_token: bool = False
    sources: tuple[SourceRef, ...] = (
        SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 17)),
    )

    def __post_init__(self) -> None:
        if not self.leader_id or not self.name:
            raise ValueError("leaders require stable IDs and names")
        if not self.catalog_url.startswith("https://"):
            raise ValueError("leader catalog URLs must use HTTPS")
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
    ),
    LeaderDefinition(
        "lady_amber_metulli",
        "Lady Amber Metulli",
        _catalog(194, "uprising-lady-amber-metulli"),
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


def leaders_for_choam(choam_module: bool) -> tuple[LeaderDefinition, ...]:
    """Return Leader cards legal for the selected setup."""

    return tuple(leader for leader in LEADERS if choam_module or not leader.choam_only)
