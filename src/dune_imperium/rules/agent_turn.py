"""Legal action enumeration and placement for an Uprising Agent turn."""

from copy import replace
from typing import Final

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    BoardSpace,
    DynamicCost,
    Faction,
    InfluenceRequirement,
    ResourceCost,
)
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    GainResources,
    OnAgentSentTo,
    OnBoardSpaceSolariPaid,
)
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.leader_abilities import leader_triggers
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    card_is_graft,
    card_is_usurp,
    card_sends_agent_anywhere,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
    PersonalCardTurnStartEffect,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import (
    AGENT_CARD_PICK_GRAFT_KEY,
    AGENT_CARD_PICK_KEY,
)
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.agent_box_abilities import box_ability, opens_at_placement
from dune_imperium.rules.agent_effects import (
    agent_card_icons_at_placement,
    holds_space_influence,
)
from dune_imperium.rules.agent_icons import (
    card_is_boosted,
    effective_agent_icons,
    is_bond_partner,
)
from dune_imperium.rules.board_effects import (
    board_effect_is_implemented,
    board_icons_for,
)
from dune_imperium.rules.board_table import board_spaces_on_table
from dune_imperium.rules.card_draw import (
    draw_or_request_personal_cards,
)
from dune_imperium.rules.combat_deployment import (
    UNGAINED_UNDEPLOYABLE_KEY,
    ungained_undeployable_troops,
)
from dune_imperium.rules.contracts import contract_candidates_for_agent_turn
from dune_imperium.rules.dreadnoughts import space_controller
from dune_imperium.rules.effects import (
    BOOST_DRAW_KEY,
    BOOSTED_CARDS_KEY,
    open_next_turn,
)
from dune_imperium.rules.frames import (
    COMMANDERS_RECRUITED_KEY,
    DREADNOUGHTS_COMMISSIONED_KEY,
    OWED_CARD,
    SHIPPING_TROOPS_KEY,
    TECH_ACQUIRE_PENDING_KEY,
    UNGAINED_SHIPPING_TROOPS_KEY,
    FrameKind,
    commissioned_dreadnought_count,
    hold_draw,
    owned_top_frame,
    recruited_commander_count,
    replace_player,
    replace_top_frame,
    shipping_troop_count,
    turn_start_is_open,
    ungained_shipping_troop_count,
    with_context,
)
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.leader_abilities import (
    apply_smuggle_spice,
    leader_signet_is_implemented,
)
from dune_imperium.rules.scouts_modifiers import (
    ignores_influence_requirements_this_round,
    space_is_combat,
)

# Stage B1 (docs/stage-b-plan.md 3a, OQ-111): an Agent turn is a card pick
# (``choose_agent_card``), then a space pick (``place_agent``) -- in the
# real game one motion, "reveal a card from your hand and send an Agent to a
# board space matching one of its Agent icons" [Main p. 9]. The pick waits
# in the turn frame's context, which no other seat's view shows; only a card
# (with its graft choice) that has a placement can be picked, and while the
# pick waits only its placements are offered, so no pick leads nowhere. The
# placements themselves are the card-and-space combinations below
# (``legal_agent_actions``), which the space pick names without the card.
CARD_PICK_ACTION: Final = "choose_agent_card"
SPACE_PICK_ACTION: Final = "place_agent"
# The placement arguments that belong to the card pick.
_CARD_PICK_ARGUMENTS: Final = frozenset({"card_id", "graft"})


def agent_card_pick(state: GameState, player: int) -> tuple[str, bool] | None:
    """The card (and whether it is grafted) ``player`` picked for the Agent
    turn and has not placed yet, or None."""

    frame = owned_top_frame(state, FrameKind.TURN, player)
    if frame is None:
        return None
    context = dict(frame.context)
    card = context.get(AGENT_CARD_PICK_KEY)
    if not isinstance(card, str):
        return None
    return card, context.get(AGENT_CARD_PICK_GRAFT_KEY) is True


def agent_card_pick_actions(
    player: int, placements: tuple[DomainAction, ...]
) -> tuple[DomainAction, ...]:
    """One card pick per (card, graft) that has a placement, in hand order."""

    picks: dict[tuple[str, bool], None] = {}
    for placement in placements:
        arguments = dict(placement.arguments)
        card = arguments["card_id"]
        assert isinstance(card, str)
        picks.setdefault((card, arguments.get("graft") is True), None)
    return tuple(
        DomainAction(
            action_id=CARD_PICK_ACTION,
            actor=player,
            arguments=(("card_id", card), *((("graft", True),) if graft else ())),
        )
        for card, graft in picks
    )


def agent_space_pick_actions(
    player: int, placements: tuple[DomainAction, ...], card: str, graft: bool
) -> tuple[DomainAction, ...]:
    """The picked card's placements, named without the card."""

    actions: list[DomainAction] = []
    for placement in placements:
        arguments = dict(placement.arguments)
        if arguments["card_id"] != card or (arguments.get("graft") is True) != graft:
            continue
        actions.append(
            DomainAction(
                action_id=SPACE_PICK_ACTION,
                actor=player,
                arguments=tuple(
                    item
                    for item in placement.arguments
                    if item[0] not in _CARD_PICK_ARGUMENTS
                ),
            )
        )
    return tuple(actions)


def apply_agent_card_pick(state: GameState, action: DomainAction) -> RuleResult:
    """Keep the picked card in the turn frame; only its seat sees it."""

    player = action.actor
    frame = owned_top_frame(state, FrameKind.TURN, player)
    if frame is None or agent_card_pick(state, player) is not None:
        raise ValueError("no Agent card can be picked now")
    arguments = dict(action.arguments)
    card = arguments.get("card_id")
    if not isinstance(card, str):
        raise ValueError("an Agent card pick names its card")
    graft = arguments.get("graft") is True
    context = dict(frame.context)
    context[AGENT_CARD_PICK_KEY] = card
    if graft:
        context[AGENT_CARD_PICK_GRAFT_KEY] = True
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{player}:agent_card_pick",
        kind="agent_card_picked",
        payload=(
            ("card_id", card),
            *((("graft", True),) if graft else ()),
            ("player", player),
        ),
        visible_to=(player,),
    )
    return RuleResult(
        state=replace_top_frame(state, with_context(frame, context)), events=(event,)
    )


def apply_agent_space_pick(state: GameState, action: DomainAction) -> RuleResult:
    """Place the Agent for the picked card: the pick and the space make the
    card-and-space placement ``apply_agent_action`` commits."""

    player = action.actor
    pick = agent_card_pick(state, player)
    frame = owned_top_frame(state, FrameKind.TURN, player)
    if pick is None or frame is None:
        raise ValueError("no Agent card is waiting for its space")
    card, graft = pick
    context = dict(frame.context)
    context.pop(AGENT_CARD_PICK_KEY)
    context.pop(AGENT_CARD_PICK_GRAFT_KEY, None)
    unpicked = replace_top_frame(state, with_context(frame, context))
    placement = DomainAction(
        action_id="agent_turn",
        actor=player,
        arguments=tuple(
            sorted(
                (
                    *action.arguments,
                    ("card_id", card),
                    *((("graft", True),) if graft else ()),
                )
            )
        ),
    )
    return apply_agent_action(unpicked, placement)


# The last ``executable_placements`` answer, for the very same state object:
# the engine lists a decision's card picks from it and an agent that weighs
# whole placements (``agents.agent_turn_steps``) asks again for that state.
# The entry holds its state, so the identity test cannot match another one.
_last_placements: (
    tuple[GameState, int, str | None, tuple[DomainAction, ...]] | None
) = None


def executable_placements(
    state: GameState, player: int, card: str | None = None
) -> tuple[DomainAction, ...]:
    """The seat's legal Agent placements (``card`` alone, when given), less
    those whose board effect or Signet Ring is not implemented yet: what the
    Agent turn's card and space picks are made of (stage B1)."""

    global _last_placements
    last = _last_placements
    if last is not None and last[0] is state and last[1:3] == (player, card):
        return last[3]
    placements = (
        legal_agent_actions(state, player)
        if card is None
        else legal_agent_actions_for_card(state, player, card)
    )
    found = tuple(
        action for action in placements if _agent_action_is_executable(state, action)
    )
    _last_placements = (state, player, card, found)
    return found


def _agent_action_is_executable(state: GameState, action: DomainAction) -> bool:
    arguments = dict(action.arguments)
    card_id = arguments["card_id"]
    space_id = arguments["space_id"]
    if not isinstance(card_id, str) or not isinstance(space_id, str):
        return False
    if personal_card_for_instance(
        card_id
    ).agent_effect is PersonalCardAgentEffect.LEADER_SIGNET and not (
        leader_signet_is_implemented(state.players[action.actor].leader_id)
    ):
        return False
    requested_option = arguments.get("cost_option")
    if isinstance(requested_option, int) and not isinstance(requested_option, bool):
        cost_option = requested_option
    elif BOARD_SPACES_BY_ID[space_id].dynamic_cost is DynamicCost.SWORDMASTER:
        cost_option = int(any(player.swordmaster_acquired for player in state.players))
    else:
        cost_option = 0
    return board_effect_is_implemented(state, space_id, cost_option)


def legal_agent_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Enumerate card-and-space pairs currently legal for ``player``.

    Occupied spaces, Agent-icon access, printed costs, and printed Influence
    requirements are enforced here. Infiltrate is handled as a distinct form of
    an Agent action because it must also identify the Spy being recalled.
    """

    owner = _placing_owner(state, player)
    if owner is None:
        return ()
    actions: list[DomainAction] = []
    for card_instance_id in owner.hand:
        actions.extend(
            _placements_for_hand_card(state, player, owner, card_instance_id)
        )
    return tuple(actions)


def legal_agent_actions_for_card(
    state: GameState, player: int, card_instance_id: str
) -> tuple[DomainAction, ...]:
    """Enumerate the placements of one hand card.

    Exactly the actions of ``legal_agent_actions`` that name
    ``card_instance_id``: the full set is the concatenation of every hand
    card's placements, so membership in this tuple is membership in the full
    set. ``apply_agent_action`` validates with it instead of re-enumerating
    every card (the second enumeration was 5-6% of a heuristic game,
    docs/evaluation/throughput-2026-09-10.md section 7).
    """

    owner = _placing_owner(state, player)
    if owner is None or card_instance_id not in owner.hand:
        return ()
    return _placements_for_hand_card(state, player, owner, card_instance_id)


def _placing_owner(state: GameState, player: int) -> PlayerState | None:
    """Return the seat when it may place an Agent now, else ``None``: an
    Agent on its Leader, or Kwisatz Haderach in hand with one of its Agents
    on the board ("Agent가 남지 않아도 낼 수 있다(이미 칸에 있는 Agent를
    보낸다)", docs/rules/imperium-base.md 13.1 [DI p. 13])."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return None
    if owned_top_frame(state, FrameKind.TURN, player) is None:
        return None
    owner = state.players[player]
    if owner.agents_available == 0 and not (
        owner.agent_locations
        and any(
            card_sends_agent_anywhere(personal_card_for_instance(card_id))
            for card_id in owner.hand
        )
    ):
        return None
    return owner


def _placements_for_hand_card(
    state: GameState,
    player: int,
    owner: PlayerState,
    card_instance_id: str,
) -> tuple[DomainAction, ...]:
    card = personal_card_for_instance(card_instance_id)
    anywhere = card_sends_agent_anywhere(card)
    if owner.agents_available == 0 and not anywhere:
        # Only Kwisatz Haderach sends an Agent already on the board.
        return ()
    # Immortality Graft [Immortality p. 10]: a Graft card "can't be
    # played alone. You must play two cards"; a plain card may join a
    # Graft partner. The partner is chosen after the placement.
    # Usurp may graft with an Imperium Row card instead [card face].
    # Kwisatz Haderach is never grafted nor a partner (``graft_partner_exists``,
    # ``graft.legal_graft_partner_actions``): the original game takes
    # Immortality from stage P7 (``setup._IMPERIUM_PENDING_OPTIONS``).
    may_graft = (
        state.config.immortality
        and not anywhere
        and (
            graft_partner_exists(owner, card_instance_id)
            or (card_is_usurp(card) and bool(state.imperium_row))
        )
    )
    graft_variants: tuple[bool, ...] = (
        *(() if card_is_graft(card) else (False,)),
        *((True,) if may_graft else ()),
    )
    actions: list[DomainAction] = []
    for graft in graft_variants:
        actions.extend(
            _placements_for_card(state, player, owner, card_instance_id, card, graft)
        )
    return tuple(actions)


def graft_partner_exists(owner: PlayerState, card_instance_id: str) -> bool:
    """Return whether the hand holds a card that may be grafted to this one
    (never Kwisatz Haderach, whose graft waits for stage P7)."""

    card = personal_card_for_instance(card_instance_id)
    return any(
        other_id != card_instance_id
        and not card_sends_agent_anywhere(personal_card_for_instance(other_id))
        and (card_is_graft(card) or card_is_graft(personal_card_for_instance(other_id)))
        for other_id in owner.hand
    )


def _infiltrator_may_join(owner: PlayerState) -> bool:
    """Tleilaxu Infiltrator: "Enemy Agents don't block your Agent this turn".

    True when the Infiltrator is in the hand: it is either the placed card
    or, being a Graft card, always a legal partner; the partner choice then
    insists on it for an occupied space.
    """

    return any(is_tleilaxu_infiltrator(other_id) for other_id in owner.hand)


def is_tleilaxu_infiltrator(card_instance_id: str) -> bool:
    """Return whether the card is Tleilaxu Infiltrator [card face]."""

    return (
        personal_card_for_instance(card_instance_id).agent_effect
        is PersonalCardAgentEffect.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS
    )


def _placements_for_card(
    state: GameState,
    player: int,
    owner: PlayerState,
    card_instance_id: str,
    card: PersonalCardDefinition,
    graft: bool,
) -> tuple[DomainAction, ...]:
    actions: list[DomainAction] = []
    opponents = tuple(seat for seat in state.players if seat.player_id != player)
    # Grafting with a Bene Gesserit card or Ghola in hand may turn the card's
    # Bond icons on: "If you have another Bene Gesserit card in play" [Long
    # Reach card] counts a card played with it [Immortality pp. 10, 14], and
    # Ghola's copy counts Long Reach (OQ-057 (12)). The partner choice then
    # keeps such a partner when the space needs it.
    bond_partner = graft and any(
        is_bond_partner(other)
        and (card_is_graft(card) or card_is_graft(personal_card_for_instance(other)))
        for other in owner.hand
        if other != card_instance_id
    )
    icons = effective_agent_icons(
        card,
        owner,
        grafted=graft,
        opponents=opponents,
        bond_partner=bond_partner,
        card_instance_id=card_instance_id,
    )
    # The card's reach without the Bond partner's promise: an occupied space
    # is entered on Tleilaxu Infiltrator's promise instead, and a turn plays
    # two cards only [Immortality p. 10], so a card that reaches the space
    # only with a Bond partner cannot also have the Infiltrator as its
    # partner.
    icons_without_bond_partner = (
        effective_agent_icons(
            card,
            owner,
            grafted=graft,
            opponents=opponents,
            card_instance_id=card_instance_id,
        )
        if bond_partner
        else icons
    )
    usurp = graft and card_is_usurp(card)
    usurp_partners: tuple[tuple[str, tuple[AgentIcon, ...], bool], ...] = ()
    if usurp:
        # Usurp has no icons of its own; "you may use an Agent icon from
        # either card" [Immortality p. 10], so a partner's icons (a Row
        # card's, or a hand card's) open the space and the partner choice
        # keeps only the cards that fit.
        usurp_partners = tuple(
            (
                partner_id,
                effective_agent_icons(
                    personal_card_for_instance(partner_id),
                    owner,
                    grafted=True,
                    opponents=opponents,
                ),
                card_is_boosted(personal_card_for_instance(partner_id), owner),
            )
            for partner_id in (
                *state.imperium_row,
                *(other for other in owner.hand if other != card_instance_id),
            )
        )
        icons = tuple(
            dict.fromkeys(
                icon
                for _, partner_icons, _ in usurp_partners
                for icon in partner_icons
            )
        )
    # Urgent Shigawire: the boosted Bene Gesserit card "has all Agent
    # icons", so every space's icon is satisfied. A Bene Gesserit card
    # grafted to Usurp is a card played, so it takes a boost still pending
    # (user ruling 2026-10-12, OQ-107: "1. 짝도 받음"), and Usurp sends the
    # Agent with its partner's icons: such a partner opens every space,
    # and the partner choice below keeps it.
    any_icon = card_is_boosted(card, owner) or any(
        boosted for _, _, boosted in usurp_partners
    )
    # Kwisatz Haderach: "Send one of your Agents from anywhere to ANY board
    # space (even if occupied)" [Kwisatz Haderach card]. The Agent comes from
    # the Leader (no ``from_space``) or off any board space the seat holds --
    # "Agent가 남지 않아도 낼 수 있다(이미 칸에 있는 Agent를 보낸다)" -- the
    # Mentat among them, one of its Agents (OQ-139 (가)); it goes to any
    # space, the one it left ("방금 있던 칸으로 되돌려 보낼 수 있다") and one
    # holding the seat's own other Agent ("내 다른 Agent가 있는 칸에도",
    # imperium-base.md 16) included, while The Voice, the once-per-game
    # spaces and the Influence requirements still stop it (13.1 [DI p. 13]).
    anywhere = card_sends_agent_anywhere(card)
    # Every other card's Agent comes from the Leader, whatever ``owner``'s
    # count: the callers that place judge the count (``_placing_owner``,
    # ``_placements_for_hand_card``), and the app AI asks this function
    # where a card could go for a projected seat (gate 4 found a count check
    # here changed its choices in Uprising games).
    sources: tuple[str | None, ...] = (
        *((None,) if not anywhere or owner.agents_available > 0 else ()),
        *(dict.fromkeys(owner.agent_locations) if anywhere else ()),
    )
    # Tuek's Sietch is on the table only with Esmar Tuek.
    for space in board_spaces_on_table(state):
        if space.space_id in owner.voice_blocked_space_ids:
            # The Voice: "Opponents can't send their next Agents there this
            # round" [The Voice card]. Judged before the occupancy below, as no
            # Agent is involved: nothing that ignores occupying Agents (a
            # Spy's Infiltrate, Eyes Everywhere, Tleilaxu Infiltrator, the
            # Infiltrate Intrigue) opens the space (OQ-116, imperium-base.md
            # 13.1), nor does Kwisatz Haderach ("The Voice를 넘지 못한다").
            # The block ends with this seat's next Agent placement
            # (``apply_agent_action``).
            continue
        if not anywhere and not card_can_access_space(
            icons, space, owner, any_icon=any_icon
        ):
            continue
        if not anywhere and space.space_id in owner.agent_locations:
            continue
        if (
            space.space_id in ("swordmaster", "imperium_swordmaster")
            and owner.swordmaster_acquired
        ):
            continue
        if space.space_id == "imperium_high_council" and owner.high_council:
            # The original High Council: "only once per game" [DI p. 17].
            continue
        requirement_unmet = not card_ignores_influence_requirements(
            card
        ) and influence_requirement_unmet(state, owner, space)
        if requirement_unmet and not usurp:
            # A plain graft's other card waives it only as the placed card:
            # the one card that ignores the requirements (Undercover Asset)
            # carries the icon of every space that has one, so placing it
            # with the other card as its partner covers the pair.
            continue
        occupying_opponents = tuple(
            candidate.player_id
            for candidate in state.players
            if candidate.player_id != player
            and space.space_id in candidate.agent_locations
        )
        if anywhere or opponents_do_not_block(owner, space):
            # Eyes Everywhere: "상대 Agent가 Landsraad·City 칸에서 내 Agent를
            # 막지 않는다" (docs/rules/imperium-base.md 12); her own Agent
            # still blocks (above), as do requirements and once-per-game
            # limits (P0 sweep L8). The Infiltrate Intrigue does the same
            # for the turn ("Enemy Agents don't block your next Agent at
            # board spaces this turn"), and Kwisatz Haderach for its own
            # placement ("even if occupied").
            occupying_opponents = ()
        infiltrator_partner_fits = True
        if usurp:
            # The partner choice must have something to offer: a partner
            # whose icons reach the space and, on an occupied space entered
            # on Tleilaxu Infiltrator's promise, the Infiltrator itself.
            # "Both played cards are considered to have “sent” the Agent, no
            # matter which card’s icon you use." [Immortality p. 10]: a
            # partner that ignores Influence requirements (Undercover Asset)
            # waives the space's for the pair, and only such a partner fits
            # a space whose requirement is unmet.
            fitting = tuple(
                partner_id
                for partner_id, partner_icons, boosted in usurp_partners
                if card_can_access_space(partner_icons, space, owner, any_icon=boosted)
                and (
                    not requirement_unmet
                    or card_ignores_influence_requirements(
                        personal_card_for_instance(partner_id)
                    )
                )
            )
            if not fitting:
                continue
            infiltrator_partner_fits = any(
                is_tleilaxu_infiltrator(partner_id) for partner_id in fitting
            )
        elif (
            graft
            and occupying_opponents
            and not is_tleilaxu_infiltrator(card_instance_id)
        ):
            # The Infiltrator must be the partner here, so the placed card
            # has to reach the space without a Bond partner's promise; the
            # partner choice would otherwise have no card that satisfies both
            # (2026-09-16 baseline re-measurement, all expansions, game seed
            # 42: Long Reach's Bond icons needed Ghola, the occupied Arrakeen
            # needed the Infiltrator, and the turn had no legal action).
            infiltrator_partner_fits = card_can_access_space(
                icons_without_bond_partner, space, owner, any_icon=any_icon
            )
        if not occupying_opponents or (
            graft and _infiltrator_may_join(owner) and infiltrator_partner_fits
        ):
            for from_space in sources:
                actions.extend(
                    _actions_for_affordable_costs(
                        player,
                        card_instance_id,
                        space,
                        owner,
                        state,
                        graft=graft,
                        from_space=from_space,
                    )
                )
            # The Infiltrator's promise is one way onto an occupied space,
            # not the only one: Infiltrate with a connected Spy stays open to
            # any pair ("Infiltrate하려면 상대 Agent가 있는 space와 연결된
            # observation post에서 자신의 Spy를 recall한다" [Main p. 11]
            # [FAQ p. 4]; the Infiltrator joins only a pair it is part of,
            # [Immortality p. 10]; general rules audit 2026-10-25). Placed
            # itself, the Infiltrator needs no recall.
            if not occupying_opponents or is_tleilaxu_infiltrator(card_instance_id):
                continue
        # OQ-006 decided convention: Infiltrate's trigger is the
        # occupied-by-another-player predicate and its printed cost is one
        # connected Spy recall, so a single recall ignores the opposing
        # occupancy however many opponent Agents share the space
        # [Main p. 11].
        for post_id in _connected_spy_post_ids(owner, space.space_id):
            actions.extend(
                _actions_for_affordable_costs(
                    player,
                    card_instance_id,
                    space,
                    owner,
                    state,
                    infiltrate_post_id=post_id,
                    graft=graft,
                )
            )
    return tuple(actions)


def opponents_do_not_block(owner: PlayerState, space: BoardSpace) -> bool:
    """Whether opponents' Agents on ``space`` stop ``owner``'s Agent: not for
    Helena Richese's Eyes Everywhere on a Landsraad or City space, nor on any
    space for the turn of an Infiltrate Intrigue (``enemy_agents_ignored_turn``).
    An opponent's Mentat is an Agent like any other and is ignored too."""

    return owner.enemy_agents_ignored_turn or (
        owner.leader_id == "helena_richese"
        and space.agent_icon in (AgentIcon.LANDSRAAD, AgentIcon.CITY)
    )


def card_can_access_space(
    agent_icons: tuple[AgentIcon, ...],
    space: BoardSpace,
    owner: PlayerState,
    *,
    any_icon: bool = False,
    recalled_post_id: str | None = None,
) -> bool:
    """Return whether a card's Agent icons make ``space`` a destination.

    A printed icon grants direct access. The Spy Agent icon instead grants
    access when at least one of the owner's currently placed Spies is connected
    to the destination, without recalling that Spy.

    ``recalled_post_id`` counts one post the owner no longer holds a Spy on.
    An Infiltrate on the same placement recalls a Spy as its own cost
    `[Main p. 11]` `[FAQ p. 4]`, and the Graft partner choice that follows has
    to judge access in the state the placement was judged in, not after that
    cost was paid.
    """

    if any_icon or space.agent_icon in agent_icons:
        return True
    # Emperor's Invitation (Bloodlines): "The card you play this turn has
    # the [Emperor] icon."
    if owner.granted_agent_icon_turn and space.agent_icon.value in (
        owner.granted_agent_icon_turn.split(",")
    ):
        return True
    # Clandestine: "Each card you play has the Spy icon" [Gaius Helen
    # Mohiam card].
    if AgentIcon.SPY not in agent_icons and owner.leader_id != "gaius_helen_mohiam":
        return False
    if _connected_spy_post_ids(owner, space.space_id):
        return True
    return recalled_post_id is not None and any(
        post.post_id == recalled_post_id and space.space_id in post.connected_space_ids
        for post in OBSERVATION_POSTS
    )


def apply_agent_action(state: GameState, action: DomainAction) -> RuleResult:
    """Pay for and commit one legal card-and-space Agent placement.

    Board, Agent-card, and Faction effects remain pending so their rules-defined
    free ordering can be resolved by subsequent decisions.
    """

    arguments = dict(action.arguments)
    card_instance_id = arguments.get("card_id")
    # The dispatcher has already checked the full legal set; this guard keeps
    # the handler's own contract at the cost of one card's placements.
    if not isinstance(card_instance_id, str) or action not in (
        legal_agent_actions_for_card(state, action.actor, card_instance_id)
    ):
        raise ValueError("action is not a legal Agent turn in the current state")

    space_id = arguments["space_id"]
    if not isinstance(space_id, str):
        raise ValueError("Agent action card_id and space_id must be strings")

    card = personal_card_for_instance(card_instance_id)
    space = BOARD_SPACES_BY_ID[space_id]
    combat_space = space_is_combat(state, space)
    cost_option, cost = _selected_cost(
        state, space, arguments.get("cost_option"), action.actor
    )
    discount = arguments.get("discount")
    if discount == "spice":
        cost = replace(cost, spice=cost.spice - 1)
    elif discount == "solari":
        cost = replace(cost, solari=cost.solari - 1)
    owner = state.players[action.actor]
    # Emperor of the Known Universe: playing Shaddam's Signet Ring blocks
    # unit deployment to the Conflict for this whole turn, effective
    # immediately from the placement [Main p. 17] [FAQ p. 3]. Used through
    # Servo-Receivers before the placement, the ban already waits in the
    # turn frame, as may a Harkonnen Advisor troop that stays undeployable
    # (OQ-062 (b), OQ-038).
    turn_context = dict(state.decision_stack[-1].context)
    units_deploy_blocked = (
        card.agent_effect is PersonalCardAgentEffect.LEADER_SIGNET
        and owner.leader_id == "shaddam_corrino_iv"
    ) or turn_context.get("units_deploy_blocked") is True
    undeployable = turn_context.get("undeployable_troops", 0)
    if isinstance(undeployable, bool) or not isinstance(undeployable, int):
        raise RuntimeError("turn frame has an invalid undeployable count")
    ungained_undeployable = ungained_undeployable_troops(turn_context)
    commanders_before = _commanders_recruited_before_placement(state)
    dreadnoughts_before = commissioned_dreadnought_count(turn_context)
    shipping_before = shipping_troop_count(turn_context)
    ungained_shipping = ungained_shipping_troop_count(turn_context)
    infiltrate_post_id = arguments.get("infiltrate_post_id")
    if infiltrate_post_id is not None and not isinstance(infiltrate_post_id, str):
        raise ValueError("Agent action infiltrate_post_id must be a string")
    graft = arguments.get("graft") is True
    # Kwisatz Haderach's Agent off a board space (``_placements_for_card``):
    # that space is empty of it from now on, and nothing resolved there is
    # undone (imperium-base.md 13.1: a Maker space it left gathers bonus spice
    # if still empty at Phase 4).
    from_space = arguments.get("from_space")
    if from_space is not None and not isinstance(from_space, str):
        raise ValueError("Agent action from_space must be a string")
    boosted = card_is_boosted(card, owner)
    next_owner = replace(
        owner,
        bene_gesserit_boost_pending=owner.bene_gesserit_boost_pending and not boosted,
        resources=_pay_cost(owner.resources, cost),
        spice_spent_turn=owner.spice_spent_turn + cost.spice,
        agents_available=owner.agents_available - int(from_space is None),
        agent_locations=(
            *_agent_moved_off(owner.agent_locations, from_space),
            space_id,
        ),
        # Every Agent placement, the Mentat's too, uses up the seat's Voice
        # blocks ("their next Agents", OQ-116) and the turn's Infiltrate.
        voice_blocked_space_ids=(),
        enemy_agents_ignored_turn=False,
        spies_supply=owner.spies_supply + int(infiltrate_post_id is not None),
        spies_recalled_turn=owner.spies_recalled_turn
        + int(infiltrate_post_id is not None),
        spy_post_ids=tuple(
            post_id for post_id in owner.spy_post_ids if post_id != infiltrate_post_id
        ),
        hand=tuple(card_id for card_id in owner.hand if card_id != card_instance_id),
        in_play=(*owner.in_play, card_instance_id),
    )
    negotiator_events: tuple[GameEvent, ...] = ()
    if cost.solari > 0 and leader_triggers(
        owner.leader_face_id or owner.leader_id, OnBoardSpaceSolariPaid
    ):
        # Ruthless Negotiator: a card whenever Solari pay a board space's
        # printed cost [FAQ p. 2] (docs/rules/imperium-base.md 12), drawn as
        # its own step after the public placement (OQ-106).
        source = (
            f"round:{state.round_number}:player:{action.actor}:ruthless_negotiator"
        )
        next_owner = hold_draw(next_owner, OWED_CARD, "ruthless_negotiator", source)
        negotiator_events = (
            GameEvent(
                event_id=f"{source}:{space_id}",
                kind="leader_ability_resolved",
                payload=(
                    ("leader_id", "count_ilban_richese"),
                    ("player", action.actor),
                ),
            ),
        )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    pending_contract_ids = contract_candidates_for_agent_turn(
        state,
        action.actor,
        space_id,
    )
    # Every printed icon of the space is its own freely ordered effect
    # [Main p. 9] (OQ-027); the visit's icon list is fixed at placement.
    board_icons = ",".join(
        board_icons_for(state, action.actor, space_id, cost_option)
    )
    agent_effect_pending = agent_effect_is_available(
        card.agent_effect,
        replace(owner, resources=next_owner.resources),
        space,
        card_instance_id,
    )
    # A multi-icon Agent box queues its printed icons for their own actions
    # (OQ-027); single-effect boxes keep the plain resolution.
    agent_icons = ",".join(
        agent_card_icons_at_placement(card.agent_effect, owner.leader_id)
        if agent_effect_pending
        else ()
    )
    effect_frame = DecisionFrame(
        kind=FrameKind.AGENT_EFFECTS,
        frame_id=(f"round:{state.round_number}:player:{action.actor}:agent_effects"),
        decision=PlayerDecision(
            owner=action.actor,
            prompt="Choose the next Agent-turn effect to resolve",
        ),
        context=tuple(
            sorted(
                (
                    ("board_icons", board_icons),
                    ("card_id", card_instance_id),
                    ("combat_troops_deployed", 0),
                    ("cost_option", cost_option),
                    # Filled in by the Graft partner choice [Immortality p. 10].
                    ("graft_card_id", ""),
                    ("graft_pending_effect", False),
                    ("graft_pending_icons", ""),
                    # A Combat icon gained earlier this turn deploys like a Combat
                    # space, never more than two from the garrison [Bloodlines p. 5].
                    # Eyes on Arrakis makes Faction spaces Combat spaces.
                    (
                        "existing_troop_deployment_limit",
                        2 if combat_space or owner.combat_icon_turn else 0,
                    ),
                    *(
                        (
                            (BOOST_DRAW_KEY, card_instance_id),
                            (BOOSTED_CARDS_KEY, card_instance_id),
                        )
                        if boosted
                        else ()
                    ),
                    ("pending_agent_effect", agent_effect_pending),
                    ("pending_agent_icons", agent_icons),
                    ("pending_board_effect", bool(board_icons)),
                    ("pending_board_icons", board_icons),
                    (
                        "pending_combat_deployment",
                        not units_deploy_blocked
                        and (
                            combat_space
                            or owner.combat_icon_turn
                            or (
                                isinstance(card, ImperiumCardEntry)
                                and card.allows_recruited_troop_deployment
                            )
                        ),
                    ),
                    *(
                        (
                            (
                                TECH_ACQUIRE_PENDING_KEY,
                                turn_context[TECH_ACQUIRE_PENDING_KEY],
                            ),
                        )
                        if turn_context.get(TECH_ACQUIRE_PENDING_KEY)
                        else ()
                    ),
                    # A research bonus a Plot raised before the Agent went
                    # out (cleanup-2b).
                    *turn_rows.carried(turn_context),
                    ("pending_contract_ids", ",".join(pending_contract_ids)),
                    (
                        # Subversive Advisor's waiting box holds the space's
                        # Influence; it comes back if the box expires
                        # (``expire_trashed_card_effects``).
                        "pending_faction_influence",
                        space.faction is not None
                        and not holds_space_influence(card.agent_effect),
                    ),
                    (
                        "pending_gather_intelligence",
                        any(
                            space_id in post.connected_space_ids
                            and post.post_id in next_owner.spy_post_ids
                            for post in OBSERVATION_POSTS
                        ),
                    ),
                    (
                        # Other Memories triggers when Lady Jessica sends an Agent to
                        # a Bene Gesserit board space [Lady Jessica card].
                        "pending_leader_ability",
                        space.faction is Faction.BENE_GESSERIT
                        and owner.leader_face_id == "lady_jessica",
                    ),
                    (
                        # Reverend Mother offers one paid repeat of the printed space
                        # effects per turn on a Bene Gesserit or Fremen board space
                        # [Reverend Mother Jessica card].
                        "pending_leader_board_repeat",
                        space.faction in (Faction.BENE_GESSERIT, Faction.FREMEN)
                        and owner.leader_face_id == "reverend_mother_jessica",
                    ),
                    ("space_id", space_id),
                    ("troops_recruited", _troops_recruited_before_placement(state)),
                    ("turn_owner", action.actor),
                    *((("undeployable_troops", undeployable),) if undeployable else ()),
                    *(
                        ((UNGAINED_UNDEPLOYABLE_KEY, ungained_undeployable),)
                        if ungained_undeployable
                        else ()
                    ),
                    # A Commander recruited before the placement keeps its
                    # deploy slot for a Commander (OQ-070).
                    *(
                        ((COMMANDERS_RECRUITED_KEY, commanders_before),)
                        if commanders_before
                        else ()
                    ),
                    # So does a dreadnought commissioned before the
                    # placement: it may deploy if the Agent goes to a Combat
                    # space [Rise of Ix p. 6].
                    *(
                        ((DREADNOUGHTS_COMMISSIONED_KEY, dreadnoughts_before),)
                        if dreadnoughts_before
                        else ()
                    ),
                    # And Troop Transports' Shipping troops recruited before
                    # the placement, which deploy wherever the Agent goes
                    # (docs/rules/rise-of-ix.md 15).
                    *(
                        ((SHIPPING_TROOPS_KEY, shipping_before),)
                        if shipping_before
                        else ()
                    ),
                    # With the part of that recruit the supply could not give
                    # yet, which a later refill moves into the allowance
                    # (OQ-030).
                    *(
                        ((UNGAINED_SHIPPING_TROOPS_KEY, ungained_shipping),)
                        if ungained_shipping
                        else ()
                    ),
                    ("units_deploy_blocked", units_deploy_blocked),
                )
            )
        ),
    )
    frames: tuple[DecisionFrame, ...] = (*state.decision_stack[:-1], effect_frame)
    if graft:
        # The second card is chosen next; its box joins the effect frame.
        frames = (
            *frames,
            DecisionFrame(
                kind=FrameKind.GRAFT_PARTNER,
                frame_id=(
                    f"round:{state.round_number}:player:{action.actor}:graft_partner"
                ),
                decision=PlayerDecision(
                    owner=action.actor, prompt="Choose the card to graft"
                ),
                context=(
                    ("card_id", card_instance_id),
                    # The Spy icon "이 아이콘을 사용하기 위해 Spy를 회수하지는
                    # 않는다" `[Main p. 11]`, but an Infiltrate on the same
                    # placement recalls a Spy as its own cost `[Main p. 11]`
                    # `[FAQ p. 4]`. When the access the partner supplies was
                    # that Spy's, it is gone by the time the partner is picked,
                    # so the post is recorded and the partner choice judges
                    # access with the Spy still on it.
                    ("infiltrate_post_id", infiltrate_post_id or ""),
                    (
                        "occupied",
                        infiltrate_post_id is None
                        # Eyes Everywhere and Infiltrate: opponents' Agents
                        # do not block, so no Infiltrator promise is needed.
                        and not opponents_do_not_block(owner, space)
                        and any(
                            space_id in seat.agent_locations
                            for seat in state.players
                            if seat.player_id != action.actor
                        ),
                    ),
                    # The placed card (Usurp) went to a space whose Influence
                    # requirement it cannot meet, on the promise of a partner
                    # that ignores the requirements [Immortality p. 10]: only
                    # such a partner may follow (absent otherwise).
                    *(
                        ((GRAFT_PARTNER_WAIVES_INFLUENCE_KEY, True),)
                        if not card_ignores_influence_requirements(card)
                        and influence_requirement_unmet(state, owner, space)
                        else ()
                    ),
                    # Whether the placed card reached this space on its own,
                    # decided here because the partner choice cannot re-derive
                    # it: Infiltrate recalls the very Spy that Mohiam's
                    # Clandestine icon needed, so by then the access is gone
                    # and only Usurp-style cards would look partner-dependent.
                    (
                        "placed_reaches",
                        card_can_access_space(
                            effective_agent_icons(
                                card,
                                owner,
                                grafted=True,
                                opponents=tuple(
                                    seat
                                    for seat in state.players
                                    if seat.player_id != action.actor
                                ),
                            ),
                            space,
                            owner,
                            any_icon=card_is_boosted(card, owner),
                        ),
                    ),
                    ("player", action.actor),
                    ("space_id", space_id),
                ),
            ),
        )
    next_state = replace(state, players=players, decision_stack=frames)
    # Kwisatz Haderach may send a second Agent of the seat to one space in a
    # round, so its placement's id names where the Agent came from; the
    # payload's ``from_space`` names the board space it left (absent: the
    # Leader).
    moved_from = (
        f":from:{from_space or 'leader'}" if card_sends_agent_anywhere(card) else ""
    )
    placement_event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:agent:{space_id}"
            f"{moved_from}"
        ),
        kind="agent_placed",
        payload=(
            ("card_id", card_instance_id),
            *((("from_space", from_space),) if from_space is not None else ()),
            ("player", action.actor),
            ("space_id", space_id),
        ),
    )
    infiltration_events = (
        ()
        if infiltrate_post_id is None
        else (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"infiltrate:{space_id}:{infiltrate_post_id}"
                ),
                kind="spy_recalled_for_infiltrate",
                payload=(
                    ("player", action.actor),
                    ("post_id", infiltrate_post_id),
                    ("space_id", space_id),
                ),
            ),
        )
    )
    next_state, control_event = _apply_control_visit_bonus(next_state, space_id)
    smuggled_players, smuggle_events = apply_smuggle_spice(
        next_state.players,
        action.actor,
        space_id,
        space.maker,
        state.round_number,
    )
    if smuggle_events:
        next_state = replace(next_state, players=smuggled_players)
    events = (
        placement_event,
        *infiltration_events,
        *negotiator_events,
        *(() if control_event is None else (control_event,)),
        *smuggle_events,
    )
    if space_id == "tuek_sietch":
        # Tuek's Sietch (Esmar Tuek): the owner's own visit pays one Solari,
        # an opponent's visit draws him an Intrigue card [Esmar Tuek card].
        next_state, sietch_events = _apply_tuek_sietch_visit(
            next_state, action.actor, state.round_number
        )
        events = (*events, *sietch_events)
    if boosted:
        # Urgent Shigawire: "added to its Agent box: draw a card". The boost
        # is spent by the placement; the draw waits in the effect frame
        # (``BOOST_DRAW_KEY``) for its own step in any order with the other
        # effects [Main p. 9], so the public placement stays undoable and only
        # the hidden draw closes the undo window: "그 외에는 전부 나누자.
        # 특히 카드 드로우는 나눠야하는게, 드로우 하기 전에 버림더미 카드를
        # 폐기하고 싶을 수 있잖아." (user ruling 2026-10-10, OQ-106).
        events = (
            *events,
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"shigawire:{card_instance_id}"
                ),
                kind="agent_card_boost_consumed",
                payload=(("card_id", card_instance_id), ("player", action.actor)),
            ),
        )
    return RuleResult(state=next_state, events=events)


def _apply_tuek_sietch_visit(
    state: GameState,
    visitor: int,
    round_number: int,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    # Tuek's Sietch: "Whenever you send an Agent to Tuek's Sietch: Gain 1
    # solari. Whenever an opponent sends an Agent there: Draw 1 Intrigue
    # card" [Esmar Tuek card], from his records (composed A6e).
    esmar = next(
        (
            seat
            for seat in state.players
            if any(
                trigger.space_id == "tuek_sietch"
                for trigger, _ in leader_triggers(
                    seat.leader_face_id or seat.leader_id, OnAgentSentTo
                )
            )
        ),
        None,
    )
    if esmar is None:
        return state, ()
    own = esmar.player_id == visitor
    ((_, (reward,)),) = (
        (trigger, rewards)
        for trigger, rewards in leader_triggers(
            esmar.leader_face_id or esmar.leader_id, OnAgentSentTo
        )
        if trigger.space_id == "tuek_sietch" and trigger.opponent is not own
    )
    # The ability is Esmar's: its events are named after the Leader and its
    # own event comes last (cleanup-2c-4).
    source = (
        f"round:{round_number}:player:{esmar.player_id}:leader:{esmar.leader_id}"
    )
    if own:
        if not isinstance(reward, GainResources):
            raise RuntimeError("Tuek's Sietch pays its owner's visit in Solari")
        paid = replace(
            esmar,
            resources=replace(
                esmar.resources, solari=esmar.resources.solari + reward.solari
            ),
        )
        return replace(state, players=replace_player(state.players, paid)), (
            resources_gained_event(source, esmar.player_id, solari=reward.solari),
            GameEvent(
                event_id=f"{source}:resolved",
                kind="leader_ability_resolved",
                payload=(
                    ("leader_id", str(esmar.leader_id)),
                    ("player", esmar.player_id),
                ),
            ),
        )
    if not isinstance(reward, DrawIntrigueCards):
        raise RuntimeError("Tuek's Sietch draws for an opponent's visit")
    drawn = draw_or_queue_intrigue_cards(
        state, esmar.player_id, reward.count, source=source
    )
    return drawn.state, (
        *drawn.events,
        GameEvent(
            event_id=f"{source}:resolved",
            kind="leader_ability_resolved",
            payload=(
                ("leader_id", str(esmar.leader_id)),
                ("player", esmar.player_id),
                ("visitor", visitor),
            ),
        ),
    )


def legal_turn_start_card_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer Litany Against Fear's turn-start alternative from the hand.

    "At the start of your turn: put this card into play -> draw a card and
    pass your turn" [Litany Against Fear card]: an alternative to the Agent
    or Reveal turn, taken from the turn frame, and only as the turn's first
    action -- once the seat did anything else in the turn (a Plot, a
    specimen return, its Emperor track Spy), the start is over (OQ-095 (6),
    user ruling 2026-10-04, ``frames.turn_start_is_open``). An Emperor track
    Spy waits in the turn only after such an action, so the turn is never
    passed over one.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return ()
    if owned_top_frame(state, FrameKind.TURN, player) is None:
        return ()
    if not turn_start_is_open(state, player):
        return ()
    return tuple(
        DomainAction(
            action_id="play_turn_start_card",
            actor=player,
            arguments=(("card_id", card_instance_id),),
        )
        for card_instance_id in turn_start_cards(state.players[player])
    )


def turn_start_cards(owner: PlayerState) -> tuple[str, ...]:
    """The seat's hand cards with Litany Against Fear's turn-start effect."""

    return tuple(
        card_instance_id
        for card_instance_id in owner.hand
        if _turn_start_effect(card_instance_id)
        is PersonalCardTurnStartEffect.PLAY_TO_DRAW_AND_PASS
    )


def _turn_start_effect(card_instance_id: str) -> PersonalCardTurnStartEffect | None:
    card = personal_card_for_instance(card_instance_id)
    return card.turn_start_effect if isinstance(card, ImperiumCardEntry) else None


def apply_turn_start_card(state: GameState, action: DomainAction) -> RuleResult:
    """Put the card into play, draw one card, and pass the turn."""

    if action not in legal_turn_start_card_actions(state, action.actor):
        raise ValueError("action is not a legal turn-start card play")
    card_instance_id = str(dict(action.arguments)["card_id"])
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        hand=tuple(card_id for card_id in owner.hand if card_id != card_instance_id),
        in_play=(*owner.in_play, card_instance_id),
    )
    # "Pass your turn": the clockwise unrevealed player's turn opens, as
    # after an Agent turn; this seat stays unrevealed and comes around again.
    passed = open_next_turn(
        replace(state, players=replace_player(state.players, next_owner)),
        action.actor,
    )
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"turn_start_card:{card_instance_id}"
    )
    drawn = draw_or_request_personal_cards(passed, action.actor, 1, source=source)
    return RuleResult(
        state=drawn.state,
        events=(
            GameEvent(
                event_id=source,
                kind="turn_start_card_played",
                payload=(("card_id", card_instance_id), ("player", action.actor)),
            ),
            *drawn.events,
        ),
    )


def agent_effect_is_available(
    effect: PersonalCardAgentEffect | None,
    owner: PlayerState,
    space: BoardSpace,
    card_instance_id: str,
) -> bool:
    """Return whether the played card's Agent box stays pending after placement.

    Only conditions that no later effect of the same turn can change are
    judged here: the visited space (its Faction, its Maker status) and
    Faction Bonds among the cards already in play, which can only shrink.
    Every other printed condition — an Influence threshold, a resource,
    hand-size or Intrigue cost, an Alliance, sandworms in the Conflict — is
    judged when the box is actually resolved, in the owner's chosen order
    [Main pp. 7, 9]: a freely ordered board, Faction, Contract or Intrigue
    effect of the same turn can still satisfy it (OQ-028).
    """

    if effect is None:
        return False
    if (
        effect is PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND
        and card_instance_id == owner.usurped_row_card_id
    ):
        # Weirding Woman borrowed with Usurp is not "in play" [Immortality p.
        # 14] (OQ-054, user ruling 2026-10-04), so "Return this card to your
        # hand" can never happen: the box is not left waiting for it.
        return False
    ability = box_ability(effect)
    if ability is not None:
        # A box written as an ability record judges its placement condition
        # (a Maker space, the Bene Gesserit Bond) from the record (OQ-028 (a)).
        return opens_at_placement(ability, owner, space, card_instance_id)
    return True


def _troops_recruited_before_placement(state: GameState) -> int:
    """Troops recruited earlier this turn (e.g. by Plot Intrigue) stay deployable."""

    frame = state.decision_stack[-1]
    value = dict(frame.context).get("troops_recruited", 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("turn frame has an invalid recruit count")
    return value


def _commanders_recruited_before_placement(state: GameState) -> int:
    """Commanders recruited earlier this turn keep their own deploy slots.

    A Sardaukar Standard trashed before the placement acquires and recruits
    the bank Commander into the turn frame (``update_turn_recruits``); the
    placement carries that count apart from the troops (OQ-070).
    """

    return recruited_commander_count(
        dict(state.decision_stack[-1].context), COMMANDERS_RECRUITED_KEY
    )


def _actions_for_affordable_costs(
    player: int,
    card_instance_id: str,
    space: BoardSpace,
    owner: PlayerState,
    state: GameState,
    infiltrate_post_id: str | None = None,
    *,
    graft: bool = False,
    from_space: str | None = None,
) -> tuple[DomainAction, ...]:
    """The placement's actions, one per cost the owner can pay; ``from_space``
    names the board space Kwisatz Haderach's Agent comes off (None: the
    Leader)."""

    costs = _effective_costs(state, space, player)
    include_choice = space.dynamic_cost is None and len(space.cost_options) > 1
    actions: list[DomainAction] = []
    for cost_option, cost in costs:
        # Navigation Chamber: "Board spaces cost you [1 spice] or [1 Solari]
        # less." [Tech tile face] (bloodlines.md: "board space 비용이 spice 1
        # 또는 Solari 1 줄어든다" [Bloodlines p. 7]). The tile has no "may",
        # so the cut always applies, as the rulebook's "the Tech tile costs
        # him 1 less Spice" [Bloodlines p. 7] and every other cost cut here
        # (Duncan's below, Sardaukar High Command, the High Council Tech
        # discount) do; the printed "or" is a choice only on a cost holding
        # both resources, which no 4-player space has (OQ-104, project
        # reading). Spice Refinery's and Gather Support's arrow payments are
        # cost options [Board Guide pp. 1-2], so the cut reaches them; their
        # free option and water-only costs keep the plain variant.
        variants: list[tuple[str | None, ResourceCost]] = []
        if has_tech(owner.tech_ids, TechAbility.SPACE_DISCOUNT):
            if cost.spice >= 1:
                variants.append(("spice", replace(cost, spice=cost.spice - 1)))
            if cost.solari >= 1:
                variants.append(("solari", replace(cost, solari=cost.solari - 1)))
        if not variants:
            variants.append((None, cost))
        for discount, effective in variants:
            if not _can_afford(owner, effective):
                continue
            argument_items: list[tuple[str, str | int | bool]] = [
                ("card_id", card_instance_id)
            ]
            if include_choice:
                argument_items.append(("cost_option", cost_option))
            if discount is not None:
                argument_items.append(("discount", discount))
            if from_space is not None:
                argument_items.append(("from_space", from_space))
            if graft:
                argument_items.append(("graft", True))
            if infiltrate_post_id is not None:
                argument_items.append(("infiltrate_post_id", infiltrate_post_id))
            argument_items.append(("space_id", space.space_id))
            actions.append(
                DomainAction(
                    action_id="agent_turn",
                    actor=player,
                    arguments=tuple(argument_items),
                )
            )
    return tuple(actions)


def _connected_spy_post_ids(
    owner: PlayerState,
    space_id: str,
) -> tuple[str, ...]:
    connected_post_ids = {
        post.post_id
        for post in OBSERVATION_POSTS
        if space_id in post.connected_space_ids
    }
    return tuple(
        post_id for post_id in owner.spy_post_ids if post_id in connected_post_ids
    )


def _effective_costs(
    state: GameState,
    space: BoardSpace,
    player: int,
) -> tuple[tuple[int, ResourceCost], ...]:
    if space.dynamic_cost is DynamicCost.SWORDMASTER:
        someone_has_swordmaster = any(
            player.swordmaster_acquired for player in state.players
        )
        option = 1 if someone_has_swordmaster else 0
        cost = space.cost_options[option]
        if state.players[player].leader_id == "duncan_idaho":
            # Ginaz Swordmaster: "The Swordmaster board space costs you 2
            # less" [Duncan Idaho card].
            cost = replace(cost, solari=max(cost.solari - 2, 0))
        return ((option, cost),)
    costs = space.cost_options or (ResourceCost(),)
    if (
        state.players[player].leader_id == "duke_leto_atreides"
        and space.agent_icon is AgentIcon.LANDSRAAD
    ):
        # Landsraad Popularity: a Landsraad space's Solari cost is 1 less,
        # never optional (docs/rules/imperium-base.md 12, P0 sweep L5); a
        # space with no Solari cost is unchanged.
        costs = tuple(
            replace(cost, solari=cost.solari - 1) if cost.solari else cost
            for cost in costs
        )
    return tuple(enumerate(costs))


def _selected_cost(
    state: GameState,
    space: BoardSpace,
    requested_option: bool | int | str | None,
    player: int,
) -> tuple[int, ResourceCost]:
    costs = dict(_effective_costs(state, space, player))
    if requested_option is None:
        if len(costs) != 1:
            raise ValueError("Agent action must identify its cost option")
        return next(iter(costs.items()))
    if isinstance(requested_option, bool) or not isinstance(requested_option, int):
        raise ValueError("Agent action cost_option must be an integer")
    try:
        return requested_option, costs[requested_option]
    except KeyError as error:
        raise ValueError("Agent action cost option is not available") from error


def _agent_moved_off(
    locations: tuple[str, ...], from_space: str | None
) -> tuple[str, ...]:
    """``locations`` less the one Agent Kwisatz Haderach takes off
    ``from_space`` (None: the Agent came from the Leader); a second Agent of
    the seat on that space stays."""

    if from_space is None:
        return locations
    index = locations.index(from_space)
    return (*locations[:index], *locations[index + 1 :])


def _pay_cost(resources: Resources, cost: ResourceCost) -> Resources:
    return Resources(
        solari=resources.solari - cost.solari,
        spice=resources.spice - cost.spice,
        water=resources.water - cost.water,
    )


def _can_afford(player: PlayerState, cost: ResourceCost) -> bool:
    return (
        player.resources.solari >= cost.solari
        and player.resources.spice >= cost.spice
        and player.resources.water >= cost.water
    )


GRAFT_PARTNER_WAIVES_INFLUENCE_KEY = "partner_waives_influence"
"""Graft partner frame key: the partner must ignore Influence requirements,
since the placed card reached a space whose requirement is unmet only on
that promise (Usurp with Undercover Asset, [Immortality p. 10])."""


def card_ignores_influence_requirements(card: PersonalCardDefinition) -> bool:
    """Whether the card's placement ignores Influence requirements
    (Undercover Asset [card face])."""

    return isinstance(card, ImperiumCardEntry) and card.ignores_influence_requirements


def influence_requirement_waived(
    state: GameState, owner: PlayerState, space: BoardSpace
) -> bool:
    """Whether the owner's own effects waive ``space``'s Influence requirement.

    Insider Information (Bloodlines) waives them for the turn; Arrakis
    Planetologist ignores Sietch Tabr's [Liet Kynes card]; Unlikely Allies
    (Arrakeen Scouts) for the round. A card that ignores them for its own
    placement is the caller's to check.
    """

    return (
        owner.ignores_influence_requirements_turn
        or ignores_influence_requirements_this_round(state)
        or (owner.leader_id == "liet_kynes" and space.space_id == "sietch_tabr")
    )


def influence_requirement_unmet(
    state: GameState, owner: PlayerState, space: BoardSpace
) -> bool:
    """Whether ``space``'s printed Influence requirement bars the owner now:
    unmet and not waived (``influence_requirement_waived``).

    The Agent placement reads it, and so does Insider Information's play
    gate (``effect_interpreter``), so the two cannot drift.
    """

    return not influence_requirement_waived(
        state, owner, space
    ) and not _meets_requirement(owner.influence, space.requirement)


def _meets_requirement(
    influence: Influence,
    requirement: InfluenceRequirement | None,
) -> bool:
    if requirement is None:
        return True
    match requirement.faction:
        case Faction.EMPEROR:
            amount = influence.emperor
        case Faction.SPACING_GUILD:
            amount = influence.spacing_guild
        case Faction.BENE_GESSERIT:
            amount = influence.bene_gesserit
        case Faction.FREMEN:
            amount = influence.fremen
    return amount >= requirement.amount


def _apply_control_visit_bonus(
    state: GameState,
    space_id: str,
) -> tuple[GameState, GameEvent | None]:
    resource = content_for(state.config).control_visit_bonuses.get(space_id)
    if resource is None:
        return state, None
    # A dreadnought on the space controls it ahead of the Control marker it
    # covers, so its owner takes the bonus [Rise of Ix p. 6].
    controller_seat = space_controller(state, space_id)
    if controller_seat is None:
        return state, None

    controller = state.players[controller_seat]
    next_controller = replace(
        controller,
        resources=replace(
            controller.resources,
            **{resource: getattr(controller.resources, resource) + 1},
        ),
    )
    players = tuple(
        next_controller if player.player_id == next_controller.player_id else player
        for player in state.players
    )
    # The controller's resource gain, named after the Control marker on the
    # space (rule decision 3, cleanup-2c-3).
    event = resources_gained_event(
        f"round:{state.round_number}:player:{controller.player_id}:control:"
        f"{space_id}",
        controller.player_id,
        **{resource: 1},
    )
    return replace(state, players=players), event
