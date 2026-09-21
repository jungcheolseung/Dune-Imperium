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
  const select = el("review-seat");
  select.textContent = "";
  /* A finished game is fully disclosed (OQ-010), so any seat — human or
     AI — can be reviewed from its own perspective. */
  state.summary.seats.forEach((kind, reviewSeat) => {
    const option = document.createElement("option");
    option.value = String(reviewSeat);
    option.textContent = `좌석 ${reviewSeat} (${seatKindLabel(kind)})`;
    select.appendChild(option);
  });
  select.value = String(seat);
  const slider = el("review-slider");
  slider.max = String(meta.step_count);
  el("review-bar").hidden = false;
  /* "My actions" are the reviewed seat's; with nobody at the table the
     buttons say whose they are. */
  const own = humanSeats().length ? "내" : "이 좌석";
  el("review-prev-own").textContent = `이전 ${own} 행동`;
  el("review-next-own").textContent = `다음 ${own} 행동`;
  await reviewGoto(cursor);
  if (options && options.play && state.review && state.review.meta === meta) {
    /* The opening position gets its interval on screen too. */
    startPlayback(playback.intervalMs);
  }
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
    el("game-error").hidden = true;
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
    let status =
      `step ${cursor}/${review.meta.step_count}` +
      ` · 라운드 ${payload.round_number}` +
      ` · ${PHASE_LABELS[payload.phase] || payload.phase}` +
      ` · ${describeReviewSpan(review)}`;
    /* Undo markers that rewound the game to this exact step (M11 slice 6). */
    for (const item of review.meta.undo_history || []) {
      if (item.step !== cursor) continue;
      status +=
        ` · ↩ 좌석 ${item.seat}가 여기서 ${item.count}단계 되돌림: ` +
        item.undone.map(describeAction).join(" / ");
    }
    el("review-status").textContent = status;
    renderPlaybackControls();
    render();
    return true;
  } catch (error) {
    el("game-error").textContent = `검토 상태 조회 실패 (${error.message})`;
    el("game-error").hidden = false;
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
  return `${describeReviewStep(opening)} 외 ${stride - 1}수`;
}

function describeReviewStep(label) {
  if (!label) return "게임 시작 전";
  if (label.type === "chance") {
    const values = label.values || [];
    const shown =
      values.length <= 3
        ? values.map(nameOf).join(", ")
        : `${values.length}장 · ${values.slice(0, 3).map(nameOf).join(", ")} …`;
    return `chance: ${prettify(label.decision_id)}` + (shown ? ` — ${shown}` : "");
  }
  return `좌석 ${label.actor}: ${describeAction(label)}`;
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
      const passing = last.action_id === "pass" && label.action_id === "pass";
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
   was; the position sought gets a full interval before the next move. */
function reviewSeek(cursor) {
  if (!state.review) return;
  if (playback.playing) schedulePlayback(playback.intervalMs);
  reviewGoto(cursor).catch(() => {});
}

/* Stepping by hand (one step, one own action) takes the wheel. */
function reviewStep(move) {
  if (!state.review) return;
  stopPlayback();
  move();
}

function renderPlaybackControls() {
  const review = state.review;
  const atEnd = Boolean(review) && review.cursor >= review.meta.step_count;
  el("review-play").textContent = playback.playing
    ? "일시정지"
    : atEnd
      ? "처음부터 재생"
      : "재생";
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
      el("game-error").textContent = `관전 시작 실패 (${error.message})`;
      el("game-error").hidden = false;
    }
  );
}
