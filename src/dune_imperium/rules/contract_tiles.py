"""Giving a Contract tile to a seat (leaf: no rule imports)."""

from dataclasses import replace

from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.core.player import PlayerState


def receive_contract(owner: PlayerState, instance_id: str) -> PlayerState:
    """Give ``owner`` a Contract tile: active, or completed at once [Main p. 16]."""

    definition = contract_for_instance(instance_id)
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
            )
        ):
            raise NotImplementedError(
                "Immediate Contracts with non-Solari rewards are not implemented"
            )
        return replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + reward.solari,
            ),
            completed_contract_ids=(*owner.completed_contract_ids, instance_id),
            contracts_completed_turn=owner.contracts_completed_turn + 1,
        )
    return replace(
        owner,
        active_contract_ids=(*owner.active_contract_ids, instance_id),
    )
