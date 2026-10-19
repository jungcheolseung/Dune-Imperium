"""The Signet Ring box's own event (composed-effects cleanup-2c-4).

docs/composed-effects-plan.md 5, "정리-2c 사건 문법" 2c-4 item 1: the Signet
Ring's box -- the card's Agent box, a Ghola's copy of it, or Servo-Receivers'
acquire icon -- ends with exactly one ``leader_signet_<outcome>`` event, last
among the events of the action that ended it (``box_events.signet_box_event``;
payload the card, or the tile as ``tech_id``, and the seat, plus ``effect``
for one icon). What the ability gave is not on it: Solari, spice and water are
a ``resources_gained`` of the Signet's source, a draw, an influence gain or a
recruit shortfall is an event of its own. A step after which the box stays
pending (a Spy placed for Staban's paid follow-up, Kota's Tech tile) ends
nothing and leaves no box event.

The walk below applies every Signet choice of every implemented Leader in
both hosts and checks that rule on each transition.
"""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
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
from dune_imperium.core.engine import RuleResult, Transition
from dune_imperium.core.events import GameEvent
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.engine import ACTION_HANDLERS, UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.leader_abilities import (
    _pending_signet_context,
    legal_feyd_track_actions,
    legal_leader_signet_actions,
)

TECH = RulesetConfig(bloodlines=True, tech_module=True)
ENGINE = UprisingRulesEngine()
RAPID_ENGINEERING = "intrigue:rapid_engineering:0"
SIGNET = "player:0:starter:signet_ring:0"
DAGGER = "player:0:starter:dagger:0"
DIPLOMACY = "player:0:starter:diplomacy:0"
ELIMINATE_ALLIES = "imperium:eliminate_allies:0"
SOURCE = "round:1:player:0:leader_signet"
BOX_KINDS = frozenset(
    f"leader_signet_{outcome}"
    for outcome in ("resolved", "declined", "unavailable", "lapsed", "expired")
)
# The Leaders whose Signet Ring offers the owner a choice (the others resolve
# at once and are checked one by one below).
CHOICE_LEADERS = (
    "feyd_rautha_harkonnen",
    "lady_jessica",
    "lady_margot_fenring",
    "princess_irulan",
    "staban_tuek",
    "shaddam_corrino_iv",
    "chani",
    "count_hasimir_fenring",
    "duncan_idaho",
    "esmar_tuek",
    "gaius_helen_mohiam",
    "kota_odax_of_ix",
)


def _owner(leader_id: str, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "leader_id": leader_id,
        "hand": (SIGNET, DIPLOMACY, DAGGER, ELIMINATE_ALLIES),
        "deck": (
            "player:0:starter:reconnaissance:0",
            "player:0:starter:seek_allies:0",
            "player:0:starter:convincing_argument:0",
        ),
        "intrigue_cards": (RAPID_ENGINEERING,),
        "resources": Resources(solari=4, spice=6, water=2),
        "influence": Influence(emperor=2, fremen=2),
        "troops_conflict": 2,
        "troops_supply": 7,
        "tech_ids": ("glowglobes",),
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _turn_state(owner: PlayerState) -> GameState:
    return GameState(
        config=TECH,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:4],
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        tech_stacks=(("servo_receivers",), (), ()),
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 2),
            ("imperial_basin", 0),
            ("tuek_sietch", 1),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _act(state: GameState, action_id: str, **arguments: object) -> GameState:
    """Apply the owner's legal action; an ``agent_turn`` is a whole placement
    (card and space), applied as the Agent turn's two steps (stage B1)."""

    def matches(action: DomainAction) -> bool:
        return all(dict(action.arguments).get(k) == v for k, v in arguments.items())

    if action_id == "agent_turn":
        placement = next(
            placement
            for placement in executable_placements(state, 0)
            if matches(placement)
        )
        return apply_placement(ENGINE, state, placement).state
    action = next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == action_id and matches(action)
    )
    return apply_whole(ENGINE, state, action).state


def _signet_ring_placed(owner: PlayerState) -> GameState:
    """Host A: the Signet Ring card sent to Arrakeen, its box pending."""

    return _act(_turn_state(owner), "agent_turn", card_id=SIGNET, space_id="arrakeen")


def _servo_acquired(owner: PlayerState) -> GameState:
    """Host B: Servo-Receivers bought, the Signet in its own frame."""

    state = _act(_turn_state(owner), "play_intrigue", card_id=RAPID_ENGINEERING)
    state = _act(state, "choose_intrigue_discard", card_id=DAGGER)
    bought = _act(state, "acquire_tech", tech_id="servo_receivers")
    return _act(bought, "resolve_tech_acquire_effect", effect="signet")


def _pending(state: GameState) -> bool:
    return _pending_signet_context(state, 0) is not None


def _box(events: tuple[GameEvent, ...]) -> list[GameEvent]:
    return [event for event in events if event.kind in BOX_KINDS]


def _signet_actions(state: GameState) -> tuple[DomainAction, ...]:
    return (*legal_feyd_track_actions(state, 0), *legal_leader_signet_actions(state, 0))


def _apply(state: GameState, action: DomainAction) -> Transition | RuleResult:
    """Apply a Signet choice: through the engine while it offers the row,
    else (a refusal an Agent turn's optional box does not offer, OQ-095 (2))
    through the action's rule function."""

    if action in ENGINE.whole_actions(state, 0):
        return apply_whole(ENGINE, state, action)
    return ACTION_HANDLERS[action.action_id](state, action)


def _check_transition(
    before: GameState, action: DomainAction, host: str
) -> GameState | None:
    """Apply one Signet choice and check the box-event rule on it; the state
    after it while the box is still pending, else None."""

    result = _apply(before, action)
    box = _box(result.events)
    ended = not _pending(result.state)
    label = f"{host} {action.action_id} {dict(action.arguments)}"
    for event in box:
        # The box's event says only which card and whose; what the ability
        # gave has events of its own.
        keys = set(dict(event.payload))
        assert keys <= {"card_id", "tech_id", "effect", "player"}, label
        assert dict(event.payload)["player"] == 0, label
        assert ("tech_id" in dict(event.payload)) is (host == "servo"), label
    if ended:
        assert len(box) == 1, f"{label}: {[e.kind for e in result.events]}"
        assert result.events[-1] == box[0], f"{label}: the box event is not last"
        assert box[0].event_id.startswith(f"{SOURCE}:"), label
    else:
        # Only one icon of the box (Kota's rewards) may end while it waits.
        assert all("effect" in dict(event.payload) for event in box), label
    assert not any(
        event.kind
        in (
            "leader_signet_payment_declined",
            "leader_card_trash_declined",
            "leader_ability_spice_gained",
        )
        for event in result.events
    ), label
    return None if ended else result.state


@pytest.mark.parametrize("spies_supply", [3, 0])
@pytest.mark.parametrize("host", ["card", "servo"])
@pytest.mark.parametrize("leader_id", CHOICE_LEADERS)
def test_every_signet_choice_ends_the_box_with_one_event_last(
    leader_id: str, host: str, spies_supply: int
) -> None:
    owner = _owner(
        leader_id,
        spies_supply=spies_supply,
        spy_post_ids=()
        if spies_supply
        else (
            "arrakis-deep-desert",
            "fremen-desert-tactics-fremkit",
            "emperor-sardaukar-dutiful-service",
        ),
    )
    start = _signet_ring_placed(owner) if host == "card" else _servo_acquired(owner)
    assert _pending(start)
    pending = [start]
    transitions = 0
    leaves = 0
    while pending:
        current = pending.pop()
        actions = _signet_actions(current)
        assert actions, "a pending Signet must offer a choice"
        for action in actions:
            still = _check_transition(current, action, host)
            transitions += 1
            if still is not None:
                pending.append(still)
            else:
                leaves += 1
        assert transitions < 600, "Signet choices must terminate"
    assert leaves >= 1


# --- What each Signet gives is not on the box event ---------------------------


def _events_of(
    state: GameState, action: DomainAction
) -> list[tuple[str, dict[str, object]]]:
    result = _apply(state, action)
    # Stage B3a: an action with a target is applied as its steps, and the
    # steps before the last add the seat-only ``effect_picked`` events, which
    # are no part of what the box's events say.
    return [
        (event.kind, dict(event.payload))
        for event in result.events
        if event.kind != "effect_picked"
    ]


def _action(state: GameState, action_id: str, **arguments: object) -> DomainAction:
    return next(
        action
        for action in _signet_actions(state)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )


def test_a_gain_is_a_resources_gained_of_the_signets_source() -> None:
    # Reverse Engineering's spice: "Gain 1 spice" [Kota Odax of Ix card].
    placed = _signet_ring_placed(_owner("kota_odax_of_ix"))
    events = _events_of(placed, _action(placed, "gain_leader_signet_spice"))
    assert events == [
        ("resources_gained", {"player": 0, "source": SOURCE, "spice": 1}),
        ("leader_signet_resolved", {"card_id": SIGNET, "player": 0}),
    ]

    # Water of Life: "Pay 1 spice -> Gain 1 water" [Reverend Mother Jessica
    # card]; the payment keeps its own event.
    water = _signet_ring_placed(
        _owner("lady_jessica", leader_face_id="reverend_mother_jessica")
    )
    events = _events_of(water, _action(water, "pay_leader_signet_spice"))
    assert [kind for kind, _ in events] == [
        "resources_paid",
        "resources_gained",
        "leader_signet_resolved",
    ]
    assert events[1][1] == {"player": 0, "source": SOURCE, "water": 1}

    # Unseen Network, next to the Landsraad: "1 spice -> 3 Solari" [Staban
    # Tuek card]; the Spy placed first leaves the box pending.
    staban = _signet_ring_placed(_owner("staban_tuek"))
    landsraad = next(
        action
        for action in _signet_actions(staban)
        if action.action_id == "place_leader_spy"
        and str(dict(action.arguments)["post_id"]).startswith("landsraad-")
    )
    events = _events_of(staban, landsraad)
    assert [kind for kind, _ in events] == ["spy_placed"]
    after_spy = _apply(staban, landsraad).state
    events = _events_of(after_spy, _action(after_spy, "pay_leader_signet_spice"))
    assert events == [
        ("resources_paid", {"player": 0, "source": SOURCE, "spice": 1}),
        ("resources_gained", {"player": 0, "source": SOURCE, "solari": 3}),
        ("leader_signet_resolved", {"card_id": SIGNET, "player": 0}),
    ]
    events = _events_of(after_spy, _action(after_spy, "decline_leader_signet_payment"))
    assert events == [("leader_signet_declined", {"card_id": SIGNET, "player": 0})]

    # Chronicler's Insight: a trashed card that costs one or more gives two
    # spice [Princess Irulan card]; a starting card has no printed cost.
    irulan = _signet_ring_placed(_owner("princess_irulan"))
    events = _events_of(irulan, _action(irulan, "trash_leader_card", card_id=DAGGER))
    assert [kind for kind, _ in events][-1] == "leader_signet_resolved"
    assert "resources_gained" not in [kind for kind, _ in events]
    costly = _signet_ring_placed(
        _owner("princess_irulan", hand=(SIGNET, ELIMINATE_ALLIES))
    )
    events = _events_of(
        costly, _action(costly, "trash_leader_card", card_id=ELIMINATE_ALLIES)
    )
    assert [kind for kind, _ in events][-2:] == [
        "resources_gained",
        "leader_signet_resolved",
    ]
    assert dict(events[-2][1]) == {"player": 0, "source": SOURCE, "spice": 2}


def test_shaddam_signet_orders_its_gain_its_shortfall_and_the_box() -> None:
    # "1 Solari and 1 troop" [Shaddam Corrino IV card]: with no troop left in
    # the supply the shortfall has its event, and the box's comes last.
    short = _signet_ring_placed(
        _owner(
            "shaddam_corrino_iv",
            troops_supply=0,
            troops_conflict=0,
            troops_garrison=12,
        )
    )
    events = _events_of(short, _action(short, "gain_leader_signet_troop"))
    assert [kind for kind, _ in events] == [
        "resources_gained",
        "troops_recruit_short",
        "leader_signet_resolved",
    ]
    assert events[0][1] == {"player": 0, "source": SOURCE, "solari": 1}

    # "3 Solari -> 1 Influence": the influence gain precedes the box event,
    # which no longer lists the Solari paid or the influence gained.
    placed = _signet_ring_placed(_owner("shaddam_corrino_iv"))
    choose = _action(placed, "choose_leader_signet_influence", faction="fremen")
    events = _events_of(placed, choose)
    assert events[-1] == ("leader_signet_resolved", {"card_id": SIGNET, "player": 0})
    assert any(kind == "influence_gained" for kind, _ in events[:-1])


def test_a_refusal_ends_the_box_as_declined() -> None:
    for leader_id, action_id in (
        ("lady_jessica", "decline_leader_signet_payment"),
        ("princess_irulan", "decline_leader_signet_payment"),
        ("chani", "decline_leader_signet_payment"),
        ("duncan_idaho", "decline_leader_signet_payment"),
    ):
        placed = _signet_ring_placed(_owner(leader_id))
        events = _events_of(placed, _action(placed, action_id))
        assert events == [
            ("leader_signet_declined", {"card_id": SIGNET, "player": 0})
        ], leader_id

    # Personal Training's trash stage and a Spy stage passed up.
    feyd = _signet_ring_placed(
        _owner("feyd_rautha_harkonnen", feyd_track_space="start")
    )
    paid = _apply(
        feyd,
        _action(feyd, "advance_feyd_track", space_id="paid_trash"),
    ).state
    events = _events_of(paid, _action(paid, "decline_leader_card_trash"))
    assert events == [("leader_signet_declined", {"card_id": SIGNET, "player": 0})]


def test_personal_training_ends_the_box_only_with_its_last_stage() -> None:
    feyd = _signet_ring_placed(
        _owner("feyd_rautha_harkonnen", feyd_track_space="second_spy")
    )
    double = _action(feyd, "advance_feyd_track", space_id="double_spice")
    events = _events_of(feyd, double)
    assert [kind for kind, _ in events] == [
        "feyd_token_advanced",
        "resources_gained",
        "leader_signet_resolved",
    ]
    assert events[1][1] == {"player": 0, "source": SOURCE, "spice": 2}

    # The troop-and-Spy space recruits at once and waits for its Spy: no box
    # event until the Spy is placed.
    final = _signet_ring_placed(
        _owner("feyd_rautha_harkonnen", feyd_track_space="late_trash")
    )
    advanced = _apply(final, _action(final, "advance_feyd_track", space_id="final"))
    assert not _box(advanced.events)
    assert _pending(advanced.state)
    events = _events_of(advanced.state, _signet_actions(advanced.state)[0])
    assert [kind for kind, _ in events] == ["spy_placed", "leader_signet_resolved"]


def test_kota_reward_icons_each_end_with_their_own_box_event() -> None:
    placed = _signet_ring_placed(_owner("kota_odax_of_ix"))
    traded = _apply(placed, _action(placed, "trash_leader_tech")).state
    # The Tech tile is the arrow's cost: the box waits for its two icons.
    assert _pending(traded)
    first = _apply(
        traded, _action(traded, "resolve_agent_card_effect", effect="intrigue")
    )
    assert [event.event_id for event in _box(first.events)] == [
        f"{SOURCE}:intrigue:resolved"
    ]
    assert dict(first.events[-1].payload) == {
        "card_id": SIGNET,
        "effect": "intrigue",
        "player": 0,
    }
    assert _pending(first.state)
    second = _apply(
        first.state, _action(first.state, "resolve_agent_card_effect", effect="cards")
    )
    assert second.events[-1].event_id == f"{SOURCE}:cards:resolved"
    assert not _pending(second.state)


def test_servo_receivers_names_its_tile_on_the_box_event() -> None:
    # The Signet frame's sentinel card id is no printed card: the log reads
    # ``tech_id`` like tech_acquired's.
    start = _servo_acquired(_owner("lady_jessica"))
    events = _apply(start, _action(start, "decline_leader_signet_payment")).events
    assert [(e.kind, dict(e.payload)) for e in events] == [
        ("leader_signet_declined", {"player": 0, "tech_id": "servo_receivers"})
    ]


def test_an_automatic_signet_gains_only_what_its_lines_give() -> None:
    # Judge of the Change: "Landsraad + 2 Emperor Influence -> water; City ->
    # Solari; Spice Trade -> spice" [Liet Kynes card], judged by the space
    # visited. A line whose condition fails adds nothing and leaves no gain
    # event, only the box's.
    for space_id, influence, gained in (
        ("arrakeen", Influence(emperor=2), {"solari": 1}),
        ("imperial_basin", Influence(emperor=2), {"spice": 1}),
        ("assembly_hall", Influence(emperor=2), {"water": 1}),
        ("assembly_hall", Influence(emperor=1), {}),
    ):
        owner = _owner("liet_kynes", influence=influence)
        placed = _act(
            _turn_state(owner), "agent_turn", card_id=SIGNET, space_id=space_id
        )
        resolved = apply_whole(ENGINE, placed, _act_row(placed))
        kinds = [event.kind for event in resolved.events]
        assert kinds[-1] == "leader_signet_resolved", space_id
        assert kinds.count("resources_gained") == (1 if gained else 0), space_id
        assert dict(resolved.events[-1].payload) == {"card_id": SIGNET, "player": 0}
        if gained:
            assert dict(resolved.events[0].payload) == {
                "player": 0,
                "source": SOURCE,
                **gained,
            }


def test_the_other_automatic_signets_leave_only_the_box_event() -> None:
    # Warmaster, Lead the Way and Harkonnen Advisor [Gurney Halleck, Muad'Dib
    # and Piter De Vries cards]: a recruit or a draw is not on the box event.
    for leader_id in ("gurney_halleck", "muad_dib", "piter_de_vries"):
        placed = _act(
            _turn_state(_owner(leader_id)),
            "agent_turn",
            card_id=SIGNET,
            space_id="arrakeen",
        )
        resolved = apply_whole(ENGINE, placed, _act_row(placed))
        assert [(e.kind, dict(e.payload)) for e in resolved.events] == [
            ("leader_signet_resolved", {"card_id": SIGNET, "player": 0})
        ], leader_id

    # With no troop left the shortfall has its event, before the box's.
    empty = _owner(
        "gurney_halleck", troops_supply=0, troops_conflict=0, troops_garrison=12
    )
    placed = _act(_turn_state(empty), "agent_turn", card_id=SIGNET, space_id="arrakeen")
    resolved = apply_whole(ENGINE, placed, _act_row(placed))
    assert [event.kind for event in resolved.events] == [
        "troops_recruit_short",
        "leader_signet_resolved",
    ]


def _act_row(state: GameState) -> DomainAction:
    """The row that resolves the Signet Ring's automatic ability."""

    return next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "resolve_agent_card_effect"
    )


def test_the_frame_kind_of_a_servo_signet_is_the_leader_signet_frame() -> None:
    start = _servo_acquired(_owner("lady_jessica"))
    assert start.decision_stack[-1].kind == FrameKind.LEADER_SIGNET
