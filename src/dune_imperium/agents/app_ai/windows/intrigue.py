"""Intrigue plays and the ``intrigue_choice`` / ``intrigue_effects`` windows.

The app answers an intrigue card in **one** ``Evaluate``: the intrigue key of a
turn-start, post-action, post-Reveal or combat prompt is valued by the card's
ability (``abilities/intrigue.py``; ``MakeChoice`` lambdas ``b__12_2`` /
``b__12_3``, ``spec/intrigues.md`` §1) and its answer already names every
target (the faction to lose, the troops to retreat, the card to acquire...).
Our engine asks the same play step by step: ``play_intrigue(card_id,
option)``, then one ``intrigue_choice`` decision per choice slot (cost slots,
then reward slots, ``rules/intrigue.py``) and, for the cards printed as
separate lines (OQ-058), the ``intrigue_effects`` window.

- ``intrigue_play_sources`` (shared by every window that offers
  ``play_intrigue``) builds one PROMPT ``Source`` per intrigue card: the
  request of ``intrigue_request`` (encoding in ``abilities/intrigue.py``),
  the ability's answer, the ``play_intrigue`` action of the option that
  answer realises, and ``run.memory.intents[("intrigue", card_id)] =
  answer`` (plus ``("intrigue_at", card_id)`` = the event-log length at the
  evaluation, so a follow-up knows the answer belongs to this very play: the
  play's ``intrigue_played`` event is appended at exactly that index). A
  card whose app ability cannot run (``CanBeRun`` = ``MeetsCost``) is not a
  source: the app never offers it (``GetUsableIntrigueAbilities``).
- ``intrigue_choice`` / ``intrigue_effects`` replay that answer. Where the
  app answers a step later through its own evaluator, that evaluator is used:
  ``PlaceSpyEvaluator`` / ``RecallSpyEvaluator`` (``common.spy_answer``),
  ``ChooseFactionInfluenceEvaluator`` (Change Allegiances' gains),
  ``ChooseBlowWall`` (``profile-influence-uprising.md`` §6.4),
  ``CunningTrashAbility`` (``TrashAbility::Evaluate``), ``ChooseYesEvaluator``
  (Strategic Stockpiling's water line).
- **Not mirrored, answered app-like:** when no fresh answer exists (the card
  was played outside an app prompt, e.g. by the heuristic fallback of an
  unmirrored window), the card's ability is evaluated again on the current
  state and its answer recorded as the intent; a step the answer does not
  cover is answered by the slot's app evaluator (the "fallback" column).
- ``resolve_intrigue_rewards`` is never chosen: the app runs each card's
  automatic part after its choices (Cunning trashes before it draws,
  ``<RunImmediateEffects>d__11 @0x4c08f00``; Unexpected Allies blows the wall
  before the worm), which our engine does when the last slot finishes.
- Returns None (random fallback, counted) only for cards and slots this port
  has no app answer for: an intrigue card without an app archetype, or a
  Bloodlines slot (``give_intrigue_card``, ``trash_intrigue_hand_card``,
  peek, discard-pile trash, the other ``LoseTroops`` costs).

Per card (``spec/intrigues.md`` §6-§8; ours ``R4`` §9). "play" = the app
answer -> our ``play_intrigue`` option; "then" = our follow-up -> its answer:

- Backed by CHOAM: play Plot ``[track]`` -> 0, Combat ``[]`` -> 1; then
  lose -> the answer's track.
- Buy Access: play ``[t1, t2]`` -> 0; then gain x2 -> ``t1``, ``t2``.
- Call to Arms, Councilor's Ambition, Intelligence Report, Mercenaries,
  Shaddam's Favor, Weirding Combat: play -> 0; no follow-up.
- Change Allegiances: play ``[lose]`` / ``[[]]`` / ``[]`` -> 0; then
  effects: line 0 when the answer names a track (lose it, gain the swap
  pick), then line 1 when usable and a track can still gain, then finish.
  Traced: ``<RunImmediateEffects>d__11 @0x4cc2540`` yields
  ``ChangeAllegiances(lost).Targeting(MakeGainFactionTargeting(forced,
  lost))``: the Targeting decorator resolves the gain pick
  (ChooseFactionInfluenceEvaluator) *before* ``ChangeAllegiances/<execute>
  d__4 @0x4a55be0`` reads it (``Context::GetTarget`` 0x4a55e47) and only
  then pays the loss (0x4a56109). So the swap pick is priced on the
  pre-loss state, over ``GetFactionTrackTargets()`` plus the lost track
  appended when missing (``MakeGainFactionTargeting @0x4cc1060``); our
  engine pays the loss slot first, so the pick is made when the answer is
  recorded and replayed by the gain slot. The ability then moves to state
  201, which the ctor (@0x4cc0d20) binds to ``<PaySpiceForInfluence>d__12
  @0x4cc2120``: with Spice >= 3 (``CanBePaid``) and
  ``GetFactionTrackTargets().Any()`` (0x4cc22ef) it pays and raises the
  gain picker over ``GetFactionTrackTargets()``, which the AI's
  ChooseFactionInfluenceEvaluator always answers (spec §13 had it UNTRACED).
- Contingency Plan: play Plot -> 0, Combat -> 1.
- Crysknife, Desert Mouse, Ornithopter: play Plot -> 0 (the Endgame half is
  auto-played by the combat window); then flip -> the partner
  ``ScoreBattleIconsPairs`` gives the card's icon
  (``complete_battle_icon_pair_card``), else the first offered card.
- Cunning: play ``Int n`` -> n; then trash -> ``CunningTrashAbility``
  (``TrashAbility::Evaluate``), before the draw.
- Depart for Arrakis: play ``[Int 1]`` / ``[Int 0]`` / ``[]`` -> 0; then
  effects: line 0 for ``Int 1``, else finish (the Guild draw line resolves
  at play).
- Detonation: play wall ``[Int 0]`` -> 0, deploy ``[Int 1, troops]`` (wall
  standing) / ``[troops]`` -> 1; then wall -> ChooseBlowWall in IntrigueMode
  (``IntrigueBlowWall``), deploy -> ``len(troops)``.
- Devour: play ``[[card]]`` / ``[[]]`` / ``[]`` -> 0; then trash -> the
  answer's card, ``[[]]`` = decline.
- Distraction: play ``[]`` -> 0; then spy -> PlaceSpyEvaluator.
- Find Weakness: play ``[spy]`` -> 0; then effects: line 1 whenever usable;
  recall -> the answer's spy.
- Go to Ground: play ``[troops]`` -> 0; then retreat ``len(troops)``, spy ->
  PlaceSpyEvaluator.
- Imperium Politics: play ``[track]`` -> 0; then gain -> that track.
- Impress / Inspire Awe: play ``[card]`` / ``[card, Int 0]`` -> 0; then
  acquire -> that card.
- Leverage: play ``[contract]`` -> 0; then ``contract_market``
  (``windows/uprising.py`` consumes the intent).
- Manipulate: play ``[card]`` -> 0; then set aside -> that card.
- Market Opportunity, Spice Is Power: play ``Int n`` -> n; Spice Is Power's
  retreat has the single count 3.
- Opportunism: play ``[t1], [t2]`` -> 0; then lose x2 -> ``t1``, ``t2``.
- Questionable Methods: play ``[track]`` / ``[[]]`` / ``[]`` -> 0; then
  effects: line 1 when the answer names a track (lose it), else finish.
- Reach Agreement: play ``[troops], [contract]`` -> 0; then retreat
  ``len(troops)``, ``contract_market`` (uprising window).
- Sietch Ritual: play ``[card], [track]`` -> 0; then discard -> the card,
  gain -> the track.
- Special Mission: play place ``[]`` / ``[Int 0]`` -> 0, recall
  ``[Int 1, spy]`` / ``[spy]`` -> 1; then spy -> PlaceSpyEvaluator, recall ->
  the answer's spy, wall -> ChooseBlowWall in IntrigueMode.
- Spring the Trap: play ``[s1, s2]`` -> 0; then recall x2 -> ``s1``, ``s2``.
- Strategic Stockpiling: play ``[Int 1]`` (confirm) -> 0; then effects:
  line 0 (confirm) then line 1 (ChooseYesEvaluator), whichever is usable
  (``<RunImmediateEffects>d__12 @0x4c56490``: spice line, then water line).
- Tactical Option: play ``[Int 0]`` -> 0, ``[Int 1, troops]`` -> 1; then
  retreat ``len(troops)``.
- Unexpected Allies: play ``[]`` -> 0; then wall -> ChooseBlowWall with
  AIAlwaysUse (detonate).
- CHOAM Profits, Secure Spice Trade, Shadow Alliance: Endgame only.

Immortality (``spec/immortality.md`` §7):

- Breakthrough: play ``[space]`` -> 0 (``BreakthroughAbility``: each next
  research space at its ``SpaceValue``); the Research then opens our
  ``research_advance`` window, whose answer ``research_intent`` reads back
  from the recorded play.
- Counterattack: play Plot ``[units]`` -> 0 (one option per garrison unit),
  Combat ``[]`` -> 1; then deploy -> ``len(units)``.
- Disguised Bureaucrat: play ``[]`` (one marker) / ``[track]`` (two) -> 0;
  then gain -> that track.
- Economic Positioning, Gruesome Sacrifice, Illicit Dealings, Shadowy
  Bargain, Study Melange, Tleilaxu Puppet, Vicious Talents: play -> the
  option of the prompt's timing; Gruesome Sacrifice's two troop losses are
  conflict troops (``lose_intrigue_troop(zone=conflict)``; a Bloodlines
  Commander only when no troop is there, the smaller loss).
- Harvest Cells: play ``[card]`` / ``[[]]`` (Combat face up, or the
  ``conflict_end_trigger`` window's play) when ``HarvestCellsAbility`` can
  run; the request is the dealt Tleilaxu Row cards the seat can pay with the
  two harvested specimens. At the Conflict's end the specimens come first
  (``resolve_intrigue_rewards``; judgement: card-text order, and the app's
  ``GetSpecimensAvailable`` counts the harvested specimens), then the
  answer's card is acquired, on top of the deck when the destination is
  offered (``AcquireAbility``'s ``ChooseAcquireTleilaxuLocation`` option 0;
  judgement: Harvest Cells uses the same picker), ``[[]]`` ->
  ``decline_intrigue_tleilaxu``. A card no longer offered: the ability is
  evaluated again over the offered cards.

Slot fallbacks (no answer for the step): lose -> the least painful
``GetGainInfluenceValue(f, -1)`` (Backed by CHOAM's pricing, first strict
best); gain -> ChooseFactionInfluence over the offered tracks that can still
gain (``GetFactionTrackTargets``; every offered track if none can);
discard -> ``GetDiscardOrder`` first;
deploy -> ``IntrigueDeployTroops`` (at least the minimum count); trash ->
``GetCardToTrash(targets, 1.0)``; acquire / set aside -> first strictly best
``AcquireValue``; recall -> ``GetRecallSpy``; retreat ->
``GetTroopsToRetreat(max)`` (at least the minimum count).

Judgements: the request's
lose tracks are the factions with influence >= 1 (our LoseInfluence
candidates), its gain tracks those with influence <= 5
(``CanGainFactionInfluence``); troop targets are one index per troop in the
Conflict (retreats) or garrison (Detonation); acquirable cards are the Row
cards then the Reserve stacks within the printed cap (``AcquireCardUpTo``);
an ``alliance_recipient`` choice (several tied opponents; the app never asks,
UNTRACED) takes the first recipient offered; a count beyond our legal range
is clamped into it; a flip whose icon finds no ``ScoreBattleIconsPairs``
partner (our engine asks; the app's Endgame half pairs on the whole list)
takes the first offered card. Change Allegiances' swap pick is priced on
the state its answer was evaluated on (the play prompt: same influence,
alliances and opponents as the app's post-play, pre-loss state); a play not
mirrored prices it where ``_intent`` evaluates the answer again, i.e. on the
first follow-up decision the agent is asked (post-loss when the effect line
and the loss each had one legal choice).
"""

import re
from collections.abc import Callable, Sequence
from typing import Final

from dune_imperium.agents.app_ai.abilities import abilities_of
from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    ResponseItem,
    TargetInfo,
)
from dune_imperium.agents.app_ai.abilities.generic import TrashAbility
from dune_imperium.agents.app_ai.abilities.immortality import HarvestCellsAbility
from dune_imperium.agents.app_ai.abilities.intrigue import (
    IntrigueAbility,
    ability_for_prompt,
    choose_faction_influence,
    complete_battle_icon_pair_card,
    intrigue_deploy_troops,
)
from dune_imperium.agents.app_ai.catalog import (
    INTRIGUE_ARCHETYPES,
    LEADER_ARCHETYPES,
    card_entity,
    contract_entity,
    intrigue_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.choice import first_strictly_best
from dune_imperium.agents.app_ai.context import FACTIONS, AppContext, card_id
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile.immortality import research_space_entity
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    int_arg,
    spy_answer,
    str_arg,
    with_arg,
    worst_recall_action,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler, arg
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireTleilaxuCard,
    DeployFromGarrison,
    DestroyShieldWall,
    DiscardFromHand,
    FlipBattleCard,
    GainInfluence,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    PlaceSpy,
    RecallSpy,
    RetreatTroops,
    SetAsideImperiumRowCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.acquisition import (
    acquirable_imperium_instance_ids,
    acquirable_reserve_card_ids,
)
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.effect_interpreter import choice_slots
from dune_imperium.rules.spy_placement import observation_post_ids_for_agent_icons

HANDLERS: dict[str, Handler] = {}

#: ``run.memory.intents`` keys: the app answer of a card's play, and the
#: event-log length at the evaluation that produced it.
INTENT: Final = "intrigue"
INTENT_AT: Final = "intrigue_at"
#: Change Allegiances' swap gain pick, made with the answer (pre-loss state).
INTENT_SWAP_GAIN: Final = "intrigue_swap_gain"
#: ``(RESEARCH_INTENT, round, seat)`` -> our research space id: the space the
#: app answer of a Reveal research key named (``GainResearchRevealAbility``,
#: Tleilaxu Master), stored by the ``reveal`` window when it takes
#: ``advance_reveal_research``. Read with ``research_intent``.
RESEARCH_INTENT: Final = "research_space"
#: The card instance inside an Intrigue play's event source
#: (``round:R:player:P:intrigue:<instance>...``, ``rules/intrigue.py``).
_INTRIGUE_SOURCE: Final = re.compile(r":intrigue:(intrigue:[a-z0-9_]+:\d+)")
#: The Reveal-gain event source (``rules/reveal_turn.apply_reveal_gain``).
_REVEAL_GAIN_SOURCE: Final = ":reveal_gain:"
#: ``WormPlayer::GetTleilaxuInfluence`` rank at the end of the Tleilaxu track.
TLEILAXU_TRACK_END: Final = 7

_PLAY: Final = "play_intrigue"
_BREAKTHROUGH: Final = "breakthrough"
_RESERVE: Final = "reserve:"
_SHADDAM: Final = "LeaderArchetypes.Uprising.ShaddamCorrinoIV"
#: ``SpecialMissionAbility::IsCircleObservationPost``: the City posts.
_CITY_POSTS: Final = observation_post_ids_for_agent_icons((AgentIcon.CITY,))
#: ``CanGainFactionInfluence @0x4846040``: rank <= 5.
_MAX_GAINABLE: Final = 5

# Cards whose two same-timing options are chosen by the answer's ``Int n``
# (spec/intrigues.md §2.5; R4 §9.1: our option indices are the app's ints).
_INT_OPTION_CARDS: Final = frozenset(
    {"cunning", "market_opportunity", "spice_is_power", "tactical_option"}
)


# ---------------------------------------------------------------------------
# Honest reads (own state and public board only; context.py rules)
# ---------------------------------------------------------------------------


def _influence(ctx: AppContext, faction: str) -> int:
    return int(getattr(ctx.me.influence, faction))


def _lose_tracks(ctx: AppContext) -> tuple[Entity, ...]:
    """Tracks P may lose influence on (influence >= 1), app track order."""

    return tuple(track_entity(f) for f in FACTIONS if _influence(ctx, f) >= 1)


def _gain_tracks(
    ctx: AppContext, factions: Sequence[str] = FACTIONS
) -> tuple[Entity, ...]:
    """Tracks P can still gain on (``CanGainFactionInfluence``: rank <= 5)."""

    return tuple(
        track_entity(f)
        for f in FACTIONS
        if f in factions and _influence(ctx, f) <= _MAX_GAINABLE
    )


def _gain_targeting(ctx: AppContext, lost: str | None) -> tuple[Entity, ...]:
    """``ChangeAllegiancesAbility::MakeGainFactionTargeting @0x4cc1060``.

    ``WormPlayer::GetFactionTrackTargets @0x483e140`` (filter ``b__0
    @0x49a1e20`` -> ``CanGainFactionInfluence``), then the lost track
    appended when it is missing (``List.Contains`` / ``Add`` at
    0x4cc1200-0x4cc1264; ``lost`` None = the 3-spice line).
    """

    tracks = _gain_tracks(ctx)
    if lost is not None and all(t.ref != lost for t in tracks):
        tracks = (*tracks, track_entity(lost))
    return tracks


def _own_spies(ctx: AppContext) -> tuple[Entity, ...]:
    """``GetDeployedSpies(P)``: P's spies in post order."""

    return tuple(spy_entity(post, ctx.seat) for post in ctx.me.spy_post_ids)


def _hand_cards(ctx: AppContext) -> tuple[Entity, ...]:
    return tuple(card_entity(i, ctx.seat) for i in ctx.hand)


def _trash_cards(ctx: AppContext) -> tuple[Entity, ...]:
    """``FindTrashTargets``: hand, discard pile, cards in play (UNTRACED order;
    every reader shuffles)."""

    me = ctx.me
    return tuple(
        card_entity(i, ctx.seat)
        for i in (*me.hand, *me.discard_pile, *counted_in_play(me))
    )


def _row_cards(ctx: AppContext) -> tuple[Entity, ...]:
    return tuple(card_entity(i) for i in ctx.imperium_row)


def _acquirable(ctx: AppContext, max_cost: int) -> tuple[Entity, ...]:
    """``MakeAcquireImperiumRowCardTargeting(maxCost)``: Row then Reserve."""

    row = acquirable_imperium_instance_ids(ctx.state, max_cost)
    reserve = acquirable_reserve_card_ids(ctx.state, max_cost)
    return (
        *(card_entity(i) for i in row),
        *(card_entity(f"{_RESERVE}{r}") for r in reserve),
    )


def _contract_options(ctx: AppContext) -> tuple[Entity, ...]:
    """``WormPlayer::GetContractOptions``: the face-up row, then Shaddam's
    set-aside Sardaukar contracts (public)."""

    ids = list(ctx.face_up_contract_ids)
    leader = ctx.me.leader_id
    if leader is not None and LEADER_ARCHETYPES.get(leader) == _SHADDAM:
        ids.extend(ctx.state.sardaukar_contract_ids)
    return tuple(contract_entity(i, ctx.seat) for i in ids)


def _can_deploy_on_circle(ctx: AppContext) -> bool:
    """``SpecialMissionAbility::CanDeployOnCircle @0x4c505a0``: a City post
    with no spy at all."""

    return any(ctx.post_owner(post) is None for post in sorted(_CITY_POSTS))


def _research_spaces(ctx: AppContext) -> tuple[Entity, ...]:
    """``ResearchTrack.SpaceDefs[RR].NextIndices`` as research ``WormSpace``s
    (Breakthrough's targets, lower index first)."""

    return tuple(research_space_entity(s) for s in ctx.research_next_space_ids())


def _harvest_targets(ctx: AppContext) -> tuple[Entity, ...]:
    """``HarvestCellsAbility::GetHarvestCellsTargets @0x4c751c0`` (UNTRACED).

    Judgement: the dealt Tleilaxu Row cards (our engine's acquirable set;
    Reclaimed Forces is not a card one acquires) whose ``SpecimenCost`` the
    seat can pay with the two specimens the card harvests
    (``GetSpecimensAvailable @0x4c75110``, by its name), in Row order.
    """

    available = ctx.specimens() + 2
    cards = (card_entity(i) for i in ctx.state.tleilaxu_row)
    return tuple(c for c in cards if c.int_attr("SpecimenCost") <= available)


def _indices(count: int) -> tuple[int, ...]:
    """One target index per troop (``WormTroop`` targets, abilities/intrigue)."""

    return tuple(range(max(0, count)))


def _opts(*options: int) -> TargetInfo:
    return TargetInfo((), tuple(options))


def _ents(entities: Sequence[Entity]) -> TargetInfo:
    return TargetInfo(tuple(entities))


def _acquire_cap(instance: str) -> int:
    """The printed cap of the card's ``AcquireCardUpTo`` (3 for Impress and
    Inspire Awe; the app's ``MakeAcquireImperiumRowCardTargeting(3)``)."""

    for option in intrigue_card_for_instance(instance).options:
        for section in option.sections:
            for reward in section.rewards:
                if isinstance(reward, AcquireCardUpTo):
                    return reward.max_cost
    return 0


# ---------------------------------------------------------------------------
# Requests and answers
# ---------------------------------------------------------------------------


def intrigue_request(ctx: AppContext, instance: str, combat: bool) -> Request:
    """The target infos the card's ability reads (``abilities/intrigue.py``).

    ``combat`` names the half being evaluated (dual cards). Every other card
    reads no target information.
    """

    cid = card_id(instance)
    me = ctx.me
    infos: tuple[TargetInfo, ...] = ()
    if cid == "backed_by_choam" and not combat:
        infos = (_ents(_lose_tracks(ctx)),)
    elif cid in ("change_allegiances", "opportunism", "questionable_methods"):
        infos = (_ents(_lose_tracks(ctx)),)
    elif cid == "buy_access":
        infos = (_ents(_gain_tracks(ctx)),)
    elif cid == "imperium_politics":
        infos = (_ents(_gain_tracks(ctx, ("emperor", "spacing_guild"))),)
    elif cid == "sietch_ritual":
        infos = (
            _ents(_hand_cards(ctx)),
            _ents(_gain_tracks(ctx, ("bene_gesserit", "fremen"))),
        )
    elif cid in ("impress", "inspire_awe"):
        infos = (_ents(_acquirable(ctx, _acquire_cap(instance))),)
    elif cid == "manipulate":
        infos = (_ents(_row_cards(ctx)),)
    elif cid == "devour":
        infos = (_ents(_trash_cards(ctx)),)
    elif cid in ("find_weakness", "spring_the_trap"):
        infos = (_ents(_own_spies(ctx)),)
    elif cid == "leverage":
        infos = (_ents(_contract_options(ctx)),)
    elif cid == "tactical_option":
        infos = (_opts(0, 1), _opts(*_indices(me.troops_conflict)))
    elif cid == "go_to_ground":
        infos = (_opts(*_indices(me.troops_conflict)),)
    elif cid == "reach_agreement":
        infos = (
            _opts(*_indices(me.troops_conflict)),
            _ents(_contract_options(ctx)),
        )
    elif cid == "detonation":
        garrison = _opts(*_indices(me.troops_garrison))
        infos = (_opts(0, 1), garrison) if ctx.shield_wall_present else (garrison,)
    elif cid == "special_mission":
        spies = _ents(_own_spies(ctx))
        infos = (_opts(0, 1), spies) if _can_deploy_on_circle(ctx) else (spies,)
    elif cid == "breakthrough":
        infos = (_ents(_research_spaces(ctx)),)
    elif cid == "counterattack" and not combat:
        # ``targets.OfType<WormUnit>()``: one index per garrison unit.
        infos = (_opts(*_indices(me.troops_garrison)),)
    elif cid == "disguised_bureaucrat":
        infos = (_ents(_gain_tracks(ctx)),)
    elif cid == "harvest_cells":
        infos = (_ents(_harvest_targets(ctx)),)
    return Request(infos)


def _item(answer: Answer, index: int) -> ResponseItem | None:
    """Response item ``index`` of the answer, if stored."""

    if answer.response is None or index >= len(answer.response):
        return None
    return answer.response[index]


def _first_ref(item: ResponseItem | None) -> str | None:
    if not item:
        return None
    ref = item[0]
    return ref if isinstance(ref, str) else None


def _first_int(item: ResponseItem | None) -> int | None:
    if not item:
        return None
    value = item[0]
    return value if isinstance(value, int) else None


def _timing_options(instance: str, combat: bool) -> list[int]:
    timing = IntrigueTiming.COMBAT if combat else IntrigueTiming.PLOT
    options = intrigue_card_for_instance(instance).options
    return [i for i, option in enumerate(options) if option.timing is timing]


def _answer_option(
    instance: str, request: Request, answer: Answer, combat: bool
) -> int | None:
    """Our ``play_intrigue`` option that realises the app's answer."""

    if answer.response is None:
        return None
    cid = card_id(instance)
    candidates = _timing_options(instance, combat)
    if cid in _INT_OPTION_CARDS:
        option = _first_int(_item(answer, 0))
    elif cid == "detonation":
        # Wall standing: [Int 0] blow / [Int 1, troops] deploy; else [troops].
        option = _first_int(_item(answer, 0)) if len(request.infos) == 2 else 1
    elif cid == "special_mission":
        if len(request.infos) == 2:  # CanDeployOnCircle: [] / [Int 0] / [Int 1, spy]
            option = 1 if _first_int(_item(answer, 0)) == 1 else 0
        else:  # recall only: [spy]
            option = 1
    elif len(candidates) == 1:
        option = candidates[0]
    else:
        return None
    return option if option in candidates else None


def _play_action(
    plays: Sequence[DomainAction], option: int | None
) -> DomainAction | None:
    if option is None:
        return None
    return with_arg(plays, "option", option)


def _record(run: DecisionRun, instance: str, answer: Answer, stamp: int | None) -> None:
    """Store the answer of the card's play, stamped ``stamp``.

    Change Allegiances also stores its swap gain pick here, on the state the
    answer was evaluated on: the app resolves that pick
    (``ChooseFactionInfluenceEvaluator`` over ``MakeGainFactionTargeting(...,
    lost)``) before ``ChangeAllegiances/<execute>d__4 @0x4a55be0`` pays the
    loss, whereas our engine asks the gain slot after the loss slot.
    """

    intents = run.memory.intents
    intents[(INTENT, instance)] = answer
    intents[(INTENT_AT, instance)] = stamp
    if card_id(instance) != "change_allegiances":
        return
    lost = _first_ref(_item(answer, 0))
    if lost is None:
        intents.pop((INTENT_SWAP_GAIN, instance), None)
        return
    tracks = _gain_targeting(run.ctx, lost)
    intents[(INTENT_SWAP_GAIN, instance)] = choose_faction_influence(
        run.profile, tracks
    )


def intrigue_play_sources(
    run: DecisionRun, actions: Sequence[DomainAction], *, combat: bool
) -> list[Source]:
    """One PROMPT ``Source`` per intrigue card offered by ``play_intrigue``.

    Shared by every window that offers intrigue plays (``turn``,
    ``agent_effects``, ``reveal`` for Plots; ``combat_intrigue`` with
    ``combat=True``). Each source evaluates the card's ability named by
    ``abilities.intrigue.ability_for_prompt(card, combat)`` on a request built
    from the current state (encoding in ``abilities/intrigue.py``), maps the
    app's answer to the matching ``play_intrigue(card_id, option)`` action and
    records the answer in ``run.memory.intents[("intrigue", card_id)]`` so the
    follow-up ``intrigue_choice`` / ``intrigue_effects`` windows can replay it.

    App: ``WormAIProfile::MakeChoice @0x48fef80`` over the intrigue keys of
    ``GetUsableIntrigueAbilities`` (``CanBeRun`` filter, spec/intrigues.md
    §2.1–2.2): a card whose ability cannot run gets no source. One source per
    physical card (each is its own ``WormIntriguePlayable`` key).
    """

    plays: dict[str, list[DomainAction]] = {}
    for action in actions:
        if action.action_id != _PLAY:
            continue
        instance = str_arg(action, "card_id")
        if instance is not None:
            plays.setdefault(instance, []).append(action)
    sources: list[Source] = []
    for instance, card_plays in plays.items():
        if card_id(instance) not in INTRIGUE_ARCHETYPES:
            continue
        ability = ability_for_prompt(intrigue_entity(instance, run.ctx.seat), combat)
        if ability is None or not ability.can_be_run(run.profile):
            continue
        sources.append(
            Source(
                label=f"intrigue {instance}",
                stage=Stage.PROMPT,
                actions=tuple(card_plays),
                evaluate=_evaluator(run, instance, ability, card_plays, combat),
            )
        )
    return sources


def _evaluator(
    run: DecisionRun,
    instance: str,
    ability: IntrigueAbility,
    plays: Sequence[DomainAction],
    combat: bool,
) -> Callable[[], tuple[float, DomainAction | None]]:
    def evaluate() -> tuple[float, DomainAction | None]:
        request = intrigue_request(run.ctx, instance, combat)
        answer = ability.evaluate(run.profile, request)
        _record(run, instance, answer, len(run.ctx.state.event_log))
        option = _answer_option(instance, request, answer, combat)
        return answer.value, _play_action(plays, option)

    return evaluate


# ---------------------------------------------------------------------------
# The answer of the play being resolved
# ---------------------------------------------------------------------------


def _play_event_index(ctx: AppContext, instance: str) -> int | None:
    """Index of this seat's latest ``intrigue_played`` event of the card.

    Reads only events visible to the seat (the play of one's own card is
    public).
    """

    log = ctx.state.event_log
    for index in range(len(log) - 1, -1, -1):
        event = log[index]
        if event.kind != "intrigue_played":
            continue
        if event.visible_to is not None and ctx.seat not in event.visible_to:
            continue
        payload = dict(event.payload)
        if payload.get("card_id") == instance and payload.get("player") == ctx.seat:
            return index
    return None


def recorded_answer(run: DecisionRun, instance: str) -> Answer | None:
    """The answer ``intrigue_play_sources`` recorded for the play of
    ``instance`` being resolved, or None.

    The stored answer counts only when it was evaluated on the state the play
    was made from (``INTENT_AT`` equals the index of the play's
    ``intrigue_played`` event); an answer from an earlier prompt in which the
    card was not played is stale. Other windows that consume the intent
    (``contract_market`` for Leverage / Reach Agreement) can use this test.
    """

    played_at = _play_event_index(run.ctx, instance)
    stored = run.memory.intents.get((INTENT, instance))
    stamp = run.memory.intents.get((INTENT_AT, instance))
    if isinstance(stored, Answer) and played_at is not None and stamp == played_at:
        return stored
    return None


def _intent(run: DecisionRun, instance: str, option: IntrigueOption) -> Answer:
    """The app answer of the play being resolved.

    ``recorded_answer`` when there is one. Otherwise (played outside an app
    prompt; not mirrored) the card's ability is evaluated again now and that
    answer is recorded in its place (``_record``, with Change Allegiances'
    swap pick), stamped with the play's event index.
    """

    stored = recorded_answer(run, instance)
    if stored is not None:
        return stored
    played_at = _play_event_index(run.ctx, instance)
    combat = option.timing is IntrigueTiming.COMBAT
    ability = ability_for_prompt(intrigue_entity(instance, run.ctx.seat), combat)
    if ability is None:
        answer = Answer(0.0, None, "no ability")
    else:
        request = intrigue_request(run.ctx, instance, combat)
        answer = ability.evaluate(run.profile, request)
    _record(run, instance, answer, played_at)
    return answer


def _flat_refs(answer: Answer) -> list[str]:
    refs: list[str] = []
    for item in answer.response or ():
        refs.extend(ref for ref in item if isinstance(ref, str))
    return refs


# ---------------------------------------------------------------------------
# Slot answers (intrigue_choice)
# ---------------------------------------------------------------------------


def _faction_action(
    actions: Sequence[DomainAction], faction: str | None
) -> DomainAction | None:
    """The first ``choose_intrigue_faction`` for ``faction`` (with several
    ``alliance_recipient`` variants the first recipient; UNTRACED)."""

    if faction is None:
        return None
    return with_arg(actions, "faction", faction)


def _offered_factions(actions: Sequence[DomainAction]) -> list[str]:
    offered = {str_arg(a, "faction") for a in actions}
    return [f for f in FACTIONS if f in offered]


def _least_painful_loss(
    run: DecisionRun, actions: Sequence[DomainAction]
) -> DomainAction | None:
    """Fallback loss: first strictly best ``GetGainInfluenceValue(f, -1)``
    (Backed by CHOAM's pricing, ``BackedByCHOAMPlotAbility::Evaluate``)."""

    p = run.profile
    scored = [
        (f, p.gain_influence_value(f, -1, -1, False).sum)
        for f in _offered_factions(actions)
    ]
    best = first_strictly_best(scored)
    return None if best is None else _faction_action(actions, best[0])


def _evaluator_gain(
    run: DecisionRun, actions: Sequence[DomainAction]
) -> DomainAction | None:
    """``ChooseFactionInfluenceEvaluator::Evaluate @0x492eca0`` over the
    offered tracks that can still gain (``G(f, +1) + 100``, first strictly
    best).

    The app's gain pickers start from ``WormPlayer::GetFactionTrackTargets
    @0x483e140`` (``CanGainFactionInfluence``: rank <= 5); our engine also
    offers a track at the top. Judgement: every offered track when none can
    gain, so the slot still has an answer.
    """

    offered = _offered_factions(actions)
    gainable = {t.ref for t in _gain_tracks(run.ctx, offered)}
    factions = [f for f in offered if f in gainable] or offered
    answer = choose_faction_influence(run.profile, [track_entity(f) for f in factions])
    return _faction_action(actions, _first_ref(_item(answer, 0)))


def _lose_influence(
    run: DecisionRun, cid: str, intent: Callable[[], Answer], k: int
) -> DomainAction | None:
    actions = run.by_id("choose_intrigue_faction")
    intended: str | None = None
    if cid in ("backed_by_choam", "change_allegiances", "questionable_methods"):
        intended = _first_ref(_item(intent(), 0))
    elif cid == "opportunism":  # [t1], [t2]: the k-th loss
        intended = _first_ref(_item(intent(), k))
    return _faction_action(actions, intended) or _least_painful_loss(run, actions)


def _frame_sections(run: DecisionRun) -> tuple[int, ...]:
    """The option sections the choice frame resolves (one printed line for
    the separate-line cards)."""

    raw = run.ctx.top_frame_context.get("sections")
    if not isinstance(raw, str):
        return ()
    return tuple(int(i) for i in raw.split(",") if i)


def _gain_influence(
    run: DecisionRun, cid: str, instance: str, intent: Callable[[], Answer], k: int
) -> DomainAction | None:
    actions = run.by_id("choose_intrigue_faction")
    intended: str | None = None
    if cid == "buy_access":  # [t1, t2]: the k-th gain
        refs = _item(intent(), 0) or ()
        ref = refs[k] if k < len(refs) else None
        intended = ref if isinstance(ref, str) else None
    elif cid in ("imperium_politics", "disguised_bureaucrat"):
        intended = _first_ref(_item(intent(), 0))
    elif cid == "sietch_ritual":
        intended = _first_ref(_item(intent(), 1))
    elif cid == "change_allegiances" and _frame_sections(run) == (0,):
        # The swap: the pick _record made with the answer, before the loss.
        intent()  # makes the play's answer (and its swap pick) current
        swap = run.memory.intents.get((INTENT_SWAP_GAIN, instance))
        if isinstance(swap, Answer):
            intended = _first_ref(_item(swap, 0))
    return _faction_action(actions, intended) or _evaluator_gain(run, actions)


def _discard(
    run: DecisionRun, cid: str, intent: Callable[[], Answer]
) -> DomainAction | None:
    actions = run.by_id("choose_intrigue_discard")
    if cid == "sietch_ritual":
        chosen = with_arg(actions, "card_id", _first_ref(_item(intent(), 0)))
        if chosen is not None:
            return chosen
    cards = [
        card_entity(ref, run.ctx.seat)
        for a in actions
        if (ref := str_arg(a, "card_id")) is not None
    ]
    order = run.profile.discard_order(cards, False)
    return with_arg(actions, "card_id", order[0].ref) if order else None


def _shield_wall(run: DecisionRun, cid: str) -> DomainAction | None:
    """The ``BlowWall`` prompt: ``ChooseBlowWall::Evaluate @0x492d810``.

    Unexpected Allies builds it with ``AIAlwaysUse`` (yes), Detonation and
    Special Mission with ``IntrigueMode`` (``IntrigueBlowWall``), every other
    source with neither (``ShouldBlowWall``) — profile-influence-uprising §6.4.
    """

    if cid == "unexpected_allies":
        blow = True
    elif cid in ("detonation", "special_mission"):
        blow = run.profile.intrigue_blow_wall()
    else:
        blow = run.profile.should_blow_wall()
    return run.first("detonate_shield_wall" if blow else "keep_shield_wall")


def _count_action(actions: Sequence[DomainAction], count: int) -> DomainAction | None:
    """The troops-only action of ``count`` units, clamped into the legal range."""

    by_count = {
        n: a
        for a in actions
        if (n := int_arg(a, "count")) is not None and arg(a, "commanders") is None
    }
    if not by_count:
        return None
    clamped = min(max(count, min(by_count)), max(by_count))
    return by_count.get(clamped)


def _deploy(
    run: DecisionRun, cid: str, intent: Callable[[], Answer]
) -> DomainAction | None:
    actions = run.by_id("deploy_intrigue_troops")
    count: int | None = None
    if cid == "detonation":
        answer = intent()
        if run.ctx.shield_wall_present:  # [Int 1, troops]
            if _first_int(_item(answer, 0)) == 1:
                troops = _item(answer, 1)
                count = len(troops) if troops else None
        else:  # [troops]
            troops = _item(answer, 0)
            count = len(troops) if troops else None
    elif cid == "counterattack":  # [units]: GetUnitsToDeploy(units, <= 2)
        units = _item(intent(), 0)
        count = len(units) if units is not None else None
    if count is None:
        garrison = _indices(run.ctx.me.troops_garrison)
        count = intrigue_deploy_troops(run.profile, garrison)
    return _count_action(actions, count)


def _trash(
    run: DecisionRun, cid: str, instance: str, intent: Callable[[], Answer]
) -> DomainAction | None:
    actions = run.by_id("trash_intrigue_card")
    decline = run.first("decline_intrigue_trash")
    if cid == "devour":
        item = _item(intent(), 0)
        if item is not None:
            if not item:  # [[]]: trash nothing
                return decline
            chosen = with_arg(actions, "card_id", _first_ref(item))
            if chosen is not None:
                return chosen
    cards = [
        card_entity(ref, run.ctx.seat)
        for a in actions
        if (ref := str_arg(a, "card_id")) is not None
    ]
    request = Request((TargetInfo(tuple(cards)),))
    trash = None
    if cid == "cunning":  # CunningTrashAbility : TrashAbility (Explicit, forced)
        entity = intrigue_entity(instance, run.ctx.seat)
        trash = next(
            (a for a in abilities_of(entity) if isinstance(a, TrashAbility)), None
        )
    if trash is not None:
        answer = trash.evaluate(run.profile, request)
        ref = _first_ref(_item(answer, 0))
    else:  # TrashAbility::Evaluate @0x4ce98a0: GetCardToTrash(targets, 1.0)
        card, _ = run.profile.card_to_trash(cards, 1.0)
        ref = None if card is None else card.ref
    if ref is None:
        return decline
    return with_arg(actions, "card_id", ref) or decline


def _card_action(
    actions: Sequence[DomainAction], ref: str | None
) -> DomainAction | None:
    """``acquire_intrigue_reserve(card_id)`` for ``reserve:<id>``, else
    ``acquire_intrigue_imperium(instance_id)``."""

    if ref is None:
        return None
    if ref.startswith(_RESERVE):
        reserve = [a for a in actions if a.action_id == "acquire_intrigue_reserve"]
        return with_arg(reserve, "card_id", ref[len(_RESERVE) :])
    row = [a for a in actions if a.action_id == "acquire_intrigue_imperium"]
    return with_arg(row, "instance_id", ref)


def _best_acquire(run: DecisionRun, cards: Sequence[Entity]) -> str | None:
    best = first_strictly_best(
        [(card.ref, run.profile.acquire_value(card).sum) for card in cards]
    )
    return None if best is None else best[0]


def _acquire(
    run: DecisionRun, cid: str, instance: str, intent: Callable[[], Answer]
) -> DomainAction | None:
    actions = [
        a
        for a in run.legal
        if a.action_id in ("acquire_intrigue_reserve", "acquire_intrigue_imperium")
    ]
    if not actions:
        return run.first("skip_intrigue_acquisition")
    if cid in ("impress", "inspire_awe"):
        chosen = _card_action(actions, _first_ref(_item(intent(), 0)))
        if chosen is not None:
            return chosen
    offered = {str_arg(a, "instance_id") for a in actions} | {
        f"{_RESERVE}{str_arg(a, 'card_id')}" for a in actions
    }
    cards = [
        c for c in _acquirable(run.ctx, _acquire_cap(instance)) if c.ref in offered
    ]
    return _card_action(actions, _best_acquire(run, cards))


def _set_aside(
    run: DecisionRun, cid: str, intent: Callable[[], Answer]
) -> DomainAction | None:
    actions = run.by_id("manipulate_imperium_row")
    if cid == "manipulate":
        chosen = with_arg(actions, "instance_id", _first_ref(_item(intent(), 0)))
        if chosen is not None:
            return chosen
    offered = {str_arg(a, "instance_id") for a in actions}
    cards = [c for c in _row_cards(run.ctx) if c.ref in offered]
    return with_arg(actions, "instance_id", _best_acquire(run, cards))


def _recall(
    run: DecisionRun, cid: str, intent: Callable[[], Answer]
) -> DomainAction | None:
    actions = run.by_id("recall_spy_for_intrigue")
    if cid in ("special_mission", "spring_the_trap", "find_weakness"):
        for ref in _flat_refs(intent()):  # the next answered spy still out
            chosen = with_arg(actions, "post_id", ref)
            if chosen is not None:
                return chosen
    return worst_recall_action(run, actions)


def _retreat(
    run: DecisionRun, cid: str, intent: Callable[[], Answer]
) -> DomainAction | None:
    actions = run.by_id("retreat_intrigue_troops")
    count: int | None = None
    if cid in ("go_to_ground", "reach_agreement"):  # [troops], ...
        troops = _item(intent(), 0)
        count = len(troops) if troops else None
    elif cid == "tactical_option":  # [Int 1, troops]
        answer = intent()
        if _first_int(_item(answer, 0)) == 1:
            troops = _item(answer, 1)
            count = len(troops) if troops else None
    if count is None:
        counts = [n for a in actions if (n := int_arg(a, "count")) is not None]
        if not counts:
            return None
        count = run.profile.troops_to_retreat(max(counts))
    return _count_action(actions, count)


def _lose_troops(run: DecisionRun, cid: str) -> DomainAction | None:
    """Gruesome Sacrifice's cost: "lose two of your troops in the Conflict".

    ``GruesomeSacrificeAbility`` answers no target (``Upd(v, src, null)``):
    the app takes two of its Conflict troops. Our engine asks each loss and
    lets a Bloodlines Commander stand in; the plain troop is taken while one
    is there (the smaller loss, plan §11.4), else the Commander. Any other
    ``LoseTroops`` cost is a Bloodlines card: not mirrored here.
    """

    if cid != "gruesome_sacrifice":
        return None
    actions = run.by_id("lose_intrigue_troop")
    for action in actions:
        if str_arg(action, "zone") == "conflict" and arg(action, "commanders") is None:
            return action
    return with_arg(actions, "zone", "conflict")


def _acquire_tleilaxu(run: DecisionRun, cid: str, instance: str) -> DomainAction | None:
    """Harvest Cells' "you may also acquire a Tleilaxu card" (module table).

    The harvested specimens are taken first (``resolve_intrigue_rewards``).
    Then the play's recorded answer (``recorded_answer``: the
    ``combat_intrigue`` or ``conflict_end_trigger`` prompt that played the
    card) is replayed: its card, or "no acquire" (an empty list) ->
    ``decline_intrigue_tleilaxu``. Without one, or when its card is not
    offered, ``HarvestCellsAbility::Evaluate @0x4c75550`` runs now over the
    offered cards (two specimens for "no acquire", a card at its
    ``AcquireValue`` + two specimens when strictly better).
    """

    if cid != "harvest_cells":
        return None
    resolve = run.first("resolve_intrigue_rewards")
    if resolve is not None:
        return resolve
    decline = run.first("decline_intrigue_tleilaxu")
    acquires = run.by_id("acquire_intrigue_tleilaxu")
    refs = list(
        dict.fromkeys(
            ref for a in acquires if (ref := str_arg(a, "instance_id")) is not None
        )
    )
    recorded = recorded_answer(run, instance)
    item = None if recorded is None else _item(recorded, 0)
    chosen: str | None
    if item is not None and (not item or _first_ref(item) in refs):
        chosen = _first_ref(item)
    else:
        entity = intrigue_entity(instance, run.ctx.seat)
        ability = next(
            (a for a in abilities_of(entity) if isinstance(a, HarvestCellsAbility)),
            None,
        )
        if ability is None:
            return None
        cards = tuple(card_entity(ref) for ref in refs)
        answer = ability.evaluate(run.profile, Request((TargetInfo(cards),)))
        chosen = _first_ref(_item(answer, 0))
    if chosen is None:
        return decline
    variants = [a for a in acquires if str_arg(a, "instance_id") == chosen]
    # ``ChooseAcquireTleilaxuLocation`` (GM > 0): option 0, the top of the deck.
    for action in variants:
        if arg(action, "to_deck_top") is True:
            return action
    return variants[0] if variants else decline


def research_intent(run: DecisionRun) -> str | None:
    """The research space the app's answer named for the Research icon the
    ``research_advance`` frame on top resolves, or None.

    For the decision windows that answer ``research_advance`` (the app asks
    the direction inside the ability that grants the Research, so its answer
    already names the space):

    - a Breakthrough play (the frame's ``source`` names the Intrigue
      instance): the space of ``recorded_answer`` (``BreakthroughAbility``'s
      ``SpaceValue`` pick, which can differ from ``GainResearchAbility``'s
      floor-1.0 pick when no space is worth more than 0);
    - a Reveal research key (Tleilaxu Master): the space the ``reveal``
      window stored under ``(RESEARCH_INTENT, round, seat)`` when it took
      ``advance_reveal_research`` (``GainResearchRevealAbility``'s answer).

    The stored Reveal intent is consumed by the call. A space that is not
    among the frame's legal ``choose_research_space`` options gives None.
    """

    key = (RESEARCH_INTENT, run.ctx.round_number, run.ctx.seat)
    stored = run.memory.intents.pop(key, None)
    source = run.ctx.top_frame_context.get("source")
    if not isinstance(source, str):
        return None
    space: str | None = None
    match = _INTRIGUE_SOURCE.search(source)
    if match is not None:
        # Only Breakthrough's answer names a research space; another
        # Intrigue's research (an acquired card's Research acquire effect,
        # e.g. Spiritual Fervor through Impress) has no answer to replay.
        instance = match.group(1)
        answer = (
            recorded_answer(run, instance)
            if card_id(instance) == _BREAKTHROUGH
            else None
        )
        if answer is not None:
            space = _first_ref(_item(answer, 0))
    elif _REVEAL_GAIN_SOURCE in source and isinstance(stored, str):
        space = stored
    if space is None:
        return None
    space = space.removeprefix("research:")
    offered = {str_arg(a, "space_id") for a in run.by_id("choose_research_space")}
    return space if space in offered else None


def _flip(run: DecisionRun, instance: str) -> DomainAction | None:
    actions = run.by_id("flip_battle_card")
    entity = intrigue_entity(instance, run.ctx.seat)
    target = complete_battle_icon_pair_card(run.profile, entity)
    chosen = with_arg(actions, "card_id", target)
    return chosen if chosen is not None else (actions[0] if actions else None)


def _choice_frame(
    run: DecisionRun,
) -> tuple[str, IntrigueOption, object, int] | None:
    """(card instance, played option, current slot, same-kind slots before it)."""

    context = run.ctx.top_frame_context
    instance = context.get("card_id")
    option_index = context.get("option")
    slot_index = context.get("slot")
    raw = context.get("sections")
    if not (
        isinstance(instance, str)
        and isinstance(option_index, int)
        and isinstance(slot_index, int)
        and isinstance(raw, str)
        and card_id(instance) in INTRIGUE_ARCHETYPES
    ):
        return None
    option = intrigue_card_for_instance(instance).options[option_index]
    sections = tuple(option.sections[int(i)] for i in raw.split(",") if i)
    wall = context.get("shield_wall_at_play", True) is True
    slots = choice_slots(sections, shield_wall_present=wall)
    if not 0 <= slot_index < len(slots):
        return None
    slot = slots[slot_index]
    k = sum(1 for s in slots[:slot_index] if type(s) is type(slot))
    return instance, option, slot, k


def intrigue_choice(run: DecisionRun) -> DomainAction | None:
    """``intrigue_choice``: one choice slot of the card being resolved.

    Replays the app answer recorded at the play (``_intent``) or answers the
    slot through the app evaluator that asks it (module table).
    """

    frame = _choice_frame(run)
    if frame is None:
        return None
    instance, option, slot, k = frame
    cid = card_id(instance)

    def intent() -> Answer:
        return _intent(run, instance, option)

    match slot:
        case LoseInfluence():
            return _lose_influence(run, cid, intent, k)
        case GainInfluence():
            return _gain_influence(run, cid, instance, intent, k)
        case DiscardFromHand():
            return _discard(run, cid, intent)
        case DestroyShieldWall():
            return _shield_wall(run, cid)
        case DeployFromGarrison():
            return _deploy(run, cid, intent)
        case TrashPersonalCard():
            return _trash(run, cid, instance, intent)
        case PlaceSpy():
            return spy_answer(
                run,
                run.by_id("place_intrigue_spy"),
                run.by_id("recall_spy_for_intrigue"),
                run.first("decline_intrigue_spy"),
            )
        case AcquireCardUpTo():
            return _acquire(run, cid, instance, intent)
        case SetAsideImperiumRowCard():
            return _set_aside(run, cid, intent)
        case RecallSpy():
            return _recall(run, cid, intent)
        case RetreatTroops():
            return _retreat(run, cid, intent)
        case FlipBattleCard():
            return _flip(run, instance)
        case LoseTroops():
            return _lose_troops(run, cid)
        case AcquireTleilaxuCard():
            return _acquire_tleilaxu(run, cid, instance)
    return None


# ---------------------------------------------------------------------------
# Separate printed lines (intrigue_effects)
# ---------------------------------------------------------------------------


def _effects_frame(run: DecisionRun) -> tuple[str, IntrigueOption, set[int]] | None:
    context = run.ctx.top_frame_context
    instance = context.get("card_id")
    option_index = context.get("option")
    if not isinstance(instance, str) or not isinstance(option_index, int):
        return None
    if card_id(instance) not in INTRIGUE_ARCHETYPES:
        return None
    option = intrigue_card_for_instance(instance).options[option_index]
    used = {int(i) for i in str(context.get("used", "")).split(",") if i}
    return instance, option, used


def intrigue_effects(run: DecisionRun) -> DomainAction | None:
    """``intrigue_effects``: which printed line to use next, or finish.

    The app resolves the card in one ability run (module table): Change
    Allegiances swaps when its answer names a track, then pays spice for
    influence whenever it has 3 spice and a track can still gain; Depart for
    Arrakis buys troops on
    ``Int 1``; Strategic Stockpiling confirms the spice line and says yes to
    the water line; Find Weakness always recalls; Questionable Methods loses
    the answered track.
    """

    frame = _effects_frame(run)
    if frame is None:
        return None
    instance, option, used = frame
    cid = card_id(instance)
    lines = {
        n: a
        for a in run.by_id("use_intrigue_effect")
        if (n := int_arg(a, "section")) is not None
    }
    finish = run.first("finish_intrigue_effects")

    def first_of(*wanted: int) -> DomainAction | None:
        for n in wanted:
            if n in lines:
                return lines[n]
        return finish

    if cid == "change_allegiances":
        # <RunImmediateEffects>d__11 @0x4cc2540: swap the answer's first track
        # (if any); <PaySpiceForInfluence>d__12 @0x4cc2120: Spice >= 3 (our
        # line 1 is offered only then) and GetFactionTrackTargets().Any()
        # (0x4cc22ef) -> pay and gain (ChooseFactionInfluenceEvaluator).
        swap = _first_ref(_item(_intent(run, instance, option), 0)) is not None
        if swap and 0 not in used and 0 in lines:
            return lines[0]
        if _gain_tracks(run.ctx):
            return first_of(1)
        return finish or first_of(1)
    if cid == "depart_for_arrakis":
        troops = _first_int(_item(_intent(run, instance, option), 0)) == 1
        return first_of(0) if troops else (finish or first_of(0))
    if cid == "strategic_stockpiling":
        # <RunImmediateEffects>d__12 @0x4c56490: Int 1 (the only answer the
        # Evaluate gives) pays 5 spice, then ChooseYes pays 3 water.
        return first_of(0, 1)
    if cid == "find_weakness":
        return first_of(1)
    if cid == "questionable_methods":
        lose = _first_ref(_item(_intent(run, instance, option), 0)) is not None
        return first_of(1) if lose else (finish or first_of(1))
    return None


HANDLERS["intrigue_choice"] = intrigue_choice
HANDLERS["intrigue_effects"] = intrigue_effects
