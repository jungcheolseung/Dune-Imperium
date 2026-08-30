"""FastAPI wiring over the framework-neutral game sessions.

Endpoints translate HTTP to ``GameSessionManager`` calls one to one; every
game decision, visibility judgment, and advance lives in the session layer
and, below it, the rules engine. Errors map to conventional status codes:
unknown games are 404, non-human seats 403, stale revisions 409, and every
other invalid request 400.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dune_imperium.server.catalog import build_catalog
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

_STATIC_DIR = Path(__file__).parent / "static"


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
    game_seed: int | None = None
    policy_seed: int | None = None


class ApplyActionRequest(BaseModel):
    """One indexed action from the legal-action listing."""

    seat: int
    revision: int
    index: int


def create_app(manager: GameSessionManager | None = None) -> FastAPI:
    """Build the local play server around one session manager."""

    sessions = manager if manager is not None else GameSessionManager()
    app = FastAPI(title="Dune: Imperium - Uprising local play server")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/catalog")
    def catalog() -> JsonObject:
        return build_catalog()

    @app.post("/games")
    def create_game(request: CreateGameRequest) -> JsonObject:
        with _http_errors():
            return sessions.create_game(
                tuple(request.seats),
                choam_module=request.choam_module,
                leader_draft=request.leader_draft,
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
            )

    @app.delete("/games/{game_id}")
    def delete_game(game_id: str) -> JsonObject:
        with _http_errors():
            sessions.delete(game_id)
        return {"deleted": game_id}

    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
    return app


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate session errors into HTTP status codes."""

    try:
        yield
    except UnknownGameError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SeatAccessError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except StaleRevisionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except SessionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
