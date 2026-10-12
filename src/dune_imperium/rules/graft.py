"""Graft: playing two cards on one Agent turn [Immortality pp. 10-11].

"When you play a card with Graft during an Agent turn, it can't be played
alone. You must play two cards (and only two) on that turn ... You may use
an Agent icon from either card to send your Agent ... Both played cards are
considered to have 'sent' the Agent ... You gain the effects on both cards,
in addition to the board space effects, in any order you choose."

The placement (``agent_turn`` with ``graft``) commits the first card and the
space, then a ``GRAFT_PARTNER`` frame takes the second card from the hand.
Both cards are in play. The placed card's box is box 0 and the partner's
box 1, and both are offered together from the start (user decision
2026-10-12, docs/graft-boxes-plan.md): box 1's rows carry ``box=1``, and
the engine makes a row's box the active one (``graft_boxes``) so either box
resolves through the ordinary Agent-box machinery in the owner's order.
"""

from dataclasses import replace

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.personal_cards import (
    card_is_ghola,
    card_is_graft,
    card_is_usurp,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import take_imperium_row_card
from dune_imperium.rules.agent_effects import (
    agent_card_icons_at_placement,
    holds_space_influence,
)
from dune_imperium.rules.agent_icons import (
    card_is_boosted,
    effective_agent_icons,
    is_bond_partner,
)
from dune_imperium.rules.agent_turn import (
    GRAFT_PARTNER_WAIVES_INFLUENCE_KEY,
    agent_effect_is_available,
    card_can_access_space,
    card_ignores_influence_requirements,
    is_tleilaxu_infiltrator,
)
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import (
    add_boost_draw,
    borrowed_agent_card,
    current_agent_effect_context,
    pending_boost_draws,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
    with_context,
)

_PARTNER_LABEL = "Graft partner frame"
_CHAIRDOG_RETURN = PersonalCardAgentEffect.RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START


def legal_graft_partner_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every hand card that may be grafted to the placed card."""

    frame = owned_top_frame(state, FrameKind.GRAFT_PARTNER, player)
    if frame is None:
        return ()
    context = dict(frame.context)
    placed_id = context_str(context, "card_id", owner=_PARTNER_LABEL)
    placed = personal_card_for_instance(placed_id)
    occupied = context.get("occupied") is True
    owner = state.players[player]
    space = BOARD_SPACES_BY_ID[context_str(context, "space_id", owner=_PARTNER_LABEL)]
    opponents = tuple(seat for seat in state.players if seat.player_id != player)
    # The placement recorded whether the placed card reached this space on its
    # own; it cannot be re-derived here. Mohiam's Clandestine -- "Each card you
    # play has the Spy icon" [Gaius Helen Mohiam card] -- let an icon-less
    # starter Infiltrate into Secrets, and Infiltrate recalls the very Spy that
    # icon needed, so the access is already spent by now. Reading the empty
    # icon tuple as "it came in on the partner's icons" then demanded a partner
    # that fit Bene Gesserit; with none in hand the turn had no legal action at
    # all (2026-09-10 all-expansion A/B, game seed 499).
    placed_reaches = context.get("placed_reaches") is True
    # The same spent access on the partner's side. A Spy icon reaches every
    # space connected to a post the owner has a Spy on and "이 아이콘을
    # 사용하기 위해 Spy를 회수하지는 않는다" `[Main p. 11]`, but an Infiltrate
    # on the same placement recalls a Spy as its own cost `[Main p. 11]`
    # `[FAQ p. 4]`. A card with no icons of its own leans entirely on the
    # partner (Usurp), so when that partner's access was the Infiltrated Spy's
    # every candidate filtered out and the turn had no legal action at all
    # (2026-09-10 Immortality A/B, game seeds 70254 and 70804). Access is
    # judged with the Spy back on the post it was recalled from, which is the
    # state the placement was judged in.
    recalled = context.get("infiltrate_post_id")
    recalled_post_id = recalled if isinstance(recalled, str) and recalled else None
    # Long Reach entered on the promise of its Bond partner -- a Bene Gesserit
    # card played with it [Long Reach card] [Immortality pp. 10, 14] or
    # Ghola's copy (OQ-057 (12)): only such a card may then be the partner.
    needs_bond_partner = False
    if not placed_reaches:
        needs_bond_partner = card_can_access_space(
            effective_agent_icons(
                placed, owner, grafted=True, opponents=opponents, bond_partner=True
            ),
            space,
            owner,
            any_icon=card_is_boosted(placed, owner),
            recalled_post_id=recalled_post_id,
        )
    # Only a placed card that cannot reach the space by any means of its own
    # (Usurp, which has no icons) leans on the partner for access.
    partner_must_fit = not placed_reaches and not needs_bond_partner
    # "Both played cards are considered to have “sent” the Agent"
    # [Immortality p. 10]: Usurp sent to a space whose Influence requirement
    # is unmet needs a partner that ignores the requirements.
    partner_must_waive = context.get(GRAFT_PARTNER_WAIVES_INFLUENCE_KEY) is True
    candidates: tuple[str, ...] = (
        *(card_id for card_id in owner.hand if card_id != placed_id),
        # Usurp: "graft this card with a card from the Imperium Row".
        *(state.imperium_row if card_is_usurp(placed) else ()),
    )
    return tuple(
        DomainAction(
            action_id="choose_graft_partner",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in candidates
        if (
            card_is_graft(placed) or card_is_graft(personal_card_for_instance(card_id))
        )
        and (not needs_bond_partner or is_bond_partner(card_id))
        and (
            not partner_must_waive
            or card_ignores_influence_requirements(personal_card_for_instance(card_id))
        )
        # An occupied space was entered on Tleilaxu Infiltrator's promise.
        and (
            not occupied
            or is_tleilaxu_infiltrator(placed_id)
            or is_tleilaxu_infiltrator(card_id)
        )
        and (
            not partner_must_fit
            or card_can_access_space(
                effective_agent_icons(
                    personal_card_for_instance(card_id),
                    owner,
                    grafted=True,
                    opponents=opponents,
                ),
                space,
                owner,
                any_icon=card_is_boosted(personal_card_for_instance(card_id), owner),
                recalled_post_id=recalled_post_id,
            )
        )
    )


def apply_graft_partner(state: GameState, action: DomainAction) -> RuleResult:
    """Put the partner into play and queue its Agent box on the effect frame."""

    if action not in legal_graft_partner_actions(state, action.actor):
        raise ValueError("action is not a legal Graft partner choice")
    player = action.actor
    partner_id = str(dict(action.arguments)["card_id"])
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    space_id = context_str(context, "space_id", owner=_PARTNER_LABEL)
    placed_id = context_str(context, "card_id", owner=_PARTNER_LABEL)
    owner = state.players[player]
    from_row = partner_id in state.imperium_row
    imperium_row, imperium_deck = (
        take_imperium_row_card(state, partner_id)
        if from_row
        else (state.imperium_row, state.imperium_deck)
    )
    # Urgent Shigawire: "The next Bene Gesserit card you play this round has
    # all Agent icons and, added to its Agent box: draw a card." [Urgent
    # Shigawire card]. A graft plays two cards [Immortality p. 10] and "Both
    # played cards are considered to have “sent” the Agent, no matter which
    # card’s icon you use." [Immortality p. 10], so a Bene Gesserit partner
    # is a card played: it takes a boost still pending -- the placed card
    # took it first when it is Bene Gesserit too (``agent_turn``) -- and the
    # draw is added to its box, box 1 (user ruling 2026-10-12, OQ-107: "1.
    # 짝도 받음"). Its "all Agent icons" reach the space only where the
    # partner's icons send the Agent (Usurp, ``card_is_boosted`` above).
    partner_boosted = card_is_boosted(personal_card_for_instance(partner_id), owner)
    # Ghola borrows the other card's box, whichever side it is on.
    partner = borrowed_agent_card(personal_card_for_instance(partner_id), placed_id)
    placed = borrowed_agent_card(personal_card_for_instance(placed_id), partner_id)
    # Chairdog: "At the start of your Reveal turn, return the other grafted
    # card from play to your hand" [card face]. Adopted designer ruling
    # (docs/rules/designer-rulings-audit.md): "Chairdog: graft 시점에 좌석에
    # 기록되므로 Chairdog가 먼저 trash돼도 되돌림" -- the return is recorded
    # on the seat as the pair is grafted, so it holds even when the partner's
    # box trashes Chairdog first (Dissecting Kit, Beguiling Pheromones) and
    # Chairdog's own box then expires (OQ-022). Ghola copying Chairdog's box
    # returns Chairdog the same way.
    chairdog_returns = tuple(
        other_id
        for card, other_id in ((placed, partner_id), (partner, placed_id))
        if card.agent_effect is _CHAIRDOG_RETURN
    )
    next_owner = replace(
        owner,
        bene_gesserit_boost_pending=(
            owner.bene_gesserit_boost_pending and not partner_boosted
        ),
        hand=tuple(card_id for card_id in owner.hand if card_id != partner_id),
        in_play=(*owner.in_play, partner_id),
        # Usurp: the borrowed Row card is trashed when the turn closes.
        usurped_row_card_id=partner_id if from_row else owner.usurped_row_card_id,
        chairdog_return_card_ids=(
            *owner.chairdog_return_card_ids,
            *chairdog_returns,
        ),
    )
    popped = replace(
        state,
        players=replace_player(state.players, next_owner),
        imperium_row=imperium_row,
        imperium_deck=imperium_deck,
        decision_stack=state.decision_stack[:-1],
    )
    effect_frame, effect_context = current_agent_effect_context(popped)
    if not isinstance(effect_frame.decision, PlayerDecision):
        raise RuntimeError("the Graft partner needs the owner's effect frame")
    space = BOARD_SPACES_BY_ID[space_id]
    pending = agent_effect_is_available(
        partner.agent_effect, next_owner, space, partner_id
    )
    effect_context["graft_card_id"] = partner_id
    effect_context["graft_pending_effect"] = pending
    if partner_boosted:
        # The added draw waits for its own step, box 1's (OQ-106, OQ-107).
        add_boost_draw(effect_context, partner_id)
    # Ghola "copies the entire Agent box of the card it's grafted to"
    # [Immortality p. 14], and the boosted card's draw was "added to its
    # Agent box" [Urgent Shigawire card]: the copy has it too, as its own
    # step in Ghola's box (user ruling 2026-10-12, OQ-107: "그럼 부스트
    # 받은거까지 복사되는게 맞는거 아니야?" -> "그래 고치자"). Ghola itself
    # is no Bene Gesserit card [Immortality p. 14], so it never takes the
    # boost: the boosted card is the other one, placed or partner.
    boosted_ids = pending_boost_draws(effect_context)
    for ghola_id, other_id in ((placed_id, partner_id), (partner_id, placed_id)):
        if other_id in boosted_ids and card_is_ghola(
            personal_card_for_instance(ghola_id)
        ):
            add_boost_draw(effect_context, ghola_id)
    if effect_context.get("units_deploy_blocked") is not True and any(
        isinstance(card, ImperiumCardEntry) and card.allows_recruited_troop_deployment
        for card in (partner, placed)
    ):
        # "You gain the effects on both cards" [Immortality p. 10]: Sardaukar
        # Coordination's "You may deploy any troops you recruit this turn to
        # the Conflict." [Sardaukar Coordination card] holds whichever card's
        # icon sent the Agent, as when it is the placed card (agent_turn).
        # It grants no garrison allowance, so the existing-troop limit stays.
        effect_context["pending_combat_deployment"] = True
    effect_context["graft_pending_icons"] = ",".join(
        agent_card_icons_at_placement(partner.agent_effect, next_owner.leader_id)
        if pending
        else ()
    )
    if effect_context["pending_agent_effect"] is not True:
        # The placed card's Bond-gated box was judged before the partner
        # was in play; the partner may provide the Bond now, and Ghola's
        # box is the partner's.
        if agent_effect_is_available(placed.agent_effect, next_owner, space, placed_id):
            effect_context["pending_agent_effect"] = True
            effect_context["pending_agent_icons"] = ",".join(
                agent_card_icons_at_placement(placed.agent_effect, next_owner.leader_id)
            )
    if (pending and holds_space_influence(partner.agent_effect)) or (
        effect_context["pending_agent_effect"] is True
        and holds_space_influence(placed.agent_effect)
    ):
        # Subversive Advisor's "gain two Influence instead of one" holds the
        # space's Influence on either side of the graft, as for a placed
        # card (agent_turn): never the space's 1 plus the card's 2.
        effect_context["pending_faction_influence"] = False
    next_state = replace(
        popped,
        decision_stack=(
            *popped.decision_stack[:-1],
            with_context(effect_frame, effect_context),
        ),
    )
    grafted = GameEvent(
        event_id=f"round:{state.round_number}:player:{player}:graft:{partner_id}",
        kind="card_grafted",
        payload=(
            ("card_id", partner_id),
            ("from_row", from_row),
            ("placed_card_id", placed_id),
            ("player", player),
            ("space_id", space_id),
        ),
    )
    if not partner_boosted:
        return RuleResult(state=next_state, events=(grafted,))
    boost = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:shigawire:{partner_id}"
        ),
        kind="agent_card_boost_consumed",
        payload=(("card_id", partner_id), ("player", player)),
    )
    return RuleResult(state=next_state, events=(grafted, boost))


def trash_usurped_card(state: GameState, player: int) -> RuleResult:
    """Usurp: "trash that card at the end of your turn." [card face].

    The owner's ``finish_agent_turn`` trashes the borrowed card, as an
    ordinary trash: it reaches the owner's trash pile and its "when this
    card is trashed" trigger resolves (OQ-054, user ruling 2026-09-08). The
    owner's Agent-turn frame is still open, so what the trigger recruits or
    gains is this turn's (user ruling 2026-10-01, OQ-095 (5)). A card that
    already left every owned zone (trashed earlier in the turn) needs
    nothing more.
    """

    owner = state.players[player]
    card_id = owner.usurped_row_card_id
    if not card_id:
        raise ValueError("the player holds no Usurped Row card")
    source = f"round:{state.round_number}:player:{player}:usurp_trash"
    cleared = replace(
        state,
        players=replace_player(state.players, replace(owner, usurped_row_card_id="")),
    )
    event = GameEvent(
        event_id=f"{source}:{card_id}",
        kind="usurped_card_trashed",
        payload=(("card_id", card_id), ("player", player)),
    )
    if card_id not in (*owner.hand, *owner.deck, *owner.discard_pile, *owner.in_play):
        return RuleResult(state=cleared, events=(event,))
    trashed = trash_personal_card(
        cleared,
        player,
        card_id,
        source=source,
        allow_deck=True,
    )
    return RuleResult(state=trashed.state, events=(event, *trashed.events))
