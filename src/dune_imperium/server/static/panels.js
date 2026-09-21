"use strict";

/* ---------- seats ---------- */

function statNode(name, label, value) {
  const stat = document.createElement("span");
  stat.className = "stat";
  stat.title = label;
  stat.append(icon(name, label), String(value));
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
      badge.textContent = seatKindLabel(summary.seats[seat]);
      badge.title = summary.seats[seat];
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
    /* The Intrigue count sits with the resources: it has a printed icon,
       and taking it off the zone line keeps that line to one row. */
    stats.append(
      statNode("victory_point", phraseText("{victory_point}"), player.victory_points),
      statNode("solari", phraseText("{solari}"), player.resources.solari),
      statNode("spice", phraseText("{spice}"), player.resources.spice),
      statNode("water", phraseText("{water}"), player.resources.water),
      statNode("intrigue", phraseText("{intrigue}"), player.intrigue_card_count),
    );
    card.appendChild(stats);

    const influence = document.createElement("div");
    influence.className = "stats";
    for (const [key, label] of Object.entries(FACTION_LABELS)) {
      const stat = statNode(
        `influence_${key}`,
        phraseText(`{influence_${key}}`),
        player.influence[key],
      );
      if (player.alliance_faction_ids.includes(key)) {
        /* The Alliance token is in this seat's supply [Main p. 7]. */
        stat.classList.add("alliance");
        stat.title += phraseText(" · {alliance}");
        stat.appendChild(allianceToken(key, undefined, seat));
      }
      influence.appendChild(stat);
    }
    card.appendChild(influence);

    const forces = document.createElement("div");
    forces.className = "stats";
    /* The sword is the printed strength icon, so it carries the strength
       number; the units in the Conflict get the troop icon under a
       "Conflict" tag so they do not read as the garrison. */
    const garrison = statNode(
      "troop",
      phraseText("{garrison} {troop}"),
      player.troops_garrison,
    );
    garrison.title += phraseText(` · {supply} ${player.troops_supply}`);
    /* Sardaukar Commanders (Bloodlines): 2-strength "troops" that return to
       the supply after Combat [Bloodlines p. 4]. Garrisoned ones read as the
       board's C chip beside the troops; the ones in the supply go on the
       zone line. The old "Commander 0/1" text pushed this row onto two. */
    if (player.commanders_garrison) {
      garrison.appendChild(commanderChip(player.commanders_garrison, "{garrison}"));
    }
    forces.append(
      statNode("agent", t("panels.agent_remaining"), player.agents_available),
      garrison,
      statNode("sword", phraseText("{strength}"), player.combat_strength || 0),
      statNode("spy", t("panels.supply_spy"), player.spies_supply),
    );
    if (
      player.troops_conflict ||
      player.sandworms_conflict ||
      player.commanders_conflict ||
      player.agent_in_conflict
    ) {
      const deployed = document.createElement("span");
      deployed.className = "stat deployed";
      deployed.title = t("panels.conflict_deployed");
      deployed.append(phraseText("{conflict} "));
      if (player.troops_conflict) {
        deployed.append(icon("troop", phraseText("{troop}")), String(player.troops_conflict));
      }
      if (player.sandworms_conflict) {
        deployed.append(
          " ",
          icon("sandworm", phraseText("{sandworm}")),
          String(player.sandworms_conflict),
        );
      }
      if (player.commanders_conflict) {
        deployed.append(commanderChip(player.commanders_conflict, "{conflict}"));
      }
      if (player.agent_in_conflict) {
        deployed.append(" ", icon("agent", phraseText("{agent}")), "(Into the Fray)");
      }
      forces.appendChild(deployed);
    }
    card.appendChild(forces);

    /* Each flag is nodes (tNode), so its rule terms keep their icons; High
       Council, Swordmaster and Family Atomics are names and stay as written. */
    const flags = [];
    if (player.high_council) flags.push("High Council");
    if (player.maker_hooks) flags.push(tNode("panels.maker_hooks"));
    if (player.swordmaster_acquired) flags.push("Swordmaster");
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
    /* Immortality: specimens in the Axolotl tanks, the two Bene Tleilax
       tokens, the Family Atomics token, and the grafted-card promises. */
    if (state.summary.immortality) {
      flags.push(tNode("panels.specimen_flag", { count: player.specimens || 0 }));
      if (player.research_space) {
        /* The research token's place, named as the log names it (core.js). */
        flags.push(researchSpaceName(player.research_space, false) || player.research_space);
      }
      flags.push(tNode("panels.tleilaxu_space", { space: player.tleilaxu_space || 0 }));
      if (player.family_atomics) flags.push("Family Atomics");
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
    const supply = document.createElement("span");
    supply.append(icon("troop", phraseText("{troop}")), String(player.troops_supply));
    if (player.commanders_supply) {
      supply.appendChild(commanderChip(player.commanders_supply, "{supply}"));
    }
    seatLine(detail, phraseText("{supply}"), supply);

    const zones = document.createElement("div");
    zones.className = "zones";
    /* The last English line in the seat panel: the zone names are glossary
       terms, so phraseText gives them the same words as everywhere else. */
    /* One row: the supply (12 troops less the garrison and the Conflict)
       moved into the detail, and into the garrison's title. */
    zones.textContent = phraseText(
      `{hand} ${player.hand_size} · {deck} ${player.deck_size}` +
        ` · {discard_pile} ${player.discard_pile.length}`,
    );
    if (player.discard_pile.length) {
      zones.classList.add("clickable");
      zones.title = t("panels.discard_pile_view");
      zones.addEventListener("click", (event) => {
        event.stopPropagation();
        openPileList(`${t("common.seat", { seat })} discard`, player.discard_pile, zones);
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

/* Steps that only close a window; kept in the record but muted. */
const QUIET_ACTIONS = new Set(["finish_agent_turn", "finish_reveal", "pass"]);

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

/* Group the log into cards. A turn card holds consecutive steps by one
   seat (with only their own events) until a step closes the turn
   (finish_agent_turn, finish_reveal, pass); a Leader pick is a card of
   its own. Everything the game does by itself — the neutral events above
   and every chance step — goes into a "게임 진행" card between them, so
   the round change never reads as the last actor's move. */
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
    if (SOLO_ACTIONS.has(entry.action_id)) {
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
  if (kinds.has("endgame_started")) parts.push("Endgame");
  if (kinds.has("game_finished")) parts.push(t("common.game_over"));
  return parts.length ? parts.join(" · ") : t("panels.neutral_default");
}

function neutralCard(group, freshFrom) {
  const card = document.createElement("div");
  card.className = "turn-card neutral";
  if (group.lastIndex >= freshFrom) card.classList.add("fresh");
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

function turnCard(group, freshFrom) {
  const card = document.createElement("div");
  card.className = "turn-card";
  const color = SEAT_COLORS[group.actor];
  card.style.borderLeftColor = color;
  if (group.entries.some((entry) => entry.index >= freshFrom)) card.classList.add("fresh");
  if (group.entries.every((entry) => entry.undone)) card.classList.add("undone");

  const player = state.view && state.view.players[group.actor];
  const leaderFace = player && (player.leader_face_id || player.leader_id);
  const head = document.createElement("div");
  head.className = "turn-head";
  head.appendChild(seatToken(group.actor, "seat-mark"));
  const who = document.createElement("strong");
  who.textContent = leaderFace ? nameOf(leaderFace) : t("common.seat", { seat: group.actor });
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
    where.append(icon("agent", "Agent"), " ", targets.spaces.map(nameOf).join(", "));
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

function undoRow(entry) {
  const row = document.createElement("div");
  row.className = "turn-card undo-marker";
  row.textContent = t("panels.undo_row", { seat: entry.seat, count: entry.count });
  return row;
}

/* Entries from this index on arrived since the viewing seat last acted;
   their turn cards are marked and the list scrolls to the first one. */
let logSeen = { gameId: null, count: 0, freshFrom: 0 };

function renderLog() {
  const panel = el("action-log");
  /* The list is rebuilt from scratch, so its scroll offset has to be read
     before the panel is emptied. A reader who has scrolled up to re-read an
     earlier turn keeps their place; one already at the end keeps following
     the game. Without this the log yanked itself to the newest entry on
     every render, including renders caused by somebody else's move. */
  const previous = panel.querySelector(".log-list");
  const previousTop = previous ? previous.scrollTop : 0;
  const following =
    !previous ||
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
  let freshFrom = log.freshFrom;
  if (!state.review) {
    if (logSeen.gameId !== state.gameId) {
      logSeen = { gameId: state.gameId, count: log.count, freshFrom: log.count };
    } else if (log.count !== logSeen.count) {
      logSeen.freshFrom = logSeen.count;
      logSeen.count = log.count;
    }
    freshFrom = logSeen.freshFrom;
  }

  const heading = document.createElement("h2");
  heading.textContent = t("panels.log_heading");
  panel.appendChild(heading);
  const list = document.createElement("div");
  list.className = "log-list";
  for (const group of logGroups(log.entries)) {
    if (group.kind === "undo") list.appendChild(undoRow(group.entry));
    else if (group.kind === "neutral") list.appendChild(neutralCard(group, freshFrom));
    else list.appendChild(turnCard(group, freshFrom));
  }
  panel.appendChild(list);
  /* Review drives the cursor itself, so it always shows the step it moved to. */
  if (!following && !state.review) {
    list.scrollTop = previousTop;
    return;
  }
  const first = list.querySelector(".turn-card.fresh");
  if (first) list.scrollTop = Math.max(0, first.offsetTop - list.offsetTop - 6);
  else list.scrollTop = list.scrollHeight;
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
    statNode("draw", "deck", view.private.deck_size),
    statNode("discard", "discard", own.discard_pile.length),
    statNode("intrigue", "Intrigue", view.private.intrigue_cards.length)
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
        el("game-error").textContent = t("panels.review_start_failed", {
          message: error.message,
        });
        el("game-error").hidden = false;
      });
    });
  }
  panel.appendChild(open);
}
