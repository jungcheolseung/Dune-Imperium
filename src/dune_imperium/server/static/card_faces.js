/* The redrawn card faces (docs/own-pictures-plan.md stage 1).

   A card without a picture (the public build, or `--pictures own`) is drawn
   from what its printed face shows: the catalog entry's `face` holds each
   box's printed content in our notation ({icon}, {icon:N}, newlines, <i>,
   <b>; display/card_faces.py), the rest (name, cost, Faction, Agent icons,
   specimens, graft) is the entry's own data. Format "A" (user 2026-11-10):
   only what play needs, no art; the marks keep their printed shapes; every
   Imperium and Tleilaxu card has the same boxes, sized for the longest
   printed text, so nothing is ever shrunk. Sizes are fractions of the card
   (CSS container units), so one face serves the hand's 76 px card and the
   popover alike. */

const FACE_FACTION_COLORS = {
  emperor: "#55575c",
  spacing_guild: "#c8343f",
  bene_gesserit: "#8b5bb5",
  fremen: "#3a76c4",
};
/* Resources printed with their number inside the icon (our CSS shapes). */
const FACE_INSIDE = { persuasion: "pz", solari: "sol", spice: "spi" };
/* Pictures a face names that the action log draws, not the icon set. */
const FACE_LOG_PICTURES = new Set(["research", "tleilaxu"]);
/* Marks the faces draw from their own pieces (pictures/faces): combat's
   crossed swords, the Tech flip. */
const FACE_PIECES = { conflict: "combat", flip: "flip", mentat: "mentat" };
/* A contract's condition frame, by the space it shows (its colour). */
const CONTRACT_FRAME_TINT = {
  emperor: "#2c2c30", spacing_guild: "#3c1416", bene_gesserit: "#2e1d44", green: "#16301c",
  yellow: "#4a3a14", harvest: "#9a8a6a", arrakeen: "#8a7a62", heighliner: "#5a6470",
  research_station: "#6e5a3a", spice_must_flow: "#3a2410", spice_refinery: "#5a4220",
};
/* A contract tile's own colour, by its printed frame. */
const CONTRACT_TILE_COLOR = {
  spacing: "#8e2a2d", spacing2: "#8e2a2d", yellow: "#9a5a22", blue: "#3c3a72",
  green: "#2f6a3a", emperor: "#4a4a50", bene_gesserit: "#5c3a7e",
};
const FACE_ARROWS = new Set(["arrow_right", "arrow_down"]);
const SPECIMEN_CUBE = "/static/pictures/faces/specimen_cube.svg";
const AGENT_MARK_DIR = "/static/pictures/faces/";
/* Specimen cubes as print lays them, in cube widths (x) and heights (y). */
const SPECIMEN_LAYOUT = {
  1: [[0.5, 0.35]],
  2: [[0, 0], [0.62, 0.62]],
  3: [[0, 0], [1, 0], [0.5, 0.85]],
  4: [[0, 0], [1, 0.18], [0, 0.95], [1, 1.13]],
};

function faceEl(tag, className, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.append(...children);
  return node;
}

/* The box's printed text in the page's language, else its English. */
function faceText(entry, box) {
  const texts = entry.face && entry.face[box];
  if (!texts) return null;
  return (TERM_LANGUAGE === "ko" && texts.ko) || texts.en || "";
}

function faceWord(name) {
  const term = TERMS[name];
  return term ? term[TERM_LANGUAGE] || term.en : name.replace(/_/g, " ");
}

function faceIcon(name, count) {
  if (FACE_PIECES[name]) {
    const piece = document.createElement("img");
    piece.className = "cf-ic" + (name === "flip" ? " cf-flipic" : "");
    piece.src = `${AGENT_MARK_DIR}${FACE_PIECES[name]}.svg`;
    piece.alt = faceWord(name);
    piece.title = piece.alt;
    piece.draggable = false;
    return piece;
  }
  /* A board space's mark in printed text (Show of Strength's "this has
     {Landsraad} and {Spice Trade}", a contract's frame) is the mark alone,
     as the card's own Agent icons are: the grey plate is gone everywhere
     on the redrawn faces (user 2026-11-11). */
  const bare = name.match(/^agent_mark_([a-z_]+)$/) || name.match(/^agent_icon_(landsraad|city|spice_trade|spy)$/);
  if (bare) {
    const mark = document.createElement("img");
    mark.className = "cf-ic cf-mark";
    mark.src = `${AGENT_MARK_DIR}agent_mark_${bare[1]}.svg`;
    mark.alt = faceWord(`agent_icon_${bare[1]}`);
    mark.title = mark.alt;
    mark.draggable = false;
    return mark;
  }
  if (name === "foldspace") {
    /* The Foldspace card (Ilesa Ecaz's Guild Contacts): a red card, our CSS. */
    const card = faceEl("span", "cf-foldspace");
    card.title = faceWord(name);
    return card;
  }
  if (name === "spy_deep_cover" && iconUrl("spy")) {
    /* A Spy with Deep Cover prints a gold Spy behind a grey one. */
    const pair = faceEl("span", "cf-deepspy", faceIcon("spy"), faceIcon("spy"));
    pair.title = faceWord(name);
    return pair;
  }
  const faction = name.match(/^agent_icon_(emperor|spacing_guild|bene_gesserit|fremen)$/);
  if (faction) {
    /* In printed text a Faction's mark sits on a small dark badge (Influence
       and Alliance conditions, "on {Emperor}/{Fremen}"), not on the grey
       Agent plate of the card's icon column. */
    const badge = document.createElement("img");
    badge.className = "cf-ic cf-badge";
    badge.src = `${AGENT_MARK_DIR}faction_${faction[1]}.svg`;
    badge.alt = faceWord(name);
    badge.title = badge.alt;
    badge.draggable = false;
    return badge;
  }
  const marker = name.match(/^genetic_marker_(\d)$/);
  if (marker && !iconUrl(name)) {
    /* Genetic markers (Immortality): one or two red diamonds, our drawing. */
    const group = faceEl("span", "cf-dna");
    for (let k = 0; k < Number(marker[1]); k += 1) {
      const img = document.createElement("img");
      img.className = "cf-ic";
      img.src = `${AGENT_MARK_DIR}genetic_marker.svg`;
      img.alt = "";
      img.draggable = false;
      group.appendChild(img);
    }
    group.title = faceWord(name);
    return group;
  }
  if (count !== undefined && FACE_INSIDE[name]) {
    const shape = faceEl("span", `cf-res cf-${FACE_INSIDE[name]}`, faceEl("b", "", String(count)));
    shape.title = `${count} ${faceWord(name)}`;
    return shape;
  }
  const url = FACE_LOG_PICTURES.has(name)
    ? (state.catalog.log_icons || {})[name] || null
    : iconUrl(name);
  if (!url) {
    const word = faceEl("span", "cf-word", count !== undefined ? `${count} ${faceWord(name)}` : faceWord(name));
    return word;
  }
  const img = document.createElement("img");
  img.className = "cf-ic" + (FACE_ARROWS.has(name) ? " cf-arrow" : "") + (name === "arrow_down" ? " cf-down" : "");
  img.src = url;
  img.alt = faceWord(name);
  img.title = faceWord(name);
  img.draggable = false;
  return img;
}

/* "—OR—", "- AND -", "—또는—", "—그리고—" inside a line. */
const FACE_SEPARATOR = /\s*[-–—]\s*(OR|AND|또는|그리고)\s*[-–—]\s*/;
/* A condition print sets as a badge before its effects: Faction marks with
   "2 Influence" / "Alliance" (영향력 2 / 동맹), a genetic marker, Maker
   Hooks, an Agent icon, or "Fremen Bond" (프레멘의 유대감), then a colon. */
const FACE_CONDITION = new RegExp(
  "^\\s*((?:\\{(?:agent_icon_[a-z_]+|genetic_marker_\\d|maker_hooks|unload)\\}\\s*)+"
  /* 영향력, 동맹, 의 유대감 as escapes: the page's Korean lives in the text tables. */
  + "(?:\\d+\\s*Influence|\\uC601\\uD5A5\\uB825\\s*\\d+|Alliance|\\uB3D9\\uB9F9)?|[A-Z][a-z]+ Bond|\\S+\\uC758 \\uC720\\uB300\\uAC10)\\s*:\\s*(?=\\S)",
);

/* Printed content -> nodes: one `.cf-line` per printed line; a line of
   icons alone is a `big` line, drawn larger and centred as one group, as
   print does. A line with "—OR—" or "—AND—" inside it sets its two sides
   apart, each wrapping in its own column with the word between them, and
   the right side takes the lines that follow it (Stillsuit Manufacturer's
   "{water} —AND— {Fremen} Alliance: / Return this card…"), as print lays
   such a choice out (user 2026-11-11). A line that opens with a badge
   condition ("{Bene Gesserit} 2 Influence:") keeps the condition on one
   line at the left and wraps its effects in their own column beside it,
   never under the condition (user 2026-11-11); the column takes the lines
   that follow until the next condition or a blank line (In the Shadows'
   Influence icons under "Choose one:"). `plain` keeps a column's icons at
   the text's size. */
function faceRich(text, className = "", plain = false) {
  const box = faceEl("div", className);
  const sources = String(text).split("\n");
  for (let index = 0; index < sources.length; index += 1) {
    const source = faceSpaceMarks(sources[index]);
    /* Command (Bloodlines): print stacks "Command" over "(◆6+)" as one
       label, then the colon and the effect beside it, wrapping on its own
       ("Command / (6+): 3 Solari and trash this card."). */
    const command = sources[index + 1] && /^\s*\S+\s*$/.test(source)
      ? sources[index + 1].match(/^\s*\(\{persuasion:(\d+)\}\+\)\s*:\s*(.*)$/)
      : null;
    if (command) {
      const label = faceEl("span", "cf-condhead cf-cmdlabel",
        faceEl("span", "", source.trim()),
        faceEl("span", "cf-cmdcost", "(", faceIcon("persuasion", command[1]), "+)"));
      const row = faceEl("div", "cf-line cf-cond cf-command", label, faceEl("span", "cf-cmdcolon", ":"),
        faceRich(command[2], "cf-part"));
      box.appendChild(row);
      index += 1;
      continue;
    }
    /* Icons alone ("🧬 : 1 spice") never wrap: they stay one big row. */
    const worded = /[^\s:+]/.test(source.replace(/\{[a-z_0-9]+(?::\d+\+?)?\}|<\/?[bi]>/g, ""));
    const condition = worded ? source.match(FACE_CONDITION) : null;
    if (condition) {
      let end = index + 1;
      while (end < sources.length && sources[end].trim() && !FACE_CONDITION.test(sources[end])
        && !FACE_SEPARATOR.test(sources[end])) {
        end += 1;
      }
      const effects = [source.slice(condition[0].length), ...sources.slice(index + 1, end)].join("\n");
      const head = faceLine(`${condition[1].trim()}:`, true);
      head.classList.add("cf-condhead");
      const row = faceEl("div", "cf-line cf-cond", head, faceRich(effects, "cf-part", true));
      box.appendChild(row);
      index = end - 1;
      continue;
    }
    const split = source.match(FACE_SEPARATOR);
    const left = split ? source.slice(0, split.index) : "";
    const after = split ? source.slice(split.index + split[0].length) : "";
    if (split && left.trim() && !after.trim()) {
      /* "Discard a card —OR—" ending its line: print keeps the word after
         the first option and stacks the next one under it. */
      box.appendChild(faceLine(source, plain));
      continue;
    }
    /* A long sentence before the word reads as one paragraph (Princess
       Irulan's Signet Ring): no columns. */
    const leftWords = left.replace(/\{[a-z_0-9]+(?::\d+\+?)?\}/g, " ").split(/\s+/).filter((w) => /[^\s:+]/.test(w)).length;
    if (split && left.trim() && leftWords <= 4) {
      /* The right side takes the following lines when it continues on
         them (nothing yet, or words: "—AND— {Fremen} Alliance: / Return…");
         a right side of icons alone is whole, and what follows belongs
         to both (Possible Futures' "… get both.") below the row. */
      const rest = source.slice(split.index + split[0].length);
      const iconsOnly = rest.trim() && !/[^\s:+]/.test(rest.replace(/\{[a-z_0-9]+(?::\d+\+?)?\}/g, ""));
      const right = (iconsOnly ? rest : [rest, ...sources.slice(index + 1)].join("\n")).replace(/^\n+/, "");
      const row = faceEl("div", "cf-line cf-split");
      row.append(faceRich(left, "cf-part"), faceEl("span", "cf-sep", `—${split[1]}—`), faceRich(right, "cf-part"));
      box.appendChild(row);
      if (iconsOnly) continue;
      break;
    }
    /* "cost → reward" with words in it: the cost in its column, the arrow,
       the reward in its own column, each wrapping on its own, so a long
       reward never runs back under the arrow (user 2026-11-11). A reward
       that ends in ":" ("→ Choose one:") takes the lines after it. */
    const arrow = worded ? source.indexOf("{arrow_right}") : -1;
    const lead = arrow > 0 ? source.slice(0, arrow).match(/^(.*?:)\s+(\S[\s\S]*)$/) : null;
    if (lead && lead[1].replace(/<\/?[bi]>|\{[^}]+\}/g, " ").trim().split(/\s+/).length >= 4) {
      /* "If you have completed four or more contracts: Trash this card →":
         the condition on its line, the cost → reward row under it. */
      box.appendChild(faceLine(lead[1], plain));
      sources[index] = lead[2] + source.slice(arrow);
      index -= 1;
      continue;
    }
    if (arrow > 0 && source.slice(0, arrow).trim()) {
      let reward = source.slice(arrow + "{arrow_right}".length);
      let end = index + 1;
      if (/:\s*$/.test(reward)) {
        while (end < sources.length && sources[end].trim() && !FACE_CONDITION.test(sources[end])
          && !FACE_SEPARATOR.test(sources[end])) {
          end += 1;
        }
        reward = [reward, ...sources.slice(index + 1, end)].join("\n");
      }
      if (reward.trim()) {
        const row = faceEl("div", "cf-line cf-arrowrow",
          faceRich(source.slice(0, arrow), "cf-part cf-cost-side", true),
          faceIcon("arrow_right"),
          faceRich(reward.trim(), "cf-part cf-reward-side", true));
        box.appendChild(row);
        index = end - 1;
        continue;
      }
    }
    box.appendChild(faceLine(source, plain));
  }
  return box;
}

/* One printed line: its words, icons, <b> and <i>; `plain` never makes it
   a big icon row. */
function faceLine(source, plain = false) {
  const line = faceEl("div", "cf-line");
  const stack = [line];
  let words = false;
  let pictures = false;
  for (const token of source.split(/(\{[a-z_0-9]+(?::\d+\+?)?\}|<\/?[bi]>)/)) {
    if (!token) continue;
    const top = stack[stack.length - 1];
    const tag = token.match(/^\{([a-z_0-9]+)(?::(\d+\+?))?\}$/);
    if (tag) {
      /* A count is printed as is: "3", or "3+" (a Harvest contract's spice). */
      top.appendChild(faceIcon(tag[1], tag[2]));
      pictures = true;
    } else if (token === "<b>" || token === "<i>") {
      const wrap = document.createElement(token.slice(1, 2));
      top.appendChild(wrap);
      stack.push(wrap);
    } else if (token === "</b>" || token === "</i>") {
      if (stack.length > 1) stack.pop();
    } else if (/^[.,:;!?)]/.test(token) && top.lastChild && top.lastChild.nodeType === 1
      && !/^(B|I)$/.test(top.lastChild.tagName)) {
      /* Punctuation right after an icon stays on its line ("…turns, 💎."). */
      const [, mark, rest] = token.match(/^([.,:;!?)]+)([\s\S]*)$/);
      const keep = faceEl("span", "cf-nobr");
      keep.append(top.lastElementChild, mark);
      top.append(keep, rest);
      if (/[^\s:+]/.test(token)) words = true;
    } else {
      top.append(token);
      /* A colon or "+" between icons ("🧬 : +1") keeps the row an icon
         row, as print draws it; any other letter makes it text. */
      if (/[^\s:+]/.test(token)) words = true;
    }
  }
  if (pictures && !words && !plain) {
    line.classList.add("big");
    /* One icon alone on its line: print draws it larger still; a row of
       many (Questionable Methods' arrow and four swords) a little smaller,
       so it keeps to one row. */
    if (line.childElementCount === 1) line.classList.add("one");
    if (line.childElementCount >= 6) line.classList.add("many");
  }
  if (words) faceKeepTail(line);
  return line;
}

/* A worded line's last word stays with the icons after it ("…contracts:
   📗", "1개당 (1).", "+ 💎 3"), so no icon is left alone on a wrapped line. */
function faceKeepTail(line) {
  const nodes = [...line.childNodes];
  let at = nodes.length - 1;
  const trailing = (node) => (node.nodeType === 1 && !/^(B|I)$/.test(node.tagName))
    || (node.nodeType === 3 && /^[\s+.,:;!?)]*$/.test(node.nodeValue));
  while (at >= 0 && trailing(nodes[at])) at -= 1;
  const tail = nodes.slice(at + 1);
  const before = nodes[at];
  if (!tail.some((node) => node.nodeType === 1) || !before || before.nodeType !== 3) return;
  /* The last word, with a lone "+" or stop after it ("units: +"). */
  const parts = before.nodeValue.match(/^([\s\S]*?)(\S+\s*(?:[+.,:;!?)]+\s*)?)$/);
  if (!parts || !parts[1].trim()) return;
  before.nodeValue = parts[1];
  line.appendChild(faceEl("span", "cf-nobr", parts[2], ...tail));
}

/* A Faction's mark naming a board space ("on an {Emperor} board space",
   "Spy on {Emperor}/{Fremen}", "…에 {spy}") is the plain mark, as print
   sets it; the dark badge is for Influence and Alliance conditions. */
function faceSpaceMarks(source) {
  const faction = "\\{agent_icon_(?:emperor|spacing_guild|bene_gesserit|fremen)\\}";
  const plain = (text) => text.replace(/\{agent_icon_/g, "{agent_mark_");
  return source
    .replace(new RegExp(`${faction}(?=\\s*(?:board space|\uAC8C\uC784\uD310 \uC7A5\uC18C))`, "g"), plain)
    .replace(new RegExp(`(\\bon an? |\\bon )((?:${faction}/?)+)`, "g"), (_m, on, marks) => on + plain(marks))
    .replace(new RegExp(`((?:${faction}/?)+)(?=\\s*\uC5D0)`, "g"), plain);
}

function faceSpecimens(count) {
  const box = faceEl("div", "cf-specimens");
  for (const [x, y] of SPECIMEN_LAYOUT[count] || SPECIMEN_LAYOUT[1]) {
    const cube = document.createElement("img");
    cube.src = SPECIMEN_CUBE;
    cube.alt = "";
    cube.draggable = false;
    cube.style.left = `calc(${x} * var(--cf-cube))`;
    cube.style.top = `calc(${y} * var(--cf-cube) * 1.12)`;
    box.appendChild(cube);
  }
  box.title = `${count} ${faceWord("specimen")}`;
  return box;
}

/* The acquire bonus the print hangs under the cost: the icons of the
   entry's acquire line (its display text, built from the engine's card;
   ``text`` and ``text_ko`` list the same lines, ``text`` says which). */
function faceAcquireIcons(entry) {
  const at = (entry.text || []).findIndex((text) => text.startsWith("On acquire"));
  const line = at >= 0 ? (entry.text_ko || [])[at] : null;
  if (!line) return [];
  /* A choice ("Recruit 2 troops / Tleilaxu": Reclaimed Forces) prints its
     options with "—OR—" between them; a counted piece without a number
     inside it (two troops) prints that many times. */
  const nodes = [];
  line.split(" / ").forEach((part, index) => {
    const option = faceEl("span", "cf-tabopt");
    for (const [, name, count] of part.matchAll(/\{([a-z_0-9]+)(?::(\d+\+?))?\}/g)) {
      if (count && !FACE_INSIDE[name] && /^\d+$/.test(count)) {
        /* Two of one piece (Reclaimed Forces' troops) print as a pair set
           corner to corner; three or more (Occupation's troops) and
           different pieces (CHOAM Directorship's Influences) stack. */
        if (Number(count) === 2) option.classList.add("pair");
        for (let k = 0; k < Number(count); k += 1) option.appendChild(faceIcon(name));
      } else {
        option.appendChild(faceIcon(name, count));
      }
    }
    if (!option.childElementCount) return;
    if (nodes.length) nodes.push(faceEl("span", "cf-tabor", t("card_faces.or")));
    nodes.push(option);
  });
  return nodes;
}

/* The module mark print sets before a card's name: the CHOAM Module's red
   ring (Cargo Runner, Leverage, ...) or the Tech Module's ring of gold dots
   (Ixian Ambassador, Rapid Engineering, ...). */
function faceChoamRing(entry) {
  if (entry.choam || entry.choam_only) return faceEl("span", "cf-ring");
  if (entry.tech_module) return faceEl("span", "cf-ring cf-techmark");
  return null;
}

function imperiumFace(entry) {
  const tleilaxu = entry.specimens !== undefined && entry.specimens !== null;
  const card = faceEl("div", "card-face cf-imp" + (tleilaxu ? " cf-tle" : ""));
  card.dataset.face = "imperium";
  const nameBand = faceEl("div", "cf-name");
  const ring = faceChoamRing(entry);
  if (ring) nameBand.appendChild(ring);
  /* The starting deck's cards print a small chevron before the name. */
  if (entry.set === "starting") nameBand.appendChild(faceEl("span", "cf-startmark"));
  nameBand.append(entry.name);
  const head = faceEl("div", "cf-head", nameBand);
  /* One ribbon per Faction, stacked as print stacks them (Double Agent's
     two, Face Dancer's three). */
  const factions = entry.factions || [];
  if (factions.length) {
    const ribbons = faceEl("div", "cf-ribbons");
    for (const faction of factions) {
      /* Every ribbon as wide as the longest Faction name in this language:
         all four names sit in one grid cell, only this one shown. */
      const ribbon = faceEl("div", "cf-ribbon");
      for (const other of Object.keys(FACE_FACTION_COLORS)) {
        const label = faceEl("span", other === faction ? "" : "off", FACTION_LABELS[other] || other);
        if (other !== faction) label.setAttribute("aria-hidden", "true");
        ribbon.appendChild(label);
      }
      ribbon.style.setProperty("--cf-faction", FACE_FACTION_COLORS[faction] || "#666");
      ribbons.appendChild(ribbon);
    }
    head.appendChild(ribbons);
  }
  const upper = faceEl("div", "cf-upper", head);
  card.appendChild(upper);
  const priced = entry.cost !== null && entry.cost !== undefined;
  if (tleilaxu) {
    card.appendChild(faceSpecimens(entry.specimens));
  } else if (priced) {
    /* Foldspace prints its red swirl in the cost's place, not a number. */
    const cost = entry.cost_mark === "foldspace"
      ? faceEl("div", "cf-cost cf-cost-foldspace", faceEl("i"))
      : faceEl("div", "cf-cost", faceEl("b", "", String(entry.cost)));
    cost.title = t("core.cost_label");
    card.appendChild(cost);
  }
  /* The acquire bonus hangs under the cost, or under a Tleilaxu card's
     specimens (Corrino Genes, Subject X-137, Reclaimed Forces), led by
     print's chevron. */
  const acquire = tleilaxu || priced ? faceAcquireIcons(entry) : [];
  if (acquire.length) {
    card.appendChild(faceEl("div", "cf-tab", faceEl("span", "cf-chev"), ...acquire));
    card.classList.add("has-tab");
  }
  /* The Agent icons as their marks alone: print sets them on grey plates,
     the redrawn face need not (user 2026-11-11). */
  const icons = faceEl("div", "cf-icons");
  for (const icon of entry.agent_icons || []) {
    const mark = document.createElement("img");
    mark.className = "cf-ic cf-mark";
    mark.src = `${AGENT_MARK_DIR}agent_mark_${icon}.svg`;
    mark.alt = faceWord(`agent_icon_${icon}`);
    mark.title = mark.alt;
    mark.draggable = false;
    icons.appendChild(mark);
  }
  upper.appendChild(icons);

  const agent = faceEl("div", "cf-agent");
  /* "When this card is trashed / discarded", "At the start of your turn":
     print sets these in their own red band right above the Agent box. */
  const staticText = faceText(entry, "static");
  if (staticText) upper.appendChild(faceRich(staticText, "cf-static"));
  const agentText = faceText(entry, "agent");
  if (agentText) {
    const body = faceRich(agentText, "cf-body");
    const lines = body.querySelectorAll(".cf-line");
    if (lines.length === 1 && lines[0].classList.contains("big")) body.classList.add("solo");
    agent.appendChild(body);
  }
  if (entry.graft) {
    agent.classList.add("grafts");
    agent.appendChild(faceEl("span", "cf-graft", termLabel("graft")));
  }
  const reveal = faceEl("div", "cf-reveal");
  let revealText = faceText(entry, "reveal") || "";
  if (revealText.includes("{unload}")) {
    /* Unload prints as a red tag down the Reveal box's whole left edge,
       pointing in, with its two little cards (draw ↓, trash ✕) on it. */
    revealText = revealText.replace(/\s*\{unload\}\s*/g, " ").trim();
    reveal.classList.add("unloads");
    const cards = document.createElement("img");
    cards.src = `${AGENT_MARK_DIR}unload_cards.svg`;
    cards.alt = faceWord("unload");
    cards.draggable = false;
    const tag = faceEl("span", "cf-unload", cards);
    tag.title = cards.alt;
    reveal.appendChild(tag);
  }
  const [first, ...rest] = revealText.split("\n");
  if (first && !first.replace(/\{[a-z_0-9]+(?::\d+\+?)?\}/g, "").trim()) {
    /* Numbers alone open the Reveal box (Persuasion, swords): its big row,
       larger still when they are all it prints. */
    reveal.appendChild(faceRich(first, rest.length ? "cf-stats" : "cf-stats only"));
    if (rest.length) reveal.appendChild(faceRich(rest.join("\n")));
  } else if (revealText) {
    reveal.appendChild(faceRich(revealText));
  }
  card.appendChild(faceEl("div", "cf-lower", agent, reveal));
  card.title = entry.name;
  return card;
}

/* An Intrigue card, 44.2 x 68 mm: its name under the printed red ring, its
   parts (one per timing, or per choice of one timing) on their timing's
   colour with "—OR—" between them, the timings named at its foot. The
   type size is one for every card (the longest, Grand Conspiracy, still
   fits); the parts share the height by what they hold. */
function intrigueFace(entry) {
  /* A Navigation card prints no name and no timing: its band stays empty. */
  const card = faceEl("div", "card-face cf-int" + (entry.navigation ? " cf-nav" : ""));
  card.dataset.face = "intrigue";
  const title = faceEl("span", "", entry.navigation ? "" : entry.name);
  const ring = faceChoamRing(entry);
  if (ring) title.prepend(ring);
  card.appendChild(faceEl("div", "cf-ihead", title));
  const parts = entry.face.parts || [];
  parts.forEach((part, index) => {
    if (index) card.appendChild(faceEl("div", "cf-or", t("card_faces.or")));
    const text = (TERM_LANGUAGE === "ko" && part.ko) || part.en || "";
    const half = faceRich(text, `cf-half cf-${part.timing}`);
    /* A short part's lone icon prints large (Favored Subject). */
    if (half.querySelectorAll(":scope > .cf-line").length <= 3) half.classList.add("few");
    card.appendChild(half);
  });
  const timings = [];
  /* A Navigation card prints no timing at its foot. */
  for (const part of parts) {
    if (part.timing !== "navigation" && !timings.includes(part.timing)) timings.push(part.timing);
  }
  const foot = faceEl("div", "cf-foot");
  timings.forEach((timing, index) => {
    if (index) foot.append(" / ");
    foot.appendChild(faceEl("span", `cf-t-${timing}`, TIMING_KEYS[timing] ? t(TIMING_KEYS[timing]) : timing));
  });
  card.appendChild(foot);
  card.title = entry.name;
  return card;
}

/* A Conflict card, 44.2 x 68 mm: its name upright along the left edge as
   printed, its battle icon in the gold corner, and its three rewards in
   their boxes, each under its place ("1st", "2nd", "3rd"). */
function conflictFace(entry) {
  const card = faceEl("div", "card-face cf-conflict");
  card.dataset.face = "conflict";
  /* A card about a board space (its first reward takes the space's
     Control) prints on the orange front, as the app's renderer does. */
  const first = ((entry.face.rewards || [])[0] || {}).en || "";
  if (first.includes("{control}") && entry.set !== "imperium" && entry.set !== "ix") {
    card.classList.add("cf-orange");
  }
  card.appendChild(faceEl("div", "cf-ctitle", entry.name));
  if (entry.icon) {
    const mark = document.createElement("img");
    mark.className = "cf-ic";
    mark.src = `${AGENT_MARK_DIR}battle_mark_${entry.icon}.svg`;
    mark.alt = faceWord(`battle_${entry.icon}`);
    mark.title = mark.alt;
    mark.draggable = false;
    card.appendChild(faceEl("div", `cf-battle cf-b-${entry.icon}`, mark));
  }
  const rewards = faceEl("div", "cf-rewards");
  (entry.face.rewards || []).forEach((reward, index) => {
    const text = (TERM_LANGUAGE === "ko" && reward.ko) || reward.en || "";
    const place = faceEl(
      "span", "cf-place", String(index + 1),
      faceEl("sup", "", t(["card_faces.first", "card_faces.second", "card_faces.third"][index] || "card_faces.third")),
    );
    rewards.appendChild(faceEl("div", "cf-reward", place, faceRich(text)));
  });
  card.appendChild(rewards);
  if (entry.shield_wall_protected) {
    /* Behind the Shield Wall: no sandworm fights here, printed in the
       third box's corner. */
    const mark = faceEl("span", "cf-noworm", faceIcon("sandworm"));
    mark.title = faceWord("shield_wall");
    card.appendChild(mark);
  }
  card.title = entry.name;
  return card;
}

/* A contract tile, 55 x 35 mm: its name, the condition as its printed frame
   (the space it names, an Agent standing in it, what is laid on it), and
   its reward large on the right. */
function contractFace(entry) {
  const face = entry.face;
  const card = faceEl("div", "card-face cf-contract");
  card.dataset.face = "contract";
  card.style.setProperty("--cf-tile", CONTRACT_TILE_COLOR[face.tile] || "#7a2a2c");
  const title = face.title || {};
  const head = faceEl("div", "cf-khead", (TERM_LANGUAGE === "ko" && title.ko) || title.en || entry.name);
  if (face.subtitle) head.appendChild(faceEl("small", "cf-ksub", faceLang(face.subtitle)));
  card.appendChild(head);
  const condition = ((TERM_LANGUAGE === "ko" && face.condition.ko) || face.condition.en || "")
    .replace(/\{agent_icon_([a-z_]+)\}/g, "{agent_mark_$1}");
  if (face.frame) {
    const frame = faceEl("div", "cf-send", faceEl("span", "cf-who"), faceRich(condition, "cf-on"));
    frame.style.setProperty("--cf-frame", CONTRACT_FRAME_TINT[face.frame] || "#2a1416");
    card.appendChild(frame);
  } else {
    /* An Immediate tile prints no condition frame: its reward alone. */
    card.classList.add("cf-noframe");
  }
  const reward = (TERM_LANGUAGE === "ko" && face.reward.ko) || face.reward.en || "";
  card.appendChild(faceRich(reward, "cf-prize"));
  card.title = entry.name;
  return card;
}

/* A Tech tile, 70 x 46 mm: its name on the gold band, its Spice cost in
   the orange hexagon, the acquire strip's icons under it, its body. */
function techFace(entry) {
  const face = entry.face;
  const card = faceEl("div", "card-face cf-tech");
  card.dataset.face = "tech";
  const name = faceEl("div", "cf-tname" + (String(entry.name).length > 20 ? " long" : ""), entry.name);
  const ring = faceChoamRing(entry);
  if (ring) name.prepend(ring);
  card.appendChild(name);
  const cost = faceEl("div", "cf-hex", String(entry.cost));
  cost.title = t("core.cost_label");
  card.appendChild(cost);
  const strip = (TERM_LANGUAGE === "ko" && face.strip.ko) || face.strip.en || "";
  if (strip) {
    /* Print's big chevron leads from the cost down to what acquiring gives. */
    const stripNode = faceRich(strip, "cf-strip");
    stripNode.prepend(faceEl("span", "cf-chev"));
    card.appendChild(stripNode);
  }
  const body = (TERM_LANGUAGE === "ko" && face.body.ko) || face.body.en || "";
  const bodyNode = faceRich(body, "cf-body");
  /* A short body's lone icon prints very large (Windtraps' water,
     Memocorders' victory point): the fewer lines, the larger. */
  const lines = bodyNode.querySelectorAll(".cf-line").length;
  if (lines <= 2) bodyNode.classList.add("few");
  else if (lines <= 4) bodyNode.classList.add("some");
  card.appendChild(bodyNode);
  card.title = entry.name;
  return card;
}

/* A leader face's own boxes for the token a seat keeps on its card (percent
   of the face, as entry.layout's boxes are of the printed card): Feyd-Rautha's
   Training track forks as print draws it, Chani's eleven Tactics spaces lie
   in one row. leaderFaceLayout hands them to core.js's leaderTokenBox. */
const FEYD_FACE_BOXES = {
  start: [3, 24, 8, 11],
  paid_trash: [15, 17.5, 21, 11],
  first_spy: [15, 30.5, 21, 11],
  mid_trash: [40, 24, 9, 11],
  late_trash: [53, 17.5, 23, 11],
  second_spy: [53, 30.5, 10.5, 11],
  double_spice: [65.5, 30.5, 10.5, 11],
  final: [80, 17.5, 17, 24],
};
const FEYD_FACE_PATHS = [
  ["start", "paid_trash"], ["start", "first_spy"], ["paid_trash", "mid_trash"],
  ["first_spy", "mid_trash"], ["mid_trash", "late_trash"], ["mid_trash", "second_spy"],
  ["second_spy", "double_spice"], ["late_trash", "final"], ["double_spice", "final"],
];
const CHANI_FACE_BOXES = Array.from({ length: 11 }, (_, i) => [2.6 + i * 8.82, 23, 7.6, 14]);

function leaderFaceLayout(entry) {
  const track = entry.face && entry.face.track;
  if (!track) return null;
  if (track.kind === "feyd") return { track: FEYD_FACE_BOXES };
  if (track.kind === "chani") return { track: CHANI_FACE_BOXES };
  return null;
}

function faceLang(texts) {
  return (texts && ((TERM_LANGUAGE === "ko" && texts.ko) || texts.en)) || "";
}

function faceAt(node, [left, top, width, height]) {
  node.style.left = `${left}%`;
  node.style.top = `${top}%`;
  node.style.width = `${width}%`;
  node.style.height = `${height}%`;
  return node;
}

/* The track print draws in a leader's art: Feyd-Rautha's Training track
   (cells joined by its paths), Chani's Tactics track, Tessia's Snooper
   rewards (topmost first). */
function leaderTrack(track) {
  const band = faceEl("div", `cf-ltrack cf-ltrack-${track.kind}`);
  if (track.kind === "snooper") {
    for (const cell of track.cells) band.appendChild(faceRich(faceLang(cell), "cf-lcell"));
    return band;
  }
  if (track.kind === "feyd") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.classList.add("cf-lpaths");
    for (const [from, to] of FEYD_FACE_PATHS) {
      const [l1, t1, w1, h1] = FEYD_FACE_BOXES[from];
      const [l2, t2, , h2] = FEYD_FACE_BOXES[to];
      const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const x1 = l1 + w1;
      const y1 = t1 + h1 / 2;
      const y2 = t2 + h2 / 2;
      const mid = (x1 + l2) / 2;
      line.setAttribute("d", `M${x1} ${y1} H${mid} V${y2} H${l2}`);
      svg.appendChild(line);
    }
    band.appendChild(svg);
  }
  const boxes = track.kind === "feyd" ? FEYD_FACE_BOXES : CHANI_FACE_BOXES;
  for (const cell of track.cells) {
    const box = boxes[cell.space];
    if (!box) continue;
    const node = faceAt(faceRich(faceLang(cell), "cf-lcell"), box);
    if (cell.space === "final") node.classList.add("final");
    band.appendChild(node);
  }
  return band;
}

/* A leader card: name with its complexity pips (and the CHOAM ring or the
   Tech gear before it), the House line, the track its art prints, the
   ability box (two stacked for Staban Tuek and Steersman Y'rkoon) and the
   Signet Ring box (Plot Course in Y'rkoon's). At the printed card's
   proportions; the art and the play mat's DECK/DISCARD tabs are left out. */
function leaderFace(entry) {
  const face = entry.face;
  const card = faceEl("div", "card-face cf-leader");
  card.dataset.face = "leader";
  const name = faceEl("div", "cf-lname");
  if (face.mark) name.appendChild(faceEl("span", `cf-lmark cf-lmark-${face.mark}`));
  name.appendChild(faceEl("span", "cf-lnametext", entry.name));
  const pips = faceEl("span", "cf-pips");
  for (let i = 0; i < (face.pips || 0); i += 1) pips.appendChild(faceEl("i"));
  name.appendChild(pips);
  card.appendChild(name);
  if (face.slots) {
    /* Steersman Y'rkoon: the Navigation cards' four slots, numbered. */
    const slots = faceEl("div", "cf-lslots");
    card.classList.add("has-slots");
    for (let k = 1; k <= face.slots; k += 1) slots.appendChild(faceEl("span", "", String(k)));
    card.appendChild(slots);
  }
  if (face.house) card.appendChild(faceEl("div", "cf-house", faceLang(face.house)));
  if (face.track) card.appendChild(leaderTrack(face.track));
  const abilities = faceEl("div", "cf-labil");
  for (const ability of face.abilities || []) {
    const part = faceEl("div", "cf-lpart" + (ability.tone === "red" ? " red" : ""));
    part.appendChild(faceEl("div", "cf-ltitle", faceLang(ability.title)));
    part.appendChild(faceRich(faceLang(ability.text), "cf-ltext"));
    abilities.appendChild(part);
  }
  card.appendChild(abilities);
  const signet = faceEl("div", "cf-lsignet");
  const badge = faceEl("span", "cf-lbadge" + (face.signet.kind === "navigation" ? " nav" : ""));
  if (face.signet.kind !== "navigation") badge.appendChild(faceIcon("signet_ring"));
  signet.appendChild(badge);
  signet.appendChild(faceEl("div", "cf-ltitle", faceLang(face.signet.title)));
  signet.appendChild(faceRich(faceLang(face.signet.text), "cf-ltext"));
  card.appendChild(signet);
  card.title = entry.name;
  return card;
}

/* A Sardaukar Commander Skill tile (Bloodlines), square: its name on the
   dark red band, what it prints on the pale body under it. */
function skillFace(entry) {
  const card = faceEl("div", "card-face cf-skill");
  card.dataset.face = "skill";
  card.appendChild(faceEl("div", "cf-sname", entry.name));
  const body = (TERM_LANGUAGE === "ko" && entry.face.body.ko) || entry.face.body.en || "";
  card.appendChild(faceRich(body, "cf-body"));
  card.title = entry.name;
  return card;
}

/* The face for a catalog entry without a picture, or null (the caller
   keeps its text card): Imperium, Tleilaxu, Intrigue, Conflict, contract,
   Tech, leader and Skill cards. */
/* An Uprising Objective card, 44.2 x 68 mm like a Conflict card: its
   battle icon large on the icon's colour, the icon again in the corner, the
   player count (or the First Player mark) and its one printed line. */
function objectiveFace(entry) {
  const face = entry.face;
  const card = faceEl("div", `card-face cf-objective cf-o-${entry.icon}`);
  card.dataset.face = "objective";
  const mark = (className) => {
    const img = document.createElement("img");
    img.className = className;
    img.src = `${AGENT_MARK_DIR}battle_mark_${entry.icon}.svg`;
    img.alt = faceWord(`battle_${entry.icon}`);
    img.draggable = false;
    return img;
  };
  card.appendChild(faceEl("div", "cf-ocorner", mark("cf-ic")));
  if (face.players) card.appendChild(faceEl("div", "cf-oplayers", face.players));
  card.appendChild(mark("cf-obig"));
  if (face.first_player) {
    const token = document.createElement("img");
    token.className = "cf-ofirst";
    token.src = "/static/pictures/tokens/first_player.svg";
    token.alt = faceWord("first_player");
    token.title = token.alt;
    token.draggable = false;
    card.appendChild(token);
  }
  card.appendChild(faceEl("div", "cf-otext", faceLang(face.text)));
  card.title = entry.name;
  return card;
}

function cardFace(entry) {
  if (!entry || entry.image || !entry.face) return null;
  if (entry.face.kind === "skill") return skillFace(entry);
  if (entry.face.kind === "objective") return objectiveFace(entry);
  if (entry.face.signet) return leaderFace(entry);
  if (entry.face.parts) return intrigueFace(entry);
  if (entry.face.strip) return techFace(entry);
  if (entry.face.rewards) return conflictFace(entry);
  if (entry.face.frame !== undefined) return contractFace(entry);
  return imperiumFace(entry);
}
