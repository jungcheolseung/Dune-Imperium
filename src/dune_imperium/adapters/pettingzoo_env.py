"""PettingZoo AEC adapter for complete four-player Uprising games."""

from typing import Any

import numpy as np
from gymnasium import spaces
from pettingzoo import AECEnv  # type: ignore[import-untyped]

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
    encode_player_view,
)
from dune_imperium.config import RulesetConfig
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings

type AgentId = str
type Observation = dict[str, np.ndarray[Any, np.dtype[np.integer[Any]]]]

WINNER_REWARD = 1.0
LOSER_REWARD = -1.0 / 3.0
_MAX_CONSECUTIVE_CHANCE_STEPS = 64


class DuneImperiumUprisingEnv(
    AECEnv[AgentId, Observation, int]  # type: ignore[misc]
):
    """Four-player AEC environment that plays one full game per episode.

    Chance decisions such as deck reshuffles resolve internally through a
    ``ChanceResolver`` seeded with the episode seed, so agents only ever act
    on player decisions and one seed reproduces the entire episode. The
    episode ends when the game reaches ``FINISHED``; the sole winner under
    the official standings receives ``+1`` and every other seat ``-1/3``.
    """

    metadata = {
        "name": "dune_imperium_uprising_v1",
        "render_modes": ["ansi"],
        "is_parallelizable": False,
    }

    def __init__(
        self,
        render_mode: str | None = None,
        *,
        choam_module: bool = False,
        max_steps: int = 30_000,
    ) -> None:
        super().__init__()
        if render_mode not in (None, "ansi"):
            raise ValueError("render_mode must be None or 'ansi'")
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.render_mode = render_mode
        self.config = RulesetConfig(choam_module=choam_module)
        self.engine = UprisingRulesEngine()
        self.codec = ActionCodec(self.config)
        self.max_steps = max_steps
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
        self._chance: ChanceResolver | None = None
        self._steps_taken = 0
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
        self._chance = ChanceResolver(seed=self._seed)
        self._steps_taken = 0
        self.agents = self.possible_agents.copy()
        self.rewards = dict.fromkeys(self.agents, 0.0)
        self._cumulative_rewards = dict.fromkeys(self.agents, 0.0)
        self.terminations = dict.fromkeys(self.agents, False)
        self.truncations = dict.fromkeys(self.agents, False)
        self.infos = {
            agent: {"observation_version": OBSERVATION_VERSION}
            for agent in self.agents
        }
        self._advance_chance()
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
            "observation": np.asarray(encode_player_view(view), dtype=np.int32),
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
        domain_action = self.codec.decode(action, player)
        self._state = self.engine.apply(state, domain_action).state
        self._steps_taken += 1
        self._advance_chance()

        if self._require_state().phase is GamePhase.FINISHED:
            self._finish_episode()
        elif self._steps_taken >= self.max_steps:
            self.truncations = dict.fromkeys(self.agents, True)
            self._accumulate_rewards()
            self._deads_step_first()
        else:
            self._accumulate_rewards()
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

    def _advance_chance(self) -> None:
        """Resolve pending chance decisions until a player must act."""

        chance = self._chance
        if chance is None:
            raise RuntimeError("reset() must be called before using the environment")
        for _ in range(_MAX_CONSECUTIVE_CHANCE_STEPS):
            decision = self.engine.current_decision(self._require_state())
            if not isinstance(decision, ChanceDecision):
                return
            outcome = chance.resolve(decision)
            self._state = self.engine.apply(self._require_state(), outcome).state
        raise RuntimeError("too many consecutive chance decisions")

    def _finish_episode(self) -> None:
        standings = final_standings(self._require_state())
        for standing in standings:
            agent = _agent_id(standing.player)
            self.rewards[agent] = (
                WINNER_REWARD if standing.rank == 1 else LOSER_REWARD
            )
            self.infos[agent] = {
                "observation_version": OBSERVATION_VERSION,
                "rank": standing.rank,
                "victory_points": standing.victory_points,
            }
        self.terminations = dict.fromkeys(self.agents, True)
        self._accumulate_rewards()
        self._deads_step_first()

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


def env(
    render_mode: str | None = None,
    *,
    choam_module: bool = False,
    max_steps: int = 30_000,
) -> DuneImperiumUprisingEnv:
    """Return the standard full-game AEC environment."""

    return DuneImperiumUprisingEnv(
        render_mode=render_mode,
        choam_module=choam_module,
        max_steps=max_steps,
    )


def _agent_id(player: int) -> AgentId:
    return f"player_{player}"
