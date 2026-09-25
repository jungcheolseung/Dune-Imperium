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

/* #game-error carries at most one message at a time. A background refresh
   failure (the doorbell's silent poll losing a request, screens.js
   showRefreshError) is marked with data-source="refresh" so that once a
   later snapshot lands the page can tell its own stale message apart from
   one the player caused; adoptSnapshot (session.js) clears the banner on a
   success only when it still carries that mark. Every other writer goes
   through here too, so its own message (the player's action, turn end,
   undo, or a review request) is never wiped by an unrelated refresh landing
   behind it. */
function showGameError(message) {
  const box = el("game-error");
  box.textContent = message;
  delete box.dataset.source;
  box.hidden = false;
}

function hideGameError() {
  const box = el("game-error");
  box.hidden = true;
  delete box.dataset.source;
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
  if (intrigue) return t("core.intrigue_timings", { timings: timingWords(intrigue.timings) });
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

/* Where a seat's own state sits on its leader's printed track: Feyd-Rautha's
   Training track [Main p. 17] and Chani's Tactics track [Bloodlines p. 12]
   are the only two with a UI text key today (the popover's `seatState` is
   `null`/`undefined` for every other card, and for a leader with no printed
   on-card token, so no line is built for them). `spaceNode` is icon-bearing
   (for the popover line, `tNode`); `spaceText` is the same words as plain
   text (for the token's title, `t()`). */
function leaderStateDescriptor(seatState) {
  if (!seatState) return null;
  if (seatState.leader_id === "chani") {
    const space = seatState.tactics_track_space + 1;
    return { key: "panels.tactics_space", spaceNode: String(space), spaceText: String(space) };
  }
  if (seatState.leader_id === "feyd_rautha_harkonnen") {
    const label = FEYD_TRACK_LABELS[seatState.feyd_track_space] || seatState.feyd_track_space;
    return { key: "panels.feyd_track_space", spaceNode: phrase(label), spaceText: phraseText(label) };
  }
  return null;
}

/* The popover's no-image fallback (openPopover's last branch): plain text
   lines for what the card image would otherwise show -- Chani's and
   Feyd-Rautha's printed space, how many of Steersman Y'rkoon's Navigation
   cards are played and remaining, and that Kota Odax holds a Secret
   Project. Other leaders get no line. */
function leaderFallbackLines(seatState) {
  if (!seatState) return [];
  const lines = [];
  const descriptor = leaderStateDescriptor(seatState);
  if (descriptor) lines.push({ key: descriptor.key, vars: { space: descriptor.spaceNode } });
  if (seatState.leader_id === "steersman_y_rkoon") {
    const played = (seatState.navigation_played || []).length;
    const remaining = seatState.navigation_remaining || 0;
    /* Nothing before his setup placed the cards; after that the line
       stays, even once all four are played. */
    if (played || remaining) {
      lines.push({ key: "panels.navigation_progress", vars: { played, remaining } });
    }
  }
  if (seatState.leader_id === "kota_odax_of_ix" && seatState.has_secret_project) {
    lines.push({ key: "panels.secret_project", vars: {} });
  }
  return lines;
}

/* The box (percent of the leader-card image, `entry.layout` from
   `display.leader_layout`) a seat's own token sits on, or `null` for a
   leader with no printed on-card token, a leader entry with no layout at
   all, or no seat context (a non-leader popover). */
function leaderTokenBox(entry, seatState) {
  if (!entry.layout || !seatState) return null;
  if (seatState.leader_id === "feyd_rautha_harkonnen") {
    return entry.layout.track ? entry.layout.track[seatState.feyd_track_space] || null : null;
  }
  if (seatState.leader_id === "chani") {
    return Array.isArray(entry.layout.track)
      ? entry.layout.track[seatState.tactics_track_space] || null
      : null;
  }
  return null;
}

/* One shared token size for every space on either track, a percent of the
   leader-card stage's width: like one physical piece, sized (with a CSS
   `aspect-ratio: 1` token, so its rendered height matches regardless of the
   stage's own aspect ratio) to sit inside Chani's tightest printed space —
   about 6.4% of the stage on both axes — with a margin, and it also clears
   Feyd's tightest space (`mid_trash`, 5.9% wide). */
const LEADER_TOKEN_SIZE = 4;

/* Each Navigation-card thumbnail's width, a percent of `leaderNavigationRow`'s
   own width (which spans the same width as the leader image below it, both
   being direct children of the popover). Navigation art is a 573x880
   portrait, so this also sets the row's own height (its `aspectRatio`
   below) to fit one card at full height. 18 sits comfortably under the
   narrowest gap between two slot centres — about 24% of the row, between
   slots 1 and 2 (`display.leader_layout.YRKOON_NAVIGATION_SLOT_BOXES`). */
const NAVIGATION_CARD_WIDTH = 18;

/* `visualCard()` (board.js) marks its `<img>` "lazy"; the few cards of a
   leader popover load eagerly instead, so none can sit outside the
   still-unmeasured fixed popover and miss the lazy-load threshold. The
   popover's height needs them (openPopover repositions as each loads). */
function eagerCard(instanceId, options) {
  const card = visualCard(instanceId, options);
  const image = card.querySelector("img");
  if (image) image.loading = "eager";
  return card;
}

/* Steersman Y'rkoon's four Navigation-card slots, drawn in a row above the
   leader image (openPopover), not overlaid on it: printed slot k (1-based;
   `entry.layout.navigation_slots[k - 1]` is the box around the printed
   "1 2 3 4" strip marking where a card lies above the card) shows
   `seatState.navigation_played[k - 1]` face up, for every viewer, once
   played [Bloodlines p. 12]. While a slot still waits
   (k <= navigation_played.length + navigation_remaining), only Y'rkoon's
   own owner sees its face -- docs/rules/bloodlines.md:142 "자신의 face-down
   Navigation 카드를 언제든 볼 수 있다" [Bloodlines p. 12] -- read from
   `state.view.private.navigation_slots` (populated only into the owning
   seat's own view, core/observation.py); every other viewer gets a plain
   card-back placeholder, since no back art exists for a Navigation card.
   Nothing is drawn past
   navigation_played.length + navigation_remaining. Returns `null` when this
   leader has no Navigation slots (every leader but Y'rkoon) or there is no
   seat context. */
function leaderNavigationRow(entry, seatState) {
  const boxes = entry.layout && entry.layout.navigation_slots;
  if (!boxes || !seatState) return null;
  const played = seatState.navigation_played || [];
  const remaining = seatState.navigation_remaining || 0;
  const view = state.view;
  const owner = Boolean(view && view.private && view.player === seatState.player);
  const hidden = owner ? view.private.navigation_slots || [] : [];
  const row = document.createElement("div");
  row.className = "popover-navigation-row";
  row.style.aspectRatio = `100 / ${NAVIGATION_CARD_WIDTH * (880 / 573)}`;
  boxes.forEach((box, index) => {
    const slot = index + 1;
    if (slot > played.length + remaining) return;
    let card;
    if (slot <= played.length) {
      card = eagerCard(played[slot - 1], { className: "leader-nav-card" });
    } else {
      const cardId = hidden[slot - played.length - 1];
      if (cardId !== undefined) {
        card = eagerCard(cardId, {
          className: "leader-nav-card flipped",
          badge: t("panels.face_down_badge"),
        });
      } else {
        card = document.createElement("div");
        card.className = "leader-nav-card nav-card-back";
      }
    }
    const [left, , width] = box;
    card.style.width = `${NAVIGATION_CARD_WIDTH}%`;
    placeAt(card, left + width / 2, 50);
    row.appendChild(card);
  });
  return row.childNodes.length ? row : null;
}

/* Kota Odax of Ix's kept Secret Project tile, drawn below the leader image
   (openPopover), left-aligned under the card's own printed "Secret
   Project" ability box: the card has no printed frame for the tile itself
   ("Place one face down here" [card face]), only the
   ability text it sits under. The owner alone sees which tile it is
   (`view.private.secret_project_tech_id`, populated only into the owning
   seat's own view, core/observation.py) and gets its face muted with the
   same "Face down" badge a face-down Navigation slot uses above
   (`leaderNavigationRow`); every other viewer, knowing only
   `has_secret_project`, gets a Tech-tile-shaped (737x479, landscape)
   placeholder with no identity, since no back art
   exists for a Tech tile either. Nothing once the tile is acquired --
   `has_secret_project` turns false the moment `_take_tile` clears it
   (rules/tech.py). Returns `null` for every leader but Kota, a seat with
   no tile kept, or no seat context. */
function leaderSecretProjectBox(seatState) {
  if (
    !seatState ||
    seatState.leader_id !== "kota_odax_of_ix" ||
    !seatState.has_secret_project
  ) {
    return null;
  }
  const view = state.view;
  const owner = Boolean(view && view.private && view.player === seatState.player);
  const techId = owner ? view.private.secret_project_tech_id : null;
  const row = document.createElement("div");
  row.className = "popover-secret-project-row";
  row.appendChild(
    techId
      ? eagerCard(techId, { className: "tile flipped", badge: t("panels.face_down_badge") })
      : Object.assign(document.createElement("div"), { className: "tile-back" }),
  );
  return row;
}

/* Shaddam Corrino IV's two set-aside Sardaukar contracts [Main p. 17]
   [FAQ p. 3], drawn face up below his leader image the same way Kota's
   tile is: `view.sardaukar_contract_ids` is a top-level, fully public
   field (not per-seat, core/observation.py), so both viewers of his own
   popover see the same list -- it shrinks as he takes one and the popover
   redraws (refreshPinnedLeaderPopover), with no market refill
   (rules/contracts.py). Their own `take_contract` action rows are
   unaffected; a card here stays a legal click target like any other
   `visualCard` (board.js `tableClick`). Returns `null` for every leader
   but Shaddam, no contracts left set aside, or no seat context. */
function leaderSardaukarRow(seatState) {
  if (!seatState || seatState.leader_id !== "shaddam_corrino_iv") return null;
  const view = state.view;
  const ids = (view && view.sardaukar_contract_ids) || [];
  if (!ids.length) return null;
  const row = document.createElement("div");
  row.className = "popover-sardaukar-row";
  for (const id of ids) {
    row.appendChild(eagerCard(id, { className: "contract", badge: t("board.set_aside") }));
  }
  return row;
}

/* The Bloodlines Leaders' texts already open with their ability's own name
   ("Tactician: Whenever…", "Plot Course (no Signet Ring): …"), so the
   popover does not print that name a second time in front of it. */
function opensWithName(text, name) {
  const first = String(name || "").split(" / ")[0];
  return Boolean(first) && (text.startsWith(`${first}:`) || text.startsWith(`${first} (`));
}

/* A line that opens with its own header name ("Tactician: Whenever…", a
   Leader's ability_text) unless the text already starts with it — a Leader
   whose Bloodlines ability text already opens that way is not given it a
   second time (opensWithName(), above). `name` is the ENGLISH header
   (entry.ability_en falls back to entry.ability); `textKo`/`nameKo` are
   Step K5's Korean twins (entry.ability_text_ko / entry.ability, the
   latter already the Korean name once i18n.js's LOCALIZED_FIELDS has
   localized it) — `undefined` for a face with no Korean scan, in which
   case this renders exactly the English line. The Korean check is re-run
   against the Korean text and name (its own text may or may not open with
   its own name, independently of whether the English does). */
function namedEffectLine(text, name, textKo, nameKo) {
  const en = opensWithName(text, name) ? text : `${name}: ${text}`;
  if (textKo === undefined) return effectLine(en, undefined);
  const koName = nameKo === undefined ? name : nameKo;
  const ko = opensWithName(textKo, koName) ? textKo : `${koName}: ${textKo}`;
  return effectLine(en, ko);
}

function popoverNodes(entry) {
  const nodes = [];
  if (entry.text) {
    const textKo = entry.text_ko || [];
    entry.text.forEach((text, i) => nodes.push(effectLine(text, textKo[i])));
  }
  if (entry.condition) {
    nodes.push(
      termLine("core.condition_line", {
        text: effectNode(entry.condition, entry.condition_ko),
      }),
    );
  }
  if (entry.reward) {
    nodes.push(
      termLine("core.reward_line", { text: effectNode(entry.reward, entry.reward_ko) }),
    );
  }
  if (entry.rewards) {
    const rewardsKo = entry.rewards_ko || [];
    entry.rewards.forEach((text, i) => nodes.push(effectLine(text, rewardsKo[i])));
  }
  if (entry.options) {
    if (entry.requirement) nodes.push(requirementNode(entry.requirement));
    for (const option of spaceOptionsFor(entry)) nodes.push(spaceOptionLine(option));
  }
  if (entry.ability_text) {
    const abilityEn = entry.ability_en !== undefined ? entry.ability_en : entry.ability;
    nodes.push(
      namedEffectLine(entry.ability_text, abilityEn, entry.ability_text_ko, entry.ability),
    );
  }
  if (entry.signet_text) {
    const signetEn = entry.signet_en !== undefined ? entry.signet_en : entry.signet;
    // Named vs. unnamed is decided against the rendered language's OWN
    // text and name (entry.signet_text_ko / entry.signet, the latter
    // already the Korean name once localized) rather than always against
    // English — the way namedEffectLine already does for the ability line
    // above. Steersman Y'rkoon's Korean signet_text_ko ("게임 시작: 운항
    // 카드를 …") never opens with its own name "항로 결정" even though the
    // English "Plot Course (no Signet Ring): …" opens with its own, so
    // deciding from English alone picked the unnamed template for Korean
    // too and the Korean name never showed (2026-09-25 fix review).
    const named =
      TERM_LANGUAGE === "ko" && entry.signet_text_ko !== undefined
        ? opensWithName(entry.signet_text_ko, entry.signet)
        : opensWithName(entry.signet_text, signetEn);
    nodes.push(
      named
        ? termLine("core.signet_line_unnamed", {
            text: effectNode(entry.signet_text, entry.signet_text_ko),
          })
        : termLine("core.signet_line", {
            name: entry.signet,
            text: effectNode(entry.signet_text, entry.signet_text_ko),
          }),
    );
  }
  if (entry.notes) {
    const notesKo = entry.notes_ko || [];
    entry.notes.forEach((text, i) => {
      nodes.push(effectLine(text, notesKo[i], "popover-line muted"));
    });
  }
  return nodes;
}

/* `seatState` is the seat's own `PublicPlayerView` (panels.js's `player`)
   when this popover was opened from a seat's leader thumbnail or name, so
   the leader image can draw that seat's own state on the card; every other
   caller leaves it out and gets the plain card popover unchanged. */
function openPopover(entry, anchor, seatState) {
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
  if (entry.timings) {
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
  const image = entryImage(entry);
  if (image && seatState) {
    /* Y'rkoon's own state is a row of Navigation-card slots above the
       image, not a token on it (leaderNavigationRow); every other leader
       with on-card state gets a token instead, below. */
    const navRow = leaderNavigationRow(entry, seatState);
    if (navRow) pop.appendChild(navRow);
    /* A seat's own leader popover: the image becomes a stage (a
       `position: relative` wrapper the same width as the popover; the img
       inside keeps its own natural aspect, so the stage does too) and a
       seat-coloured token is laid on it at the box `leaderTokenBox` finds
       for this seat's current state, in percent of the stage — the same
       technique the board draws its own tokens with (`board.js`'s
       `seatDisc`/`placeAt`). */
    const stage = document.createElement("div");
    stage.className = "popover-leader-stage";
    const stageImage = document.createElement("img");
    stageImage.loading = "lazy";
    stageImage.src = image;
    stageImage.alt = entry.name;
    stage.appendChild(stageImage);
    const box = leaderTokenBox(entry, seatState);
    if (box) {
      const [left, top, width, height] = box;
      const token = seatDisc(seatState.player, "leader-token", LEADER_TOKEN_SIZE);
      const descriptor = leaderStateDescriptor(seatState);
      if (descriptor) token.title = t(descriptor.key, { space: descriptor.spaceText });
      placeAt(token, left + width / 2, top + height / 2);
      stage.appendChild(token);
    }
    pop.appendChild(stage);
    /* Kota's kept tile and Shaddam's set-aside contracts sit below the
       image, like the Navigation row above it: neither is a token *on*
       the printed card, so neither uses `leaderTokenBox`. */
    const secretProjectBox = leaderSecretProjectBox(seatState);
    if (secretProjectBox) pop.appendChild(secretProjectBox);
    const sardaukarRow = leaderSardaukarRow(seatState);
    if (sardaukarRow) pop.appendChild(sardaukarRow);
  } else if (image) {
    const plainImage = document.createElement("img");
    plainImage.loading = "lazy";
    plainImage.src = image;
    plainImage.alt = entry.name;
    pop.appendChild(plainImage);
  } else if (seatState) {
    /* No card image (no private assets): say in words where the token
       sits or what the seat holds -- the same wording the seat panel's own
       status flag used to carry for Chani, Y'rkoon and Kota, and the log's
       own Feyd track wording for Feyd-Rautha. Kota's tile and Shaddam's
       contracts still draw here too -- `visualCard` (via `eagerCard`)
       already falls back to a named textcard when `entry.image` is
       missing, so these are the only place those two facts appear when no
       card art is loaded at all. */
    for (const line of leaderFallbackLines(seatState)) pop.appendChild(termLine(line.key, line.vars));
    const secretProjectBox = leaderSecretProjectBox(seatState);
    if (secretProjectBox) pop.appendChild(secretProjectBox);
    const sardaukarRow = leaderSardaukarRow(seatState);
    if (sardaukarRow) pop.appendChild(sardaukarRow);
  }
  placePopover(pop, anchor, 340);
  /* Every `<img>` this popover ends up with -- the leader's own portrait
     and, now, any eager card below or above it -- lacks an explicit
     `aspect-ratio`, so before it finishes loading the browser lays it out
     at no height at all; `placePopover` above, called synchronously, then
     measures a too-short popover and misplaces it. Repositioning again as
     each image finishes loading (there again once it is already
     `.complete`, e.g. from the browser's own cache, is harmless) fixes
     that without delaying the popover's first paint. */
  for (const loadingImage of pop.querySelectorAll("img")) {
    if (loadingImage.complete) continue;
    loadingImage.addEventListener(
      "load",
      () => {
        /* Only while this is still the popover showing it. A later
           `openPopover` replacing the content detaches this image
           (`pop.textContent = ""`), but `closePopover` does not -- it only
           sets `pop.hidden = true`, leaving a slow image connected and
           able to un-hide the popover from under a pointer that has
           already left. Check both. */
        if (loadingImage.isConnected && !pop.hidden) placePopover(pop, anchor, 340);
      },
      { once: true },
    );
  }
}

/* The popover is fixed-positioned (the table columns scroll on their own)
   and flips above the anchor when it would run off the bottom. An anchor
   that has left the page has an all-zero rect and would throw the popover
   into the top-left corner: the table re-rendered under a pinned popover
   before its image finished loading, or the anchor was a card inside this
   very popover, cleared with its old content. The popover then stays where
   it is, only pulled back up if its new content runs off the bottom. */
function placePopover(pop, anchor, maxWidth) {
  pop.hidden = false;
  if (!anchor.isConnected) {
    const height = pop.offsetHeight;
    const top = parseFloat(pop.style.top) || 8;
    if (top + height > window.innerHeight - 8) {
      pop.style.top = `${Math.max(8, window.innerHeight - height - 8)}px`;
    }
    return;
  }
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
  pinnedLeaderSeat = null;
  clearTimeout(hoverTimer);
}

/* Hover preview: the popover opens after a short delay while the pointer
   rests on a card and closes when it leaves, unless a click pinned it.
   In hover mode it ignores pointer events so it never blocks the cards
   it may overlap. */
let popoverPinned = false;
let hoverTimer = 0;
const HOVER_DELAY_MS = 120;

/* The seat whose leader popover is currently pinned open, or `null` when
   nothing is pinned or the pinned popover is not a seat's leader.
   `refreshPinnedLeaderPopover` uses this after a render to redraw it
   against the seat's freshly rendered state, the way a pinned popover
   otherwise stays open unrefreshed through a foreign one. */
let pinnedLeaderSeat = null;

function hoverPopover(anchor, entryOf, seatOf) {
  anchor.addEventListener("mouseenter", () => {
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => {
      const entry = entryOf();
      if (!entry || popoverPinned) return;
      openPopover(entry, anchor, seatOf ? seatOf() : undefined);
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
function pinPopover(entry, anchor, seatState) {
  openPopover(entry, anchor, seatState);
  popoverPinned = true;
  pinnedLeaderSeat = seatState ? seatState.player : null;
}

/* After a foreign update (someone else's move synced in), a pinned popover
   otherwise stays open exactly as it was — fine for a card's fixed text,
   but a seat's leader popover draws that seat's own live state, which the
   update may have just changed. Redraw it against the freshly rendered seat
   panel (panels.js's `renderSeats()` calls this right after rebuilding it);
   if the seat or its leader is gone, close it instead of showing something
   stale. */
function refreshPinnedLeaderPopover() {
  if (!popoverPinned || pinnedLeaderSeat === null) return;
  const view = state.view;
  const player = view && view.players.find((p) => p.player === pinnedLeaderSeat);
  const faceId = player && (player.leader_face_id || player.leader_id);
  const entry = faceId ? lookup(faceId) : null;
  const anchor = document.querySelector(
    `.seat[data-seat="${pinnedLeaderSeat}"] .leader-name`,
  );
  if (!player || !entry || !anchor) {
    closePopover();
    return;
  }
  openPopover(entry, anchor, player);
  popoverPinned = true;
  pinnedLeaderSeat = player.player;
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

/* An Intrigue card's chosen-option body, its timing prefix stripped
   ("Plot — " etc., intrigue_card_text()'s own label) — the card's own name
   is already on the line, so repeating the timing here would be redundant.
   entry.text_ko[index] is that option's Korean twin, undefined until a
   later step's effect_dsl_text_ko.py fills it in; this strips the same
   " — " separator from it too on the assumption that generator keeps
   ``effect_dsl_text.py option_text()``'s own prefix format (not yet
   written, so unconfirmed — worth checking when that step lands). Until
   the twin exists, effectNode() falls back to the English body. */
function intrigueOptionBody(entry, index) {
  const strip = (line) => {
    const split = line.indexOf(" — ");
    return split === -1 ? line : line.slice(split + 3);
  };
  const textKo = entry.text_ko && entry.text_ko[index];
  return effectNode(strip(entry.text[index]), textKo ? strip(textKo) : undefined);
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
           Korean translates; the rest is generated effect text (action.
           detail_ko is its Korean twin, server/sessions.py, undefined
           until a later step's generator fills it in — effectNode() then
           falls back to iconize(action.detail) exactly as before). */
        const translated = promptText(action.detail);
        parts.push(
          translated !== action.detail
            ? document.createTextNode(translated)
            : effectNode(action.detail, action.detail_ko),
        );
      }
      else if (EFFECT_ICON_LABELS[value]) parts.push(phrase(EFFECT_ICON_LABELS[value]));
    } else if (SEAT_PAYLOAD_KEYS.has(key) && typeof value === "number") {
      parts.push(document.createTextNode(t("common.seat", { seat: value })));
    } else if (
      action.action_id === "play_intrigue" &&
      key === "option" &&
      typeof value === "number"
    ) {
      /* The numeric option index means nothing on its own ("선택지: 0"); the
         catalog already carries each printed option's wording
         (catalog.intrigue[card_id].text[option], one line per engine
         option, always prefixed by its timing: "Plot — ", "Combat — ",
         "Endgame — "). Show that line, prefix stripped, as printed card
         text. A card with only one option needs nothing here (the card
         name already said it); a card the catalog can't resolve (redacted
         or unknown) falls back to the plain numeric label. */
      const cardId = action.arguments.card_id;
      const entry =
        typeof cardId === "string" && state.catalog
          ? state.catalog.intrigue[baseId(cardId)]
          : null;
      const lines = entry && Array.isArray(entry.text) ? entry.text : null;
      if (lines && lines[value] !== undefined) {
        if (lines.length > 1) {
          parts.push(intrigueOptionBody(entry, value));
        }
      } else {
        parts.push(document.createTextNode(`${label}: ${value}`));
      }
    } else if (
      action.action_id === "play_navigation" &&
      key === "option" &&
      typeof value === "number"
    ) {
      /* Unlike play_intrigue, this action carries only "option"
         (rules/navigation.py legal_navigation_play_actions) — no card_id
         argument names the card, so (unlike the play_intrigue branch above)
         this branch must find the card itself, not just its option text.
         A logged step's own `navigation_card_played` event (this action's
         `.events`, panels.js turnLine) carries the card that resolved; the
         card stays in `navigation_slots` while it resolves
         (rules/navigation.py begin_navigation_play/apply_navigation_play),
         so for a LIVE legal action (not yet in `.events`) the front of the
         viewing seat's own `view.private.navigation_slots` is that same
         card. That live-view fallback must not fire for anything else: a
         turn-log entry always carries its own `.events` already (handled
         above), but a replay-review label (server/sessions.py
         `_review_step_label`) carries neither `.events` nor a `card_id` --
         by the time it is shown, `state.view` is the view AFTER the step,
         so the played card has usually already left `navigation_slots` for
         the NEXT slot's own card, and reading the live view here would
         print that wrong card's name as if it were the one played. A live
         legal action (server/sessions.py `_serialize_action`) is the only
         shape with no "type" key at all; both a log entry and a review
         label carry `type: "action"`. Falls back to the plain numeric
         label when neither the event nor (for a live action only) the live
         view resolves a card (a redacted or unknown card, no seat context,
         or -- always, for a review label -- no event). */
      const played = Array.isArray(action.events)
        ? action.events.find((event) => event.kind === "navigation_card_played")
        : null;
      const live = action.type === undefined;
      const view = state.view;
      const liveSlots = live && view && view.private ? view.private.navigation_slots : null;
      const cardId =
        played && typeof played.payload.card_id === "string"
          ? played.payload.card_id
          : liveSlots && liveSlots.length
            ? liveSlots[0]
            : null;
      const entry = cardId && state.catalog ? state.catalog.intrigue[baseId(cardId)] : null;
      const lines = entry && Array.isArray(entry.text) ? entry.text : null;
      if (cardId && lines && lines[value] !== undefined) {
        parts.push(document.createTextNode(nameOf(cardId)));
        if (lines.length > 1) {
          parts.push(intrigueOptionBody(entry, value));
        }
      } else {
        parts.push(document.createTextNode(`${label}: ${value}`));
      }
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
