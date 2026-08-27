"""Player-scoped, immutable observations with explicit redaction."""

from dataclasses import dataclass

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState


@dataclass(frozen=True, slots=True)
class PublicPlayerView:
    """Public board and supply information for one seat.

    Private Imperium and Intrigue identities deliberately have no field here, so
    adapter code cannot accidentally recover them from an opponent's view.
    """

    player: int
    leader_id: str | None
    victory_points: int
    resources: Resources
    influence: Influence
    agents_available: int
    agent_locations: tuple[str, ...]
    swordmaster_acquired: bool
    troops_supply: int
    troops_garrison: int
    troops_conflict: int
    sandworms_conflict: int
    spies_supply: int
    spy_post_ids: tuple[str, ...]
    alliance_faction_ids: tuple[str, ...]
    control_space_ids: tuple[str, ...]
    combat_strength: int
    has_revealed: bool
    high_council: bool
    maker_hooks: bool
    in_play: tuple[str, ...]
    trashed: tuple[str, ...]
    objective_ids: tuple[str, ...]
    won_conflict_ids: tuple[str, ...]
    face_down_battle_card_ids: tuple[str, ...]
    active_contract_ids: tuple[str, ...]
    completed_contract_count: int


@dataclass(frozen=True, slots=True)
class PrivatePlayerView:
    """Card identities available only to the observing player."""

    deck_size: int
    hand: tuple[str, ...]
    discard_pile: tuple[str, ...]
    intrigue_cards: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlayerView:
    """Information safe to expose to a single player or policy."""

    player: int
    revision: int
    phase: GamePhase
    round_number: int = 0
    first_player: int | None = None
    reveal_order: tuple[int, ...] = ()
    declined_endgame_wild_card_ids: tuple[str, ...] = ()
    players: tuple[PublicPlayerView, ...] = ()
    private: PrivatePlayerView | None = None
    current_conflict_ids: tuple[str, ...] = ()
    combat_intrigue_complete: bool = False
    combat_rewards_resolved: bool = False
    imperium_row: tuple[str, ...] = ()
    intrigue_discard: tuple[str, ...] = ()
    intrigue_trash: tuple[str, ...] = ()
    contract_bank_size: int = 0
    face_up_contract_ids: tuple[str, ...] = ()
    reserve_stacks: tuple[tuple[str, int], ...] = ()
    shield_wall_present: bool = True
    maker_bonus_spice: tuple[tuple[str, int], ...] = ()
    public_data: tuple[tuple[str, ActionValue], ...] = ()
    private_data: tuple[tuple[str, ActionValue], ...] = ()


def observe_state(state: GameState, player: int) -> PlayerView:
    """Return a pure view that omits every hidden card ordering and opponent secret."""

    if not 0 <= player < state.config.players:
        raise ValueError("observer must identify a configured player")
    if len(state.players) != state.config.players:
        raise ValueError("cannot observe a state without every configured player")

    owner = state.players[player]
    return PlayerView(
        player=player,
        revision=state.revision,
        phase=state.phase,
        round_number=state.round_number,
        first_player=state.first_player,
        reveal_order=state.reveal_order,
        declined_endgame_wild_card_ids=state.declined_endgame_wild_card_ids,
        players=tuple(_public_player_view(candidate) for candidate in state.players),
        private=PrivatePlayerView(
            deck_size=len(owner.deck),
            hand=owner.hand,
            discard_pile=owner.discard_pile,
            intrigue_cards=owner.intrigue_cards,
        ),
        current_conflict_ids=state.current_conflict_ids,
        combat_intrigue_complete=state.combat_intrigue_complete,
        combat_rewards_resolved=state.combat_rewards_resolved,
        imperium_row=state.imperium_row,
        intrigue_discard=state.intrigue_discard,
        intrigue_trash=state.intrigue_trash,
        contract_bank_size=len(state.contract_bank),
        face_up_contract_ids=state.face_up_contract_ids,
        reserve_stacks=state.reserve_stacks,
        shield_wall_present=state.shield_wall_present,
        maker_bonus_spice=state.maker_bonus_spice,
    )


def _public_player_view(player: PlayerState) -> PublicPlayerView:
    return PublicPlayerView(
        player=player.player_id,
        leader_id=player.leader_id,
        victory_points=player.victory_points,
        resources=player.resources,
        influence=player.influence,
        agents_available=player.agents_available,
        agent_locations=player.agent_locations,
        swordmaster_acquired=player.swordmaster_acquired,
        troops_supply=player.troops_supply,
        troops_garrison=player.troops_garrison,
        troops_conflict=player.troops_conflict,
        sandworms_conflict=player.sandworms_conflict,
        spies_supply=player.spies_supply,
        spy_post_ids=player.spy_post_ids,
        alliance_faction_ids=player.alliance_faction_ids,
        control_space_ids=player.control_space_ids,
        combat_strength=player.combat_strength,
        has_revealed=player.has_revealed,
        high_council=player.high_council,
        maker_hooks=player.maker_hooks,
        in_play=player.in_play,
        trashed=player.trashed,
        objective_ids=player.objective_ids,
        won_conflict_ids=player.won_conflict_ids,
        face_down_battle_card_ids=player.face_down_battle_card_ids,
        active_contract_ids=player.active_contract_ids,
        completed_contract_count=len(player.completed_contract_ids),
    )
