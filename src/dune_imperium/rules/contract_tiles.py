"""Giving a Contract tile to a seat (leaf: only frame helpers)."""

from dataclasses import replace

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.frames import FrameKind


def owe_contract_completion_draw(owner: PlayerState) -> PlayerState:
    """CHOAM Transports: "When you complete a contract: draw a card" [Tech tile].

    The card is owed to the engine's post-step draw so a discard reshuffle
    never interrupts the completing effect.
    """

    if not has_tech(owner.tech_ids, TechAbility.CONTRACT_COMPLETION_DRAW):
        return owner
    return replace(owner, tech_cards_owed=owner.tech_cards_owed + 1)


def receive_contract(owner: PlayerState, instance_id: str) -> PlayerState:
    """Give ``owner`` a Contract tile: active, or completed at once [Main p. 16]."""

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
        reward = definition.reward
        if any(
            (
                reward.water,
                reward.troops,
                reward.personal_cards,
                reward.contracts,
                reward.spies,
                reward.influence,
                reward.intrigue_cards,
                reward.deep_cover_spies,
            )
        ):
            raise NotImplementedError(
                "Immediate Contracts with non-Solari rewards are not implemented"
            )
        return owe_contract_completion_draw(
            replace(
                owner,
                resources=replace(
                    owner.resources,
                    solari=owner.resources.solari + reward.solari,
                ),
                completed_contract_ids=(*owner.completed_contract_ids, instance_id),
                contracts_completed_turn=owner.contracts_completed_turn + 1,
            )
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
