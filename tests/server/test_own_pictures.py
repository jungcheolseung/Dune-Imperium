"""The project's own pictures stay its own drawings (docs/own-pictures-plan.md).

The public build ships nothing from the private assets: these SVGs, served
from ``server/static/pictures``, are the only pictures it has. A pasted raster
(a PNG as base64, an ``<image>`` of an app sprite) or a reference to an outside
file would undo that, so every file is checked as self-contained vector XML,
and the index says when each drawing was made.
"""

import json
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from dune_imperium.display.icons import ICON_NAMES
from dune_imperium.display.log_icons import LOG_ICON_NAMES
from dune_imperium.server.app import OWN_PICTURES_DIR

INDEX = OWN_PICTURES_DIR / "index.json"
SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
# Elements that bring in a picture, a page or code from elsewhere.
FORBIDDEN_ELEMENTS = frozenset(
    {"image", "feImage", "foreignObject", "script", "style", "iframe", "audio", "video"}
)


def _drawings() -> list[Path]:
    return sorted(
        path
        for path in OWN_PICTURES_DIR.rglob("*")
        if path.is_file() and path != INDEX
    )


def _index() -> dict[str, dict[str, str]]:
    loaded = json.loads(INDEX.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_every_picture_is_an_svg_listed_in_the_index() -> None:
    drawings = _drawings()
    assert drawings, "the own-pictures folder has no drawing"
    assert all(path.suffix == ".svg" for path in drawings), [
        path.name for path in drawings if path.suffix != ".svg"
    ]
    listed = {path.relative_to(OWN_PICTURES_DIR).as_posix() for path in drawings}
    assert set(_index()) == listed


def test_the_index_says_when_and_what_each_drawing_is() -> None:
    for name, entry in _index().items():
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["drawn"]), name
        assert entry["note"].strip(), name


def test_drawings_are_self_contained_vectors() -> None:
    for path in _drawings():
        text = path.read_text(encoding="utf-8")
        assert "data:" not in text and "base64" not in text, path.name
        root = ElementTree.fromstring(text)
        assert root.tag == f"{SVG_NAMESPACE}svg", path.name
        for element in root.iter():
            local = element.tag.removeprefix(SVG_NAMESPACE)
            assert local not in FORBIDDEN_ELEMENTS, (path.name, local)
            for attribute, value in element.attrib.items():
                if attribute.endswith("href"):
                    assert value.startswith("#"), (path.name, attribute, value)
                for target in re.findall(r"url\(([^)]*)\)", value):
                    assert target.strip().startswith("#"), (path.name, value)


def test_icon_drawings_are_named_after_known_icons() -> None:
    icons = OWN_PICTURES_DIR / "icons"
    assert {path.stem for path in icons.glob("*.svg")} <= set(ICON_NAMES)
    log = OWN_PICTURES_DIR / "log"
    assert {path.stem for path in log.glob("*.svg")} <= set(LOG_ICON_NAMES)


def test_every_icon_and_log_picture_has_an_own_drawing() -> None:
    """Stage 2: the public build draws every icon the page names."""

    icons = {path.stem for path in (OWN_PICTURES_DIR / "icons").glob("*.svg")}
    log = {path.stem for path in (OWN_PICTURES_DIR / "log").glob("*.svg")}
    assert icons == set(ICON_NAMES)
    assert log == set(LOG_ICON_NAMES)


def test_the_server_command_takes_the_picture_mode() -> None:
    from dune_imperium.cli.server import _build_parser

    assert _build_parser().parse_args(["--pictures", "own"]).pictures == "own"
    assert _build_parser().parse_args([]).pictures is None


# Each board that prints space names has its Korean twin (``_ko``, the
# Korean edition's names); the Bene Tleilax board prints none.
_NAMED_BOARDS = (
    "uprising",
    "imperium",
    "ix_landsraad",
    "ix_choam",
    "ix_board",
    "tuek_sietch",
    "research_station_overlay",
)
BOARD_PICTURES = frozenset(
    {*_NAMED_BOARDS, *(f"{name}_ko" for name in _NAMED_BOARDS), "bene_tleilax"}
)


def test_board_drawings_are_named_after_the_boards() -> None:
    boards = {path.stem for path in (OWN_PICTURES_DIR / "board").glob("*.svg")}
    assert boards == BOARD_PICTURES


def test_the_icon_drawings_are_current() -> None:
    """scripts/own_pictures/icons.py draws the icons, log icons, pieces, card
    backs and the faces' marks (and their index notes): a changed drawing
    needs a rerun, and a drawn file is never edited by hand."""

    import importlib.util

    script = Path(__file__).resolve().parents[2] / "scripts/own_pictures/icons.py"
    spec = importlib.util.spec_from_file_location("own_icons", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    drawn = module.drawings()
    stale = [
        name
        for name, text in drawn.items()
        if not (OWN_PICTURES_DIR / name).is_file()
        or (OWN_PICTURES_DIR / name).read_text() != text
    ]
    assert stale == []
    assert len(drawn) > 150


def test_the_board_drawings_are_current() -> None:
    """scripts/own_pictures/board.py draws them from the layout tables: a
    changed table or icon needs a redraw (run the script)."""

    import importlib.util

    script = Path(__file__).resolve().parents[2] / "scripts/own_pictures/board.py"
    spec = importlib.util.spec_from_file_location("own_board", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    drawings = {
        "uprising": lambda: module.board(False),
        "uprising_ko": lambda: module.board(True),
        "imperium": module.imperium_board,
        **{
            name.removesuffix(".svg"): (lambda text=text: text)
            for name, text in module.ix_pictures().items()
        },
        "bene_tleilax": module.bene_tleilax_board,
        **{
            name.removesuffix(".svg"): (lambda text=text: text)
            for name, text in module.tile_pictures().items()
        },
    }
    for name, draw in drawings.items():
        drawn = (OWN_PICTURES_DIR / "board" / f"{name}.svg").read_text(encoding="utf-8")
        assert draw() == drawn, f"{name}.svg is stale: run the script"


def test_token_drawings_are_named_after_the_private_token_pictures() -> None:
    """Each drawing stands in for one private token picture of the same
    name (display.token_images): the pieces in the four seat colours, both
    Combat marker faces, the Alliance tokens and the single tokens."""

    from dune_imperium.display.card_backs import CARD_BACK_KINDS
    from dune_imperium.display.token_images import (
        ALLIANCE_TOKEN_FACTIONS,
        FIRST_PLAYER_TOKEN_FILENAME,
        MAKER_HOOKS_TOKEN_FILENAME,
        SARDAUKAR_COMMANDER_TOKEN_FILENAME,
        SEAT_PIECE_KINDS,
        SHIELD_WALL_TOKEN_FILENAME,
        STRENGTH_TOKEN_COLORS,
    )

    known = {
        *(
            f"{kind}_{color}"
            for kind in SEAT_PIECE_KINDS
            for color in STRENGTH_TOKEN_COLORS
        ),
        *(f"strength_{color}" for color in STRENGTH_TOKEN_COLORS),
        *(f"strength_{color}_plus20" for color in STRENGTH_TOKEN_COLORS),
        *(f"alliance_{faction}" for faction in ALLIANCE_TOKEN_FACTIONS),
        *(f"back_{kind}" for kind in CARD_BACK_KINDS),
        *(
            name.removesuffix(".png")
            for name in (
                FIRST_PLAYER_TOKEN_FILENAME,
                MAKER_HOOKS_TOKEN_FILENAME,
                SARDAUKAR_COMMANDER_TOKEN_FILENAME,
                SHIELD_WALL_TOKEN_FILENAME,
            )
        ),
    }
    drawn = {path.stem for path in (OWN_PICTURES_DIR / "tokens").glob("*.svg")}
    assert drawn <= known, sorted(drawn - known)
    # Every seat piece, token and card back the page pictures is drawn.
    assert known <= drawn
