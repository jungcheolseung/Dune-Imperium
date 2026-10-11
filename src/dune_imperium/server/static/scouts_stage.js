"use strict";

/* ---------- the Arrakeen Scouts card over the board ----------

   User request 2026-10-11: while the Scouts step resolves an item, the item
   stays up over the board as one large card, laid out like Dire Wolf Game
   Room's reveal page -- a header band with the kind in spaced capitals and
   the item's name, the kind's painting on the left, the item on a
   parchment on the right -- and a toggle folds it away so the board can be
   seen. Display only: it reads the public view (view.scouts_item through
   panels.js scoutsDecisionItemId) and the seat's own actions, and writes
   the item's lines with panels.js scoutsItemLines, this project's own
   words and icons, never the app's text. The pictures are the app's
   (catalog.scouts_art, display/scouts_art.py), each optional: without one
   that part is drawn in CSS (scouts_stage.css).

   It covers the board square only (#scouts-stage takes the board's grid
   cell), never the decision panel, the seats or the market.

   When it shows: whenever the view names an item being resolved, for every
   seat, spectators and review alike, and it goes when the step ends. A new
   item (another id or round) opens it again. A decision of the viewer's
   own that the board answers (a space, a post, a card or a troop stepper
   on the board lights up) starts with it folded so it never covers a
   click; any other decision of its own starts with it open. In between,
   whatever the player folded or unfolded stands. */

const scoutsStage = {
  /* The item on the card ("<round>:<id>"), or null without a card. */
  key: null,
  open: true,
  /* The viewer's own decision the open state was last set for, or null. */
  decision: null,
  /* What the card's content was built from: rebuilt only when it changes,
     so an update with the same item neither flickers nor replays. */
  content: null,
};

/* The pieces every card shares, by catalog.scouts_art name, and the CSS
   variable each one fills (scouts_stage.css). */
const SCOUTS_STAGE_PIECES = {
  back: "--scouts-back",
  header_upper: "--scouts-header-upper",
  header_lower: "--scouts-header-lower",
  or_backer: "--scouts-or-backer",
  starfield: "--scouts-starfield",
};

function scoutsArtUrl(name) {
  const art = (state.catalog && state.catalog.scouts_art) || {};
  return art[name] || null;
}

/* What the card shows now, or null outside the step. While the due secret
   picks resolve (SCOUTS_SECRETS_CURSOR), the seat's own reward names its
   event, as the decision panel's header does; without one the card stands
   for the picks being revealed, naming the events they belong to. */
function scoutsStageItem() {
  const id = scoutsDecisionItemId();
  if (!id) return null;
  const view = state.view;
  const round = view.round_number;
  const secrets = view.scouts_item === SCOUTS_SECRETS_CURSOR;
  if (id === SCOUTS_SECRETS_CURSOR) {
    const events = [];
    const seats = new Map();
    for (const [pickRound, event, seat] of view.scouts_secret_pending || []) {
      const key = `${pickRound}|${event}`;
      if (!seats.has(key)) {
        seats.set(key, []);
        events.push([pickRound, event]);
      }
      seats.get(key).push(playerLabel(seat));
    }
    const kinds = events.map(([, event]) => scoutsItem(event).kind).filter(Boolean);
    return {
      key: `${round}:${id}`,
      id,
      kind: kinds[0] || "event",
      name: t("scouts_stage.secrets_name"),
      note: null,
      item: null,
      waiting: events.map(([pickRound, event]) =>
        t("panels.scouts_secret_waiting", {
          round: pickRound,
          name: scoutsItem(event).name,
          seats: seats.get(`${pickRound}|${event}`).join(", "),
        }),
      ),
    };
  }
  const item = scoutsItem(id);
  return {
    key: `${round}:${id}`,
    id,
    kind: item.kind,
    name: item.name,
    note: secrets ? t("scouts_stage.secrets_name") : null,
    item,
    waiting: [],
  };
}

/* The viewer's own decision, as "<seat>|<frame kind>|<prompt>", or null
   while it has nothing to decide (waiting, spectating, reviewing). */
function scoutsStageDecision() {
  const actions = state.actions;
  if (state.review || !actions || !(actions.actions || []).length) return null;
  const decision = (state.summary && state.summary.decision) || {};
  return `${actions.seat}|${decision.kind || ""}|${decision.prompt || ""}`;
}

/* Whether the board answers the viewer's decision: renderBoard marks what
   a legal action names (board.js: a space's hotspot, a Spy post, a card in
   a printed slot) as .legal and adds the troop stepper for a deployment. */
function scoutsStageBoardDecision() {
  return Boolean(el("board").querySelector(".legal, .force-stepper"));
}

function renderScoutsStage() {
  const stage = el("scouts-stage");
  const shown = state.summary && !el("game-screen").hidden ? scoutsStageItem() : null;
  if (!shown) {
    stage.querySelector(".scouts-stage-card").classList.remove("entering");
    stage.hidden = true;
    scoutsStage.key = null;
    scoutsStage.decision = null;
    return;
  }
  const decision = scoutsStageDecision();
  const wasHidden = stage.hidden || !scoutsStage.open;
  if (shown.key !== scoutsStage.key) {
    scoutsStage.key = shown.key;
    scoutsStage.decision = decision;
    scoutsStage.open = !(decision && scoutsStageBoardDecision());
  } else if (decision !== scoutsStage.decision) {
    scoutsStage.decision = decision;
    if (decision) scoutsStage.open = !scoutsStageBoardDecision();
  }
  fillScoutsStage(stage, shown);
  stage.hidden = false;
  applyScoutsStageOpen(wasHidden);
}

/* Build the card's content, unless it was built from the same thing. */
function fillScoutsStage(stage, shown) {
  const art = (state.catalog && state.catalog.scouts_art) || {};
  const painting = art[shown.kind] || null;
  const signature = JSON.stringify([
    shown.key,
    shown.name,
    shown.note,
    shown.waiting,
    TERM_LANGUAGE,
    painting,
    Object.keys(SCOUTS_STAGE_PIECES).map(scoutsArtUrl),
    Boolean(state.catalog && state.catalog.board_image),
  ]);
  if (signature === scoutsStage.content) return;
  scoutsStage.content = signature;

  stage.dataset.item = shown.id;
  stage.dataset.kind = shown.kind;
  /* The board scan is square and top-aligned in its cell; the card's frame
     takes the same square. The text board fills the cell. */
  stage.classList.toggle("no-scan", !(state.catalog && state.catalog.board_image));
  for (const [name, variable] of Object.entries(SCOUTS_STAGE_PIECES)) {
    const url = scoutsArtUrl(name);
    stage.classList.toggle(`has-${name.replaceAll("_", "-")}`, Boolean(url));
    if (url) stage.style.setProperty(variable, `url("${url}")`);
    else stage.style.removeProperty(variable);
  }
  stage.classList.toggle("has-art", Boolean(painting));

  const picture = stage.querySelector(".scouts-stage-art");
  picture.textContent = "";
  if (painting) {
    const image = document.createElement("img");
    image.src = painting;
    image.alt = "";
    image.draggable = false;
    picture.appendChild(image);
  }

  stage.querySelector(".scouts-stage-kind").textContent = scoutsKindName(shown.kind);
  stage.querySelector(".scouts-stage-name").textContent = shown.name;
  const card = stage.querySelector(".scouts-stage-card");
  card.setAttribute("aria-label", t("scouts_stage.region", {
    kind: scoutsKindName(shown.kind),
    name: shown.name,
  }));

  const lines = stage.querySelector(".scouts-stage-lines");
  lines.textContent = "";
  if (shown.note) {
    const note = document.createElement("div");
    note.className = "scouts-stage-note";
    note.textContent = shown.note;
    lines.appendChild(note);
  }
  const body = document.createElement("div");
  if (shown.item) scoutsItemLines(shown.item, body);
  for (const text of shown.waiting) {
    const row = document.createElement("div");
    row.className = "scouts-line scouts-stage-waiting";
    row.appendChild(phrase(text));
    body.appendChild(row);
  }
  /* The bar the app puts between alternatives, here only as a divider
     between two lines: it says nothing about how the lines combine. */
  let previous = null;
  for (const child of [...body.children]) {
    if (previous && previous.classList.contains("scouts-line")
        && child.classList.contains("scouts-line")) {
      const divider = document.createElement("div");
      divider.className = "scouts-stage-divider";
      divider.setAttribute("aria-hidden", "true");
      lines.appendChild(divider);
    }
    lines.appendChild(child);
    previous = child;
  }

  const hide = stage.querySelector(".scouts-stage-hide");
  hide.textContent = t("scouts_stage.hide");
  hide.title = t("scouts_stage.hide_title");
  const tab = stage.querySelector(".scouts-stage-tab");
  tab.textContent = t("scouts_stage.tab", { name: shown.name });
  tab.title = t("scouts_stage.tab_title");
}

/* Show the card or its tab. `entering`: the card comes into view, so it
   slides in once (scouts_stage.css; nothing moves under reduced motion). */
function applyScoutsStageOpen(entering) {
  const stage = el("scouts-stage");
  const open = scoutsStage.open;
  stage.classList.toggle("folded", !open);
  const card = stage.querySelector(".scouts-stage-card");
  card.hidden = !open;
  stage.querySelector(".scouts-stage-tab").hidden = open;
  /* An update meanwhile leaves a running slide-in alone. */
  if (!open) card.classList.remove("entering");
  else if (entering) {
    card.classList.remove("entering");
    /* A reflow between removing and adding restarts the animation. */
    void card.offsetWidth;
    card.classList.add("entering");
  }
}

/* The button, the tab and the shortcut. False when there is no card. */
function toggleScoutsStage() {
  const stage = el("scouts-stage");
  if (stage.hidden || !scoutsStage.key) return false;
  const card = stage.querySelector(".scouts-stage-card");
  const hadFocus = card.contains(document.activeElement)
    || stage.querySelector(".scouts-stage-tab") === document.activeElement;
  scoutsStage.open = !scoutsStage.open;
  applyScoutsStageOpen(scoutsStage.open);
  if (hadFocus) {
    const target = scoutsStage.open
      ? stage.querySelector(".scouts-stage-hide")
      : stage.querySelector(".scouts-stage-tab");
    target.focus();
  }
  return true;
}

function watchScoutsStage() {
  const stage = el("scouts-stage");
  stage.querySelector(".scouts-stage-hide").addEventListener("click", (event) => {
    event.stopPropagation();
    event.currentTarget.focus();
    toggleScoutsStage();
  });
  stage.querySelector(".scouts-stage-tab").addEventListener("click", (event) => {
    event.stopPropagation();
    event.currentTarget.focus();
    toggleScoutsStage();
  });
  /* Over, or cut short by the card going out of view. */
  for (const type of ["animationend", "animationcancel"]) {
    stage.querySelector(".scouts-stage-card").addEventListener(type, (event) => {
      event.currentTarget.classList.remove("entering");
    });
  }
}
