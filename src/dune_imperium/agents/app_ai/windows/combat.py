"""Combat windows.

``combat_intrigue``, ``combat_reward_*``, ``control_defense``,
``endgame_intrigue``.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to the heuristic.

App side (``analysis/ai/15-combat-phase.md`` incl. Errata, ``spec/engine-order.md``
§1 and §6, ``spec/board.md`` §2, ``spec/intrigues.md`` §2.3 and §8):

- ``combat_intrigue``: ``CombatPhase/<PlayCombatIntrigueCards>d__18`` (state
  100) asks each combatant a **non-forced** prompt ``worm.combat.intrigue``;
  every Combat intrigue key is valued by its card's ``Evaluate``
  (``windows.intrigue.intrigue_play_sources``); the empty answer is the pass.
- ``combat_reward_*``: ``CombatPhase/<PlayCombatResolutionIntrigueCards>d__21``
  (state 400). Take Control and Gain-Any-Two-Influence run without a prompt
  (their own target question is the ability's ``Evaluate``); the deferred
  rewards that ``CanRunImmediately`` (contract, spy, gain-any-influence) run
  as forced single-key prompts; the rest (pay X -> VP, recall 2 spies -> VP,
  trash) are keys of ``worm.combat.intrigue.resolution``, forced only while
  an Explicit one (Trash) is pending. Our engine asks each reward as its own
  frame, in a fixed order; each frame is answered with the port of the
  reward ability the app attaches for it (the reward archetype's
  ``CustomAbilityIDs``, ``catalog.conflict_reward_entities``).
- ``control_defense``: ``GenerateConflictPhase/<DeployControlTroops>d__8``
  asks nothing and always deploys.
- ``endgame_intrigue``: ``EndgamePhase/<PlayEndgameIntrigues>d__9`` plays every
  Endgame ability that can run for every seat, then ``ScoreBattleIconsPairs
  (includeWildcards = true)`` scores each seat's battle-icon sets; no prompt.

The app's reward window sees the sole winner's battle icon already scored
(``ResolveCombat`` runs it before the place-1 window); ours scores it in
``finish_combat`` after every reward frame. ``app_reward_run`` rebuilds the
app's view for the reward windows.

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

import copy
from collections.abc import Callable
from dataclasses import replace

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Request,
    TargetInfo,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.board import (
    GainAnyTwoInfluenceConflictAbility,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    GainAnyInfluenceConflictAbility,
    PayAttributeToGainVPAbility,
    Recall2SpiesVPAbility,
    TrashConflictCustomAbility,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    battle_icon_list,
    endgame_auto_plays,
    endgame_wild_pairs,
    score_battle_icons_pairs,
)
from dune_imperium.agents.app_ai.catalog import (
    CONFLICT_ARCHETYPES,
    card_entity,
    conflict_reward_entities,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    decide,
    spy_answer,
    str_arg,
    with_arg,
)
from dune_imperium.agents.app_ai.windows.intrigue import intrigue_play_sources
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.combat import rank_combat

#: ``Memory.intents`` key prefix of a planned "choose two" Influence answer:
#: ``(DISTINCT_INFLUENCE_INTENT, round, seat, group)`` -> the app's factions
#: in pick order (``combat_reward_distinct_influence``).
DISTINCT_INFLUENCE_INTENT = "combat_reward_distinct_influence"


# ---------------------------------------------------------------------------
# The app's view of a reward window
# ---------------------------------------------------------------------------


def app_reward_run(run: DecisionRun) -> DecisionRun:
    """``run`` as the app's reward window sees it: battle icon already scored.

    ``CombatPhase/<ResolveCombat>d__20::MoveNext @0x49f4d90`` (15 §3.2, §3.7):
    for the place-1, non-double entry it appends the Conflict's battle icon to
    the winner's ``BattleIconList`` and runs ``ScoreBattleIconsPairs
    (includeWildcards = false)`` before the winner's resolution window, and
    every later entry's window comes after it. Our engine does both in
    ``finish_combat`` after every reward frame (R3 §5.1, §6), so the values
    the app reads (``VictoryPoints`` in ``GetVictoryPointValue``'s doubling and
    ``IsClimax``, the battle-icon list) would lag by one card.

    Judgement: for every ``combat_reward_*`` window the sole winner (our
    ``rank_combat``, the same placement as ``DetermineRewards``) gets the
    current Conflict appended to ``won_conflict_ids`` and the natural sets of
    ``score_battle_icons_pairs(include_wildcards=False)`` flipped face down
    at 1 VP each (``BattleIconSetPoints``). Public information only; the
    modified state is used for valuation, never given to the engine. The
    card is then both the current Conflict (the app's ``CurrentConflict``
    until cleanup) and in the winner's icon list, a mid-window state ours
    never holds, so the copy is built without ``GameState``'s zone check.
    Not mirrored: the app pays 2nd/3rd-place fixed rewards only after the
    place-1 window (ours before); Uprising's 2nd/3rd rows carry no VP or
    Influence.
    """

    state = run.ctx.state
    conflict_id = run.ctx.current_conflict_id
    if conflict_id is None:
        return run
    winner = rank_combat(state.players).winner
    if winner is None:
        return run
    player = state.players[winner]
    if conflict_id in player.won_conflict_ids:
        return run
    won = replace(player, won_conflict_ids=(*player.won_conflict_ids, conflict_id))
    sets, _ = score_battle_icons_pairs(battle_icon_list(won), include_wildcards=False)
    refs = tuple(ref for scored in sets for ref in scored.refs)
    won = replace(
        won,
        victory_points=won.victory_points + len(sets),
        face_down_battle_card_ids=(*won.face_down_battle_card_ids, *refs),
    )
    players = tuple(won if p.player_id == winner else p for p in state.players)
    app_state = copy.copy(state)
    object.__setattr__(app_state, "players", players)  # skips __post_init__
    ctx = AppContext(app_state, run.ctx.seat, run.ctx.view)
    profile = Profile(ctx, run.profile.C, run.rng)
    return DecisionRun(ctx, profile, run.legal, run.rng, run.memory)


def _reward_place(run: DecisionRun) -> int | None:
    """The seat's reward row (1, 2 or 3) in the current Conflict, if any."""

    state = run.ctx.state
    ranking = rank_combat(state.players, first_player=state.first_player)
    for reward in ranking.rewards:
        if reward.player == run.ctx.seat:
            return int(reward.rank)
    return None


def _reward_ability[A: Ability](
    run: DecisionRun, cls: type[A], accept: Callable[[A], bool] = lambda a: True
) -> A | None:
    """The reward ability of class ``cls`` the app attached for this window.

    Read from the current Conflict's reward archetype of the seat's place
    (``GenericConflictAbility/<BeginExecution>d__3`` grants the archetype's
    ``CustomAbilityIDs``, 15 §3.3); every place if the seat has none. None
    outside the catalog (expansion Conflicts): not mirrored.
    """

    conflict_id = run.ctx.current_conflict_id
    if conflict_id is None or conflict_id not in CONFLICT_ARCHETYPES:
        return None
    entities = conflict_reward_entities(conflict_id, run.ctx.choam)
    place = _reward_place(run)
    if place is not None and place <= len(entities):
        entities = (entities[place - 1],)
    for entity in entities:
        for ability in abilities_of(entity):
            if isinstance(ability, cls) and accept(ability):
                return ability
    return None


def _faction_actions(
    run: DecisionRun, action_id: str
) -> tuple[tuple[DomainAction, ...], tuple[str, ...]]:
    actions = run.by_id(action_id)
    factions = tuple(f for a in actions if (f := str_arg(a, "faction")) is not None)
    return actions, factions


# ---------------------------------------------------------------------------
# combat_intrigue
# ---------------------------------------------------------------------------


def combat_intrigue(run: DecisionRun) -> DomainAction | None:
    """``CombatPhase/<PlayCombatIntrigueCards>d__18::MoveNext @0x49f0660``.

    15 §1.3 step 8: ``SelectTargetsFrom(map, …, forced = 0)`` over the
    Combat-timed intrigue keys (``GetUsableCombatIntrigueAbilities``), valued
    by each card's ``Evaluate`` (``intrigue_play_sources(…, combat=True)``);
    ``MakeChoice``'s empty answer is ``RunCombatSelection::OnSkip`` = the pass
    (``pass_combat_intrigue``). The app's extra prompt of the last player to
    play (``LastConflictIntriguePlayer``) sees an unchanged state, so our
    engine not asking it changes nothing (plan §6).
    """

    plays = run.by_id("play_intrigue")
    sources = intrigue_play_sources(run, plays, combat=True) if plays else []
    return decide(run, sources, skip=run.first("pass_combat_intrigue"), forced=False)


# ---------------------------------------------------------------------------
# combat_reward_*
# ---------------------------------------------------------------------------


def combat_reward_optional(run: DecisionRun) -> DomainAction | None:
    """``PayAttributeToGainVPAbility`` (Pay 3/4 Spice or 6 Solari -> 1 VP).

    15 §3.4-3.5: a key of the non-forced resolution prompt only when
    ``CanBeRun`` (``Cost @0x4b72aa0``: affordable); ``Evaluate @0x4b73250``
    = 100 ("always play"). The ability is the reward archetype's whose cost
    matches our frame (``resource``, ``cost``); decline = the empty answer.
    """

    run = app_reward_run(run)
    decline = run.first("decline_combat_reward")
    pay = run.first("pay_combat_reward")
    if pay is None:
        return decline
    context = run.ctx.top_frame_context
    resource = context.get("resource")
    cost = context.get("cost")
    wanted = (cost, 0) if resource == "solari" else (0, cost)
    ability = _reward_ability(
        run,
        PayAttributeToGainVPAbility,
        lambda a: (a.solari_cost, a.spice_cost) == wanted,
    )
    if ability is None:
        return None
    p = run.profile

    def evaluate() -> tuple[float, DomainAction | None]:
        if not ability.meets_cost(p):  # CanBeRun: not offered
            return 0.0, None
        return ability.evaluate(p, Request()).value, pay

    source = Source(ability.APP_CLASS, Stage.PROMPT, (pay,), evaluate)
    return decide(run, [source], skip=decline, forced=False)


def combat_reward_spy_recall(run: DecisionRun) -> DomainAction | None:
    """``Recall2SpiesVPAbility`` (Battle for Arrakeen 1st: recall 2 spies -> 1 VP).

    15 §3.4: Optional key of the non-forced resolution prompt when ``Cost``
    holds (two spies on the board); ``Evaluate @0x4d52860`` =
    ``GetVictoryPointValue(1) + 2·RecallSpyValue`` with the two worst posts'
    spies (``GetRecallSpies(spies, 2)``). Value <= 0 -> the empty answer
    (``decline_combat_reward``). The spy targets are the seat's spies in our
    ``spy_post_ids`` order (``GetRecallSpies`` shuffles them first).
    """

    run = app_reward_run(run)
    decline = run.first("decline_combat_reward")
    pairs = run.by_id("recall_spies_for_combat_reward")
    if not pairs:
        return decline
    ability = _reward_ability(run, Recall2SpiesVPAbility)
    if ability is None:
        return None
    p = run.profile
    spies = tuple(spy_entity(post, run.ctx.seat) for post in run.ctx.me.spy_post_ids)

    def evaluate() -> tuple[float, DomainAction | None]:
        if not ability.meets_cost(p):  # CanBeRun: not offered
            return 0.0, None
        info = TargetInfo(entities=spies, min_select=2, max_select=2)
        answer = ability.evaluate(p, Request((info,)))
        if answer.response is None:
            return answer.value, None
        wanted = set(answer.response[0])
        for action in pairs:
            chosen = {
                str_arg(action, "first_post_id"),
                str_arg(action, "second_post_id"),
            }
            if chosen == wanted:
                return answer.value, action
        return answer.value, None

    source = Source(ability.APP_CLASS, Stage.PROMPT, pairs, evaluate)
    return decide(run, [source], skip=decline, forced=False)


def combat_reward_trash(run: DecisionRun) -> DomainAction | None:
    """``TrashConflictCustomAbility`` (Trade Dispute 1st and 2nd).

    15 §3.4: ``TrashAbility::SelectionMode`` Explicit -> the resolution prompt
    is **forced**; ``TrashAbility::Evaluate @0x4ce98a0`` =
    ``GetCardToTrash(targets, 1.0)``: a card at its value, or "trash nothing"
    at 1.0 (our ``decline_combat_reward_trash``). Targets in our legal order
    (hand, discard pile, cards in play); ``GetCardToTrash`` shuffles them.
    The value is always >= 1.0, so the forced fallback never fires.
    """

    run = app_reward_run(run)
    decline = run.first("decline_combat_reward_trash")
    trashes = run.by_id("trash_combat_reward_card")
    ability = _reward_ability(run, TrashConflictCustomAbility)
    if ability is None:
        return None
    p = run.profile
    cards = tuple(
        card_entity(ref, run.ctx.seat)
        for a in trashes
        if (ref := str_arg(a, "card_id")) is not None
    )

    def evaluate() -> tuple[float, DomainAction | None]:
        info = TargetInfo(entities=cards, min_select=0, max_select=1, forced=True)
        answer = ability.evaluate(p, Request((info,), forced=True))
        if answer.response is None:
            return answer.value, None
        refs = answer.response[0]
        if not refs:
            return answer.value, decline
        return answer.value, with_arg(trashes, "card_id", refs[0])

    actions = (*trashes, *(() if decline is None else (decline,)))
    source = Source(ability.APP_CLASS, Stage.PROMPT, actions, evaluate)
    return decide(run, [source], skip=None, forced=True)


def combat_reward_influence(run: DecisionRun) -> DomainAction | None:
    """``GainAnyInfluenceConflictAbility`` (Skirmish crysknife / Spice
    Freighters 1st: +1 Influence on any track).

    15 §3.4: ``CanRunImmediately @0x4cdea10`` = true -> run without a "which
    ability" question, as a forced single-key prompt answered by
    ``GainAnyInfluenceAbility::Evaluate @0x4cdc4f0``
    (``GetGainInfluenceValue(f, 1) + 100``, first strict maximum). Tracks =
    the factions our frame offers, in faction order (the app's track order
    is UNTRACED in the port).

    Sandworm (two copies, Spice Freighters: influence, pay 3 spice,
    influence, pay 3 spice in our frames): each frame is valued on the
    state as it stands, which is the app's order too.
    ``<PlayCombatResolutionIntrigueCards>d__21::MoveNext`` case 8
    (0x49f28fc-0x49f2d7d) rebuilds the candidate list on every window pass
    from ``Playmat.Abilities`` (``abilitiesContainer.children``, one
    instance per custom ability); only ``GetCombatResolutionAbilities
    @0x49e4d40`` repeats an ability per ``CustomAbilityIDs`` copy
    (``GroupBy``, 0x49e51d6-0x49e553a), and only for the non-deferred
    immediates (``b__0 @0x49e69a0``). So the immediates of one pass
    (0x49f322d-0x49f334b; ``RunDeferredAbilities`` runs each list entry
    once, ``execute @0x499e550``) hold one copy, whose ``BeginExecution``
    removes one ID (``HandleAbilityID @0x496bb00``: ``List.Remove``); the
    pay prompt follows, and the pass after the payment runs the second
    copy. Not mirrored: when no prompt key is left after the first copy
    (pay unaffordable), case 9 (0x49f3bce) drops the reward entry
    (``PlayerRewards.RemoveAt(0)``) and the app never gains the second
    Influence (its ID stays); our engine still asks the frame (forced), so
    it is answered like the first.
    """

    run = app_reward_run(run)
    choices, factions = _faction_actions(run, "choose_combat_reward_influence")
    if not choices:
        return run.first("resolve_combat_influence_without_faction")
    ability = _reward_ability(run, GainAnyInfluenceConflictAbility)
    if ability is None:
        return None
    p = run.profile
    tracks = tuple(track_entity(f) for f in factions)

    def evaluate() -> tuple[float, DomainAction | None]:
        info = TargetInfo(entities=tracks)
        answer = ability.evaluate(p, Request((info,), forced=True))
        if answer.response is None or not answer.response[0]:
            return answer.value, None
        return answer.value, with_arg(choices, "faction", answer.response[0][0])

    source = Source(ability.APP_CLASS, Stage.PROMPT, choices, evaluate)
    return decide(run, [source], skip=None, forced=True)


def combat_reward_distinct_influence(run: DecisionRun) -> DomainAction | None:
    """``GainAnyTwoInfluenceConflictAbility`` (Propaganda 1st: two tracks).

    15 §3.4 step 2: a non-deferred Combat-Resolution ability run without a
    prompt; its targets come from ``Evaluate @0x4b6f3f0`` (shuffled tracks,
    the two best by ``GetGainInfluenceValue(f, 1)``, value
    ``Math.Max(0.5, sum)`` > 0, so it is always answered). The app names
    both tracks at once; our engine asks two frames of one ``group`` (the
    first pick only records, OQ-057). The first frame computes the app
    answer, plays its first faction and keeps the second in
    ``Memory.intents[(DISTINCT_INFLUENCE_INTENT, round, seat, group)]``; the
    second frame (``chosen_factions`` set in its context) plays it. Without
    a usable intent the second frame re-evaluates the remaining tracks.

    Sandworm: ``GetCombatResolutionAbilities @0x49e4d40`` adds the ability
    once more per extra ``CustomAbilityIDs`` copy (``GroupBy``,
    0x49e51d6-0x49e553a) and the window runs the copies one after the
    other (loop 0x49f2e44-0x49f3048), each ``Evaluate`` on the state the
    previous one left. Our engine asks each copy as its own ``group`` (the
    group's first frame index), so each group gets its own intent, computed
    once the earlier group's two gains are applied.
    """

    run = app_reward_run(run)
    choices, factions = _faction_actions(run, "choose_distinct_combat_reward_influence")
    if not choices:
        return run.first("resolve_combat_influence_without_faction")
    context = run.ctx.top_frame_context
    chosen = tuple(f for f in str(context.get("chosen_factions", "")).split(",") if f)
    key = (
        DISTINCT_INFLUENCE_INTENT,
        run.ctx.round_number,
        run.ctx.seat,
        context.get("group"),
    )
    if chosen:
        plan = run.memory.intents.pop(key, None)
        if isinstance(plan, tuple) and plan[: len(chosen)] == chosen:
            for faction in plan[len(chosen) :]:
                action = with_arg(choices, "faction", faction)
                if action is not None:
                    return action
    ability = _reward_ability(run, GainAnyTwoInfluenceConflictAbility)
    if ability is None:
        return None
    tracks = tuple(track_entity(f) for f in factions)
    info = TargetInfo(entities=tracks, min_select=2, max_select=2)
    answer = ability.evaluate(run.profile, Request((info,)))
    refs = tuple(str(r) for r in answer.response[0]) if answer.response else ()
    if not refs:
        return None
    action = with_arg(choices, "faction", refs[0])
    if action is not None and not chosen and len(refs) > 1:
        run.memory.intents[key] = refs
    return action


def combat_reward_spy(run: DecisionRun) -> DomainAction | None:
    """``PlaceSpyCustomAbility`` (Seize Spice Refinery / Test of Loyalty 1st).

    15 §3.4: ``CanRunImmediately @0x4d2c330`` = ``RoundPhase == Combat`` ->
    auto-run; ``PlaceSpyAbility::Evaluate`` only says "use" (``SpyValue`` > 0)
    and the ``PlaceSpy`` action picks the post with ``PlaceSpyEvaluator``;
    with an empty supply it first recalls with ``RecallSpyEvaluator`` (08 §2,
    branch INFERRED there) and never declines (plan §5): ``spy_answer``.
    """

    run = app_reward_run(run)
    return spy_answer(
        run,
        run.by_id("place_combat_reward_spy"),
        run.by_id("recall_spy_for_combat_reward"),
        run.first("decline_combat_reward_spy"),
    )


# ---------------------------------------------------------------------------
# control_defense
# ---------------------------------------------------------------------------


def control_defense(run: DecisionRun) -> DomainAction | None:
    """``GenerateConflictPhase/<DeployControlTroops>d__8::MoveNext @0x4a013d0``.

    ``spec/engine-order.md`` §1 (state 3), R3 §7: no picker; when the
    controller's supply holds a troop the engine always runs
    ``ControlledSpaceTroop`` (gain 1 troop, deploy it). So: deploy whenever
    our engine offers it; the decline only when it is the sole answer.
    """

    return run.first("deploy_control_defense") or run.first("decline_control_defense")


# ---------------------------------------------------------------------------
# endgame_intrigue
# ---------------------------------------------------------------------------


def endgame_intrigue(run: DecisionRun) -> DomainAction | None:
    """``EndgamePhase/<PlayEndgameIntrigues>d__9::MoveNext @0x49ff320`` and the
    closing ``ScoreBattleIconsPairs(includeWildcards = true)`` (@0x4a000a2).

    ``spec/intrigues.md`` §2.3, §8: no prompt; every Endgame ability that can
    run is played (``endgame_auto_plays``: hand order), then the seat's
    battle-icon sets are scored (``endgame_wild_pairs``: the wildcard sets,
    in the app's order; natural pairs were flipped at each combat). Our
    window offers them one at a time and stays open, so: the first planned
    play our engine offers, else the first planned wild match it offers,
    else ``pass_endgame_intrigue`` (final, OQ-001). A play or match the app
    would not make is never taken. The Crysknife-family flip target is the
    ``intrigue_choice`` window's (``complete_battle_icon_pair_card``).
    """

    p = run.profile
    plays = run.by_id("play_intrigue")
    for card, _ability in endgame_auto_plays(p):
        action = with_arg(plays, "card_id", card.ref)
        if action is not None:
            return action
    matches = run.by_id("match_endgame_wild_icon")
    for matching, wild in endgame_wild_pairs(p):
        for action in matches:
            if (
                str_arg(action, "matching_card_id") == matching
                and str_arg(action, "wild_card_id") == wild
            ):
                return action
    return run.first("pass_endgame_intrigue")


HANDLERS: dict[str, Handler] = {
    "combat_intrigue": combat_intrigue,
    "combat_reward_optional": combat_reward_optional,
    "combat_reward_distinct_influence": combat_reward_distinct_influence,
    "combat_reward_influence": combat_reward_influence,
    "combat_reward_spy": combat_reward_spy,
    "combat_reward_spy_recall": combat_reward_spy_recall,
    "combat_reward_trash": combat_reward_trash,
    "control_defense": control_defense,
    "endgame_intrigue": endgame_intrigue,
}
