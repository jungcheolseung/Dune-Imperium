"use strict";

/* ---------- help and announcements ---------- */

/* The live region: what a screen reader should hear without looking — whose
   turn it now is, and how the game ended. Errors have role="alert" of their
   own (index.html). Clearing first makes the same sentence read again. */
function announce(text) {
  const region = el("announcer");
  region.textContent = "";
  window.setTimeout(() => {
    region.textContent = text;
  }, 50);
}

/* Announce each change of the seat to act, and the end of the game, once.
   A review walks a finished record, so it announces nothing. */
let announcedTurn;

/* The seats this screen speaks for: the claimed ones on a remote server, the
   one on screen on an open server (pickViewSeat moves it to whoever acts). */
function isMine(seat) {
  return isRemote() ? mySeats().includes(seat) : seat === state.viewSeat;
}

function announceTurn(summary) {
  if (!summary || state.review) return;
  let key;
  let text;
  if (summary.finished) {
    const first = (summary.standings || []).find((entry) => entry.rank === 1);
    key = "finished";
    text = first ? `게임 종료 — ${playerLabel(first.player)} 승리` : "게임 종료";
  } else if (typeof summary.confirmation === "number") {
    /* A seat's turn has ended but can still be taken back: decision.owner
       already names the NEXT seat, yet nobody moves until this one confirms
       (renderBanner). Announcing the next seat here told it to act early and
       then swallowed the real hand-over, whose key was the same. */
    const seat = summary.confirmation;
    key = `confirm:${seat}`;
    text = isMine(seat)
      ? `${playerLabel(seat)} — 행동을 마쳤습니다. 턴 종료를 확정하세요.`
      : `${playerLabel(seat)}의 턴 종료 확정을 기다리는 중`;
  } else if (summary.decision) {
    const owner = summary.decision.owner;
    key = `seat:${owner}`;
    /* One screen can hold several human seats (an open server), so even
       "your turn" says which seat. */
    text = isMine(owner)
      ? `${playerLabel(owner)} — 당신 차례입니다: ${summary.decision.prompt}`
      : `${playerLabel(owner)} 차례`;
  } else {
    return;
  }
  if (key === announcedTurn) return;
  announcedTurn = key;
  announce(text);
}

/* ---------- the help panel ---------- */

/* What the seat panel draws that no rulebook icon explains: how to draw
   the mark, and what it means (a phrase template). */
const HELP_SEAT_MARKS = [
  [() => commanderChip(2, "{garrison}"), "{commander} — {garrison}·{conflict}·{supply}에 있는 수"],
  [() => "1st", "{first_player}"],
  [
    () => {
      const mark = document.createElement("span");
      mark.append(phraseText("{conflict} "), icon("troop", phraseText("{troop}")), "3");
      return mark;
    },
    "{conflict}에 배치한 유닛",
  ],
];

const HELP_SHORTCUTS = [
  ["c", "공용 카드 열을 모두 접기 / 펴기"],
  ["s", "모든 좌석의 자세히 펴기 / 접기"],
  ["Esc", "고르던 것 취소 · 열린 창 닫기"],
  ["?", "이 도움말 열기"],
];

const HELP_TURN = [
  "{agent_turn}: ① 손패에서 빛나는 카드 → ② 빛나는 칸 → ③ 남은 선택. 칸을 먼저 눌러도 되고, Esc로 취소합니다.",
  "되돌릴 수 있는 동안은 턴이 넘어가지 않습니다. 끝나면 \"턴 종료 확정\"을 누르세요.",
  "되돌리기는 자기 연속 행동만 됩니다. 무작위 결과나 숨겨진 정보가 공개된 뒤로는 되돌릴 수 없습니다.",
  "{reveal_turn}: 카드를 공개하고, 남은 {persuasion}으로 빛나는 카드를 산 뒤 끝냅니다.",
];

let helpOpener = null;

function helpSection(parent, title) {
  const heading = document.createElement("h3");
  heading.textContent = title;
  const body = document.createElement("div");
  body.className = "help-grid";
  parent.append(heading, body);
  return body;
}

function helpRow(grid, mark, text) {
  const key = document.createElement("span");
  key.className = "help-mark";
  if (typeof mark === "string") key.textContent = mark;
  else key.appendChild(mark);
  const what = document.createElement("span");
  what.append(text);
  grid.append(key, what);
}

function openHelp() {
  const panel = el("help");
  if (!panel.hidden) return;
  helpOpener = document.activeElement;
  const body = el("help-body");
  body.textContent = "";

  const heading = document.createElement("h2");
  heading.id = "help-title";
  heading.textContent = "도움말";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "help-close";
  close.textContent = "닫기";
  close.addEventListener("click", closeHelp);
  heading.appendChild(close);
  body.appendChild(heading);

  /* Every rule term that has a printed icon, from the one table the rest
     of the UI reads, so the legend cannot drift from what is drawn. */
  const icons = helpSection(body, "아이콘");
  for (const [name, term] of Object.entries(TERMS)) {
    if (!term.icon || !iconUrl(term.icon)) continue;
    const label = document.createElement("span");
    label.append(term[TERM_LANGUAGE] || term.en);
    if (TERM_LANGUAGE !== "en") {
      const english = document.createElement("span");
      english.className = "muted";
      english.textContent = ` ${term.en}`;
      label.appendChild(english);
    }
    const row = icon(term.icon, term[TERM_LANGUAGE] || term.en);
    row.dataset.term = name;
    helpRow(icons, row, label);
  }

  const marks = helpSection(body, "좌석 패널");
  for (const [draw, text] of HELP_SEAT_MARKS) helpRow(marks, draw(), phraseText(text));

  const keys = helpSection(body, "단축키 (한글 입력 상태에서도 됩니다)");
  for (const [key, text] of HELP_SHORTCUTS) {
    const kbd = document.createElement("kbd");
    kbd.textContent = key;
    helpRow(keys, kbd, text);
  }

  const turn = document.createElement("h3");
  turn.textContent = "한 턴 진행";
  const list = document.createElement("ul");
  list.className = "help-turn";
  for (const line of HELP_TURN) {
    const item = document.createElement("li");
    item.textContent = phraseText(line);
    list.appendChild(item);
  }
  body.append(turn, list);

  panel.hidden = false;
  close.focus();
}

function closeHelp() {
  const panel = el("help");
  if (panel.hidden) return;
  panel.hidden = true;
  el("help-body").textContent = "";
  /* Back where the reader was, if that is still on the page. */
  if (helpOpener && document.contains(helpOpener)) helpOpener.focus();
  helpOpener = null;
}
