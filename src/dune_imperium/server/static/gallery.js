/* The card encyclopedia (user 2026-11-11: "공식적으로 카드 백과사전 같은
   느낌으로"): every card, Conflict, Contract, Tech tile, Leader and Skill
   tile as its redrawn face, by kind, searchable by name in either language
   and filtered by the box it comes in (catalog `set`, `promo`); a click
   shows the face large with its rules text (core.js popoverNodes) and the
   project's rulings that name it. Below them, apart, the inspection tabs:
   every one of the project's own drawings (static/pictures/index.json)
   with its note, for a look by eye.

   Opened by the setup screen's and the help panel's buttons, or by
   #cards / #gallery in the address. It reads only the catalog and the
   pictures and touches no game. */

const GALLERY_FACES = [
  ["cards", "gallery.kind_cards", 200],
  ["intrigue", "gallery.kind_intrigue", 170],
  ["conflicts", "gallery.kind_conflicts", 170],
  ["contracts", "gallery.kind_contracts", 280],
  ["tech", "gallery.kind_tech", 320],
  ["leaders", "gallery.kind_leaders", 480],
  ["skills", "gallery.kind_skills", 200],
  ["objectives", "gallery.kind_objectives", 170],
];
const GALLERY_PICTURES = [
  ["icons", "Icons", 90],
  ["log", "Log icons", 70],
  ["tokens", "Pieces & tokens", 120],
  ["faces", "Face pieces", 90],
  ["board", "Boards", 0],
];
/* The boxes in the order the games came out, the starting deck first. */
const GALLERY_SETS = ["starting", "imperium", "ix", "immortality", "uprising", "bloodlines"];
const GALLERY_SET_KEYS = {
  starting: "gallery.set_starting",
  imperium: "gallery.set_imperium",
  ix: "gallery.set_ix",
  immortality: "gallery.set_immortality",
  uprising: "gallery.set_uprising",
  bloodlines: "gallery.set_bloodlines",
};
/* The detail view's face width by kind (px). */
const GALLERY_BIG = { cards: 340, intrigue: 300, conflicts: 300, contracts: 440, tech: 480, leaders: 620, skills: 340, objectives: 300 };

function galleryButton(label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function galleryCell(node, caption, title = "") {
  const cell = document.createElement("figure");
  cell.className = "gallery-cell";
  cell.appendChild(node);
  const text = document.createElement("figcaption");
  text.textContent = caption;
  if (title) text.title = title;
  cell.appendChild(text);
  return cell;
}

/* An entry's names in both languages (localizeCatalog keeps the English
   under name_en once it has a Korean name), for search and the detail. */
function galleryNames(entry, id) {
  return [entry.name, entry.name_en, entry.name_ko, id].filter((name) => typeof name === "string" && name);
}

/* The project's rulings that name this card (its English or Korean name in
   a ruling's title, text or kept names). */
function galleryRulings(entry) {
  const names = [entry.name_en || entry.name, entry.name_ko].filter((name) => name && name.length > 3);
  if (!names.length) return [];
  return (state.catalog.house_rulings || []).filter((ruling) => {
    const text = [ruling.title, ruling.title_ko, ruling.ruling, ruling.ruling_ko, ...(ruling.names || [])].join("\n");
    return names.some((name) => text.includes(name));
  });
}

/* A card with no redrawn face yet (Bloodlines' Imperium cards and the
   Navigation cards wait for their print to be transcribed): its name and
   rules text on a plain card of the kind's shape, so the encyclopedia still
   lists it. */
function galleryPlainFace(kind, entry) {
  const card = document.createElement("div");
  card.className = `gallery-plain gallery-plain-${kind}`;
  const name = document.createElement("b");
  name.textContent = entry.name;
  const note = document.createElement("small");
  note.className = "muted";
  note.textContent = t("gallery.no_face");
  const text = document.createElement("div");
  text.className = "gallery-plain-text";
  for (const node of popoverNodes(entry)) text.appendChild(node);
  card.append(name, note, text);
  return card;
}

function galleryTag(text, className = "") {
  const tag = document.createElement("span");
  tag.className = `gallery-tag ${className}`.trim();
  tag.textContent = text;
  return tag;
}

/* The detail view: the face large, the names, the box, the rules text and
   the rulings that name the card. */
function galleryDetail(root, kind, id) {
  const entry = state.catalog[kind][id];
  const backdrop = document.createElement("div");
  backdrop.className = "gallery-detail";
  const panel = document.createElement("div");
  panel.className = "gallery-detail-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey, true);
  };
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close();
    }
  };
  document.addEventListener("keydown", onKey, true);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) close();
  });

  const face = document.createElement("div");
  face.className = "gallery-detail-face";
  face.style.width = `${GALLERY_BIG[kind] || 340}px`;
  face.appendChild(cardFace({ ...entry, image: null }) || galleryPlainFace(kind, entry));

  const info = document.createElement("div");
  info.className = "gallery-detail-info";
  const head = document.createElement("div");
  head.className = "gallery-detail-head";
  const title = document.createElement("h3");
  title.textContent = entry.name || id;
  head.append(title, galleryButton(t("common.close"), close));
  info.appendChild(head);
  const other = TERM_LANGUAGE === "ko" ? entry.name_en : entry.name_ko;
  if (other && other !== entry.name) {
    const sub = document.createElement("div");
    sub.className = "muted";
    sub.textContent = other;
    info.appendChild(sub);
  }
  const tags = document.createElement("div");
  tags.className = "gallery-tags";
  if (entry.set) tags.appendChild(galleryTag(t(GALLERY_SET_KEYS[entry.set])));
  if (entry.promo) tags.appendChild(galleryTag(t("gallery.promo"), "promo"));
  if (entry.choam || entry.choam_only) tags.appendChild(galleryTag(t("gallery.choam"), "choam"));
  if (entry.tech_module) tags.appendChild(galleryTag(t("gallery.tech_module"), "techmodule"));
  info.appendChild(tags);
  const text = document.createElement("div");
  text.className = "gallery-detail-text";
  for (const node of popoverNodes(entry)) text.appendChild(node);
  info.appendChild(text);
  const rulings = galleryRulings(entry);
  if (rulings.length) {
    const heading = document.createElement("h4");
    heading.textContent = t("gallery.rulings");
    info.appendChild(heading);
    for (const ruling of rulings) {
      const item = document.createElement("div");
      item.className = "gallery-ruling";
      const name = document.createElement("b");
      name.textContent = (TERM_LANGUAGE === "ko" && ruling.title_ko) || ruling.title;
      const body = document.createElement("p");
      body.textContent = (TERM_LANGUAGE === "ko" && ruling.ruling_ko) || ruling.ruling;
      item.append(name, body);
      info.appendChild(item);
    }
  }
  panel.append(face, info);
  backdrop.appendChild(panel);
  root.appendChild(backdrop);
  panel.querySelector("button").focus();
}

/* `fromPage`: opened over a page already set up (its buttons), so closing
   just takes the encyclopedia away; opened by the address at load, closing
   loads the page proper. */
async function openGallery(fromPage = false) {
  if (document.getElementById("gallery")) return;
  const index = await fetch("/static/pictures/index.json").then((response) => response.json());
  const root = document.createElement("div");
  root.id = "gallery";
  const bar = document.createElement("div");
  bar.className = "gallery-bar";
  const body = document.createElement("div");
  body.className = "gallery-body";
  root.append(bar, body);
  document.body.appendChild(root);

  let current = GALLERY_FACES[0][0];
  let scale = 1;
  let query = "";
  let shownSet = "";
  const heading = document.createElement("h2");
  heading.className = "gallery-title";
  const tabs = document.createElement("div");
  tabs.className = "gallery-tabs";
  const filters = document.createElement("div");
  filters.className = "gallery-filters";
  const search = document.createElement("input");
  search.type = "search";
  search.className = "gallery-search";
  search.addEventListener("input", () => {
    query = search.value.trim().toLowerCase();
    render();
  });
  const sets = document.createElement("div");
  sets.className = "gallery-sets";
  filters.append(search, sets);
  const pictureTabs = document.createElement("div");
  pictureTabs.className = "gallery-tabs gallery-pictures";
  const tools = document.createElement("div");
  tools.className = "gallery-tools";
  const language = galleryButton("", () => {
    setLanguage(TERM_LANGUAGE === "en" ? "ko" : "en", fromPage);
    render();
  });
  const size = document.createElement("input");
  size.type = "range";
  size.min = "0.5";
  size.max = "2.5";
  size.step = "0.1";
  size.value = "1";
  size.addEventListener("input", () => {
    scale = Number(size.value);
    render();
  });
  const close = galleryButton("", () => {
    if (!fromPage) {
      window.location.href = window.location.pathname + window.location.search;
      return;
    }
    root.remove();
  });
  close.className = "gallery-close";
  tools.append(language, size, close);
  const top = document.createElement("div");
  top.className = "gallery-top";
  top.append(heading, tools);
  bar.append(top, tabs, filters, pictureTabs);

  const faceIds = (kind) => Object.keys(state.catalog[kind] || {});
  const matches = (kind, id) => {
    if (!query) return true;
    return galleryNames(state.catalog[kind][id], id).some((name) => name.toLowerCase().includes(query));
  };
  const pictureNames = (folder) => Object.keys(index).filter((path) => path.startsWith(`${folder}/`)).sort();
  /* The order (user 2026-11-11): Imperium cards by their Persuasion cost,
     then by English name; the cards with no Persuasion cost after them
     (the starting deck, then the Tleilaxu cards by their specimens); every
     other kind by English name. */
  const englishName = (entry, id) => String(entry.name_en || entry.name || id);
  const order = (kind, entries) => (a, b) => {
    const x = entries[a];
    const y = entries[b];
    if (kind === "cards") {
      const cost = (entry) => (typeof entry.cost === "number" ? entry.cost : Infinity);
      const specimens = (entry) => (typeof entry.specimens === "number" ? entry.specimens : -1);
      if (cost(x) !== cost(y)) return cost(x) - cost(y);
      if (specimens(x) !== specimens(y)) return specimens(x) - specimens(y);
    }
    return englishName(x, a).localeCompare(englishName(y, b), "en");
  };

  function render() {
    heading.textContent = t("gallery.title");
    /* The header's own language button names the other language in it. */
    language.textContent = el("language-toggle").textContent;
    size.title = t("gallery.size");
    close.textContent = t("common.close");
    search.placeholder = t("gallery.search");
    tabs.replaceChildren();
    for (const [kind, key] of GALLERY_FACES) {
      const found = faceIds(kind).filter((id) => matches(kind, id)).length;
      const tab = galleryButton(`${t(key)} (${found})`, () => {
        current = kind;
        shownSet = "";
        render();
      });
      tab.classList.toggle("on", kind === current);
      tabs.appendChild(tab);
    }
    pictureTabs.replaceChildren();
    const label = document.createElement("span");
    label.className = "muted";
    label.textContent = t("gallery.pictures");
    pictureTabs.appendChild(label);
    for (const [folder, name] of GALLERY_PICTURES) {
      const tab = galleryButton(`${name} (${pictureNames(folder).length})`, () => {
        current = folder;
        render();
      });
      tab.classList.toggle("on", folder === current);
      pictureTabs.appendChild(tab);
    }
    body.replaceChildren();
    const face = GALLERY_FACES.find(([kind]) => kind === current);
    filters.hidden = !face;
    if (face) {
      const [kind, , width] = face;
      const entries = state.catalog[kind];
      const found = faceIds(kind).filter((id) => matches(kind, id));
      /* The boxes this kind has, with how many of the found are in each. */
      sets.replaceChildren();
      const present = GALLERY_SETS.filter((set) => found.some((id) => entries[id].set === set));
      if (present.length > 1) {
        const all = galleryButton(`${t("gallery.set_all")} (${found.length})`, () => {
          shownSet = "";
          render();
        });
        all.classList.toggle("on", !shownSet);
        sets.appendChild(all);
        for (const set of present) {
          const count = found.filter((id) => entries[id].set === set).length;
          const chip = galleryButton(`${t(GALLERY_SET_KEYS[set])} (${count})`, () => {
            shownSet = set;
            render();
          });
          chip.classList.toggle("on", shownSet === set);
          sets.appendChild(chip);
        }
      }
      const shown = found
        .filter((id) => !shownSet || entries[id].set === shownSet)
        .sort(order(kind, entries));
      if (!shown.length) {
        const none = document.createElement("p");
        none.className = "muted";
        none.textContent = t("gallery.none");
        body.appendChild(none);
      }
      for (const id of shown) {
        const entry = entries[id];
        const drawn = cardFace({ ...entry, image: null }) || galleryPlainFace(kind, entry);
        const holder = document.createElement("button");
        holder.type = "button";
        holder.className = "gallery-face";
        holder.style.width = `${Math.round(width * scale)}px`;
        holder.title = entry.name || id;
        holder.appendChild(drawn);
        holder.addEventListener("click", () => galleryDetail(root, kind, id));
        body.appendChild(galleryCell(holder, `${entry.name || id}`, id));
      }
      return;
    }
    const [folder, , height] = GALLERY_PICTURES.find(([name]) => name === current);
    for (const path of pictureNames(folder)) {
      const note = (index[path] || {}).note || "";
      const name = path.slice(folder.length + 1).replace(/\.svg$/, "");
      const img = document.createElement("img");
      img.src = `/static/pictures/${path}`;
      img.alt = name;
      img.loading = "lazy";
      if (folder === "board") {
        /* A board at the window's width; click to open it alone and zoom. */
        const link = document.createElement("a");
        link.href = img.src;
        link.target = "_blank";
        link.rel = "noopener";
        img.style.width = `${Math.round(100 * Math.min(scale, 1))}%`;
        link.appendChild(img);
        const cell = galleryCell(link, `${name} — ${note}`);
        cell.classList.add("wide");
        body.appendChild(cell);
      } else {
        img.style.height = `${Math.round(height * scale)}px`;
        body.appendChild(galleryCell(img, name, note));
      }
    }
  }
  render();
  search.focus();
}
