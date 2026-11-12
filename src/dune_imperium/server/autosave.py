"""Autosave for the play server (M14 slice 5, design section 4.7).

A remote game runs for hours on a friend's machine; when that server dies the
table should lose a turn, not the evening. Whenever a turn passes on, or the
game ends, the game's one autosave slot is replaced. The host brings the
game back by loading that save like any other: a new game ID, a new room
link, and every player claims a seat again (saves keep neither tokens nor
names, decision D4).

The session layer decides *when* (``add_hand_over_listener``); this module
only builds the document and hands it to the store.
"""

import threading

from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager, UnknownGameError

AUTOSAVE_NAME_PREFIX = "자동 저장"


class Autosaver:
    """A hand-over listener that keeps one current save per game."""

    def __init__(
        self,
        sessions: GameSessionManager,
        saves: SaveStore,
        *,
        hide_unfinished_seed: bool = False,
    ) -> None:
        self._sessions = sessions
        self._saves = saves
        self._hide_unfinished_seed = hide_unfinished_seed
        # Two requests of one game can finish close together, each on its
        # own thread. The document is built inside this lock as well as
        # written, so whichever writes last has also read last: an older
        # state can never replace a newer one on disk.
        self._lock = threading.Lock()

    def __call__(self, game_id: str) -> None:
        """Replace ``game_id``'s autosave with the game as it rests now.

        Raises what the store raises (a full disk, a read-only directory);
        the session layer logs it and the game goes on unsaved.
        """

        with self._lock:
            try:
                document = self._sessions.save_document(game_id)
            except UnknownGameError:
                # Deleted between the hand-over and this call.
                return
            if document["finished"] is True:
                moment = "종료"
            else:
                moment = f"R{document['round_number']}"
            document["name"] = f"{AUTOSAVE_NAME_PREFIX} · {moment}"
            self._saves.write_autosave(
                game_id, document, hide_unfinished_seed=self._hide_unfinished_seed
            )
