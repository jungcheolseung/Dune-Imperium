"""Percent-coordinate layout of the Uprising board scan for the browser UI.

The play server can serve one machine-local scan of the printed four-player
board (``assets/board/map.jpg``, or ``DUNE_IMPERIUM_BOARD_IMAGE``)
and the browser draws the live state on top of it: a clickable hotspot per
board space, Agent tokens, Control flags and Spies on observation posts.
The coordinates below are the only thing that ties the UI to that scan.

Every value is a percentage of the image's width or height, so any scan
with the same framing works regardless of resolution. They were measured
by hand on 2026-09-03 against the owner's square 6012x6005 scan
(Tabletop Simulator export of the retail board) using a 2 % grid overlay;
a differently cropped scan needs a re-measure, not a rules change. The
space and post IDs are the engine's (``content.uprising.board``), and the
tests pin that both tables cover them exactly.

``SPACE_BOXES`` are ``(left, top, width, height)`` covering the whole
printed space (title, cost, image and effect icons) so the hotspot lights
up the same region a player would look at on the table. ``POST_POINTS``
are the centres of the observation-post "eye" icons.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

SPACE_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = (
    MappingProxyType(
        {
            # Emperor
            "sardaukar": (12.5, 4.0, 13.5, 9.0),
            "dutiful_service": (12.5, 15.0, 13.5, 8.0),
            # Spacing Guild
            "heighliner": (12.5, 30.0, 13.5, 8.0),
            "deliver_supplies": (12.5, 40.0, 13.5, 8.0),
            # Bene Gesserit
            "espionage": (12.5, 54.5, 13.5, 8.0),
            "secrets": (12.5, 64.5, 13.5, 8.0),
            # Fremen
            "desert_tactics": (12.5, 79.0, 13.5, 8.0),
            "fremkit": (12.5, 89.0, 13.5, 8.0),
            # Landsraad Council
            "high_council": (30.0, 2.0, 26.0, 8.5),
            "imperial_privilege": (30.0, 11.0, 14.0, 9.0),
            "swordmaster": (50.0, 11.5, 12.0, 8.0),
            "assembly_hall": (65.0, 2.0, 13.0, 8.0),
            "gather_support": (65.0, 11.5, 14.0, 8.0),
            # CHOAM
            "shipping": (84.0, 2.0, 13.5, 8.5),
            "accept_contract": (84.0, 11.5, 13.0, 8.0),
            # Arrakis
            "research_station": (39.0, 32.5, 13.0, 6.5),
            "spice_refinery": (60.5, 30.0, 14.5, 8.0),
            "arrakeen": (76.0, 27.5, 15.0, 7.5),
            "sietch_tabr": (29.0, 44.0, 17.0, 8.0),
            "imperial_basin": (74.0, 43.5, 16.0, 7.0),
            "hagga_basin": (49.5, 49.5, 17.5, 7.5),
            "deep_desert": (31.0, 56.0, 18.0, 7.0),
        }
    )
)

POST_POINTS: Final[Mapping[str, tuple[float, float]]] = MappingProxyType(
    {
        "emperor-sardaukar-dutiful-service": (25.3, 14.8),
        "landsraad-high-council-imperial-privilege-swordmaster": (47.5, 12.0),
        "landsraad-assembly-hall-gather-support": (77.8, 10.8),
        "choam-shipping-accept-contract": (96.2, 11.5),
        "spacing-guild-heighliner-deliver-supplies": (25.3, 39.3),
        "arrakis-research-station-spice-refinery": (55.0, 31.4),
        "arrakis-research-station-sietch-tabr": (38.5, 42.8),
        "arrakis-spice-refinery-arrakeen": (75.2, 26.8),
        "arrakis-imperial-basin": (86.0, 43.1),
        "arrakis-hagga-basin": (62.0, 47.3),
        "arrakis-deep-desert": (43.5, 54.9),
        "bene-gesserit-espionage-secrets": (25.2, 63.9),
        "fremen-desert-tactics-fremkit": (25.2, 88.2),
    }
)
