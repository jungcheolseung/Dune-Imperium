"""Aggregate tournament results per agent, seat, Leader, and first player.

``summarize`` folds a ``TournamentReport`` into one ``TournamentSummary``;
``summary_to_json`` and ``render_markdown`` serialize it for files and for
reading. The win criterion is rank 1 of the official final standings, so
every finished match has exactly one winner. The VP margin of a seat is its
Victory Points minus the mean of the other seats' Victory Points in that
match, so a positive margin means the agent out-scored its own table.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from dune_imperium.evaluation.tournament import MatchResult, TournamentReport


@dataclass(frozen=True, slots=True)
class SeatSummary:
    """One agent's record from one seat index."""

    seat: int
    games: int
    wins: int
    mean_rank: float


@dataclass(frozen=True, slots=True)
class LeaderSummary:
    """One agent's record with one Leader."""

    leader_id: str
    games: int
    wins: int
    mean_rank: float


@dataclass(frozen=True, slots=True)
class AgentSummary:
    """One agent kind's record over the whole tournament."""

    agent: str
    games: int
    wins: int
    mean_rank: float
    mean_victory_points: float
    mean_vp_margin: float
    first_player_games: int
    first_player_wins: int
    decisions: int
    illegal_actions: int
    mean_decision_ms: float
    seats: tuple[SeatSummary, ...]
    leaders: tuple[LeaderSummary, ...]

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0


@dataclass(frozen=True, slots=True)
class TournamentSummary:
    """Tournament-level totals plus one summary per agent kind."""

    matches: int
    failures: int
    rulesets: tuple[str, ...]
    duration_seconds: float
    total_steps: int
    mean_rounds: float
    agents: tuple[AgentSummary, ...]
    failure_messages: tuple[str, ...]


@dataclass(slots=True)
class _Accumulator:
    games: int = 0
    wins: int = 0
    rank_total: int = 0
    vp_total: int = 0
    margin_total: float = 0.0
    first_player_games: int = 0
    first_player_wins: int = 0
    decisions: int = 0
    illegal_actions: int = 0
    decision_seconds: float = 0.0

    def add(
        self,
        rank: int,
        victory_points: int,
        margin: float,
        *,
        first_player: bool,
        decisions: int = 0,
        illegal_actions: int = 0,
        decision_seconds: float = 0.0,
    ) -> None:
        self.games += 1
        self.wins += int(rank == 1)
        self.rank_total += rank
        self.vp_total += victory_points
        self.margin_total += margin
        if first_player:
            self.first_player_games += 1
            self.first_player_wins += int(rank == 1)
        self.decisions += decisions
        self.illegal_actions += illegal_actions
        self.decision_seconds += decision_seconds

    @property
    def mean_rank(self) -> float:
        return self.rank_total / self.games if self.games else 0.0


def _vp_margin(match: MatchResult, seat: int) -> float:
    others = [s.victory_points for s in match.seats if s.seat != seat]
    own = match.seats[seat].victory_points
    return own - (sum(others) / len(others) if others else 0.0)


def summarize(report: TournamentReport) -> TournamentSummary:
    """Fold every finished match into per-agent, per-seat, per-Leader totals."""

    totals: dict[str, _Accumulator] = defaultdict(_Accumulator)
    by_seat: dict[tuple[str, int], _Accumulator] = defaultdict(_Accumulator)
    by_leader: dict[tuple[str, str], _Accumulator] = defaultdict(_Accumulator)
    rulesets: list[str] = []
    for match in report.matches:
        if match.ruleset not in rulesets:
            rulesets.append(match.ruleset)
        for seat in match.seats:
            margin = _vp_margin(match, seat.seat)
            is_first = seat.seat == match.first_player
            totals[seat.agent].add(
                seat.rank,
                seat.victory_points,
                margin,
                first_player=is_first,
                decisions=seat.decisions,
                illegal_actions=seat.illegal_actions,
                decision_seconds=seat.decision_seconds,
            )
            by_seat[(seat.agent, seat.seat)].add(
                seat.rank, seat.victory_points, margin, first_player=is_first
            )
            by_leader[(seat.agent, seat.leader_id)].add(
                seat.rank, seat.victory_points, margin, first_player=is_first
            )

    agents = tuple(
        AgentSummary(
            agent=agent,
            games=acc.games,
            wins=acc.wins,
            mean_rank=acc.mean_rank,
            mean_victory_points=acc.vp_total / acc.games,
            mean_vp_margin=acc.margin_total / acc.games,
            first_player_games=acc.first_player_games,
            first_player_wins=acc.first_player_wins,
            decisions=acc.decisions,
            illegal_actions=acc.illegal_actions,
            mean_decision_ms=(
                acc.decision_seconds * 1000.0 / acc.decisions if acc.decisions else 0.0
            ),
            seats=tuple(
                SeatSummary(
                    seat=seat,
                    games=seat_acc.games,
                    wins=seat_acc.wins,
                    mean_rank=seat_acc.mean_rank,
                )
                for (seat_agent, seat), seat_acc in sorted(by_seat.items())
                if seat_agent == agent
            ),
            leaders=tuple(
                LeaderSummary(
                    leader_id=leader_id,
                    games=leader_acc.games,
                    wins=leader_acc.wins,
                    mean_rank=leader_acc.mean_rank,
                )
                for (leader_agent, leader_id), leader_acc in sorted(by_leader.items())
                if leader_agent == agent
            ),
        )
        for agent, acc in sorted(totals.items())
    )
    matches = len(report.matches)
    return TournamentSummary(
        matches=matches,
        failures=len(report.failures),
        rulesets=tuple(rulesets),
        duration_seconds=report.duration_seconds,
        total_steps=sum(match.steps for match in report.matches),
        mean_rounds=(
            sum(match.rounds for match in report.matches) / matches if matches else 0.0
        ),
        agents=agents,
        failure_messages=tuple(
            f"{failure.ruleset} seed={failure.game_seed} "
            f"policy={failure.policy_seed} seats={','.join(failure.seat_agents)}: "
            f"{failure.error}"
            for failure in report.failures
        ),
    )


def summary_to_json(summary: TournamentSummary) -> dict[str, Any]:
    """Return a JSON-serializable view of the summary (plus derived rates)."""

    document = asdict(summary)
    for agent, entry in zip(summary.agents, document["agents"], strict=True):
        entry["win_rate"] = agent.win_rate
    return document


def _pct(wins: int, games: int) -> str:
    return f"{100.0 * wins / games:.1f}%" if games else "-"


def render_markdown(summary: TournamentSummary) -> str:
    """Render the summary as a Markdown report."""

    games_per_second = (
        summary.matches / summary.duration_seconds if summary.duration_seconds else 0.0
    )
    lines = [
        "# Tournament report",
        "",
        f"- rulesets: {', '.join(summary.rulesets) or '-'}",
        f"- matches: {summary.matches} finished, {summary.failures} failed",
        (
            f"- duration: {summary.duration_seconds:.1f}s "
            f"({games_per_second:.2f} games/s); mean rounds {summary.mean_rounds:.1f}; "
            f"total steps {summary.total_steps}"
        ),
        "",
        "## Agents",
        "",
        "| agent | games | win rate | mean rank | mean VP | VP margin | "
        "first player | decisions | illegal | ms/decision |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for agent in summary.agents:
        lines.append(
            f"| {agent.agent} | {agent.games} | {_pct(agent.wins, agent.games)} | "
            f"{agent.mean_rank:.2f} | {agent.mean_victory_points:.2f} | "
            f"{agent.mean_vp_margin:+.2f} | "
            f"{_pct(agent.first_player_wins, agent.first_player_games)} "
            f"({agent.first_player_games}) | {agent.decisions} | "
            f"{agent.illegal_actions} | {agent.mean_decision_ms:.3f} |"
        )
    lines += ["", "## Seats (win rate / mean rank)", ""]
    seat_indexes = sorted(
        {seat.seat for agent in summary.agents for seat in agent.seats}
    )
    lines.append("| agent | " + " | ".join(f"seat {i}" for i in seat_indexes) + " |")
    lines.append("|---|" + "---:|" * len(seat_indexes))
    for agent in summary.agents:
        cells = []
        by_index = {seat.seat: seat for seat in agent.seats}
        for index in seat_indexes:
            seat = by_index.get(index)
            cells.append(
                f"{_pct(seat.wins, seat.games)} / {seat.mean_rank:.2f} ({seat.games})"
                if seat is not None
                else "-"
            )
        lines.append(f"| {agent.agent} | " + " | ".join(cells) + " |")
    leader_ids = sorted(
        {leader.leader_id for agent in summary.agents for leader in agent.leaders}
    )
    if len(leader_ids) > 1:
        lines += ["", "## Leaders (win rate / mean rank)", ""]
        lines.append(
            "| leader | " + " | ".join(agent.agent for agent in summary.agents) + " |"
        )
        lines.append("|---|" + "---:|" * len(summary.agents))
        for leader_id in leader_ids:
            cells = []
            for agent in summary.agents:
                leader = next(
                    (entry for entry in agent.leaders if entry.leader_id == leader_id),
                    None,
                )
                cells.append(
                    f"{_pct(leader.wins, leader.games)} / {leader.mean_rank:.2f} "
                    f"({leader.games})"
                    if leader is not None
                    else "-"
                )
            lines.append(f"| {leader_id} | " + " | ".join(cells) + " |")
    if summary.failure_messages:
        lines += ["", "## Failures", ""]
        lines += [f"- {message}" for message in summary.failure_messages]
    return "\n".join(lines) + "\n"
