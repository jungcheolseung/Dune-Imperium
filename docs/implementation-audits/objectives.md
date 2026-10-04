# Objective implementation audit

This checklist records how the five Objective cards interact with every
engine path that reads battle icons. The official summaries under
`docs/rules/` remain the source of truth; card identification (icons,
player-count marks, the First Player mark) was cross-checked against the
official Design Diary 2 images as recorded in `docs/rules/sources.md`.
Re-audited on 2026-08-30; updated on 2026-10-04 for Bloodlines' wild
Conflicts and the Objective flip targets (OQ-005 correction).

## Content and setup

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Card suite | Five physical Objectives: two Crysknife (one marked 4/6 players), two Desert Mouse (one grants First Player, one marked 4/6 players), one Ornithopter marked 1-3 players. Every card prints "This counts as a Conflict card you've already won." [Objective card] (card photos, 2026-10-04; the Crysknife 4/6P mark was added then). | `objectives_for_players(4)` keeps four cards and excludes the Ornithopter card, so a four-player game deals two Crysknife and two Desert Mouse icons [Main pp. 3, 5]. |
| Deal | Setup shuffles the four-player suite and deals one Objective per seat face up in the owner's supply; the printed First Player mark selects the First Player. | Exactly one card in the four-player suite grants First Player; `assign_objectives` fails loudly if the dealt suite ever breaks that [Main p. 5]. |
| Visibility | `PlayerState.objective_ids`, `won_conflict_ids`, and `face_down_battle_card_ids` are public in every `PlayerView`. | A flipped card's identity stays public. The cards were public while face up, so this falls under the OQ-010 past-public-information boundary, not hidden state. |

## Battle icon paths

| Path | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Combat immediate matching | `_matching_battle_card` scans the winner's face-up Objectives and won Conflicts uniformly; a same-icon pair is mandatory, flips both cards face down, and gains 1 VP. | The new Conflict card is not yet in `won_conflict_ids` while matching, so it cannot pair with itself [Main p. 14]. |
| Wild during Combat | A newly won Propaganda never pairs immediately with a printed icon, and a printed win never pairs with a face-up Propaganda. | Immediate matching is defined over the three printed icons; pairing the wild icon is an Endgame action [Main pp. 14, 20]. |
| Endgame wild matching | Inside the owner's OQ-001 window, every (face-up wild, face-up printed) pair is offered as its own `match_endgame_wild_icon` action; Objectives are valid printed-side candidates. Every pair of two face-up wilds is offered too, once in sorted order (`rules/endgame.py`). Matching flips both cards and gains 1 VP; the offers are recomputed after every action. A card with no printed icon (Economic Supremacy, Epic) is never a partner (OQ-094 (a)). | "Supply의 세 종류 중 하나의 battle icon"과 짝짓는다는 문장은 Conflict와 Objective를 구분하지 않으므로 Objective 포함이 맞다 [Main p. 20]. wild끼리도 짝지을 수 있다 [Bloodlines p. 5]; the offer is not gated on the option, but only Bloodlines adds wild Conflicts (the wild Skirmish I and Storms in the South II), so without Bloodlines Propaganda is the only wild and no wild-wild pair can arise. |
| Endgame Intrigue flips | Crysknife, Desert Mouse, and Ornithopter pay their Endgame cost through `FlipBattleCard`, which targets the owner's face-up won Conflict cards **and Objectives** bearing the printed icon or the wild icon; Grasp Arrakis's `FlipFaceUpConflictCard` takes face-up Objectives too. | An Objective "counts as a Conflict card you've already won" [Objective card] (OQ-005 correction 2026-10-04; before it, Objectives were wrongly excluded). Pinned by `test_endgame_flip_takes_a_face_up_objective_card`. |

## OQ-005: multiple matching candidates

- **Combat side — unreachable with official content.** Per player, at most
  one face-up battle card per printed icon can exist: setup deals exactly
  one Objective per player, the only later face-up addition is a won
  Conflict that immediately and mandatorily pairs on arrival, and every
  other transition only flips cards face down. Wild cards never pair on
  arrival [Main p. 20]: without Bloodlines Propaganda is the single wild
  card, and Bloodlines' two wild Conflicts (the wild Skirmish I, Storms in
  the South II) may sit face up beside it, but every wild pair is an
  Endgame choice [Bloodlines p. 5]. The one exception is an Ornithopter
  Fleet owner, whose icons (wilds included) all count as Ornithopters
  [Bloodlines p. 12]: those cards pair off in a fixed order without the
  guard (`rules/ornithopter.py`). The `NotImplementedError`
  guard in `_matching_battle_card` therefore stays as a tripwire for future
  content, not as a reachable boundary.
- **Endgame side — the owner chooses.** Multiple candidates do occur (for
  example a Crysknife Objective plus a Crysknife won Conflict next to
  Propaganda), and the choice is a real decision: the wild uses up the card
  it pairs with, so pairing it with a card no held Endgame Intrigue can flip
  keeps an intrigue target (for example pairing Propaganda with an
  Ornithopter Conflict leaves a Crysknife Objective for the Crysknife
  Intrigue). The window offers each pair as a separate
  action, resolving the selection question for Endgame play.
- **2026-08-30 soak evidence.** 60 base-ruleset and 20 CHOAM random games
  ran to `FINISHED` with replay verification while asserting the face-up
  invariant after every transition: 181/62 immediate pairs, 32/8 Endgame
  wild matches, and 1/0 Endgame Intrigue flips fired without a violation.

## Action and replay compatibility

The fixed catalog encodes `pass_endgame_intrigue` plus one
`match_endgame_wild_icon` template per (wild, printed) battle-card pair and
one per pair of two wilds (`action_codec._endgame_wild_templates`). Without
Bloodlines that is Propaganda against the fifteen printed-icon Conflicts and
the four four-player Objectives, 19 templates. Bloodlines catalogs have three
wild Conflicts (Propaganda, the wild Skirmish I, Storms in the South II): 3 × 19
(wild, printed) pairs plus 3 wild-wild pairs, 60 templates. Epic's Economic
Supremacy prints no icon and adds none (OQ-094). Flip targets for the
Endgame Intrigue cards (Crysknife, Desert Mouse, Ornithopter, and Grasp
Arrakis) reuse the `flip_battle_card` choice-slot templates, one per
Conflict of the catalog and, since codec v130 (OQ-005 correction,
2026-10-04), one per Objective of the player count.

## Explicitly retained guards

- `_matching_battle_card` raises `NotImplementedError` if a Conflict icon
  is ever untranscribed or if two face-up same-icon candidates ever become
  reachable; both would signal new content that must reopen OQ-005.
- All four Tier III Conflicts, including Propaganda, are in every game's
  deck, so the wild paths stay exercised [Main p. 4].
