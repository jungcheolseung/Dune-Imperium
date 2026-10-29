"use strict";

/* ---------- the Arrakeen Scouts card over the board ----------

   User request 2026-10-11: a revealed item stays up over the board as one
   large card, laid out like Dire Wolf Game Room's reveal page -- a header
   band with the kind in spaced capitals and the item's name, the kind's
   painting on the left, the item on a parchment on the right -- and a
   toggle folds it away so the board can be seen. Display only: it reads
   the public view (view.scouts_revealed, view.scouts_item through panels.js
   scoutsDecisionItemId) and the seat's own actions, and writes the item's
   lines with panels.js scoutsItemLines, this project's own words and icons,
   never the app's text. The pictures are the app's (catalog.scouts_art,
   display/scouts_art.py), each optional: without one that part is drawn in
   CSS (scouts_stage.css).

   It covers the board square only (#scouts-stage takes the board's grid
   cell), never the decision panel, the seats or the market.

   Pages (second request, same day: every item, not only those with a
   choice, and the card always at hand): the card shows one of this round's
   revealed items, in reveal order -- the Scouts panel's "this round" list.
   During the Scouts step an item it resolves that is not in that list (a
   secret pick of an earlier round's event, or the picks being revealed)
   is a page too, the first. With two or more pages, previous / next
   buttons and a counter page through them (and the arrow keys while focus
   is inside the card); nothing wraps. No page, no card and no button to
   bring it back.

   The picks being revealed (third request, 2026-10-11, after a real game:
   a page that listed the picks still waiting under "secret picks
   revealed" read as if they had been revealed): the page shows what this
   round's Scouts step revealed -- the scouts_secret_revealed events of the
   log since this round's Conflict was revealed (the step comes after
   Round Start, docs/rules/arrakeen-scouts.md 3), each seat with the line
   it picked -- and, apart and worded as not revealed, the seats whose
   picks still wait (view.scouts_secret_pending, which names who picked,
   never what). Nothing found in the log (a log that does not reach back
   that far): the page says the reveal is still to come rather than claim
   one.

   When it opens: during the Scouts step, on the item the step moves to
   (scoutsDecisionItemId), and nothing else takes the card from it there:
   a seat bidding or choosing sees the item it decides on, whatever
   updates arrive meanwhile. Outside the step (it is over, or an item was
   resolved with no choice at all), on a page this browser has not shown
   yet in this game (by game, live or review, round and item; kept in
   memory), at the first such page -- so an item resolved with no choice
   comes up like one with a choice. A page still unseen while the card
   shows another marks the pager button that leads to it as new.
   It stays until the player folds it (its button, `a`, the Scouts panel's
   button). Folded, nothing of it is left over the board (third request,
   2026-10-11: the tab that stayed on the board's top edge covered it); the
   button beside the Scouts panel's heading names the page and brings the
   card back, for the whole round, for every seat, spectators and review
   alike. The one exception: a decision of the viewer's own that the board
   answers (a space, a post, a card or a troop stepper on the board lights
   up) folds it, once per decision, so it never covers a click; reopened
   during that decision, it stays. A round with no item takes it away. */

const scoutsStage = {
  /* The page on the card ("<round>:<id>") and its place, or null and 0
     without a card. */
  page: null,
  index: 0,
  /* This round's pages as last rendered (scoutsStagePages). */
  pages: [],
  open: false,
  /* The viewer's own decision the board fold was last judged for, or null. */
  decision: null,
  /* The item the Scouts step resolved at the last render ("<round>:<id>"),
     or null outside the step. */
  current: null,
  /* Pages this browser has shown (scoutsStageSeenKey): on the card while
     it was open, or put there by the step or an auto-open. */
  seen: new Set(),
  /* Pages an auto-open has already weighed: one still unseen among them
     waits for the player behind its marked button instead of taking the
     card again at every update. */
  weighed: new Set(),
  /* What the card's content was built from: rebuilt only when it changes,
     so an update with the same page neither flickers nor replays. */
  content: null,
  /* The Scouts panel's button that opens and folds the card
     (scoutsStageOpener), made once and kept across renders. */
  opener: null,
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

/* The card's pages, in order: during the Scouts step, the item it resolves
   when that is not one of this round's (a secret pick of an earlier
   round's event, or the picks being revealed), then this round's revealed
   items in reveal order. Empty when the round has none and no step runs. */
function scoutsStagePages() {
  const view = state.view;
  if (!state.summary || !state.summary.arrakeen_scouts || !view) return [];
  const round = view.round_number;
  const ids = (view.scouts_revealed || [])
    .filter(([revealed]) => revealed === round)
    .map(([, id]) => id);
  const current = scoutsDecisionItemId();
  const secrets = view.scouts_item === SCOUTS_SECRETS_CURSOR;
  const pages = ids.map((id) =>
    scoutsStageItemPage(round, id, secrets && id === current));
  if (current && !ids.includes(current)) {
    pages.unshift(current === SCOUTS_SECRETS_CURSOR
      ? scoutsStageSecretsPage(round)
      : scoutsStageItemPage(round, current, secrets));
  }
  return pages;
}

/* One item's page. `secret`: the seat's own reward of a revealed secret
   pick, marked as one, as the decision panel's header does. */
function scoutsStageItemPage(round, id, secret) {
  const item = scoutsItem(id);
  return {
    key: `${round}:${id}`,
    id,
    kind: item.kind,
    name: item.name,
    note: secret ? t("scouts_stage.secrets_name") : null,
    item,
    rows: [],
  };
}

/* The picks this round's Scouts step revealed, as their public
   scouts_secret_revealed payloads ({event_round, item_id, pick, player}),
   in the order the engine revealed them. The step comes after Round Start
   (docs/rules/arrakeen-scouts.md 3), so they are the ones logged since the
   Conflict of `round` was revealed; taken-back steps do not count, and a
   review reads only up to its cursor. */
function scoutsStageRevealedPicks(round) {
  const log = state.review ? reviewLog(state.review) : state.log;
  const picks = [];
  let at = null;
  for (const entry of (log && log.entries) || []) {
    if (entry.undone) continue;
    for (const event of entry.events || []) {
      if (event.kind === "conflict_revealed") at = event.payload.round;
      else if (event.kind === "scouts_secret_revealed" && at === round) {
        picks.push(event.payload);
      }
    }
  }
  return picks;
}

/* Rows of one key ("<event round>|<event>") each, in first-seen order. */
function scoutsStageGroups(rows) {
  const groups = new Map();
  for (const [eventRound, event, value] of rows) {
    const key = `${eventRound}|${event}`;
    if (!groups.has(key)) groups.set(key, { eventRound, event, values: [] });
    groups.get(key).values.push(value);
  }
  return [...groups.values()];
}

/* While the due secret picks resolve (SCOUTS_SECRETS_CURSOR) and the seat
   has no reward of its own to choose, the page stands for the reveal: each
   event whose picks this step revealed, with every seat's picked line,
   then the picks that stay secret, by event, naming only who picked. */
function scoutsStageSecretsPage(round) {
  const revealed = scoutsStageGroups(scoutsStageRevealedPicks(round).map(
    (pick) => [pick.event_round, pick.item_id, pick]));
  const waiting = scoutsStageGroups(state.view.scouts_secret_pending || []);
  const rows = [];
  for (const { eventRound, event, values } of revealed) {
    const item = scoutsItem(event);
    rows.push({
      kind: "event",
      text: t("scouts_stage.secrets_event", { round: eventRound, name: item.name }),
    });
    for (const { pick, player } of values) {
      rows.push({
        kind: "revealed",
        seat: player,
        text: `${playerLabel(player)}: `,
        line: item.lines[pick] || "",
        lineKo: item.lines_ko[pick],
      });
    }
  }
  for (const { eventRound, event, values } of waiting) {
    rows.push({
      kind: "waiting",
      text: t("panels.scouts_secret_waiting", {
        round: eventRound,
        name: scoutsItem(event).name,
        seats: values.map(playerLabel).join(", "),
      }),
    });
  }
  const kinds = [...revealed, ...waiting]
    .map(({ event }) => scoutsItem(event).kind)
    .filter(Boolean);
  return {
    key: `${round}:${SCOUTS_SECRETS_CURSOR}`,
    id: SCOUTS_SECRETS_CURSOR,
    kind: kinds[0] || "event",
    name: revealed.length
      ? t("scouts_stage.secrets_name")
      : t("scouts_stage.secrets_pending_name"),
    note: null,
    item: null,
    rows,
  };
}

/* Whether this browser has put a page up: by game, live play or review
   (a review's round is the reviewed one, view.round_number), round and
   item. */
function scoutsStageSeenKey(page) {
  return `${state.gameId}|${state.review ? "review" : "live"}|${page.key}`;
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
  const pages = state.summary && !el("game-screen").hidden ? scoutsStagePages() : [];
  scoutsStage.pages = pages;
  if (!pages.length) {
    stage.querySelector(".scouts-stage-card").classList.remove("entering");
    stage.hidden = true;
    scoutsStage.page = null;
    scoutsStage.index = 0;
    scoutsStage.open = false;
    scoutsStage.decision = null;
    scoutsStage.current = null;
    labelScoutsStageOpener();
    return;
  }
  const wasHidden = stage.hidden || !scoutsStage.open;
  /* The page browsed to stays; one that went (the step's own item, once
     the step is over) leaves its place to the page now there. */
  let index = pages.findIndex((page) => page.key === scoutsStage.page);
  if (index < 0) index = Math.min(scoutsStage.index, pages.length - 1);
  let opened = false;
  const seen = scoutsStage.seen;
  const id = scoutsDecisionItemId();
  const current = id ? `${state.view.round_number}:${id}` : null;
  if (current) {
    /* The step's item: the card goes to it when it changes and stays
       with whatever the player browses to until it changes again. */
    const at = pages.findIndex((page) => page.key === current);
    if (current !== scoutsStage.current && at >= 0) {
      index = at;
      opened = true;
      seen.add(scoutsStageSeenKey(pages[at]));
    }
  } else {
    const unseen = pages.filter((page) => !seen.has(scoutsStageSeenKey(page)));
    if (unseen.some((page) => !scoutsStage.weighed.has(scoutsStageSeenKey(page)))) {
      index = pages.indexOf(unseen[0]);
      opened = true;
      seen.add(scoutsStageSeenKey(unseen[0]));
    }
    for (const page of pages) scoutsStage.weighed.add(scoutsStageSeenKey(page));
  }
  scoutsStage.current = current;
  if (opened) scoutsStage.open = true;
  /* A decision of the viewer's own that the board answers folds it, when
     the decision comes and when something opens it meanwhile; reopened by
     the player during that decision, it stays. */
  const decision = scoutsStageDecision();
  if ((opened || decision !== scoutsStage.decision) && decision
      && scoutsStageBoardDecision()) {
    scoutsStage.open = false;
  }
  scoutsStage.decision = decision;
  showScoutsStagePage(stage, index);
  applyScoutsStageOpen(wasHidden);
}

/* Put pages[index] on the card, with the pager and the Scouts panel's
   button that go with it. */
function showScoutsStagePage(stage, index) {
  const pages = scoutsStage.pages;
  const shown = pages[index];
  scoutsStage.index = index;
  scoutsStage.page = shown.key;
  if (scoutsStage.open) scoutsStage.seen.add(scoutsStageSeenKey(shown));
  fillScoutsStage(stage, shown);
  const paged = pages.length > 1;
  stage.classList.toggle("paged", paged);
  stage.querySelector(".scouts-stage-pager").hidden = !paged;
  const count = stage.querySelector(".scouts-stage-count");
  const counted = t("scouts_stage.count", { index: index + 1, total: pages.length });
  if (count.textContent !== counted) count.textContent = counted;
  /* Which way an unseen page lies. */
  const unseen = pages.map((page) => !scoutsStage.seen.has(scoutsStageSeenKey(page)));
  const previous = stage.querySelector(".scouts-stage-prev");
  const next = stage.querySelector(".scouts-stage-next");
  previous.disabled = index === 0;
  next.disabled = index === pages.length - 1;
  labelScoutsPagerButton(previous, unseen.slice(0, index).some(Boolean), {
    text: t("scouts_stage.prev"),
    aria: t("scouts_stage.prev_aria"),
    title: t("scouts_stage.prev_title"),
  });
  labelScoutsPagerButton(next, unseen.slice(index + 1).some(Boolean), {
    text: t("scouts_stage.next"),
    aria: t("scouts_stage.next_aria"),
    title: t("scouts_stage.next_title"),
  });
  labelScoutsStageOpener();
}

/* The Scouts panel's button (panels.js renderScouts puts it beside the
   panel's heading): made once, so a render of the panel keeps the node
   and its focus. */
function scoutsStageOpener() {
  if (!scoutsStage.opener) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scouts-stage-open";
    button.setAttribute("aria-controls", "scouts-stage-card");
    button.hidden = true;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      event.currentTarget.focus();
      toggleScoutsStage();
    });
    scoutsStage.opener = button;
    labelScoutsStageOpener();
  }
  return scoutsStage.opener;
}

/* The button's words: with the card folded, "Show card ▸" and the page it
   brings back (and how many more this round has); with it open, "Hide
   card". None without a page. Rebuilt only when the words change. */
function labelScoutsStageOpener() {
  const button = scoutsStage.opener;
  if (!button) return;
  const pages = scoutsStage.pages;
  const shown = scoutsStage.page
    ? pages.find((page) => page.key === scoutsStage.page)
    : null;
  button.hidden = !shown;
  if (!shown) return;
  const open = scoutsStage.open;
  const name = pages.length > 1
    ? t("scouts_stage.show_more", { name: shown.name, more: pages.length - 1 })
    : shown.name;
  const word = open ? t("scouts_stage.fold") : t("scouts_stage.show");
  const signature = JSON.stringify([open, word, name]);
  if (button.dataset.label !== signature) {
    button.dataset.label = signature;
    button.textContent = "";
    const words = document.createElement("span");
    words.className = "scouts-stage-open-word";
    words.textContent = word;
    button.appendChild(words);
    if (!open) {
      const arrow = document.createElement("span");
      arrow.className = "scouts-stage-open-arrow";
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "▸";
      const item = document.createElement("span");
      item.className = "scouts-stage-open-name";
      item.textContent = name;
      button.append(" ", arrow, " ", item);
    }
  }
  button.setAttribute("aria-expanded", String(open));
  button.title = open ? t("scouts_stage.fold_title") : t("scouts_stage.show_title");
}

/* A pager button's words, with the "new" mark when an unseen page lies
   its way; rebuilt only when that changes, so a focused button keeps its
   node. */
function labelScoutsPagerButton(button, fresh, { text, aria, title }) {
  const words = fresh ? t("scouts_stage.new") : "";
  const signature = `${text}|${words}`;
  if (button.dataset.label !== signature) {
    button.dataset.label = signature;
    button.textContent = text;
    if (fresh) {
      const mark = document.createElement("span");
      mark.className = "scouts-stage-new";
      mark.textContent = words;
      button.append(" ", mark);
    }
  }
  button.classList.toggle("has-new", fresh);
  button.setAttribute("aria-label", fresh
    ? t("scouts_stage.with_new", { label: aria })
    : aria);
  button.title = fresh ? t("scouts_stage.with_new", { label: title }) : title;
}

/* Previous (-1) or next (+1) page; false at either end, which does not
   wrap, or without a card. Focus inside the card stays inside: off a
   button that the move disables, onto the other one. */
function pageScoutsStage(step) {
  const stage = el("scouts-stage");
  const pages = scoutsStage.pages;
  if (stage.hidden || !scoutsStage.open || !scoutsStage.page) return false;
  const index = scoutsStage.index + step;
  if (index < 0 || index >= pages.length) return false;
  const card = stage.querySelector(".scouts-stage-card");
  const focused = document.activeElement;
  const hadFocus = card.contains(focused);
  showScoutsStagePage(stage, index);
  if (hadFocus && focused.disabled) {
    const other = step < 0
      ? stage.querySelector(".scouts-stage-next")
      : stage.querySelector(".scouts-stage-prev");
    (other.disabled ? card : other).focus();
  }
  return true;
}

/* Build the card's content, unless it was built from the same thing. */
function fillScoutsStage(stage, shown) {
  const art = (state.catalog && state.catalog.scouts_art) || {};
  const painting = art[shown.kind] || null;
  const signature = JSON.stringify([
    shown.key,
    shown.name,
    shown.note,
    shown.rows,
    TERM_LANGUAGE,
    painting,
    Object.keys(SCOUTS_STAGE_PIECES).map(scoutsArtUrl),
    Boolean(boardScan()),
  ]);
  if (signature === scoutsStage.content) return;
  scoutsStage.content = signature;

  stage.dataset.item = shown.id;
  stage.dataset.kind = shown.kind;
  /* The board scan is square and top-aligned in its cell; the card's frame
     takes the same square. The text board fills the cell. */
  stage.classList.toggle("no-scan", !boardScan());
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
  /* The reveal page's rows (scoutsStageSecretsPage): an event's heading,
     a seat's revealed line, a pick still secret. */
  for (const row of shown.rows) {
    const node = document.createElement("div");
    if (row.kind === "event") {
      node.className = "scouts-stage-event";
      node.appendChild(phrase(row.text));
    } else if (row.kind === "revealed") {
      node.className = "scouts-line scouts-stage-revealed";
      node.dataset.seat = String(row.seat);
      node.append(row.text, effectNode(row.line, row.lineKo));
    } else {
      node.className = "scouts-line scouts-stage-waiting";
      node.appendChild(phrase(row.text));
    }
    body.appendChild(node);
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
}

/* Show the card, or fold it away with nothing of it left over the board.
   `entering`: the card comes into view, so it slides in once
   (scouts_stage.css; nothing moves under reduced motion). */
function applyScoutsStageOpen(entering) {
  const stage = el("scouts-stage");
  const open = scoutsStage.open;
  stage.hidden = !open;
  const card = stage.querySelector(".scouts-stage-card");
  /* An update meanwhile leaves a running slide-in alone. */
  if (!open) card.classList.remove("entering");
  else if (entering) {
    card.classList.remove("entering");
    /* A reflow between removing and adding restarts the animation. */
    void card.offsetWidth;
    card.classList.add("entering");
  }
  labelScoutsStageOpener();
}

/* The card's button, the Scouts panel's button and the shortcut. False
   when there is no card. Folded from inside the card, focus goes to the
   panel's button, which brings it back. */
function toggleScoutsStage() {
  const stage = el("scouts-stage");
  if (!scoutsStage.page) return false;
  const card = stage.querySelector(".scouts-stage-card");
  const hadFocus = card.contains(document.activeElement);
  scoutsStage.open = !scoutsStage.open;
  applyScoutsStageOpen(scoutsStage.open);
  if (hadFocus && !scoutsStage.open && scoutsStage.opener) {
    scoutsStage.opener.focus({ preventScroll: true });
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
  const pager = [[".scouts-stage-prev", -1], [".scouts-stage-next", 1]];
  for (const [selector, step] of pager) {
    stage.querySelector(selector).addEventListener("click", (event) => {
      event.stopPropagation();
      event.currentTarget.focus();
      pageScoutsStage(step);
    });
  }
  /* The arrow keys page while focus is inside the card, and only there:
     elsewhere they belong to others (a focused column splitter; Alt with
     an arrow moves a hand card). */
  stage.querySelector(".scouts-stage-card").addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (scoutsStage.pages.length < 2) return;
    event.preventDefault();
    pageScoutsStage(event.key === "ArrowLeft" ? -1 : 1);
  });
  /* Over, or cut short by the card going out of view. */
  for (const type of ["animationend", "animationcancel"]) {
    stage.querySelector(".scouts-stage-card").addEventListener(type, (event) => {
      event.currentTarget.classList.remove("entering");
    });
  }
}
