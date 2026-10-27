"""Stage B3: a waiting effect is picked first, then its target.

docs/stage-b-plan.md 3c ("B3a 세부 설계"), OQ-111. The rules still offer and
resolve every effect through the actions their providers build -- a *whole*
action names the effect and its target at once (``trash_agent_card`` of one
card). This module shows a whole action to the outside as a *path* of steps:

- an **effect row** -- the verb of what the effect does and the place that
  points at it, ``ref``: the kind of source (``source``), the entity that
  printed the effect (``printed``: a card type, the visited space, the
  leader, a Tech tile, a Contract), the printed icon when the entity has
  several (``icon``) and ``box=1`` for a grafted turn's second card
  (decision 3, user decision 2026-10-19 B3-1 (가));
- then one **target row** per target the effect picks, named by the kind of
  target -- ``choose_personal_card(card_id)``, ``choose_post(post_id)`` ...
  (B3-2 (가)). A quantity (a unit mix) rides on the path's last row.

A frame that offers several effects at once (``EFFECT_STEP_FRAMES``: the
Agent-turn effect frame since stage B3a, the Reveal frame since B3b-2, the
turn frame and the Combat, Conflict-end and Endgame Intrigue windows since
B3c-1, the Conflict and Contract reward windows, an Intrigue card's lines,
Servo-Receivers' Signet frame, a research window ordering a pair's icons
and a Tech window owing acquire icons since B3d-1) offers the effect rows;
an effect without a target is resolved by its row, and one with targets
keeps the rows picked so far in the frame's context
(``EFFECT_PICK_KEY``) and offers only the next rows of its paths -- even when
there is one target (OQ-111 (2)). The context is no other seat's to see
(B3-3 (가), OQ-111 (4)); the seat's own view reads it
(``core.observation.effect_pick_of``). When a path ends, its whole action is
applied to the state without the pick, so the rules never see the steps.

A window opened for one effect (``TARGET_STEP_FRAMES``, stage B3d-2a, D-1
(가)) does not ask for its effect again: the effect row that opened it (a
reward icon, an Agent box's icon, a turn row) picked it already, so the
window's own effect is shown by its target rows alone (``TARGET_SPECS``,
``WINDOW_OWN``). Another effect offered beside it -- recalling a Spy first
when the supply is empty, an Intrigue card's automatic rewards -- and an own
effect with no target keep their effect row.

A refusal or an empty confirmation (stage B3d-3, D-2) is the row ``decline``
or ``confirm_empty`` naming the effect it answers: that effect's verb
(``of``) and its place, as the effect's own row names it.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.effect_dsl import RecallSpy
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import EFFECT_PICK_KEY, agent_box_cards
from dune_imperium.core.state import GameState
from dune_imperium.rules.action_shapes import PRINTER_KEY, Source, Verb, printer_parts
from dune_imperium.rules.frames import FrameKind, replace_top_frame, with_context

type Arguments = tuple[tuple[str, ActionValue], ...]
type Row = tuple[str, Arguments]


class Choose(StrEnum):
    """What a target row picks; its action id is ``choose_<value>``."""

    PERSONAL_CARD = "personal_card"
    INTRIGUE_CARD = "intrigue_card"
    IMPERIUM_CARD = "imperium_card"
    RESERVE_CARD = "reserve_card"
    TLEILAXU_CARD = "tleilaxu_card"
    POST = "post"
    SPACE = "space"
    TRACK_SPACE = "track_space"
    FACTION = "faction"
    CONTRACT = "contract"
    TECH = "tech"
    SKILL = "skill"
    SEAT = "seat"
    OPTION = "option"
    # A Conflict card or an Objective card (the Endgame wild match).
    CONFLICT_CARD = "conflict_card"
    # Stage B3d-2a: a unit to lose (its zone; a Commander rides along), a
    # number of units to move, a leader to draft, a Navigation card.
    UNIT = "unit"
    COUNT = "count"
    LEADER = "leader"
    NAVIGATION_CARD = "navigation_card"
    # Stage B3d-2b: an Arrakeen Scouts subcommittee to join, a mission's
    # part to take.
    SUBCOMMITTEE = "subcommittee"
    MISSION = "mission"

    @property
    def action_id(self) -> str:
        return f"choose_{self.value}"


# The one argument each target row names its target with, whatever the
# whole action called it (``intrigue_card_id``, ``card_id`` ...).
CHOOSE_ARGUMENT: Final[Mapping[Choose, str]] = MappingProxyType({
    Choose.PERSONAL_CARD: "card_id",
    Choose.INTRIGUE_CARD: "card_id",
    Choose.IMPERIUM_CARD: "instance_id",
    Choose.RESERVE_CARD: "card_id",
    Choose.TLEILAXU_CARD: "instance_id",
    Choose.POST: "post_id",
    Choose.SPACE: "space_id",
    Choose.TRACK_SPACE: "space_id",
    Choose.FACTION: "faction",
    Choose.CONTRACT: "instance_id",
    Choose.TECH: "tech_id",
    Choose.SKILL: "skill_id",
    Choose.SEAT: "player",
    Choose.OPTION: "option",
    Choose.CONFLICT_CARD: "card_id",
    Choose.UNIT: "zone",
    Choose.COUNT: "count",
    Choose.LEADER: "leader_id",
    Choose.NAVIGATION_CARD: "card_id",
    Choose.SUBCOMMITTEE: "subcommittee_id",
    Choose.MISSION: "target",
})
CHOOSE_ACTIONS: Final = frozenset(kind.action_id for kind in Choose)


class Printed(StrEnum):
    """Where a whole action's printed entity is read when no argument names it."""

    # The Agent box's card, by type: box 0 is the played card, box 1 the
    # graft partner (``box`` tag). A Signet Ring box's effect is printed on
    # the leader: its rows name the leader's face, from ``Source.LEADER``.
    BOX_CARD = "box_card"
    # The board space the turn's Agent went to.
    VISITED_SPACE = "visited_space"
    # The seat's leader (its face-up side).
    LEADER = "leader"
    # The Intrigue window the frame opens: ``plot`` on the seat's turn
    # frames, ``combat``, ``endgame`` (``intrigue.intrigue_window``).
    INTRIGUE_WINDOW = "intrigue_window"
    # The research space whose bonus window is on top (stage B3c-2a), for
    # its refusal; a research icon names its space itself since stage B3e-1
    # (``NAMED``).
    RESEARCH_SPACE = "research_space"
    # The Conflict card whose reward row the window pays (stage B3d-1): the
    # Conflict of this round, ``state.current_conflict_ids[-1]``.
    CONFLICT_CARD = "conflict_card"
    # A completed Contract: the whole action's ``contract_id`` (a row on its
    # owner's turn, B3b-1), else the Contract reward window's own (B3d-1) or
    # its Spy window's (``contract_spy_id``, B3d-2a).
    CONTRACT = "contract"
    # The Intrigue card whose printed lines its window offers (B3d-1).
    INTRIGUE_CARD = "intrigue_card"
    # The whole action names its effect's source and printed entity in its
    # own ``source`` and ``printed`` arguments (and ``printed_box`` for a
    # grafted turn's second card): an optional trash waiting on the turn,
    # whose printer the waiting item records (stage B3c-2b,
    # ``optional_trash.trash_printer``); since stage B3e-1 a research space's
    # icon, a triggered draw waiting as its own step and a Reveal's gathered
    # gain, one whole action per entity that printed one (decision 3).
    NAMED = "named"
    # Stage B3d-2a: the card whose acquire box opened the Spy window (its
    # ``acquisition_card_id``), by type.
    ACQUIRED_CARD = "acquired_card"
    # Stage B3d-2a: the entity that opened the window, as the window records
    # it (its ``printer``, ``action_shapes.printer_value``): the Spy
    # placement window of an Influence track, a Tech tile, an Intrigue card
    # or a Scouts line.
    WINDOW = "window"
    # Stage B3d-2b: the Arrakeen Scouts mission whose part the window offers
    # (its ``mission_id``).
    MISSION = "mission"
    # Stage B3d-3: the Scouts item whose line, choice or market the frame
    # offers (its ``item``).
    SCOUTS_ITEM = "scouts_item"
    # Stage B3d-3: what gives a Skill window its Commander: Plasteel Blades'
    # tile, or the card whose trash acquires the bank's Commander (its
    # ``card_id``).
    SKILL_WINDOW = "skill_window"
    # Stage B3d-3: the Tech tile whose acquire Influence waits in a Tech
    # window's icons (``pending_tech_acquire_effects``).
    TECH_PENDING = "tech_pending"


@dataclass(frozen=True, slots=True)
class StepSpec:
    """How one whole action id is shown as steps (module docstring).

    ``verb`` is the effect row's id, or a table from the icon to it when one
    whole id resolves icons of different kinds (``resolve_board_effect``;
    the key ``""`` is the verb when the whole action names no icon).
    ``printed`` is a ``Printed`` rule, the whole action's argument that
    names the entity, or ``"=<entity>"`` for the one entity that prints the
    id (a single card's Reveal choice, a market). ``icon`` is a constant
    label, ``"arg:<name>"`` for an argument, or ``""`` for none. ``option``
    names one of a printed choice's alternatives that share a verb (Sietch
    Tabr's water or supplies), as the effect row's ``option``, or
    ``"arg:<name>"`` for an argument (an Intrigue card's printed line).
    ``targets``
    are the whole action's target arguments in the order they are picked,
    ``"=<value>"`` for a target the whole action's id itself names (the
    Conflict of a recall); an argument the whole action does not carry, or
    carries empty, is no step of it. ``of`` is the verb of the effect a
    refusal or an empty confirmation answers (stage B3d-3), or a table from
    the row's icon (else its printed entity) to it. An ``icon`` of
    ``"window"`` is read off the window (a Conflict reward's).
    """

    verb: Verb | Mapping[str, Verb]
    source: Source
    printed: Printed | str
    icon: str = ""
    option: str = ""
    targets: tuple[tuple[str, Choose], ...] = ()
    of: Verb | Mapping[str, Verb] | None = None


_ARG = "arg:"
_FIXED = "="


def _spec(
    verb: Verb | Mapping[str, Verb],
    source: Source,
    printed: Printed | str,
    *,
    icon: str = "",
    option: str = "",
    targets: tuple[tuple[str, Choose], ...] = (),
    of: Verb | Mapping[str, Verb] | None = None,
) -> StepSpec:
    return StepSpec(verb, source, printed, icon, option, targets, of)


_WINDOW_ICON: Final = "window"


_V = Verb
_S = Source
_C = Choose
_BOX = Printed.BOX_CARD
_SPACE = Printed.VISITED_SPACE
_LEADER = Printed.LEADER
_CARD = (("card_id", _C.PERSONAL_CARD),)
_INTRIGUE = (("intrigue_card_id", _C.INTRIGUE_CARD),)
_POST = (("post_id", _C.POST),)
_FACTION = (("faction", _C.FACTION),)
_IMPERIUM = (("instance_id", _C.IMPERIUM_CARD),)
_RESERVE = (("card_id", _C.RESERVE_CARD),)
_RECALLED = (("space_id", _C.SPACE),)
_CONFLICT = (("=conflict", _C.SPACE),)
# Who takes an Alliance token an Influence loss hands on, when several could.
_RECIPIENT = ("alliance_recipient", _C.SEAT)

# What a visited space's automatic icon does (``board_effects``' keys).
_BOARD_ICON_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "cards": _V.DRAW,
    "contract": _V.TAKE,
    # The original game's Foldspace and Mentat spaces [DI pp. 17-18].
    "foldspace": _V.ACQUIRE,
    "high_council": _V.TAKE,
    "intrigue": _V.DRAW,
    "mentat": _V.TAKE,
    "research": _V.ADVANCE,
    "resources": _V.GAIN,
    "swordmaster": _V.TAKE,
    "troops": _V.RECRUIT,
})
# What an Agent box's keyed icon does (``agent_effects.AGENT_ICON_*``); ""
# is a single-effect box resolved as a whole.
AGENT_ICON_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "": _V.RESOLVE,
    "cards": _V.DRAW,
    "cards_second": _V.DRAW,
    "intrigue": _V.DRAW,
    "pledge": _V.GAIN,
    "research": _V.ADVANCE,
    "return_self": _V.TAKE,
    "solari": _V.GAIN,
    "spice": _V.GAIN,
    "trash_self": _V.TRASH,
    "troops": _V.RECRUIT,
    "water": _V.GAIN,
})
# What a research space's icon does (``immortality.RESEARCH_ICON_ORDER``).
_RESEARCH_ICON_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "cards": _V.DRAW,
    "intrigue": _V.DRAW,
    "specimen": _V.GENERATE_SPECIMENS,
    "tleilaxu": _V.ADVANCE,
    "trash": _V.TRASH,
})
# What a Conflict reward icon does (``combat.COMBAT_REWARD_ICON_KINDS``).
_COMBAT_ICON_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "resources": _V.GAIN,
    "intrigue": _V.DRAW,
    "troops": _V.RECRUIT,
    "victory_points": _V.GAIN,
    "faction_influence": _V.GAIN_INFLUENCE,
    "control": _V.TAKE,
    "contract": _V.TAKE,
    "choose_influence": _V.GAIN_INFLUENCE,
    "distinct_influence": _V.GAIN_INFLUENCE,
    "optional_solari": _V.PAY,
    "optional_spice": _V.PAY,
    "optional_recall_spies": _V.RECALL_SPY,
    "trash": _V.TRASH,
    "spy": _V.PLACE_SPY,
    "deep_cover_spy": _V.PLACE_SPY,
    # Planetary Array's card, a row of the winner's window (OQ-121).
    "planetary_array": _V.DRAW,
    # The sole winner's close of its window: no more winning Intrigue
    # (OQ-121 decision 6; the original game's To the Victor... and Demand
    # Respect). Nothing is gained, so it only resolves the row.
    "winning_intrigue": _V.RESOLVE,
    # The original game's: the Mentat, one Faction's two Influence, and the
    # lines of a row of alternatives.
    "mentat": _V.TAKE,
    "one_faction_influence": _V.GAIN_INFLUENCE,
    "line_0": _V.CHOOSE,
    "line_1": _V.CHOOSE,
    "line_2": _V.CHOOSE,
})
# What a completed Contract's icon does (``contracts.CONTRACT_REWARD_ICON_KINDS``).
_CONTRACT_ICON_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "cards": _V.DRAW,
    "contract": _V.TAKE,
    "deep_cover_spy": _V.PLACE_SPY,
    "faction_influence": _V.GAIN_INFLUENCE,
    "intrigue": _V.DRAW,
    "recall_agent": _V.RECALL_AGENT,
    "resources": _V.GAIN,
    "spy": _V.PLACE_SPY,
    "troops": _V.RECRUIT,
})
# What an Imperium card's acquire icon does (``acquire_icons``, OQ-141): an
# Influence with a fixed Faction, or with the one the owner chooses.
_ACQUIRE_ICON_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "influence_emperor": _V.GAIN_INFLUENCE,
    "influence_spacing_guild": _V.GAIN_INFLUENCE,
    "influence_bene_gesserit": _V.GAIN_INFLUENCE,
    "influence_fremen": _V.GAIN_INFLUENCE,
    "influence_any": _V.GAIN_INFLUENCE,
})
# What a Tech tile's acquire icon does (``TechTile.acquire_effect_keys``).
_TECH_ICON_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "cards": _V.DRAW,
    "contracts": _V.TAKE,
    "influence": _V.GAIN_INFLUENCE,
    "intrigue": _V.DRAW,
    "intrigue_or_card": _V.DRAW,
    "shield_wall": _V.DESTROY_SHIELD_WALL,
    "signet": _V.USE,
    "solari": _V.GAIN,
    "spy_0": _V.PLACE_SPY,
    "spy_1": _V.PLACE_SPY,
    "trash": _V.TRASH,
    "troops": _V.RECRUIT,
    "victory_points": _V.GAIN,
})

# What a research space's bonus does (``immortality.ResearchBonus``): the
# effect its refusal answers.
_RESEARCH_BONUS_VERBS: Final[Mapping[str, Verb]] = MappingProxyType({
    "c6r6": _V.GAIN_INFLUENCE,
    "c7r3": _V.TRASH,
    "c8r6": _V.PAY,
})
_D = _V.DECLINE
_E = _V.CONFIRM_EMPTY

STEP_SPECS: Final[Mapping[str, StepSpec]] = MappingProxyType({
    # --- A personal card's Agent box (a Signet Ring's: the leader's) --------
    "resolve_agent_card_effect": _spec(
        AGENT_ICON_VERBS, _S.AGENT_CARD, _BOX, icon="arg:effect"
    ),
    "choose_agent_card_influence": _spec(
        _V.GAIN_INFLUENCE, _S.AGENT_CARD, _BOX, targets=_FACTION
    ),
    "choose_agent_card_reward": _spec(
        _V.CHOOSE, _S.AGENT_CARD, _BOX, targets=(("reward", _C.OPTION),)
    ),
    "complete_contract_by_card": _spec(
        _V.COMPLETE_CONTRACT,
        _S.AGENT_CARD,
        _BOX,
        targets=(("instance_id", _C.CONTRACT),),
    ),
    "discard_agent_card": _spec(_V.DISCARD, _S.AGENT_CARD, _BOX, targets=_CARD),
    "select_corrinth_city_discard": _spec(
        _V.DISCARD, _S.AGENT_CARD, _BOX, targets=_CARD
    ),
    "pay_corrinth_city": _spec(_V.PAY, _S.AGENT_CARD, _BOX, targets=_CARD),
    "trash_agent_card": _spec(_V.TRASH, _S.AGENT_CARD, _BOX, targets=_CARD),
    "trash_agent_card_self_for_vp": _spec(_V.TRASH, _S.AGENT_CARD, _BOX),
    "trash_grafted_card_for_specimen": _spec(
        _V.TRASH, _S.AGENT_CARD, _BOX, targets=_CARD
    ),
    "trash_grafted_card_for_influence": _spec(
        _V.TRASH, _S.AGENT_CARD, _BOX, targets=_CARD
    ),
    "pay_agent_card_water": _spec(_V.PAY, _S.AGENT_CARD, _BOX),
    "pay_agent_card_spice": _spec(_V.PAY, _S.AGENT_CARD, _BOX),
    "pay_agent_card_solari": _spec(_V.PAY, _S.AGENT_CARD, _BOX),
    "pay_agent_card_specimen": _spec(_V.PAY, _S.AGENT_CARD, _BOX),
    "pay_agent_card_two_specimens": _spec(_V.PAY, _S.AGENT_CARD, _BOX),
    "pay_agent_card_five_solari_for_tleilaxu": _spec(_V.PAY, _S.AGENT_CARD, _BOX),
    # Arrakis Revolt's two payments: keep the Shield Wall or remove it.
    "pay_agent_card_spice_for_sandworm": _spec(
        _V.PAY, _S.AGENT_CARD, _BOX, option="sandworm"
    ),
    "pay_agent_card_spice_for_sandworm_and_shield_wall": _spec(
        _V.PAY, _S.AGENT_CARD, _BOX, option="sandworm_and_shield_wall"
    ),
    "lose_agent_card_troop": _spec(_V.LOSE_UNIT, _S.AGENT_CARD, _BOX),
    "lose_agent_card_influence": _spec(
        _V.LOSE_INFLUENCE, _S.AGENT_CARD, _BOX, targets=(*_FACTION, _RECIPIENT)
    ),
    "take_agent_card_from_discard": _spec(
        _V.TAKE, _S.AGENT_CARD, _BOX, targets=_CARD
    ),
    "pay_agent_card_intrigue_and_spice": _spec(
        _V.PAY, _S.AGENT_CARD, _BOX, targets=_INTRIGUE
    ),
    "trash_intrigue_for_agent_card": _spec(
        _V.TRASH, _S.AGENT_CARD, _BOX, targets=_INTRIGUE
    ),
    "acquire_imperium_by_card": _spec(
        _V.ACQUIRE, _S.AGENT_CARD, _BOX, targets=_IMPERIUM
    ),
    "acquire_imperium_with_solari": _spec(
        _V.ACQUIRE, _S.AGENT_CARD, _BOX, targets=_IMPERIUM
    ),
    "acquire_reserve_by_card": _spec(
        _V.ACQUIRE, _S.AGENT_CARD, _BOX, targets=_RESERVE
    ),
    "acquire_reserve_with_solari": _spec(
        _V.ACQUIRE, _S.AGENT_CARD, _BOX, targets=_RESERVE
    ),
    "place_agent_card_spy": _spec(_V.PLACE_SPY, _S.AGENT_CARD, _BOX, targets=_POST),
    "recall_spy_for_agent_card": _spec(
        _V.RECALL_SPY, _S.AGENT_CARD, _BOX, targets=_POST
    ),
    "recall_agent_for_agent_card": _spec(
        _V.RECALL_AGENT, _S.AGENT_CARD, _BOX, targets=_RECALLED
    ),
    "recall_conflict_agent_for_agent_card": _spec(
        _V.RECALL_AGENT, _S.AGENT_CARD, _BOX, targets=_CONFLICT
    ),
    "retreat_opponent_troop": _spec(
        _V.RETREAT, _S.AGENT_CARD, _BOX, targets=(("player", _C.SEAT),)
    ),
    "take_agent_card_combat_icon": _spec(
        _V.GAIN, _S.AGENT_CARD, _BOX, icon="combat"
    ),
    # --- The leader: its Signet Ring box and its leader ability -------------
    "advance_feyd_track": _spec(
        _V.ADVANCE,
        _S.LEADER,
        _LEADER,
        targets=(("space_id", _C.TRACK_SPACE),),
    ),
    "trash_leader_card": _spec(_V.TRASH, _S.LEADER, _LEADER, targets=_CARD),
    "place_leader_spy": _spec(_V.PLACE_SPY, _S.LEADER, _LEADER, targets=_POST),
    "recall_spy_for_leader_placement": _spec(
        _V.RECALL_SPY, _S.LEADER, _LEADER, targets=_POST
    ),
    "pay_leader_signet_spice": _spec(_V.PAY, _S.LEADER, _LEADER, option="spice"),
    "pay_leader_signet_solari": _spec(_V.PAY, _S.LEADER, _LEADER, option="solari"),
    "pay_leader_signet_water": _spec(_V.PAY, _S.LEADER, _LEADER, option="water"),
    "gain_leader_signet_troop": _spec(_V.RECRUIT, _S.LEADER, _LEADER),
    "choose_leader_signet_influence": _spec(
        _V.GAIN_INFLUENCE, _S.LEADER, _LEADER, targets=_FACTION
    ),
    # The original game's Helena Richese: Manipulate's Row card.
    "set_aside_leader_imperium": _spec(
        _V.SET_ASIDE, _S.LEADER, _LEADER, targets=_IMPERIUM
    ),
    # The original game's Earl Memnon Thorvald: Connections' Influence, an
    # icon of the visit that took the High Council seat.
    "choose_connections_influence": _spec(
        _V.GAIN_INFLUENCE, _S.LEADER, _LEADER, icon="connections", targets=_FACTION
    ),
    "acquire_leader_imperium": _spec(
        _V.ACQUIRE, _S.LEADER, _LEADER, targets=_IMPERIUM
    ),
    "acquire_leader_reserve": _spec(_V.ACQUIRE, _S.LEADER, _LEADER, targets=_RESERVE),
    "retreat_leader_troops": _spec(_V.RETREAT, _S.LEADER, _LEADER),
    "place_leader_bonus_spice": _spec(_V.PLACE_BONUS, _S.LEADER, _LEADER),
    "take_leader_bonus_spice": _spec(
        _V.TAKE, _S.LEADER, _LEADER, targets=(("space_id", _C.SPACE),)
    ),
    "deploy_leader_agent": _spec(_V.DEPLOY, _S.LEADER, _LEADER),
    "gain_leader_signet_spice": _spec(_V.GAIN, _S.LEADER, _LEADER),
    "trash_leader_tech": _spec(
        _V.TRASH, _S.LEADER, _LEADER, targets=(("tech_id", _C.TECH),)
    ),
    "use_other_memories": _spec(_V.USE, _S.LEADER, _LEADER),
    "pay_leader_board_repeat": _spec(
        _V.PAY, _S.LEADER, _LEADER, option="board_repeat"
    ),
    # --- A visited board space -----------------------------------------------
    "resolve_board_effect": _spec(
        _BOARD_ICON_VERBS, _S.BOARD_SPACE, _SPACE, icon="arg:effect"
    ),
    "resolve_faction_influence": _spec(
        _V.GAIN_INFLUENCE, _S.BOARD_SPACE, _SPACE, icon="faction"
    ),
    "resolve_espionage_place_spy": _spec(
        _V.PLACE_SPY, _S.BOARD_SPACE, _SPACE, icon="spy", targets=_POST
    ),
    "recall_spy_for_espionage": _spec(
        _V.RECALL_SPY, _S.BOARD_SPACE, _SPACE, icon="spy", targets=_POST
    ),
    "trash_card_for_desert_tactics": _spec(
        _V.TRASH, _S.BOARD_SPACE, _SPACE, icon="trash", targets=_CARD
    ),
    "choose_shipping_influence": _spec(
        _V.GAIN_INFLUENCE, _S.BOARD_SPACE, _SPACE, icon="influence", targets=_FACTION
    ),
    "take_sietch_tabr_supplies": _spec(
        _V.GAIN, _S.BOARD_SPACE, _SPACE, icon="sietch_tabr", option="supplies"
    ),
    "take_sietch_tabr_water": _spec(
        _V.GAIN, _S.BOARD_SPACE, _SPACE, icon="sietch_tabr", option="water"
    ),
    "take_sietch_tabr_water_and_destroy_wall": _spec(
        _V.GAIN,
        _S.BOARD_SPACE,
        _SPACE,
        icon="sietch_tabr",
        option="water_and_destroy_wall",
    ),
    "take_tuek_sietch_spice": _spec(
        _V.GAIN, _S.BOARD_SPACE, _SPACE, icon="tuek_sietch"
    ),
    "take_tuek_sietch_card": _spec(_V.DRAW, _S.BOARD_SPACE, _SPACE, icon="tuek_sietch"),
    "harvest_maker_spice": _spec(_V.GAIN, _S.BOARD_SPACE, "space_id", icon="maker"),
    "take_desert_riding_hooks": _spec(
        _V.TAKE, _S.BOARD_SPACE, "space_id", icon="maker"
    ),
    "summon_maker_sandworms": _spec(
        _V.SUMMON_SANDWORM, _S.BOARD_SPACE, "space_id", icon="maker"
    ),
    "trash_intrigue_for_imperial_privilege": _spec(
        _V.TRASH,
        _S.BOARD_SPACE,
        _SPACE,
        icon="imperial_privilege_intrigue",
        targets=(("card_id", _C.INTRIGUE_CARD),),
    ),
    "recall_agent_for_imperial_privilege": _spec(
        _V.RECALL_AGENT,
        _S.BOARD_SPACE,
        _SPACE,
        icon="imperial_privilege",
        targets=_RECALLED,
    ),
    "recall_conflict_agent_for_imperial_privilege": _spec(
        _V.RECALL_AGENT,
        _S.BOARD_SPACE,
        _SPACE,
        icon="imperial_privilege",
        targets=_CONFLICT,
    ),
    "acquire_sardaukar_commander": _spec(
        _V.ACQUIRE,
        _S.BOARD_SPACE,
        _SPACE,
        icon="sardaukar_commander",
        targets=(("skill_id", _C.SKILL),),
    ),
    "scouts_collect_mission": _spec(
        _V.COLLECT,
        _S.BOARD_SPACE,
        _SPACE,
        icon="scouts_mission",
        targets=(("choice", _C.OPTION),),
    ),
    "acquire_tech": _spec(
        _V.ACQUIRE,
        _S.BOARD_SPACE,
        _SPACE,
        icon="tech",
        targets=(("tech_id", _C.TECH), ("post_id", _C.POST)),
    ),
    # Gather Intelligence: a Spy connected to the visited space [Main p. 11].
    "gather_intelligence": _spec(_V.RECALL_SPY, _S.SPY, _SPACE, targets=_POST),
    # --- A Contract, a Tech tile ---------------------------------------------
    "complete_contract": _spec(_V.COMPLETE_CONTRACT, _S.CONTRACT, "instance_id"),
    # An icon of a completed Contract: waiting on its owner's turn (OQ-112
    # (4), B3b-1; the row names the Contract) or in its reward window (B3d-1;
    # the window names it).
    "resolve_contract_reward_icon": _spec(
        _CONTRACT_ICON_VERBS, _S.CONTRACT, Printed.CONTRACT, icon="arg:effect"
    ),
    # An icon of an acquired Imperium card's acquire box, waiting on its
    # owner's turn (OQ-141): the card names it; a chosen Faction is the
    # target row.
    "resolve_acquire_icon": _spec(
        _ACQUIRE_ICON_VERBS,
        _S.ACQUISITION,
        "acquired_card_id",
        icon="arg:effect",
        targets=_FACTION,
    ),
    "flip_tech": _spec(_V.FLIP, _S.TECH, "tech_id"),
    "resolve_tech_acquire_effect": _spec(
        _TECH_ICON_VERBS,
        _S.TECH,
        "tech_id",
        icon="arg:effect",
        targets=(("faction", _C.FACTION), ("choice", _C.OPTION)),
    ),
    # --- The Reveal frame (stage B3b-2): a purchase, one effect per market --
    "acquire_imperium": _spec(
        _V.ACQUIRE, _S.PURCHASE, "=imperium_row", targets=_IMPERIUM
    ),
    "acquire_manipulated_imperium": _spec(
        _V.ACQUIRE, _S.PURCHASE, "=set_aside", targets=_IMPERIUM
    ),
    "acquire_reserve": _spec(_V.ACQUIRE, _S.PURCHASE, "=reserve", targets=_RESERVE),
    # The Tleilaxu Row and Reclaimed Forces beside it; ``to_deck_top`` rides
    # on the card's row.
    "acquire_tleilaxu": _spec(
        _V.ACQUIRE,
        _S.PURCHASE,
        "=tleilaxu_row",
        targets=(("instance_id", _C.TLEILAXU_CARD),),
    ),
    "acquire_reclaimed_forces": _spec(
        _V.ACQUIRE, _S.PURCHASE, "=tleilaxu_row", targets=(("choice", _C.OPTION),)
    ),
    # --- A revealed card's choice: its card type by ``source``, or the one
    # card that prints an unsourced id (``reveal_turn.SOURCED_REVEAL_ACTION_IDS``)
    "place_reveal_spy": _spec(_V.PLACE_SPY, _S.REVEAL_CARD, "source", targets=_POST),
    "recall_spy_for_reveal_placement": _spec(
        _V.RECALL_SPY, _S.REVEAL_CARD, "source", targets=_POST
    ),
    "gain_two_reveal_strength": _spec(_V.GAIN, _S.REVEAL_CARD, "=undercover_asset"),
    "recall_spy_for_reveal": _spec(
        _V.RECALL_SPY, _S.REVEAL_CARD, "source", targets=_POST
    ),
    "recall_spies_for_reveal": _spec(
        _V.RECALL_SPY,
        _S.REVEAL_CARD,
        "=in_high_places",
        targets=(("first_post_id", _C.POST), ("second_post_id", _C.POST)),
    ),
    "trash_reveal_card": _spec(_V.TRASH, _S.REVEAL_CARD, "source", targets=_CARD),
    "gain_reveal_influence": _spec(
        _V.GAIN_INFLUENCE, _S.REVEAL_CARD, "source", targets=_FACTION
    ),
    "exchange_reveal_influence": _spec(
        _V.EXCHANGE_INFLUENCE,
        _S.REVEAL_CARD,
        "=captured_mentat",
        targets=(
            ("lost_faction", _C.FACTION),
            ("gained_faction", _C.FACTION),
            _RECIPIENT,
        ),
    ),
    "pay_reveal_solari_for_vp": _spec(_V.PAY, _S.REVEAL_CARD, "=opulence"),
    "pay_reveal_spice_for_vp": _spec(_V.PAY, _S.REVEAL_CARD, "=guild_ambassador"),
    "pay_reveal_solari_for_troops": _spec(
        _V.PAY, _S.REVEAL_CARD, "=gurney_halleck_card"
    ),
    "pay_reveal_spice_influence": _spec(
        _V.PAY, _S.REVEAL_CARD, "=spacing_guild_s_favor", targets=_FACTION
    ),
    "lose_reveal_influence_for_vp": _spec(
        _V.LOSE_INFLUENCE,
        _S.REVEAL_CARD,
        "=for_humanity",
        targets=(*_FACTION, _RECIPIENT),
    ),
    # A unit mix (``commanders``, ``zones``) rides on the effect's row.
    "retreat_two_troops_for_reveal": _spec(_V.RETREAT, _S.REVEAL_CARD, "source"),
    "deploy_reveal_card_troop": _spec(_V.DEPLOY, _S.REVEAL_CARD, "source"),
    "retreat_reveal_card_troop": _spec(_V.RETREAT, _S.REVEAL_CARD, "source"),
    # The count the owner picks of Sardaukar Legion's deploy, Scout's and
    # Chani's retreat (original game).
    "deploy_reveal_card_troops": _spec(
        _V.DEPLOY, _S.REVEAL_CARD, "source", targets=(("count", _C.COUNT),)
    ),
    "retreat_reveal_card_troops": _spec(
        _V.RETREAT, _S.REVEAL_CARD, "source", targets=(("count", _C.COUNT),)
    ),
    "lose_reveal_troops_for_specimens": _spec(
        _V.LOSE_UNIT, _S.REVEAL_CARD, "=tleilaxu_surgeon"
    ),
    "gain_five_reveal_solari": _spec(_V.GAIN, _S.REVEAL_CARD, "=corrinth_city"),
    "take_high_council_from_reveal": _spec(
        _V.TAKE, _S.REVEAL_CARD, "=corrinth_city"
    ),
    "gain_reveal_persuasion": _spec(_V.GAIN, _S.REVEAL_CARD, "=delivery_logistics"),
    # Bene Gesserit Sister's "-OR-": two alternatives sharing a verb.
    "gain_two_reveal_persuasion": _spec(
        _V.GAIN, _S.REVEAL_CARD, "=bene_gesserit_sister", option="persuasion"
    ),
    "gain_two_reveal_swords": _spec(
        _V.GAIN, _S.REVEAL_CARD, "=bene_gesserit_sister", option="swords"
    ),
    "take_reveal_contract": _spec(_V.TAKE, _S.REVEAL_CARD, "=delivery_logistics"),
    "keep_contract_reveal_spice": _spec(_V.KEEP, _S.REVEAL_CARD, "source"),
    "trash_contract_reveal_for_vp": _spec(_V.TRASH, _S.REVEAL_CARD, "source"),
    "pay_reveal_water_for_sandworm": _spec(_V.PAY, _S.REVEAL_CARD, "=desert_power"),
    "command_acquire_row_card": _spec(
        _V.ACQUIRE, _S.REVEAL_CARD, "=engineered_miracle", targets=_IMPERIUM
    ),
    # --- The leader, a Commander's Skill and Tech tiles in the Reveal ------
    "retreat_leader_troop": _spec(_V.RETREAT, _S.LEADER, _LEADER, option="troop"),
    "retreat_leader_commander": _spec(
        _V.RETREAT, _S.LEADER, _LEADER, option="commander"
    ),
    "recall_spy_for_leader": _spec(_V.RECALL_SPY, _S.LEADER, _LEADER, targets=_POST),
    "trash_skill_for_strength": _spec(_V.TRASH, _S.COMMANDER, "skill_id"),
    # Forbidden Weapons: three swords for an Influence, or the tile trashed.
    "choose_tech_strength": _spec(
        _V.CHOOSE,
        _S.TECH,
        "=forbidden_weapons",
        option="strength",
        targets=(*_FACTION, _RECIPIENT),
    ),
    "choose_tech_trash": _spec(
        _V.CHOOSE, _S.TECH, "=forbidden_weapons", option="trash"
    ),
    "place_tech_spy": _spec(_V.PLACE_SPY, _S.TECH, "=panopticon"),
    # --- Playing a card (stage B3c-1): the window, the card, its option -----
    # One option still opens its step (OQ-111 (2)): an option is an effect
    # printed on the card.
    "play_intrigue": _spec(
        _V.PLAY,
        _S.INTRIGUE,
        Printed.INTRIGUE_WINDOW,
        targets=(("card_id", _C.INTRIGUE_CARD), ("option", _C.OPTION)),
    ),
    # Harvest Cells' Conflict-end trigger: the window fixes its option.
    "play_conflict_end_intrigue": _spec(
        _V.PLAY,
        _S.INTRIGUE,
        "=conflict_end",
        targets=(("card_id", _C.INTRIGUE_CARD),),
    ),
    # Litany Against Fear at the start of the turn.
    "play_turn_start_card": _spec(_V.PLAY, _S.TURN, "=turn_start", targets=_CARD),
    # The card to match, then the wild card that matches it.
    "match_endgame_wild_icon": _spec(
        _V.MATCH,
        _S.ENDGAME,
        "=wild_icon",
        targets=(
            ("matching_card_id", _C.CONFLICT_CARD),
            ("wild_card_id", _C.CONFLICT_CARD),
        ),
    ),
    # --- The turn frame's research and Planetologist rows (stage B3c-2a) ---
    # Each research bonus is printed on one research space alone.
    "choose_research_influence": _spec(
        _V.GAIN_INFLUENCE, _S.RESEARCH, "=c6r6", targets=_FACTION
    ),
    "trash_intrigue_for_research_bonus": _spec(
        _V.TRASH,
        _S.RESEARCH,
        "=c7r3",
        targets=(("card_id", _C.INTRIGUE_CARD),),
    ),
    "pay_research_bonus": _spec(_V.PAY, _S.RESEARCH, "=c8r6"),
    # One icon of a research space's pair, by the space that printed it: two
    # spaces waiting the same icon are two rows (stage B3e-1, decision 3).
    "resolve_research_icon": _spec(
        _RESEARCH_ICON_VERBS, _S.REF, Printed.NAMED, icon="arg:effect"
    ),
    # Arrakis Planetologist's Intrigue card for a replaced sandworm.
    "draw_planetologist_intrigue": _spec(
        _V.DRAW, _S.LEADER, _LEADER, icon="intrigue"
    ),
    # An optional trash waiting on the turn, by the entity that printed its
    # icon (stage B3c-2b), then the card.
    "trash_optional_card": _spec(_V.TRASH, _S.REF, Printed.NAMED, targets=_CARD),
    # --- Windows that offer several effects at once (stage B3d-1) ----------
    # One icon of a recipient's Conflict reward row (OQ-112).
    "resolve_combat_reward_icon": _spec(
        _COMBAT_ICON_VERBS, _S.CONFLICT, Printed.CONFLICT_CARD, icon="arg:effect"
    ),
    # One printed line of an Intrigue card played line by line (OQ-058).
    "use_intrigue_effect": _spec(
        _V.USE, _S.INTRIGUE, Printed.INTRIGUE_CARD, option="arg:section"
    ),
    # --- Beside a window's own effect, or an own effect with no target
    # (stage B3d-2a) ----------------------------------------------------------
    # Recalling a Spy first, the supply being empty [Main pp. 11, 20], beside
    # the Spy the window places.
    "recall_spy_for_acquisition": _spec(
        _V.RECALL_SPY, _S.ACQUISITION, Printed.ACQUIRED_CARD, targets=_POST
    ),
    "recall_spy_for_contract": _spec(
        _V.RECALL_SPY, _S.CONTRACT, Printed.CONTRACT, targets=_POST
    ),
    "recall_spy_for_combat_reward": _spec(
        _V.RECALL_SPY, _S.CONFLICT, Printed.CONFLICT_CARD, targets=_POST
    ),
    "recall_spy_for_placement": _spec(
        _V.RECALL_SPY, _S.REF, Printed.WINDOW, targets=_POST
    ),
    # In a Spy placement slot; in a Recall Spy slot it is the window's own.
    "recall_spy_for_intrigue": _spec(
        _V.RECALL_SPY, _S.INTRIGUE, Printed.INTRIGUE_CARD, targets=_POST
    ),
    # A controlled space's defending troop [Main p. 20].
    "deploy_control_defense": _spec(_V.DEPLOY, _S.BOARD_SPACE, _SPACE),
    # A Conflict reward's optional payment for its VP.
    "pay_combat_reward": _spec(_V.PAY, _S.CONFLICT, Printed.CONFLICT_CARD),
    # An Intrigue card's automatic rewards beside its choice (OQ-015), its
    # Shield Wall and its look at the deck's top card.
    "resolve_intrigue_rewards": _spec(
        _V.RESOLVE, _S.INTRIGUE, Printed.INTRIGUE_CARD
    ),
    "detonate_shield_wall": _spec(
        _V.DESTROY_SHIELD_WALL, _S.INTRIGUE, Printed.INTRIGUE_CARD
    ),
    "put_back_top_card": _spec(_V.KEEP, _S.INTRIGUE, Printed.INTRIGUE_CARD),
    "discard_top_card": _spec(_V.DISCARD, _S.INTRIGUE, Printed.INTRIGUE_CARD),
    "draw_top_card_for_solari": _spec(_V.DRAW, _S.INTRIGUE, Printed.INTRIGUE_CARD),
    "draw_top_card": _spec(_V.DRAW, _S.INTRIGUE, Printed.INTRIGUE_CARD),
    # Bindu Suspension: pass the turn after the draw, or keep playing it.
    "pass_turn_intrigue": _spec(_V.PASS, _S.INTRIGUE, Printed.INTRIGUE_CARD),
    "keep_turn_intrigue": _spec(
        _D, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.PASS
    ),
    "trash_top_card": _spec(_V.TRASH, _S.INTRIGUE, Printed.INTRIGUE_CARD),
    # Cost-free choices with nothing to act on (OQ-113 (C)).
    "skip_intrigue_top_card": _spec(
        _E, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.KEEP
    ),
    "skip_intrigue_set_aside": _spec(
        _E, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.SET_ASIDE
    ),
    "skip_intrigue_trash": _spec(_E, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.TRASH),
    # --- Arrakeen Scouts (stage B3d-2b) ---------------------------------------
    # A new High Council seat may join a subcommittee (docs/rules/
    # arrakeen-scouts.md 4): the Agent turn's or the Reveal's row (D-3), then
    # the subcommittee window's target.
    "choose_subcommittee": _spec(_V.JOIN, _S.SCOUTS, "=high_council"),
    # A mission's part: its way when it has several, else the mission's
    # plain way by its effect row (an own effect with no target).
    "scouts_join_mission": _spec(
        _V.JOIN, _S.SCOUTS, Printed.MISSION, targets=(("target", _C.MISSION),)
    ),
    # Specimens returned to the supply first: a Scouts recruit step's own
    # choice, by its count; beside a mission's part Immortality's free return
    # "at any time" (OQ-050), a side branch whose effect row names the mission
    # whose window offers it (stage B3d-4, D-1), then its count.
    "scouts_return_specimens": _spec(
        _V.RETURN_SPECIMEN, _S.SCOUTS, Printed.MISSION, targets=(("count", _C.COUNT),)
    ),
    # --- Refusals and empty confirmations (stage B3d-3, D-2) -------------------
    # ``decline`` and ``confirm_empty``, each naming the effect it answers: its
    # verb (``of``) and the place its own row names.
    # An Agent box's (a Signet Ring box's: the leader's).
    "decline_agent_card_acquisition": _spec(_D, _S.AGENT_CARD, _BOX, of=_V.ACQUIRE),
    "decline_agent_card_discard": _spec(_D, _S.AGENT_CARD, _BOX, of=_V.DISCARD),
    "decline_agent_card_intrigue_payment": _spec(
        _D, _S.AGENT_CARD, _BOX, of=_V.PAY
    ),
    "decline_agent_card_payment": _spec(_D, _S.AGENT_CARD, _BOX, of=_V.PAY),
    "decline_corrinth_city_payment": _spec(_D, _S.AGENT_CARD, _BOX, of=_V.PAY),
    "decline_agent_card_spy": _spec(_D, _S.AGENT_CARD, _BOX, of=_V.PLACE_SPY),
    "decline_agent_card_recall": _spec(_D, _S.AGENT_CARD, _BOX, of=_V.RECALL_AGENT),
    "decline_agent_card_trash": _spec(_D, _S.AGENT_CARD, _BOX, of=_V.TRASH),
    # The leader's.
    "decline_leader_signet_payment": _spec(_D, _S.LEADER, _LEADER, of=_V.PAY),
    "decline_leader_spy_placement": _spec(_D, _S.LEADER, _LEADER, of=_V.PLACE_SPY),
    "decline_leader_card_trash": _spec(_D, _S.LEADER, _LEADER, of=_V.TRASH),
    "resolve_leader_signet_without_option": _spec(
        _E, _S.LEADER, _LEADER, of=_V.CHOOSE
    ),
    # A visited space's, a controlled space's, Gather Intelligence's.
    "resolve_espionage_without_spy": _spec(
        _E, _S.BOARD_SPACE, _SPACE, icon="spy", of=_V.PLACE_SPY
    ),
    "resolve_imperial_privilege_without_recall": _spec(
        _E, _S.BOARD_SPACE, _SPACE, icon="imperial_privilege", of=_V.RECALL_AGENT
    ),
    "decline_control_defense": _spec(_D, _S.BOARD_SPACE, _SPACE, of=_V.DEPLOY),
    "decline_gather_intelligence": _spec(_D, _S.SPY, _SPACE, of=_V.RECALL_SPY),
    # A revealed card's.
    "decline_reveal_sandworm": _spec(
        _D, _S.REVEAL_CARD, "=desert_power", of=_V.PAY
    ),
    "decline_reveal_spy_recall": _spec(
        _D, _S.REVEAL_CARD, "source", of=_V.RECALL_SPY
    ),
    # An Intrigue card's slot, a Navigation card's option, the Conflict-end
    # window's play (no one card prints it: the window, as its play row).
    "decline_intrigue_tleilaxu": _spec(
        _D, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.ACQUIRE
    ),
    "skip_intrigue_acquisition": _spec(
        _E, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.ACQUIRE
    ),
    "keep_shield_wall": _spec(
        _D, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.DESTROY_SHIELD_WALL
    ),
    "resolve_intrigue_influence_without_faction": _spec(
        _E, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.GAIN_INFLUENCE
    ),
    "decline_intrigue_spy": _spec(
        _D, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.PLACE_SPY
    ),
    "decline_intrigue_trash": _spec(
        _D, _S.INTRIGUE, Printed.INTRIGUE_CARD, of=_V.TRASH
    ),
    "decline_navigation": _spec(_D, _S.LEADER, Printed.INTRIGUE_CARD, of=_V.PLAY),
    "decline_conflict_end_intrigue": _spec(
        _D, _S.INTRIGUE, "=conflict_end", of=_V.PLAY
    ),
    # A Conflict card's reward icon, read off its window.
    "decline_combat_reward": _spec(
        _D,
        _S.CONFLICT,
        Printed.CONFLICT_CARD,
        icon=_WINDOW_ICON,
        of=_COMBAT_ICON_VERBS,
    ),
    "decline_combat_reward_spy": _spec(
        _D,
        _S.CONFLICT,
        Printed.CONFLICT_CARD,
        icon=_WINDOW_ICON,
        of=_COMBAT_ICON_VERBS,
    ),
    "decline_combat_reward_trash": _spec(
        _D,
        _S.CONFLICT,
        Printed.CONFLICT_CARD,
        icon=_WINDOW_ICON,
        of=_COMBAT_ICON_VERBS,
    ),
    "resolve_combat_trash_without_card": _spec(
        _E,
        _S.CONFLICT,
        Printed.CONFLICT_CARD,
        icon=_WINDOW_ICON,
        of=_COMBAT_ICON_VERBS,
    ),
    "resolve_combat_influence_without_faction": _spec(
        _E,
        _S.CONFLICT,
        Printed.CONFLICT_CARD,
        icon=_WINDOW_ICON,
        of=_COMBAT_ICON_VERBS,
    ),
    # An acquired card's, a Contract's, the Spy placement window's.
    "decline_acquisition_spy": _spec(
        _D, _S.ACQUISITION, Printed.ACQUIRED_CARD, of=_V.PLACE_SPY
    ),
    "decline_contract_spy": _spec(
        _D, _S.CONTRACT, Printed.CONTRACT, of=_V.PLACE_SPY
    ),
    "resolve_contract_without_recall": _spec(
        _E, _S.CONTRACT, Printed.CONTRACT, of=_V.RECALL_AGENT
    ),
    "decline_spy_placement": _spec(_E, _S.REF, Printed.WINDOW, of=_V.PLACE_SPY),
    # The Contract market's (the market, as a Reveal purchase names its own):
    # its icons held for later, or lapsed in Combat.
    "hold_contract_icons": _spec(
        _E, _S.CONTRACT, "=contract_market", option="hold", of=_V.TAKE
    ),
    "resolve_contract_icons_without_contract": _spec(
        _E, _S.CONTRACT, "=contract_market", of=_V.TAKE
    ),
    # A research space's bonus.
    "decline_research_bonus": _spec(
        _D, _S.RESEARCH, Printed.RESEARCH_SPACE, of=_RESEARCH_BONUS_VERBS
    ),
    # A card's Acquire Tech, a Tech tile's acquire Influence.
    "decline_tech": _spec(_D, _S.REF, Printed.WINDOW, of=_V.ACQUIRE),
    "resolve_tech_influence_without_faction": _spec(
        _E, _S.TECH, Printed.TECH_PENDING, of=_V.GAIN_INFLUENCE
    ),
    # A Commander's Skill: Plasteel Blades', or the bank Commander's.
    "decline_skill": _spec(_D, _S.COMMANDER, Printed.SKILL_WINDOW, of=_V.CHOOSE),
    "resolve_commander_without_skill": _spec(
        _E, _S.COMMANDER, Printed.SKILL_WINDOW, of=_V.CHOOSE
    ),
    # An opponent's card that makes the seat discard a card (OQ-138), lose a
    # unit or move a Spy.
    "resolve_opponent_discard_without_card": _spec(
        _E, _S.REF, Printed.WINDOW, of=_V.DISCARD
    ),
    "resolve_unit_loss_without_unit": _spec(
        _E, _S.REF, Printed.WINDOW, of=_V.LOSE_UNIT
    ),
    "lose_moved_spy": _spec(_E, _S.REF, Printed.WINDOW, of=_V.MOVE_SPY),
    # An optional trash window's trash icon.
    "decline_optional_trash": _spec(_D, _S.REF, Printed.WINDOW, of=_V.TRASH),
    # Arrakeen Scouts: a subcommittee, a mission, a choice, a market card.
    "decline_subcommittee": _spec(_D, _S.SCOUTS, "=high_council", of=_V.JOIN),
    "scouts_decline_mission": _spec(_D, _S.SCOUTS, Printed.MISSION, of=_V.JOIN),
    "resolve_scouts_choice_without_option": _spec(
        _E, _S.SCOUTS, Printed.SCOUTS_ITEM, of=_V.CHOOSE
    ),
    # Political Equilibrium's confirm of losing nothing (OQ-131).
    "resolve_scouts_loss_without_influence": _spec(
        _E, _S.SCOUTS, "=political_equilibrium", of=_V.LOSE_INFLUENCE
    ),
    "scouts_decline_card": _spec(
        _D, _S.SCOUTS, Printed.SCOUTS_ITEM, of=_V.ACQUIRE
    ),
    # --- The turn frame's last rows named by their source (stage B3d-4, D-3)
    # A triggered draw waiting as its own step (OQ-106), by the entity that
    # earned it (``owed_origin_printer``): since stage B3e-1 one row per
    # entity, not per deck (decision 3).
    "draw_owed_intrigue": _spec(_V.DRAW, _S.REF, Printed.NAMED, icon="intrigue"),
    "draw_owed_card": _spec(_V.DRAW, _S.REF, Printed.NAMED, icon="cards"),
    # The Emperor track's Influence 4 Spy [Main p. 7]; its post is the Spy
    # placement window's target.
    "place_track_spy": _spec(_V.PLACE_SPY, _S.INFLUENCE_TRACK, "=emperor"),
    # Bloodlines' once-a-turn Commander recruit [Bloodlines p. 4]: no card
    # prints it, the Sardaukar Commander itself.
    "recruit_sardaukar_commander": _spec(
        _V.RECRUIT, _S.COMMANDER, "=sardaukar_commander"
    ),
    # --- The Reveal's gathered gains (stage B3e-1, E-1) -----------------------
    # A gain waiting on the Reveal (OQ-045) is its own effect row naming what
    # printed it (``reveal_gain_printer``: a revealed card, a Skill, a Tech
    # tile, the leader), a copy of the same card once (decision 3). A
    # resource bundle or a Faction is its printer's own, so the row does not
    # repeat it (``_PRINTER_IMPLIED``).
    "recruit_reveal_troops": _spec(_V.RECRUIT, _S.REF, Printed.NAMED, icon="troops"),
    "draw_reveal_intrigue": _spec(_V.DRAW, _S.REF, Printed.NAMED, icon="intrigue"),
    "generate_reveal_specimens": _spec(
        _V.GENERATE_SPECIMENS, _S.REF, Printed.NAMED, icon="specimen"
    ),
    "advance_reveal_tleilaxu": _spec(
        _V.ADVANCE, _S.REF, Printed.NAMED, icon="tleilaxu"
    ),
    "advance_reveal_research": _spec(
        _V.ADVANCE, _S.REF, Printed.NAMED, icon="research"
    ),
    "gain_reveal_resources": _spec(_V.GAIN, _S.REF, Printed.NAMED, icon="resources"),
    "gain_reveal_faction_influence": _spec(
        _V.GAIN_INFLUENCE, _S.REF, Printed.NAMED, icon="faction_influence"
    ),
})

_CONTRACT_TARGET = (("instance_id", _C.CONTRACT),)
_INTRIGUE_TARGET = (("card_id", _C.INTRIGUE_CARD),)
_UNIT = (("zone", _C.UNIT),)
_COUNT = (("count", _C.COUNT),)
# The window-only effects (stage B3d-2a, module docstring): the whole
# actions a window opened for one effect offers as its own, by the targets
# that stand for them; they are never effect rows.
TARGET_SPECS: Final[Mapping[str, tuple[tuple[str, Choose], ...]]] = MappingProxyType({
    # A Conflict's reward windows.
    "choose_combat_reward_influence": _FACTION,
    "choose_distinct_combat_reward_influence": _FACTION,
    "place_combat_reward_spy": _POST,
    "recall_spies_for_combat_reward": (
        ("first_post_id", _C.POST),
        ("second_post_id", _C.POST),
    ),
    "trash_combat_reward_card": _CARD,
    # A Contract's windows, the Contract market and Intrigue-revealed ones.
    "take_contract": _CONTRACT_TARGET,
    "take_trigger_contract": _CONTRACT_TARGET,
    "place_contract_spy": _POST,
    "recall_agent_for_contract": _RECALLED,
    "recall_conflict_agent_for_contract": _CONFLICT,
    "trash_intrigue_for_contract": _INTRIGUE_TARGET,
    # An acquired card's Spy, a Spy placement window, an opponent's Spy.
    "place_acquisition_spy": _POST,
    "place_spy_on_space": _POST,
    "move_spy": _POST,
    # An Intrigue card's choice slot.
    "place_intrigue_spy": _POST,
    # Its Faction, then who takes an Alliance token an Influence paid hands on.
    "choose_intrigue_faction": (*_FACTION, _RECIPIENT),
    "trash_intrigue_card": _CARD,
    "choose_intrigue_discard": _CARD,
    "deploy_intrigue_troops": _COUNT,
    "retreat_intrigue_troops": _COUNT,
    "lose_intrigue_troop": _UNIT,
    # Double Cross: the opponent whose troop in the Conflict is lost.
    "choose_opponent_troop_loss": (("player", _C.SEAT),),
    "acquire_intrigue_imperium": _IMPERIUM,
    "acquire_intrigue_reserve": _RESERVE,
    "manipulate_imperium_row": _IMPERIUM,
    "acquire_intrigue_tleilaxu": (("instance_id", _C.TLEILAXU_CARD),),
    "acquire_intrigue_reclaimed_forces": (("choice", _C.OPTION),),
    "give_intrigue_card": (("card_id", _C.INTRIGUE_CARD), ("player", _C.SEAT)),
    "trash_intrigue_hand_card": _INTRIGUE_TARGET,
    "flip_battle_card": (("card_id", _C.CONFLICT_CARD),),
    # A card's own windows: an opponent's discard, the graft partner, the
    # kept Intrigue card of two, Long Live the Fighters' draw and discard.
    "discard_opponent_card": _CARD,
    "choose_graft_partner": _CARD,
    "keep_peeked_intrigue": (("instance_id", _C.INTRIGUE_CARD),),
    "select_long_live_fighters_draw": _CARD,
    "select_long_live_fighters_discard": _CARD,
    # Holy War's unit an opponent loses.
    "lose_unit": _UNIT,
    # Setup: the leader draft, the Navigation cards, the Secret Project.
    "pick_leader": (("leader_id", _C.LEADER),),
    "place_navigation_card": (("card_id", _C.NAVIGATION_CARD),),
    "choose_secret_project": (("tech_id", _C.TECH),),
    # A Navigation card's option, a Commander's Skill, the research space.
    "play_navigation": (("option", _C.OPTION),),
    "choose_skill": (("skill_id", _C.SKILL),),
    "choose_research_space": (("space_id", _C.TRACK_SPACE),),
    # --- Arrakeen Scouts' windows (stage B3d-2b) ------------------------------
    # A Scouts line's choice step: one effect a step.
    "scouts_trash_card": _CARD,
    "scouts_discard": _CARD,
    "scouts_trash_intrigue": _INTRIGUE_TARGET,
    "scouts_recall_spy": _POST,
    "scouts_recall_agent": _RECALLED,
    "scouts_choose_faction": _FACTION,
    "scouts_lose_influence": _FACTION,
    "scouts_lose_influence_to": (*_FACTION, _RECIPIENT),
    # A troop or a Sardaukar Commander of the garrison (OQ-105).
    "scouts_lose_garrison_unit": (("=garrison", _C.UNIT),),
    # Friends Everywhere's Influence 4 bonus, a subcommittee, an event's or a
    # sale's option, a secret pick, a bid, a call, an auction's retreat, a
    # market card.
    "choose_four_bonus": _FACTION,
    "join_subcommittee": (("subcommittee_id", _C.SUBCOMMITTEE),),
    "scouts_choose_option": (("option", _C.OPTION),),
    "scouts_secret_pick": (("pick", _C.OPTION),),
    "scouts_bid": _COUNT,
    "scouts_call": _COUNT,
    "scouts_retreat": _COUNT,
    "scouts_take_card": (("slot", _C.OPTION),),
})
# A whole action's arguments its printer already decides (stage B3e-1): a
# Reveal gain's resource bundle or Faction is the printed entity's own, so
# its effect row names the entity alone.
_PRINTER_IMPLIED: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType({
    "gain_reveal_resources": ("solari", "spice", "water"),
    "gain_reveal_faction_influence": ("faction",),
})
# Effects of ``STEP_SPECS`` a window also offers as its own, there by their
# targets alone: a revealed card's Spy after a recall, a Tech tile bought, a
# research space's bonus, the trash of an optional trash window, a Recall
# Spy slot's recall, a Scouts mission's way, a Scouts recruit step's
# specimen return.
WINDOW_OWN: Final = frozenset({
    "acquire_tech",
    "choose_research_influence",
    "place_reveal_spy",
    "recall_spy_for_intrigue",
    "scouts_join_mission",
    "scouts_return_specimens",
    "trash_intrigue_for_research_bonus",
    "trash_optional_card",
})

# The frames whose waiting effects are offered effect first (module doc).
EFFECT_STEP_FRAMES: Final = frozenset({
    FrameKind.AGENT_EFFECTS,
    FrameKind.REVEAL,
    # Stage B3c-1.
    FrameKind.TURN,
    FrameKind.COMBAT_INTRIGUE,
    FrameKind.CONFLICT_END_TRIGGER,
    FrameKind.ENDGAME_INTRIGUE,
    # Stage B3d-1: the windows that offer several effects at once.
    FrameKind.COMBAT_REWARD_ICONS,
    FrameKind.CONTRACT_REWARD_ICONS,
    FrameKind.INTRIGUE_EFFECTS,
    FrameKind.LEADER_SIGNET,
})
# The windows opened for one effect (stage B3d-2a, module docstring): their
# whole actions are shown by steps, so no whole id of the tables above is
# offered as it is (since stage B3d-4, a mission's specimen return too).
TARGET_STEP_FRAMES: Final = frozenset({
    FrameKind.OPPONENT_CARD_DISCARD,
    FrameKind.ACQUISITION_SPY,
    FrameKind.REVEAL_CHOICE,
    FrameKind.CONTRACT_MARKET,
    FrameKind.CONTRACT_REWARD_SPY,
    FrameKind.CONTRACT_REWARD_RECALL,
    FrameKind.CONTRACT_INTRIGUE_TRASH,
    FrameKind.CONTROL_DEFENSE,
    FrameKind.COMBAT_REWARD_INFLUENCE,
    FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE,
    FrameKind.COMBAT_REWARD_OPTIONAL,
    FrameKind.COMBAT_REWARD_SPY_RECALL,
    FrameKind.COMBAT_REWARD_TRASH,
    FrameKind.COMBAT_REWARD_SPY,
    FrameKind.INTRIGUE_CHOICE,
    FrameKind.LEADER_DRAFT,
    FrameKind.SKILL_CHOICE,
    FrameKind.OPPONENT_SPY_MOVE,
    FrameKind.OPPONENT_UNIT_LOSS,
    FrameKind.SPY_PLACEMENT,
    FrameKind.INTRIGUE_TRIGGER_CONTRACT,
    FrameKind.OPTIONAL_TRASH,
    FrameKind.NAVIGATION_SETUP,
    FrameKind.NAVIGATION_CHOICE,
    FrameKind.TECH_ACQUISITION,
    FrameKind.TECH_SECRET_PROJECT,
    FrameKind.RESEARCH_ADVANCE,
    FrameKind.RESEARCH_BONUS,
    FrameKind.GRAFT_PARTNER,
    FrameKind.INTRIGUE_PEEK,
    FrameKind.LONG_LIVE_FIGHTERS,
    # Stage B3d-2b: Arrakeen Scouts.
    FrameKind.SCOUTS_FOUR_BONUS,
    FrameKind.SCOUTS_EFFECT,
    FrameKind.SCOUTS_SUBCOMMITTEE,
    FrameKind.SCOUTS_CHOICE,
    FrameKind.SCOUTS_MISSION,
    FrameKind.SCOUTS_SECRET,
    FrameKind.SCOUTS_BID,
    FrameKind.SCOUTS_RETREAT,
    FrameKind.SCOUTS_CALL,
    FrameKind.SCOUTS_MARKET,
})
# Two of those windows offer several effects at once in one of their modes
# (stage B3d-1), every effect then by its effect row: a research window
# ordering a pair's icons (its context key ``immortality._ICONS_KEY``; a
# bonus choice is one effect), a Tech window owing a tile's acquire icons
# (``acquire_effects_only``; an acquisition is one effect).
_RESEARCH_ICONS_KEY: Final = "research_icons"
_TECH_ICONS_KEY: Final = "acquire_effects_only"


def _card_type(instance_id: str) -> str:
    return personal_card_for_instance(instance_id).card.card_id


def _is_signet(instance_id: str) -> bool:
    card = personal_card_for_instance(instance_id)
    return getattr(card, "agent_effect", None) is PersonalCardAgentEffect.LEADER_SIGNET


def printed_from_state(
    state: GameState, whole: DomainAction
) -> tuple[Source, ActionValue] | None:
    """The source and entity that printed ``whole``'s effect when the state
    names it (``Printed``), or None when an argument does."""

    spec = STEP_SPECS[whole.action_id]
    rule = spec.printed
    if not isinstance(rule, Printed):
        return None
    if rule == Printed.BOX_CARD:
        if state.decision_stack[-1].kind == FrameKind.LEADER_SIGNET:
            # Servo-Receivers' Signet frame: its icons are the leader's
            # Signet ability, no Agent box's (B3d-1).
            return Source.LEADER, _leader_face(state, whole)
        box = dict(whole.arguments).get("box", 0)
        boxes = agent_box_cards(state)
        if not isinstance(box, int) or box >= len(boxes):
            raise ValueError(f"{whole} names an Agent box the turn does not have")
        card = boxes[box][0]
        if _is_signet(card):
            return Source.LEADER, _leader_face(state, whole)
        return spec.source, _card_type(card)
    if rule == Printed.VISITED_SPACE:
        frame = state.decision_stack[-1]
        space = dict(frame.context).get("space_id")
        if not isinstance(space, str):
            raise ValueError(f"{whole} has no visited space")
        return spec.source, space
    if rule == Printed.INTRIGUE_WINDOW:
        window = _INTRIGUE_WINDOWS.get(state.decision_stack[-1].kind)
        if window is None:
            raise ValueError(f"{whole} has no Intrigue window")
        return spec.source, window
    if rule == Printed.RESEARCH_SPACE:
        return spec.source, _research_space(state, whole)
    if rule == Printed.NAMED:
        arguments = dict(whole.arguments)
        return Source(str(arguments["source"])), arguments["printed"]
    if rule == Printed.CONFLICT_CARD:
        if not state.current_conflict_ids:
            raise ValueError(f"{whole} has no Conflict card")
        return spec.source, state.current_conflict_ids[-1]
    if rule == Printed.CONTRACT:
        named: object = dict(whole.arguments).get("contract_id")
        if named is None:
            opened = dict(state.decision_stack[-1].context)
            named = opened.get("contract_id", opened.get("contract_spy_id"))
        if not isinstance(named, str):
            raise ValueError(f"{whole} has no Contract")
        return spec.source, named
    if rule == Printed.INTRIGUE_CARD:
        played: object = dict(state.decision_stack[-1].context).get("card_id")
        if not isinstance(played, str):
            raise ValueError(f"{whole} has no Intrigue card")
        return spec.source, intrigue_card_for_instance(played).card.card_id
    if rule == Printed.ACQUIRED_CARD:
        acquired = dict(state.decision_stack[-1].context).get("acquisition_card_id")
        if not isinstance(acquired, str):
            raise ValueError(f"{whole} has no acquired card")
        return spec.source, _card_type(acquired)
    if rule == Printed.WINDOW:
        printer = dict(state.decision_stack[-1].context).get(PRINTER_KEY)
        if not isinstance(printer, str):
            raise ValueError(f"{whole}'s window records no printer")
        opener, entity, _box = printer_parts(printer)
        return opener, entity
    if rule == Printed.MISSION:
        mission = dict(state.decision_stack[-1].context).get("mission_id")
        if not isinstance(mission, str):
            raise ValueError(f"{whole} has no mission")
        return spec.source, mission
    if rule == Printed.SCOUTS_ITEM:
        item = dict(state.decision_stack[-1].context).get("item")
        if not isinstance(item, str):
            raise ValueError(f"{whole} has no Scouts item")
        return spec.source, item
    if rule == Printed.SKILL_WINDOW:
        giver: object = dict(state.decision_stack[-1].context).get("card_id")
        if not isinstance(giver, str):
            raise ValueError(f"{whole} has no Skill source")
        if giver.startswith(_TECH_PREFIX):
            return Source.TECH, giver.removeprefix(_TECH_PREFIX)
        return spec.source, _card_type(giver)
    if rule == Printed.TECH_PENDING:
        pending = dict(state.decision_stack[-1].context).get(_TECH_PENDING_KEY, "")
        assert isinstance(pending, str)
        tiles = [
            entry.split(":")[0]
            for entry in pending.split(",")
            if entry.endswith(":influence")
        ]
        if not tiles:
            raise ValueError(f"{whole} has no Tech tile's Influence waiting")
        return spec.source, tiles[0]
    return spec.source, _leader_face(state, whole)


# Plasteel Blades' tile names its Skill window (``sardaukar``); a Tech window
# keeps its tiles' owed acquire icons (``frames.TECH_ACQUIRE_PENDING_KEY``).
_TECH_PREFIX: Final = "tech:"
_TECH_PENDING_KEY: Final = "pending_tech_acquire_effects"
# A Conflict reward's window by the icon whose choice it opens
# (``combat.apply_combat_reward_icon``).
_REWARD_WINDOW_ICONS: Final[Mapping[str, str]] = MappingProxyType({
    FrameKind.COMBAT_REWARD_INFLUENCE: "choose_influence",
    FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE: "distinct_influence",
    FrameKind.COMBAT_REWARD_SPY_RECALL: "optional_recall_spies",
    FrameKind.COMBAT_REWARD_TRASH: "trash",
})


# The deck of each owed draw row (``frames.OWED_INTRIGUE``, ``OWED_CARD``).
# What earned an owed draw, by its origin (``frames.hold_draw``): a research
# space's bonus, an Influence track's 4, a Tech tile; Imperial Birthright
# and Hungry for Spice are the seat's leader's.
_OWED_ORIGINS: Final[Mapping[str, tuple[Source, str]]] = MappingProxyType({
    "research_c7r3": (Source.RESEARCH, "c7r3"),
    "bene_gesserit_4": (Source.INFLUENCE_TRACK, "bene_gesserit"),
    "choam_transports": (Source.TECH, "choam_transports"),
})
_LEADER_ORIGINS: Final = frozenset(
    {
        "imperial_birthright",
        "hungry_for_spice",
        # The original game's Count Ilban Richese and Countess Ariana
        # Thorvald (docs/rules/imperium-base.md 12).
        "ruthless_negotiator",
        "spice_addict",
    }
)
# An acquired card's acquire box, and a card's "when trashed" (by its type).
_ACQUIRE_ORIGIN: Final = "acquire:"
_TRASH_ORIGIN: Final = "card:"
# The Tleilaxu track's Intrigue space, which no other kind of source names.
_TLEILAXU_ORIGIN: Final = "tleilaxu_track"


def owed_origin_printer(
    state: GameState, player: int, origin: str
) -> tuple[Source, str]:
    """The source and entity that earned an owed draw of ``origin`` (its
    ``PlayerState.owed_draws`` origin; stage B3d-4, one row each since
    B3e-1). An origin with no kind of its own -- the Tleilaxu track's space,
    a card's "when trashed" -- names the trigger (``Source.TRIGGER``)."""

    if origin in _OWED_ORIGINS:
        return _OWED_ORIGINS[origin]
    if origin in _LEADER_ORIGINS:
        return Source.LEADER, _seat_leader_face(state, player)
    if origin.startswith(_ACQUIRE_ORIGIN):
        return Source.ACQUISITION, _card_type(origin.removeprefix(_ACQUIRE_ORIGIN))
    if origin.startswith(_TRASH_ORIGIN):
        return Source.TRIGGER, _card_type(origin.removeprefix(_TRASH_ORIGIN))
    if origin == _TLEILAXU_ORIGIN:
        return Source.TRIGGER, origin
    raise ValueError(f"an owed draw has an unknown origin {origin!r}")


# A Reveal gain's source (``reveal_turn.reveal_pending_gains``) that is no
# revealed card: a Skill (``skill:<id>``), a Tech tile (``tech:<id>``), a
# leader's Reveal ability (``leader_reveal:<ability>``).
_SKILL_GAIN: Final = "skill:"
_TECH_GAIN: Final = "tech:"
_LEADER_GAIN: Final = "leader_reveal:"


def reveal_gain_printer(
    state: GameState, player: int, source: str
) -> tuple[Source, str]:
    """The source and entity that printed a Reveal gain waiting with
    ``source`` (stage B3e-1): a revealed card by its type, a Skill (its
    Commander's, ``Source.COMMANDER``), a Tech tile, the seat's leader."""

    if source.startswith(_SKILL_GAIN):
        return Source.COMMANDER, source.removeprefix(_SKILL_GAIN)
    if source.startswith(_TECH_GAIN):
        return Source.TECH, source.removeprefix(_TECH_GAIN)
    if source.startswith(_LEADER_GAIN):
        return Source.LEADER, _seat_leader_face(state, player)
    return Source.REVEAL_CARD, _card_type(source)


def research_icon_printer(source: str) -> tuple[Source, str]:
    """The research space whose icon waits with ``source`` (it ends
    ``:research:<space>``; stage B3e-1)."""

    if ":research:" not in source:
        raise ValueError(f"{source!r} names no research space")
    return Source.RESEARCH, source.rsplit(":", 1)[1]


def named_whole(
    action_id: str,
    player: int,
    printer: tuple[Source, str],
    *arguments: tuple[str, ActionValue],
) -> DomainAction:
    """A ``Printed.NAMED`` whole action naming ``printer`` (stage B3e-1)."""

    source, printed = printer
    return DomainAction(
        action_id,
        player,
        tuple(sorted((*arguments, ("printed", printed), ("source", source.value)))),
    )


def whole_printer(whole: DomainAction) -> tuple[Source, str] | None:
    """The printer a ``Printed.NAMED`` whole action names, if it names one."""

    arguments = dict(whole.arguments)
    source, printed = arguments.get("source"), arguments.get("printed")
    if not isinstance(source, str) or not isinstance(printed, str):
        return None
    return Source(source), printed


def window_icon(state: GameState) -> str:
    """The Conflict reward icon whose window is on top (``"window"`` icons):
    its payment's resource, its Spy's Deep Cover, else the window's own."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if frame.kind == FrameKind.COMBAT_REWARD_OPTIONAL:
        return f"optional_{context['resource']}"
    if frame.kind == FrameKind.COMBAT_REWARD_SPY:
        return "deep_cover_spy" if context.get("deep_cover") is True else "spy"
    icon = _REWARD_WINDOW_ICONS.get(frame.kind)
    if icon is None:
        raise ValueError(f"{frame.kind} is no Conflict reward window")
    return icon


def _research_space(state: GameState, whole: DomainAction) -> str:
    """The research space whose bonus window is on top
    (``Printed.RESEARCH_SPACE``): its source ends ``:research:<space>``."""

    frame = state.decision_stack[-1]
    source = dict(frame.context).get("source")
    if frame.kind != FrameKind.RESEARCH_BONUS or not isinstance(source, str):
        raise ValueError(f"{whole} has no research bonus window")
    return research_icon_printer(source)[1]


# The Intrigue window each frame that offers a play opens (``intrigue_window``).
_INTRIGUE_WINDOWS: Final[Mapping[str, str]] = MappingProxyType({
    FrameKind.TURN: "plot",
    FrameKind.AGENT_EFFECTS: "plot",
    FrameKind.REVEAL: "plot",
    FrameKind.COMBAT_INTRIGUE: "combat",
    # The sole winner's reward window: a winning Intrigue is played there
    # (``intrigue.intrigue_window``).
    FrameKind.COMBAT_REWARD_ICONS: "combat",
    FrameKind.ENDGAME_INTRIGUE: "endgame",
})
INTRIGUE_WINDOWS: Final = tuple(dict.fromkeys(_INTRIGUE_WINDOWS.values()))


def _leader_face(state: GameState, whole: DomainAction) -> str:
    return _seat_leader_face(state, whole.actor)


def _seat_leader_face(state: GameState, player: int) -> str:
    owner = state.players[player]
    leader = owner.leader_face_id or owner.leader_id
    if not leader:
        raise ValueError(f"seat {player} has no leader")
    return leader


def path_of(state: GameState, whole: DomainAction) -> tuple[DomainAction, ...] | None:
    """The steps that stand for ``whole`` in ``state`` (without a pick), or
    None when ``whole`` is offered as it is."""

    if _offers_one_effect(state):
        if whole.action_id in TARGET_SPECS and _own_effect(state, whole):
            return steps_for(whole, effect_row=False)
        if whole.action_id in WINDOW_OWN and _own_effect(state, whole):
            # Its target rows, or with none the effect row as below.
            targets = steps_for(whole, effect_row=False)
            if targets:
                return targets
    spec = STEP_SPECS.get(whole.action_id)
    if spec is None or (
        (spec.printed == Printed.NAMED or not isinstance(spec.printed, Printed))
        and not spec.printed.startswith(_FIXED)
        and _printed_argument(spec) not in dict(whole.arguments)
    ):
        # Not shown as steps (an optional trash window's row names no
        # printer).
        return None
    icon = window_icon(state) if spec.icon == _WINDOW_ICON else None
    named = printed_from_state(state, whole)
    if named is None:
        return steps_for(whole, icon=icon)
    return steps_for(whole, named[1], named[0], icon=icon)


def _printed_argument(spec: StepSpec) -> str:
    """The whole action's argument naming its printed entity."""

    return "printed" if spec.printed == Printed.NAMED else spec.printed


def _offers_one_effect(state: GameState) -> bool:
    """Whether the top frame is a window opened for one effect, in the mode
    that offers it (``TARGET_STEP_FRAMES``)."""

    frame = state.decision_stack[-1]
    if frame.kind not in TARGET_STEP_FRAMES:
        return False
    if frame.kind == FrameKind.RESEARCH_BONUS:
        return not dict(frame.context).get(_RESEARCH_ICONS_KEY)
    if frame.kind == FrameKind.TECH_ACQUISITION:
        return dict(frame.context).get(_TECH_ICONS_KEY) is not True
    return True


def _own_effect(state: GameState, whole: DomainAction) -> bool:
    """Whether ``whole`` is its window's own effect: an Intrigue card's
    recall is beside a Spy placement slot's Spy, and the effect of a Recall
    Spy slot; a Scouts specimen return is a recruit step's own, and a side
    branch beside a mission's part."""

    if whole.action_id == "scouts_return_specimens":
        return state.decision_stack[-1].kind != FrameKind.SCOUTS_MISSION
    if whole.action_id != "recall_spy_for_intrigue":
        return True
    # The Intrigue rules build on this module's callers.
    from dune_imperium.rules.intrigue import current_intrigue_choice_slot

    return isinstance(current_intrigue_choice_slot(state, whole.actor), RecallSpy)


def steps_for(
    whole: DomainAction,
    printed: ActionValue | None = None,
    source: Source | None = None,
    *,
    effect_row: bool = True,
    icon: str | None = None,
) -> tuple[DomainAction, ...]:
    """``whole``'s steps; its printed entity (and the source, when a Signet
    Ring box names the leader) given when the state names them
    (``printed_from_state``). Without ``effect_row``, the target rows alone
    that stand for a window's own effect (module docstring), none when the
    whole action names no target. ``icon`` is a ``"window"`` icon's
    (``window_icon``). The action codec builds its rows by this."""

    targets = TARGET_SPECS.get(whole.action_id)
    if targets is not None:
        rows = _target_rows(whole.actor, dict(whole.arguments), targets)
        if not rows:
            raise ValueError(f"{whole} names none of its targets")
        return rows
    spec = STEP_SPECS[whole.action_id]
    arguments = dict(whole.arguments)
    box = arguments.pop("box", 0)
    if spec.printed == Printed.NAMED:
        # The source and printed entity are the ref's (given here, else the
        # whole action's own), and so is a grafted turn's second card
        # (``printed_box``).
        named_source = arguments.pop("source", None)
        named_printed = arguments.pop("printed", None)
        if printed is None and isinstance(named_source, str):
            printed, source = named_printed, Source(named_source)
        box = arguments.pop("printed_box", box)
        for implied in _PRINTER_IMPLIED.get(whole.action_id, ()):
            arguments.pop(implied, None)
    elif spec.printed == Printed.CONTRACT:
        arguments.pop("contract_id", None)
    elif not isinstance(spec.printed, Printed):
        printed = (
            spec.printed.removeprefix(_FIXED)
            if spec.printed.startswith(_FIXED)
            else arguments.pop(spec.printed, None)
        )
    shown: ActionValue | None = None
    if spec.icon == _WINDOW_ICON:
        if icon is None:
            raise ValueError(f"{whole} needs its window's icon")
        shown = icon
    elif spec.icon.startswith(_ARG):
        shown = arguments.pop(spec.icon.removeprefix(_ARG), None)
    elif spec.icon:
        shown = spec.icon
    option: ActionValue | None = None
    if spec.option.startswith(_ARG):
        option = arguments.pop(spec.option.removeprefix(_ARG), None)
    elif spec.option:
        option = spec.option
    if not effect_row:
        return _target_rows(whole.actor, arguments, spec.targets)
    if printed is None:
        raise ValueError(f"{whole} needs its printed entity")
    if isinstance(spec.verb, Verb):
        verb = spec.verb
    else:
        key = "" if shown is None else shown
        if not isinstance(key, str) or key not in spec.verb:
            raise ValueError(f"{whole} has no verb for its icon")
        verb = spec.verb[key]
    ref: list[tuple[str, ActionValue]] = [
        ("printed", printed),
        ("source", (source or spec.source).value),
    ]
    if shown is not None:
        ref.append(("icon", shown))
    if spec.of is not None:
        ref.append(("of", _refused(whole, spec.of, shown, printed).value))
    if option is not None:
        ref.append(("option", option))
    if box:
        ref.append(("box", box))
    rows = _target_rows(whole.actor, arguments, spec.targets)
    if not rows:
        carried = _carried(arguments)
        return (_action(verb.value, whole.actor, [*ref, *carried]),)
    return (_action(verb.value, whole.actor, ref), *rows)


def _refused(
    whole: DomainAction,
    of: Verb | Mapping[str, Verb],
    icon: ActionValue | None,
    printed: ActionValue,
) -> Verb:
    """The verb of the effect a refusal or an empty confirmation answers:
    ``of``, or its entry for the row's icon (else its printed entity)."""

    if isinstance(of, Verb):
        return of
    key = icon if icon is not None else printed
    if not isinstance(key, str) or key not in of:
        raise ValueError(f"{whole} answers no effect of {key!r}")
    return of[key]


def _target_rows(
    actor: int,
    arguments: dict[str, ActionValue],
    targets: tuple[tuple[str, Choose], ...],
) -> tuple[DomainAction, ...]:
    """One target row per target the whole action names (``StepSpec``), the
    last carrying its other arguments (a unit mix); none when it names no
    target. Takes the targets out of ``arguments``."""

    picked: list[tuple[Choose, ActionValue]] = []
    for name, kind in targets:
        if name.startswith(_FIXED):
            picked.append((kind, name.removeprefix(_FIXED)))
            continue
        value = arguments.pop(name, None)
        if value is not None and value != "":
            picked.append((kind, value))
    carried = _carried(arguments)
    rows: list[DomainAction] = []
    for index, (kind, value) in enumerate(picked):
        row_arguments = [(CHOOSE_ARGUMENT[kind], value)]
        if index == len(picked) - 1:
            row_arguments.extend(carried)
        rows.append(_action(kind.action_id, actor, row_arguments))
    return tuple(rows)


def _carried(arguments: Mapping[str, ActionValue]) -> list[tuple[str, ActionValue]]:
    return [(name, value) for name, value in arguments.items() if value != ""]


def _action(
    action_id: str, actor: int, arguments: list[tuple[str, ActionValue]]
) -> DomainAction:
    return DomainAction(action_id, actor, tuple(sorted(arguments)))


def presents_steps(state: GameState) -> bool:
    """Whether the top frame offers its waiting effects effect first, or
    a window's own effect by its targets."""

    if not state.decision_stack:
        return False
    kind = state.decision_stack[-1].kind
    return kind in EFFECT_STEP_FRAMES or kind in TARGET_STEP_FRAMES


def picked_rows(state: GameState) -> tuple[DomainAction, ...]:
    """The rows the top frame's owner picked toward one effect so far."""

    if not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision):
        return ()
    encoded = dict(frame.context).get(EFFECT_PICK_KEY)
    if not isinstance(encoded, str):
        return ()
    return tuple(
        DomainAction(action_id, frame.decision.owner, arguments)
        for action_id, arguments in decode_pick(encoded)
    )


def decode_pick(encoded: str) -> tuple[Row, ...]:
    """The rows an ``EFFECT_PICK_KEY`` value holds."""

    rows: list[Row] = []
    for action_id, arguments in json.loads(encoded):
        rows.append((action_id, _arguments(arguments)))
    return tuple(rows)


def _arguments(arguments: object) -> Arguments:
    assert isinstance(arguments, list)
    pairs: list[tuple[str, ActionValue]] = []
    for name, value in arguments:
        assert isinstance(name, str) and isinstance(value, bool | int | str)
        pairs.append((name, value))
    return tuple(pairs)


def _encode_pick(rows: tuple[DomainAction, ...]) -> str:
    return json.dumps(
        [[row.action_id, [list(item) for item in row.arguments]] for row in rows],
        separators=(",", ":"),
    )


def without_pick(state: GameState) -> GameState:
    """``state`` with the top frame's pick dropped (the rules' own state)."""

    if not picked_rows(state):
        return state
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    del context[EFFECT_PICK_KEY]
    return replace_top_frame(state, with_context(frame, context))


def _paths(
    state: GameState, wholes: tuple[DomainAction, ...]
) -> list[tuple[DomainAction, tuple[DomainAction, ...] | None]]:
    return [(whole, path_of(state, whole)) for whole in wholes]


def present(
    state: GameState, wholes: tuple[DomainAction, ...]
) -> tuple[DomainAction, ...]:
    """The rows offered for ``wholes`` (the rules' list for ``state`` without
    its pick): every whole action shown by its next step, in the rules'
    order; during a pick only the picked effect's next rows."""

    if not presents_steps(state):
        return wholes
    pick = picked_rows(state)
    rules_state = without_pick(state)
    rows: dict[DomainAction, None] = {}
    ends: dict[tuple[DomainAction, ...], DomainAction] = {}
    for whole, path in _paths(rules_state, wholes):
        if path is None:
            if not pick:
                rows.setdefault(whole, None)
            continue
        if path[: len(pick)] != pick or len(path) == len(pick):
            continue
        other = ends.setdefault(path, whole)
        if other != whole:
            raise RuntimeError(f"{whole} and {other} share the steps {path}")
        rows.setdefault(path[len(pick)], None)
    _check_prefixes(ends)
    return tuple(rows)


def _check_prefixes(ends: Mapping[tuple[DomainAction, ...], DomainAction]) -> None:
    """A path that ends where another goes on would leave its step two
    meanings; the table must tell them apart."""

    for path, whole in ends.items():
        for cut in range(1, len(path)):
            other = ends.get(path[:cut])
            if other is not None:
                raise RuntimeError(f"{other} ends where {whole} goes on")


def whole_actions(
    state: GameState, wholes: tuple[DomainAction, ...]
) -> tuple[DomainAction, ...]:
    """The whole actions still open in ``state``: all of them, or during a
    pick those whose path begins with it."""

    pick = picked_rows(state)
    if not pick or not presents_steps(state):
        return wholes
    rules_state = without_pick(state)
    return tuple(
        whole
        for whole, path in _paths(rules_state, wholes)
        if path is not None and path[: len(pick)] == pick
    )


@dataclass(frozen=True, slots=True)
class Step:
    """What a legal row does: keeps a longer pick (``state`` with it, and
    ``event``), or applies ``whole`` to ``state`` (the rules' state)."""

    state: GameState
    whole: DomainAction | None = None
    event: GameEvent | None = None


def take_step(
    state: GameState, row: DomainAction, wholes: tuple[DomainAction, ...]
) -> Step:
    """Apply a legal ``row`` of ``present(state, wholes)``."""

    if not presents_steps(state):
        return Step(state=state, whole=row)
    pick = picked_rows(state)
    rules_state = without_pick(state)
    prefix = (*pick, row)
    matches = [
        (whole, path)
        for whole, path in _paths(rules_state, wholes)
        if path is not None and path[: len(prefix)] == prefix
    ]
    if not matches:
        # Only an action the frame offers as it is may come whole: one with
        # steps never skips them, whoever hands the engine its legal set.
        if pick or row not in wholes or path_of(rules_state, row) is not None:
            raise ValueError(f"{row} is no step of an offered action")
        return Step(state=state, whole=row)
    ended = [whole for whole, path in matches if len(path) == len(prefix)]
    if ended:
        (whole,) = ended
        return Step(state=rules_state, whole=whole)
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context[EFFECT_PICK_KEY] = _encode_pick(prefix)
    player = row.actor
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:effect_pick:{len(prefix)}"
        ),
        kind="effect_picked",
        payload=(
            ("action_id", row.action_id),
            ("arguments", json.dumps([list(item) for item in row.arguments])),
            ("player", player),
        ),
        visible_to=(player,),
    )
    return Step(
        state=replace_top_frame(state, with_context(frame, context)), event=event
    )


def first_step(state: GameState, whole: DomainAction) -> DomainAction:
    """The row to take now toward ``whole`` (one of ``whole_actions``)."""

    if not presents_steps(state):
        return whole
    path = path_of(without_pick(state), whole)
    if path is None:
        return whole
    pick = picked_rows(state)
    if path[: len(pick)] != pick or len(path) <= len(pick):
        raise ValueError(f"{whole} is not the effect picked toward")
    return path[len(pick)]


def completed_whole(
    state: GameState, row: DomainAction, wholes: tuple[DomainAction, ...]
) -> DomainAction | None:
    """The whole action that the legal ``row`` ends in ``state``: None when
    the frame shows no steps, ``row`` is offered as it is, or it only picks
    toward an effect. ``wholes`` are the rules' actions for ``state``
    without its pick (``whole_actions`` gives those of the pick)."""

    if not presents_steps(state):
        return None
    pick = picked_rows(state)
    rules_state = without_pick(state)
    for whole, path in _paths(rules_state, wholes):
        if (
            path is not None
            and len(path) == len(pick) + 1
            and path[: len(pick)] == pick
            and path[-1] == row
        ):
            return whole
    return None
