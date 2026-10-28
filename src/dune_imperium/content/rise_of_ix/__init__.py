"""Rise of Ix's content (docs/base-game-and-ix-plan.md 17, stage P4).

Its definitions use the types of ``content.uprising`` and share its id
tables (``IMPERIUM_CARDS_BY_ID`` and the like), which import these modules
after their own definitions, as ``content.imperium``'s do: an id names one
printing, so a card whose name another kind already uses takes the
``_card`` suffix (``esmar_tuek_card``, plan 17.2). The Uprising package is
imported here first, so importing a module of this package on its own still
builds the tables in that order.
"""

import dune_imperium.content.uprising  # noqa: F401
