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
    control_space_ids: tuple[str, ...]
    combat_strength: int
    high_council: bool
    maker_hooks: bool
    in_play: tuple[str, ...]
    trashed: tuple[str, ...]
    objective_ids: tuple[str, ...]


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
    players: tuple[PublicPlayerView, ...] = ()
    private: PrivatePlayerView | None = None
    current_conflict_ids: tuple[str, ...] = ()
    imperium_row: tuple[str, ...] = ()
    intrigue_discard: tuple[str, ...] = ()
    reserve_stacks: tuple[tuple[str, int], ...] = ()
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
        players=tuple(_public_player_view(candidate) for candidate in state.players),
        private=PrivatePlayerView(
            deck_size=len(owner.deck),
            hand=owner.hand,
            discard_pile=owner.discard_pile,
            intrigue_cards=owner.intrigue_cards,
        ),
        current_conflict_ids=state.current_conflict_ids,
        imperium_row=state.imperium_row,
        intrigue_discard=state.intrigue_discard,
        reserve_stacks=state.reserve_stacks,
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
        control_space_ids=player.control_space_ids,
        combat_strength=player.combat_strength,
        high_council=player.high_council,
        maker_hooks=player.maker_hooks,
        in_play=player.in_play,
        trashed=player.trashed,
        objective_ids=player.objective_ids,
    )
