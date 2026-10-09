"""Where the configured seats sit at a new game's table.

docs/rules says nothing about where players sit: the First Player comes
from the Objective deal [Main p. 5] whatever the seat order, and the engine
already deals it from the game seed. Shuffling the seats the setup screen
configured is therefore a project convention, not a rule (user request
2026-10-10, "자리 배치가 랜덤이어야 할듯").

The shuffle happens in the browser, before ``POST /games``: the server's
game creation, its saves and their restore never see a difference. The
server only tells the setup screen (``GET /whoami`` ``seating``) whether its
"shuffle the seats" box opens checked, from the play server's
``--seating`` flag.
"""

from typing import Final

# "random" opens the setup screen's box checked, "fixed" unchecked.
SEATINGS: Final = ("random", "fixed")
DEFAULT_SEATING: Final = "random"
