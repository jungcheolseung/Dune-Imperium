"""Typed resolution of implemented Uprising board-space effects.

Every printed icon of a visited space is one independently resolved effect:
the owner orders the icons freely against each other and against the card,
Faction, and Contract groups of the same Agent turn ("You may carry out all
these effects in any order" [Main p. 9]; OQ-027). Automatic icons resolve
through ``resolve_board_effect`` carrying an ``effect`` key; icons that need
a choice (a Spy post, a card to trash, a Faction) resolve through the space's
dedicated actions further down this module.
"""

from collections.abc import Mapping
from copy import replace
from typing import Final, assert_never

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.uprising.abilities import Ability
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.board_abilities import (
    BOARD_SPACE_ABILITIES,
    board_space_ability,
)
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    DrawPersonalCards,
    GainResources,
    RecruitTroops,
    Research,
    TakeContract,
    TakeHighCouncilSeat,
    TakeSwordmaster,
)
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import keep_trash_recruits, trash_personal_card
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    BOARD_ICON_COMMANDER,
    BOARD_ICON_TECH,
    OPTIONAL_BOARD_ICONS,
    AutomaticEffect,
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    OptionalBlockKind,
    OptionalEffectBlock,
    RecruitTroopsEffect,
    ResearchEffect,
    add_board_icon,
    advance_after_effect,
    board_icon_is_pending,
    current_agent_effect_context,
    finish_board_icon,
    pending_board_icons,
    recall_conflict_agent,
    recallable_conflict_agents,
    recruit_shortfall_events,
    recruit_troops,
    turn_agent_in_conflict,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    replace_player,
    top_frame_of_kind,
)
from dune_imperium.rules.immortality import advance_research
from dune_imperium.rules.influence import gain_faction_influence, influence_can_rise
from dune_imperium.rules.intrigue_deck import (
    draw_intrigue_cards,
    draw_or_queue_intrigue_cards,
    with_trashed_intrigue,
)
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.planetologist import replace_sandworms, replaces_sandworms
from dune_imperium.rules.scouts_missions import (
    BOARD_ICON_SCOUTS,
    desert_riding_token,
    maker_hooks_left_in_bank,
    mission_collectable,
    take_desert_riding_token,
)
from dune_imperium.rules.scouts_offers import BOARD_ICON_SUBCOMMITTEE
from dune_imperium.rules.shield_wall import (
    current_conflict_is_shield_wall_protected,
    destroy_shield_wall,
)
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
)

_FRAME_LABEL = "Agent-turn effect frame"

# Icon keys resolved by the generic ``resolve_board_effect`` action with
# ``effect=<key>``. Kept sorted: the action codec enumerates them.
BOARD_ICON_CARDS: Final = "cards"
BOARD_ICON_CONTRACT: Final = "contract"
BOARD_ICON_HIGH_COUNCIL: Final = "high_council"
BOARD_ICON_INTRIGUE: Final = "intrigue"
BOARD_ICON_RESOURCES: Final = "resources"
BOARD_ICON_SWORDMASTER: Final = "swordmaster"
BOARD_ICON_TROOPS: Final = "troops"
# Immortality's revised Research Station: "Draw two cards and research"
# [Immortality p. 16]; the research advance may open a direction choice.
BOARD_ICON_RESEARCH: Final = "research"
AUTOMATIC_BOARD_ICONS: Final = (
    BOARD_ICON_CARDS,
    BOARD_ICON_CONTRACT,
    BOARD_ICON_HIGH_COUNCIL,
    BOARD_ICON_INTRIGUE,
    BOARD_ICON_RESEARCH,
    BOARD_ICON_RESOURCES,
    BOARD_ICON_SWORDMASTER,
    BOARD_ICON_TROOPS,
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
# (``content.uprising.board_abilities.BOARD_CHOICE_ABILITIES``, composed A5d).
BOARD_SPACE_HOOKS: Final = frozenset(
    {
        "espionage_spy",
        "desert_tactics_trash",
        "shipping_influence",
        "imperial_privilege_trade",
        "imperial_privilege_recall",
        "sietch_tabr",
        "maker",
        "tuek_sietch",
        "secrets_steal",
    }
)

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
                case GainResources(solari=solari, spice=spice, water=water):
                    effects.append(
                        GainResourcesEffect(solari=solari, spice=spice, water=water)
                    )
                case DrawPersonalCards(count=count):
                    effects.append(DrawImperiumCardsEffect(count))
                case DrawIntrigueCards(count=count):
                    effects.append(DrawIntrigueCardsEffect(count))
                case RecruitTroops(count=count):
                    effects.append(RecruitTroopsEffect(count))
                case Research():
                    effects.append(ResearchEffect())
                case TakeHighCouncilSeat() | TakeSwordmaster() | TakeContract():
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
        case GainResourcesEffect():
            return BOARD_ICON_RESOURCES
        case DrawImperiumCardsEffect():
            return BOARD_ICON_CARDS
        case DrawIntrigueCardsEffect():
            return BOARD_ICON_INTRIGUE
        case RecruitTroopsEffect():
            return BOARD_ICON_TROOPS
        case ResearchEffect():
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
        case "swordmaster":
            icons = [BOARD_ICON_SWORDMASTER]
        case "sietch_tabr":
            icons = [BOARD_ICON_SIETCH_TABR]
        case "deep_desert" | "hagga_basin" | "imperial_basin":
            icons = [BOARD_ICON_MAKER]
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
    match _icon_effect(effects, key):
        case ResearchEffect():
            research = True
        case GainResourcesEffect() as effect:
            next_owner = _gain_resources(owner, effect)
        case DrawImperiumCardsEffect() as effect:
            personal_draw_count = effect.count
        case DrawIntrigueCardsEffect() as effect:
            intrigue_draw_count = effect.count
        case RecruitTroopsEffect() as effect:
            next_owner, recruited = recruit_troops(owner, effect.count)
            context["troops_recruited"] = (
                context_int(context, "troops_recruited", owner=_FRAME_LABEL) + recruited
            )
            recruit_shortfall = recruit_shortfall_events(
                f"{source}:{key}", player, effect.count, recruited
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
            *intrigue_events,
            *draw_events,
            *contract_events,
            *steal_events,
            event,
            *recruit_shortfall,
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
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "espionage" or not board_icon_is_pending(
        context, BOARD_ICON_SPY
    ):
        return ()

    owner = state.players[player]
    recalled = context.get("espionage_spy_recalled") is True
    # Placement needs a Spy in supply right now [Main pp. 11, 20]; a recall
    # made for Espionage may already have been consumed by another freely
    # ordered effect, so an empty supply always reopens the recall choice.
    if owner.spies_supply > 0:
        placements = tuple(
            DomainAction(
                action_id="resolve_espionage_place_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in empty_observation_post_ids(state)
        )
        if placements:
            return placements
        # Every post is taken: the icon resolves without a Spy.
        return (DomainAction(action_id="resolve_espionage_without_spy", actor=player),)

    recalls = tuple(
        DomainAction(
            action_id="recall_spy_for_espionage",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in owner.spy_post_ids
    )
    if recalled:
        return recalls
    # With an empty supply nothing has to be placed, and the recall that
    # would free a Spy is the player's choice [Main pp. 11, 20].
    return (
        DomainAction(action_id="resolve_espionage_without_spy", actor=player),
        *recalls,
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
            source=f"round:{state.round_number}:player:{action.actor}:sietch_tabr",
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
    events: list[GameEvent] = [*token_events]
    if action.action_id == "take_sietch_tabr_water_and_destroy_wall":
        destruction = destroy_shield_wall(
            effect_state,
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:shield_wall:"
                "sietch_tabr"
            ),
            source="sietch_tabr",
        )
        effect_state = destruction.state
        events.extend(destruction.events)

    finish_board_icon(context, BOARD_ICON_SIETCH_TABR)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    sietch_source = (
        f"round:{state.round_number}:player:{action.actor}:board:sietch_tabr"
    )
    events.append(
        GameEvent(
            event_id=sietch_source,
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_SIETCH_TABR),
                ("player", action.actor),
                ("space_id", "sietch_tabr"),
            ),
        )
    )
    if action.action_id == "take_sietch_tabr_supplies":
        events.extend(
            recruit_shortfall_events(sietch_source, action.actor, 1, recruited)
        )
    return RuleResult(state=next_state, events=tuple(events))


def shipping_influence_factions(owner: PlayerState) -> tuple[Faction, ...]:
    """The Factions Shipping's "Influence with a chosen Faction" offers.

    A "choose a Faction" picker never offers a Faction at the top: "합법 행동
    provider는 이미 6인 진영을 제시하지 않으므로" (OQ-060, user ruling
    2026-09-16), the gain there being lost (``influence_can_rise``). With
    every cube at 6 all four stay on offer and the gain is lost as before:
    the Agent-turn frame has no confirm for a board icon with nothing to
    pick, and Shipping's paid line still buys its 5 Solari [Board Guide
    p. 2], so OQ-071 does not withhold the space.
    """

    rising = tuple(faction for faction in Faction if influence_can_rise(owner, faction))
    return rising or tuple(Faction)


def legal_shipping_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Shipping's Faction choices for its Influence reward."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "shipping" or not board_icon_is_pending(
        context, BOARD_ICON_INFLUENCE
    ):
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


def lapse_optional_board_effects(state: GameState, player: int) -> RuleResult:
    """Lapse the visit's optional effects left unused when the turn ends.

    The owner's press of the turn's end answers every optional effect still
    unused (OQ-095 (2), user ruling 2026-10-14): the visit's optional icons
    (``effects.OPTIONAL_BOARD_ICONS``), Lady Jessica's Other Memories ("you
    may return all your memories" [Lady Jessica card]) and Reverend Mother's
    paid repeat of the printed effects ("Once during each turn" … water 1 →
    repeat [Reverend Mother Jessica card], an arrow). Each is logged.
    """

    _, context = current_agent_effect_context(state)
    space_id = context.get("space_id")
    source = f"round:{state.round_number}:player:{player}:board:{space_id}"
    events: list[GameEvent] = []
    for key in pending_board_icons(context):
        if key not in OPTIONAL_BOARD_ICONS:
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
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("space_id") != "desert_tactics" or not board_icon_is_pending(
        context, BOARD_ICON_TRASH
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="trash_card_for_desert_tactics",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in _desert_tactics_targets(state.players[player])
    )


def _desert_tactics_targets(owner: PlayerState) -> tuple[str, ...]:
    # A Row card borrowed with Usurp is not "in play" (OQ-054,
    # ``counted_in_play``), so it is no trash target.
    return (*owner.hand, *owner.discard_pile, *counted_in_play(owner))


def desert_tactics_block(state: GameState, player: int) -> OptionalEffectBlock | None:
    """Why Desert Tactics' pending optional trash offers no card, or None.

    ``legal_desert_tactics_actions`` offers one trash per card
    ``_desert_tactics_targets`` names; with none there is no card to trash.
    None when the trash is not pending for ``player``. The page greys it
    out with this (``display.unavailable``, OQ-095 (2)).
    """

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if context.get("space_id") != "desert_tactics" or not board_icon_is_pending(
        context, BOARD_ICON_TRASH
    ):
        return None
    if _desert_tactics_targets(state.players[player]):
        return None
    return OptionalEffectBlock(OptionalBlockKind.NO_CARD_TO_TRASH)


def apply_desert_tactics_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Desert Tactics' optional card trash."""

    if action not in legal_desert_tactics_actions(state, action.actor):
        raise ValueError("action is not a legal Desert Tactics choice")
    _, context = current_agent_effect_context(state)
    # The printed troop is a separate icon with its own
    # ``resolve_board_effect`` action, ordered by the owner (OQ-027).
    card_value = dict(action.arguments)["card_id"]
    if not isinstance(card_value, str):
        raise RuntimeError("Desert Tactics trash choice has invalid card ID")
    trashed = trash_personal_card(
        state,
        action.actor,
        card_value,
        source=(
            f"round:{state.round_number}:player:{action.actor}:board:desert_tactics"
        ),
    )
    # Eliminate Allies' "2 troops" lands in this AGENT_EFFECTS frame's own
    # context (``_with_recruited_troops``), which the write-back below would
    # otherwise overwrite with the box's context read before the trash,
    # discarding the credit [Main p. 10] [FAQ p. 4].
    keep_trash_recruits(context, trashed)
    effect_state = trashed.state
    events: list[GameEvent] = list(trashed.events)

    finish_board_icon(context, BOARD_ICON_TRASH)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
    events.append(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:board:"
                f"desert_tactics:{BOARD_ICON_TRASH}"
            ),
            kind="board_effect_resolved",
            payload=(
                ("action_id", action.action_id),
                ("effect", BOARD_ICON_TRASH),
                ("player", action.actor),
                ("space_id", "desert_tactics"),
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
        _imperial_privilege_context(
            state, player, BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE
        )
        is not None
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
        _imperial_privilege_context(
            state, player, BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE
        )
        is None
        or state.players[player].intrigue_cards
    ):
        return None
    return OptionalEffectBlock(OptionalBlockKind.INTRIGUE)


def _imperial_privilege_context(
    state: GameState, player: int, icon: str
) -> dict[str, ActionValue] | None:
    """``player``'s own Agent-effect context while Imperial Privilege's
    ``icon`` is pending, else None."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if context.get("space_id") != "imperial_privilege" or not board_icon_is_pending(
        context, icon
    ):
        return None
    return context


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

    context = _imperial_privilege_context(state, player, BOARD_ICON_IMPERIAL_PRIVILEGE)
    if context is None:
        return None
    owner = state.players[player]
    return (
        *(
            location
            for location in owner.agent_locations
            if location != "imperial_privilege"
        ),
        *(("conflict",) if _recallable_conflict_agents(owner, context) else ()),
    )


def _recallable_conflict_agents(
    owner: PlayerState, context: Mapping[str, ActionValue]
) -> int:
    """Count the owner's Conflict Agents Imperial Privilege may recall.

    "Recall one of your other Agents from the board" [Board Guide p. 2]
    excludes the Agent sent there this turn (docs/rules/board-spaces.md),
    and an Into the Fray Agent may be recalled only on a later turn
    (OQ-037 (d)), like every Recall Agent effect (OQ-068). See
    ``turn_agent_in_conflict`` for when this turn's Agent counts as moved.
    """

    return recallable_conflict_agents(
        owner,
        sent_this_turn=turn_agent_in_conflict(
            owner, context, "imperial_privilege"
        ),
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
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"agent_recalled:imperial_privilege:conflict"
                ),
            )
        else:
            space_value = dict(action.arguments).get("space_id")
            if not isinstance(space_value, str):
                raise RuntimeError("Imperial Privilege recall has invalid space ID")
            space_id = space_value
            next_owner = replace(
                owner,
                agents_available=owner.agents_available + 1,
                agent_locations=tuple(
                    location
                    for location in owner.agent_locations
                    if location != space_id
                ),
            )
            recall_event = GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"agent_recalled:imperial_privilege:{space_id}"
                ),
                kind="agent_recalled",
                payload=(
                    ("player", action.actor),
                    ("source", "imperial_privilege"),
                    ("space_id", space_id),
                ),
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
                event_id=source,
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
        drawn = draw_or_queue_intrigue_cards(
            effect_state, action.actor, 1, source=source
        )
        effect_state = drawn.state
        events.extend(drawn.events)

    finish_board_icon(context, BOARD_ICON_IMPERIAL_PRIVILEGE_INTRIGUE)
    next_state = advance_after_effect(effect_state, context, effect_state.players)
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
            event_id=source,
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
    event = GameEvent(
        event_id=source,
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            ("bonus_spice", bonus_spice),
            ("effect", BOARD_ICON_TUEK_SIETCH),
            ("player", action.actor),
            ("space_id", "tuek_sietch"),
            ("spice", bonus_spice + spice),
        ),
    )
    if spice:
        return RuleResult(state=next_state, events=(event,))
    drawn = draw_or_request_personal_cards(next_state, action.actor, 1, source=source)
    return RuleResult(state=drawn.state, events=(event, *drawn.events))


# The Maker spaces [Main p. 15]; Imperial Basin's printed row is spice alone
# [Board Guide p. 2], so only the other two print a sandworm choice.
MAKER_SPACE_IDS: Final = ("deep_desert", "hagga_basin", "imperial_basin")
MAKER_SANDWORM_SPACE_IDS: Final = ("deep_desert", "hagga_basin")


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
        and space_id in MAKER_SPACE_IDS
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

    owner = state.players[player]
    if not owner.maker_hooks:
        return OptionalEffectBlock(OptionalBlockKind.MAKER_HOOKS)
    if not state.current_conflict_ids:
        return OptionalEffectBlock(OptionalBlockKind.NO_CONFLICT)
    if units_deployment_blocked(state, player):
        return OptionalEffectBlock(OptionalBlockKind.DEPLOYMENT_BARRED)
    if not replaces_sandworms(owner) and current_conflict_is_shield_wall_protected(
        state
    ):
        return OptionalEffectBlock(OptionalBlockKind.SHIELD_WALL)
    return None


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
        space_id in MAKER_SANDWORM_SPACE_IDS
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


def apply_maker_space_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Collect bonus spice, then take base spice or summon sandworms."""

    if action not in legal_maker_space_actions(state, action.actor):
        raise ValueError("action is not a legal Maker-space choice")
    space_id = dict(action.arguments).get("space_id")
    if space_id not in ("deep_desert", "hagga_basin", "imperial_basin"):
        raise RuntimeError("Maker-space action has invalid space ID")
    bonus_by_space = dict(state.maker_bonus_spice)
    bonus_spice = bonus_by_space[space_id]
    owner = state.players[action.actor]
    base_spice = 0
    sandworms = 0
    replaced = 0
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
        base_spice = {
            "deep_desert": 4,
            "hagga_basin": 2,
            "imperial_basin": 1,
        }[space_id]
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + bonus_spice + base_spice,
            ),
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
    event = GameEvent(
        event_id=(f"round:{state.round_number}:player:{action.actor}:board:{space_id}"),
        kind="board_effect_resolved",
        payload=(
            ("action_id", action.action_id),
            ("bonus_spice", bonus_spice),
            ("effect", BOARD_ICON_MAKER),
            ("player", action.actor),
            ("sandworms", sandworms),
            ("space_id", space_id),
            ("spice", bonus_spice + base_spice),
        ),
    )
    if replaced:
        replacement = replace_sandworms(
            next_state,
            action.actor,
            replaced,
            source=f"round:{state.round_number}:player:{action.actor}:board:{space_id}",
        )
        return RuleResult(state=replacement.state, events=(event, *replacement.events))
    return RuleResult(state=next_state, events=(event, *token_events))


def _gain_resources(
    player: PlayerState,
    effect: GainResourcesEffect,
) -> PlayerState:
    return replace(
        player,
        resources=Resources(
            solari=player.resources.solari + effect.solari,
            spice=player.resources.spice + effect.spice,
            water=player.resources.water + effect.water,
        ),
    )
