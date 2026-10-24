"use strict";

/* ---------- help and announcements ---------- */

/* The live region: what a screen reader should hear without looking — whose
   turn it now is, and how the game ended. Errors have role="alert" of their
   own (index.html). Clearing first makes the same sentence read again. */
let announceTimer = 0;

function announce(text) {
  clearAnnouncement();
  announceTimer = window.setTimeout(() => {
    el("announcer").textContent = text;
  }, 50);
}

/* Drop what is said and what is about to be: a pending sentence must not
   land after a newer one, or after a switch of language. */
function clearAnnouncement() {
  window.clearTimeout(announceTimer);
  el("announcer").textContent = "";
}

/* Announce each change of the seat to act, and the end of the game, once.
   A review walks a finished record, so it announces nothing. */
let announcedTurn;

/* The seats this screen speaks for: the claimed ones on a remote server, the
   one on screen on an open server (pickViewSeat moves it to whoever acts). */
function isMine(seat) {
  return isRemote() ? mySeats().includes(seat) : seat === state.viewSeat;
}

function announceTurn(summary) {
  if (!summary || state.review) return;
  let key;
  let text;
  if (summary.finished) {
    const first = (summary.standings || []).find((entry) => entry.rank === 1);
    key = "finished";
    text = first
      ? t("help.announce_finished_winner", { name: playerLabel(first.player) })
      : t("common.game_over");
  } else if (typeof summary.confirmation === "number") {
    /* A seat's turn has ended but can still be taken back: decision.owner
       already names the NEXT seat, yet nobody moves until this one confirms
       (renderBanner). Announcing the next seat here told it to act early and
       then swallowed the real hand-over, whose key was the same. */
    const seat = summary.confirmation;
    key = `confirm:${seat}`;
    text = isMine(seat)
      ? t("help.announce_turn_end_mine", { name: playerLabel(seat) })
      : t("help.announce_turn_end_other", { name: playerLabel(seat) });
  } else if (summary.decision && summary.decision.turn_end_ready) {
    /* An Agent turn with nothing mandatory left: it ends only with the
       seat's own press (OQ-095), so say so once, like a held turn end. */
    const owner = summary.decision.owner;
    key = `ready:${owner}`;
    text = isMine(owner)
      ? t("help.announce_turn_end_mine", { name: playerLabel(owner) })
      : t("help.announce_turn_end_other", { name: playerLabel(owner) });
  } else if (summary.decision) {
    const owner = summary.decision.owner;
    /* A turn's start (its "turn" frame) keys apart from the rest of it, so
       a seat's own next turn right after its last one (every other seat has
       revealed) is announced; going on from the start into the same turn
       says nothing new. */
    const start = summary.decision.kind === "turn";
    key = start ? `start:${owner}` : `seat:${owner}`;
    if (!start && announcedTurn === `start:${owner}`) {
      announcedTurn = key;
      return;
    }
    /* One screen can hold several human seats (an open server), so even
       "your turn" says which seat. */
    text = isMine(owner)
      ? t("help.announce_turn_mine", {
          name: playerLabel(owner),
          prompt: promptText(summary.decision.prompt),
        })
      : t("help.announce_turn_other", { name: playerLabel(owner) });
  } else {
    return;
  }
  if (key === announcedTurn) return;
  announcedTurn = key;
  announce(text);
}

/* ---------- the help panel ---------- */

/* What the seat panel draws that no rulebook icon explains: how to draw
   the mark, and what it means (a phrase template). */
const HELP_SEAT_MARKS = [
  [() => commanderStatIcon(phraseText("{commander}")), "help.seat_mark_commander"],
  [() => firstPlayerMark(), "help.seat_mark_first_player"],
  [helpClockSample, "help.seat_mark_clock"],
];

/* A seat's play clock as its panel draws it (clock.js), running; a sample,
   so the painter never touches it. */
function helpClockSample() {
  const sample = document.createElement("span");
  sample.className = "seat-clock running";
  sample.textContent = "1:23";
  return sample;
}

const HELP_SHORTCUTS = [
  ["c", "help.shortcut_collapse_columns"],
  ["s", "help.shortcut_expand_seats"],
  ["Esc", "help.shortcut_cancel"],
  ["?", "help.shortcut_open_help"],
  /* The column handles and the hand's own order (layout.js). */
  ["Alt+←/→", "help.shortcut_layout"],
];

const HELP_TURN = [
  "help.turn_agent",
  "help.turn_confirm",
  "help.turn_undo_limit",
  "help.turn_reveal",
];

/* The project's rulings in the three groups the user asked for
   (2026-10-24): where sources disagree and one was chosen, where only the
   app plays it differently, and every other ruling of a gap. The list is
   the catalog's (display.house_rulings), the same one
   docs/rules/house-rulings-ko.md is written from. */
const HELP_RULING_GROUPS = [
  ["sources_differ", "help.rulings_sources_differ"],
  ["app_differs", "help.rulings_app_differs"],
  ["project", "help.rulings_project"],
];

let helpOpener = null;

function helpSection(parent, title) {
  const heading = document.createElement("h3");
  heading.textContent = title;
  const body = document.createElement("div");
  body.className = "help-grid";
  parent.append(heading, body);
  return body;
}

function helpRow(grid, mark, text) {
  const key = document.createElement("span");
  key.className = "help-mark";
  if (typeof mark === "string") key.textContent = mark;
  else key.appendChild(mark);
  const what = document.createElement("span");
  what.append(text);
  grid.append(key, what);
}

/* One folded list per group, closed at first so the panel still opens on
   the turn walkthrough; inside, Uprising first and then the base game and
   Rise of Ix, which are not playable yet. */
function helpRulings(parent) {
  const rulings = (state.catalog && state.catalog.house_rulings) || [];
  if (!rulings.length) return;
  const heading = document.createElement("h3");
  heading.textContent = t("help.rulings_heading");
  const intro = document.createElement("p");
  intro.className = "help-rulings-intro muted";
  intro.textContent = t("help.rulings_intro");
  parent.append(heading, intro);
  const korean = TERM_LANGUAGE === "ko";
  for (const [group, textKey] of HELP_RULING_GROUPS) {
    const entries = rulings.filter((entry) => entry.group === group);
    if (!entries.length) continue;
    const details = document.createElement("details");
    details.className = "help-rulings";
    details.dataset.group = group;
    const summary = document.createElement("summary");
    summary.textContent = t(textKey, { count: entries.length });
    const list = document.createElement("dl");
    for (const entry of entries) {
      /* The question's number stays off the page (user decision
         2026-10-14: "플레이하는 사람 입장에서는 OQ가 뭔지 상관 없으니까");
         the attribute only lets a check find an entry. */
      const term = document.createElement("dt");
      term.dataset.oq = entry.oq;
      term.textContent = korean ? entry.title_ko : entry.title;
      const tags = [];
      if (entry.game === "base_ix") tags.push(t("help.rulings_base_ix"));
      if (entry.engine_pending) tags.push(t("help.rulings_engine_pending"));
      for (const text of tags) {
        const tag = document.createElement("span");
        tag.className = "help-ruling-tag";
        tag.textContent = text;
        term.append(" ", tag);
      }
      const what = document.createElement("dd");
      what.textContent = korean ? entry.ruling_ko : entry.ruling;
      const sources = korean ? entry.sources_ko : entry.sources;
      if (sources) {
        const line = document.createElement("span");
        line.className = "help-ruling-sources muted";
        line.textContent = t("help.rulings_sources", { sources });
        what.append(line);
      }
      list.append(term, what);
    }
    details.append(summary, list);
    parent.appendChild(details);
  }
}

function openHelp() {
  const panel = el("help");
  if (!panel.hidden) return;
  helpOpener = document.activeElement;
  const body = el("help-body");
  body.textContent = "";

  const heading = document.createElement("h2");
  heading.id = "help-title";
  heading.textContent = t("help.title");
  const close = document.createElement("button");
  close.type = "button";
  close.className = "help-close";
  close.textContent = t("common.close");
  close.addEventListener("click", closeHelp);
  heading.appendChild(close);
  body.appendChild(heading);

  /* The turn walkthrough first: it is the one section a new player needs
     before any other, so it must not scroll off below the icon legend and
     the seat-panel marks (it used to be built last and fell below the
     fold at common panel heights). */
  const turn = document.createElement("h3");
  turn.textContent = t("help.turn_heading");
  const list = document.createElement("ul");
  list.className = "help-turn";
  for (const line of HELP_TURN) {
    const item = document.createElement("li");
    item.textContent = t(line);
    list.appendChild(item);
  }
  if (state.summary && state.summary.arrakeen_scouts) {
    /* Arrakeen Scouts' step and its sealed choices, only in such a game. */
    const item = document.createElement("li");
    item.textContent = t("help.turn_scouts");
    list.appendChild(item);
  }
  body.append(turn, list);

  /* Every rule term that has a printed icon, from the one table the rest
     of the UI reads, so the legend cannot drift from what is drawn. */
  const icons = helpSection(body, t("help.icons_heading"));
  for (const [name, term] of Object.entries(TERMS)) {
    if (!term.icon || (name !== "agent" && !iconUrl(term.icon))) continue;
    const label = document.createElement("span");
    label.append(term[TERM_LANGUAGE] || term.en);
    if (TERM_LANGUAGE !== "en") {
      const english = document.createElement("span");
      english.className = "muted";
      english.textContent = ` ${term.en}`;
      label.appendChild(english);
    }
    const row =
      name === "agent"
        ? agentPieceIcon(term[TERM_LANGUAGE] || term.en)
        : icon(term.icon, term[TERM_LANGUAGE] || term.en);
    row.dataset.term = name;
    helpRow(icons, row, label);
  }

  const marks = helpSection(body, t("help.seat_panel_heading"));
  for (const [draw, textKey] of HELP_SEAT_MARKS) helpRow(marks, draw(), t(textKey));

  const keys = helpSection(body, t("help.shortcuts_heading"));
  const shortcuts = [...HELP_SHORTCUTS];
  /* The Scouts card's key, only in a game of Arrakeen Scouts. */
  if (state.summary && state.summary.arrakeen_scouts) {
    shortcuts.splice(2, 0, ["a", "help.shortcut_scouts_card"]);
  }
  for (const [key, textKey] of shortcuts) {
    const kbd = document.createElement("kbd");
    kbd.textContent = key;
    helpRow(keys, kbd, t(textKey));
  }

  helpRulings(body);

  panel.hidden = false;
  close.focus();
}

function closeHelp() {
  const panel = el("help");
  if (panel.hidden) return;
  panel.hidden = true;
  el("help-body").textContent = "";
  /* Back where the reader was, if that is still on the page. */
  if (helpOpener && document.contains(helpOpener)) helpOpener.focus();
  helpOpener = null;
}
