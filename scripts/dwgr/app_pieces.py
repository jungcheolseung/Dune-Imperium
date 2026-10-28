"""Draft card ability records from the Steam app's card screen pieces.

docs/base-game-and-ix-plan.md 2.2 (4) and 13.5 D4-2: the UI prefab the app
draws a card face with (``render/prefabs/UI_crd_<kind>_<name>.prefab.json``,
from ``app_assets.py prefabs``) holds the printed layout -- each box's icon
sprites, their numbers, the arrows and the words between them. This reads
those pieces box by box and writes a draft in our ability-record vocabulary
(``content/uprising/effect_dsl.py``) for a person or agent to check. It
reads names and numbers only; the drafts it prints stay in the git-ignored
``tmp/`` like any app extraction (``scripts/dwgr/README.md``).

A piece the vocabulary does not know, or any sentence, is passed through as
``TEXT(...)``: the draft never guesses at printed words.

    uv run python scripts/dwgr/app_pieces.py --app <app dir> [--set BaseSet]
"""

import argparse
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

# Sprite name (after ``UI_crd_``) -> (atom, default amount). The atoms are
# ability-record pieces: a reward unless an arrow makes it a cost.
_ICONS: dict[str, str] = {
    "ActionIcon_Persuasion": "persuasion",
    "ActionIcon_Strength": "sword",
    "ActionIcon_ResourceCube": "troop",
    "ActionIcon_ResourceCoin": "solari",
    "ActionIcon_Spice": "spice",
    "ActionIcon_Water": "water",
    "CostIcon_Water": "water",
    "ActionIcon_DrawCard": "draw",
    "ActionIcon_IntrigueCard": "intrigue",
    "ActionIcon_TrashCard": "trash",
    "ActionIcon_VictoryPoint": "vp",
}
_FACTIONS = {
    "Emperor": "EMPEROR",
    "SpacingGuild": "SPACING_GUILD",
    "BeneGesserit": "BENE_GESSERIT",
    "Fremen": "FREMEN",
    "Wild": "ANY",
}
_FACTION_ICON = re.compile(r"ActionIcon_Faction(\w+?)(Up2|Up|Down)?(?:_Lg)?$")
# Frames and decorations: no part of an effect.
_FRAMES = re.compile(
    r"^(BaseShape|HeaderFrame|RevealFrame|ActionFrame|ActionColumnBacker|"
    r"CostIcon_Persuasion|CardFront|SubHeader_|AcquireFrame|TrashFrame|"
    r"Intrigue\w*OrFrame|CostIcon_AcquireArrow|ill_)"
)
_NUMBER = re.compile(r"^\d+$")


@dataclass(frozen=True, slots=True)
class Piece:
    """One printed piece of a box: an icon with its number, an arrow, or words."""

    kind: str  # an atom from _ICONS, "influence", "alliance", "arrow", "text"
    amount: int = 1
    faction: str = ""
    text: str = ""
    y: float = 0.0
    x: float = 0.0


def _comp(node: dict, name: str) -> dict | None:
    return next((c for c in node.get("comps", ()) if c.get("_") == name), None)


def _sprite(node: dict) -> str:
    image = _comp(node, "Image")
    sprite = (image or {}).get("m_Sprite") or ""
    return sprite.removeprefix("Sprite:").removeprefix("UI_crd_")


def _text(node: dict) -> str:
    tmp = _comp(node, "TextMeshProUGUI")
    raw = (tmp or {}).get("m_text") or ""
    # An inline icon keeps its name: "costs {Persuasion3} or less".
    raw = re.sub(r'<sprite name="?([^">]+)"?>', r"{\1}", raw)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def _pos(node: dict) -> tuple[float, float]:
    rt = _comp(node, "RT") or {}
    x, y = rt.get("pos", (0.0, 0.0))
    return float(x), float(y)


def _icon_amount(node: dict) -> int | None:
    """The number printed on an icon (its own text or a child's)."""

    for child in node.get("children", ()):
        if child.get("active", True) and _NUMBER.match(_text(child)):
            return int(_text(child))
    return None


def _pieces(node: dict, ox: float, oy: float, out: list[Piece]) -> None:
    if not node.get("active", True):
        return
    x, y = _pos(node)
    x, y = ox + x, oy + y
    sprite, text = _sprite(node), _text(node)
    if sprite in _ICONS:
        amount = _icon_amount(node)
        out.append(Piece(_ICONS[sprite], amount or 1, y=y, x=x))
    elif match := _FACTION_ICON.match(sprite):
        faction = _FACTIONS.get(match.group(1), match.group(1))
        step = match.group(2)
        if step is None:
            # A bare Faction icon marks a condition (an Alliance), no gain.
            out.append(Piece("alliance", faction=faction, y=y, x=x))
        else:
            amount = {"Up": 1, "Up2": 2, "Down": -1}[step]
            out.append(Piece("influence", amount, faction=faction, y=y, x=x))
    elif sprite == "CostIcon_IfThenArrow":
        out.append(Piece("arrow", y=y, x=x))
    elif sprite and sprite != "None" and not _FRAMES.match(sprite):
        out.append(Piece("text", text=f"sprite {sprite}", y=y, x=x))
    if text and not _NUMBER.match(text) and not sprite:
        out.append(Piece("text", text=text, y=y, x=x))
    for child in node.get("children", ()):
        if sprite in _ICONS and _NUMBER.match(_text(child)):
            continue
        _pieces(child, x, y, out)


# Region anchors of a card face, in reading order.
_REGIONS = {
    "Agent_Anchor": "AGENT",
    "Reveal_Anchor": "REVEAL",
    "GameTextArea_Anchor": "PLAY",
    "Trash_Anchor": "TRASHED",
    "Tiebreaker_Anchor": "TIEBREAK",
}


def card_pieces(prefab: dict) -> dict[str, list[Piece]]:
    """Each box's pieces, read top to bottom and left to right."""

    boxes: dict[str, list[Piece]] = {}
    for child in prefab.get("children", ()):
        name = child["name"]
        if name == "Persuasion_Anchor":
            # The cost sits here, and an acquire bonus beside it.
            acquire: list[Piece] = []
            for frame in _active_named(child, "AcquireFrame"):
                _pieces(frame, 0.0, 0.0, acquire)
            if acquire:
                boxes["ACQUIRE"] = acquire
            continue
        region = _REGIONS.get(name)
        if region is None or not child.get("active", True):
            continue
        found: list[Piece] = []
        for part in child.get("children", ()):
            _pieces(part, 0.0, 0.0, found)
        if found:
            boxes[region] = _reading_order(found)
    return boxes


def _active_named(node: dict, name: str) -> list[dict]:
    """The active nodes called ``name`` under an active ``node``."""

    if not node.get("active", True):
        return []
    if node["name"] == name:
        return [node]
    return [
        found
        for child in node.get("children", ())
        for found in _active_named(child, name)
    ]


_ROW = 15.0
_JOINERS = ("-AND-", "-OR-", "–AND–", "–OR–")


def _reading_order(pieces: list[Piece]) -> list[Piece]:
    """Rows top to bottom (a row is pieces within ``_ROW`` of its first),
    each left to right. A joiner ("-AND-") set between rows splits the box
    into columns instead: what stands left of it is read first (Gurney
    Halleck's Persuasion, then "3 Solari -> 2 troops")."""

    joiner = next((p for p in pieces if p.text in _JOINERS), None)
    if joiner is not None:
        left = [p for p in pieces if p.x < joiner.x and abs(p.y - joiner.y) <= _ROW]
        if left and any(abs(p.y - joiner.y) > _ROW for p in pieces):
            rest = [p for p in pieces if p is not joiner and p not in left]
            return [*_rows(left), joiner, *_rows(rest)]
    return _rows(pieces)


def _rows(pieces: list[Piece]) -> list[Piece]:
    rows: list[list[Piece]] = []
    for piece in sorted(pieces, key=lambda p: -p.y):
        if rows and abs(rows[-1][0].y - piece.y) <= _ROW:
            rows[-1].append(piece)
        else:
            rows.append([piece])
    return [piece for row in rows for piece in sorted(row, key=lambda p: p.x)]


_REWARD = {
    "troop": "RecruitTroops({n})",
    "solari": "GainResources(solari={n})",
    "spice": "GainResources(spice={n})",
    "water": "GainResources(water={n})",
    "draw": "DrawPersonalCards({n})",
    "intrigue": "DrawIntrigueCards({n})",
    "trash": "TrashPersonalCard()",
    "vp": "GainVictoryPoints({n})",
    "sword": "GainCombatStrength({n})",
    "persuasion": "Persuasion({n})",
}
_COST = {
    "solari": "PayResources(solari={n})",
    "spice": "PayResources(spice={n})",
    "water": "PayResources(water={n})",
    "trash": "TrashCard()",
}


def _merge(pieces: list[Piece]) -> list[Piece]:
    """Fold repeated icons (three troop cubes) into one amount."""

    merged: list[Piece] = []
    for piece in pieces:
        last = merged[-1] if merged else None
        if (
            last is not None
            and piece.kind == last.kind
            and piece.kind in ("troop", "sword", "draw", "intrigue")
            and piece.amount == 1
        ):
            merged[-1] = Piece(last.kind, last.amount + 1, y=last.y, x=last.x)
        else:
            merged.append(piece)
    return merged


def _atom(piece: Piece, cost: bool) -> str:
    n = piece.amount
    if piece.kind == "influence":
        if n < 0:
            return f"LoseInfluence({piece.faction}, {-n})"
        return f"GainInfluence({piece.faction}, {n})"
    if piece.kind == "alliance":
        return f"[HasAlliance({piece.faction})]"
    if piece.kind == "text":
        return _condition(piece.text) or f'TEXT("{piece.text}")'
    table = _COST if cost and piece.kind in _COST else _REWARD
    return table[piece.kind].format(n=n)


def _condition(text: str) -> str | None:
    if text.startswith("[") and text.endswith("]"):
        return text
    if match := re.fullmatch(r"(\w[\w ]*?) Bond ?:", text):
        return f"[FactionBond({match.group(1).upper().replace(' ', '_')})]"
    if text in ("-OR-", "–OR–", "Choose one:"):
        return "ONE_OF"
    if text in ("-AND-", "–AND–"):
        return "AND"
    return None


def _fold_conditions(pieces: list[Piece]) -> list[Piece]:
    """A bare Faction icon with its words is one condition: "2 Influence :"
    (Smuggler's Thopter) or "Alliance :" (Firm Grip)."""

    out: list[Piece] = []
    used: set[int] = set()
    for index, piece in enumerate(pieces):
        if index in used:
            continue
        if piece.kind == "alliance":
            for near in (index + 1, index - 1):
                if near < 0 or near >= len(pieces) or near in used:
                    continue
                words = pieces[near].text
                if match := re.fullmatch(r"(\d+) Influence ?:", words):
                    condition = f"InfluenceAtLeast({piece.faction}, {match.group(1)})"
                elif re.fullmatch(r"Alliance ?: ?\+?", words):
                    condition = f"HasAlliance({piece.faction})"
                else:
                    continue
                used.add(near)
                if out and out[-1] is pieces[near]:
                    out.pop()
                out.append(Piece("text", text=f"[{condition}]"))
                break
            else:
                out.append(piece)
            continue
        out.append(piece)
    return out


def draft(pieces: list[Piece]) -> str:
    """One box as a line of record pieces: costs ``->`` rewards."""

    pieces = _fold_conditions(_merge(pieces))
    arrow = next((i for i, p in enumerate(pieces) if p.kind == "arrow"), None)
    parts: list[str] = []
    for index, piece in enumerate(pieces):
        if piece.kind == "arrow":
            parts.append("->")
            continue
        cost = (
            arrow is not None and index < arrow and _is_cost_run(pieces, index, arrow)
        )
        parts.append(_atom(piece, cost))
    return " ".join(parts)


def _is_cost_run(pieces: list[Piece], index: int, arrow: int) -> bool:
    """Whether ``pieces[index]`` sits in the run right before the arrow
    (an "-AND-" or a sentence ends the run: Gurney Halleck's Persuasion
    before "-AND-" is no cost)."""

    for piece in pieces[index + 1 : arrow]:
        if piece.kind == "text" and _condition(piece.text) in ("AND", "ONE_OF", None):
            return False
    return True


# The one Rise of Ix promo among the app's promo archetypes [plan 9 8].
_IX_PROMOS = frozenset({"Boundless Ambition"})


def _loc_text(raw: str) -> str:
    raw = re.sub(r'<sprite name="?([^">]+)"?>', r"{\1}", raw)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def fill_from_loc(
    boxes: dict[str, list[Piece]], strings: list[str]
) -> dict[str, list[Piece]]:
    """Put back the icons the app writes into a box's words at run time
    (Gene Manipulation's "in play: {Spice_2}."): the prefab keeps the
    words with a gap where the card's English string has a sprite tag."""

    by_words = {
        _norm(re.sub(r"\{[^}]*\}", "", text)): text
        for text in map(_loc_text, strings)
        if "{" in text
    }
    return {
        region: [
            replace(piece, text=by_words.get(_norm(piece.text), piece.text))
            if piece.kind == "text"
            else piece
            for piece in pieces
        ]
        for region, pieces in boxes.items()
    }


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", "", name).lower())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--set", default="BaseSet")
    parser.add_argument("--kinds", default="imperium,intrigue")
    args = parser.parse_args()
    cards = json.loads(
        (args.app / "analysis/base-ix-2026-10-22/cards.json").read_text()
    )
    prefabs = {
        _norm(path.name[len("UI_crd_") : -len(".prefab.json")]): path
        for path in (args.app / "render/prefabs").glob("UI_crd_*.prefab.json")
    }
    loc = json.loads((args.app / "render/loc_en_US.json").read_text())
    kinds = args.kinds.split(",")
    for card in cards:
        if card["kind"] not in kinds:
            continue
        promo = card["short"].startswith(f"{card['kind'].capitalize()}Archetypes.Promo")
        if args.set not in card["sets"] and not (promo and args.set == "BaseSet"):
            continue
        if promo and card["title"] in _IX_PROMOS:
            continue
        title = re.sub(r"<[^>]+>", " ", card["title"]).replace("  ", " ")
        path = prefabs.get(_norm(card["kind"] + card["title"]))
        if path is None:
            print(f"{title}: no card prefab (drawn from the generic one)")
            continue
        prefab = json.loads(path.read_text())
        prefix = f"card.{card['kind']}.{_norm(card['title'])}."
        boxes = fill_from_loc(
            card_pieces(prefab),
            [text for key, text in loc.items() if key.startswith(prefix)],
        )
        line = " | ".join(f"{region}: {draft(p)}" for region, p in boxes.items())
        kinds_printed = [
            _text(node).upper()
            for node in _active_named(prefab, "CardTypeText_Anchor")
            for node in node.get("children", ())
            if node.get("active", True) and _text(node)
        ]
        if kinds_printed:
            line = f"[{'/'.join(kinds_printed)}] {line}"
        print(f"{title}: {line or '(no pieces)'}")


if __name__ == "__main__":
    main()
