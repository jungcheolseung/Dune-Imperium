"""Giving a Contract tile to a seat (leaf: no rule imports)."""

from dataclasses import replace

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.core.player import PlayerState


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
