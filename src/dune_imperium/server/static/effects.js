"use strict";

/* Card-use cues consume only events already filtered for the viewer in the
   session log. Never scan hands, draws, chance outcomes or arbitrary action
   arguments for cards. A whole AI batch can arrive in one snapshot. */
const CARD_PLAY_EVENTS = {
  agent_placed: "effects.agent",
  turn_start_card_played: "effects.played",
  card_grafted: "effects.graft",
  intrigue_played: "effects.intrigue",
  navigation_card_played: "effects.navigation",
};

const playEffects = { context: null, count: 0, queue: [], current: null, timer: 0 };

function clearPlayEffects() {
  clearTimeout(playEffects.timer);
  playEffects.timer = 0;
  playEffects.queue = [];
  playEffects.current = null;
  const box = el("play-effects");
  if (box) {
    box.hidden = true;
    box.textContent = "";
  }
}

function resetPlayEffects() {
  clearPlayEffects();
  playEffects.context = null;
  playEffects.count = 0;
}

function cardPlayCues(entries) {
  const cues = [];
  for (const entry of entries) {
    if (entry.undone || entry.type === "undo") continue;
    for (const event of entry.events || []) {
      const label = CARD_PLAY_EVENTS[event.kind];
      const payload = event.payload || {};
      if (!label || !Number.isInteger(payload.player) || payload.player < 0 || payload.player > 3) continue;
      const kind = ["intrigue_played", "navigation_card_played"].includes(event.kind)
        ? "intrigue" : "cards";
      if (typeof payload.card_id !== "string") continue;
      const card = entryOf(payload.card_id, kind);
      if (!card) continue;
      // A Plot/Combat card uses the timing of the option actually played.
      const optionText = Number.isInteger(payload.option) && (card.text || [])[payload.option];
      const timing = optionText ? optionText.split(" — ")[0].toLowerCase()
        : (card.timings || []).length === 1 ? card.timings[0] : null;
      cues.push({
        index: entry.index,
        cardId: payload.card_id,
        seat: payload.player,
        kind,
        label,
        timing,
        spaceId: event.kind === "agent_placed" || event.kind === "card_grafted"
          ? payload.space_id : null,
      });
    }
  }
  return cues;
}

function positionPlayEffect() {
  const box = el("play-effects");
  if (!box || box.hidden) return;
  const board = el("board").getBoundingClientRect();
  const width = box.offsetWidth;
  box.style.left = `${Math.max(12, Math.min(board.right - width - 12,
    window.innerWidth - width - 12))}px`;
  box.style.top = `${Math.max(56, Math.min(board.top + 12,
    window.innerHeight - box.offsetHeight - 12))}px`;
}

function drawPlayEffect() {
  const cue = playEffects.current;
  if (!cue) return;
  const entry = entryOf(cue.cardId, cue.kind);
  const box = el("play-effects");
  box.textContent = "";
  box.hidden = false;
  const toast = document.createElement("div");
  toast.className = "play-effect";
  toast.dataset.card = cue.cardId;
  toast.dataset.seat = String(cue.seat);
  toast.style.setProperty("--play-color", SEAT_COLORS[cue.seat]);
  const art = document.createElement("div");
  art.className = "play-effect-art";
  if (entry.image) {
    const img = document.createElement("img");
    img.src = entry.image;
    img.alt = entry.name;
    img.draggable = false;
    art.appendChild(img);
  } else {
    art.classList.add("textcard");
    art.textContent = entry.name;
  }
  const words = document.createElement("div");
  words.className = "play-effect-words";
  const player = document.createElement("div");
  player.className = "play-effect-player";
  player.textContent = playerLabel(cue.seat);
  const type = document.createElement("div");
  type.className = "play-effect-type";
  type.textContent = t(cue.kind === "intrigue" && cue.timing === "combat"
    ? "effects.combat_intrigue" : cue.label);
  const name = document.createElement("strong");
  name.textContent = entry.name;
  words.append(player, type, name);
  if (cue.spaceId) {
    const place = document.createElement("div");
    place.className = "play-effect-space";
    place.textContent = spaceName(cue.spaceId);
    words.appendChild(place);
  }
  toast.append(art, words);
  box.appendChild(toast);
  positionPlayEffect();
}

function nextPlayEffect() {
  clearTimeout(playEffects.timer);
  playEffects.current = playEffects.queue.shift() || null;
  if (!playEffects.current) {
    clearPlayEffects();
    return;
  }
  drawPlayEffect();
  // Shorten busy batches without delaying the game or dropping card plays.
  const duration = state.review
    ? Math.max(200, Math.min(2200, playback.intervalMs / (playEffects.queue.length + 1)))
    : playEffects.queue.length > 4 ? 1200 : 2200;
  playEffects.timer = setTimeout(nextPlayEffect, duration);
}

function renderPlayEffects() {
  if (!state.gameId || !state.view || el("game-screen").hidden) {
    resetPlayEffects();
    return;
  }
  const review = state.review;
  const log = review ? reviewLog(review) : state.log;
  if (!log) return;
  const context = `${state.gameId}:${review ? `review:${review.seat}` : "live"}`;
  if (playEffects.context !== context || log.count < playEffects.count) {
    // Joining, reloading, changing review seats or going backwards is a baseline.
    resetPlayEffects();
    playEffects.context = context;
    playEffects.count = log.count;
    return;
  }
  if (review && (!playback.playing || review.seek)) {
    clearPlayEffects();
    playEffects.count = log.count;
    return;
  }
  // An undo can change earlier entries without shrinking the append-only log.
  const live = (cue) => !log.entries[cue.index]?.undone;
  playEffects.queue = playEffects.queue.filter(live);
  if (playEffects.current && !live(playEffects.current)) {
    clearTimeout(playEffects.timer);
    playEffects.current = null;
  }
  playEffects.queue.push(...cardPlayCues(log.entries.slice(playEffects.count)));
  playEffects.count = log.count;
  if (!playEffects.current) nextPlayEffect();
  else {
    // A language switch updates the current art and caption, without requeueing.
    const shown = el("play-effects").querySelector(".play-effect-art img");
    const entry = entryOf(playEffects.current.cardId, playEffects.current.kind);
    if ((shown && shown.getAttribute("src") !== entry.image)
      || el("play-effects").dataset.language !== TERM_LANGUAGE) drawPlayEffect();
    positionPlayEffect();
  }
  el("play-effects").dataset.language = TERM_LANGUAGE;
}

/* ---------- phase and turn banners ----------

   A wide band over the board when a round starts (its Conflict is
   revealed), the Combat phase opens, an Arrakeen Scouts item is revealed,
   the Endgame begins or a seat's turn starts: the choices alone appeared
   too quietly (user request 2026-10-05). The phase cues come from the same
   viewer-filtered log events as the cues above, in log order; the turn cue
   comes from the summary and follows them. The lifecycle is the card-use
   cues' own: joining, reloading or changing the review seat is a baseline,
   an undone entry drops its cue, and leaving the table clears everything. */
const PHASE_BANNER_MS = 1600;
const PHASE_BANNER_BUSY_MS = 900;

/* The steps that end a turn (panels.js QUIET_ACTIONS lists them too). A
   seat's turn frame after one of them is a new turn, even its own again;
   the same frame met again after a turn-start Plot is the same turn. */
const TURN_END_ACTION_IDS = new Set(["finish_agent_turn", "finish_reveal"]);

const phaseBanner = {
  context: null,
  count: 0,
  turnKey: null,
  queue: [],
  current: null,
  timer: 0,
  shownAt: 0,
  duration: 0,
};

function clearPhaseBanner() {
  clearTimeout(phaseBanner.timer);
  phaseBanner.timer = 0;
  phaseBanner.queue = [];
  phaseBanner.current = null;
  const box = el("phase-banner");
  if (box) {
    box.hidden = true;
    box.textContent = "";
  }
}

function resetPhaseBanner() {
  clearPhaseBanner();
  phaseBanner.context = null;
  phaseBanner.count = 0;
  phaseBanner.turnKey = null;
}

/* The turn that starts now, as "<seat>:<log index of the last turn end>",
   or null. A held hand-over (summary.confirmation) is not a start yet: the
   next seat moves only once the last one confirms. Review shows none: its
   summary is the finished game's. */
function turnStartKey(summary, log) {
  if (!summary || summary.finished || typeof summary.confirmation === "number") return null;
  const decision = summary.decision;
  if (!decision || decision.kind !== "turn") return null;
  let ended = -1;
  for (let i = log.entries.length - 1; i >= 0; i -= 1) {
    const entry = log.entries[i];
    if (entry.type === "action" && !entry.undone && TURN_END_ACTION_IDS.has(entry.action_id)) {
      ended = entry.index;
      break;
    }
  }
  return `${decision.owner}:${ended}`;
}

/* The Conflict the log last revealed before `from`. Without a Leader draft
   the setup reveals the first one before the log begins (render.js
   resolvedConflictId), so the view's history names it. */
function conflictBefore(entries, from) {
  for (let i = from - 1; i >= 0; i -= 1) {
    const entry = entries[i];
    if (!entry || entry.undone || entry.type === "undo") continue;
    const event = (entry.events || []).findLast((item) => item.kind === "conflict_revealed");
    if (event) return { id: event.payload.conflict_id, round: event.payload.round };
  }
  const first = ((state.view && state.view.conflict_history) || [])[0];
  return first ? { id: first.conflict_id, round: first.round } : null;
}

function phaseBannerCues(entries, from) {
  const cues = [];
  let conflict;
  for (const entry of entries.slice(from)) {
    if (entry.undone || entry.type === "undo") continue;
    for (const event of entry.events || []) {
      const payload = event.payload || {};
      if (event.kind === "conflict_revealed") {
        conflict = { id: payload.conflict_id, round: payload.round };
        cues.push({
          type: "round",
          index: entry.index,
          round: payload.round,
          conflictId: payload.conflict_id,
        });
      } else if (event.kind === "combat_intrigue_started") {
        if (conflict === undefined) conflict = conflictBefore(entries, entry.index);
        cues.push({
          type: "combat",
          index: entry.index,
          round: conflict ? conflict.round : null,
          conflictId: conflict ? conflict.id : null,
        });
      } else if (event.kind === "scouts_item_revealed" && typeof payload.item_id === "string") {
        cues.push({
          type: "scouts",
          index: entry.index,
          round: payload.round,
          itemId: payload.item_id,
          itemKind: payload.kind,
        });
      } else if (event.kind === "endgame_started") {
        cues.push({ type: "endgame", index: entry.index });
      }
    }
  }
  return cues;
}

function conflictName(conflictId) {
  const entry = conflictId ? lookup(conflictId, "conflicts") : null;
  return entry ? entry.name : conflictId ? prettify(conflictId) : termLabel("conflict");
}

/* What a cue says: [kicker, title, subtitle, art entry]. */
function phaseBannerWords(cue) {
  const round = Number.isInteger(cue.round) ? t("effects.banner_round", { round: cue.round }) : null;
  if (cue.type === "round" || cue.type === "combat") {
    const conflict = t("effects.banner_conflict", { name: conflictName(cue.conflictId) });
    const card = cue.conflictId ? lookup(cue.conflictId, "conflicts") : null;
    return cue.type === "round"
      ? [PHASE_LABELS.round_start, round, conflict, card]
      : [round, PHASE_LABELS.combat, conflict, card];
  }
  if (cue.type === "scouts") {
    const item = scoutsItem(cue.itemId);
    return [round, t("panels.scouts_heading"),
      `${scoutsKindName(item.kind || cue.itemKind)} · ${item.name}`, null];
  }
  if (cue.type === "endgame") return [null, PHASE_LABELS.endgame, null, null];
  const player = ((state.view && state.view.players) || [])[cue.seat] || {};
  const faceId = player.leader_face_id || player.leader_id;
  const leader = faceId ? lookup(faceId, "leaders") : null;
  const leaderName = leader ? leader.name : faceId ? prettify(faceId) : null;
  if (isMine(cue.seat)) {
    /* One screen can hold several seats: then "your turn" says which. */
    const parts = [leaderName];
    if (mySeats().length > 1) parts.push(t("common.seat", { seat: cue.seat }));
    return [null, t("effects.banner_turn_mine"), parts.filter(Boolean).join(" · "), leader];
  }
  return [null, t("effects.banner_turn_other", { seat: cue.seat }),
    [leaderName, playerName(cue.seat)].filter(Boolean).join(" · "), leader];
}

function positionPhaseBanner() {
  const box = el("phase-banner");
  if (!box || box.hidden) return;
  const board = el("board").getBoundingClientRect();
  const room = window.innerWidth - 24;
  const width = Math.min(room, Math.max(340, Math.min(720, board.width - 24)));
  box.style.width = `${width}px`;
  const height = box.offsetHeight;
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const center = board.width ? board.left + board.width / 2 : window.innerWidth / 2;
  box.style.left = `${clamp(center - width / 2, 12, window.innerWidth - width - 12)}px`;
  /* Over the part of the board in sight, a third of the way down; with
     too little of it in sight (a stacked narrow layout scrolled away),
     a third of the way down the window. */
  const header = Math.max(0, document.querySelector("header").getBoundingClientRect().bottom);
  const above = Math.max(board.top, header);
  const below = Math.min(board.bottom, window.innerHeight);
  const top = below - above >= height + 24
    ? clamp(above + (below - above) * 0.35 - height / 2, above + 12, below - height - 12)
    : clamp(window.innerHeight * 0.3 - height / 2, header + 8, window.innerHeight - height - 12);
  box.style.top = `${Math.max(0, top)}px`;
}

function drawPhaseBanner() {
  const cue = phaseBanner.current;
  if (!cue) return;
  const [kicker, title, subtitle, art] = phaseBannerWords(cue);
  const box = el("phase-banner");
  box.textContent = "";
  box.hidden = false;
  box.dataset.language = TERM_LANGUAGE;
  const band = document.createElement("div");
  band.className = `phase-banner ${cue.type}`;
  band.dataset.cue = cue.type;
  if (cue.type === "turn") {
    band.dataset.seat = String(cue.seat);
    band.style.setProperty("--banner-color", SEAT_COLORS[cue.seat]);
    band.classList.toggle("mine", isMine(cue.seat));
    /* help.js announceTurn already says whose turn it is. */
    band.setAttribute("aria-hidden", "true");
  }
  band.style.setProperty("--banner-ms", `${phaseBanner.duration}ms`);
  /* A redraw (a language switch) carries on from where the band was. */
  band.style.animationDelay = `${-Math.round(performance.now() - phaseBanner.shownAt)}ms`;
  if (art && art.image) {
    const frame = document.createElement("div");
    frame.className = "phase-banner-art";
    const img = document.createElement("img");
    img.src = art.image;
    img.alt = art.name;
    img.draggable = false;
    frame.appendChild(img);
    band.appendChild(frame);
  }
  const words = document.createElement("div");
  words.className = "phase-banner-words";
  if (kicker) {
    const line = document.createElement("div");
    line.className = "phase-banner-kicker";
    line.textContent = kicker;
    words.appendChild(line);
  }
  const heading = document.createElement("strong");
  heading.className = "phase-banner-title";
  heading.textContent = title;
  words.appendChild(heading);
  if (subtitle) {
    const line = document.createElement("div");
    line.className = "phase-banner-subtitle";
    line.textContent = subtitle;
    words.appendChild(line);
  }
  band.appendChild(words);
  box.appendChild(band);
  positionPhaseBanner();
}

function nextPhaseBanner() {
  clearTimeout(phaseBanner.timer);
  phaseBanner.current = phaseBanner.queue.shift() || null;
  if (!phaseBanner.current) {
    clearPhaseBanner();
    return;
  }
  /* Three or more waiting go by faster; review fits them in its interval. */
  const waiting = phaseBanner.queue.length;
  phaseBanner.duration = state.review
    ? Math.max(300, Math.min(PHASE_BANNER_MS, playback.intervalMs / (waiting + 1)))
    : waiting >= 2 ? PHASE_BANNER_BUSY_MS : PHASE_BANNER_MS;
  phaseBanner.shownAt = performance.now();
  drawPhaseBanner();
  phaseBanner.timer = setTimeout(nextPhaseBanner, phaseBanner.duration);
}

function renderPhaseBanner() {
  if (!state.gameId || !state.view || el("game-screen").hidden) {
    resetPhaseBanner();
    return;
  }
  const review = state.review;
  const log = review ? reviewLog(review) : state.log;
  if (!log) return;
  const context = `${state.gameId}:${review ? `review:${review.seat}` : "live"}`;
  const turnKey = review ? null : turnStartKey(state.summary, log);
  if (phaseBanner.context !== context || log.count < phaseBanner.count) {
    // Joining, reloading, changing review seats or going backwards is a baseline.
    resetPhaseBanner();
    phaseBanner.context = context;
    phaseBanner.count = log.count;
    phaseBanner.turnKey = turnKey;
    return;
  }
  if (review && (!playback.playing || review.seek)) {
    clearPhaseBanner();
    phaseBanner.count = log.count;
    return;
  }
  /* An undo can take back a revealed step; a turn that has moved on (its
     seat already acting, or another seat's turn) no longer starts. The
     banner on screen finishes, unless its step was taken back. */
  const live = (cue) =>
    cue.type === "turn" ? cue.key === turnKey : !log.entries[cue.index]?.undone;
  phaseBanner.queue = phaseBanner.queue.filter(live);
  if (phaseBanner.current && phaseBanner.current.type !== "turn" && !live(phaseBanner.current)) {
    clearTimeout(phaseBanner.timer);
    phaseBanner.current = null;
  }
  phaseBanner.queue.push(...phaseBannerCues(log.entries, phaseBanner.count));
  phaseBanner.count = log.count;
  if (turnKey && turnKey !== phaseBanner.turnKey) {
    /* Only the newest turn start is news: an AI batch ending on this
       screen's turn shows that turn alone. */
    phaseBanner.queue = phaseBanner.queue.filter((cue) => cue.type !== "turn");
    phaseBanner.queue.push({ type: "turn", key: turnKey, seat: state.summary.decision.owner });
  }
  if (turnKey) phaseBanner.turnKey = turnKey;
  if (!phaseBanner.current) nextPhaseBanner();
  else if (el("phase-banner").dataset.language !== TERM_LANGUAGE) drawPhaseBanner();
  else positionPhaseBanner();
}
