# Personal card implementation audit

This checklist records the first M6 content slice that plays non-starting cards
from a player's personal deck. General Agent, Reveal, and deck-building rules in
`docs/rules/` remain authoritative.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Shared resolution | Starting and Reserve instances resolve through one personal-card boundary for Agent icons and Reveal values. | Untranscribed Imperium cards fail explicitly instead of being treated as blank cards. |
| Prepare the Way | The card has Landsraad and City Agent icons, draws one personal card in its Agent box when its owner has at least two Bene Gesserit Influence, and reveals for two Persuasion. | The influence requirement is checked when the Agent turn is committed; an unavailable conditional effect does not create a decision. |
| The Spice Must Flow | The card has no Agent icon, reveals for one strength, and still grants one VP only when acquired. | Trashing it later does not remove the acquired VP. |
| Maula Pistol | The first shared-deck card slice has Fremen affiliation, City and Spice Trade Agent icons, draws one personal card in its Agent box, and reveals for one Persuasion and one strength. | The draw uses the existing replayable personal-deck reshuffle path. |
| Truthtrance | The card has Bene Gesserit affiliation, all four Faction Agent icons, no Agent-box effect, and reveals for one Persuasion. | A missing Agent effect is transcribed data, distinct from an untranscribed card. |
| Sardaukar Soldier | The card has Emperor affiliation, a City Agent icon, reveals for one Persuasion and one strength, and draws one Intrigue card when trashed. | Agent-card and Combat-reward trash paths now share one transition, including Reserve return and card-specific trash triggers. |
| Hidden Missive | The card has Bene Gesserit affiliation, a Landsraad Agent icon, and reveals for one Persuasion and one strength. At two Bene Gesserit Influence, its Agent box recruits one troop and draws one personal card. | Recruited troops join the Agent turn's shared deployable count, and the draw uses the replayable personal-deck reshuffle path. |
| Desert Survival | The card has Fremen affiliation, a Spice Trade Agent icon, reveals for one Persuasion and one strength, and may trash one personal card in its Agent box. | The explicit decline and card choices cover hand, discard pile, and cards in play through the shared trash transition. |
| Smuggler's Harvester | The card has Spacing Guild affiliation, a Spice Trade Agent icon, and reveals for one Persuasion. Its Agent box gains one Spice only at a Maker space. | The condition uses the destination's typed `maker` property, so it is unavailable at other Spice Trade spaces. |
| Fedaykin Stilltent | The card has Fremen affiliation and a Spice Trade Agent icon. Its Agent box recruits one troop at a Maker space, and its Reveal effect gains one Water. | Agent recruitment contributes to the current turn's deployable count; the automatic Reveal gain uses the shared typed Reveal-effect schema. |
| Northern Watermaster | The card has Fremen affiliation and a City Agent icon. Its Agent box gains one Water; Reveal gives one Persuasion and two Spice with Fremen Bond. | Bond requires another Fremen-affiliated card among cards already in play and cards revealed this turn. |
| Maker Keeper | The card has Bene Gesserit and Fremen affiliations, City and Spice Trade Agent icons, and reveals for two Persuasion. At two Bene Gesserit Influence it gains one Water; at two Fremen Influence it gains one Spice. | The two conditions resolve independently, including receiving both rewards when both thresholds are met. |
| Southern Elders | The card has Bene Gesserit and Fremen affiliations and matching Faction Agent icons. Bene Gesserit Bond recruits two troops; Reveal always gains one Water and Fremen Bond adds two Persuasion. | Agent and Reveal paths share one typed Faction Bond check, and one card may carry multiple independently gated Reveal effects. |
| Weirding Woman | The card has Bene Gesserit affiliation, City and Spice Trade Agent icons, and reveals for one Persuasion and one strength. Bene Gesserit Bond returns the Agent card from play to its owner's hand. | The returned card remains available for the same round's later Reveal turn. |
| Ecological Testing Station | The card has Fremen affiliation and Fremen and City Agent icons. Its Agent box may pay two Water to draw two personal cards; Reveal gives one Persuasion and Fremen Bond gains one Water. | Payment has explicit pay and decline actions, and its draw uses the replayable personal-deck reshuffle path. |
| Paracompass | The card has a City Agent icon and gains two Solari in its Agent box. Reveal gains two Persuasion with High Council and one additional Persuasion when the player also has Swordmaster. | The card's conditional Persuasion stacks with the normal two-Persuasion High Council bonus. |
| Chance and replay | Prepare the Way's draw uses the same personal discard reshuffle decision as board-space and Spy draws. | Its Reserve instance ID remains stable through discard, shuffle, hand, and in-play zones. |
| RL encoding | Every transcribed physical card copy can take its Agent destinations, including Infiltrate variants. | Imperium batches grow the catalog through 832 in v8, 845 in v9, 857 in v10, 971 in v11, 991 in v12, 1001 in v13, 1014 in v14, 1060 in v15, 1068 in v16, 1114 in v17, 1133 in v18, and 1146 in v19. |

## Card-level verification

- The two printed card images linked by the Reserve content manifest were
  visually checked on 2026-08-19 for Agent icons, conditional Agent text, and
  Reveal values.
- These thirteen shared cards were bootstrapped from DIU `imperium.JSON` at
  reviewed commit `990523441421d34a670505d5b32318f01754b960`. Their local
  physical counts and stable IDs continue to come from the verified manifest;
  DIU's conflicting `quantity` values were not imported.
- Main pp. 6, 9, 12-13, and 20 provide the general play, acquisition, Reveal,
  draw, and Reserve-return rules; card artwork supplies the card-specific data.

## Deferred boundaries

- All shared Imperium cards other than the thirteen listed above still have only
  identity and acquisition-cost data. Drawing one of those cards fails
  explicitly until its play data is transcribed.
- Signet Ring remains blocked on Leader ability implementation.
- Reveal effects that require choices or change state beyond static Persuasion
  and strength need a serial Reveal-effect decision path.
