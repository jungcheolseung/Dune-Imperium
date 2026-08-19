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
| Chance and replay | Prepare the Way's draw uses the same personal discard reshuffle decision as board-space and Spy draws. | Its Reserve instance ID remains stable through discard, shuffle, hand, and in-play zones. |
| RL encoding | Every transcribed physical card copy can take its Agent destinations, including Infiltrate variants. | Reserve actions grew the catalog from 554 actions in codec v6 to 754 in v7; the first Imperium batch grows it to 832 in v8 and Sardaukar Soldier to 845 in v9. |

## Card-level verification

- The two printed card images linked by the Reserve content manifest were
  visually checked on 2026-08-19 for Agent icons, conditional Agent text, and
  Reveal values.
- Maula Pistol, Truthtrance, and Sardaukar Soldier were bootstrapped from DIU
  `imperium.JSON` at
  reviewed commit `990523441421d34a670505d5b32318f01754b960`. Their local
  physical counts and stable IDs continue to come from the verified manifest;
  DIU's conflicting `quantity` values were not imported.
- Main pp. 6, 9, 12-13, and 20 provide the general play, acquisition, Reveal,
  draw, and Reserve-return rules; card artwork supplies the card-specific data.

## Deferred boundaries

- All shared Imperium cards except Maula Pistol, Truthtrance, and Sardaukar
  Soldier still have only identity and acquisition-cost data. Drawing one of
  those cards fails explicitly until its play data is transcribed.
- Signet Ring remains blocked on Leader ability implementation.
- Reveal effects that require choices or change state beyond static Persuasion
  and strength need a serial Reveal-effect decision path.
