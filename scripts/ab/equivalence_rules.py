"""Declared differences for ``engine_equivalence.py check --differences``.

The cleanup stage of the composed-effects switch (docs/composed-effects-plan.md
5, "정리 단계") changes what a player or an agent sees on purpose: event names
and payloads, rows, windows that open or no longer open. A stage declares each
such change as a ``Rule`` in a module that defines ``RULES: tuple[Rule, ...]``;
``check`` translates the base engine's recording with them before comparing,
so every undeclared difference is still caught (the plan's "정해진 차이 목록").

Content is canonical (``records.portable.trace.canonical``): JSON-like lists,
dicts, strings and numbers, the form ``record`` stores. One recorded step is a
``Step``:

- ``step``: ``("a", action_id, actor, arguments)`` or ``("c", decision_id,
  values)``;
- ``decision``: a player decision's ``[owner, [actions...]]`` or a chance
  decision's ``[decision_id, options, count, with_replacement]``;
- ``page``: the page metadata parts (``engine_equivalence.PAGE_PARTS``), or
  ``None`` at a chance decision;
- ``events``: the step's events;
- ``views``: every seat's ``PlayerView`` before the step (parsed when a rule
  first reads it; edits are compared).

A rule may define any of these hooks. The tool counts a rule as applied on a
step when the hook changed the step (or returned moves or a move), whatever
the hook returns, and lists the rules that never applied:

- ``old(step)``: rewrite the base's step into the candidate's form, in place
  (rename an event, drop a refusal row, rename the recorded move in
  ``step.step``, which is then the move replayed), or set ``step.vanish`` when
  the candidate has no such step (a refusal the candidate no longer asks for);
- ``new(old, candidate)``: normalise the candidate's content of the same step
  in place, when the base cannot be rewritten into it (a row or event only the
  candidate has); ``candidate`` is a ``Step`` built from the candidate engine,
  with ``events`` holding everything the step and its answered decisions
  produced (empty, with no views, decision or page, at a vanished step);
- ``moves(old, at)``: the candidate's moves for a recorded step, when they are
  not the recorded one -- a tuple of ``DomainAction`` / ``ChanceOutcome``; an
  empty tuple when the candidate has no step there; ``None`` when the rule does
  not apply;
- ``answer(at)``: a move for a candidate decision the base did not have (a new
  confirm window, an order the base fixed, a choice the candidate asks before
  the base did -- ``at.rows[at.index + 1:]`` are the steps the base recorded
  after this one), or ``None``; the tool asks after every step's moves until
  no rule answers, and adds those moves' events to the step's.

A hook may set ``step.state_unchecked`` on either step to leave the state
after it out of the comparison, where the candidate reaches the base's state
a few steps later on purpose; the steps after it are compared in full again.
``step.fields_unchecked`` leaves only the named digest fields out
(``"players[1].hand"``, as the report names them), for that step only.

``state_fields`` names the state fields the candidate adds, drops or changes on
purpose as ``"<Class>.<field>"``: ``"GameState.scouts_round"``, or
``"PlayerState.hand"`` for every seat's. They are left out of the state
comparison. A nested dataclass's field (``"Resources.foo"``) may be declared
only as added: the base's digests hold the whole top-level field, so a nested
field the candidate drops or changes needs its holder declared as well
(``"PlayerState.resources"``), which leaves the holder out entirely. A
declaration holds for every step of every game.

A vanished step compares only its events (the base's, translated, against
none) and the state after it. Answered decisions are not compared themselves
(the summary lists their windows); their events and the state after them are,
with the step they follow. The ``revision`` in the candidate's views is
shifted by the number of moves the candidate made more or fewer than the
base, so it stays compared. Anything else that counts moves or logged events
moves with them too (the ``shortfall_refilled`` event ids count the event
log) and needs its own rule.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    """One step's canonical content (see the module doc)."""

    index: int
    step: tuple[Any, ...]
    decision: Any = None
    page: Any = None
    events: list[Any] = field(default_factory=list)
    views_text: str = ""
    vanish: bool = False
    # Set by a hook: the state after this step is left out of the comparison
    # (the candidate reaches the base's state a few steps later on purpose).
    state_unchecked: bool = False
    # Set by a hook: these state digest fields (``"players[1].hand"``) are
    # left out of the comparison after this step only.
    fields_unchecked: set[str] = field(default_factory=set)
    _views: list[Any] | None = None

    @property
    def views(self) -> list[Any]:
        if self._views is None:
            self._views = json.loads(self.views_text) if self.views_text else []
        return self._views

    def views_now(self) -> str:
        """The views as compared: re-dumped when a rule has read them."""

        if self._views is None:
            return self.views_text
        return json.dumps(self._views, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class At:
    """The candidate engine where a recorded step is about to be compared."""

    engine: Any
    state: Any
    decision: Any
    legal: tuple[Any, ...]
    old: Step
    # The recording's rows and the recorded step's index in them, so an
    # answer may take a choice the base made later.
    rows: Sequence[Any] = ()
    index: int = -1


@dataclass(frozen=True)
class Rule:
    """One declared difference (see the module doc)."""

    name: str
    # The plan decision, rule citation or reason this difference is wanted.
    why: str
    old: Callable[[Step], Any] | None = None
    new: Callable[[Step, Step], Any] | None = None
    moves: Callable[[Step, At], tuple[Any, ...] | None] | None = None
    answer: Callable[[At], Any] | None = None
    state_fields: frozenset[str] = frozenset()
