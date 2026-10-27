"""Declared differences of stage P1 (the base-game axis) against master
``b964e08f`` (codec v155, observation v33).

Two differences, both new fields at their Uprising values:

- ``RulesetConfig`` gains ``base_game`` and ``rise_of_ix`` (plan 4.2 item
  1), left out of the canonical state hash at their defaults; the state the
  tool digests holds the config, so they are declared added.
- Every seat's ``PlayerView`` names the base game (``base_game``, plan 4.2
  item 8, user decision 2026-10-21), as it names Epic Game Mode, so the
  observation's base-game column can be read from it; in an Uprising game it
  is ``"uprising"``.

Nothing else a player, an agent or a save sees changes. Checked with
``engine_equivalence.py check --differences
scripts/ab/differences/base_game_axis.py``.
"""

from equivalence_rules import Rule, Step


def _name_the_base_game(step: Step) -> bool:
    """Add the base game to the base's views; whether any view was."""

    named = False
    for view in step.views:
        if "base_game" not in view:
            view["base_game"] = "uprising"
            named = True
    return named


VIEW_NAMES_BASE_GAME = Rule(
    name="view_names_base_game",
    why="plan 4.2 item 8: the observation's base-game column reads the view",
    old=_name_the_base_game,
)

CONFIG_NAMES_BASE_GAME = Rule(
    name="config_names_base_game",
    why="plan 4.2 item 1: the ruleset names its base game and Rise of Ix",
    state_fields=frozenset({"RulesetConfig.base_game", "RulesetConfig.rise_of_ix"}),
)

RULES = (CONFIG_NAMES_BASE_GAME, VIEW_NAMES_BASE_GAME)
