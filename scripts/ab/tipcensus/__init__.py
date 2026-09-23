"""Tip census: per-seat statistics that test players' strategy tips.

See ``scripts/ab/tip_census.py`` for the driver and
``docs/player-tips-for-training.md`` for what each column is for. Each module
below exports ``COLLECTORS``, a tuple of ``Collector`` subclasses; the driver
runs every one of them (or the ``--collectors`` subset) over each game.
"""

COLLECTOR_MODULES = ("deck", "combat", "influence", "endgame")

