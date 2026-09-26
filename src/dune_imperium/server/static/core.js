"use strict";

/* Table UI over the local play API: the scanned board with the live state
   drawn on top, printed card images, and the rulebook's icons in place of
   effect text. Every game fact rendered here comes from the server's
   PlayerView / summary / catalog payloads; the client keeps no rules
   knowledge of its own (the icon glossary only re-renders server text). */

const state = {
  catalog: null,
  gameId: null,
  summary: null,
  view: null,
  actions: null,
  viewSeat: null,
  busy: false,
  /* Post-game replay review: {meta, seat, cursor} while active. */
  review: null,
  /* Live session log of the seat on screen: {seat, epoch, count, entries}
     (M11 slice 6). It grows by the tail each snapshot brings; `epoch` is
     the server's name for this log, sent back so the server can tell when
     entries held here went stale (M14 slice 2). */
  log: null,
  /* Who this browser is at the table: {seats, admin, access} (M14). */
  me: null,
  /* The server this page came from: {access, admin, public_url} (M14). */
  server: null,
  /* The staged Agent turn: what the player has picked so far, {cardId?,
     partnerId?, spaceId?} (partnerId: the second card of a graft). It lives
     only in this page; nothing reaches the server until the pick names one
     legal action (see pickStep). */
  pick: null,
  /* The count chosen on each count stepper, by action id (countRow). */
  counts: {},
};

let noteTimer = 0;

const SEAT_KINDS = [
  ["human", "사람"],
  ["heuristic", "휴리스틱 AI"],
  ["rollout", "롤아웃 탐색 AI"],
  ["rollout_strong", "강한 롤아웃 탐색 AI (느림)"],
  ["random", "랜덤 AI"],
  ["checkpoint", "학습 체크포인트 (아래 경로)"],
];

/* A seat assignment is "human", a registry agent name, or
   "checkpoint:<path>"; the label hides the path. */
function seatKindLabel(kind) {
  const key = kind.startsWith("checkpoint:") ? "checkpoint" : kind;
  const found = SEAT_KINDS.find(([value]) => value === key);
  return found ? found[1] : kind;
}

/* Board-layout order for the spaces panel, named as the glossary's Agent
   icons ([Board Guide pp. 1-2]). */
const AGENT_ICON_GROUPS = [
  ["emperor", "황제"],
  ["spacing_guild", "우주 항행 길드"],
  ["bene_gesserit", "베네 게세리트"],
  ["fremen", "프레멘"],
  ["landsraad", "랜드스래드"],
  ["city", "도시"],
  ["spice_trade", "스파이스 거래"],
];

function el(id) {
  return document.getElementById(id);
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = `${response.status}: ${JSON.stringify(body.detail)}`;
    } catch {
      /* keep the status code */
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

/* ---------- naming helpers ---------- */

function prettify(id) {
  return String(id)
    .replaceAll(/[_-]/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function baseId(instanceId) {
  const value = String(instanceId);
  const starter = value.match(/^player:\d+:starter:(.+):\d+$/);
  if (starter) return starter[1];
  const shared = value.match(/^(?:imperium|reserve|intrigue|tleilaxu|skill):(.+):\d+$/);
  if (shared) return shared[1];
  const contract = value.match(/^contract:(.+)$/);
  if (contract) return contract[1];
  return value;
}

function lookup(id) {
  const c = state.catalog;
  if (!c) return null;
  return (
    c.cards[id] ||
    c.intrigue[id] ||
    c.contracts[id] ||
    c.conflicts[id] ||
    c.leaders[id] ||
    c.spaces[id] ||
    c.objectives[id] ||
    (c.skills && c.skills[id]) ||
    (c.tech && c.tech[id]) ||
    null
  );
}

function nameOf(instanceId) {
  const entry = lookup(baseId(instanceId));
  return entry ? entry.name : prettify(baseId(instanceId));
}

/* An observation post has no printed name: it is called after the spaces
   it watches (catalog.post_spaces), "관측소 (Hagga Basin)". */
function postName(postId) {
  const spaces = postSpaces(postId);
  return spaces ? t("core.post_name", { spaces }) : phraseText("{observation_post}");
}

/* The watched spaces alone, for a line whose field label already says 관측소. */
function postSpaces(postId) {
  const c = state.catalog;
  const watched = (c && c.post_spaces && c.post_spaces[postId]) || [];
  const names = watched.map((spaceId) => (c.spaces[spaceId] ? c.spaces[spaceId].name : spaceId));
  return names.length ? names.join(" · ") : null;
}

/* A research space id is the transcription's own coordinate, c<column>r<row>
   (content/immortality/board.py): on screen it is that place on the research
   track, and — where nothing beside it says so — the bonus printed there. */
function researchSpaceName(spaceId, withBonus) {
  const board = state.catalog && state.catalog.bene_tleilax;
  if (!board) return null;
  if (spaceId === board.research_start) return t("board.research_start_title");
  const space = (board.research_spaces || []).find((entry) => entry.id === spaceId);
  if (!space) return null;
  const name = t("core.research_space", { column: space.column, row: space.row });
  const bonus = withBonus && RESEARCH_BONUS_LABELS[space.bonus];
  return bonus ? `${name} (${phraseText(bonus)})` : name;
}

/* A provenance string ("imperium:high_priority_travel:1",
   "round:9:player:1:agent_card:imperium:priority_contracts:0") names the
   card or space behind an event somewhere among its segments; the rest is
   bookkeeping. */
function sourceName(value) {
  for (const part of String(value).split(":")) {
    const entry = lookup(part);
    if (entry) return entry.name;
  }
  return null;
}

/* What one engine value reads as on screen, given the field that holds it
   (an action argument or an event payload key; `siblings` is the rest of
   that object). null: nothing here knows the value, and the caller prints
   it as it came. One resolver for the action list, the log and the review,
   so a post, a research space or a Feyd track space reads the same in all
   three instead of as the engine's id. */
function fieldText(key, value, siblings = {}) {
  const text = String(value);
  /* The server writes the Korean marker for an argument this seat may not
     see (sessions.py); it reads in the page's language. */
  if (text === UI_TEXT["common.hidden"].ko) return t("common.hidden");
  /* The engine joins an id list into one string ("staban_tuek,gurney_halleck",
     Family Atomics' "removed", "garrison,garrison"). */
  if (text.includes(",")) {
    const parts = text
      .split(",")
      .filter(Boolean)
      .map((part) => fieldWord(key, part, siblings));
    if (parts.length && parts.every((part) => part !== null)) return parts.join(", ");
  }
  return fieldWord(key, text, siblings);
}

function fieldWord(key, text, siblings) {
  if (key === "post_id" || key.endsWith("_post_id")) return postName(text);
  if (/^c\d+r\d+$/.test(text)) {
    const research = researchSpaceName(text, !("bonus" in siblings));
    if (research) return research;
  }
  if (key === "faction" || key.endsWith("_faction")) return FACTION_LABELS[text] || null;
  if (key === "bonus" && text in RESEARCH_BONUS_LABELS) {
    return phraseText(RESEARCH_BONUS_LABELS[text]);
  }
  if (key === "action_id") return ACTION_LABELS[text] ? phraseText(ACTION_LABELS[text]) : null;
  /* An acquired card goes to the discard pile; TERMS.discard is the verb. */
  if (key === "destination" && text === "discard") return phraseText("{discard_pile}");
  const isId = key.endsWith("_id") || key.endsWith("_ids");
  const entry = lookup(baseId(text));
  if (isId && entry) return entry.name;
  if ((key === "from_space" || key === "to_space" || key === "space_id") && text in FEYD_TRACK_LABELS) {
    return phraseText(FEYD_TRACK_LABELS[text]);
  }
  /* A rule word ("solari", "hand", "garrison") in the current language. */
  if (TERMS[text]) return phraseText(`{${text}}`);
  if (text in VALUE_LABELS) return phraseText(VALUE_LABELS[text]);
  return entry ? entry.name : null;
}

/* A chance step as words: whose pile was shuffled, or who stole from whom,
   and the card or space that made it happen. The engine's decision id
   (rules/card_draw.py, intrigue_deck.py, board_effects.py) is a provenance
   path, "round:4:player:1:board:arrakeen:discard_shuffle"; only its shape is
   read, and it never reaches the screen. */
function describeChance(decisionId) {
  const id = String(decisionId);
  const owner = id.match(/(?:^|:)player:(\d+)(?=:|$)/);
  const seat = owner ? t("common.seat", { seat: Number(owner[1]) }) : null;
  const steal = id.match(/:secrets:steal:(\d+)$/);
  let what;
  if (steal && seat) {
    what = t("core.chance_secrets_steal", {
      thief: seat,
      victim: t("common.seat", { seat: Number(steal[1]) }),
    });
  } else if (id.endsWith(":discard_shuffle") && seat) {
    what = t("core.chance_discard_shuffle", { seat });
  } else if (id.endsWith(":intrigue_shuffle")) {
    what = t("core.chance_intrigue_shuffle");
  } else {
    return t("core.chance_other");
  }
  /* The seat's own "player:N" and the last word are the kind, not the cause. */
  const cause = steal ? null : sourceName(id.split(":").slice(0, -1).join(":"));
  return cause ? `${what} (${cause})` : what;
}

function cardDetail(instanceId) {
  const id = baseId(instanceId);
  const card = state.catalog && state.catalog.cards[id];
  if (card) {
    const bits = [];
    if (card.cost !== null) bits.push(t("core.card_cost", { cost: card.cost }));
    if (card.specimens !== undefined) bits.push(t("core.card_specimens", { count: card.specimens }));
    if (card.graft) bits.push(phraseText("{graft}"));
    if (card.persuasion) bits.push(t("core.card_persuasion", { amount: card.persuasion }));
    if (card.swords) bits.push(t("core.card_swords", { amount: card.swords }));
    if (card.factions.length) {
      bits.push(card.factions.map((f) => FACTION_LABELS[f] || f).join("/"));
    }
    return bits.join(" · ");
  }
  const intrigue = state.catalog && state.catalog.intrigue[id];
  if (intrigue && intrigue.navigation) return phraseText("{navigation}");
  if (intrigue) {
    return intrigue.timings.length
      ? t("core.intrigue_timings", { timings: timingWords(intrigue.timings) })
      : "";
  }
  const tile = state.catalog && state.catalog.tech && state.catalog.tech[id];
  if (tile) return t("core.tech_tile_cost", { cost: tile.cost });
  const skill = state.catalog && state.catalog.skills && state.catalog.skills[id];
  if (skill) return phraseText("{commander_skill}");
  return "";
}

/* An Intrigue card's timings ("plot", "combat", "endgame") as the glossary
   names them: 음모 / 전투 / 종료 단계 [Main p. 7]. */
const TIMING_KEYS = {
  plot: "core.timing_plot",
  combat: "core.timing_combat",
  endgame: "core.timing_endgame",
};

function timingWords(timings) {
  return timings.map((timing) => (TIMING_KEYS[timing] ? t(TIMING_KEYS[timing]) : timing)).join("/");
}

function chip(instanceId, entryOverride) {
  const span = document.createElement("span");
  span.className = "tag";
  const entry = entryOverride || lookup(baseId(instanceId));
  span.textContent = entry ? entry.name : prettify(baseId(instanceId));
  const detail = cardDetail(instanceId);
  if (detail) span.title = detail;
  if (entry) {
    span.classList.add("clickable");
    span.addEventListener("click", (event) => {
      event.stopPropagation();
      pinPopover(entry, span);
    });
    hoverPopover(span, () => entry);
  }
  return span;
}

/* ---------- detail popover ---------- */

function choamActive() {
  return Boolean(state.summary && state.summary.choam_module);
}

/* What Immortality lays over a space (catalog.spaces[id].immortality): only
   the Research Station has an overlay tile, with its own effect, picture
   and the box where the tile covers the print. */
function spaceOverlayFor(entry) {
  return state.summary && state.summary.immortality && entry.immortality
    ? entry.immortality
    : null;
}

function spaceOptionsFor(entry) {
  const overlay = spaceOverlayFor(entry);
  if (overlay) return overlay.options;
  return choamActive() && entry.choam_options
    ? entry.choam_options
    : entry.options;
}

/* The picture that goes with an entry: a space under an overlay shows the
   overlay tile's picture when the owner's assets have it. */
function entryImage(entry) {
  const overlay = spaceOverlayFor(entry);
  return (overlay && overlay.image) || entry.image;
}

/* A Leader's own tile (Tuek's Sietch) is on the table only while that Leader
   plays [Bloodlines p. 12]. */
function spaceInPlay(entry, view) {
  return (
    !entry.required_leader_id ||
    (view.players || []).some((player) => player.leader_id === entry.required_leader_id)
  );
}

function spaceImplementedFor(entry) {
  return choamActive() ? entry.choam_implemented : entry.implemented;
}

function requirementNode(requirement) {
  const label = FACTION_LABELS[requirement.faction] || requirement.faction;
  const line = document.createElement("div");
  line.className = "popover-line requirement";
  line.append(
    t("core.requirement_prefix"),
    amount(
      `influence_${requirement.faction}`,
      phraseText(`{influence_${requirement.faction}}`),
      requirement.amount,
    ),
    "+"
  );
  return line;
}

/* A popover line of our own words around the card's: the chrome is a text
   key, the printed wording an iconized hole. */
function termLine(key, vars) {
  const line = document.createElement("div");
  line.className = "popover-line";
  line.appendChild(tNode(key, vars));
  return line;
}

function popoverNodes(entry) {
  const nodes = [];
  if (entry.text) for (const text of entry.text) nodes.push(iconLine(text));
  if (entry.condition) {
    nodes.push(termLine("core.condition_line", { text: iconize(entry.condition) }));
  }
  if (entry.reward) nodes.push(termLine("core.reward_line", { text: iconize(entry.reward) }));
  if (entry.rewards) for (const text of entry.rewards) nodes.push(iconLine(text));
  if (entry.options) {
    if (entry.requirement) nodes.push(requirementNode(entry.requirement));
    for (const option of spaceOptionsFor(entry)) nodes.push(spaceOptionLine(option));
  }
  if (entry.ability_text) {
    nodes.push(iconLine(`${entry.ability}: ${entry.ability_text}`));
  }
  if (entry.signet_text) {
    nodes.push(
      termLine("core.signet_line", { name: entry.signet, text: iconize(entry.signet_text) }),
    );
  }
  if (entry.notes) {
    for (const text of entry.notes) nodes.push(iconLine(text, "popover-line muted"));
  }
  return nodes;
}

function openPopover(entry, anchor) {
  const pop = el("card-popover");
  pop.classList.remove("hover");
  pop.textContent = "";

  const title = document.createElement("div");
  title.className = "popover-title";
  title.textContent = entry.name;
  pop.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "meta stats";
  if (entry.cost !== undefined && entry.cost !== null) {
    /* The cost is paid in Persuasion and wears its icon; its name says
       it is the cost, or it reads the same as the Persuasion it gives. */
    meta.appendChild(amount("persuasion", t("core.cost_label"), entry.cost));
  }
  if (entry.persuasion) {
    meta.appendChild(amount("persuasion", phraseText("{persuasion}"), entry.persuasion));
  }
  if (entry.swords) meta.appendChild(amount("sword", phraseText("{sword}"), entry.swords));
  const words = [];
  if (entry.factions && entry.factions.length) {
    words.push(entry.factions.map((f) => FACTION_LABELS[f] || f).join("/"));
  }
  if (entry.navigation) {
    /* No timing banner: Plot Course plays it [Steersman Y'rkoon card]. */
    words.push(phraseText("{navigation}"));
  } else if (entry.timings && entry.timings.length) {
    words.push(t("core.intrigue_timings", { timings: timingWords(entry.timings) }));
  }
  if (entry.tier !== undefined) {
    /* As the rulebook numbers the decks: 교전 I / Conflict I [Main p. 4]. */
    words.push(t("core.conflict_tier", { tier: ["I", "II", "III"][entry.tier - 1] || entry.tier }));
  }
  if (entry.options && !spaceImplementedFor(entry)) words.push(t("core.not_implemented"));
  if (words.length) meta.append(words.join(" · "));
  if (meta.childNodes.length) pop.appendChild(meta);

  for (const node of popoverNodes(entry)) pop.appendChild(node);
  if (entryImage(entry)) {
    const image = document.createElement("img");
    image.loading = "lazy";
    image.src = entryImage(entry);
    image.alt = entry.name;
    pop.appendChild(image);
  }
  placePopover(pop, anchor, 340);
}

/* The popover is fixed-positioned (the table columns scroll on their own)
   and flips above the anchor when it would run off the bottom. */
function placePopover(pop, anchor, maxWidth) {
  pop.hidden = false;
  const rect = anchor.getBoundingClientRect();
  const width = Math.min(maxWidth, window.innerWidth - 16);
  pop.style.width = `${width}px`;
  const left = Math.min(rect.left, Math.max(8, window.innerWidth - width - 8));
  pop.style.left = `${left}px`;
  pop.style.top = `${rect.bottom + 6}px`;
  const height = pop.offsetHeight;
  if (rect.bottom + 6 + height > window.innerHeight - 8) {
    const above = rect.top - height - 6;
    pop.style.top = `${Math.max(8, above >= 8 ? above : window.innerHeight - height - 8)}px`;
  }
}

function closePopover() {
  const pop = el("card-popover");
  pop.hidden = true;
  pop.classList.remove("hover");
  popoverPinned = false;
  clearTimeout(hoverTimer);
}

/* Hover preview: the popover opens after a short delay while the pointer
   rests on a card and closes when it leaves, unless a click pinned it.
   In hover mode it ignores pointer events so it never blocks the cards
   it may overlap. */
let popoverPinned = false;
let hoverTimer = 0;
const HOVER_DELAY_MS = 120;

function hoverPopover(anchor, entryOf) {
  anchor.addEventListener("mouseenter", () => {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      const entry = entryOf();
      if (!entry || popoverPinned) return;
      openPopover(entry, anchor);
      popoverPinned = false;
      el("card-popover").classList.add("hover");
    }, HOVER_DELAY_MS);
  });
  anchor.addEventListener("mouseleave", () => {
    clearTimeout(hoverTimer);
    if (!popoverPinned) closePopover();
  });
}

/* A click pins the popover open until a click elsewhere or Escape. */
function pinPopover(entry, anchor) {
  openPopover(entry, anchor);
  popoverPinned = true;
}

function chipList(container, ids, emptyText) {
  container.textContent = "";
  if (!ids.length) {
    const note = document.createElement("span");
    note.className = "muted";
    note.textContent = emptyText;
    container.appendChild(note);
    return;
  }
  for (const id of ids) container.appendChild(chip(id));
}

/* One action as nodes, not a string. The verb and any effect label are ours,
   so they go through phrase() and may name terms; a card, Leader or space
   name is a proper noun and is appended as plain text. That split is the
   point: the old version joined both into one string and ran ICON_RULES over
   it, so the card named "Signet Ring" was replaced by the Signet Ring icon
   and its line read "배치 — , Arrakeen". */
function describeAction(action) {
  const fragment = document.createDocumentFragment();
  fragment.appendChild(phrase(ACTION_LABELS[action.action_id] || prettify(action.action_id)));
  const parts = [];
  for (const [key, value] of Object.entries(action.arguments)) {
    const label = PAYLOAD_KEY_LABELS[key] || prettify(key);
    if (key === "effect" && typeof value === "string") {
      /* action.detail is the server's English effect fragment; it is printed
         card wording, so it keeps the catalog's icon pass. Without it (a
         logged step) only a keyed icon has a label: a Reveal choice's
         effect id is the engine's name for what the events then say. */
      if (action.detail) {
        /* Some details are an engine prompt (resume_reveal_choice), which
           Korean translates; the rest is card wording. */
        const translated = promptText(action.detail);
        parts.push(
          translated !== action.detail
            ? document.createTextNode(translated)
            : iconize(action.detail),
        );
      }
      else if (EFFECT_ICON_LABELS[value]) parts.push(phrase(EFFECT_ICON_LABELS[value]));
    } else if (SEAT_PAYLOAD_KEYS.has(key) && typeof value === "number") {
      parts.push(document.createTextNode(t("common.seat", { seat: value })));
    } else if (typeof value === "boolean") {
      /* A flag says itself by its name. */
      if (value) parts.push(document.createTextNode(label));
    } else if (typeof value === "number") {
      parts.push(document.createTextNode(`${label}: ${value}`));
    } else {
      const text = fieldText(key, value, action.arguments);
      const shown = text === null ? String(value) : text;
      /* A card, space or post names itself; a faction, reward or zone
         reads with the field that says what it is. */
      const named = key.endsWith("_id") || key.endsWith("_ids") || shown === t("common.hidden");
      parts.push(document.createTextNode(named ? shown : `${label}: ${shown}`));
    }
  }
  parts.forEach((part, index) => {
    fragment.append(index === 0 ? " — " : ", ");
    fragment.appendChild(part);
  });
  return fragment;
}

/* describeAction() as plain text, for a line that takes a string (the
   review status): an amount reads as its title ("3 솔라리") and any other
   icon as its alt text, the words the icons stand for. A fragment dropped
   into a template string printed "[object DocumentFragment]". */
function describeActionText(action) {
  const box = document.createElement("span");
  box.appendChild(describeAction(action));
  for (const node of box.querySelectorAll(".amount")) node.replaceWith(node.title);
  for (const node of box.querySelectorAll("img")) node.replaceWith(node.alt);
  return box.textContent;
}
