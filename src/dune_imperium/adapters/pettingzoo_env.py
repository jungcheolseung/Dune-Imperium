"""PettingZoo AEC adapter for the one-round Uprising vertical slice."""

from typing import Any

import numpy as np
from gymnasium import spaces
from pettingzoo import AECEnv  # type: ignore[import-untyped]

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine

type AgentId = str
type Observation = dict[str, np.ndarray[Any, np.dtype[np.integer[Any]]]]

OBSERVATION_SIZE = 81
_PHASES = tuple(GamePhase)


class DuneImperiumUprisingEnv(
    AECEnv[AgentId, Observation, int]  # type: ignore[misc]
):
    """Four-player AEC environment that terminates after one complete round."""

    metadata = {
        "name": "dune_imperium_uprising_v0",
        "render_modes": ["ansi"],
        "is_parallelizable": False,
    }

    def __init__(self, render_mode: str | None = None) -> None:
        super().__init__()
        if render_mode not in (None, "ansi"):
            raise ValueError("render_mode must be None or 'ansi'")
        self.render_mode = render_mode
        self.config = RulesetConfig()
        self.engine = UprisingRulesEngine()
        self.codec = ActionCodec(self.config)
        self._observation_space = spaces.Dict(
            {
                "observation": spaces.Box(
                    low=0,
                    high=32767,
                    shape=(OBSERVATION_SIZE,),
                    dtype=np.int32,
                ),
                "action_mask": spaces.MultiBinary(self.codec.size),
            }
        )
        self._action_space: spaces.Discrete[np.int64] = spaces.Discrete(self.codec.size)
        self.possible_agents = [
            _agent_id(player) for player in range(self.config.players)
        ]
        self.agents: list[AgentId] = []
        self.agent_selection = self.possible_agents[0]
        self.rewards: dict[AgentId, float] = {}
        self._cumulative_rewards: dict[AgentId, float] = {}
        self.terminations: dict[AgentId, bool] = {}
        self.truncations: dict[AgentId, bool] = {}
        self.infos: dict[AgentId, dict[str, Any]] = {}
        self._state: GameState | None = None
        self._seed = 0

    def observation_space(self, agent: AgentId) -> spaces.Dict:
        self._validate_agent(agent)
        return self._observation_space

    def action_space(self, agent: AgentId) -> spaces.Discrete[np.int64]:
        self._validate_agent(agent)
        return self._action_space

    def reset(
        self,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        del options
        if seed is not None:
            if seed < 0:
                raise ValueError("seed must not be negative")
            self._seed = seed
        self._state = self.engine.reset(self.config, self._seed)
        self.agents = self.possible_agents.copy()
        self.rewards = dict.fromkeys(self.agents, 0.0)
        self._cumulative_rewards = dict.fromkeys(self.agents, 0.0)
        self.terminations = dict.fromkeys(self.agents, False)
        self.truncations = dict.fromkeys(self.agents, False)
        self.infos = {agent: {} for agent in self.agents}
        self._select_decision_owner()

    def observe(self, agent: AgentId) -> Observation:
        player = self._player_id(agent)
        state = self._require_state()
        view = self.engine.observe(state, player)
        mask = np.zeros(self.codec.size, dtype=np.int8)
        decision = self.engine.current_decision(state)
        if (
            agent in self.agents
            and not self.terminations[agent]
            and not self.truncations[agent]
            and isinstance(decision, PlayerDecision)
            and decision.owner == player
        ):
            legal = self.engine.legal_actions(state, player)
            mask = np.asarray(self.codec.legal_action_mask(legal), dtype=np.int8)
        return {
            "observation": _encode_view(view),
            "action_mask": mask,
        }

    def step(self, action: int | None) -> None:
        agent = self.agent_selection
        if self.terminations[agent] or self.truncations[agent]:
            self._was_dead_step(action)
            return
        if action is None:
            raise ValueError("a live agent requires an integer action")

        state = self._require_state()
        player = self._player_id(agent)
        self._cumulative_rewards[agent] = 0
        self._clear_rewards()
        previous_vp = tuple(owner.victory_points for owner in state.players)
        domain_action = self.codec.decode(action, player)
        self._state = self.engine.apply(state, domain_action).state
        for owner, before in zip(self._state.players, previous_vp, strict=True):
            self.rewards[_agent_id(owner.player_id)] = float(
                owner.victory_points - before
            )
        self._accumulate_rewards()

        if _round_finished(self._state):
            self.terminations = dict.fromkeys(self.agents, True)
            self._deads_step_first()
        else:
            self._select_decision_owner()

    def render(self) -> str | None:
        if self.render_mode is None:
            return None
        state = self._require_state()
        return (
            f"round={state.round_number} phase={state.phase.value} "
            f"revision={state.revision} current={self.agent_selection}"
        )

    def close(self) -> None:
        return None

    def _select_decision_owner(self) -> None:
        decision = self.engine.current_decision(self._require_state())
        if not isinstance(decision, PlayerDecision):
            raise RuntimeError("AEC environment requires a player decision")
        self.agent_selection = _agent_id(decision.owner)

    def _validate_agent(self, agent: AgentId) -> None:
        if agent not in self.possible_agents:
            raise ValueError("unknown PettingZoo agent ID")

    def _player_id(self, agent: AgentId) -> int:
        self._validate_agent(agent)
        return int(agent.removeprefix("player_"))

    def _require_state(self) -> GameState:
        if self._state is None:
            raise RuntimeError("reset() must be called before using the environment")
        return self._state


def env(render_mode: str | None = None) -> DuneImperiumUprisingEnv:
    """Return the standard one-round AEC environment."""

    return DuneImperiumUprisingEnv(render_mode=render_mode)


def _encode_view(view: PlayerView) -> np.ndarray[Any, np.dtype[np.int32]]:
    values = [
        view.round_number,
        _PHASES.index(view.phase),
        0 if view.first_player is None else view.first_player + 1,
        int(view.shield_wall_present),
        len(view.current_conflict_ids),
    ]
    for player in view.players:
        values.extend(
            (
                player.victory_points,
                player.resources.solari,
                player.resources.spice,
                player.resources.water,
                player.influence.emperor,
                player.influence.spacing_guild,
                player.influence.bene_gesserit,
                player.influence.fremen,
                player.agents_available,
                player.troops_supply,
                player.troops_garrison,
                player.troops_conflict,
                player.sandworms_conflict,
                player.spies_supply,
                player.combat_strength,
                int(player.has_revealed),
                int(player.high_council),
                int(player.maker_hooks),
            )
        )
    if view.private is None:
        raise RuntimeError("player observation is missing its private counts")
    values.extend(
        (
            view.private.deck_size,
            len(view.private.hand),
            len(view.private.discard_pile),
            len(view.private.intrigue_cards),
        )
    )
    if len(values) != OBSERVATION_SIZE:
        raise RuntimeError("observation encoder size does not match its space")
    return np.asarray(values, dtype=np.int32)


def _round_finished(state: GameState) -> bool:
    return state.phase in (GamePhase.ROUND_START, GamePhase.ENDGAME)


def _agent_id(player: int) -> AgentId:
    return f"player_{player}"
