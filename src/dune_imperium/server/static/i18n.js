"use strict";

/* ---------- language (ko / en) ---------- */

/* The client speaks Korean or English, never a mix (사용자 결정 2026-09-20).
   TERM_LANGUAGE (labels.js) is the one switch: rule terms, the label tables,
   the strings of UI_TEXT, the engine's prompts and the static page all read
   it. Card, Leader, space, Conflict and Contract names and printed card text
   stay English in both (docs/ui-improvement-plan.md, "언어 정책"). */
const LANGUAGE_KEY = "dune.language";
const LANGUAGES = ["ko", "en"];

/* The label tables swap their contents in place, so every call site keeps
   reading ACTION_LABELS[id]. The Korean is snapshotted here, before any
   swap; the English twins are LABELS_EN (labels_en.js), keyed alike. */
const LABEL_TABLES = {
  PHASE_LABELS,
  FACTION_LABELS,
  ACTION_LABELS,
  EVENT_LABELS,
  EFFECT_ICON_LABELS,
  RESEARCH_BONUS_LABELS,
  TLEILAXU_TRACK_LABELS,
  FEYD_TRACK_LABELS,
  VALUE_LABELS,
  PAYLOAD_KEY_LABELS,
};
/* [value, label] lists (core.js): their labels swap the same way. */
const LABEL_LISTS = { SEAT_KINDS, AGENT_ICON_GROUPS };

const LABELS_KO = (() => {
  const copy = {};
  for (const [name, table] of Object.entries(LABEL_TABLES)) copy[name] = { ...table };
  for (const [name, list] of Object.entries(LABEL_LISTS)) {
    copy[name] = Object.fromEntries(list.map(([value, label]) => [value, label]));
  }
  return copy;
})();

function applyLabelLanguage(lang) {
  const source = lang === "en" ? LABELS_EN : LABELS_KO;
  for (const [name, table] of Object.entries(LABEL_TABLES)) {
    const values = source[name] || {};
    for (const key of Object.keys(table)) {
      table[key] = key in values ? values[key] : LABELS_KO[name][key];
    }
  }
  for (const [name, list] of Object.entries(LABEL_LISTS)) {
    const values = source[name] || {};
    for (const pair of list) {
      pair[1] = pair[0] in values ? values[pair[0]] : LABELS_KO[name][pair[0]];
    }
  }
}

/* ---------- strings: t() and tNode() ---------- */

/* UI_TEXT (ui_text.js) holds every string the client writes that is not a
   rule term, a name or engine text, as { ko, en }. In a template, {{name}}
   is a hole the caller fills and {term} / {term:3} a rule term (TERMS) in
   the current language. Holes are filled after the terms are expanded, so a
   value — a player's name is somebody else's input — is never read as a
   term or as markup. */
const HOLE = /\{\{([A-Za-z0-9_]+)\}\}/g;

function textTemplate(key) {
  const entry = UI_TEXT[key];
  if (!entry) return `⟦${key}⟧`;
  return entry[TERM_LANGUAGE] || entry.ko;
}

/* The string: rule terms as words. */
function t(key, vars) {
  const template = textTemplate(key);
  let out = "";
  let index = 0;
  for (const match of template.matchAll(HOLE)) {
    out += phraseText(template.slice(index, match.index));
    const name = match[1];
    out += vars && name in vars ? String(vars[name]) : match[0];
    index = match.index + match[0].length;
  }
  return out + phraseText(template.slice(index));
}

/* The nodes: rule terms as icons, holes as text nodes (or the node given). */
function tNode(key, vars) {
  const template = textTemplate(key);
  const fragment = document.createDocumentFragment();
  let index = 0;
  for (const match of template.matchAll(HOLE)) {
    fragment.appendChild(phrase(template.slice(index, match.index)));
    const name = match[1];
    const value = vars && name in vars ? vars[name] : match[0];
    fragment.append(value instanceof Node ? value : String(value));
    index = match.index + match[0].length;
  }
  fragment.appendChild(phrase(template.slice(index)));
  return fragment;
}

/* ---------- the engine's prompts ---------- */

/* Decision prompts come from rules/*.py in English. Korean maps them by the
   exact sentence (PROMPT_KO) or a pattern for the formatted ones
   (PROMPT_KO_PATTERNS, $1 for a group); an unknown prompt stays English. */
function promptText(prompt) {
  if (!prompt || TERM_LANGUAGE === "en") return prompt;
  if (Object.prototype.hasOwnProperty.call(PROMPT_KO, prompt)) {
    return phraseText(PROMPT_KO[prompt]);
  }
  for (const [pattern, korean] of PROMPT_KO_PATTERNS) {
    const match = prompt.match(new RegExp(pattern));
    if (match) {
      return phraseText(korean.replace(/\$(\d)/g, (whole, group) => match[Number(group)]));
    }
  }
  return prompt;
}

/* ---------- the static page ---------- */

/* index.html marks its text with data-i18n="<key>" (the element's text) and
   data-i18n-attr="title=<key>;aria-label=<key>" (attributes). The Korean
   stays inline as the page before any script runs. */
function applyStaticText() {
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  for (const node of document.querySelectorAll("[data-i18n-attr]")) {
    for (const pair of node.dataset.i18nAttr.split(";")) {
      const [attribute, key] = pair.split("=").map((part) => part.trim());
      if (attribute && key) node.setAttribute(attribute, t(key));
    }
  }
}

/* ---------- switching ---------- */

/* `redraw` false: only the switch itself (init draws everything next). */
function setLanguage(lang, redraw = true) {
  const chosen = LANGUAGES.includes(lang) ? lang : "ko";
  TERM_LANGUAGE = chosen;
  storageSet(LANGUAGE_KEY, chosen);
  applyLabelLanguage(chosen);
  document.documentElement.lang = chosen;
  applyStaticText();
  const toggle = el("language-toggle");
  /* The button names the other language, in that language. */
  toggle.textContent = chosen === "en" ? "한국어" : "English";
  toggle.lang = chosen === "en" ? "ko" : "en";
  if (redraw) redrawForLanguage();
}

function loadLanguage() {
  setLanguage(storageGet(LANGUAGE_KEY), false);
}

/* Whatever is on screen, drawn again in the new language. */
function redrawForLanguage() {
  /* Built once and kept while hidden: redrawn whether on screen or not. */
  buildSeatSelects();
  if (!el("setup-screen").hidden) {
    loadGameList().catch(() => {});
    loadSaveList().catch(() => {});
  } else {
    /* Hidden, they would show the old language until showHome reloads them. */
    el("game-list").textContent = "";
    el("save-list").textContent = "";
  }
  if (!el("lobby-screen").hidden && state.summary) renderLobby();
  if (state.summary && !el("game-screen").hidden) {
    if (state.review) {
      labelReviewBar(state.review.seat);
      /* The view in hand draws at once, and so do the status line and the
         play button of the step on screen; the seek below refreshes them. */
      if (state.review.round !== null) writeReviewStatus(state.review);
      renderPlaybackControls();
      render();
      /* A seek, not a bare reviewGoto: it holds playback and schedules the
         next move, where a bare request would supersede a playing tick and
         leave playback waiting forever. */
      reviewSeek(state.review.cursor);
    } else {
      render();
    }
    noticeTurn();
  }
  /* The live region still holds a sentence in the old language: say the
     current turn again in the new one (a review says nothing). */
  clearAnnouncement();
  announcedTurn = undefined;
  announceTurn(state.summary);
  if (!el("help").hidden) {
    const opener = helpOpener;
    closeHelp();
    openHelp();
    helpOpener = opener;
  }
}
