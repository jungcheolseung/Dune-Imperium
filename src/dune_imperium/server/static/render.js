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

function icon(name, label) {
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
  span.textContent = label;
  return span;
}

function amount(name, label, count) {
  const wrap = document.createElement("span");
  wrap.className = "amount";
  wrap.title = `${count} ${label}`;
  wrap.append(String(count), icon(name, label));
  return wrap;
}

const FACTION_ICON_KEY = {
  Emperor: "emperor",
  "Spacing Guild": "spacing_guild",
  "Bene Gesserit": "bene_gesserit",
  Fremen: "fremen",
};

/* Glossary that turns the catalog's English effect text into the printed
   iconography: each rule is tried at the current position (sticky), the
   first match wins, and unmatched text is copied through. Only display —
   the text itself stays the server's. */
const ICON_RULES = [
  [/(?:Gain |Pay )?(\d+) (solari|spice|water)\b/y, (m) => amount(m[2], m[2], m[1])],
  [/\b(solari|spice|water)\b/y, (m) => icon(m[1], m[1])],
  [/Draw (\d+) Intrigue cards?/y, (m) => amount("intrigue", "Intrigue card", m[1])],
  [/Draw (\d+) cards?/y, (m) => amount("draw", "Draw", m[1])],
  [/Intrigue cards?/y, () => icon("intrigue", "Intrigue card")],
  [/(?:Recruit |Gain )?(\d+) troops?\b/y, (m) => amount("troop", "troop", m[1])],
  [/\btroops?\b/y, () => icon("troop", "troop")],
  [
    /(?:Gain )?(\d+) (Emperor|Spacing Guild|Bene Gesserit|Fremen) Influence/y,
    (m) => amount(`influence_${FACTION_ICON_KEY[m[2]]}`, `${m[2]} Influence`, m[1]),
  ],
  [
    /(Emperor|Spacing Guild|Bene Gesserit|Fremen) Influence/y,
    (m) => icon(`influence_${FACTION_ICON_KEY[m[1]]}`, `${m[1]} Influence`),
  ],
  [/Lose (\d+) Influence/y, (m) => amount("influence_lose", "Lose Influence", m[1])],
  [/(?:Gain )?(\d+) Influence/y, (m) => amount("influence_any", "Influence", m[1])],
  [/Influence with the visited Faction/y, () => icon("influence_any", "visited Faction Influence")],
  [/(\d+) Persuasion/y, (m) => amount("persuasion", "Persuasion", m[1])],
  [/\bPersuasion\b/y, () => icon("persuasion", "Persuasion")],
  [/(\d+) (?:swords?|strength)\b/y, (m) => amount("sword", "sword", m[1])],
  [/\bswords?\b/y, () => icon("sword", "sword")],
  [/(?:Gain )?(\d+) (?:Victory Points?|VP)\b/y, (m) => amount("victory_point", "Victory Point", m[1])],
  [/\b(?:Victory Points?|VP)\b/y, () => icon("victory_point", "Victory Point")],
  [/\b[Tt]rash an Intrigue card\b/y, () => icon("trash_intrigue", "Trash an Intrigue card")],
  [/\b[Tt]rash\b/y, () => icon("trash", "Trash")],
  [/\b[Dd]iscard\b/y, () => icon("discard", "Discard")],
  [/\b(?:a |an )?Sp(?:y|ies)\b/y, (m) => icon("spy", m[0].trim())],
  [/\bAgents?\b/y, (m) => agentPieceIcon(m[0])],
  [/\b[Ss]andworms?\b/y, (m) => icon("sandworm", m[0])],
  [/\bMaker Hooks\b/y, () => icon("maker_hooks", "Maker Hooks")],
  [/\bShield Wall\b/y, () => icon("shield_wall", "Shield Wall")],
  [/\bSignet Ring\b/y, () => icon("signet_ring", "Signet Ring")],
  [/\bContracts?\b/y, (m) => icon("contract", m[0])],
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

function iconize(text) {
  const fragment = document.createDocumentFragment();
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

function costNode(cost) {
  const wrap = document.createElement("span");
  wrap.className = "cost";
  let any = false;
  for (const resource of ["solari", "spice", "water"]) {
    if (cost[resource]) {
      wrap.appendChild(amount(resource, resource, cost[resource]));
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
  const shown = state.review && state.review.phase ? state.review : null;
  const round = shown ? shown.round : summary.round_number;
  const phase = shown ? shown.phase : summary.phase;
  el("header-status").textContent =
    t("render.round_status", { round, phase: PHASE_LABELS[phase] || phase }) +
    (summary.game_seed === null ? "" : " · " + t("common.seed", { seed: summary.game_seed })) +
    RULESET_BADGES.filter(([field]) => summary[field])
      .map(([, key]) => " · " + t(key))
      .join("") +
    (state.review
      ? " · " + (spectatorOnly() ? t("render.spectating_ai") : t("render.replay_review"))
      : "");
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

function renderBanner() {
  const summary = state.summary;
  const info = el("decision-info");
  info.textContent = "";
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
      /* The viewing seat's turn has ended but its steps can still be taken
         back: nothing advances until it confirms the hand-over. */
      prompt.textContent = t("render.confirm_turn_prompt");
      meta.textContent = t("render.confirm_turn_meta", { next: playerLabel(decision.owner) });
      info.append(prompt, meta);
      const row = document.createElement("div");
      row.className = "confirm-row";
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.textContent = t("render.confirm_turn_button");
      confirm.disabled = state.busy;
      confirm.addEventListener("click", () => confirmTurn());
      row.appendChild(confirm);
      info.appendChild(row);
    } else if (typeof summary.confirmation === "number") {
      /* Another seat's turn has ended but can still be taken back; nobody
         moves until that seat hands it over. */
      prompt.textContent =
        t("render.waiting_confirm", { name: playerLabel(summary.confirmation) }) +
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

      if (state.actions) renderActionPanel(actionsBox);
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
  line.appendChild(iconize(option.effect));
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
    for (const text of entry.notes) nodes.push(iconLine(text, "popover-line muted"));
    return nodes;
  }
  const optionIndex = action.arguments.option;
  if (
    action.action_id === "play_intrigue" &&
    entry.text &&
    typeof optionIndex === "number" &&
    entry.text[optionIndex]
  ) {
    return [iconLine(entry.text[optionIndex])];
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

/* A list of legal actions with its count families folded into rows. */
function appendActionItems(box, actions) {
  const families = countFamilies(actions);
  const done = new Set();
  for (const action of actions) {
    const family = families.get(action.action_id);
    if (!family) box.appendChild(actionItem(action));
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
  const buys = actions.filter(isAcquire);
  const finish = actions.filter((action) => action.action_id === "finish_reveal");
  const effects = actions.filter((action) => !isAcquire(action) && action.action_id !== "finish_reveal");
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
  for (const action of finish) {
    const item = actionItem(action);
    item.classList.add("finish-row");
    const button = item.querySelector("button");
    button.textContent = buys.length
      ? t("render.finish_reveal_with_buys")
      : t("render.finish_reveal");
    box.appendChild(item);
  }
}

/* The arguments of an action that name something on the table: a board
   space or an observation post, or a card instance (ids with a colon). */
function tableRefs(action) {
  return actionRefs(action).filter(
    (ref) => ref.includes(":") || state.catalog.spaces[ref] || state.catalog.posts[ref]
  );
}

function actionItem(action, onApply) {
  const wrap = document.createElement("div");
  wrap.className = "action-item";
  wrap.dataset.index = String(action.index);
  wrap.dataset.refs = JSON.stringify(actionRefs(action));
  const button = document.createElement("button");
  button.appendChild(describeAction(action));
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
