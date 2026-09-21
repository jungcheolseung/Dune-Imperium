"use strict";

/* ---------- setup screen ---------- */

function buildSeatSelects() {
  const wrap = el("seat-selects");
  /* A language switch builds them again: keep what was chosen. */
  const chosen = [...wrap.querySelectorAll("select")].map((select) => select.value);
  wrap.textContent = "";
  for (let seat = 0; seat < 4; seat += 1) {
    const label = document.createElement("label");
    label.append(`${t("common.seat", { seat })} `);
    const select = document.createElement("select");
    select.dataset.seat = String(seat);
    for (const [value, text] of SEAT_KINDS) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.appendChild(option);
    }
    select.value = chosen[seat] || (seat === 0 ? "human" : "heuristic");
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
      ? t("common.finished")
      : t("screens.round_number", { round: summary.round_number });
    item.append(
      `${seedLabel(summary)}${summary.seats.map(seatKindLabel).join(", ")} · ${label} `
    );
    const button = document.createElement("button");
    button.textContent = t("screens.continue_button");
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
    load.textContent = t("screens.load_button");
    load.addEventListener("click", async () => {
      try {
        el("setup-error").hidden = true;
        const summary = await api(`/saves/${entry.save_id}/load`, {
          method: "POST",
        });
        await openGame(summary.game_id);
      } catch (error) {
        el("setup-error").textContent = t("screens.load_failed", { message: error.message });
        el("setup-error").hidden = false;
      }
    });
    const remove = document.createElement("button");
    remove.textContent = t("screens.delete_button");
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
  const status = entry.finished
    ? t("common.finished")
    : t("screens.round_number", { round: entry.round_number });
  /* An autosave's name only repeats what its badge and the round say. */
  if (entry.autosave) return status;
  const title =
    entry.name ||
    (entry.game_seed === null ? t("screens.unnamed_save") : `seed ${entry.game_seed}`);
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
  badge.textContent = t("screens.autosave_badge");
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
    el("setup-error").textContent = t("screens.create_game_failed", { message: error.message });
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
  return isRemote() && !info.claimed ? t("screens.empty_seat") : t("screens.person");
}

function playerLabel(seat) {
  return t("screens.player_label", { seat, name: playerName(seat) });
}

function presenceDot(info) {
  const dot = document.createElement("span");
  dot.className = "presence " + (info.online ? "on" : "off");
  dot.title = info.online ? t("screens.online") : t("screens.offline");
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
  announcedTurn = undefined;
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
        ? t("screens.game_not_found")
        : t("screens.game_fetch_failed", { message: error.message })
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
  el("game-error").textContent = t("screens.game_state_failed", { message: error.message });
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
    t("screens.lobby_status", {
      round: summary.round_number,
      phase: PHASE_LABELS[summary.phase] || summary.phase,
    }) + (summary.finished ? " · " + t("common.finished") : "");
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
        badge.textContent = t("screens.my_seat");
        item.appendChild(badge);
        item.appendChild(lobbyButton(t("screens.leave_seat"), () => releaseSeat(info.seat)));
      } else if (!info.claimed) {
        free += 1;
        item.appendChild(lobbyButton(t("screens.sit_button"), () => claimSeat(info.seat)));
      } else if (isAdmin()) {
        item.appendChild(lobbyButton(t("common.release_seat"), () => releaseSeat(info.seat)));
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
    lobbyError(t("screens.no_free_seats"));
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
    onClick().catch((error) => lobbyError(t("screens.request_failed", { message: error.message })));
  });
  return button;
}

async function claimSeat(seat) {
  if (state.busy) return;
  const name = el("lobby-name").value.trim();
  if (!name) {
    lobbyError(t("screens.name_required"));
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
        ? t("screens.seat_taken")
        : t("screens.sit_failed", { message: error.message })
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
  showLobby(t("screens.seat_left"));
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
  heading.textContent = t("screens.room_link_heading");
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
  copy.textContent = t("screens.copy_button");
  copy.addEventListener("click", () => copyText(link));
  row.append(link, copy);
  container.appendChild(row);

  if (!state.server.public_url) {
    const label = document.createElement("label");
    label.className = "room-base";
    label.append(`${t("screens.server_address_label")} `);
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
      release.textContent = t("common.release_seat");
      release.addEventListener("click", () => {
        releaseSeat(info.seat).catch((error) =>
          note(t("screens.release_seat_failed", { message: error.message }))
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
    ? t("screens.saves_heading_auto")
    : t("screens.saves_heading_manual");
  block.appendChild(heading);
  const hint = document.createElement("p");
  hint.className = "muted";
  hint.textContent = t("screens.save_recovery_hint");
  block.appendChild(hint);
  const known = hostSaves.gameId === state.gameId ? hostSaves : null;
  const list = document.createElement("ul");
  list.className = "host-save-list";
  if (known && known.error) {
    const item = document.createElement("li");
    item.className = "error";
    item.textContent = t("screens.save_list_error", { error: known.error });
    list.appendChild(item);
  } else if (known && known.entries) {
    if (!known.entries.length) {
      const item = document.createElement("li");
      item.className = "muted";
      item.textContent = t("screens.no_saves_yet");
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
  refreshButton.textContent = known
    ? t("screens.refresh_list_button")
    : t("screens.view_save_list_button");
  refreshButton.addEventListener("click", () => {
    loadHostSaves().catch(() => {});
  });
  const saveNow = document.createElement("button");
  saveNow.type = "button";
  saveNow.textContent = t("screens.save_now_button");
  saveNow.addEventListener("click", () => {
    saveGame().catch(() => {});
  });
  row.append(refreshButton, saveNow);
  block.appendChild(row);
  return block;
}
