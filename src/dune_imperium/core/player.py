"""Authoritative per-player state and component invariants."""

from dataclasses import dataclass
from typing import ClassVar

from dune_imperium.core.dataclass_copy import positional_dataclass_replace


@dataclass(frozen=True, slots=True)
class Resources:
    """Spendable resources held by one player."""

    solari: int = 0
    spice: int = 0
    water: int = 1

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("player resources must not be negative")


@dataclass(frozen=True, slots=True)
class Influence:
    """Influence positions in fixed rules order."""

    emperor: int = 0
    spacing_guild: int = 0
    bene_gesserit: int = 0
    fremen: int = 0

    def __post_init__(self) -> None:
        if (
            min(
                self.emperor,
                self.spacing_guild,
                self.bene_gesserit,
                self.fremen,
            )
            < 0
        ):
            raise ValueError("influence must not be negative")
        if (
            max(
                self.emperor,
                self.spacing_guild,
                self.bene_gesserit,
                self.fremen,
            )
            > 6
        ):
            raise ValueError("influence cannot exceed the top of its track")


@positional_dataclass_replace
@dataclass(frozen=True, slots=True)
class PlayerState:
    """All public and private state owned by one player."""

    player_id: int
    leader_id: str | None = None
    # Face-up side of a double-sided Leader; equals leader_id for the rest.
    leader_face_id: str | None = None
    victory_points: int = 1
    resources: Resources = Resources()
    influence: Influence = Influence()
    agents_available: int = 2
    agent_locations: tuple[str, ...] = ()
    swordmaster_acquired: bool = False
    # The original game's Mentat, taken this round: "this round, you may use
    # it as one of your Agents" [DI p. 18], one Agent more until Recall
    # returns it to its space [DI p. 13]. Which placed Agent is the Mentat is
    # not told apart (OQ-139).
    mentat: bool = False
    # Troops an Influence track bonus recruited this turn (the original
    # board's Emperor track, docs/base-game-and-ix-plan.md 15.3): they deploy
    # with the turn's other recruits ("이번 turn에 recruit한 troop 전부",
    # docs/rules/imperium-base.md 7) and live on the seat, not the turn's
    # frame, which the Influence gain's callers write back afterwards.
    track_troops_recruited_turn: int = 0
    # The original game's Baron Harkonnen: the two Factions chosen in secret
    # before the first round (his alone until revealed) and whether
    # Masterstroke has revealed them, once per game (OQ-115).
    masterstroke_factions: tuple[str, ...] = ()
    masterstroke_revealed: bool = False
    # The original game's The Voice: the board spaces this seat may not send
    # its next Agent to ("Opponents can't send their next Agents there this
    # round" [The Voice card]). Each is lifted, with every other, by the
    # seat's next Agent placement anywhere (a turn passed without one, a
    # Reveal turn, keeps them) and all clear when the round ends (OQ-116,
    # user ruling B 2026-10-22). A public marker, no hidden information.
    voice_blocked_space_ids: tuple[str, ...] = ()
    # The original game's Infiltrate: enemy Agents don't block this seat's
    # next Agent at board spaces this turn [Infiltrate card]. Set by the
    # Plot, spent by the turn's Agent placement, gone when any turn opens.
    enemy_agents_ignored_turn: bool = False
    troops_supply: int = 9
    troops_garrison: int = 3
    troops_conflict: int = 0
    # Arrakeen Scouts: troops parked on the board by missions until their
    # seat collects them (``GameState.scouts_parked`` says where).
    troops_parked: int = 0
    # Troops stored on the Bene Gesserit area of the board as memories
    # (Lady Jessica's Spice Agony).
    memories: int = 0
    sandworms_conflict: int = 0
    spies_supply: int = 3
    spy_post_ids: tuple[str, ...] = ()
    alliance_faction_ids: tuple[str, ...] = ()
    control_space_ids: tuple[str, ...] = ()
    combat_strength: int = 0
    units_deployed_turn: int = 0
    # The most units deployed this turn that stood in the Conflict together:
    # a retreat leaves it, an OQ-029 withdrawal lowers it (OQ-016; read by
    # ``UnitsDeployedThisTurnAtLeast``).
    units_deployed_peak: int = 0
    # Deployed-unit count a played card already used as its condition this
    # turn (Distraction, Coercive Negotiation); a withdrawal may not drop
    # below it (OQ-029).
    units_deployed_committed: int = 0
    spice_at_turn_start: int = 0
    spice_spent_turn: int = 0
    has_revealed: bool = False
    high_council: bool = False
    maker_hooks: bool = False
    # Position of the Feyd token on the printed Training track; only used by
    # the Feyd-Rautha Harkonnen Leader and left on the start space otherwise.
    feyd_track_space: str = "start"
    # Bloodlines Sardaukar Commanders: a "troop" worth 2 strength that returns
    # to the supply after Combat and is recruited from the supply only by
    # paying 2 Solari once per turn [Bloodlines p. 4]. All zero without the
    # ``bloodlines`` option.
    commanders_supply: int = 0
    commanders_garrison: int = 0
    commanders_conflict: int = 0
    # Skill tile instances in the supply (public) [Bloodlines p. 4]; at most
    # one of each Skill identity.
    skill_ids: tuple[str, ...] = ()
    # Whether the once-per-turn paid Commander recruit was used this turn.
    commander_recruited_turn: bool = False
    # Contracts completed during the current turn (Mercantile Affairs).
    contracts_completed_turn: int = 0
    # Contract icons this turn that found nothing they could take. The market
    # was not empty -- so the printed two-Solari conversion does not apply,
    # its condition being "if all contracts have been taken by players"
    # [Main p. 16] -- but every face-up token was unreachable, which happens
    # when only the Bloodlines Immediate is left and there is no Intrigue card
    # to trash [Bloodlines p. 2]. The icon waits here until the turn ends,
    # resolving if the owner gains an Intrigue meanwhile and fizzling with no
    # reward otherwise (OQ-059).
    held_contract_icons: int = 0
    # Troops a recruit and specimens a specimen icon could not take from an
    # empty supply. When troops come back to this seat's supply later in the
    # same player turn (a lost troop, a returned or paid specimen, Other
    # Memories), the engine takes the shortfall from them at once, troops
    # first (OQ-030, OQ-049; user ruling 2026-10-04 following the Steam app).
    # Every seat's count clears when a turn opens and is dropped whenever no
    # turn is open (``rules.shortfall``).
    ungained_troops: int = 0
    ungained_specimens: int = 0
    # Suspensor Suits troops the supply could not cover: made up the same way
    # and deployed to the Conflict as they come (OQ-042, user re-ruling
    # 2026-10-25), after the recruit shortfall and before the specimens.
    ungained_conflict_troops: int = 0
    # Turn-scoped Plot modifiers (Bloodlines): Honor Guard's Commander
    # discount, Insider Information's requirement waiver, and the Agent icon
    # Emperor's Invitation grants to the card played this turn ("" = none).
    commander_discount_turn: int = 0
    ignores_influence_requirements_turn: bool = False
    granted_agent_icon_turn: str = ""
    # A Combat icon gained before this turn's Agent placement (Adaptive
    # Tactics played from the turn frame): the placement deploys as if to a
    # Combat space [Bloodlines pp. 5, 12].
    combat_icon_turn: bool = False
    # Urgent Shigawire (Bloodlines): the next Bene Gesserit card played this
    # round has every Agent icon and draws a card; cleared at Round Start.
    bene_gesserit_boost_pending: bool = False
    # Chani's Tactics token: index on her printed eleven-space track (0 for
    # every other Leader) [Chani card] [Bloodlines p. 12].
    tactics_track_space: int = 0
    # Duncan Idaho's Into the Fray: the Agent sent this turn fighting in the
    # Conflict as a unit that cannot retreat (0 or 1) [Duncan Idaho card].
    agent_in_conflict: int = 0
    # Piter De Vries' face-down Twisted Intrigue deck (hidden order; the
    # size is public) [Piter De Vries card].
    twisted_deck: tuple[str, ...] = ()
    # Steersman Y'rkoon's Navigation cards [Steersman Y'rkoon card]: the
    # face-down slots (known to the owner, in play order), the cards already
    # played (public), and the cards returned to the box (hidden). While one
    # resolves, its slot number and the Faction that triggered it.
    navigation_slots: tuple[str, ...] = ()
    navigation_played: tuple[str, ...] = ()
    navigation_box: tuple[str, ...] = ()
    navigation_active_slot: int = 0
    navigation_trigger_faction: str = ""
    # Navigation card 3 from slot 4: Persuasion at every later Reveal.
    reveal_persuasion_bonus: int = 0
    # Hungry for Spice fired this turn, and a draw it earned that the engine
    # has not handed out yet: a reshuffle was pending, or the turn closed
    # straight into the same seat's next turn (OQ-063).
    hungry_for_spice_granted_turn: bool = False
    hungry_for_spice_owed: bool = False
    # The Skill strength currently folded into ``combat_strength`` so the
    # running total can be re-derived when a Skill condition changes.
    skill_strength_applied: int = 0
    # Tech Module [Bloodlines pp. 6-7]: the Tech tiles in the supply
    # (public), the ones flipped face down this round (a subset, returned
    # face up at Round Start), Kota Odax's face-down Secret Project tile
    # (identity known to the owner only; "" when none) and the Spies
    # returned to the box by Advanced Data Analysis. All empty or zero
    # without the ``tech_module`` option.
    tech_ids: tuple[str, ...] = ()
    tech_flipped: tuple[str, ...] = ()
    secret_project_tech_id: str = ""
    spies_boxed: int = 0
    # Spies recalled since this seat's turn opened (Spy Drones' "if you
    # recalled a Spy this turn") and Intrigue cards gained this turn that
    # Suspensor Suits still has to answer with a deployed troop.
    spies_recalled_turn: int = 0
    suspensor_owed: int = 0
    # Cards owed by CHOAM Transports (a contract completed outside the seat's
    # own turn) and Planetary Array (a Conflict won), drawn by the engine
    # after the transition so a reshuffle never lands inside another
    # effect's frame bookkeeping.
    tech_cards_owed: int = 0
    # Draws a trigger earned during this seat's own Agent or Reveal turn,
    # each waiting as the seat's own step (``draw_owed_intrigue`` /
    # ``draw_owed_card``) before the turn ends, as (deck "intrigue" or
    # "card", origin key, event source), oldest first (``rules.owed_draws``;
    # user ruling 2026-10-10, OQ-106): in any order with the turn's other
    # steps, or, for an immediate origin (``frames.draw_is_immediate``), as
    # the seat's very next step. Public: only the count and origin, never a
    # card.
    owed_draws: tuple[tuple[str, str, str], ...] = ()
    # Immortality [Immortality pp. 4-8, 12]: the research token's space on
    # the Bene Tleilax board ("" without the option), the Tleilaxu token's
    # space (0 = start), the troops resting in the Axolotl tanks as
    # specimens, and the once-per-game Family Atomics token.
    research_space: str = ""
    tleilaxu_space: int = 0
    specimens: int = 0
    family_atomics: bool = False
    # Tleilaxu Puppet: Persuasion granted for this round's Reveal turn only
    # (cleared at Round Start).
    reveal_persuasion_round_bonus: int = 0
    # Recruitment Mission: "You may put cards you acquire on top of your deck"
    # during this round's Reveal turn of the owner [FAQ p. 3]; effective only
    # while the owner's own Reveal turn is open, cleared when it ends and at
    # Round Start. Public, and observed since v38 (``PublicPlayerView``): the
    # Reveal shop offers the twin rows, and a network deciding a Reveal reads
    # the flag.
    acquire_to_deck_top_round: bool = False
    # Chairdog: grafted cards that return from play to the hand when the
    # owner's Reveal turn starts [card face].
    chairdog_return_card_ids: tuple[str, ...] = ()
    # Usurp: the Imperium Row card grafted without acquiring it; it leaves
    # the game when the Agent turn closes [card face].
    usurped_row_card_id: str = ""
    # Rise of Ix (docs/rules/rise-of-ix.md; plan 17.8, observation v39). Every
    # field below defaults to "absent" and stays so in every game without the
    # ``rise_of_ix`` option (``simulation.invariants``), so those games' state
    # hashes, saves and records are what they were before the fields existed
    # (``HASH_OMITTED_AT_DEFAULT``). Stage P4a only adds them; stages P4b, P4c
    # and P4e set them.
    # The seat's two dreadnoughts [Rise of Ix p. 6]: in its supply, its
    # garrison and the Conflict (one on a Control space is in
    # ``GameState.dreadnought_control``). The supply defaults to 0, not the
    # printed two: Rise of Ix's setup gives them [Rise of Ix p. 3]
    # (rise-of-ix.md 3 item 5), so a game without it holds none.
    dreadnoughts_supply: int = 0
    dreadnoughts_garrison: int = 0
    dreadnoughts_conflict: int = 0
    # The Freighter's space on the Shipping track, 0 the bottom (its setup
    # space) to 3 the top [Rise of Ix p. 5] (rise-of-ix.md 5).
    freighter_space: int = 0
    # Troops sent from the supply to the Ix board as Negotiators [Rise of Ix
    # p. 4] (rise-of-ix.md 4); they count among the seat's 12 troops.
    negotiators: int = 0
    # Tessia Vernius' Careful Observation: the Influence tracks (Faction ids)
    # still holding her Snooper token, each on its track's Influence 2 space
    # [Tessia Vernius card] (rise-of-ix.md 10). Public.
    snooper_faction_ids: tuple[str, ...] = ()
    # Ilesa Ecaz's One Step Ahead: the card set aside from the hand at Round
    # Start, face down -- its identity is the owner's alone until it returns
    # to the hand at the start of her second turn [Ilesa Ecaz card]
    # (rise-of-ix.md 10, 13); "" when none. Every seat still counts it in her
    # deck pool (plan 17.8 review item 1).
    set_aside_card_id: str = ""
    # Whether the set-aside card came back to the hand at this turn's start,
    # its bonus waiting for an Agent sent with it [Ilesa Ecaz card]; and the
    # turns this seat has finished this round, which says which turn is the
    # second (a pass without an Agent and Weirding Way's extra turn count,
    # OQ-119). Both public; kept at 0 outside a Rise of Ix game.
    set_aside_returned_turn: bool = False
    turns_finished_round: int = 0
    # Intrigue cards this seat knows that are hidden from another seat, by
    # instance: the deck's top card Viscount Hundro Moritani put back
    # [Hundro Moritani card], the cards it put on the deck's bottom with Court
    # Intrigue or Sonic Snoopers [Rise of Ix p. 10] [FAQ p. 2], and such a
    # card once another seat drew it (rise-of-ix.md 13; plan 17.8 review
    # items 2 and 6). Each entry is in the Intrigue deck or in another seat's
    # held Intrigue (``simulation.invariants``). Its place -- the deck's top,
    # its depth from the bottom (the order the seat put the cards there), or
    # the seat holding it -- is read from those zones, so the record keeps no
    # order of its own to go stale. An entry leaves when its card reaches a
    # public zone or this seat's own hand, and a reshuffle of the Intrigue
    # deck forgets the deck's entries.
    known_intrigue_ids: tuple[str, ...] = ()
    deck: tuple[str, ...] = ()
    # The deck's top cards every seat knows, top first (OQ-145, user ruling
    # 2026-10-28): cards put face up on top of the deck (Bypass Protocol,
    # Recruitment Mission, a Tleilaxu card with the first genetic marker)
    # are public until they are drawn or the deck is shuffled. Between
    # transitions ``deck[:len(deck_public_top)] == deck_public_top``
    # (``simulation.invariants``); ``rules.deck_top`` places, settles and
    # clears it, and a drawn card moves on into ``hand_public``.
    deck_public_top: tuple[str, ...] = ()
    hand: tuple[str, ...] = ()
    # Hand cards whose identity every seat already knows because they
    # entered the hand through a public move (acquired face up from the
    # Imperium Row or Reserve straight to hand, or returned from in play)
    # instead of a face-down draw. Under OQ-010 ("once revealed, information
    # stays re-checkable") they remain public until they leave the hand;
    # ``__post_init__`` drops any entry no longer in ``hand`` so a card that
    # is played, discarded, or revealed and later redrawn is hidden again.
    hand_public: tuple[str, ...] = ()
    discard_pile: tuple[str, ...] = ()
    in_play: tuple[str, ...] = ()
    trashed: tuple[str, ...] = ()
    intrigue_cards: tuple[str, ...] = ()
    intrigue_faceup: tuple[str, ...] = ()
    imperium_set_aside: tuple[str, ...] = ()
    objective_ids: tuple[str, ...] = ()
    won_conflict_ids: tuple[str, ...] = ()
    face_down_battle_card_ids: tuple[str, ...] = ()
    active_contract_ids: tuple[str, ...] = ()
    completed_contract_ids: tuple[str, ...] = ()

    # Fields added after saves and records already held state hashes, left
    # out of the canonical state hash at their default
    # (``core.state.canonical_state_hash``).
    HASH_OMITTED_AT_DEFAULT: ClassVar[frozenset[str]] = frozenset(
        {
            "mentat",
            "track_troops_recruited_turn",
            "masterstroke_factions",
            "masterstroke_revealed",
            "voice_blocked_space_ids",
            "enemy_agents_ignored_turn",
            "acquire_to_deck_top_round",
            "deck_public_top",
            # Rise of Ix (observation v39, stage P4a).
            "dreadnoughts_supply",
            "dreadnoughts_garrison",
            "dreadnoughts_conflict",
            "freighter_space",
            "negotiators",
            "snooper_faction_ids",
            "set_aside_card_id",
            "set_aside_returned_turn",
            "turns_finished_round",
            "known_intrigue_ids",
        }
    )

    @property
    def units_in_conflict(self) -> int:
        """Return every unit in the Conflict: troops, sandworms, Commanders."""

        return (
            self.troops_conflict
            + self.sandworms_conflict
            + self.commanders_conflict
            + self.agent_in_conflict
        )

    @property
    def commanders_total(self) -> int:
        """Return the Sardaukar Commanders this player owns anywhere."""

        return (
            self.commanders_supply + self.commanders_garrison + self.commanders_conflict
        )

    def __post_init__(self) -> None:
        if self.player_id < 0:
            raise ValueError("player_id must not be negative")
        quantities = (
            self.victory_points,
            self.agents_available,
            self.troops_supply,
            self.troops_garrison,
            self.troops_conflict,
            self.memories,
            self.sandworms_conflict,
            self.spies_supply,
            self.combat_strength,
            self.units_deployed_turn,
            self.units_deployed_peak,
            self.units_deployed_committed,
            self.spice_at_turn_start,
            self.spice_spent_turn,
            self.commanders_supply,
            self.commanders_garrison,
            self.commanders_conflict,
            self.skill_strength_applied,
            self.contracts_completed_turn,
            self.held_contract_icons,
            self.ungained_troops,
            self.ungained_specimens,
            self.ungained_conflict_troops,
            self.commander_discount_turn,
            self.spies_boxed,
            self.spies_recalled_turn,
            self.suspensor_owed,
            self.tech_cards_owed,
            self.tleilaxu_space,
            self.specimens,
            self.reveal_persuasion_round_bonus,
            self.dreadnoughts_supply,
            self.dreadnoughts_garrison,
            self.dreadnoughts_conflict,
            self.freighter_space,
            self.negotiators,
            self.turns_finished_round,
        )
        if min(quantities) < 0:
            raise ValueError("player component quantities must not be negative")
        # A seat is copied several times per engine step, so the expansion
        # collections are only scanned once something is in them; empty ones
        # satisfy every check here by construction.
        if self.skill_ids:
            if len(self.skill_ids) != len(set(self.skill_ids)):
                raise ValueError("a Skill tile cannot be held twice")
            skill_identities = tuple(
                instance_id.split(":")[1] for instance_id in self.skill_ids
            )
            if len(skill_identities) != len(set(skill_identities)):
                raise ValueError("a player cannot hold two copies of one Skill")
        if self.tech_ids or self.tech_flipped:
            if len(self.tech_ids) != len(set(self.tech_ids)):
                raise ValueError("a Tech tile cannot be held twice")
            if not set(self.tech_flipped) <= set(self.tech_ids) or len(
                self.tech_flipped
            ) != len(set(self.tech_flipped)):
                raise ValueError("flipped Tech tiles must be held tiles")
        # Rise of Ix: two dreadnoughts a seat (one on a Control space is the
        # game's, ``GameState.dreadnought_control``) [Rise of Ix p. 6], and a
        # Shipping track of three spaces above the bottom [Rise of Ix p. 5].
        if (
            self.dreadnoughts_supply
            + self.dreadnoughts_garrison
            + self.dreadnoughts_conflict
            > 2
        ):
            raise ValueError("a player has only two dreadnoughts")
        if self.freighter_space > 3:
            raise ValueError("the Freighter's top space is the third")
        if self.snooper_faction_ids and len(self.snooper_faction_ids) != len(
            set(self.snooper_faction_ids)
        ):
            raise ValueError("a track holds one Snooper token")
        if self.known_intrigue_ids and len(self.known_intrigue_ids) != len(
            set(self.known_intrigue_ids)
        ):
            raise ValueError("an Intrigue card is known once")

        active_agents = (3 if self.swordmaster_acquired else 2) + self.mentat
        if (
            self.agents_available + len(self.agent_locations) + self.agent_in_conflict
            != active_agents
        ):
            raise ValueError("available and placed agents must equal active agents")
        # Into the Fray may send more than one Agent into the Conflict in a
        # round when Servo-Receivers grants a second Signet use (OQ-037(e));
        # the agent total above bounds the count.
        if self.agent_in_conflict < 0 or self.tactics_track_space < 0:
            raise ValueError("Leader token positions must be non-negative")
        # Two Agents of one seat may share a space: the original game's
        # Kwisatz Haderach "can be sent to a space holding my other Agent"
        # ("Kwisatz Haderach는 내 다른 Agent가 있는 칸에도 보낼 수 있다",
        # docs/rules/imperium-base.md 16). Every other placement still skips
        # a space the seat holds (``rules.agent_turn``).
        if len(self.voice_blocked_space_ids) != len(set(self.voice_blocked_space_ids)):
            raise ValueError("a space cannot be blocked twice for a player")
        # Specimens are troops from the supply in the Axolotl tanks
        # [Immortality p. 8], and Negotiators troops from the supply on the
        # Ix board [Rise of Ix p. 4].
        if (
            self.troops_supply
            + self.troops_garrison
            + self.troops_conflict
            + self.memories
            + self.specimens
            + self.troops_parked
            + self.negotiators
            != 12
        ):
            raise ValueError("a player must always account for all 12 troops")
        # Advanced Data Analysis returns a Spy to the box [Tech tile face].
        if self.spies_supply + len(self.spy_post_ids) + self.spies_boxed != 3:
            raise ValueError("a player must always account for all three spies")
        if len(self.spy_post_ids) != len(set(self.spy_post_ids)):
            raise ValueError("a player cannot place two spies on one post")
        if len(self.alliance_faction_ids) != len(set(self.alliance_faction_ids)):
            raise ValueError("a player cannot hold one Faction Alliance twice")
        if any(not faction_id for faction_id in self.alliance_faction_ids):
            raise ValueError("Alliance faction IDs must not be empty")
        if len(self.control_space_ids) > 3:
            raise ValueError("a player has only three control markers")
        if len(self.control_space_ids) != len(set(self.control_space_ids)):
            raise ValueError("control marker locations must be unique")
        battle_card_ids = (*self.objective_ids, *self.won_conflict_ids)
        if len(battle_card_ids) != len(set(battle_card_ids)):
            raise ValueError("battle cards in a player's supply must be unique")
        if not set(self.face_down_battle_card_ids) <= set(battle_card_ids):
            raise ValueError("face-down battle cards must be in the player's supply")
        if len(self.face_down_battle_card_ids) != len(
            set(self.face_down_battle_card_ids)
        ):
            raise ValueError("a battle card cannot be face-down twice")

        contracts = (*self.active_contract_ids, *self.completed_contract_ids)
        if len(contracts) != len(set(contracts)):
            raise ValueError("a Contract cannot be active and completed")

        imperium_cards = (
            *self.deck,
            *self.hand,
            *self.discard_pile,
            *self.in_play,
            *self.trashed,
            *self.imperium_set_aside,
            *((self.set_aside_card_id,) if self.set_aside_card_id else ()),
        )
        if len(imperium_cards) != len(set(imperium_cards)):
            raise ValueError("an Imperium card instance cannot occupy two zones")

        intrigue_zones = (*self.intrigue_cards, *self.intrigue_faceup)
        if len(intrigue_zones) != len(set(intrigue_zones)):
            raise ValueError("an Intrigue card cannot be both held and face up")

        if self.owed_draws and any(
            entry[0] not in ("intrigue", "card") for entry in self.owed_draws
        ):
            raise ValueError("an owed draw is from the Intrigue deck or the deck")

        if len(self.hand_public) != len(set(self.hand_public)):
            raise ValueError("a hand card cannot be publicly known twice")
        if self.deck_public_top and len(self.deck_public_top) != len(
            set(self.deck_public_top)
        ):
            raise ValueError("a deck card cannot be publicly known twice")
        in_hand = set(self.hand)
        if any(card_id not in in_hand for card_id in self.hand_public):
            object.__setattr__(
                self,
                "hand_public",
                tuple(card_id for card_id in self.hand_public if card_id in in_hand),
            )
