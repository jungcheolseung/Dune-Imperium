"use strict";

/* Minimal text-card UI over the local play API. Every game fact rendered
   here comes from the server's PlayerView / summary / catalog payloads;
   the client keeps no rules knowledge of its own. */

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
};

let noteTimer = 0;

const SEAT_KINDS = [
  ["human", "사람"],
  ["heuristic", "휴리스틱 AI"],
  ["random", "랜덤 AI"],
];

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
  complete_contract: "Contract 완료",
  decline_agent_card_acquisition: "획득 안 함",
  decline_agent_card_discard: "Discard 안 함",
  decline_agent_card_intrigue_payment: "지불 안 함",
  decline_agent_card_payment: "지불 안 함",
  decline_agent_card_trash: "Trash 안 함",
  decline_combat_reward: "보상 비용 지불 안 함",
  decline_combat_reward_trash: "Trash 안 함",
  decline_control_defense: "방어 배치 안 함",
  decline_corrinth_city_payment: "지불 안 함",
  decline_gather_intelligence: "Gather Intelligence 안 함",
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
  recall_agent_for_agent_card: "Agent 회수",
  recall_agent_for_contract: "Agent 회수",
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
  resolve_espionage_place_spy: "Spy 배치 (Espionage)",
  resolve_espionage_without_spy: "Spy 없이 해결",
  resolve_faction_influence: "Faction Influence 해결",
  retreat_intrigue_troops: "병력 후퇴",
  retreat_leader_troop: "Troop 후퇴",
  retreat_two_troops_for_reveal: "Troop 2 후퇴 → 검 4",
  reveal_turn: "Reveal 턴 시작",
  summon_maker_sandworms: "Sandworm 소환",
  take_contract: "Contract 획득",
  take_high_council_from_reveal: "High Council 획득",
  take_sietch_tabr_supplies: "Sietch Tabr 보급 (Maker Hooks)",
  take_sietch_tabr_water: "Sietch Tabr water",
  take_sietch_tabr_water_and_destroy_wall: "Water + Shield Wall 파괴",
  trash_agent_card: "카드 trash",
  trash_combat_reward_card: "카드 trash (Combat 보상)",
  trash_contract_reveal_for_vp: "이 카드 trash → VP",
  trash_intrigue_card: "Intrigue trash",
  trash_leader_card: "카드 trash (Leader)",
  trash_reveal_card: "카드 trash",
  use_other_memories: "Other Memories 사용",
};

const RESOURCE_ICONS = { solari: "🪙", spice: "🌶", water: "💧" };

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
  const shared = value.match(/^(?:imperium|reserve|intrigue):(.+):\d+$/);
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
    if (card.persuasion) bits.push(`🗣${card.persuasion}`);
    if (card.swords) bits.push(`⚔${card.swords}`);
    if (card.factions.length) {
      bits.push(card.factions.map((f) => FACTION_LABELS[f] || f).join("/"));
    }
    return bits.join(" · ");
  }
  const intrigue = state.catalog && state.catalog.intrigue[id];
  if (intrigue) return `Intrigue (${intrigue.timings.join("/")})`;
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
      openPopover(entry, span);
    });
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

function costText(cost) {
  const parts = [];
  for (const resource of ["solari", "spice", "water"]) {
    if (cost[resource]) parts.push(`${cost[resource]}${RESOURCE_ICONS[resource]}`);
  }
  return parts.length ? parts.join(" ") : "무료";
}

function requirementText(requirement) {
  const label = FACTION_LABELS[requirement.faction] || requirement.faction;
  return `요구: ${label} Influence ${requirement.amount}+`;
}

function popoverLines(entry) {
  const lines = [];
  if (entry.text) lines.push(...entry.text);
  if (entry.condition) lines.push(`조건: ${entry.condition}`);
  if (entry.reward) lines.push(`보상: ${entry.reward}`);
  if (entry.rewards) lines.push(...entry.rewards);
  if (entry.options) {
    if (entry.requirement) lines.push(requirementText(entry.requirement));
    for (const option of spaceOptionsFor(entry)) {
      lines.push(`[${costText(option.cost)}] ${option.effect}`);
    }
  }
  if (entry.ability_text) lines.push(`${entry.ability}: ${entry.ability_text}`);
  if (entry.signet_text) {
    lines.push(`Signet — ${entry.signet}: ${entry.signet_text}`);
  }
  if (entry.notes) lines.push(...entry.notes);
  return lines;
}

function openPopover(entry, anchor) {
  const pop = el("card-popover");
  pop.textContent = "";

  const title = document.createElement("div");
  title.className = "popover-title";
  title.textContent = entry.name;
  pop.appendChild(title);

  const meta = [];
  if (entry.cost !== undefined && entry.cost !== null) {
    meta.push(`비용 ${entry.cost}`);
  }
  if (entry.persuasion) meta.push(`🗣${entry.persuasion}`);
  if (entry.swords) meta.push(`⚔${entry.swords}`);
  if (entry.factions && entry.factions.length) {
    meta.push(entry.factions.map((f) => FACTION_LABELS[f] || f).join("/"));
  }
  if (entry.timings) meta.push(`Intrigue (${entry.timings.join("/")})`);
  if (entry.tier !== undefined) meta.push(`Conflict tier ${entry.tier}`);
  if (entry.options && !spaceImplementedFor(entry)) meta.push("미구현 · 배치 불가");
  if (meta.length) {
    const line = document.createElement("div");
    line.className = "meta";
    line.textContent = meta.join(" · ");
    pop.appendChild(line);
  }

  for (const text of popoverLines(entry)) {
    const line = document.createElement("div");
    line.className = "popover-line";
    line.textContent = text;
    pop.appendChild(line);
  }
  if (entry.image) {
    const image = document.createElement("img");
    image.loading = "lazy";
    image.src = entry.image;
    image.alt = entry.name;
    pop.appendChild(image);
  }

  pop.hidden = false;
  const rect = anchor.getBoundingClientRect();
  const width = Math.min(340, window.innerWidth - 16);
  pop.style.width = `${width}px`;
  const maxLeft = window.scrollX + window.innerWidth - width - 8;
  const left = Math.min(rect.left + window.scrollX, Math.max(window.scrollX + 8, maxLeft));
  pop.style.left = `${left}px`;
  pop.style.top = `${rect.bottom + window.scrollY + 6}px`;
}

function closePopover() {
  el("card-popover").hidden = true;
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

function describeAction(action) {
  const verb = ACTION_LABELS[action.action_id] || prettify(action.action_id);
  const parts = [];
  for (const [key, value] of Object.entries(action.arguments)) {
    if (typeof value === "number" || typeof value === "boolean") {
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
      `seed ${summary.game_seed} · ${summary.seats.join(", ")} · ${label} `
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
  const seats = [...el("seat-selects").querySelectorAll("select")].map(
    (select) => select.value
  );
  const payload = {
    seats,
    choam_module: el("opt-choam").checked,
    leader_draft: el("opt-leader-draft").checked,
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
  el("leave-game").hidden = false;
  el("save-game").hidden = false;
  applySummary(summary);
}

function leaveGame() {
  state.gameId = null;
  state.summary = null;
  state.view = null;
  state.actions = null;
  state.review = null;
  el("review-bar").hidden = true;
  el("game-screen").hidden = true;
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
  if (decision && decision.owner_is_human) {
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
  if (state.viewSeat !== null) {
    state.view = await api(
      `/games/${state.gameId}/seats/${state.viewSeat}/view`
    );
    if (decision && decision.owner === state.viewSeat) {
      state.actions = await api(
        `/games/${state.gameId}/seats/${state.viewSeat}/actions`
      );
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

/* ---------- replay review ---------- */

async function enterReview(seat) {
  const meta = await api(`/games/${state.gameId}/review?seat=${seat}`);
  state.review = { meta, seat, cursor: meta.step_count };
  const select = el("review-seat");
  select.textContent = "";
  for (const humanSeat of humanSeats()) {
    const option = document.createElement("option");
    option.value = String(humanSeat);
    option.textContent = `좌석 ${humanSeat}`;
    select.appendChild(option);
  }
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
    el("review-status").textContent =
      `step ${cursor}/${review.meta.step_count}` +
      ` · 라운드 ${payload.round_number}` +
      ` · ${PHASE_LABELS[payload.phase] || payload.phase}` +
      ` · ${describeReviewStep(review.meta.steps[cursor - 1])}`;
    render();
  } catch (error) {
    el("game-error").textContent = `검토 상태 조회 실패 (${error.message})`;
    el("game-error").hidden = false;
  }
}

function describeReviewStep(label) {
  if (!label) return "게임 시작 전";
  if (label.type === "chance") {
    return `chance: ${prettify(label.decision_id)}`;
  }
  if (label.action_id) {
    return `좌석 ${label.actor}: ${describeAction(label)}`;
  }
  return `좌석 ${label.actor} 행동`;
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

function render() {
  const summary = state.summary;
  if (!summary) return;
  closePopover();
  el("header-status").textContent =
    `라운드 ${summary.round_number} · ${PHASE_LABELS[summary.phase] || summary.phase}` +
    ` · seed ${summary.game_seed}` +
    (summary.choam_module ? " · CHOAM" : "") +
    (summary.leader_draft ? " · draft" : "") +
    (state.review ? " · 리플레이 검토" : "");
  el("decision-banner").hidden = Boolean(state.review);
  renderBanner();
  renderStandings();
  renderBoard();
  renderSpaces();
  renderSeats();
  renderPrivate();
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
    return;
  }
  const decision = summary.decision;
  if (!decision) {
    prompt.textContent = "진행 중…";
    info.append(prompt);
    return;
  }
  const seatKind = summary.seats[decision.owner];
  const who =
    decision.owner === state.viewSeat
      ? `좌석 ${decision.owner} (당신)`
      : `좌석 ${decision.owner} (${seatKind})`;
  prompt.textContent = decision.prompt;
  meta.textContent = `${who} · frame: ${decision.kind}`;
  info.append(prompt, meta);

  if (!state.actions || decision.owner !== state.viewSeat) return;
  for (const action of state.actions.actions) {
    actionsBox.appendChild(actionItem(action));
  }
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

function actionPreviewLines(action, entry) {
  if (entry.options) {
    const options = spaceOptionsFor(entry);
    const index =
      typeof action.arguments.cost_option === "number"
        ? action.arguments.cost_option
        : 0;
    const option = options[index] || options[0];
    const lines = [];
    if (entry.requirement) lines.push(requirementText(entry.requirement));
    lines.push(`[${costText(option.cost)}] ${option.effect}`);
    lines.push(...entry.notes);
    return lines;
  }
  const optionIndex = action.arguments.option;
  if (
    action.action_id === "play_intrigue" &&
    entry.text &&
    typeof optionIndex === "number" &&
    entry.text[optionIndex]
  ) {
    return [entry.text[optionIndex]];
  }
  return popoverLines(entry);
}

function actionItem(action) {
  const wrap = document.createElement("div");
  wrap.className = "action-item";
  const button = document.createElement("button");
  button.textContent = describeAction(action);
  button.disabled = state.busy;
  button.addEventListener("click", () => applyAction(action.index));
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
      for (const text of actionPreviewLines(action, entry)) {
        const line = document.createElement("div");
        line.className = "popover-line";
        line.textContent = text;
        detail.appendChild(line);
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

function section(parent, title) {
  const heading = document.createElement("h3");
  heading.textContent = title;
  const body = document.createElement("div");
  parent.append(heading, body);
  return body;
}

function renderBoard() {
  const board = el("board");
  board.textContent = "";
  const view = state.view;
  if (!view) {
    board.innerHTML =
      '<span class="muted">사람 좌석이 없어 보드를 볼 수 없습니다.</span>';
    return;
  }
  const heading = document.createElement("h2");
  heading.textContent = "보드";
  board.appendChild(heading);

  if (view.leader_draft_pool.length) {
    const picked = new Set(
      view.players.map((p) => p.leader_id).filter(Boolean)
    );
    const pool = section(board, "Leader draft pool");
    for (const leaderId of view.leader_draft_pool) {
      const mark = chip(leaderId);
      if (picked.has(leaderId)) {
        mark.classList.add("muted");
        mark.textContent += " (선택됨)";
      }
      pool.appendChild(mark);
    }
  }

  const conflict = section(board, "현재 Conflict");
  chipList(conflict, view.current_conflict_ids, "아직 공개되지 않음");
  if (!view.shield_wall_present) {
    const note = document.createElement("span");
    note.className = "tag";
    note.textContent = "Shield Wall 파괴됨";
    conflict.appendChild(note);
  }

  const row = section(board, "Imperium Row");
  chipList(row, view.imperium_row, "비어 있음");

  const reserve = section(board, "Reserve");
  reserve.textContent = "";
  for (const [cardId, count] of view.reserve_stacks) {
    const mark = chip(cardId);
    mark.textContent += ` ×${count}`;
    reserve.appendChild(mark);
  }

  if (state.summary.choam_module) {
    const contracts = section(board, "Contract 시장");
    chipList(contracts, view.face_up_contract_ids, "비어 있음");
    const bank = document.createElement("span");
    bank.className = "muted";
    bank.textContent = ` bank ${view.contract_bank_size}장`;
    contracts.appendChild(bank);
    if (view.sardaukar_contract_ids.length) {
      const aside = document.createElement("span");
      aside.className = "muted";
      aside.textContent = " · set-aside: ";
      contracts.appendChild(aside);
      for (const id of view.sardaukar_contract_ids)
        contracts.appendChild(chip(id));
    }
  }

  const maker = section(board, "Maker bonus spice");
  maker.textContent = view.maker_bonus_spice
    .map(([space, amount]) => `${nameOf(space)} ${amount}`)
    .join(" · ");

  if (view.intrigue_discard.length) {
    const discard = section(board, "Intrigue discard");
    chipList(discard, view.intrigue_discard.slice(-8), "");
  }
}

function renderSpaces() {
  const panel = el("spaces");
  panel.textContent = "";
  const catalog = state.catalog;
  if (!catalog) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;

  const heading = document.createElement("h2");
  heading.textContent = "보드 공간";
  panel.appendChild(heading);
  const hint = document.createElement("div");
  hint.className = "muted";
  hint.textContent =
    "Combat space 방문 시: 이번 turn에 recruit한 troop 전부와 garrison의 " +
    "troop 최대 2개를 Conflict에 배치할 수 있습니다.";
  panel.appendChild(hint);

  const occupants = new Map();
  const controllers = new Map();
  const view = state.view;
  if (view) {
    for (const player of view.players) {
      for (const spaceId of player.agent_locations) {
        if (!occupants.has(spaceId)) occupants.set(spaceId, []);
        occupants.get(spaceId).push(player.player);
      }
      for (const spaceId of player.control_space_ids) {
        controllers.set(spaceId, player.player);
      }
    }
  }
  const makerSpice = new Map(view ? view.maker_bonus_spice : []);

  for (const [icon, label] of AGENT_ICON_GROUPS) {
    const spaceIds = Object.keys(catalog.spaces).filter(
      (spaceId) => catalog.spaces[spaceId].agent_icon === icon
    );
    if (!spaceIds.length) continue;
    const body = section(panel, label);
    for (const spaceId of spaceIds) {
      body.appendChild(spaceRow(spaceId, occupants, controllers, makerSpice));
    }
  }
}

function spaceRow(spaceId, occupants, controllers, makerSpice) {
  const entry = state.catalog.spaces[spaceId];
  const row = document.createElement("div");
  row.className = "space-row";

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
  if (entry.requirement) {
    const requirement = document.createElement("div");
    requirement.className = "muted";
    requirement.textContent = requirementText(entry.requirement);
    detail.appendChild(requirement);
  }
  for (const option of spaceOptionsFor(entry)) {
    const line = document.createElement("div");
    line.textContent = `[${costText(option.cost)}] ${option.effect}`;
    detail.appendChild(line);
  }
  for (const noteText of entry.notes) {
    const line = document.createElement("div");
    line.className = "muted";
    line.textContent = noteText;
    detail.appendChild(line);
  }
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
  return row;
}

function seatLine(container, label, text) {
  const line = document.createElement("div");
  line.className = "cardline";
  const strong = document.createElement("strong");
  strong.textContent = `${label} `;
  line.append(strong, text);
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

    const who = document.createElement("div");
    who.className = "who";
    const leader = player.leader_id ? nameOf(player.leader_id) : "Leader 미정";
    who.textContent = `좌석 ${seat} · ${leader}`;
    if (summary.seats[seat] === "human") {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = seat === activeSeat() ? "YOU" : "사람";
      who.appendChild(badge);
    }
    if (summary.first_player === seat) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "First Player";
      who.appendChild(badge);
    }
    card.appendChild(who);
    if (
      player.leader_face_id &&
      player.leader_id &&
      player.leader_face_id !== player.leader_id
    ) {
      seatLine(card, "면", nameOf(player.leader_face_id));
    }

    seatLine(
      card,
      `🏆 ${player.victory_points}`,
      ` ${RESOURCE_ICONS.solari}${player.resources.solari}` +
        ` ${RESOURCE_ICONS.spice}${player.resources.spice}` +
        ` ${RESOURCE_ICONS.water}${player.resources.water}`
    );
    seatLine(
      card,
      "Influence",
      Object.entries(FACTION_LABELS)
        .map(([key, label]) => `${label} ${player.influence[key]}`)
        .join(" · ")
    );
    const agents = player.agent_locations.map(nameOf).join(", ");
    seatLine(
      card,
      "Agents",
      `${player.agents_available}명 대기` +
        (agents ? ` · 배치: ${agents}` : "") +
        (player.swordmaster_acquired ? " · Swordmaster" : "")
    );
    seatLine(
      card,
      "병력",
      `supply ${player.troops_supply} · garrison ${player.troops_garrison}` +
        ` · conflict ${player.troops_conflict}` +
        (player.sandworms_conflict ? ` · worm ${player.sandworms_conflict}` : "") +
        (player.combat_strength ? ` · ⚔${player.combat_strength}` : "")
    );
    seatLine(
      card,
      "Spy",
      `supply ${player.spies_supply}` +
        (player.spy_post_ids.length
          ? ` · ${player.spy_post_ids.map(prettify).join(", ")}`
          : "")
    );
    const flags = [];
    if (player.high_council) flags.push("High Council");
    if (player.maker_hooks) flags.push("Maker Hooks");
    if (player.has_revealed) flags.push("Revealed");
    if (player.alliance_faction_ids.length) {
      flags.push(
        "Alliance: " +
          player.alliance_faction_ids
            .map((f) => FACTION_LABELS[f] || f)
            .join("/")
      );
    }
    if (player.control_space_ids.length) {
      flags.push("Control: " + player.control_space_ids.map(nameOf).join("/"));
    }
    if (flags.length) seatLine(card, "상태", flags.join(" · "));

    const zones = [];
    zones.push(`hand ${player.hand_size}`);
    zones.push(`deck ${player.deck_size}`);
    zones.push(`discard ${player.discard_size}`);
    zones.push(`intrigue ${player.intrigue_card_count}`);
    if (player.completed_contract_count) {
      zones.push(`계약 완료 ${player.completed_contract_count}`);
    }
    seatLine(card, "존", zones.join(" · "));

    const battle = [
      ...player.objective_ids,
      ...player.won_conflict_ids,
    ];
    if (battle.length || player.face_down_battle_card_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Battle cards ";
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
    if (player.active_contract_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Contracts ";
      line.appendChild(strong);
      for (const id of player.active_contract_ids) line.appendChild(chip(id));
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
    wrap.appendChild(card);
  }
}

function renderPrivate() {
  const panel = el("private-zone");
  panel.textContent = "";
  const view = state.view;
  if (!view || !view.private) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const heading = document.createElement("h2");
  heading.textContent = `내 카드 (좌석 ${activeSeat()})`;
  panel.appendChild(heading);

  const hand = section(panel, `Hand (${view.private.hand.length})`);
  chipList(hand, view.private.hand, "비어 있음");
  const discard = section(
    panel,
    `Discard (${view.private.discard_pile.length})`
  );
  chipList(discard, view.private.discard_pile, "비어 있음");
  const intrigue = section(
    panel,
    `Intrigue (${view.private.intrigue_cards.length})`
  );
  chipList(intrigue, view.private.intrigue_cards, "없음");
  const deck = section(panel, "Deck");
  deck.textContent = `${view.private.deck_size}장`;
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

/* ---------- boot ---------- */

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
