"use strict";

/* ---------- staged Agent turn ----------

   The server offers an Agent turn as one flat list: every legal
   (card, space, cost option, graft) is its own `agent_turn` action, because
   that is what the action codec and the learning agents need. A person
   plays it in steps: the card, then the space, then what is still open.
   The steps are only a view of that same list: the page filters it by
   what has been picked and posts the one action index that remains, so
   neither the engine nor the codec knows the difference. Either order
   works (a space first lights the cards that can go there). The flat list
   stays behind a toggle. */
/* The count families that move units into and out of the Conflict; they
   get a stepper on the board as well (renderTrackMarkers). */
const FORCE_STEPPER_ACTIONS = new Set([
  "deploy_troops",
  "withdraw_troops",
  "deploy_commanders",
  "withdraw_commanders",
]);
const PLACEMENT_ACTION = "agent_turn";
const FULL_LIST_KEY = "dune.fullActionList";

function placementActions() {
  if (!state.actions) return [];
  return state.actions.actions.filter((action) => action.action_id === PLACEMENT_ACTION);
}

function fullActionList() {
  return storageGet(FULL_LIST_KEY) === "1";
}

function stagedTurn() {
  return !state.review && !fullActionList() && placementActions().length > 0;
}

/* Whether a placement fits what has been picked; any other action always
   does. Two picked cards are a graft: "you may use an Agent icon from
   either card" [Immortality p. 10], and the server lists that as the graft
   placements of each card, so the pair reaches the union of the two. */
function matchesPick(action, pick = state.pick) {
  if (!pick || action.action_id !== PLACEMENT_ACTION) return true;
  const args = action.arguments;
  if (pick.spaceId && args.space_id !== pick.spaceId) return false;
  if (pick.partnerId) {
    return (
      args.graft === true &&
      (args.card_id === pick.cardId || args.card_id === pick.partnerId)
    );
  }
  return !pick.cardId || args.card_id === pick.cardId;
}

function isGraftCard(instanceId) {
  const entry = lookup(baseId(instanceId));
  return Boolean(entry && entry.graft);
}

function graftPlacements(cardId) {
  return placementActions().filter(
    (action) => action.arguments.graft === true && action.arguments.card_id === cardId
  );
}

/* Whether two hand cards can be played together: one of them is a Graft
   card [Immortality p. 10] and the server offers a graft placement for at
   least one of them (a card with no Agent icon leans on the other's). */
function canPair(cardId, otherId) {
  const hand = (state.view && state.view.private && state.view.private.hand) || [];
  if (cardId === otherId || !hand.includes(cardId) || !hand.includes(otherId)) return false;
  if (!isGraftCard(cardId) && !isGraftCard(otherId)) return false;
  return graftPlacements(cardId).length > 0 || graftPlacements(otherId).length > 0;
}

/* A hand card that could join (or replace the partner of) the picked card. */
function partnerCandidate(instanceId) {
  const pick = state.pick;
  return Boolean(
    pick && pick.cardId && stagedTurn() &&
    instanceId !== pick.partnerId && canPair(pick.cardId, instanceId)
  );
}

/* A pick outlives re-renders (another seat's doorbell must not undo it) but
   not the actions it was made from. */
function sanitizePick() {
  if (!state.pick) return;
  const supported = () => placementActions().some((action) => matchesPick(action));
  if (stagedTurn() && !supported() && state.pick.partnerId) delete state.pick.partnerId;
  if (!stagedTurn() || !supported()) state.pick = null;
}

function clearPick(part) {
  if (!state.pick) return;
  if (part) delete state.pick[part];
  if (part === "cardId" && state.pick.partnerId) {
    state.pick.cardId = state.pick.partnerId;
    delete state.pick.partnerId;
  }
  if (!part || (!state.pick.cardId && !state.pick.spaceId)) state.pick = null;
  closePopover();
  render();
}

/* With a pick made, the other cards (or spaces) that could take its place:
   they stay faintly lit, because a click on one swaps the pick. */
function pickAlternative(ref, part) {
  const pick = state.pick;
  if (!pick || !pick[part] || pick[part] === ref || !stagedTurn()) return false;
  const rest = { ...pick, [part]: ref };
  return placementActions().some((action) => matchesPick(action, rest));
}

/* One step of the staged turn: `ref` is a card or a space of some legal
   placement, or a hand card that can be grafted to the picked one. Returns
   false when the click is not part of a placement. */
function pickStep(ref, entry, anchor) {
  const placements = placementActions();
  const current = state.pick || {};
  const joins = Boolean(current.cardId) && canPair(current.cardId, ref);
  const part =
    joins || placements.some((action) => action.arguments.card_id === ref)
      ? "cardId"
      : placements.some((action) => action.arguments.space_id === ref)
        ? "spaceId"
        : null;
  if (!part) return false;
  if (current[part] === ref || (part === "cardId" && current.partnerId === ref)) {
    clearPick(current.partnerId === ref ? "partnerId" : part);
    return true;
  }
  const next = { ...current };
  if (part === "spaceId") next.spaceId = ref;
  else if (joins) next.partnerId = ref;
  else {
    next.cardId = ref;
    delete next.partnerId;
  }
  if (!placements.some((action) => matchesPick(action, next))) {
    /* The halves of the pick cannot go together. */
    const cards = [current.cardId, current.partnerId].filter(Boolean).map(nameOf).join(" + ");
    note(
      t("turn.no_route", {
        from: part === "spaceId" ? cards : entry ? entry.name : nameOf(ref),
        to: part === "spaceId" ? (entry ? entry.name : nameOf(ref)) : nameOf(current.spaceId),
      })
    );
    if (entry) pinPopover(entry, anchor);
    return true;
  }
  state.pick = next;
  const candidates = pickCandidates(next);
  if (next.cardId && next.spaceId && candidates.length === 1) {
    applyPlacement(candidates[0]);
    return true;
  }
  render();
  if (next.cardId && next.spaceId) openPlacementChooser(candidates);
  return true;
}

/* The placements a pick still allows. For a graft pair the server lists the
   same move once per card that can stand as the placed one; whichever icon
   is used "both cards are treated as having sent the Agent" [Immortality
   p. 10], so those are one choice here, sent with the first-picked card
   when it can be. */
function pickCandidates(pick = state.pick) {
  const fitting = placementActions().filter((action) => matchesPick(action, pick));
  if (!pick || !pick.partnerId) return fitting;
  const byOption = new Map();
  for (const action of fitting) {
    const option = JSON.stringify(
      Object.entries(action.arguments)
        .filter(([key]) => key !== "card_id")
        .sort(([a], [b]) => a.localeCompare(b))
    );
    const kept = byOption.get(option);
    if (!kept || action.arguments.card_id === pick.cardId) byOption.set(option, action);
  }
  return [...byOption.values()];
}

/* Post a placement. With two cards picked the other one follows as the
   graft partner, which the engine asks for in the very next frame. */
function applyPlacement(action) {
  const pick = state.pick;
  const partner =
    pick && pick.partnerId
      ? (action.arguments.card_id === pick.cardId ? pick.partnerId : pick.cardId)
      : null;
  const played = applyAction(action.index);
  if (partner) played.then(() => followWithPartner(partner));
}

function followWithPartner(partnerId) {
  const decision = state.summary && state.summary.decision;
  if (
    !decision || decision.kind !== "graft_partner" ||
    decision.owner !== state.viewSeat || !state.actions
  ) {
    return;
  }
  const action = state.actions.actions.find(
    (item) =>
      item.action_id === "choose_graft_partner" && item.arguments.card_id === partnerId
  );
  if (action) {
    applyAction(action.index);
    return;
  }
  /* The space was open to this card only with a certain partner (an
     occupied space on Tleilaxu Infiltrator's promise, a Bond icon on
     Ghola's): the engine's own partner choice is on screen now. */
  note(t("turn.partner_not_allowed", { name: nameOf(partnerId) }));
}

/* What still tells two placements of one card on one space apart: the
   space's cost option and whether the card is grafted. */
function placementOptionNode(action, candidates) {
  const line = document.createElement("span");
  line.className = "pick-option";
  const space = state.catalog.spaces[action.arguments.space_id];
  const option = space && spaceOptionsFor(space)[action.arguments.cost_option || 0];
  if (option && candidates.some((other) => other.arguments.cost_option !== action.arguments.cost_option)) {
    line.append(costNode(option.cost), icon("arrow_right", "→"), iconize(option.effect));
  }
  const differs = (key) =>
    candidates.some((other) => other.arguments[key] !== action.arguments[key]);
  if (differs("discount")) {
    const discount = document.createElement("span");
    discount.append(
      action.arguments.discount
        ? amount(action.arguments.discount, action.arguments.discount, 1)
        : t("turn.no_discount"),
      action.arguments.discount ? t("turn.discount_suffix") : ""
    );
    line.appendChild(discount);
  }
  if (differs("infiltrate_post_id")) {
    const spy = document.createElement("span");
    spy.textContent = action.arguments.infiltrate_post_id
      ? t("turn.spy_recall", { post: prettify(action.arguments.infiltrate_post_id) })
      : t("turn.spy_recall_none");
    line.appendChild(spy);
  }
  if (candidates.some((other) => Boolean(other.arguments.graft) !== Boolean(action.arguments.graft))) {
    const graft = document.createElement("span");
    graft.className = "pick-graft";
    graft.textContent = action.arguments.graft ? t("turn.graft_pending") : t("turn.graft_solo");
    line.appendChild(graft);
  }
  if (!line.childNodes.length) line.appendChild(describeAction(action));
  return line;
}

function placementOptionItem(action, candidates) {
  const item = actionItem(action, applyPlacement);
  const button = item.querySelector("button");
  const badges = [...button.querySelectorAll(".irreversible-badge, .shortfall-badge")];
  button.textContent = "";
  button.append(placementOptionNode(action, candidates), ...badges);
  return item;
}

/* The options of a complete pick, next to the space they are about. The
   side panel lists the same ones, so closing this loses nothing. */
function openPlacementChooser(candidates) {
  const pick = state.pick;
  const anchor =
    document.querySelector(`.hotspot[data-space="${pick.spaceId}"]`) ||
    document.querySelector(`.space-row[data-space="${pick.spaceId}"]`) ||
    el("actions");
  const pop = el("card-popover");
  pop.textContent = "";
  pop.classList.remove("hover");
  const title = document.createElement("div");
  title.className = "popover-title";
  title.textContent = `${pickedCardNames(pick)} → ${nameOf(pick.spaceId)}`;
  pop.appendChild(title);
  for (const action of candidates) pop.appendChild(placementOptionItem(action, candidates));
  placePopover(pop, anchor, 340);
  popoverPinned = true;
}

function pickedCardNames(pick) {
  return [pick.cardId, pick.partnerId].filter(Boolean).map(nameOf).join(" + ");
}

function pickStepNode(number, label, ref, part) {
  const step = document.createElement("button");
  step.type = "button";
  step.className = "pick-step" + (ref ? " done" : "");
  step.disabled = !ref || state.busy;
  step.append(`${number} ${label} · `);
  const value = document.createElement("strong");
  value.textContent = ref ? nameOf(ref) : t("turn.choose");
  step.appendChild(value);
  if (ref) {
    step.append(" ✕");
    step.title = t("turn.choose_again");
    step.addEventListener("click", () => clearPick(part));
  }
  return step;
}

/* The decision panel of the seat to move. An Agent turn is staged (card,
   space, what is left), with the turn's other actions under it; everything
   else, and the staged turn behind its toggle, is the flat list. */
function renderActionPanel(box) {
  const actions = state.actions.actions;
  const placements = placementActions();
  if (state.summary.decision && state.summary.decision.kind === "reveal") {
    renderRevealPanel(box, actions);
    return;
  }
  if (!stagedTurn()) {
    /* What follows a placement (the graft partner, a card to trash, a space
       for a Spy) is a short list whose cards and spaces are lit on the
       table: a click there is the same as the button here (tableClick). */
    if (!placements.length && actions.some((action) => tableRefs(action).length)) {
      const hint = document.createElement("div");
      hint.className = "pick-hint muted";
      hint.textContent = t("turn.table_hint");
      box.appendChild(hint);
    }
    /* The flat list of an Agent turn is long: its way back to the steps
       goes on top, where the panel cannot push it under the log. */
    if (placements.length) box.appendChild(actionListToggle(false, actions.length));
    appendActionItems(box, actions);
    return;
  }
  const pick = state.pick || {};
  const steps = document.createElement("div");
  steps.className = "pick-steps";
  steps.appendChild(pickStepNode("①", t("turn.step_card"), pick.cardId, "cardId"));
  if (pick.partnerId) {
    steps.appendChild(pickStepNode("＋", t("turn.step_together"), pick.partnerId, "partnerId"));
  }
  steps.append(
    icon("arrow_right", "→"),
    pickStepNode("②", t("turn.step_space"), pick.spaceId, "spaceId")
  );
  box.appendChild(steps);

  const hint = document.createElement("div");
  hint.className = "pick-hint muted";
  const candidates = pickCandidates();
  if (pick.cardId && pick.spaceId) {
    hint.textContent = t("turn.step3_hint");
    box.appendChild(hint);
    for (const action of candidates) box.appendChild(placementOptionItem(action, candidates));
  } else {
    const hand = (state.view && state.view.private && state.view.private.hand) || [];
    const canJoin =
      pick.cardId && !pick.partnerId && hand.some((other) => canPair(pick.cardId, other));
    hint.textContent = pick.partnerId
      ? t("turn.hint_both_picked")
      : canJoin
        ? (isGraftCard(pick.cardId)
            ? t("turn.hint_graft_required")
            : t("turn.hint_graft_optional"))
        : pick.cardId
          ? t("turn.hint_choose_space")
          : pick.spaceId
            ? t("turn.hint_choose_card")
            : t("turn.hint_start");
    box.appendChild(hint);
  }

  const others = actions.filter((action) => action.action_id !== PLACEMENT_ACTION);
  if (others.length) {
    const heading = document.createElement("div");
    heading.className = "pick-others muted";
    heading.textContent = t("turn.or");
    box.appendChild(heading);
    appendActionItems(box, others);
  }
  box.appendChild(actionListToggle(true, actions.length));
}

function actionListToggle(staged, count) {
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "action-list-toggle";
  toggle.textContent = staged ? t("turn.show_full_list", { count }) : t("turn.show_steps");
  toggle.addEventListener("click", () => {
    if (staged) storageSet(FULL_LIST_KEY, "1");
    else storageRemove(FULL_LIST_KEY);
    state.pick = null;
    render();
  });
  return toggle;
}

/* The legal actions a table object takes part in. During a staged turn the
   placements are the ones that still fit the pick, so the cards and the
   spaces light up step by step. */
function legalActionsFor(ref) {
  if (!state.actions) return [];
  const staged = stagedTurn();
  return state.actions.actions.filter(
    (action) => actionRefs(action).includes(ref) && (!staged || matchesPick(action))
  );
}

/* Click on a table object: a step of the staged Agent turn, or else one
   legal action applies directly, several focus the action list, none shows
   the detail popover. */
function tableClick(ref, entry, anchor) {
  if (state.busy) return;
  if (stagedTurn() && pickStep(ref, entry, anchor)) return;
  const legal = legalActionsFor(ref);
  if (legal.length === 1) {
    applyAction(legal[0].index);
    return;
  }
  if (legal.length > 1) {
    focusActions(ref, entry ? entry.name : ref);
    note(
      t("turn.multiple_choices", { name: entry ? entry.name : ref, count: legal.length })
    );
    return;
  }
  if (entry) pinPopover(entry, anchor);
}

function section(parent, title) {
  const heading = document.createElement("h3");
  heading.textContent = title;
  const body = document.createElement("div");
  parent.append(heading, body);
  return body;
}
