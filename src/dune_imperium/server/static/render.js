"use strict";

/* ---------- rendering ---------- */

/* ---------- icons ---------- */

/* Rulebook icons (catalog.icons, served from the machine-local extraction
   of the official Icon Guide) with a text fallback when the set is absent. */
const SEAT_COLORS = ["#2fb3ff", "#ff5a4e", "#7ddc6a", "#f4c542"];

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
  [/\bAgents?\b/y, (m) => icon("agent", m[0])],
  [/\b[Ss]andworms?\b/y, (m) => icon("sandworm", m[0])],
  [/\bMaker Hooks\b/y, () => icon("maker_hooks", "Maker Hooks")],
  [/\bShield Wall\b/y, () => icon("shield_wall", "Shield Wall")],
  [/\bSignet Ring\b/y, () => icon("signet_ring", "Signet Ring")],
  [/\bContracts?\b/y, (m) => icon("contract", m[0])],
  [/→/y, () => icon("arrow_right", "→")],
];

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
  if (!any) wrap.textContent = "무료";
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
function render(options) {
  const summary = state.summary;
  if (!summary) return;
  sanitizePick();
  const foreign = Boolean(options && options.foreign);
  const kept = foreign ? keepScroll() : [];
  if (!(foreign && popoverPinned)) closePopover();
  const allianceBefore = allianceTokenPlaces();
  const shown = state.review && state.review.phase ? state.review : null;
  const round = shown ? shown.round : summary.round_number;
  const phase = shown ? shown.phase : summary.phase;
  el("header-status").textContent =
    `라운드 ${round} · ${PHASE_LABELS[phase] || phase}` +
    (summary.game_seed === null ? "" : ` · seed ${summary.game_seed}`) +
    (summary.choam_module ? " · CHOAM" : "") +
    (summary.promo_cards ? " · promo" : "") +
    (summary.bloodlines ? " · Bloodlines" : "") +
    (summary.tech_module ? " · Tech" : "") +
    (summary.immortality ? " · Immortality" : "") +
    (summary.leader_draft ? " · draft" : "") +
    (state.review ? (spectatorOnly() ? " · AI 대국 관전" : " · 리플레이 검토") : "");
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
  animateMovedAllianceTokens(allianceBefore);
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
  heading.textContent = "종료 후 공개 (모든 비공개 존)";
  panel.appendChild(heading);
  for (const zones of view.disclosure.players) {
    const seat = section(panel, `좌석 ${zones.player}`);
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
    line(`Hand (${zones.hand.length})`, zones.hand, "비어 있음");
    line(`Deck 순서 (${zones.deck.length})`, zones.deck, "비어 있음");
    line(`Intrigue (${zones.intrigue_cards.length})`, zones.intrigue_cards, "없음");
  }
  const decks = section(panel, "공용 덱 순서");
  const deckLine = (label, ids) => {
    const row = document.createElement("div");
    row.className = "cardline";
    const strong = document.createElement("strong");
    strong.textContent = `${label} (${ids.length}) `;
    row.appendChild(strong);
    for (const id of ids) row.appendChild(chip(id));
    decks.appendChild(row);
  };
  deckLine("Imperium deck", view.disclosure.imperium_deck);
  deckLine("Intrigue deck", view.disclosure.intrigue_deck);
  deckLine("Conflict deck", view.disclosure.conflict_deck);
  if (view.disclosure.contract_bank.length) {
    deckLine("Contract bank", view.disclosure.contract_bank);
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
    prompt.textContent = "게임이 끝났습니다.";
    info.append(prompt);
  } else {
    const decision = summary.decision;
    if (!decision) {
      prompt.textContent = "진행 중…";
      info.append(prompt);
    } else if (summary.confirmation === state.viewSeat) {
      /* The viewing seat's turn has ended but its steps can still be taken
         back: nothing advances until it confirms the hand-over. */
      prompt.textContent = "행동을 마쳤습니다. 턴을 넘길까요?";
      meta.textContent =
        `되돌릴 수 있는 동안은 턴이 넘어가지 않습니다 · 다음: ${playerLabel(decision.owner)}`;
      info.append(prompt, meta);
      const row = document.createElement("div");
      row.className = "confirm-row";
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.textContent = "턴 종료 확정 ▶";
      confirm.disabled = state.busy;
      confirm.addEventListener("click", () => confirmTurn());
      row.appendChild(confirm);
      info.appendChild(row);
    } else if (typeof summary.confirmation === "number") {
      /* Another seat's turn has ended but can still be taken back; nobody
         moves until that seat hands it over. */
      prompt.textContent =
        `${playerLabel(summary.confirmation)}의 턴 종료 확정을 기다리는 중…` +
        waitingHint(summary.confirmation);
      meta.textContent = `다음: ${playerLabel(decision.owner)}`;
      info.append(prompt, meta);
    } else if (decision.owner !== state.viewSeat) {
      prompt.textContent =
        `${playerLabel(decision.owner)} 결정 대기 중…` + waitingHint(decision.owner);
      meta.textContent = decision.prompt;
      info.append(prompt, meta);
    } else {
      prompt.textContent = decision.prompt;
      meta.textContent = `좌석 ${decision.owner} (당신)`;
      info.append(prompt, meta);

      if (state.actions) renderActionPanel(actionsBox);
    }
  }

  /* A human seat may still have takeable-back steps after the game ends
     (its last live step), so the undo row renders in both branches above. */
  appendUndoRow(info);
}

/* Why a wait may be a long one: nobody sits there yet, or they dropped off. */
function waitingHint(seat) {
  const info = playerInfo(seat);
  if (!isRemote() || info.kind !== "human") return "";
  if (!info.claimed) return " (아직 아무도 앉지 않은 좌석입니다 — 방 링크를 보내 주세요)";
  return info.online ? "" : " (접속이 끊겨 있습니다)";
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
  one.textContent = "되돌리기 (1단계)";
  one.disabled = state.busy;
  one.addEventListener("click", () => submitUndo(state.viewSeat, 1));
  row.appendChild(one);

  if (entry.steps > 1) {
    const all = document.createElement("button");
    all.type = "button";
    all.textContent = `${entry.steps}단계 모두 되돌리기`;
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
  badge.title = "이 행동 뒤의 내 전투력";
  badge.append(icon("sword", "전투력"), ` ${now} → ${after}`);
  return badge;
}

/* What revealing the hand right now would give: the server's dry run of
   `reveal_turn` (`reveal_preview`: the Persuasion the Reveal opens with and
   the strength once the revealed swords count), so the engine's own sum. */
function revealPreview(preview) {
  const badge = document.createElement("span");
  badge.className = "reveal-preview";
  badge.title = "지금 손패를 공개하면 바로 얻는 Persuasion과 전투력 (Reveal 중의 선택 효과는 제외)";
  badge.append(icon("persuasion", "Persuasion"), ` ${preview.persuasion}`);
  const own = state.view && state.view.players[state.viewSeat];
  const now = own ? own.combat_strength || 0 : 0;
  if (typeof preview.strength === "number" && preview.strength !== now) {
    badge.append(" · ", icon("sword", "전투력"), ` ${now} → ${preview.strength}`);
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
  label.textContent = ACTION_LABELS[id] || prettify(id);
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
  stepper.append(step("−", position - 1, "하나 적게"), value, step("+", position + 1, "하나 더"));
  const confirm = document.createElement("button");
  confirm.type = "button";
  confirm.className = "count-confirm";
  confirm.disabled = state.busy;
  confirm.append(compact ? "확정" : `${chosen.arguments.count}개 ${label.textContent}`);
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
    cost.append(`specimen ${entry.specimens}`);
  } else if (typeof entry.cost === "number") {
    cost.append(amount(action.action_id.includes("solari") ? "solari" : "persuasion", "비용", entry.cost));
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
    left.append("남은 Persuasion ", amount("persuasion", "Persuasion", decision.persuasion));
    status.appendChild(left);
  }
  const bought = boughtThisReveal();
  if (bought.length) {
    const list = document.createElement("span");
    list.className = "reveal-bought";
    list.append("산 카드: ");
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
    heading("Reveal 효과");
    appendActionItems(box, effects);
  }
  if (buys.length) {
    heading("살 수 있는 카드 — 테이블에서 빛나는 카드를 눌러도 됩니다");
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
    button.textContent = buys.length ? "구매 끝 · Reveal 종료" : "Reveal 종료";
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
  button.appendChild(iconize(describeAction(action)));
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
    badge.textContent = "되돌리기 불가";
    badge.title =
      "이 행동 뒤에는 되돌릴 수 없습니다 (숨겨진 정보가 공개되거나 무작위 결과가 정해집니다)";
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
    badge.textContent = action.warning;
    badge.title = "선택은 할 수 있지만 supply가 부족해 인쇄된 만큼 되지 않습니다";
    button.appendChild(badge);
  }
  wrap.appendChild(button);

  const entries = actionPreviewEntries(action);
  if (entries.length) {
    const info = document.createElement("button");
    info.type = "button";
    info.className = "action-info";
    info.textContent = "ⓘ";
    info.title = "효과 미리보기";
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
  text.append(`${label || ref} · 선택지 ${matches.length}개`);
  const clear = document.createElement("button");
  clear.type = "button";
  clear.textContent = "전체 보기";
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
