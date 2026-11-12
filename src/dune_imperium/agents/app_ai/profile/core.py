"""The contract of the ``AIProfile`` port: every method, declared once.

``Profile`` (``profile/__init__.py``) combines the mixins that implement these methods:
``economy.py`` (spec/profile-economy.md), ``influence.py``
(spec/profile-influence-uprising.md), ``combat.py`` (spec/profile-combat.md),
``immortality.py`` (spec/immortality.md §2) and ``tech.py`` (spec/rix-tech.md). Each
method here only declares the signature, the app method it ports and the spec file;
calling an unimplemented one raises ``NotImplementedError``. Mixins call each other
through these declarations, so a method is always reached by its name here and never
re-declared with another signature.

Naming: the app's method name in snake_case without ``Get``/``get_``. Values the app
returns as ``AIValueSummer<double>`` return a ``Summer``, ``AIValueSummer<int>`` an
``IntSummer``, ``double`` a ``float``. The specs are kept privately.
"""

import random
from collections.abc import Callable, Sequence

from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.data.constants import AIConstants
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.core.player import PlayerState


class ProfileCore:
    """State shared by every mixin, and the declarations of all methods.

    One instance per decision (the app clears its per-decision caches at the
    start of every ``MakeChoice``: ``_isClimax``, ``_isFinalRound``,
    ``_cachedBuyGains``; ``_cachedUprisingConflicts`` holds static content).
    """

    def __init__(
        self, ctx: AppContext, constants: AIConstants, rng: random.Random
    ) -> None:
        self.ctx = ctx
        self.C = constants
        self.rng = rng
        self._is_climax: bool | None = None
        self._is_final_round: bool | None = None
        self._cached_buy_gains: dict[int, float] = {}
        # ``abilities.bloodlines_cards.unlock_value``'s per-decision caches
        # (pair values and finished results) and its re-entrancy flag. They
        # live here, not at module level, so concurrent games (the server's
        # threadpool) never share them.
        self.unlock_pair_values: dict[tuple[str, str], float | None] = {}
        self.unlock_values: dict[tuple[object, ...], float] = {}
        self.unlocking = False
        # ``ServoReceiversAcquiredAbility``'s re-entrancy flag (P7: a
        # Leader's Signet whose value prices the Tech tiles again,
        # docs/app-ai-plan.md 14.3).
        self.servo_receivers_valuing = False
        # ``RapidEngineeringAbility.is_bad_intrigue``'s re-entrancy flag (P7:
        # Sonic Snoopers' value asks the hand's Intrigues while the check
        # values the Tech tiles, docs/app-ai-plan.md 14.3).
        self.rapid_engineering_checking = False

    # ===========================================================================
    # Economy — spec/profile-economy.md (implemented in economy.py)
    # ===========================================================================

    def game_arc(self) -> int:
        """``GetGameArc``: 0 Early, 1 Mid, 2 Late."""
        raise NotImplementedError

    def is_climax(self) -> bool:
        """``IsClimax`` (cached per decision)."""
        raise NotImplementedError

    def is_final_round(self) -> bool:
        """``IsFinalRound`` (cached per decision)."""
        raise NotImplementedError

    def possible_end_of_round_score(self, seat: int) -> int:
        """``GetPossibleEndOfRoundScore``."""
        raise NotImplementedError

    def select_for_game_arc(self, choices: Sequence[float]) -> float:
        """``SelectForGameArc``."""
        raise NotImplementedError

    def is_solari_short(self) -> bool:
        """``IsSolariShort``."""
        raise NotImplementedError

    def is_solari_long(self) -> bool:
        """``IsSolariLong``."""
        raise NotImplementedError

    def is_spice_short(self) -> bool:
        """``IsSpiceShort``."""
        raise NotImplementedError

    def is_troop_short(self) -> bool:
        """``IsTroopShort``."""
        raise NotImplementedError

    def is_water_long(self) -> bool:
        """``IsWaterLong``."""
        raise NotImplementedError

    def abundance_level(self, attr: Attr) -> int:
        """``GetAbundanceLevel`` (-1 when no thresholds)."""
        raise NotImplementedError

    def resource_value(
        self, attr: Attr, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetResourceValue``."""
        raise NotImplementedError

    def persuasion_value(self, amount: int) -> float:
        """``GetPersuasionValue``."""
        raise NotImplementedError

    def solari_value(self, amount: int) -> float:
        """``GetSolariValue``."""
        raise NotImplementedError

    def spice_value(self, amount: int) -> float:
        """``GetSpiceValue``."""
        raise NotImplementedError

    def water_value(self, amount: int) -> float:
        """``GetWaterValue``."""
        raise NotImplementedError

    def specimen_value(self, amount: int) -> float:
        """``GetSpecimenValue``."""
        raise NotImplementedError

    def strength_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetStrengthValue``."""
        raise NotImplementedError

    def troop_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetTroopValue``."""
        raise NotImplementedError

    def dreadnought_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetDreadnoughtValue``."""
        raise NotImplementedError

    def sandworm_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetSandWormValue``."""
        raise NotImplementedError

    def victory_point_value(self, amount: int) -> float:
        """``GetVictoryPointValue`` (doubles at a literal 10)."""
        raise NotImplementedError

    def card_draw_value(self) -> float:
        """``CardDrawValue``."""
        raise NotImplementedError

    def card_draw_value_with_buy_gains(self) -> float:
        """``CardDrawValueWithBuyGains``."""
        raise NotImplementedError

    def intrigue_value(self) -> float:
        """``IntrigueValue``."""
        raise NotImplementedError

    def trash_card_value(self) -> float:
        """``TrashCardValue``."""
        raise NotImplementedError

    def minimum_acquire_value(self) -> float:
        """``MinimumAcquireValue``."""
        raise NotImplementedError

    def trash_mod(self) -> float:
        """``TrashMod``."""
        raise NotImplementedError

    def swordmaster_value(self) -> float:
        """``SwordmasterValue``."""
        raise NotImplementedError

    def high_council_value(self) -> float:
        """``HighCouncilValue``."""
        raise NotImplementedError

    def foldspace_value(self) -> float:
        """``FoldspaceValue``."""
        raise NotImplementedError

    def mentat_value(self) -> float:
        """``MentatValue``."""
        raise NotImplementedError

    def control_solari_value(self) -> float:
        """``ControlSolariValue``."""
        raise NotImplementedError

    def control_spice_value(self) -> float:
        """``ControlSpiceValue``."""
        raise NotImplementedError

    def control_value_avg(self) -> float:
        """``ControlValueAvg``."""
        raise NotImplementedError

    def discard_value(self) -> float:
        """``DiscardValue``."""
        raise NotImplementedError

    def buy_gains(self, amount: int) -> float:
        """``GetBuyGains`` (knapsack; cached per amount)."""
        raise NotImplementedError

    def buy_value(self) -> float:
        """``GetBuyValue``."""
        raise NotImplementedError

    def possible_persuasion(self) -> int:
        """``PossiblePersuasion``."""
        raise NotImplementedError

    def possible_persuasion_gain(self) -> int:
        """``PossiblePersuasionGain``."""
        raise NotImplementedError

    def predict_card_buys(self, with_persuasion: int) -> list[Entity]:
        """``PredictCardBuys`` (0/1 knapsack over buyable cards)."""
        raise NotImplementedError

    def acquire_cards_by_value(self, with_persuasion: int) -> list[Entity]:
        """``GetAcquireCardsByValue``."""
        raise NotImplementedError

    def deck_agent_icons(self) -> dict[str, int]:
        """``DeckAgentIcons`` (draw pile only)."""
        raise NotImplementedError

    def synergy_mod(self, card: Entity) -> Summer:
        """``GetSynergyMod`` (capped at SynergyModMaxValue)."""
        raise NotImplementedError

    def friendship_mod(self, card: Entity) -> Summer:
        """``GetFriendshipMod``."""
        raise NotImplementedError

    def acquire_effects_value(self, card: Entity) -> Summer:
        """``GetAcquireEffectsValue``."""
        raise NotImplementedError

    def specific_acquire_bonus(self, card: Entity) -> Summer:
        """``GetSpecificAcquireBonus``."""
        raise NotImplementedError

    def acquire_value(self, card: Entity) -> Summer:
        """``ImperiumPlayable.AcquireValue``."""
        raise NotImplementedError

    def spice_for_spice_refinery(self) -> int:
        """``GetSpiceForSpiceRefinery``."""
        raise NotImplementedError

    def spice_for_sell_melange(self) -> int:
        """``GetSpiceForSellMelange``."""
        raise NotImplementedError

    def can_agent_ability_be_played_with_space(
        self, space: Entity | None, attr: Attr, amount: int
    ) -> bool:
        """``CanAgentAbilityBePlayedWithSpace``."""
        raise NotImplementedError

    def card_to_trash(
        self, targets: Sequence[Entity], min_trash_value: float
    ) -> tuple[Entity | None, float]:
        """``GetCardToTrash`` (shuffles; non-strict keep-best)."""
        raise NotImplementedError

    def opponent_ratio(self, condition: Callable[[PlayerState], bool]) -> float:
        """``OpponentRatio``."""
        raise NotImplementedError

    def ordered_players(self) -> list[int]:
        """``GetOrderedPlayers`` (seats)."""
        raise NotImplementedError

    def has_turn_before_opponent_next_round(self, opponent: int) -> bool:
        """``HasTurnBeforeOpponentNextRound``."""
        raise NotImplementedError

    def bad_intrigue_cards_in_hand(self) -> list[Entity]:
        """``GetBadIntrigueCardsInHand``."""
        raise NotImplementedError

    def discard_order(
        self, cards: Sequence[Entity], spacing_guild_bonus: bool
    ) -> list[Entity]:
        """``ChooseDiscardEvaluator``/``GetDiscardOrder`` (profile-economy §12)."""
        raise NotImplementedError

    # ===========================================================================
    # Influence, spies, contracts, hooks, wall, recall —
    # spec/profile-influence-uprising.md (implemented in influence.py)
    # ===========================================================================

    def gain_influence_value(
        self,
        faction: str,
        amount: int,
        current_rank: int = -1,
        has_alliance: bool = False,
    ) -> Summer:
        """``GetGainInfluenceValue`` (current_rank -1 = read it)."""
        raise NotImplementedError

    def has_or_would_gain_alliance(self, faction: str, amount: int) -> bool:
        """``HasOrWouldGainAlliance``."""
        raise NotImplementedError

    def best_influence_exchange(
        self,
        lose_amount: int,
        gain_amount: int,
        lose_factions: Sequence[str] | None = None,
        gain_factions: Sequence[str] | None = None,
    ) -> tuple[str | None, str | None, float]:
        """``GetBestInfluenceExchange`` (shuffles; strict keep-best)."""
        raise NotImplementedError

    def spy_value(self) -> Summer:
        """``SpyValue``."""
        raise NotImplementedError

    def recall_spy_value(self) -> Summer:
        """``RecallSpyValue``."""
        raise NotImplementedError

    def post_value(self, post: Entity, unseen_network: bool = False) -> float:
        """``ObservationPost.PostValue``."""
        raise NotImplementedError

    def best_post(
        self, posts: Sequence[Entity], unseen_network: bool = False
    ) -> tuple[Entity | None, float]:
        """``GetBestPost``."""
        raise NotImplementedError

    def post_selection(
        self,
        posts: Sequence[Entity],
        take: int,
        best: bool,
        unseen_network: bool = False,
    ) -> tuple[list[Entity], float]:
        """``GetPostSelection`` (shuffle, then sort)."""
        raise NotImplementedError

    def recall_spy(self, spies: Sequence[Entity]) -> tuple[Entity | None, float]:
        """``GetRecallSpy`` (the spy on the worst post)."""
        raise NotImplementedError

    def recall_spies(
        self, spies: Sequence[Entity], take: int
    ) -> tuple[list[Entity], float]:
        """``GetRecallSpies``."""
        raise NotImplementedError

    def want_contract_count(self) -> int:
        """``WantContractCount``."""
        raise NotImplementedError

    def gain_contract_value(self) -> Summer:
        """``GainContractValue``."""
        raise NotImplementedError

    def best_contract(
        self, contracts: Sequence[Entity], forced: bool
    ) -> tuple[Entity | None, float]:
        """``GetBestContract``."""
        raise NotImplementedError

    def contract_acquire_value(self, contract: Entity) -> Summer:
        """``ContractPlayable.AcquireValue``."""
        raise NotImplementedError

    def battle_icon_value(self, icon: str) -> Summer:
        """``GetBattleIconValue``."""
        raise NotImplementedError

    def maker_hooks_value(self) -> float:
        """``MakerHooksValue``."""
        raise NotImplementedError

    def opponent_maker_hooks_ratio(self) -> float:
        """``GetOpponentMakerHooksRatio``."""
        raise NotImplementedError

    def recall_agent_value(self) -> float:
        """``RecallAgentValue``."""
        raise NotImplementedError

    def recall_agent(self, agents: Sequence[Entity]) -> Entity | None:
        """``GetRecallAgent`` (50 MINUS the space value; shuffles)."""
        raise NotImplementedError

    def space_value_for_player(self, space: Entity) -> Summer:
        """``Space.ValueForPlayer`` (merge of its abilities)."""
        raise NotImplementedError

    def blow_wall_value(self) -> Summer:
        """``BlowWallValue``."""
        raise NotImplementedError

    def should_blow_wall(self) -> bool:
        """``ShouldBlowWall``."""
        raise NotImplementedError

    def intrigue_blow_wall(self) -> bool:
        """``IntrigueBlowWall``."""
        raise NotImplementedError

    def lady_jessica_return_memories(self) -> bool:
        """``LadyJessicaReturnMemories``."""
        raise NotImplementedError

    # ===========================================================================
    # Conflict and combat — spec/profile-combat.md (implemented in combat.py)
    # ===========================================================================

    def deploy_value(self, owner: Entity) -> float:
        """``DeployValue``."""
        raise NotImplementedError

    def conflict_competitors(self) -> float:
        """``ConflictCompetitors``."""
        raise NotImplementedError

    def conflict_posture_bounds(self) -> tuple[float, float]:
        """``ConflictPostureBounds``: (lower, upper)."""
        raise NotImplementedError

    def combat_positioning(self) -> float:
        """``GetCombatPositioning``."""
        raise NotImplementedError

    def combat_posture_mod(self) -> float:
        """``GetCombatPostureMod`` (dead: every caller passes false)."""
        raise NotImplementedError

    def uprising_conflicts(self) -> tuple[Archetype, ...]:
        """``GetUprisingConflicts`` (static catalogue)."""
        raise NotImplementedError

    def relative_conflict_value(self) -> Summer:
        """``RelativeConflictValue``."""
        raise NotImplementedError

    def current_conflict_interest(self) -> Summer:
        """``CurrentConflictInterest``."""
        raise NotImplementedError

    def intrigue_hand_strength_value(self) -> int:
        """``IntrigueHandStrengthValue``."""
        raise NotImplementedError

    def est_opponent_strength(self, opponent: int) -> IntSummer:
        """``EstOpponentStrength``."""
        raise NotImplementedError

    def est_strength(self) -> IntSummer:
        """``EstStrength``."""
        raise NotImplementedError

    def potential_strength(self, max_units: int) -> IntSummer:
        """``PotentialStrength``."""
        raise NotImplementedError

    def units_to_deploy(self, garrison_troops: int, max_units: int) -> int:
        """``GetUnitsToDeploy``: how many garrison troops to deploy."""
        raise NotImplementedError

    def units_to_deploy_split(
        self, garrison_troops: int, garrison_dreadnoughts: int, max_units: int
    ) -> tuple[int, int]:
        """``GetUnitsToDeploy`` over troops and dreadnoughts:
        ``(dreadnoughts, troops)`` to deploy."""
        raise NotImplementedError

    def troops_to_retreat(self, max_troops: int) -> int:
        """``GetTroopsToRetreat``."""
        raise NotImplementedError

    def estimated_conflict_rank(self, bonus_strength: int = 0) -> int | None:
        """``EstimatedConflictRank`` (1-based)."""
        raise NotImplementedError

    def current_conflict_rank(self, bonus_strength: int = 0) -> int | None:
        """``CurrentConflictRank`` (1-based)."""
        raise NotImplementedError

    def current_combat_order(self) -> list[int]:
        """``GetCurrentCombatOrder`` (seats, strongest first)."""
        raise NotImplementedError

    def expected_combat_order(self) -> list[int]:
        """``GetExpectedCombatOrder``."""
        raise NotImplementedError

    def expected_combat_order_with_strength(self) -> list[tuple[int, int]]:
        """``GetExpectedCombatOrderWithStrength``."""
        raise NotImplementedError

    def heighliner_potential_player(self) -> int | None:
        """``GetHeighlinerPotentialPlayer``."""
        raise NotImplementedError

    def has_highliner_potential(self, seat: int | None = None) -> bool:
        """``HasHighlinerPotential``."""
        raise NotImplementedError

    def worm_potential_player(self, space_id: str) -> int | None:
        """``GetWormPotentialPlayer``."""
        raise NotImplementedError

    def has_worm_potential(self, seat: int | None = None) -> bool:
        """``HasWormPotential``."""
        raise NotImplementedError

    def has_worm_potential_a(self, seat: int | None = None) -> bool:
        """``HasWormPotentialA``."""
        raise NotImplementedError

    def has_worm_potential_b(self, seat: int | None = None) -> bool:
        """``HasWormPotentialB``."""
        raise NotImplementedError

    def can_play_to_desert_space_with_hooks(self, seat: int, space_id: str) -> bool:
        """``CanPlayToDesertSpaceWithHooks``."""
        raise NotImplementedError

    def should_play_retreat_intrigue(
        self,
        card_name: str,
        not_first_extra_strength: int,
        first_extra_strength: int,
        retreat_units: int,
    ) -> int:
        """``ShouldPlayRetreatIntrigue``."""
        raise NotImplementedError

    def should_play_troop_intrigue(
        self,
        card_name: str,
        not_first_extra_strength: int,
        first_extra_strength: int,
        troops: int,
    ) -> int:
        """``ShouldPlayTroopIntrigue``."""
        raise NotImplementedError

    def play_intrigue_for_final_round_or_hand_size(self, card: Entity) -> int:
        """``PlayIntrigueForFinalRoundOrHandSize``."""
        raise NotImplementedError

    def trash_intrigue_value(self) -> float:
        """``TrashIntrigueValue``."""
        raise NotImplementedError

    # ===========================================================================
    # Immortality — spec/immortality.md §2 (implemented in immortality.py;
    # the Immortality terms of GetResourceValue, AcquireValue, GetSynergyMod,
    # GetAcquireEffectsValue, GetCardToTrash and DeployValue live in the
    # methods above)
    # ===========================================================================

    def research_value(self) -> Summer:
        """``ResearchValue``."""
        raise NotImplementedError

    def tleilaxu_value(self, amount: int) -> Summer:
        """``TleilaxuValue(int amount)``."""
        raise NotImplementedError

    def research_space_value(self, space_id: str) -> Summer:
        """``ResearchTrack.SpaceValue(space, forPlayer)``.

        ``space_id`` is our research space id (``c<col>r<row>``).
        """
        raise NotImplementedError

    def tleilaxu_row_cards(self) -> list[Entity]:
        """``Playmat.TleilaxuRow.children.OfType<ImperiumPlayable>()``.

        Not an app method: the row the Immortality readers iterate
        (Reclaimed Forces first; ``AppContext.tleilaxu_row``).
        """
        raise NotImplementedError
