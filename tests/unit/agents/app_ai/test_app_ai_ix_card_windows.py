"""The windows that answer P4's Imperium batch d (plan §13): Imperial Bashar's
-OR- box, Satellite Ban's and Spice Trader's discards and Satellite Ban's
Reveal retreat, the Unload cards (Freighter Fleet, Ix-Guild Compact,
Boundless Ambition) and their Unload windows, on hand-built rows (the engine
rows are P4's ``claude/p4d-imperium-b``)."""

from collections.abc import Sequence

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.ix_imperium import (
    SatelliteBanRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.original_imperium import ScoutAbility
from dune_imperium.agents.app_ai.catalog import card_entity
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import agent_effects, reveal
from dune_imperium.agents.app_ai.windows.common import Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.config import BaseGame
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.state import GameState

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True, leader_draft=True
)
TROOP = DomainAction(action_id="resolve_agent_card_effect", actor=0)
TRASH = tuple(
    DomainAction(action_id="trash_agent_card", actor=0, arguments=(("card_id", c),))
    for c in ("player:0:starter:dagger:0", "imperium:imperial_bashar:0")
)


def _turn(short: str, rows: Sequence[DomainAction]) -> agent_effects._Turn:
    p = make_profile(first_decision("turn", config=IX))
    run = DecisionRun(p.ctx, p, tuple(rows), p.rng, Memory())
    card = card_entity(f"imperium:{short}:0", p.ctx.seat)
    return agent_effects._Turn(
        run=run,
        context={},
        card_ref=card.ref,
        card_short=short,
        card=card,
        space_id=None,
        space=None,
        leader=None,
    )


def _bashar_answer(
    monkeypatch: pytest.MonkeyPatch,
    rows: Sequence[DomainAction],
    troop: float,
    trash: float | None,
) -> DomainAction | None:
    t = _turn("imperial_bashar", rows)

    def card_to_trash(
        cards: Sequence[Entity], minimum: float
    ) -> tuple[Entity | None, float]:
        return (cards[0], trash) if trash is not None and cards else (None, 0.0)

    monkeypatch.setattr(t.p, "troop_value", lambda n, include=False: troop)
    monkeypatch.setattr(t.p, "trash_card_value", lambda: 0.0)
    monkeypatch.setattr(t.p, "card_to_trash", card_to_trash)
    agent_effects._ix_card_rows(t)
    [source] = t.sources
    assert source.label == "imperial_bashar box" and not t.unmapped
    assert source.evaluate is not None
    _value, action = source.evaluate()
    return action


def test_imperial_bashar_takes_the_troop_or_the_trash_its_ability_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ImperialBasharAgentAbility::Evaluate``: option 0 at the troop value,
    then option 1 with ``GetCardToTrash``'s card when strictly greater."""

    rows = (TROOP, *TRASH)
    assert _bashar_answer(monkeypatch, rows, 1.0, 0.5) is TROOP
    assert _bashar_answer(monkeypatch, rows, 1.0, 2.0) is TRASH[0]


def test_imperial_bashar_uses_its_key_on_nothing_without_a_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Option 1 alone at 0.5 (no card to trash), or the troop with no troop
    row (none can join): the box lapses unused."""

    assert _bashar_answer(monkeypatch, (TROOP, *TRASH), -1.0, None) is None
    assert _bashar_answer(monkeypatch, TRASH, 1.0, 0.5) is None


def test_the_bashar_rows_are_not_also_a_plain_box_or_trash() -> None:
    t = _turn("imperial_bashar", (TROOP, *TRASH))
    agent_effects._single_box(t, TROOP)
    agent_effects._card_trash(t, "imperial_bashar")
    assert not t.sources and not t.unmapped


@pytest.mark.parametrize(
    ("short", "label"),
    [
        ("satellite_ban", "satellite_ban discard"),
        ("spice_trader", "spice_trader discard"),
    ],
)
def test_satellite_ban_and_spice_trader_discard_through_their_ability(
    short: str, label: str
) -> None:
    rows = tuple(
        DomainAction(
            action_id="discard_agent_card", actor=0, arguments=(("card_id", c),)
        )
        for c in ("player:0:starter:dagger:0", "player:0:starter:dagger:1")
    )
    t = _turn(short, rows)
    agent_effects._card_discard(t, short)
    assert [s.label for s in t.sources] == [label] and not t.unmapped


def test_a_retreat_up_to_two_takes_the_cards_own_class() -> None:
    """Scout's ``ScoutAbility`` and Satellite Ban's
    ``SatelliteBanRevealAbility`` share the effect (both
    ``OptionalRetreatAbility``, MaxRetreat 2)."""

    p = make_profile(first_decision("turn", config=IX))
    run = DecisionRun(p.ctx, p, (), p.rng, Memory())
    effect = "may_retreat_up_to_two_troops"
    ban = reveal._choice_ability(run, effect, "imperium:satellite_ban:0")
    scout = reveal._choice_ability(run, effect, "imperium:scout:0")
    assert type(ban) is SatelliteBanRevealAbility
    assert type(scout) is ScoutAbility


def test_imperial_bashar_costs_a_trashable_card_or_a_supply_troop() -> None:
    """``ImperialBasharAgentAbility::Cost`` @0x4dc3c70: ``HasTrashableCard``
    or ``HasUnitsInSupply<WormTroop>.Any``."""

    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        ImperialBasharAgentAbility,
    )
    from dune_imperium.agents.app_ai.testing import ENGINE, with_player
    from dune_imperium.core.decisions import PlayerDecision

    state = first_decision("turn", config=IX)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    me = state.players[seat]
    supply = me.troops_supply
    card = card_entity("imperium:imperial_bashar:0", seat)
    held = make_profile(state, seat)
    assert ImperialBasharAgentAbility(card).meets_cost(held)
    empty = dict(hand=(), discard_pile=())
    troop_only = make_profile(with_player(state, seat, **empty), seat)
    assert ImperialBasharAgentAbility(card).meets_cost(troop_only)
    nothing = with_player(
        state,
        seat,
        **empty,
        troops_supply=0,
        troops_garrison=me.troops_garrison + supply,
    )
    assert not ImperialBasharAgentAbility(card).meets_cost(make_profile(nothing, seat))


def test_bounty_hunter_box_runs_its_ability_at_once() -> None:
    """``BountyHunterAbility``: ``AlwaysRunImmediately``, so its box is an
    automatic step, not a prompt key."""

    from dune_imperium.agents.app_ai.windows.common import Stage

    plain = DomainAction(action_id="resolve_agent_card_effect", actor=0)
    t = _turn("bounty_hunter", (plain,))
    agent_effects._single_box(t, plain)
    [source] = t.sources
    assert source.label == "bounty_hunter box" and source.stage is not Stage.PROMPT
    assert not t.unmapped


@pytest.mark.parametrize("icon", ["solari", "cards", "water"])
def test_web_of_power_icons_take_their_app_lines(icon: str) -> None:
    """``WebOfPower{Emperor,SpacingGuild,Fremen}Ability``: Wheels Within
    Wheels' shape, one app ability per Influence-2 line."""

    action = DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("effect", icon),)
    )
    t = _turn("web_of_power", (action,))
    agent_effects._box_icon(t, action, icon)
    assert [s.label for s in t.sources] == [f"web_of_power {icon}"]
    assert not t.unmapped


def test_ixian_engineer_acquires_the_tile_its_ability_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.tech import AcquireTechAbility

    row = DomainAction(action_id="acquire_agent_card_tech", actor=0)
    t = _turn("ixian_engineer", (row,))
    answers = iter((Answer(2.0, (("artillery",),), ""), Answer(0.0, None, "")))
    monkeypatch.setattr(
        AcquireTechAbility, "evaluate", lambda self, p, request: next(answers)
    )
    agent_effects._card_tech(t)
    [source] = t.sources
    assert source.label == "Card Acquire Tech" and not t.unmapped
    assert source.evaluate is not None
    assert source.evaluate() == (2.0, row)
    assert source.evaluate() == (0.0, None)


def test_web_of_power_and_ixian_engineer_reveal_choices() -> None:
    """Web of Power's mandatory Faction pick (``WebOfPowerRevealAbility``, a
    ``GainAnyInfluenceAbility``) and Ixian Engineer's self-trash for a VP
    (``IxianEngineerAbility``, E 100 with no sub-target)."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        IxianEngineerAbility,
        WebOfPowerRevealAbility,
    )

    p = make_profile(first_decision("turn", config=IX))
    gains = tuple(
        DomainAction(
            action_id="gain_reveal_influence",
            actor=0,
            arguments=(("faction", f), ("source", "web_of_power")),
        )
        for f in ("emperor", "fremen")
    )
    trash = DomainAction(action_id="trash_reveal_card", actor=0)
    run = DecisionRun(p.ctx, p, (*gains, trash), p.rng, Memory())
    web, engineer = (
        "gain_chosen_influence",
        ("may_trash_self_for_victory_point_if_three_tech_tiles"),
    )
    assert isinstance(
        reveal._choice_ability(run, web, "imperium:web_of_power:0"),
        WebOfPowerRevealAbility,
    )
    assert isinstance(
        reveal._choice_ability(run, engineer, "imperium:ixian_engineer:0"),
        IxianEngineerAbility,
    )
    picked = reveal._realise(run, web, Answer(1.0, (("fremen",),), ""))
    assert picked is gains[1]
    assert reveal._realise(run, engineer, Answer(100.0, (), "")) is trash


def test_in_the_shadows_discards_then_raises_the_track_of_one_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``InTheShadowsAgentAbility``: one answer ``((card,), (track,))``; our
    discard row takes the card and the Influence step after it the track."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        InTheShadowsAgentAbility,
    )

    discards = tuple(
        DomainAction(
            action_id="discard_agent_card", actor=0, arguments=(("card_id", c),)
        )
        for c in ("player:0:starter:dagger:0", "player:0:starter:dagger:1")
    )
    monkeypatch.setattr(
        InTheShadowsAgentAbility,
        "evaluate",
        lambda self, p, request: Answer(
            2.0, (("player:0:starter:dagger:1",), ("fremen",)), ""
        ),
    )
    t = _turn("in_the_shadows", discards)
    agent_effects._card_discard(t, "in_the_shadows")
    [source] = t.sources
    assert source.evaluate is not None
    assert source.evaluate() == (2.0, discards[1])
    gains = tuple(
        DomainAction(
            action_id="choose_agent_card_influence",
            actor=0,
            arguments=(("faction", f),),
        )
        for f in ("emperor", "fremen")
    )
    t2 = _turn("in_the_shadows", gains)
    t2.run.memory.intents.update(t.run.memory.intents)
    agent_effects._card_influence(t2, "in_the_shadows")
    [gain] = t2.sources
    assert gain.actions == (gains[1],)


def test_esmar_tuek_and_treachery_follow_their_app_classes() -> None:
    """Esmar Tuek: Spice Smugglers' shape (``EsmarTuekAbility`` pays, its
    Influence and card follow); Treachery: Power Play's generic box, and its
    Reveal deployment a state-300 gain."""

    assert agent_effects._PAYMENT_ABILITY["esmar_tuek_card"] == "EsmarTuekAbility"
    assert "esmar_tuek_card" in agent_effects._ARMED_REWARD_CARDS
    assert "esmar_tuek_card" in agent_effects._PAID_INFLUENCE_FOLLOW_UPS
    assert "treachery" in agent_effects._POWER_PLAY_CARDS
    assert "treachery" in agent_effects._AGENT_BOX_CARDS
    assert reveal._GAIN_KINDS["deploy_reveal_supply_troops"] == "deploy"


# -- Freighter Fleet, Ix-Guild Compact, Boundless Ambition ----------------------------

COMPACT = "imperium:ix_guild_compact:0"


def _row(action_id: str, **arguments: object) -> DomainAction:
    return DomainAction(
        action_id=action_id,
        actor=0,
        arguments=tuple(sorted(arguments.items())),  # type: ignore[arg-type]
    )


def _run(rows: Sequence[DomainAction]) -> DecisionRun:
    p = make_profile(first_decision("turn", config=IX))
    return DecisionRun(p.ctx, p, tuple(rows), p.rng, Memory())


def test_a_signet_box_is_read_from_the_cards_agent_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boundless Ambition's "[Signet Ring]" box uses the Leader's Signet Ring
    ability [Main p. 20]: a box is a Signet's by its card's ``LEADER_SIGNET``
    effect (P4's data for Boundless Ambition, stubbed here), not by the
    Signet Ring's name; a Ghola's box is its partner's."""

    from types import SimpleNamespace

    from dune_imperium.content.uprising.personal_cards import (
        personal_card_for_instance as lookup,
    )
    from dune_imperium.content.uprising.types import PersonalCardAgentEffect

    ambition = "imperium:boundless_ambition:0"

    def stub(ref: str) -> object:
        if ref == ambition:
            return SimpleNamespace(agent_effect=PersonalCardAgentEffect.LEADER_SIGNET)
        return lookup(ref)

    monkeypatch.setattr(agent_effects, "personal_card_for_instance", stub)
    t = _turn("boundless_ambition", ())
    assert agent_effects._signet_box(t)
    t.card_ref = "player:0:starter:signet_ring:0"
    assert agent_effects._signet_box(t)
    t.card_ref = "player:0:starter:dagger:0"
    assert not agent_effects._signet_box(t)
    t.card_ref, t.partner_ref, t.ghola = "imperium:ghola:0", ambition, True
    assert agent_effects._signet_box(t)


def test_ix_guild_compact_discards_both_cards_of_one_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``IxGuildCompactAgentAbility::Evaluate`` @0x4dcf430 names both cards
    (``GetDiscardOrder(...).Take(2)``); our engine asks one at a time, the
    first kept in ``DISCARD_FIRST_KEY``: the second is a follow-up."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        IxGuildCompactAgentAbility,
    )
    from dune_imperium.agents.app_ai.windows.common import Stage
    from dune_imperium.rules.agent_box_abilities import DISCARD_FIRST_KEY

    cards = (
        "player:0:starter:dagger:0",
        "player:0:starter:dagger:1",
        "player:0:starter:dune_the_desert_planet:0",
    )
    discards = tuple(_row("discard_agent_card", card_id=c) for c in cards)
    monkeypatch.setattr(
        IxGuildCompactAgentAbility,
        "evaluate",
        lambda self, p, request: Answer(3.0, ((cards[2], cards[0]),), ""),
    )
    t = _turn("ix_guild_compact", discards)
    agent_effects._card_discard(t, "ix_guild_compact")
    [source] = t.sources
    assert source.evaluate is not None and not t.unmapped
    assert source.evaluate() == (3.0, discards[2])
    key = agent_effects._ix_guild_compact_key(t)
    assert t.on_choose[discards[2]] == [(key, cards[0])]

    second = _turn("ix_guild_compact", discards[:2])
    second.context = {DISCARD_FIRST_KEY: cards[2]}
    second.run.memory.intents[key] = cards[0]
    agent_effects._card_discard(second, "ix_guild_compact")
    [follow] = second.sources
    assert follow.actions == (discards[0],) and follow.stage is not Stage.PROMPT
    assert key not in second.run.memory.intents


def test_the_unload_window_places_each_negotiator_the_supply_allows() -> None:
    """``UnloadAbility`` reruns Ix-Guild Compact's Reveal, which places both
    Negotiators without asking (``AddTechNegotiators(2)``): placed when
    offered, refused only when only the refusal is offered (an empty supply)."""

    from dune_imperium.agents.app_ai.windows import ix

    place = _row("resolve_unload_icon", card_id=COMPACT, effect="negotiator")
    decline = _row("decline_unload_icon", card_id=COMPACT, effect="negotiator")
    assert ix.unload_icons(_run((place, decline))) is place
    assert ix.unload_icons(_run((decline,))) is decline


def test_boundless_ambitions_unload_window_takes_its_custom_abilitys_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``BoundlessAmbitionCustomAbility``: Row then Reserve cards and the
    destination picker (option 0 the top of the deck while offered); its
    answer ``((card,), (0,))`` is taken whatever its value (our window has
    no refusal), and the fizzle's confirm when nothing is in reach."""

    from dune_imperium.agents.app_ai.abilities.base import Answer, Request
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        BoundlessAmbitionCustomAbility,
    )
    from dune_imperium.agents.app_ai.windows import ix

    run = _run(())
    first, second = run.ctx.imperium_row[:2]
    plain = tuple(
        _row(ix.ACQUIRE_UNLOAD_IMPERIUM, instance_id=r) for r in (first, second)
    )
    top = _row(ix.ACQUIRE_UNLOAD_IMPERIUM, instance_id=second, to_deck_top=True)
    reserve = _row(ix.ACQUIRE_UNLOAD_RESERVE, card_id="arrakis_liaison")
    requests: list[Request] = []

    def answer(ref: str) -> None:
        def evaluate(self: object, p: object, request: Request) -> Answer:
            requests.append(request)
            return Answer(-1.0, ((ref,), (0,)), "")

        monkeypatch.setattr(BoundlessAmbitionCustomAbility, "evaluate", evaluate)

    answer(second)
    assert ix.unload_icons(_run((*plain, top, reserve))) is top
    request = requests[-1]
    refs = [e.ref for e in request.infos[0].entities]
    assert refs == [first, second, "reserve:arrakis_liaison"]
    assert request.infos[1].options == (0, 1)
    assert ix.unload_icons(_run((*plain, reserve))) is plain[1]
    assert requests[-1].infos[1].options == (0,)
    answer("reserve:arrakis_liaison")
    assert ix.unload_icons(_run((*plain, reserve))) is reserve
    skip = _row(ix.SKIP_UNLOAD_ACQUISITION)
    assert ix.unload_icons(_run((skip,))) is skip


def test_freighter_fleets_reveal_moves_as_its_freighter_ability_answers() -> None:
    """``FreighterRevealAbility`` (``FreighterAbility::Evaluate``: ``Item1``
    1 recalls, 0 advances) over the Reveal's two rows."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_board import FreighterRevealAbility

    advance = _row("advance_reveal_freighter")
    recall = _row("recall_reveal_freighter")
    run = _run((advance, recall))
    effect = "may_move_freighter"
    ability = reveal._choice_ability(run, effect, "imperium:freighter_fleet:0")
    assert isinstance(ability, FreighterRevealAbility)
    assert reveal._realise(run, effect, Answer(1.0, ((1,),), "")) is recall
    assert reveal._realise(run, effect, Answer(1.0, ((0,),), "")) is advance
    only = _run((advance,))
    assert reveal._realise(only, effect, Answer(1.0, ((1,),), "")) is None


def test_ix_guild_compacts_reveal_negotiators_are_automatic_steps() -> None:
    """``IxGuildCompactRevealAbility`` (a state-300 ``RevealAbility``)
    places both without asking: each optional row is an automatic step."""

    from dune_imperium.agents.app_ai.windows.common import Stage

    place = _row("place_reveal_negotiator")
    run = _run((place,))
    for effect in ("may_place_two_negotiators", "may_place_negotiator"):
        entry = reveal._Entry(COMPACT, effect, (place,))
        [source] = reveal._automatic_choices(run, [entry])
        assert source.stage is Stage.REVEAL_AUTO and source.actions == (place,)


def test_boundless_ambitions_reveal_is_valued_by_its_custom_ability() -> None:
    """The Reveal's ``BoundlessAmbitionRevealAbility`` grants
    ``BoundlessAmbitionCustomAbility``, the prompt key; while the mandatory
    acquisition holds ``finish_reveal`` its own answer is the fallback of an
    End Turn (``_held_answer``): the best ``AcquireValue`` card."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        BoundlessAmbitionCustomAbility,
    )

    probe = _run(())
    refs = probe.ctx.imperium_row[:3]
    rows = tuple(_row("acquire_reveal_imperium_card", instance_id=r) for r in refs)
    run = _run(rows)
    card, effect = "imperium:boundless_ambition:0", "acquire_card_up_to_five"
    ability = reveal._choice_ability(run, effect, card)
    assert isinstance(ability, BoundlessAmbitionCustomAbility)
    request = reveal._choice_request(run, effect, card)
    assert [e.ref for e in request.infos[0].entities] == list(refs)
    picked = reveal._realise(run, effect, Answer(1.0, ((refs[1],), (0,)), ""))
    assert picked is rows[1]
    best = max(
        request.infos[0].entities, key=lambda e: run.profile.acquire_value(e).sum
    )
    held = reveal._held_answer(run, [reveal._Entry(card, effect, rows)])
    assert held is rows[list(refs).index(best.ref)]


# -- P4's last Imperium batch (P4 e3cac948) -------------------------------------------


def _in_conflict(
    state: GameState, seat: int, troops: int = 0, dreadnoughts: int = 0
) -> GameState:
    """``state`` with ``seat``'s troops and dreadnoughts moved from the supply
    into the Conflict."""

    from dune_imperium.agents.app_ai.testing import with_player

    me = state.players[seat]
    return with_player(
        state,
        seat,
        troops_supply=me.troops_supply - troops,
        troops_conflict=me.troops_conflict + troops,
        dreadnoughts_supply=me.dreadnoughts_supply - dreadnoughts,
        dreadnoughts_conflict=me.dreadnoughts_conflict + dreadnoughts,
    )


def _turn_on(
    state: GameState,
    short: str,
    rows: Sequence[DomainAction],
    context: dict[str, ActionValue] | None = None,
) -> agent_effects._Turn:
    p = make_profile(state)
    run = DecisionRun(p.ctx, p, tuple(rows), p.rng, Memory())
    card = card_entity(f"imperium:{short}:0", p.ctx.seat)
    return agent_effects._Turn(
        run=run,
        context=context or {},
        card_ref=card.ref,
        card_short=short,
        card=card,
        space_id=None,
        space=None,
        leader=None,
    )


def test_weirding_ways_extra_turn_follows_its_confirm_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``WeirdingWayAbility``: option 1 ("confirm", ``ExtraTurn``) takes the
    row; option 0 ("decline") uses the key on nothing, so it lapses."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_imperium import WeirdingWayAbility

    row = _row("take_agent_card_extra_turn")
    for option, expected in ((1, row), (0, None)):
        monkeypatch.setattr(
            WeirdingWayAbility,
            "evaluate",
            lambda self, p, request, o=option: Answer(1.0, ((o,),), ""),
        )
        t = _turn("weirding_way", (row,))
        agent_effects._ix_card_rows(t)
        [source] = [s for s in t.sources if s.label == "Weirding Way"]
        assert source.evaluate is not None and not t.unmapped
        assert source.evaluate() == (1.0, expected)


def test_embedded_agents_freighters_are_its_custom_freighter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``EmbeddedAgentAbility`` adds a ``FreighterCustomAbility`` per icon:
    each Freighter row is ``FreighterAbility::Evaluate``'s (1 recalls)."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_board import (
        FreighterCustomAbility,
    )

    advance = _row("advance_agent_card_freighter")
    recall = _row("recall_agent_card_freighter")
    monkeypatch.setattr(
        FreighterCustomAbility,
        "evaluate",
        lambda self, p, request: Answer(2.0, ((1,),), ""),
    )
    t = _turn("embedded_agent", (advance, recall))
    agent_effects._ix_card_rows(t)
    [source] = [s for s in t.sources if s.label == "Card Freighter"]
    assert source.evaluate is not None and not t.unmapped
    assert source.evaluate() == (2.0, recall)


def test_guild_chief_administrators_discard_and_trash_are_its_own() -> None:
    """The discard is ``GuildChiefAdministratorAbility``'s; the trash its box
    grants (named after the box) is its ``EvaluateTrash``."""

    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        GuildChiefAdministratorAbility,
    )
    from dune_imperium.agents.app_ai.windows import immortality

    rows = tuple(
        _row("discard_agent_card", card_id=c)
        for c in ("player:0:starter:dagger:0", "player:0:starter:dagger:1")
    )
    t = _turn("guild_chief_administrator", rows)
    agent_effects._card_discard(t, "guild_chief_administrator")
    assert [s.label for s in t.sources] == ["guild_chief_administrator discard"]
    box = "round:2:player:0:agent_card:imperium:guild_chief_administrator:0"
    assert isinstance(
        immortality._box_trash(box, 0), GuildChiefAdministratorAbility
    )
    other = "round:2:player:0:agent_card:imperium:control_the_spice:0"
    assert immortality._box_trash(other, 0) is None


def test_full_scale_assault_and_court_intrigue_boxes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full-Scale Assault's two troops are its generic box (state 500); Court
    Intrigue's arrow is ``CourtIntrigueAbility``'s Intrigue card, its draw a
    follow-up."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        CourtIntrigueAbility,
    )

    t = _turn("full_scale_assault", (TROOP,))
    agent_effects._single_box(t, TROOP)
    [box] = t.sources
    assert box.stage is not Stage.PROMPT and not t.unmapped
    puts = tuple(
        _row("put_intrigue_on_bottom_for_agent_card", intrigue_card_id=i)
        for i in ("intrigue:cull:0", "intrigue:diversion:0")
    )
    monkeypatch.setattr(
        CourtIntrigueAbility,
        "evaluate",
        lambda self, p, request: Answer(3.0, (("intrigue:diversion:0",),), ""),
    )
    t = _turn("court_intrigue", puts)
    agent_effects._card_intrigue_payment(t, "court_intrigue")
    [source] = t.sources
    assert source.evaluate is not None
    assert source.evaluate() == (3.0, puts[1])
    assert "court_intrigue" in agent_effects._ARMED_REWARD_CARDS


def test_desert_ambush_retreats_the_units_of_one_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``DesertAmbushAbility`` names every unit at once, at most the retreats
    the turn's troops still buy; our engine retreats one per row (seat and
    kind), the rest follow up."""

    from dune_imperium.agents.app_ai.abilities.base import Answer, Request
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        DesertAmbushAbility,
    )
    from dune_imperium.agents.app_ai.testing import with_player
    from dune_imperium.rules.agent_box_abilities import RETREATS_FOR_DEPLOYMENT_KEY

    state = first_decision("turn", config=IX)
    seat = make_profile(state).ctx.seat
    others = [p.player_id for p in state.players if p.player_id != seat]
    state = with_player(state, seat, units_deployed_turn=3)
    state = _in_conflict(state, others[0], troops=2)
    state = _in_conflict(state, others[1], dreadnoughts=1)
    troop = _row("retreat_opponent_troop", player=others[0])
    dreadnought = _row("retreat_opponent_troop", dreadnoughts=1, player=others[1])
    requests: list[Request] = []

    def evaluate(self: DesertAmbushAbility, p: object, request: Request) -> Answer:
        requests.append(request)
        assert sorted(self.units) == [0, 1, 2]
        return Answer(0.5, ((2, 0),), "")

    monkeypatch.setattr(DesertAmbushAbility, "evaluate", evaluate)
    context: dict[str, ActionValue] = {RETREATS_FOR_DEPLOYMENT_KEY: 1}
    t = _turn_on(state, "desert_ambush", (troop, dreadnought), context)
    agent_effects._disruption_tactics(t)
    [source] = t.sources
    assert source.evaluate is not None and not t.unmapped
    assert source.evaluate() == (0.5, dreadnought)
    assert requests[-1].infos[0].options == (0, 1, 2)
    assert requests[-1].infos[0].max_select == 2
    key = agent_effects._desert_ambush_key(t)
    assert t.on_choose[dreadnought] == [(key, ((others[0], "troop"),))]

    follow = _turn_on(state, "desert_ambush", (troop,), context)
    follow.run.memory.intents[key] = ((others[0], "troop"),)
    agent_effects._disruption_tactics(follow)
    [next_unit] = follow.sources
    assert next_unit.actions == (troop,) and next_unit.stage is not Stage.PROMPT
    assert key not in follow.run.memory.intents


def test_negotiated_withdrawal_retreats_troops_first_for_its_faction() -> None:
    """``NegotiatedWithdrawalAbility``: the Faction prompt, then the units;
    its compiled ``Evaluate`` names no unit, so ``BeginExecution`` takes the
    first three of troops-then-dreadnoughts. ``Cost``: three units in the
    Conflict and a Faction to rise on."""

    from dune_imperium.agents.app_ai.abilities.base import Answer
    from dune_imperium.agents.app_ai.abilities.ix_imperium import (
        NegotiatedWithdrawalAbility,
    )

    state = first_decision("turn", config=IX)
    seat = make_profile(state).ctx.seat
    base = state
    state = _in_conflict(base, seat, troops=2, dreadnoughts=2)
    rows = tuple(
        _row(
            "retreat_reveal_units_for_influence",
            count=3,
            faction=f,
            **({"dreadnoughts": d} if d else {}),
        )
        for f in ("emperor", "fremen")
        for d in (1, 2)
    )
    p = make_profile(state)
    run = DecisionRun(p.ctx, p, rows, p.rng, Memory())
    effect = "may_retreat_three_units_for_influence"
    card = "imperium:negotiated_withdrawal:0"
    ability = reveal._choice_ability(run, effect, card)
    assert isinstance(ability, NegotiatedWithdrawalAbility)
    request = reveal._choice_request(run, effect, card)
    assert [e.ref for e in request.infos[0].entities] == ["emperor", "fremen"]
    assert request.infos[1].options == (0, 1, 2, 3)
    assert request.infos[1].max_select == 3
    picked = reveal._realise(run, effect, Answer(1.0, (("fremen",), ()), ""))
    assert picked is rows[2]  # fremen, two troops and one dreadnought
    answer = ability.evaluate(p, request)
    assert answer.response is not None and answer.response[1] == ()
    assert ability.meets_cost(p)
    few = _in_conflict(base, seat, troops=1, dreadnoughts=1)
    assert not ability.meets_cost(make_profile(few))
