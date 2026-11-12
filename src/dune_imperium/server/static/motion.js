"use strict";

/* ---------- pieces that move between places ----------

   The effects UI stage 12 left for a later batch (docs/ui-improvement-plan.md
   section 12, user request 2026-11-10), all drawn from what the page
   already holds -- the viewer-filtered log's public events and the views --
   so the engine, its events and the server's pacing stay as they were:

   ③ a bought card flies from the shared cards to the buying seat's panel
     (card_acquired, tleilaxu_card_acquired, scouts_card_bought: every
     acquisition is public, OQ-010 and OQ-145, and the log line names the
     card anyway);
   ⑤ an Alliance token leaves its strip for the seat that earned it, under
     the alliance banner (effects.js), and an Influence cube slides along its
     strip when its level changes (slideInfluenceCubes);
   ⑦ the Conflict card goes from its slot to the winner who keeps it
     (conflict_won; on the original board the cards stay where they were
     revealed [DI p. 8], so none moves there);
   ⑧ the round's cleanup: bonus spice lands on each Maker space
     (maker_spice_added), every Agent flies home and the First Player
     marker passes on (agents_recalled).

   A move is a cue in the one log order advanceEffects keeps (effects.js):
   it starts when the cues before it have finished, and holds the next one
   only briefly (MOTION_HOLD_MS), so it never holds a turn or a decision and
   adds to nothing the server waits for. Its pieces fly in their own layer
   (#fx-layer) over the table and take no clicks. When the place a piece
   comes from or goes to is out of sight (a hidden panel, another phone
   view) the flight starts from the board or ends at the panel's toggle or
   tab; with nothing in sight it simply fades.

   ⑩ The viewer can turn every effect off (help panel, effectsOff below):
   remembered in this browser, like the column widths. */

const EFFECTS_OFF_KEY = "dune.effectsOff";
let effectsOffSetting = null;

/* Whether this viewer turned the table's effects off. */
function effectsOff() {
  if (effectsOffSetting === null) effectsOffSetting = storageGet(EFFECTS_OFF_KEY) === "1";
  return effectsOffSetting;
}

function setEffectsOff(off) {
  effectsOffSetting = Boolean(off);
  if (effectsOffSetting) storageSet(EFFECTS_OFF_KEY, "1");
  else storageRemove(EFFECTS_OFF_KEY);
  /* What was waiting goes quietly: the switch itself makes no sound. */
  if (effectsOffSetting) quietEffects(false);
}

/* With effects off, whatever is on screen or waiting goes, and new cues
   are dropped as they come (renderEffects); the counts stay, so turning
   them on again replays nothing. A phase banner that just came still
   sounds once (`sound`): the setting is about the screen. */
function quietEffects(sound = true) {
  playEffects.queue = [];
  if (playEffects.current) hidePlayEffect();
  const sounding = sound && phaseBanner.queue.find((cue) => PHASE_SOUNDS[cue.type]);
  phaseBanner.queue = [];
  if (phaseBanner.current) hidePhaseBanner();
  if (sounding) playPhaseSound(sounding);
  motion.queue = [];
  if (motion.current) hideMotion();
  const floats = el("stat-floats");
  if (floats) floats.textContent = "";
}

/* How long each move holds the next cue, and how long it flies (full
   length; a fast-paced game scales both like every cue, cueScale). */
const MOTION_HOLD_MS = { buy: 450, conflict: 950, makers: 700, recall: 1000 };
const MOTION_FLY_MS = { buy: 850, conflict: 950, makers: 1100, recall: 900, alliance: 1100 };
const MOTION_BUSY = 4;

/* An Arrakeen Scouts auction's card is bought too (scouts_card_bought,
   named by its instance alone). */
const BUY_EVENTS = new Set(["card_acquired", "tleilaxu_card_acquired", "scouts_card_bought"]);

const motion = {
  context: null,
  count: 0,
  queue: [],
  current: null,
  timer: 0,
  /* What the page showed at the end of the last render: each Agent on the
     board ({seat, space}), the shared cards ({id, image, rect}) and each
     Influence cube ("<seat>:<faction>" -> {level, rect}). */
  agents: null,
  cards: [],
  cubes: null,
  /* The game, review seat and undo count the cubes were last seen in. */
  cubeContext: null,
};

function validSeat(seat) {
  return Number.isInteger(seat) && seat >= 0 && seat <= 3;
}

function clearMotion() {
  clearTimeout(motion.timer);
  motion.timer = 0;
  motion.queue = [];
  motion.current = null;
  const layer = el("fx-layer");
  if (layer) layer.textContent = "";
}

function resetMotion() {
  clearMotion();
  motion.context = null;
  motion.count = 0;
  motion.agents = null;
  motion.cards = [];
  motion.cubes = null;
}

/* The moves of the log entries given, in log order. Agents are followed
   through them from the board last shown, so a recall in the same batch
   as the placements before it sends every one of them home. */
function motionCues(entries) {
  const cues = [];
  let agents = (motion.agents || []).slice();
  for (const entry of entries) {
    if (entry.undone || entry.type === "undo") continue;
    let makers = null;
    for (const [position, event] of (entry.events || []).entries()) {
      const payload = event.payload || {};
      const at = { index: entry.index, order: position };
      if (event.kind === "agent_placed" && validSeat(payload.player)
        && typeof payload.space_id === "string") {
        agents.push({ seat: payload.player, space: payload.space_id });
      } else if (event.kind === "agent_recalled" && validSeat(payload.player)) {
        const found = agents.findIndex((agent) => agent.seat === payload.player
          && agent.space === payload.space_id);
        if (found >= 0) agents.splice(found, 1);
      } else if (BUY_EVENTS.has(event.kind) && validSeat(payload.player)
        && boughtCardId(payload) && entryOf(boughtCardId(payload), "cards")) {
        cues.push({
          type: "buy",
          ...at,
          seat: payload.player,
          cardId: boughtCardId(payload),
          destination: payload.destination || "discard",
          origin: shownCardRect(payload.instance_id, boughtCardId(payload)),
        });
      } else if (event.kind === "conflict_won" && validSeat(payload.player)
        && typeof payload.conflict_id === "string" && keepsConflict(payload)) {
        cues.push({ type: "conflict", ...at, seat: payload.player, conflictId: payload.conflict_id });
      } else if (event.kind === "maker_spice_added" && typeof payload.space_id === "string") {
        /* Every Maker space of one step lands at once. */
        if (!makers) {
          makers = { type: "makers", ...at, spaces: [] };
          cues.push(makers);
        }
        makers.spaces.push(payload.space_id);
      } else if (event.kind === "agents_recalled") {
        cues.push({
          type: "recall",
          ...at,
          agents,
          firstPlayer: validSeat(payload.first_player) ? payload.first_player : null,
        });
        agents = [];
      }
    }
  }
  return cues;
}

function boughtCardId(payload) {
  if (typeof payload.card_id === "string") return payload.card_id;
  return typeof payload.instance_id === "string" ? payload.instance_id : null;
}

/* Uprising's winner keeps the card (won_conflict_ids); the original
   game's stay on the board. */
function keepsConflict(payload) {
  const player = ((state.view && state.view.players) || [])[payload.player];
  return Boolean(player && (player.won_conflict_ids || []).includes(payload.conflict_id));
}

/* Where the shared cards showed the bought card before this render: the
   copy itself, else a card of the same face (a Reserve pile shows one copy
   for all). Null when it was not in sight. */
function shownCardRect(instanceId, cardId) {
  const entry = entryOf(cardId, "cards");
  const found = motion.cards.find((card) => card.id === instanceId)
    || motion.cards.find((card) => card.id === cardId)
    || (entry && entry.image && motion.cards.find((card) => card.image === entry.image));
  return found ? found.rect : null;
}

function renderMotion() {
  if (!state.gameId || !state.view || el("game-screen").hidden) {
    resetMotion();
    return;
  }
  const review = state.review;
  const log = review ? reviewLog(review) : state.log;
  if (!log) return;
  const context = `${state.gameId}:${review ? `review:${review.seat}` : "live"}`;
  if (motion.context !== context || log.count < motion.count) {
    // Joining, reloading, changing review seats or going backwards is a baseline.
    clearMotion();
    motion.context = context;
    motion.count = log.count;
    return;
  }
  if (review && (!playback.playing || review.seek)) {
    clearMotion();
    motion.count = log.count;
    return;
  }
  // An undo can take back the step a waiting move came from.
  const live = (cue) => !log.entries[cue.index]?.undone;
  motion.queue = motion.queue.filter(live);
  if (motion.current && !live(motion.current)) hideMotion();
  motion.queue.push(...motionCues(log.entries.slice(motion.count)));
  motion.count = log.count;
}

/* After every render: what the page shows now is the next render's
   "before". */
function captureMotionBaseline() {
  const view = state.view;
  motion.agents = [];
  for (const [index, player] of ((view && view.players) || []).entries()) {
    const seat = Number.isInteger(player.player) ? player.player : index;
    for (const space of player.agent_locations || []) motion.agents.push({ seat, space });
  }
  motion.cards = [];
  for (const card of document.querySelectorAll("#market .vcard[data-instance]")) {
    const rect = card.getBoundingClientRect();
    if (!rect.width) continue;
    const image = card.querySelector("img");
    motion.cards.push({ id: card.dataset.instance, image: image ? image.getAttribute("src") : null,
      rect: plainRect(rect) });
  }
  /* Each cube's level only: where it stood is the board's printed spot for
     that level (slideInfluenceCubes), not a box measured here. */
  motion.cubes = new Map();
  for (const cube of document.querySelectorAll("#board .track-cube[data-faction]")) {
    motion.cubes.set(`${cube.dataset.seat}:${cube.dataset.faction}`, cube.dataset.level);
  }
}

/* ---------- showing a move ---------- */

function motionScale(type) {
  const waiting = effectsWaiting();
  const busy = waiting > MOTION_BUSY ? 0.6 : 1;
  return { hold: MOTION_HOLD_MS[type] * busy * cueScale(), fly: MOTION_FLY_MS[type] * busy * cueScale() };
}

/* Start the next move now (advanceEffects decides when). */
function nextMotion() {
  clearTimeout(motion.timer);
  const cue = motion.queue.shift() || null;
  motion.current = cue;
  if (!cue) return;
  let { hold, fly } = motionScale(cue.type);
  if (state.review) {
    const share = playback.intervalMs / (effectsWaiting() + 1);
    hold = Math.max(150, Math.min(hold, share));
    fly = Math.max(250, Math.min(fly, share * 1.5));
  }
  launchMotion(cue, fly);
  motion.timer = setTimeout(endMotion, hold);
}

function hideMotion() {
  clearTimeout(motion.timer);
  motion.timer = 0;
  motion.current = null;
  const layer = el("fx-layer");
  if (layer) layer.textContent = "";
}

function endMotion() {
  clearTimeout(motion.timer);
  motion.timer = 0;
  motion.current = null;
  advanceEffects();
}

function launchMotion(cue, fly) {
  if (cue.type === "buy") flyBoughtCard(cue, fly);
  else if (cue.type === "conflict") flyConflictCard(cue, fly);
  else if (cue.type === "makers") landMakerSpice(cue, fly);
  else if (cue.type === "recall") recallAgents(cue, fly);
}

function plainRect(rect) {
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}

function centerOf(rect) {
  return [rect.left + rect.width / 2, rect.top + rect.height / 2];
}

/* A box of the given size around a point. */
function boxAt([x, y], width, height) {
  return { left: x - width / 2, top: y - height / 2, width, height };
}

/* The node's box when it is on screen (laid out, and at least partly in
   the window), else null. */
function shownRect(node) {
  if (!node) return null;
  const rect = node.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  if (rect.bottom < 0 || rect.right < 0 || rect.top > window.innerHeight
    || rect.left > window.innerWidth) return null;
  return plainRect(rect);
}

/* Where a panel that is out of sight can still be pointed at: its phone
   tab, or its header toggle (folded under "보기 ▾" below 1200px). */
function panelDoor(panel) {
  return shownRect(document.querySelector(`#phone-tabs [data-view="${panel}"]`))
    || shownRect(document.querySelector(`#panel-toggles-list [data-panel="${panel}"]`))
    || shownRect(el("panel-toggles-open"));
}

/* A seat's panel, or the part of it named by `selector`, else its door. */
function seatTarget(seat, selectors) {
  const panel = document.querySelector(`#seats .seat[data-seat="${seat}"]`);
  for (const selector of selectors) {
    const rect = shownRect(selector ? panel && panel.querySelector(selector) : panel);
    if (rect) return rect;
  }
  return panelDoor("seats");
}

/* The board's part in sight, for a piece whose own place is not. */
function boardCenterBox(width, height) {
  const board = shownRect(el("board"));
  const top = Math.max(board ? board.top : 0, 0);
  const bottom = Math.min(board ? board.top + board.height : window.innerHeight, window.innerHeight);
  const center = board
    ? [board.left + board.width / 2, (top + bottom) / 2]
    : [window.innerWidth / 2, window.innerHeight / 2];
  return boxAt(center, width, height);
}

/* A card's face for a flight: its picture, else its name on a blank. */
function ghostCard(entry, className) {
  const card = document.createElement("div");
  card.className = `fx-card ${className}`;
  const face = cardFace(entry);
  if (entry && entry.image) {
    const img = document.createElement("img");
    img.src = entry.image;
    img.alt = "";
    img.draggable = false;
    card.appendChild(img);
  } else if (face) {
    card.classList.add("faced");
    card.appendChild(face);
  } else {
    card.classList.add("textcard");
    card.textContent = entry ? entry.name : "";
  }
  return card;
}

function reducedMotion() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* Fly `node` from one box to another in the effects layer: up in an arc,
   shrinking to the target's size, fading as it lands. Without a target it
   lifts and fades where it is; with reduced motion it only fades there. */
function flyGhost(node, from, to, duration, { lift = 0.18, fade = true } = {}) {
  const layer = el("fx-layer");
  if (!layer || !from) return null;
  node.classList.add("fx-ghost");
  node.style.left = `${from.left}px`;
  node.style.top = `${from.top}px`;
  node.style.width = `${from.width}px`;
  node.style.height = `${from.height}px`;
  layer.appendChild(node);
  let frames;
  if (reducedMotion() || !to) {
    frames = [
      { opacity: 0, transform: "scale(0.9)" },
      { opacity: 1, transform: "scale(1)", offset: 0.25 },
      { opacity: 0, transform: reducedMotion() ? "scale(1)" : "translateY(-24px) scale(0.9)" },
    ];
  } else {
    const [fx, fy] = centerOf(from);
    const [tx, ty] = centerOf(to);
    const dx = tx - fx;
    const dy = ty - fy;
    const scale = Math.max(0.12, Math.min(1.2, Math.min(to.width / from.width,
      to.height / from.height) || 0.4));
    const arc = Math.min(160, Math.hypot(dx, dy) * lift);
    /* Full size over most of the way, shrinking to the target's size only
       as it comes down onto it. */
    const near = Math.min(1, Math.max(scale * 1.6, (1 + scale) / 2));
    frames = [
      { opacity: 0.2, transform: "translate(0, 0) scale(0.9)" },
      { opacity: 1, transform: "translate(0, -6px) scale(1.08)", offset: 0.12 },
      {
        opacity: 1,
        transform: `translate(${dx / 2}px, ${dy / 2 - arc}px) scale(${Math.max(near, 0.85)})`,
        offset: 0.5,
      },
      {
        opacity: 1,
        transform: `translate(${dx * 0.9}px, ${dy * 0.9 - arc * 0.25}px) scale(${near})`,
        offset: 0.85,
      },
      { opacity: fade ? 0.35 : 1, transform: `translate(${dx}px, ${dy}px) scale(${scale})` },
    ];
  }
  const done = () => node.remove();
  let animation;
  try {
    animation = node.animate(frames, {
      duration, easing: "cubic-bezier(0.45, 0.05, 0.35, 1)", fill: "forwards",
    });
    animation.addEventListener("finish", done);
  } catch (error) {
    /* no Web Animations: the piece is simply not drawn */
    done();
    return null;
  }
  /* In case "finish" never comes; a flight held still (a check stopping
     it mid-way) stays until the layer is cleared. */
  setTimeout(() => {
    if (animation.playState !== "paused") done();
  }, duration + 400);
  return node;
}

/* A short flash where a moved piece landed, so the eye follows it there. */
function landingFlash(rect, color, delay) {
  const layer = el("fx-layer");
  if (!layer || !rect || reducedMotion()) return;
  const ring = document.createElement("div");
  ring.className = "fx-landing";
  ring.style.setProperty("--fx-color", color);
  const size = Math.max(28, Math.min(80, Math.max(rect.width, rect.height)));
  const box = boxAt(centerOf(rect), size, size);
  Object.assign(ring.style, {
    left: `${box.left}px`, top: `${box.top}px`, width: `${box.width}px`, height: `${box.height}px`,
    animationDelay: `${Math.round(delay)}ms`,
  });
  layer.appendChild(ring);
  ring.addEventListener("animationend", () => ring.remove(), { once: true });
  setTimeout(() => ring.remove(), delay + 1200);
}

/* ③ A bought card from where the shared cards showed it (or the board)
   to the buyer's hand, deck or discard pile on its seat panel. */
const DESTINATION_STATS = { hand: "hand", deck_top: "deck", discard: "discard" };

function flyBoughtCard(cue, fly) {
  const entry = entryOf(cue.cardId, "cards");
  const from = cue.origin && cue.origin.width
    ? cue.origin
    : boardCenterBox(phoneLayout() ? 64 : 92, phoneLayout() ? 90 : 129);
  const stat = DESTINATION_STATS[cue.destination] || "discard";
  const to = seatTarget(cue.seat, [`.stat[data-stat="${stat}"]`, ".zones", null]);
  const card = ghostCard(entry, "fx-bought");
  card.dataset.fx = "buy";
  card.dataset.seat = String(cue.seat);
  card.dataset.card = cue.cardId;
  card.style.setProperty("--fx-color", SEAT_COLORS[cue.seat]);
  flyGhost(card, from, to, fly);
  landingFlash(to, SEAT_COLORS[cue.seat], fly * 0.85);
}

/* ⑦ The Conflict card from its slot on the board to the winner's battle
   icons. */
function conflictSlotRect() {
  const view = state.view;
  const tracks = view && boardScan(view) ? boardLayout(view).tracks : null;
  const stage = document.querySelector("#board .board-stage");
  const slot = tracks && tracks.conflict_slot;
  const stageRect = shownRect(stage);
  if (!slot || !stageRect) return null;
  const [left, top, width, height] = slot;
  return {
    left: stageRect.left + (stageRect.width * left) / 100,
    top: stageRect.top + (stageRect.height * top) / 100,
    width: (stageRect.width * width) / 100,
    height: (stageRect.height * height) / 100,
  };
}

function flyConflictCard(cue, fly) {
  const entry = lookup(cue.conflictId, "conflicts");
  const from = conflictSlotRect() || boardCenterBox(phoneLayout() ? 64 : 92, phoneLayout() ? 90 : 129);
  const to = seatTarget(cue.seat, [".battle-icons", ".battle-line", null]);
  const card = ghostCard(entry, "fx-conflict");
  card.dataset.fx = "conflict";
  card.dataset.seat = String(cue.seat);
  card.dataset.card = cue.conflictId;
  card.style.setProperty("--fx-color", SEAT_COLORS[cue.seat]);
  flyGhost(card, from, to, fly, { lift: 0.12 });
  landingFlash(to, SEAT_COLORS[cue.seat], fly * 0.85);
}

/* ⑧ The bonus spice landing on each Maker space nobody took: a spice hex
   drops onto the space's bonus spot and "+1" rises from it. */
function landMakerSpice(cue, fly) {
  for (const space of cue.spaces) {
    const spot = document.querySelector(`#board .bonus-spice[data-space="${CSS.escape(space)}"]`)
      || document.querySelector(`#board .hotspot[data-space="${CSS.escape(space)}"]`);
    const rect = shownRect(spot);
    if (!rect) continue;
    const hex = document.createElement("div");
    hex.className = "fx-spice";
    hex.dataset.fx = "makers";
    hex.dataset.space = space;
    hex.appendChild(icon("spice", termLabel("spice")));
    const size = Math.max(22, Math.min(46, rect.height * 1.3));
    const at = boxAt(centerOf(rect), size, size);
    const drop = { ...at, top: at.top - size * 1.6 };
    flyGhost(hex, drop, at, fly * 0.6, { lift: 0, fade: false });
    const plus = document.createElement("div");
    plus.className = "stat-float gain fx-plus";
    plus.textContent = "+1";
    plus.style.left = `${at.left + at.width / 2}px`;
    plus.style.top = `${at.top}px`;
    plus.style.animationDelay = `${Math.round(fly * 0.45)}ms`;
    el("fx-layer").appendChild(plus);
    setTimeout(() => plus.remove(), fly * 0.45 + 1800);
  }
}

/* ⑧ Every Agent from its space to its seat's Agents on the seat panel,
   and the First Player marker from the seat that held it to the next. */
function recallAgents(cue, fly) {
  const board = shownRect(el("board"));
  /* About the size an Agent stands on the board (its figure is 2:3). */
  const size = board ? Math.max(14, Math.min(34, board.width * 0.026)) : 24;
  cue.agents.forEach((agent, position) => {
    const hotspot = document.querySelector(
      `#board .hotspot[data-space="${CSS.escape(agent.space)}"]`,
    );
    const rect = shownRect(hotspot);
    if (!rect) return;
    const from = boxAt(centerOf(rect), size, size * 1.55);
    const to = seatTarget(agent.seat, ['.stat[data-stat="agent"]', ".seat-mark", null]);
    const piece = document.createElement("div");
    piece.className = "fx-agent";
    piece.dataset.fx = "recall";
    piece.dataset.seat = String(agent.seat);
    piece.dataset.space = agent.space;
    piece.appendChild(seatPiece("agent", agent.seat));
    const delay = Math.min(position * 45, fly * 0.3);
    setTimeout(() => flyGhost(piece, from, to, fly - delay, { lift: 0.1 }), delay);
  });
  if (cue.firstPlayer !== null) passFirstPlayer(cue.firstPlayer, fly);
}

function passFirstPlayer(seat, fly) {
  const previous = (seat + 3) % 4;
  const panel = (number) => document.querySelector(`#seats .seat[data-seat="${number}"]`);
  /* firstPlayerMark: the token's picture, else a badge titled with it. */
  const name = phraseText("{first_player}");
  const mark = panel(seat) && [...panel(seat).querySelectorAll(".who > *")].find((node) =>
    node.classList.contains("first-player-token") || node.title === name);
  const to = shownRect(mark);
  const fromPanel = shownRect(panel(previous));
  const toPanel = shownRect(panel(seat));
  if (!to || !fromPanel || !toPanel) return;
  /* Where the marker sat on the seat that held it: the same spot of its
     panel. */
  const from = { ...to, left: to.left - toPanel.left + fromPanel.left,
    top: to.top - toPanel.top + fromPanel.top };
  const token = firstPlayerMark();
  token.classList.add("fx-first-player");
  token.removeAttribute("title");
  const holder = document.createElement("div");
  holder.className = "fx-token";
  holder.dataset.fx = "first_player";
  holder.dataset.seat = String(seat);
  holder.appendChild(token);
  flyGhost(holder, from, to, fly, { lift: 0.25, fade: false });
}

/* ⑤ The Alliance token's way, with its banner (effects.js nextPhaseBanner):
   from its ring on the Faction's strip to the seat that earned it, from
   the seat that lost it to the next holder, or back to the strip. */
function allianceRingRect(faction) {
  return shownRect(document.querySelector(
    `#board .alliance-ring[data-faction="${CSS.escape(faction)}"], `
      + `#board .alliance-token[data-faction="${CSS.escape(faction)}"]`,
  ));
}

function flyAllianceToken(cue, fly) {
  if (effectsOff()) return;
  const ring = allianceRingRect(cue.faction);
  const seatBox = (seat) => (validSeat(seat)
    ? seatTarget(seat, ['.stat[data-stat="victory_point"]', ".seat-mark", null]) : null);
  const giver = validSeat(cue.from) ? seatBox(cue.from) : ring;
  const taker = validSeat(cue.to) ? seatBox(cue.to) : ring;
  if (!giver || !taker) return;
  const size = ring ? Math.max(24, Math.min(54, ring.width)) : 36;
  const from = boxAt(centerOf(giver), size, size);
  const token = allianceToken(cue.faction, 100);
  token.removeAttribute("title");
  token.style.width = "100%";
  const holder = document.createElement("div");
  holder.className = "fx-token fx-alliance";
  holder.dataset.fx = "alliance";
  holder.dataset.faction = cue.faction;
  holder.appendChild(token);
  flyGhost(holder, from, taker, fly, { lift: 0.2 });
  const color = validSeat(cue.to) ? SEAT_COLORS[cue.to] : "#d9ab55";
  landingFlash(taker, color, fly * 0.85);
}

/* ⑤ An Influence cube whose level changed slides from where it stood to
   where it stands now (FLIP: put back by the difference, then let go),
   as an Agent flies to its space (board.js animatePlacedAgents). Where it
   stood is its old level's spot on the same strip (board.js places a cube
   at its seat's column and its level's row, a percent of the board): a box
   measured at the render before could be empty, and a loaded machine
   measured one without a size and dropped the slide (2026-11-11). */
function slideInfluenceCubes() {
  /* Another game or review seat, an undo, or a paused or seeking review
     is a new baseline, as for the rising numbers (renderStatFloats). */
  const context = `${motion.context}:${state.summary ? state.summary.undo_count : 0}`;
  const before = motion.cubeContext === context ? motion.cubes : null;
  motion.cubeContext = context;
  const still = state.review && (!playback.playing || state.review.seek);
  if (!before || still || effectsOff() || reducedMotion()) return;
  const levels = ((boardLayout().tracks || {}).influence || {}).levels;
  if (!levels) return;
  for (const cube of document.querySelectorAll("#board .track-cube[data-faction]")) {
    const was = before.get(`${cube.dataset.seat}:${cube.dataset.faction}`);
    if (was === undefined || was === cube.dataset.level) continue;
    const stage = cube.closest(".board-stage");
    const height = stage ? stage.getBoundingClientRect().height : 0;
    const shift = levels[Number(was)] - levels[Number(cube.dataset.level)];
    if (!height || !Number.isFinite(shift)) continue;
    cube.classList.add("fx-sliding");
    try {
      cube.animate([
        { translate: `0px ${(shift * height) / 100}px`, filter: "brightness(1.6)" },
        { translate: "0 0", filter: "brightness(1)" },
      ], { duration: 650 * cueScale(), easing: "cubic-bezier(0.3, 0.8, 0.3, 1)" })
        .addEventListener("finish", () => cube.classList.remove("fx-sliding"));
    } catch (error) {
      cube.classList.remove("fx-sliding");
    }
  }
}
