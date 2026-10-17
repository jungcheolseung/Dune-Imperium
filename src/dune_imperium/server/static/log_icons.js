"use strict";

/* ---------- action log icons ---------- */

/* The Steam app's Action Log puts one picture beside each entry. The log
   here does the same for an event line (panels.js logEventLine) and a
   "game" card's head (panels.js neutralCard), following the picture the
   app's own log chooses for that kind of entry: a trashed card gets the
   app log's red cross, an Intrigue draw its bare Intrigue glyph, a played
   Intrigue the tilted card.

   A table key is one of
   - "name": a rulebook icon (catalog.icons, display.icons.ICON_NAMES);
   - "log:name": one of the log's own pictures (catalog.log_icons,
     display.log_icons.LOG_ICON_NAMES);
   - "alliance:faction": a Faction's Alliance token (catalog.alliance_tokens).
   "{faction}" takes the event's Faction, "{agent_icon}" the Agent icon of
   the board space the event names. tests/server/test_log_icon_table.py checks
   every kind against EVENT_LABELS and every name against its picture set.

   A kind that is not here (a decline, a skipped or expired effect, the
   bookkeeping kinds, Arrakeen Scouts and Bloodlines kinds the app has no
   pictures for) stays text only, and so does every line on a machine
   without the pictures: the log is then today's. The labels' own inline
   icons stay as they are. */
const LOG_EVENT_ICONS = {
  // The Conflict and its combat.
  battle_card_flipped: "log:conflict",
  battle_icons_matched: "log:conflict",
  combat_cleaned_up: "log:conflict",
  combat_intrigue_finished: "log:conflict",
  combat_intrigue_started: "log:conflict",
  combat_reward_gained: "log:conflict",
  combat_reward_paid: "log:conflict",
  conflict_end_trigger_offered: "log:conflict",
  conflict_revealed: "log:conflict",
  conflict_won: "log:conflict",
  endgame_wild_matched: "log:conflict",
  combat_strength_gained: "sword",
  reveal_strength_gained: "sword",
  // Units going into and out of the Conflict.
  commanders_deployed: "log:troop_deploy",
  control_defense_deployed: "log:troop_deploy",
  leader_agent_deployed: "log:troop_deploy",
  scouts_mercenaries_deployed: "log:troop_deploy",
  scouts_troops_to_conflict: "log:troop_deploy",
  troops_deployed: "log:troop_deploy",
  commanders_withdrawn: "log:troop_retreat",
  scouts_mercenaries_retreated: "log:troop_retreat",
  troops_retreated: "log:troop_retreat",
  troops_withdrawn: "log:troop_retreat",
  acquisition_troop_recruited: "troop",
  leader_signet_troops_recruited: "troop",
  reveal_troops_recruited: "troop",
  sardaukar_commander_recruited: "troop",
  scouts_mission_troops: "troop",
  scouts_troops_lost: "troop",
  shortfall_refilled: "troop",
  unit_lost: "troop",
  // Agents and Spies.
  agent_placed: "agent_icon_{agent_icon}",
  agent_recalled: "recall_agent",
  agents_recalled: "recall_agent",
  spy_lost: "spy",
  spy_placed: "spy",
  spy_trashed: "spy",
  spies_recalled: "recall_spy",
  spy_recalled: "recall_spy",
  spy_recalled_for_infiltrate: "recall_spy",
  // Cards.
  cards_drawn: "draw",
  research_drew_card: "draw",
  top_card_drawn: "draw",
  card_discarded: "discard",
  top_card_discarded: "discard",
  agent_card_trashed_for_vp: "log:card_trashed",
  card_trashed: "log:card_trashed",
  contract_reveal_card_trashed_for_vp: "log:card_trashed",
  contract_trashed: "log:card_trashed",
  imperium_card_removed: "log:card_trashed",
  intrigue_card_trashed: "log:card_trashed",
  personal_card_trash_effect_resolved: "log:card_trashed",
  skill_trashed: "log:card_trashed",
  tech_trashed: "log:card_trashed",
  usurped_card_trashed: "log:card_trashed",
  intrigue_discard_shuffled: "log:reshuffle",
  personal_discard_shuffled: "log:reshuffle",
  card_acquired: "persuasion",
  reclaimed_forces_acquired: "persuasion",
  reveal_persuasion_gained: "persuasion",
  reveal_started: "persuasion",
  tleilaxu_card_acquired: "persuasion",
  // Intrigue cards.
  intrigue_cost_paid: "log:intrigue_played",
  intrigue_effect_used: "log:intrigue_played",
  intrigue_kept_faceup: "log:intrigue_played",
  intrigue_played: "log:intrigue_played",
  intrigue_triggered: "log:intrigue_played",
  intrigue_card_drawn: "log:intrigue",
  intrigue_card_given: "log:intrigue",
  intrigue_card_given_identity: "log:intrigue",
  intrigue_card_kept: "log:intrigue",
  intrigue_cards_peeked: "log:intrigue",
  intrigue_card_stolen: "steal_intrigue",
  intrigue_card_stolen_identity: "steal_intrigue",
  // Influence and Alliances.
  agent_card_influence_chosen: "influence_{faction}",
  combat_reward_influence_chosen: "influence_{faction}",
  influence_gained: "influence_{faction}",
  influence_track_bonus_gained: "influence_{faction}",
  intrigue_influence_chosen: "influence_{faction}",
  leader_influence_bonus_gained: "influence_{faction}",
  first_place_influence_pledged: "influence_any",
  influence_lost: "log:influence_down_{faction}",
  alliance_gained: "alliance:{faction}",
  alliance_lost: "alliance:{faction}",
  alliance_transferred: "alliance:{faction}",
  // Resources and Victory Points.
  contract_icons_converted_to_solari: "solari",
  leader_signet_solari_paid: "solari",
  reveal_solari_gained: "solari",
  contract_reveal_spice_gained: "spice",
  leader_ability_spice_gained: "spice",
  leader_signet_spice_paid: "spice",
  maker_spice_added: "spice",
  reveal_spice_paid: "spice",
  scouts_helix_spice: "spice",
  scouts_maker_spice_added: "spice",
  leader_board_repeat_paid: "water",
  corrinth_city_payment_resolved: "victory_point",
  reveal_victory_point_gained: "victory_point",
  victory_points_gained: "victory_point",
  game_finished: "log:vp_winner",
  // Contracts, Control, the Maker and the Shield Wall.
  contract_completed: "contract",
  contract_icons_fizzled: "contract",
  contract_icons_held: "contract",
  contract_icons_reopened: "contract",
  contract_taken: "contract",
  contracts_revealed: "contract",
  scouts_contracts_cleared: "contract",
  control_bonus_gained: "control",
  scouts_marker_returned: "control",
  reveal_sandworm_deployed: "sandworm",
  sandworm_deployed: "sandworm",
  sandworms_replaced: "sandworm",
  scouts_shield_wall_rebuilt: "shield_wall",
  shield_wall_destroyed: "shield_wall",
  shield_wall_kept: "shield_wall",
  leader_signet_resolved: "signet_ring",
  leader_signet_started: "signet_ring",
  // Immortality and the Tech module.
  scouts_specimens_paid: "specimen",
  specimen_returned: "specimen",
  specimens_generated: "specimen",
  family_atomics_used: "log:family_atomics",
  genetic_marker_reached: "log:research",
  research_advanced: "log:research",
  research_bonus_paid: "log:research",
  research_resources_gained: "log:research",
  tleilaxu_advanced: "log:tleilaxu",
  tleilaxu_track_end: "log:tleilaxu",
  secret_project_chosen: "log:tech",
  secret_project_identity: "log:tech",
  tech_acquire_effect_resolved: "log:tech",
  tech_acquired: "log:tech",
  tech_flipped: "log:tech",
  tech_reveal_bonus: "log:tech",
  tech_revealed: "log:tech",
};

/* A table key with its slots filled from the event, or null when the event
   lacks what a slot needs. */
function logIconKey(template, payload) {
  let missing = false;
  const key = template.replace(/\{([a-z_]+)\}/g, (_whole, slot) => {
    let value = null;
    if (slot === "faction") value = payload.faction;
    if (slot === "agent_icon") {
      const space = (state.catalog.spaces || {})[payload.space_id];
      value = space ? space.agent_icon : null;
    }
    if (typeof value !== "string" || !value) missing = true;
    return value;
  });
  return missing ? null : key;
}

function logIconUrl(key) {
  const catalog = state.catalog || {};
  if (key.startsWith("log:")) return (catalog.log_icons || {})[key.slice(4)] || null;
  if (key.startsWith("alliance:")) {
    return (catalog.alliance_tokens || {})[key.slice(9)] || null;
  }
  return (catalog.icons || {})[key] || null;
}

/* The picture on the app's dark icon tile (log_icons.css), or null without
   the picture. `label` is its alt text: an image's alt is no part of the
   line's textContent, so the log reads as before. */
function logIconTile(key, label) {
  const url = logIconUrl(key);
  if (!url) return null;
  const tile = document.createElement("span");
  tile.className = "log-icon";
  tile.dataset.icon = key;
  const img = document.createElement("img");
  img.src = url;
  img.alt = label;
  img.draggable = false;
  tile.appendChild(img);
  return tile;
}

function logEventIcon(event) {
  const template = LOG_EVENT_ICONS[event.kind];
  if (!template || !state.catalog) return null;
  const key = logIconKey(template, event.payload || {});
  if (!key) return null;
  return logIconTile(key, phraseText(EVENT_LABELS[event.kind] || ""));
}

/* panels.js logEventLine's hook: the icon goes first and the words into
   one span, which keeps the line's muted look while the picture stays at
   full strength (log_icons.css). */
function addLogEventIcon(line, event) {
  const tile = logEventIcon(event);
  if (!tile) return;
  const words = document.createElement("span");
  words.className = "log-text";
  words.append(...line.childNodes);
  line.append(tile, words);
  line.classList.add("has-icon");
}

/* A "game" card's head picture, for what the card leads into: the game's
   end, the Endgame, a new Round (its numeral, 1-10, the app's set), or the
   combat. Null keeps the text mark: a Leader-draft setup card, a Round
   past ten, or no picture on this machine.

   The Round's number is its Conflict reveal's. That event often comes in
   the step of a chance (the discard reshuffle drawn just before it), which
   the card shows as its chance line, so the chance steps' events are read
   too: the card's title then says only "Round started", and the numeral
   says which. */
function neutralLogIcon(group) {
  const events = group.items.filter((item) => item.event).map((item) => item.event);
  const kinds = new Set(events.map((event) => event.kind));
  const revealed = [
    ...events,
    ...group.items.flatMap((item) => (item.chance && item.chance.events) || []),
  ].find((event) => event.kind === "conflict_revealed");
  const round = revealed && revealed.payload ? revealed.payload.round : null;
  const keys = [];
  if (kinds.has("game_finished")) keys.push("log:vp_winner");
  if (kinds.has("endgame_started")) keys.push("victory_point");
  // The same kinds that make neutralTitle say a Round started.
  if (kinds.has("agents_recalled") || kinds.has("conflict_revealed") ||
      kinds.has("cards_drawn")) {
    if (Number.isInteger(round)) keys.push(`log:round_${round}`);
  }
  if (kinds.has("combat_intrigue_started") || kinds.has("conflict_won") ||
      kinds.has("combat_reward_gained")) {
    keys.push("log:conflict");
  }
  for (const key of keys) {
    const tile = logIconTile(key, neutralTitle(group));
    if (tile) return tile;
  }
  return null;
}
