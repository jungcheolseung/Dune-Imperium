"""Where the configured seats sit at a new game's table.

docs/rules says nothing about where players sit: the First Player comes
from the Objective deal [Main p. 5] whatever the seat order, and the engine
already deals it from the game seed. Shuffling the seats the setup screen
configured is therefore a project convention, not a rule (user request
2026-10-10, "자리 배치가 랜덤이어야 할듯").

The shuffle happens in the browser, before ``POST /games``: the server's
game creation, its saves and their restore never see a difference. On a
remote server the browser also opens a game with a human seat as a room
that waits for its start, which draws the people to the human seats
(``seats_at_start``, ``GameSessionManager.start_game``). The play server's
``--seating`` flag alone decides both, reported by ``GET /whoami``
``seating``: the setup screen has no box for it since the start of a
remote room seats the people at random anyway (user decision 2026-11-01).
"""

from typing import Final

# "random" shuffles the seats (and waits for a remote room's start),
# "fixed" seats row N at seat N.
SEATINGS: Final = ("random", "fixed")
DEFAULT_SEATING: Final = "random"

# The setup screen's "Player 1 starts" box (OQ-132 project convention, user
# decision 2026-10-25): checked, seat 0 takes the Objective with the First
# Player marker (``RulesetConfig.first_player_seat_zero``); unchecked, every
# Objective is dealt at random and whoever gets the marker starts
# [Main p. 5]. The play server's ``--first-player`` flag only sets how the
# box opens: "player1" checked, "deal" unchecked.
FIRST_PLAYERS: Final = ("player1", "deal")
DEFAULT_FIRST_PLAYER: Final = "player1"
