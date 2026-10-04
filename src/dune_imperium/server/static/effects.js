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
