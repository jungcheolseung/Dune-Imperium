"""What every action template does: its verb, the effect it answers, its target.

The composed-effects engine (docs/composed-effects-plan.md 4.3-4.4) offers
every decision through a few shapes and names the action of each shape by a
(shape, source) -> template table, so the action ids stay what they are
(stage A) while the executor writes no id by hand. This module is that table,
read in both directions:

- ``ACTION_SHAPES[action_id]`` says what an id does: ``trash_agent_card`` and
  ``trash_reveal_card`` share the verb ``TRASH`` and differ in ``source``
  only, which is what a network reads as action features (plan 4.4);
- ``template_id(verb, source, ...)`` names the one id the executor offers
  for a decision of that shape.

Every id of the action catalog with every option enabled has exactly one
row (``tests/unit/rules/test_action_shapes.py`` checks the set, the
arguments each target allows and each tag). A row's ``of`` names what a
refusal or an empty confirmation answers; ``also`` lists further verbs one id
answers (an Intrigue Faction choice pays Influence or gains it); ``variant``
tells two templates of one verb, source and target apart; ``tag`` is the
argument that places the effect: ``box`` for an Agent box (a grafted turn's
second card) and ``source`` for the revealed card whose choice it is.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from types import MappingProxyType
from typing import Final


class Verb(StrEnum):
    """What an action does, whichever effect it answers."""

    PLACE_AGENT = "place_agent"
    START_REVEAL = "start_reveal"
    FINISH = "finish"
    PASS = "pass"
    # Play a held card: an Intrigue, a Navigation card, a turn-start card.
    PLAY = "play"
    # Use an ability or one line of a card (Other Memories, an Intrigue line).
    USE = "use"
    # Resolve a pending effect that needs no further choice.
    RESOLVE = "resolve"
    # Confirm a pending effect that has nothing to act on now.
    CONFIRM_EMPTY = "confirm_empty"
    # Refuse an optional effect.
    DECLINE = "decline"
    # Gain a card, tile or Commander, paying what it costs.
    ACQUIRE = "acquire"
    # Take a Contract, a seat or a space's bonus.
    TAKE = "take"
    # Pick a Leader, Skill, partner card, printed option or Faction bonus.
    CHOOSE = "choose"
    # Keep one of several alternatives (a peeked card, the spice).
    KEEP = "keep"
    DRAW = "draw"
    DISCARD = "discard"
    TRASH = "trash"
    # Pay a cost, and take what it buys.
    PAY = "pay"
    # Gain resources, strength, Persuasion or an icon.
    GAIN = "gain"
    GAIN_INFLUENCE = "gain_influence"
    LOSE_INFLUENCE = "lose_influence"
    EXCHANGE_INFLUENCE = "exchange_influence"
    PLACE_SPY = "place_spy"
    RECALL_SPY = "recall_spy"
    MOVE_SPY = "move_spy"
    LOSE_SPY = "lose_spy"
    RECALL_AGENT = "recall_agent"
    DEPLOY = "deploy"
    WITHDRAW = "withdraw"
    RETREAT = "retreat"
    LOSE_UNIT = "lose_unit"
    RECRUIT = "recruit"
    SUMMON_SANDWORM = "summon_sandworm"
    DESTROY_SHIELD_WALL = "destroy_shield_wall"
    # Put a bonus on a board space (Esmar Tuek's Signet Ring).
    PLACE_BONUS = "place_bonus"
    SET_ASIDE = "set_aside"
    GIVE = "give"
    FLIP = "flip"
    MATCH = "match"
    # Move a track token: Feyd's training, research, the Tleilaxu track.
    ADVANCE = "advance"
    GENERATE_SPECIMENS = "generate_specimens"
    RETURN_SPECIMEN = "return_specimen"
    COMPLETE_CONTRACT = "complete_contract"
    JOIN = "join"
    BID = "bid"
    COLLECT = "collect"


class Source(StrEnum):
    """Whose effect an action answers."""

    # The turn itself: Agent and Reveal turns, deployment, passes, specimens.
    TURN = "turn"
    SETUP = "setup"
    # Purchases of the Reveal turn (Persuasion, specimens).
    PURCHASE = "purchase"
    # A personal card's Agent box (``box`` names a grafted turn's second card).
    AGENT_CARD = "agent_card"
    # A revealed card's effect and the Reveal turn's pending gains.
    REVEAL_CARD = "reveal_card"
    INTRIGUE = "intrigue"
    # Leader abilities, Signet Rings and Navigation cards.
    LEADER = "leader"
    # A visited board space's icons, its Faction Influence and its specials.
    BOARD_SPACE = "board_space"
    # Gather Intelligence.
    SPY = "spy"
    # The Emperor track's Influence 4 Spy.
    INFLUENCE_TRACK = "influence_track"
    # Conflict rewards and Control defense.
    CONFLICT = "conflict"
    CONTRACT = "contract"
    # An acquired card's acquire effect.
    ACQUISITION = "acquisition"
    # Bloodlines Sardaukar Commanders and their Skills.
    COMMANDER = "commander"
    TECH = "tech"
    RESEARCH = "research"
    # A choice an opponent's effect forces on a seat.
    OPPONENT = "opponent"
    # A draw a trigger earned, taken as its own step (OQ-106).
    TRIGGER = "trigger"
    SCOUTS = "scouts"
    ENDGAME = "endgame"
    # Stage B3 (``rules.effect_steps``): an effect row names its source in
    # its own ``source`` argument, and a target row answers the effect its
    # seat picked.
    REF = "ref"


class Target(StrEnum):
    """What an action's arguments pick."""

    NONE = "none"
    # The space an Agent goes to, with its cost option, discount and
    # infiltration (stage B1: the card is picked first), and the board space
    # Kwisatz Haderach's Agent comes off (the original game).
    AGENT_SPACE = "agent_space"
    IMPERIUM_CARD = "imperium_card"
    RESERVE_CARD = "reserve_card"
    TLEILAXU_CARD = "tleilaxu_card"
    RECLAIMED_FORCES = "reclaimed_forces"
    PERSONAL_CARD = "personal_card"
    INTRIGUE_CARD = "intrigue_card"
    NAVIGATION_CARD = "navigation_card"
    CONTRACT = "contract"
    TECH = "tech"
    SKILL = "skill"
    LEADER = "leader"
    POST = "post"
    SPACE = "space"
    TRACK_SPACE = "track_space"
    FACTION = "faction"
    UNITS = "units"
    RESOURCES = "resources"
    OPTION = "option"
    CONFLICT_CARD = "conflict_card"
    SUBCOMMITTEE = "subcommittee"
    MISSION = "mission"
    COUNT = "count"
    WILD_ICON = "wild_icon"
    # Stage B3: the waiting effect an effect row points at (``ref``), with
    # the quantity it carries when it picks no target.
    EFFECT = "effect"


class Tag(StrEnum):
    """The argument that places an effect among several of one kind."""

    BOX = "box"
    # Which completed Contract's icon, where several wait on one turn
    # (stage B3b, OQ-112 (4)).
    CONTRACT = "contract_id"
    # Which acquired card's icon, where several wait on one turn (OQ-141).
    ACQUIRED_CARD = "acquired_card_id"
    SOURCE = "source"


# The argument names each target may use (tags excluded).
TARGET_ARGUMENTS: Final[Mapping[Target, frozenset[str]]] = {
    Target.NONE: frozenset(),
    Target.AGENT_SPACE: frozenset(
        {"cost_option", "discount", "from_space", "infiltrate_post_id", "space_id"}
    ),
    # ``to_deck_top``: the card goes on top of the deck instead of the discard
    # pile (the original game's Bypass Protocol, Recruitment Mission).
    Target.IMPERIUM_CARD: frozenset({"instance_id", "to_deck_top"}),
    Target.RESERVE_CARD: frozenset({"card_id", "to_deck_top"}),
    Target.TLEILAXU_CARD: frozenset({"instance_id", "to_deck_top"}),
    Target.RECLAIMED_FORCES: frozenset({"choice"}),
    # ``effect``: which icon of an Unload card's Reveal box (``rules.unload``).
    Target.PERSONAL_CARD: frozenset({"card_id", "effect", "graft"}),
    Target.INTRIGUE_CARD: frozenset(
        {"card_id", "instance_id", "intrigue_card_id", "option", "player"}
    ),
    Target.NAVIGATION_CARD: frozenset({"card_id"}),
    Target.CONTRACT: frozenset({"instance_id"}),
    # ``negotiators``: the Negotiators a Rise of Ix Acquire Tech returns to
    # the supply, one spice off each [Rise of Ix p. 4] (absent for none).
    Target.TECH: frozenset(
        {
            "choice",
            "destroy_shield_wall",
            "effect",
            "faction",
            "negotiators",
            "post_id",
            "tech_id",
        }
    ),
    Target.SKILL: frozenset({"skill_id"}),
    Target.LEADER: frozenset({"leader_id"}),
    Target.POST: frozenset({"first_post_id", "post_id", "second_post_id"}),
    Target.SPACE: frozenset({"space_id"}),
    Target.TRACK_SPACE: frozenset({"space_id"}),
    Target.FACTION: frozenset(
        {"alliance_recipient", "effect", "faction", "gained_faction", "lost_faction"}
    ),
    # ``dreadnoughts``: the share of a count that is dreadnoughts, for a card
    # that moves "units" (Second Wave) [Rise of Ix p. 6]; ``faction``: the
    # Influence the units' retreat pays for (Negotiated Withdrawal).
    Target.UNITS: frozenset(
        {"commanders", "count", "dreadnoughts", "faction", "player", "zone", "zones"}
    ),
    Target.RESOURCES: frozenset({"solari", "spice", "water"}),
    Target.OPTION: frozenset(
        {"choice", "effect", "option", "pick", "reward", "section", "slot"}
    ),
    Target.CONFLICT_CARD: frozenset({"card_id"}),
    Target.SUBCOMMITTEE: frozenset({"subcommittee_id"}),
    Target.MISSION: frozenset({"target"}),
    # A number of units, the Commanders and the dreadnoughts among them
    # riding along (B3d-2a; Second Wave).
    Target.COUNT: frozenset({"commanders", "count", "dreadnoughts"}),
    Target.WILD_ICON: frozenset({"matching_card_id", "wild_card_id"}),
    Target.EFFECT: frozenset(
        {
            "commanders",
            "count",
            "destroy_shield_wall",
            "icon",
            # The effect a refusal or an empty confirmation answers (B3d-3).
            "of",
            "option",
            "printed",
            "zone",
            # Tleilaxu Surgeon's two units' zones (stage B3b-2).
            "zones",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class ActionShape:
    """One action template's verb, source and target (see the module doc)."""

    verb: Verb
    source: Source
    target: Target = Target.NONE
    of: Verb | None = None
    also: tuple[Verb, ...] = ()
    variant: str = ""
    tag: Tag | None = None

    def __post_init__(self) -> None:
        if self.of is not None and self.verb not in (Verb.DECLINE, Verb.CONFIRM_EMPTY):
            raise ValueError("only a refusal or an empty confirmation answers a verb")
        if self.verb in self.also:
            raise ValueError("an extra verb repeats the row's verb")


_V = Verb
_S = Source
_T = Target
_BOX = Tag.BOX
_SOURCE = Tag.SOURCE


def _row(
    verb: Verb,
    source: Source,
    target: Target = Target.NONE,
    *,
    of: Verb | None = None,
    also: tuple[Verb, ...] = (),
    variant: str = "",
    tag: Tag | None = None,
) -> ActionShape:
    return ActionShape(verb, source, target, of, also, variant, tag)


# Read-only: ``template_id`` caches its answers on this table.
ACTION_SHAPES: Final[Mapping[str, ActionShape]] = MappingProxyType({
    # --- The turn ------------------------------------------------------------
    # Stage B1: the Agent turn's card pick, then its space pick.
    "choose_agent_card": _row(
        _V.CHOOSE, _S.TURN, _T.PERSONAL_CARD, variant="agent_card"
    ),
    "place_agent": _row(_V.PLACE_AGENT, _S.TURN, _T.AGENT_SPACE),
    "reveal_turn": _row(_V.START_REVEAL, _S.TURN),
    "finish_agent_turn": _row(_V.FINISH, _S.TURN, variant="agent"),
    "finish_reveal": _row(_V.FINISH, _S.TURN, variant="reveal"),
    "deploy_troops": _row(_V.DEPLOY, _S.TURN, _T.UNITS),
    "deploy_commanders": _row(_V.DEPLOY, _S.TURN, _T.UNITS, variant="commanders"),
    "withdraw_troops": _row(_V.WITHDRAW, _S.TURN, _T.UNITS),
    "withdraw_commanders": _row(_V.WITHDRAW, _S.TURN, _T.UNITS, variant="commanders"),
    # Rise of Ix: a dreadnought is a third kind of unit beside the troop and
    # the Commander [Rise of Ix p. 6].
    "deploy_dreadnoughts": _row(
        _V.DEPLOY, _S.TURN, _T.UNITS, variant="dreadnoughts"
    ),
    "withdraw_dreadnoughts": _row(
        _V.WITHDRAW, _S.TURN, _T.UNITS, variant="dreadnoughts"
    ),
    "pass_combat_intrigue": _row(_V.PASS, _S.TURN, variant="combat"),
    "pass_endgame_intrigue": _row(_V.PASS, _S.TURN, variant="endgame"),
    "play_turn_start_card": _row(_V.PLAY, _S.TURN, _T.PERSONAL_CARD),
    "choose_graft_partner": _row(_V.CHOOSE, _S.TURN, _T.PERSONAL_CARD),
    "return_specimen": _row(_V.RETURN_SPECIMEN, _S.TURN),
    "use_family_atomics": _row(_V.USE, _S.TURN),
    # --- Setup ---------------------------------------------------------------
    "pick_leader": _row(_V.CHOOSE, _S.SETUP, _T.LEADER),
    "finish_leader_draft": _row(_V.FINISH, _S.SETUP),
    # --- Reveal-turn purchases -----------------------------------------------
    "acquire_imperium": _row(_V.ACQUIRE, _S.PURCHASE, _T.IMPERIUM_CARD),
    "acquire_manipulated_imperium": _row(
        _V.ACQUIRE, _S.PURCHASE, _T.IMPERIUM_CARD, variant="set_aside"
    ),
    "acquire_reserve": _row(_V.ACQUIRE, _S.PURCHASE, _T.RESERVE_CARD),
    "acquire_tleilaxu": _row(_V.ACQUIRE, _S.PURCHASE, _T.TLEILAXU_CARD),
    "acquire_reclaimed_forces": _row(_V.ACQUIRE, _S.PURCHASE, _T.RECLAIMED_FORCES),
    # --- A personal card's Agent box -----------------------------------------
    "resolve_agent_card_effect": _row(_V.RESOLVE, _S.AGENT_CARD, _T.OPTION, tag=_BOX),
    "acquire_imperium_by_card": _row(
        _V.ACQUIRE, _S.AGENT_CARD, _T.IMPERIUM_CARD, variant="by_card", tag=_BOX
    ),
    "acquire_imperium_with_solari": _row(
        _V.ACQUIRE, _S.AGENT_CARD, _T.IMPERIUM_CARD, variant="with_solari", tag=_BOX
    ),
    "acquire_reserve_by_card": _row(
        _V.ACQUIRE, _S.AGENT_CARD, _T.RESERVE_CARD, variant="by_card", tag=_BOX
    ),
    "acquire_reserve_with_solari": _row(
        _V.ACQUIRE, _S.AGENT_CARD, _T.RESERVE_CARD, variant="with_solari", tag=_BOX
    ),
    "decline_agent_card_acquisition": _row(
        _V.DECLINE, _S.AGENT_CARD, of=_V.ACQUIRE, tag=_BOX
    ),
    "choose_agent_card_influence": _row(
        _V.GAIN_INFLUENCE, _S.AGENT_CARD, _T.FACTION, tag=_BOX
    ),
    "choose_agent_card_reward": _row(_V.CHOOSE, _S.AGENT_CARD, _T.OPTION, tag=_BOX),
    "complete_contract_by_card": _row(
        _V.COMPLETE_CONTRACT, _S.AGENT_CARD, _T.CONTRACT, tag=_BOX
    ),
    "discard_agent_card": _row(_V.DISCARD, _S.AGENT_CARD, _T.PERSONAL_CARD, tag=_BOX),
    "select_corrinth_city_discard": _row(
        _V.DISCARD, _S.AGENT_CARD, _T.PERSONAL_CARD, variant="corrinth_city", tag=_BOX
    ),
    "select_long_live_fighters_discard": _row(
        _V.DISCARD, _S.AGENT_CARD, _T.PERSONAL_CARD, variant="long_live_the_fighters"
    ),
    "select_long_live_fighters_draw": _row(_V.DRAW, _S.AGENT_CARD, _T.PERSONAL_CARD),
    "decline_agent_card_discard": _row(
        _V.DECLINE, _S.AGENT_CARD, of=_V.DISCARD, tag=_BOX
    ),
    "decline_agent_card_payment": _row(_V.DECLINE, _S.AGENT_CARD, of=_V.PAY, tag=_BOX),
    "decline_agent_card_intrigue_payment": _row(
        _V.DECLINE, _S.AGENT_CARD, of=_V.PAY, variant="intrigue", tag=_BOX
    ),
    "decline_corrinth_city_payment": _row(
        _V.DECLINE, _S.AGENT_CARD, of=_V.PAY, variant="corrinth_city", tag=_BOX
    ),
    "decline_agent_card_recall": _row(
        _V.DECLINE, _S.AGENT_CARD, of=_V.RECALL_AGENT, tag=_BOX
    ),
    "decline_agent_card_spy": _row(
        _V.DECLINE, _S.AGENT_CARD, of=_V.PLACE_SPY, tag=_BOX
    ),
    "decline_agent_card_trash": _row(_V.DECLINE, _S.AGENT_CARD, of=_V.TRASH, tag=_BOX),
    "lose_agent_card_troop": _row(_V.LOSE_UNIT, _S.AGENT_CARD, _T.UNITS, tag=_BOX),
    "lose_agent_card_influence": _row(
        _V.LOSE_INFLUENCE, _S.AGENT_CARD, _T.FACTION, tag=_BOX
    ),
    "take_agent_card_from_discard": _row(
        _V.TAKE, _S.AGENT_CARD, _T.PERSONAL_CARD, tag=_BOX
    ),
    "pay_agent_card_five_solari_for_tleilaxu": _row(
        _V.PAY, _S.AGENT_CARD, variant="five_solari_for_tleilaxu", tag=_BOX
    ),
    "pay_agent_card_intrigue_and_spice": _row(
        _V.PAY, _S.AGENT_CARD, _T.INTRIGUE_CARD, tag=_BOX
    ),
    "pay_agent_card_specimen": _row(
        _V.PAY, _S.AGENT_CARD, variant="specimen", tag=_BOX
    ),
    "pay_agent_card_solari": _row(_V.PAY, _S.AGENT_CARD, variant="solari", tag=_BOX),
    "pay_agent_card_spice": _row(_V.PAY, _S.AGENT_CARD, variant="spice", tag=_BOX),
    # Landing Rights' Freighter icon (Rise of Ix): up one space or recall,
    # [Rise of Ix p. 5]; an unused icon lapses at the turn's end.
    "advance_agent_card_freighter": _row(
        _V.ADVANCE, _S.AGENT_CARD, variant="freighter", tag=_BOX
    ),
    "recall_agent_card_freighter": _row(
        _V.COLLECT, _S.AGENT_CARD, variant="freighter", tag=_BOX
    ),
    # Weirding Way's extra turn (Rise of Ix); unused, it lapses at the end.
    "take_agent_card_extra_turn": _row(
        _V.TAKE, _S.AGENT_CARD, variant="extra_turn", tag=_BOX
    ),
    # Ixian Engineer's Acquire Tech icon (Rise of Ix): it opens the window.
    "acquire_agent_card_tech": _row(
        _V.ACQUIRE, _S.AGENT_CARD, variant="tech", tag=_BOX
    ),
    # Local Fence's two arrows printed with "-OR-" (Rise of Ix), one each.
    "pay_agent_card_spice_for_solari": _row(
        _V.PAY, _S.AGENT_CARD, variant="spice_for_solari", tag=_BOX
    ),
    "pay_agent_card_solari_for_spice": _row(
        _V.PAY, _S.AGENT_CARD, variant="solari_for_spice", tag=_BOX
    ),
    "pay_agent_card_spice_for_sandworm": _row(
        _V.PAY, _S.AGENT_CARD, variant="spice_for_sandworm", tag=_BOX
    ),
    "pay_agent_card_spice_for_sandworm_and_shield_wall": _row(
        _V.PAY, _S.AGENT_CARD, variant="spice_for_sandworm_and_shield_wall", tag=_BOX
    ),
    "pay_agent_card_two_specimens": _row(
        _V.PAY, _S.AGENT_CARD, variant="two_specimens", tag=_BOX
    ),
    "pay_agent_card_water": _row(_V.PAY, _S.AGENT_CARD, variant="water", tag=_BOX),
    "pay_corrinth_city": _row(_V.PAY, _S.AGENT_CARD, _T.PERSONAL_CARD, tag=_BOX),
    "place_agent_card_spy": _row(_V.PLACE_SPY, _S.AGENT_CARD, _T.POST, tag=_BOX),
    "recall_spy_for_agent_card": _row(_V.RECALL_SPY, _S.AGENT_CARD, _T.POST, tag=_BOX),
    "recall_agent_for_agent_card": _row(
        _V.RECALL_AGENT, _S.AGENT_CARD, _T.SPACE, tag=_BOX
    ),
    "recall_conflict_agent_for_agent_card": _row(
        _V.RECALL_AGENT, _S.AGENT_CARD, variant="conflict", tag=_BOX
    ),
    "retreat_opponent_troop": _row(
        _V.RETREAT, _S.AGENT_CARD, _T.UNITS, variant="opponent", tag=_BOX
    ),
    # The Voice's board space (the original game; a new verb would widen the
    # observation's effect-pick verb segment, ``len(Verb)``).
    "block_agent_card_space": _row(_V.CHOOSE, _S.AGENT_CARD, _T.SPACE, tag=_BOX),
    "take_agent_card_combat_icon": _row(
        _V.GAIN, _S.AGENT_CARD, variant="combat_icon", tag=_BOX
    ),
    "trash_agent_card": _row(_V.TRASH, _S.AGENT_CARD, _T.PERSONAL_CARD, tag=_BOX),
    "trash_agent_card_self_for_vp": _row(
        _V.TRASH, _S.AGENT_CARD, variant="self_for_vp", tag=_BOX
    ),
    "trash_grafted_card_for_influence": _row(
        _V.TRASH,
        _S.AGENT_CARD,
        _T.PERSONAL_CARD,
        variant="grafted_for_influence",
        tag=_BOX,
    ),
    "trash_grafted_card_for_specimen": _row(
        _V.TRASH, _S.AGENT_CARD, variant="grafted_for_specimen", tag=_BOX
    ),
    "trash_intrigue_for_agent_card": _row(
        _V.TRASH, _S.AGENT_CARD, _T.INTRIGUE_CARD, tag=_BOX
    ),
    # Court Intrigue (Rise of Ix): the Intrigue card its arrow puts under the
    # Intrigue deck [Rise of Ix p. 10].
    "put_intrigue_on_bottom_for_agent_card": _row(
        _V.PAY, _S.AGENT_CARD, _T.INTRIGUE_CARD, variant="intrigue_bottom", tag=_BOX
    ),
    # Imperium Ceremony keeps one of the Intrigue deck's top two cards.
    "keep_peeked_intrigue": _row(_V.KEEP, _S.AGENT_CARD, _T.INTRIGUE_CARD),
    # --- Leaders -------------------------------------------------------------
    "advance_feyd_track": _row(_V.ADVANCE, _S.LEADER, _T.TRACK_SPACE, tag=_BOX),
    "acquire_leader_imperium": _row(
        _V.ACQUIRE, _S.LEADER, _T.IMPERIUM_CARD, tag=_BOX
    ),
    "acquire_leader_reserve": _row(_V.ACQUIRE, _S.LEADER, _T.RESERVE_CARD, tag=_BOX),
    "choose_leader_signet_influence": _row(
        _V.GAIN_INFLUENCE, _S.LEADER, _T.FACTION, tag=_BOX
    ),
    # The original game's Baron Harkonnen: a secret Masterstroke Faction.
    "choose_masterstroke_faction": _row(
        _V.CHOOSE, _S.LEADER, _T.FACTION, variant="masterstroke"
    ),
    # The original game's Helena Richese: Manipulate's set-aside Row card.
    "set_aside_leader_imperium": _row(
        _V.SET_ASIDE, _S.LEADER, _T.IMPERIUM_CARD, tag=_BOX
    ),
    # Rise of Ix's Ilesa Ecaz: One Step Ahead's Round Start hand card.
    "set_aside_leader_card": _row(_V.SET_ASIDE, _S.LEADER, _T.PERSONAL_CARD),
    # The original game's Earl Memnon Thorvald: Connections' Influence.
    "choose_connections_influence": _row(
        _V.GAIN_INFLUENCE, _S.LEADER, _T.FACTION, variant="connections"
    ),
    "decline_leader_card_trash": _row(_V.DECLINE, _S.LEADER, of=_V.TRASH, tag=_BOX),
    "decline_leader_signet_payment": _row(_V.DECLINE, _S.LEADER, of=_V.PAY, tag=_BOX),
    "resolve_leader_signet_without_option": _row(
        _V.CONFIRM_EMPTY, _S.LEADER, of=_V.CHOOSE, tag=_BOX
    ),
    "decline_leader_spy_placement": _row(
        _V.DECLINE, _S.LEADER, of=_V.PLACE_SPY, tag=_BOX
    ),
    "deploy_leader_agent": _row(_V.DEPLOY, _S.LEADER, variant="agent", tag=_BOX),
    "gain_leader_signet_spice": _row(_V.GAIN, _S.LEADER, tag=_BOX),
    # Rise of Ix's Tessia Vernius: Duplicity's Influence lost (its cost), her
    # first Snooper reward's discard and its refusal outside her turn; and an
    # effect's Influence with one Faction it names, a row each (OQ-153).
    "lose_leader_influence": _row(_V.LOSE_INFLUENCE, _S.LEADER, _T.FACTION, tag=_BOX),
    "discard_snooper_card": _row(
        _V.DISCARD, _S.LEADER, _T.PERSONAL_CARD, variant="snooper"
    ),
    "decline_snooper_discard": _row(
        _V.DECLINE, _S.LEADER, of=_V.DISCARD, variant="snooper"
    ),
    "resolve_effect_influence": _row(
        _V.GAIN_INFLUENCE, _S.INTRIGUE, _T.FACTION, variant="effect_influence"
    ),
    # Rise of Ix's Viscount Hundro Moritani: Couriers' spice for a Freighter
    # move up or a recall.
    "advance_leader_freighter": _row(
        _V.ADVANCE, _S.LEADER, variant="freighter", tag=_BOX
    ),
    "recall_leader_freighter": _row(
        _V.COLLECT, _S.LEADER, variant="freighter", tag=_BOX
    ),
    # Rise of Ix's Prince Rhombur Vernius: Ixian Technology's two halves.
    "acquire_leader_tech": _row(_V.ACQUIRE, _S.LEADER, variant="ix_tech", tag=_BOX),
    "place_leader_negotiator": _row(
        _V.RECRUIT, _S.LEADER, variant="negotiator", tag=_BOX
    ),
    "gain_leader_signet_troop": _row(_V.RECRUIT, _S.LEADER, tag=_BOX),
    "pay_leader_signet_solari": _row(_V.PAY, _S.LEADER, variant="solari", tag=_BOX),
    "pay_leader_signet_spice": _row(_V.PAY, _S.LEADER, variant="spice", tag=_BOX),
    "pay_leader_signet_water": _row(_V.PAY, _S.LEADER, variant="water", tag=_BOX),
    "place_leader_bonus_spice": _row(_V.PLACE_BONUS, _S.LEADER, tag=_BOX),
    "take_leader_bonus_spice": _row(_V.TAKE, _S.LEADER, _T.SPACE, tag=_BOX),
    "place_leader_spy": _row(_V.PLACE_SPY, _S.LEADER, _T.POST, tag=_BOX),
    "recall_spy_for_leader_placement": _row(
        _V.RECALL_SPY, _S.LEADER, _T.POST, variant="for_placement", tag=_BOX
    ),
    "recall_spy_for_leader": _row(_V.RECALL_SPY, _S.LEADER, _T.POST),
    "retreat_leader_commander": _row(_V.RETREAT, _S.LEADER, variant="commander"),
    "retreat_leader_troop": _row(_V.RETREAT, _S.LEADER, variant="troop"),
    "retreat_leader_troops": _row(_V.RETREAT, _S.LEADER, _T.UNITS, tag=_BOX),
    "trash_leader_card": _row(_V.TRASH, _S.LEADER, _T.PERSONAL_CARD, tag=_BOX),
    # Rise of Ix's Archduke Armand Ecaz: Coordination's Reveal-turn trash.
    "trash_leader_reveal_card": _row(
        _V.TRASH, _S.LEADER, _T.PERSONAL_CARD, variant="coordination"
    ),
    "trash_leader_tech": _row(_V.TRASH, _S.LEADER, _T.TECH, tag=_BOX),
    "use_other_memories": _row(_V.USE, _S.LEADER),
    "pay_leader_board_repeat": _row(_V.PAY, _S.LEADER, variant="board_repeat"),
    "place_navigation_card": _row(_V.CHOOSE, _S.LEADER, _T.NAVIGATION_CARD),
    "play_navigation": _row(_V.PLAY, _S.LEADER, _T.OPTION),
    "decline_navigation": _row(_V.DECLINE, _S.LEADER, of=_V.PLAY),
    # Liet Kynes' optional trash for a sandworm, and its Intrigue draw.
    "trash_optional_card": _row(
        _V.TRASH, _S.LEADER, _T.PERSONAL_CARD, variant="optional"
    ),
    "decline_optional_trash": _row(
        _V.DECLINE, _S.LEADER, of=_V.TRASH, variant="optional"
    ),
    "draw_planetologist_intrigue": _row(_V.DRAW, _S.LEADER, variant="intrigue"),
    # Kota Odax's Secret Project.
    "choose_secret_project": _row(_V.CHOOSE, _S.LEADER, _T.TECH),
    # --- Intrigue cards ------------------------------------------------------
    "play_intrigue": _row(_V.PLAY, _S.INTRIGUE, _T.INTRIGUE_CARD),
    "play_conflict_end_intrigue": _row(
        _V.PLAY, _S.INTRIGUE, _T.INTRIGUE_CARD, variant="conflict_end"
    ),
    "decline_conflict_end_intrigue": _row(
        _V.DECLINE, _S.INTRIGUE, of=_V.PLAY, variant="conflict_end"
    ),
    "finish_conflict_end_intrigue": _row(
        _V.FINISH, _S.INTRIGUE, variant="conflict_end"
    ),
    "use_intrigue_effect": _row(_V.USE, _S.INTRIGUE, _T.OPTION),
    "finish_intrigue_effects": _row(_V.FINISH, _S.INTRIGUE),
    "resolve_intrigue_rewards": _row(_V.RESOLVE, _S.INTRIGUE),
    # One id pays Influence and gains it (the slot says which).
    "choose_intrigue_faction": _row(
        _V.GAIN_INFLUENCE, _S.INTRIGUE, _T.FACTION, also=(_V.LOSE_INFLUENCE,)
    ),
    "resolve_intrigue_influence_without_faction": _row(
        _V.CONFIRM_EMPTY, _S.INTRIGUE, of=_V.GAIN_INFLUENCE
    ),
    "choose_intrigue_discard": _row(_V.DISCARD, _S.INTRIGUE, _T.PERSONAL_CARD),
    "detonate_shield_wall": _row(_V.DESTROY_SHIELD_WALL, _S.INTRIGUE),
    "keep_shield_wall": _row(_V.DECLINE, _S.INTRIGUE, of=_V.DESTROY_SHIELD_WALL),
    # Rise of Ix's Dreadnought icon ("you may commission", [Rise of Ix p. 6]),
    # as a recruit: a new verb would widen the observation's effect-pick verb
    # segment (``len(Verb)``).
    "commission_intrigue_dreadnought": _row(
        _V.RECRUIT, _S.INTRIGUE, variant="dreadnought"
    ),
    "decline_intrigue_dreadnought": _row(
        _V.DECLINE, _S.INTRIGUE, of=_V.RECRUIT, variant="dreadnought"
    ),
    # Rise of Ix's Tech Negotiation icon ("you may take a troop", [Rise of Ix
    # p. 4]), a recruit-shaped row for the same reason as the Dreadnought's.
    "place_intrigue_negotiator": _row(_V.RECRUIT, _S.INTRIGUE, variant="negotiator"),
    "decline_intrigue_negotiator": _row(
        _V.DECLINE, _S.INTRIGUE, of=_V.RECRUIT, variant="negotiator"
    ),
    # Rise of Ix's Freighter icon ("you may move your Freighter", [Rise of Ix
    # p. 5]): up one space, recall (collect the spaces' rewards), or neither.
    "advance_intrigue_freighter": _row(
        _V.ADVANCE, _S.INTRIGUE, variant="freighter"
    ),
    "recall_intrigue_freighter": _row(_V.COLLECT, _S.INTRIGUE, variant="freighter"),
    "decline_intrigue_freighter": _row(
        _V.DECLINE, _S.INTRIGUE, of=_V.ADVANCE, variant="freighter"
    ),
    "deploy_intrigue_troops": _row(_V.DEPLOY, _S.INTRIGUE, _T.UNITS),
    "retreat_intrigue_troops": _row(_V.RETREAT, _S.INTRIGUE, _T.UNITS),
    "lose_intrigue_troop": _row(_V.LOSE_UNIT, _S.INTRIGUE, _T.UNITS),
    "trash_intrigue_card": _row(_V.TRASH, _S.INTRIGUE, _T.PERSONAL_CARD),
    "decline_intrigue_trash": _row(_V.DECLINE, _S.INTRIGUE, of=_V.TRASH),
    "trash_intrigue_hand_card": _row(_V.TRASH, _S.INTRIGUE, _T.INTRIGUE_CARD),
    "give_intrigue_card": _row(_V.GIVE, _S.INTRIGUE, _T.INTRIGUE_CARD),
    "place_intrigue_spy": _row(_V.PLACE_SPY, _S.INTRIGUE, _T.POST),
    "recall_spy_for_intrigue": _row(_V.RECALL_SPY, _S.INTRIGUE, _T.POST),
    "decline_intrigue_spy": _row(_V.DECLINE, _S.INTRIGUE, of=_V.PLACE_SPY),
    # False Orders: the owner's Spy on the turn's board space.
    "place_spy_on_space": _row(
        _V.PLACE_SPY, _S.INTRIGUE, _T.POST, variant="turn_space"
    ),
    "recall_spy_for_placement": _row(
        _V.RECALL_SPY, _S.INTRIGUE, _T.POST, variant="for_placement"
    ),
    "decline_spy_placement": _row(
        _V.CONFIRM_EMPTY, _S.INTRIGUE, of=_V.PLACE_SPY, variant="turn_space"
    ),
    # A peek at the top card of the deck: leave it, discard it, or draw it.
    "put_back_top_card": _row(_V.KEEP, _S.INTRIGUE, variant="deck_top"),
    "discard_top_card": _row(_V.DISCARD, _S.INTRIGUE, variant="deck_top"),
    "draw_top_card_for_solari": _row(_V.DRAW, _S.INTRIGUE, variant="deck_top"),
    # Double Cross (the original game): the opponent whose troop in the
    # Conflict is lost, named by the owner.
    "choose_opponent_troop_loss": _row(
        _V.LOSE_UNIT, _S.INTRIGUE, _T.UNITS, variant="opponent"
    ),
    # Bindu Suspension (the original game): pass the turn after the draw, or
    # play it normally (OQ-117).
    "pass_turn_intrigue": _row(_V.PASS, _S.INTRIGUE, variant="turn"),
    "keep_turn_intrigue": _row(_V.DECLINE, _S.INTRIGUE, of=_V.PASS),
    # Poison Snooper (the original game): draw the card it looked at, or
    # trash it, free either way.
    "draw_top_card": _row(_V.DRAW, _S.INTRIGUE, variant="deck_top_free"),
    "trash_top_card": _row(_V.TRASH, _S.INTRIGUE, variant="deck_top"),
    # Cost-free choices with nothing to act on are played and confirmed
    # (OQ-113 (C), user ruling 2026-10-24): an empty deck's peek, an empty
    # Imperium Row's set-aside, an empty hand's mandatory trash.
    "skip_intrigue_top_card": _row(
        _V.CONFIRM_EMPTY, _S.INTRIGUE, of=_V.KEEP, variant="deck_top"
    ),
    "skip_intrigue_set_aside": _row(_V.CONFIRM_EMPTY, _S.INTRIGUE, of=_V.SET_ASIDE),
    "skip_intrigue_trash": _row(_V.CONFIRM_EMPTY, _S.INTRIGUE, of=_V.TRASH),
    # Urgent Mission (the original game): the Agent that returns to its
    # Leader, on a board space or in the Conflict, and the confirmation when
    # there is none on the board (OQ-113 (C)).
    "recall_agent_for_intrigue": _row(_V.RECALL_AGENT, _S.INTRIGUE, _T.SPACE),
    "recall_conflict_agent_for_intrigue": _row(
        _V.RECALL_AGENT, _S.INTRIGUE, variant="conflict"
    ),
    "skip_intrigue_recall_agent": _row(
        _V.CONFIRM_EMPTY, _S.INTRIGUE, of=_V.RECALL_AGENT
    ),
    "acquire_intrigue_imperium": _row(_V.ACQUIRE, _S.INTRIGUE, _T.IMPERIUM_CARD),
    "acquire_intrigue_reserve": _row(_V.ACQUIRE, _S.INTRIGUE, _T.RESERVE_CARD),
    "skip_intrigue_acquisition": _row(_V.CONFIRM_EMPTY, _S.INTRIGUE, of=_V.ACQUIRE),
    "acquire_intrigue_tleilaxu": _row(_V.ACQUIRE, _S.INTRIGUE, _T.TLEILAXU_CARD),
    "acquire_intrigue_reclaimed_forces": _row(
        _V.ACQUIRE, _S.INTRIGUE, _T.RECLAIMED_FORCES
    ),
    "decline_intrigue_tleilaxu": _row(_V.DECLINE, _S.INTRIGUE, of=_V.ACQUIRE),
    "flip_battle_card": _row(_V.FLIP, _S.INTRIGUE, _T.CONFLICT_CARD),
    "manipulate_imperium_row": _row(_V.SET_ASIDE, _S.INTRIGUE, _T.IMPERIUM_CARD),
    # Coercive Negotiation: one of the Contracts it revealed.
    "take_trigger_contract": _row(_V.TAKE, _S.INTRIGUE, _T.CONTRACT),
    # --- Board spaces --------------------------------------------------------
    "resolve_board_effect": _row(_V.RESOLVE, _S.BOARD_SPACE, _T.OPTION),
    "resolve_faction_influence": _row(_V.GAIN_INFLUENCE, _S.BOARD_SPACE),
    "choose_shipping_influence": _row(_V.GAIN_INFLUENCE, _S.BOARD_SPACE, _T.FACTION),
    "harvest_maker_spice": _row(_V.GAIN, _S.BOARD_SPACE, _T.SPACE),
    "take_desert_riding_hooks": _row(_V.TAKE, _S.BOARD_SPACE, _T.SPACE),
    "summon_maker_sandworms": _row(_V.SUMMON_SANDWORM, _S.BOARD_SPACE, _T.SPACE),
    "take_sietch_tabr_supplies": _row(
        _V.CHOOSE, _S.BOARD_SPACE, variant="sietch_tabr_supplies"
    ),
    "take_sietch_tabr_water": _row(
        _V.CHOOSE, _S.BOARD_SPACE, variant="sietch_tabr_water"
    ),
    "take_sietch_tabr_water_and_destroy_wall": _row(
        _V.CHOOSE, _S.BOARD_SPACE, variant="sietch_tabr_water_and_destroy_wall"
    ),
    "take_tuek_sietch_spice": _row(
        _V.CHOOSE, _S.BOARD_SPACE, variant="tuek_sietch_spice"
    ),
    "take_tuek_sietch_card": _row(
        _V.CHOOSE, _S.BOARD_SPACE, variant="tuek_sietch_card"
    ),
    "trash_card_for_desert_tactics": _row(_V.TRASH, _S.BOARD_SPACE, _T.PERSONAL_CARD),
    "trash_intrigue_for_imperial_privilege": _row(
        _V.TRASH, _S.BOARD_SPACE, _T.INTRIGUE_CARD
    ),
    "recall_agent_for_imperial_privilege": _row(
        _V.RECALL_AGENT, _S.BOARD_SPACE, _T.SPACE
    ),
    "recall_conflict_agent_for_imperial_privilege": _row(
        _V.RECALL_AGENT, _S.BOARD_SPACE, variant="conflict"
    ),
    "resolve_imperial_privilege_without_recall": _row(
        _V.CONFIRM_EMPTY, _S.BOARD_SPACE, of=_V.RECALL_AGENT
    ),
    "recall_spy_for_espionage": _row(_V.RECALL_SPY, _S.BOARD_SPACE, _T.POST),
    "resolve_espionage_place_spy": _row(_V.PLACE_SPY, _S.BOARD_SPACE, _T.POST),
    "resolve_espionage_without_spy": _row(
        _V.CONFIRM_EMPTY, _S.BOARD_SPACE, of=_V.PLACE_SPY
    ),
    # --- Spies and the Influence tracks --------------------------------------
    "gather_intelligence": _row(_V.RECALL_SPY, _S.SPY, _T.POST),
    "decline_gather_intelligence": _row(_V.DECLINE, _S.SPY, of=_V.RECALL_SPY),
    "place_track_spy": _row(_V.PLACE_SPY, _S.INFLUENCE_TRACK),
    # --- Conflict ------------------------------------------------------------
    # One icon of a recipient's reward window (stage B2, OQ-112).
    "resolve_combat_reward_icon": _row(_V.RESOLVE, _S.CONFLICT, _T.OPTION),
    "pay_combat_reward": _row(_V.PAY, _S.CONFLICT),
    "decline_combat_reward": _row(_V.DECLINE, _S.CONFLICT, of=_V.PAY),
    "choose_combat_reward_influence": _row(_V.GAIN_INFLUENCE, _S.CONFLICT, _T.FACTION),
    "choose_distinct_combat_reward_influence": _row(
        _V.GAIN_INFLUENCE, _S.CONFLICT, _T.FACTION, variant="distinct"
    ),
    "resolve_combat_influence_without_faction": _row(
        _V.CONFIRM_EMPTY, _S.CONFLICT, of=_V.GAIN_INFLUENCE
    ),
    "place_combat_reward_spy": _row(_V.PLACE_SPY, _S.CONFLICT, _T.POST),
    "recall_spy_for_combat_reward": _row(_V.RECALL_SPY, _S.CONFLICT, _T.POST),
    "recall_spies_for_combat_reward": _row(
        _V.RECALL_SPY, _S.CONFLICT, _T.POST, variant="two"
    ),
    "decline_combat_reward_spy": _row(_V.DECLINE, _S.CONFLICT, of=_V.PLACE_SPY),
    # The winner's dreadnought on a Control space (Rise of Ix): "take
    # control", as the Control icon's verb (a new verb would widen the
    # observation's effect-pick verb segment, ``len(Verb)``).
    "place_combat_reward_dreadnought": _row(_V.TAKE, _S.CONFLICT, _T.SPACE),
    # Detonation Devices' answer in the same choice: the dreadnought back to
    # the supply for 1 VP instead of a space ("gain", as the VP icon's verb);
    # the tile prints it.
    "detonate_combat_reward_dreadnought": _row(
        _V.GAIN, _S.TECH, variant="detonation"
    ),
    "trash_combat_reward_card": _row(_V.TRASH, _S.CONFLICT, _T.PERSONAL_CARD),
    "decline_combat_reward_trash": _row(_V.DECLINE, _S.CONFLICT, of=_V.TRASH),
    "resolve_combat_trash_without_card": _row(
        _V.CONFIRM_EMPTY, _S.CONFLICT, of=_V.TRASH
    ),
    "deploy_control_defense": _row(_V.DEPLOY, _S.CONFLICT, variant="control_defense"),
    "decline_control_defense": _row(_V.DECLINE, _S.CONFLICT, of=_V.DEPLOY),
    # --- Contracts -----------------------------------------------------------
    "take_contract": _row(_V.TAKE, _S.CONTRACT, _T.CONTRACT),
    # One icon of a completed Contract's reward: a row of its window (stage
    # B2, OQ-112), or of its owner's turn, naming the Contract (stage B3b,
    # OQ-112 (4)).
    "resolve_contract_reward_icon": _row(
        _V.RESOLVE, _S.CONTRACT, _T.OPTION, tag=Tag.CONTRACT
    ),
    # One icon of an acquired Imperium card's acquire box, waiting on its
    # owner's turn: an Influence with a fixed Faction, or the chosen one
    # (OQ-141).
    "resolve_acquire_icon": _row(
        _V.GAIN_INFLUENCE, _S.ACQUISITION, _T.FACTION, tag=Tag.ACQUIRED_CARD
    ),
    # Nothing in the market can be taken now: the icons wait, or fizzle
    # with an empty market (OQ-059).
    "hold_contract_icons": _row(
        _V.CONFIRM_EMPTY, _S.CONTRACT, of=_V.TAKE, variant="hold"
    ),
    "resolve_contract_icons_without_contract": _row(
        _V.CONFIRM_EMPTY, _S.CONTRACT, of=_V.TAKE
    ),
    # Stage B3: a Contract's completion is its own effect row
    # (``rules.effect_steps``); the id is the whole action's too.
    "complete_contract": _row(_V.COMPLETE_CONTRACT, _S.REF, _T.EFFECT, tag=_SOURCE),
    "place_contract_spy": _row(_V.PLACE_SPY, _S.CONTRACT, _T.POST),
    "recall_spy_for_contract": _row(_V.RECALL_SPY, _S.CONTRACT, _T.POST),
    "decline_contract_spy": _row(_V.DECLINE, _S.CONTRACT, of=_V.PLACE_SPY),
    "recall_agent_for_contract": _row(_V.RECALL_AGENT, _S.CONTRACT, _T.SPACE),
    "recall_conflict_agent_for_contract": _row(
        _V.RECALL_AGENT, _S.CONTRACT, variant="conflict"
    ),
    "resolve_contract_without_recall": _row(
        _V.CONFIRM_EMPTY, _S.CONTRACT, of=_V.RECALL_AGENT
    ),
    "trash_intrigue_for_contract": _row(_V.TRASH, _S.CONTRACT, _T.INTRIGUE_CARD),
    # --- A revealed card and the Reveal turn's gains -------------------------
    # One icon of a Rise of Ix Unload card's Reveal box, gained when the card
    # is discarded or trashed: a row of its owner's turn or of its window,
    # naming the card (``rules.unload``).
    "resolve_unload_icon": _row(
        _V.RESOLVE, _S.REVEAL_CARD, _T.PERSONAL_CARD, variant="unload"
    ),
    "gain_reveal_resources": _row(_V.GAIN, _S.REVEAL_CARD, _T.RESOURCES),
    "gain_reveal_faction_influence": _row(
        _V.GAIN_INFLUENCE, _S.REVEAL_CARD, _T.FACTION, variant="pending_gain"
    ),
    "recruit_reveal_troops": _row(_V.RECRUIT, _S.REVEAL_CARD),
    "deploy_reveal_supply_troops": _row(
        _V.DEPLOY, _S.REVEAL_CARD, variant="supply_troops"
    ),
    "draw_reveal_intrigue": _row(_V.DRAW, _S.REVEAL_CARD, variant="intrigue"),
    "generate_reveal_specimens": _row(_V.GENERATE_SPECIMENS, _S.REVEAL_CARD),
    "advance_reveal_tleilaxu": _row(_V.ADVANCE, _S.REVEAL_CARD, variant="tleilaxu"),
    "advance_reveal_research": _row(_V.ADVANCE, _S.REVEAL_CARD, variant="research"),
    "gain_reveal_persuasion": _row(_V.GAIN, _S.REVEAL_CARD, variant="persuasion"),
    "gain_two_reveal_persuasion": _row(
        _V.GAIN, _S.REVEAL_CARD, variant="two_persuasion"
    ),
    "gain_two_reveal_swords": _row(_V.GAIN, _S.REVEAL_CARD, variant="two_swords"),
    "take_reveal_contract": _row(_V.TAKE, _S.REVEAL_CARD, variant="contract"),
    "gain_five_reveal_solari": _row(_V.GAIN, _S.REVEAL_CARD, variant="five_solari"),
    "take_high_council_from_reveal": _row(
        _V.TAKE, _S.REVEAL_CARD, variant="high_council"
    ),
    "gain_two_reveal_strength": _row(_V.GAIN, _S.REVEAL_CARD, variant="strength"),
    "keep_contract_reveal_spice": _row(_V.KEEP, _S.REVEAL_CARD, tag=_SOURCE),
    "trash_contract_reveal_for_vp": _row(
        _V.TRASH, _S.REVEAL_CARD, variant="self_for_vp", tag=_SOURCE
    ),
    "trash_reveal_card": _row(_V.TRASH, _S.REVEAL_CARD, _T.PERSONAL_CARD, tag=_SOURCE),
    "command_acquire_row_card": _row(_V.ACQUIRE, _S.REVEAL_CARD, _T.IMPERIUM_CARD),
    "place_reveal_spy": _row(_V.PLACE_SPY, _S.REVEAL_CARD, _T.POST, tag=_SOURCE),
    "recall_spy_for_reveal": _row(_V.RECALL_SPY, _S.REVEAL_CARD, _T.POST, tag=_SOURCE),
    "recall_spy_for_reveal_placement": _row(
        _V.RECALL_SPY, _S.REVEAL_CARD, _T.POST, variant="for_placement", tag=_SOURCE
    ),
    "recall_spies_for_reveal": _row(
        _V.RECALL_SPY, _S.REVEAL_CARD, _T.POST, variant="two"
    ),
    "decline_reveal_spy_recall": _row(
        _V.DECLINE, _S.REVEAL_CARD, of=_V.RECALL_SPY, tag=_SOURCE
    ),
    "exchange_reveal_influence": _row(
        _V.EXCHANGE_INFLUENCE, _S.REVEAL_CARD, _T.FACTION
    ),
    "gain_reveal_influence": _row(
        _V.GAIN_INFLUENCE, _S.REVEAL_CARD, _T.FACTION, tag=_SOURCE
    ),
    "lose_reveal_influence_for_vp": _row(
        _V.LOSE_INFLUENCE, _S.REVEAL_CARD, _T.FACTION
    ),
    "pay_reveal_spice_influence": _row(_V.PAY, _S.REVEAL_CARD, _T.FACTION),
    "pay_reveal_solari_for_vp": _row(_V.PAY, _S.REVEAL_CARD, variant="solari_for_vp"),
    "pay_reveal_spice_for_vp": _row(_V.PAY, _S.REVEAL_CARD, variant="spice_for_vp"),
    "pay_reveal_solari_for_troops": _row(
        _V.PAY, _S.REVEAL_CARD, variant="solari_for_troops"
    ),
    # Guild Chief Administrator's Freighter icon (Rise of Ix): up one space
    # or recall [Rise of Ix p. 5]; unused, it lapses when the Reveal ends.
    "advance_reveal_freighter": _row(
        _V.ADVANCE, _S.REVEAL_CARD, variant="freighter"
    ),
    "recall_reveal_freighter": _row(_V.COLLECT, _S.REVEAL_CARD, variant="freighter"),
    # Negotiated Withdrawal's arrow (Rise of Ix): three units, troops or
    # dreadnoughts, for an Influence with a chosen Faction.
    "retreat_reveal_units_for_influence": _row(
        _V.RETREAT, _S.REVEAL_CARD, _T.UNITS, variant="units_for_influence"
    ),
    "pay_reveal_water_for_sandworm": _row(
        _V.PAY, _S.REVEAL_CARD, variant="water_for_sandworm"
    ),
    # Desert Power: the 2 Persuasion instead of the sandworm.
    "decline_reveal_sandworm": _row(
        _V.DECLINE, _S.REVEAL_CARD, of=_V.PAY, variant="sandworm"
    ),
    "deploy_reveal_card_troop": _row(
        _V.DEPLOY, _S.REVEAL_CARD, _T.UNITS, tag=_SOURCE
    ),
    "retreat_reveal_card_troop": _row(
        _V.RETREAT, _S.REVEAL_CARD, _T.UNITS, tag=_SOURCE
    ),
    # Sardaukar Legion's deploy, Scout's and Chani's retreat of ``count`` troops
    # (original game).
    "deploy_reveal_card_troops": _row(
        _V.DEPLOY, _S.REVEAL_CARD, _T.UNITS, variant="count", tag=_SOURCE
    ),
    "retreat_reveal_card_troops": _row(
        _V.RETREAT, _S.REVEAL_CARD, _T.UNITS, variant="count", tag=_SOURCE
    ),
    "retreat_two_troops_for_reveal": _row(
        _V.RETREAT, _S.REVEAL_CARD, _T.UNITS, variant="two", tag=_SOURCE
    ),
    "lose_reveal_troops_for_specimens": _row(
        _V.LOSE_UNIT, _S.REVEAL_CARD, _T.UNITS
    ),
    # Kept in the catalog after codec v147 dropped them (indices stay).
    "defer_reveal_choice": _row(_V.PASS, _S.REVEAL_CARD, variant="defer"),
    "resume_reveal_choice": _row(
        _V.CHOOSE, _S.REVEAL_CARD, _T.OPTION, variant="resume"
    ),
    # --- An acquired card's acquire effect -----------------------------------
    "place_acquisition_spy": _row(_V.PLACE_SPY, _S.ACQUISITION, _T.POST),
    "recall_spy_for_acquisition": _row(_V.RECALL_SPY, _S.ACQUISITION, _T.POST),
    "decline_acquisition_spy": _row(_V.DECLINE, _S.ACQUISITION, of=_V.PLACE_SPY),
    # --- Sardaukar Commanders ------------------------------------------------
    "acquire_sardaukar_commander": _row(_V.ACQUIRE, _S.COMMANDER, _T.SKILL),
    "recruit_sardaukar_commander": _row(_V.RECRUIT, _S.COMMANDER),
    "choose_skill": _row(_V.CHOOSE, _S.COMMANDER, _T.SKILL),
    "decline_skill": _row(_V.DECLINE, _S.COMMANDER, of=_V.CHOOSE),
    "resolve_commander_without_skill": _row(
        _V.CONFIRM_EMPTY, _S.COMMANDER, of=_V.CHOOSE
    ),
    "trash_skill_for_strength": _row(_V.TRASH, _S.COMMANDER, _T.SKILL),
    # --- Tech tiles ----------------------------------------------------------
    "acquire_tech": _row(_V.ACQUIRE, _S.TECH, _T.TECH),
    "resolve_tech_acquire_effect": _row(_V.RESOLVE, _S.TECH, _T.TECH),
    "resolve_tech_influence_without_faction": _row(
        _V.CONFIRM_EMPTY, _S.TECH, of=_V.GAIN_INFLUENCE
    ),
    "decline_tech": _row(_V.DECLINE, _S.TECH, of=_V.ACQUIRE),
    "flip_tech": _row(_V.FLIP, _S.TECH, _T.TECH),
    # Rise of Ix's tiles used by trashing them (stage P4c-2c): Spy Satellites'
    # VP and Sonic Snoopers, whose pick puts Intrigue cards on the Intrigue
    # deck's bottom ("set aside", the nearest verb: a new one would widen the
    # observation's effect-pick verb segment) and stops with the draw.
    "trash_tech": _row(_V.TRASH, _S.TECH, _T.TECH),
    "put_intrigue_on_bottom": _row(
        _V.SET_ASIDE, _S.TECH, _T.INTRIGUE_CARD, variant="deck_bottom"
    ),
    "finish_intrigue_bottom": _row(_V.FINISH, _S.TECH, variant="intrigue_bottom"),
    # The Freighter's own window outside its owner's turn, and one reward of a
    # Shipping track recall (a row of its owner's turn or of its window): the
    # track is on the Ix board (stage P4c-3, ``rules.shipping_track``).
    "advance_freighter": _row(_V.ADVANCE, _S.BOARD_SPACE, variant="freighter"),
    "recall_freighter": _row(_V.COLLECT, _S.BOARD_SPACE, variant="freighter"),
    "decline_freighter": _row(
        _V.DECLINE, _S.BOARD_SPACE, of=_V.ADVANCE, variant="freighter"
    ),
    "resolve_shipping_reward": _row(
        _V.RESOLVE, _S.BOARD_SPACE, _T.FACTION, variant="shipping_reward"
    ),
    # The icons of Rise of Ix's four spaces (stage P4c-4,
    # ``rules.ix_board_spaces``): the Dreadnought icon, the Acquire Tech icon
    # and the Tech Negotiation "OR" box's two halves, and the Freighter icon's
    # two moves. Spaceport's Foldspace card on top of the deck is the
    # Foldspace space's own variant.
    "commission_board_dreadnought": _row(
        _V.RECRUIT, _S.BOARD_SPACE, variant="dreadnought"
    ),
    "acquire_board_tech": _row(_V.ACQUIRE, _S.BOARD_SPACE, variant="ix_tech"),
    "acquire_negotiation_tech": _row(
        _V.ACQUIRE, _S.BOARD_SPACE, variant="negotiation_tech"
    ),
    "place_board_negotiator": _row(_V.RECRUIT, _S.BOARD_SPACE, variant="negotiator"),
    "advance_board_freighter": _row(
        _V.ADVANCE, _S.BOARD_SPACE, variant="board_freighter"
    ),
    "recall_board_freighter": _row(
        _V.COLLECT, _S.BOARD_SPACE, variant="board_freighter"
    ),
    "acquire_foldspace_to_deck_top": _row(
        _V.ACQUIRE, _S.BOARD_SPACE, variant="foldspace_deck_top"
    ),
    # Forbidden Weapons: the swords and an Influence lost, or the trash.
    "choose_tech_strength": _row(_V.CHOOSE, _S.TECH, _T.FACTION),
    "choose_tech_trash": _row(_V.CHOOSE, _S.TECH, variant="trash"),
    "place_tech_spy": _row(_V.PLACE_SPY, _S.TECH),
    # Disposal Facility's Reveal-turn trash of a card in play (Rise of Ix).
    "trash_disposal_facility_card": _row(
        _V.TRASH, _S.TECH, _T.PERSONAL_CARD, variant="disposal_facility"
    ),
    # --- Research ------------------------------------------------------------
    "choose_research_space": _row(_V.ADVANCE, _S.RESEARCH, _T.TRACK_SPACE),
    "choose_research_influence": _row(_V.GAIN_INFLUENCE, _S.RESEARCH, _T.FACTION),
    "trash_intrigue_for_research_bonus": _row(
        _V.TRASH, _S.RESEARCH, _T.INTRIGUE_CARD
    ),
    "pay_research_bonus": _row(_V.PAY, _S.RESEARCH),
    "decline_research_bonus": _row(_V.DECLINE, _S.RESEARCH),
    "resolve_research_icon": _row(_V.RESOLVE, _S.RESEARCH, _T.OPTION),
    # --- Choices an opponent's effect forces ---------------------------------
    "discard_opponent_card": _row(_V.DISCARD, _S.OPPONENT, _T.PERSONAL_CARD),
    # Covert Operation's confirm of a seat with an empty hand (OQ-138).
    "resolve_opponent_discard_without_card": _row(
        _V.CONFIRM_EMPTY, _S.OPPONENT, of=_V.DISCARD
    ),
    "move_spy": _row(_V.MOVE_SPY, _S.OPPONENT, _T.POST),
    "lose_moved_spy": _row(_V.LOSE_SPY, _S.OPPONENT),
    "lose_unit": _row(_V.LOSE_UNIT, _S.OPPONENT, _T.UNITS),
    "resolve_unit_loss_without_unit": _row(
        _V.CONFIRM_EMPTY, _S.OPPONENT, of=_V.LOSE_UNIT
    ),
    # --- Draws a trigger earned ----------------------------------------------
    "draw_owed_card": _row(_V.DRAW, _S.TRIGGER),
    "draw_owed_intrigue": _row(_V.DRAW, _S.TRIGGER, variant="intrigue"),
    # --- Arrakeen Scouts -----------------------------------------------------
    "choose_four_bonus": _row(_V.CHOOSE, _S.SCOUTS, _T.FACTION),
    # Stage B3d-2b: a target row (its turn row is the ``join`` effect row).
    "choose_subcommittee": _row(_V.CHOOSE, _S.REF, _T.SUBCOMMITTEE),
    "join_subcommittee": _row(_V.JOIN, _S.SCOUTS, _T.SUBCOMMITTEE),
    "decline_subcommittee": _row(_V.DECLINE, _S.SCOUTS, of=_V.JOIN),
    "scouts_discard": _row(_V.DISCARD, _S.SCOUTS, _T.PERSONAL_CARD),
    "scouts_trash_card": _row(_V.TRASH, _S.SCOUTS, _T.PERSONAL_CARD),
    "scouts_trash_intrigue": _row(_V.TRASH, _S.SCOUTS, _T.INTRIGUE_CARD),
    "scouts_recall_spy": _row(_V.RECALL_SPY, _S.SCOUTS, _T.POST),
    "scouts_choose_faction": _row(_V.GAIN_INFLUENCE, _S.SCOUTS, _T.FACTION),
    "scouts_recall_agent": _row(_V.RECALL_AGENT, _S.SCOUTS, _T.SPACE),
    "scouts_lose_influence": _row(_V.LOSE_INFLUENCE, _S.SCOUTS, _T.FACTION),
    "scouts_lose_influence_to": _row(
        _V.LOSE_INFLUENCE, _S.SCOUTS, _T.FACTION, variant="alliance_recipient"
    ),
    "scouts_lose_garrison_unit": _row(_V.LOSE_UNIT, _S.SCOUTS, _T.UNITS),
    "scouts_rewards_first": _row(_V.COLLECT, _S.SCOUTS, variant="rewards_first"),
    "scouts_choose_option": _row(_V.CHOOSE, _S.SCOUTS, _T.OPTION),
    "scouts_pass": _row(_V.PASS, _S.SCOUTS),
    "resolve_scouts_choice_without_option": _row(
        _V.CONFIRM_EMPTY, _S.SCOUTS, of=_V.CHOOSE
    ),
    "resolve_scouts_loss_without_influence": _row(
        _V.CONFIRM_EMPTY, _S.SCOUTS, of=_V.LOSE_INFLUENCE
    ),
    "scouts_join_mission": _row(_V.JOIN, _S.SCOUTS, _T.MISSION),
    "scouts_decline_mission": _row(
        _V.DECLINE, _S.SCOUTS, of=_V.JOIN, variant="mission"
    ),
    "scouts_collect_mission": _row(_V.COLLECT, _S.SCOUTS, _T.OPTION),
    "scouts_secret_pick": _row(_V.BID, _S.SCOUTS, _T.OPTION),
    "scouts_bid": _row(_V.BID, _S.SCOUTS, _T.COUNT),
    "scouts_call": _row(_V.BID, _S.SCOUTS, _T.COUNT, variant="call"),
    "confirm_scouts_bid": _row(_V.BID, _S.SCOUTS, variant="confirm"),
    "scouts_retreat": _row(_V.RETREAT, _S.SCOUTS, _T.UNITS),
    "scouts_take_card": _row(_V.ACQUIRE, _S.SCOUTS, _T.OPTION),
    "scouts_decline_card": _row(_V.DECLINE, _S.SCOUTS, of=_V.ACQUIRE),
    "scouts_return_specimens": _row(_V.RETURN_SPECIMEN, _S.SCOUTS, _T.COUNT),
    # --- Endgame -------------------------------------------------------------
    "match_endgame_wild_icon": _row(_V.MATCH, _S.ENDGAME, _T.WILD_ICON),
    # --- Stage B3: effect rows and target rows (``rules.effect_steps``) -----
    # An effect row is its verb; its ``source`` argument (the tag) names the
    # source and ``printed``/``icon``/``option`` the waiting effect.
    **{
        verb.value: _row(verb, _S.REF, _T.EFFECT, tag=_SOURCE)
        for verb in (
            _V.RESOLVE,
            _V.DRAW,
            _V.GAIN,
            _V.ADVANCE,
            _V.TAKE,
            _V.TRASH,
            _V.RECRUIT,
            _V.GAIN_INFLUENCE,
            _V.CHOOSE,
            _V.DISCARD,
            _V.PAY,
            _V.ACQUIRE,
            _V.PLACE_SPY,
            _V.RECALL_SPY,
            _V.RECALL_AGENT,
            _V.RETREAT,
            _V.PLACE_BONUS,
            _V.DEPLOY,
            _V.USE,
            _V.SUMMON_SANDWORM,
            _V.COLLECT,
            _V.FLIP,
            _V.DESTROY_SHIELD_WALL,
            # Stage B3b-2: the Reveal frame's effects.
            _V.EXCHANGE_INFLUENCE,
            _V.LOSE_INFLUENCE,
            _V.KEEP,
            # Stage B3c-1: playing a card, the Endgame wild match.
            _V.PLAY,
            _V.MATCH,
            # Stage B3c-2a: a research space's specimen icon.
            _V.GENERATE_SPECIMENS,
            # Stage B3d-2b: a new High Council seat's subcommittee.
            _V.JOIN,
            # Stage B3d-3: a refusal and an empty confirmation, naming the
            # effect they answer (``of``).
            _V.DECLINE,
            _V.CONFIRM_EMPTY,
            # Stage P3: the original game's Helena Richese's Manipulate
            # (an Imperium Row card set aside), once its deck has cards.
            _V.SET_ASIDE,
            # Stage P3: the original game's Bindu Suspension, which may pass
            # the turn after its draw (OQ-117).
            _V.PASS,
            # Stage P4c-2c: Sonic Snoopers' stop (the pick's own effect has
            # no target, so it keeps its effect row).
            _V.FINISH,
        )
    },
    # A target row picks one target of the effect its seat picked.
    "choose_personal_card": _row(_V.CHOOSE, _S.REF, _T.PERSONAL_CARD),
    "choose_intrigue_card": _row(_V.CHOOSE, _S.REF, _T.INTRIGUE_CARD),
    "choose_imperium_card": _row(_V.CHOOSE, _S.REF, _T.IMPERIUM_CARD),
    "choose_reserve_card": _row(_V.CHOOSE, _S.REF, _T.RESERVE_CARD),
    "choose_tleilaxu_card": _row(_V.CHOOSE, _S.REF, _T.TLEILAXU_CARD),
    "choose_post": _row(_V.CHOOSE, _S.REF, _T.POST),
    "choose_space": _row(_V.CHOOSE, _S.REF, _T.SPACE),
    "choose_track_space": _row(_V.CHOOSE, _S.REF, _T.TRACK_SPACE),
    "choose_faction": _row(_V.CHOOSE, _S.REF, _T.FACTION),
    "choose_contract": _row(_V.CHOOSE, _S.REF, _T.CONTRACT),
    "choose_tech": _row(_V.CHOOSE, _S.REF, _T.TECH),
    "choose_seat": _row(_V.CHOOSE, _S.REF, _T.UNITS),
    "choose_option": _row(_V.CHOOSE, _S.REF, _T.OPTION),
    "choose_conflict_card": _row(_V.CHOOSE, _S.REF, _T.CONFLICT_CARD),
    # Stage B3d-2a: a unit to lose, a number of units, a leader, a
    # Navigation card.
    "choose_unit": _row(_V.CHOOSE, _S.REF, _T.UNITS, variant="unit"),
    "choose_count": _row(_V.CHOOSE, _S.REF, _T.COUNT),
    "choose_leader": _row(_V.CHOOSE, _S.REF, _T.LEADER),
    "choose_navigation_card": _row(_V.CHOOSE, _S.REF, _T.NAVIGATION_CARD),
    # Stage B3d-2b: a mission's part.
    "choose_mission": _row(_V.CHOOSE, _S.REF, _T.MISSION),
})


# Stage B3: the entity that printed a waiting effect, as a frame or a
# waiting item records it -- an optional trash (``optional_trash``), the Spy
# placement window (``spy_moves``, B3d-2a): ``"<source>|<printed>"``, with
# ``"|1"`` for a grafted turn's second card. A frame keeps it under
# ``PRINTER_KEY``; ``effect_steps.Printed.WINDOW`` reads it.
PRINTER_KEY: Final = "printer"


def printer_value(source: Source, printed: str, box: int = 0) -> str:
    """The recorded value of the entity ``printed`` of ``source``."""

    return f"{source.value}|{printed}" + ("|1" if box == 1 else "")


def printer_parts(value: str) -> tuple[Source, str, int]:
    """A recorded printer's source, entity and box (``printer_value``)."""

    source, printed, *box = value.split("|")
    return Source(source), printed, 1 if box == ["1"] else 0


def action_shape(action_id: str) -> ActionShape:
    """The shape of ``action_id``; raises ``KeyError`` for an unknown id."""

    return ACTION_SHAPES[action_id]


# The executor names every row it offers through this table (once per row of
# every legal-action call), and the table is read-only.
@cache
def template_id(
    verb: Verb,
    source: Source,
    target: Target | None = None,
    *,
    of: Verb | None = None,
    variant: str = "",
) -> str:
    """The one action id that answers ``verb`` for ``source``.

    ``target`` narrows the match when given (a trash of a personal card or
    of an Intrigue card); ``of`` and ``variant`` must equal the row's. A
    row answers ``verb`` through its own verb or one of ``also``. Raises
    ``LookupError`` unless exactly one id matches, so a decision shape the
    table does not name, or names twice, stops the executor rather than
    offering a guessed id.
    """

    matches = [
        action_id
        for action_id, shape in ACTION_SHAPES.items()
        if shape.source is source
        and (shape.verb is verb or verb in shape.also)
        and (target is None or shape.target is target)
        and shape.of is of
        and shape.variant == variant
    ]
    if len(matches) != 1:
        raise LookupError(
            f"{len(matches)} templates answer {verb} for {source}"
            f" (target {target}, of {of}, variant {variant!r}): {matches}"
        )
    return matches[0]
