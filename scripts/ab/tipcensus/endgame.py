"""Endgame timing (C1.7, C8.2, C8.3) and Bloodlines Commander/Tech tiles (C7.1, C7.2).

``EndgameCollector`` watches when Endgame opens and what happens in the
window between "Endgame started" and the game actually finishing, including
whether the leader at that moment stays the winner. ``BloodlinesTechCollector``
tracks the Sardaukar Commander economy and the Tech tiles with the sharpest
recurring costs (Forbidden Weapons, Advanced Data Analysis).
"""

from __future__ import annotations

from dataclasses import replace

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import IntrigueTiming
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.tournament import MatchSpec
from dune_imperium.rules.effect_interpreter import flippable_battle_card_ids
from dune_imperium.rules.endgame import FinalStanding, final_standings
from dune_imperium.rules.influence import influence_amount

from .base import Collector, Columns, Step, arguments, payload

# Crysknife / Desert Mouse / Ornithopter: "—OR— Endgame: flip a face-up
# battle card of that icon for 1 Victory Point" [Main pp. 14, 20]
# (content/uprising/intrigue.py ``_spice_or_endgame_flip``, used at lines
# ~356, ~393, ~584). Their card ID happens to equal the matching BattleIcon
# value, since both are derived from the same printed name.
_PLOT_ICON_CARD_IDS: tuple[str, ...] = (
    BattleIcon.CRYSKNIFE.value,
    BattleIcon.DESERT_MOUSE.value,
    BattleIcon.ORNITHOPTER.value,
)


def _pre_endgame_tech_state(
    post: GameState, events: tuple[GameEvent, ...]
) -> GameState:
    """Undo the Endgame-opening Tech VP so ``post`` matches what the round-end
    check actually saw.

    ``rules/phases.py`` ``resolve_recall_or_endgame`` builds the phase=ENDGAME
    state, emits ``endgame_started``, and only then runs
    ``apply_endgame_tech_effects`` (CHOAM Transports, Panopticon -- OQ-040)
    in the *same* ``RuleResult`` (phases.py lines 366-374), so ``post`` here
    already has that Tech VP folded in. This walks the Tech events (their
    event ids all contain ``:endgame_tech:``) back out of ``post`` to
    reconstruct the exact state the "10+ VP / empty deck" check ran against.
    """

    tech_vp = [0] * len(post.players)
    for event in events:
        if ":endgame_tech:" not in event.event_id:
            continue
        data = payload(event)
        player = int(data["player"])
        if event.kind == "victory_points_gained":
            # CHOAM Transports: "Endgame: worth 1 VP if you have completed
            # four or more contracts" [Bloodlines Tech tile] -- a flat VP
            # gain.
            tech_vp[player] += int(data["amount"])
        elif (
            event.kind == "influence_gained"
            and influence_amount(
                post.players[player].influence, Faction(str(data["faction"]))
            )
            == 2
        ):
            # Panopticon: "gain 1 Influence with each Faction where you have
            # 1 or less" only scores a Victory Point on the 1 -> 2 step
            # [Main p. 7] (rules/influence.py line 46).
            tech_vp[player] += 1
    return replace(
        post,
        players=tuple(
            replace(player, victory_points=player.victory_points - tech_vp[i])
            for i, player in enumerate(post.players)
        ),
    )


class EndgameCollector(Collector):
    """Endgame trigger, the pre-Endgame leader, and the Endgame window itself."""

    name = "end"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        self._round_at_start: int | None = None
        self._trigger_vp: bool | None = None
        self._trigger_deck: bool | None = None
        self._leader_at_start: int | None = None
        self._vp_at_start: list[int | None] = [None] * seats
        self._endgame_intrigue_plays = [0] * seats
        self._plot_icon_plays = [0] * seats
        self._plot_icon_plays_flippable = [0] * seats
        # Round number of every Plot-icon play, to filter to the last round
        # once the final round number is known (``finish``).
        self._plot_icon_play_rounds: list[list[int]] = [[] for _ in range(seats)]
        self._pass_endgame_with_play = [0] * seats

    def step(self, s: Step) -> None:
        for event in s.events:
            if event.kind == "endgame_started" and self._round_at_start is None:
                # "Endgame이 시작되면... [Main p. 15]": the Round Start/Recall
                # check (rules/phases.py resolve_recall_or_endgame) fires the
                # Endgame-opening Tech effects (CHOAM Transports,
                # Panopticon -- OQ-040) in the same RuleResult as this event,
                # so ``s.post`` already has that Tech VP folded in.
                # ``_pre_endgame_tech_state`` reverses it back to the state
                # the round-end check actually ran against.
                self._round_at_start = s.post.round_number
                at_check = _pre_endgame_tech_state(s.post, s.events)
                self._trigger_vp = any(
                    player.victory_points >= 10 for player in at_check.players
                )
                self._trigger_deck = not at_check.conflict_deck
                self._vp_at_start = [
                    player.victory_points for player in at_check.players
                ]
                self._leader_at_start = _rank_one_seat(final_standings(at_check))
            elif event.kind == "intrigue_played":
                self._observe_intrigue_play(s, event)
        if (
            s.owner is not None
            and s.action is not None
            and s.action.action_id == "pass_endgame_intrigue"
            and any(a.action_id == "play_intrigue" for a in s.legal)
        ):
            self._pass_endgame_with_play[s.owner] += 1

    def _observe_intrigue_play(self, s: Step, event: GameEvent) -> None:
        data = payload(event)
        option_value = data.get("option")
        if option_value is None:
            # A face-up Trigger card (e.g. Harvest Cells) fires through
            # rules/combat.py's Conflict-end trigger path
            # (``resolve_faceup_trigger_option``), which plays it without
            # choosing one of ``entry.options`` by index -- always Combat
            # timing, never one of the three battle-icon cards or an
            # Endgame-timing option, so it is outside what these columns
            # count.
            return
        card_id = str(data["card_id"])
        option_index = int(option_value)
        player = int(data["player"])
        entry = intrigue_card_for_instance(card_id)
        option = entry.options[option_index]
        if option.timing is IntrigueTiming.ENDGAME:
            self._endgame_intrigue_plays[player] += 1
            return
        if (
            option.timing is IntrigueTiming.PLOT
            and entry.card.card_id in _PLOT_ICON_CARD_IDS
        ):
            self._plot_icon_plays[player] += 1
            self._plot_icon_play_rounds[player].append(s.pre.round_number)
            icon = BattleIcon(entry.card.card_id)
            if flippable_battle_card_ids(s.pre.players[player], icon):
                self._plot_icon_plays_flippable[player] += 1

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        final_vp = {standing.player: standing.victory_points for standing in standings}
        final_round = final.round_number
        per_seat: list[Columns] = []
        for seat in range(self.seats):
            vp_start = self._vp_at_start[seat]
            # endgame_vp: Victory Points gained from the Endgame-start
            # snapshot above (the state right as the round-end check ran,
            # before Tech's own Endgame-opening bonus -- CHOAM Transports,
            # Panopticon -- is paid) to the final standings. That Tech VP,
            # any Endgame Intrigue play and a wild battle-icon match [Main
            # pp. 7, 15, 20] are what can move it.
            endgame_vp = final_vp[seat] - vp_start if vp_start is not None else None
            last_round_plays = sum(
                1 for r in self._plot_icon_play_rounds[seat] if r == final_round
            )
            per_seat.append(
                {
                    "endgame_vp": endgame_vp,
                    # Intrigue plays whose chosen option's timing is Endgame
                    # (any card with an Endgame line, not only the three
                    # battle-icon cards).
                    "endgame_intrigue_plays": self._endgame_intrigue_plays[seat],
                    # Plays of Crysknife/Desert Mouse/Ornithopter's Plot
                    # option (1 spice) rather than their Endgame option.
                    "plot_icon_plays": self._plot_icon_plays[seat],
                    # Of those Plot plays, how many were made while a
                    # face-up matching or wild battle card was then
                    # flippable (rules/effect_interpreter.py
                    # ``flippable_battle_card_ids``) -- not necessarily a
                    # lost Victory Point (a wild match can still be caught
                    # by the Endgame's own wild-match resolution, and a
                    # face-up card can be auto-matched before Endgame).
                    "plot_icon_plays_flippable": self._plot_icon_plays_flippable[seat],
                    # Of those Plot plays, how many were made in the round
                    # that turned out to be the game's last round.
                    "plot_icon_plays_last_round": last_round_plays,
                    # pass_endgame_intrigue chosen while play_intrigue was
                    # also legal in that Endgame window (a card was left
                    # unplayed on purpose or by oversight).
                    "pass_endgame_with_play": self._pass_endgame_with_play[seat],
                }
            )
        winner = _rank_one_seat(standings)
        leader_changed = (
            winner != self._leader_at_start
            if self._leader_at_start is not None
            else None
        )
        game: Columns = {
            # Round number in which Endgame opened (rounds never advance
            # again once it has: rules/phases.py increments round_number
            # only in ``begin_round``, which Endgame skips).
            "endgame_round": self._round_at_start,
            # Some seat already had >= 10 Victory Points at that moment
            # [Main p. 15].
            "trigger_vp": self._trigger_vp,
            # The Conflict deck was empty at that moment [Main p. 15].
            "trigger_deck": self._trigger_deck,
            # The seat ranked 1st (rules/endgame.py final_standings) right
            # as Endgame opened is not the seat that finally won -- the
            # Endgame Intrigue window or a wild-icon match changed it
            # (C8.3).
            "leader_changed": leader_changed,
        }
        return per_seat, game


class BloodlinesTechCollector(Collector):
    """Sardaukar Commanders (C7.2) and the sharpest recurring Tech costs (C7.1)."""

    name = "bt"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        self._commanders_acquired = [0] * seats
        self._commanders_recruited_paid = [0] * seats
        self._commander_retreats = [0] * seats
        self._commanders_deployed = [0] * seats
        self._skill_reveal_bonuses = [0] * seats
        self._tech_acquired = [0] * seats
        self._tech_spice = [0] * seats
        self._tech_trashed = [0] * seats
        self._fw_strength = [0] * seats
        self._fw_trash = [0] * seats
        self._fw_influence_lost = [0] * seats
        self._ada_spies_trashed = [0] * seats

    def step(self, s: Step) -> None:
        for event in s.events:
            kind = event.kind
            if kind == "sardaukar_commander_acquired":
                self._commanders_acquired[int(payload(event)["player"])] += 1
            elif kind == "sardaukar_commander_recruited":
                self._commanders_recruited_paid[int(payload(event)["player"])] += 1
            elif kind == "troops_retreated":
                data = payload(event)
                # ``lose_unit`` (unit_loss.py) sends a Commander lost from
                # the Conflict through ``retreat_units`` first, with a
                # ``<source>:loss`` step_source, so its event id always ends
                # ``:loss:retreat`` -- that is a loss, not the "retreat and
                # reuse" tip C7.2 is about, so it is excluded here.
                # ``retreat_opponent_troop`` (agent_effects.py) also calls
                # ``retreat_units``, but on the *target* seat, with a
                # ``:opponent:<target>`` step_source -- a forced retreat
                # imposed by an opponent, not this seat's own choice, so it
                # is excluded too.
                if (
                    data.get("commanders", 0)
                    and not event.event_id.endswith(":loss:retreat")
                    and ":opponent:" not in event.event_id
                ):
                    self._commander_retreats[int(data["player"])] += 1
            elif kind == "commanders_deployed":
                # combat_deployment.py's Agent-turn deployment and
                # reveal_turn.py's Reveal-turn one: ``count`` here is
                # Commanders only.
                data = payload(event)
                self._commanders_deployed[int(data["player"])] += int(data["count"])
            elif kind == "commanders_withdrawn":
                # apply_commander_withdrawal (combat_deployment.py): moves
                # Commanders deployed *this* Agent turn back to the garrison
                # before Combat resolves, so they never fought -- net them
                # out of the same-turn deployment count above.
                data = payload(event)
                self._commanders_deployed[int(data["player"])] -= int(data["count"])
            elif kind == "troops_deployed":
                # An Intrigue card's DeployFromGarrison reward
                # (rules/intrigue.py ``_deploy_units``) can also move
                # Commanders and shares this kind with ordinary troops; only
                # its optional ``commanders`` share counts here.
                data = payload(event)
                commanders = data.get("commanders", 0)
                if commanders:
                    self._commanders_deployed[int(data["player"])] += int(commanders)
            elif kind == "skill_reveal_bonus":
                self._skill_reveal_bonuses[int(payload(event)["player"])] += 1
            elif kind == "tech_acquired":
                data = payload(event)
                player = int(data["player"])
                self._tech_acquired[player] += 1
                self._tech_spice[player] += int(data["spice"])
            elif kind == "tech_trashed":
                self._tech_trashed[int(payload(event)["player"])] += 1
            elif kind == "spy_trashed":
                self._ada_spies_trashed[int(payload(event)["player"])] += 1
            elif (
                kind == "influence_lost"
                and s.action is not None
                and s.action.action_id == "choose_tech_strength"
            ):
                # Forbidden Weapons' strength option: "lose 1 Influence with
                # a Faction where you have >= 1, if possible" [Bloodlines
                # p. 12] -- ``choose_tech_strength``'s own RuleResult is the
                # only source of an ``influence_lost`` event in this step.
                lost = payload(event)
                self._fw_influence_lost[s.action.actor] += int(lost["amount"])
        # Desert Scouts' own commander retreat (leader_abilities.py) shares
        # the ``troops_retreated`` kind above but never tags a ``commanders``
        # payload key, so it needs its own check here.
        if (
            s.owner is not None
            and s.action is not None
            and s.action.action_id == "retreat_leader_commander"
        ):
            self._commander_retreats[s.owner] += 1
        # Chani / Clever Tactician / Command Center's "retreat two troops"
        # Reveal choice (reveal_turn.py ``legal_reveal_troop_retreat_actions``
        # / the action's own resolution) can move 1 or 2 Commanders to the
        # garrison, but its ``troops_retreated`` event has no ``commanders``
        # payload key (reveal_turn.py lines ~980-984) -- read it off the
        # chosen action's own arguments instead.
        if (
            s.owner is not None
            and s.action is not None
            and s.action.action_id == "retreat_two_troops_for_reveal"
            and arguments(s.action).get("commanders", 0)
        ):
            self._commander_retreats[s.owner] += 1
        if s.owner is not None and s.action is not None:
            if s.action.action_id == "choose_tech_strength":
                self._fw_strength[s.owner] += 1
            elif s.action.action_id == "choose_tech_trash":
                self._fw_trash[s.owner] += 1

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        bloodlines = self.spec.config.bloodlines
        tech_module = self.spec.config.tech_module
        per_seat: list[Columns] = []
        for seat in range(self.seats):
            row: Columns = {
                # A new Commander entering play from the bank (board-space
                # visit or an effect granting one outright) [Bloodlines
                # p. 4].
                "commanders_acquired": (
                    self._commanders_acquired[seat] if bloodlines else None
                ),
                # "you may pay 2 Solari to recruit one Sardaukar Commander
                # from your supply" -- once per turn, supply -> garrison,
                # no new Skill [Bloodlines p. 4].
                "commanders_recruited_paid": (
                    self._commanders_recruited_paid[seat] if bloodlines else None
                ),
                # Steps that returned at least one Commander from the
                # Conflict to the garrison by this seat's own choice (a
                # Skill, Intrigue or Leader-ability retreat, or the Reveal
                # "retreat two troops" choice), the "retreat-and-reuse" tip
                # (C7.2) -- excludes a Commander lost from the Conflict (a
                # cost or an opponent's effect, which also retreats it to
                # the garrison first: unit_loss.py) and a Commander an
                # opponent's card forces this seat to retreat
                # (agent_effects.py ``retreat_opponent_troop``); distinct
                # from the automatic conflict-cleanup return to supply,
                # which has no event of its own.
                "commander_retreats": (
                    self._commander_retreats[seat] if bloodlines else None
                ),
                # Sum of Commanders added to a Conflict this turn: the basic
                # deployment (combat_deployment.py / reveal_turn.py
                # ``commanders_deployed`` events) plus any Intrigue-granted
                # DeployFromGarrison that moved a Commander
                # (rules/intrigue.py, a ``troops_deployed`` event's
                # ``commanders`` share), net of any same-turn
                # ``commanders_withdrawn`` (combat_deployment.py
                # ``apply_commander_withdrawal``) before Combat resolves.
                "commanders_deployed": (
                    self._commanders_deployed[seat] if bloodlines else None
                ),
                # Reveal-turn Skill bonuses paid out (Charismatic/Driven/
                # Hardy) while a Commander was in the Conflict [Bloodlines
                # p. 4].
                "skill_reveal_bonuses": (
                    self._skill_reveal_bonuses[seat] if bloodlines else None
                ),
                # Tech tiles bought (any stack, Secret Project included).
                "tech_acquired": self._tech_acquired[seat] if tech_module else None,
                # Total spice paid across those acquisitions.
                "tech_spice": self._tech_spice[seat] if tech_module else None,
                # Tech tiles that left the seat's tableau: Forbidden
                # Weapons' own trash option, Plasteel Blades' trash-for-Skill,
                # or a Leader ability's tech trash.
                "tech_trashed": self._tech_trashed[seat] if tech_module else None,
                # Forbidden Weapons' "choose swords" option taken (3
                # swords, + an Influence loss if any Faction allowed it)
                # [Bloodlines p. 12].
                "fw_strength": self._fw_strength[seat] if tech_module else None,
                # Forbidden Weapons' "lose all spice and trash the tile"
                # option taken instead.
                "fw_trash": self._fw_trash[seat] if tech_module else None,
                # Influence actually lost through Forbidden Weapons'
                # strength option (0 when the seat held no Influence to
                # lose).
                "fw_influence_lost": (
                    self._fw_influence_lost[seat] if tech_module else None
                ),
                # Advanced Data Analysis' acquisition cost: one board Spy
                # trashed to the box [Bloodlines pp. 7, 12].
                "ada_spies_trashed": (
                    self._ada_spies_trashed[seat] if tech_module else None
                ),
            }
            per_seat.append(row)
        return per_seat, {}


COLLECTORS: tuple[type[Collector], ...] = (EndgameCollector, BloodlinesTechCollector)


def _rank_one_seat(standings: tuple[FinalStanding, ...]) -> int:
    return next(standing.player for standing in standings if standing.rank == 1)
