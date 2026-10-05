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

Immortality, Epic Game Mode and the promos (``spec/immortality.md`` §4-§8,
``spec/epic-goto11-promo-draft.md`` §2.3, §4, §6):

- Graft (``switch_graft_card``). The app holds both cards' agent boxes in
  ``chosenAgentAbilities`` (the played card, then the grafted card; engine
  order §3.2) and their deferred abilities side by side; our engine shows
  one box at a time. The window also builds the inactive box's sources on
  the switched state (``_partner_box``) and competes both: the played
  card's 500 box before the partner's (``rank``), the card row in that
  order at 600, values in the prompt. A partner winner is realised by
  ``switch_graft_card`` and remembered (``_GRAFT_SWITCH_INTENT``) so the
  next decision takes it; the empty answer needs the partner's Optional
  keys declined first (switch, then decline). Ghola's box is the partner's
  (valued by the partner's abilities) and runs at state 210 like the
  ``SpecimenAgentAbility`` box (Bene Tleilax Lab).
- Single boxes (``_expansion_box``): Research (Experimentation, Bene
  Tleilax Researcher, Scientific Breakthrough, the Research Station's
  ``research`` icon) is ``GainResearchAgentAbility`` (Explicit) at its E
  over the next research spaces; Tleilaxu, influence and draw riders their
  card's deferred ability (``_EXPANSION_BOX_ABILITY``), gated by its
  ``Cost`` (a failing Cost has no app key: the box is a chore); boxes with
  only printed gains are the generic box (500). Two app steps in one action
  take the asking one's stage: Clandestine Meeting (intrigue + influence),
  Stillsuit Manufacturer (water + return), Throne Room Politics (troop +
  ``TrashAgentAbility``), Industrial Espionage (specimen + research + draw).
- Card choices: Organ Merchants, Tleilaxu Surgeon (never past Tleilaxu rank
  7: the Cost fails), Dissecting Kit, Scientific Breakthrough, Piter (the
  zone of the first troop the app names), Replacement Eyes, Twisted Mentat,
  Tleilaxu Master (``acquire_*_by_card``), For Humanity and Interstellar
  Conspiracy (``GainAnyInfluenceAbility``), Beguiling Pheromones, High
  Priority Travel (option 0 draw / 1 Combat icon), Slig Farmer (the
  Tleilaxu key answered on the state after the Solari), and the two-step
  answers of Long Reach and Stitched Horror (second pick in
  ``Memory.intents``; Stitched Horror's trash card for ``optional_trash``).
- Control the Spice pays iff its E names a card (the card is kept for the
  ``optional_trash`` window, ``CONTROL_THE_SPICE_TRASH_INTENT``); Arrakis
  Revolt pays at its E and picks the wall variant iff ``ShouldBlowWall`` on
  the paid state; Pivotal Gambit's E 100 trashes the card, its troop and
  pledge are follow-ups; The Beast's Spoils' riders are immediate and its
  Crysknife is a ``TrashAbility``.
- ``return_specimen`` / ``use_family_atomics``: the playmat keys
  ``ReturnSpecimenAbility`` (E 1.0 for the troop shortfall only) and
  ``FamilyAtomicsAbility`` (E only in a Reveal turn: never here), prompt
  sources like any other key, so a mid-effect offer (our engine offers them
  at every decision) is never taken before the app's prompt opens.
Bloodlines, the Tech Module and Arrakeen Scouts (app-style extensions,
``docs/app-ai-plan.md`` §11; ``docs/app-ai/bloodlines-cards.md`` §8,
``bloodlines-systems.md`` §2.3, §3.4, §4, §6, ``scouts.md`` §3.3, §3.5):

- The space: ``acquire_sardaukar_commander`` / ``decline_sardaukar_commander``
  is ``AcquireCommanderAbility`` (E; the empty answer at 0.5 declines; no
  purchase offered: the refusal is a chore); the Landsraad visit's
  ``acquire_tech`` / ``decline_tech`` is the RoI ``AcquireTechAbility`` (E,
  likewise; Advanced Data Analysis boxes the worst-post Spy); a bought
  tile's ``resolve_tech_acquire_effect`` keys are follow-ups in the engine's
  key order (Memocorders' track, Gene-Locked Vault's choice,
  ``ShouldBlowWall``; D15); ``take_tuek_sietch_*`` is
  ``TueksSietchDeferredAbility`` (E); Hagga Basin's ``DesertRidingAbility``
  answers option 2 with ``take_desert_riding_hooks``;
  ``scouts_collect_mission`` is ``MissionPiecesSpaceAbility``, automatic at
  state 400 in its icon's place; ``choose_subcommittee`` is
  ``SubcommitteeOfferAbility`` (O; its pick kept for the
  ``scouts_subcommittee`` window, ``SUBCOMMITTEE_INTENT``),
  ``decline_subcommittee`` the unused key.
- The card: ``_BLOODLINES_BOX_ABILITY`` boxes gated by their ``Cost``,
  Ixian Ambassador and Quash Rebellion the generic box (500), the Bond
  choices of Southern Faith and Possible Futures (``_bond_choice``),
  Fremen War Name's icons (gated), the trash / discard tables (Ruthless
  Leadership, Eliminate Allies, Elite Forces whose reward icons follow;
  Arrakis Observer, whose Spy with Deep Cover follows, Engineered
  Miracle, I Believe), CHOAM Demands' ``complete_contract_by_card`` and
  Disruption Tactics' ``retreat_opponent_troop`` (E, forced).
- The leader: Harkonnen Advisor (``WarmasterAbility``) and Judge of the
  Change run by themselves; Fedaykin Maneuver, Corrino Liaison, Into the
  Fray and Listeners (O), Smuggle Spice and Reverse Engineering (E) are
  their ``SignetAbility`` keys (``_BLOODLINES_SIGNETS``); Duncan's Into the
  Fray Agent is the last recall candidate (D55: Steersman, Imperial
  Privilege, and the targets a ``RecallAgentContractAbility`` key is valued
  with); Mohiam's mandatory Gather Intelligence recalls ``GetRecallSpy``'s
  Spy even when the app's answer is "no" (§4.5).
- The playmat: ``flip_tech`` (the tile's Flip key, O) and
  ``recruit_sardaukar_commander`` (``RecruitCommanderAbility``, O).
- Deployment: troops and Commanders are the garrison units (D1); the count
  is split by kind, the other kind kept as a follow-up (D6,
  ``DEPLOY_SPLIT_INTENT``); off a Combat space a ``DeployUnitsAbility`` key
  (D61). ``withdraw_commanders``: never.
- These ids are known only in a game with the option
  (``_BLOODLINES_ACTION_IDS``, ``_SCOUTS_ACTION_IDS``).

- An action no builder maps (an unknown card or icon) is not guessed:
  the window returns None and the agent falls back (counted). The same
  holds where a builder finds no app ability to rank the action (a leader's
  Signet box outside ``_SIGNET_BOX_ABILITY``, a space or contract without
  the ability, a choice whose ability the owner lacks): no automatic
  resolution, no silent drop. A legal action id the window does not know
  at all (``_KNOWN_ACTION_IDS``) makes the decision fall back too, instead
  of being left out of the ranking unseen.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to a random legal
action (``DefaultRandomChoice``), counted in ``AppAIAgent.fallbacks``.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    abilities_of,
    ability_for,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_cards import (
    retreat_target_code,
    retreat_target_of,
)
from dune_imperium.agents.app_ai.abilities.board import (
    BeneGesseritContractAbility,
)
from dune_imperium.agents.app_ai.abilities.epic_promo import (
    ArrakisRevoltAbility,
    ControlTheSpiceAbility,
    find_trash_targets,
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
    DEPLOY_UNITS_ABILITY,
    LEADER_ARCHETYPES,
    agent_entity,
    card_entity,
    commander_entity,
    contract_entity,
    intrigue_entity,
    leader_entity,
    skill_entity,
    skill_id_of,
    space_entity,
    spy_entity,
    tech_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, AppContext, card_id
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.immortality import research_space_entity
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
from dune_imperium.agents.app_ai.windows.run import (
    DecisionRun,
    Handler,
    Memory,
    arg,
)
from dune_imperium.agents.app_ai.windows.turn import board_space_order, playmat_sources
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.rules.agent_effect_frame import legal_agent_effect_frame_actions
from dune_imperium.rules.agent_effects import STITCHED_HORROR_REWARDS
from dune_imperium.rules.frames import COMMANDERS_RECRUITED_KEY
from dune_imperium.rules.graft import apply_graft_switch

_AU = "worm.canis.abilities.ActivatedAbilities.Uprising."
_PLACE_SPY_CUSTOM = _AU + "PlaceSpyCustomAbility"
_RECRUIT_COMMANDER = "worm.canis.abilities.AppStyle.Bloodlines.RecruitCommanderAbility"
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
    # Immortality multi-icon boxes (``_PLACEMENT_ICONS`` of our engine).
    ("sardaukar_quartermaster", "troops"): "SardaukarQuartermasterTroopAbility",
    ("sardaukar_quartermaster", "cards"): "SardaukarQuartermasterDrawAbility",
    ("tleilaxu_infiltrator", "cards"): "DrawAbility",
    ("tleilaxu_infiltrator", "intrigue"): "TleilaxuInfiltratorAbility",
    # Bloodlines (bloodlines-cards.md §3.12): each icon waits until two spice
    # were gained (OQ-057 (1)); gated by its Cost (``_GATED_ICON_CARDS``).
    ("fremen_war_name", "troops"): "FremenWarNameTroopAbility",
    ("fremen_war_name", "cards"): "FremenWarNameDrawAbility",
}
#: Multi-icon boxes whose icon ability is gated by its ``Cost`` (a failing
#: Cost has no app key: the icon is a chore), as ``_gated_ability_source``.
_GATED_ICON_CARDS = ("fremen_war_name",)
#: Cards whose reward icons are armed after an arrow cost: the app answered
#: the whole ability at once, so the icons are follow-ups. Elite Forces
#: (bloodlines-cards.md §3.10): its E names the Emperor card, the Intrigue,
#: troop (and Combat icon) follow.
_ARMED_REWARD_CARDS = ("captured_mentat", "guild_spy", "branching_path", "elite_forces")
#: Our trash choice of each card -> its app ability.
_TRASH_ABILITY: Mapping[str, str] = {
    "calculus_of_power": "TrashAgentAbility",
    "desert_survival": "TrashAgentAbility",
    "shishakli": "ShishakliAgentAbility",
    "tread_in_darkness": "BeneGesseritTrashAbility",
    "treacherous_maneuver": "TreacherousManeuverAbility",
    # Immortality / promo: Optional (an unused key is the decline) and the
    # Crysknife ``TrashAbility`` (Explicit: "nothing" is the decline).
    "replacement_eyes": "ReplacementEyesAgentAbility",
    "the_beast_s_spoils": "TheBeastsSpoilsCrysknifeAbility",
    # Bloodlines (bloodlines-cards.md §3.1, §3.9, §3.10): Ruthless
    # Leadership's two keys (one per trash, both ``TrashAbility``: an empty
    # pick is the decline), Eliminate Allies' generic ``TrashAgentAbility``,
    # Elite Forces' Optional hand trash.
    "ruthless_leadership": "RuthlessLeadershipTrashAbility",
    "eliminate_allies": "TrashAgentAbility",
    "elite_forces": "EliteForcesAgentAbility",
}
_DISCARD_ABILITY: Mapping[str, str] = {
    "captured_mentat": "CapturedMentatAgentAbility",
    "guild_spy": "GuildSpyAgentAbility",
    "space_time_folding": "SpacetimeFoldingAbility",
    "guild_envoy": "GuildEnvoyAbility",
    "delivery_agreement": "DeliveryAgreementAgentAbility",
    # Bloodlines (bloodlines-cards.md §2.4): ``DiscardForRewardAgentAbility``
    # (Optional; the unused key is the decline).
    "arrakis_observer": "ArrakisObserverAgentAbility",
    "engineered_miracle": "EngineeredMiracleAgentAbility",
    "i_believe": "IBelieveAgentAbility",
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
    # Immortality: ``GainAnyInfluenceAbility`` subclasses (Explicit).
    "for_humanity": "ForHumanityAgentAbility",
    "interstellar_conspiracy": "InterstellarConspiracyAbility",
}
#: Immortality, Epic and promo single boxes resolved by the card's own
#: deferred ability (app class short name), as ``_BOX_ABILITY``; the
#: ability's ``Cost`` gates it (``_gated_ability_source``).
_EXPANSION_BOX_ABILITY: Mapping[str, str] = {
    "corrupt_smuggler": "CorruptSmugglerAbility",
    "imperium_ceremony": "ImperiumCeremonyAbility",
    "keys_to_power": "KeysToPowerAbility",
    "lisan_al_gaib": "LisanAlGaibAgentAbility",
    "occupation": "DrawAbility",
    "planned_coupling": "DrawAbility",
    "show_of_strength": "DrawAbility",
    "face_dancer": "DrawAbility",
    "unnatural_reflexes": "UnnaturalReflexesAbility",
    "contaminator": "GainTleilaxuInfluenceAgentAbility",
    "corrino_genes": "CorrinoGenesAbility",
    "subject_x_137": "SubjectX137Ability",
    "guild_impersonator": "GuildImpersonatorAbility",
    "slig_farmer": "SligFarmerSolariAbility",
}
#: Expansion cards whose box resolution is only the card's generic
#: ``AgentAbility`` (printed ``AgentTroops``/``AgentSpice``/``AgentWater`` or
#: nothing; state 500): their card text has no app question, or its rider's
#: ``Cost`` fails so the engine offers only the plain resolution.
_EXPANSION_GENERIC_BOX_CARDS = (
    "blank_slate",
    "spiritual_fervor",
    "shadout_mapes",
    "face_dancer_initiate",
    "usurp",
    "chairdog",
    "from_the_tanks",
    "interstellar_conspiracy",
    "dissecting_kit",
    "organ_merchants",
    "tleilaxu_surgeon",
    "tleilaxu_master",
    "high_priority_travel",
    "piter_genius_advisor",
    "control_the_spice",
    "arrakis_revolt",
    "pivotal_gambit",
)
#: Agent boxes the app runs at ``AgentTurnPhase`` state 210
#: (``ResolveFirstAbilities @0x49e13e0``: the Ghola box, else the
#: ``SpecimenAgentAbility`` boxes; spec immortality.md §4.5).
_FIRST_BOX_CARDS = ("bene_tleilax_lab",)
#: State 210 runs before the space (220/400): placed with the follow-ups.
_FIRST_ABILITY_ORDER = -2
#: Every single box ``_expansion_box`` answers.
_EXPANSION_BOX_CARDS = frozenset(
    {
        *_EXPANSION_BOX_ABILITY,
        *_EXPANSION_GENERIC_BOX_CARDS,
        *_FIRST_BOX_CARDS,
        "experimentation",
        "bene_tleilax_researcher",
        "scientific_breakthrough",
        "clandestine_meeting",
        "stillsuit_manufacturer",
        "throne_room_politics",
        "industrial_espionage",
        "the_beast_s_spoils",
    }
)
#: Single boxes whose plain resolution is one option of a combined choice
#: answered by the payment handlers (the box action is consumed there).
_BOX_HANDLED_BY_CHOICE: Mapping[str, str] = {
    "high_priority_travel": "take_agent_card_combat_icon",
    "slig_farmer": "pay_agent_card_five_solari_for_tleilaxu",
}
#: Cards whose reward icons follow a one-step app answer (Pivotal Gambit:
#: ``BeginExecution`` trashes the card, recruits and pledges at once).
_FOLLOW_UP_ICON_CARDS = ("pivotal_gambit",)
#: Our payment-family action ids (``legal_agent_card_payment_actions``).
_PAYMENT_IDS = (
    "pay_agent_card_water",
    "pay_agent_card_spice",
    "decline_agent_card_payment",
    "pay_agent_card_specimen",
    "pay_agent_card_two_specimens",
    "trash_grafted_card_for_specimen",
    "take_agent_card_combat_icon",
    "trash_agent_card_self_for_vp",
    "pay_agent_card_five_solari_for_tleilaxu",
    "trash_grafted_card_for_influence",
    "lose_agent_card_troop",
    "choose_agent_card_reward",
    "pay_agent_card_spice_for_sandworm",
    "pay_agent_card_spice_for_sandworm_and_shield_wall",
)
#: ``Memory.intents`` keys this window writes (and the next window reads):
#: ``(CONTROL_THE_SPICE_TRASH_INTENT, round, card ref) -> trash ref | None``
#: (the ``optional_trash`` window), ``(STITCHED_HORROR_TRASH_INTENT, round,
#: card ref) -> trash ref`` (the ``optional_trash`` window, Stitched Horror's
#: trash reward), ``(_GRAFT_SWITCH_INTENT, round, partner ref) -> (action,
#: intents)`` (this window, after ``switch_graft_card``), and the second pick
#: of Long Reach / Stitched Horror (this window).
CONTROL_THE_SPICE_TRASH_INTENT = "control_the_spice_trash"
STITCHED_HORROR_TRASH_INTENT = "stitched_horror_trash"
_GRAFT_SWITCH_INTENT = "agent_effects_graft_switch"
_PARTNER_LABEL = "graft partner | "
#: Signet boxes resolved by ``resolve_agent_card_effect()``, by leader.
_SIGNET_BOX_ABILITY: Mapping[str, str] = {
    "gurney_halleck": "WarmasterAbility",
    "lady_amber_metulli": "FillCoffersAbility",
    "muad_dib": "LeadTheWayAbility",
    # Bloodlines (bloodlines-systems.md §4.6, §4.8): Harkonnen Advisor reuses
    # ``WarmasterAbility`` (D41); Judge of the Change runs by itself (D45).
    "piter_de_vries": "WarmasterAbility",
    "liet_kynes": "JudgeOfTheChangeSignetAbility",
}
#: Bloodlines Agent boxes resolved by ``resolve_agent_card_effect()`` and the
#: card's own ability (bloodlines-cards.md §3), gated by its ``Cost`` (a box
#: whose Cost fails has no app key: a chore).
_BLOODLINES_BOX_ABILITY: Mapping[str, str] = {
    "holy_war": "HolyWarAgentAbility",
    "urgent_shigawire": "UrgentShigawireAgentAbility",
    "imperial_throneship": "AgentGainIntrigueAbility",
    "shrouded_counsel": "AgentGainIntrigueAbility",
    "command_center": "CommandCenterAgentAbility",
    "sandwalk": "SandwalkDrawAbility",
    "mercantile_affairs": "MercantileAffairsAgentAbility",
    "pointing_the_way": "PointingTheWayAgentAbility",
    "corrupt_bureaucrat": "CorruptBureaucratAgentAbility",
    # Without the Bene Gesserit Bond the box is the draw alone (option 0).
    "southern_faith": "SouthernFaithAgentAbility",
}
#: Bloodlines boxes with printed gains only (``AgentSpice`` / ``AgentSolari``):
#: the generic agent box (state 500).
_BLOODLINES_GENERIC_BOX_CARDS = ("ixian_ambassador", "quash_rebellion")
#: Bond choices whose plain resolution is one option of the card's influence
#: choice (``_bond_choice``): the box action is consumed there.
_BOND_CHOICE_CARDS: Mapping[str, str] = {
    "southern_faith": "SouthernFaithAgentAbility",
    "possible_futures": "PossibleFuturesAgentAbility",
}
#: Tech tiles with a Flip activation -> its app-style ability
#: (bloodlines-systems.md §3.3, D23-D25).
_FLIP_ABILITY: Mapping[str, str] = {
    "advanced_data_analysis": "AdvancedDataAnalysisAbility",
    "spy_drones": "SpyDronesAbility",
    "rapid_dropships": "RapidDropshipsAbility",
}
#: The Into the Fray Agent as a recall candidate (``Kind.AGENT`` whose ref is
#: no space: ``GetRecallAgent`` skips it, bloodlines-systems.md §8, D55).
_CONFLICT_AGENT = "conflict"
#: ``Memory.intents`` keys of the Bloodlines and Scouts answers this window
#: writes: ``(DEPLOY_SPLIT_INTENT, round, seat, card ref) -> (action id,
#: count)`` (the other kind of a split deployment, this window) and
#: ``(SUBCOMMITTEE_INTENT, round, seat) -> subcommittee id`` (the
#: ``scouts_subcommittee`` window, scouts.md §3.3).
DEPLOY_SPLIT_INTENT = "agent_effects_deploy_split"
SUBCOMMITTEE_INTENT = "subcommittee"
#: An ``on_choose`` value that drops its key (a follow-up used up).
_DROP: object = object()
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
#: Every action id this window ranks, realises, takes as a decline or chore,
#: or leaves on purpose (``withdraw_troops``: the app never withdraws; Plots
#: before End Turn; a second deployment). A legal id outside this set has no
#: app mapping here, so the decision falls back (counted) rather than the
#: id being skipped without a trace (Bloodlines' Commanders and tech,
#: Arrakeen Scouts' missions and subcommittees, ...).
_KNOWN_ACTION_IDS: frozenset[str] = frozenset(
    {
        "acquire_imperium_by_card",
        "acquire_imperium_with_solari",
        "acquire_leader_imperium",
        "acquire_reserve_by_card",
        "acquire_reserve_with_solari",
        "advance_feyd_track",
        "choose_agent_card_influence",
        "choose_agent_card_reward",
        "choose_leader_signet_influence",
        "choose_shipping_influence",
        "complete_contract",
        "decline_agent_card_acquisition",
        "decline_agent_card_discard",
        "decline_agent_card_intrigue_payment",
        "decline_agent_card_payment",
        "decline_agent_card_recall",
        "decline_agent_card_spy",
        "decline_agent_card_trash",
        "decline_corrinth_city_payment",
        "decline_gather_intelligence",
        "decline_imperial_privilege_intrigue",
        "decline_leader_board_repeat",
        "decline_leader_card_trash",
        "decline_leader_signet_payment",
        "decline_leader_spy_placement",
        "decline_other_memories",
        "deploy_troops",
        "discard_agent_card",
        "finish_agent_turn",
        "gain_leader_signet_troop",
        "gather_intelligence",
        "harvest_maker_spice",
        "lose_agent_card_troop",
        "pay_agent_card_five_solari_for_tleilaxu",
        "pay_agent_card_intrigue_and_spice",
        "pay_agent_card_specimen",
        "pay_agent_card_spice",
        "pay_agent_card_spice_for_sandworm",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
        "pay_agent_card_two_specimens",
        "pay_agent_card_water",
        "pay_corrinth_city",
        "pay_leader_board_repeat",
        "pay_leader_signet_solari",
        "pay_leader_signet_spice",
        "place_agent_card_spy",
        "place_leader_spy",
        "place_track_spy",
        "play_intrigue",
        "recall_agent_for_agent_card",
        "recall_agent_for_imperial_privilege",
        "recall_conflict_agent_for_agent_card",
        "recall_spy_for_agent_card",
        "recall_spy_for_espionage",
        "recall_spy_for_leader_placement",
        "resolve_agent_card_effect",
        "resolve_board_effect",
        "resolve_desert_tactics_without_trash",
        "resolve_espionage_place_spy",
        "resolve_espionage_without_spy",
        "resolve_faction_influence",
        "resolve_imperial_privilege_without_recall",
        "return_specimen",
        "select_corrinth_city_discard",
        "summon_maker_sandworms",
        "switch_graft_card",
        "take_agent_card_combat_icon",
        "take_sietch_tabr_supplies",
        "take_sietch_tabr_water",
        "take_sietch_tabr_water_and_destroy_wall",
        "trash_agent_card",
        "trash_agent_card_self_for_vp",
        "trash_card_for_desert_tactics",
        "trash_grafted_card_for_influence",
        "trash_grafted_card_for_specimen",
        "trash_intrigue_for_agent_card",
        "trash_intrigue_for_imperial_privilege",
        "trash_leader_card",
        "use_family_atomics",
        "use_other_memories",
        "withdraw_troops",
    }
)
#: The ids Bloodlines and the Tech Module add (bloodlines-cards.md §8,
#: bloodlines-systems.md §2.3, §3.4, §4; ``withdraw_commanders``: never),
#: known only in a Bloodlines game (an unexpected one falls back).
_BLOODLINES_ACTION_IDS: frozenset[str] = frozenset(
    {
        "acquire_sardaukar_commander",
        "acquire_tech",
        "complete_contract_by_card",
        "decline_sardaukar_commander",
        "decline_tech",
        "deploy_commanders",
        "deploy_leader_agent",
        "flip_tech",
        "gain_leader_signet_spice",
        "pay_leader_signet_water",
        "place_leader_bonus_spice",
        # Imperial Privilege recalling Duncan's Into the Fray Agent (D55,
        # ``_imperial_privilege``).
        "recall_conflict_agent_for_imperial_privilege",
        "recruit_sardaukar_commander",
        "resolve_tech_acquire_effect",
        "retreat_leader_troops",
        "retreat_opponent_troop",
        "take_leader_bonus_spice",
        "take_tuek_sietch_card",
        "take_tuek_sietch_spice",
        "trash_leader_tech",
        "withdraw_commanders",
    }
)
#: The ids Arrakeen Scouts adds here (scouts.md §3.3, §3.5), known only in a
#: Scouts game.
_SCOUTS_ACTION_IDS: frozenset[str] = frozenset(
    {
        "choose_subcommittee",
        "decline_subcommittee",
        "scouts_collect_mission",
        "take_desert_riding_hooks",
    }
)

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
    #: The other grafted card of this turn (``graft_card_id``), if any.
    partner_ref: str | None = None
    #: The active card's place in the app's ``chosenAgentAbilities`` (0: the
    #: played card, 1: the grafted card; 0 without a graft).
    rank: int = 0
    #: The active card is Ghola: its box is the partner's (``card_short`` and
    #: ``card`` name the borrowed card).
    ghola: bool = False
    #: Legal actions this window has no app mapping for: the window falls
    #: back (``DefaultRandomChoice``, counted) instead of guessing.
    unmapped: list[str] = field(default_factory=list)
    #: ``Memory.intents`` entries to write when an action is chosen (an app
    #: answer whose rest our engine asks later).
    on_choose: dict[DomainAction, list[tuple[tuple[object, ...], object]]] = field(
        default_factory=dict
    )

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
            space = space_entity(space_id, ctx.board)
        except KeyError:
            space = None
    else:
        space_id = None
    me = ctx.me
    leader: Entity | None = None
    if me.leader_id is not None and me.leader_id in LEADER_ARCHETYPES:
        leader = leader_entity(me.leader_id, me.leader_face_id)
    partner = context.get("graft_card_id")
    partner_ref = partner if isinstance(partner, str) and partner else None
    ghola = False
    if partner_ref is not None and card_short == "ghola":
        # "This card has the same Agent box as the other grafted card"
        # [Ghola card face]: the box being resolved is the partner's.
        ghola = True
        card_short = card_id(partner_ref)
        try:
            card = card_entity(partner_ref, ctx.seat)
        except KeyError:
            card = None
    t = _Turn(run, context, card_ref, card_short, card, space_id, space, leader)
    t.partner_ref = partner_ref
    t.ghola = ghola
    if partner_ref is not None and isinstance(card_ref, str):
        t.rank = _graft_rank(me.in_play, card_ref, partner_ref)
    t.additional_space_influence = _additional_space_influence(t)
    return t


def _graft_rank(in_play: Sequence[str], card_ref: str, partner_ref: str) -> int:
    """The active card's index in ``chosenAgentAbilities`` (spec
    engine-order §3.2): the played card first, the grafted card second.

    Our engine puts the placed card into play first and appends the partner
    (``apply_graft_partner``), so the play order tells them apart; a card no
    longer in play (trashed) keeps rank 0.
    """

    if card_ref not in in_play or partner_ref not in in_play:
        return 0
    return 1 if in_play.index(card_ref) > in_play.index(partner_ref) else 0


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
    """Stable ``OrderBy(WillClearUndo)`` over the row order (row, index).

    Inside the card row the grafted card's abilities follow the played
    card's (``ActiveCards`` order; ``t.rank``).
    """

    clears = _will_clear_undo(ability, t.p, t.additional_space_influence)
    card_rank = t.rank * 50 if row == _ROW_CARD else 0
    return (1 if clears else 0) * 10_000 + row * 100 + card_rank + index


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
    not a candidate). Without an app ability (an unknown leader's Signet
    box, a space or contract with no such ability) nothing is guessed: the
    window falls back (``t.unmapped``).
    """

    if found is None:
        t.unmapped.append(label)
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
    targets fail) and the decline is a chore. Uses with no app ability to
    rank them are not guessed: the window falls back (``t.unmapped``).
    """

    if decline is not None:
        t.declines.append(decline)
    if not uses:
        return
    if found is None:
        t.unmapped.append(label)
        return
    ability, _index = found
    p = t.p

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None:
            return ans.value, None
        return ans.value, answer(ans)

    _prompt(t, label, uses, evaluate, explicit=_explicit(ability, p))


def _box_auto(t: _Turn, label: str, action: DomainAction) -> None:
    """The card's generic agent box: state 500 in ``chosenAgentAbilities``
    order (``t.rank``), or state 210 for the first abilities (a Ghola box, a
    ``SpecimenAgentAbility`` box)."""

    if t.ghola or t.card_short in _FIRST_BOX_CARDS:
        _automatic(t, label, Stage.COST_FIRST, action, _FIRST_ABILITY_ORDER)
    else:
        _automatic(t, label, Stage.AGENT_BOX, action, t.rank)


def _gated_ability_source(
    t: _Turn,
    label: str,
    found: tuple[Ability, int] | None,
    row: int,
    action: DomainAction,
    request: Request | None = None,
) -> None:
    """``_ability_source`` for an expansion box, gated by the ability's
    ``Cost``: when it fails the app has no key (``CanBeRun``), so our
    mandatory, now effect-less resolution is a chore taken at End Turn."""

    if found is None:
        t.unmapped.append(label)
        return
    ability = found[0]
    if isinstance(ability, DeferredAbility) and not ability.meets_cost(t.p):
        t.chores.append(action)
        return
    _ability_source(t, label, found, row, action, request)


def _research_request(t: _Turn) -> Request:
    """``GainResearchAbility`` targets: the next research spaces in the app's
    order (``NextIndices``, lower index first; none with two markers)."""

    spaces = tuple(
        research_space_entity(space_id)
        for space_id in t.run.ctx.research_next_space_ids()
    )
    return Request(infos=(TargetInfo(entities=spaces),))


def _trash_request(t: _Turn) -> Request:
    """``FindTrashTargets(null)``: the targets of a ``TrashAbility``."""

    return Request(infos=(TargetInfo(entities=find_trash_targets(t.p)),))


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
        elif effect == "research":
            # The Immortality Research Station: ``GainResearchAgentAbility``
            # (Explicit, never auto-run; spec immortality.md §3.1) at its E
            # over the next research spaces.
            found = _find(t.space, "GainResearchAgentAbility")
            if found is None:
                t.unmapped.append(label)
            else:
                _ability_source(
                    t, label, found, _ROW_SPACE, action, _research_request(t)
                )
        else:  # no app twin (Bloodlines' tech, commander, ...)
            t.unmapped.append(label)


def _contract_request(t: _Turn) -> Request:
    """``GainContractAbility.MakeTargets``: the contract options."""

    options = tuple(contract_entity(ref) for ref in _contract_options(t.p))
    return Request(infos=(TargetInfo(entities=options),))


def _faction_influence_source(t: _Turn) -> None:
    action = t.run.first("resolve_faction_influence")
    if action is None:
        return
    # A space with no app ``GainInfluenceAbility`` falls back (no guess).
    found = _first_of(t.space, GainInfluenceAbility)
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
        t.unmapped.append(label)  # no app ability to place it: no guess
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
    # Arrakeen Scouts swaps Hagga Basin's ability for ``DesertRidingAbility``
    # (a ``HaggaBasinUprisingDeferredAbility``; scouts.md §3.5, §4.2, D27):
    # its option 2 takes the Desert Riding hooks.
    found = (
        _find(t.space, "DesertRidingAbility")
        or _find(t.space, "HaggaBasinUprisingDeferredAbility")
        or _find(t.space, "DeepDesertDeferredAbility")
    )
    hooks = t.run.first("take_desert_riding_hooks")
    uses = tuple(a for a in (harvest, summon, hooks) if a is not None)

    def answer(ans: Answer) -> DomainAction | None:
        option = _response_ref(ans)
        if option == 2 and hooks is not None:
            return hooks
        if option == 1 and summon is not None:
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
    conflict = t.run.first("recall_conflict_agent_for_imperial_privilege")
    if recall or conflict is not None:
        # UNTRACED order: our engine draws the space's card with the recall;
        # the app draws it at state 600 unless the threshold is reached.
        # Duncan's Into the Fray Agent is the last candidate (D55).
        _choice_source(
            t,
            "Imperial Privilege recall",
            _find(t.space, "RecallAgentAbility"),
            (*recall, *((conflict,) if conflict is not None else ())),
            _recall_request(t, recall, conflict),
            _recall_answer(recall, conflict),
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


# -- Bloodlines and Arrakeen Scouts on the space ---------------------------------------


def _tuek_sietch(t: _Turn) -> None:
    """Tuek's Sietch: ``TueksSietchDeferredAbility`` (Explicit; bloodlines-
    systems.md §6, D37): option 0 -> ``take_tuek_sietch_spice``, 1 ->
    ``take_tuek_sietch_card`` (the bonus spice rides on either)."""

    spice = t.run.first("take_tuek_sietch_spice")
    card = t.run.first("take_tuek_sietch_card")
    uses = tuple(a for a in (spice, card) if a is not None)
    if not uses:
        return

    def answer(ans: Answer) -> DomainAction | None:
        return card if _response_ref(ans) == 1 else spice

    _choice_source(
        t,
        "Tuek's Sietch",
        _find(t.space, "TueksSietchDeferredAbility"),
        uses,
        Request(),
        answer,
        None,
    )


def _commander_acquire(t: _Turn) -> None:
    """The space's Sardaukar Commander: ``AcquireCommanderAbility``
    (Explicit; bloodlines-systems.md §2.2-2.3, D3) over the offered Skills in
    face-up order: ``((skill,),)`` -> ``acquire_sardaukar_commander(skill)``,
    ``((),)`` -> the Commander without a Skill, the empty answer at 0.5 ->
    ``decline_sardaukar_commander``. With no purchase offered (the cost
    cannot be paid, the Commander is gone) the app has no key: the refusal
    is a chore."""

    acquire = t.by_id("acquire_sardaukar_commander")
    decline = t.run.first("decline_sardaukar_commander")
    if not acquire:
        if decline is not None:
            t.chores.append(decline)
        return
    found = _find(t.space, "AcquireCommanderAbility")
    if found is None:
        t.unmapped.append("Sardaukar Commander")
        return
    ability = found[0]
    p = t.p
    skills = tuple(skill_entity(ref) for ref in _arg_refs(acquire, "skill_id"))
    request = Request(infos=(TargetInfo(entities=skills),))
    plain = next((a for a in acquire if str_arg(a, "skill_id") is None), None)

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None:
            return ans.value, None
        if not ans.response:
            return ans.value, decline  # the empty answer: no Commander
        ref = _response_ref(ans)
        if ref is None:
            return ans.value, plain
        return ans.value, with_arg(acquire, "skill_id", skill_id_of(str(ref)))

    uses = (*acquire, *((decline,) if decline is not None else ()))
    _prompt(t, "Sardaukar Commander", uses, evaluate, explicit=_explicit(ability, p))


def _recruit_commander(t: _Turn) -> None:
    """``recruit_sardaukar_commander``: the playmat's ``RecruitCommanderAbility``
    (Optional; bloodlines-systems.md §2.2, D5): its net when > 0, 100 while
    the deployment can still take it; an unused key needs no decline."""

    action = t.run.first("recruit_sardaukar_commander")
    if action is None:
        return
    ability = ability_for(_RECRUIT_COMMANDER, commander_entity())
    _ability_source(t, "Recruit Commander", (ability, 0), _ROW_PLAYMAT, action)


def _tech_acquire(t: _Turn) -> None:
    """The Landsraad visit's Acquire Tech (bloodlines-systems.md §3.1, §3.4):
    the space's ``AcquireTechAbility`` (Explicit; TechDiscount 0) over the
    offered tiles (stack order, then the own Secret Project): ``((tile,),)``
    -> ``acquire_tech(tile)``, the empty answer at 0.5 -> ``decline_tech``.
    Advanced Data Analysis boxes the Spy on the worst post
    (``RecallSpyEvaluator``, D14). Nothing affordable: no app key (its
    ``Cost`` fails), the refusal is a chore."""

    acquire = t.by_id("acquire_tech")
    decline = t.run.first("decline_tech")
    if not acquire:
        if decline is not None:
            t.chores.append(decline)
        return
    found = _find(t.space, "AcquireTechAbility")
    if found is None:
        t.unmapped.append("Acquire Tech")
        return
    ability = found[0]
    p = t.p
    run = t.run
    tech_ids = list(dict.fromkeys(_arg_refs(acquire, "tech_id")))
    request = Request(infos=(TargetInfo(entities=tuple(map(tech_entity, tech_ids))),))

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None:
            return ans.value, None
        ref = _response_ref(ans)
        if ref is None:
            return ans.value, decline  # the empty answer: no tile
        variants = [a for a in acquire if str_arg(a, "tech_id") == ref]
        if len(variants) > 1:  # Advanced Data Analysis: one per own Spy
            return ans.value, worst_recall_action(run, variants)
        return ans.value, (variants[0] if variants else None)

    uses = (*acquire, *((decline,) if decline is not None else ()))
    _prompt(t, "Acquire Tech", uses, evaluate, explicit=_explicit(ability, p))


def _tech_acquire_effects(t: _Turn) -> None:
    """``resolve_tech_acquire_effect``: the bought tile's owed icons resolved
    at once in the engine's key order (bloodlines-systems.md §3.1, D15), as
    follow-ups before anything else. The first owed key's variants are the
    choice: ``influence`` by ``MemocordersAcquiredAbility`` E (FACTIONS
    order), ``intrigue_or_card`` by ``GeneLockedVaultAcquiredAbility`` E,
    ``shield_wall`` destroyed iff ``ShouldBlowWall`` (D20)."""

    actions = t.by_id("resolve_tech_acquire_effect")
    if not actions:
        return
    first = actions[0]
    tech_id = str_arg(first, "tech_id")
    effect = str_arg(first, "effect")
    # A key owed twice (Ornithopter Fleet's two troops) is offered twice.
    variants = list(
        dict.fromkeys(
            a
            for a in actions
            if str_arg(a, "tech_id") == tech_id and str_arg(a, "effect") == effect
        )
    )
    label = f"tech {tech_id} {effect}"
    p = t.p
    chosen: DomainAction | None = None
    if len(variants) == 1:
        chosen = variants[0]
    elif tech_id is not None and effect == "influence":
        found = _find(tech_entity(tech_id), "MemocordersAcquiredAbility")
        if found is not None:
            offered = set(_arg_refs(variants, "faction"))
            tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
            ans = found[0].evaluate(p, Request(infos=(TargetInfo(entities=tracks),)))
            chosen = with_arg(variants, "faction", _response_ref(ans))
    elif tech_id is not None and effect == "intrigue_or_card":
        found = _find(tech_entity(tech_id), "GeneLockedVaultAcquiredAbility")
        if found is not None:
            ans = found[0].evaluate(p, Request())
            option = _response_ref(ans)
            pick = "intrigue" if option == 0 else "card" if option == 1 else None
            chosen = with_arg(variants, "choice", pick) if pick else None
    elif effect == "shield_wall":
        destroy = next(
            (a for a in variants if arg(a, "destroy_shield_wall") is True), None
        )
        plain = next((a for a in variants if a is not destroy), None)
        chosen = destroy if destroy is not None and p.should_blow_wall() else plain
    if chosen is None:
        t.unmapped.append(label)
        return
    _automatic(t, label, _FOLLOW_UP, chosen, -3)


def _flips(t: _Turn) -> None:
    """``flip_tech(tile)``: the tile's Flip activation (Optional; bloodlines-
    systems.md §3.3, D23-D25), a post-action key at its ``Evaluate``."""

    for action in t.by_id("flip_tech"):
        tech_id = str_arg(action, "tech_id") or ""
        name = _FLIP_ABILITY.get(tech_id)
        found = _find(tech_entity(tech_id), name) if name is not None else None
        _ability_source(t, f"flip {tech_id}", found, _ROW_PLAYMAT, action)


def _mission_collect(t: _Turn) -> None:
    """``scouts_collect_mission(choice)``: the visit's mission pieces
    (``MissionPiecesSpaceAbility``; scouts.md §3.5, D26), automatic with the
    space's own gains (state 400) at its icon's place. With Imperial
    Reserve's two goods its E picks (spice on ties)."""

    actions = t.by_id("scouts_collect_mission")
    if not actions:
        return
    icons = str(t.context.get("board_icons", "")).split(",")
    order = icons.index("scouts_mission") if "scouts_mission" in icons else len(icons)
    chosen: DomainAction | None = actions[0] if len(actions) == 1 else None
    if chosen is None:
        found = _find(t.space, "MissionPiecesSpaceAbility")
        if found is not None:
            ans = found[0].evaluate(t.p, Request())
            chosen = with_arg(actions, "choice", _response_ref(ans))
    if chosen is None:
        t.unmapped.append("Scouts mission pieces")
        return
    _automatic(t, "Scouts mission pieces", Stage.SPACE, chosen, order)


def _subcommittee(t: _Turn) -> None:
    """The new High Council seat's subcommittee (scouts.md §3.3, D23):
    ``SubcommitteeOfferAbility`` (Optional) realised by
    ``choose_subcommittee``; the picked id is kept for the
    ``scouts_subcommittee`` window (``(SUBCOMMITTEE_INTENT, round, seat)``).
    ``decline_subcommittee`` is the unused key."""

    choose = t.run.first("choose_subcommittee")
    decline = t.run.first("decline_subcommittee")
    if choose is None and decline is None:
        return
    if decline is not None:
        t.declines.append(decline)
    if choose is None:
        return
    found = _find(t.space, "SubcommitteeOfferAbility")
    if found is None:
        t.unmapped.append("Subcommittee")
        return
    ability = found[0]
    p = t.p
    key = (SUBCOMMITTEE_INTENT, t.run.ctx.round_number, t.seat)

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, Request())
        ref = _response_ref(ans)
        if ans.response is None or ref is None:
            return ans.value, None
        t.on_choose[choose] = [(key, ref)]
        return ans.value, choose

    _prompt(t, "Subcommittee", (choose,), evaluate, explicit=_explicit(ability, p))


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
        _box_auto(t, f"{short} box", action)
        return
    if short == "signet_ring":
        leader_id = t.run.ctx.me.leader_id or ""
        name = _SIGNET_BOX_ABILITY.get(leader_id)
        found = _find(t.leader, name) if name is not None else None
        _ability_source(t, f"signet {leader_id}", found, _ROW_LEADER, action)
        return
    if short in _EXPANSION_BOX_CARDS:
        _expansion_box(t, short, action)
        return
    if short in _BLOODLINES_BOX_CARDS:
        _bloodlines_box(t, short, action)
        return
    name = _BOX_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        # A box with no app mapping: no guess (the window falls back).
        t.unmapped.append(f"{short} box")
        return
    request = (
        _contract_request(t) if isinstance(found[0], GainContractAbility) else None
    )
    _ability_source(t, f"{short} box", found, _ROW_CARD, action, request)


def _expansion_box(t: _Turn, short: str, action: DomainAction) -> None:
    """``resolve_agent_card_effect()`` of an Immortality, Epic or promo card.

    Where one of our actions does two app steps it takes the stage of the one
    that asks (module docstring); each case names its app abilities.
    """

    label = f"{short} box"
    handled_by = _BOX_HANDLED_BY_CHOICE.get(short)
    if handled_by is not None and t.run.first(handled_by) is not None:
        return  # one option of the card's combined choice (_card_payment)
    if short in (
        "experimentation",
        "bene_tleilax_researcher",
        "scientific_breakthrough",
    ):
        # ``GainResearchAgentAbility`` (Explicit, never auto): its E over the
        # next research spaces; the direction is ``research_advance``'s.
        found = _find(t.card, "GainResearchAgentAbility")
        _gated_ability_source(t, label, found, _ROW_CARD, action, _research_request(t))
    elif short in _FIRST_BOX_CARDS:
        _box_auto(t, label, action)  # SpecimenAgentAbility (state 210)
    elif short == "clandestine_meeting":
        _clandestine_meeting(t, label, action)
    elif short == "stillsuit_manufacturer":
        # The ``AgentWater`` box (500) and ``StillsuitManufacturerAgentAbility``
        # (Explicit, E 100) when its Cost (Fremen alliance, card in play) holds.
        found = _find(t.card, "StillsuitManufacturerAgentAbility")
        if found is not None and isinstance(found[0], DeferredAbility):
            if found[0].meets_cost(t.p):
                _ability_source(t, label, found, _ROW_CARD, action)
                return
        _box_auto(t, label, action)
    elif short == "throne_room_politics":
        # The ``AgentTroops`` box (500) and ``TrashAgentAbility`` (Explicit;
        # our engine opens its trash as ``optional_trash`` right after).
        found = _find(t.card, "TrashAgentAbility")
        _gated_ability_source(t, label, found, _ROW_CARD, action, _trash_request(t))
    elif short == "industrial_espionage":
        # Grafted: ``SpecimenGraftedAgentAbility`` (210),
        # ``IndustrialEspionageResearchAbility`` (Explicit, never auto) and
        # ``DrawAbility``; the research asks. Alone: the draw only.
        if t.partner_ref is not None:
            found = _find(t.card, "IndustrialEspionageResearchAbility")
            _gated_ability_source(
                t, label, found, _ROW_CARD, action, _research_request(t)
            )
        else:
            _gated_ability_source(
                t, label, _first_of(t.card, DrawAbility), _ROW_CARD, action
            )
    elif short == "the_beast_s_spoils":
        # ``TheBeastsSpoilsDesertMouseAbility`` / ``…OrnithopterAbility``
        # (always immediate, Cost = the exact face-up battle icon); the
        # earlier of those that can run. With neither our resolution only
        # arms the Crysknife trash (``TheBeastsSpoilsCrysknifeAbility``, a
        # key of its own): the generic box.
        runnable = [
            found
            for found in (
                _find(t.card, "TheBeastsSpoilsDesertMouseAbility"),
                _find(t.card, "TheBeastsSpoilsOrnithopterAbility"),
            )
            if found is not None
            and isinstance(found[0], DeferredAbility)
            and found[0].meets_cost(t.p)
        ]
        if runnable:
            first = min(
                runnable,
                key=lambda found: _immediate_order(t, found[0], _ROW_CARD, found[1]),
            )
            _ability_source(t, label, first, _ROW_CARD, action)
        else:
            _box_auto(t, label, action)
    elif short in _EXPANSION_GENERIC_BOX_CARDS:
        _box_auto(t, label, action)
    else:
        name = _EXPANSION_BOX_ABILITY[short]
        _gated_ability_source(t, label, _find(t.card, name), _ROW_CARD, action)


def _clandestine_meeting(t: _Turn, label: str, action: DomainAction) -> None:
    """``AgentGainIntrigueAbility`` (always immediate) and the card's
    ``GainInfluenceAbility`` (immediate unless the deferral threshold is
    reached): one action of ours. Both immediate: the earlier in the 600
    order; otherwise the influence asks (Explicit, at its ``DeferValue``)."""

    intrigue = _find(t.card, "AgentGainIntrigueAbility")
    influence = _first_of(t.card, GainInfluenceAbility)
    if intrigue is None or influence is None:
        t.unmapped.append(label)
        return
    p = t.p
    if not _immediate(influence[0], p):
        _ability_source(t, label, influence, _ROW_CARD, action)
        return
    first = min(
        (intrigue, influence),
        key=lambda found: _immediate_order(t, found[0], _ROW_CARD, found[1]),
    )
    _ability_source(t, label, first, _ROW_CARD, action)


#: Every Bloodlines single box ``_bloodlines_box`` answers.
_BLOODLINES_BOX_CARDS = frozenset(
    {*_BLOODLINES_BOX_ABILITY, *_BLOODLINES_GENERIC_BOX_CARDS, *_BOND_CHOICE_CARDS}
)


def _bloodlines_box(t: _Turn, short: str, action: DomainAction) -> None:
    """``resolve_agent_card_effect()`` of a Bloodlines card (bloodlines-cards.md
    §3, §8): its own ability gated by its ``Cost`` (Holy War, Urgent
    Shigawire, Command Center, Fremen-spice and contract riders), the Agent
    Intrigue (``AgentGainIntrigueAbility``, always immediate), or the generic
    box (Ixian Ambassador's spice, Quash Rebellion's Solari). A Bond choice's
    plain resolution is one option of ``_bond_choice`` when its influence
    pick is offered."""

    label = f"{short} box"
    if short in _BOND_CHOICE_CARDS and t.by_id("choose_agent_card_influence"):
        return  # one option of the card's influence choice (_bond_choice)
    if short in _BLOODLINES_GENERIC_BOX_CARDS:
        _box_auto(t, label, action)
        return
    if short == "possible_futures":
        # Without an influence pick the box is the two troops alone (option
        # 1 of ``PossibleFuturesAgentAbility``); our engine always offers the
        # pick with it, so this is never reached in play: no guess.
        t.unmapped.append(label)
        return
    found = _find(t.card, _BLOODLINES_BOX_ABILITY[short])
    request = (
        _contract_request(t)
        if found is not None and isinstance(found[0], GainContractAbility)
        else None
    )
    _gated_ability_source(t, label, found, _ROW_CARD, action, request)


def _box_icon(t: _Turn, action: DomainAction, effect: str) -> None:
    short = t.card_short or ""
    label = f"{short} {effect}"
    if effect == "trash_self":
        t.chores.append(action)  # TrashSelfAbility: Implicit, after End Turn
        return
    if short in _ARMED_REWARD_CARDS or short in _FOLLOW_UP_ICON_CARDS:
        _automatic(t, label, _FOLLOW_UP, action, -1)
        return
    name = _ICON_ABILITY.get((short, effect))
    found = _find(t.card, name) if name is not None else None
    if found is None:
        t.unmapped.append(label)
        return
    if short in _GATED_ICON_CARDS:
        _gated_ability_source(t, label, found, _ROW_CARD, action)
        return
    _ability_source(t, label, found, _ROW_CARD, action)


def _card_choices(t: _Turn) -> None:
    short = t.card_short or ""
    _card_trash(t, short)
    _card_discard(t, short)
    _card_payment(t, short)
    _corrinth_city(t)
    _card_intrigue_payment(t, short)
    _card_recall(t, short)
    _card_spy(t, short)
    _card_influence(t, short)
    if t.by_id("acquire_imperium_by_card", "acquire_reserve_by_card") or (
        short == "tleilaxu_master"
    ):
        _tleilaxu_master(t)
    else:
        _price_is_no_object(t)
    _choam_demands(t)
    _disruption_tactics(t)


def _card_trash(t: _Turn, short: str) -> None:
    trash = t.by_id("trash_agent_card")
    decline = t.run.first("decline_agent_card_trash")
    if not trash and decline is None:
        return
    if short == "pivotal_gambit":
        _pivotal_gambit(t, trash, decline)
        return
    name = _TRASH_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        t.unmapped.append(f"{short} trash")
        return
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


def _pivotal_gambit(
    t: _Turn, trash: Sequence[DomainAction], decline: DomainAction | None
) -> None:
    """``PivotalGambitAbility`` (Optional, E 100, no targets): "use" trashes
    the card itself (our only trash target), then its troop and pledge icons
    follow (``_FOLLOW_UP_ICON_CARDS``). With Economic Supremacy the app
    silently loses the pledge (``pivotal_gambit_reward_ability``); our engine
    still records it, a later ``combat_reward_influence`` question."""

    use = trash[0] if trash else None
    _choice_source(
        t,
        "pivotal_gambit trash",
        _find(t.card, "PivotalGambitAbility"),
        tuple(trash),
        Request(),
        lambda _a: use,
        decline,
    )


def _card_discard(t: _Turn, short: str) -> None:
    discard = t.by_id("discard_agent_card")
    decline = t.run.first("decline_agent_card_discard")
    if not discard and decline is None:
        return
    name = _DISCARD_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        t.unmapped.append(f"{short} discard")
        return
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
    if not t.by_id(*_PAYMENT_IDS):
        return
    handler = _PAYMENT_HANDLERS.get(short)
    if handler is not None:
        handler(t)
        return
    pay = t.by_id("pay_agent_card_water", "pay_agent_card_spice")
    decline = t.run.first("decline_agent_card_payment")
    name = _PAYMENT_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        t.unmapped.append(f"{short} payment")
        return
    use = pay[0] if pay else None
    _choice_source(
        t, f"{short} payment", found, pay, Request(), lambda _a: use, decline
    )


# -- Immortality, Epic and promo card choices (payment-family actions) ----------------


def _optional_payment(t: _Turn, name: str, pay_id: str) -> None:
    """An Optional rider realised by one pay action: "use" pays, an unused
    key is ``decline_agent_card_payment``. A failing ``Cost`` means the app
    has no key (Tleilaxu Surgeon past Tleilaxu rank 7, …): only the decline."""

    pay = t.run.first(pay_id)
    decline = t.run.first("decline_agent_card_payment")
    found = _find(t.card, name)
    if found is None:
        t.unmapped.append(f"{t.card_short} {name}")
        return
    ability = found[0]
    uses: tuple[DomainAction, ...] = ()
    if pay is not None and not (
        isinstance(ability, DeferredAbility) and not ability.meets_cost(t.p)
    ):
        uses = (pay,)
    _choice_source(t, name, found, uses, Request(), lambda _a: pay, decline)


def _organ_merchants(t: _Turn) -> None:
    """``OrganMerchantsAbility`` (Optional): a specimen for 4 Solari."""

    _optional_payment(t, "OrganMerchantsAbility", "pay_agent_card_specimen")


def _tleilaxu_surgeon(t: _Turn) -> None:
    """``TleilaxuSurgeonAgentAbility`` (Optional; ``Cost`` two specimens and
    ``CanGainTleilaxu``): never pays to advance past rank 7."""

    _optional_payment(t, "TleilaxuSurgeonAgentAbility", "pay_agent_card_two_specimens")


def _dissecting_kit(t: _Turn) -> None:
    """``DissectingKitAgentAbility`` (Optional, E 100): trash the partner."""

    _optional_payment(t, "DissectingKitAgentAbility", "trash_grafted_card_for_specimen")


def _scientific_breakthrough(t: _Turn) -> None:
    """``ScientificBreakthroughAbility`` (Optional, E 100, ``Cost`` two
    markers): trash the card for 1 VP. Its ``GainResearchAgentAbility`` is a
    separate key: before the research our engine offers it as the plain
    resolution (``_expansion_box``) and the trash keeps the research owed;
    after it the unused key is ``decline_agent_card_payment``."""

    _optional_payment(
        t, "ScientificBreakthroughAbility", "trash_agent_card_self_for_vp"
    )


def _control_the_spice(t: _Turn) -> None:
    """``ControlTheSpiceAbility`` (Optional; spec epic §2.3).

    E on ``target_request`` (``FindTrashTargets``): with a card worth
    trashing the sum names it and the app pays; our engine then asks the
    trash as ``optional_trash``, so the card is stored for that window as
    ``(CONTROL_THE_SPICE_TRASH_INTENT, round, card) -> ref`` when the payment
    is chosen. Without one nothing is stored: the unused key is the decline.
    """

    pay = t.run.first("pay_agent_card_spice")
    decline = t.run.first("decline_agent_card_payment")
    found = _find(t.card, "ControlTheSpiceAbility")
    if found is None or not isinstance(found[0], ControlTheSpiceAbility):
        t.unmapped.append("control_the_spice payment")
        return
    ability = found[0]
    if decline is not None:
        t.declines.append(decline)
    if pay is None or not ability.meets_cost(t.p):
        return
    p = t.p
    key = (CONTROL_THE_SPICE_TRASH_INTENT, t.run.ctx.round_number, t.card_ref)

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, ability.target_request(p))
        if ans.response is None:
            return ans.value, None
        t.on_choose[pay] = [(key, ControlTheSpiceAbility.trash_target(ans))]
        return ans.value, pay

    _prompt(t, "Control the Spice", (pay,), evaluate, explicit=False)


def _arrakis_revolt(t: _Turn) -> None:
    """``ArrakisRevoltAbility`` (Optional; imperium-a §2.1, epic §4.3).

    E (``Spice(-2) + BlowWallValue + SandWorm(1)``) values the key; the
    ``BlowWall`` prompt after ``PaySpice(2)`` is ``ShouldBlowWall`` on the
    paid state (``should_blow_wall_after_payment``): the wall variant when it
    stands and the app blows it, else the sandworm variant. Judgement
    (OQ-026): when the app would pay and keep the wall but our engine offers
    no sandworm line (the worm could do nothing), no action realises the
    answer, so the key is not taken (the decline).
    """

    wall = t.run.first("pay_agent_card_spice_for_sandworm_and_shield_wall")
    worm = t.run.first("pay_agent_card_spice_for_sandworm")
    decline = t.run.first("decline_agent_card_payment")
    found = _find(t.card, "ArrakisRevoltAbility")
    if found is None or not isinstance(found[0], ArrakisRevoltAbility):
        t.unmapped.append("arrakis_revolt payment")
        return
    ability = found[0]
    if decline is not None:
        t.declines.append(decline)
    if (wall is None and worm is None) or not ability.meets_cost(t.p):
        return
    p = t.p

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, Request())
        if ans.response is None:
            return ans.value, None
        if wall is not None and ability.should_blow_wall_after_payment(p):
            return ans.value, wall
        return ans.value, worm

    uses = tuple(a for a in (wall, worm) if a is not None)
    _prompt(t, "Arrakis Revolt", uses, evaluate, explicit=False)


def _high_priority_travel(t: _Turn) -> None:
    """``HighPriorityTravelAbility`` (Explicit; spec immortality.md §5.6):
    option 0 draws (our plain resolution), option 1 takes the Combat icon
    (``HighPriorityTravelDeployUnitsCustomAbility`` then deploys)."""

    take = t.run.first("take_agent_card_combat_icon")
    draw = next(
        (
            action
            for action in t.by_id("resolve_agent_card_effect")
            if str_arg(action, "effect") is None
        ),
        None,
    )
    uses = tuple(a for a in (draw, take) if a is not None)

    def answer(ans: Answer) -> DomainAction | None:
        return take if _response_ref(ans) == 1 else draw

    _choice_source(
        t,
        "High Priority Travel",
        _find(t.card, "HighPriorityTravelAbility"),
        uses,
        Request(infos=(TargetInfo(options=(0, 1)),)),
        answer,
        None,
    )


def _slig_farmer(t: _Turn) -> None:
    """``SligFarmerSolariAbility`` (Explicit; immediate unless grafted to Show
    of Strength) and ``SligFarmerTleilaxuAbility`` (Optional; ``Cost`` 5
    Solari and ``CanGainTleilaxu``).

    Our engine settles both in one action (the per-icon Solari, then maybe
    the 5 Solari for Tleilaxu). The Tleilaxu key is answered on the state
    after the Solari (its E prices ``GetSolariValue(-5)`` on that state):
    pay when its Cost holds there and E > 0. The action takes the Solari
    ability's stage (judgement: the app would pay at its prompt, after
    600; the answer is known at 600).
    """

    pay = t.run.first("pay_agent_card_five_solari_for_tleilaxu")
    solari = next(
        (
            action
            for action in t.by_id("resolve_agent_card_effect")
            if str_arg(action, "effect") is None
        ),
        None,
    )
    solari_found = _find(t.card, "SligFarmerSolariAbility")
    tleilaxu_found = _find(t.card, "SligFarmerTleilaxuAbility")
    if solari_found is None or tleilaxu_found is None:
        t.unmapped.append("slig_farmer payment")
        return
    if pay is None:
        if solari is not None:
            _ability_source(t, "slig_farmer box", solari_found, _ROW_CARD, solari)
        return
    after = _profile_after_solari(t, _partner_icon_count(t))
    tleilaxu = tleilaxu_found[0]
    pays = (
        isinstance(tleilaxu, DeferredAbility)
        and tleilaxu.meets_cost(after)
        and tleilaxu.evaluate(after, Request()).value > 0
    )
    chosen = pay if pays or solari is None else solari
    _ability_source(t, "slig_farmer box", solari_found, _ROW_CARD, chosen)


def _partner_icon_count(t: _Turn) -> int:
    """Slig Farmer's Solari: the other grafted card's Agent icons
    (``partner.IconList.Count``, ``SligFarmerSolariAbility`` V)."""

    if t.partner_ref is None:
        return 0
    try:
        partner = card_entity(t.partner_ref, t.seat)
    except KeyError:
        return 0
    return len(partner.list_attr("IconList"))


def _profile_after_solari(t: _Turn, solari: int) -> Profile:
    """A fresh profile on the state with ``solari`` more Solari (a new
    ``MakeChoice`` after the Solari step)."""

    ctx = t.run.ctx
    me = ctx.me
    gained = replace(
        me, resources=replace(me.resources, solari=me.resources.solari + solari)
    )
    players = tuple(
        gained if player.player_id == me.player_id else player for player in ctx.players
    )
    state = replace(ctx.state, players=players)
    return Profile(AppContext(state, ctx.seat, ctx.view), t.p.C, t.run.rng)


def _beguiling_pheromones(t: _Turn) -> None:
    """``BeguilingPheromonesAbility`` (Explicit): which grafted card to trash
    (itself 1.0, the partner by ``GetCardToTrash`` or the 6.0/1.0 table)."""

    actions = t.by_id("trash_grafted_card_for_influence")
    if not actions:
        return
    refs = _arg_refs(actions, "card_id")
    _choice_source(
        t,
        "Beguiling Pheromones",
        _find(t.card, "BeguilingPheromonesAbility"),
        actions,
        Request(infos=(TargetInfo(entities=_cards(t, refs)),)),
        _ref_or(actions, "card_id", None),
        None,
    )


def _piter(t: _Turn) -> None:
    """``PiterGeniusAdvisorAbility`` (Optional): lose a troop for two cards
    and Research.

    Targets: one zone code per troop, garrison first (``0`` garrison, ``1``
    Conflict; ``GetTroopTargets``). With exactly two targets the app answers
    both (a quirk): the first names our zone (the nearest legal action).
    """

    lose = t.by_id("lose_agent_card_troop")
    decline = t.run.first("decline_agent_card_payment")
    found = _find(t.card, "PiterGeniusAdvisorAbility")
    if found is None:
        t.unmapped.append("piter_genius_advisor payment")
        return
    me = t.run.ctx.me
    zones = set(_arg_refs(lose, "zone"))
    options = (
        *((0,) * me.troops_garrison if "garrison" in zones else ()),
        *((1,) * me.troops_conflict if "conflict" in zones else ()),
    )
    request = Request(infos=(TargetInfo(options=options),))

    def answer(ans: Answer) -> DomainAction | None:
        code = _response_ref(ans)
        if code is None:
            return None
        return with_arg(lose, "zone", "garrison" if code == 0 else "conflict")

    _choice_source(t, "Piter", found, lose, request, answer, decline)


def _stitched_horror_key(t: _Turn) -> tuple[object, ...]:
    return ("agent_effects", "stitched_horror", t.run.ctx.round_number, t.card_ref)


def _stitched_horror(t: _Turn) -> None:
    """``StitchedHorrorAbility`` (Explicit; spec immortality.md §6.11).

    One app answer names two rewards (options ``0`` water, ``1`` troop, ``2``
    trash, ``3`` Tleilaxu, the order of ``STITCHED_HORROR_REWARDS``) and, with
    the trash, the card. Ours picks one reward at a time: the first now, the
    second as a follow-up (``Memory.intents``); the trash card is stored for
    the ``optional_trash`` window (``STITCHED_HORROR_TRASH_INTENT``).
    """

    picks = t.by_id("choose_agent_card_reward")
    if not picks:
        return
    found = _find(t.card, "StitchedHorrorAbility")
    if found is None:
        t.unmapped.append("stitched_horror reward")
        return
    memory = t.run.memory.intents
    key = _stitched_horror_key(t)
    offered = _arg_refs(picks, "reward")
    second = len(offered) < len(STITCHED_HORROR_REWARDS)
    if second:
        # The second pick: the rest of the app answer already given.
        intent = memory.pop(key, None)
        chosen = with_arg(picks, "reward", intent) if isinstance(intent, str) else None
        if chosen is not None:
            _automatic(t, "Stitched Horror second reward", _FOLLOW_UP, chosen, -1)
            return
    p = t.p
    request = Request(
        infos=(
            TargetInfo(options=tuple(range(len(STITCHED_HORROR_REWARDS)))),
            TargetInfo(entities=find_trash_targets(p)),
        )
    )
    ability = found[0]
    trash_key = (STITCHED_HORROR_TRASH_INTENT, t.run.ctx.round_number, t.card_ref)

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None or not ans.response:
            return ans.value, None
        ids = [
            STITCHED_HORROR_REWARDS[i] for i in ans.response[0] if isinstance(i, int)
        ]
        legal = [reward for reward in ids if reward in offered]
        if not legal:
            return ans.value, None
        action = with_arg(picks, "reward", legal[0])
        if action is None:
            return ans.value, None
        entries: list[tuple[tuple[object, ...], object]] = []
        if len(legal) > 1 and not second:
            entries.append((key, legal[1]))
        if "trash" in legal and len(ans.response) > 1 and ans.response[1]:
            entries.append((trash_key, ans.response[1][0]))
        t.on_choose[action] = entries
        return ans.value, action

    _prompt(t, "Stitched Horror", picks, evaluate, explicit=True)


#: Card -> its payment-family handler (``_card_payment``).
_PAYMENT_HANDLERS: Mapping[str, Callable[[_Turn], None]] = {
    "organ_merchants": _organ_merchants,
    "tleilaxu_surgeon": _tleilaxu_surgeon,
    "dissecting_kit": _dissecting_kit,
    "scientific_breakthrough": _scientific_breakthrough,
    "control_the_spice": _control_the_spice,
    "arrakis_revolt": _arrakis_revolt,
    "high_priority_travel": _high_priority_travel,
    "slig_farmer": _slig_farmer,
    "beguiling_pheromones": _beguiling_pheromones,
    "piter_genius_advisor": _piter,
    "stitched_horror": _stitched_horror,
}


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
        """The first discard now; the second is kept only if this key is
        the one chosen (``t.on_choose``), not on every evaluation."""

        if ans.response is None or not ans.response[0]:
            return None
        refs = ans.response[0]
        action = with_arg(select, "card_id", refs[0])
        if action is not None and len(refs) >= 2:
            t.on_choose[action] = [(key, (refs[0], refs[1]))]
        return action

    _choice_source(t, "Corrinth City", found, select, request, answer, decline)


def _card_intrigue_payment(t: _Turn, short: str) -> None:
    uses = t.by_id("trash_intrigue_for_agent_card", "pay_agent_card_intrigue_and_spice")
    decline = t.run.first("decline_agent_card_intrigue_payment")
    if not uses and decline is None:
        return
    name = _INTRIGUE_PAYMENT_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        t.unmapped.append(f"{short} intrigue payment")
        return
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


def _card_recall(t: _Turn, short: str) -> None:
    if short == "twisted_mentat":
        _twisted_mentat(t)
        return
    recall = t.by_id("recall_agent_for_agent_card")
    conflict = t.run.first("recall_conflict_agent_for_agent_card")
    if t.run.first("decline_agent_card_recall") is not None:
        t.unmapped.append(f"{short} recall")  # no app twin of an optional recall
        return
    if not recall and conflict is None:
        return
    found = _find(t.card, "RecallAgentAbility")
    if found is None:
        t.unmapped.append(f"{short} recall")
        return
    _choice_source(
        t,
        "Steersman recall",
        found,
        (*recall, *((conflict,) if conflict is not None else ())),
        _recall_request(t, recall, conflict),
        _recall_answer(recall, conflict),
        None,
    )


def _recall_request(
    t: _Turn, recall: Sequence[DomainAction], conflict: DomainAction | None
) -> Request:
    """``RecallAgentAbility`` targets: the board Agents in offered order,
    then Duncan's Into the Fray Agent (bloodlines-systems.md §8, D55: a
    candidate ``GetRecallAgent`` skips, reached only as the fallback)."""

    agents = [agent_entity(space, t.seat) for space in _arg_refs(recall, "space_id")]
    if conflict is not None:
        agents.append(agent_entity(_CONFLICT_AGENT, t.seat))
    return Request(infos=(TargetInfo(entities=tuple(agents)),))


def _recall_answer(
    recall: Sequence[DomainAction], conflict: DomainAction | None
) -> Callable[[Answer], DomainAction | None]:
    def answer(ans: Answer) -> DomainAction | None:
        ref = _response_ref(ans)
        if ref == _CONFLICT_AGENT:
            return conflict
        return with_arg(recall, "space_id", ref) if ref is not None else None

    return answer


def _twisted_mentat(t: _Turn) -> None:
    """``TwistedMentatAbility`` (Optional, E 100, no targets): recall the
    Agent sent this turn (from its space, or from the Conflict after Into the
    Fray, OQ-068); an unused key is ``decline_agent_card_recall``."""

    board = t.by_id("recall_agent_for_agent_card")
    conflict = t.run.first("recall_conflict_agent_for_agent_card")
    decline = t.run.first("decline_agent_card_recall")
    found = _find(t.card, "TwistedMentatAbility")
    if found is None:
        t.unmapped.append("twisted_mentat recall")
        return
    use = board[0] if board else conflict
    uses = (use,) if use is not None else ()
    _choice_source(
        t, "Twisted Mentat recall", found, uses, Request(), lambda _a: use, decline
    )


def _card_spy(t: _Turn, short: str) -> None:
    place = t.by_id("place_agent_card_spy")
    recall = t.by_id("recall_spy_for_agent_card")
    decline = t.run.first("decline_agent_card_spy")
    if not place and not recall and decline is None:
        return
    if short == "arrakis_observer":
        _arrakis_observer_spy(t, place, recall, decline)
        return
    name = _CARD_SPY_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        t.unmapped.append(f"{short} spy")
        return
    _spy_source(t, f"{short} spy", found, place, recall, decline, _CARD_SPY_RECALLED)


def _arrakis_observer_spy(
    t: _Turn,
    place: Sequence[DomainAction],
    recall: Sequence[DomainAction],
    decline: DomainAction | None,
) -> None:
    """Arrakis Observer's Spy with Deep Cover (bloodlines-cards.md §3.2): the
    rest of ``ArrakisObserverAgentAbility``'s discard answer, a follow-up.
    ``spy_answer`` never declines: the best offered post (``PostValue``
    ignores occupancy, §1.5 D50), or with an empty supply the recall-first
    of the worst-post Spy; the decline alone (nothing to place or recall)
    is a chore."""

    chosen = spy_answer(t.run, place, recall, None)
    if chosen is None:
        if decline is not None:
            t.chores.append(decline)
        return
    _automatic(t, "Arrakis Observer spy", _FOLLOW_UP, chosen, -1)


def _card_influence(t: _Turn, short: str) -> None:
    actions = t.by_id("choose_agent_card_influence")
    if not actions:
        return
    if short == "long_reach":
        _long_reach(t, actions)
        return
    if short in _BOND_CHOICE_CARDS:
        _bond_choice(t, short, actions)
        return
    name = _CARD_INFLUENCE_ABILITY.get(short)
    found = _find(t.card, name) if name is not None else None
    if found is None:
        t.unmapped.append(f"{short} influence")
        return
    _influence_choice(t, f"{short} influence", found, actions)


def _long_reach_key(t: _Turn) -> tuple[object, ...]:
    return ("agent_effects", "long_reach", t.run.ctx.round_number, t.card_ref)


def _long_reach(t: _Turn, actions: Sequence[DomainAction]) -> None:
    """``LongReachAgentAbility`` (Explicit; spec immortality.md §5.11): one
    answer names the two tracks; ours picks one at a time, the second as a
    follow-up (``Memory.intents``)."""

    memory = t.run.memory.intents
    key = _long_reach_key(t)
    offered = set(_arg_refs(actions, "faction"))
    second = len(offered) < len(FACTIONS)
    if second:
        intent = memory.pop(key, None)
        chosen = (
            with_arg(actions, "faction", intent) if isinstance(intent, str) else None
        )
        if chosen is not None:
            _automatic(t, "Long Reach second track", _FOLLOW_UP, chosen, -1)
            return
    found = _find(t.card, "LongReachAgentAbility")
    if found is None:
        t.unmapped.append("long_reach influence")
        return
    ability = found[0]
    p = t.p
    tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
    request = Request(infos=(TargetInfo(entities=tracks),))

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None or not ans.response or not ans.response[0]:
            return ans.value, None
        refs = [ref for ref in ans.response[0] if ref in offered]
        if not refs:
            return ans.value, None
        action = with_arg(actions, "faction", refs[0])
        if action is None:
            return ans.value, None
        if len(refs) > 1 and not second:
            t.on_choose[action] = [(key, refs[1])]
        return ans.value, action

    _prompt(t, "Long Reach", actions, evaluate, explicit=_explicit(ability, p))


# -- Bloodlines card choices (bloodlines-cards.md §3, §8) ------------------------------


def _bond_choice(t: _Turn, short: str, actions: Sequence[DomainAction]) -> None:
    """Southern Faith and Possible Futures (bloodlines-cards.md §3.21, §3.26;
    plan §11.5 Agent-box Bond, D15): one Explicit key whose ``Evaluate``
    picks the option.

    Our engine offers the box's plain resolution (Southern Faith's draw,
    Possible Futures' two troops) beside the influence picks; with Possible
    Futures' Bond the influence pick pays both. Answers: option 0 (Southern
    Faith: draw; Possible Futures: influence on the named track), option 1
    (Southern Faith: Bene Gesserit influence; Possible Futures: troops),
    option 2 (Possible Futures with the Bond: both, on the named track).
    """

    plain = next(
        (
            action
            for action in t.by_id("resolve_agent_card_effect")
            if str_arg(action, "effect") is None
        ),
        None,
    )
    offered = set(_arg_refs(actions, "faction"))
    tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
    request = Request(infos=(TargetInfo(entities=tracks),))

    def answer(ans: Answer) -> DomainAction | None:
        option = _response_ref(ans)
        if short == "southern_faith":
            if option == 1:
                return actions[0]  # the Bene Gesserit pick (the only one)
            return plain if option == 0 else None
        if option == 1:
            return plain
        if option in (0, 2):
            return with_arg(actions, "faction", _response_ref(ans, 1))
        return None

    uses = (*actions, *((plain,) if plain is not None else ()))
    _choice_source(
        t,
        f"{short} choice",
        _find(t.card, _BOND_CHOICE_CARDS[short]),
        uses,
        request,
        answer,
        None,
    )


def _choam_demands(t: _Turn) -> None:
    """``complete_contract_by_card``: ``CHOAMDemandsAgentAbility`` (Explicit,
    forced; bloodlines-cards.md §3.4) at each own active contract's
    ``GetResourceValue``, first strictly best."""

    actions = t.by_id("complete_contract_by_card")
    if not actions:
        return
    contracts = tuple(
        contract_entity(ref, t.seat) for ref in _arg_refs(actions, "instance_id")
    )
    _choice_source(
        t,
        "CHOAM Demands",
        _find(t.card, "CHOAMDemandsAgentAbility"),
        actions,
        Request(infos=(TargetInfo(entities=contracts),)),
        _ref_or(actions, "instance_id", None),
        None,
    )


def _disruption_tactics(t: _Turn) -> None:
    """``retreat_opponent_troop(player[, commanders])``:
    ``DisruptionTacticsAgentAbility`` (Explicit, forced; bloodlines-cards.md
    §3.8, D9) over the victim codes ``retreat_target_code(seat, commander)``
    of the offered units, in offered order."""

    actions = t.by_id("retreat_opponent_troop")
    if not actions:
        return
    by_code: dict[int, DomainAction] = {}
    for action in actions:
        seat = int_arg(action, "player")
        if seat is not None:
            commander = int_arg(action, "commanders") == 1
            by_code.setdefault(retreat_target_code(seat, commander), action)

    def answer(ans: Answer) -> DomainAction | None:
        code = _response_ref(ans)
        if not isinstance(code, int):
            return None
        seat, commander = retreat_target_of(code)
        return by_code.get(retreat_target_code(seat, commander))

    _choice_source(
        t,
        "Disruption Tactics",
        _find(t.card, "DisruptionTacticsAgentAbility"),
        actions,
        Request(infos=(TargetInfo(options=tuple(by_code)),)),
        answer,
        None,
    )


def _price_is_no_object(t: _Turn) -> None:
    row = t.by_id("acquire_imperium_with_solari")
    reserve = t.by_id("acquire_reserve_with_solari")
    decline = t.run.first("decline_agent_card_acquisition")
    if not row and not reserve and decline is None:
        return
    found = _find(t.card, "PriceIsNoObjectAbility")
    if found is None:
        t.unmapped.append(f"{t.card_short} acquisition")
        return
    _acquisition_choice(
        t,
        "Price Is No Object",
        found,
        row,
        reserve,
        decline,
        lambda: Request(
            infos=(TargetInfo(entities=_acquire_entities(t, row, reserve)),)
        ),
    )


def _acquire_entities(
    t: _Turn, row: Sequence[DomainAction], reserve: Sequence[DomainAction]
) -> tuple[Entity, ...]:
    """The offered cards, Row first (UNTRACED, imperium-b §Price Is No
    Object: whether the app's targets include the reserve; ours offers
    both). A Reserve The Spice Must Flow reads Market Opening's discounted
    cost while it holds (``Profile.market_opening_reserve_card``, scouts.md
    §4.7 D31, plan §11.8; unchanged outside Scouts' Market Opening)."""

    entities = [*_cards(t, _arg_refs(row, "instance_id"))]
    entities += [
        t.p.market_opening_reserve_card(card_entity(f"reserve:{c}"))
        for c in _arg_refs(reserve, "card_id")
    ]
    return tuple(entities)


def _acquisition_choice(
    t: _Turn,
    label: str,
    found: tuple[Ability, int],
    row: Sequence[DomainAction],
    reserve: Sequence[DomainAction],
    decline: DomainAction | None,
    request: Callable[[], Request],
) -> None:
    def answer(ans: Answer) -> DomainAction | None:
        ref = _response_ref(ans)
        if not isinstance(ref, str):
            return None
        if ref.startswith("reserve:"):
            return with_arg(reserve, "card_id", card_id(ref))
        return with_arg(row, "instance_id", ref)

    _choice_source(t, label, found, (*row, *reserve), request(), answer, decline)


def _tleilaxu_master(t: _Turn) -> None:
    """``TleilaxuMasterAbility`` (Optional; spec immortality.md §5.19): each
    offered card at its ``AcquireValue``, first strictly best; an unused key
    is ``decline_agent_card_acquisition``. Our engine sends the card to the
    hand with two markers by itself, so no destination picker is offered
    (``infos[1]`` absent: option 0)."""

    row = t.by_id("acquire_imperium_by_card")
    reserve = t.by_id("acquire_reserve_by_card")
    decline = t.run.first("decline_agent_card_acquisition")
    if not row and not reserve and decline is None:
        return
    found = _find(t.card, "TleilaxuMasterAbility")
    if found is None:
        t.unmapped.append("tleilaxu_master acquisition")
        return
    _acquisition_choice(
        t,
        "Tleilaxu Master",
        found,
        row,
        reserve,
        decline,
        lambda: Request(
            infos=(TargetInfo(entities=_acquire_entities(t, row, reserve)),)
        ),
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
    else:
        bloodlines = _BLOODLINES_SIGNETS.get(leader_id or "")
        if bloodlines is not None:
            bloodlines(t)
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


# -- Bloodlines leaders' Signet Rings (bloodlines-systems.md §4) ----------------------
#
# Each Signet is one key of the leader's ``SignetAbility`` port: its branches
# (the ``ClassVar`` option constants) in ``infos[0].options``, the branch's
# targets in ``infos[1]``; Optional signets take the unused key as
# ``decline_leader_signet_payment``, Explicit ones (Smuggle Spice, Reverse
# Engineering) force the prompt (D29).


def _branches(*offered: tuple[int, bool]) -> tuple[int, ...]:
    return tuple(option for option, present in offered if present)


def _fedaykin(t: _Turn) -> None:
    """Chani's Fedaykin Maneuver (§4.1, D30): ``retreat_leader_troops(count[,
    commanders])``, troops first (``retreat_split``, §1.4 D7), or
    ``pay_leader_signet_water``."""

    retreats = t.by_id("retreat_leader_troops")
    water = t.run.first("pay_leader_signet_water")
    decline = t.run.first("decline_leader_signet_payment")
    if not retreats and water is None and decline is None:
        return
    counts = tuple(
        sorted({n for n in (int_arg(a, "count") for a in retreats) if n is not None})
    )
    request = Request(
        infos=(
            TargetInfo(options=_branches((0, bool(retreats)), (1, water is not None))),
            TargetInfo(options=counts),
        )
    )
    p = t.p

    def answer(ans: Answer) -> DomainAction | None:
        if _response_ref(ans) == 1:
            return water
        count = _response_ref(ans, 1)
        if not isinstance(count, int):
            return None
        _troops, commanders = p.retreat_split(count)
        return next(
            (
                a
                for a in retreats
                if int_arg(a, "count") == count
                and (int_arg(a, "commanders") or 0) == commanders
            ),
            None,
        )

    uses = (*retreats, *((water,) if water is not None else ()))
    _choice_source(
        t,
        "Fedaykin Maneuver",
        _find(t.leader, "FedaykinManeuverSignetAbility"),
        uses,
        request,
        answer,
        decline,
    )


def _corrino_liaison(t: _Turn) -> None:
    """Count Hasimir Fenring's Corrino Liaison (§4.2, D31, D32):
    ``trash_leader_card(card)`` (a card in play) or the Spy with Deep Cover
    next to the Emperor (``spy_answer``; after a recall-first the placement
    is the rest of the answer)."""

    trash = t.by_id("trash_leader_card")
    place = t.by_id("place_leader_spy")
    recall = t.by_id("recall_spy_for_leader_placement")
    decline = t.run.first("decline_leader_signet_payment")
    run = t.run
    if place and t.flag(_LEADER_SPY_RECALLED):
        chosen = best_place_action(run, place)
        if chosen is not None:
            _automatic(t, "Corrino Liaison spy after recall", _FOLLOW_UP, chosen, -1)
            return
    if not trash and not place and not recall and decline is None:
        return
    cards = _cards(t, _arg_refs(trash, "card_id"))
    request = Request(
        infos=(
            TargetInfo(options=_branches((0, bool(trash)), (1, bool(place or recall)))),
            TargetInfo(entities=cards),
        )
    )

    def answer(ans: Answer) -> DomainAction | None:
        if _response_ref(ans) == 1:
            return spy_answer(run, place, recall, None)
        return with_arg(trash, "card_id", _response_ref(ans, 1))

    _choice_source(
        t,
        "Corrino Liaison",
        _find(t.leader, "CorrinoLiaisonSignetAbility"),
        (*trash, *place, *recall),
        request,
        answer,
        decline,
    )


def _into_the_fray(t: _Turn) -> None:
    """Duncan Idaho's Into the Fray (§4.3, D34): ``deploy_leader_agent`` at
    0.5 when ``GetUnitsToDeploy`` takes the Agent unit."""

    deploy = t.run.first("deploy_leader_agent")
    decline = t.run.first("decline_leader_signet_payment")
    if deploy is None and decline is None:
        return
    uses = (deploy,) if deploy is not None else ()
    _choice_source(
        t,
        "Into the Fray",
        _find(t.leader, "IntoTheFraySignetAbility"),
        uses,
        Request(),
        lambda _a: deploy,
        decline,
    )


def _smuggle_spice(t: _Turn) -> None:
    """Esmar Tuek's Smuggle Spice (§4.4, D36; Explicit): ``take_leader_bonus_
    spice(space)`` over the spaces holding bonus spice in board order, or
    ``place_leader_bonus_spice``. With neither possible only the refusal is
    offered: no app key, a chore."""

    place = t.run.first("place_leader_bonus_spice")
    takes = t.by_id("take_leader_bonus_spice")
    decline = t.run.first("decline_leader_signet_payment")
    if place is None and not takes:
        if decline is not None:
            t.chores.append(decline)
        return
    offered = _arg_refs(takes, "space_id")
    board = t.run.ctx.board
    order = [s for s in board_space_order(board) if s in offered]
    order += [s for s in offered if s not in order]
    request = Request(
        infos=(
            TargetInfo(options=_branches((0, place is not None), (1, bool(takes)))),
            TargetInfo(entities=tuple(space_entity(s, board) for s in order)),
        )
    )

    def answer(ans: Answer) -> DomainAction | None:
        if _response_ref(ans) == 1:
            return with_arg(takes, "space_id", _response_ref(ans, 1))
        return place

    _choice_source(
        t,
        "Smuggle Spice",
        _find(t.leader, "SmuggleSpiceSignetAbility"),
        (*((place,) if place is not None else ()), *takes),
        request,
        answer,
        None,
    )


def _listeners(t: _Turn) -> None:
    """Gaius Helen Mohiam's Listeners (§4.5, D32, D39): a Spy next to the
    Landsraad, or ``pay_leader_signet_spice`` for a Spy anywhere. The Spy
    after the payment (``listeners_paid``) or after a recall-first is the
    rest of the answer (a follow-up; ``spy_answer`` never declines)."""

    run = t.run
    place = t.by_id("place_leader_spy")
    recall = t.by_id("recall_spy_for_leader_placement")
    pay = run.first("pay_leader_signet_spice")
    decline = run.first("decline_leader_signet_payment")
    spy_decline = run.first("decline_leader_spy_placement")
    if t.flag("listeners_paid") or (place and t.flag(_LEADER_SPY_RECALLED)):
        chosen = spy_answer(run, place, recall, None)
        if chosen is not None:
            _automatic(t, "Listeners spy", _FOLLOW_UP, chosen, -1)
        elif spy_decline is not None:
            t.chores.append(spy_decline)
        return
    if not place and not recall and pay is None and decline is None:
        return
    request = Request(
        infos=(
            TargetInfo(
                options=_branches((0, bool(place or recall)), (1, pay is not None))
            ),
        )
    )

    def answer(ans: Answer) -> DomainAction | None:
        if _response_ref(ans) == 1:
            return pay
        return spy_answer(run, place, recall, None)

    _choice_source(
        t,
        "Listeners",
        _find(t.leader, "ListenersSignetAbility"),
        (*place, *recall, *((pay,) if pay is not None else ())),
        request,
        answer,
        decline,
    )


def _reverse_engineering(t: _Turn) -> None:
    """Kota Odax of Ix's Reverse Engineering (§4.9, D28; Explicit):
    ``gain_leader_signet_spice`` or ``trash_leader_tech(tech)``."""

    spice = t.run.first("gain_leader_signet_spice")
    trash = t.by_id("trash_leader_tech")
    if spice is None and not trash:
        return
    tiles = tuple(tech_entity(ref) for ref in _arg_refs(trash, "tech_id"))
    request = Request(
        infos=(
            TargetInfo(options=_branches((0, spice is not None), (1, bool(trash)))),
            TargetInfo(entities=tiles),
        )
    )

    def answer(ans: Answer) -> DomainAction | None:
        if _response_ref(ans) == 1:
            return with_arg(trash, "tech_id", _response_ref(ans, 1))
        return spice

    _choice_source(
        t,
        "Reverse Engineering",
        _find(t.leader, "ReverseEngineeringSignetAbility"),
        (*((spice,) if spice is not None else ()), *trash),
        request,
        answer,
        None,
    )


#: Bloodlines leader -> its Signet Ring choice (``_leader_choices``).
_BLOODLINES_SIGNETS: Mapping[str, Callable[[_Turn], None]] = {
    "chani": _fedaykin,
    "count_hasimir_fenring": _corrino_liaison,
    "duncan_idaho": _into_the_fray,
    "esmar_tuek": _smuggle_spice,
    "gaius_helen_mohiam": _listeners,
    "kota_odax_of_ix": _reverse_engineering,
}


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
            agents = [agent_entity(s, t.seat) for s in others]
            if _conflict_agent_recallable(t):
                # Duncan's earlier Into the Fray Agent, the last candidate of
                # the reward's recall (D55, ``recall_conflict_agent_for_
                # contract``).
                agents.append(agent_entity(_CONFLICT_AGENT, t.seat))
            request = Request(infos=(TargetInfo(entities=tuple(agents)),))
        _ability_source(t, f"contract {ref}", found, _ROW_CONTRACT, action, request)


def _conflict_agent_recallable(t: _Turn) -> bool:
    """Whether a Recall Agent reward of this turn may take an earlier turn's
    Into the Fray Agent (Bloodlines; ``rules/effects.py``
    ``recallable_conflict_agents`` with ``turn_agent_in_conflict``: this
    turn's Agent, moved to the Conflict, is excluded; OQ-068, D55)."""

    me = t.run.ctx.me
    if not t.run.ctx.bloodlines or me.agent_in_conflict < 1:
        return False
    sent_this_turn = (
        t.space_id is not None
        and t.space_id not in me.agent_locations
        and t.context.get("turn_agent_recalled") is not True
    )
    return me.agent_in_conflict - (1 if sent_this_turn else 0) > 0


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

    if t.run.ctx.bloodlines:
        _deploy_units(t)
        return
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
        found, garrison = _card_deploy_ability(t, maximum)
    if found is None:
        t.unmapped.append("deploy_troops off a Combat space")
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


def _card_deploy_ability(
    t: _Turn, maximum: int
) -> tuple[tuple[Ability, int] | None, int]:
    """The ``DeployUnits`` key of this turn's cards off a Combat space.

    The grafted partner's Sardaukar Coordination (as the active card's),
    then a card's own ``DeployUnitsAbility`` (Occupation), then High
    Priority Travel's ``HighPriorityTravelDeployUnitsCustomAbility`` (the
    grant of its Combat option; our engine offers the deployment only after
    it). Returns the ability and the garrison its targets take.
    """

    cards: list[Entity] = [c for c in (t.card,) if c is not None]
    if t.partner_ref is not None:
        try:
            cards.append(card_entity(t.partner_ref, t.seat))
        except KeyError:
            pass
    garrison = t.run.ctx.me.troops_garrison
    for card in cards:
        found = _find(card, "SardaukarCoordinationAgentAbility")
        if found is not None:
            return found, maximum
    for card in cards:
        found = _first_of(card, DeployUnitsAbility)
        if found is not None and not _find(card, "HighPriorityTravelAbility"):
            return found, garrison
    for card in cards:
        found = _find(card, "HighPriorityTravelDeployUnitsCustomAbility")
        if found is not None:
            return found, garrison
    return None, garrison


def _context_int(t: _Turn, key: str) -> int:
    value = t.context.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _max_count(actions: Sequence[DomainAction]) -> int:
    counts = [n for n in (int_arg(a, "count") for a in actions) if n is not None]
    return max(counts) if counts else 0


def _deploy_room(t: _Turn, troop_max: int, commander_max: int) -> int:
    """The largest legal ``troops + Commanders`` of one deployment (bloodlines-
    systems.md §1.3): each kind within its legal maximum, and the units
    beyond each kind's own recruits within the shared garrison extra
    (``rules/combat_deployment.py`` ``deployment_rooms``, OQ-070)."""

    recruited_troops = _context_int(t, "troops_recruited")
    recruited_commanders = _context_int(t, COMMANDERS_RECRUITED_KEY)
    shared = _context_int(t, "existing_troop_deployment_limit")
    best = 0
    for troops in range(troop_max + 1):
        for commanders in range(commander_max + 1):
            extra = max(0, troops - recruited_troops) + max(
                0, commanders - recruited_commanders
            )
            if extra <= shared:
                best = max(best, troops + commanders)
    return best


def _deploy_units(t: _Turn) -> None:
    """``DeployUnitsAbility`` in a Bloodlines game (bloodlines-systems.md §1.1,
    §1.3; D1, D6, D61).

    The garrison units are troops and Commanders (D1, plan §11.8); the
    ``NumberToSelect`` is the largest legal ``t + c`` (``_deploy_room``).
    ``GetUnitsToDeploy``'s count is split by ``deploy_split`` (Commanders
    first iff a Skill is held and none fights yet); the first kind is
    deployed now and the other kept in ``Memory.intents``
    (``DEPLOY_SPLIT_INTENT``) for the next decision, a follow-up (plan §4.6).
    Off a Combat space with no card ability that deploys (a Combat icon:
    Elite Forces, Rapid Dropships, Adaptive Tactics), the key is a
    ``DeployUnitsAbility`` custom key (D61, Sardaukar Coordination
    precedent). Used once per turn, as the base window (UNTRACED
    exhaustion); ``withdraw_*`` never.
    """

    troops = t.by_id("deploy_troops")
    commanders = t.by_id("deploy_commanders")
    run = t.run
    memory = run.memory.intents
    key = (DEPLOY_SPLIT_INTENT, run.ctx.round_number, t.seat, t.card_ref)
    stored = memory.get(key)
    if _context_int(t, "combat_troops_deployed") > 0:
        if isinstance(stored, tuple) and len(stored) == 2:
            kind, count = stored
            pool = commanders if kind == "deploy_commanders" else troops
            legal = _max_count(pool)
            if isinstance(count, int) and legal > 0:
                action = with_arg(pool, "count", min(count, legal))
                if action is not None:
                    _automatic(t, "Deploy Units rest", _FOLLOW_UP, action, -1)
                    t.on_choose[action] = [(key, _DROP)]
        return
    if stored is not None:
        memory.pop(key, None)  # stale: this turn has not deployed yet
    if not troops and not commanders:
        return
    me = run.ctx.me
    troop_max = _max_count(troops)
    commander_max = _max_count(commanders)
    maximum = _deploy_room(t, troop_max, commander_max)
    units = me.troops_garrison + me.commanders_garrison
    found = _first_of(t.space, DeployUnitsAbility)
    garrison = units
    if found is None:
        found = _find(t.card, "SardaukarCoordinationAgentAbility")
        garrison = maximum
    if found is None:
        found, _garrison = _card_deploy_ability(t, maximum)
        coordination = found is not None and ability_id(found[0]).endswith(
            "SardaukarCoordinationAgentAbility"
        )
        garrison = maximum if coordination else units
    if found is None:
        owner = t.card if t.card is not None else t.space
        if owner is None:
            t.unmapped.append("deploy off a Combat space")
            return
        found = (ability_for(DEPLOY_UNITS_ABILITY, owner), 0)
        garrison = units
    ability = found[0]
    request = Request(
        infos=(TargetInfo(options=tuple(range(garrison)), max_select=maximum),)
    )
    p = t.p
    by_kind = {"deploy_troops": troops, "deploy_commanders": commanders}

    def evaluate() -> tuple[float, DomainAction | None]:
        ans = ability.evaluate(p, request)
        if ans.response is None or not ans.response[0]:
            return ans.value, None
        count = min(len(ans.response[0]), maximum)
        n_troops, n_commanders = p.deploy_split(count, troop_max, commander_max)
        order = [("deploy_troops", n_troops), ("deploy_commanders", n_commanders)]
        if p.commanders_deploy_first():
            order.reverse()
        order = [(kind, n) for kind, n in order if n > 0]
        if not order:
            return ans.value, None
        kind, n = order[0]
        action = with_arg(by_kind[kind], "count", n)
        if action is not None and len(order) > 1:
            t.on_choose[action] = [(key, order[1])]
        return ans.value, action

    _prompt(t, "Deploy Units", (*troops, *commanders), evaluate, explicit=False)


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
    if decline is not None:
        return decline
    if not gathers:
        return None
    # Gaius Helen Mohiam's Clandestine makes the recall mandatory (no decline
    # offered): the app's "no" has no legal twin, and the Spy recalled is
    # ``GetRecallSpy``'s, as in the "yes" answer (bloodlines-systems.md §4.5).
    return worst_recall_action(run, gathers) or gathers[0]


def _explicit_pending(sources: Sequence[Source]) -> bool:
    return any(
        s.stage is Stage.PROMPT and s.extra.get("explicit") is True for s in sources
    )


def _store_on_choose(t: _Turn, chosen: DomainAction | None) -> None:
    if chosen is None:
        return
    _apply_entries(t.run.memory, t.on_choose.get(chosen, ()))


def _apply_entries(
    memory: Memory, entries: Sequence[tuple[tuple[object, ...], object]]
) -> None:
    """Write ``on_choose`` entries; ``_DROP`` removes a used follow-up."""

    for key, value in entries:
        if value is _DROP:
            memory.intents.pop(key, None)
        else:
            memory.intents[key] = value


# -- Graft: both cards' boxes in the app's order ----------------------------------


@dataclass
class _Partner:
    """The inactive grafted card's box, as the app sees it.

    ``sources`` are the partner box's sources with ``switch_graft_card`` as
    their action (``real`` maps each label to the partner action it stands
    for); ``declines``/``chores`` say the box still needs an End-Turn step.
    """

    turn: _Turn
    switch: DomainAction
    sources: list[Source]
    real: dict[str, DomainAction]
    values: dict[str, tuple[float, DomainAction | None]]


def _partner_box(t: _Turn, switch: DomainAction) -> _Partner:
    """The other grafted card's box, evaluated on the switched state.

    The app holds both cards' agent boxes in ``chosenAgentAbilities``
    (played card first, spec engine-order §3.2) and their deferred abilities
    side by side (600 and the post-action prompt). Our engine shows one box
    at a time and ``switch_graft_card`` swaps them, so the window builds the
    inactive box's sources on the state after the switch (an ordering
    device: the same seat's own frame, nothing hidden) and competes them
    with the active box's; a winning partner source is realised by the
    switch, its action kept for the next decision (``_GRAFT_SWITCH_INTENT``).
    """

    run = t.run
    seat = run.ctx.seat
    switched = apply_graft_switch(run.ctx.state, switch).state
    ctx = AppContext(switched, seat, run.ctx.view)
    # A copy of the memory: the partner's follow-ups are read, not used up.
    other_run = DecisionRun(
        ctx,
        Profile(ctx, run.profile.C, run.rng),
        legal_agent_effect_frame_actions(switched, seat),
        run.rng,
        Memory(dict(run.memory.intents), dict(run.memory.data)),
    )
    other = _turn(other_run)
    _unknown_ids(other)
    _card_box(other)
    _card_choices(other)
    if other.card_short == "signet_ring":
        # The Signet Ring's box choices are the leader's (``_leader_choices``);
        # what the leader offers in both states (Other Memories, the board
        # repeat, …) is the active state's already.
        counts = (len(other.sources), len(other.declines), len(other.chores))
        _leader_choices(other)
        legal = set(run.legal)
        other.sources[counts[0] :] = [
            s for s in other.sources[counts[0] :] if not set(s.actions) <= legal
        ]
        other.declines[counts[1] :] = [
            a for a in other.declines[counts[1] :] if a not in legal
        ]
        other.chores[counts[2] :] = [
            a for a in other.chores[counts[2] :] if a not in legal
        ]
    real: dict[str, DomainAction] = {}
    values: dict[str, tuple[float, DomainAction | None]] = {}
    sources: list[Source] = []
    for source in other.sources:
        label = _PARTNER_LABEL + source.label
        if source.stage < Stage.PROMPT:
            if source.actions:
                real[label] = source.actions[0]
            sources.append(Source(label, source.stage, (switch,), order=source.order))
            continue
        sources.append(
            Source(
                label,
                Stage.PROMPT,
                (switch,),
                evaluate=_switching(source, label, switch, real, values),
                extra=dict(source.extra),
            )
        )
    return _Partner(other, switch, sources, real, values)


def _switching(
    source: Source,
    label: str,
    switch: DomainAction,
    real: dict[str, DomainAction],
    values: dict[str, tuple[float, DomainAction | None]],
) -> Evaluation:
    evaluate = source.evaluate

    def wrapped() -> tuple[float, DomainAction | None]:
        if evaluate is None:
            return 0.0, None
        value, action = evaluate()
        values[label] = (value, action)
        if action is None:
            return value, None
        real[label] = action
        return value, switch

    return wrapped


def _recording(
    source: Source, values: dict[str, tuple[float, DomainAction | None]]
) -> Source:
    """``source`` with its evaluation recorded under its label."""

    evaluate = source.evaluate
    if source.stage is not Stage.PROMPT or evaluate is None:
        return source

    def wrapped() -> tuple[float, DomainAction | None]:
        result = evaluate()
        values[source.label] = result
        return result

    return replace(source, evaluate=wrapped)


def _partner_winner(
    sources: Sequence[Source],
    partner: _Partner,
    current: Mapping[str, tuple[float, DomainAction | None]],
) -> DomainAction | None:
    """The partner action a ``switch_graft_card`` answer stands for.

    An automatic winner is ``decide``'s ``min`` (stage, order); a prompt
    winner is a partner candidate at the top value of every candidate
    (``MakeChoice`` keeps one of the best; judgement: the first partner one
    in source order when several tie, as the shuffle cannot be replayed).
    None when the switch was the empty answer (a partner decline waits) or
    the forced prompt's random answer (no candidate above 0).
    """

    automatic = [s for s in sources if s.stage < Stage.PROMPT and s.actions]
    if automatic:
        first = min(automatic, key=lambda s: (s.stage, s.order))
        return partner.real.get(first.label)
    positive = [
        value
        for value, action in (*current.values(), *partner.values.values())
        if action is not None and value > 0
    ]
    if not positive:
        return None
    best = max(positive)
    for label, (value, action) in partner.values.items():
        if action is not None and value == best:
            return partner.real.get(label)
    return None


def _graft_intent(
    t: _Turn,
) -> tuple[DomainAction, list[tuple[tuple[object, ...], object]]] | None:
    """The partner action a ``switch_graft_card`` was taken for, if legal."""

    if t.card_ref is None:
        return None
    key = (_GRAFT_SWITCH_INTENT, t.run.ctx.round_number, t.card_ref)
    stored = t.run.memory.intents.pop(key, None)
    if not isinstance(stored, tuple) or len(stored) != 2:
        return None
    action, entries = stored
    if not isinstance(action, DomainAction) or action not in t.run.legal:
        return None
    return action, list(entries)


def _decide_with_partner(
    t: _Turn, partner: _Partner, skip: DomainAction | None, forced: bool
) -> DomainAction | None:
    """``decide`` over both boxes; a partner winner is realised by the
    switch and remembered for the next decision."""

    run = t.run
    current: dict[str, tuple[float, DomainAction | None]] = {}
    sources = [_recording(s, current) for s in t.sources]
    sources.extend(partner.sources)
    chosen = decide(run, sources, skip=skip, forced=forced)
    if chosen != partner.switch:
        return chosen
    winner = _partner_winner(sources, partner, current)
    if winner is not None:
        entries = list(partner.turn.on_choose.get(winner, ()))
        key = (_GRAFT_SWITCH_INTENT, run.ctx.round_number, partner.turn.card_ref)
        run.memory.intents[key] = (winner, entries)
    return chosen


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------


def _unknown_ids(t: _Turn) -> None:
    """A legal id outside ``_KNOWN_ACTION_IDS`` is an unmapped choice."""

    known = _KNOWN_ACTION_IDS
    ctx = t.run.ctx
    if ctx.bloodlines:
        known = known | _BLOODLINES_ACTION_IDS
    if ctx.scouts:
        known = known | _SCOUTS_ACTION_IDS
    for action_id in sorted({a.action_id for a in t.run.legal} - known):
        t.unmapped.append(f"unknown action {action_id}")


def _collect(t: _Turn) -> None:
    _unknown_ids(t)
    _board_icons(t)
    _maker(t)
    _sietch_tabr(t)
    _espionage(t)
    _shipping(t)
    _desert_tactics(t)
    _imperial_privilege(t)
    _faction_influence_source(t)
    _tuek_sietch(t)
    _mission_collect(t)
    _commander_acquire(t)
    _tech_acquire(t)
    _tech_acquire_effects(t)
    _subcommittee(t)
    _card_box(t)
    _card_choices(t)
    _leader_choices(t)
    _track_spy(t)
    _contracts(t)
    _flips(t)
    _recruit_commander(t)
    _deploy(t)
    _plots(t)
    t.sources.extend(playmat_sources(t.run))


def agent_effects_window(run: DecisionRun) -> DomainAction | None:
    """The app's answer to one ``agent_effects`` decision (module docstring)."""

    if run.first("gather_intelligence") or run.first("decline_gather_intelligence"):
        return _gather_intelligence(run)
    t = _turn(run)
    intended = _graft_intent(t)
    if intended is not None:
        action, entries = intended
        _apply_entries(run.memory, entries)
        return action
    _collect(t)
    switch = run.first("switch_graft_card")
    partner = _partner_box(t, switch) if switch is not None else None
    if t.unmapped or (partner is not None and partner.turn.unmapped):
        return None
    finish = run.first("finish_agent_turn")
    skip = next(iter((*t.declines, *t.chores)), None)
    forced = _explicit_pending(t.sources)
    if partner is None:
        chosen = decide(run, t.sources, skip=skip or finish, forced=forced)
    else:
        if skip is None and (
            partner.turn.declines or partner.turn.chores or finish is None
        ):
            # The empty answer (End Turn) needs the partner's box settled
            # first: its Optional keys declined, or (no End Turn offered
            # while it is pending) the box made active so it can wait.
            skip = switch
        forced = forced or _explicit_pending(partner.sources)
        chosen = _decide_with_partner(t, partner, skip or finish, forced)
    _store_on_choose(t, chosen)
    return chosen


HANDLERS: dict[str, Handler] = {"agent_effects": agent_effects_window}
