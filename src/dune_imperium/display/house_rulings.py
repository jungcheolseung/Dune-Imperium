"""The project's rulings as a notice for the people who play (2026-10-24).

The user asked for it while ruling OQ-113: "이렇게 기준이 통일이 안 돼서 내가
어디를 따라야할지 정해야하는 것들은 모두 따로 정리해서 플레이하는 사람들에게
공지할 수 있게 해야겠어", every user ruling, in three groups shown apart:

- ``SOURCES_DIFFER`` (가): two sources say different things -- the official
  rulebook, FAQ or card text, another edition of the rulebook, the
  designer's answers (the community digest, OQ-057), the official digital
  app -- and the ruling follows one of them;
- ``APP_DIFFERS`` (나): the official documents and the designer are silent
  and the app plays it differently from the ruling;
- ``PROJECT`` (다): every other ruling of a gap the official documents
  leave, where no recorded source disagrees.

Each entry restates one ruling of ``docs/rules/open-questions.md``, which
stays the record (the quotes, the citations, the app's evidence); this
module only words it for a player, in both languages. The words live in
``house_rulings.toml`` beside this file (long Korean sentences, which a
Python literal would have to cut into pieces). The help panel reads them
through the catalog (``server.catalog``, ``static/help.js``), and
``scripts/house_rulings_doc.py`` writes ``docs/rules/house-rulings-ko.md``
from them, so the page and the document cannot drift. The player-facing
text names no question number, path or code (user decision 2026-10-14,
"플레이하는 사람 입장에서는 OQ가 뭔지 상관 없으니까"); only the document links
each entry to its question. Korean game words follow
``docs/rules/glossary-ko.md`` and card names their Korean print where one is
known (``display.names_ko``).
"""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from typing import Any


class RulingGroup(StrEnum):
    """The three groups of the notice, in the order it shows them."""

    SOURCES_DIFFER = "sources_differ"
    APP_DIFFERS = "app_differs"
    PROJECT = "project"


class RulingGame(StrEnum):
    """Which game a ruling is for."""

    UPRISING = "uprising"
    # The original Dune: Imperium and Rise of Ix: ruled during P0
    # (docs/base-game-and-ix-plan.md), not playable yet.
    BASE_IX = "base_ix"


@dataclass(frozen=True, slots=True)
class HouseRuling:
    """One ruling, worded for a player in both languages.

    ``oq`` is the question it restates ("OQ-113", or "OQ-057 (15)" for one
    item of a question that holds several). ``sources`` names, for the
    first two groups, which source the ruling follows and which it departs
    from. ``engine_pending`` marks a ruling the engine does not play yet
    (decided, its implementation still ahead).
    """

    oq: str
    group: RulingGroup
    game: RulingGame
    title_ko: str
    title: str
    ruling_ko: str
    ruling: str
    sources_ko: str = ""
    sources: str = ""
    engine_pending: bool = False

    @property
    def question(self) -> str:
        """The question's own number, without an item's mark."""

        return self.oq.split(" ", 1)[0]


def _load() -> tuple[dict[str, Any], tuple[HouseRuling, ...]]:
    data = tomllib.loads(
        files(__package__).joinpath("house_rulings.toml").read_text("utf-8")
    )
    rulings = tuple(
        HouseRuling(
            oq=row["oq"],
            group=RulingGroup(row["group"]),
            game=RulingGame(row["game"]),
            title_ko=row["title_ko"].strip(),
            title=row["title"].strip(),
            ruling_ko=row["ruling_ko"].strip(),
            ruling=row["ruling"].strip(),
            sources_ko=row.get("sources_ko", "").strip(),
            sources=row.get("sources", "").strip(),
            engine_pending=row.get("engine_pending", False),
        )
        for row in data.get("ruling", [])
    )
    return data["notice"], rulings


_NOTICE, HOUSE_RULINGS = _load()
"""The document's own prose, and every ruling in the order it was listed."""


def ordered_house_rulings() -> tuple[HouseRuling, ...]:
    """Group by group, Uprising before the base game and Ix, then as listed."""

    groups = list(RulingGroup)
    games = list(RulingGame)
    return tuple(
        sorted(
            HOUSE_RULINGS,
            key=lambda entry: (groups.index(entry.group), games.index(entry.game)),
        )
    )


def house_rulings_markdown(anchors: Mapping[str, str]) -> str:
    """The Korean notice document; ``anchors`` maps "OQ-113" to its heading's
    anchor in open-questions.md (its index table's link)."""

    notice = _NOTICE
    lines = [f"# {notice['title_ko']}", "", notice["intro_ko"].strip()]
    entries = ordered_house_rulings()
    for group in RulingGroup:
        in_group = [entry for entry in entries if entry.group is group]
        heading = notice["groups"][group.value]
        lines += [
            "",
            f"## {heading['title_ko']} — {len(in_group)}건",
            "",
            heading["intro_ko"].strip(),
        ]
        for game in RulingGame:
            in_game = [entry for entry in in_group if entry.game is game]
            if not in_game:
                continue
            lines += ["", f"### {notice['games'][game.value]}", ""]
            for entry in in_game:
                link = f"[{entry.oq}](open-questions.md#{anchors[entry.question]})"
                pending = f" *({notice['engine_pending_ko']})*"
                lines.append(
                    f"- **{entry.title_ko}** ({link})"
                    f"{pending if entry.engine_pending else ''} — {entry.ruling_ko}"
                )
                if entry.sources_ko:
                    lines.append(f"  - {notice['sources_ko']}: {entry.sources_ko}")
    return "\n".join(lines) + "\n"
