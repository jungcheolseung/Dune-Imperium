"""Bloodlines decision windows (app-style extension, docs/app-ai-plan.md §11).

The app has no Bloodlines: every window here asks a question the app never
asks, so each one is answered with the app-style ability or helper the specs
define (``docs/app-ai/bloodlines-systems.md`` §2.3, §3.4, §4, §5, §7, §8 and
``docs/app-ai/bloodlines-cards.md`` §2.8-§2.10, §7, §8), under plan §11.4
(an optional effect is used iff its value is > 0, a forced pick with nothing
> 0 is ``DefaultRandomChoice``, a forced loss takes the least loss) and the
binding decisions of plan §11.5, §11.7 and §11.8. Values come only from the
abilities and the profile; ties from ``run.rng`` (``make_choice``'s shuffle
between sources, first strictly best inside one source).

``HANDLERS`` maps each window to its handler. A legal action id a window does
not know makes the handler return None (counted fallback), never a silent
default. Every window exists only in a Bloodlines game, so nothing here runs
without the option.

- ``skill_choice`` (systems §2.3): a bank Commander's Skill (Sardaukar
  Standard) is forced: ``make_choice`` over ``SkillValue``; Plasteel Blades'
  trade (``decline_skill`` offered) is ``PlasteelBladesAbility``'s E (a Skill
  iff ``SkillValue − HeldTileValue > 0``, D10).
- ``opponent_spy_move`` (victim, D49 / cards §2.9): ``SpyMovePick`` =
  ``GetBestPost`` over the offered posts.
- ``opponent_unit_loss`` (victim, plan §11.4 / §11.8, systems §1.4): the
  smallest ``LoseUnitValue`` of the offered (zone, kind) rows, ties at
  random (``least_loss_choice``).
- ``contract_intrigue_trash`` (D52, cards §2.10): ``JunkIntriguePick``.
- ``intrigue_trigger_contract`` (Coercive Negotiation, D53):
  ``GainContractAbility.ContractEvaluate(forced)`` over the revealed tokens.
- ``navigation_setup`` (D46): slot ``i`` takes ``make_choice`` over
  ``NavigationValue(card, i, None)``; forced.
- ``navigation_choice`` (systems §5, D48): the card's ``NavigationAbility``
  E over the offered options. With ``decline_navigation`` offered (every
  playable option costs) the card is played iff the value is > 0 (card 10:
  its exchange only from 2.0, ``ChangeAllegiancesAbility``'s literal);
  without it the play is forced (nothing > 0: ``DefaultRandomChoice``). The
  follow-up answer of cards 1 and 10 is kept in ``Memory.intents``
  (``intrigue.NAVIGATION_INTENT``) for the ``intrigue_choice`` slots.
- ``tech_acquisition`` (systems §3.1, §3.4): a card's Tech Discount
  (Battlefield Research, Rapid Engineering) is
  ``AcquireTechAbilityDiscount1``'s E over the offered tiles; an empty
  answer with no ``decline_tech`` buys ``TechTileToAcquire(1)``'s tile (D13);
  Advanced Data Analysis boxes the Spy on the worst post (D14). The
  acquire-effects-only frame (a Combat purchase) resolves the first owed key
  (D15) with ``tech_acquire_effect_action``.
- ``tech_secret_project`` (D27): ``SecretProjectAbility``'s E (forced, a tile
  worth 0 included).
- ``leader_signet`` (Servo-Receivers, D54): the leader's Signet Ring as a
  single-source prompt. The Bloodlines leaders' signets are their app-style
  ``SignetAbility`` E (systems §4); the Uprising leaders' are the
  ``agent_effects`` window's own leader rows (``agent_effects`` "The
  leader"). Optional and nothing > 0: the decline; Explicit and nothing > 0:
  ``DefaultRandomChoice``.
- Ids never legal against alternatives (systems §8: ``lose_moved_spy``,
  ``resolve_commander_without_skill``, ``resolve_unit_loss_without_unit``,
  ``decline_tech`` / ``decline_navigation`` with nothing else) are taken by
  the agent as the single legal action; a window that sees one beside other
  ids follows the app engine's forced single answer.
"""

import re
from collections.abc import Callable, Sequence
from typing import Final

from dune_imperium.agents.app_ai.abilities import abilities_of
from dune_imperium.agents.app_ai.abilities import bloodlines_cards as bc
from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
    CorrinoLiaisonSignetAbility,
    FedaykinManeuverSignetAbility,
    GeneLockedVaultAcquiredAbility,
    IntoTheFraySignetAbility,
    ListenersSignetAbility,
    NavigationAbility,
    PlasteelBladesAbility,
    ReverseEngineeringSignetAbility,
    SecretProjectAbility,
    SmuggleSpiceSignetAbility,
    navigation_one_faction,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    contract_evaluate,
)
from dune_imperium.agents.app_ai.abilities.tech import (
    AcquireTechAbilityDiscount1,
    MemocordersAcquiredAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    CONTRACT_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    LEADER_ARCHETYPES,
    NAVIGATION_ARCHETYPES,
    SKILL_ARCHETYPES,
    TECH_ARCHETYPES,
    card_entity,
    contract_entity,
    intrigue_entity,
    leader_entity,
    navigation_entity,
    post_entity,
    skill_entity,
    skill_id_of,
    space_entity,
    tech_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, card_id
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile.bloodlines import navigation_number
from dune_imperium.agents.app_ai.windows import agent_effects
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
from dune_imperium.agents.app_ai.windows.intrigue import NAVIGATION_INTENT
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler, arg
from dune_imperium.agents.app_ai.windows.turn import board_space_order
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.unit_loss import UNIT_LOSS_CANDIDATES

#: The owner of the abilities the app builds at run time (a card-granted
#: ``AcquireTechAbilityDiscount1``, the playmat): no hook reads it.
_RUNTIME_OWNER: Final = Entity(Kind.LEADER, "playmat")

#: Navigation card numbers whose follow-up an intent carries.
_NAV_ONE_FACTION: Final = 1
_NAV_EXCHANGE: Final = 10
#: Navigation card 1's printed "where you have 2 Influence (or more)".
_NAV_ONE_MIN_OWN: Final = 2

#: ``resolve_tech_acquire_effect``'s ``intrigue_or_card`` choices by
#: ``GeneLockedVaultAcquiredAbility`` branch.
_GENE_LOCKED_CHOICE: Final = {
    GeneLockedVaultAcquiredAbility.INTRIGUE: "intrigue",
    GeneLockedVaultAcquiredAbility.CARD: "card",
}
#: The acquire keys systems §3.1 resolves with no question (one variant each;
#: their follow-ups have windows of their own), and the deep-cover Spy keys.
_PLAIN_ACQUIRE_KEYS: Final = frozenset(
    {
        "solari",
        "troops",
        "intrigue",
        "cards",
        "victory_points",
        "contracts",
        "signet",
        "trash",
    }
)
_SPY_ACQUIRE_KEY: Final = re.compile(r"spy_\d+")

#: The Bloodlines leaders whose Signet Ring asks a choice (systems §4);
#: Piter's and Liet's run by themselves (no decision).
_BLOODLINES_SIGNETS: Final = frozenset(
    {
        "chani",
        "count_hasimir_fenring",
        "duncan_idaho",
        "esmar_tuek",
        "gaius_helen_mohiam",
        "kota_odax_of_ix",
    }
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _known_only(run: DecisionRun, ids: frozenset[str]) -> bool:
    """Every legal id is one this window maps (else: not mirrored)."""

    return all(action.action_id in ids for action in run.legal)


def _ability[A: Ability](owner: Entity, cls: type[A]) -> A | None:
    """The first ability of ``owner`` that is a ``cls`` port."""

    for ability in abilities_of(owner):
        if isinstance(ability, cls):
            return ability
    return None


def _first_ref(answer: Answer, index: int = 0) -> str | int | None:
    """The first ref of response item ``index``, if any."""

    if answer.response is None or len(answer.response) <= index:
        return None
    item = answer.response[index]
    return item[0] if item else None


def _refs(actions: Sequence[DomainAction], name: str) -> list[str]:
    """The string argument ``name`` of each action, first-seen order."""

    seen: dict[str, None] = {}
    for action in actions:
        value = str_arg(action, name)
        if value is not None:
            seen.setdefault(value, None)
    return list(seen)


def _forced_one_source(
    run: DecisionRun,
    label: str,
    actions: Sequence[DomainAction],
    answer: Callable[[], tuple[float, DomainAction | None]],
) -> DomainAction | None:
    """A forced prompt with one source (``uprising._one_source``'s rule).

    The source's answer counts only when its value is > 0; otherwise
    ``DefaultRandomChoice`` picks among every action of the window ("a
    random key with random legal targets", engine-order §0).
    """

    def evaluate() -> tuple[float, DomainAction | None]:
        value, action = answer()
        return value, (action if value > 0.0 else None)

    source = Source(label, Stage.PROMPT, tuple(actions), evaluate)
    return decide(run, [source], skip=None, forced=True)


# ---------------------------------------------------------------------------
# skill_choice (systems §2.3)
# ---------------------------------------------------------------------------

_SKILL_IDS: Final = frozenset(
    {"choose_skill", "decline_skill", "resolve_commander_without_skill"}
)


def skill_choice(run: DecisionRun) -> DomainAction | None:
    """A Skill for a Commander gained by a card effect, or Plasteel Blades.

    Sardaukar Standard's bank Commander (forced): plan §11.4 "여러 보기 중
    하나": one source per offered Skill at ``SkillValue`` (``make_choice``;
    nothing > 0: ``DefaultRandomChoice``). Plasteel Blades (``decline_skill``
    offered): ``PlasteelBladesAbility``'s E over the offered Skills (stack
    order): its Skill, or the decline (keep the tile).
    """

    if not _known_only(run, _SKILL_IDS):
        return None
    chooses = run.by_id("choose_skill")
    decline = run.first("decline_skill")
    if not chooses:
        return decline or run.first("resolve_commander_without_skill")
    skill_ids = [s for s in _refs(chooses, "skill_id") if s in SKILL_ARCHETYPES]
    if len(skill_ids) != len(chooses):
        return None  # a Skill outside the catalog: not mirrored
    p = run.profile
    seat = run.ctx.seat
    if decline is not None:
        ability = _ability(tech_entity("plasteel_blades", seat), PlasteelBladesAbility)
        if ability is None:
            return None
        skills = tuple(skill_entity(s, seat) for s in skill_ids)
        answer = ability.evaluate(p, Request((TargetInfo(entities=skills),)))
        ref = _first_ref(answer)
        if not isinstance(ref, str) or answer.value <= 0.0:
            return decline
        return with_arg(chooses, "skill_id", skill_id_of(ref))

    def valued(skill_id: str, action: DomainAction) -> Source:
        return Source(
            f"Skill {skill_id}",
            Stage.PROMPT,
            (action,),
            lambda: (p.skill_value(skill_id), action),
        )

    sources = [
        valued(skill_id, action)
        for skill_id, action in zip(skill_ids, chooses, strict=True)
    ]
    return decide(run, sources, skip=None, forced=True)


# ---------------------------------------------------------------------------
# opponent_spy_move / opponent_unit_loss (the victim's forced losses)
# ---------------------------------------------------------------------------


def opponent_spy_move(run: DecisionRun) -> DomainAction | None:
    """The victim's forced Spy move (Holy War, False Orders; D49).

    ``SpyMovePick`` (cards §2.9): the offered post ``GetBestPost`` ranks
    first (``PostValue`` ignores who else watches, D50). ``lose_moved_spy``
    is only ever offered alone (OQ-065).
    """

    if not _known_only(run, frozenset({"move_spy", "lose_moved_spy"})):
        return None
    moves = run.by_id("move_spy")
    if not moves:
        return run.first("lose_moved_spy")
    posts = [post_entity(post, run.ctx.seat) for post in _refs(moves, "post_id")]
    pick = bc.spy_move_pick(run.profile, posts)
    return None if pick is None else with_arg(moves, "post_id", pick.ref)


def opponent_unit_loss(run: DecisionRun) -> DomainAction | None:
    """The victim's forced unit loss (Holy War; plan §11.4 "강제 손실").

    Systems §1.4 / plan §11.8: the offered (zone, kind) with the smallest
    ``LoseUnitValue`` (a garrison troop ``troop_value(1)``, a garrison
    Commander ``CommanderUnitValue``, a Conflict unit ``strength_value(2)``
    plus the Skills the last Commander there carries, less Chani's Tactics
    step), in ``UNIT_LOSS_CANDIDATES`` order, ties at random
    (``least_loss_choice``). ``resolve_unit_loss_without_unit`` is only ever
    offered alone.
    """

    ids = frozenset({"lose_unit", "resolve_unit_loss_without_unit"})
    if not _known_only(run, ids):
        return None
    losses = run.by_id("lose_unit")
    if not losses:
        return run.first("resolve_unit_loss_without_unit")
    rows: list[tuple[int, tuple[str, bool], DomainAction]] = []
    for action in losses:
        zone = str_arg(action, "zone")
        option = (zone or "", int_arg(action, "commanders") == 1)
        if option not in UNIT_LOSS_CANDIDATES:
            return None
        rows.append((UNIT_LOSS_CANDIDATES.index(option), option, action))
    rows.sort(key=lambda row: row[0])
    p = run.profile
    values = [p.lose_unit_value(zone, commander) for _, (zone, commander), _ in rows]
    return rows[p.least_loss_choice(values)][2]


# ---------------------------------------------------------------------------
# Contracts: the Immediate token's Intrigue, Coercive Negotiation's reveal
# ---------------------------------------------------------------------------


def contract_intrigue_trash(run: DecisionRun) -> DomainAction | None:
    """The Bloodlines Immediate token: which held Intrigue to trash (D52).

    ``JunkIntriguePick`` (``BranchingPathAbility::Evaluate``): the offered
    Intrigues shuffled, a junk one (``IsBadIntrigue``) first. Forced.
    """

    if not _known_only(run, frozenset({"trash_intrigue_for_contract"})):
        return None
    trashes = run.by_id("trash_intrigue_for_contract")
    refs = _refs(trashes, "card_id")
    if any(card_id(ref) not in INTRIGUE_ARCHETYPES for ref in refs):
        return None
    intrigues = [intrigue_entity(ref, run.ctx.seat) for ref in refs]
    pick = bc.junk_intrigue_pick(run.profile, intrigues)
    return None if pick is None else with_arg(trashes, "card_id", pick.ref)


def intrigue_trigger_contract(run: DecisionRun) -> DomainAction | None:
    """Coercive Negotiation's revealed tokens: which one to take (D53).

    ``GainContractAbility.ContractEvaluate(forced = true)`` =
    ``GetBestContract`` over the takeable tokens in bank order (a forced pick
    worth <= 0 is reported at 1.0, so it always answers).
    """

    if not _known_only(run, frozenset({"take_trigger_contract"})):
        return None
    takes = run.by_id("take_trigger_contract")
    refs = _refs(takes, "instance_id")
    if any(card_id(ref) not in CONTRACT_ARCHETYPES for ref in refs):
        return None
    contracts = tuple(contract_entity(ref, run.ctx.seat) for ref in refs)
    info = TargetInfo(entities=contracts, min_select=1, max_select=1, forced=True)
    request = Request(infos=(info,), forced=True)
    p = run.profile

    def answer() -> tuple[float, DomainAction | None]:
        app = contract_evaluate(p, request, True)
        ref = _first_ref(app)
        chosen = with_arg(takes, "instance_id", ref) if isinstance(ref, str) else None
        return app.value, chosen

    return _forced_one_source(run, "GainContract", takes, answer)


# ---------------------------------------------------------------------------
# Navigation (Steersman Y'rkoon; systems §5)
# ---------------------------------------------------------------------------


def navigation_setup(run: DecisionRun) -> DomainAction | None:
    """Plot Course setup: the card for the next slot (D46).

    Slot ``i`` = the seat's own filled slots + 1 (left to right). One source
    per card in hand at ``NavigationValue(card, i, None)`` (every trigger-,
    alliance- and influence-conditional part 0: "as now", plan §11.4);
    forced, so nothing > 0 is ``DefaultRandomChoice``.
    """

    if not _known_only(run, frozenset({"place_navigation_card"})):
        return None
    places = run.by_id("place_navigation_card")
    refs = _refs(places, "card_id")
    if any(card_id(ref) not in NAVIGATION_ARCHETYPES for ref in refs):
        return None
    slot = len(run.ctx.navigation_slots) + 1
    p = run.profile

    def valued(ref: str, action: DomainAction) -> Source:
        return Source(
            f"Navigation {ref} slot {slot}",
            Stage.PROMPT,
            (action,),
            lambda: (p.navigation_value(navigation_number(ref), slot, None), action),
        )

    sources = [valued(ref, action) for ref, action in zip(refs, places, strict=True)]
    return decide(run, sources, skip=None, forced=True)


def navigation_choice(run: DecisionRun) -> DomainAction | None:
    """Plot Course: which option of the slot's card to play (systems §5).

    The card's ``NavigationAbility`` E over the offered ``play_navigation``
    options (the first strictly best ``OptionValue`` with the real slot and
    trigger). ``decline_navigation`` beside them (every playable option
    costs) makes the prompt optional: play iff the value is > 0 (card 10:
    the exchange counts only from 2.0, D48), else decline. Without it the
    prompt is forced: nothing > 0 is ``DefaultRandomChoice``. The play keeps
    the follow-up answer of card 1 (the Faction to gain, chosen on the state
    the option was valued on) and card 10 (the Faction the exchange loses)
    in ``Memory.intents[(NAVIGATION_INTENT, card)]``.
    """

    if not _known_only(run, frozenset({"play_navigation", "decline_navigation"})):
        return None
    plays = run.by_id("play_navigation")
    decline = run.first("decline_navigation")
    if not plays:
        return decline
    instance = run.ctx.top_frame_context.get("card_id")
    if not isinstance(instance, str) or card_id(instance) not in NAVIGATION_ARCHETYPES:
        return None
    ability = _ability(navigation_entity(instance, run.ctx.seat), NavigationAbility)
    if ability is None:
        return None
    options = tuple(o for a in plays if (o := int_arg(a, "option")) is not None)
    p = run.profile
    request = Request((TargetInfo(options=options),))

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(p, request)
        option = _first_ref(answer)
        action = with_arg(plays, "option", option) if answer.value > 0.0 else None
        return answer.value, action

    source = Source(f"Navigation {instance}", Stage.PROMPT, tuple(plays), evaluate)
    chosen = decide(run, [source], skip=decline, forced=decline is None)
    if chosen is not None and chosen.action_id == "play_navigation":
        _store_navigation_intent(run, instance, ability.card_number, chosen)
    return chosen


def _store_navigation_intent(
    run: DecisionRun, instance: str, number: int, chosen: DomainAction
) -> None:
    """The follow-up answer of the played option (systems §5 "Follow-ups").

    Kept only when the follow-up slot will ask (two Factions or more to
    choose from: ``influence_gain_candidates`` for card 1, the Factions with
    Influence to lose for card 10); a single candidate is taken by the agent
    without a window, so the intent would never be read and dropped.
    """

    key = (NAVIGATION_INTENT, instance)
    run.memory.intents.pop(key, None)
    p = run.profile
    me = run.ctx.me
    trigger = run.ctx.navigation_trigger_faction or None
    if number == _NAV_ONE_FACTION and int_arg(chosen, "option") == 1:
        offered = [
            f
            for f in FACTIONS
            if f != trigger and int(getattr(me.influence, f)) >= _NAV_ONE_MIN_OWN
        ]
        faction = navigation_one_faction(p, offered, trigger)
        if faction is not None and len(offered) > 1:
            run.memory.intents[key] = faction
    elif number == _NAV_EXCHANGE:
        lose, _gain, _value = p.best_influence_exchange(-1, 1)
        losable = [f for f in FACTIONS if int(getattr(me.influence, f)) >= 1]
        if lose is not None and len(losable) > 1:
            run.memory.intents[key] = lose


# ---------------------------------------------------------------------------
# Tech (systems §3.1, §3.4)
# ---------------------------------------------------------------------------

_TECH_IDS: Final = frozenset(
    {"acquire_tech", "decline_tech", "resolve_tech_acquire_effect"}
)


def tech_acquisition(run: DecisionRun) -> DomainAction | None:
    """A card-granted Acquire Tech, or a Combat purchase's acquire icons.

    Tech Discount 1 (Battlefield Research, Rapid Engineering):
    ``AcquireTechAbilityDiscount1::Evaluate`` over the offered tiles (stack
    order, then the Secret Project): the first strictly best tile worth > 0,
    else the empty answer (0.5). Our engine forces the purchase while a tile
    is affordable (no ``decline_tech``): the empty answer then buys
    ``TechTileToAcquire(1)``'s tile (D13). The acquire-effects-only frame:
    ``tech_acquire_effect_action``.
    """

    if not _known_only(run, _TECH_IDS):
        return None
    resolves = run.by_id("resolve_tech_acquire_effect")
    if resolves:
        if len(resolves) != len(run.legal):
            return None
        return tech_acquire_effect_action(run, resolves)
    acquires = run.by_id("acquire_tech")
    decline = run.first("decline_tech")
    if not acquires:
        return decline
    if run.ctx.top_frame_context.get("discount") != (
        AcquireTechAbilityDiscount1.tech_discount
    ):
        return None  # no app-style source for another discount
    tech_ids = _refs(acquires, "tech_id")
    if any(t not in TECH_ARCHETYPES for t in tech_ids):
        return None
    p = run.profile
    tiles = tuple(tech_entity(t, run.ctx.seat) for t in tech_ids)
    ability = AcquireTechAbilityDiscount1(_RUNTIME_OWNER)
    answer = ability.evaluate(p, Request((TargetInfo(entities=tiles),)))
    ref = _first_ref(answer)
    tile: str | None = ref if isinstance(ref, str) and answer.value > 0.0 else None
    if tile is None:
        if decline is not None:
            return decline  # the empty answer: acquire nothing
        best = p.tech_tile_to_acquire(1, False)  # D13: forced
        tile = None if best is None else best.ref
    if tile is None or tile not in tech_ids:
        return _forced_one_source(run, "Acquire Tech", acquires, lambda: (0.0, None))
    return _tile_action(run, acquires, tile)


def _tile_action(
    run: DecisionRun, acquires: Sequence[DomainAction], tech_id: str
) -> DomainAction | None:
    """``acquire_tech`` of ``tech_id``; Advanced Data Analysis boxes the Spy
    ``GetRecallSpy`` names (the one on the worst post, D14)."""

    variants = [a for a in acquires if str_arg(a, "tech_id") == tech_id]
    if len(variants) <= 1:
        return variants[0] if variants else None
    return worst_recall_action(run, variants)


def tech_acquire_effect_action(
    run: DecisionRun, resolves: Sequence[DomainAction]
) -> DomainAction | None:
    """One owed Tech acquire icon (systems §3.1 key table, D15).

    The first owed key in the engine's order (``acquire_effect_keys`` per
    purchase: the legal list follows it) is resolved: ``influence`` by
    ``MemocordersAcquiredAbility``'s E (``G(F, +1) + 100``, first strictly
    best in Faction order), ``intrigue_or_card`` by
    ``GeneLockedVaultAcquiredAbility``'s E, ``shield_wall`` destroys the Wall
    iff that variant is legal and ``ShouldBlowWall`` (D20); every other key
    has a single variant. Shared with any window that offers the keys.
    """

    if not resolves:
        return None
    first = resolves[0]
    effect = str_arg(first, "effect")
    tech_id = str_arg(first, "tech_id")
    if effect is None or tech_id is None or tech_id not in TECH_ARCHETYPES:
        return None
    # A key owed twice (Ornithopter Fleet's two troops) is offered twice.
    variants = list(
        dict.fromkeys(
            a
            for a in resolves
            if str_arg(a, "effect") == effect and str_arg(a, "tech_id") == tech_id
        )
    )
    p = run.profile
    tile = tech_entity(tech_id, run.ctx.seat)
    if effect == "influence":
        memocorders = _ability(tile, MemocordersAcquiredAbility)
        if memocorders is None:
            return None
        offered = set(_refs(variants, "faction"))
        tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
        answer = memocorders.evaluate(p, Request((TargetInfo(entities=tracks),)))
        return with_arg(variants, "faction", _first_ref(answer))
    if effect == "intrigue_or_card":
        vault = _ability(tile, GeneLockedVaultAcquiredAbility)
        if vault is None:
            return None
        branch = _first_ref(vault.evaluate(p, Request()))
        choice = _GENE_LOCKED_CHOICE.get(branch) if isinstance(branch, int) else None
        return with_arg(variants, "choice", choice)
    if effect == "shield_wall":
        destroy = with_arg(variants, "destroy_shield_wall", True)
        plain = next(
            (a for a in variants if arg(a, "destroy_shield_wall") is None), None
        )
        if destroy is not None and p.should_blow_wall():
            return destroy
        return plain
    if effect not in _PLAIN_ACQUIRE_KEYS and not _SPY_ACQUIRE_KEY.fullmatch(effect):
        return None  # a key the §3.1 table does not name: not mirrored
    return variants[0] if len(variants) == 1 else None


def tech_secret_project(run: DecisionRun) -> DomainAction | None:
    """Kota's Secret Project at game start (D27).

    ``SecretProjectAbility``'s E over the offered bottom tiles (stack order):
    the first tile of the descending ``AcquireValue`` order, taken whatever
    its value (forced; the Early arc zeroes most tiles).
    """

    if not _known_only(run, frozenset({"choose_secret_project"})):
        return None
    chooses = run.by_id("choose_secret_project")
    tech_ids = _refs(chooses, "tech_id")
    if any(t not in TECH_ARCHETYPES for t in tech_ids):
        return None
    ability = _ability(leader_entity("kota_odax_of_ix"), SecretProjectAbility)
    if ability is None:
        return None
    tiles = tuple(tech_entity(t, run.ctx.seat) for t in tech_ids)
    answer = ability.evaluate(run.profile, Request((TargetInfo(entities=tiles),)))
    ref = _first_ref(answer)
    chosen = with_arg(chooses, "tech_id", ref) if isinstance(ref, str) else None
    if chosen is not None:
        return chosen
    return _forced_one_source(run, "Secret Project", chooses, lambda: (0.0, None))


# ---------------------------------------------------------------------------
# leader_signet (Servo-Receivers' Signet Ring use; D54)
# ---------------------------------------------------------------------------

_SIGNET_IDS: Final = frozenset(
    {
        "decline_leader_signet_payment",
        "retreat_leader_troops",
        "pay_leader_signet_water",
        "trash_leader_card",
        "place_leader_spy",
        "recall_spy_for_leader_placement",
        "decline_leader_spy_placement",
        "deploy_leader_agent",
        "place_leader_bonus_spice",
        "take_leader_bonus_spice",
        "pay_leader_signet_spice",
        "gain_leader_signet_spice",
        "trash_leader_tech",
    }
)


def leader_signet(run: DecisionRun) -> DomainAction | None:
    """The leader's Signet Ring outside the Agent box (D54).

    A single-source prompt: the leader's ``SignetAbility`` E. Bloodlines
    leaders: their app-style signet (systems §4). Uprising leaders: the
    ``agent_effects`` window's leader rows (the same sources the Signet Ring
    box offers), with the decline as the empty answer of an Optional key
    and ``DefaultRandomChoice`` for an Explicit one.
    """

    leader_id = run.ctx.me.leader_id
    if leader_id is None or leader_id not in LEADER_ARCHETYPES:
        return None
    if leader_id in _BLOODLINES_SIGNETS:
        if not _known_only(run, _SIGNET_IDS):
            return None
        return _bloodlines_signet(run, leader_id)
    return _uprising_signet(run)


def _uprising_signet(run: DecisionRun) -> DomainAction | None:
    t = agent_effects._turn(run)
    agent_effects._leader_choices(t)
    if t.unmapped:
        return None
    # A spy key's refusal (``decline_leader_spy_placement``, offered beside
    # the recall-first rows when the supply is empty: Margot's Arrakis
    # Informant, Staban's Unseen Network, Feyd's track Spy) is that key's
    # empty answer: the leader rows realise the key with ``spy_answer``,
    # which recalls the worst-post Spy rather than decline, and an Explicit
    # key forces the prompt.
    spy_decline = run.first("decline_leader_spy_placement")
    declines = (
        *t.declines,
        *t.chores,
        *((spy_decline,) if spy_decline is not None else ()),
    )
    covered = {a for s in t.sources for a in s.actions}
    covered.update(declines)
    # An automatic source (the rest of an answer already given, e.g. the
    # Spy placed after a recall-first: ``PlaceSpyEvaluator`` over every
    # offered post) ranked every row of its action ids.
    answered = {
        a.action_id for s in t.sources if s.stage < Stage.PROMPT for a in s.actions
    }
    covered.update(a for a in run.legal if a.action_id in answered)
    if any(a not in covered for a in run.legal):
        return None  # a legal row the leader's sources do not rank
    skip = next(iter(declines), None)
    forced = agent_effects._explicit_pending(t.sources) or skip is None
    return decide(run, t.sources, skip=skip, forced=forced)


def _signet_prompt(
    run: DecisionRun,
    label: str,
    ability: DeferredAbility,
    request: Request,
    realise: Callable[[Answer], DomainAction | None],
    decline: DomainAction | None,
) -> DomainAction | None:
    """One signet key: its E realised by ``realise``; Optional keys decline
    on nothing > 0, Explicit ones fall to ``DefaultRandomChoice``."""

    p = run.profile
    explicit = ability.selection_mode(p) is SelectionMode.EXPLICIT

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(p, request)
        if answer.response is None or answer.value <= 0.0:
            return answer.value, None
        return answer.value, realise(answer)

    actions = tuple(a for a in run.legal if a != decline)
    source = Source(label, Stage.PROMPT, actions, evaluate)
    forced = explicit or decline is None
    return decide(run, [source], skip=None if forced else decline, forced=forced)


def _bloodlines_signet(run: DecisionRun, leader_id: str) -> DomainAction | None:
    p = run.profile
    seat = run.ctx.seat
    leader = leader_entity(leader_id)
    decline = run.first("decline_leader_signet_payment")
    context = run.ctx.top_frame_context
    place = run.by_id("place_leader_spy")
    recall = run.by_id("recall_spy_for_leader_placement")
    if context.get("leader_spy_recalled") is True and place:
        # The recall-first began the Spy half: the rest of the app's single
        # ``PlaceSpy`` (``PlaceSpyEvaluator`` over the offered posts).
        return best_place_action(run, place)
    if leader_id == "chani":
        fedaykin = _ability(leader, FedaykinManeuverSignetAbility)
        if fedaykin is None:
            return None
        retreats = run.by_id("retreat_leader_troops")
        water = run.first("pay_leader_signet_water")
        counts = sorted({n for a in retreats if (n := int_arg(a, "count")) is not None})
        branches = (
            *((fedaykin.RETREAT,) if retreats else ()),
            *((fedaykin.WATER,) if water is not None else ()),
        )
        request = Request(
            (TargetInfo(options=branches), TargetInfo(options=tuple(counts)))
        )

        def chani(answer: Answer) -> DomainAction | None:
            if _first_ref(answer) == fedaykin.WATER:
                return water
            count = _first_ref(answer, 1)
            if not isinstance(count, int):
                return None
            commanders = p.retreat_split(count)[1]
            for action in retreats:
                if (
                    int_arg(action, "count") == count
                    and (int_arg(action, "commanders") or 0) == commanders
                ):
                    return action
            return None

        return _signet_prompt(
            run, "Fedaykin Maneuver", fedaykin, request, chani, decline
        )
    if leader_id == "count_hasimir_fenring":
        liaison = _ability(leader, CorrinoLiaisonSignetAbility)
        if liaison is None:
            return None
        trashes = run.by_id("trash_leader_card")
        cards = tuple(card_entity(ref, seat) for ref in _refs(trashes, "card_id"))
        branches = (
            *((liaison.TRASH,) if trashes else ()),
            *((liaison.SPY,) if place or recall else ()),
        )
        request = Request((TargetInfo(options=branches), TargetInfo(entities=cards)))

        def fenring(answer: Answer) -> DomainAction | None:
            if _first_ref(answer) == liaison.SPY:
                return spy_answer(run, place, recall, None)
            return with_arg(trashes, "card_id", _first_ref(answer, 1))

        return _signet_prompt(
            run, "Corrino Liaison", liaison, request, fenring, decline
        )
    if leader_id == "duncan_idaho":
        fray = _ability(leader, IntoTheFraySignetAbility)
        deploy = run.first("deploy_leader_agent")
        if fray is None:
            return None
        if deploy is None:
            return decline
        return _signet_prompt(
            run, "Into the Fray", fray, Request(), lambda _a: deploy, decline
        )
    if leader_id == "esmar_tuek":
        smuggle = _ability(leader, SmuggleSpiceSignetAbility)
        if smuggle is None:
            return None
        takes = run.by_id("take_leader_bonus_spice")
        place_bonus = run.first("place_leader_bonus_spice")
        order = {s: i for i, s in enumerate(board_space_order(run.ctx.board))}
        space_ids = sorted(
            _refs(takes, "space_id"), key=lambda s: order.get(s, len(order))
        )
        spaces = tuple(space_entity(s, run.ctx.board) for s in space_ids)
        branches = (
            *((smuggle.PLACE,) if place_bonus is not None else ()),
            *((smuggle.TAKE,) if takes else ()),
        )
        request = Request((TargetInfo(options=branches), TargetInfo(entities=spaces)))

        def esmar(answer: Answer) -> DomainAction | None:
            if _first_ref(answer) == smuggle.PLACE:
                return place_bonus
            return with_arg(takes, "space_id", _first_ref(answer, 1))

        return _signet_prompt(run, "Smuggle Spice", smuggle, request, esmar, decline)
    if leader_id == "gaius_helen_mohiam":
        listeners = _ability(leader, ListenersSignetAbility)
        if listeners is None:
            return None
        pay = run.first("pay_leader_signet_spice")
        spy_decline = run.first("decline_leader_spy_placement")
        if context.get("listeners_paid") is True:
            # The paid half's Spy: ``GetBestPost`` over every offered post.
            return spy_answer(run, place, recall, spy_decline)
        branches = (
            *((listeners.LANDSRAAD,) if place or recall else ()),
            *((listeners.PAY,) if pay is not None else ()),
        )
        request = Request((TargetInfo(options=branches),))

        def mohiam(answer: Answer) -> DomainAction | None:
            if _first_ref(answer) == listeners.PAY:
                return pay
            return spy_answer(run, place, recall, None)

        return _signet_prompt(run, "Listeners", listeners, request, mohiam, decline)
    if leader_id == "kota_odax_of_ix":
        reverse = _ability(leader, ReverseEngineeringSignetAbility)
        if reverse is None:
            return None
        spice = run.first("gain_leader_signet_spice")
        trashes = run.by_id("trash_leader_tech")
        tech_ids = _refs(trashes, "tech_id")
        if any(t not in TECH_ARCHETYPES for t in tech_ids):
            return None  # a tile with no archetype: not mirrored
        tiles = tuple(tech_entity(t, seat) for t in tech_ids)
        branches = (
            *((reverse.SPICE,) if spice is not None else ()),
            *((reverse.TRASH,) if tiles else ()),
        )
        request = Request((TargetInfo(options=branches), TargetInfo(entities=tiles)))

        def kota(answer: Answer) -> DomainAction | None:
            if _first_ref(answer) == reverse.SPICE:
                return spice
            return with_arg(trashes, "tech_id", _first_ref(answer, 1))

        return _signet_prompt(
            run, "Reverse Engineering", reverse, request, kota, decline
        )
    return None


HANDLERS: dict[str, Handler] = {
    "skill_choice": skill_choice,
    "opponent_spy_move": opponent_spy_move,
    "opponent_unit_loss": opponent_unit_loss,
    "contract_intrigue_trash": contract_intrigue_trash,
    "intrigue_trigger_contract": intrigue_trigger_contract,
    "navigation_setup": navigation_setup,
    "navigation_choice": navigation_choice,
    "tech_acquisition": tech_acquisition,
    "tech_secret_project": tech_secret_project,
    "leader_signet": leader_signet,
}

__all__ = ["HANDLERS", "tech_acquire_effect_action"]
