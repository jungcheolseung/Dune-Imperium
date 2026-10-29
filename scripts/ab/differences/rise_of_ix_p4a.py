"""Declared differences of stage P4a so far against ``6352199d`` (master's
P3 merge, codec v156, observation v38): observation v39's Rise of Ix fields
(``rise_of_ix_v39.py``, whose rules this module includes) and OQ-149.

docs/rules/open-questions.md OQ-149, user ruling 2026-10-29 ("(가) 둘 다
기록"): a seat that looked at the Intrigue deck's top two cards with
Imperium Ceremony and put one back on top knows that card
(``rules.intrigue_knowledge``). An Uprising game with Immortality therefore
changes once a seat resolves Imperium Ceremony:

- ``PlayerState.known_intrigue_ids`` holds the card put back (and keeps it
  while another seat holds it): already declared changed by
  ``rise_of_ix_v39.STATE_HOLDS_RISE_OF_IX``;
- that seat's ``PrivatePlayerView`` shows it in ``known_intrigue_top`` and,
  by its depth from the deck's bottom, in ``known_intrigue_bottom`` (the v39
  view lists every known deck card there, the top one included), or in
  ``known_intrigue_held`` once another seat drew it.

Nothing else changes: the legal rows, the pages, the events and their
payloads stay as they were. The view difference is declared as exactly
that: the candidate's three fields are set back to their defaults only for a
seat whose own candidate view showed those very cards among its
``peeked_intrigue_ids`` at this or an earlier step of the game, so a card
it never saw is still reported. Checked with ``engine_equivalence.py check
--differences scripts/ab/differences/rise_of_ix_p4a.py``.
"""

import importlib.util
from pathlib import Path
from typing import Any

from equivalence_rules import Rule, Step


def _v39_rules() -> tuple[Rule, ...]:
    path = Path(__file__).with_name("rise_of_ix_v39.py")
    spec = importlib.util.spec_from_file_location("rise_of_ix_v39", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rules: tuple[Rule, ...] = module.RULES
    return rules


# Per game (a lower step index starts another): the Intrigue cards each
# seat's candidate view has shown it in ``peeked_intrigue_ids`` so far.
_peeked: dict[int, set[str]] = {}
_last_index = [-1]


def _known(private: dict[str, Any]) -> set[str]:
    cards = {str(card) for _, card in private.get("known_intrigue_held", [])}
    cards.update(str(card) for _, card in private.get("known_intrigue_bottom", []))
    if private.get("known_intrigue_top"):
        cards.add(str(private["known_intrigue_top"]))
    return cards


def _normalise_known_intrigue(old: Step, candidate: Step) -> bool:
    """Set the candidate's known Intrigue back to the base's defaults where
    the seat saw those cards in its own Imperium Ceremony peek."""

    if candidate.index < _last_index[0]:
        _peeked.clear()
    _last_index[0] = candidate.index
    changed = False
    for view in candidate.views:
        private = view.get("private")
        if not isinstance(private, dict):
            continue
        seat = int(view["player"])
        seen = _peeked.setdefault(seat, set())
        seen.update(str(card) for card in private.get("peeked_intrigue_ids", []))
        known = _known(private)
        if known and known <= seen:
            private["known_intrigue_top"] = ""
            private["known_intrigue_bottom"] = []
            private["known_intrigue_held"] = []
            changed = True
    return changed


CANDIDATE_KNOWS_THE_CARD_PUT_BACK = Rule(
    name="candidate_knows_the_card_put_back",
    why=(
        'OQ-149, user ruling 2026-10-29 "(가) 둘 다 기록": the seat that put '
        "an Intrigue card back on top with Imperium Ceremony knows it"
    ),
    new=_normalise_known_intrigue,
)

RULES = (*_v39_rules(), CANDIDATE_KNOWS_THE_CARD_PUT_BACK)
