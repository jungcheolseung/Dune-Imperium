"use strict";

/* ---------- the player's own layout ---------- */

/* Two things a player arranges for themselves (user request 2026-10-11):
   the widths of the table's columns, and the order of the cards in their
   own hand. Both are this browser's alone, like the folded card columns:
   nothing is sent to the server, and no other seat, spectator or replay
   sees them. */

/* ---------- column widths ---------- */

/* The three handles (index.html .col-splitter) and the width each sets, as
   a custom property on #game-screen that style.css reads (--seats-width,
   --actions-width, the shared-card column). `grows`: the way a drag widens
   the column, +1 to the right (the seat column, left of its handle), -1 to
   the left. A width the player never set keeps the stylesheet's default,
   which is narrower below 1341px. */
const COLUMN_WIDTHS_KEY = "dune.layout.columns.v1";
const COLUMNS = {
  seats: { min: 160, max: 420, property: "--seats-user", grows: 1 },
  actions: { min: 280, max: 640, property: "--actions-user", grows: -1 },
  market: { min: 150, max: 420, property: "--market-user", grows: -1 },
};
const COLUMN_KEY_STEP = 10;
const COLUMN_KEY_STEP_LARGE = 40;
let columnWidths = {};

function clampNumber(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function loadColumnWidths() {
  let stored = null;
  try {
    stored = JSON.parse(storageGet(COLUMN_WIDTHS_KEY) || "null");
  } catch (error) {
    stored = null;
  }
  columnWidths = {};
  if (stored && typeof stored === "object") {
    for (const [name, spec] of Object.entries(COLUMNS)) {
      const value = stored[name];
      if (typeof value === "number" && Number.isFinite(value)) {
        columnWidths[name] = Math.round(clampNumber(value, spec.min, spec.max));
      }
    }
  }
  applyColumnWidths();
}

function saveColumnWidths() {
  if (Object.keys(columnWidths).length) {
    storageSet(COLUMN_WIDTHS_KEY, JSON.stringify(columnWidths));
  } else {
    storageRemove(COLUMN_WIDTHS_KEY);
  }
}

function applyColumnWidths() {
  const screen = el("game-screen");
  for (const [name, spec] of Object.entries(COLUMNS)) {
    if (name in columnWidths) {
      screen.style.setProperty(spec.property, `${columnWidths[name]}px`);
    } else {
      screen.style.removeProperty(spec.property);
    }
  }
}

/* The width the column has on screen now, set or not. */
function currentColumnWidth(name) {
  if (name === "actions") {
    const value = getComputedStyle(el("table")).getPropertyValue("--actions-width");
    return parseFloat(value);
  }
  return el(name).getBoundingClientRect().width;
}

/* How much wider a column may grow before the board column reaches its
   floor (--board-min). History lent the board's spare room beside the
   action column (render.js fitActionLog) gives it back as the board needs
   it, so that counts as room too. The stylesheet's floor holds whatever
   this says; this only stops a handle where the board stops shrinking,
   instead of pushing the table into its sideways scroll. */
function boardRoom() {
  const table = el("table");
  const screen = getComputedStyle(el("game-screen"));
  const floor = parseFloat(screen.getPropertyValue("--board-min")) || 0;
  let lent = 0;
  if (table.classList.contains("log-beside")) {
    const side = el("side").getBoundingClientRect().width;
    lent = Math.max(0, side - currentColumnWidth("actions"));
  }
  return Math.max(0, el("board").getBoundingClientRect().width - floor + lent);
}

/* The widest a column may be set now, from `start` (its width now). */
function columnLimit(name, start) {
  const spec = COLUMNS[name];
  return clampNumber(start + boardRoom(), spec.min, spec.max);
}

/* `width` null: back to the default. The board and the history column fit
   themselves to what is left, as on a window resize. */
function setColumnWidth(name, width, persist = true) {
  if (width === null) delete columnWidths[name];
  else columnWidths[name] = Math.round(width);
  applyColumnWidths();
  if (persist) saveColumnWidths();
  fitActionLog();
  labelSplitter(name);
}

function labelSplitter(name) {
  const splitter = document.querySelector(`.col-splitter[data-column="${name}"]`);
  if (!splitter) return;
  const spec = COLUMNS[name];
  splitter.setAttribute("aria-valuemin", String(spec.min));
  splitter.setAttribute("aria-valuemax", String(spec.max));
  const width = currentColumnWidth(name);
  if (Number.isFinite(width) && width > 0) {
    splitter.setAttribute("aria-valuenow", String(Math.round(width)));
  }
}

function dragSplitter(event, splitter) {
  if (event.button !== 0 || !event.isPrimary) return;
  const name = splitter.dataset.column;
  const spec = COLUMNS[name];
  const start = currentColumnWidth(name);
  const limit = columnLimit(name, start);
  const originX = event.clientX;
  let width = Math.round(start);
  event.preventDefault();
  splitter.focus({ preventScroll: true });
  try {
    splitter.setPointerCapture(event.pointerId);
  } catch (error) {
    /* no capture: the moves still reach the handle while over it */
  }
  splitter.classList.add("dragging");
  document.body.classList.add("column-resizing");
  const move = (moved) => {
    if (moved.pointerId !== event.pointerId) return;
    const wanted = start + spec.grows * (moved.clientX - originX);
    const next = Math.round(clampNumber(wanted, spec.min, limit));
    /* A press without a move sets nothing: a width stays unset until the
       player really moves its handle. */
    if (next === width) return;
    width = next;
    setColumnWidth(name, next, false);
  };
  const end = (ended) => {
    if (ended.pointerId !== event.pointerId) return;
    splitter.removeEventListener("pointermove", move);
    splitter.removeEventListener("pointerup", end);
    splitter.removeEventListener("pointercancel", end);
    splitter.removeEventListener("lostpointercapture", end);
    splitter.classList.remove("dragging");
    document.body.classList.remove("column-resizing");
    if (name in columnWidths) saveColumnWidths();
  };
  splitter.addEventListener("pointermove", move);
  splitter.addEventListener("pointerup", end);
  splitter.addEventListener("pointercancel", end);
  splitter.addEventListener("lostpointercapture", end);
}

/* Arrow keys move the focused handle (Shift: further); Enter puts its
   column back to the default, like a double click. */
function splitterKey(event, splitter) {
  const name = splitter.dataset.column;
  const spec = COLUMNS[name];
  if (event.key === "Enter") {
    event.preventDefault();
    setColumnWidth(name, null);
    return;
  }
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  if (event.altKey || event.ctrlKey || event.metaKey) return;
  event.preventDefault();
  const step = event.shiftKey ? COLUMN_KEY_STEP_LARGE : COLUMN_KEY_STEP;
  const direction = event.key === "ArrowRight" ? 1 : -1;
  const start = currentColumnWidth(name);
  const wanted = start + spec.grows * direction * step;
  const next = Math.round(clampNumber(wanted, spec.min, columnLimit(name, start)));
  if (next !== Math.round(start)) setColumnWidth(name, next);
}

function watchColumnSplitters() {
  loadColumnWidths();
  for (const splitter of document.querySelectorAll(".col-splitter")) {
    splitter.addEventListener("pointerdown", (event) => dragSplitter(event, splitter));
    splitter.addEventListener("dblclick", (event) => {
      event.preventDefault();
      setColumnWidth(splitter.dataset.column, null);
    });
    splitter.addEventListener("keydown", (event) => splitterKey(event, splitter));
    /* The value a screen reader reads, measured when it is asked for. */
    splitter.addEventListener("focus", () => labelSplitter(splitter.dataset.column));
  }
}

/* ---------- the order of the player's own cards ---------- */

/* The hand and the Intrigue cards, each in the order the player dragged
   them into, stored per game and seat as {hand: [ids], intrigue: [ids]}.
   The server's order stays the truth: cards the store does not know (just
   drawn) follow the known ones in the server's order, and cards gone from
   the hand leave the store. */
const HAND_ORDER_PREFIX = "dune.handOrder.v1.";
const HAND_DRAG_THRESHOLD = 6;
const HAND_DRAG_EDGE = 32;
const HAND_DRAG_SCROLL = 14;
let handDrag = null;
let swallowHandClick = false;

function handOrderKey() {
  return `${HAND_ORDER_PREFIX}${state.gameId}.${activeSeat()}`;
}

/* The hand on screen is this browser's own, live: never a replay, a
   watched game or another seat's. */
function handReorderable() {
  const view = state.view;
  return Boolean(
    view && view.private && !state.review && state.gameId &&
      mySeats().includes(activeSeat()),
  );
}

function readHandOrder() {
  try {
    const stored = JSON.parse(storageGet(handOrderKey()) || "null");
    const usable = stored && typeof stored === "object" && !Array.isArray(stored);
    return usable ? stored : {};
  } catch (error) {
    return {};
  }
}

function writeHandOrder(order) {
  const kept = {};
  for (const strip of ["hand", "intrigue"]) {
    const ids = order[strip];
    if (Array.isArray(ids) && ids.length) kept[strip] = ids;
  }
  if (Object.keys(kept).length) storageSet(handOrderKey(), JSON.stringify(kept));
  else storageRemove(handOrderKey());
}

/* The server's ids of a strip, in the server's order. */
function serverStripIds(strip) {
  const own = state.view && state.view.private;
  if (!own) return [];
  return (strip === "hand" ? own.hand : own.intrigue_cards).slice();
}

/* The ids of a strip in the order to draw them. A replay, a watched game
   or another seat's hand gets the server's order untouched. */
function orderedStripIds(strip, serverIds) {
  if (!handReorderable()) return serverIds.slice();
  const order = readHandOrder();
  const stored = Array.isArray(order[strip])
    ? order[strip].filter((id) => typeof id === "string")
    : [];
  const present = new Set(serverIds);
  const kept = stored.filter((id) => present.has(id));
  if (kept.length !== (Array.isArray(order[strip]) ? order[strip].length : 0)) {
    order[strip] = kept;
    writeHandOrder(order);
  }
  const position = new Map();
  kept.forEach((id, index) => {
    if (!position.has(id)) position.set(id, index);
  });
  const known = serverIds
    .filter((id) => position.has(id))
    .sort((a, b) => position.get(a) - position.get(b));
  return known.concat(serverIds.filter((id) => !position.has(id)));
}

function stripCards(strip) {
  return [...strip.querySelectorAll(":scope > .vcard")];
}

function stripIds(strip) {
  return stripCards(strip).map((card) => card.dataset.instance);
}

/* Whether any strip on screen is out of the server's order. */
function handOrderCustom() {
  const strips = document.querySelectorAll("#private-zone [data-reorder]");
  return [...strips].some((strip) => {
    const server = serverStripIds(strip.dataset.reorder);
    return stripIds(strip).join("\n") !== server.join("\n");
  });
}

/* The "Reset order" button in the hand's label row, there only while an
   order of the player's own is on screen. */
function syncHandOrderReset() {
  const label = document.querySelector("#private-zone .hand-label");
  if (!label) return;
  let button = label.querySelector(".hand-order-reset");
  const custom = handReorderable() && handOrderCustom();
  if (!custom) {
    if (button) {
      const focused = document.activeElement === button;
      button.remove();
      if (focused) {
        const first = document.querySelector("#private-zone [data-reorder] > .vcard");
        if (first) first.focus();
      }
    }
    return;
  }
  if (button) return;
  button = document.createElement("button");
  button.type = "button";
  button.className = "hand-order-reset";
  button.textContent = t("layout.hand_order_reset");
  button.title = t("layout.hand_order_reset_title");
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    resetHandOrder();
  });
  label.appendChild(button);
}

function resetHandOrder() {
  storageRemove(handOrderKey());
  for (const strip of document.querySelectorAll("#private-zone [data-reorder]")) {
    const nodes = new Map();
    for (const card of stripCards(strip)) {
      const id = card.dataset.instance;
      if (!nodes.has(id)) nodes.set(id, []);
      nodes.get(id).push(card);
    }
    for (const id of serverStripIds(strip.dataset.reorder)) {
      const node = nodes.has(id) ? nodes.get(id).shift() : null;
      if (node) strip.appendChild(node);
    }
  }
  syncHandOrderReset();
}

/* The strip's order as it is on screen, remembered; the server's own order
   needs no entry. */
function saveStripOrder(strip) {
  const name = strip.dataset.reorder;
  const ids = stripIds(strip);
  const order = readHandOrder();
  if (ids.join("\n") === serverStripIds(name).join("\n")) delete order[name];
  else order[name] = ids;
  writeHandOrder(order);
  syncHandOrderReset();
}

/* A strip of the player's own cards (panels.js renderPrivate) takes drags
   and Alt+Arrow keys. */
function enableStripOrder(strip, name) {
  strip.dataset.reorder = name;
  strip.classList.add("reorderable");
  strip.addEventListener("pointerdown", (event) => handPointerDown(event, strip));
  strip.addEventListener("keydown", (event) => handKey(event, strip));
}

/* A press on a card is a click until the pointer travels
   HAND_DRAG_THRESHOLD pixels: then it is a drag, and the click that
   follows the release is swallowed (swallowDragClick), so a plain click
   still picks the card for the Agent turn or pins its popover. */
function handPointerDown(event, strip) {
  if (event.button !== 0 || !event.isPrimary || handDrag) return;
  const card = event.target.closest(".vcard");
  if (!card || card.parentElement !== strip) return;
  handDrag = {
    strip,
    card,
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    active: false,
    index: null,
    marker: null,
  };
  window.addEventListener("pointermove", handPointerMove);
  window.addEventListener("pointerup", handPointerUp);
  window.addEventListener("pointercancel", handPointerCancel);
}

function handPointerMove(event) {
  const drag = handDrag;
  if (!drag || event.pointerId !== drag.pointerId) return;
  if (!drag.active) {
    const travelled = Math.hypot(event.clientX - drag.x, event.clientY - drag.y);
    if (travelled < HAND_DRAG_THRESHOLD) return;
    drag.active = true;
    try {
      drag.card.setPointerCapture(event.pointerId);
    } catch (error) {
      /* the window listeners still follow the pointer */
    }
    drag.card.classList.add("dragging");
    document.body.classList.add("hand-dragging");
    const selection = window.getSelection && window.getSelection();
    if (selection) selection.removeAllRanges();
    clearTimeout(hoverTimer);
    if (!popoverPinned) closePopover();
    drag.marker = document.createElement("span");
    drag.marker.className = "hand-drop-marker";
    drag.marker.setAttribute("aria-hidden", "true");
    drag.strip.appendChild(drag.marker);
  }
  event.preventDefault();
  /* Near either end of a strip that scrolls, the strip scrolls along. */
  const box = drag.strip.getBoundingClientRect();
  if (event.clientX < box.left + HAND_DRAG_EDGE) {
    drag.strip.scrollLeft -= HAND_DRAG_SCROLL;
  } else if (event.clientX > box.right - HAND_DRAG_EDGE) {
    drag.strip.scrollLeft += HAND_DRAG_SCROLL;
  }
  const others = stripCards(drag.strip).filter((card) => card !== drag.card);
  drag.index = others.filter((card) => {
    const rect = card.getBoundingClientRect();
    return event.clientX > rect.left + rect.width / 2;
  }).length;
  placeDropMarker(drag, others);
}

/* The marker sits in the gap the card would land in. */
function placeDropMarker(drag, others) {
  const gap = parseFloat(getComputedStyle(drag.strip).columnGap) || 0;
  let left;
  if (!others.length) left = drag.card.offsetLeft - gap / 2;
  else if (drag.index < others.length) left = others[drag.index].offsetLeft - gap / 2;
  else {
    const last = others[others.length - 1];
    left = last.offsetLeft + last.offsetWidth + gap / 2;
  }
  drag.marker.style.left = `${left}px`;
}

function handPointerUp(event) {
  if (!handDrag || event.pointerId !== handDrag.pointerId) return;
  endHandDrag(true);
}

function handPointerCancel(event) {
  if (!handDrag || event.pointerId !== handDrag.pointerId) return;
  endHandDrag(false);
}

/* `drop`: put the card where the marker is. A drag cut short (a cancelled
   pointer, a redraw of the hand) leaves the order as it was. */
function endHandDrag(drop) {
  const drag = handDrag;
  if (!drag) return;
  handDrag = null;
  window.removeEventListener("pointermove", handPointerMove);
  window.removeEventListener("pointerup", handPointerUp);
  window.removeEventListener("pointercancel", handPointerCancel);
  if (!drag.active) return;
  /* The click the release is about to fire belongs to the drag. It comes
     in the same task, so the flag cannot outlive it. */
  swallowHandClick = true;
  setTimeout(() => {
    swallowHandClick = false;
  }, 0);
  drag.card.classList.remove("dragging");
  document.body.classList.remove("hand-dragging");
  if (drag.marker) drag.marker.remove();
  try {
    drag.card.releasePointerCapture(drag.pointerId);
  } catch (error) {
    /* already released */
  }
  if (!drop || drag.index === null || !drag.strip.isConnected) return;
  const before = stripIds(drag.strip).join("\n");
  const others = stripCards(drag.strip).filter((card) => card !== drag.card);
  const target = others[drag.index];
  if (target) drag.strip.insertBefore(drag.card, target);
  else if (others.length) others[others.length - 1].after(drag.card);
  if (stripIds(drag.strip).join("\n") !== before) saveStripOrder(drag.strip);
}

/* A redraw of the hand mid-drag (another seat's move, a language switch)
   drops the drag: the card it held is gone. */
function cancelHandDrag() {
  endHandDrag(false);
}

function swallowDragClick(event) {
  if (!swallowHandClick) return;
  swallowHandClick = false;
  event.stopPropagation();
  event.preventDefault();
}

/* Alt+Left / Alt+Right moves the focused card one place. The neighbour
   moves rather than the card, so the card keeps the focus. */
function handKey(event, strip) {
  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
  const card = event.target.closest(".vcard");
  if (!card || card.parentElement !== strip) return;
  /* Alt+Left is the browser's Back on some systems. */
  event.preventDefault();
  event.stopPropagation();
  const cards = stripCards(strip);
  const index = cards.indexOf(card);
  if (event.key === "ArrowLeft" && index > 0) card.after(cards[index - 1]);
  else if (event.key === "ArrowRight" && index < cards.length - 1) {
    card.before(cards[index + 1]);
  } else return;
  card.scrollIntoView({ block: "nearest", inline: "nearest" });
  saveStripOrder(strip);
}

function watchHandOrder() {
  window.addEventListener("click", swallowDragClick, true);
}
