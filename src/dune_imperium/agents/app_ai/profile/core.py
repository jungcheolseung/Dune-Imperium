"""The contract of the ``WormAIProfile`` port: every method, declared once.

``Profile`` (``profile/__init__.py``) combines the mixins that implement
these methods: ``economy.py`` (spec/profile-economy.md), ``influence.py``
(spec/profile-influence-uprising.md), ``combat.py``
(spec/profile-combat.md), ``immortality.py`` (spec/immortality.md §2) and
``tech.py`` (spec/rix-tech.md). Each method here only declares the signature, the
app method it ports (with its address in build dad97e20) and the spec file;
calling an unimplemented one raises ``NotImplementedError``. Mixins call each
other through these declarations, so a method is always reached by its name
here and never re-declared with another signature.

Naming: the app's method name in snake_case without ``Get``/``get_``.
Values the app returns as ``AIValueSummer<double>`` return a ``Summer``,
``AIValueSummer<int>`` an ``IntSummer``, ``double`` a ``float``.
Specs live in the assets checkout:
``reference/dune-steam-app/dad97e2021144d45b5b4f022e07bd3b3/analysis/ai/spec/``.
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

    # ===========================================================================
    # Economy — spec/profile-economy.md (implemented in economy.py)
    # ===========================================================================

    def game_arc(self) -> int:
        """``GetGameArc`` @0x4904790: 0 Early, 1 Mid, 2 Late."""
        raise NotImplementedError

    def is_climax(self) -> bool:
        """``get_IsClimax`` @0x4903d50 (cached per decision)."""
        raise NotImplementedError

    def is_final_round(self) -> bool:
        """``get_IsFinalRound`` @0x49043f0 (cached per decision)."""
        raise NotImplementedError

    def possible_end_of_round_score(self, seat: int) -> int:
        """``GetPossibleEndOfRoundScore`` @0x49045d0."""
        raise NotImplementedError

    def select_for_game_arc(self, choices: Sequence[float]) -> float:
        """``SelectForGameArc`` @0x4908c80."""
        raise NotImplementedError

    def abundance_level(self, attr: Attr) -> int:
        """``GetAbundanceLevel`` @0x4905770 (-1 when no thresholds)."""
        raise NotImplementedError

    def resource_value(
        self, attr: Attr, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetResourceValue`` @0x4905940."""
        raise NotImplementedError

    def persuasion_value(self, amount: int) -> float:
        """``GetPersuasionValue`` @0x4908890."""
        raise NotImplementedError

    def solari_value(self, amount: int) -> float:
        """``GetSolariValue`` @0x4908900."""
        raise NotImplementedError

    def spice_value(self, amount: int) -> float:
        """``GetSpiceValue`` @0x4908970."""
        raise NotImplementedError

    def water_value(self, amount: int) -> float:
        """``GetWaterValue`` @0x49089e0."""
        raise NotImplementedError

    def specimen_value(self, amount: int) -> float:
        """``GetSpecimenValue`` @0x4908a50."""
        raise NotImplementedError

    def strength_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetStrengthValue`` @0x4908ac0."""
        raise NotImplementedError

    def troop_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetTroopValue`` @0x4908b30."""
        raise NotImplementedError

    def dreadnought_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetDreadnoughtValue`` @0x4908ba0."""
        raise NotImplementedError

    def sandworm_value(
        self, amount: int, include_combat_posture_mod: bool = False
    ) -> float:
        """``GetSandWormValue`` @0x4908c10."""
        raise NotImplementedError

    def victory_point_value(self, amount: int) -> float:
        """``GetVictoryPointValue`` @0x490a030 (doubles at a literal 10)."""
        raise NotImplementedError

    def card_draw_value(self) -> float:
        """``get_CardDrawValue`` @0x4908cc0."""
        raise NotImplementedError

    def card_draw_value_with_buy_gains(self) -> float:
        """``CardDrawValueWithBuyGains`` @0x4908eb0."""
        raise NotImplementedError

    def intrigue_value(self) -> float:
        """``get_IntrigueValue`` @0x4908130."""
        raise NotImplementedError

    def trash_card_value(self) -> float:
        """``get_TrashCardValue`` @0x49091d0."""
        raise NotImplementedError

    def minimum_acquire_value(self) -> float:
        """``get_MinimumAcquireValue`` @0x49092e0."""
        raise NotImplementedError

    def trash_mod(self) -> float:
        """``TrashMod`` @0x49093f0."""
        raise NotImplementedError

    def swordmaster_value(self) -> float:
        """``get_SwordmasterValue`` @0x4909740."""
        raise NotImplementedError

    def high_council_value(self) -> float:
        """``get_HighCouncilValue`` @0x4909850."""
        raise NotImplementedError

    def foldspace_value(self) -> float:
        """``get_FoldspaceValue`` @0x4909960."""
        raise NotImplementedError

    def mentat_value(self) -> float:
        """``get_MentatValue`` @0x4909a70."""
        raise NotImplementedError

    def control_solari_value(self) -> float:
        """``get_ControlSolariValue`` @0x4909cb0."""
        raise NotImplementedError

    def control_spice_value(self) -> float:
        """``get_ControlSpiceValue`` @0x4909dc0."""
        raise NotImplementedError

    def control_value_avg(self) -> float:
        """``get_ControlValueAvg`` @0x4909ed0."""
        raise NotImplementedError

    def discard_value(self) -> float:
        """``get_DiscardValue`` @0x491aac0."""
        raise NotImplementedError

    def buy_gains(self, amount: int) -> float:
        """``GetBuyGains`` @0x4908650 (knapsack; cached per amount)."""
        raise NotImplementedError

    def buy_value(self) -> float:
        """``GetBuyValue`` @0x4909f10."""
        raise NotImplementedError

    def possible_persuasion(self) -> int:
        """``get_PossiblePersuasion`` @0x4903600."""
        raise NotImplementedError

    def possible_persuasion_gain(self) -> int:
        """``PossiblePersuasionGain`` @0x4908ef0."""
        raise NotImplementedError

    def predict_card_buys(self, with_persuasion: int) -> list[Entity]:
        """``PredictCardBuys`` @0x4903680 (0/1 knapsack over buyable cards)."""
        raise NotImplementedError

    def acquire_cards_by_value(self, with_persuasion: int) -> list[Entity]:
        """``GetAcquireCardsByValue`` @0x4903810."""
        raise NotImplementedError

    def deck_agent_icons(self) -> dict[str, int]:
        """``get_DeckAgentIcons`` @0x4903980 (draw pile only)."""
        raise NotImplementedError

    def synergy_mod(self, card: Entity) -> Summer:
        """``GetSynergyMod`` @0x490d040 (capped at SynergyModMaxValue)."""
        raise NotImplementedError

    def friendship_mod(self, card: Entity) -> Summer:
        """``GetFriendshipMod`` @0x490deb0."""
        raise NotImplementedError

    def acquire_effects_value(self, card: Entity) -> Summer:
        """``GetAcquireEffectsValue`` @0x490e470."""
        raise NotImplementedError

    def specific_acquire_bonus(self, card: Entity) -> Summer:
        """``GetSpecificAcquireBonus`` @0x490f430."""
        raise NotImplementedError

    def acquire_value(self, card: Entity) -> Summer:
        """``WormImperiumPlayable::AcquireValue`` @0x4834650."""
        raise NotImplementedError

    def spice_for_spice_refinery(self) -> int:
        """``GetSpiceForSpiceRefinery`` @0x490f850."""
        raise NotImplementedError

    def can_agent_ability_be_played_with_space(
        self, space: Entity | None, attr: Attr, amount: int
    ) -> bool:
        """``CanAgentAbilityBePlayedWithSpace`` @0x490f950."""
        raise NotImplementedError

    def card_to_trash(
        self, targets: Sequence[Entity], min_trash_value: float
    ) -> tuple[Entity | None, float]:
        """``GetCardToTrash`` @0x490fc00 (shuffles; non-strict keep-best)."""
        raise NotImplementedError

    def opponent_ratio(self, condition: Callable[[PlayerState], bool]) -> float:
        """``OpponentRatio`` @0x4911080."""
        raise NotImplementedError

    def ordered_players(self) -> list[int]:
        """``GetOrderedPlayers`` @0x4911120 (seats)."""
        raise NotImplementedError

    def has_turn_before_opponent_next_round(self, opponent: int) -> bool:
        """``HasTurnBeforeOpponentNextRound`` @0x4911e00."""
        raise NotImplementedError

    def bad_intrigue_cards_in_hand(self) -> list[Entity]:
        """``get_GetBadIntrigueCardsInHand`` @0x4912250."""
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
        """``GetGainInfluenceValue`` @0x490a180 (current_rank -1 = read it)."""
        raise NotImplementedError

    def has_or_would_gain_alliance(self, faction: str, amount: int) -> bool:
        """``HasOrWouldGainAlliance`` @0x490c260."""
        raise NotImplementedError

    def best_influence_exchange(
        self,
        lose_amount: int,
        gain_amount: int,
        lose_factions: Sequence[str] | None = None,
        gain_factions: Sequence[str] | None = None,
    ) -> tuple[str | None, str | None, float]:
        """``GetBestInfluenceExchange`` @0x490c380 (shuffles; strict keep-best)."""
        raise NotImplementedError

    def spy_value(self) -> Summer:
        """``SpyValue`` @0x490be50."""
        raise NotImplementedError

    def recall_spy_value(self) -> Summer:
        """``RecallSpyValue`` @0x491b720."""
        raise NotImplementedError

    def post_value(self, post: Entity, unseen_network: bool = False) -> float:
        """``WormObservationPost::PostValue``."""
        raise NotImplementedError

    def best_post(
        self, posts: Sequence[Entity], unseen_network: bool = False
    ) -> tuple[Entity | None, float]:
        """``GetBestPost`` @0x491d2d0."""
        raise NotImplementedError

    def post_selection(
        self,
        posts: Sequence[Entity],
        take: int,
        best: bool,
        unseen_network: bool = False,
    ) -> tuple[list[Entity], float]:
        """``GetPostSelection`` @0x491d390 (shuffle, then sort)."""
        raise NotImplementedError

    def recall_spy(self, spies: Sequence[Entity]) -> tuple[Entity | None, float]:
        """``GetRecallSpy`` @0x491db00 (the spy on the worst post)."""
        raise NotImplementedError

    def recall_spies(
        self, spies: Sequence[Entity], take: int
    ) -> tuple[list[Entity], float]:
        """``GetRecallSpies`` @0x491dba0."""
        raise NotImplementedError

    def want_contract_count(self) -> int:
        """``WantContractCount`` @0x491b990."""
        raise NotImplementedError

    def gain_contract_value(self) -> Summer:
        """``GainContractValue`` @0x491bb20."""
        raise NotImplementedError

    def best_contract(
        self, contracts: Sequence[Entity], forced: bool
    ) -> tuple[Entity | None, float]:
        """``GetBestContract`` @0x491cf10."""
        raise NotImplementedError

    def contract_acquire_value(self, contract: Entity) -> Summer:
        """``WormContractPlayable::AcquireValue`` @0x482a880."""
        raise NotImplementedError

    def battle_icon_value(self, icon: str) -> Summer:
        """``GetBattleIconValue`` @0x491bcf0."""
        raise NotImplementedError

    def maker_hooks_value(self) -> float:
        """``MakerHooksValue`` @0x491c0c0."""
        raise NotImplementedError

    def opponent_maker_hooks_ratio(self) -> float:
        """``GetOpponentMakerHooksRatio`` @0x490c0e0."""
        raise NotImplementedError

    def recall_agent_value(self) -> float:
        """``RecallAgentValue`` @0x491c600."""
        raise NotImplementedError

    def recall_agent(self, agents: Sequence[Entity]) -> Entity | None:
        """``GetRecallAgent`` @0x4912340 (50 MINUS the space value; shuffles)."""
        raise NotImplementedError

    def space_value_for_player(self, space: Entity) -> Summer:
        """``WormSpace::ValueForPlayer`` @0x49c0c40 (merge of its abilities)."""
        raise NotImplementedError

    def blow_wall_value(self) -> Summer:
        """``BlowWallValue`` @0x491c750."""
        raise NotImplementedError

    def should_blow_wall(self) -> bool:
        """``ShouldBlowWall`` @0x491dfe0."""
        raise NotImplementedError

    def intrigue_blow_wall(self) -> bool:
        """``IntrigueBlowWall`` @0x491e4a0."""
        raise NotImplementedError

    def lady_jessica_return_memories(self) -> bool:
        """``LadyJessicaReturnMemories`` @0x491de50."""
        raise NotImplementedError

    # ===========================================================================
    # Conflict and combat — spec/profile-combat.md (implemented in combat.py)
    # ===========================================================================

    def deploy_value(self, owner: Entity) -> float:
        """``DeployValue`` @0x4912c50."""
        raise NotImplementedError

    def conflict_competitors(self) -> float:
        """``get_ConflictCompetitors`` @0x4913e30."""
        raise NotImplementedError

    def conflict_posture_bounds(self) -> tuple[float, float]:
        """``get_ConflictPostureBounds`` @0x4908390: (lower, upper)."""
        raise NotImplementedError

    def combat_positioning(self) -> float:
        """``GetCombatPositioning`` @0x4913ea0."""
        raise NotImplementedError

    def combat_posture_mod(self) -> float:
        """``GetCombatPostureMod`` @0x4908080 (dead: every caller passes false)."""
        raise NotImplementedError

    def uprising_conflicts(self) -> tuple[Archetype, ...]:
        """``GetUprisingConflicts`` @0x4913fb0 (static catalogue)."""
        raise NotImplementedError

    def relative_conflict_value(self) -> Summer:
        """``RelativeConflictValue`` @0x4900490."""
        raise NotImplementedError

    def current_conflict_interest(self) -> Summer:
        """``CurrentConflictInterest`` @0x4902f80."""
        raise NotImplementedError

    def intrigue_hand_strength_value(self) -> int:
        """``IntrigueHandStrengthValue`` @0x4914170."""
        raise NotImplementedError

    def est_opponent_strength(self, opponent: int) -> IntSummer:
        """``EstOpponentStrength`` @0x4914400."""
        raise NotImplementedError

    def est_strength(self) -> IntSummer:
        """``EstStrength`` @0x4914bd0."""
        raise NotImplementedError

    def potential_strength(self, max_units: int) -> IntSummer:
        """``PotentialStrength`` @0x49152d0."""
        raise NotImplementedError

    def units_to_deploy(self, garrison_troops: int, max_units: int) -> int:
        """``GetUnitsToDeploy`` @0x49158f0: how many garrison troops to deploy."""
        raise NotImplementedError

    def troops_to_retreat(self, max_troops: int) -> int:
        """``GetTroopsToRetreat`` @0x4917820."""
        raise NotImplementedError

    def estimated_conflict_rank(self, bonus_strength: int = 0) -> int | None:
        """``EstimatedConflictRank`` @0x4918070 (1-based)."""
        raise NotImplementedError

    def current_conflict_rank(self, bonus_strength: int = 0) -> int | None:
        """``CurrentConflictRank`` @0x4918460 (1-based)."""
        raise NotImplementedError

    def current_combat_order(self) -> list[int]:
        """``GetCurrentCombatOrder`` @0x49040a0 (seats, strongest first)."""
        raise NotImplementedError

    def expected_combat_order(self) -> list[int]:
        """``GetExpectedCombatOrder`` @0x49185a0."""
        raise NotImplementedError

    def expected_combat_order_with_strength(self) -> list[tuple[int, int]]:
        """``GetExpectedCombatOrderWithStrength`` @0x49186f0."""
        raise NotImplementedError

    def heighliner_potential_player(self) -> int | None:
        """``GetHeighlinerPotentialPlayer`` @0x49189a0."""
        raise NotImplementedError

    def has_highliner_potential(self, seat: int | None = None) -> bool:
        """``HasHighlinerPotential`` @0x4914340 / @0x4914b10."""
        raise NotImplementedError

    def worm_potential_player(self, space_id: str) -> int | None:
        """``GetWormPotentialPlayer`` @0x491e770."""
        raise NotImplementedError

    def has_worm_potential(self, seat: int | None = None) -> bool:
        """``HasWormPotential`` @0x4914380 / @0x491eb90."""
        raise NotImplementedError

    def has_worm_potential_a(self, seat: int | None = None) -> bool:
        """``HasWormPotentialA`` @0x4915250 / @0x4914b50."""
        raise NotImplementedError

    def has_worm_potential_b(self, seat: int | None = None) -> bool:
        """``HasWormPotentialB`` @0x4915290 / @0x4914b90."""
        raise NotImplementedError

    def can_play_to_desert_space_with_hooks(self, seat: int, space_id: str) -> bool:
        """``CanPlayToDesertSpaceWithHooks`` @0x491ce50."""
        raise NotImplementedError

    def should_play_retreat_intrigue(
        self,
        card_name: str,
        not_first_extra_strength: int,
        first_extra_strength: int,
        retreat_units: int,
    ) -> int:
        """``ShouldPlayRetreatIntrigue`` @0x4919820."""
        raise NotImplementedError

    def should_play_troop_intrigue(
        self,
        card_name: str,
        not_first_extra_strength: int,
        first_extra_strength: int,
        troops: int,
    ) -> int:
        """``ShouldPlayTroopIntrigue`` @0x491a4c0."""
        raise NotImplementedError

    def play_intrigue_for_final_round_or_hand_size(self, card: Entity) -> int:
        """``PlayIntrigueForFinalRoundOrHandSize`` @0x4912b00."""
        raise NotImplementedError

    def trash_intrigue_value(self) -> float:
        """``TrashIntrigueValue`` @0x491b610."""
        raise NotImplementedError

    # ===========================================================================
    # Immortality — spec/immortality.md §2 (implemented in immortality.py;
    # the Immortality terms of GetResourceValue, AcquireValue, GetSynergyMod,
    # GetAcquireEffectsValue, GetCardToTrash and DeployValue live in the
    # methods above)
    # ===========================================================================

    def research_value(self) -> Summer:
        """``ResearchValue`` @0x490ea70."""
        raise NotImplementedError

    def tleilaxu_value(self, amount: int) -> Summer:
        """``TleilaxuValue(int amount)`` @0x490f130."""
        raise NotImplementedError

    def research_space_value(self, space_id: str) -> Summer:
        """``WormResearchTrack::SpaceValue(space, forPlayer)`` @0x49b9900.

        ``space_id`` is our research space id (``c<col>r<row>``).
        """
        raise NotImplementedError

    def tleilaxu_row_cards(self) -> list[Entity]:
        """``Playmat.TleilaxuRow.children.OfType<WormImperiumPlayable>()``.

        Not an app method: the row the Immortality readers iterate
        (Reclaimed Forces first; ``AppContext.tleilaxu_row``).
        """
        raise NotImplementedError
