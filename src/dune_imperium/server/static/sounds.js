"use strict";

/* ---------- sounds ---------- */

/* Every sound is drawn by the browser (Web Audio oscillators through a
   gain envelope): no sound files, so nothing of anyone's app reaches the
   assets (user, 2026-10-11: "소리 파일이 애셋에 들어가는 좀 그렇다").

   Each moment has a sound of its own ("다 동일한 음으로 하고 싶진 않은데",
   the same day), picked from a page of candidates:
   - decision: a decision comes to this screen's seat on a remote table
     (session.js noticeTurn): two soft notes rising (the user's pick, A6);
   - round: a Round starts (its Conflict revealed): a clear bell (A3);
   - combat: the combat phase starts: a low gong (A5);
   - scouts: an Arrakeen Scouts item is revealed: three quick marimba
     notes rising (A4);
   - idle: a seat this screen plays has left its decision untouched for
     15 seconds (session.js watchIdle, user request 2026-10-19): two short
     beeps, the one square-wave sound, so it reads as a warning.
   The phase sounds go with their banners (effects.js drawPhaseBanner), so
   they keep the AI pace and never sound for a moment that happened before
   the page loaded. A review plays none.

   A browser plays sound only after the page had a click or a key; until
   then a call is silently dropped, as is any failure: the banner and the
   tab title still tell. */
let soundContext = null;

function soundOutput() {
  if (!soundContext) {
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return null;
    soundContext = new Context();
  }
  if (soundContext.state === "suspended") soundContext.resume().catch(() => {});
  return soundContext;
}

/* One voice: an oscillator rising to `peak` over `attack`, holding for
   `hold`, then fading out over `decay` (seconds after now + `start`). */
function soundVoice(output, { type = "sine", freq, start = 0, attack = 0.005, hold = 0, decay, peak }) {
  const begin = output.currentTime + start;
  const tone = output.createOscillator();
  const gain = output.createGain();
  tone.type = type;
  tone.frequency.value = freq;
  gain.gain.setValueAtTime(0, begin);
  gain.gain.linearRampToValueAtTime(peak, begin + attack);
  gain.gain.setValueAtTime(peak, begin + attack + hold);
  gain.gain.exponentialRampToValueAtTime(0.0001, begin + attack + hold + decay);
  tone.connect(gain);
  gain.connect(output.destination);
  tone.start(begin);
  tone.stop(begin + attack + hold + decay + 0.05);
}

const SOUNDS = {
  decision: [
    { freq: 587.3, attack: 0.02, decay: 0.35, peak: 0.1 },
    { freq: 880, start: 0.15, attack: 0.02, decay: 0.5, peak: 0.1 },
  ],
  round: [
    { freq: 1046.5, decay: 1.4, peak: 0.1 },
    { freq: 2093, decay: 0.8, peak: 0.04 },
    { freq: 3135.9, decay: 0.4, peak: 0.02 },
  ],
  combat: [
    { freq: 110, attack: 0.01, decay: 1.8, peak: 0.25 },
    { freq: 220, attack: 0.01, decay: 1.2, peak: 0.08 },
    { freq: 331, attack: 0.01, decay: 0.6, peak: 0.04 },
  ],
  scouts: [523.3, 659.3, 784].map((freq, index) => ({
    type: "triangle", freq, start: index * 0.09, decay: 0.25, peak: 0.16,
  })),
  idle: [0, 0.22].map((start) => ({
    type: "square", freq: 987.8, start, hold: 0.08, decay: 0.06, peak: 0.05,
  })),
};

/* The banner cues (effects.js) that have a sound. */
const PHASE_SOUNDS = { round: "round", combat: "combat", scouts: "scouts" };

function playSound(name) {
  const voices = SOUNDS[name];
  if (!voices) return;
  try {
    const output = soundOutput();
    if (!output) return;
    for (const voice of voices) soundVoice(output, voice);
  } catch (error) {
    /* no audio: the screen still tells */
  }
}

/* A phase banner shown now (effects.js): its sound, outside a review. */
function playPhaseSound(cue) {
  if (state.review || !cue) return;
  const name = PHASE_SOUNDS[cue.type];
  if (name) playSound(name);
}
