"""FastAPI wiring over the framework-neutral game sessions.

Endpoints translate HTTP to ``GameSessionManager`` calls one to one; every
game decision, visibility judgment, and advance lives in the session layer
and, below it, the rules engine. Errors map to conventional status codes:
unknown games and saves are 404, non-human seats 403, stale revisions 409,
and every other invalid request 400.

Save files live on the server's local disk (``SaveStore``); HTTP responses
only ever carry save metadata because the full document records shuffle
outcomes and with them hidden deck orders.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dune_imperium.display.images import resolve_card_images
from dune_imperium.server.catalog import build_catalog
from dune_imperium.server.persistence import (
    SaveError,
    SaveStore,
    UnknownSaveError,
    default_saves_directory,
)
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

_STATIC_DIR = Path(__file__).parent / "static"
# Gitignored symlink to the private Dune-Imperium-assets checkout (cards/,
# icons/, board/, rulebooks/); every default below lives under it.
_ASSETS_DIR = Path(__file__).parents[3] / "assets"


def default_card_images_directory() -> Path:
    """Return the local card-image checkout (``cards/`` with its manifest).

    ``DUNE_IMPERIUM_CARD_IMAGE_DIR`` overrides the default ``assets/cards``
    (``assets`` is the repository's gitignored symlink to the private
    assets checkout). Optional: without the directory or its
    ``manifest.json`` the server simply serves no card images.
    """

    override = os.environ.get("DUNE_IMPERIUM_CARD_IMAGE_DIR")
    if override:
        return Path(override)
    return _ASSETS_DIR / "cards"


def default_icons_directory() -> Path:
    """Return the local rulebook icon set location.

    ``DUNE_IMPERIUM_ICON_DIR`` overrides the default ``assets/icons``, the
    tree ``scripts/extract_rulebook_icons.py`` fills. Optional like the
    card scans: without it the UI shows text.
    """

    override = os.environ.get("DUNE_IMPERIUM_ICON_DIR")
    if override:
        return Path(override)
    return _ASSETS_DIR / "icons"


def default_board_image_path() -> Path:
    """Return the owner's local board scan location.

    ``DUNE_IMPERIUM_BOARD_IMAGE`` overrides the default
    ``assets/board/map.jpg``. Without the file the UI falls back to the
    text board.
    """

    override = os.environ.get("DUNE_IMPERIUM_BOARD_IMAGE")
    if override:
        return Path(override)
    return _ASSETS_DIR / "board" / "map.jpg"


class CreateGameRequest(BaseModel):
    """Configuration for one new game."""

    seats: list[str] = Field(
        default=["human", "heuristic", "heuristic", "heuristic"],
        min_length=4,
        max_length=4,
        description="Per-seat assignment: 'human', 'heuristic', or 'random'.",
    )
    choam_module: bool = False
    leader_draft: bool = False
    # Shuffle in the three Uprising promo Imperium cards (not in the retail
    # deck; see docs/implementation-plan.md M6).
    promo_cards: bool = False
    game_seed: int | None = None
    policy_seed: int | None = None


class ApplyActionRequest(BaseModel):
    """One indexed action from the legal-action listing."""

    seat: int
    revision: int
    index: int
    # Undo generation from the summary; optional for older clients, but the
    # browser UI always sends it so a taken-back state cannot be acted on.
    undo_count: int | None = None


class UndoRequest(BaseModel):
    """Take back the seat's own latest steps (M11 slice 6, OQ-010 boundary)."""

    seat: int
    revision: int
    steps: int = Field(default=1, ge=1)
    undo_count: int | None = None


class SaveGameRequest(BaseModel):
    """Optional display name for one new save."""

    name: str | None = Field(default=None, max_length=120)


def create_app(
    manager: GameSessionManager | None = None,
    saves_dir: Path | None = None,
    card_images_dir: Path | None = None,
    icons_dir: Path | None = None,
    board_image: Path | None = None,
) -> FastAPI:
    """Build the local play server around one session manager."""

    sessions = manager if manager is not None else GameSessionManager()
    saves = SaveStore(
        saves_dir if saves_dir is not None else default_saves_directory()
    )
    images_dir = (
        card_images_dir
        if card_images_dir is not None
        else default_card_images_directory()
    )
    image_index = frozenset(
        (kind, content_id, path)
        for (kind, content_id), path in resolve_card_images(images_dir).items()
    )
    icon_dir = icons_dir if icons_dir is not None else default_icons_directory()
    icon_files = (
        frozenset(path.name for path in icon_dir.iterdir() if path.is_file())
        if icon_dir.is_dir()
        else frozenset()
    )
    board_path = (
        board_image if board_image is not None else default_board_image_path()
    )
    app = FastAPI(title="Dune: Imperium - Uprising local play server")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/catalog")
    def catalog() -> JsonObject:
        return build_catalog(image_index, icon_files, board_path.is_file())

    @app.get("/board-image", include_in_schema=False)
    def board_image_file() -> FileResponse:
        if not board_path.is_file():
            raise HTTPException(status_code=404, detail="no board image")
        return FileResponse(board_path)

    @app.post("/games")
    def create_game(request: CreateGameRequest) -> JsonObject:
        with _http_errors():
            return sessions.create_game(
                tuple(request.seats),
                choam_module=request.choam_module,
                leader_draft=request.leader_draft,
                promo_cards=request.promo_cards,
                game_seed=request.game_seed,
                policy_seed=request.policy_seed,
            )

    @app.get("/games")
    def list_games() -> list[JsonObject]:
        return sessions.list_games()

    @app.get("/games/{game_id}")
    def game_summary(game_id: str) -> JsonObject:
        with _http_errors():
            return sessions.summary(game_id)

    @app.get("/games/{game_id}/seats/{seat}/view")
    def seat_view(game_id: str, seat: int) -> JsonObject:
        with _http_errors():
            return sessions.view(game_id, seat)

    @app.get("/games/{game_id}/seats/{seat}/actions")
    def seat_actions(game_id: str, seat: int) -> JsonObject:
        with _http_errors():
            return sessions.legal_actions(game_id, seat)

    @app.post("/games/{game_id}/actions")
    def apply_action(game_id: str, request: ApplyActionRequest) -> JsonObject:
        with _http_errors():
            return sessions.apply_action(
                game_id,
                seat=request.seat,
                revision=request.revision,
                index=request.index,
                undo_count=request.undo_count,
            )

    @app.post("/games/{game_id}/undo")
    def undo_steps(game_id: str, request: UndoRequest) -> JsonObject:
        with _http_errors():
            return sessions.undo(
                game_id,
                seat=request.seat,
                revision=request.revision,
                steps=request.steps,
                undo_count=request.undo_count,
            )

    @app.get("/games/{game_id}/log")
    def game_log(game_id: str, seat: int, after: int = 0) -> JsonObject:
        with _http_errors():
            return sessions.log(game_id, seat, after=after)

    @app.delete("/games/{game_id}")
    def delete_game(game_id: str) -> JsonObject:
        with _http_errors():
            sessions.delete(game_id)
        return {"deleted": game_id}

    @app.post("/games/{game_id}/save")
    def save_game(game_id: str, request: SaveGameRequest) -> JsonObject:
        with _http_errors():
            document = sessions.save_game(game_id, name=request.name)
            return saves.write(document)

    @app.get("/saves")
    def list_saves() -> list[JsonObject]:
        return saves.list()

    @app.post("/saves/{save_id}/load")
    def load_save(save_id: str) -> JsonObject:
        with _http_errors():
            return sessions.restore_game(saves.read(save_id))

    @app.delete("/saves/{save_id}")
    def delete_save(save_id: str) -> JsonObject:
        with _http_errors():
            saves.delete(save_id)
        return {"deleted": save_id}

    @app.get("/games/{game_id}/review")
    def review_game(game_id: str, seat: int) -> JsonObject:
        with _http_errors():
            return sessions.review(game_id, seat)

    @app.get("/games/{game_id}/review/{step}")
    def review_game_state(game_id: str, step: int, seat: int) -> JsonObject:
        with _http_errors():
            return sessions.review_state(game_id, seat, step)

    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
    if images_dir.is_dir():
        app.mount(
            "/card-images",
            StaticFiles(directory=images_dir),
            name="card-images",
        )
    if icon_dir.is_dir():
        app.mount("/icons", StaticFiles(directory=icon_dir), name="icons")
    return app


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate session errors into HTTP status codes."""

    try:
        yield
    except (UnknownGameError, UnknownSaveError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SeatAccessError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except StaleRevisionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (SessionError, SaveError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
