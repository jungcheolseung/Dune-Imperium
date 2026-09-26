"use strict";

/* ---------- rendering ---------- */

/* ---------- icons ---------- */

/* Rulebook icons (catalog.icons, served from the machine-local extraction
   of the official Icon Guide) with a text fallback when the set is absent. */
const SEAT_COLORS = ["#2fb3ff", "#ff5a4e", "#7ddc6a", "#f4c542"];

/* Player pieces traced from the rulebook art.  The rulebook Icon Guide's
   agent.png has a + because it means gaining the third Agent; ordinary UI
   references to an Agent use this unadorned piece silhouette instead. */
const PIECE_SHAPES = {
  agent: {
    viewBox: "0 0 52 81",
    outline:
      "M26 1 C29.6 1 35.2 5.5 35.8 12.6 L39 14.6 L50.6 42.2 C51.3 43 51.3 43.8 50.6 44.6" +
      " L41.6 54 L41.6 65 L47 76.6 L47 80 L5 80 L5 76.6 L10.4 65 L10.4 54 L1.4 44.6" +
      " C0.7 43.8 0.7 43 1.4 42.2 L13 14.6 L16.2 12.6 C16.8 5.5 22.4 1 26 1 Z",
  },
  spy: {
    viewBox: "0 0 56 80",
    outline: "M1 16 A27 15 0 0 1 55 16 L55 64 A27 15 0 0 1 1 64 Z",
    top: { cx: 28, cy: 18, rx: 20, ry: 9 },
  },
};

function agentPieceIcon(label) {
  const svgNs = "http://www.w3.org/2000/svg";
  const shape = PIECE_SHAPES.agent;
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("class", "icon agent-piece-icon");
  svg.setAttribute("viewBox", shape.viewBox);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", label);
  const title = document.createElementNS(svgNs, "title");
  title.textContent = label;
  const path = document.createElementNS(svgNs, "path");
  path.setAttribute("d", shape.outline);
  svg.append(title, path);
  return svg;
}

/* A count of Agents, drawn with the plain piece like amount() draws the
   other counts with their icons. */
function agentAmount(label, count) {
  const wrap = document.createElement("span");
  wrap.className = "amount";
  wrap.title = `${count} ${label}`;
  wrap.append(String(count), agentPieceIcon(label));
  return wrap;
}

function iconUrl(name) {
  const icons = state.catalog && state.catalog.icons;
  return icons && icons[name] ? icons[name] : null;
}

/* `text` is what stands in for the image when the icon set is absent; it
   defaults to the label. Card text passes its own English words there, so
   only the tooltip speaks the chosen language. */
function icon(name, label, text = label) {
  const url = iconUrl(name);
  if (url) {
    const img = document.createElement("img");
    img.className = "icon";
    img.src = url;
    img.alt = label;
    img.title = label;
    return img;
  }
  const span = document.createElement("span");
  span.className = "icon-text";
  span.textContent = text;
  if (text !== label) span.title = label;
  return span;
}

function amount(name, label, count, text = label) {
  const wrap = document.createElement("span");
  wrap.className = "amount";
  wrap.title = `${count} ${label}`;
  wrap.append(String(count), icon(name, label, text));
  return wrap;
}

const FACTION_ICON_KEY = {
  Emperor: "emperor",
  "Spacing Guild": "spacing_guild",
  "Bene Gesserit": "bene_gesserit",
  Fremen: "fremen",
};

/* A card-text icon for a TERMS entry: the tooltip is the glossary word in
   the chosen language, the fallback text the card's own English `words`
   (glossary-ko.md: card text stays English, with term tooltips). */
function termLabel(term) {
  return TERMS[term][TERM_LANGUAGE] || TERMS[term].en;
}

function textIcon(term, words) {
  if (term === "agent") return agentPieceIcon(termLabel(term));
  return icon(TERMS[term].icon, termLabel(term), words);
}

function textAmount(term, count, words) {
  return amount(TERMS[term].icon, termLabel(term), count, words);
}

/* Glossary that turns the catalog's English effect text into the printed
   iconography: each rule is tried at the current position (sticky), the
   first match wins, and unmatched text is copied through. Only display —
   the text itself stays the server's. */
const ICON_RULES = [
  [/(?:Gain |Pay )?(\d+) (solari|spice|water)\b/y, (m) => textAmount(m[2], m[1], m[2])],
  [/\b(solari|spice|water)\b/y, (m) => textIcon(m[1], m[1])],
  [/Draw (\d+) Intrigue cards?/y, (m) => textAmount("intrigue", m[1], "Intrigue card")],
  [/Draw (\d+) cards?/y, (m) => textAmount("draw", m[1], "Draw")],
  [/Intrigue cards?/y, () => textIcon("intrigue", "Intrigue card")],
  [/(?:Recruit |Gain )?(\d+) troops?\b/y, (m) => textAmount("troop", m[1], "troop")],
  [/\btroops?\b/y, () => textIcon("troop", "troop")],
  [
    /(?:Gain )?(\d+) (Emperor|Spacing Guild|Bene Gesserit|Fremen) Influence/y,
    (m) => textAmount(`influence_${FACTION_ICON_KEY[m[2]]}`, m[1], `${m[2]} Influence`),
  ],
  [
    /(Emperor|Spacing Guild|Bene Gesserit|Fremen) Influence/y,
    (m) => textIcon(`influence_${FACTION_ICON_KEY[m[1]]}`, `${m[1]} Influence`),
  ],
  [/Lose (\d+) Influence/y, (m) => textAmount("influence_lose", m[1], "Lose Influence")],
  [/(?:Gain )?(\d+) Influence/y, (m) => textAmount("influence_any", m[1], "Influence")],
  /* No glossary row names "the visited Faction"; the icon is the any-Faction
     Influence, so its tooltip is that word. */
  [
    /Influence with the visited Faction/y,
    () => icon(
      "influence_any",
      TERM_LANGUAGE === "en" ? "visited Faction Influence" : termLabel("influence_any"),
      "visited Faction Influence",
    ),
  ],
  [/(\d+) Persuasion/y, (m) => textAmount("persuasion", m[1], "Persuasion")],
  [/\bPersuasion\b/y, () => textIcon("persuasion", "Persuasion")],
  [/(\d+) (?:swords?|strength)\b/y, (m) => textAmount("sword", m[1], "sword")],
  [/\bswords?\b/y, () => textIcon("sword", "sword")],
  [
    /(?:Gain )?(\d+) (?:Victory Points?|VP)\b/y,
    (m) => textAmount("victory_point", m[1], "Victory Point"),
  ],
  [/\b(?:Victory Points?|VP)\b/y, () => textIcon("victory_point", "Victory Point")],
  [/\b[Tt]rash an Intrigue card\b/y, () => textIcon("trash_intrigue", "Trash an Intrigue card")],
  [/\b[Tt]rash\b/y, () => textIcon("trash", "Trash")],
  /* "your discard pile" names the pile, which has no icon: kept as words so
     the Discard rule does not title it with the discard action. */
  [/\b[Dd]iscard piles?\b/y, (m) => document.createTextNode(m[0])],
  [/\b[Dd]iscard\b/y, () => textIcon("discard", "Discard")],
  [/\b(?:a |an )?Sp(?:y|ies)\b/y, (m) => textIcon("spy", m[0].trim())],
  /* A line's box label ("Agent: …" for an Agent box, "Agent Turn: …",
     "On discard: …") names where the effect sits, not a piece: kept as
     words. As an icon it read like part of the card title above it
     ("Double Agent" / "[Agent]: Place a Spy"). */
  [/(?:Agent(?: Turn)?|On discard):/y, (m) => document.createTextNode(m[0])],
  [/\bAgents?\b/y, (m) => textIcon("agent", m[0])],
  [/\b[Ss]andworms?\b/y, (m) => textIcon("sandworm", m[0])],
  [/\bMaker Hooks\b/y, () => textIcon("maker_hooks", "Maker Hooks")],
  [/\bShield Wall\b/y, () => textIcon("shield_wall", "Shield Wall")],
  [/\bSignet Ring\b/y, () => textIcon("signet_ring", "Signet Ring")],
  [/\bContracts?\b/y, (m) => textIcon("contract", m[0])],
  [/→/y, () => icon("arrow_right", "→")],
];

/* Expand a label of ours into nodes: `{term}` becomes that term's icon (or
   its word where there is no icon) and `{term:3}` the icon with a count.
   Everything else is copied through as text.

   This is what our own generated labels use instead of iconize(). The
   difference that matters: a card, Leader or space name is never handed to
   it, so "Signet Ring" the card can never be swallowed by the Signet Ring
   icon the way ICON_RULES swallowed it. */
function termNode(name, count) {
  const term = TERMS[name];
  if (!term) return document.createTextNode(`{${name}}`);
  const label = term[TERM_LANGUAGE] || term.en;
  if (!term.icon) {
    const span = document.createElement("span");
    span.textContent = count === undefined ? label : `${count} ${label}`;
    return span;
  }
  if (name === "agent") {
    return count === undefined ? agentPieceIcon(label) : agentAmount(label, count);
  }
  return count === undefined ? icon(term.icon, label) : amount(term.icon, label, count);
}

/* The same expansion as plain text, for places that take a string rather
   than nodes: a title or alt attribute, or a line built by joining. An
   icon becomes its word, which is what a title should read anyway. */
function phraseText(template) {
  return String(template).replace(/\{([a-z_]+)(?::(\d+))?\}/g, (whole, name, count) => {
    const term = TERMS[name];
    if (!term) return whole;
    const label = term[TERM_LANGUAGE] || term.en;
    return count === undefined ? label : `${count} ${label}`;
  });
}

function phrase(template) {
  const fragment = document.createDocumentFragment();
  let index = 0;
  for (const match of String(template).matchAll(/\{([a-z_]+)(?::(\d+))?\}/g)) {
    if (match.index > index) fragment.append(template.slice(index, match.index));
    fragment.appendChild(
      termNode(match[1], match[2] === undefined ? undefined : Number(match[2])),
    );
    index = match.index + match[0].length;
  }
  if (index < template.length) fragment.append(template.slice(index));
  return fragment;
}

/* Printed card wording, iconized. The wrapper marks it as the card's own
   English text (glossary-ko.md keeps it English), which lang.py's Korean
   check skips; its icons' tooltips follow the chosen language. */
function iconize(text) {
  const fragment = document.createElement("span");
  fragment.className = "card-text";
  let plain = "";
  let index = 0;
  const flush = () => {
    if (plain) fragment.append(plain);
    plain = "";
  };
  while (index < text.length) {
    let matched = false;
    for (const [pattern, build] of ICON_RULES) {
      pattern.lastIndex = index;
      const match = pattern.exec(text);
      if (match && match.index === index) {
        flush();
        fragment.appendChild(build(match));
        index += match[0].length;
        matched = true;
        break;
      }
    }
    if (!matched) {
      plain += text[index];
      index += 1;
    }
  }
  flush();
  return fragment;
}

function iconLine(text, className) {
  const line = document.createElement("div");
  line.className = className || "popover-line";
  line.appendChild(iconize(text));
  return line;
}

/* One line of engine-*generated* effect text (a card's Agent/Reveal line, a
   Contract's condition/reward, a space option, ...), as opposed to printed
   card wording (which stays English in both languages and always goes
   through iconize() above). The catalog serves such a field's Korean twin
   beside the English one, suffixed `_ko` (server/catalog.py); ``ko`` is
   that twin, possibly ``undefined`` where a later step's generator has not
   filled it in yet.

   Korean reads `ko` through phrase(), the same `{term}`/`{term:count}`
   expansion our own hand-written labels use (TERMS, static/labels.js) — a
   Korean line names its icons this way instead of English words for
   iconize()'s regex to catch. It is wrapped in its own class, not
   `card-text` (which marks *printed* wording and is what lang.py's/
   log_words.py's Korean-leak checks skip): this text is not printed on any
   card, so it must read as ordinary Korean and stays inside those checks.

   English, or Korean with no twin yet, reads `en` through iconize() exactly
   as before — the fallback that keeps every renderer working before its
   own step fills in a `_ko` field. */
function effectNode(en, ko) {
  if (TERM_LANGUAGE === "ko" && ko) {
    const span = document.createElement("span");
    span.className = "effect-text-ko";
    span.appendChild(phrase(ko));
    return span;
  }
  return iconize(en);
}

function effectLine(en, ko, className) {
  const line = document.createElement("div");
  line.className = className || "popover-line";
  line.appendChild(effectNode(en, ko));
  return line;
}

function costNode(cost) {
  const wrap = document.createElement("span");
  wrap.className = "cost";
  let any = false;
  for (const resource of ["solari", "spice", "water"]) {
    if (cost[resource]) {
      wrap.appendChild(amount(resource, termLabel(resource), cost[resource]));
      any = true;
    }
  }
  if (!any) wrap.textContent = t("render.free");
  return wrap;
}

/* ---------- board spotlight ----------

   The action log's turn cards (renderLog) light what they refer to on the
   table while the pointer rests on them: the spaces and cards named by
   the steps' arguments or events. The stage is rebuilt by every render,
   so the spotlight is re-applied afterwards. */

let spotlightGroup = null;

function setSpotlight(group) {
  spotlightGroup = group;
  applySpotlight();
}

/* Everything a group of steps points at: spaces and cards named by the
   action arguments or by the events (acquired card, placed Agent). */
function logTargets(group) {
  const spaces = [];
  const cards = [];
  const seen = new Set();
  const consider = (value) => {
    if (typeof value !== "string") return;
    /* An event may name a card both by kind (card_id) and by the exact
       copy (instance_id); one image per printed card is enough. */
    const key = state.catalog.spaces[value] ? value : baseId(value);
    if (seen.has(key)) return;
    seen.add(key);
    if (state.catalog.spaces[value]) spaces.push(value);
    else if (lookup(key)) cards.push(value);
  };
  for (const entry of group.entries) {
    if (entry.type !== "action") continue;
    for (const value of Object.values(entry.arguments)) consider(value);
    for (const event of entry.events) {
      if (!event.payload) continue;
      for (const [key, value] of Object.entries(event.payload)) {
        if (key === "card_id" || key === "space_id" || key.endsWith("instance_id")) {
          consider(value);
        }
      }
    }
  }
  return { spaces, cards };
}

function applySpotlight() {
  for (const node of document.querySelectorAll(".spotlight")) {
    node.classList.remove("spotlight");
  }
  if (!spotlightGroup) return;
  const { spaces, cards } = logTargets(spotlightGroup);
  for (const spaceId of spaces) {
    for (const node of document.querySelectorAll(`[data-space="${spaceId}"]`)) {
      node.classList.add("spotlight");
    }
  }
  for (const id of cards) {
    for (const node of document.querySelectorAll(`#game-screen [data-instance="${id}"]`)) {
      if (!node.closest("#action-log")) node.classList.add("spotlight");
    }
  }
}

/* ---------- rendering ---------- */

/* The panes that can scroll on their own; their content is rebuilt on every
   render, which would throw the reader back to the top. Which of them really
   scrolls depends on the viewport — `@media (max-width: 1700px)` moves the
   side column's scrolling from #side-main up to #side — so keepScroll() asks
   each pane at render time instead of trusting the list. Naming only the
   panes that scroll at one width is what silently dropped #side on every
   screen narrower than 1700px. */
const SCROLL_PANES = [
  "seats",
  "side",
  "side-main",
  "side-log",
  "board",
  "market",
  "private-zone",
];

/* Panes with something to restore, as [element, top, left]. A pane sitting at
   the origin needs no entry: putting it back would be a no-op. */
function keepScroll() {
  const kept = [];
  for (const id of SCROLL_PANES) {
    const pane = el(id);
    if (!pane || (!pane.scrollTop && !pane.scrollLeft)) continue;
    kept.push([pane, pane.scrollTop, pane.scrollLeft]);
  }
  return kept;
}

/* `foreign`: somebody else changed the game (the doorbell asked for this
   pass). The player did nothing, so a pinned popover stays open and every
   pane keeps its scroll position. */
/* The header's ruleset badges, in the setup form's order of the options. */
const RULESET_BADGES = [
  ["choam_module", "render.badge_choam"],
  ["promo_cards", "render.badge_promo"],
  ["bloodlines", "render.badge_bloodlines"],
  ["tech_module", "render.badge_tech"],
  ["immortality", "render.badge_immortality"],
  ["leader_draft", "render.badge_draft"],
];

function render(options) {
  const summary = state.summary;
  if (!summary) return;
  sanitizePick();
  const foreign = Boolean(options && options.foreign);
  const kept = foreign ? keepScroll() : [];
  if (!(foreign && popoverPinned)) closePopover();
  renderHeaderStatus();
  el("decision-banner").hidden = Boolean(state.review);
  renderBanner();
  renderStandings();
  renderBoard();
  renderMarket();
  renderSeats();
  renderLog();
  renderPrivate();
  renderDisclosure();
  el("host-panel").hidden = !(isRemote() && isAdmin());
  renderHostBlock(el("host-panel-body"));
  applySpotlight();
  for (const [pane, top, left] of kept) {
    pane.scrollTop = top;
    pane.scrollLeft = left;
  }
}

/* #header-status in three spans (style.css): the round and phase, the
   review label, then the seed and ruleset badges. The first two always
   stay whole; the last, which never changes during a game, takes what room
   is left and ends in an ellipsis when it runs out. The full text goes in
   the title. */
function renderHeaderStatus() {
  const summary = state.summary;
  const shown = state.review && state.review.phase ? state.review : null;
  const round = shown ? shown.round : summary.round_number;
  const phase = shown ? shown.phase : summary.phase;
  const pieces = [
    ["status-core", t("render.round_status", { round, phase: PHASE_LABELS[phase] || phase })],
  ];
  if (state.review) {
    const label = spectatorOnly() ? t("render.spectating_ai") : t("render.replay_review");
    pieces.push(["status-label", " · " + label]);
  }
  /* The seed and the ruleset badges never change during a game. */
  const extras = RULESET_BADGES.filter(([field]) => summary[field]).map(([, key]) => t(key));
  if (summary.game_seed !== null) extras.unshift(t("common.seed", { seed: summary.game_seed }));
  if (extras.length) pieces.push(["status-badges", " · " + extras.join(" · ")]);
  const status = el("header-status");
  status.textContent = "";
  for (const [className, text] of pieces) {
    const span = document.createElement("span");
    span.className = className;
    span.textContent = text;
    status.appendChild(span);
  }
  status.title = status.textContent;
}

/* Post-game full disclosure (OQ-010 ruling 4): once a game has finished,
   the server adds every hidden zone to the view, both live and in review. */
function renderDisclosure() {
  const panel = el("disclosure");
  panel.textContent = "";
  const view = state.view;
  if (!view || !view.disclosure) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const heading = document.createElement("h2");
  const title = t("render.disclosure_title");
  panel.appendChild(heading);
  /* A review opens it folded: it holds every hand and deck order as of the
     reviewed step — the draws the replay is walking towards, the way the
     standings are its result (사용자 결정 2026-09-21). One click opens it. */
  const review = state.review;
  if (!review) {
    heading.textContent = title;
  } else {
    const open = Boolean(review.disclosureOpen);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "strip-toggle";
    button.setAttribute("aria-expanded", open ? "true" : "false");
    button.title = open ? t("common.collapse") : t("common.expand");
    button.append(open ? "▾" : "▸", " ", title);
    button.addEventListener("click", () => {
      if (!state.review) return;
      state.review.disclosureOpen = !open;
      renderDisclosure();
    });
    heading.appendChild(button);
    if (!open) {
      const note = document.createElement("p");
      note.className = "muted";
      note.textContent = t("render.disclosure_closed_note");
      panel.appendChild(note);
      return;
    }
  }
  for (const zones of view.disclosure.players) {
    const seat = section(panel, t("common.seat", { seat: zones.player }));
    const line = (label, ids, empty) => {
      const row = document.createElement("div");
      row.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${label} `;
      row.appendChild(strong);
      if (!ids.length) row.append(empty);
      for (const id of ids) row.appendChild(chip(id));
      seat.appendChild(row);
    };
    line(t("render.hand_line", { count: zones.hand.length }), zones.hand, t("common.empty"));
    line(t("render.deck_order_line", { count: zones.deck.length }), zones.deck, t("common.empty"));
    line(
      t("render.intrigue_line", { count: zones.intrigue_cards.length }),
      zones.intrigue_cards,
      t("common.none"),
    );
  }
  const decks = section(panel, t("render.shared_deck_order_title"));
  const deckLine = (label, ids) => {
    const row = document.createElement("div");
    row.className = "cardline";
    const strong = document.createElement("strong");
    strong.textContent = `${label} (${ids.length}) `;
    row.appendChild(strong);
    for (const id of ids) row.appendChild(chip(id));
    decks.appendChild(row);
  };
  deckLine(t("render.deck_imperium"), view.disclosure.imperium_deck);
  deckLine(t("render.deck_intrigue"), view.disclosure.intrigue_deck);
  deckLine(t("render.deck_conflict"), view.disclosure.conflict_deck);
  if (view.disclosure.contract_bank.length) {
    deckLine(t("render.contract_bank"), view.disclosure.contract_bank);
  }
}

/* Actions whose whole meaning is "I am done": applying one IS the seat's
   own turn-end press, so it renders as the banner's turn-end row instead
   of an item in the action list. Mirrors EXPLICIT_TURN_ENDS in
   server/turn_end.py — keep the two lists in step. */
const EXPLICIT_TURN_END_IDS = new Set([
  "finish_agent_turn",
  "finish_reveal",
  "pass_combat_intrigue",
  "pass_endgame_intrigue",
]);

/* The seat's own explicit turn-end action among its legal actions, if the
   pending decision offers one. There is at most one: the four ids belong
   to four different decision kinds. */
function turnEndAction(actions) {
  return actions.find((action) => EXPLICIT_TURN_END_IDS.has(action.action_id)) || null;
}

/* The turn-end row's label for the seat's own explicit action: plain, or
   with the prefix that marks a Reveal that still offers buyable cards (the
   same isAcquire test renderRevealPanel uses for its own `buys`, not
   whether anything was already bought) or an Intrigue pass. */
function turnEndButtonLabel(action, actions) {
  if (action.action_id === "finish_reveal" && actions.some(isAcquire)) {
    return t("render.turn_end_button_with_buys");
  }
  if (action.action_id === "pass_combat_intrigue" || action.action_id === "pass_endgame_intrigue") {
    return t("render.turn_end_button_pass");
  }
  return t("render.turn_end_button");
}

/* The one turn-end control, always the same row in the same place: a hold
   waiting for confirmTurn(), or the seat's own explicit turn-end action
   applied directly (onClick). Never marked irreversible — it is built by
   hand, not through actionItem(), so no badge is possible. */
function appendTurnEndRow(container, label, onClick) {
  const row = document.createElement("div");
  row.className = "confirm-row turn-end-row";
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = state.busy;
  button.addEventListener("click", onClick);
  row.appendChild(button);
  container.appendChild(row);
}

/* ---------- combat result line (banner) ----------

   ITEM 5: nothing on screen said who won a Conflict or what a seat got —
   the reward is a public log event (combat_reward_gained, conflict_won),
   just never surfaced. One muted line above the prompt reports the most
   recently resolved Conflict from the live log, from the moment its
   reward events appear (so the winner reads it while still choosing an
   optional reward) until the viewing seat's own next turn-taking step. */

/* The action ids that start the viewing seat's own next turn, at which
   point an older combat result stops being news. */
const OWN_TURN_ACTION_IDS = new Set(["agent_turn", "reveal_turn", "play_turn_start_card"]);

/* The reward group for the most recently resolved Conflict the given seat
   has seen, or null when none has resolved yet, it already resolved with
   no participants (rank_combat's zero-strength rule leaves no reward
   events to report), or the seat has since taken its own next turn. Reads
   only the live log (undone steps dropped, like board.js's spyArrivals). */
function latestCombatResolution(seat) {
  const entries = (state.log && state.log.entries) || [];
  let conflictId = null;
  let bundle = null;
  let sawRewards = false;
  for (const entry of entries) {
    if (entry.undone) continue;
    for (const event of entry.events || []) {
      if (event.kind === "conflict_revealed") {
        conflictId = event.payload.conflict_id;
        sawRewards = false;
      } else if (event.kind === "combat_reward_gained") {
        if (!sawRewards) {
          bundle = { conflictId, rewards: [] };
          sawRewards = true;
        }
        bundle.rewards.push(event.payload);
      } else if (event.kind === "combat_cleaned_up" && !sawRewards) {
        bundle = null;
      }
    }
    if (
      bundle &&
      entry.type === "action" &&
      entry.actor === seat &&
      OWN_TURN_ACTION_IDS.has(entry.action_id)
    ) {
      bundle = null;
    }
  }
  return bundle;
}

const COMBAT_RESULT_RANK_KEYS = {
  1: "render.combat_result_rank_1",
  2: "render.combat_result_rank_2",
  3: "render.combat_result_rank_3",
};

/* "1위: 좌석 0 (사람) · 2위: 좌석 1 (사람), 좌석 2 (사람)" — ties share a rank
   and are read from left in turn order (the ranking's own order, combat.py's
   _rewards). Plain text: ranks and names are never a rule term. */
function combatResultRanksText(bundle) {
  const byRank = new Map();
  for (const reward of bundle.rewards) {
    if (!byRank.has(reward.rank)) byRank.set(reward.rank, []);
    byRank.get(reward.rank).push(reward.player);
  }
  return [...byRank.keys()]
    .sort((a, b) => a - b)
    .map(
      (rank) => `${t(COMBAT_RESULT_RANK_KEYS[rank])}: ${byRank.get(rank).map(playerLabel).join(", ")}`,
    )
    .join(" · ");
}

/* What one reward payload (combat.py's _combat_reward_event) grants, as
   term icons in printed order. A reward already carries the sandworm
   multiplier, so the counts here are the amounts the seat actually got. */
function combatRewardNodes(reward) {
  const nodes = [];
  const add = (term, count) => nodes.push(termNode(term, count));
  if (reward.victory_points) add("victory_point", reward.victory_points);
  if (reward.solari) add("solari", reward.solari);
  if (reward.spice) add("spice", reward.spice);
  if (reward.water) add("water", reward.water);
  if (reward.troops) add("troop", reward.troops);
  if (reward.intrigue) add("intrigue", reward.intrigue);
  if (reward.contracts) add("contract", reward.contracts);
  if (reward.faction_influence && reward.faction) {
    nodes.push(termNode(`influence_${reward.faction}`, reward.faction_influence));
  }
  if (reward.choose_influence) add("influence_any", reward.choose_influence);
  if (reward.control_space_id) nodes.push(termNode("control"));
  return nodes;
}

/* The banner's one-line Conflict summary for `seat`, or null to show
   nothing (no Conflict has resolved yet, review mode, or the line's
   window has closed). */
function combatResultLine(seat) {
  /* A finished game has its own headline; review shows the log instead. */
  if (state.review || state.summary.finished) return null;
  const bundle = latestCombatResolution(seat);
  if (!bundle) return null;
  const own = bundle.rewards.find((reward) => reward.player === seat);
  const vars = { name: nameOf(bundle.conflictId), ranks: combatResultRanksText(bundle) };
  let key = "render.combat_result_line";
  if (!own) {
    vars.reward = t("render.combat_result_unranked");
  } else {
    const nodes = combatRewardNodes(own);
    if (nodes.length) {
      vars.reward = document.createDocumentFragment();
      nodes.forEach((node, index) => {
        if (index) vars.reward.append(" ");
        vars.reward.appendChild(node);
      });
    } else {
      /* A reward the event does not itemize (a Spy, a trash, two distinct
         Influences) is the choice the seat is shown next. */
      key = "render.combat_result_line_ranks";
    }
  }
  const line = document.createElement("div");
  line.className = "combat-result";
  line.appendChild(tNode(key, vars));
  return line;
}

function renderBanner() {
  const summary = state.summary;
  const info = el("decision-info");
  info.textContent = "";
  const resultLine = combatResultLine(state.viewSeat);
  if (resultLine) info.appendChild(resultLine);
  const actionsBox = el("actions");
  actionsBox.textContent = "";

  const prompt = document.createElement("div");
  prompt.className = "prompt";
  const meta = document.createElement("div");
  meta.className = "meta";

  if (summary.finished) {
    const [first, second] = [...(summary.standings || [])].sort(
      (a, b) => a.rank - b.rank,
    );
    if (!first) {
      prompt.textContent = t("render.game_over_no_standings");
      info.append(prompt);
    } else {
      prompt.textContent = t("render.game_over_winner", { winner: playerLabel(first.player) });
      /* Names are other people's input: text nodes, never phrase() input. */
      if (second) {
        const margin = gameOverMargin(first, second);
        meta.append(
          tNode(margin.key, margin.vars),
          t("render.second_place", { name: playerLabel(second.player) }),
        );
      } else {
        meta.append(phrase(`{victory_point:${first.victory_points}}`));
      }
      info.append(prompt, meta);
    }
  } else {
    const decision = summary.decision;
    if (!decision) {
      prompt.textContent = t("render.in_progress");
      info.append(prompt);
    } else if (summary.confirmation === state.viewSeat) {
      /* The viewing seat's turn has ended: nothing advances until it
         presses the turn-end row (confirmTurn), whether or not the steps
         that ended it can still be taken back. */
      prompt.textContent = t("render.turn_end_prompt");
      meta.textContent = t("render.next_label", { name: playerLabel(decision.owner) });
      info.append(prompt, meta);
      appendTurnEndRow(info, t("render.turn_end_button"), () => confirmTurn());
    } else if (typeof summary.confirmation === "number") {
      /* Another seat's turn has ended; nobody moves until that seat
         presses its own turn-end row. */
      prompt.textContent =
        t("render.waiting_turn_end", { name: playerLabel(summary.confirmation) }) +
        waitingHint(summary.confirmation);
      meta.textContent = t("render.next_label", { name: playerLabel(decision.owner) });
      info.append(prompt, meta);
    } else if (decision.owner !== state.viewSeat) {
      prompt.textContent =
        t("render.waiting_decision", { name: playerLabel(decision.owner) }) +
        waitingHint(decision.owner);
      meta.textContent = promptText(decision.prompt);
      info.append(prompt, meta);
    } else {
      prompt.textContent = promptText(decision.prompt);
      meta.textContent = t("render.seat_you", { seat: decision.owner });
      info.append(prompt, meta);

      /* The seat's own explicit turn-end action (EXPLICIT_TURN_END_IDS),
         when the pending decision offers one, IS this turn's end: it
         renders as the same banner row and is pulled out of every action
         list below (renderActionPanel). */
      const turnEnd = state.actions ? turnEndAction(state.actions.actions) : null;
      if (turnEnd) {
        appendTurnEndRow(
          info,
          turnEndButtonLabel(turnEnd, state.actions.actions),
          () => applyAction(turnEnd.index),
        );
      }
      if (state.actions) renderActionPanel(actionsBox, turnEnd);
    }
  }

  /* A human seat may still have takeable-back steps after the game ends
     (its last live step), so the undo row renders in both branches above. */
  appendUndoRow(info);
}

/* The tiebreaks after equal Victory Points, in order: spice, Solari, water,
   troops in garrison [Main p. 15], a garrisoned Sardaukar Commander counting
   as a troop (OQ-047). The server ranks on the same keys (rules/endgame.py). */
const VP_TIEBREAKS = [
  ["{spice}", (entry) => entry.spice],
  ["{solari}", (entry) => entry.solari],
  ["{water}", (entry) => entry.water],
  ["{garrison} {troop}", (entry) => entry.troops_garrison + (entry.commanders_garrison || 0)],
];

/* What put the winner ahead of second place, as a t()/tNode() key and vars:
   the victory-point count is a pre-built term node (a hole value), so it
   never sits inside a stored template's {term:count} slot. */
function gameOverMargin(first, second) {
  const vp = first.victory_points;
  if (vp !== second.victory_points) {
    return {
      key: "render.margin_vp",
      vars: { vp: termNode("victory_point", vp), diff: vp - second.victory_points },
    };
  }
  for (const [label, value] of VP_TIEBREAKS) {
    if (value(first) !== value(second)) {
      return {
        key: "render.margin_tiebreak",
        vars: {
          vp: termNode("victory_point", vp),
          tiebreak: phrase(label),
          first: value(first),
          second: value(second),
        },
      };
    }
  }
  /* Still tied: whoever took a Reveal turn most recently wins [FAQ p. 2]. */
  return { key: "render.margin_all_tied", vars: { vp: termNode("victory_point", vp) } };
}

/* Why a wait may be a long one: nobody sits there yet, or they dropped off. */
function waitingHint(seat) {
  const info = playerInfo(seat);
  if (!isRemote() || info.kind !== "human") return "";
  if (!info.claimed) return t("render.waiting_hint_empty");
  return info.online ? "" : t("render.waiting_hint_offline");
}

/* Undo controls for the viewing seat (M11 slice 6): a single-step button
   and, when more than one step is available, a take-back-everything button. */
function appendUndoRow(container) {
  if (state.review) return;
  const entry = (state.summary.undo || []).find(
    (item) => item.seat === state.viewSeat
  );
  if (!entry || entry.steps <= 0) return;
  const row = document.createElement("div");
  row.className = "undo-row";

  const one = document.createElement("button");
  one.type = "button";
  one.textContent = t("render.undo_one_step");
  one.disabled = state.busy;
  one.addEventListener("click", () => submitUndo(state.viewSeat, 1));
  row.appendChild(one);

  if (entry.steps > 1) {
    const all = document.createElement("button");
    all.type = "button";
    all.textContent = t("render.undo_all_steps", { steps: entry.steps });
    all.disabled = state.busy;
    all.addEventListener("click", () => submitUndo(state.viewSeat, entry.steps));
    row.appendChild(all);
  }
  container.appendChild(row);
}

/* Effect preview for one legal action: resolve its referenced space/cards
   against the catalog. space_id resolves against the spaces section
   explicitly (a contract may share its id with a space). */
function actionPreviewEntries(action) {
  const entries = [];
  const args = action.arguments;
  if (typeof args.space_id === "string" && state.catalog.spaces[args.space_id]) {
    entries.push(state.catalog.spaces[args.space_id]);
  }
  for (const [key, value] of Object.entries(args)) {
    if (key === "space_id" || typeof value !== "string") continue;
    const entry = lookup(baseId(value));
    if (entry && !entries.includes(entry)) entries.push(entry);
  }
  return entries;
}

function spaceOptionLine(option) {
  const line = document.createElement("div");
  line.className = "popover-line option-line";
  line.appendChild(costNode(option.cost));
  line.appendChild(icon("arrow_right", "→"));
  line.appendChild(effectNode(option.effect, option.effect_ko));
  return line;
}

function actionPreviewNodes(action, entry) {
  if (entry.options) {
    const options = spaceOptionsFor(entry);
    const index =
      typeof action.arguments.cost_option === "number"
        ? action.arguments.cost_option
        : 0;
    const option = options[index] || options[0];
    const nodes = [];
    if (entry.requirement) nodes.push(requirementNode(entry.requirement));
    nodes.push(spaceOptionLine(option));
    const notesKo = entry.notes_ko || [];
    entry.notes.forEach((text, i) => {
      nodes.push(effectLine(text, notesKo[i], "popover-line muted"));
    });
    return nodes;
  }
  const optionIndex = action.arguments.option;
  if (
    action.action_id === "play_intrigue" &&
    entry.text &&
    typeof optionIndex === "number" &&
    entry.text[optionIndex]
  ) {
    const textKo = entry.text_ko || [];
    return [effectLine(entry.text[optionIndex], textKo[optionIndex])];
  }
  return popoverNodes(entry);
}

/* Argument values that name a card instance or space, for hotspot and hand
   click matching (data-refs) — the same strings describeAction resolves. */
function actionRefs(action) {
  return Object.values(action.arguments).filter((value) => typeof value === "string");
}

/* What the seat's running combat strength becomes with a step: the
   server's dry run of that step (`strength_after`), so the engine's own
   figure. */
function strengthPreview(after) {
  const own = state.view && state.view.players[state.viewSeat];
  const now = own ? own.combat_strength || 0 : 0;
  const badge = document.createElement("span");
  badge.className = "strength-preview";
  badge.title = t("render.strength_preview_title");
  badge.append(icon("sword", phraseText("{strength}")), ` ${now} → ${after}`);
  return badge;
}

/* What revealing the hand right now would give: the server's dry run of
   `reveal_turn` (`reveal_preview`: the Persuasion the Reveal opens with and
   the strength once the revealed swords count), so the engine's own sum. */
function revealPreview(preview) {
  const badge = document.createElement("span");
  badge.className = "reveal-preview";
  badge.title = t("render.reveal_preview_title");
  badge.append(icon("persuasion", phraseText("{persuasion}")), ` ${preview.persuasion}`);
  const own = state.view && state.view.players[state.viewSeat];
  const now = own ? own.combat_strength || 0 : 0;
  if (typeof preview.strength === "number" && preview.strength !== now) {
    badge.append(" · ", icon("sword", phraseText("{strength}")), ` ${now} → ${preview.strength}`);
  }
  return badge;
}

/* The `reveal_turn` step among the seat's legal actions, if it is there and
   the server previewed it. */
function revealTurnPreview() {
  if (state.review || !state.actions) return null;
  const reveal = state.actions.actions.find((action) => action.action_id === "reveal_turn");
  return reveal && reveal.reveal_preview ? reveal.reveal_preview : null;
}

/* ---------- count steppers ----------

   "Deploy 1", "Deploy 2", "Deploy 3" are one decision with a number in it.
   Actions of one id that differ only in a `count` argument are shown as a
   single row with a stepper over the legal counts; the panel and the
   Conflict area share the chosen number. */
function countFamilies(actions) {
  const byId = new Map();
  for (const action of actions) {
    if (!byId.has(action.action_id)) byId.set(action.action_id, []);
    byId.get(action.action_id).push(action);
  }
  const families = new Map();
  for (const [id, group] of byId) {
    const onlyCount = group.every((action) => {
      const keys = Object.keys(action.arguments);
      return keys.length === 1 && keys[0] === "count" && Number.isInteger(action.arguments.count);
    });
    /* Units go in and out of the Conflict through the same control even
       when a single count is left to choose. */
    if (!onlyCount || (group.length < 2 && !FORCE_STEPPER_ACTIONS.has(id))) continue;
    families.set(id, [...group].sort((a, b) => a.arguments.count - b.arguments.count));
  }
  return families;
}

/* The family's action for the chosen count. Sending units defaults to all
   of them, taking them back to one. */
function chosenOf(id, family) {
  const found = family.find((action) => action.arguments.count === state.counts[id]);
  if (found) return found;
  return id.startsWith("deploy") ? family[family.length - 1] : family[0];
}

function countRow(id, family, compact) {
  const chosen = chosenOf(id, family);
  const position = family.indexOf(chosen);
  const row = document.createElement("div");
  row.className = "action-item count-row" + (compact ? " compact" : "");
  row.dataset.action = id;
  row.dataset.index = String(chosen.index);
  const label = document.createElement("span");
  label.className = "count-label";
  label.appendChild(phrase(ACTION_LABELS[id] || prettify(id)));
  const stepper = document.createElement("span");
  stepper.className = "stepper";
  const step = (text, target, title) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    button.title = title;
    button.disabled = state.busy || !family[target];
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      state.counts[id] = family[target].arguments.count;
      render();
    });
    return button;
  };
  const value = document.createElement("strong");
  value.className = "stepper-value";
  value.textContent = String(chosen.arguments.count);
  stepper.append(
    step("−", position - 1, t("render.count_step_down")),
    value,
    step("+", position + 1, t("render.count_step_up")),
  );
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "count-confirm";
  confirm.disabled = state.busy;
  confirm.append(
    compact
      ? t("render.confirm_short")
      : t("render.confirm_count_label", { count: chosen.arguments.count, label: label.textContent }),
  );
  if (typeof chosen.strength_after === "number") {
    confirm.appendChild(strengthPreview(chosen.strength_after));
  }
  confirm.addEventListener("click", (event) => {
    event.stopPropagation();
    applyAction(chosen.index);
  });
  row.append(label, stepper, confirm);
  return row;
}

/* The viewing seat's own pile holding a card instance ("hand", "discard_pile"
   or "in_play"), or null when the card sits in none of them (a board or
   reserve card, or another seat's). Zones come from the viewing seat's own
   view: its hand in the private block, its discard pile and in-play list in
   its public player block. */
function ownCardZone(cardId) {
  const hand = (state.view && state.view.private && state.view.private.hand) || [];
  if (hand.includes(cardId)) return "hand";
  const own = state.view && state.view.players && state.view.players[state.viewSeat];
  if (own && own.discard_pile.includes(cardId)) return "discard_pile";
  if (own && own.in_play.includes(cardId)) return "in_play";
  return null;
}

/* Rows of this list that need a zone suffix: two or more rows of the same
   action_id naming the same card (same baseId) but sitting in different
   piles of the viewing seat. Trashing the hand copy costs that card's play
   this round, and nothing else on the row says which pile a row means
   (item 8c: the Feyd track, Desert Tactics and Combat reward trashes all
   offer hand, then discard pile, then in-play candidates). A duplicate
   that shares one pile with its sibling rows is interchangeable and keeps
   its plain label. */
function zoneSuffixes(actions) {
  const groups = new Map();
  for (const action of actions) {
    const cardId = action.arguments.card_id;
    if (typeof cardId !== "string") continue;
    const zone = ownCardZone(cardId);
    if (!zone) continue;
    const key = `${action.action_id}\u0000${baseId(cardId)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ action, zone });
  }
  const suffixes = new Map();
  for (const entries of groups.values()) {
    if (new Set(entries.map((entry) => entry.zone)).size < 2) continue;
    for (const { action, zone } of entries) suffixes.set(action, zone);
  }
  return suffixes;
}

/* " (hand)" / " (discard pile)" / " (in play)": the TERMS glossary word for
   the zone a row's card sits in ([Main p. 20]), through phrase() so it
   reads in the chosen language like the rest of the row. */
function zoneSuffixNode(zone) {
  return phrase(` ({${zone}})`);
}

/* A list of legal actions with its count families folded into rows. */
function appendActionItems(box, actions) {
  const families = countFamilies(actions);
  const suffixes = zoneSuffixes(actions);
  const done = new Set();
  for (const action of actions) {
    const family = families.get(action.action_id);
    if (!family) box.appendChild(actionItem(action, undefined, suffixes.get(action)));
    else if (!done.has(action.action_id)) {
      done.add(action.action_id);
      box.appendChild(countRow(action.action_id, family, false));
    }
  }
}

/* ---------- Reveal purchases ----------

   A Reveal is a small shop: the Persuasion still unspent (the server's
   summary carries it), what has been bought so far (the session log), the
   cards that can still be bought, the Reveal effects left to resolve, and
   one clear way out. */
function isAcquire(action) {
  return action.action_id.startsWith("acquire");
}

function boughtThisReveal() {
  const entries = (state.log && state.log.entries) || [];
  const seat = state.viewSeat;
  let start = -1;
  entries.forEach((entry, position) => {
    if (entry.action_id === "reveal_turn" && entry.actor === seat && !entry.undone) start = position;
  });
  if (start < 0) return [];
  const bought = [];
  for (const entry of entries.slice(start + 1)) {
    if (entry.actor !== seat || entry.undone) continue;
    for (const event of entry.events || []) {
      if (event.kind === "card_acquired" && event.payload.player === seat) {
        bought.push(event.payload.card_id);
      }
    }
  }
  return bought;
}

function acquireCostNode(action) {
  const ref = actionRefs(action)[0];
  const entry = ref ? lookup(baseId(ref)) : null;
  if (!entry) return null;
  const cost = document.createElement("span");
  cost.className = "acquire-cost";
  if (action.action_id.includes("tleilaxu") && typeof entry.specimens === "number") {
    cost.append(`${phraseText("{specimen}")} ${entry.specimens}`);
  } else if (typeof entry.cost === "number") {
    cost.append(
      amount(
        action.action_id.includes("solari") ? "solari" : "persuasion",
        t("render.acquire_cost_label"),
        entry.cost,
      ),
    );
  } else {
    return null;
  }
  return cost;
}

function renderRevealPanel(box, actions) {
  const decision = state.summary.decision;
  const status = document.createElement("div");
  status.className = "reveal-status";
  if (typeof decision.persuasion === "number") {
    const left = document.createElement("span");
    left.className = "reveal-persuasion";
    left.dataset.persuasion = String(decision.persuasion);
    left.append(
      t("render.persuasion_remaining"),
      amount("persuasion", phraseText("{persuasion}"), decision.persuasion),
    );
    status.appendChild(left);
  }
  const bought = boughtThisReveal();
  if (bought.length) {
    const list = document.createElement("span");
    list.className = "reveal-bought";
    list.append(t("render.bought_cards_label"));
    bought.forEach((cardId) => list.appendChild(chip(cardId)));
    status.appendChild(list);
  }
  if (status.childNodes.length) box.appendChild(status);

  const heading = (text) => {
    const node = document.createElement("div");
    node.className = "pick-others muted";
    node.textContent = text;
    box.appendChild(node);
  };
  /* finish_reveal itself never reaches `actions`: it is the seat's
     explicit turn-end action, already pulled into the banner's turn-end
     row by renderBanner. */
  const buys = actions.filter(isAcquire);
  const effects = actions.filter((action) => !isAcquire(action));
  if (effects.length) {
    heading(t("render.reveal_effects_heading"));
    appendActionItems(box, effects);
  }
  if (buys.length) {
    heading(t("render.buyable_cards_heading"));
    for (const action of buys) {
      const item = actionItem(action);
      const cost = acquireCostNode(action);
      if (cost) item.querySelector("button").appendChild(cost);
      box.appendChild(item);
    }
  }
}

/* The arguments of an action that name something on the table: a board
   space or an observation post, or a card instance (ids with a colon). */
function tableRefs(action) {
  return actionRefs(action).filter(
    (ref) => ref.includes(":") || state.catalog.spaces[ref] || state.catalog.posts[ref]
  );
}

function actionItem(action, onApply, zone) {
  const wrap = document.createElement("div");
  wrap.className = "action-item";
  wrap.dataset.index = String(action.index);
  wrap.dataset.refs = JSON.stringify(actionRefs(action));
  const button = document.createElement("button");
  button.appendChild(describeAction(action));
  if (zone) button.appendChild(zoneSuffixNode(zone));
  button.disabled = state.busy;
  button.addEventListener("click", () =>
    onApply ? onApply(action) : applyAction(action.index)
  );
  if (action.undoable === false) {
    /* The server dry-ran the step: it reveals hidden information or hands
       the game to a chance outcome, so it cannot be taken back afterwards. */
    wrap.classList.add("irreversible");
    const badge = document.createElement("span");
    badge.className = "irreversible-badge";
    badge.textContent = t("render.irreversible_badge");
    badge.title = t("render.irreversible_title");
    button.appendChild(badge);
  }
  if (typeof action.strength_after === "number") {
    button.appendChild(strengthPreview(action.strength_after));
  }
  if (action.reveal_preview) button.appendChild(revealPreview(action.reveal_preview));
  if (action.warning) {
    /* The server dry-ran the step: the troop supply cannot cover what the
       effect asks for (OQ-030, OQ-049), so the action does less than printed. */
    wrap.classList.add("shortfall");
    const badge = document.createElement("span");
    badge.className = "shortfall-badge";
    /* The server's `warning` is Korean; `shortfall` is the same as data. */
    badge.textContent = action.shortfall
      ? action.shortfall
          .map((short) =>
            t(
              short.kind === "troops"
                ? "render.shortfall_troops"
                : "render.shortfall_specimens",
              { requested: short.requested, made: short.made },
            ),
          )
          .join(" · ")
      : action.warning;
    badge.title = t("render.shortfall_title");
    button.appendChild(badge);
  }
  wrap.appendChild(button);

  const entries = actionPreviewEntries(action);
  if (entries.length) {
    const info = document.createElement("button");
    info.type = "button";
    info.className = "action-info";
    info.textContent = "ⓘ";
    info.title = t("render.effect_preview_title");
    const detail = document.createElement("div");
    detail.className = "action-detail";
    detail.hidden = true;
    for (const entry of entries) {
      const head = document.createElement("div");
      head.className = "popover-title";
      head.textContent = entry.name;
      detail.appendChild(head);
      for (const node of actionPreviewNodes(action, entry)) detail.appendChild(node);
      if (entry.image && !entry.options) {
        const image = document.createElement("img");
        image.className = "detail-card";
        image.loading = "lazy";
        image.src = entry.image;
        image.alt = entry.name;
        detail.appendChild(image);
      }
    }
    info.addEventListener("click", (event) => {
      event.stopPropagation();
      detail.hidden = !detail.hidden;
    });
    wrap.append(info, detail);
  }
  return wrap;
}

/* Focus the action list on one card instance or space (table click with
   several options): the matching actions move to the top under a header
   that names the object, the rest stay below dimmed. The list is rebuilt
   by every render, so the focus lasts until the next state change or the
   header's "전체 보기". */
function focusActions(ref, label) {
  clearActionFocus();
  const box = el("actions");
  const items = [...box.querySelectorAll(".action-item")];
  const matches = items.filter((item) =>
    JSON.parse(item.dataset.refs || "[]").includes(ref)
  );
  if (!matches.length) return;
  for (const item of items) {
    const hit = matches.includes(item);
    item.classList.toggle("action-match", hit);
    item.classList.toggle("action-dim", !hit);
  }
  const header = document.createElement("div");
  header.className = "action-focus";
  const text = document.createElement("span");
  text.append(t("render.action_focus_label", { label: label || ref, count: matches.length }));
  const clear = document.createElement("button");
  clear.type = "button";
  clear.textContent = t("render.view_all");
  clear.addEventListener("click", clearActionFocus);
  header.append(text, clear);
  box.prepend(header);
  let anchor = header;
  for (const item of matches) {
    anchor.after(item);
    anchor = item;
  }
  header.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function clearActionFocus() {
  const box = el("actions");
  const header = box.querySelector(".action-focus");
  if (header) header.remove();
  const items = [...box.querySelectorAll(".action-item")];
  for (const item of items) item.classList.remove("action-match", "action-dim");
  items
    .sort((a, b) => Number(a.dataset.index) - Number(b.dataset.index))
    .forEach((item) => box.appendChild(item));
}
