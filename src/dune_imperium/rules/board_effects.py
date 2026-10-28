"""Typed resolution of implemented Uprising board-space effects.

Every printed icon of a visited space is one independently resolved effect:
the owner orders the icons freely against each other and against the card,
Faction, and Contract groups of the same Agent turn ("You may carry out all
these effects in any order" [Main p. 9]; OQ-027). Automatic icons resolve
through ``resolve_board_effect`` carrying an ``effect`` key; icons that need
a choice (a Spy post, a card to trash, a Faction) resolve through the space's
dedicated actions further down this module.
"""

from copy import replace
from types import MappingProxyType
from typing import Final, assert_never

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.abilities import Ability, AbilityMark
from dune_imperium.content.uprising.agent_abilities import agent_box_ability
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.board_abilities import (
    BOARD_CHOICE_ABILITIES,
    BOARD_SPACE_ABILITIES,
    board_space_ability,
)
from dune_imperium.content.uprising.effect_dsl import (
    AcquireReserveCard,
    DoubleBaseHarvestSpice,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    OnHighCouncilSeatTaken,
    OnMakerSpiceHarvested,
    PlaceSpy,
    RecallAgent,
    RecruitTroops,
    Research,
    TakeContract,
    TakeHighCouncilSeat,
    TakeMentat,
    TakeSwordmaster,
    TrashCard,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.leader_abilities import leader_triggers
from dune_imperium.content.uprising.personal_cards import PersonalCardDefinition
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import acquire_reserve_for_intrigue
from dune_imperium.rules.card_bonds import trashable_cards
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import keep_trash_recruits, trash_personal_card
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    BOARD_ICON_COMMANDER,
    BOARD_ICON_TECH,
    OPTIONAL_BOARD_ICONS,
    AutomaticEffect,
    OptionalBlockKind,
    OptionalEffectBlock,
    active_agent_card,
    add_board_icon,
    advance_after_effect,
    blocked_board_icons,
    board_icon_is_pending,
    current_agent_effect_context,
    finish_board_icon,
    mentat_rests,
    pending_board_icons,
    recall_agent_targets,
    recall_board_agent,
    recall_conflict_agent,
    recruit_shortfall_events,
    recruit_troops,
    turn_agent_in_conflict,
)
from dune_imperium.rules.frames import (
    OWED_CARD,
    FrameKind,
    context_int,
    context_str,
    hold_draw,
    replace_player,
    top_frame_of_kind,
)
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.immortality import advance_research
from dune_imperium.rules.influence import gain_faction_influence, influence_can_rise
from dune_imperium.rules.intrigue_deck import (
    draw_intrigue_cards,
    draw_or_queue_intrigue_cards,
    with_trashed_intrigue,
)
from dune_imperium.rules.planetologist import replace_sandworms, replaces_sandworms
from dune_imperium.rules.sandworms import sandworm_block
from dune_imperium.rules.scouts_missions import (
    BOARD_ICON_SCOUTS,
    desert_riding_token,
    maker_hooks_left_in_bank,
    mission_collectable,
    take_desert_riding_token,
)
from dune_imperium.rules.scouts_offers import BOARD_ICON_SUBCOMMITTEE
from dune_imperium.rules.shield_wall import destroy_shield_wall
from dune_imperium.rules.spy_placement import (
    place_spy,
    recall_spy,
    spy_options,
    spy_placement_allowed_post_ids,
)

_FRAME_LABEL = "Agent-turn effect frame"
# The original game's Foldspace Reserve card (``content.imperium.reserve``).
FOLDSPACE_CARD: Final = "foldspace_card"

# Icon keys resolved by the generic ``resolve_board_effect`` action with
# ``effect=<key>``. Kept sorted: the action codec enumerates them.
BOARD_ICON_CARDS: Final = "cards"
BOARD_ICON_CONTRACT: Final = "contract"
BOARD_ICON_HIGH_COUNCIL: Final = "high_council"
BOARD_ICON_FOLDSPACE: Final = "foldspace"
BOARD_ICON_INTRIGUE: Final = "intrigue"
BOARD_ICON_MENTAT: Final = "mentat"
# Earl Memnon Thorvald's Connections: the seat just taken's chosen Influence
# (``choose_connections_influence``), one more effect of the visit.
BOARD_ICON_CONNECTIONS: Final = "connections"
BOARD_ICON_RESOURCES: Final = "resources"
BOARD_ICON_SWORDMASTER: Final = "swordmaster"
BOARD_ICON_TROOPS: Final = "troops"
# Immortality's revised Research Station: "Draw two cards and research"
# [Immortality p. 16]; the research advance may open a direction choice.
BOARD_ICON_RESEARCH: Final = "research"
AUTOMATIC_BOARD_ICONS: Final = (
    BOARD_ICON_CARDS,
    BOARD_ICON_CONTRACT,
    BOARD_ICON_FOLDSPACE,
    BOARD_ICON_HIGH_COUNCIL,
    BOARD_ICON_INTRIGUE,
    BOARD_ICON_MENTAT,
    BOARD_ICON_RESEARCH,
    BOARD_ICON_RESOURCES,
    BOARD_ICON_SWORDMASTER,
    BOARD_ICON_TROOPS,
)
# The automatic icons only the original game's board prints: the Mentat
# space's take [DI p. 18] and the Foldspace space's acquisition [DI p. 17].
# A catalog holds their rows only with a board that prints them, so
# Uprising's rows stay what they were (docs/base-game-and-ix-plan.md 15.4).
IMPERIUM_ONLY_BOARD_ICONS: Final = frozenset({BOARD_ICON_FOLDSPACE, BOARD_ICON_MENTAT})
# The automatic icons the original board prints [DI pp. 17-18]: no Contract
# and no research (Uprising systems, docs/rules/imperium-base.md 2).
IMPERIUM_BOARD_ICONS: Final = frozenset(
    {
        BOARD_ICON_CARDS,
        BOARD_ICON_HIGH_COUNCIL,
        BOARD_ICON_INTRIGUE,
        BOARD_ICON_RESOURCES,
        BOARD_ICON_SWORDMASTER,
        BOARD_ICON_TROOPS,
        *IMPERIUM_ONLY_BOARD_ICONS,
    }
)

# Icon keys resolved through a space's dedicated choice actions.
BOARD_ICON_SPY: Final = "spy"  # Espionage: the optional Spy placement
BOARD_ICON_TRASH: Final = "trash"  # Desert Tactics: the optional card trash
BOARD_ICON_INFLUENCE: Final = "influence"  # Shipping: Influence with a chosen Faction
BOARD_ICON_SIETCH_TABR: Final = "sietch_tabr"  # one printed choose-one row
BOARD_ICON_MAKER: Final = "maker"  # bonus spice, then spice or sandworms
BOARD_ICON_IMPERIAL_PRIVILEGE: Final = "imperial_privilege"  # written sentences
# Imperial Privilege's optional Intrigue trade, "Trash an Intrigue card" ->
# an Intrigue card [Main p. 20], an arrow cost and its own icon beside the
# recall (user ruling 2026-10-14: "따로 인쇄된 효과는 따로", OQ-027 (d)).
BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE: Final = "imperial_privilege_intrigue"
BOARD_ICON_TUEK_SIETCH: Final = "tuek_sietch"  # bonus spice, then spice or a card
# ``BOARD_ICON_COMMANDER`` (Bloodlines) is defined in ``effects`` and resolved
# by ``rules.sardaukar``.

# The board flows kept as code, named by their records' ``hook``
# (``content.uprising.board_abilities.BOARD_CHOICE_ABILITIES``, composed A5d);
# the other choice icons are read off their records' lines
# (``_recorded_choice``, cleanup-2d).
BOARD_SPACE_HOOKS: Final = frozenset(
    {"sietch_tabr", "maker", "tuek_sietch", "secrets_steal"}
)


def _check_board_choice_records() -> None:
    """Every board choice record names a flow kept as code, or prints the one
    line a flow below reads off it: a Spy to place (Espionage), an optional
    trash (Desert Tactics), Influence with a chosen Faction (Shipping), an
    optional Intrigue trade (Imperial Privilege) or a recall of another
    Agent (Imperial Privilege)."""

    for (space_id, key), ability in BOARD_CHOICE_ABILITIES.items():
        if ability.hook is not None:
            if ability.hook not in BOARD_SPACE_HOOKS:
                raise ValueError(f"{space_id}: unknown board hook {ability.hook!r}")
            continue
        if len(ability.sections) != 1 or ability.sections[0].condition is not None:
            raise ValueError(f"{space_id} {key}: a recorded icon prints one plain line")
        line = ability.sections[0]
        match line.costs, line.rewards, ability.mark:
            case (), (PlaceSpy(visited_space=False),), AbilityMark.MANDATORY:
                pass
            case (), (
                TrashPersonalCard(mandatory=False, bonus_spice=0),
            ), AbilityMark.OPTIONAL:
                pass
            case (
                (TrashCard() as trash,),
                (DrawPersonalCards(),),
                AbilityMark.OPTIONAL,
            ) if trash == TrashCard():
                # Selective Breeding: any card's trash buys the draw it arms.
                pass
            case (), (
                GainInfluence(
                    times=1,
                    distinct=False,
                    where_opponent_leads=False,
                    different_from_trigger=False,
                    minimum_own=0,
                    visited_space=False,
                ),
            ), AbilityMark.MANDATORY:
                pass
            case (TrashIntrigueCard(troops_if_not_twisted=0),), (
                DrawIntrigueCards(),
            ), AbilityMark.OPTIONAL:
                pass
            case (), (RecallAgent(sent_this_turn=False),), AbilityMark.MANDATORY:
                pass
            case _:
                raise ValueError(f"{space_id} {key}: no board flow reads {line!r}")


_check_board_choice_records()


type _RecordedTrash = tuple[
    dict[str, ActionValue], str, TrashPersonalCard | TrashCard, EffectSection
]


def _recorded_trash(state: GameState, player: int) -> _RecordedTrash | None:
    """The visited space's pending optional trash (``_recorded_choice``):
    Desert Tactics' trash icon, or the arrow of the original game's Selective
    Breeding, "Trash one card to draw two cards" [DI p. 18]."""

    found = _recorded_choice(state, player, TrashPersonalCard)
    if found is not None:
        return found
    return _recorded_choice(state, player, TrashCard)


def _recorded_choice[P](
    state: GameState, player: int, piece: type[P]
) -> tuple[dict[str, ActionValue], str, P, EffectSection] | None:
    """``player``'s own Agent-effect context, then the key, the ``piece`` and
    the line of the visited space's pending choice icon whose record prints
    that piece (``_check_board_choice_records``); None when no such icon
    waits for ``player``."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    space_id = context.get("space_id")
    for key in pending_board_icons(context):
        ability = BOARD_CHOICE_ABILITIES.get((str(space_id), key))
        if ability is None or ability.hook is not None:
            continue
        line = ability.sections[0]
        for part in (*line.costs, *line.rewards):
            if isinstance(part, piece):
                return context, key, part, line
    return None

# Board spaces with at least one icon that is resolved through a dedicated
# choice rather than the generic ``resolve_board_effect`` action.
CHOICE_DRIVEN_SPACE_IDS = frozenset(
    {
        "espionage",
        "sietch_tabr",
        "deep_desert",
        "hagga_basin",
        "imperial_basin",
        "shipping",
        "desert_tactics",
        "imperial_privilege",
        "tuek_sietch",
        # The original game's.
        "imperium_hagga_basin",
        "the_great_flat",
        "selective_breeding",
    }
)

def board_effect_is_implemented(
    state: GameState,
    space_id: str,
    cost_option: int,
) -> bool:
    """Return whether an Agent may be advertised for this paid board option.

    Spaces whose printed effect still depends on unimplemented content (for
    example Intrigue-driven spaces) are withheld from legal actions so that
    every advertised action stays executable.
    """

    if space_id in CHOICE_DRIVEN_SPACE_IDS:
        return True
    try:
        board_effects_for(state, space_id, cost_option)
    except NotImplementedError:
        return False
    return True


def board_effects_for(
    state: GameState,
    space_id: str,
    cost_option: int,
) -> tuple[AutomaticEffect, ...]:
    """Return implemented automatic effects for one paid board-space option."""

    return static_board_effects(
        space_id,
        cost_option,
        choam_module=state.config.choam_module,
        immortality=state.config.immortality,
    )


def static_board_effects(
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
    immortality: bool = False,
) -> tuple[AutomaticEffect, ...]:
    """Return the printed automatic effects of one paid board-space option.

    This is the state-free table behind ``board_effects_for``; the display
    catalog reads it too, so effect text shown to players always derives from
    the same table the engine executes. Choice-driven spaces list only their
    automatic icons here (Espionage's card draw, Desert Tactics' troop,
    Shipping's Solari, Imperial Privilege's card draw); High Council's
    revisit rewards depend on the visitor
    and live in ``visit_board_effects``.
    """

    ability = board_space_ability(
        space_id, cost_option, choam_module=choam_module, immortality=immortality
    )
    if ability is None:
        raise NotImplementedError(
            f"board effect is not implemented: {space_id} option {cost_option}"
        )
    return _gains(ability)


def _gains(ability: Ability) -> tuple[AutomaticEffect, ...]:
    """A space record's gain icons, in printed order (composed A5c); the
    High Council seat, the Swordmaster and the Contract are icon keys of
    their own (``resolve_board_effect``)."""

    effects: list[AutomaticEffect] = []
    for line in ability.sections:
        if line.condition is not None or line.costs:
            raise ValueError("a board space's printed icon has no condition or cost")
        for reward in line.rewards:
            match reward:
                case (
                    GainResources()
                    | DrawPersonalCards()
                    | DrawIntrigueCards()
                    | RecruitTroops()
                    | Research()
                ):
                    effects.append(reward)
                case (
                    TakeHighCouncilSeat()
                    | TakeSwordmaster()
                    | TakeContract()
                    | TakeMentat()
                    | AcquireReserveCard()
                ):
                    pass
                case _:
                    raise TypeError(f"{reward!r} is not a board space icon")
    return tuple(effects)


# High Council after the Councilor is seated: "spice 2, Intrigue 1장, troop
# 3개" on every later visit [Board Guide p. 2] -- its record's seated line.
HIGH_COUNCIL_REVISIT_EFFECTS: Final = _gains(
    BOARD_SPACE_ABILITIES["high_council", 0, "seated"]
)
# Every space record compiles when the module loads: a record the table cannot
# read fails here, not on the first visit.
for _record in BOARD_SPACE_ABILITIES.values():
    _gains(_record)


def visit_board_effects(
    owner: PlayerState,
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
    immortality: bool = False,
) -> tuple[AutomaticEffect, ...]:
    """Return the automatic icons one visit by ``owner`` resolves."""

    if space_id == "high_council":
        return HIGH_COUNCIL_REVISIT_EFFECTS if owner.high_council else ()
    return static_board_effects(
        space_id, cost_option, choam_module=choam_module, immortality=immortality
    )


def board_icon_for_effect(effect: AutomaticEffect) -> str:
    """Return the icon key one automatic effect is resolved under."""

    match effect:
        case GainResources():
            return BOARD_ICON_RESOURCES
        case DrawPersonalCards():
            return BOARD_ICON_CARDS
        case DrawIntrigueCards():
            return BOARD_ICON_INTRIGUE
        case RecruitTroops():
            return BOARD_ICON_TROOPS
        case Research():
            return BOARD_ICON_RESEARCH
        case _:
            assert_never(effect)


def board_icons_for(
    state: GameState,
    player: int,
    space_id: str,
    cost_option: int,
) -> tuple[str, ...]:
    """Return the printed icons of one visit, in printed order.

    Each key is one independently resolved effect [Main p. 9]: automatic keys
    through ``resolve_board_effect``, the rest through the space's own choice
    actions. A printed choose-one row (Sietch Tabr, the Maker spaces' spice or
    sandworms) stays a single key, and Secrets' random steal is text that
    follows its Intrigue draw (OQ-027). Imperial Privilege's optional
    Intrigue trade, its recall and the card draw printed beside the recall
    are three keys: "소환과 뽑기가 당연히 두 단계로 나눠야지" (user ruling
    2026-10-10, OQ-027 (d)), and the optional trade no longer gates the
    recall (user ruling 2026-10-14).
    Those single printed keys still take the Bloodlines additions
    every visit gets: a waiting Sardaukar Commander [Bloodlines p. 4] and,
    on a Landsraad space, the Ixian Embassy's Acquire Tech -- a first High
    Council visit included, as in the rulebook's Brennen example
    [Bloodlines p. 7].
    """

    owner = state.players[player]
    choam_module = state.config.choam_module
    icons: list[str]
    match space_id:
        case "high_council" if not owner.high_council:
            icons = [BOARD_ICON_HIGH_COUNCIL]
        case "imperium_high_council":
            # Once per game [DI p. 17]: a seated seat cannot come back.
            icons = [BOARD_ICON_HIGH_COUNCIL]
        case "swordmaster" | "imperium_swordmaster":
            icons = [BOARD_ICON_SWORDMASTER]
        case "sietch_tabr":
            icons = [BOARD_ICON_SIETCH_TABR]
        case (
            "deep_desert"
            | "hagga_basin"
            | "imperial_basin"
            | "imperium_hagga_basin"
            | "the_great_flat"
        ):
            icons = [BOARD_ICON_MAKER]
        case "selective_breeding":
            # The two cards wait for the trash that buys them (OQ-106).
            icons = [BOARD_ICON_TRASH]
        case "foldspace":
            icons = [BOARD_ICON_FOLDSPACE]
        case "imperial_privilege":
            icons = [
                BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE,
                BOARD_ICON_IMPERIAL_PRIVILEGE,
                *(
                    board_icon_for_effect(effect)
                    for effect in visit_board_effects(
                        owner,
                        space_id,
                        cost_option,
                        choam_module=choam_module,
                        immortality=state.config.immortality,
                    )
                ),
            ]
        case "tuek_sietch":
            icons = [BOARD_ICON_TUEK_SIETCH]
        case _:
            icons = [
                board_icon_for_effect(effect)
                for effect in visit_board_effects(
                    owner,
                    space_id,
                    cost_option,
                    choam_module=choam_module,
                    immortality=state.config.immortality,
                )
            ]
            match space_id:
                case "mentat" if mentat_rests(state):
                    # "If the Mentat is here, take it" [DI p. 18].
                    icons.append(BOARD_ICON_MENTAT)
                case "espionage":
                    icons.append(BOARD_ICON_SPY)
                case "desert_tactics":
                    icons.append(BOARD_ICON_TRASH)
                case "shipping":
                    icons.append(BOARD_ICON_INFLUENCE)
                case "accept_contract" | "dutiful_service" if choam_module:
                    icons.append(BOARD_ICON_CONTRACT)
    if space_id in state.sardaukar_commander_space_ids:
        # Bloodlines: the Commander waiting on the space may be bought as
        # one more freely ordered effect of the visit [Bloodlines p. 4].
        icons.append(BOARD_ICON_COMMANDER)
    if mission_collectable(state, player, space_id):
        # Arrakeen Scouts: the visiting seat's mission pieces on the space
        # are one more effect of the visit (docs/rules/arrakeen-scouts.md 5).
        icons.append(BOARD_ICON_SCOUTS)
    if (
        state.config.tech_module
        and BOARD_SPACES_BY_ID[space_id].agent_icon is AgentIcon.LANDSRAAD
    ):
        # Tech Module: the Ixian Embassy's Acquire Tech "each time you send
        # an Agent to a Landsraad board space" [Bloodlines pp. 7, 12].
        icons.append(BOARD_ICON_TECH)
    if len(set(icons)) != len(icons):
        raise RuntimeError(f"board icons of {space_id} must be distinct: {icons}")
    return tuple(icons)


def legal_board_effect_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return one ``resolve_board_effect`` action per pending automatic icon."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    return tuple(
        DomainAction(
            action_id="resolve_board_effect",
            actor=player,
            arguments=(("effect", key),),
        )
        for key in pending_board_icons(context)
        if key in AUTOMATIC_BOARD_ICONS
        # "If the Mentat is here, take it" [DI p. 18] is judged when it
        # resolves (OQ-028): with the Mentat gone from its space -- Calculated
        # Hire took it earlier in the visit -- the icon waits and lapses at
        # the turn's end (``effects.blocked_board_icons``).
        and not (key == BOARD_ICON_MENTAT and not mentat_rests(state))
    )


def _icon_effect(
    effects: tuple[AutomaticEffect, ...],
    key: str,
) -> AutomaticEffect | None:
    return next(
        (effect for effect in effects if board_icon_for_effect(effect) == key),
        None,
    )


def _secrets_victims(state: GameState, thief: int) -> tuple[int, ...]:
    """Return opponents clockwise from ``thief`` holding 4+ Intrigue cards.

    Only HELD Intrigue counts [Board Guide p. 2, Main p. 7]; face-up trigger
    cards in ``intrigue_faceup`` are played, not held, and do not count.
    """
    players = state.config.players
    return tuple(
        seat
        for seat in ((thief + offset) % players for offset in range(1, players))
        if len(state.players[seat].intrigue_cards)
        >= (
            # Gene-Locked Vault: "can't be stolen unless you have five or
            # more" [Gene-Locked Vault Tech tile].
            5
            if has_tech(
                state.players[seat].tech_ids, TechAbility.INTRIGUE_STEAL_PROTECTION
            )
            else 4
        )
    )


def _secrets_steal_frame(
    state: GameState,
    thief: int,
    victim: int,
    options: tuple[str, ...],
) -> DecisionFrame:
    decision_id = (
        f"round:{state.round_number}:player:{thief}:board:secrets:steal:{victim}"
    )
    return DecisionFrame(
        kind=FrameKind.SECRETS_STEAL,
        frame_id=f"{decision_id}:secrets_steal",
        decision=ChanceDecision(
            decision_id=decision_id,
            prompt=f"Randomly steal one Intrigue card from player {victim}",
            options=options,
            count=1,
        ),
        context=(("thief", thief), ("victim", victim)),
    )


def secrets_steal_is_pending(state: GameState) -> bool:
    """Return whether the top decision is a Secrets random-steal chance."""

    frame = top_frame_of_kind(state, FrameKind.SECRETS_STEAL)
    return frame is not None and isinstance(frame.decision, ChanceDecision)


def apply_secrets_steal(state: GameState, outcome: ChanceOutcome) -> RuleResult:
    """Move the randomly chosen Intrigue card from victim to thief."""

    frame = top_frame_of_kind(state, FrameKind.SECRETS_STEAL)
    if frame is None or not isinstance(frame.decision, ChanceDecision):
        raise ValueError("the current chance decision is not a Secrets steal")
    context = dict(frame.context)
    owner_label = "Secrets steal frame"
    thief = context_int(context, "thief", owner=owner_label)
    victim = context_int(context, "victim", owner=owner_label)
    card_id = outcome.values[0]

    victim_state = state.players[victim]
    thief_state = state.players[thief]
    next_victim = replace(
        victim_state,
        intrigue_cards=tuple(c for c in victim_state.intrigue_cards if c != card_id),
    )
    next_thief = replace(
        thief_state, intrigue_cards=(*thief_state.intrigue_cards, card_id)
    )
    if has_tech(thief_state.tech_ids, TechAbility.INTRIGUE_DRAW_TROOP):
        # Suspensor Suits counts a stolen card like a drawn one; Secrets is
        # always the thief's own turn.
        next_thief = replace(next_thief, suspensor_owed=next_thief.suspensor_owed + 1)
    players = tuple(
        next_victim
        if candidate.player_id == victim
        else next_thief
        if candidate.player_id == thief
        else candidate
        for candidate in state.players
    )
    next_state = replace(state.pop_decision(), players=players)
    # The theft itself is public (both Intrigue counts change at the table),
    # but the stolen identity is not: Intrigue cards stay hidden from
    # opponents until played [Main p. 7], so only the thief and the victim
    # learn which card moved (OQ-010 ruling 3).
    events = (
        GameEvent(
            event_id=f"{frame.decision.decision_id}:stolen",
            kind="intrigue_card_stolen",
            payload=(("player", thief), ("victim", victim)),
        ),
        GameEvent(
            event_id=f"{frame.decision.decision_id}:stolen:identity",
            kind="intrigue_card_stolen_identity",
            payload=(("card_id", card_id), ("player", thief), ("victim", victim)),
            visible_to=(thief, victim),
        ),
    )
    return RuleResult(state=next_state, events=events)


def resolve_board_effect(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one printed icon of the visited space in the current Agent turn.

    The ``effect`` argument names the icon; the other icons of the space stay
    pending for their own actions, so the owner sequences them freely against
    each other and against the card, Faction, and Contract groups
    [Main p. 9] (OQ-027).
    """

    if action not in legal_board_effect_actions(state, action.actor):
        raise ValueError("action is not a legal board-effect resolution")
    _, context = current_agent_effect_context(state)
    player = action.actor
    space_id = context_str(context, "space_id", owner=_FRAME_LABEL)
    cost_option = context_int(context, "cost_option", owner=_FRAME_LABEL)
    key = str(dict(action.arguments)["effect"])
    owner = state.players[player]
    effects = visit_board_effects(
        owner,
        space_id,
        cost_option,
        choam_module=state.config.choam_module,
        immortality=state.config.immortality,
    )
    source = f"round:{state.round_number}:player:{player}:board:{space_id}"
    finish_board_icon(context, key)

    next_owner = owner
    personal_draw_count = 0
    intrigue_draw_count = 0
    research = False
    recruit_shortfall: tuple[GameEvent, ...] = ()
    gains: tuple[GameEvent, ...] = ()
    match _icon_effect(effects, key):
        case Research():
            research = True
        case GainResources() as effect:
            next_owner = _gain_resources(owner, effect)
            gains = (
                resources_gained_event(
                    source,
                    player,
                    solari=effect.solari,
                    spice=effect.spice,
                    water=effect.water,
                ),
            )
        case DrawPersonalCards() as effect:
            personal_draw_count = effect.count
        case DrawIntrigueCards() as effect:
            intrigue_draw_count = effect.count
        case RecruitTroops() as effect:
            next_owner, recruited = recruit_troops(owner, effect.count)
            context["troops_recruited"] = (
                context_int(context, "troops_recruited", owner=_FRAME_LABEL) + recruited
            )
            recruit_shortfall = recruit_shortfall_events(
                source, player, effect.count, recruited
            )
        case None if key == BOARD_ICON_HIGH_COUNCIL:
            next_owner = replace(owner, high_council=True)
        case None if key == BOARD_ICON_SWORDMASTER:
            if owner.swordmaster_acquired:
                raise RuntimeError("a player cannot acquire Swordmaster twice")
            next_owner = replace(
                owner,
                swordmaster_acquired=True,
                agents_available=owner.agents_available + 1,
            )
        case None if key == BOARD_ICON_CONTRACT:
            pass
        case None if key == BOARD_ICON_MENTAT:
            # "take it and place it on your Leader; this round, you may use it
            # as one of your Agents" [DI p. 18].
            if not mentat_rests(state):
                raise RuntimeError("the Mentat is not on its space")
            next_owner = replace(
                owner, mentat=True, agents_available=owner.agents_available + 1
            )
        case None if key == BOARD_ICON_FOLDSPACE:
            pass
        case _:
            raise RuntimeError(f"board icon {key} has no effect on {space_id}")

    effect_state = replace(state, players=replace_player(state.players, next_owner))
    if (
        key == BOARD_ICON_HIGH_COUNCIL
        and state.config.arrakeen_scouts
        and not owner.high_council
    ):
        # Arrakeen Scouts: the seat just taken lets the seat join one
        # still-empty subcommittee (docs/rules/arrakeen-scouts.md 4) any time
        # in this turn, one more effect of the visit in any order with the
        # others [Main p. 9] (OQ-076 alternative C, user ruling 2026-09-30).
        # Only a seat newly taken offers it: a repeat of the printed effects
        # takes no second seat. Armed even with every subcommittee taken
        # (then only its decline is offered; unreachable with four players,
        # OQ-076 (c)): "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을
        # 연다" (user ruling 2026-09-30).
        add_board_icon(context, BOARD_ICON_SUBCOMMITTEE)
    if (
        key == BOARD_ICON_HIGH_COUNCIL
        and not owner.high_council
        and leader_triggers(
            owner.leader_face_id or owner.leader_id, OnHighCouncilSeatTaken
        )
    ):
        # Connections: on taking a High Council seat, Influence with a
        # Faction of the owner's choice (docs/rules/imperium-base.md 12), one
        # more effect of the visit in any order with the others [DI p. 9].
        add_board_icon(context, BOARD_ICON_CONNECTIONS)
    intrigue_events: tuple[GameEvent, ...] = ()
    if intrigue_draw_count:
        intrigue_draw = draw_or_queue_intrigue_cards(
            effect_state,
            player,
            intrigue_draw_count,
            source=source,
        )
        effect_state = intrigue_draw.state
        intrigue_events = intrigue_draw.events
    next_state = advance_after_effect(effect_state, context)
    draw_events: tuple[GameEvent, ...] = ()
    if personal_draw_count:
        draw = draw_or_request_personal_cards(
            next_state,
            player,
            personal_draw_count,
            source=source,
        )
        next_state = draw.state
        draw_events = draw.events
    contract_events: tuple[GameEvent, ...] = ()
    if key == BOARD_ICON_FOLDSPACE:
        # "Acquire a Foldspace card from the Reserve" [DI p. 17]; with the
        # stack empty there is nothing to take.
        if dict(next_state.reserve_stacks).get(FOLDSPACE_CARD, 0) > 0:
            acquired = acquire_reserve_for_intrigue(
                next_state, player, FOLDSPACE_CARD, to_hand=False, source=source
            )
            next_state = acquired.result.state
            contract_events = acquired.result.events
    if key == BOARD_ICON_CONTRACT:
        contracts = begin_contract_gain(next_state, player, 1, source=source)
        next_state = contracts.state
        contract_events = contracts.events
    if research:
        # The advance (and any direction choice it opens) follows the
        # frame bookkeeping, like the card draw.
        advanced = advance_research(next_state, player, source=source)
        next_state = advanced.state
        contract_events = (*contract_events, *advanced.events)
    steal_events: tuple[GameEvent, ...] = ()
    if key == BOARD_ICON_INTRIGUE and space_id == "secrets":
        # The random steal is printed text that follows the Intrigue draw
        # [Board Guide p. 2], so it rides on the draw icon (OQ-027).
        victims = _secrets_victims(next_state, player)
        for victim in reversed(victims):
            next_state = next_state.push_decision(
                _secrets_steal_frame(
                    next_state,
                    player,
                    victim,
                    next_state.players[victim].intrigue_cards,
                )
            )
        if victims and next_state.pending_intrigue_draws:
            queued_player, queued_count, queued_source = (
                next_state.pending_intrigue_draws[0]
            )
            if queued_player != player or len(next_state.pending_intrigue_draws) != 1:
                raise RuntimeError("Secrets has an unexpected queued Intrigue draw")
            reshuffle = draw_intrigue_cards(
                replace(next_state, pending_intrigue_draws=()),
                queued_player,
                queued_count,
                source=queued_source,
            )
            next_state = reshuffle.state
            steal_events = reshuffle.events
    event = GameEvent(
        event_id=f"{source}:{key}",
        kind="board_effect_resolved",
        payload=(("effect", key), ("player", player), ("space_id", space_id)),
    )
    return RuleResult(
        state=next_state,
        events=(
            *gains,
            *recruit_shortfall,
            *intrigue_events,
            *draw_events,
            *contract_events,
            *steal_events,
            event,
        ),
    )


def legal_espionage_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Espionage's Spy placement, or its recall-first and skip choices.

    Placing the Spy is mandatory while a Spy is in the supply and a post is
    free: the designer's erratum to [Main p. 11] ("The word 'may' is
    incorrectly used here. It is mandatory to place a Spy if you have at
    least one Spy in your supply", Hidden Assets Discord; adopted with
    OQ-057). Only the recall that an empty supply needs first stays optional
    ("you may first recall one of your Spies" [Main pp. 11, 20]).
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    found = _recorded_choice(state, player, PlaceSpy)
    if found is None:
        return ()
    context, _, piece, _ = found

    # Placement needs a Spy in supply right now [Main pp. 11, 20]; a recall
    # made for Espionage may already have been consumed by another freely
    # ordered effect, so an empty supply reopens the recall choice. Every
    # post taken, the icon resolves without a Spy (``spy_options``).
    options = spy_options(
        state,
        player,
        spy_placement_allowed_post_ids(piece),
        shared_post=piece.shared_post,
        recalled=context.get("espionage_spy_recalled") is True,
    )
    return (
        *(
            (DomainAction(action_id="resolve_espionage_without_spy", actor=player),)
            if options.pass_up
            else ()
        ),
        *(
            DomainAction(
                action_id="recall_spy_for_espionage",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.recall
        ),
        *(
            DomainAction(
                action_id="resolve_espionage_place_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.place
        ),
    )


def apply_espionage_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Espionage, including its two-step recall-then-place branch."""

    if action not in legal_espionage_actions(state, action.actor):
        raise ValueError("action is not a legal Espionage choice")
    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    post_id = dict(action.arguments).get("post_id")

    if action.action_id == "recall_spy_for_espionage":
        if not isinstance(post_id, str):
            raise RuntimeError("Espionage recall has invalid post ID")
        next_owner = recall_spy(owner, post_id)
        context["espionage_spy_recalled"] = True
        players = tuple(
            next_owner if candidate.player_id == action.actor else candidate
            for candidate in state.players
        )
        next_state = advance_after_effect(state, context, players)
        event = GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:spy_recalled:"
                f"espionage:{post_id}"
            ),
            kind="spy_recalled",
            payload=(
                ("player", action.actor),
                ("post_id", post_id),
                ("source", "espionage"),
            ),
        )
        return RuleResult(state=next_state, events=(event,))

    next_owner = owner
    events: list[GameEvent] = []
    if action.action_id == "resolve_espionage_place_spy":
        if not isinstance(post_id, str):
            raise RuntimeError("Espionage placement has invalid post ID")
        next_owner = place_spy(next_owner, post_id)
        events.append(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:spy_placed:"
                    f"espionage:{post_id}"
                ),
                kind="spy_placed",
                payload=(
                    ("player", action.actor),
                    ("post_id", post_id),
                    ("source", "espionage"),
                ),
            )
        )

    players = tuple(
        next_owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    # The printed card draw is a separate icon with its own
    # ``resolve_board_effect`` action, ordered by the owner (OQ-027).
    finish_board_icon(context, BOARD_ICON_SPY)
    next_state = advance_after_effect(state, context, players)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:espionage:"
                f"{BOARD_ICON_SPY}"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_SPY),
                ("player", action.actor),
                ("space_id", "espionage"),
            ),
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


def pending_sietch_tabr(state: GameState, player: int) -> bool:
    """Whether ``player`` decides Sietch Tabr's unresolved choice-one row."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return False
    return context.get("space_id") == "sietch_tabr" and board_icon_is_pending(
        context, BOARD_ICON_SIETCH_TABR
    )


def sietch_tabr_wall_block(state: GameState) -> OptionalEffectBlock | None:
    """Why Sietch Tabr's "water and destroy the Shield Wall" cannot be taken.

    The branch destroys the Shield Wall, so it needs the token still on the
    board: once a detonation has destroyed it for good, the branch does
    nothing and is not offered. ``legal_sietch_tabr_actions`` offers
    ``take_sietch_tabr_water_and_destroy_wall`` exactly when this is None,
    and the page's greyed-out row reads the same block
    (``display.unavailable``). Public: the Shield Wall lies on the board.
    """

    if state.shield_wall_present:
        return None
    return OptionalEffectBlock(OptionalBlockKind.NO_SHIELD_WALL)


def legal_sietch_tabr_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Sietch Tabr's supplies or water/detonation choices."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not pending_sietch_tabr(state, player):
        return ()
    actions = [
        DomainAction(action_id="take_sietch_tabr_supplies", actor=player),
        DomainAction(action_id="take_sietch_tabr_water", actor=player),
    ]
    if sietch_tabr_wall_block(state) is None:
        actions.append(
            DomainAction(
                action_id="take_sietch_tabr_water_and_destroy_wall",
                actor=player,
            )
        )
    return tuple(actions)


def apply_sietch_tabr_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve one explicit Sietch Tabr reward branch."""

    if action not in legal_sietch_tabr_actions(state, action.actor):
        raise ValueError("action is not a legal Sietch Tabr choice")
    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    recruited = 0
    token_events: tuple[GameEvent, ...] = ()
    if (
        action.action_id == "take_sietch_tabr_supplies"
        and not owner.maker_hooks
        and maker_hooks_left_in_bank(state) <= 0
    ):
        # Desert Riding's token is one of the four Maker Hooks: when it is
        # the last, Sietch Tabr takes it (OQ-079 (e)).
        taken = take_desert_riding_token(
            state,
            action.actor,
            source=f"round:{state.round_number}:player:{action.actor}:board:sietch_tabr",
        )
        state = taken.state
        token_events = taken.events
        owner = state.players[action.actor]
    if action.action_id == "take_sietch_tabr_supplies":
        owner, recruited = recruit_troops(owner, 1)
        owner = replace(
            owner,
            resources=replace(owner.resources, water=owner.resources.water + 1),
            maker_hooks=True,
        )
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
    else:
        owner = replace(
            owner,
            resources=replace(owner.resources, water=owner.resources.water + 1),
        )

    players = tuple(
        owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    effect_state = replace(state, players=players)
    sietch_source = (
        f"round:{state.round_number}:player:{action.actor}:board:sietch_tabr"
    )
    events: list[GameEvent] = [
        *token_events,
        resources_gained_event(sietch_source, action.actor, water=1),
    ]
    if action.action_id == "take_sietch_tabr_supplies":
        events.extend(
            recruit_shortfall_events(sietch_source, action.actor, 1, recruited)
        )
    if action.action_id == "take_sietch_tabr_water_and_destroy_wall":
        destruction = destroy_shield_wall(
            effect_state,
            event_id=f"{sietch_source}:shield_wall",
            source="sietch_tabr",
        )
        effect_state = destruction.state
        events.extend(destruction.events)

    finish_board_icon(context, BOARD_ICON_SIETCH_TABR)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    events.append(
        GameEvent(
            event_id=f"{sietch_source}:{BOARD_ICON_SIETCH_TABR}",
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_SIETCH_TABR),
                ("player", action.actor),
                ("space_id", "sietch_tabr"),
            ),
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


def shipping_influence_factions(owner: PlayerState) -> tuple[Faction, ...]:
    """The Factions Shipping's "Influence with a chosen Faction" offers.

    A "choose a Faction" picker never offers a Faction at the top: "합법 행동
    provider는 이미 6인 진영을 제시하지 않으므로" (OQ-060, user ruling
    2026-09-16), the gain there being lost (``influence_can_rise``). With
    every cube at 6 it offers none: the icon waits, greyed out, and the
    turn's end lapses it (``effects.blocked_board_icons``; user decision
    2026-10-17, composed-effects plan 5, rule decision 1, which removes the
    old boundary that offered all four). Shipping's paid line still buys its
    5 Solari [Board Guide p. 2], so OQ-071 does not withhold the space.
    """

    record = BOARD_CHOICE_ABILITIES["shipping", BOARD_ICON_INFLUENCE]
    (piece,) = record.sections[0].rewards
    assert isinstance(piece, GainInfluence)
    return tuple(
        faction
        for faction in piece.factions or tuple(Faction)
        if influence_can_rise(owner, faction)
    )


def shipping_influence_pending(state: GameState, player: int) -> bool:
    """Whether ``player``'s own Agent turn at Shipping still owes its
    "Influence with a chosen Faction"."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    return _recorded_choice(state, player, GainInfluence) is not None


def legal_shipping_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Shipping's Faction choices for its Influence reward."""

    if not shipping_influence_pending(state, player):
        return ()
    return tuple(
        DomainAction(
            action_id="choose_shipping_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in shipping_influence_factions(state.players[player])
    )


def apply_shipping_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Grant Shipping's Influence with the chosen Faction."""

    if action not in legal_shipping_actions(state, action.actor):
        raise ValueError("action is not a legal Shipping choice")
    _, context = current_agent_effect_context(state)
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Shipping Influence choice has invalid Faction")
    faction = Faction(faction_value)

    # The printed 5 Solari are a separate icon with their own
    # ``resolve_board_effect`` action, ordered by the owner (OQ-027).
    gained = gain_faction_influence(
        state,
        action.actor,
        faction,
        1,
        event_prefix=(
            f"round:{state.round_number}:player:{action.actor}:board:shipping:"
            f"influence:{faction.value}"
        ),
    )

    finish_board_icon(context, BOARD_ICON_INFLUENCE)
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:board:shipping:"
            f"{BOARD_ICON_INFLUENCE}"
        ),
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            ("effect", BOARD_ICON_INFLUENCE),
            ("player", action.actor),
            ("space_id", "shipping"),
        ),
    )
    return RuleResult(state=next_state, events=(*gained.events, event))


def connections_influence_pending(state: GameState, player: int) -> bool:
    """Whether ``player``'s own Agent turn still owes Connections' Influence
    (Earl Memnon Thorvald, ``BOARD_ICON_CONNECTIONS``)."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return False
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return False
    return board_icon_is_pending(context, BOARD_ICON_CONNECTIONS)


def legal_connections_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Connections' Faction choices: never one at the top, where the gain is
    lost (OQ-060); with every cube there the icon waits and lapses at the
    turn's end (``effects.blocked_board_icons``)."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not connections_influence_pending(state, player):
        return ()
    owner = state.players[player]
    return tuple(
        DomainAction(
            action_id="choose_connections_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
        if influence_can_rise(owner, faction)
    )


def apply_connections_action(state: GameState, action: DomainAction) -> RuleResult:
    """Grant Connections' Influence with the chosen Faction."""

    if action not in legal_connections_actions(state, action.actor):
        raise ValueError("action is not a legal Connections choice")
    _, context = current_agent_effect_context(state)
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Connections' Influence choice has invalid Faction")
    faction = Faction(faction_value)
    source = f"round:{state.round_number}:player:{action.actor}:connections"
    gained = gain_faction_influence(
        state,
        action.actor,
        faction,
        1,
        event_prefix=f"{source}:influence:{faction.value}",
    )
    finish_board_icon(context, BOARD_ICON_CONNECTIONS)
    next_state = advance_after_effect(gained.state, context, gained.state.players)
    event = GameEvent(
        event_id=f"{source}:resolved",
        kind="leader_ability_resolved",
        payload=(("leader_id", "earl_memnon_thorvald"), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(*gained.events, event))


def lapse_optional_board_effects(state: GameState, player: int) -> RuleResult:
    """Lapse the visit's optional effects left unused when the turn ends.

    The owner's press of the turn's end answers every optional effect still
    unused (OQ-095 (2), user ruling 2026-10-14): the visit's optional icons
    (``effects.OPTIONAL_BOARD_ICONS``), Lady Jessica's Other Memories ("you
    may return all your memories" [Lady Jessica card]) and Reverend Mother's
    paid repeat of the printed effects ("Once during each turn" … water 1 →
    repeat [Reverend Mother Jessica card], an arrow). Each is logged. So is
    a mandatory icon that could only lapse (``blocked_board_icons``:
    Shipping's Influence with every Faction at the top).
    """

    _, context = current_agent_effect_context(state)
    space_id = context.get("space_id")
    source = f"round:{state.round_number}:player:{player}:board:{space_id}"
    events: list[GameEvent] = []
    blocked = blocked_board_icons(context, state.players[player])
    for key in pending_board_icons(context):
        if key not in OPTIONAL_BOARD_ICONS and key not in blocked:
            continue
        finish_board_icon(context, key)
        events.append(
            GameEvent(
                event_id=f"{source}:{key}:lapsed",
                kind="board_effect_lapsed",
                payload=(
                    ("effect", key),
                    ("player", player),
                    ("space_id", space_id if isinstance(space_id, str) else ""),
                ),
            )
        )
    if context.get("pending_leader_ability") is True:
        context["pending_leader_ability"] = False
        events.append(
            GameEvent(
                event_id=f"{source}:other_memories:lapsed",
                kind="leader_ability_lapsed",
                payload=(("player", player),),
            )
        )
    if context.get("pending_leader_board_repeat") is True:
        context["pending_leader_board_repeat"] = False
        events.append(
            GameEvent(
                event_id=f"{source}:board_repeat:lapsed",
                kind="leader_ability_lapsed",
                payload=(("player", player),),
            )
        )
    if not events:
        return RuleResult(state=state, events=())
    return RuleResult(state=advance_after_effect(state, context), events=tuple(events))


def legal_desert_tactics_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Desert Tactics' optional trash choices.

    The black trash icon is optional [Main p. 20]; left unused it lapses
    when the turn ends (OQ-095 (2), user ruling 2026-10-14), so no refusal
    is offered.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    found = _recorded_trash(state, player)
    if found is None:
        return ()
    _, _, piece, _ = found
    return tuple(
        DomainAction(
            action_id="trash_card_for_desert_tactics",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in trashable_cards(state.players[player], hand_only=piece.hand_only)
    )


def desert_tactics_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why Desert Tactics' pending optional trash offers no card, or None.

    ``legal_desert_tactics_actions`` offers one trash per card
    ``_desert_tactics_targets`` names; with none there is no card to trash.
    None when the trash is not pending for ``player``. The page greys it
    out with this (``display.unavailable``, OQ-095 (2)).
    """

    found = _recorded_trash(state, player)
    if found is None:
        return None
    _, _, piece, _ = found
    if trashable_cards(state.players[player], hand_only=piece.hand_only):
        return None
    return OptionalEffectBlock(OptionalBlockKind.NO_CARD_TO_TRASH)


def apply_desert_tactics_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Desert Tactics' optional card trash."""

    if action not in legal_desert_tactics_actions(state, action.actor):
        raise ValueError("action is not a legal Desert Tactics choice")
    found = _recorded_trash(state, action.actor)
    if found is None:
        raise RuntimeError("no optional board trash waits for this seat")
    _, _, _, line = found
    _, context = current_agent_effect_context(state)
    # Desert Tactics, or the original game's Selective Breeding, whose trash
    # buys its two cards: "Trash one card to draw two cards" [DI p. 18].
    space_id = context_str(context, "space_id", owner=_FRAME_LABEL)
    # The printed troop is a separate icon with its own
    # ``resolve_board_effect`` action, ordered by the owner (OQ-027).
    card_value = dict(action.arguments)["card_id"]
    if not isinstance(card_value, str):
        raise RuntimeError("Desert Tactics trash choice has invalid card ID")
    trashed = trash_personal_card(
        state,
        action.actor,
        card_value,
        source=(f"round:{state.round_number}:player:{action.actor}:board:{space_id}"),
    )
    # Eliminate Allies' "2 troops" lands in this AGENT_EFFECTS frame's own
    # context (``_with_recruited_troops``), which the write-back below would
    # otherwise overwrite with the box's context read before the trash,
    # discarding the credit [Main p. 10] [FAQ p. 4].
    keep_trash_recruits(context, trashed)
    effect_state = trashed.state
    events: list[GameEvent] = list(trashed.events)

    finish_board_icon(context, BOARD_ICON_TRASH)
    if line.costs:
        # Selective Breeding: the cards the trash bought are a step of their
        # own, the public trash first, then the hidden draw (OQ-106).
        add_board_icon(context, BOARD_ICON_CARDS)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:"
                f"{space_id}:{BOARD_ICON_TRASH}"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_TRASH),
                ("player", action.actor),
                ("space_id", space_id),
            ),
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


def legal_imperial_privilege_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Imperial Privilege's optional Intrigue trade and its recall.

    The two are separate printed effects, each its own icon, offered
    together in any order [Main p. 9] (user ruling 2026-10-14; the trade
    gated the recall before). The space prints the Trash-an-Intrigue-card
    icon and an arrow to an Intrigue card: "Trash an Intrigue card of your
    choice from your hand" [Main p. 20], optional like every arrow cost, so
    it offers no refusal: left unused it lapses when the turn ends (OQ-095
    (2)). The Board Space Guide words
    the same line "You may discard an Intrigue card to draw an Intrigue
    card" [Board Guide p. 2]. The action stays a trash, but Intrigue cards
    have no trash pile: the card joins the shared Intrigue discard and is
    reshuffled with it (``with_trashed_intrigue``, OQ-061, user ruling
    2026-10-04).

    The recall offers one action per ``imperial_privilege_recall_targets``
    entry. With none, only the recall is skipped (OQ-023), through
    ``resolve_imperial_privilege_without_recall``: the owner confirms it
    instead of the engine skipping it unasked (user ruling 2026-09-30, "결정
    창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다").

    The recall only recalls: the card draw printed beside it is the space's
    own ``cards`` icon, resolved through ``resolve_board_effect`` in any
    order with this one ("4번은 소환과 뽑기가 당연히 두 단계로 나눠야지. 이건
    정말 기본적인 원칙인데", user ruling 2026-10-10; OQ-027 (d), OQ-023's
    "별개의 효과"). A recall reveals nothing, so it can be taken back; the
    draw from the hidden deck cannot (OQ-010).
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    owner = state.players[player]
    trades: tuple[DomainAction, ...] = ()
    if (
        _recorded_choice(state, player, TrashIntrigueCard) is not None
        and imperial_privilege_trade_block(state, player) is None
    ):
        trades = tuple(
            DomainAction(
                action_id="trash_intrigue_for_imperial_privilege",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in owner.intrigue_cards
        )
    targets = imperial_privilege_recall_targets(state, player)
    if targets is None:
        return trades
    if not targets:
        return (
            *trades,
            DomainAction(
                action_id="resolve_imperial_privilege_without_recall", actor=player
            ),
        )
    return trades + tuple(
        # Duncan Idaho's Into the Fray Agent is still "one of your Agents"
        # [Board Guide p. 2]: the designer confirmed Imperial Privilege may
        # recall it from the Conflict (OQ-037(d)).
        DomainAction(
            action_id="recall_conflict_agent_for_imperial_privilege",
            actor=player,
        )
        if target == "conflict"
        else DomainAction(
            action_id="recall_agent_for_imperial_privilege",
            actor=player,
            arguments=(("space_id", target),),
        )
        for target in targets
    )


def imperial_privilege_trade_block(
    state: GameState, player: int
) -> OptionalEffectBlock | None:
    """Why Imperial Privilege's pending Intrigue trade is not offered, or None.

    "Trash an Intrigue card" -> an Intrigue card [Main p. 20]:
    ``legal_imperial_privilege_actions`` offers one trade per Intrigue card
    in hand while the trade's icon is pending, exactly when this is None.
    None when the trade is not pending for ``player``. The page greys it
    out with this (``display.unavailable``, OQ-095 (2)).
    """

    if (
        _recorded_choice(state, player, TrashIntrigueCard) is None
        or state.players[player].intrigue_cards
    ):
        return None
    return OptionalEffectBlock(OptionalBlockKind.INTRIGUE)


def imperial_privilege_recall_targets(
    state: GameState, player: int
) -> tuple[str, ...] | None:
    """Where ``player``'s pending Imperial Privilege recall may take an Agent.

    None unless the recall's icon is pending on the seat's own Agent-effect
    frame. The
    targets are the seat's other board spaces ("Recall one of your other
    Agents from the board" [Board Guide p. 2]) and "conflict" for an earlier
    turn's Into the Fray Agent (OQ-037 (d)). The provider offers one recall
    per target, or the confirm when there is none, and the page greys the
    recall out with this same answer (``display.unavailable``). Targets
    never grow within one Agent turn -- only the turn's own placement adds
    a board Agent -- so confirming as soon as none is left gives up nothing.
    """

    found = _recorded_choice(state, player, RecallAgent)
    if found is None:
        return None
    context = found[0]
    space_id = str(context["space_id"])
    owner = state.players[player]
    # "Recall one of your other Agents from the board" [Board Guide p. 2]
    # excludes the Agent sent there this turn (docs/rules/board-spaces.md),
    # and an Into the Fray Agent may be recalled only on a later turn
    # (OQ-037 (d)), like every Recall Agent effect (OQ-068).
    return recall_agent_targets(
        owner,
        excluded_space_id=space_id,
        turn_agent_in_conflict=turn_agent_in_conflict(owner, context, space_id),
    )


def apply_imperial_privilege_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Imperial Privilege's optional Intrigue trade or its recall.

    The recall (or its confirm without a target) is the icon's last step and
    draws nothing: the card draw is the space's ``cards`` icon (user ruling
    2026-10-10, OQ-027 (d)).
    """

    if action not in legal_imperial_privilege_actions(state, action.actor):
        raise ValueError("action is not a legal Imperial Privilege choice")
    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    source = (
        f"round:{state.round_number}:player:{action.actor}:board:imperial_privilege"
    )

    if action.action_id == "resolve_imperial_privilege_without_recall":
        return _resolve_imperial_privilege_without_recall(
            state, context, action.actor, source
        )

    if action.action_id in (
        "recall_agent_for_imperial_privilege",
        "recall_conflict_agent_for_imperial_privilege",
    ):
        if action.action_id == "recall_conflict_agent_for_imperial_privilege":
            # Into the Fray's Agent leaves the Conflict as a unit and returns
            # to the Leader (OQ-037(d), OQ-068); the running strength
            # follows (``recall_conflict_agent``). One recall brings back one
            # Agent, even when a Servo-Receivers Signet sent a second one
            # (OQ-037(e)).
            space_id = "conflict"
            next_owner, recall_event = recall_conflict_agent(
                owner,
                player=action.actor,
                source="imperial_privilege",
                event_id=f"{source}:agent_recalled:conflict",
            )
        else:
            space_value = dict(action.arguments).get("space_id")
            if not isinstance(space_value, str):
                raise RuntimeError("Imperial Privilege recall has invalid space ID")
            space_id = space_value
            next_owner, recall_event = recall_board_agent(
                owner,
                space_id,
                player=action.actor,
                source="imperial_privilege",
                event_id=f"{source}:agent_recalled:{space_id}",
            )
        players = tuple(
            next_owner if candidate.player_id == action.actor else candidate
            for candidate in state.players
        )
        finish_board_icon(context, BOARD_ICON_IMPERIAL_PRIVILEGE)
        # The recall alone: the card draw is the space's own ``cards`` icon
        # (user ruling 2026-10-10, OQ-027 (d)).
        next_state = advance_after_effect(state, context, players)
        recall_events = (
            recall_event,
            GameEvent(
                event_id=f"{source}:{BOARD_ICON_IMPERIAL_PRIVILEGE}",
                kind="board_effect_resolved",
                payload=(
                    ("action_id", action.action_id),
                    ("effect", BOARD_ICON_IMPERIAL_PRIVILEGE),
                    ("player", action.actor),
                    ("space_id", "imperial_privilege"),
                ),
            ),
        )
        return RuleResult(state=next_state, events=recall_events)

    effect_state = state
    events: list[GameEvent] = []
    if action.action_id == "trash_intrigue_for_imperial_privilege":
        card_id = dict(action.arguments).get("card_id")
        if not isinstance(card_id, str):
            raise RuntimeError("Imperial Privilege trash has invalid card ID")
        trashing_owner = replace(
            owner,
            intrigue_cards=tuple(
                held for held in owner.intrigue_cards if held != card_id
            ),
        )
        # The trashed card joins the Intrigue discard before the draw, so an
        # empty deck's reshuffle can bring it straight back (OQ-061, user
        # ruling 2026-10-04).
        effect_state = with_trashed_intrigue(
            replace(
                state,
                players=tuple(
                    trashing_owner if candidate.player_id == action.actor else candidate
                    for candidate in state.players
                ),
            ),
            card_id,
        )
        events.append(
            GameEvent(
                event_id=f"{source}:intrigue_trashed:{card_id}",
                kind="intrigue_card_trashed",
                payload=(("card_id", card_id), ("player", action.actor)),
            )
        )
        found = _recorded_choice(state, action.actor, TrashIntrigueCard)
        assert found is not None
        draws = sum(
            reward.count
            for reward in found[3].rewards
            if isinstance(reward, DrawIntrigueCards)
        )
        drawn = draw_or_queue_intrigue_cards(
            effect_state, action.actor, draws, source=source
        )
        effect_state = drawn.state
        events.extend(drawn.events)

    finish_board_icon(context, BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    events.append(
        GameEvent(
            event_id=f"{source}:{BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE}",
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE),
                ("player", action.actor),
                ("space_id", "imperial_privilege"),
            ),
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


def _resolve_imperial_privilege_without_recall(
    state: GameState,
    context: dict[str, ActionValue],
    player: int,
    source: str,
) -> RuleResult:
    """Confirm the skipped recall when no other Agent can be recalled (OQ-023)."""

    # With no other deployed Agent only the recall is skipped; the card
    # draw is a separate printed effect (OQ-023 decided ruling, [Board Guide
    # p. 2]) and its own ``cards`` icon, which still waits for its action
    # if it has not resolved yet (user ruling 2026-10-10, OQ-027 (d)).
    finish_board_icon(context, BOARD_ICON_IMPERIAL_PRIVILEGE)
    next_state = advance_after_effect(state, context, state.players)
    events = (
        GameEvent(
            event_id=f"{source}:recall_skipped",
            kind="imperial_privilege_recall_skipped",
            payload=(("player", player),),
        ),
        GameEvent(
            event_id=f"{source}:{BOARD_ICON_IMPERIAL_PRIVILEGE}",
            kind="board_effect_resolved",
            payload=(
                ("action_id", "resolve_imperial_privilege_without_recall"),
                ("effect", BOARD_ICON_IMPERIAL_PRIVILEGE),
                ("player", player),
                ("space_id", "imperial_privilege"),
            ),
        ),
    )
    return RuleResult(state=next_state, events=events)


def legal_tuek_sietch_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Tuek's Sietch: take the bonus spice, then one spice or one card."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "tuek_sietch" or not board_icon_is_pending(
        context, BOARD_ICON_TUEK_SIETCH
    ):
        return ()
    return (
        DomainAction(action_id="take_tuek_sietch_spice", actor=player),
        DomainAction(action_id="take_tuek_sietch_card", actor=player),
    )


def apply_tuek_sietch_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Tuek's Sietch: bonus spice plus the chosen printed reward."""

    if action not in legal_tuek_sietch_actions(state, action.actor):
        raise ValueError("action is not a legal Tuek's Sietch choice")
    _, context = current_agent_effect_context(state)
    bonus_by_space = dict(state.maker_bonus_spice)
    bonus_spice = bonus_by_space.get("tuek_sietch", 0)
    owner = state.players[action.actor]
    spice = 1 if action.action_id == "take_tuek_sietch_spice" else 0
    owner = replace(
        owner,
        resources=replace(
            owner.resources, spice=owner.resources.spice + bonus_spice + spice
        ),
    )
    players = replace_player(state.players, owner)
    maker_bonus_spice = tuple(
        (candidate, 0 if candidate == "tuek_sietch" else amount)
        for candidate, amount in state.maker_bonus_spice
    )
    finish_board_icon(context, BOARD_ICON_TUEK_SIETCH)
    effect_state = replace(state, players=players, maker_bonus_spice=maker_bonus_spice)
    next_state = advance_after_effect(effect_state, context, players)
    source = f"round:{state.round_number}:player:{action.actor}:board:tuek_sietch"
    gains = (
        (resources_gained_event(source, action.actor, spice=bonus_spice + spice),)
        if bonus_spice + spice
        else ()
    )
    event = GameEvent(
        event_id=f"{source}:{BOARD_ICON_TUEK_SIETCH}",
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            *((("bonus_spice", bonus_spice),) if bonus_spice else ()),
            ("effect", BOARD_ICON_TUEK_SIETCH),
            ("player", action.actor),
            ("space_id", "tuek_sietch"),
        ),
    )
    if spice:
        return RuleResult(state=next_state, events=(*gains, event))
    drawn = draw_or_request_personal_cards(next_state, action.actor, 1, source=source)
    return RuleResult(state=drawn.state, events=(*gains, *drawn.events, event))


def _printed_maker_spice(space_id: str) -> int:
    """The spice an original Maker space's record prints beside its bonus."""

    return sum(
        reward.spice
        for line in BOARD_CHOICE_ABILITIES[(space_id, BOARD_ICON_MAKER)].sections
        for reward in line.rewards
        if isinstance(reward, GainResources)
    )


# The spice each Maker space prints beside its bonus spice: Uprising's
# [Board Guide pp. 1-2] (Imperial Basin's 1 is the original board's too), and
# the original game's Hagga Basin and The Great Flat from their records
# [DI p. 17] [FAQ p. 1].
MAKER_BASE_SPICE: Final = MappingProxyType(
    {
        "deep_desert": 4,
        "hagga_basin": 2,
        "imperial_basin": 1,
        **{
            space_id: _printed_maker_spice(space_id)
            for space_id in ("imperium_hagga_basin", "the_great_flat")
        },
    }
)


# The Maker spaces [Main p. 15]; Imperial Basin's printed row is spice alone
# [Board Guide p. 2], so only the other two print a sandworm choice.
def pending_maker_space(state: GameState, player: int) -> str | None:
    """The Maker space whose spice-or-sandworm choice ``player`` has pending.

    None unless ``player`` decides the Agent turn's effect frame of a Maker
    space whose icon is still unresolved.
    """

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    space_id = context.get("space_id")
    if (
        isinstance(space_id, str)
        and space_id in content_for(state.config).maker_space_ids
        and board_icon_is_pending(context, BOARD_ICON_MAKER)
    ):
        return space_id
    return None


def maker_sandworm_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why a Maker space's sandworm choice cannot be taken now, or None.

    Deep Desert and Hagga Basin print "with Maker Hooks, summon sandworms"
    [Board Guide pp. 1-2]: it needs Maker Hooks, a Conflict to deploy into
    (a summoned sandworm is immediately deployed [Main p. 20], so Emperor of
    the Known Universe's deployment ban withholds it) and no Shield Wall
    protecting that Conflict -- except that Arrakis Planetologist replaces
    the sandworms "even when the Conflict is protected by the Shield Wall"
    [Liet Kynes card]. Checked in that order.
    ``legal_maker_space_actions`` offers ``summon_maker_sandworms`` at Deep
    Desert and Hagga Basin exactly when this is None, and the page's
    greyed-out row reads the same block (``display.unavailable``). Every
    input is public.
    """

    reason = sandworm_block(state, player)
    return None if reason is None else OptionalEffectBlock(OptionalBlockKind(reason))


def desert_riding_offered_at(state: GameState, space_id: str) -> bool:
    """Whether Arrakeen Scouts' Desert Riding token is on offer at ``space_id``.

    The token waits beside Hagga Basin until a visitor takes it in place of
    the space's own 2 spice (docs/rules/arrakeen-scouts.md 5).
    """

    return space_id == "hagga_basin" and desert_riding_token(state) is not None


def desert_riding_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why ``player`` cannot take the Desert Riding token, or None.

    The token is one of the four Maker Hooks, and a seat holding Maker Hooks
    gets no second one [Main p. 20] (OQ-079 (b)). ``legal_maker_space_actions``
    offers ``take_desert_riding_hooks`` where ``desert_riding_offered_at``
    exactly when this is None, and the page's greyed-out row reads the same
    block (``display.unavailable``).
    """

    if state.players[player].maker_hooks:
        return OptionalEffectBlock(OptionalBlockKind.MAKER_HOOKS_HELD)
    return None


def legal_maker_space_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return spice and any legal sandworm choices for a Maker space."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    space_id = pending_maker_space(state, player)
    if space_id is None:
        return ()
    actions = [
        DomainAction(
            action_id="harvest_maker_spice",
            actor=player,
            arguments=(("space_id", space_id),),
        )
    ]
    if (
        desert_riding_offered_at(state, space_id)
        # Arrakeen Scouts' Desert Riding: the token in place of the space's
        # own 2 spice (docs/rules/arrakeen-scouts.md 5); a seat holding Maker
        # Hooks gets no second one [Main p. 20] (OQ-079).
        and desert_riding_block(state, player) is None
    ):
        actions.append(
            DomainAction(
                action_id="take_desert_riding_hooks",
                actor=player,
                arguments=(("space_id", space_id),),
            )
        )
    if (
        space_id in content_for(state.config).sandworm_space_ids
        and maker_sandworm_block(state, player) is None
    ):
        actions.append(
            DomainAction(
                action_id="summon_maker_sandworms",
                actor=player,
                arguments=(("space_id", space_id),),
            )
        )
    return tuple(actions)


def _doubles_base_harvest(card: PersonalCardDefinition) -> bool:
    """Whether the card's Agent box doubles the base spice of its harvest."""

    ability = agent_box_ability(card.agent_effect)
    return ability is not None and any(
        isinstance(reward, DoubleBaseHarvestSpice)
        for line in ability.sections
        for reward in line.rewards
    )


def apply_maker_space_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Collect bonus spice, then take base spice or summon sandworms."""

    if action not in legal_maker_space_actions(state, action.actor):
        raise ValueError("action is not a legal Maker-space choice")
    space_id = dict(action.arguments).get("space_id")
    if not isinstance(space_id, str) or space_id not in MAKER_BASE_SPICE:
        raise RuntimeError("Maker-space action has invalid space ID")
    bonus_by_space = dict(state.maker_bonus_spice)
    bonus_spice = bonus_by_space[space_id]
    owner = state.players[action.actor]
    # The card whose Agent made this visit: a box that is a modifier of the
    # harvest rather than a step (Carryall) is read off it. A grafted
    # partner's own modifier is for the combinations stage (P7).
    context_card = active_agent_card(current_agent_effect_context(state)[1])
    base_spice = 0
    sandworms = 0
    replaced = 0
    addict = False
    token_events: tuple[GameEvent, ...] = ()
    if action.action_id == "take_desert_riding_hooks":
        # The token replaces the base spice; the bonus spice still comes
        # (docs/rules/arrakeen-scouts.md 5). It is this visit's one choice of
        # the printed row, so no sandworm follows (OQ-079 (d)).
        taken = take_desert_riding_token(
            state,
            action.actor,
            source=f"round:{state.round_number}:player:{action.actor}:board:{space_id}",
        )
        state = taken.state
        token_events = taken.events
        owner = state.players[action.actor]
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + bonus_spice,
            ),
        )
    elif action.action_id == "harvest_maker_spice":
        base_spice = MAKER_BASE_SPICE[space_id]
        if _doubles_base_harvest(context_card):
            # Carryall: "Double the base (not bonus) spice you harvest with
            # this Agent" -- the printed base only [FAQ p. 1]; the bonus spice
            # below stays as it is. Doubled before Spice Addict's one less
            # (imperium-base.md 16: Countess Ariana's -1 comes off the total).
            base_spice *= 2
        face = owner.leader_face_id or owner.leader_id
        addict = bool(leader_triggers(face, OnMakerSpiceHarvested))
        if addict:
            # Spice Addict: a Maker space's harvest -- only there, never
            # optional [FAQ p. 2] -- yields 1 spice less and a card
            # (docs/rules/imperium-base.md 12); every original Maker space
            # prints at least 1 spice [FAQ p. 1]. The card is its own step
            # after the public harvest (OQ-106).
            base_spice -= 1
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + bonus_spice + base_spice,
            ),
        )
        if addict:
            owner = hold_draw(
                owner,
                OWED_CARD,
                "spice_addict",
                f"round:{state.round_number}:player:{action.actor}:spice_addict",
            )
    elif replaces_sandworms(owner):
        replaced = 2 if space_id == "deep_desert" else 1
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + bonus_spice,
            ),
        )
    else:
        sandworms = 2 if space_id == "deep_desert" else 1
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + bonus_spice,
            ),
            sandworms_conflict=owner.sandworms_conflict + sandworms,
            units_deployed_turn=owner.units_deployed_turn + sandworms,
        )

    players = tuple(
        owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    maker_bonus_spice = tuple(
        (candidate, 0 if candidate == space_id else amount)
        for candidate, amount in state.maker_bonus_spice
    )
    _, context = current_agent_effect_context(state)
    finish_board_icon(context, BOARD_ICON_MAKER)
    effect_state = replace(
        state,
        players=players,
        maker_bonus_spice=maker_bonus_spice,
    )
    next_state = advance_after_effect(effect_state, context, players)
    source = f"round:{state.round_number}:player:{action.actor}:board:{space_id}"
    gains = (
        (resources_gained_event(source, action.actor, spice=bonus_spice + base_spice),)
        if bonus_spice + base_spice
        else ()
    )
    event = GameEvent(
        event_id=f"{source}:{BOARD_ICON_MAKER}",
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            *((("bonus_spice", bonus_spice),) if bonus_spice else ()),
            ("effect", BOARD_ICON_MAKER),
            ("player", action.actor),
            *((("sandworms", sandworms),) if sandworms else ()),
            ("space_id", space_id),
        ),
    )
    if addict:
        gains = (
            *gains,
            GameEvent(
                event_id=f"{source}:spice_addict",
                kind="leader_ability_resolved",
                payload=(
                    ("leader_id", "countess_ariana_thorvald"),
                    ("player", action.actor),
                ),
            ),
        )
    if replaced:
        replacement = replace_sandworms(
            next_state, action.actor, replaced, source=source
        )
        return RuleResult(
            state=replacement.state, events=(*gains, *replacement.events, event)
        )
    return RuleResult(state=next_state, events=(*token_events, *gains, event))


def _gain_resources(
    player: PlayerState,
    effect: GainResources,
) -> PlayerState:
    return replace(
        player,
        resources=Resources(
            solari=player.resources.solari + effect.solari,
            spice=player.resources.spice + effect.spice,
            water=player.resources.water + effect.water,
        ),
    )
