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
      ? t("help.announce_confirm_mine", { name: playerLabel(seat) })
      : t("help.announce_confirm_other", { name: playerLabel(seat) });
  } else if (summary.decision) {
    const owner = summary.decision.owner;
    key = `seat:${owner}`;
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
  [() => commanderChip(2, "{garrison}"), "help.seat_mark_commander"],
  [() => "1st", "help.seat_mark_first_player"],
  [
    () => {
      const mark = document.createElement("span");
      mark.append(phraseText("{conflict} "), icon("troop", phraseText("{troop}")), "3");
      return mark;
    },
    "help.seat_mark_conflict",
  ],
];

const HELP_SHORTCUTS = [
  ["c", "help.shortcut_collapse_columns"],
  ["s", "help.shortcut_expand_seats"],
  ["Esc", "help.shortcut_cancel"],
  ["?", "help.shortcut_open_help"],
];

const HELP_TURN = [
  "help.turn_agent",
  "help.turn_confirm",
  "help.turn_undo_limit",
  "help.turn_reveal",
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

  /* Every rule term that has a printed icon, from the one table the rest
     of the UI reads, so the legend cannot drift from what is drawn. */
  const icons = helpSection(body, t("help.icons_heading"));
  for (const [name, term] of Object.entries(TERMS)) {
    if (!term.icon || !iconUrl(term.icon)) continue;
    const label = document.createElement("span");
    label.append(term[TERM_LANGUAGE] || term.en);
    if (TERM_LANGUAGE !== "en") {
      const english = document.createElement("span");
      english.className = "muted";
      english.textContent = ` ${term.en}`;
      label.appendChild(english);
    }
    const row = icon(term.icon, term[TERM_LANGUAGE] || term.en);
    row.dataset.term = name;
    helpRow(icons, row, label);
  }

  const marks = helpSection(body, t("help.seat_panel_heading"));
  for (const [draw, textKey] of HELP_SEAT_MARKS) helpRow(marks, draw(), t(textKey));

  const keys = helpSection(body, t("help.shortcuts_heading"));
  for (const [key, textKey] of HELP_SHORTCUTS) {
    const kbd = document.createElement("kbd");
    kbd.textContent = key;
    helpRow(keys, kbd, t(textKey));
  }

  const turn = document.createElement("h3");
  turn.textContent = t("help.turn_heading");
  const list = document.createElement("ul");
  list.className = "help-turn";
  for (const line of HELP_TURN) {
    const item = document.createElement("li");
    item.textContent = t(line);
    list.appendChild(item);
  }
  body.append(turn, list);

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
