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
  /* Live session log of the seat on screen: {seat, epoch, count, entries}
     (M11 slice 6). It grows by the tail each snapshot brings; `epoch` is
     the server's name for this log, sent back so the server can tell when
     entries held here went stale (M14 slice 2). */
  log: null,
  /* Who this browser is at the table: {seats, admin, access} (M14). */
  me: null,
  /* The server this page came from: {access, admin, public_url} (M14). */
  server: null,
  /* The staged Agent turn: what the player has picked so far, {cardId?,
     partnerId?, spaceId?} (partnerId: the second card of a graft). It lives
     only in this page; nothing reaches the server until the pick names one
     legal action (see pickStep). */
  pick: null,
  /* The count chosen on each count stepper, by action id (countRow). */
  counts: {},
};

let noteTimer = 0;

const SEAT_KINDS = [
  ["human", "사람"],
  ["heuristic", "휴리스틱 AI"],
  ["rollout", "롤아웃 탐색 AI"],
  ["rollout_strong", "강한 롤아웃 탐색 AI (느림)"],
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
  decline_imperial_privilege_intrigue: "Intrigue trash 안 함",
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
  use_intrigue_effect: "Intrigue 효과 줄 사용",
  finish_intrigue_effects: "Intrigue 카드 마무리 (남은 줄 사용 안 함)",
  play_conflict_end_intrigue: "Conflict 종료 trigger Intrigue play (Harvest Cells)",
  decline_conflict_end_intrigue: "Conflict 종료 trigger Intrigue 사용 안 함",
  recall_agent_for_agent_card: "Agent 회수",
  recall_agent_for_contract: "Agent 회수",
  recall_agent_for_imperial_privilege: "Agent 회수",
  recall_conflict_agent_for_imperial_privilege: "Conflict의 Agent 회수 (Into the Fray)",
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
  skip_intrigue_acquisition: "획득할 카드 없음 (건너뛰기)",
  trash_intrigue_for_agent_card: "Intrigue trash (카드 비용)",
  trash_intrigue_for_contract: "Intrigue 카드 trash (Immediate Contract)",
  trash_intrigue_for_imperial_privilege: "Intrigue trash → Intrigue 1장 (Imperial Privilege)",
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
  lose_reveal_troops_for_specimens: "troop 2 잃기 (존 선택) → specimen 2",
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
  trash_intrigue_for_research_bonus: "Research bonus: Intrigue trash → card + Intrigue",
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

/* What Immortality lays over a space (catalog.spaces[id].immortality): only
   the Research Station has an overlay tile, with its own effect, picture
   and the box where the tile covers the print. */
function spaceOverlayFor(entry) {
  return state.summary && state.summary.immortality && entry.immortality
    ? entry.immortality
    : null;
}

function spaceOptionsFor(entry) {
  const overlay = spaceOverlayFor(entry);
  if (overlay) return overlay.options;
  return choamActive() && entry.choam_options
    ? entry.choam_options
    : entry.options;
}

/* The picture that goes with an entry: a space under an overlay shows the
   overlay tile's picture when the owner's assets have it. */
function entryImage(entry) {
  const overlay = spaceOverlayFor(entry);
  return (overlay && overlay.image) || entry.image;
}

/* A Leader's own tile (Tuek's Sietch) is on the table only while that Leader
   plays [Bloodlines p. 12]. */
function spaceInPlay(entry, view) {
  return (
    !entry.required_leader_id ||
    (view.players || []).some((player) => player.leader_id === entry.required_leader_id)
  );
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
  if (entryImage(entry)) {
    const image = document.createElement("img");
    image.loading = "lazy";
    image.src = entryImage(entry);
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
      `${seedLabel(summary)}${summary.seats.map(seatKindLabel).join(", ")} · ${label} `
    );
    const button = document.createElement("button");
    button.textContent = "이어서";
    button.addEventListener("click", () => openGame(summary.game_id));
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
    if (entry.autosave) item.appendChild(autosaveBadge());
    item.append(`${saveTitle(entry)} · ${entry.seats.join(", ")} · ${savedWhen(entry)} `);
    const load = document.createElement("button");
    load.textContent = "불러오기";
    load.addEventListener("click", async () => {
      try {
        el("setup-error").hidden = true;
        const summary = await api(`/saves/${entry.save_id}/load`, {
          method: "POST",
        });
        await openGame(summary.game_id);
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

function saveTitle(entry) {
  const status = entry.finished ? "종료됨" : `라운드 ${entry.round_number}`;
  /* An autosave's name only repeats what its badge and the round say. */
  if (entry.autosave) return status;
  const title =
    entry.name ||
    (entry.game_seed === null ? "이름 없는 저장" : `seed ${entry.game_seed}`);
  return `${title} · ${status}`;
}

/* Saves are stamped in UTC; a host looking for "the one from ten minutes
   ago" after a crash reads local time. */
function savedWhen(entry) {
  const when = new Date(entry.saved_at);
  return Number.isNaN(when.getTime()) ? String(entry.saved_at) : when.toLocaleString();
}

function autosaveBadge() {
  const badge = document.createElement("span");
  badge.className = "badge autosave";
  badge.textContent = "자동 저장";
  return badge;
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
    await openGame(summary.game_id);
  } catch (error) {
    el("setup-error").textContent = `게임 생성 실패 (${error.message})`;
    el("setup-error").hidden = false;
  }
}

/* ---------- screens and entry (M14 slice 4) ---------- */

const BASE_TITLE = document.title;
const SCREENS = ["setup-screen", "landing-screen", "lobby-screen", "game-screen"];

function isRemote() {
  return Boolean(state.server && state.server.access === "remote");
}

/* On an open server every browser is the host. */
function isAdmin() {
  return Boolean(state.server && state.server.admin);
}

function showScreen(name) {
  for (const id of SCREENS) el(id).hidden = id !== name;
  const atTable = name === "game-screen";
  document.body.classList.toggle("in-game", atTable);
  el("leave-game").hidden = !(atTable || name === "lobby-screen");
  el("save-game").hidden = !(atTable && isAdmin());
  el("open-lobby").hidden = !(atTable && isRemote());
}

function storageGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function storageSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    /* a private window: the convenience is simply not remembered */
  }
}

function storageRemove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    /* nothing was remembered in the first place */
  }
}

function hashParams() {
  return new URLSearchParams(window.location.hash.replace(/^#/, ""));
}

/* A game ID goes into request paths, and both the hash and localStorage are
   whatever somebody put there. */
function roomId(value) {
  return value && /^[\w-]{1,64}$/.test(value) ? value : null;
}

function roomFromHash() {
  return roomId(hashParams().get("game"));
}

/* The room link is `#game=<id>`: a reload, or the link pasted to a friend,
   comes back to this game. The ID is the ticket into the room, not a seat;
   seats live in HttpOnly cookies and never reach the address bar. */
function setRoomHash(gameId) {
  const target = gameId
    ? `#game=${gameId}`
    : window.location.pathname + window.location.search;
  window.history.replaceState(null, "", target);
}

function seedLabel(summary) {
  return summary.game_seed === null ? "" : `seed ${summary.game_seed} · `;
}

function humanSeatsOf(summary) {
  return summary.seats
    .map((kind, seat) => (kind === "human" ? seat : null))
    .filter((seat) => seat !== null);
}

function humanSeats() {
  return humanSeatsOf(state.summary);
}

/* The seats this browser plays: every human seat on an open server, the
   seats it claimed on a remote one. */
function mySeats() {
  return state.me ? state.me.seats : [];
}

function activeSeat() {
  return state.review ? state.review.seat : state.viewSeat;
}

function playerInfo(seat) {
  const players = state.summary && state.summary.players;
  return (players && players[seat]) || { seat, kind: "human", name: null };
}

/* What to call a seat's player. Names come from other people: they are only
   ever written through textContent, never as markup. */
function playerName(seat) {
  const info = playerInfo(seat);
  if (info.kind !== "human") return seatKindLabel(info.kind);
  if (info.name) return info.name;
  return isRemote() && !info.claimed ? "빈 좌석" : "사람";
}

function playerLabel(seat) {
  return `좌석 ${seat} (${playerName(seat)})`;
}

function presenceDot(info) {
  const dot = document.createElement("span");
  dot.className = "presence " + (info.online ? "on" : "off");
  dot.title = info.online ? "접속 중" : "접속 끊김";
  return dot;
}

function resetGameState() {
  state.gameId = null;
  state.summary = null;
  state.view = null;
  state.actions = null;
  state.log = null;
  state.me = null;
  state.viewSeat = null;
  stopPlayback();
  state.review = null;
  state.pick = null;
  state.counts = {};
  myTurnBefore = null;
  document.title = BASE_TITLE;
  el("review-bar").hidden = true;
}

/* The setup screen for the host (everyone, on an open server); a plain
   landing page for a visitor who came without a room link. */
async function showHome(message) {
  setRoomHash(null);
  const target = isAdmin() ? "setup" : "landing";
  showScreen(`${target}-screen`);
  const error = el(`${target}-error`);
  error.textContent = message || "";
  error.hidden = !message;
  /* A guest has no game list; the last room this browser was in is the way
     back after closing the tab or leaving (a convenience only: what lets
     it sit down again is the seat cookie). */
  el("landing-resume").hidden = isAdmin() || !roomId(storageGet("dune.lastGame"));
  if (isAdmin()) {
    await Promise.all([
      loadGameList().catch(() => {}),
      loadSaveList().catch(() => {}),
    ]);
  }
}

/* Entering a game starts with who this browser is at that table: the seats
   it holds decide between the table and the seat picker. */
let openTicket = 0;

async function openGame(gameId) {
  openTicket += 1;
  const ticket = openTicket;
  closeDoorbell();
  setSpotlight(null);
  resetGameState();
  let entry;
  try {
    entry = await api(`/games/${gameId}/snapshot`);
  } catch (error) {
    if (ticket !== openTicket) return;
    if (error.status === 404 && storageGet("dune.lastGame") === gameId) {
      storageRemove("dune.lastGame");
    }
    await showHome(
      error.status === 404
        ? "그 게임은 이 서버에 없습니다 (서버가 다시 시작됐을 수 있습니다)."
        : `게임 조회 실패 (${error.message})`
    );
    return;
  }
  /* A later openGame (a second link pasted meanwhile) owns the page now. */
  if (ticket !== openTicket) return;
  state.gameId = gameId;
  state.summary = entry.summary;
  state.me = entry.you;
  setRoomHash(gameId);
  storageSet("dune.lastGame", gameId);
  openDoorbell();
  if (mySeats().length || !humanSeatsOf(entry.summary).length) {
    enterTable(entry.summary);
  } else {
    showLobby();
  }
}

function enterTable(summary, seat) {
  stopPlayback();
  state.review = null;
  el("review-bar").hidden = true;
  el("game-error").hidden = true;
  showScreen("game-screen");
  const options = seat === undefined ? undefined : { seat };
  const gameId = state.gameId;
  refresh(summary, options)
    .then(() => {
      if (state.gameId !== gameId || state.review) return;
      if (spectatorOnly() && state.summary.finished) watchGame();
    })
    .catch(showRefreshError);
}

function showRefreshError(error) {
  el("game-error").textContent = `게임 상태 조회 실패 (${error.message})`;
  el("game-error").hidden = false;
}

function leaveGame(message) {
  openTicket += 1;
  closeDoorbell();
  setSpotlight(null);
  resetGameState();
  showHome(message).catch(() => {});
}

/* ---------- seat picker (remote servers) ---------- */

function showLobby(message) {
  showScreen("lobby-screen");
  const note = el("lobby-note");
  note.textContent = message || "";
  note.hidden = !message;
  el("lobby-error").hidden = true;
  const name = el("lobby-name");
  if (!name.value) name.value = storageGet("dune.playerName") || "";
  renderLobby();
}

function lobbyError(text) {
  el("lobby-error").textContent = text;
  el("lobby-error").hidden = false;
}

function renderLobby() {
  const summary = state.summary;
  if (!summary) return;
  const mine = mySeats();
  el("lobby-status").textContent =
    `라운드 ${summary.round_number} · ${PHASE_LABELS[summary.phase] || summary.phase}` +
    (summary.finished ? " · 종료됨" : "");
  const list = el("lobby-seats");
  list.textContent = "";
  let free = 0;
  for (const info of summary.players) {
    const item = document.createElement("li");
    item.className = "lobby-seat";
    item.dataset.seat = String(info.seat);
    item.appendChild(seatToken(info.seat, "seat-mark"));
    const label = document.createElement("span");
    label.className = "lobby-seat-label";
    label.textContent = playerName(info.seat);
    item.appendChild(label);
    if (info.kind === "human") {
      if (info.claimed) item.appendChild(presenceDot(info));
      if (mine.includes(info.seat)) {
        const badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = "내 좌석";
        item.appendChild(badge);
        item.appendChild(lobbyButton("자리 비우기", () => releaseSeat(info.seat)));
      } else if (!info.claimed) {
        free += 1;
        item.appendChild(lobbyButton("앉기", () => claimSeat(info.seat)));
      } else if (isAdmin()) {
        item.appendChild(lobbyButton("좌석 비우기", () => releaseSeat(info.seat)));
      }
    } else {
      const badge = document.createElement("span");
      badge.className = "badge ai";
      badge.textContent = "AI";
      item.appendChild(badge);
    }
    list.appendChild(item);
  }
  if (!mine.length && !free) {
    lobbyError("빈 좌석이 없습니다. 호스트에게 좌석을 비워 달라고 하세요.");
  }
  el("lobby-enter").hidden = !mine.length;
  /* The seat picker above already lists the seats, with the host's release
     buttons. */
  renderHostBlock(el("lobby-host"), { seats: false });
}

function lobbyButton(text, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = text;
  button.addEventListener("click", () => {
    el("lobby-error").hidden = true;
    onClick().catch((error) => lobbyError(`요청 실패 (${error.message})`));
  });
  return button;
}

async function claimSeat(seat) {
  if (state.busy) return;
  const name = el("lobby-name").value.trim();
  if (!name) {
    lobbyError("이름을 먼저 적어 주세요.");
    el("lobby-name").focus();
    return;
  }
  let summary;
  /* Leaving (or a deleted game) while the claim is on its way must not be
     answered by putting the table back on screen. */
  const ticket = openTicket;
  /* Busy as for any other POST of this page: its own doorbell is not
     answered with a request, the refresh that follows covers it. */
  state.busy = true;
  try {
    summary = await api(`/games/${state.gameId}/seats/${seat}/claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  } catch (error) {
    state.busy = false;
    if (ticket !== openTicket) return;
    await refresh();
    lobbyError(
      error.status === 409
        ? "방금 다른 사람이 그 좌석에 앉았습니다."
        : `앉기 실패 (${error.message})`
    );
    return;
  }
  state.busy = false;
  storageSet("dune.playerName", name);
  if (ticket !== openTicket) return;
  /* A stream registers presence with the cookies it was opened with, so the
     seat only shows as online once the stream is opened again. */
  openDoorbell();
  /* state.me does not know the new seat yet; only a snapshot may say so
     (see refresh), and this one asks for the seat by name. */
  enterTable(summary, seat);
}

async function releaseSeat(seat) {
  if (state.busy) return;
  let summary;
  state.busy = true;
  try {
    summary = await api(`/games/${state.gameId}/seats/${seat}/release`, {
      method: "POST",
    });
  } finally {
    state.busy = false;
  }
  /* Giving up the seat on screen: ask without a seat, not for one the
     server has just stopped answering for. Losing the last seat lands in
     the seat picker (adoptSnapshot). */
  const options = seat === state.viewSeat ? { seat: null } : undefined;
  await refresh(summary, options);
}

/* This browser held seats and now holds none: it gave its seat up, or the
   host released it. The stream stays as it is; a released token stopped
   counting as present the moment it was released. */
function seatLost() {
  state.view = null;
  state.actions = null;
  state.log = null;
  state.viewSeat = null;
  showLobby("좌석에서 내려왔습니다. 다시 앉으려면 좌석을 고르세요.");
}

/* ---------- host block: the room link and the seats ---------- */

function roomLink() {
  const base =
    state.server.public_url ||
    storageGet("dune.publicUrl") ||
    window.location.origin;
  return `${base.replace(/\/+$/, "")}/#game=${state.gameId}`;
}

function copyText(input) {
  input.select();
  /* The clipboard API needs a secure context; a Tailscale address served
     over plain HTTP is not one, so the selection stays as the fallback. */
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(input.value).catch(() => {});
  } else {
    try {
      document.execCommand("copy");
    } catch (error) {
      /* the link stays selected for a manual copy */
    }
  }
}

function renderHostBlock(container, options) {
  const show = isRemote() && isAdmin() && Boolean(state.gameId);
  container.hidden = !show;
  if (!show) {
    container.textContent = "";
    return;
  }
  /* Never rebuild under the host's cursor while an address is being typed.
     Only that: a button keeps the focus after its click, and the click is
     exactly what the block has to show the result of. */
  const active = document.activeElement;
  if (
    active &&
    active.tagName === "INPUT" &&
    !active.readOnly &&
    container.contains(active)
  ) {
    return;
  }
  container.textContent = "";

  const heading = document.createElement("h3");
  heading.textContent = "방 링크 — 친구들에게 이 주소 하나를 보내세요";
  container.appendChild(heading);
  const row = document.createElement("div");
  row.className = "room-link";
  const link = document.createElement("input");
  link.type = "text";
  link.readOnly = true;
  link.className = "room-link-value";
  link.value = roomLink();
  link.addEventListener("focus", () => link.select());
  const copy = document.createElement("button");
  copy.type = "button";
  copy.textContent = "복사";
  copy.addEventListener("click", () => copyText(link));
  row.append(link, copy);
  container.appendChild(row);

  if (!state.server.public_url) {
    const label = document.createElement("label");
    label.className = "room-base";
    label.append("친구들이 접속하는 서버 주소 (예: http://100.x.y.z:8000) ");
    const base = document.createElement("input");
    base.type = "text";
    base.value = storageGet("dune.publicUrl") || window.location.origin;
    base.addEventListener("change", () => {
      storageSet("dune.publicUrl", base.value.trim());
      link.value = roomLink();
    });
    label.appendChild(base);
    container.appendChild(label);
  }

  if (options && options.seats === false) return;
  const list = document.createElement("ul");
  list.className = "host-seats";
  for (const info of state.summary.players) {
    if (info.kind !== "human") continue;
    const item = document.createElement("li");
    item.appendChild(seatToken(info.seat, "seat-mark"));
    const label = document.createElement("span");
    label.textContent = playerName(info.seat);
    item.appendChild(label);
    if (info.claimed) {
      item.appendChild(presenceDot(info));
      const release = document.createElement("button");
      release.type = "button";
      release.textContent = "좌석 비우기";
      release.addEventListener("click", () => {
        releaseSeat(info.seat).catch((error) =>
          note(`좌석 비우기 실패 (${error.message})`)
        );
      });
      item.appendChild(release);
    }
    list.appendChild(item);
  }
  container.appendChild(list);
  container.appendChild(hostSavesBlock());
}

/* What is on the host's disk for this game. The listing reads every save
   file, so it is asked for when the host looks (the panel opens, a save
   was made, the refresh button), never on a timer or a doorbell. */
let hostSaves = { gameId: null, entries: null, error: null };

async function loadHostSaves() {
  const gameId = state.gameId;
  if (!gameId || !(isRemote() && isAdmin())) return;
  try {
    const saves = await api("/saves");
    hostSaves = {
      gameId,
      entries: saves.filter((entry) => entry.source_game_id === gameId),
      error: null,
    };
  } catch (error) {
    hostSaves = { gameId, entries: null, error: error.message };
  }
  if (state.gameId === gameId && !el("game-screen").hidden) {
    renderHostBlock(el("host-panel-body"));
  }
}

function hostSavesBlock() {
  const block = document.createElement("div");
  block.className = "host-saves";
  const heading = document.createElement("h3");
  heading.textContent = state.server.autosave
    ? "저장 — 턴이 넘어갈 때마다 자동 저장됩니다"
    : "저장 — 자동 저장이 꺼져 있습니다 (--no-autosave)";
  block.appendChild(heading);
  const hint = document.createElement("p");
  hint.className = "muted";
  hint.textContent =
    "서버가 죽으면: 서버를 다시 띄우고 관리자 링크로 들어가 자동 저장을 불러온 뒤, 새 방 링크를 보내세요.";
  block.appendChild(hint);
  const known = hostSaves.gameId === state.gameId ? hostSaves : null;
  const list = document.createElement("ul");
  list.className = "host-save-list";
  if (known && known.error) {
    const item = document.createElement("li");
    item.className = "error";
    item.textContent = `저장 목록을 읽지 못했습니다 (${known.error})`;
    list.appendChild(item);
  } else if (known && known.entries) {
    if (!known.entries.length) {
      const item = document.createElement("li");
      item.className = "muted";
      item.textContent = "아직 이 게임의 저장이 없습니다.";
      list.appendChild(item);
    }
    for (const entry of known.entries) {
      const item = document.createElement("li");
      if (entry.autosave) item.appendChild(autosaveBadge());
      item.append(`${saveTitle(entry)} · ${savedWhen(entry)}`);
      list.appendChild(item);
    }
  }
  block.appendChild(list);
  const row = document.createElement("div");
  row.className = "host-save-actions";
  const refreshButton = document.createElement("button");
  refreshButton.type = "button";
  refreshButton.textContent = known ? "목록 새로 고침" : "저장 목록 보기";
  refreshButton.addEventListener("click", () => {
    loadHostSaves().catch(() => {});
  });
  const saveNow = document.createElement("button");
  saveNow.type = "button";
  saveNow.textContent = "지금 저장";
  saveNow.addEventListener("click", () => {
    saveGame().catch(() => {});
  });
  row.append(refreshButton, saveNow);
  block.appendChild(row);
  return block;
}

/* ---------- my turn ---------- */

let myTurnBefore = null;

function isMyTurn(summary) {
  if (!summary || summary.finished) return false;
  const mine = mySeats();
  if (typeof summary.confirmation === "number") {
    return mine.includes(summary.confirmation);
  }
  return Boolean(summary.decision) && mine.includes(summary.decision.owner);
}

/* On a remote server a player waits for the others with the tab in the
   background: the title says when the wait is over, and a short tone marks
   the moment. (Notifications need a secure context, which a Tailscale
   address over plain HTTP is not.) */
function noticeTurn() {
  if (!isRemote()) return;
  const mine = isMyTurn(state.summary);
  document.title = mine ? `▶ 내 차례 — ${BASE_TITLE}` : BASE_TITLE;
  if (mine && myTurnBefore === false) turnTone();
  myTurnBefore = mine;
}

function turnTone() {
  try {
    const Context = window.AudioContext || window.webkitAudioContext;
    const context = new Context();
    const tone = context.createOscillator();
    const gain = context.createGain();
    tone.frequency.value = 880;
    gain.gain.value = 0.08;
    tone.connect(gain);
    gain.connect(context.destination);
    tone.start();
    tone.stop(context.currentTime + 0.18);
    tone.onended = () => context.close();
  } catch (error) {
    /* no audio: the title still tells */
  }
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
    if (hostSaves.gameId === state.gameId) loadHostSaves().catch(() => {});
  } catch (error) {
    note(`저장 실패 (${error.message})`);
  }
}

/* The seat the table is shown from, among the seats this browser plays:
   the one that must confirm its turn end, else the one that owns the
   decision, else the seat already on screen. On an open server that is
   every human seat, so one screen follows the game around the table. */
function pickViewSeat(summary, mine) {
  if (!mine.length) return null;
  if (typeof summary.confirmation === "number") {
    /* The seat whose turn just ended still holds the table until it
       confirms the hand-over (or takes its steps back). */
    if (mine.includes(summary.confirmation)) return summary.confirmation;
  } else if (summary.decision && mine.includes(summary.decision.owner)) {
    return summary.decision.owner;
  }
  return mine.includes(state.viewSeat) ? state.viewSeat : mine[0];
}

function snapshotPath(seat) {
  const params = new URLSearchParams();
  if (seat !== null) {
    params.set("seat", String(seat));
    /* Ask only for the entries this seat's log is missing. The server
       sends the whole log again when the epoch no longer names it: an undo
       re-flags earlier entries and the end of the game lifts redaction. */
    const known = state.log;
    if (known && known.seat === seat) {
      params.set("log_after", String(known.count));
      params.set("log_epoch", known.epoch);
    }
  }
  const query = params.toString();
  return `/games/${state.gameId}/snapshot${query ? `?${query}` : ""}`;
}

/* Returns null when the tail does not continue the entries held here (it
   always does while the server honours the cursor it was sent). */
function mergeLog(known, tail) {
  let entries = tail.entries;
  if (tail.from > 0) {
    if (
      !known ||
      known.seat !== tail.seat ||
      known.entries.length !== tail.from
    ) {
      return null;
    }
    entries = known.entries.concat(tail.entries);
  }
  return { seat: tail.seat, epoch: tail.epoch, count: tail.count, entries };
}

/* Refreshes never overlap: one that arrives while another runs makes the
   running one go round once more, and every caller gets the promise of
   the state being current. */
let refreshFlight = null;
let refreshAgain = false;
let refreshHint = null;
/* A seat to ask for first, when the caller knows what state.me does not
   yet: the seat it has just claimed, or `null` after giving one up. */
let refreshSeat;
/* A pass is foreign when only the doorbell asked for it: the player did
   nothing, so it must not take their popover or scroll position away. */
let refreshForeign = false;
let refreshQueuedForeign = true;

/* One refresh is one request (M14 slice 2): the snapshot carries the
   summary, the seat's view, its legal actions and the log tail, all read
   from one state. Which seat to ask for depends on the summary, so a
   summary already in hand (a POST's response) picks it; otherwise the seat
   on screen is asked for, and asked again in the rare case that the answer
   hands the table to another seat. */
async function loadSnapshot(hint, first) {
  const gameId = state.gameId;
  if (!gameId) return;
  let seat = state.viewSeat;
  if (first !== undefined) seat = first;
  else if (hint) seat = pickViewSeat(hint, mySeats());
  for (let attempt = 0; ; attempt += 1) {
    let snapshot;
    try {
      snapshot = await api(snapshotPath(seat));
    } catch (error) {
      if (error.status !== 403 || seat === null || attempt >= 3) throw error;
      /* The seat is no longer this browser's (the host released it): a
         snapshot without a seat says which seats still are. */
      seat = null;
      continue;
    }
    if (state.gameId !== gameId) return;
    /* The seats to pick from are the ones this very answer names. */
    const wanted = pickViewSeat(snapshot.summary, snapshot.you.seats);
    if (wanted === seat || attempt >= 3) {
      adoptSnapshot(snapshot, seat);
      return;
    }
    seat = wanted;
  }
}

/* The one place where the page learns the game's state and who it is at the
   table. Snapshots are asked for one after another (refresh), so each one
   adopted was read after the one before it; a request made outside that
   line could answer late and put the page back in time, after the last
   doorbell, where nothing would correct it. */
function adoptSnapshot(snapshot, seat) {
  const held = mySeats().length > 0;
  state.summary = snapshot.summary;
  state.me = snapshot.you;
  state.viewSeat = seat;
  if (held && !mySeats().length && isRemote()) {
    noticeTurn();
    seatLost();
    return;
  }
  /* Review mode draws its own timeline and states (reviewGoto); a refresh
     arriving meanwhile must not put the live table back under it. */
  if (!state.review) {
    state.view = snapshot.view || null;
    state.actions = snapshot.actions || null;
    state.log = snapshot.log ? mergeLog(state.log, snapshot.log) : null;
    if (snapshot.log && !state.log) refreshAgain = true;
  }
  noticeTurn();
  if (!el("lobby-screen").hidden) renderLobby();
  render({ foreign: refreshForeign });
}

function refresh(summary, options) {
  const foreign = Boolean(options && options.foreign);
  if (summary) refreshHint = summary;
  if (options && options.seat !== undefined) refreshSeat = options.seat;
  if (refreshFlight) {
    refreshAgain = true;
    refreshQueuedForeign = refreshQueuedForeign && foreign;
    return refreshFlight;
  }
  refreshForeign = foreign;
  refreshFlight = (async () => {
    try {
      do {
        refreshAgain = false;
        const hint = refreshHint;
        const first = refreshSeat;
        refreshHint = null;
        refreshSeat = undefined;
        await loadSnapshot(hint, first);
        refreshForeign = refreshQueuedForeign;
        refreshQueuedForeign = true;
      } while (refreshAgain);
    } finally {
      refreshFlight = null;
    }
  })();
  return refreshFlight;
}

/* ---------- doorbell (M14 slice 3) ---------- */

/* The server rings when the game changes: a Server-Sent Events stream of
   public fields that says *that* something changed; what changed is then
   fetched through refresh(). Where the stream does not get through (a
   proxy that buffers or refuses SSE), the same check runs on a poll of
   the summary instead. */
const DOORBELL_GREETING_MS = 5000;
const DOORBELL_MAX_ERRORS = 3;
const DOORBELL_POLL_MS = 2000;

let doorbell = null;

function openDoorbell() {
  closeDoorbell();
  const gameId = state.gameId;
  if (!gameId) return;
  const bell = { gameId, source: null, greetTimer: 0, pollTimer: 0, errors: 0 };
  doorbell = bell;
  if (typeof EventSource === "undefined") {
    startDoorbellPolling(bell);
    return;
  }
  const source = new EventSource(`/games/${gameId}/events`);
  bell.source = source;
  const heard = (event) => {
    if (doorbell !== bell) return;
    bell.errors = 0;
    showConnectionLost(false);
    window.clearTimeout(bell.greetTimer);
    onDoorbell(JSON.parse(event.data));
  };
  source.addEventListener("hello", heard);
  source.addEventListener("change", heard);
  source.addEventListener("closed", () => {
    if (doorbell !== bell) return;
    closeDoorbell();
    onGameGone("deleted");
  });
  /* EventSource reconnects by itself; only a stream that keeps failing,
     or never greets, is given up for polling. */
  source.onerror = () => {
    if (doorbell !== bell) return;
    bell.errors += 1;
    if (bell.errors >= DOORBELL_MAX_ERRORS) startDoorbellPolling(bell);
  };
  bell.greetTimer = window.setTimeout(() => {
    if (doorbell === bell) startDoorbellPolling(bell);
  }, DOORBELL_GREETING_MS);
}

function startDoorbellPolling(bell) {
  if (bell.pollTimer) return;
  window.clearTimeout(bell.greetTimer);
  if (bell.source) {
    bell.source.close();
    bell.source = null;
  }
  bell.pollTimer = window.setInterval(async () => {
    if (doorbell !== bell || state.busy) return;
    try {
      /* A summary has every field a doorbell payload is compared by. */
      const summary = await api(`/games/${bell.gameId}`);
      if (doorbell !== bell) return;
      showConnectionLost(false);
      onDoorbell(summary);
    } catch (error) {
      if (doorbell !== bell) return;
      if (error.status === 404) {
        /* The server answers and does not know the game: deleted, or
           the server came back from a restart without it. */
        closeDoorbell();
        onGameGone("missing");
      } else if (error.status === undefined) {
        /* No answer at all: the server is down or unreachable. The
           poll goes on; a restarted server ends it with the 404. */
        showConnectionLost(true);
      }
    }
  }, DOORBELL_POLL_MS);
}

function showConnectionLost(lost) {
  el("connection-note").hidden = !lost;
}

function closeDoorbell() {
  const bell = doorbell;
  doorbell = null;
  showConnectionLost(false);
  if (!bell) return;
  window.clearTimeout(bell.greetTimer);
  window.clearInterval(bell.pollTimer);
  if (bell.source) bell.source.close();
}

/* A stale picture is refreshed; a change to `players` alone (a name, a
   claim, who is online) is public as it stands and needs no request. */
function onDoorbell(bell) {
  const summary = state.summary;
  if (!summary || state.busy) return;
  if (
    bell.revision !== summary.revision ||
    bell.undo_count !== summary.undo_count ||
    bell.log_count !== summary.log_count ||
    bell.confirmation !== summary.confirmation ||
    bell.finished !== summary.finished
  ) {
    refresh(null, { foreign: true }).catch(showRefreshError);
  } else if (
    bell.players &&
    JSON.stringify(bell.players) !== JSON.stringify(summary.players)
  ) {
    const mine = mySeatChanged(summary.players, bell.players);
    summary.players = bell.players;
    if (mine) {
      /* A release by the host takes a seat from under this browser without
         any game step, and the payload cannot say whose claim it shows:
         ask who this browser still is, in line with every other refresh.
         A seat nobody holds is certainly not held here, so the seat on
         screen is not asked for once it shows as free. */
      const shown = bell.players[state.viewSeat];
      const options = { foreign: true };
      if (!shown || !shown.claimed) options.seat = null;
      refresh(null, options).catch(showRefreshError);
    } else if (refreshFlight) {
      /* A snapshot already on its way may have been read before this bell
         rang (a page entering a game opens its stream and asks for its
         snapshot at once) and would put the older list back when it lands,
         with no later bell to correct it: one more pass after it. */
      refresh(null, { foreign: true }).catch(showRefreshError);
    } else if (!el("lobby-screen").hidden) {
      renderLobby();
    } else {
      render({ foreign: true });
    }
  }
}

/* Whether a seat this browser holds on a remote server changed its claim or
   its name. Presence alone (somebody's tab opened or closed) is public as
   the payload has it and needs no request. */
function mySeatChanged(before, after) {
  if (!isRemote()) return false;
  return mySeats().some((seat) => {
    const was = before[seat];
    const now = after[seat];
    return !was || !now || was.claimed !== now.claimed || was.name !== now.name;
  });
}

function onGameGone(reason) {
  /* Nothing to come back to: do not offer it on the landing page. */
  if (storageGet("dune.lastGame") === state.gameId) storageRemove("dune.lastGame");
  leaveGame(
    reason === "deleted"
      ? "이 게임은 서버에서 삭제되었습니다."
      : "이 게임은 서버에 더 이상 없습니다. 서버가 다시 시작됐다면 호스트가 자동 저장을 " +
          "불러온 뒤 보내는 새 방 링크로 들어오세요."
  );
}

async function applyAction(index) {
  if (state.busy) return;
  state.busy = true;
  state.pick = null;
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
    await refresh(summary);
  } catch (error) {
    state.busy = false;
    /* 409: the table moved on. 403: the seat is no longer this browser's;
       the refresh finds that out and lands in the seat picker. */
    if (error.status === 409 || error.status === 403) {
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
    await refresh(summary);
  } catch (error) {
    state.busy = false;
    /* 409: the table moved on. 403: the seat is no longer this browser's;
       the refresh finds that out and lands in the seat picker. */
    if (error.status === 409 || error.status === 403) {
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
    await refresh(summary);
  } catch (error) {
    state.busy = false;
    /* 409: the table moved on. 403: the seat is no longer this browser's;
       the refresh finds that out and lands in the seat picker. */
    if (error.status === 409 || error.status === 403) {
      await refresh();
      return;
    }
    el("game-error").textContent = `되돌리기 실패 (${error.message})`;
    el("game-error").hidden = false;
    render();
  }
}

/* ---------- replay review ---------- */

/* `options.cursor`: the step to open at (default: the end of the game).
   `options.play`: start walking forward from there (playback below). */
async function enterReview(seat, options) {
  const gameId = state.gameId;
  const meta = await api(`/games/${gameId}/review?seat=${seat}`);
  if (state.gameId !== gameId || !state.summary) return;
  stopPlayback();
  const wanted = options && typeof options.cursor === "number" ? options.cursor : null;
  const cursor = wanted === null ? meta.step_count : wanted;
  /* The log position of every live step: steps that were taken back and
     the undo markers sit between them (reviewLog). */
  const liveIndex = [];
  for (const entry of meta.log || []) {
    if (entry.type !== "undo" && !entry.undone) liveIndex.push(entry.index);
  }
  state.review = {
    meta,
    seat,
    cursor,
    /* Where the cursor stood before its latest move: what lies between is
       what the log marks as fresh. */
    cameFrom: cursor,
    round: null,
    phase: null,
    liveIndex,
    stops: turnStops(meta.steps),
  };
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
  /* "My actions" are the reviewed seat's; with nobody at the table the
     buttons say whose they are. */
  const own = humanSeats().length ? "내" : "이 좌석";
  el("review-prev-own").textContent = `이전 ${own} 행동`;
  el("review-next-own").textContent = `다음 ${own} 행동`;
  await reviewGoto(cursor);
  if (options && options.play && state.review && state.review.meta === meta) {
    /* The opening position gets its interval on screen too. */
    startPlayback(playback.intervalMs);
  }
}

/* Review states load at very different speeds (the server replays every
   step up to the cursor), so answers can arrive out of order; only the
   latest request may draw. Resolves to true once it drew, false when the
   request failed, and null when a later request (or leaving review) took
   the page over meanwhile. */
let reviewRequest = 0;

async function reviewGoto(cursor) {
  const review = state.review;
  if (!review) return null;
  cursor = Math.max(0, Math.min(review.meta.step_count, cursor));
  const request = ++reviewRequest;
  try {
    el("game-error").hidden = true;
    const payload = await api(
      `/games/${state.gameId}/review/${cursor}?seat=${review.seat}`
    );
    if (request !== reviewRequest || state.review !== review) return null;
    review.cameFrom = review.cursor;
    review.cursor = cursor;
    review.round = payload.round_number;
    review.phase = payload.phase;
    state.view = payload.view;
    state.actions = null;
    el("review-slider").value = String(cursor);
    let status =
      `step ${cursor}/${review.meta.step_count}` +
      ` · 라운드 ${payload.round_number}` +
      ` · ${PHASE_LABELS[payload.phase] || payload.phase}` +
      ` · ${describeReviewSpan(review)}`;
    /* Undo markers that rewound the game to this exact step (M11 slice 6). */
    for (const item of review.meta.undo_history || []) {
      if (item.step !== cursor) continue;
      status +=
        ` · ↩ 좌석 ${item.seat}가 여기서 ${item.count}단계 되돌림: ` +
        item.undone.map(describeAction).join(" / ");
    }
    el("review-status").textContent = status;
    renderPlaybackControls();
    render();
    return true;
  } catch (error) {
    el("game-error").textContent = `검토 상태 조회 실패 (${error.message})`;
    el("game-error").hidden = false;
    return false;
  }
}

/* What the cursor's latest move showed: the step under the cursor, or,
   when the move was one whole turn forward (turn-by-turn playback), the
   action that opened the turn — it says where the Agent went — and how
   many steps came with it. A seek across several turns names no turn. */
function describeReviewSpan(review) {
  const steps = review.meta.steps;
  const stride = review.cursor - review.cameFrom;
  const oneTurn =
    stride > 1 && review.stops.find((stop) => stop > review.cameFrom) === review.cursor;
  const opening = oneTurn
    ? steps.slice(review.cameFrom, review.cursor).find((label) => label.type === "action")
    : null;
  if (!opening) return describeReviewStep(steps[review.cursor - 1]);
  return `${describeReviewStep(opening)} 외 ${stride - 1}수`;
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
  stopPlayback();
  state.review = null;
  el("review-bar").hidden = true;
  refresh().catch(() => {});
}

/* The finished game's log as far as the review cursor: every entry up to
   the cursor's live step, the steps taken back on the way included, as they
   happened. What the cursor's latest move forward added counts as fresh. */
function reviewLog(review) {
  const entries = review.meta.log || [];
  const lengthAt = (cursor) =>
    cursor >= review.liveIndex.length
      ? entries.length
      : cursor <= 0
        ? 0
        : review.liveIndex[cursor - 1] + 1;
  const count = lengthAt(review.cursor);
  return {
    entries: entries.slice(0, count),
    count,
    freshFrom: lengthAt(Math.min(review.cameFrom, review.cursor)),
  };
}

/* ---------- playback (watching a finished game unfold) ---------- */

/* The review cursor walks forward by itself, one turn or one step per
   interval. A game of AI seats only is watched this way (watchGame): the
   server plays such a game to the end as it is created — a session rests on
   a human decision or on the finished game — so by the time anybody looks
   there is a full record to walk through and nothing left to wait for. */
const playback = { playing: false, timer: 0, unit: "turn", intervalMs: 1000 };

/* Where turn-by-turn playback stops: the cursor positions between two
   turns, by the rule the log's turn cards follow (logGroups) — the action
   before closed its turn, or the next action is another seat's. Chance steps
   go with the action before them, and seats passing one after another (a
   Combat Intrigue window nobody used) make one stop, not four. */
function turnStops(steps) {
  const stops = [];
  let last = null;
  steps.forEach((label, position) => {
    if (label.type !== "action") return;
    if (last) {
      const closed =
        SOLO_ACTIONS.has(last.action_id) ||
        QUIET_ACTIONS.has(last.action_id) ||
        label.actor !== last.actor;
      const passing = last.action_id === "pass" && label.action_id === "pass";
      if (closed && !passing) stops.push(position);
    }
    last = label;
  });
  stops.push(steps.length);
  return stops;
}

function playbackNext(review) {
  if (playback.unit === "step") return review.cursor + 1;
  const stop = review.stops.find((position) => position > review.cursor);
  return stop === undefined ? review.meta.step_count : stop;
}

function schedulePlayback(delay) {
  window.clearTimeout(playback.timer);
  playback.timer = window.setTimeout(() => {
    playbackTick().catch(() => {});
  }, delay);
}

async function playbackTick() {
  const review = state.review;
  if (!review || !playback.playing) return;
  if (review.cursor >= review.meta.step_count) {
    stopPlayback();
    return;
  }
  const started = performance.now();
  const drew = await reviewGoto(playbackNext(review));
  if (state.review !== review || !playback.playing) return;
  /* A seek answered first, and has set the next move itself (reviewSeek). */
  if (drew === null) return;
  if (drew === false || review.cursor >= review.meta.step_count) {
    stopPlayback();
    return;
  }
  /* The interval runs from one move to the next, not from answer to move. */
  schedulePlayback(Math.max(0, playback.intervalMs - (performance.now() - started)));
}

/* `delay`: how long the position on screen stays before the first move. */
function startPlayback(delay) {
  const review = state.review;
  if (!review) return;
  playback.playing = true;
  renderPlaybackControls();
  if (review.cursor < review.meta.step_count) {
    schedulePlayback(delay || 0);
    return;
  }
  /* Pressed at the end of the game, play starts it over. */
  reviewGoto(0).then((drew) => {
    if (state.review !== review || !playback.playing) return;
    if (drew) schedulePlayback(playback.intervalMs);
    else stopPlayback();
  });
}

function stopPlayback() {
  playback.playing = false;
  window.clearTimeout(playback.timer);
  renderPlaybackControls();
}

/* A seek (slider, first, last) moves the cursor and leaves playback as it
   was; the position sought gets a full interval before the next move. */
function reviewSeek(cursor) {
  if (!state.review) return;
  if (playback.playing) schedulePlayback(playback.intervalMs);
  reviewGoto(cursor).catch(() => {});
}

/* Stepping by hand (one step, one own action) takes the wheel. */
function reviewStep(move) {
  if (!state.review) return;
  stopPlayback();
  move();
}

function renderPlaybackControls() {
  const review = state.review;
  const atEnd = Boolean(review) && review.cursor >= review.meta.step_count;
  el("review-play").textContent = playback.playing
    ? "일시정지"
    : atEnd
      ? "처음부터 재생"
      : "재생";
  el("review-unit").value = playback.unit;
  el("review-interval").value = String(playback.intervalMs);
}

/* A game nobody sits at has no seat to look from while it is live, and it
   is never live when somebody looks: it opens as a review from its first
   position, playing. */
function spectatorOnly() {
  return Boolean(state.summary) && !humanSeats().length;
}

function watchGame() {
  enterReview(state.review ? state.review.seat : 0, { cursor: 0, play: true }).catch(
    (error) => {
      el("game-error").textContent = `관전 시작 실패 (${error.message})`;
      el("game-error").hidden = false;
    }
  );
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
  [/\b[Tt]rash an Intrigue card\b/y, () => icon("trash_intrigue", "Trash an Intrigue card")],
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

/* The panes that scroll on their own; their content is rebuilt on every
   render, which would throw the reader back to the top. */
const SCROLL_PANES = ["seats", "side-main", "board", "market", "private-zone"];

/* `foreign`: somebody else changed the game (the doorbell asked for this
   pass). The player did nothing, so a pinned popover stays open and every
   pane keeps its scroll position. */
function render(options) {
  const summary = state.summary;
  if (!summary) return;
  sanitizePick();
  const foreign = Boolean(options && options.foreign);
  const kept = foreign
    ? SCROLL_PANES.map((id) => [el(id), el(id).scrollTop, el(id).scrollLeft])
    : [];
  if (!(foreign && popoverPinned)) closePopover();
  const allianceBefore = allianceTokenPlaces();
  const shown = state.review && state.review.phase ? state.review : null;
  const round = shown ? shown.round : summary.round_number;
  const phase = shown ? shown.phase : summary.phase;
  el("header-status").textContent =
    `라운드 ${round} · ${PHASE_LABELS[phase] || phase}` +
    (summary.game_seed === null ? "" : ` · seed ${summary.game_seed}`) +
    (summary.choam_module ? " · CHOAM" : "") +
    (summary.promo_cards ? " · promo" : "") +
    (summary.bloodlines ? " · Bloodlines" : "") +
    (summary.tech_module ? " · Tech" : "") +
    (summary.immortality ? " · Immortality" : "") +
    (summary.leader_draft ? " · draft" : "") +
    (state.review ? (spectatorOnly() ? " · AI 대국 관전" : " · 리플레이 검토") : "");
  el("decision-banner").hidden = Boolean(state.review);
  renderBanner();
  renderStandings();
  renderBoard();
  renderMarket();
  renderSeats();
  renderLog();
  renderPrivate();
  renderDisclosure();
  el("host-panel").hidden = !(isRemote() && isAdmin());
  renderHostBlock(el("host-panel-body"));
  applySpotlight();
  for (const [pane, top, left] of kept) {
    pane.scrollTop = top;
    pane.scrollLeft = left;
  }
  animateMovedAllianceTokens(allianceBefore);
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
      prompt.textContent = "행동을 마쳤습니다. 턴을 넘길까요?";
      meta.textContent =
        `되돌릴 수 있는 동안은 턴이 넘어가지 않습니다 · 다음: ${playerLabel(decision.owner)}`;
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
    } else if (typeof summary.confirmation === "number") {
      /* Another seat's turn has ended but can still be taken back; nobody
         moves until that seat hands it over. */
      prompt.textContent =
        `${playerLabel(summary.confirmation)}의 턴 종료 확정을 기다리는 중…` +
        waitingHint(summary.confirmation);
      meta.textContent = `다음: ${playerLabel(decision.owner)}`;
      info.append(prompt, meta);
    } else if (decision.owner !== state.viewSeat) {
      prompt.textContent =
        `${playerLabel(decision.owner)} 결정 대기 중…` + waitingHint(decision.owner);
      meta.textContent = decision.prompt;
      info.append(prompt, meta);
    } else {
      prompt.textContent = decision.prompt;
      meta.textContent = `좌석 ${decision.owner} (당신)`;
      info.append(prompt, meta);

      if (state.actions) renderActionPanel(actionsBox);
    }
  }

  /* A human seat may still have takeable-back steps after the game ends
     (its last live step), so the undo row renders in both branches above. */
  appendUndoRow(info);
}

/* Why a wait may be a long one: nobody sits there yet, or they dropped off. */
function waitingHint(seat) {
  const info = playerInfo(seat);
  if (!isRemote() || info.kind !== "human") return "";
  if (!info.claimed) return " (아직 아무도 앉지 않은 좌석입니다 — 방 링크를 보내 주세요)";
  return info.online ? "" : " (접속이 끊겨 있습니다)";
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

/* What the seat's running combat strength becomes with a step: the
   server's dry run of that step (`strength_after`), so the engine's own
   figure. */
function strengthPreview(after) {
  const own = state.view && state.view.players[state.viewSeat];
  const now = own ? own.combat_strength || 0 : 0;
  const badge = document.createElement("span");
  badge.className = "strength-preview";
  badge.title = "이 행동 뒤의 내 전투력";
  badge.append(icon("sword", "전투력"), ` ${now} → ${after}`);
  return badge;
}

/* What revealing the hand right now would give: the server's dry run of
   `reveal_turn` (`reveal_preview`: the Persuasion the Reveal opens with and
   the strength once the revealed swords count), so the engine's own sum. */
function revealPreview(preview) {
  const badge = document.createElement("span");
  badge.className = "reveal-preview";
  badge.title = "지금 손패를 공개하면 바로 얻는 Persuasion과 전투력 (Reveal 중의 선택 효과는 제외)";
  badge.append(icon("persuasion", "Persuasion"), ` ${preview.persuasion}`);
  const own = state.view && state.view.players[state.viewSeat];
  const now = own ? own.combat_strength || 0 : 0;
  if (typeof preview.strength === "number" && preview.strength !== now) {
    badge.append(" · ", icon("sword", "전투력"), ` ${now} → ${preview.strength}`);
  }
  return badge;
}

/* The `reveal_turn` step among the seat's legal actions, if it is there and
   the server previewed it. */
function revealTurnPreview() {
  if (state.review || !state.actions) return null;
  const reveal = state.actions.actions.find((action) => action.action_id === "reveal_turn");
  return reveal && reveal.reveal_preview ? reveal.reveal_preview : null;
}

/* ---------- count steppers ----------

   "Deploy 1", "Deploy 2", "Deploy 3" are one decision with a number in it.
   Actions of one id that differ only in a `count` argument are shown as a
   single row with a stepper over the legal counts; the panel and the
   Conflict area share the chosen number. */
function countFamilies(actions) {
  const byId = new Map();
  for (const action of actions) {
    if (!byId.has(action.action_id)) byId.set(action.action_id, []);
    byId.get(action.action_id).push(action);
  }
  const families = new Map();
  for (const [id, group] of byId) {
    const onlyCount = group.every((action) => {
      const keys = Object.keys(action.arguments);
      return keys.length === 1 && keys[0] === "count" && Number.isInteger(action.arguments.count);
    });
    /* Units go in and out of the Conflict through the same control even
       when a single count is left to choose. */
    if (!onlyCount || (group.length < 2 && !FORCE_STEPPER_ACTIONS.has(id))) continue;
    families.set(id, [...group].sort((a, b) => a.arguments.count - b.arguments.count));
  }
  return families;
}

/* The family's action for the chosen count. Sending units defaults to all
   of them, taking them back to one. */
function chosenOf(id, family) {
  const found = family.find((action) => action.arguments.count === state.counts[id]);
  if (found) return found;
  return id.startsWith("deploy") ? family[family.length - 1] : family[0];
}

function countRow(id, family, compact) {
  const chosen = chosenOf(id, family);
  const position = family.indexOf(chosen);
  const row = document.createElement("div");
  row.className = "action-item count-row" + (compact ? " compact" : "");
  row.dataset.action = id;
  row.dataset.index = String(chosen.index);
  const label = document.createElement("span");
  label.className = "count-label";
  label.textContent = ACTION_LABELS[id] || prettify(id);
  const stepper = document.createElement("span");
  stepper.className = "stepper";
  const step = (text, target, title) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = title;
    button.disabled = state.busy || !family[target];
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      state.counts[id] = family[target].arguments.count;
      render();
    });
    return button;
  };
  const value = document.createElement("strong");
  value.className = "stepper-value";
  value.textContent = String(chosen.arguments.count);
  stepper.append(step("−", position - 1, "하나 적게"), value, step("+", position + 1, "하나 더"));
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "count-confirm";
  confirm.disabled = state.busy;
  confirm.append(compact ? "확정" : `${chosen.arguments.count}개 ${label.textContent}`);
  if (typeof chosen.strength_after === "number") {
    confirm.appendChild(strengthPreview(chosen.strength_after));
  }
  confirm.addEventListener("click", (event) => {
    event.stopPropagation();
    applyAction(chosen.index);
  });
  row.append(label, stepper, confirm);
  return row;
}

/* A list of legal actions with its count families folded into rows. */
function appendActionItems(box, actions) {
  const families = countFamilies(actions);
  const done = new Set();
  for (const action of actions) {
    const family = families.get(action.action_id);
    if (!family) box.appendChild(actionItem(action));
    else if (!done.has(action.action_id)) {
      done.add(action.action_id);
      box.appendChild(countRow(action.action_id, family, false));
    }
  }
}

/* ---------- Reveal purchases ----------

   A Reveal is a small shop: the Persuasion still unspent (the server's
   summary carries it), what has been bought so far (the session log), the
   cards that can still be bought, the Reveal effects left to resolve, and
   one clear way out. */
function isAcquire(action) {
  return action.action_id.startsWith("acquire");
}

function boughtThisReveal() {
  const entries = (state.log && state.log.entries) || [];
  const seat = state.viewSeat;
  let start = -1;
  entries.forEach((entry, position) => {
    if (entry.action_id === "reveal_turn" && entry.actor === seat && !entry.undone) start = position;
  });
  if (start < 0) return [];
  const bought = [];
  for (const entry of entries.slice(start + 1)) {
    if (entry.actor !== seat || entry.undone) continue;
    for (const event of entry.events || []) {
      if (event.kind === "card_acquired" && event.payload.player === seat) {
        bought.push(event.payload.card_id);
      }
    }
  }
  return bought;
}

function acquireCostNode(action) {
  const ref = actionRefs(action)[0];
  const entry = ref ? lookup(baseId(ref)) : null;
  if (!entry) return null;
  const cost = document.createElement("span");
  cost.className = "acquire-cost";
  if (action.action_id.includes("tleilaxu") && typeof entry.specimens === "number") {
    cost.append(`specimen ${entry.specimens}`);
  } else if (typeof entry.cost === "number") {
    cost.append(amount(action.action_id.includes("solari") ? "solari" : "persuasion", "비용", entry.cost));
  } else {
    return null;
  }
  return cost;
}

function renderRevealPanel(box, actions) {
  const decision = state.summary.decision;
  const status = document.createElement("div");
  status.className = "reveal-status";
  if (typeof decision.persuasion === "number") {
    const left = document.createElement("span");
    left.className = "reveal-persuasion";
    left.dataset.persuasion = String(decision.persuasion);
    left.append("남은 Persuasion ", amount("persuasion", "Persuasion", decision.persuasion));
    status.appendChild(left);
  }
  const bought = boughtThisReveal();
  if (bought.length) {
    const list = document.createElement("span");
    list.className = "reveal-bought";
    list.append("산 카드: ");
    bought.forEach((cardId) => list.appendChild(chip(cardId)));
    status.appendChild(list);
  }
  if (status.childNodes.length) box.appendChild(status);

  const heading = (text) => {
    const node = document.createElement("div");
    node.className = "pick-others muted";
    node.textContent = text;
    box.appendChild(node);
  };
  const buys = actions.filter(isAcquire);
  const finish = actions.filter((action) => action.action_id === "finish_reveal");
  const effects = actions.filter((action) => !isAcquire(action) && action.action_id !== "finish_reveal");
  if (effects.length) {
    heading("Reveal 효과");
    appendActionItems(box, effects);
  }
  if (buys.length) {
    heading("살 수 있는 카드 — 테이블에서 빛나는 카드를 눌러도 됩니다");
    for (const action of buys) {
      const item = actionItem(action);
      const cost = acquireCostNode(action);
      if (cost) item.querySelector("button").appendChild(cost);
      box.appendChild(item);
    }
  }
  for (const action of finish) {
    const item = actionItem(action);
    item.classList.add("finish-row");
    const button = item.querySelector("button");
    button.textContent = buys.length ? "구매 끝 · Reveal 종료" : "Reveal 종료";
    box.appendChild(item);
  }
}

/* The arguments of an action that name something on the table: a board
   space or an observation post, or a card instance (ids with a colon). */
function tableRefs(action) {
  return actionRefs(action).filter(
    (ref) => ref.includes(":") || state.catalog.spaces[ref] || state.catalog.posts[ref]
  );
}

function actionItem(action, onApply) {
  const wrap = document.createElement("div");
  wrap.className = "action-item";
  wrap.dataset.index = String(action.index);
  wrap.dataset.refs = JSON.stringify(actionRefs(action));
  const button = document.createElement("button");
  button.appendChild(iconize(describeAction(action)));
  button.disabled = state.busy;
  button.addEventListener("click", () =>
    onApply ? onApply(action) : applyAction(action.index)
  );
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
  if (typeof action.strength_after === "number") {
    button.appendChild(strengthPreview(action.strength_after));
  }
  if (action.reveal_preview) button.appendChild(revealPreview(action.reveal_preview));
  if (action.warning) {
    /* The server dry-ran the step: the troop supply cannot cover what the
       effect asks for (OQ-030, OQ-049), so the action does less than printed. */
    wrap.classList.add("shortfall");
    const badge = document.createElement("span");
    badge.className = "shortfall-badge";
    badge.textContent = action.warning;
    badge.title = "선택은 할 수 있지만 supply가 부족해 인쇄된 만큼 되지 않습니다";
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

/* ---------- staged Agent turn ----------

   The server offers an Agent turn as one flat list: every legal
   (card, space, cost option, graft) is its own `agent_turn` action, because
   that is what the action codec and the learning agents need. A person
   plays it in steps: the card, then the space, then what is still open.
   The steps are only a view of that same list: the page filters it by
   what has been picked and posts the one action index that remains, so
   neither the engine nor the codec knows the difference. Either order
   works (a space first lights the cards that can go there). The flat list
   stays behind a toggle. */
/* The count families that move units into and out of the Conflict; they
   get a stepper on the board as well (renderTrackMarkers). */
const FORCE_STEPPER_ACTIONS = new Set([
  "deploy_troops",
  "withdraw_troops",
  "deploy_commanders",
  "withdraw_commanders",
]);
const PLACEMENT_ACTION = "agent_turn";
const FULL_LIST_KEY = "dune.fullActionList";

function placementActions() {
  if (!state.actions) return [];
  return state.actions.actions.filter((action) => action.action_id === PLACEMENT_ACTION);
}

function fullActionList() {
  return storageGet(FULL_LIST_KEY) === "1";
}

function stagedTurn() {
  return !state.review && !fullActionList() && placementActions().length > 0;
}

/* Whether a placement fits what has been picked; any other action always
   does. Two picked cards are a graft: "you may use an Agent icon from
   either card" [Immortality p. 10], and the server lists that as the graft
   placements of each card, so the pair reaches the union of the two. */
function matchesPick(action, pick = state.pick) {
  if (!pick || action.action_id !== PLACEMENT_ACTION) return true;
  const args = action.arguments;
  if (pick.spaceId && args.space_id !== pick.spaceId) return false;
  if (pick.partnerId) {
    return (
      args.graft === true &&
      (args.card_id === pick.cardId || args.card_id === pick.partnerId)
    );
  }
  return !pick.cardId || args.card_id === pick.cardId;
}

function isGraftCard(instanceId) {
  const entry = lookup(baseId(instanceId));
  return Boolean(entry && entry.graft);
}

function graftPlacements(cardId) {
  return placementActions().filter(
    (action) => action.arguments.graft === true && action.arguments.card_id === cardId
  );
}

/* Whether two hand cards can be played together: one of them is a Graft
   card [Immortality p. 10] and the server offers a graft placement for at
   least one of them (a card with no Agent icon leans on the other's). */
function canPair(cardId, otherId) {
  const hand = (state.view && state.view.private && state.view.private.hand) || [];
  if (cardId === otherId || !hand.includes(cardId) || !hand.includes(otherId)) return false;
  if (!isGraftCard(cardId) && !isGraftCard(otherId)) return false;
  return graftPlacements(cardId).length > 0 || graftPlacements(otherId).length > 0;
}

/* A hand card that could join (or replace the partner of) the picked card. */
function partnerCandidate(instanceId) {
  const pick = state.pick;
  return Boolean(
    pick && pick.cardId && stagedTurn() &&
    instanceId !== pick.partnerId && canPair(pick.cardId, instanceId)
  );
}

/* A pick outlives re-renders (another seat's doorbell must not undo it) but
   not the actions it was made from. */
function sanitizePick() {
  if (!state.pick) return;
  const supported = () => placementActions().some((action) => matchesPick(action));
  if (stagedTurn() && !supported() && state.pick.partnerId) delete state.pick.partnerId;
  if (!stagedTurn() || !supported()) state.pick = null;
}

function clearPick(part) {
  if (!state.pick) return;
  if (part) delete state.pick[part];
  if (part === "cardId" && state.pick.partnerId) {
    state.pick.cardId = state.pick.partnerId;
    delete state.pick.partnerId;
  }
  if (!part || (!state.pick.cardId && !state.pick.spaceId)) state.pick = null;
  closePopover();
  render();
}

/* With a pick made, the other cards (or spaces) that could take its place:
   they stay faintly lit, because a click on one swaps the pick. */
function pickAlternative(ref, part) {
  const pick = state.pick;
  if (!pick || !pick[part] || pick[part] === ref || !stagedTurn()) return false;
  const rest = { ...pick, [part]: ref };
  return placementActions().some((action) => matchesPick(action, rest));
}

/* One step of the staged turn: `ref` is a card or a space of some legal
   placement, or a hand card that can be grafted to the picked one. Returns
   false when the click is not part of a placement. */
function pickStep(ref, entry, anchor) {
  const placements = placementActions();
  const current = state.pick || {};
  const joins = Boolean(current.cardId) && canPair(current.cardId, ref);
  const part =
    joins || placements.some((action) => action.arguments.card_id === ref)
      ? "cardId"
      : placements.some((action) => action.arguments.space_id === ref)
        ? "spaceId"
        : null;
  if (!part) return false;
  if (current[part] === ref || (part === "cardId" && current.partnerId === ref)) {
    clearPick(current.partnerId === ref ? "partnerId" : part);
    return true;
  }
  const next = { ...current };
  if (part === "spaceId") next.spaceId = ref;
  else if (joins) next.partnerId = ref;
  else {
    next.cardId = ref;
    delete next.partnerId;
  }
  if (!placements.some((action) => matchesPick(action, next))) {
    /* The halves of the pick cannot go together. */
    const cards = [current.cardId, current.partnerId].filter(Boolean).map(nameOf).join(" + ");
    note(
      part === "spaceId"
        ? `${cards}(으)로는 ${entry ? entry.name : nameOf(ref)}에 갈 수 없습니다.`
        : `${entry ? entry.name : nameOf(ref)}(으)로는 ${nameOf(current.spaceId)}에 갈 수 없습니다.`
    );
    if (entry) pinPopover(entry, anchor);
    return true;
  }
  state.pick = next;
  const candidates = pickCandidates(next);
  if (next.cardId && next.spaceId && candidates.length === 1) {
    applyPlacement(candidates[0]);
    return true;
  }
  render();
  if (next.cardId && next.spaceId) openPlacementChooser(candidates);
  return true;
}

/* The placements a pick still allows. For a graft pair the server lists the
   same move once per card that can stand as the placed one; whichever icon
   is used "both cards are treated as having sent the Agent" [Immortality
   p. 10], so those are one choice here, sent with the first-picked card
   when it can be. */
function pickCandidates(pick = state.pick) {
  const fitting = placementActions().filter((action) => matchesPick(action, pick));
  if (!pick || !pick.partnerId) return fitting;
  const byOption = new Map();
  for (const action of fitting) {
    const option = JSON.stringify(
      Object.entries(action.arguments)
        .filter(([key]) => key !== "card_id")
        .sort(([a], [b]) => a.localeCompare(b))
    );
    const kept = byOption.get(option);
    if (!kept || action.arguments.card_id === pick.cardId) byOption.set(option, action);
  }
  return [...byOption.values()];
}

/* Post a placement. With two cards picked the other one follows as the
   graft partner, which the engine asks for in the very next frame. */
function applyPlacement(action) {
  const pick = state.pick;
  const partner =
    pick && pick.partnerId
      ? (action.arguments.card_id === pick.cardId ? pick.partnerId : pick.cardId)
      : null;
  const played = applyAction(action.index);
  if (partner) played.then(() => followWithPartner(partner));
}

function followWithPartner(partnerId) {
  const decision = state.summary && state.summary.decision;
  if (
    !decision || decision.kind !== "graft_partner" ||
    decision.owner !== state.viewSeat || !state.actions
  ) {
    return;
  }
  const action = state.actions.actions.find(
    (item) =>
      item.action_id === "choose_graft_partner" && item.arguments.card_id === partnerId
  );
  if (action) {
    applyAction(action.index);
    return;
  }
  /* The space was open to this card only with a certain partner (an
     occupied space on Tleilaxu Infiltrator's promise, a Bond icon on
     Ghola's): the engine's own partner choice is on screen now. */
  note(
    `${nameOf(partnerId)}은(는) 이 칸에서 함께 낼 수 없습니다. ` +
      "함께 낼 카드를 다시 고르거나 되돌리기를 누르세요."
  );
}

/* What still tells two placements of one card on one space apart: the
   space's cost option and whether the card is grafted. */
function placementOptionNode(action, candidates) {
  const line = document.createElement("span");
  line.className = "pick-option";
  const space = state.catalog.spaces[action.arguments.space_id];
  const option = space && spaceOptionsFor(space)[action.arguments.cost_option || 0];
  if (option && candidates.some((other) => other.arguments.cost_option !== action.arguments.cost_option)) {
    line.append(costNode(option.cost), icon("arrow_right", "→"), iconize(option.effect));
  }
  const differs = (key) =>
    candidates.some((other) => other.arguments[key] !== action.arguments[key]);
  if (differs("discount")) {
    const discount = document.createElement("span");
    discount.append(
      action.arguments.discount
        ? amount(action.arguments.discount, action.arguments.discount, 1)
        : "할인 없이",
      action.arguments.discount ? " 할인" : ""
    );
    line.appendChild(discount);
  }
  if (differs("infiltrate_post_id")) {
    const spy = document.createElement("span");
    spy.textContent = action.arguments.infiltrate_post_id
      ? `Spy 회수 — ${prettify(action.arguments.infiltrate_post_id)}`
      : "Spy 회수 없이";
    line.appendChild(spy);
  }
  if (candidates.some((other) => Boolean(other.arguments.graft) !== Boolean(action.arguments.graft))) {
    const graft = document.createElement("span");
    graft.className = "pick-graft";
    graft.textContent = action.arguments.graft
      ? "Graft — 함께 낼 카드는 다음에 고릅니다"
      : "이 카드만";
    line.appendChild(graft);
  }
  if (!line.childNodes.length) line.appendChild(iconize(describeAction(action)));
  return line;
}

function placementOptionItem(action, candidates) {
  const item = actionItem(action, applyPlacement);
  const button = item.querySelector("button");
  const badges = [...button.querySelectorAll(".irreversible-badge, .shortfall-badge")];
  button.textContent = "";
  button.append(placementOptionNode(action, candidates), ...badges);
  return item;
}

/* The options of a complete pick, next to the space they are about. The
   side panel lists the same ones, so closing this loses nothing. */
function openPlacementChooser(candidates) {
  const pick = state.pick;
  const anchor =
    document.querySelector(`.hotspot[data-space="${pick.spaceId}"]`) ||
    document.querySelector(`.space-row[data-space="${pick.spaceId}"]`) ||
    el("actions");
  const pop = el("card-popover");
  pop.textContent = "";
  pop.classList.remove("hover");
  const title = document.createElement("div");
  title.className = "popover-title";
  title.textContent = `${pickedCardNames(pick)} → ${nameOf(pick.spaceId)}`;
  pop.appendChild(title);
  for (const action of candidates) pop.appendChild(placementOptionItem(action, candidates));
  placePopover(pop, anchor, 340);
  popoverPinned = true;
}

function pickedCardNames(pick) {
  return [pick.cardId, pick.partnerId].filter(Boolean).map(nameOf).join(" + ");
}

function pickStepNode(number, label, ref, part) {
  const step = document.createElement("button");
  step.type = "button";
  step.className = "pick-step" + (ref ? " done" : "");
  step.disabled = !ref || state.busy;
  step.append(`${number} ${label} · `);
  const value = document.createElement("strong");
  value.textContent = ref ? nameOf(ref) : "고르세요";
  step.appendChild(value);
  if (ref) {
    step.append(" ✕");
    step.title = "다시 고르기";
    step.addEventListener("click", () => clearPick(part));
  }
  return step;
}

/* The decision panel of the seat to move. An Agent turn is staged (card,
   space, what is left), with the turn's other actions under it; everything
   else, and the staged turn behind its toggle, is the flat list. */
function renderActionPanel(box) {
  const actions = state.actions.actions;
  const placements = placementActions();
  if (state.summary.decision && state.summary.decision.kind === "reveal") {
    renderRevealPanel(box, actions);
    return;
  }
  if (!stagedTurn()) {
    /* What follows a placement (the graft partner, a card to trash, a space
       for a Spy) is a short list whose cards and spaces are lit on the
       table: a click there is the same as the button here (tableClick). */
    if (!placements.length && actions.some((action) => tableRefs(action).length)) {
      const hint = document.createElement("div");
      hint.className = "pick-hint muted";
      hint.textContent = "테이블에서 빛나는 카드나 칸을 눌러 골라도 됩니다.";
      box.appendChild(hint);
    }
    /* The flat list of an Agent turn is long: its way back to the steps
       goes on top, where the panel cannot push it under the log. */
    if (placements.length) box.appendChild(actionListToggle(false, actions.length));
    appendActionItems(box, actions);
    return;
  }
  const pick = state.pick || {};
  const steps = document.createElement("div");
  steps.className = "pick-steps";
  steps.appendChild(pickStepNode("①", "카드", pick.cardId, "cardId"));
  if (pick.partnerId) steps.appendChild(pickStepNode("＋", "함께", pick.partnerId, "partnerId"));
  steps.append(
    icon("arrow_right", "→"),
    pickStepNode("②", "보낼 칸", pick.spaceId, "spaceId")
  );
  box.appendChild(steps);

  const hint = document.createElement("div");
  hint.className = "pick-hint muted";
  const candidates = pickCandidates();
  if (pick.cardId && pick.spaceId) {
    hint.textContent = "③ 남은 선택을 고르세요.";
    box.appendChild(hint);
    for (const action of candidates) box.appendChild(placementOptionItem(action, candidates));
  } else {
    const hand = (state.view && state.view.private && state.view.private.hand) || [];
    const canJoin =
      pick.cardId && !pick.partnerId && hand.some((other) => canPair(pick.cardId, other));
    hint.textContent = pick.partnerId
      ? "두 카드로 갈 수 있는 칸이 빛납니다. 보낼 곳을 누르세요. (Esc: 취소)"
      : canJoin
        ? (isGraftCard(pick.cardId)
            ? "Graft 카드는 혼자 낼 수 없습니다. ＋ 표시된 카드를 눌러 함께 낼 카드를 고르거나, 칸을 먼저 눌러도 됩니다."
            : "빛나는 칸을 누르세요. Graft로 함께 낼 카드가 있으면 ＋ 표시된 카드를 먼저 누르세요. (Esc: 취소)")
        : pick.cardId
          ? "빛나는 칸 중에서 Agent를 보낼 곳을 누르세요. (Esc: 취소)"
          : pick.spaceId
            ? "빛나는 카드 중에서 그 칸에 낼 카드를 누르세요. (Esc: 취소)"
            : "손패에서 빛나는 카드를 누르세요. 칸을 먼저 눌러도 됩니다.";
    box.appendChild(hint);
  }

  const others = actions.filter((action) => action.action_id !== PLACEMENT_ACTION);
  if (others.length) {
    const heading = document.createElement("div");
    heading.className = "pick-others muted";
    heading.textContent = "또는";
    box.appendChild(heading);
    appendActionItems(box, others);
  }
  box.appendChild(actionListToggle(true, actions.length));
}

function actionListToggle(staged, count) {
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "action-list-toggle";
  toggle.textContent = staged ? `전체 행동 목록 보기 (${count}개)` : "단계별로 고르기";
  toggle.addEventListener("click", () => {
    if (staged) storageSet(FULL_LIST_KEY, "1");
    else storageRemove(FULL_LIST_KEY);
    state.pick = null;
    render();
  });
  return toggle;
}

/* The legal actions a table object takes part in. During a staged turn the
   placements are the ones that still fit the pick, so the cards and the
   spaces light up step by step. */
function legalActionsFor(ref) {
  if (!state.actions) return [];
  const staged = stagedTurn();
  return state.actions.actions.filter(
    (action) => actionRefs(action).includes(ref) && (!staged || matchesPick(action))
  );
}

/* Click on a table object: a step of the staged Agent turn, or else one
   legal action applies directly, several focus the action list, none shows
   the detail popover. */
function tableClick(ref, entry, anchor) {
  if (state.busy) return;
  if (stagedTurn() && pickStep(ref, entry, anchor)) return;
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
      '<span class="muted">사람 좌석이 없는 게임입니다. 최종 순위의 ' +
      '"AI 대국 다시 보기"로 처음부터 볼 수 있습니다.</span>';
    return;
  }
  if (state.catalog.board_image) {
    renderBoardStage(board, view);
    animatePlacedAgents(board, before);
  } else {
    renderSpaceList(board, view);
  }
}

/* A picture laid on the board scan at a box (percent of the stage). */
function boardPiece(src, box, className) {
  const [left, top, width, height] = box;
  const piece = document.createElement("img");
  piece.className = className;
  piece.src = src;
  piece.alt = "";
  piece.draggable = false;
  piece.style.left = `${left}%`;
  piece.style.top = `${top}%`;
  piece.style.width = `${width}%`;
  piece.style.height = `${height}%`;
  return piece;
}

/* Where the board prints the flag under a controllable space
   (catalog.tracks.control_flags, a percent box), if it does. */
function controlFlagBox(spaceId) {
  const flags = state.catalog.tracks && state.catalog.tracks.control_flags;
  return (flags && flags.boxes[spaceId]) || null;
}

/* A seat's Control marker: "place your Control marker on the flag below
   that space" [Main p. 20]. It is the printed pennant's own shape and size,
   flat in the seat's colour like every other player token. */
function controlMarker(seat, spaceId, box) {
  const svgNs = "http://www.w3.org/2000/svg";
  const [left, top, width, height] = box;
  const dip = 100 * (1 - state.catalog.tracks.control_flags.notch);
  const marker = document.createElementNS(svgNs, "svg");
  marker.setAttribute("class", "control-marker");
  marker.setAttribute("viewBox", "0 0 100 100");
  marker.setAttribute("preserveAspectRatio", "none");
  marker.dataset.seat = String(seat);
  marker.dataset.space = spaceId;
  marker.style.left = `${left}%`;
  marker.style.top = `${top}%`;
  marker.style.width = `${width}%`;
  marker.style.height = `${height}%`;
  const title = document.createElementNS(svgNs, "title");
  title.textContent = `Control: 좌석 ${seat} · ${nameOf(spaceId)}`;
  const pennant = document.createElementNS(svgNs, "polygon");
  pennant.setAttribute("points", `0,0 100,0 100,100 50,${dip} 0,100`);
  pennant.setAttribute("fill", SEAT_COLORS[seat]);
  marker.append(title, pennant);
  return marker;
}

/* The centre of the hexagon a Maker space prints for its bonus spice
   (catalog.tracks.maker_spice), if the layout has one for the space. */
function makerSpicePoint(spaceId) {
  const spots = state.catalog.tracks && state.catalog.tracks.maker_spice;
  return (spots && spots.points[spaceId]) || null;
}

/* The bonus spice waiting on a Maker space, "in the spot designated for
   bonus spice" [Main p. 15]: a spice hexagon exactly over the printed one,
   with the amount in it like the board's own spice numbers. */
function bonusSpiceToken(spaceId, count, point) {
  const [width, height] = state.catalog.tracks.maker_spice.size;
  const token = document.createElement("span");
  token.className = "bonus-spice";
  token.dataset.space = spaceId;
  token.title = `${nameOf(spaceId)} · bonus spice ${count}`;
  token.style.width = `${width}%`;
  token.style.height = `${height}%`;
  const amountText = document.createElement("span");
  amountText.className = "bonus-spice-count" + (count > 9 ? " wide" : "");
  amountText.textContent = String(count);
  token.appendChild(amountText);
  return placeAt(token, point[0], point[1]);
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

  /* Pieces that lie on the board, under the hotspots and the tokens. The
     Shield Wall token stays on its marked position until a player removes
     it [Main pp. 4, 10]; a Leader's tile in play and Immortality's overlay
     tile are pictures the scan does not have. */
  const wall = state.catalog.shield_wall;
  if (view.shield_wall_present && wall && wall.image) {
    const token = boardPiece(wall.image, wall.box, "shield-wall-token");
    token.alt = "Shield Wall";
    token.style.transform = `rotate(${wall.rotation}deg)`;
    stage.appendChild(token);
  }
  for (const entry of Object.values(state.catalog.spaces)) {
    if (!spaceInPlay(entry, view)) continue;
    const overlay = spaceOverlayFor(entry);
    if (overlay && overlay.image) {
      stage.appendChild(boardPiece(overlay.image, overlay.tile_box, "board-tile"));
    } else if (entry.tile_box && entry.image) {
      stage.appendChild(boardPiece(entry.image, entry.tile_box, "board-tile"));
    }
  }

  for (const [spaceId, entry] of Object.entries(state.catalog.spaces)) {
    if (!spaceInPlay(entry, view)) continue;
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
    if (state.pick && state.pick.spaceId === spaceId) hotspot.classList.add("picked");
    else if (pickAlternative(spaceId, "spaceId")) hotspot.classList.add("alternative");
    if (!spaceImplementedFor(entry)) hotspot.classList.add("unimplemented");
    const seats = occupants.get(spaceId) || [];
    if (seats.length) {
      const tokens = document.createElement("span");
      tokens.className = "agent-tokens";
      for (const seat of seats) tokens.appendChild(seatToken(seat, "agent-token"));
      hotspot.appendChild(tokens);
    }
    /* The Control marker and the bonus spice lie on their printed places
       (drawn below, outside the hotspot); a space the layout has no place
       for keeps the mark inside its hotspot. */
    if (controllers.has(spaceId) && !controlFlagBox(spaceId)) {
      const flag = seatToken(controllers.get(spaceId), "control-flag");
      flag.title = `Control: 좌석 ${controllers.get(spaceId)}`;
      hotspot.appendChild(flag);
    }
    if (makerSpice.get(spaceId) && !makerSpicePoint(spaceId)) {
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

  for (const [spaceId, seat] of controllers) {
    const box = controlFlagBox(spaceId);
    if (box) stage.appendChild(controlMarker(seat, spaceId, box));
  }
  for (const [spaceId, count] of makerSpice) {
    const point = makerSpicePoint(spaceId);
    if (count && point) stage.appendChild(bonusSpiceToken(spaceId, count, point));
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

/* The printed cell a strength is shown on: 0 is the framed square, and a
   strength beyond 20 counts on from 1 on the token's "+20" face [Main
   p. 12]. The token has that one flip, so 41 and up stay on 20. */
function strengthCell(strength) {
  if (strength <= 0) return 0;
  return Math.min(strength > 20 ? strength - 20 : strength, 20);
}

/* A seat's pictured Combat marker: one face of the owner's token picture,
   sized as a percent of the stage so it keeps to its cell at any zoom. */
function strengthPicture(seat, src, size) {
  const token = document.createElement("span");
  token.className = "strength-token pictured";
  token.dataset.seat = String(seat);
  token.style.width = `${size}%`;
  token.style.borderColor = SEAT_COLORS[seat];
  const face = document.createElement("img");
  face.src = src;
  face.alt = "";
  face.draggable = false;
  token.appendChild(face);
  return token;
}

/* The player disc: the one common round token in a seat's colour — the
   Score marker and the Councilor token on the board, the research and
   Tleilaxu track tokens on the Bene Tleilax board. Flat colour, no seat
   number. `size` is its diameter as a percent of the stage it lies on
   (the diameter of the spot that board prints for it); without a size it
   is an inline disc for the text layouts. */
function seatDisc(seat, className, size) {
  const disc = document.createElement("span");
  disc.className = `seat-disc ${className}`;
  disc.dataset.seat = String(seat);
  if (size !== undefined) disc.style.width = `${size}%`;
  disc.style.backgroundColor = SEAT_COLORS[seat];
  return disc;
}

/* The cell of the Score track a score is shown on: its printed number, or
   one shared place on the emblem above the last number for anything higher. */
function scoreLevel(vp, tracks) {
  return Math.max(0, Math.min(vp, tracks.victory_points.levels.length));
}

/* Half the distance between two discs of `size` that share `room`: side by
   side with a hair between them when the room allows it, overlapping just
   enough to stay inside it when it does not. */
function discHalfGap(size, room) {
  return Math.max(0, Math.min(size / 2 + 0.05, (room - size) / 2));
}

/* Offsets that lay `count` discs around a point: alone on the point, a pair
   side by side, a triangle, a 2×2 (a fifth disc and on would reuse the
   places). `fromTop` keeps the first row on the point and puts the second
   row under it, for spots where a lone disc must leave the print below it
   readable; `upright` stands a pair one above the other, for room too
   narrow to show two discs side by side. */
function discCluster(count, halfX, halfY, { fromTop = false, upright = false } = {}) {
  let places;
  if (count <= 1) places = [[0, 0]];
  else if (count === 2) places = upright ? [[0, -halfY], [0, halfY]] : [[-halfX, 0], [halfX, 0]];
  else if (count === 3) places = [[-halfX, -halfY], [halfX, -halfY], [0, halfY]];
  else places = [[-halfX, -halfY], [halfX, -halfY], [-halfX, halfY], [halfX, halfY]];
  const twoRows = count >= 3 || (count === 2 && upright);
  const lift = fromTop && twoRows ? halfY : 0;
  return Array.from({ length: Math.max(count, 1) }, (_, index) => {
    const [dx, dy] = places[index % places.length];
    return [dx, dy + lift];
  });
}

/* A Faction's Alliance token: its picture (catalog.alliance_tokens) cut to
   the round token, or a drawn disc with the Faction's emblem without the
   owner's token pictures. With a `size` (percent of the stage) it lies on
   the board; without one it is an inline token for the seat panels. */
function allianceToken(key, size, holder) {
  const token = document.createElement("span");
  token.className = "alliance-token";
  token.dataset.faction = key;
  token.dataset.holder = holder === undefined ? "" : String(holder);
  token.title = `${FACTION_LABELS[key]} Alliance`;
  if (size !== undefined) token.style.width = `${size}%`;
  else token.classList.add("inline");
  const url = (state.catalog.alliance_tokens || {})[key];
  if (url) {
    const face = document.createElement("img");
    face.src = url;
    face.alt = "";
    face.draggable = false;
    token.appendChild(face);
  } else {
    token.classList.add("drawn");
    token.appendChild(icon(`influence_${key}`, `${FACTION_LABELS[key]} Alliance`));
  }
  return token;
}

/* Where each Faction's Alliance token is on the screen and who holds it
   ("" on the board), so a render can tell a token that changed hands. */
function allianceTokenPlaces() {
  const places = new Map();
  for (const token of document.querySelectorAll(".alliance-token:not(.flying)")) {
    const rect = token.getBoundingClientRect();
    if (rect.width) places.set(token.dataset.faction, { holder: token.dataset.holder, rect });
  }
  return places;
}

/* An Alliance token that changed hands — earned from the board, taken over
   by a seat that passed its holder, or returned [Main p. 7] [FAQ p. 1] —
   flies from where it lay to where it lies now. The flight is a copy above
   the page (the seat panels scroll and would clip the token itself). */
function animateMovedAllianceTokens(before) {
  if (!before.size) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  for (const token of document.querySelectorAll(".alliance-token:not(.flying)")) {
    const was = before.get(token.dataset.faction);
    const to = token.getBoundingClientRect();
    if (!was || was.holder === token.dataset.holder || !to.width) continue;
    const ghost = token.cloneNode(true);
    ghost.classList.remove("inline");
    ghost.classList.add("flying");
    const lay = (rect) => {
      ghost.style.left = `${rect.left}px`;
      ghost.style.top = `${rect.top}px`;
      ghost.style.width = `${rect.width}px`;
    };
    lay(was.rect);
    document.body.appendChild(ghost);
    token.style.visibility = "hidden";
    ghost.getBoundingClientRect();
    ghost.classList.add("moving");
    lay(to);
    const land = () => {
      ghost.remove();
      token.style.visibility = "";
    };
    ghost.addEventListener("transitionend", land, { once: true });
    setTimeout(land, 1200);
  }
}

/* A seat's Maker Hooks token in the slot its garrison prints for it: "Place
   it on your garrison" [Main p. 20]. The picture is turned (and mirrored)
   into the slot, so its long side lies along the slot's height; without the
   picture the rulebook icon marks the slot. */
function makerHooksToken(seat, layout) {
  const [x, y] = layout.points[seat] || layout.points[0];
  const [width, height] = layout.size;
  const url = state.catalog.maker_hooks_token;
  let token;
  if (url) {
    const turn = layout.turns[seat] || layout.turns[0];
    token = document.createElement("img");
    token.className = "maker-hooks-token";
    token.src = url;
    token.alt = "Maker Hooks";
    token.draggable = false;
    token.style.width = `${height}%`;
    token.style.transform =
      `translate(-50%, -50%) rotate(${turn.rotation}deg)` + (turn.mirrored ? " scaleX(-1)" : "");
  } else {
    token = document.createElement("span");
    token.className = "maker-hooks-token drawn";
    token.style.width = `${width}%`;
    token.style.height = `${height}%`;
    token.appendChild(icon("maker_hooks", "Maker Hooks"));
  }
  token.dataset.seat = String(seat);
  token.title = `좌석 ${seat} · Maker Hooks`;
  return placeAt(token, x, y);
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
  /* The seats on each cell of the combat track and of the Score track, in
     seat order. */
  const strengthStacks = new Map();
  const scoreStacks = new Map();
  view.players.forEach((player, index) => {
    const seat = typeof player.player_id === "number" ? player.player_id : index;
    const shown = strengthCell(player.combat_strength || 0);
    if (!strengthStacks.has(shown)) strengthStacks.set(shown, []);
    strengthStacks.get(shown).push(seat);
    const level = scoreLevel(player.victory_points || 0, tracks);
    if (!scoreStacks.has(level)) scoreStacks.set(level, []);
    scoreStacks.get(level).push(seat);
  });
  /* An Alliance token lies on the marked ring of its Faction's strip until a
     player earns it and takes it into their supply [Main pp. 4, 7] (it then
     shows on that seat's panel); the vacated ring takes the holder's colour. */
  for (const key of factions) {
    const offset = tracks.influence.offsets[key];
    if (offset === undefined) continue;
    const [ax, ay] = tracks.influence.alliance;
    const size = tracks.influence.alliance_size;
    const holder = view.players.find((p) => (p.alliance_faction_ids || []).includes(key));
    if (holder) {
      const ring = document.createElement("span");
      ring.className = "alliance-ring";
      ring.dataset.faction = key;
      if (size !== undefined) ring.style.width = `${size}%`;
      ring.style.borderColor = SEAT_COLORS[holder.player];
      ring.title = `좌석 ${holder.player} · ${FACTION_LABELS[key]} Alliance`;
      stage.appendChild(placeAt(ring, ax, ay + offset));
    } else {
      stage.appendChild(placeAt(allianceToken(key, size), ax, ay + offset));
    }
  }

  view.players.forEach((player, index) => {
    const seat = typeof player.player_id === "number" ? player.player_id : index;
    const color = SEAT_COLORS[seat];

    for (const key of factions) {
      const offset = tracks.influence.offsets[key];
      if (offset === undefined) continue;
      const level = Math.max(0, Math.min(6, player.influence[key] || 0));
      /* The cube is exactly the square the strip prints for it (its
         width is a percent of the stage, like the player disc). */
      const cube = document.createElement("span");
      cube.className = "track-cube";
      cube.style.width = `${tracks.influence.cube_size}%`;
      cube.style.background = color;
      cube.title = `좌석 ${seat} · ${FACTION_LABELS[key]} Influence ${player.influence[key]}`;
      placeAt(cube, tracks.influence.seat_x[seat], tracks.influence.levels[level] + offset);
      stage.appendChild(cube);
    }

    /* A Score marker alone on its score lies on the centre of the cell, so
       its height reads as the score. The disc is as large as on the table
       (a cell holds one), so seats that share a score cluster around that
       centre and overlap just enough to stay inside the cell. */
    const vp = player.victory_points || 0;
    const vpToken = seatDisc(seat, "vp-token", tracks.disc_size);
    vpToken.title = `좌석 ${seat} · ${vp} VP`;
    const level = scoreLevel(vp, tracks);
    const vpY = level < tracks.victory_points.levels.length
      ? tracks.victory_points.levels[level]
      : tracks.victory_points.overflow_y;
    const together = scoreStacks.get(level);
    const [cellWidth, cellHeight] = tracks.victory_points.cell;
    const [vpDx, vpDy] = discCluster(
      together.length,
      discHalfGap(tracks.disc_size, cellWidth),
      discHalfGap(tracks.disc_size, cellHeight),
    )[together.indexOf(seat)];
    placeAt(vpToken, tracks.victory_points.x + vpDx, vpY + vpDy);
    stage.appendChild(vpToken);

    const units =
      (player.troops_conflict || 0) +
      (player.sandworms_conflict || 0) +
      (player.commanders_conflict || 0) +
      (player.agent_in_conflict || 0);
    /* Every seat's strength token is always on the track: in the framed
       square left of 1/11 at strength 0 (four tokens in a 2×2), on the
       printed number otherwise, and on its "+20" face beyond 20 (23 is
       the token on 3 showing +20). With the owner's token pictures
       (catalog.strength_tokens) it is the picture of that face, lying in
       the open part of its cell like the marker on the table, and seats
       that share a cell fan out so that every colour stays in sight. */
    const strength = player.combat_strength || 0;
    const flipped = strength > 20;
    const shown = strengthCell(strength);
    const faces = (state.catalog.strength_tokens || [])[seat];
    const token = faces
      ? strengthPicture(seat, flipped ? faces.plus20 : faces.front, tracks.strength.token_size)
      : seatToken(seat, "track-token strength-token");
    token.title = `좌석 ${seat} · 전투력 ${strength}`;
    if (shown === 0) {
      const [zx, zy, zw, zh] = tracks.strength.zero_box;
      const inset = faces ? 0.25 : 0.3;
      placeAt(
        token,
        zx + zw * (inset + (seat % 2) * (1 - 2 * inset)),
        zy + zh * (inset + Math.floor(seat / 2) * (1 - 2 * inset)),
      );
    } else {
      const row = shown > 10 ? 1 : 0;
      const cell = shown > 10 ? shown - 10 : shown;
      if (faces) {
        /* The fan may lap about half a percent over each neighbour (a
           cell is 3.75 wide, the widest fan 4.95), which keeps a strip of
           every tied colour visible at the size of a 3% token. */
        const sharing = strengthStacks.get(shown);
        const step = sharing.length > 1 ? Math.min(1.1, 1.95 / (sharing.length - 1)) : 0;
        const shift = (sharing.indexOf(seat) - (sharing.length - 1) / 2) * step;
        placeAt(token, tracks.strength.cells[cell] + shift, tracks.strength.token_rows[row] - shift * 0.35);
      } else {
        if (flipped) {
          token.classList.add("flipped");
          const plus = document.createElement("span");
          plus.className = "strength-plus";
          plus.textContent = "+20";
          token.appendChild(plus);
        }
        placeAt(token, tracks.strength.cells[cell] + (seat - 1.5) * 0.9, tracks.strength.rows[row]);
      }
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
    if (player.maker_hooks && tracks.maker_hooks) {
      stage.appendChild(makerHooksToken(seat, tracks.maker_hooks));
    }

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

    /* The seat to move sends and takes back its units right here: the same
       count rows as in the panel, by the seat's quadrant (above the upper
       seats, under the lower ones, clear of the units chip). */
    if (seat === state.viewSeat && !state.review && state.actions) {
      const families = countFamilies(state.actions.actions);
      const rows = [...families.entries()].filter(([id]) => FORCE_STEPPER_ACTIONS.has(id));
      if (rows.length) {
        const [sx, sy] = tracks.conflict_quadrants[seat] || tracks.conflict_quadrants[0];
        const control = document.createElement("div");
        control.className = "force-stepper";
        control.style.borderColor = color;
        for (const [id, family] of rows) control.appendChild(countRow(id, family, true));
        placeAt(control, sx, sy + (sy > 77 ? 4.6 : -4.6));
        stage.appendChild(control);
      }
    }

    if (player.high_council && councilSlot < tracks.council_seats.length) {
      const [cx, cy] = tracks.council_seats[councilSlot];
      councilSlot += 1;
      const token = seatDisc(seat, "council-token", tracks.disc_size);
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
      (spaceId) =>
        catalog.spaces[spaceId].agent_icon === iconId &&
        spaceInPlay(catalog.spaces[spaceId], view)
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
  if (state.pick && state.pick.spaceId === spaceId) row.classList.add("picked");
  row.dataset.space = spaceId;

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
  if (state.pick && (state.pick.cardId === instanceId || state.pick.partnerId === instanceId)) {
    card.classList.add("picked");
  } else if (partnerCandidate(instanceId)) {
    card.classList.add("partner");
  } else if (pickAlternative(instanceId, "cardId")) {
    card.classList.add("alternative");
  }
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
  renderIntriguePiles(market, view);
}

/* The public Intrigue piles as one line: the cards themselves only matter
   when somebody wants to look back, so a click lists them (newest first) —
   the face-up discard pile beside the deck [Main p. 7] and the Intrigue
   cards trashed out of the game [Main p. 20]. */
function renderIntriguePiles(market, view) {
  const discard = view.intrigue_discard || [];
  const trash = view.intrigue_trash || [];
  if (!discard.length && !trash.length) return;
  const box = document.createElement("div");
  box.className = "strip";
  const pile = document.createElement("button");
  pile.type = "button";
  pile.className = "pile-button";
  pile.dataset.pile = "intrigue";
  pile.append(icon("intrigue", "Intrigue"), ` Intrigue discard ${discard.length}장`);
  if (trash.length) pile.append(` · trash ${trash.length}장`);
  pile.title = "지금까지 쓰인 Intrigue 카드 보기";
  pile.addEventListener("click", (event) => {
    event.stopPropagation();
    openPileList(
      [
        ["Intrigue discard", [...discard].reverse()],
        ["Intrigue trash", [...trash].reverse()],
      ],
      null,
      pile
    );
  });
  box.appendChild(pile);
  market.appendChild(box);
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
  trash_intrigue_for_card_and_intrigue: "Intrigue trash → card + Intrigue",
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
  if (layout.image) {
    /* The owner's scan with the live tokens drawn over it
       (catalog.bene_tleilax.layout, percent of the image). */
    box.appendChild(renderBeneTleilaxScan(layout, view));
    market.appendChild(box);
    return;
  }

  /* Without a scan: the 22 hexes as a column/row grid; each seat's
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
    for (const seat of tokensBySpace[space.id] || []) tokens.appendChild(seatDisc(seat, "rtoken"));
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
      if ((player.tleilaxu_space || 0) === index) tokens.appendChild(seatDisc(player.player, "rtoken"));
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

function renderBeneTleilaxScan(layout, view) {
  const stage = document.createElement("div");
  stage.className = "bt-stage";
  const map = document.createElement("img");
  map.className = "bt-map";
  map.src = layout.image;
  map.alt = "Bene Tleilax board";
  map.draggable = false;
  stage.appendChild(map);
  const overlay = layout.layout;
  const [hexWidth, hexHeight] = overlay.hex_size;
  /* The common player disc at the size of this board's printed spots; y
     values are percents of the height, hence the taller figure. */
  const discWidth = overlay.disc_size;
  const discHeight = overlay.disc_size * overlay.aspect;

  /* Research hexes: a titled hotspot per space and the seats' tokens in
     its dark upper half, above the printed bonus. */
  const tokensBySpace = {};
  for (const player of view.players) {
    if (!player.research_space) continue;
    (tokensBySpace[player.research_space] ||= []).push(player.player);
  }
  const bonusOf = {};
  for (const space of layout.research_spaces) bonusOf[space.id] = space.bonus;
  for (const [spaceId, [x, y]] of Object.entries(overlay.research_points)) {
    const hex = document.createElement("div");
    hex.className = "bt-hex";
    hex.style.left = `${x - hexWidth / 2}%`;
    hex.style.top = `${y - hexHeight / 2}%`;
    hex.style.width = `${hexWidth}%`;
    hex.style.height = `${hexHeight}%`;
    hex.title =
      spaceId === layout.research_start
        ? "Research 시작"
        : `${spaceId} · ${RESEARCH_BONUS_LABELS[bonusOf[spaceId]] || "보너스 없음"}`;
    stage.appendChild(hex);
    /* The start piece prints a spot per disc (the fourth seat continues
       the column); elsewhere the discs lie in the hex's dark upper half
       and a second row, if three or more meet, goes over the bonus. */
    const seats = tokensBySpace[spaceId] || [];
    const places = discCluster(
      seats.length,
      discHalfGap(discWidth, hexWidth - 1),
      (discHeight + 0.1) / 2,
      { fromTop: true },
    );
    seats.forEach((seat, index) => {
      const token = seatDisc(seat, "bt-token", discWidth);
      if (spaceId === layout.research_start) {
        const [sx, sy] = overlay.research_start_discs[seat % overlay.research_start_discs.length];
        placeAt(token, sx, sy);
      } else {
        placeAt(token, x + places[index][0], y - hexHeight / 4 + places[index][1]);
      }
      stage.appendChild(token);
    });
  }

  /* Tleilaxu track: tokens along the top band, the bank's spice on the
     fourth space until a token first arrives [Immortality p. 4]. */
  const [bandTop, bandHeight] = overlay.track_band;
  overlay.track_cells.forEach(([left, width], index) => {
    const cell = document.createElement("div");
    cell.className = "bt-track-cell";
    cell.style.left = `${left}%`;
    cell.style.top = `${bandTop}%`;
    cell.style.width = `${width}%`;
    cell.style.height = `${bandHeight}%`;
    const bonus = layout.tleilaxu_track[index];
    cell.title = `Tleilaxu track ${index}${TLEILAXU_TRACK_LABELS[bonus] ? " · " + TLEILAXU_TRACK_LABELS[bonus] : ""}`;
    stage.appendChild(cell);
    /* The first space prints a spot per disc. The other spaces take the
       same two rows: the upper one first, which leaves the printed bonus
       in sight, and a pair stands upright where a space is too narrow. */
    const seats = view.players.filter((p) => (p.tleilaxu_space || 0) === index);
    const [rowTop, rowBottom] = [overlay.track_start_discs[0][1], overlay.track_start_discs[2][1]];
    const halfX = discHalfGap(discWidth, width - 0.4);
    const places = discCluster(seats.length, halfX, (rowBottom - rowTop) / 2, {
      fromTop: true,
      upright: halfX < discWidth * 0.3,
    });
    seats.forEach((player, slot) => {
      const token = seatDisc(player.player, "bt-token", discWidth);
      if (index === 0) {
        const [sx, sy] = overlay.track_start_discs[player.player % overlay.track_start_discs.length];
        placeAt(token, sx, sy);
      } else {
        placeAt(token, left + width / 2 + places[slot][0], rowTop + places[slot][1]);
      }
      stage.appendChild(token);
    });
  });
  if (view.tleilaxu_track_spice) {
    const spice = document.createElement("span");
    spice.className = "bt-spice";
    spice.append(icon("spice", "spice"), String(view.tleilaxu_track_spice));
    spice.title = "첫 도달자가 가져가는 spice";
    placeAt(spice, overlay.spice_point[0], overlay.spice_point[1]);
    stage.appendChild(spice);
  }
  return stage;
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
      const mine = isRemote() ? mySeats().includes(seat) : seat === activeSeat();
      badge.textContent = mine
        ? isRemote() && playerInfo(seat).name
          ? `YOU · ${playerInfo(seat).name}`
          : "YOU"
        : playerName(seat);
      who.appendChild(badge);
      if (isRemote() && playerInfo(seat).claimed) {
        who.appendChild(presenceDot(playerInfo(seat)));
      }
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
        /* The Alliance token is in this seat's supply [Main p. 7]. */
        stat.classList.add("alliance");
        stat.title += " · Alliance";
        stat.appendChild(allianceToken(key, undefined, seat));
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

/* A pile listing (discard, Intrigue piles) in the popover: one pile as
   `(title, ids, anchor)`, or several as `([[title, ids], ...], null, anchor)`
   (empty piles are left out). */
function openPileList(title, ids, anchor) {
  const piles = Array.isArray(title) ? title : [[title, ids]];
  const pop = el("card-popover");
  pop.textContent = "";
  for (const [pileTitle, pileIds] of piles) {
    if (!pileIds.length && piles.length > 1) continue;
    const head = document.createElement("div");
    head.className = "popover-title";
    head.textContent = `${pileTitle} (${pileIds.length})`;
    pop.appendChild(head);
    const row = document.createElement("div");
    row.className = "strip-cards wrap";
    for (const id of pileIds) row.appendChild(visualCard(id, { className: "small" }));
    pop.appendChild(row);
  }
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
    /* Every id-shaped field resolves through the catalog. The engine emits
       about 35 distinct ones (card_id, leader_id, tech_id, contract_id,
       skill_id, post_id, space_id, their first_/second_ variants…) and the
       old allowlist named only five, so the rest printed raw engine ids —
       leader_ids is the first log line of every Leader-draft game. */
    const isIdField = key.endsWith("_id");
    const isIdList = key.endsWith("_ids") && Array.isArray(value);
    /* Combat rewards and the like list every field; zeros say nothing. */
    if (value === 0 || value === "" || value === null || value === false) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    /* action_id has its own Korean table; everything else is a catalog name. */
    const resolve = (item) =>
      key === "action_id" ? ACTION_LABELS[item] || prettify(item) : nameOf(item);
    const shown = isIdList
      ? value.map(resolve).join(", ")
      : isIdField
        ? resolve(value)
        : String(value);
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
        : playerName(group.actor)
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
  /* In review the log follows the cursor (reviewLog) and leaves the live
     table's own bookkeeping of what is fresh alone. */
  const log = state.review ? reviewLog(state.review) : state.log;
  if (!log || !log.entries.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  let freshFrom = log.freshFrom;
  if (!state.review) {
    if (logSeen.gameId !== state.gameId) {
      logSeen = { gameId: state.gameId, count: log.count, freshFrom: log.count };
    } else if (log.count !== logSeen.count) {
      logSeen.freshFrom = logSeen.count;
      logSeen.count = log.count;
    }
    freshFrom = logSeen.freshFrom;
  }

  const heading = document.createElement("h2");
  heading.textContent = "행동 로그";
  panel.appendChild(heading);
  const list = document.createElement("div");
  list.className = "log-list";
  for (const group of logGroups(log.entries)) {
    if (group.kind === "undo") list.appendChild(undoRow(group.entry));
    else if (group.kind === "neutral") list.appendChild(neutralCard(group, freshFrom));
    else list.appendChild(turnCard(group, freshFrom));
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
  /* A review can look from a seat this browser never played (an AI's, or
     any seat of a game nobody sat at): that hand is not "mine". */
  const mine = !state.review || mySeats().includes(activeSeat());
  const title = document.createElement("strong");
  title.textContent = mine
    ? `내 손패 · 좌석 ${activeSeat()}`
    : `${playerLabel(activeSeat())}의 손패`;
  label.appendChild(title);
  const revealNow = revealTurnPreview();
  if (revealNow) {
    /* Beside the hand while the seat may still choose between an Agent turn
       and a Reveal turn: what this hand is worth revealed right now. */
    const note = document.createElement("span");
    note.className = "hand-reveal-note";
    note.append("지금 공개하면 ", revealPreview(revealNow));
    label.appendChild(note);
  }
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
    if (own.discard_pile.length) {
      openPileList(mine ? "내 discard" : `좌석 ${activeSeat()} discard`, own.discard_pile, counts);
    }
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
  const review = state.review;
  /* A review hides the result it is walking towards; a watched game (nobody
     sat at it, so nobody has seen it) shows it on reaching the end. */
  const reached =
    review && spectatorOnly() && review.cursor >= review.meta.step_count;
  if ((review && !reached) || !summary.finished || !summary.standings) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  panel.textContent = "";
  const heading = document.createElement("h2");
  heading.textContent = "최종 순위";
  panel.appendChild(heading);
  /* Cells are text nodes: a row carries a player's name, and a name is
     somebody else's input. */
  const table = document.createElement("table");
  const tableRow = (tag, cells) => {
    const row = document.createElement("tr");
    for (const text of cells) {
      const cell = document.createElement(tag);
      cell.textContent = String(text);
      row.appendChild(cell);
    }
    table.appendChild(row);
    return row;
  };
  tableRow("th", ["순위", "좌석", "VP", "Spice", "Solari", "Water", "Garrison"]);
  for (const entry of summary.standings) {
    const row = tableRow("td", [
      entry.rank,
      playerLabel(entry.player),
      entry.victory_points,
      entry.spice,
      entry.solari,
      entry.water,
      entry.troops_garrison,
    ]);
    if (entry.rank === 1) row.className = "winner";
  }
  panel.appendChild(table);

  const humans = humanSeats();
  const open = document.createElement("button");
  if (!humans.length) {
    /* While the watched game is on screen, its play button starts it over. */
    if (review) return;
    open.textContent = "AI 대국 다시 보기";
    open.addEventListener("click", watchGame);
  } else {
    open.textContent = "리플레이 검토";
    open.addEventListener("click", () => {
      const seat = humans.includes(state.viewSeat)
        ? state.viewSeat
        : mySeats().length
          ? mySeats()[0]
          : humans[0];
      enterReview(seat).catch((error) => {
        el("game-error").textContent = `검토 시작 실패 (${error.message})`;
        el("game-error").hidden = false;
      });
    });
  }
  panel.appendChild(open);
}

/* The host's link is `#admin=<key>`: trade the key for an HttpOnly cookie
   and take it out of the address bar at once. */
async function adoptAdminLink() {
  const key = hashParams().get("admin");
  if (!key) return null;
  setRoomHash(null);
  try {
    await api("/auth/admin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    return null;
  } catch (error) {
    return `관리자 링크가 맞지 않습니다 (${error.message})`;
  }
}

async function init() {
  state.catalog = await api("/catalog");
  const adminError = await adoptAdminLink();
  state.server = await api("/whoami");
  /* The host of a remote game plays too and must not know the seed. */
  el("opt-seed-row").hidden = isRemote();
  buildSeatSelects();
  document.addEventListener("click", (event) => {
    const pop = el("card-popover");
    if (!pop.hidden && !pop.contains(event.target)) closePopover();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (state.pick) clearPick();
    else closePopover();
  });
  el("setup-form").addEventListener("submit", createGame);
  el("leave-game").addEventListener("click", () => leaveGame());
  el("open-lobby").addEventListener("click", () => showLobby());
  el("lobby-enter").addEventListener("click", () => enterTable(state.summary));
  el("host-panel").addEventListener("toggle", () => {
    /* The host opened the panel: show what is on disk for this game. */
    if (el("host-panel").open) loadHostSaves().catch(() => {});
  });
  el("landing-resume-button").addEventListener("click", () => {
    const last = roomId(storageGet("dune.lastGame"));
    if (last) openGame(last).catch(() => {});
  });
  window.addEventListener("hashchange", () => {
    const wanted = roomFromHash();
    if (wanted && wanted !== state.gameId) openGame(wanted).catch(() => {});
  });
  el("save-game").addEventListener("click", () => {
    saveGame().catch(() => {});
  });
  el("review-exit").addEventListener("click", exitReview);
  el("review-first").addEventListener("click", () => reviewSeek(0));
  el("review-last").addEventListener("click", () => {
    if (state.review) reviewSeek(state.review.meta.step_count);
  });
  el("review-prev").addEventListener("click", () =>
    reviewStep(() => reviewGoto(state.review.cursor - 1).catch(() => {}))
  );
  el("review-next").addEventListener("click", () =>
    reviewStep(() => reviewGoto(state.review.cursor + 1).catch(() => {}))
  );
  el("review-prev-own").addEventListener("click", () =>
    reviewStep(() => reviewJumpOwn(-1))
  );
  el("review-next-own").addEventListener("click", () =>
    reviewStep(() => reviewJumpOwn(1))
  );
  el("review-slider").addEventListener("change", (event) =>
    reviewSeek(Number(event.target.value))
  );
  el("review-seat").addEventListener("change", (event) => {
    if (!state.review) return;
    /* Another seat's eyes on the same position; playback carries on. */
    const play = playback.playing;
    stopPlayback();
    enterReview(Number(event.target.value), {
      cursor: state.review.cursor,
      play,
    }).catch(() => {});
  });
  el("review-play").addEventListener("click", () => {
    if (playback.playing) stopPlayback();
    else startPlayback(0);
  });
  el("review-unit").addEventListener("change", (event) => {
    playback.unit = event.target.value === "step" ? "step" : "turn";
  });
  el("review-interval").addEventListener("change", (event) => {
    playback.intervalMs = Number(event.target.value) || 1000;
    if (playback.playing) schedulePlayback(playback.intervalMs);
  });
  const room = roomFromHash();
  if (room) await openGame(room);
  else await showHome(adminError);
}

init().catch((error) => {
  el("setup-error").textContent = `초기화 실패 (${error.message})`;
  el("setup-error").hidden = false;
});
