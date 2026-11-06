"use strict";

/* ---------- the phone layout ---------- */

/* Below 600px wide (docs/mobile-ui-plan.md, user decision 2026-11-06) the
   table is one column: one view at a time (the board, the hand, the
   players, the shared cards or the log), the decision panel under it, and
   a tab bar to switch views. The header keeps the round and phase and folds
   its buttons into a menu. phone.css draws all of it inside one media
   query; this file keeps which view is shown and whether the menu is open.
   At 600px and wider the tab bar and the menu button are not displayed, so
   nothing here changes what a desktop or a narrow window shows. */

const PHONE_QUERY = window.matchMedia("(max-width: 599px)");
const PHONE_VIEWS = ["board", "hand", "seats", "market", "log"];

function phoneLayout() {
  return PHONE_QUERY.matches;
}

function showPhoneView(view) {
  if (!PHONE_VIEWS.includes(view)) return;
  el("game-screen").dataset.phoneView = view;
  for (const button of document.querySelectorAll("#phone-tabs [data-view]")) {
    button.setAttribute("aria-pressed", button.dataset.view === view ? "true" : "false");
  }
}

function phoneMenuOpen() {
  return document.querySelector("header").classList.contains("menu-open");
}

function setPhoneMenu(open) {
  document.querySelector("header").classList.toggle("menu-open", open);
  el("phone-menu").setAttribute("aria-expanded", open ? "true" : "false");
}

/* The staged Agent turn on a phone (turn.js pickStep): a card picked in the
   hand view has its spaces on the board, so the board comes up; a space
   picked first has its cards in the hand. */
function followPickOnPhone(pick) {
  if (!phoneLayout() || !pick) return;
  if (pick.cardId && !pick.spaceId) {
    /* A Graft card that a hand card can join waits for that partner, in
       the hand (turn.hint_graft_required). */
    const hand = (state.view && state.view.private && state.view.private.hand) || [];
    const partnerFirst =
      isGraftCard(pick.cardId) && !pick.partnerId &&
      hand.some((other) => canPair(pick.cardId, other));
    if (!partnerFirst) showPhoneView("board");
  } else if (pick.spaceId && !pick.cardId) showPhoneView("hand");
}

/* The picked card's spaces as buttons under the step hint (turn.js
   renderActionPanel): at the screen's width a board space is about
   27x21px. A button does what a tap on its lit space does. */
function phoneSpaceButtons(candidates) {
  const list = document.createElement("div");
  list.className = "phone-space-list";
  const spaces = [...new Set(candidates.map((action) => action.arguments.space_id))];
  for (const spaceId of spaces.filter(Boolean)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "phone-space";
    button.dataset.space = spaceId;
    button.textContent = spaceName(spaceId);
    button.disabled = state.busy;
    button.addEventListener("click", (event) => {
      /* As a board space's own click does: a choice of options this opens
         (turn.js openPlacementChooser) must not meet the document's
         click-elsewhere close on the way up. */
      event.stopPropagation();
      tableClick(spaceId, lookup(spaceId, "spaces"), button);
    });
    list.appendChild(button);
  }
  return list;
}

/* After every render (render.js): a tab whose view holds something the
   seat's decision can take (a lit card or space) carries a mark, so a
   decision about the hand or the shared cards says where to look. */
const PHONE_CUES = {
  board: "#board .legal",
  hand: "#private-zone .legal",
  market: "#market .legal",
  seats: "#seats .legal",
};

function markPhoneTabs() {
  for (const [view, selector] of Object.entries(PHONE_CUES)) {
    const tab = document.querySelector(`#phone-tabs [data-view="${view}"]`);
    if (tab) tab.classList.toggle("cue", Boolean(document.querySelector(selector)));
  }
}

function setBoardZoom(on) {
  el("game-screen").classList.toggle("board-zoomed", on);
  el("phone-board-zoom").setAttribute("aria-pressed", on ? "true" : "false");
}

function watchPhoneLayout() {
  el("phone-board-zoom").addEventListener("click", () =>
    setBoardZoom(!el("game-screen").classList.contains("board-zoomed"))
  );
  for (const button of document.querySelectorAll("#phone-tabs [data-view]")) {
    button.addEventListener("click", () => showPhoneView(button.dataset.view));
  }
  el("phone-menu").addEventListener("click", () => setPhoneMenu(!phoneMenuOpen()));
  /* A choice from the menu, or a tap anywhere else, closes it: caught on
     the way down, so a tap whose own handler stops it (a board space, a
     hand card, ⓘ) closes it too. The AI pace list stays open while it is
     being chosen from; its change closes it. */
  document.addEventListener(
    "click",
    (event) => {
      if (!phoneMenuOpen() || event.target.closest("#phone-menu, #ai-pace")) return;
      setPhoneMenu(false);
    },
    true,
  );
  el("ai-pace").addEventListener("change", () => setPhoneMenu(false));
  /* Turned across 600px (a phone rotated): the menu's buttons go back to
     the header, and the table is drawn again for the other layout, whose
     decision panel has or lacks the phone's steps and space buttons. */
  PHONE_QUERY.addEventListener("change", () => {
    setPhoneMenu(false);
    if (state.summary && !el("game-screen").hidden) render();
  });
  showPhoneView(el("game-screen").dataset.phoneView || "board");
}
