"""Authoritative per-player state and component invariants."""

from dataclasses import dataclass


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
    troops_supply: int = 9
    troops_garrison: int = 3
    troops_conflict: int = 0
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
    deploy_trigger_offered_at: int = 0
    # Deployed-unit count an effect already consumed as its condition this
    # turn (Distraction's Spy); a withdrawal may not drop below it (OQ-029).
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
    # Hungry for Spice fired this turn.
    hungry_for_spice_granted_turn: bool = False
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
    # Cards owed by CHOAM Transports (a contract completed) and Planetary
    # Array (a Conflict won), drawn by the engine after the transition so a
    # reshuffle never lands inside another effect's frame bookkeeping.
    tech_cards_owed: int = 0
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
    # Chairdog: grafted cards that return from play to the hand when the
    # owner's Reveal turn starts [card face].
    chairdog_return_card_ids: tuple[str, ...] = ()
    # Usurp: the Imperium Row card grafted without acquiring it; it leaves
    # the game when the Agent turn closes [card face].
    usurped_row_card_id: str = ""
    deck: tuple[str, ...] = ()
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
            self.deploy_trigger_offered_at,
            self.units_deployed_committed,
            self.spice_at_turn_start,
            self.spice_spent_turn,
            self.commanders_supply,
            self.commanders_garrison,
            self.commanders_conflict,
            self.skill_strength_applied,
            self.contracts_completed_turn,
            self.commander_discount_turn,
            self.spies_boxed,
            self.spies_recalled_turn,
            self.suspensor_owed,
            self.tech_cards_owed,
            self.tleilaxu_space,
            self.specimens,
            self.reveal_persuasion_round_bonus,
        )
        if min(quantities) < 0:
            raise ValueError("player component quantities must not be negative")
        if len(self.skill_ids) != len(set(self.skill_ids)):
            raise ValueError("a Skill tile cannot be held twice")
        if len(self.tech_ids) != len(set(self.tech_ids)):
            raise ValueError("a Tech tile cannot be held twice")
        if not set(self.tech_flipped) <= set(self.tech_ids) or len(
            self.tech_flipped
        ) != len(set(self.tech_flipped)):
            raise ValueError("flipped Tech tiles must be held tiles")
        skill_identities = tuple(
            instance_id.split(":")[1] for instance_id in self.skill_ids
        )
        if len(skill_identities) != len(set(skill_identities)):
            raise ValueError("a player cannot hold two copies of one Skill")

        active_agents = 3 if self.swordmaster_acquired else 2
        if (
            self.agents_available + len(self.agent_locations) + self.agent_in_conflict
            != active_agents
        ):
            raise ValueError("available and placed agents must equal active agents")
        if self.agent_in_conflict not in (0, 1) or self.tactics_track_space < 0:
            raise ValueError("Leader token positions must be non-negative")
        if len(self.agent_locations) != len(set(self.agent_locations)):
            raise ValueError("a player cannot place two agents in one space")
        # Specimens are troops from the supply in the Axolotl tanks
        # [Immortality p. 8].
        if (
            self.troops_supply
            + self.troops_garrison
            + self.troops_conflict
            + self.memories
            + self.specimens
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
        )
        if len(imperium_cards) != len(set(imperium_cards)):
            raise ValueError("an Imperium card instance cannot occupy two zones")

        intrigue_zones = (*self.intrigue_cards, *self.intrigue_faceup)
        if len(intrigue_zones) != len(set(intrigue_zones)):
            raise ValueError("an Intrigue card cannot be both held and face up")

        if len(self.hand_public) != len(set(self.hand_public)):
            raise ValueError("a hand card cannot be publicly known twice")
        in_hand = set(self.hand)
        if any(card_id not in in_hand for card_id in self.hand_public):
            object.__setattr__(
                self,
                "hand_public",
                tuple(card_id for card_id in self.hand_public if card_id in in_hand),
            )
