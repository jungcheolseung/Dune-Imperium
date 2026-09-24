"use strict";

/* ---------- seats ---------- */

function statNode(name, label, value) {
  const stat = document.createElement("span");
  stat.className = "stat";
  stat.title = label;
  stat.append(
    name === "agent" ? agentPieceIcon(label) : icon(name, label),
    String(value),
  );
  return stat;
}

/* Sardaukar Commanders as the board draws them (renderTrackMarkers): "C2",
   with where they stand in the title. `where` is a term template. */
function commanderChip(count, where) {
  const chip = document.createElement("span");
  chip.className = "commander-count";
  chip.textContent = `C${count}`;
  chip.title = t("panels.commander_where", { where: phraseText(where), count });
  return chip;
}

function seatLine(container, label, content) {
  const line = document.createElement("div");
  line.className = "cardline";
  const strong = document.createElement("strong");
  strong.textContent = `${label} `;
  line.appendChild(strong);
  if (typeof content === "string") line.append(content);
  else line.appendChild(content);
  container.appendChild(line);
}

/* Which seats are showing their detail. Four panels of everything do not fit
   the column: measured on an all-expansion game, the four cards came to
   1,678px mid-game and 2,189px late against 751px of room, so the fourth seat
   was always below the fold. Head, stats and the zone counts stay; the card
   lines fold, and the fold still names what it holds. Remembered per browser,
   like the shared columns. */
const SEATS_KEY = "dune.expandedSeats";
let expandedSeats = new Set();

function loadExpandedSeats() {
  try {
    const stored = JSON.parse(storageGet(SEATS_KEY) || "[]");
    expandedSeats = new Set(Array.isArray(stored) ? stored.map(Number) : []);
  } catch (error) {
    expandedSeats = new Set();
  }
}

function setSeatExpanded(seat, expanded) {
  if (expanded) expandedSeats.add(seat);
  else expandedSeats.delete(seat);
  storageSet(SEATS_KEY, JSON.stringify([...expandedSeats]));
  renderSeats();
}

function toggleAllSeats() {
  const seats = (state.view ? state.view.players : []).map((p) => p.player);
  const anyClosed = seats.some((seat) => !expandedSeats.has(seat));
  expandedSeats = new Set(anyClosed ? seats : []);
  storageSet(SEATS_KEY, JSON.stringify([...expandedSeats]));
  renderSeats();
}

/* What a folded seat says it is hiding: each line's label and how many cards
   are on it, so the fold is still informative. */
function seatDetailSummary(detail) {
  const parts = [];
  for (const line of detail.children) {
    const strong = line.querySelector("strong");
    if (!strong) continue;
    const label = strong.textContent.trim();
    const chips = line.querySelectorAll(".tag").length;
    parts.push(chips ? `${label} ${chips}` : label);
  }
  return parts;
}

function renderSeats() {
  const wrap = el("seats");
  wrap.textContent = "";
  const view = state.view;
  if (!view) return;
  const summary = state.summary;
  const decisionOwner = state.review
    ? view.decision_owner
    : summary.decision
      ? summary.decision.owner
      : null;

  for (const player of view.players) {
    const seat = player.player;
    const card = document.createElement("article");
    card.className = "seat" + (seat === decisionOwner ? " active" : "");
    card.dataset.seat = String(seat);
    card.style.borderLeftColor = SEAT_COLORS[seat];

    const head = document.createElement("div");
    head.className = "seat-head";
    const faceId = player.leader_face_id || player.leader_id;
    const leaderEntry = faceId ? lookup(faceId) : null;
    if (leaderEntry && leaderEntry.image) {
      const image = document.createElement("img");
      image.className = "leader-thumb";
      image.src = leaderEntry.image;
      image.alt = leaderEntry.name;
      image.addEventListener("click", (event) => {
        event.stopPropagation();
        pinPopover(leaderEntry, image);
      });
      hoverPopover(image, () => leaderEntry);
      head.appendChild(image);
    }
    const who = document.createElement("div");
    who.className = "who";
    /* The name keeps one line of its own (cut short with an ellipsis; the
       hover card has it whole) and the badges take the next: a long name
       wrapping to two lines made three of four seats 23px taller. */
    const nameLine = document.createElement("span");
    nameLine.className = "who-name";
    const seatMark = seatToken(seat, "seat-mark");
    nameLine.appendChild(seatMark);
    const leaderName = document.createElement("span");
    leaderName.className = "leader-name";
    leaderName.textContent = player.leader_id ? nameOf(faceId) : t("panels.leader_unset");
    /* A cut-short name reads whole in the hover card, or in the title. */
    if (!leaderEntry) leaderName.title = leaderName.textContent;
    if (leaderEntry) {
      leaderName.classList.add("clickable");
      leaderName.addEventListener("click", (event) => {
        event.stopPropagation();
        pinPopover(leaderEntry, leaderName);
      });
      hoverPopover(leaderName, () => leaderEntry);
    }
    nameLine.appendChild(leaderName);
    who.appendChild(nameLine);
    if (summary.seats[seat] === "human") {
      const badge = document.createElement("span");
      badge.className = "badge";
      const mine = isRemote() ? mySeats().includes(seat) : seat === activeSeat();
      badge.textContent = mine
        ? isRemote() && playerInfo(seat).name
          ? t("panels.you_named", { name: playerInfo(seat).name })
          : t("panels.you_badge")
        : playerName(seat);
      who.appendChild(badge);
      if (isRemote() && playerInfo(seat).claimed) {
        who.appendChild(presenceDot(playerInfo(seat)));
      }
    } else {
      const badge = document.createElement("span");
      badge.className = "badge ai";
      const kind = summary.seats[seat];
      badge.textContent = seatKindLabel(kind);
      /* The label hides a checkpoint's path; its tooltip names the file. */
      badge.title = kind.startsWith("checkpoint:")
        ? kind.slice("checkpoint:".length)
        : seatKindLabel(kind);
      who.appendChild(badge);
    }
    if (summary.first_player === seat) {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = t("panels.first_badge");
      badge.title = phraseText("{first_player}");
      who.appendChild(badge);
    }
    head.appendChild(who);
    card.appendChild(head);

    const stats = document.createElement("div");
    stats.className = "stats";
    /* Counts that are not already visible on a board track stay at a glance.
       Immortality p. 16 names the green cube as the Specimen icon. */
    stats.append(
      statNode("victory_point", phraseText("{victory_point}"), player.victory_points),
      statNode("solari", phraseText("{solari}"), player.resources.solari),
      statNode("spice", phraseText("{spice}"), player.resources.spice),
      statNode("water", phraseText("{water}"), player.resources.water),
      statNode("intrigue", phraseText("{intrigue}"), player.intrigue_card_count),
    );
    if (summary.immortality) {
      stats.appendChild(
        statNode("specimen", phraseText("{specimen}"), player.specimens || 0),
      );
    }
    card.appendChild(stats);


    const pieces = document.createElement("div");
    pieces.className = "stats";
    pieces.append(
      statNode("agent", t("panels.agent_remaining"), player.agents_available),
      statNode("spy", t("panels.supply_spy"), player.spies_supply),
    );
    card.appendChild(pieces);

    /* Each flag is nodes (tNode), so its rule terms keep their icons. The
       High Council seat and the Swordmaster are the glossary's 원로회 and
       소드마스터; only the board spaces of those names stay English. */
    const flags = [];
    if (player.high_council) flags.push(tNode("panels.high_council"));
    if (player.maker_hooks) flags.push(tNode("panels.maker_hooks"));
    if (player.swordmaster_acquired) flags.push(tNode("panels.swordmaster"));
    if (player.has_revealed) flags.push(tNode("panels.revealed"));
    if (player.control_space_ids.length) {
      flags.push(
        tNode("panels.control_spaces", {
          spaces: player.control_space_ids.map(nameOf).join("/"),
        }),
      );
    }
    /* Bloodlines Leader state: Chani's Tactics token, Piter's Twisted deck,
       Y'rkoon's remaining Navigation slots, Kota's Secret Project tile. */
    if (player.leader_id === "chani") {
      flags.push(tNode("panels.tactics_space", { space: player.tactics_track_space + 1 }));
    }
    if (player.twisted_deck_size) {
      flags.push(tNode("panels.twisted_deck", { count: player.twisted_deck_size }));
    }
    if (player.navigation_remaining) {
      flags.push(tNode("panels.navigation_remaining", { count: player.navigation_remaining }));
    }
    if (player.has_secret_project) flags.push(tNode("panels.secret_project"));
    if (player.spies_boxed) flags.push(tNode("panels.spy_boxed", { count: player.spies_boxed }));
    /* Immortality state not drawn on the Bene Tleilax board: the Family
       Atomics token and grafted-card promises. */
    if (state.summary.immortality) {
      if (player.family_atomics) flags.push(tNode("panels.family_atomics"));
      if ((player.chairdog_return_card_ids || []).length) {
        flags.push(
          tNode("panels.chairdog_return", {
            cards: player.chairdog_return_card_ids.map(nameOf).join("/"),
          })
        );
      }
      if (player.usurped_row_card_id) {
        flags.push(tNode("panels.usurp_trash", { card: nameOf(player.usurped_row_card_id) }));
      }
    }
    /* Everything below the zone counts folds away: the card lines are what
       pushed the fourth seat off the screen. */
    const detail = document.createElement("div");
    detail.className = "seat-detail";
    if (flags.length) {
      const status = document.createDocumentFragment();
      flags.forEach((flag, index) => {
        if (index) status.append(" · ");
        status.append(flag);
      });
      seatLine(detail, t("panels.status_label"), status);
    }
    if (player.skill_ids && player.skill_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${t("panels.skills_label")} `;
      line.appendChild(strong);
      for (const id of player.skill_ids) line.appendChild(chip(skillIdOf(id)));
      detail.appendChild(line);
    }
    if (player.tech_ids && player.tech_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${t("panels.tech_label")} `;
      line.appendChild(strong);
      for (const id of player.tech_ids) {
        const mark = chip(id);
        if ((player.tech_flipped || []).includes(id)) {
          mark.textContent += t("panels.flip_suffix");
          mark.classList.add("muted");
        }
        line.appendChild(mark);
      }
      detail.appendChild(line);
    }
    const agents = player.agent_locations.map(nameOf).join(", ");
    if (agents) seatLine(detail, t("panels.agents_placed_label"), agents);

    const zones = document.createElement("div");
    zones.className = "zones";
    /* The last English line in the seat panel: the zone names are glossary
       terms, so phraseText gives them the same words as everywhere else. */
    zones.textContent = phraseText(
      `{hand} ${player.hand_size} · {deck} ${player.deck_size}` +
        ` · {discard_pile} ${player.discard_pile.length}`,
    );
    if (player.discard_pile.length) {
      zones.classList.add("clickable");
      zones.title = t("panels.discard_pile_view");
      /* Same "mine" test as the hand strip (~line 997): on a remote table
         ownership follows the seats this browser claimed regardless of what
         is being viewed; locally (live or reviewed) it follows the seat
         being looked at, but only when reviewing a seat this browser
         actually played -- an all-AI review must never call an AI's pile
         "my discard" just because it is the one on screen. */
      const mine = isRemote()
        ? mySeats().includes(seat)
        : seat === activeSeat() && (!state.review || mySeats().includes(seat));
      zones.addEventListener("click", (event) => {
        event.stopPropagation();
        openPileList(
          mine
            ? t("panels.my_discard")
            : t("panels.seat_discard", { seat: t("common.seat", { seat }) }),
          player.discard_pile,
          zones,
        );
      });
    }
    card.appendChild(zones);

    const battle = [...player.objective_ids, ...player.won_conflict_ids];
    if (battle.length || player.face_down_battle_card_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${t("panels.battle_label")} `;
      line.appendChild(strong);
      for (const id of battle) line.appendChild(chip(id));
      for (const id of player.face_down_battle_card_ids) {
        const mark = chip(id);
        mark.textContent += t("panels.facedown_suffix");
        mark.classList.add("muted");
        line.appendChild(mark);
      }
      detail.appendChild(line);
    }
    if (player.active_contract_ids.length || player.completed_contract_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${t("panels.contracts_label")} `;
      line.appendChild(strong);
      for (const id of player.active_contract_ids) line.appendChild(chip(id));
      /* Completed Contracts stay re-checkable (OQ-010): their completion
         was announced before they flipped face down. */
      for (const id of player.completed_contract_ids) {
        const mark = chip(id);
        mark.textContent += t("panels.completed_suffix");
        mark.classList.add("muted");
        line.appendChild(mark);
      }
      detail.appendChild(line);
    }
    if (player.in_play.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${t("panels.in_play_label")} `;
      line.appendChild(strong);
      for (const id of player.in_play) line.appendChild(chip(id));
      detail.appendChild(line);
    }
    /* Hand cards that entered through a public move (Corrinth City, an
       Intrigue "put it in your hand", a Bond return) stay known (OQ-010). */
    if (player.hand_public.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = t("panels.hand_public_label");
      line.appendChild(strong);
      for (const id of player.hand_public) line.appendChild(chip(id));
      detail.appendChild(line);
    }
    if (view.intrigue_resolving.length && view.decision_owner === player.player) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = t("panels.intrigue_resolving_label");
      line.appendChild(strong);
      for (const id of view.intrigue_resolving) line.appendChild(chip(id));
      detail.appendChild(line);
    }
    if (detail.children.length) {
      const expanded = expandedSeats.has(player.player);
      const more = document.createElement("button");
      more.type = "button";
      more.className = "seat-more";
      more.setAttribute("aria-expanded", expanded ? "true" : "false");
      const summary = seatDetailSummary(detail).join(" · ");
      more.textContent = expanded
        ? t("panels.seat_more_collapse")
        : t("panels.seat_more_expand", { summary });
      if (!expanded) more.title = summary;
      more.addEventListener("click", (event) => {
        event.stopPropagation();
        setSeatExpanded(player.player, !expanded);
      });
      detail.hidden = !expanded;
      card.append(more, detail);
    }
    wrap.appendChild(card);
  }
}

/* A Skill tile instance ("skill:<id>:<copy>") to its catalog id. */
function skillIdOf(instanceId) {
  const match = String(instanceId).match(/^skill:(.+):\d+$/);
  return match ? match[1] : String(instanceId);
}

/* A pile listing (discard, Intrigue piles) in the popover: one pile as
   `(title, ids, anchor)`, or several as `([[title, ids], ...], null, anchor)`
   (empty piles are left out). */
function openPileList(title, ids, anchor) {
  const piles = Array.isArray(title) ? title : [[title, ids]];
  const pop = el("card-popover");
  pop.textContent = "";
  for (const [pileTitle, pileIds] of piles) {
    if (!pileIds.length && piles.length > 1) continue;
    const head = document.createElement("div");
    head.className = "popover-title";
    head.textContent = `${pileTitle} (${pileIds.length})`;
    pop.appendChild(head);
    const row = document.createElement("div");
    row.className = "strip-cards wrap";
    for (const id of pileIds) row.appendChild(visualCard(id, { className: "small" }));
    pop.appendChild(row);
  }
  placePopover(pop, anchor, 420);
}

/* ---------- live action log (M11 slice 6) ---------- */

/* Render one event's payload as compact "key: value" pairs. Values keyed by
   an id-shaped field (card/instance/conflict id, post_id, space_id) resolve
   through the catalog via nameOf; the "player" key renders as a seat label. */
/* Payload fields that hold a seat number (-1: nobody). */
const SEAT_PAYLOAD_KEYS = new Set([
  "player",
  "first_player",
  "from_player",
  "to_player",
  "recipient",
  "victim",
  "visitor",
]);

function logEventPayload(payload) {
  const parts = [];
  const shownNames = new Set();
  for (const [key, value] of Object.entries(payload)) {
    const label = PAYLOAD_KEY_LABELS[key] || prettify(key);
    /* Before the zero filter: seat 0 is a seat. */
    if (SEAT_PAYLOAD_KEYS.has(key)) {
      if (typeof value !== "number" || value < 0) continue;
      const seat = t("common.seat", { seat: value });
      parts.push(key === "player" ? seat : `${label}: ${seat}`);
      continue;
    }
    /* Combat rewards and the like list every field; zeros say nothing. */
    if (value === 0 || value === "" || value === null || value === false) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    if (key === "source") {
      const name = sourceName(value);
      if (name) parts.push(`${label}: ${name}`);
      continue;
    }
    /* A flag says itself by its name. */
    if (value === true) {
      parts.push(label);
      continue;
    }
    /* Every id-shaped field resolves through the catalog (the engine emits
       about 35: card_id, leader_id, tech_id, skill_instance_id, post_id…),
       and every other word through fieldText (core.js), as the action list
       does. */
    const isIdField = key.endsWith("_id");
    let shown;
    if (key === "effect") {
      /* A keyed board icon has a label; a Reveal choice's effect id is the
         engine's name for what the event line already says. */
      if (!EFFECT_ICON_LABELS[value]) continue;
      shown = phraseText(EFFECT_ICON_LABELS[value]);
    } else if ((key === "post_id" || key.endsWith("_post_id")) && postSpaces(value)) {
      shown = postSpaces(value);
    } else {
      const raw = Array.isArray(value) ? value.join(",") : value;
      const text = typeof raw === "string" ? fieldText(key, raw, payload) : null;
      if (text === "") continue;
      shown = text === null ? String(value) : text;
    }
    /* card_id and instance_id of one event resolve to the same name. */
    if (isIdField && shownNames.has(shown)) continue;
    if (isIdField) shownNames.add(shown);
    parts.push(`${label}: ${shown}`);
  }
  return parts.join(" · ");
}

function logEventLine(event) {
  const line = document.createElement("div");
  line.className = "logevent";
  /* phrase(), not textContent: an event label may name a term, and the
     braces must never reach the screen. */
  line.appendChild(phrase(EVENT_LABELS[event.kind] || prettify(event.kind)));
  const payload = logEventPayload(event.payload);
  if (payload) line.append(` — ${payload}`);
  return line;
}

/* Steps that only close a window; kept in the record but muted:
   finish_agent_turn and finish_reveal end an Agent or Reveal turn, and
   pass_combat_intrigue / pass_endgame_intrigue decline a Combat or Endgame
   Intrigue window (rules/combat.py, rules/endgame.py) — the engine never
   emits a bare "pass". */
const QUIET_ACTIONS = new Set([
  "finish_agent_turn",
  "finish_reveal",
  "pass_combat_intrigue",
  "pass_endgame_intrigue",
]);

/* Steps that stand as a card of their own (setup picks). */
const SOLO_ACTIONS = new Set(["pick_leader"]);

/* Events the game produces on its own once a step closes a window —
   setup after the last Leader pick, combat resolution after the last
   Reveal, the round change — rather than the acting seat's doing. From
   the first of these in a step, the rest of that step's events belong to
   the game too (the round-start draws follow the recall, the Victory
   Points follow the combat reward). */
const NEUTRAL_EVENT_KINDS = new Set([
  "leader_draft_pool_revealed",
  "leader_draft_unused",
  "conflict_revealed",
  "combat_intrigue_started",
  "combat_intrigue_finished",
  "combat_reward_gained",
  "conflict_won",
  "battle_icons_matched",
  "battle_card_flipped",
  "combat_cleaned_up",
  "maker_spice_added",
  "agents_recalled",
  "endgame_started",
  "endgame_wild_matched",
  "game_finished",
]);

/* Split one step's events into the actor's own and the game's: a neutral
   kind switches the rest of the step over, and an event aimed at another
   seat (its draw, its loss) is never the actor's own. */
function splitEntryEvents(entry) {
  const own = [];
  const neutral = [];
  let flow = false;
  for (const event of entry.events) {
    if (!flow && NEUTRAL_EVENT_KINDS.has(event.kind)) flow = true;
    const target = event.payload ? event.payload.player : undefined;
    const other = typeof target === "number" && target !== entry.actor;
    (flow || other ? neutral : own).push(event);
  }
  return { own, neutral };
}

/* Events a folded pass's own line (below) may carry and still fold: the
   window's own "declined" marker, or nothing at all (the pass that closes
   the window reads as flow instead, see splitEntryEvents/NEUTRAL_EVENT_KINDS
   and combat_intrigue_finished). */
const PASS_MARKER_KINDS = new Set(["combat_intrigue_passed", "endgame_intrigue_passed"]);

/* Group the log into cards. A turn card holds consecutive steps by one
   seat (with only their own events) until a step closes the turn
   (finish_agent_turn, finish_reveal, pass_combat_intrigue,
   pass_endgame_intrigue); a Leader pick is a card of
   its own. Everything the game does by itself — the neutral events above
   and every chance step — goes into a "게임 진행" card between them, so
   the round change never reads as the last actor's move.

   A pass_combat_intrigue / pass_endgame_intrigue that would otherwise start
   a brand new, single-entry card of its own (nothing of that seat's own is
   open to continue) instead folds into the run of chained passes right
   before it, one "passes" group per unbroken chain of the same action_id:
   an unused Combat or Endgame Intrigue window used to show "pass" once per
   seat, each as its own full-weight card (ITEM 8h). A pass that closes a
   seat's own open card (it played something first) still ends that card,
   as before -- it is that seat's own move, not an empty decline. */
function logGroups(entries) {
  const groups = [];
  let open = null;
  let neutral = null;
  const addNeutral = (index, items) => {
    if (!items.length) return;
    if (!neutral) {
      neutral = { kind: "neutral", items: [], firstIndex: index, lastIndex: index };
      groups.push(neutral);
    }
    neutral.items.push(...items);
    neutral.lastIndex = index;
    open = null;
  };
  for (const entry of entries) {
    if (entry.type === "undo") {
      groups.push({ kind: "undo", entry });
      open = null;
      neutral = null;
      continue;
    }
    if (entry.type === "chance") {
      addNeutral(entry.index, [{ chance: entry }]);
      continue;
    }
    const { own, neutral: flow } = splitEntryEvents(entry);
    const step = { ...entry, events: own };
    const foldable =
      PASS_ACTION_IDS.has(entry.action_id) &&
      !(open && open.actor === entry.actor) &&
      own.every((event) => PASS_MARKER_KINDS.has(event.kind));
    const last = groups[groups.length - 1];
    if (foldable && last && last.kind === "passes" && last.action_id === entry.action_id) {
      last.entries.push(step);
      open = null;
    } else if (foldable) {
      groups.push({ kind: "passes", action_id: entry.action_id, entries: [step] });
      open = null;
    } else if (SOLO_ACTIONS.has(entry.action_id)) {
      groups.push({ kind: "turn", actor: entry.actor, entries: [step] });
      open = null;
    } else {
      if (open && open.actor === entry.actor) open.entries.push(step);
      else {
        open = { kind: "turn", actor: entry.actor, entries: [step] };
        groups.push(open);
      }
      if (QUIET_ACTIONS.has(entry.action_id)) open = null;
    }
    neutral = null;
    addNeutral(entry.index, flow.map((event) => ({ event, index: entry.index })));
  }
  return groups;
}

/* What a neutral card is about, from the kinds it carries. */
function neutralTitle(group) {
  const kinds = new Set(group.items.filter((item) => item.event).map((item) => item.event.kind));
  const parts = [];
  if (kinds.has("leader_draft_unused") || kinds.has("leader_draft_pool_revealed")) {
    parts.push(t("panels.neutral_setup"));
  }
  if (kinds.has("combat_intrigue_started")) parts.push(t("panels.neutral_combat_intrigue"));
  if (kinds.has("conflict_won") || kinds.has("combat_reward_gained")) {
    parts.push(t("panels.neutral_combat_resolved"));
  }
  if (kinds.has("agents_recalled") || kinds.has("conflict_revealed")) {
    const revealed = group.items.find(
      (item) => item.event && item.event.kind === "conflict_revealed"
    );
    const round = revealed && revealed.event.payload && revealed.event.payload.round;
    parts.push(
      round
        ? t("panels.neutral_round_started", { round })
        : t("panels.neutral_round_started_generic")
    );
  }
  if (kinds.has("endgame_started")) parts.push(phraseText("{endgame}"));
  if (kinds.has("game_finished")) parts.push(t("common.game_over"));
  return parts.length ? parts.join(" · ") : t("panels.neutral_default");
}

function neutralCard(group, glowFrom) {
  const card = document.createElement("div");
  card.className = "turn-card neutral";
  if (group.lastIndex >= glowFrom) card.classList.add("fresh");
  const head = document.createElement("div");
  head.className = "turn-head";
  const mark = document.createElement("span");
  mark.className = "neutral-mark";
  mark.textContent = "⚙";
  const who = document.createElement("strong");
  who.textContent = neutralTitle(group);
  head.append(mark, who);
  card.appendChild(head);
  const lines = document.createElement("div");
  lines.className = "turn-lines";
  for (const item of group.items) {
    lines.appendChild(item.chance ? chanceLine(item.chance) : logEventLine(item.event));
  }
  card.appendChild(lines);
  /* Spotlight what the game touched (Maker spice, the new Conflict). */
  const pseudo = {
    entries: [
      {
        type: "action",
        actor: null,
        arguments: {},
        events: group.items.filter((item) => item.event).map((item) => item.event),
      },
    ],
  };
  card.addEventListener("mouseenter", () => setSpotlight(pseudo));
  card.addEventListener("mouseleave", () => {
    if (spotlightGroup === pseudo) setSpotlight(null);
  });
  return card;
}

function chanceLine(entry) {
  const line = document.createElement("div");
  line.className = "turn-line chance";
  let text = t("core.chance_label", { decision: describeChance(entry.decision_id) });
  if (entry.values) {
    const shown =
      entry.values.length <= 3
        ? entry.values.map(nameOf).join(", ")
        : `${entry.values.slice(0, 3).map(nameOf).join(", ")} …`;
    text += ` — ${shown}`;
  }
  line.textContent = text;
  return line;
}

function turnLine(entry) {
  const line = document.createElement("div");
  line.className = "turn-line";
  if (QUIET_ACTIONS.has(entry.action_id)) line.classList.add("quiet");
  if (entry.undone) line.classList.add("undone");
  const head = document.createElement("div");
  head.className = "turn-line-head";
  const index = document.createElement("span");
  index.className = "turn-index";
  index.textContent = `#${entry.index}`;
  head.append(index, describeAction(entry));
  if (entry.undone) head.append(t("panels.undone_suffix"));
  line.appendChild(head);
  for (const event of entry.events) line.appendChild(logEventLine(event));
  return line;
}

/* The Leader name shown for a seat in the log -- its current Leader once
   picked (front or flipped face), "Seat N" before that. turnCard's head and
   a folded pass's seat line (passesCard) both read a seat's name this way. */
function seatLeaderName(seat) {
  const player = state.view && state.view.players[seat];
  const leaderFace = player && (player.leader_face_id || player.leader_id);
  return leaderFace ? nameOf(leaderFace) : t("common.seat", { seat });
}

function turnCard(group, glowFrom) {
  const card = document.createElement("div");
  card.className = "turn-card";
  const color = SEAT_COLORS[group.actor];
  card.style.borderLeftColor = color;
  if (group.entries.some((entry) => entry.index >= glowFrom)) card.classList.add("fresh");
  if (group.entries.every((entry) => entry.undone)) card.classList.add("undone");

  const head = document.createElement("div");
  head.className = "turn-head";
  head.appendChild(seatToken(group.actor, "seat-mark"));
  const who = document.createElement("strong");
  who.textContent = seatLeaderName(group.actor);
  head.appendChild(who);
  const kind = state.summary.seats[group.actor];
  const badge = document.createElement("span");
  badge.className = kind === "human" ? "badge" : "badge ai";
  badge.textContent =
    kind === "human"
      ? group.actor === activeSeat()
        ? t("panels.you_badge")
        : playerName(group.actor)
      : seatKindLabel(kind);
  head.appendChild(badge);
  const targets = logTargets(group);
  if (targets.spaces.length) {
    const where = document.createElement("span");
    where.className = "turn-where";
    where.append(
      agentPieceIcon(phraseText("{agent}")),
      " ",
      targets.spaces.map(nameOf).join(", "),
    );
    head.appendChild(where);
  }
  card.appendChild(head);

  const body = document.createElement("div");
  body.className = "turn-body";
  const lines = document.createElement("div");
  lines.className = "turn-lines";
  for (const entry of group.entries) lines.appendChild(turnLine(entry));
  body.appendChild(lines);
  if (targets.cards.length) {
    const row = document.createElement("div");
    row.className = "turn-cards";
    for (const id of targets.cards.slice(0, 4)) {
      row.appendChild(
        visualCard(id, {
          className: "small",
          onClick: (entry, node) => {
            if (entry) pinPopover(entry, node);
          },
        })
      );
    }
    body.appendChild(row);
  }
  card.appendChild(body);

  card.addEventListener("mouseenter", () => setSpotlight(group));
  card.addEventListener("mouseleave", () => {
    if (spotlightGroup === group) setSpotlight(null);
  });
  return card;
}

/* The label for a folded chain of Combat/Endgame Intrigue passes: the words
   the engine's own event carries for it, once for the whole card. Combat
   Intrigue already has one (EVENT_LABELS.combat_intrigue_passed); Endgame
   Intrigue's own event label is bare ("Passed") because turnLine's head
   names the window already (ACTION_LABELS) -- a fold has no such head per
   seat, so it gets a matching label of its own
   (panels.pass_fold_endgame_intrigue, UI_TEXT). */
function passFoldLabel(actionId) {
  return actionId === "pass_endgame_intrigue"
    ? tNode("panels.pass_fold_endgame_intrigue")
    : phrase(EVENT_LABELS.combat_intrigue_passed);
}

/* One compact card for a run of chained Combat/Endgame Intrigue passes
   (logGroups, ITEM 8h): the label once, then the seats that passed, in
   order, on the SAME wrapping line as the label (one .turn-head, like a
   turn card's own head) -- not a full turn card per seat repeating the
   same "pass", and not a second line below the label either. */
function passesCard(group, glowFrom) {
  const card = document.createElement("div");
  card.className = "turn-card passes";
  if (group.entries.some((entry) => entry.index >= glowFrom)) card.classList.add("fresh");
  if (group.entries.every((entry) => entry.undone)) card.classList.add("undone");

  const head = document.createElement("div");
  head.className = "turn-head";
  const label = document.createElement("strong");
  label.appendChild(passFoldLabel(group.action_id));
  head.appendChild(label);
  group.entries.forEach((entry, index) => {
    if (index) head.append(" · ");
    const seat = document.createElement("span");
    seat.className = "pass-seat";
    if (entry.undone) seat.classList.add("undone");
    seat.appendChild(seatToken(entry.actor, "seat-mark"));
    seat.append(seatLeaderName(entry.actor));
    head.appendChild(seat);
  });
  card.appendChild(head);
  return card;
}

function undoRow(entry) {
  const row = document.createElement("div");
  row.className = "turn-card undo-marker";
  row.textContent = t("panels.undo_row", { seat: entry.seat, count: entry.count });
  return row;
}

/* Entries from this index on arrived since the previous render: the list
   scrolls to the first card that holds one of them (arrivedFrom in
   renderLog). Locally a whole AI batch lands in one render, so this is
   close to "since the viewing seat last acted" (glowFrom) -- not exactly
   equal, since glowFrom also leaves out the viewing seat's own new card,
   which this number includes. In remote play every opponent step triggers
   its own render, so this number alone would only ever cover the last
   step -- see glowFrom for what actually glows. */
let logSeen = { gameId: null, count: 0, freshFrom: 0 };

/* The scrollTop the renderer itself set on its last automatic scroll (to the
   first arrived card, or to the end), per game. Whether the *next* render
   should keep following is decided from this, not from "near the bottom"
   alone: a fresh batch taller than the list (the leader draft, a round
   change) lands the auto-scroll well short of the end, and comparing only
   position then reads that as the reader having wandered off and never
   follows again. */
let logAutoTop = { gameId: null, top: 0 };

/* Where "new to `seat`" starts: one past `seat`'s own last live entry (its
   last non-undone action, or its last undo marker, whichever is later in
   the log). Everything from there on is new to that seat, whether it
   arrived in one render or many -- which is what a remote table needs,
   since there every opponent step is its own render and "since the
   previous render" (logSeen.freshFrom) would only ever show the last one.
   0 when the seat has not acted yet, so its whole log is new. */
function ownGlowFrom(seat, entries) {
  let last = -1;
  for (const entry of entries) {
    if (entry.type === "action" && entry.actor === seat && !entry.undone) last = entry.index;
    else if (entry.type === "undo" && entry.seat === seat) last = entry.index;
  }
  return last + 1;
}

function renderLog() {
  const panel = el("action-log");
  /* The list is rebuilt from scratch, so its scroll offset has to be read
     before the panel is emptied. A reader who has scrolled up to re-read an
     earlier turn keeps their place; one already at the end, or still sitting
     where the previous render's auto-scroll left them, keeps following the
     game. Without this the log yanked itself to the newest entry on every
     render, including renders caused by somebody else's move. */
  const previous = panel.querySelector(".log-list");
  const previousTop = previous ? previous.scrollTop : 0;
  const atAutoOffset =
    Boolean(previous) &&
    logAutoTop.gameId === state.gameId &&
    Math.abs(previousTop - logAutoTop.top) <= 2;
  const following =
    !previous ||
    atAutoOffset ||
    previous.scrollHeight - previous.scrollTop - previous.clientHeight < 24;
  panel.textContent = "";
  /* In review the log follows the cursor (reviewLog) and leaves the live
     table's own bookkeeping of what is fresh alone. */
  const log = state.review ? reviewLog(state.review) : state.log;
  if (!log || !log.entries.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  /* arrivedFrom only decides the auto-scroll target (below); glowFrom
     decides which cards get the .fresh class. In review both are the
     cursor's own freshFrom, as before -- review has one reader and no
     per-step renders to tell apart. Live, arrivedFrom keeps today's "since
     the previous render" bookkeeping, and glowFrom is the viewing seat's
     own boundary (ownGlowFrom), so a remote table's separate renders for
     each opponent step still glow every step since this seat's own last
     action, not just the last one to arrive. A spectator (no seat) has no
     "own last action", so it falls back to arrivedFrom like before. */
  let arrivedFrom = log.freshFrom;
  let glowFrom = log.freshFrom;
  if (!state.review) {
    if (logSeen.gameId !== state.gameId) {
      logSeen = { gameId: state.gameId, count: log.count, freshFrom: log.count };
    } else if (log.count !== logSeen.count) {
      logSeen.freshFrom = logSeen.count;
      logSeen.count = log.count;
    }
    arrivedFrom = logSeen.freshFrom;
    const seat = activeSeat();
    glowFrom = typeof seat === "number" ? ownGlowFrom(seat, log.entries) : arrivedFrom;
  }

  const heading = document.createElement("h2");
  heading.textContent = t("panels.log_heading");
  panel.appendChild(heading);
  const list = document.createElement("div");
  list.className = "log-list";
  /* The scroll target is picked from the groups themselves (which card
     first reaches arrivedFrom), not by re-querying the DOM for .fresh --
     that class now tracks glowFrom, which can lag behind arrivedFrom (a
     seat's own new card is never fresh to itself) or sit ahead of it (a
     remote reader catching up on several opponents' steps at once). */
  let arrivedTarget = null;
  for (const group of logGroups(log.entries)) {
    let node;
    if (group.kind === "undo") {
      node = undoRow(group.entry);
    } else if (group.kind === "neutral") {
      node = neutralCard(group, glowFrom);
      if (!arrivedTarget && group.lastIndex >= arrivedFrom) arrivedTarget = node;
    } else {
      node = group.kind === "passes" ? passesCard(group, glowFrom) : turnCard(group, glowFrom);
      if (!arrivedTarget && group.entries.some((entry) => entry.index >= arrivedFrom)) {
        arrivedTarget = node;
      }
    }
    list.appendChild(node);
  }
  panel.appendChild(list);
  /* Review drives the cursor itself, so it always shows the step it moved to. */
  if (!following && !state.review) {
    list.scrollTop = previousTop;
    return;
  }
  if (arrivedTarget) list.scrollTop = Math.max(0, arrivedTarget.offsetTop - list.offsetTop - 6);
  else list.scrollTop = list.scrollHeight;
  /* Remember this render's own offset so the next one can tell "still
     following" from "wandered off, coincidentally near the same spot".
     Review positions the cursor itself and never follows, so it neither
     reads nor writes this. */
  if (!state.review) logAutoTop = { gameId: state.gameId, top: list.scrollTop };
}

/* ---------- own hand ---------- */

function renderPrivate() {
  const panel = el("private-zone");
  panel.textContent = "";
  const view = state.view;
  if (!view || !view.private) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const own = view.players[view.player];

  const label = document.createElement("div");
  label.className = "hand-label";
  /* A review can look from a seat this browser never played (an AI's, or
     any seat of a game nobody sat at): that hand is not "mine". */
  const mine = !state.review || mySeats().includes(activeSeat());
  const title = document.createElement("strong");
  title.textContent = mine
    ? t("panels.my_hand", { seat: t("common.seat", { seat: activeSeat() }) })
    : t("panels.seat_hand", { name: playerLabel(activeSeat()) });
  label.appendChild(title);
  const revealNow = revealTurnPreview();
  if (revealNow) {
    /* Beside the hand while the seat may still choose between an Agent turn
       and a Reveal turn: what this hand is worth revealed right now. */
    const note = document.createElement("span");
    note.className = "hand-reveal-note";
    note.append(t("panels.reveal_preview_prefix"), revealPreview(revealNow));
    label.appendChild(note);
  }
  const counts = document.createElement("span");
  counts.className = "hand-counts";
  counts.append(
    statNode("draw", phraseText("{deck}"), view.private.deck_size),
    statNode("discard", phraseText("{discard_pile}"), own.discard_pile.length),
    statNode("intrigue", phraseText("{intrigue}"), view.private.intrigue_cards.length)
  );
  /* Discard piles are public (OQ-010); the owner's copy lives in the seat's
     public block like everyone else's. */
  counts.addEventListener("click", (event) => {
    event.stopPropagation();
    if (own.discard_pile.length) {
      openPileList(
        mine
          ? t("panels.my_discard")
          : t("panels.seat_discard", { seat: t("common.seat", { seat: activeSeat() }) }),
        own.discard_pile,
        counts
      );
    }
  });
  counts.classList.add("clickable");
  label.appendChild(counts);
  panel.appendChild(label);

  const zones = document.createElement("div");
  zones.className = "hand-zones";
  const hand = document.createElement("div");
  hand.className = "strip-cards hand-cards";
  if (!view.private.hand.length) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = t("panels.hand_empty");
    hand.appendChild(empty);
  }
  for (const cardId of view.private.hand) hand.appendChild(visualCard(cardId));
  zones.appendChild(hand);

  if (view.private.intrigue_cards.length) {
    const intrigue = document.createElement("div");
    intrigue.className = "strip-cards intrigue-cards";
    for (const cardId of view.private.intrigue_cards) {
      intrigue.appendChild(visualCard(cardId, { className: "intrigue" }));
    }
    zones.appendChild(intrigue);
  }
  /* Owner-only peeks: the deck's top card (Controlled, Glowglobes) and
     Kota Odax's face-down Secret Project tile. */
  const peekedIntrigue = view.private.peeked_intrigue_ids || [];
  if (
    view.private.peeked_card_id ||
    view.private.secret_project_tech_id ||
    peekedIntrigue.length
  ) {
    const peeks = document.createElement("div");
    peeks.className = "strip-cards";
    if (view.private.peeked_card_id) {
      peeks.appendChild(
        visualCard(view.private.peeked_card_id, {
          className: "small",
          badge: t("panels.deck_top_badge"),
        })
      );
    }
    for (const cardId of peekedIntrigue) {
      peeks.appendChild(
        visualCard(cardId, { className: "small", badge: t("panels.intrigue_deck_top_badge") })
      );
    }
    if (view.private.secret_project_tech_id) {
      peeks.appendChild(
        visualCard(view.private.secret_project_tech_id, {
          className: "tile",
          badge: "Secret Project (−1)",
        })
      );
    }
    zones.appendChild(peeks);
  }
  panel.appendChild(zones);
}

function renderStandings() {
  const panel = el("standings");
  const summary = state.summary;
  const review = state.review;
  /* A review hides the result it is walking towards; a watched game (nobody
     sat at it, so nobody has seen it) shows it on reaching the end. */
  const reached =
    review && spectatorOnly() && review.cursor >= review.meta.step_count;
  if ((review && !reached) || !summary.finished || !summary.standings) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  panel.textContent = "";
  const heading = document.createElement("h2");
  heading.textContent = t("panels.standings_heading");
  panel.appendChild(heading);
  /* Cells are text nodes: a row carries a player's name, and a name is
     somebody else's input. */
  const table = document.createElement("table");
  const tableRow = (tag, cells) => {
    const row = document.createElement("tr");
    for (const text of cells) {
      const cell = document.createElement(tag);
      cell.textContent = String(text);
      row.appendChild(cell);
    }
    table.appendChild(row);
    return row;
  };
  tableRow("th", [
    t("panels.standings_rank_header"),
    t("panels.standings_seat_header"),
    t("panels.standings_vp_header"),
    t("panels.standings_spice_header"),
    t("panels.standings_solari_header"),
    t("panels.standings_water_header"),
    t("panels.standings_garrison_header"),
  ]);
  for (const entry of summary.standings) {
    /* The garrison tiebreak counts a garrisoned Sardaukar Commander as a
       troop — rules/endgame.py ranks on troops_garrison + commanders_garrison
       (OQ-047, 사용자 판정 2026-09-08). Printing the troops alone showed a
       number that did not explain the order it was standing in. */
    const commanders = entry.commanders_garrison || 0;
    const row = tableRow("td", [
      entry.rank,
      playerLabel(entry.player),
      entry.victory_points,
      entry.spice,
      entry.solari,
      entry.water,
      entry.troops_garrison + commanders,
    ]);
    if (commanders) {
      row.lastChild.title = phraseText(
        `{troop} ${entry.troops_garrison} + {commander} ${commanders}`,
      );
    }
    if (entry.rank === 1) row.className = "winner";
  }
  panel.appendChild(table);

  const humans = humanSeats();
  const open = document.createElement("button");
  if (!humans.length) {
    /* While the watched game is on screen, its play button starts it over. */
    if (review) return;
    open.textContent = t("panels.watch_ai_button");
    open.addEventListener("click", watchGame);
  } else {
    open.textContent = t("panels.review_replay_button");
    open.addEventListener("click", () => {
      const seat = humans.includes(state.viewSeat)
        ? state.viewSeat
        : mySeats().length
          ? mySeats()[0]
          : humans[0];
      enterReview(seat).catch((error) => {
        showGameError(t("panels.review_start_failed", { message: error.message }));
      });
    });
  }
  panel.appendChild(open);
}
