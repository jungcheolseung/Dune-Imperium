"use strict";

/* The host's admin page (admin.html): how the server and its machine are
   doing, the games and saves, and the recent log. Host only; every call it
   makes is refused for anyone else (server/app.py). Everything the server
   sends -- player names, save names, log lines -- is other people's input
   and goes into the page as text, never as markup. */

const LANGUAGE_KEY = "dune.language";
const REFRESH_MS = 10000;

let language = "ko";
let whoami = null;
let refreshing = false;
let statusFromRefresh = false;
let lastRefreshAt = null;
/* The newest data, so a language switch redraws without asking again. */
let latest = { status: null, games: null, saves: null };
/* Games whose room link is open, and what each section last drew (a redraw
   of identical data would drop the host's text selection). */
const shownLinks = new Set();
const drawn = {};

const KIND_KEYS = {
  human: "admin.kind_human",
  app_ai: "admin.kind_app_ai",
  app_ai_medium: "admin.kind_app_ai_medium",
  app_ai_easy: "admin.kind_app_ai_easy",
  search: "admin.kind_search",
  heuristic: "admin.kind_heuristic",
  rollout: "admin.kind_rollout",
  rollout_strong: "admin.kind_rollout_strong",
  random: "admin.kind_random",
  checkpoint: "admin.kind_checkpoint",
};

function el(id) {
  return document.getElementById(id);
}

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

/* ---------- language ---------- */

function textTemplate(key) {
  const entry = UI_TEXT[key];
  if (!entry) return `[${key}]`;
  return entry[language] || entry.ko;
}

function t(key, vars) {
  return textTemplate(key).replace(/\{\{([A-Za-z0-9_]+)\}\}/g, (match, name) =>
    vars && name in vars ? String(vars[name]) : match,
  );
}

function loadLanguage() {
  try {
    language = window.localStorage.getItem(LANGUAGE_KEY) === "en" ? "en" : "ko";
  } catch (error) {
    language = "ko";
  }
}

function applyStaticText() {
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  document.documentElement.lang = language;
  document.title = `Dune: Imperium · ${t("admin.title")}`;
  /* The button names the other language, in that language. */
  el("language-toggle").textContent = language === "en" ? "한국어" : "English";
}

function setLanguage(chosen) {
  language = chosen;
  try {
    window.localStorage.setItem(LANGUAGE_KEY, chosen);
  } catch (error) {
    /* private mode: the choice lasts until the page closes */
  }
  for (const key of Object.keys(drawn)) delete drawn[key];
  applyStaticText();
  renderSignedOutHow();
  showRefreshTime();
  renderAll();
}

/* ---------- formatting ---------- */

const DASH = "—";

function formatBytes(value) {
  if (typeof value !== "number") return DASH;
  const gb = value / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}

function formatTime(value) {
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return typeof value === "string" ? value : DASH;
  return date.toLocaleString(language === "en" ? "en-GB" : "ko-KR");
}

function formatUptime(seconds) {
  const minutes = Math.floor(seconds / 60) % 60;
  const hours = Math.floor(seconds / 3600) % 24;
  const days = Math.floor(seconds / 86400);
  if (days > 0) return t("admin.uptime_days", { days, hours, minutes });
  if (hours > 0) return t("admin.uptime_hours", { hours, minutes });
  return t("admin.uptime_minutes", { minutes });
}

function orDash(value) {
  return value === null || value === undefined || value === "" ? DASH : String(value);
}

function onOff(value) {
  return value ? t("admin.on") : t("admin.off");
}

function shortId(gameId) {
  return gameId.slice(0, 8);
}

function kindLabel(kind) {
  const key = kind.startsWith("checkpoint:")
    ? "checkpoint"
    : kind.startsWith("search:")
      ? "search"
      : kind;
  return KIND_KEYS[key] ? t(KIND_KEYS[key]) : kind;
}

const PACE_KEYS = {
  normal: "screens.ai_pace_normal",
  fast: "screens.ai_pace_fast",
  instant: "screens.ai_pace_instant",
};
const SEATING_KEYS = { random: "admin.seating_random", fixed: "admin.seating_fixed" };
const FIRST_PLAYER_KEYS = {
  player1: "admin.first_player_player1",
  deal: "admin.first_player_deal",
};

/* A server option's word, or the option as the server wrote it. */
function optionLabel(keys, value) {
  return keys[value] ? t(keys[value]) : orDash(value);
}

function seatLabel(seat) {
  return t("admin.seat_label", { n: seat + 1 });
}

/* ---------- requests ---------- */

/* The server's error sentence in Korean where errors_ko.js has it (the
   table and its patterns, read the way i18n.js serverErrorText reads them:
   $N a group as written, #N a group plus one). */
function serverText(detail) {
  if (language !== "ko" || typeof SERVER_ERROR_KO === "undefined") return detail;
  if (Object.prototype.hasOwnProperty.call(SERVER_ERROR_KO, detail)) {
    return SERVER_ERROR_KO[detail];
  }
  for (const [pattern, korean] of SERVER_ERROR_KO_PATTERNS) {
    const match = detail.match(new RegExp(pattern));
    if (match) {
      return korean.replace(/([$#])(\d)/g, (whole, sign, group) =>
        sign === "#" ? String(Number(match[Number(group)]) + 1) : match[Number(group)],
      );
    }
  }
  return detail;
}

async function api(path, options) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    throw new Error(t("admin.unreachable"));
  }
  if (!response.ok) {
    let message = t("admin.request_failed", { status: response.status });
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = serverText(body.detail);
      else if (body.detail) message = JSON.stringify(body.detail);
    } catch (error) {
      /* keep the status text */
    }
    const failure = new Error(message);
    failure.status = response.status;
    throw failure;
  }
  return response.json();
}

function post(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body === undefined ? {} : body),
  });
}

function setStatus(message, isError, fromRefresh) {
  const node = el("status");
  node.textContent = message || "";
  node.hidden = !message;
  node.classList.toggle("error", Boolean(isError));
  statusFromRefresh = Boolean(fromRefresh);
}

/* ---------- sign-in ---------- */

async function adoptAdminLink() {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const key = params.get("admin");
  if (!key) return null;
  window.history.replaceState(
    null,
    "",
    window.location.pathname + window.location.search,
  );
  try {
    await post("/auth/admin", { key });
    return null;
  } catch (error) {
    return t("admin.link_invalid", { message: error.message });
  }
}

async function adoptTailscaleSignIn(server) {
  if (server.admin || !server.tailscale_sign_in) return server;
  try {
    await post("/auth/tailscale");
  } catch (error) {
    return server;
  }
  return api("/whoami");
}

function renderSignedOutHow() {
  el("signed-out-how").textContent =
    whoami && whoami.tailscale_sign_in ? t("admin.how_tailscale") : t("admin.how_link");
}

function showMode(isAdmin) {
  el("signed-out").hidden = isAdmin;
  el("panels").hidden = !isAdmin;
  el("back-link").hidden = !isAdmin;
  el("refresh").hidden = !isAdmin;
  if (!isAdmin) el("last-refresh").hidden = true;
}

/* ---------- drawing ---------- */

/* Draws a section's content unless it is what the section already shows. */
function draw(name, container, signature, build) {
  const key = JSON.stringify(signature);
  if (drawn[name] === key) return;
  drawn[name] = key;
  container.textContent = "";
  build(container);
}

function fact(list, labelKey, value) {
  list.appendChild(make("dt", "", t(labelKey)));
  list.appendChild(make("dd", "", value));
}

function renderServer(status) {
  const list = el("server-list");
  list.textContent = "";
  if (!status) return;
  const server = status.server;
  fact(list, "admin.f_commit", orDash(server.commit));
  fact(list, "admin.f_codec", orDash(server.action_codec));
  fact(list, "admin.f_observation", orDash(server.observation));
  fact(list, "admin.f_python", orDash(server.python));
  fact(list, "admin.f_uptime", formatUptime(server.uptime_seconds));
  fact(list, "admin.f_started", formatTime(server.started_at));
  fact(
    list,
    "admin.f_access",
    server.access === "remote" ? t("admin.access_remote") : t("admin.access_open"),
  );
  fact(list, "admin.f_public_url", orDash(server.public_url));
  fact(list, "admin.f_autosave", onOff(server.autosave));
  fact(list, "admin.f_saves_dir", orDash(server.saves_dir));
  fact(list, "admin.f_search_ai", orDash(server.search_ai));
  fact(list, "admin.f_search_ai_imperium", orDash(server.search_ai_imperium));
  fact(list, "admin.f_search_worlds", orDash(server.search_turn_extend));
  fact(list, "admin.f_ai_pace", optionLabel(PACE_KEYS, server.ai_pace));
  fact(list, "admin.f_seating", optionLabel(SEATING_KEYS, server.seating));
  fact(list, "admin.f_first_player", optionLabel(FIRST_PLAYER_KEYS, server.first_player));
  const users = server.tailscale_users || [];
  fact(list, "admin.f_tailscale", users.length ? users.join(", ") : t("admin.none"));
}

function renderMachine(status) {
  const list = el("machine-list");
  list.textContent = "";
  if (!status) return;
  const machine = status.machine;
  fact(list, "admin.m_name", orDash(machine.name));
  fact(list, "admin.m_system", orDash(machine.system));
  fact(list, "admin.m_cpus", orDash(machine.cpus));
  const load = machine.load;
  fact(
    list,
    "admin.m_load",
    Array.isArray(load) ? load.map((value) => value.toFixed(2)).join(" / ") : DASH,
  );
  fact(
    list,
    "admin.m_memory",
    `${formatBytes(machine.memory_available)} / ${formatBytes(machine.memory_total)}`,
  );
  fact(list, "admin.m_process", formatBytes(machine.process_rss));
  fact(
    list,
    "admin.m_disk",
    `${formatBytes(machine.disk_free)} / ${formatBytes(machine.disk_total)}`,
  );
}

function roomLink(gameId) {
  const base = (whoami && whoami.public_url) || window.location.origin;
  return `${base.replace(/\/+$/, "")}/#game=${gameId}`;
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

function actionButton(label, onClick, danger) {
  const button = make("button", danger ? "danger" : "", label);
  button.type = "button";
  button.addEventListener("click", onClick);
  return button;
}

function whoIs(player) {
  if (player.kind === "human") {
    return player.claimed ? player.name || seatLabel(player.seat) : t("admin.seat_open");
  }
  return kindLabel(player.kind);
}

function gameState(game) {
  if (game.finished) return t("admin.game_finished");
  if (game.awaiting_start) return t("admin.game_waiting");
  return t("admin.game_round", { round: game.round_number });
}

function renderGame(game) {
  const block = make("article", "game");
  block.dataset.gameId = game.game_id;
  const id = shortId(game.game_id);
  block.appendChild(make("h3", "", t("admin.game_title", { id })));
  const base = game.base_game === "imperium" ? "admin.base_imperium" : "admin.base_uprising";
  block.appendChild(make("div", "meta", `${t(base)} · ${gameState(game)}`));

  const seats = make("ul", "seats");
  for (const player of game.players) {
    const row = make("li");
    row.dataset.seat = String(player.seat);
    if (player.kind === "human" && player.claimed) {
      const dot = make("span", player.online ? "dot online" : "dot");
      dot.title = player.online ? t("admin.online") : t("admin.offline");
      row.appendChild(dot);
    }
    row.appendChild(make("span", "seat-label", seatLabel(player.seat)));
    row.appendChild(make("span", "seat-name", whoIs(player)));
    if (player.kind === "human" && player.claimed) {
      const who = `${seatLabel(player.seat)} ${player.name || ""}`.trim();
      row.appendChild(
        actionButton(t("admin.release"), () => releaseSeat(game, player, who), true),
      );
    }
    /* A person's seat the host hands to the AI, say once its player has
       left (sessions.py hand_to_ai); only its player takes it back. */
    if (player.kind === "human" && !game.finished && !game.awaiting_start) {
      if (player.ai) {
        row.appendChild(make("span", "seat-ai", t("admin.ai_plays")));
      } else {
        const who = `${seatLabel(player.seat)} ${player.name || ""}`.trim();
        row.appendChild(
          actionButton(t("admin.hand_to_ai"), () => handSeatToAi(game, player, who)),
        );
      }
    }
    seats.appendChild(row);
  }
  block.appendChild(seats);

  const decision = game.decision;
  if (!game.finished && decision && typeof decision.owner === "number") {
    const owner = game.players[decision.owner];
    const who = owner
      ? `${seatLabel(owner.seat)} · ${whoIs(owner)}`
      : seatLabel(decision.owner);
    block.appendChild(make("div", "meta decision", t("admin.turn_of", { who })));
  }

  const actions = make("div", "actions");
  actions.appendChild(actionButton(t("admin.copy_link"), () => showLink(game.game_id)));
  actions.appendChild(actionButton(t("admin.save_now"), () => saveGame(game)));
  actions.appendChild(
    actionButton(t("admin.delete_game"), () => deleteGame(game), true),
  );
  block.appendChild(actions);
  if (shownLinks.has(game.game_id)) {
    const input = make("input", "room-link");
    input.type = "text";
    input.readOnly = true;
    input.value = roomLink(game.game_id);
    block.appendChild(input);
  }
  return block;
}

function renderGames() {
  const games = latest.games;
  if (!games) return;
  draw("games", el("games"), [games, [...shownLinks], language], (box) => {
    if (!games.length) {
      box.appendChild(make("p", "", t("admin.games_none")));
      return;
    }
    for (const game of games) box.appendChild(renderGame(game));
  });
}

function renderSave(save) {
  const block = make("article", "save");
  block.dataset.saveId = save.save_id;
  const name = save.autosave
    ? t("admin.save_autosave")
    : save.name || t("admin.save_unnamed");
  block.appendChild(make("h3", "", name));
  const progress = save.finished
    ? t("admin.save_finished")
    : t("admin.save_progress", {
        round: orDash(save.round_number),
        phase: orDash(save.phase),
      });
  block.appendChild(make("div", "meta", `${formatTime(save.saved_at)} · ${progress}`));
  const actions = make("div", "actions");
  actions.appendChild(actionButton(t("admin.load"), () => loadSave(save)));
  actions.appendChild(
    actionButton(t("admin.delete_save"), () => deleteSave(save, name), true),
  );
  block.appendChild(actions);
  return block;
}

function renderSaves() {
  const saves = latest.saves;
  if (!saves) return;
  const ordered = [...saves].sort((a, b) =>
    String(b.saved_at).localeCompare(String(a.saved_at)),
  );
  draw("saves", el("saves"), [ordered, language], (box) => {
    if (!ordered.length) {
      box.appendChild(make("p", "", t("admin.saves_none")));
      return;
    }
    for (const save of ordered) box.appendChild(renderSave(save));
  });
}

function renderLog() {
  const status = latest.status;
  if (!status) return;
  const lines = status.log;
  draw("log", el("log"), [lines, language], (box) => {
    if (lines === null || lines === undefined) {
      box.appendChild(make("p", "", t("admin.log_none")));
      return;
    }
    if (!lines.length) {
      box.appendChild(make("p", "", t("admin.log_empty")));
      return;
    }
    for (const line of [...lines].reverse()) {
      const row = make("div", `log-line level-${line.level}`);
      row.appendChild(make("span", "log-time", formatTime(line.time)));
      row.appendChild(make("span", "log-level", line.level));
      row.appendChild(make("span", "log-message", line.message));
      box.appendChild(row);
    }
  });
}

function renderAll() {
  if (!whoami || !whoami.admin) return;
  renderServer(latest.status);
  renderMachine(latest.status);
  renderGames();
  renderSaves();
  renderLog();
}

function showRefreshTime() {
  const node = el("last-refresh");
  if (!lastRefreshAt) return;
  node.hidden = false;
  node.textContent = t("admin.last_refresh", {
    time: lastRefreshAt.toLocaleTimeString(language === "en" ? "en-GB" : "ko-KR"),
  });
}

/* ---------- refreshing ---------- */

async function signedOut() {
  whoami = await api("/whoami");
  renderSignedOutHow();
  showMode(Boolean(whoami.admin));
}

async function refresh() {
  if (!whoami || !whoami.admin || refreshing) return;
  refreshing = true;
  try {
    const calls = {
      status: api("/admin/status"),
      games: api("/games"),
      saves: api("/saves"),
    };
    const names = Object.keys(calls);
    const results = await Promise.allSettled(names.map((name) => calls[name]));
    let failure = null;
    results.forEach((result, index) => {
      if (result.status === "fulfilled") latest[names[index]] = result.value;
      else failure = failure || result.reason;
    });
    lastRefreshAt = new Date();
    showRefreshTime();
    renderAll();
    if (failure) {
      setStatus(failure.message, true, true);
      if (failure.status === 403) await signedOut().catch(() => {});
    } else if (statusFromRefresh) {
      setStatus("", false, false);
    }
  } finally {
    refreshing = false;
  }
}

/* One action: confirmed by the host first when it cannot be undone, its
   error shown in the status line, the lists redrawn right after. */
async function act(run, doneKey, vars) {
  try {
    const result = await run();
    setStatus(t(doneKey, vars ? vars(result) : undefined), false, false);
  } catch (error) {
    setStatus(error.message, true, false);
  }
  await refresh();
}

function showLink(gameId) {
  shownLinks.add(gameId);
  renderGames();
  const input = document.querySelector(
    `.game[data-game-id="${gameId}"] .room-link`,
  );
  if (input) copyText(input);
}

function saveGame(game) {
  return act(() => post(`/games/${game.game_id}/save`, {}), "admin.done_saved", () => ({
    id: shortId(game.game_id),
  }));
}

function deleteGame(game) {
  const id = shortId(game.game_id);
  if (!window.confirm(t("admin.confirm_delete_game", { id }))) return Promise.resolve();
  shownLinks.delete(game.game_id);
  return act(
    () => api(`/games/${game.game_id}`, { method: "DELETE" }),
    "admin.done_deleted_game",
    () => ({ id }),
  );
}

function releaseSeat(game, player, who) {
  if (!window.confirm(t("admin.confirm_release", { who }))) return Promise.resolve();
  return act(
    () => post(`/games/${game.game_id}/seats/${player.seat}/release`),
    "admin.done_released",
    () => ({ who }),
  );
}

function handSeatToAi(game, player, who) {
  if (!window.confirm(t("admin.confirm_hand_to_ai", { who }))) return Promise.resolve();
  return act(
    () => post(`/games/${game.game_id}/seats/${player.seat}/ai`),
    "admin.done_handed",
    () => ({ who }),
  );
}

function loadSave(save) {
  return act(() => post(`/saves/${save.save_id}/load`), "admin.done_loaded", (made) => ({
    id: shortId(made.game_id),
  }));
}

function deleteSave(save, name) {
  if (!window.confirm(t("admin.confirm_delete_save", { name }))) return Promise.resolve();
  return act(
    () => api(`/saves/${save.save_id}`, { method: "DELETE" }),
    "admin.done_deleted_save",
  );
}

/* ---------- start ---------- */

async function init() {
  loadLanguage();
  applyStaticText();
  el("language-toggle").addEventListener("click", () =>
    setLanguage(language === "en" ? "ko" : "en"),
  );
  el("refresh").addEventListener("click", () => refresh());
  const linkError = await adoptAdminLink();
  try {
    whoami = await adoptTailscaleSignIn(await api("/whoami"));
  } catch (error) {
    setStatus(error.message, true, false);
    return;
  }
  renderSignedOutHow();
  showMode(Boolean(whoami.admin));
  if (linkError) setStatus(linkError, true, false);
  if (!whoami.admin) return;
  await refresh();
  window.setInterval(() => {
    if (document.visibilityState === "visible") refresh();
  }, REFRESH_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refresh();
  });
}

init();
