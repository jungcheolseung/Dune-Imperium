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
    AtFactionSpace,
    AtMakerSpace,
    CompleteContract,
    DiscardedCardHasFaction,
    DiscardFromHand,
    EachOpponentDiscardsCard,
    EachOpponentLosesTroop,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainSolariPerPartnerAgentIcon,
    GainVictoryPoints,
    GraftedTrash,
    GraftedWithFaction,
    HasAlliance,
    InfluenceAtLeast,
    OpponentsMoveSpiesFromVisitedSpace,
    PayResources,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecallAgent,
    RecruitTroops,
    ReturnOtherGraftedCardAtRevealStart,
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
from dune_imperium.rules import turn_rows
from dune_imperium.rules.acquisition import agent_box_acquisition
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.agent_box_abilities import (
    AgentIconBlock,
    AgentIconCondition,
    AgentPaymentBlock,
    choose_two_box,
    condition_block,
    discard_box,
    discard_pay_block,
    discard_pay_box,
    discard_spy,
    either_box,
    graft_trash_box,
    intrigue_box,
    lose_box,
    opens_at_placement,
    optional_arrow,
    payment_box,
    plain_and_paid_box,
    target_piece,
    trash_box,
    wall_and_worm_box,
    wall_and_worm_needs_hooks,
    wall_and_worm_spice,
)
from dune_imperium.rules.agent_effects import (
    AGENT_ICON_CARDS,
    AGENT_ICON_INTRIGUE,
    AGENT_ICON_PLEDGE,
    AGENT_ICON_RESEARCH,
    AGENT_ICON_SPICE,
    AGENT_ICON_TROOPS,
    AUTOMATIC_AGENT_ICONS,
    OPTIONAL_AGENT_ICONS,
    agent_box_influence_blocked,
    agent_card_cost_block,
    agent_card_effect_is_unavailable,
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
from dune_imperium.rules.box_events import BoxNeedsRows, BoxOutcome, agent_box_event
from dune_imperium.rules.effect_interpreter import condition_holds
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    agent_card_source,
    short_of,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.optional_trash import (
    apply_optional_trash,
    legacy_trash_whole,
    legal_optional_trash_actions,
    open_optional_trash,
    trash_printer,
)
from dune_imperium.rules.spy_placement import spy_placement_allowed_post_ids

_BOX = PersonalCardAgentEffect


def test_every_record_is_a_printed_agent_box() -> None:
    # 103 Uprising-family boxes, the original game's Foldspace and the
    # original Imperium cards' new boxes (stage P3: Arrakis Recruiter, Spice
    # Smugglers, Gun Thopter, Crysknife, Duncan Idaho, Fremen Camp, Opulence).
    assert len(AGENT_BOX_ABILITIES) == 103 + 1 + 7
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
        # Split per icon (cleanup-2d-5, user decision 2026-10-18).
        _BOX.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE: ("influence", "intrigue"),
        _BOX.DRAW_ONE_AND_COMBAT_ICON: ("cards", "combat"),
        _BOX.DRAW_ONE_AND_PLACE_SPY_IF_BENE_GESSERIT_BOND: ("cards", "spy"),
        # Split per icon (engine audit 2026-10-22, P4; the same decision).
        _BOX.GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD: (
            "spice",
            "influence",
        ),
        # The original game's Foldspace: "Draw 1 card" and "Trash this card",
        # separate effects (imperium-base.md 13.3).
        _BOX.DRAW_ONE_AND_TRASH_SELF: ("cards", "trash_self"),
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
    assert requirements == {AtMakerSpace, AtFactionSpace, FactionBond}
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
    assert result.events == (
        resources_gained_event(source, 0, solari=2),
        agent_box_event(source, card, 0, BoxOutcome.RESOLVED, effect="solari"),
    )


def test_one_action_box_puts_its_event_last_and_draws_by_its_box() -> None:
    """Prepare the Way: one action; its draw is named after the box, and the
    box's event comes last (cleanup-2c-2)."""

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
    box = agent_card_source(1, 0, card)
    assert resolved.events[-1] == agent_box_event(box, card, 0, BoxOutcome.RESOLVED)
    assert resolved.state.players[0].hand == ("starting:0:dagger:0",)
    # An empty deck shows the draw's source: the reshuffle is named after the
    # box.
    shuffling = _played(
        card,
        PlayerState(
            player_id=0,
            influence=Influence(bene_gesserit=2),
            discard_pile=("starting:0:dagger:0",),
        ),
    )
    reshuffle = resolve_agent_card_effect(shuffling).state.decision_stack[-1]
    assert reshuffle.frame_id == f"{box}:discard_shuffle:personal_draw"


def test_throne_room_politics_recruits_then_queues_its_trash_on_the_turn() -> None:
    """The troop first; the black trash icon waits on the Agent turn as rows
    with no refusal, queued under the box's own source so a self-trash keeps
    its card's effects (OQ-022; cleanup-2b, OQ-095 (2))."""

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
    assert frame.kind == FrameKind.AGENT_EFFECTS
    # The trash records the card whose box printed it (stage B3c-2b).
    printer = "agent_card|throne_room_politics"
    assert turn_rows.pending(frame) == (
        (turn_rows.OPTIONAL_TRASH, agent_card_source(1, 0, card), printer),
    )
    legal = legal_optional_trash_actions(result.state, 0)
    # The card itself sits in play: it may trash itself (OQ-022). No refusal.
    assert [(a.action_id, dict(a.arguments)) for a in legal] == [
        (
            "trash_optional_card",
            {
                "card_id": card,
                "printed": "throne_room_politics",
                "source": "agent_card",
            },
        )
    ]
    assert result.events[0].kind == "agent_card_effect_resolved"


def test_the_seat_picks_which_waiting_trash_icon_trashes_a_card() -> None:
    """With two trashes waiting, each is an effect of its own, resolved in
    its owner's order ("You may carry out all these effects in any order"
    [Main p. 9], OQ-027), and which one trashes a card matters: a card
    trashed by its own box's icon keeps what is left of its box (OQ-022:
    "카드가 자기 효과로 자신을 trash하는 경우 인쇄된 이득은 정상 지급"), by
    another effect it loses it (OQ-022, 2026-10-12). So the seat picks the
    icon by what printed it, then the card (stage B3c-2b); the older engine
    picked the icon itself (``legacy_trash_whole``: the card's own box's
    first, else the newest no other card in play opened)."""

    card = "imperium:throne_room_politics:0"
    other = "starting:0:dagger:0"
    placed = _played(
        card,
        PlayerState(player_id=0, discard_pile=(other,)),
        RulesetConfig(immortality=True, bloodlines=True, choam_module=True),
    )
    own = agent_card_source(1, 0, card)
    elsewhere = "round:1:player:0:research:c3r3"
    # The box's trash first, a research space's raised after it.
    waiting = open_optional_trash(
        resolve_agent_card_effect(placed).state,
        0,
        elsewhere,
        printer=trash_printer(Source.RESEARCH, "c3r3"),
    )
    frame = waiting.decision_stack[-1]
    box_icon = (turn_rows.OPTIONAL_TRASH, own, "agent_card|throne_room_politics")
    research_icon = (turn_rows.OPTIONAL_TRASH, elsewhere, "research|c3r3")
    assert turn_rows.pending(frame) == (box_icon, research_icon)

    def row(card_id: str, source: str, printed: str) -> DomainAction:
        return DomainAction(
            "trash_optional_card",
            0,
            (("card_id", card_id), ("printed", printed), ("source", source)),
        )

    by_box = ("agent_card", "throne_room_politics")
    by_research = ("research", "c3r3")
    # Each card (discard pile, then play) by each icon, the newest first.
    assert legal_optional_trash_actions(waiting, 0) == (
        row(other, *by_research),
        row(other, *by_box),
        row(card, *by_research),
        row(card, *by_box),
    )

    def trash(action: DomainAction) -> GameState:
        return apply_optional_trash(waiting, action).state

    # The card by its own box's icon: that trash is taken, the research
    # space's still waits, and the box is marked self-trashed.
    itself = trash(row(card, *by_box))
    assert itself.players[0].trashed == (card,)
    assert turn_rows.pending(itself.decision_stack[-1]) == (research_icon,)
    assert dict(itself.decision_stack[-1].context)["agent_card_self_trashed"] is True
    # The card by the research space's icon: another effect's trash, so the
    # box is not its own (the expiry hook ends it, OQ-022) and its own icon
    # still waits.
    by_other = trash(row(card, *by_research))
    assert by_other.players[0].trashed == (card,)
    assert turn_rows.pending(by_other.decision_stack[-1]) == (box_icon,)
    assert "agent_card_self_trashed" not in dict(by_other.decision_stack[-1].context)
    # The engine's expiry hook, which runs after that step, then ends the
    # trashed card's own waiting icon too: "you can't receive or activate an
    # effect from a card that is already trashed" (OQ-022; OQ-027 (b); engine
    # audit 2026-10-22, P1).
    from dune_imperium.core import RuleResult
    from dune_imperium.rules.agent_effects import expire_trashed_card_effects

    expired = expire_trashed_card_effects(RuleResult(state=by_other))
    assert turn_rows.pending(expired.state.decision_stack[-1]) == ()
    assert [event.kind for event in expired.events] == ["agent_card_effect_expired"]
    # The older engine's own picks.
    assert legacy_trash_whole(waiting, 0, card) == row(card, *by_box)
    assert legacy_trash_whole(waiting, 0, other) == row(other, *by_research)


def test_pointing_the_way_draws_its_intrigue_before_the_write_back() -> None:
    """Pointing the Way waits for a sandworm in the Conflict, then draws its
    Intrigue card under the box's ``:intrigue_draw`` source; the box's event
    comes last. (The equivalence games never resolve it.)"""

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
        ("intrigue_card_drawn", f"{source}:intrigue_draw:1"),
        ("agent_card_effect_resolved", f"{source}:resolved"),
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
    in the turn) once it is not; the payment's event is named after the box
    and has no card id, and the box's event comes last."""

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
    box = agent_card_source(1, 0, card)
    payment, *rest = paid.events
    assert (payment.kind, payment.event_id, payment.payload) == (
        "resources_paid",
        f"{box}:paid",
        (("player", 0), ("source", box), ("spice", 4)),
    )
    assert rest == [
        resources_gained_event(box, 0, victory_points=1),
        agent_box_event(box, card, 0, BoxOutcome.RESOLVED),
    ]
    poor = _played(card, PlayerState(player_id=0, resources=Resources(spice=3)))
    assert legal_agent_card_payment_actions(poor, 0) == (
        DomainAction("decline_agent_card_payment", 0),
    )
    assert agent_card_cost_block(poor, 0) == short_of(OptionalBlockKind.SPICE, 4, 3)


def test_a_payment_that_buys_nothing_is_withheld() -> None:
    """Tleilaxu Surgeon: spending two specimens is not offered once the
    Tleilaxu token is at the track's end (OQ-071); otherwise it advances the
    token twice under the box's ``:tleilaxu`` source."""

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
    box = agent_card_source(1, 0, card)
    assert paid.events[0].payload == (
        ("player", 0),
        ("source", box),
        ("specimens", 2),
    )
    assert paid.events[0].event_id == f"{box}:paid"
    advances = paid.events[1:-1]
    assert advances
    # The Tleilaxu track names its own events (cleanup-2c-5).
    assert all(
        event.event_id.startswith("round:1:player:0:tleilaxu:") for event in advances
    )
    assert paid.events[-1] == agent_box_event(box, card, 0, BoxOutcome.RESOLVED)
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
    """The payment shape takes the eight records it was written for (Control
    the Spice since cleanup-2d, the original game's Spice Smugglers since
    stage P3, whose reward is one fixed Faction's Influence, its Duncan
    Idaho, whose troop and draw wait as armed icons, and its Fremen Camp),
    and refuses a
    record it would pay wrongly (a reward it does not give -- a chosen or the
    visited Faction's Influence --, a cost no row names): such a box keeps its
    own code."""

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
        _BOX.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT,
        _BOX.MAY_PAY_TWO_SPICE_FOR_SPACING_GUILD_INFLUENCE_AND_THREE_SOLARI,
        _BOX.MAY_PAY_ONE_WATER_FOR_TROOP_AND_DRAW_ONE,
        _BOX.MAY_PAY_TWO_SPICE_FOR_THREE_TROOPS,
    }
    for cost, rewards in (
        (PayResources(spice=1), (GainInfluence(),)),
        (PayResources(spice=1), (GainInfluence(visited_space=True),)),
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
    assert gained.events[-1] == agent_box_event(source, card, 0, BoxOutcome.RESOLVED)
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
        ("agent_card_effect_unavailable", f"{source}:unavailable")
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
    with pytest.raises(BoxNeedsRows, match="resolves through its target choice"):
        resolve_agent_card_effect(recalled)


def test_seven_boxes_choose_one_target_and_read_as_their_cards() -> None:
    """Composed A3c: a mandatory line that is one target choice -- a
    Faction, a Spy's post, an enemy unit, a Contract; Long Reach's two
    distinct Factions since cleanup-2d -- and no other record is read as
    one; the new pieces read as the printed text."""

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
        _BOX.GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE: GainInfluence,
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
        ("agent_card_effect_unavailable", f"{source}:unavailable")
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
    with pytest.raises(BoxNeedsRows, match="target choice"):
        resolve_agent_card_effect(engaged)

    owner = PlayerState(player_id=0, active_contract_ids=("contract:heighliner_ii",))
    demands = _played("imperium:choam_demands:0", owner, config)
    assert [
        dict(row.arguments)["instance_id"]
        for row in legal_agent_card_contract_completion_actions(demands, 0)
    ] == ["contract:heighliner_ii"]
    with pytest.raises(BoxNeedsRows, match="target choice"):
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
        # Guild Envoy prints no arrow: its mandatory discard and the hidden
        # draw printed below it are separate steps (OQ-106; user decision
        # 2026-10-25; engine audit 2026-10-22, P6).
        _BOX.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD: (AGENT_ICON_CARDS,),
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


def test_six_trash_boxes_and_what_they_read_as() -> None:
    """Composed A3e: black trash icons (Calculus of Power's one, Ruthless
    Leadership's two under its Commander condition) and arrows paid by a
    trash (Shishakli's draw, Pivotal Gambit's armed troop and pledge, Elite
    Forces' armed draw and troop with the Combat paid at once; Treacherous
    Maneuver's two trashes for the visited Faction's 2 instead of 1 since
    cleanup-2d). Only Ruthless Leadership resolves as one action -- its
    condition failing -- the others through their rows alone."""

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
        _BOX.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE,
    }
    treacherous = _BOX.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
    hand = TrashCard(hand_only=True, faction=Faction.EMPEROR)
    assert trash[treacherous].sections[0].costs == (hand, TrashCard(this_card=True))
    assert cost_text_ko(hand) in AGENT_EFFECT_TEXT_KO[treacherous]
    assert "an Emperor card from your hand" in AGENT_EFFECT_TEXT[treacherous]
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
    with pytest.raises(ValueError, match="in hand"):
        TrashCard(faction=Faction.EMPEROR)


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
    with pytest.raises(BoxNeedsRows, match="trash effect requires"):
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
    # Guild Envoy's two cards: the icon path reads an armed line's count
    # (engine audit 2026-10-22, P6).
    envoy = _BOX.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD
    # The original game's Duncan Idaho (stage P3): a paid arrow arming the
    # same troop and card icons.
    duncan = _BOX.MAY_PAY_ONE_WATER_FOR_TROOP_AND_DRAW_ONE
    assert users == {
        AGENT_ICON_INTRIGUE: {mentat, guild_spy, branching, elite},
        AGENT_ICON_CARDS: {mentat, guild_spy, piter, envoy, duncan},
        AGENT_ICON_SPICE: {branching},
        AGENT_ICON_TROOPS: {gambit, elite, duncan},
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
    # The spice is a gain of the box; the box is not over, so it has no event.
    source = agent_card_source(1, 0, card)
    assert paid.events == (
        paid.events[0],
        resources_gained_event(source, 0, spice=2),
    )
    assert paid.events[0].kind == "card_discarded"
    assert paid.events[0].event_id == f"{source}:discard:{guild}"
    context = dict(paid.state.decision_stack[-1].context)
    assert context["agent_card_spy_pending"] is True
    assert context["pending_agent_effect"] is True
    spy_rows = legal_agent_card_spy_actions(paid.state, 0)
    assert spy_rows and {row.action_id for row in spy_rows} == {"place_agent_card_spy"}
    # The one-action resolution of the Spy step: refused while it has rows,
    # else the Spy marks go and the box is unavailable (OQ-057 (1)).
    with pytest.raises(BoxNeedsRows, match="place-Spy"):
        resolve_agent_card_effect(paid.state)
    seat = paid.state.players[0]
    boxed = replace(seat, spies_supply=0, spy_post_ids=(), spies_boxed=3)
    stuck = replace(paid.state, players=(boxed, *paid.state.players[1:]))
    assert legal_agent_card_spy_actions(stuck, 0) == ()
    fizzled = resolve_agent_card_effect(stuck)
    assert fizzled.events == (
        agent_box_event(source, card, 0, BoxOutcome.UNAVAILABLE),
    )
    after = dict(fizzled.state.decision_stack[-1].context)
    assert "agent_card_spy_pending" not in after
    assert after["pending_agent_effect"] is False


def test_piter_loses_a_unit_then_arms_its_rewards() -> None:
    """Composed A3f: Piter, Genius Advisor's "You may lose 1 troop -> Draw 2
    cards, Research" -- a troop or a Sardaukar Commander per zone (OQ-105),
    then both rewards armed (OQ-106); with no unit only the refusal, and the
    dry run answers that the box is unavailable (cleanup-2c-2: every optional
    arrow alike, and the one-action resolution leaves an optional box to its
    rows)."""

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
    assert agent_card_effect_is_unavailable(bare)
    with pytest.raises(BoxNeedsRows):
        resolve_agent_card_effect(bare)


def test_control_the_spice_is_a_payment_box() -> None:
    """Control the Spice's arrow is the payment shape's since cleanup-2d:
    the troop now, the black trash icon on a frame of its own
    (``tests/unit/rules/test_control_the_spice.py`` plays it)."""

    spice = AGENT_BOX_ABILITIES[_BOX.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT]
    assert spice.hook is None
    assert spice.mark is AbilityMark.OPTIONAL
    (line,) = spice.sections
    assert line.costs == (PayResources(spice=1),)
    assert line.rewards == (TrashPersonalCard(), RecruitTroops(1))
    assert payment_box(spice) and not trash_box(spice)


def test_two_boxes_put_a_plain_line_beside_a_choice() -> None:
    """Composed A3f: Southern Faith and High Priority Travel ("Choose one").
    The plain line resolves as one action; Possible Futures, whose Bond
    turns its choice into both, is a hook. Interstellar Conspiracy, a plain
    line then a conditioned choice that once paid both, resolves icon by
    icon since the engine audit 2026-10-22 (P4; OQ-027 extension 3, user
    decision 2026-10-18 "원칙대로 아이콘마다 나누자")."""

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
    }
    assert AGENT_BOX_ABILITIES[conspiracy].icons == ("spice", "influence")
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


def test_every_personal_card_box_has_a_record() -> None:
    """Composed A3g: with the boxes no stage of the plan listed, only a
    leader's Signet Ring keeps its own code."""

    assert set(PersonalCardAgentEffect) - set(AGENT_BOX_ABILITIES) == {
        _BOX.LEADER_SIGNET
    }


def test_three_boxes_resolve_as_one_action_with_their_own_pieces() -> None:
    """Covert Operation, Holy War and Chairdog (composed A3g) resolve as one
    action; their pieces read as the cards print them, Holy War's sentences
    in printed order (its losses are answered before its Spy moves,
    OQ-036)."""

    pieces = {
        _BOX.EACH_OPPONENT_DISCARDS_PERSONAL_CARD: (EachOpponentDiscardsCard(),),
        _BOX.EACH_OPPONENT_LOSES_TROOP_AND_MOVES_SPY: (
            EachOpponentLosesTroop(),
            OpponentsMoveSpiesFromVisitedSpace(),
        ),
        _BOX.RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START: (
            ReturnOtherGraftedCardAtRevealStart(),
        ),
    }
    for effect, rewards in pieces.items():
        ability = AGENT_BOX_ABILITIES[effect]
        assert ability.hook is None and not ability.icons
        assert ability.mark is AbilityMark.MANDATORY
        (line,) = ability.sections
        assert line.rewards == rewards and line.condition is None
        for reward in rewards:
            assert reward_text(reward) in AGENT_EFFECT_TEXT[effect]
            assert reward_text_ko(reward) in AGENT_EFFECT_TEXT_KO[effect]


def test_no_optional_box_is_a_hook_any_more() -> None:
    """The optional boxes once kept as hooks (composed A3, A3g) are records
    since cleanup-2d; the boxes still kept as hooks are mandatory flows."""

    assert not {
        ability.hook
        for ability in AGENT_BOX_ABILITIES.values()
        if ability.hook is not None and ability.mark is AbilityMark.OPTIONAL
    }
    assert box_hook_names() == {
        "beasts_spoils",
        "long_live_the_fighters",
        "possible_futures",
        "scientific_breakthrough",
    }
    revolt = AGENT_BOX_ABILITIES[
        _BOX.MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS
    ]
    assert wall_and_worm_box(revolt)
    assert wall_and_worm_spice(revolt) == 2 and wall_and_worm_needs_hooks(revolt)


def test_the_grafted_card_trashes_are_records() -> None:
    """Dissecting Kit and Beguiling Pheromones (cleanup-2d): a grafted card's
    trash for a specimen (optional, "the other grafted card") or for the
    visited Faction's Influence (mandatory, "one of the grafted cards"),
    read as the cards print them."""

    kit_effect = _BOX.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN
    pheromones_effect = _BOX.TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE
    kit = AGENT_BOX_ABILITIES[kit_effect]
    pheromones = AGENT_BOX_ABILITIES[pheromones_effect]
    assert graft_trash_box(kit) and graft_trash_box(pheromones)
    assert kit.mark is AbilityMark.OPTIONAL
    assert pheromones.mark is AbilityMark.MANDATORY
    assert kit.sections[0].costs == (TrashCard(grafted=GraftedTrash.OTHER),)
    assert pheromones.sections[0].costs == (TrashCard(grafted=GraftedTrash.EITHER),)
    assert pheromones.sections[0].rewards == (GainInfluence(visited_space=True),)
    for effect, ability in ((kit_effect, kit), (pheromones_effect, pheromones)):
        cost = ability.sections[0].costs[0]
        assert cost_text(cost).lower() in AGENT_EFFECT_TEXT[effect].lower()
        assert cost_text_ko(cost) in AGENT_EFFECT_TEXT_KO[effect]
    with pytest.raises(ValueError, match="no other place"):
        TrashCard(hand_only=True, grafted=GraftedTrash.OTHER)


def test_stitched_horror_is_a_choose_two_record() -> None:
    """Stitched Horror's "Choose two" (cleanup-2d): four one-reward lines,
    picked by their keys in printed order; a "Choose two" needs lines to
    choose from."""

    horror = AGENT_BOX_ABILITIES[_BOX.CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU]
    assert choose_two_box(horror)
    assert horror.structure is AbilityStructure.CHOOSE_TWO
    assert [line.rewards for line in horror.sections] == [
        (GainResources(water=1),),
        (RecruitTroops(1),),
        (TrashPersonalCard(),),
        (AdvanceTleilaxu(1),),
    ]
    with pytest.raises(ValueError, match="two or more lines"):
        Ability(
            AbilityTiming.AGENT_BOX,
            (EffectSection(rewards=(GainResources(water=1),)),),
            structure=AbilityStructure.CHOOSE_TWO,
        )


def test_corrinth_city_is_a_discard_and_pay_record() -> None:
    """Corrinth City's arrow (cleanup-2d): two discards and five Solari for a
    Victory Point, judged as a whole, its rows keeping the card's names."""

    corrinth = AGENT_BOX_ABILITIES[_BOX.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP]
    assert discard_pay_box(corrinth) and corrinth.hook is None
    (line,) = corrinth.sections
    assert line.costs == (DiscardFromHand(2), PayResources(solari=5))
    assert line.rewards == (GainVictoryPoints(1),)
    owner = PlayerState(player_id=0, resources=Resources(solari=4), hand=("a", "b"))
    assert discard_pay_block(owner, corrinth) == short_of(
        OptionalBlockKind.SOLARI, 5, 4
    )


def test_slig_farmer_is_a_plain_line_beside_a_paid_arrow() -> None:
    """Slig Farmer (cleanup-2d): the per-icon Solari, then "You may pay 5
    solari -> Advance the Tleilaxu track", read as the card prints them."""

    effect = _BOX.GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU
    farmer = AGENT_BOX_ABILITIES[effect]
    assert plain_and_paid_box(farmer) and farmer.hook is None
    plain, paid = farmer.sections
    assert plain.rewards == (GainSolariPerPartnerAgentIcon(),)
    assert paid.costs == (PayResources(solari=5),)
    assert paid.rewards == (AdvanceTleilaxu(1),)
    gain = GainSolariPerPartnerAgentIcon()
    assert reward_text(gain) in AGENT_EFFECT_TEXT[effect]
    assert reward_text_ko(gain) in AGENT_EFFECT_TEXT_KO[effect]


def test_scripted_agents_finish_a_trash_icon_another_chooser_picked() -> None:
    """The scripted agents see only the older engine's pick of each card's
    trash icon (``engine_order.older_engine_wholes``), but once an effect is
    picked -- by a network seat whose untrained rows fall back to them --
    they finish it as it is. The 2026-10-20 review of B3c-2b: with a research
    space's and a Tech tile's trashes waiting, the older engine picked the
    newer (the tile's) for every card, so after the research space's row the
    filter left no card and both agents raised."""

    from dune_imperium.agents import HeuristicAgent
    from dune_imperium.agents.app_ai import AppAIAgent
    from dune_imperium.rules import UprisingRulesEngine

    card = "imperium:throne_room_politics:0"
    other = "starting:0:dagger:0"
    state = _played(
        card,
        PlayerState(player_id=0, discard_pile=(other,)),
        RulesetConfig(immortality=True, bloodlines=True, choam_module=True),
    )
    state = resolve_agent_card_effect(state).state
    for source, printer in (
        ("round:1:player:0:research:c3r3", trash_printer(Source.RESEARCH, "c3r3")),
        (
            "round:1:player:0:tech:planetary_array:acquire",
            trash_printer(Source.TECH, "planetary_array"),
        ),
    ):
        state = open_optional_trash(state, 0, source, printer=printer)
    engine = UprisingRulesEngine()
    research = DomainAction("trash", 0, (("printed", "c3r3"), ("source", "research")))
    picked = engine.apply(state, research).state
    legal = engine.legal_actions(picked, 0)
    assert legal and {a.action_id for a in legal} == {"choose_personal_card"}
    view = engine.observe(picked, 0)
    for agent in (HeuristicAgent(seed=1), AppAIAgent(seed=1, level=2)):
        assert agent.choose_action_with_state(picked, view, legal) in legal
