"""The ``agent_effects`` window: the app's fixed Agent-turn order, then its
post-action prompt.

Our engine offers every pending effect of the Agent turn in free order (OQ-027,
scratchpad R1 §2) and asks for each optional effect explicitly. The app runs
the turn in fixed ``AgentTurnPhase`` states and asks the AI only what is left
afterwards (``spec/engine-order.md`` §3.1-3.6, §4; ``12-turn-structure.md``
§2.3, §6):

- 260 ``SpyIntelligence``: ``RecallSpyIntelligenceAbility`` (yes/no, forced
  single-ability prompt). Our engine makes Gather Intelligence exclusive while
  it is pending, so it is answered first (the app asks it after the 220 cost
  step, which only Gather Support and Spice Refinery have; their gains are
  resolved right after it here, a harmless swap).
- 220/400 the space's own ``SpaceAbility`` (printed gains; no question).
- 500 the card's generic agent box (``AgentAbility`` with ``AgentWater`` /
  ``AgentSpice`` / ``AgentSolari`` / ``AgentTroops``, and the ``PowerPlay``
  box of Overthrow and Subversive Advisor; no question).
- 600 ``ResolveImmediateDeferredAbilities``: every deferred ability whose
  ``CanRunImmediately`` holds, in ``GetUsableDeferredAbilities`` row order
  (the card's, then the space's: ``ActiveCards.Concat(ActiveSpace)``
  @0x49aeb14-0x49aeb3f, which engine-order §9 left untraced; the leader's,
  the playmat's, the contract area's), stable-sorted with the ones that do
  not clear the undo stack first (``OrderBy(WillClearUndo)``).
  ``DrawAbility``, the space's ``GainInfluenceAbility``, ``GainContractAbility``,
  ``Draw2``/``TSMF``/``BG`` contracts and Muad'Dib's ``LeadTheWay`` run here
  only while ``DeferredThresholdReached`` is false
  (``abilities.generic.deferred_threshold_reached``); otherwise they wait in
  the prompt as Explicit keys valued by their ``Evaluate``.
- The post-action prompt (``PlayerTurnPhase/<ResolveDeferredAbilities>``):
  every remaining Optional/Explicit deferred ability of the card, the space,
  the leader and the contract area, the owed Emperor-4 Spy
  (``PlaceSpyCustomAbility``), ``DeployUnitsAbility`` (0.5) and the Plots,
  ranked by ``MakeChoice``; forced while an Explicit ability is pending; the
  empty answer is End Turn.

``agent_effects_window`` groups our legal actions into ``common.Source``s with
those stages and calls ``common.decide``. A PROMPT source is valued by its
port's ``evaluate`` on a ``Request`` built from our legal targets, and the
app's answer is mapped back to the legal action that realises it. The empty
answer (End Turn) needs, in our engine, every Optional effect declined first:
the skip action is the first pending decline, then the end-of-turn chores
(``TrashSelfAbility``, Implicit: the app runs it after End Turn; no-op
confirmations with no app question), then ``finish_agent_turn``. With an
Explicit source pending and nothing worth more than 0 the prompt is forced and
``decide`` answers at random (``DefaultRandomChoice``). ``withdraw_troops`` is
never used (the app never withdraws).

Action table: our action -> app ability (owner) -> stage -> how the answer maps
back. (E) Explicit: forces the prompt; (O) Optional. "Follow-up": the rest of
an app answer already given, resolved before anything else. "Chore": no app
question; taken when the app would End Turn.

The space:

- ``gather_intelligence(post)`` / ``decline_gather_intelligence``:
  ``RecallSpyIntelligenceAbility`` (playmat), 260, forced; option 1 with
  ``GetRecallSpy``'s Spy -> gather(post), option 0 -> decline.
- ``resolve_board_effect(troops|resources|high_council|swordmaster)``:
  ``SpaceAbility`` and its subclasses (space), 400 (220 at Gather Support and
  Spice Refinery), automatic in printed icon order.
- ``resolve_board_effect(intrigue)``: ``AgentGainIntrigueAbility`` /
  ``HighCouncilGainIntrigueAbility`` (space), 600 (always immediate); at
  Secrets the same action runs ``SecretsSpaceAbility``'s steal (400 in the
  app; judgement: placed at the draw).
- ``resolve_board_effect(cards)``: ``DrawAbility`` (space), 600 unless the
  threshold is reached, else (E) at its ``DeferValue``.
- ``resolve_board_effect(contract)``: ``GainContractAbility`` (space), 600
  or (E) at ``ContractEvaluate`` over the contract options.
- ``harvest_maker_spice`` at Imperial Basin: ``SpaceAbility``, 400.
- ``harvest_maker_spice`` / ``summon_maker_sandworms``:
  ``HaggaBasinUprisingDeferredAbility`` / ``DeepDesertDeferredAbility`` (E);
  option 0 -> harvest, 1 -> summon.
- ``take_sietch_tabr_supplies`` / ``take_sietch_tabr_water`` /
  ``take_sietch_tabr_water_and_destroy_wall``:
  ``SietchTabrUprisingDeferredSpaceAbility`` (E); option 0 -> supplies;
  option 1 grants ``BlowWallCustomAbility`` (100), whose ``BlowWall`` prompt
  is ``ChooseBlowWall`` = ``ShouldBlowWall`` -> the wall when legal and
  wanted, else plain water.
- ``resolve_espionage_place_spy(post)`` / ``recall_spy_for_espionage(post)``
  / ``resolve_espionage_without_spy``: ``PlaceSpyAgentAbility`` (E) at
  ``SpyValue``; ``common.spy_answer`` (never declines); the placement after a
  recall is a follow-up; ``without_spy`` alone is a chore.
- ``choose_shipping_influence(faction)``: ``GainAnyInfluenceAgentAbility``
  (E); the chosen track.
- ``trash_card_for_desert_tactics(card)`` /
  ``resolve_desert_tactics_without_trash``: ``TrashAgentAbility`` (E); card ->
  trash, empty pick -> without trash.
- ``trash_intrigue_for_imperial_privilege(card)`` /
  ``decline_imperial_privilege_intrigue``: ``ImperialPrivilegeAbility`` (O);
  card -> trash, unused -> decline.
- ``recall_agent_for_imperial_privilege(space)``: ``RecallAgentAbility`` (E)
  (the space's draw rides along); ``resolve_imperial_privilege_without_recall``:
  the space's ``DrawAbility`` (600 or E).
- ``resolve_faction_influence``: ``GainInfluenceAbility`` (space), 600 or (E)
  at its ``DeferValue``.

The card's Agent box (``resolve_agent_card_effect``, by card):

- Paracompass, Northern Watermaster, Stilgar (``AgentSolari`` /
  ``AgentWater`` / ``AgentTroops``), Overthrow and Subversive Advisor
  (``PowerPlayAgentAbility``): 500, automatic.
- Seek Allies, and Dangerous Rhetoric's ``trash_self`` icon:
  ``TrashSelfAbility`` (Implicit, after End Turn): chore.
- Prepare the Way, Maula Pistol, Spacing Guild's Favor, Cargo Runner: their
  ``DrawAbility``, 600 or (E) at ``DeferValue``; Priority Contracts:
  ``GainContractAbility``, likewise.
- Rebel Supplier, Strike Fleet, Desert Power, Smuggler's Harvester, Fedaykin
  Stilltent, Southern Elders: their ``AlwaysRunImmediately`` ability, 600.
- Leadership, Chani Clever Tactician, Imperial Spymaster, Weirding Woman,
  Covert Operation: their ability (E) at its ``Evaluate``.
- In High Places: ``InHighPlacesPlaceSpyAbility`` (E) at ``SpyValue`` (the
  ``BeneGesseritDrawAbility`` draw rides along).
- Long Live the Fighters: ``LongLiveTheFightersStartAbility`` (O), 100.
- ``effect=`` icons: Hidden Missive ``troops`` / Maker Keeper / Wheels Within
  Wheels -> their ``AlwaysRunImmediately`` riders, 600; Hidden Missive and
  Steersman ``cards`` -> their draw (600 or E). The reward icons Captured
  Mentat, Guild Spy and Branching Path arm after their cost: follow-ups.
- ``trash_agent_card(card)`` / ``decline_agent_card_trash``:
  ``TrashAgentAbility`` (Calculus of Power, Desert Survival; E),
  ``BeneGesseritTrashAbility`` (Tread in Darkness; E; the draw rides along),
  ``ShishakliAgentAbility`` (O; targets hand, in play, discard),
  ``TreacherousManeuverAbility`` (O); card -> trash, empty pick or unused ->
  decline.
- ``discard_agent_card(card)`` / ``decline_agent_card_discard``:
  ``CapturedMentatAgentAbility`` (O), ``GuildSpyAgentAbility`` (O),
  ``SpacetimeFoldingAbility`` (O), ``GuildEnvoyAbility`` (E),
  ``DeliveryAgreementAgentAbility`` (O); card -> discard, unused -> decline.
- ``pay_agent_card_water`` / ``pay_agent_card_spice`` /
  ``decline_agent_card_payment``: ``EcologicalTestingStationAbility`` (O),
  ``SmugglersHavenAgentAbility`` (O); used -> pay, unused -> decline.
- ``select_corrinth_city_discard(card)`` / ``pay_corrinth_city(card)`` /
  ``decline_corrinth_city_payment``: ``CorrinthCityAgentAbility`` (O); its one
  answer names both cards: the first now, the second (memory intent
  ``("agent_effects", "corrinth_city", round, card)``) as a follow-up.
- ``trash_intrigue_for_agent_card`` / ``pay_agent_card_intrigue_and_spice`` /
  ``decline_agent_card_intrigue_payment``: ``BranchingPathAbility`` (O),
  ``JunctionHeadquartersAbility`` (O).
- ``recall_agent_for_agent_card(space)``: Steersman's ``RecallAgentAbility``
  (E).
- ``place_agent_card_spy`` / ``recall_spy_for_agent_card`` /
  ``decline_agent_card_spy``: ``PlaceSpyAgentAbility`` (Bene Gesserit
  Operative), ``ReliableInformantAbility``, ``DoubleAgentAbility`` (E);
  ``spy_answer``; follow-up after a recall.
- ``choose_agent_card_influence(faction)``: ``DangerousRhetoricAbility``,
  ``PublicSpectacleAbility``, ``GainAnyInfluenceAgentAbility`` (Interstellar
  Trade) (E).
- ``acquire_imperium_with_solari`` / ``acquire_reserve_with_solari`` /
  ``decline_agent_card_acquisition``: ``PriceIsNoObjectAbility`` (O).

The leader (Signet Ring box and leader abilities):

- ``resolve_agent_card_effect()`` of the Signet Ring: ``WarmasterAbility``
  (Gurney) and ``FillCoffersAbility`` (Amber), 600; ``LeadTheWayAbility``
  (Muad'Dib), 600 or (E) (the Signet Ring's ``DeferValue`` 3 always reaches
  the threshold).
- ``advance_feyd_track(space)``: ``PersonalTrainingAbility`` (E); Feyd's
  ``trash_leader_card`` / ``decline_leader_card_trash``:
  ``PersonalTrainingPayToTrashAbility`` / ``PersonalTrainingTrashAbility``
  (O, ``TrashAbility`` E): card -> trash, empty pick -> decline (the app pays
  Pay-to-Trash's Solari for nothing; ours cannot, plan §10).
- ``place_leader_spy`` / ``recall_spy_for_leader_placement`` /
  ``decline_leader_spy_placement``: ``PlaceSpyCustomAbility`` (Feyd),
  ``ArrakisInformantAbility`` (Margot), ``UnseenNetworkAbility`` (Staban,
  ``GetBestPost`` with ``UnseenNetwork``) (E).
- ``pay_leader_signet_spice`` / ``pay_leader_signet_solari`` /
  ``decline_leader_signet_payment``: ``SpiceAgonyAbility`` (Lady Jessica),
  ``WaterOfLifeSignetAbility`` (Reverend Mother),
  ``UnseenNetworkLandsraadAbility`` / ``UnseenNetworkInfluenceAbility``
  (Staban) (O).
- ``acquire_leader_imperium`` / ``trash_leader_card`` /
  ``decline_leader_signet_payment`` (Irulan): ``ChroniclersInsightAbility``
  (O); option 1 -> trash the named card; option 0 -> the card
  ``ChroniclersInsightAcquireAbility``'s E picks.
- ``gain_leader_signet_troop`` / ``choose_leader_signet_influence``
  (Shaddam): ``EmperorOfTheKnownUniverseSignetAbility`` (E).
- ``use_other_memories`` / ``decline_other_memories``:
  ``OtherMemoriesAbility`` (O); ``pay_leader_board_repeat`` /
  ``decline_leader_board_repeat``: ``ReverendMotherAbility`` (O).

The rest:

- ``place_track_spy``: the Emperor track's ``PlaceSpyCustomAbility``
  (playmat, E) at ``SpyValue``.
- ``complete_contract(contract)``: its ``ContractAbility`` (contract area):
  plain and harvest contracts 600; Draw-2, TSMF and BG contracts 600 or (E)
  at 100; ``PlaceSpyContractAbility`` (``SpyValue``) and
  ``RecallAgentContractAbility`` (``RecallAgentValue + 1``) always (E).
- ``deploy_troops(count)``: ``DeployUnitsAbility`` (space), or
  ``SardaukarCoordinationAgentAbility`` off a Combat space (O), 0.5 with
  ``GetUnitsToDeploy``'s count; once per turn (UNTRACED: exhausted after use).
- ``play_intrigue(card, option)``: ``intrigue_play_sources``, only once
  ``finish_agent_turn`` is legal (plan §4.4).
- ``finish_agent_turn``: End Turn, the empty answer; ``withdraw_troops``:
  never.

Judgement calls (our engine cannot ask the app's question exactly):

- Plots join the prompt only once ``finish_agent_turn`` is legal (plan §4.4);
  the app may play one before a pending Explicit key worth less.
- Where one of our actions does two app steps, it takes the stage of the one
  that asks: Imperial Privilege's draw rides on the recall, In High Places'
  draw on its Spy, Tread in Darkness' draw on its trash, Secrets' steal on its
  draw, Subversive Advisor's influence and self-trash on its box (500).
- The app computes the 600 list once; here every decision re-reads
  ``CanRunImmediately`` in the same order, so a card drawn earlier in 600 can
  move a later threshold-gated key into the prompt (it then runs as an
  Explicit key at once unless something is worth more).
- ``DeployUnitsAbility`` is used once per turn (UNTRACED: exhausted after
  use; ``combat_troops_deployed > 0`` marks the use).
- ``player.AdditionalSpaceInfluence`` (read by the influence step's
  ``WillClearUndo``) has no field of ours: it is derived from the turn
  (``_additional_space_influence``: the ``PowerPlay`` box of Overthrow or
  Subversive Advisor resolved, or Treacherous Maneuver used).
- The faction tracks of every influence choice are offered in ``FACTIONS``
  order (UNTRACED track order; ``GainAnyInfluenceAbility`` keeps the first
  strict maximum).

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to the heuristic.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    abilities_of,
    ability_for,
)
from dune_imperium.agents.app_ai.abilities.board import (
    BeneGesseritContractAbility,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    ContractAbility,
    DeferredAbility,
    DeployUnitsAbility,
    DrawAbility,
    GainContractAbility,
    GainInfluenceAbility,
    GainIntrigueAbility,
    _contract_options,
    _faction_influence,
    ability_id,
)
from dune_imperium.agents.app_ai.abilities.leaders import (
    DisciplineAbility,
    training_space_entity,
)
from dune_imperium.agents.app_ai.catalog import (
    LEADER_ARCHETYPES,
    agent_entity,
    card_entity,
    contract_entity,
    intrigue_entity,
    leader_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, card_id
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    best_place_action,
    decide,
    int_arg,
    spy_answer,
    str_arg,
    with_arg,
    worst_recall_action,
)
from dune_imperium.agents.app_ai.windows.intrigue import intrigue_play_sources
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.core.actions import ActionValue, DomainAction

_AU = "worm.canis.abilities.ActivatedAbilities.Uprising."
_PLACE_SPY_CUSTOM = _AU + "PlaceSpyCustomAbility"
_RECALL_SPY_INTELLIGENCE = _AU + "RecallSpyIntelligenceAbility"
_IRULAN = "LeaderArchetypes.Uprising.PrincessIrulan"

#: The rest of an app answer already given (its second step in our engine)
#: resolves before anything else.
_FOLLOW_UP = Stage.COST_FIRST
#: Spaces whose ``SpaceAbility`` is a ``CostFirstSpaceAbility`` (state 220).
_COST_FIRST_SPACES = ("gather_support", "spice_refinery")
#: Board icons the space's own ``SpaceAbility`` resolves (state 400).
_SPACE_ICONS = ("troops", "resources", "high_council", "swordmaster")

#: ``GetUsableDeferredAbilities`` @0x49ae890 rows (``12-turn-structure.md``
#: §2.2): the active cards' then the active space's abilities
#: (``ActiveCards.Concat(ActiveSpace)`` @0x49aeb3f), the leader's, the
#: playmat's custom abilities, the contract area.
_ROW_CARD = 0
_ROW_SPACE = 1
_ROW_LEADER = 2
_ROW_PLAYMAT = 3
_ROW_CONTRACT = 4

#: Single Agent boxes our engine resolves with ``resolve_agent_card_effect()``
#: whose app counterpart is the card's generic agent box (state 500):
#: printed ``AgentSolari``/``AgentWater``/``AgentTroops`` or the
#: ``PowerPlayAgentAbility`` of Overthrow and Subversive Advisor (the latter's
#: ``TrashSelf`` and the space influence are folded into the same action).
_AGENT_BOX_CARDS = (
    "paracompass",
    "northern_watermaster",
    "stilgar_the_devoted",
    "overthrow",
    "subversive_advisor",
)
#: Cards whose generic agent box is ``PowerPlayAgentAbility`` (it sets
#: ``player.AdditionalSpaceInfluence``; archetypes ``WormAbilityIDs``).
_POWER_PLAY_CARDS = ("overthrow", "subversive_advisor")
#: Single boxes resolved by the card's own deferred ability (app class short
#: name); the stage follows from the port's ``CanRunImmediately``.
_BOX_ABILITY: Mapping[str, str] = {
    "prepare_the_way": "BeneGesseritInfluenceDrawAbility",
    "maula_pistol": "DrawAbility",
    "spacing_guild_s_favor": "DrawAbility",
    "cargo_runner": "CargoRunner2ContractsDrawAbility",
    "leadership": "LeadershipAgentAbility",
    "chani_clever_tactician": "ChaniCleverTacticianAgentAbility",
    "imperial_spymaster": "ImperialSpymasterAbility",
    "rebel_supplier": "RebelSupplierAbility",
    "strike_fleet": "StrikeFleetAbility",
    "desert_power": "DesertPowerAgentAbility",
    "smuggler_s_harvester": "SmugglersHarvesterAbility",
    "fedaykin_stilltent": "FedaykinStilltentAbility",
    "southern_elders": "SouthernEldersAgentAbility",
    "weirding_woman": "WeirdingWomanAbility",
    "in_high_places": "InHighPlacesPlaceSpyAbility",
    "covert_operation": "CovertOperationAbility",
    "priority_contracts": "GainContractAbility",
    "long_live_the_fighters": "LongLiveTheFightersStartAbility",
}
#: Multi-icon boxes: (card, our icon key) -> the app ability of that icon.
_ICON_ABILITY: Mapping[tuple[str, str], str] = {
    ("hidden_missive", "troops"): "BeneGesseritInfluenceTroopAbility",
    ("hidden_missive", "cards"): "BeneGesseritInfluenceDrawAbility",
    ("steersman", "cards"): "DrawAbility",
    ("maker_keeper", "water"): "MakerKeeperBeneGesseritAbility",
    ("maker_keeper", "spice"): "MakerKeeperFremenAbility",
    ("wheels_within_wheels", "solari"): "WheelsWithinWheelsEmperorAbility",
    ("wheels_within_wheels", "spice"): "WheelsWithinWheelsSpacingGuildAbility",
}
#: Cards whose reward icons are armed after an arrow cost: the app answered
#: the whole ability at once, so the icons are follow-ups.
_ARMED_REWARD_CARDS = ("captured_mentat", "guild_spy", "branching_path")
#: Our trash choice of each card -> its app ability.
_TRASH_ABILITY: Mapping[str, str] = {
    "calculus_of_power": "TrashAgentAbility",
    "desert_survival": "TrashAgentAbility",
    "shishakli": "ShishakliAgentAbility",
    "tread_in_darkness": "BeneGesseritTrashAbility",
    "treacherous_maneuver": "TreacherousManeuverAbility",
}
_DISCARD_ABILITY: Mapping[str, str] = {
    "captured_mentat": "CapturedMentatAgentAbility",
    "guild_spy": "GuildSpyAgentAbility",
    "space_time_folding": "SpacetimeFoldingAbility",
    "guild_envoy": "GuildEnvoyAbility",
    "delivery_agreement": "DeliveryAgreementAgentAbility",
}
_PAYMENT_ABILITY: Mapping[str, str] = {
    "ecological_testing_station": "EcologicalTestingStationAbility",
    "smuggler_s_haven": "SmugglersHavenAgentAbility",
}
_INTRIGUE_PAYMENT_ABILITY: Mapping[str, str] = {
    "branching_path": "BranchingPathAbility",
    "junction_headquarters": "JunctionHeadquartersAbility",
}
_CARD_SPY_ABILITY: Mapping[str, str] = {
    "bene_gesserit_operative": "PlaceSpyAgentAbility",
    "reliable_informant": "ReliableInformantAbility",
    "double_agent": "DoubleAgentAbility",
}
_CARD_INFLUENCE_ABILITY: Mapping[str, str] = {
    "dangerous_rhetoric": "DangerousRhetoricAbility",
    "public_spectacle": "PublicSpectacleAbility",
    "interstellar_trade": "GainAnyInfluenceAgentAbility",
}
#: Signet boxes resolved by ``resolve_agent_card_effect()``, by leader.
_SIGNET_BOX_ABILITY: Mapping[str, str] = {
    "gurney_halleck": "WarmasterAbility",
    "lady_amber_metulli": "FillCoffersAbility",
    "muad_dib": "LeadTheWayAbility",
}
#: Feyd's trash stage -> its custom ability (``PersonalTraining*``).
_FEYD_TRASH_ABILITY: Mapping[str, str] = {
    "paid_trash": "PersonalTrainingPayToTrashAbility",
    "mid_trash": "PersonalTrainingTrashAbility",
    "late_trash": "PersonalTrainingTrashAbility",
}
#: The context flag our engine sets after each family's recall-first Spy
#: recall: the placement that follows is the rest of the app's single
#: ``PlaceSpy`` (``SelectSpy`` then ``SelectPost``).
_ESPIONAGE_RECALLED = "espionage_spy_recalled"
_CARD_SPY_RECALLED = "agent_card_spy_recalled"
_LEADER_SPY_RECALLED = "leader_spy_recalled"
_FEYD_SPY_RECALLED = "feyd_spy_recalled"

type Evaluation = Callable[[], tuple[float, DomainAction | None]]


# ---------------------------------------------------------------------------
# The turn being resolved
# ---------------------------------------------------------------------------


@dataclass
class _Turn:
    """One ``agent_effects`` decision: the run and the turn's subjects."""

    run: DecisionRun
    context: Mapping[str, ActionValue]
    card_ref: str | None
    card_short: str | None
    card: Entity | None
    space_id: str | None
    space: Entity | None
    leader: Entity | None
    sources: list[Source] = field(default_factory=list)
    declines: list[DomainAction] = field(default_factory=list)
    chores: list[DomainAction] = field(default_factory=list)
    #: ``player.AdditionalSpaceInfluence`` this turn
    #: (``_additional_space_influence``).
    additional_space_influence: bool = False

    @property
    def p(self) -> Profile:
        return self.run.profile

    @property
    def seat(self) -> int:
        return self.run.ctx.seat

    def by_id(self, *action_ids: str) -> tuple[DomainAction, ...]:
        return tuple(a for a in self.run.legal if a.action_id in action_ids)

    def flag(self, key: str) -> bool:
        return self.context.get(key) is True


def _turn(run: DecisionRun) -> _Turn:
    ctx = run.ctx
    context = ctx.top_frame_context
    card_ref = context.get("card_id")
    space_id = context.get("space_id")
    card: Entity | None = None
    card_short: str | None = None
    if isinstance(card_ref, str) and card_ref:
        card_short = card_id(card_ref)
        try:
            card = card_entity(card_ref, ctx.seat)
        except KeyError:  # a card with no app archetype (promos, expansions)
            card = None
    else:
        card_ref = None
    space: Entity | None = None
    if isinstance(space_id, str) and space_id:
        try:
            space = space_entity(space_id, ctx.choam)
        except KeyError:
            space = None
    else:
        space_id = None
    me = ctx.me
    leader: Entity | None = None
    if me.leader_id is not None and me.leader_id in LEADER_ARCHETYPES:
        leader = leader_entity(me.leader_id, me.leader_face_id)
    t = _Turn(run, context, card_ref, card_short, card, space_id, space, leader)
    t.additional_space_influence = _additional_space_influence(t)
    return t


def _additional_space_influence(t: _Turn) -> bool:
    """``player.AdditionalSpaceInfluence`` (a ``WormAttributes`` bool) at
    this decision.

    Set true by ``PowerPlayAgentAbility`` (the generic agent box of Overthrow
    and Subversive Advisor, run at state 500:
    ``<RunImmediateEffects>d__5::MoveNext`` @0x4cab010, ``ChangeAttribute``
    to ``Nullable<bool>(true)`` at 0x4cab111-0x4cab14c, targeting the
    player) and by ``TreacherousManeuverAbility`` when used
    (``<BeginExecution>d__11::MoveNext`` @0x4d46de0, state 5 at
    0x4d4726f-0x4d472c1, unless already true); reset to false by
    ``PlayerTurnPhase/<Cleanup>d__17`` @0x4a10980 (case 53, 0x4a1217c-
    0x4a121d8) at the end of every turn, so only this turn's frame matters.
    ``DemandAttentionAbility`` also sets it, but the card is in no Uprising
    deck (absent from our engine).

    Our engine: the box is resolved once ``pending_agent_effect`` is no
    longer true (it starts false when the box has nothing to do, while the
    app still runs ``PowerPlay`` at 500; the flag is only read at state 600
    and later, after 500 either way). Treacherous Maneuver trashes itself
    when used, so it is used once its box is done and the card has left
    play (declined: still in play).
    """

    done = t.context.get("pending_agent_effect") is not True
    if t.card_short in _POWER_PLAY_CARDS:
        return done
    if t.card_short == "treacherous_maneuver":
        return done and t.card_ref not in t.run.ctx.me.in_play
    return False


# ---------------------------------------------------------------------------
# App-side helpers
# ---------------------------------------------------------------------------


def _find(owner: Entity | None, short: str) -> tuple[Ability, int] | None:
    """The first ability of ``owner`` whose app class name is ``short``."""

    if owner is None:
        return None
    for index, ability in enumerate(abilities_of(owner)):
        if ability_id(ability).rsplit(".", 1)[-1] == short:
            return ability, index
    return None


def _first_of(owner: Entity | None, kind: type[Ability]) -> tuple[Ability, int] | None:
    """The first ability of ``owner`` that is a ``kind`` port."""

    if owner is None:
        return None
    for index, ability in enumerate(abilities_of(owner)):
        if isinstance(ability, kind):
            return ability, index
    return None


def _explicit(ability: Ability, p: Profile) -> bool:
    """``SelectionMode == Explicit`` (the key forces the post-action prompt)."""

    return (
        isinstance(ability, DeferredAbility)
        and ability.selection_mode(p) == SelectionMode.EXPLICIT
    )


def _immediate(ability: Ability, p: Profile) -> bool:
    """``DeferredAbility.CanRunImmediately`` (engine-order §4.2)."""

    return isinstance(ability, DeferredAbility) and ability.can_run_immediately(p)


def _will_clear_undo(ability: Ability, p: Profile, extra: bool) -> bool:
    """``WillClearUndo(player)``: the sort key of the immediate abilities.

    ``WormAbilityDefinition::WillClearUndo`` @0x4a89fc0 reads the ability's
    ``WillClearUndo`` attribute, set true by the ``.ctor``s of
    ``DrawAbility`` @0x4cda279, ``GainIntrigueAbility`` @0x4cdf3e0,
    ``GainContractAbility`` @0x4d12138 and ``DisciplineAbility`` (and every
    subclass); the plain riders and contracts leave it false.
    ``GainInfluenceAbility::WillClearUndo`` @0x4bad640 computes it (below,
    ``extra`` = ``player.AdditionalSpaceInfluence``);
    ``BeneGesseritContractAbility`` @0x4d54610 is the port's
    ``will_clear_undo``.
    """

    if isinstance(ability, DrawAbility | GainIntrigueAbility | GainContractAbility):
        return True
    if isinstance(ability, DisciplineAbility):
        return True
    if isinstance(ability, GainInfluenceAbility):
        return _gain_influence_clears_undo(ability, p, extra)
    if isinstance(ability, BeneGesseritContractAbility):
        return ability.will_clear_undo(p)
    return False


def _gain_influence_clears_undo(
    ability: GainInfluenceAbility, p: Profile, extra: bool
) -> bool:
    """``GainInfluenceAbility::WillClearUndo`` @0x4bad640.

    ``extra = player.AdditionalSpaceInfluence`` (read at 0x4bad6f3-0x4bad709;
    ``_additional_space_influence``). Princess Irulan at a space giving
    Emperor influence: true when her Emperor influence is 1 (``cmp ecx, 1;
    je``: the gain reaches 2 and Imperial Birthright draws), or 0 with
    ``extra`` (0x4bad7fc ``and dl, r14b``). Then for everyone: the space gives
    Bene Gesserit influence (``> 0``) and the player's is exactly 3 (the
    4-step Intrigue card), else ``extra and BG == 2`` (0x4bad858-0x4bad85e:
    the space's factions are not tested there, an app quirk kept).
    """

    gains = dict(_faction_influence(ability.owner))
    me = p.ctx.me
    leader = None if me.leader_id is None else LEADER_ARCHETYPES.get(me.leader_id)
    if leader == _IRULAN and gains.get("emperor", 0) > 0:
        emperor = me.influence.emperor
        if emperor == 1 or (emperor == 0 and extra):
            return True
    bene_gesserit = me.influence.bene_gesserit
    if gains.get("bene_gesserit", 0) > 0 and bene_gesserit == 3:
        return True
    return extra and bene_gesserit == 2


def _immediate_order(t: _Turn, ability: Ability, row: int, index: int) -> int:
    """Stable ``OrderBy(WillClearUndo)`` over the row order (row, index)."""

    clears = _will_clear_undo(ability, t.p, t.additional_space_influence)
    return (1 if clears else 0) * 10_000 + row * 100 + index


def _response_ref(answer: Answer, index: int = 0) -> str | int | None:
    """The first ref / option of response item ``index`` (None: empty)."""

    if answer.response is None or len(answer.response) <= index:
        return None
    item = answer.response[index]
    return item[0] if item else None


# ---------------------------------------------------------------------------
# Source builders
# ---------------------------------------------------------------------------


def _automatic(
    t: _Turn, label: str, stage: Stage, action: DomainAction, order: int = 0
) -> None:
    t.sources.append(Source(label, stage, (action,), order=order))


def _prompt(
    t: _Turn,
    label: str,
    actions: Sequence[DomainAction],
    evaluate: Evaluation,
    *,
    explicit: bool,
) -> None:
    t.sources.append(
        Source(
            label,
            Stage.PROMPT,
            tuple(actions),
            evaluate=evaluate,
            extra={"explicit": explicit},
        )
    )


def _ability_source(
    t: _Turn,
    label: str,
    found: tuple[Ability, int] | None,
    row: int,
    action: DomainAction,
    request: Request | None = None,
) -> None:
    """One deferred ability realised by ``action`` (no sub-choice of ours).

    Immediate (``CanRunImmediately``) -> stage 600 in the app's order;
    otherwise a prompt key valued by its ``Evaluate`` (an untouched answer is
    not a candidate). Without a port the action is resolved automatically.
    """

    if found is None:
        _automatic(t, label, Stage.IMMEDIATE, action, 9_999)
        return
    ability, index = found
    p = t.p
    if _immediate(ability, p):
        _automatic(
            t, label, Stage.IMMEDIATE, action, _immediate_order(t, ability, row, index)
        )
        return
    req = request if request is not None else Request()

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, req)
        return ans.value, (None if ans.response is None else action)

    _prompt(t, label, (action,), evaluate, explicit=_explicit(ability, p))


def _choice_source(
    t: _Turn,
    label: str,
    found: tuple[Ability, int] | None,
    uses: Sequence[DomainAction],
    request: Request,
    answer: Callable[[Answer], DomainAction | None],
    decline: DomainAction | None,
) -> None:
    """A prompt key whose ``Evaluate`` picks among ``uses`` (or nothing).

    An Optional key the app leaves unused needs our ``decline`` before End
    Turn; with no ``uses`` at all the app has no such key (its ``Cost`` or
    targets fail) and the decline is a chore.
    """

    if decline is not None:
        t.declines.append(decline)
    if found is None or not uses:
        return
    ability, _index = found
    p = t.p

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None:
            return ans.value, None
        return ans.value, answer(ans)

    _prompt(t, label, uses, evaluate, explicit=_explicit(ability, p))


def _cards(t: _Turn, refs: Sequence[str]) -> tuple[Entity, ...]:
    return tuple(card_entity(ref, t.seat) for ref in refs)


def _arg_refs(actions: Sequence[DomainAction], name: str) -> list[str]:
    refs: list[str] = []
    for action in actions:
        ref = str_arg(action, name)
        if ref is not None:
            refs.append(ref)
    return refs


def _ref_or(
    actions: Sequence[DomainAction], name: str, fallback: DomainAction | None
) -> Callable[[Answer], DomainAction | None]:
    """Map the first response ref to the action with that argument; an empty
    pick to ``fallback``."""

    def answer(ans: Answer) -> DomainAction | None:
        ref = _response_ref(ans)
        if ref is None:
            return fallback
        return with_arg(actions, name, ref)

    return answer


# -- the space ----------------------------------------------------------------------


def _board_icons(t: _Turn) -> None:
    """``resolve_board_effect(effect)``: the space's automatic icons."""

    icons = str(t.context.get("board_icons", "")).split(",")
    for action in t.by_id("resolve_board_effect"):
        effect = str_arg(action, "effect") or ""
        order = icons.index(effect) if effect in icons else len(icons)
        label = f"board {effect}"
        if effect in _SPACE_ICONS:
            stage = (
                Stage.COST_FIRST if t.space_id in _COST_FIRST_SPACES else Stage.SPACE
            )
            _automatic(t, label, stage, action, order)
        elif effect == "intrigue":
            # Judgement: at Secrets our one action also runs the steal of the
            # app's ``SecretsSpaceAbility`` (400); it is placed at the draw
            # (``AgentGainIntrigueAbility``, 600), which every visit has.
            _ability_source(
                t, label, _first_of(t.space, GainIntrigueAbility), _ROW_SPACE, action
            )
        elif effect == "cards":
            _ability_source(
                t, label, _first_of(t.space, DrawAbility), _ROW_SPACE, action
            )
        elif effect == "contract":
            _ability_source(
                t,
                label,
                _first_of(t.space, GainContractAbility),
                _ROW_SPACE,
                action,
                _contract_request(t),
            )
        else:  # not in a 4-player Uprising game (research, ...)
            _automatic(t, label, Stage.SPACE, action, order)


def _contract_request(t: _Turn) -> Request:
    """``GainContractAbility.MakeTargets``: the contract options."""

    options = tuple(contract_entity(ref) for ref in _contract_options(t.p))
    return Request(infos=(TargetInfo(entities=options),))


def _faction_influence_source(t: _Turn) -> None:
    action = t.run.first("resolve_faction_influence")
    if action is None:
        return
    found = _first_of(t.space, GainInfluenceAbility)
    if found is None:
        _automatic(t, "faction influence", Stage.SPACE, action, 99)
        return
    _ability_source(t, "faction influence", found, _ROW_SPACE, action)


def _spy_source(
    t: _Turn,
    label: str,
    found: tuple[Ability, int] | None,
    place: Sequence[DomainAction],
    recall: Sequence[DomainAction],
    decline: DomainAction | None,
    recalled_flag: str,
    *,
    unseen_network: bool = False,
) -> None:
    """A ``PlaceSpy`` key: ``SpyValue``, then the post (``PlaceSpyEvaluator``)
    or, with an empty supply, the recall first (``RecallSpyEvaluator``)."""

    run = t.run
    if place and t.flag(recalled_flag):
        chosen = best_place_action(run, place, unseen_network=unseen_network)
        if chosen is not None:
            _automatic(t, f"{label} after recall", _FOLLOW_UP, chosen, -1)
            return
    if not place and not recall:
        if decline is not None:
            t.chores.append(decline)
        return
    if found is None:
        return

    def realise() -> DomainAction | None:
        if place:
            return best_place_action(run, place, unseen_network=unseen_network)
        if recall:
            return worst_recall_action(run, recall)
        return decline

    ability, _index = found
    p = t.p

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, Request())
        if ans.response is None:
            return ans.value, None
        if unseen_network:
            return ans.value, realise()
        return ans.value, spy_answer(run, place, recall, decline)

    _prompt(t, label, (*place, *recall), evaluate, explicit=_explicit(ability, p))


def _espionage(t: _Turn) -> None:
    place = t.by_id("resolve_espionage_place_spy")
    recall = t.by_id("recall_spy_for_espionage")
    without = t.run.first("resolve_espionage_without_spy")
    if not place and not recall and without is None:
        return
    found = _find(t.space, "PlaceSpyAgentAbility")
    _spy_source(t, "Espionage spy", found, place, recall, without, _ESPIONAGE_RECALLED)


def _sietch_tabr(t: _Turn) -> None:
    supplies = t.run.first("take_sietch_tabr_supplies")
    water = t.run.first("take_sietch_tabr_water")
    wall = t.run.first("take_sietch_tabr_water_and_destroy_wall")
    uses = tuple(a for a in (supplies, water, wall) if a is not None)
    if not uses:
        return
    p = t.p

    def answer(ans: Answer) -> DomainAction | None:
        """Option 1 grants ``BlowWallCustomAbility`` (Optional, 100): its
        ``BlowWall`` prompt asks ``ChooseBlowWall`` = ``ShouldBlowWall``
        (``profile-influence-uprising.md`` §6.4-6.5)."""

        option = _response_ref(ans)
        if option == 0:
            return supplies
        if wall is not None and p.should_blow_wall():
            return wall
        return water

    _choice_source(
        t,
        "Sietch Tabr",
        _find(t.space, "SietchTabrUprisingDeferredSpaceAbility"),
        uses,
        Request(),
        answer,
        None,
    )


def _maker(t: _Turn) -> None:
    harvest = t.run.first("harvest_maker_spice")
    summon = t.run.first("summon_maker_sandworms")
    if harvest is None and summon is None:
        return
    if t.space_id == "imperial_basin":
        # No DesertSpaceDeferredAbility: the SpaceAbility gives the spice.
        if harvest is not None:
            _automatic(t, "Imperial Basin spice", Stage.SPACE, harvest)
        return
    found = _find(t.space, "HaggaBasinUprisingDeferredAbility") or _find(
        t.space, "DeepDesertDeferredAbility"
    )
    uses = tuple(a for a in (harvest, summon) if a is not None)

    def answer(ans: Answer) -> DomainAction | None:
        if _response_ref(ans) == 1 and summon is not None:
            return summon
        return harvest

    _choice_source(t, "Maker space", found, uses, Request(), answer, None)


def _shipping(t: _Turn) -> None:
    actions = t.by_id("choose_shipping_influence")
    if not actions:
        return
    _influence_choice(
        t, "Shipping", _find(t.space, "GainAnyInfluenceAgentAbility"), actions
    )


def _influence_choice(
    t: _Turn,
    label: str,
    found: tuple[Ability, int] | None,
    actions: Sequence[DomainAction],
) -> None:
    """``GainAnyInfluenceAbility.Evaluate`` over the offered faction tracks,
    in ``FactionList`` order (the app's track order is UNTRACED)."""

    offered = set(_arg_refs(actions, "faction"))
    tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
    request = Request(infos=(TargetInfo(entities=tracks),))
    _choice_source(
        t, label, found, actions, request, _ref_or(actions, "faction", None), None
    )


def _desert_tactics(t: _Turn) -> None:
    trash = t.by_id("trash_card_for_desert_tactics")
    without = t.run.first("resolve_desert_tactics_without_trash")
    if not trash and without is None:
        return
    uses = (*trash, *((without,) if without is not None else ()))
    request = Request(
        infos=(TargetInfo(entities=_cards(t, _arg_refs(trash, "card_id"))),)
    )
    _choice_source(
        t,
        "Desert Tactics trash",
        _find(t.space, "TrashAgentAbility"),
        uses,
        request,
        _ref_or(trash, "card_id", without),
        None,
    )


def _imperial_privilege(t: _Turn) -> None:
    trash = t.by_id("trash_intrigue_for_imperial_privilege")
    decline = t.run.first("decline_imperial_privilege_intrigue")
    if trash or decline is not None:
        intrigues = tuple(
            intrigue_entity(ref, t.seat) for ref in _arg_refs(trash, "card_id")
        )
        _choice_source(
            t,
            "Imperial Privilege intrigue",
            _find(t.space, "ImperialPrivilegeAbility"),
            trash,
            Request(infos=(TargetInfo(entities=intrigues),)),
            _ref_or(trash, "card_id", None),
            decline,
        )
    recall = t.by_id("recall_agent_for_imperial_privilege")
    if recall:
        agents = tuple(
            agent_entity(space, t.seat) for space in _arg_refs(recall, "space_id")
        )
        # UNTRACED order: our engine draws the space's card with the recall;
        # the app draws it at state 600 unless the threshold is reached.
        _choice_source(
            t,
            "Imperial Privilege recall",
            _find(t.space, "RecallAgentAbility"),
            recall,
            Request(infos=(TargetInfo(entities=agents),)),
            _ref_or(recall, "space_id", None),
            None,
        )
    without = t.run.first("resolve_imperial_privilege_without_recall")
    if without is not None:
        _ability_source(
            t,
            "Imperial Privilege draw",
            _first_of(t.space, DrawAbility),
            _ROW_SPACE,
            without,
        )


# -- the card's Agent box -------------------------------------------------------------


def _card_box(t: _Turn) -> None:
    """``resolve_agent_card_effect`` (single box or one icon of a box)."""

    for action in t.by_id("resolve_agent_card_effect"):
        effect = str_arg(action, "effect")
        if effect is None:
            _single_box(t, action)
        else:
            _box_icon(t, action, effect)


def _single_box(t: _Turn, action: DomainAction) -> None:
    short = t.card_short or ""
    if short == "seek_allies":
        t.chores.append(action)  # TrashSelfAbility: Implicit, after End Turn
        return
    if short in _AGENT_BOX_CARDS:
        _automatic(t, f"{short} box", Stage.AGENT_BOX, action)
        return
    if short == "signet_ring":
        leader_id = t.run.ctx.me.leader_id or ""
        name = _SIGNET_BOX_ABILITY.get(leader_id)
        found = _find(t.leader, name) if name is not None else None
        _ability_source(t, f"signet {leader_id}", found, _ROW_LEADER, action)
        return
    name = _BOX_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        # A box with no app question (not in a 4-player Uprising game).
        _automatic(t, f"{short} box", Stage.AGENT_BOX, action)
        return
    request = (
        _contract_request(t) if isinstance(found[0], GainContractAbility) else None
    )
    _ability_source(t, f"{short} box", found, _ROW_CARD, action, request)


def _box_icon(t: _Turn, action: DomainAction, effect: str) -> None:
    short = t.card_short or ""
    label = f"{short} {effect}"
    if effect == "trash_self":
        t.chores.append(action)  # TrashSelfAbility: Implicit, after End Turn
        return
    if short in _ARMED_REWARD_CARDS:
        _automatic(t, label, _FOLLOW_UP, action, -1)
        return
    name = _ICON_ABILITY.get((short, effect))
    found = _find(t.card, name) if name is not None else None
    _ability_source(t, label, found, _ROW_CARD, action)


def _card_choices(t: _Turn) -> None:
    short = t.card_short or ""
    _card_trash(t, short)
    _card_discard(t, short)
    _card_payment(t, short)
    _corrinth_city(t)
    _card_intrigue_payment(t, short)
    _card_recall(t)
    _card_spy(t, short)
    _card_influence(t, short)
    _price_is_no_object(t)


def _card_trash(t: _Turn, short: str) -> None:
    trash = t.by_id("trash_agent_card")
    decline = t.run.first("decline_agent_card_trash")
    if not trash and decline is None:
        return
    name = _TRASH_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    refs = _arg_refs(trash, "card_id")
    if short == "shishakli":
        # ShishakliAgentAbility Targets: hand, then in play, then discard.
        me = t.run.ctx.me
        zones = (me.hand, me.in_play, me.discard_pile)
        refs = [ref for zone in zones for ref in zone if ref in refs]
    request = Request(infos=(TargetInfo(entities=_cards(t, refs)),))
    explicit = found is not None and _explicit(found[0], t.p)
    # Explicit trashes (TrashAbility) answer "nothing" with our decline.
    _choice_source(
        t,
        f"{short} trash",
        found,
        trash,
        request,
        _ref_or(trash, "card_id", decline if explicit else None),
        decline,
    )


def _card_discard(t: _Turn, short: str) -> None:
    discard = t.by_id("discard_agent_card")
    decline = t.run.first("decline_agent_card_discard")
    if not discard and decline is None:
        return
    name = _DISCARD_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    request = Request(
        infos=(TargetInfo(entities=_cards(t, _arg_refs(discard, "card_id"))),)
    )
    _choice_source(
        t,
        f"{short} discard",
        found,
        discard,
        request,
        _ref_or(discard, "card_id", None),
        decline,
    )


def _card_payment(t: _Turn, short: str) -> None:
    pay = t.by_id("pay_agent_card_water", "pay_agent_card_spice")
    decline = t.run.first("decline_agent_card_payment")
    if not pay and decline is None:
        return
    name = _PAYMENT_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    use = pay[0] if pay else None
    _choice_source(
        t, f"{short} payment", found, pay, Request(), lambda _a: use, decline
    )


def _corrinth_key(t: _Turn) -> tuple[object, ...]:
    return ("agent_effects", "corrinth_city", t.run.ctx.round_number, t.card_ref)


def _corrinth_city(t: _Turn) -> None:
    """``CorrinthCityAgentAbility``: one answer names both discards; ours
    takes them in two steps (the second is a follow-up, rule 6)."""

    select = t.by_id("select_corrinth_city_discard")
    pay = t.by_id("pay_corrinth_city")
    decline = t.run.first("decline_corrinth_city_payment")
    if not select and not pay and decline is None:
        return
    memory = t.run.memory.intents
    key = _corrinth_key(t)
    if pay:
        intent = memory.pop(key, None)
        second = intent[1] if isinstance(intent, tuple) and len(intent) == 2 else None
        chosen = with_arg(pay, "card_id", second) if second is not None else None
        if chosen is None:
            # No stored answer: the app's discard order over what is left.
            order = t.p.discard_order(_cards(t, _arg_refs(pay, "card_id")), False)
            chosen = with_arg(pay, "card_id", order[0].ref) if order else pay[0]
        if chosen is not None:
            _automatic(t, "Corrinth City second discard", _FOLLOW_UP, chosen, -1)
        return
    found = _find(t.card, "CorrinthCityAgentAbility")
    request = Request(
        infos=(TargetInfo(entities=_cards(t, _arg_refs(select, "card_id"))),)
    )

    def answer(ans: Answer) -> DomainAction | None:
        if ans.response is None or not ans.response[0]:
            return None
        refs = ans.response[0]
        if len(refs) >= 2:
            memory[key] = (refs[0], refs[1])
        return with_arg(select, "card_id", refs[0])

    _choice_source(t, "Corrinth City", found, select, request, answer, decline)


def _card_intrigue_payment(t: _Turn, short: str) -> None:
    uses = t.by_id("trash_intrigue_for_agent_card", "pay_agent_card_intrigue_and_spice")
    decline = t.run.first("decline_agent_card_intrigue_payment")
    if not uses and decline is None:
        return
    name = _INTRIGUE_PAYMENT_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    refs = _arg_refs(uses, "intrigue_card_id")
    intrigues = tuple(intrigue_entity(ref, t.seat) for ref in refs)
    _choice_source(
        t,
        f"{short} intrigue",
        found,
        uses,
        Request(infos=(TargetInfo(entities=intrigues),)),
        _ref_or(uses, "intrigue_card_id", None),
        decline,
    )


def _card_recall(t: _Turn) -> None:
    recall = t.by_id("recall_agent_for_agent_card")
    if not recall:
        return
    agents = tuple(
        agent_entity(space, t.seat) for space in _arg_refs(recall, "space_id")
    )
    _choice_source(
        t,
        "Steersman recall",
        _find(t.card, "RecallAgentAbility"),
        recall,
        Request(infos=(TargetInfo(entities=agents),)),
        _ref_or(recall, "space_id", None),
        None,
    )


def _card_spy(t: _Turn, short: str) -> None:
    place = t.by_id("place_agent_card_spy")
    recall = t.by_id("recall_spy_for_agent_card")
    decline = t.run.first("decline_agent_card_spy")
    if not place and not recall and decline is None:
        return
    name = _CARD_SPY_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    _spy_source(t, f"{short} spy", found, place, recall, decline, _CARD_SPY_RECALLED)


def _card_influence(t: _Turn, short: str) -> None:
    actions = t.by_id("choose_agent_card_influence")
    if not actions:
        return
    name = _CARD_INFLUENCE_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    _influence_choice(t, f"{short} influence", found, actions)


def _price_is_no_object(t: _Turn) -> None:
    row = t.by_id("acquire_imperium_with_solari")
    reserve = t.by_id("acquire_reserve_with_solari")
    decline = t.run.first("decline_agent_card_acquisition")
    if not row and not reserve and decline is None:
        return
    # UNTRACED (imperium-b §Price Is No Object): whether the app's targets
    # include the reserve; ours offers both, Row first.
    entities = [*_cards(t, _arg_refs(row, "instance_id"))]
    entities += [card_entity(f"reserve:{c}") for c in _arg_refs(reserve, "card_id")]

    def answer(ans: Answer) -> DomainAction | None:
        ref = _response_ref(ans)
        if not isinstance(ref, str):
            return None
        if ref.startswith("reserve:"):
            return with_arg(reserve, "card_id", card_id(ref))
        return with_arg(row, "instance_id", ref)

    _choice_source(
        t,
        "Price Is No Object",
        _find(t.card, "PriceIsNoObjectAbility"),
        (*row, *reserve),
        Request(infos=(TargetInfo(entities=tuple(entities)),)),
        answer,
        decline,
    )


# -- the leader ----------------------------------------------------------------------


def _leader_choices(t: _Turn) -> None:
    leader_id = t.run.ctx.me.leader_id
    if leader_id == "feyd_rautha_harkonnen":
        _feyd(t)
    elif leader_id == "lady_margot_fenring":
        _leader_spy(t, "ArrakisInformantAbility")
    elif leader_id == "staban_tuek":
        _staban(t)
    elif leader_id == "princess_irulan":
        _irulan(t)
    elif leader_id == "shaddam_corrino_iv":
        _shaddam(t)
    elif leader_id == "lady_jessica":
        name = (
            "WaterOfLifeSignetAbility"
            if t.run.ctx.me.leader_face_id == "reverend_mother_jessica"
            else "SpiceAgonyAbility"
        )
        _signet_payment(t, name, "pay_leader_signet_spice")
    _other_memories(t)
    _board_repeat(t)


def _signet_payment(t: _Turn, name: str, pay_id: str) -> None:
    pay = t.run.first(pay_id)
    decline = t.run.first("decline_leader_signet_payment")
    if pay is None and decline is None:
        return
    uses = (pay,) if pay is not None else ()
    _choice_source(
        t, name, _find(t.leader, name), uses, Request(), lambda _a: pay, decline
    )


def _feyd(t: _Turn) -> None:
    advance = t.by_id("advance_feyd_track")
    if advance:
        spaces = tuple(
            training_space_entity(ref) for ref in _arg_refs(advance, "space_id")
        )
        _choice_source(
            t,
            "Personal Training",
            _find(t.leader, "PersonalTrainingAbility"),
            advance,
            Request(infos=(TargetInfo(entities=spaces),)),
            _ref_or(advance, "space_id", None),
            None,
        )
    stage = str(t.context.get("feyd_track_stage") or "")
    trash = t.by_id("trash_leader_card")
    decline = t.run.first("decline_leader_card_trash")
    if trash or decline is not None:
        name = _FEYD_TRASH_ABILITY.get(stage, "PersonalTrainingTrashAbility")
        request = Request(
            infos=(TargetInfo(entities=_cards(t, _arg_refs(trash, "card_id"))),)
        )
        # TrashAbility E: an empty pick at 1.0. Our engine cannot pay
        # Pay-to-Trash's Solari for nothing: the empty pick is the decline
        # (docs/app-ai-plan.md §10).
        _choice_source(
            t,
            f"Personal Training {stage}",
            _find(t.leader, name),
            trash,
            request,
            _ref_or(trash, "card_id", decline),
            decline,
        )
    place = t.by_id("place_leader_spy")
    recall = t.by_id("recall_spy_for_leader_placement")
    spy_decline = t.run.first("decline_leader_spy_placement")
    if place or recall or spy_decline is not None:
        # The spy spaces grant ``PlaceSpyCustomAbility`` (a playmat custom
        # ability; its owner is never read).
        custom: tuple[Ability, int] | None = None
        if t.leader is not None:
            custom = (ability_for(_PLACE_SPY_CUSTOM, t.leader), 0)
        _spy_source(
            t,
            "Personal Training spy",
            custom,
            place,
            recall,
            spy_decline,
            _FEYD_SPY_RECALLED,
        )


def _leader_spy(t: _Turn, name: str, *, unseen_network: bool = False) -> None:
    place = t.by_id("place_leader_spy")
    recall = t.by_id("recall_spy_for_leader_placement")
    decline = t.run.first("decline_leader_spy_placement")
    if not place and not recall and decline is None:
        return
    _spy_source(
        t,
        name,
        _find(t.leader, name),
        place,
        recall,
        decline,
        _LEADER_SPY_RECALLED,
        unseen_network=unseen_network,
    )


def _staban(t: _Turn) -> None:
    _leader_spy(t, "UnseenNetworkAbility", unseen_network=True)
    if t.run.first("pay_leader_signet_solari") is not None:
        _signet_payment(t, "UnseenNetworkInfluenceAbility", "pay_leader_signet_solari")
    elif t.run.first("pay_leader_signet_spice") is not None:
        _signet_payment(t, "UnseenNetworkLandsraadAbility", "pay_leader_signet_spice")
    else:
        decline = t.run.first("decline_leader_signet_payment")
        if decline is not None:
            t.chores.append(decline)


def _irulan(t: _Turn) -> None:
    acquire = t.by_id("acquire_leader_imperium")
    trash = t.by_id("trash_leader_card")
    decline = t.run.first("decline_leader_signet_payment")
    if not acquire and not trash and decline is None:
        return
    p = t.p
    hand = _cards(t, _arg_refs(trash, "card_id"))
    options = (0, 1) if trash else (0,)
    request = Request(
        infos=(TargetInfo(options=options), TargetInfo(entities=hand)),
    )
    acquire_found = _find(t.leader, "ChroniclersInsightAcquireAbility")

    def answer(ans: Answer) -> DomainAction | None:
        """Option 1 trashes the named hand card; option 0 starts
        ``ChroniclersInsightAcquireAbility``, answered by its own E over the
        cost-1 cards we offer."""

        if _response_ref(ans) == 1:
            return with_arg(trash, "card_id", _response_ref(ans, 1))
        if not acquire or acquire_found is None:
            return None
        cards = _cards(t, _arg_refs(acquire, "instance_id"))
        follow = acquire_found[0].evaluate(
            p, Request(infos=(TargetInfo(entities=cards),))
        )
        return with_arg(acquire, "instance_id", _response_ref(follow))

    _choice_source(
        t,
        "Chronicler's Insight",
        _find(t.leader, "ChroniclersInsightAbility"),
        (*acquire, *trash),
        request,
        answer,
        decline,
    )


def _shaddam(t: _Turn) -> None:
    troop = t.run.first("gain_leader_signet_troop")
    influence = t.by_id("choose_leader_signet_influence")
    if troop is None and not influence:
        return
    offered = set(_arg_refs(influence, "faction"))
    tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
    request = Request(
        infos=(
            TargetInfo(options=(0, 1) if tracks else (0,)),
            TargetInfo(entities=tracks),
        )
    )

    def answer(ans: Answer) -> DomainAction | None:
        if _response_ref(ans) == 1:
            return with_arg(influence, "faction", _response_ref(ans, 1))
        return troop

    uses = (*((troop,) if troop is not None else ()), *influence)
    _choice_source(
        t,
        "Emperor of the Known Universe",
        _find(t.leader, "EmperorOfTheKnownUniverseSignetAbility"),
        uses,
        request,
        answer,
        None,
    )


def _other_memories(t: _Turn) -> None:
    use = t.run.first("use_other_memories")
    decline = t.run.first("decline_other_memories")
    if use is None and decline is None:
        return
    uses = (use,) if use is not None else ()
    _choice_source(
        t,
        "Other Memories",
        _find(t.leader, "OtherMemoriesAbility"),
        uses,
        Request(),
        lambda _a: use,
        decline,
    )


def _board_repeat(t: _Turn) -> None:
    pay = t.run.first("pay_leader_board_repeat")
    decline = t.run.first("decline_leader_board_repeat")
    if pay is None and decline is None:
        return
    uses = (pay,) if pay is not None else ()
    _choice_source(
        t,
        "Reverend Mother",
        _find(t.leader, "ReverendMotherAbility"),
        uses,
        Request(),
        lambda _a: pay,
        decline,
    )


# -- playmat, contracts, deployment, Plots ---------------------------------------------


def _track_spy(t: _Turn) -> None:
    """The Emperor-4 Spy: ``FactionTrackBonusAction`` grants
    ``PlaceSpyCustomAbility`` (Explicit; never immediate outside Combat)."""

    action = t.run.first("place_track_spy")
    if action is None:
        return
    ability = ability_for(_PLACE_SPY_CUSTOM, track_entity("emperor"))
    _ability_source(t, "Emperor track spy", (ability, 0), _ROW_PLAYMAT, action)


def _contracts(t: _Turn) -> None:
    me = t.run.ctx.me
    area = [*me.completed_contract_ids, *me.active_contract_ids]
    for action in t.by_id("complete_contract"):
        ref = str_arg(action, "instance_id")
        if ref is None:
            continue
        contract = contract_entity(ref, t.seat)
        found = _first_contract(contract)
        index = area.index(ref) if ref in area else len(area)
        if found is not None:
            found = (found[0], index)
        request = Request()
        if found is not None and ability_id(found[0]).endswith(
            "RecallAgentContractAbility"
        ):
            others = [s for s in me.agent_locations if s != t.space_id]
            agents = tuple(agent_entity(s, t.seat) for s in others)
            request = Request(infos=(TargetInfo(entities=agents),))
        _ability_source(t, f"contract {ref}", found, _ROW_CONTRACT, action, request)


def _first_contract(contract: Entity) -> tuple[Ability, int] | None:
    """``Abilities.OfType<ContractAbility>().FirstOrDefault()``."""

    return _first_of(contract, ContractAbility)


def _deploy(t: _Turn) -> None:
    """``DeployUnitsAbility``: 0.5 with ``GetUnitsToDeploy``'s units.

    UNTRACED (engine-order §9): the app exhausts the ability after one use
    in a turn (read so: ``IsUnexhausted`` in ``CanBeRun``); ours keeps
    offering the rest of the room, so a turn that already deployed
    (``combat_troops_deployed`` > 0) does not deploy again.
    """

    actions = t.by_id("deploy_troops")
    if not actions:
        return
    deployed = t.context.get("combat_troops_deployed", 0)
    if isinstance(deployed, int) and deployed > 0:
        return
    counts = [n for n in (int_arg(a, "count") for a in actions) if n is not None]
    maximum = max(counts) if counts else 0
    found = _first_of(t.space, DeployUnitsAbility)
    garrison = t.run.ctx.me.troops_garrison
    if found is None:
        # Sardaukar Coordination off a Combat space: its Targets take
        # ``TroopDeployNumber`` garrison units (the max).
        found = _find(t.card, "SardaukarCoordinationAgentAbility")
        garrison = maximum
    if found is None:
        return
    ability = found[0]
    request = Request(
        infos=(TargetInfo(options=tuple(range(garrison)), max_select=maximum),)
    )
    p = t.p

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None or not ans.response[0]:
            return ans.value, None
        count = min(len(ans.response[0]), maximum)
        return ans.value, with_arg(actions, "count", count)

    _prompt(t, "Deploy Units", actions, evaluate, explicit=False)


def _plots(t: _Turn) -> None:
    """Plots join the post-action prompt only once ``finish_agent_turn`` is
    legal (``docs/app-ai-plan.md`` §4.4)."""

    if t.run.first("finish_agent_turn") is None:
        return
    plays = t.by_id("play_intrigue")
    if plays:
        t.sources.extend(intrigue_play_sources(t.run, plays, combat=False))


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------


def _gather_intelligence(run: DecisionRun) -> DomainAction | None:
    """Agent-turn state 260: ``RecallSpyIntelligenceAbility::Evaluate``.

    A forced single-ability prompt (the ability is a playmat ability; its
    owner is never read). Option 1 recalls the Spy ``GetRecallSpy`` names
    (the second target info lists the observing Spies), option 0 declines.
    """

    gathers = run.by_id("gather_intelligence")
    decline = run.first("decline_gather_intelligence")
    seat = run.ctx.seat
    spies = tuple(spy_entity(post, seat) for post in _arg_refs(gathers, "post_id"))
    owner = track_entity("emperor")  # a stand-in: the playmat owns it
    ability = ability_for(_RECALL_SPY_INTELLIGENCE, owner)
    request = Request(
        infos=(TargetInfo(options=(0, 1)), TargetInfo(entities=spies)), forced=True
    )
    ans = ability.evaluate(run.profile, request)
    if _response_ref(ans) == 1 and gathers:
        ref = _response_ref(ans, 1)
        chosen = with_arg(gathers, "post_id", ref) if ref is not None else None
        return chosen or gathers[0]
    return decline if decline is not None else (gathers[0] if gathers else None)


def agent_effects_window(run: DecisionRun) -> DomainAction | None:
    """The app's answer to one ``agent_effects`` decision (module docstring)."""

    if run.first("gather_intelligence") or run.first("decline_gather_intelligence"):
        return _gather_intelligence(run)
    t = _turn(run)
    _board_icons(t)
    _maker(t)
    _sietch_tabr(t)
    _espionage(t)
    _shipping(t)
    _desert_tactics(t)
    _imperial_privilege(t)
    _faction_influence_source(t)
    _card_box(t)
    _card_choices(t)
    _leader_choices(t)
    _track_spy(t)
    _contracts(t)
    _deploy(t)
    _plots(t)
    finish = run.first("finish_agent_turn")
    skip = next(iter((*t.declines, *t.chores)), finish)
    forced = any(
        s.stage is Stage.PROMPT and s.extra.get("explicit") is True for s in t.sources
    )
    return decide(run, t.sources, skip=skip, forced=forced)


HANDLERS: dict[str, Handler] = {"agent_effects": agent_effects_window}
