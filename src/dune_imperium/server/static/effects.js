"use strict";

/* Card-use cues consume only events already filtered for the viewer in the
   session log. Never scan hands, draws, chance outcomes or arbitrary action
   arguments for cards. A whole AI batch can arrive in one snapshot.

   The card cues and the banners below take turns on screen, in log order
   (advanceEffects): a seat's turn banner, then the cards of that turn,
   then the next seat's banner. Every cue carries the log index it comes
   from and its event's position there (`order`), and a turn banner comes
   before the steps of its turn (order -1). */
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
  applyCueSpace();
}

function resetPlayEffects() {
  clearPlayEffects();
  playEffects.context = null;
  playEffects.count = 0;
}

/* A Reveal: the hand the seat revealed (cards_revealed, a public event
   the engine reports without keeping) and its Persuasion and strength
   (reveal_started), as one cue. */
const REVEAL_EVENTS = new Set(["reveal_started", "cards_revealed"]);

function cardPlayCues(entries) {
  const cues = [];
  for (const entry of entries) {
    if (entry.undone || entry.type === "undo") continue;
    let reveal = null;
    for (const [position, event] of (entry.events || []).entries()) {
      if (REVEAL_EVENTS.has(event.kind)) {
        const payload = event.payload || {};
        if (!Number.isInteger(payload.player) || payload.player < 0 || payload.player > 3) {
          continue;
        }
        if (!reveal) {
          reveal = { index: entry.index, order: position, kind: "reveal",
            seat: payload.player, cards: [], persuasion: null, strength: null };
          cues.push(reveal);
        }
        if (event.kind === "reveal_started") {
          reveal.persuasion = payload.persuasion;
          reveal.strength = payload.strength;
        } else if (typeof payload.card_ids === "string") {
          reveal.cards = payload.card_ids.split(",").filter((id) => entryOf(id, "cards"));
        }
        continue;
      }
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
        order: position,
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

/* The revealed hand fanned out under the seat's name, with what it adds
   up to. */
function drawRevealEffect(cue) {
  const box = el("play-effects");
  box.textContent = "";
  box.hidden = false;
  const toast = document.createElement("div");
  toast.className = "play-effect reveal";
  toast.dataset.seat = String(cue.seat);
  toast.style.setProperty("--play-color", SEAT_COLORS[cue.seat]);
  const words = document.createElement("div");
  words.className = "play-effect-words";
  const player = document.createElement("div");
  player.className = "play-effect-player";
  player.textContent = playerLabel(cue.seat);
  const type = document.createElement("div");
  type.className = "play-effect-type";
  type.textContent = termLabel("reveal_turn");
  words.append(player, type);
  const fan = document.createElement("div");
  fan.className = "reveal-fan";
  fan.style.setProperty("--fan-count", String(Math.max(1, cue.cards.length)));
  cue.cards.forEach((id, position) => {
    const entry = entryOf(id, "cards");
    const card = document.createElement("div");
    card.className = "reveal-card";
    card.dataset.card = id;
    card.style.setProperty("--fan-at", String(position - (cue.cards.length - 1) / 2));
    if (entry.image) {
      const img = document.createElement("img");
      img.src = entry.image;
      img.alt = entry.name;
      img.draggable = false;
      card.appendChild(img);
    } else {
      card.classList.add("textcard");
      card.textContent = entry.name;
    }
    fan.appendChild(card);
  });
  const totals = document.createElement("div");
  totals.className = "reveal-totals";
  if (Number.isInteger(cue.persuasion)) {
    totals.appendChild(amount("persuasion", termLabel("persuasion"), cue.persuasion));
  }
  if (Number.isInteger(cue.strength)) {
    if (totals.childNodes.length) totals.append(" · ");
    totals.appendChild(amount("sword", phraseText("{strength}"), cue.strength));
  }
  toast.append(words, fan, totals);
  box.appendChild(toast);
  positionPlayEffect();
  applyCueSpace();
}

function drawPlayEffect() {
  const cue = playEffects.current;
  if (!cue) return;
  if (cue.kind === "reveal") {
    drawRevealEffect(cue);
    return;
  }
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
  applyCueSpace();
}

/* While an Agent card's cue is on screen, the space it went to glows in
   the seat's colour, so the eye finds the Agent on the board. The board
   is drawn again on every render, so renderEffects applies it again. */
function applyCueSpace() {
  for (const node of document.querySelectorAll("#board .hotspot.cue-space")) {
    node.classList.remove("cue-space");
    node.style.removeProperty("--cue-color");
  }
  const cue = playEffects.current;
  if (!cue || !cue.spaceId) return;
  const hotspot = document.querySelector(
    `#board .hotspot[data-space="${CSS.escape(cue.spaceId)}"]`,
  );
  if (!hotspot) return;
  hotspot.classList.add("cue-space");
  hotspot.style.setProperty("--cue-color", SEAT_COLORS[cue.seat]);
}

/* Show the next card cue now, whatever else is on screen (advanceEffects
   decides when). */
function nextPlayEffect() {
  clearTimeout(playEffects.timer);
  playEffects.current = playEffects.queue.shift() || null;
  if (!playEffects.current) {
    clearPlayEffects();
    return;
  }
  drawPlayEffect();
  // Shorten busy batches without delaying the game or dropping card plays.
  const waiting = effectsWaiting();
  const duration = state.review
    ? Math.max(200, Math.min(2200, playback.intervalMs / (waiting + 1)))
    : (waiting > 4 ? 1200 : 2200) * cueScale();
  playEffects.timer = setTimeout(endPlayEffect, duration);
}

function hidePlayEffect() {
  clearTimeout(playEffects.timer);
  playEffects.timer = 0;
  playEffects.current = null;
  const box = el("play-effects");
  if (box) {
    box.hidden = true;
    box.textContent = "";
  }
  applyCueSpace();
}

function endPlayEffect() {
  hidePlayEffect();
  advanceEffects();
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
  if (playEffects.current && !live(playEffects.current)) hidePlayEffect();
  playEffects.queue.push(...cardPlayCues(log.entries.slice(playEffects.count)));
  playEffects.count = log.count;
  if (playEffects.current) {
    // A language switch updates the current art and caption, without requeueing.
    const shown = el("play-effects").querySelector(".play-effect-art img");
    const entry = playEffects.current.kind === "reveal" ? null
      : entryOf(playEffects.current.cardId, playEffects.current.kind);
    if ((shown && entry && shown.getAttribute("src") !== entry.image)
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
   viewer-filtered log events as the cues above, in log order. The lifecycle
   is the card-use cues' own: joining, reloading or changing the review
   seat is a baseline, an undone entry drops its cue, and leaving the table
   clears everything.

   A turn banner comes from two places. The summary names the turn that
   starts now, for this screen's seats and anyone else the game waits on.
   The log names every turn taken since, so an AI seat's turn, answered
   inside the request that handed it the decision, has its banner too ("AI
   차례가 될 때도 플레이어 차례처럼 안내 이펙트가 있어야 해", user,
   2026-10-08). Both key a turn by "<seat>:<log index of the last turn
   end>", so each turn is announced once.

   When the rewards of a Conflict begin, the engine logs the whole standing
   (combat_standing, one public event per seat in the Conflict) and a
   result board shows it ("전투 단계 종료 때 전투 최종 순위도 그렇게
   보여지면 좋겠고", user, 2026-10-08). It stays longer than a band, and a
   click or Escape closes it. So does the final standings board when the
   game ends. A summoned sandworm and a destroyed Shield Wall get a band of
   their own. */
const PHASE_BANNER_MS = 1600;
const PHASE_BANNER_BUSY_MS = 900;
const RESULT_BOARD_MS = 3200;
const RESULT_BOARD_BUSY_MS = 2400;
const FINAL_BOARD_MS = 6000;
const FINAL_BOARD_BUSY_MS = 4000;

/* The boards that list seats, stay longer and close on a click. */
const BOARD_CUES = new Set(["result", "final"]);
const SANDWORM_EVENTS = new Set(["sandworm_deployed", "reveal_sandworm_deployed"]);

/* The steps that end a turn (panels.js QUIET_ACTIONS lists them too). A
   seat's turn frame after one of them is a new turn, even its own again;
   the same frame met again after a turn-start Plot is the same turn. */
const TURN_END_ACTION_IDS = new Set(["finish_agent_turn", "finish_reveal"]);

/* The steps that take a turn: an Agent sent, a Reveal, a turn-passing
   card (render.js OWN_TURN_ACTION_IDS). */
const TURN_TAKING_ACTION_IDS = new Set(["agent_turn", "reveal_turn", "play_turn_start_card"]);

/* Events after which a seat's earlier steps belong to no turn still to
   come: a phase of its own opens, or the turn-passing card passed it. */
const TURN_BOUNDARY_EVENTS = new Set([
  "conflict_revealed",
  "combat_intrigue_started",
  "combat_intrigue_finished",
  "combat_standing",
  "scouts_item_revealed",
  "endgame_started",
  "turn_passed",
]);

const phaseBanner = {
  context: null,
  count: 0,
  turnKey: null,
  /* Every turn announced or queued since the baseline. */
  turnKeys: new Set(),
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
  phaseBanner.turnKeys = new Set();
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

/* The cues of the log entries from `from` on. The whole log is read so a
   turn taken now is keyed by the turn end before it and placed at its
   seat's first step since (a Plot played at the turn's start comes after
   the banner). */
function phaseBannerCues(entries, from) {
  const cues = [];
  let conflict;
  let ended = -1;
  /* Each seat's first step since the last turn end or phase boundary. */
  let opened = new Map();
  for (const entry of entries) {
    if (entry.undone || entry.type === "undo") continue;
    const fresh = entry.index >= from;
    if (entry.type === "action" && !opened.has(entry.actor)) opened.set(entry.actor, entry.index);
    if (fresh && entry.type === "action" && TURN_TAKING_ACTION_IDS.has(entry.action_id)) {
      cues.push({
        type: "turn",
        source: "log",
        key: `${entry.actor}:${ended}`,
        seat: entry.actor,
        index: opened.get(entry.actor),
        order: -1,
        entry: entry.index,
      });
    }
    let standing = null;
    for (const [position, event] of (entry.events || []).entries()) {
      if (TURN_BOUNDARY_EVENTS.has(event.kind)) opened = new Map();
      if (!fresh) continue;
      const payload = event.payload || {};
      const at = { index: entry.index, order: position };
      if (event.kind === "conflict_revealed") {
        conflict = { id: payload.conflict_id, round: payload.round };
        cues.push({ type: "round", ...at, round: payload.round, conflictId: payload.conflict_id });
      } else if (event.kind === "combat_intrigue_started") {
        if (conflict === undefined) conflict = conflictBefore(entries, entry.index);
        cues.push({
          type: "combat",
          ...at,
          round: conflict ? conflict.round : null,
          conflictId: conflict ? conflict.id : null,
        });
      } else if (event.kind === "combat_standing" && Number.isInteger(payload.player)) {
        if (!standing) {
          if (conflict === undefined) conflict = conflictBefore(entries, entry.index);
          standing = {
            type: "result",
            ...at,
            round: conflict && conflict.id === payload.conflict_id ? conflict.round : null,
            conflictId: payload.conflict_id,
            rows: [],
          };
          cues.push(standing);
        }
        standing.rows.push({
          seat: payload.player,
          rank: payload.rank,
          strength: payload.strength,
          multiplier: payload.multiplier,
        });
      } else if (event.kind === "scouts_item_revealed" && typeof payload.item_id === "string") {
        cues.push({
          type: "scouts",
          ...at,
          round: payload.round,
          itemId: payload.item_id,
          itemKind: payload.kind,
        });
      } else if (event.kind === "endgame_started") {
        cues.push({ type: "endgame", ...at });
      } else if (SANDWORM_EVENTS.has(event.kind) && Number.isInteger(payload.player)) {
        /* Several worms of one seat in one step are one band. */
        const count = Number.isInteger(payload.count) ? payload.count
          : Number.isInteger(payload.amount) ? payload.amount : 1;
        const last = cues[cues.length - 1];
        if (last && last.type === "sandworm" && last.index === entry.index
          && last.seat === payload.player) last.count += count;
        else cues.push({ type: "sandworm", ...at, seat: payload.player, count });
      } else if (event.kind === "shield_wall_destroyed") {
        cues.push({ type: "shield_wall", ...at });
      } else if (event.kind === "game_finished") {
        cues.push({ type: "final", ...at });
      }
    }
    if (entry.type === "action" && TURN_END_ACTION_IDS.has(entry.action_id)) {
      ended = entry.index;
      opened = new Map();
    }
  }
  return cues;
}

function conflictName(conflictId) {
  const entry = conflictId ? lookup(conflictId, "conflicts") : null;
  return entry ? entry.name : conflictId ? prettify(conflictId) : termLabel("conflict");
}

/* Whether a turn cue is this screen's own. A review watches a finished
   game from one seat; its banners all name the seat. */
function ownTurnCue(cue) {
  return cue.type === "turn" && !state.review && isMine(cue.seat);
}

function seatLeader(seat) {
  const player = ((state.view && state.view.players) || [])[seat] || {};
  const faceId = player.leader_face_id || player.leader_id;
  const leader = faceId ? lookup(faceId, "leaders") : null;
  return { leader, name: leader ? leader.name : faceId ? prettify(faceId) : null };
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
  if (cue.type === "result") {
    const card = cue.conflictId ? lookup(cue.conflictId, "conflicts") : null;
    return [round, t("effects.result_title"),
      t("effects.banner_conflict", { name: conflictName(cue.conflictId) }), card];
  }
  if (cue.type === "scouts") {
    const item = scoutsItem(cue.itemId);
    return [round, t("panels.scouts_heading"),
      `${scoutsKindName(item.kind || cue.itemKind)} · ${item.name}`, null];
  }
  if (cue.type === "endgame") return [null, PHASE_LABELS.endgame, null, null];
  if (cue.type === "shield_wall") return [null, t("effects.banner_shield_wall"), null, null];
  if (cue.type === "final") {
    const winner = finalRows()[0];
    const named = winner ? seatLeader(winner.seat) : { leader: null, name: null };
    const who = winner ? [named.name, playerLabel(winner.seat)].filter(Boolean).join(" · ") : null;
    return [t("common.game_over"), t("effects.final_title"),
      who ? t("effects.final_winner", { name: who }) : null, named.leader];
  }
  const { leader, name: leaderName } = seatLeader(cue.seat);
  if (cue.type === "sandworm") {
    return [playerLabel(cue.seat),
      cue.count > 1 ? t("effects.banner_sandworms", { count: cue.count })
        : t("effects.banner_sandworm"),
      leaderName, null];
  }
  if (ownTurnCue(cue)) {
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

const RESULT_RANK_KEYS = {
  1: "render.combat_result_rank_1",
  2: "render.combat_result_rank_2",
  3: "render.combat_result_rank_3",
};

/* The final standings (the finished summary's), best first. */
function finalRows() {
  const standings = (state.summary && state.summary.standings) || [];
  return standings.map((entry) => ({ seat: entry.player, rank: entry.rank,
    points: entry.victory_points }));
}

const FINAL_RANK_KEYS = { ...RESULT_RANK_KEYS, 4: "effects.rank_4" };

/* One row per seat, as a board lists them: rank, colour, Leader and
   player, and `value` (its nodes). */
function boardRow(seat, rankText, ranked, value) {
  const line = document.createElement("div");
  line.className = "phase-result-row";
  line.dataset.seat = String(seat);
  line.style.setProperty("--seat-color", SEAT_COLORS[seat]);
  line.classList.toggle("mine", !state.review && isMine(seat));
  line.classList.toggle("unranked", !ranked);
  const rank = document.createElement("span");
  rank.className = "phase-result-rank";
  rank.textContent = rankText;
  const chip = document.createElement("span");
  chip.className = "phase-result-chip";
  /* The Leader is who a seat is on the table (the seat panels lead with
     it); the player follows, smaller. */
  const who = document.createElement("span");
  who.className = "phase-result-player";
  const leader = seatLeader(seat).name;
  const small = document.createElement("small");
  small.textContent = playerLabel(seat);
  if (leader) who.append(leader, " ", small);
  else who.textContent = playerLabel(seat);
  const amountBox = document.createElement("span");
  amountBox.className = "phase-result-strength";
  amountBox.append(...value);
  line.append(rank, chip, who, amountBox);
  return line;
}

function finalBoardRows() {
  const list = document.createElement("div");
  list.className = "phase-result-rows";
  for (const row of finalRows()) {
    const line = boardRow(row.seat, t(FINAL_RANK_KEYS[row.rank] || "effects.rank_4"),
      true, [amount("victory_point", phraseText("{victory_point}"), row.points)]);
    line.dataset.rank = String(row.rank);
    list.appendChild(line);
  }
  return list;
}

/* The standing, one row per seat in the Conflict, as the engine lists it:
   reward rows in rank order, then the seats left without one. */
function resultRows(cue) {
  const list = document.createElement("div");
  list.className = "phase-result-rows";
  for (const row of cue.rows) {
    const ranked = Boolean(RESULT_RANK_KEYS[row.rank]);
    const value = [amount("sword", phraseText("{strength}"), row.strength)];
    if (row.multiplier > 1) {
      const doubled = document.createElement("span");
      doubled.className = "phase-result-double";
      doubled.title = t("effects.result_double");
      doubled.append(termNode("sandworm"), ` ×${row.multiplier}`);
      value.push(" ", doubled);
    }
    const line = boardRow(row.seat,
      ranked ? t(RESULT_RANK_KEYS[row.rank]) : t("effects.result_unranked"), ranked, value);
    line.dataset.rank = String(row.rank);
    list.appendChild(line);
  }
  return list;
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
  if (cue.type === "sandworm") {
    band.dataset.seat = String(cue.seat);
    band.style.setProperty("--seat-color", SEAT_COLORS[cue.seat]);
  }
  if (cue.type === "turn") {
    band.dataset.seat = String(cue.seat);
    band.style.setProperty("--banner-color", SEAT_COLORS[cue.seat]);
    band.classList.toggle("mine", ownTurnCue(cue));
    /* help.js announceTurn already says whose turn it is. */
    band.setAttribute("aria-hidden", "true");
  }
  band.style.setProperty("--banner-ms", `${phaseBanner.duration}ms`);
  /* A redraw (a language switch) carries on from where the band was. */
  band.style.animationDelay = `${-Math.round(performance.now() - phaseBanner.shownAt)}ms`;
  if (cue.type === "sandworm" || cue.type === "shield_wall") {
    const frame = document.createElement("div");
    frame.className = "phase-banner-art phase-banner-icon";
    frame.appendChild(icon(cue.type, termLabel(cue.type)));
    band.appendChild(frame);
  } else if (art && art.image) {
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
  if (BOARD_CUES.has(cue.type)) {
    words.appendChild(cue.type === "result" ? resultRows(cue) : finalBoardRows());
    const hint = document.createElement("div");
    hint.className = "phase-result-hint";
    hint.textContent = t("effects.result_close");
    words.appendChild(hint);
    band.title = t("effects.result_close");
    band.addEventListener("click", endPhaseBanner);
  }
  band.appendChild(words);
  box.appendChild(band);
  positionPhaseBanner();
}

/* Show the next banner now, whatever else is on screen (advanceEffects
   decides when). Three or more cues waiting go by faster; review fits
   them in its interval. */
function nextPhaseBanner() {
  clearTimeout(phaseBanner.timer);
  phaseBanner.current = phaseBanner.queue.shift() || null;
  if (!phaseBanner.current) {
    clearPhaseBanner();
    return;
  }
  const waiting = effectsWaiting();
  const type = phaseBanner.current.type;
  const [full, busy] = type === "result" ? [RESULT_BOARD_MS, RESULT_BOARD_BUSY_MS]
    : type === "final" ? [FINAL_BOARD_MS, FINAL_BOARD_BUSY_MS]
    : [PHASE_BANNER_MS, PHASE_BANNER_BUSY_MS];
  phaseBanner.duration = state.review
    ? Math.max(300, Math.min(full, playback.intervalMs / (waiting + 1)))
    : (waiting >= 2 ? busy : full) * cueScale();
  phaseBanner.shownAt = performance.now();
  drawPhaseBanner();
  /* A Round, combat or Scouts banner sounds once, as it appears. */
  playPhaseSound(phaseBanner.current);
  phaseBanner.timer = setTimeout(endPhaseBanner, phaseBanner.duration);
}

function hidePhaseBanner() {
  clearTimeout(phaseBanner.timer);
  phaseBanner.timer = 0;
  phaseBanner.current = null;
  const box = el("phase-banner");
  if (box) {
    box.hidden = true;
    box.textContent = "";
  }
}

function endPhaseBanner() {
  hidePhaseBanner();
  advanceEffects();
}

/* Escape closes a result or final board on screen; returns whether it did. */
function closeResultBoard() {
  if (!phaseBanner.current || !BOARD_CUES.has(phaseBanner.current.type)) return false;
  endPhaseBanner();
  return true;
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
    if (turnKey) phaseBanner.turnKeys.add(turnKey);
    return;
  }
  if (review && (!playback.playing || review.seek)) {
    clearPhaseBanner();
    phaseBanner.count = log.count;
    return;
  }
  /* An undo can take back a revealed step. A turn the summary announced
     stops being news once it has moved on (its seat already acting, or
     another seat's turn): its banner leaves the screen, so the seat's
     first card shows at once. Another seat's turn that moved on before its
     banner came up is left to the log, which announces it with its steps. */
  const live = (cue) => cue.source === "summary"
    ? cue.key === turnKey
    : !log.entries[cue.entry ?? cue.index]?.undone;
  for (const cue of phaseBanner.queue) {
    if (cue.source === "summary" && !live(cue) && !isMine(cue.seat)) {
      phaseBanner.turnKeys.delete(cue.key);
    }
  }
  phaseBanner.queue = phaseBanner.queue.filter(live);
  if (phaseBanner.current && !live(phaseBanner.current)) hidePhaseBanner();
  for (const cue of phaseBannerCues(log.entries, phaseBanner.count)) {
    if (cue.type === "turn") {
      if (phaseBanner.turnKeys.has(cue.key)) continue;
      phaseBanner.turnKeys.add(cue.key);
    }
    phaseBanner.queue.push(cue);
  }
  if (turnKey && !phaseBanner.turnKeys.has(turnKey)) {
    phaseBanner.turnKeys.add(turnKey);
    phaseBanner.queue.push({
      type: "turn",
      source: "summary",
      key: turnKey,
      seat: state.summary.decision.owner,
      /* Before whatever the seat does next. */
      index: log.count,
      order: -1,
    });
  }
  phaseBanner.count = log.count;
  if (turnKey) phaseBanner.turnKey = turnKey;
  phaseBanner.queue.sort((a, b) => (cueBefore(a, b) ? -1 : cueBefore(b, a) ? 1 : 0));
  if (phaseBanner.current && el("phase-banner").dataset.language !== TERM_LANGUAGE) {
    drawPhaseBanner();
  } else positionPhaseBanner();
}

/* ---------- changes on the seat panels ----------

   When a seat's Victory Points, Solari, spice or water change, the change
   rises over that number on its seat panel ("+2", "−1"), so a gain made on
   the board is seen where it lands. Read from the view the page holds,
   whose numbers every seat sees; a new game, an undo, a reload or a review
   is a new baseline, and a review shows none. */
const STAT_READERS = {
  victory_point: (player) => player.victory_points,
  solari: (player) => player.resources.solari,
  spice: (player) => player.resources.spice,
  water: (player) => player.resources.water,
};
const statFloats = { context: null, values: null };

function statValues(view) {
  return ((view && view.players) || []).map((player) => Object.fromEntries(
    Object.entries(STAT_READERS).map(([key, read]) => [key, read(player)]),
  ));
}

function floatStat(seat, key, delta) {
  const stat = document.querySelector(
    `#seats .seat[data-seat="${seat}"] .stat[data-stat="${key}"]`,
  );
  const rect = stat && stat.getBoundingClientRect();
  if (!rect || !rect.width) return;
  const chip = document.createElement("div");
  chip.className = `stat-float ${delta > 0 ? "gain" : "loss"}`;
  chip.dataset.seat = String(seat);
  chip.dataset.stat = key;
  chip.textContent = `${delta > 0 ? "+" : "\u2212"}${Math.abs(delta)}`;
  chip.style.left = `${rect.left + rect.width / 2}px`;
  chip.style.top = `${rect.top}px`;
  el("stat-floats").appendChild(chip);
  const drop = () => chip.remove();
  chip.addEventListener("animationend", drop, { once: true });
  setTimeout(drop, 2500);
}

function resetStatFloats() {
  statFloats.context = null;
  statFloats.values = null;
  const box = el("stat-floats");
  if (box) box.textContent = "";
}

function renderStatFloats() {
  if (!state.gameId || !state.view || state.review || el("game-screen").hidden) {
    resetStatFloats();
    return;
  }
  const context = `${state.gameId}:${state.summary ? state.summary.undo_count : 0}`;
  const values = statValues(state.view);
  const before = statFloats.context === context ? statFloats.values : null;
  statFloats.context = context;
  statFloats.values = values;
  if (!before) return;
  values.forEach((now, seat) => {
    for (const [key, value] of Object.entries(now)) {
      const was = before[seat] ? before[seat][key] : value;
      if (typeof was === "number" && value !== was) floatStat(seat, key, value - was);
    }
  });
}

/* ---------- one order for every cue ---------- */

/* A fast-paced game (server/pacing.py PACE_SCALE) shows every cue for the
   share of its length the server waits for it. */
const PACE_CUE_SCALE = { fast: 0.6 };

function cueScale() {
  return (state.summary && PACE_CUE_SCALE[state.summary.ai_pace]) || 1;
}

function effectsWaiting() {
  return playEffects.queue.length + phaseBanner.queue.length;
}

function cueBefore(a, b) {
  return a.index !== b.index ? a.index < b.index : (a.order || 0) < (b.order || 0);
}

/* With nothing on screen, show whichever cue comes first in the log. */
function advanceEffects() {
  if (playEffects.current || phaseBanner.current) return;
  const card = playEffects.queue[0];
  const band = phaseBanner.queue[0];
  if (band && (!card || cueBefore(band, card))) nextPhaseBanner();
  else if (card) nextPlayEffect();
}

function renderEffects() {
  renderPlayEffects();
  renderPhaseBanner();
  advanceEffects();
  /* The board and the seat panels were drawn again before this. */
  applyCueSpace();
  renderStatFloats();
}
