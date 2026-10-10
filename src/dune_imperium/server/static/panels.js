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

/* One in-play card's chip. The card the open Agent turn played, or its
   graft partner, carries a "this turn" mark (server view.turn_card_ids,
   sessions.py turn_cards), so it reads apart from a copy of the same card
   played on an earlier turn; while its Agent box still waits
   (view.pending_box_card_ids) the mark's title says trashing it by another
   effect loses the rest of that box (OQ-022, user feedback 2026-10-11; a
   card trashing itself by its own effect keeps its rewards). The mark is no
   .tag, so seatDetailSummary still counts one chip per card, and the chip
   keeps its own hover and click. */
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
    /* Counts that are not already visible on a board track stay at a glance.
       Spice before Solari (user, 2026-10-11: "스파이스/솔라리/물 순으로").
       Immortality p. 16 names the green cube as the Specimen icon. */
    stats.append(
      statNode("victory_point", phraseText("{victory_point}"), player.victory_points),
      statNode("spice", phraseText("{spice}"), player.resources.spice),
      statNode("solari", phraseText("{solari}"), player.resources.solari),
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
    /* The seat's time holding control, ticking on its own (clock.js). */
    if (clocksShown()) pieces.appendChild(seatClockNode(seat));
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
          spaces: player.control_space_ids.map(spaceName).join("/"),
        }),
      );
    }
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
    const agents = player.agent_locations.map(spaceName).join(", ");
    if (agents) seatLine(detail, t("panels.agents_placed_label"), agents);

    const zones = document.createElement("div");
    zones.className = "zones";
    /* The last English line in the seat panel: the zone names are glossary
       terms, so phraseText gives them the same words as everywhere else. */
    const zoneCounts = [
      `{hand} ${player.hand_size}`,
      `{deck} ${player.deck_size}`,
      `{discard_pile} ${player.discard_pile.length}`,
      `{intrigue} ${player.intrigue_card_count}`,
    ];
    /* One unbreakable part per count, its "·" included: in the narrow seat
       column the line then breaks between counts, never inside one. */
    zoneCounts.forEach((count, index) => {
      if (index) zones.append(" ");
      const part = document.createElement("span");
      part.className = "zone-count";
      part.textContent =
        phraseText(count) + (index < zoneCounts.length - 1 ? " ·" : "");
      zones.appendChild(part);
    });
    if (player.discard_pile.length) {
      zones.classList.add("clickable");
      zones.title = t("panels.discard_pile_view");
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
        togglePileViewer({ kind: "discard", seat, mine, opener }, zones);
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
      for (const id of player.active_contract_ids) {
        const tag = chip(id);
        tag.dataset.contract = id;
        /* CHOAM Escort's goods wait on the Contract until it is completed. */
        const tray = scoutsTray(`contract:${id}`, view);
        if (tray) tag.appendChild(tray);
        line.appendChild(tag);
      }
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
   "intrigue_discard" or "deck" (the seat's own); the seat it belongs to
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
   viewer. */
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
    scene.seat === key.scene.seat &&
    scene.cursor === key.scene.cursor;
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
   headed inside, above its cards. */
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
    const row = document.createElement("div");
    row.className = "strip-cards wrap";
    row.append(...section.cards);
    body.append(...(section.notes || []), row);
  });
}

/* What a key shows in the current state, or null when there is nothing to
   show. The openers read the same fields: a seat's public discard pile,
   the Intrigue discard (newest first) and the seat's own deck_cards. */
function pileViewerContent(key) {
  const view = state.view;
  if (!view) return null;
  if (key.kind === "deck") return deckListContent(key, view);
  if (key.kind === "intrigue_discard") {
    const ids = [...(view.intrigue_discard || [])].reverse();
    return pileListContent([[t("board.pile_intrigue_discard"), ids]]);
  }
  const player = view.players.find((p) => p.player === key.seat);
  const title = key.mine
    ? t("panels.my_discard")
    : t("panels.seat_discard", { seat: t("common.seat", { seat: key.seat }) });
  return pileListContent([[title, player ? player.discard_pile : []]]);
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
   the top card only when `peeked_card_id` names one of them (Glowglobes at
   any time, Controlled while its choice is up; core/observation.py), with
   the name of what shows it. */
function deckListState(view) {
  const own = view.players[view.player];
  const deckCards = view.private.deck_cards || [];
  const peeked = view.private.peeked_card_id || "";
  const glowglobes = (own.tech_ids || []).includes("glowglobes");
  const top = peeked && deckCards.includes(peeked)
    ? { id: peeked, source: deckTopSource(glowglobes) }
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
    topNote.textContent = t("panels.deck_list_top_note", { source: top.source });
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

function logEventPayload(payload, eventKind) {
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
    /* Esmar Tuek's Signet Ring, Smuggle Spice, taking a bonus spice off a
       Maker space (rules/leader_abilities.py apply_leader_bonus_spice): the
       payload writes the space's loss, -1, and the spice goes to the
       Signet's player, so the line says so rather than "Bonus spice: -1".
       Placing one on Tuek's Sietch (+1) keeps the plain pair. */
    if (
      key === "bonus_spice" &&
      eventKind === "leader_signet_resolved" &&
      typeof value === "number" &&
      value < 0
    ) {
      parts.push(t("panels.log_bonus_spice_taken", { count: -value }));
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
    /* Seats joined into one string: Rebuild Infrastructure's two payers,
       "0,1" (rules/scouts_effects.py). Named bare, as "player" is. */
    if (key === "players" && typeof value === "string") {
      const seats = value.split(",").filter(Boolean);
      parts.push(seats.map((seat) => t("common.seat", { seat: Number(seat) })).join(", "));
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

/* Event kinds only one Leader's ability emits, so their payload names no
   Leader: the line names the ability and the Leader from the catalog
   (lookup(id, "leaders"), localized by i18n.js) through its own text, whose
   holes are {{ability}} and {{leader}}, in place of the bare "{leader}" of
   EVENT_LABELS (kept for a catalog without the Leader).
   tests/server/test_action_labels.py checks that each kind here has one
   emitter in the engine and that it names this Leader, so a row cannot go
   stale silently.
   - leader_ability_spice_gained: rules/leader_abilities.py
     apply_smuggle_spice pays only staban_tuek, Smuggle Spice [Staban Tuek
     card]. Its Korean particle, 로, follows that ability's name. */
const EVENT_IMPLIED_LEADER = {
  leader_ability_spice_gained: {
    leader: "staban_tuek",
    text: "panels.log_leader_ability_spice_gained",
  },
};

/* An event line's words before the payload. */
function logEventHead(event) {
  const implied = EVENT_IMPLIED_LEADER[event.kind];
  const leader = implied ? lookup(implied.leader, "leaders") : null;
  if (leader && leader.ability) {
    return tNode(implied.text, { ability: leader.ability, leader: leader.name });
  }
  /* phrase(), not textContent: an event label may name a term, and the
     braces must never reach the screen. */
  return phrase(EVENT_LABELS[event.kind] || prettify(event.kind));
}

function logEventLine(event) {
  const line = document.createElement("div");
  line.className = "logevent";
  line.appendChild(logEventHead(event));
  const payload = logEventPayload(event.payload, event.kind);
  if (payload) line.append(` — ${payload}`);
  addLogEventIcon(line, event);
  return line;
}

/* Steps that only close a window; kept in the record but muted:
   finish_agent_turn and finish_reveal end an Agent or Reveal turn,
   pass_combat_intrigue / pass_endgame_intrigue decline a Combat or Endgame
   Intrigue window (rules/combat.py, rules/endgame.py) — the engine never
   emits a bare "pass" — and decline_conflict_end_intrigue a Conflict-end
   window, which opens on public facts, mostly with nothing to play
   (OQ-103). */
const QUIET_ACTIONS = new Set([
  "finish_agent_turn",
  "finish_reveal",
  "pass_combat_intrigue",
  "pass_endgame_intrigue",
  "decline_conflict_end_intrigue",
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
   conflict_won). */
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
  if (kinds.has("leader_ability_spice_gained") || kinds.has("leader_ability_resolved")) {
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
  if (isPauseChance(entry.decision_id)) {
    line.textContent = t("core.pause_step");
    return line;
  }
  let text = t("core.chance_label", { decision: describeChance(entry.decision_id) });
  if (entry.values) {
    const valueName = (value) => chanceValueName(entry.decision_id, value);
    const shown =
      entry.values.length <= 3
        ? entry.values.map(valueName).join(", ")
        : `${entry.values.slice(0, 3).map(valueName).join(", ")} …`;
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
  /* Keep the phrase's text and icons in one inline flow. Appending its
     fragment to the flex head makes each piece a separate wrapping column. */
  const label = document.createElement("span");
  label.className = "turn-action";
  label.appendChild(describeAction(entry));
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

/* An Arrakeen Scouts choice the viewing seat could take nothing from is
   skipped without asking (rules/scouts_effects.py, OQ-071). The log
   records it; this also says so once, in the note, when it arrives. (A new
   High Council seat with no subcommittee left open asks, offering only its
   decline: OQ-076 (c).) */
function noticeScoutsSkips(entries, from) {
  const seat = activeSeat();
  if (typeof seat !== "number") return;
  const notes = [];
  for (const entry of entries) {
    if (entry.index < from || entry.undone || !entry.events) continue;
    for (const event of entry.events) {
      if (!event.payload || event.payload.player !== seat) continue;
      if (event.kind === "scouts_choice_skipped") {
        notes.push(t("panels.scouts_skipped", { item: scoutsItem(event.payload.item_id).name }));
      }
    }
  }
  if (notes.length) note(notes.join(" · "));
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
      noticeScoutsSkips(log.entries, logSeen.freshFrom);
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

/* Controlled's choice on the deck's top card (rules/intrigue.py, the
   PeekTopCard choice): these actions are offered exactly while that choice
   is up for the seat. Their live buttons name the card the seat is looking
   at (deckTopChoiceLabel, the text keyed here); the logged step keeps its
   plain label (ACTION_LABELS), since the log is everyone's to read. */
const DECK_TOP_CHOICE_TEXT = {
  put_back_top_card: "panels.deck_top_put_back",
  discard_top_card: "panels.deck_top_discard",
  draw_top_card_for_solari: "panels.deck_top_draw",
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
function deckTopSource(glowglobes) {
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
  panel.textContent = "";
  const heading = document.createElement("h2");
  heading.textContent = t("panels.scouts_heading");
  panel.appendChild(heading);

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
