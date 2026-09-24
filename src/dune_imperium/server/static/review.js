"use strict";

/* ---------- replay review ---------- */

/* `options.cursor`: the step to open at (default: the end of the game).
   `options.play`: start walking forward from there (playback below). */
async function enterReview(seat, options) {
  const gameId = state.gameId;
  const meta = await api(`/games/${gameId}/review?seat=${seat}`);
  if (state.gameId !== gameId || !state.summary) return;
  stopPlayback();
  const wanted = options && typeof options.cursor === "number" ? options.cursor : null;
  const cursor = wanted === null ? meta.step_count : wanted;
  /* The log position of every live step: steps that were taken back and
     the undo markers sit between them (reviewLog). */
  const liveIndex = [];
  for (const entry of meta.log || []) {
    if (entry.type !== "undo" && !entry.undone) liveIndex.push(entry.index);
  }
  state.review = {
    meta,
    seat,
    cursor,
    /* Where the cursor stood before its latest move: what lies between is
       what the log marks as fresh. */
    cameFrom: cursor,
    round: null,
    phase: null,
    liveIndex,
    stops: turnStops(meta.steps),
    /* Opened by hand (renderDisclosure); another seat's eyes keep it. */
    disclosureOpen: Boolean(state.review && state.review.disclosureOpen),
  };
  labelReviewBar(seat);
  const slider = el("review-slider");
  slider.max = String(meta.step_count);
  el("review-bar").hidden = false;
  await reviewGoto(cursor);
  if (options && options.play && state.review && state.review.meta === meta) {
    /* The opening position gets its interval on screen too. */
    startPlayback(playback.intervalMs);
  }
}

/* The seat choices and the "own action" buttons, in the page's language:
   set by enterReview and again by a language switch. */
function labelReviewBar(seat) {
  const select = el("review-seat");
  select.textContent = "";
  /* A finished game is fully disclosed (OQ-010), so any seat — human or
     AI — can be reviewed from its own perspective. */
  state.summary.seats.forEach((kind, reviewSeat) => {
    const option = document.createElement("option");
    option.value = String(reviewSeat);
    option.textContent = t("review.seat_option", {
      seat: reviewSeat,
      kind: seatKindLabel(kind),
    });
    select.appendChild(option);
  });
  select.value = String(seat);
  /* "My actions" are the reviewed seat's; with nobody at the table the
     buttons say whose they are. */
  const own = humanSeats().length ? t("review.own_mine") : t("review.own_seat");
  el("review-prev-own").textContent = t("review.prev_own_action", { own });
  el("review-next-own").textContent = t("review.next_own_action", { own });
}

/* Review states load at very different speeds (the server replays every
   step up to the cursor), so answers can arrive out of order; only the
   latest request may draw. Resolves to true once it drew, false when the
   request failed, and null when a later request (or leaving review) took
   the page over meanwhile. */
let reviewRequest = 0;

async function reviewGoto(cursor) {
  const review = state.review;
  if (!review) return null;
  cursor = Math.max(0, Math.min(review.meta.step_count, cursor));
  const request = ++reviewRequest;
  try {
    hideGameError();
    const payload = await api(
      `/games/${state.gameId}/review/${cursor}?seat=${review.seat}`
    );
    if (request !== reviewRequest || state.review !== review) return null;
    review.cameFrom = review.cursor;
    review.cursor = cursor;
    review.round = payload.round_number;
    review.phase = payload.phase;
    state.view = payload.view;
    state.actions = null;
    el("review-slider").value = String(cursor);
    writeReviewStatus(review);
    renderPlaybackControls();
    render();
    return true;
  } catch (error) {
    showGameError(t("review.status_fetch_failed", { message: error.message }));
    return false;
  }
}

/* What the cursor's latest move showed: the step under the cursor, or,
   when the move was one whole turn forward (turn-by-turn playback), the
   action that opened the turn — it says where the Agent went — and how
   many steps came with it. A seek across several turns names no turn. */
function describeReviewSpan(review) {
  const steps = review.meta.steps;
  const stride = review.cursor - review.cameFrom;
  const oneTurn =
    stride > 1 && review.stops.find((stop) => stop > review.cameFrom) === review.cursor;
  const opening = oneTurn
    ? steps.slice(review.cameFrom, review.cursor).find((label) => label.type === "action")
    : null;
  if (!opening) return describeReviewStep(steps[review.cursor - 1]);
  return t("review.span_extra", { opening: describeReviewStep(opening), extra: stride - 1 });
}

function describeReviewStep(label) {
  if (!label) return t("review.before_game_start");
  if (label.type === "chance") {
    const values = label.values || [];
    const shown =
      values.length <= 3
        ? values.map(nameOf).join(", ")
        : t("review.chance_values", {
            count: values.length,
            names: values.slice(0, 3).map(nameOf).join(", "),
          });
    return (
      t("core.chance_label", { decision: describeChance(label.decision_id) }) +
      (shown ? ` — ${shown}` : "")
    );
  }
  return t("review.step_label", { seat: label.actor, action: describeActionText(label) });
}

function reviewJumpOwn(direction) {
  const review = state.review;
  if (!review) return;
  const steps = review.meta.steps;
  for (
    let cursor = review.cursor + direction;
    cursor >= 1 && cursor <= steps.length;
    cursor += direction
  ) {
    const label = steps[cursor - 1];
    if (label.type === "action" && label.actor === review.seat) {
      reviewGoto(cursor).catch(() => {});
      return;
    }
  }
}

function exitReview() {
  stopPlayback();
  state.review = null;
  el("review-bar").hidden = true;
  refresh().catch(() => {});
}

/* The finished game's log as far as the review cursor: every entry up to
   the cursor's live step, the steps taken back on the way included, as they
   happened. What the cursor's latest move forward added counts as fresh. */
function reviewLog(review) {
  const entries = review.meta.log || [];
  const lengthAt = (cursor) =>
    cursor >= review.liveIndex.length
      ? entries.length
      : cursor <= 0
        ? 0
        : review.liveIndex[cursor - 1] + 1;
  const count = lengthAt(review.cursor);
  return {
    entries: entries.slice(0, count),
    count,
    freshFrom: lengthAt(Math.min(review.cameFrom, review.cursor)),
  };
}

/* ---------- playback (watching a finished game unfold) ---------- */

/* The review cursor walks forward by itself, one turn or one step per
   interval. A game of AI seats only is watched this way (watchGame): the
   server plays such a game to the end as it is created — a session rests on
   a human decision or on the finished game — so by the time anybody looks
   there is a full record to walk through and nothing left to wait for. */
const playback = { playing: false, timer: 0, unit: "turn", intervalMs: 1000 };

/* Declining a Combat or Endgame Intrigue window (rules/combat.py,
   rules/endgame.py): both count as "a pass" for turnStops below, whichever
   seat and whichever of the two it is. */
const PASS_ACTION_IDS = new Set(["pass_combat_intrigue", "pass_endgame_intrigue"]);

/* Where turn-by-turn playback stops: the cursor positions between two
   turns, by the rule the log's turn cards follow (logGroups) — the action
   before closed its turn, or the next action is another seat's. Chance steps
   go with the action before them, and seats passing one after another (a
   Combat Intrigue window nobody used) make one stop, not four. */
function turnStops(steps) {
  const stops = [];
  let last = null;
  steps.forEach((label, position) => {
    if (label.type !== "action") return;
    if (last) {
      const closed =
        SOLO_ACTIONS.has(last.action_id) ||
        QUIET_ACTIONS.has(last.action_id) ||
        label.actor !== last.actor;
      const passing =
        PASS_ACTION_IDS.has(last.action_id) && PASS_ACTION_IDS.has(label.action_id);
      if (closed && !passing) stops.push(position);
    }
    last = label;
  });
  stops.push(steps.length);
  return stops;
}

function playbackNext(review) {
  if (playback.unit === "step") return review.cursor + 1;
  const stop = review.stops.find((position) => position > review.cursor);
  return stop === undefined ? review.meta.step_count : stop;
}

function schedulePlayback(delay) {
  window.clearTimeout(playback.timer);
  playback.timer = window.setTimeout(() => {
    playbackTick().catch(() => {});
  }, delay);
}

async function playbackTick() {
  const review = state.review;
  if (!review || !playback.playing) return;
  /* A seek in flight owns the next move: a tick now would ask for the step
     after the old cursor and, as the later request, throw the seek away
     (reviewGoto draws only the latest). The seek schedules once it drew. */
  if (review.seek) return;
  if (review.cursor >= review.meta.step_count) {
    stopPlayback();
    return;
  }
  const started = performance.now();
  const drew = await reviewGoto(playbackNext(review));
  if (state.review !== review || !playback.playing) return;
  /* A seek answered first, and has set the next move itself (reviewSeek). */
  if (drew === null) return;
  if (drew === false || review.cursor >= review.meta.step_count) {
    stopPlayback();
    return;
  }
  /* The interval runs from one move to the next, not from answer to move. */
  schedulePlayback(Math.max(0, playback.intervalMs - (performance.now() - started)));
}

/* `delay`: how long the position on screen stays before the first move. */
function startPlayback(delay) {
  const review = state.review;
  if (!review) return;
  playback.playing = true;
  renderPlaybackControls();
  if (review.cursor < review.meta.step_count) {
    schedulePlayback(delay || 0);
    return;
  }
  /* Pressed at the end of the game, play starts it over. */
  reviewGoto(0).then((drew) => {
    if (state.review !== review || !playback.playing) return;
    if (drew) schedulePlayback(playback.intervalMs);
    else stopPlayback();
  });
}

function stopPlayback() {
  playback.playing = false;
  window.clearTimeout(playback.timer);
  renderPlaybackControls();
}

/* A seek (slider, first, last) moves the cursor and leaves playback as it
   was; the position sought gets a full interval before the next move.
   Playback holds until the seek has drawn: a tick fired meanwhile — the
   running timer, Play pressed, the interval changed — would ask for the
   step after the old cursor, and being the later request it would win
   (reviewGoto draws only the latest) and throw the seek away. A 0.3 s
   review load against a 0.25 s interval lost every seek that way.
   `review.seek` marks the latest seek until it lands (playbackTick). */
function reviewSeek(cursor) {
  const review = state.review;
  if (!review) return;
  window.clearTimeout(playback.timer);
  const seek = {};
  review.seek = seek;
  const landed = () => {
    if (review.seek === seek) review.seek = null;
  };
  reviewGoto(cursor)
    .then((drew) => {
      landed();
      if (state.review !== review || !playback.playing) return;
      /* null: a later request took over, and schedules for itself. */
      if (drew) schedulePlayback(playback.intervalMs);
      else if (drew === false) stopPlayback();
    })
    .catch(landed);
}

/* Stepping by hand (one step, one own action) takes the wheel. */
function reviewStep(move) {
  if (!state.review) return;
  stopPlayback();
  move();
}

/* The status line of the step on screen, from what the review holds, so a
   language switch can rewrite it at once instead of after its re-fetch. */
function writeReviewStatus(review) {
  const cursor = review.cursor;
  let status =
    t("review.step_count", { cursor, total: review.meta.step_count }) +
    ` · ${t("review.round_label", { round: review.round })}` +
    ` · ${PHASE_LABELS[review.phase] || review.phase}` +
    ` · ${describeReviewSpan(review)}`;
  /* Undo markers that rewound the game to this exact step (M11 slice 6). */
  for (const item of review.meta.undo_history || []) {
    if (item.step !== cursor) continue;
    status +=
      t("review.undo_marker", { seat: item.seat, count: item.count }) +
      item.undone.map(describeActionText).join(" / ");
  }
  el("review-status").textContent = status;
}

function renderPlaybackControls() {
  const review = state.review;
  const atEnd = Boolean(review) && review.cursor >= review.meta.step_count;
  el("review-play").textContent = playback.playing
    ? t("review.pause")
    : atEnd
      ? t("review.replay_from_start")
      : t("review.play");
  el("review-unit").value = playback.unit;
  el("review-interval").value = String(playback.intervalMs);
}

/* A game nobody sits at has no seat to look from while it is live, and it
   is never live when somebody looks: it opens as a review from its first
   position, playing. */
function spectatorOnly() {
  return Boolean(state.summary) && !humanSeats().length;
}

function watchGame() {
  enterReview(state.review ? state.review.seat : 0, { cursor: 0, play: true }).catch(
    (error) => {
      showGameError(t("review.watch_failed", { message: error.message }));
    }
  );
}
