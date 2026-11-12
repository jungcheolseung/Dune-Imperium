"""Kept answers of content lookups by id (2026-11-11 engine speed, stage A).

A card or tile definition never changes once the content is loaded, and the
engine resolves the same instance ids millions of times a game (a search
seat's playouts: ``personal_card_for_instance`` about 4.7 million calls a
game on Uprising with every expansion). ``kept_by_id`` keeps a resolver's
answer for each id it resolved, so later calls return the very object the
resolver returned the first time, which is the object it would return again:
every resolver it wraps reads only module-level tables that nothing changes.

Only an exact ``str`` id is kept, and only a successful answer: any other
argument, and any id that raises, goes through the resolver every time, so
it fails as it always did. A table changed in place after an id was kept
(as a test's monkeypatch would) is not seen: the tables are ``Final``
constants that nothing writes (Codex review r1, accepted).
"""

from collections.abc import Callable
from functools import wraps
from typing import Final

# Only ids shorter than this are kept: no digit run in them reaches Python's
# lowest possible integer-parsing limit (``sys.int_info``'s 640 digits), so a
# kept id parses alike whatever ``sys.set_int_max_str_digits`` says (Codex
# review r4).
_SHORT: Final = 640

# Ids kept per resolver before its table starts over (the content has a few
# thousand ids; a hand-made state may invent more, e.g. "player:57:starter:...").
_LIMIT: Final = 65_536


def kept_by_id[T](resolve: Callable[[str], T]) -> Callable[[str], T]:
    """``resolve`` with its answer kept for each exact ``str`` id."""

    kept: dict[str, T] = {}
    get = kept.get

    @wraps(resolve)
    def lookup(instance_id: str) -> T:
        if type(instance_id) is not str or len(instance_id) >= _SHORT:
            return resolve(instance_id)
        found = get(instance_id)
        if found is None:
            found = resolve(instance_id)
            if len(kept) >= _LIMIT:
                kept.clear()
            kept[instance_id] = found
        return found

    return lookup
