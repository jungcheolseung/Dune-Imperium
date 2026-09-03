"""Stable integer encoding for structured Uprising actions."""

from dataclasses import dataclass, field
from numbers import Integral

from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contracts import contract_instance_ids
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    ImperiumCardEntry,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import (
    intrigue_card_for_instance,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.uprising.leaders import (
    FEYD_TRACK_START,
    FEYD_TRAINING_TRACK,
    leaders_for_choam,
)
from dune_imperium.content.uprising.objectives import objectives_for_players
from dune_imperium.content.uprising.reserve import (
    RESERVE_STACKS,
    ReserveStackDefinition,
)
from dune_imperium.content.uprising.starting_cards import (
    STARTING_DECK,
    StartingCardEntry,
)
from dune_imperium.content.uprising.types import AgentIcon, BattleIcon
from dune_imperium.core.actions import ActionValue, DomainAction

ACTION_CODEC_VERSION = 85
MAX_DEPLOYMENT_COUNT = 12
MAX_INTRIGUE_DEPLOYMENT = 4


@dataclass(frozen=True, slots=True)
class ActionTemplate:
    """Actor-neutral action stored at one stable catalog index."""

    action_id: str
    arguments: tuple[tuple[str, ActionValue], ...] = ()

    def __post_init__(self) -> None:
        DomainAction(self.action_id, actor=0, arguments=self.arguments)


@dataclass(frozen=True, slots=True)
class ActionCodec:
    """Encode, decode, and mask actions for one ruleset configuration."""

    config: RulesetConfig
    catalog: tuple[ActionTemplate, ...] = field(init=False)
    _indices: dict[ActionTemplate, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        catalog = _build_catalog(self.config)
        indices = {template: index for index, template in enumerate(catalog)}
        if len(indices) != len(catalog):
            raise RuntimeError("action catalog contains duplicate templates")
        object.__setattr__(self, "catalog", catalog)
        object.__setattr__(self, "_indices", indices)

    @property
    def size(self) -> int:
        """Return the fixed discrete action-space size."""

        return len(self.catalog)

    def encode(self, action: DomainAction) -> int:
        """Return the integer ID for one structured action."""

        if not 0 <= action.actor < self.config.players:
            raise ValueError("action actor must identify a configured player")
        template = ActionTemplate(
            action_id=action.action_id,
            arguments=_normalize_arguments(action.arguments, action.actor),
        )
        try:
            return self._indices[template]
        except KeyError as error:
            raise ValueError("action is not present in this codec version") from error

    def decode(self, action_index: int, actor: int) -> DomainAction:
        """Reconstruct an actor-owned structured action from an integer ID."""

        if isinstance(action_index, bool) or not isinstance(action_index, Integral):
            raise TypeError("action index must be an integer")
        index = int(action_index)
        if not 0 <= index < self.size:
            raise ValueError("action index is outside the catalog")
        if not 0 <= actor < self.config.players:
            raise ValueError("action actor must identify a configured player")
        template = self.catalog[index]
        return DomainAction(
            action_id=template.action_id,
            actor=actor,
            arguments=_denormalize_arguments(template.arguments, actor),
        )

    def legal_action_mask(
        self,
        legal_actions: tuple[DomainAction, ...],
    ) -> tuple[int, ...]:
        """Return a fixed-width binary mask for the supplied legal actions."""

        mask = [0] * self.size
        for action in legal_actions:
            mask[self.encode(action)] = 1
        return tuple(mask)


def _build_catalog(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    # The OQ-007 Leader draft picks are part of every catalog so the
    # leader_draft ruleset option never changes the action space; the mask
    # simply keeps them illegal outside a draft setup.
    templates: list[ActionTemplate] = [
        ActionTemplate(
            action_id="pick_leader",
            arguments=(("leader_id", leader.leader_id),),
        )
        for leader in leaders_for_choam(config.choam_module)
    ]
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            "decline_combat_reward",
            "decline_combat_reward_trash",
            "decline_agent_card_trash",
            "decline_agent_card_payment",
            "decline_corrinth_city_payment",
            "decline_agent_card_intrigue_payment",
            "decline_agent_card_discard",
            "decline_agent_card_acquisition",
            "decline_control_defense",
            "decline_leader_board_repeat",
            "decline_leader_card_trash",
            "decline_leader_signet_payment",
            "decline_other_memories",
            "decline_gather_intelligence",
            "decline_reveal_spy_recall",
            "decline_reveal_influence_exchange",
            "decline_reveal_card_trash",
            "decline_reveal_sandworm",
            "decline_reveal_spice_influence",
            "decline_reveal_troop_retreat",
            "deploy_control_defense",
            "finish_reveal",
            "gain_five_reveal_solari",
            "gain_leader_signet_troop",
            "gain_two_reveal_strength",
            "pass_combat_intrigue",
            "pass_endgame_intrigue",
            "pay_agent_card_water",
            "pay_agent_card_spice",
            "pay_agent_card_spice_for_sandworm",
            "pay_agent_card_spice_for_sandworm_and_shield_wall",
            "pay_leader_board_repeat",
            "pay_leader_signet_solari",
            "pay_leader_signet_spice",
            "pay_reveal_water_for_sandworm",
            "take_high_council_from_reveal",
            "pay_combat_reward",
            "resolve_agent_card_effect",
            "resolve_board_effect",
            "resolve_desert_tactics_without_trash",
            "resolve_espionage_without_spy",
            "resolve_faction_influence",
            "retreat_leader_troop",
            "reveal_turn",
            "retreat_two_troops_for_reveal",
            "take_sietch_tabr_supplies",
            "take_sietch_tabr_water",
            "take_sietch_tabr_water_and_destroy_wall",
            "use_other_memories",
        )
    )
    if config.choam_module:
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in (
                "keep_contract_reveal_spice",
                "take_exhausted_contract_solari",
                "trash_contract_reveal_for_vp",
            )
        )
    templates.extend(_agent_turn_templates(config))
    templates.extend(_endgame_wild_templates(config))
    templates.extend(
        ActionTemplate(
            action_id="deploy_troops",
            arguments=(("count", count),),
        )
        for count in range(MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="recall_agent_for_agent_card",
            arguments=(("space_id", space.space_id),),
        )
        for space in BOARD_SPACES
    )
    templates.extend(
        ActionTemplate(
            action_id="recall_agent_for_imperial_privilege",
            arguments=(("space_id", space.space_id),),
        )
        for space in BOARD_SPACES
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    imperium_instances = imperium_deck_instance_ids(
        config.choam_module, config.promo_cards
    )
    intrigue_instances = intrigue_deck_instance_ids(config.choam_module)
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    if config.choam_module:
        for action_id in ("take_contract", "complete_contract"):
            templates.extend(
                ActionTemplate(
                    action_id=action_id,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in contract_instance_ids()
            )
        templates.extend(
            ActionTemplate(
                action_id="recall_agent_for_contract",
                arguments=(("space_id", space.space_id),),
            )
            for space in BOARD_SPACES
        )
    templates.extend(
        ActionTemplate(
            action_id="pay_agent_card_intrigue_and_spice",
            arguments=(("intrigue_card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="discard_intrigue_for_imperial_privilege",
            arguments=(("card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="play_intrigue",
            arguments=(("card_id", instance_id), ("option", option)),
        )
        for instance_id in intrigue_instances
        for option in range(len(intrigue_card_for_instance(instance_id).options))
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_intrigue_faction",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_intrigue_faction",
            arguments=(("alliance_recipient", recipient), ("faction", faction.value)),
        )
        for faction in Faction
        for recipient in range(config.players)
    )
    templates.extend(_trash_templates(config, "choose_intrigue_discard"))
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            "detonate_shield_wall",
            "keep_shield_wall",
            "decline_intrigue_trash",
            "decline_intrigue_trigger",
            "decline_intrigue_spy",
            "decline_imperial_privilege_intrigue",
            "resolve_intrigue_rewards",
        )
    )
    templates.extend(_trash_templates(config, "trash_intrigue_card"))
    templates.extend(
        ActionTemplate(
            action_id="deploy_intrigue_troops", arguments=(("count", count),)
        )
        for count in range(1, MAX_INTRIGUE_DEPLOYMENT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="retreat_intrigue_troops", arguments=(("count", count),)
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_intrigue_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_intrigue_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    templates.extend(
        ActionTemplate(
            action_id="flip_battle_card",
            arguments=(("card_id", conflict.card.card_id),),
        )
        for conflict in CONFLICTS
    )
    for action_id in ("manipulate_imperium_row", "acquire_manipulated_imperium"):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in imperium_instances
        )
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium_with_solari",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve_with_solari",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    for space_id in ("deep_desert", "hagga_basin", "imperial_basin"):
        templates.append(
            ActionTemplate(
                action_id="harvest_maker_spice",
                arguments=(("space_id", space_id),),
            )
        )
    for space_id in ("deep_desert", "hagga_basin"):
        templates.append(
            ActionTemplate(
                action_id="summon_maker_sandworms",
                arguments=(("space_id", space_id),),
            )
        )
    post_ids = tuple(post.post_id for post in OBSERVATION_POSTS)
    templates.extend(
        ActionTemplate(
            action_id="gather_intelligence",
            arguments=(("post_id", post_id),),
        )
        for post_id in post_ids
    )
    for action_id in (
        "place_acquisition_spy",
        "place_agent_card_spy",
        "place_intrigue_spy",
        "place_leader_spy",
        "place_trigger_spy",
        "recall_spy_for_intrigue",
        "recall_spy_for_leader",
        "recall_spy_for_leader_placement",
        "recall_spy_for_trigger",
        "place_reveal_spy",
        "recall_spy_for_acquisition",
        "recall_spy_for_agent_card",
        "recall_spy_for_espionage",
        "recall_spy_for_reveal",
        "recall_spy_for_reveal_placement",
        "resolve_espionage_place_spy",
        *(
            ("place_contract_spy", "recall_spy_for_contract")
            if config.choam_module
            else ()
        ),
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("post_id", post_id),),
            )
            for post_id in post_ids
        )
    templates.extend(
        ActionTemplate(
            action_id="place_combat_reward_spy",
            arguments=(("post_id", post_id),),
        )
        for post_id in post_ids
    )
    templates.extend(
        ActionTemplate(
            action_id="recall_spies_for_reveal",
            arguments=(
                ("first_post_id", first_post_id),
                ("second_post_id", second_post_id),
            ),
        )
        for index, first_post_id in enumerate(post_ids)
        for second_post_id in post_ids[index + 1 :]
    )
    templates.extend(
        ActionTemplate(
            action_id="recall_spies_for_combat_reward",
            arguments=(
                ("first_post_id", first_post_id),
                ("second_post_id", second_post_id),
            ),
        )
        for first_post_id in post_ids
        for second_post_id in post_ids
        if first_post_id != second_post_id
    )
    for action_id in (
        "choose_agent_card_influence",
        "choose_combat_reward_influence",
        "choose_distinct_combat_reward_influence",
        "choose_leader_signet_influence",
        "choose_shipping_influence",
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
    templates.extend(
        ActionTemplate(
            action_id="exchange_reveal_influence",
            arguments=(
                ("gained_faction", gained_faction.value),
                ("lost_faction", lost_faction.value),
            ),
        )
        for lost_faction in Faction
        for gained_faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="exchange_reveal_influence",
            arguments=(
                ("alliance_recipient", recipient),
                ("gained_faction", gained_faction.value),
                ("lost_faction", lost_faction.value),
            ),
        )
        for lost_faction in Faction
        for gained_faction in Faction
        for recipient in range(config.players)
    )
    templates.extend(
        ActionTemplate(
            action_id="pay_reveal_spice_influence",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="advance_feyd_track",
            arguments=(("space_id", space.space_id),),
        )
        for space in FEYD_TRAINING_TRACK
        if space.space_id != FEYD_TRACK_START
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_leader_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_leader_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in RESERVE_STACKS
    )
    templates.extend(_trash_templates(config, "trash_leader_card"))
    templates.extend(_trash_templates(config, "trash_agent_card"))
    templates.extend(_trash_templates(config, "select_long_live_fighters_draw"))
    templates.extend(_trash_templates(config, "select_long_live_fighters_discard"))
    templates.extend(_trash_templates(config, "discard_agent_card"))
    templates.extend(_trash_templates(config, "discard_opponent_card"))
    templates.extend(_trash_templates(config, "trash_reveal_card"))
    templates.extend(_trash_templates(config, "trash_combat_reward_card"))
    templates.extend(_trash_templates(config, "trash_card_for_desert_tactics"))
    templates.extend(_trash_templates(config, "select_corrinth_city_discard"))
    templates.extend(_trash_templates(config, "pay_corrinth_city"))
    return tuple(sorted(templates, key=_template_sort_key))


def _agent_turn_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    templates: list[ActionTemplate] = []
    for starting_card in STARTING_DECK:
        templates.extend(_agent_turn_templates_for_card("starter", starting_card))
    for reserve_card in RESERVE_STACKS:
        templates.extend(_agent_turn_templates_for_card("reserve", reserve_card))
    for imperium_card in IMPERIUM_CARDS:
        if (
            imperium_card.play_data_complete
            and (config.choam_module or not imperium_card.choam_only)
            and (config.promo_cards or not imperium_card.promo)
        ):
            templates.extend(_agent_turn_templates_for_card("imperium", imperium_card))
    return tuple(templates)


def _agent_turn_templates_for_card(
    prefix: str,
    card: StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry,
) -> tuple[ActionTemplate, ...]:
    templates: list[ActionTemplate] = []
    for copy in range(card.copies):
        card_id = f"{prefix}:{card.card.card_id}:{copy}"
        for space in BOARD_SPACES:
            if (
                space.agent_icon not in card.agent_icons
                and AgentIcon.SPY not in card.agent_icons
            ):
                continue
            cost_options: tuple[int | None, ...] = (
                tuple(range(len(space.cost_options)))
                if space.dynamic_cost is None and len(space.cost_options) > 1
                else (None,)
            )
            infiltration_post_ids: tuple[str | None, ...] = (
                None,
                *(
                    post.post_id
                    for post in OBSERVATION_POSTS
                    if space.space_id in post.connected_space_ids
                ),
            )
            for cost_option in cost_options:
                for infiltrate_post_id in infiltration_post_ids:
                    arguments: list[tuple[str, ActionValue]] = [("card_id", card_id)]
                    if cost_option is not None:
                        arguments.append(("cost_option", cost_option))
                    if infiltrate_post_id is not None:
                        arguments.append(("infiltrate_post_id", infiltrate_post_id))
                    arguments.append(("space_id", space.space_id))
                    templates.append(
                        ActionTemplate(
                            action_id="agent_turn",
                            arguments=tuple(arguments),
                        )
                    )
    return tuple(templates)


def _endgame_wild_templates(
    config: RulesetConfig,
) -> tuple[ActionTemplate, ...]:
    battle_cards = (
        *((conflict.card.card_id, conflict.battle_icon) for conflict in CONFLICTS),
        *(
            (objective.objective_id, objective.battle_icon)
            for objective in objectives_for_players(config.players)
        ),
    )
    wild_card_ids = tuple(
        card_id for card_id, icon in battle_cards if icon is BattleIcon.WILD
    )
    matching_card_ids = tuple(
        card_id for card_id, icon in battle_cards if icon not in (None, BattleIcon.WILD)
    )
    return tuple(
        ActionTemplate(
            action_id="match_endgame_wild_icon",
            arguments=(
                ("matching_card_id", matching_card_id),
                ("wild_card_id", wild_card_id),
            ),
        )
        for wild_card_id in wild_card_ids
        for matching_card_id in matching_card_ids
    )


def _trash_templates(
    config: RulesetConfig,
    action_id: str,
) -> tuple[ActionTemplate, ...]:
    return tuple(
        ActionTemplate(
            action_id=action_id,
            arguments=(("card_id", card_id),),
        )
        for card_id in _personal_card_instance_ids(config)
    )


def _personal_card_instance_ids(config: RulesetConfig) -> tuple[str, ...]:
    card_ids = [
        f"starter:{card.card.card_id}:{copy}"
        for card in STARTING_DECK
        for copy in range(card.copies)
    ]
    card_ids.extend(
        imperium_deck_instance_ids(config.choam_module, config.promo_cards)
    )
    card_ids.extend(
        f"reserve:{stack.card.card_id}:{copy}"
        for stack in RESERVE_STACKS
        for copy in range(stack.copies)
    )
    return tuple(card_ids)


def _normalize_arguments(
    arguments: tuple[tuple[str, ActionValue], ...],
    actor: int,
) -> tuple[tuple[str, ActionValue], ...]:
    prefix = f"player:{actor}:starter:"
    return tuple(
        (key, f"starter:{value.removeprefix(prefix)}")
        if isinstance(value, str) and value.startswith(prefix)
        else (key, value)
        for key, value in arguments
    )


def _denormalize_arguments(
    arguments: tuple[tuple[str, ActionValue], ...],
    actor: int,
) -> tuple[tuple[str, ActionValue], ...]:
    return tuple(
        (key, f"player:{actor}:{value}")
        if isinstance(value, str) and value.startswith("starter:")
        else (key, value)
        for key, value in arguments
    )


def _template_sort_key(template: ActionTemplate) -> tuple[str, str]:
    return template.action_id, repr(template.arguments)
