/* The table's loose pieces drawn from the Steam app's pictures: the First
   Player marker on its holder's seat panel, and the card backs of the
   face-down decks (the Conflict deck in its printed slot, the Imperium,
   Tleilaxu and Intrigue decks in the shared-card column, Kota Odax's
   Secret Project tile). Every helper here falls back
   to the drawing the UI had before when the private assets lack the
   picture (the catalog then carries null), so a checkout without them
   looks as it always did. */

/* The First Player marker beside its holder's name: "첫 라운드의 First
   Player는 공개된 Objective로 결정한다" [Main p. 5], passed clockwise in
   Recall [Main p. 15]. The app's round token (catalog.first_player_token),
   or the short text badge without it; either way it is named by the
   glossary's term. */
function firstPlayerMark() {
  const name = phraseText("{first_player}");
  const url = state.catalog && state.catalog.first_player_token;
  if (!url) {
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = t("panels.first_badge");
    badge.title = name;
    return badge;
  }
  const token = document.createElement("img");
  token.className = "first-player-token";
  token.src = url;
  token.alt = name;
  token.title = name;
  token.draggable = false;
  return token;
}

/* ---------- card backs and face-down decks ---------- */

const TIER_NUMERALS = ["I", "II", "III"];

/* The app's picture of a card back (catalog.card_backs: imperium,
   intrigue, conflict_1..3, tech), or null where the assets lack it. */
function cardBackUrl(kind) {
  const backs = (state.catalog && state.catalog.card_backs) || {};
  return backs[kind] || null;
}

function cardBackImage(url, className) {
  const back = document.createElement("img");
  back.className = className;
  back.src = url;
  back.alt = "";
  back.draggable = false;
  return back;
}

/* A face-down deck drawn as its back with the count on it, or null
   without the picture. Never a `.vcard`: that class means a card face
   (popovers, clicks, the e2e). The count already stands in text beside
   it (a strip heading, the Intrigue deck line), so the pile is hidden
   from screen readers and only titled for the mouse. */
function deckPile(kind, count, title) {
  const url = cardBackUrl(kind);
  if (!url) return null;
  const pile = document.createElement("span");
  pile.className = count > 0 ? "deck-pile" : "deck-pile empty";
  pile.dataset.back = kind;
  pile.title = title;
  pile.setAttribute("aria-hidden", "true");
  const badge = document.createElement("span");
  badge.className = "deck-pile-count";
  badge.textContent = String(count);
  pile.append(cardBackImage(url, "deck-pile-back"), badge);
  return pile;
}

/* Put a deck's pile first in `parent` (a strip's card row, the Intrigue
   deck line); without the picture `parent` stays as it was. A line's own
   text and icons are wrapped into one label first, so that they stay
   together beside the pile. */
function prependDeckPile(parent, kind, count, title) {
  const pile = deckPile(kind, count, title);
  if (!pile) return;
  if (!parent.classList.contains("strip-cards")) {
    const label = document.createElement("span");
    label.className = "deck-pile-label";
    label.append(...parent.childNodes);
    parent.appendChild(label);
  }
  parent.classList.add("with-deck-pile");
  parent.prepend(pile);
}

/* The face-down Conflict deck in its printed slot: `deck` is the drawn
   box board.js renderSlotCards builds. The deck is built by back, I on
   II on III, and lies face down [Main p. 4], so the top card's tier is
   public (view.conflict_deck_top_tier, 0 once the deck is empty): its
   back fills the box with the count on it, and the title names the tier.
   Without that tier's picture the drawn box stays. */
function showConflictDeckBack(deck, view) {
  const tier = view.conflict_deck_top_tier || 0;
  if (!tier) return;
  deck.dataset.tier = String(tier);
  deck.title = `${deck.title} · ${t("core.conflict_tier", { tier: TIER_NUMERALS[tier - 1] })}`;
  const url = cardBackUrl(`conflict_${tier}`);
  if (!url) return;
  deck.classList.add("pictured");
  deck.prepend(cardBackImage(url, "slot-deck-back"));
}

/* Kota Odax of Ix's face-down Secret Project tile as other seats see it
   (core.js leaderSecretProjectBox builds the plain `.tile-back`): the
   Tech tile back, where the assets have it. */
function showTechBack(tile) {
  const url = cardBackUrl("tech");
  if (url) {
    tile.classList.add("pictured");
    tile.appendChild(cardBackImage(url, "tile-back-image"));
  }
  return tile;
}
