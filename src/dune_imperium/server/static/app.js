"use strict";

/* Table UI over the local play API: the scanned board with the live state
   drawn on top, printed card images, and the rulebook's icons in place of
   effect text. Every game fact rendered here comes from the server's
   PlayerView / summary / catalog payloads; the client keeps no rules
   knowledge of its own (the icon glossary only re-renders server text). */

const state = {
  catalog: null,
  gameId: null,
  summary: null,
  view: null,
  actions: null,
  viewSeat: null,
  busy: false,
  /* Post-game replay review: {meta, seat, cursor} while active. */
  review: null,
  /* Live session log for the active seat: {count, entries} (M11 slice 6). */
  log: null,
};

let noteTimer = 0;

const SEAT_KINDS = [
  ["human", "사람"],
  ["heuristic", "휴리스틱 AI"],
  ["rollout", "롤아웃 탐색 AI"],
  ["random", "랜덤 AI"],
  ["checkpoint", "학습 체크포인트 (아래 경로)"],
];

/* A seat assignment is "human", a registry agent name, or
   "checkpoint:<path>"; the label hides the path. */
function seatKindLabel(kind) {
  const key = kind.startsWith("checkpoint:") ? "checkpoint" : kind;
  const found = SEAT_KINDS.find(([value]) => value === key);
  return found ? found[1] : kind;
}

const PHASE_LABELS = {
  setup: "Setup",
  round_start: "라운드 시작",
  player_turns: "플레이어 턴",
  combat: "Combat",
  makers: "Makers",
  recall_or_endgame: "Recall / Endgame",
  endgame: "Endgame",
  finished: "게임 종료",
};

const FACTION_LABELS = {
  emperor: "Emperor",
  spacing_guild: "Spacing Guild",
  bene_gesserit: "Bene Gesserit",
  fremen: "Fremen",
};

/* One Korean verb per engine action_id; tests/server/test_action_labels.py
   fails when a rules action id is missing here. */
const ACTION_LABELS = {
  acquire_imperium: "카드 획득",
  acquire_imperium_with_solari: "카드 획득 (Solari)",
  acquire_intrigue_imperium: "카드 획득 (Intrigue)",
  acquire_intrigue_reserve: "카드 획득 (Intrigue)",
  acquire_leader_imperium: "카드 획득 (Leader)",
  acquire_leader_reserve: "카드 획득 (Leader)",
  acquire_manipulated_imperium: "Set-aside 카드 획득",
  acquire_reserve: "카드 획득",
  acquire_reserve_with_solari: "카드 획득 (Solari)",
  advance_feyd_track: "Feyd token 전진",
  agent_turn: "Agent 배치",
  choose_agent_card_influence: "Influence 선택",
  choose_combat_reward_influence: "Influence 선택 (Combat 보상)",
  choose_distinct_combat_reward_influence: "Influence 선택 (Combat 보상)",
  choose_intrigue_discard: "Discard할 카드 선택",
  choose_intrigue_faction: "Influence 선택 (Intrigue)",
  choose_leader_signet_influence: "Influence 선택 (Signet)",
  choose_shipping_influence: "Influence 선택 (Shipping)",
  complete_contract: "Contract 완료",
  decline_agent_card_acquisition: "획득 안 함",
  decline_agent_card_discard: "Discard 안 함",
  decline_agent_card_intrigue_payment: "지불 안 함",
  decline_agent_card_payment: "지불 안 함",
  pay_agent_card_spice_for_sandworm: "2 spice 지불 → sandworm 소환",
  pay_agent_card_spice_for_sandworm_and_shield_wall:
    "2 spice 지불 → Shield Wall 제거 + sandworm 소환",
  decline_agent_card_trash: "Trash 안 함",
  decline_combat_reward: "보상 비용 지불 안 함",
  decline_combat_reward_trash: "Trash 안 함",
  decline_control_defense: "방어 배치 안 함",
  decline_corrinth_city_payment: "지불 안 함",
  decline_gather_intelligence: "Gather Intelligence 안 함",
  decline_imperial_privilege_intrigue: "Discard 안 함",
  decline_intrigue_spy: "Spy 배치 안 함",
  decline_intrigue_trash: "Trash 안 함",
  decline_intrigue_trigger: "발동 안 함",
  decline_leader_board_repeat: "반복 안 함",
  decline_leader_card_trash: "Trash 안 함",
  decline_leader_signet_payment: "지불 안 함",
  decline_other_memories: "Other Memories 안 씀",
  decline_reveal_card_trash: "Trash 안 함",
  decline_reveal_influence_exchange: "교환 안 함",
  decline_reveal_sandworm: "Sandworm 소환 안 함",
  decline_reveal_spice_influence: "지불 안 함",
  decline_reveal_spy_recall: "Spy 회수 안 함",
  decline_reveal_troop_retreat: "후퇴 안 함",
  deploy_control_defense: "Control 방어 배치",
  deploy_intrigue_troops: "병력 배치",
  deploy_troops: "병력 배치",
  withdraw_troops: "병력 회수",
  finish_agent_turn: "Agent turn 종료",
  detonate_shield_wall: "Shield Wall 파괴",
  discard_agent_card: "카드 discard",
  discard_intrigue_for_imperial_privilege: "Intrigue discard (Imperial Privilege)",
  discard_opponent_card: "상대 카드 discard",
  exchange_reveal_influence: "Influence 교환",
  finish_reveal: "Reveal 종료",
  flip_battle_card: "Battle card 뒤집기",
  gain_five_reveal_solari: "5 Solari 획득",
  gain_leader_signet_troop: "Troop 획득 (Signet)",
  gain_two_reveal_strength: "검 2 획득",
  gather_intelligence: "Gather Intelligence",
  harvest_maker_spice: "Spice 수확",
  keep_contract_reveal_spice: "Spice 유지",
  keep_shield_wall: "Shield Wall 유지",
  manipulate_imperium_row: "Imperium Row 카드 set-aside",
  match_endgame_wild_icon: "Wild icon 매칭",
  pass_combat_intrigue: "패스",
  pass_endgame_intrigue: "패스",
  pay_agent_card_intrigue_and_spice: "Intrigue+Spice 지불",
  pay_combat_reward: "보상 비용 지불",
  pay_leader_board_repeat: "보드 효과 반복 (1💧)",
  pay_leader_signet_solari: "Solari 지불 (Signet)",
  pay_leader_signet_spice: "Spice 지불 (Signet)",
  pay_reveal_spice_influence: "3 Spice → Influence",
  pay_reveal_water_for_sandworm: "1 Water → Sandworm",
  pick_leader: "Leader 선택",
  place_acquisition_spy: "Spy 배치",
  place_agent_card_spy: "Spy 배치",
  place_combat_reward_spy: "Spy 배치",
  place_contract_spy: "Spy 배치",
  place_intrigue_spy: "Spy 배치",
  place_leader_spy: "Spy 배치",
  place_reveal_spy: "Spy 배치",
  place_trigger_spy: "Spy 배치",
  play_intrigue: "Intrigue 사용",
  recall_agent_for_agent_card: "Agent 회수",
  recall_agent_for_contract: "Agent 회수",
  recall_agent_for_imperial_privilege: "Agent 회수",
  recall_spies_for_combat_reward: "Spy 회수",
  recall_spies_for_reveal: "Spy 회수",
  recall_spy_for_acquisition: "Spy 회수",
  recall_spy_for_agent_card: "Spy 회수",
  recall_spy_for_contract: "Spy 회수",
  recall_spy_for_espionage: "Spy 회수",
  recall_spy_for_intrigue: "Spy 회수",
  recall_spy_for_leader: "Spy 회수",
  recall_spy_for_leader_placement: "Spy 회수",
  recall_spy_for_reveal: "Spy 회수",
  recall_spy_for_reveal_placement: "Spy 회수",
  recall_spy_for_trigger: "Spy 회수",
  resolve_agent_card_effect: "카드 효과 해결",
  resolve_board_effect: "보드 효과 해결",
  resolve_desert_tactics_without_trash: "Trash 없이 해결",
  resolve_espionage_place_spy: "Spy 배치 (Espionage)",
  resolve_espionage_without_spy: "Spy 없이 해결",
  resolve_faction_influence: "Faction Influence 해결",
  resolve_intrigue_rewards: "Intrigue 자동 보상 먼저 해결",
  defer_reveal_choice: "이 Reveal 선택은 나중에",
  resume_reveal_choice: "미룬 Reveal 선택 재개",
  retreat_intrigue_troops: "병력 후퇴",
  retreat_leader_troop: "Troop 후퇴",
  retreat_two_troops_for_reveal: "Troop 2 후퇴 → 검 4",
  reveal_turn: "Reveal 턴 시작",
  summon_maker_sandworms: "Sandworm 소환",
  take_contract: "Contract 획득",
  take_exhausted_contract_solari: "Contract 대신 2 Solari",
  take_high_council_from_reveal: "High Council 획득",
  take_sietch_tabr_supplies: "Sietch Tabr 보급 (Maker Hooks)",
  take_sietch_tabr_water: "Sietch Tabr water",
  take_sietch_tabr_water_and_destroy_wall: "Water + Shield Wall 파괴",
  take_tuek_sietch_spice: "Tuek's Sietch: spice 1",
  take_tuek_sietch_card: "Tuek's Sietch: draw 1",
  place_leader_bonus_spice: "Tuek's Sietch에 bonus spice 놓기 (Signet)",
  take_leader_bonus_spice: "Maker space의 bonus spice 가져오기 (Signet)",
  lose_intrigue_troop: "troop 잃기 (Intrigue)",
  give_intrigue_card: "상대에게 Intrigue 카드 주기",
  trash_intrigue_hand_card: "Intrigue 카드 trash",
  put_back_top_card: "덱 맨 위 카드 되돌리기",
  discard_top_card: "덱 맨 위 카드 discard",
  draw_top_card_for_solari: "Solari 1 지불 → 덱 맨 위 카드 draw",
  place_navigation_card: "Navigation 카드 슬롯에 놓기",
  play_navigation: "Navigation 카드 play",
  trash_agent_card: "카드 trash",
  trash_card_for_desert_tactics: "카드 trash (Desert Tactics)",
  trash_combat_reward_card: "카드 trash (Combat 보상)",
  trash_contract_reveal_for_vp: "이 카드 trash → VP",
  trash_intrigue_card: "Intrigue trash",
  trash_leader_card: "카드 trash (Leader)",
  trash_reveal_card: "카드 trash",
  use_other_memories: "Other Memories 사용",
  acquire_sardaukar_commander: "Sardaukar Commander 획득 (2 Solari)",
  decline_sardaukar_commander: "Sardaukar Commander 거절",
  recruit_sardaukar_commander: "Sardaukar Commander recruit (2 Solari)",
  trash_skill_for_strength: "Skill trash → 검 3",
  deploy_commanders: "Commander 배치",
  withdraw_commanders: "Commander 회수",
  retreat_leader_commander: "Commander 1 retreat (Leader)",
  gain_reveal_influence: "Influence 1 획득 (선택)",
  retreat_opponent_troop: "상대 troop 강제 retreat",
  command_acquire_row_card: "Command: 카드 trash 후 Imperium Row 카드 획득",
  decline_command_acquisition: "Command 획득 거절",
  gain_reveal_persuasion: "Persuasion 1 선택",
  take_reveal_contract: "Contract 선택",
  play_turn_start_card: "턴 시작: 카드 play 후 draw 1, 턴 넘기기",
  complete_contract_by_card: "카드 효과로 contract 완료",
  choose_skill: "Commander Skill 선택",
  acquire_tech: "Tech tile 획득",
  decline_tech: "Tech tile 획득 거절",
  flip_tech: "Tech tile Flip",
  choose_tech_strength: "Forbidden Weapons: 검 3 + Influence 1 잃기",
  choose_tech_trash: "Forbidden Weapons: spice 전부 잃고 trash",
  place_tech_spy: "Panopticon: Spy 배치",
  recruit_reveal_troops: "Reveal: troop recruit",
  draw_reveal_intrigue: "Reveal: Intrigue draw",
  generate_reveal_specimens: "Reveal: specimen",
  advance_reveal_tleilaxu: "Reveal: Tleilaxu",
  advance_reveal_research: "Reveal: Research",
  pay_agent_card_specimen: "specimen 1 지불 → Solari 4",
  pay_agent_card_two_specimens: "specimen 2 지불 → Tleilaxu ×2",
  trash_grafted_card_for_specimen: "graft한 다른 카드 trash → specimen",
  take_agent_card_combat_icon: "Combat 아이콘",
  keep_peeked_intrigue: "Intrigue 카드 keep",
  acquire_reserve_by_card: "Tleilaxu Master: Reserve 카드 획득",
  acquire_imperium_by_card: "Tleilaxu Master: Imperium Row 카드 획득",
  lose_reveal_influence_for_vp: "Influence 1 잃기 → VP 1",
  decline_reveal_influence_loss: "Influence 잃지 않음",
  deploy_reveal_card_troop: "troop 1 배치",
  retreat_reveal_card_troop: "troop 1 후퇴",
  decline_reveal_troop_move: "troop 이동 안 함",
  lose_reveal_troops_for_specimens: "troop 2 잃기 → specimen 2",
  trash_agent_card_self_for_vp: "이 카드 trash → VP 1",
  pay_agent_card_five_solari_for_tleilaxu: "Solari 5 지불 → Tleilaxu",
  trash_grafted_card_for_influence: "graft한 카드 trash → 그 진영 Influence 1",
  lose_agent_card_troop: "troop 1 잃기 → 카드 2 + Research",
  choose_agent_card_reward: "Stitched Horror: 보상 선택",
  decline_reveal_troop_sacrifice: "troop 잃지 않음",
  acquire_tleilaxu: "Tleilaxu 카드 획득",
  acquire_reclaimed_forces: "Reclaimed Forces",
  acquire_intrigue_tleilaxu: "Harvest Cells: Tleilaxu 카드 획득",
  decline_intrigue_tleilaxu: "Harvest Cells: 획득 안 함",
  choose_graft_partner: "Graft: 함께 play할 카드",
  switch_graft_card: "Graft: 다른 카드의 Agent box 해결",
  decline_agent_card_recall: "Agent recall 거절",
  choose_research_space: "Research: advance to",
  choose_research_influence: "Research bonus: Influence",
  trash_for_research_bonus: "Research bonus: trash → card + Intrigue",
  pay_research_bonus: "Research bonus: 7 Solari → Tleilaxu ×2",
  decline_research_bonus: "Research bonus: decline",
  return_specimen: "Return a specimen to supply",
  use_family_atomics: "Family Atomics: redeal the Imperium Row",
  gain_reveal_resources: "Reveal: 자원 획득",
  gain_reveal_faction_influence: "Reveal: Influence 획득",
  decline_skill: "Plasteel Blades 유지 (Skill 거절)",
  choose_secret_project: "Secret Project: 맨 아래 Tech tile 선택",
  gain_leader_signet_spice: "spice 1 (Signet)",
  trash_leader_tech: "Tech tile trash → Intrigue + draw 1 (Signet)",
  move_spy: "Spy 이동",
  place_spy_on_space: "그 공간에 Spy 배치",
  recall_spy_for_placement: "배치를 위해 Spy 회수",
  decline_spy_placement: "Spy 배치 불가",
  lose_unit: "유닛 1 잃기",
  take_trigger_contract: "공개된 contract 선택",
  decline_intrigue_contract_trigger: "Intrigue trigger 거절",
  retreat_leader_troops: "Fedaykin Maneuver: troop 후퇴",
  pay_leader_signet_water: "Water 지불 → troop 2 (Signet)",
  deploy_leader_agent: "Into the Fray: Agent를 Conflict에 배치",
  trash_optional_card: "카드 trash (선택)",
  decline_optional_trash: "trash 거절",
};

/* Korean labels for session-log event kinds (M11 slice 6); falls back to
   prettify(kind) for anything not listed here. */
const EVENT_LABELS = {
  agent_placed: "Agent 배치",
  card_acquired: "카드 획득",
  card_discarded: "카드 discard",
  card_trashed: "카드 trash",
  cards_drawn: "카드 draw",
  intrigue_played: "Intrigue play",
  intrigue_card_drawn: "Intrigue draw",
  intrigue_card_discarded: "Intrigue discard",
  intrigue_card_stolen: "Intrigue 강탈",
  troops_deployed: "병력 배치",
  troops_withdrawn: "병력 회수",
  troops_recruit_short: "병력 recruit 부족 (supply 없음)",
  agent_turn_finished: "Agent turn 종료",
  troops_retreated: "병력 후퇴",
  influence_gained: "Influence 상승",
  influence_lost: "Influence 하락",
  alliance_gained: "Alliance 획득",
  alliance_lost: "Alliance 상실",
  spy_placed: "Spy 배치",
  spy_recalled: "Spy 회수",
  reveal_started: "Reveal 시작",
  reveal_finished: "Reveal 종료",
  conflict_revealed: "Conflict 공개",
  conflict_won: "Conflict 승리",
  combat_reward_gained: "Combat 보상",
  contract_taken: "Contract 획득",
  contract_completed: "Contract 완료",
  victory_points_gained: "VP 획득",
  personal_discard_shuffled: "discard reshuffle",
  game_finished: "게임 종료",
  leader_drafted: "Leader pick",
};

/* Board-layout order for the spaces panel. */
const AGENT_ICON_GROUPS = [
  ["emperor", "Emperor"],
  ["spacing_guild", "Spacing Guild"],
  ["bene_gesserit", "Bene Gesserit"],
  ["fremen", "Fremen"],
  ["landsraad", "Landsraad"],
  ["city", "City"],
  ["spice_trade", "Spice Trade"],
];

function el(id) {
  return document.getElementById(id);
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = `${response.status}: ${JSON.stringify(body.detail)}`;
    } catch {
      /* keep the status code */
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

/* ---------- naming helpers ---------- */

function prettify(id) {
  return String(id)
    .replaceAll(/[_-]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function baseId(instanceId) {
  const value = String(instanceId);
  const starter = value.match(/^player:\d+:starter:(.+):\d+$/);
  if (starter) return starter[1];
  const shared = value.match(/^(?:imperium|reserve|intrigue|tleilaxu):(.+):\d+$/);
  if (shared) return shared[1];
  const contract = value.match(/^contract:(.+)$/);
  if (contract) return contract[1];
  return value;
}

function lookup(id) {
  const c = state.catalog;
  if (!c) return null;
  return (
    c.cards[id] ||
    c.intrigue[id] ||
    c.contracts[id] ||
    c.conflicts[id] ||
    c.leaders[id] ||
    c.spaces[id] ||
    c.objectives[id] ||
    (c.skills && c.skills[id]) ||
    (c.tech && c.tech[id]) ||
    null
  );
}

function nameOf(instanceId) {
  const entry = lookup(baseId(instanceId));
  return entry ? entry.name : prettify(baseId(instanceId));
}

function cardDetail(instanceId) {
  const id = baseId(instanceId);
  const card = state.catalog && state.catalog.cards[id];
  if (card) {
    const bits = [];
    if (card.cost !== null) bits.push(`비용 ${card.cost}`);
    if (card.specimens !== undefined) bits.push(`specimen ${card.specimens}`);
    if (card.graft) bits.push("Graft");
    if (card.persuasion) bits.push(`Persuasion ${card.persuasion}`);
    if (card.swords) bits.push(`sword ${card.swords}`);
    if (card.factions.length) {
      bits.push(card.factions.map((f) => FACTION_LABELS[f] || f).join("/"));
    }
    return bits.join(" · ");
  }
  const intrigue = state.catalog && state.catalog.intrigue[id];
  if (intrigue) return `Intrigue (${intrigue.timings.join("/")})`;
  const tile = state.catalog && state.catalog.tech && state.catalog.tech[id];
  if (tile) return `Tech tile · 비용 ${tile.cost} spice`;
  const skill = state.catalog && state.catalog.skills && state.catalog.skills[id];
  if (skill) return "Sardaukar Commander Skill";
  return "";
}

function chip(instanceId, entryOverride) {
  const span = document.createElement("span");
  span.className = "tag";
  const entry = entryOverride || lookup(baseId(instanceId));
  span.textContent = entry ? entry.name : prettify(baseId(instanceId));
  const detail = cardDetail(instanceId);
  if (detail) span.title = detail;
  if (entry) {
    span.classList.add("clickable");
    span.addEventListener("click", (event) => {
      event.stopPropagation();
      pinPopover(entry, span);
    });
    hoverPopover(span, () => entry);
  }
  return span;
}

/* ---------- detail popover ---------- */

function choamActive() {
  return Boolean(state.summary && state.summary.choam_module);
}

function spaceOptionsFor(entry) {
  return choamActive() && entry.choam_options
    ? entry.choam_options
    : entry.options;
}

function spaceImplementedFor(entry) {
  return choamActive() ? entry.choam_implemented : entry.implemented;
}

function requirementNode(requirement) {
  const label = FACTION_LABELS[requirement.faction] || requirement.faction;
  const line = document.createElement("div");
  line.className = "popover-line requirement";
  line.append(
    "요구: ",
    amount(`influence_${requirement.faction}`, `${label} Influence`, requirement.amount),
    "+"
  );
  return line;
}

function popoverNodes(entry) {
  const nodes = [];
  if (entry.text) for (const text of entry.text) nodes.push(iconLine(text));
  if (entry.condition) nodes.push(iconLine(`조건: ${entry.condition}`));
  if (entry.reward) nodes.push(iconLine(`보상: ${entry.reward}`));
  if (entry.rewards) for (const text of entry.rewards) nodes.push(iconLine(text));
  if (entry.options) {
    if (entry.requirement) nodes.push(requirementNode(entry.requirement));
    for (const option of spaceOptionsFor(entry)) nodes.push(spaceOptionLine(option));
  }
  if (entry.ability_text) {
    nodes.push(iconLine(`${entry.ability}: ${entry.ability_text}`));
  }
  if (entry.signet_text) {
    nodes.push(iconLine(`Signet — ${entry.signet}: ${entry.signet_text}`));
  }
  if (entry.notes) {
    for (const text of entry.notes) nodes.push(iconLine(text, "popover-line muted"));
  }
  return nodes;
}

function openPopover(entry, anchor) {
  const pop = el("card-popover");
  pop.classList.remove("hover");
  pop.textContent = "";

  const title = document.createElement("div");
  title.className = "popover-title";
  title.textContent = entry.name;
  pop.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "meta stats";
  if (entry.cost !== undefined && entry.cost !== null) {
    meta.appendChild(amount("persuasion", "비용 (Persuasion)", entry.cost));
  }
  if (entry.persuasion) meta.appendChild(amount("persuasion", "Persuasion", entry.persuasion));
  if (entry.swords) meta.appendChild(amount("sword", "sword", entry.swords));
  const words = [];
  if (entry.factions && entry.factions.length) {
    words.push(entry.factions.map((f) => FACTION_LABELS[f] || f).join("/"));
  }
  if (entry.timings) words.push(`Intrigue (${entry.timings.join("/")})`);
  if (entry.tier !== undefined) words.push(`Conflict tier ${entry.tier}`);
  if (entry.options && !spaceImplementedFor(entry)) words.push("미구현 · 배치 불가");
  if (words.length) meta.append(words.join(" · "));
  if (meta.childNodes.length) pop.appendChild(meta);

  for (const node of popoverNodes(entry)) pop.appendChild(node);
  if (entry.image) {
    const image = document.createElement("img");
    image.loading = "lazy";
    image.src = entry.image;
    image.alt = entry.name;
    pop.appendChild(image);
  }
  placePopover(pop, anchor, 340);
}

/* The popover is fixed-positioned (the table columns scroll on their own)
   and flips above the anchor when it would run off the bottom. */
function placePopover(pop, anchor, maxWidth) {
  pop.hidden = false;
  const rect = anchor.getBoundingClientRect();
  const width = Math.min(maxWidth, window.innerWidth - 16);
  pop.style.width = `${width}px`;
  const left = Math.min(rect.left, Math.max(8, window.innerWidth - width - 8));
  pop.style.left = `${left}px`;
  pop.style.top = `${rect.bottom + 6}px`;
  const height = pop.offsetHeight;
  if (rect.bottom + 6 + height > window.innerHeight - 8) {
    const above = rect.top - height - 6;
    pop.style.top = `${Math.max(8, above >= 8 ? above : window.innerHeight - height - 8)}px`;
  }
}

function closePopover() {
  const pop = el("card-popover");
  pop.hidden = true;
  pop.classList.remove("hover");
  popoverPinned = false;
  clearTimeout(hoverTimer);
}

/* Hover preview: the popover opens after a short delay while the pointer
   rests on a card and closes when it leaves, unless a click pinned it.
   In hover mode it ignores pointer events so it never blocks the cards
   it may overlap. */
let popoverPinned = false;
let hoverTimer = 0;
const HOVER_DELAY_MS = 120;

function hoverPopover(anchor, entryOf) {
  anchor.addEventListener("mouseenter", () => {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      const entry = entryOf();
      if (!entry || popoverPinned) return;
      openPopover(entry, anchor);
      popoverPinned = false;
      el("card-popover").classList.add("hover");
    }, HOVER_DELAY_MS);
  });
  anchor.addEventListener("mouseleave", () => {
    clearTimeout(hoverTimer);
    if (!popoverPinned) closePopover();
  });
}

/* A click pins the popover open until a click elsewhere or Escape. */
function pinPopover(entry, anchor) {
  openPopover(entry, anchor);
  popoverPinned = true;
}

function chipList(container, ids, emptyText) {
  container.textContent = "";
  if (!ids.length) {
    const note = document.createElement("span");
    note.className = "muted";
    note.textContent = emptyText;
    container.appendChild(note);
    return;
  }
  for (const id of ids) container.appendChild(chip(id));
}

/* Korean labels for the printed icon a keyed resolve_board_effect /
   resolve_agent_card_effect action resolves (OQ-027). A legal action carries
   the server's English effect fragment as `detail` (e.g. "Recruit 1 troop"),
   which iconizes; log lines fall back to these labels. */
const EFFECT_ICON_LABELS = {
  cards: "카드 draw",
  contract: "Contract 획득",
  high_council: "High Council 착석",
  intrigue: "Intrigue draw",
  pledge: "1위 보상에 Influence 선택 추가",
  resources: "자원 획득",
  solari: "Solari 획득",
  spice: "Spice 획득",
  swordmaster: "Swordmaster 획득",
  trash_self: "이 카드 trash",
  troops: "병력 recruit (garrison)",
  water: "Water 획득",
};

function describeAction(action) {
  const verb = ACTION_LABELS[action.action_id] || prettify(action.action_id);
  const parts = [];
  for (const [key, value] of Object.entries(action.arguments)) {
    if (key === "effect" && typeof value === "string") {
      parts.push(action.detail || EFFECT_ICON_LABELS[value] || prettify(value));
    } else if (typeof value === "number" || typeof value === "boolean") {
      parts.push(`${prettify(key)}: ${value}`);
    } else {
      parts.push(nameOf(value));
    }
  }
  return parts.length ? `${verb} — ${parts.join(", ")}` : verb;
}

/* ---------- setup screen ---------- */

function buildSeatSelects() {
  const wrap = el("seat-selects");
  wrap.textContent = "";
  for (let seat = 0; seat < 4; seat += 1) {
    const label = document.createElement("label");
    label.append(`좌석 ${seat} `);
    const select = document.createElement("select");
    select.dataset.seat = String(seat);
    for (const [value, text] of SEAT_KINDS) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    }
    select.value = seat === 0 ? "human" : "heuristic";
    label.appendChild(select);
    wrap.appendChild(label);
  }
}

async function loadGameList() {
  const games = await api("/games");
  el("game-list-wrap").hidden = games.length === 0;
  const list = el("game-list");
  list.textContent = "";
  for (const summary of games) {
    const item = document.createElement("li");
    const label = summary.finished
      ? "종료됨"
      : `라운드 ${summary.round_number}`;
    item.append(
      `seed ${summary.game_seed} · ${summary.seats.map(seatKindLabel).join(", ")} · ${label} `
    );
    const button = document.createElement("button");
    button.textContent = "이어서";
    button.addEventListener("click", () => enterGame(summary));
    item.appendChild(button);
    list.appendChild(item);
  }
}

async function loadSaveList() {
  const saves = await api("/saves");
  el("save-list-wrap").hidden = saves.length === 0;
  const list = el("save-list");
  list.textContent = "";
  for (const entry of saves) {
    const item = document.createElement("li");
    if (entry.error) {
      item.className = "muted";
      item.append(`${entry.save_id} · ${entry.error}`);
      list.appendChild(item);
      continue;
    }
    const title = entry.name || `seed ${entry.game_seed}`;
    const status = entry.finished ? "종료됨" : `라운드 ${entry.round_number}`;
    item.append(
      `${title} · ${entry.seats.join(", ")} · ${status} · ${entry.saved_at} `
    );
    const load = document.createElement("button");
    load.textContent = "불러오기";
    load.addEventListener("click", async () => {
      try {
        el("setup-error").hidden = true;
        const summary = await api(`/saves/${entry.save_id}/load`, {
          method: "POST",
        });
        enterGame(summary);
      } catch (error) {
        el("setup-error").textContent = `불러오기 실패 (${error.message})`;
        el("setup-error").hidden = false;
      }
    });
    const remove = document.createElement("button");
    remove.textContent = "삭제";
    remove.addEventListener("click", async () => {
      await api(`/saves/${entry.save_id}`, { method: "DELETE" }).catch(
        () => {}
      );
      loadSaveList().catch(() => {});
    });
    item.append(load, " ", remove);
    list.appendChild(item);
  }
}

async function createGame(event) {
  event.preventDefault();
  const checkpoint = el("opt-checkpoint").value.trim();
  const seats = [...el("seat-selects").querySelectorAll("select")].map(
    (select) =>
      select.value === "checkpoint" ? `checkpoint:${checkpoint}` : select.value
  );
  const payload = {
    seats,
    choam_module: el("opt-choam").checked,
    leader_draft: el("opt-leader-draft").checked,
    promo_cards: el("opt-promo").checked,
    bloodlines: el("opt-bloodlines").checked,
    tech_module: el("opt-tech").checked,
    immortality: el("opt-immortality").checked,
  };
  const seed = el("opt-seed").value;
  if (seed !== "") payload.game_seed = Number(seed);
  try {
    el("setup-error").hidden = true;
    const summary = await api("/games", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    enterGame(summary);
  } catch (error) {
    el("setup-error").textContent = `게임 생성 실패 (${error.message})`;
    el("setup-error").hidden = false;
  }
}

/* ---------- game screen ---------- */

function humanSeats() {
  return state.summary.seats
    .map((kind, seat) => (kind === "human" ? seat : null))
    .filter((seat) => seat !== null);
}

function activeSeat() {
  return state.review ? state.review.seat : state.viewSeat;
}

function enterGame(summary) {
  state.gameId = summary.game_id;
  state.review = null;
  el("review-bar").hidden = true;
  el("setup-screen").hidden = true;
  el("game-screen").hidden = false;
  document.body.classList.add("in-game");
  el("leave-game").hidden = false;
  el("save-game").hidden = false;
  applySummary(summary);
}

function leaveGame() {
  setSpotlight(null);
  state.gameId = null;
  state.summary = null;
  state.view = null;
  state.actions = null;
  state.review = null;
  el("review-bar").hidden = true;
  el("game-screen").hidden = true;
  document.body.classList.remove("in-game");
  el("leave-game").hidden = true;
  el("save-game").hidden = true;
  el("setup-screen").hidden = false;
  loadGameList().catch(() => {});
  loadSaveList().catch(() => {});
}

function note(text) {
  const target = el("game-note");
  target.textContent = text;
  target.hidden = false;
  window.clearTimeout(noteTimer);
  noteTimer = window.setTimeout(() => {
    target.hidden = true;
  }, 4000);
}

async function saveGame() {
  if (!state.gameId) return;
  const name = window.prompt("저장 이름 (비워도 됩니다)", "");
  if (name === null) return;
  try {
    const metadata = await api(`/games/${state.gameId}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name || null }),
    });
    note(`저장됨: ${metadata.name || metadata.save_id.slice(0, 8)}`);
  } catch (error) {
    note(`저장 실패 (${error.message})`);
  }
}

async function applySummary(summary) {
  state.summary = summary;
  const humans = humanSeats();
  const decision = summary.decision;
  if (typeof summary.confirmation === "number") {
    /* The seat whose turn just ended still holds the table until it
       confirms the hand-over (or takes its steps back). */
    state.viewSeat = summary.confirmation;
  } else if (decision && decision.owner_is_human) {
    state.viewSeat = decision.owner;
  } else if (humans.length) {
    state.viewSeat = humans.includes(state.viewSeat)
      ? state.viewSeat
      : humans[0];
  } else {
    state.viewSeat = null;
  }
  state.view = null;
  state.actions = null;
  state.log = null;
  if (state.viewSeat !== null) {
    state.view = await api(
      `/games/${state.gameId}/seats/${state.viewSeat}/view`
    );
    if (decision && decision.owner === state.viewSeat) {
      state.actions = await api(
        `/games/${state.gameId}/seats/${state.viewSeat}/actions`
      );
    }
    /* The live action log is a game-screen feature only; review mode reads
       its own timeline (meta.steps) instead. */
    if (!state.review) {
      state.log = await api(`/games/${state.gameId}/log?seat=${activeSeat()}`);
    }
  }
  render();
}

async function refresh() {
  const summary = await api(`/games/${state.gameId}`);
  await applySummary(summary);
}

async function applyAction(index) {
  if (state.busy) return;
  state.busy = true;
  render();
  try {
    el("game-error").hidden = true;
    const summary = await api(`/games/${state.gameId}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat: state.viewSeat,
        revision: state.summary.revision,
        undo_count: state.summary.undo_count,
        index,
      }),
    });
    state.busy = false;
    await applySummary(summary);
  } catch (error) {
    state.busy = false;
    if (error.status === 409) {
      await refresh();
      return;
    }
    el("game-error").textContent = `행동 적용 실패 (${error.message})`;
    el("game-error").hidden = false;
    render();
  }
}

/* Hand the turn over after the seat's still-undoable steps: only now do
   the chance stream and the other seats advance. */
async function confirmTurn() {
  if (state.busy) return;
  state.busy = true;
  render();
  try {
    el("game-error").hidden = true;
    const summary = await api(`/games/${state.gameId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat: state.viewSeat,
        revision: state.summary.revision,
        undo_count: state.summary.undo_count,
      }),
    });
    state.busy = false;
    await applySummary(summary);
  } catch (error) {
    state.busy = false;
    if (error.status === 409) {
      await refresh();
      return;
    }
    el("game-error").textContent = `턴 종료 실패 (${error.message})`;
    el("game-error").hidden = false;
    render();
  }
}

/* Take back `steps` of `seat`'s own latest steps (M11 slice 6). */
async function submitUndo(seat, steps) {
  if (state.busy) return;
  state.busy = true;
  render();
  try {
    el("game-error").hidden = true;
    const summary = await api(`/games/${state.gameId}/undo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat,
        revision: state.summary.revision,
        undo_count: state.summary.undo_count,
        steps,
      }),
    });
    state.busy = false;
    await applySummary(summary);
  } catch (error) {
    state.busy = false;
    if (error.status === 409) {
      await refresh();
      return;
    }
    el("game-error").textContent = `되돌리기 실패 (${error.message})`;
    el("game-error").hidden = false;
    render();
  }
}

/* ---------- replay review ---------- */

async function enterReview(seat) {
  const meta = await api(`/games/${state.gameId}/review?seat=${seat}`);
  state.review = { meta, seat, cursor: meta.step_count };
  const select = el("review-seat");
  select.textContent = "";
  /* A finished game is fully disclosed (OQ-010), so any seat — human or
     AI — can be reviewed from its own perspective. */
  state.summary.seats.forEach((kind, reviewSeat) => {
    const option = document.createElement("option");
    option.value = String(reviewSeat);
    option.textContent = `좌석 ${reviewSeat} (${seatKindLabel(kind)})`;
    select.appendChild(option);
  });
  select.value = String(seat);
  const slider = el("review-slider");
  slider.max = String(meta.step_count);
  el("review-bar").hidden = false;
  await reviewGoto(meta.step_count);
}

async function reviewGoto(cursor) {
  const review = state.review;
  if (!review) return;
  cursor = Math.max(0, Math.min(review.meta.step_count, cursor));
  try {
    el("game-error").hidden = true;
    const payload = await api(
      `/games/${state.gameId}/review/${cursor}?seat=${review.seat}`
    );
    review.cursor = cursor;
    state.view = payload.view;
    state.actions = null;
    el("review-slider").value = String(cursor);
    let status =
      `step ${cursor}/${review.meta.step_count}` +
      ` · 라운드 ${payload.round_number}` +
      ` · ${PHASE_LABELS[payload.phase] || payload.phase}` +
      ` · ${describeReviewStep(review.meta.steps[cursor - 1])}`;
    /* Undo markers that rewound the game to this exact step (M11 slice 6). */
    for (const item of review.meta.undo_history || []) {
      if (item.step !== cursor) continue;
      status +=
        ` · ↩ 좌석 ${item.seat}가 여기서 ${item.count}단계 되돌림: ` +
        item.undone.map(describeAction).join(" / ");
    }
    el("review-status").textContent = status;
    render();
  } catch (error) {
    el("game-error").textContent = `검토 상태 조회 실패 (${error.message})`;
    el("game-error").hidden = false;
  }
}

function describeReviewStep(label) {
  if (!label) return "게임 시작 전";
  if (label.type === "chance") {
    const values = label.values || [];
    const shown =
      values.length <= 3
        ? values.map(nameOf).join(", ")
        : `${values.length}장 · ${values.slice(0, 3).map(nameOf).join(", ")} …`;
    return `chance: ${prettify(label.decision_id)}` + (shown ? ` — ${shown}` : "");
  }
  return `좌석 ${label.actor}: ${describeAction(label)}`;
}

function reviewJumpOwn(direction) {
  const review = state.review;
  if (!review) return;
  const steps = review.meta.steps;
  for (
    let cursor = review.cursor + direction;
    cursor >= 1 && cursor <= steps.length;
    cursor += direction
  ) {
    const label = steps[cursor - 1];
    if (label.type === "action" && label.actor === review.seat) {
      reviewGoto(cursor).catch(() => {});
      return;
    }
  }
}

function exitReview() {
  state.review = null;
  el("review-bar").hidden = true;
  refresh().catch(() => {});
}

/* ---------- rendering ---------- */

/* ---------- icons ---------- */

/* Rulebook icons (catalog.icons, served from the machine-local extraction
   of the official Icon Guide) with a text fallback when the set is absent. */
const SEAT_COLORS = ["#2fb3ff", "#ff5a4e", "#7ddc6a", "#f4c542"];

function iconUrl(name) {
  const icons = state.catalog && state.catalog.icons;
  return icons && icons[name] ? icons[name] : null;
}

function icon(name, label) {
  const url = iconUrl(name);
  if (url) {
    const img = document.createElement("img");
    img.className = "icon";
    img.src = url;
    img.alt = label;
    img.title = label;
    return img;
  }
  const span = document.createElement("span");
  span.className = "icon-text";
  span.textContent = label;
  return span;
}

function amount(name, label, count) {
  const wrap = document.createElement("span");
  wrap.className = "amount";
  wrap.title = `${count} ${label}`;
  wrap.append(String(count), icon(name, label));
  return wrap;
}

const FACTION_ICON_KEY = {
  Emperor: "emperor",
  "Spacing Guild": "spacing_guild",
  "Bene Gesserit": "bene_gesserit",
  Fremen: "fremen",
};

/* Glossary that turns the catalog's English effect text into the printed
   iconography: each rule is tried at the current position (sticky), the
   first match wins, and unmatched text is copied through. Only display —
   the text itself stays the server's. */
const ICON_RULES = [
  [/(?:Gain |Pay )?(\d+) (solari|spice|water)\b/y, (m) => amount(m[2], m[2], m[1])],
  [/\b(solari|spice|water)\b/y, (m) => icon(m[1], m[1])],
  [/Draw (\d+) Intrigue cards?/y, (m) => amount("intrigue", "Intrigue card", m[1])],
  [/Draw (\d+) cards?/y, (m) => amount("draw", "Draw", m[1])],
  [/Intrigue cards?/y, () => icon("intrigue", "Intrigue card")],
  [/(?:Recruit |Gain )?(\d+) troops?\b/y, (m) => amount("troop", "troop", m[1])],
  [/\btroops?\b/y, () => icon("troop", "troop")],
  [
    /(?:Gain )?(\d+) (Emperor|Spacing Guild|Bene Gesserit|Fremen) Influence/y,
    (m) => amount(`influence_${FACTION_ICON_KEY[m[2]]}`, `${m[2]} Influence`, m[1]),
  ],
  [
    /(Emperor|Spacing Guild|Bene Gesserit|Fremen) Influence/y,
    (m) => icon(`influence_${FACTION_ICON_KEY[m[1]]}`, `${m[1]} Influence`),
  ],
  [/Lose (\d+) Influence/y, (m) => amount("influence_lose", "Lose Influence", m[1])],
  [/(?:Gain )?(\d+) Influence/y, (m) => amount("influence_any", "Influence", m[1])],
  [/Influence with the visited Faction/y, () => icon("influence_any", "visited Faction Influence")],
  [/(\d+) Persuasion/y, (m) => amount("persuasion", "Persuasion", m[1])],
  [/\bPersuasion\b/y, () => icon("persuasion", "Persuasion")],
  [/(\d+) (?:swords?|strength)\b/y, (m) => amount("sword", "sword", m[1])],
  [/\bswords?\b/y, () => icon("sword", "sword")],
  [/(?:Gain )?(\d+) (?:Victory Points?|VP)\b/y, (m) => amount("victory_point", "Victory Point", m[1])],
  [/\b(?:Victory Points?|VP)\b/y, () => icon("victory_point", "Victory Point")],
  [/\bTrash an Intrigue card\b/y, () => icon("trash_intrigue", "Trash an Intrigue card")],
  [/\b[Tt]rash\b/y, () => icon("trash", "Trash")],
  [/\b[Dd]iscard\b/y, () => icon("discard", "Discard")],
  [/\b(?:a |an )?Sp(?:y|ies)\b/y, (m) => icon("spy", m[0].trim())],
  [/\bAgents?\b/y, (m) => icon("agent", m[0])],
  [/\b[Ss]andworms?\b/y, (m) => icon("sandworm", m[0])],
  [/\bMaker Hooks\b/y, () => icon("maker_hooks", "Maker Hooks")],
  [/\bShield Wall\b/y, () => icon("shield_wall", "Shield Wall")],
  [/\bSignet Ring\b/y, () => icon("signet_ring", "Signet Ring")],
  [/\bContracts?\b/y, (m) => icon("contract", m[0])],
  [/→/y, () => icon("arrow_right", "→")],
];

function iconize(text) {
  const fragment = document.createDocumentFragment();
  let plain = "";
  let index = 0;
  const flush = () => {
    if (plain) fragment.append(plain);
    plain = "";
  };
  while (index < text.length) {
    let matched = false;
    for (const [pattern, build] of ICON_RULES) {
      pattern.lastIndex = index;
      const match = pattern.exec(text);
      if (match && match.index === index) {
        flush();
        fragment.appendChild(build(match));
        index += match[0].length;
        matched = true;
        break;
      }
    }
    if (!matched) {
      plain += text[index];
      index += 1;
    }
  }
  flush();
  return fragment;
}

function iconLine(text, className) {
  const line = document.createElement("div");
  line.className = className || "popover-line";
  line.appendChild(iconize(text));
  return line;
}

function costNode(cost) {
  const wrap = document.createElement("span");
  wrap.className = "cost";
  let any = false;
  for (const resource of ["solari", "spice", "water"]) {
    if (cost[resource]) {
      wrap.appendChild(amount(resource, resource, cost[resource]));
      any = true;
    }
  }
  if (!any) wrap.textContent = "무료";
  return wrap;
}

/* ---------- board spotlight ----------

   The action log's turn cards (renderLog) light what they refer to on the
   table while the pointer rests on them: the spaces and cards named by
   the steps' arguments or events. The stage is rebuilt by every render,
   so the spotlight is re-applied afterwards. */

let spotlightGroup = null;

function setSpotlight(group) {
  spotlightGroup = group;
  applySpotlight();
}

/* Everything a group of steps points at: spaces and cards named by the
   action arguments or by the events (acquired card, placed Agent). */
function logTargets(group) {
  const spaces = [];
  const cards = [];
  const seen = new Set();
  const consider = (value) => {
    if (typeof value !== "string") return;
    /* An event may name a card both by kind (card_id) and by the exact
       copy (instance_id); one image per printed card is enough. */
    const key = state.catalog.spaces[value] ? value : baseId(value);
    if (seen.has(key)) return;
    seen.add(key);
    if (state.catalog.spaces[value]) spaces.push(value);
    else if (lookup(key)) cards.push(value);
  };
  for (const entry of group.entries) {
    if (entry.type !== "action") continue;
    for (const value of Object.values(entry.arguments)) consider(value);
    for (const event of entry.events) {
      if (!event.payload) continue;
      for (const [key, value] of Object.entries(event.payload)) {
        if (key === "card_id" || key === "space_id" || key.endsWith("instance_id")) {
          consider(value);
        }
      }
    }
  }
  return { spaces, cards };
}

function applySpotlight() {
  for (const node of document.querySelectorAll(".spotlight")) {
    node.classList.remove("spotlight");
  }
  if (!spotlightGroup) return;
  const { spaces, cards } = logTargets(spotlightGroup);
  for (const spaceId of spaces) {
    for (const node of document.querySelectorAll(`[data-space="${spaceId}"]`)) {
      node.classList.add("spotlight");
    }
  }
  for (const id of cards) {
    for (const node of document.querySelectorAll(`#game-screen [data-instance="${id}"]`)) {
      if (!node.closest("#action-log")) node.classList.add("spotlight");
    }
  }
}

/* ---------- rendering ---------- */

function render() {
  const summary = state.summary;
  if (!summary) return;
  closePopover();
  el("header-status").textContent =
    `라운드 ${summary.round_number} · ${PHASE_LABELS[summary.phase] || summary.phase}` +
    ` · seed ${summary.game_seed}` +
    (summary.choam_module ? " · CHOAM" : "") +
    (summary.promo_cards ? " · promo" : "") +
    (summary.bloodlines ? " · Bloodlines" : "") +
    (summary.tech_module ? " · Tech" : "") +
    (summary.immortality ? " · Immortality" : "") +
    (summary.leader_draft ? " · draft" : "") +
    (state.review ? " · 리플레이 검토" : "");
  el("decision-banner").hidden = Boolean(state.review);
  renderBanner();
  renderStandings();
  renderBoard();
  renderMarket();
  renderSeats();
  renderLog();
  renderPrivate();
  renderDisclosure();
  applySpotlight();
}

/* Post-game full disclosure (OQ-010 ruling 4): once a game has finished,
   the server adds every hidden zone to the view, both live and in review. */
function renderDisclosure() {
  const panel = el("disclosure");
  panel.textContent = "";
  const view = state.view;
  if (!view || !view.disclosure) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const heading = document.createElement("h2");
  heading.textContent = "종료 후 공개 (모든 비공개 존)";
  panel.appendChild(heading);
  for (const zones of view.disclosure.players) {
    const seat = section(panel, `좌석 ${zones.player}`);
    const line = (label, ids, empty) => {
      const row = document.createElement("div");
      row.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${label} `;
      row.appendChild(strong);
      if (!ids.length) row.append(empty);
      for (const id of ids) row.appendChild(chip(id));
      seat.appendChild(row);
    };
    line(`Hand (${zones.hand.length})`, zones.hand, "비어 있음");
    line(`Deck 순서 (${zones.deck.length})`, zones.deck, "비어 있음");
    line(`Intrigue (${zones.intrigue_cards.length})`, zones.intrigue_cards, "없음");
  }
  const decks = section(panel, "공용 덱 순서");
  const deckLine = (label, ids) => {
    const row = document.createElement("div");
    row.className = "cardline";
    const strong = document.createElement("strong");
    strong.textContent = `${label} (${ids.length}) `;
    row.appendChild(strong);
    for (const id of ids) row.appendChild(chip(id));
    decks.appendChild(row);
  };
  deckLine("Imperium deck", view.disclosure.imperium_deck);
  deckLine("Intrigue deck", view.disclosure.intrigue_deck);
  deckLine("Conflict deck", view.disclosure.conflict_deck);
  if (view.disclosure.contract_bank.length) {
    deckLine("Contract bank", view.disclosure.contract_bank);
  }
}

function renderBanner() {
  const summary = state.summary;
  const info = el("decision-info");
  info.textContent = "";
  const actionsBox = el("actions");
  actionsBox.textContent = "";

  const prompt = document.createElement("div");
  prompt.className = "prompt";
  const meta = document.createElement("div");
  meta.className = "meta";

  if (summary.finished) {
    prompt.textContent = "게임이 끝났습니다.";
    info.append(prompt);
  } else {
    const decision = summary.decision;
    if (!decision) {
      prompt.textContent = "진행 중…";
      info.append(prompt);
    } else if (summary.confirmation === state.viewSeat) {
      /* The viewing seat's turn has ended but its steps can still be taken
         back: nothing advances until it confirms the hand-over. */
      const nextKind = summary.seats[decision.owner];
      prompt.textContent = "행동을 마쳤습니다. 턴을 넘길까요?";
      meta.textContent =
        `되돌릴 수 있는 동안은 턴이 넘어가지 않습니다 · 다음: 좌석 ${decision.owner} (${nextKind})`;
      info.append(prompt, meta);
      const row = document.createElement("div");
      row.className = "confirm-row";
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.textContent = "턴 종료 확정 ▶";
      confirm.disabled = state.busy;
      confirm.addEventListener("click", () => confirmTurn());
      row.appendChild(confirm);
      info.appendChild(row);
    } else {
      const seatKind = summary.seats[decision.owner];
      const who =
        decision.owner === state.viewSeat
          ? `좌석 ${decision.owner} (당신)`
          : `좌석 ${decision.owner} (${seatKind})`;
      prompt.textContent = decision.prompt;
      meta.textContent = `${who} · frame: ${decision.kind}`;
      info.append(prompt, meta);

      if (state.actions && decision.owner === state.viewSeat) {
        for (const action of state.actions.actions) {
          actionsBox.appendChild(actionItem(action));
        }
      }
    }
  }

  /* A human seat may still have takeable-back steps after the game ends
     (its last live step), so the undo row renders in both branches above. */
  appendUndoRow(info);
}

/* Undo controls for the viewing seat (M11 slice 6): a single-step button
   and, when more than one step is available, a take-back-everything button. */
function appendUndoRow(container) {
  if (state.review) return;
  const entry = (state.summary.undo || []).find(
    (item) => item.seat === state.viewSeat
  );
  if (!entry || entry.steps <= 0) return;
  const row = document.createElement("div");
  row.className = "undo-row";

  const one = document.createElement("button");
  one.type = "button";
  one.textContent = "되돌리기 (1단계)";
  one.disabled = state.busy;
  one.addEventListener("click", () => submitUndo(state.viewSeat, 1));
  row.appendChild(one);

  if (entry.steps > 1) {
    const all = document.createElement("button");
    all.type = "button";
    all.textContent = `${entry.steps}단계 모두 되돌리기`;
    all.disabled = state.busy;
    all.addEventListener("click", () => submitUndo(state.viewSeat, entry.steps));
    row.appendChild(all);
  }
  container.appendChild(row);
}

/* Effect preview for one legal action: resolve its referenced space/cards
   against the catalog. space_id resolves against the spaces section
   explicitly (a contract may share its id with a space). */
function actionPreviewEntries(action) {
  const entries = [];
  const args = action.arguments;
  if (typeof args.space_id === "string" && state.catalog.spaces[args.space_id]) {
    entries.push(state.catalog.spaces[args.space_id]);
  }
  for (const [key, value] of Object.entries(args)) {
    if (key === "space_id" || typeof value !== "string") continue;
    const entry = lookup(baseId(value));
    if (entry && !entries.includes(entry)) entries.push(entry);
  }
  return entries;
}

function spaceOptionLine(option) {
  const line = document.createElement("div");
  line.className = "popover-line option-line";
  line.appendChild(costNode(option.cost));
  line.appendChild(icon("arrow_right", "→"));
  line.appendChild(iconize(option.effect));
  return line;
}

function actionPreviewNodes(action, entry) {
  if (entry.options) {
    const options = spaceOptionsFor(entry);
    const index =
      typeof action.arguments.cost_option === "number"
        ? action.arguments.cost_option
        : 0;
    const option = options[index] || options[0];
    const nodes = [];
    if (entry.requirement) nodes.push(requirementNode(entry.requirement));
    nodes.push(spaceOptionLine(option));
    for (const text of entry.notes) nodes.push(iconLine(text, "popover-line muted"));
    return nodes;
  }
  const optionIndex = action.arguments.option;
  if (
    action.action_id === "play_intrigue" &&
    entry.text &&
    typeof optionIndex === "number" &&
    entry.text[optionIndex]
  ) {
    return [iconLine(entry.text[optionIndex])];
  }
  return popoverNodes(entry);
}

/* Argument values that name a card instance or space, for hotspot and hand
   click matching (data-refs) — the same strings describeAction resolves. */
function actionRefs(action) {
  return Object.values(action.arguments).filter((value) => typeof value === "string");
}

function actionItem(action) {
  const wrap = document.createElement("div");
  wrap.className = "action-item";
  wrap.dataset.index = String(action.index);
  wrap.dataset.refs = JSON.stringify(actionRefs(action));
  const button = document.createElement("button");
  button.appendChild(iconize(describeAction(action)));
  button.disabled = state.busy;
  button.addEventListener("click", () => applyAction(action.index));
  if (action.undoable === false) {
    /* The server dry-ran the step: it reveals hidden information or hands
       the game to a chance outcome, so it cannot be taken back afterwards. */
    wrap.classList.add("irreversible");
    const badge = document.createElement("span");
    badge.className = "irreversible-badge";
    badge.textContent = "되돌리기 불가";
    badge.title =
      "이 행동 뒤에는 되돌릴 수 없습니다 (숨겨진 정보가 공개되거나 무작위 결과가 정해집니다)";
    button.appendChild(badge);
  }
  wrap.appendChild(button);

  const entries = actionPreviewEntries(action);
  if (entries.length) {
    const info = document.createElement("button");
    info.type = "button";
    info.className = "action-info";
    info.textContent = "ⓘ";
    info.title = "효과 미리보기";
    const detail = document.createElement("div");
    detail.className = "action-detail";
    detail.hidden = true;
    for (const entry of entries) {
      const head = document.createElement("div");
      head.className = "popover-title";
      head.textContent = entry.name;
      detail.appendChild(head);
      for (const node of actionPreviewNodes(action, entry)) detail.appendChild(node);
      if (entry.image && !entry.options) {
        const image = document.createElement("img");
        image.className = "detail-card";
        image.loading = "lazy";
        image.src = entry.image;
        image.alt = entry.name;
        detail.appendChild(image);
      }
    }
    info.addEventListener("click", (event) => {
      event.stopPropagation();
      detail.hidden = !detail.hidden;
    });
    wrap.append(info, detail);
  }
  return wrap;
}

/* Focus the action list on one card instance or space (table click with
   several options): the matching actions move to the top under a header
   that names the object, the rest stay below dimmed. The list is rebuilt
   by every render, so the focus lasts until the next state change or the
   header's "전체 보기". */
function focusActions(ref, label) {
  clearActionFocus();
  const box = el("actions");
  const items = [...box.querySelectorAll(".action-item")];
  const matches = items.filter((item) =>
    JSON.parse(item.dataset.refs || "[]").includes(ref)
  );
  if (!matches.length) return;
  for (const item of items) {
    const hit = matches.includes(item);
    item.classList.toggle("action-match", hit);
    item.classList.toggle("action-dim", !hit);
  }
  const header = document.createElement("div");
  header.className = "action-focus";
  const text = document.createElement("span");
  text.append(`${label || ref} · 선택지 ${matches.length}개`);
  const clear = document.createElement("button");
  clear.type = "button";
  clear.textContent = "전체 보기";
  clear.addEventListener("click", clearActionFocus);
  header.append(text, clear);
  box.prepend(header);
  let anchor = header;
  for (const item of matches) {
    anchor.after(item);
    anchor = item;
  }
  header.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function clearActionFocus() {
  const box = el("actions");
  const header = box.querySelector(".action-focus");
  if (header) header.remove();
  const items = [...box.querySelectorAll(".action-item")];
  for (const item of items) item.classList.remove("action-match", "action-dim");
  items
    .sort((a, b) => Number(a.dataset.index) - Number(b.dataset.index))
    .forEach((item) => box.appendChild(item));
}

function legalActionsFor(ref) {
  if (!state.actions) return [];
  return state.actions.actions.filter((action) => actionRefs(action).includes(ref));
}

/* Click on a table object: one legal action applies directly, several
   focus the action list, none shows the detail popover. */
function tableClick(ref, entry, anchor) {
  const legal = legalActionsFor(ref);
  if (legal.length === 1) {
    applyAction(legal[0].index);
    return;
  }
  if (legal.length > 1) {
    focusActions(ref, entry ? entry.name : ref);
    note(`${entry ? entry.name : ref}: 선택지가 ${legal.length}개입니다. 오른쪽 행동 목록에서 고르세요.`);
    return;
  }
  if (entry) pinPopover(entry, anchor);
}

function section(parent, title) {
  const heading = document.createElement("h3");
  heading.textContent = title;
  const body = document.createElement("div");
  parent.append(heading, body);
  return body;
}

/* ---------- board ---------- */

function boardOccupancy(view) {
  const occupants = new Map();
  const controllers = new Map();
  const spies = new Map();
  for (const player of view.players) {
    for (const spaceId of player.agent_locations) {
      if (!occupants.has(spaceId)) occupants.set(spaceId, []);
      occupants.get(spaceId).push(player.player);
    }
    for (const spaceId of player.control_space_ids) {
      controllers.set(spaceId, player.player);
    }
    for (const postId of player.spy_post_ids) {
      if (!spies.has(postId)) spies.set(postId, []);
      spies.get(postId).push(player.player);
    }
  }
  return { occupants, controllers, spies };
}

function seatToken(seat, className) {
  const token = document.createElement("span");
  token.className = className;
  token.style.background = SEAT_COLORS[seat];
  token.textContent = String(seat);
  token.title = `좌석 ${seat}`;
  token.dataset.seat = String(seat);
  return token;
}

/* Agent tokens keyed by seat and space, with their screen rectangles, so
   a re-render can animate the ones that were just placed. */
function agentTokenRects(board) {
  const rects = new Map();
  for (const hotspot of board.querySelectorAll(".hotspot")) {
    for (const token of hotspot.querySelectorAll(".agent-token")) {
      rects.set(
        `${token.dataset.seat}:${hotspot.dataset.space}`,
        token.getBoundingClientRect()
      );
    }
  }
  return rects;
}

/* A newly placed Agent token flies in from its seat's mark in the seat
   panel (FLIP: start translated at the origin, then transition to rest).
   Tokens that were already on their space, and the first paint of a
   board, stay still. */
function animatePlacedAgents(board, before) {
  if (before === null) return;
  for (const hotspot of board.querySelectorAll(".hotspot")) {
    for (const token of hotspot.querySelectorAll(".agent-token")) {
      if (before.has(`${token.dataset.seat}:${hotspot.dataset.space}`)) continue;
      const origin = document.querySelector(
        `#seats .seat[data-seat="${token.dataset.seat}"] .seat-mark`
      );
      const target = token.getBoundingClientRect();
      if (!origin || !target.width) {
        token.classList.add("placed");
        continue;
      }
      const from = origin.getBoundingClientRect();
      const dx = from.left + from.width / 2 - (target.left + target.width / 2);
      const dy = from.top + from.height / 2 - (target.top + target.height / 2);
      token.style.transition = "none";
      token.style.transform = `translate(${dx}px, ${dy}px) scale(0.7)`;
      token.getBoundingClientRect();
      token.style.transition = "";
      token.classList.add("flying");
      token.style.transform = "";
      token.addEventListener(
        "transitionend",
        () => token.classList.remove("flying"),
        { once: true }
      );
    }
  }
}

function renderBoard() {
  const board = el("board");
  const before = board.querySelector(".board-stage") ? agentTokenRects(board) : null;
  board.textContent = "";
  const view = state.view;
  if (!view) {
    board.innerHTML =
      '<span class="muted">사람 좌석이 없어 보드를 볼 수 없습니다.</span>';
    return;
  }
  if (state.catalog.board_image) {
    renderBoardStage(board, view);
    animatePlacedAgents(board, before);
  } else {
    renderSpaceList(board, view);
  }
}

/* The scanned board with the live state on top: a hotspot per space
   (catalog.spaces[id].box, percent of the image), Agent tokens, Control
   flags, Maker bonus spice, and Spies on the observation posts. */
function renderBoardStage(board, view) {
  const stage = document.createElement("div");
  stage.className = "board-stage";
  const map = document.createElement("img");
  map.className = "board-map";
  map.src = state.catalog.board_image;
  map.alt = "Dune: Imperium — Uprising board";
  map.draggable = false;
  stage.appendChild(map);

  const { occupants, controllers, spies } = boardOccupancy(view);
  const makerSpice = new Map(view.maker_bonus_spice);

  for (const [spaceId, entry] of Object.entries(state.catalog.spaces)) {
    const [left, top, width, height] = entry.box;
    const hotspot = document.createElement("button");
    hotspot.type = "button";
    hotspot.className = "hotspot";
    hotspot.style.left = `${left}%`;
    hotspot.style.top = `${top}%`;
    hotspot.style.width = `${width}%`;
    hotspot.style.height = `${height}%`;
    hotspot.title = entry.name;
    hotspot.dataset.space = spaceId;
    hotspot.setAttribute("aria-label", entry.name);
    const legal = legalActionsFor(spaceId);
    if (legal.length) hotspot.classList.add("legal");
    if (!spaceImplementedFor(entry)) hotspot.classList.add("unimplemented");
    const seats = occupants.get(spaceId) || [];
    if (seats.length) {
      const tokens = document.createElement("span");
      tokens.className = "agent-tokens";
      for (const seat of seats) tokens.appendChild(seatToken(seat, "agent-token"));
      hotspot.appendChild(tokens);
    }
    if (controllers.has(spaceId)) {
      const flag = seatToken(controllers.get(spaceId), "control-flag");
      flag.title = `Control: 좌석 ${controllers.get(spaceId)}`;
      hotspot.appendChild(flag);
    }
    if (makerSpice.get(spaceId)) {
      const bonus = amount("spice", "bonus spice", makerSpice.get(spaceId));
      bonus.classList.add("maker-bonus");
      hotspot.appendChild(bonus);
    }
    if ((view.sardaukar_commander_space_ids || []).includes(spaceId)) {
      /* A Sardaukar Commander waits on the space: 2 Solari with a visit
         [Bloodlines p. 4]. */
      const mark = document.createElement("span");
      mark.className = "commander-mark";
      mark.textContent = "C";
      mark.title = "Sardaukar Commander (2 Solari)";
      hotspot.appendChild(mark);
    }
    hotspot.addEventListener("click", (event) => {
      event.stopPropagation();
      tableClick(spaceId, entry, hotspot);
    });
    hoverPopover(hotspot, () => entry);
    stage.appendChild(hotspot);
  }

  for (const [postId, [x, y]] of Object.entries(state.catalog.posts)) {
    const seats = spies.get(postId) || [];
    if (!seats.length) continue;
    const post = document.createElement("span");
    post.className = "spy-post";
    post.style.left = `${x}%`;
    post.style.top = `${y}%`;
    post.title = `${prettify(postId)}: 좌석 ${seats.join(", ")}`;
    for (const seat of seats) post.appendChild(seatToken(seat, "spy-token"));
    stage.appendChild(post);
  }

  if (!view.shield_wall_present) {
    const note = document.createElement("span");
    note.className = "board-note";
    note.appendChild(icon("shield_wall", "Shield Wall"));
    note.append(" 파괴됨");
    stage.appendChild(note);
  }
  renderSlotCards(stage, view);
  renderTrackMarkers(stage, view);
  board.appendChild(stage);
}

/* The Conflict card and the face-up CHOAM contracts drawn in their printed
   slots (catalog.tracks.conflict_slot / contract_slots, percent boxes).
   Every card is centred on its slot and drawn before the live markers so
   the unit counts stay on top. The Conflict card fills its portrait frame;
   the landscape contracts are drawn a little larger than their slot
   because the dark band around it is empty. Shaddam's set-aside Sardaukar
   contracts have no printed home and stay in the market strip. */
const CONTRACT_SLOT_SCALE = 1.2;

function renderSlotCards(stage, view) {
  const tracks = state.catalog.tracks;
  if (!tracks || !tracks.conflict_slot) return;

  const [cLeft, cTop, cWidth, cHeight] = tracks.conflict_slot;
  for (const id of view.current_conflict_ids) {
    const card = visualCard(id, { className: "conflict slot-card" });
    card.style.width = `${cWidth}%`;
    placeAt(card, cLeft + cWidth / 2, cTop + cHeight / 2);
    stage.appendChild(card);
  }
  if (view.conflict_deck_size > 0 && tracks.conflict_deck_slot) {
    const [dLeft, dTop, dWidth, dHeight] = tracks.conflict_deck_slot;
    const deck = document.createElement("div");
    deck.className = "slot-deck";
    deck.style.width = `${dWidth}%`;
    deck.style.height = `${dHeight}%`;
    deck.title = `Conflict deck · ${view.conflict_deck_size}장 남음`;
    const count = document.createElement("span");
    count.className = "slot-deck-count";
    count.textContent = String(view.conflict_deck_size);
    deck.append(icon("sword", "Conflict"), count);
    placeAt(deck, dLeft + dWidth / 2, dTop + dHeight / 2);
    stage.appendChild(deck);
  }

  if (!state.summary.choam_module) return;
  view.face_up_contract_ids.forEach((id, index) => {
    const box = tracks.contract_slots[index];
    if (!box) return;
    const [left, top, width, height] = box;
    const card = visualCard(id, { className: "contract slot-card" });
    card.style.width = `${width * CONTRACT_SLOT_SCALE}%`;
    placeAt(card, left + width / 2, top + height / 2);
    stage.appendChild(card);
  });
  const [left, top, width, height] = tracks.contract_slots[tracks.contract_slots.length - 1];
  const bank = document.createElement("span");
  bank.className = "slot-bank";
  bank.title = "face-down contract bank";
  bank.append(icon("contract", "Contract"), ` bank ${view.contract_bank_size}`);
  const overhang = (width * (CONTRACT_SLOT_SCALE - 1)) / 2;
  placeAt(bank, left + width + overhang + 0.8, top + height / 2);
  stage.appendChild(bank);
}

function placeAt(node, x, y) {
  node.style.left = `${x}%`;
  node.style.top = `${y}%`;
  return node;
}

/* Live markers on the printed tracks (catalog.tracks, percent of the
   scan): Influence cubes and Alliance rings on the Faction strips, VP
   tokens on the score column, strength tokens on the combat track, deployed
   units in each seat's Conflict quadrant, and Councilor tokens on the High
   Council seats. */
function renderTrackMarkers(stage, view) {
  const tracks = state.catalog.tracks;
  if (!tracks || !Array.isArray(view.players)) return;
  const factions = Object.keys(FACTION_LABELS);
  let councilSlot = 0;
  view.players.forEach((player, index) => {
    const seat = typeof player.player_id === "number" ? player.player_id : index;
    const color = SEAT_COLORS[seat];

    for (const key of factions) {
      const offset = tracks.influence.offsets[key];
      if (offset === undefined) continue;
      const level = Math.max(0, Math.min(6, player.influence[key] || 0));
      const cube = document.createElement("span");
      cube.className = "track-cube";
      cube.style.background = color;
      cube.title = `좌석 ${seat} · ${FACTION_LABELS[key]} Influence ${player.influence[key]}`;
      placeAt(cube, tracks.influence.seat_x[seat], tracks.influence.levels[level] + offset);
      stage.appendChild(cube);
      if ((player.alliance_faction_ids || []).includes(key)) {
        const ring = document.createElement("span");
        ring.className = "alliance-ring";
        ring.style.borderColor = color;
        ring.title = `좌석 ${seat} · ${FACTION_LABELS[key]} Alliance`;
        placeAt(ring, tracks.influence.alliance[0], tracks.influence.alliance[1] + offset);
        stage.appendChild(ring);
      }
    }

    const vp = player.victory_points || 0;
    const vpToken = seatToken(seat, "track-token vp-token");
    vpToken.title = `좌석 ${seat} · ${vp} VP`;
    const vpY = vp < tracks.victory_points.levels.length
      ? tracks.victory_points.levels[vp]
      : tracks.victory_points.overflow_y;
    placeAt(vpToken, tracks.victory_points.x + (seat - 1.5) * 1.3, vpY);
    stage.appendChild(vpToken);

    const units =
      (player.troops_conflict || 0) +
      (player.sandworms_conflict || 0) +
      (player.commanders_conflict || 0) +
      (player.agent_in_conflict || 0);
    /* Every seat's strength token is always on the track: in the framed
       square left of 1/11 at strength 0 (four tokens in a 2×2), on the
       printed number otherwise, and on its "+20" face beyond 20 (23 is
       the token on 3 showing +20). */
    const strength = player.combat_strength || 0;
    const token = seatToken(seat, "track-token strength-token");
    token.title = `좌석 ${seat} · 전투력 ${strength}`;
    if (strength <= 0) {
      const [zx, zy, zw, zh] = tracks.strength.zero_box;
      placeAt(token, zx + zw * (0.3 + (seat % 2) * 0.4), zy + zh * (0.3 + Math.floor(seat / 2) * 0.4));
    } else {
      const flipped = strength > 20;
      const shown = Math.min(flipped ? strength - 20 : strength, 20);
      const row = shown > 10 ? 1 : 0;
      const cell = shown > 10 ? shown - 10 : shown;
      if (flipped) {
        token.classList.add("flipped");
        const plus = document.createElement("span");
        plus.className = "strength-plus";
        plus.textContent = "+20";
        token.appendChild(plus);
      }
      placeAt(token, tracks.strength.cells[cell] + (seat - 1.5) * 0.9, tracks.strength.rows[row]);
    }
    stage.appendChild(token);

    /* Garrison count in the seat's bracketed circle (always shown), and
       the units deployed this round in the seat's quadrant of the central
       field, with the strength [Main p. 10]. */
    const [gx, gy] = tracks.garrisons[seat] || tracks.garrisons[0];
    const garrison = document.createElement("div");
    garrison.className = "force-chip garrison";
    garrison.style.borderColor = color;
    garrison.title = `좌석 ${seat} · garrison ${player.troops_garrison || 0}`;
    garrison.append(
      seatToken(seat, "seat-mark"),
      amount("troop", "garrison troop", player.troops_garrison || 0)
    );
    if (player.commanders_garrison) {
      const commanders = document.createElement("span");
      commanders.className = "commander-count";
      commanders.title = `Sardaukar Commander ${player.commanders_garrison}`;
      commanders.textContent = `C${player.commanders_garrison}`;
      garrison.appendChild(commanders);
    }
    placeAt(garrison, gx, gy);
    stage.appendChild(garrison);

    if (units > 0) {
      const [qx, qy] = tracks.conflict_quadrants[seat] || tracks.conflict_quadrants[0];
      const deployed = document.createElement("div");
      deployed.className = "force-chip deployed";
      deployed.style.borderColor = color;
      deployed.title = `좌석 ${seat} · Conflict 병력`;
      deployed.appendChild(seatToken(seat, "seat-mark"));
      if (player.troops_conflict) {
        deployed.appendChild(amount("troop", "Conflict troop", player.troops_conflict));
      }
      if (player.sandworms_conflict) {
        deployed.appendChild(amount("sandworm", "sandworm", player.sandworms_conflict));
      }
      if (player.commanders_conflict) {
        const commanders = document.createElement("span");
        commanders.className = "commander-count";
        commanders.title = `Sardaukar Commander ${player.commanders_conflict}`;
        commanders.textContent = `C${player.commanders_conflict}`;
        deployed.appendChild(commanders);
      }
      if (player.agent_in_conflict) {
        deployed.appendChild(amount("agent", "Agent (Into the Fray)", player.agent_in_conflict));
      }
      if (strength) {
        const total = document.createElement("span");
        total.className = "force-strength";
        total.title = `전투력 ${strength}`;
        total.textContent = String(strength);
        deployed.appendChild(total);
      }
      placeAt(deployed, qx, qy);
      stage.appendChild(deployed);
    }

    if (player.high_council && councilSlot < tracks.council_seats.length) {
      const [cx, cy] = tracks.council_seats[councilSlot];
      councilSlot += 1;
      const token = seatToken(seat, "track-token council-token");
      token.title = `좌석 ${seat} · High Council`;
      placeAt(token, cx, cy);
      stage.appendChild(token);
    }
  });
}

/* Text board for a machine without the board scan: the same data as a
   list, grouped by Agent icon, with the live occupancy inline. */
function renderSpaceList(board, view) {
  const catalog = state.catalog;
  const heading = document.createElement("h2");
  heading.textContent = "보드 공간";
  board.appendChild(heading);
  const hint = document.createElement("div");
  hint.className = "muted";
  hint.textContent = "보드 스캔(assets/board/map.jpg)이 없어 목록으로 표시합니다.";
  board.appendChild(hint);
  const { occupants, controllers } = boardOccupancy(view);
  const makerSpice = new Map(view.maker_bonus_spice);

  for (const [iconId, label] of AGENT_ICON_GROUPS) {
    const spaceIds = Object.keys(catalog.spaces).filter(
      (spaceId) => catalog.spaces[spaceId].agent_icon === iconId
    );
    if (!spaceIds.length) continue;
    const body = section(board, label);
    for (const spaceId of spaceIds) {
      body.appendChild(spaceRow(spaceId, occupants, controllers, makerSpice));
    }
  }
}

function spaceRow(spaceId, occupants, controllers, makerSpice) {
  const entry = state.catalog.spaces[spaceId];
  const row = document.createElement("div");
  row.className = "space-row";
  if (legalActionsFor(spaceId).length) row.classList.add("legal");

  const title = document.createElement("div");
  title.appendChild(chip(spaceId, entry));
  const flags = [];
  if (entry.combat) flags.push("⚔ Combat");
  if (entry.maker) flags.push("Maker");
  if (entry.critical) flags.push("Control");
  if (flags.length) {
    const flagLine = document.createElement("div");
    flagLine.className = "muted";
    flagLine.textContent = flags.join(" · ");
    title.appendChild(flagLine);
  }
  if (!spaceImplementedFor(entry)) {
    const badge = document.createElement("span");
    badge.className = "badge-unimpl";
    badge.textContent = "미구현 · 배치 불가";
    title.appendChild(badge);
  }
  row.appendChild(title);

  const detail = document.createElement("div");
  if (entry.requirement) detail.appendChild(requirementNode(entry.requirement));
  for (const option of spaceOptionsFor(entry)) detail.appendChild(spaceOptionLine(option));
  for (const noteText of entry.notes) detail.appendChild(iconLine(noteText, "muted"));
  const status = [];
  const seats = occupants.get(spaceId);
  if (seats && seats.length) {
    status.push(`Agent: ${seats.map((seat) => `좌석 ${seat}`).join(", ")}`);
  }
  if (controllers.has(spaceId)) {
    status.push(`Control: 좌석 ${controllers.get(spaceId)}`);
  }
  if (makerSpice.get(spaceId)) {
    status.push(`bonus spice ${makerSpice.get(spaceId)}`);
  }
  if (status.length) {
    const line = document.createElement("div");
    line.className = "space-status";
    line.textContent = status.join(" · ");
    detail.appendChild(line);
  }
  row.appendChild(detail);
  row.addEventListener("click", (event) => {
    if (event.target.closest(".tag")) return;
    tableClick(spaceId, entry, row);
  });
  hoverPopover(row, () => entry);
  return row;
}

/* ---------- market strip (shared table zones) ---------- */

/* One card as its printed image (or a text card without the cache), lit
   when a legal action references it; a click applies or focuses. */
function visualCard(instanceId, options = {}) {
  const entry = options.entry || lookup(baseId(instanceId));
  const card = document.createElement("button");
  card.type = "button";
  card.className = "vcard" + (options.className ? ` ${options.className}` : "");
  card.dataset.instance = instanceId;
  const legal = legalActionsFor(instanceId);
  if (legal.length) card.classList.add("legal");
  if (entry && entry.image) {
    const image = document.createElement("img");
    image.src = entry.image;
    image.alt = entry.name;
    image.loading = "lazy";
    image.draggable = false;
    card.appendChild(image);
  } else {
    card.classList.add("textcard");
    const name = document.createElement("span");
    name.className = "vcard-name";
    name.textContent = entry ? entry.name : prettify(baseId(instanceId));
    card.appendChild(name);
    const detail = cardDetail(instanceId);
    if (detail) {
      const meta = document.createElement("span");
      meta.className = "vcard-meta";
      meta.textContent = detail;
      card.appendChild(meta);
    }
  }
  if (options.badge) {
    const badge = document.createElement("span");
    badge.className = "vcard-badge";
    badge.textContent = options.badge;
    card.appendChild(badge);
  }
  card.title = entry ? entry.name : nameOf(instanceId);
  card.addEventListener("click", (event) => {
    event.stopPropagation();
    if (options.onClick) options.onClick(entry, card);
    else tableClick(instanceId, entry, card);
  });
  hoverPopover(card, () => entry);
  return card;
}

function cardStrip(parent, title, ids, emptyText, options = {}) {
  const box = document.createElement("div");
  box.className = "strip";
  const heading = document.createElement("h3");
  heading.textContent = title;
  box.appendChild(heading);
  const row = document.createElement("div");
  row.className = "strip-cards";
  if (!ids.length && emptyText) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = emptyText;
    row.appendChild(empty);
  }
  for (const id of ids) {
    row.appendChild(visualCard(id, typeof options === "function" ? options(id) : options));
  }
  box.appendChild(row);
  parent.appendChild(box);
  return row;
}

function renderMarket() {
  const market = el("market");
  market.textContent = "";
  const view = state.view;
  if (!view) return;

  /* The draft pool stays in the view after every seat has picked; the
     chosen Leaders then live on the seat cards, so the strip goes away. */
  const drafting = view.players.some((p) => !p.leader_id);
  if (view.leader_draft_pool.length && drafting) {
    const picked = new Set(view.players.map((p) => p.leader_id).filter(Boolean));
    cardStrip(market, "Leader draft", view.leader_draft_pool, "", (id) => ({
      className: "leader" + (picked.has(id) ? " taken" : ""),
      badge: picked.has(id) ? "선택됨" : null,
    }));
  }

  /* With the board scan the Conflict card and the face-up contracts sit
     in their printed slots on the board (renderSlotCards); the strips
     below only cover the text-board fallback. */
  const onBoard = Boolean(state.catalog.board_image);
  if (!onBoard) {
    cardStrip(market, "Conflict", view.current_conflict_ids, "아직 공개되지 않음", {
      className: "conflict",
    });
  }
  cardStrip(market, "Imperium Row", view.imperium_row, "비어 있음");
  cardStrip(market, "Reserve", view.reserve_stacks.map(([cardId]) => cardId), "", (id) => {
    const stack = view.reserve_stacks.find(([cardId]) => cardId === id);
    return { badge: `×${stack ? stack[1] : 0}` };
  });

  if (state.summary.bloodlines) {
    /* Sardaukar Commanders still waiting on their setup spaces, the bank
       Commander (Sardaukar Standard) and the four face-up Skills
       [Bloodlines pp. 3-4]. */
    const spaces = view.sardaukar_commander_space_ids || [];
    const box = document.createElement("div");
    box.className = "strip";
    const heading = document.createElement("h3");
    heading.textContent =
      `Sardaukar Commander · 보드 ${spaces.length} · bank ${view.sardaukar_commanders_bank || 0}`;
    box.appendChild(heading);
    const row = document.createElement("div");
    row.className = "strip-cards wrap";
    if (!spaces.length) {
      const empty = document.createElement("span");
      empty.className = "muted";
      empty.textContent = "보드에 남은 Commander 없음";
      row.appendChild(empty);
    }
    for (const spaceId of spaces) row.appendChild(chip(spaceId));
    box.appendChild(row);
    market.appendChild(box);
    cardStrip(
      market,
      `Skill (face-up) · stack ${view.skill_stack_size || 0}`,
      (view.skill_face_up || []).map(skillIdOf),
      "없음",
      { className: "skill" }
    );
  }
  if (state.summary.tech_module) {
    /* The Ixian Embassy's three stacks: the face-up top of each with the
       stack size; an emptied stack simply offers nothing [Bloodlines p. 7]. */
    const box = document.createElement("div");
    box.className = "strip";
    const heading = document.createElement("h3");
    heading.textContent = "Ixian Embassy · Tech tiles";
    box.appendChild(heading);
    const row = document.createElement("div");
    row.className = "strip-cards";
    (view.tech_face_up || []).forEach((tileId, index) => {
      const size = (view.tech_stack_sizes || [])[index] || 0;
      if (!tileId) {
        const empty = document.createElement("span");
        empty.className = "stack-empty";
        empty.textContent = `stack ${index + 1} 비었음`;
        row.appendChild(empty);
        return;
      }
      row.appendChild(visualCard(tileId, { className: "tile", badge: `×${size}` }));
    });
    box.appendChild(row);
    market.appendChild(box);
    if ((view.tech_trash || []).length) {
      cardStrip(market, "Tech trash", view.tech_trash, "", { className: "tile taken" });
    }
  }
  if (state.summary.immortality) renderBeneTleilax(market, view);
  if (state.summary.choam_module && !onBoard) {
    cardStrip(
      market,
      `Contracts · bank ${view.contract_bank_size}`,
      view.face_up_contract_ids,
      "비어 있음",
      { className: "contract" }
    );
  }
  if (view.sardaukar_contract_ids.length) {
    cardStrip(market, "Sardaukar contract · Shaddam 전용 set-aside", view.sardaukar_contract_ids, "", {
      className: "contract",
      badge: "set-aside",
    });
  }
  if (view.intrigue_discard.length) {
    cardStrip(market, "Intrigue discard", view.intrigue_discard.slice(-6), "", {
      className: "intrigue",
    });
  }
}

/* ---------- Immortality: the Tleilaxu Row and the Bene Tleilax board ---------- */

const RESEARCH_BONUS_LABELS = {
  none: "",
  specimen: "specimen",
  tleilaxu: "Tleilaxu",
  research: "Research",
  trash_and_specimen: "trash · specimen",
  tleilaxu_and_specimen: "Tleilaxu · specimen",
  solari_one: "Solari 1",
  spice_one: "spice 1",
  spice_two: "spice 2",
  influence_any: "Influence 1",
  trash_for_card_and_intrigue: "trash → card + Intrigue",
  seven_solari_for_two_tleilaxu: "7 Solari → Tleilaxu ×2",
};
const TLEILAXU_TRACK_LABELS = {
  none: "",
  intrigue: "Intrigue",
  victory_point_and_first_spice: "VP · 첫 도달 spice",
  victory_point: "VP",
};

function renderBeneTleilax(market, view) {
  /* The Tleilaxu Row: two deck cards bought with specimens plus the fixed
     Reclaimed Forces card [Immortality pp. 6, 9]. */
  const rowIds = [...(view.tleilaxu_row || []), "reclaimed_forces"];
  cardStrip(
    market,
    `Tleilaxu Row · deck ${view.tleilaxu_deck_size || 0}`,
    rowIds,
    "",
    (id) => {
      const entry = lookup(baseId(id));
      const specimens = entry && entry.specimens !== undefined ? entry.specimens : null;
      return {
        className: id === "reclaimed_forces" ? "reclaimed" : "",
        badge: specimens === null ? null : `specimen ×${specimens}`,
      };
    }
  );

  const layout = state.catalog && state.catalog.bene_tleilax;
  if (!layout) return;
  const box = document.createElement("div");
  box.className = "strip bene-tleilax";
  const heading = document.createElement("h3");
  heading.textContent = "Bene Tleilax board";
  box.appendChild(heading);

  /* Research track: the 22 hexes as a column/row grid; each seat's
     research token sits on its space, the genetic-marker columns are
     tinted. */
  const grid = document.createElement("div");
  grid.className = "research-grid";
  const columns = Math.max(...layout.research_spaces.map((s) => s.column)) + 1;
  const rows = Math.max(...layout.research_spaces.map((s) => s.row)) + 1;
  grid.style.gridTemplateColumns = `repeat(${columns}, minmax(3.6rem, 1fr))`;
  grid.style.gridTemplateRows = `repeat(${rows}, auto)`;
  const tokensBySpace = {};
  for (const player of view.players) {
    if (!player.research_space) continue;
    (tokensBySpace[player.research_space] ||= []).push(player.player);
  }
  for (const space of layout.research_spaces) {
    const cell = document.createElement("div");
    cell.className = "hex";
    if (layout.genetic_marker_columns.includes(space.column)) cell.classList.add("marker");
    if (space.id === layout.research_start) cell.classList.add("start");
    cell.style.gridColumn = String(space.column + 1);
    cell.style.gridRow = String(space.row + 1);
    const label = document.createElement("span");
    label.className = "hex-label";
    label.textContent =
      space.id === layout.research_start ? "시작" : RESEARCH_BONUS_LABELS[space.bonus] || space.bonus;
    cell.appendChild(label);
    const tokens = document.createElement("span");
    tokens.className = "hex-tokens";
    for (const seat of tokensBySpace[space.id] || []) tokens.appendChild(seatToken(seat, "rtoken"));
    cell.appendChild(tokens);
    cell.title = `${space.id} · ${RESEARCH_BONUS_LABELS[space.bonus] || "보너스 없음"}`;
    grid.appendChild(cell);
  }
  box.appendChild(grid);

  /* Tleilaxu track: eight spaces, the bank's spice on the fourth until a
     token first arrives [Immortality p. 4]. */
  const track = document.createElement("div");
  track.className = "tleilaxu-track";
  layout.tleilaxu_track.forEach((bonus, index) => {
    const cell = document.createElement("div");
    cell.className = "track-cell";
    const label = document.createElement("span");
    label.className = "hex-label";
    label.textContent = `${index}${TLEILAXU_TRACK_LABELS[bonus] ? " · " + TLEILAXU_TRACK_LABELS[bonus] : ""}`;
    cell.appendChild(label);
    if (index === layout.tleilaxu_spice_space && view.tleilaxu_track_spice) {
      const spice = document.createElement("span");
      spice.className = "stat";
      spice.append(icon("spice", "spice"), String(view.tleilaxu_track_spice));
      cell.appendChild(spice);
    }
    const tokens = document.createElement("span");
    tokens.className = "hex-tokens";
    for (const player of view.players) {
      if ((player.tleilaxu_space || 0) === index) tokens.appendChild(seatToken(player.player, "rtoken"));
    }
    cell.appendChild(tokens);
    track.appendChild(cell);
  });
  const trackHead = document.createElement("div");
  trackHead.className = "muted";
  trackHead.textContent = "Tleilaxu track";
  box.appendChild(trackHead);
  box.appendChild(track);
  market.appendChild(box);
}

/* ---------- seats ---------- */

function statNode(name, label, value) {
  const stat = document.createElement("span");
  stat.className = "stat";
  stat.title = label;
  stat.append(icon(name, label), String(value));
  return stat;
}

function seatLine(container, label, content) {
  const line = document.createElement("div");
  line.className = "cardline";
  const strong = document.createElement("strong");
  strong.textContent = `${label} `;
  line.appendChild(strong);
  if (typeof content === "string") line.append(content);
  else line.appendChild(content);
  container.appendChild(line);
}

function renderSeats() {
  const wrap = el("seats");
  wrap.textContent = "";
  const view = state.view;
  if (!view) return;
  const summary = state.summary;
  const decisionOwner = state.review
    ? view.decision_owner
    : summary.decision
      ? summary.decision.owner
      : null;

  for (const player of view.players) {
    const seat = player.player;
    const card = document.createElement("article");
    card.className = "seat" + (seat === decisionOwner ? " active" : "");
    card.dataset.seat = String(seat);
    card.style.borderLeftColor = SEAT_COLORS[seat];

    const head = document.createElement("div");
    head.className = "seat-head";
    const faceId = player.leader_face_id || player.leader_id;
    const leaderEntry = faceId ? lookup(faceId) : null;
    if (leaderEntry && leaderEntry.image) {
      const image = document.createElement("img");
      image.className = "leader-thumb";
      image.src = leaderEntry.image;
      image.alt = leaderEntry.name;
      image.addEventListener("click", (event) => {
        event.stopPropagation();
        pinPopover(leaderEntry, image);
      });
      hoverPopover(image, () => leaderEntry);
      head.appendChild(image);
    }
    const who = document.createElement("div");
    who.className = "who";
    const seatMark = seatToken(seat, "seat-mark");
    who.appendChild(seatMark);
    const leaderName = document.createElement("span");
    leaderName.textContent = player.leader_id ? nameOf(faceId) : "Leader 미정";
    if (leaderEntry) {
      leaderName.className = "clickable";
      leaderName.addEventListener("click", (event) => {
        event.stopPropagation();
        pinPopover(leaderEntry, leaderName);
      });
      hoverPopover(leaderName, () => leaderEntry);
    }
    who.appendChild(leaderName);
    if (summary.seats[seat] === "human") {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = seat === activeSeat() ? "YOU" : "사람";
      who.appendChild(badge);
    } else {
      const badge = document.createElement("span");
      badge.className = "badge ai";
      badge.textContent = seatKindLabel(summary.seats[seat]);
      badge.title = summary.seats[seat];
      who.appendChild(badge);
    }
    if (summary.first_player === seat) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "1st";
      badge.title = "First Player";
      who.appendChild(badge);
    }
    head.appendChild(who);
    card.appendChild(head);

    const stats = document.createElement("div");
    stats.className = "stats";
    stats.append(
      statNode("victory_point", "Victory Points", player.victory_points),
      statNode("solari", "solari", player.resources.solari),
      statNode("spice", "spice", player.resources.spice),
      statNode("water", "water", player.resources.water)
    );
    card.appendChild(stats);

    const influence = document.createElement("div");
    influence.className = "stats";
    for (const [key, label] of Object.entries(FACTION_LABELS)) {
      const stat = statNode(`influence_${key}`, `${label} Influence`, player.influence[key]);
      if (player.alliance_faction_ids.includes(key)) {
        stat.classList.add("alliance");
        stat.title += " · Alliance";
      }
      influence.appendChild(stat);
    }
    card.appendChild(influence);

    const forces = document.createElement("div");
    forces.className = "stats";
    /* The sword is the printed strength icon, so it carries the strength
       number; the units in the Conflict get the troop icon under a
       "Conflict" tag so they do not read as the garrison. */
    forces.append(
      statNode("agent", "Agents 대기", player.agents_available),
      statNode("troop", "garrison", player.troops_garrison),
      statNode("sword", "전투력", player.combat_strength || 0),
      statNode("spy", "Spy supply", player.spies_supply)
    );
    const commanders =
      (player.commanders_supply || 0) +
      (player.commanders_garrison || 0) +
      (player.commanders_conflict || 0);
    if (commanders) {
      /* Sardaukar Commanders (Bloodlines): 2-strength "troops" that return
         to the supply after Combat [Bloodlines p. 4]. */
      const mark = document.createElement("span");
      mark.className = "stat commanders";
      mark.title =
        `Sardaukar Commander · garrison ${player.commanders_garrison || 0}` +
        ` · supply ${player.commanders_supply || 0}`;
      mark.textContent =
        `Commander ${player.commanders_garrison || 0}` +
        `/${player.commanders_supply || 0}`;
      forces.appendChild(mark);
    }
    if (
      player.troops_conflict ||
      player.sandworms_conflict ||
      player.commanders_conflict ||
      player.agent_in_conflict
    ) {
      const deployed = document.createElement("span");
      deployed.className = "stat deployed";
      deployed.title = "Conflict에 배치한 유닛";
      deployed.append("Conflict ");
      if (player.troops_conflict) {
        deployed.append(icon("troop", "troop"), String(player.troops_conflict));
      }
      if (player.sandworms_conflict) {
        deployed.append(" ", icon("sandworm", "sandworm"), String(player.sandworms_conflict));
      }
      if (player.commanders_conflict) {
        deployed.append(` Commander ${player.commanders_conflict}`);
      }
      if (player.agent_in_conflict) {
        deployed.append(" ", icon("agent", "Agent"), "(Into the Fray)");
      }
      forces.appendChild(deployed);
    }
    card.appendChild(forces);

    const flags = [];
    if (player.high_council) flags.push("High Council");
    if (player.maker_hooks) flags.push("Maker Hooks");
    if (player.swordmaster_acquired) flags.push("Swordmaster");
    if (player.has_revealed) flags.push("Revealed");
    if (player.control_space_ids.length) {
      flags.push("Control: " + player.control_space_ids.map(nameOf).join("/"));
    }
    /* Bloodlines Leader state: Chani's Tactics token, Piter's Twisted deck,
       Y'rkoon's remaining Navigation slots, Kota's Secret Project tile. */
    if (player.leader_id === "chani") flags.push(`Tactics ${player.tactics_track_space + 1}칸`);
    if (player.twisted_deck_size) flags.push(`Twisted deck ${player.twisted_deck_size}`);
    if (player.navigation_remaining) flags.push(`Navigation ${player.navigation_remaining}장 남음`);
    if (player.has_secret_project) flags.push("Secret Project (face-down Tech tile)");
    if (player.spies_boxed) flags.push(`Spy ${player.spies_boxed}개 box로`);
    /* Immortality: specimens in the Axolotl tanks, the two Bene Tleilax
       tokens, the Family Atomics token, and the grafted-card promises. */
    if (state.summary.immortality) {
      flags.push(`specimen ${player.specimens || 0}`);
      if (player.research_space) flags.push(`Research ${player.research_space}`);
      flags.push(`Tleilaxu ${player.tleilaxu_space || 0}`);
      if (player.family_atomics) flags.push("Family Atomics");
      if ((player.chairdog_return_card_ids || []).length) {
        flags.push(
          "Chairdog: Reveal 시작 때 hand로 " +
            player.chairdog_return_card_ids.map(nameOf).join("/")
        );
      }
      if (player.usurped_row_card_id) {
        flags.push(`Usurp: turn 끝에 ${nameOf(player.usurped_row_card_id)} trash`);
      }
    }
    if (flags.length) seatLine(card, "상태", iconize(flags.join(" · ")));
    if (player.skill_ids && player.skill_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Skills ";
      line.appendChild(strong);
      for (const id of player.skill_ids) line.appendChild(chip(skillIdOf(id)));
      card.appendChild(line);
    }
    if (player.tech_ids && player.tech_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Tech ";
      line.appendChild(strong);
      for (const id of player.tech_ids) {
        const mark = chip(id);
        if ((player.tech_flipped || []).includes(id)) {
          mark.textContent += " (Flip됨)";
          mark.classList.add("muted");
        }
        line.appendChild(mark);
      }
      card.appendChild(line);
    }
    const agents = player.agent_locations.map(nameOf).join(", ");
    if (agents) seatLine(card, "배치", agents);

    const zones = document.createElement("div");
    zones.className = "zones";
    zones.textContent =
      `hand ${player.hand_size} · deck ${player.deck_size}` +
      ` · discard ${player.discard_pile.length} · intrigue ${player.intrigue_card_count}` +
      ` · supply ${player.troops_supply}`;
    if (player.discard_pile.length) {
      zones.classList.add("clickable");
      zones.title = "discard 더미 보기";
      zones.addEventListener("click", (event) => {
        event.stopPropagation();
        openPileList(`좌석 ${seat} discard`, player.discard_pile, zones);
      });
    }
    card.appendChild(zones);

    const battle = [...player.objective_ids, ...player.won_conflict_ids];
    if (battle.length || player.face_down_battle_card_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Battle ";
      line.appendChild(strong);
      for (const id of battle) line.appendChild(chip(id));
      for (const id of player.face_down_battle_card_ids) {
        const mark = chip(id);
        mark.textContent += " (뒤집힘)";
        mark.classList.add("muted");
        line.appendChild(mark);
      }
      card.appendChild(line);
    }
    if (player.active_contract_ids.length || player.completed_contract_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Contracts ";
      line.appendChild(strong);
      for (const id of player.active_contract_ids) line.appendChild(chip(id));
      /* Completed Contracts stay re-checkable (OQ-010): their completion
         was announced before they flipped face down. */
      for (const id of player.completed_contract_ids) {
        const mark = chip(id);
        mark.textContent += " (완료)";
        mark.classList.add("muted");
        line.appendChild(mark);
      }
      card.appendChild(line);
    }
    if (player.in_play.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "In play ";
      line.appendChild(strong);
      for (const id of player.in_play) line.appendChild(chip(id));
      card.appendChild(line);
    }
    /* Hand cards that entered through a public move (Corrinth City, an
       Intrigue "put it in your hand", a Bond return) stay known (OQ-010). */
    if (player.hand_public.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Hand (공개) ";
      line.appendChild(strong);
      for (const id of player.hand_public) line.appendChild(chip(id));
      card.appendChild(line);
    }
    if (view.intrigue_resolving.length && view.decision_owner === player.player) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Intrigue 해결 중 ";
      line.appendChild(strong);
      for (const id of view.intrigue_resolving) line.appendChild(chip(id));
      card.appendChild(line);
    }
    wrap.appendChild(card);
  }
}

/* A Skill tile instance ("skill:<id>:<copy>") to its catalog id. */
function skillIdOf(instanceId) {
  const match = String(instanceId).match(/^skill:(.+):\d+$/);
  return match ? match[1] : String(instanceId);
}

/* A pile listing (discard, Intrigue hand) in the popover. */
function openPileList(title, ids, anchor) {
  const pop = el("card-popover");
  pop.textContent = "";
  const head = document.createElement("div");
  head.className = "popover-title";
  head.textContent = `${title} (${ids.length})`;
  pop.appendChild(head);
  const row = document.createElement("div");
  row.className = "strip-cards wrap";
  for (const id of ids) row.appendChild(visualCard(id, { className: "small" }));
  pop.appendChild(row);
  placePopover(pop, anchor, 420);
}

/* ---------- live action log (M11 slice 6) ---------- */

/* Render one event's payload as compact "key: value" pairs. Values keyed by
   an id-shaped field (card/instance/conflict id, post_id, space_id) resolve
   through the catalog via nameOf; the "player" key renders as a seat label. */
function logEventPayload(payload) {
  const parts = [];
  const shownNames = new Set();
  for (const [key, value] of Object.entries(payload)) {
    if (key === "player") {
      parts.push(`좌석 ${value}`);
      continue;
    }
    const isIdField =
      key.endsWith("card_id") ||
      key.endsWith("instance_id") ||
      key.endsWith("conflict_id") ||
      key === "card_id" ||
      key === "post_id" ||
      key === "space_id";
    /* Combat rewards and the like list every field; zeros say nothing. */
    if (value === 0 || value === "" || value === null || value === false) continue;
    const shown = isIdField ? nameOf(value) : String(value);
    /* card_id and instance_id of one event resolve to the same name. */
    if (isIdField && shownNames.has(shown)) continue;
    if (isIdField) shownNames.add(shown);
    parts.push(`${prettify(key)}: ${shown}`);
  }
  return parts.join(" · ");
}

function logEventLine(event) {
  const line = document.createElement("div");
  line.className = "logevent";
  const label = EVENT_LABELS[event.kind] || prettify(event.kind);
  const payload = logEventPayload(event.payload);
  line.textContent = payload ? `${label} — ${payload}` : label;
  return line;
}

/* Steps that only close a window; kept in the record but muted. */
const QUIET_ACTIONS = new Set(["finish_agent_turn", "finish_reveal", "pass"]);

/* Steps that stand as a card of their own (setup picks). */
const SOLO_ACTIONS = new Set(["pick_leader"]);

/* Events the game produces on its own once a step closes a window —
   setup after the last Leader pick, combat resolution after the last
   Reveal, the round change — rather than the acting seat's doing. From
   the first of these in a step, the rest of that step's events belong to
   the game too (the round-start draws follow the recall, the Victory
   Points follow the combat reward). */
const NEUTRAL_EVENT_KINDS = new Set([
  "leader_draft_pool_revealed",
  "leader_draft_unused",
  "conflict_revealed",
  "combat_intrigue_started",
  "combat_intrigue_finished",
  "combat_reward_gained",
  "conflict_won",
  "battle_icons_matched",
  "battle_card_flipped",
  "combat_cleaned_up",
  "maker_spice_added",
  "agents_recalled",
  "endgame_started",
  "endgame_wild_matched",
  "game_finished",
]);

/* Split one step's events into the actor's own and the game's: a neutral
   kind switches the rest of the step over, and an event aimed at another
   seat (its draw, its loss) is never the actor's own. */
function splitEntryEvents(entry) {
  const own = [];
  const neutral = [];
  let flow = false;
  for (const event of entry.events) {
    if (!flow && NEUTRAL_EVENT_KINDS.has(event.kind)) flow = true;
    const target = event.payload ? event.payload.player : undefined;
    const other = typeof target === "number" && target !== entry.actor;
    (flow || other ? neutral : own).push(event);
  }
  return { own, neutral };
}

/* Group the log into cards. A turn card holds consecutive steps by one
   seat (with only their own events) until a step closes the turn
   (finish_agent_turn, finish_reveal, pass); a Leader pick is a card of
   its own. Everything the game does by itself — the neutral events above
   and every chance step — goes into a "게임 진행" card between them, so
   the round change never reads as the last actor's move. */
function logGroups(entries) {
  const groups = [];
  let open = null;
  let neutral = null;
  const addNeutral = (index, items) => {
    if (!items.length) return;
    if (!neutral) {
      neutral = { kind: "neutral", items: [], firstIndex: index, lastIndex: index };
      groups.push(neutral);
    }
    neutral.items.push(...items);
    neutral.lastIndex = index;
    open = null;
  };
  for (const entry of entries) {
    if (entry.type === "undo") {
      groups.push({ kind: "undo", entry });
      open = null;
      neutral = null;
      continue;
    }
    if (entry.type === "chance") {
      addNeutral(entry.index, [{ chance: entry }]);
      continue;
    }
    const { own, neutral: flow } = splitEntryEvents(entry);
    const step = { ...entry, events: own };
    if (SOLO_ACTIONS.has(entry.action_id)) {
      groups.push({ kind: "turn", actor: entry.actor, entries: [step] });
      open = null;
    } else {
      if (open && open.actor === entry.actor) open.entries.push(step);
      else {
        open = { kind: "turn", actor: entry.actor, entries: [step] };
        groups.push(open);
      }
      if (QUIET_ACTIONS.has(entry.action_id)) open = null;
    }
    neutral = null;
    addNeutral(entry.index, flow.map((event) => ({ event, index: entry.index })));
  }
  return groups;
}

/* What a neutral card is about, from the kinds it carries. */
function neutralTitle(group) {
  const kinds = new Set(group.items.filter((item) => item.event).map((item) => item.event.kind));
  const parts = [];
  if (kinds.has("leader_draft_unused") || kinds.has("leader_draft_pool_revealed")) {
    parts.push("게임 준비");
  }
  if (kinds.has("combat_intrigue_started")) parts.push("Combat Intrigue 창");
  if (kinds.has("conflict_won") || kinds.has("combat_reward_gained")) parts.push("전투 해결");
  if (kinds.has("agents_recalled") || kinds.has("conflict_revealed")) {
    const revealed = group.items.find(
      (item) => item.event && item.event.kind === "conflict_revealed"
    );
    const round = revealed && revealed.event.payload && revealed.event.payload.round;
    parts.push(round ? `라운드 ${round} 시작` : "라운드 시작");
  }
  if (kinds.has("endgame_started")) parts.push("Endgame");
  if (kinds.has("game_finished")) parts.push("게임 종료");
  return parts.length ? parts.join(" · ") : "게임 진행";
}

function neutralCard(group, freshFrom) {
  const card = document.createElement("div");
  card.className = "turn-card neutral";
  if (group.lastIndex >= freshFrom) card.classList.add("fresh");
  const head = document.createElement("div");
  head.className = "turn-head";
  const mark = document.createElement("span");
  mark.className = "neutral-mark";
  mark.textContent = "⚙";
  const who = document.createElement("strong");
  who.textContent = neutralTitle(group);
  head.append(mark, who);
  card.appendChild(head);
  const lines = document.createElement("div");
  lines.className = "turn-lines";
  for (const item of group.items) {
    lines.appendChild(item.chance ? chanceLine(item.chance) : logEventLine(item.event));
  }
  card.appendChild(lines);
  /* Spotlight what the game touched (Maker spice, the new Conflict). */
  const pseudo = {
    entries: [
      {
        type: "action",
        actor: null,
        arguments: {},
        events: group.items.filter((item) => item.event).map((item) => item.event),
      },
    ],
  };
  card.addEventListener("mouseenter", () => setSpotlight(pseudo));
  card.addEventListener("mouseleave", () => {
    if (spotlightGroup === pseudo) setSpotlight(null);
  });
  return card;
}

function chanceLine(entry) {
  const line = document.createElement("div");
  line.className = "turn-line chance";
  let text = `chance: ${prettify(entry.decision_id)}`;
  if (entry.values) {
    const shown =
      entry.values.length <= 3
        ? entry.values.map(nameOf).join(", ")
        : `${entry.values.slice(0, 3).map(nameOf).join(", ")} …`;
    text += ` — ${shown}`;
  }
  line.textContent = text;
  return line;
}

function turnLine(entry) {
  const line = document.createElement("div");
  line.className = "turn-line";
  if (QUIET_ACTIONS.has(entry.action_id)) line.classList.add("quiet");
  if (entry.undone) line.classList.add("undone");
  const head = document.createElement("div");
  head.className = "turn-line-head";
  const index = document.createElement("span");
  index.className = "turn-index";
  index.textContent = `#${entry.index}`;
  head.append(index, iconize(describeAction(entry)));
  if (entry.undone) head.append(" (되돌림)");
  line.appendChild(head);
  for (const event of entry.events) line.appendChild(logEventLine(event));
  return line;
}

function turnCard(group, freshFrom) {
  const card = document.createElement("div");
  card.className = "turn-card";
  const color = SEAT_COLORS[group.actor];
  card.style.borderLeftColor = color;
  if (group.entries.some((entry) => entry.index >= freshFrom)) card.classList.add("fresh");
  if (group.entries.every((entry) => entry.undone)) card.classList.add("undone");

  const player = state.view && state.view.players[group.actor];
  const leaderFace = player && (player.leader_face_id || player.leader_id);
  const head = document.createElement("div");
  head.className = "turn-head";
  head.appendChild(seatToken(group.actor, "seat-mark"));
  const who = document.createElement("strong");
  who.textContent = leaderFace ? nameOf(leaderFace) : `좌석 ${group.actor}`;
  head.appendChild(who);
  const kind = state.summary.seats[group.actor];
  const badge = document.createElement("span");
  badge.className = kind === "human" ? "badge" : "badge ai";
  badge.textContent =
    kind === "human"
      ? group.actor === activeSeat()
        ? "YOU"
        : "사람"
      : seatKindLabel(kind);
  head.appendChild(badge);
  const targets = logTargets(group);
  if (targets.spaces.length) {
    const where = document.createElement("span");
    where.className = "turn-where";
    where.append(icon("agent", "Agent"), " ", targets.spaces.map(nameOf).join(", "));
    head.appendChild(where);
  }
  card.appendChild(head);

  const body = document.createElement("div");
  body.className = "turn-body";
  const lines = document.createElement("div");
  lines.className = "turn-lines";
  for (const entry of group.entries) lines.appendChild(turnLine(entry));
  body.appendChild(lines);
  if (targets.cards.length) {
    const row = document.createElement("div");
    row.className = "turn-cards";
    for (const id of targets.cards.slice(0, 4)) {
      row.appendChild(
        visualCard(id, {
          className: "small",
          onClick: (entry, node) => {
            if (entry) pinPopover(entry, node);
          },
        })
      );
    }
    body.appendChild(row);
  }
  card.appendChild(body);

  card.addEventListener("mouseenter", () => setSpotlight(group));
  card.addEventListener("mouseleave", () => {
    if (spotlightGroup === group) setSpotlight(null);
  });
  return card;
}

function undoRow(entry) {
  const row = document.createElement("div");
  row.className = "turn-card undo-marker";
  row.textContent = `↩ 좌석 ${entry.seat}이(가) ${entry.count}단계 되돌림`;
  return row;
}

/* Entries from this index on arrived since the viewing seat last acted;
   their turn cards are marked and the list scrolls to the first one. */
let logSeen = { gameId: null, count: 0, freshFrom: 0 };

function renderLog() {
  const panel = el("action-log");
  panel.textContent = "";
  const log = state.log;
  if (!log || !log.entries.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  if (logSeen.gameId !== state.gameId) {
    logSeen = { gameId: state.gameId, count: log.count, freshFrom: log.count };
  } else if (log.count !== logSeen.count) {
    logSeen.freshFrom = logSeen.count;
    logSeen.count = log.count;
  }

  const heading = document.createElement("h2");
  heading.textContent = "행동 로그";
  panel.appendChild(heading);
  const list = document.createElement("div");
  list.className = "log-list";
  for (const group of logGroups(log.entries)) {
    if (group.kind === "undo") list.appendChild(undoRow(group.entry));
    else if (group.kind === "neutral") list.appendChild(neutralCard(group, logSeen.freshFrom));
    else list.appendChild(turnCard(group, logSeen.freshFrom));
  }
  panel.appendChild(list);
  const first = list.querySelector(".turn-card.fresh");
  if (first) list.scrollTop = Math.max(0, first.offsetTop - list.offsetTop - 6);
  else list.scrollTop = list.scrollHeight;
}

/* ---------- own hand ---------- */

function renderPrivate() {
  const panel = el("private-zone");
  panel.textContent = "";
  const view = state.view;
  if (!view || !view.private) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const own = view.players[view.player];

  const label = document.createElement("div");
  label.className = "hand-label";
  const title = document.createElement("strong");
  title.textContent = `내 손패 · 좌석 ${activeSeat()}`;
  label.appendChild(title);
  const counts = document.createElement("span");
  counts.className = "hand-counts";
  counts.append(
    statNode("draw", "deck", view.private.deck_size),
    statNode("discard", "discard", own.discard_pile.length),
    statNode("intrigue", "Intrigue", view.private.intrigue_cards.length)
  );
  /* Discard piles are public (OQ-010); the owner's copy lives in the seat's
     public block like everyone else's. */
  counts.addEventListener("click", (event) => {
    event.stopPropagation();
    if (own.discard_pile.length) openPileList("내 discard", own.discard_pile, counts);
  });
  counts.classList.add("clickable");
  label.appendChild(counts);
  panel.appendChild(label);

  const zones = document.createElement("div");
  zones.className = "hand-zones";
  const hand = document.createElement("div");
  hand.className = "strip-cards hand-cards";
  if (!view.private.hand.length) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "손패 없음";
    hand.appendChild(empty);
  }
  for (const cardId of view.private.hand) hand.appendChild(visualCard(cardId));
  zones.appendChild(hand);

  if (view.private.intrigue_cards.length) {
    const intrigue = document.createElement("div");
    intrigue.className = "strip-cards intrigue-cards";
    for (const cardId of view.private.intrigue_cards) {
      intrigue.appendChild(visualCard(cardId, { className: "intrigue" }));
    }
    zones.appendChild(intrigue);
  }
  /* Owner-only peeks: the deck's top card (Controlled, Glowglobes) and
     Kota Odax's face-down Secret Project tile. */
  const peekedIntrigue = view.private.peeked_intrigue_ids || [];
  if (
    view.private.peeked_card_id ||
    view.private.secret_project_tech_id ||
    peekedIntrigue.length
  ) {
    const peeks = document.createElement("div");
    peeks.className = "strip-cards";
    if (view.private.peeked_card_id) {
      peeks.appendChild(
        visualCard(view.private.peeked_card_id, { className: "small", badge: "덱 맨 위" })
      );
    }
    for (const cardId of peekedIntrigue) {
      peeks.appendChild(
        visualCard(cardId, { className: "small", badge: "Intrigue 덱 맨 위" })
      );
    }
    if (view.private.secret_project_tech_id) {
      peeks.appendChild(
        visualCard(view.private.secret_project_tech_id, {
          className: "tile",
          badge: "Secret Project (−1)",
        })
      );
    }
    zones.appendChild(peeks);
  }
  panel.appendChild(zones);
}

function renderStandings() {
  const panel = el("standings");
  const summary = state.summary;
  if (state.review || !summary.finished || !summary.standings) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  panel.textContent = "";
  const heading = document.createElement("h2");
  heading.textContent = "최종 순위";
  panel.appendChild(heading);
  const table = document.createElement("table");
  table.innerHTML =
    "<tr><th>순위</th><th>좌석</th><th>VP</th>" +
    "<th>Spice</th><th>Solari</th><th>Water</th><th>Garrison</th></tr>";
  for (const entry of summary.standings) {
    const row = document.createElement("tr");
    if (entry.rank === 1) row.className = "winner";
    row.innerHTML =
      `<td>${entry.rank}</td>` +
      `<td>좌석 ${entry.player} (${summary.seats[entry.player]})</td>` +
      `<td>${entry.victory_points}</td>` +
      `<td>${entry.spice}</td><td>${entry.solari}</td>` +
      `<td>${entry.water}</td><td>${entry.troops_garrison}</td>`;
    table.appendChild(row);
  }
  panel.appendChild(table);

  const humans = humanSeats();
  if (humans.length) {
    const review = document.createElement("button");
    review.textContent = "리플레이 검토";
    review.addEventListener("click", () => {
      const seat = humans.includes(state.viewSeat)
        ? state.viewSeat
        : humans[0];
      enterReview(seat).catch((error) => {
        el("game-error").textContent = `검토 시작 실패 (${error.message})`;
        el("game-error").hidden = false;
      });
    });
    panel.appendChild(review);
  }
}

async function init() {
  state.catalog = await api("/catalog");
  buildSeatSelects();
  document.addEventListener("click", (event) => {
    const pop = el("card-popover");
    if (!pop.hidden && !pop.contains(event.target)) closePopover();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePopover();
  });
  el("setup-form").addEventListener("submit", createGame);
  el("leave-game").addEventListener("click", leaveGame);
  el("save-game").addEventListener("click", () => {
    saveGame().catch(() => {});
  });
  el("review-exit").addEventListener("click", exitReview);
  el("review-first").addEventListener("click", () => {
    reviewGoto(0).catch(() => {});
  });
  el("review-last").addEventListener("click", () => {
    if (state.review) reviewGoto(state.review.meta.step_count).catch(() => {});
  });
  el("review-prev").addEventListener("click", () => {
    if (state.review) reviewGoto(state.review.cursor - 1).catch(() => {});
  });
  el("review-next").addEventListener("click", () => {
    if (state.review) reviewGoto(state.review.cursor + 1).catch(() => {});
  });
  el("review-prev-own").addEventListener("click", () => reviewJumpOwn(-1));
  el("review-next-own").addEventListener("click", () => reviewJumpOwn(1));
  el("review-slider").addEventListener("change", (event) => {
    if (state.review) reviewGoto(Number(event.target.value)).catch(() => {});
  });
  el("review-seat").addEventListener("change", (event) => {
    if (state.review) {
      enterReview(Number(event.target.value)).catch(() => {});
    }
  });
  await loadGameList();
  await loadSaveList();
}

init().catch((error) => {
  el("setup-error").textContent = `초기화 실패 (${error.message})`;
  el("setup-error").hidden = false;
});
