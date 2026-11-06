"use strict";

/* ---------- a board space in words ----------

   What a space's popover says beside (or without) its tile picture: the
   Agent icon it takes, whether it is a combat, Maker or Control space, the
   printed cost that applies now and the bonus spice lying on a Maker
   space. The popover (core.js openPopover/popoverNodes) and the board list
   (board.js spaceRow) both read these, so the two say the same thing. */

/* The tile's own marks, as words: crossed swords for a combat space
   [Main p. 10], the Maker icon, the Control flag. */
function spaceFlagWords(entry) {
  const flags = [];
  if (entry.combat) flags.push(t("board.flag_combat_space"));
  if (entry.maker) flags.push(phraseText("{maker}"));
  if (entry.critical) flags.push(phraseText("{control}"));
  return flags;
}

/* The popover's meta line: the Agent icon the space takes, as the Board
   Guide heads each space ("Agent icon: Landsraad" [Board Guide pp. 1-2]),
   then the flags. The board list needs no icon word: it already groups its
   rows under these headings. */
function spaceMetaWords(entry) {
  const group = AGENT_ICON_GROUPS.find(([value]) => value === entry.agent_icon);
  const words = group ? [t("board.space_agent_icon", { icon: group[1] })] : [];
  return words.concat(spaceFlagWords(entry));
}

/* The catalog id of a space entry (localizeCatalog() edits entries in
   place, so the entry is the catalog's own object). */
function spaceIdOf(entry) {
  const spaces = (state.catalog && state.catalog.spaces) || {};
  return Object.keys(spaces).find((id) => spaces[id] === entry) || null;
}

/* The printed cost option that applies now, for a space whose cost depends
   on the table rather than on the player's choice: the Swordmaster costs
   8 Solari until any player has their Swordmaster, then 6 [Board Guide
   p. 2], which the engine charges as option 1 (agent_turn.py
   _effective_costs). null for every other space, or with no table yet. */
function currentSpaceCostOption(entry) {
  if (entry.dynamic_cost !== "swordmaster") return null;
  const players = state.view && state.view.players;
  if (!players || !players.length) return null;
  return players.some((player) => player.swordmaster_acquired) ? 1 : 0;
}

/* The space's option lines, in their printed order: both stay listed
   (actionPreviewNodes picks one by the action's cost_option); the one that
   applies now is tagged and the other dimmed. */
function spaceOptionNodes(entry) {
  const current = currentSpaceCostOption(entry);
  return spaceOptionsFor(entry).map((option, index) => {
    const line = spaceOptionLine(option);
    if (current === null) return line;
    if (index === current) {
      line.classList.add("space-cost-now");
      const tag = document.createElement("span");
      tag.className = "space-cost-tag";
      tag.textContent = t("board.space_cost_now");
      line.appendChild(tag);
    } else {
      line.classList.add("space-cost-later");
    }
    return line;
  });
}

/* What lies on the space now, beyond its printed text: the bonus spice on
   a Maker space, in the board list's own words. */
function spaceStatusNodes(entry) {
  if (!entry.maker || !state.view) return [];
  const spaceId = spaceIdOf(entry);
  const bonus = new Map(state.view.maker_bonus_spice || []);
  if (!spaceId || !bonus.has(spaceId)) return [];
  const line = document.createElement("div");
  line.className = "popover-line space-bonus";
  line.appendChild(tNode("board.bonus_spice", { count: bonus.get(spaceId) }));
  return [line];
}
