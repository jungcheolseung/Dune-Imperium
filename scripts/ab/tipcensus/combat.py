"""Combat collector: the reward-auction, kicker, sandworm, and Shield Wall tips.

Tests: C2.1 "Combat is a reward auction: win narrowly", C2.2 "one unit for a
kicker 2nd/3rd reward", C2.3 + the owner's tip 1 (sandworms double rewards),
C2.4 Shield Wall, C2.6 garrison reserve for tier III, C2.8 Combat Intrigue.

Engine facts this module relies on (see ``rules/combat.py``):

- ``engine.apply()`` folds every automatic phase transition into one
  ``RuleResult`` (``rules/engine.py::_advance_automatic``), so
  ``combat_intrigue_started``/``combat_intrigue_finished``/
  ``combat_reward_gained``/``conflict_won``/``combat_cleaned_up`` can all land
  in a single ``Step`` -- or be split across several when a reward or
  Conflict-end trigger opens a further player decision.
- ``resolve_combat_rewards`` always appends one ``combat_reward_gained`` event
  per reward recipient *before* it pushes any decision frames the reward
  needs (Influence choice, trash, Spy placement, ...), so those events are
  always in the same step as the ``combat_intrigue_finished`` that precedes
  them, even when ``conflict_won``/``combat_cleaned_up`` are delayed to a
  later step waiting on those decisions.
- ``finish_combat`` zeroes ``combat_strength``/``troops_conflict`` and pops
  ``current_conflict_ids`` only in its own *post*-state, so the units/strength
  snapshot must come from the *pre*-state of the step whose events contain
  ``combat_intrigue_finished`` (never from a ``conflict_won`` step's
  post-state, which is already cleaned up).
- ``current_conflict_ids`` is a stack: one Conflict is revealed per round
  (``rules/phases.py::begin_round``) and pushed on top; ``finish_combat`` pops
  it only when there was a winner, so a Conflict nobody won (an empty
  ``rank_combat`` top group, or a >1-way tie for 1st) can be left underneath
  a later round's Conflict. ``current_conflict_ids[-1]`` is always the
  Conflict currently resolving.
- A Conflict nobody entered still finishes Combat Intrigue: with no
  participants, ``begin_combat_intrigue`` emits ``combat_intrigue_finished``
  at once (``rules/combat.py`` ~137-146). That call happens inside the same
  ``apply()`` as the round's last ``finish_reveal`` (the one that flips
  ``state.phase`` to ``COMBAT``, ``rules/reveal_turn.py`` ~3914), so the
  *Step*'s ``pre.phase`` is still ``PLAYER_TURNS`` even though the internal
  ``state.phase`` was already ``COMBAT`` when the event fired. This module
  does not gate on ``pre.phase`` for that reason -- ``combat_intrigue_finished``
  is only ever emitted from Combat Intrigue itself, so the kind alone is
  enough.
- A Conflict can also leave Combat Intrigue with **no event at all**:
  ``refresh_combat_participants`` (``rules/combat.py`` ~1741-1746) ends the
  priority loop silently once the last remaining participant loses its last
  unit. By the time ``combat_cleaned_up`` fires, every seat is back to 0
  units/strength, so this module records a zero row for that Conflict there
  instead of at a ``combat_intrigue_finished`` it will never see.
- Sandworms reach ``sandworms_conflict`` through three event kinds, not one:
  ``sandworm_deployed`` (an agent-effect summon; payload key ``count``),
  ``reveal_sandworm_deployed`` (the Desert Power Reveal choice; payload key
  ``amount``, always 1), and ``board_effect_resolved`` with
  ``effect == "maker"`` and a positive ``sandworms`` key (a Maker-space
  summon; that key is 0 for the harvest-spice and Arrakis-Planetologist-
  replace choices at the same space, so gating on it > 0 is exact).
"""

from __future__ import annotations

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.tournament import MatchSpec
from dune_imperium.rules.endgame import FinalStanding

from .base import Collector, Columns, Step, arguments, payload


def _mean(values: list[int]) -> float | None:
    """Arithmetic mean of ``values``, or None for "mean over zero items"."""

    return sum(values) / len(values) if values else None


class CombatCollector(Collector):
    """Per-Conflict combat outcomes and the board visits that feed them."""

    name = "combat"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        # One dict per resolved Conflict, in resolution order; see
        # ``_record_conflict`` for its keys. Kept only in the JSONL rows
        # (it is a ``list`` column, per ``tipcensus.base``).
        self._conflicts: list[Columns] = []
        # combat_strength per seat when Combat Intrigue priority opened for
        # the Conflict currently resolving (None until that event is seen;
        # consumed and reset to None at the matching combat_intrigue_finished).
        self._pre_intrigue: list[int] | None = None
        self._wall_fall_round: int | None = None
        self._wall_dropper: int | None = None
        # True once the Conflict currently resolving has a row in
        # self._conflicts (set at combat_intrigue_finished, consumed and
        # reset at the matching combat_cleaned_up); starts True since no
        # Conflict is pending before the first one begins.
        self._recorded = True
        # Running per-seat totals, kept for the whole game (never reset per
        # round/Conflict).
        self._worms_summoned: list[int] = [0] * seats
        self._garrison_combat_visits: list[list[int]] = [[] for _ in range(seats)]
        self._garrison_tier3_visits: list[list[int]] = [[] for _ in range(seats)]
        self._heighliner_visits: list[int] = [0] * seats

    def step(self, s: Step) -> None:
        for event in s.events:
            kind = event.kind
            if kind == "combat_intrigue_started":
                # The state right after Combat Intrigue priority opens and
                # before any card has been played: the strengths a "flip"
                # is measured against [Main p. 14] (combat-and-round-end.md:16).
                self._pre_intrigue = [
                    player.combat_strength for player in s.post.players
                ]
            elif kind == "shield_wall_destroyed" and self._wall_fall_round is None:
                self._wall_fall_round = s.pre.round_number
                self._wall_dropper = s.owner
            elif kind == "sandworm_deployed":
                # Agent-effect summon (SummonSandworm).
                info = payload(event)
                self._worms_summoned[int(info["player"])] += int(info["count"])
            elif kind == "reveal_sandworm_deployed":
                # Desert Power Reveal choice; one sandworm per event.
                info = payload(event)
                self._worms_summoned[int(info["player"])] += int(info["amount"])
            elif kind == "board_effect_resolved":
                info = payload(event)
                if info.get("effect") == "maker" and int(info.get("sandworms", 0)) > 0:
                    # Maker-space summon (apply_maker_space_action); the
                    # "sandworms" key is 0 for that space's other two
                    # choices, so this only fires on an actual summon.
                    self._worms_summoned[int(info["player"])] += int(info["sandworms"])
            elif kind == "combat_intrigue_finished":
                self._record_conflict(s)
                self._recorded = True
            elif kind == "combat_cleaned_up":
                if not self._recorded:
                    self._record_missing_conflict(s)
                self._recorded = False
        if (
            s.owner is not None
            and s.action is not None
            and s.action.action_id == "agent_turn"
        ):
            self._record_agent_turn(s, s.owner, s.action)

    def _record_conflict(self, s: Step) -> None:
        """Snapshot one Conflict's resolution from the *pre*-state (see module
        docstring): the moment Combat Intrigue priority just closed, before
        rewards or cleanup can zero any of these fields."""

        state = s.pre
        conflict_id = state.current_conflict_ids[-1]
        conflict = CONFLICTS_BY_ID[conflict_id]
        # combat_reward_gained is always emitted in this same step (see
        # module docstring), one per rank-1/2/3 recipient; rank 0 = no
        # reward, multiplier 1 unless the seat's own sandworm doubled it
        # [Main p. 14] (combat-and-round-end.md:38).
        ranks: dict[int, tuple[int, int]] = {}
        for event in s.events:
            if event.kind == "combat_reward_gained":
                info = payload(event)
                ranks[int(info["player"])] = (
                    int(info["rank"]),
                    int(info["multiplier"]),
                )
        winner = next(
            (seat for seat, (rank, _mult) in ranks.items() if rank == 1), None
        )
        strengths = [player.combat_strength for player in state.players]
        pre_intrigue = (
            self._pre_intrigue if self._pre_intrigue is not None else list(strengths)
        )
        self._pre_intrigue = None
        margin: int | None = None
        if winner is not None:
            others = [strengths[i] for i in range(self.seats) if i != winner]
            # Strictly the highest strength among the four [Main p. 14]
            # (combat-and-round-end.md:24): "the reward auction" margin.
            margin = strengths[winner] - max(others)
        self._conflicts.append(
            {
                "round": state.round_number,
                "conflict_id": conflict_id,
                "tier": int(conflict.tier),
                # Sandworms cannot enter a Shield Wall-protected Conflict
                # while the Wall still stands [Main p. 20].
                "protected_and_wall_standing": bool(
                    conflict.shield_wall_protected and state.shield_wall_present
                ),
                "strength": [player.combat_strength for player in state.players],
                "troops": [player.troops_conflict for player in state.players],
                "sandworms": [player.sandworms_conflict for player in state.players],
                "commanders": [player.commanders_conflict for player in state.players],
                # Into the Fray: 0/1, Duncan Idaho's Agent fighting as a unit
                # in the Conflict (PlayerState.units_in_conflict includes it)
                # [Duncan Idaho card].
                "agents": [player.agent_in_conflict for player in state.players],
                "garrison": [player.troops_garrison for player in state.players],
                "rank": [ranks.get(seat, (0, 0))[0] for seat in range(self.seats)],
                "multiplier": [
                    ranks.get(seat, (0, 0))[1] for seat in range(self.seats)
                ],
                "pre_intrigue_strength": pre_intrigue,
                "winner": winner,
                "margin": margin,
            }
        )

    def _record_missing_conflict(self, s: Step) -> None:
        """Zero row for a Conflict that closed Combat Intrigue with no
        ``combat_intrigue_finished`` event: every remaining participant lost
        its last unit and ``refresh_combat_participants`` (``combat.py``
        ~1741-1746) ended the loop silently. By the time ``combat_cleaned_up``
        fires here every seat's units and strength are already 0 (nobody
        stayed a participant, and a seat without a unit has 0 strength even
        with swords [Main p. 12], combat-and-round-end.md:10), so the
        pre-state is legitimately all-zero."""

        state = s.pre
        conflict_id = state.current_conflict_ids[-1]
        conflict = CONFLICTS_BY_ID[conflict_id]
        zeros = [0] * self.seats
        self._conflicts.append(
            {
                "round": state.round_number,
                "conflict_id": conflict_id,
                "tier": int(conflict.tier),
                "protected_and_wall_standing": bool(
                    conflict.shield_wall_protected and state.shield_wall_present
                ),
                "strength": list(zeros),
                "troops": list(zeros),
                "sandworms": list(zeros),
                "commanders": list(zeros),
                "agents": list(zeros),
                "garrison": [player.troops_garrison for player in state.players],
                "rank": list(zeros),
                "multiplier": list(zeros),
                "pre_intrigue_strength": list(zeros),
                "winner": None,
                "margin": None,
            }
        )
        # A stale combat_intrigue_started snapshot (from before this
        # Conflict's participants dropped to none) must not leak into the
        # next Conflict's _record_conflict.
        self._pre_intrigue = None

    def _record_agent_turn(self, s: Step, owner: int, action: DomainAction) -> None:
        """Garrison size and Combat-space choice at the moment an Agent lands."""

        space_id = arguments(action).get("space_id")
        if not isinstance(space_id, str):
            return
        space = BOARD_SPACES_BY_ID.get(space_id)
        if space is None or not space.combat:
            return
        garrison = s.pre.players[owner].troops_garrison
        self._garrison_combat_visits[owner].append(garrison)
        current_conflict_ids = s.pre.current_conflict_ids
        if current_conflict_ids:
            conflict = CONFLICTS_BY_ID.get(current_conflict_ids[-1])
            if conflict is not None and conflict.tier is ConflictTier.THREE:
                self._garrison_tier3_visits[owner].append(garrison)
        if space_id == "heighliner":
            # Spacing Guild Influence 1, troop 5 recruit, cost 5 spice
            # [Board Guide p. 2] (board-spaces.md:32).
            self._heighliner_visits[owner] += 1

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        per_seat: list[Columns] = []
        for seat in range(self.seats):
            # Conflicts with >=1 own unit: troop, sandworm, Sardaukar
            # Commander, or Duncan Idaho's Into-the-Fray Agent -- matches
            # PlayerState.units_in_conflict [Duncan Idaho card].
            entered = 0
            won = 0  # Conflicts where this seat was the sole rank-1 recipient.
            unopposed_wins = 0  # Wins where every other seat was at strength 0.
            win_margins: list[int] = []
            excess_troops: list[int] = []
            one_unit_entries = 0  # Entries with exactly one own unit.
            one_unit_rewarded = 0  # ...of those, paid a rank-2/3 reward.
            worm_entries = 0  # Entries with >=1 own sandworm.
            worm_not_first = 0  # ...of those, did not win.
            doubled_rewards = 0  # Reward receipts paid at multiplier 2.
            intrigue_flip_won = 0  # Won without being the strict pre-Intrigue leader.
            intrigue_flip_lost = 0  # Was the strict pre-Intrigue leader but lost.
            for c in self._conflicts:
                troops = c["troops"][seat]
                worms = c["sandworms"][seat]
                commanders = c["commanders"][seat]
                agents = c["agents"][seat]
                units = troops + worms + commanders + agents
                is_winner = c["winner"] == seat
                rank = c["rank"][seat]
                if c["multiplier"][seat] == 2:
                    doubled_rewards += 1
                if units >= 1:
                    entered += 1
                    if units == 1:
                        one_unit_entries += 1
                        if rank in (2, 3):
                            one_unit_rewarded += 1
                    if worms >= 1:
                        worm_entries += 1
                        if not is_winner:
                            worm_not_first += 1
                if is_winner:
                    won += 1
                    others = [c["strength"][i] for i in range(self.seats) if i != seat]
                    if max(others) == 0:
                        unopposed_wins += 1
                    if c["margin"] is not None:
                        win_margins.append(c["margin"])
                        # Upper bound on troops that could have stayed home
                        # and still won strictly, ignoring opponents'
                        # reactions to a smaller commitment.
                        bound = max(0, (c["margin"] - 1) // 2)
                        # If troops are the winner's only units, at least one
                        # must stay: without any unit strength is 0 even with
                        # swords [Main p. 12] (combat-and-round-end.md:10).
                        floor = (
                            1 if worms + commanders + agents == 0 and troops > 0 else 0
                        )
                        excess_troops.append(min(troops - floor, bound))
                pre = c["pre_intrigue_strength"]
                top = max(pre)
                leaders = [i for i, value in enumerate(pre) if value == top]
                strict_leader = leaders[0] if len(leaders) == 1 else None
                if is_winner and strict_leader != seat:
                    intrigue_flip_won += 1
                if strict_leader == seat and not is_winner:
                    intrigue_flip_lost += 1
            per_seat.append(
                {
                    "entered": entered,
                    "won": won,
                    "unopposed_wins": unopposed_wins,
                    "win_margin": _mean(win_margins),
                    "excess_troops": _mean(excess_troops),
                    "one_unit_entries": one_unit_entries,
                    "one_unit_rewarded": one_unit_rewarded,
                    "worm_entries": worm_entries,
                    "worm_not_first": worm_not_first,
                    "doubled_rewards": doubled_rewards,
                    # Total sandworms this seat summoned over the whole game,
                    # from sandworm_deployed, reveal_sandworm_deployed and
                    # maker board_effect_resolved events (see module
                    # docstring for the three payload keys).
                    "worms_summoned": self._worms_summoned[seat],
                    "intrigue_flip_won": intrigue_flip_won,
                    "intrigue_flip_lost": intrigue_flip_lost,
                    # Whether this seat's step destroyed the Shield Wall
                    # [Main p. 14] (C2.4); a per-seat bool so the summary can
                    # compare winners' vs. all seats' share, unlike the
                    # game-column seat index in "wall_dropper".
                    "dropped_wall": self._wall_dropper == seat,
                    # Mean garrison (troops_garrison) at the moment this
                    # seat's Agent landed on a Combat space, over the game.
                    "garrison_combat_visit": _mean(self._garrison_combat_visits[seat]),
                    # Same, restricted to visits while the round's Conflict
                    # is tier III.
                    "garrison_tier3_visit": _mean(self._garrison_tier3_visits[seat]),
                    # Agent turns onto the Heighliner space, over the game.
                    "heighliner_visits": self._heighliner_visits[seat],
                }
            )
        game: Columns = {
            "conflicts": list(self._conflicts),
            "conflicts_no_winner": sum(
                1 for c in self._conflicts if c["winner"] is None
            ),
            "wall_fall_round": self._wall_fall_round,
            "wall_dropper": self._wall_dropper,
        }
        return per_seat, game


COLLECTORS: tuple[type[Collector], ...] = (CombatCollector,)
