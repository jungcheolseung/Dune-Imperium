"""Stage B3: a waiting effect is picked before its target.

docs/stage-b-plan.md 3c ("B3a 세부 설계"), OQ-111: the Agent-turn effect
frame shows each whole action -- an effect and its target, as the rules
resolve it -- as an effect row (the verb and the place that points at the
effect) and then its target rows. The pick waits in the frame's context:
only its seat sees it (OQ-111 (4)), the turn's other effects and its end
wait for it, and one target still opens the target step (OQ-111 (2)).
"""

from dataclasses import replace

import pytest
from tests.unit.rules.test_board_effects import _espionage_state

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.core import DomainAction, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import (
    first_step,
    path_of,
    picked_rows,
    steps_for,
)

ENGINE = UprisingRulesEngine()
_PLACE = "resolve_espionage_place_spy"


def _ref(icon: str) -> tuple[tuple[str, str], ...]:
    return (("icon", icon), ("printed", "espionage"), ("source", "board_space"))


def test_each_waiting_effect_is_one_effect_row() -> None:
    state, _ = _espionage_state()

    rows = ENGINE.legal_actions(state, 0)

    # Espionage's draw and its Spy [Board Guide p. 1] wait as two effects
    # (OQ-027): the draw has no target and its row resolves it; the Spy
    # opens its posts.
    assert DomainAction("draw", 0, _ref("cards")) in rows
    assert DomainAction("place_spy", 0, _ref("spy")) in rows
    assert not any(row.action_id.startswith("choose_") for row in rows)
    assert not any(row.action_id == _PLACE for row in rows)
    # The whole actions behind the rows are the rules' own list.
    assert any(whole.action_id == _PLACE for whole in ENGINE.whole_actions(state, 0))


def test_a_picked_effect_offers_only_its_targets() -> None:
    state, _ = _espionage_state()
    spy = DomainAction("place_spy", 0, _ref("spy"))

    picked = ENGINE.apply(state, spy).state
    rows = ENGINE.legal_actions(picked, 0)

    posts = {
        dict(whole.arguments)["post_id"]
        for whole in ENGINE.whole_actions(state, 0)
        if whole.action_id == _PLACE
    }
    assert set(rows) == {
        DomainAction("choose_post", 0, (("post_id", post),)) for post in posts
    }
    # Nothing else of the turn -- the draw, the turn's end -- comes in between.
    assert picked_rows(picked) == (spy,)
    assert {whole.action_id for whole in ENGINE.whole_actions(picked, 0)} == {_PLACE}


def test_the_last_step_applies_the_whole_action() -> None:
    state, _ = _espionage_state()
    whole = next(w for w in ENGINE.whole_actions(state, 0) if w.action_id == _PLACE)
    post = dict(whole.arguments)["post_id"]

    stepped = apply_whole(ENGINE, state, whole)

    owner = stepped.state.players[0]
    assert post in owner.spy_post_ids
    assert owner.spies_supply == state.players[0].spies_supply - 1
    assert picked_rows(stepped.state) == ()
    assert [event.kind for event in stepped.events].count("effect_picked") == 1
    # The rules' handler ran on the state without the pick: the rest of the
    # visit (its draw) still waits.
    assert DomainAction("draw", 0, _ref("cards")) in ENGINE.legal_actions(
        stepped.state, 0
    )


def test_one_target_still_opens_the_target_step() -> None:
    # An empty supply with one Spy on a post: the recall-first has one post
    # to take it from [Main pp. 11, 20] (the other two are boxed, as
    # Advanced Data Analysis leaves them).
    state = _recall_state()
    owner = state.players[0]
    post = owner.spy_post_ids[0]
    owner = replace(owner, spy_post_ids=(post,), spies_boxed=2)
    state = replace(
        state,
        config=replace(state.config, bloodlines=True, tech_module=True),
        players=(owner, *state.players[1:]),
    )
    recall = DomainAction("recall_spy", 0, _ref("spy"))
    assert recall in ENGINE.legal_actions(state, 0)

    picked = ENGINE.apply(state, recall).state

    assert ENGINE.legal_actions(picked, 0) == (
        DomainAction("choose_post", 0, (("post_id", post),)),
    )


def test_only_the_seat_sees_its_picked_effect() -> None:
    state, _ = _espionage_state()
    spy = DomainAction("place_spy", 0, _ref("spy"))

    picked = ENGINE.apply(state, spy).state

    own = ENGINE.observe(picked, 0)
    assert own.private is not None
    assert own.private.effect_pick == ((spy.action_id, spy.arguments),)
    for seat in (1, 2, 3):
        before, after = ENGINE.observe(state, seat), ENGINE.observe(picked, seat)
        assert replace(after, revision=before.revision) == before
        assert encode_player_view(replace(after, revision=before.revision)) == (
            encode_player_view(before)
        )
    # The seat's own observation reads the pick (observation v33).
    assert encode_player_view(own) != encode_player_view(
        replace(ENGINE.observe(state, 0), revision=own.revision)
    )


def test_the_pick_event_is_the_seats_alone() -> None:
    state, _ = _espionage_state()

    result = ENGINE.apply(state, DomainAction("place_spy", 0, _ref("spy")))

    (event,) = result.events
    assert event.kind == "effect_picked"
    assert event.visible_to == (0,)


def test_a_row_that_is_no_step_of_an_offered_action_is_refused() -> None:
    state, _ = _espionage_state()
    picked = ENGINE.apply(state, DomainAction("place_spy", 0, _ref("spy"))).state

    with pytest.raises(Exception, match="not legal"):
        ENGINE.apply(picked, DomainAction("draw", 0, _ref("cards")))


def test_the_steps_name_targets_by_their_kind() -> None:
    state, _ = _espionage_state()
    whole = next(w for w in ENGINE.whole_actions(state, 0) if w.action_id == _PLACE)

    path = path_of(state, whole)

    assert path == steps_for(whole, "espionage")
    assert path is not None
    assert [row.action_id for row in path] == ["place_spy", "choose_post"]
    assert first_step(state, whole) == path[0]


def _recall_state() -> GameState:
    state, _ = _espionage_state(spies_supply=0)
    return state


def test_a_recall_first_is_its_own_effect_row() -> None:
    state = _recall_state()

    rows = ENGINE.legal_actions(state, 0)

    # With an empty supply the Spy's recall comes first [Main pp. 11, 20].
    assert DomainAction("recall_spy", 0, _ref("spy")) in rows
    picked = ENGINE.apply(state, DomainAction("recall_spy", 0, _ref("spy"))).state
    assert {row.action_id for row in ENGINE.legal_actions(picked, 0)} == {
        "choose_post"
    }


def test_a_fixed_printed_card_is_the_one_card_that_offers_its_id() -> None:
    # Stage B3b-2: a Reveal choice id that no ``source`` names (one card
    # type produces it, ``reveal_turn.SOURCED_REVEAL_ACTION_IDS``) names its
    # card in the table instead; every card offering the id must be that
    # one, and every sourced id must read its card from ``source``.
    from dune_imperium.content.immortality.tleilaxu import tleilaxu_deck_instance_ids
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.content.uprising.personal_cards import (
        personal_card_for_instance,
    )
    from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
    from dune_imperium.content.uprising.starting_cards import (
        starting_deck_instance_ids,
    )
    from dune_imperium.rules.effect_steps import STEP_SPECS
    from dune_imperium.rules.reveal_turn import (
        REVEAL_CHOICE_EFFECT_ACTIONS,
        SOURCED_REVEAL_ACTION_IDS,
    )

    instances = (
        *imperium_deck_instance_ids(
            True, True, bloodlines=True, tech_module=True, immortality=True
        ),
        *tleilaxu_deck_instance_ids(True),
        *starting_deck_instance_ids(0, immortality=True, epic_game=True),
        *(f"reserve:{card_id}:0" for card_id in RESERVE_STACKS_BY_ID),
    )
    printers: dict[str, set[str]] = {}
    for instance in instances:
        card = personal_card_for_instance(instance)
        for effect in getattr(card, "reveal_choice_effects", ()):
            for action_id in REVEAL_CHOICE_EFFECT_ACTIONS[effect]:
                printers.setdefault(action_id, set()).add(card.card.card_id)
    checked = 0
    for action_id, cards in printers.items():
        spec = STEP_SPECS.get(action_id)
        if spec is None:
            continue
        assert isinstance(spec.printed, str)
        if action_id in SOURCED_REVEAL_ACTION_IDS:
            assert spec.printed == "source", action_id
        else:
            assert {spec.printed.removeprefix("=")} == cards, action_id
            checked += 1
    # Thirteen since stage B3d-3: Desert Power's refusal names its card too.
    assert checked == 13


def _reveal_frame_state(hand: tuple[str, ...], troops_conflict: int = 0) -> GameState:
    from tests.unit.rules.test_reveal_choices import _reveal, _state

    from dune_imperium.core import PlayerState

    owner = PlayerState(
        player_id=0,
        hand=hand,
        troops_supply=PlayerState(player_id=0).troops_supply - troops_conflict,
        troops_conflict=troops_conflict,
    )
    state = _state(owner)
    return _reveal(replace(state, reserve_stacks=(("prepare_the_way", 7),)))


def test_a_reveal_purchase_is_its_markets_acquire_row_then_the_card() -> None:
    # Stage B3b-2 (docs/stage-b-plan.md "B3b 세부 설계"): the Reveal frame
    # offers its effects effect first too; a purchase is one ``acquire`` row
    # per market, then the card (OQ-111 (2): one card still opens the step).
    from tests.unit.rules.test_reveal_choices import STARTERS

    revealed = _reveal_frame_state(STARTERS[:5])
    acquire = DomainAction(
        "acquire", 0, (("printed", "reserve"), ("source", "purchase"))
    )
    whole = DomainAction("acquire_reserve", 0, (("card_id", "prepare_the_way"),))
    assert acquire in ENGINE.legal_actions(revealed, 0)
    assert whole in ENGINE.whole_actions(revealed, 0)
    assert whole not in ENGINE.legal_actions(revealed, 0)

    picked = ENGINE.apply(revealed, acquire).state
    target = DomainAction("choose_reserve_card", 0, (("card_id", "prepare_the_way"),))
    # While the pick waits, only its targets are offered (no turn end).
    assert ENGINE.legal_actions(picked, 0) == (target,)
    bought = ENGINE.apply(picked, target).state
    assert bought == apply_whole(ENGINE, revealed, whole).state


def test_a_reveal_choice_row_names_the_card_that_printed_it() -> None:
    # A revealed card's choice: ``source=reveal_card`` and the card type,
    # then its target -- Calculus of Power's trash of another Emperor card.
    from tests.unit.rules.test_reveal_choices import _card

    calculus, corrinth = _card("calculus_of_power"), _card("corrinth_city")
    revealed = _reveal_frame_state((calculus, corrinth), troops_conflict=1)
    trash = DomainAction(
        "trash", 0, (("printed", "calculus_of_power"), ("source", "reveal_card"))
    )
    assert trash in ENGINE.legal_actions(revealed, 0)
    picked = ENGINE.apply(revealed, trash).state
    assert ENGINE.legal_actions(picked, 0) == (
        DomainAction("choose_personal_card", 0, (("card_id", corrinth),)),
    )
    assert path_of(
        revealed,
        DomainAction(
            "trash_reveal_card",
            0,
            (("card_id", corrinth), ("source", "calculus_of_power")),
        ),
    ) == (trash, DomainAction("choose_personal_card", 0, (("card_id", corrinth),)))


def test_an_intrigue_play_is_the_window_then_the_card_then_its_option() -> None:
    # Stage B3c-1 (docs/stage-b-plan.md "B3c 세부 설계"): ``play(ref=책략)`` ->
    # the card -> its option; one option still opens its step (OQ-111 (2)).
    from tests.unit.rules.test_intrigue import _intrigue, _turn_state

    from dune_imperium.core import PlayerState

    card = _intrigue("contingency_plan")
    state = _turn_state(PlayerState(player_id=0, intrigue_cards=(card,)))
    play = DomainAction("play", 0, (("printed", "plot"), ("source", "intrigue")))
    whole = DomainAction("play_intrigue", 0, (("card_id", card), ("option", 0)))
    assert play in ENGINE.legal_actions(state, 0)
    assert whole in ENGINE.whole_actions(state, 0)
    assert path_of(state, whole) == (
        play,
        DomainAction("choose_intrigue_card", 0, (("card_id", card),)),
        DomainAction("choose_option", 0, (("option", 0),)),
    )

    picked = ENGINE.apply(state, play).state
    chose = ENGINE.apply(
        picked, DomainAction("choose_intrigue_card", 0, (("card_id", card),))
    )
    # The card picked so far is the seat's alone (OQ-111 (4)).
    assert all(event.visible_to == (0,) for event in chose.events)
    assert ENGINE.legal_actions(chose.state, 0) == (
        DomainAction("choose_option", 0, (("option", 0),)),
    )
    option = DomainAction("choose_option", 0, (("option", 0),))
    played = ENGINE.apply(chose.state, option)
    assert played.state.players[0].resources.solari == 2
    assert played.state == apply_whole(ENGINE, state, whole).state


def test_a_combat_play_names_the_combat_window() -> None:
    from tests.unit.rules.test_intrigue import _combat_state, _intrigue

    from dune_imperium.core import PlayerState

    card = _intrigue("weirding_combat")
    state = _combat_state(
        PlayerState(
            player_id=0,
            intrigue_cards=(card,),
            troops_supply=PlayerState(player_id=0).troops_supply - 2,
            troops_conflict=2,
        )
    )
    rows = ENGINE.legal_actions(state, 0)
    assert DomainAction("play", 0, (("printed", "combat"), ("source", "intrigue"))) in (
        rows
    )
    assert DomainAction("pass_combat_intrigue", 0) in rows
    assert not any(row.action_id == "play_intrigue" for row in rows)


def test_agents_see_the_turn_frames_play_beside_its_placements_as_a_whole() -> None:
    # Stage B3c-1: the turn frame shows its Agent-turn card pick as
    # placements (B1) and, since it offers its other effects effect first,
    # those as the whole actions they stand for -- an agent never sees the
    # bare ``play`` row (the app AI answered it at random before this).
    from tests.unit.rules.test_intrigue import _intrigue, _turn_state

    from dune_imperium.agents.agent_turn_steps import placements_for_steps
    from dune_imperium.content.uprising.starting_cards import (
        starting_deck_instance_ids,
    )
    from dune_imperium.core import PlayerState

    card = _intrigue("contingency_plan")
    state = _turn_state(
        PlayerState(
            player_id=0, hand=starting_deck_instance_ids(0), intrigue_cards=(card,)
        )
    )
    rows = ENGINE.legal_actions(state, 0)
    shown = placements_for_steps(state, 0, rows)
    assert shown is not None
    wholes, answer = shown
    whole = DomainAction("play_intrigue", 0, (("card_id", card), ("option", 0)))
    assert whole in wholes
    assert not any(action.action_id == "play" for action in wholes)
    assert any(action.action_id == "agent_turn" for action in wholes)
    assert answer(whole) == DomainAction(
        "play", 0, (("printed", "plot"), ("source", "intrigue"))
    )


def _research_turn(*items: tuple[str, str, str]) -> GameState:
    """Seat 0's own turn frame with ``items`` waiting on it, oldest first."""

    from tests.unit.rules.test_immortality import _owner, _turn_state

    from dune_imperium.rules import turn_rows

    state: GameState | None = _turn_state(_owner())
    for item in items:
        assert state is not None
        state = turn_rows.queue(state, 0, item)
    assert state is not None
    return state


def _space_source(space_id: str) -> str:
    return f"round:1:player:0:agent:research:{space_id}"


def _research_row(verb: str, space_id: str, **extra: str) -> DomainAction:
    arguments = {"printed": space_id, "source": "research", **extra}
    return DomainAction(verb, 0, tuple(sorted(arguments.items())))


def test_a_research_icon_row_names_its_space_the_newest_first() -> None:
    # Stage B3c-2a (docs/stage-b-plan.md "B3c-2 세부 설계"): a research
    # pair's icon is printed on its research space. Two spaces waiting the
    # same icon resolve alike, so one row names the newest, as
    # ``apply_research_icon`` takes it (decision 3).
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.rules import turn_rows

    icon = turn_rows.RESEARCH_ICON
    state = _research_turn(
        (icon, _space_source("c3r3"), "specimen"),
        (icon, _space_source("c3r5"), "tleilaxu"),
        (icon, _space_source("c7r5"), "specimen"),
    )
    specimen = DomainAction("resolve_research_icon", 0, (("effect", "specimen"),))
    newest = _research_row("generate_specimens", "c7r5", icon="specimen")
    advance = _research_row("advance", "c3r5", icon="tleilaxu")
    assert path_of(state, specimen) == (newest,)
    offered = ENGINE.legal_actions(state, 0)
    assert {newest, advance} <= set(offered)
    assert specimen not in offered and specimen in ENGINE.whole_actions(state, 0)
    codec = ActionCodec(state.config)
    older = _research_row("generate_specimens", "c3r3", icon="specimen")
    for row in (newest, advance, older):
        codec.encode(row)

    taken = ENGINE.apply(state, newest)
    assert taken.state == apply_whole(ENGINE, state, specimen).state
    assert [event.event_id for event in taken.events] == [
        "round:1:player:0:research:c7r5:specimens"
    ]
    # The older one is still waiting, named by its own space.
    assert path_of(taken.state, specimen) == (older,)
    assert older in ENGINE.legal_actions(taken.state, 0)


@pytest.mark.parametrize(
    ("bonus", "whole", "rows"),
    [
        pytest.param(
            "influence_any",
            DomainAction("choose_research_influence", 0, (("faction", "fremen"),)),
            (
                _research_row("gain_influence", "c6r6"),
                DomainAction("choose_faction", 0, (("faction", "fremen"),)),
            ),
            id="c6r6",
        ),
        pytest.param(
            "seven_solari_for_two_tleilaxu",
            DomainAction("pay_research_bonus", 0),
            (_research_row("pay", "c8r6"),),
            id="c8r6",
        ),
    ],
)
def test_a_research_bonus_row_names_the_one_space_that_prints_it(
    bonus: str, whole: DomainAction, rows: tuple[DomainAction, ...]
) -> None:
    # Stage B3c-2a: each research bonus is printed on one space alone.
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.rules import turn_rows

    space = rows[0].arguments[0][1]
    assert isinstance(space, str)
    state = _research_turn(
        (turn_rows.RESEARCH_BONUS, _space_source(space), bonus)
    )
    state = replace(
        state,
        players=(
            replace(
                state.players[0],
                resources=replace(state.players[0].resources, solari=7),
            ),
            *state.players[1:],
        ),
    )
    assert whole in ENGINE.whole_actions(state, 0)
    assert path_of(state, whole) == rows
    assert rows[0] in ENGINE.legal_actions(state, 0)
    ActionCodec(state.config).encode(rows[0])
    stepped = state
    for row in rows:
        stepped = ENGINE.apply(stepped, row).state
    assert stepped == apply_whole(ENGINE, state, whole).state


def test_c7r3s_trash_names_its_space_then_the_intrigue_card() -> None:
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.rules import turn_rows

    state = _research_turn(
        (
            turn_rows.RESEARCH_BONUS,
            _space_source("c7r3"),
            "trash_intrigue_for_card_and_intrigue",
        )
    )
    card = state.intrigue_deck[0]
    state = replace(
        state,
        intrigue_deck=state.intrigue_deck[1:],
        players=(
            replace(state.players[0], intrigue_cards=(card,)),
            *state.players[1:],
        ),
    )
    whole = DomainAction(
        "trash_intrigue_for_research_bonus", 0, (("card_id", card),)
    )
    trash = _research_row("trash", "c7r3")
    assert path_of(state, whole) == (
        trash,
        DomainAction("choose_intrigue_card", 0, (("card_id", card),)),
    )
    ActionCodec(state.config).encode(trash)


def test_the_planetologist_intrigue_row_names_the_leader() -> None:
    # Stage B3c-2a: Arrakis Planetologist's Intrigue card is the leader's.
    from tests.unit.rules.test_immortality import _owner, _turn_state

    from dune_imperium import RulesetConfig
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.rules.planetologist import replace_sandworms

    # Liet Kynes is a Bloodlines leader.
    state = _turn_state(
        _owner(leader_id="liet_kynes"),
        config=RulesetConfig(immortality=True, bloodlines=True),
    )
    state = replace_sandworms(state, 0, 1, source="test").state
    whole = DomainAction("draw_planetologist_intrigue", 0)
    row = DomainAction(
        "draw",
        0,
        (("icon", "intrigue"), ("printed", "liet_kynes"), ("source", "leader")),
    )
    assert path_of(state, whole) == (row,)
    assert row in ENGINE.legal_actions(state, 0)
    assert whole not in ENGINE.legal_actions(state, 0)
    ActionCodec(state.config).encode(row)
    assert ENGINE.apply(state, row).state == apply_whole(ENGINE, state, whole).state


def test_a_conflict_reward_window_offers_its_icons_by_the_conflict_card() -> None:
    # Stage B3d-1 (docs/stage-b-plan.md "B3d 세부 설계"): a recipient's
    # reward window offers several effects at once, so each icon is an
    # effect row naming the Conflict card that prints the reward row.
    from tests.unit.rules.test_combat import _reward_state

    from dune_imperium.adapters import ActionCodec
    from dune_imperium.core import PlayerDecision
    from dune_imperium.rules.combat import resolve_combat_rewards
    from dune_imperium.rules.effect_steps import presents_steps

    conflict = "skirmish_desert_mouse"
    state = resolve_combat_rewards(_reward_state(conflict)).state
    top = state.decision_stack[-1]
    assert top.kind == "combat_reward_icons" and presents_steps(state)
    assert isinstance(top.decision, PlayerDecision)
    owner = top.decision.owner
    wholes = ENGINE.whole_actions(state, owner)
    assert wholes and all(w.action_id == "resolve_combat_reward_icon" for w in wholes)
    codec = ActionCodec(state.config)
    for whole in wholes:
        effect = dict(whole.arguments)["effect"]
        (row,) = path_of(state, whole) or ()
        assert dict(row.arguments) == {
            "icon": effect,
            "printed": conflict,
            "source": "conflict",
        }
        codec.encode(row)
        assert ENGINE.apply(state, row).state == apply_whole(ENGINE, state, whole).state
    assert set(ENGINE.legal_actions(state, owner)) == {
        first_step(state, whole) for whole in wholes
    }


def test_the_several_effect_windows_offer_their_effect_rows() -> None:
    # Stage B3d-1: the Conflict and Contract reward windows, an Intrigue
    # card's lines, Servo-Receivers' Signet frame, a research window's pair
    # and a Tech window's acquire icons offer effect rows: every legal row
    # is a whole action's next step, and encodes. A research bonus choice
    # and a Tech acquisition are one effect each, offered by their targets
    # since stage B3d-2a (the next test).
    from dune_imperium import RulesetConfig
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.agents import RandomAgent
    from dune_imperium.core import (
        ChanceDecision,
        ChanceResolver,
        GamePhase,
        PlayerDecision,
    )
    from dune_imperium.rules.effect_steps import presents_steps

    config = RulesetConfig(
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        arrakeen_scouts=True,
    )
    windows = {
        "combat_reward_icons",
        "contract_reward_icons",
        "intrigue_effects",
        "leader_signet",
        "research_bonus",
        "tech_acquisition",
    }
    codec = ActionCodec(config)
    seen: set[str] = set()
    for seed in range(6):
        state = ENGINE.reset(config, seed)
        chance = ChanceResolver(seed=seed)
        agents = [RandomAgent(seed=seed * 10 + seat) for seat in range(4)]
        for _ in range(6_000):
            if state.phase is GamePhase.FINISHED:
                break
            decision = ENGINE.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = ENGINE.apply(state, chance.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            legal = ENGINE.legal_actions(state, decision.owner)
            kind = str(state.decision_stack[-1].kind)
            if kind in windows and presents_steps(state):
                seen.add(kind)
                wholes = ENGINE.whole_actions(state, decision.owner)
                assert set(legal) == {first_step(state, w) for w in wholes}, kind
                for row in legal:
                    codec.encode(row)
            action = agents[decision.owner].choose_action(
                ENGINE.observe(state, decision.owner), legal
            )
            state = ENGINE.apply(state, action, legal_actions=legal).state
    assert "combat_reward_icons" in seen


@pytest.mark.parametrize(
    ("before", "space", "icons"),
    [
        pytest.param("c2r2", "c3r3", ("specimen", "trash"), id="c3r3"),
        pytest.param("c2r4", "c3r5", ("specimen", "tleilaxu"), id="c3r5"),
        pytest.param("c6r2", "c7r3", ("intrigue", "cards"), id="c7r3"),
    ],
)
def test_a_research_window_offers_each_icon_by_its_space(
    before: str, space: str, icons: tuple[str, ...]
) -> None:
    # Stage B3d-1: a research window outside its owner's turn ordering a
    # pair's icons (or c7r3's rewards once paid) offers each icon as an
    # effect row naming its research space -- the black trash and c7r3's
    # draws too, which no turn row offers (the 2026-10-20 review of B3d-1:
    # those rows were missing from the codec).
    from tests.unit.rules.test_immortality import _out_of_turn, _research_choices

    from dune_imperium.adapters import ActionCodec
    from dune_imperium.rules.effect_steps import presents_steps
    from dune_imperium.rules.immortality import (
        advance_research,
        apply_research_advance,
        apply_research_bonus,
        legal_research_bonus_actions,
    )

    held = "intrigue:ambush:1"
    fork = _out_of_turn(before, intrigue_cards=(held,))
    advanced = advance_research(fork, 0, source="test").state
    state = apply_research_advance(advanced, _research_choices(advanced)[space]).state
    if space == "c7r3":
        pay = next(
            action
            for action in legal_research_bonus_actions(state, 0)
            if action.action_id == "trash_intrigue_for_research_bonus"
        )
        state = apply_research_bonus(state, pay).state
    assert state.decision_stack[-1].kind == "research_bonus" and presents_steps(state)
    codec = ActionCodec(state.config)
    verbs = {
        "specimen": "generate_specimens",
        "tleilaxu": "advance",
        "trash": "trash",
        "intrigue": "draw",
        "cards": "draw",
    }
    rows = [
        DomainAction(
            verbs[icon],
            0,
            (("icon", icon), ("printed", space), ("source", "research")),
        )
        for icon in icons
    ]
    assert set(rows) <= set(ENGINE.legal_actions(state, 0))
    for row in rows:
        codec.encode(row)


def test_the_one_effect_windows_offer_their_targets() -> None:
    # Stage B3d-2a (D-1 (가)): a window opened for one effect shows its own
    # effect by its target rows alone -- the effect row that opened it
    # picked the effect -- while recalling a Spy first, an Intrigue card's
    # automatic rewards and an own effect with no target keep their effect
    # row. Every legal row is a whole action's next step and encodes, and a
    # pick begun by a target row (two Spies recalled, a Tech tile bought)
    # reaches the seat's observation.
    from dune_imperium import RulesetConfig
    from dune_imperium.adapters import ActionCodec
    from dune_imperium.agents import RandomAgent
    from dune_imperium.core import (
        ChanceDecision,
        ChanceResolver,
        GamePhase,
        PlayerDecision,
    )
    from dune_imperium.rules.action_shapes import Verb
    from dune_imperium.rules.effect_steps import (
        CHOOSE_ACTIONS,
        OFFERED_AS_WHOLE,
        STEP_SPECS,
        TARGET_SPECS,
        TARGET_STEP_FRAMES,
        presents_steps,
    )

    config = RulesetConfig(
        choam_module=True,
        leader_draft=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        arrakeen_scouts=True,
    )
    codec = ActionCodec(config)
    seen: set[str] = set()
    for seed in range(6):
        state = ENGINE.reset(config, seed)
        chance = ChanceResolver(seed=seed)
        agents = [RandomAgent(seed=seed * 10 + seat) for seat in range(4)]
        for _ in range(8_000):
            if state.phase is GamePhase.FINISHED:
                break
            decision = ENGINE.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = ENGINE.apply(state, chance.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            legal = ENGINE.legal_actions(state, decision.owner)
            kind = str(state.decision_stack[-1].kind)
            if kind in TARGET_STEP_FRAMES:
                assert presents_steps(state)
                seen.add(kind)
                wholes = ENGINE.whole_actions(state, decision.owner)
                assert set(legal) == {first_step(state, w) for w in wholes}, kind
                for whole in wholes:
                    spec = STEP_SPECS.get(whole.action_id)
                    if spec is not None and spec.verb in (
                        Verb.DECLINE,
                        Verb.CONFIRM_EMPTY,
                    ):
                        # Stage B3d-3: a refusal names the effect it answers.
                        row = first_step(state, whole)
                        assert row.action_id == spec.verb.value
                        assert "of" in dict(row.arguments)
                    if whole.action_id in TARGET_SPECS:
                        # A side branch a window still offers as it is (a
                        # mission's specimen return, stage B3d-2b).
                        row = first_step(state, whole)
                        assert row.action_id in CHOOSE_ACTIONS or (
                            row == whole and whole.action_id in OFFERED_AS_WHOLE
                        )
                for row in legal:
                    codec.encode(row)
                if picked_rows(state):
                    encode_player_view(ENGINE.observe(state, decision.owner))
            action = agents[decision.owner].choose_action(
                ENGINE.observe(state, decision.owner), legal
            )
            state = ENGINE.apply(state, action, legal_actions=legal).state
    assert {
        "acquisition_spy",
        "combat_reward_spy",
        "contract_market",
        "control_defense",
        "graft_partner",
        "intrigue_choice",
        "leader_draft",
        "navigation_setup",
        "research_advance",
        "spy_placement",
        # Stage B3d-2b: Arrakeen Scouts.
        "scouts_bid",
        "scouts_choice",
        "scouts_effect",
        "scouts_subcommittee",
    } <= seen


def _no_spy_in_supply(state: GameState, posts: tuple[str, ...]) -> GameState:
    from dune_imperium.rules.frames import replace_player

    owner = replace(state.players[0], spies_supply=0, spy_post_ids=posts)
    return replace(state, players=replace_player(state.players, owner))


def test_a_spy_window_names_what_opened_it_when_a_spy_is_recalled_first() -> None:
    # Stage B3d-2a: with the supply empty, recalling a Spy first [Main pp.
    # 11, 20] is another effect beside the window's own Spy, its row naming
    # what opened the window (the window records it, ``printer``); the
    # recalled post is its target, then the window's Spy is picked by its
    # post alone.
    from dune_imperium import RulesetConfig
    from dune_imperium.rules.action_shapes import Source, printer_value
    from dune_imperium.rules.spy_moves import spy_placement_frame
    from dune_imperium.rules.tech import ALL_POST_IDS

    posts = ALL_POST_IDS[:3]
    state = spy_placement_frame(
        _no_spy_in_supply(ENGINE.reset(RulesetConfig(), 0), posts),
        0,
        ALL_POST_IDS,
        source="test",
        printer=printer_value(Source.TECH, "panopticon"),
    )
    recall = DomainAction(
        "recall_spy", 0, (("printed", "panopticon"), ("source", "tech"))
    )
    # Its empty confirmation names the same window and the effect it answers
    # (stage B3d-3).
    assert set(ENGINE.legal_actions(state, 0)) == {
        recall,
        DomainAction(
            "confirm_empty",
            0,
            (("of", "place_spy"), ("printed", "panopticon"), ("source", "tech")),
        ),
    }
    picked = ENGINE.apply(state, recall).state
    assert set(ENGINE.legal_actions(picked, 0)) == {
        DomainAction("choose_post", 0, (("post_id", post),)) for post in posts
    }
    recalled = ENGINE.apply(
        picked, DomainAction("choose_post", 0, (("post_id", posts[0]),))
    ).state
    assert recalled.players[0].spies_supply == 1
    assert recalled.decision_stack[-1].kind == "spy_placement"
    offered = ENGINE.legal_actions(recalled, 0)
    assert DomainAction("choose_post", 0, (("post_id", posts[0]),)) in offered
    assert {row.action_id for row in offered} <= {"choose_post", "recall_spy"}


def test_the_emperor_tracks_spy_window_names_the_track() -> None:
    # The Emperor strip prints the Influence 4 Spy [Main p. 7]: its window
    # records the track, the row of a recall first names it.
    from dune_imperium import RulesetConfig
    from dune_imperium.rules.spy_moves import _open_track_spy
    from dune_imperium.rules.tech import ALL_POST_IDS

    base = _no_spy_in_supply(ENGINE.reset(RulesetConfig(), 0), ALL_POST_IDS[:3])
    state = _open_track_spy(replace(base, pending_track_spies=((0, "test"),)), 0)
    assert DomainAction(
        "recall_spy", 0, (("printed", "emperor"), ("source", "influence_track"))
    ) in ENGINE.legal_actions(state, 0)


def test_a_recall_spy_slot_is_its_windows_own_effect() -> None:
    # Sleeper Unit's Recall Spy slot: the recall is the slot's own effect,
    # picked by its post alone; recalling first beside a Spy placement slot
    # keeps its effect row (the random walk above).
    from tests.unit.rules.test_bloodlines_cards import (
        CHOAM_BLOODLINES,
        _card,
        _intrigue,
        _owner,
        _play,
        _play_intrigue,
        _state,
    )

    card = _card("corrupt_bureaucrat")
    sleeper = _intrigue("sleeper_unit")
    post = "emperor-sardaukar-dutiful-service"
    base = replace(
        _state(
            _owner(
                hand=(card,),
                intrigue_cards=(sleeper,),
                spies_supply=2,
                spy_post_ids=(post,),
            ),
            CHOAM_BLOODLINES,
        ),
        face_up_contract_ids=("contract:deliver_supplies:0", "contract:harvest_3:0"),
    )
    played = _play(base, card, "assembly_hall")
    opened = apply_whole(ENGINE, played, _play_intrigue(sleeper, 1)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    assert set(ENGINE.legal_actions(opened, 0)) == {
        DomainAction("choose_post", 0, (("post_id", post),))
    }


def test_long_live_the_fighters_shows_the_card_to_draw_as_its_first_target() -> None:
    # Its one effect picks the card to draw and then the card to discard by
    # the same target row, in two decisions of its own frame (stage B3d-2a):
    # at the second the seat's view holds the first as its picked target, so
    # the two decisions differ in the seat's observation (the 2026-10-20
    # review of B3d-2a: they did not).
    from tests.unit.rules.test_agent_effects import (
        _action_to,
        _instance,
        _long_live_state,
    )

    from dune_imperium.adapters.observation_encoding import segment_slice
    from dune_imperium.rules.agent_turn import apply_agent_action

    first = _instance("dagger")
    cards = (first, _instance("convincing_argument"), _instance("reconnaissance"))
    state = _long_live_state((*cards, _instance("dune_the_desert_planet")))
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    ready = apply_whole(
        ENGINE, placed, DomainAction("resolve_agent_card_effect", 0)
    ).state
    assert ready.decision_stack[-1].kind == "long_live_fighters"
    assert set(ENGINE.legal_actions(ready, 0)) == {
        DomainAction("choose_personal_card", 0, (("card_id", card),))
        for card in cards
    }
    drawing = ENGINE.observe(ready, 0)
    assert drawing.private is not None and drawing.private.effect_pick == ()
    row = DomainAction("choose_personal_card", 0, (("card_id", first),))
    discarding = ENGINE.apply(ready, row).state
    view = ENGINE.observe(discarding, 0)
    assert view.private is not None
    assert view.private.effect_pick == (
        ("choose_personal_card", (("card_id", first),)),
    )
    # No other seat sees it.
    other = ENGINE.observe(discarding, 1)
    assert other.private is None or other.private.effect_pick == ()
    picked = segment_slice("private_effect_pick_personal")
    before = encode_player_view(drawing)[picked]
    after = encode_player_view(view)[picked]
    assert sum(before) == 0 and sum(after) == 1


def test_a_new_high_council_seat_joins_a_subcommittee_by_its_target() -> None:
    # Stage B3d-2b (D-3): the turn's subcommittee choice is the effect row
    # ``join`` that the Arrakeen Scouts rule for a new High Council seat
    # prints (docs/rules/arrakeen-scouts.md 4), and the window it opens
    # offers each joinable subcommittee by its target row.
    whole = DomainAction("choose_subcommittee", 0)
    assert steps_for(whole) == (
        DomainAction("join", 0, (("printed", "high_council"), ("source", "scouts"))),
    )
    joined = DomainAction("join_subcommittee", 0, (("subcommittee_id", "leverage"),))
    assert steps_for(joined, effect_row=False) == (
        DomainAction("choose_subcommittee", 0, (("subcommittee_id", "leverage"),)),
    )


def test_a_scouts_mission_shows_its_ways_and_its_plain_way() -> None:
    # A mission's part with several ways (a Contract to escort, recruiting)
    # is picked by its way's target row; the plain way names no target, so it
    # is the effect row of the mission (an own effect with no target, D-1).
    way = DomainAction("scouts_join_mission", 0, (("target", "recruit"),))
    plain = DomainAction("scouts_join_mission", 0, (("target", ""),))
    assert steps_for(way, effect_row=False) == (
        DomainAction("choose_mission", 0, (("target", "recruit"),)),
    )
    assert steps_for(plain, effect_row=False) == ()
    assert steps_for(plain, "prison_planet") == (
        DomainAction("join", 0, (("printed", "prison_planet"), ("source", "scouts"))),
    )


def test_a_scouts_specimen_return_is_a_recruit_steps_own_and_beside_a_mission() -> None:
    # Stage B3d-2b (the review of B3d-2b): a Scouts recruit step's specimen
    # top-up is the step's own choice, by its count's target row; beside a
    # mission's part it is Immortality's free return "at any time"
    # (OQ-050), a side branch offered as it is (``OFFERED_AS_WHOLE``).
    from tests.unit.agents.app_ai import test_app_ai_window_scouts as scouts

    from dune_imperium.rules.scouts_missions import offer_mission_join

    troops = scouts._troops(supply=1, garrison=8, specimens=3)
    recruit = scouts._effect(
        scouts._me(scouts._base(), **troops), "covert_operation", 2, step=1
    )
    assert recruit.decision_stack[-1].kind == "scouts_effect"
    offered = ENGINE.legal_actions(recruit, 0)
    assert offered and {row.action_id for row in offered} == {"choose_count"}
    mission = offer_mission_join(
        scouts._me(
            scouts._resources(scouts._base(), solari=4),
            **scouts._troops(supply=1, garrison=9, specimens=2),
        ),
        0,
        "weirding_warfare",
        source=scouts.SOURCE,
    ).state
    rows = set(ENGINE.legal_actions(mission, 0))
    assert DomainAction("scouts_return_specimens", 0, (("count", 1),)) in rows
    assert not any(row.action_id == "choose_count" for row in rows)


def test_a_refusal_names_the_effect_it_answers_and_its_place() -> None:
    # Stage B3d-3 (D-2): every refusal is ``decline`` and every empty
    # confirmation ``confirm_empty``, naming the effect answered by its verb
    # (``of``) and the place its own row names -- a Conflict reward's icon
    # read off its window, a research space's bonus, a leader, a Contract.
    assert steps_for(
        DomainAction("decline_combat_reward", 0),
        "battle_for_imperial_basin",
        icon="optional_spice",
    ) == (
        DomainAction(
            "decline",
            0,
            (
                ("icon", "optional_spice"),
                ("of", "pay"),
                ("printed", "battle_for_imperial_basin"),
                ("source", "conflict"),
            ),
        ),
    )
    assert steps_for(
        DomainAction("decline_combat_reward", 0),
        "battle_for_imperial_basin",
        icon="optional_recall_spies",
    )[0].arguments[1] == ("of", "recall_spy")
    assert steps_for(DomainAction("decline_research_bonus", 0), "c7r3") == (
        DomainAction(
            "decline", 0, (("of", "trash"), ("printed", "c7r3"), ("source", "research"))
        ),
    )
    assert steps_for(
        DomainAction("resolve_leader_signet_without_option", 0), "esmar_tuek"
    ) == (
        DomainAction(
            "confirm_empty",
            0,
            (("of", "choose"), ("printed", "esmar_tuek"), ("source", "leader")),
        ),
    )


@pytest.mark.parametrize("answered", ["lose_unit", "move_spy"])
def test_a_ghola_copying_holy_war_names_itself_in_the_opponents_windows(
    answered: str,
) -> None:
    # Ghola copies the other grafted card's Agent box, so the box's own card
    # names the effect, in its rows and in the windows it opens for the
    # opponents (Holy War's unit loss and Spy move): their empty
    # confirmations name Ghola, and the action catalog holds them (the
    # independent review of B3d-3 found them missing).
    from dune_imperium import RulesetConfig
    from dune_imperium.adapters import ActionCodec

    row = DomainAction(
        "confirm_empty",
        0,
        (("of", answered), ("printed", "ghola"), ("source", "agent_card")),
    )
    ActionCodec(RulesetConfig(bloodlines=True, immortality=True)).encode(row)
