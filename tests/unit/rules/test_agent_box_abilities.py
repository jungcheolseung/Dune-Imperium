"""Agent boxes resolved from ability records (composed effects, stage A2).

docs/composed-effects-plan.md 5 (A2, A3): personal-card Agent boxes are
written as records (``content.uprising.agent_abilities``) and resolved by
``rules.agent_box_abilities``. The engine equivalence gate holds the move to
the old engine game by game; these tests pin the record table and the
conventions a later edit could break.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.immortality.board import (
    RESEARCH_START_ID,
    TLEILAXU_TRACK_END,
)
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.agent_abilities import AGENT_BOX_ABILITIES
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    AtMakerSpace,
    CompleteContract,
    DiscardedCardHasFaction,
    DiscardFromHand,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    GainedSpiceThisTurn,
    GainInfluence,
    GraftedWithFaction,
    HasAlliance,
    InfluenceAtLeast,
    PayResources,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecallAgent,
    RecruitTroops,
    TrashCard,
    TrashedCardHasFaction,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.display.effect_dsl_text import condition_text, cost_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import (
    condition_text_ko,
    cost_text_ko,
    reward_text_ko,
)
from dune_imperium.display.tokens import AGENT_EFFECT_TEXT
from dune_imperium.display.tokens_ko import AGENT_EFFECT_TEXT_KO
from dune_imperium.rules.acquisition import agent_box_acquisition
from dune_imperium.rules.agent_box_abilities import (
    AgentIconBlock,
    AgentIconCondition,
    AgentPaymentBlock,
    condition_block,
    discard_box,
    discard_spy,
    either_box,
    intrigue_box,
    lose_box,
    opens_at_placement,
    optional_arrow,
    payment_box,
    target_piece,
    trash_box,
)
from dune_imperium.rules.agent_effects import (
    AGENT_ICON_CARDS,
    AGENT_ICON_INTRIGUE,
    AGENT_ICON_PLEDGE,
    AGENT_ICON_RESEARCH,
    AGENT_ICON_SPICE,
    AGENT_ICON_TROOPS,
    AUTOMATIC_AGENT_ICONS,
    CONTROL_THE_SPICE_PRICE,
    OPTIONAL_AGENT_ICONS,
    agent_box_influence_blocked,
    agent_card_cost_block,
    agent_card_icons_at_placement,
    agent_card_payment_block,
    agent_icon_block,
    apply_agent_card_discard,
    apply_agent_card_influence,
    apply_agent_card_payment,
    box_hook_names,
    legal_agent_card_contract_completion_actions,
    legal_agent_card_discard_actions,
    legal_agent_card_icon_actions,
    legal_agent_card_influence_actions,
    legal_agent_card_opponent_retreat_actions,
    legal_agent_card_payment_actions,
    legal_agent_card_spy_actions,
    legal_agent_card_trash_actions,
    resolve_agent_card_effect,
    resolve_agent_card_icon,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.effect_interpreter import (
    condition_holds,
    spy_placement_allowed_post_ids,
)
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    agent_card_source,
    short_of,
)
from dune_imperium.rules.frames import FrameKind

_BOX = PersonalCardAgentEffect


def test_every_record_is_a_printed_agent_box() -> None:
    assert len(AGENT_BOX_ABILITIES) == 88
    for effect in AGENT_BOX_ABILITIES:
        assert effect in AGENT_EFFECT_TEXT, effect


def test_icon_boxes_keep_their_printed_icons_in_order() -> None:
    """The icon-by-icon boxes queue the icons OQ-027 rules, in printed order."""

    assert {
        effect: agent_card_icons_at_placement(effect)
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if ability.icons
    } == {
        _BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: ("troops", "cards"),
        _BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO: ("water", "spice"),
        _BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO: ("solari", "spice"),
        _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN: (
            "troops",
            "cards",
        ),
        _BOX.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS: ("cards", "intrigue"),
        _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED: ("troops", "cards"),
        _BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO: ("cards", "cards_second"),
        _BOX.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED: ("cards", "research"),
        _BOX.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE: ("water", "return_self"),
        # With a choice icon answered by its own rows (composed A3f).
        _BOX.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE: ("influence", "trash_self"),
        _BOX.DRAW_ONE_AND_RECALL_AGENT: ("cards", "recall"),
        _BOX.MAY_RECALL_AGENT_SENT_THIS_TURN: ("recall",),
        _BOX.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND: ("trash", "cards"),
    }
    for effect, ability in AGENT_BOX_ABILITIES.items():
        if not ability.icons:
            assert agent_card_icons_at_placement(effect) == ()


def test_placement_requirements_are_fixed_by_the_placement() -> None:
    """Only the visited space and a Bond among cards in play are judged when
    the card is played (OQ-028 (a)); every other condition when it resolves."""

    requirements = {
        type(ability.requirement)
        for ability in AGENT_BOX_ABILITIES.values()
        if ability.requirement is not None
    }
    assert requirements == {AtMakerSpace, FactionBond}
    harvester = AGENT_BOX_ABILITIES[_BOX.GAIN_SPICE_IF_MAKER_SPACE]
    owner = PlayerState(player_id=0)
    maker = next(space for space in BOARD_SPACES if space.maker)
    city = next(space for space in BOARD_SPACES if not space.maker)
    assert opens_at_placement(harvester, owner, maker, "imperium:x:0")
    assert not opens_at_placement(harvester, owner, city, "imperium:x:0")
    elders = AGENT_BOX_ABILITIES[_BOX.RECRUIT_TWO_IF_BENE_GESSERIT_BOND]
    elders_id = "imperium:southern_elders:0"
    assert not opens_at_placement(elders, owner, city, elders_id)
    bonded = replace(owner, in_play=("imperium:weirding_woman:0",))
    assert opens_at_placement(elders, bonded, city, elders_id)


def test_every_icon_condition_has_a_block() -> None:
    """An icon's condition must say why it waits (``condition_block``): the
    legal list and the page ask for it, and a condition with no block would
    raise there (the dry run does not catch a TypeError). The genetic-marker
    icons only exist with Immortality, where the research token is placed."""

    owner = PlayerState(player_id=0, research_space=RESEARCH_START_ID)
    context = {"card_id": "imperium:x:0", "graft_card_id": ""}
    for ability in AGENT_BOX_ABILITIES.values():
        for line in ability.sections if ability.icons else ():
            if line.condition is not None:
                condition_block(line.condition, owner, context)


def test_condition_blocks_say_what_the_owner_has() -> None:
    owner = PlayerState(
        player_id=0,
        influence=Influence(bene_gesserit=1),
        resources=Resources(spice=1),
    )
    context = {"card_id": "imperium:x:0", "graft_card_id": ""}
    assert condition_block(
        InfluenceAtLeast(Faction.BENE_GESSERIT, 2), owner, context
    ) == AgentIconBlock(
        AgentIconCondition.INFLUENCE, 2, 1, faction=Faction.BENE_GESSERIT
    )
    assert condition_block(GainedSpiceThisTurn(2), owner, context) == AgentIconBlock(
        AgentIconCondition.SPICE_GAINED, 2, 1
    )
    assert condition_block(HasAlliance(Faction.FREMEN), owner, context) == (
        AgentIconBlock(AgentIconCondition.ALLIANCE, faction=Faction.FREMEN)
    )
    allied = replace(owner, alliance_faction_ids=("fremen",))
    assert condition_block(HasAlliance(Faction.FREMEN), allied, context) is None
    with pytest.raises(TypeError, match="no icon block"):
        condition_block(AtMakerSpace(), owner, context)


def _played(
    card: str, owner: PlayerState, config: RulesetConfig | None = None
) -> GameState:
    """``card`` sent to the first space it may visit, its box pending."""

    state = GameState(
        config=config or RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            replace(owner, hand=(card,)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["card_id"] == card
    )
    placed = apply_agent_action(state, action).state
    assert placed.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    return placed


def test_an_icon_waits_for_its_condition_and_resolves_last_in_its_events() -> None:
    """Wheels Within Wheels: each icon is its own action, judged when it
    resolves; the icon's event comes after its gains (OQ-027, OQ-028)."""

    card = "imperium:wheels_within_wheels:0"
    # Its only Agent icon is the Spy: a Spy on a post opens that post's spaces.
    spy = PlayerState(
        player_id=0,
        influence=Influence(emperor=2),
        spy_post_ids=(OBSERVATION_POSTS[0].post_id,),
        spies_supply=2,
    )
    placed = _played(card, spy)
    assert legal_agent_card_icon_actions(placed, 0) == (
        DomainAction("resolve_agent_card_effect", 0, (("effect", "solari"),)),
    )
    context = dict(placed.decision_stack[-1].context)
    wheels = _BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO
    assert agent_icon_block(placed.players[0], context, wheels, "spice") == (
        AgentIconBlock(
            AgentIconCondition.INFLUENCE, 2, 0, faction=Faction.SPACING_GUILD
        )
    )
    result = resolve_agent_card_icon(
        placed, DomainAction("resolve_agent_card_effect", 0, (("effect", "solari"),))
    )
    assert result.state.players[0].resources.solari == 2
    source = agent_card_source(1, 0, card)
    assert [(event.kind, event.event_id) for event in result.events] == [
        ("agent_card_effect_resolved", f"{source}:solari:resolved")
    ]


def test_one_action_box_puts_its_event_first_and_draws_by_card_name() -> None:
    """Prepare the Way: one action; its draw is named after the card's
    definition, so every Reserve copy draws from the same source."""

    card = "reserve:prepare_the_way:3"
    waiting = _played(card, PlayerState(player_id=0, deck=("imperium:x:0",)))
    unavailable = resolve_agent_card_effect(waiting)
    assert [event.kind for event in unavailable.events] == [
        "agent_card_effect_unavailable"
    ]
    ready = _played(
        card,
        PlayerState(
            player_id=0,
            influence=Influence(bene_gesserit=2),
            deck=("starting:0:dagger:0",),
        ),
    )
    resolved = resolve_agent_card_effect(ready)
    assert resolved.events[0].event_id == agent_card_source(1, 0, card)
    assert resolved.events[0].kind == "agent_card_effect_resolved"
    assert resolved.state.players[0].hand == ("starting:0:dagger:0",)
    # An empty deck shows the draw's source: the reshuffle is named after the
    # card, whichever copy drew.
    shuffling = _played(
        card,
        PlayerState(
            player_id=0,
            influence=Influence(bene_gesserit=2),
            discard_pile=("starting:0:dagger:0",),
        ),
    )
    reshuffle = resolve_agent_card_effect(shuffling).state.decision_stack[-1]
    assert reshuffle.frame_id == (
        "round:1:player:0:agent_card:prepare_the_way:discard_shuffle:personal_draw"
    )


def test_throne_room_politics_recruits_then_offers_its_trash_on_a_frame() -> None:
    """The troop first; the black trash icon on a frame named after the box,
    so a self-trash keeps its card's effects (OQ-022)."""

    card = "imperium:throne_room_politics:0"
    placed = _played(
        card,
        PlayerState(player_id=0),
        RulesetConfig(immortality=True, bloodlines=True, choam_module=True),
    )
    result = resolve_agent_card_effect(placed)
    troops = placed.players[0].troops_garrison
    assert result.state.players[0].troops_garrison == troops + 1
    frame = result.state.decision_stack[-1]
    assert frame.kind == FrameKind.OPTIONAL_TRASH
    assert dict(frame.context)["source"] == agent_card_source(1, 0, card)
    assert result.events[0].kind == "agent_card_effect_resolved"


def test_pointing_the_way_draws_its_intrigue_before_the_write_back() -> None:
    """Pointing the Way waits for a sandworm in the Conflict, then draws its
    Intrigue card under the box's ``:intrigue_draw`` source; the box's event
    comes first. (The equivalence games never resolve it.)"""

    card = "imperium:pointing_the_way:0"
    config = RulesetConfig(bloodlines=True)
    waiting = _played(card, PlayerState(player_id=0), config)
    assert [event.kind for event in resolve_agent_card_effect(waiting).events] == [
        "agent_card_effect_unavailable"
    ]
    owner = replace(waiting.players[0], sandworms_conflict=1)
    ready = replace(
        waiting,
        players=(owner, *waiting.players[1:]),
        intrigue_deck=("intrigue:bribery:0",),
    )
    result = resolve_agent_card_effect(ready)
    source = agent_card_source(1, 0, card)
    assert [(event.kind, event.event_id) for event in result.events] == [
        ("agent_card_effect_resolved", source),
        ("intrigue_card_drawn", f"{source}:intrigue_draw:intrigue_draw:1"),
    ]
    assert result.state.players[0].intrigue_cards == ("intrigue:bribery:0",)


def test_every_hook_record_names_a_special_flow() -> None:
    """A record's ``hook`` names a function of ``agent_effects._BOX_HOOKS``,
    and every such function has its record (composed effects, A3)."""

    named = {
        ability.hook
        for ability in AGENT_BOX_ABILITIES.values()
        if ability.hook is not None
    }
    assert named == box_hook_names()
    for ability in AGENT_BOX_ABILITIES.values():
        if ability.hook is not None:
            assert not ability.icons


def test_an_optional_arrow_offers_its_payment_while_it_can_pay() -> None:
    """Smuggler's Haven, "You may pay 4 spice -> Gain 1 VP" (composed A3b):
    the payment row while the spice is there, only the raw refusal (dropped
    in the turn) once it is not; the payment's event has no card id."""

    card = "imperium:smuggler_s_haven:0"
    rich = _played(card, PlayerState(player_id=0, resources=Resources(spice=4)))
    assert legal_agent_card_payment_actions(rich, 0) == (
        DomainAction("decline_agent_card_payment", 0),
        DomainAction("pay_agent_card_spice", 0),
    )
    paid = apply_agent_card_payment(rich, DomainAction("pay_agent_card_spice", 0))
    owner = paid.state.players[0]
    assert (owner.resources.spice, owner.spice_spent_turn) == (0, 4)
    assert owner.victory_points == rich.players[0].victory_points + 1
    assert [(e.kind, e.event_id, e.payload) for e in paid.events] == [
        (
            "agent_card_payment_resolved",
            "round:1:player:0:agent_card_payment:paid",
            (("player", 0), ("resource", "spice"), ("spent", 4)),
        )
    ]
    poor = _played(card, PlayerState(player_id=0, resources=Resources(spice=3)))
    assert legal_agent_card_payment_actions(poor, 0) == (
        DomainAction("decline_agent_card_payment", 0),
    )
    assert agent_card_cost_block(poor, 0) == short_of(OptionalBlockKind.SPICE, 4, 3)


def test_a_payment_that_buys_nothing_is_withheld() -> None:
    """Tleilaxu Surgeon: spending two specimens is not offered once the
    Tleilaxu token is at the track's end (OQ-071); otherwise it advances the
    token twice under the payment's ``:tleilaxu`` source."""

    card = "imperium:tleilaxu_surgeon:0"
    config = RulesetConfig(immortality=True)
    owner = PlayerState(player_id=0, specimens=2, troops_supply=7)
    placed = _played(card, owner, config)
    assert legal_agent_card_payment_actions(placed, 0)[-1] == DomainAction(
        "pay_agent_card_two_specimens", 0
    )
    paid = apply_agent_card_payment(
        placed, DomainAction("pay_agent_card_two_specimens", 0)
    )
    assert paid.state.players[0].specimens == 0
    assert paid.events[0].payload == (
        ("player", 0),
        ("resource", "specimen"),
        ("spent", 2),
    )
    assert all(
        event.event_id.startswith("round:1:player:0:agent_card_payment:tleilaxu")
        for event in paid.events[1:]
    )
    assert paid.events[1:]
    finished = replace(
        placed,
        players=(
            replace(placed.players[0], tleilaxu_space=TLEILAXU_TRACK_END),
            *placed.players[1:],
        ),
    )
    assert agent_card_payment_block(
        finished, 0, _BOX.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU
    ) is AgentPaymentBlock.TLEILAXU_TRACK_END
    assert legal_agent_card_payment_actions(finished, 0) == (
        DomainAction("decline_agent_card_payment", 0),
    )


def test_only_a_payment_the_shape_pays_is_a_payment_box() -> None:
    """The payment shape takes the four records it was written for, and
    refuses a record it would pay wrongly (a reward it does not give, a
    cost no row names): such a box keeps its own code."""

    payments = {
        effect
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if payment_box(ability)
    }
    assert payments == {
        _BOX.PAY_TWO_WATER_TO_DRAW_TWO,
        _BOX.MAY_PAY_FOUR_SPICE_FOR_VP,
        _BOX.MAY_PAY_SPECIMEN_FOR_FOUR_SOLARI,
        _BOX.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU,
    }
    for cost, rewards in (
        (PayResources(spice=1), (TrashPersonalCard(), RecruitTroops(1))),
        (PayResources(solari=5), (AdvanceTleilaxu(1),)),
    ):
        optional = Ability(
            AbilityTiming.AGENT_BOX,
            (EffectSection(rewards=rewards, costs=(cost,)),),
            mark=AbilityMark.OPTIONAL,
        )
        assert not payment_box(optional)


def test_a_chosen_influence_offers_every_rising_faction_and_waits_without_one() -> None:
    """For Humanity, "Gain 1 Influence with a chosen Faction" (composed A3c):
    one row per Faction that can rise, named for the Agent box; with every
    cube at the top it offers no confirmation and waits, then fizzles at the
    turn's end (OQ-060, OQ-057 (1))."""

    card = "imperium:for_humanity:0"
    config = RulesetConfig(immortality=True)
    owner = PlayerState(player_id=0, influence=Influence(emperor=6))
    placed = _played(card, owner, config)
    rows = legal_agent_card_influence_actions(placed, 0)
    assert [dict(row.arguments)["faction"] for row in rows] == [
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    assert {row.action_id for row in rows} == {"choose_agent_card_influence"}
    gained = apply_agent_card_influence(placed, rows[0])
    assert gained.state.players[0].influence.spacing_guild == 1
    source = agent_card_source(1, 0, card)
    prefix = f"{source}:influence:spacing_guild"
    assert gained.events[0].event_id == f"{prefix}:influence"
    context = dict(gained.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False
    top = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    stuck = _played(card, PlayerState(player_id=0, influence=top), config)
    assert legal_agent_card_influence_actions(stuck, 0) == ()
    # The page names the reason it waits (``display.unavailable``).
    assert agent_box_influence_blocked(stuck, 0)
    assert not agent_box_influence_blocked(placed, 0)
    fizzled = resolve_agent_card_effect(stuck)
    assert [(e.kind, e.event_id) for e in fizzled.events] == [
        ("agent_card_effect_unavailable", source)
    ]


def test_public_spectacle_waits_for_a_recalled_spy() -> None:
    card = "imperium:public_spectacle:0"
    spy = PlayerState(
        player_id=0, spy_post_ids=(OBSERVATION_POSTS[0].post_id,), spies_supply=2
    )
    placed = _played(card, spy)
    assert legal_agent_card_influence_actions(placed, 0) == ()
    # Waiting for its condition, not for a cube to lower.
    assert not agent_box_influence_blocked(placed, 0)
    recalled = replace(
        placed,
        players=(
            replace(placed.players[0], spies_recalled_turn=1),
            *placed.players[1:],
        ),
    )
    assert len(legal_agent_card_influence_actions(recalled, 0)) == 4
    with pytest.raises(RuntimeError, match="requires a player choice"):
        resolve_agent_card_effect(recalled)


def test_six_boxes_choose_one_target_and_read_as_their_cards() -> None:
    """Composed A3c: a mandatory line that is one target choice -- a
    Faction, a Spy's post, an enemy unit, a Contract -- and no other record
    is read as one; the new pieces read as the printed text."""

    targets = {
        effect: type(piece)
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if (piece := target_piece(ability)) is not None
    }
    assert targets == {
        _BOX.GAIN_CHOSEN_INFLUENCE: GainInfluence,
        _BOX.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN: GainInfluence,
        _BOX.PLACE_SPY: PlaceSpy,
        _BOX.PLACE_SPY_ON_VISITED_SPACE_MAY_SHARE: PlaceSpy,
        _BOX.FORCE_OPPONENT_TROOP_RETREAT: ForceEnemyRetreat,
        _BOX.COMPLETE_ONE_CONTRACT: CompleteContract,
    }
    for effect in (
        _BOX.PLACE_SPY,
        _BOX.PLACE_SPY_ON_VISITED_SPACE_MAY_SHARE,
        _BOX.FORCE_OPPONENT_TROOP_RETREAT,
        _BOX.COMPLETE_ONE_CONTRACT,
    ):
        (reward,) = AGENT_BOX_ABILITIES[effect].sections[0].rewards
        assert reward_text(reward) == AGENT_EFFECT_TEXT[effect]
        assert reward_text_ko(reward) == AGENT_EFFECT_TEXT_KO[effect]
    with pytest.raises(ValueError, match="names no other limit"):
        PlaceSpy(factions=(Faction.EMPEROR,), visited_space=True)
    # Only the Agent box knows the space visited this turn.
    with pytest.raises(TypeError, match="judged with its Agent box"):
        spy_placement_allowed_post_ids(PlaceSpy(visited_space=True))


def test_double_agent_shares_another_players_post_never_its_own() -> None:
    """Double Agent's Spy goes on a post of the space visited this turn, held
    by another player's Spy or not; without a Spy in supply the owner may
    pass the icon up or recall one of its own Spies there [Main pp. 11, 20]."""

    placed = _played("imperium:double_agent:0", PlayerState(player_id=0))
    visited = dict(placed.decision_stack[-1].context)["space_id"]
    connected = tuple(
        post.post_id
        for post in OBSERVATION_POSTS
        if visited in post.connected_space_ids
    )
    (post,) = connected  # Assembly Hall shares its post with Gather Support.
    elsewhere = tuple(
        p.post_id for p in OBSERVATION_POSTS if p.post_id not in connected
    )[:2]

    def spies(owner: tuple[str, ...], other: tuple[str, ...]) -> GameState:
        return replace(
            placed,
            players=(
                replace(
                    placed.players[0],
                    spy_post_ids=owner,
                    spies_supply=3 - len(owner),
                ),
                replace(
                    placed.players[1],
                    spy_post_ids=other,
                    spies_supply=3 - len(other),
                ),
                *placed.players[2:],
            ),
        )

    def posts(state: GameState) -> list[tuple[str, object]]:
        return [
            (row.action_id, dict(row.arguments).get("post_id"))
            for row in legal_agent_card_spy_actions(state, 0)
        ]

    shared = spies((), (post,))
    assert posts(shared) == [("place_agent_card_spy", post)]
    own = spies((post,), ())
    assert posts(own) == []
    # No Spy left: only a recall on the visited space's posts frees one.
    empty = spies((post, *elsewhere), ())
    assert posts(empty) == [
        ("decline_agent_card_spy", None),
        ("recall_spy_for_agent_card", post),
    ]


def test_a_target_box_raises_while_it_can_choose_and_fizzles_without() -> None:
    """Disruption Tactics and CHOAM Demands resolve through their rows; the
    one-action resolution refuses while a row is offered and otherwise
    reports the box unavailable (OQ-057 (1))."""

    config = RulesetConfig(bloodlines=True, choam_module=True)
    card = "imperium:disruption_tactics:0"
    tactics = _played(card, PlayerState(player_id=0), config)
    source = agent_card_source(1, 0, card)
    assert legal_agent_card_opponent_retreat_actions(tactics, 0) == ()
    fizzled = resolve_agent_card_effect(tactics)
    assert [(e.kind, e.event_id) for e in fizzled.events] == [
        ("agent_card_effect_unavailable", source)
    ]
    enemy = replace(
        tactics.players[2],
        troops_supply=tactics.players[2].troops_supply - 1,
        troops_conflict=1,
        commanders_conflict=1,
    )
    engaged = replace(
        tactics, players=(*tactics.players[:2], enemy, tactics.players[3])
    )
    assert [
        dict(row.arguments)
        for row in legal_agent_card_opponent_retreat_actions(engaged, 0)
    ] == [{"player": 2}, {"commanders": 1, "player": 2}]
    with pytest.raises(RuntimeError, match="enemy retreat"):
        resolve_agent_card_effect(engaged)

    owner = PlayerState(player_id=0, active_contract_ids=("contract:heighliner_ii",))
    demands = _played("imperium:choam_demands:0", owner, config)
    assert [
        dict(row.arguments)["instance_id"]
        for row in legal_agent_card_contract_completion_actions(demands, 0)
    ] == ["contract:heighliner_ii"]
    with pytest.raises(ValueError, match="complete_contract_by_card"):
        resolve_agent_card_effect(demands)


def test_eight_discard_arrows_read_the_discarded_card() -> None:
    """Composed A3d: "[You may] discard a card -> ..." boxes. The cost is on
    the first line; a later line's condition reads the discarded card, which
    only the Agent box knows (the generic interpreter refuses it). Captured
    Mentat's and Guild Spy's rewards are armed as icons after the discard,
    under the keys the icon path resolves."""

    discards = {
        effect: ability.mark
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if discard_box(ability)
    }
    assert discards == {
        _BOX.MAY_DISCARD_TO_TAKE_CONTRACT: AbilityMark.OPTIONAL,
        _BOX.MAY_DISCARD_TO_DRAW_ONE: AbilityMark.OPTIONAL,
        _BOX.MAY_DISCARD_FOR_WATER: AbilityMark.OPTIONAL,
        _BOX.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD: AbilityMark.OPTIONAL,
        _BOX.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD: AbilityMark.MANDATORY,
        _BOX.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD: AbilityMark.OPTIONAL,
        _BOX.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD: (
            AbilityMark.OPTIONAL
        ),
        _BOX.MAY_DISCARD_FOR_DEEP_COVER_SPY: AbilityMark.OPTIONAL,
    }
    assert {
        effect: ability.armed_icons
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if ability.armed_icons and discard_box(ability)
    } == {
        _BOX.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD: (
            AGENT_ICON_INTRIGUE,
            AGENT_ICON_CARDS,
        ),
        _BOX.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD: (
            AGENT_ICON_CARDS,
            AGENT_ICON_INTRIGUE,
        ),
    }
    for effect, mark in discards.items():
        ability = AGENT_BOX_ABILITIES[effect]
        assert ability.sections[0].costs == (DiscardFromHand(),)
        assert not payment_box(ability) and target_piece(ability) is None
        # An optional arrow resolves only through its rows.
        assert optional_arrow(ability) is (mark is AbilityMark.OPTIONAL)
    guild = DiscardedCardHasFaction(Faction.SPACING_GUILD)
    folding = _BOX.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD
    assert condition_text(guild) in AGENT_EFFECT_TEXT[folding]
    assert condition_text_ko(guild) in AGENT_EFFECT_TEXT_KO[folding]
    envoy = _played("imperium:guild_envoy:0", PlayerState(player_id=0))
    with pytest.raises(TypeError, match="judged with its Agent box"):
        condition_holds(envoy, 0, guild)


def test_two_intrigue_arrows_trash_an_intrigue_card() -> None:
    """Composed A3d: Branching Path and Junction Headquarters pay with an
    Intrigue card under an Alliance judged when the cost is paid; Branching
    Path's rewards are armed as icons, Junction's VP is paid at once."""

    branching = AGENT_BOX_ABILITIES[
        _BOX.MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
    ]
    junction = AGENT_BOX_ABILITIES[
        _BOX.MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
    ]
    intrigue_arrows = [
        ability for ability in AGENT_BOX_ABILITIES.values() if intrigue_box(ability)
    ]
    assert intrigue_arrows == [branching, junction]
    assert branching.armed_icons == (AGENT_ICON_INTRIGUE, AGENT_ICON_SPICE)
    assert not junction.armed_icons
    for ability in intrigue_arrows:
        assert optional_arrow(ability)
        assert not discard_box(ability) and not payment_box(ability)


def test_five_trash_boxes_and_what_they_read_as() -> None:
    """Composed A3e: black trash icons (Calculus of Power's one, Ruthless
    Leadership's two under its Commander condition) and arrows paid by a
    trash (Shishakli's draw, Pivotal Gambit's armed troop and pledge, Elite
    Forces' armed draw and troop with the Combat paid at once). Only
    Ruthless Leadership resolves as one action -- its condition failing --
    the others through their rows alone."""

    trash = {
        effect: ability
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if trash_box(ability)
    }
    assert set(trash) == {
        _BOX.TRASH_PERSONAL_CARD,
        _BOX.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT,
        _BOX.TRASH_PERSONAL_CARD_TO_DRAW_ONE,
        _BOX.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE,
        _BOX.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS,
    }
    elite = trash[_BOX.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS]
    assert elite.armed_icons == (AGENT_ICON_INTRIGUE, AGENT_ICON_TROOPS)
    assert len(elite.sections) == 3
    emperor = TrashedCardHasFaction(Faction.EMPEROR)
    assert condition_text_ko(emperor) in AGENT_EFFECT_TEXT_KO[
        _BOX.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS
    ]
    assert {e for e, a in trash.items() if not optional_arrow(a)} == {
        _BOX.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT
    }
    gambit = _BOX.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE
    assert trash[gambit].armed_icons == (AGENT_ICON_TROOPS, AGENT_ICON_PLEDGE)
    assert cost_text(TrashCard(this_card=True)) == "Trash this card"
    assert cost_text_ko(TrashCard(this_card=True)) in AGENT_EFFECT_TEXT_KO[gambit]
    pledge = PledgeFirstPlaceInfluence()
    assert reward_text(pledge).lower() in AGENT_EFFECT_TEXT[gambit].lower()
    assert reward_text_ko(pledge) in AGENT_EFFECT_TEXT_KO[gambit]
    with pytest.raises(ValueError, match="one place"):
        TrashCard(hand_only=True, this_card=True)


def test_ruthless_leadership_waits_for_a_commander() -> None:
    """Its condition is judged at each trash (OQ-028): no row without a
    Commander in the Conflict, and the one-action resolution then reports
    the box unavailable; with one, it refuses (the rows resolve it)."""

    card = "imperium:ruthless_leadership:0"
    config = RulesetConfig(bloodlines=True, promo_cards=True)
    alone = _played(card, PlayerState(player_id=0), config)
    assert legal_agent_card_trash_actions(alone, 0) == ()
    events = resolve_agent_card_effect(alone).events
    assert [e.kind for e in events] == ["agent_card_effect_unavailable"]
    owner = replace(alone.players[0], commanders_garrison=0, commanders_conflict=1)
    commanding = replace(alone, players=(owner, *alone.players[1:]))
    rows = legal_agent_card_trash_actions(commanding, 0)
    assert rows[0].action_id == "decline_agent_card_trash"
    with pytest.raises(RuntimeError, match="trash effect requires"):
        resolve_agent_card_effect(commanding)


def test_two_optional_acquisitions_are_records() -> None:
    """Composed A3f: Price is No Object (paid in Solari, to hand) and Tleilaxu
    Master (cost cap 6 under one genetic marker, to hand at two). Only Tleilaxu
    Master resolves as one action -- its old answer, unavailable."""

    price = AGENT_BOX_ABILITIES[_BOX.ACQUIRE_WITH_SOLARI_TO_HAND]
    master = AGENT_BOX_ABILITIES[_BOX.MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER]
    found = {
        effect
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if agent_box_acquisition(ability) is not None
    }
    assert found == {
        _BOX.ACQUIRE_WITH_SOLARI_TO_HAND,
        _BOX.MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER,
    }
    assert optional_arrow(price) and not optional_arrow(master)
    (piece,) = price.sections[0].rewards
    printed = _BOX.ACQUIRE_WITH_SOLARI_TO_HAND
    assert reward_text_ko(piece) in AGENT_EFFECT_TEXT_KO[printed]
    assert reward_text(piece).lower() in AGENT_EFFECT_TEXT[printed].lower()


def test_each_armed_key_stays_with_the_boxes_the_icon_path_serves() -> None:
    """The legacy icon path offers and pays an armed key per effect (Branching
    Path's ``spice`` is its 2 spice), so a record arming a key elsewhere would
    be refused there or paid wrong; a new one has to extend that path first."""

    users: dict[str, set[PersonalCardAgentEffect]] = {}
    for effect, ability in AGENT_BOX_ABILITIES.items():
        for key in ability.armed_icons:
            users.setdefault(key, set()).add(effect)
    branching = (
        _BOX.MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
    )
    mentat = _BOX.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD
    guild_spy = _BOX.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD
    gambit = _BOX.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE
    elite = _BOX.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS
    piter = _BOX.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH
    assert users == {
        AGENT_ICON_INTRIGUE: {mentat, guild_spy, branching, elite},
        AGENT_ICON_CARDS: {mentat, guild_spy, piter},
        AGENT_ICON_SPICE: {branching},
        AGENT_ICON_TROOPS: {gambit, elite},
        AGENT_ICON_PLEDGE: {gambit},
        AGENT_ICON_RESEARCH: {piter},
    }


def test_arrakis_observer_announces_its_spice_and_waits_on_its_spy() -> None:
    """Composed A3f: Arrakis Observer's discard pays 2 spice for a Spacing
    Guild card, announced as before, and leaves the box on its mandatory Deep
    Cover Spy (OQ-057 (14)), whose rows the record's Spy gives."""

    ability = AGENT_BOX_ABILITIES[_BOX.MAY_DISCARD_FOR_DEEP_COVER_SPY]
    assert discard_spy(ability) == PlaceSpy(shared_post=True)
    card = "imperium:arrakis_observer:0"
    guild = "imperium:guild_envoy:0"
    owner = PlayerState(player_id=0, hand=(guild,))
    # The Tech Module lets a Spy be boxed (used below).
    placed = _played(card, owner, RulesetConfig(bloodlines=True, tech_module=True))
    placed = replace(
        placed, players=(replace(placed.players[0], hand=(guild,)), *placed.players[1:])
    )
    rows = legal_agent_card_discard_actions(placed, 0)
    discard = next(row for row in rows if row.action_id == "discard_agent_card")
    paid = apply_agent_card_discard(placed, discard)
    source = "round:1:player:0:agent_card_discard"
    assert [(e.kind, e.event_id) for e in paid.events][-1] == (
        "agent_card_effect_resolved",
        f"{source}:{guild}:spice",
    )
    context = dict(paid.state.decision_stack[-1].context)
    assert context["agent_card_spy_pending"] is True
    assert context["pending_agent_effect"] is True
    spy_rows = legal_agent_card_spy_actions(paid.state, 0)
    assert spy_rows and {row.action_id for row in spy_rows} == {"place_agent_card_spy"}
    # The one-action resolution of the Spy step: refused while it has rows,
    # else the Spy marks go and the box is unavailable (OQ-057 (1)).
    with pytest.raises(RuntimeError, match="place-Spy"):
        resolve_agent_card_effect(paid.state)
    seat = paid.state.players[0]
    boxed = replace(seat, spies_supply=0, spy_post_ids=(), spies_boxed=3)
    stuck = replace(paid.state, players=(boxed, *paid.state.players[1:]))
    assert legal_agent_card_spy_actions(stuck, 0) == ()
    fizzled = resolve_agent_card_effect(stuck)
    assert [e.kind for e in fizzled.events] == ["agent_card_effect_unavailable"]
    after = dict(fizzled.state.decision_stack[-1].context)
    assert "agent_card_spy_pending" not in after
    assert after["pending_agent_effect"] is False


def test_piter_loses_a_unit_then_arms_its_rewards() -> None:
    """Composed A3f: Piter, Genius Advisor's "You may lose 1 troop -> Draw 2
    cards, Research" -- a troop or a Sardaukar Commander per zone (OQ-105),
    then both rewards armed (OQ-106); with no unit only the refusal, and the
    one-action resolution keeps its old answer (unavailable)."""

    piter = AGENT_BOX_ABILITIES[_BOX.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH]
    assert lose_box(piter) and not optional_arrow(piter)
    assert piter.armed_icons == (AGENT_ICON_CARDS, AGENT_ICON_RESEARCH)
    card = "tleilaxu:piter_genius_advisor:0"
    config = RulesetConfig(immortality=True, promo_cards=True)
    placed = _played(card, PlayerState(player_id=0), config)
    rows = legal_agent_card_payment_actions(placed, 0)
    assert [(row.action_id, dict(row.arguments)) for row in rows] == [
        ("decline_agent_card_payment", {}),
        ("lose_agent_card_troop", {"zone": "garrison"}),
    ]
    lost = apply_agent_card_payment(placed, rows[1])
    context = dict(lost.state.decision_stack[-1].context)
    assert context["pending_agent_icons"] == "cards,research"
    owner = replace(placed.players[0], troops_garrison=0, troops_supply=12)
    bare = replace(placed, players=(owner, *placed.players[1:]))
    assert [row.action_id for row in legal_agent_card_payment_actions(bare, 0)] == [
        "decline_agent_card_payment"
    ]
    assert [e.kind for e in resolve_agent_card_effect(bare).events] == [
        "agent_card_effect_unavailable"
    ]


def test_control_the_spice_is_a_payment_hook() -> None:
    """Control the Spice keeps its payment flow as code (its paid event names
    the card and carries the troops, its trash is a frame of its own): the
    record names the hook, prints the line, and the one-action resolution
    refuses as before."""

    spice = AGENT_BOX_ABILITIES[_BOX.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT]
    assert spice.hook == "control_the_spice"
    assert spice.mark is AbilityMark.OPTIONAL
    (line,) = spice.sections
    assert line.costs == (PayResources(spice=CONTROL_THE_SPICE_PRICE),)
    assert not payment_box(spice) and not trash_box(spice)


def test_three_boxes_put_a_plain_line_beside_a_choice() -> None:
    """Composed A3f: Southern Faith and High Priority Travel ("Choose one")
    and Interstellar Conspiracy (a plain line, then a conditioned choice that
    pays both). The plain line resolves as one action; Possible Futures,
    whose Bond turns its choice into both, is a hook."""

    either = {
        effect: ability.structure
        for effect, ability in AGENT_BOX_ABILITIES.items()
        if either_box(ability)
    }
    conspiracy = _BOX.GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD
    assert either == {
        _BOX.DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND: AbilityStructure.ONE_OF,
        _BOX.DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO: (
            AbilityStructure.ONE_OF
        ),
        conspiracy: AbilityStructure.SEQUENCE,
    }
    futures = AGENT_BOX_ABILITIES[_BOX.CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND]
    assert futures.hook == "possible_futures"
    partner = GraftedWithFaction((Faction.EMPEROR, Faction.SPACING_GUILD))
    assert condition_text(partner) in AGENT_EFFECT_TEXT[conspiracy]
    assert condition_text_ko(partner) in AGENT_EFFECT_TEXT_KO[conspiracy]


def test_southern_faith_offers_its_influence_beside_the_draw_with_the_bond() -> None:
    """Without the Bond only the frame's plain row (the draw); with it and a
    Bene Gesserit cube that can rise, the plain row and that Influence."""

    card = "imperium:southern_faith:0"
    config = RulesetConfig(bloodlines=True)
    alone = _played(card, PlayerState(player_id=0), config)
    assert legal_agent_card_influence_actions(alone, 0) == ()
    resolved = resolve_agent_card_effect(alone)
    assert resolved.events[0].kind == "agent_card_effect_resolved"
    bonded = PlayerState(player_id=0, in_play=("imperium:bene_gesserit_operative:0",))
    with_bond = _played(card, bonded, config)
    rows = legal_agent_card_influence_actions(with_bond, 0)
    assert [(row.action_id, dict(row.arguments)) for row in rows] == [
        ("resolve_agent_card_effect", {}),
        ("choose_agent_card_influence", {"faction": "bene_gesserit"}),
    ]


def test_a_choice_icon_stays_with_its_own_rows() -> None:
    """Composed A3f: a choice icon (Dangerous Rhetoric's Influence, the Agent
    recalls, Tread in Darkness's trash) is never a ``resolve_agent_card_effect``
    row: only the automatic icons are, and "Trash this card." reads as the
    card prints it."""

    choice_keys = {"influence", "recall", "trash"}
    for ability in AGENT_BOX_ABILITIES.values():
        assert not choice_keys & set(ability.icons) & set(AUTOMATIC_AGENT_ICONS)
    rhetoric = _BOX.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE
    trash_line = AGENT_BOX_ABILITIES[rhetoric].sections[1]
    (piece,) = trash_line.rewards
    assert reward_text_ko(piece) in AGENT_EFFECT_TEXT_KO[rhetoric]
    for effect in (
        _BOX.DRAW_ONE_AND_RECALL_AGENT,
        _BOX.MAY_RECALL_AGENT_SENT_THIS_TURN,
    ):
        (recall,) = AGENT_BOX_ABILITIES[effect].sections[-1].rewards
        assert reward_text_ko(recall) in AGENT_EFFECT_TEXT_KO[effect]


def test_dangerous_rhetoric_trashes_itself_by_its_own_icon() -> None:
    """The card trashes itself and the Influence icon still pays (OQ-022);
    the trash names the box, and the icon's event comes last."""

    card = "imperium:dangerous_rhetoric:0"
    placed = _played(card, PlayerState(player_id=0))
    icons = legal_agent_card_icon_actions(placed, 0)
    assert [dict(row.arguments)["effect"] for row in icons] == ["trash_self"]
    trashed = resolve_agent_card_icon(placed, icons[0])
    source = agent_card_source(1, 0, card)
    assert [e.event_id for e in trashed.events][0] == f"{source}:trash:{card}"
    assert trashed.events[-1].event_id == f"{source}:trash_self:resolved"
    context = dict(trashed.state.decision_stack[-1].context)
    assert context["agent_card_self_trashed"] is True
    assert context["pending_agent_icons"] == "influence"


def test_the_optional_icons_are_marked_in_their_records() -> None:
    """The icons ``OPTIONAL_AGENT_ICONS`` lets lapse are the ones their records
    print as optional (Tread in Darkness's black trash icon, Twisted Mentat's
    "You may recall"), so a later stage can read it from the records."""

    marked = {}
    for effect, ability in AGENT_BOX_ABILITIES.items():
        keys = frozenset(
            key
            for key, line in zip(ability.icons, ability.sections, strict=False)
            if any(
                isinstance(reward, TrashPersonalCard) and not reward.mandatory
                or isinstance(reward, RecallAgent) and reward.optional
                for reward in line.rewards
            )
        )
        if keys:
            marked[effect] = keys
    assert marked == dict(OPTIONAL_AGENT_ICONS)
