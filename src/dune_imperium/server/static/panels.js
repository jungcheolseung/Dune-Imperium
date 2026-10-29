"use strict";

/* ---------- seats ---------- */

function statNode(name, label, value) {
  const stat = document.createElement("span");
  stat.className = "stat";
  stat.dataset.stat = name;
  stat.title = label;
  stat.append(
    name === "agent"
      ? agentPieceIcon(label)
      : name === "commander"
        ? commanderStatIcon(label)
        : icon(name, label),
    String(value),
  );
  return stat;
}

/* A seat's track counts for the text board (renderSeats): its Influence
   with each Faction, then its troops in the garrison and in the Conflict
   and its strength, as icons and numbers. */
function textBoardStats(player) {
  const row = document.createElement("div");
  row.className = "stats text-board-stats";
  for (const faction of Object.keys(FACTION_LABELS)) {
    const key = `influence_${faction}`;
    row.appendChild(statNode(key, phraseText(`{${key}}`), (player.influence || {})[faction] || 0));
  }
  row.append(
    statNode("troop", t("panels.garrison_troops"), player.troops_garrison || 0),
    statNode("troop", t("panels.conflict_troops"), player.troops_conflict || 0),
    statNode("sword", phraseText("{strength}"), player.combat_strength || 0),
  );
  return row;
}

/* Lady Jessica's memories: the Bene Gesserit mark and the count, so they do
   not read as troops in the supply; the title names them ("기억",
   [KO card: Lady Jessica]). An icon, not a word, since the user asked the
   rows to keep to icons (play feedback 2026-10-26). */
function memoryStat(count) {
  const stat = statNode("agent_icon_bene_gesserit", t("panels.memories_title"), count);
  stat.dataset.stat = "memory";
  return stat;
}

/* A seat's card piles as icons and counts (play feedback 2026-10-26: "글자 줄을
   아이콘으로"): the hand as two card backs, the deck as one, the discard pile
   and the Intrigue cards by their icons. Without the card back picture the
   pile's glossary word stands in. */
function pileStat(name, label, count) {
  const stat = document.createElement("span");
  stat.className = "stat pile-stat";
  stat.dataset.stat = name;
  stat.title = label;
  const back = name === "hand" || name === "deck" ? cardBackUrl("imperium") : null;
  if (back) {
    const mark = document.createElement("span");
    mark.className = `pile-mark ${name}`;
    mark.setAttribute("role", "img");
    mark.setAttribute("aria-label", label);
    for (let i = 0; i < (name === "hand" ? 2 : 1); i += 1) {
      mark.appendChild(cardBackImage(back, "pile-mark-back"));
    }
    stat.appendChild(mark);
  } else if (name === "hand" || name === "deck") {
    stat.append(`${label} `);
  } else {
    stat.appendChild(icon(name, label));
  }
  stat.append(String(count));
  return stat;
}

/* The battle icons a seat holds face up, by kind: its Objective and the
   Conflict cards it won, less the pairs already matched face down
   [Main p. 14] (play feedback 2026-10-26: the cards themselves, listed with
   "(뒤집힘)" twice over, now open from the line instead). */
function heldBattleIcons(player) {
  const faceDown = new Set(player.face_down_battle_card_ids || []);
  const counts = new Map();
  for (const id of [...player.objective_ids, ...player.won_conflict_ids]) {
    if (faceDown.has(id)) continue;
    const entry = lookup(id, id.startsWith("objective") ? "objectives" : "conflicts");
    const kind = entry && entry.icon;
    if (!kind) continue;
    counts.set(kind, (counts.get(kind) || 0) + 1);
  }
  return counts;
}

const BATTLE_ICON_ORDER = ["desert_mouse", "crysknife", "ornithopter", "wild"];

/* A seat's Skill or Tech tile or open Contract as a small picture at its
   real height (style.css --thumb-mm): hover enlarges it and a click pins
   it, as a chip does. A flipped Tech tile is dimmed and
   says so in its title. Without the picture the chip stands in. */
function tileThumb(id, kind, flipped = false) {
  const entry = entryOf(id, kind);
  const suffix = flipped ? t("panels.flip_suffix") : "";
  if (!entry || !entry.image) {
    const tag = chip(id, kind);
    if (flipped) {
      tag.textContent += suffix;
      tag.classList.add("muted");
    }
    return tag;
  }
  const image = document.createElement("img");
  image.className = `tile-thumb ${kind}` + (flipped ? " flipped" : "");
  image.src = entry.image;
  image.alt = entry.name + suffix;
  image.title = entry.name + suffix;
  image.draggable = false;
  image.dataset.tile = id;
  image.addEventListener("click", (event) => {
    event.stopPropagation();
    pinPopover(entry, image);
  });
  hoverPopover(image, () => entry);
  return image;
}

/* A stat that opens a card list: a button for the mouse and the keyboard
   (Enter or Space), its title and accessible name saying what it opens.
   Escape closes the list (app.js). */
function openerStat(stat, label, open) {
  stat.classList.add("clickable");
  stat.tabIndex = 0;
  stat.setAttribute("role", "button");
  stat.setAttribute("aria-haspopup", "true");
  stat.title = label;
  stat.setAttribute("aria-label", label);
  stat.addEventListener("click", (event) => {
    event.stopPropagation();
    open();
  });
  stat.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    open();
  });
}

/* A Sardaukar Commander as the board draws one (unitPiece): the rulebook's
   neutral figure (catalog.commander_token), or without the picture the drawn
   mark in the plastic's grey (.commander-piece.drawn). The rule term has
   no icon of its own (TERMS.commander), so the piece itself is the icon. */
function commanderStatIcon(label) {
  const picture = state.catalog && state.catalog.commander_token;
  if (picture) {
    const img = document.createElement("img");
    img.className = "icon commander-stat-icon";
    img.src = picture;
    img.alt = label;
    img.title = label;
    img.draggable = false;
    return img;
  }
  const mark = document.createElement("span");
  mark.className = "commander-stat-icon drawn";
  mark.textContent = "C";
  mark.title = label;
  mark.setAttribute("role", "img");
  mark.setAttribute("aria-label", label);
  return mark;
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

/* One in-play card's chip. The card the open Agent turn played, or its
   graft partner, carries a "this turn" mark (server view.turn_card_ids,
   sessions.py turn_cards), so it reads apart from a copy of the same card
   played on an earlier turn; while its Agent box still waits
   (view.pending_box_card_ids) the mark's title says trashing it by another
   effect loses the rest of that box (OQ-022, user feedback 2026-10-11; a
   card trashing itself by its own effect keeps its rewards). The mark is no
   .tag, so a line still holds one chip per card, and the chip keeps its own
   hover and click. */
function inPlayChip(id, view) {
  const tag = chip(id);
  if (!(view.turn_card_ids || []).includes(id)) return tag;
  const pending = (view.pending_box_card_ids || []).includes(id);
  tag.classList.add("this-turn");
  if (pending) tag.classList.add("box-pending");
  const mark = document.createElement("span");
  mark.className = "this-turn-mark";
  mark.textContent = t("panels.this_turn_badge");
  mark.title = pending ? t("panels.this_turn_pending_title") : t("panels.this_turn_title");
  tag.appendChild(mark);
  return tag;
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
    const leaderEntry = faceId ? lookup(faceId, "leaders") : null;
    if (leaderEntry && leaderEntry.image) {
      const image = document.createElement("img");
      image.className = "leader-thumb";
      image.src = leaderEntry.image;
      image.alt = leaderEntry.name;
      image.addEventListener("click", (event) => {
        event.stopPropagation();
        pinPopover(leaderEntry, image, player);
      });
      hoverPopover(image, () => leaderEntry, () => player);
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
    leaderName.textContent = player.leader_id
      ? (leaderEntry ? leaderEntry.name : prettify(faceId))
      : t("panels.leader_unset");
    /* A cut-short name reads whole in the hover card, or in the title. */
    if (!leaderEntry) leaderName.title = leaderName.textContent;
    if (leaderEntry) {
      leaderName.classList.add("clickable");
      leaderName.addEventListener("click", (event) => {
        event.stopPropagation();
        pinPopover(leaderEntry, leaderName, player);
      });
      hoverPopover(leaderName, () => leaderEntry, () => player);
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
      const kind = summary.seats[seat];
      /* A search seat answers on the server's worker after the request that
         handed it the turn has returned (summary.thinking), and its badge
         says so meanwhile, in the badge's own place: a mark beside it cut
         the Leader name to a few pixels at 1366x768 and took a third line
         in the wider column. The tooltip keeps the kind. */
      const thinking = !state.review && summary.thinking === seat;
      badge.className = thinking ? "badge ai thinking" : "badge ai";
      badge.textContent = thinking ? t("panels.thinking") : seatKindLabel(kind);
      /* The label hides a checkpoint's path; its tooltip names the file. A
         search seat's file is the server's own and stays out of sight. */
      badge.title = kind.startsWith("checkpoint:")
        ? kind.slice("checkpoint:".length)
        : seatKindLabel(kind);
      who.appendChild(badge);
    }
    /* A review step shows who held the marker at that step. */
    const firstPlayer = state.review ? view.first_player : summary.first_player;
    if (firstPlayer === seat) who.appendChild(firstPlayerMark());
    head.appendChild(who);
    card.appendChild(head);

    const stats = document.createElement("div");
    stats.className = "stats";
    /* The Victory Points open how they were scored (vpLedgerContent). */
    const points = statNode(
      "victory_point",
      phraseText("{victory_point}"),
      player.victory_points,
    );
    if (vpLedgerReadable()) {
      const pointsOpener = `seat-vp:${seat}`;
      points.dataset.pileOpener = pointsOpener;
      openerStat(points, t("panels.vp_ledger_open", { points: player.victory_points }), () =>
        togglePileViewer({ kind: "vp", seat, opener: pointsOpener }, points)
      );
    }
    /* Counts that are not already visible on a board track stay at a glance.
       Spice before Solari (user, 2026-10-11: "스파이스/솔라리/물 순으로").
       Immortality p. 16 names the green cube as the Specimen icon. */
    stats.append(
      points,
      statNode("spice", phraseText("{spice}"), player.resources.spice),
      statNode("solari", phraseText("{solari}"), player.resources.solari),
      statNode("water", phraseText("{water}"), player.resources.water),
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
    if (player.track_spies_owed > 0) {
      const owed = document.createElement("span");
      owed.className = "stat";
      owed.appendChild(tNode("panels.track_spies_owed", { count: player.track_spies_owed }));
      pieces.appendChild(owed);
    }
    /* Commanders in the supply: the board draws the ones in the garrison
       and the Conflict, but nothing on it shows the ones that went home
       after a Combat [Bloodlines p. 4], and the supply is public
       [Main p. 5]. Always shown in a Bloodlines game, 0 included, like the
       Specimens above. */
    if (summary.bloodlines) {
      pieces.appendChild(
        statNode("commander", t("panels.supply_commander"), player.commanders_supply || 0),
      );
    }
    /* Lady Jessica's memories: the troops Spice Agony moved to the Bene
       Gesserit board area [Lady Jessica card]. Nothing on the board draws
       them, and the count is public. Shown on her Lady Jessica face, 0
       included, and on any seat that still holds one. */
    if (player.leader_face_id === "lady_jessica" || player.memories > 0) {
      pieces.appendChild(memoryStat(player.memories || 0));
    }
    /* The seat's time holding control, ticking on its own (clock.js). */
    if (clocksShown()) pieces.appendChild(seatClockNode(seat));
    card.appendChild(pieces);
    /* Without a board scan (the text board: no local scan, or the original
       game before its board layout), nothing else shows the counts the
       board's tracks would: Influence on each strip, the garrison, the
       troops in the Conflict and the strength. */
    if (!boardDrawsTracks(view)) card.appendChild(textBoardStats(player));

    /* Each flag is nodes (tNode), so its rule terms keep their icons. The
       Swordmaster is the glossary's 소드마스터; only the board space of that
       name stays English. The High Council seat, the Maker Hooks and the
       Control markers are drawn on the board, and so are the Agents on their
       spaces: the panel no longer repeats them (play feedback 2026-10-26). */
    const flags = [];
    if (player.swordmaster_acquired) flags.push(tNode("panels.swordmaster"));
    /* The original game's Mentat, where the screen puts it (mentatSpace). */
    if (player.mentat) {
      const space = mentatSpace(player);
      flags.push(
        tNode("panels.mentat_at", {
          where: space ? spaceName(space) : t("panels.mentat_on_leader"),
        })
      );
    }
    /* The Sort Through the Chaos winner takes the Mentat at the next
       round's start [FAQ p. 4] (view.mentat_owed_to, public). */
    if (view.mentat_owed_to === seat) flags.push(tNode("panels.mentat_next_round"));
    for (const flag of originalMarkers(player, seat, view)) flags.push(flag);
    for (const flag of ixMarkers(player, seat, view)) flags.push(flag);
    for (const flag of knownIntrigueMarkers(seat, view)) flags.push(flag);
    if (player.has_revealed) flags.push(tNode("panels.revealed"));
    /* Bloodlines Leader state: Piter's Twisted deck. Chani's Tactics space,
       Y'rkoon's Navigation cards and Kota's Secret Project tile are drawn
       on the leader popover (core.js openPopover, with a text fallback
       without card images), so this line does not repeat them. */
    if (player.twisted_deck_size) {
      flags.push(tNode("panels.twisted_deck", { count: player.twisted_deck_size }));
    }
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
    /* The card lines below the counts. They used to fold away behind
       "자세히 ▸", whose summary listed every line in words; the user would
       rather see them always (play feedback 2026-10-26), and the lines the
       board already draws are gone. */
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
    /* The Skill and Tech tiles as small pictures, no label: their names
       alone did not say which tile was which, so the player hovered each
       one (play feedback 2026-10-26). */
    const skills = (player.skill_ids || []).map((id) => tileThumb(skillIdOf(id), "skills"));
    const tech = (player.tech_ids || []).map((id) =>
      tileThumb(id, "tech", (player.tech_flipped || []).includes(id))
    );
    if (skills.length || tech.length) {
      const line = document.createElement("div");
      line.className = "cardline tile-line";
      for (const [labelKey, thumbs] of [
        ["panels.skills_label", skills],
        ["panels.tech_label", tech],
      ]) {
        if (!thumbs.length) continue;
        const group = document.createElement("span");
        group.className = "tile-group";
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", t(labelKey));
        group.append(...thumbs);
        line.appendChild(group);
      }
      detail.appendChild(line);
    }
    /* The seat's cards: hand, deck, discard pile and Intrigue cards, as
       icons and counts (pileStat; the Intrigue count used to sit in the
       resources row as well as in a line of words). */
    const zones = document.createElement("div");
    zones.className = "zones stats";
    zones.append(
      pileStat("hand", phraseText("{hand}"), player.hand_size),
      pileStat("deck", phraseText("{deck}"), player.deck_size),
      pileStat("discard", phraseText("{discard_pile}"), player.discard_pile.length),
      pileStat("intrigue", phraseText("{intrigue}"), player.intrigue_card_count),
    );
    /* The zones line opens the seat's public lists: the deck pool (the
       draw deck and the hidden part of the hand together, OQ-010 ruling 6),
       the hand cards that entered it publicly (hand_public) and the discard
       pile. The hand strip's own discard count opens the discard pile alone,
       so only this opener asks for the pool. */
    if (
      (player.deck_pool || []).length ||
      (player.hand_public || []).length ||
      player.discard_pile.length
    ) {
      zones.classList.add("clickable");
      zones.title = t("panels.seat_piles_view");
      /* Same "mine" test as this seat panel's own "you" badge above, with a
         review guard added to the local branch: on a remote table
         ownership follows the seats this browser claimed regardless of what
         is being viewed; locally (live or reviewed) it follows the seat
         being looked at, but only when reviewing a seat this browser
         actually played -- an all-AI review must never call an AI's pile
         "my discard" just because it is the one on screen. */
      const mine = isRemote()
        ? mySeats().includes(seat)
        : seat === activeSeat() && (!state.review || mySeats().includes(seat));
      const opener = `seat-discard:${seat}`;
      zones.dataset.pileOpener = opener;
      zones.addEventListener("click", (event) => {
        event.stopPropagation();
        togglePileViewer({ kind: "discard", seat, mine, opener, pool: true }, zones);
      });
    }
    card.appendChild(zones);

    /* Intrigue cards played but kept face up in front of their owner until a
       later moment (Call to Arms, a Reveal-turn Plot; FAQ p. 2) are public,
       so every seat shows them. They stay outside the fold below: the line
       is rare and short-lived, and the other seats must see what is pending. */
    const faceupIntrigue = player.intrigue_faceup || [];
    if (faceupIntrigue.length) {
      const line = document.createElement("div");
      line.className = "cardline faceup-intrigue";
      const strong = document.createElement("strong");
      strong.textContent = t("panels.intrigue_faceup_label");
      line.appendChild(strong);
      for (const id of faceupIntrigue) line.appendChild(chip(id));
      card.appendChild(line);
    }

    /* The battle icons held face up, icons alone (play feedback
       2026-10-26), and at the line's end the seat's details: what the
       panel leaves out but a player looks up now and then -- the cards
       behind those icons, matched pairs included, the completed Contracts
       and what the seat trashed ("자세히 보기를 다시 만들고"). */
    const battleLine = document.createElement("div");
    battleLine.className = "cardline battle-line";
    const icons = document.createElement("span");
    icons.className = "battle-icons";
    icons.setAttribute("role", "group");
    icons.setAttribute("aria-label", t("panels.battle_label"));
    const held = heldBattleIcons(player);
    for (const kind of BATTLE_ICON_ORDER) {
      const count = held.get(kind);
      if (!count) continue;
      const mark = statNode(`battle_${kind}`, termLabel(`battle_${kind}`), count);
      mark.dataset.stat = `battle:${kind}`;
      icons.appendChild(mark);
    }
    const details = document.createElement("button");
    details.type = "button";
    details.className = "seat-details";
    details.textContent = t("panels.seat_details_open");
    const detailsOpener = `seat-details:${seat}`;
    details.dataset.pileOpener = detailsOpener;
    details.title = t("panels.seat_details_title");
    details.addEventListener("click", (event) => {
      event.stopPropagation();
      togglePileViewer({ kind: "details", seat, opener: detailsOpener }, details);
    });
    battleLine.append(icons, details);
    /* First of the lines, beside the counts it reads like. */
    detail.prepend(battleLine);
    /* The open Contracts as small pictures too ("아직 완료 전인 계약도
       텍스트 말고 그냥 이미지로", play feedback 2026-10-26); the completed
       ones are in the seat's details, still re-checkable (OQ-010). */
    if (player.active_contract_ids.length) {
      const line = document.createElement("div");
      line.className = "cardline tile-line";
      const group = document.createElement("span");
      group.className = "tile-group";
      group.setAttribute("role", "group");
      group.setAttribute("aria-label", t("panels.contracts_label"));
      for (const id of player.active_contract_ids) {
        const holder = document.createElement("span");
        holder.className = "contract-thumb";
        holder.dataset.contract = id;
        holder.appendChild(tileThumb(id, "contracts"));
        /* CHOAM Escort's goods wait on the Contract until it is completed. */
        const tray = scoutsTray(`contract:${id}`, view);
        if (tray) holder.appendChild(tray);
        group.appendChild(holder);
      }
      line.appendChild(group);
      detail.appendChild(line);
    }
    if (player.in_play.length) {
      const line = document.createElement("div");
      line.className = "cardline";
      const strong = document.createElement("strong");
      strong.textContent = `${t("panels.in_play_label")} `;
      line.appendChild(strong);
      for (const id of player.in_play) line.appendChild(inPlayChip(id, view));
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
    /* Cards put face up on top of the deck (Bypass Protocol, Recruitment
       Mission, a Tleilaxu card) are known to every seat until drawn or
       shuffled, top first (OQ-145, core/observation.py). */
    if ((player.deck_public_top || []).length) {
      const line = document.createElement("div");
      line.className = "cardline deck-public-top";
      const strong = document.createElement("strong");
      strong.textContent = t("panels.deck_public_top_label");
      line.appendChild(strong);
      for (const id of player.deck_public_top) line.appendChild(chip(id));
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
    if (detail.children.length) card.appendChild(detail);
    wrap.appendChild(card);
  }
  // A pinned leader popover otherwise stays open exactly as it was through
  // a foreign update (render.js's `render()` only closes a pinned popover
  // on a local one) -- fine for a card's fixed text, but this popover draws
  // the seat's own live state, which the update may have just changed;
  // redraw it (core.js) against the seat panel this call just rebuilt.
  refreshPinnedLeaderPopover();
  paintClocks();
}

/* A Skill tile instance ("skill:<id>:<copy>") to its catalog id. */
function skillIdOf(instanceId) {
  const match = String(instanceId).match(/^skill:(.+):\d+$/);
  return match ? match[1] : String(instanceId);
}

/* ---------- the pile viewer ---------- */

/* A pile's cards in a window of their own, #pile-viewer (index.html): a
   seat's discard pile, the Intrigue discard pile or the owner's draw deck.
   The lists used to be drawn into the card popover, where a card's hover
   enlargement replaced them: the enlargement ignores the pointer, so the
   card under it on the table took the pointer and its own enlargement took
   the popover, and render() closed the list on every update, anyone's move
   included (user feedback after a remote game, 2026-10-11). Now a card in
   the viewer shows enlarged in the card popover above it, and the viewer
   stays open until its ×, Escape or a second click on its opener closes
   it; a click elsewhere on the page leaves it open.

   It remembers which pile it shows, never the cards: `pileViewerKey` is
   `{kind, seat, mine, opener, scene}`, with kind "discard" (a seat's),
   "intrigue_discard", "deck" (the seat's own) or "vp" (a seat's Victory
   Point ledger, which is no pile: vpLedgerContent); the seat it belongs to
   (null for the Intrigue discard); `mine`, the opener's own "my pile" test
   that picks the title; `opener`, the name in its opener's
   `data-pile-opener`, so a second click there closes it; and the table it
   was opened on (pileViewerScene). Every render draws it again from the
   fresh state (refreshPileViewer) and closes it when the pile is empty or
   gone or the table is another one. */
let pileViewerKey = null;
const PILE_VIEWER_WIDTH = 420;

/* The table a pile was opened on: the game, the seat looked from and, in a
   review, the step on screen (the openers read the reviewed view). Leaving
   the game, switching seats or moving the review cursor closes the
   viewer. The Victory Point ledger is the exception: what it shows is public
   and belongs to the seat it was opened for, so it stays open for the
   whole game and follows the review cursor (vpLedgerContent). */
function pileViewerScene() {
  return {
    game: state.gameId,
    seat: activeSeat(),
    cursor: state.review ? state.review.cursor : null,
  };
}

function pileViewerOpen() {
  return pileViewerKey !== null;
}

/* An opener's click: its pile in the viewer, or, when the viewer already
   shows what this same opener put there, the viewer closed (with a card
   popover pinned from it: the opener's click stops at the opener, before
   the document's click-elsewhere close). Another opener's pile replaces
   the contents and moves the viewer to it. */
function togglePileViewer(key, anchor) {
  if (pileViewerKey && pileViewerKey.opener === key.opener) {
    closePopover();
    closePileViewer();
    return;
  }
  openPileViewer(key, anchor);
}

function openPileViewer(key, anchor) {
  const content = pileViewerContent(key);
  if (!content) return;
  /* A card popover, pinned or not, gives way: it would lie over the list,
     and the opener's click stops at the opener, before the document's
     click-elsewhere close. */
  closePopover();
  pileViewerKey = { ...key, scene: pileViewerScene() };
  const viewer = el("pile-viewer");
  fillPileViewer(content);
  el("pile-viewer-body").scrollTop = 0;
  /* Below the opener, or above it when it would run off the bottom; then
     inside the window, for an opener the table has scrolled partly out of
     it (a narrow window scrolls the table sideways). */
  const place = () => {
    placePopover(viewer, anchor, PILE_VIEWER_WIDTH);
    keepPileViewerInWindow();
  };
  place();
  /* Card images arrive after the first placement and make the list taller
     (openPopover does the same). Once the table has re-rendered the anchor
     is gone and placePopover only pulls the viewer back inside. */
  placePileViewerOnImages(place);
}

/* Focus inside the viewer goes back to its opener, when that can take it
   (the seat panel's zone line cannot). */
function closePileViewer() {
  const viewer = el("pile-viewer");
  const opener = pileViewerKey ? pileViewerKey.opener : null;
  const focused = viewer.contains(document.activeElement);
  pileViewerKey = null;
  viewer.hidden = true;
  el("pile-viewer-body").textContent = "";
  if (focused && opener) {
    const node = document.querySelector(`[data-pile-opener="${opener}"]`);
    if (node) node.focus();
  }
}

/* After every render: the open pile drawn again from the fresh state where
   the viewer stands, its scroll and a focused card kept; closed when the
   pile is empty or gone or the table is another one. */
function refreshPileViewer() {
  const key = pileViewerKey;
  if (!key) return;
  const scene = pileViewerScene();
  const same =
    !el("game-screen").hidden &&
    scene.game === key.scene.game &&
    (key.kind === "vp" ||
      (scene.seat === key.scene.seat && scene.cursor === key.scene.cursor));
  const content = same ? pileViewerContent(key) : null;
  if (!content) {
    closePileViewer();
    return;
  }
  const viewer = el("pile-viewer");
  const body = el("pile-viewer-body");
  const scroll = body.scrollTop;
  const active = document.activeElement;
  const focused =
    active && body.contains(active) && active.dataset ? active.dataset.instance : null;
  const focusedRow =
    active && body.contains(active) && active.dataset ? active.dataset.ledgerRow : null;
  fillPileViewer(content);
  body.scrollTop = scroll;
  keepPileViewerInWindow();
  placePileViewerOnImages(keepPileViewerInWindow);
  if (focused) {
    const card = [...body.querySelectorAll(".vcard")].find(
      (node) => node.dataset.instance === focused,
    );
    if (card) card.focus();
  }
  if (focusedRow) {
    const row = body.querySelector(`[data-ledger-row="${focusedRow}"]`);
    if (row) row.focus();
  }
}

/* The viewer where it stands, pulled back inside the window when new
   contents or a smaller window would leave it running off. */
function keepPileViewerInWindow() {
  const viewer = el("pile-viewer");
  if (viewer.hidden) return;
  const width = Math.min(PILE_VIEWER_WIDTH, window.innerWidth - 16);
  viewer.style.width = `${width}px`;
  const left = parseFloat(viewer.style.left) || 8;
  viewer.style.left = `${Math.max(8, Math.min(left, window.innerWidth - width - 8))}px`;
  const top = parseFloat(viewer.style.top) || 8;
  const lowest = window.innerHeight - viewer.offsetHeight - 8;
  viewer.style.top = `${Math.max(8, Math.min(top, lowest))}px`;
}

/* `place` again as each card image still loading arrives, while it is
   this viewer's image. */
function placePileViewerOnImages(place) {
  const viewer = el("pile-viewer");
  for (const image of viewer.querySelectorAll("img")) {
    if (image.complete) continue;
    image.addEventListener(
      "load",
      () => {
        if (image.isConnected && !viewer.hidden) place();
      },
      { once: true },
    );
  }
}

/* `content.sections`: `[{title, notes, cards}]`. The first title is the
   viewer's own, its accessible name beside the ×; a later section is
   headed inside, above its cards. A section with a `body` node (the
   Victory Point ledger's list) shows that in place of a card strip. */
function fillPileViewer(content) {
  const body = el("pile-viewer-body");
  body.textContent = "";
  content.sections.forEach((section, index) => {
    if (index) {
      const head = document.createElement("div");
      head.className = "popover-title";
      head.textContent = section.title;
      body.appendChild(head);
    } else {
      el("pile-viewer-title").textContent = section.title;
    }
    if (section.body) {
      body.append(...(section.notes || []), section.body);
      return;
    }
    /* A title alone (the seat details' own heading) or an empty group. */
    if (!section.cards || !section.cards.length) {
      body.append(...(section.notes || []));
      return;
    }
    const row = document.createElement("div");
    row.className = "strip-cards wrap";
    row.append(...section.cards);
    body.append(...(section.notes || []), row);
  });
}

/* What a key shows in the current state, or null when there is nothing to
   show. The openers read the same fields: a seat's public discard pile
   (and, for a seat panel's key with `pool`, its public deck pool and its
   publicly entered hand cards before it), the Intrigue discard (newest
   first) and the seat's own deck_cards. */
function pileViewerContent(key) {
  const view = state.view;
  if (!view) return null;
  if (key.kind === "vp") return vpLedgerContent(key, view);
  if (key.kind === "deck") return deckListContent(key, view);
  if (key.kind === "details") return seatDetailsContent(key, view);
  if (key.kind === "intrigue_discard") {
    const ids = [...(view.intrigue_discard || [])].reverse();
    return pileListContent([[t("board.pile_intrigue_discard"), ids]]);
  }
  const player = view.players.find((p) => p.player === key.seat);
  const title = key.mine
    ? t("panels.my_discard")
    : t("panels.seat_discard", { seat: t("common.seat", { seat: key.seat }) });
  const discard = pileListContent([[title, player ? player.discard_pile : []]]);
  if (!key.pool) return discard;
  const sections = [];
  const pool = deckPoolSection(key, player ? player.deck_pool || [] : []);
  if (pool) sections.push(pool);
  /* A card acquired straight to the hand (Price is No Object, Corrinth
     City, a Bond return) is public there (hand_public, OQ-010) and so not
     in the pool; without this section the viewer lost it until it left
     the hand (user report 2026-10-19). */
  const handPublic = player ? player.hand_public || [] : [];
  if (handPublic.length) {
    const handTitle = key.mine
      ? t("panels.my_hand_public", { count: handPublic.length })
      : t("panels.seat_hand_public", {
          seat: t("common.seat", { seat: key.seat }),
          count: handPublic.length,
        });
    sections.push({
      title: handTitle,
      cards: handPublic.map((id) => visualCard(id, { className: "small" })),
    });
  }
  if (discard) sections.push(...discard.sections);
  return sections.length ? { sections } : null;
}

/* A card in the seat's details, which only show: a click pins its
   enlargement, and it neither lights as a legal choice nor dims as an
   unavailable one (a won Conflict card can be one to flip, and a trashed
   Skill copy shares its name with the copy still in play). */
function detailsCard(id, options) {
  const card = visualCard(id, {
    ...options,
    onClick: (entry, node) => {
      if (entry) pinPopover(entry, node);
    },
  });
  card.classList.remove("legal", "blocked", "picked", "partner", "alternative");
  const entry = options.entry || entryOf(id);
  card.title = entry ? entry.name : nameOf(id);
  return card;
}

/* A seat's details (the battle line's "자세히" button, play feedback
   2026-10-26): its Objective and the Conflict cards it won, the matched
   pairs marked face down [Main p. 14]; its completed Contracts; the cards
   it trashed; and the Skill and Tech tiles it trashed (sessions.py
   `_trashed_tiles`, a Skill by its copy). The trashed cards are the ones in
   the box: a trashed Reserve card goes back to its Reserve stack
   [Main p. 20], so it is not among them. Each group of the game's modules
   is listed, an empty one as "없음". */
function seatDetailsContent(key, view) {
  const player = view.players.find((p) => p.player === key.seat);
  if (!player) return null;
  const summary = state.summary || {};
  const faceDown = new Set(player.face_down_battle_card_ids || []);
  const groups = [
    [
      "panels.details_battle",
      [...player.objective_ids, ...player.won_conflict_ids].map((id) =>
        detailsCard(id, {
          className: faceDown.has(id) ? "real-small-card face-down" : "real-small-card",
          entry: lookup(id, id.startsWith("objective") ? "objectives" : "conflicts"),
          badge: faceDown.has(id) ? t("panels.battle_card_matched") : undefined,
        })
      ),
    ],
  ];
  if (summary.choam_module) {
    groups.push([
      "panels.details_contracts",
      player.completed_contract_ids.map((id) =>
        detailsCard(id, { className: "real-contract" })
      ),
    ]);
  }
  groups.push([
    "panels.details_trashed_cards",
    (player.trashed || []).map((id) => detailsCard(id, { className: "real-card" })),
  ]);
  if (summary.bloodlines) {
    groups.push([
      "panels.details_trashed_skills",
      (player.trashed_skill_ids || []).map((id) =>
        detailsCard(id, { className: "real-skill", entry: lookup(skillIdOf(id), "skills") })
      ),
    ]);
  }
  if (summary.tech_module) {
    groups.push([
      "panels.details_trashed_tech",
      (player.trashed_tech_ids || []).map((id) =>
        detailsCard(id, { className: "real-tech", entry: lookup(id, "tech") })
      ),
    ]);
  }
  const sections = [
    { title: t("panels.seat_details_viewer", { name: seatLeaderName(key.seat) }) },
  ];
  for (const [textKey, cards] of groups) {
    const section = { title: t(textKey, { count: cards.length }), cards };
    if (!cards.length) {
      const none = document.createElement("div");
      none.className = "popover-note muted";
      none.textContent = t("panels.details_none");
      section.notes = [none];
    }
    sections.push(section);
  }
  return { sections };
}

/* A seat's deck pool as a viewer section: the cards of its draw deck and of
   the hidden part of its hand, together, by card id (`deck_pool`: plain ids
   sorted by id, one entry per copy; OQ-010 ruling 6, user decision
   2026-10-13). Which of them is in the deck and which in the hand stays
   hidden, so this groups copies of one card (x N) and sorts the groups by
   the name on screen like deckListContent, and shows no instance ids. A
   click on a card only pins its enlargement. Null for an empty pool. */
function deckPoolSection(key, ids) {
  if (!ids.length) return null;
  const title = key.mine
    ? t("panels.my_deck_pool", { count: ids.length })
    : t("panels.seat_deck_pool", {
        seat: t("common.seat", { seat: key.seat }),
        count: ids.length,
      });
  const groups = new Map();
  for (const id of ids) {
    if (!groups.has(id)) {
      const entry = lookup(id, "cards");
      groups.set(id, { id, count: 0, entry, name: entry ? entry.name : prettify(id) });
    }
    groups.get(id).count += 1;
  }
  const locale = TERM_LANGUAGE === "ko" ? "ko" : "en";
  const sorted = [...groups.values()].sort(
    (a, b) => a.name.localeCompare(b.name, locale) || (a.id < b.id ? -1 : 1),
  );
  const note = document.createElement("div");
  note.className = "popover-note";
  note.textContent = t("panels.deck_pool_note");
  const pin = (entry, card) => {
    if (entry) pinPopover(entry, card);
  };
  const cards = sorted.map((group) => {
    const copies = group.count > 1 ? `×${group.count}` : "";
    return visualCard(group.id, {
      entry: group.entry || undefined,
      className: "small",
      badge: copies,
      title: copies ? `${group.name} ${copies}` : group.name,
      onClick: pin,
    });
  });
  return { title, notes: [note], cards };
}

/* A pile listing (discard, Intrigue piles): one pile, or several as
   `[[title, ids], ...]` with the empty ones left out, each titled with its
   count. */
function pileListContent(piles) {
  const shown = piles.length > 1 ? piles.filter(([, ids]) => ids.length) : piles;
  if (!shown.length || !shown[0][1].length) return null;
  return {
    sections: shown.map(([title, ids]) => ({
      title: `${title} (${ids.length})`,
      cards: ids.map((id) => visualCard(id, { className: "small" })),
    })),
  };
}

/* The deck list's cards and its marked top card, as the hand strip's deck
   count reads them: `deck_cards` (sorted by card id, OQ-010 ruling 5) and
   the top card only when `peeked_card_id` names one of them (Glowglobes or
   the original Paul Atreides' Prescience at any time, Controlled while its
   choice is up; core/observation.py), with the name of what shows it -- or,
   with no such peek, a card put face up on top of the deck, which every
   seat knows (`deck_public_top`, OQ-145; `source` is then null). */
function deckListState(view) {
  const own = view.players[view.player];
  const deckCards = view.private.deck_cards || [];
  const peeked = view.private.peeked_card_id || "";
  const glowglobes = (own.tech_ids || []).includes("glowglobes");
  const publicTop = (own.deck_public_top || [])[0] || "";
  const top = peeked && deckCards.includes(peeked)
    ? { id: peeked, source: deckTopSource(glowglobes, own.leader_id) }
    : publicTop && deckCards.includes(publicTop)
      ? { id: publicTop, source: null }
      : null;
  return { deckCards, top };
}

/* The owner's draw deck as a pile list: which cards and how many copies,
   never in what order. The server sends `deck_cards` sorted by card id
   (sessions.py `_serialize_view`); this groups copies of one card (x N) and
   sorts the groups by the name on screen, so the list is a function of the
   deck's contents alone and shows no trace of the draw order (OQ-010
   ruling 5). A click on a card here only pins its enlargement: a deck card
   is never something to act on from a list.

   The one exception is the top card when a card effect lets the owner see
   it (`top`: `{id, source}`, the view's own `peeked_card_id` and the name
   of what shows it -- Glowglobes, or Controlled while its choice is up).
   That one copy is split off as its own entry, badged "Top" ("맨 위") and
   outlined, right before the rest of the same card, which keep their group
   ("×2", or no count for one copy left); a card with a single copy is just
   that entry. A second note says where the mark comes from. The groups'
   name order is as before and each remaining group's card is its smallest
   instance id, so the list still says nothing about the cards below the
   top (user decision 2026-10-10). */
function deckListContent(key, view) {
  if (!view.private) return null;
  const { deckCards: ids, top } = deckListState(view);
  if (!ids.length) return null;
  const title = key.mine
    ? t("panels.my_deck", { count: ids.length })
    : t("panels.seat_deck", {
        seat: t("common.seat", { seat: key.seat }),
        count: ids.length,
      });
  const groupKey = (id) => {
    const ref = instanceRef(id);
    return `${ref.kind}:${ref.id}`;
  };
  const topId = top && top.id && ids.includes(top.id) ? top.id : "";
  const groups = new Map();
  for (const id of ids) {
    const key = groupKey(id);
    const group = groups.get(key) || { key, ids: [], name: nameOf(id) };
    group.ids.push(id);
    groups.set(key, group);
  }
  const locale = TERM_LANGUAGE === "ko" ? "ko" : "en";
  const first = (list) => list.reduce((low, id) => (id < low ? id : low));
  const sorted = [...groups.values()].sort(
    (a, b) => a.name.localeCompare(b.name, locale) || (first(a.ids) < first(b.ids) ? -1 : 1),
  );
  /* One entry per group, the top copy split off before its group. */
  const entries = [];
  for (const group of sorted) {
    const rest = group.ids.filter((id) => id !== topId);
    if (rest.length < group.ids.length) entries.push({ id: topId, name: group.name, top: true });
    if (rest.length) entries.push({ id: first(rest), name: group.name, count: rest.length });
  }
  const note = document.createElement("div");
  note.className = "popover-note";
  note.textContent = t("panels.deck_list_note");
  const notes = [note];
  if (topId) {
    const topNote = document.createElement("div");
    topNote.className = "popover-note deck-top-note";
    topNote.textContent = top.source
      ? t("panels.deck_list_top_note", { source: top.source })
      : t("panels.deck_list_public_top_note");
    notes.push(topNote);
  }
  const pin = (entry, card) => {
    if (entry) pinPopover(entry, card);
  };
  const cards = entries.map((entry) => {
    const copies = entry.count > 1 ? `×${entry.count}` : "";
    return visualCard(entry.id, entry.top
      ? {
          className: "small deck-top",
          badge: t("panels.deck_list_top_badge"),
          title: `${entry.name} · ${t("panels.deck_list_top_title")}`,
          onClick: pin,
        }
      : {
          className: "small",
          badge: copies,
          title: copies ? `${entry.name} ${copies}` : entry.name,
          onClick: pin,
        });
  });
  return { sections: [{ title, notes, cards }] };
}

/* ---------- the Victory Point ledger ---------- */

/* How a seat scored its Victory Points (user request 2026-10-11): its
   Victory Point count on the seat panel opens the pile viewer on every step
   that moved them, "R3 +1 → 4" and the cause. The server walks the game
   and reports each seat's change step by step (GET /games/{id}/vp-ledger,
   sessions.py vp_ledger): most changes come with no Victory Point event of
   their own (an Influence track reaching 2, an Alliance passing on). A row
   names its step by log index only, so the cause is drawn here from this
   page's own log entry, as redacted as the log already is for this seat,
   and a click on the row finds that entry in the action log.

   The ledger is fetched while the viewer shows it and again whenever the
   game has moved on (summary.log_count). The rows kept are the ones before
   the end of the log on screen, so they add up to the points the seat
   panel shows: live, a ledger read a moment after the snapshot loses the
   steps the page has not drawn yet; in a review, the rows stop at the
   cursor. */
const vpLedger = {
  gameId: null,
  /* The payload: {log_count, start, entries}. */
  data: null,
  /* The log_count being fetched, and the one a fetch failed at (no retry
     until the game moves on). */
  loading: null,
  failedAt: null,
  error: null,
};

/* Event kinds that can carry a Victory Point change; the row lists the ones
   its log entry holds for the seat. A sweep of 24 app AI games (every
   expansion) and the review's 75 found one in nearly every scoring step;
   a step with none still shows its own head. */
const VP_CAUSE_KINDS = new Set([
  /* A line's gain (cleanup-2c: its Victory Points are a payload key). */
  "resources_gained",
  "reveal_victory_point_gained",
  "influence_gained",
  "influence_lost",
  "leader_influence_bonus_gained",
  "alliance_gained",
  "alliance_transferred",
  "alliance_lost",
  "conflict_won",
  "combat_reward_gained",
  "combat_reward_icon_resolved",
  "battle_icons_matched",
  "endgame_wild_matched",
  "card_acquired",
  "agent_card_trashed_for_vp",
  "contract_reveal_card_trashed_for_vp",
  "contract_completed",
  "tleilaxu_advanced",
  "tleilaxu_track_end",
  "research_advanced",
  "intrigue_effect_used",
  "board_effect_resolved",
  "scouts_effect_resolved",
  "tech_acquire_effect_resolved",
  "agent_card_effect_resolved",
  "agent_card_reward_chosen",
  /* A Combat reward paid by recalling Spies scores on its own event
     (2026-10-11 review); a paid arrow's point is a resources_gained. */
  "spies_recalled",
]);

/* Whether this page may read the ledger: always on an open server; on a
   remote one while it holds a seat of the game, or once the game has
   finished (sessions.py vp_ledger: a client with only the room link gets
   nothing more than before until the end). Elsewhere the count is a plain
   number. */
function vpLedgerReadable() {
  return (
    !isRemote() || mySeats().length > 0 || Boolean(state.summary && state.summary.finished)
  );
}

/* The ledger for the state on screen: `{data, fresh, error}`, `data` the
   last one fetched (possibly older than the page, while a newer one
   loads). Starts that fetch when there is none. */
function vpLedgerState() {
  const gameId = state.gameId;
  if (vpLedger.gameId !== gameId) {
    Object.assign(vpLedger, {
      gameId,
      data: null,
      loading: null,
      failedAt: null,
      error: null,
    });
  }
  const wanted = state.summary ? state.summary.log_count : 0;
  const fresh = Boolean(vpLedger.data) && vpLedger.data.log_count >= wanted;
  if (!fresh && vpLedger.loading === null && vpLedger.failedAt !== wanted) {
    loadVpLedger(gameId, wanted);
  }
  return {
    data: vpLedger.data,
    fresh,
    error: vpLedger.failedAt === wanted ? vpLedger.error : null,
  };
}

function loadVpLedger(gameId, wanted) {
  vpLedger.loading = wanted;
  api(`/games/${gameId}/vp-ledger`)
    .then((data) => {
      if (vpLedger.gameId !== gameId) return;
      vpLedger.data = data;
      vpLedger.failedAt = null;
      vpLedger.error = null;
    })
    .catch((error) => {
      if (vpLedger.gameId !== gameId) return;
      vpLedger.failedAt = wanted;
      vpLedger.error = error.message;
    })
    .finally(() => {
      if (vpLedger.gameId !== gameId) return;
      vpLedger.loading = null;
      if (pileViewerKey && pileViewerKey.kind === "vp") refreshPileViewer();
    });
}

/* The log on screen: the live one, or a review's up to its cursor. */
function shownLog() {
  return state.review ? reviewLog(state.review) : state.log;
}

/* The viewer's contents for one seat: a title with its current points, a
   note, and the rows. `aria-busy` stays "true" while a newer ledger loads,
   so a reader (or a check) knows the rows may still be catching up. */
function vpLedgerContent(key, view) {
  const player = view.players.find((p) => p.player === key.seat);
  if (!player || !vpLedgerReadable()) return null;
  const { data, fresh, error } = vpLedgerState();
  const title = t("panels.vp_ledger_title", {
    name: seatLeaderName(key.seat),
    points: player.victory_points,
  });
  const note = document.createElement("div");
  note.className = "popover-note";
  note.textContent = t("panels.vp_ledger_note");
  const notes = [note];
  if (error) {
    const failed = document.createElement("div");
    failed.className = "popover-note error";
    failed.textContent = t("panels.vp_ledger_failed", { message: error });
    notes.push(failed);
  } else if (!fresh) {
    const loading = document.createElement("div");
    loading.className = "popover-note";
    loading.textContent = t("panels.vp_ledger_loading");
    notes.push(loading);
  }
  const list = document.createElement("ol");
  list.className = "vp-ledger";
  list.dataset.seat = String(key.seat);
  list.setAttribute("aria-busy", fresh ? "false" : "true");
  if (data) {
    const log = shownLog();
    const end = log ? log.count : 0;
    const entries = new Map(((log && log.entries) || []).map((entry) => [entry.index, entry]));
    list.appendChild(vpStartRow(data.start[key.seat]));
    for (const row of data.entries) {
      if (row.seat !== key.seat || row.index >= end) continue;
      list.appendChild(vpLedgerRow(row, entries.get(row.index)));
    }
  }
  return { sections: [{ title, notes, body: list }] };
}

/* The points every seat starts with, as the first row, so the rows add up
   to the count on the seat panel. */
function vpStartRow(points) {
  const item = document.createElement("li");
  item.className = "vp-row vp-start";
  item.dataset.delta = String(points);
  item.dataset.total = String(points);
  const main = document.createElement("div");
  main.className = "vp-row-main";
  const cause = document.createElement("div");
  cause.className = "vp-cause";
  cause.textContent = t("panels.vp_ledger_start");
  main.append(
    vpCell("vp-round", ""),
    vpCell("vp-delta", String(points)),
    vpCell("vp-total", `→ ${points}`),
    cause,
  );
  item.appendChild(main);
  return item;
}

function vpCell(className, text) {
  const cell = document.createElement("span");
  cell.className = className;
  cell.textContent = text;
  return cell;
}

/* One step that moved the seat's points: its round, the change, the points
   after it and what the log says the step did. A row whose log entry is on
   screen finds it in the action log (findLogEntry). */
function vpLedgerRow(row, entry) {
  const item = document.createElement("li");
  item.className = "vp-row";
  item.dataset.ledgerIndex = String(row.index);
  item.dataset.delta = String(row.delta);
  item.dataset.total = String(row.total);
  const main = document.createElement("div");
  main.className = "vp-row-main";
  const round = vpCell("vp-round", t("panels.vp_ledger_round", { round: row.round }));
  round.title = t("review.round_label", { round: row.round });
  const sign = row.delta > 0 ? "+" : "−";
  const delta = vpCell(
    `vp-delta ${row.delta > 0 ? "gain" : "loss"}`,
    `${sign}${Math.abs(row.delta)}`,
  );
  const total = vpCell("vp-total", `→ ${row.total}`);
  total.title = t("panels.vp_ledger_total", { points: row.total });
  const cause = document.createElement("div");
  cause.className = "vp-cause";
  vpCause(cause, entry, row.seat, row.index);
  main.append(round, delta, total, cause);
  item.appendChild(main);
  if (entry) {
    main.tabIndex = 0;
    main.setAttribute("role", "button");
    main.dataset.ledgerRow = String(row.index);
    main.title = t("panels.vp_ledger_find");
    main.addEventListener("click", (event) => {
      event.stopPropagation();
      findLogEntry(row.index);
    });
    main.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      event.stopPropagation();
      findLogEntry(row.index);
    });
  }
  return item;
}

/* Whether an event is aimed at `seat` (its player, an Alliance's giver or
   taker, ...). */
function eventNamesSeat(event, seat) {
  const payload = event.payload || {};
  return [...SEAT_PAYLOAD_KEYS].some((key) => payload[key] === seat);
}

/* The cause of one row from the page's own log entry: the step's head as
   the action log reads it (the seat and its action; a chance step's name,
   or for the engine's pause what it went on to do), then the entry's
   events that can move this seat's points. Where those events are all the
   game's own doing after the step (splitEntryEvents: the Combat resolved
   by the last pass), the head names that first, as the log's "game in
   progress" card does, and the step that set it off after it. Without an
   entry on screen, the step's number alone. */
function vpCause(cause, entry, seat, index) {
  if (!entry) {
    cause.textContent = `#${index}`;
    return;
  }
  const head = document.createElement("div");
  head.className = "vp-cause-head";
  const explains = (event) => VP_CAUSE_KINDS.has(event.kind) && eventNamesSeat(event, seat);
  const events = (entry.events || []).filter(explains);
  /* What the log's own card calls the game's doing; null when it has no
     better name than "game in progress". */
  const gameTitle = (items, always) => {
    const title = neutralTitle({ items: items.map((event) => ({ event })) });
    if (!always && title === t("panels.neutral_default")) return null;
    const mark = document.createElement("span");
    mark.className = "neutral-mark";
    mark.textContent = "⚙";
    const what = document.createElement("strong");
    what.textContent = title;
    return [mark, what];
  };
  if (entry.type === "chance") {
    /* A pause, or a chance step whose point events are the game's own
       (Scouts secret rewards resolving inside a discard shuffle): the
       log files these under a neutral game card, so the row says so too. */
    const flow = splitEntryEvents({ ...entry, events: entry.events || [] }).neutral;
    if (isPauseChance(entry.decision_id)) head.append(...gameTitle(entry.events || [], true));
    else if (events.length > 0 && events.every((event) => flow.includes(event))) {
      head.append(...gameTitle(flow, true));
    } else {
      const what = document.createElement("strong");
      what.textContent = t("core.chance_label", {
        decision: describeChance(entry.decision_id),
      });
      head.append(what);
    }
  } else {
    const flow = splitEntryEvents(entry).neutral;
    const byGame =
      events.length > 0 && events.every((event) => flow.includes(event))
        ? gameTitle(flow, false)
        : null;
    const step = document.createElement("span");
    step.className = byGame ? "vp-cause-step after" : "vp-cause-step";
    const who = document.createElement("strong");
    who.textContent = seatLeaderName(entry.actor);
    const action = document.createElement("span");
    action.className = "turn-action";
    action.appendChild(describeAction(entry));
    step.append(seatToken(entry.actor, "seat-mark"), who, action);
    if (byGame) head.append(...byGame);
    head.appendChild(step);
  }
  cause.appendChild(head);
  for (const event of events) cause.appendChild(logEventLine(event));
}

/* ---------- finding a step in the action log ---------- */

/* A ledger row's click scrolls the action log to its entry and marks it for
   a moment. The log is rebuilt by every render, so the mark is kept here
   and put back by renderLog until it runs out. */
const LOG_TARGET_MS = 2500;
let logTarget = { gameId: null, index: null, until: 0 };
let logTargetTimer = 0;

function findLogEntry(index) {
  logTarget = { gameId: state.gameId, index, until: performance.now() + LOG_TARGET_MS };
  window.clearTimeout(logTargetTimer);
  releaseLogTarget();
  logTargetTimer = window.setTimeout(() => {
    logTarget = { gameId: null, index: null, until: 0 };
    releaseLogTarget();
    for (const node of document.querySelectorAll(".log-target")) {
      node.classList.remove("log-target");
    }
  }, LOG_TARGET_MS);
  const list = document.querySelector("#action-log .log-list");
  if (!list) return false;
  const nodes = markLogTarget(list);
  if (!nodes.length) return false;
  /* The line that carries a Victory Point event first (the game's own
     card for a Combat's rewards), else the step's own line. */
  const target =
    nodes.find((node) => VP_CAUSE_KINDS.has(node.dataset.eventKind)) ||
    nodes.find((node) => node.querySelector(".logevent")) ||
    nodes[0];
  scrollLogTo(list, target);
  holdLogTarget(list, target);
  return true;
}

/* The log's card pictures load lazily once scrolled to, and the ones above
   the target push it down as they arrive: keep it a third of the way down
   while it is marked, until the reader takes the log in hand (a wheel, a
   touch, the scrollbar or a key on it). The log's scrollTop cannot tell
   that apart: the browser's scroll anchoring moves it too as pictures
   arrive, holding the line at the top of the box rather than the target.
   An entry whose Victory Point line the game's own card files below its
   step's line (an Endgame match, a Combat's rewards) has pictures between
   the two, so in a short log (1366x768) the target slid out of the box
   while the anchored line stayed (2026-10-12). */
const LOG_READER_INPUTS = ["wheel", "touchstart", "pointerdown", "keydown"];
let releaseLogTarget = () => {};

function holdLogTarget(list, target) {
  const keep = () => {
    if (target.isConnected && target.classList.contains("log-target")) {
      scrollLogTo(list, target);
    } else release();
  };
  const release = () => {
    list.removeEventListener("load", keep, true);
    for (const kind of LOG_READER_INPUTS) list.removeEventListener(kind, release);
    if (releaseLogTarget === release) releaseLogTarget = () => {};
  };
  /* A picture's load does not bubble, but the log sees it on the way down. */
  list.addEventListener("load", keep, true);
  for (const kind of LOG_READER_INPUTS) {
    list.addEventListener(kind, release, { passive: true });
  }
  releaseLogTarget = release;
}

/* `node` a third of the way down the log's box; the scrollTop it set. */
function scrollLogTo(list, node) {
  const offset = node.getBoundingClientRect().top - list.getBoundingClientRect().top;
  list.scrollTop = Math.max(0, list.scrollTop + offset - list.clientHeight / 3);
  return list.scrollTop;
}

/* Mark the log's lines of the target entry, if one is still marked. */
function markLogTarget(list) {
  for (const node of list.querySelectorAll(".log-target")) {
    node.classList.remove("log-target");
  }
  if (
    logTarget.gameId !== state.gameId ||
    logTarget.index === null ||
    performance.now() > logTarget.until
  ) {
    return [];
  }
  const nodes = [...list.querySelectorAll(`[data-log-index="${logTarget.index}"]`)];
  for (const node of nodes) node.classList.add("log-target");
  return nodes;
}

/* Unlike won Battle cards, this timeline keeps a reveal in its original
   round even after a tie, an award or a later transfer of the card. The
   server projects only public reveals, up to the live/reviewed state. */
function conflictHistoryAnchor() {
  return document.querySelector("#board .slot-card.conflict") ||
    document.querySelector("#market .vcard.conflict") ||
    document.querySelector(".conflict-history-trigger") || el("board");
}

function openConflictHistory(anchor) {
  const pop = el("card-popover");
  clearTimeout(hoverTimer);
  pop.classList.remove("hover");
  pop.textContent = "";
  const history = document.createElement("div");
  history.className = "conflict-history";
  history.setAttribute("role", "region");
  history.setAttribute("aria-label", t("panels.conflict_history"));
  const head = document.createElement("div");
  head.className = "conflict-history-heading";
  const title = document.createElement("div");
  title.className = "popover-title";
  title.textContent = t("panels.conflict_history");
  const close = document.createElement("button");
  close.type = "button";
  close.className = "conflict-history-close";
  close.textContent = "×";
  close.setAttribute("aria-label", t("common.close"));
  close.addEventListener("click", () => {
    closePopover();
    if (anchor.isConnected) anchor.focus();
  });
  head.append(title, close);
  history.appendChild(head);
  const grid = document.createElement("div");
  grid.className = "conflict-history-grid";
  const view = state.view;
  for (const revealed of [...(view.conflict_history || [])].reverse()) {
    const item = document.createElement("div");
    item.className = "conflict-history-item";
    item.dataset.round = revealed.round;
    const round = document.createElement("div");
    round.className = "conflict-history-round";
    round.textContent = t("review.round_label", { round: revealed.round });
    if (revealed.round === view.round_number) {
      item.classList.add("current");
      const badge = document.createElement("span");
      badge.className = "conflict-history-current";
      badge.textContent = t("panels.conflict_history_current");
      round.append(" · ", badge);
    }
    const card = visualCard(revealed.conflict_id, {
      className: "conflict",
      onClick: (entry, thumb) => {
        if (!entry) return;
        pinPopover(entry, thumb);
        const back = document.createElement("button");
        back.type = "button";
        back.className = "conflict-history-back";
        back.textContent = t("panels.conflict_history_back");
        back.addEventListener("click", (event) => {
          event.stopPropagation();
          openConflictHistory(conflictHistoryAnchor());
        });
        pop.prepend(back);
        placePopover(pop, thumb, 340);
      },
    });
    const name = document.createElement("div");
    name.className = "conflict-history-name";
    name.textContent = nameOf(revealed.conflict_id);
    item.append(round, card, name);
    grid.appendChild(item);
  }
  if (!grid.childNodes.length) {
    grid.textContent = t("board.conflict_not_revealed");
  }
  history.appendChild(grid);
  pop.appendChild(history);
  popoverPinned = true;
  pinnedLeaderSeat = null;
  placePopover(pop, anchor, 620);
  for (const image of pop.querySelectorAll("img")) {
    if (image.complete) continue;
    image.addEventListener("load", () => {
      if (history.isConnected && !pop.hidden) placePopover(pop, anchor, 620);
    }, { once: true });
  }
}

/* A foreign move keeps pinned popovers open. Update this timeline when
   the next round is revealed, preserving the reader's scroll position. */
function refreshConflictHistory() {
  const pop = el("card-popover");
  if (!popoverPinned || !pop.querySelector(".conflict-history")) return;
  const scroll = pop.scrollTop;
  openConflictHistory(conflictHistoryAnchor());
  pop.scrollTop = scroll;
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

/* The payload's pairs as one string, the words its line shows
   (logEventParts). */
function logEventPayload(payload, eventKind) {
  const words = (piece) => (typeof piece === "string" ? piece : piece.textContent);
  return logEventParts(payload, eventKind)
    .map((part) => (Array.isArray(part) ? part.map(words).join("") : part))
    .join(" · ");
}

/* The pairs of logEventPayload(), each a string, or a list of strings and
   nodes when it names a card (cardNameNode, its picture on hover);
   logEventLine joins them. */
function logEventParts(payload, eventKind) {
  const parts = [];
  const shownNames = new Set();
  for (const [key, value] of Object.entries(payload)) {
    /* intrigue_played and navigation_card_played (rules/intrigue.py,
       rules/navigation.py): the step head already names the option in words
       (describeAction's play_intrigue and play_navigation branches,
       core.js), so a bare index here ("선택지: 1") would only repeat it
       unreadably. A declined or fizzled navigation_card_played
       (rules/navigation.py apply_navigation_play's decline_navigation)
       carries no "option" at all, so this leaves it untouched. */
    if (
      key === "option" &&
      (eventKind === "intrigue_played" || eventKind === "navigation_card_played")
    ) {
      continue;
    }
    const label = PAYLOAD_KEY_LABELS[key] || prettify(key);
    /* Before the zero filter: seat 0 is a seat. */
    if (SEAT_PAYLOAD_KEYS.has(key)) {
      if (typeof value !== "number" || value < 0) continue;
      const seat = t("common.seat", { seat: value });
      parts.push(key === "player" ? seat : `${label}: ${seat}`);
      continue;
    }
    /* A list of seats: Rebuild Infrastructure's two payers, [0, 1]
       (rules/scouts_effects.py). Named bare, as "player" is. */
    if (key === "players" && Array.isArray(value)) {
      parts.push(value.map((seat) => t("common.seat", { seat })).join(", "));
      continue;
    }
    /* The seats The Voice bars from the space (the original game's
       space_blocked_for_opponents, rules/agent_effects.py), by their names. */
    if (key === "blocked_players" && Array.isArray(value)) {
      const seats = value.map((seat) => t("common.seat", { seat })).join(", ");
      parts.push(`${PAYLOAD_KEY_LABELS[key]}: ${seats}`);
      continue;
    }
    /* The line of a reward row printed with "-OR-" or "Choose two:" that
       its recipient took (combat_reward_line_chosen, the one event with a
       "line"; rules/combat.py counts from line_0): named from one, before
       the zero filter, since the first line is line 0. */
    if (key === "line") {
      if (typeof value === "number") parts.push(t("panels.log_reward_line", { n: value + 1 }));
      continue;
    }
    /* Combat rewards and the like list every field; zeros say nothing. */
    if (value === 0 || value === "" || value === null || value === false) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    if (key === "source") {
      const found = sourceRef(value);
      if (found && CARD_SECTIONS.has(found.section)) {
        parts.push([`${label}: `, cardNameNode(found.entry)]);
      } else if (found) {
        parts.push(`${label}: ${found.entry.name}`);
      }
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
    let cards = null;
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
      if (text !== null) cards = fieldNodes(key, raw, payload, shown);
    }
    /* card_id and instance_id of one event resolve to the same name. */
    if (isIdField && shownNames.has(shown)) continue;
    if (isIdField) shownNames.add(shown);
    parts.push(cards ? [`${label}: `, ...cards] : `${label}: ${shown}`);
  }
  return parts;
}

/* Event kinds only one Leader's ability emits, so their payload names no
   Leader: the line names the ability and the Leader from the catalog
   (lookup(id, "leaders"), localized by i18n.js) through its own text, whose
   holes are {{ability}} and {{leader}}, in place of the bare "{leader}" of
   EVENT_LABELS (kept for a catalog without the Leader).
   tests/server/test_action_labels.py checks that each kind here has one
   emitter in the engine and that it names this Leader, so a row cannot go
   stale silently. No kind needs a row now: Staban Tuek's Smuggle Spice is a
   leader_ability_resolved naming him, after its resources_gained
   (cleanup-2c-4). */
const EVENT_IMPLIED_LEADER = {
};

/* An event line's words before the payload. */
function logEventHead(event) {
  const implied = EVENT_IMPLIED_LEADER[event.kind];
  const leader = implied ? lookup(implied.leader, "leaders") : null;
  if (leader && leader.ability) {
    return tNode(implied.text, { ability: leader.ability, leader: leader.name });
  }
  /* A Leader's ability (Staban Tuek's Smuggle Spice, Esmar Tuek's Tuek's
     Sietch, the Assassin, Hungry for Spice): its line names the ability and
     the Leader from the catalog (user report 2026-10-10), its gain on the
     resources_gained line before it (cleanup-2c-4). */
  const named =
    event.kind === "leader_ability_resolved" && event.payload
      ? lookup(event.payload.leader_id, "leaders")
      : null;
  if (named && named.ability) {
    return tNode("panels.log_leader_ability_resolved", {
      ability: named.ability,
      leader: named.name,
    });
  }
  /* phrase(), not textContent: an event label may name a term, and the
     braces must never reach the screen. */
  return phrase(EVENT_LABELS[event.kind] || prettify(event.kind));
}

function logEventLine(event) {
  const line = document.createElement("div");
  line.className = "logevent";
  line.dataset.eventKind = event.kind;
  line.appendChild(logEventHead(event));
  const pieces = [];
  logEventParts(event.payload, event.kind).forEach((part, index) => {
    pieces.push(index ? " · " : " — ");
    if (Array.isArray(part)) pieces.push(...part);
    else pieces.push(part);
  });
  appendRun(line, pieces);
  addLogEventIcon(line, event);
  return line;
}

/* Steps that only close a window; kept in the record but muted:
   finish_agent_turn and finish_reveal end an Agent or Reveal turn,
   pass_combat_intrigue / pass_endgame_intrigue decline a Combat or Endgame
   Intrigue window (rules/combat.py, rules/endgame.py) — the engine never
   emits a bare "pass" — and decline_conflict_end_intrigue a Conflict-end
   window, which opens on public facts, mostly with nothing to play
   (OQ-103), or finish_conflict_end_intrigue it once a card was played. */
const QUIET_ACTIONS = new Set([
  "finish_agent_turn",
  "finish_reveal",
  "pass_combat_intrigue",
  "pass_endgame_intrigue",
  "decline_conflict_end_intrigue",
  "finish_conflict_end_intrigue",
]);

/* Steps that stand as a card of their own (setup picks). */
const SOLO_ACTIONS = new Set(["pick_leader"]);

/* Events the game produces on its own once a step closes a window —
   setup after the last Leader pick, combat resolution after the last
   Reveal, the round change — rather than the acting seat's doing. From
   the first of these in a step, the rest of that step's events belong to
   the game too (the round-start draws follow the recall, the Victory
   Points follow the combat reward).

   cards_drawn is only ever the Round Start draw (rules/phases.py
   draw_round_hands). When a revealed Conflict offers a Control defense, the
   draw comes after it [Main p. 8] [Main p. 20], so it arrives inside the
   controller's defense step: listing it here keeps the controller's own
   draw (and whatever follows it in that step) out of their defense card. */
const NEUTRAL_EVENT_KINDS = new Set([
  "leader_draft_pool_revealed",
  "leader_draft_unused",
  "conflict_revealed",
  "cards_drawn",
  "combat_intrigue_started",
  "combat_intrigue_finished",
  "combat_standing",
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
    if (UNLOGGED_EVENT_KINDS.has(event.kind)) continue;
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
   and combat_intrigue_finished; the last Conflict-end decline runs on into
   the cleanup). */
const PASS_MARKER_KINDS = new Set([
  "combat_intrigue_passed",
  "endgame_intrigue_passed",
  "conflict_end_trigger_declined",
]);

/* Events the log cards leave out; the record keeps them. The Conflict-end
   window opens on public facts for every seat with enough units in the
   Conflict and an Intrigue card (OQ-103), so one "offered" line per seat
   would only repeat what the declines and plays after it already say. */
const UNLOGGED_EVENT_KINDS = new Set(["conflict_end_trigger_offered"]);

/* Group the log into cards. A turn card holds consecutive steps by one
   seat (with only their own events) until a step closes the turn
   (QUIET_ACTIONS: finish_agent_turn, finish_reveal and the Intrigue
   windows' passes); a Leader pick is a card of
   its own. Everything the game does by itself — the neutral events above
   and every chance step — goes into a "게임 진행" card between them, so
   the round change never reads as the last actor's move.

   A pass (PASS_ACTION_IDS: a Combat or Endgame Intrigue pass, a declined
   Conflict-end window) that would otherwise start
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
    /* A step that only picks toward a waiting effect: the step that ends
       the effect shows it whole (stage B3). */
    if (entry.pick) continue;
    if (entry.type === "undo") {
      groups.push({ kind: "undo", entry });
      open = null;
      neutral = null;
      continue;
    }
    if (entry.type === "chance") {
      /* A chance step's own line, then what its step went on to do: a
         reshuffle can run on into the round's reveal and draw, and the
         engine's pause before a reveal (rules/pauses.py) carries whatever it
         held back (the next recipient's reward, the Conflict's winner, the
         next round). The pause itself has one outcome and changes nothing:
         the record keeps its line, the log does not. */
      const lines = isPauseChance(entry.decision_id) ? [] : [{ chance: entry }];
      for (const event of entry.events || []) {
        if (!UNLOGGED_EVENT_KINDS.has(event.kind)) lines.push({ event, index: entry.index });
      }
      /* Every chance step closes the open turn card, also one whose lines
         are all left out (the CONFLICT_END pause carries only the windows'
         "offered" events), so a Conflict-end decline does not join the
         same seat's reward card before the pause and split the chain of
         declines. A pass chain right before such a step may still go on,
         as nothing shows between them. */
      open = null;
      addNeutral(entry.index, lines);
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
  if (
    kinds.has("conflict_won") ||
    kinds.has("combat_standing") ||
    kinds.has("combat_reward_gained")
  ) {
    parts.push(t("panels.neutral_combat_resolved"));
  }
  // cards_drawn is the Round Start draw; after a Control defense it lands
  // in a card of its own, apart from the reveal [Main p. 8] [Main p. 20].
  if (
    kinds.has("agents_recalled") ||
    kinds.has("conflict_revealed") ||
    kinds.has("cards_drawn")
  ) {
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
  /* A Leader's ability paying out on another seat's step: Staban Tuek's
     Smuggle Spice, Esmar Tuek's Tuek's Sietch, Steersman Y'rkoon's Hungry
     for Spice (an event aimed at a seat other than the actor's lands here,
     splitEntryEvents). */
  if (kinds.has("leader_ability_resolved")) {
    parts.push(t("panels.neutral_leader_ability"));
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
  const picture = neutralLogIcon(group);
  if (picture) mark.appendChild(picture);
  else mark.textContent = "⚙";
  const who = document.createElement("strong");
  who.textContent = neutralTitle(group);
  head.append(mark, who);
  card.appendChild(head);
  const lines = document.createElement("div");
  lines.className = "turn-lines";
  for (const item of group.items) {
    const line = item.chance ? chanceLine(item.chance) : logEventLine(item.event);
    /* Its log entry, for findLogEntry. */
    line.dataset.logIndex = String(item.chance ? item.chance.index : item.index);
    lines.appendChild(line);
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
  if (isPauseChance(entry.decision_id)) {
    line.textContent = t("core.pause_step");
    return line;
  }
  /* The card behind the step, and a drawn card, show their picture on
     hover (cardNameNode); the words are describeChance()'s and
     chanceValueName()'s. */
  const words = chanceWords(entry.decision_id);
  const text = t("core.chance_label", { decision: words.text });
  const cause = words.cause && CARD_SECTIONS.has(words.cause.section) ? words.cause.entry : null;
  const at = cause ? text.lastIndexOf(`(${cause.name})`) : -1;
  const pieces =
    at < 0
      ? [text]
      : [text.slice(0, at + 1), cardNameNode(cause), text.slice(at + 1 + cause.name.length)];
  if (entry.values) {
    pieces.push(" — ");
    entry.values.slice(0, 3).forEach((value, index) => {
      if (index) pieces.push(", ");
      pieces.push(chanceValueNode(entry.decision_id, value));
    });
    if (entry.values.length > 3) pieces.push(" …");
  }
  appendRun(line, pieces);
  return line;
}

/* One drawn value of a chance line: chanceValueName()'s words, as the
   card's cardNameNode() when they are that card's name. A Scouts draw
   names an item, a layout or a round, never a card. */
function chanceValueNode(decisionId, value) {
  const name = chanceValueName(decisionId, value);
  if (SCOUTS_DRAW.test(String(decisionId))) return name;
  const card = cardEntryOf(value);
  return card && card.name === name ? cardNameNode(card) : name;
}

function turnLine(entry) {
  const line = document.createElement("div");
  line.className = "turn-line";
  line.dataset.logIndex = String(entry.index);
  if (QUIET_ACTIONS.has(entry.action_id)) line.classList.add("quiet");
  if (entry.undone) line.classList.add("undone");
  const head = document.createElement("div");
  head.className = "turn-line-head";
  const index = document.createElement("span");
  index.className = "turn-index";
  index.textContent = `#${entry.index}`;
  /* Keep the phrase's text and icons in one inline flow. Appending its
     fragment to the flex head makes each piece a separate wrapping column. */
  const label = document.createElement("span");
  label.className = "turn-action";
  label.appendChild(describeAction(entry, { cardNames: true }));
  if (entry.undone) label.append(t("panels.undone_suffix"));
  /* A parenthesized icon is one unit, including both punctuation marks. */
  for (const token of label.querySelectorAll(".icon, .amount, .agent-piece-icon, .term-text")) {
    const before = token.previousSibling;
    const after = token.nextSibling;
    if (before?.nodeType !== Node.TEXT_NODE || after?.nodeType !== Node.TEXT_NODE ||
        !before.textContent.endsWith("(") || !after.textContent.startsWith(")")) continue;
    const group = document.createElement("span");
    group.className = "log-term-group";
    before.textContent = before.textContent.slice(0, -1);
    after.textContent = after.textContent.slice(1);
    token.before(group);
    group.append("(", token, ")");
  }
  head.append(index, label);
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
  const entry = leaderFace ? lookup(leaderFace, "leaders") : null;
  if (entry) return entry.name;
  return leaderFace ? prettify(leaderFace) : t("common.seat", { seat });
}

/* seatLeaderName() as a node: the Leader's name shows its card on hover
   (cardNameNode), "Seat N" stays text. */
function seatLeaderNode(seat) {
  const name = seatLeaderName(seat);
  const player = state.view && state.view.players[seat];
  const leaderFace = player && (player.leader_face_id || player.leader_id);
  const entry = leaderFace ? lookup(leaderFace, "leaders") : null;
  return entry && entry.name === name ? cardNameNode(entry) : document.createTextNode(name);
}

/* How many card pictures a turn card in the log shows before "+N". */
const LOG_CARDS_SHOWN = 8;
/* The mark for each reason logTargets gives a card. */
const LOG_REASON_TEXT = {
  acquired: "panels.log_reason_acquired",
  trashed: "panels.log_reason_trashed",
  discarded: "panels.log_reason_discarded",
  flipped: "panels.log_reason_flipped",
  grafted: "panels.log_reason_grafted",
  completed: "panels.log_reason_completed",
  used: "panels.log_reason_used",
};

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
  who.appendChild(seatLeaderNode(group.actor));
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
      targets.spaces.map(spaceName).join(", "),
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
    /* Every card the turn named, up to LOG_CARDS_SHOWN, each marked with
       why it is there (logTargets reasons). Four used to be the limit, and
       a busy turn lost its later cards: a Tech tile flipped after an Agent
       card, a graft and a Skill (play feedback 2026-10-26). */
    for (const id of targets.cards.slice(0, LOG_CARDS_SHOWN)) {
      const reasons = targets.reasons.get(baseId(id)) || [];
      const text = reasons
        .slice(0, 2)
        .map((reason) => t(LOG_REASON_TEXT[reason]))
        .join("·");
      row.appendChild(
        visualCard(id, {
          className: "small",
          badge: text || undefined,
          badgeClass: "log-reason",
          badgeTitle: text || undefined,
          onClick: (entry, node) => {
            if (entry) pinPopover(entry, node);
          },
        })
      );
    }
    /* Past four pictures they stand two abreast, so the card does not
       grow twice as tall. */
    if (Math.min(targets.cards.length, LOG_CARDS_SHOWN) > 4) row.classList.add("many");
    const more = targets.cards.length - LOG_CARDS_SHOWN;
    if (more > 0) {
      const extra = document.createElement("span");
      extra.className = "turn-cards-more muted";
      extra.textContent = t("panels.log_cards_more", { count: more });
      row.appendChild(extra);
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
   Intrigue already has one that names the window
   (EVENT_LABELS.combat_intrigue_passed, "{combat} {intrigue_card} 패스"); Endgame
   Intrigue's own event label is bare ("Passed", EVENT_LABELS.
   endgame_intrigue_passed) -- and so is the action label next to it
   (ACTION_LABELS.pass_endgame_intrigue is just "패스"/"Pass" too, nothing on
   an unfolded pass names the window either) -- so a fold needs a label of
   its own that does name it (panels.pass_fold_endgame_intrigue, UI_TEXT).
   A chain of Conflict-end declines has its own too
   (panels.pass_fold_conflict_end_intrigue). */
function passFoldLabel(actionId) {
  if (actionId === "pass_endgame_intrigue") return tNode("panels.pass_fold_endgame_intrigue");
  if (actionId === "decline_conflict_end_intrigue") {
    return tNode("panels.pass_fold_conflict_end_intrigue");
  }
  return phrase(EVENT_LABELS.combat_intrigue_passed);
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
    seat.dataset.logIndex = String(entry.index);
    if (entry.undone) seat.classList.add("undone");
    seat.appendChild(seatToken(entry.actor, "seat-mark"));
    seat.append(seatLeaderNode(entry.actor));
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
   0 when the seat has not acted yet, so its whole log is new.

   In a game with one human seat, that seat's own Conflict-end declines
   (decline_conflict_end_intrigue) are not a boundary: the server answers
   a decline-only window for it there (sessions.py _auto_decline_locked),
   logged as the seat's own step, so the AI moves and the Combat result
   before it would stop glowing although the seat never saw them. The page
   cannot tell that decline from a pressed one, and a pressed one adds
   nothing the seat had not already seen when it pressed: at worst what it
   read at its window keeps glowing until its next move. With two or more
   human seats the server never answers, so every decline is a press and
   stays a boundary (OQ-103). */
const LONE_HUMAN_GLOW_SKIPPED = new Set(["decline_conflict_end_intrigue"]);

function ownGlowFrom(seat, entries, seats) {
  const loneHuman = seats.filter((kind) => kind === "human").length === 1;
  let last = -1;
  for (const entry of entries) {
    if (
      entry.type === "action" &&
      entry.actor === seat &&
      !entry.undone &&
      !(loneHuman && LONE_HUMAN_GLOW_SKIPPED.has(entry.action_id))
    ) {
      last = entry.index;
    } else if (entry.type === "undo" && entry.seat === seat) last = entry.index;
  }
  return last + 1;
}

const LOG_EXPANDED_KEY = "dune.logExpanded";

function labelLogSize(button) {
  const expanded = el("side").classList.contains("log-expanded");
  button.textContent = expanded ? t("panels.log_compact") : t("panels.log_expand");
  button.setAttribute("aria-expanded", String(expanded));
}

function toggleLogSize(button) {
  const list = el("action-log").querySelector(".log-list");
  const following = list && list.scrollHeight - list.scrollTop - list.clientHeight < 24;
  const expanded = el("side").classList.toggle("log-expanded");
  storageSet(LOG_EXPANDED_KEY, expanded ? "1" : "0");
  labelLogSize(button);
  if (following) list.scrollTop = list.scrollHeight;
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
    glowFrom = typeof seat === "number"
      ? ownGlowFrom(seat, log.entries, state.summary.seats)
      : arrivedFrom;
  }

  const toolbar = document.createElement("div");
  toolbar.className = "log-heading";
  const heading = document.createElement("h2");
  heading.textContent = t("panels.log_heading");
  const resize = document.createElement("button");
  resize.type = "button";
  resize.className = "log-size-toggle";
  resize.setAttribute("aria-controls", "turn-history");
  labelLogSize(resize);
  resize.addEventListener("click", () => toggleLogSize(resize));
  toolbar.append(heading, resize);
  panel.appendChild(toolbar);
  const list = document.createElement("div");
  list.className = "log-list";
  list.id = "turn-history";
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
  /* A step a Victory Point ledger row asked for stays marked (findLogEntry). */
  markLogTarget(list);
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

/* Controlled's and Poison Snooper's choice on the deck's top card
   (rules/intrigue.py, the PeekTopCard choice): these actions are offered
   exactly while that choice is up for the seat. Their live buttons name the
   card the seat is looking at (deckTopChoiceLabel, the text keyed here); the
   logged step keeps its plain label (ACTION_LABELS), since the log is
   everyone's to read. */
const DECK_TOP_CHOICE_TEXT = {
  put_back_top_card: "panels.deck_top_put_back",
  discard_top_card: "panels.deck_top_discard",
  draw_top_card_for_solari: "panels.deck_top_draw",
  draw_top_card: "panels.deck_top_draw_free",
  trash_top_card: "panels.deck_top_trash",
};
const DECK_TOP_CHOICES = new Set(Object.keys(DECK_TOP_CHOICE_TEXT));

function deckTopChoiceOffered() {
  return Boolean(
    !state.review && state.actions &&
      state.actions.actions.some((action) => DECK_TOP_CHOICES.has(action.action_id)),
  );
}

/* The card Controlled's choice is about while it is offered to the seat:
   the seat's own view's peeked_card_id (only the owner's view carries it,
   core/observation.py), or "" -- no such choice, a review (no actions), or
   nothing peeked. The view and the actions are one seat's snapshot
   (session.js adoptSnapshot), so the card is the deciding seat's own. */
function deckTopChoiceCard() {
  if (!deckTopChoiceOffered()) return "";
  const own = state.view && state.view.private;
  return (own && own.peeked_card_id) || "";
}

/* One of those live buttons naming the card ("{deck} 맨 위 카드(Dagger)
   버리기"), by its name on screen; null for any other action, or when
   no card is known (the plain label then stands). Only actionItem (render.js),
   which draws the seat's offered actions, asks for it. */
function deckTopChoiceLabel(action) {
  if (!DECK_TOP_CHOICES.has(action.action_id)) return null;
  const card = deckTopChoiceCard();
  return card ? tNode(DECK_TOP_CHOICE_TEXT[action.action_id], { card: nameOf(card) }) : null;
}

/* The card itself above those buttons in the decision panel
   (renderActionPanel, turn.js): its picture like any card on the table,
   enlarged on hover or click, badged as the deck's top. null when the
   choice is not up for the seat. */
function deckTopChoicePicture() {
  const card = deckTopChoiceCard();
  if (!card) return null;
  const box = document.createElement("div");
  box.className = "deck-top-choice";
  box.appendChild(
    visualCard(card, { className: "deck-top-choice-card", badge: t("panels.deck_top_badge") }),
  );
  return box;
}

/* What shows the seat its deck's top card, by its name on screen: the
   Glowglobes tile it owns, or else Controlled (the one Intrigue that peeks
   at a deck, content/uprising/intrigue.py). */
/* The original game's Mentat held by `player` this round: the engine does
   not tell it from the seat's own Agents (OQ-139 (가)), so the screen draws
   it by rule (user ruling 2026-10-28, "(가) 로 하자"): the last piece the seat
   placed beyond its own Agents (two, three with the Swordmaster) is the
   Mentat; with no such piece it stands on the Leader (""). A Kwisatz
   Haderach move puts the moved piece last, Urgent Mission's recall takes
   one off, and Recall returns the Mentat to its space (not held). */
function mentatSpace(player) {
  if (!player.mentat) return null;
  const own = 2 + (player.swordmaster_acquired ? 1 : 0);
  const placed = player.agent_locations || [];
  return placed.length > own ? placed[placed.length - 1] : "";
}

/* The original game's public markers on a seat (docs/rules/imperium-base.md):
   the spaces The Voice bars its next Agent from (OQ-116: shown apart from
   any Control marker), Infiltrate's turn and Recruitment Mission's round,
   and Baron Harkonnen's Masterstroke -- that he holds two secret Factions,
   which ones once revealed, and to his own seat alone (the view's private
   block, which only the observing seat's view carries) which ones before
   that (imperium-base.md 14). */
function originalMarkers(player, seat, view) {
  const flags = [];
  const card = (id, kind) => {
    const entry = lookup(id, kind);
    return entry ? entry.name : prettify(id);
  };
  const blocked = player.voice_blocked_space_ids || [];
  if (blocked.length) {
    flags.push(tNode("panels.voice_blocked", {
      card: card("the_voice", "cards"),
      spaces: blocked.map(spaceName).join(", "),
    }));
  }
  if (player.enemy_agents_ignored_turn) {
    flags.push(tNode("panels.infiltrate_turn", { card: card("infiltrate", "intrigue") }));
  }
  if (player.acquire_to_deck_top_round) {
    flags.push(tNode("panels.deck_top_round", {
      card: card("recruitment_mission", "intrigue"),
    }));
  }
  /* Masterstroke is Baron Harkonnen's ability: 절묘한 수완 in the Korean
     rulebook [DI-ko p. 13] (his Korean face is not transcribed). */
  const ability = t("panels.masterstroke_name");
  const factions = (ids) => ids.map((id) => FACTION_LABELS[id] || id).join(", ");
  const own = view.player === seat && view.private
    ? view.private.masterstroke_factions || []
    : [];
  if ((player.masterstroke_revealed_factions || []).length) {
    flags.push(tNode("panels.masterstroke_revealed", {
      ability, factions: factions(player.masterstroke_revealed_factions),
    }));
  } else if (own.length) {
    flags.push(tNode("panels.masterstroke_own", { ability, factions: factions(own) }));
  } else if (player.masterstroke_secret) {
    flags.push(tNode("panels.masterstroke_secret", { ability }));
  }
  return flags;
}

/* Rise of Ix's seat state (docs/rules/rise-of-ix.md 13). Public: the
   dreadnoughts waiting in the supply, the tracks still holding Tessia
   Vernius' Snooper tokens, that Ilesa Ecaz has a card set aside and that it
   came back this turn, and on the text board the Freighter's step and the
   Negotiators the board picture otherwise shows. Hidden, read only from the
   view's private block (which only the observing seat's view carries): the
   card Ilesa set aside, on her own panel, and the observer's own open Rise
   of Ix decision (ix_pending), on its own panel. */
function ixMarkers(player, seat, view) {
  if (!view.rise_of_ix) return [];
  const flags = [];
  const own = view.private && view.player === seat ? view.private : null;
  flags.push(tNode("panels.dreadnought_supply", { count: player.dreadnoughts_supply || 0 }));
  if (!boardDrawsTracks(view)) {
    flags.push(tNode("panels.freighter_step", { step: player.freighter_space || 0 }));
    if (player.negotiators) {
      flags.push(tNode("panels.negotiators", { count: player.negotiators }));
    }
  }
  const snoopers = player.snooper_faction_ids || [];
  if (snoopers.length) {
    flags.push(tNode("panels.snoopers", {
      factions: snoopers.map((id) => FACTION_LABELS[id] || id).join(", "),
    }));
  }
  if (player.has_set_aside_card) {
    flags.push(own && own.set_aside_card_id
      ? tNode("panels.set_aside_own", { card: nameOf(own.set_aside_card_id) })
      : tNode("panels.set_aside_hidden"));
  }
  if (player.set_aside_returned_turn) flags.push(tNode("panels.set_aside_returned"));
  const pending = own && own.ix_pending;
  if (pending && (pending.shipping_rewards || []).length) {
    flags.push(tNode("panels.ix_pending_shipping", {
      steps: pending.shipping_rewards.join(", "),
    }));
  }
  if (pending && pending.tech_payment) {
    flags.push(tNode("panels.ix_pending_tech", {
      discount: pending.tech_discount || 0,
      payment: phraseText(pending.tech_payment === "solari" ? "{solari}" : "{spice}"),
      negotiators: pending.negotiators_returnable || 0,
    }));
  }
  return flags;
}

/* The Intrigue cards the observer knows this seat holds (OQ-149): a card it
   saw on the deck's top and another seat drew -- Immortality's Imperium
   Ceremony in any game it is in, Rise of Ix's Hundro Moritani -- or one it
   put at the bottom (Court Intrigue, Sonic Snoopers) that another seat drew
   (rules.intrigue_knowledge). Read only from the view's private block, on
   the holder's panel, for every combination of expansions. */
function knownIntrigueMarkers(seat, view) {
  if (!view.private || view.player === seat) return [];
  const held = (view.private.known_intrigue_held || []).filter(([holder]) => holder === seat);
  if (!held.length) return [];
  return [tNode("panels.known_intrigue_held", {
    cards: held.map(([, id]) => nameOf(id)).join(", "),
  })];
}

function deckTopSource(glowglobes, leaderId) {
  if (!glowglobes && leaderId === "paul_atreides") {
    /* Prescience: "자기 덱 맨 위 카드를 언제든 볼 수 있다" (imperium-base.md
       12), named by its Leader. */
    const leader = lookup("paul_atreides", "leaders");
    return leader ? leader.name : prettify("paul_atreides");
  }
  const id = glowglobes ? "glowglobes" : "twisted_controlled";
  const entry = lookup(id, glowglobes ? "tech" : "intrigue");
  return entry ? entry.name : prettify(id);
}

function renderPrivate() {
  const panel = el("private-zone");
  cancelHandDrag();
  /* The board-width hand can scroll even with a normal five-card hand.
     A staged pick or a foreign update must not hide the card just read.
     Restore only an unchanged list, so a different hand starts at zero
     (the list as drawn: the player's own order, layout.js, when set). */
  const cardIds = pane => [...pane.querySelectorAll(".vcard")]
    .map(card => card.dataset.instance).join("\n");
  const scrolled = [...panel.querySelectorAll(".hand-zones, .strip-cards")]
    .filter(pane => pane.scrollLeft)
    .map(pane => ({
      selector: `.${pane.className.split(" ").join(".")}`,
      cards: cardIds(pane),
      left: pane.scrollLeft,
    }));
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
  const deckStat = statNode("draw", phraseText("{deck}"), view.private.deck_size);
  const discardStat = statNode("discard", phraseText("{discard_pile}"), own.discard_pile.length);
  counts.append(
    deckStat,
    discardStat,
    statNode("intrigue", phraseText("{intrigue}"), view.private.intrigue_cards.length)
  );
  /* The deck's contents, never its order, are the owner's to see (OQ-010
     ruling 5): the server's `deck_cards` is a sorted list of card ids.
     The top card is the exception when a card effect shows it to the owner
     (`peeked_card_id`: Glowglobes at any time, Controlled while its choice
     is up; core/observation.py): the list marks it, and the count's title
     says so, so the mark is found without opening the list first. The
     viewer reads the same two fields again on every render
     (deckListState). */
  const { deckCards, top } = deckListState(view);
  if (deckCards.length) {
    deckStat.dataset.pileOpener = "hand-deck";
    openerStat(deckStat, t(top ? "panels.deck_view_top" : "panels.deck_view"), () =>
      togglePileViewer(
        { kind: "deck", seat: activeSeat(), mine, opener: "hand-deck" },
        deckStat,
      )
    );
  }
  /* Discard piles are public (OQ-010); the owner's copy lives in the seat's
     public block like everyone else's. */
  if (own.discard_pile.length) {
    discardStat.dataset.pileOpener = "hand-discard";
    openerStat(discardStat, t("panels.discard_pile_view"), () =>
      togglePileViewer(
        { kind: "discard", seat: activeSeat(), mine, opener: "hand-discard" },
        discardStat,
      )
    );
  }
  label.appendChild(counts);
  panel.appendChild(label);

  const zones = document.createElement("div");
  zones.className = "hand-zones";
  /* The player's own live hand and Intrigue cards come in the order the
     player gave them in this browser (layout.js); anything else in the
     server's order. */
  const reorderable = handReorderable();
  const hand = document.createElement("div");
  hand.className = "strip-cards hand-cards";
  if (!view.private.hand.length) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = t("panels.hand_empty");
    hand.appendChild(empty);
  }
  for (const cardId of orderedStripIds("hand", view.private.hand)) {
    hand.appendChild(visualCard(cardId));
  }
  if (reorderable && view.private.hand.length) enableStripOrder(hand, "hand");
  zones.appendChild(hand);

  if (view.private.intrigue_cards.length) {
    const intrigue = document.createElement("div");
    intrigue.className = "strip-cards intrigue-cards";
    for (const cardId of orderedStripIds("intrigue", view.private.intrigue_cards)) {
      intrigue.appendChild(visualCard(cardId, { className: "intrigue" }));
    }
    if (reorderable) enableStripOrder(intrigue, "intrigue");
    zones.appendChild(intrigue);
  }
  /* Owner-only peeks beside the Intrigue cards: the Intrigue deck's top
     cards Imperium Ceremony shows while one is kept. Kota Odax's Secret
     Project tile is on his leader popover (core.js
     leaderSecretProjectBox). The seat's own deck's top card is never
     here (user decision 2026-10-10): Glowglobes' standing look is the deck
     list's "Top" entry (deckListContent), and Controlled's is its picture
     above the put back / discard / draw buttons, which name it
     (deckTopChoicePicture, deckTopChoiceLabel). */
  const peekedIntrigue = view.private.peeked_intrigue_ids || [];
  if (peekedIntrigue.length) {
    const peeks = document.createElement("div");
    peeks.className = "strip-cards";
    for (const cardId of peekedIntrigue) {
      peeks.appendChild(
        visualCard(cardId, { className: "small", badge: t("panels.intrigue_deck_top_badge") })
      );
    }
    zones.appendChild(peeks);
  }
  panel.appendChild(zones);
  for (const scroll of scrolled) {
    const pane = panel.querySelector(scroll.selector);
    if (pane && cardIds(pane) === scroll.cards) pane.scrollLeft = scroll.left;
  }
  syncHandOrderReset();
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
  /* The final clocks: a line of its own, not an eighth column. */
  const clocks = clockTotalsNode();
  if (clocks) panel.appendChild(clocks);

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

/* ---------- Arrakeen Scouts ----------

   Everything the view says about the Scouts deck (docs/rules/arrakeen-
   scouts.md): the subcommittees and their members, what was revealed each
   round, the mission pieces on the board, who still has a secret pick
   waiting (and the viewer's own), and the auction running now. Only the
   view is read, so nothing hidden can show: another seat's pick or bid is
   never in it. */
function scoutsItem(itemId) {
  const items = (state.catalog && state.catalog.scouts_items) || {};
  return items[itemId] || { kind: "", name: prettify(itemId), lines: [], lines_ko: [] };
}

function scoutsAuctionCurrency() {
  const item = scoutsItem(state.view && state.view.scouts_item);
  return item.kind === "auction" && TERMS[item.currency] ? item.currency : null;
}

/* A currency needs its visible name as well as its icon: reward lines do
   not say which resource an auction charges. No art still leaves the name. */
function scoutsCurrencyNode(currency) {
  const span = document.createElement("span");
  span.className = "scouts-currency";
  span.dataset.resource = currency;
  const name = termLabel(currency);
  if (iconUrl(currency)) {
    const picture = icon(currency, name);
    picture.setAttribute("aria-hidden", "true");
    span.append(picture, " ");
  }
  span.append(name);
  return span;
}

function scoutsCurrencyLine(currency) {
  const line = document.createElement("div");
  line.className = "scouts-auction-currency";
  line.append(t("panels.scouts_currency"), " ", scoutsCurrencyNode(currency));
  return line;
}

/* `currency: false` leaves an auction's bid resource out: the decision
   panel's header (scoutsDecisionHeader) leaves it to #actions, which shows
   it once (turn.js renderActionPanel). */
function scoutsItemLines(item, box, { currency = true } = {}) {
  if (currency && item.kind === "auction" && TERMS[item.currency]) {
    box.appendChild(scoutsCurrencyLine(item.currency));
  }
  item.lines.forEach((line, index) => {
    box.appendChild(effectLine(line, item.lines_ko[index], "scouts-line"));
  });
}

/* The Scouts step's cursor while due secret picks resolve
   (rules/scouts_secrets.py SECRET_ITEM): not an item of the catalog. */
const SCOUTS_SECRETS_CURSOR = "secrets";

/* The item the Scouts step is resolving now, or null outside the step.
   view.scouts_item is public (every seat's view) and empty during the
   round's turns (rules/scouts.py advance_scouts_step clears it); the
   seat's own choice names its item first, so a revealed secret pick shows
   its event while the cursor is "secrets". */
function scoutsDecisionItemId() {
  const view = state.view;
  if (!state.summary || !state.summary.arrakeen_scouts || !view || !view.scouts_item) {
    return null;
  }
  const own = state.actions && state.actions.scouts_lines;
  return (own && own.item_id) || view.scouts_item;
}

/* Whether the seat's own rows in #actions already are the item's lines:
   its Scouts choice of that item, or a secret pick's four lines. */
function scoutsRowsAreLines(itemId) {
  const actions = state.actions;
  if (!actions) return false;
  const own = actions.scouts_lines;
  if (own && own.frame === "scouts_choice" && own.item_id === itemId) return true;
  return (actions.actions || []).some((action) => action.action_id === "scouts_secret_pick");
}

/* User request 2026-10-10 (feedback item 8): the decision panel names the
   item a Scouts decision belongs to, with its lines, so nobody has to look
   down at the Scouts panel while choosing or waiting. Display only: it
   reads the public view and the seat's own actions. */
function scoutsDecisionHeader() {
  const id = scoutsDecisionItemId();
  if (!id) return null;
  const box = document.createElement("div");
  box.className = "scouts-decision-item";
  box.dataset.item = id;
  const title = document.createElement("div");
  title.className = "scouts-decision-title";
  box.appendChild(title);
  const known = Boolean(state.catalog && state.catalog.scouts_items
    && state.catalog.scouts_items[id]);
  const item = scoutsItem(id);
  if (state.view.scouts_item === SCOUTS_SECRETS_CURSOR) {
    title.textContent = known
      ? t("render.scouts_decision_secret_item", { name: item.name })
      : t("render.scouts_decision_secrets");
  } else {
    title.textContent = t("render.scouts_decision_item", {
      kind: scoutsKindName(item.kind),
      name: item.name,
    });
  }
  if (known && !scoutsRowsAreLines(id)) scoutsItemLines(item, box, { currency: false });
  return box;
}

function scoutsGoodsText(resource, amount) {
  if (resource === "marker") return "{control_marker}";
  if (resource === "maker_hooks") return "{maker_hooks}";
  return `{${resource}:${amount}}`;
}

/* "1 parked troop" / "2 parked troops"; the same for face-down cards. */
function scoutsParkedText(count) {
  return Number(count) === 1
    ? t("panels.scouts_parked_one", { count })
    : t("panels.scouts_parked", { count });
}

function scoutsFaceDownText(count) {
  return Number(count) === 1
    ? t("panels.scouts_face_down_one", { count })
    : t("panels.scouts_face_down", { count });
}

function scoutsSection(panel, title) {
  const heading = document.createElement("h3");
  heading.textContent = title;
  panel.appendChild(heading);
  const box = document.createElement("div");
  box.className = "scouts-section";
  panel.appendChild(box);
  return box;
}

function scoutsRow(box, content) {
  const row = document.createElement("div");
  row.className = "scouts-row";
  if (typeof content === "string") row.appendChild(phrase(content));
  else row.appendChild(content);
  box.appendChild(row);
  return row;
}

function renderScouts() {
  const panel = el("scouts-panel");
  const summary = state.summary;
  const view = state.view;
  if (!summary || !summary.arrakeen_scouts || !view) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  /* The heading row stays from one render to the next: beside the heading
     is the button that brings the Scouts card back over the board
     (scouts_stage.js scoutsStageOpener), which keeps its node and focus. */
  let head = panel.querySelector(":scope > .scouts-panel-head");
  if (!head) {
    head = document.createElement("div");
    head.className = "scouts-panel-head";
    head.append(document.createElement("h2"), scoutsStageOpener());
  }
  for (const node of [...panel.childNodes]) if (node !== head) node.remove();
  if (head.parentNode !== panel) panel.appendChild(head);
  head.querySelector("h2").textContent = t("panels.scouts_heading");

  if (view.scouts_subcommittees.length) {
    const box = scoutsSection(panel, t("panels.scouts_subcommittees"));
    const members = new Map(view.scouts_subcommittee_members.map(([id, seat]) => [id, seat]));
    for (const id of view.scouts_subcommittees) {
      const item = scoutsItem(id);
      const member = members.has(id) ? playerLabel(members.get(id)) : t("panels.scouts_open_seat");
      const row = scoutsRow(box, `${item.name} — ${member}`);
      row.dataset.item = id;
      scoutsItemLines(item, row);
    }
  }

  const current = view.scouts_revealed.filter(([round]) => round === view.round_number);
  const earlier = view.scouts_revealed.filter(([round]) => round !== view.round_number);
  if (current.length) {
    const box = scoutsSection(panel, t("panels.scouts_this_round"));
    for (const [, id] of current) {
      const item = scoutsItem(id);
      const row = scoutsRow(box, `${scoutsKindName(item.kind)} · ${item.name}`);
      row.dataset.item = id;
      scoutsItemLines(item, row);
    }
  }

  const pieces = [];
  const goodsByMission = new Map();
  for (const [mission, location, resource, amount, seat] of view.scouts_goods) {
    const who = seat < 0 ? t("panels.scouts_anyone") : playerLabel(seat);
    if (!goodsByMission.has(mission)) goodsByMission.set(mission, []);
    goodsByMission
      .get(mission)
      .push(`${scoutsPlace(location)}: ${scoutsGoodsText(resource, amount)} (${who})`);
  }
  for (const [mission, seat, location, troops] of view.scouts_parked) {
    if (!goodsByMission.has(mission)) goodsByMission.set(mission, []);
    goodsByMission
      .get(mission)
      .push(`${scoutsPlace(location)}: ${scoutsParkedText(troops)} (${playerLabel(seat)})`);
  }
  for (const [mission, location, count] of view.scouts_board_card_counts) {
    if (!goodsByMission.has(mission)) goodsByMission.set(mission, []);
    goodsByMission
      .get(mission)
      .push(`${scoutsPlace(location)}: ${scoutsFaceDownText(count)}`);
  }
  for (const [mission, lines] of goodsByMission) pieces.push([mission, lines]);
  if (pieces.length) {
    const box = scoutsSection(panel, t("panels.scouts_pieces"));
    for (const [mission, lines] of pieces) {
      const row = scoutsRow(box, scoutsItem(mission).name);
      row.dataset.item = mission;
      for (const line of lines) {
        const detail = document.createElement("div");
        detail.className = "scouts-line";
        detail.appendChild(phrase(line));
        row.appendChild(detail);
      }
    }
  }

  const own = (view.private && view.private.scouts_secret_picks) || [];
  if (view.scouts_secret_pending.length || own.length) {
    const box = scoutsSection(panel, t("panels.scouts_secrets"));
    const waiting = new Map();
    for (const [round, event, seat] of view.scouts_secret_pending) {
      const key = `${round}|${event}`;
      if (!waiting.has(key)) waiting.set(key, []);
      waiting.get(key).push(playerLabel(seat));
    }
    for (const [key, seats] of waiting) {
      const [round, event] = key.split("|");
      scoutsRow(
        box,
        t("panels.scouts_secret_waiting", {
          round,
          name: scoutsItem(event).name,
          seats: seats.join(", "),
        }),
      );
    }
    for (const [, event, pick] of own) {
      const item = scoutsItem(event);
      const row = scoutsRow(box, t("panels.scouts_own_pick", { name: item.name }));
      row.classList.add("scouts-own");
      row.appendChild(effectNode(item.lines[pick] || "", item.lines_ko[pick]));
    }
  }

  const auctionHere = current.some(([, id]) => scoutsItem(id).kind === "auction");
  const ownBid = view.private ? view.private.scouts_bid : -1;
  if (auctionHere && (view.scouts_bids_confirmed.length || ownBid >= 0)) {
    const box = scoutsSection(panel, scoutsKindName("auction"));
    scoutsRow(
      box,
      view.scouts_bids_confirmed.length
        ? t("panels.scouts_bids", { seats: view.scouts_bids_confirmed.map(playerLabel).join(", ") })
        : t("panels.scouts_no_bids"),
    );
    if (ownBid >= 0) {
      const row = scoutsRow(box, t("panels.scouts_own_bid", { count: ownBid }));
      row.classList.add("scouts-own");
      const currency = scoutsAuctionCurrency();
      if (currency) row.append(" ", scoutsCurrencyNode(currency));
    }
  }
  if (view.scouts_market_cards.length) {
    const box = scoutsSection(panel, t("panels.scouts_market"));
    box.classList.add("scouts-market-cards");
    view.scouts_market_cards.forEach((id, slot) => {
      const row = scoutsRow(box, `${slot + 1}. ${nameOf(id)}`);
      row.dataset.card = id;
      row.prepend(visualCard(id, {
        /* Inspecting a prize must not submit a card-pick action. */
        onClick: (entry, card) => { if (entry) pinPopover(entry, card); },
      }));
    });
    if (view.scouts_calls.length) {
      const calls = view.scouts_calls.map(
        ([seat, amount]) => `${playerLabel(seat)} ${amount ? `{spice:${amount}}` : t("panels.scouts_pass")}`,
      );
      scoutsRow(panel, t("panels.scouts_calls", { calls: calls.join(", ") }));
    }
  }

  if (earlier.length) {
    const details = document.createElement("details");
    const label = document.createElement("summary");
    label.textContent = t("panels.scouts_earlier");
    details.appendChild(label);
    for (const [round, id] of earlier) {
      const item = scoutsItem(id);
      const row = document.createElement("div");
      row.className = "scouts-row";
      row.dataset.item = id;
      row.textContent = `${t("panels.scouts_round", { round })} · ${scoutsKindName(item.kind)} · ${item.name}`;
      details.appendChild(row);
    }
    panel.appendChild(details);
  }
}
