"use strict";

/* The host's link is `#admin=<key>`: trade the key for an HttpOnly cookie
   and take it out of the address bar at once. */
async function adoptAdminLink() {
  const key = hashParams().get("admin");
  if (!key) return null;
  setRoomHash(null);
  try {
    await api("/auth/admin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    return null;
  } catch (error) {
    return `관리자 링크가 맞지 않습니다 (${error.message})`;
  }
}

async function init() {
  loadCollapsedStrips();
  state.catalog = await api("/catalog");
  const adminError = await adoptAdminLink();
  state.server = await api("/whoami");
  /* The host of a remote game plays too and must not know the seed. */
  el("opt-seed-row").hidden = isRemote();
  buildSeatSelects();
  document.addEventListener("click", (event) => {
    const pop = el("card-popover");
    if (!pop.hidden && !pop.contains(event.target)) closePopover();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (state.pick) clearPick();
      else closePopover();
      return;
    }
    /* `c` folds the shared card columns away and back, so the board can have
       the room when you are not shopping. Not while typing a name or a seed,
       and not when the key is part of a browser shortcut. */
    const target = event.target;
    const typing =
      target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
    if (typing || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "c" || event.key === "C") {
      if (el("game-screen").hidden) return;
      event.preventDefault();
      toggleAllStrips();
    }
  });
  el("setup-form").addEventListener("submit", createGame);
  el("leave-game").addEventListener("click", () => leaveGame());
  el("open-lobby").addEventListener("click", () => showLobby());
  el("lobby-enter").addEventListener("click", () => enterTable(state.summary));
  el("host-panel").addEventListener("toggle", () => {
    /* The host opened the panel: show what is on disk for this game. */
    if (el("host-panel").open) loadHostSaves().catch(() => {});
  });
  el("landing-resume-button").addEventListener("click", () => {
    const last = roomId(storageGet("dune.lastGame"));
    if (last) openGame(last).catch(() => {});
  });
  window.addEventListener("hashchange", () => {
    const wanted = roomFromHash();
    if (wanted && wanted !== state.gameId) openGame(wanted).catch(() => {});
  });
  el("save-game").addEventListener("click", () => {
    saveGame().catch(() => {});
  });
  el("review-exit").addEventListener("click", exitReview);
  el("review-first").addEventListener("click", () => reviewSeek(0));
  el("review-last").addEventListener("click", () => {
    if (state.review) reviewSeek(state.review.meta.step_count);
  });
  el("review-prev").addEventListener("click", () =>
    reviewStep(() => reviewGoto(state.review.cursor - 1).catch(() => {}))
  );
  el("review-next").addEventListener("click", () =>
    reviewStep(() => reviewGoto(state.review.cursor + 1).catch(() => {}))
  );
  el("review-prev-own").addEventListener("click", () =>
    reviewStep(() => reviewJumpOwn(-1))
  );
  el("review-next-own").addEventListener("click", () =>
    reviewStep(() => reviewJumpOwn(1))
  );
  el("review-slider").addEventListener("change", (event) =>
    reviewSeek(Number(event.target.value))
  );
  el("review-seat").addEventListener("change", (event) => {
    if (!state.review) return;
    /* Another seat's eyes on the same position; playback carries on. */
    const play = playback.playing;
    stopPlayback();
    enterReview(Number(event.target.value), {
      cursor: state.review.cursor,
      play,
    }).catch(() => {});
  });
  el("review-play").addEventListener("click", () => {
    if (playback.playing) stopPlayback();
    else startPlayback(0);
  });
  el("review-unit").addEventListener("change", (event) => {
    playback.unit = event.target.value === "step" ? "step" : "turn";
  });
  el("review-interval").addEventListener("change", (event) => {
    playback.intervalMs = Number(event.target.value) || 1000;
    if (playback.playing) schedulePlayback(playback.intervalMs);
  });
  const room = roomFromHash();
  if (room) await openGame(room);
  else await showHome(adminError);
}

init().catch((error) => {
  el("setup-error").textContent = `초기화 실패 (${error.message})`;
  el("setup-error").hidden = false;
});
