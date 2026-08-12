"""Stateless transition engine contract and validation boundary."""

import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, validate_chance_outcome
from dune_imperium.core.decisions import ChanceDecision, Decision, PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash


class IllegalActionError(ValueError):
    """Raised when an action is not legal at the current decision."""


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Internal result returned after a validated action is resolved."""

    state: GameState
    events: tuple[GameEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class Transition:
    """Externally visible result of applying one action."""

    state: GameState
    action: DomainAction | ChanceOutcome
    events: tuple[GameEvent, ...]
    next_decision: Decision | None


class RulesEngine(ABC):
    """Template for deterministic, library-independent rules engines."""

    def reset(self, config: RulesetConfig, seed: int) -> GameState:
        """Create and validate an initial state."""

        if seed < 0:
            raise ValueError("seed must not be negative")
        state = self._initial_state(config, seed)
        if state.config != config or state.seed != seed or state.revision != 0:
            raise RuntimeError("initial state does not match reset inputs")
        return state

    def current_decision(self, state: GameState) -> Decision | None:
        """Return the top pending decision, if any."""

        if not state.decision_stack:
            return None
        return state.decision_stack[-1].decision

    @abstractmethod
    def _initial_state(self, config: RulesetConfig, seed: int) -> GameState:
        """Build rules-specific initial state."""

    @abstractmethod
    def legal_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        """Enumerate all legal actions for ``player``."""

    @abstractmethod
    def _apply_legal(self, state: GameState, action: DomainAction) -> RuleResult:
        """Resolve an action already proven legal."""

    @abstractmethod
    def observe(self, state: GameState, player: int) -> PlayerView:
        """Create a deterministic player-scoped view."""

    def apply(
        self,
        state: GameState,
        action: DomainAction | ChanceOutcome,
    ) -> Transition:
        """Validate and apply a player action or chance outcome."""

        if isinstance(action, ChanceOutcome):
            return self._apply_chance_outcome(state, action)
        return self._apply_player_action(state, action)

    def _apply_player_action(
        self,
        state: GameState,
        action: DomainAction,
    ) -> Transition:
        """Validate and apply one player-owned action."""

        decision = self.current_decision(state)
        if not isinstance(decision, PlayerDecision):
            raise IllegalActionError(
                "the current decision does not accept a player action"
            )
        if action.actor != decision.owner:
            raise IllegalActionError("action actor does not own the current decision")
        if action not in self.legal_actions(state, action.actor):
            raise IllegalActionError("action is not legal in the current state")

        original_hash = canonical_state_hash(state)
        result = self._apply_legal(state, action)
        return self._finish_transition(state, original_hash, action, result)

    def _apply_chance_outcome(
        self,
        state: GameState,
        outcome: ChanceOutcome,
    ) -> Transition:
        """Validate and apply one recorded chance result."""

        decision = self.current_decision(state)
        if not isinstance(decision, ChanceDecision):
            raise IllegalActionError("the current decision does not accept chance")
        try:
            validate_chance_outcome(decision, outcome)
        except ValueError as error:
            raise IllegalActionError(str(error)) from error
        original_hash = canonical_state_hash(state)
        result = self._apply_chance(state, outcome)
        return self._finish_transition(state, original_hash, outcome, result)

    def _apply_chance(self, state: GameState, outcome: ChanceOutcome) -> RuleResult:
        """Resolve a valid chance result; override when chance is used."""

        del state, outcome
        raise NotImplementedError("this rules engine has no chance transitions")

    def _finish_transition(
        self,
        state: GameState,
        original_hash: str,
        action: DomainAction | ChanceOutcome,
        result: RuleResult,
    ) -> Transition:
        """Enforce transition invariants shared by every input type."""

        if canonical_state_hash(state) != original_hash:
            raise RuntimeError("rules mutated the input state")
        if result.state.revision != state.revision:
            raise RuntimeError("rules must leave revision updates to RulesEngine")

        next_state = replace(
            result.state,
            revision=state.revision + 1,
            event_log=(*state.event_log, *result.events),
        )
        return Transition(
            state=next_state,
            action=action,
            events=result.events,
            next_decision=self.current_decision(next_state),
        )

    def clone_full(self, state: GameState) -> GameState:
        """Return an independent full-information state clone."""

        return copy.deepcopy(state)

    def is_terminal(self, state: GameState) -> bool:
        """Return whether no further game transition may occur."""

        return state.phase is GamePhase.FINISHED
