"""FastAPI wiring over the framework-neutral game sessions.

Endpoints translate HTTP to ``GameSessionManager`` calls one to one; every
game decision, visibility judgment, and advance lives in the session layer
and, below it, the rules engine. Errors map to conventional status codes:
unknown games and saves are 404, non-human seats, seats the client does not
hold and host operations without the admin key 403, stale revisions and
seats already taken 409, and every other invalid request 400.

Save files live on the server's local disk (``SaveStore``); HTTP responses
only ever carry save metadata because the full document records shuffle
outcomes and with them hidden deck orders.

On a remote server (M14, ``docs/multiplayer-design.md``) a client proves
itself with cookies: one ``HttpOnly`` cookie per claimed seat, scoped to
that game's path, and one for the host's admin key. This module only moves
them between the request and ``Credentials``; the session layer judges.
Cookies rather than header tokens because ``EventSource`` and ``<img>``
cannot send headers, and because a token must never show in the address
bar of a player who is sharing their screen.

``GET /games/{id}/events`` is the doorbell (M14 slice 3, ``events``): a
Server-Sent Events stream of public fields that tells a browser *that* the
game changed. What changed it then fetches itself, through the judged
snapshot call, so the stream never has to be filtered per seat.
"""

import os
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Final

import anyio
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dune_imperium.display.images import resolve_card_images
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.autosave import Autosaver
from dune_imperium.server.catalog import build_catalog, card_image_url
from dune_imperium.server.events import DEFAULT_HEARTBEAT_SECONDS, DoorbellHub
from dune_imperium.server.persistence import (
    SaveError,
    SaveStore,
    UnknownSaveError,
    default_saves_directory,
)
from dune_imperium.server.sessions import (
    AdminAccessError,
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SeatTakenError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

ADMIN_COOKIE: Final = "dune_admin"
_SEAT_COOKIE_PREFIX: Final = "dune_seat_"
# A game runs for an evening but may be resumed weeks later; the cookie
# dies earlier anyway when its seat is released or the server restarts.
_COOKIE_MAX_AGE: Final = 30 * 24 * 60 * 60
# Below this a response fits one packet anyway and compressing it is waste.
_GZIP_MINIMUM_SIZE: Final = 1024

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


def asset_url_versions(files: Mapping[str, Path]) -> frozenset[tuple[str, str]]:
    """Return ``(url, version)`` for every asset URL whose file exists.

    The version is the file's modification time and size, so replacing a
    picture in place (same name, same URL) gives the catalog a new
    ``?v=`` and the browsers fetch it instead of reusing what they cached:
    the asset mounts send only ``Last-Modified``/``ETag``, which lets a
    browser serve an old file for days without asking. Read once at server
    start, like the file listings themselves.
    """

    versions: set[tuple[str, str]] = set()
    for url, path in files.items():
        try:
            stat = path.stat()
        except OSError:
            continue
        versions.add((url, f"{stat.st_mtime_ns // 1_000_000:x}-{stat.st_size:x}"))
    return frozenset(versions)


def default_tokens_directory() -> Path:
    """Return the local pictured-token location (the Combat markers).

    ``DUNE_IMPERIUM_TOKEN_DIR`` overrides the default ``assets/tokens``
    (``dune_imperium.display.token_images`` names the files). Optional like the
    icons: without it the UI draws its own seat tokens.
    """

    override = os.environ.get("DUNE_IMPERIUM_TOKEN_DIR")
    if override:
        return Path(override)
    return _ASSETS_DIR / "tokens"


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


def default_bene_tleilax_image_path() -> Path:
    """Return the owner's local Bene Tleilax board scan (Immortality).

    ``DUNE_IMPERIUM_BENE_TLEILAX_IMAGE`` overrides the default
    ``assets/board/bene_tleilax.jpg``. Without the file the UI draws a
    synthetic research grid instead.
    """

    override = os.environ.get("DUNE_IMPERIUM_BENE_TLEILAX_IMAGE")
    if override:
        return Path(override)
    return _ASSETS_DIR / "board" / "bene_tleilax.jpg"


class CreateGameRequest(BaseModel):
    """Configuration for one new game."""

    seats: list[str] = Field(
        default=["human", "heuristic", "heuristic", "heuristic"],
        min_length=4,
        max_length=4,
        description=(
            "Per-seat assignment: 'human', or an agent kind of the evaluation "
            "registry: 'heuristic', 'random', 'rollout' (determinized search), "
            "'rollout_strong' (the same search at twice the budget), "
            "'checkpoint:<path>' (a trained policy; needs the train extra), or "
            "'search:<path>' (that policy with determinized search around it: "
            "much stronger, about 2s a decision)."
        ),
    )
    choam_module: bool = False
    leader_draft: bool = False
    # Shuffle in the promo Imperium cards (not in the retail decks): the
    # three Uprising promos, plus the Bloodlines promo Ruthless Leadership
    # when the expansion is on (see docs/implementation-plan.md M6, M12).
    promo_cards: bool = False
    # The Bloodlines expansion and its Tech Module (docs/rules/bloodlines.md).
    bloodlines: bool = False
    tech_module: bool = False
    # The Immortality expansion (docs/rules/immortality.md).
    immortality: bool = False
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


class ConfirmTurnRequest(BaseModel):
    """Hand the turn over after the seat's still-undoable steps."""

    seat: int
    revision: int
    undo_count: int | None = None


class SaveGameRequest(BaseModel):
    """Optional display name for one new save."""

    name: str | None = Field(default=None, max_length=120)


class AdminLoginRequest(BaseModel):
    """The host's admin key, as printed by the server at startup."""

    key: str = Field(min_length=1, max_length=200)


class ClaimSeatRequest(BaseModel):
    """The name a player sits down under.

    The session layer cleans it and enforces the real length limit; the
    bound here only keeps a request body small.
    """

    name: str = Field(max_length=200)


class _RevalidateUIFiles:
    """Make browsers revalidate ``index.html`` and ``/static`` on every load.

    The UI is edited in place while the server runs; ``no-cache`` (the ETag
    keeps it cheap) stops a browser from heuristically caching a stale
    ``app.js``.

    This wraps the ASGI ``send`` instead of using ``@app.middleware("http")``:
    Starlette's ``BaseHTTPMiddleware`` raises ``RuntimeError("No response
    returned.")`` for every request whose client leaves before the response
    starts, and a page that reopens its doorbell closes an event stream it
    has only just asked for. uvicorn logged a traceback for each of those.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope["path"] if scope["type"] == "http" else None
        if path is None or not (path == "/" or path.startswith("/static/")):
            await self._app(scope, receive, send)
            return

        async def send_revalidating(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = "no-cache"
            await send(message)

        await self._app(scope, receive, send_revalidating)


def seat_cookie_name(game_id: str, seat: int) -> str:
    """Name of the cookie that carries one claimed seat's token."""

    return f"{_SEAT_COOKIE_PREFIX}{game_id}_{seat}"


def _credentials(request: Request, game_id: str | None = None) -> Credentials:
    """Collect what a request presents: its seat tokens for one game, and admin.

    Which seat a token belongs to is decided by comparing values in the
    session layer, never by trusting a cookie's name.
    """

    seat_tokens: frozenset[str] = frozenset()
    if game_id is not None:
        prefix = f"{_SEAT_COOKIE_PREFIX}{game_id}_"
        seat_tokens = frozenset(
            value for name, value in request.cookies.items() if name.startswith(prefix)
        )
    return Credentials(
        seat_tokens=seat_tokens, admin_key=request.cookies.get(ADMIN_COOKIE)
    )


def create_app(
    manager: GameSessionManager | None = None,
    saves_dir: Path | None = None,
    card_images_dir: Path | None = None,
    icons_dir: Path | None = None,
    tokens_dir: Path | None = None,
    board_image: Path | None = None,
    bene_tleilax_image: Path | None = None,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
    public_url: str | None = None,
    autosave: bool | None = None,
) -> FastAPI:
    """Build the local play server around one session manager.

    ``public_url`` is the address the other players reach this server at
    (a Tailscale IP, a tunnel); the host's browser builds the room link from
    it, because the host itself may well be looking at 127.0.0.1.

    ``autosave`` keeps one current save per game, replaced whenever a turn
    passes on (``server.autosave``). Left at ``None`` it follows the access
    mode: on for a remote server, off for an open one, whose save
    directory holds what its one user chose to save and nothing else.
    """

    sessions = manager if manager is not None else GameSessionManager()
    hub = DoorbellHub()
    sessions.add_change_listener(hub.publish)
    saves = SaveStore(
        saves_dir if saves_dir is not None else default_saves_directory()
    )
    images_dir = (
        card_images_dir
        if card_images_dir is not None
        else default_card_images_directory()
    )
    # One index per UI language: each prefers its own language's picture
    # and falls back to the other's per file (the catalog pairs them).
    image_index = frozenset(
        (kind, content_id, path)
        for (kind, content_id), path in resolve_card_images(
            images_dir, ("en", "ko")
        ).items()
    )
    image_index_ko = frozenset(
        (kind, content_id, path)
        for (kind, content_id), path in resolve_card_images(
            images_dir, ("ko", "en")
        ).items()
    )
    icon_dir = icons_dir if icons_dir is not None else default_icons_directory()
    icon_files = (
        frozenset(path.name for path in icon_dir.iterdir() if path.is_file())
        if icon_dir.is_dir()
        else frozenset()
    )
    token_dir = tokens_dir if tokens_dir is not None else default_tokens_directory()
    token_files = (
        frozenset(path.name for path in token_dir.iterdir() if path.is_file())
        if token_dir.is_dir()
        else frozenset()
    )
    board_path = (
        board_image if board_image is not None else default_board_image_path()
    )
    bene_tleilax_path = (
        bene_tleilax_image
        if bene_tleilax_image is not None
        else default_bene_tleilax_image_path()
    )
    asset_versions = asset_url_versions(
        {
            card_image_url(path): images_dir / path
            for _, _, path in image_index | image_index_ko
        }
        | {f"/icons/{name}": icon_dir / name for name in icon_files}
        | {f"/tokens/{name}": token_dir / name for name in token_files}
        | {"/board-image": board_path, "/bene-tleilax-image": bene_tleilax_path}
    )
    app = FastAPI(title="Dune: Imperium - Uprising local play server")
    # Whoever runs the server ends the open event streams through this when
    # it is asked to stop (``cli.server``); they never end by themselves.
    app.state.doorbell_hub = hub
    # JSON and the UI files shrink four- to tenfold, which is what a remote
    # player's refresh is made of. Starlette's default exclusions already
    # skip the card and board scans and ``text/event-stream``.
    app.add_middleware(GZipMiddleware, minimum_size=_GZIP_MINIMUM_SIZE)
    app.add_middleware(_RevalidateUIFiles)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/catalog")
    def catalog() -> JsonObject:
        return build_catalog(
            image_index,
            icon_files,
            board_path.is_file(),
            bene_tleilax_image=bene_tleilax_path.is_file(),
            token_files=token_files,
            asset_versions=asset_versions,
            image_index_ko=image_index_ko,
        )

    @app.get("/board-image", include_in_schema=False)
    def board_image_file() -> FileResponse:
        if not board_path.is_file():
            raise HTTPException(status_code=404, detail="no board image")
        return FileResponse(board_path)

    @app.get("/bene-tleilax-image", include_in_schema=False)
    def bene_tleilax_image_file() -> FileResponse:
        if not bene_tleilax_path.is_file():
            raise HTTPException(status_code=404, detail="no Bene Tleilax board image")
        return FileResponse(bene_tleilax_path)

    # A remote server's host plays too, so the seed of a game in progress
    # stays out of the save listings it serves (see ``save_metadata``).
    hide_unfinished_seed = sessions.access is AccessMode.REMOTE
    autosaving = (
        autosave if autosave is not None else sessions.access is AccessMode.REMOTE
    )
    if autosaving:
        sessions.add_hand_over_listener(
            Autosaver(sessions, saves, hide_unfinished_seed=hide_unfinished_seed)
        )

    @app.get("/whoami")
    def who_is_asking(request: Request) -> JsonObject:
        # What a browser needs before any game exists: whether seats have to
        # be claimed here at all, and whether it is the host's browser.
        admin = sessions.is_admin(_credentials(request))
        return {
            "access": str(sessions.access),
            "admin": admin,
            "public_url": public_url if admin else None,
            "autosave": autosaving,
        }

    @app.post("/auth/admin")
    def admin_login(body: AdminLoginRequest, response: Response) -> JsonObject:
        with _http_errors():
            sessions.admin_login(body.key)
        response.set_cookie(
            ADMIN_COOKIE,
            body.key,
            max_age=_COOKIE_MAX_AGE,
            path="/",
            httponly=True,
            samesite="strict",
        )
        return {"admin": True}

    @app.post("/games")
    def create_game(body: CreateGameRequest, request: Request) -> JsonObject:
        with _http_errors():
            return sessions.create_game(
                tuple(body.seats),
                choam_module=body.choam_module,
                leader_draft=body.leader_draft,
                promo_cards=body.promo_cards,
                bloodlines=body.bloodlines,
                tech_module=body.tech_module,
                immortality=body.immortality,
                game_seed=body.game_seed,
                policy_seed=body.policy_seed,
                credentials=_credentials(request),
            )

    @app.get("/games")
    def list_games(request: Request) -> list[JsonObject]:
        with _http_errors():
            return sessions.list_games(credentials=_credentials(request))

    @app.get("/games/{game_id}")
    def game_summary(game_id: str) -> JsonObject:
        with _http_errors():
            return sessions.summary(game_id)

    @app.get("/games/{game_id}/me")
    def who_am_i(game_id: str, request: Request) -> JsonObject:
        with _http_errors():
            return sessions.identify(
                game_id, credentials=_credentials(request, game_id)
            )

    @app.get("/games/{game_id}/snapshot")
    def game_snapshot(
        game_id: str,
        request: Request,
        seat: int | None = None,
        log_after: int = 0,
        log_epoch: str | None = None,
    ) -> JsonObject:
        with _http_errors():
            return sessions.snapshot(
                game_id,
                seat,
                log_after=log_after,
                log_epoch=log_epoch,
                credentials=_credentials(request, game_id),
            )

    @app.get("/games/{game_id}/events")
    async def game_events(game_id: str, request: Request) -> StreamingResponse:
        credentials = _credentials(request, game_id)
        with _http_errors():
            # An unknown game is a plain 404, not a stream that ends at once.
            # Session calls take the session lock, which an advancing AI seat
            # may hold for a while, so they stay off the event loop.
            await run_in_threadpool(sessions.doorbell, game_id)

        async def current() -> JsonObject | None:
            try:
                return await run_in_threadpool(sessions.doorbell, game_id)
            except UnknownGameError:
                return None

        async def body() -> AsyncIterator[str]:
            # Connecting inside the generator pairs it with the disconnect
            # below even when the client is gone before the first byte.
            try:
                connection = await run_in_threadpool(
                    sessions.connect, game_id, credentials=credentials
                )
            except UnknownGameError:
                connection = None
            try:
                async for chunk in hub.stream(
                    game_id, current, heartbeat_seconds=heartbeat_seconds
                ):
                    yield chunk
            finally:
                if connection is not None:
                    # The stream ends by cancellation when the client
                    # leaves; presence must still be taken down.
                    with anyio.CancelScope(shield=True):
                        await run_in_threadpool(
                            sessions.disconnect, game_id, connection
                        )

        return StreamingResponse(
            body(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/games/{game_id}/seats/{seat}/claim")
    def claim_seat(
        game_id: str,
        seat: int,
        body: ClaimSeatRequest,
        request: Request,
        response: Response,
    ) -> JsonObject:
        with _http_errors():
            claim = sessions.claim_seat(
                game_id,
                seat,
                body.name,
                credentials=_credentials(request, game_id),
            )
        response.set_cookie(
            seat_cookie_name(game_id, seat),
            claim.token,
            max_age=_COOKIE_MAX_AGE,
            path=f"/games/{game_id}",
            httponly=True,
            samesite="strict",
        )
        return claim.summary

    @app.post("/games/{game_id}/seats/{seat}/release")
    def release_seat(
        game_id: str, seat: int, request: Request, response: Response
    ) -> JsonObject:
        with _http_errors():
            summary = sessions.release_seat(
                game_id, seat, credentials=_credentials(request, game_id)
            )
        # Harmless when the host released someone else's seat: that
        # browser's cookie simply stopped matching anything.
        response.delete_cookie(
            seat_cookie_name(game_id, seat),
            path=f"/games/{game_id}",
            httponly=True,
            samesite="strict",
        )
        return summary

    @app.get("/games/{game_id}/seats/{seat}/view")
    def seat_view(game_id: str, seat: int, request: Request) -> JsonObject:
        with _http_errors():
            return sessions.view(
                game_id, seat, credentials=_credentials(request, game_id)
            )

    @app.get("/games/{game_id}/seats/{seat}/actions")
    def seat_actions(game_id: str, seat: int, request: Request) -> JsonObject:
        with _http_errors():
            return sessions.legal_actions(
                game_id, seat, credentials=_credentials(request, game_id)
            )

    @app.post("/games/{game_id}/actions")
    def apply_action(
        game_id: str, body: ApplyActionRequest, request: Request
    ) -> JsonObject:
        with _http_errors():
            return sessions.apply_action(
                game_id,
                seat=body.seat,
                revision=body.revision,
                index=body.index,
                undo_count=body.undo_count,
                credentials=_credentials(request, game_id),
            )

    @app.post("/games/{game_id}/undo")
    def undo_steps(game_id: str, body: UndoRequest, request: Request) -> JsonObject:
        with _http_errors():
            return sessions.undo(
                game_id,
                seat=body.seat,
                revision=body.revision,
                steps=body.steps,
                undo_count=body.undo_count,
                credentials=_credentials(request, game_id),
            )

    @app.post("/games/{game_id}/confirm")
    def confirm_turn(
        game_id: str, body: ConfirmTurnRequest, request: Request
    ) -> JsonObject:
        with _http_errors():
            return sessions.confirm_turn(
                game_id,
                seat=body.seat,
                revision=body.revision,
                undo_count=body.undo_count,
                credentials=_credentials(request, game_id),
            )

    @app.get("/games/{game_id}/log")
    def game_log(
        game_id: str, seat: int, request: Request, after: int = 0
    ) -> JsonObject:
        with _http_errors():
            return sessions.log(
                game_id,
                seat,
                after=after,
                credentials=_credentials(request, game_id),
            )

    @app.delete("/games/{game_id}")
    def delete_game(game_id: str, request: Request) -> JsonObject:
        with _http_errors():
            sessions.delete(game_id, credentials=_credentials(request))
        return {"deleted": game_id}

    @app.post("/games/{game_id}/save")
    def save_game(game_id: str, body: SaveGameRequest, request: Request) -> JsonObject:
        with _http_errors():
            document = sessions.save_game(
                game_id, name=body.name, credentials=_credentials(request)
            )
            return saves.write(document, hide_unfinished_seed=hide_unfinished_seed)

    @app.get("/saves")
    def list_saves(request: Request) -> list[JsonObject]:
        with _http_errors():
            sessions.require_admin(_credentials(request))
            return saves.list(hide_unfinished_seed=hide_unfinished_seed)

    @app.post("/saves/{save_id}/load")
    def load_save(save_id: str, request: Request) -> JsonObject:
        with _http_errors():
            credentials = _credentials(request)
            # Checked before the file is read so a stranger learns nothing
            # about which save IDs exist.
            sessions.require_admin(credentials)
            return sessions.restore_game(saves.read(save_id), credentials=credentials)

    @app.delete("/saves/{save_id}")
    def delete_save(save_id: str, request: Request) -> JsonObject:
        with _http_errors():
            sessions.require_admin(_credentials(request))
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
    if token_dir.is_dir():
        app.mount("/tokens", StaticFiles(directory=token_dir), name="tokens")
    return app


@contextmanager
def _http_errors() -> Iterator[None]:
    """Translate session errors into HTTP status codes."""

    try:
        yield
    except (UnknownGameError, UnknownSaveError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (SeatAccessError, AdminAccessError) as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (StaleRevisionError, SeatTakenError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (SessionError, SaveError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
