"use strict";

/* ---------- play clock ----------

   How long the game has been played, and each seat's time holding control
   (a chess clock, AI seats included; server/play_clock.py, user request
   2026-10-10). The server sends the clock as of its last change in the
   summary, and a snapshot says how long ago that change was on the
   server's own clock (clock_age_ms): the page adds the time since the
   snapshot arrived, measured here, and never compares its wall clock with
   the server's. After AI moves, `narration` names the AI seats whose
   moves the tables are still showing, piece by piece, before `running`'s
   own clock runs.

   The clocks tick on their own: one painter writes the text of the
   [data-clock] nodes when the shown text changes, on a timer aligned to
   the next whole second. It never draws anything else, so a tick closes no
   popover and makes no request. A review or a watched game shows no clock:
   it has no time per step. */

/* The time sources; a test stands in its own (scripts/e2e/clock.py). */
function clockNow() {
  return performance.now();
}

function clockWallNow() {
  return Date.now();
}

/* A page left asleep (a laptop lid) can stop clockNow while the server's
   clock goes on: once the wall clock pulls this far ahead, the page asks
   for a fresh snapshot rather than guess. */
const CLOCK_STALL_MS = 2000;
const CLOCK_RETRY_MS = 5000;

const playClock = { anchor: null, timer: 0, stallAsked: false };

/* The snapshot just adopted (adoptSnapshot, openGame) carries the clock to
   count from; anything else (a POST's summary) does not. */
function anchorClock(snapshot) {
  const summary = snapshot && snapshot.summary;
  const age = snapshot && snapshot.clock_age_ms;
  if (!summary || !summary.clock || typeof age !== "number") {
    playClock.anchor = null;
    return;
  }
  playClock.anchor = { clock: summary.clock, age, at: clockNow(), wall: clockWallNow() };
  playClock.stallAsked = false;
}

function resetClocks() {
  clearTimeout(playClock.timer);
  playClock.timer = 0;
  playClock.anchor = null;
  playClock.stallAsked = false;
  const header = el("game-clock");
  header.hidden = true;
  header.textContent = "";
  header.removeAttribute("title");
}

/* A live game shows its clocks; a review, a watched game (no human seat)
   and the screens around the table do not. */
function clocksShown() {
  return Boolean(state.gameId && state.summary && state.summary.clock)
    && !state.review && !spectatorOnly() && !el("game-screen").hidden;
}

/* The clock now: the game time, every seat's total, the running seat's
   spell, and the seat whose clock moves right now (`charged`: the running
   seat, or an AI seat while the tables show its moves). null without a
   snapshot's clock for the summary on screen. */
function clockReading() {
  const anchor = playClock.anchor;
  const summary = state.summary;
  if (!anchor || !summary || summary.clock !== anchor.clock) return null;
  const clock = anchor.clock;
  const age = Math.max(0, anchor.age + clockNow() - anchor.at);
  const seats = clock.seat_ms.slice();
  const running = clock.running;
  let spell = running === null ? 0 : clock.spell_ms;
  let left = age;
  let charged = running;
  /* How long until the seat being charged changes. */
  let switchIn = Infinity;
  for (const [seat, ms] of clock.narration || []) {
    const spent = Math.min(left, ms);
    seats[seat] += spent;
    if (seat === running) spell += spent;
    left -= spent;
    if (spent < ms) {
      charged = seat;
      switchIn = ms - spent;
      break;
    }
  }
  if (left > 0 && running !== null) {
    seats[running] += left;
    spell += left;
  }
  return {
    elapsed: clock.elapsed_ms + (clock.counting ? age : 0),
    seats,
    spell,
    running,
    charged,
    counting: clock.counting,
    known: clock.known,
    switchIn,
  };
}

/* h:mm:ss, or m:ss under an hour: digits only, in either language. */
function formatClock(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const two = (value) => String(value).padStart(2, "0");
  return hours ? `${hours}:${two(minutes)}:${two(seconds)}` : `${minutes}:${two(seconds)}`;
}

/* `clock` is a reading or the summary's clock: both say whether it is known. */
function clockTitle(text, clock) {
  return clock && !clock.known ? `${text} · ${t("clock.since_load")}` : text;
}

/* A seat panel's total (renderSeats): its own span in the pieces row, not
   a .stat (the stat floats and the compact-row checks read those). */
function seatClockNode(seat) {
  const node = document.createElement("span");
  node.className = "seat-clock";
  node.dataset.clock = "seat";
  node.dataset.clockSeat = String(seat);
  node.title = clockTitle(t("clock.seat_title", { name: playerLabel(seat) }), state.summary.clock);
  return node;
}

/* The running seat's spell after the banner's prompt (renderBanner), never
   inside it. */
function appendSpellClock(info) {
  if (!clocksShown()) return;
  const reading = clockReading();
  const prompt = info.querySelector(":scope > .prompt");
  if (!reading || reading.running === null || !prompt) return;
  const node = document.createElement("span");
  node.className = "clock-spell";
  node.dataset.clock = "spell";
  node.title = t("clock.spell_title", { name: playerLabel(reading.running) });
  prompt.after(node);
}

/* The frozen totals of a finished game, under the standings table. */
function clockTotalsNode() {
  if (!clocksShown()) return null;
  const reading = clockReading();
  if (!reading) return null;
  const line = document.createElement("p");
  line.className = "clock-totals muted";
  line.title = clockTitle(t("clock.game_title"), reading);
  const parts = [t("clock.totals_game", { time: formatClock(reading.elapsed) })];
  reading.seats.forEach((ms, seat) => {
    parts.push(t("clock.totals_seat", { name: playerLabel(seat), time: formatClock(ms) }));
  });
  line.textContent = parts.join(" · ");
  return line;
}

function writeClockText(node, text) {
  if (node.textContent !== text) node.textContent = text;
}

/* Write every clock on screen, then wait for the next second that changes
   one of them. Called at the end of render() and renderSeats(), by its own
   timer, and when the tab comes back into view. */
function paintClocks() {
  clearTimeout(playClock.timer);
  playClock.timer = 0;
  const header = el("game-clock");
  const reading = clocksShown() ? clockReading() : null;
  if (!reading) {
    header.hidden = true;
    for (const node of document.querySelectorAll("[data-clock]:not(#game-clock)")) {
      node.hidden = true;
    }
    return;
  }
  header.hidden = false;
  const headerTitle = clockTitle(t("clock.game_title"), reading);
  if (header.title !== headerTitle) header.title = headerTitle;
  writeClockText(header, formatClock(reading.elapsed));
  for (const node of document.querySelectorAll("[data-clock='seat']")) {
    const seat = Number(node.dataset.clockSeat);
    node.hidden = false;
    writeClockText(node, formatClock(reading.seats[seat] || 0));
    node.classList.toggle("running", seat === reading.charged);
  }
  for (const node of document.querySelectorAll("[data-clock='spell']")) {
    node.hidden = false;
    writeClockText(node, formatClock(reading.spell));
  }
  scheduleClockTick(reading);
}

function scheduleClockTick(reading) {
  if (document.hidden || clockStalled()) return;
  const untilNext = (ms) => 1000 - (Math.floor(ms) % 1000);
  const waits = [reading.switchIn];
  if (reading.counting) waits.push(untilNext(reading.elapsed));
  if (reading.charged !== null) waits.push(untilNext(reading.seats[reading.charged]));
  if (reading.running !== null && reading.charged === reading.running) {
    waits.push(untilNext(reading.spell));
  }
  const wait = Math.min(...waits);
  if (!Number.isFinite(wait)) return;
  /* A few milliseconds past the boundary, so the next paint lands on it. */
  playClock.timer = setTimeout(paintClocks, Math.max(20, Math.ceil(wait) + 5));
}

/* Whether the page's own clock stood still while the wall clock went on
   (the machine slept); if so, a fresh snapshot is asked for once. */
function clockStalled() {
  const anchor = playClock.anchor;
  if (!anchor) return false;
  const lag = (clockWallNow() - anchor.wall) - (clockNow() - anchor.at);
  if (lag <= CLOCK_STALL_MS) return false;
  if (!playClock.stallAsked) {
    playClock.stallAsked = true;
    refresh(null, { foreign: true }).catch((error) => {
      /* Still unreachable (the network is coming back too): ask again. */
      playClock.stallAsked = false;
      clearTimeout(playClock.timer);
      playClock.timer = setTimeout(paintClocks, CLOCK_RETRY_MS);
      showRefreshError(error);
    });
  }
  return true;
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) paintClocks();
});
