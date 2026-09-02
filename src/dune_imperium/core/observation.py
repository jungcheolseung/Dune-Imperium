"""Player-scoped, immutable observations with explicit redaction."""

from dataclasses import dataclass

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState


@dataclass(frozen=True, slots=True)
class PublicPlayerView:
    """Public board and supply information for one seat.

    Hand, deck, and held-Intrigue identities deliberately have no field here,
    so adapter code cannot accidentally recover them from an opponent's view.
    """

    player: int
    leader_id: str | None
    leader_face_id: str | None
    victory_points: int
    resources: Resources
    influence: Influence
    # Zone sizes are public by project convention (OQ-010): the physical
    # game leaves every pile and hand count visible while identities stay
    # governed by the explicit visibility rules.
    hand_size: int
    deck_size: int
    intrigue_card_count: int
    # Hand cards every seat can identify because they entered the hand
    # through a public move (OQ-010); see ``PlayerState.hand_public``.
    hand_public: tuple[str, ...]
    agents_available: int
    agent_locations: tuple[str, ...]
    swordmaster_acquired: bool
    troops_supply: int
    troops_garrison: int
    troops_conflict: int
    memories: int
    sandworms_conflict: int
    spies_supply: int
    spy_post_ids: tuple[str, ...]
    alliance_faction_ids: tuple[str, ...]
    control_space_ids: tuple[str, ...]
    combat_strength: int
    has_revealed: bool
    high_council: bool
    maker_hooks: bool
    feyd_track_space: str
    in_play: tuple[str, ...]
    # Every card reaches a discard pile face up (acquired cards [Main p. 13],
    # played and revealed cards after Clean Up [Main pp. 9, 12, 20], cards
    # discarded from hand), so the pile stays re-checkable by everyone until a
    # reshuffle hides it again (OQ-010 ruling 1).
    discard_pile: tuple[str, ...]
    trashed: tuple[str, ...]
    intrigue_faceup: tuple[str, ...]
    imperium_set_aside: tuple[str, ...]
    objective_ids: tuple[str, ...]
    won_conflict_ids: tuple[str, ...]
    face_down_battle_card_ids: tuple[str, ...]
    active_contract_ids: tuple[str, ...]
    # A completed Contract was face up while active and its completion was
    # announced before it flipped [Main p. 16], so its identity stays public
    # like a flipped battle card (OQ-010 ruling 2).
    completed_contract_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrivatePlayerView:
    """Card identities available only to the observing player."""

    deck_size: int
    hand: tuple[str, ...]
    intrigue_cards: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlayerView:
    """Information safe to expose to a single player or policy."""

    player: int
    revision: int
    phase: GamePhase
    round_number: int = 0
    first_player: int | None = None
    # Public summary of the pending decision frame: its kind, the deciding
    # player (None for chance), and the acting turn owner when the frame
    # tracks one. Frame contexts stay unexposed until each kind's fields are
    # individually cleared for visibility.
    decision_kind: str | None = None
    decision_owner: int | None = None
    turn_owner: int | None = None
    reveal_order: tuple[int, ...] = ()
    endgame_intrigue_complete: bool = False
    players: tuple[PublicPlayerView, ...] = ()
    private: PrivatePlayerView | None = None
    current_conflict_ids: tuple[str, ...] = ()
    combat_intrigue_complete: bool = False
    combat_rewards_resolved: bool = False
    imperium_row: tuple[str, ...] = ()
    imperium_removed: tuple[str, ...] = ()
    # Intrigue cards already played (hence revealed [Main p. 7]) whose
    # choices are still being resolved; they stay in the owner's held set
    # until the last slot resolves, so the public view names them here.
    intrigue_resolving: tuple[str, ...] = ()
    intrigue_discard: tuple[str, ...] = ()
    intrigue_trash: tuple[str, ...] = ()
    contract_bank_size: int = 0
    face_up_contract_ids: tuple[str, ...] = ()
    sardaukar_contract_ids: tuple[str, ...] = ()
    # The face-up six-Leader pool of the OQ-007 draft option, public to
    # everyone for the whole game (empty without the option).
    leader_draft_pool: tuple[str, ...] = ()
    reserve_stacks: tuple[tuple[str, int], ...] = ()
    shield_wall_present: bool = True
    maker_bonus_spice: tuple[tuple[str, int], ...] = ()
    public_data: tuple[tuple[str, ActionValue], ...] = ()
    private_data: tuple[tuple[str, ActionValue], ...] = ()


_RESOLVING_INTRIGUE_FRAME_KINDS = frozenset({"intrigue_choice"})


def resolving_intrigue_ids(state: GameState) -> tuple[str, ...]:
    """Return played Intrigue cards still held while their choices resolve."""

    resolving: list[str] = []
    for frame in state.decision_stack:
        if str(frame.kind) not in _RESOLVING_INTRIGUE_FRAME_KINDS:
            continue
        card_id = dict(frame.context).get("card_id")
        if isinstance(card_id, str) and card_id not in resolving:
            resolving.append(card_id)
    return tuple(resolving)


def observe_state(state: GameState, player: int) -> PlayerView:
    """Return a pure view that omits every hidden card ordering and opponent secret."""

    if not 0 <= player < state.config.players:
        raise ValueError("observer must identify a configured player")
    if len(state.players) != state.config.players:
        raise ValueError("cannot observe a state without every configured player")

    owner = state.players[player]
    decision_kind: str | None = None
    decision_owner: int | None = None
    turn_owner_value: int | None = None
    if state.decision_stack:
        frame = state.decision_stack[-1]
        decision_kind = str(frame.kind)
        if isinstance(frame.decision, PlayerDecision):
            decision_owner = frame.decision.owner
        context_owner = dict(frame.context).get("turn_owner")
        if isinstance(context_owner, int) and not isinstance(context_owner, bool):
            turn_owner_value = context_owner
    return PlayerView(
        player=player,
        revision=state.revision,
        phase=state.phase,
        round_number=state.round_number,
        first_player=state.first_player,
        decision_kind=decision_kind,
        decision_owner=decision_owner,
        turn_owner=turn_owner_value,
        reveal_order=state.reveal_order,
        endgame_intrigue_complete=state.endgame_intrigue_complete,
        players=tuple(_public_player_view(candidate) for candidate in state.players),
        private=PrivatePlayerView(
            deck_size=len(owner.deck),
            hand=owner.hand,
            intrigue_cards=owner.intrigue_cards,
        ),
        current_conflict_ids=state.current_conflict_ids,
        combat_intrigue_complete=state.combat_intrigue_complete,
        combat_rewards_resolved=state.combat_rewards_resolved,
        imperium_row=state.imperium_row,
        imperium_removed=state.imperium_removed,
        intrigue_resolving=resolving_intrigue_ids(state),
        intrigue_discard=state.intrigue_discard,
        intrigue_trash=state.intrigue_trash,
        contract_bank_size=len(state.contract_bank),
        face_up_contract_ids=state.face_up_contract_ids,
        sardaukar_contract_ids=state.sardaukar_contract_ids,
        leader_draft_pool=state.leader_draft_pool,
        reserve_stacks=state.reserve_stacks,
        shield_wall_present=state.shield_wall_present,
        maker_bonus_spice=state.maker_bonus_spice,
    )


def _public_player_view(player: PlayerState) -> PublicPlayerView:
    return PublicPlayerView(
        player=player.player_id,
        leader_id=player.leader_id,
        leader_face_id=player.leader_face_id,
        victory_points=player.victory_points,
        resources=player.resources,
        influence=player.influence,
        hand_size=len(player.hand),
        deck_size=len(player.deck),
        intrigue_card_count=len(player.intrigue_cards),
        hand_public=player.hand_public,
        agents_available=player.agents_available,
        agent_locations=player.agent_locations,
        swordmaster_acquired=player.swordmaster_acquired,
        troops_supply=player.troops_supply,
        troops_garrison=player.troops_garrison,
        troops_conflict=player.troops_conflict,
        memories=player.memories,
        sandworms_conflict=player.sandworms_conflict,
        spies_supply=player.spies_supply,
        spy_post_ids=player.spy_post_ids,
        alliance_faction_ids=player.alliance_faction_ids,
        control_space_ids=player.control_space_ids,
        combat_strength=player.combat_strength,
        has_revealed=player.has_revealed,
        high_council=player.high_council,
        maker_hooks=player.maker_hooks,
        feyd_track_space=player.feyd_track_space,
        in_play=player.in_play,
        discard_pile=player.discard_pile,
        trashed=player.trashed,
        intrigue_faceup=player.intrigue_faceup,
        imperium_set_aside=player.imperium_set_aside,
        objective_ids=player.objective_ids,
        won_conflict_ids=player.won_conflict_ids,
        face_down_battle_card_ids=player.face_down_battle_card_ids,
        active_contract_ids=player.active_contract_ids,
        completed_contract_ids=player.completed_contract_ids,
    )
