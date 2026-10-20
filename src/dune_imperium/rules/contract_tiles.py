"""Giving a Contract tile to a seat (leaf: only frame helpers)."""

from copy import replace

from dune_imperium.content.bloodlines.tech_abilities import tech_draws_on
from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.content.uprising.effect_dsl import (
    OnContractCompleted,
    RevealContractsTakeOne,
)
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    OWED_CARD,
    OWED_ORIGIN_CHOAM_TRANSPORTS,
    FrameKind,
    draw_waits_for_owner,
    hold_draw,
)


def owe_contract_completion_draw(state: GameState, owner: PlayerState) -> PlayerState:
    """CHOAM Transports: "When you complete a contract: draw a card" [Tech tile].

    "The card draw from CHOAM Transports is triggered as soon as the
    contract is completed and can't be deferred." (Message from designer,
    docs/rules/designer-rulings-audit.md). Inside the owner's own turn the
    card is its own step, the one right after the completing step, with
    nothing of the owner's in between, so the completion stays undoable
    (user decision 2026-10-10, OQ-106, ``draw_is_immediate``). Anywhere else
    (a Conflict reward, the Arrakeen Scouts step) it is owed to the engine's
    post-step draw (``tech.draw_owed_tech_cards``) so a discard reshuffle
    never interrupts the completing effect. ``state`` is the state the
    completion happens in (its turn and round).
    """

    draws = tech_draws_on(owner.tech_ids, OnContractCompleted)
    if not draws:
        return owner
    if draw_waits_for_owner(state, owner.player_id):
        return hold_draw(
            owner,
            OWED_CARD,
            OWED_ORIGIN_CHOAM_TRANSPORTS,
            f"round:{state.round_number}:player:{owner.player_id}:tech_draw",
        )
    return replace(owner, tech_cards_owed=owner.tech_cards_owed + draws)


def receive_contract(
    state: GameState, owner: PlayerState, instance_id: str
) -> PlayerState:
    """Give ``owner`` a Contract tile: active, or completed at once [Main p. 16].

    ``state`` is the state the tile is taken in (CHOAM Transports' draw for
    an Immediate tile, ``owe_contract_completion_draw``).
    """

    definition = contract_for_instance(instance_id)
    if definition.requires_intrigue_trash:
        # The Bloodlines Immediate is paid by trashing an Intrigue card
        # [Bloodlines p. 2]: the tile waits in the active zone while the
        # taker chooses the card in ``contract_intrigue_trash_frame`` and
        # ``apply_contract_intrigue_trash`` completes it.
        return replace(
            owner,
            active_contract_ids=(*owner.active_contract_ids, instance_id),
        )
    if definition.completes_immediately:
        # An Immediate tile completes the moment it is taken [Main p. 16]:
        # it waits active until the taker's step completes it and opens its
        # reward window (``contracts.complete_immediate_contract``, OQ-112).
        return replace(
            owner,
            active_contract_ids=(*owner.active_contract_ids, instance_id),
        )
    return replace(
        owner,
        active_contract_ids=(*owner.active_contract_ids, instance_id),
    )


def contract_intrigue_trash_frame(
    player: int,
    instance_id: str,
    *,
    source: str,
) -> DecisionFrame:
    """Return the frame in which the taker of the Bloodlines Immediate trashes.

    "Requires an Intrigue card": the tile cannot be taken without one, and
    trashing it is the price of the printed reward [Bloodlines p. 2].
    """

    return DecisionFrame(
        kind=FrameKind.CONTRACT_INTRIGUE_TRASH,
        frame_id=f"{source}:intrigue_trash",
        decision=PlayerDecision(
            owner=player,
            prompt="Trash an Intrigue card for the Immediate Contract",
        ),
        context=(
            ("contract_id", instance_id),
            ("source", source),
            ("turn_owner", player),
        ),
    )


def contract_reveal_is_possible(
    state: GameState, reward: RevealContractsTakeOne
) -> bool:
    """Return whether the bank holds every Contract ``reward`` must reveal.

    "Reveal three contracts from the bank. Take one and trash the other
    two." [Coercive Negotiation card]. Intrigue cards reshuffle when their
    deck runs out [FAQ p. 2], but no rule refills the Contract bank, so with
    fewer than three left the card cannot be used at all (OQ-064, user
    ruling 2026-09-26): "3장이 없으면 Coercive Negotiation을 아예 사용할 수
    없는게 맞다 ... 사용 후 효과가 없는게 아니라 아예 사용을 못 하는거지".
    """

    return state.config.choam_module and len(state.contract_bank) >= reward.count
