"""Print the original game's or Rise of Ix's card entries from the app's table.

docs/base-game-and-ix-plan.md 11 (1) and 13.5 D4-1: the numbers, icons,
copies and Factions of a card are generated, never typed by hand, from the
app AI's attribute table (``agents/app_ai/data/archetypes.py``, already in
this repository). The machine comparison tests
(``tests/unit/content/test_imperium_app_table.py`` and
``test_rise_of_ix_app_table.py``) read the same table.

``--set base`` (the default) is the original game with its three promos;
``--set ix`` is Rise of Ix (plan 17.7): its 29 Imperium kinds, the promo
Boundless Ambition and its 17 Intrigue cards. The option goes before or
after the command.

- ``skeleton``: an identity entry (id, name, copies, cost) for every card
  of the set, for a stage that lists the cards before their play data
  (``play_data_complete`` stays False, so no attribute may be set;
  ``ImperiumCardEntry`` refuses partial play data).
- ``full NAME...``: the attribute fields of a card for the transcriber who
  completes it (Factions, Agent icons, printed Reveal values).

    uv run python scripts/dwgr/imperium_entries.py skeleton
    uv run python scripts/dwgr/imperium_entries.py --set ix skeleton
    uv run python scripts/dwgr/imperium_entries.py full "Gun Thopter"
    uv run python scripts/dwgr/imperium_entries.py full --set ix "Treachery"
"""

import argparse
import re
from typing import Final

from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype

# The app's Agent icon names (cards-compact.md: Pentagon/Circle/Triangle are
# Landsraad/City/Spice Trade) -> ``AgentIcon`` members.
AGENT_ICONS: Final = {
    "Emperor": "EMPEROR",
    "SpacingGuild": "SPACING_GUILD",
    "BeneGesserit": "BENE_GESSERIT",
    "Fremen": "FREMEN",
    "Pentagon": "LANDSRAAD",
    "Circle": "CITY",
    "Triangle": "SPICE_TRADE",
}
FACTIONS: Final = {
    "Emperor": "EMPEROR",
    "SpacingGuild": "SPACING_GUILD",
    "BeneGesserit": "BENE_GESSERIT",
    "Fremen": "FREMEN",
}
# A name another kind already uses takes ``_card`` (plan 16.2: no new
# cross-kind id; ``foldspace_card`` is the P2 case): the Uprising Intrigue
# card ``crysknife``, six Uprising or Bloodlines Leaders, and Rise of Ix's
# Imperium card Esmar Tuek, whose name is a Bloodlines Leader (plan 17.2).
ID_OVERRIDES: Final = {
    name: re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") + "_card"
    for name in (
        "Crysknife",
        "Chani",
        "Duncan Idaho",
        "Gurney Halleck",
        "Lady Jessica",
        "Liet Kynes",
        "Piter De Vries",
        "Esmar Tuek",
    )
}
# The original game's three promos (plan 9 8); the app's other promo
# archetypes are Uprising's and Rise of Ix's.
BASE_PROMOS: Final = frozenset({"Duncan, Loyal Blade", "Jessica of Arrakis", "Thumper"})
# Rise of Ix's one promo (plan 9 8, 17.7).
IX_PROMOS: Final = frozenset({"Boundless Ambition"})
SETS: Final = ("base", "ix")


def title(archetype: Archetype) -> str:
    raw = archetype.title or ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def card_id(archetype: Archetype) -> str:
    name = title(archetype)
    if name in ID_OVERRIDES:
        return ID_OVERRIDES[name]
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("'", "")).strip("_")


def set_archetypes(card_set: str, kind: str) -> tuple[Archetype, ...]:
    """The archetypes of ``kind`` (``imperium`` with its promos, or
    ``intrigue``) in ``card_set`` (``base``: the original game; ``ix``: Rise
    of Ix), in the app's order."""

    group, promos = (
        ("BaseSet", BASE_PROMOS) if card_set == "base" else ("RiseOfIx", IX_PROMOS)
    )
    if kind == "intrigue":
        return tuple(
            archetype
            for short, archetype in ARCHETYPES.items()
            if short.startswith(f"IntrigueArchetypes.{group}.")
        )
    # The Imperium deck's cards, not the starting cards (Rise of Ix's Control
    # the Spice, the Epic starting card of ``content/uprising``) or the
    # Reserve; the promos come after them whatever the app's order is.
    deck = tuple(
        archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith(f"ImperiumArchetypes.{group}.")
        and archetype.attributes.get("ImperiumType") == "Main"
    )
    promo_cards = tuple(
        archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("ImperiumArchetypes.Promo.") and title(archetype) in promos
    )
    return deck + promo_cards


def original_archetypes(kind: str) -> tuple[Archetype, ...]:
    """The original game's archetypes of ``kind``."""

    return set_archetypes("base", kind)


def is_promo(archetype: Archetype) -> bool:
    return ".Promo." in archetype.short


def skeleton(archetype: Archetype, helper_prefix: str = "") -> str:
    """An identity entry; Rise of Ix's helpers are ``ix_imperium_card`` and
    ``ix_intrigue_card`` (``helper_prefix`` ``ix_``)."""

    name = title(archetype).replace('"', '\\"')
    copies = archetype.attributes["CardCount"]
    identity = f'("{card_id(archetype)}", "{name}")'
    if archetype.kind == "intrigue":
        return (
            "    IntrigueCardEntry(\n"
            f"        card={helper_prefix}intrigue_card{identity},\n"
            f"        copies={copies},\n"
            "    ),"
        )
    cost = archetype.attributes.get("PersuasionCost", 0)
    promo = "        promo=True,\n" if is_promo(archetype) else ""
    return (
        "    ImperiumCardEntry(\n"
        f"        card={helper_prefix}imperium_card{identity},\n"
        f"        copies={copies},\n"
        f"        acquisition_cost={cost},\n"
        f"{promo}"
        "    ),"
    )


def full(archetype: Archetype) -> str:
    attributes = archetype.attributes
    factions = ", ".join(
        f"Faction.{FACTIONS[f]}" for f in attributes.get("FactionList", ())
    )
    icons = ", ".join(
        f"AgentIcon.{AGENT_ICONS[i]}" for i in attributes.get("IconList", ())
    )
    lines = [
        f"# {title(archetype)} ({archetype.short})",
        f"copies={attributes['CardCount']},",
        f"acquisition_cost={attributes.get('PersuasionCost', 0)},",
        f"factions=({factions}{',' if factions and ',' not in factions else ''}),",
        f"agent_icons=({icons}{',' if icons and ',' not in icons else ''}),",
        f"reveal_persuasion={attributes.get('Persuasion', 0)},",
        f"reveal_strength={attributes.get('Strength', 0)},",
    ]
    other = sorted(
        key
        for key in attributes
        if key.startswith(("Agent", "Acquire", "Reveal"))
        and key not in ("AcquireValue",)
    )
    if other:
        # Attribute values the record helpers carry (an Agent box's gain, an
        # acquire bonus): checked against the records, not set as fields.
        lines.append(
            "# also: " + ", ".join(f"{key}={attributes[key]!r}" for key in other)
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--set", choices=SETS, default="base", dest="card_set")
    # The same option after the command; absent, it keeps the value before it.
    after = argparse.ArgumentParser(add_help=False)
    after.add_argument(
        "--set", choices=SETS, default=argparse.SUPPRESS, dest="card_set"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("skeleton", parents=[after])
    full_parser = sub.add_parser("full", parents=[after])
    full_parser.add_argument("names", nargs="+")
    args = parser.parse_args()
    if args.command == "skeleton":
        prefix = "" if args.card_set == "base" else "ix_"
        for kind in ("imperium", "intrigue"):
            print(f"# --- {kind} ---")
            for archetype in set_archetypes(args.card_set, kind):
                print(skeleton(archetype, prefix))
        return
    wanted = set(args.names)
    for kind in ("imperium", "intrigue"):
        for archetype in set_archetypes(args.card_set, kind):
            if title(archetype) in wanted:
                print(full(archetype))


if __name__ == "__main__":
    main()
