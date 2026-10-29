"""Stable integer encoding for structured Uprising actions."""

import functools
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from numbers import Integral
from typing import Final

from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS,
    EVENTS,
    MAX_AUCTION_BID,
    MAX_MERCENARIES_BID,
    MAX_SPECIMEN_TOP_UP,
    SALES,
    missions_for,
    scouts_pool,
    subcommittees_for,
)
from dune_imperium.content.arrakeen_scouts.types import MissionKind
from dune_imperium.content.bloodlines.sardaukar import SKILLS
from dune_imperium.content.bloodlines.tech import TECH_TILES
from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES_BY_ID,
    RESEARCH_START_ID,
)
from dune_imperium.content.immortality.tleilaxu import (
    tleilaxu_cards_for,
    tleilaxu_deck_instance_ids,
)
from dune_imperium.content.rise_of_ix.tech import IX_TECH_TILES
from dune_imperium.content.rulesets import TUEK_SIETCH, RulesetContent, content_for
from dune_imperium.content.uprising.abilities import AbilityStructure
from dune_imperium.content.uprising.agent_abilities import agent_box_ability
from dune_imperium.content.uprising.board import (
    BoardSpace,
    Faction,
    ObservationPost,
)
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTech,
    EachOpponentDiscardsCard,
    EachOpponentDiscardsOrLosesDeployedTroop,
    EachOpponentLosesTroop,
    GrantAgentIconsThisTurn,
    OnTroopsLostAtConflictEnd,
    OpponentLosesTroop,
    OpponentsMoveSpiesFromVisitedSpace,
    PeekTopCard,
    PrintedRevealValue,
    RedirectSpiesOnTurnSpace,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.imperium import (
    ImperiumCardEntry,
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import (
    intrigue_card_for_instance,
    intrigue_deck_instance_ids,
    navigation_card_instance_ids,
    twisted_intrigue_instance_ids,
)
from dune_imperium.content.uprising.leaders import (
    FEYD_TRACK_START,
    FEYD_TRAINING_TRACK,
)
from dune_imperium.content.uprising.personal_cards import (
    card_is_ghola,
    card_is_graft,
    card_is_usurp,
    card_sends_agent_anywhere,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.reserve import (
    RESERVE_STACKS,
    ReserveStackDefinition,
)
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    STARTING_DECK,
    StartingCardEntry,
)
from dune_imperium.content.uprising.trigger_abilities import acquisition_ability
from dune_imperium.content.uprising.types import (
    BLOODLINES_REVEAL_CHOICE_EFFECTS,
    IMMORTALITY_REVEAL_CHOICE_EFFECTS,
    IMPERIUM_REVEAL_CHOICE_EFFECTS,
    AgentIcon,
    BattleIcon,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardTrashEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.rules.acquire_icons import (
    ACQUIRE_ICON_ACTION,
    ACQUIRED_CARD_ARGUMENT,
    DREADNOUGHT_ICON,
    acquire_box_icons,
    acquire_icon_faction,
)
from dune_imperium.rules.acquisition import (
    acquire_box_draws_intrigue,
    acquire_box_places_spy,
)
from dune_imperium.rules.action_shapes import ACTION_SHAPES, Source
from dune_imperium.rules.agent_effects import AUTOMATIC_AGENT_ICONS
from dune_imperium.rules.board_effects import (
    AUTOMATIC_BOARD_ICONS,
    IMPERIUM_BOARD_ICONS,
    IMPERIUM_ONLY_BOARD_ICONS,
)
from dune_imperium.rules.combat import (
    COMBAT_REWARD_ICON_KINDS,
    DREADNOUGHT_CONTROL,
    DREADNOUGHT_CONTROL_ACTION,
    DREADNOUGHT_DETONATE_ACTION,
    IMPERIUM_REWARD_ICON_KINDS,
    IX_REWARD_ICON_KINDS,
    STRATEGIC_PUSH,
    WINDTRAPS,
    conflict_reward_icon_kinds,
)
from dune_imperium.rules.contracts import (
    CONTRACT_REWARD_ICON_KINDS,
    contract_reward_icons,
)
from dune_imperium.rules.effect_interpreter import (
    automatic_rewards,
    choice_slots,
    rewards_come_first,
)
from dune_imperium.rules.effect_steps import (
    AGENT_ICON_VERBS,
    INTRIGUE_WINDOWS,
    STEP_SPECS,
    TARGET_SPECS,
    WINDOW_OWN,
    Printed,
    steps_for,
)
from dune_imperium.rules.graft_boxes import BOX_ACTION_IDS, BOX_ARGUMENT
from dune_imperium.rules.immortality import (
    RESEARCH_ICON_ORDER,
    research_icon_spaces,
    research_trash_spaces,
)
from dune_imperium.rules.intrigue_bottom import FINISH_ACTION, PUT_ACTION
from dune_imperium.rules.planetologist import PLANETOLOGIST_LEADER
from dune_imperium.rules.reveal_lines import RevealLine, reveal_lines
from dune_imperium.rules.reveal_turn import (
    SOURCE_ARGUMENT,
    card_holds_reveal_value,
    troops_move_shape,
    troops_trash_move,
)
from dune_imperium.rules.scouts_effects import scouts_spy_items, scouts_trash_items
from dune_imperium.rules.scouts_missions import mission_takes_supply_troops
from dune_imperium.rules.shipping_track import (
    ADVANCE_ACTION,
    DECLINE_ACTION,
    DIVIDENDS,
    INFLUENCE,
    RECALL_ACTION,
    RECRUIT,
    REWARD_ACTION,
    SPICE,
    TECH,
)
from dune_imperium.rules.shipping_track import PRINTED as SHIPPING_PRINTED
from dune_imperium.rules.tech import (
    TRASH_ABILITIES,
    optional_trash_tech_ids,
    tech_acquire_effect_arguments,
)
from dune_imperium.rules.units import unit_count_arguments
from dune_imperium.rules.unload import UNLOAD_ICON_ACTION, unload_icons

# v109 (OQ-068, 2026-09-26 user ruling): every Recall Agent effect, not only
# Imperial Privilege, may recall an Into the Fray Agent from the Conflict --
# Steersman's Recall Agent icon and Twisted Mentat
# (recall_conflict_agent_for_agent_card, Bloodlines catalogs) and the
# Sardaukar II / High Council token Contract reward
# (recall_conflict_agent_for_contract, CHOAM+Bloodlines catalogs).
# v110 (OQ-057 (14)): an Agent-box Spy without a Spy in supply may pass up
# the recall-first when the box resolves [Main pp. 9, 11, 20]
# (decline_agent_card_spy, every catalog), instead of only fizzling at the
# turn's end.
# v111 (2026-09-27): the standard Contract set drops the four Rise of Ix
# tiles (Espionage II, Harvest 3+/4+ with a Contract, Heighliner III) for
# Spice Refinery I and II and the second copies of Espionage I and Harvest
# 3+ [Main p. 16]; the per-Contract templates follow the new instance ids.
# v112: the ``arrakeen_scouts`` option joined ``RulesetConfig``, so every
# state hash changes and old saves need the clean version error -- no
# Scouts templates exist yet.
# v113: the first Scouts templates (Friends Everywhere's choice of Influence
# 4 bonus), only in ``arrakeen_scouts`` catalogs.
# v114: subcommittees (join/decline) and the Scouts effect frame's choices.
# v115: the Scouts events' and sales' turn-order choices and Influence losses.
# v116: missions (take part or pass, collect on a visit).
# v117: Desert Riding's Maker Hooks token at Hagga Basin.
# v118: secret picks (Covert Operation, Offworld Operation).
# v119: auctions (sealed bids, Mercenaries' retreat, Critical Moment).
# v120: the ``go_to_11`` option joined ``RulesetConfig``, so every state
# hash changes and old saves need the clean version error -- no template
# changes.
# v121: Immortality specimen top-ups before a Scouts recruit, mission or
# Mercenaries deployment, and an Agent recalled from the Conflict. (The
# Mercenaries part is superseded by v122: Mercenaries now tops up by itself.)
# v122: Round Start follows the rules order [Main p. 8] [Main p. 20]: the
# Control defense comes before the draw (OQ-072). The same batch of
# Arrakeen Scouts rulings changes replays too: Mercenaries returns its
# specimens by itself, so ``scouts_return_specimens`` is no longer offered
# there (OQ-074 (a)); Critical Moment is not drawn while the Imperium deck
# is short, which changes that draw's options (OQ-087 (b)); Clear the
# Market's CHOAM shuffle mixes the old pair into the whole bank before
# dealing (OQ-083); CHOAM Research skips Bloodlines' Immediate Contract
# (OQ-090); a mandatory event a seat can do only one line of still opens
# its choice frame (OQ-071); Emperor's Schemes reshuffles the Intrigue
# discard when the deck is short (OQ-078). Saves whose game met any of
# these replay differently -- no template change.
# v123: the subcommittee join moves into the turn: choose_subcommittee (no
# arguments, every Scouts catalog) opens the list any time in the turn a
# High Council seat was taken, beside the visit's other effects or in the
# rest of Corrinth City's Reveal turn, and decline_subcommittee is offered
# there too; the old immediate offer is gone (OQ-076 alternative C, user
# ruling 2026-09-30).
# v124: the ``epic_game`` option (Epic Game Mode) joined ``RulesetConfig``;
# its catalogs add Control the Spice's templates and Economic Supremacy's
# ``flip_battle_card``. Catalogs without the option are unchanged. (Built
# as v121 on the epic-game-mode branch; renumbered when it was merged onto
# the line that had meanwhile used v121..v123.)
# v125: every Agent turn ends only through its owner's ``finish_agent_turn``
# (OQ-095, user ruling 2026-09-30): the last effect no longer hands the turn
# over, so a Plot Intrigue, Family Atomics, a specimen return, a Tech flip or
# a Commander recruit stays possible until the press, and what the last
# effect left behind resolves inside the turn. Usurp's borrowed card is
# trashed by the press and its results are the turn's own. An Arrakeen
# Scouts line's spice cost now counts as spice spent this turn, like every
# other spend. Saves replay differently -- no template change. The
# ``turn_closed`` fields (the 4th field of the Skill choice, Navigation play
# and Scouts offer queues, and the frame-context markers) left the state.
# Also in v125 (L2, merged with L1): Desert Power's Reveal choice opens for
# a seat without Maker Hooks too, whose 2 Persuasion now count only from
# ``decline_reveal_sandworm`` (option (B), user ruling 2026-09-30; OQ-069).
# Imperial Privilege's recall and a Contract's Recall Agent reward with no
# target are no longer skipped unasked: the owner confirms them with
# ``resolve_imperial_privilege_without_recall`` (every catalog) and
# ``resolve_contract_without_recall`` (CHOAM catalogs), and the engine hook
# ``skip_impossible_imperial_privilege_recall`` is gone (OQ-023, OQ-068).
# An Immortality research bonus whose arrow cost cannot be paid opens its
# window too, offering only ``decline_research_bonus`` (no template change;
# the ``research_bonus_unavailable`` event is gone).
# A Conflict reward's "choose a Faction" Influence with every eligible
# Faction at the top opens its window too, offering only
# ``resolve_combat_influence_without_faction`` (every catalog; OQ-060); the
# engine no longer drops it unasked. A Conflict reward Spy and Panopticon's
# Spy with nothing to place offer only their declines (no template change;
# unreachable with four players, and the ``tech_reveal_unavailable`` event is
# gone, OQ-044 (b)).
# Holy War's unit loss asks every opponent, even with one (zone, unit) to
# lose or none (OQ-036 (a), user ruling 2026-09-30, which reverses the
# automatic single-option loss and the event-only skip); a seat with no unit
# confirms with ``resolve_unit_loss_without_unit`` (Bloodlines catalogs).
# The windows follow the printed order: every opponent's loss, then every
# opponent's Spy moves (user ruling 2026-10-02).
# Rare sites that skipped without asking now open their windows too. Per
# the user ruling of 2026-09-30 (every automatic skip opens a window):
# Plasteel Blades' extra Skill with nothing to gain offers only
# ``decline_skill`` (OQ-044 (c)); a Navigation card with no usable line
# offers only ``decline_navigation`` (OQ-039 (b)); a card's Tech
# acquisition with no tile left offers only ``decline_tech`` (the
# ``tech_acquisition_unavailable`` event is gone, OQ-057 (9)); a new High
# Council seat's subcommittee offer is always armed, offering only
# ``decline_subcommittee`` when every subcommittee is taken (unreachable
# with four players; the ``scouts_subcommittee_unavailable`` event is
# gone, OQ-076 (c)). Per the user ruling of 2026-10-02 (L2-Q3, confirm
# windows for the old no-window rulings): a bank Commander gained with no
# choosable Skill is confirmed with ``resolve_commander_without_skill``
# (Bloodlines catalogs; OQ-031, OQ-035 (b)), and Imperium Ceremony with
# one Intrigue card left and no discard opens its peek on that card
# (OQ-052). No other template change.
# A Contract icon over a market where nothing can be taken (only the
# Bloodlines Immediate, no Intrigue card to trash) is no longer held
# unasked: the owner confirms it with ``hold_contract_icons``
# (CHOAM+Bloodlines catalogs; OQ-059, user ruling 2026-09-30). Such an icon
# from a Conflict reward is held to the end of its seat's Conflict rewards
# and then fizzles with ``contract_icons_fizzled`` (user ruling 2026-10-02,
# L2-Q2); it no longer reaches a later turn nor vanishes silently.
# Shortfalls with nothing to choose open no window but are logged (user
# ruling 2026-10-02, L2-Q4): an Intrigue draw the Intrigue deck and
# discard cannot cover together logs ``intrigue_draw_short``, and
# Suspensor Suits troops only partly deployed log
# ``suspensor_deployment_unavailable`` too (no template change; the event
# log, and so a replay's hashes, moves).
# v126 (user rulings of 2026-10-02 after v125 was pushed, OQ-059): a Combat
# Intrigue's Contract icons with nothing to take fizzle as the card
# resolves, confirmed by ``resolve_contract_icons_without_contract``
# (CHOAM+Bloodlines catalogs: one template, which shifts every later one),
# and icons held in the Arrakeen Scouts step reopen when an Intrigue card
# arrives and fizzle as the step ends.
# v127: a Combat Intrigue card that leaves a window of its own above the
# Combat Intrigue loop (Reach Agreement's Contract market, Battlefield
# Research's Tech window) still restarts the consecutive passes, and so
# does Harvest Cells laid face up [Main p. 14]; the loop drops a participant
# left without units once that window closes (OQ-003), and a loop that
# empties so now logs combat_intrigue_finished (event id ``...:emptied``;
# the event log, so the state hash, gains it). Saves replay differently --
# no template change.
# v128: with the OQ-007 Leader draft, Epic Game Mode's setup Intrigue card
# is dealt after the last pick instead of before the first, since it is
# drawn once every Leader is known [Rise of Ix p. 10]. Each seat gets the
# same card; the draft-phase states (hands, Intrigue deck, observations)
# and so a draft save's hashes move -- no template change.
# v129 (user ruling 2026-10-03, OQ-016): "When you deploy three or more
# units to the Conflict in a single turn" is a condition for playing
# Distraction and Coercive Negotiation [FAQ p. 2] [Board Guide p. 10], met at
# the turn's deployment peak (designer ruling), not a trigger they wait face
# up for. Distraction's Spy now goes through the Intrigue choice
# (``place_intrigue_spy`` / ``recall_spy_for_intrigue`` /
# ``decline_intrigue_spy`` with the shared-post targets), so
# ``decline_intrigue_trigger``, ``place_trigger_spy`` and
# ``recall_spy_for_trigger`` leave every catalog (-27); Coercive
# Negotiation keeps ``take_trigger_contract``. The player's offer record
# became the turn's deployment peak, so every state hash moves.
# v130 (user ruling 2026-10-04, OQ-021, following the Steam app): over an
# exhausted market Shaddam's Contract icon must take a set-aside Sardaukar
# Contract while one remains -- nobody has taken them, so the two-Solari
# reversion [Main p. 16] waits until they are gone. ``take_exhausted_contract
# _solari`` leaves the CHOAM catalogs (-1). Also v130 (user ruling 2026-10-04,
# OQ-005): an Objective "counts as a Conflict card you've already won"
# [Objective card], so the Endgame Intrigue flips and Grasp Arrakis may take
# it; ``flip_battle_card`` gains one template per Objective of the player
# count in every catalog (+4). Also v130 (user rulings 2026-10-04, OQ-030,
# OQ-049, OQ-050): a recruit or specimen shortfall waits on the seat
# (``PlayerState.ungained_troops``/``ungained_specimens``, so every state
# hash moves) and is made up when troops return to its supply in the same
# turn, and ``return_specimen`` is also offered at Combat Intrigue priority
# and at a supply-less Control defense; replays change, no template does.
# v131 (user rulings 2026-10-04, second batch): the Emperor track's
# Influence-4 Spy owed inside its owner's turn waits as the freely ordered
# action ``place_track_spy`` until placed (OQ-057 (15), following the Steam
# app; +1 template in every catalog); a card discarded straight from a deck
# fires its discard trigger (OQ-013); Interstellar Trade adds +1 Persuasion
# per contract completed later in the Reveal and a trashed card's Reveal
# effects pay nothing late (OQ-028 (c) restored, OQ-022); Call to Arms waits
# for the decision frames the acquired card's own effects opened (OQ-012);
# an Intrigue "trash" goes to the Intrigue discard and ``GameState`` no
# longer has an Intrigue trash zone (OQ-061). Every state hash and many
# replays change.
# v132 (user rulings 2026-10-04, third batch): Litany Against Fear and
# Withdrawn ("At the start of your turn: ...") only as the turn's first
# action -- the owner's turn frame records that its start is over (OQ-095
# (6)); Twisted Intrigue cards stay in the Intrigue discard when it is
# reshuffled (OQ-097). No template change; replays and hashes change.
# v133 (user rulings 2026-10-04, fourth batch): a card or Leader retreat or
# loss no longer gives the basic deployment allowance back (OQ-029; only a
# voluntary withdrawal does); the Usurp-borrowed Row card is not counted as
# in play anywhere (OQ-054, [Immortality p. 14]); a separate-line Intrigue
# must use at least one line before it can be finished (OQ-058); Arrakis
# Revolt's no-effect keep-wall line is withheld under a deployment block
# (OQ-026). No template change; replays and hashes change.
# v134: the final Leader pick waits for finish_leader_draft before setup
# reveals hidden cards, so the play server can undo every pick (OQ-007).
# v135: Tech purchases queue freely ordered acquire icons (OQ-098);
# reward choices move from acquire_tech to resolve_tech_acquire_effect.
# v136 (user ruling 2026-10-05, OQ-100): an Arrakeen Scouts line's later
# automatic rewards may resolve ahead of an earlier reward's pending choice
# (Water Discipline's draw before its trash); ``scouts_rewards_first`` joins
# the Scouts catalogs (+1).
# v137 (card-transcription comparison batch, 2026-10-06): three automatic
# Agent-icon keys, one more ``resolve_agent_card_effect`` template each
# (+3): ``cards_second`` (Cargo Runner's "four or more contracts" draw,
# judged apart from its "two or more" line), ``research`` (Industrial
# Espionage's "If grafted: [Research] [specimen]" line, apart from its draw)
# and ``return_self`` (Stillsuit Manufacturer's return, waiting for a Fremen
# Alliance apart from its water) (OQ-027, OQ-028, OQ-057 (1)).
# ``retreat_intrigue_troops`` gains count 0, since Tactical Option's "any
# number" may be zero [Main p. 20] [FAQ p. 3] (+1); ``deploy_intrigue_troops``
# gains count 0, since "Deploy up to ..." (Counterattack, Detonation, Twisted
# Devious) may deploy none and no longer needs a deployable garrison unit to
# be played (+1). ``resolve_intrigue_influence_without_faction`` confirms an
# Intrigue "choose a Faction" Influence gain with every cube it may raise at
# 6 (OQ-060, +1). Immortality catalogs also gain
# ``acquire_intrigue_reclaimed_forces`` (one template per chosen effect,
# +2): Harvest Cells may take Reclaimed Forces (user ruling 2026-10-06).
# Legal-action sets also change without template changes, so saves and
# replays from v136 are refused by the version check: Harvest contracts
# count the whole turn's spice; Tread in Darkness's trash and draw are
# separate icons; Fill Coffers' Alliance spice and Stillsuit Manufacturer's
# return wait for their conditions; Treacherous Maneuver replaces the
# space's Influence with two and Subversive Advisor's expired box gives the
# space's Influence back; cost lines whose reward would change nothing are
# withheld (OQ-071); card and Leader Influence pickers no longer offer a
# Faction at 6 (OQ-060); other acquire effects may take a Manipulate
# set-aside card at its printed cost [FAQ p. 3]; and Harvest Cells is played
# only after the Conflict resolves (OQ-057 (11)).
# v138 (user ruling 2026-10-06, "아무 효과 없이 책략을 쓸 수 없는거지"): an
# Intrigue or Navigation option is offered only if one of its effects can
# change something now, so legal-action sets change with no template
# change and saves and replays from v137 are refused by the version check.
# A draw with an empty deck and discard pile (Cunning, Intelligence Report,
# Emperor's Invitation, Twisted Discerning and Sadistic, Navigation card 9),
# an "up to" deploy with no deployable garrison unit (Detonation,
# Counterattack, Twisted Devious: again a play condition, the reverse of
# v137's), an acquisition with no target (Inspire Awe, Battlefield Research,
# Rapid Engineering, Navigation card 4), a Tleilaxu advance at the track's
# end (Illicit Dealings, Shadowy Bargain), a recruit with no troop to take
# (Shaddam's Favor, Mercenaries, Sleeper Unit, Navigation card 6), a Spy
# recalled and replaced after an earlier recall that turn (Special
# Mission), and the agent-turn grants with no Agent placement ahead
# (Emperor's Invitation, Insider Information, Twisted Resourceful) are no
# longer offered. Call to Arms is not offered in a Reveal with nothing left
# to acquire, and Harvest Cells' Conflict-end window skips a copy that
# could change nothing.
# v139 (Combat Intrigue hand-over, [Main pp. 14-15]): a seat that played a
# Combat Intrigue card since priority last came to it hands priority on with
# ``pass_combat_intrigue`` without that pass counting as one of the
# consecutive passes, so in the rulebook's example Abby still decides after
# John passes again. The Combat Intrigue frame marks such a seat
# (``played_at_priority``); legal-action sequences change with no template
# change, so saves and replays from v138 are refused by the version check.
# v140 (user decision 2026-10-08, "추천대로"; rules/pauses.py, OQ-103): the
# engine pauses with a one-outcome chance decision before each Conflict
# reward recipient after the first, once the rewards are paid before the
# Conflict-end Intrigue windows, before every Round Start after the first,
# and after a Control defense, so the play server can hold a seat's
# last choice before the reveal that follows it. No template or legal
# action changes and the pause draws nothing from the random stream, but
# every recorded step sequence gains those chance steps, so saves and
# replays from v139 are refused by the version check.
# v141 (user decisions 2026-10-09, OQ-103, OQ-056): the Conflict-end
# Intrigue window opens on public facts (Immortality, at least three units
# in the Conflict, an Intrigue card held, a Harvest Cells copy not yet
# public), with only the decline for a seat that can play nothing, and
# stays open after a play while the seat holds an Intrigue card; Earn Any
# Alliance completes at the end of the step that took the Alliance, also
# when that step stopped at a pause, so in Combat before the cleanup.
# Legal-action sequences change with no template change, so saves and
# replays from v140 are refused by the version check.
# v142 (user decision 2026-10-10, OQ-104): Navigation Chamber's cut ("Board
# spaces cost you [1 spice] or [1 Solari] less." [Tech tile face]) is
# mandatory, so its holder is no longer offered the undiscounted
# ``agent_turn`` beside the discounted one on a costed space. Legal-action
# sequences change with no template change, so saves and replays from v141
# are refused by the version check.
# Also in v142 (user ruling 2026-10-10, OQ-105): a Sardaukar Commander pays
# the self-paid troop costs too. Bloodlines catalogs with Immortality add
# ``lose_agent_card_troop(commanders=1, zone)`` (Piter, Genius Advisor);
# Bloodlines Scouts catalogs add ``scouts_lose_garrison_unit`` and its
# ``commanders=1`` twin (Bene Gesserit Treachery's garrison troop, picked
# when the garrison holds both kinds) and, with Prison Planet in the pool,
# ``scouts_join_mission(target="commander")``. New templates; the other
# catalogs are unchanged.
# Also in v142 (user ruling 2026-10-10, OQ-027 (d)): Imperial Privilege's
# recall and its card draw are two steps. The draw is the space's own
# ``resolve_board_effect(effect=cards)`` icon, ordered freely with the
# Intrigue slot and the recall; ``recall_agent_for_imperial_privilege``,
# ``recall_conflict_agent_for_imperial_privilege`` and
# ``resolve_imperial_privilege_without_recall`` no longer draw. No template
# change.
# Also in v142 (user ruling 2026-10-10, OQ-106: "그 외에는 전부 나누자"): the
# draw Urgent Shigawire adds to the boosted Bene Gesserit card's Agent box is
# its own ``resolve_agent_card_effect(effect=cards)`` step after the
# placement instead of being drawn by the ``agent_turn`` itself. No template
# change.
# Also in v142 (OQ-106): Cunning's and Insider Information's draw is its own
# ``resolve_intrigue_rewards`` when the owner resolves the line's trash slot
# first. No template change.
# Also in v142 (OQ-106): Liet Kynes' Arrakis Planetologist pays a replaced
# sandworm's spice at once and holds its Intrigue card in the replacement's
# trash frame as its own step: Bloodlines catalogs add the nullary
# ``draw_planetologist_intrigue``.
# Also in v142 (OQ-106): Piter, Genius Advisor's ``lose_agent_card_troop`` and
# Kota Odax's ``trash_leader_tech`` pay only the arrow's cost; their rewards
# are then their own ``resolve_agent_card_effect(effect=cards|research)`` and
# ``(effect=intrigue|cards)`` steps. No template change.
# Also in v142 (OQ-106, triggered draws): a draw another printed effect
# triggers inside the seat's own Agent or Reveal turn waits as the seat's own
# step (``PlayerState.owed_draws``) instead of being drawn by the step that
# triggered it -- the Bene Gesserit Influence 4 bonus, Princess Irulan's
# Imperial Birthright, a Tleilaxu track Intrigue space, Sardaukar Soldier's
# "when trashed" and Overthrow's acquire box. Every catalog adds the nullary
# ``draw_owed_intrigue``. Muad'Dib's Unpredictable Foe queues its card on the
# Reveal's pending gains for the existing ``draw_reveal_intrigue``.
# Also in v142 (OQ-106): the card Steersman Y'rkoon's Hungry for Spice owes
# inside his own turn waits likewise: Bloodlines catalogs add the nullary
# ``draw_owed_card``.
# Also in v142 (OQ-106, Arrakeen Scouts): a pause stands before each auction
# winner's reward after the first (rules/pauses.py), so Competitive Study's
# second place no longer researches, or draws past the second genetic
# marker, in the first place's step. No template change; recorded step
# sequences gain those chance steps.
# Also in v142 (OQ-106, Arrakeen Scouts lines): a draw printed after one of a
# line's reward choices (Leverage's Faction, Water Discipline's trash, the
# late Spies for Hire's Spy post and CHOAM Negotiations' Contract) waits as
# the line's own ``scouts_rewards_first``, then that line's only action,
# instead of being drawn by the choice. No template change.
# Also in v142 (OQ-106, user decision 2026-10-10 "가 로 가자"): three held
# draws whose adopted community rulings say they come at once -- the Bene
# Gesserit Influence 4 card and Imperial Birthright, Overthrow's acquire box,
# and CHOAM Transports' card, which is now held too instead of being drawn by
# the completing step -- are the owner's only action right after their
# trigger, on whatever frame of the owner's is open (``draw_owed_intrigue``,
# ``draw_owed_card``). No template change.
# v143 (user decision 2026-10-12, docs/graft-boxes-plan.md): a grafted Agent
# turn offers both cards' Agent boxes from the start [Immortality pp. 10-11].
# Box 0 is the placed card, box 1 the partner; box 1's rows carry
# ``box=1``. Immortality catalogs add the ``box=1`` twin of every template an
# Agent box offers (``rules.graft_boxes.BOX_ACTION_IDS``) and drop
# ``switch_graft_card``; the untagged templates stay box 0's and every
# source outside a box (a Servo-Receivers Signet frame, Kota Odax's
# rewards there, Urgent Shigawire's added draw). Other catalogs are
# unchanged. Recorded step sequences change (no switch, tagged rows), so
# saves and replays from v142 are refused by the version check.
# v144 (user ruling 2026-10-12 "2. 고치자", OQ-057 (1)): a pending Agent box
# that still offers a choice giving its effect -- Stitched Horror's "Choose
# two", Beguiling Pheromones' trash, Piter's, Tleilaxu Surgeon's and
# Dissecting Kit's arrows while their cost can be paid, Tleilaxu Master's
# acquisition, Ghola's copies of them -- holds the turn end until it is
# answered; the dry run behind ``finish_agent_turn`` misread them as boxes
# that can only fizzle (one offering only its refusal still does). No
# template change; recorded step sequences change, so saves and replays
# from v143 are refused by the version check.
# Also in v144 (user ruling 2026-10-12 "1. 짝도 받음", OQ-107): a Bene
# Gesserit graft partner played while Urgent Shigawire's boost is pending
# takes it; the draw added to its box is box 1's
# ``resolve_agent_card_effect(box=1, effect=cards)`` (an existing template),
# and Usurp reaches every space through such a partner. No template change.
# v145 (user ruling 2026-10-12 "그래 고치자", OQ-107): a Ghola grafted to the
# card that took Urgent Shigawire's boost copies the draw added to its box
# ("Ghola copies the entire Agent box of the card it's grafted to"
# [Immortality p. 14]): Ghola's box offers its own
# ``resolve_agent_card_effect(effect=cards)`` row (``box=1`` when Ghola is
# the partner), which holds the turn end. Also (OQ-022): a card that trashes
# itself with its own optional trash icon (Throne Room Politics) keeps its
# added draw, which an older engine lapsed. No template change; recorded
# step sequences change, so saves and replays from v144 are refused by the
# version check.
# v146 (user ruling 2026-10-14, "선택행동의 경우 거절 버튼이 왜 따로 있는거야
# 그럼?"; OQ-095 (2), [FAQ p. 3]): an optional effect of the Agent turn --
# a "may", arrow or black-trash Agent box, a Leader Signet's optional stage,
# the visit's optional icons (Desert Tactics' trash, Imperial Privilege's
# Intrigue trade, a Sardaukar Commander, the Ixian Embassy's Tech, a
# subcommittee seat) and Reverend Mother's repeat -- holds no turn end back
# and offers no refusal; the press of ``finish_agent_turn`` lapses one left
# unused (events ``agent_card_effect_lapsed``, ``board_effect_lapsed``,
# ``leader_ability_lapsed``). A refusal stays where it is still needed: a
# bundled selection part way through while the other grafted box waits, a
# Spy placement passed up with an empty supply (OQ-057 (14)), the
# confirmations of mandatory effects with no target, and every frame on top
# of the turn. Imperial Privilege's trade and recall are now separate icons
# offered together. No template change; recorded step sequences change, so
# saves and replays from v145 are refused by the version check.
# v147 (user ruling 2026-10-14, "그래 그 구조로 진행하자"; OQ-095 (7) addition,
# [Main p. 12], [FAQ p. 3]): a Reveal choice no longer opens its own frame. Every
# choice effect of a revealed card waits on the Reveal frame and is offered
# there, beside the purchases and gains, whenever its condition holds; an
# optional one ("may", an arrow cost, a black trash icon) offers no refusal and
# lapses at ``finish_reveal`` (event ``reveal_choice_lapsed``), a mandatory one
# holds the end. ``defer_reveal_choice``, ``resume_reveal_choice`` and the
# optional choices' refusals (``decline_reveal_card_trash``,
# ``decline_reveal_influence_exchange``, ``decline_reveal_influence_loss``,
# ``decline_reveal_spice_influence``, ``decline_reveal_troop_move``,
# ``decline_reveal_troop_retreat``, ``decline_reveal_troop_sacrifice``,
# ``decline_command_acquisition``; ``decline_reveal_spy_recall`` stays for a
# Spy icon's recall-first with an empty supply) are never offered again but keep
# their rows. With every choice offered at once, the eleven ids that different
# cards produce name their card with ``source`` (its definition id):
# ``trash_reveal_card``, ``recall_spy_for_reveal``,
# ``retreat_two_troops_for_reveal``, ``place_reveal_spy``,
# ``recall_spy_for_reveal_placement``, ``keep_contract_reveal_spice``,
# ``trash_contract_reveal_for_vp``, ``gain_reveal_influence``,
# ``deploy_reveal_card_troop``, ``retreat_reveal_card_troop`` and
# ``decline_reveal_spy_recall`` (``_reveal_source_templates``, one per card of
# the catalog's decks). Their source-less rows stay as never-legal rows, and a
# checkpoint's ``source`` row starts from the source-less one
# (``training.checkpoint._alias``). Recorded step sequences change, so saves and
# replays from v146 are refused by the version check.
# v148 (composed-effects stage A1, docs/composed-effects-plan.md): an Intrigue
# card's choice frame and its separate-lines frame (OQ-058) store one pending
# ability of the executor (``rules.ability_executor``, context key
# ``pending_ability``) in place of their own progress keys, and the executor
# offers and applies the slots. Nothing a seat is offered, sees or is told
# changes (the engine equivalence gate: 200 games step by step); only the
# decision stack's form does, so saves from v147 are refused by the version
# check while a v147 record replays as it is.
# v149 (composed-effects cleanup-2, docs/composed-effects-plan.md 5 "정리-2
# 계획"; one raise for the whole cleanup, on branch ``cleanup2`` until it
# merges with A8): (2a, user decision 2026-10-17 applying the 2026-09-30
# ruling "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다", OQ-071) an
# Arrakeen Scouts choice with no line the seat can take -- an event's or a
# sale's, or a revealed secret pick's costed line -- opens for that seat
# too, its lines greyed with their reasons, and its one row
# ``resolve_scouts_choice_without_option`` (new template, Scouts catalogs)
# emits the ``scouts_choice_skipped`` an older engine emitted without
# asking. Older records cross the window with the bridge
# ``scouts_no_option_window``. (2b, user decisions 2026-10-17, OQ-095 (2) and
# OQ-060) a research bonus and an optional trash raised in the owner's own
# turn wait on the turn as rows with no refusal and lapse at the turn-end
# press (Arrakis Planetologist's Intrigue card waits beside its trash and
# holds the end); Shipping's and a Tech tile's acquire "Influence with any
# Faction" offer no Faction at the top and, with every one there, wait and
# lapse, or in Combat confirm with ``resolve_tech_influence_without_faction``
# (new template, Tech catalogs); a research space's paired icons and c7r3's
# rewards are each their own step in the owner's order
# (``resolve_research_icon``, five new templates, Immortality catalogs; owed
# draws for c7r3 in the turn). Older records drop the in-turn refusals and
# the picks at the top, confirm in Combat (``tech_influence_confirm``) and
# take the research icons in their old order (``research_icon_order``).
# (Conflict end, user decision 2026-10-18) every reward, then the Conflict's
# troops and Commanders back to the supply, then each seat's Conflict-end
# window, then the rest of the cleanup: Harvest Cells resolves as it is
# played (its specimens at once, then its acquisition) and the window's
# press after a play is ``finish_conflict_end_intrigue`` (new template,
# Immortality catalogs). Older records answer the acquisition as it is
# asked (``harvest_cells_at_once``), drop its rewards step and rewrite the
# press (``conflict_end_finish``). (OQ-108, OQ-109, same decision) the winner
# takes the Conflict card, and Planetary Array's card, before the troops go
# back, and a played window stays open while its seat holds an Intrigue card,
# judged as it comes back on top; older records take a moved reshuffle of the
# same cards (``tech_draw_at_the_win``, ``reshuffle_moved``) and finish a
# window this engine keeps open (``conflict_end_reopened``). (2c) Event
# kinds, ids and payloads follow the event grammar of the plan's "정리-2c 사건
# 문법" (no action changes; the state hash changes with the event log).
# v150 (stage B, docs/stage-b-plan.md; one raise for the whole stage, on
# branch ``stage-b``): (B1, user decision 2026-10-19, OQ-111) the Agent turn
# is a card pick ``choose_agent_card(card_id[, graft])`` and then a space pick
# ``place_agent(space_id[, cost_option][, discount][, infiltrate_post_id])``
# in place of the one ``agent_turn`` template per card-and-space combination
# (26,372 rows of the all-options catalog); the pick waits in the turn frame,
# seen only by its seat. Older records split each ``agent_turn`` with the
# bridges ``agent_card_pick`` and ``agent_space_pick`` (records.migration).
# v151 (user request 2026-10-21, after the Reveal totals cleanup): the state
# names that still said "effect" for a Reveal record line follow the code --
# the Reveal frame's ``granted_reveal_lines``, the ``reveal_line_granted_late``
# event and its ``line_index`` (no action changes; the state hash changes with
# the frame context and the event log).
# v152 (engine audit 2026-10-22, OQ-128 to OQ-131; user
# decisions 2026-10-25): Interstellar Conspiracy's spice and Influence are two
# icons (``resolve_agent_card_effect(effect=spice)``, P4); Scientific
# Breakthrough's Research after its trash and Guild Envoy's two cards after a
# Spacing Guild discard are steps of their own (P5, P6); a seat that cannot
# take part in a Scouts mission is asked, with the pass alone (G4, OQ-131),
# and Political Equilibrium asks every seat, one with every track at 0 to
# confirm ``resolve_scouts_loss_without_influence`` (new template, Scouts
# catalogs; OQ-131, user decision 2026-10-25).
# The offered rows change too: Scouts cost lines and Spy Network's recall need
# a reward that can happen (P2, P8), Chani's water line a card to draw (P9),
# and the round's first turn, Reveal-turn draws, Signet grafts and Overthrow
# follow the audit's other fixes. Older records take the split parts where an
# older engine did them (``conspiracy_icon``, ``conspiracy_spice``,
# ``breakthrough_research``, ``guild_envoy_draw``), land Overthrow's two
# instead of one on one of its two recorded parts (``overthrow_for_space``,
# ``overthrow_deferred``, ``overthrow_with_the_space``), rename the
# Navigation reshuffle it moves (``navigation_reshuffle_renamed``), take a
# recorded Scouts pass as the confirm where every line is withheld
# (``scouts_pass_without_option``) and answer the new one-row windows
# before the next recorded step (``mission_pass_alone``,
# ``equilibrium_alone``); docs/human-records.md.
# v153 (general rules audit 2026-10-25; user decisions 2026-10-26): an
# Arrakeen Scouts line's Faction step opens with one track below the top
# too (OQ-111 (2); Leverage, Relations, Share Intelligence, Ingratiate), and
# Leverage's Intrigue then waits as the line's ``scouts_rewards_first``
# (OQ-106). No template changes. The audit's other fixes change what is
# offered or gained too: Infiltrate stays open to other graft pairs with
# Tleilaxu Infiltrator in hand, a refilled Harkonnen Advisor troop stays
# undeployable (OQ-038), and a Guild Spy played in an Agent turn no longer
# reacts to The Spice Must Flow.
# Older records answer the one-row Faction window before the next recorded
# step, Leverage's draw taken ahead of it (``scouts_faction_alone_draw``,
# ``scouts_faction_alone``), and take a reshuffle the Faction's track card
# asks under its old name (``scouts_faction_reshuffle_renamed``);
# docs/human-records.md.
# v154 (Uprising rulings batch, user rulings 2026-10-25): Planetary Array's
# card is a row of the sole winner's reward window (OQ-121, OQ-108
# re-ruled): ``resolve_combat_reward_icon{effect: planetary_array}`` and its
# step row ``draw{icon: planetary_array, printed: <conflict>, source:
# conflict}`` (new templates, Tech catalogs). Suspensor Suits' troop is
# recruited and the part the supply lacks is made up as troops return to it
# in the same player turn (OQ-042 (가)); no template changes. Older records
# answer the row once only it is left and the record goes on
# (``planetary_array_row``), and take its reshuffle from the award ahead
# (``tech_draw_at_the_win``, widened); docs/human-records.md.
# v155 (general rules audit gap 6, OQ-138; user ruling 2026-10-26): Covert
# Operation's "Each opponent discards a card." opens its window for every
# opponent, an empty hand too, which confirms it discards nothing
# (``resolve_opponent_discard_without_card``, every catalog: its
# ``confirm_empty`` row by Covert Operation, and by Ghola with Immortality).
# The window records the card that opened it (``printer``). Older records
# answer the new window before the next recorded step
# (``opponent_discard_alone``); docs/human-records.md.
# v156 (base game P3, docs/base-game-and-ix-plan.md 16; one raise for the
# whole stage, in its master merge, user decision 2026-10-28 "병합 때 한
# 번"): the original game's Imperium and Intrigue cards and three promos,
# their templates in the original-game catalogs only (the 144 Uprising
# catalogs are unchanged). Uprising games change where the stage's rulings
# reach them: a card put face up on a deck top is public until drawn or
# shuffled and stays public in hand (OQ-145, Immortality's Tleilaxu
# placements), and a paid line whose recruit or draw cannot happen is not
# offered (OQ-071, the trash-to-draw lines). Observation v38. Older records
# need no new bridge (the v155 records replay with ``hand_public`` the only
# difference).
ACTION_CODEC_VERSION = 156
MAX_DEPLOYMENT_COUNT = 12
MAX_INTRIGUE_DEPLOYMENT = 4
# Seven Sardaukar Commanders exist [Bloodlines p. 2].
MAX_COMMANDER_DEPLOYMENT = 7
# Two dreadnoughts a seat [Rise of Ix p. 6].
MAX_DREADNOUGHT_DEPLOYMENT = 2
# Second Wave: "Deploy up to two units from your garrison to the Conflict."
SECOND_WAVE_UNITS = 2


@dataclass(frozen=True, slots=True)
class ActionTemplate:
    """Actor-neutral action stored at one stable catalog index."""

    action_id: str
    arguments: tuple[tuple[str, ActionValue], ...] = ()

    def __post_init__(self) -> None:
        DomainAction(self.action_id, actor=0, arguments=self.arguments)


@dataclass(frozen=True, slots=True)
class ActionCodec:
    """Encode, decode, and mask actions for one ruleset configuration."""

    config: RulesetConfig
    catalog: tuple[ActionTemplate, ...] = field(init=False)
    _indices: dict[ActionTemplate, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        catalog, indices = _catalog_of(self.config)
        object.__setattr__(self, "catalog", catalog)
        object.__setattr__(self, "_indices", indices)

    @property
    def size(self) -> int:
        """Return the fixed discrete action-space size."""

        return len(self.catalog)

    def encode(self, action: DomainAction) -> int:
        """Return the integer ID for one structured action."""

        if not 0 <= action.actor < self.config.players:
            raise ValueError("action actor must identify a configured player")
        template = ActionTemplate(
            action_id=action.action_id,
            arguments=_normalize_arguments(action.arguments, action.actor),
        )
        try:
            return self._indices[template]
        except KeyError as error:
            raise ValueError("action is not present in this codec version") from error

    def decode(self, action_index: int, actor: int) -> DomainAction:
        """Reconstruct an actor-owned structured action from an integer ID."""

        if isinstance(action_index, bool) or not isinstance(action_index, Integral):
            raise TypeError("action index must be an integer")
        index = int(action_index)
        if not 0 <= index < self.size:
            raise ValueError("action index is outside the catalog")
        if not 0 <= actor < self.config.players:
            raise ValueError("action actor must identify a configured player")
        template = self.catalog[index]
        return DomainAction(
            action_id=template.action_id,
            actor=actor,
            arguments=_denormalize_arguments(template.arguments, actor),
        )

    def legal_action_mask(
        self,
        legal_actions: tuple[DomainAction, ...],
    ) -> tuple[int, ...]:
        """Return a fixed-width binary mask for the supplied legal actions."""

        mask = [0] * self.size
        for action in legal_actions:
            mask[self.encode(action)] = 1
        return tuple(mask)


@functools.lru_cache(maxsize=32)
def _catalog_of(
    config: RulesetConfig,
) -> tuple[tuple[ActionTemplate, ...], dict[ActionTemplate, int]]:
    """``config``'s catalog and each template's index, built once per config.

    Both depend only on the config and the content tables, which never change
    in a process, and the codecs that share them only read them. A test run
    built the same few catalogs 894 times, about 13% of its CPU (2026-10-21).
    """

    catalog = _build_catalog(config)
    indices = {template: index for index, template in enumerate(catalog)}
    if len(indices) != len(catalog):
        raise RuntimeError("action catalog contains duplicate templates")
    return catalog, indices


# The fixed rows of the Uprising board's own systems (docs/base-game-and-ix-
# plan.md 4.2 item 3), which a catalog holds only while its base game prints
# that system: Spies need observation posts, sandworms a space that summons
# them, and Sietch Tabr's choice (with the Shield Wall) that space.
_SPY_ROWS: Final = frozenset(
    {
        "decline_combat_reward_spy",
        "decline_leader_spy_placement",
        "decline_gather_intelligence",
        "decline_reveal_spy_recall",
        "resolve_espionage_without_spy",
        "decline_spy_placement",
        "place_track_spy",
        "decline_acquisition_spy",
        "decline_agent_card_spy",
    }
)
_SANDWORM_ROWS: Final = frozenset(
    {
        "decline_reveal_sandworm",
        "pay_agent_card_spice_for_sandworm",
        "pay_agent_card_spice_for_sandworm_and_shield_wall",
        "pay_reveal_water_for_sandworm",
    }
)
_SIETCH_TABR_ROWS: Final = frozenset(
    {
        "take_sietch_tabr_supplies",
        "take_sietch_tabr_water",
        "take_sietch_tabr_water_and_destroy_wall",
    }
)
# The Conflict reward icons that place or recall Spies.
_SPY_REWARD_ICONS: Final = frozenset({"spy", "optional_recall_spies"})


def _withheld_rows(content: RulesetContent) -> frozenset[str]:
    """The Uprising system rows ``content``'s board does not print."""

    withheld: set[str] = set()
    if not content.observation_posts:
        withheld |= _SPY_ROWS
    if not content.sandworm_space_ids:
        withheld |= _SANDWORM_ROWS
    if all(space.space_id != "sietch_tabr" for space in content.board_spaces):
        withheld |= _SIETCH_TABR_ROWS
    return frozenset(withheld)


def _build_catalog(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    content = content_for(config)
    withheld = _withheld_rows(content)
    # The OQ-007 Leader draft picks are part of every catalog so the
    # leader_draft ruleset option never changes the action space; the mask
    # simply keeps them illegal outside a draft setup.
    templates: list[ActionTemplate] = [
        ActionTemplate(
            action_id="pick_leader",
            arguments=(("leader_id", leader.leader_id),),
        )
        for leader in content.leaders
    ]
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            "finish_leader_draft",
            "decline_combat_reward",
            "decline_combat_reward_spy",
            "decline_combat_reward_trash",
            # A Conflict reward trash with no card to trash is confirmed
            # (cleanup-2f, the 2026-09-30 principle).
            "resolve_combat_trash_without_card",
            # A Conflict reward Influence choice with every eligible Faction
            # at the top is confirmed (OQ-060).
            "resolve_combat_influence_without_faction",
            "decline_agent_card_trash",
            "decline_agent_card_payment",
            "decline_corrinth_city_payment",
            "decline_agent_card_intrigue_payment",
            "decline_agent_card_discard",
            "decline_agent_card_acquisition",
            "decline_control_defense",
            "decline_leader_card_trash",
            "decline_leader_signet_payment",
            # A mandatory Signet stage with nothing it can do is confirmed
            # (cleanup-2f, the 2026-09-30 principle).
            "resolve_leader_signet_without_option",
            # A Leader's Spy may pass up the recall-first without a Spy in
            # supply [Main pp. 11, 20].
            "decline_leader_spy_placement",
            "decline_gather_intelligence",
            "decline_reveal_spy_recall",
            "skip_intrigue_acquisition",
            # Manipulate's set-aside with an empty Imperium Row (OQ-113 (C)).
            "skip_intrigue_set_aside",
            # An Intrigue "choose a Faction" Influence with every Faction it
            # may raise at the top is confirmed (OQ-060).
            "resolve_intrigue_influence_without_faction",
            "finish_intrigue_effects",
            "decline_reveal_sandworm",
            # Unswerving Loyalty's Fremen Bond troop move [Unswerving Loyalty
            # card], shared with Shadout Mapes (Immortality).
            "deploy_reveal_card_troop",
            "retreat_reveal_card_troop",
            "defer_reveal_choice",
            "deploy_control_defense",
            # Reveal troop recruits and Intrigue draws in the owner's order
            # (OQ-045, codec v92).
            "draw_reveal_intrigue",
            "finish_reveal",
            "recruit_reveal_troops",
            "gain_five_reveal_solari",
            "gain_leader_signet_troop",
            "gain_two_reveal_strength",
            "pass_combat_intrigue",
            "pass_endgame_intrigue",
            "pay_agent_card_water",
            "pay_agent_card_spice",
            "pay_agent_card_spice_for_sandworm",
            "pay_agent_card_spice_for_sandworm_and_shield_wall",
            "pay_leader_board_repeat",
            "pay_leader_signet_solari",
            "pay_leader_signet_spice",
            "pay_reveal_water_for_sandworm",
            "take_high_council_from_reveal",
            "pay_combat_reward",
            "resolve_agent_card_effect",
            "resolve_espionage_without_spy",
            # The generic Spy placement frame's way out when nothing can be
            # placed (every ruleset since the Emperor track's Spy uses it).
            "decline_spy_placement",
            # The owner's waiting Emperor track Spy, opened in any order
            # inside its own turn (user ruling 2026-10-04).
            "place_track_spy",
            # An Intrigue card a trigger earned in the owner's own turn, its
            # own step (user ruling 2026-10-10, OQ-106; codec v142).
            "draw_owed_intrigue",
            # An acquisition-bonus Spy may pass up the recall-first without a
            # Spy in supply [Main pp. 11, 20] (OQ-057 (14)).
            "decline_acquisition_spy",
            # So may an Agent-box Spy, when the box resolves (codec v110).
            "decline_agent_card_spy",
            "resolve_faction_influence",
            "retreat_leader_troop",
            "reveal_turn",
            "retreat_two_troops_for_reveal",
            "take_sietch_tabr_supplies",
            "take_sietch_tabr_water",
            "take_sietch_tabr_water_and_destroy_wall",
            "use_other_memories",
        )
        if action_id not in withheld
    )
    # A Conflict reward recipient resolves its reward icon by icon (stage B2,
    # OQ-112); a Deep Cover Spy is printed only on Bloodlines Conflicts.
    printed_reward_kinds = {
        kind
        for conflict in content.conflicts
        for kind in conflict_reward_icon_kinds(conflict.card.card_id)
    }
    templates.extend(
        ActionTemplate(
            action_id="resolve_combat_reward_icon", arguments=(("effect", kind),)
        )
        for kind in COMBAT_REWARD_ICON_KINDS
        # The original game's and Rise of Ix's kinds only where the
        # Conflicts print them.
        if (
            kind not in IMPERIUM_REWARD_ICON_KINDS | IX_REWARD_ICON_KINDS
            or kind in printed_reward_kinds
        )
        and (kind != "deep_cover_spy" or config.bloodlines)
        and (kind not in _SPY_REWARD_ICONS or content.observation_posts)
        and (kind != "contract" or content.contract_instance_ids)
        # Planetary Array's row of the winner's window (OQ-121).
        and (kind != "planetary_array" or config.tech_module)
        # The original game's winning Intrigue closes the winner's window
        # (OQ-121 decision 6); Uprising's catalogs hold no such row.
        and (kind != "winning_intrigue" or content.base_game is BaseGame.IMPERIUM)
        # Rise of Ix's winner's dreadnought, set on a Control space (OQ-121
        # ruling 6 (1)); no catalog without the expansion holds its row.
        and (kind != DREADNOUGHT_CONTROL or config.rise_of_ix)
        # Windtraps' water, a row of the same window (Rise of Ix).
        and (kind != WINDTRAPS or config.rise_of_ix)
        # Strategic Push's pledged Solari, a row of the same window (a Rise
        # of Ix Intrigue card).
        and (kind != STRATEGIC_PUSH or config.rise_of_ix)
    )
    # One board-effect resolution per printed automatic icon (OQ-027).
    templates.extend(
        ActionTemplate(
            action_id="resolve_board_effect",
            arguments=(("effect", key),),
        )
        for key in AUTOMATIC_BOARD_ICONS
        # Each board's own icons (plan 15.4): Uprising's rows as they were.
        if (
            key in IMPERIUM_BOARD_ICONS
            if content.base_game is BaseGame.IMPERIUM
            else key not in IMPERIUM_ONLY_BOARD_ICONS
        )
    )
    # One Agent-box resolution per printed automatic icon of a multi-icon
    # card (OQ-027); single-effect boxes keep the argument-less template.
    templates.extend(
        ActionTemplate(
            action_id="resolve_agent_card_effect",
            arguments=(("effect", key),),
        )
        for key in AUTOMATIC_AGENT_ICONS
    )
    # Bringing back one kind of deferred Reveal choice [Main p. 12]: the
    # kinds the Uprising family's cards print, or those the original game's
    # deck cards print (stage P3: the cards transcribed so far).
    original_choices = frozenset(
        effect
        for card in content.imperium_cards
        for effect in card.reveal_choice_effects
    )
    templates.extend(
        ActionTemplate(
            action_id="resume_reveal_choice",
            arguments=(("effect", effect.value),),
        )
        for effect in PersonalCardRevealChoiceEffect
        if (
            content.base_game is BaseGame.UPRISING
            and (config.bloodlines or effect not in BLOODLINES_REVEAL_CHOICE_EFFECTS)
            and (config.immortality or effect not in IMMORTALITY_REVEAL_CHOICE_EFFECTS)
            and effect not in IMPERIUM_REVEAL_CHOICE_EFFECTS
        )
        or (content.base_game is BaseGame.IMPERIUM and effect in original_choices)
    )
    if config.choam_module:
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in (
                "keep_contract_reveal_spice",
                "trash_contract_reveal_for_vp",
                # A Contract Spy may pass up the recall-first without a Spy
                # in supply [Main pp. 11, 20].
                "decline_contract_spy",
                # A Contract recall reward with no target is confirmed.
                "resolve_contract_without_recall",
            )
        )
    templates.extend(_agent_turn_templates(config))
    templates.extend(_endgame_wild_templates(config))
    templates.extend(_reveal_resource_templates())
    # Basic Combat deployment is adjustable until the explicit turn end
    # (OQ-029): add, withdraw, finish.
    templates.extend(
        ActionTemplate(
            action_id="deploy_troops",
            arguments=(("count", count),),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="withdraw_troops",
            arguments=(("count", count),),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.append(ActionTemplate(action_id="finish_agent_turn"))
    if config.rise_of_ix:
        # Rise of Ix's dreadnought, a third kind of unit to deploy and take
        # back [Rise of Ix p. 6], and the Dreadnought icon an Intrigue slot
        # offers; no catalog without the expansion holds these rows.
        templates.extend(_rise_of_ix_unit_templates(config))
        # Local Fence's two Agent-box arrows printed with "-OR-", one row
        # each (``agent_box_abilities.payment_box``).
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in (
                "pay_agent_card_spice_for_solari",
                "pay_agent_card_solari_for_spice",
            )
        )
        # Landing Rights' Freighter icon, an Agent box's two moves
        # (``agent_effects.apply_agent_card_freighter``), and Guild Chief
        # Administrator's, a Reveal choice's (``reveal_turn``).
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in (
                "advance_agent_card_freighter",
                "recall_agent_card_freighter",
                "advance_reveal_freighter",
                "recall_reveal_freighter",
            )
        )
        # Desert Ambush's enemy unit (a troop or a dreadnought) to retreat,
        # by its seat; the Bloodlines catalog holds the troop rows already.
        for seat in range(config.players):
            if not config.bloodlines:
                templates.append(
                    ActionTemplate(
                        action_id="retreat_opponent_troop",
                        arguments=(("player", seat),),
                    )
                )
            templates.append(
                ActionTemplate(
                    action_id="retreat_opponent_troop",
                    arguments=(("dreadnoughts", 1), ("player", seat)),
                )
            )
        # Negotiated Withdrawal's arrow: three units in any mix of troops,
        # dreadnoughts (a seat has two) and, with Bloodlines, Commanders, for
        # an Influence with each Faction (``reveal_turn``).
        templates.extend(
            ActionTemplate(
                action_id="retreat_reveal_units_for_influence",
                arguments=tuple(
                    sorted(
                        (
                            *((("commanders", share),) if share else ()),
                            ("count", 3),
                            *((("dreadnoughts", ships),) if ships else ()),
                            ("faction", faction.value),
                        )
                    )
                ),
            )
            for ships in range(MAX_DREADNOUGHT_DEPLOYMENT + 1)
            for share in range(0, (4 - ships) if config.bloodlines else 1)
            for faction in Faction
        )
        # An Unload card's Reveal box icon, a row each (``rules.unload``).
        templates.extend(
            ActionTemplate(
                action_id=UNLOAD_ICON_ACTION,
                arguments=(("card_id", instance_id), ("effect", name)),
            )
            for instance_id in content.imperium_deck_instance_ids
            for name in dict.fromkeys(name for name, _ in unload_icons(instance_id))
        )
    if config.bloodlines:
        templates.extend(_bloodlines_templates(config))
    elif content.base_game is BaseGame.IMPERIUM:
        # The original game's Gun Thopter asks each opponent to lose a
        # garrisoned troop (stage P3), in the window Holy War opens; a seat
        # with none confirms it (OQ-036 (a)).
        templates.extend(_unit_loss_templates())
        templates.append(ActionTemplate("resolve_unit_loss_without_unit"))
    if content.base_game is BaseGame.IMPERIUM:
        # The original game's Poison Snooper: draw the card it looked at or
        # trash it, or confirm an empty deck (stage P3); only in its catalog,
        # so Uprising's rows stay what they were.
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in (*_DRAW_OR_TRASH_EFFECTS, *_OPTIONAL_PASS_EFFECTS)
        )
        # Double Cross: the opponent whose Conflict troop is lost.
        templates.extend(
            ActionTemplate(
                action_id="choose_opponent_troop_loss", arguments=(("player", seat),)
            )
            for seat in range(config.players)
        )
        # Urgent Mission: the Agent that returns to its Leader -- one row per
        # board space, one for the Conflict -- or the confirmation when none
        # is on the board.
        templates.extend(
            ActionTemplate(
                action_id="recall_agent_for_intrigue",
                arguments=(("space_id", space.space_id),),
            )
            for space in catalog_spaces(config)
        )
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in _RECALL_AGENT_EFFECTS[1:]
        )
    if config.tech_module:
        templates.extend(_tech_templates(config))
    if config.rise_of_ix:
        templates.extend(_ix_tech_templates(config))
    if config.immortality:
        templates.extend(_immortality_templates(config))
    if config.arrakeen_scouts:
        templates.extend(_scouts_templates(config))
    if config.epic_game and not (
        config.bloodlines or config.immortality or config.arrakeen_scouts
    ):
        # Control the Spice's paid trash opens the generic optional-trash
        # frame, which only the Bloodlines, Immortality and Scouts catalogs
        # hold otherwise; it pays with the shared ``pay_agent_card_spice``.
        templates.append(ActionTemplate(action_id="decline_optional_trash"))
        templates.extend(_trash_templates(config, "trash_optional_card"))
    templates.extend(
        ActionTemplate(
            action_id="recall_agent_for_agent_card",
            arguments=(("space_id", space.space_id),),
        )
        for space in catalog_spaces(config)
    )
    templates.extend(
        ActionTemplate(
            action_id="recall_agent_for_imperial_privilege",
            arguments=(("space_id", space.space_id),),
        )
        for space in catalog_spaces(config)
        # Imperial Privilege is an Uprising space (the original board has none).
        if any(space.space_id == "imperial_privilege" for space in content.board_spaces)
    )
    # A Reserve card bought with Persuasion; Foldspace is not (OQ-125).
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in content.reserve_stacks
        if not stack.icon_only
    )
    imperium_instances = content.imperium_deck_instance_ids
    intrigue_instances = content.intrigue_deck_instance_ids
    if config.bloodlines:
        # Piter De Vries' Twisted Intrigue cards are held and played like
        # any Intrigue card once dealt.
        intrigue_instances = (*intrigue_instances, *twisted_intrigue_instance_ids())
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    if config.bloodlines:
        # Engineered Miracle's Command acquisition from the Imperium Row.
        templates.extend(
            ActionTemplate(
                action_id="command_acquire_row_card",
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in imperium_instances
        )
        # Litany Against Fear's turn-start play from the hand.
        templates.extend(
            ActionTemplate(
                action_id="play_turn_start_card",
                arguments=(("card_id", instance_id),),
            )
            for instance_id in imperium_instances
            if instance_id.startswith("imperium:litany_against_fear:")
        )
        if config.choam_module:
            # CHOAM Demands completes any active Contract; Coercive
            # Negotiation takes one of the bank's revealed Contracts.
            templates.extend(
                ActionTemplate(
                    action_id=action_id,
                    arguments=(("instance_id", instance_id),),
                )
                for action_id in ("complete_contract_by_card", "take_trigger_contract")
                for instance_id in content.contract_instance_ids
            )
    if config.choam_module:
        # A completed Contract's reward, icon by icon (stage B2, OQ-112).
        templates.extend(
            ActionTemplate(
                action_id="resolve_contract_reward_icon", arguments=(("effect", kind),)
            )
            for kind in CONTRACT_REWARD_ICON_KINDS
        )
        # A Contract completed in its owner's turn: its icons wait on the
        # turn as rows naming the Contract (stage B3b, OQ-112 (4)).
        templates.extend(
            dict.fromkeys(
                ActionTemplate(
                    action_id="resolve_contract_reward_icon",
                    arguments=(("contract_id", instance_id), ("effect", kind)),
                )
                for instance_id in content.contract_instance_ids
                for kind, _piece in contract_reward_icons(instance_id)
            )
        )
        for action_id in ("take_contract", "complete_contract"):
            templates.extend(
                ActionTemplate(
                    action_id=action_id,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in content.contract_instance_ids
            )
        templates.extend(
            ActionTemplate(
                action_id="recall_agent_for_contract",
                arguments=(("space_id", space.space_id),),
            )
            for space in catalog_spaces(config)
        )
    templates.extend(
        ActionTemplate(
            action_id="pay_agent_card_intrigue_and_spice",
            arguments=(("intrigue_card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    # v106: Branching Path trashes an Intrigue card from hand for a Bene
    # Gesserit Alliance reward (Intrigue card, 2 spice) instead of trashing a
    # personal card for 2 troops (card-face re-transcription, 2026-09-19).
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_for_agent_card",
            arguments=(("intrigue_card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    # v106: Imperial Privilege trashes the Intrigue card, as its printed icon
    # says (OQ-061); the action was ``discard_intrigue_for_imperial_privilege``.
    # The id stays a trash, though since the OQ-061 user ruling of 2026-10-04
    # the trashed card lands on the shared Intrigue discard.
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_for_imperial_privilege",
            arguments=(("card_id", instance_id),),
        )
        for instance_id in intrigue_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="play_intrigue",
            arguments=(("card_id", instance_id), ("option", option)),
        )
        for instance_id in intrigue_instances
        for option in range(len(intrigue_card_for_instance(instance_id).options))
    )
    # Separate printed lines (OQ-058): one template per line index.
    line_count = max(
        (
            len(option.sections)
            for instance_id in intrigue_instances
            for option in intrigue_card_for_instance(instance_id).options
            if option.separate
        ),
        default=0,
    )
    templates.extend(
        ActionTemplate(action_id="use_intrigue_effect", arguments=(("section", index),))
        for index in range(line_count)
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_intrigue_faction",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_intrigue_faction",
            arguments=(("alliance_recipient", recipient), ("faction", faction.value)),
        )
        for faction in Faction
        for recipient in range(config.players)
    )
    templates.extend(_trash_templates(config, "choose_intrigue_discard"))
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            "detonate_shield_wall",
            "keep_shield_wall",
            "decline_intrigue_trash",
            "decline_intrigue_spy",
            # Imperial Privilege's recall with no target is confirmed (the
            # card draw is the space's own ``cards`` icon, codec v142).
            "resolve_imperial_privilege_without_recall",
            "resolve_intrigue_rewards",
        )
    )
    templates.extend(_trash_templates(config, "trash_intrigue_card"))
    # "Deploy up to N troops" (Detonation, Counterattack, Devious) may deploy
    # zero, hence ``count`` 0 (codec v137).
    templates.extend(
        ActionTemplate(
            action_id="deploy_intrigue_troops", arguments=(("count", count),)
        )
        for count in range(0, MAX_INTRIGUE_DEPLOYMENT + 1)
    )
    # Tactical Option's "any number" retreat may choose zero [Main p. 20]
    # [FAQ p. 3], hence ``count`` 0 (codec v137).
    templates.extend(
        ActionTemplate(
            action_id="retreat_intrigue_troops", arguments=(("count", count),)
        )
        for count in range(0, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_intrigue_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_intrigue_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in content.reserve_stacks
    )
    templates.extend(
        ActionTemplate(
            action_id="flip_battle_card",
            arguments=(("card_id", conflict.card.card_id),),
        )
        for conflict in content.conflicts_in_play()
    )
    # An Objective "counts as a Conflict card you've already won" [Objective
    # card], so the flip effects may take it too (OQ-005, codec v130).
    templates.extend(
        ActionTemplate(
            action_id="flip_battle_card",
            arguments=(("card_id", objective.objective_id),),
        )
        for objective in content.objectives
    )
    for action_id in ("manipulate_imperium_row", "acquire_manipulated_imperium"):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in imperium_instances
        )
    if content.base_game is BaseGame.IMPERIUM:
        templates.extend(_deck_top_templates(config, imperium_instances))
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium_with_solari",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve_with_solari",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in content.reserve_stacks
    )
    for space_id in content.maker_space_ids:
        templates.append(
            ActionTemplate(
                action_id="harvest_maker_spice",
                arguments=(("space_id", space_id),),
            )
        )
    for space_id in content.sandworm_space_ids:
        templates.append(
            ActionTemplate(
                action_id="summon_maker_sandworms",
                arguments=(("space_id", space_id),),
            )
        )
    post_ids = tuple(post.post_id for post in content.observation_posts)
    templates.extend(
        ActionTemplate(
            action_id="gather_intelligence",
            arguments=(("post_id", post_id),),
        )
        for post_id in post_ids
    )
    for action_id in (
        "place_acquisition_spy",
        "place_agent_card_spy",
        "place_intrigue_spy",
        "place_leader_spy",
        "recall_spy_for_intrigue",
        "recall_spy_for_leader",
        "recall_spy_for_leader_placement",
        "place_reveal_spy",
        "recall_spy_for_acquisition",
        "recall_spy_for_agent_card",
        "recall_spy_for_espionage",
        "recall_spy_for_reveal",
        "recall_spy_for_reveal_placement",
        "resolve_espionage_place_spy",
        # v107: the generic placement frame serves the Emperor track's
        # Influence 4 Spy [Main p. 7] in every ruleset, not only Bloodlines.
        "place_spy_on_space",
        "recall_spy_for_placement",
        *(("move_spy",) if config.bloodlines else ()),
        *(
            ("place_contract_spy", "recall_spy_for_contract")
            if config.choam_module
            else ()
        ),
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("post_id", post_id),),
            )
            for post_id in post_ids
        )
    for action_id in (
        "place_combat_reward_spy",
        # Without a Spy in supply a Conflict reward Spy may recall one first
        # [Main pp. 11, 20].
        "recall_spy_for_combat_reward",
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("post_id", post_id),),
            )
            for post_id in post_ids
        )
    templates.extend(
        ActionTemplate(
            action_id="recall_spies_for_reveal",
            arguments=(
                ("first_post_id", first_post_id),
                ("second_post_id", second_post_id),
            ),
        )
        for index, first_post_id in enumerate(post_ids)
        for second_post_id in post_ids[index + 1 :]
    )
    if config.rise_of_ix:
        # The Control space the winner's dreadnought is set on, one row for
        # each space of the base game (``content.control_visit_bonuses``).
        templates.extend(
            ActionTemplate(
                action_id=DREADNOUGHT_CONTROL_ACTION,
                arguments=(("space_id", space_id),),
            )
            for space_id in content.control_visit_bonuses
        )
        # Detonation Devices' answer in the same choice (OQ-121 ruling 3).
        templates.append(ActionTemplate(action_id=DREADNOUGHT_DETONATE_ACTION))
    templates.extend(
        ActionTemplate(
            action_id="recall_spies_for_combat_reward",
            arguments=(
                ("first_post_id", first_post_id),
                ("second_post_id", second_post_id),
            ),
        )
        for first_post_id in post_ids
        for second_post_id in post_ids
        if first_post_id != second_post_id
    )
    for action_id in (
        "choose_agent_card_influence",
        "choose_combat_reward_influence",
        "choose_distinct_combat_reward_influence",
        "choose_leader_signet_influence",
        "choose_shipping_influence",
        # The original game's Connections (Earl Memnon Thorvald): only in
        # its catalog, so Uprising's rows stay what they were.
        *(
            ("choose_connections_influence",)
            if content.base_game is BaseGame.IMPERIUM
            else ()
        ),
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
    templates.extend(
        ActionTemplate(
            action_id="exchange_reveal_influence",
            arguments=(
                ("gained_faction", gained_faction.value),
                ("lost_faction", lost_faction.value),
            ),
        )
        for lost_faction in Faction
        for gained_faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="exchange_reveal_influence",
            arguments=(
                ("alliance_recipient", recipient),
                ("gained_faction", gained_faction.value),
                ("lost_faction", lost_faction.value),
            ),
        )
        for lost_faction in Faction
        for gained_faction in Faction
        for recipient in range(config.players)
    )
    templates.extend(
        ActionTemplate(
            action_id="pay_reveal_spice_influence",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="advance_feyd_track",
            arguments=(("space_id", space.space_id),),
        )
        for space in FEYD_TRAINING_TRACK
        if space.space_id != FEYD_TRACK_START
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_leader_imperium",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_instances
    )
    # The original game's Manipulate (Helena Richese) and Masterstroke (the
    # Baron's secret Factions): only in its catalog, so Uprising's rows stay
    # what they were.
    if content.base_game is BaseGame.IMPERIUM:
        # Bene Gesserit Sister's "2 Persuasion OR 2 swords" (stage P3).
        templates.extend(
            ActionTemplate(action_id=action_id)
            for action_id in (
                "gain_two_reveal_persuasion",
                "gain_two_reveal_swords",
                "pay_reveal_solari_for_vp",
                "pay_reveal_spice_for_vp",
                "pay_reveal_solari_for_troops",
                # Firm Grip's "2 Solari -> Influence" (an Agent-box arrow).
                "pay_agent_card_solari",
            )
        )
        templates.extend(
            ActionTemplate(
                action_id="choose_masterstroke_faction",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
        # Shifting Allegiances' "lose 1 Influence + 2 spice -> 2 Influence" (an
        # Agent-box arrow): the Faction lost, and where its Alliance token could
        # go to several seats, the recipient.
        templates.extend(
            ActionTemplate(
                action_id="lose_agent_card_influence",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
        templates.extend(
            ActionTemplate(
                action_id="lose_agent_card_influence",
                arguments=(
                    ("alliance_recipient", recipient),
                    ("faction", faction.value),
                ),
            )
            for faction in Faction
            for recipient in range(config.players)
        )
        # Other Memory's Bene Gesserit card taken from the discard pile (an
        # Agent-box choice).
        templates.extend(_trash_templates(config, "take_agent_card_from_discard"))
        # The Voice's board space (an Agent-box choice): every space on the
        # table, a Leader's own only with its Leader's catalog.
        templates.extend(
            ActionTemplate(
                action_id="block_agent_card_space",
                arguments=(("space_id", space.space_id),),
            )
            for space in catalog_spaces(config)
        )
        templates.extend(
            ActionTemplate(
                action_id="set_aside_leader_imperium",
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in imperium_instances
        )
        # An acquire box paid icon by icon (OQ-141; CHOAM Directorship, Lady
        # Jessica): a row per icon, the chosen Faction's once per Faction.
        templates.extend(_acquire_icon_templates(content.imperium_cards))
    templates.extend(
        ActionTemplate(
            action_id="acquire_leader_reserve",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in content.reserve_stacks
    )
    templates.extend(_trash_templates(config, "trash_leader_card"))
    if config.rise_of_ix:
        # Archduke Armand Ecaz (stage P4e): Coordination's Reveal-turn trash,
        # and Conscript's card on top of the deck while Spaceport lets him
        # put it there.
        templates.extend(_trash_templates(config, "trash_leader_reveal_card"))
        if not config.immortality:
            # Viscount Hundro Moritani's Intelligence keeps one of the
            # Intrigue deck's top two (an Immortality catalog holds the
            # keep-one rows already, for Imperium Ceremony).
            templates.extend(
                ActionTemplate(
                    action_id="keep_peeked_intrigue",
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in intrigue_instances
            )
        templates.extend(
            ActionTemplate(
                action_id="acquire_leader_imperium",
                arguments=(("instance_id", instance_id), ("to_deck_top", True)),
            )
            for instance_id in imperium_instances
        )
        # Guild Contacts' Foldspace goes on the deck the same way, so every
        # Reserve stack has its twin.
        templates.extend(
            ActionTemplate(
                action_id="acquire_leader_reserve",
                arguments=(("card_id", stack.card.card_id), ("to_deck_top", True)),
            )
            for stack in content.reserve_stacks
        )
        # Ilesa Ecaz's One Step Ahead: the hand card set aside at Round Start.
        templates.extend(_trash_templates(config, "set_aside_leader_card"))
        # Tessia Vernius (stage P4e): her first Snooper reward's discard and
        # its refusal, and Duplicity's Influence lost -- naming the Alliance's
        # recipient when several opponents could take it.
        templates.extend(_trash_templates(config, "discard_snooper_card"))
        templates.append(ActionTemplate(action_id="decline_snooper_discard"))
        templates.extend(
            ActionTemplate(
                action_id="lose_leader_influence",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
        templates.extend(
            ActionTemplate(
                action_id="lose_leader_influence",
                arguments=(
                    ("alliance_recipient", recipient),
                    ("faction", faction.value),
                ),
            )
            for faction in Faction
            for recipient in range(config.players)
        )
        # An effect's Influence with each Faction it names, a row each
        # (OQ-153: Quid Pro Quo).
        templates.extend(
            ActionTemplate(
                action_id="resolve_effect_influence",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
    templates.extend(_trash_templates(config, "trash_agent_card"))
    templates.extend(_trash_templates(config, "select_long_live_fighters_draw"))
    templates.extend(_trash_templates(config, "select_long_live_fighters_discard"))
    templates.extend(_trash_templates(config, "discard_agent_card"))
    templates.extend(_trash_templates(config, "discard_opponent_card"))
    # Covert Operation: an opponent with an empty hand confirms it discards
    # nothing (OQ-138, user ruling 2026-10-26; codec v155).
    templates.append(ActionTemplate(action_id="resolve_opponent_discard_without_card"))
    templates.extend(_trash_templates(config, "trash_reveal_card"))
    templates.extend(_trash_templates(config, "trash_combat_reward_card"))
    templates.extend(_trash_templates(config, "trash_card_for_desert_tactics"))
    templates.extend(_trash_templates(config, "select_corrinth_city_discard"))
    templates.extend(_trash_templates(config, "pay_corrinth_city"))
    templates.extend(_reveal_source_templates(config))
    if config.immortality:
        # v143: a grafted turn offers both Agent boxes from the start, box
        # 1's rows tagged ``box=1`` (docs/graft-boxes-plan.md 4.6). Every
        # template an Agent box can offer gets that twin; the untagged one
        # stays box 0's and every source outside a box's (a Servo-Receivers
        # Signet frame, Urgent Shigawire's added draw).
        templates.extend(
            ActionTemplate(
                action_id=template.action_id,
                arguments=tuple(sorted((*template.arguments, (BOX_ARGUMENT, 1)))),
            )
            for template in tuple(templates)
            if template.action_id in BOX_ACTION_IDS
        )
    # Stage B3: the effect and target rows that stand for the whole actions
    # of a frame offering its waiting effects effect first, and of a window
    # offering its own effect by its targets (B3d-2a).
    wholes = tuple(templates)
    templates = [
        template
        for template in wholes
        if template.action_id not in STEP_SPECS
        and template.action_id not in TARGET_SPECS
    ]
    templates.extend(_effect_step_templates(config, wholes))
    return tuple(sorted(dict.fromkeys(templates), key=_template_sort_key))


def _deck_top_templates(
    config: RulesetConfig, imperium_instances: tuple[str, ...]
) -> tuple[ActionTemplate, ...]:
    """The original game's ``to_deck_top`` twins of the Imperium Row and
    Reserve acquisitions (stage P3): Bypass Protocol's "to the top of your
    deck" and, while Recruitment Mission is effective in its owner's Reveal
    turn, every card the seat acquires there [FAQ p. 3]. A Reveal purchase
    (``acquire_imperium``, ``acquire_reserve``, a Manipulate set-aside card),
    an Intrigue acquisition (``acquire_intrigue_*``) and Engineered
    Miracle's Command (Bloodlines); Foldspace is never acquired by a cost
    cap or a purchase (OQ-125). The Tleilaxu Row's twins stand in every
    Immortality catalog (``acquire_tleilaxu``). Only the original game's
    catalogs hold these rows, so Uprising's stay what they were."""

    content = content_for(config)
    reserve = tuple(
        stack.card.card_id for stack in content.reserve_stacks if not stack.icon_only
    )
    templates: list[ActionTemplate] = []
    for action_id in (
        "acquire_imperium",
        "acquire_manipulated_imperium",
        "acquire_intrigue_imperium",
        *(("command_acquire_row_card",) if config.bloodlines else ()),
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("instance_id", instance_id), ("to_deck_top", True)),
            )
            for instance_id in imperium_instances
        )
    for action_id in ("acquire_reserve", "acquire_intrigue_reserve"):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("card_id", card_id), ("to_deck_top", True)),
            )
            for card_id in reserve
        )
    return tuple(templates)


def _acquire_icon_templates(
    cards: tuple[ImperiumCardEntry, ...],
) -> tuple[ActionTemplate, ...]:
    """The rows of the Imperium cards' acquire boxes paid icon by icon
    (``rules.acquire_icons``)."""

    templates: list[ActionTemplate] = []
    for card in cards:
        icons = acquire_box_icons(card)
        for icon in () if icons is None else dict.fromkeys(icons):
            base: tuple[tuple[str, ActionValue], ...] = (
                (ACQUIRED_CARD_ARGUMENT, card.card.card_id),
                ("effect", icon),
            )
            if acquire_icon_faction(icon) is not None or icon == DREADNOUGHT_ICON:
                templates.append(ActionTemplate(ACQUIRE_ICON_ACTION, base))
                continue
            templates.extend(
                ActionTemplate(ACQUIRE_ICON_ACTION, (*base, ("faction", faction.value)))
                for faction in Faction
            )
    return tuple(templates)


def _effect_step_templates(
    config: RulesetConfig, wholes: tuple[ActionTemplate, ...]
) -> tuple[ActionTemplate, ...]:
    """The rows ``rules.effect_steps`` shows the catalog's whole actions by
    (stage B3): each whole template's steps, once per entity that may have
    printed its effect when the state names it (``effect_steps.Printed``),
    and a window's own effect by its target rows (B3d-2a). An Agent box's
    rows name the card types whose box can offer them
    (``_box_effect_cards``) and, for a Signet Ring box, every leader face."""

    faces = _leader_faces(config)
    spaces = tuple(space.space_id for space in catalog_spaces(config))
    box_cards = _box_effect_cards(config)
    intrigue_cards = _intrigue_choice_cards(config)
    rows: dict[ActionTemplate, None] = {}
    for template in wholes:
        if template.action_id in TARGET_SPECS or template.action_id in WINDOW_OWN:
            window_own = DomainAction(template.action_id, 0, template.arguments)
            for row in steps_for(window_own, effect_row=False):
                rows.setdefault(ActionTemplate(row.action_id, row.arguments), None)
        spec = STEP_SPECS.get(template.action_id)
        if spec is None or (
            not isinstance(spec.printed, Printed)
            and not spec.printed.startswith("=")
            and spec.printed not in dict(template.arguments)
        ):
            continue
        whole = DomainAction(template.action_id, 0, template.arguments)
        named: tuple[tuple[Source | None, ActionValue | None], ...]
        if spec.printed == Printed.BOX_CARD:
            effect = steps_for(whole, "", Source.AGENT_CARD)[0]
            arguments = dict(effect.arguments)
            icon = arguments.get("icon", "")
            assert isinstance(icon, str)
            # A refusal's: those of the effect it answers (B3d-3).
            answered = arguments.get("of", effect.action_id)
            assert isinstance(answered, str)
            cards = box_cards.get((answered, icon), ())
            # A Signet Ring box resolves its leader's Signet: only the plain
            # and keyed rows are the box's own, the rest are the leader's.
            signets = faces if template.action_id == "resolve_agent_card_effect" else ()
            named = (
                *((Source.AGENT_CARD, card) for card in cards),
                *((Source.LEADER, face) for face in signets),
            )
        elif spec.printed == Printed.VISITED_SPACE:
            named = tuple(
                (None, space)
                for space in _visited_spaces(config, template.action_id, spaces)
            )
        elif spec.printed == Printed.INTRIGUE_WINDOW:
            named = tuple((None, window) for window in INTRIGUE_WINDOWS)
        elif spec.printed == Printed.RESEARCH_SPACE:
            # A bonus's refusal (B3d-3): each space printing a bonus.
            assert isinstance(spec.of, Mapping)
            named = tuple((None, space) for space in spec.of)
        elif spec.printed == Printed.LEADER:
            own = _LEADER_ROW_FACES.get(template.action_id)
            named = tuple(
                (None, face) for face in faces if own is None or face in own
            )
        elif template.action_id in _REWARD_WINDOW_REFUSALS:
            # A Conflict reward window's refusal or empty confirmation
            # (B3d-3), by each icon whose window offers it and each Conflict
            # printing that icon.
            for icon in _REWARD_WINDOW_REFUSALS[template.action_id]:
                for conflict in content_for(config).conflicts_in_play():
                    if not (
                        icon in conflict_reward_icon_kinds(conflict.card.card_id)
                        or (icon == "choose_influence" and config.promo_cards)
                    ):
                        continue
                    for row in steps_for(whole, conflict.card.card_id, icon=icon):
                        template_row = ActionTemplate(row.action_id, row.arguments)
                        rows.setdefault(template_row, None)
            continue
        elif spec.printed == Printed.CONFLICT_CARD:
            # A Conflict reward icon (stage B3d-1): each Conflict printing
            # it, and any Conflict's first place for Pivotal Gambit's
            # Influence (OQ-025) and for Planetary Array's card (OQ-121).
            # A reward window's other effect (B3d-2a): each Conflict printing
            # an icon that opens the window.
            kind = dict(template.arguments).get("effect")
            kinds = _WINDOW_REWARD_ICONS.get(template.action_id, (kind,))
            named = tuple(
                (None, conflict.card.card_id)
                for conflict in content_for(config).conflicts_in_play()
                if (
                    any(
                        printed in conflict_reward_icon_kinds(conflict.card.card_id)
                        for printed in kinds
                    )
                    or (kind == "choose_influence" and config.promo_cards)
                    or kind
                    in (
                        "planetary_array",
                        "winning_intrigue",
                        DREADNOUGHT_CONTROL,
                        WINDTRAPS,
                        STRATEGIC_PUSH,
                    )
                )
            )
        elif spec.printed == Printed.CONTRACT:
            # A window's row names no Contract: the rows of its Contract are
            # the owner's turn rows' (``contract_id``), already named.
            # A Spy window's recall (B3d-2a) names each Contract printing a
            # Spy icon.
            contract = dict(template.arguments).get("contract_id")
            if template.action_id in _WINDOW_REWARD_ICONS and config.choam_module:
                named = tuple(
                    (None, instance)
                    for instance in content_for(config).contract_instance_ids
                    if any(
                        kind in _WINDOW_REWARD_ICONS[template.action_id]
                        for kind, _ in contract_reward_icons(instance)
                    )
                )
            elif contract is None:
                continue
            else:
                named = ((None, contract),)
        elif spec.printed == Printed.INTRIGUE_CARD:
            # A printed line of a card played line by line (OQ-058), or an
            # effect beside a choice slot's own (B3d-2a).
            line = dict(template.arguments).get("section")
            if not isinstance(line, int):
                named = tuple(
                    (None, card_id)
                    for card_id in intrigue_cards.get(template.action_id, ())
                )
            else:
                held = map(
                    intrigue_card_for_instance, _held_intrigue_instance_ids(config)
                )
                named = tuple(
                    (None, card_id)
                    for card_id in dict.fromkeys(
                        card.card.card_id
                        for card in held
                        if any(
                            option.separate and line < len(option.sections)
                            for option in card.options
                        )
                    )
                )
        elif spec.printed == Printed.ACQUIRED_CARD:
            # An acquired card's Spy window (B3d-2a).
            named = tuple((None, card) for card in _acquisition_spy_cards(config))
        elif spec.printed == Printed.WINDOW:
            # A window, by what opened it: the Spy placement window (B3d-2a),
            # an opponent's or a card's window (B3d-3).
            named = _window_printers(config, template.action_id, box_cards, faces)
        elif spec.printed == Printed.SCOUTS_ITEM:
            # A Scouts market's or choice's refusal (B3d-3).
            items = (
                tuple(auction.auction_id for auction in AUCTIONS)
                if template.action_id == "scouts_decline_card"
                else (
                    # The events' and sales' choices (``offer_scouts_choice``,
                    # a secret reward's ``offer_only_line``).
                    *(event.event_id for event in EVENTS),
                    *(sale.sale_id for sale in SALES),
                )
            )
            named = tuple((None, item) for item in items)
        elif spec.printed == Printed.SKILL_WINDOW:
            named = _skill_window_givers(config)
        elif spec.printed == Printed.TECH_PENDING:
            named = tuple(
                (None, tile.tech_id)
                for tile in (TECH_TILES if config.tech_module else ())
                if "influence" in tile.acquire_effect_keys
            ) + tuple(
                (None, tile.tech_id)
                for tile in (IX_TECH_TILES if config.rise_of_ix else ())
                if {"influence", "distinct_influence"} & set(tile.acquire_effect_keys)
            )
        elif spec.printed == Printed.MISSION:
            # A Scouts mission's plain way in (B3d-2b); the specimen return
            # beside a mission that takes troops from the supply (B3d-4).
            named = tuple(
                (None, mission.mission_id)
                for mission in missions_for(
                    scouts_pool(immortality=config.immortality),
                    choam=config.choam_module,
                )
                if template.action_id != "scouts_return_specimens"
                or mission_takes_supply_troops(mission)
            )
        elif spec.printed == Printed.NAMED and template.action_id in _OWED_DRAW_IDS:
            named = _owed_draw_printers(config, template.action_id, faces)
        elif spec.printed == Printed.NAMED and template.action_id == (
            "resolve_research_icon"
        ):
            # A research space's icon, by each space printing it (B3e-1).
            waiting = dict(template.arguments).get("effect")
            assert isinstance(waiting, str)
            named = tuple(
                (Source.RESEARCH, space) for space in research_icon_spaces(waiting)
            )
        elif spec.printed == Printed.NAMED and template.action_id in _REVEAL_GAIN_OF:
            named = _reveal_gain_printers(config, template.action_id, faces)
        elif spec.printed == Printed.NAMED:
            # An optional trash waiting on the turn, by every entity that
            # may print one (stage B3c-2b); a grafted turn's second card's
            # effect row carries ``box=1``.
            for printer, entity, box in _optional_trash_printers(
                config, box_cards, faces
            ):
                boxed = DomainAction(
                    template.action_id,
                    0,
                    tuple(
                        sorted(
                            (
                                *template.arguments,
                                *((("printed_box", 1),) if box else ()),
                            )
                        )
                    ),
                )
                for row in steps_for(boxed, entity, printer):
                    rows.setdefault(ActionTemplate(row.action_id, row.arguments), None)
            continue
        elif (
            spec.source in _CARD_SOURCES
            and not isinstance(spec.printed, Printed)
            and spec.printed.startswith("=")
            and spec.printed.removeprefix("=") not in content_for(config).card_ids
        ):
            # A row one card prints, in another base game's catalog.
            continue
        else:
            named = ((None, None),)
        for source, printed in named:
            for row in steps_for(whole, printed, source):
                rows.setdefault(ActionTemplate(row.action_id, row.arguments), None)
    return tuple(rows)


# The reward icons whose window a recall first or a payment stands beside
# (stage B3d-2a), on a Conflict card or a Contract.
_WINDOW_REWARD_ICONS: Final[Mapping[str, tuple[str, ...]]] = {
    "pay_combat_reward": ("optional_solari", "optional_spice"),
    "recall_spy_for_combat_reward": ("spy", "deep_cover_spy"),
    "recall_spy_for_contract": ("spy", "deep_cover_spy"),
    # A Contract window's refusal and empty confirmation (B3d-3).
    "decline_contract_spy": ("spy", "deep_cover_spy"),
    "resolve_contract_without_recall": ("recall_agent",),
}
# The sources whose ``=<entity>`` printer is a personal card.
_CARD_SOURCES: Final = frozenset({Source.REVEAL_CARD, Source.AGENT_CARD})
# The one space printing the effect an empty confirmation answers
# (``board_effects``; B3d-3).
_VISITED_SPACES: Final[Mapping[str, tuple[str, ...]]] = {
    "resolve_espionage_without_spy": ("espionage",),
    "resolve_imperial_privilege_without_recall": ("imperial_privilege",),
    # Rise of Ix's four spaces' icons (stage P4c-4, ``rules.ix_board_spaces``)
    # and Spaceport's Foldspace card on top of the deck.
    "commission_board_dreadnought": ("dreadnought",),
    "acquire_board_tech": ("dreadnought",),
    "acquire_negotiation_tech": ("tech_negotiation",),
    "place_board_negotiator": ("tech_negotiation",),
    "advance_board_freighter": ("interstellar_shipping", "smuggling"),
    "recall_board_freighter": ("interstellar_shipping", "smuggling"),
    "acquire_foldspace_to_deck_top": ("foldspace",),
}
# A controlled space's defending troop (B3d-2a): a space a Conflict card's
# control reward names.
_CONTROL_DEFENSE_IDS: Final = frozenset(
    {"deploy_control_defense", "decline_control_defense"}
)


def _visited_spaces(
    config: RulesetConfig, action_id: str, spaces: tuple[str, ...]
) -> tuple[str, ...]:
    """The catalog's spaces whose visit may print ``action_id``'s effect."""

    if action_id in _CONTROL_DEFENSE_IDS:
        visited: tuple[str, ...] = tuple(
            dict.fromkeys(
                conflict.control_space_id
                for conflict in content_for(config).conflicts
                if conflict.control_space_id is not None
            )
        )
    else:
        visited = _VISITED_SPACES.get(action_id, spaces)
    return tuple(space for space in visited if space in spaces)
# The effects an Intrigue card's choice slot offers beside its own, by the
# slot (``ability_executor.piece_rows``): recalling a Spy first, the Shield
# Wall, the look at the deck's top card.
# Bindu Suspension's optional pass of the turn after its draw: pass, or play
# the turn normally (OQ-117).
_OPTIONAL_PASS_EFFECTS: Final = ("pass_turn_intrigue", "keep_turn_intrigue")
# Urgent Mission's recall of one of the seat's own Agents: from a board
# space (one row per space, in the catalog's own loop), from the Conflict, or
# the empty confirmation (OQ-113 (C)).
_RECALL_AGENT_EFFECTS: Final = (
    "recall_agent_for_intrigue",
    "recall_conflict_agent_for_intrigue",
    "skip_intrigue_recall_agent",
)
_INTRIGUE_SLOT_EFFECTS: Final[Mapping[str, tuple[str, ...]]] = {
    "PlaceSpy": ("recall_spy_for_intrigue", "decline_intrigue_spy"),
    "DestroyShieldWall": ("detonate_shield_wall", "keep_shield_wall"),
    "CommissionDreadnought": (
        "commission_intrigue_dreadnought",
        "decline_intrigue_dreadnought",
    ),
    "PlaceNegotiator": (
        "place_intrigue_negotiator",
        "decline_intrigue_negotiator",
    ),
    "Freighter": (
        "advance_intrigue_freighter",
        "recall_intrigue_freighter",
        "decline_intrigue_freighter",
    ),
    "PeekTopCard": (
        "put_back_top_card",
        "discard_top_card",
        "draw_top_card_for_solari",
        "skip_intrigue_top_card",
    ),
    # The slots' refusals and empty confirmations (B3d-3; OQ-113 (C)), a
    # mandatory trash's own below (``_MANDATORY_TRASH_EFFECTS``), Poison
    # Snooper's draw-or-trash look at the deck's top card
    # (``_DRAW_OR_TRASH_EFFECTS``).
    "TrashPersonalCard": ("decline_intrigue_trash",),
    "SetAsideImperiumRowCard": ("skip_intrigue_set_aside",),
    "TrashDiscardPileCard": ("decline_intrigue_trash",),
    "AcquireTleilaxuCard": ("decline_intrigue_tleilaxu",),
    "AcquireCardUpTo": ("skip_intrigue_acquisition",),
    "GainInfluence": ("resolve_intrigue_influence_without_faction",),
    "PassTurn": _OPTIONAL_PASS_EFFECTS,
    "RecallYourAgent": _RECALL_AGENT_EFFECTS,
}
# A mandatory personal-card trash (Twisted Devious) is confirmed with an empty
# hand instead of refused (OQ-113 (C)).
_MANDATORY_TRASH_EFFECTS: Final = ("skip_intrigue_trash",)
# Poison Snooper's look at the deck's top card (``PeekTopCard.draw_or_trash``):
# draw it or trash it, free, and confirmed when the deck is empty (OQ-113 (C)).
_DRAW_OR_TRASH_EFFECTS: Final = (
    "draw_top_card",
    "trash_top_card",
    "skip_intrigue_top_card",
)
# A Conflict reward window's refusal or empty confirmation by the icons
# whose window offers it (``effect_steps.window_icon``, B3d-3).
_REWARD_WINDOW_REFUSALS: Final[Mapping[str, tuple[str, ...]]] = {
    "decline_combat_reward": (
        "optional_solari",
        "optional_spice",
        "optional_recall_spies",
    ),
    "decline_combat_reward_spy": ("spy", "deep_cover_spy"),
    "decline_combat_reward_trash": ("trash",),
    "resolve_combat_trash_without_card": ("trash",),
    "resolve_combat_influence_without_faction": (
        "choose_influence",
        "distinct_influence",
    ),
}


def _intrigue_choice_cards(config: RulesetConfig) -> dict[str, tuple[str, ...]]:
    """For each effect beside an Intrigue choice slot's own, and the
    automatic rewards beside a card's choices (OQ-015), the cards that may
    print it: the Intrigue cards a seat can hold and, with Bloodlines,
    Steersman Y'rkoon's Navigation cards."""

    held = _held_intrigue_instance_ids(config)
    if config.bloodlines:
        held = (*held, *navigation_card_instance_ids())
    cards: dict[str, dict[str, None]] = {}
    for instance_id in held:
        card = intrigue_card_for_instance(instance_id)
        for option in card.options:
            slots = {
                slot
                for wall in (True, False)
                for slot in choice_slots(option.sections, shield_wall_present=wall)
            }
            if not slots:
                continue
            effects = {
                effect
                for slot in slots
                for effect in (
                    *(
                        _DRAW_OR_TRASH_EFFECTS
                        if isinstance(slot, PeekTopCard) and slot.draw_or_trash
                        else _INTRIGUE_SLOT_EFFECTS.get(type(slot).__name__, ())
                    ),
                    *(
                        _MANDATORY_TRASH_EFFECTS
                        if isinstance(slot, TrashPersonalCard) and slot.mandatory
                        else ()
                    ),
                )
            }
            if automatic_rewards(option.sections) and not rewards_come_first(
                option.sections
            ):
                effects.add("resolve_intrigue_rewards")
            for effect in effects:
                cards.setdefault(effect, {})[card.card.card_id] = None
    if config.bloodlines:
        # A Navigation card's refusal (B3d-3).
        cards["decline_navigation"] = {
            intrigue_card_for_instance(instance_id).card.card_id: None
            for instance_id in navigation_card_instance_ids()
        }
    return {effect: tuple(found) for effect, found in cards.items()}


_OWED_DRAW_IDS: Final = frozenset({"draw_owed_intrigue", "draw_owed_card"})
# Whether a printed Reveal line gives the gain of each Reveal gain action
# (stage B3e-1, ``reveal_turn.legal_reveal_gain_actions``).
_REVEAL_GAIN_OF: Final[Mapping[str, Callable[[RevealLine], bool]]] = {
    "recruit_reveal_troops": lambda line: line.recruit_troops > 0,
    "draw_reveal_intrigue": lambda line: line.draw_intrigue > 0,
    "generate_reveal_specimens": lambda line: line.specimens > 0,
    "advance_reveal_tleilaxu": lambda line: line.tleilaxu > 0,
    "advance_reveal_research": lambda line: line.research > 0,
    "gain_reveal_resources": lambda line: bool(
        line.solari or line.spice or line.water
    ),
    "gain_reveal_faction_influence": lambda line: (
        line.influence is not None and line.influence[1] > 0
    ),
}


def _reveal_gain_printers(
    config: RulesetConfig, action_id: str, faces: tuple[str, ...]
) -> tuple[tuple[Source | None, ActionValue | None], ...]:
    """What may print a Reveal gain of ``action_id`` (stage B3e-1,
    ``effect_steps.reveal_gain_printer``): every card a seat of the ruleset
    may own with such a Reveal line (not a spice a Reveal choice holds,
    which the choice pays: Delivery Agreement, Priority Contracts), Hardy's
    troop and Driven's spice, Panopticon's troop and Delivery Bay's Command
    Solari, Muad'Dib's Intrigue card."""

    gives = _REVEAL_GAIN_OF[action_id]
    # (A Tleilaxu card's entry is an Imperium card's; Epic Game Mode's
    # Control the Spice is a starting card.)
    cards: tuple[
        StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry, ...
    ] = (
        *_starting_entries(config),
        *content_for(config).reserve_stacks,
        *content_for(config).imperium_cards,
        *(tleilaxu_cards_for(config.promo_cards) if config.immortality else ()),
    )
    printers: list[tuple[Source | None, ActionValue | None]] = [
        (Source.REVEAL_CARD, card_id)
        for card_id in dict.fromkeys(
            card.card.card_id
            for card in cards
            if any(
                gives(line)
                and not (
                    line.spice > 0
                    and card_holds_reveal_value(card, PrintedRevealValue.SPICE)
                )
                for line in reveal_lines(card)
            )
        )
    ]
    if config.bloodlines:
        skill_gains = {
            "recruit_reveal_troops": lambda skill: skill.reveal_troops > 0,
            "gain_reveal_resources": lambda skill: skill.reveal_spice > 0,
        }
        if action_id in skill_gains:
            printers.extend(
                (Source.COMMANDER, skill.skill_id)
                for skill in SKILLS
                if skill_gains[action_id](skill)
            )
    if config.tech_module:
        tile = {
            "recruit_reveal_troops": "panopticon",
            "gain_reveal_resources": "delivery_bay",
        }.get(action_id)
        if tile is not None:
            printers.append((Source.TECH, tile))
    if action_id == "draw_reveal_intrigue" and "muad_dib" in faces:
        printers.append((Source.LEADER, "muad_dib"))
    return tuple(printers)


def _owed_draw_printers(
    config: RulesetConfig, action_id: str, faces: tuple[str, ...]
) -> tuple[tuple[Source | None, ActionValue | None], ...]:
    """What may earn an owed draw of the row's deck (B3d-4,
    ``effect_steps.owed_origin_printer``): an Intrigue card from the Bene
    Gesserit track's 4, Imperial Birthright, the Tleilaxu track, c7r3, an
    acquire box or a card's "when trashed"; a card from c7r3, CHOAM
    Transports or Hungry for Spice."""

    printers: list[tuple[Source | None, ActionValue | None]] = []
    if action_id == "draw_owed_intrigue":
        printers.append((Source.INFLUENCE_TRACK, "bene_gesserit"))
        printers.extend(
            (Source.LEADER, face) for face in faces if face == "princess_irulan"
        )
        if config.immortality:
            printers.append((Source.TRIGGER, "tleilaxu_track"))
            printers.append((Source.RESEARCH, "c7r3"))
        cards = _personal_card_instance_ids(config)
        printers.extend(
            (Source.ACQUISITION, card)
            for card in dict.fromkeys(
                personal_card_for_instance(instance).card.card_id
                for instance in cards
                if instance.startswith(("imperium:", "tleilaxu:"))
                and acquire_box_draws_intrigue(instance)
            )
        )
        printers.extend(
            (Source.TRIGGER, card.card.card_id)
            for card in content_for(config).imperium_cards
            if card.trash_effect is PersonalCardTrashEffect.DRAW_INTRIGUE_CARD
        )
        return tuple(printers)
    if config.immortality:
        printers.append((Source.RESEARCH, "c7r3"))
    if config.tech_module:
        printers.append((Source.TECH, "choam_transports"))
    printers.extend(
        (Source.LEADER, face)
        for face in faces
        # Hungry for Spice; the original game's Ruthless Negotiator and
        # Spice Addict.
        if face
        in ("steersman_y_rkoon", "count_ilban_richese", "countess_ariana_thorvald")
    )
    return tuple(printers)


def _skill_window_givers(
    config: RulesetConfig,
) -> tuple[tuple[Source | None, ActionValue | None], ...]:
    """What opens a Skill window (B3d-3): Plasteel Blades' tile, and each
    card whose trash acquires the bank's Sardaukar Commander."""

    givers: list[tuple[Source | None, ActionValue | None]] = []
    if config.tech_module:
        givers.append((Source.TECH, "plasteel_blades"))
    if config.bloodlines:
        givers.extend(
            (None, card.card.card_id)
            for card in content_for(config).imperium_cards
            if card.trash_effect is PersonalCardTrashEffect.ACQUIRE_BANK_COMMANDER
        )
    return tuple(givers)


def _box_reward_cards(config: RulesetConfig, reward: type) -> tuple[str, ...]:
    """The card types whose Agent box may resolve ``reward`` (B3d-3): those
    printing it, and, as ``_box_effect_cards`` reads them, Ghola (which
    copies the other grafted card's box, so its own card names the effect)
    and any box its own code resolves."""

    found: dict[str, None] = {}
    for instance_id in _personal_card_instance_ids(config):
        seated = (
            f"player:0:{instance_id}"
            if instance_id.startswith("starter:")
            else instance_id
        )
        card = personal_card_for_instance(seated)
        agent_effect = getattr(card, "agent_effect", None)
        if agent_effect is PersonalCardAgentEffect.LEADER_SIGNET:
            # Its effects are the leader's Signet.
            continue
        ability = None if agent_effect is None else agent_box_ability(agent_effect)
        if (
            card_is_ghola(card)
            or (agent_effect is not None and ability is None)
            or (
                ability is not None
                and any(
                    isinstance(piece, reward)
                    for section in ability.sections
                    for piece in (*section.costs, *section.rewards)
                )
            )
        ):
            found[card.card.card_id] = None
    return tuple(found)


def _intrigue_reward_cards(config: RulesetConfig, reward: type) -> tuple[str, ...]:
    """The Intrigue cards a seat can hold that print ``reward`` (B3d-3)."""

    held = map(intrigue_card_for_instance, _held_intrigue_instance_ids(config))
    return tuple(
        dict.fromkeys(
            card.card.card_id
            for card in held
            if any(
                isinstance(piece, reward)
                for option in card.options
                for section in option.sections
                for piece in (*section.costs, *section.rewards)
            )
        )
    )


def _window_printers(
    config: RulesetConfig,
    action_id: str,
    box_cards: Mapping[tuple[str, str], tuple[str, ...]],
    faces: tuple[str, ...],
) -> tuple[tuple[Source | None, ActionValue | None], ...]:
    """What may open the window whose row ``action_id`` names it by its
    recorded printer (``effect_steps.Printed.WINDOW``)."""

    if action_id in ("recall_spy_for_placement", "decline_spy_placement"):
        return _spy_placement_printers(config)
    if action_id == "decline_tech":
        # Battlefield Research, Rapid Engineering, and the Shipping track's
        # space 3 and the two Landsraad spaces of the overlay (Rise of Ix).
        return (
            *(
                (Source.INTRIGUE, card)
                for card in _intrigue_reward_cards(config, AcquireTech)
            ),
            *(
                (
                    (Source.BOARD_SPACE, SHIPPING_PRINTED),
                    # The Dreadnought and Tech Negotiation spaces' Acquire Tech.
                    (Source.BOARD_SPACE, "dreadnought"),
                    (Source.BOARD_SPACE, "tech_negotiation"),
                )
                if config.rise_of_ix
                else ()
            ),
            # Prince Rhombur Vernius' Ixian Technology (stage P4e).
            *(
                (Source.LEADER, face)
                for face in faces
                if config.rise_of_ix and face == "prince_rhombur_vernius"
            ),
        )
    if action_id == "resolve_opponent_discard_without_card":
        # Covert Operation's, Reverend Mother Mohiam's and Test of Humanity's
        # (an opponent with neither a card nor a deployed troop).
        return tuple(
            dict.fromkeys(
                (Source.AGENT_CARD, card)
                for reward in (
                    EachOpponentDiscardsCard,
                    EachOpponentDiscardsOrLosesDeployedTroop,
                )
                for card in _box_reward_cards(config, reward)
            )
        )
    if action_id == "resolve_unit_loss_without_unit":
        return (
            *(
                (Source.AGENT_CARD, card)
                for card in _box_reward_cards(config, EachOpponentLosesTroop)
            ),
            # Double Cross's chosen opponent (never without a troop to lose
            # in the Conflict, but the window can always be confirmed).
            *(
                (Source.INTRIGUE, card)
                for card in _intrigue_reward_cards(config, OpponentLosesTroop)
            ),
        )
    if action_id == "lose_moved_spy":
        return (
            *(
                (Source.AGENT_CARD, card)
                for card in _box_reward_cards(
                    config, OpponentsMoveSpiesFromVisitedSpace
                )
            ),
            *(
                (Source.INTRIGUE, card)
                for card in _intrigue_reward_cards(config, RedirectSpiesOnTurnSpace)
            ),
        )
    if action_id == "decline_optional_trash":
        return (
            *(
                (printer, entity)
                for printer, entity, box in _optional_trash_printers(
                    config, box_cards, faces
                )
                if not box
            ),
            *(
                (Source.SCOUTS, item)
                for item in (scouts_trash_items() if config.arrakeen_scouts else ())
            ),
        )
    raise ValueError(f"{action_id} names no window printer")


def _acquisition_spy_cards(config: RulesetConfig) -> tuple[str, ...]:
    """The card types whose acquire box places a Spy (B3d-2a)."""

    return tuple(
        dict.fromkeys(
            personal_card_for_instance(instance_id).card.card_id
            for instance_id in _personal_card_instance_ids(config)
            if instance_id.startswith(("imperium:", "tleilaxu:"))
            and acquire_box_places_spy(instance_id)
        )
    )


def _spy_placement_printers(
    config: RulesetConfig,
) -> tuple[tuple[Source | None, ActionValue | None], ...]:
    """What may open the Spy placement window (``spy_moves``, B3d-2a): the
    Emperor track's Influence 4 Spy, a Tech tile's Spy icon and Panopticon,
    False Orders, a Scouts line."""

    printers: list[tuple[Source | None, ActionValue | None]] = [
        (Source.INFLUENCE_TRACK, Faction.EMPEROR.value)
    ]
    if config.tech_module:
        printers.extend(
            (Source.TECH, tile.tech_id)
            for tile in TECH_TILES
            if any(key.startswith("spy_") for key in tile.acquire_effect_keys)
        )
        printers.append((Source.TECH, "panopticon"))
    if config.bloodlines:
        held = map(intrigue_card_for_instance, _held_intrigue_instance_ids(config))
        printers.extend(
            (Source.INTRIGUE, card_id)
            for card_id in dict.fromkeys(
                card.card.card_id
                for card in held
                if any(
                    isinstance(reward, RedirectSpiesOnTurnSpace)
                    for option in card.options
                    for section in option.sections
                    for reward in section.rewards
                )
            )
        )
    if config.arrakeen_scouts:
        printers.extend((Source.SCOUTS, item) for item in scouts_spy_items())
    return tuple(printers)


def _acquire_box_trashes(card: ImperiumCardEntry) -> bool:
    """Whether the Imperium card's acquire box prints the black Trash icon."""

    ability = acquisition_ability(card.acquisition_effect)
    return ability is not None and any(
        isinstance(reward, TrashPersonalCard) for reward in ability.sections[0].rewards
    )


def _optional_trash_printers(
    config: RulesetConfig,
    box_cards: Mapping[tuple[str, str], tuple[str, ...]],
    faces: tuple[str, ...],
) -> tuple[tuple[Source, str, int], ...]:
    """The entities that may print an optional trash waiting on the turn
    (``optional_trash.trash_printer``): a card whose Agent box may trash (box
    1 too with grafting), a Tech tile's acquire or Flip trash (the Tech
    Module's, and Rise of Ix's Disposal Facility, whose acquire icon trashes),
    an Imperium card's acquire box (Rise of Ix's Shai-Hulud), a research
    pair's trash, Arrakis Planetologist's leader."""

    boxes = (0, 1) if config.immortality else (0,)
    return (
        *(
            (Source.AGENT_CARD, card, box)
            for card in box_cards.get(("trash", ""), ())
            for box in boxes
        ),
        *(
            (Source.TECH, tech_id, 0)
            for tech_id in (optional_trash_tech_ids() if config.tech_module else ())
        ),
        *(
            (Source.TECH, tile.tech_id, 0)
            for tile in (IX_TECH_TILES if config.rise_of_ix else ())
            if "trash" in tile.acquire_effect_keys
        ),
        *(
            (Source.ACQUISITION, card.card.card_id, 0)
            for card in content_for(config).imperium_cards
            if _acquire_box_trashes(card)
        ),
        *(
            (Source.RESEARCH, space, 0)
            for space in (research_trash_spaces() if config.immortality else ())
        ),
        *((Source.LEADER, face, 0) for face in faces if face == PLANETOLOGIST_LEADER),
    )


_LEADER_TRASH_FACES: Final = frozenset(
    {"feyd_rautha_harkonnen", "count_hasimir_fenring", "princess_irulan"}
)
_LEADER_SPY_FACES: Final = frozenset(
    {
        "feyd_rautha_harkonnen",
        "lady_margot_fenring",
        "staban_tuek",
        "count_hasimir_fenring",
        "gaius_helen_mohiam",
    }
)
# The leader faces whose Signet or leader ability offers a leader row; the
# rules tell the leaders apart by id (``leader_abilities``).
_LEADER_ROW_FACES: Final[Mapping[str, frozenset[str]]] = {
    "advance_feyd_track": frozenset({"feyd_rautha_harkonnen"}),
    # The original game's Connections.
    "choose_connections_influence": frozenset({"earl_memnon_thorvald"}),
    # The Reveal leader abilities (``leader_abilities._leader_reveal_ability``).
    "recall_spy_for_leader": frozenset({"feyd_rautha_harkonnen"}),
    "retreat_leader_troop": frozenset({"lady_amber_metulli"}),
    "retreat_leader_commander": frozenset({"lady_amber_metulli"}),
    "trash_leader_card": _LEADER_TRASH_FACES,
    "place_leader_spy": _LEADER_SPY_FACES,
    # A leader's refusal: the leaders that print the effect it answers
    # (B3d-3; ``leader_abilities.legal_leader_signet_actions``).
    "decline_leader_card_trash": _LEADER_TRASH_FACES,
    "decline_leader_spy_placement": _LEADER_SPY_FACES,
    "decline_leader_signet_payment": frozenset(
        {
            "lady_jessica",
            "reverend_mother_jessica",
            "staban_tuek",
            "princess_irulan",
            "chani",
            "count_hasimir_fenring",
            "duncan_idaho",
            "gaius_helen_mohiam",
            # The original game's Prudent Diplomacy and Scheme.
            "duke_leto_atreides",
            "baron_vladimir_harkonnen",
            # Rise of Ix's Final Delivery, Ixian Technology, Conscript,
            # Couriers, Guild Contacts and Duplicity.
            "princess_yuna_moritani",
            "prince_rhombur_vernius",
            "archduke_armand_ecaz",
            "viscount_hundro_moritani",
            "ilesa_ecaz",
            "tessia_vernius",
        }
    ),
    "resolve_leader_signet_without_option": frozenset(
        {
            "count_hasimir_fenring",
            "esmar_tuek",
            "gaius_helen_mohiam",
            # The original game's Manipulate with an empty Row.
            "helena_richese",
        }
    ),
    # The original game's Manipulate.
    "set_aside_leader_imperium": frozenset({"helena_richese"}),
    "recall_spy_for_leader_placement": frozenset(
        {
            "feyd_rautha_harkonnen",
            "lady_margot_fenring",
            "staban_tuek",
            "count_hasimir_fenring",
            "gaius_helen_mohiam",
        }
    ),
    "pay_leader_signet_spice": frozenset(
        {"lady_jessica", "reverend_mother_jessica", "staban_tuek", "gaius_helen_mohiam"}
    ),
    # Unseen Network's Solari; the original game's Scheme; Rise of Ix's
    # Final Delivery with every Faction at the top.
    "pay_leader_signet_solari": frozenset(
        {"staban_tuek", "baron_vladimir_harkonnen", "princess_yuna_moritani"}
    ),
    "pay_leader_signet_water": frozenset({"chani"}),
    "gain_leader_signet_troop": frozenset({"shaddam_corrino_iv"}),
    # Shaddam's three Solari; the original game's Prudent Diplomacy; Rise
    # of Ix's Final Delivery and Duplicity's gain.
    "choose_leader_signet_influence": frozenset(
        {
            "shaddam_corrino_iv",
            "duke_leto_atreides",
            "princess_yuna_moritani",
            "tessia_vernius",
        }
    ),
    # Rise of Ix's Duplicity: the Influence lost.
    "lose_leader_influence": frozenset({"tessia_vernius"}),
    # Chronicler's Insight; Rise of Ix's Conscript and Guild Contacts.
    "acquire_leader_imperium": frozenset({"princess_irulan", "archduke_armand_ecaz"}),
    "acquire_leader_reserve": frozenset(
        {"princess_irulan", "archduke_armand_ecaz", "ilesa_ecaz"}
    ),
    # Rise of Ix's One Step Ahead.
    "set_aside_leader_card": frozenset({"ilesa_ecaz"}),
    # Rise of Ix's Coordination.
    "trash_leader_reveal_card": frozenset({"archduke_armand_ecaz"}),
    "retreat_leader_troops": frozenset({"chani"}),
    "place_leader_bonus_spice": frozenset({"esmar_tuek"}),
    "take_leader_bonus_spice": frozenset({"esmar_tuek"}),
    "deploy_leader_agent": frozenset({"duncan_idaho"}),
    "gain_leader_signet_spice": frozenset({"kota_odax_of_ix"}),
    # Rise of Ix's Couriers and Ixian Technology.
    "advance_leader_freighter": frozenset({"viscount_hundro_moritani"}),
    "recall_leader_freighter": frozenset({"viscount_hundro_moritani"}),
    "acquire_leader_tech": frozenset({"prince_rhombur_vernius"}),
    "place_leader_negotiator": frozenset({"prince_rhombur_vernius"}),
    "trash_leader_tech": frozenset({"kota_odax_of_ix"}),
    "use_other_memories": frozenset({"lady_jessica"}),
    "draw_planetologist_intrigue": frozenset({"liet_kynes"}),
    "pay_leader_board_repeat": frozenset({"reverend_mother_jessica"}),
}
# What an Agent box's record pieces let it offer beside its plain
# resolution, as (effect row, icon) pairs (``effect_steps.STEP_SPECS``).
_PIECE_EFFECTS: Final[Mapping[str, tuple[tuple[str, str], ...]]] = {
    "TrashPersonalCard": (("trash", ""),),
    "TrashCard": (("trash", ""),),
    "TrashThisCard": (("trash", ""),),
    "TrashIntrigueCard": (("trash", ""), ("pay", "")),
    "DiscardFromHand": (("discard", ""), ("pay", "")),
    "PayResources": (("pay", ""),),
    "SpendSpecimens": (("pay", ""),),
    "GainInfluence": (("gain_influence", ""),),
    "PlaceSpy": (("place_spy", ""), ("recall_spy", "")),
    "RecallAgent": (("recall_agent", ""),),
    "ForceEnemyRetreat": (("retreat", ""),),
    "CompleteContract": (("complete_contract", ""),),
    "LoseTroops": (("lose_unit", ""),),
    # Shifting Allegiances' cost (no Uprising box prints one).
    "LoseInfluence": (("lose_influence", ""),),
    # Other Memory's card from the discard pile.
    "TakeCardFromDiscard": (("take", ""),),
    # The Voice's "Choose any board space".
    "BlockChosenSpaceForOpponentsNextAgent": (("choose", ""),),
    "AcquireCardForSolari": (("acquire", ""),),
    "AcquireCardUpTo": (("acquire", ""),),
    "GrantCombatDeployment": (("gain", "combat"),),
    "DestroyShieldWall": (("pay", ""),),
    "SummonSandworm": (("pay", ""),),
}
# Keyed icons answered by their own rows instead of an icon row.
_ICON_EFFECTS: Final[Mapping[str, tuple[tuple[str, str], ...]]] = {
    "influence": (("gain_influence", ""),),
    "recall": (("recall_agent", ""),),
    "trash": (("trash", ""),),
    "combat": (("gain", "combat"),),
    "spy": (("place_spy", ""), ("recall_spy", "")),
    "freighter": (("advance", "freighter"), ("collect", "freighter")),
    # Embedded Agent's second Freighter icon: the same two rows.
    "freighter_second": (("advance", "freighter"), ("collect", "freighter")),
}
_HOOK_EFFECTS: Final[Mapping[str, tuple[tuple[str, str], ...]]] = {
    "possible_futures": (("gain_influence", ""),),
    "beasts_spoils": (("trash", ""),),
    "scientific_breakthrough": (("trash", ""),),
    "long_live_the_fighters": (),
}


def _box_effect_cards(
    config: RulesetConfig,
) -> dict[tuple[str, str], tuple[str, ...]]:
    """For each (effect row, icon) an Agent box may offer, the card types
    whose box can: read off the box's record (its plain resolution, keyed
    icons, pieces and hook). A box its own code resolves, and Ghola (which
    copies the other grafted card's box), may offer any; any card's box may
    take Urgent Shigawire's added draw (``effect=cards``)."""

    effects: dict[str, set[tuple[str, str]]] = {}
    unread: list[str] = []
    for instance_id in _personal_card_instance_ids(config):
        seated = (
            f"player:0:{instance_id}"
            if instance_id.startswith("starter:")
            else instance_id
        )
        card = personal_card_for_instance(seated)
        card_type = card.card.card_id
        if card_type in effects or card_type in unread:
            continue
        agent_effect = getattr(card, "agent_effect", None)
        if agent_effect is PersonalCardAgentEffect.LEADER_SIGNET:
            continue
        mine = {("draw", "cards")}
        effects[card_type] = mine
        if card_is_ghola(card):
            unread.append(card_type)
            continue
        if agent_effect is None:
            continue
        ability = agent_box_ability(agent_effect)
        if ability is None:
            unread.append(card_type)
            continue
        mine.add(("resolve", ""))
        if ability.structure is AbilityStructure.CHOOSE_TWO:
            mine.add(("choose", ""))
        for key in (*ability.icons, *ability.armed_icons):
            if key in AGENT_ICON_VERBS:
                mine.add((AGENT_ICON_VERBS[key].value, key))
            mine.update(_ICON_EFFECTS.get(key, ()))
        if ability.hook is not None:
            mine.update(_HOOK_EFFECTS[ability.hook])
        for section in ability.sections:
            for piece in (*section.costs, *section.rewards):
                mine.update(_PIECE_EFFECTS.get(type(piece).__name__, ()))
    every = set().union(*effects.values()) | {
        (shape.verb.value, "")
        for action_id, shape in ACTION_SHAPES.items()
        if shape.source is Source.AGENT_CARD
    }
    for card_type in unread:
        effects.setdefault(card_type, set()).update(every)
    cards: dict[tuple[str, str], list[str]] = {}
    for card_type, kinds in effects.items():
        for kind in kinds:
            cards.setdefault(kind, []).append(card_type)
    return {kind: tuple(types) for kind, types in cards.items()}


def _leader_faces(config: RulesetConfig) -> tuple[str, ...]:
    faces: dict[str, None] = {}
    for leader in content_for(config).leaders:
        faces.setdefault(leader.setup_face_id or leader.leader_id, None)
        if leader.alternate_face_id is not None:
            faces.setdefault(leader.alternate_face_id, None)
    return tuple(faces)


def _rise_of_ix_unit_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Rise of Ix's dreadnought rows (``rules.combat_deployment``,
    ``rules.dreadnought_commission``): the deployment of garrison dreadnoughts
    and its withdrawal, a count each (a seat has two), an Intrigue slot's
    commission and its refusal, and the Tech Negotiation icon's Negotiator
    and its refusal (``rules.negotiators``)."""

    templates: list[ActionTemplate] = [
        ActionTemplate(action_id=action_id, arguments=(("count", count),))
        for action_id in ("deploy_dreadnoughts", "withdraw_dreadnoughts")
        for count in range(1, MAX_DREADNOUGHT_DEPLOYMENT + 1)
    ]
    # Second Wave's "up to two units" deployment, dreadnoughts among them
    # [Rise of Ix p. 6]: the units in all, the share that is dreadnoughts,
    # and with Bloodlines the Commanders' share (``units.unit_count_arguments``).
    # The count-only and the Commander-only rows are the base catalog's.
    templates.extend(
        ActionTemplate(
            action_id="deploy_intrigue_troops",
            arguments=tuple(
                sorted(
                    (
                        *((("commanders", share),) if share else ()),
                        ("count", count),
                        ("dreadnoughts", ships),
                    )
                )
            ),
        )
        for count in range(1, SECOND_WAVE_UNITS + 1)
        for ships in range(1, min(count, MAX_DREADNOUGHT_DEPLOYMENT) + 1)
        for share in range(0, (count - ships + 1) if config.bloodlines else 1)
    )
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            "commission_intrigue_dreadnought",
            "decline_intrigue_dreadnought",
            "place_intrigue_negotiator",
            "decline_intrigue_negotiator",
            "advance_intrigue_freighter",
            "recall_intrigue_freighter",
            "decline_intrigue_freighter",
            # The icons of the four spaces the overlay prints (stage P4c-4).
            "commission_board_dreadnought",
            "acquire_board_tech",
            "acquire_negotiation_tech",
            "place_board_negotiator",
            "advance_board_freighter",
            "recall_board_freighter",
            # Spaceport's Foldspace card on top of the deck.
            "acquire_foldspace_to_deck_top",
            # Prince Rhombur Vernius' Ixian Technology and Viscount Hundro
            # Moritani's Couriers (stage P4e).
            "acquire_leader_tech",
            "place_leader_negotiator",
            "advance_leader_freighter",
            "recall_leader_freighter",
        )
    )
    templates.extend(_shipping_track_templates())
    return tuple(templates)


def _shipping_track_templates() -> tuple[ActionTemplate, ...]:
    """The Freighter's own window and the Shipping track's rewards
    (``rules.shipping_track``): up, recall or neither outside the owner's
    turn, and a row for each reward a recall owes -- Dividends, spice, the
    recruit, the Influence once for each Faction that gains it (and once
    without, every cube at the top, OQ-060) and the discounted Acquire
    Tech."""

    templates = [
        ActionTemplate(action_id=action_id)
        for action_id in (ADVANCE_ACTION, RECALL_ACTION, DECLINE_ACTION)
    ]
    for effect in (DIVIDENDS, SPICE, RECRUIT, INFLUENCE, TECH):
        templates.append(
            ActionTemplate(action_id=REWARD_ACTION, arguments=(("effect", effect),))
        )
    templates.extend(
        ActionTemplate(
            action_id=REWARD_ACTION,
            arguments=(("effect", INFLUENCE), ("faction", faction.value)),
        )
        for faction in Faction
    )
    return tuple(templates)


def _unit_loss_templates() -> tuple[ActionTemplate, ...]:
    """The unit-loss window's rows: the loser picks the zone and the unit
    kind (OQ-036); ``commanders`` marks a Sardaukar Commander like the
    retreat argument does."""

    return tuple(
        ActionTemplate(action_id="lose_unit", arguments=arguments)
        for zone in ("garrison", "conflict")
        for arguments in (
            (("zone", zone),),
            (("commanders", 1), ("zone", zone)),
        )
    )


def _bloodlines_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Sardaukar Commander choices [Bloodlines p. 4] (``rules.sardaukar``)."""

    templates: list[ActionTemplate] = [
        ActionTemplate(action_id=action_id)
        for action_id in (
            "recruit_sardaukar_commander",
            # Bought without a Skill when none is choosable (OQ-031).
            "acquire_sardaukar_commander",
            # False Orders / Holy War: no empty post off the Agent's space,
            # so the forced-to-move Spy is lost [FAQ p. 2] (OQ-065).
            "lose_moved_spy",
            # Holy War: an opponent with no unit to lose confirms it
            # (OQ-036 (a), user ruling 2026-09-30).
            "resolve_unit_loss_without_unit",
            # A bank Commander with no choosable Skill is confirmed
            # (OQ-031, OQ-035 (b), user ruling 2026-10-02).
            "resolve_commander_without_skill",
        )
    ]
    for action_id in (
        "acquire_sardaukar_commander",
        "trash_skill_for_strength",
        "choose_skill",
    ):
        templates.extend(
            ActionTemplate(
                action_id=action_id,
                arguments=(("skill_id", skill.skill_id),),
            )
            for skill in SKILLS
        )
    for action_id in ("deploy_commanders", "withdraw_commanders"):
        templates.extend(
            ActionTemplate(action_id=action_id, arguments=(("count", count),))
            for count in range(1, MAX_COMMANDER_DEPLOYMENT + 1)
        )
    # Commanders are troops for retreats and garrison deployments
    # [Bloodlines p. 4]: the ``commanders`` share of a unit count. A Commander
    # is its own component, not one of the twelve troops, so a seat's units in
    # the Conflict reach MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT and
    # Tactical Option's unbounded "retreat any number" offers every one of
    # them; stopping the count at the troop total left the engine able to
    # offer a retreat this codec could not encode (2026-09-10).
    templates.extend(
        ActionTemplate(
            action_id="retreat_intrigue_troops",
            arguments=(("commanders", share), ("count", count)),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT + 1)
        for share in range(
            max(1, count - MAX_DEPLOYMENT_COUNT),
            min(count, MAX_COMMANDER_DEPLOYMENT) + 1,
        )
    )
    templates.extend(
        ActionTemplate(
            action_id="deploy_intrigue_troops",
            arguments=(("commanders", share), ("count", count)),
        )
        for count in range(1, MAX_INTRIGUE_DEPLOYMENT + 1)
        for share in range(1, count + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="retreat_two_troops_for_reveal",
            arguments=(("commanders", share),),
        )
        for share in (1, 2)
    )
    templates.append(ActionTemplate(action_id="retreat_leader_commander"))
    # Disruption Tactics: one enemy unit (troop or Commander) to retreat.
    for seat in range(4):
        templates.append(
            ActionTemplate(
                action_id="retreat_opponent_troop", arguments=(("player", seat),)
            )
        )
        templates.append(
            ActionTemplate(
                action_id="retreat_opponent_troop",
                arguments=(("commanders", 1), ("player", seat)),
            )
        )
    templates.append(ActionTemplate(action_id="gain_reveal_persuasion"))
    templates.append(ActionTemplate(action_id="take_reveal_contract"))
    templates.extend(
        ActionTemplate(action_id=action_id)
        for action_id in (
            # Bloodlines Leaders: Duncan Idaho, Chani, Liet Kynes, Esmar Tuek.
            "deploy_leader_agent",
            "recall_conflict_agent_for_imperial_privilege",
            # Steersman's Recall Agent icon and Twisted Mentat may likewise
            # recall an Into the Fray Agent from the Conflict (OQ-068).
            "recall_conflict_agent_for_agent_card",
            "pay_leader_signet_water",
            "decline_optional_trash",
            # Liet Kynes' Arrakis Planetologist: the replacement's Intrigue
            # card, its own step beside the trash (codec v142, OQ-106).
            "draw_planetologist_intrigue",
            # A card Hungry for Spice owes in Steersman Y'rkoon's own turn,
            # its own step (codec v142, OQ-106).
            "draw_owed_card",
            "take_tuek_sietch_spice",
            "take_tuek_sietch_card",
            "place_leader_bonus_spice",
            # Twisted Intrigue (Piter De Vries).
            "put_back_top_card",
            "discard_top_card",
            "draw_top_card_for_solari",
            # Twisted Controlled's look at an empty deck and Twisted Devious'
            # mandatory trash with an empty hand, played and confirmed
            # (OQ-113 (C), user ruling 2026-10-24).
            "skip_intrigue_top_card",
            "skip_intrigue_trash",
        )
    )
    templates.extend(
        ActionTemplate(action_id="lose_intrigue_troop", arguments=arguments)
        for zone in ("garrison", "conflict")
        for arguments in ((("zone", zone),), (("commanders", 1), ("zone", zone)))
    )
    # Steersman Y'rkoon: the four Navigation picks and the played option.
    templates.extend(
        ActionTemplate(
            action_id="place_navigation_card", arguments=(("card_id", card_id),)
        )
        for card_id in navigation_card_instance_ids()
    )
    templates.extend(
        ActionTemplate(action_id="play_navigation", arguments=(("option", option),))
        for option in range(2)
    )
    # An arrow cost is optional [Main p. 20]: Navigation card 10 may be
    # declined (spent without effect).
    templates.append(ActionTemplate(action_id="decline_navigation"))
    twisted = twisted_intrigue_instance_ids()
    all_intrigue = (
        *intrigue_deck_instance_ids(
            config.choam_module,
            bloodlines=True,
            tech_module=config.tech_module,
            # Immortality Intrigue can be given or trashed too (soak seed
            # 5038 found Gruesome Sacrifice missing from give_intrigue_card).
            immortality=config.immortality,
        ),
        *twisted,
    )
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_hand_card", arguments=(("card_id", card_id),)
        )
        for card_id in all_intrigue
    )
    if config.choam_module:
        # The Bloodlines Immediate Contract trashes a hand Intrigue card.
        templates.extend(
            ActionTemplate(
                action_id="trash_intrigue_for_contract",
                arguments=(("card_id", card_id),),
            )
            for card_id in all_intrigue
        )
        # Sardaukar II and the High Council token's Recall Agent reward may
        # likewise recall an Into the Fray Agent from the Conflict (OQ-068).
        templates.append(
            ActionTemplate(action_id="recall_conflict_agent_for_contract")
        )
        # A market whose only token is the Immediate, with no Intrigue card
        # to trash: the owner confirms its Contract icons are held (OQ-059).
        templates.append(ActionTemplate(action_id="hold_contract_icons"))
        templates.append(
            ActionTemplate(action_id="resolve_contract_icons_without_contract")
        )
    templates.extend(
        ActionTemplate(
            action_id="give_intrigue_card",
            arguments=(("card_id", card_id), ("player", seat)),
        )
        for card_id in all_intrigue
        for seat in range(config.players)
    )
    # Esmar Tuek's Smuggle Spice: the board's Maker spaces and his own Tuek's
    # Sietch (rows of his face only, ``_LEADER_ROW_FACES``).
    templates.extend(
        ActionTemplate(
            action_id="take_leader_bonus_spice", arguments=(("space_id", space_id),)
        )
        for space_id in (*content_for(config).maker_space_ids, TUEK_SIETCH)
    )
    templates.extend(_trash_templates(config, "trash_optional_card"))
    # Fedaykin Maneuver retreats any number, Commanders included: ``count``
    # is troops plus Commanders (Commanders are troops [Bloodlines p. 4]), so
    # it reaches MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT with the
    # Commander share bounded like ``retreat_intrigue_troops`` above. v105:
    # the share branch stopped at MAX_DEPLOYMENT_COUNT, so a 12-troop Conflict
    # with one Commander offered ``count 13`` that had no template (found by a
    # trained policy in greedy play, 2026-09-18).
    templates.extend(
        ActionTemplate(action_id="retreat_leader_troops", arguments=(("count", count),))
        for count in range(1, MAX_DEPLOYMENT_COUNT + 1)
    )
    templates.extend(
        ActionTemplate(
            action_id="retreat_leader_troops",
            arguments=(("commanders", share), ("count", count)),
        )
        for count in range(1, MAX_DEPLOYMENT_COUNT + MAX_COMMANDER_DEPLOYMENT + 1)
        for share in range(
            max(1, count - MAX_DEPLOYMENT_COUNT),
            min(count, MAX_COMMANDER_DEPLOYMENT) + 1,
        )
    )
    templates.extend(_unit_loss_templates())
    # "Gain one Influence of your choice" as a Reveal choice (Pointing the Way).
    templates.extend(
        ActionTemplate(
            action_id="gain_reveal_influence",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    return tuple(templates)


def _scouts_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Arrakeen Scouts actions (docs/rules/arrakeen-scouts.md), all here so
    the other catalogs never grow with them (design 4.9)."""

    templates: list[ActionTemplate] = [
        # Friends Everywhere: take any Faction's Influence 4 bonus.
        *(
            ActionTemplate(
                action_id="choose_four_bonus", arguments=(("faction", faction.value),)
            )
            for faction in Faction
        ),
        # Subcommittees: open the list during the turn (OQ-076), join one,
        # or decline the chance.
        ActionTemplate(action_id="choose_subcommittee"),
        ActionTemplate(action_id="decline_subcommittee"),
        *(
            ActionTemplate(
                action_id="join_subcommittee",
                arguments=(("subcommittee_id", entry.subcommittee_id),),
            )
            for entry in subcommittees_for(
                scouts_pool(immortality=config.immortality),
                choam=config.choam_module,
            )
        ),
        # A seat's line: the choices of the Scouts effect frame.
        *_trash_templates(config, "scouts_discard"),
        *_trash_templates(config, "scouts_trash_card"),
        *(
            ActionTemplate(
                action_id="scouts_trash_intrigue", arguments=(("card_id", card_id),)
            )
            for card_id in _held_intrigue_instance_ids(config)
        ),
        *(
            ActionTemplate(
                action_id="scouts_recall_spy", arguments=(("post_id", post.post_id),)
            )
            for post in content_for(config).observation_posts
        ),
        *(
            ActionTemplate(
                action_id="scouts_choose_faction",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        ),
        *(
            ActionTemplate(
                action_id="scouts_recall_agent",
                arguments=(("space_id", space_id),),
            )
            for space_id in (
                *(space.space_id for space in catalog_spaces(config)),
                "conflict",  # an Into the Fray Agent (OQ-075 (D))
            )
        ),
        # Immortality: specimens returned to the supply first (0 = none).
        *(
            ActionTemplate(
                action_id="scouts_return_specimens", arguments=(("count", n),)
            )
            for n in range(MAX_SPECIMEN_TOP_UP + 1 if config.immortality else 0)
        ),
        # Political Equilibrium for a seat with every track at 0: the confirm
        # of losing nothing (v152, OQ-131).
        ActionTemplate(action_id="resolve_scouts_loss_without_influence"),
        # Influence losses (Crackdown and the like, Political Equilibrium),
        # with the Alliance recipient when several opponents tie.
        *(
            ActionTemplate(
                action_id="scouts_lose_influence",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        ),
        *(
            ActionTemplate(
                action_id="scouts_lose_influence_to",
                arguments=(
                    ("alliance_recipient", recipient),
                    ("faction", faction.value),
                ),
            )
            for recipient in range(config.players)
            for faction in Faction
        ),
        # A "lose a garrison troop" cost with a troop and a Sardaukar
        # Commander in the garrison: the seat picks which (OQ-105, codec v142).
        *(
            (
                ActionTemplate(action_id="scouts_lose_garrison_unit"),
                ActionTemplate(
                    action_id="scouts_lose_garrison_unit",
                    arguments=(("commanders", 1),),
                ),
            )
            if config.bloodlines
            else ()
        ),
        # A line's later automatic rewards taken ahead of an earlier reward's
        # pending choice (OQ-100).
        ActionTemplate(action_id="scouts_rewards_first"),
        # The trash icon (Oversight, Water Discipline) opens the generic
        # optional-trash frame, which only the Bloodlines and Immortality
        # catalogs hold otherwise.
        *(
            (
                ActionTemplate(action_id="decline_optional_trash"),
                *_trash_templates(config, "trash_optional_card"),
            )
            if not config.bloodlines and not config.immortality
            else ()
        ),
        # Missions: take part (CHOAM Escort: recruit or a face-up Contract of
        # the seat's) or pass, and collect on a visit (Imperial Reserve's
        # pick of spice or Solari).
        ActionTemplate(action_id="scouts_decline_mission"),
        *(
            ActionTemplate(action_id="scouts_join_mission", arguments=(("target", t),))
            for t in (
                "",
                *(
                    ("recruit", *content_for(config).contract_instance_ids)
                    if config.choam_module
                    else ()
                ),
                # Prison Planet paid with a garrison Sardaukar Commander
                # (OQ-105, codec v142; the mission is in the Uprising pool).
                *(
                    ("commander",)
                    if config.bloodlines
                    and any(
                        mission.kind is MissionKind.PRISON_PLANET
                        for mission in missions_for(
                            scouts_pool(immortality=config.immortality),
                            choam=config.choam_module,
                        )
                    )
                    else ()
                ),
            )
        ),
        *(
            ActionTemplate(
                action_id="scouts_collect_mission", arguments=(("choice", choice),)
            )
            for choice in ("", "solari", "spice")
        ),
        # Desert Riding: Hagga Basin's Maker Hooks token instead of its spice.
        ActionTemplate(
            action_id="take_desert_riding_hooks",
            arguments=(("space_id", "hagga_basin"),),
        ),
        # A secret pick among an event's four lines.
        *(
            ActionTemplate(action_id="scouts_secret_pick", arguments=(("pick", i),))
            for i in range(4)
        ),
        # Auctions: a sealed bid and its confirmation, Mercenaries' retreat,
        # Critical Moment's call (0 a pass) and the purchase by card slot.
        ActionTemplate(action_id="confirm_scouts_bid"),
        *(
            ActionTemplate(action_id="scouts_bid", arguments=(("count", n),))
            for n in range(MAX_AUCTION_BID + 1)
        ),
        *(
            ActionTemplate(action_id="scouts_retreat", arguments=(("count", n),))
            for n in range(MAX_MERCENARIES_BID + 1)
        ),
        *(
            ActionTemplate(action_id="scouts_call", arguments=(("count", n),))
            for n in range(MAX_AUCTION_BID + 1)
        ),
        ActionTemplate(action_id="scouts_decline_card"),
        *(
            ActionTemplate(action_id="scouts_take_card", arguments=(("slot", slot),))
            for slot in range(max(auction.revealed_cards for auction in AUCTIONS))
        ),
        # One seat's turn-order pick of an event's or sale's line, or a pass.
        ActionTemplate(action_id="scouts_pass"),
        *(
            ActionTemplate(action_id="scouts_choose_option", arguments=(("option", i),))
            for i in range(_MAX_SCOUTS_OPTIONS)
        ),
        # The same choice with no line the seat can take: take nothing.
        ActionTemplate(action_id="resolve_scouts_choice_without_option"),
    ]
    return tuple(templates)


# The most lines any Scouts event or sale offers, counting a revealed secret
# pick's line, which is taken or left by its index (Covert Operation's
# third line).
_MAX_SCOUTS_OPTIONS = max(
    len(options)
    for options in (
        *(event.options for event in EVENTS),
        *(event.secret_choices for event in EVENTS),
        *(sale.options for sale in SALES),
    )
)


def _held_intrigue_instance_ids(config: RulesetConfig) -> tuple[str, ...]:
    """Every Intrigue card a seat can hold in this ruleset."""

    held = content_for(config).intrigue_deck_instance_ids
    if config.bloodlines:
        # Piter De Vries' Twisted Intrigue cards are held once dealt.
        held = (*held, *twisted_intrigue_instance_ids())
    return held


def _immortality_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Bene Tleilax board choices [Immortality pp. 6-8, 12] (``rules.immortality``)."""

    templates: list[ActionTemplate] = [
        ActionTemplate(action_id=action_id)
        for action_id in (
            "decline_research_bonus",
            # Harvest Cells, played only after the rewards and before the
            # cleanup (OQ-057 (11), user ruling 2026-10-06).
            "decline_conflict_end_intrigue",
            # The window's end once a card was played in it (codec v149,
            # cleanup-2, user decision 2026-10-18: "끝내기").
            "finish_conflict_end_intrigue",
            "pay_research_bonus",
            "return_specimen",
            "use_family_atomics",
            "generate_reveal_specimens",
            "advance_reveal_tleilaxu",
            "advance_reveal_research",
            "pay_agent_card_specimen",
            # Tleilaxu Surgeon, Dissecting Kit, High Priority Travel.
            "pay_agent_card_two_specimens",
            "trash_grafted_card_for_specimen",
            "take_agent_card_combat_icon",
            # Scientific Breakthrough, Slig Farmer.
            "trash_agent_card_self_for_vp",
            "pay_agent_card_five_solari_for_tleilaxu",
        )
    ]
    templates.extend(
        ActionTemplate(
            action_id="lose_reveal_troops_for_specimens", arguments=(("zones", zones),)
        )
        for zones in ("garrison,garrison", "garrison,conflict", "conflict,conflict")
    )
    # A research space's paired icons and c7r3's rewards, each its own step
    # in the owner's order (codec v149, cleanup-2b, rule decision 5).
    templates.extend(
        ActionTemplate(action_id="resolve_research_icon", arguments=(("effect", icon),))
        for icon in RESEARCH_ICON_ORDER
    )
    if not config.bloodlines:
        # c7r3's card, owed in the owner's turn; the Bloodlines catalog has
        # it already (Hungry for Spice, CHOAM Transports).
        templates.append(ActionTemplate(action_id="draw_owed_card"))
    # Piter's troop cost, Stitched Horror's picks, Beguiling Pheromones'
    # grafted-card trash.
    templates.extend(
        ActionTemplate(action_id="lose_agent_card_troop", arguments=(("zone", zone),))
        for zone in ("garrison", "conflict")
    )
    if config.bloodlines:
        # A Sardaukar Commander may pay Piter's troop (OQ-105, codec v142).
        templates.extend(
            ActionTemplate(
                action_id="lose_agent_card_troop",
                arguments=(("commanders", 1), ("zone", zone)),
            )
            for zone in ("garrison", "conflict")
        )
    templates.extend(
        ActionTemplate(
            action_id="choose_agent_card_reward", arguments=(("reward", reward),)
        )
        for reward in ("water", "troop", "trash", "tleilaxu")
    )
    templates.extend(
        ActionTemplate(
            action_id="trash_grafted_card_for_influence",
            arguments=(("card_id", card_id),),
        )
        for card_id in _personal_card_instance_ids(config)
    )
    templates.extend(
        ActionTemplate(
            action_id="lose_reveal_influence_for_vp",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="lose_reveal_influence_for_vp",
            arguments=(("alliance_recipient", recipient), ("faction", faction.value)),
        )
        for faction in Faction
        for recipient in range(config.players)
    )
    # Imperium Ceremony's keep-one choice over any Intrigue card.
    peekable = intrigue_deck_instance_ids(
        config.choam_module,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
        immortality=True,
    )
    if config.bloodlines:
        peekable = (*peekable, *twisted_intrigue_instance_ids())
    templates.extend(
        ActionTemplate(
            action_id="keep_peeked_intrigue", arguments=(("instance_id", instance_id),)
        )
        for instance_id in peekable
    )
    # Tleilaxu Master's free acquisition of a card costing 6 or less.
    templates.extend(
        ActionTemplate(
            action_id="acquire_reserve_by_card",
            arguments=(("card_id", stack.card.card_id),),
        )
        for stack in content_for(config).reserve_stacks
    )
    templates.extend(
        ActionTemplate(
            action_id="acquire_imperium_by_card",
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in imperium_deck_instance_ids(
            config.choam_module,
            config.promo_cards,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=True,
        )
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_research_space", arguments=(("space_id", space_id),)
        )
        for space_id in RESEARCH_SPACES_BY_ID
        if space_id != RESEARCH_START_ID
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_research_influence",
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )
    # v106: c7r3's arrow cost trashes an Intrigue card from hand ("Trash an
    # Intrigue card" [Immortality p. 16]); the peekable set above is every
    # Intrigue card a seat of this ruleset can hold.
    templates.extend(
        ActionTemplate(
            action_id="trash_intrigue_for_research_bonus",
            arguments=(("card_id", instance_id),),
        )
        for instance_id in peekable
    )
    if not config.bloodlines:
        # The trash-and-specimen research spaces open the generic optional
        # trash frame, and Gruesome Sacrifice's troop loss the unit-loss
        # choice; Bloodlines catalogs already hold both.
        templates.append(ActionTemplate(action_id="decline_optional_trash"))
        templates.extend(_trash_templates(config, "trash_optional_card"))
        templates.extend(
            ActionTemplate(action_id="lose_intrigue_troop", arguments=(("zone", zone),))
            for zone in ("garrison", "conflict")
        )
    # The Tleilaxu Row: each deck card to the discard pile or, past the
    # first genetic marker, on top of the deck; Reclaimed Forces' two
    # effects [Immortality pp. 6, 9].
    for instance_id in tleilaxu_deck_instance_ids(config.promo_cards):
        templates.append(
            ActionTemplate(
                action_id="acquire_tleilaxu", arguments=(("instance_id", instance_id),)
            )
        )
        templates.append(
            ActionTemplate(
                action_id="acquire_tleilaxu",
                arguments=(("instance_id", instance_id), ("to_deck_top", True)),
            )
        )
    templates.extend(
        ActionTemplate(
            action_id="acquire_reclaimed_forces", arguments=(("choice", choice),)
        )
        for choice in ("troops", "tleilaxu")
    )
    # Graft [Immortality p. 10]: the partner choice over every personal
    # card, and Twisted Mentat's recall decline.
    templates.extend(
        ActionTemplate(
            action_id="choose_graft_partner", arguments=(("card_id", card_id),)
        )
        for card_id in _personal_card_instance_ids(config)
    )
    templates.append(ActionTemplate(action_id="decline_agent_card_recall"))
    # Harvest Cells' offer: a Row card (to the discard pile or the deck
    # top) or the decline.
    for instance_id in tleilaxu_deck_instance_ids(config.promo_cards):
        templates.append(
            ActionTemplate(
                action_id="acquire_intrigue_tleilaxu",
                arguments=(("instance_id", instance_id),),
            )
        )
        templates.append(
            ActionTemplate(
                action_id="acquire_intrigue_tleilaxu",
                arguments=(("instance_id", instance_id), ("to_deck_top", True)),
            )
        )
    # Reclaimed Forces is a Tleilaxu card Harvest Cells may take too: one
    # template per effect chosen (user ruling 2026-10-06).
    templates.extend(
        ActionTemplate(
            action_id="acquire_intrigue_reclaimed_forces",
            arguments=(("choice", choice),),
        )
        for choice in ("troops", "tleilaxu")
    )
    templates.append(ActionTemplate(action_id="decline_intrigue_tleilaxu"))
    templates.extend(
        ActionTemplate(
            action_id="play_conflict_end_intrigue",
            arguments=(("card_id", instance_id),),
        )
        for instance_id in intrigue_deck_instance_ids(
            config.choam_module,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            immortality=True,
        )
        if any(
            isinstance(option.trigger, OnTroopsLostAtConflictEnd)
            for option in intrigue_card_for_instance(instance_id).options
        )
    )
    return tuple(templates)


def _tech_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Tech Module choices [Bloodlines pp. 6-7] (``rules.tech``)."""

    templates: list[ActionTemplate] = [
        ActionTemplate(action_id="decline_tech"),
        # An acquire Influence with every Faction at the top, outside a
        # turn (codec v149, cleanup-2b).
        ActionTemplate(action_id="resolve_tech_influence_without_faction"),
    ]
    for tile in TECH_TILES:
        base: tuple[tuple[str, ActionValue], ...] = (("tech_id", tile.tech_id),)
        variants: list[tuple[tuple[str, ActionValue], ...]] = []
        if tile.acquire_requires_spy_trash:
            # Advanced Data Analysis: the Spy trashed from the board.
            variants.extend(
                (("post_id", post.post_id), *base)
                for post in content_for(config).observation_posts
            )
        else:
            variants.append(base)
        templates.extend(
            ActionTemplate(action_id="acquire_tech", arguments=arguments)
            for arguments in variants
        )
        for effect in tile.acquire_effect_keys:
            effect_base = (("effect", effect), *base)
            if effect == "influence":
                rewards = tuple(
                    tuple(sorted((*effect_base, ("faction", faction.value))))
                    for faction in Faction
                )
            elif effect == "intrigue_or_card":
                rewards = tuple(
                    tuple(sorted((*effect_base, ("choice", choice))))
                    for choice in ("card", "intrigue")
                )
            elif effect == "shield_wall":
                rewards = (
                    effect_base,
                    tuple(sorted((*effect_base, ("destroy_shield_wall", True)))),
                )
            else:
                rewards = (effect_base,)
            templates.extend(
                ActionTemplate(action_id="resolve_tech_acquire_effect", arguments=args)
                for args in rewards
            )
        if tile.flips:
            templates.append(ActionTemplate(action_id="flip_tech", arguments=base))
    # Forbidden Weapons' Reveal choice: swords with an Influence loss (and
    # the Alliance recipient when several opponents tie), or the trash.
    templates.append(ActionTemplate(action_id="choose_tech_strength"))
    templates.extend(
        ActionTemplate(
            action_id="choose_tech_strength", arguments=(("faction", faction.value),)
        )
        for faction in Faction
    )
    templates.extend(
        ActionTemplate(
            action_id="choose_tech_strength",
            arguments=(("alliance_recipient", seat), ("faction", faction.value)),
        )
        for faction in Faction
        for seat in range(config.players)
    )
    templates.append(ActionTemplate(action_id="choose_tech_trash"))
    # Panopticon's Reveal-turn Spy, taken in the owner's order.
    templates.append(ActionTemplate(action_id="place_tech_spy"))
    # Plasteel Blades' optional trash for an extra Skill.
    templates.append(ActionTemplate(action_id="decline_skill"))
    # Kota Odax of Ix: the Secret Project pick and Reverse Engineering.
    templates.extend(
        ActionTemplate(action_id=action_id, arguments=(("tech_id", tile.tech_id),))
        for action_id in ("choose_secret_project", "trash_leader_tech")
        for tile in TECH_TILES
    )
    templates.append(ActionTemplate(action_id="gain_leader_signet_spice"))
    return tuple(templates)


def _ix_tech_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """Rise of Ix's Tech tile rows (``rules.tech``, stage P4c-1).

    An Acquire Tech buys an Ix tile ("아이콘마다 ... 하나를 얻을 수 있다"
    [Rise of Ix p. 4]) with its Negotiators returned: ``acquire_tech`` names
    the tile alone for none, and adds ``negotiators`` for one up to the tile's
    price (a Negotiator beyond it lowers nothing). Each tile's acquire icons
    are the Tech Module's rows (``resolve_tech_acquire_effect``; Windtraps'
    water and Shuttle Fleet's two Factions have keys of their own, stage
    P4c-2a). Rows a game with the Tech Module already holds are not repeated.
    """

    templates: list[ActionTemplate] = []
    if not config.tech_module:
        templates.extend(
            (
                ActionTemplate(action_id="decline_tech"),
                # An acquire Influence with every Faction at the top.
                ActionTemplate(action_id="resolve_tech_influence_without_faction"),
            )
        )
    for tile in IX_TECH_TILES:
        base: tuple[tuple[str, ActionValue], ...] = (("tech_id", tile.tech_id),)
        templates.append(ActionTemplate(action_id="acquire_tech", arguments=base))
        templates.extend(
            ActionTemplate(
                action_id="acquire_tech",
                arguments=tuple(sorted((("negotiators", returned), *base))),
            )
            for returned in range(1, tile.cost + 1)
        )
        for effect in tile.acquire_effect_keys:
            templates.extend(
                ActionTemplate(action_id="resolve_tech_acquire_effect", arguments=args)
                for args in tech_acquire_effect_arguments(tile, effect)
            )
    # Disposal Facility's Reveal-turn trash of a card in play (OQ-126); the
    # card is the step row's target.
    templates.append(ActionTemplate(action_id="trash_disposal_facility_card"))
    # Its acquire icon's trash opens the generic optional-trash frame (a
    # "trash" key, ``_optional_trash_printers``), which an original game holds
    # only with other modules; the catalog keeps one copy of each row.
    templates.append(ActionTemplate(action_id="decline_optional_trash"))
    templates.extend(_trash_templates(config, "trash_optional_card"))
    # The four Flip tiles (docs/rules/rise-of-ix.md 4, stage P4c-2b): the tile
    # names the whole action, and the card Holoprojectors and Invasion Ships
    # discard is the step row's target.
    templates.extend(
        ActionTemplate(action_id="flip_tech", arguments=(("tech_id", tile.tech_id),))
        for tile in IX_TECH_TILES
        if tile.flips
    )
    # The tiles used by trashing them (stage P4c-2c): Spy Satellites' VP and
    # Sonic Snoopers, whose pick has a row per Intrigue card of the game's deck
    # for the deck's bottom (a Twisted card is never put, OQ-097) and the stop.
    templates.extend(
        ActionTemplate(action_id="trash_tech", arguments=(("tech_id", tile.tech_id),))
        for tile in IX_TECH_TILES
        if tile.ability in TRASH_ABILITIES
    )
    templates.extend(
        ActionTemplate(action_id=PUT_ACTION, arguments=(("card_id", card_id),))
        for card_id in content_for(config).intrigue_deck_instance_ids
    )
    templates.append(ActionTemplate(action_id=FINISH_ACTION))
    return tuple(templates)


def _reveal_resource_templates() -> tuple[ActionTemplate, ...]:
    """One ``gain_reveal_resources`` per distinct printed Reveal resource bundle.

    Reveal resource gains are the owner's own actions (OQ-045, codec v93);
    a bundle is the solari/spice/water of one printed Reveal effect, a
    Skill's Reveal bonus, or Delivery Bay's Command Solari.
    """

    bundles: set[tuple[int, int, int]] = set()
    cards: tuple[
        StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry, ...
    ] = (
        *STARTING_DECK,
        CONTROL_THE_SPICE,
        *RESERVE_STACKS,
        *imperium_cards_for_choam(
            True, True, bloodlines=True, tech_module=True, immortality=True
        ),
    )
    for card in cards:
        for line in reveal_lines(card):
            if line.solari or line.spice or line.water:
                bundles.add((line.solari, line.spice, line.water))
    for skill in SKILLS:
        if skill.reveal_spice:
            bundles.add((0, skill.reveal_spice, 0))
    bundles.add((2, 0, 0))  # Delivery Bay
    return (
        *(
            ActionTemplate(
                action_id="gain_reveal_resources",
                arguments=(("solari", solari), ("spice", spice), ("water", water)),
            )
            for solari, spice, water in sorted(bundles)
        ),
        # Fixed-Faction Reveal Influence, one per Faction (codec v94).
        *(
            ActionTemplate(
                action_id="gain_reveal_faction_influence",
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        ),
    )


def _agent_turn_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """The Agent turn's card picks and space picks (stage B1): every card
    (with its graft choice) that has a placement somewhere, and every space
    variant some card can reach."""

    picks: dict[tuple[str, bool], None] = {}
    spaces: dict[tuple[tuple[str, ActionValue], ...], None] = {}
    for placement in _agent_placement_templates(config):
        arguments = dict(placement.arguments)
        card = arguments["card_id"]
        assert isinstance(card, str)
        picks.setdefault((card, arguments.get("graft") is True), None)
        spaces.setdefault(
            tuple(
                item
                for item in placement.arguments
                if item[0] not in ("card_id", "graft")
            ),
            None,
        )
    return (
        *(
            ActionTemplate(
                action_id="choose_agent_card",
                arguments=(("card_id", card), *((("graft", True),) if graft else ())),
            )
            for card, graft in picks
        ),
        *(
            ActionTemplate(action_id="place_agent", arguments=arguments)
            for arguments in spaces
        ),
    )


def _deck_granted_icons(config: RulesetConfig) -> tuple[AgentIcon, ...]:
    """The Agent icons an Intrigue card of the game's deck gives the card
    played this turn (``GrantAgentIconsThisTurn``), in printed order."""

    icons: dict[AgentIcon, None] = {}
    for instance_id in content_for(config).intrigue_deck_instance_ids:
        for option in intrigue_card_for_instance(instance_id).options:
            for section in option.sections:
                for reward in section.rewards:
                    if isinstance(reward, GrantAgentIconsThisTurn):
                        icons.update(dict.fromkeys(reward.icons))
    return tuple(icons)


def _agent_placement_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    # Emperor's Invitation (Bloodlines) can give any card the Emperor icon
    # for a turn, so the option's catalogs also hold every card's Emperor
    # placements.
    granted: tuple[AgentIcon, ...] = (AgentIcon.EMPEROR,) if config.bloodlines else ()
    # Gaius Helen Mohiam gives every card the Spy icon, Urgent Shigawire
    # gives the next Bene Gesserit card "all Agent icons" and Delivery
    # Logistics borrows its Contracts' icons, so the option's catalogs hold
    # every card's placement on every space.
    every_icon = tuple(AgentIcon) if config.bloodlines else ()
    if config.bloodlines:
        granted = every_icon
    if content_for(config).base_game is BaseGame.IMPERIUM:
        # The original game's Dispatch an Envoy gives the card played this
        # turn the four Faction icons (stage P3): its deck's grants.
        granted = tuple(dict.fromkeys((*granted, *_deck_granted_icons(config))))
    templates: list[ActionTemplate] = []
    for starting_card in _starting_entries(config):
        templates.extend(
            _agent_turn_templates_for_card(
                "starter",
                starting_card,
                granted,
                catalog_spaces(config),
                content_for(config).observation_posts,
                space_discounts=config.tech_module,
                graft=config.immortality,
            )
        )
    for reserve_card in content_for(config).reserve_stacks:
        templates.extend(
            _agent_turn_templates_for_card(
                "reserve",
                reserve_card,
                granted,
                catalog_spaces(config),
                content_for(config).observation_posts,
                space_discounts=config.tech_module,
                graft=config.immortality,
            )
        )
    for imperium_card in content_for(config).imperium_cards:
        if imperium_card.play_data_complete:
            card_granted = (
                every_icon
                if config.bloodlines
                and (
                    Faction.BENE_GESSERIT in imperium_card.factions
                    or imperium_card.agent_icons_from_contracts
                )
                else granted
            )
            templates.extend(
                _agent_turn_templates_for_card(
                    "imperium",
                    imperium_card,
                    card_granted,
                    catalog_spaces(config),
                    content_for(config).observation_posts,
                    space_discounts=config.tech_module,
                    graft=config.immortality,
                )
            )
    if config.immortality:
        for tleilaxu_card in tleilaxu_cards_for(config.promo_cards):
            templates.extend(
                _agent_turn_templates_for_card(
                    "tleilaxu",
                    tleilaxu_card,
                    granted,
                    catalog_spaces(config),
                    content_for(config).observation_posts,
                    space_discounts=config.tech_module,
                    graft=config.immortality,
                )
            )
    return tuple(templates)


def catalog_spaces(config: RulesetConfig) -> tuple[BoardSpace, ...]:
    """Board spaces a catalog holds: Leader-only spaces need Bloodlines."""

    return tuple(
        space
        for space in content_for(config).board_spaces
        if space.required_leader_id is None or config.bloodlines
    )


def _agent_turn_templates_for_card(
    prefix: str,
    card: StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry,
    granted_icons: tuple[AgentIcon, ...],
    spaces: tuple[BoardSpace, ...],
    posts: tuple[ObservationPost, ...],
    *,
    space_discounts: bool = False,
    graft: bool = False,
) -> tuple[ActionTemplate, ...]:
    templates: list[ActionTemplate] = []
    anywhere = card_sends_agent_anywhere(card)
    # Immortality: a Graft card is only ever played grafted; any other card
    # may also be played grafted (the partner is chosen next), and Blank
    # Slate grafted has the four Faction icons [card face]. Kwisatz Haderach
    # is never grafted: the original game takes Immortality from stage P7
    # (``rules.agent_turn._placements_for_hand_card``).
    if not graft or anywhere:
        graft_variants: tuple[bool, ...] = (False,)
    elif card_is_graft(card):
        graft_variants = (True,)
    else:
        graft_variants = (False, True)
    grafted_icons: tuple[AgentIcon, ...] = (
        (
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        )
        if card.card.card_id == "blank_slate"
        else ()
    )
    # Kwisatz Haderach's Agent comes from the Leader (no ``from_space``) or
    # off any board space of the catalog (``rules.agent_turn``).
    from_spaces: tuple[str | None, ...] = (
        (None, *(space.space_id for space in spaces)) if anywhere else (None,)
    )
    for copy in range(card.copies):
        card_id = f"{prefix}:{card.card.card_id}:{copy}"
        for space in spaces:
            for grafted in graft_variants:
                templates.extend(
                    _placement_templates(
                        card,
                        card_id,
                        space,
                        (*granted_icons, *(grafted_icons if grafted else ())),
                        posts,
                        space_discounts=space_discounts,
                        grafted=grafted,
                        from_spaces=from_spaces,
                    )
                )
    return tuple(templates)


def _placement_templates(
    card: StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry,
    card_id: str,
    space: BoardSpace,
    granted_icons: tuple[AgentIcon, ...],
    posts: tuple[ObservationPost, ...],
    *,
    space_discounts: bool,
    grafted: bool,
    from_spaces: tuple[str | None, ...] = (None,),
) -> tuple[ActionTemplate, ...]:
    templates: list[ActionTemplate] = []
    # Kwisatz Haderach goes to "ANY board space (even if occupied)" [card].
    anywhere = card_sends_agent_anywhere(card)
    if (
        space.agent_icon not in card.agent_icons
        and space.agent_icon not in granted_icons
        and AgentIcon.SPY not in card.agent_icons
        # Usurp reaches any space on a Row card's icons [card face].
        and not (grafted and card_is_usurp(card))
        and not anywhere
    ):
        return ()
    cost_options: tuple[int | None, ...] = (
        tuple(range(len(space.cost_options)))
        if space.dynamic_cost is None and len(space.cost_options) > 1
        else (None,)
    )
    # Navigation Chamber (Tech Module): one spice or one Solari off.
    discounts: tuple[str | None, ...] = (None,)
    if space_discounts:
        discounts = (
            None,
            *(
                kind
                for kind in ("spice", "solari")
                if any(
                    getattr(option, kind) > 0 for option in space.cost_options
                )
            ),
        )
    # An occupied space never needs a Spy's Infiltrate for Kwisatz Haderach.
    infiltration_post_ids: tuple[str | None, ...] = (
        None,
        *(
            post.post_id
            for post in posts
            if space.space_id in post.connected_space_ids and not anywhere
        ),
    )
    for cost_option in cost_options:
        for discount in discounts:
            for from_space in from_spaces:
                for infiltrate_post_id in infiltration_post_ids:
                    arguments: list[tuple[str, ActionValue]] = [
                        ("card_id", card_id)
                    ]
                    if cost_option is not None:
                        arguments.append(("cost_option", cost_option))
                    if discount is not None:
                        arguments.append(("discount", discount))
                    if from_space is not None:
                        arguments.append(("from_space", from_space))
                    if grafted:
                        arguments.append(("graft", True))
                    if infiltrate_post_id is not None:
                        arguments.append(
                            ("infiltrate_post_id", infiltrate_post_id)
                        )
                    arguments.append(("space_id", space.space_id))
                    templates.append(
                        ActionTemplate(
                            action_id="agent_turn",
                            arguments=tuple(arguments),
                        )
                    )
    return tuple(templates)


def _endgame_wild_templates(
    config: RulesetConfig,
) -> tuple[ActionTemplate, ...]:
    battle_cards = (
        *(
            (conflict.card.card_id, conflict.battle_icon)
            for conflict in content_for(config).conflicts_in_play()
        ),
        *(
            (objective.objective_id, objective.battle_icon)
            for objective in content_for(config).objectives
        ),
    )
    wild_card_ids = tuple(
        card_id for card_id, icon in battle_cards if icon is BattleIcon.WILD
    )
    matching_card_ids = tuple(
        card_id for card_id, icon in battle_cards if icon not in (None, BattleIcon.WILD)
    )
    templates = [
        ActionTemplate(
            action_id="match_endgame_wild_icon",
            arguments=(
                ("matching_card_id", matching_card_id),
                ("wild_card_id", wild_card_id),
            ),
        )
        for wild_card_id in wild_card_ids
        for matching_card_id in matching_card_ids
    ]
    # Wild-with-wild pairs [Bloodlines p. 5], once each in sorted order.
    sorted_wild = sorted(wild_card_ids)
    templates.extend(
        ActionTemplate(
            action_id="match_endgame_wild_icon",
            arguments=(("matching_card_id", second), ("wild_card_id", first)),
        )
        for index, first in enumerate(sorted_wild)
        for second in sorted_wild[index + 1 :]
    )
    return tuple(templates)


# The ids each Reveal choice effect offers with ``source`` (codec v147,
# ``rules.reveal_turn.SOURCED_REVEAL_ACTION_IDS``), with what else names the
# row: an observation post, the Commander share of a retreat or a troop
# move, a Faction, or nothing.
_SOURCED_SPY_PLACEMENT: Final = (
    "place_reveal_spy",
    "recall_spy_for_reveal_placement",
)
# A plain Spy icon also passes up its empty-supply recall-first (OQ-057 (14)).
_SOURCED_PLAIN_SPY: Final = (*_SOURCED_SPY_PLACEMENT, "decline_reveal_spy_recall")
_SOURCED_TROOP_MOVE: Final = ("deploy_reveal_card_troop", "retreat_reveal_card_troop")
# The troops a count of which a Reveal choice moves (original game).
_SOURCED_TROOPS_MOVE: Final = (
    "deploy_reveal_card_troops",
    "retreat_reveal_card_troops",
)
_Choice = PersonalCardRevealChoiceEffect
_SOURCED_REVEAL_ROWS: Final[Mapping[_Choice, tuple[str, ...]]] = {
    _Choice.PLACE_SPY: _SOURCED_PLAIN_SPY,
    _Choice.PLACE_TWO_SPIES: _SOURCED_PLAIN_SPY,
    _Choice.COMMAND_PLACE_SPY: _SOURCED_PLAIN_SPY,
    _Choice.PLACE_SPY_OR_GAIN_TWO_STRENGTH: (
        _SOURCED_SPY_PLACEMENT
    ),
    _Choice.COMMAND_GAIN_CHOSEN_INFLUENCE: ("gain_reveal_influence",),
    _Choice.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH: ("gain_reveal_influence",),
    _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP: _SOURCED_TROOP_MOVE,
    _Choice.MAY_DEPLOY_OR_RETREAT_ONE_TROOP_IF_FREMEN_BOND: _SOURCED_TROOP_MOVE,
    _Choice.MAY_DEPLOY_ONE_TROOP: ("deploy_reveal_card_troop",),
    # Sardaukar Legion, Scout, Chani (original game): a count of troops.
    _Choice.MAY_DEPLOY_UP_TO_THREE_TROOPS: ("deploy_reveal_card_troops",),
    _Choice.MAY_RETREAT_UP_TO_TWO_TROOPS: ("retreat_reveal_card_troops",),
    _Choice.MAY_RETREAT_ANY_NUMBER_OF_TROOPS: ("retreat_reveal_card_troops",),
    # Duncan, Loyal Blade (original game promo): the trash, then one
    # direction and a count, none included.
    _Choice.MAY_TRASH_SELF_TO_MOVE_ANY_NUMBER_OF_TROOPS: _SOURCED_TROOPS_MOVE,
    _Choice.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED: (
        "recall_spy_for_reveal",
    ),
    _Choice.MAY_RECALL_SPY_FOR_THREE_STRENGTH: (
        "recall_spy_for_reveal",
    ),
    _Choice.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH: (
        "retreat_two_troops_for_reveal",
    ),
    _Choice.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION: (
        "retreat_two_troops_for_reveal",
    ),
    _Choice.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS: (
        "keep_contract_reveal_spice",
        "trash_contract_reveal_for_vp",
    ),
    _Choice.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH: (
        "trash_reveal_card",
    ),
    _Choice.COMMAND_MAY_TRASH_CARD: ("trash_reveal_card",),
    _Choice.MAY_TRASH_SELF_FOR_COMBAT_ICON: (
        "trash_reveal_card",
    ),
    _Choice.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS: (
        "trash_reveal_card",
    ),
}


def _reveal_source_templates(config: RulesetConfig) -> tuple[ActionTemplate, ...]:
    """The ``source``-named Reveal choice rows of the catalog's cards (v147).

    One per card of the catalog's Imperium deck whose choice effect offers
    such an id, with every value its other arguments can take: a post for
    the Spy rows, the Commander share of a retreat or a troop move
    (Bloodlines), a Faction for an Influence gain, the trashed card (any
    personal card for Shrouded Counsel, another Emperor card for Calculus of
    Power, the card itself for a self-trash).
    """

    personal = _personal_card_instance_ids(config)
    post_ids = tuple(post.post_id for post in content_for(config).observation_posts)
    shares: tuple[tuple[tuple[str, ActionValue], ...], ...] = (
        ((), (("commanders", 1),), (("commanders", 2),))
        if config.bloodlines
        else ((),)
    )
    # A Sardaukar Commander is a troop [Bloodlines p. 4].
    one_unit: tuple[tuple[tuple[str, ActionValue], ...], ...] = (
        ((), (("commanders", 1),)) if config.bloodlines else ((),)
    )
    templates: dict[ActionTemplate, None] = {}
    for entry in content_for(config).imperium_cards:
        source = entry.card.card_id
        own = tuple(
            instance_id
            for instance_id in personal
            if instance_id.startswith(f"imperium:{source}:")
        )
        for effect in entry.reveal_choice_effects:
            for action_id in _SOURCED_REVEAL_ROWS.get(effect, ()):
                variants: tuple[tuple[tuple[str, ActionValue], ...], ...]
                if action_id in _SOURCED_SPY_PLACEMENT or (
                    action_id == "recall_spy_for_reveal"
                ):
                    variants = tuple((("post_id", post_id),) for post_id in post_ids)
                elif action_id == "retreat_two_troops_for_reveal":
                    variants = shares
                elif action_id in _SOURCED_TROOP_MOVE:
                    variants = one_unit
                elif action_id in _SOURCED_TROOPS_MOVE:
                    # One row per count the card allows: up to its most, or
                    # as many as a seat can have in play ("any number"); with
                    # Bloodlines also per Sardaukar Commander share, a
                    # Commander being a troop [Bloodlines p. 4], as the engine
                    # offers them (``units.unit_count_arguments``).
                    shape = troops_move_shape(effect)
                    # Duncan, Loyal Blade names a count from none (one
                    # direction and a count, "any number" [FAQ p. 3]).
                    assert shape is not None or troops_trash_move(effect)
                    variants = unit_count_arguments(
                        minimum=0 if shape is None else 1,
                        maximum=None if shape is None else shape[1],
                        troops=MAX_DEPLOYMENT_COUNT,
                        commanders=(
                            MAX_COMMANDER_DEPLOYMENT if config.bloodlines else 0
                        ),
                    )
                elif action_id == "gain_reveal_influence":
                    variants = tuple(
                        (("faction", faction.value),) for faction in Faction
                    )
                elif action_id == "trash_reveal_card":
                    variants = tuple(
                        (("card_id", card_id),)
                        for card_id in _reveal_trash_targets(effect, personal, own)
                    )
                else:
                    variants = ((),)
                templates.update(
                    (
                        ActionTemplate(
                            action_id=action_id,
                            arguments=tuple(
                                sorted((*arguments, (SOURCE_ARGUMENT, source)))
                            ),
                        ),
                        None,
                    )
                    for arguments in variants
                )
    return tuple(templates)


def _reveal_trash_targets(
    effect: PersonalCardRevealChoiceEffect,
    personal: tuple[str, ...],
    own: tuple[str, ...],
) -> tuple[str, ...]:
    """The cards a Reveal choice's ``trash_reveal_card`` may name."""

    if effect is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD:
        return personal
    if effect is _Choice.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH:
        # A starter's catalog id drops its seat prefix (``_normalize_arguments``).
        return tuple(
            card_id
            for card_id in personal
            if Faction.EMPEROR
            in personal_card_for_instance(
                f"player:0:{card_id}" if card_id.startswith("starter:") else card_id
            ).factions
        )
    return own


def _trash_templates(
    config: RulesetConfig,
    action_id: str,
) -> tuple[ActionTemplate, ...]:
    return tuple(
        ActionTemplate(
            action_id=action_id,
            arguments=(("card_id", card_id),),
        )
        for card_id in _personal_card_instance_ids(config)
    )


def _starting_entries(config: RulesetConfig) -> tuple[StartingCardEntry, ...]:
    """Every starting card a seat owns: its deck and, in Epic Game Mode with
    Immortality, the Control the Spice that starts in the discard pile."""

    content = content_for(config)
    return (*content.starting_deck_entries, *content.starting_discard_entries)


def _personal_card_instance_ids(config: RulesetConfig) -> tuple[str, ...]:
    card_ids = [
        f"starter:{card.card.card_id}:{copy}"
        for card in _starting_entries(config)
        for copy in range(card.copies)
    ]
    card_ids.extend(content_for(config).imperium_deck_instance_ids)
    card_ids.extend(
        f"reserve:{stack.card.card_id}:{copy}"
        for stack in content_for(config).reserve_stacks
        for copy in range(stack.copies)
    )
    if config.immortality:
        card_ids.extend(tleilaxu_deck_instance_ids(config.promo_cards))
    return tuple(card_ids)


def _normalize_arguments(
    arguments: tuple[tuple[str, ActionValue], ...],
    actor: int,
) -> tuple[tuple[str, ActionValue], ...]:
    prefix = f"player:{actor}:starter:"
    return tuple(
        (key, f"starter:{value.removeprefix(prefix)}")
        if isinstance(value, str) and value.startswith(prefix)
        else (key, value)
        for key, value in arguments
    )


def _denormalize_arguments(
    arguments: tuple[tuple[str, ActionValue], ...],
    actor: int,
) -> tuple[tuple[str, ActionValue], ...]:
    return tuple(
        (key, f"player:{actor}:{value}")
        if isinstance(value, str) and value.startswith("starter:")
        else (key, value)
        for key, value in arguments
    )


def _template_sort_key(template: ActionTemplate) -> tuple[str, str]:
    return template.action_id, repr(template.arguments)
