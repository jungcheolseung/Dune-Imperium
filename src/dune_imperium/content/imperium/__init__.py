"""The original Dune: Imperium's content (docs/base-game-and-ix-plan.md P2).

Its definitions use the types of ``content.uprising`` and share its id
tables (``BOARD_SPACES_BY_ID`` and the like), which import these modules
after their own definitions: an id names one printing, so a space or card
printed alike in both base games is Uprising's definition itself and one
printed differently takes its own id (plan 4.2 item 7). The Uprising
package is imported here first (its ``__init__`` builds every Uprising
module), so importing a module of this package on its own still builds the
tables in that order: each Uprising module reaches its ``content.imperium``
import after the names this package's modules take from it.
"""

import dune_imperium.content.uprising  # noqa: F401
