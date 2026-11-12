"""Who sits at a self-play table: the opponent mix and the past selves.

docs/entity-self-play-plan.md section 3.4, with the user's shares of
2026-10-30 ("자기 판 비중 높임"): the current network at all four seats in
half the games, two current seats against two past copies in three tenths,
against two of the server's network (X) in a tenth, and against two app AI
(Hard) seats in a tenth. The learning seats are the current network's.

``TableMix`` deals the kinds in a fixed smooth cycle, so any run of games as
long as the cycle holds the shares exactly and a resumed collection deals
the same tables. ``PastSelves`` keeps the copies the "past" tables draw from.

``dealt_share`` (the user, 2026-10-30, after the pilot: 20%): in that share
of games, drawn by the game's seed apart from the table kind, the draft is
skipped and four different Leaders are dealt at random, so every Leader --
those the greedy policy never drafts too (Liet Kynes, Gaius Helen Mohiam in
the pilot) -- gets games for the value to learn from.
"""

import random
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

TABLE_KINDS: Final = ("self", "past", "x", "app")
# The user's shares (tenths), 2026-10-30.
DEFAULT_SHARES: Final[Mapping[str, int]] = {"self": 5, "past": 3, "x": 1, "app": 1}
_SEATS: Final = 4


def parse_shares(text: str) -> dict[str, int]:
    """``self=5,past=3,x=1,app=1`` as a mapping (kinds left out get 0)."""

    shares = dict.fromkeys(TABLE_KINDS, 0)
    for part in text.split(","):
        kind, _, count = part.partition("=")
        if kind not in shares or not count.isdigit():
            raise ValueError(f"a share is <kind>=<count> with kind in {TABLE_KINDS}")
        shares[kind] = int(count)
    return shares


@dataclass(frozen=True, slots=True)
class Table:
    """One game's seating: each seat's agent kind and the learning seats."""

    kind: str
    agents: tuple[str, ...]
    learners: tuple[int, ...]
    # Each seat's Leader when they are dealt instead of drafted.
    leaders: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class TableMix:
    """The opponent mix: who sits where in game ``index``."""

    cycle: tuple[str, ...]
    dealt_share: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.dealt_share <= 1.0:
            raise ValueError("the dealt share is between 0 and 1")

    @classmethod
    def from_shares(
        cls, shares: Mapping[str, int], *, dealt_share: float = 0.0
    ) -> TableMix:
        """The smooth weighted round robin of ``shares``: each kind's games
        spread evenly over a cycle of ``sum(shares)`` games."""

        unknown = set(shares) - set(TABLE_KINDS)
        if unknown or any(count < 0 for count in shares.values()):
            raise ValueError(f"shares are non-negative counts of {TABLE_KINDS}")
        total = sum(shares.values())
        if not total:
            raise ValueError("the shares are all zero")
        current = dict.fromkeys(TABLE_KINDS, 0)
        cycle = []
        for _ in range(total):
            for kind in TABLE_KINDS:
                current[kind] += shares.get(kind, 0)
            # Ties go to the earlier kind in TABLE_KINDS.
            chosen = max(TABLE_KINDS, key=lambda kind: current[kind])
            current[chosen] -= total
            cycle.append(chosen)
        return cls(tuple(cycle), dealt_share)

    def kind(self, index: int) -> str:
        return self.cycle[index % len(self.cycle)]

    def dealt(self, seed: int, pool: Sequence[str]) -> tuple[str, ...] | None:
        """Four different Leaders from ``pool`` when game ``seed`` deals them,
        else None (the game drafts). Drawn apart from the seating, so the
        share holds in every table kind and the seating does not move."""

        rng = random.Random(f"{seed}:dealt-leaders")
        if not self.dealt_share or rng.random() >= self.dealt_share:
            return None
        return tuple(rng.sample(list(pool), _SEATS))

    def table(
        self,
        index: int,
        seed: int,
        *,
        learner: str,
        x: str,
        app: str,
        past: Sequence[str] = (),
        leader_pool: Sequence[str] = (),
    ) -> Table:
        """Game ``index``'s seating, seeded by the game's ``seed``.

        A "past" table without any past copy (stage 1, before the policy has
        moved) seats the current network four times and is a "self" table.
        Two learning seats are drawn by ``seed``; a past table's two copies
        are drawn from ``past``. With a ``dealt_share`` the Leaders of the
        games it picks are dealt from ``leader_pool``.
        """

        leaders = self.dealt(seed, leader_pool) if leader_pool else None
        kind = self.kind(index)
        if kind == "past" and not past:
            kind = "self"
        if kind == "self":
            return Table("self", (learner,) * _SEATS, tuple(range(_SEATS)), leaders)
        rng = random.Random(seed)
        learners = tuple(sorted(rng.sample(range(_SEATS), 2)))
        if kind == "past":
            others = [rng.choice(list(past)) for _ in range(2)]
        else:
            others = [x if kind == "x" else app] * 2
        agents = []
        for seat in range(_SEATS):
            agents.append(learner if seat in learners else others.pop(0))
        return Table(kind, tuple(agents), learners, leaders)


_COPY = re.compile(r"past-(\d{6})\.pt")


@dataclass(frozen=True, slots=True)
class PastSelves:
    """Copies of the learning network kept for the "past" tables.

    ``keep`` saves a copy every ``every`` iterations into ``directory``
    (``past-<iteration>.pt``) and drops all but the newest ``size``; the
    tables draw from ``paths``. The section 3.4 default: every 200
    iterations, the newest 8.
    """

    directory: Path
    every: int = 200
    size: int = 8

    def paths(self) -> list[Path]:
        if not self.directory.exists():
            return []
        found = [
            path for path in self.directory.iterdir() if _COPY.fullmatch(path.name)
        ]
        return sorted(found)[-self.size :]

    def keep(self, iteration: int, checkpoint: Path) -> Path | None:
        """Copy ``checkpoint`` as the copy of ``iteration`` when it is due."""

        if iteration <= 0 or iteration % self.every:
            return None
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"past-{iteration:06d}.pt"
        temporary = target.with_name(target.name + ".tmp")
        shutil.copyfile(checkpoint, temporary)
        temporary.replace(target)
        for old in sorted(
            path for path in self.directory.iterdir() if _COPY.fullmatch(path.name)
        )[: -self.size]:
            old.unlink()
        return target
