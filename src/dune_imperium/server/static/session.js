"use strict";

/* ---------- my turn ---------- */

let myTurnBefore = null;

function isMyTurn(summary) {
  if (!summary || summary.finished) return false;
  const mine = mySeats();
  if (typeof summary.confirmation === "number") {
    return mine.includes(summary.confirmation);
  }
  return Boolean(summary.decision) && mine.includes(summary.decision.owner);
}

/* On a remote server a player waits for the others with the tab in the
   background: the title says when the wait is over, and a short tone marks
   the moment. (Notifications need a secure context, which a Tailscale
   address over plain HTTP is not.) */
function noticeTurn() {
  if (!isRemote()) return;
  const mine = isMyTurn(state.summary);
  document.title = mine ? t("session.my_turn_title", { title: baseTitle() }) : baseTitle();
  if (mine && myTurnBefore === false) turnTone();
  myTurnBefore = mine;
}

function turnTone() {
  try {
    const Context = window.AudioContext || window.webkitAudioContext;
    const context = new Context();
    const tone = context.createOscillator();
    const gain = context.createGain();
    tone.frequency.value = 880;
    gain.gain.value = 0.08;
    tone.connect(gain);
    gain.connect(context.destination);
    tone.start();
    tone.stop(context.currentTime + 0.18);
    tone.onended = () => context.close();
  } catch (error) {
    /* no audio: the title still tells */
  }
}

function note(text) {
  const target = el("game-note");
  target.textContent = text;
  target.hidden = false;
  window.clearTimeout(noteTimer);
  noteTimer = window.setTimeout(() => {
    target.hidden = true;
  }, 4000);
}

async function saveGame() {
  if (!state.gameId) return;
  const name = window.prompt(t("session.save_name_prompt"), "");
  if (name === null) return;
  try {
    const metadata = await api(`/games/${state.gameId}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name || null }),
    });
    note(t("session.saved", { name: metadata.name || metadata.save_id.slice(0, 8) }));
    if (hostSaves.gameId === state.gameId) loadHostSaves().catch(() => {});
  } catch (error) {
    note(t("session.save_failed", { message: error.message }));
  }
}

/* The seat the table is shown from, among the seats this browser plays:
   the one that must confirm its turn end, else the one that owns the
   decision, else the seat already on screen. On an open server that is
   every human seat, so one screen follows the game around the table. */
function pickViewSeat(summary, mine) {
  if (!mine.length) return null;
  if (typeof summary.confirmation === "number") {
    /* The seat whose turn just ended still holds the table until it
       confirms the hand-over (or takes its steps back). */
    if (mine.includes(summary.confirmation)) return summary.confirmation;
  } else if (summary.decision && mine.includes(summary.decision.owner)) {
    return summary.decision.owner;
  }
  return mine.includes(state.viewSeat) ? state.viewSeat : mine[0];
}

function snapshotPath(seat) {
  const params = new URLSearchParams();
  if (seat !== null) {
    params.set("seat", String(seat));
    /* Ask only for the entries this seat's log is missing. The server
       sends the whole log again when the epoch no longer names it: an undo
       re-flags earlier entries and the end of the game lifts redaction. */
    const known = state.log;
    if (known && known.seat === seat) {
      params.set("log_after", String(known.count));
      params.set("log_epoch", known.epoch);
    }
  }
  const query = params.toString();
  return `/games/${state.gameId}/snapshot${query ? `?${query}` : ""}`;
}

/* Returns null when the tail does not continue the entries held here (it
   always does while the server honours the cursor it was sent). */
function mergeLog(known, tail) {
  let entries = tail.entries;
  if (tail.from > 0) {
    if (
      !known ||
      known.seat !== tail.seat ||
      known.entries.length !== tail.from
    ) {
      return null;
    }
    entries = known.entries.concat(tail.entries);
  }
  return { seat: tail.seat, epoch: tail.epoch, count: tail.count, entries };
}

/* Refreshes never overlap: one that arrives while another runs makes the
   running one go round once more, and every caller gets the promise of
   the state being current. */
let refreshFlight = null;
let refreshAgain = false;
let refreshHint = null;
/* A seat to ask for first, when the caller knows what state.me does not
   yet: the seat it has just claimed, or `null` after giving one up. */
let refreshSeat;
/* A pass is foreign when only the doorbell asked for it: the player did
   nothing, so it must not take their popover or scroll position away. */
let refreshForeign = false;
let refreshQueuedForeign = true;

/* One refresh is one request (M14 slice 2): the snapshot carries the
   summary, the seat's view, its legal actions and the log tail, all read
   from one state. Which seat to ask for depends on the summary, so a
   summary already in hand (a POST's response) picks it; otherwise the seat
   on screen is asked for, and asked again in the rare case that the answer
   hands the table to another seat. */
async function loadSnapshot(hint, first) {
  const gameId = state.gameId;
  if (!gameId) return;
  let seat = state.viewSeat;
  if (first !== undefined) seat = first;
  else if (hint) seat = pickViewSeat(hint, mySeats());
  for (let attempt = 0; ; attempt += 1) {
    let snapshot;
    try {
      snapshot = await api(snapshotPath(seat));
    } catch (error) {
      if (error.status !== 403 || seat === null || attempt >= 3) throw error;
      /* The seat is no longer this browser's (the host released it): a
         snapshot without a seat says which seats still are. */
      seat = null;
      continue;
    }
    if (state.gameId !== gameId) return;
    /* The seats to pick from are the ones this very answer names. */
    const wanted = pickViewSeat(snapshot.summary, snapshot.you.seats);
    if (wanted === seat || attempt >= 3) {
      adoptSnapshot(snapshot, seat);
      return;
    }
    seat = wanted;
  }
}

/* The one place where the page learns the game's state and who it is at the
   table. Snapshots are asked for one after another (refresh), so each one
   adopted was read after the one before it; a request made outside that
   line could answer late and put the page back in time, after the last
   doorbell, where nothing would correct it. */
function adoptSnapshot(snapshot, seat) {
  const held = mySeats().length > 0;
  state.summary = snapshot.summary;
  state.me = snapshot.you;
  state.viewSeat = seat;
  if (held && !mySeats().length && isRemote()) {
    noticeTurn();
    seatLost();
    return;
  }
  /* Review mode draws its own timeline and states (reviewGoto); a refresh
     arriving meanwhile must not put the live table back under it. */
  if (!state.review) {
    state.view = snapshot.view || null;
    state.actions = snapshot.actions || null;
    state.log = snapshot.log ? mergeLog(state.log, snapshot.log) : null;
    if (snapshot.log && !state.log) refreshAgain = true;
  }
  noticeTurn();
  if (!el("lobby-screen").hidden) renderLobby();
  render({ foreign: refreshForeign });
  announceTurn(state.summary);
}

function refresh(summary, options) {
  const foreign = Boolean(options && options.foreign);
  if (summary) refreshHint = summary;
  if (options && options.seat !== undefined) refreshSeat = options.seat;
  if (refreshFlight) {
    refreshAgain = true;
    refreshQueuedForeign = refreshQueuedForeign && foreign;
    return refreshFlight;
  }
  refreshForeign = foreign;
  refreshFlight = (async () => {
    try {
      do {
        refreshAgain = false;
        const hint = refreshHint;
        const first = refreshSeat;
        refreshHint = null;
        refreshSeat = undefined;
        await loadSnapshot(hint, first);
        refreshForeign = refreshQueuedForeign;
        refreshQueuedForeign = true;
      } while (refreshAgain);
    } finally {
      refreshFlight = null;
    }
  })();
  return refreshFlight;
}

/* ---------- doorbell (M14 slice 3) ---------- */

/* The server rings when the game changes: a Server-Sent Events stream of
   public fields that says *that* something changed; what changed is then
   fetched through refresh(). Where the stream does not get through (a
   proxy that buffers or refuses SSE), the same check runs on a poll of
   the summary instead. */
const DOORBELL_GREETING_MS = 5000;
const DOORBELL_MAX_ERRORS = 3;
const DOORBELL_POLL_MS = 2000;

let doorbell = null;

function openDoorbell() {
  closeDoorbell();
  const gameId = state.gameId;
  if (!gameId) return;
  const bell = { gameId, source: null, greetTimer: 0, pollTimer: 0, errors: 0 };
  doorbell = bell;
  if (typeof EventSource === "undefined") {
    startDoorbellPolling(bell);
    return;
  }
  const source = new EventSource(`/games/${gameId}/events`);
  bell.source = source;
  const heard = (event) => {
    if (doorbell !== bell) return;
    bell.errors = 0;
    showConnectionLost(false);
    window.clearTimeout(bell.greetTimer);
    onDoorbell(JSON.parse(event.data));
  };
  source.addEventListener("hello", heard);
  source.addEventListener("change", heard);
  source.addEventListener("closed", () => {
    if (doorbell !== bell) return;
    closeDoorbell();
    onGameGone("deleted");
  });
  /* EventSource reconnects by itself; only a stream that keeps failing,
     or never greets, is given up for polling. */
  source.onerror = () => {
    if (doorbell !== bell) return;
    bell.errors += 1;
    if (bell.errors >= DOORBELL_MAX_ERRORS) startDoorbellPolling(bell);
  };
  bell.greetTimer = window.setTimeout(() => {
    if (doorbell === bell) startDoorbellPolling(bell);
  }, DOORBELL_GREETING_MS);
}

function startDoorbellPolling(bell) {
  if (bell.pollTimer) return;
  window.clearTimeout(bell.greetTimer);
  if (bell.source) {
    bell.source.close();
    bell.source = null;
  }
  bell.pollTimer = window.setInterval(async () => {
    if (doorbell !== bell || state.busy) return;
    try {
      /* A summary has every field a doorbell payload is compared by. */
      const summary = await api(`/games/${bell.gameId}`);
      if (doorbell !== bell) return;
      showConnectionLost(false);
      onDoorbell(summary);
    } catch (error) {
      if (doorbell !== bell) return;
      if (error.status === 404) {
        /* The server answers and does not know the game: deleted, or
           the server came back from a restart without it. */
        closeDoorbell();
        onGameGone("missing");
      } else if (error.status === undefined) {
        /* No answer at all: the server is down or unreachable. The
           poll goes on; a restarted server ends it with the 404. */
        showConnectionLost(true);
      }
    }
  }, DOORBELL_POLL_MS);
}

function showConnectionLost(lost) {
  el("connection-note").hidden = !lost;
}

function closeDoorbell() {
  const bell = doorbell;
  doorbell = null;
  showConnectionLost(false);
  if (!bell) return;
  window.clearTimeout(bell.greetTimer);
  window.clearInterval(bell.pollTimer);
  if (bell.source) bell.source.close();
}

/* A stale picture is refreshed; a change to `players` alone (a name, a
   claim, who is online) is public as it stands and needs no request. */
function onDoorbell(bell) {
  const summary = state.summary;
  if (!summary || state.busy) return;
  if (
    bell.revision !== summary.revision ||
    bell.undo_count !== summary.undo_count ||
    bell.log_count !== summary.log_count ||
    bell.confirmation !== summary.confirmation ||
    bell.finished !== summary.finished
  ) {
    refresh(null, { foreign: true }).catch(showRefreshError);
  } else if (
    bell.players &&
    JSON.stringify(bell.players) !== JSON.stringify(summary.players)
  ) {
    const mine = mySeatChanged(summary.players, bell.players);
    summary.players = bell.players;
    if (mine) {
      /* A release by the host takes a seat from under this browser without
         any game step, and the payload cannot say whose claim it shows:
         ask who this browser still is, in line with every other refresh.
         A seat nobody holds is certainly not held here, so the seat on
         screen is not asked for once it shows as free. */
      const shown = bell.players[state.viewSeat];
      const options = { foreign: true };
      if (!shown || !shown.claimed) options.seat = null;
      refresh(null, options).catch(showRefreshError);
    } else if (refreshFlight) {
      /* A snapshot already on its way may have been read before this bell
         rang (a page entering a game opens its stream and asks for its
         snapshot at once) and would put the older list back when it lands,
         with no later bell to correct it: one more pass after it. */
      refresh(null, { foreign: true }).catch(showRefreshError);
    } else if (!el("lobby-screen").hidden) {
      renderLobby();
    } else {
      render({ foreign: true });
    }
  }
}

/* Whether a seat this browser holds on a remote server changed its claim or
   its name. Presence alone (somebody's tab opened or closed) is public as
   the payload has it and needs no request. */
function mySeatChanged(before, after) {
  if (!isRemote()) return false;
  return mySeats().some((seat) => {
    const was = before[seat];
    const now = after[seat];
    return !was || !now || was.claimed !== now.claimed || was.name !== now.name;
  });
}

function onGameGone(reason) {
  /* Nothing to come back to: do not offer it on the landing page. */
  if (storageGet("dune.lastGame") === state.gameId) storageRemove("dune.lastGame");
  leaveGame(
    reason === "deleted"
      ? t("session.game_deleted")
      : t("session.game_missing")
  );
}

async function applyAction(index) {
  if (state.busy) return;
  state.busy = true;
  state.pick = null;
  render();
  try {
    el("game-error").hidden = true;
    const summary = await api(`/games/${state.gameId}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat: state.viewSeat,
        revision: state.summary.revision,
        undo_count: state.summary.undo_count,
        index,
      }),
    });
    state.busy = false;
    await refresh(summary);
  } catch (error) {
    state.busy = false;
    /* 409: the table moved on. 403: the seat is no longer this browser's;
       the refresh finds that out and lands in the seat picker. */
    if (error.status === 409 || error.status === 403) {
      await refresh();
      return;
    }
    el("game-error").textContent = t("session.action_failed", { message: error.message });
    el("game-error").hidden = false;
    render();
  }
}

/* Hand the turn over after the seat's still-undoable steps: only now do
   the chance stream and the other seats advance. */
async function confirmTurn() {
  if (state.busy) return;
  state.busy = true;
  render();
  try {
    el("game-error").hidden = true;
    const summary = await api(`/games/${state.gameId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat: state.viewSeat,
        revision: state.summary.revision,
        undo_count: state.summary.undo_count,
      }),
    });
    state.busy = false;
    await refresh(summary);
  } catch (error) {
    state.busy = false;
    /* 409: the table moved on. 403: the seat is no longer this browser's;
       the refresh finds that out and lands in the seat picker. */
    if (error.status === 409 || error.status === 403) {
      await refresh();
      return;
    }
    el("game-error").textContent = t("session.turn_end_failed", { message: error.message });
    el("game-error").hidden = false;
    render();
  }
}

/* Take back `steps` of `seat`'s own latest steps (M11 slice 6). */
async function submitUndo(seat, steps) {
  if (state.busy) return;
  state.busy = true;
  render();
  try {
    el("game-error").hidden = true;
    const summary = await api(`/games/${state.gameId}/undo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        seat,
        revision: state.summary.revision,
        undo_count: state.summary.undo_count,
        steps,
      }),
    });
    state.busy = false;
    await refresh(summary);
  } catch (error) {
    state.busy = false;
    /* 409: the table moved on. 403: the seat is no longer this browser's;
       the refresh finds that out and lands in the seat picker. */
    if (error.status === 409 || error.status === 403) {
      await refresh();
      return;
    }
    el("game-error").textContent = t("session.undo_failed", { message: error.message });
    el("game-error").hidden = false;
    render();
  }
}
