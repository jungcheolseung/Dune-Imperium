/* The table's loose pieces drawn from the Steam app's pictures: the First
   Player marker on its holder's seat panel. Every helper here falls back
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
