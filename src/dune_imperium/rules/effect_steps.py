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
B3c-1) offers
the effect rows; an effect without a target is resolved by its row, and one
with targets keeps the rows picked so far in the frame's context
(``EFFECT_PICK_KEY``) and offers only the next rows of its paths -- even when
there is one target (OQ-111 (2)). The context is no other seat's to see
(B3-3 (가), OQ-111 (4)); the seat's own view reads it
(``core.observation.effect_pick_of``). When a path ends, its whole action is
applied to the state without the pick, so the rules never see the steps.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import EFFECT_PICK_KEY, agent_box_cards
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.action_shapes import Source, Verb
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
    # The research space whose icon waits (stage B3c-2a): a research
    # window's own space, or on the turn frame the newest waiting icon of
    # the whole action's kind -- the one ``apply_research_icon`` takes.
    RESEARCH_SPACE = "research_space"


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
    Tabr's water or supplies), as the effect row's ``option``. ``targets``
    are the whole action's target arguments in the order they are picked,
    ``"=<value>"`` for a target the whole action's id itself names (the
    Conflict of a recall); an argument the whole action does not carry, or
    carries empty, is no step of it.
    """

    verb: Verb | Mapping[str, Verb]
    source: Source
    printed: Printed | str
    icon: str = ""
    option: str = ""
    targets: tuple[tuple[str, Choose], ...] = ()


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
) -> StepSpec:
    return StepSpec(verb, source, printed, icon, option, targets)


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
    "high_council": _V.TAKE,
    "intrigue": _V.DRAW,
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
    # An icon of a Contract completed in the owner's turn, waiting on it
    # (OQ-112 (4)); its window's rows name no Contract and stay as they are.
    "resolve_contract_reward_icon": _spec(
        _CONTRACT_ICON_VERBS, _S.CONTRACT, "contract_id", icon="arg:effect"
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
    "lose_reveal_troops_for_specimens": _spec(
        _V.LOSE_UNIT, _S.REVEAL_CARD, "=tleilaxu_surgeon"
    ),
    "gain_five_reveal_solari": _spec(_V.GAIN, _S.REVEAL_CARD, "=corrinth_city"),
    "take_high_council_from_reveal": _spec(
        _V.TAKE, _S.REVEAL_CARD, "=corrinth_city"
    ),
    "gain_reveal_persuasion": _spec(_V.GAIN, _S.REVEAL_CARD, "=delivery_logistics"),
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
    # One icon of a research space's pair; two spaces waiting the same icon
    # resolve alike, so one row (decision 3), the newest first as before.
    "resolve_research_icon": _spec(
        _RESEARCH_ICON_VERBS, _S.RESEARCH, Printed.RESEARCH_SPACE, icon="arg:effect"
    ),
    # Arrakis Planetologist's Intrigue card for a replaced sandworm.
    "draw_planetologist_intrigue": _spec(
        _V.DRAW, _S.LEADER, _LEADER, icon="intrigue"
    ),
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
})
# Whole ids of ``STEP_SPECS`` a frame outside ``EFFECT_STEP_FRAMES`` still
# offers as they are (the Tech acquisition window, Servo-Receivers' Signet
# frame, a Contract's reward window, a revealed card's own choice frame, a
# research window outside the turn, the Planetologist's window -- stage B3d
# gives those target rows); every other whole id of the table is offered
# only as steps, so the action catalog drops it.
OFFERED_AS_WHOLE: Final = frozenset({
    "acquire_leader_imperium",
    "acquire_leader_reserve",
    "acquire_tech",
    "advance_feyd_track",
    "choose_leader_signet_influence",
    "choose_research_influence",
    "command_acquire_row_card",
    "deploy_leader_agent",
    "deploy_reveal_card_troop",
    "draw_planetologist_intrigue",
    "exchange_reveal_influence",
    "gain_five_reveal_solari",
    "gain_leader_signet_spice",
    "gain_leader_signet_troop",
    "gain_reveal_influence",
    "gain_reveal_persuasion",
    "gain_two_reveal_strength",
    "keep_contract_reveal_spice",
    "lose_reveal_influence_for_vp",
    "lose_reveal_troops_for_specimens",
    "pay_leader_signet_solari",
    "pay_leader_signet_spice",
    "pay_leader_signet_water",
    "pay_research_bonus",
    "pay_reveal_spice_influence",
    "pay_reveal_water_for_sandworm",
    "place_leader_bonus_spice",
    "place_leader_spy",
    "place_reveal_spy",
    "recall_spies_for_reveal",
    "recall_spy_for_leader_placement",
    "recall_spy_for_reveal",
    "recall_spy_for_reveal_placement",
    "resolve_agent_card_effect",
    "resolve_contract_reward_icon",
    "resolve_research_icon",
    "resolve_tech_acquire_effect",
    "retreat_leader_troops",
    "retreat_reveal_card_troop",
    "retreat_two_troops_for_reveal",
    "take_high_council_from_reveal",
    "take_leader_bonus_spice",
    "take_reveal_contract",
    "trash_contract_reveal_for_vp",
    "trash_intrigue_for_research_bonus",
    "trash_leader_card",
    "trash_leader_tech",
    "trash_reveal_card",
})


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
    return spec.source, _leader_face(state, whole)


def _research_space(state: GameState, whole: DomainAction) -> str:
    """The research space whose waiting icon ``whole`` resolves
    (``Printed.RESEARCH_SPACE``): its source ends ``:research:<space>``."""

    frame = state.decision_stack[-1]
    source: object = None
    if frame.kind == FrameKind.RESEARCH_BONUS:
        source = dict(frame.context).get("source")
    else:
        icon = dict(whole.arguments).get("effect")
        source = next(
            (
                item[1]
                for item in reversed(turn_rows.pending(frame))
                if item[0] == turn_rows.RESEARCH_ICON and item[2] == icon
            ),
            None,
        )
    if not isinstance(source, str) or ":research:" not in source:
        raise ValueError(f"{whole} has no waiting research icon")
    return source.rsplit(":", 1)[1]


# The Intrigue window each frame that offers a play opens (``intrigue_window``).
_INTRIGUE_WINDOWS: Final[Mapping[str, str]] = MappingProxyType({
    FrameKind.TURN: "plot",
    FrameKind.AGENT_EFFECTS: "plot",
    FrameKind.REVEAL: "plot",
    FrameKind.COMBAT_INTRIGUE: "combat",
    FrameKind.ENDGAME_INTRIGUE: "endgame",
})
INTRIGUE_WINDOWS: Final = tuple(dict.fromkeys(_INTRIGUE_WINDOWS.values()))


def _leader_face(state: GameState, whole: DomainAction) -> str:
    owner = state.players[whole.actor]
    leader = owner.leader_face_id or owner.leader_id
    if not leader:
        raise ValueError(f"{whole} has no leader")
    return leader


def path_of(state: GameState, whole: DomainAction) -> tuple[DomainAction, ...] | None:
    """The steps that stand for ``whole`` in ``state`` (without a pick), or
    None when ``whole`` is offered as it is."""

    spec = STEP_SPECS.get(whole.action_id)
    if spec is None or (
        not isinstance(spec.printed, Printed)
        and not spec.printed.startswith(_FIXED)
        and spec.printed not in dict(whole.arguments)
    ):
        # Not shown as steps (a reward window's row names no Contract).
        return None
    named = printed_from_state(state, whole)
    if named is None:
        return steps_for(whole)
    return steps_for(whole, named[1], named[0])


def steps_for(
    whole: DomainAction,
    printed: ActionValue | None = None,
    source: Source | None = None,
) -> tuple[DomainAction, ...]:
    """``whole``'s steps; its printed entity (and the source, when a Signet
    Ring box names the leader) given when the state names them
    (``printed_from_state``). The action codec builds its rows by this."""

    spec = STEP_SPECS[whole.action_id]
    arguments = dict(whole.arguments)
    box = arguments.pop("box", 0)
    if not isinstance(spec.printed, Printed):
        printed = (
            spec.printed.removeprefix(_FIXED)
            if spec.printed.startswith(_FIXED)
            else arguments.pop(spec.printed)
        )
    if printed is None:
        raise ValueError(f"{whole} needs its printed entity")
    icon: ActionValue | None = None
    if spec.icon.startswith(_ARG):
        icon = arguments.pop(spec.icon.removeprefix(_ARG), None)
    elif spec.icon:
        icon = spec.icon
    if isinstance(spec.verb, Verb):
        verb = spec.verb
    else:
        key = "" if icon is None else icon
        if not isinstance(key, str) or key not in spec.verb:
            raise ValueError(f"{whole} has no verb for its icon")
        verb = spec.verb[key]
    ref: list[tuple[str, ActionValue]] = [
        ("printed", printed),
        ("source", (source or spec.source).value),
    ]
    if icon is not None:
        ref.append(("icon", icon))
    if spec.option:
        ref.append(("option", spec.option))
    if box:
        ref.append(("box", box))
    targets: list[tuple[Choose, ActionValue]] = []
    for name, kind in spec.targets:
        if name.startswith(_FIXED):
            targets.append((kind, name.removeprefix(_FIXED)))
            continue
        value = arguments.pop(name, None)
        if value is not None and value != "":
            targets.append((kind, value))
    arguments = {name: value for name, value in arguments.items() if value != ""}
    carried = tuple(arguments.items())
    rows: list[DomainAction] = []
    effect_arguments = ref if targets else [*ref, *carried]
    rows.append(_action(verb.value, whole.actor, effect_arguments))
    for index, (kind, value) in enumerate(targets):
        row_arguments = [(CHOOSE_ARGUMENT[kind], value)]
        if index == len(targets) - 1:
            row_arguments.extend(carried)
        rows.append(_action(kind.action_id, whole.actor, row_arguments))
    return tuple(rows)


def _action(
    action_id: str, actor: int, arguments: list[tuple[str, ActionValue]]
) -> DomainAction:
    return DomainAction(action_id, actor, tuple(sorted(arguments)))


def presents_steps(state: GameState) -> bool:
    """Whether the top frame offers its waiting effects effect first."""

    return bool(state.decision_stack) and (
        state.decision_stack[-1].kind in EFFECT_STEP_FRAMES
    )


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
