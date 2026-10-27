"""Declared differences of stage P2a (the original game's board and flow)
against master ``12294215`` (codec v155, observation v34).

docs/base-game-and-ix-plan.md 15.4. Every difference is a new field at its
Uprising value, where an Uprising game has no Mentat:

- ``PlayerState`` gains ``mentat`` (the Mentat on the seat's Leader this
  round) and ``GameState`` ``mentat_owed_to`` (the Sort Through the Chaos
  winner owed it), both left out of the canonical state hash at their
  defaults; the states the tool digests hold them, so they are declared
  added.
- Every seat's ``PlayerView`` shows each seat's ``mentat`` and the
  ``mentat_owed_to`` seat, which the observation's ``mentat`` segment reads;
  in an Uprising game they are ``False`` and ``None``.

Nothing else a player, an agent or a save sees changes. Checked with
``engine_equivalence.py check --differences
scripts/ab/differences/imperium_board.py``.
"""

from equivalence_rules import Rule, Step


def _show_no_mentat(step: Step) -> bool:
    """Add the Mentat's fields at their Uprising values to the base's views;
    whether any view was."""

    shown = False
    for view in step.views:
        if "mentat_owed_to" not in view:
            view["mentat_owed_to"] = None
            shown = True
        for seat in view["players"]:
            if "mentat" not in seat:
                seat["mentat"] = False
                shown = True
    return shown


VIEWS_SHOW_THE_MENTAT = Rule(
    name="views_show_the_mentat",
    why="plan 15.4: the observation's mentat segment reads the view",
    old=_show_no_mentat,
)

STATE_HOLDS_THE_MENTAT = Rule(
    name="state_holds_the_mentat",
    why="plan 15.4: the seat holding the Mentat and the seat owed it",
    state_fields=frozenset({"PlayerState.mentat", "GameState.mentat_owed_to"}),
)

RULES = (STATE_HOLDS_THE_MENTAT, VIEWS_SHOW_THE_MENTAT)
