"""A recall-first may only free a post the Spy can then be placed on.

"If you have no Spies in your supply when you need to place one, you may
first recall one of your Spies" [Main pp. 11, 20]. A post the owner shares
with another player's Spy (Deep Cover) stays occupied after the recall, so
recalling from it opens no placement; the Intrigue slot already offered only
posts the owner holds alone (``spy_placement.solo_occupied_post_ids``). The
Leader Signet's and the Agent box's restricted placements offered every
restricted post the owner held, and a recall from a shared one left no legal
action (heuristic mirror, all options, seed 543, round 9: Lady Margot
Fenring's Signet through Servo-Receivers, 2026-10-14).
"""

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.leader_abilities import (
    CITY_POST_IDS,
    _leader_spy_placement_actions,
    _listeners_spies,
)
from dune_imperium.rules.spy_moves import (
    legal_spy_placement_actions,
    spy_placement_frame,
)
from dune_imperium.rules.spy_placement import SpyOptions, spy_options

ENGINE = UprisingRulesEngine()
SHARED = "arrakis-research-station-spice-refinery"
SOLO = "arrakis-spice-refinery-arrakeen"


def _seat(seat: int, posts: tuple[str, ...], hand: tuple[str, ...] = ()) -> PlayerState:
    return PlayerState(
        player_id=seat,
        hand=hand,
        spy_post_ids=posts,
        spies_supply=3 - len(posts),
    )


def _state(*seats: PlayerState) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=seats,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def test_a_leader_spy_recall_skips_a_post_shared_with_another_spy() -> None:
    """Lady Margot Fenring's Arrakis Informant places on a City post. Every
    City post is taken; the owner's Spy shares one with seat 2's: only the
    post the owner holds alone is offered for the recall-first."""

    state = _state(
        _seat(0, (SHARED, SOLO, "bene-gesserit-espionage-secrets")),
        _seat(1, ("arrakis-research-station-sietch-tabr",)),
        _seat(2, (SHARED,)),
        _seat(3, ()),
    )
    actions = _leader_spy_placement_actions(state, 0, {}, CITY_POST_IDS)
    assert actions == (
        DomainAction("decline_leader_spy_placement", 0),
        DomainAction("recall_spy_for_leader_placement", 0, (("post_id", SOLO),)),
    )


def test_an_agent_box_spy_recall_skips_a_post_shared_with_another_spy() -> None:
    """Reliable Informant places on an Emperor, Bene Gesserit or Fremen post.
    All three are taken and the owner's Spy on the Emperor one shares it:
    the recall-first is offered only from the Bene Gesserit post the owner
    holds alone."""

    informant = next(
        instance
        for instance in imperium_deck_instance_ids(False)
        if ":reliable_informant:" in instance
    )
    emperor = "emperor-sardaukar-dutiful-service"
    bene_gesserit = "bene-gesserit-espionage-secrets"
    state = _state(
        _seat(0, (emperor, bene_gesserit, SOLO), hand=(informant,)),
        _seat(1, (emperor,)),
        _seat(2, ("fremen-desert-tactics-fremkit",)),
        _seat(3, ()),
    )
    placement = next(
        action
        for action in executable_placements(state, 0)
        if len(action.arguments) == 2
    )
    state = apply_placement(ENGINE, state, placement).state
    recalls = {
        dict(action.arguments)["post_id"]
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "recall_spy_for_agent_card"
    }
    assert recalls == {bene_gesserit}


def test_listeners_recall_first_serves_the_paid_half_too() -> None:
    """Gaius Helen Mohiam's Listeners: "a Spy next to the Landsraad —OR— 1
    spice -> a Spy anywhere" [Gaius Helen Mohiam card]. With the supply
    empty and both Landsraad posts taken, a recall from the Landsraad post
    the owner shares opens no Landsraad placement, but with a spice it
    opens the paid half's: it is offered (an older engine's game recalled
    there, then paid; v145 corpus records no-immortality.ha.6 and
    full.h4.164). Without the spice only recalls that open a Landsraad post
    remain."""

    high_council = "landsraad-high-council-imperial-privilege-swordmaster"
    assembly = "landsraad-assembly-hall-gather-support"
    owner_posts = (high_council, "arrakis-imperial-basin", "arrakis-deep-desert")

    def recalls(spice: int) -> set[str]:
        owner = _seat(0, owner_posts)
        state = _state(
            PlayerState(
                player_id=0,
                spy_post_ids=owner.spy_post_ids,
                spies_supply=0,
                resources=Resources(spice=spice),
            ),
            _seat(1, ("arrakis-research-station-sietch-tabr",)),
            _seat(2, (assembly,)),
            _seat(3, (high_council,)),
        )
        return {
            str(dict(action.arguments)["post_id"])
            for action in _listeners_spies(state, 0, {})
            if action.action_id == "recall_spy_for_leader_placement"
        }

    assert recalls(1) == set(owner_posts)
    assert recalls(0) == set()


def test_every_spy_host_reads_one_recall_first_rule() -> None:
    """cleanup-2d: one decision for every host (``spy_options``). With an
    empty supply the pass-up comes first, then the recalls that open a post:
    with a free post any Spy, else a post the owner holds alone; after a
    recall-first the pass-up is gone; with nothing to place or recall a host
    passes or (``stuck_passes`` off: an Agent box, a Leader) waits."""

    state = _state(
        _seat(0, (SHARED, SOLO, "bene-gesserit-espionage-secrets")),
        _seat(1, ("arrakis-research-station-sietch-tabr",)),
        _seat(2, (SHARED,)),
        _seat(3, ()),
    )
    city = frozenset((SHARED, SOLO, "arrakis-research-station-sietch-tabr"))
    assert spy_options(state, 0, city) == SpyOptions(recall=(SOLO,), pass_up=True)
    assert spy_options(state, 0, city, recalled=True) == SpyOptions(recall=(SOLO,))
    assert spy_options(state, 3, city) == SpyOptions(pass_up=True)
    assert spy_options(state, 3, city, stuck_passes=False) == SpyOptions()
    free = spy_options(state, 0)
    assert free.pass_up and free.recall == state.players[0].spy_post_ids


def test_the_shared_placement_frame_recalls_a_spy_that_frees_its_post() -> None:
    """The shared placement frame (Emperor track, Panopticon, In High
    Places): every allowed post taken and the supply empty, a recall of the
    owner's Spy holding an allowed post alone opens a placement, so it is
    offered beside the pass-up -- "먼저 회수는 그 회수로 놓을 수 있는 칸이
    생길 때만 제시한다" (OQ-057 (14) addition 2026-10-14). The frame used to
    offer only the pass-up there (cleanup-2d)."""

    allowed = (SOLO, "arrakis-research-station-sietch-tabr")
    state = spy_placement_frame(
        _state(
            _seat(0, (SOLO, "bene-gesserit-espionage-secrets", SHARED)),
            _seat(1, ("arrakis-research-station-sietch-tabr",)),
            _seat(2, ()),
            _seat(3, ()),
        ),
        0,
        allowed,
        source="test",
        printer=printer_value(Source.TECH, "panopticon"),
    )
    assert legal_spy_placement_actions(state, 0) == (
        DomainAction("decline_spy_placement", 0),
        DomainAction("recall_spy_for_placement", 0, (("post_id", SOLO),)),
    )
    recalled = apply_whole(ENGINE, 
        state, DomainAction("recall_spy_for_placement", 0, (("post_id", SOLO),))
    ).state
    assert legal_spy_placement_actions(recalled, 0) == (
        DomainAction("place_spy_on_space", 0, (("post_id", SOLO),)),
    )
