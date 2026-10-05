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

/* When each Spy on the board arrived: the log's spy_placed events, in
   order, a later placement of the same seat on the same post replacing an
   earlier one (a Spy recalled and placed again). The engine keeps each
   seat's posts, not who came first. Taken-back steps do not count, and a
   review reads only up to its cursor, as the log panel does. */
function spyArrivals() {
  const log = state.review ? reviewLog(state.review) : state.log;
  const arrivals = new Map();
  let order = 0;
  for (const entry of (log && log.entries) || []) {
    if (entry.undone) continue;
    for (const event of entry.events || []) {
      if (event.kind !== "spy_placed") continue;
      arrivals.set(`${event.payload.post_id}|${event.payload.player}`, order++);
    }
  }
  return arrivals;
}

/* A post's Spies from the bottom up: first come first, then any the log
   does not place (a log that starts later), by seat, beneath them. */
function stackOrder(postId, seats, arrivals) {
  const when = (seat) => {
    const order = arrivals.get(`${postId}|${seat}`);
    return order === undefined ? -1 : order;
  };
  return [...seats].sort((a, b) => when(a) - when(b) || a - b);
}

function seatToken(seat, className) {
  const token = document.createElement("span");
  token.className = className;
  token.style.background = SEAT_COLORS[seat];
  token.textContent = String(seatNumber(seat));
  token.title = t("common.seat", { seat });
  token.setAttribute("role", "img");
  token.setAttribute("aria-label", t("common.seat", { seat }));
  token.dataset.seat = String(seat);
  return token;
}

/* One hidden sprite holds every piece's outline and its clip, so each
   piece on the board reuses them: made on first use and kept outside the
   board, which every render rebuilds. Not display:none, which would drop
   the clips in some browsers. */
function pieceSprite() {
  if (document.getElementById("agent-outline")) return;
  const svgNs = "http://www.w3.org/2000/svg";
  const sprite = document.createElementNS(svgNs, "svg");
  sprite.setAttribute("aria-hidden", "true");
  sprite.setAttribute("width", "0");
  sprite.setAttribute("height", "0");
  sprite.style.position = "absolute";
  const defs = document.createElementNS(svgNs, "defs");
  for (const [kind, shape] of Object.entries(PIECE_SHAPES)) {
    const outline = document.createElementNS(svgNs, "path");
    outline.id = `${kind}-outline`;
    outline.setAttribute("d", shape.outline);
    const clip = document.createElementNS(svgNs, "clipPath");
    clip.id = `${kind}-clip`;
    const clipShape = document.createElementNS(svgNs, "use");
    clipShape.setAttribute("href", `#${kind}-outline`);
    clip.appendChild(clipShape);
    defs.append(outline, clip);
  }
  sprite.appendChild(defs);
  document.body.appendChild(sprite);
}

/* A seat's Agent on a space or Spy on a post: the rulebook icon's shape,
   flat in the seat's colour like every other player piece and without a
   seat number, with the icon's light rim inside a dark edge (and a Spy's
   lighter top face). */
function seatPiece(kind, seat) {
  pieceSprite();
  const svgNs = "http://www.w3.org/2000/svg";
  const shape = PIECE_SHAPES[kind];
  const label = t("common.seat", { seat });
  const piece = document.createElementNS(svgNs, "svg");
  piece.setAttribute("class", `${kind}-token`);
  piece.setAttribute("viewBox", shape.viewBox);
  piece.setAttribute("role", "img");
  piece.setAttribute("aria-label", label);
  piece.dataset.seat = String(seat);
  const title = document.createElementNS(svgNs, "title");
  title.textContent = label;
  const layer = (className) => {
    const use = document.createElementNS(svgNs, "use");
    use.setAttribute("href", `#${kind}-outline`);
    use.setAttribute("class", className);
    return use;
  };
  const body = layer("piece-body");
  body.setAttribute("fill", SEAT_COLORS[seat]);
  piece.append(title, body);
  if (shape.top) {
    const top = document.createElementNS(svgNs, "ellipse");
    top.setAttribute("class", "piece-top");
    for (const [name, value] of Object.entries(shape.top)) {
      top.setAttribute(name, String(value));
    }
    piece.appendChild(top);
  }
  const rim = layer("piece-rim");
  rim.setAttribute("clip-path", `url(#${kind}-clip)`);
  piece.append(rim, layer("piece-edge"));
  return piece;
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
  title.textContent = t("board.control_seat_space", { seat, name: spaceName(spaceId) });
  const pennant = document.createElementNS(svgNs, "polygon");
  pennant.setAttribute("points", `0,0 100,0 100,100 50,${dip} 0,100`);
  pennant.setAttribute("fill", SEAT_COLORS[seat]);
  marker.append(title, pennant);
  return marker;
}

/* The white frame a space prints around its picture, which its hotspot's
   box follows (catalog.space_frame): square top-left and bottom-right
   corners, the other two cut. The highlight is drawn on this outline so
   every space lights up the same shape, without the icons beside it. */
function spaceFrame() {
  const svgNs = "http://www.w3.org/2000/svg";
  const [cutX, cutY] = state.catalog.space_frame.cut;
  const frame = document.createElementNS(svgNs, "svg");
  frame.setAttribute("class", "space-frame");
  frame.setAttribute("viewBox", "0 0 100 100");
  frame.setAttribute("preserveAspectRatio", "none");
  frame.setAttribute("aria-hidden", "true");
  const outline = document.createElementNS(svgNs, "polygon");
  outline.setAttribute(
    "points",
    `0,0 ${100 - cutX},0 100,${cutY} 100,100 ${cutX},100 0,${100 - cutY}`,
  );
  frame.appendChild(outline);
  return frame;
}

/* The centre of the hexagon a Maker space prints for its bonus spice
   (catalog.tracks.maker_spice), if the layout has one for the space. */
function makerSpicePoint(spaceId) {
  const spots = state.catalog.tracks && state.catalog.tracks.maker_spice;
  return (spots && spots.points[spaceId]) || null;
}

/* A Sardaukar Commander still on its setup space, standing on the top-right
   corner of the printed frame so the frame stays free for Agents, about as
   tall as the frame [Bloodlines p. 3] (catalog.commander_spot). It is the
   rulebook's figure (catalog.commander_token), or a drawn mark in its place;
   it is the same neutral piece for everyone until acquired, and it never
   takes the click meant for the space. */
function commanderPiece(spaceId, box) {
  const [left, top, width, height] = box;
  const spot = state.catalog.commander_spot;
  const picture = state.catalog.commander_token;
  const piece = document.createElement(picture ? "img" : "span");
  piece.className = picture ? "commander-piece" : "commander-piece drawn";
  piece.dataset.space = spaceId;
  piece.setAttribute("aria-hidden", "true");
  if (picture) {
    piece.src = picture;
    piece.alt = "";
    piece.draggable = false;
  } else {
    piece.textContent = "C";
  }
  piece.style.left = `${left + width * spot.anchor[0]}%`;
  piece.style.top = `${top + height * spot.anchor[1]}%`;
  piece.style.height = `${height * spot.height}%`;
  /* The anchor takes the base's centre, not the picture's corner. */
  piece.style.transform =
    `translate(${-100 * spot.base[0]}%, ${-100 * spot.base[1]}%)`;
  return piece;
}

/* Spice waiting on a printed hexagon: a spice hexagon exactly over the
   printed one (`size` is its white outline, percent of the stage), with the
   amount in it like the board's own spice numbers. */
function spiceHex(count, point, [width, height], title) {
  const token = document.createElement("span");
  token.className = "bonus-spice";
  token.title = title;
  token.style.width = `${width}%`;
  token.style.height = `${height}%`;
  const amountText = document.createElement("span");
  amountText.className = "bonus-spice-count" + (count > 9 ? " wide" : "");
  amountText.textContent = String(count);
  token.appendChild(amountText);
  return placeAt(token, point[0], point[1]);
}

/* The bonus spice waiting on a Maker space, "in the spot designated for
   bonus spice" [Main p. 15]. */
function bonusSpiceToken(spaceId, count, point) {
  const token = spiceHex(
    count,
    point,
    state.catalog.tracks.maker_spice.size,
    `${spaceName(spaceId)} · ${t("board.bonus_spice", { count })}`,
  );
  token.dataset.space = spaceId;
  return token;
}

/* The scanned board with the live state on top: a hotspot per space
   (catalog.spaces[id].box, percent of the image: the frame the space
   prints around its picture), Agent tokens, Control
   flags, Maker bonus spice, and Spies on the observation posts. */
function renderBoardStage(board, view) {
  const stage = document.createElement("div");
  stage.className = "board-stage";
  const map = document.createElement("img");
  map.className = "board-map";
  map.src = state.catalog.board_image;
  map.alt = t("board.map_alt");
  map.draggable = false;
  stage.appendChild(map);

  const { occupants, controllers, spies } = boardOccupancy(view);
  const arrivals = spyArrivals();
  const makerSpice = new Map(view.maker_bonus_spice);
  const commanders = new Set(view.sardaukar_commander_space_ids || []);

  /* Pieces that lie on the board, under the hotspots and the tokens. The
     Shield Wall token stays on its marked position until a player removes
     it [Main pp. 4, 10]; a Leader's tile in play and Immortality's overlay
     tile are pictures the scan does not have. */
  const wall = state.catalog.shield_wall;
  if (view.shield_wall_present && wall && wall.image) {
    const token = boardPiece(wall.image, wall.box, "shield-wall-token");
    token.alt = phraseText("{shield_wall}");
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
    /* The Commander standing on the space is drawn outside the hotspot and
       takes no pointer, so the space says it has one. */
    const label = commanders.has(spaceId)
      ? t("board.space_with_commander", { space: entry.name })
      : entry.name;
    hotspot.title = label;
    hotspot.dataset.space = spaceId;
    hotspot.setAttribute("aria-label", label);
    hotspot.appendChild(spaceFrame());
    const legal = legalActionsFor(spaceId);
    if (legal.length) hotspot.classList.add("legal");
    if (state.pick && state.pick.spaceId === spaceId) hotspot.classList.add("picked");
    else if (pickAlternative(spaceId, "spaceId")) hotspot.classList.add("alternative");
    if (!spaceImplementedFor(entry)) hotspot.classList.add("unimplemented");
    const seats = occupants.get(spaceId) || [];
    if (seats.length) {
      const tokens = document.createElement("span");
      tokens.className = "agent-tokens";
      tokens.dataset.count = String(Math.min(seats.length, 4));
      for (const seat of seats) tokens.appendChild(seatPiece("agent", seat));
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
      const bonus = amount("spice", t("board.bonus_spice_label"), makerSpice.get(spaceId));
      bonus.classList.add("maker-bonus");
      hotspot.appendChild(bonus);
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
  for (const spaceId of commanders) {
    const entry = state.catalog.spaces[spaceId];
    if (entry && spaceInPlay(entry, view)) stage.appendChild(commanderPiece(spaceId, entry.box));
  }

  /* Arrakeen Scouts: what missions left on the spaces and posts. */
  renderScoutsBoardPieces(stage, view, spies);

  for (const [postId, [x, y]] of Object.entries(state.catalog.posts)) {
    const legal = legalSpyPostActions(postId);
    if (legal.length) {
      const target = document.createElement("button");
      target.type = "button";
      target.className = "spy-post-hotspot legal";
      target.dataset.post = postId;
      target.style.width = `${state.catalog.post_size * 1.8}%`;
      placeAt(target, x, y);
      const name = postName(postId);
      target.title = name;
      target.setAttribute("aria-label", name);
      target.addEventListener("click", (event) => {
        event.stopPropagation();
        tableClick(postId, { name }, target, legalSpyPostActions(postId));
      });
      stage.appendChild(target);
    }
    const seats = stackOrder(postId, spies.get(postId) || [], arrivals);
    if (!seats.length) continue;
    const post = document.createElement("span");
    post.className = "spy-post" + (legal.length ? " selectable" : "");
    post.style.left = `${x}%`;
    post.style.top = `${y}%`;
    /* A Spy is as wide as the printed post disc (catalog.post_size, a
       percent of the width; the scan is square within 0.12 %), so the row
       is that tall at the icon's proportions. */
    post.style.height = `${(state.catalog.post_size * 80) / 56}%`;
    post.dataset.count = String(Math.min(seats.length, 4));
    post.title = t("board.post_seats", {
      post: postName(postId),
      seats: seats.map(seatNumber).join(", "),
    });
    /* A Spy sharing a post stands on the one that was there first. */
    seats.forEach((seat, level) => {
      const piece = seatPiece("spy", seat);
      piece.style.setProperty("--level", String(level));
      post.appendChild(piece);
    });
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
   the units stay on top. The Conflict card fills its portrait frame;
   the landscape contracts are drawn a little larger than their slot
   because the dark band around it is empty. Shaddam's set-aside Sardaukar
   contracts have no printed home on the board either; they are drawn on
   his own leader popover instead (core.js leaderSardaukarRow), not here. */
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
    deck.append(icon("sword", phraseText("{conflict}")), count);
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
  bank.title = t("board.contract_bank_title");
  bank.append(
    icon("contract", phraseText("{contract}")),
    ` ${t("board.contract_bank_count", { count: view.contract_bank_size })}`,
  );
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
   owner's token pictures. The size is a percentage of the board stage. */
function allianceToken(key, size) {
  const token = document.createElement("span");
  token.className = "alliance-token";
  token.dataset.faction = key;
  token.title = phraseText(`${FACTION_LABELS[key]} {alliance}`);
  token.style.width = `${size}%`;
  const url = (state.catalog.alliance_tokens || {})[key];
  if (url) {
    const face = document.createElement("img");
    face.src = url;
    face.alt = "";
    face.draggable = false;
    token.appendChild(face);
  } else {
    token.classList.add("drawn");
    token.appendChild(icon(`influence_${key}`, token.title));
  }
  return token;
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
    token.alt = phraseText("{maker_hooks}");
    token.draggable = false;
    token.style.width = `${height}%`;
    token.style.transform =
      `translate(-50%, -50%) rotate(${turn.rotation}deg)` + (turn.mirrored ? " scaleX(-1)" : "");
  } else {
    token = document.createElement("span");
    token.className = "maker-hooks-token drawn";
    token.style.width = `${width}%`;
    token.style.height = `${height}%`;
    token.appendChild(icon("maker_hooks", phraseText("{maker_hooks}")));
  }
  token.dataset.seat = String(seat);
  token.title = t("board.seat_maker_hooks", { seat });
  return placeAt(token, x, y);
}

/* The kinds of unit a seat can have in the Conflict, in the order they are
   laid out: troops, then the figures (Bloodlines' Sardaukar Commanders,
   Duncan Idaho's Into the Fray Agent, sandworms). */
const CONFLICT_UNIT_KINDS = ["troop", "commander", "agent", "sandworm"];

/* Where each of a seat's units stands in its quadrant of the Conflict, one
   piece per unit as on the table ("keep your deployed units in the quadrant
   nearest to your garrison" [Main p. 10]). `counts` is {kind: n}, `box` the
   quadrant (stage percent) and `layout` catalog.tracks.conflict_units.
   Troops fill rows from the quadrant's outer edge (`fromBottom` for the
   lower seats), each row from the garrison side (`fromRight` for the right
   seats), so a partial row is the innermost; the figures follow in rows
   toward the printed cross, Commanders first, then Agents, then sandworms,
   every piece standing on its row's floor. Rows that do not fit shrink
   every piece in steps of 0.05 down to layout.min_scale; past that the rows
   close up (and may overlap) so that everything stays inside the box.
   Pure: returns {scale, pieces: [{kind, x, y, w, h}]}, the top-left corner
   and size of each piece in stage percent. */
function conflictUnitLayout(counts, box, layout, { fromRight = false, fromBottom = false } = {}) {
  const [left, top, width, height] = box;
  const { gap, padding, sizes } = layout;
  const innerWidth = width - 2 * padding;
  const innerHeight = height - 2 * padding;
  const rowsAt = (scale) => {
    const rows = [];
    let row = null;
    for (const kind of CONFLICT_UNIT_KINDS) {
      const [w, h] = sizes[kind].map((value) => value * scale);
      const figure = kind !== "troop";
      for (let index = 0; index < (counts[kind] || 0); index += 1) {
        const wider = row ? row.width + gap + w : w;
        if (!row || row.figure !== figure || wider > innerWidth + 1e-9) {
          row = { figure, items: [], width: 0, height: 0 };
          rows.push(row);
        }
        row.width = row.items.length ? row.width + gap + w : w;
        row.height = Math.max(row.height, h);
        row.items.push({ kind, w, h });
      }
    }
    return rows;
  };
  const depth = (rows) =>
    rows.reduce((sum, row) => sum + row.height, 0) + gap * Math.max(0, rows.length - 1);
  let scale = 1;
  let rows = rowsAt(scale);
  while (depth(rows) > innerHeight + 1e-9 && scale > layout.min_scale + 1e-9) {
    scale = Math.max(layout.min_scale, Math.round((scale - 0.05) * 100) / 100);
    rows = rowsAt(scale);
  }
  /* Rows start `offset` in from the outer edge; closing up scales every
     offset by one factor, the largest that keeps each row inside. */
  const offsets = [];
  let running = 0;
  for (const row of rows) {
    offsets.push(running);
    running += row.height + gap;
  }
  let squeeze = 1;
  rows.forEach((row, index) => {
    if (offsets[index] > 0 && offsets[index] + row.height > innerHeight) {
      squeeze = Math.min(squeeze, Math.max(0, innerHeight - row.height) / offsets[index]);
    }
  });
  const pieces = [];
  rows.forEach((row, index) => {
    const start = offsets[index] * squeeze;
    const rowTop = fromBottom
      ? top + height - padding - start - row.height
      : top + padding + start;
    let along = 0;
    for (const item of row.items) {
      pieces.push({
        kind: item.kind,
        x: fromRight ? left + width - padding - along - item.w : left + padding + along,
        y: rowTop + row.height - item.h,
        w: item.w,
        h: item.h,
      });
      along += item.w + gap;
    }
  });
  return { scale, pieces };
}

/* The kinds of unit a garrison holds, in the order they are laid out:
   troops, then Bloodlines' Sardaukar Commanders (nothing else is ever
   garrisoned; a sandworm goes straight to the Conflict). */
const GARRISON_UNIT_KINDS = ["troop", "commander"];

/* Every way to share `total` rows among `parts` kinds, at least one row
   each, the first kind's fewest first. */
function rowSplits(total, parts) {
  if (parts === 1) return [[total]];
  const splits = [];
  for (let first = 1; first <= total - parts + 1; first += 1) {
    for (const rest of rowSplits(total - first, parts - 1)) splits.push([first, ...rest]);
  }
  return splits;
}

/* Where each unit of a seat's garrison stands in its printed ring, one
   piece per unit as on the table. `counts` is {kind: n}, `ring` the ring's
   outer box (stage percent), `layout` catalog.tracks.garrison_units, and
   `avoid` boxes (stage percent) lying over the ring that the pieces keep
   clear of: a Maker Hooks token in the slot printed over the ring's outer
   corner. The pieces stand in rows inside the ring's inner circle (the
   outer edge less layout.line and layout.padding; an ellipse in stage
   percent, as the scan is a hair wider than tall): troops first, then
   Commanders, in the fewest rows that hold them, a kind's units shared
   evenly among its rows (the upper rows take any extra). The block of rows
   is centred in the ring and every row on the ring's centre line; a row is
   only as long as the circle is wide at its edge farther from the centre.
   A box to avoid first moves the block just clear of the box's height;
   where the circle has no room for that, the rows it cuts keep a padding
   off it, in the part it leaves free. Rows that do not fit shrink every
   piece and the gaps in steps of 0.05 down to layout.min_scale; past that
   (no real garrison gets there) the rows close up inside the ring's box.
   Pure: returns {scale, pieces: [{kind, x, y, w, h}]}, the top-left corner
   and size of each piece in stage percent. */
function ringUnitLayout(counts, ring, layout, avoid = []) {
  const [left, top, width, height] = ring;
  const { gap, padding, sizes } = layout;
  const inset = layout.line + padding;
  const cx = left + width / 2;
  const cy = top + height / 2;
  const rx = width / 2 - inset;
  const ry = height / 2 - inset;
  const kinds = GARRISON_UNIT_KINDS.filter((kind) => counts[kind] > 0);
  if (!kinds.length) return { scale: 1, pieces: [] };
  const total = kinds.reduce((sum, kind) => sum + counts[kind], 0);
  const blocks = avoid.map(([bl, bt, bw, bh]) => [
    bl - padding, bt - padding, bl + bw + padding, bt + bh + padding,
  ]);
  /* The longest stretch of a row from `rowTop` to `rowBottom` inside the
     circle and clear of every box, and whether a box cut into it. */
  const freeSpan = (rowTop, rowBottom) => {
    const edge = Math.max(Math.abs(rowTop - cy), Math.abs(rowBottom - cy));
    if (edge >= ry) return { span: null, cut: false };
    const half = rx * Math.sqrt(1 - (edge / ry) ** 2);
    let spans = [[cx - half, cx + half]];
    let cut = false;
    for (const [bx0, by0, bx1, by1] of blocks) {
      if (by1 <= rowTop || by0 >= rowBottom) continue;
      const rest = [];
      for (const [a, b] of spans) {
        if (bx1 <= a || bx0 >= b) {
          rest.push([a, b]);
          continue;
        }
        cut = true;
        if (bx0 > a) rest.push([a, bx0]);
        if (bx1 < b) rest.push([bx1, b]);
      }
      spans = rest;
    }
    let span = null;
    for (const s of spans) if (!span || s[1] - s[0] > span[1] - span[0]) span = s;
    return { span, cut };
  };
  /* Share each kind's units among its rows, least-filled row first. */
  const fill = (rows) => {
    for (const kind of kinds) {
      const own = rows.filter((row) => row.kind === kind);
      const room = own.reduce((sum, row) => sum + row.capacity, 0);
      if (own.some((row) => row.capacity < 1) || room < counts[kind]) return false;
      for (let unit = 0; unit < counts[kind]; unit += 1) {
        let pick = null;
        for (const row of own) {
          if (row.count < row.capacity && (!pick || row.count < pick.count)) pick = row;
        }
        pick.count += 1;
      }
    }
    return true;
  };
  /* `split[k]` rows of kinds[k] at `scale`: centred, or moved just clear
     of a box above or below it; the first placement no box cuts, else the
     centred one with the cut rows narrowed, else null. */
  const arrange = (split, scale) => {
    const between = gap * scale;
    const rows = [];
    kinds.forEach((kind, index) => {
      const [w, h] = sizes[kind].map((value) => value * scale);
      for (let n = 0; n < split[index]; n += 1) rows.push({ kind, w, h });
    });
    const depth = rows.reduce((sum, row) => sum + row.h, 0) + between * (rows.length - 1);
    if (depth > 2 * ry + 1e-9) return null;
    const shifts = [0];
    for (const [, by0, , by1] of blocks) {
      for (const shift of [by0 - (cy + depth / 2), by1 - (cy - depth / 2)]) {
        if (Math.abs(shift) > 1e-9 && Math.abs(shift) + depth / 2 <= ry + 1e-9) shifts.push(shift);
      }
    }
    shifts.sort((a, b) => Math.abs(a) - Math.abs(b));
    let narrowed = null;
    for (const shift of shifts) {
      let rowTop = cy + shift - depth / 2;
      let cut = false;
      const placed = rows.map((row) => {
        const free = freeSpan(rowTop, rowTop + row.h);
        cut = cut || free.cut;
        const capacity = free.span
          ? Math.floor((free.span[1] - free.span[0] + between + 1e-9) / (row.w + between))
          : 0;
        const at = { ...row, top: rowTop, span: free.span, capacity, count: 0 };
        rowTop += row.h + between;
        return at;
      });
      if (!fill(placed)) continue;
      if (!cut) return { rows: placed, between };
      if (!narrowed) narrowed = { rows: placed, between };
    }
    return narrowed;
  };
  let scale = 1;
  let arranged = null;
  for (;;) {
    for (let count = kinds.length; count <= total && !arranged; count += 1) {
      for (const split of rowSplits(count, kinds.length)) {
        arranged = arrange(split, scale);
        if (arranged) break;
      }
    }
    if (arranged || scale <= layout.min_scale + 1e-9) break;
    scale = Math.max(layout.min_scale, Math.round((scale - 0.05) * 100) / 100);
  }
  if (!arranged && total) {
    /* Closed up: rows as wide as the circle, their pitch shrunk so the
       last one still ends inside the ring's box. */
    const between = gap * scale;
    const rows = [];
    for (const kind of kinds) {
      const [w, h] = sizes[kind].map((value) => value * scale);
      const perRow = Math.max(1, Math.floor((2 * rx + between + 1e-9) / (w + between)));
      for (let rest = counts[kind]; rest > 0; rest -= perRow) {
        rows.push({ kind, w, h, count: Math.min(perRow, rest), span: [cx - rx, cx + rx] });
      }
    }
    const offsets = [];
    let running = 0;
    for (const row of rows) {
      offsets.push(running);
      running += row.h + between;
    }
    const depth = running - between;
    let squeeze = 1;
    rows.forEach((row, index) => {
      if (offsets[index] > 0 && offsets[index] + row.h > 2 * ry) {
        squeeze = Math.min(squeeze, Math.max(0, 2 * ry - row.h) / offsets[index]);
      }
    });
    const start = depth <= 2 * ry ? cy - depth / 2 : cy - ry;
    rows.forEach((row, index) => {
      row.top = start + offsets[index] * squeeze;
    });
    arranged = { rows, between };
  }
  const pieces = [];
  for (const row of arranged ? arranged.rows : []) {
    const length = row.count * row.w + (row.count - 1) * arranged.between;
    const [spanLeft, spanRight] = row.span;
    const rowLeft = Math.max(spanLeft, Math.min(cx - length / 2, spanRight - length));
    for (let index = 0; index < row.count; index += 1) {
      pieces.push({
        kind: row.kind,
        x: rowLeft + index * (row.w + arranged.between),
        y: row.top,
        w: row.w,
        h: row.h,
      });
    }
  }
  return { scale, pieces };
}

/* One unit's piece: a troop is the seat's cube (the Influence cube's
   colour, size and edge), an Agent the seat's Agent figure; a Sardaukar
   Commander and a sandworm are the neutral pieces everyone shares, their
   own pictures (catalog.commander_token, the Icon Guide's worm) or a drawn
   shape without them. The quadrant or the garrison ring says whose they
   are, as on the table. `className` is the piece's class where it stands
   (conflict-unit, garrison-unit). */
function unitPiece(kind, seat, className) {
  let piece;
  if (kind === "agent") {
    piece = seatPiece("agent", seat);
    piece.removeAttribute("role");
    piece.removeAttribute("aria-label");
    piece.querySelector("title").remove();
    piece.setAttribute("class", className);
  } else if (kind === "troop") {
    piece = document.createElement("span");
    piece.className = className;
    piece.style.background = SEAT_COLORS[seat];
  } else {
    const picture = kind === "commander" ? state.catalog.commander_token : iconUrl("sandworm");
    if (picture) {
      piece = document.createElement("img");
      piece.src = picture;
      piece.alt = "";
      piece.draggable = false;
      piece.className = className;
    } else if (kind === "sandworm") {
      piece = drawnSandworm(className);
    } else {
      piece = document.createElement("span");
      piece.className = `${className} drawn`;
    }
  }
  piece.setAttribute("aria-hidden", "true");
  piece.dataset.seat = String(seat);
  piece.dataset.kind = kind;
  return piece;
}

/* A sandworm without the Icon Guide's picture: the worm's arch rising out
   of the sand, in the plastic's grey with the dark edge of every piece. */
function drawnSandworm(className) {
  const svgNs = "http://www.w3.org/2000/svg";
  const worm = document.createElementNS(svgNs, "svg");
  worm.setAttribute("class", `${className} drawn`);
  worm.setAttribute("viewBox", "0 0 62 57");
  worm.setAttribute("preserveAspectRatio", "none");
  const body = document.createElementNS(svgNs, "path");
  body.setAttribute(
    "d",
    "M3 55 C3 28 15 3 35 3 C52 3 60 16 60 31 L60 38 L47 38 L47 31" +
      " C47 22 43 16 35 16 C24 16 17 30 17 55 Z",
  );
  worm.appendChild(body);
  return worm;
}

/* "troop 3, Sardaukar Commander 1": the kinds a seat has, with their
   numbers, for the name of its pieces. */
function unitCountsText(kinds, counts) {
  return kinds
    .filter((kind) => counts[kind] > 0)
    .map((kind) => phraseText(`{${kind}:${counts[kind]}}`))
    .join(", ");
}

/* A seat's pieces in a printed box (a Conflict quadrant, a garrison ring):
   the box is the group, named with the exact numbers, and every piece is
   placed and sized in percent of it. `placed` is a layout's result. */
function unitGroup(seat, box, placed, { className, pieceClass, label }) {
  const [left, top, width, height] = box;
  const units = document.createElement("div");
  units.className = className;
  units.dataset.seat = String(seat);
  units.dataset.scale = String(placed.scale);
  units.setAttribute("role", "img");
  units.setAttribute("aria-label", label);
  units.title = label;
  units.style.left = `${left}%`;
  units.style.top = `${top}%`;
  units.style.width = `${width}%`;
  units.style.height = `${height}%`;
  for (const { kind, x, y, w, h } of placed.pieces) {
    const piece = unitPiece(kind, seat, pieceClass);
    piece.style.left = `${((x - left) / width) * 100}%`;
    piece.style.top = `${((y - top) / height) * 100}%`;
    piece.style.width = `${(w / width) * 100}%`;
    piece.style.height = `${(h / height) * 100}%`;
    units.appendChild(piece);
  }
  return units;
}

/* A seat's units in its quadrant of the Conflict: no count, no badge — one
   piece per unit (conflictUnitLayout), with the exact numbers in the
   quadrant's name. The seat's strength is on the combat track. */
function conflictUnits(seat, counts, layout) {
  const box = layout.boxes[seat] || layout.boxes[0];
  const [left, top, width, height] = box;
  const [crossX, crossY] = layout.cross;
  const placed = conflictUnitLayout(counts, box, layout, {
    fromRight: left + width / 2 > crossX,
    fromBottom: top + height / 2 > crossY,
  });
  return unitGroup(seat, box, placed, {
    className: "conflict-units",
    pieceClass: "conflict-unit",
    label: t("board.seat_conflict_units", {
      seat,
      units: unitCountsText(CONFLICT_UNIT_KINDS, counts),
    }),
  });
}

/* A seat's garrison in its printed ring: no count, no badge — one piece
   per unit (ringUnitLayout), clear of a Maker Hooks token in the ring's
   slot (`avoid`), with the exact numbers in the ring's name. */
function garrisonUnits(seat, counts, layout, avoid) {
  const ring = layout.rings[seat] || layout.rings[0];
  return unitGroup(seat, ring, ringUnitLayout(counts, ring, layout, avoid), {
    className: "garrison-units",
    pieceClass: "garrison-unit",
    label: t("board.seat_garrison_units", {
      seat,
      units: unitCountsText(GARRISON_UNIT_KINDS, counts),
    }),
  });
}

/* The box (stage percent) a seat's Maker Hooks token covers in its slot. */
function makerHooksBox(seat, layout) {
  const [x, y] = layout.points[seat] || layout.points[0];
  const [width, height] = layout.size;
  return [x - width / 2, y - height / 2, width, height];
}

/* The smallest text (px) the board's copy of the count rows is drawn at: a
   band too small for the rows at this size shows none, and the panel
   (#actions) keeps the same rows. */
const FORCE_STEPPER_MIN_FONT = 9;

/* The seat to move sends and takes back its units on the board as well:
   the same count rows as in the panel, in the plain desert just above the
   Conflict (catalog.tracks.force_stepper_band) where nothing is printed and
   no piece stands, on the band's bottom edge, the one nearest the
   Conflict. The rows shrink with the board (fitForceStepper). */
function forceStepper(seat, rows, band) {
  const [left, top, width, height] = band;
  const holder = document.createElement("div");
  holder.className = "force-stepper-band";
  holder.style.left = `${left}%`;
  holder.style.top = `${top}%`;
  holder.style.width = `${width}%`;
  holder.style.height = `${height}%`;
  const control = document.createElement("div");
  control.className = "force-stepper";
  control.style.borderColor = SEAT_COLORS[seat];
  for (const [id, family] of rows) control.appendChild(countRow(id, family, true));
  holder.appendChild(control);
  watchForceStepper(holder);
  return holder;
}

/* Fit the board's count rows into their band: the CSS size when they fit,
   smaller when not, and hidden below FORCE_STEPPER_MIN_FONT. The borders
   do not shrink with the text, so it steps until the rows fit. */
function fitForceStepper(holder) {
  const control = holder.querySelector(".force-stepper");
  if (!control || !holder.isConnected) return;
  const room = holder.getBoundingClientRect();
  control.hidden = false;
  control.style.fontSize = "";
  let size = parseFloat(getComputedStyle(control).fontSize);
  for (let step = 0; step < 8 && size >= FORCE_STEPPER_MIN_FONT; step += 1) {
    const box = control.getBoundingClientRect();
    const ratio = Math.min(room.width / box.width, room.height / box.height);
    if (ratio >= 1) break;
    size = Math.floor(size * ratio * 0.99 * 100) / 100;
    control.style.fontSize = `${size}px`;
  }
  control.hidden = !(size >= FORCE_STEPPER_MIN_FONT);
}

/* The band follows the board, so a ResizeObserver on it re-fits the rows
   whenever the window (or the table's columns) change size, without a
   re-render. One band at a time: every render builds a new one. */
let forceStepperObserver = null;

function watchForceStepper(holder) {
  if (typeof ResizeObserver !== "function") return;
  if (!forceStepperObserver) {
    forceStepperObserver = new ResizeObserver((entries) => {
      for (const entry of entries) fitForceStepper(entry.target);
    });
  }
  forceStepperObserver.disconnect();
  forceStepperObserver.observe(holder);
}

/* Live markers on the printed tracks (catalog.tracks, percent of the
   scan): Influence cubes and Alliance rings on the Faction strips, VP
   tokens on the score column, strength tokens on the combat track, each
   seat's garrison in its ring and deployed units in its Conflict quadrant,
   and Councilor tokens on the High Council seats. */
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
     player earns it and takes it into their supply [Main pp. 4, 7]; the
     vacated ring takes the holder's colour. */
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

    /* The seat's garrison in its bracketed circle and the units deployed
       this round in its quadrant of the central field [Main p. 10], a
       piece each. A Maker Hooks token lies in the slot printed over the
       ring's outer corner, so the garrison keeps clear of it; the token is
       drawn after the garrison, on top of the ring's name. */
    const hooks = player.maker_hooks && tracks.maker_hooks ? tracks.maker_hooks : null;
    const garrison = {
      troop: player.troops_garrison || 0,
      commander: player.commanders_garrison || 0,
    };
    if (tracks.garrison_units && GARRISON_UNIT_KINDS.some((kind) => garrison[kind] > 0)) {
      const avoid = hooks ? [makerHooksBox(seat, hooks)] : [];
      stage.appendChild(garrisonUnits(seat, garrison, tracks.garrison_units, avoid));
    }
    if (hooks) stage.appendChild(makerHooksToken(seat, hooks));

    const unitLayout = tracks.conflict_units;
    const counts = {
      troop: player.troops_conflict || 0,
      commander: player.commanders_conflict || 0,
      agent: player.agent_in_conflict || 0,
      sandworm: player.sandworms_conflict || 0,
    };
    if (CONFLICT_UNIT_KINDS.some((kind) => counts[kind] > 0)) {
      stage.appendChild(conflictUnits(seat, counts, unitLayout));
    }

    /* The seat to move sends and takes back its units on the board too,
       just above the Conflict (forceStepper). */
    if (seat === state.viewSeat && !state.review && state.actions && tracks.force_stepper_band) {
      const families = countFamilies(state.actions.actions);
      const rows = [...families.entries()].filter(([id]) => FORCE_STEPPER_ACTIONS.has(id));
      if (rows.length) stage.appendChild(forceStepper(seat, rows, tracks.force_stepper_band));
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
  title.appendChild(chip(spaceId, "spaces"));
  const flags = [];
  if (entry.combat) flags.push(t("board.flag_combat_space"));
  if (entry.maker) flags.push(phraseText("{maker}"));
  if (entry.critical) flags.push(phraseText("{control}"));
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
  const notesKo = entry.notes_ko || [];
  entry.notes.forEach((noteText, i) => {
    detail.appendChild(effectLine(noteText, notesKo[i], "muted"));
  });
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
    status.push(t("board.bonus_spice", { count: makerSpice.get(spaceId) }));
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
   when a legal action references it; a click applies or focuses. A card
   the seat's decision offers but it cannot take now (a Row card it cannot
   afford, an Intrigue card it cannot play) is dimmed instead, with the
   server's reason in its title (render.js unavailableRef). */
function visualCard(instanceId, options = {}) {
  const entry = options.entry || entryOf(instanceId);
  const card = document.createElement("button");
  card.type = "button";
  card.className = "vcard" + (options.className ? ` ${options.className}` : "");
  card.dataset.instance = instanceId;
  const legal = legalActionsFor(instanceId);
  if (legal.length) card.classList.add("legal");
  const blocked = legal.length ? null : unavailableRef(instanceId);
  if (blocked) card.classList.add("blocked");
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
  const name = entry ? entry.name : nameOf(instanceId);
  card.title = blocked ? `${name} — ${unavailableText(blocked)}` : name;
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
/* `key`: the column's name for folding and for data-strip. A title that
   follows the language passes the English name it always had, so a fold
   survives a switch and the folds saved before it still apply. */
function stripBox(title, count, className, key) {
  const box = document.createElement("div");
  box.className = "strip" + (className ? ` ${className}` : "");
  const name = key || stripName(title);
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

function cardStrip(parent, title, ids, emptyText, options = {}, key = undefined) {
  const box = stripBox(title, ids.length, undefined, key);
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

  if (state.summary.immortality) renderBeneTleilax(market, view);
  if (state.summary.tech_module) renderIxianEmbassy(market, view);

  /* The draft pool stays in the view after every seat has picked; the
     chosen Leaders then live on the seat cards, so the strip goes away. */
  const drafting = view.players.some((p) => !p.leader_id);
  if (view.leader_draft_pool.length && drafting) {
    const picked = new Set(view.players.map((p) => p.leader_id).filter(Boolean));
    cardStrip(
      market,
      t("board.strip_leader_draft"),
      view.leader_draft_pool,
      "",
      (id) => ({
        className: "leader" + (picked.has(id) ? " taken" : ""),
        badge: picked.has(id) ? t("board.leader_taken") : null,
      }),
      "Leader draft",
    );
  }

  /* With the board scan the Conflict card and the face-up contracts sit
     in their printed slots on the board (renderSlotCards); the strips
     below only cover the text-board fallback. */
  const onBoard = Boolean(state.catalog.board_image);
  if (!onBoard) {
    cardStrip(
      market,
      phraseText("{conflict}"),
      view.current_conflict_ids,
      t("board.conflict_not_revealed"),
      { className: "conflict" },
      "Conflict",
    );
  }
  cardStrip(
    market,
    phraseText("{imperium_row}"),
    view.imperium_row,
    t("common.empty"),
    {},
    "Imperium Row",
  );
  if (state.summary.immortality) renderTleilaxuRow(market, view);
  cardStrip(
    market,
    t("board.strip_reserve"),
    view.reserve_stacks.map(([cardId]) => cardId),
    "",
    (id) => {
      const stack = view.reserve_stacks.find(([cardId]) => cardId === id);
      return { badge: `×${stack ? stack[1] : 0}` };
    },
    "Reserve",
  );

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
      undefined,
      "Sardaukar Commander",
    );
    const row = document.createElement("div");
    row.className = "strip-cards wrap";
    if (!spaces.length) {
      const empty = document.createElement("span");
      empty.className = "muted";
      empty.textContent = t("board.no_commanders_on_board");
      row.appendChild(empty);
    }
    for (const spaceId of spaces) row.appendChild(chip(spaceId, "spaces"));
    box.appendChild(row);
    market.appendChild(box);
    cardStrip(
      market,
      t("board.strip_skills", { count: view.skill_stack_size || 0 }),
      (view.skill_face_up || []).map(skillIdOf),
      t("common.none"),
      { className: "skill" },
      "Skill (face-up)",
    );
  }
  if (state.summary.tech_module) {
    if ((view.tech_trash || []).length) {
      cardStrip(
        market,
        t("board.strip_tech_trash"),
        view.tech_trash,
        "",
        { className: "tile taken" },
        "Tech trash",
      );
    }
  }
  if (state.summary.choam_module && !onBoard) {
    cardStrip(
      market,
      t("board.strip_contracts", { count: view.contract_bank_size }),
      view.face_up_contract_ids,
      t("common.empty"),
      { className: "contract" },
      "Contracts",
    );
  }
  /* Shaddam's set-aside Sardaukar contracts are drawn on his leader
     popover (core.js leaderSardaukarRow), not in the shared market. */
  renderIntriguePiles(market, view);
  /* Folding is only worth anything if the column then gives its width back,
     and #market has a min-width that would otherwise hold it open. */
  const boxes = [...market.querySelectorAll(".strip[data-strip]")];
  market.classList.toggle(
    "all-folded",
    boxes.length > 0 && boxes.every((box) => box.classList.contains("collapsed")),
  );
}

function renderIxianEmbassy(market, view) {
  /* The Ixian Embassy's three stacks: the face-up top of each with the
     stack size; an emptied stack simply offers nothing [Bloodlines p. 7]. */
  const box = stripBox(
    t("board.strip_ixian_embassy"),
    (view.tech_face_up || []).filter(Boolean).length,
    undefined,
    "Ixian Embassy",
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
}

/* The public Intrigue discard pile as one line: the cards themselves only
   matter when somebody wants to look back, so a click lists them (newest
   first) — the face-up discard pile beside the deck [Main p. 7]. Intrigue
   cards have no trash pile: a trashed one lies here too (OQ-061, user
   ruling 2026-10-04). */
function renderIntriguePiles(market, view) {
  const discard = view.intrigue_discard || [];
  if (!discard.length) return;
  const box = document.createElement("div");
  box.className = "strip";
  const pile = document.createElement("button");
  pile.type = "button";
  pile.className = "pile-button";
  pile.dataset.pile = "intrigue";
  pile.appendChild(tNode("board.intrigue_discard_count", { count: discard.length }));
  pile.title = t("board.intrigue_pile_title");
  pile.addEventListener("click", (event) => {
    event.stopPropagation();
    openPileList(t("board.pile_intrigue_discard"), [...discard].reverse(), pile);
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
  heading.textContent = phraseText("{bene_tleilax_board}");
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

function renderTleilaxuRow(market, view) {
  /* The Tleilaxu Row: two deck cards bought with specimens plus the fixed
     Reclaimed Forces card [Immortality pp. 6, 9]. */
  const rowIds = [...(view.tleilaxu_row || []), "reclaimed_forces"];
  const tleilaxuRow = cardStrip(
    market,
    t("board.strip_tleilaxu_row", { count: view.tleilaxu_deck_size || 0 }),
    rowIds,
    "",
    (id) => {
      const entry = entryOf(id);
      const specimens = entry && entry.specimens !== undefined ? entry.specimens : null;
      return {
        className: id === "reclaimed_forces" ? "reclaimed" : "",
        badge: specimens === null ? null : phraseText(`{specimen} ×${specimens}`),
      };
    },
    "Tleilaxu Row",
  );
  /* Back Room Deal's Solari lie on Reclaimed Forces until someone next
     acquires it. */
  const reclaimed = tleilaxuRow.querySelector('.vcard[data-instance="reclaimed_forces"]');
  const tray = reclaimed && scoutsTray("reclaimed_forces", view);
  if (tray) reclaimed.appendChild(tray);
}

function renderBeneTleilax(market, view) {
  const layout = state.catalog && state.catalog.bene_tleilax;
  if (!layout) return;
  const box = stripBox(
    phraseText("{bene_tleilax_board}"),
    null,
    "bene-tleilax",
    "Bene Tleilax board",
  );

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
    cell.title = `${researchSpaceName(space.id, false)} · ${phraseText(RESEARCH_BONUS_LABELS[space.bonus] || t("board.no_bonus"))}`;
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
      spice.append(icon("spice", phraseText("{spice}")), String(view.tleilaxu_track_spice));
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
  trackHead.textContent = t("board.tleilaxu_track");
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
  map.alt = phraseText("{bene_tleilax_board}");
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
        : `${researchSpaceName(spaceId, false)} · ${phraseText(RESEARCH_BONUS_LABELS[bonusOf[spaceId]] || t("board.no_bonus"))}`;
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
  const scouts = overlay.scouts || null;
  const scoutsRows = scouts ? scoutsPieceRows(view) : [];
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
      `${t("board.tleilaxu_track")} ${index}${TLEILAXU_TRACK_LABELS[bonus] ? " · " + phraseText(TLEILAXU_TRACK_LABELS[bonus]) : ""}`;
    stage.appendChild(cell);
    /* Tleilaxu Offering's troops on the track's third space, under the
       tokens that come to stand there. */
    if (scouts && index === scouts.offering_space) {
      renderScoutsRegionPieces(stage, scoutsRows, "tleilaxu_track", scouts);
    }
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
  /* Sponsored Research's spice beside the Helix, the first genetic
     marker (OQ-089 (b)): the setup spice's hexagon. */
  if (scouts) {
    let x = scouts.helix_spice_point[0];
    for (const row of scoutsRowsAt(scoutsRows, "helix")) {
      const [w, h] = overlay.spice_size;
      const piece = scoutsPiece(row, { x: x - w / 2, y: scouts.helix_spice_point[1] - h / 2, w, h });
      stage.appendChild(piece);
      x -= w + scouts.gap[0];
    }
  }
  /* The setup spice on the fourth space [Immortality p. 4], the same
     hexagon as a Maker space's bonus spice over the printed "1st / 2" one. */
  if (view.tleilaxu_track_spice) {
    const spice = spiceHex(
      view.tleilaxu_track_spice,
      overlay.spice_point,
      overlay.spice_size,
      t("board.spice_first_reacher"),
    );
    spice.classList.add("bt-spice");
    stage.appendChild(spice);
  }
  return stage;
}

/* ---------- Arrakeen Scouts: mission pieces on the boards ---------- */

/* Every Scouts piece in the view, one entry per row of it: bank goods
   (view.scouts_goods, seat -1 for anyone), parked troops (scouts_parked)
   and face-down piles (scouts_board_card_counts: the view carries only
   their counts, never the cards). `key` names the row for the DOM. */
function scoutsPieceRows(view) {
  const rows = [];
  (view.scouts_goods || []).forEach(([mission, location, resource, count, seat], index) => {
    rows.push({ key: `goods:${index}`, kind: resource, mission, location, count, seat });
  });
  (view.scouts_parked || []).forEach(([mission, seat, location, troops], index) => {
    rows.push({ key: `parked:${index}`, kind: "troop", mission, location, count: troops, seat });
  });
  (view.scouts_board_card_counts || []).forEach(([mission, location, count], index) => {
    rows.push({
      key: `cards:${index}`,
      kind: mission === "choam_research" ? "contract" : "intrigue",
      mission,
      location,
      count,
      seat: -1,
    });
  });
  return rows;
}

/* The rows waiting at one location, in the order they are laid out: the
   bank's goods and piles first, then each seat's troops and goods. */
const SCOUTS_KIND_ORDER = ["contract", "intrigue", "maker_hooks", "troop", "marker", "spice", "solari", "water"];

function scoutsRowsAt(rows, location) {
  const order = (row) => SCOUTS_KIND_ORDER.indexOf(row.kind);
  return rows
    .filter((row) => row.location === location)
    .sort((a, b) => a.seat - b.seat || order(a) - order(b));
}

/* "Prison Planet · 2 spice (Seat 1)": the piece's mission, what it is and
   whose, in the page's language. */
function scoutsPieceTitle(row) {
  let goods;
  if (row.kind === "troop") goods = scoutsParkedText(row.count);
  else if (row.kind === "contract" || row.kind === "intrigue") {
    goods = scoutsFaceDownText(row.count);
  } else goods = phraseText(scoutsGoodsText(row.kind, row.count));
  const who = row.seat < 0 ? t("panels.scouts_anyone") : t("common.seat", { seat: row.seat });
  return t("board.scouts_piece", { mission: scoutsItem(row.mission).name, goods, who });
}

/* A piece's footprint (width, height) in stage percent at scale 1:
   several troops of one row stand side by side, as do several drops. */
function scoutsPieceSize(row, layout) {
  const [w, h] = layout.sizes[row.kind] || layout.sizes.spice;
  if (row.kind === "troop" || row.kind === "water") {
    const n = Math.max(1, row.count);
    return [n * w + (n - 1) * layout.gap[0], h];
  }
  return [w, h];
}

/* Where each unit lies in a location's free regions (catalog
   tracks.scouts.regions): rows from each region's start edge (the bottom
   one for `from_bottom`), left to right; a unit's pieces `gap` apart,
   groups `group_gap` apart. A group (the consecutive units sharing
   `group`: one seat's pieces, or one mission's bank goods) lies whole in
   the first region with room for all of it, never split across two, and a
   unit that `overlap`s the one before it (goods on their marker or troop)
   stays in that unit's row. A crowded location shrinks every piece in
   steps of 0.05 down to `min_scale`; past that the last region's rows
   close up. Pure: returns {scale, places: [{x, y, w, h}]} (top-left corner
   and size, stage percent), in the units' order. */
function scoutsPieceLayout(units, regions, layout) {
  const [gapX, gapY] = layout.gap;
  const groupGapX = layout.group_gap[0];
  const attempt = (scale, overflow) => {
    const boxes = regions.map((region) => ({ region, rows: [] }));
    /* One unit into `box`: its last row when there is room (always for an
       overlapping unit), else a new row under it (past the bottom only
       when `deep`). Returns the placement or null, changing nothing. */
    const fit = (box, unit, deep) => {
      const w = unit.w * scale;
      const h = unit.h * scale;
      const [, , width, height] = box.region.box;
      const row = box.rows[box.rows.length - 1];
      if (row) {
        const gap = row.group === unit.group
          ? (unit.overlap ? -unit.overlap * w : gapX * scale)
          : groupGapX * scale;
        const grown = Math.max(row.h, h);
        if (row.x + gap + w <= width + 1e-9 && (row.top + grown <= height + 1e-9 || deep)) {
          return { row, x: row.x + gap, w, h, grown };
        }
        if (unit.overlap && row.group === unit.group) return null;
      }
      const top = row ? row.top + row.h + gapY * scale : 0;
      if (w <= width + 1e-9 && (top + h <= height + 1e-9 || deep)) {
        return { row: null, top, x: 0, w, h, grown: h };
      }
      return null;
    };
    /* The whole group into `box`, or nothing (its rows as they were). */
    const settle = (box, group, deep) => {
      const saved = box.rows.map((row) => [row, row.x, row.h, row.group, row.items.length]);
      const count = box.rows.length;
      const done = [];
      for (const unit of group) {
        const spot = fit(box, unit, deep);
        if (!spot) {
          box.rows.length = count;
          for (const [row, x, h, owner, items] of saved) {
            Object.assign(row, { x, h, group: owner });
            row.items.length = items;
          }
          return null;
        }
        let row = spot.row;
        if (!row) {
          row = { top: spot.top, h: spot.h, x: 0, items: [], group: unit.group };
          box.rows.push(row);
        }
        const item = { w: spot.w, h: spot.h, x: spot.x };
        row.items.push(item);
        row.h = spot.grown;
        row.x = Math.max(row.x, spot.x + spot.w);
        row.group = unit.group;
        done.push({ item, row, box });
      }
      return done;
    };
    const placed = [];
    /* Regions fill in order: a group never goes back to an earlier one. */
    let first = 0;
    for (let start = 0; start < units.length;) {
      let stop = start + 1;
      while (stop < units.length && units[stop].group === units[start].group) stop += 1;
      const group = units.slice(start, stop);
      let done = null;
      for (let index = first; index < boxes.length && !done; index += 1) {
        done = settle(boxes[index], group, overflow && index === boxes.length - 1);
        if (done) first = index;
      }
      if (!done) return null;
      placed.push(...done);
      start = stop;
    }
    for (const box of boxes) {
      const height = box.region.box[3];
      const end = box.rows.length ? box.rows[box.rows.length - 1] : null;
      const depth = end ? end.top + end.h : 0;
      /* Closing up: every row's offset shrinks by one factor so the last
         one ends inside the region. */
      box.squeeze = depth > height && end && end.top > 0
        ? Math.max(0, height - end.h) / end.top
        : 1;
    }
    return placed.map(({ item, row, box }) => {
      const [left, top, , height] = box.region.box;
      const rowTop = row.top * box.squeeze;
      const y = box.region.from_bottom
        ? top + height - rowTop - row.h + (row.h - item.h) / 2
        : top + rowTop + (row.h - item.h) / 2;
      return { x: left + item.x, y, w: item.w, h: item.h };
    });
  };
  let scale = 1;
  for (;;) {
    const places = attempt(scale, false);
    if (places) return { scale, places };
    if (scale <= layout.min_scale + 1e-9) break;
    scale = Math.max(layout.min_scale, Math.round((scale - 0.05) * 100) / 100);
  }
  return { scale, places: attempt(scale, true) || [] };
}

/* One Scouts piece, named for its row. Seat pieces are flat in the seat's
   colour with the cubes' dark edge: a cube per parked troop, a Control
   marker as the printed flag's pennant. The bank's goods are the tokens the
   board prints: a spice hexagon and a Solari coin with the amount, a water
   drop per water; the Maker Hooks token is its picture (or the icon); a
   face-down pile is a card back with its count and nothing else. The box
   is the piece's footprint, centred on (x, y) in stage percent (or sized
   in em when `inline`, for the seat panel and the Tleilaxu Row). */
function scoutsPiece(row, box, { inline = false } = {}) {
  const piece = document.createElement("span");
  piece.className = `scouts-piece scouts-${row.kind}` + (inline ? " inline" : "");
  piece.dataset.row = row.key;
  piece.dataset.location = row.location;
  piece.dataset.mission = row.mission;
  piece.dataset.kind = row.kind;
  if (row.seat >= 0) piece.dataset.seat = String(row.seat);
  const title = scoutsPieceTitle(row);
  piece.title = title;
  piece.setAttribute("role", "img");
  piece.setAttribute("aria-label", title);
  if (box) {
    const { x, y, w, h } = box;
    piece.style.width = `${w}%`;
    piece.style.height = `${h}%`;
    placeAt(piece, x + w / 2, y + h / 2);
  }
  const count = (text) => {
    const number = document.createElement("span");
    number.className = "scouts-count" + (String(text).length > 1 ? " wide" : "");
    number.textContent = String(text);
    return number;
  };
  const svgNs = "http://www.w3.org/2000/svg";
  switch (row.kind) {
    case "troop":
    case "water": {
      const n = Math.max(1, row.count);
      for (let index = 0; index < n; index += 1) {
        let part;
        if (row.kind === "troop") {
          part = document.createElement("span");
          part.className = "scouts-cube";
          part.style.background = SEAT_COLORS[row.seat];
        } else {
          part = document.createElementNS(svgNs, "svg");
          part.setAttribute("class", "scouts-drop");
          part.setAttribute("viewBox", "0 0 58 100");
          part.setAttribute("preserveAspectRatio", "none");
          const drop = document.createElementNS(svgNs, "path");
          drop.setAttribute("d", "M29 2 C35 22 56 44 56 68 A27 29 0 0 1 2 68 C2 44 23 22 29 2 Z");
          part.appendChild(drop);
        }
        /* Each part is 1/n of the row less the gaps between them. */
        part.style.width = `calc((100% - ${n - 1} * var(--scouts-gap, 0%)) / ${n})`;
        part.style.left = `calc(${index} * ((100% - ${n - 1} * var(--scouts-gap, 0%)) / ${n} + var(--scouts-gap, 0%)))`;
        piece.appendChild(part);
      }
      break;
    }
    case "spice":
    case "solari":
      piece.appendChild(count(row.count));
      break;
    case "marker": {
      const dip = 100 * (1 - ((state.catalog.tracks.control_flags || {}).notch || 0.2));
      const pennant = document.createElementNS(svgNs, "svg");
      pennant.setAttribute("class", "scouts-pennant");
      pennant.setAttribute("viewBox", "0 0 100 100");
      pennant.setAttribute("preserveAspectRatio", "none");
      const shape = document.createElementNS(svgNs, "polygon");
      shape.setAttribute("points", `0,0 100,0 100,100 50,${dip} 0,100`);
      shape.setAttribute("fill", SEAT_COLORS[row.seat]);
      pennant.appendChild(shape);
      piece.appendChild(pennant);
      break;
    }
    case "maker_hooks": {
      const url = state.catalog.maker_hooks_token;
      if (url) {
        const picture = document.createElement("img");
        picture.src = url;
        picture.alt = "";
        picture.draggable = false;
        piece.appendChild(picture);
      } else {
        piece.classList.add("drawn");
        const mark = icon("maker_hooks", title);
        mark.removeAttribute("title");
        piece.appendChild(mark);
      }
      break;
    }
    case "contract":
    case "intrigue": {
      const mark = icon(row.kind, phraseText(`{${row.kind}}`));
      mark.removeAttribute("title");
      mark.setAttribute("aria-hidden", "true");
      piece.append(mark, count(row.count));
      break;
    }
    default:
      piece.appendChild(count(row.count));
  }
  return piece;
}

/* A location's regions less the boxes a piece stands in (a Sardaukar
   Commander on the space's frame corner): a region such a box cuts keeps
   its parts left and right of it, full height. */
function scoutsRegionsClear(regions, avoid) {
  let result = regions;
  for (const [bl, bt, bw, bh] of avoid) {
    const next = [];
    for (const region of result) {
      const [left, top, width, height] = region.box;
      const clear = bl >= left + width || bl + bw <= left || bt >= top + height || bt + bh <= top;
      if (clear) {
        next.push(region);
        continue;
      }
      const margin = 0.2;
      if (bl - margin - left > 0.5) {
        next.push({ ...region, box: [left, top, bl - margin - left, height] });
      }
      if (left + width - (bl + bw + margin) > 0.5) {
        next.push({ ...region, box: [bl + bw + margin, top, left + width - bl - bw - margin, height] });
      }
    }
    result = next;
  }
  return result;
}

/* The box (stage percent) of the Sardaukar Commander standing on a space's
   frame (commanderPiece). */
function commanderBox(spaceBox) {
  const [left, top, width, height] = spaceBox;
  const spot = state.catalog.commander_spot;
  const size = state.catalog.tracks.conflict_units.sizes.commander;
  const tall = height * spot.height;
  const wide = tall * (size[0] / size[1]);
  const x = left + width * spot.anchor[0];
  const y = top + height * spot.anchor[1];
  return [x - wide * spot.base[0], y - tall * spot.base[1], wide, tall];
}

/* The pieces waiting at `location` laid out in its regions
   (layout.regions[location], scoutsPieceLayout) and drawn on `stage`. */
function renderScoutsRegionPieces(stage, rows, location, layout, avoid = []) {
  const regions = scoutsRegionsClear(layout.regions[location] || [], avoid);
  const here = scoutsRowsAt(rows, location);
  if (!regions.length || !here.length) return;
  const units = here.map((row, index) => {
    const [w, h] = scoutsPieceSize(row, layout);
    /* A seat's goods lie on its marker or against its troop: they overlap
       the piece before them a little, as they do on the table. */
    const before = here[index - 1];
    const onto = row.seat >= 0 && before && before.seat === row.seat
      && before.mission === row.mission && (before.kind === "troop" || before.kind === "marker");
    return {
      w,
      h,
      group: row.seat < 0 ? `bank:${row.mission}` : `seat:${row.seat}`,
      overlap: onto ? 0.35 : 0,
    };
  });
  const { scale, places } = scoutsPieceLayout(units, regions, layout);
  here.forEach((row, index) => {
    const place = places[index];
    if (!place) return;
    const piece = scoutsPiece(row, place);
    piece.dataset.scale = String(scale);
    piece.style.setProperty("--scouts-gap", `${((layout.gap[0] * scale) / place.w) * 100}%`);
    stage.appendChild(piece);
  });
}

/* The Scouts pieces on the main board scan: the goods, parked troops and
   face-down piles of each space in the free parts of its printed panel
   (catalog.tracks.scouts.regions), and the goods of an observation post on
   its disc (beside it when a Spy stands there). Locations the scan has no
   place for (a seat's Contract, the Bene Tleilax board, the Tleilaxu Row)
   are drawn where those are; the Scouts panel lists them all as text. */
function renderScoutsBoardPieces(stage, view, spies) {
  const layout = state.catalog.tracks && state.catalog.tracks.scouts;
  if (!layout) return;
  const rows = scoutsPieceRows(view);
  if (!rows.length) return;
  const commanders = new Set(view.sardaukar_commander_space_ids || []);
  for (const location of Object.keys(layout.regions)) {
    const space = state.catalog.spaces[location];
    const avoid = space && commanders.has(location) && state.catalog.commander_spot
      ? [commanderBox(space.box)]
      : [];
    renderScoutsRegionPieces(stage, rows, location, layout, avoid);
  }
  const size = state.catalog.post_size || 1.93;
  const byPost = new Map();
  for (const row of rows) {
    if (!row.location.startsWith("post:")) continue;
    const postId = row.location.slice("post:".length);
    if (!state.catalog.posts[postId]) continue;
    if (!byPost.has(postId)) byPost.set(postId, []);
    byPost.get(postId).push(row);
  }
  for (const [postId, here] of byPost) {
    const [px, py] = state.catalog.posts[postId];
    const guarded = (spies.get(postId) || []).length > 0;
    let x = guarded ? px + size / 2 + layout.gap[0] : null;
    here.forEach((row, index) => {
      const [w, h] = scoutsPieceSize(row, layout);
      if (x === null) x = px - w / 2;
      const place = { x, y: py - h / 2, w, h };
      x += w + layout.gap[0];
      const piece = scoutsPiece(row, place);
      piece.dataset.index = String(index);
      stage.appendChild(piece);
    });
  }
}

/* The Scouts pieces of a location drawn on something that is not a scan
   (a seat's face-up Contract in its panel, Reclaimed Forces in the
   Tleilaxu Row): small tokens in em, in a tray the caller places. */
function scoutsTray(location, view) {
  const rows = scoutsRowsAt(scoutsPieceRows(view), location);
  if (!rows.length) return null;
  const tray = document.createElement("span");
  tray.className = "scouts-tray";
  tray.dataset.location = location;
  for (const row of rows) tray.appendChild(scoutsPiece(row, null, { inline: true }));
  return tray;
}
