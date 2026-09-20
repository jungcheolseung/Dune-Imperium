"use strict";

/* ---------- seats ---------- */

function statNode(name, label, value) {
  const stat = document.createElement("span");
  stat.className = "stat";
  stat.title = label;
  stat.append(icon(name, label), String(value));
  return stat;
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
    const seatMark = seatToken(seat, "seat-mark");
    who.appendChild(seatMark);
    const leaderName = document.createElement("span");
    leaderName.textContent = player.leader_id ? nameOf(faceId) : "Leader 미정";
    if (leaderEntry) {
      leaderName.className = "clickable";
      leaderName.addEventListener("click", (event) => {
        event.stopPropagation();
        pinPopover(leaderEntry, leaderName);
      });
      hoverPopover(leaderName, () => leaderEntry);
    }
    who.appendChild(leaderName);
    if (summary.seats[seat] === "human") {
      const badge = document.createElement("span");
      badge.className = "badge";
      const mine = isRemote() ? mySeats().includes(seat) : seat === activeSeat();
      badge.textContent = mine
        ? isRemote() && playerInfo(seat).name
          ? `YOU · ${playerInfo(seat).name}`
          : "YOU"
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
      badge.textContent = "1st";
      badge.title = "First Player";
      who.appendChild(badge);
    }
    head.appendChild(who);
    card.appendChild(head);

    const stats = document.createElement("div");
    stats.className = "stats";
    stats.append(
      statNode("victory_point", "Victory Points", player.victory_points),
      statNode("solari", "solari", player.resources.solari),
      statNode("spice", "spice", player.resources.spice),
      statNode("water", "water", player.resources.water)
    );
    card.appendChild(stats);

    const influence = document.createElement("div");
    influence.className = "stats";
    for (const [key, label] of Object.entries(FACTION_LABELS)) {
      const stat = statNode(`influence_${key}`, `${label} Influence`, player.influence[key]);
      if (player.alliance_faction_ids.includes(key)) {
        /* The Alliance token is in this seat's supply [Main p. 7]. */
        stat.classList.add("alliance");
        stat.title += " · Alliance";
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
    forces.append(
      statNode("agent", "Agents 대기", player.agents_available),
      statNode("troop", "garrison", player.troops_garrison),
      statNode("sword", "전투력", player.combat_strength || 0),
      statNode("spy", "Spy supply", player.spies_supply)
    );
    const commanders =
      (player.commanders_supply || 0) +
      (player.commanders_garrison || 0) +
      (player.commanders_conflict || 0);
    if (commanders) {
      /* Sardaukar Commanders (Bloodlines): 2-strength "troops" that return
         to the supply after Combat [Bloodlines p. 4]. */
      const mark = document.createElement("span");
      mark.className = "stat commanders";
      mark.title =
        `Sardaukar Commander · garrison ${player.commanders_garrison || 0}` +
        ` · supply ${player.commanders_supply || 0}`;
      mark.textContent =
        `Commander ${player.commanders_garrison || 0}` +
        `/${player.commanders_supply || 0}`;
      forces.appendChild(mark);
    }
    if (
      player.troops_conflict ||
      player.sandworms_conflict ||
      player.commanders_conflict ||
      player.agent_in_conflict
    ) {
      const deployed = document.createElement("span");
      deployed.className = "stat deployed";
      deployed.title = "Conflict에 배치한 유닛";
      deployed.append("Conflict ");
      if (player.troops_conflict) {
        deployed.append(icon("troop", "troop"), String(player.troops_conflict));
      }
      if (player.sandworms_conflict) {
        deployed.append(" ", icon("sandworm", "sandworm"), String(player.sandworms_conflict));
      }
      if (player.commanders_conflict) {
        deployed.append(` Commander ${player.commanders_conflict}`);
      }
      if (player.agent_in_conflict) {
        deployed.append(" ", icon("agent", "Agent"), "(Into the Fray)");
      }
      forces.appendChild(deployed);
    }
    card.appendChild(forces);

    const flags = [];
    if (player.high_council) flags.push("High Council");
    if (player.maker_hooks) flags.push("Maker Hooks");
    if (player.swordmaster_acquired) flags.push("Swordmaster");
    if (player.has_revealed) flags.push("Revealed");
    if (player.control_space_ids.length) {
      flags.push("Control: " + player.control_space_ids.map(nameOf).join("/"));
    }
    /* Bloodlines Leader state: Chani's Tactics token, Piter's Twisted deck,
       Y'rkoon's remaining Navigation slots, Kota's Secret Project tile. */
    if (player.leader_id === "chani") flags.push(`Tactics ${player.tactics_track_space + 1}칸`);
    if (player.twisted_deck_size) flags.push(`Twisted deck ${player.twisted_deck_size}`);
    if (player.navigation_remaining) flags.push(`Navigation ${player.navigation_remaining}장 남음`);
    if (player.has_secret_project) flags.push("Secret Project (face-down Tech tile)");
    if (player.spies_boxed) flags.push(`Spy ${player.spies_boxed}개 box로`);
    /* Immortality: specimens in the Axolotl tanks, the two Bene Tleilax
       tokens, the Family Atomics token, and the grafted-card promises. */
    if (state.summary.immortality) {
      flags.push(`specimen ${player.specimens || 0}`);
      if (player.research_space) flags.push(`Research ${player.research_space}`);
      flags.push(`Tleilaxu ${player.tleilaxu_space || 0}`);
      if (player.family_atomics) flags.push("Family Atomics");
      if ((player.chairdog_return_card_ids || []).length) {
        flags.push(
          "Chairdog: Reveal 시작 때 hand로 " +
            player.chairdog_return_card_ids.map(nameOf).join("/")
        );
      }
      if (player.usurped_row_card_id) {
        flags.push(`Usurp: turn 끝에 ${nameOf(player.usurped_row_card_id)} trash`);
      }
    }
    if (flags.length) seatLine(card, "상태", iconize(flags.join(" · ")));
    if (player.skill_ids && player.skill_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Skills ";
      line.appendChild(strong);
      for (const id of player.skill_ids) line.appendChild(chip(skillIdOf(id)));
      card.appendChild(line);
    }
    if (player.tech_ids && player.tech_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Tech ";
      line.appendChild(strong);
      for (const id of player.tech_ids) {
        const mark = chip(id);
        if ((player.tech_flipped || []).includes(id)) {
          mark.textContent += " (Flip됨)";
          mark.classList.add("muted");
        }
        line.appendChild(mark);
      }
      card.appendChild(line);
    }
    const agents = player.agent_locations.map(nameOf).join(", ");
    if (agents) seatLine(card, "배치", agents);

    const zones = document.createElement("div");
    zones.className = "zones";
    zones.textContent =
      `hand ${player.hand_size} · deck ${player.deck_size}` +
      ` · discard ${player.discard_pile.length} · intrigue ${player.intrigue_card_count}` +
      ` · supply ${player.troops_supply}`;
    if (player.discard_pile.length) {
      zones.classList.add("clickable");
      zones.title = "discard 더미 보기";
      zones.addEventListener("click", (event) => {
        event.stopPropagation();
        openPileList(`좌석 ${seat} discard`, player.discard_pile, zones);
      });
    }
    card.appendChild(zones);

    const battle = [...player.objective_ids, ...player.won_conflict_ids];
    if (battle.length || player.face_down_battle_card_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Battle ";
      line.appendChild(strong);
      for (const id of battle) line.appendChild(chip(id));
      for (const id of player.face_down_battle_card_ids) {
        const mark = chip(id);
        mark.textContent += " (뒤집힘)";
        mark.classList.add("muted");
        line.appendChild(mark);
      }
      card.appendChild(line);
    }
    if (player.active_contract_ids.length || player.completed_contract_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Contracts ";
      line.appendChild(strong);
      for (const id of player.active_contract_ids) line.appendChild(chip(id));
      /* Completed Contracts stay re-checkable (OQ-010): their completion
         was announced before they flipped face down. */
      for (const id of player.completed_contract_ids) {
        const mark = chip(id);
        mark.textContent += " (완료)";
        mark.classList.add("muted");
        line.appendChild(mark);
      }
      card.appendChild(line);
    }
    if (player.in_play.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "In play ";
      line.appendChild(strong);
      for (const id of player.in_play) line.appendChild(chip(id));
      card.appendChild(line);
    }
    /* Hand cards that entered through a public move (Corrinth City, an
       Intrigue "put it in your hand", a Bond return) stay known (OQ-010). */
    if (player.hand_public.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Hand (공개) ";
      line.appendChild(strong);
      for (const id of player.hand_public) line.appendChild(chip(id));
      card.appendChild(line);
    }
    if (view.intrigue_resolving.length && view.decision_owner === player.player) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = "Intrigue 해결 중 ";
      line.appendChild(strong);
      for (const id of view.intrigue_resolving) line.appendChild(chip(id));
      card.appendChild(line);
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
function logEventPayload(payload) {
  const parts = [];
  const shownNames = new Set();
  for (const [key, value] of Object.entries(payload)) {
    if (key === "player") {
      parts.push(`좌석 ${value}`);
      continue;
    }
    /* Every id-shaped field resolves through the catalog. The engine emits
       about 35 distinct ones (card_id, leader_id, tech_id, contract_id,
       skill_id, post_id, space_id, their first_/second_ variants…) and the
       old allowlist named only five, so the rest printed raw engine ids —
       leader_ids is the first log line of every Leader-draft game. */
    const isIdField = key.endsWith("_id");
    const isIdList = key.endsWith("_ids") && Array.isArray(value);
    /* Combat rewards and the like list every field; zeros say nothing. */
    if (value === 0 || value === "" || value === null || value === false) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    /* action_id has its own Korean table; everything else is a catalog name. */
    const resolve = (item) =>
      key === "action_id"
        ? phraseText(ACTION_LABELS[item] || prettify(item))
        : nameOf(item);
    const shown = isIdList
      ? value.map(resolve).join(", ")
      : isIdField
        ? resolve(value)
        : String(value);
    /* card_id and instance_id of one event resolve to the same name. */
    if (isIdField && shownNames.has(shown)) continue;
    if (isIdField) shownNames.add(shown);
    parts.push(`${prettify(key)}: ${shown}`);
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
    parts.push("게임 준비");
  }
  if (kinds.has("combat_intrigue_started")) parts.push("Combat Intrigue 창");
  if (kinds.has("conflict_won") || kinds.has("combat_reward_gained")) parts.push("전투 해결");
  if (kinds.has("agents_recalled") || kinds.has("conflict_revealed")) {
    const revealed = group.items.find(
      (item) => item.event && item.event.kind === "conflict_revealed"
    );
    const round = revealed && revealed.event.payload && revealed.event.payload.round;
    parts.push(round ? `라운드 ${round} 시작` : "라운드 시작");
  }
  if (kinds.has("endgame_started")) parts.push("Endgame");
  if (kinds.has("game_finished")) parts.push("게임 종료");
  return parts.length ? parts.join(" · ") : "게임 진행";
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
  let text = `chance: ${prettify(entry.decision_id)}`;
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
  if (entry.undone) head.append(" (되돌림)");
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
  who.textContent = leaderFace ? nameOf(leaderFace) : `좌석 ${group.actor}`;
  head.appendChild(who);
  const kind = state.summary.seats[group.actor];
  const badge = document.createElement("span");
  badge.className = kind === "human" ? "badge" : "badge ai";
  badge.textContent =
    kind === "human"
      ? group.actor === activeSeat()
        ? "YOU"
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
  row.textContent = `↩ 좌석 ${entry.seat}이(가) ${entry.count}단계 되돌림`;
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
  heading.textContent = "행동 로그";
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
    ? `내 손패 · 좌석 ${activeSeat()}`
    : `${playerLabel(activeSeat())}의 손패`;
  label.appendChild(title);
  const revealNow = revealTurnPreview();
  if (revealNow) {
    /* Beside the hand while the seat may still choose between an Agent turn
       and a Reveal turn: what this hand is worth revealed right now. */
    const note = document.createElement("span");
    note.className = "hand-reveal-note";
    note.append("지금 공개하면 ", revealPreview(revealNow));
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
      openPileList(mine ? "내 discard" : `좌석 ${activeSeat()} discard`, own.discard_pile, counts);
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
    empty.textContent = "손패 없음";
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
        visualCard(view.private.peeked_card_id, { className: "small", badge: "덱 맨 위" })
      );
    }
    for (const cardId of peekedIntrigue) {
      peeks.appendChild(
        visualCard(cardId, { className: "small", badge: "Intrigue 덱 맨 위" })
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
  heading.textContent = "최종 순위";
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
  tableRow("th", ["순위", "좌석", "VP", "Spice", "Solari", "Water", "Garrison"]);
  for (const entry of summary.standings) {
    const row = tableRow("td", [
      entry.rank,
      playerLabel(entry.player),
      entry.victory_points,
      entry.spice,
      entry.solari,
      entry.water,
      entry.troops_garrison,
    ]);
    if (entry.rank === 1) row.className = "winner";
  }
  panel.appendChild(table);

  const humans = humanSeats();
  const open = document.createElement("button");
  if (!humans.length) {
    /* While the watched game is on screen, its play button starts it over. */
    if (review) return;
    open.textContent = "AI 대국 다시 보기";
    open.addEventListener("click", watchGame);
  } else {
    open.textContent = "리플레이 검토";
    open.addEventListener("click", () => {
      const seat = humans.includes(state.viewSeat)
        ? state.viewSeat
        : mySeats().length
          ? mySeats()[0]
          : humans[0];
      enterReview(seat).catch((error) => {
        el("game-error").textContent = `검토 시작 실패 (${error.message})`;
        el("game-error").hidden = false;
      });
    });
  }
  panel.appendChild(open);
}
