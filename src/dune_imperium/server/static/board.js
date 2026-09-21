"use strict";

/* ---------- board ---------- */

function boardOccupancy(view) {
  const occupants = new Map();
  const controllers = new Map();
  const spies = new Map();
  for (const player of view.players) {
    for (const spaceId of player.agent_locations) {
      if (!occupants.has(spaceId)) occupants.set(spaceId, []);
      occupants.get(spaceId).push(player.player);
    }
    for (const spaceId of player.control_space_ids) {
      controllers.set(spaceId, player.player);
    }
    for (const postId of player.spy_post_ids) {
      if (!spies.has(postId)) spies.set(postId, []);
      spies.get(postId).push(player.player);
    }
  }
  return { occupants, controllers, spies };
}

function seatToken(seat, className) {
  const token = document.createElement("span");
  token.className = className;
  token.style.background = SEAT_COLORS[seat];
  token.textContent = String(seat);
  token.title = t("common.seat", { seat });
  token.setAttribute("role", "img");
  token.setAttribute("aria-label", t("common.seat", { seat }));
  token.dataset.seat = String(seat);
  return token;
}

/* Agent tokens keyed by seat and space, with their screen rectangles, so
   a re-render can animate the ones that were just placed. */
function agentTokenRects(board) {
  const rects = new Map();
  for (const hotspot of board.querySelectorAll(".hotspot")) {
    for (const token of hotspot.querySelectorAll(".agent-token")) {
      rects.set(
        `${token.dataset.seat}:${hotspot.dataset.space}`,
        token.getBoundingClientRect()
      );
    }
  }
  return rects;
}

/* A newly placed Agent token flies in from its seat's mark in the seat
   panel (FLIP: start translated at the origin, then transition to rest).
   Tokens that were already on their space, and the first paint of a
   board, stay still. */
function animatePlacedAgents(board, before) {
  if (before === null) return;
  for (const hotspot of board.querySelectorAll(".hotspot")) {
    for (const token of hotspot.querySelectorAll(".agent-token")) {
      if (before.has(`${token.dataset.seat}:${hotspot.dataset.space}`)) continue;
      const origin = document.querySelector(
        `#seats .seat[data-seat="${token.dataset.seat}"] .seat-mark`
      );
      const target = token.getBoundingClientRect();
      if (!origin || !target.width) {
        token.classList.add("placed");
        continue;
      }
      const from = origin.getBoundingClientRect();
      const dx = from.left + from.width / 2 - (target.left + target.width / 2);
      const dy = from.top + from.height / 2 - (target.top + target.height / 2);
      token.style.transition = "none";
      token.style.transform = `translate(${dx}px, ${dy}px) scale(0.7)`;
      token.getBoundingClientRect();
      token.style.transition = "";
      token.classList.add("flying");
      token.style.transform = "";
      token.addEventListener(
        "transitionend",
        () => token.classList.remove("flying"),
        { once: true }
      );
    }
  }
}

function renderBoard() {
  const board = el("board");
  const before = board.querySelector(".board-stage") ? agentTokenRects(board) : null;
  board.textContent = "";
  const view = state.view;
  if (!view) {
    const note = document.createElement("span");
    note.className = "muted";
    note.textContent = t("board.no_human_seats");
    board.appendChild(note);
    return;
  }
  if (state.catalog.board_image) {
    renderBoardStage(board, view);
    animatePlacedAgents(board, before);
  } else {
    renderSpaceList(board, view);
  }
}

/* A picture laid on the board scan at a box (percent of the stage). */
function boardPiece(src, box, className) {
  const [left, top, width, height] = box;
  const piece = document.createElement("img");
  piece.className = className;
  piece.src = src;
  piece.alt = "";
  piece.draggable = false;
  piece.style.left = `${left}%`;
  piece.style.top = `${top}%`;
  piece.style.width = `${width}%`;
  piece.style.height = `${height}%`;
  return piece;
}

/* Where the board prints the flag under a controllable space
   (catalog.tracks.control_flags, a percent box), if it does. */
function controlFlagBox(spaceId) {
  const flags = state.catalog.tracks && state.catalog.tracks.control_flags;
  return (flags && flags.boxes[spaceId]) || null;
}

/* A seat's Control marker: "place your Control marker on the flag below
   that space" [Main p. 20]. It is the printed pennant's own shape and size,
   flat in the seat's colour like every other player token. */
function controlMarker(seat, spaceId, box) {
  const svgNs = "http://www.w3.org/2000/svg";
  const [left, top, width, height] = box;
  const dip = 100 * (1 - state.catalog.tracks.control_flags.notch);
  const marker = document.createElementNS(svgNs, "svg");
  marker.setAttribute("class", "control-marker");
  marker.setAttribute("viewBox", "0 0 100 100");
  marker.setAttribute("preserveAspectRatio", "none");
  marker.dataset.seat = String(seat);
  marker.dataset.space = spaceId;
  marker.style.left = `${left}%`;
  marker.style.top = `${top}%`;
  marker.style.width = `${width}%`;
  marker.style.height = `${height}%`;
  const title = document.createElementNS(svgNs, "title");
  title.textContent = t("board.control_seat_space", { seat, name: nameOf(spaceId) });
  const pennant = document.createElementNS(svgNs, "polygon");
  pennant.setAttribute("points", `0,0 100,0 100,100 50,${dip} 0,100`);
  pennant.setAttribute("fill", SEAT_COLORS[seat]);
  marker.append(title, pennant);
  return marker;
}

/* The centre of the hexagon a Maker space prints for its bonus spice
   (catalog.tracks.maker_spice), if the layout has one for the space. */
function makerSpicePoint(spaceId) {
  const spots = state.catalog.tracks && state.catalog.tracks.maker_spice;
  return (spots && spots.points[spaceId]) || null;
}

/* The bonus spice waiting on a Maker space, "in the spot designated for
   bonus spice" [Main p. 15]: a spice hexagon exactly over the printed one,
   with the amount in it like the board's own spice numbers. */
function bonusSpiceToken(spaceId, count, point) {
  const [width, height] = state.catalog.tracks.maker_spice.size;
  const token = document.createElement("span");
  token.className = "bonus-spice";
  token.dataset.space = spaceId;
  token.title = `${nameOf(spaceId)} · bonus spice ${count}`;
  token.style.width = `${width}%`;
  token.style.height = `${height}%`;
  const amountText = document.createElement("span");
  amountText.className = "bonus-spice-count" + (count > 9 ? " wide" : "");
  amountText.textContent = String(count);
  token.appendChild(amountText);
  return placeAt(token, point[0], point[1]);
}

/* The scanned board with the live state on top: a hotspot per space
   (catalog.spaces[id].box, percent of the image), Agent tokens, Control
   flags, Maker bonus spice, and Spies on the observation posts. */
function renderBoardStage(board, view) {
  const stage = document.createElement("div");
  stage.className = "board-stage";
  const map = document.createElement("img");
  map.className = "board-map";
  map.src = state.catalog.board_image;
  map.alt = "Dune: Imperium — Uprising board";
  map.draggable = false;
  stage.appendChild(map);

  const { occupants, controllers, spies } = boardOccupancy(view);
  const makerSpice = new Map(view.maker_bonus_spice);

  /* Pieces that lie on the board, under the hotspots and the tokens. The
     Shield Wall token stays on its marked position until a player removes
     it [Main pp. 4, 10]; a Leader's tile in play and Immortality's overlay
     tile are pictures the scan does not have. */
  const wall = state.catalog.shield_wall;
  if (view.shield_wall_present && wall && wall.image) {
    const token = boardPiece(wall.image, wall.box, "shield-wall-token");
    token.alt = "Shield Wall";
    token.style.transform = `rotate(${wall.rotation}deg)`;
    stage.appendChild(token);
  }
  for (const entry of Object.values(state.catalog.spaces)) {
    if (!spaceInPlay(entry, view)) continue;
    const overlay = spaceOverlayFor(entry);
    if (overlay && overlay.image) {
      stage.appendChild(boardPiece(overlay.image, overlay.tile_box, "board-tile"));
    } else if (entry.tile_box && entry.image) {
      stage.appendChild(boardPiece(entry.image, entry.tile_box, "board-tile"));
    }
  }

  for (const [spaceId, entry] of Object.entries(state.catalog.spaces)) {
    if (!spaceInPlay(entry, view)) continue;
    const [left, top, width, height] = entry.box;
    const hotspot = document.createElement("button");
    hotspot.type = "button";
    hotspot.className = "hotspot";
    hotspot.style.left = `${left}%`;
    hotspot.style.top = `${top}%`;
    hotspot.style.width = `${width}%`;
    hotspot.style.height = `${height}%`;
    hotspot.title = entry.name;
    hotspot.dataset.space = spaceId;
    hotspot.setAttribute("aria-label", entry.name);
    const legal = legalActionsFor(spaceId);
    if (legal.length) hotspot.classList.add("legal");
    if (state.pick && state.pick.spaceId === spaceId) hotspot.classList.add("picked");
    else if (pickAlternative(spaceId, "spaceId")) hotspot.classList.add("alternative");
    if (!spaceImplementedFor(entry)) hotspot.classList.add("unimplemented");
    const seats = occupants.get(spaceId) || [];
    if (seats.length) {
      const tokens = document.createElement("span");
      tokens.className = "agent-tokens";
      for (const seat of seats) tokens.appendChild(seatToken(seat, "agent-token"));
      hotspot.appendChild(tokens);
    }
    /* The Control marker and the bonus spice lie on their printed places
       (drawn below, outside the hotspot); a space the layout has no place
       for keeps the mark inside its hotspot. */
    if (controllers.has(spaceId) && !controlFlagBox(spaceId)) {
      const flag = seatToken(controllers.get(spaceId), "control-flag");
      flag.title = t("board.control_seat", { seat: controllers.get(spaceId) });
      hotspot.appendChild(flag);
    }
    if (makerSpice.get(spaceId) && !makerSpicePoint(spaceId)) {
      const bonus = amount("spice", "bonus spice", makerSpice.get(spaceId));
      bonus.classList.add("maker-bonus");
      hotspot.appendChild(bonus);
    }
    if ((view.sardaukar_commander_space_ids || []).includes(spaceId)) {
      /* A Sardaukar Commander waits on the space: 2 Solari with a visit
         [Bloodlines p. 4]. */
      const mark = document.createElement("span");
      mark.className = "commander-mark";
      mark.textContent = "C";
      mark.title = "Sardaukar Commander (2 Solari)";
      hotspot.appendChild(mark);
    }
    hotspot.addEventListener("click", (event) => {
      event.stopPropagation();
      tableClick(spaceId, entry, hotspot);
    });
    hoverPopover(hotspot, () => entry);
    stage.appendChild(hotspot);
  }

  for (const [spaceId, seat] of controllers) {
    const box = controlFlagBox(spaceId);
    if (box) stage.appendChild(controlMarker(seat, spaceId, box));
  }
  for (const [spaceId, count] of makerSpice) {
    const point = makerSpicePoint(spaceId);
    if (count && point) stage.appendChild(bonusSpiceToken(spaceId, count, point));
  }

  for (const [postId, [x, y]] of Object.entries(state.catalog.posts)) {
    const seats = spies.get(postId) || [];
    if (!seats.length) continue;
    const post = document.createElement("span");
    post.className = "spy-post";
    post.style.left = `${x}%`;
    post.style.top = `${y}%`;
    post.title = t("board.post_seats", { post: prettify(postId), seats: seats.join(", ") });
    for (const seat of seats) post.appendChild(seatToken(seat, "spy-token"));
    stage.appendChild(post);
  }

  if (!view.shield_wall_present) {
    const note = document.createElement("span");
    note.className = "board-note";
    note.appendChild(tNode("board.shield_wall_destroyed"));
    stage.appendChild(note);
  }
  renderSlotCards(stage, view);
  renderTrackMarkers(stage, view);
  board.appendChild(stage);
}

/* The Conflict card and the face-up CHOAM contracts drawn in their printed
   slots (catalog.tracks.conflict_slot / contract_slots, percent boxes).
   Every card is centred on its slot and drawn before the live markers so
   the unit counts stay on top. The Conflict card fills its portrait frame;
   the landscape contracts are drawn a little larger than their slot
   because the dark band around it is empty. Shaddam's set-aside Sardaukar
   contracts have no printed home and stay in the market strip. */
const CONTRACT_SLOT_SCALE = 1.2;

function renderSlotCards(stage, view) {
  const tracks = state.catalog.tracks;
  if (!tracks || !tracks.conflict_slot) return;

  const [cLeft, cTop, cWidth, cHeight] = tracks.conflict_slot;
  for (const id of view.current_conflict_ids) {
    const card = visualCard(id, { className: "conflict slot-card" });
    card.style.width = `${cWidth}%`;
    placeAt(card, cLeft + cWidth / 2, cTop + cHeight / 2);
    stage.appendChild(card);
  }
  if (view.conflict_deck_size > 0 && tracks.conflict_deck_slot) {
    const [dLeft, dTop, dWidth, dHeight] = tracks.conflict_deck_slot;
    const deck = document.createElement("div");
    deck.className = "slot-deck";
    deck.style.width = `${dWidth}%`;
    deck.style.height = `${dHeight}%`;
    deck.title = t("board.conflict_deck_remaining", { count: view.conflict_deck_size });
    const count = document.createElement("span");
    count.className = "slot-deck-count";
    count.textContent = String(view.conflict_deck_size);
    deck.append(icon("sword", "Conflict"), count);
    placeAt(deck, dLeft + dWidth / 2, dTop + dHeight / 2);
    stage.appendChild(deck);
  }

  if (!state.summary.choam_module) return;
  view.face_up_contract_ids.forEach((id, index) => {
    const box = tracks.contract_slots[index];
    if (!box) return;
    const [left, top, width, height] = box;
    const card = visualCard(id, { className: "contract slot-card" });
    card.style.width = `${width * CONTRACT_SLOT_SCALE}%`;
    placeAt(card, left + width / 2, top + height / 2);
    stage.appendChild(card);
  });
  const [left, top, width, height] = tracks.contract_slots[tracks.contract_slots.length - 1];
  const bank = document.createElement("span");
  bank.className = "slot-bank";
  bank.title = "face-down contract bank";
  bank.append(icon("contract", "Contract"), ` bank ${view.contract_bank_size}`);
  const overhang = (width * (CONTRACT_SLOT_SCALE - 1)) / 2;
  placeAt(bank, left + width + overhang + 0.8, top + height / 2);
  stage.appendChild(bank);
}

function placeAt(node, x, y) {
  node.style.left = `${x}%`;
  node.style.top = `${y}%`;
  return node;
}

/* The printed cell a strength is shown on: 0 is the framed square, and a
   strength beyond 20 counts on from 1 on the token's "+20" face [Main
   p. 12]. The token has that one flip, so 41 and up stay on 20. */
function strengthCell(strength) {
  if (strength <= 0) return 0;
  return Math.min(strength > 20 ? strength - 20 : strength, 20);
}

/* A seat's pictured Combat marker: one face of the owner's token picture,
   sized as a percent of the stage so it keeps to its cell at any zoom. */
function strengthPicture(seat, src, size) {
  const token = document.createElement("span");
  token.className = "strength-token pictured";
  token.dataset.seat = String(seat);
  token.style.width = `${size}%`;
  token.style.borderColor = SEAT_COLORS[seat];
  const face = document.createElement("img");
  face.src = src;
  face.alt = "";
  face.draggable = false;
  token.appendChild(face);
  return token;
}

/* The player disc: the one common round token in a seat's colour — the
   Score marker and the Councilor token on the board, the research and
   Tleilaxu track tokens on the Bene Tleilax board. Flat colour, no seat
   number. `size` is its diameter as a percent of the stage it lies on
   (the diameter of the spot that board prints for it); without a size it
   is an inline disc for the text layouts. */
function seatDisc(seat, className, size) {
  const disc = document.createElement("span");
  disc.className = `seat-disc ${className}`;
  disc.dataset.seat = String(seat);
  if (size !== undefined) disc.style.width = `${size}%`;
  disc.style.backgroundColor = SEAT_COLORS[seat];
  return disc;
}

/* The cell of the Score track a score is shown on: its printed number, or
   one shared place on the emblem above the last number for anything higher. */
function scoreLevel(vp, tracks) {
  return Math.max(0, Math.min(vp, tracks.victory_points.levels.length));
}

/* Half the distance between two discs of `size` that share `room`: side by
   side with a hair between them when the room allows it, overlapping just
   enough to stay inside it when it does not. */
function discHalfGap(size, room) {
  return Math.max(0, Math.min(size / 2 + 0.05, (room - size) / 2));
}

/* Offsets that lay `count` discs around a point: alone on the point, a pair
   side by side, a triangle, a 2×2 (a fifth disc and on would reuse the
   places). `fromTop` keeps the first row on the point and puts the second
   row under it, for spots where a lone disc must leave the print below it
   readable; `upright` stands a pair one above the other, for room too
   narrow to show two discs side by side. */
function discCluster(count, halfX, halfY, { fromTop = false, upright = false } = {}) {
  let places;
  if (count <= 1) places = [[0, 0]];
  else if (count === 2) places = upright ? [[0, -halfY], [0, halfY]] : [[-halfX, 0], [halfX, 0]];
  else if (count === 3) places = [[-halfX, -halfY], [halfX, -halfY], [0, halfY]];
  else places = [[-halfX, -halfY], [halfX, -halfY], [-halfX, halfY], [halfX, halfY]];
  const twoRows = count >= 3 || (count === 2 && upright);
  const lift = fromTop && twoRows ? halfY : 0;
  return Array.from({ length: Math.max(count, 1) }, (_, index) => {
    const [dx, dy] = places[index % places.length];
    return [dx, dy + lift];
  });
}

/* A Faction's Alliance token: its picture (catalog.alliance_tokens) cut to
   the round token, or a drawn disc with the Faction's emblem without the
   owner's token pictures. With a `size` (percent of the stage) it lies on
   the board; without one it is an inline token for the seat panels. */
function allianceToken(key, size, holder) {
  const token = document.createElement("span");
  token.className = "alliance-token";
  token.dataset.faction = key;
  token.dataset.holder = holder === undefined ? "" : String(holder);
  token.title = `${FACTION_LABELS[key]} Alliance`;
  if (size !== undefined) token.style.width = `${size}%`;
  else token.classList.add("inline");
  const url = (state.catalog.alliance_tokens || {})[key];
  if (url) {
    const face = document.createElement("img");
    face.src = url;
    face.alt = "";
    face.draggable = false;
    token.appendChild(face);
  } else {
    token.classList.add("drawn");
    token.appendChild(icon(`influence_${key}`, `${FACTION_LABELS[key]} Alliance`));
  }
  return token;
}

/* Where each Faction's Alliance token is on the screen and who holds it
   ("" on the board), so a render can tell a token that changed hands. */
function allianceTokenPlaces() {
  const places = new Map();
  for (const token of document.querySelectorAll(".alliance-token:not(.flying)")) {
    const rect = token.getBoundingClientRect();
    if (rect.width) places.set(token.dataset.faction, { holder: token.dataset.holder, rect });
  }
  return places;
}

/* An Alliance token that changed hands — earned from the board, taken over
   by a seat that passed its holder, or returned [Main p. 7] [FAQ p. 1] —
   flies from where it lay to where it lies now. The flight is a copy above
   the page (the seat panels scroll and would clip the token itself). */
function animateMovedAllianceTokens(before) {
  if (!before.size) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  for (const token of document.querySelectorAll(".alliance-token:not(.flying)")) {
    const was = before.get(token.dataset.faction);
    const to = token.getBoundingClientRect();
    if (!was || was.holder === token.dataset.holder || !to.width) continue;
    const ghost = token.cloneNode(true);
    ghost.classList.remove("inline");
    ghost.classList.add("flying");
    const lay = (rect) => {
      ghost.style.left = `${rect.left}px`;
      ghost.style.top = `${rect.top}px`;
      ghost.style.width = `${rect.width}px`;
    };
    lay(was.rect);
    document.body.appendChild(ghost);
    token.style.visibility = "hidden";
    ghost.getBoundingClientRect();
    ghost.classList.add("moving");
    lay(to);
    const land = () => {
      ghost.remove();
      token.style.visibility = "";
    };
    ghost.addEventListener("transitionend", land, { once: true });
    setTimeout(land, 1200);
  }
}

/* A seat's Maker Hooks token in the slot its garrison prints for it: "Place
   it on your garrison" [Main p. 20]. The picture is turned (and mirrored)
   into the slot, so its long side lies along the slot's height; without the
   picture the rulebook icon marks the slot. */
function makerHooksToken(seat, layout) {
  const [x, y] = layout.points[seat] || layout.points[0];
  const [width, height] = layout.size;
  const url = state.catalog.maker_hooks_token;
  let token;
  if (url) {
    const turn = layout.turns[seat] || layout.turns[0];
    token = document.createElement("img");
    token.className = "maker-hooks-token";
    token.src = url;
    token.alt = "Maker Hooks";
    token.draggable = false;
    token.style.width = `${height}%`;
    token.style.transform =
      `translate(-50%, -50%) rotate(${turn.rotation}deg)` + (turn.mirrored ? " scaleX(-1)" : "");
  } else {
    token = document.createElement("span");
    token.className = "maker-hooks-token drawn";
    token.style.width = `${width}%`;
    token.style.height = `${height}%`;
    token.appendChild(icon("maker_hooks", "Maker Hooks"));
  }
  token.dataset.seat = String(seat);
  token.title = t("board.seat_maker_hooks", { seat });
  return placeAt(token, x, y);
}

/* Live markers on the printed tracks (catalog.tracks, percent of the
   scan): Influence cubes and Alliance rings on the Faction strips, VP
   tokens on the score column, strength tokens on the combat track, deployed
   units in each seat's Conflict quadrant, and Councilor tokens on the High
   Council seats. */
function renderTrackMarkers(stage, view) {
  const tracks = state.catalog.tracks;
  if (!tracks || !Array.isArray(view.players)) return;
  const factions = Object.keys(FACTION_LABELS);
  let councilSlot = 0;
  /* The seats on each cell of the combat track and of the Score track, in
     seat order. */
  const strengthStacks = new Map();
  const scoreStacks = new Map();
  view.players.forEach((player, index) => {
    const seat = typeof player.player_id === "number" ? player.player_id : index;
    const shown = strengthCell(player.combat_strength || 0);
    if (!strengthStacks.has(shown)) strengthStacks.set(shown, []);
    strengthStacks.get(shown).push(seat);
    const level = scoreLevel(player.victory_points || 0, tracks);
    if (!scoreStacks.has(level)) scoreStacks.set(level, []);
    scoreStacks.get(level).push(seat);
  });
  /* An Alliance token lies on the marked ring of its Faction's strip until a
     player earns it and takes it into their supply [Main pp. 4, 7] (it then
     shows on that seat's panel); the vacated ring takes the holder's colour. */
  for (const key of factions) {
    const offset = tracks.influence.offsets[key];
    if (offset === undefined) continue;
    const [ax, ay] = tracks.influence.alliance;
    const size = tracks.influence.alliance_size;
    const holder = view.players.find((p) => (p.alliance_faction_ids || []).includes(key));
    if (holder) {
      const ring = document.createElement("span");
      ring.className = "alliance-ring";
      ring.dataset.faction = key;
      if (size !== undefined) ring.style.width = `${size}%`;
      ring.style.borderColor = SEAT_COLORS[holder.player];
      ring.title = t("board.alliance_holder", { seat: holder.player, faction: FACTION_LABELS[key] });
      stage.appendChild(placeAt(ring, ax, ay + offset));
    } else {
      stage.appendChild(placeAt(allianceToken(key, size), ax, ay + offset));
    }
  }

  view.players.forEach((player, index) => {
    const seat = typeof player.player_id === "number" ? player.player_id : index;
    const color = SEAT_COLORS[seat];

    for (const key of factions) {
      const offset = tracks.influence.offsets[key];
      if (offset === undefined) continue;
      const level = Math.max(0, Math.min(6, player.influence[key] || 0));
      /* The cube is exactly the square the strip prints for it (its
         width is a percent of the stage, like the player disc). */
      const cube = document.createElement("span");
      cube.className = "track-cube";
      cube.style.width = `${tracks.influence.cube_size}%`;
      cube.style.background = color;
      cube.title = t("board.influence_cube", {
        seat,
        faction: FACTION_LABELS[key],
        level: player.influence[key],
      });
      placeAt(cube, tracks.influence.seat_x[seat], tracks.influence.levels[level] + offset);
      stage.appendChild(cube);
    }

    /* A Score marker alone on its score lies on the centre of the cell, so
       its height reads as the score. The disc is as large as on the table
       (a cell holds one), so seats that share a score cluster around that
       centre and overlap just enough to stay inside the cell. */
    const vp = player.victory_points || 0;
    const vpToken = seatDisc(seat, "vp-token", tracks.disc_size);
    vpToken.title = t("board.seat_vp", { seat, vp });
    const level = scoreLevel(vp, tracks);
    const vpY = level < tracks.victory_points.levels.length
      ? tracks.victory_points.levels[level]
      : tracks.victory_points.overflow_y;
    const together = scoreStacks.get(level);
    const [cellWidth, cellHeight] = tracks.victory_points.cell;
    const [vpDx, vpDy] = discCluster(
      together.length,
      discHalfGap(tracks.disc_size, cellWidth),
      discHalfGap(tracks.disc_size, cellHeight),
    )[together.indexOf(seat)];
    placeAt(vpToken, tracks.victory_points.x + vpDx, vpY + vpDy);
    stage.appendChild(vpToken);

    const units =
      (player.troops_conflict || 0) +
      (player.sandworms_conflict || 0) +
      (player.commanders_conflict || 0) +
      (player.agent_in_conflict || 0);
    /* Every seat's strength token is always on the track: in the framed
       square left of 1/11 at strength 0 (four tokens in a 2×2), on the
       printed number otherwise, and on its "+20" face beyond 20 (23 is
       the token on 3 showing +20). With the owner's token pictures
       (catalog.strength_tokens) it is the picture of that face, lying in
       the open part of its cell like the marker on the table, and seats
       that share a cell fan out so that every colour stays in sight. */
    const strength = player.combat_strength || 0;
    const flipped = strength > 20;
    const shown = strengthCell(strength);
    const faces = (state.catalog.strength_tokens || [])[seat];
    const token = faces
      ? strengthPicture(seat, flipped ? faces.plus20 : faces.front, tracks.strength.token_size)
      : seatToken(seat, "track-token strength-token");
    token.title = t("board.seat_strength", { seat, strength });
    if (shown === 0) {
      const [zx, zy, zw, zh] = tracks.strength.zero_box;
      const inset = faces ? 0.25 : 0.3;
      placeAt(
        token,
        zx + zw * (inset + (seat % 2) * (1 - 2 * inset)),
        zy + zh * (inset + Math.floor(seat / 2) * (1 - 2 * inset)),
      );
    } else {
      const row = shown > 10 ? 1 : 0;
      const cell = shown > 10 ? shown - 10 : shown;
      if (faces) {
        /* The fan may lap about half a percent over each neighbour (a
           cell is 3.75 wide, the widest fan 4.95), which keeps a strip of
           every tied colour visible at the size of a 3% token. */
        const sharing = strengthStacks.get(shown);
        const step = sharing.length > 1 ? Math.min(1.1, 1.95 / (sharing.length - 1)) : 0;
        const shift = (sharing.indexOf(seat) - (sharing.length - 1) / 2) * step;
        placeAt(token, tracks.strength.cells[cell] + shift, tracks.strength.token_rows[row] - shift * 0.35);
      } else {
        if (flipped) {
          token.classList.add("flipped");
          const plus = document.createElement("span");
          plus.className = "strength-plus";
          plus.textContent = "+20";
          token.appendChild(plus);
        }
        placeAt(token, tracks.strength.cells[cell] + (seat - 1.5) * 0.9, tracks.strength.rows[row]);
      }
    }
    stage.appendChild(token);

    /* Garrison count in the seat's bracketed circle (always shown), and
       the units deployed this round in the seat's quadrant of the central
       field, with the strength [Main p. 10]. */
    const [gx, gy] = tracks.garrisons[seat] || tracks.garrisons[0];
    const garrison = document.createElement("div");
    garrison.className = "force-chip garrison";
    garrison.style.borderColor = color;
    garrison.title = t("board.seat_garrison", { seat, count: player.troops_garrison || 0 });
    garrison.append(
      seatToken(seat, "seat-mark"),
      amount("troop", "garrison troop", player.troops_garrison || 0)
    );
    if (player.commanders_garrison) {
      const commanders = document.createElement("span");
      commanders.className = "commander-count";
      commanders.title = `Sardaukar Commander ${player.commanders_garrison}`;
      commanders.textContent = `C${player.commanders_garrison}`;
      garrison.appendChild(commanders);
    }
    placeAt(garrison, gx, gy);
    stage.appendChild(garrison);
    if (player.maker_hooks && tracks.maker_hooks) {
      stage.appendChild(makerHooksToken(seat, tracks.maker_hooks));
    }

    if (units > 0) {
      const [qx, qy] = tracks.conflict_quadrants[seat] || tracks.conflict_quadrants[0];
      const deployed = document.createElement("div");
      deployed.className = "force-chip deployed";
      deployed.style.borderColor = color;
      deployed.title = t("board.seat_conflict_troops", { seat });
      deployed.appendChild(seatToken(seat, "seat-mark"));
      if (player.troops_conflict) {
        deployed.appendChild(amount("troop", "Conflict troop", player.troops_conflict));
      }
      if (player.sandworms_conflict) {
        deployed.appendChild(amount("sandworm", "sandworm", player.sandworms_conflict));
      }
      if (player.commanders_conflict) {
        const commanders = document.createElement("span");
        commanders.className = "commander-count";
        commanders.title = `Sardaukar Commander ${player.commanders_conflict}`;
        commanders.textContent = `C${player.commanders_conflict}`;
        deployed.appendChild(commanders);
      }
      if (player.agent_in_conflict) {
        deployed.appendChild(amount("agent", "Agent (Into the Fray)", player.agent_in_conflict));
      }
      if (strength) {
        const total = document.createElement("span");
        total.className = "force-strength";
        total.title = t("board.total_strength", { strength });
        total.textContent = String(strength);
        deployed.appendChild(total);
      }
      placeAt(deployed, qx, qy);
      stage.appendChild(deployed);
    }

    /* The seat to move sends and takes back its units right here: the same
       count rows as in the panel, by the seat's quadrant (above the upper
       seats, under the lower ones, clear of the units chip). */
    if (seat === state.viewSeat && !state.review && state.actions) {
      const families = countFamilies(state.actions.actions);
      const rows = [...families.entries()].filter(([id]) => FORCE_STEPPER_ACTIONS.has(id));
      if (rows.length) {
        const [sx, sy] = tracks.conflict_quadrants[seat] || tracks.conflict_quadrants[0];
        const control = document.createElement("div");
        control.className = "force-stepper";
        control.style.borderColor = color;
        for (const [id, family] of rows) control.appendChild(countRow(id, family, true));
        placeAt(control, sx, sy + (sy > 77 ? 4.6 : -4.6));
        stage.appendChild(control);
      }
    }

    if (player.high_council && councilSlot < tracks.council_seats.length) {
      const [cx, cy] = tracks.council_seats[councilSlot];
      councilSlot += 1;
      const token = seatDisc(seat, "council-token", tracks.disc_size);
      token.title = t("board.seat_high_council", { seat });
      placeAt(token, cx, cy);
      stage.appendChild(token);
    }
  });
}

/* Text board for a machine without the board scan: the same data as a
   list, grouped by Agent icon, with the live occupancy inline. */
function renderSpaceList(board, view) {
  const catalog = state.catalog;
  const heading = document.createElement("h2");
  heading.textContent = t("board.board_spaces_heading");
  board.appendChild(heading);
  const hint = document.createElement("div");
  hint.className = "muted";
  hint.textContent = t("board.board_scan_missing");
  board.appendChild(hint);
  const { occupants, controllers } = boardOccupancy(view);
  const makerSpice = new Map(view.maker_bonus_spice);

  for (const [iconId, label] of AGENT_ICON_GROUPS) {
    const spaceIds = Object.keys(catalog.spaces).filter(
      (spaceId) =>
        catalog.spaces[spaceId].agent_icon === iconId &&
        spaceInPlay(catalog.spaces[spaceId], view)
    );
    if (!spaceIds.length) continue;
    const body = section(board, label);
    for (const spaceId of spaceIds) {
      body.appendChild(spaceRow(spaceId, occupants, controllers, makerSpice));
    }
  }
}

function spaceRow(spaceId, occupants, controllers, makerSpice) {
  const entry = state.catalog.spaces[spaceId];
  const row = document.createElement("div");
  row.className = "space-row";
  if (legalActionsFor(spaceId).length) row.classList.add("legal");
  if (state.pick && state.pick.spaceId === spaceId) row.classList.add("picked");
  row.dataset.space = spaceId;

  const title = document.createElement("div");
  title.appendChild(chip(spaceId, entry));
  const flags = [];
  if (entry.combat) flags.push("⚔ Combat");
  if (entry.maker) flags.push("Maker");
  if (entry.critical) flags.push("Control");
  if (flags.length) {
    const flagLine = document.createElement("div");
    flagLine.className = "muted";
    flagLine.textContent = flags.join(" · ");
    title.appendChild(flagLine);
  }
  if (!spaceImplementedFor(entry)) {
    const badge = document.createElement("span");
    badge.className = "badge-unimpl";
    badge.textContent = t("board.unimplemented_badge");
    title.appendChild(badge);
  }
  row.appendChild(title);

  const detail = document.createElement("div");
  if (entry.requirement) detail.appendChild(requirementNode(entry.requirement));
  for (const option of spaceOptionsFor(entry)) detail.appendChild(spaceOptionLine(option));
  for (const noteText of entry.notes) detail.appendChild(iconLine(noteText, "muted"));
  const status = [];
  const seats = occupants.get(spaceId);
  if (seats && seats.length) {
    status.push(
      t("board.agent_seats", {
        seats: seats.map((seat) => t("common.seat", { seat })).join(", "),
      }),
    );
  }
  if (controllers.has(spaceId)) {
    status.push(t("board.control_seat", { seat: controllers.get(spaceId) }));
  }
  if (makerSpice.get(spaceId)) {
    status.push(`bonus spice ${makerSpice.get(spaceId)}`);
  }
  if (status.length) {
    const line = document.createElement("div");
    line.className = "space-status";
    line.textContent = status.join(" · ");
    detail.appendChild(line);
  }
  row.appendChild(detail);
  row.addEventListener("click", (event) => {
    if (event.target.closest(".tag")) return;
    tableClick(spaceId, entry, row);
  });
  hoverPopover(row, () => entry);
  return row;
}

/* ---------- market strip (shared table zones) ---------- */

/* One card as its printed image (or a text card without the cache), lit
   when a legal action references it; a click applies or focuses. */
function visualCard(instanceId, options = {}) {
  const entry = options.entry || lookup(baseId(instanceId));
  const card = document.createElement("button");
  card.type = "button";
  card.className = "vcard" + (options.className ? ` ${options.className}` : "");
  card.dataset.instance = instanceId;
  const legal = legalActionsFor(instanceId);
  if (legal.length) card.classList.add("legal");
  if (state.pick && (state.pick.cardId === instanceId || state.pick.partnerId === instanceId)) {
    card.classList.add("picked");
  } else if (partnerCandidate(instanceId)) {
    card.classList.add("partner");
  } else if (pickAlternative(instanceId, "cardId")) {
    card.classList.add("alternative");
  }
  if (entry && entry.image) {
    const image = document.createElement("img");
    image.src = entry.image;
    image.alt = entry.name;
    image.loading = "lazy";
    image.draggable = false;
    card.appendChild(image);
  } else {
    card.classList.add("textcard");
    const name = document.createElement("span");
    name.className = "vcard-name";
    name.textContent = entry ? entry.name : prettify(baseId(instanceId));
    card.appendChild(name);
    const detail = cardDetail(instanceId);
    if (detail) {
      const meta = document.createElement("span");
      meta.className = "vcard-meta";
      meta.textContent = detail;
      card.appendChild(meta);
    }
  }
  if (options.badge) {
    const badge = document.createElement("span");
    badge.className = "vcard-badge";
    badge.textContent = options.badge;
    card.appendChild(badge);
  }
  card.title = entry ? entry.name : nameOf(instanceId);
  card.addEventListener("click", (event) => {
    event.stopPropagation();
    if (options.onClick) options.onClick(entry, card);
    else tableClick(instanceId, entry, card);
  });
  hoverPopover(card, () => entry);
  return card;
}

/* ---------- collapsing the shared card columns ---------- */

/* Which columns the viewer has folded away. #market is rebuilt by every
   render, so this cannot live in the DOM; it is remembered per browser, the
   way a collapsed panel should be. Keyed by the heading's stable part, since
   the counts in it change every turn ("Tleilaxu Row · deck 16" is still the
   Tleilaxu Row). */
const COLLAPSED_KEY = "dune.collapsedStrips";
let collapsedStrips = new Set();

function loadCollapsedStrips() {
  try {
    const stored = JSON.parse(storageGet(COLLAPSED_KEY) || "[]");
    collapsedStrips = new Set(Array.isArray(stored) ? stored : []);
  } catch (error) {
    collapsedStrips = new Set();
  }
}

function stripName(title) {
  return String(title).split(" · ")[0].trim();
}

function setStripCollapsed(name, collapsed) {
  if (collapsed) collapsedStrips.add(name);
  else collapsedStrips.delete(name);
  storageSet(COLLAPSED_KEY, JSON.stringify([...collapsedStrips]));
  renderMarket();
}

function toggleAllStrips() {
  const names = [...el("market").querySelectorAll(".strip[data-strip]")].map(
    (box) => box.dataset.strip,
  );
  const anyOpen = names.some((name) => !collapsedStrips.has(name));
  collapsedStrips = new Set(anyOpen ? names : []);
  storageSet(COLLAPSED_KEY, JSON.stringify([...collapsedStrips]));
  renderMarket();
}

/* One shared-card column, with a heading that folds it away. Collapsed, the
   heading keeps its count so the column still says what is in it. */
function stripBox(title, count, className) {
  const box = document.createElement("div");
  box.className = "strip" + (className ? ` ${className}` : "");
  const name = stripName(title);
  box.dataset.strip = name;
  const collapsed = collapsedStrips.has(name);
  if (collapsed) box.classList.add("collapsed");
  const heading = document.createElement("h3");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "strip-toggle";
  button.setAttribute("aria-expanded", collapsed ? "false" : "true");
  button.title = collapsed ? t("common.expand") : t("common.collapse");
  button.append(collapsed ? "▸" : "▾", " ", title);
  if (collapsed && count !== undefined && count !== null) button.append(` (${count})`);
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    setStripCollapsed(name, !collapsed);
  });
  heading.appendChild(button);
  box.appendChild(heading);
  return box;
}

function cardStrip(parent, title, ids, emptyText, options = {}) {
  const box = stripBox(title, ids.length);
  const row = document.createElement("div");
  row.className = "strip-cards";
  if (!ids.length && emptyText) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = emptyText;
    row.appendChild(empty);
  }
  for (const id of ids) {
    row.appendChild(visualCard(id, typeof options === "function" ? options(id) : options));
  }
  box.appendChild(row);
  parent.appendChild(box);
  return row;
}

function renderMarket() {
  const market = el("market");
  market.textContent = "";
  const view = state.view;
  if (!view) return;

  /* The draft pool stays in the view after every seat has picked; the
     chosen Leaders then live on the seat cards, so the strip goes away. */
  const drafting = view.players.some((p) => !p.leader_id);
  if (view.leader_draft_pool.length && drafting) {
    const picked = new Set(view.players.map((p) => p.leader_id).filter(Boolean));
    cardStrip(market, "Leader draft", view.leader_draft_pool, "", (id) => ({
      className: "leader" + (picked.has(id) ? " taken" : ""),
      badge: picked.has(id) ? t("board.leader_taken") : null,
    }));
  }

  /* With the board scan the Conflict card and the face-up contracts sit
     in their printed slots on the board (renderSlotCards); the strips
     below only cover the text-board fallback. */
  const onBoard = Boolean(state.catalog.board_image);
  if (!onBoard) {
    cardStrip(market, "Conflict", view.current_conflict_ids, t("board.conflict_not_revealed"), {
      className: "conflict",
    });
  }
  cardStrip(market, "Imperium Row", view.imperium_row, t("common.empty"));
  cardStrip(market, "Reserve", view.reserve_stacks.map(([cardId]) => cardId), "", (id) => {
    const stack = view.reserve_stacks.find(([cardId]) => cardId === id);
    return { badge: `×${stack ? stack[1] : 0}` };
  });

  if (state.summary.bloodlines) {
    /* Sardaukar Commanders still waiting on their setup spaces, the bank
       Commander (Sardaukar Standard) and the four face-up Skills
       [Bloodlines pp. 3-4]. */
    const spaces = view.sardaukar_commander_space_ids || [];
    const box = stripBox(
      t("board.sardaukar_commander_summary", {
        count: spaces.length,
        bank: view.sardaukar_commanders_bank || 0,
      }),
      spaces.length,
    );
    const row = document.createElement("div");
    row.className = "strip-cards wrap";
    if (!spaces.length) {
      const empty = document.createElement("span");
      empty.className = "muted";
      empty.textContent = t("board.no_commanders_on_board");
      row.appendChild(empty);
    }
    for (const spaceId of spaces) row.appendChild(chip(spaceId));
    box.appendChild(row);
    market.appendChild(box);
    cardStrip(
      market,
      `Skill (face-up) · stack ${view.skill_stack_size || 0}`,
      (view.skill_face_up || []).map(skillIdOf),
      t("common.none"),
      { className: "skill" }
    );
  }
  if (state.summary.tech_module) {
    /* The Ixian Embassy's three stacks: the face-up top of each with the
       stack size; an emptied stack simply offers nothing [Bloodlines p. 7]. */
    const box = stripBox(
      "Ixian Embassy · Tech tiles",
      (view.tech_face_up || []).filter(Boolean).length,
    );
    const row = document.createElement("div");
    row.className = "strip-cards";
    (view.tech_face_up || []).forEach((tileId, index) => {
      const size = (view.tech_stack_sizes || [])[index] || 0;
      if (!tileId) {
        const empty = document.createElement("span");
        empty.className = "stack-empty";
        empty.textContent = t("board.stack_empty", { index: index + 1 });
        row.appendChild(empty);
        return;
      }
      row.appendChild(visualCard(tileId, { className: "tile", badge: `×${size}` }));
    });
    box.appendChild(row);
    market.appendChild(box);
    if ((view.tech_trash || []).length) {
      cardStrip(market, "Tech trash", view.tech_trash, "", { className: "tile taken" });
    }
  }
  if (state.summary.immortality) renderBeneTleilax(market, view);
  if (state.summary.choam_module && !onBoard) {
    cardStrip(
      market,
      `Contracts · bank ${view.contract_bank_size}`,
      view.face_up_contract_ids,
      t("common.empty"),
      { className: "contract" }
    );
  }
  if (view.sardaukar_contract_ids.length) {
    cardStrip(market, t("board.sardaukar_contract_title"), view.sardaukar_contract_ids, "", {
      className: "contract",
      badge: "set-aside",
    });
  }
  renderIntriguePiles(market, view);
  /* Folding is only worth anything if the column then gives its width back,
     and #market has a min-width that would otherwise hold it open. */
  const boxes = [...market.querySelectorAll(".strip[data-strip]")];
  market.classList.toggle(
    "all-folded",
    boxes.length > 0 && boxes.every((box) => box.classList.contains("collapsed")),
  );
}

/* The public Intrigue piles as one line: the cards themselves only matter
   when somebody wants to look back, so a click lists them (newest first) —
   the face-up discard pile beside the deck [Main p. 7] and the Intrigue
   cards trashed out of the game [Main p. 20]. */
function renderIntriguePiles(market, view) {
  const discard = view.intrigue_discard || [];
  const trash = view.intrigue_trash || [];
  if (!discard.length && !trash.length) return;
  const box = document.createElement("div");
  box.className = "strip";
  const pile = document.createElement("button");
  pile.type = "button";
  pile.className = "pile-button";
  pile.dataset.pile = "intrigue";
  pile.appendChild(tNode("board.intrigue_discard_count", { count: discard.length }));
  if (trash.length) pile.append(t("board.intrigue_trash_count", { count: trash.length }));
  pile.title = t("board.intrigue_pile_title");
  pile.addEventListener("click", (event) => {
    event.stopPropagation();
    openPileList(
      [
        ["Intrigue discard", [...discard].reverse()],
        ["Intrigue trash", [...trash].reverse()],
      ],
      null,
      pile
    );
  });
  box.appendChild(pile);
  market.appendChild(box);
}

/* ---------- Immortality: the Tleilaxu Row and the Bene Tleilax board ---------- */

/* The Bene Tleilax board at a readable size. renderBeneTleilaxScan places
   everything in percentages of its stage, so the same call fills a large
   container with no second layout to keep in step. */
let btZoomOpen = false;

function fillBeneTleilaxZoom(layout, view) {
  const body = el("bt-zoom-body");
  body.textContent = "";
  const heading = document.createElement("h2");
  heading.textContent = "Bene Tleilax board";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "bt-zoom-close";
  close.textContent = t("common.close");
  close.addEventListener("click", closeBeneTleilaxZoom);
  heading.appendChild(close);
  body.append(heading, renderBeneTleilaxScan(layout, view));
  el("bt-zoom").hidden = false;
  close.focus();
}

function openBeneTleilaxZoom() {
  const layout = state.catalog && state.catalog.bene_tleilax;
  if (!layout || !state.view) return;
  btZoomOpen = true;
  fillBeneTleilaxZoom(layout, state.view);
}

function closeBeneTleilaxZoom() {
  btZoomOpen = false;
  el("bt-zoom").hidden = true;
  el("bt-zoom-body").textContent = "";
}

function renderBeneTleilax(market, view) {
  /* The Tleilaxu Row: two deck cards bought with specimens plus the fixed
     Reclaimed Forces card [Immortality pp. 6, 9]. */
  const rowIds = [...(view.tleilaxu_row || []), "reclaimed_forces"];
  cardStrip(
    market,
    `Tleilaxu Row · deck ${view.tleilaxu_deck_size || 0}`,
    rowIds,
    "",
    (id) => {
      const entry = lookup(baseId(id));
      const specimens = entry && entry.specimens !== undefined ? entry.specimens : null;
      return {
        className: id === "reclaimed_forces" ? "reclaimed" : "",
        badge: specimens === null ? null : `specimen ×${specimens}`,
      };
    }
  );

  const layout = state.catalog && state.catalog.bene_tleilax;
  if (!layout) return;
  const box = stripBox("Bene Tleilax board", null, "bene-tleilax");

  if (layout.image) {
    /* The owner's scan with the live tokens drawn over it
       (catalog.bene_tleilax.layout, percent of the image). */
    box.appendChild(renderBeneTleilaxScan(layout, view));
    /* In the shared-card column this board is about 167px wide — its scan is
       5551px, so a 33x reduction, against 10x for the main board. Its research
       spaces come out around 19x21px and the seat tokens under 10px, which is
       a picture of a board rather than a board. The column keeps the small one
       as an at-a-glance marker; this opens it at a size you can read. */
    const open = document.createElement("button");
    open.type = "button";
    open.className = "bt-open";
    open.textContent = t("board.view_full_size");
    open.addEventListener("click", (event) => {
      event.stopPropagation();
      openBeneTleilaxZoom();
    });
    box.appendChild(open);
    market.appendChild(box);
    if (btZoomOpen) fillBeneTleilaxZoom(layout, view);
    return;
  }

  /* Without a scan: the 22 hexes as a column/row grid; each seat's
     research token sits on its space, the genetic-marker columns are
     tinted. */
  const grid = document.createElement("div");
  grid.className = "research-grid";
  const columns = Math.max(...layout.research_spaces.map((s) => s.column)) + 1;
  const rows = Math.max(...layout.research_spaces.map((s) => s.row)) + 1;
  grid.style.gridTemplateColumns = `repeat(${columns}, minmax(3.6rem, 1fr))`;
  grid.style.gridTemplateRows = `repeat(${rows}, auto)`;
  const tokensBySpace = {};
  for (const player of view.players) {
    if (!player.research_space) continue;
    (tokensBySpace[player.research_space] ||= []).push(player.player);
  }
  for (const space of layout.research_spaces) {
    const cell = document.createElement("div");
    cell.className = "hex";
    if (layout.genetic_marker_columns.includes(space.column)) cell.classList.add("marker");
    if (space.id === layout.research_start) cell.classList.add("start");
    cell.style.gridColumn = String(space.column + 1);
    cell.style.gridRow = String(space.row + 1);
    const label = document.createElement("span");
    label.className = "hex-label";
    label.textContent =
      space.id === layout.research_start
        ? t("board.research_start_short")
        : phraseText(RESEARCH_BONUS_LABELS[space.bonus] || space.bonus);
    cell.appendChild(label);
    const tokens = document.createElement("span");
    tokens.className = "hex-tokens";
    for (const seat of tokensBySpace[space.id] || []) tokens.appendChild(seatDisc(seat, "rtoken"));
    cell.appendChild(tokens);
    cell.title = `${space.id} · ${phraseText(RESEARCH_BONUS_LABELS[space.bonus] || t("board.no_bonus"))}`;
    grid.appendChild(cell);
  }
  box.appendChild(grid);

  /* Tleilaxu track: eight spaces, the bank's spice on the fourth until a
     token first arrives [Immortality p. 4]. */
  const track = document.createElement("div");
  track.className = "tleilaxu-track";
  layout.tleilaxu_track.forEach((bonus, index) => {
    const cell = document.createElement("div");
    cell.className = "track-cell";
    const label = document.createElement("span");
    label.className = "hex-label";
    label.textContent =
      `${index}${TLEILAXU_TRACK_LABELS[bonus] ? " · " + phraseText(TLEILAXU_TRACK_LABELS[bonus]) : ""}`;
    cell.appendChild(label);
    if (index === layout.tleilaxu_spice_space && view.tleilaxu_track_spice) {
      const spice = document.createElement("span");
      spice.className = "stat";
      spice.append(icon("spice", "spice"), String(view.tleilaxu_track_spice));
      cell.appendChild(spice);
    }
    const tokens = document.createElement("span");
    tokens.className = "hex-tokens";
    for (const player of view.players) {
      if ((player.tleilaxu_space || 0) === index) tokens.appendChild(seatDisc(player.player, "rtoken"));
    }
    cell.appendChild(tokens);
    track.appendChild(cell);
  });
  const trackHead = document.createElement("div");
  trackHead.className = "muted";
  trackHead.textContent = "Tleilaxu track";
  box.appendChild(trackHead);
  box.appendChild(track);
  market.appendChild(box);
}

function renderBeneTleilaxScan(layout, view) {
  const stage = document.createElement("div");
  stage.className = "bt-stage";
  const map = document.createElement("img");
  map.className = "bt-map";
  map.src = layout.image;
  map.alt = "Bene Tleilax board";
  map.draggable = false;
  stage.appendChild(map);
  const overlay = layout.layout;
  const [hexWidth, hexHeight] = overlay.hex_size;
  /* The common player disc at the size of this board's printed spots; y
     values are percents of the height, hence the taller figure. */
  const discWidth = overlay.disc_size;
  const discHeight = overlay.disc_size * overlay.aspect;

  /* Research hexes: a titled hotspot per space and the seats' tokens in
     its dark upper half, above the printed bonus. */
  const tokensBySpace = {};
  for (const player of view.players) {
    if (!player.research_space) continue;
    (tokensBySpace[player.research_space] ||= []).push(player.player);
  }
  const bonusOf = {};
  for (const space of layout.research_spaces) bonusOf[space.id] = space.bonus;
  for (const [spaceId, [x, y]] of Object.entries(overlay.research_points)) {
    const hex = document.createElement("div");
    hex.className = "bt-hex";
    hex.style.left = `${x - hexWidth / 2}%`;
    hex.style.top = `${y - hexHeight / 2}%`;
    hex.style.width = `${hexWidth}%`;
    hex.style.height = `${hexHeight}%`;
    hex.title =
      spaceId === layout.research_start
        ? t("board.research_start_title")
        : `${spaceId} · ${phraseText(RESEARCH_BONUS_LABELS[bonusOf[spaceId]] || t("board.no_bonus"))}`;
    stage.appendChild(hex);
    /* The start piece prints a spot per disc (the fourth seat continues
       the column); elsewhere the discs lie in the hex's dark upper half
       and a second row, if three or more meet, goes over the bonus. */
    const seats = tokensBySpace[spaceId] || [];
    const places = discCluster(
      seats.length,
      discHalfGap(discWidth, hexWidth - 1),
      (discHeight + 0.1) / 2,
      { fromTop: true },
    );
    seats.forEach((seat, index) => {
      const token = seatDisc(seat, "bt-token", discWidth);
      if (spaceId === layout.research_start) {
        const [sx, sy] = overlay.research_start_discs[seat % overlay.research_start_discs.length];
        placeAt(token, sx, sy);
      } else {
        placeAt(token, x + places[index][0], y - hexHeight / 4 + places[index][1]);
      }
      stage.appendChild(token);
    });
  }

  /* Tleilaxu track: tokens along the top band, the bank's spice on the
     fourth space until a token first arrives [Immortality p. 4]. */
  const [bandTop, bandHeight] = overlay.track_band;
  overlay.track_cells.forEach(([left, width], index) => {
    const cell = document.createElement("div");
    cell.className = "bt-track-cell";
    cell.style.left = `${left}%`;
    cell.style.top = `${bandTop}%`;
    cell.style.width = `${width}%`;
    cell.style.height = `${bandHeight}%`;
    const bonus = layout.tleilaxu_track[index];
    cell.title =
      `Tleilaxu track ${index}${TLEILAXU_TRACK_LABELS[bonus] ? " · " + phraseText(TLEILAXU_TRACK_LABELS[bonus]) : ""}`;
    stage.appendChild(cell);
    /* The first space prints a spot per disc. The other spaces take the
       same two rows: the upper one first, which leaves the printed bonus
       in sight, and a pair stands upright where a space is too narrow. */
    const seats = view.players.filter((p) => (p.tleilaxu_space || 0) === index);
    const [rowTop, rowBottom] = [overlay.track_start_discs[0][1], overlay.track_start_discs[2][1]];
    const halfX = discHalfGap(discWidth, width - 0.4);
    const places = discCluster(seats.length, halfX, (rowBottom - rowTop) / 2, {
      fromTop: true,
      upright: halfX < discWidth * 0.3,
    });
    seats.forEach((player, slot) => {
      const token = seatDisc(player.player, "bt-token", discWidth);
      if (index === 0) {
        const [sx, sy] = overlay.track_start_discs[player.player % overlay.track_start_discs.length];
        placeAt(token, sx, sy);
      } else {
        placeAt(token, left + width / 2 + places[slot][0], rowTop + places[slot][1]);
      }
      stage.appendChild(token);
    });
  });
  if (view.tleilaxu_track_spice) {
    const spice = document.createElement("span");
    spice.className = "bt-spice";
    spice.append(icon("spice", "spice"), String(view.tleilaxu_track_spice));
    spice.title = t("board.spice_first_reacher");
    placeAt(spice, overlay.spice_point[0], overlay.spice_point[1]);
    stage.appendChild(spice);
  }
  return stage;
}
