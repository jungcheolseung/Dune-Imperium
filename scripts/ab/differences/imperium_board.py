"""Declared differences of stage P2a (the original game's board and flow)
against master ``12294215`` (codec v155, observation v34).

docs/base-game-and-ix-plan.md 15.4. Every difference is a new field at its
Uprising value, where an Uprising game has no Mentat:

- ``PlayerState`` gains ``mentat`` (the Mentat on the seat's Leader this
  round) and ``track_troops_recruited_turn`` (troops an Influence track
  bonus recruited this turn, the original Emperor track's), and
  ``GameState`` ``mentat_owed_to`` (the Sort Through the Chaos winner owed
  it), all left out of the canonical state hash at their defaults; the
  states the tool digests hold them, so they are declared added.
- Every seat's ``PlayerView`` shows each seat's ``mentat`` and the
  ``mentat_owed_to`` seat, which the observation's ``mentat`` segment reads;
  in an Uprising game they are ``False`` and ``None``.
- Stage P2b's Baron Harkonnen (Masterstroke): ``PlayerState`` gains
  ``masterstroke_factions`` and ``masterstroke_revealed`` (hash-omitted at
  their defaults); each seat's view shows ``masterstroke_secret`` and
  ``masterstroke_revealed_factions``, and the private view the seat's own
  ``masterstroke_factions`` -- ``False``, ``[]`` and ``[]`` in Uprising.

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
        private = view.get("private")
        if isinstance(private, dict) and "masterstroke_factions" not in private:
            private["masterstroke_factions"] = []
            shown = True
        for seat in view["players"]:
            for name, default in (
                ("mentat", False),
                ("masterstroke_secret", False),
                ("masterstroke_revealed_factions", []),
            ):
                if name not in seat:
                    seat[name] = default
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
    state_fields=frozenset(
        {
            "PlayerState.mentat",
            "PlayerState.track_troops_recruited_turn",
            "PlayerState.masterstroke_factions",
            "PlayerState.masterstroke_revealed",
            "GameState.mentat_owed_to",
        }
    ),
)

RULES = (STATE_HOLDS_THE_MENTAT, VIEWS_SHOW_THE_MENTAT)
